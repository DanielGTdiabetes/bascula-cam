import time, threading, math, random
from bascula.domain.filters import ProfessionalWeightFilter

class ScaleService:
    def __init__(self, state, logger):
        self.state = state
        self.logger = logger
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self.running = False
        self.simulation = True
        self.hx = None
        self._init_hx711()

    def _init_hx711(self):
        try:
            import RPi.GPIO as GPIO
            from hx711 import HX711
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.hx = HX711(
                dout_pin=self.state.cfg.hardware.hx711_dout_pin,
                pd_sck_pin=self.state.cfg.hardware.hx711_sck_pin,
                gain=self.state.cfg.hardware.hx711_gain,
                channel="A"
            )
            self.hx.reset(); time.sleep(0.4)
            self.simulation = False
            self.state.hx_ready = True
            self.logger.info("HX711 inicializado")
        except Exception as e:
            self.logger.warning(f"HX711 no disponible (simulación): {e}")
            self.simulation = True
            self.state.hx_ready = False

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _read_raw(self) -> float:
        if self.simulation or not self.hx:
            t = time.time()
            base = 0.0 + 300 * math.sin(t*0.3)
            noise = random.gauss(0, 2.0)
            return base + noise
        vals = self.hx.get_raw_data(times=3) or []
        valid = [v for v in vals if v is not None]
        if not valid:
            return 0.0
        raw_avg = sum(valid)/len(valid)
        # calibración
        return (raw_avg - self.state.cfg.calibration.base_offset) / self.state.cfg.calibration.scale_factor

    def _loop(self):
        while self.running:
            try:
                raw = self._read_raw()
                out = self.filter.step(raw)
                self.state.current_weight = out.display
            except Exception as e:
                self.logger.error(f"Lectura error: {e}")
                time.sleep(0.2)
            time.sleep(0.1)

    def tara(self) -> bool:
        ok = self.filter.tara()
        if ok:
            self.state.current_weight = 0.0
        return ok

    def toggle_zero_tracking(self):
        self.filter.set_zero_tracking(not self.filter.zero_tracking)
        return self.filter.zero_tracking
