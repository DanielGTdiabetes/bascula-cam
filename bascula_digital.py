#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Pro (Raspberry Pi Zero 2 W + HX711 + Cámara)
- Filtro robusto: Mediana + IIR (EMA)
- Cero comercial: banda de cero + auto-zero (lento) + display 0.0 dentro de banda
- Estabilidad: σ en ventana, bloqueo/hold al estar estable
- Resolución de display/step
- Cámara opcional (Picamera2): auto-foto al guardar + botón manual
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
import statistics
import math

# ============================
#     CÁMARA (opcional)
# ============================
CAM_AVAILABLE = True
Picamera2 = None
try:
    from picamera2 import Picamera2
    Picamera2  # evitar linter
except Exception:
    CAM_AVAILABLE = False

CAPTURE_DIR = "capturas"

# ============================
#       HX711 - GPIO
# ============================
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


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class BasculaDigital:
    def __init__(self, root):
        self.root = root
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
        self.current_weight_in = 0.0          # entrada (raw->peso)
        self.filtered_weight = 0.0            # peso filtrado (EMA)
        self.display_weight = 0.0             # peso mostrado (con redondeo/hold)
        self.max_weight = float("-inf")
        self.min_weight = float("inf")
        self.tare_offset = 0.0               # en unidades de "raw" transformadas a peso (ver fórmula)
        self.scale_factor = 1.0
        self.is_reading = False
        self.weight_queue = queue.Queue()
        self.readings = deque(maxlen=300)     # historial de pesos mostrados
        self.filtered_hist = deque(maxlen=120)  # historial filtrado (para σ)
        self.median_buf = deque(maxlen=5)     # buffer para mediana (anti picos)
        self.hold_active = False
        self.hold_value = 0.0
        self.last_update_ts = time.time()

        # Config de entrada raw->peso (basado en tus lecturas sin peso ~ -8575)
        self.base_offset = -8575  # offset base (sin tara)
        # Sampling del bucle
        self.update_period = 0.2   # s (5 Hz aprox)

        # ------ “Modo comercial”: parámetros ajustables ------
        self.filter_alpha = 0.15        # EMA (0..1) menor = más suave (más estable)
        self.zero_band = 0.5            # ±g donde se muestra 0.0 y opera auto-zero
        self.auto_zero_rate_gps = 0.05  # g por segundo máx que corrige auto-zero dentro de la banda
        self.display_step = 0.1         # resolución del display (g)
        self.stability_window = 25      # N muestras para σ
        self.stability_sigma = 0.2      # umbral σ (g) para considerar estable
        self.stability_drift = 0.2      # máxima deriva entre min/max en ventana (g)
        self.hold_on_stable = True      # bloquea display mientras estable

        # Cámara
        self.cam = None
        self.camera_ready = False
        self.last_photo_path = ""
        self.auto_photo = True

        # Estados de UI
        self.connection_status = "🔄 Simulación" if not HX711_AVAILABLE else "⏳"

    # ---------- Cámara ----------
    def setup_camera(self):
        os.makedirs(CAPTURE_DIR, exist_ok=True)
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
                print("🔧 Inicializando HX711 (configuración probada)...")
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

        # Estado conexión
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

        # Mini-gráfico (texto de tendencia simple para no depender de libs)
        raw_frame = tk.Frame(self.root, bg="#34495e", relief="raised", bd=1)
        raw_frame.pack(fill=tk.X, padx=10, pady=5)
        self.raw_label = tk.Label(
            raw_frame,
            text="RAW/DBG: filt=-- σ=-- | OFFSET=-- | FACTOR=--",
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

        self.auto_photo_var = tk.BooleanVar(value=self.auto_photo)
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

        row1 = tk.Frame(btn_frame)
        row1.pack(fill=tk.X, pady=2)

        self.tare_btn = tk.Button(
            row1, text="🔄 TARA", command=self.tare, font=("Arial", 12, "bold"), bg="#3498db", fg="white", height=2
        )
        self.tare_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.calibrate_btn = tk.Button(
            row1, text="⚖️ CALIBRAR", command=self.calibrate, font=("Arial", 12, "bold"), bg="#e67e22", fg="white", height=2
        )
        self.calibrate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.save_btn = tk.Button(
            row1, text="💾 GUARDAR", command=self.save_reading, font=("Arial", 12, "bold"), bg="#27ae60", fg="white", height=2
        )
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        row2 = tk.Frame(btn_frame)
        row2.pack(fill=tk.X, pady=2)

        self.reset_btn = tk.Button(
            row2, text="🔄 RESET", command=self.reset_stats, font=("Arial", 12, "bold"), bg="#f39c12", fg="white", height=2
        )
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.raw_btn = tk.Button(
            row2, text="📊 RAW/DBG", command=self.toggle_raw_display, font=("Arial", 12, "bold"), bg="#9b59b6", fg="white", height=2
        )
        self.raw_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.settings_btn = tk.Button(
            row2, text="⚙️ AJUSTES", command=self.open_settings, font=("Arial", 12, "bold"), bg="#2c3e50", fg="white", height=2
        )
        self.settings_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.exit_btn = tk.Button(
            row2, text="🚪 SALIR", command=self.safe_exit, font=("Arial", 12, "bold"), bg="#e74c3c", fg="white", height=2
        )
        self.exit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

    # ---------- Lectura continua ----------
    def start_reading(self):
        self.is_reading = True
        self.reading_thread = threading.Thread(target=self.reading_loop, daemon=True)
        self.reading_thread.start()
        self.root.after(100, self.update_display)

    def _raw_to_weight(self, raw_avg):
        # peso = (raw - base_offset - tare_offset) / scale_factor
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
        """Filtro: mediana corta -> EMA; cero; estabilidad; hold; redondeo; color"""
        now = time.time()
        dt = max(1e-3, now - self.last_update_ts)
        self.last_update_ts = now

        self.current_weight_in = w_in
        # 1) Mediana anti-picos
        self.median_buf.append(w_in)
        w_med = statistics.median(self.median_buf)

        # 2) EMA (IIR) para suavizar
        if not self.filtered_hist:
            self.filtered_weight = w_med
        else:
            alpha = clamp(self.filter_alpha, 0.01, 0.9)
            self.filtered_weight = (1 - alpha) * self.filtered_weight + alpha * w_med

        # 3) Auto-zero (dentro de banda de cero), corrige deriva poco a poco
        if abs(self.filtered_weight) <= self.zero_band:
            # convertir g a “raw-equivalente” para ajustar tare_offset (pero ya trabajamos en g)
            # Aquí ajustamos la tara directamente en g, consistente con _raw_to_weight
            corr = clamp(-self.filtered_weight, -self.auto_zero_rate_gps * dt, self.auto_zero_rate_gps * dt)
            # mover display hacia 0.0 corrigiendo la tara efectiva: sumar en términos de "peso" a la tara
            self.tare_offset -= corr * self.scale_factor  # porque peso = (raw - base - tare)/scale
            self.filtered_weight += corr  # aplica inmediatamente al valor visto

        # 4) Estabilidad -> σ y rango en ventana del filtrado
        self.filtered_hist.append(self.filtered_weight)
        stable = False
        sigma = None
        rng = None
        if len(self.filtered_hist) >= max(5, self.stability_window // 2):
            window = list(self.filtered_hist)[-self.stability_window :]
            if len(window) >= 5:
                try:
                    sigma = statistics.pstdev(window)
                except Exception:
                    sigma = None
                rng = (max(window) - min(window)) if window else None
                if sigma is not None and rng is not None:
                    if sigma <= self.stability_sigma and rng <= self.stability_drift:
                        stable = True

        # 5) Hold de estabilidad
        if self.hold_on_stable and stable:
            if not self.hold_active:
                # activar y memorizar
                self.hold_value = sum(self.filtered_hist[-self.stability_window:]) / min(
                    len(self.filtered_hist), self.stability_window
                )
                self.hold_active = True
        else:
            self.hold_active = False

        # 6) Banda de cero (display “0.0”)
        disp = self.hold_value if self.hold_active else self.filtered_weight
        if abs(disp) <= self.zero_band:
            disp = 0.0

        # 7) Resolución de display (redondeo “comercial”)
        step = max(0.01, self.display_step)
        disp = round(disp / step) * step

        self.display_weight = disp
        self.readings.append(disp)

        # 8) Colores/indicadores
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

        # 9) Extremos
        self.max_weight = max(self.max_weight, disp)
        self.min_weight = min(self.min_weight, disp)

    def _refresh_stats_and_debug(self):
        if len(self.readings) > 0:
            avg = sum(self.readings) / len(self.readings)
            wrange = self.max_weight - self.min_weight
            self.stats_text.configure(
                text=f"Lecturas: {len(self.readings)} | Promedio: {avg:.1f}g | Rango: {wrange:.1f}g"
            )

        # Debug line
        sigma = "-"
        if len(self.filtered_hist) >= 5:
            try:
                sigma_val = statistics.pstdev(list(self.filtered_hist)[-self.stability_window :])
                sigma = f"{sigma_val:.2f}"
            except Exception:
                sigma = "-"
        self.raw_label.configure(
            text=f"DBG: filt={self.filtered_weight:+.2f}g σ={sigma} | OFFSET={(self.base_offset + self.tare_offset):.0f} | FACTOR={self.scale_factor:.3f}"
        )

    # ---------- Acciones ----------
    def tare(self):
        """Tara manual: fuerza 0.0 a partir de las últimas lecturas"""
        # Calcula offset adicional en g y lo traslada a tare_offset (en raw-equivalente)
        recent = list(self.filtered_hist)[-10:] if len(self.filtered_hist) >= 10 else list(self.filtered_hist)
        if recent:
            avg_g = sum(recent) / len(recent)
            self.tare_offset += avg_g * self.scale_factor  # mueve el cero
            self._flash_status("✅ Tara establecida", fg="#2ecc71", ms=1500)

    def calibrate(self):
        """Calibración rápida por peso conocido"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibración")
        dialog.geometry("320x220")
        dialog.configure(bg="#2c3e50")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="⚖️ Calibración Rápida", font=("Arial", 14, "bold"), fg="white", bg="#2c3e50").pack(pady=10)
        tk.Label(
            dialog,
            text="1) TARA sin peso\n2) Coloca peso conocido\n3) Introduce gramos y pulsa Calibrar",
            font=("Arial", 10),
            fg="white",
            bg="#2c3e50",
        ).pack(pady=6)

        fw = tk.Frame(dialog, bg="#2c3e50")
        fw.pack(pady=10)
        tk.Label(fw, text="Peso (g):", fg="white", bg="#2c3e50").pack(side=tk.LEFT)
        ent = tk.Entry(fw, width=8)
        ent.pack(side=tk.LEFT, padx=8)
        ent.insert(0, "1000")

        def do_cal():
            try:
                known = float(ent.get())
                # usar media de últimas lecturas filtradas
                window = list(self.filtered_hist)[-10:] if len(self.filtered_hist) >= 10 else list(self.filtered_hist)
                if len(window) < 3:
                    messagebox.showerror("Error", "Necesito algunas lecturas estables…")
                    return
                avg_f = sum(window) / len(window)
                if abs(avg_f) < 1e-6:
                    messagebox.showerror("Error", "Coloca el peso conocido sobre la báscula.")
                    return
                # scale_new ajusta para que avg_f -> known
                self.scale_factor = self.scale_factor * abs(avg_f / known)
                self._flash_status("✅ Calibrado", fg="#2ecc71", ms=1500)
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Peso inválido")

        tk.Button(dialog, text="Calibrar", command=do_cal, bg="#27ae60", fg="white", font=("Arial", 12)).pack(pady=16)

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
            try:
                with open("mediciones.json", "r") as f:
                    readings = json.load(f)
            except FileNotFoundError:
                readings = []
            readings.append(data)
            with open("mediciones.json", "w") as f:
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

    def open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Ajustes de Filtrado y Estabilidad")
        dlg.geometry("420x360")
        dlg.configure(bg="#2c3e50")
        dlg.transient(self.root)
        dlg.grab_set()

        def add_row(parent, label, var, inc=0.01, fmt="%.2f", minv=None, maxv=None):
            fr = tk.Frame(parent, bg="#2c3e50")
            fr.pack(fill=tk.X, padx=6, pady=4)
            tk.Label(fr, text=label, width=22, anchor="w", fg="white", bg="#2c3e50").pack(side=tk.LEFT)
            ent = tk.Entry(fr, width=10)
            ent.pack(side=tk.LEFT, padx=4)
            ent.insert(0, fmt % var())

            def apply():
                try:
                    val = float(ent.get())
                    if minv is not None: val = max(minv, val)
                    if maxv is not None: val = min(maxv, val)
                    var(val)
                    ent.delete(0, tk.END)
                    ent.insert(0, fmt % val)
                except ValueError:
                    pass

            tk.Button(fr, text="Aplicar", command=apply, bg="#34495e", fg="white").pack(side=tk.LEFT, padx=4)
            return ent

        # Vars “get/set” como closures
        get_alpha = lambda: self.filter_alpha
        set_alpha = lambda v: setattr(self, "filter_alpha", v)
        get_zero = lambda: self.zero_band
        set_zero = lambda v: setattr(self, "zero_band", v)
        get_az = lambda: self.auto_zero_rate_gps
        set_az = lambda v: setattr(self, "auto_zero_rate_gps", v)
        get_step = lambda: self.display_step
        set_step = lambda v: setattr(self, "display_step", v)
        get_win = lambda: float(self.stability_window)
        set_win = lambda v: setattr(self, "stability_window", int(max(5, round(v))))
        get_sig = lambda: self.stability_sigma
        set_sig = lambda v: setattr(self, "stability_sigma", v)
        get_drift = lambda: self.stability_drift
        set_drift = lambda v: setattr(self, "stability_drift", v)

        add_row(dlg, "Alpha (EMA 0.01..0.90)", get_alpha, minv=0.01, maxv=0.90)
        add_row(dlg, "Banda de cero ±g", get_zero, minv=0.0, maxv=5.0)
        add_row(dlg, "Auto-zero g/seg", get_az, minv=0.0, maxv=1.0)
        add_row(dlg, "Paso display (g)", get_step, minv=0.01, maxv=10.0)
        add_row(dlg, "Ventana σ (N)", get_win, fmt="%.0f", minv=5, maxv=200)
        add_row(dlg, "Umbral σ (g)", get_sig, minv=0.01, maxv=5.0)
        add_row(dlg, "Deriva máx (g)", get_drift, minv=0.01, maxv=10.0)

        def preset_soft():
            self.filter_alpha = 0.12
            self.zero_band = 0.5
            self.auto_zero_rate_gps = 0.05
            self.display_step = 0.1
            self.stability_window = 25
            self.stability_sigma = 0.2
            self.stability_drift = 0.2
            self._flash_status("Preset suave aplicado", fg="#2ecc71", ms=1200)

        def preset_ultra():
            self.filter_alpha = 0.08
            self.zero_band = 1.0
            self.auto_zero_rate_gps = 0.03
            self.display_step = 0.1
            self.stability_window = 35
            self.stability_sigma = 0.12
            self.stability_drift = 0.12
            self._flash_status("Preset ULTRA estable", fg="#2ecc71", ms=1200)

        frb = tk.Frame(dlg, bg="#2c3e50")
        frb.pack(pady=10)
        tk.Button(frb, text="Preset suave", command=preset_soft, bg="#27ae60", fg="white").pack(side=tk.LEFT, padx=6)
        tk.Button(frb, text="Preset ULTRA", command=preset_ultra, bg="#16a085", fg="white").pack(side=tk.LEFT, padx=6)

        tk.Button(dlg, text="Cerrar", command=dlg.destroy, bg="#e74c3c", fg="white").pack(pady=8)

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
