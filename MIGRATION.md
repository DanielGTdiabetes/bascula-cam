# Migración a la interfaz RPi 2024

Este documento describe los pasos recomendados para migrar instalaciones existentes de Báscula Cam a la nueva interfaz optimizada para Raspberry Pi 5.

## 1. Requisitos previos
- Raspberry Pi OS Lite actualizado (Bookworm).
- Python 3.11 con virtualenv creado en `~/bascula-cam/.venv`.
- Dependencias del backend instaladas (`pip install -r requirements.txt`).
- Acceso físico a la pantalla táctil de 7" (1024×600) y a la báscula serie.

## 2. Respaldo
1. Detener servicios `bascula-ui.service` y `bascula-miniweb.service`.
2. Realizar copia de seguridad de `~/.config/bascula/` y de `bascula/config/*.json`.
3. Guardar una imagen del sistema en caso de rollback completo.

## 3. Actualización del repositorio
```bash
cd ~/bascula-cam
git pull
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Reconstrucción opcional de assets
La nueva mascota es vectorial. Si en el futuro se añaden SVG externos ejecute:
```bash
./scripts/build-mascot-assets.sh
```
El script verificará la presencia de `bascula/ui/assets/mascota/*.svg` y generará PNG en `bascula/ui/assets/mascota/_gen/`.

## 5. Configuración
- Revisar `~/.config/bascula/ui.json` para ajustar `vision_model`, `vision_labels` o parámetros de cámara.
- El nuevo archivo `bascula/ui/rpi_config.py` define colores y tamaños táctiles; puede personalizarse vía variables de entorno.

## 6. Verificación
Ejecutar las herramientas automáticas:
```bash
./scripts/verify-scale.sh
./scripts/verify-kiosk.sh
python tools/check_scale.py
python tools/smoke_nav.py
python tools/smoke_mascot.py
```
Todas deben finalizar con código 0. Revise los logs en `logs/ui.log`.

## 7. Reinicio de servicios
```bash
sudo systemctl daemon-reload
sudo systemctl restart bascula-ui.service
sudo systemctl restart bascula-miniweb.service
```

## 8. Validación final
- Confirmar que la pantalla Home muestra la mascota y responde al tacto.
- Pesar un alimento y verificar que la transición a la pantalla de confirmación es fluida (<300 ms).
- Comprobar que el historial del día enumera los alimentos y que los botones “ENVIAR” y “LIMPIAR” responden.
- Revisar `topbar` para asegurar presencia de iconos y menú overflow.

