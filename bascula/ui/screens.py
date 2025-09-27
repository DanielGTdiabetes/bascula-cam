"""UI screens for the modern Bascula interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from ..services.nutrition import FoodEntry
from .widgets import PALETTE, PrimaryButton, TotalsTable, WeightDisplay


if TYPE_CHECKING:
    from .app import BasculaApp


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
        decimals = self.app.settings.scale.decimals
        formatted = f"{value:.{decimals}f} {unit}"
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
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=30, pady=30)

        self._build_general(notebook)
        self._build_scale(notebook)
        self._build_network(notebook)
        self._build_diabetes(notebook)
        self._build_ota(notebook)
        self._build_miniweb(notebook)

    def _build_general(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="General")
        tk.Label(frame, text="Sonido", bg=PALETTE["panel"], font=("DejaVu Sans", 12, "bold")).pack(anchor="w", padx=20, pady=20)
        ttk.Checkbutton(frame, text="Activar sonido", variable=self.app.general_sound_var).pack(anchor="w", padx=20)
        tk.Scale(
            frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.app.general_volume_var,
        ).pack(fill="x", padx=20, pady=10)
        PrimaryButton(frame, text="Probar beep", command=self.app.audio_service.beep_ok).pack(
            anchor="w", padx=20, pady=10
        )

    def _build_scale(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Báscula")
        tk.Label(frame, text="Calibración", bg=PALETTE["panel"], font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=20, pady=20
        )
        ttk.Entry(frame, textvariable=self.app.scale_calibration_var).pack(anchor="w", padx=20)
        tk.Label(frame, text="Densidad ml", bg=PALETTE["panel"], font=("DejaVu Sans", 12, "bold")).pack(
            anchor="w", padx=20, pady=(20, 0)
        )
        ttk.Entry(frame, textvariable=self.app.scale_density_var).pack(anchor="w", padx=20)

    def _build_network(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Red")
        tk.Label(
            frame,
            text="Mini web en http://<ip>:%s" % self.app.settings.network.miniweb_port,
            bg=PALETTE["panel"],
        ).pack(anchor="w", padx=20, pady=20)

    def _build_diabetes(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Diabetes")
        ttk.Checkbutton(frame, text="Modo diabético", variable=self.app.diabetes_enabled_var).pack(
            anchor="w", padx=20, pady=20
        )
        ttk.Entry(frame, textvariable=self.app.diabetes_url_var).pack(anchor="w", padx=20)
        ttk.Entry(frame, textvariable=self.app.diabetes_token_var, show="*").pack(anchor="w", padx=20, pady=10)

    def _build_ota(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="OTA/Recovery")
        tk.Label(frame, text="Versión instalada: 1.0", bg=PALETTE["panel"]).pack(anchor="w", padx=20, pady=20)

    def _build_miniweb(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=PALETTE["panel"])
        notebook.add(frame, text="Mini-web")
        ttk.Checkbutton(frame, text="Habilitar mini-web", variable=self.app.miniweb_enabled_var).pack(
            anchor="w", padx=20, pady=20
        )


__all__ = [
    "HomeScreen",
    "FoodsScreen",
    "RecipesScreen",
    "SettingsScreen",
]
