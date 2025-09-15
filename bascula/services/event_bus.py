class EventBus:
    """Simple publish/subscribe event bus."""

    def __init__(self):
        self._subs = {}

    def subscribe(self, topic, fn):
        self._subs.setdefault(topic, []).append(fn)

    def publish(self, topic, payload=None):
        for fn in self._subs.get(topic, []):
            try:
                fn(payload)
            except Exception:
                pass


# Known topics
TOPICS = [
    "IDLE_TICK",
    "TIMER_STARTED",
    "TIMER_FINISHED",
    "WEIGHT_CAPTURED",
    "TARA",
    "SCANNER_OPEN",
    "SCANNER_DETECTED",
    "THEME_CHANGED",
    "BG_UPDATE",
    "BG_HYPO",
    "BG_NORMAL",
]
