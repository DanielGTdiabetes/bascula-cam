from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess, requests

PANEL_URL = "http://192.168.50.1:8080"

app = FastAPI(title="Bascula WiFi Config", version="1.1")

def panel_online() -> bool:
    try:
        r = requests.get(PANEL_URL, timeout=1.5)
        return r.status_code < 500
    except Exception:
        return False

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Configurar Wi-Fi</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{font-family:sans-serif;max-width:560px;margin:2rem auto;padding:0 1rem;}
  .card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0;}
  .ok{color:green}.warn{color:#c77e00}.err{color:#b00020}
  button{padding:.6rem 1rem;border-radius:8px;border:1px solid #222;cursor:pointer;background:#f6f6f6}
  input{width:100%;padding:.5rem;border-radius:8px;border:1px solid #bbb;margin:.25rem 0 .75rem}
  a.btn{display:inline-block;padding:.6rem 1rem;border-radius:8px;border:1px solid #222;text-decoration:none;color:#000;background:#f6f6f6}
</style>
</head>
<body>
  <h2>Configurar Wi-Fi</h2>
  <div class="card">
    <form method="post" action="/connect">
      <label>SSID:<br><input type="text" name="ssid" required></label>
      <label>Contraseña:<br><input type="password" name="password"></label>
      <button type="submit">Conectar</button>
    </form>
  </div>

  <div class="card">
    <h3>Panel completo</h3>
    <p>Configuración avanzada (API key ChatGPT, Nightscout, etc.).</p>
    <p id="panel_state" class="warn">Comprobando estado del panel…</p>
    <p>
      <a class="btn" href="{panel_url}" target="_blank">Abrir panel</a>
    </p>
    <small>Si no abre todavía, primero conecta a una red Wi-Fi y vuelve a intentarlo.</small>
  </div>

  <script>
    fetch('/panel-status').then(r=>r.json()).then(j=>{
      const el=document.getElementById('panel_state');
      if(j.ok){ el.textContent = 'Panel disponible'; el.className='ok'; }
      else { el.textContent = 'Panel no disponible aún'; el.className='warn'; }
    }).catch(()=>{});
  </script>
</body>
</html>
""".replace("{panel_url}", PANEL_URL)

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FORM

@app.get("/panel-status")
async def pstatus():
    return {"ok": panel_online(), "url": PANEL_URL}

@app.post("/connect")
async def connect(ssid: str = Form(...), password: str = Form("")):
    try:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        subprocess.run(cmd, check=True)
        return JSONResponse({"ok": True, "msg": f"Conectado a {ssid}"})
    except subprocess.CalledProcessError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
