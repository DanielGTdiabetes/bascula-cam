python3 - <<'PY'
import RPi.GPIO as GPIO, time
DT,SCK=5,6
GPIO.setmode(GPIO.BCM); GPIO.setup(DT,GPIO.IN); GPIO.setup(SCK,GPIO.OUT,initial=GPIO.LOW)
def ready(): return GPIO.input(DT)==0
def read():
  t=time.time()
  while not ready():
    if time.time()-t>0.2: return None
    time.sleep(0.001)
  v=0
  for _ in range(24):
    GPIO.output(SCK,True); time.sleep(0.000002)
    v=(v<<1)|GPIO.input(DT)
    GPIO.output(SCK,False); time.sleep(0.000002)
  GPIO.output(SCK,True); time.sleep(0.000002); GPIO.output(SCK,False); time.sleep(0.000002)
  if v & 0x800000: v |= ~0xffffff
  return v
print("DT listo (0=ok):", GPIO.input(DT))
for i in range(10):
  r=read(); print(i, r); time.sleep(0.2)
GPIO.cleanup()
PY
