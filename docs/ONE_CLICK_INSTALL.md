# Instalación en un paso (OS Lite / Desktop) — v2.1_persist

Este proyecto incluye un **instalador todo‑en‑uno** que deja la **UI (Tk) en modo kiosco**, la **mini‑web** y el **sistema OTA con rollback** listos en **Raspberry Pi OS Bookworm**. Funciona tanto sobre **Raspberry Pi OS with Desktop** como sobre **OS Lite** (el propio instalador añade el stack gráfico mínimo si no existe).

> **Script recomendado:** `scripts/install-all_v2.1_persist.sh`

---

## ✅ Requisitos previos

- Raspberry Pi OS **Bookworm** recién instalado (Lite o Desktop).  
- Usuario con sudo (por defecto `pi`).  
- Conectividad a Internet (Wi‑Fi o Ethernet) **durante** la instalación.  
- (Opcional) Conocer la **IP** de la Pi: `hostname -I`.

> **Sugerencia:** Si usas **OS Lite**, no instales manualmente Xorg ni Picamera2. El instalador los configura por ti (Xorg, xinit, openbox, x11‑utils, fuentes DejaVu, unclutter, python3‑tk, libcamera, rpicam‑apps, python3‑picamera2…).

---

## 🚀 Uso rápido (TL;DR)

1) Conéctate por SSH o abre terminal en la Pi y **clona el repo**:
```bash
cd ~
git clone https://github.com/DanielGTdiabetes/bascula-cam.git
cd bascula-cam/scripts
```

2) **Ejecuta el instalador** (como root):
```bash
chmod +x install-all_v2.1_persist.sh
sudo ./install-all_v2.1_persist.sh
```

3) **Reinicia** cuando finalice:
```bash
sudo reboot
```

La báscula arrancará automáticamente en modo kiosco (pantalla completa) y la **mini‑web** quedará disponible en el puerto indicado (por defecto 8080).

---

## 🧭 Alternativas de ejecución

### A) Copiando el instalador por `scp` (ideal para repos privados)
En tu PC:
```bash
scp /ruta/local/install-all_v2.1_persist.sh pi@<IP_PI>:~/
```

En la Pi:
```bash
ssh pi@<IP_PI>
sudo bash ~/install-all_v2.1_persist.sh
```

### B) Vía `curl` (si publicas el instalador en una URL)
```bash
curl -fsSL https://<TU_URL>/install-all_v2.1_persist.sh -o install.sh
sudo bash install.sh
```

> **Privado por SSH**: exporta `GIT_SSH_KEY_BASE64` (clave privada en base64) y `BASCULA_REPO_SSH_URL` antes de ejecutar el instalador (ver “Variables de entorno”).

---

## 🔧 ¿Qué hace el instalador? (resumen)

1. **Paquetes sistema**  
   - Python (venv/pip), dependencias nativas (Pillow/numpy), **Picamera2/libcamera/rpicam‑apps**.  
   - **Stack gráfico mínimo** si falta: `xserver-xorg`, `xinit`, `openbox`, `x11-xserver-utils`, `unclutter`, `fonts-dejavu*`, `python3-tk`.
2. **Gráfica / KMS / HDMI**  
   - Ajusta `/boot/firmware/config.txt` (o `/boot/config.txt`) con **KMS** y `hdmi_force_hotplug=1` + `hdmi_cvt` (1024×600@60 por defecto) para evitar el clásico “no screens found”.  
   - Escribe `/etc/X11/Xwrapper.config` con:  
     ```
     allowed_users=anybody
     needs_root_rights=yes
     ```
3. **Servicios systemd**  
   - **App en kiosco**: autologin + `startx`/`.xinitrc` o servicio dedicado que llama a `xinit` → sesión `/usr/local/bin/bascula-xsession` (DPMS off, cursor oculto, lanza `scripts/run-ui.sh`).  
   - **Mini‑web** (puerto 8080 por defecto).  
   - **Health check** (timer) y **Updater OTA** (timer) con **rollback automático** si falla el “smoke test”.
4. **NetworkManager + AP**  
   - Instala/activa **NetworkManager**, crea AP de emergencia `BasculaAP` (PSK por defecto `12345678`), y aplica permisos (polkit) para gestionar Wi‑Fi sin sudo desde la mini‑web.  
