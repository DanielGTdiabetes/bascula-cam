#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Profesional - Interfaz Industrial
Diseño moderno y profesional para entornos de producción
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
from typing import Optional, Callable

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont

# Colores del tema profesional
COLORS = {
    'primary': '#1e3a8a',      # Azul profesional
    'primary_light': '#3b82f6', # Azul claro
    'secondary': '#059669',     # Verde éxito
    'danger': '#dc2626',       # Rojo error
    'warning': '#d97706',      # Naranja advertencia
    'dark': '#1f2937',         # Gris oscuro
    'medium': '#374151',       # Gris medio
    'light': '#6b7280',        # Gris claro
    'background': '#f9fafb',   # Fondo principal
    'surface': '#ffffff',      # Superficie
    'text_primary': '#111827', # Texto principal
    'text_secondary': '#6b7280', # Texto secundario
    'accent': '#8b5cf6',       # Morado acento
    'success_bg': '#d1fae5',   # Fondo éxito
    'error_bg': '#fee2e2',     # Fondo error
}

class ModernButton(tk.Button):
    """Botón moderno con efectos hover y estados"""
    def __init__(self, parent, text="", command=None, style="primary", size="medium", icon="", **kwargs):
        
        # Estilos predefinidos
        styles = {
            'primary': {'bg': COLORS['primary'], 'fg': 'white', 'active_bg': COLORS['primary_light']},
            'success': {'bg': COLORS['secondary'], 'fg': 'white', 'active_bg': '#047857'},
            'danger': {'bg': COLORS['danger'], 'fg': 'white', 'active_bg': '#b91c1c'},
            'warning': {'bg': COLORS['warning'], 'fg': 'white', 'active_bg': '#b45309'},
            'secondary': {'bg': COLORS['medium'], 'fg': 'white', 'active_bg': COLORS['light']},
            'outline': {'bg': COLORS['surface'], 'fg': COLORS['primary'], 'active_bg': COLORS['background']}
        }
        
        sizes = {
            'small': {'font': ('Segoe UI', 10, 'bold'), 'padx': 12, 'pady': 6},
            'medium': {'font': ('Segoe UI', 12, 'bold'), 'padx': 16, 'pady': 10},
            'large': {'font': ('Segoe UI', 14, 'bold'), 'padx': 20, 'pady': 12},
            'xl': {'font': ('Segoe UI', 16, 'bold'), 'padx': 24, 'pady': 16}
        }
        
        current_style = styles.get(style, styles['primary'])
        current_size = sizes.get(size, sizes['medium'])
        
        # Texto con icono si se proporciona
        display_text = f"{icon} {text}".strip()
        
        super().__init__(
            parent,
            text=display_text,
            command=command,
            bg=current_style['bg'],
            fg=current_style['fg'],
            font=current_size['font'],
            relief='flat',
            bd=0,
            cursor='hand2',
            padx=current_size['padx'],
            pady=current_size['pady'],
            **kwargs
        )
        
        self.default_bg = current_style['bg']
        self.active_bg = current_style['active_bg']
        
        # Efectos hover
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        
    def _on_hover(self, event):
        self.configure(bg=self.active_bg)
        
    def _on_leave(self, event):
        self.configure(bg=self.default_bg)
        
    def _on_click(self, event):
        self.configure(bg=self.default_bg)
        self.after(100, lambda: self.configure(bg=self.active_bg))

