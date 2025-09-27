"""Scale service supporting serial and HX711 GPIO backends."""
from __future__ import annotations

import inspect
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Deque, List, Optional

from ..config.settings import ScaleSettings

try:  # pragma: no cover - optional dependency
    import serial  # type: ignore
    from serial import SerialException  # type: ignore
except Exception:  # pragma: no cover
    serial = None  # type: ignore
    SerialException = Exception  # type: ignore

try:  # pragma: no cover - optional dependency on Raspberry Pi
    import lgpio  # type: ignore
except Exception:  # pragma: no cover
    lgpio = None  # type: ignore

LOGGER = logging.getLogger("bascula.scale")

MAX_WEIGHT_G = 99999.0
HEARTBEAT_SECONDS = 1.0
POLL_INTERVAL = 0.1


class BackendUnavailable(RuntimeError):
    """Raised when a backend cannot operate."""


class BaseScaleBackend:
    """Common interface implemented by all backends."""

    name = "BASE"

    def start(self) -> None:  # pragma: no cover - default no-op
        """Prepare backend resources."""

    def stop(self) -> None:  # pragma: no cover - default no-op
        """Release backend resources."""

    def read(self) -> Optional[float]:  # pragma: no cover - interface method
        raise NotImplementedError

    def tare(self) -> None:  # pragma: no cover - optional
        """Instruct backend to tare if needed."""

    def zero(self) -> None:  # pragma: no cover - optional
        """Instruct backend to zero if needed."""


class SerialScaleBackend(BaseScaleBackend):
    """Backend reading weights from a serial device using pyserial."""

    name = "SERIAL"

    def __init__(self, port: str, baud: int, *, timeout: float = 0.5, logger: Optional[logging.Logger] = None) -> None:
        if serial is None:
            raise BackendUnavailable("pyserial not available")
        resolved = self._resolve_port(port)
        if not Path(resolved).exists():
            raise BackendUnavailable(f"device {resolved} not found")
        try:
            self._serial = serial.Serial(resolved, baudrate=baud, timeout=timeout)  # type: ignore[attr-defined]
        except SerialException as exc:  # pragma: no cover - depends on hardware
            raise BackendUnavailable(str(exc)) from exc
        self._logger = logger or LOGGER

    @staticmethod
    def _resolve_port(port: str) -> str:
        port = port.strip()
        if port == "serial0":
            return "/dev/serial0"
        if port and port.startswith("/dev/"):
            return port
        if port.startswith("tty"):
            return f"/dev/{port}"
        return port

    def stop(self) -> None:  # pragma: no cover - depends on hardware
        try:
            self._serial.close()
        except Exception:
            pass

    def read(self) -> Optional[float]:
        try:
            line = self._serial.readline().decode(errors="ignore").strip()
        except SerialException as exc:  # pragma: no cover - hardware dependent
            raise BackendUnavailable(str(exc)) from exc
        except Exception as exc:
            self._logger.debug("Serial read error: %s", exc)
            return None
        if not line:
            return None
        candidates = line.replace(",", ".").split()
        for token in candidates:
            fragment = token.split(":")[-1]
            try:
                return float(fragment)
            except ValueError:
                continue
        return None

    def _send_command(self, command: str) -> None:
        try:
            payload = f"{command}\n".encode()
            self._serial.write(payload)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._logger.debug("Serial command %s failed: %s", command, exc)

    def tare(self) -> None:
        self._send_command("TARE")

    def zero(self) -> None:
        self._send_command("ZERO")


