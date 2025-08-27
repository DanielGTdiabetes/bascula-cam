import tkinter as tk
from datetime import datetime
from tkinter import messagebox, filedialog
from bascula.config.theme import THEME
from bascula.ui.widgets import ProButton, WeightDisplay
from bascula.ui.keyboard import NumericKeyboard

class HomeScreen(tk.Frame):
    def __init__(self, root, state, storage, logger, scale, camera):
        super().__init__(root, bg=THEME.background)
        # Normaliza scaling para evitar desproporciones por DPI
        try:
            self.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass

        self.state = state
        self.storage = storage
        self.logger = logger
        self.scale = scale
        self.camera = camera
        self.auto_photo_on_save = True

        header = tk.Frame(self, bg=THEME.surface, bd=1, relief="solid")
        header.pack(fill="x", padx=16, pady=(16,8))
        tk.Label(header, text="⚖️ SMART BÁSCULA CAM", font=("Arial",18,"bold"),
                 bg=THEME.surface, fg=THEME.primary).pack(padx=12, pady=8)

        self.display = WeightDisplay(self)
        self.display.pack(fill="both", expand=True, padx=16, pady=8)

        controls = tk.Frame(self, bg=THEME.background); controls.pack(fill="x", padx=16, pady=8)
        ProButton(controls, text="TARA",            size="lg", command=self._tara, height=2).pack(side="left", expand=True, fill="x", padx=4)
        ProButton(controls, text="PLATO COMPLETO",  size="lg", command=self._plate, height=2).pack(side="left", expand=True, fill="x", padx=4)
        ProButton(controls, text="AÑADIR ALIMENTO", size="lg", command=self._add_item, height=2).pack(side="left", expand=True, fill="x", padx=4)
        ProButton(controls, text="MENÚ",            size="lg", command=self._menu, height=2).pack(side="left", expand=True, fill="x", padx=4)
        ProButton(controls, text="RESET", kind="warning", size="lg", command=self._reset, height=2).pack(side="right", padx=4)

        self.info = tk.Label(self, text="Sistema iniciado", font=("Arial",11),
                             bg=THEME.background, fg=THEME.text)
        self.info.pack(pady=(0,8))

        self._tick()

    def _tick(self):
        stable = self.scale.filter.stable
        self.display.set_value(self.state.current_weight, stable)
        self.after(200, self._tick)

    def _tara(self):
        if self.scale.tara():
            self._status("TARA aplicada", "ok")
        else:
            self._status("Espera 1–2 s y vuelve a pulsar TARA", "warn")

    def _plate(self):
        self.state.mode = "plate"
        self._status("Modo plato completo", "ok")

    def _add_item(self):
        self.state.mode = "add_item"
        self._status("Modo añadir alimento", "ok")

    def _menu(self):
        win = tk.Toplevel(self); win.title("Menú"); win.configure(bg=THEME.background)
        for txt, kind, cmd in [
            ("Historial (WIP)",       "secondary", lambda: win.destroy()),
            ("Exportar CSV",          "secondary", self._export_csv),
            ("Ajustes",               "secondary", lambda: self._settings(win)),
            ("Recetas guiadas (WIP)", "secondary", lambda: win.destroy()),
            ("Técnico (PIN)",         "secondary", lambda: self._tech_menu(win)),
            ("Cerrar",                "danger",    win.destroy),
        ]:
            ProButton(win, text=txt, kind=kind, size="lg", height=2, command=cmd).pack(fill="x", padx=16, pady=6)

    def _reset(self):
        self.state.meal_active = False
        self.state.meal_items = 0
        self.state.meal_carbs = 0.0
        self._status("Sesión reiniciada", "ok")

    def _export_csv(self):
        from pathlib import Path
        path = filedialog.asksaveasfilename(title="Guardar CSV",
                                            defaultextension=".csv",
                                            filetypes=[("CSV","*.csv")])
        if not path:
            return
        try:
            self.storage.export_csv(Path(path))
            messagebox.showinfo("Exportación", f"CSV exportado:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportación", str(e))

    def _settings(self, parent):
        w = tk.Toplevel(parent); w.title("Ajustes"); w.configure(bg=THEME.background)
        tk.Label(w, text="OpenAI API Key", bg=THEME.background).grid(row=0, column=0, sticky="w", padx=12, pady=6)
        e_api = tk.Entry(w, show="*", width=40); e_api.insert(0, self.state.cfg.network.api_key); e_api.grid(row=0, column=1, padx=12, pady=6)

        tk.Label(w, text="Wi-Fi SSID", bg=THEME.background).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        e_ssid = tk.Entry(w, width=32); e_ssid.insert(0, self.state.cfg.network.wifi_ssid); e_ssid.grid(row=1, column=1, padx=12, pady=6)

        tk.Label(w, text="Wi-Fi Password", bg=THEME.background).grid(row=2, column=0, sticky="w", padx=12, pady=6)
        e_wpass = tk.Entry(w, show="*", width=32); e_wpass.insert(0, self.state.cfg.network.wifi_pass); e_wpass.grid(row=2, column=1, padx=12, pady=6)

        from tkinter import BooleanVar
        show_ins = BooleanVar(value=self.state.cfg.diabetes.show_insulin)
        tk.Checkbutton(w, text="Mostrar sugerencia de insulina (informativo)", variable=show_ins, bg=THEME.background)            .grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(10,6))

        tk.Label(w, text="ICR (g/U)", bg=THEME.background).grid(row=4, column=0, sticky="w", padx=12, pady=6)
        e_icr = tk.Entry(w, width=8); e_icr.insert(0, str(self.state.cfg.diabetes.icr)); e_icr.grid(row=4, column=1, sticky="w", padx=12, pady=6)

        tk.Label(w, text="ISF (mg/dL por U)", bg=THEME.background).grid(row=5, column=0, sticky="w", padx=12, pady=6)
        e_isf = tk.Entry(w, width=8); e_isf.insert(0, str(self.state.cfg.diabetes.isf)); e_isf.grid(row=5, column=1, sticky="w", padx=12, pady=6)

        tk.Label(w, text="Objetivo BG (mg/dL)", bg=THEME.background).grid(row=6, column=0, sticky="w", padx=12, pady=6)
        e_tbg = tk.Entry(w, width=8); e_tbg.insert(0, str(self.state.cfg.diabetes.target_bg)); e_tbg.grid(row=6, column=1, sticky="w", padx=12, pady=6)

        from bascula.config.settings import save_config
        def save_and_close():
            try:
                self.state.cfg.network.api_key = e_api.get().strip()
                self.state.cfg.network.wifi_ssid = e_ssid.get().strip()
                self.state.cfg.network.wifi_pass = e_wpass.get().strip()
                self.state.cfg.diabetes.show_insulin = bool(show_ins.get())
                self.state.cfg.diabetes.icr = float(e_icr.get())
                self.state.cfg.diabetes.isf = float(e_isf.get())
                self.state.cfg.diabetes.target_bg = float(e_tbg.get())
                save_config(self.state.cfg)
                self._status("Ajustes guardados", "ok")
                w.destroy()
            except Exception as e:
                messagebox.showerror("Ajustes", str(e))

        ProButton(w, text="Guardar", kind="success", size="lg", command=save_and_close)            .grid(row=7, column=0, padx=12, pady=(12,12))
        ProButton(w, text="Cerrar", kind="secondary", size="lg", command=w.destroy)            .grid(row=7, column=1, padx=12, pady=(12,12), sticky="e")

    def _tech_menu(self, parent):
        kb = NumericKeyboard(parent, title="PIN Técnico", big=True)
        self.wait_window(kb)
        if kb.result != (self.state.cfg.ui.tech_pin or "2468"):
            messagebox.showerror("Técnico", "PIN incorrecto"); return
        w = tk.Toplevel(parent); w.title("Técnico"); w.configure(bg=THEME.background)
        ProButton(w, text="Calibración", kind="warning", size="lg", height=2, command=lambda: self._calibrate(w)).pack(fill="x", padx=16, pady=6)
        ProButton(w, text="Diagnóstico", kind="secondary", size="lg", height=2, command=self._diagnostics).pack(fill="x", padx=16, pady=6)
        ProButton(w, text="Cerrar", kind="danger", size="lg", height=2, command=w.destroy).pack(fill="x", padx=16, pady=(6,12))

    def _calibrate(self, parent):
        kb = NumericKeyboard(parent, title="Peso de calibración (g)", initial="1000", big=True)
        self.wait_window(kb)
        if not kb.result: return
        try:
            known = float(kb.result); assert known > 0
        except Exception:
            messagebox.showerror("Calibración", "Valor inválido"); return

        msg = ("1) Retira todo del plato y espera a que marque CERO.\n"
               "2) Pulsa ACEPTAR.\n\n"
               "Luego coloca el peso patrón y pulsa ACEPTAR de nuevo.")
        if not messagebox.askokcancel("Calibración", msg):
            return
        try:
            if not messagebox.askokcancel("Calibración", "Cero listo sin peso. ¿Continuar?"):
                return
            if not messagebox.askokcancel("Calibración", f"Coloca {known:.0f} g y espera ESTABLE.\n¿Medir ahora?"):
                return
            res = self.scale.calibrate_two_points(known_weight_g=known, settle_time_s=1.0)
            from bascula.config.settings import save_config
            save_config(self.state.cfg)
            messagebox.showinfo("Calibración", f"OK\nbase_offset={res['base_offset']:.1f}\nscale={res['scale_factor']:.6f}")
            self._status("Calibración guardada", "ok")
        except Exception as e:
            messagebox.showerror("Calibración", f"Error: {e}")

    def _diagnostics(self):
        stab = self.scale.filter
        msg = f"""DIAGNÓSTICO

HX711: {'✅' if self.state.hx_ready else '❌'}
Cámara: {'✅' if self.state.camera_ready else '❌'}

Filtro:
- Estable: {'✅' if stab.stable else '❌'}
- Zero-tracking: {'ON' if stab.zero_tracking else 'OFF'}
"""
        messagebox.showinfo("Diagnóstico", msg)

    def _status(self, msg, kind="ok"):
        colors = {"ok": THEME.success, "warn": THEME.warning, "err": THEME.danger}
        self.info.configure(text=msg, fg=colors.get(kind, THEME.primary))

    def _save_measurement(self):
        w = round(self.state.current_weight, 2)
        photo = ""
        if self.auto_photo_on_save:
            photo = self.camera.capture(w) or ""
        rec = {"timestamp": datetime.now().isoformat(), "weight": w, "unit": "g",
               "stable": self.scale.filter.stable, "photo": photo}
        self.storage.append_measurement(rec)
        self._status("Medición guardada", "ok")
