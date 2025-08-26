#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Profesional - Filtrado Industrial
Sistema de filtrado avanzado tipo báscula comercial
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

# Configuración del sistema
BASE_DIR = os.path.expanduser("~/bascula-cam")
CAPTURE_DIR = os.path.join(BASE_DIR, "capturas")
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

for d in (CAPTURE_DIR, DATA_DIR):
    os.makedirs(d, exist_ok=True)

# Tema profesional
THEME = {
    'primary': '#2563eb', 'success': '#10b981', 'danger': '#ef4444',
    'warning': '#f59e0b', 'dark': '#1f2937', 'medium': '#6b7280',
    'light': '#9ca3af', 'background': '#f8fafc', 'surface': '#ffffff',
    'text': '#111827', 'text_light': '#6b7280'
}

class ProfessionalWeightFilter:
    """Filtro de peso profesional tipo báscula comercial"""
    
    def __init__(self):
        # Parámetros de filtrado profesional
        self.iir_alpha = 0.12           # Filtro IIR más suave
        self.median_window = 7          # Ventana mediana más grande
        self.stability_window = 12      # Ventana de estabilidad
        self.zero_band = 0.2           # Banda de cero más estricta
        self.display_resolution = 0.1  # Resolución de display
        self.auto_zero_rate = 0.3      # Velocidad de auto-zero
        self.stability_threshold = 0.15 # Umbral de estabilidad
        
        # Buffers de filtrado
        self.raw_buffer = deque(maxlen=self.median_window)
        self.filtered_buffer = deque(maxlen=self.stability_window)
        self.display_buffer = deque(maxlen=5)
        
        # Estados del filtro
        self.filtered_value = 0.0
        self.display_value = 0.0
        self.last_display_value = 0.0
        self.is_stable = False
        self.zero_tracking_active = True
        self.tare_offset = 0.0
        
        # Contadores para comportamiento profesional
        self.stable_count = 0
        self.zero_count = 0
        self.update_count = 0
        
    def process_reading(self, raw_weight):
        """Procesar nueva lectura con filtrado profesional"""
        self.update_count += 1
        
        # 1. Buffer de mediana para eliminar picos
        self.raw_buffer.append(raw_weight)
        
        if len(self.raw_buffer) >= 3:
            # Mediana móvil
            recent_values = list(self.raw_buffer)[-min(5, len(self.raw_buffer)):]
            median_value = statistics.median(recent_values)
        else:
            median_value = raw_weight
        
        # 2. Filtro IIR (Infinite Impulse Response) - más suave que EMA
        if not self.filtered_buffer:
            self.filtered_value = median_value
        else:
            # IIR con coeficiente variable según estabilidad
            alpha = self.iir_alpha
            if self.is_stable:
                alpha *= 0.5  # Más suave cuando está estable
                
            self.filtered_value = (1 - alpha) * self.filtered_value + alpha * median_value
        
        self.filtered_buffer.append(self.filtered_value)
        
        # 3. Detección de estabilidad profesional
        self._update_stability()
        
        # 4. Auto-zero tracking (como básculas comerciales)
        self._auto_zero_tracking()
        
        # 5. Cuantización para display estable
        self._update_display_value()
        
        return {
            'raw': raw_weight,
            'filtered': self.filtered_value,
            'display': self.display_value,
            'stable': self.is_stable,
            'zero_tracking': self.zero_tracking_active
        }
    
    def _update_stability(self):
        """Detectar estabilidad como básculas profesionales"""
        if len(self.filtered_buffer) < self.stability_window:
            self.is_stable = False
            self.stable_count = 0
            return
        
        # Calcular desviación estándar de la ventana
        window = list(self.filtered_buffer)[-self.stability_window:]
        try:
            std_dev = statistics.pstdev(window) if len(window) > 1 else 0.0
        except statistics.StatisticsError:
            std_dev = float('inf')
        
        # Estable si la desviación es pequeña
        if std_dev <= self.stability_threshold:
            self.stable_count += 1
            # Requiere estabilidad sostenida (como básculas reales)
            self.is_stable = self.stable_count >= 5
        else:
            self.stable_count = 0
            self.is_stable = False
    
    def _auto_zero_tracking(self):
        """Auto-zero tracking como básculas comerciales"""
        # Solo activo cerca de cero y cuando está estable
        abs_filtered = abs(self.filtered_value)
        
        if abs_filtered <= self.zero_band and self.is_stable:
            self.zero_count += 1
            
            # Auto-zero gradual (como básculas reales)
            if self.zero_count >= 8:  # Después de estar estable en zero
                if self.zero_tracking_active:
                    correction = -self.filtered_value * self.auto_zero_rate
                    self.tare_offset += correction
                    self.zero_count = 0
        else:
            self.zero_count = 0
    
    def _update_display_value(self):
        """Actualizar valor de display con cuantización profesional"""
        # Aplicar tara
        tared_value = self.filtered_value + self.tare_offset
        
        # Banda muerta de cero
        if abs(tared_value) <= self.zero_band:
            quantized = 0.0
        else:
            # Cuantización a la resolución de display
            quantized = round(tared_value / self.display_resolution) * self.display_resolution
        
        # Buffer de display para suavizado adicional
        self.display_buffer.append(quantized)
        
        # Solo actualizar display si hay cambio significativo o es estable
        if len(self.display_buffer) >= 3:
            recent_displays = list(self.display_buffer)[-3:]
            
            # Si los últimos 3 valores son iguales, usar ese valor
            if len(set(recent_displays)) == 1:
                new_display = recent_displays[0]
            elif self.is_stable:
                # Si está estable, usar el valor más frecuente
                try:
                    new_display = max(set(recent_displays), key=recent_displays.count)
                except ValueError:
                    new_display = quantized
            else:
                # Si no está estable, cambiar solo si la diferencia es significativa
                if abs(quantized - self.last_display_value) >= self.display_resolution:
                    new_display = quantized
                else:
                    new_display = self.last_display_value
        else:
            new_display = quantized
        
        self.display_value = new_display
        self.last_display_value = new_display
    
    def apply_tara_instant(self):
        """Tara instantánea como básculas profesionales"""
        if len(self.filtered_buffer) >= 3:
            # Usar promedio de últimas lecturas filtradas
            recent_values = list(self.filtered_buffer)[-5:]
            average_filtered = sum(recent_values) / len(recent_values)
            
            # Aplicar tara instantáneamente
            self.tare_offset = -average_filtered
            
            # Resetear buffers de display para actualización inmediata
            self.display_buffer.clear()
            self.display_value = 0.0
            self.last_display_value = 0.0
            
            return True
        return False
    
    def reset_tara(self):
        """Reset de tara"""
        self.tare_offset = 0.0
        self.display_buffer.clear()
        
    def set_zero_tracking(self, enabled):
        """Activar/desactivar auto-zero tracking"""
        self.zero_tracking_active = enabled
        
    def get_stability_info(self):
        """Información de estabilidad para diagnóstico"""
        if len(self.filtered_buffer) >= self.stability_window:
            window = list(self.filtered_buffer)[-self.stability_window:]
            try:
                std_dev = statistics.pstdev(window) if len(window) > 1 else 0.0
            except statistics.StatisticsError:
                std_dev = float('inf')
        else:
            std_dev = float('inf')
            
        return {
            'std_dev': std_dev,
            'stable_count': self.stable_count,
            'zero_count': self.zero_count,
            'is_stable': self.is_stable,
            'buffer_size': len(self.filtered_buffer)
        }

