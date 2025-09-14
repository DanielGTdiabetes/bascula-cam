# -*- coding: utf-8 -*-
"""
Lector serie robusto para Báscula-Cam
-------------------------------------
Acepta líneas tipo:  G:<float>,S:<0|1>
Tolera terminadores \r, \n o \r\n y también líneas concatenadas (pegadas).

Motivo del cambio:
- En la Pi llegan tramas con '\r' y a veces dos lecturas pegadas (p.ej. "G:-0.4,S:\rG:-0.44,S:1\r\n").
- El lector antiguo usaba readline() esperando '\n' y terminaba parseando cadenas incompletas
  (ValueError/invalid literal), bloqueando la UI.

Uso:
    scale = SerialScale("/dev/serial0", 115200)
    scale.start(on_read=lambda grams, stable: print(grams, stable))
    ...
    scale.stop()
"""

from __future__ import annotations
import re
import threading
import time
from typing import Callable, Optional

import serial

# Divide por CR o LF (uno o más)
_SPLIT_CRLF = re.compile(r"[\r\n]+")
# G:<float>,S:<0|1> con espacios tolerantes
_PARSE = re.compile(r"\s*G:\s*([+-]?\d+(?:\.\d+)?)\s*,\s*S:\s*([01])\s*$", re.ASCII)
# Cuando vienen dos mensajes pegados sin separador claro, se puede partir por el inicio de "G:"
_SPLIT_G = re.compile(r"(?=G:)")


class SerialScale:
    """
    Lector robusto de puerto serie para la báscula.
    - No depende de '\n' (read por bloques).
    - Tolera CR, LF, CRLF y “líneas pegadas”.
    - Filtra ruido y evita que el hilo muera por excepciones de parseo.
    """

    def __init__(self, port: str, baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_read: Optional[Callable[[float, int], None]] = None
        self._buf = b""

    # API pública -------------------------------------------------------------

    def start(self, on_read: Callable[[float, int], None]) -> None:
        """Arranca el hilo lector y llama a on_read(grams: float, stable: int)."""
        self._on_read = on_read
        self._stop.clear()
        # timeout corto para no bloquear y poder trocear por CR/LF
        self._ser = serial.Serial(self._port, self._baudrate, timeout=0.3)
        self._thread = threading.Thread(target=self._reader_loop, daemon=True, name="SerialScaleReader")
        self._thread.start()

    def stop(self) -> None:
        """Detiene el hilo y cierra el puerto."""
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

    # Internals ---------------------------------------------------------------

    def _reader_loop(self) -> None:
        ser = self._ser
        if not ser:
            return

        last_emit = 0.0  # rate limit para ráfagas
        while not self._stop.is_set():
            try:
                chunk = ser.read(128)  # lee “a mordiscos”, no espera '\n'
                if not chunk:
                    time.sleep(0.02)
                    continue

                # acumula y decodifica tolerando bytes raros
                self._buf += chunk
                parts = _SPLIT_CRLF.split(self._buf.decode("ascii", errors="ignore"))
                # el último fragmento puede estar incompleto -> vuelve al buffer
                self._buf = parts[-1].encode("ascii", errors="ignore")
                lines = parts[:-1]

                for raw in lines:
                    line = raw.strip()
                    if not line:
                        continue

                    # Si vienen dos lecturas pegadas sin separador claro, intenta partir por "G:"
                    sublines = _SPLIT_G.split(line)
                    # _SPLIT_G mantiene el "G:" al inicio de cada pieza; puede dejar una pieza vacía al principio
                    for sub in sublines:
                        sub = sub.strip()
                        if not sub:
                            continue

                        m = _PARSE.match(sub)
                        if not m:
                            # Línea no válida: ignora sin matar el hilo
                            continue

                        g_str, s_str = m.groups()
                        try:
                            grams = float(g_str)
                            stable = int(s_str)
                        except Exception:
                            continue

                        # Evita saturar el UI si llegan muchas por segundo
                        now = time.time()
                        if now - last_emit >= 0.015:  # ~66 Hz máx.
                            last_emit = now
                            cb = self._on_read
                            if cb:
                                cb(grams, stable)

            except serial.SerialException:
                # puerto temporalmente no disponible o sin datos; espera suave
                time.sleep(0.05)
            except Exception:
                # protección adicional contra cualquier texto/ruido inesperado
                time.sleep(0.02)


# Pequeño autotest opcional: ejecuta `python serial_scale.py /dev/serial0 115200`
if __name__ == "__main__":
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/serial0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    def _cb(g, s):
        print(f"{g:.3f} g  stable={s}")

    s = SerialScale(port, baud)
    print(f"Abriendo {port} @ {baud}...")
    s.start(_cb)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
