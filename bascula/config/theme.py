from dataclasses import dataclass

@dataclass
class ColorTheme:
    primary: str = "#2563eb"
    success: str = "#10b981"
    danger: str = "#ef4444"
    warning: str = "#f59e0b"
    dark: str = "#1f2937"
    medium: str = "#6b7280"
    light: str = "#9ca3af"
    background: str = "#f8fafc"
    surface: str = "#ffffff"
    text: str = "#111827"
    text_light: str = "#6b7280"

THEME = ColorTheme()
