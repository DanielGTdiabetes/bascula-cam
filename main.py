#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse


def _run_modern():
    from bascula.ui.modern_app import run_app
    run_app()


def _run_screens():
    import tkinter as tk
    import os
    from bascula.config.settings import load_config
    from bascula.services.logging import get_logger
    from bascula.services.scale import ScaleService
    from bascula.services.storage import Storage
    from bascula.services.camera import CameraService
    from bascula.state import AppState
    from bascula.ui.screens import HomeScreen

    cfg = load_config()
    logger = get_logger("bascula", cfg.paths.log_dir, cfg.paths.log_file)
    state = AppState(cfg=cfg)
    base_dir = os.path.join(os.path.expanduser("~"), "bascula-cam")
    storage = Storage(base_dir=base_dir)
    scale = ScaleService(state, logger)
    camera = CameraService(state, logger, storage)

    root = tk.Tk()
    root.title("Báscula Pro (screens)")
    try:
        root.geometry("900x600")
    except Exception:
        pass
    HomeScreen(root, state, storage, logger, scale, camera).pack(fill="both", expand=True)
    root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bascula Cam")
    parser.add_argument(
        "--ui",
        choices=["modern", "screens"],
        default="modern",
        help="Selecciona la interfaz gráfica (modern|screens)",
    )
    args = parser.parse_args(argv)

    if args.ui == "screens":
        _run_screens()
    else:
        _run_modern()


if __name__ == "__main__":
    main()
