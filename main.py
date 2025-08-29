#!/usr/bin/env python3
import tkinter as tk
from tkinter import simpledialog, messagebox
from python_backend.bascula.services.scale import ScaleService

def run_app():
    # Crear backend (UART a ESP32)
    scale = ScaleService(port="/dev/serial0", baud=115200)
    scale.start()

    # --- UI ---
    root = tk.Tk()
    root.title("Báscula Digital Pro")
    root.geometry("480x320")

    weight_var = tk.StringVar(value="--- g")
    stable_var = tk.StringVar(value="")

    label_weight = tk.Label(root, textvariable=weight_var, font=("Arial", 40))
    label_weight.pack(pady=20)

    label_stable = tk.Label(root, textvariable=stable_var, font=("Arial", 18))
    label_stable.pack()

    # Botones
    frame_btns = tk.Frame(root)
    frame_btns.pack(pady=10)

    def do_tare():
        if scale.tare():
            messagebox.showinfo("Tara", "Tara enviada")
        else:
            messagebox.showerror("Error", "No se pudo enviar tara")

    def do_calibrate():
        grams = simpledialog.askfloat("Calibración", "Peso patrón (g):")
        if grams is None:
            return
        if scale.calibrate(grams):
            messagebox.showinfo("Calibración", f"Comando enviado ({grams} g)")
        else:
            messagebox.showerror("Error", "No se pudo enviar calibración")

    btn_tare = tk.Button(frame_btns, text="Tara", font=("Arial", 16), command=do_tare)
    btn_tare.pack(side=tk.LEFT, padx=10)

    btn_cal = tk.Button(frame_btns, text="Calibrar", font=("Arial", 16), command=do_calibrate)
    btn_cal.pack(side=tk.LEFT, padx=10)

    # Actualización periódica
    def update():
        g = scale.get_weight()
        s = scale.is_stable()
        weight_var.set(f"{g:.2f} g")
        stable_var.set("Estable ✓" if s else "Inestable …")
        root.after(200, update)

    update()
    root.mainloop()

if __name__ == "__main__":
    run_app()
