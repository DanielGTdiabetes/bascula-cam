"""Helpers to persist UI-specific options in ``ui.toml``.

The legacy project mixes JSON configuration (``config.json``) with a
secondary TOML file that stores lightweight UI preferences.  Several
modules – the timer overlay, for instance – already read and update the
``timer_last_seconds`` entry in that file using ad-hoc helpers.  This
module centralises that logic so new features (like the optional mascot)
can reuse a single implementation for loading and saving values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path.home() / ".config" / "bascula" / "ui.toml"


def _load_toml(text: str) -> Dict[str, Any]:
    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(text)
    except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
        import tomli  # type: ignore

        return tomli.loads(text)


def load_ui_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Return the parsed UI configuration or an empty dict on failure."""

    try:
        if path.exists():
            return _load_toml(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace("\"", "\\\"")
    return f'"{escaped}"'


def dump_ui_config(data: Dict[str, Any], path: Path = CONFIG_PATH) -> None:
    """Persist ``data`` to ``ui.toml`` keeping it human friendly."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    lines = [f"{key} = {_format_value(value)}" for key, value in sorted(data.items())]
    try:
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except Exception:
        pass


def set_ui_value(key: str, value: Any, path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Convenience helper that updates one key and writes the file."""

    data = load_ui_config(path)
    data[key] = value
    dump_ui_config(data, path)
    return data
