🛠️ Troubleshooting — Báscula Digital Pro

Este documento recopila los problemas más comunes encontrados en la instalación y uso de la Báscula Digital Pro, junto con sus soluciones rápidas.

📺 Pantalla HDMI — Error no screens found

Síntomas

En el log del servicio aparece:

Fatal server error: no screens found


La pantalla queda negra.

Solución

Editar /boot/firmware/config.txt y añadir:

hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 600 60 3 0 0 0
dtoverlay=vc4-kms-v3d


Reiniciar:

sudo reboot

📷 Cámara — Picamera2 no disponible

Síntomas

En el log de la app:

Estado de la cámara: Picamera2 no disponible (instala python3-picamera2)


Causa
El venv no tiene acceso a los paquetes instalados con APT (python3-picamera2).

Solución
Recrear el venv con acceso al sistema:

sudo systemctl stop bascula.service
rm -rf /home/pi/bascula-cam/.venv
python3 -m venv --system-site-packages /home/pi/bascula-cam/.venv
source /home/pi/bascula-cam/.venv/bin/activate
pip install -r /home/pi/bascula-cam/requirements.txt
deactivate
sudo systemctl start bascula.service

📡 Wi-Fi AP — No aparece BasculaAP o no acepta clave

Síntomas

El SSID BasculaAP no se muestra.

Windows pide “PIN del enrutador” en lugar de clave.

El AP aparece pero no conecta.

Solución

Verifica configuración de NetworkManager:

sudo nano /etc/NetworkManager/system-connections/bascula-ap.nmconnection


Debe contener:

[wifi]
ssid=BasculaAP
mode=ap
band=bg
channel=1

[wifi-security]
key-mgmt=wpa-psk
psk=bascula1234


Asegura permisos:

sudo chown root:root /etc/NetworkManager/system-connections/bascula-ap.nmconnection
sudo chmod 600 /etc/NetworkManager/system-connections/bascula-ap.nmconnection


Reinicia servicio:

sudo systemctl restart NetworkManager

🔌 UART — No se detecta /dev/serial0

Síntomas

ls -l /dev/serial* no muestra serial0 → ttyAMA0.

App no recibe datos del ESP32.

Solución

Editar /boot/firmware/config.txt y asegurar:

enable_uart=1
dtoverlay=disable-bt


Editar /boot/firmware/cmdline.txt y eliminar cualquier console=serial0,… o console=ttyAMA0,….

Reiniciar.

Verificar:

ls -l /dev/serial0

🖥️ Xorg — Solo root puede lanzar la UI

Síntomas

En el log:

Only console users are allowed to run the X server


Solución

Editar /etc/X11/Xwrapper.config:

allowed_users=anybody
needs_root_rights=yes


Reiniciar servicio:

sudo systemctl restart bascula.service

Mini-web - ModuleNotFoundError: No module named 'flask' / ExecStart roto

Sintomas

- En `bascula-web.service`: `ModuleNotFoundError: No module named 'flask'`.
- En el log de systemd: `/bin/bash: line 1: =/home/pi/bascula-cam/.venv/bin/python3: No such file or directory`.

Causa

El servicio `bascula-web.service` esta arrancando con el Python del sistema en vez del del entorno virtual (`.venv`), por un `ExecStart` danado. Al no usar el venv, no encuentra Flask ni otras dependencias.

Solucion paso a paso

1) Asegurar que el servicio NO corre como root

Si ves errores a /root/.config/bascula en los logs, el servicio está corriendo como root. Fuerza el usuario correcto (pi o bascula):

```bash
sudo mkdir -p /etc/systemd/system/bascula-web.service.d
cat >/tmp/05-user.conf <<'EOF'
[Service]
User=pi
Group=pi
WorkingDirectory=%h/bascula-cam
Environment=BASCULA_CFG_DIR=%h/.config/bascula
EOF
sudo mv /tmp/05-user.conf /etc/systemd/system/bascula-web.service.d/05-user.conf
```

Comprueba el usuario efectivo:

```bash
systemctl show bascula-web.service -p User
```

2) Corregir el override de systemd (ExecStart simple apuntando al venv)

```bash
sudo mkdir -p /etc/systemd/system/bascula-web.service.d
cat >/tmp/10-venv-and-lan.conf <<'EOF'
[Service]
ExecStart=
# Usar la ruta directa al python del venv. Es mas simple y robusto.
ExecStart=%h/bascula-cam/.venv/bin/python3 -m bascula.services.wifi_config
Environment=BASCULA_WEB_HOST=0.0.0.0
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressAllow=
IPAddressDeny=
EOF
sudo mv /tmp/10-venv-and-lan.conf /etc/systemd/system/bascula-web.service.d/10-venv-and-lan.conf
```

Notas:

- La linea `ExecStart=` en blanco borra el `ExecStart` anterior.
- Se usa `%h` (HOME del usuario del servicio) para que funcione con `pi` o `bascula`.
- Si no quieres abrir a la red, elimina la linea `Environment=BASCULA_WEB_HOST=0.0.0.0` y los `RestrictAddressFamilies/IPAddress*`.

3) Reinstalar dependencias en el venv (por si acaso)

```bash
cd ~/bascula-cam
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

4) Recargar systemd y reiniciar el servicio

```bash
sudo systemctl daemon-reload
sudo systemctl restart bascula-web.service
```

5) Verificar

```bash
systemctl status bascula-web.service --no-pager -l
journalctl -u bascula-web.service -n 100 --no-pager
```

Comprobaciones utiles:

- Ver el `ExecStart` efectivo: `systemctl cat bascula-web.service`.
- Confirmar que el venv existe: `ls -l %h/bascula-cam/.venv/bin/python3` (reemplaza `%h` por `/home/pi` o `/home/bascula` si estas en shell).
 - Para pruebas manuales fuera de systemd, ejecuta desde la carpeta del repo para que Python encuentre el paquete `bascula`:
   - `cd ~/bascula-cam && . .venv/bin/activate && python -m bascula.services.wifi_config`


🔑 Repositorios — Error NO_PUBKEY

Síntomas

Al hacer sudo apt update →

NO_PUBKEY 9165938D90FDDD2E


Solución

Instalar keyring oficial:

sudo apt install -y raspberrypi-archive-keyring


Usar repos firmados en /etc/apt/sources.list.d/raspi.list:

deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.org/debian/ bookworm main


Actualizar:

sudo apt update

📋 Comandos de emergencia

Ver logs de la app:

tail -n 80 /home/pi/app.log


Ver logs del servicio:

journalctl -u bascula.service -n 80 --no-pager


Reiniciar servicio:

sudo systemctl restart bascula.service
