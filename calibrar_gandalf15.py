#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, time, statistics
import RPi.GPIO as GPIO
from hx711 import HX711

DT, SCK = 5, 6
STORE = "hx711_ratio.json"

# ---------- utilidades robustas ----------
def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0: return 0.0
    m = n // 2
    return float(s[m]) if n % 2 else 0.5 * (s[m-1] + s[m])

def trimmed_mean(vals, trim=0.15):
    if not vals: return 0.0
    s = sorted(vals)
    k = int(len(s) * trim)
    if k > 0: s = s[k:-k]
    if not s: return 0.0
    return sum(s) / len(s)

def read_list_safe(hx, N=30, delay=0.02):
    """
    Lee N muestras crudas de forma robusta usando las funciones disponibles en la librería,
    SIN depender de filtros internos que puedan lanzar excepciones.
    Devuelve una lista con >= 2 enteros (o lo máximo que consiga).
    """
    out = []
    # 1) Intentar método que devuelve 'lista' directamente
    get_list = getattr(hx, "get_raw_data", None)
    if callable(get_list):
        try:
            lst = get_list(N)
            # algunas versiones devuelven None o una lista con None
            if lst:
                out.extend([int(x) for x in lst if x is not None])
        except Exception:
            out = []

    # 2) Si no hay lista suficiente, hacemos lecturas una a una desde mean(1)
    if len(out) < 2:
        get_mean = getattr(hx, "get_raw_data_mean", None)
        if callable(get_mean):
            for _ in range(N):
                try:
                    v = get_mean(1)
                    if v is not None:
                        out.append(int(v))
                except Exception:
                    pass
                time.sleep(delay)
    # 3) Si sigue corto, intenta un fallback de peso (sin ratio) como crudo
    if len(out) < 2:
        get_w = getattr(hx, "get_weight_mean", None)
        if callable(get_w):
            for _ in range(N):
                try:
                    v = get_w(1)  # sin ratio aún: lo usamos solo como crudo relativo
                    if v is not None:
                        out.append(int(v))
                except Exception:
                    pass
                time.sleep(delay)
    return out

def create_hx():
    # firma flexible según versión
    for args in (
        dict(dout_pin=DT, pd_sck_pin=SCK, gain_channel_A=128),
        dict(dout_pin=DT, pd_sck_pin=SCK),
        dict()
    ):
        try:
            return HX711(**args) if args else HX711(DT, SCK)
        except TypeError:
            continue
    # último recurso
    return HX711(DT, SCK)

def select_A_gain(hx):
    # canal A
    for name in ("select_channel", "set_channel", "channel"):
        f = getattr(hx, name, None)
        if callable(f):
            try: f('A')
            except Exception: pass
            break
    # ganancia A=128
    for name in ("set_gain_A", "set_gain", "set_gain_channel_A"):
        f = getattr(hx, name, None)
        if callable(f):
            try: f(128)
            except Exception: pass
            break
    # desactivar filtros internos si existe API
    for name in ("set_data_filter", "set_filter_data", "set_data_filtering"):
        f = getattr(hx, name, None)
        if callable(f):
            try: f('none')
            except Exception: pass

def main():
    GPIO.setmode(GPIO.BCM)
    hx = create_hx()
    try:
        select_A_gain(hx)

        # Tara básica (si falla, continuamos igualmente)
        print("→ Tara en vacío… no toques la plataforma")
        zero = getattr(hx, "zero", None)
        if callable(zero):
            try:
                err = zero()
                if err:
                    print("WARN: tara no perfecta (zero() devolvió error). Continúo.")
            except Exception as e:
                print(f"WARN: zero() lanzó excepción: {e}. Continúo.")
        time.sleep(0.3)

        # Pedir peso patrón
        while True:
            try:
                ref_g = float(input("Introduce el peso patrón en gramos (ej. 1000): ").strip())
                if ref_g > 0:
                    break
            except Exception:
                pass
            print("Valor inválido, prueba de nuevo.")

        print("→ Coloca el peso patrón y no toques la plataforma… midiendo 1–2 s")
        time.sleep(0.3)

        # Lecturas robustas sin filtros internos
        vals = read_list_safe(hx, N=60, delay=0.02)
        if len(vals) < 2:
            raise RuntimeError("No se obtuvieron suficientes muestras válidas. Revisa cableado/ruido.")

        # Media robusta (quita outliers)
        m = trimmed_mean(vals, trim=0.15)
        # ratio: grams = raw / ratio  => ratio = raw_mean / ref_g
        ratio = float(m) / ref_g

        with open(STORE, "w", encoding="utf-8") as f:
            json.dump({"ratio": ratio}, f, ensure_ascii=False, indent=2)

        print(f"✔ Calibración OK. ratio = {ratio:.8f} (guardado en {STORE})")
        print("Nota: si al poner peso el valor baja (negativo), edita el JSON y cambia el signo del ratio.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
