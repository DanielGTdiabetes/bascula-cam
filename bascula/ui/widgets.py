# -*- coding: utf-8 -*-
# bascula/ui/widgets.py - VERSIÓN CORREGIDA
import tkinter as tk
import math

# Paleta de colores refinada - Tema oscuro con acentos verdes suaves
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

# TAMAÑOS BASE PARA ESCALADO AUTOMÁTICO - CORREGIDOS
FS_HUGE = 48           # Peso principal
FS_TITLE = 18          # Títulos principales
FS_CARD_TITLE = 15     # Títulos de cartas
FS_TEXT = 13           # Texto normal
FS_BTN = 16            # Botones
FS_BTN_SMALL = 14      
FS_ENTRY = 16          
FS_ENTRY_SMALL = 14    
FS_ENTRY_MICRO = 12    
FS_BTN_MICRO = 12      

# Variable global para el factor de escala calculado - INICIALIZADA
SCALE_FACTOR = 1.0
_SCALING_APPLIED = False  # Para evitar aplicar escalado múltiples veces

def auto_apply_scaling(widget, target=(1024, 600)):
    """
    Aplica escalado automático basado en la resolución real de pantalla.
    VERSIÓN CORREGIDA que evita aplicación múltiple y maneja errores.
    """
    global SCALE_FACTOR, _SCALING_APPLIED
    global FS_HUGE, FS_TITLE, FS_CARD_TITLE, FS_TEXT, FS_BTN
    global FS_BTN_SMALL, FS_ENTRY, FS_ENTRY_SMALL, FS_ENTRY_MICRO, FS_BTN_MICRO
    
    # Evitar aplicar escalado múltiples veces
    if _SCALING_APPLIED:
        print(f"[SCALING] Ya aplicado previamente, factor actual: {SCALE_FACTOR:.2f}")
        return
    
    try:
        root = widget.winfo_toplevel()
        root.update_idletasks()
        
        # Obtener dimensiones reales de pantalla
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        
        print(f"[SCALING] Pantalla detectada: {screen_w}x{screen_h}")
        
        # Calcular factor de escala más conservador
        target_w, target_h = target
        scale_w = screen_w / target_w
        scale_h = screen_h / target_h
        
        # Usar el menor factor pero con límites más estrictos
        raw_scale = min(scale_w, scale_h)
        
        # Aplicar límites para evitar escalados extremos
        if raw_scale > 1.5:
            SCALE_FACTOR = 1.5  # máximo 150%
        elif raw_scale < 0.8:
            SCALE_FACTOR = 0.8  # mínimo 80%
        else:
            SCALE_FACTOR = raw_scale
        
        print(f"[SCALING] Factor aplicado: {SCALE_FACTOR:.2f} (calculado: {raw_scale:.2f})")
        
        # Aplicar scaling solo si es significativamente diferente de 1.0
        if abs(SCALE_FACTOR - 1.0) > 0.1:
            # Aplicar factor de manera más conservadora
            FS_HUGE = max(32, int(48 * SCALE_FACTOR))
            FS_TITLE = max(14, int(18 * SCALE_FACTOR))
            FS_CARD_TITLE = max(12, int(15 * SCALE_FACTOR))
            FS_TEXT = max(10, int(13 * SCALE_FACTOR))
            FS_BTN = max(12, int(16 * SCALE_FACTOR))
            FS_BTN_SMALL = max(10, int(14 * SCALE_FACTOR))
            FS_ENTRY = max(12, int(16 * SCALE_FACTOR))
            FS_ENTRY_SMALL = max(10, int(14 * SCALE_FACTOR))
            FS_ENTRY_MICRO = max(8, int(12 * SCALE_FACTOR))
            FS_BTN_MICRO = max(8, int(12 * SCALE_FACTOR))
            
            print(f"[SCALING] Tamaños ajustados - HUGE: {FS_HUGE}, TITLE: {FS_TITLE}, TEXT: {FS_TEXT}")
        else:
            print("[SCALING] Sin cambios necesarios")
        
        # Marcar como aplicado
        _SCALING_APPLIED = True
            
    except Exception as e:
        print(f"[SCALING] Error aplicando escalado: {e}")
        SCALE_FACTOR = 1.0

