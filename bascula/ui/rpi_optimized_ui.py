"""Simplified UI tuned for Raspberry Pi 5 kiosks."""
from __future__ import annotations

import logging
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Callable, Dict, List, Optional

from bascula.services.bg_monitor import BgMonitor
from bascula.services.event_bus import EventBus
from bascula.services.scale import ScaleService
from bascula.services.tare_manager import TareManager
from bascula.state import AppState
from bascula.utils import load_config

from .failsafe_mascot import MASCOT_STATES, MascotCanvas, MascotPlaceholder
from .lightweight_widgets import AccentButton, Card, ScrollFrame, ValueLabel, WidgetPool, format_weight
from .memory_monitor import MemoryMonitor
from .rpi_camera_manager import RpiCameraManager
from .rpi_config import PRIMARY_COLORS, TOUCH, configure_root, ensure_env_defaults
from .simple_animations import AnimationManager

logger = logging.getLogger("bascula.ui.rpi")

try:  # Optional voice prompts
    from bascula.services.voice import VoiceService
except Exception:  # pragma: no cover - optional dependency missing in CI
    VoiceService = None  # type: ignore

try:
    from bascula.services.vision import VisionService
except Exception:  # pragma: no cover
    VisionService = None  # type: ignore

try:
    from bascula.services.barcode import decode_barcodes as decode_barcode
except Exception:  # pragma: no cover
    decode_barcode = None  # type: ignore


@dataclass(slots=True)
class FoodEntry:
    name: str
    weight: float
    timestamp: float
    macros: Dict[str, Any]

    def as_row(self) -> str:
        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M")
        carbs = self.macros.get("carbs", "-")
        prot = self.macros.get("protein", "-")
        fats = self.macros.get("fat", "-")
        return f"{ts}  {self.name}  {format_weight(self.weight)}  C:{carbs} P:{prot} G:{fats}"


class BaseScreen(tk.Frame):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, bg=PRIMARY_COLORS["bg"])
        self.app = app
        self.visible = False

    def on_show(self) -> None:
        self.visible = True

    def on_hide(self) -> None:
        self.visible = False

    def refresh(self) -> None:
        pass


class HomeScreen(BaseScreen):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        header.grid(row=0, column=0, pady=(12, 0))
        self.weight_label = ValueLabel(header, text="0 g", size_key="title", bg=PRIMARY_COLORS["bg"])
        self.weight_label.pack()
        self.status_label = tk.Label(
            header,
            text="Coloca alimento o toca Tara",
            bg=PRIMARY_COLORS["bg"],
            fg=PRIMARY_COLORS["muted"],
            font=("Inter", 18),
        )
        self.status_label.pack(pady=(4, 0))

        center = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        center.grid(row=1, column=0, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(0, weight=1)
        self.mascot_holder = tk.Frame(center, bg=PRIMARY_COLORS["bg"])
        self.mascot_holder.grid(row=0, column=0, sticky="nsew")
        self._ensure_mascot()

        actions = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        actions.grid(row=2, column=0, pady=(18, 12))
        actions.columnconfigure((0, 1, 2), weight=1)
        self.tare_btn = AccentButton(actions, text="TARA", command=self._handle_tare)
        self.tare_btn.grid(row=0, column=0, padx=TOUCH.button_spacing)
        self.scan_btn = AccentButton(actions, text="ESCANEAR", command=self._handle_scan)
        self.scan_btn.grid(row=0, column=1, padx=TOUCH.button_spacing)
        self.history_btn = AccentButton(actions, text="HISTORIAL", command=lambda: self.app.show_screen("history"))
        self.history_btn.grid(row=0, column=2, padx=TOUCH.button_spacing)

        footer = Card(self, bg=PRIMARY_COLORS["surface"])
        footer.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 16))
        footer.columnconfigure(0, weight=1)
        self.last_food_label = tk.Label(
            footer,
            text="Sin alimentos registrados",
            bg=PRIMARY_COLORS["surface"],
            fg=PRIMARY_COLORS["text"],
            font=("Inter", 16),
            anchor="w",
        )
        self.last_food_label.grid(row=0, column=0, sticky="ew", padx=18, pady=12)

    def _ensure_mascot(self) -> None:
        if self.app.mascot_widget is None:
            try:
                self.app.mascot_widget = MascotCanvas(self.mascot_holder, manager=self.app.animations)
                self.app.mascot_widget.pack(expand=True)
            except Exception:
                logger.exception("Mascota Canvas falló; usando placeholder")
                self.app.mascot_widget = MascotPlaceholder(self.mascot_holder)
                self.app.mascot_widget.pack(expand=True)
        elif self.app.mascot_widget.master is self.mascot_holder:
            self.app.mascot_widget.pack(expand=True)

    def on_show(self) -> None:
        super().on_show()
        self._ensure_mascot()
        self.refresh()

    def on_hide(self) -> None:
        super().on_hide()
        if self.app.mascot_widget is not None and self.app.mascot_widget.master is self.mascot_holder:
            try:
                self.app.mascot_widget.pack_forget()
            except Exception:
                pass

    def refresh(self) -> None:
        weight = self.app.net_weight
        self.weight_label.configure(text=format_weight(weight))
        if self.app.scale_stable:
            self.status_label.configure(text="Peso estable", fg=PRIMARY_COLORS["accent"])
        else:
            self.status_label.configure(text="Leyendo...", fg=PRIMARY_COLORS["muted"])
        if self.app.food_history:
            last = self.app.food_history[-1]
            self.last_food_label.configure(text=last.as_row())
        else:
            self.last_food_label.configure(text="Sin alimentos registrados")

    def _handle_tare(self) -> None:
        self.app.perform_tare()

    def _handle_scan(self) -> None:
        self.app.scan_current_food()


