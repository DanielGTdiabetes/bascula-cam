import tkinter as tk
from tkinter import ttk
from bascula.ui.widgets import COL_BG, COL_CARD, COL_ACCENT, COL_TEXT


class MascotaCanvas(tk.Canvas):
    """Mascota IA animada con estados: idle, listen, process, wink, recovery, alarm."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=kwargs.get('bg', COL_BG), highlightthickness=0)
        self.state = 'idle'  # idle|listen|process|wink
        self._after = None
        self._kitt_pos = 0
        self._kitt_dir = 1
        self._blink_countdown = 50
        # Recovery anim
        self._recovery_active = False
        self._recovery_phase = 0
        # Alarm anim
        self._alarm_active = False
        self._alarm_phase = 0
        self.wakeword = None  # Optional wake word engine
        self.bind('<Configure>', lambda e: self._render())
        self._tick()

    def set_state(self, state: str):
        self.state = state
        self._render()

    def _render(self):
        self.delete('all')
        w = self.winfo_width() or 300
        h = self.winfo_height() or 220
        cx, cy = w//2, h//2

        # Base face
        face_r = min(w, h)//3
        self.create_oval(cx-face_r, cy-face_r, cx+face_r, cy+face_r, fill=COL_CARD, outline=COL_ACCENT, width=2)

        # Eyes
        eye_dx = face_r//2
        eye_ry = max(3, face_r//6)
        if self.state == 'wink' and (self._blink_countdown % 10 < 5):
            # wink one eye
            self.create_line(cx-eye_dx-12, cy-10, cx-eye_dx+12, cy-10, fill=COL_TEXT, width=3)
        else:
            self.create_oval(cx-eye_dx-12, cy-18, cx-eye_dx+12, cy+6, fill=COL_TEXT, outline='')
        self.create_oval(cx+eye_dx-12, cy-18, cx+eye_dx+12, cy+6, fill=COL_TEXT, outline='')

        # Mouth
        self.create_arc(cx-face_r//2, cy, cx+face_r//2, cy+face_r//2, start=200, extent=140,
                        style='arc', outline=COL_ACCENT, width=3)

        # KITT bar for 'process'
        if self.state == 'process':
            bar_w = int(w*0.6)
            bar_h = 10
            x0 = cx - bar_w//2
            y0 = cy + face_r + 12
            self.create_rectangle(x0, y0, x0+bar_w, y0+bar_h, outline=COL_ACCENT)
            seg_w = 20
            pos = max(0, min(bar_w-seg_w, self._kitt_pos))
            self.create_rectangle(x0+pos, y0, x0+pos+seg_w, y0+bar_h, fill=COL_ACCENT, outline='')

        # Recovery halo pulse (green)
        if self.state == 'recovery' and self._recovery_active:
            # 0..1..0 pulse
            import math
            pulse = 0.5 * (1 + math.sin(self._recovery_phase / 6.0))
            halo_r = int(face_r + 8 + 10 * pulse)
            try:
                # Fallback a un verde fijo si no hay alpha
                col = '#22c55e'
                self.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r,
                                 outline=col, width=3)
            except Exception:
                pass
        # Alarm halo pulse (red)
        if self.state == 'alarm':
            import math
            pulse = 0.5 * (1 + math.sin(self._alarm_phase / 3.0))
            halo_r = int(face_r + 8 + 8 * pulse)
            try:
                col = '#ef4444'
                self.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r,
                                 outline=col, width=3)
            except Exception:
                pass

    def _tick(self):
        try:
            # Wake word trigger: if idle and engine signals, switch to listen
            try:
                if self.state == 'idle' and self.wakeword is not None:
                    if getattr(self.wakeword, 'is_triggered', lambda: False)():
                        self.state = 'listen'
            except Exception:
                pass
            # simple blink cadence in idle
            if self.state == 'idle':
                self._blink_countdown -= 1
                if self._blink_countdown <= 0:
                    self.state = 'wink'
                    self._blink_countdown = 50
            elif self.state == 'wink':
                if self._blink_countdown % 7 == 0:
                    self.state = 'idle'

            if self.state == 'process':
                w = self.winfo_width() or 300
                bar_w = int(w*0.6)
                self._kitt_pos += self._kitt_dir * 12
                if self._kitt_pos <= 0:
                    self._kitt_pos = 0; self._kitt_dir = 1
                if self._kitt_pos >= max(0, bar_w-20):
                    self._kitt_pos = max(0, bar_w-20); self._kitt_dir = -1
            if self.state == 'recovery' and self._recovery_active:
                self._recovery_phase += 1
            if self.state == 'alarm':
                self._alarm_phase += 1
            self._render()
        except Exception:
            pass
        self._after = self.after(120, self._tick)

    # ---- Public: recovery animation ----
    def play_recovery_animation(self, duration_ms: int = 2000):
        """Inicia animación de recuperación (halo verde) y vuelve a idle al finalizar."""
        try:
            self.state = 'recovery'
            self._recovery_active = True
            self._recovery_phase = 0
            total = max(500, int(duration_ms))
            self.after(total, self._end_recovery)
        except Exception:
            # Fallback inmediato a idle
            self.state = 'idle'
            self._recovery_active = False

    def _end_recovery(self):
        self._recovery_active = False
        self.state = 'idle'

    # ---- Public: alarm animation (continuous until state changes) ----
    def set_alarm(self):
        self.state = 'alarm'
        self._alarm_active = True
