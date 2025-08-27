import tkinter as tk
from bascula.ui.extras.modern_theme import THEME_MODERN as MT
from bascula.ui.extras.weight_display_modern import AnimatedWeightDisplay
from bascula.ui.extras.status_panel import StatusPanel
from bascula.ui.extras.modern_button import ModernButton

class ModernHome(tk.Frame):
    def __init__(self, root, state, storage, logger, scale, camera):
        super().__init__(root, bg=MT.background)
        self.state = state; self.storage = storage; self.logger = logger
        self.scale = scale; self.camera = camera

        header = tk.Frame(self, bg=MT.surface, bd=1, relief="solid",
                          highlightbackground=MT.surface_light, highlightthickness=1)
        header.pack(fill="x", padx=16, pady=(16,8))
        tk.Label(header, text="⚖️ SMART SCALE PRO", font=("Segoe UI", 18, "bold"),
                 fg=MT.text, bg=MT.surface).pack(side="left", padx=12, pady=8)

        self.disp = AnimatedWeightDisplay(self); self.disp.pack(fill="x")
        self.stats = StatusPanel(self); self.stats.pack(fill="x")

        btns = tk.Frame(self, bg=MT.background); btns.pack(fill="x", padx=16, pady=8)
        ModernButton(btns, "🔄 TARA", lambda: self.scale.tara(), "success", "lg", width=16).pack(side="left", padx=(0,8))
        ModernButton(btns, "💾 GUARDAR", self._save, "primary", "lg", width=16).pack(side="left", padx=4)
        ModernButton(btns, "MENÚ", lambda: None, "secondary", "lg", width=10).pack(side="left", padx=4)
        ModernButton(btns, "RESET", self._reset, "warning", "lg", width=10).pack(side="left", padx=4)

        self.after(200, self._tick)

    def _tick(self):
        # Compose a confidence proxy using filter stability and buffer length (0..1)
        filt = self.scale.filter
        confidence = 1.0 if getattr(filt, "stable", False) else 0.6
        self.disp.set(self.state.current_weight, filt.stable, confidence)
        if abs(self.state.current_weight) > 0.5:
            self.stats.update(self.state.current_weight)
        self.after(200, self._tick)

    def _save(self):
        # simple save hook using storage
        from datetime import datetime
        rec = {"timestamp": datetime.now().isoformat(),
               "weight": round(self.state.current_weight, 1),
               "unit":"g", "stable": self.scale.filter.stable}
        try:
            self.storage.append_measurement(rec)
        except Exception as e:
            self.logger.error(f"save error: {e}")

    def _reset(self):
        self.stats.reset()
