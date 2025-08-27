from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass

from ..config.settings import AppSettings
from ..domain.filters import ProfessionalWeightFilter
from ..services.scale import ScaleService
from .widgets import ProButton, WeightDisplay
from .keyboard import OnScreenKeyboard


@dataclass
class UIState:
    in_calibration: bool = False
    last_stable: bool = False
    ref_weight_g: float = 1000.0
    raw_zero: float | None = None
    raw_span: float | None = None


class SmartBasculaApp(tk.Tk):
    def __init__(self, settings: AppSettings, scale: ScaleService):
        super().__init__()
        self.settings = settings
        self.scale = scale
        self.state = UIState()
        self.title(self.settings.ui.title)

        self.geometry("1000x600")
        self.configure(bg="#f7f7f7")

        fs = settings.filters
        self.filter = ProfessionalWeightFilter(
            fast_alpha=fs.fast_alpha,
            stable_alpha=fs.stable_alpha,
            stability_window=fs.stability_window,
            stability_threshold=fs.stability_threshold,
        )

        self._build_main()
        self.after(80, self._tick)

    def _build_main(self):
        s = self.settings.ui.button_size
        top = tk.Frame(self, bg=self["bg"])
        top.pack(fill="both", expand=True, padx=20, pady=20)

        self.weight_display = WeightDisplay(top, bg="#ffffff")
        self.weight_display.pack(fill="x", pady=10, ipady=20)

        btns = tk.Frame(top, bg=self["bg"])
        btns.pack(fill="x", pady=12)

        ProButton(btns, text="TARA", size=s, command=self._on_tare).pack(side="left", expand=True, fill="x", padx=8)
        ProButton(btns, text="PLATO COMPLETO", size=s, command=self._on_plato).pack(side="left", expand=True, fill="x", padx=8)
        ProButton(btns, text="AÑADIR ALIMENTO", size=s, command=self._on_add_food).pack(side="left", expand=True, fill="x", padx=8)
        ProButton(btns, text="MENÚ", size=s, command=self._on_menu).pack(side="left", expand=True, fill="x", padx=8)
        ProButton(btns, text="RESET", size=s, command=self._on_reset).pack(side="left", expand=True, fill="x", padx=8)

    def _open_menu(self):
        win = tk.Toplevel(self)
        win.title("Menú principal")
        s = self.settings.ui.button_size
        ProButton(win, text="Historial (próx.)", size=s).pack(fill="x", padx=12, pady=8)
        ProButton(win, text="Exportar CSV (próx.)", size=s).pack(fill="x", padx=12, pady=8)
        ProButton(win, text="Ajustes (próx.)", size=s).pack(fill="x", padx=12, pady=8)
        ProButton(win, text="Técnico", size=s, command=lambda: self._open_tech(win)).pack(fill="x", padx=12, pady=8)

    def _open_tech(self, parent):
        dlg = tk.Toplevel(parent)
        dlg.title("Técnico – PIN")
        kb = OnScreenKeyboard(dlg, big=self.settings.ui.keyboard_big, on_submit=lambda v: self._check_pin(dlg, v))
        kb.pack(fill="both", expand=True)

    def _check_pin(self, dlg, value: str):
        try:
            ok = int(value) == int(self.settings.ui.tech_pin)
        except Exception:
            ok = False
        if not ok:
            messagebox.showerror("PIN", "PIN incorrecto")
            return
        dlg.destroy()
        self._open_calibration()

    def _open_calibration(self):
        self.state = UIState(in_calibration=True, ref_weight_g=1000.0, raw_zero=None, raw_span=None)
        win = tk.Toplevel(self)
        win.title("Calibración (2 puntos)")
        s = self.settings.ui.button_size

        lbl = tk.Label(win, text="Introduce peso patrón (g)", font=("Arial", 16, "bold"))
        lbl.pack(pady=8)

        ent_var = tk.StringVar(value=str(int(self.state.ref_weight_g)))
        ent = tk.Entry(win, textvariable=ent_var, font=("Arial", 20), justify="center")
        ent.pack(pady=6)

        steps = tk.Frame(win)
        steps.pack(fill="x", padx=10, pady=10)

        ProButton(steps, text="1) Aceptar CERO (sin peso)", size=s, command=lambda: self._accept_zero(win)).pack(fill="x", pady=6)
        ProButton(steps, text="2) Coloca patrón, esperar ESTABLE y Aceptar", size=s, command=lambda: self._accept_span(win)).pack(fill="x", pady=6)

        def on_change(v):
            try:
                self.state.ref_weight_g = max(1.0, float(v))
            except Exception:
                pass

        kb = OnScreenKeyboard(win, big=True, on_submit=lambda v: None, on_change=on_change)
        kb.set(ent_var.get())
        kb.pack(fill="both", expand=True, pady=6)

        ProButton(win, text="Guardar y salir", size=s, command=lambda: self._finish_calibration(win)).pack(fill="x", pady=10)

    def _accept_zero(self, win):
        raw = self.scale.read_raw(samples=16)
        self.state.raw_zero = raw
        messagebox.showinfo("Calibración", f"CERO aceptado.\nRaw cero = {raw:0.1f}")

    def _accept_span(self, win):
        stable_count = 0
        need = max(3, int(self.settings.filters.stability_window * 0.8))
        while True:
            grams = self.scale.get_weight_g(samples=4)
            _, _, info = self.filter.update(grams)
            self.weight_display.set_weight(grams, info.is_stable)
            self.update_idletasks()
            self.after(80)
            if info.is_stable:
                stable_count += 1
                if stable_count >= need:
                    break
            else:
                stable_count = 0
        raw = self.scale.read_raw(samples=16)
        self.state.raw_span = raw
        messagebox.showinfo("Calibración", f"SPAN aceptado.\nRaw span = {raw:0.1f}")

    def _finish_calibration(self, win):
        if self.state.raw_zero is None or self.state.raw_span is None:
            messagebox.showwarning("Calibración", "Falta aceptar CERO y/o SPAN.")
            return
        try:
            self.scale.calibrate_two_points(self.state.raw_zero, self.state.raw_span, self.state.ref_weight_g)
        except Exception as e:
            messagebox.showerror("Calibración", str(e))
            return

        self.settings.calibration.base_offset = self.scale.cal.base_offset
        self.settings.calibration.scale_factor = self.scale.cal.scale_factor
        self.settings.calibration.last_ref_weight_g = self.state.ref_weight_g
        self.settings.save()

        self.state.in_calibration = False
        win.destroy()
        messagebox.showinfo("Calibración", f"Listo.\nbase_offset={self.scale.cal.base_offset:0.2f}\nscale_factor={self.scale.cal.scale_factor:0.6f}")

    def _on_tare(self):
        self.scale.tare()

    def _on_plato(self):
        messagebox.showinfo("Plato completo", "Función no implementada aún.")

    def _on_add_food(self):
        messagebox.showinfo("Añadir alimento", "Función no implementada aún.")

    def _on_menu(self):
        self._open_menu()

    def _on_reset(self):
        self.scale.clear_tare()
        self.filter.reset()

    def _tick(self):
        grams = self.scale.get_weight_g(samples=4)
        _, stable_val, info = self.filter.update(grams)
        self.weight_display.set_weight(stable_val, info.is_stable)
        self.after(80, self._tick)


def run_app():
    settings = AppSettings.load()
    scale = ScaleService()

    cal = settings.calibration
    if cal.base_offset is not None and cal.scale_factor is not None:
        scale.cal.base_offset = cal.base_offset
        scale.cal.scale_factor = cal.scale_factor

    app = SmartBasculaApp(settings, scale)
    app.mainloop()
