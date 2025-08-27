import tkinter as tk
from bascula.ui.widgets import ProButton
from bascula.config.theme import THEME

class NumericKeyboard(tk.Toplevel):
    def __init__(self, parent, title="Entrada", initial="", big=False):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME.background)
        self.transient(parent); self.grab_set()
        self.resizable(False, False)
        self.result = None

        font_size = 22 if big else 18
        btn_size  = "xl" if big else "lg"
        btn_h = 2 if big else 1  # alturas en líneas de texto
        btn_w = 6

        self.var = tk.StringVar(value=str(initial))
        e = tk.Entry(self, textvariable=self.var, font=("Arial", font_size), justify="center",
                     relief="solid", bd=1)
        e.pack(fill="x", padx=18, pady=12, ipady=8); e.focus_set()

        grid = tk.Frame(self, bg=THEME.background); grid.pack(padx=12, pady=8)
        keys = [["7","8","9"],["4","5","6"],["1","2","3"],["0",".","⌫"]]
        for r,row in enumerate(keys):
            for c,k in enumerate(row):
                cmd = (lambda ch=k: self._add(ch)) if k!="⌫" else self._back
                ProButton(grid, text=k, command=cmd, size=btn_size, width=btn_w, height=btn_h)                    .grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
                grid.grid_columnconfigure(c, weight=1, uniform="kb")
            grid.grid_rowconfigure(r, weight=1, uniform="kb")

        ProButton(self, text="ENTER / ACEPTAR", command=self._ok, kind="success", size=btn_size, height=btn_h)            .pack(fill="x", padx=18, pady=(4,12))
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _add(self, ch): self.var.set(self.var.get()+ch)
    def _back(self): self.var.set(self.var.get()[:-1])
    def _ok(self): self.result = self.var.get(); self.destroy()
    def _cancel(self): self.result = None; self.destroy()
