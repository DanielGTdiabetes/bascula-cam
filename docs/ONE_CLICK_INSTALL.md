# Instalación en un paso (One‑Click)

Este repositorio incluye un script de instalación "todo en uno" para
Raspberry Pi OS (Bookworm) que deja lista la mini‑web y la UI en modo kiosco.

## Uso

1) Descargar y ejecutar como root:

```bash
curl -fsSL https://<TU_URL>/install-all.sh -o install.sh
sudo bash install.sh
```

- Variables opcionales: `BASCULA_USER=pi`, `BASCULA_REPO_URL=...`, `BASCULA_REPO_DIR=...`
 - Repos privados: define `GIT_SSH_KEY_BASE64` (clave privada en base64) y opcionalmente
   `BASCULA_REPO_SSH_URL` (si no, convierte automáticamente https→ssh para GitHub).

## ¿Qué hace?

- Instala paquetes del sistema: Xorg mínimo, NetworkManager, venv, `python3-picamera2`, etc.
- Crea (si no existe) el usuario de servicio `bascula` y añade grupos necesarios.
- Clona/actualiza este repo en `~bascula/bascula-cam`.
- Crea un venv `.venv` con `--system-site-packages` y instala `requirements.txt`.
- Configura polkit para `nmcli` sin sudo para el usuario de servicio.
- Instala el servicio `bascula-web.service` y le aplica un override:
  - Usa el venv para `ExecStart`
  - `BASCULA_WEB_HOST=0.0.0.0` (accesible desde cualquier red)
  - Limpia filtros `IPAddressAllow/Deny` y permite IPv4+IPv6
- Activa modo kiosco: autologin en TTY1 + `.bash_profile` + `.xinitrc` que lanza `scripts/run-ui.sh`.

## Extras incluidos

- Git + SSH para el usuario `bascula`:
  - Genera clave `~/.ssh/id_ed25519` y muestra la pública para añadirla en GitHub.
  - Crea `~/.ssh/config` con `StrictHostKeyChecking accept-new` para `github.com`.
- Audio: intenta detectar Hifiberry/I2S y exporta `BASCULA_APLAY_DEVICE` automáticamente; instala ALSA y `espeak-ng`.
- AP de emergencia (fallback): instala dispatcher de NetworkManager y crea la conexión `BasculaAP` con clave por defecto `12345678`.
- UART (serie): activa `enable_uart=1`, desactiva BT con `dtoverlay=disable-bt` y quita `console=serial0` del `cmdline.txt`.
- I2S MAX98357A: activado por defecto (añade overlays en `config.txt`).
  - Para desactivar: ejecuta con `ENABLE_I2S=0`.

## Seguridad

- La mini‑web quedará accesible en la red. Mantén el PIN, usa redes confiables
  y no expongas 8080 directamente a Internet sin una capa adicional.
- Para volver a solo‑localhost: `make local-only`.
- El instalador configura polkit para:
  - NetworkManager sin sudo (solo para el usuario de servicio).
  - Reiniciar/arrancar/parar exclusivamente `bascula-web.service` sin contraseña.

## Diagnóstico

- Logs mini‑web: `journalctl -u bascula-web.service -f`
- Comprobación general: `make doctor`
- Ver URL/PIN: `make show-url` y `make show-pin`

## Actualizaciones (OTA)

- Desde la UI: pestaña “Acerca de” → “OTA”.
  - Botón “Comprobar actualización”: verifica si hay commits nuevos en el remoto.
  - Botón “Actualizar ahora”: realiza `git fetch` y actualiza el repo a la última versión de la rama remota (con rollback automático si el smoke test falla), instala dependencias en el venv y muestra el estado.
  - Reinicio mini‑web: la UI puede reiniciar automáticamente el servicio mini‑web tras actualizar (opción marcada por defecto) o manualmente con el botón “Reiniciar mini‑web”.
  - Tras actualizar: si no se reinicia automáticamente, reinicia la app para aplicar cambios. La mini‑web también puede aplicarse reiniciando su servicio.
- Requisitos: conexión a Internet y árbol Git limpio (sin cambios locales).
- Mini‑web: para aplicar código nuevo sin reiniciar, ejecuta `systemctl restart bascula-web.service` (sin sudo, gracias a polkit).

## Variables de entorno útiles

- `BASCULA_USER` (por defecto `bascula`)
- `BASCULA_REPO_URL`, `BASCULA_REPO_DIR`
- `GIT_SSH_KEY_BASE64` (si se usa repo privado por SSH), `BASCULA_REPO_SSH_URL`
- `ENABLE_UART=1|0`
- `ENABLE_I2S=1|0` (por defecto 1)
- `BASCULA_AP_SSID` (por defecto `BasculaAP`), `BASCULA_AP_PSK` (por defecto `12345678`)
- `BASCULA_APLAY_DEVICE` (para forzar dispositivo `aplay`, p.ej. `plughw:MAX98357A,0`)
