import os, time
from pathlib import Path
from datetime import datetime

class CameraService:
    """
    Picamera2 con inicialización simple (start + capture_file) y controles de AF.
    - Sigue el patrón recomendado:
        picam2 = Picamera2(); picam2.start(); picam2.capture_file("foto.jpg")
    - Autofoco opcional (Continuous/Fast) usando libcamera.controls.
    - Ráfaga configurable (cam_burst_num, cam_burst_delay).
    - Verifica tamaño del archivo (> 1 KB) y registra mensajes para diagnóstico.
    """
    def __init__(self, state, logger, storage):
        self.state = state
        self.logger = logger
        self.storage = storage
        self.picam2 = None
        self.available = False

        # En modo estricto intentamos dejarla lista ya
        try:
            if self.state.cfg.hardware.strict_hardware:
                self._ensure_started(strict=True)
            else:
                self._ensure_started(strict=False)
        except Exception as e:
            self.logger.error(f"Cámara no disponible en init: {e}")
            self.available = False
            self.state.camera_ready = False

    # ---------- Inicialización básica ----------
    def _ensure_started(self, strict: bool) -> bool:
        if self.available and self.picam2:
            return True

        # Comprobación rápida de dispositivo
        if not os.path.exists("/dev/video0") and not os.path.exists("/dev/media0"):
            msg = "No se detecta dispositivo de cámara (/dev/video0 o /dev/media0)"
            self.logger.error(msg)
            if strict:
                raise RuntimeError(msg)
            self.available = False
            self.state.camera_ready = False
            return False

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()

            # Preview (opcional). Nota: en Zero 2 W el preview puede consumir CPU.
            if self.state.cfg.hardware.cam_show_preview:
                # show_preview=True crea una ventana DRM/Qt. Si vas en kiosk sin X, no lo uses.
                self.picam2.start(show_preview=True)
            else:
                self.picam2.start()

            # Autofoco (si está disponible y activado en settings)
            try:
                from libcamera import controls
                af_mode = self.state.cfg.hardware.cam_af_mode
                af_speed = self.state.cfg.hardware.cam_af_speed
                set_controls = {}
                if af_mode in ("Auto", "Continuous", "Off"):
                    enum_map_mode = {
                        "Off": controls.AfModeEnum.Manual if hasattr(controls, "AfModeEnum") else 0,
                        "Auto": controls.AfModeEnum.Auto if hasattr(controls, "AfModeEnum") else 1,
                        "Continuous": controls.AfModeEnum.Continuous if hasattr(controls, "AfModeEnum") else 2,
                    }
                    set_controls["AfMode"] = enum_map_mode.get(af_mode, controls.AfModeEnum.Continuous)
                if af_speed in ("Normal", "Fast"):
                    enum_map_speed = {
                        "Normal": controls.AfSpeedEnum.Normal if hasattr(controls, "AfSpeedEnum") else 0,
                        "Fast": controls.AfSpeedEnum.Fast if hasattr(controls, "AfSpeedEnum") else 1,
                    }
                    set_controls["AfSpeed"] = enum_map_speed.get(af_speed, 1)
                if set_controls:
                    self.picam2.set_controls(set_controls)
                    self.logger.info(f"AF: {af_mode} / {af_speed}")
            except Exception as e:
                # Si libcamera.controls no está, seguimos sin AF.
                self.logger.warning(f"No se pudieron aplicar controles AF: {e}")

            # Pequeño warm-up para AE/AF
            time.sleep(0.8)

            self.available = True
            self.state.camera_ready = True
            self.logger.info("Cámara Picamera2 lista (start OK)")
            return True
        except Exception as e:
            self.logger.error(f"Fallo al iniciar Picamera2: {e}")
            if strict:
                raise
            self.available = False
            self.state.camera_ready = False
            return False

    # ---------- Captura única ----------
    def capture(self, weight: float) -> str:
        """
        Captura una sola imagen a ~/bascula-cam/capturas/ y devuelve la ruta, o "" si falla.
        """
        if not self._ensure_started(strict=False):
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"peso_{ts}_{weight:.1f}g.jpg"
            path = self.storage.captures_dir / name
            # Patrón simple recomendado
            self.picam2.capture_file(str(path))
            if self._valid_file(path):
                self.logger.info(f"📷 Foto guardada: {path}")
                return str(path)
            else:
                self.logger.warning("Archivo de captura inválido (tamaño insuficiente)")
                return ""
        except Exception as e:
            self.logger.error(f"Error en capture(): {e}")
            # Reintento con restart rápido
            try:
                self._restart_pipeline()
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                name = f"peso_{ts}_{weight:.1f}g.jpg"
                path = self.storage.captures_dir / name
                self.picam2.capture_file(str(path))
                if self._valid_file(path):
                    self.logger.info(f"📷 Foto guardada tras restart: {path}")
                    return str(path)
            except Exception as e2:
                self.logger.error(f"Reintento de foto falló: {e2}")
            return ""

    # ---------- Captura en ráfaga ----------
    def capture_burst(self, weight: float, num: int = None, delay: float = None) -> list:
        """
        Toma N fotos en ráfaga con 'delay' entre ellas. Devuelve lista de rutas válidas.
        Si num/delay no se indican, usa los valores de settings (cam_burst_num/cam_burst_delay).
        """
        if not self._ensure_started(strict=False):
            return []
        n = int(num if num is not None else max(1, self.state.cfg.hardware.cam_burst_num))
        d = float(delay if delay is not None else max(0.0, self.state.cfg.hardware.cam_burst_delay))
        paths = []
        for i in range(n):
            p = self.capture(weight)
            if p:
                paths.append(p)
            if i < n - 1 and d > 0:
                time.sleep(d)
        return paths

    # ---------- Utilidades ----------
    def _restart_pipeline(self):
        try:
            if self.picam2:
                self.picam2.stop()
                # Preview depende de la setting
                if self.state.cfg.hardware.cam_show_preview:
                    self.picam2.start(show_preview=True)
                else:
                    self.picam2.start()
                time.sleep(0.6)  # pequeño warm-up de reenganche
        except Exception:
            # Re-inicialización completa si el restart simple falla
            self.available = False
            self.state.camera_ready = False
            self._ensure_started(strict=False)

    @staticmethod
    def _valid_file(path: Path) -> bool:
        try:
            return path.exists() and path.stat().st_size > 1024
        except Exception:
            return False

    def close(self):
        try:
            if self.picam2:
                # Si se activó preview, hay que pararlo igual con stop()
                self.picam2.stop()
                self.picam2.close()
        except Exception:
            pass
        self.picam2 = None
        self.available = False
        self.state.camera_ready = False
