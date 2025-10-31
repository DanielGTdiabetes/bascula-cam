"""OpenSky API client with client credentials support."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from ..health import opensky_health

log = logging.getLogger(__name__)

DEFAULT_OPEN_SKY_BASE_URL = "https://opensky-network.org"
TOKEN_ENDPOINT = "/oauth/token"


@dataclass
class Token:
    access_token: str
    expires_at: float
    scope: Optional[str] = None

    @property
    def expires_in(self) -> int:
        remaining = int(self.expires_at - time.monotonic())
        return remaining if remaining > 0 else 0

    def is_valid(self, skew: int = 10) -> bool:
        return self.expires_at - time.monotonic() > skew


class OpenSkyClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or os.environ.get("OPENSKY_BASE_URL", DEFAULT_OPEN_SKY_BASE_URL)
        self._token: Optional[Token] = None

    async def ensure_token(self, client_id: str, client_secret: str) -> Dict[str, Any]:
        opensky_health.token_set = bool(client_id and client_secret)
        if not client_id or not client_secret:
            opensky_health.token_valid = False
            opensky_health.last_error = "missing_credentials"
            return {"token_valid": False, "last_error": "missing_credentials"}

        if self._token and self._token.is_valid():
            opensky_health.token_valid = True
            opensky_health.last_error = None
            opensky_health.last_check = time.time()
            opensky_health.last_ok = time.time()
            opensky_health.expires_at = self._token.expires_at
            return {
                "token_valid": True,
                "expires_in": self._token.expires_in,
                "last_error": None,
            }

        payload = {"grant_type": "client_credentials"}
        token_url = self._compose_url(TOKEN_ENDPOINT)
        auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.post(token_url, data=payload, headers=headers)
            except httpx.RequestError as exc:  # pragma: no cover - network
                error = str(exc)
                self._record_failure(error)
                return {"token_valid": False, "last_error": error}

        opensky_health.last_check = time.time()
        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            retry_after = float(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None
            opensky_health.rate_limited = True
            opensky_health.retry_after = retry_after
            error = "rate_limited"
            opensky_health.last_error = error
            opensky_health.token_valid = False
            return {"token_valid": False, "last_error": error, "retry_after": retry_after}

        opensky_health.rate_limited = False
        opensky_health.retry_after = None

        if response.status_code != 200:
            error = f"http_{response.status_code}"
            body: Any
            try:
                body = response.json()
            except json.JSONDecodeError:
                body = response.text
            log.info("OpenSky token request failed: %s (%s)", error, body)
            self._record_failure(error)
            return {"token_valid": False, "last_error": error}

        try:
            payload_json = response.json()
        except json.JSONDecodeError:
            self._record_failure("invalid_json")
            return {"token_valid": False, "last_error": "invalid_json"}

        access_token = payload_json.get("access_token")
        expires_in = payload_json.get("expires_in", 0)
        scope = payload_json.get("scope")
        if not isinstance(access_token, str) or not access_token:
            self._record_failure("missing_access_token")
            return {"token_valid": False, "last_error": "missing_access_token"}

        try:
            expires_in_val = int(expires_in)
        except Exception:
            expires_in_val = 3600

        expires_at = time.monotonic() + max(30, expires_in_val)
        self._token = Token(access_token=access_token, expires_at=expires_at, scope=scope if isinstance(scope, str) else None)
        opensky_health.token_valid = True
        opensky_health.last_ok = time.time()
        opensky_health.last_error = None
        opensky_health.expires_at = expires_at

        return {
            "token_valid": True,
            "expires_in": self._token.expires_in,
            "scope": self._token.scope,
            "last_error": None,
        }

    def _record_failure(self, error: str) -> None:
        opensky_health.token_valid = False
        opensky_health.last_error = error
        opensky_health.expires_at = None
        opensky_health.last_check = time.time()

    def _compose_url(self, path: str) -> str:
        return self._base_url.rstrip("/") + path
