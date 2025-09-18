#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pantalla de recuperación minimalista.

Se muestra cuando la actualización falla o la UI principal no puede
iniciarse. Usa la paleta de `bascula.ui.widgets` para mantener un estilo
consistente. Permite intentar una actualización y reiniciar el sistema.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk

from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_ACCENT, FS_TITLE, FS_TEXT


OTA_STATE: dict[str, object] = {
    "running": False,
    "proc": None,
    "queue": None,
    "buffer": [],
}


def _repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


class RecoveryUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.configure(bg=COL_BG)
        try:
            self.root.attributes("-fullscreen", True)
        except Exception:
            self.root.geometry("960x600")

        container = tk.Frame(self.root, bg=COL_CARD)
        container.pack(expand=True, fill="both", padx=40, pady=40)

        tk.Label(
            container,
            text="Modo recuperación",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", max(FS_TITLE, 24), "bold"),
        ).pack(pady=(12, 6))

        tk.Label(
            container,
            text=(
                "La interfaz principal no se pudo iniciar.\n"
                "Puedes intentar una actualización OTA o reintentar el arranque."
            ),
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT, 14)),
            justify="center",
        ).pack(pady=(0, 12))

        self.status = tk.StringVar(value="Listo")
        tk.Label(
            container,
            textvariable=self.status,
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT - 2, 12)),
            justify="center",
        ).pack(pady=(0, 16))

        buttons = tk.Frame(container, bg=COL_CARD)
        buttons.pack(pady=20)

        tk.Button(
            buttons,
            text="Reintentar UI",
            command=self._retry,
            bg=COL_ACCENT,
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        ).pack(side="left", padx=8)

        self.ota_button = tk.Button(
            buttons,
            text="Actualización OTA",
            command=self._open_ota_dialog,
            bg="#2563eb",
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        )
        self.ota_button.pack(side="left", padx=8)

        tk.Button(
            buttons,
            text="Salir",
            command=self.root.destroy,
            bg="#6b7280",
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        ).pack(side="left", padx=8)

        self.repo = _repo_root(Path(__file__).resolve())
        self._ota_dialog: tk.Toplevel | None = None
        self._ota_text: tk.Text | None = None
        self._ota_mode = tk.StringVar(value="stash")
        self._ota_controls: dict[str, list[tk.Widget] | tk.Widget] = {}
        self._ota_watcher_id: str | None = None
        if self._ota_is_running() or isinstance(OTA_STATE.get("queue"), queue.Queue):
            self._ensure_ota_watcher()

    # ------------------------------------------------------------------ actions
    def _retry(self) -> None:
        self.status.set("Relanzando interfaz…")
        try:
            self.root.destroy()
            os.execl(sys.executable, sys.executable, "main.py")
        except Exception as exc:
            self.status.set(f"Error al relanzar: {exc}")

    def _open_ota_dialog(self) -> None:
        if self._ota_dialog and self._ota_dialog.winfo_exists():
            self._ota_dialog.lift()
            return

        dialog = tk.Toplevel(self.root)
        self._ota_dialog = dialog
        dialog.title("Actualización OTA")
        dialog.configure(bg=COL_CARD)
        dialog.geometry("720x420")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", self._on_ota_dialog_close)
        dialog.bind("<Destroy>", self._on_ota_dialog_destroy)

        tk.Label(
            dialog,
            text="Selecciona el modo de actualización",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT, 14), "bold"),
        ).pack(pady=(18, 6))

        options = tk.Frame(dialog, bg=COL_CARD)
        options.pack(pady=(0, 12))

        keep = tk.Radiobutton(
            options,
            text="Conservar mis cambios (stash)",
            variable=self._ota_mode,
            value="stash",
            bg=COL_CARD,
            fg=COL_TEXT,
            selectcolor=COL_ACCENT,
            font=("DejaVu Sans", max(FS_TEXT - 1, 12)),
            anchor="w",
            pady=4,
        )
        keep.pack(fill="x", padx=24, pady=2)

        force = tk.Radiobutton(
            options,
            text="Forzar actualización (descartar cambios)",
            variable=self._ota_mode,
            value="force",
            bg=COL_CARD,
            fg=COL_TEXT,
            selectcolor=COL_ACCENT,
            font=("DejaVu Sans", max(FS_TEXT - 1, 12)),
            anchor="w",
            pady=4,
        )
        force.pack(fill="x", padx=24, pady=2)

        text_frame = tk.Frame(dialog, bg=COL_CARD)
        text_frame.pack(fill="both", expand=True, padx=18, pady=(6, 12))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        output = tk.Text(
            text_frame,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            font=("DejaVu Sans Mono", max(FS_TEXT - 4, 10)),
            wrap="word",
            state="disabled",
        )
        output.pack(fill="both", expand=True)
        output.configure(yscrollcommand=scrollbar.set)
        scrollbar.configure(command=output.yview)

        controls = tk.Frame(dialog, bg=COL_CARD)
        controls.pack(pady=(0, 16))

        start_btn = tk.Button(
            controls,
            text="Iniciar actualización",
            command=self._start_ota,
            bg=COL_ACCENT,
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
        )
        start_btn.pack(side="left", padx=8)

        close_btn = tk.Button(
            controls,
            text="Cerrar",
            command=self._on_ota_dialog_close,
            bg="#6b7280",
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
        )
        close_btn.pack(side="left", padx=8)

        self._ota_text = output
        self._ota_controls = {
            "start": start_btn,
            "close": close_btn,
            "radios": [keep, force],
        }
        buffer = OTA_STATE.get("buffer")
        if not isinstance(buffer, list) or not buffer:
            OTA_STATE["buffer"] = []
            self._append_ota_log("Listo para iniciar OTA\n")
        else:
            self._render_ota_buffer()

        if self._ota_is_running():
            self.status.set("Actualización OTA en curso…")

        self._update_ota_controls()
        self._ensure_ota_watcher()

    def _append_ota_log(self, message: str) -> None:
        text = str(message)
        buffer = OTA_STATE.get("buffer")
        if not isinstance(buffer, list):
            buffer = []
            OTA_STATE["buffer"] = buffer
        buffer.append(text)
        if not self._ota_text or not self._ota_text.winfo_exists():
            return
        self._ota_text.configure(state="normal")
        self._ota_text.insert("end", text)
        self._ota_text.see("end")
        self._ota_text.configure(state="disabled")

    def _render_ota_buffer(self) -> None:
        if not self._ota_text or not self._ota_text.winfo_exists():
            return
        buffer = OTA_STATE.get("buffer")
        if not isinstance(buffer, list):
            return
        self._ota_text.configure(state="normal")
        self._ota_text.delete("1.0", "end")
        self._ota_text.insert("end", "".join(str(entry) for entry in buffer))
        self._ota_text.see("end")
        self._ota_text.configure(state="disabled")

    def _watch_ota_queue(self) -> None:
        self._ota_watcher_id = None
        queue_ref = OTA_STATE.get("queue")
        running = self._ota_is_running()
        if isinstance(queue_ref, queue.Queue):
            try:
                while True:
                    kind, payload = queue_ref.get_nowait()
                    if kind == "line":
                        line = str(payload)
                        if not line.endswith("\n"):
                            line += "\n"
                        self._append_ota_log(line)
                    elif kind == "result":
                        info = payload if isinstance(payload, dict) else {}
                        success = bool(info.get("success"))
                        message = str(info.get("message", "")) if info else ""
                        self._handle_ota_result(success, message)
            except queue.Empty:
                pass

        needs_more = running
        if isinstance(queue_ref, queue.Queue):
            if queue_ref.empty() and not running:
                OTA_STATE["queue"] = None
            elif not queue_ref.empty():
                needs_more = True

        if needs_more:
            self._ensure_ota_watcher()

    def _update_ota_controls(self) -> None:
        start = self._ota_controls.get("start")
        close = self._ota_controls.get("close")
        radios = self._ota_controls.get("radios", [])
        running = self._ota_is_running()
        start_state = tk.NORMAL if not running else tk.DISABLED
        close_state = tk.NORMAL if not running else tk.DISABLED
        if isinstance(start, tk.Widget):
            start.configure(state=start_state)
        if isinstance(close, tk.Widget):
            close.configure(state=close_state)
        if isinstance(radios, list):
            for widget in radios:
                widget.configure(state=start_state)

    def _ota_is_running(self) -> bool:
        return bool(OTA_STATE.get("running"))

    def _ensure_ota_watcher(self) -> None:
        if self._ota_watcher_id is not None:
            return
        self._ota_watcher_id = self.root.after(200, self._watch_ota_queue)

    def _on_ota_dialog_close(self) -> None:
        if not self._ota_dialog or not self._ota_dialog.winfo_exists():
            return
        if self._ota_is_running():
            self.status.set("Actualización OTA en curso…")
            last_message = "Actualización en curso; espera a que finalice.\n"
            buffer = OTA_STATE.get("buffer")
            if isinstance(buffer, list):
                if not buffer or buffer[-1] != last_message:
                    self._append_ota_log(last_message)
            return
        self._ota_dialog.destroy()

    def _on_ota_dialog_destroy(self, _event: tk.Event) -> None:
        self._ota_dialog = None
        self._ota_text = None
        self._ota_controls = {}

    def _start_ota(self) -> None:
        if self._ota_is_running():
            self._append_ota_log("Ya hay una actualización en curso\n")
            return
        script = self.repo / "scripts" / "ota.sh"
        if not script.exists():
            self._append_ota_log("Script OTA no encontrado\n")
            return
        OTA_STATE["running"] = True
        OTA_STATE["buffer"] = []
        self._render_ota_buffer()
        queue_ref: queue.Queue[tuple[str, object]] = queue.Queue()
        OTA_STATE["queue"] = queue_ref
        self._ensure_ota_watcher()
        self._update_ota_controls()
        self.status.set("Ejecutando actualización OTA…")
        mode = self._ota_mode.get() or "stash"
        cmd = [str(script)]
        if mode == "force":
            cmd.append("--force")
        else:
            cmd.append("--stash")

        self._append_ota_log(f"Comando: {' '.join(cmd)}\n")

        def worker() -> None:
            success = False
            message = ""
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                OTA_STATE["proc"] = process
            except Exception as exc:  # pragma: no cover - defensive
                queue_ref.put(("line", f"Error al iniciar OTA: {exc}"))
                queue_ref.put(("result", {"success": False, "message": str(exc)}))
                return

            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.rstrip("\n")
                queue_ref.put(("line", line))
                if line.startswith("OTA_OK"):
                    success = True
                    message = line
                elif line.startswith("OTA_FAIL:"):
                    success = False
                    message = line
            process.wait()
            if process.returncode == 0 and success:
                queue_ref.put(("result", {"success": True, "message": message}))
            else:
                if not message:
                    message = f"OTA_FAIL:Proceso terminó con código {process.returncode}"
                    queue_ref.put(("line", message))
                queue_ref.put(("result", {"success": False, "message": message}))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_ota_result(self, success: bool, message: str) -> None:
        OTA_STATE["running"] = False
        OTA_STATE["proc"] = None
        self._update_ota_controls()
        if success:
            suffix = f" ({message})" if message else ""
            self.status.set(f"Actualizado; reiniciando UI…{suffix}")
            self._append_ota_log("Actualización finalizada correctamente\n")
            self._restart_ui()
        else:
            detail = message or "ver registros"
            self.status.set(f"OTA falló: {detail}")
            if message:
                self._append_ota_log(message + "\n")
            else:
                self._append_ota_log("OTA falló\n")

    def _restart_ui(self) -> None:
        if self._ota_dialog and self._ota_dialog.winfo_exists():
            self._ota_dialog.after(1500, self._ota_dialog.destroy)

        def _close() -> None:
            try:
                self.root.destroy()
            except Exception:
                pass

        if self._launched_by_systemd():
            self._append_ota_log("Reiniciando servicio bascula-ui\n")
            cmd = ["systemctl", "restart", "bascula-ui"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.stdout:
                self._append_ota_log(result.stdout)
            if result.returncode != 0:
                self._append_ota_log("No se pudo reiniciar bascula-ui automáticamente\n")
            self.root.after(2000, _close)
        else:
            launcher = self.repo / "scripts" / "safe_run.sh"
            if launcher.exists():
                self._append_ota_log("Lanzando interfaz principal\n")
                try:
                    subprocess.Popen([str(launcher)])
                except Exception as exc:
                    self._append_ota_log(f"No se pudo lanzar safe_run.sh: {exc}\n")
            self.root.after(2000, _close)

    def _launched_by_systemd(self) -> bool:
        if os.environ.get("INVOCATION_ID") or os.environ.get("JOURNAL_STREAM"):
            return True
        return Path("/run/systemd/system").exists()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    ui = RecoveryUI()
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
