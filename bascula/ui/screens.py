# -*- coding: utf-8 -*-
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, filedialog

from bascula.config.theme import THEME
from bascula.ui.widgets import ProButton, WeightDisplay
from bascula.ui.keyboard import NumericKeyboard
from bascula.config.settings import save_config


class HomeScreen(tk.Frame):
    """
    Pantalla principal compatible con el estado y la configuración actuales.
    - Lee peso con `ScaleService.read()` y actualiza `AppState` (last_weight_g, stable).
    - Exporta CSV vía `Storage` y puede adjuntar foto con `CameraService`.
    - Ajustes mínimos: ZERO tracking y calibración con peso patrón.
    """

    def __init__(self, root, state, storage, logger, scale, camera):
        super().__init__(root, bg=THEME.background)
        self.state = state
        self.storage = storage
        self.logger = logger
        self.scale = scale
        self.camera = camera
        self.auto_photo_on_save = True

        # Header
        header = tk.Frame(self, bg=THEME.surface, bd=1, relief="solid")
        header.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(
            header,
            text="Báscula Digital Pro",
            font=("Arial", 18, "bold"),
            bg=THEME.surface,
            fg=THEME.primary,
        ).pack(padx=16, pady=10)

        # Display
        self.display = WeightDisplay(self)
        self.display.pack(fill="both", expand=True, padx=20, pady=10)

        # Controls
        controls = tk.Frame(self, bg=THEME.background)
        controls.pack(fill="x", padx=20, pady=10)
        ProButton(controls, text="TARA", command=self._tara).pack(
            side="left", expand=True, fill="x", padx=4
        )
        ProButton(controls, text="PLATO COMPLETO", command=self._plate).pack(
            side="left", expand=True, fill="x", padx=4
        )
        ProButton(controls, text="AÑADIR ALIMENTO", command=self._add_item).pack(
            side="left", expand=True, fill="x", padx=4
        )
        ProButton(controls, text="MENÚ", command=self._menu).pack(
            side="left", expand=True, fill="x", padx=4
        )
        ProButton(controls, text="RESET", command=self._reset, kind="warning").pack(
            side="right", padx=4
        )

        # Info
        self.info = tk.Label(
            self,
            text="Sistema iniciado",
            font=("Arial", 10),
            bg=THEME.background,
            fg=THEME.text,
        )
        self.info.pack(pady=(0, 10))

        self._tick()

    def _tick(self):
        # Lee de la báscula y actualiza la UI/estado
        try:
            fast, stable_val, info, raw = self.scale.read()
            self.state.last_weight_g = stable_val
            self.state.stable = bool(getattr(info, "is_stable", False))
            self.display.set_value(stable_val, self.state.stable)
        except Exception as e:
            # Muestra error en la barra inferior pero mantiene el loop
            self._status(f"ERR: {e}", "err")
        finally:
            self.after(200, self._tick)

    def _tara(self):
        # El servicio no devuelve bool; aplicamos siempre
        try:
            self.scale.tare()
            self._status("TARA aplicada", "ok")
        except Exception as e:
            self._status(str(e), "err")

    def _plate(self):
        # Placeholder de modo plato
        self._status("Modo plato completo", "ok")

    def _add_item(self):
        # Placeholder de añadir alimento
        self._status("Modo añadir alimento", "ok")

    def _menu(self):
        win = tk.Toplevel(self)
        win.title("Menú")
        win.configure(bg=THEME.background)
        ProButton(win, text="Historial (WIP)", kind="secondary", command=win.destroy).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(win, text="Exportar CSV", kind="secondary", command=self._export_csv).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(win, text="Ajustes", kind="secondary", command=lambda: self._settings(win)).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(win, text="Recetas guiadas (WIP)", kind="secondary", command=win.destroy).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(
            win, text="Técnico (PIN)", kind="secondary", command=lambda: self._tech_menu(win)
        ).pack(fill="x", padx=20, pady=8)
        ProButton(win, text="Cerrar", kind="danger", command=win.destroy).pack(
            fill="x", padx=20, pady=(8, 16)
        )

    def _reset(self):
        try:
            self.scale.reset()
        except Exception:
            pass
        self._status("Sesión reiniciada", "ok")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            title="Guardar CSV", defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        from pathlib import Path

        try:
            self.storage.export_csv(Path(path))
            messagebox.showinfo("Exportación", f"CSV exportado:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportación", str(e))

    def _settings(self, parent):
        # Ajustes mínimos compatibles con la config actual
        w = tk.Toplevel(parent)
        w.title("Ajustes")
        w.configure(bg=THEME.background)
        from tkinter import BooleanVar

        tk.Label(w, text="ZERO tracking (auto-cero)", bg=THEME.background).grid(
            row=0, column=0, sticky="w", padx=12, pady=6
        )
        zero_var = BooleanVar(value=self.state.cfg.filters.zero_tracking)
        tk.Checkbutton(w, variable=zero_var, bg=THEME.background).grid(
            row=0, column=1, sticky="w", padx=12, pady=6
        )

        ProButton(
            w, text="Guardar", kind="success", command=lambda: self._save_settings(w, zero_var.get())
        ).grid(row=1, column=0, padx=12, pady=(12, 12))
        ProButton(w, text="Cerrar", kind="secondary", command=w.destroy).grid(
            row=1, column=1, padx=12, pady=(12, 12), sticky="e"
        )

    def _save_settings(self, win, zero_tracking):
        try:
            self.state.cfg.filters.zero_tracking = bool(zero_tracking)
            save_config(self.state.cfg)
            self._status("Ajustes guardados", "ok")
            win.destroy()
        except Exception as e:
            messagebox.showerror("Ajustes", str(e))

    def _tech_menu(self, parent):
        # PIN simple
        kb = NumericKeyboard(parent, title="PIN Técnico")
        self.wait_window(kb)
        if kb.result != "2468":
            messagebox.showerror("Técnico", "PIN incorrecto")
            return
        # Menú técnico (Calibración y diagnósticos)
        w = tk.Toplevel(parent)
        w.title("Técnico")
        w.configure(bg=THEME.background)
        ProButton(w, text="Calibración", kind="warning", command=lambda: self._calibrate(w)).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(w, text="Diagnóstico", kind="secondary", command=self._diagnostics).pack(
            fill="x", padx=20, pady=8
        )
        ProButton(w, text="Cerrar", kind="danger", command=w.destroy).pack(
            fill="x", padx=20, pady=(8, 16)
        )

    def _calibrate(self, parent):
        kb = NumericKeyboard(parent, title="Peso de calibración (g)", initial="1000")
        self.wait_window(kb)
        if not kb.result:
            return
        try:
            known = float(kb.result)
            if known <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Calibración", "Valor inválido")
            return

        try:
            new_ref = self.scale.calibrate_with_known_weight(known_weight_g=known, settle_ms=1200)
            self.state.cfg.hardware.reference_unit = new_ref
            save_config(self.state.cfg)
            messagebox.showinfo("Calibración", f"reference_unit = {new_ref:.8f}\nGuardado en config")
        except Exception as e:
            messagebox.showerror("Calibración", str(e))

    def _diagnostics(self):
        cam_ok = getattr(self.camera, "available", None)
        cam_txt = "N/D" if cam_ok is None else ("OK" if cam_ok else "NO")
        msg = (
            "DIAGNÓSTICO\n\n"
            f"HX711 backend: {self.scale.get_backend_name()}\n"
            f"Cámara: {cam_txt}\n\n"
            f"Último peso: {self.state.last_weight_g:.1f} g\n"
            f"Estable: {'SÍ' if self.state.stable else 'NO'}\n"
            f"Zero-tracking: {'ON' if self.state.cfg.filters.zero_tracking else 'OFF'}\n"
        )
        messagebox.showinfo("Diagnóstico", msg)

    # Guardado con foto (ejemplo de uso)
    def _save_measurement(self):
        w = round(self.state.last_weight_g, 2)
        photo = ""
        if self.auto_photo_on_save:
            photo = self.camera.capture(w) or ""
        rec = {
            "timestamp": datetime.now().isoformat(),
            "weight": w,
            "unit": "g",
            "stable": bool(self.state.stable),
            "photo": photo,
        }
        self.storage.append_measurement(rec)
        self._status("Medición guardada", "ok")