class ProButton(tk.Button):
    """Botón profesional optimizado"""
    def __init__(self, parent, text="", command=None, btn_type="primary", 
                 icon="", width=None, height=2, **kwargs):
        
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
            parent, text=display_text, command=command,
            bg=style['bg'], fg=style['fg'],
            font=('Arial', 12, 'bold'), relief='flat', bd=0,
            height=height, width=width, cursor='hand2', **kwargs
        )

class ProfessionalWeightDisplay(tk.Frame):
    """Display de peso profesional con actualización suave"""
    
    def __init__(self, parent):
        super().__init__(parent, bg=THEME['surface'], relief='solid', bd=2)
        
        # Frame principal con padding
        main = tk.Frame(self, bg=THEME['surface'])
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # Display del peso principal
        self.weight_label = tk.Label(
            main, text="0.0", font=('Arial', 72, 'bold'),
            bg=THEME['surface'], fg=THEME['text']
        )
        self.weight_label.pack()
        
        # Frame inferior
        bottom = tk.Frame(main, bg=THEME['surface'])
        bottom.pack(fill=tk.X, pady=(15, 0))
        
        # Unidad
        self.unit_label = tk.Label(
            bottom, text="GRAMOS", font=('Arial', 16, 'bold'),
            bg=THEME['surface'], fg=THEME['primary']
        )
        self.unit_label.pack(side=tk.LEFT)
        
        # Indicador de estabilidad
        self.stability_frame = tk.Frame(bottom, bg=THEME['surface'])
        self.stability_frame.pack(side=tk.RIGHT)
        
        self.stability_dot = tk.Label(
            self.stability_frame, text="●", font=('Arial', 20, 'bold'),
            bg=THEME['surface'], fg=THEME['medium']
        )
        self.stability_dot.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stability_text = tk.Label(
            self.stability_frame, text="MIDIENDO", font=('Arial', 12, 'bold'),
            bg=THEME['surface'], fg=THEME['medium']
        )
        self.stability_text.pack(side=tk.LEFT)
        
        # Variables de animación
        self.current_display = 0.0
        self.target_display = 0.0
        self.animation_active = False
        
    def update_weight(self, weight_data):
        """Actualizar display con datos de peso"""
        display_weight = weight_data['display']
        is_stable = weight_data['stable']
        
        # Actualizar valor objetivo
        self.target_display = display_weight
        
        # Actualización inmediata para cambios grandes o cuando está estable
        weight_change = abs(display_weight - self.current_display)
        
        if weight_change >= 1.0 or is_stable or abs(display_weight) < 0.1:
            # Cambio inmediato
            self.current_display = display_weight
            self._update_display_immediate()
            self.animation_active = False
        else:
            # Transición suave para cambios menores
            if not self.animation_active:
                self.animation_active = True
                self._animate_to_target()
        
        # Actualizar indicador de estabilidad
        self._update_stability_indicator(is_stable, weight_data.get('zero_tracking', False))
    
    def _update_display_immediate(self):
        """Actualización inmediata del display"""
        # Formatear según magnitud
        if abs(self.current_display) >= 1000:
            text = f"{self.current_display:.1f}"
        elif abs(self.current_display) >= 10:
            text = f"{self.current_display:.1f}"
        else:
            text = f"{self.current_display:.1f}"
        
        self.weight_label.configure(text=text)
        
        # Color según valor
        if abs(self.current_display) < 0.1:
            color = THEME['medium']  # Gris para cero
        elif self.current_display < 0:
            color = THEME['danger']  # Rojo para negativo
        elif self.current_display > 5000:
            color = THEME['warning']  # Naranja para sobrecarga
        else:
            color = THEME['text']    # Negro para normal
            
        self.weight_label.configure(fg=color)
    
    def _animate_to_target(self):
        """Animación suave hacia el valor objetivo"""
        if not self.animation_active:
            return
            
        if abs(self.target_display - self.current_display) > 0.05:
            # Interpolación suave
            diff = self.target_display - self.current_display
            self.current_display += diff * 0.3  # Factor de suavizado
            
            self._update_display_immediate()
            
            # Continuar animación
            self.after(50, self._animate_to_target)
        else:
            # Llegar al objetivo exacto
            self.current_display = self.target_display
            self._update_display_immediate()
            self.animation_active = False
    
    def _update_stability_indicator(self, is_stable, zero_tracking):
        """Actualizar indicador de estabilidad"""
        if is_stable:
            if zero_tracking and abs(self.current_display) < 0.1:
                # Modo auto-zero
                self.stability_dot.configure(fg=THEME['warning'])
                self.stability_text.configure(text="AUTO-ZERO", fg=THEME['warning'])
            else:
                # Estable
                self.stability_dot.configure(fg=THEME['success'])
                self.stability_text.configure(text="ESTABLE", fg=THEME['success'])
        else:
            # Midiendo
            self.stability_dot.configure(fg=THEME['medium'])
            self.stability_text.configure(text="MIDIENDO", fg=THEME['medium'])

