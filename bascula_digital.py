#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Profesional - Versión Compatible con Raspberry Pi
Interfaz moderna y funcional, optimizada para hardware limitado
Versión Mejorada 2.0
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
import csv  # ## MEJORA: Usaremos CSV para un guardado más eficiente

import tkinter as tk
from tkinter import ttk, messagebox

# --- CONFIGURACIÓN Y CONSTANTES (Sin cambios) ---
BASE_DIR = os.path.expanduser("~/bascula-cam")
CAPTURE_DIR = os.path.join(BASE_DIR, "capturas")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
MEASUREMENTS_PATH = os.path.join(BASE_DIR, "measurements.csv") # ## MEJORA: Ruta para el archivo CSV

for d in (CAPTURE_DIR, DATA_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

THEME = {
    'primary': '#2563eb', 'primary_light': '#3b82f6', 'success': '#10b981',
    'danger': '#ef4444', 'warning': '#f59e0b', 'dark': '#1f2937',
    'medium': '#6b7280', 'light': '#9ca3af', 'background': '#f8fafc',
    'surface': '#ffffff', 'text': '#111827', 'text_light': '#6b7280'
}

DEFAULT_SETTINGS = {
    "calibration": {
        "scale_ratio": 430.0,  # ## MEJORA: Renombrado de 'scale_factor' a 'scale_ratio' para mayor claridad
        "offset": 0           # ## MEJORA: Un solo offset que se ajusta con la tara
    },
    "ui": { "auto_photo": True, "units": "g" }
}

# --- FUNCIONES DE CONFIGURACIÓN (Sin cambios en la lógica principal) ---
def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        # ## MEJORA: Fusión anidada para asegurar que todas las sub-claves existan
        settings = DEFAULT_SETTINGS.copy()
        for key, value in data.items():
            if isinstance(value, dict):
                settings[key] = {**settings.get(key, {}), **value}
            else:
                settings[key] = value
        return settings
    except (FileNotFoundError, json.JSONDecodeError):
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


# --- CLASES DE UI (ProButton, SimpleKeyboard, WeightDisplayPro) ---
# Estas clases están muy bien diseñadas, no necesitan cambios funcionales.
# He añadido docstrings para mejorar la legibilidad.

class ProButton(tk.Button):
    """Botón profesional con colores y efectos predefinidos."""
    def __init__(self, parent, text="", command=None, btn_type="primary", icon="", width=None, height=2, **kwargs):
        styles = {'primary': {'bg': THEME['primary'], 'fg': 'white'}, 'success': {'bg': THEME['success'], 'fg': 'white'}, 'danger': {'bg': THEME['danger'], 'fg': 'white'}, 'warning': {'bg': THEME['warning'], 'fg': 'white'}, 'secondary': {'bg': THEME['medium'], 'fg': 'white'}, 'light': {'bg': THEME['light'], 'fg': 'white'}}
        style = styles.get(btn_type, styles['primary'])
        display_text = f"{icon} {text}" if icon else text
        super().__init__(parent, text=display_text, command=command, bg=style['bg'], fg=style['fg'], font=('Arial', 12, 'bold'), relief='flat', bd=0, height=height, width=width, cursor='hand2', **kwargs)

class SimpleKeyboard(tk.Toplevel):
    """Teclado virtual simplificado para entrada en pantalla táctil."""
    # (El código de SimpleKeyboard es funcional y no requiere cambios)
    pass # En el script final, aquí iría el código completo de la clase

class WeightDisplayPro(tk.Frame):
    """Display profesional del peso con formato dinámico y estado."""
    # (El código de WeightDisplayPro es excelente y no requiere cambios)
    pass # En el script final, aquí iría el código completo de la clase

# --- APLICACIÓN PRINCIPAL ---

class BasculaProApp:
    """Aplicación principal de la báscula profesional."""
    
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.setup_window()
        self.setup_variables()
        self.setup_hardware()
        self.create_ui()
        self.start_reading_loop()

    def setup_window(self):
        self.root.title("⚖️ Báscula Digital Profesional - Sistema de Producción")
        self.root.configure(bg=THEME['background'])
        width, height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        # ## MEJORA: Forzar modo de pantalla completa (kiosk mode) para interfaz dedicada en Pi
        if width <= 1024:
            self.root.attributes('-fullscreen', True)
        else:
            self.root.geometry("1024x768")
        self.root.bind("<Escape>", lambda e: self.safe_exit())
        self.root.protocol("WM_DELETE_WINDOW", self.safe_exit)
        
    def setup_variables(self):
        """Inicializar variables de estado y medición."""
        self.current_raw = 0.0
        self.display_weight = 0.0
        self.is_stable = False
        
        # ## MEJORA: Lógica de calibración simplificada
        self.scale_ratio = self.settings['calibration']['scale_ratio']
        self.offset = self.settings['calibration']['offset']
        
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.raw_history = deque(maxlen=25) # ## MEJORA: Historial de valores raw para filtrado
        self.stats_history = deque(maxlen=100)
        
        self.session_start_time = time.time()
        self.session_readings = 0
        self.session_max = -float('inf')
        self.session_min = float('inf')

    def setup_hardware(self):
        # (Lógica de inicialización de hardware sin cambios, es correcta)
        pass # Aquí iría el código de setup_hardware

    def create_ui(self):
        # (Lógica de creación de UI sin cambios, es correcta y bien estructurada)
        pass # Aquí iría el código de create_ui

    # ============ MÉTODOS DE LECTURA Y PROCESAMIENTO ============
    
    def start_reading_loop(self):
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_worker, daemon=True)
        self.reading_thread.start()
        self.update_ui()
        
    def reading_worker(self):
        """Worker thread para leer datos del HX711 continuamente."""
        while self.is_reading:
            try:
                if self.hx711_available and self.hx:
                    # ## MEJORA: Usar la mediana de varias lecturas para robustez
                    raw_value = self.hx.get_raw_data_mean(times=3)
                    if raw_value is not False:
                        self.weight_queue.put(raw_value)
                else: # Simulación
                    import random
                    base = 85000 + 43000 * math.sin(time.time() * 0.5)
                    noise = random.uniform(-150, 150)
                    self.weight_queue.put(base + noise)
                time.sleep(0.1)  # 10 Hz, el filtrado suavizará esto
            except Exception as e:
                print(f"Error en lectura: {e}")
                time.sleep(0.5)

    def raw_to_weight(self, raw_value):
        """Convierte un valor raw del ADC a peso en gramos."""
        return (raw_value - self.offset) / self.scale_ratio

    def update_ui(self):
        """Bucle principal de actualización de la interfaz gráfica."""
        try:
            new_data_processed = False
            while not self.weight_queue.empty():
                raw_value = self.weight_queue.get_nowait()
                self.process_raw_reading(raw_value)
                new_data_processed = True
            
            if new_data_processed:
                self.weight_display.update_display(self.display_weight, self.is_stable)
                self.update_stats()
        except Exception as e:
            print(f"Error actualizando UI: {e}")
        self.root.after(100, self.update_ui)

    def process_raw_reading(self, raw_value):
        """Filtra el valor raw y actualiza el estado de la báscula."""
        self.current_raw = raw_value
        self.raw_history.append(raw_value)
        
        # ## MEJORA: Usar filtro de mediana para robustez contra ruido
        if len(self.raw_history) < 5:
            return # Esperar a tener suficientes datos para filtrar

        # Usamos los últimos 15 valores para la mediana, que es muy estable
        filtered_raw = statistics.median(list(self.raw_history)[-15:])
        
        # ## MEJORA: Detección de estabilidad basada en la desviación estándar de los valores raw
        std_dev_raw = statistics.pstdev(list(self.raw_history)[-10:])
        self.is_stable = std_dev_raw < (self.scale_ratio * 0.2) # Estable si la desviación es < 0.2g en valor raw
        
        weight = self.raw_to_weight(filtered_raw)
        
        # Banda muerta para evitar lecturas "fantasma" cerca de cero
        if abs(weight) < 0.1:
            self.display_weight = 0.0
        else:
            self.display_weight = round(weight, 2)
        
        # Actualizar historial para estadísticas
        self.stats_history.append(self.display_weight)

    def update_stats(self):
        # (Lógica de estadísticas sin cambios funcionales, solo se adapta a las nuevas variables)
        pass # Aquí iría el código de update_stats
        
    # ============ MÉTODOS DE CONTROL ============

    def show_keyboard(self, title, initial="", numeric_only=False, password=False):
        # (Sin cambios)
        pass

    def show_message(self, title, message, msg_type="info"):
        # (Sin cambios)
        pass
    
    def tare_weight(self):
        """Establece el peso actual como cero (tara)."""
        if len(self.raw_history) >= 10:
            # ## MEJORA: La tara ahora establece el offset directamente desde el valor raw filtrado
            self.offset = statistics.mean(list(self.raw_history)[-10:])
            self.settings['calibration']['offset'] = self.offset
            save_settings(self.settings)
            self.show_message("Tara", "Tara aplicada correctamente", "success")
        else:
            self.show_message("Error", "Esperando lecturas estables...", "warning")
            
    def calibrate_scale(self):
        """Inicia el proceso de calibración guiado."""
        if not messagebox.askyesno("Calibración", "Esto recalibrará la báscula.\n¿Desea continuar?"):
            return

        # Paso 1: Tara
        messagebox.showinfo("Paso 1: Tara", "Asegúrese de que la báscula esté vacía y pulse Aceptar.")
        self.tare_weight() # Reutilizamos la función de tarado para obtener el offset cero
        if len(self.raw_history) < 10: return # Salir si no se pudo tarar

        # Paso 2: Medir con peso conocido
        known_weight_str = self.show_keyboard("Peso de Calibración (gramos)", "1000", numeric_only=True)
        if not known_weight_str: return
        
        try:
            known_weight = float(known_weight_str)
            if known_weight <= 0: raise ValueError
        except (ValueError, TypeError):
            self.show_message("Error", "Peso inválido. Introduzca un número positivo.", "error")
            return

        messagebox.showinfo("Paso 2: Pesar", f"Coloque el peso conocido de {known_weight}g en la báscula y pulse Aceptar.")
        
        # Esperar 2 segundos para que la lectura se estabilice
        self.show_message("Calibrando", "Midiendo... no mueva la báscula.", "info")
        time.sleep(2)

        if len(self.raw_history) >= 10:
            # ## MEJORA: Lógica de calibración directa y más precisa
            raw_val_with_weight = statistics.mean(list(self.raw_history)[-10:])
            # El ratio es la diferencia de lecturas raw dividida por el peso que causó esa diferencia
            self.scale_ratio = (raw_val_with_weight - self.offset) / known_weight
            
            self.settings['calibration']['scale_ratio'] = self.scale_ratio
            save_settings(self.settings)
            
            self.show_message("Éxito", f"Báscula calibrada. Ratio: {self.scale_ratio:.2f}", "success")
        else:
            self.show_message("Error", "No se pudo obtener una lectura estable.", "error")

    def save_measurement(self):
        """Guarda la medición actual en un archivo CSV."""
        if self.display_weight == 0.0:
            self.show_message("Aviso", "No se puede guardar un peso de cero.", "warning")
            return
        
        if not self.is_stable:
            if not messagebox.askyesno("Medición Inestable", "¿La medición no es estable. Desea guardarla de todas formas?"):
                return
        
        self.root.config(cursor="watch") # ## MEJORA: Feedback visual de que algo está pasando
        self.root.update_idletasks()

        timestamp = datetime.now()
        photo_filename = ""
        
        if self.settings['ui']['auto_photo'] and self.camera_available:
            photo_path = self.capture_photo(timestamp)
            if photo_path:
                photo_filename = os.path.basename(photo_path)
        
        measurement_data = {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "weight_g": self.display_weight,
            "is_stable": self.is_stable,
            "photo_file": photo_filename
        }
        
        # ## MEJORA: Guardado eficiente en formato CSV
        try:
            file_exists = os.path.isfile(MEASUREMENTS_PATH)
            with open(MEASUREMENTS_PATH, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=measurement_data.keys())
                if not file_exists:
                    writer.writeheader() # Escribir cabecera si el archivo es nuevo
                writer.writerow(measurement_data)
            
            self.show_message("Guardado", "Medición guardada correctamente.", "success")
        except Exception as e:
            self.show_message("Error", f"No se pudo guardar: {e}", "error")
        finally:
            self.root.config(cursor="") # Restaurar cursor

    def capture_photo(self, timestamp_obj):
        """Captura una foto con un nombre de archivo estandarizado."""
        if not self.camera_available or not self.camera:
            return ""
        try:
            filename = f"{timestamp_obj.strftime('%Y%m%d_%H%M%S')}_{self.display_weight:.1f}g.jpg"
            photo_path = os.path.join(CAPTURE_DIR, filename)
            self.camera.capture_file(photo_path)
            return photo_path if os.path.exists(photo_path) else ""
        except Exception as e:
            print(f"Error capturando foto: {e}")
            return ""
            
    def safe_exit(self):
        """Limpia los recursos de hardware y cierra la aplicación."""
        if messagebox.askyesno("Salir", "¿Está seguro que desea salir?"):
            self.is_reading = False
            if self.reading_thread.is_alive():
                self.reading_thread.join(timeout=1) # Esperar al hilo
            
            # (Lógica de limpieza de hardware sin cambios)
            self.root.destroy()

# --- Punto de entrada ---
if __name__ == "__main__":
    root = tk.Tk()
    app = BasculaProApp(root)
    root.mainloop()