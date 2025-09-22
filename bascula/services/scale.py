"""ESP32/HX711 scale service with calibration and dummy fallback."""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Deque, Optional

try:  # pragma: no cover - optional dependency during docs builds
    import serial
    from serial import SerialException
except Exception:  # pragma: no cover - fallback when pyserial missing
    serial = None  # type: ignore
    SerialException = Exception  # type: ignore

try:  # pragma: no cover - Python < 3.11 not supported in production
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore

try:  # pragma: no cover - dependency already declared in requirements.txt
    import tomli_w
except Exception:  # pragma: no cover - keep running without persisting
    tomli_w = None  # type: ignore

LOGGER = logging.getLogger("bascula.scale")

CFG_DIR = Path(os.environ.get("BASCULA_CFG_DIR", Path.home() / ".config/bascula"))
CFG_FILE = CFG_DIR / "scale.toml"

MAX_WEIGHT = 9999.0
WINDOW_SIZE = 5


class _DummyScale:
    """Simple simulator used when the serial device is unavailable."""

    def __init__(self) -> None:
        self._weight = 0.0
        self._drift = 0.0

    def read(self) -> float:
        # Oscillate gently to make the UI feel alive
        self._drift += 0.35
        if self._drift > 360.0:
            self._drift -= 360.0
        self._weight = max(0.0, (50.0 * abs(math.sin(self._drift / 25.0))))
        return self._weight

    def tare(self) -> None:
        self._weight = 0.0

    def zero(self) -> None:
        self._weight = 0.0


