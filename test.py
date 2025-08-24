python3 - <<'PY'
import RPi.GPIO as G, time
DT,SCK=27,17
G.setmode(G.BCM)
G.setup(DT,G.IN,pull_up_down=G.PUD_UP)
G.setup(SCK,G.OUT,initial=G.LOW)
print("DT nivel inicial:", G.input(DT)," (0=READY)")
t=time.time(); cnt=0
while time.time()-t<2:
    if G.input(DT)==0: cnt+=1
    time.sleep(0.001)
print("Veces READY en 2s:", cnt)
G.cleanup()
PY
