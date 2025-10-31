"""FastAPI application for Pantalla Reloj."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import LEGACY_SECRET_PATHS, ensure_config_dir, load_config, migrate_legacy_secrets
from .health import aemet_health, opensky_health
from .integrations.aemet import AemetClient
from .integrations.opensky import OpenSkyClient
from .secrets import delete_secret, load_secret, save_secret

SECRET_FIELDS: Dict[str, str] = {
    "aemet_api_key": "AEMET API Key",
    "opensky_client_id": "OpenSky Client ID",
    "opensky_client_secret": "OpenSky Client Secret",
}

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    ensure_config_dir()
    migrate_legacy_secrets(load_secret, save_secret)

    app = FastAPI(title="Pantalla Reloj", version="1.0.0")

    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    router = APIRouter(prefix="/api")

    @router.get("/config")
    async def get_config() -> Dict[str, Any]:
        config = _load_runtime_config()
        sanitized = _sanitized_config(config)
        secrets_status = {key: bool(load_secret(key)) for key in SECRET_FIELDS}
        return {"integrations": sanitized.get("integrations", {}), "secrets": secrets_status}

    @router.get("/config/schema")
    async def get_config_schema() -> Dict[str, Any]:
        config = _sanitized_config(_load_runtime_config())
        secrets_status = {key: bool(load_secret(key)) for key in SECRET_FIELDS}
        secrets_schema = [
            {
                "key": key,
                "label": label,
                "type": "string",
                "masked": True,
                "has_value": secrets_status[key],
            }
            for key, label in SECRET_FIELDS.items()
        ]
        return {"secrets": secrets_schema, "integrations": config.get("integrations", {})}

    @router.post("/config/secret/aemet_api_key")
    async def set_aemet_secret(request: Request) -> Dict[str, Any]:
        value = await _extract_secret_value(request)
        save_secret("aemet_api_key", value)
        return {"ok": True}

    @router.post("/config/secret/opensky_client_id")
    async def set_opensky_client_id(request: Request) -> Dict[str, Any]:
        value = await _extract_secret_value(request)
        save_secret("opensky_client_id", value)
        return {"ok": True}

    @router.post("/config/secret/opensky_client_secret")
    async def set_opensky_client_secret(request: Request) -> Dict[str, Any]:
        value = await _extract_secret_value(request)
        save_secret("opensky_client_secret", value)
        return {"ok": True}

    @router.delete("/config/secret/{key}")
    async def delete_secret_endpoint(key: str) -> Dict[str, Any]:
        if key not in SECRET_FIELDS:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_secret")
        delete_secret(key)
        return {"ok": True}

    @router.get("/aemet/test")
    async def aemet_test(client: AemetClient = Depends(_aemet_client)) -> Dict[str, Any]:
        key = load_secret("aemet_api_key")
        result = await client.validate_api_key(key or "")
        return result

    @router.get("/opensky/test")
    async def opensky_test(client: OpenSkyClient = Depends(_opensky_client)) -> Dict[str, Any]:
        client_id = load_secret("opensky_client_id") or ""
        client_secret = load_secret("opensky_client_secret") or ""
        result = await client.ensure_token(client_id, client_secret)
        return result

    @router.get("/health/full")
    async def health_full() -> Dict[str, Any]:
        _load_runtime_config()
        return {
            "integrations": {
                "aemet": aemet_health.as_dict(),
                "opensky": opensky_health.as_dict(),
            },
            "secrets": {key: bool(load_secret(key)) for key in SECRET_FIELDS},
        }

    app.include_router(router)

    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse("config.html", {"request": request})

    return app


async def _extract_secret_value(request: Request) -> str:
    content_type = request.headers.get("content-type", "")
    value: Any
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_payload")
        value = payload.get("value", "")
    else:
        form = await request.form()
        value = form.get("value", "")
    if value is None:
        value = ""
    return str(value).strip()


def _sanitized_config(config: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = json.loads(json.dumps(config))
    for path in LEGACY_SECRET_PATHS.values():
        container: Any = sanitized
        for token in path[:-1]:
            if not isinstance(container, dict):
                container = None
                break
            container = container.get(token)
        if isinstance(container, dict):
            container.pop(path[-1], None)
    return sanitized


def _load_runtime_config() -> Dict[str, Any]:
    config = load_config()
    integrations = config.get("integrations")
    if isinstance(integrations, dict):
        aemet_health.enabled = bool(
            isinstance(integrations.get("aemet"), dict) and integrations["aemet"].get("enabled")
        )
        opensky_health.enabled = bool(
            isinstance(integrations.get("opensky"), dict) and integrations["opensky"].get("enabled")
        )
    return config


def _aemet_client() -> AemetClient:
    return AemetClient()


def _opensky_client() -> OpenSkyClient:
    return OpenSkyClient()
