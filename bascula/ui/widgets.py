# -*- coding: utf-8 -*-
import tkinter as tk
import os
import math

# =========================
# Paleta de colores refinada
# =========================
COL_BG = "#0a0e1a"           # Fondo principal - azul muy oscuro
COL_CARD = "#141823"          # Fondo de cartas - azul oscuro
COL_CARD_HOVER = "#1a1f2e"    # Hover en cartas
COL_TEXT = "#f0f4f8"          # Texto principal - blanco suave
COL_MUTED = "#8892a0"         # Texto secundario - gris azulado
COL_ACCENT = "#00d4aa"        # Acento principal - verde agua moderno
COL_ACCENT_DARK = "#00a383"   # Acento oscuro
COL_ACCENT_LIGHT = "#00ffcc"  # Acento claro para hover
COL_SUCCESS = "#00d4aa"       # Éxito - verde agua
COL_WARN = "#ffa500"          # Advertencia - naranja suave
COL_DANGER = "#ff6b6b"        # Peligro - rojo suave
COL_GRADIENT_1 = "#00d4aa"    # Gradiente inicio
COL_GRADIENT_2 = "#00a383"    # Gradiente fin
COL_BORDER = "#2a3142"        # Bordes sutiles
COL_SHADOW = "#050810"        # Sombras

# ======================================================
# Tamaños base pensados para 1024x600 (HDMI 7")
# Usamos tk scaling dinámico para otras resoluciones.
# ======================================================
FS_HUGE = 56
FS_TITLE = 20
FS_CARD_TITLE = 17
FS_TEXT = 15
FS_BTN = 18
FS_BTN_SMALL = 16
FS_ENTRY = 18
FS_ENTRY_SMALL = 16
FS_ENTRY_MICRO = 14
FS_BTN_MICRO = 14

# Margen/padding base (ajustados para evitar “3 cm vacíos”)
PAD_BASE = 10
PAD_CARD_INNER_X = 14
PAD_CARD_INNER_Y = 12

# Flag interno para no re-aplicar scaling
_SCALING_DONE = False

def _calc_scale_from_widget(widget, target=(1024, 600)):
    """Calcula un tk scaling proporcional a un tamaño objetivo."""
    try:
        sw = widget.winfo_screenwidth()
        sh = widget.winfo_screenheight()
        tw, th = target
        if tw <= 0 or th <= 0:
            return 1.0
        scale_w = sw / float(tw)
        scale_h = sh / float(th)
        scale = min(scale_w, scale_h)
        # Limitar a un rango razonable para no deformar exagerado
        return max(0.7, min(scale, 1.6))
    except Exception:
        return 1.0

def auto_apply_scaling(widget, target=(1024, 600), force=False, debug_env_var="BASCULA_DEBUG"):
    """
    Aplica tk scaling UNA SOLA VEZ por proceso, basado en la pantalla real.
    Se invoca desde BaseScreen al construirse.
    """
    global _SCALING_DONE
    if _SCALING_DONE and not force:
        return

    scale = _calc_scale_from_widget(widget, target=target)
    try:
        widget.tk.call('tk', 'scaling', scale)
        _SCALING_DONE = True
    except Exception:
        pass

    # Depuración opcional
    if os.environ.get(debug_env_var, "0") == "1":
        try:
            root = widget.winfo_toplevel()
            root.after(300, lambda: _show_debug_overlay(root, scale))
        except Exception:
            pass

def _show_debug_overlay(root, scale):
    """Overlay sencillo para ver tamaño real y scale aplicado."""
    try:
        w = root.winfo_width()
        h = root.winfo_height()
        if w <= 1 or h <= 1:
            root.update_idletasks()
            w = root.winfo_width()
            h = root.winfo_height()

        overlay = tk.Toplevel(root)
        overlay.wm_overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.85)
        overlay.configure(bg="#000000")
        # Dimensiones mínimas para evitar cubrir toda la UI
        tw, th = min(420, int(w * 0.6)), 130
        overlay.geometry(f"{tw}x{th}+15+15")

        tk.Label(
            overlay,
            text=f"🧪 Layout debug\n"
                 f"Screen: {root.winfo_screenwidth()}x{root.winfo_screenheight()}\n"
                 f"Window: {w}x{h}\n"
                 f"tk scaling: {scale:.2f}",
            bg="#000000", fg="#00ffcc", font=("DejaVu Sans Mono", 12)
        ).pack(fill="both", expand=True, padx=12, pady=12)

        def close_on_click(_e=None):
            try: overlay.destroy()
            except: pass

        overlay.bind("<Button-1>", close_on_click)
    except Exception:
        pass

