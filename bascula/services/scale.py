"""Scale service supporting serial and HX711 GPIO backends."""
from __future__ import annotations

import inspect
import logging
import re
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
POLL_INTERVAL = 0.1


def _normalize_serial_port(port: str) -> str:
    port = (port or "").strip()
    if port == "serial0":
        return "/dev/serial0"
    if port and port.startswith("/dev/"):
        return port
    if port.startswith("tty"):
        return f"/dev/{port}"
    return port


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
        self._port = resolved
        self._baudrate = int(baud)
        self._pattern = re.compile(r"G\s*:\s*([+-]?\d+(?:\.\d+)?)\s*,\s*S\s*:\s*(\d+)")
        self._last_valid_ts = time.monotonic()
        self._last_no_data_log = 0.0
        self._signal_state = False
        self._last_signal_log = 0.0
        self.signal_hint: Optional[bool] = None

    @staticmethod
    def _resolve_port(port: str) -> str:
        return _normalize_serial_port(port)

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    def stop(self) -> None:  # pragma: no cover - depends on hardware
        try:
            self._serial.close()
        except Exception:
            pass

    def read(self) -> Optional[float]:
        try:
            raw_line = self._serial.readline().decode(errors="ignore")
        except SerialException as exc:  # pragma: no cover - hardware dependent
            raise BackendUnavailable(str(exc)) from exc
        except Exception as exc:
            self._logger.debug("Serial read error: %s", exc)
            return None
        line = raw_line.strip()
        if not line:
            self._handle_no_data()
            return None
        match = self._pattern.search(line)
        if not match:
            self._handle_no_data(line)
            return None
        grams_text, signal_text = match.groups()
        try:
            grams = float(grams_text)
        except ValueError:
            self._handle_no_data(line)
            return None
        try:
            self.signal_hint = bool(int(signal_text))
        except ValueError:
            self.signal_hint = None
        self._mark_signal_restored()
        return grams

    def _mark_signal_restored(self) -> None:
        now = time.monotonic()
        self._last_valid_ts = now
        if not self._signal_state:
            if now - self._last_signal_log >= 1.0:
                self._logger.info("Serial %s: señal recuperada", self._port)
                self._last_signal_log = now
            self._signal_state = True

    def _handle_no_data(self, payload: Optional[str] = None) -> None:
        now = time.monotonic()
        elapsed = now - self._last_valid_ts
        if self._signal_state and elapsed >= 1.0:
            if now - self._last_signal_log >= 1.0:
                self._logger.info("Serial %s: señal perdida", self._port)
                self._last_signal_log = now
            self._signal_state = False
        if elapsed >= 1.0 and now - self._last_no_data_log >= 1.0:
            if payload:
                self._logger.debug(
                    "Serial %s sin datos válidos (%.1fs): %s",
                    self._port,
                    elapsed,
                    payload,
                )
            else:
                self._logger.debug(
                    "Serial %s sin datos válidos (%.1fs)",
                    self._port,
                    elapsed,
                )
            self._last_no_data_log = now

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
        read_timeout: float = 0.2,
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
        self._read_timeout = max(0.05, float(read_timeout))
        self._lock = threading.Lock()
        self._chip_handle: Optional[int] = None
        self._setup_gpio()
        self._logger.info(
            "Scale backend: HX711_GPIO (lgpio) inicializado (chip=%s, dt=%s, sck=%s)",
            self._chip_id,
            self._dt_pin,
            self._sck_pin,
        )

    def _setup_gpio(self) -> None:
        try:
            handle = lgpio.gpiochip_open(self._chip_id)
        except Exception as exc:  # pragma: no cover - hardware dependent
            message = f"lgpio open failed: {exc}"
            self._logger.warning(message)
            raise BackendUnavailable(message) from None
        try:
            lgpio.gpio_claim_input(handle, self._dt_pin)
            lgpio.gpio_claim_output(handle, self._sck_pin, 0)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self._logger.debug("lgpio setup failed: %s", exc)
            try:
                lgpio.gpiochip_close(handle)
            except Exception as close_exc:  # pragma: no cover - best effort
                self._logger.debug("lgpio close during setup failed: %s", close_exc)
            raise BackendUnavailable(f"lgpio setup failed: {exc}") from None
        self._chip_handle = handle

    def _cleanup_gpio(self) -> None:
        if self._chip_handle is None:
            return
        handle = self._chip_handle
        try:
            try:
                lgpio.gpio_write(handle, self._sck_pin, 0)
            except Exception as exc:
                self._logger.debug("lgpio write low failed: %s", exc)
            try:
                lgpio.gpio_free(handle, self._sck_pin)
            except Exception as exc:
                self._logger.debug("lgpio free pin %s failed: %s", self._sck_pin, exc)
            try:
                lgpio.gpio_free(handle, self._dt_pin)
            except Exception as exc:
                self._logger.debug("lgpio free pin %s failed: %s", self._dt_pin, exc)
        finally:
            try:
                lgpio.gpiochip_close(handle)
            except Exception as exc:
                self._logger.debug("lgpio close failed: %s", exc)
            self._chip_handle = None

    def stop(self) -> None:  # pragma: no cover - best effort
        self._cleanup_gpio()

    def read(self) -> Optional[float]:
        with self._lock:
            value = self._read_raw()
        return float(value)

    def _read_raw(self) -> int:
        if self._chip_handle is None:
            raise BackendUnavailable("lgpio chip not initialised")
        handle = self._chip_handle
        deadline = time.monotonic() + self._read_timeout
        while True:
            try:
                level = lgpio.gpio_read(handle, self._dt_pin)
            except Exception as exc:  # pragma: no cover - hardware dependent
                raise BackendUnavailable(f"gpio read failed: {exc}") from None
            if level == 0:
                break
            if time.monotonic() > deadline:
                raise BackendUnavailable("no data")
            time.sleep(0.001)

        value = 0
        for _ in range(24):
            self._set_clock(handle, 1)
            bit = self._read_bit(handle)
            value = (value << 1) | bit
            self._set_clock(handle, 0)
        self._set_clock(handle, 1)
        self._set_clock(handle, 0)

        if value & 0x800000:
            value -= 0x1000000
        return value

    def _set_clock(self, handle: int, level: int) -> None:
        try:
            lgpio.gpio_write(handle, self._sck_pin, level)
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise BackendUnavailable(f"gpio write failed: {exc}") from None
        time.sleep(0.000002)

    def _read_bit(self, handle: int) -> int:
        try:
            level = lgpio.gpio_read(handle, self._dt_pin)
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise BackendUnavailable(f"gpio read failed: {exc}") from None
        return 1 if level else 0


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
        self._none_heartbeat_interval = 0.5
        self._last_none_heartbeat = 0.0

        self._backend = self._select_backend()
        self._backend_name = self._backend.name
        self.logger.info("Scale backend: %s", self._backend_name)

        self.start()

    # ------------------------------------------------------------------
    def _select_backend(self) -> BaseScaleBackend:
        port = (self._settings.port or "").strip()
        if port and port not in {"__dummy__", ""}:
            try:
                backend = SerialScaleBackend(port, self._settings.baud, logger=self.logger)
            except BackendUnavailable as exc:
                self.logger.warning(
                    "Scale backend: SERIAL %s @%d no disponible (%s)",
                    _normalize_serial_port(port),
                    self._settings.baud,
                    exc,
                )
                raise
            self.logger.info("Scale backend: SERIAL %s @%d", backend.port, backend.baudrate)
            return backend
        try:
            backend = HX711GpioBackend(self._settings.hx711_dt, self._settings.hx711_sck, logger=self.logger)
        except BackendUnavailable as exc:
            self.logger.error("HX711 GPIO backend unavailable (%s)", exc)
            raise
        return backend

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
        while not self._stop_event.is_set():
            sample = None
            try:
                sample = self._backend.read()
            except BackendUnavailable as exc:
                reason = str(exc).strip()
                if isinstance(self._backend, HX711GpioBackend):
                    reason = f"hx711 {reason or 'no data'}"
                elif not reason:
                    reason = "no signal"
                self.logger.debug("Backend %s unavailable: %s", self._backend.name, reason)
                self._set_signal_available(False, reason=reason)
                self._emit_none_heartbeat()
                time.sleep(POLL_INTERVAL)
                continue
            except Exception as exc:
                self.logger.debug("Backend %s read error: %s", self._backend.name, exc, exc_info=True)
            if sample is not None:
                self._set_signal_available(True)
                self._process_sample(float(sample))
            else:
                self._set_signal_available(False, reason="no data")
                self._emit_none_heartbeat()
            time.sleep(POLL_INTERVAL)

    # ------------------------------------------------------------------
    def _process_sample(self, raw: float) -> None:
        with self._lock:
            self._last_raw = raw
            grams = (raw - self._offset) / self._effective_factor()
            grams = max(0.0, min(MAX_WEIGHT_G, grams))
            self._window.append(grams)
            avg = sum(self._window) / len(self._window)
            hint = getattr(self._backend, "signal_hint", None)
            if isinstance(hint, bool):
                self._stable = hint
            elif len(self._window) >= max(2, self._window.maxlen or 1):
                delta = max(self._window) - min(self._window)
                threshold = 0.1 if self._decimals else 0.5
                self._stable = delta <= threshold
            else:
                self._stable = False
            rounded = round(avg, self._decimals)
            self._last_weight_g = max(0.0, min(MAX_WEIGHT_G, rounded))
        self._notify_subscribers()

    def _set_signal_available(self, available: bool, *, reason: Optional[str] = None) -> None:
        log_method: Optional[Callable[[str], None]] = None
        message: Optional[str] = None
        with self._lock:
            previous = self._signal_available
            if previous == available:
                return
            self._signal_available = available
            if available:
                self._last_none_heartbeat = time.monotonic()
                log_method = self.logger.info
                message = f"{self._backend_name}: señal recuperada"
            else:
                log_method = self.logger.info
                detail = (reason or "no signal").strip()
                message = f"{self._backend_name}: señal perdida ({detail})"
        if log_method and message:
            log_method(message)

    def _emit_none_heartbeat(self) -> None:
        now = time.monotonic()
        if now - self._last_none_heartbeat >= self._none_heartbeat_interval:
            self._last_none_heartbeat = now
            self._notify_subscribers()

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

    def set_unit(self, unit: str) -> str:
        value = str(unit or "g").lower()
        with self._lock:
            self._unit = "ml" if value == "ml" else "g"
        self._notify_subscribers()
        return self._unit

    def get_unit(self) -> str:
        with self._lock:
            return str(self._unit)

    def get_decimals(self) -> int:
        with self._lock:
            return int(self._decimals)


HX711Service = ScaleService

__all__ = [
    "ScaleService",
    "HX711Service",
    "SerialScaleBackend",
    "HX711GpioBackend",
]
