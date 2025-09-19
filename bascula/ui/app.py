"""Tkinter UI entry point for Báscula Cam."""
from __future__ import annotations

import json
import logging
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from typing import Any, Dict, List, Optional

import yaml

from bascula.core.camera_scanner import CameraScanner
from bascula.core.nutrition import compute_totals
from bascula.core.scale import ScaleService
from bascula.core.tts import TextToSpeech, discover_tts

from .lightweight_widgets import PrimaryButton, SecondaryButton, ValueLabel
from .mascot import MascotCanvas
from .theme_classic import COLORS, SPACING, font

logger = logging.getLogger("bascula.ui.app")

CONFIG_PATH = Path.home() / ".bascula" / "config.yaml"
DATA_DIR = Path.home() / ".bascula" / "data"
FAVORITES_PATH = DATA_DIR / "favorites.json"


@dataclass
class FoodItem:
    name: str
    grams: float
    per_100g: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "grams": self.grams, "per_100g": self.per_100g}


class Screen(tk.Frame):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app

    def on_show(self) -> None:  # pragma: no cover - UI hook
        pass

    def on_hide(self) -> None:  # pragma: no cover - UI hook
        pass

    def refresh(self) -> None:  # pragma: no cover - UI hook
        pass


class HomeScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.mascot = MascotCanvas(self, width=360, height=260)
        self.mascot.grid(row=0, column=0, pady=(SPACING.padding, SPACING.padding))

        self.status_label = tk.Label(self, text="Báscula lista", font=font("md"), bg=COLORS["bg"], fg=COLORS["text"])
        self.status_label.grid(row=1, column=0, pady=(0, SPACING.padding))

        button_frame = tk.Frame(self, bg=COLORS["bg"])
        button_frame.grid(row=2, column=0, pady=(0, SPACING.padding))
        for index in range(5):
            button_frame.columnconfigure(index, weight=1)

        actions = [
            ("Pesar", self.app.show_scale),
            ("Recetas", lambda: self.app.show_screen("recipes")),
            ("Favoritos", lambda: self.app.show_screen("favorites")),
            ("Añadir", self.app.add_manual_food),
            ("Temporizador", lambda: self.app.show_screen("timer")),
        ]
        for column, (label, command) in enumerate(actions):
            button = PrimaryButton(button_frame, text=label, command=command)
            button.grid(row=0, column=column, padx=SPACING.padding, pady=SPACING.padding, sticky="ew")

        self.settings_button = SecondaryButton(button_frame, text="Ajustes", command=lambda: self.app.show_screen("settings"))
        self.settings_button.grid(row=1, column=2, pady=(SPACING.padding, 0))

    def refresh(self) -> None:
        weight = self.app.current_weight
        self.status_label.configure(text=f"Peso neto: {weight:0.1f} g")
        self.mascot.configure_state("happy" if self.app.scale_stable else "processing")


class ScaleScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self.mascot = MascotCanvas(self, width=320, height=220)
        self.mascot.grid(row=0, column=0, pady=SPACING.padding)

        self.weight_label = ValueLabel(self, text="0.0 g", size_key="xxl", mono_font=True, bg=COLORS["bg"])
        self.weight_label.grid(row=1, column=0, pady=(0, SPACING.padding))

        self.state_label = tk.Label(self, text="Leyendo", font=font("md"), bg=COLORS["bg"], fg=COLORS["muted"])
        self.state_label.grid(row=2, column=0, pady=(0, SPACING.padding))

        self.items_frame = tk.Frame(self, bg=COLORS["surface"], bd=1, relief=tk.GROOVE)
        self.items_frame.grid(row=3, column=0, sticky="nsew", padx=SPACING.gutter, pady=SPACING.padding)
        self.items_frame.columnconfigure(0, weight=1)
        self.items_list = tk.Listbox(self.items_frame, font=font("sm"), height=8)
        self.items_list.grid(row=0, column=0, sticky="nsew", padx=SPACING.padding, pady=SPACING.padding)
        self.totals_label = tk.Label(self.items_frame, text="Totales: -", font=font("md"), bg=COLORS["surface"], fg=COLORS["text"])
        self.totals_label.grid(row=1, column=0, sticky="ew", padx=SPACING.padding, pady=(0, SPACING.padding))

        button_frame = tk.Frame(self, bg=COLORS["bg"])
        button_frame.grid(row=4, column=0, pady=SPACING.padding)
        btn_zero = PrimaryButton(button_frame, text="Cero", command=self.app.zero_scale)
        btn_zero.grid(row=0, column=0, padx=SPACING.padding)
        btn_tare = PrimaryButton(button_frame, text="Tara", command=self.app.tare_scale)
        btn_tare.grid(row=0, column=1, padx=SPACING.padding)
        btn_add = PrimaryButton(button_frame, text="Añadir alimento", command=self.app.capture_food)
        btn_add.grid(row=0, column=2, padx=SPACING.padding)
        btn_close = SecondaryButton(button_frame, text="Cerrar", command=self.app.show_home)
        btn_close.grid(row=0, column=3, padx=SPACING.padding)
        self.refresh()

    def refresh(self) -> None:
        self.refresh_items(self.app.items)
        self.update_weight(self.app.current_weight, self.app.scale_stable)

    def update_weight(self, grams: float, stable: bool) -> None:
        self.weight_label.configure(text=f"{grams:0.1f} g")
        self.state_label.configure(text="Estable" if stable else "Leyendo")
        self.mascot.configure_state("happy" if stable else "processing")

    def refresh_items(self, items: List[FoodItem]) -> None:
        self.items_list.delete(0, tk.END)
        for item in items:
            self.items_list.insert(tk.END, f"{item.name} · {item.grams:0.1f} g")
        totals = compute_totals(item.to_dict() for item in items)
        self.totals_label.configure(
            text=(
                f"Totales: {totals['carbs']:0.1f} g HC · {totals['kcal']:0.1f} kcal · "
                f"Proteína {totals['protein']:0.1f} g · Grasa {totals['fat']:0.1f} g"
            )
        )


class FavoritesScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        fav_title = tk.Label(self, text="Favoritos", font=font("xl"), bg=COLORS["bg"], fg=COLORS["text"])
        fav_title.grid(row=0, column=0, pady=SPACING.padding)

        self.listbox = tk.Listbox(self, font=font("md"), height=12)
        self.listbox.grid(row=1, column=0, padx=SPACING.gutter, pady=SPACING.padding, sticky="nsew")

        button_frame = tk.Frame(self, bg=COLORS["bg"])
        button_frame.grid(row=2, column=0, pady=SPACING.padding)
        btn_use = PrimaryButton(button_frame, text="Usar", command=self._use_favorite)
        btn_use.grid(row=0, column=0, padx=SPACING.padding)
        btn_delete = SecondaryButton(button_frame, text="Borrar", command=self._delete_favorite)
        btn_delete.grid(row=0, column=1, padx=SPACING.padding)
        btn_back = SecondaryButton(button_frame, text="Cerrar", command=self.app.show_home)
        btn_back.grid(row=0, column=2, padx=SPACING.padding)

    def refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        for favorite in self.app.favorites:
            self.listbox.insert(tk.END, favorite["name"])

    def _use_favorite(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        favorite = self.app.favorites[selection[0]]
        grams = self.app.current_weight
        self.app.add_food_item(favorite["name"], grams, favorite["per_100g"])
        messagebox.showinfo("Favorito", f"Añadido {favorite['name']} ({grams:0.1f} g)")
        self.app.show_scale()

    def _delete_favorite(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        del self.app.favorites[idx]
        self.app.save_favorites()
        self.refresh()


class TimerScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)

        timer_title = tk.Label(self, text="Temporizador", font=font("xl"), bg=COLORS["bg"], fg=COLORS["text"])
        timer_title.grid(row=0, column=0, pady=SPACING.padding)

        self.countdown_label = ValueLabel(self, text="00:00", size_key="xl", bg=COLORS["bg"], mono_font=True)
        self.countdown_label.grid(row=1, column=0, pady=SPACING.padding)

        presets_frame = tk.Frame(self, bg=COLORS["bg"])
        presets_frame.grid(row=2, column=0, pady=SPACING.padding)
        for minutes in (1, 3, 5, 10):
            PrimaryButton(presets_frame, text=f"{minutes} min", command=lambda m=minutes: self.app.start_timer(m * 60)).pack(side=tk.LEFT, padx=SPACING.padding)

        self.custom_entry = tk.Entry(self, font=font("md"))
        self.custom_entry.grid(row=3, column=0, pady=(0, SPACING.padding))
        btn_custom = SecondaryButton(self, text="Iniciar", command=self._start_custom)
        btn_custom.grid(row=4, column=0)
        btn_timer_back = SecondaryButton(self, text="Cerrar", command=self.app.show_home)
        btn_timer_back.grid(row=5, column=0, pady=SPACING.padding)

    def refresh(self) -> None:
        remaining = max(0, self.app.timer_remaining)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.countdown_label.configure(text=f"{minutes:02d}:{seconds:02d}")

    def _start_custom(self) -> None:
        try:
            seconds = int(float(self.custom_entry.get()) * 60)
        except (TypeError, ValueError):
            messagebox.showerror("Temporizador", "Introduce minutos válidos")
            return
        self.app.start_timer(max(1, seconds))


class RecipesScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        recipes_title = tk.Label(self, text="Recetas", font=font("xl"), bg=COLORS["bg"], fg=COLORS["text"])
        recipes_title.grid(row=0, column=0, pady=SPACING.padding)

        self.text = tk.Text(self, wrap="word", font=font("sm"), width=50, height=18)
        self.text.grid(row=1, column=0, padx=SPACING.gutter, pady=SPACING.padding)

        button_frame = tk.Frame(self, bg=COLORS["bg"])
        button_frame.grid(row=2, column=0, pady=SPACING.padding)
        btn_generate = PrimaryButton(button_frame, text="Generar", command=self.app.generate_recipe)
        btn_generate.grid(row=0, column=0, padx=SPACING.padding)
        btn_recipe_back = SecondaryButton(button_frame, text="Cerrar", command=self.app.show_home)
        btn_recipe_back.grid(row=0, column=1, padx=SPACING.padding)

    def display_recipe(self, content: str) -> None:
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)


