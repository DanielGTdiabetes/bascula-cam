"""Integration health state tracking."""

from __future__ import annotations

import dataclasses
import time
from typing import Any, Dict, Optional


@dataclasses.dataclass
class AemetHealth:
    enabled: bool = False
    last_check: Optional[float] = None
    last_ok: Optional[float] = None
    last_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "last_check": self.last_check,
            "last_ok": self.last_ok,
            "last_error": self.last_error,
        }


@dataclasses.dataclass
class OpenSkyHealth:
    enabled: bool = False
    last_check: Optional[float] = None
    last_ok: Optional[float] = None
    token_set: bool = False
    token_valid: bool = False
    expires_at: Optional[float] = None
    last_error: Optional[str] = None
    rate_limited: bool = False
    retry_after: Optional[float] = None

    def expires_in(self) -> Optional[int]:
        if not self.expires_at:
            return None
        remaining = int(self.expires_at - time.monotonic())
        return remaining if remaining > 0 else 0

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "enabled": self.enabled,
            "last_check": self.last_check,
            "last_ok": self.last_ok,
            "token_set": self.token_set,
            "token_valid": self.token_valid,
            "expires_in": self.expires_in(),
            "last_error": self.last_error,
            "rate_limited": self.rate_limited,
        }
        if self.retry_after is not None:
            payload["retry_after"] = self.retry_after
        return payload


aemet_health = AemetHealth()
opensky_health = OpenSkyHealth()


def reset_health() -> None:
    global aemet_health, opensky_health
    aemet_health = AemetHealth()
    opensky_health = OpenSkyHealth()
