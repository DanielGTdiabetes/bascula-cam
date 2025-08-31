# -*- coding: utf-8 -*-
"""
CameraService sencillo para Raspberry Pi Zero 2 W.

Esta implementación evita configuraciones complejas y se centra en la
compatibilidad y estabilidad para la Raspberry Pi Zero 2 W con la cámara
Module 3 Wide. Proporciona vista previa en Tkinter usando `ImageTk` y
captura imágenes JPEG en un directorio configurable. Si `picamera2` o
Pillow no están disponibles, el servicio se degradará de forma segura y
mostrará mensajes informativos.

Principales características:

* Resolución predeterminada moderada (640×480) para no saturar la CPU.
* Tasa de fotogramas razonable (10 fps) ajustable mediante parámetro.
* Preview mediante bucle `after()` en el hilo principal de Tkinter.
* Capturas a fichero JPEG mediante `picamera2.capture_file()`, con
  fallback a captura por array si fuese necesario.
* Método `available()` que comprueba la disponibilidad de la cámara y
  de Pillow, de forma que la UI pueda reaccionar adecuadamente.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional

# Intentamos importar las dependencias opcionales. No fallamos si no
# están instaladas para permitir un fallback elegante.
try:
    from picamera2 import Picamera2
    PICAM_AVAILABLE = True
except Exception:
    PICAM_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


class CameraUnavailable(Exception):
    """Se lanza cuando la cámara no está disponible o falla en uso."""
    pass


class CameraService:
    """
    Servicio de cámara simplificado para Raspberry Pi.

    El objetivo es ofrecer una interfaz mínima para iniciar una vista
    previa en un widget Tkinter y capturar imágenes a disco. El
    constructor permite ajustar la resolución de preview y la tasa de
    fotogramas. En hardware modesto como la Pi Zero 2 W conviene
    mantener estos valores bajos para evitar saturar la CPU.
    """

    def __init__(self, width: int = 640, height: int = 480, fps: int = 10,
                 save_dir: str = "captures") -> None:
        # Guardamos parámetros, limitándolos a valores sensatos. Se evita
        # configurar resoluciones muy grandes en este hardware.
        self.width = max(1, min(int(width), 1920))
        self.height = max(1, min(int(height), 1080))
        self.fps = max(1, min(int(fps), 30))
        # Intervalo de actualización en milisegundos para el after() de Tk.
        self.interval_ms = int(1000 / self.fps)

        # Directorio donde se guardarán las capturas.
        self.save_dir = os.path.abspath(save_dir)
        os.makedirs(self.save_dir, exist_ok=True)

        # Propiedades internas.
        self.picam: Optional[Picamera2] = None
        self._previewing: bool = False
        self._last_frame_tk: Optional[ImageTk.PhotoImage] = None
        self._bound_widget = None

        # Si picamera está disponible, inicializamos la cámara.
        if PICAM_AVAILABLE:
            try:
                self.picam = Picamera2()
                # Configuración básica de vídeo. No especificamos formato
                # concreto; Picamera2 elegirá uno razonable para RGB.
                video_config = self.picam.create_video_configuration(
                    main={"size": (self.width, self.height)}
                )
                self.picam.configure(video_config)
                # Activamos autoexposición y balance de blancos si se soporta.
                try:
                    self.picam.set_controls({
                        "AwbEnable": True,
                        "AeEnable": True,
                    })
                except Exception:
                    pass
            except Exception:
                # Si algo falla, dejamos self.picam en None para degradar.
                self.picam = None

    def available(self) -> bool:
        """
        Devuelve True si Picamera2 y Pillow están disponibles y la
        cámara se ha inicializado correctamente.
        """
        return bool(self.picam and PICAM_AVAILABLE and PIL_AVAILABLE)

    # ------------------------------------------------------------------
    # PREVIEW
    # ------------------------------------------------------------------
    def preview_to_tk(self, label_widget) -> Callable[[], None]:
        """
        Inicia la vista previa en un `tk.Label` proporcionado.

        Si la cámara o Pillow no están disponibles, muestra un mensaje
        informativo en el label y devuelve un stopper que no hace nada.
        En caso contrario, inicia la cámara (si no lo estaba) y
        programa un bucle de actualización con `after()`.

        :param label_widget: widget Tkinter donde dibujar la imagen
        :return: función que detiene la vista previa cuando se llama
        """
        # Verificamos Pillow primero. Sin PIL no hay preview.
        if not PIL_AVAILABLE:
            label_widget.configure(
                text="Vista previa requiere Pillow",
                bg="#1a1f2e",
                fg="#cccccc",
                font=("monospace", 12),
            )
            return lambda: None

        # Verificamos la cámara.
        if not self.picam:
            label_widget.configure(
                text="Cámara no disponible",
                bg="#1a1f2e",
                fg="#ff6666",
                font=("monospace", 12),
            )
            return lambda: None

        # Guardamos el widget para las actualizaciones.
        self._bound_widget = label_widget
        if not self._previewing:
            self._previewing = True
            try:
                # Ponemos la cámara en marcha; start() es idempotente.
                self.picam.start()
            except Exception:
                # Si no podemos arrancar, mostramos mensaje y no hacemos nada más.
                label_widget.configure(
                    text="Error iniciando cámara",
                    bg="#1a1f2e",
                    fg="#ff6666",
                    font=("monospace", 12),
                )
                return lambda: None
            # Lanzamos la primera actualización.
            self._schedule_next()

        def stop():
            # Detiene el bucle de preview. No para la cámara para poder
            # reutilizarla en capturas posteriores.
            self._previewing = False
            self._bound_widget = None

        return stop

    def _schedule_next(self):
        """Programa la próxima actualización de preview."""
        if not self._previewing or not self._bound_widget:
            return
        self._bound_widget.after(self.interval_ms, self._update_frame)

    def _update_frame(self):
        """Obtiene una imagen de la cámara y la dibuja en el widget."""
        if not (self._previewing and self._bound_widget and self.picam):
            return
        try:
            # Capturamos un array RGB (HxWx3)
            arr = self.picam.capture_array()
            if arr is None:
                return
            # Convertimos a Image para usar con ImageTk
            img = Image.fromarray(arr)
            # Redimensionamos manteniendo aspecto para encajar en el label.
            try:
                w = max(1, self._bound_widget.winfo_width())
                h = max(1, self._bound_widget.winfo_height())
                img.thumbnail((w, h), Image.Resampling.LANCZOS)
            except Exception:
                img.thumbnail((self.width, self.height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image=img)
            # Guardamos referencia para que no sea recolectado por GC.
            self._last_frame_tk = photo
            # Actualizamos la imagen en el widget.
            self._bound_widget.configure(image=photo)
        except Exception:
            # Silenciamos la excepción para no saturar el log.
            pass
        finally:
            # Programamos la siguiente actualización.
            self._schedule_next()

    # ------------------------------------------------------------------
    # CAPTURA
    # ------------------------------------------------------------------
    def capture_still(self, path: Optional[str] = None) -> str:
        """
        Captura una imagen JPEG utilizando la cámara.

        Si se indica `path` se usará esa ruta; en caso contrario se genera
        un nombre único en `save_dir`. Si la cámara no está disponible,
        se lanzará `CameraUnavailable`.
        """
        if not self.picam:
            raise CameraUnavailable("Picamera2 no disponible")
        # Determinar ruta destino
        if path is None:
            ts = int(time.time())
            path = os.path.join(self.save_dir, f"capture_{ts}.jpg")
        try:
            # Guardamos directamente a fichero; es más eficiente que
            # capturar array y luego guardar.
            self.picam.capture_file(path)
        except Exception:
            # Si la captura directa falla, hacemos fallback a captura por array.
            try:
                arr = self.picam.capture_array()
                if arr is None:
                    raise CameraUnavailable("Array vacío en captura")
                Image.fromarray(arr).save(path, format="JPEG", quality=85)
            except Exception as e:
                raise CameraUnavailable(f"Error en captura: {e}")
        return path

    # ------------------------------------------------------------------
    # PARADA
    # ------------------------------------------------------------------
    def stop(self) -> None:
        """
        Detiene la cámara y cancela la vista previa. Puede ser
        invocado de forma segura tanto si la cámara está o no activa.
        """
        self._previewing = False
        self._bound_widget = None
        if self.picam:
            try:
                self.picam.stop()
            except Exception:
                pass

    def __del__(self):
        """Destructor para limpiar recursos al recolectar el objeto."""
        try:
            self.stop()
        except Exception:
            pass