class ScaleScreen(BaseScreen):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        title = ValueLabel(self, text="Revisa el peso", size_key="subtitle", bg=PRIMARY_COLORS["bg"])
        title.grid(row=0, column=0, pady=(12, 0))

        card = Card(self)
        card.grid(row=1, column=0, padx=24, pady=12, sticky="nsew")
        card.columnconfigure(0, weight=1)
        self.delta_label = ValueLabel(card, text="Δ 0 g", size_key="subtitle")
        self.delta_label.grid(row=0, column=0, pady=(12, 0))
        self.total_label = ValueLabel(card, text="Total 0 g", size_key="title")
        self.total_label.grid(row=1, column=0, pady=(6, 18))

        self.message_label = tk.Label(
            card,
            text="Confirma para guardar",
            bg=PRIMARY_COLORS["surface"],
            fg=PRIMARY_COLORS["muted"],
            font=("Inter", 16),
        )
        self.message_label.grid(row=2, column=0, pady=(0, 16))

        buttons = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        buttons.grid(row=2, column=0, pady=(4, 12))
        self.confirm_btn = AccentButton(buttons, text="CONFIRMAR", command=self._confirm)
        self.confirm_btn.grid(row=0, column=0, padx=TOUCH.button_spacing)
        self.cancel_btn = AccentButton(buttons, text="CANCELAR", command=self._cancel, bg=PRIMARY_COLORS["accent_dark"])
        self.cancel_btn.grid(row=0, column=1, padx=TOUCH.button_spacing)

    def refresh(self) -> None:
        self.delta_label.configure(text=f"Δ {format_weight(self.app.session_delta)}")
        self.total_label.configure(text=f"Total {format_weight(self.app.net_weight)}")
        if self.app.scale_stable:
            self.message_label.configure(text="Listo para guardar", fg=PRIMARY_COLORS["accent"])
        else:
            self.message_label.configure(text="Esperando estabilidad...", fg=PRIMARY_COLORS["muted"])

    def _confirm(self) -> None:
        self.app.confirm_food()

    def _cancel(self) -> None:
        self.app.cancel_food()