# ========================
# Widgets visuales
# ========================

class Card(tk.Frame):
    """Contenedor tipo carta con efecto de profundidad y bordes redondeados simulados."""
    def __init__(self, parent, **kwargs):
        # Frame exterior para simular sombra
        self.shadow_frame = tk.Frame(parent, bg=COL_BG, bd=0, highlightthickness=0)

        # Frame principal de la carta
        super().__init__(
            self.shadow_frame, bg=COL_CARD, bd=1,
            highlightbackground=COL_BORDER,
            highlightthickness=1,
            relief="flat", **kwargs
        )
        self.configure(padx=PAD_CARD_INNER_X, pady=PAD_CARD_INNER_Y)

        # Posicionar el frame principal dentro del shadow_frame
        super().pack(padx=2, pady=2, fill="both", expand=True)

        # Efecto hover suave
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(bg=COL_CARD_HOVER)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    # Solo cambiamos si el hijo comparte el mismo bg para evitar “parches”
                    if str(child.cget("bg")) in (COL_CARD, COL_CARD_HOVER):
                        child.configure(bg=COL_CARD_HOVER)
                except tk.TclError:
                    pass

    def _on_leave(self, e):
        self.configure(bg=COL_CARD)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    if str(child.cget("bg")) in (COL_CARD, COL_CARD_HOVER):
                        child.configure(bg=COL_CARD)
                except tk.TclError:
                    pass

    def grid(self, **kwargs):
        # Sobrescribir grid para aplicarlo al shadow_frame
        self.shadow_frame.grid(**kwargs)

    def pack(self, **kwargs):
        # Sobrescribir pack para aplicarlo al shadow_frame
        self.shadow_frame.pack(**kwargs)


class CardTitle(tk.Label):
    def __init__(self, parent, text):
        super().__init__(parent, text=text, bg=COL_CARD, fg=COL_ACCENT,
                         font=("DejaVu Sans", FS_CARD_TITLE, "bold"), anchor="w")
        # Línea decorativa bajo el título
        self.underline = tk.Frame(parent, bg=COL_ACCENT, height=2)


class BigButton(tk.Button):
    """Botón primario con gradiente simulado y animación."""
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=bg, fg=fg,
            activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
            font=("DejaVu Sans Mono", font_size, "bold"),
            bd=0, padx=18, pady=10, relief="flat",
            highlightthickness=0, cursor="hand2"
        )

        # Efecto hover
        self.default_bg = bg
        self.bind("<Enter>", lambda e: self.configure(bg=COL_ACCENT_LIGHT))
        self.bind("<Leave>", lambda e: self.configure(bg=self.default_bg))


class GhostButton(tk.Button):
    """Botón secundario con borde elegante."""
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=COL_CARD, fg=COL_ACCENT,
            activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
            font=("DejaVu Sans", font_size),
            bd=1, padx=14, pady=8, relief="solid",
            highlightbackground=COL_ACCENT, highlightcolor=COL_ACCENT,
            highlightthickness=1, cursor="hand2"
        )

        # Efecto hover
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(bg=COL_CARD_HOVER, fg=COL_ACCENT_LIGHT)

    def _on_leave(self, e):
        self.configure(bg=COL_CARD, fg=COL_ACCENT)


