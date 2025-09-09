# Retro Theme Pack — bascula-cam

Este paquete aplica un **estilo retro verde sobre negro** (tipo CRT/8‑bit) a toda la UI de Tkinter/ttk del proyecto.

## Archivos incluidos
- `bascula/config/theme.py` — Reemplazo completo con el tema **Retro** (green‑on‑black).

## Cómo activar el tema

1. Abre `bascula/ui/app.py` (o el primer archivo donde creas la ventana principal `Tk()`).
2. Justo después de `root = tk.Tk()` (o equivalente), añade estas líneas:

```python
from bascula.config.theme import apply_theme
apply_theme(root)
```

> **No rompe** tu jerarquía de widgets: asigna colores, fuentes y estilos globales.
> Se mapean también los estilos base (`TLabel`, `TButton`, etc.) para que hereden el look retro sin cambiar código existente.

### (Opcional) Usar estilos explícitos en tus widgets
Si quieres forzar el look en un widget concreto, usa estos estilos:

- Botón principal: `style="Retro.TButton"`
- Botón pequeño: `style="Retro.S.TButton"`
- Etiquetas: `style="Retro.TLabel"`, `Retro.M.TLabel`, `Retro.L.TLabel`, `Retro.Num.TLabel`
- Entry: `style="Retro.TEntry"`
- Notebook: `style="Retro.TNotebook"` y pestañas `Retro.TNotebook.Tab`
- Treeview: `style="Retro.Treeview"`
- Estados: `Retro/Ok.TLabel`, `Retro/Warn.TLabel`, `Retro/Error.TLabel`

### (Opcional) Tamaño de fuentes
Puedes escalar el tamaño base antes de aplicar el tema:

```python
from bascula.config import theme
theme.set_scale(1.15)   # 15% más grande
theme.apply_theme(root)
```

### Colores de estado
Aunque el estilo es monocromo verde, **se mantienen colores retro** para estados especiales:
- **Ok:** verde claro (`CRT_OK`)
- **Warning:** ámbar (`CRT_WARN`)
- **Error:** magenta/rojo (`CRT_ERROR`)

Si necesitas monocromo estricto, cambia estas constantes en `theme.py` al verde principal.

## Rendimiento (Raspberry Pi Zero 2W)
- El tema evita efectos costosos. 
- La opción de **scanlines** está desactivada (puedes activarla con `ENABLE_SCANLINES = True`, aunque no se recomienda en Pi Zero).

## Verificación
Fecha de generación: 2025-09-09 11:01:37
- Archivo `theme.py` válido (Python 3.9+), sin dependencias externas.
- Probado localmente en un Tk `Tk()` mínimo para confirmar que no lanza excepciones.
