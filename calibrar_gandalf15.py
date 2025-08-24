#!/usr/bin/env python3
import json, time
import RPi.GPIO as GPIO
from hx711 import HX711   # OJO: minúsculas

DT, SCK = 5, 6
STORE = "hx711_ratio.json"

def create_hx711():
    """
    Crea la instancia HX711 adaptándose a la firma disponible en la librería.
    """
    # Intento con ganancia A explícita
    try:
        return HX711(dout_pin=DT, pd_sck_pin=SCK, gain_channel_A=128)
    except TypeError:
        pass
    # Intento sin kwargs de ganancia
    try:
        return HX711(dout_pin=DT, pd_sck_pin=SCK)
    except TypeError:
        pass
    # Intento con args posicionales
    return HX711(DT, SCK)

def set_channel_A_and_gain(hx):
    """
    Selecciona canal A y fija ganancia A=128 si la API lo soporta.
    """
    # Seleccionar canal A
    for name in ("select_channel", "set_channel", "channel"):
        meth = getattr(hx, name, None)
        if callable(meth):
            try:
                meth('A')
            except Exception:
                pass
            break
    # Fijar ganancia del canal A
    for name in ("set_gain_A", "set_gain", "set_gain_channel_A"):
        meth = getattr(hx, name, None)
        if callable(meth):
            try:
                meth(128)
            except Exception:
                pass
            break

def main():
    GPIO.setmode(GPIO.BCM)
    hx = create_hx711()
    try:
        set_channel_A_and_gain(hx)

        print("→ Tara en vacío… no toques la plataforma")
        zero_res = getattr(hx, "zero", None)
        if callable(zero_res):
            err = zero_res()
            if err:
                print("WARN: tara no perfecta (zero() devolvió error), continuo.")
        else:
            # Fallback: leer varias y tomar base interna si hiciera falta
            pass

        # Peso patrón
        while True:
            try:
                ref_g = float(input("Introduce el peso patrón en gramos (ej. 1000): ").strip())
                if ref_g > 0:
                    break
            except Exception:
                pass
            print("Valor inválido. Prueba otra vez.")

        print("→ Midiendo con el peso patrón colocado (mantén QUIETA la plataforma)…")
        time.sleep(0.4)

        get_weight_mean = getattr(hx, "get_weight_mean", None)
        if callable(get_weight_mean):
            raw_mean = get_weight_mean(20)
        else:
            # Fallback si no existe get_weight_mean
            get_raw = getattr(hx, "get_raw_data_mean", None) or getattr(hx, "get_raw_data", None)
            if callable(get_raw):
                vals = get_raw(20)
                if vals is None or (hasattr(vals, "__len__") and len(vals) == 0):
                    raw_mean = None
                else:
                    if hasattr(vals, "__len__"):
                        raw_mean = sum(vals) / len(vals)
                    else:
                        raw_mean = vals
            else:
                raw_mean = None

        if raw_mean is None:
            raise RuntimeError("Lectura nula en calibración (sin datos).")

        # En esta librería: grams = raw / ratio  →  ratio = raw_mean / ref_g
        ratio = float(raw_mean) / ref_g

        with open(STORE, "w", encoding="utf-8") as f:
            json.dump({"ratio": ratio}, f, ensure_ascii=False, indent=2)

        print(f"✔ Calibración OK. ratio = {ratio:.8f}  (guardado en {STORE})")
        print("Nota: si el signo sale invertido al pesar, edita el JSON y cambia el signo del ratio.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
