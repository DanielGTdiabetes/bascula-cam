#!/usr/bin/env python3
import json, time
import RPi.GPIO as GPIO
from hx711 import HX711

DT, SCK = 5, 6
STORE = "hx711_ratio.json"

def main():
    GPIO.setmode(GPIO.BCM)
    hx = HX711(dout_pin=DT, pd_sck_pin=SCK, channel='A', gain_A=128)
    try:
        # 1) Tara (en vacío, no toques la plataforma)
        print("→ Tara en vacío…")
        err = hx.zero()           # mide y guarda el offset interno
        if err:
            raise RuntimeError("Tara no exitosa (hx.zero() devolvió error)")

        # 2) Pide peso patrón y calcula ratio
        ref_g = float(input("Introduce el peso patrón en gramos (ej. 1000): ").strip())
        if ref_g <= 0:
            raise ValueError("El peso debe ser > 0 g")

        print("→ Midiendo con el peso patrón colocado (mantén QUIETO)…")
        time.sleep(0.5)
        # Nota: get_weight_mean(N) devuelve “gramos” si el ratio ya está bien;
        # como aún no tenemos ratio, lo usamos como “LSB medios” relativos
        raw_mean = hx.get_weight_mean(20)
        if raw_mean is None:
            raise RuntimeError("Lectura nula en calibración")

        # El ratio es cuántos LSB corresponden a 1 gramo
        # En esta librería se pasa como "grams per LSB" (escala) o inverso según versión,
        # así que calculamos y comprobamos signo luego.
        # En gandalf15, set_scale_ratio(r) hace: grams = raw / r
        # Por tanto r = raw_mean / ref_g
        ratio = raw_mean / ref_g

        # Guarda ratio y signo
        data = {"ratio": ratio}
        with open(STORE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✔ Calibración OK. ratio = {ratio:.8f}  (guardado en {STORE})")
        print("Si al poner peso real sale negativo, invierte el signo del ratio en el JSON.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
