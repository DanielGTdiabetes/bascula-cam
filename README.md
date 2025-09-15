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
