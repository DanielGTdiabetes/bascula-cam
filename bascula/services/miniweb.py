"""FastAPI miniweb exposed on the local network."""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import FastAPI

from bascula import __version__

APP_NAME = "Báscula Miniweb"
APP_DESCRIPTION = "Endpoints ligeros para supervisión y diagnóstico desde la LAN."


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/health", tags=["core"])
    async def health() -> Dict[str, bool]:
        """Health probe used por systemd y chequeos ligeros."""

        return {"ok": True}

    @app.get("/info", tags=["core"])
    async def info() -> Dict[str, Any]:
        """Return version metadata and runtime details."""

        return {
            "app": APP_NAME,
            "description": APP_DESCRIPTION,
            "version": __version__,
            "docs": {
                "openapi": "/openapi.json",
                "swagger_ui": "/docs",
                "redoc": "/redoc",
            },
        }

    return app


app = create_app()


def main() -> None:
    """Entry point when executed as a module."""

    import uvicorn

    host = os.environ.get("UVICORN_HOST", "0.0.0.0")
    port = int(os.environ.get("UVICORN_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
