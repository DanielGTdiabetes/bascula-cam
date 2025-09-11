# bascula/config/themes.py
# Sistema de temas intercambiables para la UI
# Incluye: CRT Verde, Synthwave Neón, Dark Modern, Light Mode

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
from pathlib import Path

@dataclass
class Theme:
    """Estructura de datos para un tema"""
    name: str
    display_name: str
    
    # Colores base
    bg: str              # Fondo principal
    card: str            # Fondo de tarjetas
    card_hover: str      # Hover en tarjetas
    text: str            # Texto principal
    text_muted: str      # Texto secundario
    accent: str          # Color de acento
    accent_light: str    # Acento claro
    success: str         # Éxito/OK
    warning: str         # Advertencia
    danger: str          # Error/Peligro
    border: str          # Bordes
    
    # Efectos especiales
    scanlines: bool = False
    scanline_color: str = "#000000"
    scanline_opacity: float = 0.3
    glow_effect: bool = False
    animations: bool = False
    
    # Configuración de fuentes
    font_family: str = "DejaVu Sans Mono"
    font_weight_display: str = "bold"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'display_name': self.display_name,
            'colors': {
                'bg': self.bg,
                'card': self.card,
                'card_hover': self.card_hover,
                'text': self.text,
                'text_muted': self.text_muted,
                'accent': self.accent,
                'accent_light': self.accent_light,
                'success': self.success,
                'warning': self.warning,
                'danger': self.danger,
                'border': self.border,
            },
            'effects': {
                'scanlines': self.scanlines,
                'scanline_color': self.scanline_color,
                'scanline_opacity': self.scanline_opacity,
                'glow_effect': self.glow_effect,
                'animations': self.animations,
            },
            'fonts': {
                'family': self.font_family,
                'weight_display': self.font_weight_display,
            }
        }

# ==== DEFINICIÓN DE TEMAS ====

THEMES = {
    'crt_green': Theme(
        name='crt_green',
        display_name='🖥️ CRT Verde Retro',
        bg='#000000',           # Negro puro
        card='#0a0f0a',         # Verde muy oscuro
        card_hover='#0f1a0f',   # Verde oscuro hover
        text='#00ff66',         # Verde CRT brillante
        text_muted='#00cc44',   # Verde CRT apagado
        accent='#00ff88',       # Verde neón
        accent_light='#44ffaa', # Verde claro
        success='#00ff00',      # Verde puro
        warning='#ffee00',      # Amarillo ámbar
        danger='#ff3366',       # Rojo rosado
        border='#00ff66',       # Verde bordes
        scanlines=True,         # Activar scanlines
        scanline_color='#001100',
        scanline_opacity=0.4,
        glow_effect=True,       # Efecto glow en texto
        font_family='Courier New',
    ),
    
    'synthwave': Theme(
        name='synthwave',
        display_name='🌆 Synthwave Neón',
        bg='#0a0613',           # Azul muy oscuro
        card='#1a0e2e',         # Púrpura oscuro
        card_hover='#2a1e3e',   # Púrpura hover
        text='#ff00ff',         # Magenta neón
        text_muted='#bd93f9',   # Púrpura pastel
        accent='#00ffff',       # Cyan neón
        accent_light='#66ffff', # Cyan claro
        success='#50fa7b',      # Verde neón
        warning='#ffb86c',      # Naranja neón
        danger='#ff79c6',       # Rosa neón
        border='#ff00ff',       # Magenta bordes
        glow_effect=True,
        animations=True,
        font_family='DejaVu Sans Mono',
    ),
    
    'cyberpunk': Theme(
        name='cyberpunk',
        display_name='🌃 Cyberpunk 2077',
        bg='#000000',
        card='#0d0d0d',
        card_hover='#1a1a1a',
        text='#f0e800',         # Amarillo cyberpunk
        text_muted='#a89c00',
        accent='#ff0066',       # Rosa neón
        accent_light='#ff3388',
        success='#00ff9f',      # Verde neón
        warning='#ff9f00',      # Naranja
        danger='#ff0040',       # Rojo neón
        border='#f0e800',
        glow_effect=True,
        font_family='DejaVu Sans Mono',
    ),
    
    'terminal_amber': Theme(
        name='terminal_amber',
        display_name='📟 Terminal Ámbar',
        bg='#000000',
        card='#0a0700',
        card_hover='#1a0f00',
        text='#ffb000',         # Ámbar
        text_muted='#cc8800',
        accent='#ffc833',       # Ámbar brillante
        accent_light='#ffdd66',
        success='#88ff00',      # Verde lima
        warning='#ffff00',      # Amarillo
        danger='#ff3333',       # Rojo
        border='#ffb000',
        scanlines=True,
        scanline_color='#110800',
        scanline_opacity=0.3,
        font_family='Courier New',
    ),
    
    'matrix': Theme(
        name='matrix',
        display_name='💊 Matrix',
        bg='#000000',
        card='#001100',
        card_hover='#002200',
        text='#00ff00',         # Verde Matrix
        text_muted='#008800',
        accent='#00ff00',
        accent_light='#44ff44',
        success='#00ff00',
        warning='#ffff00',
        danger='#ff0000',
        border='#00ff00',
        scanlines=True,
        scanline_color='#001100',
        scanline_opacity=0.2,
        glow_effect=True,
        font_family='Courier New',
    ),
    
    'vaporwave': Theme(
        name='vaporwave',
        display_name='🌴 Vaporwave',
        bg='#1a0033',           # Púrpura oscuro
        card='#2d1b69',         # Púrpura medio
        card_hover='#3d2b79',
        text='#ff71ce',         # Rosa pastel
        text_muted='#cc5aa3',
        accent='#01cdfe',       # Cyan pastel
        accent_light='#34dfff',
        success='#05ffa1',      # Verde pastel
        warning='#fffb96',      # Amarillo pastel
        danger='#ff71ce',       # Rosa
        border='#b967ff',       # Púrpura pastel
        glow_effect=True,
        font_family='DejaVu Sans',
    ),
    
    'dark_modern': Theme(
        name='dark_modern',
        display_name='🌙 Dark Modern',
        bg='#0a0e1a',
        card='#141823',
        card_hover='#1a1f2e',
        text='#f0f4f8',
        text_muted='#8892a0',
        accent='#00d4aa',
        accent_light='#00ffcc',
        success='#00d4aa',
        warning='#ffa500',
        danger='#ff6b6b',
        border='#2a3142',
        font_family='DejaVu Sans',
    ),
    
    'light_mode': Theme(
        name='light_mode',
        display_name='☀️ Light Mode',
        bg='#ffffff',
        card='#f8f9fa',
        card_hover='#e9ecef',
        text='#212529',
        text_muted='#6c757d',
        accent='#007bff',
        accent_light='#4da3ff',
        success='#28a745',
        warning='#ffc107',
        danger='#dc3545',
        border='#dee2e6',
        font_family='DejaVu Sans',
    ),
}

