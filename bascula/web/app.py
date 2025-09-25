"""Minimal FastAPI app exposed by the bascula-web service."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Bascula Mini-Web", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple JSON payload used by the service health checks."""

    return {"status": "ok"}


@app.get("/")
def root() -> HTMLResponse:
    """Serve a tiny HTML landing page for manual sanity checks."""

    return HTMLResponse(
        "<!doctype html><h1>Bascula Mini-Web</h1>"
        "<p>Status: OK</p><p><a href='/health'>/health</a></p>"
    )
