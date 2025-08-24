# guardar como hx711_rawtest_slow.py
import RPi.GPIO as GPIO, time
DT,SCK = 5,6  # DT=GPIO5, SCK=GPIO6
GPIO.setmode(GPIO.BCM)
GPIO.setup(DT, GPIO.IN, pull_up_down=GPIO.PUD_UP)      # DT con pull-up interno
GPIO.setup(SCK, GPIO.OUT, initial=GPIO.LOW)
time_high = 0.00001   # 10 us (más lento que antes)
time_low  = 0.00001

def ready():
    return GPIO.input(DT) == 0

def read(timeout=0.8):
    t = time.time()
    while not ready():
        if time.time()-t > timeout:
            return None
        time.sleep(0.001)
    v = 0
    for _ in range(24):
        GPIO.output(SCK, True);  time.sleep(time_high)
        v = (v<<1) | GPIO.input(DT)
        GPIO.output(SCK, False); time.sleep(time_low)
    GPIO.output(SCK, True);  time.sleep(time_high)   # pulso 25 (ganancia 128)
    GPIO.output(SCK, False); time.sleep(time_low)
    if v & 0x800000:
        v |= ~0xffffff
    return v

base=None
for i in range(40):
    r = read()
    if r is None:
        print(i, "timeout")
    else:
        if base is None: base = r
        print(i, "raw:", r, "net:", r-base)
    time.sleep(0.08)

GPIO.cleanup()
