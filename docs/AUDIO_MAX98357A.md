# Audio con MAX98357A (I²S) en Raspberry Pi Zero 2 W

Este módulo (MAX98357A) es un DAC I²S con amplificador. Permite reproducir audio (pitidos/voz) desde la Raspberry sin usar USB ni analógico.

- Cableado (Pi Zero 2 W):
  - BCLK → GPIO18 (PCM_CLK)
  - LRCLK/WS → GPIO19 (PCM_FS)
  - DIN → GPIO21 (PCM_DIN)
  - VIN → 5V
  - GND → GND

## Configuración del sistema (Bookworm)
1) Edita `/boot/firmware/config.txt` (o `/boot/config.txt` según tu imagen) y añade:

```
# Habilitar I2S y usar overlay de DAC simple
# Desactiva audio PWM integrado

dtparam=audio=off

dtoverlay=hifiberry-dac
```

2) Reinicia la Raspberry Pi.

3) Verifica que ALSA ve el dispositivo:

```
aplay -l
```

Deberías ver una tarjeta tipo `snd_rpi_hifiberry_dac`.

4) Ajusta volumen (si procede):

```
alsamixer
```

## Dependencias recomendadas
- `alsa-utils` (aplay/alsamixer)
- `espeak-ng` (voz opcional en español). Si no está, el sistema usa “beeps”.

## Integración con la app
- La app detecta automáticamente `aplay` y `espeak(-ng)` si están presentes.
- Tema de sonido: Ajustes → “Sonido” → `beep` o `voice_es`.
- Silenciar: botón 🔊/🔇 en la pantalla principal.

Eventos soportados (ejemplos):
- Estabilidad de peso → beep corto.
- Tara → “Tara realizada.” (en voz) o beep.
- “Boot ready”, “Wi‑Fi conectado”, etc. (si se activa voz).

Si no quieres voz, deja el tema en `beep`.
