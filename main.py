#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox, filedialog
import csv
import json
from datetime import datetime

from python_backend.bascula.services.scale import ScaleService

# ---------- Teclado numérico ----------
class NumPadDialog(tk.Toplevel):
    def __init__(self, master, title="Calibración (g)", initial=""):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="black")
        self.result = None
        self.value = tk.StringVar(value=str(initial))

        wrap = tk.Frame(self, bg="black")
        wrap.pack(padx=10, pady=10)

        entry = tk.Entry(wrap, textvariable=self.value, font=("Arial", 36), justify="right", width=10)
        entry.grid(row=0, column=0, columnspan=3, pady=(0,10))
        entry.focus_set()

        buttons = [
            ("7",1,0),("8",1,1),("9",1,2),
            ("4",2,0),("5",2,1),("6",2,2),
            ("1",3,0),("2",3,1),("3",3,2),
            ("0",4,0),(".",4,1),("←",4,2),
        ]
        for text, r, c in buttons:
            tk.Button(wrap, text=text, font=("Arial", 26), width=3, height=1,
                      command=lambda t=text: self._press(t)).grid(row=r, column=c, padx=4, pady=4)

        bwrap = tk.Frame(wrap, bg="black")
        bwrap.grid(row=5, column=0, columnspan=3, pady=(10,0))
        tk.Button(bwrap, text="Cancelar", font=("Arial", 22), width=8, command=self._cancel).pack(side=tk.LEFT, padx=8)
        tk.Button(bwrap, text="OK", font=("Arial", 22), width=8, command=self._ok).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _press(self, t):
        s = self.value.get()
        if t == "←":
            self.value.set(s[:-1])
        else:
            if t == "." and "." in s:
                return
            self.value.set(s + t)

    def _ok(self):
        txt = self.value.get().strip()
        try:
            v = float(txt)
            if v <= 0:
                raise ValueError
            self.result = v
            self.destroy()
        except Exception:
            messagebox.showerror("Error", "Introduce un número válido (> 0).")

    def _cancel(self):
        self.result = None
        self.destroy()