def get_scaled_size(base_size):
    """Función auxiliar para obtener tamaños escalados dinámicamente."""
    # Usar el factor global, con fallback seguro
    global SCALE_FACTOR
    try:
        return max(8, int(base_size * SCALE_FACTOR))
    except (NameError, TypeError):
        # Fallback si SCALE_FACTOR no está definido
        return max(8, int(base_size * 1.0))

class Card(tk.Frame):
    """Contenedor tipo carta con sombra - VERSIÓN COMPLETA."""
    def __init__(self, parent, min_width=None, min_height=None, **kwargs):
        # Frame exterior (sombra)
        self.shadow_frame = tk.Frame(parent, bg=COL_BG, bd=0, highlightthickness=0)
        
        # Configurar tamaños mínimos si se especifican
        if min_width:
            self.shadow_frame.configure(width=get_scaled_size(min_width))
        if min_height:
            self.shadow_frame.configure(height=get_scaled_size(min_height))
        
        # Inicializa el Frame real dentro de la sombra
        super().__init__(self.shadow_frame, bg=COL_CARD,
                         bd=1, highlightbackground=COL_BORDER,
                         highlightthickness=1, relief="flat", **kwargs)
        
        # Padding escalado
        scaled_padding = get_scaled_size(16)
        self.configure(padx=scaled_padding, pady=get_scaled_size(14))
        
        # Coloca el frame real dentro de la sombra
        super().pack(padx=2, pady=2, fill="both", expand=True)

        # Efecto hover
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    # ---- Reenvío de gestores de geometría al shadow_frame ----
    def pack(self, *args, **kwargs):
        return self.shadow_frame.pack(*args, **kwargs)

    def grid(self, *args, **kwargs):
        return self.shadow_frame.grid(*args, **kwargs)

    def place(self, *args, **kwargs):
        return self.shadow_frame.place(*args, **kwargs)

    def pack_forget(self):
        return self.shadow_frame.pack_forget()

    def grid_forget(self):
        return self.shadow_frame.grid_forget()

    def place_forget(self):
        return self.shadow_frame.place_forget()

    def destroy(self):
        try:
            super().destroy()
        finally:
            if hasattr(self, 'shadow_frame') and self.shadow_frame.winfo_exists():
                self.shadow_frame.destroy()

    def _on_enter(self, e):
        self.configure(bg=COL_CARD_HOVER)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    child.configure(bg=COL_CARD_HOVER)
                except tk.TclError:
                    pass

    def _on_leave(self, e):
        self.configure(bg=COL_CARD)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    child.configure(bg=COL_CARD)
                except tk.TclError:
                    pass

