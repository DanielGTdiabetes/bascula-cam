#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada principal simplificado
"""
import argparse
import json
import logging
import os
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Añadir la raíz del proyecto al path
REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

log = logging.getLogger("main")

LAST_CRASH_PATH = Path("/opt/bascula/shared/userdata/last_crash.json")


def _env_flag(name: str, default=None):
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in ("1", "true", "yes", "on", "enabled", "enable"):
        return True
    if value in ("0", "false", "no", "off", "disabled", "disable"):
        return False
    return default


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Báscula Digital Pro UI")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activa modo depuración (permite Ctrl+Shift+Q para salir)",
    )
    parser.add_argument(
        "--kiosk",
        dest="kiosk",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Fuerza modo kiosko (usa --no-kiosk para desactivar)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Función principal."""
    log.info("=== BÁSCULA DIGITAL PRO - INICIO ===")

    args = parse_args(argv)
    env_kiosk = _env_flag("BASCULA_KIOSK", default=None)
    display_present = bool(os.getenv("DISPLAY"))
    if args.kiosk is None:
        if env_kiosk is None:
            kiosk_mode = display_present
        else:
            kiosk_mode = env_kiosk
    else:
        kiosk_mode = args.kiosk

    env_debug = bool(_env_flag("BASCULA_DEBUG", default=False))
    debug_mode = args.debug or env_debug

    try:
        from bascula.ui.app import BasculaAppTk

        app = BasculaAppTk(kiosk=kiosk_mode, debug=debug_mode)

        resolution = "N/A"
        if app.screen_width and app.screen_height:
            resolution = f"{app.screen_width}x{app.screen_height}"
        log.info(
            "Modo kiosko: %s | Resolución detectada: %s",
            "ON" if app.kiosk_mode else "OFF",
            resolution,
        )
        if app.headless:
            log.warning("Modo headless activo: Tk no disponible")

        app.run()

        return 0

    except ImportError as e:
        log.error(f"Error de importación: {e}")
        log.error("Verifica que todos los módulos estén instalados")
        return 1

    except KeyboardInterrupt:
        log.info("Aplicación interrumpida por usuario (Ctrl+C)")
        return 0

    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
        _record_last_crash(e)
        return 2

    finally:
        log.info("=== BÁSCULA DIGITAL PRO - FIN ===")

def _record_last_crash(exc: Exception) -> None:
    """Guarda detalles del último fallo en disco."""
    try:
        LAST_CRASH_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "versions": {
                "python": platform.python_version(),
                "app_version": os.getenv("BASCULA_APP_VERSION", "desconocida"),
                "git_rev": os.getenv("BASCULA_GIT_REV", ""),
            },
        }
        LAST_CRASH_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as write_err:
        log.error("No se pudo escribir last_crash.json: %s", write_err)


if __name__ == "__main__":
    sys.exit(main())
