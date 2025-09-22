# -*- coding: utf-8 -*-
"""Mini servidor Flask para configurar la báscula desde la red local."""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import socket
import string
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    from flask import (
        Flask,
        jsonify,
        redirect,
        render_template_string,
        request,
        session,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback mínimo para tests sin Flask
    import json as _json
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlsplit

    class _Request(SimpleNamespace):
        def get_json(self, force: bool = False, silent: bool = False):
            if getattr(self, "json", None) is not None:
                return self.json
            if silent:
                return None
            raise ValueError("No JSON body")

    class _Response:
        def __init__(self, data="", status=200, headers=None, mimetype="text/html"):
            if isinstance(data, bytes):
                self.data = data
            else:
                self.data = str(data).encode("utf-8")
            self.status_code = status
            self.headers = headers or {}
            self.mimetype = mimetype

        def get_json(self):
            if not self.data:
                return None
            return _json.loads(self.data.decode("utf-8"))

    request = _Request(method="GET", remote_addr="127.0.0.1", json=None, args={})
    session: Dict[str, str] = {}

    def jsonify(*args, **kwargs):
        payload = args[0] if args else kwargs
        return _Response(_json.dumps(payload), status=200, mimetype="application/json")

    def redirect(location: str, code: int = 302):
        return _Response("", status=code, headers={"Location": location})

    def render_template_string(template: str, **context):
        return template

    class Flask:  # type: ignore
        def __init__(self, name: str):
            self.name = name
            self.secret_key: Optional[bytes] = None
            self.config: Dict[str, object] = {}
            self._routes: Dict[tuple[str, str], callable] = {}

        def route(self, rule: str, methods: Optional[Iterable[str]] = None):
            methods = list(methods or ["GET"])

            def decorator(func):
                for method in methods:
                    self._routes[(rule, method.upper())] = func
                return func

            return decorator

        def run(self, *_, **__):
            raise RuntimeError("Flask no disponible")

        def test_client(self):
            app = self

            class _Client:
                def __init__(self):
                    self.environ_base: Dict[str, str] = {}

                def open(self, path: str, method: str = "GET", json=None, data=None, headers=None):
                    url = urlsplit(path)
                    key = (url.path or "/", method.upper())
                    view = app._routes.get(key)
                    if view is None:
                        raise AssertionError(f"Ruta no encontrada: {path} [{method}]")
                    request.method = method.upper()
                    request.remote_addr = self.environ_base.get("REMOTE_ADDR", "127.0.0.1")
                    if json is not None:
                        request.json = json
                    else:
                        request.json = None
                    request.args = {k: v[-1] for k, v in parse_qs(url.query).items()}
                    request.form = data or {}
                    session.update(getattr(self, "_session", {}))
                    result = view()
                    if isinstance(result, tuple):
                        resp, status = result[0], result[1]
                        headers = result[2] if len(result) > 2 else None
                        if isinstance(resp, _Response):
                            resp.status_code = status
                            if headers:
                                resp.headers.update(headers)
                            final = resp
                        else:
                            final = _Response(resp, status=status, headers=headers)
                    elif isinstance(result, _Response):
                        final = result
                    else:
                        final = _Response(result)
                    self._session = dict(session)
                    return final

                def get(self, path: str, **kwargs):
                    return self.open(path, method="GET", **kwargs)

                def post(self, path: str, json=None, data=None, **kwargs):
                    return self.open(path, method="POST", json=json, data=data, **kwargs)

            return _Client()

        def __repr__(self):  # pragma: no cover - depuración básica
            return f"<FakeFlask {self.name}>"


from bascula.utils import load_config, save_config

# --- Configuración y rutas -------------------------------------------------

_port_value = os.getenv("BASCULA_MINIWEB_PORT") or os.getenv("BASCULA_WEB_PORT") or "8080"
try:
    APP_PORT = int(_port_value)
except (TypeError, ValueError):  # pragma: no cover - valores inesperados
    APP_PORT = 8080

_host_value = os.getenv("BASCULA_WEB_HOST", "0.0.0.0") or "0.0.0.0"
APP_HOST = _host_value.strip() or "0.0.0.0"

_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CFG_DIR = Path(_CFG_ENV) if _CFG_ENV else (Path.home() / ".config" / "bascula")
CFG_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(CFG_DIR, 0o700)
except Exception:  # pragma: no cover - chmod puede fallar
    pass

API_FILE = CFG_DIR / "apikey.json"
NS_FILE = CFG_DIR / "nightscout.json"
STATE_FILE = CFG_DIR / "miniweb.json"
SECRET_FILE = CFG_DIR / "web_secret.key"

# --- Gestión de estado persistente -----------------------------------------

_state_lock = threading.Lock()


def _read_state() -> Dict[str, str]:
    try:
        if STATE_FILE.is_file():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if isinstance(v, (str, int, float)) or v is None}
    except Exception:
        return {}
    return {}


def _write_state(data: Dict[str, str]) -> None:
    with _state_lock:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        STATE_FILE.write_text(payload, encoding="utf-8")
        try:
            os.chmod(STATE_FILE, 0o600)
        except Exception:  # pragma: no cover
            pass


_state = _read_state()

if SECRET_FILE.exists():
    app_secret = SECRET_FILE.read_bytes()
