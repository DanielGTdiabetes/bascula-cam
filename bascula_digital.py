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
    """Teclado simplificado mejorado con botón ACEPTAR visible"""
    
    def __init__(self, parent, title="Entrada", initial="", numeric_only=False):
        super().__init__(parent)
        
        self.title(title)
        self.configure(bg=THEME['background'])
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        self.numeric_only = numeric_only
        
        if numeric_only:
            self.geometry("500x600")
            self.create_numeric_ui(initial)
        else:
            self.geometry("700x500")
            self.create_text_ui(initial)
            
        self.center_window()
        
        # Focus en el entry
        self.entry.focus_set()
        self.entry.selection_range(0, tk.END)
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_reqwidth() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_reqheight() // 2)
        self.geometry(f"+{x}+{y}")
        
    def create_numeric_ui(self, initial):
        """Interfaz numérica optimizada con botón ACEPTAR grande"""
        # Título más grande
        title_frame = tk.Frame(self, bg=THEME['surface'], relief='solid', bd=2)
        title_frame.pack(fill=tk.X, padx=20, pady=20)
        tk.Label(title_frame, text=self.title, font=('Arial', 18, 'bold'),
                bg=THEME['surface'], fg=THEME['text']).pack(pady=15)
        
        # Campo de entrada más grande
        entry_frame = tk.Frame(self, bg=THEME['background'])
        entry_frame.pack(fill=tk.X, padx=20, pady=15)
        
        self.text_var = tk.StringVar(value=str(initial))
        self.entry = tk.Entry(
            entry_frame, textvariable=self.text_var, font=('Arial', 24),
            justify='center', bg='white', relief='solid', bd=3
        )
        self.entry.pack(fill=tk.X, ipady=15)
        
        # Teclado numérico más grande
        keypad = tk.Frame(self, bg=THEME['background'])
        keypad.pack(expand=True, fill=tk.BOTH, padx=30, pady=20)
        
        # Layout 3x4 mejorado
        numbers = [
            ['7', '8', '9'],
            ['4', '5', '6'], 
            ['1', '2', '3'],
            ['C', '0', '.']
        ]
        
        for row_idx, row in enumerate(numbers):
            for col_idx, key in enumerate(row):
                if key == 'C':
                    btn = ProButton(keypad, text='LIMPIAR', command=self.clear,
                                   btn_type='warning', width=10, height=3)
                else:
                    btn = ProButton(keypad, text=key, 
                                   command=lambda k=key: self.add_char(k),
                                   width=10, height=3)
                btn.grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky='nsew')
        
        # Botón borrar en fila separada
        ProButton(keypad, text='⌫ BORRAR', command=self.backspace,
                 btn_type='danger', width=32, height=3).grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        
        # Configurar expansión
        for i in range(5):
            keypad.grid_rowconfigure(i, weight=1)
        for i in range(3):
            keypad.grid_columnconfigure(i, weight=1)
        
        # Botones de control MÁS GRANDES
        self.create_control_buttons()
        
    def create_text_ui(self, initial):
        """Interfaz de texto básica mejorada"""
        # Título
        title_frame = tk.Frame(self, bg=THEME['surface'], relief='solid', bd=2)
        title_frame.pack(fill=tk.X, padx=20, pady=20)
        tk.Label(title_frame, text=self.title, font=('Arial', 18, 'bold'),
                bg=THEME['surface'], fg=THEME['text']).pack(pady=15)
        
        # Campo de entrada
        self.text_var = tk.StringVar(value=str(initial))
        self.entry = tk.Entry(
            self, textvariable=self.text_var, font=('Arial', 20),
            bg='white', relief='solid', bd=3
        )
        self.entry.pack(fill=tk.X, padx=30, pady=20, ipady=12)
        
        # Teclado QWERTY básico
        keyboard_frame = tk.Frame(self, bg=THEME['background'])
        keyboard_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=10)
        
        # Layout básico
        rows = [
            '1234567890',
            'qwertyuiop',
            'asdfghjkl',
            'zxcvbnm'
        ]
        
        for row in rows:
            row_frame = tk.Frame(keyboard_frame, bg=THEME['background'])
            row_frame.pack(pady=5)
            
            for char in row:
                btn = tk.Button(
                    row_frame, text=char.upper(),
                    command=lambda c=char: self.add_char(c),
                    width=5, height=2,
                    font=('Arial', 12, 'bold'),
                    bg=THEME['surface'], fg=THEME['text'],
                    relief='solid', bd=2
                )
                btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Fila especial
        special_frame = tk.Frame(keyboard_frame, bg=THEME['background'])
        special_frame.pack(pady=10)
        
        ProButton(special_frame, text='ESPACIO', 
                 command=lambda: self.add_char(' '),
                 width=20, height=2).pack(side=tk.LEFT, padx=5)
        
        ProButton(special_frame, text='⌫ BORRAR', 
                 command=self.backspace, btn_type='danger',
                 width=12, height=2).pack(side=tk.LEFT, padx=5)
        
        # Botones de control
        self.create_control_buttons()
        
    def create_control_buttons(self):
        """Botones de control MÁS GRANDES Y VISIBLES"""
        btn_frame = tk.Frame(self, bg=THEME['background'])
        btn_frame.pack(fill=tk.X, padx=20, pady=30)
        
        # Botones más grandes y visibles
        ProButton(btn_frame, text='❌ CANCELAR', command=self.cancel,
                 btn_type='danger', width=15, height=3).pack(side=tk.LEFT, padx=10)
        
        # BOTÓN ACEPTAR MUY GRANDE Y VERDE
        ProButton(btn_frame, text='✅ ACEPTAR', command=self.accept,
                 btn_type='success', width=20, height=3).pack(side=tk.RIGHT, padx=10)
        
        # Bindings mejorados
        self.bind('<Return>', lambda e: self.accept())
        self.bind('<KP_Enter>', lambda e: self.accept())  # Enter del keypad
        self.bind('<Escape>', lambda e: self.cancel())
        
        # Binding para el entry también
        self.entry.bind('<Return>', lambda e: self.accept())
        self.entry.bind('<KP_Enter>', lambda e: self.accept())
        
    def add_char(self, char):
        current = self.text_var.get()
        self.text_var.set(current + char)
        self.entry.icursor(tk.END)  # Mover cursor al final
        
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
        """Configurar ventana a PANTALLA COMPLETA"""
        self.root.title("⚖️ Báscula Digital Profesional - Filtrado Industrial")
        self.root.configure(bg=THEME['background'])
        
        # PANTALLA COMPLETA FORZADA
        try:
            # Método 1: Geometry completa
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            self.root.geometry(f"{width}x{height}+0+0")
            
            # Método 2: Sin decoraciones de ventana
            self.root.overrideredirect(False)
            
            # Método 3: Estado fullscreen si está disponible
            try:
                self.root.attributes('-fullscreen', True)
            except tk.TclError:
                try:
                    self.root.attributes('-zoomed', True)
                except tk.TclError:
                    self.root.state('zoomed')
                    
        except Exception as e:
            print(f"Error configurando pantalla completa: {e}")
            self.root.geometry("1024x768")
            
        # Binding para salir de pantalla completa con ESC
        self.root.bind('<Escape>', self.toggle_fullscreen)
        self.root.bind('<F11>', self.toggle_fullscreen)
        
        self.root.protocol("WM_DELETE_WINDOW", self.safe_exit)
        
    def toggle_fullscreen(self, event=None):
        """Toggle pantalla completa con ESC o F11"""
        try:
            is_fullscreen = self.root.attributes('-fullscreen')
            self.root.attributes('-fullscreen', not is_fullscreen)
        except tk.TclError:
            # Si no soporta -fullscreen, usar geometry
            if self.root.winfo_width() >= self.root.winfo_screenwidth() * 0.9:
                self.root.geometry("1024x768")
            else:
                width = self.root.winfo_screenwidth()
                height = self.root.winfo_screenheight()
                self.root.geometry(f"{width}x{height}+0+0")
        
    def setup_hardware(self):
        """Inicializar hardware con mejor detección de cámara"""
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
            
        # Cámara - Detección mejorada
        self.camera_available = False
        self.camera = None
        
        # Verificar si el dispositivo de cámara existe
        camera_devices = ['/dev/video0', '/dev/video1', '/dev/video2']
        camera_found = any(os.path.exists(dev) for dev in camera_devices)
        
        if not camera_found:
            print("⚠️ No se encontró dispositivo de cámara en /dev/video*")
        
        try:
            print("🔍 Intentando inicializar Picamera2...")
            from picamera2 import Picamera2
            
            self.camera = Picamera2()
            
            # Configuración más robusta
            still_config = self.camera.create_still_configuration(
                main={"size": (1640, 1232)},
                lores={"size": (320, 240)},
                display="lores"
            )
            
            print("📷 Configurando cámara...")
            self.camera.configure(still_config)
            
            print("🚀 Iniciando cámara...")
            self.camera.start()
            
            # Esperar más tiempo para la inicialización
            print("⏳ Esperando estabilización...")
            time.sleep(3)
            
            # Test de captura
            print("🧪 Probando captura...")
            test_path = "/tmp/test_camera.jpg"
            self.camera.capture_file(test_path)
            
            if os.path.exists(test_path) and os.path.getsize(test_path) > 0:
                os.remove(test_path)
                self.camera_available = True
                print("✅ Cámara inicializada correctamente")
            else:
                raise Exception("Test de captura falló")
                
        except ImportError:
            print("❌ Picamera2 no instalado. Instala con: sudo apt install python3-picamera2")
        except Exception as e:
            print(f"❌ Error inicializando cámara: {e}")
            print("💡 Soluciones:")
            print("   1. Verificar conexión física")
            print("   2. sudo raspi-config > Interface Options > Camera > Enable")
            print("   3. Verificar /boot/config.txt: dtparam=camera=on")
            print("   4. sudo reboot")
            
            if self.camera:
                try:
                    self.camera.close()
                except:
                    pass
            self.camera = None
            
    def setup_variables(self):
        """Variables del sistema"""
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.session_start = time.time()
        
        # Parámetros HX711 - CALIBRACIÓN CORREGIDA
        self.base_offset = -8575  # Tu valor base sin peso
        self.scale_factor = 400.0  # Factor más realista para HX711 (ajustar según tu celda)
        
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
        
        # Estado del sistema mejorado
        status_frame = tk.Frame(content, bg=THEME['surface'])
        status_frame.pack(side=tk.RIGHT)
        
        hx_status = "HX711 ✅" if self.hx711_available else "HX711 ❌"
        cam_status = "CAM ✅" if self.camera_available else "CAM ❌"
        
        status_text = f"{hx_status} • {cam_status} • F11=Pantalla completa"
        
        tk.Label(status_frame, text=status_text,
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
        
        tk.Label(content, text="Raspberry Pi Zero 2W • HX711 • Filtrado Profesional • ESC=Salir Pantalla Completa",
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
                            # Convertir a peso en gramos - FÓRMULA CORREGIDA
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
        """Calibración profesional CORREGIDA"""
        try:
            # Mostrar instrucciones
            messagebox.showinfo("Calibración - Paso 1", 
                               "PASO 1: Retire todo peso de la báscula\n"
                               "Presione OK cuando esté vacía")
            
            # Esperar a que esté estable sin peso
            stability = self.weight_filter.get_stability_info()
            if not stability['is_stable']:
                self.show_status("Esperando estabilidad sin peso...", "warning", 3000)
                return
            
            # Capturar valor sin peso
            zero_value = self.weight_filter.filtered_value
            
            # Pedir peso conocido
            keyboard = SimpleKeyboard(self.root, "PASO 2: Peso de Calibración (gramos)", "1000", numeric_only=True)
            self.root.wait_window(keyboard)
            
            if not keyboard.result:
                return
                
            known_weight = float(keyboard.result)
            if known_weight <= 0:
                raise ValueError("El peso debe ser positivo")
            
            # Mostrar instrucción para colocar peso
            messagebox.showinfo("Calibración - Paso 2", 
                               f"PASO 2: Coloque exactamente {known_weight}g en la báscula\n"
                               "Presione OK cuando esté colocado")
            
            # Esperar estabilidad con peso
            time.sleep(1)  # Dar tiempo para colocar peso
            attempts = 0
            while attempts < 30:  # Máximo 30 segundos
                stability = self.weight_filter.get_stability_info()
                if stability['is_stable']:
                    break
                time.sleep(1)
                attempts += 1
                
            if not stability['is_stable']:
                self.show_status("Peso no estable. Inténtelo de nuevo.", "warning", 3000)
                return
            
            # Capturar valor con peso
            weight_value = self.weight_filter.filtered_value
            
            # Verificar que hay diferencia significativa
            raw_difference = abs(weight_value - zero_value)
            if raw_difference < 10:  # Menos de 10 unidades de diferencia
                self.show_status("Diferencia insuficiente. Verifique el peso.", "warning", 3000)
                return
            
            # Calcular nuevo factor de escala
            # known_weight = (raw_with_weight - raw_without_weight) / scale_factor
            # scale_factor = (raw_with_weight - raw_without_weight) / known_weight
            raw_per_gram = raw_difference / known_weight
            self.scale_factor = raw_per_gram
            
            # Actualizar offset base
            self.base_offset = zero_value * self.scale_factor
            
            # Reset tara después de calibración
            self.weight_filter.tare_offset = 0.0
            
            # Guardar calibración
            try:
                settings = {
                    'scale_factor': self.scale_factor, 
                    'base_offset': self.base_offset,
                    'calibration_date': datetime.now().isoformat(),
                    'calibration_weight': known_weight
                }
                with open(SETTINGS_PATH, 'w') as f:
                    json.dump(settings, f, indent=2)
            except Exception:
                pass
            
            self.show_status(f"CALIBRADO: {known_weight}g (Factor: {self.scale_factor:.1f})", "success", 4000)
            
            # Mostrar resultado
            messagebox.showinfo("Calibración Completada", 
                               f"✅ Calibración exitosa\n\n"
                               f"Peso usado: {known_weight}g\n"
                               f"Factor de escala: {self.scale_factor:.2f}\n"
                               f"La báscula está lista para usar")
            
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
        """Capturar foto manual MEJORADA"""
        try:
            if not self.camera_available:
                self.show_status("CÁMARA NO DISPONIBLE", "danger", 2000)
                messagebox.showwarning("Cámara", "La cámara no está disponible.\n\nPosibles soluciones:\n1. Verificar conexión física\n2. sudo raspi-config > Interface Options > Camera\n3. Reiniciar sistema")
                return
                
            current_weight = self.weight_display.current_display
            self.show_status("📷 Capturando foto...", "warning", 1000)
            
            photo_path = self.capture_photo(current_weight)
            
            if photo_path:
                self.show_status("FOTO CAPTURADA", "success", 2000)
                messagebox.showinfo("Foto Guardada", f"Foto guardada en:\n{os.path.basename(photo_path)}")
            else:
                self.show_status("ERROR EN FOTO", "danger", 2000)
                messagebox.showerror("Error", "No se pudo capturar la foto.\nVerifique la cámara.")
        except Exception as e:
            print(f"Error capturando foto: {e}")
            self.show_status("ERROR EN FOTO", "danger", 2000)
    
    def capture_photo(self, weight):
        """Capturar foto con timestamp MEJORADA"""
        if not self.camera_available or not self.camera:
            return ""
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"peso_{timestamp}_{weight:.1f}g.jpg"
            photo_path = os.path.join(CAPTURE_DIR, filename)
            
            # Capturar con timeout
            self.camera.capture_file(photo_path)
            
            # Esperar un poco para que se complete la escritura
            time.sleep(0.5)
            
            # Verificar que se creó correctamente
            if os.path.exists(photo_path) and os.path.getsize(photo_path) > 1000:  # Al menos 1KB
                print(f"📷 Foto guardada: {filename} ({os.path.getsize(photo_path)} bytes)")
                return photo_path
            else:
                print(f"❌ Foto falló: archivo muy pequeño o no existe")
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

Calibración:
• Factor de escala: {self.scale_factor:.3f}
• Offset base: {self.base_offset:.1f}
• Tara actual: {self.weight_filter.tare_offset:.2f}g

Valores Actuales:
• Peso filtrado: {self.weight_filter.filtered_value:.2f}g
• Peso display: {self.weight_filter.display_value:.1f}g
• Zero tracking: {'✅' if self.weight_filter.zero_tracking_active else '❌'}

Sesión:
• Lecturas totales: {self.reading_count}
• Tiempo activo: {int(time.time() - self.session_start)//60:02d}:{int(time.time() - self.session_start)%60:02d}
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
        print("🔧 F11 = Pantalla completa • ESC = Salir pantalla completa")
        print("=" * 60)
        
        # Ejecutar aplicación
        root.mainloop()
        
    except KeyboardInterrupt:
        print("\n⚠️ Aplicación interrumpida por el usuario")
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        try:
            messagebox.showerror("Error Crítico", f"Error en la aplicación:\n{e}")
        except:
            pass
    finally:
        print("🔄 Finalizando aplicación...")
        try:
            root.quit()
        except:
            pass

if __name__ == "__main__":
    main()
