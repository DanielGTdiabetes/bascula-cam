# Instalación en un paso (OS Lite / Desktop) — v3.0 (NM AP, All-in)

Este proyecto incluye un **instalador todo-en-uno** (`scripts/install-all.sh`) que deja:

- La **UI (Tk)** en modo kiosco.  
- La **mini-web completa** (configuración API Key, Nightscout, etc.) en **puerto 8080**.  
- El **sistema IA local** (voz ASR, OCR, visión).  
- El **punto de acceso Wi-Fi de respaldo (AP fallback)** con **NetworkManager**.  

Funciona tanto sobre **Raspberry Pi OS with Desktop** como sobre **OS Lite** (el propio instalador añade el stack gráfico mínimo si no existe).

---

## ✅ Requisitos previos

- Raspberry Pi OS **Bookworm** recién instalado (Lite o Desktop).  
- Usuario con sudo (por defecto `pi`).  
- Conectividad a Internet (Wi-Fi o Ethernet) durante la instalación.  
- (Opcional) Conocer la **IP** de la Pi: `hostname -I`.

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
chmod +x install-all.sh
sudo ./install-all.sh
```

3) **Reinicia** cuando finalice:
```bash
sudo reboot
```

La báscula arrancará automáticamente en modo kiosco (pantalla completa) y la **mini-web** quedará disponible en **http://<IP>:8080/**.  
En modo AP, normalmente en **http://10.42.0.1:8080**.

---

## 🔧 ¿Qué hace el instalador? (resumen)

1. **Paquetes sistema**  
   - Python (venv/pip), dependencias nativas (Pillow/numpy), **Picamera2/libcamera/rpicam-apps**.  
   - Stack gráfico mínimo: `xserver-xorg`, `xinit`, `openbox`, `unclutter`, `fonts-dejavu*`, `python3-tk`.

2. **Pantalla (KMS)**  
   - Ajusta `/boot/firmware/config.txt` con **KMS** y resolución forzada **1024×600@60**.

3. **Servicios systemd**  
   - `bascula-app.service` → arranca la UI en kiosco (Tkinter).  
   - `bascula-web.service` → mini-web completa (puerto 8080).  
   - `ocr-service.service` → OCR (FastAPI en 127.0.0.1:8078).  

4. **NetworkManager + AP fallback**  
   - Instala y configura **NetworkManager**.  
   - Crea el perfil `BasculaAP` (SSID **Bascula_AP**, clave **bascula1234**, interfaz `wlan0`).  
   - Copia el dispatcher `scripts/nm-dispatcher/90-bascula-ap-fallback`.  
   - En ausencia de Wi-Fi conocida, la Pi levanta su propio AP → panel accesible en `http://10.42.0.1:8080`.

5. **IA local (activada siempre)**  
   - **ASR** → Whisper.cpp (`hear.sh`).  
   - **OCR** → Tesseract + FastAPI (`http://127.0.0.1:8078/ocr`).  
   - **OCR robusto** → PaddleOCR.  
   - **Visión** → TFLite (`classify.py`).

6. **Audio / Voz**  
   - Instala **Piper TTS** (modelo español por defecto) + fallback con `espeak-ng`.  
   - Crea script `say.sh`.  
   - Crea script `mic-test.sh`.

---

## ✅ Verificaciones post-instalación

1) **Servicio principal (UI)**  
```bash
systemctl status bascula-app.service --no-pager
```

2) **Mini-web**  
```bash
journalctl -u bascula-web.service -n 80 --no-pager
```

3) **OCR local**  
```bash
curl -F "file=@ejemplo.png" http://127.0.0.1:8078/ocr
```

4) **AP fallback**  
- Apaga tu Wi-Fi normal.  
- La Pi emitirá `Bascula_AP` (clave `bascula1234`).  
- Conéctate y abre: `http://10.42.0.1:8080`.

---

## 🧪 Problemas comunes

- **Pantalla negra / sin UI** → revisa `/boot*/config.txt`, confirma resolución 1024×600.  
- **Sin mini-web en AP** → asegúrate de conectar a la red `Bascula_AP` y usar la IP `10.42.0.1`.  
- **Cámara no detectada** → prueba `libcamera-hello`.  

---

## ♻️ Actualizaciones OTA

- Desde la UI: pestaña **“Acerca de” → OTA**.  
- Rollback automático si falla el smoke test.
