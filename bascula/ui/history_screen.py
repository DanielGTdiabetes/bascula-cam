import tkinter as tk
from pathlib import Path
import json
from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_BORDER, FS_TEXT, FS_TITLE


class HistoryScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        tk.Label(self, text='Historial', bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, 'bold')).pack(pady=8)
        self.body = tk.Frame(self, bg=COL_BG)
        self.body.pack(fill='both', expand=True)
        self._render()

    def _iter_meals(self):
        path = Path.home() / '.config' / 'bascula' / 'meals.jsonl'
        if not path.exists():
            return []
        items = []
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                items.append(json.loads(line))
            except Exception:
                pass
        return items

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        for it in self._iter_meals()[-50:]:
            row = tk.Frame(self.body, bg=COL_CARD, highlightbackground=COL_BORDER, highlightthickness=1)
            row.pack(fill='x', padx=10, pady=3)
            name = it.get('name') or 'Item'
            grams = it.get('grams') or 0
            tk.Label(row, text=f"{name}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side='left', padx=8)
            tk.Label(row, text=f"{grams:.0f} g", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side='right', padx=8)

