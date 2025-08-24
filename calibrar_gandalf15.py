#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, time
import RPi.GPIO as GPIO
from hx711 import HX711

DT, SCK = 5, 6
STORE = "hx711_ratio.json"

def trimmed_mean(vals, trim=0.15):
    if not vals: return 0.0
    s = sorted(vals)
    k = int(len(s) * trim)
    if k > 0: s = s[k:-k]
    if not s: return 0.0
    return sum(s) / len(s)

def read_list_safe(hx, N=60, delay=0.02):
    out = []
    # 1) Preferir lista cruda si existe
    get_list = getattr(hx, "get_raw_data", None)
    if callable(get_list):
        try:
            lst = get_list(N)
            if lst:
                out.extend([int(x) for x in lst if x is not None])
        except Exception:
            out = []
    # 2) Fallback: medias de 1 lectura (evita filtros internos)
    if len(out) < 3:
        get_mean = getattr(hx, "get_raw_data_mean", None)
        if callable(get_mean):
            for _ in range(N):
                try:
                    v = get_mean(1)
                    if v is not None: out.append(int(v))
                except Exception:
                    pass
                time.sleep(delay)
    # 3) Último recurso: usar get_weight_mean(1) como crudo relativo
    if len(out) < 3:
        get_w = getattr(hx, "get_weight_mean", None)
        if callable(get_w):
            for _ in range(N):
                try:
                    v = get_w(1)
                    if v is not None: out.append(int(v))
                except Exception:
                    pass
                time.sleep(delay)
    return out

def create_hx():
    for args in (
        dict(dout_pin=DT, pd_sck_pin=SCK, gain_channel_A=128),
        dict(dout_pin=DT, pd_sck_pin=SCK),
        dict()
    ):
        try:
            return HX711(**args) if args else HX711(DT, SCK)
        except TypeError:
            continue
    return HX711(DT, SCK)

def select_A_gain_disable_filters(hx):
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
    # desactiva filtros internos si existieran
    for name in ("set_data_filter", "set_filter_data", "set_data_filtering"):
        f = getattr(hx, name, None)
        if callable(f):
            try: f('none')
            except Exception: pass

def main():
    GPIO.setmode(GPIO.BCM)
    hx = create_hx()
    try:
        select_A_gain_disable_filters(hx)

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

        while True:
            try:
                ref_g = float(input("Introduce el peso patrón en gramos (ej. 1000): ").strip())
                if ref_g > 0: break
            except Exception:
                pass
            print("Valor inválido, prueba de nuevo.")

        print("→ Coloca el peso patrón y NO toques la plataforma… midiendo 1–2 s")
        time.sleep(0.3)

        vals = read_list_safe(hx, N=60, delay=0.02)
        if len(vals) < 3:
            raise RuntimeError("No se obtuvieron suficientes muestras válidas. Revisa cableado/ruido/mecánica.")

        raw_mean = trimmed_mean(vals, trim=0.15)
        if abs(raw_mean) < 1e-6:
            raise RuntimeError(f"Media cruda ~0 (raw_mean={raw_mean}). No puede calibrar.")

        # En esta lib: grams = raw / ratio  ⇒  ratio = raw_mean / ref_g
        ratio = float(raw_mean) / ref_g

        with open(STORE, "w", encoding="utf-8") as f:
            json.dump({"ratio": ratio}, f, ensure_ascii=False, indent=2)

        print(f"✔ Calibración OK. ratio = {ratio:.8f}  (guardado en {STORE})")
        print("Nota: si el signo sale invertido al pesar, edita el JSON y cambia el signo del ratio.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
