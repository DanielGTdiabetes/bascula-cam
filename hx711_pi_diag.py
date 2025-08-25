#!/usr/bin/env python3
# hx711_pi_diag.py — Diagnóstico y lectura básica de HX711 en Raspberry Pi
# Config para Dani:
#   DT  -> GPIO22
#   SCK -> GPIO17
#
# Notas:
# - Mantén SCK en LOW desde antes de iniciar (recomendado pull-down físico 47–100 kΩ a GND).
# - Alimenta el HX711 a 3.3 V. Si pruebas 5 V, usa conversor de nivel (DT->Pi y SCK<-Pi).
# - El script no usa pull-ups en DT; el propio HX711 gobierna esa línea.

import RPi.GPIO as GPIO
import time

# ======= CONFIGURACIÓN =======
PIN_DT  = 22         # DOUT del HX711 (hacia Pi)
PIN_SCK = 17         # PD_SCK del HX711 (desde Pi)
CLK_US  = 50e-6      # semiperiodo de reloj ~50 us (ajustable)
READY_TIMEOUT_S = 3.0
LECTURAS = 10        # lecturas a imprimir
PULSOS_EXTRA = 25    # 25=A128 (por defecto). 26=B32, 27=A64

# ======= AUXILIARES GPIO =======
def setup():
    GPIO.setmode(GPIO.BCM)
    # MUY IMPORTANTE: SCK debe quedar en LOW desde ya
    GPIO.setup(PIN_SCK, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PIN_DT,  GPIO.IN)  # sin PUD

    # pequeño settle
    time.sleep(0.01)

def cleanup():
    try:
        GPIO.output(PIN_SCK, GPIO.LOW)
    except Exception:
        pass
    GPIO.cleanup()

def sck_pulse():
    GPIO.output(PIN_SCK, True)
    time.sleep(CLK_US)
    GPIO.output(PIN_SCK, False)
    time.sleep(CLK_US)

def powerdown_reset():
    # SCK alto > 60 us apaga/rehabilita el chip, útil para salir de estados raros
    GPIO.output(PIN_SCK, True)
    time.sleep(0.001)  # 1 ms
    GPIO.output(PIN_SCK, False)
    time.sleep(0.003)

def wait_ready(timeout_s=READY_TIMEOUT_S) -> bool:
    t0 = time.time()
    while (time.time() - t0) < timeout_s:
        if GPIO.input(PIN_DT) == 0:
            return True
        time.sleep(0.001)
    return False

# ======= LECTURA 24 BITS =======
def read_raw_24(pulsos_extra=PULSOS_EXTRA):
    """
    Lee 24 bits (MSB primero) del HX711 observando DT en el flanco alto de SCK.
    Luego aplica 'pulsos_extra' para fijar ganancia/canal (25=A128, 26=B32, 27=A64).
    Devuelve (bitstring, signed_24bit, dt_after)
    """
    bits = []
    for _ in range(24):
        GPIO.output(PIN_SCK, True)
        time.sleep(CLK_US)
        bits.append(GPIO.input(PIN_DT))
        GPIO.output(PIN_SCK, False)
        time.sleep(CLK_US)

    # Pulsos extra para fijar ganancia/canal
    for _ in range(pulsos_extra - 24):
        sck_pulse()

    # construir bitstring y entero con signo
    bitstr = "".join("1" if b else "0" for b in bits)
    val = 0
    for b in bits:
        val = (val << 1) | (1 if b else 0)
    if val & (1 << 23):  # bit de signo
        val -= (1 << 24)

    dt_after = GPIO.input(PIN_DT)
    return bitstr, val, dt_after

# ======= PROGRAMA PRINCIPAL =======
def main():
    print("=== HX711 Pi Diag ===")
    print(f"DT  (DOUT): GPIO{PIN_DT}")
    print(f"SCK (CLK) : GPIO{PIN_SCK}")
    setup()
    try:
        # Reset inicial por si el chip quedó en power-down
        print("Haciendo reset/power-down corto…")
        powerdown_reset()

        # Comprobar READY
        print("Esperando READY (DT=0)…")
        if not wait_ready():
            print("⚠️  Timeout esperando READY (DT permanece en 1).")
            print("Sugerencias:")
            print("  • Verifica E+–E- ≈ VCC en el módulo (excitación presente).")
            print("  • Asegura SCK LOW de hardware (pull-down 47–100 kΩ).")
            print("  • Prueba a alimentar a 5 V SOLO con conversor de nivel.")
            return

        print("✅ READY detectado. Leyendo muestras…")
        for i in range(1, LECTURAS + 1):
            # Asegurar que está READY antes de cada lectura
            if not wait_ready():
                print(f"[{i}] DT no está listo. Reset y reintento…")
                powerdown_reset()
                if not wait_ready():
                    print(f"[{i}] Sigue sin READY tras reset.")
                    continue

            bitstr, val, dt_after = read_raw_24(PULSOS_EXTRA)
            unos = bitstr.count('1')
            print(f"[{i}] bits(24)={bitstr} (1s={unos},0s={24-unos})  signed24={val}  DT_despues={dt_after}")
            time.sleep(0.05)

        print("\nListo. Si los valores cambian al poner/quitar peso, el HX711 está OK.")
        print("Si los bits son siempre iguales o DT nunca baja, revisa hardware/alimentación.")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
