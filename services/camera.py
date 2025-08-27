import os, time
from pathlib import Path
from datetime import datetime

class CameraService:
    def __init__(self, state, logger, storage):
        self.state = state
        self.logger = logger
        self.storage = storage
        self.cam = None
        self.available = False

    def _ensure(self):
        if self.available and self.cam:
            return True
        try:
            from picamera2 import Picamera2
            self.cam = Picamera2()
            cfg = self.cam.create_still_configuration(main={"size": self.state.cfg.hardware.camera_resolution})
            self.cam.configure(cfg)
            self.cam.start()
            time.sleep(1.0)
            self.available = True
            self.state.camera_ready = True
            self.logger.info("Cámara lista")
        except Exception as e:
            self.logger.warning(f"Cámara no disponible: {e}")
            self.available = False
            self.state.camera_ready = False
        return self.available

    def capture(self, weight: float) -> str:
        if not self._ensure():
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"peso_{ts}_{weight:.1f}g.jpg"
            path = self.storage.captures_dir / name
            self.cam.capture_file(str(path))
            if path.exists() and path.stat().st_size > 0:
                return str(path)
        except Exception as e:
            self.logger.error(f"Foto error: {e}")
        return ""

    def close(self):
        try:
            if self.cam:
                self.cam.stop()
                self.cam.close()
        except Exception:
            pass
