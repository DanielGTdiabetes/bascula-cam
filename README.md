# Báscula conectada a Raspberry Pi

Proyecto para integrar una báscula basada en ESP32+HX711 con una Raspberry Pi 5, cámara y servicios de nutrición/diabetes. El repositorio incluye firmware, backend Python, UI en Tkinter y scripts para preparar una imagen de Raspberry Pi OS Bookworm.

## Hardware recomendado

- **Raspberry Pi 5** con Raspberry Pi OS Bookworm de 64 bits.
- **Pantalla HDMI de 7"** (modo kiosk sin ratón, usa `unclutter`).
- **ESP32 con HX711** para la báscula serie que entrega lecturas `G:<gramos>` y estado de estabilidad `S:<0|1>`. 【F:README.md.bak†L1-L9】【F:bascula/services/scale.py†L32-L120】
- **Cámara soportada por Picamera2** para el escáner de alimentos. 【F:scripts/test_camera.py†L1-L38】【F:bascula/ui/views/food_scanner.py†L1-L121】
- **Geekworm X735 v3** (requerido) para ventilador PWM y apagado seguro por GPIO. 【F:overlay/x735/x735-fan.sh†L1-L116】【F:systemd/x735-poweroff.service†L1-L11】
- **Módulo MAX98357A** (I2S) para audio y avisos por voz. 【F:systemd/bascula-ui.service†L14-L19】【F:bascula/services/audio.py†L104-L134】
- **Micrófono USB opcional** para pruebas de reconocimiento de voz.

## Arquitectura del repositorio

- `firmware-esp32/`: firmware Arduino con filtro mediana+IIR, tara/cero y protocolo UART. 【F:README.md.bak†L5-L9】
- `python_backend/` y `bascula/services/`: servicios de serie, cámara, audio, Nightscout y mini-web. 【F:README.md.bak†L9-L13】【F:bascula/services/wifi_config.py†L166-L214】
- `bascula/ui/`: aplicación Tkinter (home, temporizador, recetas, ajustes y overlays). 【F:bascula/ui/app.py†L41-L123】【F:bascula/ui/views/home.py†L1-L102】
- `scripts/`: instaladores, diagnóstico y utilidades para AP, OTA y pruebas rápidas. 【F:scripts/install-1-system.sh†L1-L164】【F:scripts/setup_ap_nm.sh†L1-L73】

## Instalación en Raspberry Pi OS Bookworm

1. **Preparar microSD** con Raspberry Pi OS Bookworm (64 bits). Habilita SSH (opcional) y conecta red cableada para la fase inicial.
2. **Clonar el repositorio** en `/home/pi/bascula-cam` o descarga el paquete OTA a `/opt/bascula/current`.

### Fase 1 – sistema base

Ejecuta como `pi`:

```bash
cd ~/bascula-cam
sudo TARGET_USER=pi bash scripts/install-1-system.sh
```

Esta fase instala X11 ligero, dependencias de cámara/audio/OCR, habilita NetworkManager y configura el punto de acceso `Bascula_AP`. Además detecta automáticamente la GPU HDMI activa para escribir `/dev/dri/<cardX>` en `20-modesetting.conf`, aplica el bloque "Bascula-Cam (Pi 5)" en `config.txt` (creando `.bak` la primera vez) y despliega los servicios `x735-fan`/`x735-poweroff` basados en libgpiod. Al finalizar se crea `/var/lib/bascula/install-1.done` y se solicita un reinicio. 【F:scripts/install-1-system.sh†L24-L270】【F:tools/update-config.py†L1-L194】【F:systemd/x735-fan.service†L1-L11】

Reinicia la Raspberry Pi antes de continuar.

### X735 v3 (requerido)
La Fase 1 despliega los scripts vendor del HAT Geekworm X735 v3 en `/usr/local/bin` (`x735-fan`, `x735-poweroff`) y habilita los servicios correspondientes basados en libgpiod. El ventilador conmuta según la temperatura del SoC usando `gpioset` y registra advertencias si el pin está ocupado; el monitor de apagado escucha el botón en `GPIO17` y delega en `systemctl poweroff`. Los overlays `gpio-shutdown` y `gpio-poweroff` quedan fijados en el bloque "X735 v3" de `config.txt`. Tras un reinicio ambos servicios deben mostrarse activos (`systemctl is-active x735-fan x735-poweroff`). 【F:overlay/x735/x735-fan.sh†L1-L116】【F:overlay/x735/x735-poweroff.sh†L1-L62】【F:tools/update-config.py†L1-L194】【F:systemd/x735-poweroff.service†L1-L11】

### Fase 2 – aplicación

