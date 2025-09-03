# Instalación paso a paso (Pi OS Bookworm)

Este documento guía la instalación completa: mini-web (Wi‑Fi/API) + UI en modo kiosco sin LightDM, usando `.xinitrc`.

## 0) Requisitos
- Raspberry Pi OS Bookworm (Lite recomendado)
- Red con acceso a Internet para instalar paquetes

## 1) Paquetes del sistema
```bash
sudo apt-get update
sudo apt-get install -y \
  git ca-certificates \
  xserver-xorg xinit python3-tk \
  network-manager policykit-1 \
  python3-venv python3-pip \
  rpicam-apps python3-picamera2 \
  alsa-utils espeak-ng
```

## 2) Usuario de servicio `bascula`
```bash
sudo adduser --disabled-password --gecos "Bascula" bascula
sudo usermod -aG tty,dialout,video,gpio bascula
```

## 3) Clonar el repo (como `bascula`)
```bash
sudo -u bascula -H bash -lc '
cd ~
[ -d bascula-cam ] || git clone https://github.com/DanielGTdiabetes/bascula-cam.git bascula-cam
cd ~/bascula-cam && git pull
'
```

## 4) Dependencias Python (usuario `bascula`)
El mini‑web (systemd) ejecuta `/usr/bin/python3` como usuario `bascula`, por lo que conviene instalar dependencias en su `~/.local`.
```bash
sudo -u bascula -H bash -lc '
cd ~/bascula-cam
pip3 install --user -r requirements.txt
'
```

## 5) Permisos para Wi‑Fi sin sudo (polkit)
Permite que el usuario de la app use `nmcli` sin contraseña.
- Rápido: `make install-polkit` (o `make install-polkit BASCULA_USER=pi`)
- Detalles y soluciones a problemas: `docs/polkit-networkmanager.md:1`

Nota: si `make doctor` sigue diciendo "polkit NM: regla no encontrada" y el archivo
`/etc/polkit-1/rules.d/50-bascula-nm.rules` existe, ajusta permisos de los
directorios para que el usuario no root pueda verificarlos:
```bash
sudo chmod 755 /etc/polkit-1 /etc/polkit-1/rules.d
```
Alternativamente, ejecuta sólo la comprobación como root: `sudo make doctor`.

## 6) Instalar mini‑web (systemd)
Desde la raíz del repo, instala el servicio bajo el usuario de servicio (por defecto `bascula`):
```bash
make install-web
```
Si prefieres ejecutarlo con otro usuario (p. ej. `pi`):
```bash
make install-web BASCULA_USER=pi
```
Lo que hace:
- Copia `systemd/bascula-web.service` a `/etc/systemd/system/`
- Ajusta `User=` y `Group=` al valor de `BASCULA_USER`
- `systemctl daemon-reload` y `enable --now`

Verificar:
```bash
make status-web
# o
make logs-web
# o
curl http://127.0.0.1:8080/api/status
# chequeo integral
make doctor
```

Abrir la mini‑web a la red local (acceso desde móvil/PC):
```bash
make allow-lan SUBNET=192.168.1.0/24   # ajusta a tu LAN
make show-url                           # muestra la URL
make show-pin                           # muestra el PIN de acceso
```
Accede desde el móvil a la URL mostrada. Te pedirá el PIN.

Volver a modo local (más seguro):
```bash
make local-only
```

## 7) Arranque UI sin LightDM (.xinitrc)
Usa `.xinitrc` y autologin en TTY1 para lanzar la UI.
- Guía detallada: `docs/SETUP_XINITRC.md:1`
- Resumen:
  1) Autologin en TTY1 (como root):
     ```bash
     sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
     sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null << 'EOF'
     [Service]
     ExecStart=
     ExecStart=-/sbin/agetty --autologin bascula --noclear %I $TERM
     Type=idle
     EOF
     sudo systemctl daemon-reload
     sudo systemctl restart getty@tty1
     ```
  2) Lanzar X en TTY1 automáticamente (como `bascula`): añade a `~/.bash_profile`:
     ```bash
     if [ -z "$DISPLAY" ] && [ "${XDG_VTNR:-0}" = "1" ]; then
       exec startx -- -nocursor
     fi
     ```
  3) Crear `~/.xinitrc` (como `bascula`):
     ```bash
     cat > ~/.xinitrc << 'XRC'
     #!/usr/bin/env bash
     xset -dpms; xset s off; xset s noblank
     exec "$HOME/bascula-cam/scripts/run-ui.sh" >> "$HOME/app.log" 2>&1
     XRC
     chmod +x ~/.xinitrc
     ```
  4) Probar: `startx -- -nocursor`

Si usas otro usuario para la UI (p. ej. `pi`), sustituye `bascula` por ese usuario en la override de `getty@tty1` y crea los archivos en su HOME.

## 8) Configuración inicial
- API Key (opcional, para nutrición): UI → Ajustes → API Key
- Wi‑Fi: UI → Ajustes → Wi‑Fi; o mini‑web `http://127.0.0.1:8080` (local)
- Nightscout (opcional): UI → Ajustes → Nightscout

## 9) UART (serie) en la Pi
- Asegúrate de que `/boot/config.txt` (o `/boot/firmware/config.txt`) tiene:
  - `enable_uart=1`
  - `dtoverlay=disable-bt` (en Pi 3/4/Zero2W)
- Quita la consola serie de `/boot/cmdline.txt` (sin `console=serial0,...`)
- Cableado: ESP32 TX → Pi RX (GPIO15), ESP32 RX → Pi TX (GPIO14), GND común
- Diagnóstico: `python3 scripts/diagnose_serial.py`

## 10) Mantenimiento
- Actualizar dependencias: `make deps`
- Limpiar cachés Python: `make clean`
- Ver logs mini‑web: `make logs-web`
- Desinstalar mini‑web: `make uninstall-web`

---
Si prefieres un único arranque “todo en uno” sin systemd para la web, puedes lanzar manualmente la mini‑web en otra consola: `make run-web`.

## Anexo: Pantalla HDMI que no muestra X
Si tras configurar el kiosco la pantalla queda en negro o X reinicia en bucle, puede ser necesario forzar el modo HDMI. Revisa `docs/DISPLAY_HDMI.md:1` y añade las líneas sugeridas en `/boot/firmware/config.txt` (Bookworm) para 1024x600 u otra resolución.
