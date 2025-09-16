#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from bascula.ui.app import BasculaApp

def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    app = BasculaApp(theme='modern')
    logging.getLogger(__name__).info("UI inicializada. Entrando en mainloop()")
    app.run()

if __name__ == '__main__':
    main()
