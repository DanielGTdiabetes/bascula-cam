#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital HX711 - GUI + Headless
Base: tu GUI funcional (con lecturas ~ -8575)
Mejoras:
- Config persistente en bascula_config.json (pines, canal, ganancia, refresco)
- Calibración persistente en calibracion.json (offset + factor escala)
- Filtro de ruido: mediana + EMA
- Tara estable basada en crudo + persistencia temporal por sesión
- Logging JSON y CSV (mediciones.json / mediciones.csv)
- Detección headless (sin DISPLAY): modo terminal interactivo
- Limpieza segura de GPIO e hilos
- Botones táctiles: Tara, Calibrar, Guardar, Reset, Raw Toggle, Salir
- Mini-gráfico con Canvas (tendencia últimas lecturas)

Requisitos:
- Python 3.11 (Raspberry Pi OS Bookworm)
- Paquetes: RPi.GPIO, hx711 (pip en venv), tkinter (apt), (matplotlib NO requerido)
- Pines por defecto (los que probaste): DT=5, SCK=6, canal A, ganancia 64
  * Sugerido: SCK con pull-down físico 47–100k a GND si usas GPIO 0–8.
"""

import os
import sys
import json
import csv
import time
import math
import signal
import threading
import queue
from datetime import datetime
from collections import deque

# --- Detección de entorno gráfico ---
HAS_DISPLAY = bool(os.environ.get("DISPLAY"))

# --- HX711 / GPIO ---
HX711_AVAILABLE = True
try:
    import RPi.GPIO as GPIO
    from hx711 import HX711
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("✅ HX711 disponible")
except Exception as e:
    HX711_AVAILABLE = False
    print(f"❌ HX711 no disponible ({e}) - modo simulación")

# --- GUI (si hay DISPLAY) ---
if HAS_DISPLAY:
    import tkinter as tk
    from tkinter import ttk, messagebox
else:
    # Placeholders para anotaciones
    tk = None
    ttk = None
    messagebox = None

# ====== Utilidades de configuración/calibración ======
CONFIG_FILE = "bascula_config.json"
CAL_FILE    = "calibracion.json"
LOG_JSON    = "mediciones.json"
LOG_CSV     = "mediciones.csv"

DEFAULT_CONFIG = {
    "pins": {
        "dout": 5,      # Tu wiring probado
        "sck": 6        # Tu wiring probado
    },
    "channel": "A",     # 'A' o 'B'
    "gain": 64,         # 64, 128 (A) / 32 (B)
    "refresh_ms": 100,  # GUI update
    "raw_averages": 3   # cuántas lecturas crudas promedia hx.get_raw_data
}

DEFAULT_CAL = {
    "offset": -8575.0,      # tu promedio sin peso
    "scale_counts_per_gram": 1.0,   # 1 cuenta == 1 gr (ajustar con calibración)
    "unit": "gramos"
}

def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default.copy()
    except Exception as e:
        print(f"⚠️ No se pudo leer {path}: {e}")
        return default.copy()

def save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ No se pudo guardar {path}: {e}")
        return False

# ====== Filtros de ruido (mediana + EMA) ======
def median(lst):
    if not lst:
        return 0.0
    s = sorted(lst)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return 0.5 * (s[mid-1] + s[mid])

class MedianEMAFilter:
    """
    Filtro combinado:
    - Ventana circular para mediana (resistente a outliers)
    - Luego un EMA (alpha configurable) para suavizar
    """
    def __init__(self, window=7, alpha=0.3):
        self.window = max(3, int(window))
        self.alpha = max(0.01, min(1.0, float(alpha)))
        self.buffer = deque(maxlen=self.window)
        self.ema = None

    def push(self, value):
        self.buffer.append(float(value))
        med = median(self.buffer)
        if self.ema is None:
            self.ema = med
        else:
            self.ema = self.alpha * med + (1 - self.alpha) * self.ema
        return self.ema

# ====== Lectura HX711 en hilo ======
class HX711Reader(threading.Thread):
    def __init__(self, cfg, cal, data_queue, stop_event):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.cal = cal
        self.q = data_queue
        self.stop = stop_event
        self.hx = None
        self.filter = MedianEMAFilter(window=9, alpha=0.25)
        self.sim_seed = DEFAULT_CAL["offset"]
        self.ok = False

    def init_hx(self):
        if not HX711_AVAILABLE:
            self.ok = False
            return
        try:
            self.hx = HX711(
                dout_pin=self.cfg["pins"]["dout"],
                pd_sck_pin=self.cfg["pins"]["sck"],
                channel=self.cfg["channel"],
                gain=self.cfg["gain"]
            )
            self.hx.reset()
            # pequeño settle
            time.sleep(0.3)
            self.ok = True
            print("🔧 HX711 inicializado")
        except Exception as e:
            self.hx = None
            self.ok = False
            print(f"❌ Error inicializando HX711: {e}")

    def read_raw_avg(self, times):
        """
        Devuelve promedio de hx.get_raw_data(times=times)
        o None si hay error.
        """
        if not self.hx:
            return None
        try:
            raw_list = self.hx.get_raw_data(times=times)
            if not raw_list:
                return None
            valid = [x for x in raw_list if x is not None]
            if not valid:
                return None
            return sum(valid) / len(valid)
        except Exception:
            return None

    def run(self):
        if HX711_AVAILABLE:
            self.init_hx()
        refresh_s = max(0.05, self.cfg.get("refresh_ms", 100) / 1000.0)

        while not self.stop.is_set():
            if self.ok and self.hx:
                raw = self.read_raw_avg(self.cfg.get("raw_averages", 3))
                if raw is not None:
                    filtered = self.filter.push(raw)
                    # Convertir a peso
                    grams = (filtered - self.cal["offset"]) / max(1e-9, self.cal["scale_counts_per_gram"])
                    self.q.put(("data", grams, raw, filtered))
                else:
                    self.q.put(("warn", "Sin datos del HX711"))
            else:
                # Simulación si no hay HX
                import random
                raw_sim = self.sim_seed + random.randint(-30, 30)
                filtered = self.filter.push(raw_sim)
                grams = (filtered - self.cal["offset"]) / max(1e-9, self.cal["scale_counts_per_gram"])
                self.q.put(("data", grams, raw_sim, filtered))
            time.sleep(refresh_s)

    def close(self):
        try:
            if self.hx and HX711_AVAILABLE:
                GPIO.cleanup()
        except Exception:
            pass

# ====== Modo GUI ======
class BasculaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🏭 Báscula Digital Pro - HX711")
        self.root.geometry("800x480")
        self.root.configure(bg='#1a1a1a')

        # Estilo
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass

        # Estado
        self.cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        self.cal = load_json(CAL_FILE, DEFAULT_CAL)
        self.unit = self.cal.get("unit", "gramos")
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.reader = HX711Reader(self.cfg, self.cal, self.queue, self.stop_event)
        self.is_running = False

        # Variables de vista
        self.current_weight = 0.0
        self.max_weight = float('-inf')
        self.min_weight = float('inf')
        self.recent_weights = deque(maxlen=120)  # ~12 s si refresh_ms=100
        self.recent_raw = deque(maxlen=60)
        self.show_raw = False

        # UI
        self._build_ui()

        # Señales
        self.root.bind('<Escape>', lambda e: self.safe_exit())

        # Arranque
        self.start()

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=5)

        title = tk.Label(
            header, text="🏭 BÁSCULA DIGITAL HX711",
            font=('Arial', 20, 'bold'),
            fg='white', bg='#1a1a1a'
        )
        title.pack(side=tk.LEFT)

        status_txt = "✅ Conectado" if HX711_AVAILABLE else "🔄 Simulación"
        self.status_label = tk.Label(
            header, text=status_txt,
            font=('Arial', 12),
            fg='#2ecc71' if HX711_AVAILABLE else '#f39c12',
            bg='#1a1a1a'
        )
        self.status_label.pack(side=tk.RIGHT)

        # Display principal
        display_frame = tk.Frame(self.root, bg='#2c3e50', relief='raised', bd=2)
        display_frame.pack(fill=tk.X, padx=10, pady=10)

        self.weight_display = tk.Label(
            display_frame, text="0.0",
            font=('Courier New', 60, 'bold'),
            fg='#2ecc71', bg='#2c3e50'
        )
        self.weight_display.pack(pady=16)

        self.unit_label = tk.Label(
            display_frame, text=self.unit,
            font=('Arial', 16),
            fg='#3498db', bg='#2c3e50'
        )
        self.unit_label.pack()

        # Stats
        stats_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        self.stats_text = tk.Label(
            stats_frame,
            text="Lecturas: 0 | Promedio: 0.0g | Rango: 0.0g",
            font=('Arial', 11),
            fg='white', bg='#34495e'
        )
        self.stats_text.pack(pady=8)

        # Botones
        self._build_buttons()

        # Mini gráfico
        graph_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        graph_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(
            graph_frame, text="📈 Tendencia (últimas 60 lecturas)",
            font=('Arial', 11, 'bold'), fg='white', bg='#34495e'
        ).pack(pady=5)

        self.graph_canvas = tk.Canvas(graph_frame, width=760, height=120, bg='#2c3e50', highlightthickness=0)
        self.graph_canvas.pack(pady=5)

        # RAW info
        raw_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=1)
        raw_frame.pack(fill=tk.X, padx=10, pady=5)
        self.raw_label = tk.Label(
            raw_frame,
            text=f"RAW: -- | OFFSET: {self.cal['offset']:.0f} | FACTOR: {self.cal['scale_counts_per_gram']:.6f}",
            font=('Courier New', 10), fg='#95a5a6', bg='#34495e'
        )
        self.raw_label.pack(pady=5)

    def _build_buttons(self):
        btn_frame = tk.Frame(self.root, bg='#1a1a1a')
        btn_frame.pack(fill=tk.X, padx=10, pady=8)

        # fila 1
        row1 = tk.Frame(btn_frame, bg='#1a1a1a')
        row1.pack(fill=tk.X, pady=2)
        tk.Button(row1, text="🔄 TARA", command=self.do_tare,
                  font=('Arial', 12, 'bold'), bg='#3498db', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        tk.Button(row1, text="⚖️ CALIBRAR", command=self.open_cal_dialog,
                  font=('Arial', 12, 'bold'), bg='#e67e22', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        tk.Button(row1, text="💾 GUARDAR", command=self.save_current,
                  font=('Arial', 12, 'bold'), bg='#27ae60', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        # fila 2
        row2 = tk.Frame(btn_frame, bg='#1a1a1a')
        row2.pack(fill=tk.X, pady=2)
        tk.Button(row2, text="🧽 RESET", command=self.reset_stats,
                  font=('Arial', 12, 'bold'), bg='#f39c12', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        tk.Button(row2, text="📊 RAW", command=self.toggle_raw,
                  font=('Arial', 12, 'bold'), bg='#9b59b6', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        tk.Button(row2, text="🚪 SALIR", command=self.safe_exit,
                  font=('Arial', 12, 'bold'), bg='#e74c3c', fg='white', height=2
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

    def start(self):
        self.is_running = True
        self.reader.start()
        self._pump_queue()
        self.root.after(max(50, self.cfg.get("refresh_ms", 100)), self._update_ui)

    def _pump_queue(self):
        """Lee eventos del hilo lector"""
        try:
            while True:
                kind, *payload = self.queue.get_nowait()
                if kind == "data":
                    grams, raw, filtered = payload
                    self._process_reading(grams, raw, filtered)
                elif kind == "warn":
                    msg = payload[0]
                    # Mostrar una vez cada X?
                    # print(f"⚠️ {msg}")
                else:
                    pass
        except queue.Empty:
            pass
        if self.is_running:
            self.root.after(10, self._pump_queue)

    def _process_reading(self, grams, raw, filtered):
        self.current_weight = grams
        self.recent_weights.append(grams)
        self.recent_raw.append(raw)
        if grams > self.max_weight:
            self.max_weight = grams
        if grams < self.min_weight:
            self.min_weight = grams

    def _update_ui(self):
        # Peso principal
        w = self.current_weight
        self.weight_display.configure(text=f"{w:.1f}")
        # color
        if abs(w) < 2:
            color = '#95a5a6'
        elif w > 5000:
            color = '#e74c3c'
        else:
            color = '#2ecc71'
        self.weight_display.configure(fg=color)

        # Stats
        n = len(self.recent_weights)
        if n:
            avg = sum(self.recent_weights) / n
            rng = self.max_weight - self.min_weight if math.isfinite(self.max_weight) and math.isfinite(self.min_weight) else 0.0
            self.stats_text.configure(text=f"Lecturas: {n} | Promedio: {avg:.1f} {self.unit} | Rango: {rng:.1f} {self.unit}")
        else:
            self.stats_text.configure(text="Lecturas: 0 | Promedio: 0.0 | Rango: 0.0")

        # RAW info
        raw_last = self.recent_raw[-1] if self.recent_raw else None
        self.raw_label.configure(
            text=f"RAW: {raw_last:.0f} | OFFSET: {self.cal['offset']:.0f} | FACTOR: {self.cal['scale_counts_per_gram']:.6f}"
            if raw_last is not None else
                 f"RAW: -- | OFFSET: {self.cal['offset']:.0f} | FACTOR: {self.cal['scale_counts_per_gram']:.6f}"
        )
        # Mini gráfico
        self._draw_graph()

        if self.is_running:
            self.root.after(max(50, self.cfg.get("refresh_ms", 100)), self._update_ui)

    def _draw_graph(self):
        self.graph_canvas.delete("graph")
        vals = list(self.recent_weights)[-60:]
        if len(vals) < 2:
            return
        w = 760
        h = 120
        pad = 10
        vmin = min(vals)
        vmax = max(vals)
        rng = vmax - vmin if vmax != vmin else 1.0
        pts = []
        for i, v in enumerate(vals):
            x = pad + (i/(len(vals)-1)) * (w - 2*pad)
            y = h - pad - ((v - vmin)/rng) * (h - 2*pad)
            pts.extend([x, y])
        if len(pts) >= 4:
            self.graph_canvas.create_line(pts, fill='#2ecc71', width=2, tags="graph")

    # --- Acciones ---
    def do_tare(self):
        """
        Ajusta offset (tara) a partir de últimas lecturas crudas.
        Para evitar drift, movemos el offset global de calibración en memoria.
        """
        if not self.recent_raw:
            self._flash_status("⚠️ Sin lecturas crudas", fg="#f39c12")
            return
        # Tomamos mediana de los últimos crudos filtrados en reader (usamos raw último)
        # Mejor: calculemos media de últimos N raw
        raws = list(self.recent_raw)[-15:] if len(self.recent_raw) >= 15 else list(self.recent_raw)
        avg_raw = sum(raws)/len(raws)
        # Queremos que el peso actual pase a 0 -> offset := raw_filtrado_actual
        # Para ser más estable, usamos avg_raw
        self.cal["offset"] = avg_raw
        save_json(CAL_FILE, self.cal)
        self._flash_status("✅ Tara aplicada", fg="#2ecc71")

    def open_cal_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Calibración")
        dlg.geometry("320x220")
        dlg.configure(bg='#2c3e50')
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="⚖️ Calibración rápida (peso conocido)", font=('Arial', 13, 'bold'),
                 fg='white', bg='#2c3e50').pack(pady=10)
        tk.Label(dlg, text="1) TARA sin peso\n2) Coloca el peso conocido\n3) Introduce gramos y pulsa Calibrar",
                 font=('Arial', 10), fg='white', bg='#2c3e50').pack(pady=6)

        frm = tk.Frame(dlg, bg='#2c3e50')
        frm.pack(pady=8)
        tk.Label(frm, text="Peso (g):", fg='white', bg='#2c3e50').pack(side=tk.LEFT, padx=5)
        ent = tk.Entry(frm, width=10)
        ent.pack(side=tk.LEFT, padx=5)
        ent.insert(0, "1000")

        msg = tk.Label(dlg, text="", font=('Arial', 10), fg='#f1c40f', bg='#2c3e50')
        msg.pack(pady=4)

        def apply():
            try:
                known = float(ent.get().strip())
                if known <= 0:
                    raise ValueError("peso no positivo")
                # Tomar promedio de últimos pesos (ya convertidos con offset actual)
                vals = list(self.recent_weights)[-20:] if len(self.recent_weights) >= 5 else list(self.recent_weights)
                if not vals:
                    msg.configure(text="Aún no hay lecturas suficientes")
                    return
                avg_weight_now = sum(vals)/len(vals)
                # scale = (filtered - offset) / grams  => grams = (filtered - offset)/scale
                # Queremos que avg_weight_now == known -> adjust scale:
                # new_scale = current_scale * (avg_filtered_delta / known)
                # Pero no tenemos filtered aquí; reestimemos usando raw último:
                if not self.recent_raw:
                    msg.configure(text="Sin RAW disponible")
                    return
                raw_vals = list(self.recent_raw)[-10:]
                avg_raw = sum(raw_vals)/len(raw_vals)
                delta_counts = avg_raw - self.cal["offset"]
                if abs(delta_counts) < 1e-6:
                    msg.configure(text="Delta RAW ~0 (coloca peso)")
                    return
                new_scale = delta_counts / known
                self.cal["scale_counts_per_gram"] = float(abs(new_scale))
                save_json(CAL_FILE, self.cal)
                self._flash_status("✅ Calibración guardada", fg="#2ecc71")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Peso inválido o error: {e}")

        tk.Button(dlg, text="Calibrar", command=apply,
                  bg='#27ae60', fg='white', font=('Arial', 12)).pack(pady=10)

    def save_current(self):
        """Guarda lectura actual en JSON y CSV"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "weight": round(self.current_weight, 2),
            "unit": self.unit
        }
        # JSON
        try:
            try:
                with open(LOG_JSON, "r") as f:
                    arr = json.load(f)
            except FileNotFoundError:
                arr = []
            arr.append(record)
            with open(LOG_JSON, "w") as f:
                json.dump(arr, f, indent=2)
            ok_json = True
        except Exception as e:
            print(f"⚠️ No se pudo guardar JSON: {e}")
            ok_json = False
        # CSV
        try:
            new_file = not os.path.exists(LOG_CSV)
            with open(LOG_CSV, "a", newline="") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(["timestamp", "weight", "unit"])
                w.writerow([record["timestamp"], record["weight"], record["unit"]])
            ok_csv = True
        except Exception as e:
            print(f"⚠️ No se pudo guardar CSV: {e}")
            ok_csv = False

        if ok_json or ok_csv:
            self._flash_status("💾 Lectura guardada", fg="#f39c12")
        else:
            self._flash_status("❌ Error guardando", fg="#e74c3c")

    def reset_stats(self):
        self.recent_weights.clear()
        self.recent_raw.clear()
        self.max_weight = float('-inf')
        self.min_weight = float('inf')
        self._flash_status("🔄 Reset completado", fg="#f39c12")

    def toggle_raw(self):
        self.show_raw = not self.show_raw
        self.raw_label.configure(fg='#f39c12' if self.show_raw else '#95a5a6')

    def _flash_status(self, text, fg="#2ecc71", ms=2500):
        self.status_label.configure(text=text, fg=fg)
        self.root.after(ms, lambda: self.status_label.configure(
            text=("✅ Conectado" if HX711_AVAILABLE else "🔄 Simulación"),
            fg=('#2ecc71' if HX711_AVAILABLE else '#f39c12')
        ))

    def safe_exit(self):
        self.is_running = False
        self.stop_event.set()
        try:
            self.reader.close()
        except Exception:
            pass
        self.root.quit()

