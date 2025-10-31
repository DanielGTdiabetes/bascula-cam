"""Client helpers for the AEMET integration."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

from ..health import aemet_health

log = logging.getLogger(__name__)

DEFAULT_AEMET_BASE_URL = "https://opendata.aemet.es/opendata/api"
DEFAULT_AEMET_TEST_PATH = "/map/infomet/mapa"


class AemetClient:
    """Helper to perform lightweight API checks against AEMET."""

    def __init__(self, base_url: str | None = None, test_path: str | None = None) -> None:
        self._base_url = base_url or os.environ.get("AEMET_BASE_URL", DEFAULT_AEMET_BASE_URL)
        self._test_path = test_path or os.environ.get("AEMET_TEST_PATH", DEFAULT_AEMET_TEST_PATH)

    async def validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """Perform a HEAD request that requires the API key."""

        if not api_key:
            return {"ok": False, "last_error": "missing_api_key"}

        url = self._compose_url()
        log.debug("Testing AEMET API key at %s", url)

        headers = {"api_key": api_key}
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as exc:  # pragma: no cover - network errors are logged
                error = str(exc)
                log.warning("AEMET test request failed: %s", error)
                self._update_health(ok=False, error=error)
                return {"ok": False, "last_error": error}

        if response.status_code == 200:
            self._update_health(ok=True)
            return {"ok": True, "last_error": None}

        detail = f"http_{response.status_code}"
        log.info("AEMET test responded with %s", detail)
        self._update_health(ok=False, error=detail)
        return {"ok": False, "last_error": detail}

    def _compose_url(self) -> str:
        return self._base_url.rstrip("/") + "/" + self._test_path.strip("/")

    def _update_health(self, *, ok: bool, error: Optional[str] = None) -> None:
        now = time.time()
        aemet_health.last_check = now
        if ok:
            aemet_health.last_ok = now
            aemet_health.last_error = None
        else:
            aemet_health.last_error = error
