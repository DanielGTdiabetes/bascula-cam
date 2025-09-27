"""Reusable Tk widgets for the modern UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "accent": "#0050d0",
    "accent_hover": "#1b6dff",
    "text": "#1f2430",
    "muted": "#6b7180",
}

FONT_LG = ("DejaVu Sans", 18, "bold")
FONT_MD = ("DejaVu Sans", 14, "bold")
FONT_SM = ("DejaVu Sans", 12)


class PrimaryButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            bg=PALETTE["accent"],
            fg="white",
            activebackground=PALETTE["accent_hover"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=22,
            pady=18,
            font=FONT_LG,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
            **kwargs,
        )
        self.bind("<Enter>", lambda _e: self.configure(bg=PALETTE["accent_hover"]))
        self.bind("<Leave>", lambda _e: self.configure(bg=PALETTE["accent"]))


class ToolbarButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            activebackground=PALETTE["panel"],
            activeforeground=PALETTE["accent_hover"],
            font=FONT_MD,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            takefocus=0,
            **kwargs,
        )


class WeightDisplay(tk.Label):
    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(
            master,
            text="--",
            font=("DejaVu Sans", 120, "bold"),
            fg=PALETTE["text"],
            bg=PALETTE["panel"],
            anchor="center",
            **kwargs,
        )

    def update_value(self, value: float, unit: str) -> None:
        self.configure(text=f"{value:.0f} {unit}")


class TotalsTable(ttk.Treeview):
    def __init__(self, master: tk.Misc) -> None:
        columns = ("name", "weight", "carbs", "protein", "fat", "gi")
        super().__init__(
            master,
            columns=columns,
            show="headings",
            height=6,
        )
        headings = {
            "name": "Alimento",
            "weight": "Peso (g)",
            "carbs": "HC (g)",
            "protein": "Prot (g)",
            "fat": "Grasa (g)",
            "gi": "IG",
        }
        for cid, label in headings.items():
            self.heading(cid, text=label)
            self.column(cid, width=120, anchor="center")
        self.column("name", width=200, anchor="w")


class KeyboardPopup(tk.Toplevel):
    """Simple on-screen keyboard supporting text and numeric layouts."""

    _TEXT_LAYOUT: tuple[tuple[str, ...], ...] = (
        tuple("1234567890"),
        tuple("qwertyuiop"),
        tuple("asdfghjklñ"),
        ("MAYÚS", "z", "x", "c", "v", "b", "n", "m", "⌫"),
        ("@", "#", "$", "%", "&", "/", "+", "-", "_"),
        (".", ",", ";", ":", "\"", "'", "(", ")", "?", "!"),
    )

    _NUMERIC_LAYOUT: tuple[tuple[str, ...], ...] = (
        ("1", "2", "3"),
        ("4", "5", "6"),
        ("7", "8", "9"),
        ("±", "0", ".", "⌫"),
    )

    def __init__(self, master: tk.Misc, target: tk.Entry, mode: str = "text") -> None:
        super().__init__(master)
        self.title("Teclado")
        self.configure(bg=PALETTE["panel"], padx=12, pady=12)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.target = target
        self.mode = mode
        self.shift = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(10, self.focus_force)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        layout = self._TEXT_LAYOUT if self.mode != "numeric" else self._NUMERIC_LAYOUT
        for r_index, row in enumerate(layout):
            frame = tk.Frame(self, bg=PALETTE["panel"])
            frame.grid(row=r_index, column=0, pady=4)
            for key in row:
                self._create_key(frame, key).pack(side="left", padx=3)

        controls = tk.Frame(self, bg=PALETTE["panel"])
        controls.grid(row=len(layout), column=0, pady=(8, 0))
        if self.mode != "numeric":
            tk.Button(
                controls,
                text="Espacio",
                command=lambda: self._insert(" "),
                width=12,
                bg=PALETTE["bg"],
                fg=PALETTE["text"],
            ).pack(side="left", padx=4)
        tk.Button(
            controls,
            text="Aceptar",
            command=self._accept,
            width=10,
            bg=PALETTE["accent"],
            fg="white",
            activebackground=PALETTE["accent_hover"],
            activeforeground="white",
        ).pack(side="left", padx=4)
        tk.Button(
            controls,
            text="Cerrar",
            command=self.destroy,
            width=10,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
        ).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    def _create_key(self, master: tk.Misc, key: str) -> tk.Button:
        return tk.Button(
            master,
            text=key,
            width=4,
            height=2,
            command=lambda k=key: self._on_key_press(k),
            bg=PALETTE["bg"],
            fg=PALETTE["text"],
            relief="raised",
        )

    # ------------------------------------------------------------------
    def _on_key_press(self, key: str) -> None:
        if key == "⌫":
            if self._delete_selection():
                return
            index = int(self.target.index("insert"))
            if index > 0:
                self.target.delete(index - 1)
            return
        if key == "MAYÚS":
            self.shift = not self.shift
            self._refresh_case()
            return
        if key == "±":
            value = self.target.get()
            if value.startswith("-"):
                self.target.delete(0, 1)
            else:
                self.target.insert(0, "-")
            return
        self._insert(key)

    # ------------------------------------------------------------------
    def _refresh_case(self) -> None:
        for child in self.winfo_children():
            for sub in child.winfo_children():
                text = getattr(sub, "cget", lambda _k: None)("text")
                if not text or len(text) != 1 or not text.isalpha():
                    continue
                sub.configure(text=text.upper() if self.shift else text.lower())

    # ------------------------------------------------------------------
    def _insert(self, value: str) -> None:
        if self.shift and value.isalpha():
            value = value.upper()
        if getattr(self.target, "selection_present", None) and self.target.selection_present():
            self.target.delete("sel.first", "sel.last")
        self.target.insert("insert", value)
        self.target.focus_set()

    # ------------------------------------------------------------------
    def _accept(self) -> None:
        self.target.focus_set()
        self.destroy()

    # ------------------------------------------------------------------
    def _delete_selection(self) -> bool:
        if getattr(self.target, "selection_present", None) and self.target.selection_present():
            self.target.delete("sel.first", "sel.last")
            return True
        return False


__all__ = [
    "PrimaryButton",
    "ToolbarButton",
    "WeightDisplay",
    "TotalsTable",
    "KeyboardPopup",
    "PALETTE",
]
