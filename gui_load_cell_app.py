#!/usr/bin/env python3
"""
Aplicación GUI ligera para celda de carga optimizada para Raspberry Pi Zero 2W
Sin matplotlib para mejor rendimiento
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

# Importar HX711 (sintaxis correcta)
try:
    from hx711 import HX711
    import RPi.GPIO as GPIO
    HX711_AVAILABLE = True
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
except ImportError:
    print("Advertencia: hx711 no disponible - usando datos simulados")
    HX711_AVAILABLE = False

class LightweightLoadCellGUI:
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
        self.root.title("🏭 Báscula Digital Pro")
        self.root.geometry("800x480")
        self.root.configure(bg='#1a1a1a')
        
        # Pantalla completa (descomenta si quieres)
        # self.root.attributes('-fullscreen', True)
        
        # Configurar estilos
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Bind para salir con Escape
        self.root.bind('<Escape>', lambda e: self.safe_exit())
        
    def configure_styles(self):
        """Configurar estilos personalizados"""
        # Colores para tema oscuro
        bg_dark = '#2c3e50'
        bg_card = '#34495e'
        fg_light = '#ecf0f1'
        accent = '#3498db'
        success = '#2ecc71'
        warning = '#f39c12'
        danger = '#e74c3c'
        
        # Botones grandes para táctil
        self.style.configure('Large.TButton', 
                           font=('Arial', 12, 'bold'),
                           padding=(15, 10))
        
        # Botones de acción específicos
        self.style.configure('Tare.TButton',
                           font=('Arial', 12, 'bold'),
                           padding=(15, 10))
        
        self.style.configure('Danger.TButton',
                           font=('Arial', 12, 'bold'),
                           padding=(15, 10))
        
        # Labels
        self.style.configure('Title.TLabel',
                           font=('Arial', 18, 'bold'),
                           background=bg_dark,
                           foreground=fg_light)
        
        self.style.configure('Status.TLabel',
                           font=('Arial', 10),
                           background=bg_dark,
                           foreground=fg_light)
        
        # Frames
        self.style.configure('Card.TFrame',
                           background=bg_card,
                           relief='raised',
                           borderwidth=1)
    
    def setup_variables(self):
        """Inicializar variables"""
        self.current_weight = tk.DoubleVar(value=0.0)
        self.max_weight = tk.DoubleVar(value=0.0)
        self.min_weight = tk.DoubleVar(value=0.0)
        self.tare_weight = tk.DoubleVar(value=0.0)
        self.unit = tk.StringVar(value="g")
        self.is_reading = False
        self.is_calibrated = False
        
        # Datos para mini-gráfico
        self.weight_history = deque(maxlen=50)
        self.graph_width = 300
        self.graph_height = 100
        
        # Queue para comunicación entre hilos
        self.weight_queue = queue.Queue()
        
        # Estadísticas
        self.reading_count = 0
        self.average_weight = 0.0
        
    def setup_hx711(self):
        """Configurar HX711 con sintaxis correcta"""
        if HX711_AVAILABLE:
            try:
                # Sintaxis correcta para la librería hx711
                self.hx = HX711(
                    dout_pin=5,
                    pd_sck_pin=6,
                    channel='A',
                    gain=64
                )
                self.hx.reset()
                time.sleep(2)
                self.connection_status = "✅ Conectado"
                print("HX711 inicializado correctamente")
            except Exception as e:
                self.connection_status = f"❌ Error: {str(e)[:20]}"
                self.hx = None
                print(f"Error inicializando HX711: {e}")
        else:
            self.hx = None
            self.connection_status = "🔄 Simulación"
    
    def create_widgets(self):
        """Crear interfaz gráfica"""
        # Frame principal con scroll si es necesario
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Crear secciones
        self.create_header(main_frame)
        self.create_weight_display(main_frame)
        self.create_control_buttons(main_frame)
        self.create_mini_graph(main_frame)
        self.create_statistics(main_frame)
        self.create_status_bar(main_frame)
    
    def create_header(self, parent):
        """Crear header compacto"""
        header_frame = ttk.Frame(parent, style='Card.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Frame interno para organizar contenido
        content_frame = ttk.Frame(header_frame)
        content_frame.pack(fill=tk.X, padx=10, pady=8)
        
        # Título a la izquierda
        title_label = ttk.Label(content_frame, 
                               text="🏭 BÁSCULA DIGITAL",
                               font=('Arial', 16, 'bold'),
                               background='#34495e',
                               foreground='white')
        title_label.pack(side=tk.LEFT)
        
        # Info a la derecha
        info_frame = ttk.Frame(content_frame)
        info_frame.pack(side=tk.RIGHT)
        
        # Estado conexión
        self.connection_label = ttk.Label(info_frame, 
                                         text=self.connection_status,
                                         font=('Arial', 9),
                                         background='#34495e',
                                         foreground='white')
        self.connection_label.pack()
        
        # Hora
        self.time_label = ttk.Label(info_frame, 
                                   text="",
                                   font=('Arial', 9),
                                   background='#34495e',
                                   foreground='#bdc3c7')
        self.time_label.pack()
        self.update_time()
    
    def create_weight_display(self, parent):
        """Display principal del peso - más compacto"""
        display_frame = ttk.Frame(parent, style='Card.TFrame')
        display_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Peso principal
        weight_container = ttk.Frame(display_frame)
        weight_container.pack(pady=15)
        
        # Frame para peso y unidad
        weight_row = ttk.Frame(weight_container)
        weight_row.pack()
        
        self.weight_label = tk.Label(weight_row,
                                   text="0.0",
                                   font=('Courier New', 42, 'bold'),
                                   fg='#2ecc71',
                                   bg='#34495e',
                                   width=10)
        self.weight_label.pack(side=tk.LEFT)
        
        self.unit_label = tk.Label(weight_row,
                                 textvariable=self.unit,
                                 font=('Arial', 20, 'bold'),
                                 fg='#3498db',
                                 bg='#34495e')
        self.unit_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Estadísticas compactas
        stats_frame = ttk.Frame(display_frame)
        stats_frame.pack(pady=(0, 15))
        
        # Una sola fila con estadísticas
        stats_row = ttk.Frame(stats_frame)
        stats_row.pack()
        
        # Max
        max_frame = ttk.Frame(stats_row)
        max_frame.pack(side=tk.LEFT, padx=15)
        ttk.Label(max_frame, text="MAX", font=('Arial', 8, 'bold')).pack()
        self.max_display = ttk.Label(max_frame, text="0.0",
                                    font=('Arial', 12, 'bold'), 
                                    foreground='#e74c3c')
        self.max_display.pack()
        
        # Min
        min_frame = ttk.Frame(stats_row)
        min_frame.pack(side=tk.LEFT, padx=15)
        ttk.Label(min_frame, text="MIN", font=('Arial', 8, 'bold')).pack()
        self.min_display = ttk.Label(min_frame, text="0.0",
                                    font=('Arial', 12, 'bold'),
                                    foreground='#3498db')
        self.min_display.pack()
        
        # Tara
        tare_frame = ttk.Frame(stats_row)
        tare_frame.pack(side=tk.LEFT, padx=15)
        ttk.Label(tare_frame, text="TARA", font=('Arial', 8, 'bold')).pack()
        self.tare_display = ttk.Label(tare_frame, text="0.0",
                                     font=('Arial', 12, 'bold'),
                                     foreground='#f39c12')
        self.tare_display.pack()
        
        # Promedio
        avg_frame = ttk.Frame(stats_row)
        avg_frame.pack(side=tk.LEFT, padx=15)
        ttk.Label(avg_frame, text="PROM", font=('Arial', 8, 'bold')).pack()
        self.avg_display = ttk.Label(avg_frame, text="0.0",
                                    font=('Arial', 12, 'bold'),
                                    foreground='#9b59b6')
        self.avg_display.pack()
    
    def create_control_buttons(self, parent):
        """Botones de control optimizados"""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Primera fila - controles principales
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=1)
        
        self.tare_btn = ttk.Button(row1, text="🔄 TARA", 
                                  command=self.tare,
                                  style='Large.TButton')
        self.tare_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        self.calibrate_btn = ttk.Button(row1, text="⚖️ CALIBRAR",
                                       command=self.show_calibration_dialog,
                                       style='Large.TButton')
        self.calibrate_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        self.unit_btn = ttk.Button(row1, text="📏 UNIDAD",
                                  command=self.toggle_unit,
                                  style='Large.TButton')
        self.unit_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        # Segunda fila - acciones
        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=1)
        
        self.reset_btn = ttk.Button(row2, text="🔄 RESET",
                                   command=self.reset_stats,
                                   style='Large.TButton')
        self.reset_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        self.save_btn = ttk.Button(row2, text="💾 GUARDAR",
                                  command=self.save_measurement,
                                  style='Large.TButton')
        self.save_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        self.exit_btn = ttk.Button(row2, text="🚪 SALIR",
                                  command=self.safe_exit,
                                  style='Danger.TButton')
        self.exit_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
    
    def create_mini_graph(self, parent):
        """Mini gráfico simple con Canvas"""
        graph_frame = ttk.Frame(parent, style='Card.TFrame')
        graph_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Título
        title_frame = ttk.Frame(graph_frame)
        title_frame.pack(fill=tk.X, padx=10, pady=(8, 0))
        
        ttk.Label(title_frame, text="📊 Tendencia",
                 font=('Arial', 12, 'bold'),
                 background='#34495e',
                 foreground='white').pack(side=tk.LEFT)
        
        # Indicador de actividad
        self.activity_indicator = ttk.Label(title_frame, text="●",
                                           font=('Arial', 12),
                                           background='#34495e',
                                           foreground='#2ecc71')
        self.activity_indicator.pack(side=tk.RIGHT)
        
        # Canvas para mini-gráfico
        self.graph_canvas = tk.Canvas(graph_frame,
                                     width=self.graph_width,
                                     height=self.graph_height,
                                     bg='#2c3e50',
                                     highlightthickness=0)
        self.graph_canvas.pack(pady=(5, 10))
        
        # Inicializar gráfico
        self.init_mini_graph()
    
    def create_statistics(self, parent):
        """Panel de estadísticas adicionales"""
        stats_frame = ttk.Frame(parent, style='Card.TFrame')
        stats_frame.pack(fill=tk.X, pady=(0, 5))
        
        content_frame = ttk.Frame(stats_frame)
        content_frame.pack(fill=tk.X, padx=10, pady=8)
        
        ttk.Label(content_frame, text="📈 Estadísticas",
                 font=('Arial', 12, 'bold'),
                 background='#34495e',
                 foreground='white').pack(side=tk.LEFT)
        
        # Stats en una línea
        self.stats_text = ttk.Label(content_frame,
                                   text="Lecturas: 0 | Estabilidad: -- | Última: --",
                                   font=('Arial', 9),
                                   background='#34495e',
                                   foreground='#bdc3c7')
        self.stats_text.pack(side=tk.RIGHT)
    
    def create_status_bar(self, parent):
        """Barra de estado compacta"""
        status_frame = ttk.Frame(parent, style='Card.TFrame')
        status_frame.pack(fill=tk.X)
        
        status_content = ttk.Frame(status_frame)
        status_content.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = ttk.Label(status_content,
                                     text="✅ Sistema listo",
                                     font=('Arial', 9),
                                     background='#34495e',
                                     foreground='#2ecc71')
        self.status_label.pack(side=tk.LEFT)
        
        # Contador de mediciones guardadas
        self.saved_count_label = ttk.Label(status_content,
                                          text="💾 0 guardadas",
                                          font=('Arial', 9),
                                          background='#34495e',
                                          foreground='#95a5a6')
        self.saved_count_label.pack(side=tk.RIGHT)
    
    def setup_data_logging(self):
        """Configurar guardado de datos"""
        self.data_file = "mediciones_bascula.json"
        
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.saved_data = json.load(f)
            except:
                self.saved_data = []
        else:
            self.saved_data = []
        
        # Actualizar contador
        self.saved_count_label.configure(text=f"💾 {len(self.saved_data)} guardadas")
    
    def start_reading_thread(self):
        """Iniciar hilo de lectura"""
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
        self.reading_thread.start()
        
        # Iniciar actualización GUI
        self.root.after(100, self.update_gui)
    
    def reading_loop(self):
        """Bucle de lectura del sensor con sintaxis correcta"""
        simulation_time = 0
        while self.is_reading:
            try:
                if self.hx and HX711_AVAILABLE:
                    # Sintaxis correcta para leer peso
                    raw_data = self.hx.get_raw_data(num_measures=3)
                    if raw_data:
                        # Convertir a peso (necesitarás calibrar)
                        weight = sum(raw_data) / len(raw_data)
                        # Aplicar factor de escala (ajustar después de calibrar)
                        weight = weight / 1000.0  # Factor temporal
                        weight = round(weight, 1)
                    else:
                        weight = 0.0
                else:
                    # Simulación más realista
                    base_weight = 100 + 50 * math.sin(simulation_time * 0.1)
                    noise = (hash(str(time.time())) % 100 - 50) * 0.1
                    weight = round(base_weight + noise, 1)
                    simulation_time += 1
                    time.sleep(0.2)
                
                self.weight_queue.put(weight)
                
            except Exception as e:
                print(f"Error en lectura: {e}")
                # En caso de error, enviar peso cero
                self.weight_queue.put(0.0)
                time.sleep(0.5)
    
    def update_gui(self):
        """Actualizar GUI"""
        try:
            # Procesar pesos del queue
            while not self.weight_queue.empty():
                weight = self.weight_queue.get_nowait()
                self.process_new_weight(weight)
            
            # Programar próxima actualización
            self.root.after(150, self.update_gui)
            
        except Exception as e:
            print(f"Error actualizando GUI: {e}")
            self.root.after(150, self.update_gui)
    
    def process_new_weight(self, weight):
        """Procesar nuevo peso"""
        # Actualizar display principal
        if self.unit.get() == "kg" and abs(weight) >= 1000:
            display_weight = weight / 1000
            display_text = f"{display_weight:.3f}"
        else:
            display_text = f"{weight:.1f}"
        
        self.weight_label.configure(text=display_text)
        
        # Actualizar estadísticas
        if weight > self.max_weight.get():
            self.max_weight.set(weight)
            self.max_display.configure(text=f"{weight:.1f}")
        
        if weight < self.min_weight.get() or self.min_weight.get() == 0:
            self.min_weight.set(weight)
            self.min_display.configure(text=f"{weight:.1f}")
        
        # Calcular promedio
        self.reading_count += 1
        self.average_weight = ((self.average_weight * (self.reading_count - 1)) + weight) / self.reading_count
        self.avg_display.configure(text=f"{self.average_weight:.1f}")
        
        # Agregar a histórico
        self.weight_history.append(weight)
        
        # Actualizar mini-gráfico
        self.update_mini_graph()
        
        # Color del peso según valor
        if abs(weight) < 5:
            color = '#95a5a6'  # Gris
        elif weight > 9500:  # Cerca de 10kg
            color = '#e74c3c'  # Rojo
        elif weight < 0:
            color = '#f39c12'  # Naranja
        else:
            color = '#2ecc71'  # Verde
        
        self.weight_label.configure(fg=color)
        
        # Indicador de actividad
        current_color = self.activity_indicator.cget('foreground')
        new_color = '#e74c3c' if current_color == '#2ecc71' else '#2ecc71'
        self.activity_indicator.configure(foreground=new_color)
        
        # Actualizar estadísticas
        stability = "ESTABLE" if len(self.weight_history) > 5 and max(list(self.weight_history)[-5:]) - min(list(self.weight_history)[-5:]) < 2 else "VARIABLE"
        last_reading_time = datetime.now().strftime("%H:%M:%S")
        
        stats_text = f"Lecturas: {self.reading_count} | {stability} | {last_reading_time}"
        self.stats_text.configure(text=stats_text)
    
    def init_mini_graph(self):
        """Inicializar mini-gráfico"""
        self.graph_canvas.create_line(0, self.graph_height//2, 
                                     self.graph_width, self.graph_height//2,
                                     fill='#7f8c8d', width=1)
        
        # Etiquetas
        self.graph_canvas.create_text(5, 10, text="📊", fill='#bdc3c7', anchor='nw')
    
    def update_mini_graph(self):
        """Actualizar mini-gráfico"""
        if len(self.weight_history) < 2:
            return
        
        # Limpiar canvas
        self.graph_canvas.delete("graph_line")
        
        # Obtener datos
        data = list(self.weight_history)
        if len(data) < 2:
            return
        
        # Normalizar datos
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val if max_val != min_val else 1
        
        # Crear puntos
        points = []
        for i, value in enumerate(data):
            x = (i / (len(data) - 1)) * (self.graph_width - 20) + 10
            y = self.graph_height - 10 - ((value - min_val) / range_val) * (self.graph_height - 20)
            points.extend([x, y])
        
        # Dibujar línea
        if len(points) >= 4:
            self.graph_canvas.create_line(points, fill='#2ecc71', width=2, tags="graph_line")
    
    def tare(self):
        """Establecer tara con sintaxis correcta"""
        if self.hx and HX711_AVAILABLE:
            try:
                # La librería hx711 no tiene tare(), así que calculamos offset
                raw_readings = []
                for _ in range(10):
                    data = self.hx.get_raw_data(num_measures=3)
                    if data:
                        raw_readings.extend(data)
                    time.sleep(0.1)
                
                if raw_readings:
                    self.hx._offset = sum(raw_readings) / len(raw_readings)
                    current = float(self.weight_label.cget('text'))
                    self.tare_weight.set(current)
                    self.tare_display.configure(text=f"{current:.1f}")
                    self.status_label.configure(text="✅ Tara establecida")
                else:
                    self.status_label.configure(text="❌ Error estableciendo tara")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
                self.status_label.configure(text=f"❌ Error tara: {str(e)[:20]}")
        else:
            current = float(self.weight_label.cget('text'))
            self.tare_weight.set(current)
            self.tare_display.configure(text=f"{current:.1f}")
            self.status_label.configure(text="✅ Tara establecida (sim)")
    
    def toggle_unit(self):
        """Cambiar unidades"""
        if self.unit.get() == "g":
            self.unit.set("kg")
        else:
            self.unit.set("g")
        self.status_label.configure(text=f"📏 Unidad: {self.unit.get()}")
    
    def reset_stats(self):
        """Reiniciar estadísticas"""
        self.max_weight.set(0.0)
        self.min_weight.set(0.0)
        self.tare_weight.set(0.0)
        self.reading_count = 0
        self.average_weight = 0.0
        
        # Resetear displays
        self.max_display.configure(text="0.0")
        self.min_display.configure(text="0.0")
        self.tare_display.configure(text="0.0")
        self.avg_display.configure(text="0.0")
        
        # Limpiar histórico
        self.weight_history.clear()
        self.graph_canvas.delete("graph_line")
        
        self.status_label.configure(text="🔄 Estadísticas reiniciadas")
    
    def show_calibration_dialog(self):
        """Diálogo de calibración simplificado"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibración")
        dialog.geometry("350x250")
        dialog.configure(bg='#2c3e50')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar diálogo
        dialog.geometry("+200+100")
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        ttk.Label(main_frame, text="⚖️ Calibración",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        ttk.Label(main_frame, 
                 text="1. Retira todo peso\n2. Presiona 'Cero'",
                 font=('Arial', 10)).pack(pady=(0, 10))
        
        ttk.Button(main_frame, text="Establecer Cero",
                  command=lambda: self.set_zero_cal(dialog),
                  style='Large.TButton').pack(pady=5, fill=tk.X)
        
        ttk.Label(main_frame, 
                 text="3. Coloca peso conocido\n4. Introduce peso y calibra",
                 font=('Arial', 10)).pack(pady=(10, 5))
        
        weight_frame = ttk.Frame(main_frame)
        weight_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(weight_frame, text="Peso (g):").pack(side=tk.LEFT)
        weight_entry = ttk.Entry(weight_frame, font=('Arial', 12), width=10)
        weight_entry.pack(side=tk.RIGHT)
        weight_entry.insert(0, "500")
        
        ttk.Button(main_frame, text="Calibrar",
                  command=lambda: self.calibrate_with_weight(dialog, weight_entry),
                  style='Large.TButton').pack(pady=15, fill=tk.X)
        
        ttk.Button(main_frame, text="Cancelar",
                  command=dialog.destroy,
                  style='Large.TButton').pack(fill=tk.X)
    
    def set_zero_cal(self, dialog):
        """Establecer cero en calibración"""
        if self.hx and HX711_AVAILABLE:
            try:
                # Reset y establecer offset
                self.hx.reset()
                time.sleep(1)
                
                # Tomar lecturas para offset
                raw_readings = []
                for _ in range(15):
                    data = self.hx.get_raw_data(num_measures=3)
                    if data:
                        raw_readings.extend(data)
                    time.sleep(0.1)
                
                if raw_readings:
                    self.hx._offset = sum(raw_readings) / len(raw_readings)
                    messagebox.showinfo("Éxito", "Cero establecido")
                else:
                    messagebox.showerror("Error", "No se pudieron leer datos")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error: {e}")
        else:
            messagebox.showinfo("Simulación", "Cero establecido")
    
    def calibrate_with_weight(self, dialog, weight_entry):
        """Calibrar con peso conocido"""
        try:
            known_weight = float(weight_entry.get())
            
            if self.hx and HX711_AVAILABLE:
                # Tomar lecturas con peso conocido
                raw_readings = []
                for _ in range(10):
                    data = self.hx.get_raw_data(num_measures=3)
                    if data:
                        raw_readings.extend(data)
                    time.sleep(0.2)
                
                if raw_readings:
                    avg_reading = sum(raw_readings) / len(raw_readings)
                    # Calcular factor de escala
                    self.hx._scale = (avg_reading - self.hx._offset) / known_weight
                    
                    messagebox.showinfo("Éxito", 
                                      f"Calibración completada\nFactor: {self.hx._scale:.2f}")
                else:
                    messagebox.showerror("Error", "No se pudieron leer datos")
                    return
            else:
                messagebox.showinfo("Simulación", "Calibración completada")
            
            self.is_calibrated = True
            dialog.destroy()
            self.status_label.configure(text="⚖️ Calibrado correctamente")
            
        except ValueError:
            messagebox.showerror("Error", "Peso inválido")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")
    
    def save_measurement(self):
        """Guardar medición"""
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "weight": float(self.weight_label.cget('text')),
            "unit": self.unit.get(),
            "tare": self.tare_weight.get(),
            "max": self.max_weight.get(),
            "min": self.min_weight.get(),
            "average": self.average_weight
        }
        
        self.saved_data.append(measurement)
        
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.saved_data, f, indent=2)
            
            count = len(self.saved_data)
            self.saved_count_label.configure(text=f"💾 {count} guardadas")
            self.status_label.configure(text=f"💾 Medición #{count} guardada")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando: {e}")
    
    def update_time(self):
        """Actualizar reloj"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.configure(text=current_time)
        self.root.after(1000, self.update_time)
    
    def safe_exit(self):
        """Salida segura"""
        result = messagebox.askyesno("Confirmar", "¿Salir de la aplicación?")
        if result:
            self.is_reading = False
            
            # Limpiar GPIO si está disponible
            if HX711_AVAILABLE:
                try:
                    GPIO.cleanup()
                    print("GPIO limpiado")
                except:
                    pass
                    
            # Pequeño delay para que termine el hilo
            self.root.after(500, self.root.quit)

def main():
    """Función principal"""
    # Configurar para mejor rendimiento en Pi Zero
    import sys
    if 'linux' in sys.platform:
        # Optimizaciones para Linux/Raspberry Pi
        os.environ['TK_SILENCE_DEPRECATION'] = '1'
    
    root = tk.Tk()
    
    # Configuraciones adicionales para pantalla táctil
    root.configure(cursor='none')  # Ocultar cursor del mouse
    
    app = LightweightLoadCellGUI(root)
    
    try:
        print("🚀 Iniciando Báscula Digital...")
        print("📱 Optimizada para Raspberry Pi Zero 2W")
        print("👆 Interfaz táctil lista")
        print("⌨️  Presiona 'Escape' para salir")
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\n⏹️  Aplicación cerrada por usuario")
        app.is_reading = False
    except Exception as e:
        print(f"❌ Error fatal: {e}")
    finally:
        print("🧹 Limpiando recursos...")

if __name__ == "__main__":
    main()
