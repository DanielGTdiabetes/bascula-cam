# Puesta en marcha segura: Mini‑web + UI

Este documento resume cómo desplegar la UI y el mini‑web de configuración (Wi‑Fi, API Key, Nightscout) de forma segura en la báscula.

## 1) Requisitos del sistema
- NetworkManager con `nmcli` (gestión Wi‑Fi)
- Python 3.9+ con `pip`
- Paquetes Python del proyecto: `pip install -r requirements.txt`

## 2) Usuario dedicado
Crea un usuario sin privilegios para ejecutar todo:

```
sudo adduser --disabled-password --gecos "Bascula" bascula
sudo usermod -a -G bascula bascula
```

Coloca el repositorio en `~bascula/bascula-cam` y ajusta su propiedad:

```
sudo rsync -a --delete ./ /home/bascula/bascula-cam/
sudo chown -R bascula:bascula /home/bascula/bascula-cam
```

## 3) Permisos mínimos para Wi‑Fi (polkit)
Permite que el usuario `bascula` pueda conectar redes Wi‑Fi vía NetworkManager sin `sudo`.
Sigue: `docs/polkit-networkmanager.md:1`

## 4) Servicio mini‑web (solo localhost)
Instala el servicio que expone la API en `127.0.0.1:8080`:

```
sudo cp systemd/bascula-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bascula-web.service
```

- Ver estado: `journalctl -u bascula-web.service -f`
- El servicio escribe/lee en `~/.config/bascula` con permisos estrictos (700/600).

## 5) UI (pantalla táctil)
Desactiva el servicio legacy (si existía) y configura autologin gráfico:

```
sudo systemctl disable --now bascula.service || true
```

Instala LightDM + Xorg y habilita autologin del usuario `bascula`:

```
sudo apt-get update
sudo apt-get install -y lightdm xserver-xorg lightdm-gtk-greeter
echo -e "[Seat:*]\nautologin-user=bascula\nautologin-user-timeout=0\nuser-session=lightdm-autologin\n" | sudo tee /etc/lightdm/lightdm.conf.d/50-bascula-autologin.conf
sudo systemctl enable --now lightdm.service
```

Instala la unidad endurecida `bascula-ui.service` para ejecutar la UI como `bascula`:

```
sudo cp systemd/bascula-ui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bascula-ui.service
```

Requisitos:
- Un servidor gráfico activo (DISPLAY `:0`) antes de lanzar la UI (LightDM autologin).
- Dispositivo serie accesible (`/dev/serial0`) para la báscula.

Consejo: si la UI no conecta a X11, verifica que existe `/home/bascula/.Xauthority` y ajusta `Environment=XAUTHORITY=/home/bascula/.Xauthority` (ya presente en la unidad).

Notas:
- La UI detecta automáticamente el mini‑web en `http://127.0.0.1:8080`.
- Si el mini‑web no está disponible, usa fallback: `nmcli` (Wi‑Fi) y ficheros locales (`~/.config/bascula`).

## 6) Comprobaciones rápidas
- Mini‑web local:
  - `curl http://127.0.0.1:8080/api/status` ⇒ `{"ok": true, ...}` (si se invoca desde la propia báscula)
  - `curl http://127.0.0.1:8080/api/wifi_scan` ⇒ lista de redes (requiere `nmcli`)
- UI:
  - Ajustes → Wi‑Fi: lista redes, conectar con teclado en pantalla.
  - Ajustes → API Key: guarda en `~/.config/bascula/apikey.json` (o vía API local).
  - Ajustes → Nightscout: guarda `~/.config/bascula/nightscout.json`; botón “Probar”.

## 7) Seguridad (resumen)
- Mini‑web ligado a `127.0.0.1` (no expone en LAN).
- Peticiones sin PIN solo desde loopback; resto requiere sesión con PIN.
- Cookies de sesión `HttpOnly`, `SameSite=Lax`.
- Ficheros sensibles con permisos 600; directorio de config con 700.
- Servicio systemd con aislamiento (`NoNewPrivileges`, `ProtectSystem`, `IPAddressAllow=127.0.0.1`).

## 8) Resolución de problemas
- Revisar logs: `journalctl -u bascula-web.service -f`
- Verificar `nmcli`: `nmcli dev status`, `nmcli radio wifi on`
- Polkit: si `nmcli` falla desde `bascula`, revisa `docs/polkit-networkmanager.md:1` y reinicia `polkit` y `NetworkManager`.
- Puertos: `ss -ltnp | grep :8080` debe mostrar `127.0.0.1:8080`.
- Python deps: `pip install -r requirements.txt`.

## 9) Desarrollo / pruebas sin systemd
- Mini‑web: `sudo -u bascula -H bash -lc 'cd ~/bascula-cam && python3 -m bascula.services.wifi_config'`
- UI: según tu entorno (X11/Wayland), asegúrate de que DISPLAY y permisos están correctos.

*** Fin ***
