"""Windowing helpers for configuring the Tk kiosk mode."""
from __future__ import annotations

import logging
import os
import tkinter as tk
import weakref
from dataclasses import dataclass, field
from typing import Callable, Optional


_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass
class _KioskConfig:
    """Runtime configuration of kiosk windowing preferences."""

    strict: bool
    force: bool
    hard: bool
    debug: bool
    enforce_override: bool
    root: Optional[tk.Tk]
    logger: logging.Logger
    windows: "weakref.WeakSet[tk.Misc]" = field(default_factory=weakref.WeakSet)


_CONFIG: Optional[_KioskConfig] = None


def _env_flag(name: str) -> bool:
    """Return ``True`` when the named environment variable is truthy."""

    return (os.environ.get(name) or "").strip().lower() in _TRUE_VALUES


def _safe_apply(call: Callable[..., object], *args: object) -> None:
    """Run ``call`` with ``args`` swallowing ``tk.TclError`` exceptions."""

    try:
        call(*args)
    except tk.TclError:
        pass


def _ensure_config(window: tk.Misc | None = None) -> _KioskConfig:
    """Return the active kiosk configuration, creating a default one if needed."""

    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    logger = logging.getLogger("bascula.ui.windowing")
    strict = _env_flag("BASCULA_KIOSK_STRICT")
    force = _env_flag("BASCULA_KIOSK_FORCE")
    hard = _env_flag("BASCULA_KIOSK_HARD")
    debug = _env_flag("BASCULA_DEBUG_KIOSK") and not hard
    _CONFIG = _KioskConfig(
        strict=strict,
        force=force,
        hard=hard,
        debug=debug,
        enforce_override=strict or force or hard,
        root=window.winfo_toplevel() if window is not None else None,
        logger=logger,
    )
    return _CONFIG


def _is_fullscreen(root: tk.Misc) -> bool:
    """Best-effort detection of the current fullscreen state."""

    for attr in ("attributes", "wm_attributes"):
        getter = getattr(root, attr, None)
        if getter is None:
            continue
        try:
            value = bool(getter("-fullscreen"))
        except tk.TclError:
            continue
        else:
            return value
    return False


def _window_label(window: tk.Misc, fallback: str) -> str:
    """Build a human readable label for ``window`` for logging purposes."""

    name = getattr(window, "name", "") or ""
    try:
        if not name:
            name = window.winfo_name()
    except tk.TclError:
        name = ""
    prefix = window.__class__.__name__
    if fallback:
        prefix = fallback
    return f"{prefix}:{name}" if name else prefix


def _set_fullscreen(root: tk.Misc, enabled: bool) -> None:
    """Toggle fullscreen for ``root`` across Tk variants."""

    for attr in ("attributes", "wm_attributes"):
        setter = getattr(root, attr, None)
        if setter is None:
            continue
        _safe_apply(setter, "-fullscreen", enabled)
    if enabled:
        _safe_apply(root.state, "zoomed")
    else:
        _safe_apply(root.state, "normal")


def _set_topmost(window: tk.Misc, enabled: bool = True) -> None:
    """Apply the ``-topmost`` attribute consistently."""

    for attr in ("attributes", "wm_attributes"):
        setter = getattr(window, attr, None)
        if setter is None:
            continue
        _safe_apply(setter, "-topmost", enabled)


def _log_window_state(window: tk.Misc, label: str, *, include_fullscreen: bool = False) -> None:
    """Emit a log line summarising the window decoration state."""

    config = _ensure_config(window)
    try:
        override = bool(window.overrideredirect())
    except tk.TclError:
        override = False
    try:
        topmost = bool(window.attributes("-topmost"))
    except tk.TclError:
        topmost = False

    if include_fullscreen:
        fullscreen = _is_fullscreen(window)
        config.logger.info(
            "Kiosk %s state: fullscreen=%s overrideredirect=%s topmost=%s",
            label,
            fullscreen,
            override,
            topmost,
        )
    else:
        config.logger.info(
            "Kiosk %s state: overrideredirect=%s topmost=%s",
            label,
            override,
            topmost,
        )


