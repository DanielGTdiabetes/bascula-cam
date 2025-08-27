from dataclasses import dataclass
@dataclass
class ModernTheme:
    primary: str = "#2563EB"
    success: str = "#10B981"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    info: str = "#06B6D4"
    accent: str = "#8B5CF6"
    background: str = "#0F172A"
    surface: str = "#334155"
    surface_light: str = "#475569"
    medium: str = "#64748B"
    light: str = "#94A3B8"
    text: str = "#F8FAFC"
    text_light: str = "#CBD5E1"
THEME_MODERN = ModernTheme()
