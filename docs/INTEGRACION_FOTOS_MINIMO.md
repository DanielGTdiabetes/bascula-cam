# Integración mínima y segura de fotos (sin tocar tu `camera.py`)

Este paquete añade **captura de fotos efímeras** usando tu cámara actual **sin reemplazar** tu `camera.py`.

## Archivos incluidos
- `bascula/services/photo_manager.py` — gestor de fotos (guardar en `~/.bascula/photos/staging/` y borrar tras uso).

## Uso (sin modificar tu servicio de cámara)
1. Importa y crea el gestor UNA sola vez donde ya tengas tu instancia `picam2` (reutilizarla es clave):
```python
from bascula.services.photo_manager import PhotoManager

self.photo_manager = PhotoManager(logger=self.logger)  # o el logger que uses
self.photo_manager.attach_camera(self.camera.picam2)   # reutiliza tu picam2 existente
```

2. En tus handlers de botones, captura y borra de inmediato:
```python
# AÑADIR ALIMENTO
p = self.photo_manager.capture(label="add_item")
self.photo_manager.mark_used(p)

# PLATO ÚNICO / CERRAR PLATO
p = self.photo_manager.capture(label="close_plate")
self.photo_manager.mark_used(p)

# TEST (Ajustes)
p = self.photo_manager.capture(label="test-button")
self.photo_manager.mark_used(p)
```

> Si necesitas conservar temporalmente algunas fotos para depurar, edita `~/.bascula/photos/config.json` y pon `keep_last_n_after_use` a un número mayor que 0.
> Los límites por defecto: máximo 500 fotos o 800 MB en `~/.bascula/photos/staging/` (el gestor limpia lo antiguo).

## Requisitos
- `python3-picamera2` instalado en el sistema.
- `Pillow` instalado en tu venv (está en `requirements.txt`).

## Garantía de no interferencia
- No se crea nueva `Picamera2`: se **usa la tuya**.
- No se llama a `start()` ni `stop()`: solo se captura con `capture_file(...)` o, si falla, con `capture_array()`.
- No toca tu ciclo de preview ni la configuración de la cámara.
