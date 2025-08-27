import json, csv
from pathlib import Path
from typing import List, Dict, Any

class Storage:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.data_dir = self.base_dir / "data"
        self.captures_dir = self.base_dir / "capturas"
        for d in (self.data_dir, self.captures_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.measure_path = self.base_dir / "measurements.json"

    @staticmethod
    def load_json(path: Path, default):
        try:
            return json.loads(path.read_text())
        except Exception:
            return default

    @staticmethod
    def save_json(path: Path, obj: Any):
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        tmp.replace(path)

    def append_measurement(self, measurement: Dict[str, Any]):
        data = self.load_json(self.measure_path, [])
        data.append(measurement)
        self.save_json(self.measure_path, data)

    def export_csv(self, output_path: Path):
        rows = self.load_json(self.measure_path, [])
        with output_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["timestamp", "weight", "unit", "stable", "photo"])
            w.writeheader()
            for r in rows:
                w.writerow({
                    "timestamp": r.get("timestamp",""),
                    "weight": r.get("weight",""),
                    "unit": r.get("unit","g"),
                    "stable": r.get("stable", True),
                    "photo": r.get("photo","")
                })
