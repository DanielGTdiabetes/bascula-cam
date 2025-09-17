from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bascula.services.voice import VoiceService

v = VoiceService()
print("say: hola")
v.say("Hola, probando voz.")

got = []

def cb(text: str) -> None:
    print("heard:", text)
    got.append(text)

print("listen start")
v.start_listening(cb, duration=3)

import time

time.sleep(1.0)
print("is_listening:", v.is_listening())
v.stop_listening()
print("done")
