# Ejecutar la aplicación y seleccionar UI

## Requisitos rápidos
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Lanzar la app (UI moderna por defecto)
```bash
python3 main.py
# o explícito
python3 main.py --ui modern
```

## UI alternativa `screens` (módulo opcional)
```bash
python3 main.py --ui screens
```

Notas:
- La UI `screens` usa `HomeScreen` y comparte backend con la moderna.
- Si usas Raspberry Pi, instala la librería HX711 adecuada para tu módulo.
