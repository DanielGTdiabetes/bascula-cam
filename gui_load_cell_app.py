#!/usr/bin/env python3
"""
Aplicación GUI para celda de carga con HX711 optimizada para pantalla táctil 7"
Resolución recomendada: 800x480
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import numpy as np
import time
import threading
import queue
from datetime import datetime
import json
import os
from collections import deque

# Importar HX711 (comentar si no está disponible para desarrollo)
try:
    from hx711py import HX711
    HX711_AVAILABLE = True
except ImportError:
    print("Advertencia: hx711py no disponible - usando datos simulados")
    HX711_AVAILABLE = False

class LoadCellGUI:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.setup_hx711()
        self.create_widgets()
        self.setup_data_logging()
        self.start_reading_thread()
        
    def setup_window(self):
        """Configuración de la ventana principal"""
        self.root.title("Báscula Digital Profesional")
        self.root.geometry("800x480")
        self.root.configure(bg='#2c3e50')
        
        # Pantalla completa para pantalla táctil (comentar si no se desea)
        # self.root.attributes('-fullscreen', True)
        
        # Configurar estilos
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
    def configure_styles(self):
        """Configurar estilos personalizados"""
        # Botones grandes para táctil
        self.style.configure('Large.TButton', 
                           font=('Arial', 14, 'bold'),
                           padding=(20, 15))
        
        # Labels grandes
        self.style.configure('Title.TLabel',
                           font=('Arial', 18, 'bold'),
                           background='#2c3e50',
                           foreground='white')
        
        self.style.configure('Status.TLabel',
                           font=('Arial', 12),
                           background='#2c3e50',
                           foreground='#ecf0f1')
        
        # Frame estilo
        self.style.configure('Card.TFrame',
                           background='#34495e',
                           relief='raised',
                           borderwidth=2)
    
    def setup_variables(self):
        """Inicializar variables"""
        self.current_weight = tk.DoubleVar(value=0.0)
        self.max_weight = tk.DoubleVar(value=0.0)
        self.min_weight = tk.DoubleVar(value=0.0)
        self.tare_weight = tk.DoubleVar(value=0.0)
        self.unit = tk.StringVar(value="g")
        self.is_reading = False
        self.is_calibrated = False
        
        # Datos para gráfico
        self.weight_history = deque(maxlen=100)
        self.time_history = deque(maxlen=100)
        
        # Queue para comunicación entre hilos
        self.weight_queue = queue.Queue()
        
    def setup_hx711(self):
        """Configurar HX711"""
        if HX711_AVAILABLE:
            try:
                self.hx = HX711(dout_pin=5, sck_pin=6)
                self.hx.reset()
                time.sleep(2)
                self.connection_status = "Conectado"
            except Exception as e:
                self.connection_status = f"Error: {e}"
                self.hx = None
        else:
            self.hx = None
            self.connection_status = "Simulación"
    
    def create_widgets(self):
        """Crear interfaz gráfica"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crear secciones
        self.create_header(main_frame)
        self.create_weight_display(main_frame)
        self.create_control_buttons(main_frame)
        self.create_graph_section(main_frame)
        self.create_status_bar(main_frame)
    
    def create_header(self, parent):
        """Crear header con título e información"""
        header_frame = ttk.Frame(parent, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(header_frame, 
                               text="🏭 BÁSCULA INDUSTRIAL",
                               style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Frame para información adicional
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        # Información del sensor
        ttk.Label(info_frame, text=f"Estado: {self.connection_status}",
                 style='Status.TLabel').pack(side=tk.LEFT)
        
        # Hora actual
        self.time_label = ttk.Label(info_frame, text="", style='Status.TLabel')
        self.time_label.pack(side=tk.RIGHT)
        self.update_time()
    
    def create_weight_display(self, parent):
        """Crear display principal del peso"""
        display_frame = ttk.Frame(parent, style='Card.TFrame')
        display_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Peso principal (muy grande y visible)
        weight_frame = ttk.Frame(display_frame)
        weight_frame.pack(pady=20)
        
        self.weight_label = tk.Label(weight_frame,
                                   textvariable=self.current_weight,
                                   font=('Digital-7', 48, 'bold'),
                                   fg='#2ecc71',
                                   bg='#2c3e50',
                                   width=12)
        self.weight_label.pack(side=tk.LEFT)
        
        self.unit_label = tk.Label(weight_frame,
                                 textvariable=self.unit,
                                 font=('Arial', 24, 'bold'),
                                 fg='#3498db',
                                 bg='#2c3e50')
        self.unit_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Frame para estadísticas
        stats_frame = ttk.Frame(display_frame)
        stats_frame.pack(pady=(0, 20))
        
        # Estadísticas en tres columnas
        stats_columns = ttk.Frame(stats_frame)
        stats_columns.pack()
        
        # Máximo
        max_frame = ttk.Frame(stats_columns)
        max_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(max_frame, text="MÁXIMO", font=('Arial', 10, 'bold')).pack()
        self.max_label = ttk.Label(max_frame, textvariable=self.max_weight,
                                  font=('Arial', 14), foreground='#e74c3c')
        self.max_label.pack()
        
        # Mínimo
        min_frame = ttk.Frame(stats_columns)
        min_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(min_frame, text="MÍNIMO", font=('Arial', 10, 'bold')).pack()
        self.min_label = ttk.Label(min_frame, textvariable=self.min_weight,
                                  font=('Arial', 14), foreground='#3498db')
        self.min_label.pack()
        
        # Tara
        tare_frame = ttk.Frame(stats_columns)
        tare_frame.pack(side=tk.LEFT, padx=20)
        ttk.Label(tare_frame, text="TARA", font=('Arial', 10, 'bold')).pack()
        self.tare_label = ttk.Label(tare_frame, textvariable=self.tare_weight,
                                   font=('Arial', 14), foreground='#f39c12')
        self.tare_label.pack()
    
    def create_control_buttons(self, parent):
        """Crear botones de control táctil"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Primera fila de botones
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=2)
        
        self.tare_btn = ttk.Button(row1, text="🔄 TARA", 
                                  command=self.tare,
                                  style='Large.TButton')
        self.tare_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.calibrate_btn = ttk.Button(row1, text="⚖️ CALIBRAR",
                                       command=self.show_calibration_dialog,
                                       style='Large.TButton')
        self.calibrate_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.unit_btn = ttk.Button(row1, text="📏 g/kg",
                                  command=self.toggle_unit,
                                  style='Large.TButton')
        self.unit_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Segunda fila de botones
        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=2)
        
        self.reset_btn = ttk.Button(row2, text="🔄 RESET",
                                   command=self.reset_stats,
                                   style='Large.TButton')
        self.reset_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.save_btn = ttk.Button(row2, text="💾 GUARDAR",
                                  command=self.save_measurement,
                                  style='Large.TButton')
        self.save_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.exit_btn = ttk.Button(row2, text="🚪 SALIR",
                                  command=self.safe_exit,
                                  style='Large.TButton')
        self.exit_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
    
    def create_graph_section(self, parent):
        """Crear sección del gráfico en tiempo real"""
        graph_frame = ttk.Frame(parent, style='Card.TFrame')
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Título del gráfico
        ttk.Label(graph_frame, text="📊 Gráfico en Tiempo Real",
                 style='Title.TLabel').pack(pady=(10, 5))
        
        # Configurar matplotlib para la GUI
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(8, 3))
        self.fig.patch.set_facecolor('#2c3e50')
        
        self.ax.set_facecolor('#34495e')
        self.ax.set_xlabel('Tiempo (s)', color='white')
        self.ax.set_ylabel('Peso (g)', color='white')
        self.ax.tick_params(colors='white')
        
        # Línea del gráfico
        self.line, = self.ax.plot([], [], 'g-', linewidth=2, label='Peso')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        # Canvas para tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Iniciar animación
        self.animation = FuncAnimation(self.fig, self.update_graph, 
                                     interval=500, blit=False)
    
    def create_status_bar(self, parent):
        """Crear barra de estado"""
        status_frame = ttk.Frame(parent, style='Card.TFrame')
        status_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(status_frame,
                                     text="✅ Sistema listo",
                                     style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Indicador de actividad
        self.activity_label = ttk.Label(status_frame, text="●", 
                                       font=('Arial', 16),
                                       foreground='#2ecc71')
        self.activity_label.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def setup_data_logging(self):
        """Configurar sistema de guardado de datos"""
        self.data_file = "mediciones_bascula.json"
        
        # Cargar datos existentes si existen
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.saved_data = json.load(f)
            except:
                self.saved_data = []
        else:
            self.saved_data = []
    
    def start_reading_thread(self):
        """Iniciar hilo de lectura del sensor"""
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
        self.reading_thread.start()
        
        # Iniciar actualización de la GUI
        self.root.after(100, self.update_gui)
    
    def reading_loop(self):
        """Bucle principal de lectura del sensor"""
        while self.is_reading:
            try:
                if self.hx and HX711_AVAILABLE:
                    # Lectura real del sensor
                    raw_weight = self.hx.get_weight(3)
                    weight = round(raw_weight, 1)
                else:
                    # Datos simulados para desarrollo
                    weight = round(np.random.normal(100, 5), 1)
                    time.sleep(0.1)
                
                # Enviar peso al queue
                self.weight_queue.put(weight)
                
            except Exception as e:
                print(f"Error en lectura: {e}")
                time.sleep(0.5)
    
    def update_gui(self):
        """Actualizar GUI con nuevos datos"""
        try:
            # Obtener último peso del queue
            while not self.weight_queue.empty():
                weight = self.weight_queue.get_nowait()
                self.process_new_weight(weight)
            
            # Programar próxima actualización
            self.root.after(100, self.update_gui)
            
        except Exception as e:
            print(f"Error actualizando GUI: {e}")
            self.root.after(100, self.update_gui)
    
    def process_new_weight(self, weight):
        """Procesar nuevo peso recibido"""
        # Actualizar peso actual
        if self.unit.get() == "kg" and abs(weight) >= 1000:
            display_weight = weight / 1000
            self.current_weight.set(f"{display_weight:.3f}")
        else:
            self.current_weight.set(f"{weight:.1f}")
        
        # Actualizar estadísticas
        if weight > self.max_weight.get():
            self.max_weight.set(f"{weight:.1f}")
        if weight < self.min_weight.get() or self.min_weight.get() == 0:
            self.min_weight.set(f"{weight:.1f}")
        
        # Agregar a histórico para gráfico
        current_time = time.time()
        self.weight_history.append(weight)
        self.time_history.append(current_time)
        
        # Cambiar color según peso
        if abs(weight) < 5:
            color = '#95a5a6'  # Gris para cero
        elif weight > 9000:  # Cerca del límite de 10kg
            color = '#e74c3c'  # Rojo para sobrecarga
        else:
            color = '#2ecc71'  # Verde normal
        
        self.weight_label.configure(fg=color)
        
        # Actualizar indicador de actividad
        current_color = self.activity_label.cget('foreground')
        new_color = '#e74c3c' if current_color == '#2ecc71' else '#2ecc71'
        self.activity_label.configure(foreground=new_color)
    
    def update_graph(self, frame):
        """Actualizar gráfico en tiempo real"""
        if len(self.time_history) > 1:
            # Convertir tiempo a relativo
            times = np.array(self.time_history)
            times = times - times[-1]  # Tiempo relativo al último punto
            
            weights = np.array(self.weight_history)
            
            self.line.set_data(times, weights)
            
            # Ajustar límites
            self.ax.set_xlim(min(times), 0)
            y_min, y_max = min(weights) * 0.9, max(weights) * 1.1
            if y_max - y_min < 10:  # Mínimo rango de 10g
                y_center = (y_max + y_min) / 2
                y_min, y_max = y_center - 5, y_center + 5
            self.ax.set_ylim(y_min, y_max)
        
        return self.line,
    
    def tare(self):
        """Establecer tara (punto cero)"""
        if self.hx and HX711_AVAILABLE:
            try:
                self.hx.tare()
                current_weight = self.current_weight.get()
                self.tare_weight.set(f"{float(current_weight.split()[0]) if ' ' in str(current_weight) else current_weight:.1f}")
                self.status_label.configure(text="✅ Tara establecida")
            except Exception as e:
                messagebox.showerror("Error", f"Error estableciendo tara: {e}")
        else:
            # Simulación
            self.tare_weight.set(f"{self.current_weight.get():.1f}")
            self.status_label.configure(text="✅ Tara establecida (simulación)")
    
    def toggle_unit(self):
        """Cambiar entre gramos y kilogramos"""
        if self.unit.get() == "g":
            self.unit.set("kg")
        else:
            self.unit.set("g")
        
        self.status_label.configure(text=f"📏 Unidad cambiada a {self.unit.get()}")
    
    def reset_stats(self):
        """Reiniciar estadísticas"""
        self.max_weight.set(0.0)
        self.min_weight.set(0.0)
        self.tare_weight.set(0.0)
        self.weight_history.clear()
        self.time_history.clear()
        self.status_label.configure(text="🔄 Estadísticas reiniciadas")
    
    def show_calibration_dialog(self):
        """Mostrar diálogo de calibración"""
        dialog = CalibrationDialog(self.root, self.hx)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            self.is_calibrated = True
            self.status_label.configure(text="⚖️ Calibración completada")
    
    def save_measurement(self):
        """Guardar medición actual"""
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "weight": float(str(self.current_weight.get()).split()[0]) if ' ' in str(self.current_weight.get()) else float(self.current_weight.get()),
            "unit": self.unit.get(),
            "tare": float(self.tare_weight.get())
        }
        
        self.saved_data.append(measurement)
        
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.saved_data, f, indent=2)
            
            self.status_label.configure(text=f"💾 Medición guardada ({len(self.saved_data)} total)")
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando: {e}")
    
    def update_time(self):
        """Actualizar reloj"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.configure(text=current_time)
        self.root.after(1000, self.update_time)
    
    def safe_exit(self):
        """Salida segura de la aplicación"""
        if messagebox.askyesno("Salir", "¿Seguro que quieres salir?"):
            self.is_reading = False
            self.root.quit()

class CalibrationDialog:
    """Diálogo de calibración"""
    def __init__(self, parent, hx):
        self.hx = hx
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Calibración")
        self.dialog.geometry("400x300")
        self.dialog.configure(bg='#2c3e50')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_calibration_widgets()
    
    def create_calibration_widgets(self):
        """Crear widgets del diálogo de calibración"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="⚖️ Calibración de la Báscula",
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        ttk.Label(main_frame, 
                 text="1. Retira todo peso de la báscula\n2. Presiona 'Establecer Cero'",
                 font=('Arial', 12)).pack(pady=(0, 20))
        
        ttk.Button(main_frame, text="Establecer Cero",
                  command=self.set_zero,
                  style='Large.TButton').pack(pady=10, fill=tk.X)
        
        ttk.Label(main_frame, 
                 text="3. Coloca un peso conocido\n4. Introduce el peso y presiona 'Calibrar'",
                 font=('Arial', 12)).pack(pady=(20, 10))
        
        # Frame para peso conocido
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(weight_frame, text="Peso conocido (g):").pack(side=tk.LEFT)
        self.weight_entry = ttk.Entry(weight_frame, font=('Arial', 14))
        self.weight_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        self.weight_entry.insert(0, "500")
        
        ttk.Button(main_frame, text="Calibrar",
                  command=self.calibrate,
                  style='Large.TButton').pack(pady=20, fill=tk.X)
        
        ttk.Button(main_frame, text="Cancelar",
                  command=self.cancel,
                  style='Large.TButton').pack(fill=tk.X)
    
    def set_zero(self):
        """Establecer punto cero"""
        if self.hx and HX711_AVAILABLE:
            try:
                self.hx.reset()
                time.sleep(1)
                self.hx.tare()
                messagebox.showinfo("Éxito", "Punto cero establecido")
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
        else:
            messagebox.showinfo("Simulación", "Punto cero establecido (simulación)")
    
    def calibrate(self):
        """Realizar calibración"""
        try:
            known_weight = float(self.weight_entry.get())
            
            if self.hx and HX711_AVAILABLE:
                # Tomar varias lecturas para mayor precisión
                readings = []
                for _ in range(10):
                    reading = self.hx.get_weight(3)
                    readings.append(reading)
                    time.sleep(0.1)
                
                avg_reading = sum(readings) / len(readings)
                reference_unit = avg_reading / known_weight
                self.hx.set_reference_unit(reference_unit)
                
                messagebox.showinfo("Éxito", 
                                  f"Calibración completada\nUnidad de referencia: {reference_unit:.6f}")
                
            else:
                messagebox.showinfo("Simulación", "Calibración completada (simulación)")
            
            self.result = True
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Introduce un peso válido")
        except Exception as e:
            messagebox.showerror("Error", f"Error en calibración: {e}")
    
    def cancel(self):
        """Cancelar calibración"""
        self.dialog.destroy()

def main():
    """Función principal"""
    root = tk.Tk()
    app = LoadCellGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación cerrada por usuario")

if __name__ == "__main__":
    main()