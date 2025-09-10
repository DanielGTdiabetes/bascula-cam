from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess

app = FastAPI(title="Bascula WiFi Config", version="1.0")

HTML_FORM = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Configurar WiFi</title></head><body style="font-family:sans-serif;max-width:520px;margin:2rem auto;"><h2>Configurar WiFi</h2><form method="post" action="/connect"><label>SSID:<br><input type="text" name="ssid" required></label><br><br><label>Contraseña:<br><input type="password" name="password"></label><br><br><button type="submit">Conectar</button></form><p style="color:#555">La báscula intentará conectar con la red indicada. Si funciona, el punto de acceso se apagará automáticamente en el próximo reinicio.</p></body></html>'

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FORM

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
