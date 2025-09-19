#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada robusto para la interfaz Tk de Báscula-Cam."""
from __future__ import annotations

import os
import sys
import tkinter as tk
from typing import Optional, Tuple

from bascula.services.logging import setup_logging
from bascula.ui.app import BasculaAppTk
from bascula.ui.splash import SplashScreen
from bascula.ui import recovery_ui


def _run_headless(logger) -> int:
    """Ejecuta el modo headless cuando la UI Tk no está disponible."""
    logger.warning("Tk no disponible; degradando a modo headless", exc_info=True)
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


def _ensure_display_variable() -> None:
    """Garantiza que exista DISPLAY al ejecutarse en modo kiosco."""
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":0"


def _initialise_app(
    root: tk.Tk,
    logger,
) -> Tuple[BasculaAppTk, tk.Tk]:
    """Crea la aplicación principal reutilizando la raíz recibida.

    Algunas versiones de :class:`BasculaAppTk` aceptan el parámetro ``root``
    directamente. En instalaciones más antiguas no existe dicho argumento,
    por lo que hacemos un *fallback* inyectando la raíz manualmente.
    """
    logger.info("Inicializando BasculaAppTk…")
    try:
        app = BasculaAppTk(root=root, theme="modern")  # type: ignore[call-arg]
    except TypeError as exc:
        logger.debug(
            "BasculaAppTk no acepta el parámetro 'root'; aplicando compatibilidad",
            exc_info=True,
        )
        # Fallback: forzamos que el módulo use la raíz creada en este archivo
        from bascula.ui import app as app_module

        original_factory = app_module.tk.Tk
        app_module.tk.Tk = lambda: root  # type: ignore[assignment]
        try:
            app = BasculaAppTk(theme="modern")
        finally:
            app_module.tk.Tk = original_factory
    actual_root = getattr(app, "root", root)
    return app, actual_root


def _launch_recovery_ui(logger) -> None:
    """Intenta arrancar la interfaz de recuperación como último recurso."""
    try:
        logger.warning("Iniciando modo recuperación tras fallo de arranque")
        recovery_ui.main()
    except Exception:
        logger.exception("No se pudo iniciar la interfaz de recuperación")


def main() -> int:
    """Arranque principal con control de splash screen y recuperación."""
    _ensure_display_variable()
    bascula_logger = setup_logging()
    logger = bascula_logger.getChild("main")
    logger.info("Arrancando Báscula-Cam (Tk)")

    root: Optional[tk.Tk] = None
    splash: Optional[SplashScreen] = None

    try:
        try:
            root = tk.Tk()
        except tk.TclError:
            return _run_headless(logger)
        root.withdraw()
        splash = SplashScreen(root, subtitle="Inicializando módulos…")
        try:
            splash.update_idletasks()
        except Exception:
            logger.debug("No se pudo actualizar el splash inmediatamente", exc_info=True)

        try:
            app, root = _initialise_app(root, logger)
        except Exception:
            logger.exception("Error fatal durante la inicialización de la UI principal")
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    logger.debug("Fallo al destruir la raíz tras el error", exc_info=True)
                finally:
                    root = None
            _launch_recovery_ui(logger)
            return 1
        else:
            if splash is not None:
                try:
                    splash.close()
                except Exception:
                    logger.debug("No se pudo cerrar el splash tras la carga", exc_info=True)
                splash = None

            if root is not None:
                try:
                    root.deiconify()
                except Exception:
                    logger.warning("No se pudo mostrar la ventana principal", exc_info=True)
            logger.info("UI inicializada correctamente. Entrando en mainloop().")
            app.run()
            return 0
    finally:
        if splash is not None:
            try:
                splash.close()
            except Exception:
                bascula_logger.getChild("main").debug(
                    "Fallo al cerrar el splash en limpieza final", exc_info=True
                )
        if root is not None:
            try:
                root.destroy()
            except Exception:
                bascula_logger.getChild("main").debug(
                    "Error al destruir la raíz de Tk en limpieza final", exc_info=True
                )


if __name__ == "__main__":
    sys.exit(main())