else:
    app_secret = os.urandom(32)
    SECRET_FILE.write_bytes(app_secret)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except Exception:  # pragma: no cover
        pass

PIN = _state.get("pin") if isinstance(_state.get("pin"), str) else ""
if not PIN:
    rng = secrets.SystemRandom()
    PIN = "".join(rng.choice(string.digits) for _ in range(6))
    _state["pin"] = PIN
    _write_state(_state)

app = Flask(__name__)
app.secret_key = app_secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE="Lax",
)

# --- Plantillas ------------------------------------------------------------

BASE_HTML = """<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Bascula · {{ title }}</title>
<style>
:root {
  color-scheme: dark;
  --bg: #050b1a;
  --bg-card: #0f172a;
  --accent: #2563eb;
  --accent-strong: #1d4ed8;
  --text: #e5e7eb;
  --muted: #64748b;
  --success: #34d399;
  --warn: #f59e0b;
  --error: #f87171;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
  background: radial-gradient(circle at top, rgba(37,99,235,0.15), transparent 55%), var(--bg);
  color: var(--text);
  min-height: 100vh;
}
header.top {
  background: rgba(15,23,42,0.85);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid rgba(148,163,184,0.15);
}
header .bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  flex-wrap: wrap;
  gap: 12px;
}
.brand {
  font-size: 18px;
  font-weight: 600;
}
nav a {
  color: var(--muted);
  text-decoration: none;
  margin-right: 16px;
  font-weight: 500;
  padding-bottom: 4px;
  border-bottom: 2px solid transparent;
}
nav a.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
nav a:last-child { margin-right: 0; }
.logout {
  margin-left: auto;
}
.logout button {
  background: transparent;
  border: 1px solid rgba(148,163,184,0.25);
  color: var(--muted);
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.container {
  width: min(920px, 92vw);
  margin: 28px auto 60px auto;
  display: grid;
  gap: 18px;
}
.card {
  background: var(--bg-card);
  padding: 18px;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgba(15,23,42,0.35);
}
.card h2, .card h3 { margin-top: 0; }
.field { margin-bottom: 14px; }
label { display: block; font-size: 14px; color: var(--muted); margin-bottom: 6px; }
input, select, textarea {
  width: 100%;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid rgba(148,163,184,0.15);
  background: rgba(15,23,42,0.75);
  color: var(--text);
}
textarea { resize: vertical; min-height: 80px; }
button.primary {
  background: linear-gradient(135deg, var(--accent), var(--accent-strong));
  border: none;
  color: white;
  padding: 11px 16px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
}
button.secondary {
  background: rgba(148,163,184,0.15);
  border: none;
  color: var(--text);
  padding: 10px 14px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 500;
}
button.linkish {
  background: transparent;
  color: var(--accent);
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 15px;
}
ul.list {
  list-style: none;
  margin: 12px 0 0 0;
  padding: 0;
}
ul.list li {
  padding: 10px 0;
  border-bottom: 1px solid rgba(148,163,184,0.12);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
ul.list li:last-child { border-bottom: none; }
.badge {
  background: rgba(37,99,235,0.15);
  color: var(--text);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
}
.status { margin-top: 10px; font-size: 14px; }
.status.ok { color: var(--success); }
.status.warn { color: var(--warn); }
.status.error { color: var(--error); }
.grid2 {
  display: grid;
  gap: 16px;
}
@media (min-width: 760px) {
  .grid2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.qr-img {
  width: 240px;
  height: 240px;
  margin-top: 12px;
  border-radius: 16px;
  background: white;
  padding: 10px;
}
small { color: var(--muted); }
</style>
</head>
<body>
<header class='top'>
  <div class='bar'>
    <div class='brand'>Bascula · Configuración</div>
    <nav>
      <a href='/wifi' class='{% if active == "wifi" %}active{% endif %}'>Wi‑Fi</a>
      <a href='/openai' class='{% if active == "openai" %}active{% endif %}'>OpenAI</a>
      <a href='/nightscout' class='{% if active == "nightscout" %}active{% endif %}'>Nightscout</a>
      <a href='/voice' class='{% if active == "voice" %}active{% endif %}'>Voz Piper</a>
      <a href='/info' class='{% if active == "info" %}active{% endif %}'>Info & PIN</a>
    </nav>
    <form class='logout' method='post' action='/logout'>
      <button>Salir</button>
    </form>
  </div>
</header>
<main class='container'>
  {{ body|safe }}
</main>
</body>
</html>"""

LOGIN_HTML = """<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Bascula · Acceso</title>
<style>
body {
  margin: 0;
  font-family: "Inter", "Segoe UI", system-ui, sans-serif;
  background: radial-gradient(circle at top, rgba(37,99,235,0.25), rgba(5,11,26,0.95));
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #e2e8f0;
}
.card {
  background: rgba(15,23,42,0.9);
  padding: 28px;
  border-radius: 18px;
  box-shadow: 0 24px 60px rgba(15,23,42,0.45);
  width: min(400px, 92vw);
}
h1 { margin-top: 0; }
label { display: block; margin-bottom: 6px; color: #94a3b8; }
input[type=password] {
  width: 100%;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(148,163,184,0.2);
  background: rgba(15,23,42,0.65);
  color: #e2e8f0;
}
button {
  margin-top: 16px;
  width: 100%;
  padding: 12px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: white;
  font-weight: 600;
  cursor: pointer;
}
.error { margin-top: 12px; color: #f87171; }
small { color: #94a3b8; }
</style>
</head>
<body>
<form class='card' method='post' action='/auth'>
  <h1>Bascula · Acceso</h1>
  <p><small>Introduce el PIN que aparece en la pantalla de la báscula.</small></p>
  <label>PIN</label>
  <input name='pin' type='password' autofocus required>
  <button type='submit'>Entrar</button>
  {% if error %}<div class='error'>{{ error }}</div>{% endif %}
</form>
</body>
</html>"""

