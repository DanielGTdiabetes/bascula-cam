# -*- coding: utf-8 -*-
import os, time, tkinter as tk

try:
    from bascula.services.camera import CameraService, CameraUnavailable
except Exception:
    CameraService = None
    class CameraUnavailable(Exception): pass

COL_BG = "#0a0e1a"; COL_ACC = "#6BD1FF"; COL_BTN = "#16223a"; COL_BTN_TXT = "#FFFFFF"

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula")
        try: self.root.overrideredirect(True)
        except Exception: pass
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0"); self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._overlay = None
        self._cap_var = None

        # Servicio de cámara (lazy)
        try:
            cap_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "captures"))
            os.makedirs(cap_dir, exist_ok=True)
            self.camera = CameraService(width=1024, height=600, fps=10, save_dir=cap_dir) if CameraService else None
        except Exception as e:
            print(f"[APP] Cámara no disponible: {e}"); self.camera = None

        # Pantalla mínima con botón de prueba si tu UI no se importa aquí
        self.main = tk.Frame(self.root, bg=COL_BG); self.main.pack(fill="both", expand=True)
        tk.Button(self.main, text="Añadir / Plato", command=self.capture_image, font=("DejaVu Sans", 24)).pack(pady=30)

    # ---------- OVERLAY TÁCTIL ----------
    def capture_image(self) -> str:
        if self._overlay is not None:
            return ""

        self._cap_var = tk.StringVar(value="")
        self._overlay = tk.Frame(self.root, bg=COL_BG)
        self._overlay.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # Barra superior con título (siempre visible)
        tk.Label(self._overlay, text="📷 Cámara", bg=COL_BG, fg=COL_ACC,
                 font=("DejaVu Sans", 28, "bold")).pack(anchor="w", padx=20, pady=10)

        # Área de preview
        preview_area = tk.Frame(self._overlay, bg="#000000")
        preview_area.pack(expand=True, fill="both", padx=20, pady=(0,10))

        # >>> Aseguramos que el Label se crea y se PACKea ANTES de iniciar la preview
        lbl = tk.Label(preview_area, bg="#000000", fg="#ffffff", text="Inicializando la cámara…", font=("DejaVu Sans", 18))
        lbl.pack(expand=True, fill="both")

        stop_prev = (lambda: None)
        def _start_preview():
            nonlocal stop_prev
            try:
                if getattr(self, "camera", None):
                    stop_prev = self.camera.preview_to_tk(lbl)
                else:
                    lbl.config(text="Cámara no disponible (servicio no inicializado)")
            except Exception as e:
                lbl.config(text=f"No hay preview:\n{e}")

        # Iniciamos la preview después de que la UI pinte el overlay (evita negro inicial)
        self.root.after(50, _start_preview)

        # Barra inferior con botones grandes SIEMPRE visibles
        bar = tk.Frame(self._overlay, bg=COL_BG, height=110)
        bar.pack(fill="x")

        def _close_overlay(path: str):
            try:
                stop_prev()
            except Exception:
                pass
            self._cap_var.set(path)
            try: self._overlay.destroy()
            except Exception: pass
            self._overlay = None

        def _cancel():
            p = f"/tmp/capture_{int(time.time())}.jpg"
            try:
                with open(p, "wb") as f: f.write(b"")
            except Exception: pass
            _close_overlay(p)

        def _shot():
            p = None
            try:
                p = self.camera.capture_still() if getattr(self, "camera", None) else None
            except Exception as e:
                print(f"[APP] Error captura: {e}")
            if not p:
                p = f"/tmp/capture_{int(time.time())}.jpg"
                try:
                    with open(p, "wb") as f: f.write(b"")
                except Exception: pass
            _close_overlay(p)

        btn_cancel = tk.Button(bar, text="Cancelar", command=_cancel,
                               bg=COL_BTN, fg=COL_BTN_TXT, activebackground="#223456",
                               font=("DejaVu Sans", 28), padx=40, pady=20)
        btn_shoot  = tk.Button(bar, text="📸 Capturar", command=_shot,
                               bg="#2d7d46", fg=COL_BTN_TXT, activebackground="#2f9c56",
                               font=("DejaVu Sans", 28), padx=40, pady=20)
        btn_cancel.pack(side="left", padx=20, pady=10)
        btn_shoot.pack(side="right", padx=20, pady=10)

        # Esperar hasta que el usuario pulse algo (el mainloop sigue procesando after/preview)
        self.root.wait_variable(self._cap_var)
        return self._cap_var.get()

    def _on_close(self):
        try:
            if getattr(self, "camera", None):
                try: self.camera.stop()
                except Exception: pass
        except Exception: pass
        try: self.root.quit(); self.root.destroy()
        except Exception: pass

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                if getattr(self, "camera", None): self.camera.stop()
            except Exception: pass

if __name__ == "__main__":
    BasculaAppTk().run()
