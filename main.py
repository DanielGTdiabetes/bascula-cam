#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada principal simplificado
"""
import os
import sys
import logging
from pathlib import Path

# Añadir la raíz del proyecto al path (por si se ejecuta fuera del repo)
REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Logging básico (safe_run.sh redirige a /var/log/bascula/app.log)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("main")

def main() -> int:
    log.info("=== BÁSCULA DIGITAL PRO - INICIO ===")

    # Entorno gráfico disponible
    if not os.environ.get("DISPLAY") and sys.platform != "win32":
        log.error("Entorno sin DISPLAY, no se puede iniciar la interfaz gráfica")
        return 1

    try:
        # Import y arranque de la app
        from bascula.ui.app import BasculaApp
        app = BasculaApp()
        log.info("UI inicializada. Entrando en mainloop()")
        app.root.mainloop()
        return 0

    except ImportError as e:
        log.error(f"Error de importación: {e}")
        log.error("Verifica módulos y paquetes instalados (requirements.txt)")
        return 1

    except KeyboardInterrupt:
        log.info("Aplicación interrumpida por el usuario (Ctrl+C)")
        return 0

    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
        return 2

    finally:
        log.info("=== BÁSCULA DIGITAL PRO - FIN ===")

if __name__ == "__main__":
    sys.exit(main())