class WeightLabel(tk.Label):
    """Marcador de peso principal con animación de cambio."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="0 g",
            font=("DejaVu Sans Mono", FS_HUGE),
            bg=COL_CARD, fg=COL_TEXT
        )
        self.last_value = "0 g"
        self.animation_after = None

    def config(self, **kwargs):
        if 'text' in kwargs:
            new_text = kwargs['text']
            if new_text != self.last_value:
                # Efecto de cambio suave
                self.configure(fg=COL_ACCENT_LIGHT)
                if self.animation_after:
                    self.after_cancel(self.animation_after)
                self.animation_after = self.after(200, lambda: self.configure(fg=COL_TEXT))
                self.last_value = new_text
        super().config(**kwargs)


class Toast(tk.Frame):
    """Mensaje temporal con animación de entrada."""
    def __init__(self, parent):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=1,
                         highlightbackground=COL_BORDER)
        self._lbl = tk.Label(self, text="", bg=COL_CARD, fg=COL_TEXT,
                             font=("DejaVu Sans", FS_TEXT), padx=16, pady=10)
        self._lbl.pack()
        self._after_id = None
        self.place_forget()

        # Icono decorativo
        self._icon = tk.Label(self, text="✓", bg=COL_CARD, fg=COL_SUCCESS,
                              font=("DejaVu Sans", 18), padx=10)

    def show(self, text: str, ms: int = 1500, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        # Configurar color e icono
        display_color = color or COL_SUCCESS
        self._lbl.config(text=text, fg=display_color)

        # Seleccionar icono según el color
        if color == COL_SUCCESS:
            self._icon.config(text="✓", fg=COL_SUCCESS)
        elif color == COL_WARN:
            self._icon.config(text="⚠", fg=COL_WARN)
        elif color == COL_DANGER:
            self._icon.config(text="✕", fg=COL_DANGER)
        else:
            self._icon.config(text="ℹ", fg=COL_ACCENT)

        self._icon.pack(side="left", before=self._lbl)

        # Asegurar medidas actualizadas
        try:
            self.master.update_idletasks()
        except Exception:
            pass
        w = max(20, self.master.winfo_width())

        # Posicionar
        self.place(x=w - PAD_BASE, y=PAD_BASE, anchor="ne")

        # Traer al frente
        self.lift()

        self._after_id = self.after(ms, self.hide)

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._icon.pack_forget()
        self.place_forget()


class NumericKeypad(tk.Frame):
    """Teclado numérico elegante con efecto de presión."""
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None,
                 allow_dot=True, variant="ultracompact"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot
        self.variant = variant

        # Tamaños según variante
        if variant == "ultracompact":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_MICRO)
            f_btn = ("DejaVu Sans", FS_BTN_MICRO, "bold")
            pad_x = 3; pad_y = 3
        elif variant == "compact":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_SMALL)
            f_btn = ("DejaVu Sans", FS_BTN_SMALL, "bold")
            pad_x = 4; pad_y = 4
        else:
            f_entry = ("DejaVu Sans Mono", FS_ENTRY)
            f_btn = ("DejaVu Sans", FS_BTN, "bold")
            pad_x = 5; pad_y = 5

        # Display con estilo moderno
        self.entry = tk.Entry(self, textvariable=self.var, justify="right",
                              bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT,
                              font=f_entry, relief="flat", bd=8,
                              highlightbackground=COL_BORDER, highlightthickness=1)
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, pad_y+3))

        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_columnconfigure(2, weight=1, uniform="cols")

        def mkbtn(txt, r, c, cmd=None, span=1, special=False):
            bg_color = COL_ACCENT if special else "#1a1f2e"
            fg_color = COL_TEXT
            hover_bg = COL_ACCENT_LIGHT if special else "#2a3142"

            b = tk.Button(self, text=txt, command=cmd or (lambda t=txt: self._press(t)),
                          bg=bg_color, fg=fg_color,
                          activebackground=hover_bg, activeforeground=COL_TEXT,
                          font=f_btn, bd=0, relief="flat")
            b.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=pad_x, pady=pad_y)

            # Efecto hover
            b.bind("<Enter>", lambda e: b.configure(bg=hover_bg))
            b.bind("<Leave>", lambda e: b.configure(bg=bg_color))

            return b

        # Teclado numérico con diseño moderno
        mkbtn("7", 1, 0); mkbtn("8", 1, 1); mkbtn("9", 1, 2)
        mkbtn("4", 2, 0); mkbtn("5", 2, 1); mkbtn("6", 2, 2)
        mkbtn("1", 3, 0); mkbtn("2", 3, 1); mkbtn("3", 3, 2)
        mkbtn("0", 4, 0, span=2)

        if self.allow_dot:
            mkbtn(".", 4, 2, cmd=self._press_dot)
        else:
            mkbtn("", 4, 2)  # Espacio vacío

        # Botones de acción con colores especiales
        mkbtn("⌫", 5, 0, cmd=self._backspace, special=False)
        mkbtn("C", 5, 1, cmd=self._clear, special=False)
        mkbtn("✓", 5, 2, cmd=self._ok, special=True)

        # Configurar filas
        for r in range(1, 6):
            self.grid_rowconfigure(r, weight=1, uniform="rows")
        self.grid_rowconfigure(0, weight=0)

    def _press(self, t):
        current = self.var.get()
        # Limitar longitud para evitar desbordamiento visual
        if len(current) < 12:
            self.var.set(current + str(t))

    def _press_dot(self):
        if not self.allow_dot:
            return
        s = self.var.get()
        if '.' not in s and ',' not in s:
            self.var.set(s + ".")

    def _backspace(self):
        s = self.var.get()
        if s:
            self.var.set(s[:-1])

    def _clear(self):
        self.var.set("")
        if self.on_clear:
            self.on_clear()

    def _ok(self):
        if self.on_ok:
            self.on_ok()


class StatusIndicator(tk.Canvas):
    """Indicador de estado con animación de pulso."""
    def __init__(self, parent, size=12):
        # Fondo igual al del padre para que no “corte” en hover
        bg = parent.cget("bg") if hasattr(parent, "cget") else COL_CARD
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.size = size
        self.status = "inactive"
        self.pulse_after = None
        self._draw_indicator()

    def _draw_indicator(self):
        self.delete("all")
        center = self.size // 2
        radius = (self.size // 2) - 2

        colors = {
            "active": COL_SUCCESS,
            "warning": COL_WARN,
            "error": COL_DANGER,
            "inactive": COL_MUTED
        }

        color = colors.get(self.status, COL_MUTED)

        # Círculo principal
        self.create_oval(center - radius, center - radius,
                         center + radius, center + radius,
                         fill=color, outline="", tags="indicator")

        # Efecto de brillo
        if self.status == "active":
            self.create_oval(center - radius + 2, center - radius + 2,
                             center - radius + 4, center - radius + 4,
                             fill=COL_ACCENT_LIGHT, outline="")

    def set_status(self, status):
        self.status = status
        self._draw_indicator()

        # Animación de pulso para estado activo
        if status == "active" and not self.pulse_after:
            self._pulse()

    def _pulse(self):
        if self.status != "active":
            self.pulse_after = None
            return

        # Efecto de pulso (expandir y contraer)
        self.itemconfig("indicator", fill=COL_ACCENT_LIGHT)
        self.after(200, lambda: self.itemconfig("indicator", fill=COL_SUCCESS))
        self.pulse_after = self.after(1000, self._pulse)


# =========================
# Contenedor scroll vertical
# =========================
class ScrollFrame(tk.Frame):
    """
    Frame desplazable verticalmente:
      contenedor = ScrollFrame(parent)
      body = contenedor.body   # aquí añades tus widgets
    """
    def __init__(self, parent, bg=COL_BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.body = tk.Frame(self.canvas, bg=bg)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")

        # Eventos para recalcular scroll region
        self.body.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Scroll con rueda/táctil
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_frame_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Hacer que el frame ocupe todo el ancho disponible
        canvas_width = event.width
        self.canvas.itemconfig(self.body_id, width=canvas_width)

    def _on_mousewheel(self, event):
        delta = 0
        if hasattr(event, "delta") and event.delta:
            delta = -1 * int(event.delta / 120)
        elif hasattr(event, "num"):
            # Linux
            if event.num == 4: delta = -1
            elif event.num == 5: delta = 1
        if delta != 0:
            self.canvas.yview_scroll(delta, "units")
