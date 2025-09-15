from __future__ import annotations

from .widgets import Mascot, COL_ACCENT


class MascotaCanvas(Mascot):
    """Mascota con animaciones simples (shake, wink, bounce)."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._orig_pos = None

    # ---- Animaciones -------------------------------------------------
    def shake(self, dist: int = 10, times: int = 4, delay: int = 50):
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))

        def step(i=0):
            if i >= times * 2:
                self.place(x=x, y=y)
                return
            dx = dist if i % 2 == 0 else -dist
            self.place(x=x + dx, y=y)
            self.after(delay, step, i + 1)

        step()

    def bounce(self, height: int = 20, delay: int = 40):
        info = self.place_info()
        x = int(info.get("x", 0))
        y = int(info.get("y", 0))

        def up(i=0):
            if i >= height:
                down()
                return
            self.place(x=x, y=y - i)
            self.after(delay, up, i + 4)

        def down(i=height):
            if i <= 0:
                self.place(x=x, y=y)
                return
            self.place(x=x, y=y - i)
            self.after(delay, down, i - 4)

        up()

    def wink(self, duration_ms: int = 400):
        old = self.state
        self.state = "wink"
        self._render()
        self.after(duration_ms, lambda: (setattr(self, "state", old), self._render()))

    # Override render to support wink state
    def _render(self):
        super()._render()
        if self.state == "wink":
            w = self.winfo_width() or self.size
            h = self.winfo_height() or self.size
            cx, cy = w // 2, h // 2
            r = min(w, h) // 5
            # cubre ojo derecho y dibuja línea
            self.create_rectangle(cx + r//2 - 8, cy - r, cx + r//2, cy - r + 8,
                                  fill=self["bg"], outline=self["bg"])
            self.create_line(cx + r//2 - 8, cy - r + 4, cx + r//2, cy - r + 4,
                              fill=COL_ACCENT, width=2)


__all__ = ["MascotaCanvas"]