class ScaleService:
    """High level interface to the ESP32/HX711 firmware."""

    def __init__(
        self,
        port: Optional[str] = None,
        *,
        baud: int = 115200,
        decimals: Optional[int] = None,
        density: Optional[float] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or LOGGER
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._subscribers: list[Callable[[float, bool], None]] = []

        self._config = self._load_config()

        self._port = self._resolve_port(port)
        self._baud = int(baud)

        self._host_tare_mode: bool = bool(int(os.getenv("BASCULA_SCALE_HOST_TARE", "0")))
        mode_label = "host" if self._host_tare_mode else "dispositivo"
        self.logger.info("Modo tara seleccionado: %s", mode_label)

        self._last_raw: float = 0.0
        self._factor = float(self._config.get("factor", 1.0) or 1.0)
        if abs(self._factor) < 1e-6:
            self._factor = 1.0
        cfg_offset = float(self._config.get("offset", 0.0) or 0.0)
        cfg_tare = float(self._config.get("tare", 0.0) or 0.0)
        if not self._host_tare_mode:
            if cfg_offset or cfg_tare:
                self.logger.info(
                    "Firmware tare mode activo: ignoro offset/tare guardados (offset=%.3f, tare=%.3f).",
                    cfg_offset,
                    cfg_tare,
                )
            self._offset = 0.0
            self._tare = 0.0
        else:
            self._offset = cfg_offset
            self._tare = cfg_tare

        self._decimals = self._clamp_decimals(
            decimals if decimals is not None else self._config.get("decimals", 0)
        )
        self._density = self._clamp_density(
            density if density is not None else self._config.get("density", 1.0)
        )

        self._raw_value = 0.0
        self._net_weight = 0.0
        self._stable = False
        self._window: Deque[float] = deque(maxlen=WINDOW_SIZE)

        self._serial: Optional[serial.Serial] = None  # type: ignore[attr-defined]
        self._dummy = False
        self._backend: Optional[_DummyScale] = None

        self._connect_serial()
        self.start()

    # ------------------------------------------------------------------
    def _load_config(self) -> dict:
        if not CFG_FILE.exists() or tomllib is None:
            return {}
        try:
            return tomllib.loads(CFG_FILE.read_text())
        except Exception:
            self.logger.debug("No se pudo leer %s", CFG_FILE)
            return {}

    def _save_config(self) -> None:
        if tomli_w is None:
            return
        data = {
            "port": self._port,
            "factor": self._factor,
            "offset": self._offset if self._host_tare_mode else 0.0,
            "decimals": self._decimals,
            "density": self._density,
            "tare": self._tare if self._host_tare_mode else 0.0,
            "mode": "host" if self._host_tare_mode else "device",
        }
        try:
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            CFG_FILE.write_text(tomli_w.dumps(data))
        except Exception:
            self.logger.debug("No se pudo guardar configuración de báscula")

    def _resolve_port(self, port: Optional[str]) -> str:
        if port == "__dummy__":
            return "__dummy__"
        if port:
            return port
        env_port = os.environ.get("BASCULA_DEVICE")
        if env_port:
            return env_port
        return str(self._config.get("port", "/dev/serial0"))

    def _connect_serial(self) -> None:
        if serial is None or self._port == "__dummy__":
            self.logger.warning("Modo simulado: dependencia pyserial no disponible" if serial is None else "Modo simulado")
            self._dummy = True
            self._backend = _DummyScale()
            return

        attempts = 0
        while attempts < 5:
            attempts += 1
            try:
                self._serial = serial.Serial(self._port, self._baud, timeout=1)  # type: ignore[call-arg]
                self.logger.info("Báscula conectada en %s", self._port)
                return
            except PermissionError:
                self.logger.error("Añade a dialout y reinicia")
                break
            except SerialException as exc:
                self.logger.warning("No se puede abrir %s (%s). Reintentando...", self._port, exc)
                time.sleep(3)
            except FileNotFoundError as exc:
                self.logger.warning("%s no encontrado: %s", self._port, exc)
                break
        self.logger.warning("Modo simulado")
        self._serial = None
        self._dummy = True
        self._backend = _DummyScale()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ScaleService", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        try:
            if self._serial:
                self._serial.close()
        except Exception:  # pragma: no cover - hardware dependent
            pass

    close = stop

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._dummy:
                raw = float(self._backend.read() if self._backend else 0.0)
                self._process_sample(raw)
                time.sleep(0.2)
                continue

            if not self._serial:
                time.sleep(1.0)
                continue

            try:
                line = self._serial.readline().decode(errors="ignore").strip()
            except Exception as exc:  # pragma: no cover - hardware dependent
                self.logger.debug("Lectura serie falló: %s", exc)
                time.sleep(0.3)
                continue

            if not line:
                continue
            try:
                raw = float(line)
            except ValueError:
                self.logger.debug("Valor inválido desde báscula: %r", line)
                continue
            self._process_sample(raw)

    def _process_sample(self, raw: float) -> None:
        with self._lock:
            self._last_raw = raw
            self._raw_value = raw
            denominator = self._factor if abs(self._factor) >= 1e-9 else 1e-9
            effective_offset = self._offset if self._host_tare_mode else 0.0
            effective_tare = self._tare if self._host_tare_mode else 0.0
            grams = (raw - effective_offset) / denominator
            grams -= effective_tare
            if abs(grams) < 0.05:
                grams = 0.0
            grams = max(0.0, min(MAX_WEIGHT, grams))
            self._window.append(grams)
            if self._window:
                avg = sum(self._window) / len(self._window)
            else:
                avg = grams
            threshold = 0.1 if self._decimals else 0.5
            if len(self._window) == self._window.maxlen:
                delta = max(self._window) - min(self._window)
                self._stable = delta <= threshold
            else:
                self._stable = False
            rounded = round(avg, self._decimals)
            self._net_weight = max(0.0, min(MAX_WEIGHT, rounded))
        for callback in list(self._subscribers):
            try:
                callback(self._net_weight, self._stable)
            except Exception:  # pragma: no cover - subscriber safety
                self.logger.exception("Scale subscriber failed")

    # ------------------------------------------------------------------
    @property
    def net_weight(self) -> float:
        with self._lock:
            return float(self._net_weight)

    @property
    def stable(self) -> bool:
        with self._lock:
            return bool(self._stable)

    @property
    def decimals(self) -> int:
        with self._lock:
            return int(self._decimals)

    @property
    def density(self) -> float:
        with self._lock:
            return float(self._density)

    @property
    def simulated(self) -> bool:
        return bool(self._dummy)

    @property
    def calibration_factor(self) -> float:
        with self._lock:
            return float(self._factor)

    @property
    def calibration_offset(self) -> float:
        with self._lock:
            return float(self._offset)

    # ------------------------------------------------------------------
    def tare(self) -> None:
        with self._lock:
            if self._host_tare_mode:
                denominator = self._factor if abs(self._factor) >= 1e-9 else 1e-9
                self._tare = (self._last_raw - self._offset) / denominator
                self.logger.info("Tara en host: _tare=%.3f", self._tare)
            else:
                self._offset = 0.0
                self._tare = 0.0
                self.logger.info("Tara delegada al dispositivo (modo firmware)")
            self._window.clear()
        if not self._host_tare_mode:
            if self._serial:
                self._send_command("TARE")
            elif self._backend:
                self._backend.tare()

    def zero(self) -> None:
        with self._lock:
            if self._host_tare_mode:
                self._offset = self._last_raw
                self._tare = 0.0
                self.logger.info("Zero en host: _offset=%.3f", self._offset)
            else:
                self._offset = 0.0
                self._tare = 0.0
                self.logger.info("Zero delegado al dispositivo (modo firmware)")
            self._window.clear()
        self._save_config()
        if not self._host_tare_mode:
            if self._serial:
                self._send_command("ZERO")
            elif self._backend:
                self._backend.zero()

    def calibrate_zero(self) -> float:
        with self._lock:
            self._offset = self._raw_value
            self._tare = 0.0
            self._window.clear()
        self._save_config()
        return self._offset

    def calibrate_known_weight(self, grams: float) -> float:
        grams = float(grams)
        if grams <= 0:
            raise ValueError("El peso conocido debe ser mayor que cero")
        with self._lock:
            delta = self._raw_value - self._offset
            if abs(delta) < 1e-6:
                raise ValueError("Coloca el peso conocido en la báscula")
            self._factor = delta / grams
            if abs(self._factor) < 1e-6:
                raise ValueError("Factor de calibración inválido")
            self._tare = 0.0
            self._window.clear()
        self._save_config()
        return self._factor

    def set_decimals(self, decimals: int) -> int:
        with self._lock:
            self._decimals = self._clamp_decimals(decimals)
            self._window.clear()
        self._save_config()
        return self._decimals

    def set_density(self, density: float) -> float:
        with self._lock:
            self._density = self._clamp_density(density)
        self._save_config()
        return self._density

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[float, bool], None]) -> None:
        if callable(callback):
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[float, bool], None]) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    def _send_command(self, command: str) -> None:
        if not self._serial:
            return
        try:
            data = f"{command.strip().upper()}\n".encode()
            self._serial.write(data)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.debug("No se pudo enviar %s: %s", command, exc)

    @staticmethod
    def _clamp_decimals(decimals: Optional[int]) -> int:
        value = 1 if int(decimals or 0) > 0 else 0
        return value

    @staticmethod
    def _clamp_density(density: Optional[float]) -> float:
        try:
            value = float(density)
        except Exception:
            value = 1.0
        return 1.0 if value <= 0 else value


HX711Service = ScaleService

__all__ = ["ScaleService", "HX711Service"]
