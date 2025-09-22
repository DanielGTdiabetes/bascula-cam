# InstalaciÃ³n en un paso (OS Lite / Desktop) â€” v3.0 (NM AP, All-in)

Este proyecto incluye un **instalador todo-en-uno** (`scripts/install-all.sh`) que deja:

- La **UI (Tk)** en modo kiosco.  
- La **mini-web completa** (configuraciÃ³n API Key, Nightscout, etc.) en **puerto 8080**.  
- El **sistema IA local** (voz ASR, OCR, visiÃ³n).  
- El **punto de acceso Wi-Fi de respaldo (AP fallback)** con **NetworkManager**.  

Funciona tanto sobre **Raspberry Pi OS with Desktop** como sobre **OS Lite** (el propio instalador aÃ±ade el stack grÃ¡fico mÃ­nimo si no existe).

---

## âœ… Requisitos previos

- Raspberry Pi OS **Bookworm** reciÃ©n instalado (Lite o Desktop).  
- Usuario con sudo (por defecto `pi`).  
- Conectividad a Internet (Wi-Fi o Ethernet) durante la instalaciÃ³n.  
- (Opcional) Conocer la **IP** de la Pi: `hostname -I`.

---

## ðŸš€ Uso rÃ¡pido (TL;DR)

1) ConÃ©ctate por SSH o abre terminal en la Pi y **clona el repo**:
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

La bÃ¡scula arrancarÃ¡ automÃ¡ticamente en modo kiosco (pantalla completa) y la **mini-web** quedarÃ¡ disponible en **http://<IP>:8080/**.  
En modo AP, normalmente en **http://10.42.0.1:8080**.

---

## ðŸ”§ Â¿QuÃ© hace el instalador? (resumen)

1. **Paquetes sistema**  
   - Python (venv/pip), dependencias nativas (Pillow/numpy), **Picamera2/libcamera/rpicam-apps**.  
   - Stack grÃ¡fico mÃ­nimo: `xserver-xorg`, `xinit`, `openbox`, `unclutter`, `fonts-dejavu*`, `python3-tk`.

2. **Pantalla (KMS)**  
   - Ajusta `/boot/firmware/config.txt` con **KMS** y resoluciÃ³n forzada **1024Ã—600@60**.

3. **Servicios systemd**  
   - `bascula-app.service` â†’ arranca la UI en kiosco (Tkinter).  
   - `bascula-web.service` â†’ mini-web completa (puerto 8080).  
   - `ocr-service.service` â†’ OCR (FastAPI en 127.0.0.1:8078).  

4. **NetworkManager + AP fallback**  
   - Instala y configura **NetworkManager**.  
   - Crea el perfil `BasculaAP` (SSID **Bascula_AP**, clave **bascula1234**, interfaz `wlan0`).  
   - Copia el dispatcher `scripts/nm-dispatcher/90-bascula-ap`.
   - En ausencia de conectividad (sin ruta por defecto), la Pi levanta `Bascula_AP` y la mini-web responde en `http://10.42.0.1:8080`.

5. **IA local (activada siempre)**  
   - **ASR** â†’ Whisper.cpp (`hear.sh`).  
   - **OCR** â†’ Tesseract + FastAPI (`http://127.0.0.1:8078/ocr`).  
   - **OCR robusto** â†’ PaddleOCR.  
   - **VisiÃ³n** â†’ TFLite (`classify.py`).

6. **Audio / Voz**  
   - Instala **Piper TTS** (modelo espaÃ±ol por defecto) + fallback con `espeak-ng`.  
   - Crea script `say.sh`.  
   - Crea script `mic-test.sh`.

---

## âœ… Verificaciones post-instalaciÃ³n

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
- La Pi emitirÃ¡ `Bascula_AP` (clave `bascula1234`).  
- ConÃ©ctate y abre: `http://10.42.0.1:8080`.

---

## ðŸ§ª Problemas comunes

- **Pantalla negra / sin UI** â†’ revisa `/boot*/config.txt`, confirma resoluciÃ³n 1024Ã—600.  
- **Sin mini-web en AP** â†’ asegÃºrate de conectar a la red `Bascula_AP` y usar la IP `10.42.0.1`.  
- **CÃ¡mara no detectada** â†’ prueba `libcamera-hello`.  

---

## â™»ï¸ Actualizaciones OTA

- Desde la UI: pestaÃ±a **â€œAcerca deâ€ â†’ OTA**.  
- Rollback automÃ¡tico si falla el smoke test.

---

### Voz Piper (nota)

- El instalador intenta descargar una voz española de Piper. Si falla, usa espeak-ng como fallback.
- Puedes forzar una voz concreta exportando PIPER_VOICE antes de ejecutar el instalador. Ejemplos:
  - PIPER_VOICE=es_ES-mls_10246-medium
  - PIPER_VOICE=es_ES-mls_10246-low
  - PIPER_VOICE=es_ES-carlfm-medium
- También puedes colocar paquetes .tar.gz de voces en /boot/bascula-offline/piper-voices/ para instalación offline.

---

## Instalación en dos fases (recomendada en Pi 5)

1) Fase 1 — Sistema (requiere reinicio):

`ash
cd ~/bascula-cam/scripts
sudo bash ./install-1-system.sh
sudo reboot
`

2) Fase 2 — App y servicios:

`ash
cd ~/bascula-cam/scripts
sudo bash ./install-2-app.sh
`

Notas:
- La Fase 1 configura paquetes base, cámara (libcamera/rpicam), UART, HDMI/KMS, polkit/NM.
- La Fase 2 despliega la app en /opt/bascula/current, crea el venv, instala dependencias, servicios systemd, voz/OCR, y el AP fallback.
- Puedes seguir usando install-all.sh directamente (PHASE=all por defecto).

---

## Instalación en dos fases (recomendada en Pi 5)

1) Fase 1 — Sistema (requiere reinicio):

`ash
cd ~/bascula-cam/scripts
sudo bash ./install-1-system.sh
sudo reboot
`

2) Fase 2 — App y servicios:

`ash
cd ~/bascula-cam/scripts
sudo bash ./install-2-app.sh
`

Notas:
- La Fase 1 configura paquetes base, cámara (libcamera/rpicam), UART, HDMI/KMS, polkit/NM.
- La Fase 2 despliega la app en /opt/bascula/current, crea el venv, instala dependencias, servicios systemd, voz/OCR, y el AP fallback.
- Puedes seguir usando install-all.sh directamente (PHASE=all por defecto).
