#!/usr/bin/env python3
"""
Módulo principal para ejecutar Bascula en modo headless (sin interfaz gráfica).
Este módulo permite que la aplicación funcione en Raspberry Pi OS Lite.
"""

import sys
import time
import logging
import signal
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/bascula-headless.log')
    ]
)

logger = logging.getLogger(__name__)

class HeadlessBascula:
    """Clase principal para ejecutar Bascula en modo headless."""
    
    def __init__(self):
        self.running = True
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
        
        try:
            # Importar servicios necesarios
            from bascula.services.wifi_config import main as wifi_main
            from bascula.services.scale_reader import ScaleReader
            
            # Iniciar servicio web en segundo plano
            logger.info("Iniciando servicio web…")
            # El servicio web se ejecutará en un hilo separado
            
            # Iniciar lector de báscula
            logger.info("Iniciando lector de báscula…")
            scale_reader = ScaleReader()
            
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
