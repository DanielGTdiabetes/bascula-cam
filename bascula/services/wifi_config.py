# -*- coding: utf-8 -*-
"""Mini servidor Flask para configurar Wi‑Fi y API key en la báscula.
- Guarda API Key en ~/.config/bascula/apikey.json
- Aplica Wi‑Fi usando nmcli si está, o wpa_cli con un script (requiere sudoers)
Ejecutar:  python3 -m bascula.services.wifi_config  (o lanzar por systemd)
"""
import os, json, subprocess, secrets, string
from pathlib import Path
from flask import Flask, request, redirect, render_template_string, session, jsonify
# Importar utilidades desde el paquete correctamente instalado
# Antes: `from utils import ...` podía fallar al ejecutarse como módulo (-m)
from bascula.utils import load_config, save_config

APP_PORT = int(os.environ.get("BASCULA_WEB_PORT", "8080"))
APP_HOST = os.environ.get("BASCULA_WEB_HOST", "127.0.0.1")
_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CFG_DIR = Path(_CFG_ENV) if _CFG_ENV else (Path.home() / ".config" / "bascula")
CFG_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(CFG_DIR, 0o700)
except Exception:
    pass
API_FILE = CFG_DIR / "apikey.json"
NS_FILE = CFG_DIR / "nightscout.json"
PIN_FILE = CFG_DIR / "pin.txt"
SECRET_FILE = CFG_DIR / "web_secret.key"
APP_CFG_FILE = Path.home() / "bascula-cam" / "config.json"

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
<label>Introduce API Key</label><input id='apikey' type='password' placeholder='sk-...'>
<div>
  <button onclick='saveKey()'>Guardar API Key</button>
  <button style='margin-left:8px' onclick='testKey()'>Probar API Key</button>
  <span id='apiStatus' style='margin-left:8px'></span>
</div>
</div>
<div class='card'><h3>Nightscout</h3>
<label>URL</label><input id='ns_url' placeholder='https://mi-nightscout.example.com'>
<label>Token</label><input id='ns_token' type='password' placeholder='(opcional)'>
<div>
  <button onclick='saveNS()'>Guardar Nightscout</button>
  <button style='margin-left:8px' onclick='testNS()'>Probar</button>
  <span id='nsStatus' style='margin-left:8px'></span>
  </div>
</div>
<div class='card'><h3>Parámetros de bolo (experimental)</h3>
<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px'>
  <div><label>Objetivo (mg/dL)</label><input id='tbg' placeholder='110'></div>
  <div><label>ISF (mg/dL/U)</label><input id='isf' placeholder='50'></div>
  <div><label>Ratio HC (g/U)</label><input id='carb' placeholder='10'></div>
  <div><label>DIA (h)</label><input id='dia' placeholder='4'></div>
