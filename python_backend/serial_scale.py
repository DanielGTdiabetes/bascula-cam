"""
python_backend/serial_scale.py
Implementación del backend serie para la báscula basada en ESP32.
Lee líneas con el formato: 'G:<peso_en_gramos>,S:<0|1>' por el puerto serie.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional, List
try:
    import serial  # pyserial
except Exception as e:
    serial = None

class SerialScale:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, timeout: float = 1.0, logger=None, **kwargs):
        # Aceptar alias 'baudrate' por compatibilidad
        if "baudrate" in kwargs and not baud:
            baud = int(kwargs.pop("baudrate"))
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.logger = logger

        self._ser = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._latest_weight: float = 0.0
        self._stable: bool = False
        self._subs: List[Callable[[float, bool], None]] = []

        if serial is None:
            raise ImportError("pyserial no está instalado. Instala con 'pip install pyserial'.")

    # --- ciclo de vida ---
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            if self.logger:
                self.logger.info(f"Serial abierto en {self.port} @ {self.baud}")
        except Exception as e:
            if self.logger:
                self.logger.exception(f"No se pudo abrir {self.port} @ {self.baud}: {e!r}")
            raise

        self._thread = threading.Thread(target=self._reader_loop, name="SerialScaleReader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._thread:
                self._thread.join(timeout=1.0)
        finally:
            self._thread = None
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        finally:
            self._ser = None

    # --- suscripciones ---
    def subscribe(self, cb: Callable[[float, bool], None]) -> None:
        if cb not in self._subs:
            self._subs.append(cb)

    # --- I/O ---
    def _reader_loop(self) -> None:
        buf = b""
        while not self._stop.is_set():
            try:
                line = self._ser.readline()
                if not line:
                    continue
                try:
                    txt = line.decode(errors="ignore").strip()
                    if not txt:
                        continue
                    # Formato esperado: G:<float>,S:<0|1>
                    # Ej: 'G:123.45,S:1'
                    g = None
                    s = None
                    parts = [p.strip() for p in txt.split(",")]
                    for p in parts:
                        if p.startswith("G:"):
                            g = float(p[2:].strip())
                        elif p.startswith("S:"):
                            s = int(p[2:].strip())
                    if g is None:
                        continue
                    self._latest_weight = float(g)
                    self._stable = bool(s) if s is not None else False

                    # Notificar subs
                    for cb in self._subs:
                        try:
                            cb(self._latest_weight, self._stable)
                        except Exception:
                            pass
                except Exception as pe:
                    if self.logger:
                        self.logger.warning(f"Línea no válida: {line!r} ({pe!r})")
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error en lectura serie: {e!r}")
                time.sleep(0.1)

    # --- API pública ---
    def get_weight(self) -> float:
        return float(self._latest_weight)

    def get_latest(self) -> float:
        """Alias por compatibilidad con UI antiguas."""
        return self.get_weight()

    def is_stable(self) -> bool:
        return bool(self._stable)

    def tare(self) -> bool:
        return self._send_command("T")

    def calibrate(self, weight_grams: float) -> bool:
        return self._send_command(f"C:{float(weight_grams)}")

    # --- comandos ---
    def _send_command(self, payload: str) -> bool:
        try:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Puerto serie no abierto")
            data = (payload.strip() + "\n").encode()
            self._ser.write(data)
            return True
        except Exception as e:
            if self.logger:
                self.logger.exception(f"Error enviando comando '{payload}': {e!r}")
            return False