class ProfessionalKeyboard(tk.Toplevel):
    """Teclado en pantalla profesional y táctil"""
    
    def __init__(self, master, title="Introducir texto", initial="", 
                 keyboard_type="alphanumeric", password=False, callback=None):
        super().__init__(master)
        
        self.title(title)
        self.configure(bg=COLORS['background'])
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        
        self.result = None
        self.password = password
        self.callback = callback
        self.caps_lock = False
        self.keyboard_type = keyboard_type
        
        # Centrar ventana
        self.geometry("900x600")
        self.center_window()
        
        self.create_keyboard_ui(initial)
        self.entry_field.focus_set()
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"900x600+{x}+{y}")
        
    def create_keyboard_ui(self, initial_text):
        # Header
        header = tk.Frame(self, bg=COLORS['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(header, text=self.title, font=('Segoe UI', 16, 'bold'),
                bg=COLORS['surface'], fg=COLORS['text_primary']).pack(pady=15)
        
        # Campo de entrada
        entry_frame = tk.Frame(self, bg=COLORS['background'])
        entry_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.text_var = tk.StringVar(value=initial_text)
        self.entry_field = tk.Entry(
            entry_frame,
            textvariable=self.text_var,
            font=('Segoe UI', 18),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            relief='solid',
            bd=2,
            justify='left',
            show='•' if self.password else ''
        )
        self.entry_field.pack(fill=tk.X, ipady=12)
        
        # Teclado
        keyboard_frame = tk.Frame(self, bg=COLORS['background'])
        keyboard_frame.pack(fill=tk.BOTH, expand=True, padx=20)
        
        if self.keyboard_type == "numeric":
            self.create_numeric_keyboard(keyboard_frame)
        else:
            self.create_alphanumeric_keyboard(keyboard_frame)
        
        # Botones de control
        self.create_control_buttons()
        
    def create_alphanumeric_keyboard(self, parent):
        # Layout QWERTY
        rows = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '='],
            ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'"],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/']
        ]
        
        for i, row in enumerate(rows):
            row_frame = tk.Frame(parent, bg=COLORS['background'])
            row_frame.pack(fill=tk.X, pady=2)
            
            # Espaciado especial para la fila de letras
            if i >= 1:
                tk.Frame(row_frame, bg=COLORS['background'], width=30).pack(side=tk.LEFT)
            
            for key in row:
                btn = tk.Button(
                    row_frame,
                    text=key.upper() if self.caps_lock and key.isalpha() else key,
                    command=lambda k=key: self.insert_char(k),
                    font=('Segoe UI', 12, 'bold'),
                    bg=COLORS['surface'],
                    fg=COLORS['text_primary'],
                    relief='solid',
                    bd=1,
                    width=4,
                    height=2,
                    cursor='hand2'
                )
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                self.bind_key_effects(btn)
        
        # Fila especial con teclas de función
        special_frame = tk.Frame(parent, bg=COLORS['background'])
        special_frame.pack(fill=tk.X, pady=5)
        
        # Caps Lock
        caps_btn = tk.Button(
            special_frame,
            text="⇪ MAYÚS",
            command=self.toggle_caps,
            font=('Segoe UI', 11, 'bold'),
            bg=COLORS['warning'] if self.caps_lock else COLORS['medium'],
            fg='white',
            relief='solid',
            bd=1,
            width=8,
            height=2,
            cursor='hand2'
        )
        caps_btn.pack(side=tk.LEFT, padx=2)
        self.caps_button = caps_btn
        
        # Espacio
        space_btn = tk.Button(
            special_frame,
            text="ESPACIO",
            command=lambda: self.insert_char(' '),
            font=('Segoe UI', 12, 'bold'),
            bg=COLORS['medium'],
            fg='white',
            relief='solid',
            bd=1,
            width=30,
            height=2,
            cursor='hand2'
        )
        space_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.bind_key_effects(space_btn)
        
        # Backspace
        back_btn = tk.Button(
            special_frame,
            text="⌫ BORRAR",
            command=self.backspace,
            font=('Segoe UI', 11, 'bold'),
            bg=COLORS['danger'],
            fg='white',
            relief='solid',
            bd=1,
            width=10,
            height=2,
            cursor='hand2'
        )
        back_btn.pack(side=tk.RIGHT, padx=2)
        self.bind_key_effects(back_btn)
        
    def create_numeric_keyboard(self, parent):
        # Teclado numérico 3x4 más profesional
        numbers = [
            ['7', '8', '9'],
            ['4', '5', '6'],
            ['1', '2', '3'],
            ['0', '.', '⌫']
        ]
        
        grid_frame = tk.Frame(parent, bg=COLORS['background'])
        grid_frame.pack(expand=True, fill=tk.BOTH, padx=50, pady=30)
        
        for row_idx, row in enumerate(numbers):
            for col_idx, key in enumerate(row):
                if key == '⌫':
                    btn = tk.Button(
                        grid_frame,
                        text=key,
                        command=self.backspace,
                        font=('Segoe UI', 20, 'bold'),
                        bg=COLORS['danger'],
                        fg='white',
                        relief='solid',
                        bd=2,
                        cursor='hand2'
                    )
                elif key == '.':
                    btn = tk.Button(
                        grid_frame,
                        text=key,
                        command=lambda k=key: self.insert_char(k),
                        font=('Segoe UI', 24, 'bold'),
                        bg=COLORS['warning'],
                        fg='white',
                        relief='solid',
                        bd=2,
                        cursor='hand2'
                    )
                else:
                    btn = tk.Button(
                        grid_frame,
                        text=key,
                        command=lambda k=key: self.insert_char(k),
                        font=('Segoe UI', 24, 'bold'),
                        bg=COLORS['surface'],
                        fg=COLORS['text_primary'],
                        relief='solid',
                        bd=2,
                        cursor='hand2'
                    )
                
                btn.grid(row=row_idx, column=col_idx, sticky='nsew', padx=5, pady=5)
                self.bind_key_effects(btn)
        
        # Configurar grid weights para expansión uniforme
        for i in range(4):
            grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(3):
            grid_frame.grid_columnconfigure(i, weight=1)
    
    def bind_key_effects(self, button):
        """Efectos visuales para las teclas"""
        original_bg = button.cget('bg')
        
        def on_press(event):
            button.configure(bg=COLORS['primary_light'])
            
        def on_release(event):
            button.configure(bg=original_bg)
            
        button.bind('<Button-1>', on_press)
        button.bind('<ButtonRelease-1>', on_release)
        
    def create_control_buttons(self):
        control_frame = tk.Frame(self, bg=COLORS['background'])
        control_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Limpiar
        ModernButton(
            control_frame, 
            text="LIMPIAR", 
            command=self.clear_text,
            style="warning",
            size="large",
            icon="🗑"
        ).pack(side=tk.LEFT, padx=10)
        
        # Cancelar
        ModernButton(
            control_frame, 
            text="CANCELAR", 
            command=self.cancel,
            style="secondary",
            size="large",
            icon="✖"
        ).pack(side=tk.LEFT, padx=10)
        
        # Aceptar
        ModernButton(
            control_frame, 
            text="ACEPTAR", 
            command=self.accept,
            style="success",
            size="large",
            icon="✓"
        ).pack(side=tk.RIGHT, padx=10)
        
        # Bind teclas
        self.bind('<Return>', lambda e: self.accept())
        self.bind('<Escape>', lambda e: self.cancel())
        
    def insert_char(self, char):
        if self.caps_lock and char.isalpha():
            char = char.upper()
        
        cursor_pos = self.entry_field.index(tk.INSERT)
        current_text = self.text_var.get()
        new_text = current_text[:cursor_pos] + char + current_text[cursor_pos:]
        self.text_var.set(new_text)
        self.entry_field.icursor(cursor_pos + 1)
        
    def backspace(self):
        cursor_pos = self.entry_field.index(tk.INSERT)
        if cursor_pos > 0:
            current_text = self.text_var.get()
            new_text = current_text[:cursor_pos-1] + current_text[cursor_pos:]
            self.text_var.set(new_text)
            self.entry_field.icursor(cursor_pos - 1)
            
    def clear_text(self):
        self.text_var.set("")
        self.entry_field.icursor(0)
        
    def toggle_caps(self):
        self.caps_lock = not self.caps_lock
        color = COLORS['warning'] if self.caps_lock else COLORS['medium']
        self.caps_button.configure(bg=color)
        
    def accept(self):
        self.result = self.text_var.get()
        if self.callback:
            self.callback(self.result)
        self.destroy()
        
    def cancel(self):
        self.result = None
        if self.callback:
            self.callback(None)
        self.destroy()

