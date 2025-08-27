import os, time
from pathlib import Path
from datetime import datetime

class CameraService:
    """
    Inicializa Picamera2 de forma robusta y captura JPG con verificación.
    - Reintenta con configuraciones alternativas si falla.
    - Verifica tamaño > 0 y existencia en disco.
    - Deja trazas en logger para diagnóstico.
    """
    def __init__(self, state, logger, storage):
        self.state = state
        self.logger = logger
        self.storage = storage
        self.cam = None
        self.available = False
        if self.state.cfg.hardware.strict_hardware:
            # En modo estricto, intentamos levantar cámara al inicio
            self._ensure()

    def _ensure(self) -> bool:
        if self.available and self.cam:
            return True
        return self._init_with_retries()

    def _init_with_retries(self, retries: int = 2) -> bool:
        # Comprobaciones básicas de sistema
        if not os.path.exists("/dev/video0") and not os.path.exists("/dev/media0"):
            self.logger.error("No se detecta dispositivo de cámara (/dev/video0 o /dev/media0)")
            self._mark_unavailable()
            return False

        # Reintentos con variaciones
        attempts = [
            {"size": self.state.cfg.hardware.camera_resolution},
            {"size": (1280, 720)},
            {"size": (1640, 922)},  # 16:9 cercano
        ]
        for i, params in enumerate(attempts[:retries+1], start=1):
            try:
                self._init_once(params["size"])
                self.logger.info(f"Cámara lista con tamaño {params['size']} (intento {i})")
                self.state.camera_ready = True
                self.available = True
                return True
            except Exception as e:
                self.logger.warning(f"Init cámara intento {i} falló: {e}")
                self._safe_close()
                time.sleep(0.8)

        self._mark_unavailable()
        return False

    def _init_once(self, size_tuple):
        from picamera2 import Picamera2
        cam = Picamera2()
        cfg = cam.create_still_configuration(main={"size": size_tuple}, buffer_count=2)
        cam.configure(cfg)
        cam.start()
        time.sleep(1.2)  # warm-up sensores/AE
        # Pequeña captura de prueba a tmp
        tmp = Path("/tmp/_cam_probe.jpg")
        cam.capture_file(str(tmp))
        if not tmp.exists() or tmp.stat().st_size < 1024:
            raise RuntimeError("Prueba de captura fallida o muy pequeña")
        tmp.unlink(missing_ok=True)
        self.cam = cam

    def _safe_close(self):
        try:
            if self.cam:
                self.cam.stop()
                self.cam.close()
        except Exception:
            pass
        self.cam = None

    def _mark_unavailable(self):
        self.available = False
        self.state.camera_ready = False

    def capture(self, weight: float) -> str:
        """
        Captura a ~/bascula-cam/capturas/ y devuelve la ruta o "".
        En caso de fallo, intenta re-inicializar una vez y reintenta.
        """
        if not self._ensure():
            self.logger.error("Cámara no disponible (ensure falló)")
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"peso_{ts}_{weight:.1f}g.jpg"
            path = self.storage.captures_dir / name
            # Captura directa
            self.cam.capture_file(str(path))
            ok = path.exists() and path.stat().st_size > 1024
            if not ok:
                # Reintento: restart pipeline rápido
                self.logger.warning("Verificación de captura falló; reintento tras restart")
                self.cam.stop()
                self.cam.start()
                time.sleep(0.6)
                self.cam.capture_file(str(path))
                ok = path.exists() and path.stat().st_size > 1024
            if ok:
                self.logger.info(f"📷 Foto guardada: {path}")
                return str(path)
            else:
                self.logger.error("Captura fallida tras reintento")
        except Exception as e:
            self.logger.error(f"Foto error: {e}")
            # Reintentar con re-init agresivo una vez
            if self._init_with_retries(retries=1):
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    name = f"peso_{ts}_{weight:.1f}g.jpg"
                    path = self.storage.captures_dir / name
                    self.cam.capture_file(str(path))
                    if path.exists() and path.stat().st_size > 1024:
                        self.logger.info(f"📷 Foto guardada (tras reinit): {path}")
                        return str(path)
                except Exception as e2:
                    self.logger.error(f"Reintento de foto falló: {e2}")
        return ""

    def close(self):
        self._safe_close()
