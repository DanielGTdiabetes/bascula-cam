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
- (Opcional) I2S MAX98357A: si se define `ENABLE_I2S=1`, añade los overlays en `config.txt`.

## Seguridad

- La mini‑web quedará accesible en la red. Mantén el PIN, usa redes confiables
  y no expongas 8080 directamente a Internet sin una capa adicional.
- Para volver a solo‑localhost: `make local-only`.

## Diagnóstico

- Logs mini‑web: `journalctl -u bascula-web.service -f`
- Comprobación general: `make doctor`
- Ver URL/PIN: `make show-url` y `make show-pin`

## Variables de entorno útiles

- `BASCULA_USER` (por defecto `bascula`)
- `BASCULA_REPO_URL`, `BASCULA_REPO_DIR`
- `GIT_SSH_KEY_BASE64` (si se usa repo privado por SSH), `BASCULA_REPO_SSH_URL`
- `ENABLE_UART=1|0`
- `ENABLE_I2S=1|0`
- `BASCULA_AP_SSID` (por defecto `BasculaAP`), `BASCULA_AP_PSK` (por defecto `12345678`)
- `BASCULA_APLAY_DEVICE` (para forzar dispositivo `aplay`, p.ej. `plughw:MAX98357A,0`)
