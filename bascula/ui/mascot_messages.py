# -*- coding: utf-8 -*-
from __future__ import annotations
import time, tkinter as tk
from tkinter import ttk

# Mensajes básicos. Se mantiene compatibilidad con código existente que
# espera funciones que devuelven texto, pero añadimos diccionarios con
# animaciones y acciones opcionales.
MSGS = {
  "auto_captured":     lambda grams: f"Capturado: {int(grams)} g",
  "tara_applied":      lambda: "Tara aplicada",
  "zero_applied":      lambda: "Cero aplicado",
  "scanner_ready":     lambda: "Pasa el código por el recuadro",
  "scanner_detected":  lambda: "Código detectado",
  "timer_started":     lambda s: f"Temporizador {s//60:02d}:{s%60:02d} iniciado",
  "timer_finished":    lambda: "Tiempo cumplido",
  "settings_focus":    lambda txt: txt,
  "error":             lambda txt: f"Error: {txt}",
}

# Extras: animaciones y acciones asociadas a ciertos mensajes.
MSG_ANIMS = {
  "timer_started": "bounce",
  "timer_finished": "shake",
  "scanner_detected": "wink",
}

MSG_ACTIONS = {
  # clave -> callable que se ejecutará tras mostrar el mensaje
}

def get_message(key: str, *args):
    """Devuelve (texto, acción, anim)."""
    text = MSGS[key](*args)
    return text, MSG_ACTIONS.get(key), MSG_ANIMS.get(key)

class MascotMessenger:
    def __init__(self, get_mascot_widget, get_topbar=None, theme_colors=None, scanlines: bool=False):
        """
        get_mascot_widget(): callable -> devuelve el widget Mascot actual o None si no visible
        get_topbar(): callable -> devuelve topbar (opcional) con .set_message(text) o None
        theme_colors: dict con COL_CARD, COL_TEXT, COL_ACCENT, etc.
        """
        self.get_mascot = get_mascot_widget
        self.get_topbar = get_topbar or (lambda: None)
        self.pal = theme_colors or {}
        self.scanlines = bool(scanlines)
        self._queue = []
        self._last = ("", 0.0)  # (text, ts)
        self._bubble = None
        self._anim = None
        self._visible = False

    def show(self, text:str, kind:str="info", ttl_ms:int=2200, priority:int=0, icon:str="💬", action=None, anim=None):
        if kind == "error" and ttl_ms == 2200:
            ttl_ms = 3000
        # anti-spam: no repetir exactamente el mismo texto en < 1.0 s
        now = time.time()
        if text == self._last[0] and (now - self._last[1]) < 1.0:
            return
        self._last = (text, now)
        self._queue.append((priority, now, icon, text, kind, ttl_ms, action, anim))
        self._queue.sort(key=lambda x: (-x[0], x[1]))  # prioridad desc, luego tiempo
        self._drain()

    def _drain(self):
        if self._visible or not self._queue:
            return
        _, _, icon, text, kind, ttl, action, anim = self._queue.pop(0)
        host = self.get_mascot()
        if host and hasattr(host, "winfo_toplevel"):
            if anim and hasattr(host, anim):
                try:
                    getattr(host, anim)()
                except Exception:
                    pass
            self._show_bubble(host, f"{icon} {text}", ttl, kind)
        else:
            tb = self.get_topbar()
            if tb and hasattr(tb, "set_message"):
                tb.set_message(text)
            # si hay toast disponible en la app/pantalla, se puede invocar aquí (opcional)
        if callable(action):
            try:
                action()
            except Exception:
                pass

    def _show_bubble(self, mascot_widget, text, ttl_ms, kind):
        # crea un contenedor flotante (Frame) sobre la mascota, con Canvas para el globito
        root = mascot_widget.winfo_toplevel()
        pal = self.pal
        bg = pal.get("COL_CARD", "#111827")
        fg = pal.get("COL_TEXT", "#e5e7eb")
        acc = pal.get("COL_ACCENT", "#22c55e")

        if self._bubble:
            try: self._bubble.destroy()
            except: pass
        self._bubble = tk.Frame(root, bg="", highlightthickness=0)
        self._bubble.place(in_=mascot_widget, relx=1.0, rely=0.0, x=-8, y=-8, anchor="ne")

        canvas = tk.Canvas(self._bubble, width=320, height=110, bg="", highlightthickness=0)
        canvas.pack()
        # burbuja redondeada
        r = 12
        w, h = 300, 80
        x1, y1, x2, y2 = 10, 10, 10+w, 10+h
        bubble = canvas.create_rectangle(x1, y1, x2, y2, fill=bg, outline=acc, width=2)
        # “rabito” del globo
        canvas.create_polygon(x2-30, y2, x2-50, y2, x2-40, y2+14, fill=bg, outline=acc)
        if self.scanlines:
            try:
                for y in range(y1+4, y2-4, 4):
                    canvas.create_line(x1+2, y, x2-2, y, fill=pal.get("COL_BORDER", acc))
            except Exception:
                pass

        msg = canvas.create_text(x1+16, y1+16, text=text, anchor="nw", fill=fg,
                                 font=("DejaVu Sans", 16, "bold"), width=w-32)
        # animación simple fade-in/out por alpha simulado (variar outline/fg) o por .place y opacidad si está disponible
        self._visible = True
        # cerrar tras ttl
        root.after(ttl_ms, self._hide_bubble)

    def _hide_bubble(self):
        self._visible = False
        if self._bubble:
            try: self._bubble.destroy()
            except: pass
        self._bubble = None
        # Consumir el siguiente mensaje
        self._drain()
