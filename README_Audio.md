# Audio en Raspberry Pi 5 (Bookworm)

Este proyecto utiliza un amplificador I²S MAX98357A. En Raspberry Pi OS
Bookworm, el fichero de configuración está en `/boot/firmware/config.txt`.
Asegúrate de que existan las siguientes líneas:

```
dtoverlay=audremap,pins_18_19
dtoverlay=hifiberry-dac
```

Pasos recomendados:

```
sudo ./scripts/install-piper-voices.sh --voices es_ES-sharvard-medium
sudo ./scripts/install-all.sh --audio=max98357a
sudo reboot
./scripts/sound-selftest.sh
```

Forzar dispositivo (solo si es necesario):

```
sudo systemctl edit bascula-ui.service
# [Service]
# Environment=BASCULA_APLAY_DEVICE=plughw:MAX98357A,0
sudo systemctl daemon-reload
sudo systemctl restart bascula-ui
```

Resolución de problemas:

- `aplay -l` para listar tarjetas.
- `dmesg | grep -i hifiberry` para ver errores de overlay.
- Verifica conexiones I²S: BCLK=GPIO18, LRCLK=GPIO19, DIN=GPIO21.
- Usa `softvol` si tu tarjeta no ofrece control de volumen por hardware.

La salida HDMI/jack suele ser la tarjeta `vc4hdmi` y no requiere forzar
dispositivo. Solo fuerza `BASCULA_APLAY_DEVICE` cuando haya múltiples
tarjetas y necesites fijar MAX98357A.

