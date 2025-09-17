#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_serial.py - Diagnóstico completo de la conexión serie
"""
import os
import sys
import time
import subprocess

print("="*60)
print("DIAGNÓSTICO DE CONEXIÓN SERIE ESP32 → RASPBERRY PI")
print("="*60)

# 1. Verificar que el puerto existe
print("\n1. VERIFICANDO DISPOSITIVOS SERIE:")
print("-" * 40)
ports_to_check = ["/dev/serial0", "/dev/ttyS0", "/dev/ttyAMA0", "/dev/ttyUSB0"]
found_ports = []

for port in ports_to_check:
    if os.path.exists(port):
        print(f"✔. {port} existe")
        # Verificar a qué apunta si es un symlink
        if os.path.islink(port):
            target = os.readlink(port)
            print(f"   → Apunta a: {target}")
        found_ports.append(port)
    else:
        print(f"✗ {port} no existe")

if not found_ports:
    print("\n✱ NO SE ENCONTRARON PUERTOS SERIE")
    print("Posibles causas:")
    print("  1. UART no habilitado en Raspberry Pi")
    print("  2. Puerto serie usado por consola")
    sys.exit(1)

# 2. Verificar configuración de Raspberry Pi
print("\n2. CONFIGURACIÓN RASPBERRY PI:")
print("-" * 40)

# Verificar cmdline.txt
print("Verificando /boot/cmdline.txt…")
try:
    with open("/boot/cmdline.txt", "r") as f:
        cmdline = f.read()
    if "console=serial0" in cmdline or "console=ttyAMA0" in cmdline:
        print("✱  ADVERTENCIA: La consola está usando el puerto serie")
        print("   Debes eliminar 'console=serial0,115200' de /boot/cmdline.txt")
    else:
        print("✔. Puerto serie no usado por consola")
except Exception as e:
    print(f"   No se pudo leer: {e}")

# Verificar config.txt
print("\nVerificando /boot/config.txt…")
config_paths = ["/boot/config.txt", "/boot/firmware/config.txt"]
for config_path in config_paths:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = f.read()
            if "enable_uart=1" in config:
                print("✔. UART habilitado (enable_uart=1)")
            else:
                print("✱  UART podría no estar habilitado")
                print("   Añade 'enable_uart=1' a config.txt")
            break
        except Exception as e:
            print(f"   No se pudo leer: {e}")

# 3. Probar lectura directa
print("\n3. PRUEBA DE LECTURA DIRECTA:")
print("-" * 40)

import serial

PORT = "/dev/serial0"
BAUDRATES = [115200, 9600, 57600]  # Probar diferentes baudrates

for baud in BAUDRATES:
    print(f"\nProbando {PORT} @ {baud} baudios…")
    try:
        ser = serial.Serial(PORT, baud, timeout=2)
        print(f"✔. Puerto abierto")
        
        # Limpiar buffer
        ser.reset_input_buffer()
        
        print("Leyendo 5 segundos…")
        start_time = time.time()
        data_received = False
        
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"  RX ({len(data)} bytes): {data}")
                try:
                    decoded = data.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        print(f"  Decodificado: {decoded}")
                        data_received = True
                except:
                    pass
            time.sleep(0.1)
        
        ser.close()
        
        if data_received:
            print(f"✔. ÉXITO: Datos recibidos @ {baud} baudios")
            print(f"\n★ USA BAUDRATE: {baud}")
            break
        else:
            print(f"✗ No se recibieron datos @ {baud} baudios")
            
    except serial.SerialException as e:
        print(f"✗ Error: {e}")
    except Exception as e:
        print(f"✗ Error inesperado: {e}")

# 4. Verificar procesos usando el puerto
print("\n4. PROCESOS USANDO EL PUERTO:")
print("-" * 40)
try:
    result = subprocess.run(["sudo", "lsof", "/dev/serial0"], 
                          capture_output=True, text=True, timeout=5)
    if result.stdout:
        print("✱  Procesos usando /dev/serial0:")
        print(result.stdout)
    else:
        print("✔. Ningún proceso está usando /dev/serial0")
except:
    print("   No se pudo verificar (instala lsof: sudo apt install lsof)")

# 5. Resumen y soluciones
print("\n" + "="*60)
print("RESUMEN Y SOLUCIONES:")
print("="*60)

print("""
Si no recibes datos:

1. VERIFICA EL CABLEADO:
   ESP32 TX (GPIO17) → Pi RX (GPIO15 / pin físico 10)
   ESP32 RX (GPIO16) → Pi TX (GPIO14 / pin físico 8)
   GND común

2. VERIFICA EL ESP32:
   - ¿Está encendido y ejecutando el firmware?
   - Conecta el ESP32 por USB a tu PC y abre el monitor serie
   - Deberías ver líneas como: G:123.45,S:1

3. CONFIGURA LA RASPBERRY PI:
   sudo raspi-config
   → Interface Options → Serial Port
   → NO a "login shell over serial"
   → YES a "serial port hardware enabled"
   
4. EDITA /boot/config.txt:
   enable_uart=1
   dtoverlay=disable-bt  # Si usas Pi 3/4/Zero2W
   
5. EDITA /boot/cmdline.txt:
   Elimina: console=serial0,115200 console=ttyAMA0,115200
   
6. REINICIA:
   sudo reboot
""")

