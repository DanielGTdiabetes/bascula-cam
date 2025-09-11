from __future__ import annotations
from pathlib import Path
import json, time, threading
from typing import Optional, Dict, Any, List

try:
    import requests  # type: ignore
except Exception:
    requests = None


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


_retry_thread = None
_retry_lock = threading.Lock()
_retry_running = False


def retry_all(base_url: str, token: str) -> None:
    """Retry sending queued Nightscout treatments with exponential backoff.

    Backoff plan: 60s, 300s, 900s, 3600s. Non-blocking: spawns a background thread
    if one is not already running. Safe to call multiple times.
    """
    global _retry_thread, _retry_running
    base_url = (base_url or "").rstrip("/")

    def _drain_once(items: List[Dict[str, Any]]) -> bool:
        if not items:
            return True
        if requests is None or not base_url:
            return False
        ok_any = False
        keep: List[Dict[str, Any]] = []
        url = f"{base_url}/api/v1/treatments"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["API-SECRET"] = token
        for it in items:
            if (it or {}).get("type") != "ns_treatment":
                # Unknown item types are kept for future logic
                keep.append(it)
                continue
            payload = (it or {}).get("payload") or {}
            try:
                r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=8)
                if 200 <= getattr(r, "status_code", 0) < 300:
                    ok_any = True
                else:
                    keep.append(it)
            except Exception:
                keep.append(it)

        # Rewrite file with remaining items
        q = OfflineQueue("ns_queue")
        try:
            if keep:
                q.path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in keep) + "\n", encoding="utf-8")
            else:
                q.clear()
        except Exception:
            pass
        return ok_any and not keep

    def _worker():
        global _retry_running
        with _retry_lock:
            if _retry_running:
                return
            _retry_running = True
        try:
            schedule = [60, 300, 900, 3600]
            attempt = 0
            q = OfflineQueue("ns_queue")
            while True:
                items = q.items()
                if not items:
                    break
                all_ok = _drain_once(items)
                if all_ok:
                    break
                # Wait backoff
                d = schedule[min(attempt, len(schedule)-1)]
                attempt += 1
                time.sleep(d)
        finally:
            with _retry_lock:
                _retry_running = False

    # Start worker thread if not active
    if _retry_thread is None or not _retry_thread.is_alive():
        _retry_thread = threading.Thread(target=_worker, daemon=True)
        _retry_thread.start()
