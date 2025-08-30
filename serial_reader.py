# -*- coding: utf-8 -*-
import threading, queue, time, re
import serial

_FLOAT_RE = re.compile(r'[-+]?\d+(?:[.,]\d+)?')

class SerialReader:
    """
    Lector serie robusto con:
    - exclusive=True (evita doble acceso)
    - reconexión automática si el puerto cae
    - parseo tolerante: busca el primer número en cada línea (coma o punto)
    """
    def __init__(self, port="/dev/serial0", baud=115200, timeout=0.2):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.q = queue.Queue(maxsize=10)
        self._stop = threading.Event()
        self._thr = None
        self._ser = None

    def start(self):
        self._stop.clear()
        if self._thr and self._thr.is_alive():
            return
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()

    def _open(self):
        return serial.Serial(
            self.port, self.baud,
            timeout=self.timeout,
            inter_byte_timeout=0.1,
            exclusive=True,
            rtscts=False, dsrdtr=False, xonxoff=False
        )

    def _run(self):
        buf = b""
        last_err_log = 0
        while not self._stop.is_set():
            # Asegura puerto abierto
            if self._ser is None or not self._ser.is_open:
                try:
                    self._ser = self._open()
                except Exception as e:
                    now = time.time()
                    if now - last_err_log > 1.0:
                        print(f"[SERIE] open fail: {e}", flush=True)
                        last_err_log = now
                    time.sleep(0.8)
                    continue

            # Lectura
            try:
                chunk = self._ser.read(64)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    s = line.strip().decode(errors="ignore")
                    if not s:
                        continue
                    # Busca número dentro de la línea
                    m = _FLOAT_RE.search(s)
                    if not m:
                        continue
                    token = m.group(0).replace(",", ".")
                    try:
                        value = float(token)
                        # mantén solo el último
                        with self.q.mutex:
                            self.q.queue.clear()
                        self.q.put_nowait(value)
                    except ValueError:
                        pass
            except Exception as e:
                now = time.time()
                if now - last_err_log > 1.0:
                    print(f"[SERIE] read fail: {e}", flush=True)
                    last_err_log = now
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                time.sleep(0.5)

    def get_latest(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self._stop.set()
        if self._thr is not None:
            self._thr.join(timeout=1.0)
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
