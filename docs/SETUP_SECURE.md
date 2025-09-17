# Puesta en marcha segura: Mini-web + UI (sin LightDM)

Este documento resume cómo desplegar la UI y el mini‑web de configuración (Wi‑Fi, API Key, Nightscout) de forma segura en la báscula, usando arranque con `.xinitrc` (sin LightDM ni Openbox).

## 1) Requisitos del sistema
- NetworkManager con `nmcli` (gestión Wi‑Fi)
- Python 3.9+ con `pip`
- Dependencias Python del proyecto: `pip install -r requirements.txt`

## 2) Usuario dedicado
Crea un usuario sin privilegios para ejecutar todo:

```
sudo adduser --disabled-password --gecos "Bascula" bascula
sudo usermod -aG tty,dialout,video,gpio bascula
```

Coloca el repositorio en `~bascula/bascula-cam` y ajusta su propiedad:

```
sudo rsync -a --delete ./ /home/bascula/bascula-cam/
sudo chown -R bascula:bascula /home/bascula/bascula-cam
```

## 3) Permisos mínimos para Wi‑Fi (polkit)
Permite que el usuario `bascula` conecte redes Wi‑Fi vía NetworkManager sin `sudo`.
Sigue: `docs/polkit-networkmanager.md:1`

## 4) Servicio mini‑web (solo localhost)
Instala el servicio que expone la API en `127.0.0.1:8080`:

```
sudo cp systemd/bascula-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bascula-web.service
```

- Ver estado: `journalctl -u bascula-web.service -f`
- El servicio lee/escribe `~/.config/bascula` con permisos estrictos (700/600).

## 5) UI con `.xinitrc`
- Sigue la guía: `docs/SETUP_XINITRC.md:1` (autologin a tty1 + startx + `.xinitrc`).
- Desactiva gestores gráficos alternativos si existían (por ejemplo LightDM):
  - `sudo systemctl disable --now lightdm || true`

Requisitos:
- Paquetes X mínimos: `xserver-xorg`, `xinit`, `python3-tk`
- Dispositivo serie accesible (`/dev/serial0`)

Notas:
- La UI usa el mini‑web en `http://127.0.0.1:8080` si está activo; si no, hace fallback a `nmcli`/ficheros locales.

## 6) Comprobaciones rápidas
- Mini‑web local:
  - `curl http://127.0.0.1:8080/api/status` → `{"ok": true, ...}`
  - `curl http://127.0.0.1:8080/api/wifi_scan` → lista redes (requiere `nmcli`)
- UI:
  - Ajustes → Wi‑Fi: lista redes y conecta.
  - Ajustes → API Key: guarda en `~/.config/bascula/apikey.json` (o vía API local).
  - Ajustes → Nightscout: guarda `~/.config/bascula/nightscout.json`.

## 7) Seguridad (resumen)
- Mini‑web ligado a `127.0.0.1` (no expone en LAN).
- Peticiones sin PIN solo desde loopback; resto requiere sesión con PIN.
- Cookies de sesión `HttpOnly`, `SameSite=Lax`.
- Ficheros sensibles con permisos 600; directorio de config con 700.
- Servicio systemd con aislamiento (`NoNewPrivileges`, `ProtectSystem`, `IPAddressAllow=127.0.0.1`).

## 8) Resolución de problemas
- Logs: `journalctl -u bascula-web.service -f`
- `nmcli`: `nmcli dev status`, `nmcli radio wifi on`
- Polkit: si `nmcli` falla, revisa `docs/polkit-networkmanager.md:1`
- Puertos: `ss -ltnp | grep :8080` debe mostrar `127.0.0.1:8080`
- Python deps: `pip install -r requirements.txt`

## 9) Desarrollo / pruebas sin systemd
- Mini‑web: `sudo -u bascula -H bash -lc 'cd ~/bascula-cam && python3 -m bascula.services.wifi_config'`
- UI: `cd ~/bascula-cam && ./scripts/run-ui.sh`