class SettingsScreen(Screen):
    def __init__(self, parent: tk.Widget, app: "BasculaApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        settings_title = tk.Label(self, text="Ajustes", font=font("xl"), bg=COLORS["bg"], fg=COLORS["text"])
        settings_title.grid(row=0, column=0, pady=SPACING.padding)

        self.sections: Dict[str, tk.Text] = {}
        for row, section in enumerate(
            [
                "Báscula",
                "Cámara",
                "Miniweb",
                "Audio/TTS",
                "Red",
                "ChatGPT",
                "Diabetes",
                "Acerca de",
            ],
            start=1,
        ):
            frame = tk.LabelFrame(self, text=section, font=font("md"), bg=COLORS["bg"], fg=COLORS["text"])
            frame.grid(row=row, column=0, padx=SPACING.gutter, pady=SPACING.padding, sticky="ew")
            text_widget = tk.Text(frame, height=2, font=font("sm"))
            text_widget.pack(fill="x", padx=SPACING.padding, pady=SPACING.padding)
            self.sections[section] = text_widget

        btn_save = PrimaryButton(self, text="Guardar", command=self._save)
        btn_save.grid(row=len(self.sections) + 1, column=0, pady=SPACING.padding)
        btn_settings_back = SecondaryButton(self, text="Cerrar", command=self.app.show_home)
        btn_settings_back.grid(row=len(self.sections) + 2, column=0, pady=(0, SPACING.padding))

    def refresh(self) -> None:
        for section, widget in self.sections.items():
            key = section.lower().replace("/", "_")
            value = self.app.config.get(key, "")
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, value)

    def _save(self) -> None:
        data = {}
        for section, widget in self.sections.items():
            key = section.lower().replace("/", "_")
            data[key] = widget.get("1.0", tk.END).strip()
        self.app.save_config(data)
        messagebox.showinfo("Ajustes", "Configuración guardada")


