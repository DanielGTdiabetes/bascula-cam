"""Interactive food scanner view using camera + AI recognition."""
from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from ...domain.food_items import FoodItem
from ...services.nutrition_ai import (
    NutritionAIAuthError,
    NutritionAIError,
    NutritionAIServiceError,
    analyze_food,
)
from ..theme_neo import COLORS, SPACING, font_sans

logger = logging.getLogger(__name__)


class FoodScannerView(tk.Toplevel):
    """Toplevel window that orchestrates camera capture and AI analysis."""

    def __init__(self, controller, scale, camera=None, tts=None) -> None:
        super().__init__(controller.root if hasattr(controller, "root") else controller)
        self.title("Escáner de alimentos")
        self.configure(bg=COLORS["bg"], padx=SPACING["lg"], pady=SPACING["lg"])
        self.transient(controller.root if hasattr(controller, "root") else controller)
        self.resizable(False, False)

        self.controller = controller
        self.scale = scale
        self.camera = camera
        self.tts = tts

        self._current_weight: float = 0.0
        self._stable: bool = False
        self._items: Dict[str, FoodItem] = {}
        self._busy = False

        self._weight_var = tk.StringVar(value="0.0 g")
        self._stable_var = tk.StringVar(value="Inestable")
        self._status_var = tk.StringVar(value="")
        self._totals_var = tk.StringVar(value="Carbs: 0 g · Proteínas: 0 g · Grasas: 0 g · GI medio: -")

        self._build_layout()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.scale.subscribe(self._on_scale_update)
        except Exception:
            logger.debug("No se pudo suscribir a la báscula")
        self.after(100, self._update_weight_label)
        try:
            self.grab_set()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            header,
            text="Peso en vivo",
            font=font_sans(24, "bold"),
            fg=COLORS["text"],
            bg=COLORS["bg"],
        ).pack(anchor="w")

        weight_frame = tk.Frame(self, bg=COLORS["surface"], padx=SPACING["lg"], pady=SPACING["lg"], bd=0)
        weight_frame.pack(fill="x", pady=(0, SPACING["md"]))
        tk.Label(
            weight_frame,
            textvariable=self._weight_var,
            font=font_sans(48, "bold"),
            fg=COLORS["primary"],
            bg=COLORS["surface"],
        ).pack(side="left")
        tk.Label(
            weight_frame,
            textvariable=self._stable_var,
            font=font_sans(16, "bold"),
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            padx=SPACING["lg"],
        ).pack(side="right")

        actions = tk.Frame(self, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(0, SPACING["md"]))
        self._recognize_btn = tk.Button(
            actions,
            text="📷 Reconocer",
            font=font_sans(18, "bold"),
            command=self._handle_recognize,
            bg=COLORS["primary"],
            fg=COLORS["bg"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["text"],
            relief="flat",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        )
        self._recognize_btn.pack(side="left")

        self._status_label = tk.Label(
            actions,
            textvariable=self._status_var,
            font=font_sans(12),
            fg=COLORS["muted"],
            bg=COLORS["bg"],
        )
        self._status_label.pack(side="right")

        table_frame = tk.Frame(self, bg=COLORS["bg"])
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "weight", "carbs", "protein", "fat", "gi")
        self._tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=8,
        )
        self._tree.heading("name", text="Alimento")
        self._tree.heading("weight", text="Peso (g)")
        self._tree.heading("carbs", text="Carbs (g)")
        self._tree.heading("protein", text="Proteínas (g)")
        self._tree.heading("fat", text="Grasas (g)")
        self._tree.heading("gi", text="GI")
        self._tree.column("name", width=200, anchor="w")
        for key in columns[1:]:
            self._tree.column(key, width=100, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        totals = tk.Label(
            self,
            textvariable=self._totals_var,
            font=font_sans(14, "bold"),
            fg=COLORS["text"],
            bg=COLORS["bg"],
            pady=SPACING["sm"],
        )
        totals.pack(fill="x")

        footer = tk.Frame(self, bg=COLORS["bg"])
        footer.pack(fill="x", pady=(SPACING["md"], 0))
        tk.Button(
            footer,
            text="Eliminar seleccionado",
            command=self._handle_remove,
            font=font_sans(14, "bold"),
            bg=COLORS["surface"],
            fg=COLORS["text"],
            relief="flat",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        ).pack(side="left")
        tk.Button(
            footer,
            text="Terminar",
            command=self._handle_finish,
            font=font_sans(16, "bold"),
            bg=COLORS["primary"],
            fg=COLORS["bg"],
            relief="flat",
            padx=SPACING["lg"],
            pady=SPACING["sm"],
        ).pack(side="right")

    # ------------------------------------------------------------------
    def _on_scale_update(self, weight: float, stable: bool) -> None:
        self._current_weight = float(weight)
        self._stable = bool(stable)
        try:
            self.after(0, self._update_weight_label)
        except Exception:
            pass

    def _update_weight_label(self) -> None:
        self._weight_var.set(f"{self._current_weight:.1f} g")
        self._stable_var.set("Estable" if self._stable else "Inestable")

    # ------------------------------------------------------------------
    def _handle_recognize(self) -> None:
        if self._busy:
            return
        if not self.camera or not getattr(self.camera, "available", lambda: False)():
            messagebox.showerror("Cámara", "Cámara no disponible")
            return
        weight = self._current_weight
        if weight <= 0:
            messagebox.showinfo("Reconocer", "Coloca alimento en la báscula antes de reconocer")
            return

        self._busy = True
        self._recognize_btn.configure(state="disabled")
        self._set_status("Capturando imagen…")

        def worker() -> None:
            result = None
            error: Optional[str] = None
            try:
                try:
                    if hasattr(self.camera, "set_mode"):
                        self.camera.set_mode("foodshot")
                except Exception:
                    pass
                jpeg, _thumb = self.camera.capture_snapshot()
                result = analyze_food(jpeg, weight)
            except NutritionAIAuthError as exc:
                error = str(exc)
            except NutritionAIServiceError as exc:
                error = str(exc)
            except TimeoutError:
                error = "La captura tardó demasiado"
            except NutritionAIError as exc:
                error = str(exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Reconocimiento falló: %s", exc)
                error = f"No se pudo reconocer: {exc}"

            def done() -> None:
                self._busy = False
                self._recognize_btn.configure(state="normal")
                if error:
                    self._set_status(error, error=True)
                    return
                if result is None:
                    self._set_status("Sin datos de IA", error=True)
                    return
                item = FoodItem.from_ai(weight, {**result, "ts": time.time()})
                self._items[item.id] = item
                self._tree.insert(
                    "",
                    "end",
                    iid=item.id,
                    values=(
                        item.name,
                        f"{item.weight_g:.1f}",
                        _fmt(item.carbs_g),
                        _fmt(item.protein_g),
                        _fmt(item.fat_g),
                        item.gi if item.gi is not None else "-",
                    ),
                )
                self._set_status(f"{item.name} añadido ({item.source})")
                self._update_totals()

            try:
                self.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, name="FoodRecognize", daemon=True).start()

    # ------------------------------------------------------------------
    def _handle_remove(self) -> None:
        selected = list(self._tree.selection())
        if not selected:
            return
        for iid in selected:
            self._tree.delete(iid)
            self._items.pop(iid, None)
        self._update_totals()
        self._set_status("Elemento eliminado")

    def _handle_finish(self) -> None:
        if not self._items:
            messagebox.showinfo("Resumen", "No hay alimentos reconocidos aún")
            return
        totals = self._compute_totals()
        SummaryDialog(self, totals, list(self._items.values()))
        self._speak_summary(totals)

    def _speak_summary(self, totals: Dict[str, Optional[float]]) -> None:
        lines = []
        carbs = totals.get("carbs")
        protein = totals.get("protein")
        fat = totals.get("fat")
        gi = totals.get("gi")
        if carbs is not None:
            lines.append(f"Carbohidratos {carbs:.1f} gramos")
        if protein is not None:
            lines.append(f"Proteínas {protein:.1f} gramos")
        if fat is not None:
            lines.append(f"Grasas {fat:.1f} gramos")
        if gi is not None:
            lines.append(f"Índice glucémico medio {gi:.0f}")
        if not lines:
            return
        text = ", ".join(lines)
        try:
            if self.tts and hasattr(self.tts, "speak_text"):
                self.tts.speak_text(text)
            elif self.tts and hasattr(self.tts, "speak"):
                self.tts.speak(text)
        except Exception:
            logger.debug("No se pudo reproducir resumen TTS")

    # ------------------------------------------------------------------
    def _compute_totals(self) -> Dict[str, Optional[float]]:
        carbs = sum(item.carbs_g or 0.0 for item in self._items.values())
        protein = sum(item.protein_g or 0.0 for item in self._items.values())
        fat = sum(item.fat_g or 0.0 for item in self._items.values())
        gi_values = [item.gi for item in self._items.values() if item.gi is not None]
        gi_avg = (sum(gi_values) / len(gi_values)) if gi_values else None
        return {
            "carbs": carbs,
            "protein": protein,
            "fat": fat,
            "gi": gi_avg,
        }

    def _update_totals(self) -> None:
        totals = self._compute_totals()
        gi_text = f"{totals['gi']:.0f}" if totals["gi"] is not None else "-"
        self._totals_var.set(
            "Carbs: {0:.1f} g · Proteínas: {1:.1f} g · Grasas: {2:.1f} g · GI medio: {3}".format(
                totals["carbs"], totals["protein"], totals["fat"], gi_text
            )
        )

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status_var.set(text)
        self._status_label.configure(fg=COLORS["danger"] if error else COLORS["muted"])

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        try:
            self.scale.unsubscribe(self._on_scale_update)
        except Exception:
            pass
        self.destroy()


class SummaryDialog(tk.Toplevel):
    """Simple overlay summarising totals and individual items."""

    def __init__(self, parent, totals: Dict[str, Optional[float]], items: List[FoodItem]) -> None:
        super().__init__(parent)
        self.title("Resumen de alimentos")
        self.configure(bg=COLORS["surface"], padx=SPACING["lg"], pady=SPACING["lg"])
        self.resizable(False, False)
        self.transient(parent)

        tk.Label(
            self,
            text="Resumen nutricional",
            font=font_sans(22, "bold"),
            fg=COLORS["text"],
            bg=COLORS["surface"],
        ).pack(anchor="w", pady=(0, SPACING["md"]))

        lines = [
            f"Carbohidratos: {totals['carbs']:.1f} g",
            f"Proteínas: {totals['protein']:.1f} g",
            f"Grasas: {totals['fat']:.1f} g",
            f"GI medio: {totals['gi']:.0f}" if totals["gi"] is not None else "GI medio: -",
        ]
        for line in lines:
            tk.Label(
                self,
                text=line,
                font=font_sans(16, "bold"),
                fg=COLORS["text"],
                bg=COLORS["surface"],
            ).pack(anchor="w")

        if items:
            tk.Label(
                self,
                text="Detalle",
                font=font_sans(18, "bold"),
                fg=COLORS["muted"],
                bg=COLORS["surface"],
                pady=SPACING["sm"],
            ).pack(anchor="w")
            for item in items:
                desc = (
                    f"• {item.name} · {item.weight_g:.1f} g · "
                    f"C:{_fmt(item.carbs_g)} g · P:{_fmt(item.protein_g)} g · "
                    f"G:{_fmt(item.fat_g)} g · GI {item.gi if item.gi is not None else '-'}"
                )
                tk.Label(
                    self,
                    text=desc,
                    font=font_sans(14),
                    fg=COLORS["text"],
                    bg=COLORS["surface"],
                ).pack(anchor="w")

        tk.Button(
            self,
            text="Cerrar",
            command=self.destroy,
            font=font_sans(14, "bold"),
            bg=COLORS["primary"],
            fg=COLORS["bg"],
            relief="flat",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        ).pack(pady=(SPACING["md"], 0), anchor="e")


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}"


__all__ = ["FoodScannerView", "SummaryDialog"]
