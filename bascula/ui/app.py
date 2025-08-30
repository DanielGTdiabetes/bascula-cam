# -*- coding: utf-8 -*-
"""
Bascula UI - Tk launcher estable con soporte de escala y modo kiosko.

Características clave:
- Respeta BASCULA_SCALING (float o "auto") aplicándolo a Tk ANTES de crear widgets.
- Modo kiosko sin parpadeos: borderless (overrideredirect) sin usar -fullscreen.
- Variables de entorno:
    BASCULA_SCALING   -> float (p.ej. "1.30") o "auto" (por defecto "auto")
    BASCULA_FULLSCREEN-> "1" o "0" (por defecto "0"). *Ojo*: puede provocar flicker.
    BASCULA_BORDERLESS-> "1" o "0" (por defecto "1") - recomendado
    BASCULA_DEBUG     -> "1" o "0" (overlay con Screen/Window/scaling)
- Teclas útiles en tiempo de ejecución:
    F11 -> alternar borderless
    Ctrl+q o Escape -> salir
"""

import os
import tkinter as tk
from tkinter import ttk


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "y", "on"):
        return True
    if val in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None else default


def _apply_tk_scaling(root: tk.Tk) -> float:
    """
    Aplica tk scaling desde BASCULA_SCALING ANTES de construir la UI.
    Devuelve el scaling efectivo.
    """
    raw = _env_str("BASCULA_SCALING", "auto").strip()
    effective = 1.0
    try:
        if raw.lower() != "auto":
            val = float(raw)
            # Tk scaling: "pixels por punto" (72 dpi base). 1.0 = 72dpi
            root.tk.call("tk", "scaling", val)
            effective = val
        else:
            # "auto": no tocar; garantizamos mínimo 1.0 para evitar tiny fonts
            cur = float(root.tk.call("tk", "scaling"))
            if cur < 1.0:
                root.tk.call("tk", "scaling", 1.0)
                effective = 1.0
            else:
                effective = cur
    except Exception as e:
        print(f"[scaling] fallo aplicando BASCULA_SCALING={raw}: {e}", flush=True)
        try:
            cur = float(root.tk.call("tk", "scaling"))
            effective = cur
        except Exception:
            effective = 1.0
    return effective


class BasculaAppTk:
    """
    Lanzador principal. Construye la ventana a pantalla completa (borderless)
    sin usar el flag -fullscreen para evitar renegociación de vídeo.
    """

    def __init__(self) -> None:
        # 1) Crear raíz Tk lo antes posible y aplicar scaling ANTES de widgets
        self.root = tk.Tk()
        self.root.title("Bascula")

        # Variables de entorno (con defaults seguros)
        self._fullscreen = _env_bool("BASCULA_FULLSCREEN", False)
        self._borderless = _env_bool("BASCULA_BORDERLESS", True)
        self._debug = _env_bool("BASCULA_DEBUG", False)

        self._scaling = _apply_tk_scaling(self.root)

        # 2) Dimensiones de pantalla y geometría de la ventana
        self.root.update_idletasks()  # asegurar medidas disponibles
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Siempre colocamos la ventana ocupando toda la superficie
        self.root.geometry(f"{sw}x{sh}+0+0")

        # 3) Modo kiosko recomendado: borderless (sin flicker de fullscreen)
        if self._borderless:
            try:
                self.root.overrideredirect(True)
            except Exception as e:
                print(f"[kiosk] overrideredirect fallo: {e}", flush=True)

        # (Opcional) Soporte de fullscreen, por si se fuerza en entorno
        # ATENCIÓN: En algunos paneles puede provocar parpadeo.
        if self._fullscreen:
            try:
                self.root.attributes("-fullscreen", True)
            except Exception as e:
                print(f"[kiosk] fullscreen fallo: {e}", flush=True)

        # 4) Configurar cierre y teclas útiles
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.bind("<Control-q>", lambda e: self._on_close())
        self.root.bind("<F11>", lambda e: self._toggle_borderless())

        # 5) Contenedor raíz de la aplicación (ajusta aquí tu UI real)
        self._build_ui()

        # 6) Overlay de depuración (Screen/Window/scaling)
        self._overlay = None
        if self._debug:
            self._overlay = self._build_overlay()
            self._tick_overlay()

    # --------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        """
        Construye la UI base. Sustituye el contenido del frame central por tu UI real.
        """
        root = self.root

        # Estilo base ttk (para que escale con tk scaling)
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Frame raíz a pantalla completa
        self.main = ttk.Frame(root, padding=0)
        self.main.pack(fill="both", expand=True)

        # Ejemplo de cabecera + contenido (placeholder)
        header = ttk.Frame(self.main)
        header.pack(side="top", fill="x")
        title = ttk.Label(
            header,
            text="Báscula – Kiosko",
            font=("TkDefaultFont", 16, "bold"),
            anchor="w",
            padding=(12, 8),
        )
        title.pack(side="left")

        self.content = ttk.Frame(self.main)
        self.content.pack(side="top", fill="both", expand=True)

        info = ttk.Label(
            self.content,
            text="Aquí va tu interfaz real.\n"
                 "La escala se controla con BASCULA_SCALING (p.ej. 1.25, 1.30...).",
            anchor="center",
            padding=20,
            justify="center",
        )
        info.pack(expand=True)

        # Forzar foco para evitar mostrar el cursor del texto en pantalla
        root.focus_force()

    def _build_overlay(self) -> tk.Label:
        """
        Crea un pequeño overlay en la esquina superior-izquierda con datos de depuración.
        """
        ov = tk.Label(
            self.root,
            text="",
            bg="#000000",
            fg="#FFFFFF",
            font=("TkDefaultFont", 9),
            justify="left",
            anchor="nw",
        )
        # Colocar arriba a la izquierda y por encima
        ov.place(x=5, y=5)
        return ov

    def _tick_overlay(self) -> None:
        """
        Actualiza el texto del overlay cada ~500ms.
        """
        if not self._overlay:
            return
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()
            cur_scal = float(self.root.tk.call("tk", "scaling"))
            txt = f"Screen: {sw}x{sh}\nWindow: {ww}x{wh}\ntk scaling: {cur_scal:.2f}"
            self._overlay.config(text=txt)
        except Exception as e:
            self._overlay.config(text=f"[overlay err] {e}")
        # Reprogramar
        self.root.after(500, self._tick_overlay)

    # --------------------------------------------------------------- Helpers

    def _toggle_borderless(self) -> None:
        """
        Alterna overrideredirect (útil para depurar si algo tapa la ventana).
        """
        self._borderless = not self._borderless
        try:
            self.root.overrideredirect(self._borderless)
        except Exception as e:
            print(f"[kiosk] toggle borderless fallo: {e}", flush=True)

    def _on_close(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

    # --------------------------------------------------------------- Run loop

    def run(self) -> None:
        """
        Inicia el bucle principal.
        """
        # Aseguramos tamaño/posición cada inicio
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        # Bucle Tk
        self.root.mainloop()
