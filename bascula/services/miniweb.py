"""Lightweight REST API exposing Báscula status and settings."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

try:  # FastAPI is optional but preferred for async handling
    from fastapi import FastAPI, HTTPException
except Exception:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore
    HTTPException = Exception  # type: ignore

try:  # uvicorn runs the ASGI app
    import uvicorn
except Exception:  # pragma: no cover - optional dependency
    uvicorn = None  # type: ignore


class MiniWebService:
    """Simple background web service exposing status and settings endpoints."""

    def __init__(self, app, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.app = app
        self.host = host
        self.port = int(port)
        self.logger = logging.getLogger("bascula.miniweb")
        self._api: Optional[FastAPI] = None  # type: ignore[assignment]
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None  # type: ignore[type-arg]

        if FastAPI is None or uvicorn is None:  # pragma: no cover - platform without deps
            self.logger.warning("FastAPI/uvicorn no disponibles; mini web desactivada")
            return

        self._api = FastAPI(title="Bascula Mini Web", version="1.0")
        self._register_routes()

    # ------------------------------------------------------------------ public API
    def start(self) -> bool:
        if self._api is None or uvicorn is None:
            return False
        if self._thread and self._thread.is_alive():
            return True

        config = uvicorn.Config(self._api, host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)

        def _runner() -> None:
            try:
                self._server.run()
            except Exception:
                self.logger.exception("Fallo en mini web")

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()
        self.logger.info("Mini web escuchando en %s:%s", self.host, self.port)
        return True

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            try:
                self._thread.join(timeout=1.5)
            except Exception:
                pass
        self._thread = None
        self._server = None

    # ------------------------------------------------------------------ internals
    def _register_routes(self) -> None:
        assert self._api is not None  # for type checkers

        @self._api.get("/health")
        async def health() -> Dict[str, Any]:  # pragma: no cover - trivial endpoint
            return {"ok": True}

        @self._api.get("/status")
        async def status() -> Dict[str, Any]:
            try:
                return {"ok": True, "data": self.app.get_status_snapshot()}
            except Exception as exc:
                self.logger.exception("Error obteniendo estado")
                raise HTTPException(status_code=500, detail=str(exc))

        @self._api.get("/settings")
        async def get_settings() -> Dict[str, Any]:
            try:
                return {"ok": True, "data": self.app.get_settings_snapshot()}
            except Exception as exc:
                self.logger.exception("Error obteniendo ajustes")
                raise HTTPException(status_code=500, detail=str(exc))

        @self._api.post("/settings")
        async def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
            payload = payload or {}
            ok, msg = self.app.update_settings_from_dict(payload)
            if not ok:
                raise HTTPException(status_code=400, detail=msg)
            return {"ok": True}


__all__ = ["MiniWebService"]
