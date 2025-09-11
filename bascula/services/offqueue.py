from __future__ import annotations
from pathlib import Path
import json, time
from typing import Optional, Dict, Any


class OfflineQueue:
    def __init__(self, name: str = 'ns_queue') -> None:
        self.path = Path.home() / '.config' / 'bascula' / f'{name}.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(self, item: Dict[str, Any]) -> None:
        item = dict(item)
        item['ts'] = time.time()
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def items(self):
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding='utf-8').splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out

    def clear(self):
        try:
            self.path.unlink()
        except Exception:
            pass

