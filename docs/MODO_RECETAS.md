# Modo Recetas (Paso a Paso)

Este modo permite generar o abrir recetas, seguir los pasos con control por voz, usar temporizadores por paso y reconocer ingredientes con cámara/barcode.

## Acceso

- Desde la pantalla principal (Home), pulsa `🍳 Recetas`.
- Opciones:
  - Generar con IA: escribe o dicta una consulta (botón `🎤 Voz`). Si no hay API, usa plantillas locales.
  - Abrir guardada…: abre el selector de recetas guardadas.

## Selector de recetas guardadas

- Filtro: busca por título e ingredientes. Puedes dictar con `🎤 Voz` o limpiar el filtro.
- Vista previa: al seleccionar una receta se muestran ingredientes y los primeros pasos.
- Abrir: botón `Abrir` o doble toque sobre la receta (pantalla táctil compatible). También con `Enter`.
- Eliminar: botón `Eliminar` con confirmación.

## Interfaz del overlay

- Panel de ingredientes: muestra estado
  - Pendiente (gris), Detectado (verde), Sustitución disponible (ámbar).
  - `📷 Buscar ingrediente`: abre escáner de códigos. Si coincide, se marca y se muestra animación Target Lock.
  - `🔍 Detectar (visión)`: clasificador ligero (placeholder) que marca el siguiente pendiente.
- Paso actual:
  - Texto grande con transición suave.
  - `▶️/⏸️/⏭️/↩️` para reproducir, pausar, siguiente y repetir.
  - Temporizador por paso: si el paso tiene `timer_s`, muestra una insignia de tiempo. Al finalizar, suena una alarma (3 pares de tonos).
- Mascota IA: indica estados `listen/process/idle` durante voz y animaciones.
- `💾 Guardar`: persiste la receta y su estado en `~/.config/bascula/recipes.jsonl`.

## Control por voz

Pulsa `🎤 Escuchar` para activar escucha continua (auto-rearme). Si tienes wakeword activado, se iniciará la escucha al detectarlo.

Comandos soportados (español, tolerantes a acentos/sinónimos):

- Navegación:
  - “siguiente”, “avanza”, “adelante”
  - “atrás/atras”, “anterior”, “previo”
  - “ir al paso N”, “paso N”
  - “primer paso”, “al inicio”
  - “último paso”, “al final”
- Reproducción y lectura:
  - “repite”, “repetir paso N”
  - “leer paso” (vuelve a leer el paso actual)
  - “leer ingredientes” (lee la lista de ingredientes)
  - “pausa”, “continuar”
- Temporizador:
  - “iniciar temporizador”, “reanudar temporizador”
  - “parar/pausar temporizador”
  - “cuánto queda”, “tiempo restante”
- Ingredientes:
  - “buscar ingrediente”, “escanear” (abre el escáner)
  - “detectar” (clasificador rápido)
  - “marcar ingrediente [nombre]” (marca el ingrediente por nombre)
- Voz:
  - “voz on”, “voz off”, “silencio”

Notas:
- La escucha no bloquea la interfaz. Las respuestas habladas confirman acciones (“Siguiente”, “Pausa”, etc.).
- El wakeword, si está habilitado en ajustes, dispara auto-escucha con enfriamiento breve para evitar repeticiones.

## Persistencia

- Las recetas se guardan en `~/.config/bascula/recipes.jsonl` (una por línea, formato JSON). Disponible offline.

## Problemas comunes

- Si no se detecta la cámara o `pyzbar`/`Pillow`, el escáner no funcionará. El resto del modo sigue operativo.
- Si los scripts `hear.sh`/`say.sh` no están instalados, la voz se desactiva de forma silenciosa.

