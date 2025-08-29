#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
from python_backend.bascula.services.scale import ScaleService

# ---------- Teclado numérico ----------
class NumPadDialog(tk.Toplevel):
    def __init__(self, master, title="Calibración (g)", initial=""):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="black")
        self.result = None
        self.value = tk.StringVar(value=str(initial))

        wrap = tk.Frame(self, bg="black")
        wrap.pack(padx=10, pady=10)

        entry = tk.Entry(wrap, textvariable=self.value, font=("Arial", 36), justify="right", width=10)
        entry.grid(row=0, column=0, columnspan=3, pady=(0,10))
        entry.focus_set()

        buttons = [
            ("7",1,0),("8",1,1),("9",1,2),
            ("4",2,0),("5",2,1),("6",2,2),
            ("1",3,0),("2",3,1),("3",3,2),
            ("0",4,0),(".",4,1),("←",4,2),
        ]
        for text, r, c in buttons:
            tk.Button(wrap, text=text, font=("Arial", 26), width=3, height=1,
                      command=lambda t=text: self._press(t)).grid(row=r, column=c, padx=4, pady=4)

        bwrap = tk.Frame(wrap, bg="black")
        bwrap.grid(row=5, column=0, columnspan=3, pady=(10,0))
        tk.Button(bwrap, text="Cancelar", font=("Arial", 22), width=8, command=self._cancel).pack(side=tk.LEFT, padx=8)
        tk.Button(bwrap, text="OK", font=("Arial", 22), width=8, command=self._ok).pack(side=tk.LEFT, padx=8)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

    def _press(self, t):
        s = self.value.get()
        if t == "←":
            self.value.set(s[:-1])
        else:
            if t == "." and "." in s:
                return
            self.value.set(s + t)

    def _ok(self):
        txt = self.value.get().strip()
        try:
            v = float(txt)
            if v <= 0:
                raise ValueError
            self.result = v
            self.destroy()
        except Exception:
            messagebox.showerror("Error", "Introduce un número válido (> 0).")

    def _cancel(self):
        self.result = None
        self.destroy()

# ---------- App ----------
class ScaleApp:
    def __init__(self):
        # Backend serie
        self.scale = ScaleService(port="/dev/serial0", baud=115200)
        self.scale.start()

        # Ventana a pantalla completa
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="black")
        self.root.attributes("-fullscreen", True)   # pantalla completa
        self.root.bind("<Escape>", lambda e: self.on_close())  # ESC para salir

        # Contenedor central que se expande
        outer = tk.Frame(self.root, bg="black")
        outer.pack(fill="both", expand=True)

        # Grid para centrar elementos
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=0)
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Peso grande centrado
        self.weight_var = tk.StringVar(value="--- g")
        lbl = tk.Label(outer, textvariable=self.weight_var, font=("Arial", 96),
                       fg="white", bg="black")
        lbl.grid(row=0, column=0, sticky="nsew", pady=(40,10))

        # Estado
        self.stable_var = tk.StringVar(value="")
        lst = tk.Label(outer, textvariable=self.stable_var, font=("Arial", 28),
                       fg="#9acd32", bg="black")
        lst.grid(row=1, column=0, pady=(0,10))

        # Botonera grande centrada
        btns = tk.Frame(outer, bg="black")
        btns.grid(row=2, column=0, pady=(10,40))

        def mkbtn(text, cmd):
            return tk.Button(btns, text=text, font=("Arial", 26), width=10, height=2, command=cmd)

        mkbtn("Tara", self.do_tare).grid(row=0, column=0, padx=12, pady=12)
        mkbtn("Cal 200g", lambda: self.do_cal_preset(200)).grid(row=0, column=1, padx=12, pady=12)
        mkbtn("Cal 500g", lambda: self.do_cal_preset(500)).grid(row=0, column=2, padx=12, pady=12)
        mkbtn("Cal 1000g", lambda: self.do_cal_preset(1000)).grid(row=0, column=3, padx=12, pady=12)
        mkbtn("Calibrar…", self.do_cal_dialog).grid(row=0, column=4, padx=12, pady=12)

        # Bucle de actualización
        self.root.after(200, self.update_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---- Botones ----
    def do_tare(self):
        ok = self.scale.tare()
        messagebox.showinfo("Tara", "OK" if ok else "Fallo al enviar")

    def do_cal_preset(self, grams):
        ok = self.scale.calibrate(float(grams))
        messagebox.showinfo("Calibración", f"{'OK' if ok else 'Fallo'} C:{grams}")

    def do_cal_dialog(self):
        dlg = NumPadDialog(self.root, title="Calibración (g)")
        self.root.wait_window(dlg)
        if dlg.result is not None:
            ok = self.scale.calibrate(float(dlg.result))
            messagebox.showinfo("Calibración", f"{'OK' if ok else 'Fallo'} C:{dlg.result:g}")

    # ---- UI loop ----
    def update_loop(self):
        g = self.scale.get_weight()
        s = self.scale.is_stable()
        self.weight_var.set(f"{g:.2f} g")
        self.stable_var.set("Estable ✓" if s else "Inestable …")
        self.root.after(200, self.update_loop)

    def on_close(self):
        try:
            self.scale.stop()
        except Exception:
            pass
        self.root.destroy()

def run_app():
    app = ScaleApp()
    app.root.mainloop()

if __name__ == "__main__":
    run_app()
