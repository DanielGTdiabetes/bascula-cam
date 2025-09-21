"""Interfaz gráfica de modo recovery para Báscula Digital Pro."""
from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext


SCRIPTS_DIR = Path("/opt/bascula/current/scripts")
LAST_CRASH_FILE = Path("/opt/bascula/shared/userdata/last_crash.json")
DEFAULT_FONT = ("DejaVu Sans", 20, "bold")
STATUS_FONT = ("DejaVu Sans", 16)
TITLE_FONT = ("DejaVu Sans", 26, "bold")
BG_COLOR = "#10141f"
BTN_COLOR = "#2563eb"
BTN_ALT_COLOR = "#10b981"
BTN_DANGER_COLOR = "#ef4444"
TEXT_COLOR = "#f8fafc"
STATUS_COLOR = "#38bdf8"
ERROR_COLOR = "#f87171"


class RecoveryApp:
    """Aplicación Tkinter para recuperación asistida."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Modo Recovery Báscula")
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1024x600")
        self.root.resizable(False, False)
        try:
            self.root.attributes("-type", "dock")
        except Exception:
            pass

        self.status_var = tk.StringVar(value="Seleccione una acción de recuperación")
        self._status_color = STATUS_COLOR
        self._buttons: list[tk.Button] = []
        self._busy = False

        self._build_layout()
        self._refresh_crash_info()

    # ------------------------------------------------------------------
    # Layout y widgets
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg=BG_COLOR)
        header.pack(fill="x", pady=(24, 12))

        tk.Label(
            header,
            text="🚑  Recuperación de Báscula",
            font=TITLE_FONT,
            fg=TEXT_COLOR,
            bg=BG_COLOR,
        ).pack()

        self.crash_label = tk.Label(
            header,
            text="Sin fallos registrados",
            font=("DejaVu Sans", 14),
            fg="#e2e8f0",
            bg=BG_COLOR,
            wraplength=900,
            justify="center",
        )
        self.crash_label.pack(pady=(8, 0))

        status_frame = tk.Frame(self.root, bg=BG_COLOR)
        status_frame.pack(fill="x", padx=40, pady=(0, 20))

        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=STATUS_FONT,
            fg=self._status_color,
            bg=BG_COLOR,
            wraplength=900,
            justify="center",
        )
        self.status_label.pack(fill="x")

        grid = tk.Frame(self.root, bg=BG_COLOR)
        grid.pack(expand=True)

        self._make_button(
            grid,
            text="Reintentar aplicación",
            command=self._retry_app,
            row=0,
            column=0,
            color=BTN_ALT_COLOR,
        )
        self._make_button(
            grid,
            text="Actualizar",
            command=self._run_update,
            row=0,
            column=1,
            color=BTN_COLOR,
        )
        self._make_button(
            grid,
            text="Configurar Wi-Fi",
            command=self._show_wifi,
            row=1,
            column=0,
            color=BTN_COLOR,
        )
        self._make_button(
            grid,
            text="Ver logs",
            command=self._show_logs,
            row=1,
            column=1,
            color=BTN_COLOR,
        )
        self._make_button(
            grid,
            text="Reiniciar",
            command=self._reboot,
            row=2,
            column=0,
            color="#f59e0b",
        )
        self._make_button(
            grid,
            text="Apagar",
            command=self._shutdown,
            row=2,
            column=1,
            color=BTN_DANGER_COLOR,
        )

        for child in grid.winfo_children():
            child.grid_configure(padx=20, pady=20, ipadx=30, ipady=30, sticky="nsew")

        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)
        for i in range(3):
            grid.grid_rowconfigure(i, weight=1)

    def _make_button(
        self,
        parent: tk.Widget,
        *,
        text: str,
        command: Callable[[], None],
        row: int,
        column: int,
        color: str,
    ) -> None:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=DEFAULT_FONT,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            bd=0,
            relief="flat",
            wraplength=320,
            justify="center",
        )
        btn.grid(row=row, column=column, sticky="nsew")
        self._buttons.append(btn)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in self._buttons:
            btn.configure(state=state)
        if not busy:
            self.status_label.configure(fg=self._status_color)

    def _refresh_crash_info(self) -> None:
        summary = "Sin fallos registrados"
        if LAST_CRASH_FILE.exists():
            try:
                data = json.loads(LAST_CRASH_FILE.read_text(encoding="utf-8"))
                timestamp = data.get("timestamp")
                message = data.get("error") or data.get("message")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        timestamp = dt.strftime("%d/%m/%Y %H:%M:%S")
                    except ValueError:
                        pass
                details = []
                if timestamp:
                    details.append(f"Último fallo: {timestamp}")
                if message:
                    details.append(f"Error: {message}")
                version_info = data.get("versions") or {}
                if isinstance(version_info, dict):
                    version_text = ", ".join(
                        f"{key} {value}" for key, value in version_info.items()
                    )
                    if version_text:
                        details.append(f"Versiones: {version_text}")
                if not details:
                    details.append("Se registró un fallo pero sin más detalles")
                summary = "\n".join(details)
            except Exception as exc:
                summary = f"No se pudo leer last_crash.json: {exc}"
        self.crash_label.configure(text=summary)

    # ------------------------------------------------------------------
    # Acciones de botones
    # ------------------------------------------------------------------
    def _retry_app(self) -> None:
        self._run_script(
            SCRIPTS_DIR / "recovery_retry.sh",
            success_message="UI principal relanzada. Cerrando recovery…",
            failure_message="No se pudo relanzar la aplicación",
            on_success=lambda: self.root.after(1500, self._close_app),
            show_output=False,
        )

    def _run_update(self) -> None:
        self._run_script(
            SCRIPTS_DIR / "recovery_update.sh",
            success_message="Actualización completada",
            failure_message="Falló la actualización",
            show_output=True,
        )

    def _show_wifi(self) -> None:
        self._run_script(
            SCRIPTS_DIR / "recovery_wifi.sh",
            success_message="Información de Wi-Fi actualizada",
            failure_message="No se pudo obtener información Wi-Fi",
            show_output=True,
        )

    def _show_logs(self) -> None:
        self._run_command(
            ["journalctl", "-u", "bascula-app.service", "-n", "300", "--no-pager"],
            title="Logs recientes de la app",
        )

    def _reboot(self) -> None:
        if messagebox.askyesno("Reiniciar", "¿Seguro que deseas reiniciar la báscula?"):
            try:
                subprocess.Popen(["systemctl", "reboot"])
                self.status_var.set("Reiniciando…")
            except Exception as exc:
                self._show_error(f"No se pudo reiniciar: {exc}")

    def _shutdown(self) -> None:
        if messagebox.askyesno("Apagar", "¿Seguro que deseas apagar la báscula?"):
            try:
                subprocess.Popen(["systemctl", "poweroff"])
                self.status_var.set("Apagando…")
            except Exception as exc:
                self._show_error(f"No se pudo apagar: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _close_app(self) -> None:
        self.root.quit()

    def _run_script(
        self,
        script_path: Path,
        *,
        success_message: str,
        failure_message: str,
        on_success: Optional[Callable[[], None]] = None,
        show_output: bool = False,
    ) -> None:
        if self._busy:
            return
        if not script_path.exists():
            self._show_error(f"No se encontró {script_path}")
            return

        self._set_busy(True)
        self.status_var.set("Ejecutando…")

        def worker() -> None:
            try:
                result = subprocess.run(
                    [str(script_path)],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                output = _merge_output(result.stdout, result.stderr)
                self.root.after(
                    0,
                    lambda: self._on_success(success_message, output, on_success, show_output),
                )
            except subprocess.CalledProcessError as exc:
                output = _merge_output(exc.stdout, exc.stderr)
                self.root.after(
                    0,
                    lambda: self._on_failure(failure_message, output),
                )
            except Exception as exc:
                self.root.after(0, lambda: self._on_failure(failure_message, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _run_command(self, command: Iterable[str], *, title: str) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.status_var.set("Recuperando información…")

        def worker() -> None:
            try:
                result = subprocess.run(
                    list(command),
                    check=True,
                    text=True,
                    capture_output=True,
                )
                output = _merge_output(result.stdout, result.stderr)
                self.root.after(0, lambda: self._show_text_window(title, output or "(sin datos)"))
            except subprocess.CalledProcessError as exc:
                output = _merge_output(exc.stdout, exc.stderr)
                self.root.after(0, lambda: self._show_error(output or "Error al obtener logs"))
            except Exception as exc:
                self.root.after(0, lambda: self._show_error(str(exc)))
            finally:
                self.root.after(0, lambda: (self._set_busy(False), self.status_var.set("Seleccione una acción de recuperación")))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(
        self,
        message: str,
        output: str,
        on_success: Optional[Callable[[], None]],
        show_output: bool,
    ) -> None:
        self._set_busy(False)
        self.status_var.set(message)
        if show_output and output:
            self._show_text_window("Resultado", output)
        if on_success:
            on_success()

    def _on_failure(self, message: str, output: str) -> None:
        self._set_busy(False)
        self.status_label.configure(fg=ERROR_COLOR)
        self.status_var.set(message)
        if output:
            self._show_text_window("Detalle del error", output)

    def _show_text_window(self, title: str, content: str) -> None:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=BG_COLOR)
        win.geometry("900x500")
        text_area = scrolledtext.ScrolledText(
            win,
            font=("DejaVu Sans Mono", 12),
            bg="#0f172a",
            fg="#e2e8f0",
            wrap="word",
        )
        text_area.insert("1.0", content)
        text_area.configure(state="disabled")
        text_area.pack(fill="both", expand=True)
        tk.Button(
            win,
            text="Cerrar",
            command=win.destroy,
            font=("DejaVu Sans", 14, "bold"),
            bg=BTN_COLOR,
            fg="white",
            bd=0,
            relief="flat",
            padx=20,
            pady=10,
        ).pack(pady=10)

    def _show_error(self, message: str) -> None:
        self.status_label.configure(fg=ERROR_COLOR)
        self.status_var.set(message)
        messagebox.showerror("Modo recovery", message, parent=self.root)

    def run(self) -> None:
        self.root.mainloop()


def _merge_output(stdout: Optional[str], stderr: Optional[str]) -> str:
    parts = []
    for chunk in (stdout, stderr):
        if chunk:
            parts.append(chunk.strip())
    return "\n".join(part for part in parts if part)


def main() -> None:
    app = RecoveryApp()
    app.run()


if __name__ == "__main__":
    main()