Tras el reinicio, vuelve a clonar (o actualiza) y ejecuta:

```bash
cd ~/bascula-cam
sudo scripts/install-2-app.sh
```

Esta fase sincroniza el repositorio a `/opt/bascula/current`, crea el entorno virtual, instala dependencias (`numpy`, `tflite-runtime`, `opencv-python-headless`) y registra servicios `bascula-app`, `bascula-web`, `bascula-alarmd` y `bascula-net-fallback`. También genera `/etc/default/bascula` con las variables de entorno principales. 【F:scripts/install-2-app.sh†L1-L142】【F:scripts/install-2-app.sh†L204-L314】【F:scripts/install-2-app.sh†L48-L92】

Si trabajas sin OTA puedes reutilizar el repositorio local y un venv en `~/bascula-cam/.venv`, reconocido automáticamente por el instalador. 【F:scripts/install-2-app.sh†L80-L88】

> Nota: los drop-ins de `systemd/bascula-web.service.d/*.conf` son opcionales. Si no están presentes en el repositorio, el instalador los omite sin error y `bascula-web` queda operativo igualmente.

### Checklist postinst
1. `systemctl is-active bascula-app x735-fan x735-poweroff` para confirmar que la UI y los servicios del HAT están activos tras el primer reinicio.
2. `tail -n200 ~/.local/share/xorg/Xorg.0.log | grep -i modesetting` y verificar que el log menciona `modesetting` y el `kmsdev` esperado.
3. `aplay -l` para listar tarjetas ALSA y comprobar que aparece `MAX98357A` (si no, revisa cables y vuelve a ejecutar la fase 1). 【F:scripts/smoke.sh†L1-L74】【F:overlay/x735/x735-fan.sh†L1-L116】

## Despliegue rápido sin reinstalar

Si ya tienes el repositorio clonado en `~/bascula-cam`, puedes reemplazar el despliegue en `/opt/bascula/current` sin ejecutar de nuevo los instaladores:

```bash
cd ~/bascula-cam && git pull
sudo systemctl stop bascula-app
sudo mv /opt/bascula/current /opt/bascula/current.bak.$(date +%s)
sudo ln -s "$PWD" /opt/bascula/current
sudo systemctl daemon-reload
sudo systemctl start bascula-app
```

Verifica después `journalctl -u bascula-app -n80 --no-pager` para confirmar que el backend serie quedó activo.

### Configuración UART con ESP32

Cuando la báscula está conectada por ESP32→Pi mediante UART (`/dev/ttyAMA0` a 115200 baudios) usa el fichero `~/.bascula/config.json` con un bloque como:

```json
{
  "scale": {
    "port": "/dev/ttyAMA0",
    "baud": 115200,
    "hx711_dt": null,
    "hx711_sck": null,
    "unit": "g",
    "decimals": 0,
    "smoothing": 5,
    "calib_factor": 1.0,
    "ml_factor": 1.0
  }
}
```

Puedes comprobar que el ESP32 emite tramas `G:<peso>,S:<estado>` con:

```bash
sudo stty -F /dev/ttyAMA0 115200 cs8 -cstopb -parenb -echo -icanon min 0 time 5
sudo timeout 3s head -c 64 /dev/ttyAMA0 | hexdump -C
```

La UI mostrará `--` cuando no haya señal y reflejará el peso real en cuanto regresen las líneas `G:…,S:…`.

## Primer arranque y flujos principales

### Inicio

- El servicio `bascula-app` lanza la UI en modo kiosk tras el auto-login en `tty1`. Si la báscula serie no entrega datos la UI muestra `--` y mantiene la sesión sin simular lecturas. 【F:bascula/ui/app.py†L41-L129】【F:bascula/ui/screens.py†L34-L57】
- El panel principal muestra peso en vivo, estado de estabilidad e iconos para tara/cero/unidades. 【F:bascula/ui/views/home.py†L27-L101】

### Home

- Botones de acceso rápido: tara, cero, cambio g↔ml (usa la densidad configurada), escáner de alimentos, recetas, temporizador y ajustes. 【F:bascula/ui/views/home.py†L55-L101】
- El interruptor “1 decimal” invoca `set_decimals` para ajustar la precisión enviada al servicio de báscula. 【F:bascula/ui/views/home.py†L39-L54】【F:bascula/ui/app.py†L96-L121】

### Alimentos

