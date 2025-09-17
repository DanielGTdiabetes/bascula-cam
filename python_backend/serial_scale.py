# -*- coding: utf-8 -*-
"""
Lector serie robusto para Báscula-Cam (compatibilidad hacia atrás)
------------------------------------------------------------------
- Acepta líneas:  G:<float>,S:<0|1>
- Tolera terminadores \r, \n o \r\n y líneas concatenadas.
- Firma retrocompatible: __init__(port, baudrate=115200, baud=None, logger=None)
  (el wrapper actual llama con baud= y logger=).
"""

from __future__ import annotations
import re
import threading
import time
from typing import Callable, Optional

import serial

_SPLIT_CRLF = re.compile(r"[\r\n]+")
_SPLIT_G = re.compile(r"(?=G:)")  # partir cuando aparecen múltiples "G:"
_PARSE = re.compile(r"\s*G:\s*([+-]?\d+(?:\.\d+)?)\s*,\s*S:\s*([01])\s*$", re.ASCII)


class SerialScale:
    """
    Lector robusto de puerto serie:
    - No depende de '\n' (lee por bloques).
    - Tolera CR, LF, CRLF y líneas pegadas.
    - No muere ante texto/ruido inesperado.
    """

    def __init__(self, port: str, baudrate: int = 115200, *, baud: int | None = None, logger=None):
        # Mantener compatibilidad: si llega baud, tiene prioridad
        if baud is not None:
            baudrate = baud
        self._port = port
        self._baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_read: Optional[Callable[[float, int], None]] = None
        self._buf = b""
        # logger se acepta para compat, no se usa aquí.

    def start(self, on_read: Callable[[float, int], None]) -> None:
        self._on_read = on_read
        self._stop.clear()
        self._ser = serial.Serial(self._port, self._baudrate, timeout=0.3)
        self._thread = threading.Thread(target=self._reader_loop, daemon=True, name="SerialScaleReader")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._thread = None
        self._ser = None

    def _reader_loop(self) -> None:
        ser = self._ser
        if not ser:
            return
        last_emit = 0.0
        while not self._stop.is_set():
            try:
                chunk = ser.read(128)  # lee “a mordiscos”
                if not chunk:
                    time.sleep(0.02)
                    continue

                self._buf += chunk
                parts = _SPLIT_CRLF.split(self._buf.decode("ascii", errors="ignore"))
                self._buf = parts[-1].encode("ascii", errors="ignore")  # posible resto incompleto
                lines = parts[:-1]

                for raw in lines:
                    line = raw.strip()
                    if not line:
                        continue
                    for sub in _SPLIT_G.split(line):
                        sub = sub.strip()
                        if not sub:
                            continue
                        m = _PARSE.match(sub)
                        if not m:
                            continue
                        g_str, s_str = m.groups()
                        try:
                            grams = float(g_str)
                            stable = int(s_str)
                        except Exception:
                            continue
                        now = time.time()
                        if now - last_emit >= 0.015:  # ~66 Hz máx.
                            last_emit = now
                            cb = self._on_read
                            if cb:
                                cb(grams, stable)

            except serial.SerialException:
                time.sleep(0.05)
            except Exception:
                time.sleep(0.02)


if __name__ == "__main__":
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/serial0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    def _cb(g, s): print(f"{g:.3f} g  stable={s}")

    s = SerialScale(port, baud=baud)
    print(f"Abriendo {port} @ {baud}…")
    s.start(_cb)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
