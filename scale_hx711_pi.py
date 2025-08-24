#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scale_hx711_pi.py  (v1.4)
- Pines por defecto más “limpios”: DT=GPIO27, SCK=GPIO17
- Reloj lento + pull-up en DT
- Rechazo de picos (valores saturados tipo 2^N)
- Filtros: mediana + promedio + IIR
- Tara y calibración robustas con persistencia
Comandos: [t]=tara [c]=calibrar [i]=info [r]=reset [s]=signo [q]=salir
"""
import sys, os, time, json, select, statistics
import RPi.GPIO as GPIO

# ---------------- CONFIG ----------------
GPIO.setmode(GPIO.BCM)
PIN_DT  = 27   # DOUT del HX711  (pin físico 13)
PIN_SCK = 17   # SCK  del HX711  (pin físico 11)

# tiempos de reloj más lentos (us)
T_HIGH = 0.00001
T_LOW  = 0.00001
READ_TIMEOUT = 1.2

RAW_SAMPLES_PER_READ = 8
OVERSAMPLES          = 6
IIR_ALPHA            = 0.12
PRINT_PERIODS        = 0.25

HOLD_WINDOW_SAMPLES  = 20
HOLD_MAX_STD_LSB     = 400

STORE_PATH = os.path.join(os.path.dirname(__file__), "scale_store.json")

SAT_LIMIT = (1 << 23) - 1   # 8388607

# ------------- Driver mínimo HX711 -------------
class HX711:
    def __init__(self, pin_dt=PIN_DT, pin_sck=PIN_SCK):
        self.dt = pin_dt
        self.sck = pin_sck
        self._last_raw = 0

    def begin(self):
        GPIO.setup(self.dt,  GPIO.IN,  pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sck, GPIO.OUT, initial=GPIO.LOW)
        self.read_raw(READ_TIMEOUT)  # dummy

    def is_ready(self):
        return GPIO.input(self.dt) == 0

    def read_raw(self, timeout=READ_TIMEOUT):
        t0 = time.time()
        while not self.is_ready():
            if time.time() - t0 > timeout:
                return self._last_raw
            time.sleep(0.001)

        v = 0
        for _ in range(24):
            GPIO.output(self.sck, True);  time.sleep(T_HIGH)
            v = (v << 1) | GPIO.input(self.dt)
            GPIO.output(self.sck, False); time.sleep(T_LOW)

        # pulso 25 -> canal A, ganancia 128
        GPIO.output(self.sck, True);  time.sleep(T_HIGH)
        GPIO.output(self.sck, False); time.sleep(T_LOW)

        if v & 0x800000:
            v |= ~0xffffff

        # rechazar saturaciones/picos “binarios”
        if abs(v) >= SAT_LIMIT:
            return self._last_raw

        self._last_raw = int(v)
        return self._last_raw

    def power_down(self):
        GPIO.output(self.sck, False)
        time.sleep(0.000005)
        GPIO.output(self.sck, True)
        time.sleep(0.00007)

    def power_up(self):
        GPIO.output(self.sck, False)
        self.read_raw(READ_TIMEOUT)

# --------- utilidades de filtro ----------
def median_of(vals):
    vals = list(vals)
    vals.sort()
    n = len(vals)
    if n == 0: return 0
    m = n // 2
    return vals[m] if n % 2 else (vals[m-1] + vals[m]) // 2

def robust_mean(values, trim=0.15):
    if not values: return 0.0
    vals = sorted(values)
    k = int(len(vals) * trim)
    if k > 0: vals = vals[k:-k]
    if not vals: return 0.0
    return sum(vals) / len(vals)

# -------------- lógica de escala --------------
class Scale:
    def __init__(self, hx: HX711):
        self.hx = hx
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.iir_state_g = None
        self.hold_buf = []

    def load(self):
        if not os.path.exists(STORE_PATH): return
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.calibration_g_per_lsb = float(d.get("calibration_g_per_lsb", 1.0))
            self.tare_offset = int(d.get("tare_offset", 0))
            self.invert_sign = bool(d.get("invert_sign", False))
        except Exception:
            pass

    def save(self):
        d = {
            "calibration_g_per_lsb": self.calibration_g_per_lsb,
            "tare_offset": self.tare_offset,
            "invert_sign": self.invert_sign
        }
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    def read_sample_median(self):
        raws = [self.hx.read_raw() for _ in range(max(1, RAW_SAMPLES_PER_READ))]
        return median_of(raws)

    def read_oversampled(self):
        mids = [self.read_sample_median() for _ in range(max(1, OVERSAMPLES))]
        return sum(mids) // max(1, len(mids))

    def read_net_lsb(self):
        raw = self.read_oversampled()
        net = raw - self.tare_offset
        if self.invert_sign: net = -net
        return net

    def read_net_g(self):
        lsb = self.read_net_lsb()
        g = lsb * self.calibration_g_per_lsb
        if self.iir_state_g is None:
            self.iir_state_g = g
        else:
            self.iir_state_g = (1.0 - IIR_ALPHA) * self.iir_state_g + IIR_ALPHA * g

        self.hold_buf.append(lsb)
        if len(self.hold_buf) > HOLD_WINDOW_SAMPLES:
            self.hold_buf.pop(0)
        return self.iir_state_g

    def tare(self, seconds=1.5):
        print("\n→ Tara robusta: NO toques la plataforma…")
        time.sleep(0.3)
        samples = []
        t0 = time.time()
        while time.time() - t0 < seconds:
            samples.append(self.read_oversampled())
            time.sleep(0.01)
        self.tare_offset = int(round(robust_mean(samples, trim=0.15)))
        self.save()
        self.iir_state_g = None; self.hold_buf.clear()
        print(f"✔ Tara guardada (offset LSB = {self.tare_offset})")

    def calibrate(self):
        print("\n→ Calibración: coloca peso patrón y escribe su valor en gramos (ej. 1000)")
        while True:
            try:
                s = input("Peso patrón [g]: ").strip()
                val = float(s)
                if val > 0: break
            except Exception:
                pass
            print("Entrada no válida.")
        print("Midiendo… mantén QUIETA la plataforma (≈1.2 s).")
        nets = []
        for _ in range(60):
            nets.append(self.read_net_lsb())
            time.sleep(0.02)
        mean_lsb = robust_mean(nets, trim=0.15)
        if abs(mean_lsb) < 1e-6:
            print("Lectura nula; revisa tara/montaje.")
            return
        self.calibration_g_per_lsb = val / mean_lsb
        self.save()
        self.iir_state_g = None; self.hold_buf.clear()
        print(f"✔ Calibración OK: {self.calibration_g_per_lsb:.8f} g/LSB")

    def reset(self):
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.save()
        self.iir_state_g = None; self.hold_buf.clear()
        print("\n✔ Calibración/tara/signo reseteados.")

    def toggle_sign(self):
        self.invert_sign = not self.invert_sign
        self.save()
        self.iir_state_g = None; self.hold_buf.clear()
        print(f"\n✔ invert_sign = {self.invert_sign}")

    def info(self):
        try:
            std = statistics.pstdev(self.hold_buf) if len(self.hold_buf) >= 5 else 0
        except Exception:
            std = 0
        raw_now = self.read_oversampled()
        net_lsb = (raw_now - self.tare_offset) * (-1 if self.invert_sign else 1)
        print("\n--- INFO ---")
        print(f"  tare_offset (LSB):         {self.tare_offset}")
        print(f"  factor (g/LSB):            {self.calibration_g_per_lsb:.8f}")
        print(f"  invert_sign:               {self.invert_sign}")
        print(f"  RAW_SAMPLES/OVERSAMPLES:   {RAW_SAMPLES_PER_READ} / {OVERSAMPLES}")
        print(f"  IIR_ALPHA:                 {IIR_ALPHA}")
        print(f"  HOLD win/std (LSB):        {len(self.hold_buf)} / {int(std)} (umbral {HOLD_MAX_STD_LSB})")
        print(f"  raw_now (LSB):             {raw_now}")
        print(f"  net_lsb (LSB):             {net_lsb}")
        print("--------------")

# -------------------- MAIN --------------------
def main():
    print("=== HX711 Scale v1.4 (DT=GPIO27, SCK=GPIO17) ===")
    print("Comandos: [t]=tara  [c]=calibrar  [i]=info  [r]=reset  [s]=signo  [q]=salir")
    print(f"Almacenamiento: {STORE_PATH}")

    hx = HX711(PIN_DT, PIN_SCK)
    hx.begin()

    scale = Scale(hx)
    scale.load()

    last = 0.0
    try:
        while True:
            g = scale.read_net_g()
            now = time.time()
            if now - last >= PRINT_PERIODS:
                sys.stdout.write(f"\rPeso: {g:8.1f} g   (t/c/i/r/s/q) ")
                sys.stdout.flush()
                last = now

            r, _, _ = select.select([sys.stdin], [], [], 0.01)
            if r:
                key = sys.stdin.readline().strip().lower()[:1]
                if   key == 't': scale.tare()
                elif key == 'c': scale.calibrate()
                elif key == 'i': scale.info()
                elif key == 'r': scale.reset()
                elif key == 's': scale.toggle_sign()
                elif key == 'q':
                    print("\nSaliendo…"); break
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        try: hx.power_down()
        except Exception: pass
        GPIO.cleanup()
        print("\nGPIO limpio. Bye!")

if __name__ == "__main__":
    main()
