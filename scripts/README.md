Scripts útiles

- run-ui.sh: lanza la UI Tk desde la raíz del repo. Crea/usa venv y verifica pyserial.
- diagnose_serial.py: diagnóstico de UART `/dev/serial0` (baudrate, procesos, configuración).
- camera_diagnostic.py: diagnóstico de cámara (libcamera/picamera2) y prueba de captura.
- fix_plymouth_v2.sh: ajustes de splash Plymouth y cmdline para ocultar mensajes al boot.
- rollback_to_startx.sh: automatiza el paso a arranque con `.xinitrc` sin LightDM.
- test_camera.py: prueba simple de `CameraService` y captura.
- clean.sh / clean.ps1: limpia `__pycache__` y `*.pyc`.

Atajos con Make

- `make run-ui`: ejecuta `scripts/run-ui.sh`
- `make run-web`: ejecuta el mini‑web `bascula.services.wifi_config`
- `make install-web` o `make install-web BASCULA_USER=pi`: instala el servicio mini‑web bajo ese usuario
- `make clean`: borra cachés Python
- `make deps`: instala dependencias de `requirements.txt`
- `make diag-serial`: ejecuta `scripts/diagnose_serial.py`
- `make diag-camera`: ejecuta `scripts/camera_diagnostic.py`
- `make doctor`: diagnóstico integral (nmcli, polkit, mini‑web, serial, pyserial, picamera2)
- `make allow-lan SUBNET=192.168.1.0/24`: abre la mini‑web a tu LAN (requiere PIN)
- `make local-only`: restringe la mini‑web a 127.0.0.1
- `make show-url` / `make show-pin`: muestra URL y PIN actuales

Notas

- En Raspberry Pi, usa `bash` para los `.sh` y `python3` para los `.py`.
- En Windows, usa PowerShell para `clean.ps1` o WSL para los `.sh`.
