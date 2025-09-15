#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada principal simplificado
"""
import os
import sys
import logging
from pathlib import Path

# Añadir la raíz del proyecto al path
REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

log = logging.getLogger("main")

def main():
    """Función principal."""
    log.info("=== BÁSCULA DIGITAL PRO - INICIO ===")
    
    try:
        # Importar y ejecutar la aplicación
        from bascula.ui.app import BasculaApp

        app = BasculaApp()
        app.root.mainloop()
        
        return 0
        
    except ImportError as e:
        log.error(f"Error de importación: {e}")
        log.error("Verifica que todos los módulos estén instalados")
        return 1
        
    except KeyboardInterrupt:
        log.info("Aplicación interrumpida por usuario (Ctrl+C)")
        return 0
        
    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
        return 2
        
    finally:
        log.info("=== BÁSCULA DIGITAL PRO - FIN ===")

if __name__ == "__main__":
    sys.exit(main())
