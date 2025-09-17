# -*- coding: utf-8 -*-
import tkinter as tk
from bascula.config.theme import get_current_colors, THEMES

class BaseScreen(tk.Frame):
    """Base class for all screens with common functionality"""
    name = "base"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=get_current_colors()['COL_BG'], **kwargs)
        self.app = app
        self.name = self.__class__.__name__

    def on_show(self):
        pass

    def on_hide(self):
        pass


class HomeScreen(BaseScreen):
    name = "home"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        
        # Título principal más visible
        title = tk.Label(self, text="🏠 BÁSCULA DIGITAL PRO", 
                        fg=pal['COL_ACCENT'], bg=pal['COL_BG'],
                        font=("DejaVu Sans", 32, "bold"))
        title.pack(pady=40)
        
        # Subtítulo con estado
        subtitle = tk.Label(self, text="Sistema listo • Selecciona una opción", 
                           fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                           font=("DejaVu Sans", 16))
        subtitle.pack(pady=10)

        # Grid de botones más grande y visible
        grid = tk.Frame(self, bg=pal['COL_BG'])
        grid.pack(expand=True, pady=50)

        def btn(txt, icon, cmd, r, c):
            b = tk.Button(grid, text=f"{icon}\n{txt}", 
                         width=20, height=4, 
                         command=cmd,
                         font=("DejaVu Sans", 18, "bold"),
                         bg=pal['COL_ACCENT'], 
                         fg=pal['COL_BG'],
                         activebackground=pal['COL_ACCENT_LIGHT'],
                         relief="raised", bd=3)
            b.grid(row=r, column=c, padx=20, pady=20)
            return b

        btn("BÁSCULA", "⚖️", app.show_scale, 0, 0)
        btn("ESCÁNER", "📱", app.show_scanner, 0, 1)
        btn("AJUSTES", "⚙️", app.show_settings, 0, 2)
        
        # Información del sistema en la parte inferior
        info_frame = tk.Frame(self, bg=pal['COL_BG'])
        info_frame.pack(side="bottom", fill="x", pady=20)
        
        status_text = "✅ Sistema operativo • Presiona ESC para salir"
        tk.Label(info_frame, text=status_text, 
                fg=pal['COL_MUTED'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 12)).pack()


class ScaleScreen(BaseScreen):
    name = "scale"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        
        # Título
        tk.Label(self, text="⚖️ BÁSCULA DIGITAL", 
                fg=pal['COL_ACCENT'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 28, "bold")).pack(pady=20)
        
        # Display principal del peso - más grande y visible
        weight_frame = tk.Frame(self, bg=pal['COL_CARD'], relief="sunken", bd=5)
        weight_frame.pack(pady=30, padx=50, fill="x")
        
        self.weight_var = tk.StringVar(value="0.0 g")
        self.unit = "g"
        self.decimals = 1
        
        weight_display = tk.Label(weight_frame, textvariable=self.weight_var, 
                                 fg=pal['COL_ACCENT'], bg=pal['COL_CARD'],
                                 font=("DejaVu Sans", 64, "bold"))
        weight_display.pack(pady=40)
        
        # Estado de la báscula
        self.status_var = tk.StringVar(value="Listo para pesar")
        tk.Label(self, textvariable=self.status_var, 
                fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 16)).pack(pady=10)

        # Botones de control más grandes
        controls = tk.Frame(self, bg=pal['COL_BG'])
        controls.pack(pady=30)
        
        def control_btn(text, icon, cmd, col):
            btn = tk.Button(controls, text=f"{icon}\n{text}", 
                           width=12, height=3,
                           command=cmd,
                           font=("DejaVu Sans", 14, "bold"),
                           bg=pal['COL_ACCENT'], fg=pal['COL_BG'],
                           activebackground=pal['COL_ACCENT_LIGHT'])
            btn.grid(row=0, column=col, padx=15)
            return btn
            
        control_btn("TARA", "🔄", app.tare_scale, 0)
        control_btn("CERO", "⭕", app.zero_scale, 1)
        control_btn("UNIDAD", "📏", self._toggle_unit, 2)
        
        # Botón volver
        tk.Button(self, text="🏠 VOLVER AL INICIO", 
                 command=app.show_main,
                 font=("DejaVu Sans", 16, "bold"),
                 bg=pal['COL_CARD'], fg=pal['COL_TEXT'],
                 width=20, height=2).pack(pady=30)

        # Refresco del peso
        self.after(200, self._refresh_weight)

    def _refresh_weight(self):
        try:
            w = self.app.get_latest_weight()
            if self.unit == "g":
                if w > 1000:
                    txt = f"{w/1000:.2f} kg"
                else:
                    txt = f"{w:.{self.decimals}f} g"
            else:
                # convertir a oz
                oz_val = w / 28.3495
                txt = f"{oz_val:.{max(0, self.decimals)}f} oz"
            self.weight_var.set(txt)
            
            # Actualizar estado
            if w > 5:
                self.status_var.set("Pesando...")
            else:
                self.status_var.set("Listo para pesar")
                
        except Exception as e:
            self.weight_var.set("-- Error --")
            self.status_var.set("Error de conexión")
        
        self.after(200, self._refresh_weight)

    def _toggle_unit(self):
        self.unit = "oz" if self.unit == "g" else "g"


