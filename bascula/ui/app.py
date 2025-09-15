from __future__ import annotations

"""Entry point for the redesigned Bascula-Cam UI."""

import tkinter as tk
import time
from bascula.config.theme import apply_theme, get_current_colors
from bascula.ui.widgets import TopBar
from bascula.ui import screens


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

        self.current_screen = None
        self.sound_on = True
        self.timer_job = None
        self.timer_end = 0.0
        self.diabetic_mode = False

        self.show_main()

    # ----- screen management ------------------------------------------
    def _set_screen(self, scr: tk.Frame) -> None:
        if self.current_screen is not None:
            self.current_screen.destroy()
        self.current_screen = scr
        self.current_screen.pack(fill='both', expand=True)

    def show_main(self) -> None:
        self.topbar.set_message('')
        self._set_screen(screens.HomeScreen(self.screen_container, self))

    def show_scale(self) -> None:
        self.topbar.set_message('')
        self._set_screen(screens.ScaleScreen(self.screen_container, self))

    def show_scanner(self) -> None:
        self.topbar.set_message('Acerca un código...')
        self._set_screen(screens.ScannerScreen(self.screen_container, self))

    def show_settings(self) -> None:
        self.topbar.set_message('Ajustes')
        self._set_screen(screens.SettingsScreen(self.screen_container,
                                               self.get_state, self.set_state,
                                               self.change_theme, self.show_main))

    # ----- callbacks from buttons ------------------------------------
    def open_timer_popup(self) -> None:
        screens.TimerPopup(self)

    def open_scanner(self) -> None:
        self.show_scanner()

    def open_settings(self) -> None:
        self.show_settings()

    def quit(self) -> None:  # exposed to button
        self.root.destroy()

    # scale stubs ------------------------------------------------------
    def zero_scale(self) -> None:
        pass

    def tare_scale(self) -> None:
        pass

    def toggle_unit(self) -> None:
        if isinstance(self.current_screen, screens.ScaleScreen):
            self.current_screen._toggle_unit()

    # ----- timer ------------------------------------------------------
    def start_timer(self, seconds: int) -> None:
        self.timer_end = time.time() + seconds
        self._update_timer()

    def _update_timer(self) -> None:
        remaining = int(self.timer_end - time.time())
        if remaining <= 0:
            self.topbar.set_timer('')
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
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
        return {'theme': self.theme_name, 'diabetic_mode': self.diabetic_mode}

    def set_state(self, state: dict) -> None:
        if 'theme' in state:
            self.change_theme(state['theme'])
        if 'diabetic_mode' in state:
            self.set_diabetic_mode(state['diabetic_mode'])


if __name__ == '__main__':
    app = BasculaApp()
    app.root.mainloop()
