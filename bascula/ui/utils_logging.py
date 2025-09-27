from __future__ import annotations

import logging
from typing import Any


def safe_logger(obj: Any) -> logging.Logger:
    """
    Devuelve un logger seguro para cualquier objeto de la UI.
    Prioridad: obj.logger -> obj.app.logger -> module logger.
    Nunca lanza excepción aunque no existan los atributos.
    """
    if hasattr(obj, "logger") and obj.logger:
        return obj.logger  # type: ignore[return-value]
    app = getattr(obj, "app", None)
    if app is not None and getattr(app, "logger", None):
        return app.logger  # type: ignore[return-value]
    return logging.getLogger(getattr(obj, "__module__", __name__))
