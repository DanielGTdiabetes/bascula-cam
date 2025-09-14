# bascula/ui/overlay_weight.py
from __future__ import annotations

import tkinter as tk
from collections import deque
from pathlib import Path
import json

from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    COL_CARD, COL_TEXT, COL_ACCENT, COL_DANGER, FS_TEXT,
    BigButton, WeightLabel,
)
from bascula.domain.foods import load_foods


class WeightOverlay(OverlayBase):
    """Overlay de peso con estabilidad y sugerencia proactiva (visión)."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._buf = deque(maxlen=10)
        self._tick_after = None
        self._vision_after = None
        self._stable = False
        self._last_detection = None
        self._foods = []
        self._aliases = {}

        c = self.content()
        c.configure(padx=18, pady=18)

        self.lbl = WeightLabel(c, bg=COL_CARD, fg=COL_ACCENT)
        self.lbl.pack(fill="x", padx=8, pady=8)

        self.stab = tk.Label(c, text="Moviendo...", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
        self.stab.pack(pady=(0, 12))

        # Sugerencia por visión (botón proactivo)
        self.suggestion_frame = tk.Frame(c, bg=COL_CARD)
        self.suggestion_frame.pack(fill="x", pady=(0, 12))

        btns = tk.Frame(c, bg=COL_CARD)
        btns.pack(fill="x", pady=(12, 0))
        BigButton(btns, text="Tara", command=self._on_tare).pack(side="left", expand=True, fill="x", padx=(0, 4))
        BigButton(btns, text="Cerrar", command=self.hide, bg=COL_DANGER).pack(side="right", expand=True, fill="x", padx=(4, 0))

    # --- lifecycle ---
    def _open(self):
        if getattr(self, "_running", False):
            return
        self._running = True
        self._stable = False
        self._buf.clear()
        self._last_detection = None
        # Cargar foods y alias
        try:
            self._foods = load_foods()
        except Exception:
            self._foods = []
        try:
            p = Path.home() / ".config" / "bascula" / "vision_aliases.json"
            self._aliases = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            self._aliases = {}
        self._clear_suggestion()

        self.after(0, self._tick)
        # Iniciar visión si está activada
        try:
            if bool(getattr(self.app, "get_cfg", lambda: {})().get("vision_autosuggest_enabled", False)):
                self.after(400, self._vision_loop)
        except Exception:
            pass

    def _close(self):
        self._running = False
        try:
            if self._tick_after:
                self.after_cancel(self._tick_after)
        except Exception:
            pass
        try:
            if self._vision_after:
                self.after_cancel(self._vision_after)
        except Exception:
            pass
        self._tick_after = None
        self._vision_after = None
        self._clear_suggestion()

    def show(self):
        self._open()
        return super().show()

    def hide(self):
        self._close()
        return super().hide()

    def _on_tare(self):
        try:
            reader = self.app.get_reader() if hasattr(self.app, "get_reader") else getattr(self.app, "reader", None)
            tare = self.app.get_tare() if hasattr(self.app, "get_tare") else getattr(self.app, "tare", None)
            if reader and tare:
                if hasattr(reader, "send_command"):
                    try:
                        reader.send_command("T")
                    except Exception:
                        pass
                current_raw = reader.get_latest() if hasattr(reader, "get_latest") else None
                if current_raw is not None:
                    tare.set_tare(current_raw)
        except Exception:
            pass

    # Mantener compatibilidad con código antiguo
    def open(self):  # pragma: no cover - alias
        return self.show()

    def close(self):  # pragma: no cover - alias
        return self.hide()

    # --- helpers ---
    def _get_weight(self) -> float:
        # Preferir app.get_latest_weight() para tener tara aplicada
        try:
            if hasattr(self.app, "get_latest_weight"):
                return float(self.app.get_latest_weight())
        except Exception:
            pass
        try:
            if self.app.reader and hasattr(self.app.reader, "get_latest"):
                return float(self.app.reader.get_latest())
        except Exception:
            pass
        return 0.0

    def _is_stable(self) -> bool:
        if len(self._buf) < self._buf.maxlen:
            return False
        arr = list(self._buf)
        span = max(arr) - min(arr)
        return span <= 2.0  # +/- 1 g

    def _beep(self):
        try:
            if getattr(self.app, "audio", None):
                self.app.audio.play_event("stable")
        except Exception:
            pass

    # --- loops ---
    def _tick(self):
        w = self._get_weight()
        self._buf.append(w)
        try:
            self.lbl.configure(text=f"{w:.0f}g")
        except Exception:
            self.lbl.configure(text=f"{w}g")
        was_stable = self._stable
        is_stable = self._is_stable()
        self._stable = is_stable
        self.stab.configure(text=("Estable" if is_stable else "Moviendo..."))
        if is_stable and not was_stable:
            self._beep()
            # Limpiar sugerencia previa en transición
            self._clear_suggestion()
        self._tick_after = self.after(120, self._tick)

    def _vision_loop(self):
        try:
            if not getattr(self, "_running", False):
                return
            vs = getattr(self.app, "vision_service", None)
            cam = getattr(self.app, "camera", None)
            if not vs or not cam or not hasattr(cam, "grab_frame"):
                self._vision_after = self.after(1200, self._vision_loop)
                return
            try:
                min_w = float(self.app.get_cfg().get("vision_min_weight_g", 20) or 20)
            except Exception:
                min_w = 20.0
            if self._stable and self._get_weight() >= min_w:
                img = cam.grab_frame()
                if img is not None:
                    res = vs.classify_image(img)
                    if res and res != self._last_detection:
                        self._last_detection = res
                        label, _ = res
                        self._show_suggestion(label)
            self._vision_after = self.after(800, self._vision_loop)
        except Exception:
            try:
                self._vision_after = self.after(1200, self._vision_loop)
            except Exception:
                pass

    # --- UI: sugerencia ---
    def _clear_suggestion(self):
        try:
            for w in list(self.suggestion_frame.winfo_children()):
                w.destroy()
        except Exception:
            pass

    def _show_suggestion(self, raw_label: str):
        self._clear_suggestion()
        label = (raw_label or "").strip()
        # Aplicar alias opcional (archivo JSON en ~/.config/bascula/vision_aliases.json)
        try:
            alias = (self._aliases.get(label.lower()) or self._aliases.get(label)) if isinstance(self._aliases, dict) else None
        except Exception:
            alias = None
        name = str(alias or label)
        food = self._find_food_by_name(name)
        if not food:
            return

        def _add():
            weight = max(0.0, float(self._get_weight()))
            if weight <= 0:
                return
            item = {
                "name": food.name,
                "grams": weight,
                "kcal": (food.kcal / 100.0) * weight,
                "carbs": (food.carbs / 100.0) * weight,
                "protein": (food.protein / 100.0) * weight,
                "fat": (food.fat / 100.0) * weight,
            }
            # Delegar en FocusScreen si tiene hook
            try:
                if hasattr(self.master, "_on_add_food"):
                    self.master._on_add_food(item)
            except Exception:
                pass
            self._clear_suggestion()

        try:
            txt = f"¿Añadir {food.name}?"
            BigButton(self.suggestion_frame, text=txt, command=_add, bg=COL_ACCENT, small=True).pack(fill="x")
        except Exception:
            pass

    def _find_food_by_name(self, name: str):
        n = (name or "").strip().lower()
        if not n:
            return None
        for f in (self._foods or []):
            try:
                fn = f.name.lower()
                if fn.startswith(n) or n.startswith(fn):
                    return f
            except Exception:
                pass
        for f in (self._foods or []):
            try:
                fn = f.name.lower()
                if n in fn or fn in n:
                    return f
            except Exception:
                pass
        return None

