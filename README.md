# Báscula ESP32 → Raspberry Pi (UART)

Objetivo: lectura de peso en ESP32+HX711 y envío por UART a Raspberry Pi (pyserial).
Protocolo 115200 bps: líneas `G:<gramos>` y `S:<0|1>`; comandos `T` (tara) y `C:<peso>`.

Estructura:
- firmware-esp32/: Arduino (C++) con HX711, Serial1, filtro mediana+IIR, tara y calibración.
- python_backend/: backend serial para la app (serial_scale.py) + integración mínima en services/scale.py
- rpi-setup/: scripts y pasos para habilitar UART, instalar pyserial, governor performance.
- scripts/: utilidades (test puerto, systemd opcional, run-ui.sh).
- docs/: cableado y checklist de pruebas.
- docs/SETUP_XINITRC.md: guía para arrancar la UI sin LightDM usando .xinitrc y autologin en tty1.
- docs/INSTALL_STEP_BY_STEP.md: guía paso a paso (mini-web + UI con .xinitrc).
- docs/MINIWEB_OVERRIDE.md: override menos estricto (0.0.0.0) y notas.

## Versiones probadas

- Raspberry Pi 5 (ARM64)
- Raspberry Pi OS Bookworm 64-bit
- Python 3.11.x

## Paquetes del sistema necesarios

El instalador `scripts/install-all.sh` prepara una Raspberry Pi 5 Bookworm con los siguientes paquetes APT:

- `python3-venv`, `python3-pip`, `python3-dev`, `python3-tk`
- `python3-picamera2` (Picamera2 se instala vía APT, no por `pip`)
- `libzbar0`, `fonts-dejavu-core`
- `network-manager`, `dnsutils`, `curl`, `jq`

Otros paquetes (X11, audio, OCR, etc.) se instalan automáticamente durante la fase 1 del script.

## Dependencias de la UI

- El script `scripts/install-2-app.sh` crea/actualiza el entorno virtual en `/opt/bascula/current/.venv`, fuerza `pip/wheel/setuptools` recientes e intenta descargar ruedas (`--only-binary=:all:`) para `numpy`, `tflite-runtime` y `opencv-python-headless`. Si no hay wheel disponible intenta compilar (o deja el error visible en el smoke test).
- En Raspberry Pi 5 (aarch64, Python 3.11) existe wheel oficial de `numpy==2.*`, por lo que la instalación completa del venv se resuelve sin compilar.
- Tras la instalación se ejecuta un smoke de imports (`numpy`, `PIL`, `tflite_runtime`, `cv2`, `tkinter`). Si aparece `MISSING: ...` en la salida, no habilites `bascula-app` hasta completar las dependencias.
- Entornos sin Internet: instala desde APT los paquetes necesarios (`sudo apt-get install python3-numpy python3-opencv`) y ejecuta el venv con `--system-site-packages` o exporta los módulos al venv (por ejemplo, creando un `.pth` apuntando a `/usr/lib/python3/dist-packages`).

## Báscula serie

El driver `bascula/core/scale_serial.py` autodetecta puerto y baudios utilizando el siguiente orden de prioridad:

1. Variables de entorno: `BASCULA_DEVICE`, `BASCULA_BAUD`, `BASCULA_CMD_TARE`, `BASCULA_CMD_ZERO`.
2. Configuración YAML: `~/.bascula/config.yaml`, sección `scale:` (`device`, `baud`, `cmd_tare`, `cmd_zero`).
3. Puertos comunes: `/dev/serial0`, `/dev/ttyAMA0`, `/dev/ttyS0`, `/dev/ttyUSB*`, `/dev/ttyACM*` y lista de baudios `[115200, 57600, 38400, 19200, 9600, 4800]`.

Para firmwares sin soporte de tara/cero por comando se puede forzar el cálculo en el host exportando `BASCULA_SCALE_HOST_TARE=1`. En ese modo no se envían comandos `TARE`/`ZERO` al dispositivo y los ajustes se aplican con los datos crudos recibidos.

Para diagnosticar la conexión en la Raspberry Pi:

```bash
python3 tools/check_scale.py --seconds 3 --raw
```

El comando muestra lecturas parseadas en gramos, indica si el modo es simulación y resume puerto/baudios detectados.

### Troubleshooting

- El usuario (`pi`) debe pertenecer a los grupos `dialout` y `tty`. Ejecutar `sudo scripts/fix-serial.sh` para aplicar grupos, reglas udev y deshabilitar la consola serie.
- Verificar que existe `/etc/udev/rules.d/90-bascula.rules` con permisos `0660` para los puertos `ttyAMA0`, `ttyS0` y dispositivos USB CDC.
- Asegurarse de que el fichero `/boot/firmware/cmdline.txt` (o `/boot/cmdline.txt`) no contiene `console=serial0,115200` y que en `config.txt` está definido `enable_uart=1`.
- En adaptadores USB-serial basados en PL2303/CH340 puede ser necesario instalar el paquete `python3-serial` (ya incluido en `requirements.txt`).

### Acceso mini-web

- En la AP Bascula_AP: http://10.42.0.1:8080/
- En la LAN: http://<IP-de-la-Pi>:8080/
- Seguridad: la unit permite solo redes privadas (loopback, 10.42.0.0/24, 192.168.0.0/16, 172.16.0.0/12). Si se cambia el puerto o la red, actualizar `IPAddressAllow` y las variables `BASCULA_WEB_HOST`/`BASCULA_WEB_PORT`.
- La mini-web se expone por defecto en `0.0.0.0:8080` (valores escritos en `/etc/default/bascula`).
- El puerto puede fijarse editando `/etc/default/bascula` y definiendo `BASCULA_MINIWEB_PORT` (prioritario) o `BASCULA_WEB_PORT` como respaldo.
- Nota: si no existe `/opt/bascula/current/.venv/bin/python`, el servicio `bascula-web` utilizará `${BASCULA_VENV}` (definido por `install-2-app.sh`) como intérprete alternativo de desarrollo.

### OTA y recursos opcionales

- El código de la release OTA se sincroniza a `/opt/bascula/current`, mientras que los recursos opcionales (`assets/`, `voices-v1/` y `ota/`) persisten en `/opt/bascula/shared`.
- Durante la instalación se crean symlinks (`assets`, `voices-v1`, `ota`) en `/opt/bascula/current/` apuntando a los directorios dentro de `shared`, evitando que un OTA sin recursos los borre.
- Los scripts de instalación toleran errores `rsync` 23/24 y mantienen permisos `0755` con propietario `${TARGET_USER}:${TARGET_USER}` en todos los directorios bajo `/opt/bascula/shared`.