class NumericKeypad(tk.Frame):
    """Teclado numérico CORREGIDO - garantiza que se muestren todos los botones."""
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None,
                 allow_dot=True, variant="ultracompact"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot
        self.variant = variant

        # Configurar tamaños según variante y escalado
        if variant == "ultracompact":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_MICRO)
            f_btn = ("DejaVu Sans Mono", FS_BTN_MICRO, "bold")
            pad = (4, 4)
            ipady = 4
        elif variant == "small":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_SMALL)
            f_btn = ("DejaVu Sans Mono", FS_BTN_SMALL, "bold")
            pad = (6, 6)
            ipady = 6
        else:
            f_entry = ("DejaVu Sans Mono", FS_ENTRY)
            f_btn = ("DejaVu Sans Mono", FS_BTN, "bold")
            pad = (8, 8)
            ipady = 8

        # Entry en la fila 0
        entry = tk.Entry(self, textvariable=self.var, font=f_entry,
                         bg=COL_CARD, fg=COL_TEXT,
                         highlightbackground=COL_BORDER, highlightthickness=1,
                         insertbackground=COL_ACCENT, relief="flat", justify="right")
        entry.grid(row=0, column=0, columnspan=3, sticky="ew", 
                  padx=pad, pady=(pad[1], pad[1]//2))

        # Configurar columnas con peso uniforme
        for i in range(3):
            self.columnconfigure(i, weight=1, uniform="keys")

        # Botones numéricos 7-9, 4-6, 1-3 - CORREGIDO
        buttons_layout = [
            [("7", 1, 0), ("8", 1, 1), ("9", 1, 2)],
            [("4", 2, 0), ("5", 2, 1), ("6", 2, 2)],
            [("1", 3, 0), ("2", 3, 1), ("3", 3, 2)],
        ]

        for row_buttons in buttons_layout:
            for txt, row, col in row_buttons:
                btn = tk.Button(self, text=txt, command=lambda t=txt: self._add(t),
                              font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                              activebackground=COL_CARD_HOVER, 
                              activeforeground=COL_ACCENT_LIGHT,
                              bd=1, highlightthickness=0, relief="flat")
                btn.grid(row=row, column=col, sticky="nsew", 
                        padx=pad, pady=pad, ipady=ipady)
                # Configurar peso de fila
                self.rowconfigure(row, weight=1)

        # Fila inferior: 0, punto (opcional), OK
        bottom_row = 4
        
        # Botón 0
        zero_btn = tk.Button(self, text="0", command=lambda: self._add("0"),
                             font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                             activebackground=COL_CARD_HOVER, 
                             activeforeground=COL_ACCENT_LIGHT,
                             bd=1, highlightthickness=0, relief="flat")
        
        if self.allow_dot:
            # Con punto: 0 ocupa 1 columna, punto 1 columna, OK 1 columna
            zero_btn.grid(row=bottom_row, column=0, sticky="nsew", 
                         padx=pad, pady=pad, ipady=ipady)
            
            dot_btn = tk.Button(self, text=".", command=lambda: self._add("."),
                                font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                                activebackground=COL_CARD_HOVER, 
                                activeforeground=COL_ACCENT_LIGHT,
                                bd=1, highlightthickness=0, relief="flat")
            dot_btn.grid(row=bottom_row, column=1, sticky="nsew", 
                        padx=pad, pady=pad, ipady=ipady)
            
            ok_btn = tk.Button(self, text="OK", command=self._ok,
                               font=f_btn, bg=COL_ACCENT, fg=COL_TEXT,
                               activebackground=COL_ACCENT_LIGHT, 
                               activeforeground=COL_TEXT,
                               bd=0, highlightthickness=0, relief="flat")
            ok_btn.grid(row=bottom_row, column=2, sticky="nsew", 
                       padx=pad, pady=pad, ipady=ipady)
        else:
            # Sin punto: 0 ocupa 2 columnas, OK 1 columna
            zero_btn.grid(row=bottom_row, column=0, columnspan=2, sticky="nsew", 
                         padx=pad, pady=pad, ipady=ipady)
            
            ok_btn = tk.Button(self, text="OK", command=self._ok,
                               font=f_btn, bg=COL_ACCENT, fg=COL_TEXT,
                               activebackground=COL_ACCENT_LIGHT, 
                               activeforeground=COL_TEXT,
                               bd=0, highlightthickness=0, relief="flat")
            ok_btn.grid(row=bottom_row, column=2, sticky="nsew", 
                       padx=pad, pady=pad, ipady=ipady)

        self.rowconfigure(bottom_row, weight=1)

        # Fila de botones especiales - LAYOUT CORREGIDO
        special_row = 5
        
        # Configurar esta fila también
        self.rowconfigure(special_row, weight=1)
        
        # Botón BACKSPACE (borrar último carácter) - Columna 0
        back_btn = tk.Button(self, text="⌫", command=self._back,
                             font=f_btn, bg=COL_CARD, fg=COL_WARN,
                             activebackground=COL_CARD_HOVER, 
                             activeforeground=COL_ACCENT_LIGHT,
                             bd=1, highlightthickness=0, relief="flat")
        back_btn.grid(row=special_row, column=0, sticky="nsew", 
                     padx=pad, pady=pad, ipady=ipady)
        
        # Botón CLR (limpiar todo) - Columnas 1-2
        clear_btn = tk.Button(self, text="CLR", command=self._clear,
                              font=f_btn, bg=COL_CARD, fg=COL_WARN,
                              activebackground=COL_CARD_HOVER, 
                              activeforeground=COL_ACCENT_LIGHT,
                              bd=1, highlightthickness=0, relief="flat")
        clear_btn.grid(row=special_row, column=1, columnspan=2, sticky="nsew", 
                      padx=pad, pady=pad, ipady=ipady)

    def _add(self, ch: str):
        s = self.var.get() or ""
        self.var.set(s + ch)

    def _back(self):
        s = self.var.get() or ""
        if s:
            self.var.set(s[:-1])

    def _clear(self):
        self.var.set("")
        if self.on_clear:
            self.on_clear()

    def _ok(self):
        if self.on_ok:
            self.on_ok()

# [Resto de clases sin cambios...]
class CardTitle(tk.Frame):
    """Título de carta con subrayado acento."""
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.lbl = tk.Label(self, text=text, bg=COL_CARD, fg=COL_ACCENT,
                            font=("DejaVu Sans", FS_CARD_TITLE, "bold"), anchor="w")
        self.lbl.pack(side="top", anchor="w")

class BigButton(tk.Button):
    """Botón primario con gradiente simulado y animación."""
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        padding_x = get_scaled_size(20 if not micro else 16)
        padding_y = get_scaled_size(10 if not micro else 8)
        
        self.configure(
            bg=bg, fg=fg, 
            activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
            font=("DejaVu Sans Mono", font_size, "bold"),
            bd=0, padx=padding_x, pady=padding_y, relief="flat",
            highlightthickness=0, cursor="hand2"
        )
        self.default_bg = bg
        self.bind("<Enter>", lambda e: self.configure(bg=COL_ACCENT_LIGHT))
        self.bind("<Leave>", lambda e: self.configure(bg=self.default_bg))

class GhostButton(tk.Button):
    """Botón secundario con borde elegante."""
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        padding_x = get_scaled_size(16 if not micro else 12)
        padding_y = get_scaled_size(8 if not micro else 6)
        
        self.configure(
            bg=COL_CARD, fg=COL_ACCENT,
            activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
            font=("DejaVu Sans Mono", font_size, "bold"),
            bd=1, relief="solid", highlightthickness=0,
            highlightbackground=COL_ACCENT, cursor="hand2",
            padx=padding_x, pady=padding_y
        )

class WeightLabel(tk.Label):
    """Marcador de peso principal con animación de cambio."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="0 g",
            font=("DejaVu Sans Mono", FS_HUGE, "bold"),
            bg=COL_CARD, fg=COL_TEXT,
            anchor="center"
        )
        self.last_value = "0 g"
        self.animation_after = None
    
    def config(self, **kwargs):
        if 'text' in kwargs:
            new_text = kwargs['text']
            if new_text != self.last_value:
                self.configure(fg=COL_ACCENT_LIGHT)
                if self.animation_after:
                    self.after_cancel(self.animation_after)
                self.animation_after = self.after(200, lambda: self.configure(fg=COL_TEXT))
                self.last_value = new_text
        super().config(**kwargs)

class Toast(tk.Frame):
    """Mensaje temporal con animación de entrada - VERSIÓN COMPLETA."""
    def __init__(self, parent):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=1,
                        highlightbackground=COL_BORDER)
        padding = get_scaled_size(20)
        self._lbl = tk.Label(self, text="", bg=COL_CARD, fg=COL_TEXT,
                             font=("DejaVu Sans", FS_TEXT), 
                             padx=padding, pady=get_scaled_size(12))
        self._lbl.pack()
        self._after_id = None
        self.place_forget()
        self._icon = tk.Label(self, text="✓", bg=COL_CARD, fg=COL_SUCCESS,
                             font=("DejaVu Sans", 18), padx=get_scaled_size(10))
        
        # Configuración adicional para mejor visualización
        self.configure(relief="raised", bd=1)

    def show(self, text: str, ms: int = 1500, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        
        if color:
            self._lbl.configure(fg=color)
            self._icon.configure(fg=color)
        else:
            self._lbl.configure(fg=COL_TEXT)
            self._icon.configure(fg=COL_SUCCESS)
        
        self._icon.pack(side="left")
        self._lbl.configure(text=text)
        
        # Mejor posicionamiento que se adapte al tamaño de la ventana
        self.update_idletasks()
        parent_width = self.master.winfo_width()
        if parent_width > 100:  # Evitar errores si la ventana aún no se ha dibujado
            self.place(x=max(20, parent_width - 20), y=20, anchor="ne")
        else:
            self.place(x=300, y=20, anchor="ne")
        self.lift()
        self._after_id = self.after(ms, self.hide)

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._icon.pack_forget()
        self.place_forget()

class ScrollFrame(tk.Frame):
    """Frame con scroll vertical para contenido largo - VERSIÓN COMPLETA."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Canvas y scrollbar
        self.canvas = tk.Canvas(self, bg=kwargs.get('bg', COL_BG), highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                width=get_scaled_size(16))
        self.scrollable_frame = tk.Frame(self.canvas, bg=kwargs.get('bg', COL_BG))
        
        # Configurar scroll
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Bind para redimensionar el frame interno con el canvas
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Layout
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Acceso directo al frame de contenido
        self.body = self.scrollable_frame
        
        # Bind mousewheel - Compatible con diferentes sistemas
        self._bind_mousewheel()
        
    def _on_canvas_configure(self, event):
        """Ajustar el ancho del frame interno al ancho del canvas."""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
    def _bind_mousewheel(self):
        """Bind scroll wheel events for different systems."""
        # Linux
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        # Windows/MacOS
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        
        # También bind en el frame padre para capturar eventos
        self.bind("<Button-4>", self._on_mousewheel)
        self.bind("<Button-5>", self._on_mousewheel)
        self.bind("<MouseWheel>", self._on_mousewheel)
        
    def _on_mousewheel(self, event):
        """Manejo del scroll con la rueda del ratón."""
        try:
            # Para Linux - eventos Button-4 y Button-5
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            # Para otros sistemas - usar delta si está disponible
            elif hasattr(event, 'delta') and event.delta:
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass

class StatusIndicator(tk.Canvas):
    """Indicador de estado con animación de pulso."""
    def __init__(self, parent, size=12):
        scaled_size = get_scaled_size(size)
        super().__init__(parent, width=scaled_size, height=scaled_size, 
                        bg=COL_CARD, highlightthickness=0)
        self.size = scaled_size
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
            "inactive": COL_MUTED
        }
        color = colors.get(self.status, COL_MUTED)
        
        self.create_oval(1, 1, self.size-1, self.size-1, outline=COL_BORDER, width=1, tags="border")
        self.create_oval(center-radius, center-radius, center+radius, center+radius,
                         fill=color, outline=color, tags="indicator")
    
    def set_status(self, status: str):
        self.status = status
        if self.pulse_after:
            self.after_cancel(self.pulse_after)
            self.pulse_after = None
        self._draw_indicator()
        if status == "active" and not self.pulse_after:
            self._pulse()
    
    def _pulse(self):
        if self.status != "active":
            self.pulse_after = None
            return
        self.itemconfig("indicator", fill=COL_ACCENT_LIGHT)
        self.after(200, lambda: self.itemconfig("indicator", fill=COL_SUCCESS))
        self.pulse_after = self.after(1000, self._pulse)
