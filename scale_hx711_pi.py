#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scale_hx711_pi.py  (v1.1)
Báscula con HX711 en Raspberry Pi Zero 2 W (sin librerías externas HX711).

Cambios v1.1:
- Eliminado el hilo/teclado en modo cbreak (que chocaba con input()).
- Lectura de comandos no bloqueante con select; para calibrar se usa input() normal.
- Verás lo que tecleas y la calibración no se cuelga.

Funciones:
- Promedio + filtro IIR para estabilizar.
- Tara [t], Calibración [c] (en gramos), Info [i], Reset [r], Invertir signo [s], Salir [q].
- Persistencia en JSON: factor (g/LSB), offset de tara (LSB) y 'invert_sign'.

Cableado (BCM):
  HX711 DT  -> BCM5
  HX711 SCK -> BCM6
  HX711 VCC -> 3V3
  HX711 GND -> GND
"""

import sys, os, time, json, select
import RPi.GPIO as GPIO

# ----------------- CONFIGURACIÓN -----------------
GPIO.setmode(GPIO.BCM)
PIN_DT  = 5   # DOUT del HX711
PIN_SCK = 6   # SCK  del HX711

OVERSAMPLES   = 10       # lecturas por media rápida
IIR_ALPHA     = 0.20     # 0..1 (más alto = más rápido, menos suave)
PRINT_PERIODS = 0.20     # s entre impresiones

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

# ----------------- LÓGICA DE ESCALA -----------------
class Scale:
    def __init__(self, hx: HX711):
        self.hx = hx
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.iir_state = None

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

    # Lecturas
    def read_oversampled(self, n=OVERSAMPLES):
        acc = 0
        for _ in range(max(1, n)):
            acc += self.hx.read_raw()
        return acc // max(1, n)

    def read_net_lsb(self):
        raw = self.read_oversampled()
        net = raw - self.tare_offset
        if self.invert_sign:
            net = -net
        return net

    def read_net_g(self):
        lsb = self.read_net_lsb()
        g = lsb * self.calibration_g_per_lsb
        if self.iir_state is None:
            self.iir_state = g
        else:
            self.iir_state = (1.0 - IIR_ALPHA) * self.iir_state + IIR_ALPHA * g
        return self.iir_state

    # Operaciones
    def tare(self, samples=30):
        print("\n→ Tara: deja la plataforma VACÍA...")
        time.sleep(0.5)
        vals = [self.hx.read_raw() for _ in range(max(10, samples))]
        self.tare_offset = int(round(sum(vals) / len(vals)))
        self.save_store()
        print(f"✔ Tara guardada (offset LSB = {self.tare_offset})")

    def calibrate(self):
        print("\n→ Calibración: coloca un peso patrón y escribe su valor en gramos (ej. 1000)")
        while True:
            try:
                s = input("Peso patrón [g]: ").strip()
                target = float(s)
                if target > 0:
                    break
                print("Debe ser > 0.")
            except Exception:
                print("Entrada inválida. Intenta de nuevo.")
        print("Midiendo… espera a que se estabilice (≈0.6 s).")
        time.sleep(0.3)
        samples = 60
        acc = 0
        for _ in range(samples):
            acc += self.read_net_lsb()
            time.sleep(0.01)
        mean_lsb = acc / samples
        if abs(mean_lsb) < 1e-6:
            print("Lectura nula; revisa tara o montaje.")
            return
        self.calibration_g_per_lsb = target / mean_lsb
        self.save_store()
        print(f"✔ Calibración OK: {self.calibration_g_per_lsb:.8f} g/LSB")

    def reset(self):
        self.calibration_g_per_lsb = 1.0
        self.tare_offset = 0
        self.invert_sign = False
        self.save_store()
        print("\n✔ Calibración/tara/signo reseteados.")

    def toggle_sign(self):
        self.invert_sign = not self.invert_sign
        self.save_store()
        print(f"\n✔ invert_sign = {self.invert_sign}")

    def info(self):
        print("\n--- INFO ---")
        print(f"  tare_offset (LSB):         {self.tare_offset}")
        print(f"  factor (g/LSB):            {self.calibration_g_per_lsb:.8f}")
        print(f"  invert_sign:               {self.invert_sign}")
        print(f"  store:                     {STORE_PATH}")
        print(f"  OVERSAMPLES / IIR_ALPHA:   {OVERSAMPLES} / {IIR_ALPHA}")
        print("--------------")

# ----------------- MAIN -----------------
def main():
    print("=== HX711 Scale (Raspberry Pi Zero 2 W) v1.1 ===")
    print("Comandos: [t]=tara  [c]=calibrar  [i]=info  [r]=reset  [s]=signo  [q]=salir")
    print(f"Almacenamiento: {STORE_PATH}")

    hx = HX711(PIN_DT, PIN_SCK)
    hx.begin()

    scale = Scale(hx)
    scale.load_store()

    last_print = 0.0
    try:
        while True:
            # Medición y print periódico
            g = scale.read_net_g()
            now = time.time()
            if now - last_print >= PRINT_PERIODS:
                sys.stdout.write(f"\rPeso: {g:8.1f} g   (t/c/i/r/s/q) ")
                sys.stdout.flush()
                last_print = now

            # Lectura no bloqueante del teclado (línea completa)
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
