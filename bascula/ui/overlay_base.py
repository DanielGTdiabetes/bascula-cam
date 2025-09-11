import tkinter as tk
from bascula.ui.widgets import COL_BG, COL_CARD, COL_BORDER


class OverlayBase(tk.Toplevel):
    """Base overlay no modal con transición alpha y backdrop."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes('-topmost', True)
        except Exception:
            pass
        self.configure(bg=COL_BG)
        self._alpha = 0.0
        self._target_alpha = 0.92
        self._fade_after = None
        self._root = parent.winfo_toplevel()
        # Backdrop container
        self._frame = tk.Frame(self, bg=COL_BG, highlightthickness=0)
        self._frame.pack(fill='both', expand=True)
        self._content = tk.Frame(self._frame, bg=COL_CARD, highlightbackground=COL_BORDER, highlightthickness=1)
        self._content.place(relx=0.5, rely=0.5, anchor='center')
        self.bind('<Escape>', lambda e: self.hide())
        self._place_fullscreen()

    def _place_fullscreen(self):
        try:
            self.update_idletasks()
            x = self._root.winfo_rootx()
            y = self._root.winfo_rooty()
            w = self._root.winfo_width()
            h = self._root.winfo_height()
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def content(self) -> tk.Frame:
        return self._content

    def show(self):
        self._place_fullscreen()
        self.deiconify()
        try:
            self.lift()
        except Exception:
            pass
        self._alpha = 0.0
        self._animate(True)

    def hide(self):
        self._animate(False)

    def _animate(self, showing: bool):
        if self._fade_after:
            try: self.after_cancel(self._fade_after)
            except Exception: pass
        step = 0.08 if showing else -0.1
        def tick():
            try:
                self._alpha += step
                if showing and self._alpha >= self._target_alpha:
                    self._alpha = self._target_alpha
                if (not showing) and self._alpha <= 0.0:
                    self._alpha = 0.0
                try:
                    self.attributes('-alpha', max(0.0, min(1.0, self._alpha)))
                except Exception:
                    pass
                if (showing and self._alpha < self._target_alpha) or ((not showing) and self._alpha > 0.0):
                    self._fade_after = self.after(16, tick)
                else:
                    if not showing:
                        self.withdraw()
            except Exception:
                pass
        tick()