class StatusIndicator(tk.Frame):
    """Indicador de estado con colores y animaciones"""
    def __init__(self, parent, text="", status="inactive"):
        super().__init__(parent, bg=COLORS['background'])
        
        self.status_colors = {
            'active': COLORS['secondary'],
            'inactive': COLORS['light'],
            'error': COLORS['danger'],
            'warning': COLORS['warning']
        }
        
        self.indicator = tk.Label(
            self, 
            text="●", 
            font=('Segoe UI', 16, 'bold'),
            bg=COLORS['background'],
            fg=self.status_colors['inactive']
        )
        self.indicator.pack(side=tk.LEFT, padx=(0, 8))
        
        self.label = tk.Label(
            self,
            text=text,
            font=('Segoe UI', 11),
            bg=COLORS['background'],
            fg=COLORS['text_secondary']
        )
        self.label.pack(side=tk.LEFT)
        
        self.set_status(status)
        
    def set_status(self, status, text=None):
        if text:
            self.label.configure(text=text)
        self.indicator.configure(fg=self.status_colors.get(status, self.status_colors['inactive']))
        
    def pulse(self, duration=2000):
        """Efecto de pulsación para llamar la atención"""
        def animate():
            current_color = self.indicator.cget('fg')
            self.indicator.configure(fg=COLORS['primary_light'])
            self.after(200, lambda: self.indicator.configure(fg=current_color))
            
        animate()
        if duration > 500:
            self.after(500, lambda: self.pulse(duration - 500))

