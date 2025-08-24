#!/usr/bin/env python3
import json, time, os
import RPi.GPIO as GPIO
from HX711 import HX711

DT, SCK = 5, 6
STORE = "hx711_ratio.json"

def load_ratio():
    if not os.path.exists(STORE):
        return None
    with open(STORE, "r", encoding="utf-8") as f:
        d = json.load(f)
    return float(d.get("ratio", 0.0))

def main():
    GPIO.setmode(GPIO.BCM)
    hx = HX711(dout_pin=DT, pd_sck_pin=SCK, channel='A', gain_A=128)
    try:
        # Asegura offset (tara) en vacío
        print("→ Tara en vacío…")
        err = hx.zero()
        if err:
            print("WARN: tara no perfecta; continúo igualmente.")

        ratio = load_ratio()
        if not ratio or ratio == 0.0:
            raise RuntimeError(f"No encuentro ratio válido en {STORE}. Ejecuta primero calibrar_gandalf15.py")

        # En esta librería: grams = raw / ratio
        hx.set_scale_ratio(ratio)

        print("Leyendo…  Ctrl+C para salir.  (Pon peso en la plataforma)")
        while True:
            # media de 10 muestras para suavizar
            g = hx.get_weight_mean(10)   # devuelve gramos usando ratio
            if g is None:
                print("\rtimeout              ", end="")
            else:
                print(f"\rPeso: {g:8.1f} g     ", end="")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nSaliendo…")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