class SimpleKeyboard(tk.Toplevel):
    """Teclado simplificado para entrada numérica"""
    
    def __init__(self, parent, title="Entrada", initial="", numeric_only=False):
        super().__init__(parent)
        
        self.title(title)
        self.configure(bg=THEME['background'])
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.numeric_only = numeric_only
        
        if numeric_only:
            self.geometry("400x500")
            self.create_numeric_ui(initial)
        else:
            self.geometry("600x400")
            self.create_text_ui(initial)
            
        self.center_window()
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_reqwidth() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_reqheight() // 2)
        self.geometry(f"+{x}+{y}")
        
    def create_numeric_ui(self, initial):
        """Interfaz numérica optimizada"""
        # Título
        title_frame = tk.Frame(self, bg=THEME['surface'], relief='solid', bd=1)
        title_frame.pack(fill=tk.X, padx=15, pady=15)
        tk.Label(title_frame, text=self.title, font=('Arial', 16, 'bold'),
                bg=THEME['surface'], fg=THEME['text']).pack(pady=10)
        
        # Campo de entrada
        self.text_var = tk.StringVar(value=str(initial))
        self.entry = tk.Entry(
            self, textvariable=self.text_var, font=('Arial', 18),
            justify='center', bg='white', relief='solid', bd=2
        )
        self.entry.pack(fill=tk.X, padx=20, pady=15, ipady=10)
        
        # Teclado numérico
        keypad = tk.Frame(self, bg=THEME['background'])
        keypad.pack(expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        # Layout 3x4
        numbers = [
            ['7', '8', '9'],
            ['4', '5', '6'], 
            ['1', '2', '3'],
            ['0', '.', '⌫']
        ]
        
        for row_idx, row in enumerate(numbers):
            for col_idx, key in enumerate(row):
                if key == '⌫':
                    btn = ProButton(keypad, text='Borrar', command=self.backspace,
                                   btn_type='danger', width=8, height=3)
                else:
                    btn = ProButton(keypad, text=key, 
                                   command=lambda k=key: self.add_char(k),
                                   width=8, height=3)
                btn.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky='nsew')
        
        # Configurar expansión
        for i in range(4):
            keypad.grid_rowconfigure(i, weight=1)
        for i in range(3):
            keypad.grid_columnconfigure(i, weight=1)
        
        # Botones de control
        self.create_control_buttons()
        self.entry.focus_set()
        
    def create_text_ui(self, initial):
        """Interfaz de texto básica"""
        # Título
        tk.Label(self, text=self.title, font=('Arial', 16, 'bold'),
                bg=THEME['background'], fg=THEME['text']).pack(pady=15)
        
        # Campo de entrada
        self.text_var = tk.StringVar(value=str(initial))
        self.entry = tk.Entry(
            self, textvariable=self.text_var, font=('Arial', 16),
            bg='white', relief='solid', bd=2
        )
        self.entry.pack(fill=tk.X, padx=30, pady=20, ipady=8)
        
        # Botones de control
        self.create_control_buttons()
        self.entry.focus_set()
        
    def create_control_buttons(self):
        """Botones de control"""
        btn_frame = tk.Frame(self, bg=THEME['background'])
        btn_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ProButton(btn_frame, text='LIMPIAR', command=self.clear,
                 btn_type='warning', width=10).pack(side=tk.LEFT, padx=5)
        
        ProButton(btn_frame, text='CANCELAR', command=self.cancel,
                 btn_type='secondary', width=10).pack(side=tk.LEFT, padx=5)
        
        ProButton(btn_frame, text='ACEPTAR', command=self.accept,
                 btn_type='success', width=12).pack(side=tk.RIGHT, padx=5)
        
        # Bindings
        self.bind('<Return>', lambda e: self.accept())
        self.bind('<Escape>', lambda e: self.cancel())
        
    def add_char(self, char):
        current = self.text_var.get()
        self.text_var.set(current + char)
        
    def backspace(self):
        current = self.text_var.get()
        if current:
            self.text_var.set(current[:-1])
            
    def clear(self):
        self.text_var.set("")
        
    def accept(self):
        self.result = self.text_var.get()
        self.destroy()
        
    def cancel(self):
        self.result = None
        self.destroy()

