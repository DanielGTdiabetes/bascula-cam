# python_backend/serial_scale.py
# Backend de báscula vía /dev/serial0 (UART) para la UI Tk existente.
# Protocolo: líneas "G:<gramos>,S:<0|1>"
# Comandos: "T" (tara), "C:<peso>\n" (calibración)
#
# Mejoras:
# - Backoff exponencial ante errores consecutivos en el hilo lector (hasta 0.5s)
# - Logging opcional (si se pasa logger) de excepciones de callbacks y E/S serial
#
# Uso:
#   from python_backend.serial_scale import SerialScale
#   ss = SerialScale(port="/dev/serial0", baud=115200, logger=logger)
#   ss.start()
#   ss.subscribe(lambda g, s: print(g, s))
#   ss.tare(); ss.calibrate(500)
#   ss.stop()

import threading
import time
import serial
from typing import Callable, Optional, List

class SerialScale:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200,
                 timeout: float = 1.0, logger=None):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.logger = logger

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
        if self.logger: self.logger.info(f"SerialScale started on {self.port}@{self.baud}")

    def stop(self):
        self._stop.set()
        if self._thr:
            self._thr.join(timeout=2)
        if self._ser:
            try:
                self._ser.close()
            except Exception as e:
                if self.logger: self.logger.warning(f"Serial close error: {e}")
        self._thr = None
        self._ser = None
        if self.logger: self.logger.info("SerialScale stopped")

    def subscribe(self, cb: Callable[[float, bool], None]):
        with self._lock:
            self._subs.append(cb)

    def _notify(self, g: float, s: bool):
        with self._lock:
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(g, s)
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Subscriber callback error: {e}")

    def _reader_loop(self):
        ser = self._ser
        if ser is None:
            return
        backoff = 0.05  # 50 ms inicial
        while not self._stop.is_set():
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    # No data → resetear backoff (no es error)
                    backoff = 0.05
                    continue
                g, s = self._parse_line(line)
                if g is not None and s is not None:
                    self._last_g = g
                    self._last_s = bool(s)
                    self._notify(self._last_g, self._last_s)
                else:
                    # línea malformada: lo anotamos si hay logger, pero sin penalizar demasiado
                    if self.logger:
                        self.logger.debug(f"Línea malformada: {line!r}")
                # Éxito → resetear backoff
                backoff = 0.05
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Serial read error: {e}")
                # backoff exponencial con tope 0.5s
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 0.5)

    @staticmethod
    def _parse_line(line: str):
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

    # --- API pública ---
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
            if self.logger: self.logger.error("Serial no inicializado en _send_line")
            return False
        try:
            ser.write(s.encode())
            ser.flush()
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Serial write error: {e}")
            return False