class HX711GpioBackend(BaseScaleBackend):
    """Backend reading the HX711 via Raspberry Pi GPIO pins using lgpio."""

    name = "HX711_GPIO (lgpio)"

    def __init__(
        self,
        dt_pin: int,
        sck_pin: int,
        *,
        logger: Optional[logging.Logger] = None,
        read_timeout: float = 1.0,
        chip: int = 0,
    ) -> None:
        if lgpio is None:
            raise BackendUnavailable("lgpio not available")
        if dt_pin is None or sck_pin is None:
            raise BackendUnavailable("HX711 pins not configured")
        self._dt_pin = int(dt_pin)
        self._sck_pin = int(sck_pin)
        if self._dt_pin < 0 or self._sck_pin < 0:
            raise BackendUnavailable("HX711 pins must be positive BCM numbers")
        self._chip_id = int(chip)
        self._logger = logger or LOGGER
        self._read_timeout = read_timeout
        self._lock = threading.Lock()
        self._chip_handle: Optional[int] = None
        self._setup_gpio()

    def _setup_gpio(self) -> None:
        try:
            self._chip_handle = lgpio.gpiochip_open(self._chip_id)
            lgpio.gpio_claim_input(self._chip_handle, self._dt_pin)
            lgpio.gpio_claim_output(self._chip_handle, self._sck_pin, 0)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._cleanup_gpio()
            raise BackendUnavailable(f"lgpio setup failed: {exc}") from exc

    def _cleanup_gpio(self) -> None:
        if self._chip_handle is None:
            return
        try:
            try:
                lgpio.gpio_write(self._chip_handle, self._sck_pin, 0)
            except Exception:
                pass
            try:
                lgpio.gpio_free(self._chip_handle, self._sck_pin)
            except Exception:
                pass
            try:
                lgpio.gpio_free(self._chip_handle, self._dt_pin)
            except Exception:
                pass
        finally:
            try:
                lgpio.gpiochip_close(self._chip_handle)
            except Exception:
                pass
            self._chip_handle = None

    def stop(self) -> None:  # pragma: no cover - best effort
        self._cleanup_gpio()

    def read(self) -> Optional[float]:
        with self._lock:
            try:
                value = self._read_raw()
            except TimeoutError:
                return None
            except Exception as exc:
                raise BackendUnavailable(str(exc)) from exc
        return float(value)

    def _read_raw(self) -> int:
        if self._chip_handle is None:
            raise BackendUnavailable("lgpio chip not initialised")
        start = time.monotonic()
        while True:
            level = lgpio.gpio_read(self._chip_handle, self._dt_pin)
            if level == 0:
                break
            if time.monotonic() - start > self._read_timeout:
                raise TimeoutError("HX711 timeout waiting for data")
            time.sleep(0.001)

        value = 0
        for _ in range(24):
            lgpio.gpio_write(self._chip_handle, self._sck_pin, 1)
            time.sleep(0.000002)
            bit = lgpio.gpio_read(self._chip_handle, self._dt_pin)
            value = (value << 1) | (1 if bit else 0)
            lgpio.gpio_write(self._chip_handle, self._sck_pin, 0)
            time.sleep(0.000002)

        lgpio.gpio_write(self._chip_handle, self._sck_pin, 1)
        time.sleep(0.000002)
        lgpio.gpio_write(self._chip_handle, self._sck_pin, 0)

        if value & 0x800000:
            value -= 0x1000000
        return value


