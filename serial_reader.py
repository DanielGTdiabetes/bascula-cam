# -*- coding: utf-8 -*-
"""
Lector serie robusto (no "consume" la lectura):
- Mantiene el último valor válido y su timestamp.
- get_latest() NO vacía el dato; devuelve el último si no está "stale".
- Reconexión automática si el puerto cae.
"""
from __future__ import annotations
import threading
import time
import re
from typing import Optional

try:
    import serial  # pyserial
except Exception:
    serial = None

_NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)")

class SerialReader:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, stale_ms: int = 800) -> None:
        self.port = port
        self.baud = baud
        self.stale_ms = stale_ms
        self._ser = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._last_value: Optional[float] = None
        self._last_ts: float = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="SerialReader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    def _open(self):
        if serial is None:
            raise RuntimeError("pyserial no está instalado")
        self._ser = serial.Serial(self.port, self.baud, timeout=1)

    def _run(self):
        while not self._stop.is_set():
            try:
                if self._ser is None or not self._ser.is_open:
                    self._open()
                line = self._ser.readline()
                if not line:
                    continue
                # Decodifica con errores ignorados
                try:
                    text = line.decode("utf-8", errors="ignore")
                except Exception:
                    text = str(line)
                m = _NUMBER_RE.search(text)
                if m:
                    val = float(m.group(1))
                    with self._lock:
                        self._last_value = val
                        self._last_ts = time.time()
            except Exception:
                # Espera breve y reintenta (reconexión)
                time.sleep(0.2)
                try:
                    if self._ser:
                        self._ser.close()
                except Exception:
                    pass
                self._ser = None

    def get_latest(self) -> Optional[float]:
        """Devuelve el último valor si no está pasado de tiempo; si no, None."""
        with self._lock:
            val = self._last_value
            ts = self._last_ts
        if val is None:
            return None
        if (time.time() - ts) * 1000.0 > self.stale_ms:
            # dato antiguo: no forzamos 0, devolvemos None para no "saltar"
            return None
        return val
