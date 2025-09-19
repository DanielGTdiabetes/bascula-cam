"""Entry point for the Báscula Cam kiosk UI."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

try:
    from tkinter import TclError
except Exception:  # pragma: no cover - tkinter no disponible
    TclError = Exception  # type: ignore[misc,assignment]

REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bascula.main")


def _self_check_symbols() -> None:
    missing: list[str] = []
    try:
        from bascula.ui.scaling import auto_apply_scaling  # noqa: F401
    except Exception:
        missing.append("bascula.ui.scaling.auto_apply_scaling")
    if missing:
        logging.getLogger("bascula.main").warning("Símbolos ausentes: %s", ", ".join(missing))


_self_check_symbols()


def _run_headless() -> int:
    try:
        from bascula.services.headless_main import HeadlessBascula
    except Exception:
        logger.exception("Modo headless no disponible")
        return 1
    try:
        app = HeadlessBascula()
        success = app.run()
    except Exception:
        logger.exception("Error ejecutando modo headless")
        return 1
    return 0 if success else 1


def main() -> int:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        logger.warning("DISPLAY no definido; activando modo headless")
        return _run_headless()

    try:
        from bascula.ui.app import BasculaApp

        theme = os.environ.get("BASCULA_THEME", "retro")
        app = BasculaApp(theme=theme)
        app.run()
        return 0
    except TclError:
        logger.warning("Tkinter no disponible; degradando a modo headless", exc_info=True)
        return _run_headless()
    except Exception:
        logger.exception("Fallo crítico al ejecutar la UI principal")
        try:
            from bascula.ui import recovery_ui

            recovery_ui.main()
        except Exception:
            logger.exception("No se pudo iniciar la interfaz de recuperación")
        return 1


if __name__ == "__main__":
    sys.exit(main())