# --- Helpers ----------------------------------------------------------------


def pin_ok() -> bool:
    return session.get("pin") == PIN


def ui_or_pin_ok() -> bool:
    try:
        remote_addr = request.remote_addr or ""
    except Exception:
        remote_addr = ""
    if remote_addr in ("127.0.0.1", "::1"):
        return True
    return pin_ok()


def require_login() -> Optional[None]:
    if not pin_ok():
        return redirect("/")
    return None


def render_page(body: str, *, active: str, title: str) -> str:
    return render_template_string(BASE_HTML, body=body, active=active, title=title)


def _norm_sec(value: str | None) -> str:
    s = (value or "").strip().lower()
    if not s or s in ("none", "open"):
        return "open"
    return s


@dataclass
class WifiNetwork:
    ssid: str
    signal: str = ""
    bssid: str | None = None
    channel: int | None = None
    freq: int | None = None
    rssi: int | None = None
    quality: int | None = None
    security: str | None = None
    known: bool = False

    def to_api(self) -> dict:
        sec = _norm_sec(self.security)
        return {
            "ssid": self.ssid,
            "signal": self.signal,
            "bssid": self.bssid,
            "chan": self.channel,
            "freq": self.freq,
            "rssi": self.rssi,
            "quality": self.quality,
            "sec": sec,
            "security": sec,
            "open": sec == "open",
            "known": bool(self.known),
        }


