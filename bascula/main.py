#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os

# Garantiza DISPLAY al arrancar vía systemd (kiosco X en :0)
if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
    os.environ["DISPLAY"] = ":0"

from bascula.ui.app import BasculaApp


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    app = BasculaApp(theme='modern')
    logging.getLogger(__name__).info("UI inicializada. Entrando en mainloop()")
    app.run()


if __name__ == '__main__':
    main()
