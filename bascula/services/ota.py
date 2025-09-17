"""Background Git updater used for OTA updates."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional


class OTAService:
    """Fetches and applies updates from the remote Git repository."""

    def __init__(self, repo_path: Optional[Path] = None, log_path: Optional[Path] = None) -> None:
        self.repo_path = Path(repo_path or Path(__file__).resolve().parents[3])
        self.log_path = Path(log_path or Path("/var/log/bascula/ota.log"))
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.logger = logging.getLogger("bascula.ota")
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public API
    def trigger_update(self, callback: Optional[Callable[[dict], None]] = None) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._thread = threading.Thread(target=self._worker, args=(callback,), daemon=True)
            self._thread.start()
            return True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ internals
    def _worker(self, callback: Optional[Callable[[dict], None]]) -> None:
        result = {"success": False, "version": "", "error": ""}
        self._log("Inicio de actualización OTA")
        try:
            repo = self.repo_path
            if not (repo / ".git").exists():
                raise RuntimeError(f"No es un repo git válido: {repo}")
            self._ensure_clean(repo)
            remote, branch = self._detect_remote(repo)
            self._log(f"Usando upstream {remote}/{branch}")
            subprocess.run(["git", "fetch", "--all", "--tags"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            new_rev = subprocess.check_output(["git", "rev-parse", f"{remote}/{branch}"], cwd=repo, text=True).strip()
            result["version"] = new_rev[:7]
            subprocess.run(["git", "reset", "--hard", f"{remote}/{branch}"], cwd=repo, check=True)
            req = repo / "requirements.txt"
            if req.exists():
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "-r", str(req)], cwd=repo, check=False)
            result["success"] = True
            self._log(f"Actualizado a {new_rev}")
        except Exception as exc:
            result["error"] = str(exc)
            self._log(f"OTA falló: {exc}")
        finally:
            if callable(callback):
                try:
                    callback(result)
                except Exception:
                    self.logger.exception("Callback de OTA falló")

    def _ensure_clean(self, repo: Path) -> None:
        proc = subprocess.run(["git", "diff", "--quiet"], cwd=repo)
        if proc.returncode != 0:
            raise RuntimeError("Hay cambios locales. Limpiar git antes de actualizar")

    def _detect_remote(self, repo: Path) -> tuple[str, str]:
        remotes = subprocess.check_output(["git", "remote"], cwd=repo, text=True).split()
        remote = "origin"
        if remotes:
            remote = "origin" if "origin" in remotes else remotes[0]
        branch = "main"
        try:
            show = subprocess.check_output(["git", "remote", "show", remote], cwd=repo, text=True)
            for line in show.splitlines():
                if "HEAD branch" in line:
                    branch = line.split(":", 1)[-1].strip()
                    break
        except Exception:
            pass
        return remote, branch

    def _log(self, message: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {message}\n"
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            self.logger.debug("No se pudo escribir en %s", self.log_path, exc_info=True)


__all__ = ["OTAService"]
