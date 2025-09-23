#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serial scale driver with auto-detection and simulation fallback."""
from __future__ import annotations

import glob
import logging
import math
import os
import random
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Iterable, Optional, Tuple

try:
    import serial
    SerialException = serial.SerialException
except ImportError:  # pragma: no cover - depends on optional dependency
    serial = None  # type: ignore[assignment]
    SerialException = Exception

try:
    import yaml
except ImportError:  # pragma: no cover - depends on optional dependency
    yaml = None  # type: ignore[assignment]

LOGGER = logging.getLogger("bascula.scale")

DEFAULT_PORT_CANDIDATES = [
    "/dev/serial0",
    "/dev/ttyAMA0",
    "/dev/ttyS0",
]
DEFAULT_BAUD_CANDIDATES = [115200, 57600, 38400, 19200, 9600, 4800]

_WEIGHT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)(?:\s*(mg|g|kg|lb|oz))?", re.IGNORECASE)


class SerialScale:
    """Serial scale reader running in a background thread."""

    def __init__(
        self,
        device: str | None = None,
        baudrate: int | None = None,
        *,
        timeout: float = 0.2,
        simulate_if_unavailable: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or LOGGER
        self._timeout = max(0.05, float(timeout))
        self._simulate_if_unavailable = bool(simulate_if_unavailable)

        cfg = _load_scale_config()
        env_device = _clean_str(os.getenv("BASCULA_DEVICE"))
        env_baud = _parse_int(os.getenv("BASCULA_BAUD"))

        cfg_scale = cfg.get("scale", {}) if isinstance(cfg, dict) else {}
        cfg_device = _clean_str(cfg_scale.get("device") or cfg.get("device"))
        cfg_baud = _parse_int(cfg_scale.get("baud") or cfg.get("baud") or cfg_scale.get("baudrate"))

        self._device_candidates = list(_unique_preserve([
            env_device,
            cfg_device,
            device,
        ]) or [])
        if not self._device_candidates:
            self._device_candidates = []
        self._device_candidates.extend(_scan_default_ports())
        self._device_candidates = list(_unique_preserve(self._device_candidates))

        baud_candidates = list(_unique_preserve([
            env_baud,
            cfg_baud,
            baudrate,
        ]) or [])
        baud_candidates = [b for b in baud_candidates if b]
        if not baud_candidates:
            baud_candidates = []
        baud_candidates.extend(DEFAULT_BAUD_CANDIDATES)
        self._baud_candidates = [int(b) for b in _unique_preserve(baud_candidates)]

        self._cmd_tare = _clean_str(os.getenv("BASCULA_CMD_TARE") or cfg_scale.get("cmd_tare"))
        self._cmd_zero = _clean_str(os.getenv("BASCULA_CMD_ZERO") or cfg_scale.get("cmd_zero"))

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()

        self._last_gross: float = 0.0
        self._last_net: float = 0.0
        self._offset: float = 0.0
        self._last_raw_line: str = ""
        self._stable_window: Deque[float] = deque(maxlen=12)
        self._stable_flag: bool = False
        self._last_sample_ts: float = 0.0

        self._active_device: Optional[str] = None
        self._active_baud: Optional[int] = None
        self._simulate: bool = False

    # ------------------------------------------------------------------
    @property
    def device(self) -> Optional[str]:
        return self._active_device

    @property
    def baudrate(self) -> Optional[int]:
        return self._active_baud

    @property
    def is_simulated(self) -> bool:
        return self._simulate

    @property
    def last_raw_line(self) -> str:
        with self._lock:
            return self._last_raw_line

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        try:
            self._serial = self._open_serial()
            self._simulate = False
        except Exception as exc:
            if not self._simulate_if_unavailable:
                self._logger.error("Serial scale unavailable: %s", exc)
                raise
            self._logger.warning("Falling back to scale simulation: %s", exc)
            self._simulate = True
            self._serial = None
        self._thread = threading.Thread(target=self._run, name="SerialScale", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None

    # ------------------------------------------------------------------
    def read_weight(self) -> float:
        with self._lock:
            return float(self._last_net)

    def read_gross(self) -> float:
        with self._lock:
            return float(self._last_gross)

    @property
    def stable(self) -> bool:
        with self._lock:
            return bool(self._stable_flag)

    # ------------------------------------------------------------------
    def tare(self) -> None:
        if self._simulate or not self._cmd_tare:
            with self._lock:
                self._offset = self._last_gross
                self._stable_window.clear()
            return
        self._send_command(self._cmd_tare)

    def zero(self) -> None:
        if self._simulate or not self._cmd_zero:
            with self._lock:
                self._offset = self._last_gross
                self._stable_window.clear()
            return
        self._send_command(self._cmd_zero)

    def send_command(self, command: str) -> None:
        self._send_command(command)

    # ------------------------------------------------------------------
    def _open_serial(self) -> serial.Serial:
        if serial is None:
            raise RuntimeError("pyserial is required for serial scale access")

        errors: list[str] = []
        for dev in self._device_candidates:
            if not dev:
                continue
            for baud in self._baud_candidates:
                try:
                    self._logger.info("Trying scale at %s @ %s bps", dev, baud)
                    ser = serial.Serial(dev, baudrate=baud, timeout=self._timeout)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.flush()
                    self._logger.info("Connected to scale at %s @ %s bps", dev, baud)
                    self._active_device = dev
                    self._active_baud = baud
                    return ser
                except Exception as exc:  # pragma: no cover - hardware dependent
                    errors.append(f"{dev}@{baud}: {exc}")
        raise RuntimeError("; ".join(errors) or "No serial port candidates available")

    def _run(self) -> None:
        if self._simulate:
            self._run_simulation()
        else:
            self._run_serial()

    def _run_serial(self) -> None:
        buffer = ""
        ser = self._serial
        if not ser:
            return
        while not self._stop_event.is_set():
            try:
                chunk = ser.read_until(b"\n")
                if not chunk:
                    continue
                try:
                    text = chunk.decode("utf-8", errors="ignore")
                except Exception:
                    text = repr(chunk)
                buffer += text
                lines = re.split(r"[\r\n]+", buffer)
                buffer = lines.pop() if lines else ""
                for line in lines:
                    self._handle_line(line)
            except SerialException as exc:  # pragma: no cover - depends on hardware
                self._logger.error("Serial error: %s", exc)
                if self._simulate_if_unavailable:
                    self._logger.warning("Switching to simulation due to serial error")
                    self._simulate = True
                    self._run_simulation()
                    return
                time.sleep(0.5)
            except Exception as exc:  # pragma: no cover - safety
                self._logger.debug("Serial reader error: %s", exc)
                time.sleep(0.1)

    def _run_simulation(self) -> None:
        self._logger.info("Scale simulation active")
        start = time.monotonic()
        while not self._stop_event.is_set():
            t = time.monotonic() - start
            phase = t % 12.0
            if phase < 6.0:
                target = 180.0 + 8.0 * math.sin(phase)
            else:
                target = 320.0 + 8.0 * math.sin(phase)
            drift = 5.0 * math.sin(t / 18.0)
            noise = random.gauss(0.0, 0.05)
            gross = max(0.0, target + drift + noise)
            self._handle_measurement(gross, None)
            time.sleep(0.1)

    def _handle_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        grams, stable = parse_weight_line(line)
        if grams is None:
            return
        self._handle_measurement(grams, stable, raw_line=line)

    def _handle_measurement(
        self,
        gross: float,
        stable_hint: Optional[bool],
        *,
        raw_line: Optional[str] = None,
    ) -> None:
        net = gross
        with self._lock:
            if raw_line is not None:
                self._last_raw_line = raw_line
            self._last_gross = float(gross)
            net = self._last_gross - self._offset
            self._last_net = net
            self._stable_window.append(self._last_net)
            if stable_hint is not None:
                self._stable_flag = bool(stable_hint)
            else:
                self._stable_flag = _window_is_stable(self._stable_window)
            self._last_sample_ts = time.monotonic()

    def _send_command(self, command: Optional[str]) -> None:
        if not command:
            return
        payload = command if command.endswith("\n") else f"{command}\r\n"
        ser = self._serial
        if not ser:
            return
        try:
            ser.write(payload.encode("ascii", errors="ignore"))
            ser.flush()
        except Exception as exc:  # pragma: no cover - hardware
            self._logger.warning("Failed to send command '%s': %s", command, exc)


def _load_scale_config() -> dict:
    path = Path.home() / ".bascula" / "config.yaml"
    if yaml is None:
        return {}
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
                if isinstance(data, dict):
                    return data
    except Exception as exc:  # pragma: no cover - filesystem
        LOGGER.debug("Failed to load %s: %s", path, exc)
    return {}


def _scan_default_ports() -> Iterable[str]:
    ports = list(DEFAULT_PORT_CANDIDATES)
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        ports.extend(sorted(glob.glob(pattern)))
    return ports


def _unique_preserve(items: Iterable[Optional[str | int]]) -> Iterable[str | int]:
    seen = set()
    for item in items:
        if item in (None, "", False):
            continue
        if item in seen:
            continue
        seen.add(item)
        yield item


def _clean_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_int(value: Optional[object]) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_weight_line(text: str) -> Tuple[Optional[float], Optional[bool]]:
    """Parse a line of text and return (grams, stable_hint)."""
    if not text:
        return None, None
    raw = text.strip()
    if not raw:
        return None, None
    stable_hint: Optional[bool] = None
    prefix = raw.upper()
    if prefix.startswith("ST"):
        stable_hint = True
    elif prefix.startswith("US") or "UNST" in prefix:
        stable_hint = False
    match = _WEIGHT_RE.search(raw)
    if not match:
        return None, stable_hint
    value_str, unit = match.groups()
    try:
        value = float(value_str)
    except ValueError:
        return None, stable_hint
    unit = (unit or "g").lower()
    if unit == "mg":
        grams = value / 1000.0
    elif unit == "kg":
        grams = value * 1000.0
    elif unit == "lb":
        grams = value * 453.59237
    elif unit == "oz":
        grams = value * 28.349523125
    else:
        grams = value
    return grams, stable_hint


def _window_is_stable(window: Deque[float]) -> bool:
    if len(window) < max(6, window.maxlen or 0):
        return False
    values = list(window)
    if not values:
        return False
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    stddev = math.sqrt(variance)
    delta = abs(values[-1] - values[0])
    return stddev < 0.5 and delta < 1.0


__all__ = ["SerialScale", "parse_weight_line"]
