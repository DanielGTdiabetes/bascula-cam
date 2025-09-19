#!/usr/bin/env python3
"""
Módulo principal para ejecutar Bascula en modo headless (sin interfaz gráfica).
Este módulo permite que la aplicación funcione en Raspberry Pi OS Lite.
"""

import sys
import time
import logging
import signal
import threading
from pathlib import Path
from typing import Optional

# Configurar logging
_log_handlers = [logging.StreamHandler(sys.stdout)]
_log_file_path = None
_log_candidates = [Path('/tmp/bascula-headless.log')]
try:
    _log_candidates.append(Path.home() / '.cache' / 'bascula' / 'bascula-headless.log')
except RuntimeError:
    pass
for candidate in _log_candidates:
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        _log_handlers.append(logging.FileHandler(candidate))
        _log_file_path = candidate
        break
    except OSError:
        continue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_log_handlers,
)

logger = logging.getLogger(__name__)
if _log_file_path is None:
    logger.warning('No se pudo crear archivo de log; se usará solo stdout')
else:
    logger.info('Archivo de log en %s', _log_file_path)

class HeadlessBascula:
    """Clase principal para ejecutar Bascula en modo headless."""
    
    def __init__(self):
        self.running = True
        self.scale_reader: Optional[object] = None
        self._web_server = None
        self._web_thread: Optional[threading.Thread] = None
        self.setup_signal_handlers()
        logger.info("Bascula Headless iniciado")
    
    def setup_signal_handlers(self):
        """Configurar manejadores de señales para cierre limpio."""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Manejar señales de cierre."""
        logger.info(f"Recibida señal {signum}, cerrando aplicación…")
        self.running = False
    
    def check_hardware(self):
        """Verificar que el hardware necesario esté disponible."""
        logger.info("Verificando hardware…")
        
        # Verificar puerto serie para báscula
        serial_devices = list(Path('/dev').glob('ttyUSB*')) + list(Path('/dev').glob('ttyACM*'))
        if serial_devices:
            logger.info(f"Dispositivos serie encontrados: {[str(d) for d in serial_devices]}")
        else:
            logger.warning("No se encontraron dispositivos serie")
        
        # Verificar cámara
        camera_devices = list(Path('/dev').glob('video*'))
        if camera_devices:
            logger.info(f"Dispositivos de cámara encontrados: {[str(d) for d in camera_devices]}")
        else:
            logger.warning("No se encontraron dispositivos de cámara")
        
        return True
    
    def run_services(self):
        """Ejecutar los servicios principales en modo headless."""
        logger.info("Iniciando servicios en modo headless…")

        scale_reader = None
        web_server = None
        web_thread: Optional[threading.Thread] = None

        try:
            # Importar servicios necesarios
            from werkzeug.serving import make_server
            from bascula.services import wifi_config
            from bascula.services.serial_reader import SerialReader

            # Iniciar servicio web en segundo plano
            logger.info("Iniciando servicio web…")
            web_server = make_server(wifi_config.APP_HOST, wifi_config.APP_PORT, wifi_config.app)

            def _serve() -> None:
                try:
                    web_server.serve_forever()
                except Exception as exc:
                    logger.error("Error en servidor web: %s", exc)
                    self.running = False

            web_thread = threading.Thread(target=_serve, name="WifiConfigServer", daemon=True)
            web_thread.start()
            self._web_server = web_server
            self._web_thread = web_thread

            # Iniciar lector de báscula
            logger.info("Iniciando lector de báscula…")
            scale_reader = SerialReader()
            scale_reader.start()
            self.scale_reader = scale_reader

            # Bucle principal
            while self.running:
                try:
                    # Aquí puedes agregar lógica de monitoreo
                    # Por ejemplo, verificar estado de servicios
                    time.sleep(5)
                    logger.debug("Servicios funcionando correctamente")

                except Exception as e:
                    logger.error(f"Error en bucle principal: {e}")
                    time.sleep(1)

        except ImportError as e:
            logger.error(f"Error importando módulos: {e}")
            logger.info("Ejecutando en modo básico…")

            # Modo básico sin servicios complejos
            while self.running:
                logger.info("Bascula ejecutándose en modo básico headless")
                time.sleep(30)

        except Exception as e:
            logger.error(f"Error crítico: {e}")
            return False

        finally:
            if scale_reader is not None:
                try:
                    scale_reader.stop()
                except Exception:
                    pass
                self.scale_reader = None

            if web_server is not None:
                try:
                    web_server.shutdown()
                except Exception:
                    pass

            if web_thread is not None and web_thread.is_alive():
                try:
                    web_thread.join(timeout=2.0)
                except Exception:
                    pass
            self._web_server = None
            self._web_thread = None

        return True
    
    def run(self):
        """Ejecutar la aplicación principal."""
        logger.info("=== Bascula Headless Mode ===")
        
        if not self.check_hardware():
            logger.error("Verificación de hardware falló")
            return False
        
        try:
            return self.run_services()
        except Exception as e:
            logger.error(f"Error ejecutando servicios: {e}")
            return False
        finally:
            logger.info("Bascula Headless terminado")

def main():
    """Función principal."""
    try:
        app = HeadlessBascula()
        success = app.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