# ====== Modo headless (terminal) ======
class BasculaHeadless:
    def __init__(self):
        self.cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        self.cal = load_json(CAL_FILE, DEFAULT_CAL)
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.reader = HX711Reader(self.cfg, self.cal, self.queue, self.stop_event)
        self.running = False

    def start(self):
        self.running = True
        self.reader.start()
        print("🚀 Headless - Báscula Digital (Ctrl+C para salir)")
        print(f"Pins: DOUT={self.cfg['pins']['dout']} SCK={self.cfg['pins']['sck']}  Canal={self.cfg['channel']}  Ganancia={self.cfg['gain']}")
        print(f"Offset={self.cal['offset']:.1f}  Scale={self.cal['scale_counts_per_gram']:.6f}  Unidad={self.cal.get('unit','gramos')}")

        last_print = 0.0
        try:
            while self.running:
                try:
                    kind, *payload = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if kind == "data":
                    grams, raw, filtered = payload
                    now = time.time()
                    if now - last_print >= 0.2:
                        sys.stdout.write(f"\rPeso: {grams:8.2f} {self.cal.get('unit','g')}    RAW:{raw:10.0f}    FILT:{filtered:10.1f}")
                        sys.stdout.flush()
                        last_print = now
                elif kind == "warn":
                    print(f"\n⚠️ {payload[0]}")
        except KeyboardInterrupt:
            print("\n⏹️  Saliendo…")
        finally:
            self.stop_event.set()
            self.reader.close()

# ====== Punto de entrada ======
def run_gui():
    root = tk.Tk()
    app = BasculaGUI(root)
    def handle_sigint(signum, frame):
        app.safe_exit()
    signal.signal(signal.SIGINT, handle_sigint)
    try:
        root.mainloop()
    finally:
        try:
            app.safe_exit()
        except Exception:
            pass

def run_headless():
    app = BasculaHeadless()
    def handle_sigint(signum, frame):
        app.running = False
    signal.signal(signal.SIGINT, handle_sigint)
    app.start()

def main():
    if HAS_DISPLAY:
        run_gui()
    else:
        run_headless()

if __name__ == "__main__":
    main()
