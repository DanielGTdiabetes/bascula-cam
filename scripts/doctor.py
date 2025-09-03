#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bascula Doctor — comprobaciones de entorno (Raspberry Pi)
Valida:
- Python >= 3.9, tkinter
- nmcli disponible y NetworkManager activo
- Regla polkit para NetworkManager (si existe)
- Servicio mini-web (systemd) activo y HTTP responde
- Dispositivo serie presente y pyserial instalado
- Picamera2 instalable (opcional)
"""
from __future__ import annotations
import os, sys, json, shutil, socket, subprocess, time


def _run(cmd: list[str], timeout=5) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:
        return 127, "", str(e)


class Result:
    def __init__(self, name: str, ok: bool, info: str = ""):
        self.name = name
        self.ok = bool(ok)
        self.info = info

    def line(self) -> str:
        mark = "✔" if self.ok else "✗"
        return f"{mark} {self.name}: {self.info}".rstrip()


def check_python() -> Result:
    ver = sys.version.split(" ")[0]
    ok = sys.version_info >= (3, 9)
    try:
        import tkinter  # noqa: F401
        tk = "tkinter OK"
    except Exception as e:
        tk = f"tkinter faltante ({e})"
        ok = False
    return Result("Python", ok, f"{ver}; {tk}")


def check_nmcli() -> Result:
    path = shutil.which("nmcli")
    if not path:
        return Result("nmcli", False, "no encontrado (instala NetworkManager)")
    rc, out, err = _run(["nmcli", "dev", "status"])  # lista dispositivos
    ok = (rc == 0)
    return Result("nmcli", ok, "ok" if ok else err or "error ejecutando nmcli")


def check_nm_service() -> Result:
    rc, out, _ = _run(["systemctl", "is-active", "NetworkManager"])
    ok = (rc == 0 and out == "active")
    return Result("NetworkManager", ok, out or "inactivo")


def check_polkit_rule() -> Result:
    path = "/etc/polkit-1/rules.d/50-bascula-nm.rules"
    # Primero, comprobar si los directorios son accesibles por el usuario.
    # Si no lo son, os.path.exists() devolverá False aunque el archivo exista.
    for d in ("/etc/polkit-1", "/etc/polkit-1/rules.d"):
        try:
            # Intentar listar para detectar permisos de ejecución/lectura insuficientes
            os.listdir(d)
        except PermissionError:
            fix = "sudo chmod 755 /etc/polkit-1 /etc/polkit-1/rules.d"
            return Result(
                "polkit NM",
                False,
                f"sin permisos para acceder a {d} (sugerido: {fix})",
            )
        except FileNotFoundError:
            # Directorio ausente; dejar que el check normal informe "no encontrada"
            break
        except Exception:
            # Ignorar otros errores y continuar con la comprobación estándar
            pass

    if os.path.exists(path):
        try:
            sz = os.path.getsize(path)
            return Result("polkit NM", True, f"{path} ({sz} bytes)")
        except Exception:
            return Result("polkit NM", True, f"{path}")
    return Result("polkit NM", False, "regla no encontrada (make install-polkit)")


def check_miniweb_service() -> Result:
    rc, out, _ = _run(["systemctl", "is-active", "bascula-web.service"])
    ok = (rc == 0 and out == "active")
    return Result("mini-web (systemd)", ok, out or "inactivo")


def check_miniweb_http() -> Result:
    try:
        import requests  # noqa: F401
    except Exception:
        # Fallback a socket + HTTP simple
        try:
            with socket.create_connection(("127.0.0.1", 8080), timeout=1.5) as s:
                s.sendall(b"GET /api/status HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
                data = s.recv(4096).decode(errors="ignore")
                ok = ("200" in data and "{" in data)
                return Result("mini-web (HTTP)", ok, "ok" if ok else "sin respuesta válida")
        except Exception as e:
            return Result("mini-web (HTTP)", False, str(e))
    # Con requests
    try:
        import requests
        r = requests.get("http://127.0.0.1:8080/api/status", timeout=2)
        ok = (r.ok and isinstance(r.json(), dict))
        return Result("mini-web (HTTP)", ok, f"{r.status_code}")
    except Exception as e:
        return Result("mini-web (HTTP)", False, str(e))


def check_serial() -> Result:
    devs = ["/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0", "/dev/ttyUSB0"]
    found = [d for d in devs if os.path.exists(d)]
    if not found:
        return Result("Serial device", False, "no encontrado /dev/serial0 (habilita UART)")
    return Result("Serial device", True, ", ".join(found))


def check_pyserial() -> Result:
    try:
        import serial  # noqa: F401
        return Result("pyserial", True, "ok")
    except Exception as e:
        return Result("pyserial", False, str(e))


def check_picamera2() -> Result:
    try:
        import picamera2  # noqa: F401
        return Result("picamera2", True, "ok")
    except Exception as e:
        return Result("picamera2", False, str(e))


def main() -> int:
    checks = [
        check_python,
        check_nmcli,
        check_nm_service,
        check_polkit_rule,
        check_miniweb_service,
        check_miniweb_http,
        check_serial,
        check_pyserial,
        check_picamera2,
    ]
    results: list[Result] = []
    print("== Bascula Doctor ==")
    for fn in checks:
        try:
            res = fn()
        except Exception as e:
            res = Result(fn.__name__, False, f"excepción: {e}")
        results.append(res)
        print(res.line())
    ok_all = all(r.ok for r in results if r.name not in ("picamera2",))
    # picamera2 es opcional; no bloquea ok_all
    print("\nResumen:")
    print(f"OK: {sum(1 for r in results if r.ok)} / {len(results)} (picamera2 es opcional)")
    if not ok_all:
        print("Consejos:")
        print("- 'make install-polkit' y 'make restart-nm' si nmcli falla por permisos")
        print("- 'make install-web' para instalar el mini-web y verificar HTTP")
        print("- Habilita UART: enable_uart=1 y sin console=serial0 en cmdline.txt")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())

