"""UI screens for the modern Bascula interface."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

from ..services.nutrition import FoodEntry
from .widgets import PALETTE, PrimaryButton, TotalsTable, WeightDisplay


try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
except Exception:  # pragma: no cover - best effort fallback
    requests = None

try:  # pragma: no cover - optional dependency
    import qrcode  # type: ignore
    from PIL import ImageTk  # type: ignore
except Exception:  # pragma: no cover - gracefully degrade
    qrcode = None
    ImageTk = None

if TYPE_CHECKING:
    from .app import BasculaApp


_PORT_RAW = os.environ.get("BASCULA_WEB_PORT") or os.environ.get("FLASK_RUN_PORT") or "8080"
_PORT = str(_PORT_RAW).strip() or "8080"
_HOST_RAW = os.environ.get("BASCULA_WEB_HOST", "127.0.0.1").strip()
_HOST = _HOST_RAW if _HOST_RAW and _HOST_RAW != "0.0.0.0" else "127.0.0.1"
BASE_URL = os.environ.get("BASCULA_WEB_URL", f"http://{_HOST}:{_PORT}")

_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CONFIG_DIR = Path(_CFG_ENV) if _CFG_ENV else (Path.home() / ".config" / "bascula")
API_KEY_FILE = CONFIG_DIR / "apikey.json"


class BaseScreen(tk.Frame):
    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, bg=PALETTE["bg"])
        self.app = app


class HomeScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        container = tk.Frame(self, bg=PALETTE["bg"])
        container.pack(expand=True, fill="both", padx=40, pady=40)

        display_card = tk.Frame(container, bg=PALETTE["panel"], bd=0, relief="flat")
        display_card.pack(fill="x", padx=0, pady=(0, 32))
        self.weight_display = WeightDisplay(display_card)
        self.weight_display.pack(fill="both", expand=True, padx=32, pady=32)
        self.status_label = tk.Label(
            display_card,
            text="Coloque un objeto para pesar",
            fg=PALETTE["muted"],
            bg=PALETTE["panel"],
            font=("DejaVu Sans", 16),
        )
        self.status_label.pack(pady=(0, 20))

        button_grid = tk.Frame(container, bg=PALETTE["bg"])
        button_grid.pack(fill="x")

        self._add_button(button_grid, "TARA", lambda: app.handle_tare(), column=0)
        self._add_button(button_grid, "ZERO", lambda: app.handle_zero(), column=1)
        self._add_button(button_grid, "g / ml", lambda: app.handle_toggle_units(), column=2)
        self._add_button(button_grid, "ALIMENTOS", lambda: app.navigate("alimentos"), column=3)
        self._add_button(button_grid, "RECETAS", lambda: app.navigate("recetas"), column=4)
        self._add_button(button_grid, "TEMPORIZADOR", lambda: app.handle_timer(), column=5)

    def _add_button(self, frame: tk.Frame, text: str, command, column: int) -> None:
        btn = PrimaryButton(frame, text=text, command=command)
        btn.grid(row=0, column=column, padx=10, pady=10, sticky="nsew")
        frame.grid_columnconfigure(column, weight=1)

    def update_weight(self, value: Optional[float], stable: bool, unit: str) -> None:
        if value is None:
            self.weight_display.configure(text="--")
            self.status_label.configure(text="Sin señal")
            return
        decimals = self.app.scale_service.get_decimals()
        formatted_value = f"{value:.{decimals}f}" if decimals >= 0 else f"{value}"
        formatted = f"{formatted_value} {unit}"
        self.weight_display.configure(text=formatted)
        self.status_label.configure(text="Peso estable" if stable else "Midiendo...")


class FoodsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        title = tk.Label(
            self,
            text="Registro de alimentos",
            font=("DejaVu Sans", 28, "bold"),
            fg=PALETTE["text"],
            bg=PALETTE["bg"],
        )
        title.pack(anchor="w", padx=40, pady=(30, 10))

        disclaimer = tk.Label(
            self,
            text="Estimación nutricional. No es un consejo médico.",
            fg=PALETTE["muted"],
            bg=PALETTE["bg"],
            font=("DejaVu Sans", 12),
        )
        disclaimer.pack(anchor="w", padx=40, pady=(0, 20))

        table_frame = tk.Frame(self, bg=PALETTE["panel"], bd=0)
        table_frame.pack(fill="both", expand=True, padx=40, pady=10)
        self.table = TotalsTable(table_frame)
        self.table.pack(fill="both", expand=True, padx=20, pady=20)

        controls = tk.Frame(self, bg=PALETTE["bg"])
        controls.pack(fill="x", padx=40, pady=20)

        PrimaryButton(controls, text="Añadir actual", command=self._add_current).pack(
            side="left", padx=10
        )
        PrimaryButton(controls, text="Eliminar seleccionado", command=self._remove_selected).pack(
            side="left", padx=10
        )
        PrimaryButton(controls, text="Finalizar", command=self._finish).pack(side="right", padx=10)
        PrimaryButton(controls, text="Volver", command=lambda: app.navigate("home")).pack(
            side="right", padx=10
        )

        app.nutrition_service.subscribe(self._refresh_table)

    def _add_current(self) -> None:
        weight = self.app.scale_service.get_last_weight_g()
        if weight <= 0:
            return
        self.app.nutrition_service.recognise("alimento", weight)

    def _remove_selected(self) -> None:
        selected = self.table.selection()
        if not selected:
            return
        index = self.table.index(selected[0])
        self.app.nutrition_service.remove_entry(index)

    def _finish(self) -> None:
        totals = self.app.nutrition_service.totals()
        summary = (
            f"Totales: {totals.weight_g:.0f} g, HC {totals.carbs_g:.1f} g, "
            f"Proteínas {totals.protein_g:.1f} g, Grasas {totals.fat_g:.1f} g"
        )
        self.app.audio_service.speak(summary)
        self.app.navigate("home")

    def _refresh_table(self, entries: list[FoodEntry], totals) -> None:
        for iid in self.table.get_children():
            self.table.delete(iid)
        for entry in entries:
            self.table.insert(
                "",
                "end",
                values=(
                    entry.name,
                    f"{entry.weight_g:.0f}",
                    f"{entry.carbs_g:.1f}",
                    f"{entry.protein_g:.1f}",
                    f"{entry.fat_g:.1f}",
                    f"{entry.glycemic_index:.0f}",
                ),
            )


class RecipesScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        title = tk.Label(
            self,
            text="Asistente de recetas",
            font=("DejaVu Sans", 28, "bold"),
            fg=PALETTE["text"],
            bg=PALETTE["bg"],
        )
        title.pack(anchor="w", padx=40, pady=(30, 10))

        self.text = tk.Text(self, font=("DejaVu Sans", 14), height=12, bg=PALETTE["panel"], bd=0)
        self.text.pack(fill="both", expand=True, padx=40, pady=20)
        self.text.insert("end", "Pulsa Siguiente para avanzar por la receta.")

        controls = tk.Frame(self, bg=PALETTE["bg"])
        controls.pack(fill="x", padx=40, pady=20)
        PrimaryButton(controls, text="Siguiente", command=self._next).pack(side="left", padx=10)
        PrimaryButton(controls, text="Repetir", command=self._repeat).pack(side="left", padx=10)
        PrimaryButton(controls, text="Cancelar", command=lambda: app.navigate("home")).pack(side="right", padx=10)

        self.steps = [
            "Describe qué quieres cocinar.",
            "Pesa los ingredientes cuando se te indique.",
            "Sigue los pasos uno a uno.",
        ]
        self.step_index = 0

    def _next(self) -> None:
        self.step_index = min(len(self.steps) - 1, self.step_index + 1)
        self._render()

    def _repeat(self) -> None:
        self._render()

    def _render(self) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("end", self.steps[self.step_index])
        self.app.audio_service.speak(self.steps[self.step_index])



class SettingsScreen(BaseScreen):
    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        self.voice_model_map: dict[str, str] = {}
        self.voice_status_var = tk.StringVar(value="")
        self.api_key_var = tk.StringVar(value=self._load_api_key())
        self.api_key_status_var = tk.StringVar(value="")
        self.wifi_status_var = tk.StringVar(value="Pulsa «Escanear redes» para empezar.")
        self.wifi_ssid_var = tk.StringVar()
        self.wifi_password_var = tk.StringVar()
        self.network_status_var = tk.StringVar(value="")
        self.diabetes_status_var = tk.StringVar(value="")
        self.ota_status_var = tk.StringVar(value="Listo")
        self.version_var = tk.StringVar(value=self._current_version_text())
        self.ip_var = tk.StringVar(value="IP: --")
        self.miniweb_url_var = tk.StringVar(value="")
        self._wifi_tree: Optional[ttk.Treeview] = None
        self._qr_photo = None
        self.qr_label: Optional[tk.Label] = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=30, pady=30)

        self._build_general(notebook)
        self._build_scale(notebook)
        self._build_network(notebook)
        self._build_diabetes(notebook)
        self._build_ota(notebook)
        self._build_recovery(notebook)

        self.after(400, self._populate_voice_models)
        self.after(600, self._update_ip_info)
        self.after(800, self._scan_wifi)
        self.after(1000, self._update_miniweb_url)

    # ------------------------------------------------------------------
    def _build_general(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="General")

        tk.Label(
            frame,
            text="Audio y voz",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        ttk.Checkbutton(frame, text="Activar sonido", variable=self.app.general_sound_var).pack(
            anchor="w", padx=24, pady=(0, 4)
        )
        tk.Scale(
            frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.app.general_volume_var,
            bg=PALETTE["panel"],
            highlightthickness=0,
        ).pack(fill="x", padx=24, pady=(0, 10))

        ttk.Checkbutton(frame, text="Activar voz (TTS)", variable=self.app.general_tts_var).pack(
            anchor="w", padx=24, pady=(0, 12)
        )

        voice_section = tk.Frame(frame, bg=PALETTE["panel"])
        voice_section.pack(fill="x", padx=20, pady=4)
        tk.Label(
            voice_section,
            text="Modelo Piper",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w")
        combo_frame = tk.Frame(voice_section, bg=PALETTE["panel"])
        combo_frame.pack(fill="x", pady=4)
        self.voice_combo = ttk.Combobox(combo_frame, state="readonly")
        self.voice_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(combo_frame, text="Refrescar", command=self._populate_voice_models).pack(
            side="left", padx=6
        )
        controls = tk.Frame(voice_section, bg=PALETTE["panel"])
        controls.pack(fill="x", pady=4)
        ttk.Button(controls, text="Guardar voz", command=self._apply_voice_selection).pack(
            side="left", padx=4
        )
        ttk.Button(controls, text="Probar voz", command=self._test_voice).pack(side="left", padx=4)
        tk.Label(
            voice_section,
            textvariable=self.voice_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
        ).pack(anchor="w", pady=(2, 8))

        ttk.Button(frame, text="Probar beep", command=self.app.audio_service.beep_ok).pack(
            anchor="w", padx=24, pady=(4, 16)
        )

    # ------------------------------------------------------------------
    def _build_scale(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Báscula")

        tk.Label(
            frame,
            text="Calibración de la báscula",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        form = tk.Frame(frame, bg=PALETTE["panel"])
        form.pack(fill="x", padx=20)

        tk.Label(form, text="Factor de calibración", bg=PALETTE["panel"], fg=PALETTE["text"]).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(form, textvariable=self.app.scale_calibration_var, width=18).grid(
            row=0, column=1, padx=(8, 0), pady=4, sticky="w"
        )

        tk.Label(form, text="Factor ml↔g", bg=PALETTE["panel"], fg=PALETTE["text"]).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(form, textvariable=self.app.scale_density_var, width=18).grid(
            row=1, column=1, padx=(8, 0), pady=4, sticky="w"
        )

        tk.Label(form, text="Decimales", bg=PALETTE["panel"], fg=PALETTE["text"]).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Spinbox(form, from_=0, to=1, textvariable=self.app.scale_decimals_var, width=5).grid(
            row=2, column=1, padx=(8, 0), pady=4, sticky="w"
        )

        tk.Label(form, text="Unidad preferida", bg=PALETTE["panel"], fg=PALETTE["text"]).grid(
            row=3, column=0, sticky="w"
        )
        unit_combo = ttk.Combobox(
            form,
            values=("g", "ml"),
            textvariable=self.app.scale_unit_var,
            state="readonly",
            width=6,
        )
        unit_combo.grid(row=3, column=1, padx=(8, 0), pady=4, sticky="w")

        ttk.Button(frame, text="Guardar ajustes", command=self._save_scale).pack(
            anchor="w", padx=20, pady=(16, 6)
        )
        tk.Label(
            frame,
            text="Permite ajustar el peso a recipientes específicos y la conversión a mililitros.",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            wraplength=540,
            justify="left",
        ).pack(anchor="w", padx=20)

    # ------------------------------------------------------------------
    def _build_network(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Red")

        tk.Label(
            frame,
            text="Conectividad Wi‑Fi",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        wifi_section = tk.Frame(frame, bg=PALETTE["panel"])
        wifi_section.pack(fill="both", expand=False, padx=20)

        ctrl = tk.Frame(wifi_section, bg=PALETTE["panel"])
        ctrl.pack(fill="x", pady=(0, 4))
        ttk.Button(ctrl, text="Escanear redes", command=self._scan_wifi).pack(side="left", padx=(0, 6))
        ttk.Button(ctrl, text="Conectar", command=self._connect_wifi).pack(side="left", padx=(0, 6))
        tk.Label(ctrl, textvariable=self.wifi_status_var, bg=PALETTE["panel"], fg=PALETTE["muted"]).pack(
            side="left", padx=8
        )

        tree_container = tk.Frame(wifi_section, bg=PALETTE["panel"])
        tree_container.pack(fill="both", expand=False, pady=(0, 6))
        columns = ("ssid", "signal", "sec")
        self._wifi_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=5)
        for col, title in (
            ("ssid", "SSID"),
            ("signal", "Señal"),
            ("sec", "Seguridad"),
        ):
            self._wifi_tree.heading(col, text=title)
            width = 220 if col == "ssid" else 100
            anchor = "w" if col == "ssid" else "center"
            self._wifi_tree.column(col, width=width, anchor=anchor)
        self._wifi_tree.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(tree_container, orient="vertical", command=self._wifi_tree.yview)
        sb.pack(side="right", fill="y")
        self._wifi_tree.configure(yscrollcommand=sb.set)
        self._wifi_tree.bind("<<TreeviewSelect>>", self._on_wifi_select)

        entry_row = tk.Frame(wifi_section, bg=PALETTE["panel"])
        entry_row.pack(fill="x", pady=4)
        ttk.Label(entry_row, text="SSID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(entry_row, textvariable=self.wifi_ssid_var, width=32).grid(
            row=0, column=1, sticky="we", padx=(6, 12)
        )
        ttk.Label(entry_row, text="Contraseña:").grid(row=0, column=2, sticky="w")
        ttk.Entry(entry_row, textvariable=self.wifi_password_var, show="*", width=24).grid(
            row=0, column=3, sticky="w"
        )
        entry_row.grid_columnconfigure(1, weight=1)

        tk.Label(
            frame,
            text="Mini web y API",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        miniweb = tk.Frame(frame, bg=PALETTE["panel"])
        miniweb.pack(fill="x", padx=20)
        tk.Label(miniweb, textvariable=self.ip_var, bg=PALETTE["panel"], fg=PALETTE["text"]).pack(
            anchor="w"
        )
        tk.Label(miniweb, textvariable=self.miniweb_url_var, bg=PALETTE["panel"], fg=PALETTE["text"]).pack(
            anchor="w", pady=(0, 6)
        )

        row = tk.Frame(miniweb, bg=PALETTE["panel"])
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Puerto:").pack(side="left")
        ttk.Entry(row, textvariable=self.app.miniweb_port_var, width=8).pack(side="left", padx=(4, 12))
        ttk.Label(row, text="PIN:").pack(side="left")
        ttk.Entry(row, textvariable=self.app.miniweb_pin_var, width=12).pack(side="left", padx=(4, 12))
        ttk.Button(row, text="Guardar", command=self._apply_miniweb).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Generar QR", command=self._show_qr).pack(side="left")

        self.qr_label = tk.Label(miniweb, bg=PALETTE["panel"])
        self.qr_label.pack(anchor="w", pady=(8, 4))

        tk.Label(
            miniweb,
            textvariable=self.network_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            miniweb,
            text="API Key de OpenAI",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w", pady=(12, 4))
        api_row = tk.Frame(miniweb, bg=PALETTE["panel"])
        api_row.pack(fill="x")
        ttk.Entry(api_row, textvariable=self.api_key_var, show="*", width=36).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(api_row, text="Guardar", command=self._save_api_key).pack(side="left", padx=4)
        ttk.Button(api_row, text="Probar", command=self._test_api_key).pack(side="left")
        tk.Label(
            miniweb,
            textvariable=self.api_key_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
        ).pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    def _build_diabetes(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Diabetes")

        tk.Label(
            frame,
            text="Asistente de diabetes",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        ttk.Checkbutton(frame, text="Modo diabetes activo", variable=self.app.diabetes_enabled_var).pack(
            anchor="w", padx=24, pady=(0, 8)
        )

        form = tk.Frame(frame, bg=PALETTE["panel"])
        form.pack(fill="x", padx=20)
        ttk.Label(form, text="URL Nightscout").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.app.diabetes_url_var, width=42).grid(
            row=0, column=1, padx=(8, 0), pady=4, sticky="we"
        )
        ttk.Label(form, text="Token/API Secret").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.app.diabetes_token_var, show="*", width=42).grid(
            row=1, column=1, padx=(8, 0), pady=4, sticky="we"
        )
        ttk.Label(form, text="Alarma hipo (mg/dL)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(form, from_=50, to=120, textvariable=self.app.diabetes_hypo_var, width=6).grid(
            row=2, column=1, padx=(8, 0), pady=4, sticky="w"
        )
        ttk.Label(form, text="Alarma hiper (mg/dL)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(form, from_=140, to=300, textvariable=self.app.diabetes_hyper_var, width=6).grid(
            row=3, column=1, padx=(8, 0), pady=4, sticky="w"
        )
        ttk.Checkbutton(form, text="Activar protocolo 15/15", variable=self.app.diabetes_mode1515_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 6)
        )
        ttk.Label(form, text="Ratio insulina (g/U)").grid(row=5, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.app.diabetes_ratio_var, width=10).grid(
            row=5, column=1, padx=(8, 0), pady=4, sticky="w"
        )
        ttk.Label(form, text="Sensibilidad (mg/dL/U)").grid(row=6, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.app.diabetes_sensitivity_var, width=10).grid(
            row=6, column=1, padx=(8, 0), pady=4, sticky="w"
        )
        ttk.Label(form, text="Objetivo glucosa").grid(row=7, column=0, sticky="w")
        ttk.Spinbox(form, from_=80, to=150, textvariable=self.app.diabetes_target_var, width=6).grid(
            row=7, column=1, padx=(8, 0), pady=4, sticky="w"
        )

        ttk.Button(frame, text="Guardar ajustes", command=self._save_diabetes).pack(
            anchor="w", padx=20, pady=(16, 6)
        )
        tk.Label(
            frame,
            textvariable=self.diabetes_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
        ).pack(anchor="w", padx=20)

    # ------------------------------------------------------------------
    def _build_ota(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="OTA")

        tk.Label(
            frame,
            text="Actualizaciones y mantenimiento",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        tk.Label(frame, textvariable=self.version_var, bg=PALETTE["panel"], fg=PALETTE["text"]).pack(
            anchor="w", padx=20
        )
        ttk.Button(frame, text="Comprobar actualización", command=self._check_updates).pack(
            anchor="w", padx=20, pady=(12, 4)
        )
        ttk.Button(frame, text="Actualizar ahora", command=self._update_repo).pack(
            anchor="w", padx=20, pady=4
        )
        ttk.Button(frame, text="Reiniciar mini-web", command=self._restart_miniweb).pack(
            anchor="w", padx=20, pady=4
        )
        tk.Label(
            frame,
            textvariable=self.ota_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            wraplength=540,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(10, 0))

    # ------------------------------------------------------------------
    def _build_recovery(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Recovery")

        text = (
            "Si la aplicación no arranca después de una actualización, puedes iniciar el modo "
            "recovery desde la mini-web o ejecutando manualmente el módulo "
            "'bascula.recovery.app'. Desde ahí es posible volver a aplicar la OTA, reiniciar "
            "los servicios o relanzar la interfaz."
        )
        tk.Label(
            frame,
            text=text,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            wraplength=640,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(20, 12))
        ttk.Button(frame, text="Ver instrucciones", command=self._show_recovery_help).pack(
            anchor="w", padx=20
        )

    # ------------------------------------------------------------------
    def _save_scale(self) -> None:
        self.app.apply_scale_settings()
        self._set_status(self.voice_status_var, "")
        self._set_status(self.network_status_var, "")

    def _populate_voice_models(self) -> None:
        voices = self.app.discover_voice_models()
        self.voice_model_map = {label: path for label, path in voices}
        labels = list(self.voice_model_map.keys())
        if not labels:
            self.voice_combo.configure(values=["Sin voces disponibles"])
            self.voice_combo.set("Sin voces disponibles")
            self._set_status(self.voice_status_var, "No se encontraron modelos Piper.")
            return
        self.voice_combo.configure(values=labels)
        current = self.app.voice_model_var.get()
        selected = next((label for label, path in voices if path == current), labels[0])
        self.voice_combo.set(selected)
        self._set_status(self.voice_status_var, "Lista de voces actualizada.")

    def _apply_voice_selection(self) -> None:
        label = self.voice_combo.get().strip()
        model = self.voice_model_map.get(label)
        if not model and self.voice_model_map:
            self._set_status(self.voice_status_var, "Selecciona un modelo válido.")
            return
        if self.app.select_voice_model(model or None):
            self._set_status(self.voice_status_var, "Voz guardada correctamente.")
        else:
            self._set_status(self.voice_status_var, "No se pudo aplicar la voz seleccionada.")

    def _test_voice(self) -> None:
        try:
            self.app.audio_service.speak("Esto es una prueba de voz")
            self._set_status(self.voice_status_var, "Prueba enviada.")
        except Exception as exc:  # pragma: no cover - depende de piper
            self._set_status(self.voice_status_var, f"Error al reproducir voz: {exc}")

    # ------------------------------------------------------------------
    def _scan_wifi(self) -> None:
        if not self._wifi_tree:
            return
        self._set_status(self.wifi_status_var, "Buscando redes...")
        self._wifi_tree.delete(*self._wifi_tree.get_children())
        networks: list[dict[str, str]] = []
        if requests is not None:
            try:
                resp = requests.get(f"{BASE_URL}/api/wifi_scan", timeout=6)
                if resp.ok and resp.json().get("ok"):
                    networks = resp.json().get("nets", [])
            except Exception:
                pass
        if not networks:
            networks = self._scan_wifi_nmcli()
        for net in networks:
            self._wifi_tree.insert(
                "",
                "end",
                values=(
                    net.get("ssid", ""),
                    net.get("signal", ""),
                    net.get("sec", ""),
                ),
            )
        self._set_status(self.wifi_status_var, f"Redes disponibles: {len(networks)}")

    def _scan_wifi_nmcli(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        if not self._has_nmcli():
            self._set_status(self.wifi_status_var, "nmcli no disponible en el sistema.")
            return results
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                text=True,
                timeout=8,
            )
            for line in out.splitlines():
                if not line.strip():
                    continue
                parts = line.split(":")
                while len(parts) < 3:
                    parts.append("")
                ssid, signal, sec = parts[:3]
                if ssid:
                    results.append({"ssid": ssid, "signal": signal, "sec": sec})
        except Exception as exc:
            self._set_status(self.wifi_status_var, f"Error al escanear: {exc}")
        return results

    def _has_nmcli(self) -> bool:
        try:
            subprocess.check_call(
                ["/usr/bin/env", "which", "nmcli"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def _on_wifi_select(self, _event=None) -> None:
        if not self._wifi_tree:
            return
        sel = self._wifi_tree.selection()
        if not sel:
            return
        values = self._wifi_tree.item(sel[0], "values")
        if values:
            self.wifi_ssid_var.set(values[0])

    def _connect_wifi(self) -> None:
        ssid = self.wifi_ssid_var.get().strip()
        password = self.wifi_password_var.get().strip()
        if not ssid:
            self._set_status(self.wifi_status_var, "Introduce el SSID.")
            return
        if requests is not None:
            try:
                payload = {"ssid": ssid, "psk": password}
                resp = requests.post(
                    f"{BASE_URL}/api/wifi",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload),
                    timeout=10,
                )
                if resp.ok and resp.json().get("ok"):
                    self._set_status(self.wifi_status_var, "Conexión enviada a la mini-web.")
                    self.after(2000, self._update_ip_info)
                    return
            except Exception:
                pass
        if not password:
            self._set_status(self.wifi_status_var, "Introduce la contraseña de la red.")
            return
        if not self._has_nmcli():
            self._set_status(self.wifi_status_var, "No es posible conectar sin nmcli.")
            return
        try:
            proc = subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                self._set_status(self.wifi_status_var, "Conectado correctamente.")
                self.after(2000, self._update_ip_info)
            else:
                err = proc.stderr.strip() or proc.stdout.strip() or "falló la conexión"
                self._set_status(self.wifi_status_var, f"Error: {err}")
        except Exception as exc:
            self._set_status(self.wifi_status_var, f"Error conectando: {exc}")

    # ------------------------------------------------------------------
    def _apply_miniweb(self) -> None:
        self.app.apply_network_settings()
        self._update_miniweb_url()
        self._set_status(self.network_status_var, "Mini-web guardada.")

    def _current_miniweb_url(self) -> str:
        try:
            port = int(self.app.miniweb_port_var.get())
        except Exception:
            port = 8080
        ip = self.ip_var.get().split(":", 1)[-1].strip()
        host = ip if ip and ip != "--" else "localhost"
        return f"http://{host}:{port}"

    def _update_miniweb_url(self) -> None:
        self.miniweb_url_var.set(f"Mini-web: {self._current_miniweb_url()}")

    def _show_qr(self) -> None:
        if qrcode is None or ImageTk is None:
            self._set_status(
                self.network_status_var,
                "Instala las librerías 'qrcode' y 'Pillow' para mostrar el QR.",
            )
            return
        url = self._current_miniweb_url()
        try:
            img = qrcode.make(url)
            img = img.resize((180, 180))
            self._qr_photo = ImageTk.PhotoImage(img)
            if self.qr_label is not None:
                self.qr_label.configure(image=self._qr_photo)
            self._set_status(self.network_status_var, "QR actualizado.")
        except Exception as exc:
            self._set_status(self.network_status_var, f"Error generando QR: {exc}")

    # ------------------------------------------------------------------
    def _load_api_key(self) -> str:
        try:
            if API_KEY_FILE.exists():
                data = json.loads(API_KEY_FILE.read_text(encoding="utf-8"))
                return str(data.get("openai_api_key", ""))
        except Exception:
            return ""
        return ""

    def _save_api_key(self) -> None:
        key = self.api_key_var.get().strip()
        if requests is not None:
            try:
                resp = requests.post(
                    f"{BASE_URL}/api/apikey",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({"key": key}),
                    timeout=6,
                )
                if resp.ok and resp.json().get("ok"):
                    self._set_status(self.api_key_status_var, "Clave guardada en la mini-web.")
                    return
            except Exception:
                pass
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            API_KEY_FILE.write_text(json.dumps({"openai_api_key": key}), encoding="utf-8")
            try:
                os.chmod(API_KEY_FILE, 0o600)
            except Exception:
                pass
            self._set_status(self.api_key_status_var, "Clave guardada localmente.")
        except Exception as exc:
            self._set_status(self.api_key_status_var, f"Error guardando clave: {exc}")

    def _test_api_key(self) -> None:
        key = self.api_key_var.get().strip()
        if not key:
            self._set_status(self.api_key_status_var, "Introduce una clave.")
            return
        if key.startswith("sk-") and len(key) > 20:
            self._set_status(self.api_key_status_var, "Formato de clave válido.")
        else:
            self._set_status(self.api_key_status_var, "Formato de clave sospechoso.")

    # ------------------------------------------------------------------
    def _save_diabetes(self) -> None:
        self.app.apply_diabetes_settings()
        self._set_status(self.diabetes_status_var, "Ajustes guardados.")

    # ------------------------------------------------------------------
    def _check_updates(self) -> None:
        self._set_status(self.ota_status_var, "Buscando actualizaciones...")
        self._run_thread(self._check_updates_worker)

    def _check_updates_worker(self) -> None:
        root = self._repo_root()
        try:
            subprocess.run(
                ["git", "fetch", "--all", "--tags"],
                cwd=str(root),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
            remotes = subprocess.check_output(["git", "remote"], cwd=str(root), text=True).strip().splitlines()
            remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")
            upstream = f"{remote}/main"
            try:
                show = subprocess.check_output(["git", "remote", "show", remote], cwd=str(root), text=True)
                for line in show.splitlines():
                    if "HEAD branch:" in line:
                        upstream = f"{remote}/{line.split(':', 1)[-1].strip()}"
                        break
            except Exception:
                pass
            remote_rev = subprocess.check_output(["git", "rev-parse", upstream], cwd=str(root), text=True).strip()
            if local == remote_rev:
                msg = f"Sin novedades ({local[:7]})"
            else:
                msg = f"Actualización disponible: {remote_rev[:7]} (local {local[:7]})"
            self._set_status(self.ota_status_var, msg)
        except Exception as exc:
            self._set_status(self.ota_status_var, f"Error comprobando OTA: {exc}")

    def _update_repo(self) -> None:
        self._set_status(self.ota_status_var, "Aplicando actualización...")
        self._run_thread(self._update_repo_worker)

    def _update_repo_worker(self) -> None:
        root = self._repo_root()
        try:
            if subprocess.run(["git", "diff", "--quiet"], cwd=str(root)).returncode != 0:
                self._set_status(self.ota_status_var, "Hay cambios locales; limpia el repositorio antes de actualizar.")
                return
            remotes = subprocess.check_output(["git", "remote"], cwd=str(root), text=True).strip().splitlines()
            remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")
            upstream = f"{remote}/main"
            try:
                show = subprocess.check_output(["git", "remote", "show", remote], cwd=str(root), text=True)
                for line in show.splitlines():
                    if "HEAD branch:" in line:
                        upstream = f"{remote}/{line.split(':', 1)[-1].strip()}"
                        break
            except Exception:
                pass
            subprocess.run(["git", "fetch", "--all", "--tags"], cwd=str(root), check=True)
            new_rev = subprocess.check_output(["git", "rev-parse", upstream], cwd=str(root), text=True).strip()
            subprocess.run(["git", "reset", "--hard", new_rev], cwd=str(root), check=True)
            req = root / "requirements.txt"
            if req.exists():
                subprocess.run(
                    ["python3", "-m", "pip", "install", "--upgrade", "-r", str(req)],
                    cwd=str(root),
                    check=False,
                )
            msg = f"Actualización completada ({new_rev[:7]}). Reinicia la aplicación para aplicar cambios."
            self._set_status(self.ota_status_var, msg)
            self._set_status(self.version_var, f"Versión actual: {new_rev[:7]}")
        except Exception as exc:
            self._set_status(self.ota_status_var, f"Error al actualizar: {exc}")

    def _restart_miniweb(self) -> None:
        try:
            proc = subprocess.run(
                ["systemctl", "restart", "bascula-web.service"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                self._set_status(self.ota_status_var, "Mini-web reiniciada.")
            else:
                msg = proc.stderr.strip() or proc.stdout.strip() or "Fallo al reiniciar mini-web"
                self._set_status(self.ota_status_var, msg)
        except Exception as exc:
            self._set_status(self.ota_status_var, f"Error reiniciando mini-web: {exc}")

    # ------------------------------------------------------------------
    def _show_recovery_help(self) -> None:
        message = (
            "Para lanzar el modo recovery ejecuta 'python3 -m bascula.recovery.app' "
            "desde una terminal o accede a la mini-web en modo AP Wi-Fi si la red "
            "habitual no está disponible."
        )
        messagebox.showinfo("Recovery", message)

    def _update_ip_info(self) -> None:
        ip = self._current_ip() or "--"
        self.ip_var.set(f"IP: {ip}")
        self._update_miniweb_url()
        self.after(15000, self._update_ip_info)

    def _current_ip(self) -> Optional[str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        except Exception:
            ip = None
        finally:
            try:
                sock.close()
            except Exception:
                pass
        if not ip:
            try:
                out = subprocess.check_output(
                    ["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"],
                    text=True,
                    timeout=1,
                ).strip()
                ip = out or None
            except Exception:
                ip = None
        return ip

    def _run_thread(self, target) -> None:
        threading.Thread(target=target, daemon=True).start()

    def _set_status(self, var: tk.StringVar, text: str) -> None:
        try:
            self.after(0, lambda v=var, t=text: v.set(t))
        except Exception:
            pass

    def _repo_root(self) -> Path:
        base = Path(__file__).resolve()
        for candidate in [base] + list(base.parents):
            if (candidate / ".git").exists():
                return candidate
        return base.parent

    def _current_version_text(self) -> str:
        try:
            rev = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self._repo_root()),
                text=True,
            ).strip()
            return f"Versión actual: {rev}"
        except Exception:
            return "Versión actual: desconocida"

__all__ = [
    "HomeScreen",
    "FoodsScreen",
    "RecipesScreen",
    "SettingsScreen",
]
