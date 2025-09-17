#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico completo de cámara para Raspberry Pi Zero 2W + Module 3 Wide
Ejecutar: python3 scripts/camera_diagnostic.py
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Asegura que el repo raíz está en sys.path para imports del proyecto
try:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
except Exception:
    pass

def run_command(cmd, capture_output=True):
    """Ejecuta un comando y devuelve resultado"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, 
                              text=True, timeout=10)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def check_system_info():
    """Información del sistema"""
    print("=== INFORMACIÓN DEL SISTEMA ===")
    
    # Modelo de Pi
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
        print(f"Modelo: {model}")
    except:
        print("Modelo: No detectado")
    
    # Versión del OS
    success, output, _ = run_command("cat /etc/os-release | grep PRETTY_NAME")
    if success:
        print(f"OS: {output.strip()}")
    
    # Memoria
    success, output, _ = run_command("free -h | grep Mem:")
    if success:
        print(f"RAM: {output.strip()}")
    
    # GPU Memory
    success, output, _ = run_command("vcgencmd get_mem gpu")
    if success:
        print(f"GPU Memory: {output.strip()}")
    
    print()

def check_camera_hardware():
    """Verificar hardware de cámara"""
    print("=== HARDWARE DE CÁMARA ===")
    
    # vcgencmd
    success, output, _ = run_command("vcgencmd get_camera")
    print(f"vcgencmd get_camera: {output.strip() if success else 'ERROR'}")
    
    # Dispositivos video
    success, output, _ = run_command("ls -la /dev/video*")
    if success:
        print("Dispositivos video encontrados:")
        print(output)
    else:
        print("No se encontraron dispositivos video")
    
    # dmesg cámara
    success, output, _ = run_command("dmesg | grep -i camera | tail -5")
    if success and output.strip():
        print("Últimos logs de cámara:")
        print(output)
    
    print()

def check_config_txt():
    """Verificar configuración"""
    print("=== CONFIGURACIÓN (/boot/firmware/config.txt) ===")
    
    config_paths = ['/boot/firmware/config.txt', '/boot/config.txt']
    config_found = False
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"Archivo encontrado: {config_path}")
            config_found = True
            
            # Leer configuración relevante
            try:
                with open(config_path, 'r') as f:
                    content = f.read()
                
                relevant_lines = []
                for line in content.split('\n'):
                    line = line.strip()
                    if any(keyword in line.lower() for keyword in 
                           ['camera', 'imx708', 'gpu_mem', 'start_x', 'dtoverlay']):
                        relevant_lines.append(line)
                
                if relevant_lines:
                    print("Configuración relevante:")
                    for line in relevant_lines:
                        print(f"  {line}")
                else:
                    print("No se encontró configuración específica de cámara")
                    
            except Exception as e:
                print(f"Error leyendo {config_path}: {e}")
            break
    
    if not config_found:
        print("⚠️  No se encontró config.txt")
    
    print()

def check_software():
    """Verificar software instalado"""
    print("=== SOFTWARE INSTALADO ===")
    
    packages = [
        ('libcamera-apps', 'libcamera-hello --version'),
        ('python3-picamera2', 'python3 -c "import picamera2; print(picamera2.__version__)"'),
        ('python3-pil', 'python3 -c "from PIL import Image; print(Image.__version__)"'),
        ('python3-libcamera', 'python3 -c "import libcamera; print(\'OK\')"')
    ]
    
    for name, cmd in packages:
        success, output, error = run_command(cmd)
        status = "✅ OK" if success else "❌ FALTA"
        version = output.strip() if success else error
        print(f"{name:20} {status:10} {version}")
    
    print()

def test_libcamera():
    """Probar libcamera"""
    print("=== PRUEBAS LIBCAMERA ===")
    
    # Listar cámaras
    print("Listando cámaras…")
    success, output, error = run_command("libcamera-hello --list-cameras")
    if success:
        print("Cámaras detectadas:")
        print(output)
    else:
        print(f"❌ Error: {error}")
        return False
    
    # Prueba rápida (sin preview)
    print("Prueba de captura…")
    success, output, error = run_command("libcamera-still -o /tmp/test_diagnostic.jpg --immediate")
    if success:
        print("✅ Captura exitosa: /tmp/test_diagnostic.jpg")
        
        # Verificar archivo
        if os.path.exists('/tmp/test_diagnostic.jpg'):
            size = os.path.getsize('/tmp/test_diagnostic.jpg')
            print(f"Tamaño del archivo: {size} bytes")
        return True
    else:
        print(f"❌ Error en captura: {error}")
        return False

def test_picamera2():
    """Probar Picamera2"""
    print("\n=== PRUEBA PICAMERA2 ===")
    
    try:
        from picamera2 import Picamera2
        print("✅ Import picamera2 OK")
        
        try:
            picam = Picamera2()
            print("✅ Picamera2() creado OK")
            
            # Configurar
            config = picam.create_preview_configuration(main={"size": (640, 480)})
            picam.configure(config)
            print("✅ Configuración OK")
            
            # Iniciar
            picam.start()
            print("✅ Camera iniciada OK")
            
            # Capturar
            picam.capture_file("/tmp/test_picamera2.jpg")
            print("✅ Captura con Picamera2 OK: /tmp/test_picamera2.jpg")
            
            # Verificar archivo
            if os.path.exists('/tmp/test_picamera2.jpg'):
                size = os.path.getsize('/tmp/test_picamera2.jpg')
                print(f"Tamaño del archivo: {size} bytes")
            
            picam.stop()
            picam.close()
            return True
            
        except Exception as e:
            print(f"❌ Error con Picamera2: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ No se pudo importar Picamera2: {e}")
        return False

def test_camera_service():
    """Probar el servicio de cámara del proyecto"""
    print("\n=== PRUEBA CAMERA SERVICE ===")
    
    try:
        # Importar el servicio de cámara del proyecto
        from bascula.services.camera import CameraService
        print("✅ Import CameraService OK")
        
        # Crear servicio
        cam = CameraService(prefer_backend="picamera2", resolution=(800,600))
        print(f"Backend: {cam.backend}")
        print(f"Estado: {cam.explain_status()}")
        print(f"¿Disponible? {cam.is_available()}")
        
        if cam.is_available():
            # Prueba de captura
            result = cam.capture_jpeg("/tmp/test_service.jpg")
            if result:
                print(f"✅ Captura con CameraService OK: {result}")
                if os.path.exists(result):
                    size = os.path.getsize(result)
                    print(f"Tamaño del archivo: {size} bytes")
            else:
                print("❌ Error en captura con CameraService")
        
        cam.close()
        return cam.is_available()
        
    except Exception as e:
        print(f"❌ Error con CameraService: {e}")
        return False

def generate_fixes():
    """Generar comandos de solución"""
    print("\n=== POSIBLES SOLUCIONES ===")
    
    print("Si la cámara no funciona, prueba estos comandos:")
    print()
    
    print("1. Instalar dependencias:")
    print("sudo apt update")
    print("sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps python3-pil")
    print()
    
    print("2. Configurar /boot/firmware/config.txt (añadir estas líneas):")
    print("camera_auto_detect=1")
    print("dtoverlay=imx708")
    print("gpu_mem=128")
    print()
    
    print("3. Reiniciar:")
    print("sudo reboot")
    print()
    
    print("4. Si persiste el problema, prueba:")
    print("sudo raspi-config  # Enable Camera in Interface Options")
    print()

def main():
    """Ejecutar diagnóstico completo"""
    print("🔍 DIAGNÓSTICO DE CÁMARA RASPBERRY PI")
    print("=" * 50)
    
    check_system_info()
    check_camera_hardware()
    check_config_txt()
    check_software()
    
    libcamera_ok = test_libcamera()
    picamera2_ok = test_picamera2()
    service_ok = test_camera_service()
    
    print("\n=== RESUMEN ===")
    print(f"libcamera:      {'✅ OK' if libcamera_ok else '❌ FALLO'}")
    print(f"Picamera2:      {'✅ OK' if picamera2_ok else '❌ FALLO'}")
    print(f"CameraService:  {'✅ OK' if service_ok else '❌ FALLO'}")
    
    if all([libcamera_ok, picamera2_ok, service_ok]):
        print("\n🎉 ¡CÁMARA FUNCIONANDO CORRECTAMENTE!")
        print("Tu aplicación de báscula debería poder usar la cámara.")
    else:
        print("\n⚠️  PROBLEMAS DETECTADOS")
        generate_fixes()

if __name__ == "__main__":
    main()
