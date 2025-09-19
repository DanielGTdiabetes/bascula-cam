from tkinter import Tk

from bascula.ui.lightweight_widgets import ValueLabel
from bascula.ui.theme_crt import CRT_SPACING, _assert_theme_sanity

_assert_theme_sanity()

root = Tk()
root.withdraw()
label = ValueLabel(root, text='X', padx=CRT_SPACING.padding, pady=CRT_SPACING.padding)
label.destroy()
root.destroy()
print('TK_SMOKE_OK')
