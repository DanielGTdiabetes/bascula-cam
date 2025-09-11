# Retro Theme Pack — bascula-cam

Este paquete aplica un estilo retro verde sobre negro (tipo CRT) a la UI.

## Dónde están los temas
- `bascula/config/themes.py`: gestor de temas (ThemeManager) y paletas (incluye Retro).

## Cómo activar el tema Retro

1. Abre `bascula/ui/app.py` (o el primer archivo donde creas `Tk()`).
2. Justo después de `root = tk.Tk()`, añade:

```python
from bascula.config.themes import apply_theme
apply_theme(root, 'retro')
```

Esto aplica colores y estilos globales (ttk) sin cambiar tu jerarquía de widgets.

### (Opcional) Selección y estado del tema con ThemeManager

```python
from bascula.config import themes
tm = themes.get_theme_manager()
tm.set_theme('retro')
tm.apply_to_root(root)
themes.update_color_constants()
```

### Estilos útiles (ejemplos)
- Botón: `style="Retro.TButton"`, mini: `Retro.S.TButton`
- Label: `Retro.TLabel`, `Retro.M.TLabel`, `Retro.L.TLabel`, `Retro.Num.TLabel`
- Entry: `Retro.TEntry`
- Notebook: `Retro.TNotebook` y `Retro.TNotebook.Tab`
- Treeview: `Retro.Treeview`

### Rendimiento (Raspberry Pi Zero 2W)
- Efectos costosos desactivados por defecto. `scanlines` opcional vía ThemeManager.

## Notas
- La implementación antigua `bascula.config.theme` ha sido sustituida por `bascula.config.themes`.
- Si encuentras referencias a `bascula.config.theme`, cámbialas por `bascula.config.themes`.

