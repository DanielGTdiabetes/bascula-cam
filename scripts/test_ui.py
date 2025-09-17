#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ui.py - Script de diagnóstico para probar la UI en modo kiosk
"""
import os
import sys
import logging
import tkinter as tk
from pathlib import Path

# Añadir la raíz del proyecto al path
REPO_ROOT = Path(__file__).parent.parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("test_ui")

def test_tkinter_basic():
    """Prueba básica de Tkinter"""
    log.info("=== PRUEBA BÁSICA DE TKINTER ===")
    
    try:
        root = tk.Tk()
        root.title("Test Básico")
        root.geometry("800x600")
        root.configure(bg="#0a0e1a")
        
        # Etiqueta de prueba
        label = tk.Label(root, text="✅ Tkinter funcionando correctamente", 
                        fg="#00ff66", bg="#0a0e1a", 
                        font=("DejaVu Sans", 24, "bold"))
        label.pack(expand=True)
        
        # Botón para cerrar
        btn = tk.Button(root, text="Cerrar", command=root.destroy,
                       font=("DejaVu Sans", 16))
        btn.pack(pady=20)
        
        log.info("Ventana de prueba creada. Mostrando por 5 segundos…")
        root.after(5000, root.destroy)  # Auto-cerrar después de 5 segundos
        root.mainloop()
        
        log.info("✅ Prueba básica de Tkinter: EXITOSA")
        return True
        
    except Exception as e:
        log.error(f"❌ Error en prueba básica de Tkinter: {e}")
        return False

def test_fullscreen():
    """Prueba de modo pantalla completa"""
    log.info("=== PRUEBA MODO PANTALLA COMPLETA ===")
    
    try:
        root = tk.Tk()
        root.title("Test Fullscreen")
        root.attributes('-fullscreen', True)
        root.configure(bg="#000000", cursor='none')
        
        # Contenido de prueba
        tk.Label(root, text="🖥️ MODO PANTALLA COMPLETA", 
                fg="#00ff66", bg="#000000", 
                font=("DejaVu Sans", 32, "bold")).pack(pady=100)
        
        tk.Label(root, text="Presiona ESC para salir", 
                fg="#ffffff", bg="#000000", 
                font=("DejaVu Sans", 16)).pack(pady=20)
        
        # Bind para salir con Escape
        root.bind('<Escape>', lambda e: root.destroy())
        root.focus_set()
        
        log.info("Modo fullscreen activado. Presiona ESC para salir…")
        root.after(10000, root.destroy)  # Auto-cerrar después de 10 segundos
        root.mainloop()
        
        log.info("✅ Prueba fullscreen: EXITOSA")
        return True
        
    except Exception as e:
        log.error(f"❌ Error en prueba fullscreen: {e}")
        return False

def test_bascula_ui():
    """Prueba de la UI completa de la báscula"""
    log.info("=== PRUEBA UI COMPLETA DE BÁSCULA ===")
    
    try:
        from bascula.ui.app import BasculaApp
        
        log.info("Creando instancia de BasculaApp…")
        app = BasculaApp()
        
        log.info("✅ BasculaApp creada exitosamente")
        log.info("Iniciando aplicación (se cerrará automáticamente en 15 segundos)…")
        
        # Auto-cerrar después de 15 segundos para prueba
        app.root.after(15000, app.quit)
        
        app.run()
        
        log.info("✅ Prueba UI completa: EXITOSA")
        return True
        
    except Exception as e:
        log.error(f"❌ Error en prueba UI completa: {e}", exc_info=True)
        return False

def check_environment():
    """Verificar el entorno de ejecución"""
    log.info("=== VERIFICACIÓN DEL ENTORNO ===")
    
    # Variables de entorno importantes
    env_vars = ['DISPLAY', 'XDG_RUNTIME_DIR', 'USER', 'HOME']
    for var in env_vars:
        value = os.environ.get(var, 'NO DEFINIDA')
        log.info(f"{var}: {value}")
    
    # Información del sistema
    log.info(f"Plataforma: {sys.platform}")
    log.info(f"Python: {sys.version}")
    log.info(f"Directorio actual: {os.getcwd()}")
    log.info(f"Raíz del proyecto: {REPO_ROOT}")
    
    # Verificar si estamos en un entorno gráfico
    has_display = bool(os.environ.get('DISPLAY'))
    log.info(f"Entorno gráfico disponible: {'✅ SÍ' if has_display else '❌ NO'}")
    
    return has_display

def main():
    """Función principal de diagnóstico"""
    log.info("🔍 INICIANDO DIAGNÓSTICO DE UI")
    log.info("=" * 50)
    
    # Verificar entorno
    if not check_environment():
        log.error("❌ No hay entorno gráfico disponible")
        if sys.platform != "win32":
            log.info("💡 Asegúrate de que DISPLAY esté configurado correctamente")
            log.info("💡 En Raspberry Pi: export DISPLAY=:0")
        return 1
    
    # Ejecutar pruebas
    tests = [
        ("Tkinter Básico", test_tkinter_basic),
        ("Modo Fullscreen", test_fullscreen),
        ("UI Completa Báscula", test_bascula_ui)
    ]
    
    results = []
    for test_name, test_func in tests:
        log.info(f"\n🧪 Ejecutando: {test_name}")
        log.info("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            log.error(f"❌ Error inesperado en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen final
    log.info("\n" + "=" * 50)
    log.info("📊 RESUMEN DE PRUEBAS")
    log.info("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        log.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    log.info(f"\nResultado: {passed}/{len(results)} pruebas exitosas")
    
    if passed == len(results):
        log.info("🎉 ¡Todas las pruebas pasaron! La UI debería funcionar correctamente.")
        return 0
    else:
        log.error("⚠️  Algunas pruebas fallaron. Revisa los logs para más detalles.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
