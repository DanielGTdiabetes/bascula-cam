import threading, queue, time
import serial

class SerialReader:
    def __init__(self, port="/dev/serial0", baud=115200, timeout=0.2):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.q = queue.Queue(maxsize=10)
        self._stop = threading.Event()
        self._thr = None
        self._ser = None

    def start(self):
        self._ser = serial.Serial(
            self.port, self.baud,
            timeout=self.timeout,
            inter_byte_timeout=0.1,
            exclusive=True,       # evita “multiple access”
            rtscts=False, dsrdtr=False, xonxoff=False
        )
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()

    def _run(self):
        buf = b""
        last_err_ts = 0
        while not self._stop.is_set():
            try:
                chunk = self._ser.read(64)
                if not chunk:
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip().decode(errors="ignore")
                    if not line:
                        continue
                    token = line.split("=", 1)[-1] if "=" in line else line
                    try:
                        value = float(token)
                        # guarda solo el último
                        with self.q.mutex:
                            self.q.queue.clear()
                        self.q.put_nowait(value)
                    except ValueError:
                        pass
            except Exception as e:
                now = time.time()
                if now - last_err_ts > 1.0:
                    print(f"[SERIE] Error lectura: {e}", flush=True)
                    last_err_ts = now
                time.sleep(0.1)

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
