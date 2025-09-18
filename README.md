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

## Testing

```bash
source .venv/bin/activate
python -m pip install -e .
python -m pytest
```

## Instalación en Raspberry Pi OS Lite (Pi 5 modo kiosko)

1. Configura el arranque automático en consola:

   ```bash
   sudo raspi-config nonint do_boot_behaviour B2
   ```

2. Clona el repositorio y lanza el instalador orquestador:

   ```bash
   git clone https://github.com/DanielGTdiabetes/bascula-cam.git
   cd bascula-cam
   chmod +x scripts/install-all.sh
   ./scripts/install-all.sh
   ```

   La Fase 1 prepara el sistema, instala dependencias y reinicia automáticamente. Tras el login de `pi`, se reanuda la Fase 2 sin intervención.

### Ejecución manual de las fases

```bash
sudo bash scripts/install-1-system.sh   # reinicia automáticamente salvo que uses --skip-reboot
sudo reboot                             # solo necesario si omitiste el reinicio automático
sudo bash scripts/install-2-app.sh
```

### Notas de audio, voz y cámara

- **Audio**: el servicio `bascula-ui` hereda `BASCULA_THEME=retro`. Si necesitas forzar una tarjeta ALSA concreta, exporta `BASCULA_APLAY_DEVICE` antes de lanzar `safe_run.sh` o ajusta el servicio con `Environment=BASCULA_APLAY_DEVICE=plughw:X,Y`.
- **Piper**: los modelos descargados se guardan en `/opt/piper/models`. El fichero `.default-voice` selecciona el modelo usado por defecto.
- **Cámara**: `libcamera-apps` y `python3-picamera2` quedan instalados durante la Fase 1. Usa `libcamera-hello --version` para verificar la pila de cámara.

### Diagnóstico posterior

Tras cualquier actualización ejecuta `bash scripts/post-update-audit.sh`. El script lanza `scripts/verify-all.sh`, guarda el log completo en `audit/` y genera un resumen legible en `audit/SUMMARY.md` con el estado de cada verificador (UI, servicios, instaladores, voz, miniweb, OTA y x735). Si dispones de GitHub CLI y estás en un entorno de Pull Request, publicará automáticamente el resumen como comentario. Para comprobaciones rápidas en kiosco sigue disponible `scripts/verify-kiosk.sh` (no bloqueante) que valida X11, Tkinter, Piper, audio, cámara y servicios `bascula-miniweb`/`x735-fan`.

## Mascota

La interfaz incluye una mascota robótica con distintos estados animados que ayudan a comunicar lo que ocurre en pantalla sin mostrar cifras de peso. Puedes cambiar su estado desde cualquier punto del código llamando a `app.set_mascot_state("listen")`. Los estados admitidos son:

- `idle`
- `listen`
- `think`
- `error`
- `sleep`

Variables de entorno:

- `BASCULA_MASCOT_THEME`: tema activo (`retro-green` por defecto) con brillo sutil en la pantalla del pecho.
- `BASCULA_MASCOT_COMPACT`: si vale `1`, utiliza la versión compacta para pantallas muy pequeñas.

### Mascota (assets)

El repositorio solo versiona los SVG ubicados en `bascula/ui/assets/mascota/`. Los PNG @1x (512px) y @2x (1024px) se generan durante la instalación gracias a `librsvg2-bin` y se guardan en `bascula/ui/assets/mascota/_gen/` (por ejemplo `robot_idle@512.png`).

Para regenerarlos manualmente ejecuta:

```bash
bash scripts/build-mascot-assets.sh
```

Al añadir un tema nuevo replica los SVG actuales, ajusta los colores conservando la pantalla vacía en el pecho y vuelve a ejecutar el script para generar los PNG correspondientes.