5. **Repo + venv**  
   - Clona/actualiza el repo en `~/<usuario>/bascula-cam`.  
   - Crea **venv** con `--system-site-packages` e instala `requirements.txt`.
6. **Audio / UART / I2S (opcional)**  
   - Ajustes de ALSA / detección de dispositivo `aplay`.  
   - Activa `enable_uart=1` y overlay I2S MAX98357A si están habilitados por variables.

---

## 🌐 Variables de entorno útiles

Puedes pasarlas **antes** de ejecutar el script, por ejemplo:
```bash
sudo AP_SSID="BasculaAP" AP_PSK="una_clave_fuerte" HDMI_W=1024 HDMI_H=600 HDMI_FPS=60      BASCULA_REPO_URL="https://github.com/DanielGTdiabetes/bascula-cam.git"      ./install-all_v2.1_persist.sh
```

- **Repo/usuario**
  - `BASCULA_USER` (por defecto `pi` o el usuario desde `sudo`).
  - `BASCULA_REPO_URL` (por defecto GitHub HTTPS).  
  - `BASCULA_REPO_SSH_URL` (si usas SSH).  
  - `GIT_SSH_KEY_BASE64` (clave SSH en base64 para clonar privados).
- **Pantalla/HDMI**
  - `HDMI_W`, `HDMI_H`, `HDMI_FPS` (por defecto `1024x600@60`).
- **Access Point**
  - `AP_SSID` (por defecto `BasculaAP`), `AP_PSK` (por defecto `12345678`), `AP_CHANNEL` (por defecto `6`).
- **Audio** (si aplica)
  - `BASCULA_APLAY_DEVICE`, `BASCULA_VOLUME_BOOST`, `BASCULA_BEEP_GAIN`, `BASCULA_VOICE_SPEED`, `BASCULA_VOICE_AMPL`.
- **Interfaces opcionales**
  - `ENABLE_UART=1|0`, `ENABLE_I2S=1|0` (1 por defecto si el script lo soporta).

---

## ✅ Verificaciones post‑instalación

1) **Servicio principal**  
```bash
systemctl status bascula --no-pager
```

2) **Mini‑web**  
```bash
journalctl -u bascula-web.service -n 80 --no-pager
```

3) **Sesión X / Tk** (si hubiera dudas)  
```bash
pgrep -a Xorg || pgrep -a Xwayland || echo "No X server"
echo "DISPLAY=$DISPLAY"
```

4) **Cámara**  
```bash
libcamera-hello -t 1000
python3 -c "import picamera2, PIL, numpy; print('OK Picamera2 + Pillow + numpy')"
```

---

## 🧪 Problemas comunes y solución rápida

- **Pantalla en negro / no aparece UI**  
  - Revisa `/boot*/config.txt` (sección HDMI/KMS), prueba con otra resolución (`HDMI_W/H`).  
  - Comprueba `systemctl status bascula` y `~/<usuario>/app.log`.
- **“no display name and no $DISPLAY”**  
  - Indica que la sesión X no está activa: revisa el servicio `bascula` y que `xorg/xinit` estén instalados (el script debería haberlos instalado).
- **Cámara no inicializa**  
  - Asegúrate de tener `/dev/video*`. Ejecuta `libcamera-hello` para comprobar libcamera.
- **Mini‑web no accesible**  
  - Verifica `bascula-web.service` y que no haya un firewall bloqueando el puerto.

---

## 🔐 Seguridad

- La mini‑web puede quedar accesible en la red. Usa un **PIN** y redes confiables.  
- No expongas el puerto 8080 a Internet sin una capa extra.  
- Polkit permite gestionar Wi‑Fi/servicios sin contraseña **solo** al usuario de servicio.

---

## ♻️ Actualizaciones OTA

- Desde la UI: pestaña **“Acerca de” → OTA**.  
- Requiere Internet y repo sin cambios locales.  
- El updater hace rollback si el **smoke test** falla.

---

## 🧹 Desinstalación rápida (básica)

> **Cuidado:** esto detiene y deshabilita servicios, pero no restaura todos los archivos del sistema.

```bash
sudo systemctl disable --now bascula bascula-web.service || true
sudo rm -f /etc/systemd/system/bascula.service
sudo systemctl daemon-reload
```

---

**¿Dudas o mejoras?** Dímelo y lo afinamos para tu caso (por ejemplo, cambiar la resolución por defecto, puerto de la mini‑web, o integración con tu AP corporativo).
