#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada principal - VERSIÓN CORREGIDA
Elimina imports problemáticos y maneja errores de inicialización
"""
import os
import sys
import logging
from pathlib import Path

# Configurar logging ANTES de cualquier import de la app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path.home() / "bascula_main.log", encoding="utf-8")
    ]
)

log = logging.getLogger("main")

def setup_environment():
    """Configura el entorno antes de importar la aplicación"""
    try:
        # Asegurar que estamos en la raíz del proyecto
        repo_root = Path(__file__).parent.absolute()
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        
        # Configurar variables de entorno críticas
        os.environ.setdefault("PYTHONUNBUFFERED", "1")
        os.environ.setdefault("BASCULA_CFG_DIR", str(Path.home() / ".bascula"))
        
        log.info(f"Raíz del proyecto: {repo_root}")
        log.info(f"Python path: {sys.path[:3]}")  # Solo primeros 3 elementos
        
        return True
        
    except Exception as e:
        log.error(f"Error configurando entorno: {e}")
        return False

def test_critical_imports():
    """Prueba imports críticos antes de lanzar la app completa"""
    try:
        # Test 1: Tkinter (fundamental)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana de prueba
        root.destroy()
        log.info("✓ Tkinter disponible")
        
        # Test 2: Módulos base del proyecto
        from bascula import utils
        log.info("✓ bascula.utils disponible")
        
        from bascula.ui.widgets import Card, COL_BG
        log.info("✓ bascula.ui.widgets disponible")
        
        return True
        
    except ImportError as e:
        log.error(f"Import crítico faltante: {e}")
        return False
    except Exception as e:
        log.error(f"Error en test de imports: {e}")
        return False

def run_app():
    """Ejecuta la aplicación con manejo robusto de errores"""
    try:
        log.info("Importando BasculaAppTk...")
        from bascula.ui.app import BasculaAppTk
        
        log.info("Creando instancia de aplicación...")
        app = BasculaAppTk()
        
        log.info("Iniciando aplicación...")
        app.run()
        
        return 0
        
    except ImportError as e:
        log.error(f"Error de importación: {e}")
        log.error("Verifica que todos los módulos estén instalados correctamente")
        return 1
        
    except Exception as e:
        log.error(f"Error ejecutando aplicación: {e}", exc_info=True)
        return 2

def main():
    """Función principal con checks y manejo de errores"""
    log.info("=" * 50)
    log.info("=== BÁSCULA DIGITAL PRO - INICIO ===")
    log.info("=" * 50)
    
    try:
        # Paso 1: Configurar entorno
        log.info("[1/4] Configurando entorno...")
        if not setup_environment():
            log.error("Fallo en configuración del entorno")
            return 1
        
        # Paso 2: Test de imports críticos
        log.info("[2/4] Verificando dependencias críticas...")
        if not test_critical_imports():
            log.error("Fallo en verificación de dependencias")
            return 2
        
        # Paso 3: Ejecutar aplicación
        log.info("[3/4] Lanzando aplicación...")
        result = run_app()
        
        # Paso 4: Cleanup
        log.info("[4/4] Finalizando...")
        return result
        
    except KeyboardInterrupt:
        log.info("Aplicación interrumpida por usuario (Ctrl+C)")
        return 0
        
    except Exception as e:
        log.error(f"Error fatal no manejado: {e}", exc_info=True)
        return 3
        
    finally:
        log.info("=== BÁSCULA DIGITAL PRO - FIN ===")

if __name__ == "__main__":
    sys.exit(main())
