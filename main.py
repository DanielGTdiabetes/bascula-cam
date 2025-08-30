#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, tkinter as tk
CUR_DIR = os.path.abspath(os.path.dirname(__file__))
if CUR_DIR not in sys.path:
    sys.path.insert(0, CUR_DIR)

from utils import load_config
from bascula.ui.app import BasculaAppTk

def main():
    cfg = load_config()
    root = tk.Tk()
    app = BasculaAppTk(root, cfg)
    root.mainloop()

if __name__ == "__main__":
    main()
