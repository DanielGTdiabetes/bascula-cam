Tarea
Ajustar la UI de Báscula Cam para que coincida con los mockups en docs/ui/ (estilo CRT verde) manteniendo la arquitectura nueva (UI modular RPi). No romper servicios ni instaladores.

Referencias visuales (guía, no lectura automática):
- docs/ui/home_mockup.svg (o .png)
- docs/ui/recipes_mockup.svg
- docs/ui/settings_mockup.svg
- docs/ui/scale_overlay_mockup.svg

Requisitos de diseño (obligatorios)
- Paleta: BG #031d16, Primer #11f0c5, Acento #14e4b7, Texto #c4fff3.
- Tipografía monoespaciada para cabecera y números grandes (ej. “DejaVu Sans Mono” / fallback Arial).
- Cabecera fija: “Báscula Cam v3.0” a la izquierda, icono ⚙ a la derecha.
- Barra inferior con 5 botones grandes (≥80 px alto): Pesar, Favoritos, Escanear, Temporizador, Escuchar.
- Mascota centrada, tamaño ~40% de ancho útil (vector Canvas o PNG generado), SIN bloquear toques.
- Overlay de pesaje: número en grande (≥ 120 pt aprox.), estado “Estable/Inestable”, atajos Cero/Tara/Cerrar, CTA “Añadir <alimento>?”.
- Pantalla Recetas: dos columnas → izquierda lista ingredientes con checks, derecha paso actual grande + temporizador + controles (▶ ⏸ ⏭).
- Pantalla Ajustes: pestañas “General, Tema, Báscula, Red, Diabetes, Datos, Acerca de” con toggles grandes.

Robustez UI (no-crash)
- Prohibido `bg=""`. Si falta color → `#111111`.
- Si faltan assets de mascota → placeholder Canvas.
- `show_mascot_message` con defaults si falta icono/color; nunca exception.
- Navegación `show_screen(name)` envuelta en try/except con toast y retorno a “home”.

Compatibilidad (no romper)
- Mantener ScaleService.safe_create + NullScaleService.
- Mantener VoiceService/Piper, VisionService, TareManager, BgMonitor.
- No tocar install-1/2 salvo para añadir build de assets si hace falta.
- Pantallas opcionales registradas perezosas: history, focus, diabetes, nightscout, wifi, apikey.

Implementación
1) Ajusta layouts en:
   - bascula/ui/rpi_optimized_ui.py  (Home, ScaleOverlay, Recipes, Settings)
   - bascula/ui/lightweight_widgets.py (Buttons CRT, Tabs CRT, Toggles grandes)
   - bascula/ui/failsafe_mascot.py (tamaños y centrado; Canvas por defecto)
2) Añade helpers de estilo CRT:
   - bascula/ui/theme_crt.py  → colores, fuentes, padding, util draw_dotted_rule()
3) Iconos en botones:
   - Usa caracteres simples (⚖ ★ 📷 ⏱ 🎙) o imágenes pequeñas (<10KB) si existen.
4) Generación de mascota (si hay SVG):
   - scripts/build-mascot-assets.sh → rsvg-convert @512/@1024 a assets/mascota/_gen
   - Carga preferente Canvas; si no, PNG @512.

Alineación con mockups (pixel-ish)
- Cabecera: altura ~48 px, regla de puntos dibujada con draw_dotted_rule().
- Home: mascota centrada + peso actual visible; si no hay pesaje activo, peso pequeño “0 g”.
- Recetas: lista izquierda (máx. 12 items visibles con scroll), paso actual derecha (font 28–36 pt), temporizador caja 120×64 aprox.
- Settings: toggles tipo cápsula, estado ON color #11f0c5, OFF color #073e33.

Testing
- `python -m py_compile $(git ls-files '*.py')` OK.
- `bash scripts/verify-all.sh` OK (puede avisar si no hay X/hardware).
- `tools/smoke_nav.py` recorre home/scale/settings/history/focus/diabetes/nightscout/wifi/apikey sin tumbar Tkinter.
- `tools/smoke_mascot.py` cambia estados sin error.
- Home, Recipes, Settings y ScaleOverlay se ven como en docs/ui/*.svg a nivel de estructura (no exige exactitud tipográfica al píxel).

Entrega
- Código actualizado, sin dependencias nuevas de Python.
- `docs/ui/spec.md` actualizado con cualquier ajuste fino aplicado.
- Si usas PNG generados, añade a .gitignore para no versionarlos.