class ScaleService:
    """High level service managing scale backends and filtering."""

    def __init__(self, settings: Optional[ScaleSettings] = None, *, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or LOGGER
        self._settings = settings or ScaleSettings()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[..., None]] = []

        self._calibration_factor = max(1e-6, float(self._settings.calib_factor))
        self._offset = 0.0
        self._ml_factor = self._sanitize_ml_factor(self._settings.ml_factor)
        self._decimals = 1 if int(self._settings.decimals) > 0 else 0
        self._unit = self._settings.unit
        self._smoothing = max(1, int(self._settings.smoothing))
        self._window: Deque[float] = deque(maxlen=self._smoothing)
        self._last_weight_g = 0.0
        self._last_raw = 0.0
        self._stable = False
        self._signal_available = False
        self._signal_warning_emitted = False

        self._backend = self._select_backend()
        self._backend_name = self._backend.name
        self.logger.info("Scale backend: %s", self._backend_name)

        self.start()

    # ------------------------------------------------------------------
    def _select_backend(self) -> BaseScaleBackend:
        port = (self._settings.port or "").strip()
        if port and port not in {"__dummy__", ""}:
            try:
                return SerialScaleBackend(port, self._settings.baud, logger=self.logger)
            except BackendUnavailable as exc:
                self.logger.warning("Serial backend unavailable (%s); falling back", exc)
        try:
            return HX711GpioBackend(self._settings.hx711_dt, self._settings.hx711_sck, logger=self.logger)
        except BackendUnavailable as exc:
            self.logger.error("HX711 GPIO backend unavailable (%s)", exc)
            raise

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        try:
            self._backend.start()
        except Exception:
            self.logger.debug("Backend start failed", exc_info=True)
        self._thread = threading.Thread(target=self._run_loop, name="ScaleService", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        try:
            self._backend.stop()
        except Exception:
            pass

    close = stop

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        last_heartbeat = time.monotonic()
        while not self._stop_event.is_set():
            sample = None
            try:
                sample = self._backend.read()
            except BackendUnavailable as exc:
                self.logger.error("Backend %s failed: %s", self._backend.name, exc)
                self._set_signal_available(False)
                time.sleep(POLL_INTERVAL)
                continue
            except Exception as exc:
                self.logger.debug("Backend %s read error: %s", self._backend.name, exc, exc_info=True)
            if sample is not None:
                self._set_signal_available(True)
                self._process_sample(float(sample))
                last_heartbeat = time.monotonic()
            else:
                self._set_signal_available(False)
                if time.monotonic() - last_heartbeat >= HEARTBEAT_SECONDS:
                    self._notify_subscribers()
                    last_heartbeat = time.monotonic()
            time.sleep(POLL_INTERVAL)

    # ------------------------------------------------------------------
    def _process_sample(self, raw: float) -> None:
        with self._lock:
            self._last_raw = raw
            grams = (raw - self._offset) / self._effective_factor()
            grams = max(0.0, min(MAX_WEIGHT_G, grams))
            self._window.append(grams)
            avg = sum(self._window) / len(self._window)
            if len(self._window) >= max(2, self._window.maxlen or 1):
                delta = max(self._window) - min(self._window)
                threshold = 0.1 if self._decimals else 0.5
                self._stable = delta <= threshold
            else:
                self._stable = False
            rounded = round(avg, self._decimals)
            self._last_weight_g = max(0.0, min(MAX_WEIGHT_G, rounded))
        self._notify_subscribers()

    def _set_signal_available(self, available: bool) -> None:
        should_log = False
        with self._lock:
            if self._signal_available == available:
                if not available and not self._signal_warning_emitted:
                    self._signal_warning_emitted = True
                    should_log = True
            else:
                self._signal_available = available
                if available:
                    self._signal_warning_emitted = False
                elif not self._signal_warning_emitted:
                    self._signal_warning_emitted = True
                    should_log = True
        if should_log:
            self.logger.warning("Scale: no signal")

    def _notify_subscribers(self) -> None:
        with self._lock:
            signal = self._signal_available
            grams = self._last_weight_g
            stable = self._stable if signal else False
            unit = self._unit
            ml_factor = self._ml_factor
        if not signal:
            display_value: Optional[float] = None
        elif unit == "ml" and ml_factor > 0:
            display_value = grams / ml_factor
        else:
            display_value = grams
        for callback in list(self._callbacks):
            try:
                params = inspect.signature(callback).parameters
                if len(params) >= 3:
                    callback(display_value, stable, unit)
                else:
                    callback(display_value, stable)
            except Exception:  # pragma: no cover - protect callbacks
                self.logger.exception("Scale subscriber failed")

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[..., None]) -> None:
        if not callable(callback):
            return
        self._callbacks.append(callback)
        if self._callbacks:
            self._notify_subscribers()

    def unsubscribe(self, callback: Callable[..., None]) -> None:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    def tare(self) -> None:
        with self._lock:
            self._offset = self._last_raw
            self._window.clear()
        try:
            self._backend.tare()
        except Exception:
            pass

    def zero(self) -> None:
        with self._lock:
            self._offset = 0.0
            self._window.clear()
        try:
            self._backend.zero()
        except Exception:
            pass

    def get_last_weight_g(self) -> float:
        with self._lock:
            return float(self._last_weight_g)

    # ------------------------------------------------------------------
    def _effective_factor(self) -> float:
        return self._calibration_factor if abs(self._calibration_factor) > 1e-6 else 1.0

    @staticmethod
    def _sanitize_ml_factor(value: float) -> float:
        try:
            value = float(value)
        except Exception:
            value = 1.0
        if value <= 0:
            value = 1.0
        return value

    def set_calibration_factor(self, factor: float) -> float:
        try:
            value = float(factor)
        except (TypeError, ValueError):
            return self._calibration_factor
        if abs(value) < 1e-6:
            return self._calibration_factor
        with self._lock:
            self._calibration_factor = value
            self._window.clear()
        return self._calibration_factor

    def get_calibration_factor(self) -> float:
        return float(self._calibration_factor)

    def set_ml_factor(self, ml_factor: float) -> float:
        value = self._sanitize_ml_factor(ml_factor)
        with self._lock:
            self._ml_factor = value
        return self._ml_factor

    def get_ml_factor(self) -> float:
        with self._lock:
            return float(self._ml_factor)

    def set_decimals(self, decimals: int) -> int:
        value = 1 if int(decimals or 0) > 0 else 0
        with self._lock:
            if self._decimals != value:
                self._decimals = value
                self._window.clear()
        return self._decimals

    def toggle_units(self) -> str:
        with self._lock:
            self._unit = "ml" if self._unit == "g" else "g"
        self._notify_subscribers()
        return self._unit


HX711Service = ScaleService

__all__ = [
    "ScaleService",
    "HX711Service",
    "SerialScaleBackend",
    "HX711GpioBackend",
]
