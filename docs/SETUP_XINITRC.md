# Arranque sin LightDM con .xinitrc (modo kiosco)

Este documento explica cómo arrancar la UI directamente tras el inicio, sin LightDM ni Openbox, usando `~/.xinitrc` y autologin en consola (tty1).

## 1) Paquetes necesarios

- Xorg mínimo: `sudo apt install -y xserver-xorg xinit`
- Tk para Python: `sudo apt install -y python3-tk`
- Venv (si no lo tienes): `sudo apt install -y python3-venv`

## 2) Desactivar LightDM (si estaba presente)

```bash
sudo systemctl disable --now lightdm || true
```

## 3) Autologin en tty1 (usuario `bascula`)

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

Para que `startx` se lance automáticamente al entrar en tty1, añade esto a `~/.bash_profile` (o `~/.profile` si no tienes el primero):

```bash
if [ -z "$DISPLAY" ] && [ "${XDG_VTNR:-0}" = "1" ]; then
  exec startx -- -nocursor
fi
```

## 4) Crear `~/.xinitrc`

Ejemplo recomendado (ajusta la ruta del repo si es distinta a `~/bascula-cam`):

```bash
#!/usr/bin/env bash
xset -dpms       # Desactiva Energy Star
xset s off       # Sin salvapantallas
xset s noblank   # No apagar pantalla

# Lanza la UI desde el script del repo
exec "$HOME/bascula-cam/scripts/run-ui.sh" >> "$HOME/app.log" 2>&1
```

Recuerda dar permisos de ejecución si haces un script propio:

```bash
chmod +x ~/bascula-cam/scripts/run-ui.sh
```

## 5) Probar manualmente

Entra como el usuario objetivo (`bascula`) y ejecuta:

```bash
cd ~/bascula-cam
startx -- -nocursor
```

Si todo funciona, tras reiniciar el sistema la UI se mostrará automáticamente.

## 6) Logs y diagnóstico

- Log de la app: `~/app.log`
- Verifica import corregido: `python3 -c "from bascula.services.scale import ScaleService; print(ScaleService)"`
- UART/pyserial: asegúrate de tener `/dev/serial0` habilitado y permisos del usuario.

## 7) Revertir cambios

```bash
sudo rm -f /etc/systemd/system/getty@tty1.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1
sudo systemctl enable --now lightdm   # si quieres volver a LightDM
```

## 8) Notas

- El servicio `systemd/bascula-web.service` sigue siendo válido para la mini‑web de configuración (Wi‑Fi, API Key, Nightscout) en `http://127.0.0.1:8080`.
- El script `scripts/run-ui.sh` prepara el entorno (venv y pyserial) y lanza `main.py` desde la raíz del repo.

