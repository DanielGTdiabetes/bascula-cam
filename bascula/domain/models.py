from dataclasses import dataclass
from typing import Optional

@dataclass
class StabilityInfo:
    std_dev: float
    stable: bool
    zero_count: int

@dataclass
class Measurement:
    timestamp: str
    weight: float
    unit: str = "g"
    stable: bool = True
    photo: Optional[str] = None
