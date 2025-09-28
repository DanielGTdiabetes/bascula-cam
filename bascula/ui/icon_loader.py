"""Icon loading helpers for the holographic UI."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageTk

from .theme_holo import COLOR_PRIMARY

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


def load_icon(name: str, size: int = 72, *, target_diameter: int | None = None) -> ImageTk.PhotoImage:
    """Return a Tk image for the given icon name.

    Parameters
    ----------
    name:
        File name inside ``assets/icons``. The lookup is case-insensitive
        and accepts names without extension.
    size:
        Target square size in pixels. Icons are rescaled with high-quality
        filtering and cached for reuse.
    target_diameter:
        Optional diameter of the UI element that will host the icon. When
        provided, the icon size is constrained so it cannot exceed the
        available circular footprint minus a safety margin.
    """

    raw_name = str(name or "")
    key_size = int(max(1, size))
    if target_diameter is not None:
        safe_target = int(max(1, target_diameter))
        margin = max(12, safe_target // 6)
        safe_size = max(16, safe_target - margin)
        key_size = min(key_size, safe_size)

    if raw_name.startswith("text:"):
        normalized_name = raw_name
        key = (normalized_name, key_size)
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        image = _text_icon_image(raw_name[5:], key_size)
        tk_image = ImageTk.PhotoImage(image)
        _CACHE[key] = tk_image
        return tk_image

    normalized_name = _normalize_name(raw_name)
    key = (normalized_name, key_size)
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


def _text_icon_image(text: str, size: int) -> Image.Image:
    side = int(max(16, size))
    clean = (text or "").strip()
    if not clean:
        return _placeholder_icon(side)

    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    padding = max(4, side // 8)
    max_box = side - padding * 2

    font = _resolve_font(side)
    bbox = _measure_text(draw, clean, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if text_w > max_box or text_h > max_box:
        for candidate in range(side, 6, -1):
            font = _resolve_font(candidate)
            bbox = _measure_text(draw, clean, font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            if text_w <= max_box and text_h <= max_box:
                break

    x = (side - text_w) / 2 - bbox[0]
    y = (side - text_h) / 2 - bbox[1]
    draw.text((x, y), clean, font=font, fill=COLOR_PRIMARY)
    return image


def _resolve_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = int(max(8, size))
    candidates = (
        "Oxanium-Bold.ttf",
        "ShareTechMono-Regular.ttf",
        "ShareTechMono-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox
    except Exception:
        w, h = draw.textsize(text, font=font)
        return (0, 0, w, h)


__all__ = ["load_icon"]
