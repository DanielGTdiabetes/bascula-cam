"""Entry point for the Báscula Cam kiosk UI."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bascula.main")


def main() -> int:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        logger.error("DISPLAY no definido; no se puede iniciar la interfaz gráfica.")
        return 1

    try:
        from bascula.ui.app import BasculaApp

        theme = os.environ.get("BASCULA_THEME", "retro")
        app = BasculaApp(theme=theme)
        app.run()
        return 0
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
