#!/usr/bin/env python3
"""
GUI Báscula Digital - Configurada para HX711 funcionando
Basada en las lecturas exitosas: valores ~-8575
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading
import queue
from datetime import datetime
import json
import os
from collections import deque
import math

# HX711 - ¡Sabemos que funciona!
try:
    import RPi.GPIO as GPIO
    from hx711 import HX711
    HX711_AVAILABLE = True
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("✅ HX711 disponible y funcionando")
except ImportError:
    HX711_AVAILABLE = False
    print("❌ HX711 no disponible")

class BasculaDigital:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.setup_hx711()
        self.create_widgets()
        self.start_reading()
        
    def setup_window(self):
        """Configurar ventana principal"""
        self.root.title("🏭 Báscula Digital Pro - HX711")
        self.root.geometry("800x480")
        self.root.configure(bg='#1a1a1a')
        
        # Configurar estilos
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Bind para salir
        self.root.bind('<Escape>', lambda e: self.safe_exit())
    
    def setup_variables(self):
        """Variables principales"""
        self.current_weight = 0.0
        self.max_weight = float('-inf')
        self.min_weight = float('inf')
        self.tare_offset = 0.0
        self.scale_factor = 1.0
        self.is_reading = False
        self.readings = deque(maxlen=100)
        self.weight_queue = queue.Queue()
        
        # Configuración basada en tus lecturas exitosas
        self.base_offset = -8575  # Promedio de tus lecturas sin peso
        
    def setup_hx711(self):
        """Configurar HX711 - sabemos que funciona"""
        if HX711_AVAILABLE:
            try:
                print("🔧 Inicializando HX711 (configuración probada)...")
                self.hx = HX711(
                    dout_pin=5,
                    pd_sck_pin=6,
                    channel='A',
                    gain=64
                )
                
                self.hx.reset()
                time.sleep(2)
                
                print("✅ HX711 inicializado correctamente")
                self.connection_status = "✅ Conectado"
                
            except Exception as e:
                print(f"❌ Error: {e}")
                self.hx = None
                self.connection_status = f"❌ {str(e)[:20]}"
        else:
            self.hx = None
            self.connection_status = "🔄 Simulación"
    
    def create_widgets(self):
        """Crear interfaz"""
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=5)
        
        title = tk.Label(header, text="🏭 BÁSCULA DIGITAL HX711", 
                        font=('Arial', 20, 'bold'), 
                        fg='white', bg='#1a1a1a')
        title.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(header, text=self.connection_status,
                                    font=('Arial', 12),
                                    fg='#2ecc71', bg='#1a1a1a')
        self.status_label.pack(side=tk.RIGHT)
        
        # Display principal
        display_frame = tk.Frame(self.root, bg='#2c3e50', relief='raised', bd=2)
        display_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Peso principal
        self.weight_display = tk.Label(display_frame,
                                      text="0.0",
                                      font=('Courier New', 48, 'bold'),
                                      fg='#2ecc71', bg='#2c3e50')
        self.weight_display.pack(pady=20)
        
        self.unit_label = tk.Label(display_frame, text="gramos",
                                  font=('Arial', 16), 
                                  fg='#3498db', bg='#2c3e50')
        self.unit_label.pack()
        
        # Estadísticas
        stats_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.stats_text = tk.Label(stats_frame,
                                  text="Lecturas: 0 | Promedio: 0.0g | Rango: 0.0g",
                                  font=('Arial', 11),
                                  fg='white', bg='#34495e')
        self.stats_text.pack(pady=8)
        
        # Botones de control
        self.create_control_buttons()
        
        # Mini gráfico
        self.create_mini_graph()
        
        # Datos RAW (para debugging)
        raw_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        raw_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.raw_label = tk.Label(raw_frame, text="RAW: -- | OFFSET: -- | FACTOR: --",
                                 font=('Courier New', 9),
                                 fg='#95a5a6', bg='#34495e')
        self.raw_label.pack(pady=5)
    
    def create_control_buttons(self):
        """Botones de control táctil"""
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Primera fila
        row1 = tk.Frame(btn_frame)
        row1.pack(fill=tk.X, pady=2)
        
        self.tare_btn = tk.Button(row1, text="🔄 TARA", 
                                 command=self.tare,
                                 font=('Arial', 12, 'bold'),
                                 bg='#3498db', fg='white', 
                                 height=2)
        self.tare_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.calibrate_btn = tk.Button(row1, text="⚖️ CALIBRAR",
                                      command=self.calibrate,
                                      font=('Arial', 12, 'bold'),
                                      bg='#e67e22', fg='white', 
                                      height=2)
        self.calibrate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.save_btn = tk.Button(row1, text="💾 GUARDAR",
                                 command=self.save_reading,
                                 font=('Arial', 12, 'bold'),
                                 bg='#27ae60', fg='white', 
                                 height=2)
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Segunda fila
        row2 = tk.Frame(btn_frame)
        row2.pack(fill=tk.X, pady=2)
        
        self.reset_btn = tk.Button(row2, text="🔄 RESET",
                                  command=self.reset_stats,
                                  font=('Arial', 12, 'bold'),
                                  bg='#f39c12', fg='white',
                                  height=2)
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.raw_btn = tk.Button(row2, text="📊 RAW DATA",
                                command=self.toggle_raw_display,
                                font=('Arial', 12, 'bold'),
                                bg='#9b59b6', fg='white',
                                height=2)
        self.raw_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.exit_btn = tk.Button(row2, text="🚪 SALIR",
                                 command=self.safe_exit,
                                 font=('Arial', 12, 'bold'),
                                 bg='#e74c3c', fg='white',
                                 height=2)
        self.exit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    
    def create_mini_graph(self):
        """Mini gráfico simple"""
        graph_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        graph_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(graph_frame, text="📈 Tendencia (últimas 20 lecturas)",
                font=('Arial', 11, 'bold'),
                fg='white', bg='#34495e').pack(pady=5)
        
        self.graph_canvas = tk.Canvas(graph_frame, width=760, height=80,
                                     bg='#2c3e50', highlightthickness=0)
        self.graph_canvas.pack(pady=5)
    
    def start_reading(self):
        """Iniciar lectura continua"""
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
        self.reading_thread.start()
        self.root.after(100, self.update_display)
    
    def reading_loop(self):
        """Bucle de lectura del HX711"""
        while self.is_reading:
            try:
                if self.hx and HX711_AVAILABLE:
                    # Usar la configuración que sabemos que funciona
                    raw_data = self.hx.get_raw_data(times=3)
                    
                    if raw_data and len(raw_data) > 0:
                        valid_data = [x for x in raw_data if x is not None]
                        if valid_data:
                            raw_avg = sum(valid_data) / len(valid_data)
                            # Convertir a peso usando offset y factor
                            weight = (raw_avg - self.base_offset - self.tare_offset) / self.scale_factor
                            self.weight_queue.put((weight, raw_avg))
                else:
                    # Simulación basada en tus datos reales
                    import random
                    raw_sim = -8575 + random.randint(-30, 30)
                    weight_sim = (raw_sim - self.base_offset - self.tare_offset) / self.scale_factor
                    self.weight_queue.put((weight_sim, raw_sim))
                    
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Error en lectura: {e}")
                time.sleep(0.5)
    
    def update_display(self):
        """Actualizar display"""
        try:
            # Procesar todas las lecturas pendientes
            while not self.weight_queue.empty():
                weight, raw_value = self.weight_queue.get_nowait()
                self.process_reading(weight, raw_value)
            
            self.root.after(100, self.update_display)
            
        except Exception as e:
            print(f"Error actualizando display: {e}")
            self.root.after(100, self.update_display)
    
    def process_reading(self, weight, raw_value):
        """Procesar nueva lectura"""
        self.current_weight = weight
        self.readings.append(weight)
        
        # Actualizar estadísticas
        if weight > self.max_weight:
            self.max_weight = weight
        if weight < self.min_weight:
            self.min_weight = weight
        
        # Actualizar display principal
        self.weight_display.configure(text=f"{weight:.1f}")
        
        # Color según peso
        if abs(weight) < 2:
            color = '#95a5a6'  # Gris para ~cero
        elif weight > 5000:
            color = '#e74c3c'  # Rojo para mucho peso
        else:
            color = '#2ecc71'  # Verde normal
        
        self.weight_display.configure(fg=color)
        
        # Actualizar estadísticas
        if len(self.readings) > 0:
            avg_weight = sum(self.readings) / len(self.readings)
            weight_range = self.max_weight - self.min_weight
            
            stats_text = f"Lecturas: {len(self.readings)} | Promedio: {avg_weight:.1f}g | Rango: {weight_range:.1f}g"
            self.stats_text.configure(text=stats_text)
        
        # Actualizar datos RAW
        raw_text = f"RAW: {raw_value:.0f} | OFFSET: {self.base_offset + self.tare_offset:.0f} | FACTOR: {self.scale_factor:.2f}"
        self.raw_label.configure(text=raw_text)
        
        # Actualizar mini-gráfico
        self.update_mini_graph()
    
    def update_mini_graph(self):
        """Actualizar mini-gráfico"""
        if len(self.readings) < 2:
            return
            
        self.graph_canvas.delete("graph")
        
        # Últimas 20 lecturas
        recent_readings = list(self.readings)[-20:]
        if len(recent_readings) < 2:
            return
        
        # Normalizar para el canvas
        min_val = min(recent_readings)
        max_val = max(recent_readings)
        range_val = max_val - min_val if max_val != min_val else 1
        
        canvas_width = 760
        canvas_height = 80
        
        points = []
        for i, value in enumerate(recent_readings):
            x = (i / (len(recent_readings) - 1)) * (canvas_width - 20) + 10
            y = canvas_height - 10 - ((value - min_val) / range_val) * (canvas_height - 20)
            points.extend([x, y])
        
        if len(points) >= 4:
            self.graph_canvas.create_line(points, fill='#2ecc71', width=2, tags="graph")
    
    def tare(self):
        """Establecer tara (punto cero)"""
        if hasattr(self, 'current_weight'):
            # Establecer offset de tara basado en lecturas actuales
            recent_readings = list(self.readings)[-10:] if len(self.readings) >= 10 else list(self.readings)
            if recent_readings:
                # Calcular tara en términos de peso actual
                avg_current = sum(recent_readings) / len(recent_readings)
                self.tare_offset += avg_current * self.scale_factor
                
                self.status_label.configure(text="✅ Tara establecida", fg='#2ecc71')
                self.root.after(3000, lambda: self.status_label.configure(text=self.connection_status, fg='#2ecc71'))
    
    def calibrate(self):
        """Calibración rápida"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibración")
        dialog.geometry("300x200")
        dialog.configure(bg='#2c3e50')
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="⚖️ Calibración Rápida", 
                font=('Arial', 14, 'bold'),
                fg='white', bg='#2c3e50').pack(pady=10)
        
        tk.Label(dialog, text="1. Sin peso: presiona TARA\n2. Con peso conocido: introduce peso",
                font=('Arial', 10),
                fg='white', bg='#2c3e50').pack(pady=10)
        
        weight_frame = tk.Frame(dialog, bg='#2c3e50')
        weight_frame.pack(pady=10)
        
        tk.Label(weight_frame, text="Peso conocido (g):", 
                fg='white', bg='#2c3e50').pack(side=tk.LEFT)
        weight_entry = tk.Entry(weight_frame)
        weight_entry.pack(side=tk.RIGHT)
        weight_entry.insert(0, "1000")
        
        def apply_calibration():
            try:
                known_weight = float(weight_entry.get())
                if len(self.readings) >= 5:
                    current_avg = sum(list(self.readings)[-5:]) / 5
                    if abs(current_avg) > 0.1:  # Evitar división por cero
                        new_factor = abs(current_avg * self.scale_factor / known_weight)
                        self.scale_factor = new_factor
                        self.status_label.configure(text="✅ Calibrado", fg='#2ecc71')
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Coloca peso en la báscula")
                else:
                    messagebox.showerror("Error", "Esperando más lecturas...")
            except ValueError:
                messagebox.showerror("Error", "Peso inválido")
        
        tk.Button(dialog, text="Calibrar", command=apply_calibration,
                 bg='#27ae60', fg='white', font=('Arial', 12)).pack(pady=20)
    
    def save_reading(self):
        """Guardar lectura actual"""
        if hasattr(self, 'current_weight'):
            data = {
                "timestamp": datetime.now().isoformat(),
                "weight": round(self.current_weight, 2),
                "unit": "gramos"
            }
            
            try:
                # Cargar datos existentes
                try:
                    with open("mediciones.json", "r") as f:
                        readings = json.load(f)
                except FileNotFoundError:
                    readings = []
                
                readings.append(data)
                
                with open("mediciones.json", "w") as f:
                    json.dump(readings, f, indent=2)
                
                self.status_label.configure(text=f"💾 Guardado #{len(readings)}", fg='#f39c12')
                self.root.after(3000, lambda: self.status_label.configure(text=self.connection_status, fg='#2ecc71'))
                
            except Exception as e:
                messagebox.showerror("Error", f"Error guardando: {e}")
    
    def reset_stats(self):
        """Resetear estadísticas"""
        self.readings.clear()
        self.max_weight = float('-inf')
        self.min_weight = float('inf')
        self.tare_offset = 0.0
        self.scale_factor = 1.0
        
        self.stats_text.configure(text="Lecturas: 0 | Promedio: 0.0g | Rango: 0.0g")
        self.graph_canvas.delete("graph")
        
        self.status_label.configure(text="🔄 Reset completado", fg='#f39c12')
        self.root.after(3000, lambda: self.status_label.configure(text=self.connection_status, fg='#2ecc71'))
    
    def toggle_raw_display(self):
        """Toggle visualización de datos RAW"""
        current = self.raw_label.cget('fg')
        if current == '#95a5a6':  # Gris apagado
            self.raw_label.configure(fg='#f39c12')  # Naranja activo
        else:
            self.raw_label.configure(fg='#95a5a6')  # Gris apagado
    
    def safe_exit(self):
        """Salida segura"""
        self.is_reading = False
        try:
            if HX711_AVAILABLE:
                GPIO.cleanup()
        except:
            pass
        self.root.quit()

def main():
    """Función principal"""
    root = tk.Tk()
    app = BasculaDigital(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación cerrada")
        app.safe_exit()

if __name__ == "__main__":
    main()