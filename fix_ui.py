#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parche para arreglar la visibilidad de la lista de alimentos en la UI principal.
Ejecutar este script desde la raíz del proyecto.
"""

import os
import sys
from pathlib import Path

def apply_patch():
    # Buscar el archivo screens.py
    screens_file = Path("bascula/ui/screens.py")
    
    if not screens_file.exists():
        print(f"Error: No se encuentra {screens_file}")
        return False
    
    print(f"Leyendo {screens_file}...")
    with open(screens_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup del archivo original
    backup_file = screens_file.with_suffix('.py.backup')
    print(f"Creando backup en {backup_file}...")
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Buscar y reemplazar la sección problemática
    # El problema parece estar en cómo se configuran las columnas del grid principal
    
    # Cambio 1: Asegurar que las columnas tengan el peso correcto
    old_grid_config = """        # Layout principal: 3 columnas (peso, lista, nutrición)
        self.grid_columnconfigure(0, weight=4, minsize=get_scaled_size(360))
        self.grid_columnconfigure(1, weight=4)
        self.grid_columnconfigure(2, weight=2)"""
    
    new_grid_config = """        # Layout principal: 3 columnas (peso, lista, nutrición)
        self.grid_columnconfigure(0, weight=3, minsize=get_scaled_size(340))
        self.grid_columnconfigure(1, weight=5)  # Más espacio para la lista
        self.grid_columnconfigure(2, weight=2)"""
    
    if old_grid_config in content:
        content = content.replace(old_grid_config, new_grid_config)
        print("✓ Actualizado configuración de columnas del grid")
    
    # Cambio 2: Verificar que el panel derecho no esté sobreescribiendo
    # Cambiar la configuración del panel derecho para que no se expanda demasiado
    old_right_config = """        # Panel derecho (totales + consejos)
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)
        right.grid_rowconfigure(1, weight=1)"""
    
    new_right_config = """        # Panel derecho (totales + consejos)
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)
        right.grid_rowconfigure(0, weight=0)  # Totales no se expanden
        right.grid_rowconfigure(1, weight=0)  # Consejos altura fija"""
    
    if old_right_config in content:
        content = content.replace(old_right_config, new_right_config)
        print("✓ Actualizado configuración del panel derecho")
    
    # Cambio 3: Asegurar que la card de consejos no se expanda demasiado
    old_tips_config = """        # Hacemos más pequeña la pantalla de consejos para dejar más espacio a la lista
        tips = Card(right); tips.pack(fill="both", expand=False)"""
    
    new_tips_config = """        # Hacemos más pequeña la pantalla de consejos para dejar más espacio a la lista
        tips = Card(right); tips.pack(fill="x", expand=False)  # Solo expandir horizontalmente"""
    
    if old_tips_config in content:
        content = content.replace(old_tips_config, new_tips_config)
        print("✓ Actualizado configuración de la card de consejos")
    
    # Cambio 4: Verificar el texto de consejos
    old_tips_text = """        # Reducimos la altura del texto de consejos para que no ocupe tanto espacio
        self.tips_text = tk.Text(tips, bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT-1), height=5, wrap="word", relief="flat", state="disabled")"""
    
    new_tips_text = """        # Reducimos la altura del texto de consejos para que no ocupe tanto espacio
        self.tips_text = tk.Text(tips, bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT-1), height=6, wrap="word", relief="flat", state="disabled")"""
    
    if old_tips_text in content:
        content = content.replace(old_tips_text, new_tips_text)
        print("✓ Actualizado altura del texto de consejos")
    
    # Guardar el archivo parcheado
    print(f"Guardando cambios en {screens_file}...")
    with open(screens_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n✅ Parche aplicado exitosamente!")
    print(f"   Backup guardado en: {backup_file}")
    print("\nPara revertir los cambios, ejecuta:")
    print(f"   cp {backup_file} {screens_file}")
    
    return True

def create_diagnostic():
    """Crear un script de diagnóstico para verificar el layout"""
    diagnostic_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script de diagnóstico para verificar el layout de la UI"""

import tkinter as tk
from tkinter import ttk

def check_layout():
    root = tk.Tk()
    root.title("Diagnóstico Layout")
    root.geometry("1024x600")
    
    # Simular el layout de 3 columnas
    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=5)
    root.grid_columnconfigure(2, weight=2)
    root.grid_rowconfigure(0, weight=1)
    
    # Panel izquierdo (peso)
    left = tk.Frame(root, bg="red", relief="solid", bd=2)
    left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    tk.Label(left, text="PESO", bg="red", fg="white", font=("Arial", 20)).pack()
    
    # Panel central (lista)
    center = tk.Frame(root, bg="green", relief="solid", bd=2)
    center.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    tk.Label(center, text="LISTA DE ALIMENTOS", bg="green", fg="white", font=("Arial", 20)).pack()
    
    # Crear un Treeview de prueba
    tree = ttk.Treeview(center, columns=("item", "grams", "kcal"), show="headings", height=10)
    tree.heading("item", text="Alimento")
    tree.heading("grams", text="Peso")
    tree.heading("kcal", text="Calorías")
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Añadir algunos items de prueba
    for i in range(5):
        tree.insert("", "end", values=(f"Alimento {i+1}", f"{100*(i+1)} g", f"{50*(i+1)} kcal"))
    
    # Panel derecho (totales)
    right = tk.Frame(root, bg="blue", relief="solid", bd=2)
    right.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
    tk.Label(right, text="TOTALES", bg="blue", fg="white", font=("Arial", 20)).pack()
    
    # Info de diagnóstico
    info = tk.Text(root, height=3, wrap="word")
    info.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
    
    def update_info():
        info.delete(1.0, "end")
        info.insert(1.0, f"Tamaño ventana: {root.winfo_width()}x{root.winfo_height()}\\n")
        info.insert("end", f"Panel izq: {left.winfo_width()}px, centro: {center.winfo_width()}px, der: {right.winfo_width()}px")
        root.after(500, update_info)
    
    root.after(1000, update_info)
    root.mainloop()

if __name__ == "__main__":
    check_layout()
'''
    
    diag_file = Path("test_layout.py")
    print(f"\nCreando script de diagnóstico en {diag_file}...")
    with open(diag_file, 'w', encoding='utf-8') as f:
        f.write(diagnostic_script)
    print(f"✓ Script de diagnóstico creado: {diag_file}")
    print("  Ejecuta: python3 test_layout.py")

if __name__ == "__main__":
    print("=== Parche para arreglar la lista de alimentos ===\n")
    
    if apply_patch():
        create_diagnostic()
        print("\n⚠️  IMPORTANTE:")
        print("1. Reinicia la aplicación para ver los cambios")
        print("2. Si el problema persiste, ejecuta el script de diagnóstico")
        print("3. Si necesitas revertir, usa el archivo .backup creado")
