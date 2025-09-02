# Instalación Báscula Digital Pro (Raspberry Pi Zero 2 W)

Este documento describe el proceso de instalación **desde cero** en una Raspberry Pi recién formateada.  
Se ha simplificado la red: **sin AP**, solo Wi-Fi de casa configurado desde Raspberry Pi Imager.

---

## 1. Pre-requisitos (Imager)

- Graba Raspberry Pi OS Bookworm 64-bit Lite con **Raspberry Pi Imager**.
- En "Opciones avanzadas":
  - Hostname: `bascula-pi`
  - Habilitar SSH
  - Usuario inicial: `pi` (o el que uses para la primera entrada)
  - Configura **SSID y contraseña de tu red Wi-Fi de casa**

Al primer arranque la Pi se conectará directamente a tu Wi-Fi.

---

## 2. Usuario `bascula`

Crear el usuario de servicio:

```bash
sudo adduser --disabled-password --gecos "Bascula" bascula
sudo usermod -aG tty,dialout,video,gpio bascula
```

---

## 3. Instalar dependencias básicas

```bash
sudo apt-get update
sudo apt-get install -y   git ca-certificates   xserver-xorg lightdm lightdm-gtk-greeter openbox   network-manager policykit-1   python3-venv python3-pip python3-tk   rpicam-apps python3-picamera2   curl nano raspi-config
```

---

## 4. Claves SSH para GitHub

Generar clave SSH en `bascula`:

```bash
sudo -u bascula -H bash -lc '
mkdir -p ~/.ssh && chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "bascula@bascula-pi" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
'
```

Copia la clave pública y añádela en: **GitHub → Settings → SSH and GPG keys**.

Probar conexión:

```bash
sudo -u bascula -H bash -lc 'ssh -T git@github.com || true'
```

---

## 5. Clonar el repositorio

```bash
sudo -u bascula -H bash -lc '
cd ~
git clone git@github.com:DanielGTdiabetes/bascula-cam.git ~/bascula-cam
cd ~/bascula-cam && git pull
'
```

---

## 6. Configuración de LightDM + Openbox (autologin)

Crear config para autologin en `bascula`:

```bash
sudo mkdir -p /etc/lightdm/lightdm.conf.d
sudo tee /etc/lightdm/lightdm.conf.d/50-bascula-autologin.conf >/dev/null <<'EOF'
[Seat:*]
autologin-user=bascula
autologin-user-timeout=0
autologin-session=openbox
greeter-session=lightdm-gtk-greeter
EOF
```

---

## 7. Autostart de Openbox

Openbox ejecuta `autostart` al iniciar sesión. Ahí lanzamos la app.

```bash
sudo -u bascula -H bash -lc '
mkdir -p ~/.config/openbox ~/.local/bin
cat > ~/.local/bin/start-bascula.sh << "SH"
#!/usr/bin/env bash
set -euo pipefail
echo "$(date) - start-bascula.sh lanzado" >> /home/bascula/autostart.log 2>&1
cd /home/bascula/bascula-cam
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv >> /home/bascula/autostart.log 2>&1
fi
source .venv/bin/activate
echo "$(date) - ejecutando main.py" >> /home/bascula/autostart.log 2>&1
exec python3 /home/bascula/bascula-cam/main.py >> /home/bascula/autostart.log 2>&1
SH
chmod +x ~/.local/bin/start-bascula.sh

cat > ~/.config/openbox/autostart << "EOF2"
#!/usr/bin/env bash
/home/bascula/.local/bin/start-bascula.sh &
EOF2
chmod +x ~/.config/openbox/autostart
'
```

---

## 8. Ajustes de pantalla y UART

El script de bootstrap añade estas líneas a `/boot/config.txt`:

```
dtoverlay=vc4-kms-v3d
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 600 60 3 0 0 0
enable_uart=1
dtoverlay=disable-bt
```

---

## 9. Arranque final

Reinicia la Pi:

```bash
sudo reboot
```

Al iniciar:
- LightDM hace autologin → sesión Openbox en `bascula`.
- Openbox ejecuta `autostart` → lanza la app.
- La UI aparece directamente en la pantalla.

---

## 10. Logs útiles

- Log de la app: `/home/bascula/autostart.log`
- Errores de sesión X: `/home/bascula/.xsession-errors`
- Estado de LightDM:
  ```bash
  systemctl status lightdm --no-pager -l
  ```
- Procesos Python en ejecución:
  ```bash
  pgrep -a python3
  ```
