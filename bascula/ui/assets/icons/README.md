# Iconos neon para la UI

Este directorio contiene los PNG base (192×192 px) usados en los botones y accesos directos de la interfaz Holo/retro. Cada icono se exporta en blanco puro (`#FFFFFF`) sobre fondo transparente; el tinte final se aplica en tiempo de ejecución con `bascula.ui.icon_loader.load_icon`.

## Iconos disponibles

- `home.png` — Acceso a la pantalla principal.
- `tare.png` — Acción de tara / puesta a cero.
- `timer.png` — Temporizador / cronómetro.
- `settings.png` — Ajustes generales.
- `camara.png` — Escáner o cámara.
- `historial.png` — Historial de pesos / registros.
- `recipe.png` — Recetario.
- `food.png` — Base de datos de alimentos.
- `swap.png` — Cambio de unidades.
- `red.png` — Indicadores de red.
- `usuario.png` — Perfil de usuario / inicio de sesión.

## Flujo de trabajo

1. Diseña el icono en estilo trazo (líneas finas) sobre lienzo 192×192 px.
2. Exporta el resultado como PNG con fondo transparente y color blanco (`#FFFFFF`).
3. Copia el archivo a este directorio y nómbralo siguiendo la convención en minúsculas.
4. En el código, importa el cargador centralizado:
   ```python
   from bascula.ui.icon_loader import load_icon
   ```
5. Carga el icono indicando el nombre del archivo y, opcionalmente, el tamaño y el color de tinte:
   ```python
   neon_green = "#00FF88"
   play_icon = load_icon("timer.png", size=128, color=neon_green)
   ```
6. Reutiliza el mismo `PhotoImage` devolvido por `load_icon` para evitar cargas repetidas; el módulo realiza caché automáticamente.

Si el icono solicitado no existe se lanzará `FileNotFoundError` con la ruta completa para facilitar la depuración.
