import os
import sys
from pathlib import Path
from tkinter import Tk


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bascula.ui.lightweight_widgets import ValueLabel
from bascula.ui.theme_crt import CRT_SPACING


def main() -> None:
    os.environ.setdefault("DISPLAY", ":0")
    root = Tk()
    root.withdraw()
    label = ValueLabel(root, text="X", padx=CRT_SPACING.padding, pady=CRT_SPACING.padding)
    label.destroy()
    root.destroy()
    print("TK_SMOKE_OK")


if __name__ == "__main__":
    main()