class BasculaProfesional:
    """Aplicación principal con filtrado profesional"""
    
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_hardware()
        self.setup_variables()
        
        # Filtro profesional
        self.weight_filter = ProfessionalWeightFilter()
        
        self.create_ui()
        self.start_reading_system()
        
    def setup_window(self):
        """Configurar ventana"""
        self.root.title("⚖️ Báscula Digital Profesional - Filtrado Industrial")
        self.root.configure(bg=THEME['background'])
        
        # Adaptarse a la pantalla
        try:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            
            if width <= 800:
                self.root.geometry(f"{width}x{height}+0+0")
            else:
                self.root.geometry("1024x768")
        except tk.TclError:
            # Fallback si no se puede obtener el tamaño de pantalla
            self.root.geometry("1024x768")
            
        self.root.protocol("WM_DELETE_WINDOW", self.safe_exit)
        
    def setup_hardware(self):
        """Inicializar hardware"""
        # HX711
        self.hx711_available = False
        self.hx = None
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
        self.camera = None
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(main={"size": (1640, 1232)})
            self.camera.configure(config)
            self.camera.start()
            time.sleep(2)
            self.camera_available = True
            print("✅ Cámara lista")
        except Exception as e:
            print(f"⚠️ Cámara no disponible: {e}")
            self.camera = None
            
    def setup_variables(self):
        """Variables del sistema"""
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.session_start = time.time()
        
        # Parámetros HX711
        self.base_offset = -8575  # Tu valor base sin peso
        self.scale_factor = 1000.0  # Factor de calibración inicial
        
        # Estadísticas
        self.reading_count = 0
        self.last_saved_weight = 0.0
        
    def create_ui(self):
        """Crear interfaz de usuario"""
        # Header
        self.create_header()
        
        # Contenido principal
        main_frame = tk.Frame(self.root, bg=THEME['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Display de peso (ocupar más espacio)
        self.weight_display = ProfessionalWeightDisplay(main_frame)
        self.weight_display.pack(fill=tk.BOTH, expand=True)
        
        # Panel de controles (más compacto)
        self.create_control_panel(main_frame)
        
        # Footer con información
        self.create_footer()
        
    def create_header(self):
        """Header de la aplicación"""
        header = tk.Frame(self.root, bg=THEME['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        content = tk.Frame(header, bg=THEME['surface'])
        content.pack(fill=tk.X, padx=20, pady=12)
        
        # Título
        tk.Label(
            content, text="⚖️ BÁSCULA DIGITAL PROFESIONAL",
            font=('Arial', 18, 'bold'), bg=THEME['surface'], fg=THEME['primary']
        ).pack(side=tk.LEFT)
        
        # Estado del sistema
        status_frame = tk.Frame(content, bg=THEME['surface'])
        status_frame.pack(side=tk.RIGHT)
        
        hx_status = "HX711 ✅" if self.hx711_available else "HX711 ❌"
        cam_status = "CAM ✅" if self.camera_available else "CAM ❌"
        
        tk.Label(status_frame, text=f"{hx_status} • {cam_status}",
                font=('Arial', 10), bg=THEME['surface'], 
                fg=THEME['success'] if (self.hx711_available and self.camera_available) else THEME['warning']
                ).pack()
                
    def create_control_panel(self, parent):
        """Panel de controles optimizado"""
        control_frame = tk.Frame(parent, bg=THEME['background'])
        control_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Botones principales en una fila
        main_buttons = tk.Frame(control_frame, bg=THEME['background'])
        main_buttons.pack(fill=tk.X, pady=5)
        
        ProButton(main_buttons, text="TARA", icon="🔄",
                 command=self.tara_instant, btn_type="primary",
                 width=12, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                 
        ProButton(main_buttons, text="CALIBRAR", icon="⚙️",
                 command=self.calibrate, btn_type="warning", 
                 width=12, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                 
        ProButton(main_buttons, text="GUARDAR", icon="💾",
                 command=self.save_measurement, btn_type="success",
                 width=12, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                 
        ProButton(main_buttons, text="FOTO", icon="📷", 
                 command=self.take_photo, btn_type="secondary",
                 width=12, height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Botones secundarios
        secondary_buttons = tk.Frame(control_frame, bg=THEME['background'])
        secondary_buttons.pack(fill=tk.X, pady=(8, 0))
        
        ProButton(secondary_buttons, text="ZERO-TRACK ON/OFF",
                 command=self.toggle_zero_tracking, btn_type="light",
                 height=1).pack(side=tk.LEFT, padx=2)
                 
        ProButton(secondary_buttons, text="DIAGNÓSTICO",
                 command=self.show_diagnostics, btn_type="light",
                 height=1).pack(side=tk.LEFT, padx=2)
                 
        ProButton(secondary_buttons, text="RESET",
                 command=self.reset_system, btn_type="light",
                 height=1).pack(side=tk.LEFT, padx=2)
                 
        ProButton(secondary_buttons, text="SALIR", icon="🚪",
                 command=self.safe_exit, btn_type="danger",
                 height=1).pack(side=tk.RIGHT, padx=2)
                 
        # Información de sesión
        self.info_label = tk.Label(
            control_frame, text="Sistema iniciado - Lecturas: 0",
            font=('Arial', 9), bg=THEME['background'], fg=THEME['text_light']
        )
        self.info_label.pack(pady=(8, 0))
        
    def create_footer(self):
        """Footer con timestamp"""
        footer = tk.Frame(self.root, bg=THEME['surface'], relief='solid', bd=1)
        footer.pack(fill=tk.X, padx=20, pady=(5, 20))
        
        content = tk.Frame(footer, bg=THEME['surface'])
        content.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(content, text="Raspberry Pi Zero 2W • HX711 • Filtrado Profesional",
                font=('Arial', 8), bg=THEME['surface'], fg=THEME['text_light']).pack(side=tk.LEFT)
        
        self.timestamp_label = tk.Label(
            content, text="", font=('Arial', 8),
            bg=THEME['surface'], fg=THEME['text_light']
        )
        self.timestamp_label.pack(side=tk.RIGHT)
        
        self.update_timestamp()
        
    def update_timestamp(self):
        """Actualizar timestamp cada segundo"""
        try:
            current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.timestamp_label.configure(text=current_time)
        except Exception:
            pass
        self.root.after(1000, self.update_timestamp)
        
    # ============ SISTEMA DE LECTURA ============
    
    def start_reading_system(self):
        """Iniciar sistema de lectura profesional"""
        self.is_reading = True
        
        # Thread de lectura a 10 Hz (como básculas comerciales)
        self.reading_thread = threading.Thread(target=self.reading_worker, daemon=True)
        self.reading_thread.start()
        
        # UI update a 5 Hz para suavidad
        self.ui_update()
        
    def reading_worker(self):
        """Worker de lectura optimizado"""
        while self.is_reading:
            try:
                if self.hx711_available and self.hx:
                    # Lectura real HX711
                    raw_readings = self.hx.get_raw_data(times=3)
                    if raw_readings:
                        valid = [r for r in raw_readings if r is not None]
                        if valid:
                            raw_avg = sum(valid) / len(valid)
                            # Convertir a peso en gramos
                            weight_g = (raw_avg - self.base_offset) / self.scale_factor
                            self.weight_queue.put(weight_g)
                else:
                    # Simulación mejorada para desarrollo
                    import random
                    t = time.time()
                    
                    # Simular peso base con variaciones realistas
                    base_weight = 500 + 300 * math.sin(t * 0.3)  # Cambio lento
                    noise = random.gauss(0, 2.0)  # Ruido gaussiano
                    spikes = random.choice([0, 0, 0, 0, random.uniform(-10, 10)])  # Picos ocasionales
                    
                    sim_weight = max(0, base_weight + noise + spikes)
                    self.weight_queue.put(sim_weight)
                
                time.sleep(0.1)  # 10 Hz de lectura
                
            except Exception as e:
                print(f"Error en lectura: {e}")
                time.sleep(0.2)
                
    def ui_update(self):
        """Actualización de UI a 5 Hz"""
        try:
            # Procesar todas las lecturas pendientes
            readings_processed = 0
            while not self.weight_queue.empty() and readings_processed < 10:
                try:
                    raw_weight = self.weight_queue.get_nowait()
                    
                    # Procesar con filtro profesional
                    weight_data = self.weight_filter.process_reading(raw_weight)
                    
                    # Actualizar display
                    self.weight_display.update_weight(weight_data)
                    
                    self.reading_count += 1
                    readings_processed += 1
                    
                except queue.Empty:
                    break
            
            # Actualizar información de sesión cada 50 actualizaciones (10 segundos aprox)
            if self.reading_count % 50 == 0 and self.reading_count > 0:
                self.update_session_info()
                
        except Exception as e:
            print(f"Error actualizando UI: {e}")
        
        # Continuar loop a 5 Hz
        if self.is_reading:
            self.root.after(200, self.ui_update)
        
    def update_session_info(self):
        """Actualizar información de la sesión"""
        try:
            uptime = int(time.time() - self.session_start)
            stability_info = self.weight_filter.get_stability_info()
            
            info_text = (f"Lecturas: {self.reading_count} • "
                        f"Tiempo: {uptime//60:02d}:{uptime%60:02d} • "
                        f"Estabilidad: {stability_info['std_dev']:.2f}g")
            
            self.info_label.configure(text=info_text)
        except Exception as e:
            print(f"Error actualizando info de sesión: {e}")
        
    # ============ FUNCIONES DE CONTROL ============
    
    def tara_instant(self):
        """Tara instantánea profesional"""
        try:
            success = self.weight_filter.apply_tara_instant()
            if success:
                self.show_status("TARA APLICADA", "success", 1500)
            else:
                self.show_status("Esperando lecturas estables...", "warning", 2000)
        except Exception as e:
            print(f"Error aplicando tara: {e}")
            self.show_status("Error en tara", "danger", 2000)
    
    def calibrate(self):
        """Calibración profesional"""
        try:
            # Pedir peso conocido
            keyboard = SimpleKeyboard(self.root, "Peso de Calibración (gramos)", "1000", numeric_only=True)
            self.root.wait_window(keyboard)
            
            if not keyboard.result:
                return
                
            known_weight = float(keyboard.result)
            if known_weight <= 0:
                raise ValueError("El peso debe ser positivo")
                
            # Necesitamos lecturas estables para calibrar
            stability = self.weight_filter.get_stability_info()
            if not stability['is_stable']:
                self.show_status("Esperando estabilidad para calibrar...", "warning", 3000)
                return
            
            # Obtener peso actual filtrado (sin tara)
            current_filtered = self.weight_filter.filtered_value
            
            if abs(current_filtered) < 1.0:
                self.show_status("Coloque el peso conocido en la báscula", "warning", 3000)
                return
            
            # Calcular nuevo factor de escala
            new_scale_factor = self.scale_factor * abs(current_filtered / known_weight)
            self.scale_factor = new_scale_factor
            
            # Guardar calibración
            try:
                settings = {'scale_factor': self.scale_factor, 'base_offset': self.base_offset}
                with open(SETTINGS_PATH, 'w') as f:
                    json.dump(settings, f, indent=2)
            except Exception:
                pass
            
            self.show_status(f"CALIBRADO: {known_weight}g", "success", 3000)
            
        except ValueError:
            self.show_status("Peso inválido", "danger", 2000)
        except Exception as e:
            print(f"Error en calibración: {e}")
            self.show_status("Error en calibración", "danger", 2000)
    
    def save_measurement(self):
        """Guardar medición actual"""
        try:
            current_weight = self.weight_display.current_display
            is_stable = self.weight_filter.is_stable
            
            # Advertir si no está estable
            if not is_stable:
                if not messagebox.askyesno("Medición Inestable", 
                                         "La medición no está estable.\n¿Guardar de todos modos?"):
                    return
            
            # Datos de la medición
            measurement = {
                "timestamp": datetime.now().isoformat(),
                "weight": round(current_weight, 2),
                "unit": "g",
                "stable": is_stable,
                "filter_data": self.weight_filter.get_stability_info()
            }
            
            # Capturar foto si está disponible
            photo_path = ""
            if self.camera_available:
                photo_path = self.capture_photo(current_weight)
                if photo_path:
                    measurement["photo"] = photo_path
            
            # Guardar a archivo JSON
            measurements_file = os.path.join(BASE_DIR, "measurements.json")
            
            # Cargar mediciones existentes
            try:
                with open(measurements_file, 'r') as f:
                    measurements = json.load(f)
            except FileNotFoundError:
                measurements = []
                
            measurements.append(measurement)
            
            # Guardar con backup
            with open(measurements_file, 'w') as f:
                json.dump(measurements, f, indent=2)
            
            self.last_saved_weight = current_weight
            count = len(measurements)
            
            if photo_path:
                self.show_status(f"GUARDADO #{count} + FOTO", "success", 2500)
            else:
                self.show_status(f"GUARDADO #{count}", "success", 2000)
                
        except Exception as e:
            print(f"Error guardando medición: {e}")
            self.show_status(f"ERROR: {str(e)[:30]}", "danger", 3000)
    
    def take_photo(self):
        """Capturar foto manual"""
        try:
            if not self.camera_available:
                self.show_status("CÁMARA NO DISPONIBLE", "danger", 2000)
                return
                
            current_weight = self.weight_display.current_display
            photo_path = self.capture_photo(current_weight)
            
            if photo_path:
                self.show_status("FOTO CAPTURADA", "success", 2000)
            else:
                self.show_status("ERROR EN FOTO", "danger", 2000)
        except Exception as e:
            print(f"Error capturando foto: {e}")
            self.show_status("ERROR EN FOTO", "danger", 2000)
    
    def capture_photo(self, weight):
        """Capturar foto con timestamp"""
        if not self.camera_available or not self.camera:
            return ""
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"peso_{timestamp}_{weight:.1f}g.jpg"
            photo_path = os.path.join(CAPTURE_DIR, filename)
            
            self.camera.capture_file(photo_path)
            
            # Verificar que se creó correctamente
            if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
                print(f"📷 Foto guardada: {filename}")
                return photo_path
            else:
                return ""
                
        except Exception as e:
            print(f"Error capturando foto: {e}")
            return ""
    
    def toggle_zero_tracking(self):
        """Activar/desactivar auto-zero tracking"""
        try:
            current_state = self.weight_filter.zero_tracking_active
            self.weight_filter.set_zero_tracking(not current_state)
            
            if not current_state:
                self.show_status("AUTO-ZERO ACTIVADO", "success", 2000)
            else:
                self.show_status("AUTO-ZERO DESACTIVADO", "warning", 2000)
        except Exception as e:
            print(f"Error toggling zero tracking: {e}")
    
    def show_diagnostics(self):
        """Mostrar diagnóstico detallado"""
        try:
            stability = self.weight_filter.get_stability_info()
            
            diag_text = f"""DIAGNÓSTICO DEL SISTEMA

Hardware:
• HX711: {'✅ Conectado' if self.hx711_available else '❌ No disponible'}
• Cámara: {'✅ Conectada' if self.camera_available else '❌ No disponible'}

Filtro de Peso:
• Desviación estándar: {stability['std_dev']:.3f}g
• Contador estabilidad: {stability['stable_count']}
• Contador auto-zero: {stability['zero_count']}
• Estado estable: {'✅' if stability['is_stable'] else '❌'}
• Buffer lleno: {stability['buffer_size']}/{self.weight_filter.stability_window}

Sistema:
• Lecturas totales: {self.reading_count}
• Factor de escala: {self.scale_factor:.3f}
• Offset base: {self.base_offset}
• Tara actual: {self.weight_filter.tare_offset:.2f}g

Valores Actuales:
• Peso filtrado: {self.weight_filter.filtered_value:.2f}g
• Peso display: {self.weight_filter.display_value:.1f}g
• Zero tracking: {'✅' if self.weight_filter.zero_tracking_active else '❌'}
"""
            
            messagebox.showinfo("Diagnóstico del Sistema", diag_text)
        except Exception as e:
            print(f"Error mostrando diagnóstico: {e}")
            messagebox.showerror("Error", f"Error en diagnóstico: {e}")
    
    def reset_system(self):
        """Reset completo del sistema"""
        try:
            if messagebox.askyesno("Reset del Sistema", 
                                 "¿Reiniciar completamente el sistema?\n\n"
                                 "Se perderán:\n"
                                 "• Calibración de tara\n"
                                 "• Estadísticas de sesión\n"
                                 "• Filtros de peso"):
                
                # Reset del filtro
                self.weight_filter = ProfessionalWeightFilter()
                
                # Reset de variables
                self.reading_count = 0
                self.session_start = time.time()
                self.last_saved_weight = 0.0
                
                # Reset de display
                self.weight_display.current_display = 0.0
                self.weight_display.target_display = 0.0
                self.weight_display.animation_active = False
                self.weight_display._update_display_immediate()
                
                self.show_status("SISTEMA RESETEADO", "success", 2500)
        except Exception as e:
            print(f"Error reseteando sistema: {e}")
            self.show_status("Error en reset", "danger", 2000)
    
    def show_status(self, message, status_type="info", duration=2000):
        """Mostrar mensaje de estado temporal"""
        try:
            original_text = self.info_label.cget('text')
            original_color = self.info_label.cget('fg')
            
            # Colores según tipo
            colors = {
                'success': THEME['success'],
                'warning': THEME['warning'], 
                'danger': THEME['danger'],
                'info': THEME['primary']
            }
            
            # Mostrar mensaje
            self.info_label.configure(text=f"● {message}", fg=colors.get(status_type, THEME['primary']))
            
            # Restaurar después del tiempo especificado
            self.root.after(duration, lambda: self._restore_status(original_text, original_color))
        except Exception as e:
            print(f"Error mostrando status: {e}")
            
    def _restore_status(self, original_text, original_color):
        """Restaurar texto de status original"""
        try:
            if hasattr(self, 'info_label') and self.info_label.winfo_exists():
                self.info_label.configure(text=original_text, fg=original_color)
        except Exception:
            pass
    
    def safe_exit(self):
        """Salida segura del sistema"""
        try:
            if messagebox.askyesno("Salir del Sistema", 
                                 "¿Está seguro de que desea cerrar el sistema de báscula?"):
                
                print("🔄 Cerrando sistema...")
                
                # Parar lectura
                self.is_reading = False
                
                # Cleanup de hardware
                try:
                    if self.camera_available and self.camera:
                        self.camera.stop()
                        self.camera.close()
                        print("📷 Cámara cerrada")
                except Exception as e:
                    print(f"Warning: Error cerrando cámara: {e}")
                
                try:
                    if self.hx711_available:
                        import RPi.GPIO as GPIO
                        GPIO.cleanup()
                        print("⚖️ GPIO limpiado")
                except Exception as e:
                    print(f"Warning: Error limpiando GPIO: {e}")
                
                # Guardar configuración final
                try:
                    final_settings = {
                        'scale_factor': self.scale_factor,
                        'base_offset': self.base_offset,
                        'total_readings': self.reading_count,
                        'last_session': datetime.now().isoformat()
                    }
                    with open(SETTINGS_PATH, 'w') as f:
                        json.dump(final_settings, f, indent=2)
                    print("💾 Configuración guardada")
                except Exception:
                    pass
                
                print("👋 Sistema cerrado correctamente")
                self.root.quit()
        except Exception as e:
            print(f"Error en salida segura: {e}")
            self.root.quit()

def main():
    """Función principal"""
    print("🚀 Iniciando Báscula Digital Profesional con Filtrado Industrial")
    print("=" * 60)
    
    try:
        # Crear aplicación
        root = tk.Tk()
        app = BasculaProfesional(root)
        
        print("✅ Sistema iniciado correctamente")
        print("📊 Filtrado profesional activo")
        print("🎯 Listo para pesar con precisión industrial")
        print("=" * 60)
        
        # Ejecutar aplicación
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\n⚠️ Aplicación interrumpida por el usuario")
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error Crítico", f"Error en la aplicación:\n{e}")
    finally:
        print("🔄 Finalizando aplicación...")
        try:
            root.quit()
        except:
            pass

if __name__ == "__main__":
    main()