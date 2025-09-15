from __future__ import annotations

"""Entry point for the redesigned Bascula-Cam UI."""

import tkinter as tk
import time
from bascula.config.theme import apply_theme, get_current_colors
from bascula.ui.widgets import TopBar, Mascot
from bascula.ui import screens
from bascula.ui.overlay_recipe import RecipeOverlay
from bascula.ui.mascot_messages import MascotMessenger


class BasculaApp:
    def __init__(self, theme: str = 'modern') -> None:
        self.root = tk.Tk()
        self.root.title('Báscula Cam')
        self.theme_name = theme
        apply_theme(self.root, theme)

        pal = get_current_colors()
        self.topbar = TopBar(self.root, app=self)
        self.topbar.pack(fill='x')

        self.screen_container = tk.Frame(self.root, bg=pal['COL_BG'])
        self.screen_container.pack(fill='both', expand=True)

        self.mascot_host = tk.Frame(self.screen_container, bg=pal['COL_BG'])
        self.mascot_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.mascot = Mascot(self.mascot_host, width=300, height=300, with_legs=True)
        self.mascot.place(x=0, y=0)

        self.messenger = MascotMessenger(
            lambda: self.mascot if self.mascot.winfo_ismapped() else None,
            lambda: self.topbar,
            pal,
        )

        self.current_screen = None
        self.sound_on = True
        self.timer_job = None
        self.timer_end = 0.0
        self.diabetic_mode = False
        self.auto_capture_enabled = True
        self.auto_capture_min_delta_g = 8.0
        self._recipe_overlay: RecipeOverlay | None = None

        self.show_main()

    # ----- screen management ------------------------------------------
    def _set_screen(self, scr: tk.Frame) -> None:
        if self.current_screen is not None:
            self.current_screen.destroy()
        self.current_screen = scr
        self.current_screen.pack(fill='both', expand=True)
        self.mascot_host.lift()

    def show_main(self) -> None:
        self.topbar.set_message('')
        x, y = self._center_coords(300)
        self.mascot.animate_to(self.mascot_host, x, y, 300)
        self._set_screen(screens.HomeScreen(self.screen_container, self))

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
            self.messenger.show('Peso puesto a cero', kind='success', priority=1, icon='🟢')

    def tare_scale(self) -> None:
        if hasattr(self, 'messenger'):
            self.messenger.show('Tara aplicada', kind='success', priority=1, icon='🟢')

    def toggle_unit(self) -> None:
        if isinstance(self.current_screen, screens.ScaleScreen):
            self.current_screen._toggle_unit()

    # ----- timer ------------------------------------------------------
    def start_timer(self, seconds: int) -> None:
        self.timer_end = time.time() + seconds
        if hasattr(self, 'messenger'):
            mins = int(seconds // 60)
            msg = f'Temporizador {mins} min' if mins else f'{seconds}s de cuenta'
            self.messenger.show(msg, kind='info', icon='⏱')
        self._update_timer()

    def _update_timer(self) -> None:
        remaining = int(self.timer_end - time.time())
        if remaining <= 0:
            self.topbar.set_timer('')
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
            if hasattr(self, 'messenger'):
                self.messenger.show('¡Tiempo!', kind='success', priority=1, icon='⏰')
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
        try:
            self.root.event_generate('<<ThemeChanged>>', when='tail')
        except Exception:
            pass

    def set_diabetic_mode(self, enabled: bool) -> None:
        self.diabetic_mode = enabled
        if not enabled:
            self.topbar.set_bg(None)
        else:
            self.topbar.set_bg('---')

    # ----- state helpers -------------------------------------------
    def get_state(self) -> dict:
        return {
            'theme': self.theme_name,
            'diabetic_mode': self.diabetic_mode,
            'auto_capture_enabled': self.auto_capture_enabled,
            'auto_capture_min_delta_g': self.auto_capture_min_delta_g,
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


if __name__ == '__main__':
    app = BasculaApp()
    app.root.mainloop()
