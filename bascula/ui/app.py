from __future__ import annotations

"""Entry point for the redesigned Bascula-Cam UI."""

import logging
import tkinter as tk
import time
from bascula.config.theme import apply_theme, get_current_colors
from bascula.ui.widgets import TopBar
from bascula.ui.widgets_mascota import MascotaCanvas
from bascula.ui import screens
from bascula.ui.overlay_recipe import RecipeOverlay
from bascula.ui.mascot_messages import MascotMessenger, MSGS
from bascula.services.bg_monitor import BgMonitor
from bascula.services.event_bus import EventBus
from bascula.services.mascot_brain import MascotBrain
from bascula.services.llm_client import LLMClient
from bascula.state import AppState


logger = logging.getLogger(__name__)


class BasculaApp:
    def __init__(self, theme: str = 'modern') -> None:
        self.root = tk.Tk()
        self.root.title('Báscula Cam')
        self.root.configure(bg="#111")
        self.theme_name = theme
        apply_theme(self.root, theme)

        pal = get_current_colors()
        self.topbar = TopBar(self.root, app=self)
        self.topbar.pack(fill='x')

        self.screen_container = tk.Frame(self.root, bg=pal['COL_BG'])

        self._boot_label = tk.Label(
            self.root,
            text="Cargando Báscula…",
            fg="#EEE",
            bg="#111",
            font=("DejaVu Sans", 20),
        )
        self._boot_label.pack(expand=True, fill="both")

        self.mascot_host = tk.Frame(self.screen_container, bg=pal['COL_BG'])
        self.mascot_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.mascot = MascotaCanvas(self.mascot_host, width=300, height=300, with_legs=True)
        self.mascot.place(x=0, y=0)

        self.messenger = MascotMessenger(
            get_mascot_widget=lambda: self.current_mascot_widget(),
            get_topbar=lambda: getattr(self, "topbar", None),
            theme_colors=pal,
        )

        self.event_bus = EventBus()
        # Initialize state-related attributes before accessing configuration
        self.state = AppState()
        self.current_screen = None
        self.current_screen_name = "home"
        self.sound_on = True
        self.timer_job = None
        self.timer_end = 0.0
        self.hypo_timer_job = None
        self.diabetic_mode = False
        self.auto_capture_enabled = True
        self.auto_capture_min_delta_g = 8.0
        self.bg_monitor: BgMonitor | None = None
        self._recipe_overlay: RecipeOverlay | None = None
        self._last_low_alarm_ts = 0.0
        self._last_high_alarm_ts = 0.0
        self._last_nightscout_err_ts = 0.0
        self.last_capture_g = None
        self.bg_value = None
        self.bg_trend = None

        self._diagnostics_overlay: tk.Toplevel | None = None
        try:
            self.root.bind("<Control-d>", self._toggle_diagnostics_overlay)
            self.root.bind("<Control-D>", self._toggle_diagnostics_overlay)
        except Exception:
            pass

        self.llm_client = LLMClient(self.get_cfg().get("llm_api_key"))
        self.mascot_brain = MascotBrain(self, self.event_bus)

        logger.info("Creando pantalla inicial…")
        try:
            self.show_main()
        except Exception as exc:
            logger.exception("Error al crear la pantalla inicial")
            self._display_boot_error(exc)
        else:
            logger.info("Pantalla inicial mostrada")
        self.root.after(20000, self._idle_tick)

    # ----- screen management ------------------------------------------
    def _set_screen(self, scr: tk.Frame) -> None:
        if not self.screen_container.winfo_ismapped():
            try:
                self.screen_container.pack(fill='both', expand=True)
            except Exception:
                pass
        if self.current_screen is not None:
            self.current_screen.destroy()
        self.current_screen = scr
        self.current_screen.pack(fill='both', expand=True)
        self._remove_boot_label()
        self.mascot_host.lift()
        self.current_screen_name = getattr(scr, "name", scr.__class__.__name__)

    def show_main(self) -> None:
        self.topbar.set_message('')
        self._set_screen(screens.HomeScreen(self.screen_container, self))
        x, y = self._center_coords(300)
        self.mascot.animate_to(self.mascot_host, x, y, 300)

    def show_scale(self) -> None:
        self.topbar.set_message('')
        x, y = self._corner_coords()
        self.mascot.animate_to(self.mascot_host, x, y, 140)
        self._set_screen(screens.ScaleScreen(self.screen_container, self))

    def show_scanner(self) -> None:
        self.topbar.set_message('Acerca un código...')
        x, y = self._corner_coords()
        self.mascot.animate_to(self.mascot_host, x, y, 140)
        self._set_screen(screens.ScannerScreen(self.screen_container, self))
        self.event_bus.publish("SCANNER_OPEN")

    def show_settings(self) -> None:
        self.topbar.set_message('Ajustes')
        x, y = self._corner_coords()
        self.mascot.animate_to(self.mascot_host, x, y, 140)
        self._set_screen(screens.SettingsScreen(self.screen_container,
                                               self,
                                               self.get_state, self.set_state,
                                               self.change_theme, self.show_main))

    def _center_coords(self, size: int) -> tuple[int, int]:
        self.root.update_idletasks()
        w = self.screen_container.winfo_width()
        h = self.screen_container.winfo_height()
        return (w - size) // 2, (h - size) // 2

    def _corner_coords(self, size: int = 140) -> tuple[int, int]:
        self.root.update_idletasks()
        w = self.screen_container.winfo_width()
        return w - size - 16, 16

    def current_mascot_widget(self):
        """Return the mascot widget currently in use."""
        if self.current_screen is not None:
            for attr in ("mascot", "mascota"):
                widget = getattr(self.current_screen, attr, None)
                if widget is not None:
                    return widget.as_widget() if hasattr(widget, "as_widget") else widget
        return self.mascot

    # ----- idle ticker -----------------------------------------------
    def _idle_tick(self) -> None:
        try:
            self.event_bus.publish("IDLE_TICK")
        except Exception:
            pass
        try:
            self.root.after(20000, self._idle_tick)
        except Exception:
            pass

    # ----- callbacks from buttons ------------------------------------
    def open_timer_popup(self) -> None:
        screens.TimerPopup(self)

    def open_scanner(self) -> None:
        self.show_scanner()

    def open_settings(self) -> None:
        self.show_settings()

    def open_recipes(self) -> None:
        if self._recipe_overlay is None:
            self._recipe_overlay = RecipeOverlay(self.root, self)
        self._recipe_overlay.show()

    def quit(self) -> None:  # exposed to button
        self.root.destroy()

    # scale stubs ------------------------------------------------------
    def zero_scale(self) -> None:
        if hasattr(self, 'messenger'):
            self.messenger.show(MSGS["zero_applied"](), kind='info', priority=4, icon='ℹ️')
        self.event_bus.publish("TARA")

    def tare_scale(self) -> None:
        if hasattr(self, 'messenger'):
            self.messenger.show(MSGS["tara_applied"](), kind='info', priority=4, icon='ℹ️')
        self.event_bus.publish("TARA")

    def toggle_unit(self) -> None:
        if isinstance(self.current_screen, screens.ScaleScreen):
            self.current_screen._toggle_unit()

    # ----- timer ------------------------------------------------------
    def start_timer(self, seconds: int) -> None:
        self.timer_end = time.time() + seconds
        self.event_bus.publish("TIMER_STARTED", seconds)
        self._update_timer()

    def _update_timer(self) -> None:
        remaining = int(self.timer_end - time.time())
        if remaining <= 0:
            self.topbar.set_timer('')
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
            self.event_bus.publish("TIMER_FINISHED")
            return
        m, s = divmod(remaining, 60)
        self.topbar.set_timer(f"{m:02d}:{s:02d}")
        self.timer_job = self.root.after(1000, self._update_timer)

    # ----- top bar helpers -------------------------------------------
    def toggle_sound(self) -> None:
        self.sound_on = not self.sound_on
        self.topbar.sound_btn.config(text='🔊' if self.sound_on else '🔇')

    # ----- settings helpers -----------------------------------------
    def change_theme(self, name: str) -> None:
        self.theme_name = name
        apply_theme(self.root, name)
        if hasattr(self, 'messenger'):
            self.messenger.pal = get_current_colors()
            self.messenger.scanlines = bool(self.get_cfg().get('theme_scanlines', False))
        self.event_bus.publish("THEME_CHANGED", name)
        try:
            self.root.event_generate('<<ThemeChanged>>', when='tail')
        except Exception:
            pass

    def set_diabetic_mode(self, enabled: bool) -> None:
        self.diabetic_mode = enabled
        if not enabled:
            if self.bg_monitor:
                self.bg_monitor.stop()
                self.bg_monitor = None
            self.topbar.set_bg(None)
        else:
            interval = int(self.get_cfg().get('bg_poll_s', 60))
            self.bg_monitor = BgMonitor(self, interval_s=interval)
            self.bg_monitor.start()
            self.topbar.set_bg('---')
            if hasattr(self, 'messenger'):
                self.messenger.show('Modo diabético activo.', kind='info', priority=4, icon='ℹ️')

    def on_bg_update(self, value_mgdl: int, trend: str) -> None:
        self.topbar.set_bg(str(value_mgdl), trend)
        cfg = self.get_cfg()
        low = int(cfg.get("bg_low_mgdl", 70))
        high = int(cfg.get("bg_high_mgdl", 180))
        self.bg_value = value_mgdl
        self.bg_trend = trend
        self.event_bus.publish("BG_UPDATE", {"bg": value_mgdl, "trend": trend})
        if value_mgdl <= low:
            self.event_bus.publish("BG_HYPO", value_mgdl)
        elif value_mgdl >= low:
            self.event_bus.publish("BG_NORMAL", value_mgdl)
        low_cd = int(cfg.get("bg_low_cooldown_min", 10)) * 60
        high_cd = int(cfg.get("bg_high_cooldown_min", 10)) * 60
        now = time.time()
        if value_mgdl < low:
            if now - self._last_low_alarm_ts >= low_cd:
                if getattr(self, "audio", None):
                    self.audio.play_event("bg_low")
                if hasattr(self, "messenger"):
                    self.messenger.show("Glucosa baja", kind="warning", priority=7, icon="⚠️")
                self._last_low_alarm_ts = now
                self.start_hypo_flow(value_mgdl, trend)
        elif value_mgdl > high:
            if now - self._last_high_alarm_ts >= high_cd:
                if getattr(self, "audio", None):
                    self.audio.play_event("bg_high")
                if hasattr(self, "messenger"):
                    self.messenger.show("Glucosa alta", kind="warning", priority=6, icon="⚠️")
                self._last_high_alarm_ts = now
        else:
            if getattr(self, "audio", None):
                self.audio.play_event("bg_ok")
        st = self.state
        if st.hypo_modal_open and (low <= value_mgdl <= high):
            st.hypo_modal_open = False
            st.hypo_started_ts = None
            if self.hypo_timer_job:
                try:
                    self.root.after_cancel(self.hypo_timer_job)
                except Exception:
                    pass
                self.hypo_timer_job = None
            try:
                self.topbar.set_timer("")
            except Exception:
                pass
            if hasattr(self, "messenger"):
                self.messenger.show("Glucosa normalizada.", kind="success", priority=6, icon="✅")
        if trend == "up":
            if hasattr(self, "messenger"):
                self.messenger.show("Flecha ↑, ojo con subidas.", kind="info", priority=2, icon="↗️")
        elif trend == "down":
            if hasattr(self, "messenger"):
                self.messenger.show("Flecha ↓, prudencia.", kind="info", priority=2, icon="↘️")

    def on_bg_error(self, msg: str):
        now = time.time()
        if now - getattr(self, "_last_nightscout_err_ts", 0.0) >= 300:
            self._last_nightscout_err_ts = now
            try:
                self.messenger.show(msg, kind="info", priority=2, icon="ℹ️")
            except Exception:
                if hasattr(self, "topbar"):
                    self.topbar.set_message(msg)

    def start_hypo_flow(self, bg_value: int, trend: str):
        st = self.state
        if st.hypo_modal_open:
            return
        st.hypo_modal_open = True
        st.hypo_started_ts = time.time()
        st.hypo_cycle = st.hypo_cycle + 1
        if hasattr(self, "messenger"):
            self.messenger.show("Hipoglucemia: toma 15 g de HC rápidos.", kind="warning", priority=8, icon="🍬")
        self._show_hypo_popup()

    def _show_hypo_popup(self):
        try:
            import tkinter as tk
            from bascula.ui.widgets import Card, BigButton, COL_BG, COL_CARD, COL_TEXT, COL_DANGER
            top = tk.Toplevel(self.root)
            top.title("Regla 15/15")
            top.configure(bg=COL_BG)
            card = Card(top)
            card.pack(padx=10, pady=10)
            tk.Label(
                card,
                text=(
                    "Hipoglucemia detectada.\n"
                    "Toma 15 g de HC de acción rápida (glucosa en gel, zumo, azúcar).\n"
                    "Pulsa “He tomado 15 g” y espera 15 minutos. Luego vuelve a medir."
                ),
                bg=COL_CARD,
                fg=COL_TEXT,
                justify="left",
                font=("DejaVu Sans", 16, "bold"),
            ).pack(pady=6)
            btns = tk.Frame(card, bg=COL_CARD)
            btns.pack(pady=6)

            BigButton(
                btns,
                text="He tomado 15 g",
                command=lambda: (top.destroy(), self._start_15_timer()),
            ).pack(side="left", padx=4)

            def _cancel():
                st = self.state
                st.hypo_modal_open = False
                st.hypo_started_ts = None
                if getattr(self, "hypo_timer_job", None):
                    try:
                        self.root.after_cancel(self.hypo_timer_job)
                    except Exception:
                        pass
                    self.hypo_timer_job = None
                try:
                    self.topbar.set_timer("")
                except Exception:
                    pass
                if hasattr(self, "messenger"):
                    self.messenger.show(
                        "Flujo 15/15 cancelado.",
                        kind="info",
                        priority=5,
                        icon="ℹ️",
                    )
                top.destroy()

            BigButton(btns, text="Cancelar", command=_cancel, bg=COL_DANGER).pack(side="left", padx=4)
            try:
                top.lift()
            except Exception:
                pass
        except Exception:
            self.state.clear_hypo_flow()

    def _start_15_timer(self):
        if self.hypo_timer_job:
            try:
                self.root.after_cancel(self.hypo_timer_job)
            except Exception:
                pass
            self.hypo_timer_job = None
        end_ts = time.time() + 15 * 60

        def tick():
            remaining = int(end_ts - time.time())
            if remaining <= 0:
                try:
                    self.topbar.set_timer("")
                except Exception:
                    pass
                if hasattr(self, "messenger"):
                    self.messenger.show("Revisa la glucosa.", kind="info", priority=7, icon="🩸")
                self.hypo_timer_job = None
                return
            m, s = divmod(remaining, 60)
            try:
                self.topbar.set_timer(f"{m:02d}:{s:02d}")
            except Exception:
                pass
            self.hypo_timer_job = self.root.after(1000, tick)

        try:
            self.topbar.set_timer("15:00")
            self.hypo_timer_job = self.root.after(1000, tick)
        except Exception:
            self.hypo_timer_job = self.root.after(
                15 * 60 * 1000,
                lambda: self.messenger.show(
                    "Revisa la glucosa.",
                    kind="info",
                    priority=7,
                    icon="🩸",
                ),
            )

    # ----- state helpers -------------------------------------------
    def get_state(self) -> dict:
        return {
            "theme": self.theme_name,
            "diabetic_mode": self.diabetic_mode,
            "auto_capture_enabled": self.auto_capture_enabled,
            "auto_capture_min_delta_g": self.auto_capture_min_delta_g,
            "timer_active": bool(self.timer_job),
            "last_capture_g": self.last_capture_g,
            "bg_value": self.bg_value,
            "bg_trend": self.bg_trend,
        }

    def set_state(self, state: dict) -> None:
        if 'theme' in state:
            self.change_theme(state['theme'])
        if 'diabetic_mode' in state:
            self.set_diabetic_mode(state['diabetic_mode'])
        if 'auto_capture_enabled' in state:
            self.auto_capture_enabled = bool(state['auto_capture_enabled'])
        if 'auto_capture_min_delta_g' in state:
            try:
                self.auto_capture_min_delta_g = float(state['auto_capture_min_delta_g'])
            except Exception:
                pass

    def get_cfg(self) -> dict:
        return self.get_state()

    def save_cfg(self) -> None:
        pass

    # ----- boot helpers -----------------------------------------------
    def _remove_boot_label(self) -> None:
        lbl = getattr(self, "_boot_label", None)
        if lbl is not None:
            try:
                lbl.destroy()
            except Exception:
                pass
            self._boot_label = None

    def _display_boot_error(self, exc: Exception) -> None:
        message = f"Error al iniciar la pantalla: {exc}"
        lbl = getattr(self, "_boot_label", None)
        if lbl is None:
            self._boot_label = tk.Label(
                self.root,
                text=message,
                fg="#EEE",
                bg="#111",
                font=("DejaVu Sans", 14),
                wraplength=600,
                justify="center",
            )
            self._boot_label.pack(expand=True, fill="both")
        else:
            try:
                lbl.configure(text=message)
            except Exception:
                pass

    def _toggle_diagnostics_overlay(self, event=None):
        try:
            if self._diagnostics_overlay is not None and self._diagnostics_overlay.winfo_exists():
                self._diagnostics_overlay.destroy()
                self._diagnostics_overlay = None
                return "break"
        except Exception:
            self._diagnostics_overlay = None
            return "break"

        overlay = tk.Toplevel(self.root)
        overlay.title("Diagnóstico Báscula")
        overlay.configure(bg="#222")
        try:
            overlay.attributes("-topmost", True)
        except Exception:
            pass
        overlay.geometry("+40+40")
        state = self.get_state()
        info_lines = [
            f"Tema: {self.theme_name}",
            f"Modo diabético: {'activo' if self.diabetic_mode else 'apagado'}",
            f"Autocaptura: {'sí' if state.get('auto_capture_enabled') else 'no'}",
            f"BG: {self.bg_value if self.bg_value is not None else '---'} {self.bg_trend or ''}",
        ]
        tk.Label(
            overlay,
            text="\n".join(info_lines),
            bg="#222",
            fg="#EEE",
            font=("DejaVu Sans", 14),
            justify="left",
        ).pack(padx=20, pady=20)
        overlay.bind("<Escape>", lambda e: overlay.destroy())
        self._diagnostics_overlay = overlay
        return "break"


if __name__ == '__main__':
    app = BasculaApp()
    app.root.mainloop()