class HistoryScreen(BaseScreen):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", pady=(12, 0))
        ValueLabel(header, text="Historial del día", size_key="subtitle", bg=PRIMARY_COLORS["bg"]).pack()
        self.summary_label = tk.Label(
            header,
            text="",
            bg=PRIMARY_COLORS["bg"],
            fg=PRIMARY_COLORS["muted"],
            font=("Inter", 16),
        )
        self.summary_label.pack(pady=(2, 0))

        self.scroll = ScrollFrame(self)
        self.scroll.grid(row=1, column=0, padx=18, pady=12, sticky="nsew")
        self.rows_pool = WidgetPool(lambda parent: tk.Label(parent, anchor="w", bg=PRIMARY_COLORS["bg"], fg=PRIMARY_COLORS["text"], font=("Inter", 16)))
        self._active_rows: List[tk.Label] = []

        buttons = tk.Frame(self, bg=PRIMARY_COLORS["bg"])
        buttons.grid(row=2, column=0, pady=(4, 12))
        self.send_btn = AccentButton(buttons, text="ENVIAR", command=self._send)
        self.send_btn.grid(row=0, column=0, padx=TOUCH.button_spacing)
        self.clear_btn = AccentButton(buttons, text="LIMPIAR", command=self._clear)
        self.clear_btn.grid(row=0, column=1, padx=TOUCH.button_spacing)

    def refresh(self) -> None:
        for row in self._active_rows:
            self.rows_pool.release(row)
        self._active_rows.clear()
        totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0, "weight": 0.0}
        for entry in self.app.food_history:
            row = self.rows_pool.acquire(self.scroll.inner)
            row.configure(text=entry.as_row())
            row.pack(fill="x", padx=8, pady=4)
            self._active_rows.append(row)
            totals["weight"] += entry.weight
            for key in ("carbs", "protein", "fat"):
                try:
                    totals[key] += float(entry.macros.get(key, 0) or 0)
                except Exception:
                    continue
        summary = f"Total: {format_weight(totals['weight'])}  C:{totals['carbs']:.1f} P:{totals['protein']:.1f} G:{totals['fat']:.1f}"
        self.summary_label.configure(text=summary)

    def _send(self) -> None:
        self.app.send_to_nightscout()

    def _clear(self) -> None:
        self.app.clear_history()


class PlaceholderScreen(BaseScreen):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp", *, title: str, message: str) -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        card = Card(self)
        card.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        card.columnconfigure(0, weight=1)
        ValueLabel(card, text=title, size_key="subtitle").grid(row=0, column=0, pady=(16, 12))
        tk.Label(
            card,
            text=message,
            bg=PRIMARY_COLORS["surface"],
            fg=PRIMARY_COLORS["text"],
            font=("Inter", 18),
            wraplength=720,
            justify="center",
        ).grid(row=1, column=0, padx=18, pady=(0, 16))


