"""Compatibility layer for legacy imports."""

from bascula.miniweb import (  # noqa: F401
    APP_DESCRIPTION,
    APP_NAME,
    MiniwebServer,
    app,
    create_app,
    main,
)

__all__ = [
    "APP_DESCRIPTION",
    "APP_NAME",
    "MiniwebServer",
    "app",
    "create_app",
    "main",
]
