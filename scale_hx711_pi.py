#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scale_hx711_pi.py  (v1.2)
Báscula con HX711 en Raspberry Pi Zero 2 W (sin librerías externas HX711).

Novedades v1.2:
- Filtro robusto: mediana de N + promedio.
- Tara robusta: descarta outliers y promedia estable.
- Detector de estabilidad (HOLD): solo fija lectura si la ventana es “tranquila”.
- Parámetros por defecto más conservadores para reducir saltos.

Comandos: [t]=tara  [c]=calibrar  [i]=info  [r]=reset  [s]=signo  [q]=salir

Cableado (BCM):
  HX711 DT  -> BCM5
  HX711 SCK -> BCM6
  HX711 VCC -> 3V3
  HX711 GND -> GND
"""

import sys, os, time, json, select, statistics
import RPi.GPIO as GPIO

# ----------------- CONFIGURACIÓN -----------------
GPIO.setmode(GPIO.BCM)
PIN_DT  = 5   # DOUT del HX711
PIN_SCK = 6   # SCK  del HX711

# Filtros y tiempos
RAW_SAMPLES_PER_READ = 8      # lecturas crudas por "muestra" (se aplica MEDIANA)
OVERSAMPLES          = 6      # cuántas "muestras" medianizadas promediamos
IIR_ALPHA            = 0.12   # 0..1 (más alto = más rápido, menos suave)
PRINT_PERIODS        = 0.25   # s entre impresiones

# Estabilidad (HOLD)
HOLD_WINDOW_SAMPLES  = 20     # tamaño ventana para comprobar estabilidad
HOLD_MAX_STD_LSB     = 300    # umbral de desviación típica (LSB) para considerar estable

# Persistencia
STORE_PATH = os.path.join(os.path.dirname(__file__), "scale_store.json")

# ----------------- DRIVER HX711 (mínimo) -----------------
class HX711:
    def __init__(self, pin_dt=PIN_DT, pin_sck=PIN_SCK):
        self.pin_dt  = pin_dt
        self.pin_sck = pin_sck
        self._last_raw = 0

    def begin(self):
        GPIO.setup(self.pin_sck, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.pin_dt,  GPIO.IN)
        self.read_raw(timeout_ms=200)  # dummy para fijar ganancia

    def is_ready(self):
        return GPIO.input(self.pin_dt) == 0

    def read_raw(self, timeout_ms=120):
        t0 = time.time()
        while not self.is_ready():
            if (time.time() - t0) * 1000.0 > timeout_ms:
                return self._last_raw
            time.sleep(0.0005)

        value = 0
        for _ in range(24):
            GPIO.output(self.pin_sck, True)
            time.sleep(0.000002)
            value = (value << 1) | GPIO.input(self.pin_dt)
            GPIO.output(self.pin_sck, False)
            time.sleep(0.000002)

        # 1 pulso extra -> canal A, ganancia 128
        GPIO.output(self.pin_sck, True)
        time.sleep(0.000002)
        GPIO.output(self.pin_sck, False)
        time.sleep(0.000002)

        if value & 0x800000:  # sign-extend 24->32
            value |= (~0xffffff)

        self._last_raw = int(value)
        return self._last_raw

    def power_down(self):
        GPIO.output(self.pin_sck, False)
        time.sleep(0.000005)
        GPIO.output(self.pin_sck, True)
        time.sleep(0.00007)  # >60us

    def power_up(self):
        GPIO.output(self.pin_sck, False)
        self.read_raw(timeout_ms=200)

# ----------------- UTILIDADES DE FILTRO -----------------
def median_of(iterable):
    data = list(iterable)
    data.sort()
    n = len(data)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2:
        return data[mid]
    return (data[mid - 1] + data[mid]) // 2

def robust_mean(values, trim=0.1):
    """Media recortada: descarta trim% más bajo y más alto."""
    if not values:
        return 0
    vals = sorted(values)
    k = int(len(vals) * trim)
    if k > 0:
        vals = vals[k:-k]
    return sum(vals) / max(1, len(vals))

# ----------------- LÓGICA DE ESCALA -----------------
class Scale:
    def __init__(self, hx: HX711):
        self.hx = hx
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.iir_state_g = None
        self.hold_buffer = []

    # Persistencia
    def load_store(self, path=STORE_PATH):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.calibration_g_per_lsb = float(data.get("calibration_g_per_lsb", 1.0))
            self.tare_offset = int(data.get("tare_offset", 0))
            self.invert_sign = bool(data.get("invert_sign", False))
            return True
        except Exception as e:
            print(f"[WARN] No se pudo leer {path}: {e}")
            return False

    def save_store(self, path=STORE_PATH):
        try:
            tmp = {
                "calibration_g_per_lsb": self.calibration_g_per_lsb,
                "tare_offset": self.tare_offset,
                "invert_sign": self.invert_sign
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(tmp, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] No se pudo guardar {path}: {e}")
            return False

    # Lecturas robustas
    def read_sample_median(self):
        # mediana de RAW_SAMPLES_PER_READ lecturas crudas
        raws = [self.hx.read_raw() for _ in range(max(1, RAW_SAMPLES_PER_READ))]
        return median_of(raws)

    def read_oversampled(self):
        # promedio de 'OVERSAMPLES' muestras medianizadas
        mids = [self.read_sample_median() for _ in range(max(1, OVERSAMPLES))]
        return sum(mids) // max(1, len(mids))

    def read_net_lsb(self):
        raw = self.read_oversampled()
        net = raw - self.tare_offset
        if self.invert_sign:
            net = -net
        return net

    def read_net_g(self):
        lsb = self.read_net_lsb()
        g = lsb * self.calibration_g_per_lsb
        # IIR
        if self.iir_state_g is None:
            self.iir_state_g = g
        else:
            self.iir_state_g = (1.0 - IIR_ALPHA) * self.iir_state_g + IIR_ALPHA * g

        # HOLD: mantener salida si la ventana es inestable
        self.hold_buffer.append(lsb)
        if len(self.hold_buffer) > HOLD_WINDOW_SAMPLES:
            self.hold_buffer.pop(0)

        try:
            std = statistics.pstdev(self.hold_buffer) if len(self.hold_buffer) >= 5 else 0
        except Exception:
            std = 0

        if std > HOLD_MAX_STD_LSB:
            # ventana ruidosa: “congela” salida suavizada
            return self.iir_state_g
        else:
            # ventana tranquila: salida suavizada normal
            return self.iir_state_g

    # Operaciones
    def tare(self, seconds=1.5):
        print("\n→ Tara robusta: NO toques la plataforma...")
        time.sleep(0.3)
        samples = []
        t0 = time.time()
        while (time.time() - t0) < seconds:
            samples.append(self.hx.read_raw())
            time.sleep(0.01)
        # media recortada para quitar outliers
        m = robust_mean(samples, trim=0.15)
        self.tare_offset = int(round(m))
        self.save_store()
        # Reset estados de filtro/hold
        self.iir_state_g = None
        self.hold_buffer.clear()
        print(f"✔ Tara guardada (offset LSB = {self.tare_offset})")

    def calibrate(self):
        print("\n→ Calibración: coloca peso patrón y escribe su valor en gramos (p. ej. 1000)")
        while True:
            try:
                s = input("Peso patrón [g]: ").strip()
                target = float(s)
                if target > 0:
                    break
                print("Debe ser > 0.")
            except Exception:
                print("Entrada inválida. Intenta de nuevo.")
        print("Midiendo… mantén QUIETA la plataforma (≈1.2 s).")
        time.sleep(0.2)
        nets = []
        for _ in range(60):
            nets.append(self.read_net_lsb())
            time.sleep(0.02)
        # usa media recortada contra outliers
        mean_lsb = robust_mean(nets, trim=0.15)
        if abs(mean_lsb) < 1e-6:
            print("Lectura nula; revisa tara o montaje.")
            return
        self.calibration_g_per_lsb = target / mean_lsb
        self.save_store()
        # Reset filtros
        self.iir_state_g = None
        self.hold_buffer.clear()
        print(f"✔ Calibración OK: {self.calibration_g_per_lsb:.8f} g/LSB")

    def reset(self):
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.save_store()
        self.iir_state_g = None
        self.hold_buffer.clear()
        print("\n✔ Calibración/tara/signo reseteados.")

    def toggle_sign(self):
        self.invert_sign = not self.invert_sign
        self.save_store()
        self.iir_state_g = None
        self.hold_buffer.clear()
        print(f"\n✔ invert_sign = {self.invert_sign}")

    def info(self):
        # estimar std actual
        try:
            std = statistics.pstdev(self.hold_buffer) if len(self.hold_buffer) >= 5 else 0
        except Exception:
            std = 0
        print("\n--- INFO ---")
        print(f"  tare_offset (LSB):         {self.tare_offset}")
        print(f"  factor (g/LSB):            {self.calibration_g_per_lsb:.8f}")
        print(f"  invert_sign:               {self.invert_sign}")
        print(f"  store:                     {STORE_PATH}")
        print(f"  RAW_SAMPLES/OVERSAMPLES:   {RAW_SAMPLES_PER_READ} / {OVERSAMPLES}")
        print(f"  IIR_ALPHA:                 {IIR_ALPHA}")
        print(f"  HOLD win/std (LSB):        {len(self.hold_buffer)} / {int(std)} (umbral {HOLD_MAX_STD_LSB})")
        print("--------------")

# ----------------- MAIN -----------------
def main():
    print("=== HX711 Scale (Raspberry Pi Zero 2 W) v1.2 ===")
    print("Comandos: [t]=tara  [c]=calibrar  [i]=info  [r]=reset  [s]=signo  [q]=salir")
    print(f"Almacenamiento: {STORE_PATH}")

    hx = HX711(PIN_DT, PIN_SCK)
    hx.begin()

    scale = Scale(hx)
    scale.load_store()

    last_print = 0.0
    try:
        while True:
            g = scale.read_net_g()
            now = time.time()
            if now - last_print >= PRINT_PERIODS:
                sys.stdout.write(f"\rPeso: {g:8.1f} g   (t/c/i/r/s/q) ")
                sys.stdout.flush()
                last_print = now

            r, _, _ = select.select([sys.stdin], [], [], 0.01)
            if r:
                line = sys.stdin.readline().strip().lower()
                if not line:
                    continue
                key = line[0]
                if key == 't':
                    scale.tare()
                elif key == 'c':
                    scale.calibrate()
                elif key == 'i':
                    scale.info()
                elif key == 'r':
                    scale.reset()
                elif key == 's':
                    scale.toggle_sign()
                elif key == 'q':
                    print("\nSaliendo...")
                    break

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            hx.power_down()
        except Exception:
            pass
        GPIO.cleanup()
        print("\nGPIO limpio. Bye!")

if __name__ == "__main__":
    main()