- `FoodScannerView` abre una ventana secundaria con peso en vivo, botón de reconocimiento por cámara y búsqueda por código de barras (FatSecret + caché local). 【F:bascula/ui/views/food_scanner.py†L19-L121】【F:bascula/services/fatsecret.py†L14-L100】
- Los ítems agregados calculan totales de carbohidratos, proteínas, grasas y GI. Se puede eliminar o terminar para enviar datos al registro. 【F:bascula/ui/views/food_scanner.py†L74-L170】
- Requiere `keys.toml` con credenciales FatSecret y, opcionalmente, NutritionAI. 【F:bascula/services/fatsecret.py†L34-L83】【F:bascula/ui/views/food_scanner.py†L10-L18】

### Temporizador

- El overlay de temporizador guarda el último valor en `ui.toml` (`timer_last_seconds`) y reproduce alarmas con audio/TTS cuando finaliza. 【F:bascula/ui/overlays/timer.py†L1-L121】
- Control global (`TimerController`) permite cancelar/retomar y notifica al shell para mostrar banners. 【F:bascula/ui/overlays/timer.py†L67-L160】【F:bascula/ui/app.py†L73-L117】

### Diabetes

- `diabetes.toml` habilita Nightscout (URL, token) y parámetros para asistente de bolo (ICR, ISF, objetivo). 【F:bascula/services/nightscout.py†L31-L91】【F:bascula/ui/overlay_bolus.py†L69-L257】
- El overlay de bolo ofrece cálculo de unidades, recordatorios 15/15 y exporta eventos según `export_mode`. 【F:bascula/ui/overlay_bolus.py†L245-L341】【F:bascula/ui/overlay_bolus.py†L617-L740】
- `bascula-alarmd` monitoriza Nightscout y dispara alarmas de voz si `alarms_enabled`/`announce_on_alarm` están activos. 【F:bascula/services/alarmd.py†L39-L134】【F:bascula/services/alarmd.py†L235-L339】

### Mini-web y llaves API

- `bascula-web` expone FastAPI/Uvicorn en `0.0.0.0:${BASCULA_MINIWEB_PORT}` para configurar Wi-Fi, claves de servicios y Nightscout. 【F:bascula/services/wifi_config.py†L166-L214】【F:scripts/install-2-app.sh†L48-L92】
- Guarda secretos en `~/.config/bascula/miniweb.json` y genera un PIN de 6 dígitos. 【F:bascula/services/wifi_config.py†L186-L210】
- El enlace rápido desde la UI usa la IP detectada o la AP (`http://10.42.0.1:8080`). 【F:README.md.bak†L63-L76】【F:scripts/setup_ap_nm.sh†L1-L73】

### Punto de acceso (AP)

- `setup_ap_nm.sh` crea la conexión `BasculaAP` en NetworkManager con SSID `Bascula_AP`, clave `bascula1234`, rango `10.42.0.1/24` y modo compartido. 【F:scripts/setup_ap_nm.sh†L1-L73】
- Tras Fase 1 la AP queda disponible para onboarding y la mini-web responde en `http://10.42.0.1:8080/` cuando no hay Wi-Fi conocida. 【F:scripts/install-1-system.sh†L142-L164】【F:scripts/setup_ap_nm.sh†L59-L73】

### OTA y recursos compartidos

- El OTA sincroniza código a `/opt/bascula/current` y mantiene recursos en `/opt/bascula/shared` (`assets`, `voices-v1`, `ota`, `models`, `userdata`, `config`). 【F:scripts/install-2-app.sh†L104-L173】
- Los symlinks se recrean en cada instalación y se preservan permisos para el usuario objetivo. 【F:scripts/install-2-app.sh†L165-L214】
- `scripts/ota.sh` permite desplegar nuevas releases sin perder datos. 【F:scripts/ota.sh†L48-L134】【F:scripts/ota.sh†L177-L214】

## Configuración de archivos

Las configuraciones se almacenan en `~/.config/bascula`. Para comenzar puedes copiar los ejemplos de `docs/examples/*.toml`:

```bash
mkdir -p ~/.config/bascula
cp docs/examples/scale.toml ~/.config/bascula/
cp docs/examples/diabetes.toml ~/.config/bascula/
cp docs/examples/ui.toml ~/.config/bascula/
cp docs/examples/keys.toml ~/.config/bascula/
chmod 600 ~/.config/bascula/keys.toml
```

Los servicios también crean `~/.bascula/` para logs y datos históricos. 【F:bascula/services/storage.py†L16-L25】

### Idempotencia de config.txt
`scripts/install-1-system.sh` invoca `tools/update-config.py` para mantener un bloque etiquetado "Bascula-Cam (Pi 5)" y otro "X735 v3" en `/boot/firmware/config.txt`, eliminando duplicados conflictivos (por ejemplo `dtparam=audio=on`). La primera ejecución genera una copia de seguridad `.bak`; si necesitas revertir cambios basta con restaurar ese archivo y volver a ejecutar la fase 1. Ejecutar el instalador varias veces no altera el contenido cuando no hay novedades (idempotente). 【F:scripts/install-1-system.sh†L90-L173】【F:tools/update-config.py†L1-L194】

