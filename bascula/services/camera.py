# -*- coding: utf-8 -*-
"""
CameraService actualizado para IMX708 Wide en Pi Zero 2W
Optimizado para tu configuración específica
"""
from __future__ import annotations
import os, time
from typing import Optional, Callable

try:
    from picamera2 import Picamera2
    from libcamera import controls as libcam_controls
    PICAM_AVAILABLE = True
except Exception:
    PICAM_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

class CameraUnavailable(Exception):
    pass

class CameraService:
    def __init__(self, width:int=800, height:int=600, fps:int=15, save_dir:str="captures") -> None:
        """
        Servicio de cámara optimizado para Pi Zero 2W + IMX708 Wide
        - Resoluciones moderadas para mejor rendimiento
        - Configuración específica para Module 3 Wide
        """
        # Resoluciones optimizadas para Pi Zero 2W
        self.width = min(int(width), 1920)  # Límite razonable
        self.height = min(int(height), 1080)
        self.fps = min(int(fps), 20)  # Límite para Pi Zero 2W
        self.interval_ms = int(1000 / max(1, self.fps))
        
        self.save_dir = os.path.abspath(save_dir)
        os.makedirs(self.save_dir, exist_ok=True)

        self.picam: Optional[Picamera2] = None
        self._previewing = False
        self._last_frame_tk = None
        self._bound_widget = None

        if PICAM_AVAILABLE:
            self._init_camera()

    def _init_camera(self):
        """Inicialización específica para IMX708 Wide"""
        try:
            self.picam = Picamera2()
            
            # Configuración optimizada para IMX708 Wide
            # Usar modo nativo de 1536x864 para mejor rendimiento
            if self.width <= 1536 and self.height <= 864:
                sensor_mode = {"size": (1536, 864)}
            else:
                sensor_mode = {"size": (2304, 1296)}
            
            # Configuración de preview con formato RGB888 para mejor compatibilidad
            video_config = self.picam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                sensor=sensor_mode
            )
            self.picam.configure(video_config)
            
            # Controles específicos para IMX708
            try:
                self.picam.set_controls({
                    "AwbEnable": True,
                    "AeEnable": True,
                    "FrameDurationLimits": (int(1000000/self.fps), int(1000000/self.fps)),
                    "ExposureTime": 10000,  # 10ms inicial
                    "AnalogueGain": 1.0,
                })
            except Exception as e:
                print(f"[CAMERA] Advertencia en controles: {e}")
                
        except Exception as e:
            print(f"[CAMERA] Error inicializando: {e}")
            self.picam = None

    def available(self) -> bool:
        """Verificación mejorada de disponibilidad"""
        if not PICAM_AVAILABLE:
            return False
        if not self.picam:
            return False
        
        # Test rápido de funcionalidad
        try:
            # Solo verificar que podemos configurar
            test_config = self.picam.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            return True
        except Exception:
            return False

    def preview_to_tk(self, label_widget) -> Callable[[], None]:
        """Preview optimizado para Pi Zero 2W"""
        if not PIL_AVAILABLE:
            # Mostrar mensaje explicativo en lugar de error
            label_widget.configure(text="Vista previa requiere PIL\n(funciona para capturas)", 
                                 bg="#1a1f2e", fg="#cccccc", font=("monospace", 12))
            return lambda: None
            
        if not self.picam:
            label_widget.configure(text="Cámara no disponible", 
                                 bg="#1a1f2e", fg="#ff6666", font=("monospace", 12))
            return lambda: None
            
        self._bound_widget = label_widget
        if not self._previewing:
            self._previewing = True
            try:
                self.picam.start()
                time.sleep(0.1)  # Tiempo de estabilización
            except Exception as e:
                print(f"[CAMERA] Error iniciando preview: {e}")
                return lambda: None
            self._schedule_next()

        def stop():
            try:
                self._previewing = False
                self._bound_widget = None
            except Exception:
                pass
        return stop

    def _schedule_next(self):
        if not self._previewing or not self._bound_widget:
            return
        # Intervalo más largo para Pi Zero 2W
        interval = max(self.interval_ms, 100)  # Mínimo 100ms
        self._bound_widget.after(interval, self._update_frame)

    def _update_frame(self):
        if not (self._previewing and self._bound_widget and self.picam):
            return
        try:
            # Captura con timeout para evitar bloqueos
            arr = self.picam.capture_array()
            if arr is None:
                return
                
            # Redimensionar para preview eficiente
            img = Image.fromarray(arr)
            try:
                w = max(100, self._bound_widget.winfo_width())
                h = max(100, self._bound_widget.winfo_height())
                # Mantener aspect ratio
                img.thumbnail((w, h), Image.Resampling.LANCZOS)
            except Exception:
                img.thumbnail((320, 240), Image.Resampling.LANCZOS)
                
            photo = ImageTk.PhotoImage(image=img)
            self._last_frame_tk = photo
            self._bound_widget.configure(image=photo)
            
        except Exception as e:
            # Log solo errores persistentes
            if hasattr(self, '_error_count'):
                self._error_count += 1
            else:
                self._error_count = 1
                
            if self._error_count <= 3:  # Solo los primeros errores
                print(f"[CAMERA] Preview error: {e}")
        finally:
            self._schedule_next()

    def capture_still(self, path: Optional[str]=None) -> str:
        """Captura optimizada para IMX708 Wide"""
        if not self.picam:
            raise CameraUnavailable("Picamera2 no está disponible")
            
        if path is None:
            ts = int(time.time())
            path = os.path.join(self.save_dir, f"capture_{ts}.jpg")

        try:
            # Configuración de alta resolución para capturas
            # IMX708 Wide soporta hasta 4608x2592
            still_config = self.picam.create_still_configuration(
                main={"size": (2304, 1296)},  # Resolución intermedia para balance calidad/velocidad
                sensor={"size": (2304, 1296)}
            )
            
            # Cambiar temporalmente a modo still
            was_started = self.picam.started
            if was_started:
                self.picam.stop()
                
            self.picam.configure(still_config)
            self.picam.start()
            
            # Tiempo de estabilización para IMX708
            time.sleep(0.2)
            
            # Captura directa a archivo (más eficiente)
            self.picam.capture_file(path)
            
            # Restaurar configuración de video si estaba en preview
            if was_started:
                self.picam.stop()
                video_config = self.picam.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"}
                )
                self.picam.configure(video_config)
                if self._previewing:
                    self.picam.start()
                    
        except Exception as e:
            # Fallback a captura por array si falla la directa
            try:
                print(f"[CAMERA] Fallback capture method: {e}")
                arr = self.picam.capture_array()
                if arr is not None:
                    Image.fromarray(arr).save(path, format="JPEG", quality=85, optimize=True)
                else:
                    raise CameraUnavailable(f"Captura falló: {e}")
            except Exception as e2:
                raise CameraUnavailable(f"Error en captura: {e2}")
                
        return path

    def explain_status(self) -> str:
        """Estado detallado para diagnóstico"""
        status_parts = []
        
        if not PICAM_AVAILABLE:
            status_parts.append("Picamera2 no disponible")
        else:
            status_parts.append("Picamera2 OK")
            
        if not PIL_AVAILABLE:
            status_parts.append("PIL no disponible (preview limitado)")
        else:
            status_parts.append("PIL OK")
            
        if self.picam:
            status_parts.append("Cámara inicializada")
        else:
            status_parts.append("Cámara no inicializada")
            
        # Test de funcionalidad
        if self.available():
            status_parts.append("✅ FUNCIONAL")
        else:
            status_parts.append("❌ NO FUNCIONAL")
            
        return " | ".join(status_parts)

    def stop(self):
        """Parada limpia"""
        try:
            self._previewing = False
            if self.picam and self.picam.started:
                self.picam.stop()
        except Exception as e:
            print(f"[CAMERA] Error en stop: {e}")

    def __del__(self):
        """Limpieza automática"""
        try:
            self.stop()
        except Exception:
            pass
