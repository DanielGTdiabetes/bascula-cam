#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Profesional - Versión Compatible con Raspberry Pi
Interfaz moderna y funcional, optimizada para hardware limitado
"""

import os
import stat
import json
import time
import math
import queue
import threading
import statistics
from datetime import datetime
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox

# Configuración compatible con Raspberry Pi
BASE_DIR = os.path.expanduser("~/bascula-cam")
CAPTURE_DIR = os.path.join(BASE_DIR, "capturas")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

for d in (CAPTURE_DIR, DATA_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

# Tema de colores profesional
THEME = {
    'primary': '#2563eb',      # Azul profesional
    'primary_light': '#3b82f6',
    'success': '#10b981',      # Verde éxito
    'danger': '#ef4444',       # Rojo peligro
    'warning': '#f59e0b',      # Naranja advertencia
    'dark': '#1f2937',         # Gris oscuro
    'medium': '#6b7280',       # Gris medio
    'light': '#9ca3af',        # Gris claro
    'background': '#f8fafc',   # Fondo
    'surface': '#ffffff',      # Superficie
    'text': '#111827',         # Texto
    'text_light': '#6b7280'    # Texto claro
}

# Configuración por defecto
DEFAULT_SETTINGS = {
    "api_key": "",
    "wifi_ssid": "",
    "wifi_password": "",
    "calibration": {
        "scale_factor": 1.0,
        "tare_offset": 0.0,
        "base_offset": -8575
    },
    "ui": {
        "auto_photo": True,
        "units": "g"
    }
}

def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        return {**DEFAULT_SETTINGS, **data}
    except FileNotFoundError:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(SETTINGS_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        print(f"Error guardando configuración: {e}")

class ProButton(tk.Button):
    """Botón profesional con colores y efectos"""
    def __init__(self, parent, text="", command=None, btn_type="primary", 
                 icon="", width=None, height=2, **kwargs):
        
        # Configuración de estilos
        styles = {
            'primary': {'bg': THEME['primary'], 'fg': 'white'},
            'success': {'bg': THEME['success'], 'fg': 'white'},
            'danger': {'bg': THEME['danger'], 'fg': 'white'},
            'warning': {'bg': THEME['warning'], 'fg': 'white'},
            'secondary': {'bg': THEME['medium'], 'fg': 'white'},
            'light': {'bg': THEME['light'], 'fg': 'white'}
        }
        
        style = styles.get(btn_type, styles['primary'])
        display_text = f"{icon} {text}" if icon else text
        
        super().__init__(
            parent,
            text=display_text,
            command=command,
            bg=style['bg'],
            fg=style['fg'],
            font=('Arial', 12, 'bold'),
            relief='flat',
            bd=0,
            height=height,
            width=width,
            cursor='hand2',
            **kwargs
        )

class SimpleKeyboard(tk.Toplevel):
    """Teclado simplificado y funcional"""
    
    def __init__(self, parent, title="Entrada de texto", initial="", 
                 numeric_only=False, password=False):
        super().__init__(parent)
        
        self.title(title)
        self.configure(bg=THEME['background'])
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.numeric_only = numeric_only
        self.password = password
        
        # Configurar tamaño según tipo
        if numeric_only:
            self.geometry("400x500")
        else:
            self.geometry("800x600")
            
        self.create_ui(initial)
        self.center_window()
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_reqwidth() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_reqheight() // 2)
        self.geometry(f"+{x}+{y}")
        
    def create_ui(self, initial_text):
        # Título
        title_frame = tk.Frame(self, bg=THEME['surface'], relief='solid', bd=1)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(title_frame, text=self.title, font=('Arial', 16, 'bold'),
                bg=THEME['surface'], fg=THEME['text']).pack(pady=10)
        
        # Campo de entrada
        self.text_var = tk.StringVar(value=initial_text)
        self.entry = tk.Entry(
            self,
            textvariable=self.text_var,
            font=('Arial', 16),
            justify='center',
            show='*' if self.password else '',
            bg='white',
            relief='solid',
            bd=2
        )
        self.entry.pack(fill=tk.X, padx=20, pady=10, ipady=8)
        
        # Teclado
        if self.numeric_only:
            self.create_numeric_pad()
        else:
            self.create_qwerty_pad()
            
        # Botones de control
        self.create_controls()
        
        self.entry.focus_set()
        
    def create_numeric_pad(self):
        """Teclado numérico simple"""
        keypad_frame = tk.Frame(self, bg=THEME['background'])
        keypad_frame.pack(padx=20, pady=10)
        
        # Números en grid 3x3
        numbers = [
            ['7', '8', '9'],
            ['4', '5', '6'],
            ['1', '2', '3'],
            ['0', '.', 'C']
        ]
        
        for row_idx, row in enumerate(numbers):
            for col_idx, num in enumerate(row):
                if num == 'C':
                    btn = ProButton(keypad_frame, text='Borrar', 
                                  command=self.clear, btn_type='danger',
                                  width=8, height=2)
                else:
                    btn = ProButton(keypad_frame, text=num, 
                                  command=lambda n=num: self.add_char(n),
                                  width=8, height=2)
                btn.grid(row=row_idx, column=col_idx, padx=2, pady=2, sticky='nsew')
        
        # Configurar expansión
        for i in range(4):
            keypad_frame.grid_rowconfigure(i, weight=1)
        for i in range(3):
            keypad_frame.grid_columnconfigure(i, weight=1)
    
    def create_qwerty_pad(self):
        """Teclado QWERTY simplificado"""
        keyboard_frame = tk.Frame(self, bg=THEME['background'])
        keyboard_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Layout básico
        rows = [
            '1234567890',
            'qwertyuiop',
            'asdfghjkl',
            'zxcvbnm'
        ]
        
        for row in rows:
            row_frame = tk.Frame(keyboard_frame, bg=THEME['background'])
            row_frame.pack(pady=2)
            
            for char in row:
                btn = tk.Button(
                    row_frame,
                    text=char.upper(),
                    command=lambda c=char: self.add_char(c),
                    width=4,
                    height=2,
                    font=('Arial', 10, 'bold'),
                    bg=THEME['surface'],
                    relief='solid',
                    bd=1
                )
                btn.pack(side=tk.LEFT, padx=1, pady=1)
        
        # Fila especial
        special_frame = tk.Frame(keyboard_frame, bg=THEME['background'])
        special_frame.pack(pady=5)
        
        ProButton(special_frame, text='ESPACIO', 
                 command=lambda: self.add_char(' '),
                 width=20, height=2).pack(side=tk.LEFT, padx=5)
        
        ProButton(special_frame, text='BORRAR', 
                 command=self.backspace, btn_type='danger',
                 width=10, height=2).pack(side=tk.LEFT, padx=5)
    
    def create_controls(self):
        """Botones de control"""
        control_frame = tk.Frame(self, bg=THEME['background'])
        control_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ProButton(control_frame, text='LIMPIAR', command=self.clear,
                 btn_type='warning', width=12).pack(side=tk.LEFT, padx=5)
        
        ProButton(control_frame, text='CANCELAR', command=self.cancel,
                 btn_type='secondary', width=12).pack(side=tk.LEFT, padx=5)
        
        ProButton(control_frame, text='ACEPTAR', command=self.accept,
                 btn_type='success', width=12).pack(side=tk.RIGHT, padx=5)
    
    def add_char(self, char):
        """Agregar carácter"""
        current = self.text_var.get()
        self.text_var.set(current + char)
        
    def backspace(self):
        """Borrar último carácter"""
        current = self.text_var.get()
        if current:
            self.text_var.set(current[:-1])
            
    def clear(self):
        """Limpiar todo"""
        self.text_var.set("")
        
    def accept(self):
        """Aceptar entrada"""
        self.result = self.text_var.get()
        self.destroy()
        
    def cancel(self):
        """Cancelar entrada"""
        self.result = None
        self.destroy()

class WeightDisplayPro(tk.Frame):
    """Display profesional del peso"""
    
    def __init__(self, parent):
        super().__init__(parent, bg=THEME['surface'], relief='solid', bd=2)
        
        # Frame principal
        main = tk.Frame(self, bg=THEME['surface'])
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # Peso
        self.weight_label = tk.Label(
            main,
            text="0.000",
            font=('Arial', 64, 'bold'),
            bg=THEME['surface'],
            fg=THEME['text']
        )
        self.weight_label.pack()
        
        # Unidad y estado
        bottom = tk.Frame(main, bg=THEME['surface'])
        bottom.pack(fill=tk.X, pady=(10, 0))
        
        self.unit_label = tk.Label(
            bottom,
            text="GRAMOS",
            font=('Arial', 16, 'bold'),
            bg=THEME['surface'],
            fg=THEME['primary']
        )
        self.unit_label.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(
            bottom,
            text="● Midiendo",
            font=('Arial', 14),
            bg=THEME['surface'],
            fg=THEME['warning']
        )
        self.status_label.pack(side=tk.RIGHT)
    
    def update_display(self, weight, stable=False):
        """Actualizar display"""
        # Formatear peso
        if abs(weight) >= 1000:
            text = f"{weight:.1f}"
        else:
            text = f"{weight:.2f}"
            
        self.weight_label.configure(text=text)
        
        # Color según peso
        if abs(weight) < 0.1:
            color = THEME['medium']
        elif weight < 0:
            color = THEME['danger']
        elif weight > 5000:
            color = THEME['warning']
        else:
            color = THEME['text']
            
        self.weight_label.configure(fg=color)
        
        # Estado
        if stable:
            self.status_label.configure(text="🔒 ESTABLE", fg=THEME['success'])
        else:
            self.status_label.configure(text="📊 Midiendo", fg=THEME['warning'])

class BasculaProApp:
    """Aplicación principal profesional"""
    
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.setup_window()
        self.setup_variables()
        self.setup_hardware()
        self.create_ui()
        self.start_reading_loop()
        
    def setup_window(self):
        """Configurar ventana principal"""
        self.root.title("⚖️ Báscula Digital Profesional - Sistema de Producción")
        self.root.configure(bg=THEME['background'])
        
        # Detectar tamaño de pantalla y ajustar
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        
        if width <= 800:  # Pantalla pequeña (Raspberry Pi touch)
            self.root.geometry(f"{width}x{height}+0+0")
        else:
            self.root.geometry("1024x768")
            
        # Bindings
        self.root.bind("<Escape>", lambda e: self.safe_exit())
        self.root.protocol("WM_DELETE_WINDOW", self.safe_exit)
        
    def setup_variables(self):
        """Inicializar variables"""
        self.current_weight = 0.0
        self.filtered_weight = 0.0
        self.display_weight = 0.0
        self.is_stable = False
        self.tare_offset = 0.0
        self.scale_factor = self.settings['calibration']['scale_factor']
        self.base_offset = self.settings['calibration']['base_offset']
        
        # Para lectura
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.readings_history = deque(maxlen=100)
        self.filter_history = deque(maxlen=20)
        
        # Estadísticas
        self.session_readings = 0
        self.session_average = 0.0
        self.session_max = 0.0
        self.session_min = 0.0
        
    def setup_hardware(self):
        """Inicializar hardware"""
        # HX711
        self.hx711_available = False
        try:
            import RPi.GPIO as GPIO
            from hx711 import HX711
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.hx = HX711(dout_pin=5, pd_sck_pin=6, channel="A", gain=64)
            self.hx.reset()
            time.sleep(1)
            self.hx711_available = True
            print("✅ HX711 inicializado")
        except Exception as e:
            print(f"⚠️ HX711 no disponible: {e}")
            self.hx = None
            
        # Cámara
        self.camera_available = False
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(main={"size": (1640, 1232)})
            self.camera.configure(config)
            self.camera.start()
            time.sleep(2)
            self.camera_available = True
            print("✅ Cámara inicializada")
        except Exception as e:
            print(f"⚠️ Cámara no disponible: {e}")
            self.camera = None
            
    def create_ui(self):
        """Crear interfaz de usuario"""
        # Header
        self.create_header()
        
        # Contenido principal
        main_frame = tk.Frame(self.root, bg=THEME['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Panel izquierdo - Display de peso
        left_panel = tk.Frame(main_frame, bg=THEME['background'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.weight_display = WeightDisplayPro(left_panel)
        self.weight_display.pack(fill=tk.BOTH, expand=True)
        
        # Panel derecho - Controles
        right_panel = tk.Frame(main_frame, bg=THEME['background'], width=320)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)
        
        self.create_control_panel(right_panel)
        self.create_stats_panel(right_panel)
        
        # Footer
        self.create_footer()
        
    def create_header(self):
        """Crear header de la aplicación"""
        header = tk.Frame(self.root, bg=THEME['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        header_content = tk.Frame(header, bg=THEME['surface'])
        header_content.pack(fill=tk.X, padx=20, pady=15)
        
        # Título
        tk.Label(
            header_content,
            text="⚖️ BÁSCULA DIGITAL PROFESIONAL",
            font=('Arial', 20, 'bold'),
            bg=THEME['surface'],
            fg=THEME['primary']
        ).pack(side=tk.LEFT)
        
        # Estados del sistema
        status_frame = tk.Frame(header_content, bg=THEME['surface'])
        status_frame.pack(side=tk.RIGHT)
        
        # Estado HX711
        hx_color = THEME['success'] if self.hx711_available else THEME['danger']
        hx_text = "HX711 Conectado" if self.hx711_available else "HX711 Desconectado"
        self.hx_status = tk.Label(
            status_frame, text=f"● {hx_text}",
            font=('Arial', 10), bg=THEME['surface'], fg=hx_color
        )
        self.hx_status.pack(anchor='e', pady=2)
        
        # Estado Cámara
        cam_color = THEME['success'] if self.camera_available else THEME['danger']
        cam_text = "Cámara Lista" if self.camera_available else "Cámara No disponible"
        self.cam_status = tk.Label(
            status_frame, text=f"📷 {cam_text}",
            font=('Arial', 10), bg=THEME['surface'], fg=cam_color
        )
        self.cam_status.pack(anchor='e', pady=2)
        
    def create_control_panel(self, parent):
        """Panel de controles principales"""
        control_frame = tk.LabelFrame(
            parent,
            text="  🎛️ CONTROLES PRINCIPALES  ",
            font=('Arial', 12, 'bold'),
            bg=THEME['surface'],
            fg=THEME['text'],
            relief='solid',
            bd=1,
            padx=15,
            pady=15
        )
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid de botones principales
        btn_frame = tk.Frame(control_frame, bg=THEME['surface'])
        btn_frame.pack(fill=tk.X, pady=10)
        
        # Fila 1
        ProButton(btn_frame, text="TARA", icon="🔄", 
                 command=self.tare_weight, btn_type="primary",
                 width=12, height=3).grid(row=0, column=0, padx=3, pady=3, sticky='ew')
        
        ProButton(btn_frame, text="CALIBRAR", icon="⚙️",
                 command=self.calibrate_scale, btn_type="warning", 
                 width=12, height=3).grid(row=0, column=1, padx=3, pady=3, sticky='ew')
        
        # Fila 2
        ProButton(btn_frame, text="GUARDAR", icon="💾",
                 command=self.save_measurement, btn_type="success",
                 width=12, height=3).grid(row=1, column=0, padx=3, pady=3, sticky='ew')
        
        ProButton(btn_frame, text="FOTO", icon="📷",
                 command=self.take_photo, btn_type="secondary",
                 width=12, height=3).grid(row=1, column=1, padx=3, pady=3, sticky='ew')
        
        # Configurar expansión
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        # Botones secundarios
        secondary_frame = tk.Frame(control_frame, bg=THEME['surface'])
        secondary_frame.pack(fill=tk.X, pady=(10, 0))
        
        ProButton(secondary_frame, text="AJUSTES", icon="⚙️",
                 command=self.open_settings, btn_type="light",
                 width=8).pack(side=tk.LEFT, padx=2)
        
        ProButton(secondary_frame, text="RESET", icon="🔄",
                 command=self.reset_session, btn_type="light", 
                 width=8).pack(side=tk.LEFT, padx=2)
        
        ProButton(secondary_frame, text="SALIR", icon="🚪",
                 command=self.safe_exit, btn_type="danger",
                 width=8).pack(side=tk.RIGHT, padx=2)
                 
    def create_stats_panel(self, parent):
        """Panel de estadísticas"""
        stats_frame = tk.LabelFrame(
            parent,
            text="  📊 ESTADÍSTICAS DE SESIÓN  ",
            font=('Arial', 12, 'bold'),
            bg=THEME['surface'],
            fg=THEME['text'],
            relief='solid',
            bd=1,
            padx=15,
            pady=15
        )
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        # Grid de estadísticas
        stats_grid = tk.Frame(stats_frame, bg=THEME['surface'])
        stats_grid.pack(fill=tk.X, pady=10)
        
        # Labels de estadísticas
        self.stats_labels = {}
        stats_info = [
            ('readings', 'Mediciones:', '0'),
            ('average', 'Promedio:', '0.0g'),
            ('maximum', 'Máximo:', '0.0g'),
            ('minimum', 'Mínimo:', '0.0g'),
            ('precision', 'Precisión:', '±0.1g'),
            ('uptime', 'Tiempo activo:', '00:00:00')
        ]
        
        for i, (key, label, value) in enumerate(stats_info):
            row = i // 2
            col = (i % 2) * 2
            
            tk.Label(
                stats_grid, text=label, font=('Arial', 10),
                bg=THEME['surface'], fg=THEME['text_light'], anchor='w'
            ).grid(row=row, column=col, sticky='w', padx=(0, 5), pady=3)
            
            self.stats_labels[key] = tk.Label(
                stats_grid, text=value, font=('Arial', 10, 'bold'),
                bg=THEME['surface'], fg=THEME['text'], anchor='e'
            )
            self.stats_labels[key].grid(row=row, column=col+1, sticky='e', pady=3)
        
        # Configurar grid
        for i in range(4):
            stats_grid.grid_columnconfigure(i, weight=1)
            
        # Información adicional
        info_frame = tk.Frame(stats_frame, bg=THEME['surface'])
        info_frame.pack(fill=tk.X, pady=(15, 5))
        
        self.status_info = tk.Label(
            info_frame,
            text="Sistema iniciado - Esperando mediciones",
            font=('Arial', 9),
            bg=THEME['surface'],
            fg=THEME['text_light'],
            wraplength=280
        )
        self.status_info.pack()
        
    def create_footer(self):
        """Footer de la aplicación"""
        footer = tk.Frame(self.root, bg=THEME['surface'], relief='solid', bd=1)
        footer.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        footer_content = tk.Frame(footer, bg=THEME['surface'])
        footer_content.pack(fill=tk.X, padx=20, pady=8)
        
        # Info del sistema
        system_info = "Raspberry Pi Zero 2W • HX711 • Camera Module 3"
        tk.Label(
            footer_content, text=system_info, font=('Arial', 8),
            bg=THEME['surface'], fg=THEME['text_light']
        ).pack(side=tk.LEFT)
        
        # Timestamp
        self.timestamp_label = tk.Label(
            footer_content, text="", font=('Arial', 8),
            bg=THEME['surface'], fg=THEME['text_light']
        )
        self.timestamp_label.pack(side=tk.RIGHT)
        
        self.update_timestamp()
        
    def update_timestamp(self):
        """Actualizar timestamp"""
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.timestamp_label.configure(text=current_time)
        self.root.after(1000, self.update_timestamp)
        
    # ============ MÉTODOS DE HARDWARE ============
    
    def start_reading_loop(self):
        """Iniciar loop de lectura"""
        self.is_reading = True
        self.start_time = time.time()
        
        # Thread de lectura
        self.reading_thread = threading.Thread(target=self.reading_worker, daemon=True)
        self.reading_thread.start()
        
        # Timer de actualización UI
        self.update_ui()
        
    def reading_worker(self):
        """Worker thread para lecturas del HX711"""
        while self.is_reading:
            try:
                if self.hx711_available and self.hx:
                    # Lectura real del HX711
                    raw_data = self.hx.get_raw_data(times=3)
                    if raw_data:
                        valid_readings = [x for x in raw_data if x is not None]
                        if valid_readings:
                            raw_avg = sum(valid_readings) / len(valid_readings)
                            weight = self.raw_to_weight(raw_avg)
                            self.weight_queue.put(weight)
                else:
                    # Simulación para desarrollo
                    import random
                    base = 500 + 200 * math.sin(time.time() * 0.5)
                    noise = random.uniform(-5, 5)
                    sim_weight = max(0, base + noise)
                    self.weight_queue.put(sim_weight)
                    
                time.sleep(0.2)  # 5 Hz
                
            except Exception as e:
                print(f"Error en lectura: {e}")
                time.sleep(0.5)
                
    def raw_to_weight(self, raw_value):
        """Convertir valor raw a peso en gramos"""
        return (raw_value - self.base_offset - self.tare_offset) / self.scale_factor
        
    def update_ui(self):
        """Actualizar UI con nuevas lecturas"""
        try:
            # Procesar nuevas lecturas
            updated = False
            while not self.weight_queue.empty():
                try:
                    weight = self.weight_queue.get_nowait()
                    self.process_weight_reading(weight)
                    updated = True
                except queue.Empty:
                    break
                    
            if updated:
                # Actualizar display
                self.weight_display.update_display(self.display_weight, self.is_stable)
                
                # Actualizar estadísticas
                self.update_stats()
                
        except Exception as e:
            print(f"Error actualizando UI: {e}")
            
        # Continuar loop
        self.root.after(100, self.update_ui)
        
    def process_weight_reading(self, weight):
        """Procesar una nueva lectura de peso"""
        self.current_weight = weight
        
        # Filtro simple de media móvil
        self.filter_history.append(weight)
        if len(self.filter_history) >= 5:
            self.filtered_weight = sum(list(self.filter_history)[-5:]) / 5
        else:
            self.filtered_weight = weight
            
        # Detección de estabilidad
        if len(self.filter_history) >= 10:
            recent = list(self.filter_history)[-10:]
            std_dev = statistics.pstdev(recent) if len(recent) > 1 else 0
            self.is_stable = std_dev < 0.5  # Estable si desviación < 0.5g
        else:
            self.is_stable = False
            
        # Display con banda muerta
        if abs(self.filtered_weight) < 0.1:
            self.display_weight = 0.0
        else:
            self.display_weight = round(self.filtered_weight, 2)
            
        # Histórico para estadísticas
        self.readings_history.append(self.display_weight)
        
    def update_stats(self):
        """Actualizar estadísticas de sesión"""
        if not self.readings_history:
            return
            
        readings = list(self.readings_history)
        self.session_readings = len(readings)
        self.session_average = sum(readings) / len(readings)
        self.session_max = max(readings)
        self.session_min = min(readings)
        
        # Actualizar labels
        self.stats_labels['readings'].configure(text=str(self.session_readings))
        self.stats_labels['average'].configure(text=f"{self.session_average:.1f}g")
        self.stats_labels['maximum'].configure(text=f"{self.session_max:.1f}g")
        self.stats_labels['minimum'].configure(text=f"{self.session_min:.1f}g")
        
        # Uptime
        uptime_seconds = int(time.time() - self.start_time)
        uptime_str = f"{uptime_seconds//3600:02d}:{(uptime_seconds%3600)//60:02d}:{uptime_seconds%60:02d}"
        self.stats_labels['uptime'].configure(text=uptime_str)
        
    # ============ MÉTODOS DE CONTROL ============
    
    def show_keyboard(self, title, initial="", numeric_only=False, password=False):
        """Mostrar teclado y retornar resultado"""
        keyboard = SimpleKeyboard(self.root, title, initial, numeric_only, password)
        self.root.wait_window(keyboard)
        return keyboard.result
        
    def show_message(self, title, message, msg_type="info"):
        """Mostrar mensaje temporal"""
        colors = {
            'info': THEME['primary'],
            'success': THEME['success'],
            'warning': THEME['warning'],
            'error': THEME['danger']
        }
        
        # Actualizar status info temporalmente
        original_text = self.status_info.cget('text')
        self.status_info.configure(text=message, fg=colors.get(msg_type, THEME['primary']))
        
        # Restaurar después de 3 segundos
        self.root.after(3000, lambda: self.status_info.configure(
            text=original_text, fg=THEME['text_light']))
            
    def tare_weight(self):
        """Aplicar tara"""
        if len(self.filter_history) >= 5:
            recent_avg = sum(list(self.filter_history)[-5:]) / 5
            self.tare_offset += recent_avg * self.scale_factor
            self.show_message("Tara", "Tara aplicada correctamente", "success")
        else:
            self.show_message("Error", "Esperando lecturas estables...", "warning")
            
    def calibrate_scale(self):
        """Calibrar báscula"""
        known_weight = self.show_keyboard("Peso de Calibración (gramos)", "1000", numeric_only=True)
        
        if known_weight:
            try:
                weight_value = float(known_weight)
                if weight_value <= 0:
                    raise ValueError("El peso debe ser positivo")
                    
                if len(self.filter_history) >= 5:
                    current_avg = sum(list(self.filter_history)[-5:]) / 5
                    if abs(current_avg) > 1:  # Debe haber peso en la báscula
                        self.scale_factor = self.scale_factor * abs(current_avg / weight_value)
                        
                        # Guardar calibración
                        self.settings['calibration']['scale_factor'] = self.scale_factor
                        save_settings(self.settings)
                        
                        self.show_message("Calibración", f"Calibrado con {weight_value}g", "success")
                    else:
                        self.show_message("Error", "Coloque peso en la báscula", "warning")
                else:
                    self.show_message("Error", "Esperando lecturas estables...", "warning")
                    
            except ValueError:
                self.show_message("Error", "Peso inválido", "error")
                
    def save_measurement(self):
        """Guardar medición actual"""
        if not self.is_stable:
            if not messagebox.askyesno("Medición inestable", 
                                     "La medición no está estable. ¿Guardar de todas formas?"):
                return
                
        # Datos de medición
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "weight": self.display_weight,
            "unit": "g",
            "stable": self.is_stable,
            "raw_reading": self.current_weight
        }
        
        # Foto automática si está habilitada
        photo_path = ""
        if self.settings['ui']['auto_photo'] and self.camera_available:
            photo_path = self.capture_photo()
            if photo_path:
                measurement['photo'] = photo_path
                
        # Guardar a archivo
        try:
            measurements_file = os.path.join(BASE_DIR, "measurements.json")
            try:
                with open(measurements_file, "r") as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                measurements = []
                
            measurements.append(measurement)
            
            with open(measurements_file, "w") as f:
                json.dump(measurements, f, indent=2)
                
            count = len(measurements)
            if photo_path:
                self.show_message("Guardado", f"Medición #{count} guardada con foto", "success")
            else:
                self.show_message("Guardado", f"Medición #{count} guardada", "success")
                
        except Exception as e:
            self.show_message("Error", f"Error guardando: {e}", "error")
            
    def take_photo(self):
        """Capturar foto manual"""
        if not self.camera_available:
            self.show_message("Error", "Cámara no disponible", "error")
            return
            
        photo_path = self.capture_photo()
        if photo_path:
            self.show_message("Foto", "Foto capturada correctamente", "success")
        else:
            self.show_message("Error", "Error capturando foto", "error")
            
    def capture_photo(self):
        """Capturar foto con timestamp"""
        if not self.camera_available or not self.camera:
            return ""
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{self.display_weight:.1f}g.jpg"
            photo_path = os.path.join(CAPTURE_DIR, filename)
            
            self.camera.capture_file(photo_path)
            
            if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
                return photo_path
            else:
                return ""
                
        except Exception as e:
            print(f"Error capturando foto: {e}")
            return ""
            
    def reset_session(self):
        """Reset de estadísticas de sesión"""
        if messagebox.askyesno("Reset de Sesión", 
                             "¿Reiniciar estadísticas de la sesión actual?"):
            self.readings_history.clear()
            self.filter_history.clear()
            self.session_readings = 0
            self.session_average = 0.0
            self.session_max = 0.0
            self.session_min = 0.0
            self.start_time = time.time()
            
            # Resetear labels
            for key in ['readings', 'average', 'maximum', 'minimum', 'uptime']:
                if key == 'readings':
                    self.stats_labels[key].configure(text="0")
                elif key == 'uptime':
                    self.stats_labels[key].configure(text="00:00:00")
                else:
                    self.stats_labels[key].configure(text="0.0g")
                    
            self.show_message("Reset", "Sesión reiniciada", "success")
            
    def open_settings(self):
        """Abrir configuración"""
        SettingsWindow(self.root, self)
        
    def safe_exit(self):
        """Salida segura"""
        if messagebox.askyesno("Salir", "¿Está seguro que desea salir del sistema?"):
            self.is_reading = False
            
            # Cleanup hardware
            try:
                if self.camera_available and self.camera:
                    self.camera.stop()
                    self.camera.close()
            except:
                pass
                
            try:
                if self.hx711_available:
                    import RPi.GPIO as GPIO
                    GPIO.cleanup()
            except:
                pass
                
            self.root.quit()

class SettingsWindow(tk.Toplevel):
    """Ventana de configuración"""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.title("⚙️ Configuración del Sistema")
        self.geometry("600x500")
        self.configure(bg=THEME['background'])
        self.transient(parent)
        self.grab_set()
        
        self.create_settings_ui()
        self.center_window()
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (300)
        y = (self.winfo_screenheight() // 2) - (250)
        self.geometry(f"+{x}+{y}")
        
    def create_settings_ui(self):
        # Header
        header = tk.Frame(self, bg=THEME['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(
            header, text="⚙️ CONFIGURACIÓN DEL SISTEMA",
            font=('Arial', 18, 'bold'), bg=THEME['surface'], fg=THEME['primary']
        ).pack(pady=15)
        
        # Notebook
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Pestaña General
        general_frame = tk.Frame(notebook, bg=THEME['background'])
        notebook.add(general_frame, text="  General  ")
        self.create_general_tab(general_frame)
        
        # Pestaña Wi-Fi
        wifi_frame = tk.Frame(notebook, bg=THEME['background'])
        notebook.add(wifi_frame, text="  Wi-Fi  ")
        self.create_wifi_tab(wifi_frame)
        
        # Pestaña Sistema
        system_frame = tk.Frame(notebook, bg=THEME['background'])
        notebook.add(system_frame, text="  Sistema  ")
        self.create_system_tab(system_frame)
        
        # Botones
        button_frame = tk.Frame(self, bg=THEME['background'])
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ProButton(button_frame, text="GUARDAR", icon="💾",
                 command=self.save_settings, btn_type="success",
                 width=15).pack(side=tk.LEFT, padx=10)
        
        ProButton(button_frame, text="CERRAR", icon="✖",
                 command=self.destroy, btn_type="secondary",
                 width=15).pack(side=tk.RIGHT, padx=10)
                 
    def create_general_tab(self, parent):
        # Auto foto
        auto_frame = tk.LabelFrame(
            parent, text="  📷 Configuración de Cámara  ",
            font=('Arial', 12, 'bold'), bg=THEME['surface'],
            fg=THEME['text'], padx=20, pady=15
        )
        auto_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.auto_photo_var = tk.BooleanVar(value=self.app.settings['ui']['auto_photo'])
        tk.Checkbutton(
            auto_frame, text="Capturar foto automáticamente al guardar medición",
            variable=self.auto_photo_var, font=('Arial', 11),
            bg=THEME['surface'], fg=THEME['text']
        ).pack(anchor='w')
        
        # Calibración
        cal_frame = tk.LabelFrame(
            parent, text="  ⚖️ Información de Calibración  ",
            font=('Arial', 12, 'bold'), bg=THEME['surface'],
            fg=THEME['text'], padx=20, pady=15
        )
        cal_frame.pack(fill=tk.X, padx=20, pady=20)
        
        cal_info = [
            ("Factor de escala:", f"{self.app.scale_factor:.3f}"),
            ("Offset de tara:", f"{self.app.tare_offset:.1f}"),
            ("Offset base:", f"{self.