## Variables de entorno clave

| Variable | Descripción | Valor por defecto |
| --- | --- | --- |
| `BASCULA_DEVICE`, `BASCULA_BAUD` | Fuerzan puerto y baudios de la báscula serie. 【F:bascula/services/scale.py†L86-L120】 | `/dev/serial0`, `115200` |
| `BASCULA_CMD_TARE`, `BASCULA_CMD_ZERO` | Comandos personalizados si el firmware no usa `T`/`C:<peso>`. 【F:bascula/core/scale_serial.py†L50-L105】 | Dependen del firmware |
| `BASCULA_SCALE_HOST_TARE` | Activa modo de tara/offset en host. `1` habilita conservar `offset/tare` del `scale.toml`. 【F:bascula/services/scale.py†L66-L104】 | `0` |
| `BASCULA_CFG_DIR` | Redefine la carpeta de configuración para UI, mini-web y servicios. 【F:bascula/ui/app.py†L37-L123】【F:bascula/services/wifi_config.py†L176-L200】 | `~/.config/bascula` |
| `BASCULA_WEB_HOST`, `BASCULA_WEB_PORT`, `BASCULA_MINIWEB_PORT` | Host/puerto de mini-web y endpoints FastAPI. Se escriben en `/etc/default/bascula`. 【F:scripts/install-2-app.sh†L48-L92】【F:bascula/services/wifi_config.py†L166-L214】 | `0.0.0.0`, `8080` |
| `BASCULA_APLAY_DEVICE`, `BASCULA_VOICE_*`, `BASCULA_VOLUME_BOOST` | Selección de dispositivo ALSA y parámetros de voz/beeps. 【F:bascula/services/audio.py†L104-L134】 | `plughw:MAX98357A,0`, valores internos |
| `BASCULA_PIPER_MODEL` | Ruta al modelo Piper TTS a utilizar. 【F:bascula/services/audio.py†L116-L128】 | Detecta desde `assets/voices` |
| `BASCULA_NIGHTSCOUT_URL`, `BASCULA_NIGHTSCOUT_TOKEN` | Sustituyen la configuración de `diabetes.toml` para alertas/overlay. 【F:bascula/services/alarmd.py†L239-L339】 | Vacío |
| `BASCULA_RUNTIME_DIR`, `BASCULA_PREFIX`, `BASCULA_VENV` | Directorios internos utilizados por los servicios systemd y OTA. 【F:scripts/install-2-app.sh†L48-L173】【F:systemd/bascula-alarmd.service†L10-L19】 | `/run/bascula`, `/opt/bascula/current`, `/opt/bascula/current/.venv` |
| `BASCULA_UI_CURSOR`, `BASCULA_NO_EMOJI` | Controles UI para ocultar cursor o desactivar emoji. 【F:bascula/ui/app_shell.py†L214-L236】【F:bascula/ui/screens.py†L47-L75】 | Desactivados |

### Modo kiosco Tkinter (fullscreen/undecorated)

- La función `apply_kiosk_window_prefs` en `bascula/ui/windowing.py` aplica `-fullscreen`, fija la ventana como `topmost`, bloquea `Escape` y ajusta la geometría al tamaño real de la pantalla al arrancar la UI. 【F:bascula/ui/windowing.py†L1-L78】
- Si la decoración persiste con el gestor de ventanas, exporta `BASCULA_KIOSK_STRICT=1` para activar `overrideredirect(True)` y suprimir cualquier barra residual. 【F:bascula/ui/windowing.py†L48-L66】
- Para sesiones de desarrollo se puede definir `BASCULA_DEBUG_KIOSK=1` y alternar fullscreen con `F11` (gestiona `overrideredirect` antes/después del cambio). 【F:bascula/ui/windowing.py†L68-L77】
- En instalaciones normales basta con el modo `-fullscreen`; el modo estricto sólo debe usarse si Openbox ignora la preferencia.

## Ejemplos de configuración TOML

Los ficheros de `docs/examples/` son sintácticamente válidos y listos para copiar/editar:

