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
        frame_delay = kwargs.pop('frame_delay_ms', 120)
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
        try:
            delay = int(frame_delay)
        except Exception:
            delay = 120
        self._frame_delay_ms = max(33, delay)
        self._running = False
        self.bind('<Configure>', lambda e: self._render())
        self.start_animation()

    def start_animation(self):
        if self._running:
            return
        self._running = True
        self._render()
        self._schedule_tick(immediate=True)

    def stop_animation(self):
        self._running = False
        if self._after is not None:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def destroy(self):
        self.stop_animation()
        super().destroy()

    def _schedule_tick(self, *, immediate: bool = False):
        if not self._running:
            return
        delay = 0 if immediate else self._frame_delay_ms
        self._after = self.after(delay, self._tick)

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
        self._after = None
        if not self._running:
            return
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
        finally:
            self._schedule_tick()


class MiniMascotaAvatar(tk.Canvas):
    """Compact 50×50 mascot used as an optional corner assistant."""

    def __init__(self, parent, size: int = 50, **kwargs):
        bg = kwargs.get('bg', COL_BG)
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self._size = size
        self._blink_job = None
        self._talk_job = None
        self._blink_state = False
        self._talk_state = False
        self._build_face()
        self._schedule_blink()

    # ------------------------------------------------------------------
    def _build_face(self):
        self.delete('all')
        s = self._size
        pad = max(3, s // 10)
        face_color = COL_ACCENT
        detail = 'white'

        self._face = self.create_oval(pad, pad, s - pad, s - pad, fill=face_color, outline='')

        eye_w = max(4, s // 6)
        eye_h = max(4, s // 5)
        eye_y = pad + eye_h
        gap = eye_w // 2
        center = s // 2

        self._eye_left = self.create_oval(center - gap - eye_w, eye_y, center - gap,
                                          eye_y + eye_h, fill=detail, outline='')
        self._eye_right = self.create_oval(center + gap, eye_y, center + gap + eye_w,
                                           eye_y + eye_h, fill=detail, outline='')
        self._eye_left_closed = self.create_line(center - gap - eye_w, eye_y + eye_h // 2,
                                                 center - gap, eye_y + eye_h // 2,
                                                 fill=detail, width=2, state='hidden')
        self._eye_right_closed = self.create_line(center + gap, eye_y + eye_h // 2,
                                                  center + gap + eye_w, eye_y + eye_h // 2,
                                                  fill=detail, width=2, state='hidden')

        mouth_top = s - pad - eye_h
        self._mouth_closed = self.create_arc(pad + eye_w // 2, mouth_top - eye_h,
                                             s - pad - eye_w // 2, mouth_top + eye_h,
                                             start=200, extent=140, outline=detail,
                                             style='arc', width=2)
        self._mouth_open = self.create_oval(center - eye_w, mouth_top - eye_h // 2,
                                            center + eye_w, mouth_top + eye_h // 2,
                                            outline=detail, fill=detail, state='hidden')

    # ------------------------------------------------------------------
    def destroy(self):
        self._cancel_jobs()
        super().destroy()

    # ------------------------------------------------------------------
    def _cancel_jobs(self):
        for job in (self._blink_job, self._talk_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._blink_job = None
        self._talk_job = None

    # ------------------------------------------------------------------
    def _schedule_blink(self):
        self._blink_job = self.after(2600, self._blink)

    def _blink(self):
        self._set_blink(True)
        self.after(160, lambda: self._set_blink(False))
        self._schedule_blink()

    def _set_blink(self, value: bool):
        self._blink_state = value
        state_open = 'hidden' if value else 'normal'
        state_closed = 'normal' if value else 'hidden'
        self.itemconfigure(self._eye_left, state=state_open)
        self.itemconfigure(self._eye_right, state=state_open)
        self.itemconfigure(self._eye_left_closed, state=state_closed)
        self.itemconfigure(self._eye_right_closed, state=state_closed)

    # ------------------------------------------------------------------
    def speak(self, duration_ms: int = 1200):
        """Trigger a small mouth animation."""

        self._talk_cycles = max(2, duration_ms // 120)
        if self._talk_job is not None:
            try:
                self.after_cancel(self._talk_job)
            except Exception:
                pass
        self._talk_state = False
        self._animate_talk()

    def _animate_talk(self):
        if self._talk_cycles <= 0:
            self.itemconfigure(self._mouth_open, state='hidden')
            self.itemconfigure(self._mouth_closed, state='normal')
            self._talk_job = None
            return

        self._talk_state = not self._talk_state
        if self._talk_state:
            self.itemconfigure(self._mouth_closed, state='hidden')
            self.itemconfigure(self._mouth_open, state='normal')
        else:
            self.itemconfigure(self._mouth_closed, state='normal')
            self.itemconfigure(self._mouth_open, state='hidden')

        self._talk_cycles -= 1
        self._talk_job = self.after(120, self._animate_talk)

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
