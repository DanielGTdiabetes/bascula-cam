from pathlib import Path
from PIL import Image, ImageTk

ICONS_DIR = Path(__file__).parent / "assets" / "icons"
_cache = {}


def load_icon(name: str, size: int = 128, color: str = "#00FF88"):
    """
    Carga un PNG desde assets/icons, lo reescala y lo tiñe al color dado.
    Devuelve un PhotoImage cacheado.
    """
    key = (name, size, color)
    if key in _cache:
        return _cache[key]

    path = ICONS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Icono no encontrado: {path}")

    img = Image.open(path).convert("RGBA")
    img = img.resize((size, size), Image.LANCZOS)

    # Tinte de color manteniendo alpha
    r, g, b, a = img.split()
    overlay = Image.new("RGBA", img.size, color)
    img = Image.composite(overlay, img, a)

    tk_img = ImageTk.PhotoImage(img)
    _cache[key] = tk_img
    return tk_img
