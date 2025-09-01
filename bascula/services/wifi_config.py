# -*- coding: utf-8 -*-
"""Mini servidor Flask para configurar Wi‑Fi y API key en la báscula.
- Guarda API Key en ~/.config/bascula/apikey.json
- Aplica Wi‑Fi usando nmcli si está, o wpa_cli con un script (requiere sudoers)
Ejecutar:  python3 -m bascula.services.wifi_config  (o lanzar por systemd)
"""
import os, json, subprocess, secrets, string
from pathlib import Path
from flask import Flask, request, redirect, render_template_string, session, jsonify

APP_PORT = int(os.environ.get("BASCULA_WEB_PORT", "8080"))
APP_HOST = os.environ.get("BASCULA_WEB_HOST", "0.0.0.0")
CFG_DIR = Path.home() / ".config" / "bascula"
CFG_DIR.mkdir(parents=True, exist_ok=True)
API_FILE = CFG_DIR / "apikey.json"
PIN_FILE = CFG_DIR / "pin.txt"
SECRET_FILE = CFG_DIR / "web_secret.key"

INDEX_HTML = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Bascula · Configuración</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;background:#0a0e1a;color:#e5e7eb;margin:0;padding:24px}
.wrap{max-width:900px;margin:0 auto}.card{background:#111827;padding:18px;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.grid{display:grid;grid-template-columns:1fr;gap:16px}@media(min-width:820px){.grid{grid-template-columns:1fr 1fr}}label{display:block;margin:10px 0 6px}
input{width:100%;padding:10px 12px;background:#0b1220;color:#e5e7eb;border:1px solid #243041;border-radius:10px;outline:0}
button{margin-top:12px;padding:10px 14px;background:#2563eb;color:white;border:0;border-radius:10px;cursor:pointer}.ok{color:#34d399}.warn{color:#f59e0b}</style>
</head><body><div class='wrap'>
<form method='post' action='/logout' style='text-align:right'><button>Salir</button></form>
<h1>Bascula · Configuración</h1><div class='grid'>
<div class='card'><h3>Wi‑Fi</h3><label>SSID</label><input id='ssid'><label>Contraseña</label><input id='psk' type='password'>
<button onclick='saveWifi()'>Guardar Wi‑Fi</button><div id='wifiStatus'></div></div>
<div class='card'><h3>API Key (OpenAI / ChatGPT)</h3><p>Estado: <b id='apiState'>{{ 'Presente' if api_present else 'No configurada' }}</b></p>
<label>Introduce API Key</label><input id='apikey' type='password' placeholder='sk-...'><button onclick='saveKey()'>Guardar API Key</button></div>
</div><p class='warn'>PIN actual: <b>{{pin}}</b></p></div>
<script>
async function saveKey(){const key=document.getElementById('apikey').value.trim();if(!key){alert('Introduce una clave');return;}
const r=await fetch('/api/apikey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
const j=await r.json(); if(j.ok){document.getElementById('apiState').innerText='Presente'; alert('API Key guardada');} else {alert('Error');}}
async function saveWifi(){const ssid=document.getElementById('ssid').value.trim();const psk=document.getElementById('psk').value.trim();
if(!ssid||!psk){alert('Rellena SSID y contraseña');return;}const r=await fetch('/api/wifi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid,psk})});
const j=await r.json(); if(j.ok){document.getElementById('wifiStatus').innerHTML='<span class=\"ok\">Conectado/Guardado</span>';} else {document.getElementById('wifiStatus').innerHTML='<span class=\"warn\">No se pudo aplicar (rc='+j.rc+')</span>';}}</script>
</body></html>"""

LOGIN_HTML = """<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Bascula · Acceso</title><style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;background:#0a0e1a;color:#e5e7eb;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#111827;padding:24px;border-radius:14px;width:min(420px,92vw);box-shadow:0 10px 30px rgba(0,0,0,.35)}h1{margin:0 0 6px 0;font-size:20px}
label{display:block;margin:14px 0 6px}input[type=password]{width:100%;padding:10px 12px;background:#0b1220;color:#e5e7eb;border:1px solid #243041;border-radius:10px;outline:0}
button{margin-top:14px;padding:10px 14px;background:#2563eb;color:white;border:0;border-radius:10px;cursor:pointer}.error{color:#f87171;margin-top:8px}</style></head>
<body><form class='card' method='post' action='/auth'><h1>Bascula · Acceso</h1><p>Introduce el PIN mostrado en pantalla.</p><label>PIN</label><input name='pin' type='password' autofocus>
<button type='submit'>Entrar</button>{% if error %}<div class='error'>{{error}}</div>{% endif %}</form></body></html>"""

# Secretos
if SECRET_FILE.exists():
    app_secret = SECRET_FILE.read_bytes()
else:
    app_secret = os.urandom(32)
    SECRET_FILE.write_bytes(app_secret)

if PIN_FILE.exists():
    PIN = PIN_FILE.read_text().strip()
else:
    import random
    PIN = "".join(random.choice(string.digits) for _ in range(6))
    PIN_FILE.write_text(PIN)

app = Flask(__name__)
app.secret_key = app_secret

def pin_ok():
    return session.get("pin") == PIN

@app.route("/", methods=["GET"])
def index():
    if not pin_ok():
        return render_template_string(LOGIN_HTML)
    api_present = API_FILE.exists()
    return render_template_string(INDEX_HTML, api_present=api_present, pin=PIN)

@app.route("/auth", methods=["POST"])
def auth():
    pin = request.form.get("pin","").strip()
    if pin and pin == PIN:
        session["pin"] = pin
        return redirect("/")
    return render_template_string(LOGIN_HTML, error="PIN incorrecto")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/status", methods=["GET"])
def status():
    if not pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    return jsonify({"ok": True, "api_key_present": API_FILE.exists()})

@app.route("/api/apikey", methods=["POST"])
def set_apikey():
    if not pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    key = data.get("key","").strip()
    if not key: return jsonify({"ok": False, "error": "missing"}), 400
    API_FILE.write_text(json.dumps({"openai_api_key": key}), encoding="utf-8")
    os.chmod(API_FILE, 0o600)
    return jsonify({"ok": True})

def _has(cmd):
    return subprocess.call(["/usr/bin/env", "which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def _apply_wifi_nmcli(ssid, psk):
    return subprocess.call(["/usr/bin/env", "nmcli", "dev", "wifi", "connect", ssid, "password", psk])

def _apply_wifi_wpa_cli(ssid, psk):
    script = Path.home() / "bascula-cam" / "scripts" / "apply_wifi.sh"
    return subprocess.call(["sudo", str(script), ssid, psk])

@app.route("/api/wifi", methods=["POST"])
def set_wifi():
    if not pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    ssid = data.get("ssid","").strip()
    psk = data.get("psk","").strip()
    if not ssid or not psk: return jsonify({"ok": False, "error": "missing"}), 400
    if _has("nmcli"):
        rc = _apply_wifi_nmcli(ssid, psk)
    else:
        rc = _apply_wifi_wpa_cli(ssid, psk)
    return jsonify({"ok": rc == 0, "rc": rc})

if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
