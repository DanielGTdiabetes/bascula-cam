"""Recorrido rápido de pantallas para detectar errores de importación."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from contextlib import suppress
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.ui.app import BasculaAppTk

LOG = logging.getLogger("bascula.tools.smoke_nav")
logging.basicConfig(level=logging.INFO, format="[smoke_nav] %(message)s")


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - entorno sin X
        LOG.warning("Tk no disponible: %s", exc)
        return 0

    root.withdraw()
    app = None
    try:
        app = BasculaAppTk(root=root)
    except Exception as exc:  # pragma: no cover - diagnóstico
        LOG.error("Fallo inicializando la app: %s", exc)
        with suppress(Exception):
            root.destroy()
        return 1

    targets = [
        "home",
        "scale",
        "settings",
        "history",
        "focus",
        "diabetes",
        "nightscout",
        "wifi",
        "apikey",
    ]

    for name in targets:
        if name not in app._factories:  # type: ignore[attr-defined]
            LOG.info("Pantalla %s no registrada (opcional)", name)
            continue
        try:
            app.show_screen(name)
            app.root.update_idletasks()
            app.root.update()
        except Exception as exc:  # pragma: no cover - diagnóstico
            LOG.error("Error mostrando %s: %s", name, exc)
        else:
            LOG.info("Pantalla %s OK", name)

    with suppress(Exception):
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