class ThemeManager:
    """Gestor de temas para la aplicación"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path.home() / '.bascula')
        self.config_file = self.config_dir / 'theme.json'
        self.current_theme_name = 'dark_modern'
        self.current_theme = THEMES[self.current_theme_name]
        self._scanline_overlay = None
        self._glow_widgets = []
        self.load_theme_preference()
    
    def load_theme_preference(self):
        """Carga el tema guardado"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    theme_name = data.get('current_theme', 'dark_modern')
                    if theme_name in THEMES:
                        self.current_theme_name = theme_name
                        self.current_theme = THEMES[theme_name]
        except Exception:
            pass
    
    def save_theme_preference(self):
        """Guarda el tema actual"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump({'current_theme': self.current_theme_name}, f)
        except Exception:
            pass
    
    def get_available_themes(self) -> Dict[str, str]:
        """Retorna dict de nombre: display_name"""
        return {name: theme.display_name for name, theme in THEMES.items()}
    
    def set_theme(self, theme_name: str) -> bool:
        """Cambia al tema especificado"""
        if theme_name not in THEMES:
            return False
        
        self.current_theme_name = theme_name
        self.current_theme = THEMES[theme_name]
        self.save_theme_preference()
        return True
    
    def apply_to_root(self, root: tk.Tk):
        """Aplica el tema a la ventana raíz"""
        theme = self.current_theme
        
        # Configurar colores base
        root.configure(bg=theme.bg)
        
        # Configurar opciones globales
        root.option_add("*background", theme.bg)
        root.option_add("*foreground", theme.text)
        root.option_add("*selectBackground", theme.accent)
        root.option_add("*selectForeground", theme.bg)
        root.option_add("*insertBackground", theme.text)
        root.option_add("*highlightThickness", 0)
        root.option_add("*font", f"{theme.font_family} 12")
        
        # Aplicar efectos especiales
        if theme.scanlines:
            self._apply_scanlines(root)
        else:
            self._remove_scanlines()
        
        # Configurar ttk Style
        self._setup_ttk_style(root)
    
    def _setup_ttk_style(self, root: tk.Misc):
        """Configura los estilos ttk según el tema"""
        theme = self.current_theme
        style = ttk.Style(root)
        
        try:
            style.theme_use("clam")
        except:
            pass
        
        # Configuración general
        style.configure(".",
            background=theme.bg,
            foreground=theme.text,
            fieldbackground=theme.card,
            bordercolor=theme.border,
            lightcolor=theme.border,
            darkcolor=theme.border,
            troughcolor=theme.card_hover,
            selectbackground=theme.accent,
            selectforeground=theme.bg,
            insertcolor=theme.text,
            font=(theme.font_family, 12)
        )
        
        # Estados
        style.map(".",
            foreground=[("disabled", theme.text_muted)],
            background=[("disabled", theme.bg)]
        )
        
        # Botones
        style.configure("TButton",
            padding=(10, 8),
            relief="flat",
            borderwidth=2,
            background=theme.accent,
            foreground=theme.bg,
            focuscolor=theme.accent_light,
            font=(theme.font_family, 12, theme.font_weight_display)
        )
        style.map("TButton",
            background=[
                ("pressed", theme.accent_light),
                ("active", theme.accent_light)
            ],
            foreground=[
                ("pressed", theme.bg),
                ("active", theme.bg)
            ]
        )
        
        # Labels
        style.configure("TLabel",
            background=theme.bg,
            foreground=theme.text,
            font=(theme.font_family, 12)
        )
        
        # Entry
        style.configure("TEntry",
            padding=(8, 6),
            fieldbackground=theme.card,
            foreground=theme.text,
            bordercolor=theme.border,
            insertcolor=theme.text,
            font=(theme.font_family, 12)
        )
        style.map("TEntry",
            fieldbackground=[
                ("focus", theme.card_hover),
                ("readonly", theme.card)
            ],
            bordercolor=[
                ("focus", theme.accent)
            ]
        )
        
        # Checkbutton y Radiobutton
        style.configure("TCheckbutton",
            background=theme.bg,
            foreground=theme.text,
            focuscolor=theme.accent,
            font=(theme.font_family, 12)
        )
        style.configure("TRadiobutton",
            background=theme.bg,
            foreground=theme.text,
            focuscolor=theme.accent,
            font=(theme.font_family, 12)
        )
        
        # Notebook (tabs)
        style.configure("TNotebook",
            background=theme.bg,
            borderwidth=0
        )
        style.configure("TNotebook.Tab",
            background=theme.card,
            foreground=theme.text_muted,
            padding=(12, 8),
            font=(theme.font_family, 11),
            borderwidth=2
        )
        style.map("TNotebook.Tab",
            background=[
                ("selected", theme.card_hover),
                ("active", theme.card_hover)
            ],
            foreground=[
                ("selected", theme.text),
                ("active", theme.accent)
            ]
        )
        
        # Scrollbar
        style.configure("Vertical.TScrollbar",
            background=theme.card,
            troughcolor=theme.bg,
            bordercolor=theme.border,
            arrowcolor=theme.text,
            width=20
        )
        style.configure("Horizontal.TScrollbar",
            background=theme.card,
            troughcolor=theme.bg,
            bordercolor=theme.border,
            arrowcolor=theme.text,
            width=20
        )
        
        # Progressbar
        style.configure("Horizontal.TProgressbar",
            troughcolor=theme.card,
            background=theme.accent,
            bordercolor=theme.border
        )
        
        # Treeview
        style.configure("Treeview",
            background=theme.card,
            fieldbackground=theme.card,
            foreground=theme.text,
            bordercolor=theme.border,
            rowheight=28,
            font=(theme.font_family, 11)
        )
        style.configure("Treeview.Heading",
            background=theme.card_hover,
            foreground=theme.text,
            font=(theme.font_family, 11, "bold"),
            bordercolor=theme.border
        )
        style.map("Treeview",
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.bg)]
        )
        style.map("Treeview.Heading",
            background=[("active", theme.accent_light)]
        )
        
        # Combobox
        style.configure("TCombobox",
            fieldbackground=theme.card,
            background=theme.card,
            foreground=theme.text,
            bordercolor=theme.border,
            arrowcolor=theme.text,
            font=(theme.font_family, 12)
        )
        style.map("TCombobox",
            fieldbackground=[
                ("readonly", theme.card),
                ("focus", theme.card_hover)
            ],
            bordercolor=[
                ("focus", theme.accent)
            ]
        )
    
    def _apply_scanlines(self, root: tk.Tk):
        """Aplica efecto de scanlines CRT"""
        if self._scanline_overlay:
            self._remove_scanlines()
        
        theme = self.current_theme
        if not theme.scanlines:
            return
        
        # Crear overlay canvas para scanlines
        self._scanline_overlay = tk.Canvas(
            root,
            highlightthickness=0,
            bd=0,
            bg=theme.bg
        )
        
        # Posicionar sobre todo pero sin interceptar eventos
        self._scanline_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Dibujar scanlines
        def draw_scanlines():
            if not self._scanline_overlay or not self._scanline_overlay.winfo_exists():
                return
            
            self._scanline_overlay.delete("all")
            w = self._scanline_overlay.winfo_width()
            h = self._scanline_overlay.winfo_height()
            
            # Líneas horizontales cada 2 píxeles
            for y in range(0, h, 3):
                self._scanline_overlay.create_rectangle(
                    0, y, w, y+1,
                    fill=theme.scanline_color,
                    outline="",
                    stipple="gray25"  # Patrón semi-transparente
                )
            
            # Hacer el canvas "transparente" a eventos
            self._scanline_overlay.lower()
        
        self._scanline_overlay.bind("<Configure>", lambda e: draw_scanlines())
        root.after(100, draw_scanlines)
    
    def _remove_scanlines(self):
        """Elimina el overlay de scanlines"""
        if self._scanline_overlay:
            try:
                self._scanline_overlay.destroy()
            except:
                pass
            self._scanline_overlay = None
    
    def apply_glow_effect(self, widget: tk.Widget):
        """Aplica efecto glow a un widget (solo si el tema lo soporta)"""
        if not self.current_theme.glow_effect:
            return
        
        # Simular glow con sombra de texto
        if isinstance(widget, (tk.Label, tk.Button)):
            try:
                # Crear efecto de sombra/glow
                widget.configure(
                    highlightbackground=self.current_theme.accent,
                    highlightthickness=1
                )
            except:
                pass
    
    def get_colors(self) -> Dict[str, str]:
        """Retorna el diccionario de colores del tema actual"""
        return {
            'COL_BG': self.current_theme.bg,
            'COL_CARD': self.current_theme.card,
            'COL_CARD_HOVER': self.current_theme.card_hover,
            'COL_TEXT': self.current_theme.text,
            'COL_MUTED': self.current_theme.text_muted,
            'COL_ACCENT': self.current_theme.accent,
            'COL_ACCENT_LIGHT': self.current_theme.accent_light,
            'COL_SUCCESS': self.current_theme.success,
            'COL_WARN': self.current_theme.warning,
            'COL_DANGER': self.current_theme.danger,
            'COL_BORDER': self.current_theme.border,
        }

# Instancia global del gestor de temas
_theme_manager: Optional[ThemeManager] = None

def get_theme_manager() -> ThemeManager:
    """Obtiene o crea la instancia global del gestor de temas"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager

def apply_theme(root: tk.Tk, theme_name: Optional[str] = None) -> bool:
    """
    Función de conveniencia para aplicar un tema a la ventana raíz.
    
    Args:
        root: Ventana Tk principal
        theme_name: Nombre del tema (opcional, usa el guardado si no se especifica)
    
    Returns:
        True si se aplicó correctamente
    """
    manager = get_theme_manager()
    
    if theme_name:
        if not manager.set_theme(theme_name):
            return False
    
    manager.apply_to_root(root)
    return True

def get_current_colors() -> Dict[str, str]:
    """Obtiene los colores del tema actual"""
    return get_theme_manager().get_colors()

# Exportar las constantes de color para compatibilidad con código existente
def update_color_constants():
    """Actualiza las constantes globales de color según el tema actual"""
    colors = get_current_colors()
    
    # Esto permite que el código existente siga funcionando
    import bascula.ui.widgets as widgets
    if widgets:
        widgets.COL_BG = colors['COL_BG']
        widgets.COL_CARD = colors['COL_CARD']
        widgets.COL_CARD_HOVER = colors['COL_CARD_HOVER']
        widgets.COL_TEXT = colors['COL_TEXT']
        widgets.COL_MUTED = colors['COL_MUTED']
        widgets.COL_ACCENT = colors['COL_ACCENT']
        widgets.COL_ACCENT_LIGHT = colors['COL_ACCENT_LIGHT']
        widgets.COL_SUCCESS = colors['COL_SUCCESS']
        widgets.COL_WARN = colors['COL_WARN']
        widgets.COL_DANGER = colors['COL_DANGER']
        widgets.COL_BORDER = colors['COL_BORDER']