def _enforce_override(window: tk.Misc, label: str, *, log_state: bool = True) -> None:
    """Ensure ``overrideredirect(True)`` sticks with a delayed reaffirmation."""

    config = _ensure_config(window)
    if not config.enforce_override:
        return

    _safe_apply(window.overrideredirect, True)

    def _finalise() -> None:
        _safe_apply(window.overrideredirect, True)
        _set_topmost(window, True)
        if log_state:
            _log_window_state(window, label, include_fullscreen=False)

    try:
        window.after(200, _finalise)
    except tk.TclError:
        _finalise()


def _bind_reapply(window: tk.Misc, label: str) -> None:
    """Bind events so decorations cannot return after mapping/unmapping."""

    def _reapply(_event: tk.Event | None = None) -> None:
        _set_topmost(window, True)
        _enforce_override(window, label, log_state=False)

    for sequence in ("<Map>", "<Visibility>", "<Expose>"):
        try:
            window.bind(sequence, _reapply, add="+")
        except tk.TclError:
            continue


def apply_kiosk_window_prefs(root: tk.Tk) -> None:
    """Configure ``root`` for the fullscreen/undecorated kiosk experience."""

    config = _ensure_config(root)
    config.root = root

    width = max(1, int(getattr(root, "winfo_screenwidth", lambda: 0)() or 0))
    height = max(1, int(getattr(root, "winfo_screenheight", lambda: 0)() or 0))
    if width and height:
        config.logger.info("Detected screen resolution: %sx%s", width, height)
        root.geometry(f"{width}x{height}+0+0")

    config.logger.info(
        "Kiosk flags: strict=%s force=%s hard=%s debug=%s",
        config.strict,
        config.force,
        config.hard,
        config.debug,
    )

    _set_fullscreen(root, True)
    _set_topmost(root, True)
    _bind_reapply(root, "root")

    def _escape_override(_event: tk.Event) -> str:
        return "break"

    try:
        root.bind_all("<Escape>", _escape_override, add="+")
    except tk.TclError:
        pass

    if config.enforce_override:
        _enforce_override(root, "root")
    else:
        _log_window_state(root, "root", include_fullscreen=True)

    def _log_root_state() -> None:
        _log_window_state(root, "root", include_fullscreen=True)

    try:
        root.after(300, _log_root_state)
    except tk.TclError:
        _log_root_state()

    if config.debug:

        def _toggle_fullscreen(_event: tk.Event | None = None) -> str:
            currently_fullscreen = _is_fullscreen(root)
            if currently_fullscreen and config.enforce_override:
                _safe_apply(root.overrideredirect, False)
            _set_fullscreen(root, not currently_fullscreen)
            if not currently_fullscreen:
                _set_topmost(root, True)
                if config.enforce_override:
                    _enforce_override(root, "root")
            else:
                _log_window_state(root, "root", include_fullscreen=True)
            config.logger.info(
                "F11 toggle processed: fullscreen=%s overrideredirect=%s",
                not currently_fullscreen,
                bool(root.overrideredirect()) if hasattr(root, "overrideredirect") else False,
            )
            return "break"

        try:
            root.bind("<F11>", _toggle_fullscreen, add="+")
        except tk.TclError:
            pass


def apply_kiosk_to_toplevel(window: tk.Toplevel) -> None:
    """Apply kiosk preferences to secondary toplevel windows."""

    if not isinstance(window, tk.Toplevel):  # Defensive guard for duck typed widgets
        return

    if getattr(window, "_bascula_kiosk_applied", False):
        return

    config = _ensure_config(window)
    if config.hard:
        config.debug = False

    setattr(window, "_bascula_kiosk_applied", True)
    try:
        config.windows.add(window)
    except Exception:
        pass

    label = _window_label(window, window.__class__.__name__)
    _set_topmost(window, True)
    _bind_reapply(window, label)

    if config.enforce_override:
        _enforce_override(window, label)
    else:
        _log_window_state(window, label, include_fullscreen=False)

    def _final_log() -> None:
        _log_window_state(window, label, include_fullscreen=False)

    try:
        window.after(300, _final_log)
    except tk.TclError:
        _final_log()

