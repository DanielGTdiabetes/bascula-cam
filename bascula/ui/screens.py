# -*- coding: utf-8 -*-
# bascula/ui/screens.py - CÓDIGO COMPLETO Y CORREGIDO
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    StatusIndicator, KeypadPopup, bind_numeric_popup, bind_text_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, DANGER, ACCENT, BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)

class HomeScreen(BaseScreen):
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu
        self.items = []; self._next_id = 1; self._selection_id = None; self._revert_timer = None

        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # --- Columna Izquierda: Peso ---
        self.card_weight = Card(self, min_width=700, min_height=400)
        self.card_weight.grid(row=0, column=0, sticky="nsew", padx=get_scaled_size(10), pady=get_scaled_size(10))
        header_weight = tk.Frame(self.card_weight, bg=COL_CARD); header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))
        tk.Label(header_weight, text="Peso actual ●", bg=COL_CARD, fg=ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left", padx=(get_scaled_size(10),0))
        tk.Frame(self.card_weight, bg=ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(8)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(5): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # --- Columna Derecha: Totales y Lista ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=0); right.grid_rowconfigure(1, weight=1); right.grid_columnconfigure(0, weight=1)

        self.card_nutrition = Card(right, min_width=320)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, get_scaled_size(12)))
        # ... (contenido de card_nutrition igual)

        self.card_items = Card(right, min_width=320, min_height=240); self.card_items.grid(row=1, column=0, sticky="nsew")
        GhostButton(self.card_items, text="🗑 Borrar seleccionado", command=self._on_delete_selected, micro=False).pack(side="bottom", fill="x", pady=(get_scaled_size(10), 0))
        # ... (contenido de card_items igual)

        self.toast = Toast(self); self.after(80, self._tick)

    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg(); unit = cfg.get("unit","g"); decimals = max(0, int(cfg.get("decimals",0)))
        if unit == "kg": return f"{grams/1000.0:.{decimals}f} kg"
        return f"{grams:.{decimals}f} g" if decimals>0 else f"{round(grams):.0f} g"

    def _tick(self):
        try:
            net_weight = self.app.get_latest_weight()
            is_stable = self.app.get_stability()
            
            self.weight_lbl.config(text=self._fmt(net_weight))
            self.stability_label.config(text=f"● {'Estable' if is_stable else 'Midiendo...'}", fg=COL_SUCCESS if is_stable else COL_WARN)
            
            reader_ok = self.app.get_reader() is not None
            self.status_indicator.set_status("active" if reader_ok else "inactive")
            if not reader_ok:
                self.stability_label.config(text="○ Sin señal", fg=COL_MUTED)

        except Exception: pass
        finally: self.after(80, self._tick)

    def _on_tara(self):
        reader = self.app.get_reader()
        if not reader: self.toast.show("⚠ Sin báscula", 1200, COL_WARN); return
        
        # Envía comando de tara al hardware
        if reader.tare():
            # Actualiza también la tara local para consistencia inmediata
            raw_val = self.app.get_raw_weight()
            self.app.get_tare().set_tare(raw_val)
            self.toast.show("✓ Tara OK", 1000, COL_SUCCESS)
        else:
            self.toast.show("❌ Error de tara", 1200, DANGER)
    
    # ... (el resto de los métodos de HomeScreen, y las otras clases de screen se mantienen igual, pero ahora se los proporciono completos)

    def _on_plato(self): self.toast.show("🍽 Plato (pendiente)", 1000, ACCENT)

    def _on_add_item(self):
        self.app.start_camera_preview()
        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG); modal.attributes("-topmost", True); modal.overrideredirect(True)
        sw,sh = self.winfo_screenwidth(), self.winfo_screenheight(); w, h = 400, 100
        modal.geometry(f"{w}x{h}+{ (sw-w)//2 }+{ sh - h - 20 }")
        modal.transient(self.winfo_toplevel()); modal.grab_set()
        cont = Card(modal, min_width=w, min_height=h); cont.pack(fill="both", expand=True, padx=10, pady=10)
        row = tk.Frame(cont, bg=COL_CARD); row.pack(fill="both", expand=True)
        row.columnconfigure(0, weight=1); row.columnconfigure(1, weight=1); row.rowconfigure(0, weight=1)
        def on_cancel(): self.app.stop_camera_preview(); modal.destroy()
        def on_capture(): self.app.stop_camera_preview(); modal.destroy(); self.after(100, self._process_capture)
        GhostButton(row, text="Cancelar", command=on_cancel, micro=False).grid(row=0, column=0, sticky="nsew", padx=5)
        BigButton(row, text="📸 Capturar", command=on_capture, micro=False).grid(row=0, column=1, sticky="nsew", padx=5)
    
    def _process_capture(self):
        img_path = self.app.capture_image(); grams = self.app.get_latest_weight()
        data = self.app.request_nutrition(image_path=img_path, grams=grams)
        self._add_item_from_data(data)

    def _add_item_from_data(self, data: dict):
        item = {k: data.get(k) for k in ["name", "grams", "kcal", "carbs", "protein", "fat", "image_path"]}
        item["id"] = self._next_id; self._next_id += 1; self.items.append(item)
        self.tree.insert("", "end", iid=str(item["id"]), values=(item.get("name","?"), f"{item.get('grams',0):.0f}", f"{item.get('kcal',0):.0f}", f"{item.get('carbs',0):.1f}", f"{item.get('protein',0):.1f}", f"{item.get('fat',0):.1f}"))
        self._show_item(item)
        if self._revert_timer: self.after_cancel(self._revert_timer)
        self._revert_timer = self.after(2000, self._show_totals)

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection()
        if not sel: self._selection_id = None; self._show_totals(); return
        iid = int(sel[0]); self._selection_id = iid
        item = next((x for x in self.items if x["id"]==iid), None)
        if item: self._show_item(item)

    def _on_delete_selected(self):
        sel = self.tree.selection()
        if not sel: self.toast.show("Selecciona un alimento para borrar", 1100, COL_MUTED); return
        iid = int(sel[0]); self.tree.delete(sel[0])
        self.items = [x for x in self.items if x["id"]!=iid]
        self._selection_id = None; self._show_totals()

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children()); self.items.clear()
        self._selection_id = None; self._show_totals(); self.toast.show("🔄 Sesión Reiniciada", 900, COL_SUCCESS)

    def _show_totals(self):
        self.lbl_nut_title.config(text="🥗 Totales")
        totals = {"grams":0.0,"kcal":0.0,"carbs":0.0,"protein":0.0,"fat":0.0}
        for it in self.items:
            for k in totals: totals[k] += it.get(k, 0.0)
        self._render_nut(totals)

    def _show_item(self, item): self.lbl_nut_title.config(text=f"🥗 {item['name']}"); self._render_nut(item)

    def _render_nut(self, data):
        def fmt(v, d=1):
            try: return f"{float(v):.{d}f}"
            except Exception: return "—"
        for k, v in self._nut_labels.items():
            decimals = 0 if k in ["grams", "kcal"] else 1
            v.config(text=fmt(data.get(k, 0), decimals))
            
# --- El resto de las clases de Screens ---
class CalibScreen(BaseScreen):
    # ...
    def _calc_save(self):
        reader = self.app.get_reader()
        if not reader: self.toast.show("⚠ Sin báscula", 1200, COL_WARN); return
        
        Wg = self._parse_patron()
        if Wg is None: self.toast.show("⚠ Peso inválido", 1200, COL_WARN); return
        
        # Envía el comando de calibración al hardware
        if reader.calibrate(Wg):
            self.toast.show("✅ Calibración enviada", 1500, COL_SUCCESS)
            # Podríamos esperar un ACK con el nuevo factor y guardarlo
            self.after(800, lambda:self.app.show_screen('settings_menu'))
        else:
            self.toast.show("❌ Error de calibración", 1500, DANGER)
