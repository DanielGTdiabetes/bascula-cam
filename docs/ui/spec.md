# UI Specification – Báscula Cam v3.0

## Introducción
Este documento define las pantallas de usuario de la aplicación **Báscula Cam v3.0** en estilo retro CRT (verde/negro).  
Las imágenes en esta carpeta (`docs/ui/`) son mockups de referencia. Las pantallas sin imagen deben implementarse siguiendo el mismo estilo visual.

---

## Principios de Diseño
- Estética retro tipo terminal CRT (verde sobre negro).  
- Mascota robot verde siempre visible y animada.  
- Botones inferiores grandes (mínimo 80px) con icono + texto.  
- Máximo 3–4 botones principales por pantalla.  
- Jerarquía visual:  
  1. Mascota y estado actual.  
  2. Peso o información crítica.  
  3. Acciones principales.  
  4. Información secundaria.  

---

## Pantallas Definidas con Mockup

### 1. **Home Screen** (`Home.png`)
- Mascota centrada con mensaje inicial: *"¡Hola! ¿Qué vamos a pesar?"*.  
- Texto superior: *"Báscula Cam v3.0"*.  
- Barra inferior con botones: **Pesar, Favoritos, Escanear, Temporizador, Escuchar**.  

---

### 2. **Pantalla Recetas / Paso Actual** (`recetas.png`)
- Panel izquierdo: Lista de ingredientes con check ✅.  
- Panel derecho: Paso actual con texto grande.  
- Temporizador en cuenta atrás.  
- Controles de reproducción (⏮ ⏯ ⏭).  
- Mascota pequeña en esquina inferior derecha.  

---

### 3. **Pantalla Ajustes** (`ajustes.png`)
- Pestañas superiores: *General, Tema, Báscula, Red, Diabetes, Datos, Acerca de*.  
- Toggles con switches para:  
  - Focus Mode  
  - Animaciones de la mascota  
  - Efectos de sonido  
- Diseño limpio y minimalista.  

---

### 4. **Pantalla Báscula (Overlay de Pesaje)** (`bascula.png`)
- Número de peso **grande en el centro** (ej: `150 g`).  
- Estado debajo: *"Estable"*.  
- Botón contextual: *"Añadir Manzana?"*.  
- Mascota semi-transparente en segundo plano.  
- Botones inferiores: **Cero, Tara, Cerrar**.  

---

## Pantallas Adicionales (sin mockup, mismo estilo)

### 5. **Favoritos**
- Lista de alimentos marcados como favoritos.  
- Botón rápido para añadir al plato actual.  
- Opciones: **Añadir, Editar, Eliminar**.  
- Botones inferiores: **Volver, Añadir a Plato, Cerrar**.  

---

### 6. **Historial de Alimentos**
- Lista cronológica de comidas del día.  
- Cada entrada muestra: nombre alimento, gramos, macros.  
- Totales al pie.  
- Botones inferiores: **Exportar CSV, Enviar a Nightscout, Limpiar**.  

---

### 7. **Pantalla Diabetes / Nightscout**
- Integración directa con glucosa en sangre (si configurado).  
- Indicadores: **Glucosa actual, TIR, tendencias**.  
- Estado visual: colores y mascota reaccionando según valores (verde, amarillo, rojo).  
- Botones: **Refrescar, Configurar URL, Volver**.  

---

### 8. **Pantalla Miniweb**
- Vista previa ligera de la miniweb embebida.  
- Solo lectura: historial, comidas y datos exportables.  
- Consistencia visual con tema CRT.  

---

### 9. **Pantalla OTA / Sistema**
- Estado de actualización: versión actual vs. disponible.  
- Barra de progreso.  
- Botones: **Actualizar ahora, Posponer, Ver logs**.  

---

### 10. **Pantalla Información / Acerca de**
- Versión del software.  
- Créditos y colaboradores.  
- Estado de hardware detectado: **báscula, cámara, red, x735 HAT**.  

---

## Reglas de Implementación
1. **Colores seguros**:  
   - Fondo: `#001a00`  
   - Texto: `#00ffcc`  
   - Acentos: `#00e6b8`  
2. **Fallbacks obligatorios**:  
   - Si falla mascota → usar círculo + símbolo ♥.  
   - Si faltan iconos → reemplazar con texto.  
3. **Performance optimizada**:  
   - Máximo 2 animaciones simultáneas.  
   - Reutilización de widgets con `place()`.  
   - Assets gráficos < 50MB.  

---

## Mapeo de Archivos
| Archivo       | Pantalla                  |
|---------------|---------------------------|
| `Home.png`    | Home Screen               |
| `recetas.png` | Recetas / Paso Actual     |
| `ajustes.png` | Pantalla Ajustes          |
| `bascula.png` | Pantalla Báscula          |
| *(sin imagen)* | Favoritos                |
| *(sin imagen)* | Historial de Alimentos   |
| *(sin imagen)* | Pantalla Diabetes/NS     |
| *(sin imagen)* | Pantalla Miniweb         |
| *(sin imagen)* | Pantalla OTA/Sistema     |
| *(sin imagen)* | Pantalla Información     |

---

## Nota Final
Las pantallas con mockup tienen prioridad visual. Las pantallas sin mockup deben implementarse con la misma tipografía, colores y layout retro CRT, siguiendo los principios definidos arriba.  
Cualquier nueva función debe respetar esta especificación.