class ScannerScreen(BaseScreen):
    name = "scanner"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        
        # Título
        tk.Label(self, text="📱 ESCÁNER DE CÓDIGOS", 
                fg=pal['COL_ACCENT'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 28, "bold")).pack(pady=30)
        
        # Área de estado del escáner
        scanner_frame = tk.Frame(self, bg=pal['COL_CARD'], relief="sunken", bd=5)
        scanner_frame.pack(pady=40, padx=50, fill="both", expand=True)
        
        # Icono grande
        tk.Label(scanner_frame, text="📷", 
                fg=pal['COL_ACCENT'], bg=pal['COL_CARD'],
                font=("DejaVu Sans", 80)).pack(pady=40)
        
        # Instrucciones
        tk.Label(scanner_frame, text="Acerca un código de barras\no QR al lector", 
                fg=pal['COL_TEXT'], bg=pal['COL_CARD'],
                font=("DejaVu Sans", 18), justify="center").pack(pady=20)
        
        # Estado
        self.scan_status = tk.StringVar(value="Esperando código...")
        tk.Label(scanner_frame, textvariable=self.scan_status, 
                fg=pal['COL_MUTED'], bg=pal['COL_CARD'],
                font=("DejaVu Sans", 14)).pack(pady=10)
        
        # Botón volver
        tk.Button(self, text="🏠 VOLVER AL INICIO", 
                 command=app.show_main,
                 font=("DejaVu Sans", 16, "bold"),
                 bg=pal['COL_CARD'], fg=pal['COL_TEXT'],
                 width=20, height=2).pack(pady=30)


class SettingsScreen(BaseScreen):
    name = "settings"
    def __init__(self, parent, app, get_state=None, set_state=None, change_theme=None, back=None):
        super().__init__(parent, app)
        pal = get_current_colors()

        # Título
        tk.Label(self, text="⚙️ CONFIGURACIÓN",
                fg=pal['COL_ACCENT'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 28, "bold")).pack(pady=30)

        # Sección de temas
        self._theme_display = {k: v.display_name for k, v in THEMES.items()}
        theme_frame = tk.LabelFrame(self, text="Apariencia",
                                   fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                                   font=("DejaVu Sans", 16, "bold"))
        theme_frame.pack(pady=20, padx=50, fill="x")
        
        theme_buttons = tk.Frame(theme_frame, bg=pal['COL_BG'])
        theme_buttons.pack(pady=20)
        
        def theme_btn(text, icon, theme_name, col):
            cmd = lambda: change_theme(theme_name) if change_theme else None
            btn = tk.Button(theme_buttons, text=f"{icon}\n{text}", 
                           width=15, height=3,
                           command=cmd,
                           font=("DejaVu Sans", 14, "bold"),
                           bg=pal['COL_ACCENT'], fg=pal['COL_BG'],
                           activebackground=pal['COL_ACCENT_LIGHT'])
            btn.grid(row=0, column=col, padx=15)
            return btn
            
        theme_btn("MODERNO", "🌆", "modern", 0)
        theme_btn("RETRO", "📺", "retro", 1)
        
        # Información del sistema
        info_frame = tk.LabelFrame(self, text="Sistema", 
                                  fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                                  font=("DejaVu Sans", 16, "bold"))
        info_frame.pack(pady=20, padx=50, fill="x")
        
        tk.Label(info_frame, text="Báscula Digital Pro v1.0\nRaspberry Pi 5 - Kiosk Mode", 
                fg=pal['COL_MUTED'], bg=pal['COL_BG'],
                font=("DejaVu Sans", 12), justify="center").pack(pady=15)
        
        # Botón volver
        tk.Button(self, text="🏠 VOLVER AL INICIO", 
                 command=(back or app.show_main),
                 font=("DejaVu Sans", 16, "bold"),
                 bg=pal['COL_CARD'], fg=pal['COL_TEXT'],
                 width=20, height=2).pack(pady=30)


class TimerPopup(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.title("Temporizador")
        self.geometry("300x160+50+50")
        pal = get_current_colors()
        self.configure(bg=pal['COL_BG'])
        tk.Label(self, text="Minutos:", fg=pal['COL_TEXT'], bg=pal['COL_BG']).pack(pady=6)
        self.e = tk.Entry(self); self.e.insert(0, "1"); self.e.pack(pady=6)
        tk.Button(self, text="Iniciar", command=self._start).pack(pady=8)
        tk.Button(self, text="Cerrar", command=self.destroy).pack()
        self.app = app

    def _start(self):
        try:
            m = int(self.e.get().strip() or "1")
        except Exception:
            m = 1
        self.app.start_timer(m * 60)
        self.destroy()