class WeightDisplay(tk.Frame):
    """Display principal del peso con diseño profesional"""
    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['surface'], relief='solid', bd=2)
        
        # Frame principal con padding
        main_frame = tk.Frame(self, bg=COLORS['surface'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # Display del peso
        self.weight_label = tk.Label(
            main_frame,
            text="0.000",
            font=('Segoe UI', 72, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary']
        )
        self.weight_label.pack()
        
        # Frame inferior con unidad y estado
        bottom_frame = tk.Frame(main_frame, bg=COLORS['surface'])
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.unit_label = tk.Label(
            bottom_frame,
            text="GRAMOS",
            font=('Segoe UI', 16, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['primary']
        )
        self.unit_label.pack(side=tk.LEFT)
        
        # Indicador de estabilidad
        self.stability_indicator = StatusIndicator(bottom_frame, "En medición", "active")
        self.stability_indicator.pack(side=tk.RIGHT)
        
    def update_weight(self, weight, stable=False, unit="g"):
        # Formatear peso según magnitud
        if abs(weight) >= 1000:
            display_text = f"{weight:.1f}"
        elif abs(weight) >= 10:
            display_text = f"{weight:.2f}"
        else:
            display_text = f"{weight:.3f}"
            
        self.weight_label.configure(text=display_text)
        
        # Color según el peso
        if abs(weight) < 0.1:
            color = COLORS['light']
        elif weight < 0:
            color = COLORS['danger']
        elif weight > 5000:
            color = COLORS['warning']
        else:
            color = COLORS['text_primary']
            
        self.weight_label.configure(fg=color)
        
        # Estado de estabilidad
        if stable:
            self.stability_indicator.set_status("active", "🔒 ESTABLE")
        else:
            self.stability_indicator.set_status("warning", "📊 Midiendo...")

class BasculaProfessional:
    """Aplicación principal con diseño profesional"""
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.create_professional_ui()
        # Aquí irían las funciones de inicialización de cámara y HX711
        self.start_demo_mode()  # Para demostración
        
    def setup_window(self):
        self.root.title("⚖️ Báscula Digital Profesional - Sistema de Producción")
        self.root.geometry("1024x768")
        self.root.configure(bg=COLORS['background'])
        self.root.state('zoomed')  # Maximizar en Windows/Linux
        
        # Configurar fuentes por defecto
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)
        
    def setup_variables(self):
        self.current_weight = 0.0
        self.is_stable = False
        self.connection_status = "Conectado"
        self.demo_weight = 0.0
        
    def create_professional_ui(self):
        # Header principal
        self.create_header()
        
        # Área principal dividida
        main_container = tk.Frame(self.root, bg=COLORS['background'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Panel izquierdo - Display principal
        left_panel = tk.Frame(main_container, bg=COLORS['background'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.weight_display = WeightDisplay(left_panel)
        self.weight_display.pack(fill=tk.BOTH, expand=True)
        
        # Panel derecho - Controles y estadísticas
        right_panel = tk.Frame(main_container, bg=COLORS['background'], width=350)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False)
        
        self.create_control_panel(right_panel)
        self.create_stats_panel(right_panel)
        
        # Footer con información adicional
        self.create_footer()
        
    def create_header(self):
        header = tk.Frame(self.root, bg=COLORS['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        # Título principal
        title_frame = tk.Frame(header, bg=COLORS['surface'])
        title_frame.pack(fill=tk.X, padx=20, pady=15)
        
        tk.Label(
            title_frame,
            text="⚖️ BÁSCULA DIGITAL PROFESIONAL",
            font=('Segoe UI', 24, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['primary']
        ).pack(side=tk.LEFT)
        
        # Indicadores de estado
        status_frame = tk.Frame(title_frame, bg=COLORS['surface'])
        status_frame.pack(side=tk.RIGHT)
        
        self.connection_indicator = StatusIndicator(status_frame, "Sistema conectado", "active")
        self.connection_indicator.pack(pady=2)
        
        self.camera_indicator = StatusIndicator(status_frame, "Cámara lista", "active")
        self.camera_indicator.pack(pady=2)
        
    def create_control_panel(self, parent):
        # Panel de control principal
        control_panel = tk.LabelFrame(
            parent,
            text="  🎛️ CONTROLES PRINCIPALES  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            relief='solid',
            bd=2,
            padx=20,
            pady=15
        )
        control_panel.pack(fill=tk.X, pady=(0, 15))
        
        # Botones principales en grid 2x2
        button_frame = tk.Frame(control_panel, bg=COLORS['surface'])
        button_frame.pack(fill=tk.X, pady=10)
        
        # Fila 1
        ModernButton(
            button_frame,
            text="TARA",
            command=self.tare_weight,
            style="primary",
            size="xl",
            icon="🔄",
            width=12
        ).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        
        ModernButton(
            button_frame,
            text="CALIBRAR",
            command=self.calibrate_scale,
            style="warning",
            size="xl",
            icon="⚙️",
            width=12
        ).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Fila 2
        ModernButton(
            button_frame,
            text="GUARDAR",
            command=self.save_measurement,
            style="success",
            size="xl",
            icon="💾",
            width=12
        ).grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        
        ModernButton(
            button_frame,
            text="FOTO",
            command=self.take_photo,
            style="secondary",
            size="xl",
            icon="📷",
            width=12
        ).grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        
        # Panel de acciones secundarias
        secondary_panel = tk.Frame(control_panel, bg=COLORS['surface'])
        secondary_panel.pack(fill=tk.X, pady=(15, 5))
        
        ModernButton(
            secondary_panel,
            text="AJUSTES",
            command=self.open_settings,
            style="outline",
            size="medium",
            icon="⚙️"
        ).pack(side=tk.LEFT, padx=5)
        
        ModernButton(
            secondary_panel,
            text="RESET",
            command=self.reset_system,
            style="outline",
            size="medium",
            icon="🔄"
        ).pack(side=tk.LEFT, padx=5)
        
        ModernButton(
            secondary_panel,
            text="SALIR",
            command=self.safe_exit,
            style="danger",
            size="medium",
            icon="🚪"
        ).pack(side=tk.RIGHT, padx=5)
    
    def create_stats_panel(self, parent):
        # Panel de estadísticas
        stats_panel = tk.LabelFrame(
            parent,
            text="  📊 ESTADÍSTICAS DE SESIÓN  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            relief='solid',
            bd=2,
            padx=20,
            pady=15
        )
        stats_panel.pack(fill=tk.BOTH, expand=True)
        
        # Grid de estadísticas
        stats_grid = tk.Frame(stats_panel, bg=COLORS['surface'])
        stats_grid.pack(fill=tk.X, pady=10)
        
        # Crear estadísticas con valores
        stats = [
            ("Mediciones:", "156"),
            ("Promedio:", "245.6g"),
            ("Máximo:", "1.245kg"),
            ("Mínimo:", "12.3g"),
            ("Precisión:", "±0.1g"),
            ("Uptime:", "04:23:15")
        ]
        
        for i, (label, value) in enumerate(stats):
            row = i // 2
            col = (i % 2) * 2
            
            tk.Label(
                stats_grid,
                text=label,
                font=('Segoe UI', 11),
                bg=COLORS['surface'],
                fg=COLORS['text_secondary'],
                anchor='w'
            ).grid(row=row, column=col, sticky='w', padx=(0, 10), pady=5)
            
            tk.Label(
                stats_grid,
                text=value,
                font=('Segoe UI', 11, 'bold'),
                bg=COLORS['surface'],
                fg=COLORS['text_primary'],
                anchor='e'
            ).grid(row=row, column=col+1, sticky='e', pady=5)
        
        # Configurar columnas
        for i in range(4):
            stats_grid.grid_columnconfigure(i, weight=1)
            
    def create_footer(self):
        footer = tk.Frame(self.root, bg=COLORS['surface'], relief='solid', bd=1)
        footer.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        footer_content = tk.Frame(footer, bg=COLORS['surface'])
        footer_content.pack(fill=tk.X, padx=20, pady=10)
        
        # Información del sistema
        tk.Label(
            footer_content,
            text="Sistema: Raspberry Pi Zero 2W • Sensor: HX711 • Cámara: Module 3",
            font=('Segoe UI', 9),
            bg=COLORS['surface'],
            fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)
        
        # Timestamp
        self.timestamp_label = tk.Label(
            footer_content,
            text=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            font=('Segoe UI', 9),
            bg=COLORS['surface'],
            fg=COLORS['text_secondary']
        )
        self.timestamp_label.pack(side=tk.RIGHT)
        
        # Actualizar timestamp cada segundo
        self.update_timestamp()
    
    def update_timestamp(self):
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.timestamp_label.configure(text=current_time)
        self.root.after(1000, self.update_timestamp)
    
    # Métodos de la aplicación
    def start_demo_mode(self):
        """Modo demo con simulación de peso"""
        self.demo_running = True
        self.demo_loop()
    
    def demo_loop(self):
        """Simula lecturas de peso para demostración"""
        if not hasattr(self, 'demo_running') or not self.demo_running:
            return
            
        import random
        import math
        
        # Simular peso variable
        time_factor = time.time() * 0.5
        base_weight = 500 + 200 * math.sin(time_factor)
        noise = random.uniform(-2, 2)
        self.demo_weight = max(0, base_weight + noise)
        
        # Simular estabilidad
        self.is_stable = random.random() > 0.7
        
        # Actualizar display
        self.weight_display.update_weight(self.demo_weight, self.is_stable)
        
        # Continuar demo
        self.root.after(200, self.demo_loop)
    
    def show_keyboard(self, title="Introducir texto", initial="", 
                     keyboard_type="alphanumeric", password=False):
        """Mostrar teclado profesional"""
        result = [None]  # Usar lista para capturar resultado
        
        def on_result(value):
            result[0] = value
        
        keyboard = ProfessionalKeyboard(
            self.root, 
            title=title,
            initial=initial,
            keyboard_type=keyboard_type,
            password=password,
            callback=on_result
        )
        
        self.root.wait_window(keyboard)
        return result[0]
    
    def tare_weight(self):
        """Función de tara"""
        self.show_status_message("Tara aplicada correctamente", "success")
        self.connection_indicator.pulse()
    
    def calibrate_scale(self):
        """Función de calibración"""
        weight = self.show_keyboard(
            title="Peso de Calibración (gramos)",
            initial="1000",
            keyboard_type="numeric"
        )
        
        if weight:
            try:
                cal_weight = float(weight)
                self.show_status_message(f"Calibración con {cal_weight}g completada", "success")
            except ValueError:
                self.show_status_message("Peso inválido", "error")
    
    def save_measurement(self):
        """Guardar medición"""
        # Simulación de guardado
        measurement_data = {
            "weight": self.demo_weight,
            "timestamp": datetime.now().isoformat(),
            "stable": self.is_stable
        }
        
        # Aquí iría la lógica real de guardado
        self.show_status_message("Medición guardada correctamente", "success")
        
        # Simular captura de foto automática
        if hasattr(self, 'auto_photo') and self.auto_photo:
            self.root.after(500, lambda: self.show_status_message("📷 Foto capturada", "success"))
    
    def take_photo(self):
        """Capturar foto manual"""
        self.show_status_message("📷 Capturando foto...", "warning")
        # Simular tiempo de captura
        self.root.after(1000, lambda: self.show_status_message("📷 Foto guardada", "success"))
        self.camera_indicator.pulse()
    
    def open_settings(self):
        """Abrir panel de configuración"""
        SettingsDialog(self.root, self)
    
    def reset_system(self):
        """Reset del sistema"""
        if messagebox.askyesno("Confirmar Reset", 
                              "¿Está seguro de que desea resetear el sistema?\n\nSe perderán las estadísticas actuales."):
            self.show_status_message("Sistema reseteado", "warning")
            # Aquí iría la lógica de reset
    
    def safe_exit(self):
        """Salida segura"""
        if messagebox.askyesno("Confirmar Salida", 
                              "¿Está seguro de que desea salir del sistema?"):
            self.demo_running = False
            self.root.quit()
    
    def show_status_message(self, message, msg_type="info"):
        """Mostrar mensaje de estado temporal"""
        colors = {
            'success': COLORS['secondary'],
            'error': COLORS['danger'],
            'warning': COLORS['warning'],
            'info': COLORS['primary']
        }
        
        # Crear overlay temporal
        overlay = tk.Toplevel(self.root)
        overlay.title("")
        overlay.configure(bg=colors[msg_type])
        overlay.overrideredirect(True)
        overlay.resizable(False, False)
        
        # Centrar en pantalla
        overlay.geometry("400x80")
        overlay.update_idletasks()
        x = (overlay.winfo_screenwidth() // 2) - 200
        y = (overlay.winfo_screenheight() // 2) - 40
        overlay.geometry(f"400x80+{x}+{y}")
        
        # Mensaje
        tk.Label(
            overlay,
            text=message,
            font=('Segoe UI', 14, 'bold'),
            bg=colors[msg_type],
            fg='white'
        ).pack(expand=True, fill=tk.BOTH)
        
        # Auto-cerrar después de 2 segundos
        overlay.after(2000, overlay.destroy)
        
        # Traer al frente
        overlay.lift()
        overlay.attributes('-topmost', True)

class SettingsDialog(tk.Toplevel):
    """Diálogo de configuración profesional"""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.title("⚙️ Configuración del Sistema")
        self.geometry("800x600")
        self.configure(bg=COLORS['background'])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        
        # Centrar ventana
        self.center_window()
        self.create_settings_ui()
        
    def center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 400
        y = (self.winfo_screenheight() // 2) - 300
        self.geometry(f"800x600+{x}+{y}")
    
    def create_settings_ui(self):
        # Header
        header = tk.Frame(self, bg=COLORS['surface'], relief='solid', bd=1)
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        tk.Label(
            header,
            text="⚙️ CONFIGURACIÓN DEL SISTEMA",
            font=('Segoe UI', 20, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['primary']
        ).pack(pady=20)
        
        # Notebook para pestañas
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Pestaña de Conexión
        conn_frame = tk.Frame(notebook, bg=COLORS['background'])
        notebook.add(conn_frame, text="  🔗 Conexión  ")
        self.create_connection_tab(conn_frame)
        
        # Pestaña de Calibración
        cal_frame = tk.Frame(notebook, bg=COLORS['background'])
        notebook.add(cal_frame, text="  ⚖️ Calibración  ")
        self.create_calibration_tab(cal_frame)
        
        # Pestaña de Sistema
        sys_frame = tk.Frame(notebook, bg=COLORS['background'])
        notebook.add(sys_frame, text="  🖥️ Sistema  ")
        self.create_system_tab(sys_frame)
        
        # Botones de control
        button_frame = tk.Frame(self, bg=COLORS['background'])
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ModernButton(
            button_frame,
            text="GUARDAR CONFIGURACIÓN",
            command=self.save_settings,
            style="success",
            size="large",
            icon="💾"
        ).pack(side=tk.LEFT, padx=10)
        
        ModernButton(
            button_frame,
            text="CERRAR",
            command=self.destroy,
            style="secondary",
            size="large",
            icon="✖"
        ).pack(side=tk.RIGHT, padx=10)
    
    def create_connection_tab(self, parent):
        # Wi-Fi Settings
        wifi_frame = tk.LabelFrame(
            parent,
            text="  📶 Configuración Wi-Fi  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        wifi_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # SSID
        tk.Label(wifi_frame, text="Red Wi-Fi (SSID):", font=('Segoe UI', 12),
                bg=COLORS['surface'], fg=COLORS['text_primary']).pack(anchor='w', pady=(0, 5))
        
        ssid_frame = tk.Frame(wifi_frame, bg=COLORS['surface'])
        ssid_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.ssid_var = tk.StringVar(value="MiRed_WiFi")
        ssid_entry = tk.Entry(ssid_frame, textvariable=self.ssid_var, font=('Segoe UI', 12),
                             bg='white', fg=COLORS['text_primary'], relief='solid', bd=1, state='readonly')
        ssid_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        ModernButton(
            ssid_frame,
            text="EDITAR",
            command=lambda: self.edit_wifi_setting('ssid'),
            style="outline",
            size="small"
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Password
        tk.Label(wifi_frame, text="Contraseña:", font=('Segoe UI', 12),
                bg=COLORS['surface'], fg=COLORS['text_primary']).pack(anchor='w', pady=(0, 5))
        
        pass_frame = tk.Frame(wifi_frame, bg=COLORS['surface'])
        pass_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.pass_var = tk.StringVar(value="••••••••••")
        pass_entry = tk.Entry(pass_frame, textvariable=self.pass_var, font=('Segoe UI', 12),
                             bg='white', fg=COLORS['text_primary'], relief='solid', bd=1, 
                             state='readonly', show='•')
        pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        ModernButton(
            pass_frame,
            text="EDITAR",
            command=lambda: self.edit_wifi_setting('password'),
            style="outline",
            size="small"
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        # API Settings
        api_frame = tk.LabelFrame(
            parent,
            text="  🔐 Configuración API  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        api_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(api_frame, text="API Key:", font=('Segoe UI', 12),
                bg=COLORS['surface'], fg=COLORS['text_primary']).pack(anchor='w', pady=(0, 5))
        
        api_frame_inner = tk.Frame(api_frame, bg=COLORS['surface'])
        api_frame_inner.pack(fill=tk.X)
        
        self.api_var = tk.StringVar(value="sk-•••••••••••••••••••••••••••••••")
        api_entry = tk.Entry(api_frame_inner, textvariable=self.api_var, font=('Segoe UI', 12),
                           bg='white', fg=COLORS['text_primary'], relief='solid', bd=1, 
                           state='readonly', show='•')
        api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        ModernButton(
            api_frame_inner,
            text="CONFIGURAR",
            command=self.configure_api,
            style="outline",
            size="small"
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
    def create_calibration_tab(self, parent):
        # Calibración actual
        current_frame = tk.LabelFrame(
            parent,
            text="  📊 Calibración Actual  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        current_frame.pack(fill=tk.X, padx=20, pady=20)
        
        cal_info = [
            ("Factor de escala:", "1247.3"),
            ("Offset de tara:", "-8575"),
            ("Precisión:", "±0.1g"),
            ("Última calibración:", "25/08/2025 14:30")
        ]
        
        for label, value in cal_info:
            row = tk.Frame(current_frame, bg=COLORS['surface'])
            row.pack(fill=tk.X, pady=5)
            
            tk.Label(row, text=label, font=('Segoe UI', 12),
                    bg=COLORS['surface'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)
            
            tk.Label(row, text=value, font=('Segoe UI', 12, 'bold'),
                    bg=COLORS['surface'], fg=COLORS['text_primary']).pack(side=tk.RIGHT)
        
        # Acciones de calibración
        actions_frame = tk.LabelFrame(
            parent,
            text="  🔧 Acciones de Calibración  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        actions_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ModernButton(
            actions_frame,
            text="CALIBRACIÓN RÁPIDA",
            command=self.quick_calibration,
            style="primary",
            size="large",
            icon="⚡"
        ).pack(fill=tk.X, pady=5)
        
        ModernButton(
            actions_frame,
            text="CALIBRACIÓN AVANZADA",
            command=self.advanced_calibration,
            style="warning",
            size="large",
            icon="🔬"
        ).pack(fill=tk.X, pady=5)
        
        ModernButton(
            actions_frame,
            text="RESTAURAR VALORES POR DEFECTO",
            command=self.reset_calibration,
            style="danger",
            size="large",
            icon="🔄"
        ).pack(fill=tk.X, pady=5)
        
    def create_system_tab(self, parent):
        # Información del sistema
        info_frame = tk.LabelFrame(
            parent,
            text="  🖥️ Información del Sistema  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        info_frame.pack(fill=tk.X, padx=20, pady=20)
        
        system_info = [
            ("Modelo:", "Raspberry Pi Zero 2 W"),
            ("Sistema operativo:", "Raspberry Pi OS Lite"),
            ("Versión Python:", "3.11.2"),
            ("Sensor de peso:", "HX711 - Activo"),
            ("Cámara:", "Module 3 - Conectada"),
            ("Memoria libre:", "1.2 GB / 512 MB"),
            ("Temperatura CPU:", "42.3°C")
        ]
        
        for label, value in system_info:
            row = tk.Frame(info_frame, bg=COLORS['surface'])
            row.pack(fill=tk.X, pady=3)
            
            tk.Label(row, text=label, font=('Segoe UI', 11),
                    bg=COLORS['surface'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)
            
            tk.Label(row, text=value, font=('Segoe UI', 11, 'bold'),
                    bg=COLORS['surface'], fg=COLORS['text_primary']).pack(side=tk.RIGHT)
        
        # Mantenimiento
        maintenance_frame = tk.LabelFrame(
            parent,
            text="  🔧 Mantenimiento  ",
            font=('Segoe UI', 14, 'bold'),
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            padx=20,
            pady=20
        )
        maintenance_frame.pack(fill=tk.X, padx=20, pady=20)
        
        maint_buttons = tk.Frame(maintenance_frame, bg=COLORS['surface'])
        maint_buttons.pack(fill=tk.X)
        
        ModernButton(
            maint_buttons,
            text="DIAGNÓSTICO",
            command=self.run_diagnostics,
            style="primary",
            size="medium",
            icon="🔍"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ModernButton(
            maint_buttons,
            text="EXPORTAR DATOS",
            command=self.export_data,
            style="secondary",
            size="medium",
            icon="📤"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ModernButton(
            maint_buttons,
            text="REINICIAR",
            command=self.restart_system,
            style="danger",
            size="medium",
            icon="🔄"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
    
    # Métodos de configuración
    def edit_wifi_setting(self, setting_type):
        if setting_type == 'ssid':
            result = self.app.show_keyboard(
                title="Configurar Red Wi-Fi",
                initial=self.ssid_var.get(),
                keyboard_type="alphanumeric"
            )
            if result:
                self.ssid_var.set(result)
        else:  # password
            result = self.app.show_keyboard(
                title="Contraseña Wi-Fi",
                initial="",
                keyboard_type="alphanumeric",
                password=True
            )
            if result:
                self.pass_var.set("•" * len(result))
    
    def configure_api(self):
        result = self.app.show_keyboard(
            title="Configurar API Key",
            initial="",
            keyboard_type="alphanumeric",
            password=True
        )
        if result and len(result) > 10:
            self.api_var.set(f"sk-{'•' * (len(result) - 10)}")
            self.app.show_status_message("API Key configurada", "success")
    
    def quick_calibration(self):
        weight = self.app.show_keyboard(
            title="Peso de Calibración (gramos)",
            initial="1000",
            keyboard_type="numeric"
        )
        if weight:
            self.app.show_status_message(f"Calibración rápida con {weight}g iniciada", "success")
    
    def advanced_calibration(self):
        self.app.show_status_message("Modo de calibración avanzada activado", "warning")
    
    def reset_calibration(self):
        if messagebox.askyesno("Confirmar", "¿Restaurar calibración por defecto?"):
            self.app.show_status_message("Calibración restaurada", "success")
    
    def run_diagnostics(self):
        self.app.show_status_message("Ejecutando diagnóstico del sistema...", "warning")
    
    def export_data(self):
        self.app.show_status_message("Exportando datos del sistema...", "success")
    
    def restart_system(self):
        if messagebox.askyesno("Confirmar Reinicio", "¿Reiniciar el sistema?"):
            self.app.show_status_message("Reiniciando sistema...", "danger")
    
    def save_settings(self):
        self.app.show_status_message("Configuración guardada correctamente", "success")
        self.destroy()

def main():
    """Función principal"""
    root = tk.Tk()
    app = BasculaProfessional(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación cerrada por el usuario")
    except Exception as e:
        print(f"Error en la aplicación: {e}")
    finally:
        try:
            root.quit()
        except:
            pass

if __name__ == "__main__":
    main()