"""Animated robot mascot widget used across the Báscula UI."""

from __future__ import annotations

import logging
import math
import os
import random
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import tkinter as tk

_LOG = logging.getLogger(__name__)

_ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "mascota"
_GENERATED_DIR = _ASSET_ROOT / "_gen"

_VALID_STATES = {"idle", "listen", "think", "error", "sleep"}
_STATE_TO_BASE = {
    "idle": "robot_idle",
    "listen": "robot_listen",
    "think": "robot_think",
    "error": "robot_error",
    "sleep": "robot_sleep",
}
_STATE_HIGHLIGHT = {
    "listen": "#2ecc71",
    "think": "#1abc9c",
    "error": "#e74c3c",
    "sleep": "#16a085",
}


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_compact_mode() -> bool:
    """Return ``True`` when the environment requests the compact avatar."""

    return _is_true(os.getenv("BASCULA_MASCOT_COMPACT", "0"))


class MascotWidget(tk.Frame):
    """Simple animated Tk widget that renders the green robot mascot."""

    def __init__(self, parent: tk.Misc, *, max_width: int = 280, **kwargs) -> None:
        bg = kwargs.pop("bg", None)
        if not bg:
            try:
                bg = str(parent.cget("bg")) or "#111111"
            except Exception:
                bg = "#111111"
        super().__init__(parent, bg=bg, **kwargs)
        try:
            self.configure(highlightthickness=0)
        except tk.TclError:
            pass

        self._max_width = max_width
        self._rng = random.Random()
        self._state = "idle"
        self._compact = False
        self._blink_enabled = False
        self._pulse_enabled = False
        self._blink_job: Optional[str] = None
        self._blink_restore_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._pulse_phase = 0.0
        self._current_photo: Optional[tk.PhotoImage] = None
        self._images: Dict[Tuple[str, bool], tk.PhotoImage] = {}
        self._placeholder: Optional[tk.Canvas] = None
        self._theme = (os.getenv("BASCULA_MASCOT_THEME", "retro-green") or "retro-green").strip()
        self._revert_job: Optional[str] = None

        self._image_label = tk.Label(self, bd=0, highlightthickness=0, bg=self._bg_color)
        self._image_label.place(relx=0.5, rely=0.5, anchor="center")

        if is_compact_mode():
            self.set_compact(True)

        self.set_state("idle")

    # ------------------------------------------------------------------ public API
    def set_state(self, name: str) -> None:
        """Switch the mascot to *name* if it is a recognised state."""

        if not name:
            return
        key = str(name).strip().lower()
        if key not in _VALID_STATES:
            _LOG.debug("MascotWidget: ignoring unknown state '%s'", key)
            return
        if self._state == key and not self._compact and self._current_photo is not None:
            # Avoid unnecessary reloads when nothing changed.
            return
        self._state = key
        self._apply_highlight()
        self._update_image()
        if key in {"listen", "think"}:
            self._schedule_revert(2600)
        elif key == "error":
            self._schedule_revert(3600)
        elif key == "sleep":
            self._cancel_revert()

    def blink(self, enable: bool = True) -> None:
        """Enable or disable the random blink animation."""

        self._blink_enabled = bool(enable)
        if not enable:
            self._cancel_blink()
            return
        if self._blink_job is None:
            self._schedule_blink()

    def pulse(self, enable: bool = True) -> None:
        """Enable or disable the idle bobbing animation."""

        self._pulse_enabled = bool(enable)
        if not enable:
            self._cancel_pulse()
            return
        self._pulse_phase = 0.0
        if self._pulse_job is None:
            self._animate_pulse()

    def set_compact(self, compact: bool) -> None:
        """Toggle compact mode, switching to the mini avatar asset."""

        compact = bool(compact)
        if self._compact == compact:
            return
        self._compact = compact
        self._images.clear()
        if compact:
            try:
                self.configure(padx=0, pady=0)
            except tk.TclError:
                pass
        self._update_image(force=True)

    # ------------------------------------------------------------------ lifecycle helpers
    @property
    def _bg_color(self) -> str:
        try:
            value = str(self.cget("bg"))
        except tk.TclError:
            value = ""
        return value or "#111111"

    def destroy(self) -> None:  # pragma: no cover - Tk teardown
        self.blink(False)
        self.pulse(False)
        self._cancel_revert()
        super().destroy()

    # ------------------------------------------------------------------ animation internals
    def _schedule_blink(self) -> None:
        if not self._blink_enabled:
            return
        delay = self._rng.randint(2000, 6000)
        try:
            self._blink_job = self.after(delay, self._do_blink)
        except Exception:  # pragma: no cover - Tk shutdown
            self._blink_job = None

    def _cancel_blink(self) -> None:
        if self._blink_job:
            try:
                self.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None
        if self._blink_restore_job:
            try:
                self.after_cancel(self._blink_restore_job)
            except Exception:
                pass
            self._blink_restore_job = None
        if not self._compact:
            self._update_image()

    def _do_blink(self) -> None:
        self._blink_job = None
        if not self._blink_enabled or self._compact or self._state != "idle":
            self._schedule_blink()
            return
        blink_photo = self._get_image(self._state, blink=True)
        if blink_photo is None:
            self._schedule_blink()
            return
        self._set_photo(blink_photo)
        try:
            self._blink_restore_job = self.after(160, self._end_blink)
        except Exception:
            self._blink_restore_job = None

    def _end_blink(self) -> None:
        self._blink_restore_job = None
        self._update_image()
        self._schedule_blink()

    def _animate_pulse(self) -> None:
        if not self._pulse_enabled:
            return
        self._pulse_phase = (self._pulse_phase + 0.25) % (2 * math.pi)
        offset = math.sin(self._pulse_phase)
        amplitude = 4 if not self._compact else 2
        try:
            self._image_label.place_configure(rely=0.5, anchor="center", y=int(offset * amplitude))
            self._pulse_job = self.after(80, self._animate_pulse)
        except Exception:  # pragma: no cover - Tk teardown
            self._pulse_job = None

    def _cancel_pulse(self) -> None:
        if self._pulse_job:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        try:
            self._image_label.place_configure(rely=0.5, anchor="center", y=0)
        except Exception:
            pass

    def _schedule_revert(self, delay: int) -> None:
        self._cancel_revert()
        try:
            self._revert_job = self.after(delay, lambda: self.set_state("idle"))
        except Exception:
            self._revert_job = None

    def _cancel_revert(self) -> None:
        if self._revert_job:
            try:
                self.after_cancel(self._revert_job)
            except Exception:
                pass
            self._revert_job = None

    # ------------------------------------------------------------------ image helpers
    def _asset_path(self, base_name: str) -> Optional[str]:
        for candidate in self._asset_candidates(base_name):
            if candidate.exists():
                return str(candidate)
        _LOG.warning("[warn] Missing mascot asset: %s", base_name)
        return None

    def _asset_candidates(self, base_name: str) -> Iterable[Path]:
        seen: set[str] = set()
        for size in ("1024", "512"):
            candidate = _GENERATED_DIR / f"{base_name}@{size}.png"
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
        for size in self._preferred_sizes():
            candidate = _ASSET_ROOT / f"{base_name}@{size}.png"
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
        fallback = _ASSET_ROOT / f"{base_name}.png"
        key = str(fallback)
        if key not in seen:
            yield fallback

    def _preferred_sizes(self) -> Tuple[str, ...]:
        if self._compact:
            return ("512", "1024")
        try:
            width = int(self.winfo_screenwidth())
        except Exception:
            width = 0
        if width >= 800:
            return ("1024", "512")
        return ("512", "1024")

    def _get_image(self, state: str, *, blink: bool = False) -> Optional[tk.PhotoImage]:
        key = (state if not blink else f"{state}-blink", self._compact)
        if key in self._images:
            return self._images[key]
        if blink and state == "idle":
            base_photo = self._get_image(state, blink=False)
            if base_photo is None:
                return None
            blink_photo = self._make_blink_frame(base_photo)
            if blink_photo is not None:
                self._images[key] = blink_photo
                return blink_photo
            return base_photo
        base_name: Optional[str]
        if self._compact:
            base_name = "avatar_mini"
        else:
            base_name = _STATE_TO_BASE.get(state)
        if not base_name:
            return None
        path = self._asset_path(base_name)
        if path is None:
            return None
        photo = self._load_photo(path)
        if photo is None:
            return None
        self._images[key] = photo
        return photo

    def _load_photo(self, path: str) -> Optional[tk.PhotoImage]:
        try:
            photo = tk.PhotoImage(file=path)
            target = self._max_width
            if self._compact:
                target = max(1, target // 2)
            if photo.width() > target:
                scale = max(1, int(math.ceil(photo.width() / float(target))))
                try:
                    photo = photo.subsample(scale, scale)
                except Exception:
                    pass
            return photo
        except Exception:
            _LOG.warning("[warn] Failed to load mascot asset: %s", path, exc_info=True)
            return None

    def _make_blink_frame(self, base: tk.PhotoImage) -> Optional[tk.PhotoImage]:
        try:
            blink = base.copy()
        except Exception:
            return None
        try:
            width = max(1, blink.width())
            height = max(1, blink.height())
        except Exception:
            return blink
        eyelid_height = max(2, height // 8)
        mid = height // 2
        y1 = max(0, mid - eyelid_height // 2)
        y2 = min(height, y1 + eyelid_height)
        try:
            blink.put("#0f3a24", to=(0, y1, width, y2))
        except Exception:
            return blink
        return blink

    def _update_image(self, force: bool = False) -> None:
        if self._compact:
            photo = self._get_image("idle", blink=False)
        else:
            photo = self._get_image(self._state, blink=False)
        if photo is None:
            self._show_placeholder()
            return
        self._hide_placeholder()
        if force or photo is not self._current_photo:
            self._set_photo(photo)

    def _set_photo(self, photo: tk.PhotoImage) -> None:
        self._current_photo = photo
        try:
            self._image_label.configure(image=photo)
        except Exception:
            pass

    def _show_placeholder(self) -> None:
        self._image_label.place_forget()
        if self._placeholder is None:
            self._placeholder = tk.Canvas(
                self,
                width=self._max_width,
                height=self._max_width,
                bg=self._bg_color,
                highlightthickness=0,
            )
            shade = "#27AE60"
            try:
                w = self._placeholder.winfo_reqwidth()
                h = self._placeholder.winfo_reqheight()
            except Exception:
                w = h = self._max_width
            size = min(w, h)
            pad = size * 0.2
            self._placeholder.create_oval(pad, pad, size - pad, size - pad, outline=shade, width=4)
            self._placeholder.create_text(size / 2, size / 2, text="🤖", font=("DejaVu Sans", int(size * 0.28)))
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _hide_placeholder(self) -> None:
        if self._placeholder is not None:
            self._placeholder.place_forget()
        self._image_label.place(relx=0.5, rely=0.5, anchor="center")

    def _apply_highlight(self) -> None:
        color = _STATE_HIGHLIGHT.get(self._state)
        if color and self._theme == "retro-green":
            try:
                self.configure(highlightthickness=2, highlightbackground=color)
            except tk.TclError:
                pass
        else:
            try:
                self.configure(highlightthickness=0)
            except tk.TclError:
                pass


__all__ = ["MascotWidget", "is_compact_mode"]
