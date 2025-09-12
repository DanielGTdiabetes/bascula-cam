Bascula-Cam â€” InstalaciÃ³n Offline (Paquete en /boot/bascula-offline)

Objetivo
- Permitir instalar/actualizar en Raspberry Pi sin Internet o con bloqueo temporal (p. ej., partidos/blackouts).
- El instalador detecta y usa el paquete en `BASCULA_OFFLINE_DIR` o `/boot/bascula-offline`.

Estructura del paquete offline
Coloca esta carpeta en la particiÃ³n BOOT de la SD/USB (visible como `boot` o `bootfs`), con esta estructura:

```
/boot/bascula-offline/
  wheels/                     # Ruedas (.whl) para dependencias de Python (opcional pero recomendado)
  requirements.txt            # Opcional: para instalar desde wheels
  piper/
    bin/piper                 # Binario Piper para tu arquitectura (ejecutable)
  piper-voices/
    es_ES-mls-medium.tar.gz   # Voz Piper (cambia VOICE si usas otra)
  whisper/
    ggml-tiny-es.bin          # Modelo Whisper tiny-es
```

CÃ³mo generar el paquete offline automÃ¡ticamente
En una mÃ¡quina con acceso a Internet (Linux o la propia Pi cuando sÃ­ haya conectividad):

1) Ejecuta el helper para construir el bundle
```
# Una voz `n bash scripts/build-offline-bundle.sh /tmp/bascula-offline es_ES-mls-medium `n # Varias voces (ej.: medium + low) `n bash scripts/build-offline-bundle.sh /tmp/bascula-offline es_ES-mls-medium es_ES-mls-low `n # Incluir wheels opcionales de Paddle (si hay en piwheels) `n WITH_PADDLE=1 bash scripts/build-offline-bundle.sh /tmp/bascula-offline es_ES-mls-medium
```
Esto descargarÃ¡:
- wheels: pyserial, pillow, fastapi, uvicorn[standard], pytesseract, requests, pyzbar, pytz, tflite-runtime==2.14.0, opencv-python-headless, numpy, piper-tts, rapidocr-onnxruntime
- piper binario según arquitectura (aarch64, armv7l o x86_64)
- voz de Piper (VOICE)
- modelo Whisper tiny-es

2) Copia el resultado a la particiÃ³n BOOT
```
sudo cp -a /tmp/bascula-offline /boot/bascula-offline
```

Uso en la instalaciÃ³n
- El instalador `scripts/install-all.sh` detecta `/boot/bascula-offline` automÃ¡ticamente y:
  - Instala dependencias Python desde `wheels/` si no hay red
  - Usa `piper/bin/piper` si falta el binario en el sistema
  - Usa `piper-voices/<VOICE>.tar.gz` para instalar la voz local
  - Copia `whisper/ggml-tiny-es.bin` si falta

Notas y recomendaciones
- Puedes cambiar la voz por otra de https://github.com/rhasspy/piper-voices (guÃ¡rdala como `<VOICE>.tar.gz` en `piper-voices/`).
- Si prefieres instalar Piper vÃ­a pip en offline, aÃ±ade la wheel de `piper-tts` a `wheels/` (el helper ya intenta descargarla).
- Para PaddleOCR/PaddlePaddle el soporte offline no estÃ¡ garantizado (ruedas pesadas/limitadas). Son opcionales.
- Los paquetes del sistema (APT) no se cachean con este bundle; si necesitas APT offline, usa un mirror local o `apt-cacher-ng`.

SoluciÃ³n de problemas
- Piper usa espeak-ng en lugar de TTS neural:
  - Verifica que existe un binario `piper` y que hay un modelo `.onnx` y su `.onnx.json` en `/opt/piper/models/`.
  - Ejecuta: `say.sh "Hola, probando Piper"`.
- Whisper no transcribe:
  - Comprueba `/opt/whisper.cpp/models/ggml-tiny-es.bin`. Si no existe, colÃ³calo en `bascula-offline/whisper/` y reinstala.

Compatibilidad
- Probado en Raspberry Pi OS Bookworm (Pi 5, aarch64). Para armv7l (32-bit) selecciona el binario Piper armv7l.



