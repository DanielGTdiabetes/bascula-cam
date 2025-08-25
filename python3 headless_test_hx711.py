#!/usr/bin/env python3
"""
Test de HX711 sin GUI - Solo terminal
Para probar la conexión HX711 sin necesidad de display
"""

import time
import json
from datetime import datetime

# Importar HX711 (versión 1.1.2.3 ya instalada)
try:
    import RPi.GPIO as GPIO
    from hx711 import HX711
    HX711_AVAILABLE = True
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("✅ HX711 library (v1.1.2.3) disponible")
except ImportError as e:
    print(f"❌ HX711 no disponible: {e}")
    HX711_AVAILABLE = False

class HeadlessLoadCellTester:
    def __init__(self):
        self.setup_hx711()
        self.readings = []
        
    def setup_hx711(self):
        """Configurar HX711 con librería v1.1.2.3"""
        if HX711_AVAILABLE:
            try:
                print("🔧 Inicializando HX711 (v1.1.2.3)...")
                # Sintaxis correcta para hx711 v1.1.2.3
                self.hx = HX711(
                    dout_pin=5,
                    pd_sck_pin=6,
                    channel='A',
                    gain=64
                )
                
                print("🔄 Reseteando HX711...")
                self.hx.reset()
                time.sleep(2)
                
                print("✅ HX711 conectado correctamente")
                self.connection_status = "Conectado"
                
            except Exception as e:
                print(f"❌ Error inicializando HX711: {e}")
                print(f"Detalles del error: {type(e).__name__}")
                self.hx = None
                self.connection_status = "Error"
        else:
            self.hx = None
            self.connection_status = "Simulación"
            print("🔄 Modo simulación activado")
    
    def read_raw_data(self):
        """Leer datos RAW con hx711 v1.1.2.3"""
        if self.hx and HX711_AVAILABLE:
            try:
                # La librería v1.1.2.3 usa get_raw_data() con parámetro times
                raw_data = self.hx.get_raw_data(times=5)
                if raw_data and len(raw_data) > 0:
                    # Filtrar valores None si existen
                    valid_data = [x for x in raw_data if x is not None]
                    return valid_data if valid_data else None
                else:
                    print("⚠️  No se recibieron datos")
                    return None
            except Exception as e:
                print(f"❌ Error leyendo datos: {e}")
                return None
        else:
            # Simulación
            import random
            return [random.randint(8000000, 8500000) for _ in range(5)]
    
    def test_readings(self, count=10):
        """Test de lecturas básico"""
        print(f"\n📊 TEST DE {count} LECTURAS")
        print("=" * 50)
        
        readings = []
        for i in range(count):
            print(f"Lectura {i+1}/{count}...", end=" ")
            
            raw_data = self.read_raw_data()
            if raw_data:
                avg = sum(raw_data) / len(raw_data)
                readings.append(avg)
                print(f"✅ {avg:.0f}")
            else:
                print("❌ Error")
                
            time.sleep(0.5)
        
        if readings:
            print(f"\n📈 ESTADÍSTICAS:")
            print(f"   Promedio: {sum(readings)/len(readings):.2f}")
            print(f"   Máximo: {max(readings):.2f}")
            print(f"   Mínimo: {min(readings):.2f}")
            print(f"   Rango: {max(readings) - min(readings):.2f}")
            
            # Calcular estabilidad
            if len(readings) > 1:
                import statistics
                std_dev = statistics.stdev(readings)
                print(f"   Desv. Estándar: {std_dev:.2f}")
                
                if std_dev < 1000:
                    print("   ✅ Estabilidad: BUENA")
                elif std_dev < 5000:
                    print("   ⚠️  Estabilidad: REGULAR")
                else:
                    print("   ❌ Estabilidad: MALA")
        
        return readings
    
    def calibration_assistant(self):
        """Asistente de calibración paso a paso"""
        print("\n⚖️  ASISTENTE DE CALIBRACIÓN")
        print("=" * 50)
        
        # Paso 1: Sin peso
        print("\n1️⃣  PASO 1: Establecer punto cero")
        print("   • Retira todo peso de la celda de carga")
        input("   • Presiona Enter cuando esté listo...")
        
        print("   🔄 Tomando lecturas sin peso...")
        zero_readings = []
        for i in range(15):
            raw_data = self.read_raw_data()
            if raw_data:
                zero_readings.extend(raw_data)
            print(f"   Lectura {i+1}/15", end="\r")
            time.sleep(0.2)
        
        if zero_readings:
            offset = sum(zero_readings) / len(zero_readings)
            print(f"\n   ✅ Offset establecido: {offset:.2f}")
            
            # Con hx711 v1.1.2.3, establecer offset manualmente
            if self.hx and HX711_AVAILABLE:
                # Establecer offset interno (algunos métodos varían por versión)
                try:
                    # Método 1: si tiene set_offset
                    if hasattr(self.hx, 'set_offset'):
                        self.hx.set_offset(offset)
                        print("   ✅ Offset aplicado con set_offset()")
                    else:
                        # Método 2: guardar offset manualmente
                        self.hx._offset_A_128 = offset
                        print("   ✅ Offset guardado manualmente")
                except Exception as e:
                    print(f"   ⚠️  Advertencia estableciendo offset: {e}")
                    self.manual_offset = offset  # Guardar para uso manual
        else:
            print("\n   ❌ Error estableciendo offset")
            return
        
        # Paso 2: Con peso conocido
        print(f"\n2️⃣  PASO 2: Calibración con peso conocido")
        
        while True:
            try:
                weight_str = input("   • Introduce el peso conocido en gramos (ej: 500): ")
                known_weight = float(weight_str)
                break
            except ValueError:
                print("   ❌ Por favor introduce un número válido")
        
        print(f"   • Coloca exactamente {known_weight}g en la celda de carga")
        input("   • Presiona Enter cuando esté colocado...")
        
        print("   🔄 Tomando lecturas con peso...")
        weight_readings = []
        for i in range(10):
            raw_data = self.read_raw_data()
            if raw_data:
                weight_readings.extend(raw_data)
            print(f"   Lectura {i+1}/10", end="\r")
            time.sleep(0.3)
        
        if weight_readings:
            avg_with_weight = sum(weight_readings) / len(weight_readings)
            
            # Usar offset previo
            if hasattr(self, 'manual_offset'):
                offset = self.manual_offset
            elif self.hx and hasattr(self.hx, '_offset_A_128'):
                offset = self.hx._offset_A_128
            else:
                offset = 8250000  # Valor por defecto para simulación
            
            scale_factor = (avg_with_weight - offset) / known_weight
            
            # Con hx711 v1.1.2.3, establecer la escala
            if self.hx and HX711_AVAILABLE:
                try:
                    # Método 1: si tiene set_scale
                    if hasattr(self.hx, 'set_scale'):
                        self.hx.set_scale(scale_factor)
                        print(f"\n   ✅ Escala aplicada con set_scale(): {scale_factor:.6f}")
                    else:
                        # Método 2: guardar manualmente
                        self.hx._scale_A_128 = scale_factor
                        print(f"\n   ✅ Escala guardada manualmente: {scale_factor:.6f}")
                        self.manual_scale = scale_factor
                except Exception as e:
                    print(f"   ⚠️  Advertencia estableciendo escala: {e}")
                    self.manual_scale = scale_factor
            else:
                print(f"\n   ✅ Factor de escala (sim): {scale_factor:.6f}")
            
            print(f"   ✅ Lectura promedio con peso: {avg_with_weight:.2f}")
            
            # Prueba de calibración
            print(f"\n3️⃣  PRUEBA DE CALIBRACIÓN")
            print("   🔄 Convirtiendo lecturas a peso...")
            
            test_readings = []
            for i in range(5):
                raw_data = self.read_raw_data()
                if raw_data:
                    avg_raw = sum(raw_data) / len(raw_data)
                    # Calcular peso manualmente ya que la librería puede no tener get_weight
                    calculated_weight = (avg_raw - offset) / scale_factor
                    test_readings.append(calculated_weight)
                    print(f"   Peso calculado: {calculated_weight:.1f}g")
                time.sleep(0.5)
            
            if test_readings:
                avg_calculated = sum(test_readings) / len(test_readings)
                error = abs(avg_calculated - known_weight)
                error_percent = (error / known_weight) * 100
                
                print(f"\n   📊 RESULTADOS DE CALIBRACIÓN:")
                print(f"      Peso real: {known_weight:.1f}g")
                print(f"      Peso promedio medido: {avg_calculated:.1f}g")
                print(f"      Error: {error:.1f}g ({error_percent:.1f}%)")
                
                if error_percent < 2:
                    print("      ✅ CALIBRACIÓN EXCELENTE")
                elif error_percent < 5:
                    print("      ⚠️  CALIBRACIÓN BUENA")
                else:
                    print("      ❌ CALIBRACIÓN NECESITA AJUSTE")
                
                # Guardar datos de calibración
                cal_data = {
                    "timestamp": datetime.now().isoformat(),
                    "offset": offset,
                    "scale_factor": scale_factor,
                    "known_weight": known_weight,
                    "measured_weight": avg_calculated,
                    "error_percent": error_percent
                }
                
                try:
                    with open("calibracion.json", "w") as f:
                        json.dump(cal_data, f, indent=2)
                    print(f"      💾 Datos guardados en calibracion.json")
                except Exception as e:
                    print(f"      ⚠️  Error guardando: {e}")
                    
        else:
            print("\n   ❌ Error leyendo datos con peso")
    
    def continuous_monitoring(self, duration=60):
        """Monitoreo continuo"""
        print(f"\n📡 MONITOREO CONTINUO ({duration}s)")
        print("=" * 50)
        print("Presiona Ctrl+C para detener")
        
        readings = []
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                raw_data = self.read_raw_data()
                
                if raw_data and self.hx and HX711_AVAILABLE:
                    # Convertir a peso si está calibrado
                    if hasattr(self.hx, '_offset') and hasattr(self.hx, '_scale'):
                        avg_raw = sum(raw_data) / len(raw_data)
                        weight = (avg_raw - self.hx._offset) / self.hx._scale
                        readings.append(weight)
                        
                        elapsed = time.time() - start_time
                        print(f"⏱️  {elapsed:5.1f}s | Peso: {weight:8.1f}g | RAW: {avg_raw:.0f}")
                    else:
                        avg_raw = sum(raw_data) / len(raw_data)
                        readings.append(avg_raw)
                        
                        elapsed = time.time() - start_time
                        print(f"⏱️  {elapsed:5.1f}s | RAW: {avg_raw:.0f} (sin calibrar)")
                elif raw_data:
                    # Modo simulación
                    avg_raw = sum(raw_data) / len(raw_data)
                    simulated_weight = (avg_raw - 8250000) / 1000
                    readings.append(simulated_weight)
                    
                    elapsed = time.time() - start_time
                    print(f"⏱️  {elapsed:5.1f}s | Peso: {simulated_weight:8.1f}g (sim)")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n⏹️  Monitoreo detenido por usuario")
        
        # Mostrar resumen
        if readings:
            print(f"\n📊 RESUMEN DE {len(readings)} LECTURAS:")
            print(f"   Promedio: {sum(readings)/len(readings):.2f}")
            print(f"   Máximo: {max(readings):.2f}")  
            print(f"   Mínimo: {min(readings):.2f}")
    
    def menu_principal(self):
        """Menú principal"""
        while True:
            print(f"\n{'='*60}")
            print(f"🏭 PROBADOR DE CELDA DE CARGA - MODO TERMINAL")
            print(f"{'='*60}")
            print(f"Estado: {self.connection_status}")
            print(f"Pines: DOUT=GPIO5, SCK=GPIO6")
            print()
            print("1️⃣  Test de lecturas básico")
            print("2️⃣  Asistente de calibración completo")
            print("3️⃣  Monitoreo continuo") 
            print("4️⃣  Información del sistema")
            print("0️⃣  Salir")
            print("="*60)
            
            try:
                opcion = input("Selecciona una opción: ").strip()
                
                if opcion == "1":
                    count = input("Número de lecturas (default 10): ") or "10"
                    self.test_readings(int(count))
                    
                elif opcion == "2":
                    self.calibration_assistant()
                    
                elif opcion == "3":
                    duration = input("Duración en segundos (default 60): ") or "60"
                    self.continuous_monitoring(int(duration))
                    
                elif opcion == "4":
                    self.show_system_info()
                    
                elif opcion == "0":
                    print("👋 ¡Hasta luego!")
                    break
                    
                else:
                    print("❌ Opción no válida")
                    
            except ValueError:
                print("❌ Por favor introduce un número válido")
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def show_system_info(self):
        """Mostrar información del sistema"""
        print(f"\n💻 INFORMACIÓN DEL SISTEMA")
        print("=" * 50)
        print(f"Estado HX711: {self.connection_status}")
        print(f"Pin DOUT: GPIO 5")
        print(f"Pin SCK: GPIO 6")
        
        if self.hx and HX711_AVAILABLE:
            print(f"Canal: A")
            print(f"Ganancia: 64")
            
            if hasattr(self.hx, '_offset'):
                print(f"Offset: {self.hx._offset:.2f}")
            else:
                print(f"Offset: No establecido")
                
            if hasattr(self.hx, '_scale'):
                print(f"Factor de escala: {self.hx._scale:.6f}")
            else:
                print(f"Factor de escala: No calibrado")
        
        # Test de conectividad
        print(f"\n🔍 TEST DE CONECTIVIDAD:")
        raw_data = self.read_raw_data()
        if raw_data:
            print(f"✅ Comunicación OK")
            print(f"   Última lectura: {sum(raw_data)/len(raw_data):.0f}")
        else:
            print(f"❌ Error de comunicación")
    
    def cleanup(self):
        """Limpiar recursos"""
        if HX711_AVAILABLE:
            try:
                GPIO.cleanup()
                print("🧹 GPIO limpiado")
            except:
                pass

def main():
    print("🚀 Iniciando probador de celda de carga...")
    
    tester = HeadlessLoadCellTester()
    
    try:
        tester.menu_principal()
    except KeyboardInterrupt:
        print("\n⏹️  Programa interrumpido")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main()