# Audio en Raspberry Pi 5 (Bookworm)

Este proyecto utiliza un amplificador I²S MAX98357A. El fichero de configuración
está en `/boot/firmware/config.txt` (o `/boot/config.txt` en otros modelos).

## Configuración rápida

```
sudo ./scripts/install-piper-voices.sh
sudo ./scripts/install-all.sh --audio=max98357a
sudo reboot
./scripts/sound-selftest.sh   # No ejecutar como root
```

Tras instalar y reiniciar, en `/boot/firmware/config.txt` deben existir:

```
dtoverlay=audremap,pins_18_19
dtoverlay=hifiberry-dac
```

## Voces Piper

`install-piper-voices.sh` usa primero los modelos de mi Release (variable
`VOICES_BASE`). La voz por defecto es `es_ES-sharvard-medium`, pero puedes
elegir `es_ES-davefx-medium` o `es_ES-carlfm-x_low` con:

```
PIPER_VOICE=es_ES-davefx-medium sudo ./scripts/install-piper-voices.sh
```

## Forzar tarjeta al arrancar la UI (opcional)

El instalador detecta la mayoría de tarjetas y actualiza `/etc/asound.conf` de
forma automática. Si aún así necesitas fijar manualmente el dispositivo ALSA,
edita el `~/.xinitrc` del usuario que arranca la interfaz (`pi` por defecto) y
exporta la variable antes de ejecutar la UI:

```
nano ~/.xinitrc
# Añade o ajusta la línea antes del "exec":
export BASCULA_APLAY_DEVICE=plughw:MAX98357A,0
```

Guarda el archivo y reinicia la sesión gráfica (por ejemplo
`sudo loginctl terminate-user pi`) o reinicia la Raspberry Pi para aplicar el
cambio. La salida HDMI/jack (`vc4hdmi`) suele seleccionarse automáticamente; solo
fuerza `BASCULA_APLAY_DEVICE` si existen varias tarjetas y necesitas fijar la
MAX98357A.

## Testing

✅ `python -m pytest`

⚠️ `./scripts/sound-selftest.sh` (No ejecutar como root)

## Resolución de problemas

- `aplay -l` para listar tarjetas.
- `dmesg | grep -i hifiberry` para ver errores de overlay.
- Verifica pines I²S: BCLK=GPIO18, LRCLK=GPIO19, DIN=GPIO21.
- Usa `softvol` si tu tarjeta no ofrece control de volumen por hardware.

La salida HDMI/jack y la I²S son tarjetas distintas; normalmente no se fuerza
dispositivo salvo que quieras usar MAX98357A cuando existan varias.