- `scale.toml`: puerto, factor, densidad y modo de tara. 【F:docs/examples/scale.toml†L1-L11】
- `diabetes.toml`: Nightscout, asistente de bolo y umbrales de alarmas. 【F:docs/examples/diabetes.toml†L1-L12】
- `ui.toml`: preferencias ligeras (mascota, temporizador, unidades). 【F:docs/examples/ui.toml†L1-L5】
- `keys.toml`: credenciales FatSecret bajo la tabla `[fatsecret]`. 【F:docs/examples/keys.toml†L1-L5】

## Solución de problemas

### Instalador

- Si `scripts/install-all.sh` muestra `[warn] Missing … (skipping)`, es esperado cuando ese drop-in opcional no está versionado en el repositorio.

### Pi OS Lite (Bookworm)

- Instala `xserver-xorg-legacy` y genera `/etc/X11/Xwrapper.config` con `allowed_users=anybody` y `needs_root_rights=yes` para habilitar `Xorg.wrap`. 【F:scripts/install-1-system.sh†L193-L210】
- La fase 2 crea `~/.xserverrc` con `exec /usr/lib/xorg/Xorg.wrap :0 vt1 -nolisten tcp -noreset` y el servicio `bascula-app` reserva `TTY1`, lo que evita conflictos con `getty@tty1` y el modo framebuffer. 【F:scripts/run-ui.sh†L67-L81】【F:systemd/bascula-app.service†L5-L40】
- Se purga `xserver-xorg-video-fbdev` y se genera `/etc/X11/xorg.conf.d/20-modesetting.conf` con `Option "kmsdev"` apuntando al DRM detectado por HDMI (`/dev/dri/cardX`). 【F:scripts/install-1-system.sh†L60-L188】【F:tools/update-config.py†L1-L194】
- Tras el arranque, comprueba el log de Xorg con `tail -n 200 ~/.local/share/xorg/Xorg.0.log` para validar que detecta `modesetting` y carga la configuración de `/etc/X11/xorg.conf.d`. 【F:scripts/install-2-app.sh†L322-L357】
- Ejecuta `scripts/smoke.sh` tras la instalación para verificar permisos de `Xorg.wrap`, `Xwrapper.config` y que `kmsdev` coincide con el HDMI activo. Si persiste `no screens found`, revisa `~/.local/share/xorg/Xorg.0.log` y el mapeo de `/sys/class/drm/`. 【F:scripts/smoke.sh†L1-L74】【F:scripts/install-1-system.sh†L60-L210】

### Cámara

- Ejecuta `python3 scripts/test_camera.py` para validar Picamera2 y capturar una imagen de prueba. 【F:scripts/test_camera.py†L1-L38】
- Si falla, verifica permisos de Video (`sudo usermod -aG video,render,input pi`) y reinstala dependencias con la Fase 1.

### Permisos `/dev/serial0`

- Usa `sudo scripts/fix-serial.sh` para añadir al usuario a `dialout`/`tty`, crear reglas `90-bascula.rules` y habilitar `enable_uart=1`. 【F:scripts/fix-serial.sh†L1-L52】
- Comprueba que `console=serial0,115200` no esté en `/boot/firmware/cmdline.txt` tras ejecutar el script. 【F:scripts/fix-serial.sh†L36-L44】

### Mini-web y puertos

- Edita `/etc/default/bascula` para cambiar `BASCULA_MINIWEB_PORT` o `BASCULA_WEB_PORT` y reinicia `sudo systemctl restart bascula-web`. 【F:scripts/install-2-app.sh†L48-L92】
- La unit `bascula-web` escucha en el host especificado (`0.0.0.0` por defecto); evita puertos inferiores a 1024 sin privilegios. 【F:systemd/bascula-web.service†L11-L19】

### Punto de acceso

- Para forzar la AP ejecuta de nuevo `sudo scripts/setup_ap_nm.sh`; revisa `nmcli connection show BasculaAP` si no arranca. 【F:scripts/setup_ap_nm.sh†L1-L73】
- Si otro servicio ocupa `wlan0`, detén `hostapd`/`dnsmasq` como hace el script antes de reintentar. 【F:scripts/setup_ap_nm.sh†L28-L46】

## Descargas OTA y mantenimiento

- `scripts/ota.sh` gestiona releases en `/opt/bascula/releases/<versión>` y actualiza el symlink `current`. 【F:scripts/ota.sh†L48-L136】
- Persiste estado de fallos en `/opt/bascula/shared/userdata` para recuperar la app tras errores repetidos. 【F:scripts/ota.sh†L50-L90】【F:scripts/ota.sh†L176-L214】

## Descargo de responsabilidad

Este proyecto no sustituye asesoría médica. Verifica toda recomendación nutricional o cálculo de bolo con tu equipo de salud antes de aplicarlo. Usa la báscula y sus servicios bajo tu propio riesgo.
