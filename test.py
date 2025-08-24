#!/usr/bin/python3

from hx711 import HX711

try:
    hx711 = HX711(
        dout_pin=5,      # Pin DT conectado al GPIO 5
        pd_sck_pin=6,    # Pin SCK conectado al GPIO 6
        channel='A',
        gain=64
    )
    hx711.reset()        # Opcional, reinicia el HX711

    # Lee 3 mediciones crudas
    measures = hx711.get_raw_data(num_measures=3)
    print("\n".join([str(value) for value in measures]))

finally:
    import RPi.GPIO as GPIO
    GPIO.cleanup()       # Limpia los estados de los GPIO al finalizar