class TopBar(tk.Frame):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, bg=PRIMARY_COLORS["surface"], height=64)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.clock_label = tk.Label(
            self,
            text="",
            bg=PRIMARY_COLORS["surface"],
            fg=PRIMARY_COLORS["text"],
            font=("Inter", 18, "bold"),
        )
        self.clock_label.grid(row=0, column=0, sticky="w", padx=18)
        self.icon_bar = tk.Frame(self, bg=PRIMARY_COLORS["surface"])
        self.icon_bar.grid(row=0, column=1, sticky="e", padx=12)
        self.buttons: Dict[str, AccentButton] = {}
        self._build_buttons()
        self._job: Optional[str] = None
        self._update_clock()

    def _build_buttons(self) -> None:
        configs = [
            ("home", "🏠"),
            ("scale", "⚖"),
            ("history", "📜"),
        ]
        optional = self.app.optional_screens()
        if "focus" in optional:
            configs.append(("focus", "🧘"))
        overflow_needed = len(optional - {"focus"}) > 0
        for name, icon in configs:
            btn = AccentButton(self.icon_bar, text=icon, command=lambda n=name: self.app.show_screen(n))
            btn.configure(width=4)
            btn.pack(side="left", padx=6)
            self.buttons[name] = btn
        if overflow_needed:
            overflow = tk.Menubutton(
                self.icon_bar,
                text="⋯",
                bg=PRIMARY_COLORS["accent"],
                fg=PRIMARY_COLORS["bg"],
                font=("Inter", 20, "bold"),
                relief="flat",
                activebackground=PRIMARY_COLORS["accent_mid"],
            )
            menu = tk.Menu(overflow, tearoff=False)
            for name in sorted(optional - {"focus"}):
                menu.add_command(label=name.capitalize(), command=lambda n=name: self.app.show_screen(n))
            overflow.configure(menu=menu)
            overflow.pack(side="left", padx=6)

    def _update_clock(self) -> None:
        now = time.strftime("%H:%M")
        self.clock_label.configure(text=now)
        self._job = self.after(1000, self._update_clock)

    def destroy(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        super().destroy()


class RpiOptimizedApp:
    def __init__(self, root: Optional[tk.Tk] = None, *, theme: str = "retro") -> None:
        ensure_env_defaults()
        self.logger = logger
        self.cfg = load_config()
        self.state = AppState()
        self.event_bus = EventBus()
        self.voice: Optional[VoiceService] = None
        if VoiceService is not None:
            try:
                self.voice = VoiceService()
            except Exception:
                self.logger.warning("VoiceService no disponible", exc_info=True)
        self.vision: Optional[VisionService] = None
        self._vision_ready = False
        self._pending_capture: Optional[str] = None
        self.root = root or tk.Tk()
        configure_root(self.root)
        self.animations = AnimationManager(self.root)
        self.memory = MemoryMonitor()
        self.tare = TareManager()
        self.scale_service = ScaleService.safe_create(logger=self.logger, config=self.cfg)
        if isinstance(self.scale_service, ScaleService):
            self.scale_service.on_tick(self._on_scale_tick)
        self.net_weight: float = 0.0
        self.scale_stable = False
        self.session_delta: float = 0.0
        self.last_weight: float = 0.0
        self.food_history: List[FoodEntry] = []
        self.mascot_widget: Optional[tk.Widget] = None
        self.mascot_state = "idle"
        self.camera = RpiCameraManager()
        self.bg_monitor = BgMonitor(self, interval_s=90)
        self.bg_monitor.start()
        self._build_layout()
        self._factories: Dict[str, Callable[[tk.Widget], BaseScreen]] = {
            "home": lambda parent: HomeScreen(parent, self),
            "scale": lambda parent: ScaleScreen(parent, self),
            "history": lambda parent: HistoryScreen(parent, self),
            "settings": lambda parent: PlaceholderScreen(parent, self, title="Ajustes", message="Configuración avanzada disponible en la versión completa."),
        }
        self._register_optional_factories()
        self.screens: Dict[str, Optional[BaseScreen]] = {name: None for name in self._factories}
        self.current_screen: Optional[str] = None
        self.show_screen("home")

    def _build_layout(self) -> None:
        self.root.configure(bg=PRIMARY_COLORS["bg"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.topbar = TopBar(self.root, self)
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.content = tk.Frame(self.root, bg=PRIMARY_COLORS["bg"])
        self.content.grid(row=1, column=0, sticky="nsew")

    def optional_screens(self) -> set[str]:
        return set(self._factories.keys()) - {"home", "scale", "history"}

    def _register_optional_factories(self) -> None:
        mapping = {
            "focus": ("bascula.ui.focus_screen", "FocusScreen"),
            "diabetes": ("bascula.ui.screens_diabetes", "DiabetesScreen"),
            "nightscout": ("bascula.ui.screens_nightscout", "NightscoutScreen"),
            "wifi": ("bascula.ui.screens_wifi", "WifiScreen"),
            "apikey": ("bascula.ui.screens_apikey", "ApiKeyScreen"),
        }
        for name, (module_name, class_name) in mapping.items():
            try:
                module = import_module(module_name)
                screen_cls = getattr(module, class_name)
            except Exception:
                self.logger.warning("Pantalla opcional %s no disponible", name)
                continue
            self._factories[name] = lambda parent, cls=screen_cls: cls(parent, self)  # type: ignore[arg-type]

    def show_screen(self, name: str) -> None:
        if name not in self._factories:
            self.logger.warning("Pantalla %s no registrada", name)
            return
        for screen_name, screen in list(self.screens.items()):
            if screen_name != name and screen is not None and screen.visible:
                screen.on_hide()
                screen.pack_forget()
        screen = self.screens.get(name)
        if screen is None:
            try:
                screen = self._factories[name](self.content)
            except Exception:
                self.logger.exception("No se pudo crear la pantalla %s", name)
                return
            self.screens[name] = screen
        if screen is None:
            return
        screen.pack(expand=True, fill="both")
        screen.on_show()
        screen.refresh()
        self.current_screen = name
        if self.mascot_widget is not None and hasattr(self.mascot_widget, "configure_state"):
            state = "idle" if name == "home" else "processing"
            try:
                self.mascot_widget.configure_state(state)  # type: ignore[attr-defined]
            except Exception:
                pass
        self.memory.maybe_collect()

    def close(self) -> None:
        try:
            self.bg_monitor.stop()
        except Exception:
            pass
        try:
            if isinstance(self.scale_service, ScaleService):
                self.scale_service.stop()
        except Exception:
            pass
        try:
            self.animations.cancel_all()
        except Exception:
            pass
        self.root.destroy()

    def run(self) -> None:
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("UI interrumpida por el usuario")
        finally:
            self.close()

    # ------------------------------------------------------------------ scale events
    def _on_scale_tick(self, weight: float, stable: bool) -> None:
        self.last_weight = weight
        self.scale_stable = bool(stable)
        self.net_weight = self.tare.compute_net(weight)
        if not self.scale_stable:
            self.session_delta = self.net_weight
        self._update_screen_data()

    def _update_screen_data(self) -> None:
        if self.current_screen and self.current_screen in self.screens:
            screen = self.screens[self.current_screen]
            try:
                screen.refresh()
            except Exception:
                self.logger.exception("Error refrescando pantalla %s", self.current_screen)

    # ------------------------------------------------------------------ actions
    def perform_tare(self) -> None:
        self.tare.set_tare(self.last_weight)
        self.session_delta = 0.0
        self.event_bus.publish("TARA", {"weight": self.last_weight})
        self._update_screen_data()

    def scan_current_food(self) -> None:
        if decode_barcode is None and VisionService is None:
            self.show_mascot_message("Escáner no disponible")
            return
        self.show_mascot_message("Analizando...", state="processing")
        # Lazy import of heavy models
        if not self._vision_ready and VisionService is not None:
            try:
                model = self.cfg.get("vision_model", "")
                labels = self.cfg.get("vision_labels", "")
                if model and labels:
                    self.vision = VisionService(model, labels)
                    self._vision_ready = True
            except Exception:
                self.logger.exception("Visión IA no disponible")
        if decode_barcode is not None:
            self.logger.info("Escaneo barcode placeholder (sin cámara)")
        if self.camera.available():
            container = tk.Toplevel(self.root, bg=PRIMARY_COLORS["bg"])
            container.title("Escaneo")
            preview = tk.Frame(container, width=320, height=240, bg="#000")
            preview.pack(padx=12, pady=12)
            self.camera.start_preview(preview)
            container.after(4200, container.destroy)

    def confirm_food(self) -> None:
        entry = FoodEntry(
            name="Alimento",
            weight=self.net_weight,
            timestamp=time.time(),
            macros={"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        )
        self.food_history.append(entry)
        self.session_delta = 0.0
        self.event_bus.publish("WEIGHT_CAPTURED", {"weight": self.net_weight})
        self.show_screen("home")

    def cancel_food(self) -> None:
        self.session_delta = 0.0
        self.show_screen("home")

    def clear_history(self) -> None:
        self.food_history.clear()
        if "history" in self.screens:
            self.screens["history"].refresh()

    def send_to_nightscout(self) -> None:
        self.logger.info("Envío a Nightscout (placeholder)")

    # ------------------------------------------------------------------ mascot
    def show_mascot_message(self, text: str, *, state: str = "idle", icon: str = "", icon_color: str = "") -> None:
        state = state if state in MASCOT_STATES else "idle"
        icon = icon or MASCOT_STATES[state]["symbol"]
        icon_color = icon_color or MASCOT_STATES[state]["color"]
        self.logger.info("Mascota: %s %s", icon, text)
        if isinstance(self.mascot_widget, (MascotCanvas, MascotPlaceholder)):
            try:
                self.mascot_widget.configure_state(state)  # type: ignore[attr-defined]
            except Exception:
                pass

    # ------------------------------------------------------------------ BG monitor callbacks
    def on_bg_update(self, value: Optional[int], trend: str) -> None:
        self.logger.debug("BG %s trend=%s", value, trend)

    def on_bg_error(self, message: str) -> None:
        self.logger.warning("BG monitor: %s", message)

    # ------------------------------------------------------------------ config helpers
    def get_cfg(self) -> Dict[str, Any]:
        return dict(self.cfg)


BasculaAppTk = RpiOptimizedApp
BasculaApp = RpiOptimizedApp

