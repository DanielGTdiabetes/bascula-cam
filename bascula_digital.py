#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Pro (Raspberry Pi Zero 2 W + HX711 + Cámara + Teclado en pantalla)
- Filtro robusto tipo "comercial": Mediana + EMA (IIR), banda de cero, auto-zero, estabilidad y hold
- Teclado NUMÉRICO grande integrado (calibración, cantidades)
- Teclado ALFANUMÉRICO integrado (Wi-Fi SSID/Password, API Key)
- Ajustes: API Key (guardar/validar stub), Wi-Fi (captura de credenciales; integración nmcli pendiente),
           Perfil (placeholder), Exportar (placeholder), Diagnóstico (HX711/Cámara)
- Cámara (opcional) con Picamera2: foto al guardar y botón manual
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

# --------------------------
#     Carpetas y rutas
# --------------------------
BASE_DIR = os.path.expanduser("~/bascula-cam")
CAPTURE_DIR = os.path.join(BASE_DIR, "capturas")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

for d in (CAPTURE_DIR, DATA_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

# --------------------------
#     Cámara (opcional)
# --------------------------
CAM_AVAILABLE = True
Picamera2 = None
try:
    from picamera2 import Picamera2
    Picamera2  # quiet linters
except Exception:
    CAM_AVAILABLE = False

# --------------------------
#     HX711 / GPIO
# --------------------------
try:
    import RPi.GPIO as GPIO
    from hx711 import HX711
    HX711_AVAILABLE = True
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("✅ HX711 disponible y funcionando")
except Exception:
    HX711_AVAILABLE = False
    print("❌ HX711 no disponible (modo simulación)")

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# --------------------------
#   Utilidades de ajustes
# --------------------------
DEFAULT_SETTINGS = {
    "api_key": "",
    "wifi_ssid": "",
    "wifi_password": "",
    "diabetes_profile": {
        "icr": 10.0,            # g/U
        "isf": 50.0,            # mg/dL por U
        "target_bg": 110.0,     # mg/dL
        "show_insulin": False,
        "dose_step": 0.5
    },
    "ui": {
        "locale": "es",
        "units": "g"
    }
}

def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        # merge con defaults (por si añadimos campos)
        def deep_merge(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                r = dict(a)
                for k, v in b.items():
                    r[k] = deep_merge(r.get(k), v)
                return r
            return b if b is not None else a
        return deep_merge(DEFAULT_SETTINGS, data)
    except FileNotFoundError:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print("⚠️ Error leyendo settings:", e)
        return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    try:
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, SETTINGS_PATH)
        # permisos 600
        os.chmod(SETTINGS_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        print("⚠️ Error guardando settings:", e)

# --------------------------
#   Teclado en pantalla
# --------------------------
class OnScreenKeyboard(tk.Toplevel):
    """
    Teclado alfanumérico grande con:
    - filas QWERTY
    - Shift (mayúsculas)
    - Numeración y signos básicos
    - Modo password opcional (oculta texto)
    """
    def __init__(self, master, title="Introducir texto", initial="", password=False):
        super().__init__(master)
        self.title(title)
        self.configure(bg="#2c3e50")
        self.geometry("780x420")
        self.transient(master)
        self.grab_set()

        self.password = password
        self.value = initial
        self.caps = False

        top = tk.Frame(self, bg="#2c3e50")
        top.pack(fill=tk.X, padx=10, pady=10)

        self.var = tk.StringVar(value=initial)
        self.entry = tk.Entry(top, textvariable=self.var, font=("Arial", 22), justify="left", show="*" if password else "")
        self.entry.pack(fill=tk.X, padx=5, pady=5)
        self.entry.focus_set()
        self.entry.icursor(tk.END)

        body = tk.Frame(self, bg="#2c3e50")
        body.pack(padx=8, pady=8)

        # Layout de teclas
        rows = [
            list("1234567890-_."),
            list("qwertyuiop"),
            list("asdfghjkl"),
            list("zxcvbnm"),
        ]

        btn_style = dict(font=("Arial", 18, "bold"), bg="#34495e", fg="white", width=4, height=2)

        # Fila números
        row0 = tk.Frame(body, bg="#2c3e50"); row0.pack()
        for ch in rows[0]:
            tk.Button(row0, text=ch, command=lambda c=ch: self.put(c), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(row0, text="←", command=self.backspace, **btn_style).pack(side=tk.LEFT, padx=4, pady=4)

        # Fila 1
        row1 = tk.Frame(body, bg="#2c3e50"); row1.pack()
        for ch in rows[1]:
            tk.Button(row1, text=ch, command=lambda c=ch: self.put(c), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)

        # Fila 2 + Enter
        row2 = tk.Frame(body, bg="#2c3e50"); row2.pack()
        for ch in rows[2]:
            tk.Button(row2, text=ch, command=lambda c=ch: self.put(c), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(row2, text="Esp", command=lambda: self.put(" "), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)

        # Fila 3 + Shift
        row3 = tk.Frame(body, bg="#2c3e50"); row3.pack()
        tk.Button(row3, text="Shift", command=self.toggle_shift, **btn_style).pack(side=tk.LEFT, padx=4, pady=4)
        for ch in rows[3]:
            tk.Button(row3, text=ch, command=lambda c=ch: self.put(c), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(row3, text=".", command=lambda: self.put("."), **btn_style).pack(side=tk.LEFT, padx=4, pady=4)

        # Controles
        bottom = tk.Frame(self, bg="#2c3e50"); bottom.pack(pady=8)
        tk.Button(bottom, text="Borrar", command=self.clear, font=("Arial", 18, "bold"), bg="#e67e22", fg="white", width=8, height=2).pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="Cancelar", command=self.cancel, font=("Arial", 18, "bold"), bg="#95a5a6", fg="white", width=8, height=2).pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="OK", command=self.ok, font=("Arial", 18, "bold"), bg="#27ae60", fg="white", width=10, height=2).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())

    def put(self, ch):
        if self.caps and ch.isalpha():
            ch = ch.upper()
        self.entry.insert(tk.END, ch)

    def backspace(self):
        val = self.var.get()
        if len(val) > 0:
            self.var.set(val[:-1])

    def clear(self):
        self.var.set("")

    def toggle_shift(self):
        self.caps = not self.caps

    def ok(self):
        self.value = self.var.get()
        self.destroy()

    def cancel(self):
        self.value = None
        self.destroy()

class NumpadDialog(tk.Toplevel):
    """Teclado numérico grande (0-9, punto, borrar, C, OK/Cancel)."""
    def __init__(self, master, title="Introducir número", initial="1000"):
        super().__init__(master)
        self.title(title)
        self.configure(bg="#2c3e50")
        self.geometry("360x460")
        self.transient(master)
        self.grab_set()

        self.var = tk.StringVar(value=str(initial))

        e = tk.Entry(self, font=("Arial", 24), justify="right", textvariable=self.var)
        e.pack(fill=tk.X, padx=12, pady=12)
        e.focus_set()
        e.icursor(tk.END)

        grid = tk.Frame(self, bg="#2c3e50"); grid.pack(padx=8, pady=8)
        keys = [
            "7","8","9",
            "4","5","6",
            "1","2","3",
            "0",".","←"
        ]
        btn_style = dict(font=("Arial", 22, "bold"), bg="#34495e", fg="white", width=4, height=2)
        for i, k in enumerate(keys):
            if k == "←":
                cmd = self.backspace
            elif k == ".":
                cmd = lambda c=".": self.put(c)
            else:
                cmd = lambda c=k: self.put(c)
            tk.Button(grid, text=k, command=cmd, **btn_style).grid(row=i//3, column=i%3, padx=6, pady=6)

        bottom = tk.Frame(self, bg="#2c3e50"); bottom.pack(pady=6)
        tk.Button(bottom, text="C", command=self.clear, font=("Arial", 18, "bold"), bg="#e67e22", fg="white", width=6, height=2).pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="Cancelar", command=self.cancel, font=("Arial", 18, "bold"), bg="#95a5a6", fg="white", width=8, height=2).pack(side=tk.LEFT, padx=8)
        tk.Button(bottom, text="OK", command=self.ok, font=("Arial", 18, "bold"), bg="#27ae60", fg="white", width=10, height=2).pack(side=tk.LEFT, padx=8)

        self.value = None
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())

    def put(self, txt):
        self.var.set(self.var.get() + txt)

    def backspace(self):
        val = self.var.get()
        self.var.set(val[:-1])

    def clear(self):
        self.var.set("")

    def ok(self):
        self.value = self.var.get()
        self.destroy()

    def cancel(self):
        self.value = None
        self.destroy()

# --------------------------
#      Aplicación GUI
# --------------------------
class BasculaDigital:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.setup_window()
        self.setup_variables()
        self.setup_camera()
        self.setup_hx711()
        self.create_widgets()
        self.start_reading()

    # ---------- Ventana ----------
    def setup_window(self):
        self.root.title("🏭 Báscula Digital Pro - HX711")
        self.root.geometry("800x480")
        self.root.configure(bg="#1a1a1a")
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.root.bind("<Escape>", lambda e: self.safe_exit())

    # ---------- Variables ----------
    def setup_variables(self):
        # Estado general
        self.current_weight_in = 0.0
        self.filtered_weight = 0.0
        self.display_weight = 0.0
        self.max_weight = float("-inf")
        self.min_weight = float("inf")
        self.tare_offset = 0.0
        self.scale_factor = 1.0
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.readings = deque(maxlen=300)
        self.filtered_hist = deque(maxlen=120)
        self.median_buf = deque(maxlen=5)
        self.hold_active = False
        self.hold_value = 0.0
        self.last_update_ts = time.time()

        # Conversión raw->peso
        self.base_offset = -8575  # tu media sin peso
        self.update_period = 0.2  # s

        # Parámetros de “báscula comercial”
        self.filter_alpha = 0.15
        self.zero_band = 0.5
        self.auto_zero_rate_gps = 0.05
        self.display_step = 0.1
        self.stability_window = 25
        self.stability_sigma = 0.2
        self.stability_drift = 0.2
        self.hold_on_stable = True

        # Cámara
        self.cam = None
        self.camera_ready = False
        self.last_photo_path = ""
        self.auto_photo = True

        # Estado conexión
        self.connection_status = "🔄 Simulación" if not HX711_AVAILABLE else "⏳"

    # ---------- Cámara ----------
    def setup_camera(self):
        if not CAM_AVAILABLE:
            print("ℹ️ Cámara no disponible (python3-picamera2 no instalado)")
            self.camera_ready = False
            return
        try:
            self.cam = Picamera2()
            self.cam.configure(self.cam.create_still_configuration())
            self.cam.start()
            time.sleep(0.2)
            self.camera_ready = True
            print("📷 Cámara lista (Picamera2)")
        except Exception as e:
            print(f"⚠️ No se pudo iniciar la cámara: {e}")
            self.cam = None
            self.camera_ready = False

    # ---------- HX711 ----------
    def setup_hx711(self):
        if HX711_AVAILABLE:
            try:
                print("🔧 Inicializando HX711...")
                self.hx = HX711(dout_pin=5, pd_sck_pin=6, channel="A", gain=64)
                self.hx.reset()
                time.sleep(2)
                print("✅ HX711 inicializado correctamente")
                self.connection_status = "✅ Conectado"
            except Exception as e:
                print(f"❌ Error HX711: {e}")
                self.hx = None
                self.connection_status = f"❌ {str(e)[:20]}"
        else:
            self.hx = None
            self.connection_status = "🔄 Simulación"

    # ---------- UI ----------
    def create_widgets(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=5)

        title = tk.Label(
            header,
            text="🏭 BÁSCULA DIGITAL HX711",
            font=("Arial", 20, "bold"),
            fg="white",
            bg="#1a1a1a",
        )
        title.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            header, text=self.connection_status, font=("Arial", 12), fg="#2ecc71", bg="#1a1a1a"
        )
        self.status_label.pack(side=tk.RIGHT)

        # Display principal
        display_frame = tk.Frame(self.root, bg="#2c3e50", relief="raised", bd=2)
        display_frame.pack(fill=tk.X, padx=10, pady=10)

        self.weight_display = tk.Label(
            display_frame,
            text="0.0",
            font=("Courier New", 64, "bold"),
            fg="#2ecc71",
            bg="#2c3e50",
        )
        self.weight_display.pack(pady=5)

        unit_row = tk.Frame(display_frame, bg="#2c3e50")
        unit_row.pack()
        self.unit_label = tk.Label(
            unit_row, text="gramos", font=("Arial", 16), fg="#3498db", bg="#2c3e50"
        )
        self.unit_label.pack(side=tk.LEFT, padx=6)

        self.stable_label = tk.Label(
            unit_row, text="•", font=("Arial", 16, "bold"), fg="#7f8c8d", bg="#2c3e50"
        )
        self.stable_label.pack(side=tk.LEFT, padx=8)

        # Estadísticas
        stats_frame = tk.Frame(self.root, bg="#34495e", relief="raised", bd=1)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        self.stats_text = tk.Label(
            stats_frame,
            text="Lecturas: 0 | Promedio: 0.0g | Rango: 0.0g",
            font=("Arial", 11),
            fg="white",
            bg="#34495e",
        )
        self.stats_text.pack(pady=6)

        # Botones control
        self.create_control_buttons()

        # Debug line
        raw_frame = tk.Frame(self.root, bg="#34495e", relief="raised", bd=1)
        raw_frame.pack(fill=tk.X, padx=10, pady=5)
        self.raw_label = tk.Label(
            raw_frame,
            text="DBG: filt=-- σ=-- | OFFSET=-- | FACTOR=--",
            font=("Courier New", 10),
            fg="#bdc3c7",
            bg="#34495e",
        )
        self.raw_label.pack(pady=5)

        # Cámara + controles
        cam_frame = tk.Frame(self.root, bg="#1a1a1a")
        cam_frame.pack(fill=tk.X, padx=10, pady=4)

        cam_state = "📷 Cámara lista" if self.camera_ready else "📷 Cámara no disponible"
        self.camera_label = tk.Label(
            cam_frame,
            text=cam_state,
            font=("Arial", 10),
            fg=("#2ecc71" if self.camera_ready else "#f39c12"),
            bg="#1a1a1a",
        )
        self.camera_label.pack(side=tk.LEFT)

        self.auto_photo_var = tk.BooleanVar(value=True)
        self.auto_check = tk.Checkbutton(
            cam_frame,
            text="📸 Auto-foto al GUARDAR",
            variable=self.auto_photo_var,
            onvalue=True,
            offvalue=False,
            bg="#1a1a1a",
            fg="white",
            selectcolor="#1a1a1a",
            activebackground="#1a1a1a",
            activeforeground="white",
            command=self.toggle_auto_photo,
        )
        self.auto_check.pack(side=tk.LEFT, padx=12)

        self.photo_btn = tk.Button(
            cam_frame, text="📷 FOTO", command=self.take_photo_now, font=("Arial", 11, "bold"), bg="#16a085", fg="white", height=1
        )
        self.photo_btn.pack(side=tk.RIGHT)

        self.last_photo_label = tk.Label(
            self.root, text="Última foto: —", font=("Arial", 9), fg="#bdc3c7", bg="#1a1a1a"
        )
        self.last_photo_label.pack(fill=tk.X, padx=10)

    def create_control_buttons(self):
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        row1 = tk.Frame(btn_frame); row1.pack(fill=tk.X, pady=2)
        self.tare_btn = tk.Button(row1, text="🔄 TARA", command=self.tare, font=("Arial", 12, "bold"), bg="#3498db", fg="white", height=2)
        self.tare_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.calibrate_btn = tk.Button(row1, text="⚖️ CALIBRAR", command=self.calibrate, font=("Arial", 12, "bold"), bg="#e67e22", fg="white", height=2)
        self.calibrate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.save_btn = tk.Button(row1, text="💾 GUARDAR", command=self.save_reading, font=("Arial", 12, "bold"), bg="#27ae60", fg="white", height=2)
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        row2 = tk.Frame(btn_frame); row2.pack(fill=tk.X, pady=2)
        self.reset_btn = tk.Button(row2, text="🔄 RESET", command=self.reset_stats, font=("Arial", 12, "bold"), bg="#f39c12", fg="white", height=2)
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.raw_btn = tk.Button(row2, text="📊 RAW/DBG", command=self.toggle_raw_display, font=("Arial", 12, "bold"), bg="#9b59b6", fg="white", height=2)
        self.raw_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.settings_btn = tk.Button(row2, text="⚙️ AJUSTES", command=self.open_settings, font=("Arial", 12, "bold"), bg="#2c3e50", fg="white", height=2)
        self.settings_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.exit_btn = tk.Button(row2, text="🚪 SALIR", command=self.safe_exit, font=("Arial", 12, "bold"), bg="#e74c3c", fg="white", height=2)
        self.exit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    # ---------- Lectura continua ----------
    def start_reading(self):
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
        self.reading_thread.start()
        self.root.after(100, self.update_display)

    def _raw_to_weight(self, raw_avg):
        return (raw_avg - self.base_offset - self.tare_offset) / self.scale_factor

    def reading_loop(self):
        while self.is_reading:
            try:
                if self.hx and HX711_AVAILABLE:
                    raw_data = self.hx.get_raw_data(times=3)
                    if raw_data:
                        valid = [x for x in raw_data if x is not None]
                        if valid:
                            raw_avg = sum(valid) / len(valid)
                            w = self._raw_to_weight(raw_avg)
                        else:
                            w = None
                    else:
                        w = None
                else:
                    # Simulación
                    import random
                    raw_sim = -8575 + random.randint(-15, 15)
                    w = self._raw_to_weight(raw_sim)

                if w is not None:
                    self.weight_queue.put(w)

                time.sleep(self.update_period)
            except Exception as e:
                print(f"Error lectura: {e}")
                time.sleep(0.5)

    # ---------- Procesado / Display ----------
    def update_display(self):
        try:
            updated = False
            while not self.weight_queue.empty():
                w_in = self.weight_queue.get_nowait()
                self.process_reading(w_in)
                updated = True

            if updated:
                self._refresh_stats_and_debug()

            self.root.after(100, self.update_display)

        except Exception as e:
            print(f"Error actualización display: {e}")
            self.root.after(100, self.update_display)

    def process_reading(self, w_in):
        now = time.time()
        dt = max(1e-3, now - self.last_update_ts)
        self.last_update_ts = now

        self.current_weight_in = w_in
        # 1) Mediana
        self.median_buf.append(w_in)
        w_med = statistics.median(self.median_buf)
        # 2) EMA
        if not self.filtered_hist:
            self.filtered_weight = w_med
        else:
            alpha = clamp(self.filter_alpha, 0.01, 0.9)
            self.filtered_weight = (1 - alpha) * self.filtered_weight + alpha * w_med
        # 3) Auto-zero dentro de banda
        if abs(self.filtered_weight) <= self.zero_band:
            corr = clamp(-self.filtered_weight, -self.auto_zero_rate_gps * dt, self.auto_zero_rate_gps * dt)
            self.tare_offset -= corr * self.scale_factor
            self.filtered_weight += corr
        # 4) Estabilidad
        self.filtered_hist.append(self.filtered_weight)
        stable = False
        sigma = None
        rng = None
        if len(self.filtered_hist) >= max(5, self.stability_window // 2):
            window = list(self.filtered_hist)[-self.stability_window:]
            if len(window) >= 5:
                try:
                    sigma = statistics.pstdev(window)
                except Exception:
                    sigma = None
                rng = (max(window) - min(window)) if window else None
                if sigma is not None and rng is not None:
                    if sigma <= self.stability_sigma and rng <= self.stability_drift:
                        stable = True
        # 5) Hold
        if self.hold_on_stable and stable:
            if not self.hold_active:
                window_hold = list(self.filtered_hist)[-self.stability_window:]
                self.hold_value = sum(window_hold) / (len(window_hold) or 1)  
                
                self.hold_active = True
        else:
            self.hold_active = False
        # 6) Banda de cero en display
        disp = self.hold_value if self.hold_active else self.filtered_weight
        if abs(disp) <= self.zero_band:
            disp = 0.0
        # 7) Paso display
        step = max(0.01, self.display_step)
        disp = round(disp / step) * step

        self.display_weight = disp
        self.readings.append(disp)

        # Indicadores
        if self.hold_active:
            self.stable_label.configure(text="🔒 ESTABLE", fg="#2ecc71")
        else:
            self.stable_label.configure(text="•", fg="#7f8c8d")

        color = "#2ecc71"
        if abs(disp) < self.zero_band:
            color = "#95a5a6"
        elif disp > 5000:
            color = "#e74c3c"
        self.weight_display.configure(text=f"{disp:.1f}", fg=color)

        self.max_weight = max(self.max_weight, disp)
        self.min_weight = min(self.min_weight, disp)

    def _refresh_stats_and_debug(self):
        if len(self.readings) > 0:
            avg = sum(self.readings) / len(self.readings)
            wrange = self.max_weight - self.min_weight
            self.stats_text.configure(text=f"Lecturas: {len(self.readings)} | Promedio: {avg:.1f}g | Rango: {wrange:.1f}g")
        sigma = "-"
        if len(self.filtered_hist) >= 5:
            try:
                sigma_val = statistics.pstdev(list(self.filtered_hist)[-self.stability_window:])
                sigma = f"{sigma_val:.2f}"
            except Exception:
                sigma = "-"
        self.raw_label.configure(text=f"DBG: filt={self.filtered_weight:+.2f}g σ={sigma} | OFFSET={(self.base_offset + self.tare_offset):.0f} | FACTOR={self.scale_factor:.3f}")

    # ---------- Acciones ----------
    def tare(self):
        recent = list(self.filtered_hist)[-10:] if len(self.filtered_hist) >= 10 else list(self.filtered_hist)
        if recent:
            avg_g = sum(recent) / len(recent)
            self.tare_offset += avg_g * self.scale_factor
            self._flash_status("✅ Tara establecida", fg="#2ecc71", ms=1500)

    def calibrate(self):
        # 1) Preguntar peso conocido con NUMPAD
        dlg = NumpadDialog(self.root, title="Peso conocido (g)", initial="1000")
        self.root.wait_window(dlg)
        val = dlg.value
        if val is None:
            return
        try:
            known = float(str(val).replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Número inválido")
            return

        # 2) Usar media del filtrado reciente
        window = list(self.filtered_hist)[-10:] if len(self.filtered_hist) >= 10 else list(self.filtered_hist)
        if len(window) < 3:
            messagebox.showerror("Error", "Necesito algunas lecturas estables…")
            return
        avg_f = sum(window) / len(window)
        if abs(avg_f) < 1e-6:
            messagebox.showerror("Error", "Coloca el peso conocido sobre la báscula.")
            return

        self.scale_factor = self.scale_factor * abs(avg_f / known)
        self._flash_status("✅ Calibrado", fg="#2ecc71", ms=1500)

    def toggle_raw_display(self):
        current = self.raw_label.cget("fg")
        self.raw_label.configure(fg="#f39c12" if current == "#bdc3c7" else "#bdc3c7")

    def _flash_status(self, text, fg="#2ecc71", ms=2300):
        self.status_label.configure(text=text, fg=fg)
        self.root.after(ms, lambda: self.status_label.configure(text=self.connection_status, fg="#2ecc71"))

    # ----- Cámara -----
    def toggle_auto_photo(self):
        self.auto_photo = bool(self.auto_photo_var.get())
        txt = "Auto-foto ACTIVADA" if self.auto_photo else "Auto-foto DESACTIVADA"
        self._flash_status(txt, fg=("#2ecc71" if self.auto_photo else "#f39c12"), ms=1500)

    def _capture_photo(self, weight_g: float) -> str:
        if not self.camera_ready or self.cam is None:
            return ""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{ts}_{weight_g:.1f}g.jpg"
            path = os.path.join(CAPTURE_DIR, fname)
            self.cam.capture_file(path)
            self.last_photo_path = path
            self.last_photo_label.configure(text=f"Última foto: {path}")
            print("📸 Foto guardada ->", path)
            return path
        except Exception as e:
            print(f"⚠️ Error capturando foto: {e}")
            return ""

    def take_photo_now(self):
        if not self.camera_ready:
            self._flash_status("📷 Cámara no disponible", fg="#f39c12", ms=1600)
            return
        path = self._capture_photo(self.display_weight)
        if path:
            self._flash_status("📷 Foto capturada", fg="#2ecc71", ms=1400)
        else:
            self._flash_status("⚠️ No se pudo capturar", fg="#e67e22", ms=1600)

    # ----- Guardado -----
    def save_reading(self):
        data = {
            "timestamp": datetime.now().isoformat(),
            "weight": round(self.display_weight, 2),
            "unit": "gramos",
            "stable": self.hold_active,
        }
        photo_path = ""
        if self.auto_photo and self.camera_ready:
            photo_path = self._capture_photo(self.display_weight)
            if photo_path:
                data["photo"] = photo_path

        try:
            path = os.path.join(BASE_DIR, "mediciones.json")
            try:
                with open(path, "r") as f:
                    readings = json.load(f)
            except FileNotFoundError:
                readings = []
            readings.append(data)
            with open(path, "w") as f:
                json.dump(readings, f, indent=2)

            saved_n = len(readings)
            if photo_path:
                self.status_label.configure(text=f"💾 Guardado #{saved_n} + 📷", fg="#f39c12")
            else:
                if self.auto_photo and self.camera_ready:
                    self.status_label.configure(text=f"💾 Guardado #{saved_n} (⚠️ sin foto)", fg="#f39c12")
                else:
                    self.status_label.configure(text=f"💾 Guardado #{saved_n}", fg="#f39c12")

            self.root.after(2500, lambda: self.status_label.configure(text=self.connection_status, fg="#2ecc71"))
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando: {e}")

    def reset_stats(self):
        self.readings.clear()
        self.filtered_hist.clear()
        self.median_buf.clear()
        self.max_weight = float("-inf")
        self.min_weight = float("inf")
        self.hold_active = False
        self.hold_value = 0.0
        self.stats_text.configure(text="Lecturas: 0 | Promedio: 0.0g | Rango: 0.0g")
        self._flash_status("🔄 Reset completado", fg="#f39c12", ms=1500)

    # ---------- Ajustes (con teclados) ----------
    def open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Ajustes")
        dlg.geometry("520x420")
        dlg.configure(bg="#2c3e50")
        dlg.transient(self.root)
        dlg.grab_set()

        def btn(parent, text, cmd, bg="#34495e"):
            return tk.Button(parent, text=text, command=cmd, font=("Arial", 14, "bold"), bg=bg, fg="white", height=2)

        tk.Label(dlg, text="Ajustes del sistema", font=("Arial", 18, "bold"), fg="white", bg="#2c3e50").pack(pady=10)

        fr = tk.Frame(dlg, bg="#2c3e50"); fr.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        btn(fr, "🔑 API Key (OpenAI)", self._settings_api_key).pack(fill=tk.X, pady=6)
        btn(fr, "📶 Wi-Fi (SSID y Password)", self._settings_wifi).pack(fill=tk.X, pady=6)
        btn(fr, "👤 Perfil diabetes (ICR/ISF)", self._settings_profile).pack(fill=tk.X, pady=6)
        btn(fr, "📤 Exportar datos", self._settings_export).pack(fill=tk.X, pady=6)
        btn(fr, "🩺 Diagnóstico", self._settings_diag).pack(fill=tk.X, pady=6)

        tk.Button(dlg, text="Cerrar", command=dlg.destroy, font=("Arial", 12, "bold"), bg="#e74c3c", fg="white").pack(pady=10)

    def _settings_api_key(self):
        # entrada con teclado alfanumérico (oculto tipo password)
        kb = OnScreenKeyboard(self.root, title="Introducir API Key", initial=self.settings.get("api_key", ""), password=True)
        self.root.wait_window(kb)
        val = kb.value
        if val is None:
            return
        # Guardar
        self.settings["api_key"] = val.strip()
        save_settings(self.settings)
        self._flash_status("🔑 API Key guardada", fg="#2ecc71", ms=1500)
        # Validación *stub* (aquí solo indicamos OK; en Fase 2 haremos ping real)
        messagebox.showinfo("Validación", "Conectividad pendiente de activar en la Fase 2 (vision_client).")

    def _settings_wifi(self):
        # Pedir SSID y Password con teclados
        kb1 = OnScreenKeyboard(self.root, title="Wi-Fi SSID", initial=self.settings.get("wifi_ssid", ""), password=False)
        self.root.wait_window(kb1)
        ssid = kb1.value
        if ssid is None:
            return
        kb2 = OnScreenKeyboard(self.root, title="Wi-Fi Password", initial=self.settings.get("wifi_password", ""), password=True)
        self.root.wait_window(kb2)
        pwd = kb2.value
        if pwd is None:
            return

        self.settings["wifi_ssid"] = ssid.strip()
        self.settings["wifi_password"] = pwd.strip()
        save_settings(self.settings)
        self._flash_status("📶 Wi-Fi credenciales guardadas", fg="#2ecc71", ms=1800)

        # NOTA: integración con nmcli/nmtui se hará en una función separada (próxima fase)
        messagebox.showinfo("Wi-Fi", "Credenciales guardadas. Conexión automática vía sistema se integrará en la siguiente fase.")

    def _settings_profile(self):
        # Placeholder rápido con numpad
        prof = self.settings.get("diabetes_profile", {}).copy()

        # ICR
        dlg1 = NumpadDialog(self.root, title="ICR (g/U)", initial=str(prof.get("icr", 10.0)))
        self.root.wait_window(dlg1)
        v1 = dlg1.value
        if v1 is None: return
        try: prof["icr"] = float(str(v1).replace(",", "."))
        except: pass

        # ISF
        dlg2 = NumpadDialog(self.root, title="ISF (mg/dL por U)", initial=str(prof.get("isf", 50.0)))
        self.root.wait_window(dlg2)
        v2 = dlg2.value
        if v2 is None: return
        try: prof["isf"] = float(str(v2).replace(",", "."))
        except: pass

        # target BG
        dlg3 = NumpadDialog(self.root, title="Objetivo glucémico (mg/dL)", initial=str(prof.get("target_bg", 110.0)))
        self.root.wait_window(dlg3)
        v3 = dlg3.value
        if v3 is None: return
        try: prof["target_bg"] = float(str(v3).replace(",", "."))
        except: pass

        # show_insulin toggle rápido
        ans = messagebox.askyesno("Sugerencia de insulina", "¿Mostrar sugerencia (no es consejo médico)?")
        prof["show_insulin"] = bool(ans)

        self.settings["diabetes_profile"] = prof
        save_settings(self.settings)
        self._flash_status("👤 Perfil guardado", fg="#2ecc71", ms=1500)

    def _settings_export(self):
        try:
            # Exportación simple de mediciones.json a CSV
            src = os.path.join(BASE_DIR, "mediciones.json")
            if not os.path.exists(src):
                messagebox.showwarning("Exportar", "No hay mediciones para exportar.")
                return
            with open(src, "r") as f:
                data = json.load(f)
            out = os.path.join(BASE_DIR, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            import csv
            with open(out, "w", newline="") as csvfile:
                w = csv.writer(csvfile)
                w.writerow(["timestamp", "weight_g", "unit", "stable", "photo"])
                for row in data:
                    w.writerow([row.get("timestamp",""), row.get("weight",""), row.get("unit",""), row.get("stable",""), row.get("photo","")])
            self._flash_status("📤 Exportado CSV", fg="#2ecc71", ms=1500)
            messagebox.showinfo("Exportar", f"Archivo exportado:\n{out}")
        except Exception as e:
            messagebox.showerror("Exportar", f"Error: {e}")

    def _settings_diag(self):
        cam = "OK" if self.camera_ready else "No disponible"
        hx = "OK" if (self.hx is not None and HX711_AVAILABLE) else "No disponible"
        info = f"""Diagnóstico:
- HX711: {hx}
- Cámara: {cam}
- Lecturas en memoria: {len(self.readings)}
- API Key: {"configurada" if self.settings.get("api_key") else "no configurada"}
- Wi-Fi SSID guardado: {self.settings.get("wifi_ssid") or "—"}
"""
        messagebox.showinfo("Diagnóstico", info)

    # ---------- Salida segura ----------
    def safe_exit(self):
        self.is_reading = False
        try:
            if HX711_AVAILABLE:
                GPIO.cleanup()
        except:
            pass
        try:
            if self.cam is not None:
                self.cam.close()
        except:
            pass
        self.root.quit()


def main():
    root = tk.Tk()
    app = BasculaDigital(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación cerrada")
        app.safe_exit()


if __name__ == "__main__":
    main()
