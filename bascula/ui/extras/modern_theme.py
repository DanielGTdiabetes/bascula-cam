# Optional Modern theme inspired by Claude's palette, mapped to our THEME interface.
from dataclasses import dataclass

@dataclass
class ModernTheme:
    primary: str = "#2563EB"
    success: str = "#10B981"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    info: str = "#06B6D4"
    accent: str = "#8B5CF6"

    background: str = "#0F172A"     # BG primary (dark)
    surface: str = "#334155"        # Card surface
    surface_light: str = "#475569"  # Lighter surface
    medium: str = "#64748B"         # Secondary text / muted
    light: str = "#94A3B8"

    text: str = "#F8FAFC"
    text_light: str = "#CBD5E1"

THEME_MODERN = ModernTheme()
