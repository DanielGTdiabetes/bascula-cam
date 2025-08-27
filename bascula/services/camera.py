import os, time
from pathlib import Path
from datetime import datetime

class CameraService:
    def __init__(self, state, logger, storage):
        self.state = state
        self.logger = logger
        self.storage = storage
        self.picam2 = None
        self.available = False
        try:
            if self.state.cfg.hardware.strict_hardware:
                self._ensure_started(strict=True)
            else:
                self._ensure_started(strict=False)
        except Exception as e:
            self.logger.error(f"Cámara no disponible en init: {e}")
            self.available = False
            self.state.camera_ready = False

    def _ensure_started(self, strict: bool) -> bool:
        if self.available and self.picam2:
            return True
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
            if self.state.cfg.hardware.cam_show_preview:
                self.picam2.start(show_preview=True)
            else:
                self.picam2.start()
            # Autofoco (si disponible)
            try:
                from libcamera import controls
                set_controls = {}
                mode = self.state.cfg.hardware.cam_af_mode
                speed = self.state.cfg.hardware.cam_af_speed
                if mode in ("Off", "Auto", "Continuous"):
                    enum_mode = {
                        "Off": getattr(controls.AfModeEnum, "Manual", 0),
                        "Auto": getattr(controls.AfModeEnum, "Auto", 1),
                        "Continuous": getattr(controls.AfModeEnum, "Continuous", 2),
                    }[mode]
                    set_controls["AfMode"] = enum_mode
                if speed in ("Normal", "Fast"):
                    enum_speed = {
                        "Normal": getattr(controls.AfSpeedEnum, "Normal", 0),
                        "Fast": getattr(controls.AfSpeedEnum, "Fast", 1),
                    }[speed]
                    set_controls["AfSpeed"] = enum_speed
                if set_controls:
                    self.picam2.set_controls(set_controls)
            except Exception as e:
                self.logger.warning(f"AF no aplicado: {e}")
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

    def capture(self, weight: float) -> str:
        if not self._ensure_started(strict=False):
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"peso_{ts}_{weight:.1f}g.jpg"
            path = self.storage.captures_dir / name
            self.picam2.capture_file(str(path))
            if self._valid_file(path):
                self.logger.info(f"📷 Foto guardada: {path}")
                return str(path)
            else:
                self.logger.warning("Archivo captura inválido")
                return ""
        except Exception as e:
            self.logger.error(f"Error en capture(): {e}")
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
                self.logger.error(f"Reintento falló: {e2}")
            return ""

    def capture_burst(self, weight: float, num: int = None, delay: float = None) -> list:
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

    def _restart_pipeline(self):
        try:
            if self.picam2:
                self.picam2.stop()
                if self.state.cfg.hardware.cam_show_preview:
                    self.picam2.start(show_preview=True)
                else:
                    self.picam2.start()
                time.sleep(0.6)
        except Exception:
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
                self.picam2.stop()
                self.picam2.close()
        except Exception:
            pass
        self.picam2 = None
        self.available = False
        self.state.camera_ready = False
