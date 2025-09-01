📦 Instalador SSH — Báscula Digital Pro

Este documento explica cómo instalar y configurar Báscula Digital Pro en una Raspberry Pi Zero 2 W desde SSH, usando el script install_bascula_ssh.sh.

El instalador automatiza todo lo que antes había que hacer a mano:
✅ Configuración de repositorios Raspberry Pi y claves GPG
✅ Instalación de paquetes base (Python, Xorg, Tk, Picamera2, rpicam-apps, etc.)
✅ Creación de AP Wi-Fi BasculaAP (WPA2, clave configurable)
✅ Configuración HDMI (pantalla 7" 1024×600 forzado, evita errores no screens found)
✅ Configuración UART (GPIO14/15 para el ESP32, sin consola serial ocupando puerto)
✅ Creación de venv con --system-site-packages (Picamera2 siempre disponible)
✅ Lanzadores (/usr/local/bin/bascula, bascula-xsession)
✅ Servicio bascula.service que arranca la UI al inicio

🔧 Requisitos previos

Raspberry Pi Zero 2 W con Raspberry Pi OS/Debian Bookworm.

Acceso por SSH con usuario pi (o el que uses).

Conexión a Internet en la Raspberry Pi.

El repositorio de la app en GitHub:

https://github.com/DanielGTdiabetes/bascula-cam.git

📥 Descarga y ejecución

Copia el script a tu Raspberry Pi:

nano install_bascula_ssh.sh
# (pega aquí el contenido completo del instalador)
chmod +x install_bascula_ssh.sh


Ejecuta el instalador con sudo:

sudo bash ./install_bascula_ssh.sh


Por defecto:

SSID Wi-Fi → BasculaAP

Clave Wi-Fi → bascula1234

Canal → 1

Puerto serie → /dev/serial0 @ 115200

⚙️ Variables opcionales

Puedes cambiar opciones al invocar el script:

sudo AP_SSID="MiBascula" AP_PSK="otraclave123" AP_CHANNEL=11 \
     REPO_URL="https://github.com/DanielGTdiabetes/bascula-cam.git" \
     bash ./install_bascula_ssh.sh


AP_SSID → Nombre del punto de acceso.

AP_PSK → Contraseña WPA2.

AP_CHANNEL → Canal (1, 6 o 11 recomendados).

REPO_URL → Repositorio de GitHub.

HDMI_W / HDMI_H / HDMI_FPS → Resolución/frecuencia forzada.

▶️ Arranque y uso

Tras instalar:

Arranca el servicio manualmente:

sudo systemctl start bascula.service


Ver logs en vivo:

journalctl -u bascula.service -f


Arranque automático al boot: el servicio queda habilitado por defecto.

Recomendación: reinicia la Raspberry Pi tras instalar para aplicar los cambios de HDMI/UART:

sudo reboot

📡 Conexión al punto de acceso

SSID: el definido en AP_SSID (por defecto BasculaAP).

Contraseña: AP_PSK (por defecto bascula1234).

Método: WPA2.

El dispositivo conectado recibe IP automáticamente.

🖼️ Cámara

El script instala:

python3-picamera2 (librería para la app).

rpicam-apps (herramientas de prueba: rpicam-hello, rpicam-still, rpicam-vid).

Pruebas rápidas:

rpicam-hello --list-cameras
rpicam-still -o test.jpg

🧪 Comprobaciones rápidas

¿App funciona al inicio?

sudo systemctl status bascula.service


¿Cámara disponible?

python3 -c "from picamera2 import Picamera2; Picamera2(); print('OK cámara')"


¿Peso responde?
Conecta ESP32 → mira logs en /home/pi/app.log.

📂 Rutas importantes

Código de la app: /home/pi/bascula-cam

Venv: /home/pi/bascula-cam/.venv

Logs app: /home/pi/app.log

Servicio: /etc/systemd/system/bascula.service

Config HDMI/UART: ${BOOTDIR}/config.txt y ${BOOTDIR}/cmdline.txt

AP NetworkManager: /etc/NetworkManager/system-connections/bascula-ap.nmconnection

🛠️ Comandos útiles

Reiniciar servicio:

sudo systemctl restart bascula.service


Actualizar código de la app:

cd /home/pi/bascula-cam && git pull


Exportar datos (CSV/JSON) → se guardan en:

/home/pi/.bascula/
