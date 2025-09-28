"""Icon loading helpers for the holographic UI."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageTk


ICONS_DIR = Path(__file__).parent / "assets" / "icons"
_CACHE: Dict[Tuple[str, int], ImageTk.PhotoImage] = {}
_KNOWN_FILES: Dict[str, str] = {}
_PLACEHOLDER_COLOR = "#00E5FF"
_ALIASES = {
    "sound.png": "speaker.png",
    "sound": "speaker.png",
    "audio.png": "speaker.png",
    "audio": "speaker.png",
    "alarm.png": "timer.png",
    "alarm": "timer.png",
    "bell.png": "timer.png",
    "bell": "timer.png",
}
try:  # Pillow >=9.1
    _RESAMPLE = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - compatibility fallback
    _RESAMPLE = Image.LANCZOS


def load_icon(name: str, size: int = 72) -> ImageTk.PhotoImage:
    """Return a Tk image for the given icon name.

    Parameters
    ----------
    name:
        File name inside ``assets/icons``. The lookup is case-insensitive
        and accepts names without extension.
    size:
        Target square size in pixels. Icons are rescaled with high-quality
        filtering and cached for reuse.
    """

    normalized_name = _normalize_name(name)
    key = (normalized_name, int(max(1, size)))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    image = _load_image_from_disk(normalized_name)
    if image is None:
        image = _placeholder_icon(key[1])
    else:
        image = image.resize((key[1], key[1]), _RESAMPLE)

    tk_image = ImageTk.PhotoImage(image)
    _CACHE[key] = tk_image
    return tk_image


def _normalize_name(name: str) -> str:
    candidate = Path(name or "").name
    if not candidate:
        return ""
    if "." not in candidate:
        candidate = f"{candidate}.png"
    lower = candidate.lower()
    if lower in _ALIASES:
        candidate = _ALIASES[lower]
        lower = candidate.lower()
    if not _KNOWN_FILES:
        for path in ICONS_DIR.glob("*.png"):
            _KNOWN_FILES[path.name.lower()] = path.name
    return _KNOWN_FILES.get(lower, candidate)


def _load_image_from_disk(name: str) -> Image.Image | None:
    if not name:
        return None
    path = ICONS_DIR / name
    try:
        with Image.open(path) as img:
            return img.convert("RGBA")
    except Exception:
        return None


def _placeholder_icon(size: int) -> Image.Image:
    side = int(max(1, size))
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    stroke = max(2, side // 12)
    inset = stroke // 2 + 1
    draw.ellipse((inset, inset, side - inset - 1, side - inset - 1), outline=_PLACEHOLDER_COLOR, width=stroke)

    cross_thickness = max(2, stroke - 1)
    cx = side / 2
    cy = side / 2
    arm = side * 0.32
    draw.line((cx, cy - arm, cx, cy + arm), fill=_PLACEHOLDER_COLOR, width=cross_thickness)
    draw.line((cx - arm, cy, cx + arm, cy), fill=_PLACEHOLDER_COLOR, width=cross_thickness)

    return image


__all__ = ["load_icon"]
