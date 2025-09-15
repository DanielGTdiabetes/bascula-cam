"""Small provider‑agnostic LLM client wrapper.

This module defines :class:`LLMClient`, a very light facade used by the
``MascotBrain``.  It merely stores an API key and exposes a ``generate``
method.  Real implementations can subclass this class and override
``generate`` to call a remote provider.  The key is obtained from the
configuration or from environment variables so tests can run without
network access.
"""

from __future__ import annotations

import os
from typing import Optional


class LLMClient:
    """Minimal LLM client.

    Parameters
    ----------
    api_key:
        Optional API key.  If not provided, ``LLM_API_KEY`` from the
        environment is used.  This class does not perform any network call; it
        simply stores the key and returns empty strings when ``generate`` is
        invoked.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY") or ""

    def generate(self, prompt: str) -> str:
        """Return a completion for *prompt*.

        The base implementation is a stub returning an empty string.  Real
        integrations should override this method.
        """

        return ""


__all__ = ["LLMClient"]

