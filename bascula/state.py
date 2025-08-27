from dataclasses import dataclass
from bascula.config.settings import AppConfig

@dataclass
class AppState:
    cfg: AppConfig
    current_weight: float = 0.0
    mode: str = "home"  # home | plate | add_item | recipe
    meal_active: bool = False
    meal_items: int = 0
    meal_carbs: float = 0.0
    camera_ready: bool = False
    hx_ready: bool = False
