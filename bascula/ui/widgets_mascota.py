import tkinter as tk
from tkinter import ttk
from bascula.ui.widgets import COL_BG, COL_CARD, COL_ACCENT, COL_TEXT


class MascotaCanvas(tk.Canvas):
    """Mascota IA animada con estética CRT (Basculín).

    Estados: idle | listen | process | wink | recovery | alarm
    Mantiene animaciones existentes y dibuja un robot verde tipo
    wireframe con pequeñas interferencias (scan/glitch) al estilo CRT.
    """
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
        h = self.winfo_height() or 240
        cx, cy = w//2, int(h*0.52)

        # Paleta CRT
        G = '#23f1b2'  # verde neón
        G2 = '#11c896' # borde tenue
        FG = G

        # Factores de escala
        scale = max(0.6, min(1.4, min(w/360.0, h/320.0)))

        def s(v):
            return int(v*scale)

        # Robot: cabeza (rect redondeado simulado con óvalos + líneas)
        head_w, head_h, r = s(180), s(140), s(24)
        hx0, hy0 = cx - head_w//2, cy - head_h//2 - s(20)
        hx1, hy1 = cx + head_w//2, cy + head_h//2 - s(20)
        # Marco cabeza (wireframe doble para pseudo-glow)
        for off, col, wdt in ((0, FG, 3), (2, G2, 1)):
            self.create_arc(hx0, hy0, hx0+2*r, hy0+2*r, start=90, extent=90, style='arc', outline=col, width=wdt)
            self.create_arc(hx1-2*r, hy0, hx1, hy0+2*r, start=0, extent=90, style='arc', outline=col, width=wdt)
            self.create_arc(hx0, hy1-2*r, hx0+2*r, hy1, start=180, extent=90, style='arc', outline=col, width=wdt)
            self.create_arc(hx1-2*r, hy1-2*r, hx1, hy1, start=270, extent=90, style='arc', outline=col, width=wdt)
            self.create_line(hx0+r, hy0, hx1-r, hy0, fill=col, width=wdt)
            self.create_line(hx0+r, hy1, hx1-r, hy1, fill=col, width=wdt)
            self.create_line(hx0, hy0+r, hx0, hy1-r, fill=col, width=wdt)
            self.create_line(hx1, hy0+r, hx1, hy1-r, fill=col, width=wdt)

        # Antenas
        ant_dx, ant_h = s(54), s(26)
        self.create_line(cx-ant_dx, hy0-s(10), cx-ant_dx, hy0-ant_h, fill=FG, width=2)
        self.create_oval(cx-ant_dx-s(6), hy0-ant_h-s(6), cx-ant_dx+s(6), hy0-ant_h+s(6), outline=FG, width=2)
        self.create_line(cx+ant_dx, hy0-s(10), cx+ant_dx, hy0-ant_h, fill=FG, width=2)
        self.create_oval(cx+ant_dx-s(6), hy0-ant_h-s(6), cx+ant_dx+s(6), hy0-ant_h+s(6), outline=FG, width=2)

        # Orejeras laterales
        ew, eh = s(36), s(46)
        self.create_rectangle(hx0-s(14), cy-eh//2-s(20), hx0, cy+eh//2-s(20), outline=FG, width=2)
        self.create_rectangle(hx1, cy-eh//2-s(20), hx1+s(14), cy+eh//2-s(20), outline=FG, width=2)

        # Ojos grandes estilo CRT (con anillos internos)
        ox = s(50); oy = s(8); orad = s(20)
        def draw_eye(ex, ey, wink=False):
            if wink and (self.state == 'wink') and (self._blink_countdown % 10 < 5):
                self.create_line(ex-orad, ey, ex+orad, ey, fill=FG, width=3)
            else:
                self.create_oval(ex-orad, ey-orad, ex+orad, ey+orad, outline=FG, width=2)
                self.create_oval(ex-s(10), ey-s(10), ex+s(10), ey+s(10), outline=G2, width=1)
                self.create_oval(ex-s(4), ey-s(4), ex+s(4), ey+s(4), outline=FG, width=1)
                # pequeño brillo
                self.create_oval(ex-s(3), ey-s(7), ex-s(1), ey-s(5), outline=FG, width=1)
        draw_eye(cx-ox, cy-oy-s(20), wink=True)
        draw_eye(cx+ox, cy-oy-s(20), wink=False)

        # Boca curva
        self.create_arc(cx-s(50), cy-s(6), cx+s(50), cy+s(36), start=200, extent=140, style='arc', outline=FG, width=2)

        # Cuerpo
        bw, bh = s(160), s(120)
        bx0, by0 = cx-bw//2, cy+s(40)
        bx1, by1 = cx+bw//2, cy+s(40)+bh
        self.create_rectangle(bx0, by0, bx1, by1, outline=FG, width=2)
        # Panel pecho con carita
        px0, py0, px1, py1 = cx-s(40), by0+s(22), cx+s(40), by0+s(70)
        self.create_rectangle(px0, py0, px1, py1, outline=FG, width=2)
        self.create_line(px0+s(8), py0+s(22), px1-s(8), py0+s(22), fill=FG)
        self.create_oval(px0+s(12), py0+s(10), px0+s(24), py0+s(22), outline=FG, width=2)
        self.create_oval(px1-s(24), py0+s(10), px1-s(12), py0+s(22), outline=FG, width=2)
        self.create_arc(px0+s(16), py0+s(18), px1-s(16), py1-s(6), start=200, extent=140, style='arc', outline=FG, width=2)

        # Brazos y piernas (segmentos)
        arm_y = by0+s(24)
        self.create_line(bx0, arm_y, bx0-s(28), arm_y+s(28), fill=FG, width=2)
        self.create_line(bx1, arm_y, bx1+s(28), arm_y+s(28), fill=FG, width=2)
        leg_y = by1
        self.create_rectangle(cx-s(60), leg_y, cx-s(36), leg_y+s(34), outline=FG, width=2)
        self.create_rectangle(cx+s(36), leg_y, cx+s(60), leg_y+s(34), outline=FG, width=2)

        # Glitch/scanlines ligeras
        try:
            import random
            if random.random() < 0.25:
                for _ in range(4):
                    y = random.randint(h//6, int(h*0.9))
                    x0 = random.randint(10, w//3)
                    x1 = x0 + random.randint(20, w//2)
                    self.create_line(x0, y, x1, y, fill=G2)
        except Exception:
            pass

        # Texto BASCULÍN
        try:
            self.create_text(cx, by1+s(48), text='BASCULÍN', fill=FG, font=("DejaVu Sans Mono", s(22), 'bold'))
        except Exception:
            pass

        # Indicador de proceso (KITT)
        if self.state == 'process':
            bar_w = int(w*0.6)
            bar_h = s(10)
            x0 = cx - bar_w//2
            y0 = by1 + s(16)
            self.create_rectangle(x0, y0, x0+bar_w, y0+bar_h, outline=G2)
            seg_w = s(22)
            pos = max(0, min(bar_w-seg_w, self._kitt_pos))
            self.create_rectangle(x0+pos, y0, x0+pos+seg_w, y0+bar_h, fill=FG, outline='')

        # Recovery halo pulse (verde)
        if self.state == 'recovery' and self._recovery_active:
            import math
            pulse = 0.5 * (1 + math.sin(self._recovery_phase / 6.0))
            halo_r = int(min(w, h)//2.4 + 8 + 10 * pulse)
            try:
                col = G
                self.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r, outline=col, width=2)
            except Exception:
                pass
        # Alarm halo pulse (rojo)
        if self.state == 'alarm':
            import math
            pulse = 0.5 * (1 + math.sin(self._alarm_phase / 3.0))
            halo_r = int(min(w, h)//2.5 + 8 + 8 * pulse)
            try:
                col = '#ef4444'
                self.create_oval(cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r, outline=col, width=2)
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
