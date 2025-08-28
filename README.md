# Báscula Pro — UI moderna (con panel de alimentos)

Proyecto híbrido: backend robusto (HX711 autodetectado, filtros, calibración) + **interfaz moderna** con tarjetas y botones grandes. (El panel de alimentos se integrará más adelante).

## Ejecutar (PC o Raspberry)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

> En Raspberry, instala la librería HX711 que corresponda a tu módulo si `hx711` no te funciona (ver alternativas en `requirements.txt`).

## Panel de alimentos (demo)
- Muestra **nombre del alimento**, **porción (g)** = peso estable, **kcal** y **macros** por porción.
- La detección está **simulada** en `bascula/services/food.py` (rota entre ejemplos).  
  Puedes conectar aquí tu visor/IA y llamar a `FoodService.detect(grams)` devolviendo el mismo formato.

## Configuración
Archivo `~/.bascula/config.json` con pines BCM, `reference_unit`, `offset_raw`, etc.

