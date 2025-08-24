#!/usr/bin/env python3
import RPi.GPIO as GPIO, time

DT, SCK = 27, 17  # DT=GPIO27 (pin 13), SCK=GPIO17 (pin 11)
GPIO.setmode(GPIO.BCM)
GPIO.setup(DT,  GPIO.IN,  pull_up_down=GPIO.PUD_UP)   # pull-up ayuda en DT
GPIO.setup(SCK, GPIO.OUT, initial=GPIO.LOW)

T_HIGH = 0.00001  # 10 us
T_LOW  = 0.00001

def ready():
    return GPIO.input(DT) == 0

def read(timeout=1.2):
    t0 = time.time()
    while not ready():
        if time.time() - t0 > timeout:
            return None
        time.sleep(0.001)
    v = 0
    for _ in range(24):
        GPIO.output(SCK, True);  time.sleep(T_HIGH)
        v = (v << 1) | GPIO.input(DT)
        GPIO.output(SCK, False); time.sleep(T_LOW)
    GPIO.output(SCK, True);  time.sleep(T_HIGH)   # pulso 25 (A, gain 128)
    GPIO.output(SCK, False); time.sleep(T_LOW)
    if v & 0x800000:
        v |= ~0xffffff
    return v

base = None
try:
    for i in range(40):
        r = read()
        if r is None:
            print(f"{i:02d} timeout")
        else:
            if base is None: base = r
            print(f"{i:02d} raw: {r:>9d}   net: {r-base:>9d}")
        time.sleep(0.08)
finally:
    GPIO.cleanup()
