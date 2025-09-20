from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import tkinter as tk
from tkinter import ttk

from bascula.domain.session import WeighSession, SessionItem
from bascula.services import treatments
from bascula.services.treatments import TreatmentCalc
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    Card,
    COL_ACCENT,
    COL_BG,
    COL_CARD,
    COL_MUTED,
    COL_TEXT,
    FS_CARD_TITLE,
    FS_TEXT,
    FS_TITLE,
    BigButton,
    GhostButton,
)

_CFG_DIR_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CFG_DIR = Path(_CFG_DIR_ENV) if _CFG_DIR_ENV else (Path.home() / ".config" / "bascula")
CONFIG_FILE = CFG_DIR / "config.json"
NS_FILE = CFG_DIR / "nightscout.json"
MEALS_FILE = CFG_DIR / "meals.jsonl"
EXPORT_JSON = CFG_DIR / "session_last.json"
EXPORT_CSV = CFG_DIR / "session_last.csv"


class BolusOverlay(OverlayBase):
    def __init__(
        self,
        parent,
        app,
        session: WeighSession,
        on_finalize: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.app = app
        self.session = session
        self.on_finalize = on_finalize
        self.diabetic_mode = bool((app.get_cfg() or {}).get("diabetic_mode", False))
        self._status_var = tk.StringVar(value="")
        self._result_var = tk.StringVar(value="")
        self._bg_var = tk.StringVar(value="")
        self._send_ns_var = tk.BooleanVar(value=bool((app.get_cfg() or {}).get("send_to_ns_default", False)))
        self._finalizing = False
        self._confirm_btn: Optional[tk.Widget] = None
        self._ns_cfg = self._load_nightscout_cfg()
        if not (self._ns_cfg.get("url")):
            self._send_ns_var.set(False)
        self._diabetes_cfg = self._load_diabetes_cfg()
        self._build_ui()
        self._populate_items()
        if self.diabetic_mode:
            self._prefill_bg()

    # --- Config helpers ---
    def _load_diabetes_cfg(self) -> Dict[str, float]:
        cfg = dict(self.app.get_cfg() or {})
        try:
            if CONFIG_FILE.exists():
                file_cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for key in ("target_bg_mgdl", "isf_mgdl_per_u", "carb_ratio_g_per_u"):
                    if key in file_cfg:
                        cfg[key] = file_cfg[key]
        except Exception:
            pass
        return {
            "target_bg_mgdl": int(cfg.get("target_bg_mgdl", 110) or 110),
            "isf_mgdl_per_u": float(cfg.get("isf_mgdl_per_u", 50) or 50.0),
            "carb_ratio_g_per_u": float(cfg.get("carb_ratio_g_per_u", 10) or 10.0),
        }

    def _load_nightscout_cfg(self) -> Dict[str, str]:
        try:
            if NS_FILE.exists():
                data = json.loads(NS_FILE.read_text(encoding="utf-8"))
                return {
                    "url": (data.get("url") or "").strip(),
                    "token": (data.get("token") or "").strip(),
                }
        except Exception:
            pass
        return {"url": "", "token": ""}

    # --- UI construction ---
    def _build_ui(self) -> None:
        c = self.content()
        c.configure(bg=COL_BG, padx=20, pady=20)
        for i in range(3):
            c.grid_rowconfigure(i, weight=0)
        c.grid_rowconfigure(2, weight=1)
        c.grid_columnconfigure(0, weight=1)

        tk.Label(
            c,
            text="Finalizar comida",
            bg=COL_BG,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        body = Card(c)
        body.grid(row=1, column=0, sticky="nsew")
        body.configure(padx=16, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        self._carbs_big = tk.Label(
            body,
            text="0 g hidratos",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TITLE + 6, "bold"),
        )
        self._carbs_big.grid(row=0, column=0, sticky="w")

        totals_frame = tk.Frame(body, bg=COL_CARD)
        totals_frame.grid(row=1, column=0, sticky="ew", pady=(6, 12))
        totals_frame.grid_columnconfigure(0, weight=1)
        totals_frame.grid_columnconfigure(1, weight=1)

        self._tot_labels: Dict[str, tk.Label] = {}
        fields = [
            ("Peso", "grams", "g"),
            ("Calorías", "kcal", "kcal"),
            ("Proteínas", "protein_g", "g"),
            ("Grasas", "fat_g", "g"),
        ]
        for idx, (title, key, unit) in enumerate(fields):
            frame = tk.Frame(totals_frame, bg=COL_CARD)
            frame.grid(row=0, column=idx, sticky="w", padx=(0, 16))
            tk.Label(
                frame,
                text=title,
                bg=COL_CARD,
                fg=COL_MUTED,
                font=("DejaVu Sans", FS_TEXT),
            ).pack(anchor="w")
            val = tk.Label(
                frame,
                text="0",
                bg=COL_CARD,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold"),
            )
            val.pack(anchor="w")
            tk.Label(
                frame,
                text=unit,
                bg=COL_CARD,
                fg=COL_MUTED,
                font=("DejaVu Sans", FS_TEXT - 1),
            ).pack(anchor="w")
            self._tot_labels[key] = val

        # Tabla de items
        table_frame = tk.Frame(body, bg=COL_CARD)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style(table_frame)
        style.theme_use("clam")
        style.configure(
            "Bolus.Treeview",
            background="#101522",
            foreground=COL_TEXT,
            fieldbackground="#101522",
            rowheight=26,
            font=("DejaVu Sans", FS_TEXT - 2),
        )
        style.configure(
            "Bolus.Treeview.Heading",
            background=COL_CARD,
            foreground=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT - 1, "bold"),
        )
        self._tree = ttk.Treeview(
            table_frame,
            columns=("name", "grams", "carbs", "gi", "kcal", "protein", "fat"),
            show="headings",
            style="Bolus.Treeview",
            height=6,
        )
        self._tree.heading("name", text="Alimento")
        self._tree.heading("grams", text="g")
        self._tree.heading("carbs", text="Hidratos")
        self._tree.heading("gi", text="IG")
        self._tree.heading("kcal", text="kcal")
        self._tree.heading("protein", text="Prot")
        self._tree.heading("fat", text="Grasa")
        self._tree.column("name", width=220, anchor="w")
        self._tree.column("grams", width=70, anchor="center")
        self._tree.column("carbs", width=90, anchor="center")
        self._tree.column("gi", width=60, anchor="center")
        self._tree.column("kcal", width=80, anchor="center")
        self._tree.column("protein", width=80, anchor="center")
        self._tree.column("fat", width=80, anchor="center")
        self._tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=sb.set)

        params_card = Card(c)
        params_card.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        params_card.configure(padx=16, pady=14)

        if self.diabetic_mode:
            params_card.grid_columnconfigure(0, weight=1)
            tk.Label(
                params_card,
                text="Modo diabético",
                bg=COL_CARD,
                fg=COL_ACCENT,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold"),
            ).grid(row=0, column=0, sticky="w")

            grid = tk.Frame(params_card, bg=COL_CARD)
            grid.grid(row=1, column=0, sticky="ew", pady=(8, 8))
            for i in range(4):
                grid.grid_columnconfigure(i, weight=1)

            target = self._diabetes_cfg.get("target_bg_mgdl", 110)
            isf = self._diabetes_cfg.get("isf_mgdl_per_u", 50)
            ratio = self._diabetes_cfg.get("carb_ratio_g_per_u", 10)

            self._add_param(grid, 0, "Objetivo", f"{int(target)} mg/dL")
            self._add_param(grid, 1, "ISF", f"{isf:.1f} mg/dL/U")
            self._add_param(grid, 2, "Ratio HC", f"{ratio:.1f} g/U")

            bg_frame = tk.Frame(params_card, bg=COL_CARD)
            bg_frame.grid(row=2, column=0, sticky="ew", pady=(6, 6))
            tk.Label(
                bg_frame,
                text="BG actual (mg/dL)",
                bg=COL_CARD,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT),
            ).pack(side="left")
            entry = tk.Entry(
                bg_frame,
                textvariable=self._bg_var,
                bg="#111827",
                fg=COL_TEXT,
                insertbackground=COL_TEXT,
                width=8,
                font=("DejaVu Sans", FS_TEXT, "bold"),
                justify="center",
            )
            entry.pack(side="left", padx=(8, 8))
            try:
                from bascula.ui.widgets import bind_numeric_entry

                bind_numeric_entry(entry, decimals=0)
            except Exception:
                pass
            GhostButton(bg_frame, text="Teclado", micro=True, command=lambda: self._open_keypad()).pack(side="left")

            tk.Checkbutton(
                params_card,
                text="Enviar a Nightscout",
                variable=self._send_ns_var,
                bg=COL_CARD,
                fg=COL_TEXT,
                selectcolor=COL_CARD,
                activebackground=COL_CARD,
            ).grid(row=3, column=0, sticky="w")
        else:
            params_card.grid_columnconfigure(0, weight=1)
            tk.Label(
                params_card,
                text="Modo diabético desactivado",
                bg=COL_CARD,
                fg=COL_MUTED,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold"),
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                params_card,
                text="Puedes exportar la sesión para revisarla en otro dispositivo.",
                bg=COL_CARD,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT),
            ).grid(row=1, column=0, sticky="w", pady=(6, 0))
            export_row = tk.Frame(params_card, bg=COL_CARD)
            export_row.grid(row=2, column=0, sticky="w", pady=(6, 0))
            GhostButton(export_row, text="Exportar JSON", micro=True, command=lambda: self._export_session("json")).pack(side="left", padx=(0, 6))
            GhostButton(export_row, text="Exportar CSV", micro=True, command=lambda: self._export_session("csv")).pack(side="left")

        status_card = Card(c)
        status_card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        status_card.configure(padx=16, pady=10)
        tk.Label(
            status_card,
            textvariable=self._status_var,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT),
            wraplength=520,
            justify="left",
        ).pack(anchor="w")
        tk.Label(
            status_card,
            textvariable=self._result_var,
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TEXT, "bold"),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(c, bg=COL_BG)
        buttons.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        BigButton(buttons, text="Cancelar", command=self.hide, bg="#4b5563").grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._confirm_btn = BigButton(
            buttons,
            text="Confirmar",
            command=self._on_confirm,
            bg="#2563eb",
        )
        self._confirm_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _add_param(self, parent: tk.Frame, column: int, title: str, value: str) -> None:
        cell = tk.Frame(parent, bg=COL_CARD)
        cell.grid(row=0, column=column, sticky="w", padx=(0, 12))
        tk.Label(cell, text=title, bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")
        tk.Label(cell, text=value, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(anchor="w")

    # --- Session rendering ---
    def _populate_items(self) -> None:
        totals = self.session.totals()
        self._carbs_big.config(text=f"{totals['carbs_g']:.1f} g hidratos")
        for key, label in self._tot_labels.items():
            val = float(totals.get(key, 0.0) or 0.0)
            if key == "grams" or key == "kcal":
                label.config(text=f"{val:.0f}")
            else:
                label.config(text=f"{val:.1f}")
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        for item in self.session.items:
            self._tree.insert(
                "",
                "end",
                values=(
                    item.name,
                    f"{item.grams:.0f}",
                    f"{item.carbs_g:.1f}",
                    (item.gi if item.gi is not None else "-"),
                    f"{item.kcal:.0f}",
                    f"{item.protein_g:.1f}",
                    f"{item.fat_g:.1f}",
                ),
            )

    # --- BG helpers ---
    def _prefill_bg(self) -> None:
        if self._ns_cfg.get("url"):
            self._status_var.set("Consultando Nightscout...")
            threading.Thread(target=self._fetch_bg_from_nightscout, daemon=True).start()
        else:
            self._status_var.set("Introduce el valor de glucosa actual.")

    def _fetch_bg_from_nightscout(self) -> None:
        try:
            import requests  # type: ignore
        except Exception:
            self.after(0, lambda: self._status_var.set("Nightscout no disponible."))
            return
        url = self._ns_cfg.get("url", "").rstrip("/")
        if not url:
            return
        full = f"{url}/api/v1/entries.json?count=1"
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self._ns_cfg.get("token"):
            headers["API-SECRET"] = self._ns_cfg["token"]
        try:
            resp = requests.get(full, headers=headers, timeout=6)
            if 200 <= getattr(resp, "status_code", 0) < 300:
                data = resp.json()
                if isinstance(data, list) and data:
                    entry = data[0]
                    sgv = entry.get("sgv") or entry.get("sgv_mgdl")
                    if sgv:
                        try:
                            val = int(float(sgv))
                        except Exception:
                            val = None
                        if val:
                            self.after(0, lambda: self._set_bg_from_ns(val))
                            return
        except Exception:
            pass
        self.after(0, lambda: self._status_var.set("Introduce BG manualmente."))

    def _set_bg_from_ns(self, value: int) -> None:
        self._bg_var.set(str(value))
        self._status_var.set(f"BG desde Nightscout: {value} mg/dL")

    def _open_keypad(self) -> None:
        try:
            from bascula.ui.widgets import KeypadPopup

            KeypadPopup(
                self,
                title="BG actual (mg/dL)",
                initial=self._bg_var.get() or "",
                allow_dot=False,
                on_accept=lambda v: self._bg_var.set(v),
            )
        except Exception:
            pass

    # --- Export helpers ---
    def _export_session(self, fmt: str) -> None:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": _utc_iso(),
            "items": [self._serialize_item(it) for it in self.session.items],
            "totals": self.session.totals(),
        }
        try:
            if fmt == "json":
                EXPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                self._status_var.set(f"Sesión exportada a {EXPORT_JSON}")
            elif fmt == "csv":
                with EXPORT_CSV.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["Alimento", "Gramos", "Hidratos", "IG", "kcal", "Proteína", "Grasa", "Fuente"])
                    for it in self.session.items:
                        writer.writerow([
                            it.name,
                            f"{it.grams:.0f}",
                            f"{it.carbs_g:.1f}",
                            it.gi if it.gi is not None else "",
                            f"{it.kcal:.0f}",
                            f"{it.protein_g:.1f}",
                            f"{it.fat_g:.1f}",
                            it.source,
                        ])
                self._status_var.set(f"Sesión exportada a {EXPORT_CSV}")
        except Exception as exc:
            self._status_var.set(f"Error exportando sesión: {exc}")

    # --- Confirm flow ---
    def _on_confirm(self) -> None:
        if self._finalizing:
            return
        if not self.session.items:
            self._status_var.set("No hay elementos en la sesión.")
            return

        totals = {k: float(v) for k, v in self.session.totals().items()}
        items_snapshot = [self._serialize_item(it) for it in self.session.items]

        current_bg: Optional[int] = None
        if self.diabetic_mode:
            try:
                current_bg = int(float(self._bg_var.get().strip()))
            except Exception:
                self._status_var.set("Introduce la glucosa actual en mg/dL.")
                return

            bolus_cfg = self._collect_bolus_cfg_snapshot(current_bg)
            ratio = float(bolus_cfg.get("carb_ratio_g_per_u", 0.0) or 0.0)
            isf = float(bolus_cfg.get("isf_mgdl_per_u", 0.0) or 0.0)
            if ratio <= 0 or isf <= 0:
                self._status_var.set("Configura ratio e ISF válidos en ajustes de diabetes.")
                return
        else:
            bolus_cfg = self._collect_bolus_cfg_snapshot(None)

        send_ns = bool(self._send_ns_var.get()) if self.diabetic_mode else False
        ns_cfg = self._collect_nightscout_cfg_snapshot()

        self._set_busy(True)
        self._status_var.set("Procesando...")
        self._result_var.set("")

        threading.Thread(
            target=self._finalize_worker,
            args=(totals, items_snapshot, bolus_cfg, ns_cfg, send_ns),
            daemon=True,
        ).start()

    def _finalize_worker(
        self,
        totals: Dict[str, float],
        items: List[Dict[str, object]],
        bolus_cfg: Dict[str, object],
        ns_cfg: Dict[str, str],
        send_ns: bool,
    ) -> None:
        try:
            result = self._execute_finalize(totals, items, bolus_cfg, ns_cfg, send_ns)
            self.after(0, lambda: self._on_finalize_success(result))
        except Exception as exc:
            err = str(exc)
            self.after(0, lambda: self._on_finalize_error(err))

    def _execute_finalize(
        self,
        totals: Dict[str, float],
        items: List[Dict[str, object]],
        bolus_cfg: Dict[str, object],
        ns_cfg: Dict[str, str],
        send_ns: bool,
    ) -> Dict[str, object]:
        result: Dict[str, object] = {"success": True}
        calc: Optional[TreatmentCalc] = None
        record: Optional[Dict[str, object]] = None
        persist_error: Optional[str] = None

        try:
            record = self._persist_session(totals, items)
            result["record"] = record
        except Exception as exc:
            persist_error = str(exc)
            result["success"] = False
            result["error"] = persist_error

        try:
            calc_data = self._compute_bolus_offline(totals, bolus_cfg)
            calc_candidate = calc_data.get("calc") if isinstance(calc_data, dict) else None
            calc = calc_candidate if isinstance(calc_candidate, TreatmentCalc) else None
            if calc:
                result["calc"] = calc
            if isinstance(calc_data, dict) and calc_data.get("error"):
                result["success"] = False
                result["error"] = calc_data["error"]
        except Exception as exc:
            result["success"] = False
            result["error"] = f"Error cálculo bolo: {exc}"

        ns_state: Optional[bool] = None
        if send_ns and calc:
            try:
                ns_state = self._post_nightscout(ns_cfg, totals, items, record, calc)
            except Exception as exc:
                ns_state = False
                result["ns_error"] = str(exc)
            result["ns_state"] = ns_state

        result["persist_error"] = persist_error
        return result

    def _persist_session(
        self,
        totals: Dict[str, float],
        items: List[Dict[str, object]],
    ) -> Dict[str, object]:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        meal_id = uuid.uuid4().hex
        created_at = _utc_iso()
        record = {
            "id": meal_id,
            "created_at": created_at,
            "items": [self._serialize_item(it) for it in items],
            "totals": {k: float(v) for k, v in totals.items()},
        }
        with MEALS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            from bascula.services.retention import prune_jsonl

            cfg = self.app.get_cfg() or {}
            prune_jsonl(
                MEALS_FILE,
                max_days=int(cfg.get("meals_max_days", 180) or 0),
                max_entries=int(cfg.get("meals_max_entries", 1000) or 0),
                max_bytes=int(cfg.get("meals_max_bytes", 5_000_000) or 0),
            )
        except Exception:
            pass
        return record

    def _build_ns_payload(
        self,
        totals: Dict[str, float],
        items: List[Dict[str, object]],
        record: Optional[Dict[str, object]],
        calc: TreatmentCalc,
    ) -> Dict[str, object]:
        total_carbs = float(totals.get("carbs_g", 0.0) or 0.0)
        total_grams = float(totals.get("grams", 0.0) or 0.0)
        n_items = len(items)
        gi_values = [it.get("gi") for it in items if it.get("gi") is not None]
        if gi_values:
            gi_note = f"GI prom {round(sum(gi_values) / len(gi_values))}"
        else:
            gi_note = "GI N/D"
        payload = {
            "eventType": "Meal Bolus",
            "carbs": round(total_carbs),
            "insulin": float(calc.bolus),
            "notes": f"BasculaCam: {n_items} items, {int(total_grams)} g, {gi_note}",
        }
        if record and record.get("created_at"):
            payload["created_at"] = record["created_at"]
        return payload

    def _finalize_done(self, result: Dict[str, object]) -> None:
        if result.get("persist_error"):
            self._status_var.set(f"Error guardando comida: {result['persist_error']}")
        elif result.get("success"):
            self._status_var.set("Comida guardada correctamente.")
        else:
            self._status_var.set(str(result.get("error", "No se pudo finalizar")))

        calc: Optional[TreatmentCalc] = result.get("calc") if isinstance(result.get("calc"), TreatmentCalc) else None
        if calc:
            msg = f"Bolo sugerido: {calc.bolus:.2f} U. Espera {calc.peak_time_min} minutos."
            ns_state = result.get("ns_state")
            if ns_state is True:
                msg += " Enviado a Nightscout."
            elif ns_state is False:
                msg += " Encolado para Nightscout."
            self._result_var.set(msg)
            self._announce_bolus(calc.bolus, calc.peak_time_min)
        else:
            if self.diabetic_mode:
                self._result_var.set("No se pudo calcular el bolo.")

        if result.get("success"):
            self.after(1800, lambda: self._finish(result))

    def _finish(self, result: Dict[str, object]) -> None:
        if callable(self.on_finalize):
            try:
                self.on_finalize(result)
            except Exception:
                pass
        self.hide()

    def _announce_bolus(self, units: float, wait_min: int) -> None:
        try:
            audio = getattr(self.app, "get_audio", lambda: None)()
            if audio and hasattr(audio, "speak_text"):
                audio.speak_text(
                    f"Bolo recomendado {units:.2f} unidades. Espera {int(wait_min)} minutos."
                )
        except Exception:
            pass

    def _collect_bolus_cfg_snapshot(self, current_bg: Optional[int]) -> Dict[str, object]:
        cfg = dict(self._diabetes_cfg or {})
        snapshot: Dict[str, object] = {
            "diabetic_mode": bool(self.diabetic_mode),
            "current_bg": current_bg,
            "target_bg_mgdl": int(cfg.get("target_bg_mgdl", 110) or 110),
            "isf_mgdl_per_u": float(cfg.get("isf_mgdl_per_u", 50.0) or 50.0),
            "carb_ratio_g_per_u": float(cfg.get("carb_ratio_g_per_u", 10.0) or 10.0),
        }
        return snapshot

    def _collect_nightscout_cfg_snapshot(self) -> Dict[str, str]:
        cfg = dict(self._ns_cfg or {})
        return {
            "url": str(cfg.get("url", "") or ""),
            "token": str(cfg.get("token", "") or ""),
        }

    def _compute_bolus_offline(
        self,
        totals: Dict[str, float],
        bolus_cfg: Dict[str, object],
    ) -> Dict[str, object]:
        result: Dict[str, object] = {}
        if not bolus_cfg.get("diabetic_mode"):
            return result
        current_bg = bolus_cfg.get("current_bg")
        if current_bg is None:
            return result
        ratio = float(bolus_cfg.get("carb_ratio_g_per_u", 0.0) or 0.0)
        isf = float(bolus_cfg.get("isf_mgdl_per_u", 0.0) or 0.0)
        target = int(bolus_cfg.get("target_bg_mgdl", 0) or 0)
        calc = treatments.calc_bolus(
            grams_carbs=float(totals.get("carbs_g", 0.0)),
            target_bg=target,
            current_bg=int(current_bg),
            isf=isf,
            ratio=ratio,
        )
        result["calc"] = calc
        return result

    def _post_nightscout(
        self,
        ns_cfg: Dict[str, str],
        totals: Dict[str, float],
        items: List[Dict[str, object]],
        record: Optional[Dict[str, object]],
        calc: TreatmentCalc,
    ) -> bool:
        payload = self._build_ns_payload(totals, items, record, calc)
        url = ns_cfg.get("url", "")
        token = ns_cfg.get("token", "")
        return treatments.post_treatment(url, token, payload)

    def _on_finalize_success(self, result: Dict[str, object]) -> None:
        try:
            self._finalize_done(result)
        finally:
            self._set_busy(False)

    def _on_finalize_error(self, msg: str) -> None:
        self._set_busy(False)
        self._status_var.set(f"Error al finalizar: {msg}")
        self._result_var.set("")

    def _set_busy(self, busy: bool) -> None:
        self._finalizing = busy
        if self._confirm_btn is not None:
            self._confirm_btn.config(state=tk.DISABLED if busy else tk.NORMAL)

    def _serialize_item(self, item: Union[SessionItem, Dict[str, Any]]) -> Dict[str, object]:
        if isinstance(item, SessionItem):
            data = asdict(item)
        else:
            data = dict(item)
        data.update(
            {
                "grams": float(data.get("grams", 0.0)),
                "carbs_g": float(data.get("carbs_g", 0.0)),
                "kcal": float(data.get("kcal", 0.0)),
                "protein_g": float(data.get("protein_g", 0.0)),
                "fat_g": float(data.get("fat_g", 0.0)),
            }
        )
        return data


def _utc_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0, tzinfo=_dt.timezone.utc).isoformat().replace("+00:00", "Z")
