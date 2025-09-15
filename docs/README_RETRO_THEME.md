# Retro Theme Pack — bascula-cam

Este paquete aplica un estilo retro verde sobre negro (tipo CRT) a la UI.

## Dónde están los temas
- `bascula/config/theme.py`: paletas disponibles y helpers para aplicarlas.

## Cómo activar el tema Retro

1. Abre `bascula/ui/app.py` (o el primer archivo donde creas `Tk()`).
2. Justo después de `root = tk.Tk()`, añade:

```python
from bascula.config.theme import apply_theme
apply_theme(root, 'retro')
```

Esto aplica colores y estilos globales (ttk) sin cambiar tu jerarquía de widgets.

## Notas
- El antiguo gestor de temas ha sido sustituido por `bascula.config.theme`.

