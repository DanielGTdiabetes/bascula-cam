"""Interactive food scanner view using camera + AI recognition."""
from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from ...domain.food_items import FoodItem
from ...services import barcode as barcode_service
from ...services import fatsecret
from ...services.nutrition_ai import (
    NutritionAIAuthError,
    NutritionAIError,
    NutritionAIServiceError,
    analyze_food,
)
from ..messages import MEDICAL_DISCLAIMER
from ..theme_neo import COLORS, SPACING, font_sans
from ..windowing import apply_kiosk_to_toplevel

logger = logging.getLogger(__name__)


class FoodScannerView(tk.Toplevel):
    """Toplevel window that orchestrates camera capture and AI analysis."""

    def __init__(self, controller, scale, camera=None, tts=None) -> None:
        super().__init__(controller.root if hasattr(controller, "root") else controller)
        apply_kiosk_to_toplevel(self)
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
        self._barcode_icon = _create_barcode_icon()
        self._barcode_btn: Optional[tk.Button] = None

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

        self._barcode_btn = tk.Button(
            actions,
            text="Escanear código",
            image=self._barcode_icon,
            compound="left",
            font=font_sans(18, "bold"),
            command=self._handle_scan_barcode,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"],
            relief="flat",
            padx=SPACING["md"],
            pady=SPACING["sm"],
        )
        self._barcode_btn.pack(side="left", padx=(SPACING["sm"], 0))

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

        disclaimer = tk.Label(
            self,
            text=MEDICAL_DISCLAIMER,
            font=font_sans(11),
            fg=COLORS["muted"],
            bg=COLORS["bg"],
            justify="left",
            wraplength=820,
        )
        disclaimer.pack(fill="x", pady=(SPACING["sm"], 0))
        self._disclaimer_label = disclaimer

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

        self._set_busy_state(True)
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
                self._set_busy_state(False)
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

    def _set_busy_state(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        try:
            self._recognize_btn.configure(state=state)
        except Exception:
            pass
        if self._barcode_btn is not None:
            try:
                self._barcode_btn.configure(state=state)
            except Exception:
                pass

    def _handle_scan_barcode(self) -> None:
        if self._busy:
            return
        if not self.camera or not getattr(self.camera, "available", lambda: False)():
            messagebox.showerror("Cámara", "Cámara no disponible")
            return
        weight = self._current_weight
        if weight <= 0:
            messagebox.showinfo("Escanear código", "Coloca el producto en la báscula antes de escanear")
            return

        self._set_busy_state(True)
        self._set_status("Buscando código de barras…")

        def worker() -> None:
            payload: Optional[Dict[str, Any]] = None
            error: Optional[str] = None
            try:
                code = barcode_service.scan(self.camera, timeout_s=6)
                if not code:
                    code = barcode_service.decode_snapshot(self.camera)
                if not code:
                    error = "Código no detectado"
                else:
                    fat_data = fatsecret.macros_for_weight(code, weight)
                    if fat_data and fat_data.get("resolved"):
                        name = str(fat_data.get("name") or code)
                        payload = {
                            "name": name,
                            "carbs_g": fat_data.get("carbs_g"),
                            "protein_g": fat_data.get("protein_g"),
                            "fat_g": fat_data.get("fat_g"),
                            "gi": None,
                            "source": "FatSecret",
                        }
                    else:
                        name_hint = None
                        if fat_data:
                            name_hint = fat_data.get("name")
                            if not name_hint:
                                raw = fat_data.get("raw") or {}
                                if isinstance(raw, dict):
                                    name_hint = raw.get("name") or raw.get("raw_name")
                        if not name_hint:
                            lookup = fatsecret.lookup_barcode(code)
                            if lookup:
                                name_hint = lookup.get("name") or lookup.get("raw_name")
                        if not name_hint:
                            name_hint = f"Código {code}"
                        try:
                            self.after(0, lambda: self._set_status("FatSecret sin datos, consultando IA…"))
                        except Exception:
                            pass
                        ai_data = analyze_food(b"", weight, description=name_hint)
                        payload = {
                            "name": name_hint,
                            "carbs_g": ai_data.get("carbs_g"),
                            "protein_g": ai_data.get("protein_g"),
                            "fat_g": ai_data.get("fat_g"),
                            "gi": ai_data.get("gi"),
                            "source": "ChatGPT",
                            "confidence": ai_data.get("confidence"),
                        }
            except NutritionAIAuthError as exc:
                error = str(exc)
            except NutritionAIServiceError as exc:
                error = str(exc)
            except NutritionAIError as exc:
                error = str(exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Escaneo de código falló: %s", exc)
                error = f"No se pudo escanear: {exc}"

            def done() -> None:
                self._set_busy_state(False)
                if error:
                    self._set_status(error, error=True)
                    return
                if payload is None:
                    self._set_status("Código no detectado", error=True)
                    return
                item_data = dict(payload)
                item_data.setdefault("gi", None)
                item_data.setdefault("source", "FatSecret")
                item_data["ts"] = time.time()
                item = FoodItem.from_ai(weight, item_data)
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

        threading.Thread(target=worker, name="BarcodeScan", daemon=True).start()

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
        bolus_info = self._resolve_bolus_info(totals)
        SummaryDialog(
            self,
            totals,
            list(self._items.values()),
            bolus_info=bolus_info,
            disclaimer=MEDICAL_DISCLAIMER,
        )
        self._speak_summary(totals, bolus_info)
        if bolus_info:
            message = bolus_info.get("text") or bolus_info.get("error")
            if message:
                self._set_status(str(message), error=bool(bolus_info.get("error")))

    def _speak_summary(
        self, totals: Dict[str, Optional[float]], bolus_info: Optional[Dict[str, object]]
    ) -> None:
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
        if bolus_info:
            voice_line = bolus_info.get("voice") or bolus_info.get("error")
            if voice_line:
                lines.append(str(voice_line))
        lines.append("Recuerda que es una estimación, no es consejo médico.")
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

    def _resolve_bolus_info(
        self, totals: Dict[str, Optional[float]]
    ) -> Optional[Dict[str, object]]:
        compute = getattr(self.controller, "compute_bolus_recommendation", None)
        if callable(compute):
            try:
                return compute(totals, list(self._items.values()))
            except Exception as exc:
                logger.debug("No se pudo calcular bolo: %s", exc)
        return None

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        try:
            self.scale.unsubscribe(self._on_scale_update)
        except Exception:
            pass
        self.destroy()


class SummaryDialog(tk.Toplevel):
    """Simple overlay summarising totals and individual items."""

    def __init__(
        self,
        parent,
        totals: Dict[str, Optional[float]],
        items: List[FoodItem],
        *,
        bolus_info: Optional[Dict[str, object]] = None,
        disclaimer: str = MEDICAL_DISCLAIMER,
    ) -> None:
        super().__init__(parent)
        apply_kiosk_to_toplevel(self)
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

        if bolus_info:
            msg = bolus_info.get("text") or bolus_info.get("error")
            color = COLORS["danger"] if bolus_info.get("error") else COLORS["primary"]
            if msg:
                tk.Label(
                    self,
                    text=str(msg),
                    font=font_sans(14, "bold"),
                    fg=color,
                    bg=COLORS["surface"],
                    wraplength=560,
                    justify="left",
                ).pack(anchor="w", pady=(SPACING["md"], 0))

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

        tk.Label(
            self,
            text=disclaimer,
            font=font_sans(11),
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(SPACING["sm"], 0))


def _create_barcode_icon() -> Optional[tk.PhotoImage]:
    try:
        icon = tk.PhotoImage(width=32, height=32)
    except Exception:
        return None
    try:
        icon.put("#f7f9fc", to=(0, 0, 32, 32))
        accent = "#1e88e5"
        dark = "#1f1f1f"
        icon.put(accent, to=(4, 4, 12, 6))
        icon.put(accent, to=(4, 4, 6, 14))
        icon.put(accent, to=(20, 4, 28, 6))
        icon.put(accent, to=(26, 4, 28, 14))
        for idx, x in enumerate(range(4, 28, 3)):
            width = 1 + (idx % 3)
            icon.put(dark, to=(x, 8, min(31, x + width), 26))
    except Exception:
        return None
    return icon


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}"


__all__ = ["FoodScannerView", "SummaryDialog"]