# ---------- App ----------
class ScaleApp:
    def __init__(self):
        # Backend serie
        self.scale = ScaleService(port="/dev/serial0", baud=115200)
        self.scale.start()

        # Ventana a pantalla completa
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="black")
        self.root.attributes("-fullscreen", True)   # pantalla completa
        # Nota: mantenemos ESC para salir como tenías.
        self.root.bind("<Escape>", lambda e: self.on_close())

        # Atajos exportación
        self.root.bind("<Control-s>", lambda e: self.export_csv())
        self.root.bind("<Control-j>", lambda e: self.export_json())

        # Contenedor central que se expande
        outer = tk.Frame(self.root, bg="black")
        outer.pack(fill="both", expand=True)

        # Grid para centrar elementos
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=0)
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Peso grande centrado (ahora sin decimales en la vista)
        self.weight_var = tk.StringVar(value="--- g")
        lbl = tk.Label(outer, textvariable=self.weight_var, font=("Arial", 96),
                       fg="white", bg="black")
        lbl.grid(row=0, column=0, sticky="nsew", pady=(40,10))

        # Estado
        self.stable_var = tk.StringVar(value="")
        self.status_label = tk.Label(outer, textvariable=self.stable_var, font=("Arial", 28),
                                     fg="#9acd32", bg="black")
        self.status_label.grid(row=1, column=0, pady=(0,10))

        # Botonera grande centrada
        btns = tk.Frame(outer, bg="black")
        btns.grid(row=2, column=0, pady=(10,40))

        def mkbtn(text, cmd, w=10):
            return tk.Button(btns, text=text, font=("Arial", 26), width=w, height=2, command=cmd)

        # Fila 1: calibraciones como ya tenías
        mkbtn("Tara", self.do_tare).grid(row=0, column=0, padx=12, pady=12)
        mkbtn("Cal 200g", lambda: self.do_cal_preset(200)).grid(row=0, column=1, padx=12, pady=12)
        mkbtn("Cal 500g", lambda: self.do_cal_preset(500)).grid(row=0, column=2, padx=12, pady=12)
        mkbtn("Cal 1000g", lambda: self.do_cal_preset(1000)).grid(row=0, column=3, padx=12, pady=12)
        mkbtn("Calibrar…", self.do_cal_dialog).grid(row=0, column=4, padx=12, pady=12)

        # Fila 2: exportación + salir (mismo ancho para homogeneidad visual)
        mkbtn("Exportar CSV", self.export_csv, w=12).grid(row=1, column=0, padx=12, pady=12)
        mkbtn("Exportar JSON", self.export_json, w=12).grid(row=1, column=1, padx=12, pady=12)
        mkbtn("Salir (Esc)", self.on_close, w=12).grid(row=1, column=4, padx=12, pady=12)

        # Estado para logging/exportación
        self.measure_log = []          # Lista de dicts
        self._last_logged_int = None   # Para evitar duplicados excesivos
        self._last_display_int = None  # Para refrescos UI

        # Bucle de actualización
        self.root.after(200, self.update_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- Botones ----
    def do_tare(self):
        ok = self.scale.tare()
        messagebox.showinfo("Tara", "OK" if ok else "Fallo al enviar")

    def do_cal_preset(self, grams):
        ok = self.scale.calibrate(float(grams))
        messagebox.showinfo("Calibración", f"{'OK' if ok else 'Fallo'} C:{grams}")

    def do_cal_dialog(self):
        dlg = NumPadDialog(self.root, title="Calibración (g)")
        self.root.wait_window(dlg)
        if dlg.result is not None:
            ok = self.scale.calibrate(float(dlg.result))
            messagebox.showinfo("Calibración", f"{'OK' if ok else 'Fallo'} C:{dlg.result:g}")

    # ---- UI loop ----
    def update_loop(self):
        g = self.scale.get_weight()         # float interno
        s = self.scale.is_stable()          # bool/0-1
        display_int = int(round(g))         # <-- solo enteros en la vista

        # Actualización de UI (solo si cambia el entero mostrado)
        if display_int != self._last_display_int:
            self.weight_var.set(f"{display_int} g")
            self._last_display_int = display_int

        # Estado estable/inestable (y color suave)
        if s:
            self.stable_var.set("Estable ✓")
            self.status_label.config(fg="#41D888")  # verde
        else:
            self.stable_var.set("Inestable …")
            self.status_label.config(fg="#FFB020")  # ámbar

        # Logging: guarda solo cuando está estable y cambia el entero
        if s and (self._last_logged_int != display_int):
            self._append_measure(display_int, g, int(bool(s)))
            self._last_logged_int = display_int

        self.root.after(200, self.update_loop)

    def _append_measure(self, grams_int, grams_raw, stable_flag):
        self.measure_log.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "grams_int": int(grams_int),
            "grams_raw": float(grams_raw),
            "stable": int(stable_flag),
        })
        # Evita crecimiento infinito
        if len(self.measure_log) > 5000:
            self.measure_log = self.measure_log[-2000:]

    # ---- Exportación ----
    def _ensure_data_for_export(self):
        if not self.measure_log:
            messagebox.showinfo("Exportar", "No hay datos que exportar todavía.")
            return None
        return list(self.measure_log)  # copia superficial

    def export_csv(self):
        data = self._ensure_data_for_export()
        if data is None:
            return
        default = f"pesajes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            title="Guardar CSV",
            defaultextension=".csv",
            initialfile=default,
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["timestamp", "grams_int", "grams_raw", "stable"])
                w.writeheader()
                for row in data:
                    w.writerow(row)
            messagebox.showinfo("Exportar", f"CSV guardado:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo guardar CSV:\n{e}")

    def export_json(self):
        data = self._ensure_data_for_export()
        if data is None:
            return
        default = f"pesajes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = filedialog.asksaveasfilename(
            title="Guardar JSON",
            defaultextension=".json",
            initialfile=default,
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportar", f"JSON guardado:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo guardar JSON:\n{e}")

    # ---- Salida limpia ----
    def on_close(self):
        try:
            self.scale.stop()
        except Exception:
            pass
        self.root.destroy()

def run_app():
    app = ScaleApp()
    app.root.mainloop()

if __name__ == "__main__":
    run_app()
