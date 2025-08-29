# python-backend/serial_scale.py
# Backend de báscula vía /dev/serial0 (UART) para la UI Tk existente.
# Protocolo: líneas "G:<gramos>,S:<0|1>"
# Comandos: "T" (tara), "C:<peso>\n" (calibración)
#
# Uso:
#   from serial_scale import SerialScale
#   ss = SerialScale(port="/dev/serial0", baud=115200)
#   ss.start()
#   # subscripción a lecturas
#   ss.subscribe(lambda g, s: print(g, s))
#   ...
#   ss.tare()
#   ss.calibrate(500.0)
#   ...
#   ss.stop()

import threading
import time
import serial
from typing import Callable, Optional, List

class SerialScale:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None
        self._thr: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._subs: List[Callable[[float, bool], None]] = []
        self._last_g = 0.0
        self._last_s = False

    def start(self):
        if self._thr and self._thr.is_alive():
            return
        self._stop.clear()
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        except Exception as e:
            raise RuntimeError(f"No se pudo abrir {self.port}@{self.baud}: {e}")
        self._thr = threading.Thread(target=self._reader_loop, daemon=True)
        self._thr.start()

    def stop(self):
        self._stop.set()
        if self._thr:
            self._thr.join(timeout=2)
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._thr = None
        self._ser = None

    def subscribe(self, cb: Callable[[float, bool], None]):
        # cb(grams: float, stable: bool)
        with self._lock:
            self._subs.append(cb)

    def _notify(self, g: float, s: bool):
        with self._lock:
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(g, s)
            except Exception:
                pass

    def _reader_loop(self):
        # lectura de líneas "G:<g>,S:<s>"
        ser = self._ser
        if ser is None:
            return
        while not self._stop.is_set():
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                # formato esperado
                # G:123.45,S:1
                g, s = self._parse_line(line)
                if g is not None and s is not None:
                    self._last_g = g
                    self._last_s = bool(s)
                    self._notify(self._last_g, self._last_s)
            except Exception:
                time.sleep(0.05)

    @staticmethod
    def _parse_line(line: str):
        # Devuelve (grams: float|None, stable: int|None)
        try:
            parts = line.split(',')
            g_part = next((p for p in parts if p.startswith("G:")), None)
            s_part = next((p for p in parts if p.startswith("S:")), None)
            if g_part is None or s_part is None:
                return (None, None)
            g = float(g_part.split(':', 1)[1])
            s = int(s_part.split(':', 1)[1])
            return (g, s)
        except Exception:
            return (None, None)

    # --- API pública compatible con tu ScaleService ---
    def get_weight(self) -> float:
        return self._last_g

    def is_stable(self) -> bool:
        return self._last_s

    def tare(self) -> bool:
        return self._send_line("T\n")

    def calibrate(self, weight_grams: float) -> bool:
        return self._send_line(f"C:{weight_grams}\n")

    def _send_line(self, s: str) -> bool:
        ser = self._ser
        if not ser:
            return False
        try:
            ser.write(s.encode())
            ser.flush()
            return True
        except Exception:
            return False
