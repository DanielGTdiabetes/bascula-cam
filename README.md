# B�scula ESP32 ? Raspberry Pi (UART)

Objetivo: lectura de peso en ESP32+HX711 y env�o por UART a Raspberry Pi (pyserial).
Protocolo 115200 bps: l�neas `G:<gramos>` y `S:<0|1>`; comandos `T` (tara) y `C:<peso>`.

Estructura:
- firmware-esp32/: Arduino (C++) con HX711, Serial1, filtro mediana+IIR, tara y calibraci�n.
- python_backend/: backend serial para la app (serial_scale.py) + integraci�n m�nima en services/scale.py
- rpi-setup/: scripts y pasos para habilitar UART, instalar pyserial, governor performance.
- scripts/: utilidades (test puerto, systemd opcional).
- docs/: cableado y checklist de pruebas.