def _has(cmd: str) -> bool:
    return subprocess.call(["/usr/bin/env", "which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _nmcli_wifi_device() -> str:
    try:
        out = subprocess.check_output([
            "nmcli",
            "-t",
            "-f",
            "DEVICE,TYPE,STATE",
            "device",
            "status",
        ], text=True, timeout=5)
        for line in out.splitlines():
            parts = (line.split(":") + ["", ""])[:3]
            if len(parts) >= 2 and parts[1] == "wifi":
                return parts[0]
    except Exception:
        pass
    return "wlan0"


def _apply_wifi_nmcli(ssid: str, psk: str) -> tuple[int, str]:
    conn = "BasculaWiFi"
    dev = _nmcli_wifi_device()
    last_rc = 0
    last_err = ""

    def run(cmd: List[str], *, timeout: int = 15, ignore_rc: bool = False) -> int:
        nonlocal last_rc, last_err
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            last_rc = proc.returncode
            if proc.returncode != 0:
                last_err = (proc.stderr or proc.stdout or "").strip()
                if not ignore_rc:
                    return proc.returncode
            return proc.returncode
        except Exception as exc:  # pragma: no cover - errores raros
            last_rc = 1
            last_err = str(exc)
            return 1

    run(["nmcli", "radio", "wifi", "on"], ignore_rc=True)
    if dev:
        run(["nmcli", "device", "set", dev, "managed", "yes"], ignore_rc=True)

    run(["nmcli", "connection", "down", "BasculaAP"], ignore_rc=True)

    existing = subprocess.run([
        "nmcli",
        "-t",
        "-f",
        "NAME",
        "connection",
        "show",
    ], capture_output=True, text=True)
    has_conn = existing.returncode == 0 and any(line.strip() == conn for line in existing.stdout.splitlines())

    if not has_conn:
        rc = run(["nmcli", "connection", "add", "type", "wifi", "ifname", dev or "wlan0", "con-name", conn, "ssid", ssid])
        if rc != 0:
            return last_rc, last_err or "cannot add connection"
    else:
        run(["nmcli", "connection", "modify", conn, "802-11-wireless.ssid", ssid], ignore_rc=True)

    if psk:
        rc = run([
            "nmcli",
            "connection",
            "modify",
            conn,
            "802-11-wireless-security.key-mgmt",
            "wpa-psk",
            "802-11-wireless-security.psk",
            psk,
            "802-11-wireless-security.psk-flags",
            "0",
        ])
        if rc != 0:
            return last_rc, last_err or "cannot set psk"
    else:
        run(["nmcli", "connection", "modify", conn, "802-11-wireless-security.key-mgmt", "none"], ignore_rc=True)

    run([
        "nmcli",
        "connection",
        "modify",
        conn,
        "connection.autoconnect",
        "yes",
        "connection.autoconnect-priority",
        "10",
    ], ignore_rc=True)

    if dev:
        run(["nmcli", "device", "wifi", "rescan", "ifname", dev], ignore_rc=True)
        rc = run(["nmcli", "connection", "up", conn, "ifname", dev])
    else:
        rc = run(["nmcli", "connection", "up", conn])
    return last_rc, last_err


def _apply_wifi_wpa_cli(ssid: str, psk: str) -> tuple[int, str]:
    script = Path.home() / "bascula-cam" / "scripts" / "apply_wifi.sh"
    try:
        rc = subprocess.call(["sudo", str(script), ssid, psk])
    except Exception as exc:  # pragma: no cover - en tests no existe sudo
        return 1, str(exc)
    return rc, ""


def _forget_wifi_nmcli() -> tuple[bool, str]:
    try:
        proc = subprocess.run(["nmcli", "connection", "delete", "BasculaWiFi"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return True, ""
        if "Unknown connection" in (proc.stderr or ""):
            return True, ""
        return False, (proc.stderr or proc.stdout or "").strip()
    except Exception as exc:
        return False, str(exc)


def _saved_networks_nmcli() -> List[str]:
    try:
        proc = subprocess.run([
            "nmcli",
            "-t",
            "-f",
            "NAME,TYPE",
            "connection",
            "show",
        ], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            return []
        saved: List[str] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            name, _, conn_type = (line.split(":") + ["", ""])[:3]
            if conn_type == "wifi":
                saved.append(name)
        return saved
    except Exception:
        return []


def _scan_wifi_nmcli() -> List[WifiNetwork]:
    try:
        out = subprocess.check_output([
            "nmcli",
            "-t",
            "-f",
            "SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list",
        ], stderr=subprocess.STDOUT, text=True, timeout=10)
    except Exception:
        return []
    networks: List[WifiNetwork] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split(":")
        while len(parts) < 3:
            parts.append("")
        ssid, signal, security = parts[0], parts[1], parts[2]
        if not ssid:
            continue
        sig = signal or ""
        quality = None
        try:
            quality = int(sig)
        except (TypeError, ValueError):
            quality = None
        networks.append(
            WifiNetwork(
                ssid=ssid,
                signal=sig,
                quality=quality,
                security=security or None,
            )
        )
    return networks


def _list_ips() -> List[str]:
    ipv4: List[str] = []
    try:
        hostname = socket.gethostname()
        info = socket.getaddrinfo(hostname, None)
        for entry in info:
            addr = entry[4][0]
            if ":" in addr:
                continue
            if addr.startswith("127."):
                continue
            if addr not in ipv4:
                ipv4.append(addr)
    except Exception:
        pass
    if not ipv4:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            candidate = s.getsockname()[0]
            s.close()
            if candidate and candidate not in ipv4 and not candidate.startswith("127."):
                ipv4.append(candidate)
        except Exception:
            pass
    if not ipv4:
        ipv4.append("127.0.0.1")
    return ipv4


def _camera_health() -> Dict[str, str]:
    try:
        from picamera2 import Picamera2  # type: ignore

        if Picamera2 is None:  # pragma: no cover - dependencias dinámicas
            return {"ok": False, "detail": "picamera2 no disponible"}
        return {"ok": True, "detail": "Picamera2 importado"}
    except Exception as exc:
        return {"ok": False, "detail": f"{exc}"}


def _scale_health() -> Dict[str, str]:
    try:
        cfg = load_config()
        port = str(cfg.get("port") or "")
    except Exception:
        port = "/dev/serial0"
    path = Path(port)
    if path.exists():
        return {"ok": True, "detail": f"Puerto {port} accesible"}
    return {"ok": False, "detail": f"Puerto {port} no encontrado"}


def _network_health() -> Dict[str, str]:
    ips = _list_ips()
    if any(ip and not ip.startswith("127.") for ip in ips):
        return {"ok": True, "detail": ", ".join(ips)}
    return {"ok": False, "detail": "Solo loopback"}


def _load_voice_state() -> Dict[str, str]:
    state = dict(_state)
    model = state.get("piper_model", "")
    return {"piper_model": model}


def _update_state(**kwargs: str) -> None:
    global PIN
    state = dict(_state)
    state.update({k: v for k, v in kwargs.items() if v is None or isinstance(v, str)})
    _state.clear()
    _state.update(state)
    if "pin" in kwargs and isinstance(kwargs["pin"], str):
        PIN = kwargs["pin"]
        session["pin"] = PIN
    _write_state(_state)


def _voice_directories() -> Iterable[Path]:
    paths = [
        CFG_DIR,
        CFG_DIR / "voices",
        Path.home() / ".local/share/piper",
        Path.home() / "piper",
        Path("/opt/piper/models"),
        Path("/usr/share/piper/voices"),
    ]
    for path in paths:
        try:
            if path.exists():
                yield path
        except Exception:  # pragma: no cover - rutas inválidas
            continue


def _list_piper_models() -> List[Dict[str, str]]:
    seen: set[str] = set()
    voices: List[Dict[str, str]] = []
    for base in _voice_directories():
        try:
            for file in base.rglob("*.onnx"):
                key = str(file.resolve())
                if key in seen:
                    continue
                seen.add(key)
                voices.append({
                    "path": key,
                    "name": file.stem.replace("_", " "),
                    "folder": str(file.parent),
                })
        except Exception:
            continue
    voices.sort(key=lambda item: item["name"].lower())
    return voices


# --- Rutas HTML -------------------------------------------------------------


@app.route("/", methods=["GET"])
def index():
    if pin_ok():
        return redirect("/wifi")
    return render_template_string(LOGIN_HTML)


@app.route("/auth", methods=["POST"])
def auth():
    pin = (request.form.get("pin") or "").strip()
    if pin and secrets.compare_digest(pin, PIN):
        session["pin"] = pin
        return redirect("/wifi")
    try:
        import time

        time.sleep(0.8)
    except Exception:  # pragma: no cover - suspensión opcional
        pass
    return render_template_string(LOGIN_HTML, error="PIN incorrecto")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")


WIFI_PAGE = """
<div class='grid2'>
  <section class='card'>
    <h2>Conectar a Wi‑Fi</h2>
    <div class='field'>
      <label>SSID</label>
      <input id='wifi-ssid' placeholder='MiRed'>
    </div>
    <div class='field'>
      <label>Contraseña</label>
      <input id='wifi-psk' type='password' placeholder='·······'>
    </div>
    <div class='field'>
      <button class='primary' type='button' onclick='connectWifi()'>Conectar</button>
      <button class='secondary' type='button' onclick='forgetWifi()' style='margin-left:12px'>Olvidar</button>
    </div>
    <div id='wifi-status' class='status'></div>
  </section>
  <section class='card'>
    <h2>Redes disponibles</h2>
    <button class='secondary' type='button' onclick='scanWifi()'>Buscar redes</button>
    <ul id='wifi-list' class='list'></ul>
  </section>
</div>
<section class='card'>
  <h3>Redes guardadas</h3>
  <ul id='wifi-saved' class='list'></ul>
</section>
<script>
async function connectWifi(){
  const ssid = document.getElementById('wifi-ssid').value.trim();
  const psk = document.getElementById('wifi-psk').value;
  if(!ssid){ showWifiStatus('Indica un SSID', 'warn'); return; }
  const body = {ssid, psk};
  const resp = await fetch('/api/wifi/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const data = await resp.json();
  if(data.ok){ showWifiStatus('Wi-Fi configurado', 'ok'); loadSaved(); }
  else { showWifiStatus(data.error || 'No se pudo conectar', 'error'); }
}
async function forgetWifi(){
  const resp = await fetch('/api/wifi/forget', {method:'POST'});
  const data = await resp.json();
  if(data.ok){ showWifiStatus('Configuración eliminada', 'ok'); loadSaved(); }
  else { showWifiStatus(data.error || 'No se pudo eliminar', 'error'); }
}
function showWifiStatus(text, cls){
  const el = document.getElementById('wifi-status');
  el.className = 'status ' + (cls||'');
  el.textContent = text;
}
async function scanWifi(){
  const list = document.getElementById('wifi-list');
  list.innerHTML = '<li>Buscando redes...</li>';
  try {
    const resp = await fetch('/api/wifi/scan');
    const data = await resp.json();
    list.innerHTML = '';
    if(!data.ok){ list.innerHTML = '<li>No disponible</li>'; return; }
    if(!data.nets.length){ list.innerHTML = '<li>Sin redes detectadas</li>'; return; }
    for(const net of data.nets){
      const li = document.createElement('li');
      const left = document.createElement('div');
      left.innerHTML = `<strong>${net.ssid}</strong><br><small>${net.signal || ''} ${net.sec || ''}</small>`;
      const btn = document.createElement('button');
      btn.className = 'linkish';
      btn.type = 'button';
      btn.textContent = 'Usar';
      btn.onclick = () => {
        document.getElementById('wifi-ssid').value = net.ssid;
        if(net.sec && net.sec.toLowerCase().includes('wep') || net.sec.toLowerCase().includes('wpa')){
          document.getElementById('wifi-psk').focus();
        }
      };
      li.append(left, btn);
      list.appendChild(li);
    }
  } catch(e){
    list.innerHTML = '<li>Error al escanear</li>';
  }
}
async function loadSaved(){
  try {
    const resp = await fetch('/api/wifi/saved');
    const data = await resp.json();
    const list = document.getElementById('wifi-saved');
    list.innerHTML = '';
    if(!data.ok){ list.innerHTML = '<li>No disponible</li>'; return; }
    if(!data.networks.length){ list.innerHTML = '<li>Sin redes guardadas</li>'; return; }
    for(const name of data.networks){
      const li = document.createElement('li');
      li.innerHTML = `<div><strong>${name}</strong></div>`;
      list.appendChild(li);
    }
  } catch(e){
    const list = document.getElementById('wifi-saved');
    list.innerHTML = '<li>Error al cargar</li>';
  }
}
scanWifi();
loadSaved();
</script>
"""


@app.route("/wifi", methods=["GET"])
def wifi_page():
    response = require_login()
    if response:
        return response
    return render_page(WIFI_PAGE, active="wifi", title="Wi‑Fi")


OPENAI_PAGE = """
<section class='card'>
  <h2>Clave OpenAI</h2>
  <p>Introduce tu clave <code>sk-...</code> para habilitar el asistente.</p>
  <div class='field'>
    <label>API key</label>
    <input id='api-key' type='password' placeholder='sk-...'>
  </div>
  <div class='field'>
    <button class='primary' type='button' onclick='saveKey()'>Guardar</button>
    <button class='secondary' type='button' onclick='checkKey()' style='margin-left:12px'>Comprobar</button>
  </div>
  <div id='api-status' class='status'></div>
</section>
<script>
async function saveKey(){
  const key = document.getElementById('api-key').value.trim();
  if(!key){ setStatus('api-status', 'Introduce una clave', 'warn'); return; }
  const resp = await fetch('/api/apikey', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key})});
  const data = await resp.json();
  if(data.ok){ setStatus('api-status', 'Clave guardada', 'ok'); }
  else { setStatus('api-status', data.error || 'Error al guardar', 'error'); }
}
async function checkKey(){
  const resp = await fetch('/api/apikey_status');
  const data = await resp.json();
  if(data.ok){
    setStatus('api-status', data.present ? 'Clave presente' : 'No configurada', data.present ? 'ok' : 'warn');
  } else {
    setStatus('api-status', data.error || 'Error', 'error');
  }
}
function setStatus(id, text, cls){
  const el = document.getElementById(id);
  el.className = 'status ' + (cls||'');
  el.textContent = text;
}
checkKey();
</script>
"""


@app.route("/openai", methods=["GET"])
def openai_page():
    response = require_login()
    if response:
        return response
    return render_page(OPENAI_PAGE, active="openai", title="OpenAI")


NIGHTSCOUT_PAGE = """
<section class='card'>
  <h2>Nightscout</h2>
  <p>Configura la URL y el token opcional para sincronizar.</p>
  <div class='grid2'>
    <div class='field'>
      <label>URL</label>
      <input id='ns-url' placeholder='https://mi-nightscout.example.com'>
    </div>
    <div class='field'>
      <label>Token (opcional)</label>
      <input id='ns-token' type='password'>
    </div>
  </div>
  <div class='field'>
    <button class='primary' type='button' onclick='saveNS()'>Guardar</button>
    <button class='secondary' type='button' style='margin-left:12px' onclick='testNS()'>Probar</button>
  </div>
  <div id='ns-status' class='status'></div>
</section>
<script>
async function loadNS(){
  const resp = await fetch('/api/nightscout');
  const data = await resp.json();
  if(data.ok && data.data){
    document.getElementById('ns-url').value = data.data.url || '';
    document.getElementById('ns-token').value = data.data.token || '';
  }
}
async function saveNS(){
  const url = document.getElementById('ns-url').value.trim();
  const token = document.getElementById('ns-token').value.trim();
  const resp = await fetch('/api/nightscout', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, token})});
  const data = await resp.json();
  if(data.ok){ setStatus('ns-status', 'Guardado', 'ok'); }
  else { setStatus('ns-status', data.error || 'Error', 'error'); }
}
async function testNS(){
  setStatus('ns-status', 'Probando...', '');
  const url = document.getElementById('ns-url').value.trim();
  const token = document.getElementById('ns-token').value.trim();
  if(!url){ setStatus('ns-status', 'Falta URL', 'warn'); return; }
  try {
    const resp = await fetch('/api/nightscout_test', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, token})});
    const data = await resp.json();
    if(data.ok){ setStatus('ns-status', 'Nightscout responde', 'ok'); }
    else { setStatus('ns-status', data.error || 'Fallo', 'warn'); }
  } catch(e){ setStatus('ns-status', 'Error de conexión', 'error'); }
}
function setStatus(id, text, cls){
  const el = document.getElementById(id);
  el.className = 'status ' + (cls||'');
  el.textContent = text;
}
loadNS();
</script>
"""


@app.route("/nightscout", methods=["GET"])
def nightscout_page():
    response = require_login()
    if response:
        return response
    return render_page(NIGHTSCOUT_PAGE, active="nightscout", title="Nightscout")


VOICE_PAGE = """
<section class='card'>
  <h2>Voz Piper</h2>
  <p>Selecciona el modelo de voz disponible en el sistema.</p>
  <div class='field'>
    <label>Modelo</label>
    <select id='voice-select'></select>
  </div>
  <div class='field'>
    <button class='primary' type='button' onclick='saveVoice()'>Guardar selección</button>
  </div>
  <div id='voice-status' class='status'></div>
</section>
<script>
async function loadVoices(){
  const resp = await fetch('/api/voice/voices');
  const data = await resp.json();
  const select = document.getElementById('voice-select');
  select.innerHTML = '';
  if(!data.ok){
    const opt = document.createElement('option');
    opt.textContent = 'No disponible';
    opt.value = '';
    select.appendChild(opt);
    setStatus('voice-status', data.error || 'Sin voces', 'warn');
    return;
  }
  for(const voice of data.voices){
    const opt = document.createElement('option');
    opt.value = voice.path;
    opt.textContent = `${voice.name} (${voice.folder})`;
    if(voice.selected){ opt.selected = true; }
    select.appendChild(opt);
  }
  if(data.voices.length === 0){
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No se encontraron modelos';
    select.appendChild(opt);
  }
}
async function saveVoice(){
  const select = document.getElementById('voice-select');
  const model = select.value;
  const resp = await fetch('/api/voice/select', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({model})});
  const data = await resp.json();
  if(data.ok){ setStatus('voice-status', 'Voz guardada', 'ok'); }
  else { setStatus('voice-status', data.error || 'Error', 'error'); }
}
function setStatus(id, text, cls){
  const el = document.getElementById(id);
  el.className = 'status ' + (cls||'');
  el.textContent = text;
}
loadVoices();
</script>
"""


@app.route("/voice", methods=["GET"])
def voice_page():
    response = require_login()
    if response:
        return response
    return render_page(VOICE_PAGE, active="voice", title="Voz Piper")


INFO_PAGE = """
<section class='card'>
  <h2>Información de acceso</h2>
  <p>Comparte la dirección con tu móvil o escanea el QR.</p>
  <div id='info-block'></div>
  <div class='field'>
    <button class='secondary' type='button' onclick='loadQR()'>Generar QR</button>
  </div>
  <img id='qr-image' class='qr-img' alt='QR de acceso' style='display:none;'>
  <div id='info-status' class='status'></div>
</section>
<section class='card'>
  <h3>Cambiar PIN</h3>
  <div class='grid2'>
    <div class='field'>
      <label>Nuevo PIN (6 dígitos)</label>
      <input id='pin-new' maxlength='6' placeholder='123456'>
    </div>
    <div class='field'>
      <label>Confirmar PIN</label>
      <input id='pin-confirm' maxlength='6' placeholder='123456'>
    </div>
  </div>
  <div class='field'>
    <button class='primary' type='button' onclick='changePin()'>Actualizar PIN</button>
  </div>
  <div id='pin-status' class='status'></div>
</section>
<script>
let currentInfo = null;
async function loadInfo(){
  const block = document.getElementById('info-block');
  block.innerHTML = '<p>Cargando...</p>';
  try {
    const resp = await fetch('/api/info');
    const data = await resp.json();
    if(!data.ok){ block.innerHTML = '<p>No disponible</p>'; return; }
    currentInfo = data;
    const list = document.createElement('ul');
    list.className = 'list';
    list.innerHTML = '';
    const pin = document.createElement('li');
    pin.innerHTML = `<div><strong>PIN actual</strong><br><small>${data.pin}</small></div>`;
    list.appendChild(pin);
    const port = document.createElement('li');
    port.innerHTML = `<div><strong>Puerto</strong><br><small>${data.port}</small></div>`;
    list.appendChild(port);
    const ips = document.createElement('li');
    ips.innerHTML = `<div><strong>IPs</strong><br><small>${data.ips.join(', ')}</small></div>`;
    list.appendChild(ips);
    block.innerHTML = '';
    block.appendChild(list);
  } catch(e){
    block.innerHTML = '<p>Error de conexión</p>';
  }
}
async function loadQR(){
  if(!currentInfo || !currentInfo.ips.length){ return; }
  const ip = currentInfo.ips[0];
  const resp = await fetch(`/api/info/qr?ip=${encodeURIComponent(ip)}`);
  const data = await resp.json();
  if(data.ok){
    const img = document.getElementById('qr-image');
    img.src = data.image;
    img.style.display = 'block';
    setStatus('info-status', `QR listo (${data.url})`, 'ok');
  } else {
    setStatus('info-status', data.error || 'No se pudo generar QR', 'error');
  }
}
async function changePin(){
  const pin = document.getElementById('pin-new').value.trim();
  const confirm = document.getElementById('pin-confirm').value.trim();
  if(pin.length !== 6 || !/^[0-9]{6}$/.test(pin)){ setStatus('pin-status', 'El PIN debe tener 6 dígitos', 'warn'); return; }
  if(pin !== confirm){ setStatus('pin-status', 'Los PIN no coinciden', 'warn'); return; }
  const resp = await fetch('/api/pin', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pin})});
  const data = await resp.json();
  if(data.ok){ setStatus('pin-status', 'PIN actualizado', 'ok'); loadInfo(); }
  else { setStatus('pin-status', data.error || 'No se pudo actualizar', 'error'); }
}
function setStatus(id, text, cls){
  const el = document.getElementById(id);
  el.className = 'status ' + (cls||'');
  el.textContent = text;
}
loadInfo();
</script>
"""


@app.route("/info", methods=["GET"])
def info_page():
    response = require_login()
    if response:
        return response
    return render_page(INFO_PAGE, active="info", title="Información")


# --- API --------------------------------------------------------------------


@app.route("/api/status", methods=["GET"])
def status():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    return jsonify({"ok": True, "api_key_present": API_FILE.exists()})


@app.route("/api/apikey_status", methods=["GET"])
def apikey_status():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    try:
        present = API_FILE.exists()
        key = ""
        if present:
            try:
                data = json.loads(API_FILE.read_text(encoding="utf-8"))
                key = str(data.get("openai_api_key", "")).strip()
            except Exception:
                key = ""
        valid = bool(key and key.startswith("sk-") and len(key) > 20)
        return jsonify({"ok": True, "present": present, "valid": valid})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/apikey", methods=["POST"])
def set_apikey():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    key = str(data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "missing"}), 400
    API_FILE.write_text(json.dumps({"openai_api_key": key}), encoding="utf-8")
    try:
        os.chmod(API_FILE, 0o600)
    except Exception:  # pragma: no cover
        pass
    return jsonify({"ok": True})


@app.route("/api/wifi", methods=["POST"])
def legacy_wifi():  # Compatibilidad hacia atrás
    return set_wifi()


@app.route("/api/wifi/connect", methods=["POST"])
def set_wifi():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    ssid = str(payload.get("ssid") or "").strip()
    psk = str(payload.get("psk") or "").strip()
    if not ssid:
        return jsonify({"ok": False, "error": "missing"}), 400
    if _has("nmcli"):
        rc, err = _apply_wifi_nmcli(ssid, psk)
    else:
        rc, err = _apply_wifi_wpa_cli(ssid, psk)
    if rc == 0:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": err or f"rc={rc}"})


@app.route("/api/wifi/forget", methods=["POST"])
def wifi_forget():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    if _has("nmcli"):
        ok, err = _forget_wifi_nmcli()
        if ok:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": err or "nmcli"}), 500
    return jsonify({"ok": False, "error": "unsupported"}), 400


@app.route("/api/wifi/saved", methods=["GET"])
def wifi_saved():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    if _has("nmcli"):
        networks = _saved_networks_nmcli()
        return jsonify({"ok": True, "networks": networks})
    return jsonify({"ok": True, "networks": []})


@app.route("/api/wifi/scan", methods=["GET"])
def wifi_scan():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    if not _has("nmcli"):
        return jsonify({"ok": False, "error": "nmcli_unavailable"}), 400
    nets = _scan_wifi_nmcli()
    saved = set(_saved_networks_nmcli()) if nets else set()
    items = []
    for net in nets:
        if net.ssid in saved:
            net.known = True
        items.append(net.to_api())
    return jsonify({"ok": True, "nets": items})


@app.route("/api/bolus", methods=["GET", "POST"])
def bolus_cfg():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    if request.method == "GET":
        try:
            cfg = load_config()
            return jsonify({
                "ok": True,
                "data": {
                    "tbg": int(cfg.get("target_bg_mgdl", 110) or 0),
                    "isf": int(cfg.get("isf_mgdl_per_u", 50) or 0),
                    "carb": int(cfg.get("carb_ratio_g_per_u", 10) or 0),
                    "dia": int(cfg.get("dia_hours", 4) or 0),
                },
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
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
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/nightscout", methods=["GET", "POST"])
def nightscout_cfg():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    if request.method == "GET":
        try:
            if NS_FILE.exists():
                data = json.loads(NS_FILE.read_text(encoding="utf-8"))
            else:
                data = {}
            return jsonify({"ok": True, "data": data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
    payload = request.get_json(force=True, silent=True) or {}
    url = str(payload.get("url") or "").strip()
    token = str(payload.get("token") or "").strip()
    try:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        NS_FILE.write_text(json.dumps({"url": url, "token": token}), encoding="utf-8")
        try:
            os.chmod(NS_FILE, 0o600)
        except Exception:  # pragma: no cover
            pass
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/nightscout_test", methods=["POST"])
def nightscout_test():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get("url") or "").strip().rstrip("/")
    token = str(data.get("token") or "").strip()
    if not url:
        try:
            if NS_FILE.exists():
                stored = json.loads(NS_FILE.read_text(encoding="utf-8"))
                url = str(stored.get("url") or "").strip().rstrip("/")
                token = token or str(stored.get("token") or "").strip()
        except Exception:
            pass
    if not url:
        return jsonify({"ok": False, "error": "missing_url"}), 400
    try:
        import requests as rq

        resp = rq.get(f"{url}/api/v1/status.json", params={"token": token} if token else None, timeout=6)
        if resp.ok:
            try:
                payload = resp.json()
            except Exception:
                payload = {}
            return jsonify({"ok": True, "http": resp.status_code, "data": {"apiEnabled": payload.get("apiEnabled", True)}})
        return jsonify({"ok": False, "error": f"http_{resp.status_code}"}), 502
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/voice/voices", methods=["GET"])
def voice_list():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    voices = _list_piper_models()
    state = _load_voice_state()
    selected = state.get("piper_model")
    for item in voices:
        item["selected"] = selected and item["path"] == selected
    return jsonify({"ok": True, "voices": voices})


@app.route("/api/voice/select", methods=["POST"])
def voice_select():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    model = str(payload.get("model") or "").strip()
    if model and not Path(model).exists():
        return jsonify({"ok": False, "error": "not_found"}), 404
    _update_state(piper_model=model)
    return jsonify({"ok": True})


@app.route("/api/pin", methods=["POST"])
def change_pin():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    pin = str(payload.get("pin") or "").strip()
    if len(pin) != 6 or not pin.isdigit():
        return jsonify({"ok": False, "error": "invalid"}), 400
    _update_state(pin=pin)
    return jsonify({"ok": True})


@app.route("/api/info", methods=["GET"])
def info_data():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    return jsonify({
        "ok": True,
        "pin": PIN,
        "port": APP_PORT,
        "ips": _list_ips(),
    })


@app.route("/api/info/qr", methods=["GET"])
def info_qr():
    if not ui_or_pin_ok():
        return jsonify({"ok": False, "error": "auth"}), 401
    ip = request.args.get("ip", "127.0.0.1")
    if not ip:
        return jsonify({"ok": False, "error": "invalid_ip"}), 400
    url = f"http://{ip}:{APP_PORT}"
    try:
        import qrcode

        img = qrcode.make(url)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return jsonify({"ok": True, "image": f"data:image/png;base64,{encoded}", "url": url})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "camera": _camera_health(),
        "scale": _scale_health(),
        "network": _network_health(),
    })


def main() -> None:
    app.run(host=APP_HOST, port=APP_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
