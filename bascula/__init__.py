"""Top level package for the Bascula application stack."""

from importlib import metadata as _metadata

try:  # pragma: no cover - metadata only available when installed
    __version__ = _metadata.version("bascula")
except _metadata.PackageNotFoundError:  # pragma: no cover - editable installs
    __version__ = "0.0.0"

from . import utils  # noqa: F401 - re-export for backwards compatibility

__all__ = ["__version__", "utils"]