class BasculaApp:
    def __init__(self, *, theme: str = "classic") -> None:
        self.root = tk.Tk()
        self.root.title("Báscula Cam")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(800, 600)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.scale_service = ScaleService()
        self.scale_service.add_stability_listener(self._handle_stability)
        try:
            self.camera_scanner = CameraScanner()
        except Exception:
            logger.warning("Cámara no disponible", exc_info=True)
            self.camera_scanner = None
        self.tts: TextToSpeech = discover_tts()
        self.current_weight: float = 0.0
        self.scale_stable: bool = False
        self.items: List[FoodItem] = []
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.favorites: List[Dict[str, Any]] = self._load_favorites()
        self.config: Dict[str, Any] = self._load_config()
        self.timer_remaining: int = 0
        self.timer_total: int = 0
        self._timer_started_at: Optional[float] = None

        self.container = tk.Frame(self.root, bg=COLORS["bg"])
        self.container.pack(fill="both", expand=True)

        self.screens: Dict[str, Screen] = {
            "home": HomeScreen(self.container, self),
            "scale": ScaleScreen(self.container, self),
            "favorites": FavoritesScreen(self.container, self),
            "recipes": RecipesScreen(self.container, self),
            "timer": TimerScreen(self.container, self),
            "settings": SettingsScreen(self.container, self),
        }
        for screen in self.screens.values():
            screen.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
            screen.lower()

        self.active_screen: Optional[str] = None
        self.show_home()
        self._schedule_tick()

    # Navigation ---------------------------------------------------------
    def show_home(self) -> None:
        self.show_screen("home")

    def show_scale(self) -> None:
        self.show_screen("scale")

    def show_screen(self, name: str) -> None:
        if self.active_screen == name:
            target = self.screens[name]
            target.refresh()
            return
        if self.active_screen:
            current = self.screens[self.active_screen]
            current.on_hide()
            current.lower()
        screen = self.screens[name]
        screen.refresh()
        screen.lift()
        screen.on_show()
        self.active_screen = name

    # Scale operations ---------------------------------------------------
    def _schedule_tick(self) -> None:
        self.root.after(250, self._tick)

    def _tick(self) -> None:
        self.current_weight = self.scale_service.read_weight()
        if self.active_screen == "scale":
            scale_screen: ScaleScreen = self.screens["scale"]  # type: ignore[assignment]
            scale_screen.update_weight(self.current_weight, self.scale_stable)
        if self.active_screen == "home":
            home: HomeScreen = self.screens["home"]  # type: ignore[assignment]
            home.refresh()
        if self.active_screen == "timer":
            timer: TimerScreen = self.screens["timer"]  # type: ignore[assignment]
            timer.refresh()
        self._update_timer_state()
        self._schedule_tick()

    def _update_timer_state(self) -> None:
        if self._timer_started_at is None:
            return
        elapsed = int(time.time() - self._timer_started_at)
        remaining = max(0, self.timer_total - elapsed)
        if remaining != self.timer_remaining:
            self.timer_remaining = remaining
            if remaining == 0:
                self._on_timer_finished()

    def _handle_stability(self, stable: bool) -> None:
        self.scale_stable = stable

    def tare_scale(self) -> None:
        self.scale_service.tare()

    def zero_scale(self) -> None:
        self.scale_service.zero()

    # Items --------------------------------------------------------------
    def add_food_item(self, name: str, grams: float, per_100g: Dict[str, float]) -> None:
        item = FoodItem(name=name, grams=grams, per_100g=per_100g)
        self.items.append(item)
        scale_screen: ScaleScreen = self.screens["scale"]  # type: ignore[assignment]
        scale_screen.refresh_items(self.items)
        self._maybe_store_favorite(item)

    def _maybe_store_favorite(self, item: FoodItem) -> None:
        if any(fav["name"] == item.name for fav in self.favorites):
            return
        if messagebox.askyesno("Favoritos", f"¿Guardar {item.name} como favorito?"):
            self.favorites.append(item.to_dict())
            self.save_favorites()

    def capture_food(self) -> None:
        if self.camera_scanner is None:
            messagebox.showwarning("Cámara", "Cámara no disponible")
            return
        threading.Thread(target=self._capture_food_worker, daemon=True).start()

    def _capture_food_worker(self) -> None:
        try:
            result = self.camera_scanner.analyze()
        except Exception:
            logger.exception("Fallo analizando alimento")
            self._show_async_message("Error", "No se pudo analizar el alimento")
            return
        grams = self.current_weight
        self.root.after(0, lambda: self.add_food_item(result["name"], grams, result["per_100g"]))

    def add_manual_food(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Añadir alimento")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        name_label = tk.Label(dialog, text="Nombre", bg=COLORS["bg"], fg=COLORS["text"], font=font("md"))
        name_label.grid(row=0, column=0, padx=SPACING.padding, pady=SPACING.padding)
        name_entry = tk.Entry(dialog, font=font("md"))
        name_entry.grid(row=0, column=1, padx=SPACING.padding, pady=SPACING.padding)
        fields = {}
        for row, key in enumerate(["carbs", "kcal", "protein", "fat"], start=1):
            label = tk.Label(dialog, text=f"{key} por 100 g", bg=COLORS["bg"], fg=COLORS["text"], font=font("sm"))
            label.grid(row=row, column=0, padx=SPACING.padding, pady=SPACING.padding)
            entry = tk.Entry(dialog, font=font("sm"))
            entry.grid(row=row, column=1, padx=SPACING.padding, pady=SPACING.padding)
            fields[key] = entry

        def _submit() -> None:
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Añadir", "Introduce un nombre")
                return
            try:
                per_100g = {key: float(entry.get() or 0.0) for key, entry in fields.items()}
            except ValueError:
                messagebox.showerror("Añadir", "Valores numéricos inválidos")
                return
            grams = self.current_weight
            self.add_food_item(name, grams, per_100g)
            dialog.destroy()

        btn_dialog_save = PrimaryButton(dialog, text="Guardar", command=_submit)
        btn_dialog_save.grid(row=5, column=0, columnspan=2, pady=SPACING.padding)

    # Favorites ----------------------------------------------------------
    def _load_favorites(self) -> List[Dict[str, Any]]:
        if not FAVORITES_PATH.exists():
            return []
        try:
            return json.loads(FAVORITES_PATH.read_text("utf-8"))
        except Exception:
            logger.warning("Favoritos corruptos", exc_info=True)
            return []

    def save_favorites(self) -> None:
        try:
            FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
            FAVORITES_PATH.write_text(json.dumps(self.favorites, indent=2), "utf-8")
        except Exception:
            logger.warning("No se pudo guardar favoritos", exc_info=True)

    # Config -------------------------------------------------------------
    def _load_config(self) -> Dict[str, Any]:
        if not CONFIG_PATH.exists():
            return {}
        try:
            return yaml.safe_load(CONFIG_PATH.read_text("utf-8")) or {}
        except Exception:
            logger.warning("Config inválida", exc_info=True)
            return {}

    def save_config(self, data: Dict[str, Any]) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle)
        self.config = data

    # Recipes ------------------------------------------------------------
    def generate_recipe(self) -> None:
        items = [item.to_dict() for item in self.items]
        if not items:
            messagebox.showinfo("Recetas", "Añade alimentos antes de generar una receta")
            return
        threading.Thread(target=self._recipe_worker, args=(items,), daemon=True).start()

    def _recipe_worker(self, items: List[Dict[str, Any]]) -> None:
        try:
            import openai  # type: ignore
        except Exception:
            content = "Receta sugerida:\n" + "\n".join(
                f"- {item['name']} ({item['grams']:.0f} g)" for item in items
            )
            self.root.after(0, lambda: self._display_recipe(content))
            return
        client = openai.OpenAI()  # type: ignore[attr-defined]
        names = ", ".join(item["name"] for item in items)
        prompt = f"Genera una receta sencilla usando: {names}. Devuelve texto en español."
        try:
            response = client.responses.create(model="gpt-4o-mini", input=prompt, max_output_tokens=400)
            text = response.output[0].content[0].text  # type: ignore[index]
        except Exception:
            logger.warning("Fallo generando receta", exc_info=True)
            text = "Receta sugerida:\n" + "\n".join(
                f"- {item['name']}" for item in items
            )
        self.root.after(0, lambda: self._display_recipe(text))

    def _display_recipe(self, content: str) -> None:
        screen: RecipesScreen = self.screens["recipes"]  # type: ignore[assignment]
        screen.display_recipe(content)
        self.show_screen("recipes")

    # Timer --------------------------------------------------------------
    def start_timer(self, seconds: int) -> None:
        self.timer_total = seconds
        self.timer_remaining = seconds
        self._timer_started_at = time.time()
        self.show_screen("timer")

    def _on_timer_finished(self) -> None:
        self.timer_remaining = 0
        self._timer_started_at = None
        self.tts.say("Temporizador finalizado")
        try:
            self.screens["home"].mascot.configure_state("happy")  # type: ignore[attr-defined]
        except Exception:
            pass
        messagebox.showinfo("Temporizador", "Tiempo cumplido")

    # Helpers ------------------------------------------------------------
    def _show_async_message(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showerror(title, message))

    def _on_close(self) -> None:
        self.root.destroy()

    # Lifecycle ----------------------------------------------------------
    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            try:
                self.scale_service.shutdown()
            except Exception:
                logger.debug("Error al cerrar báscula", exc_info=True)


__all__ = ["BasculaApp"]
