# Báscula Cam

Aplicación de kiosko para Raspberry Pi que combina lectura de peso en tiempo real, análisis de alimentos con cámara y seguimiento nutricional básico. Esta versión utiliza la interfaz clásica de Tk (sin temas personalizados) y funciona tanto con hardware real como en modo de simulación.

## Características principales

- **Lectura de báscula**: comunica con `/dev/serial0` a 115200 bps mediante `pyserial`. Si no se encuentra el puerto serie, activa un simulador con ruido suave y detección de estabilidad.
- **Análisis con cámara**:
  - Captura con Picamera2 cuando está disponible.
  - Decodificación de códigos de barras usando `pyzbar` y consulta de OpenFoodFacts con caché local en `~/.bascula/cache/off/`.
  - Si no se detecta código y existe `OPENAI_API_KEY`, usa OpenAI Vision para identificar el alimento y obtener su perfil nutricional.
  - Fallback offline con `data/local_food_db.json`.
- **Cálculo de macronutrientes**: resume hidratos, kcal, proteína y grasa por alimento y totales de la sesión.
- **Persistencia**: favoritos en `~/.bascula/data/favorites.json` y configuración en `~/.bascula/config.yaml`.
- **Mascota animada**: canvas clásico con sprites (`assets/mascot/`) y placeholder vectorial en caso de fallo. Cambia de estado según lecturas de la báscula o alarmas del temporizador.
- **Miniweb**: servicio FastAPI que se ejecuta en el puerto 8080 o 8078 si el puerto principal está ocupado.

## Requisitos

- Python 3.11.
- Raspberry Pi OS Bookworm (aarch64) recomendado.
- Dependencias listadas en `requirements.txt` (instalación mediante `pip`).

## Instalación rápida

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python -m pytest
```

En Raspberry Pi utiliza los instaladores incluidos:

```bash
chmod +x scripts/install-*.sh
sudo bash scripts/install-1-system.sh --skip-reboot
sudo bash scripts/install-2-app.sh
```

El segundo script crea el entorno virtual como el usuario final (por defecto `pi`), instala dependencias y despliega los servicios systemd `bascula-ui` y `bascula-miniweb` (con `PYTHONPATH=/home/pi/bascula-cam`).

## Uso

Ejecuta la interfaz gráfica directamente con:

```bash
python main.py
```

La aplicación inicia en pantalla de inicio con la mascota y botones principales (Pesar, Recetas, Favoritos, Añadir, Temporizador). Desde ahí puedes acceder al modo báscula para leer peso, aplicar tara/cero y añadir alimentos mediante la cámara o introducción manual.

## Verificación

`scripts/verify-all.sh` compila bytecode, ejecuta `pytest`, lanza un smoke test de Tk y valida que el miniweb responda en 8080/8078. También comprueba que no haya fuentes declaradas como cadenas (`font="..."`) ni llamadas encadenadas a `grid()`.

## Datos y cachés

- `~/.bascula/data/favorites.json`: alimentos guardados como favoritos.
- `~/.bascula/config.yaml`: ajustes de la aplicación (báscula, cámara, miniweb, audio, etc.).
- `~/.bascula/cache/off/`: respuestas de OpenFoodFacts cacheadas.

## Licencia

Consulta el archivo `LICENSE` del repositorio original para los términos de uso.