</div>
<button onclick='saveBolus()'>Guardar parámetros</button>
<span id='bolStatus' style='margin-left:8px'></span>
</div>
</div><p class='warn'>PIN actual: <b>{{pin}}</b></p></div>
<script>
async function saveKey(){
  const key=document.getElementById('apikey').value.trim();
  if(!key){alert('Introduce una clave');return;}
  const r=await fetch('/api/apikey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
  const j=await r.json();
  if(j.ok){document.getElementById('apiState').innerText='Presente'; document.getElementById('apiStatus').innerHTML='<span class=\"ok\">Guardado</span>';}
  else {document.getElementById('apiStatus').innerHTML='<span class=\"warn\">Error: '+(j.error||'desconocido')+'</span>';}
}
async function testKey(){
  try{
    const r=await fetch('/api/apikey_status');
    const j=await r.json();
    if(j.ok){
      document.getElementById('apiState').innerText=j.present?'Presente':'No configurada';
      document.getElementById('apiStatus').innerHTML=j.present?'<span class=\"ok\">Presente</span>':'<span class=\"warn\">No configurada</span>';
    } else {
      document.getElementById('apiStatus').innerHTML='<span class=\"warn\">Error</span>';
    }
  }catch(e){ document.getElementById('apiStatus').innerHTML='<span class=\"warn\">Error</span>'; }
}
async function saveWifi(){const ssid=document.getElementById('ssid').value.trim();const psk=document.getElementById('psk').value.trim();
if(!ssid||!psk){alert('Rellena SSID y contraseña');return;}const r=await fetch('/api/wifi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid,psk})});
const j=await r.json(); if(j.ok){document.getElementById('wifiStatus').innerHTML='<span class=\"ok\">Conectado/Guardado</span>';} else {document.getElementById('wifiStatus').innerHTML='<span class=\"warn\">No se pudo aplicar (rc='+j.rc+')</span>';}}
async function loadNS(){try{const r=await fetch('/api/nightscout');if(!r.ok)return;const j=await r.json();if(j.ok&&j.data){if(j.data.url)document.getElementById('ns_url').value=j.data.url;if(j.data.token)document.getElementById('ns_token').value=j.data.token;}}catch(e){}}
async function saveNS(){
  const url=document.getElementById('ns_url').value.trim();
  const token=document.getElementById('ns_token').value.trim();
  const r=await fetch('/api/nightscout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,token})});
  const j=await r.json();
  if(j.ok){document.getElementById('nsStatus').innerHTML='<span class=\"ok\">Guardado</span>';}
  else {document.getElementById('nsStatus').innerHTML='<span class=\"warn\">Error: '+(j.error||'desconocido')+'</span>';}
}
async function testNS(){const url=document.getElementById('ns_url').value.trim();const token=document.getElementById('ns_token').value.trim();if(!url){document.getElementById('nsStatus').innerHTML='<span class=\"warn\">Falta URL</span>';return;}document.getElementById('nsStatus').innerText='Probando...';try{const r=await fetch('/api/nightscout_test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,token})});const j=await r.json();if(j.ok){document.getElementById('nsStatus').innerHTML='<span class=\"ok\">OK</span>';} else {document.getElementById('nsStatus').innerHTML='<span class=\"warn\">'+(j.error||'Fallo')+'</span>';}}catch(e){document.getElementById('nsStatus').innerHTML='<span class=\"warn\">Error</span>';}}
async function loadBolus(){try{const r=await fetch('/api/bolus');if(!r.ok)return;const j=await r.json();if(j.ok&&j.data){const d=j.data; if(d.tbg!=null)document.getElementById('tbg').value=d.tbg; if(d.isf!=null)document.getElementById('isf').value=d.isf; if(d.carb!=null)document.getElementById('carb').value=d.carb; if(d.dia!=null)document.getElementById('dia').value=d.dia;}}catch(e){}}
async function saveBolus(){const payload={tbg:parseInt(document.getElementById('tbg').value||'0'),isf:parseInt(document.getElementById('isf').value||'0'),carb:parseInt(document.getElementById('carb').value||'0'),dia:parseInt(document.getElementById('dia').value||'0')};const r=await fetch('/api/bolus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const j=await r.json();document.getElementById('bolStatus').innerHTML=j.ok?'<span class=\"ok\">Guardado</span>':'<span class=\"warn\">Error</span>';}
loadNS(); loadBolus();</script>
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
    try:
        os.chmod(SECRET_FILE, 0o600)
    except Exception:
        pass

if PIN_FILE.exists():
    PIN = PIN_FILE.read_text(encoding="utf-8", errors="ignore").strip()
else:
    import random
    PIN = "".join(random.choice(string.digits) for _ in range(6))
    PIN_FILE.write_text(PIN, encoding="utf-8")
    try:
        os.chmod(PIN_FILE, 0o600)
    except Exception:
        pass

app = Flask(__name__)
app.secret_key = app_secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
)

def pin_ok():
    return session.get("pin") == PIN

def ui_or_pin_ok():
    try:
        ra = request.remote_addr or ""
    except Exception:
        ra = ""
    # Permite peticiones locales (UI en el mismo host) sin sesión de navegador
    if ra in ("127.0.0.1", "::1"):
        return True
    return pin_ok()

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
    # Mitigar fuerza bruta con peque1o retraso
    try:
        import time; time.sleep(0.8)
    except Exception:
        pass
    return render_template_string(LOGIN_HTML, error="PIN incorrecto")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/status", methods=["GET"])
def status():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    return jsonify({"ok": True, "api_key_present": API_FILE.exists()})

@app.route("/api/apikey_status", methods=["GET"])
def apikey_status():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    try:
        present = API_FILE.exists()
        key = None
        try:
            if present:
                key = json.loads(API_FILE.read_text(encoding="utf-8")).get("openai_api_key", "").strip()
        except Exception:
            key = ""
        valid = bool(key and key.startswith("sk-") and len(key) > 20)
        return jsonify({"ok": True, "present": present, "valid": valid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/apikey", methods=["POST"])
def set_apikey():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    key = data.get("key","").strip()
    if not key: return jsonify({"ok": False, "error": "missing"}), 400
    API_FILE.write_text(json.dumps({"openai_api_key": key}), encoding="utf-8")
    try:
        os.chmod(API_FILE, 0o600)
    except Exception:
        # En Windows puede fallar chmod; no debe impedir guardar
        pass
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
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    ssid = data.get("ssid","").strip()
    psk = data.get("psk","").strip()
    if not ssid or not psk: return jsonify({"ok": False, "error": "missing"}), 400
    if _has("nmcli"):
        rc = _apply_wifi_nmcli(ssid, psk)
    else:
        rc = _apply_wifi_wpa_cli(ssid, psk)
    return jsonify({"ok": rc == 0, "rc": rc})

@app.route("/api/wifi_scan", methods=["GET"])
def wifi_scan():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    if not _has("nmcli"):
        return jsonify({"ok": False, "error": "nmcli_unavailable"}), 400
    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], stderr=subprocess.STDOUT, text=True, timeout=8)
        nets = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split(":")
            while len(parts) < 3:
                parts.append("")
            ssid, signal, sec = parts[0], parts[1], parts[2]
            if not ssid:
                continue
            nets.append({"ssid": ssid, "signal": signal or "", "sec": sec or ""})
        return jsonify({"ok": True, "nets": nets})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Configuración de bolo (en ~/bascula-cam/config.json)
@app.route("/api/bolus", methods=["GET", "POST"])
def bolus_cfg():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    if request.method == "GET":
        try:
            cfg = load_config()
            out = {
                "tbg": int(cfg.get("target_bg_mgdl", 110) or 0),
                "isf": int(cfg.get("isf_mgdl_per_u", 50) or 0),
                "carb": int(cfg.get("carb_ratio_g_per_u", 10) or 0),
                "dia": int(cfg.get("dia_hours", 4) or 0),
            }
            return jsonify({"ok": True, "data": out})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    # POST
    try:
        req = request.get_json(force=True, silent=True) or {}
        tbg = int(req.get("tbg") or 0)
        isf = int(req.get("isf") or 0)
        carb = int(req.get("carb") or 0)
        dia = int(req.get("dia") or 0)
        cfg = load_config()
        cfg.update({
            "target_bg_mgdl": max(60, tbg),
            "isf_mgdl_per_u": max(5, isf),
            "carb_ratio_g_per_u": max(2, carb),
            "dia_hours": max(2, dia),
        })
        save_config(cfg)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/nightscout", methods=["GET", "POST"])
def nightscout_cfg():
    if not ui_or_pin_ok(): return jsonify({"ok": False, "error": "auth"}), 401
    if request.method == "GET":
        try:
            if NS_FILE.exists():
                data = json.loads(NS_FILE.read_text(encoding="utf-8"))
            else:
                data = {}
            return jsonify({"ok": True, "data": data})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    # POST
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    token = (data.get("token") or "").strip()
    try:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        NS_FILE.write_text(json.dumps({"url": url, "token": token}), encoding="utf-8")
        try:
            os.chmod(NS_FILE, 0o600)
        except Exception:
            pass
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Probar conectividad/estado de Nightscout (evita CORS en el navegador)
@app.route("/api/nightscout_test", methods=["POST"])
def nightscout_test():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip().rstrip('/')
    token = (data.get("token") or "").strip()
    if not url:
        # fallback a fichero si no viene en la petici3n
        try:
            if NS_FILE.exists():
                d = json.loads(NS_FILE.read_text(encoding="utf-8"))
                url = (d.get("url") or "").strip().rstrip('/')
                token = (token or d.get("token") or "").strip()
        except Exception:
            pass
    if not url:
        return jsonify({"ok": False, "error": "missing_url"}), 400
    try:
        import requests as rq
        r = rq.get(f"{url}/api/v1/status.json", params={"token": token} if token else None, timeout=6)
        if r.ok:
            try:
                j = r.json()
            except Exception:
                j = {}
            return jsonify({"ok": True, "http": r.status_code, "data": {"apiEnabled": j.get("apiEnabled", True)}})
        else:
            return jsonify({"ok": False, "error": f"http_{r.status_code}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
