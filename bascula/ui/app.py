# -*- coding: utf-8 -*-
import os, time, threading, logging, tkinter as tk
import sys
from utils import load_config, save_config, MovingAverage
from bascula.services.audio import AudioService
from bascula.services.retention import prune_jsonl
from tare_manager import TareManager
from serial_reader import SerialReader
from bascula.ui.splash import SplashScreen
from bascula.ui.screens import HomeScreen, CalibScreen
try:
    # Usar pantallas extendidas con Wi‑Fi, API Key y Nightscout
    from bascula.ui.screens_ext import SettingsMenuScreen, WifiScreen, ApiKeyScreen, NightscoutScreen, DiabetesSettingsScreen
except Exception:
    from bascula.ui.screens import SettingsMenuScreen, WifiScreen, ApiKeyScreen  # fall back
    NightscoutScreen = None
from bascula.services.photo_manager import PhotoManager

try:
    from bascula.services.camera import CameraService
except Exception as e:
    CameraService = None
    logging.error(f"Fallo al importar CameraService: {e}")

try:
    from PIL import Image
    _PIL_OK = True
except Exception:
    _PIL_OK = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bascula")

class BasculaAppTk:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
            self.root.configure(cursor="none")
        except tk.TclError:
            log.warning("No se pudo ocultar la barra de título o el cursor.")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        self._last_weight_net = 0.0
        self.splash = SplashScreen(self.root, subtitle="Inicializando servicios…")
        self.root.update()

        self.cfg = None
        self.reader = None
        self.tare = None
        self.smoother = None
        self.camera = None       # Lazy
        self.photo_manager = None
        self.audio = None

        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    # ---------- INIT ----------
    def _init_services_bg(self):
        try:
            self._set_status("Cargando configuración")
            self.cfg = load_config()
            self._set_status("Iniciando báscula")
            self.reader = SerialReader(port=self.cfg.get("port", "/dev/serial0"), baud=self.cfg.get("baud", 115200))
            self.reader.start()
            self._set_status("Aplicando tara y suavizado")
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))
            # Retención: limpiar meals.jsonl si existe
            try:
                from pathlib import Path as _P
                logf = _P.home() / '.config' / 'bascula' / 'meals.jsonl'
                if logf.exists():
                    prune_jsonl(
                        logf,
                        max_days=int(self.cfg.get('meals_max_days', 0) or 0),
                        max_entries=int(self.cfg.get('meals_max_entries', 0) or 0),
                        max_bytes=int(self.cfg.get('meals_max_bytes', 0) or 0),
                    )
            except Exception:
                pass
            # Fotos: si no queremos guardar, limpiar staging al iniciar
            try:
                if not self.photo_manager:
                    self.photo_manager = PhotoManager(logger=log)
                if not bool(self.cfg.get('keep_photos', False)):
                    self.photo_manager.clear_all()
            except Exception as e:
                log.warning(f"PhotoManager init/clear fallo: {e}")
            # Audio service (sonido)
            self.audio = AudioService(cfg=self.cfg, logger=log)
            time.sleep(0.1)
        finally:
            self.root.after(0, self._on_services_ready)

    def _set_status(self, text: str):
        """Actualiza el texto del splash de forma segura desde hilos secundarios."""
        try:
            self.root.after(0, lambda: self.splash.set_status(text))
        except Exception:
            # Si aún no existe el splash o el root, ignorar
            pass

    def ensure_camera(self):
        """Inicializa la cámara solo cuando hace falta."""
        if self.camera and hasattr(self.camera, "available") and self.camera.available():
            return True
        if CameraService is None:
            log.error("CameraService no disponible.")
            return False
        try:
            log.info("Inicializando cámara bajo demanda…")
            self.camera = CameraService(width=800, height=480, fps=10)
            status = getattr(self.camera, "explain_status", lambda: "N/D")()
            log.info("Estado de la cámara: %s", status)
            if hasattr(self.camera, "picam") and self.camera.picam:
                if not self.photo_manager:
                    self.photo_manager = PhotoManager(logger=log)
                try:
                    self.photo_manager.attach_camera(self.camera.picam)
                    log.info("PhotoManager adjuntado.")
                except Exception as e:
                    log.warning("No se pudo adjuntar PhotoManager: %s", e)
            return self.camera.available()
        except Exception as e:
            log.error("Fallo al inicializar la cámara: %s", e)
            return False

    def _on_services_ready(self):
        try:
            log.info("Servicios listos; construyendo UI...")
            self._build_ui()
            log.info("UI construida; cerrando splash y mostrando ventana...")
        except Exception as e:
            log.error("Error al construir la UI: %s", e, exc_info=True)
        try:
            self.splash.close()
            log.info("Splash cerrado.")
        except Exception:
            pass
        try:
            self.root.deiconify()
            self.root.focus_force()
        except Exception as e:
            log.warning("No se pudo mostrar/focalizar la ventana principal: %s", e)
        # Sonido de arranque desactivado para simplificar experiencia

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        self.screens = {}
        screen_map = {
            "home": HomeScreen,
            "settingsmenu": SettingsMenuScreen,
            "calib": CalibScreen,
            "wifi": WifiScreen,
            "apikey": ApiKeyScreen,
        }
        if NightscoutScreen is not None:
            screen_map["nightscout"] = NightscoutScreen
        try:
            screen_map["diabetes"] = DiabetesSettingsScreen
        except Exception:
            pass
        for name, ScreenClass in screen_map.items():
            if name == "home":
                screen = ScreenClass(self.main, self, on_open_settings_menu=lambda: self.show_screen("settingsmenu"))
            else:
                screen = ScreenClass(self.main, self)
            self.screens[name] = screen
        self.show_screen("home")

    # ---------- LIFECYCLE ----------
    def show_screen(self, name: str):
        for screen in self.screens.values():
            if hasattr(screen, "on_hide"): screen.on_hide()
            screen.pack_forget()
        target = self.screens.get(name)
        if target:
            target.pack(fill="both", expand=True)
            if hasattr(target, "on_show"): target.on_show()

    def _on_close(self):
        log.info("Cerrando aplicación…")
        try:
            if self.camera and hasattr(self.camera, "stop"):
                self.camera.stop()
        except Exception:
            pass
        try:
            if self.reader:
                self.reader.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        finally:
            sys.exit(0)

    # ---------- ACCESSORS ----------
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    def get_audio(self): return self.audio

    # ---------- CORE ----------
    def get_latest_weight(self):
        raw = self.reader.get_latest() if self.reader else None
        if raw is not None:
            smoothed = self.smoother.add(raw)
            self._last_weight_net = self.tare.compute_net(smoothed)
        return self._last_weight_net
    
    def capture_image(self, label: str = "add_item"):
        if not self.ensure_camera():
            raise RuntimeError("Cámara no operativa para capturar.")
        path = self.camera.capture_still()
        # Garantizar JPEG en caso de flujos RGBA → convertir a RGB y regrabar
        if _PIL_OK and isinstance(path, str) and os.path.exists(path) and path.lower().endswith((".jpg", ".jpeg")):
            try:
                im = Image.open(path)
                if im.mode == "RGBA":
                    im = im.convert("RGB")
                    im.save(path, "JPEG", quality=85, optimize=True)
            except Exception as e:
                log.warning(f"No se pudo asegurar JPEG estándar: {e}")
        return path

    def delete_image(self, path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log.warning(f"No se pudo borrar imagen temporal: {e}")

    def request_nutrition(self, image_path: str, weight: float):
        """
        Llama a OpenAI (Chat Completions) con la foto y el peso y devuelve un dict:
        {name, grams, kcal, carbs, protein, fat}
        Fallback: simulación local si no hay API key o falla la llamada.
        """
        # 1) Obtener API key (ENV o ~/.config/bascula/apikey.json)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            try:
                from pathlib import Path
                ap = Path.home() / ".config" / "bascula" / "apikey.json"
                if ap.exists():
                    import json as _json
                    api_key = _json.loads(ap.read_text(encoding="utf-8")).get("openai_api_key")
            except Exception:
                api_key = None

        def _simulate():
            log.info(f"Simulando reconocimiento para {image_path} con peso {weight:.2f}g")
            time.sleep(0.4)
            return {"name": "Alimento", "grams": round(weight, 1), "kcal": round(weight * 1.2, 1),
                    "carbs": round(weight * 0.15, 1), "protein": round(weight * 0.05, 1),
                    "fat": round(weight * 0.03, 1), "simulated": True}

        if not api_key:
            return _simulate()

        try:
            import base64, json, requests
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            data_url = f"data:image/jpeg;base64,{b64}"

            system_prompt = (
                "Eres un asistente nutricional. Dado el peso en gramos y una foto del alimento o plato, "
                "responde SOLO un JSON con los campos: name (string), grams (number), kcal (number), "
                "carbs (number), protein (number), fat (number).\n"
                "Reglas: \n"
                "- Usa SIEMPRE el peso proporcionado como grams (no estimes gramos distintos).\n"
                "- Si parece un plato compuesto por varios alimentos (p.ej., arroz con pollo y verduras), "
                "  infiere proporciones razonables y calcula los macronutrientes totales para esos grams.\n"
                "- En 'name' devuelve un nombre corto y, si aplica, los componentes principales entre paréntesis, "
                "  por ejemplo: 'Arroz con pollo (arroz, pollo, verduras)'.\n"
                "- Redondea 'kcal', 'carbs', 'protein' y 'fat' a 1 decimal."
            )
            user_text = f"Peso medido: {weight:.1f} g. Identifica el alimento y estima macronutrientes para ese peso."

            payload = {
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, data=json.dumps(payload), timeout=20)
            resp.raise_for_status()
            j = resp.json()
            content = j["choices"][0]["message"]["content"].strip()
            parsed = json.loads(content)

            # Normaliza y rellena con el peso real cuando falte
            def num(x, default=0.0):
                try:
                    return float(x)
                except Exception:
                    return default
            out = {
                "name": parsed.get("name") or "Alimento",
                "grams": num(parsed.get("grams"), weight),
                "kcal": num(parsed.get("kcal"), round(weight * 1.2, 1)),
                "carbs": num(parsed.get("carbs"), round(weight * 0.15, 1)),
                "protein": num(parsed.get("protein"), round(weight * 0.05, 1)),
                "fat": num(parsed.get("fat"), round(weight * 0.03, 1)),
            }
            out["simulated"] = False
            return out
        except Exception as e:
            log.warning(f"Fallo al pedir nutrición a OpenAI: {e}")
            return _simulate()

    def run(self):
        self.root.mainloop()
