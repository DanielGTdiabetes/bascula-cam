"""FastAPI mini web exposed on the local network and UI helper server."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, FastAPI
import uvicorn

from bascula import __version__

from .config.settings import Settings

APP_NAME = "Báscula Miniweb"
APP_DESCRIPTION = "Endpoints ligeros para supervisión y diagnóstico desde la LAN."

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    core_router = APIRouter(tags=["core"])

    @core_router.get("/health")
    async def health() -> Dict[str, bool]:
        """Basic liveness probe used by systemd and manual checks."""

        return {"ok": True}

    @core_router.get("/info")
    async def info() -> Dict[str, Any]:
        """Return metadata about the mini web instance."""

        host = socket.gethostname()
        host_env = os.environ.get("UVICORN_HOST", "0.0.0.0")
        port_env = os.environ.get("UVICORN_PORT", "8080")
        return {
            "app": APP_NAME,
            "description": APP_DESCRIPTION,
            "version": __version__,
            "hostname": host,
            "listen": {
                "host": host_env,
                "port": int(port_env) if port_env.isdigit() else port_env,
            },
            "docs": {
                "openapi": "/openapi.json",
                "swagger_ui": "/docs",
                "redoc": "/redoc",
            },
        }

    app.include_router(core_router)

    return app


app = create_app()


class MiniwebServer:
    """Run the FastAPI mini web in a background uvicorn thread."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        app_path: str = "bascula.miniweb:app",
    ) -> None:
        self._settings = settings
        self._app_path = app_path
        self._lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._stopped_event: Optional[threading.Event] = None

        self._startup_error: Optional[BaseException] = None
        self._started_logged = False

        self._host = "0.0.0.0"
        self._port = 8080
        self._pin = ""

    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Start the mini-web server in a daemon thread."""

        with self._lock:
            if self._thread and self._thread.is_alive():
                return True

            settings = self._settings or Settings.load()
            network = getattr(settings, "network", None)
            enabled = True if network is None else bool(getattr(network, "miniweb_enabled", True))
            if not enabled:
                log.info("Miniweb disabled via configuration; not starting")
                return False

            host = "0.0.0.0"
            port = self._coerce_port(getattr(network, "miniweb_port", 8080) if network else 8080)
            pin = str(getattr(network, "miniweb_pin", "") if network else "").strip()

            config = uvicorn.Config(
                self._app_path,
                host=host,
                port=port,
                log_level="info",
                proxy_headers=True,
                server_header=False,
            )

            server = uvicorn.Server(config)
            server.install_signal_handlers = False

            self._server = server
            self._host = host
            self._port = port
            self._pin = pin
            self._startup_error = None
            self._started_logged = False
            self._stopped_event = threading.Event()

            thread = threading.Thread(target=self._run, name="MiniwebServer", daemon=True)
            self._thread = thread
            thread.start()

        self._wait_for_start(timeout=5.0)
        if self._startup_error is not None:
            return False
        return self.is_running

    # ------------------------------------------------------------------
    def stop(self, timeout: float = 5.0) -> None:
        """Request shutdown and wait for the background thread."""

        with self._lock:
            server = self._server
            thread = self._thread
            stopped = self._stopped_event

        if not thread:
            return

        if server is not None:
            server.should_exit = True

        if stopped is not None:
            stopped.wait(timeout=timeout)

        thread.join(timeout=timeout)

        with self._lock:
            self._thread = None
            self._server = None
            self._stopped_event = None
            self._startup_error = None
            self._started_logged = False

    # ------------------------------------------------------------------
    def wait(self, timeout: float | None = None) -> bool:
        """Wait until the server thread finishes (used by CLI entry points)."""

        event = self._stopped_event
        if event is None:
            return True
        return event.wait(timeout=timeout)

    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    # ------------------------------------------------------------------
    def _run(self) -> None:
        server = self._server
        try:
            if server is None:
                return
            server.run()
        except OSError as exc:
            self._startup_error = exc
            log.error("Miniweb failed to bind to %s:%d: %s", self._host, self._port, exc)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._startup_error = exc
            log.exception("Miniweb server crashed: %s", exc)
        finally:
            event = self._stopped_event
            if event is not None:
                event.set()

    # ------------------------------------------------------------------
    def _wait_for_start(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._startup_error is not None:
                return
            server = self._server
            if server and server.started.is_set():
                self._log_started_once()
                return
            thread = self._thread
            if thread and not thread.is_alive():
                return
            time.sleep(0.05)

        server = self._server
        if server and server.started.is_set():
            self._log_started_once()

    # ------------------------------------------------------------------
    def _log_started_once(self) -> None:
        with self._lock:
            if self._started_logged:
                return
            self._started_logged = True

        if self._pin:
            log.info("Miniweb listening on %s:%d (PIN %s)", self._host, self._port, self._pin)
        else:
            log.info("Miniweb listening on %s:%d", self._host, self._port)

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_port(value: object) -> int:
        try:
            port = int(value)
        except (TypeError, ValueError):
            port = 8080
        return port if 0 < port < 65536 else 8080


def main() -> None:
    """CLI entry point used by the systemd wrapper."""

    server = MiniwebServer()
    if not server.start():
        return

    try:
        server.wait()
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        pass
    finally:
        server.stop()


__all__ = [
    "APP_DESCRIPTION",
    "APP_NAME",
    "app",
    "create_app",
    "MiniwebServer",
    "main",
]

