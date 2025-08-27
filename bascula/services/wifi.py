import subprocess

def connect_wifi(ssid: str, password: str) -> bool:
    if not ssid:
        return False
    try:
        subprocess.run(["nmcli","c","delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        r = subprocess.run(["nmcli","dev","wifi","connect", ssid, "password", password], capture_output=True, text=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False
