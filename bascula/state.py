# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional
from bascula.config.settings import AppConfig

@dataclass
class AppState:
    cfg: AppConfig
    running: bool = True
    last_weight_g: float = 0.0
    stable: bool = False
    error: Optional[str] = None
