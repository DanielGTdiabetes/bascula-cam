#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serial_scale.py — Backend serie para báscula ESP32 + HX711

Protocolo soportado (ambos a la vez):

1) Línea combinada (nuevo firmware):
   G:<gramos>,S:<0|1>
   Ejemplo: G:123.45,S:1

2) Líneas separadas (compatibilidad hacia atrás):
   G:<gramos>
   S:<0|1>
   (en cualquier orden; el backend las agrupa)

Comandos salientes (terminados en '\n'):
   - T            -> Tara
   - C:<peso_g>   -> Calibrar con peso patrón en gramos

Mensajes informativos (se ignoran para el peso pero se loguean):
   - HELLO:ESP32-HX711
   - ACK:T
   - ACK:C:<factor>
   - ERR:...

Dependencias:
   pip install pyserial
"""

import threading
import time
import serial
import logging
from typing import Callable, Optional

# Configura logging sencillo (puedes ajustarlo en tu app principal si quieres)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class SerialScale:
    """
    Lee de /dev/serial0 (u otro puerto) líneas del ESP32, parsea
    y expone peso y estado. Notifica a subscriptores en cada actualización.
    """

    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout

        self._ser: Optional[serial.Serial] = None
        self._th: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Estado medido
        self._weight_g: float = 0.0
        self._stable: bool = False

        # Para compatibilidad con líneas separadas
        self._pending_g: Optional[float] = None
        self._pending_s: Optional[int] = None

        # Suscriptores: callbacks que reciben (weight_g: float, stable: bool)
        self._subs: list[Callable[[float, bool], None]] = []

    # -------- API pública --------

    def start(self):
        if self._th and self._th.is_alive():
            return
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
        except Exception as e:
            logging.error("No se pudo abrir %s @ %d: %s", self.port, self.baud, e)
            raise
        self._stop.clear()
        self._th = threading.Thread(target=self._reader_loop, name="SerialScaleReader", daemon=True)
        self._th.start()
        logging.info("SerialScale: leyendo %s @ %d", self.port, self.baud)

    def stop(self):
        self._stop.set()
        if self._th:
            self._th.join(timeout=1.0)
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._th = None

    def subscribe(self, cb: Callable[[float, bool], None]):
        """Registra un callback que recibirá (peso_g, estable)"""
        self._subs.append(cb)

    def tare(self) -> bool:
        return self._send_line("T")

    def calibrate(self, grams: float) -> bool:
        try:
            g = float(grams)
        except Exception:
            return False
        if g <= 0:
            return False
        return self._send_line(f"C:{g:.6f}")

    def get_weight(self) -> float:
        return float(self._weight_g)

    def is_stable(self) -> bool:
        return bool(self._stable)

    # -------- Internals --------

    def _send_line(self, txt: str) -> bool:
        try:
            if not self._ser:
                logging.error("Serial no inicializado")
                return False
            self._ser.write((txt + "\n").encode("ascii"))
            return True
        except Exception as e:
            logging.error("Error enviando '%s': %s", txt, e)
            return False

    def _notify(self):
        for cb in list(self._subs):
            try:
                cb(self._weight_g, self._stable)
            except Exception as e:
                # No paramos la lectura por un callback que falle
                logging.warning("Callback lanzó excepción: %s", e)

    def _set_measure(self, g: Optional[float] = None, s: Optional[int] = None):
        """
        Actualiza el estado con los valores recibidos.
        Si vienen por separado, guarda en pending hasta tener ambos.
        """
        updated = False

        # Caso 1: línea combinada -> ambos presentes
        if g is not None and s is not None:
            self._weight_g = float(g)
            self._stable = bool(int(s))
            self._pending_g = None
            self._pending_s = None
            updated = True

        # Caso 2: líneas separadas
        else:
            if g is not None:
                self._pending_g = float(g)
            if s is not None:
                self._pending_s = int(s)

            # Si ya tenemos ambos pendientes, consolidar
            if self._pending_g is not None and self._pending_s is not None:
                self._weight_g = float(self._pending_g)
                self._stable = bool(self._pending_s)
                self._pending_g = None
                self._pending_s = None
                updated = True

        if updated:
            self._notify()

    def _parse_line(self, line: str):
        """
        Acepta:
          - "G:<num>,S:<0|1>"
          - "G:<num>"
          - "S:<0|1>"
          - "ACK:...", "HELLO:...", "ERR:..."
        """
        t = line.strip()
        if not t:
            return

        # Mensajes informativos
        if t.startswith(("HELLO:", "ACK:", "ERR:")):
            logging.info("Serie: %s", t)
            return

        # ¿Formato combinado?
        if "," in t and "G:" in t and "S:" in t:
            try:
                parts = t.split(",")
                g_part = next(p for p in parts if p.startswith("G:"))
                s_part = next(p for p in parts if p.startswith("S:"))
                g = float(g_part.split(":", 1)[1])
                s = int(s_part.split(":", 1)[1])
                self._set_measure(g=g, s=s)
            except Exception:
                logging.debug("Línea no válida (combinada): %r", t)
            return

        # ¿Formato G:... solamente?
        if t.startswith("G:"):
            try:
                g = float(t.split(":", 1)[1])
                self._set_measure(g=g, s=None)
            except Exception:
                logging.debug("Línea G no válida: %r", t)
            return

        # ¿Formato S:... solamente?
        if t.startswith("S:"):
            try:
                s = int(t.split(":", 1)[1])
                self._set_measure(g=None, s=s)
            except Exception:
                logging.debug("Línea S no válida: %r", t)
            return

        # Cualquier otra cosa, ignorar con debug
        logging.debug("Descartado: %r", t)

    def _reader_loop(self):
        assert self._ser is not None
        ser = self._ser
        while not self._stop.is_set():
            try:
                line = ser.readline().decode(errors="ignore")
                if line:
                    self._parse_line(line)
            except Exception as e:
                logging.error("Error lectura serie: %s", e)
                time.sleep(0.05)  # breve respiro y seguimos
