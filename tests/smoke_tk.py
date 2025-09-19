from __future__ import annotations

from tkinter import Tk

from bascula.ui.lightweight_widgets import ValueLabel


def test_value_label_instantiation() -> None:
    root = Tk()
    root.withdraw()
    try:
        label = ValueLabel(root, text="Hola", size_key="md")
        label.update_idletasks()
    finally:
        root.destroy()
