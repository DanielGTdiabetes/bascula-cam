import time, threading
from tkinter import messagebox
from bascula.domain.filters import ProfessionalWeightFilter

class ScaleService:
    def __init__(self, state, logger):
        self.state = state
        self.logger = logger
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self.running = False
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
            test = self.hx.get_raw_data(times=2) or []
            if not test or all(v is None for v in test):
                raise RuntimeError("HX711 no devuelve datos válidos")
            self.state.hx_ready = True
            self.logger.info("HX711 inicializado")
        except Exception as e:
            self.state.hx_ready = False
            self.logger.error(f"HX711 error: {e}")
            if self.state.cfg.hardware.strict_hardware:
                try:
                    messagebox.showerror("Error de hardware", f"No se detecta HX711.\nDetalle: {e}\nLa aplicación se cerrará.")
                except Exception:
                    pass
                raise

    def start(self):
        if not self.state.hx_ready:
            self.logger.error("No se puede iniciar lectura: HX711 no listo")
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _read_raw(self) -> float:
        vals = self.hx.get_raw_data(times=3) or []
        valid = [v for v in vals if v is not None]
        if not valid:
            raise RuntimeError("Lectura HX711 vacía")
        raw_avg = sum(valid)/len(valid)
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
