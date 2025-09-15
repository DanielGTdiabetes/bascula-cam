import random
import time
from typing import Callable

from bascula.ui.mascot_messages import MSGS, get_message


class SimpleLLMClient:
    """Placeholder LLM client with opt-in sensitive data."""

    def __init__(self, send_bg: bool = False):
        self.send_bg = send_bg

    def complete(self, prompt: str) -> str | None:
        # Real implementation would call an online API with guardrails
        return None


class MascotBrain:
    """Local mascot brain with optional LLM client.

    It listens to events published on the EventBus and decides simple
    reactions.  A small idle loop publishes ``IDLE_TICK`` every minute.
    """

    def __init__(self, bus, messenger, cfg_provider: Callable[[], dict], root=None):
        self.bus = bus
        self.messenger = messenger
        self.cfg_provider = cfg_provider
        self.root = root or messenger.get_mascot().winfo_toplevel()
        cfg = cfg_provider() or {}
        self.llm = None
        if cfg.get('mascot_llm_enabled'):
            self.llm = SimpleLLMClient(send_bg=bool(cfg.get('mascot_llm_send_bg')))

        # subscribe to events
        bus.subscribe("TIMER_STARTED", self.on_timer_started)
        bus.subscribe("TIMER_FINISHED", self.on_timer_finished)
        bus.subscribe("BG_HYPO", self.on_bg_hypo)
        bus.subscribe("BG_NORMAL", self.on_bg_normal)
        bus.subscribe("THEME_CHANGED", self.on_theme_changed)
        bus.subscribe("IDLE_TICK", self.on_idle_tick)

        # idle ticker
        self._schedule_tick()

    # ---- event helpers -------------------------------------------------
    def _schedule_tick(self):
        try:
            self.root.after(60000, self._tick)
        except Exception:
            pass

    def _tick(self):
        self.bus.publish("IDLE_TICK")
        self._schedule_tick()

    def _show(self, key, *args, **kwargs):
        text, action, anim = get_message(key, *args)
        self.messenger.show(text, anim=anim, action=action, **kwargs)

    # ---- event handlers ------------------------------------------------
    def on_timer_started(self, payload):
        self._show("timer_started", payload, kind="info", priority=3, icon="⏱")

    def on_timer_finished(self, _payload):
        self._show("timer_finished", kind="success", priority=6, icon="⏱")

    def on_bg_hypo(self, value):
        # Supportive only, no medical advice
        msg = f"BG {value} mg/dL. ¿Te sientes bien?" if value is not None else "BG bajo"
        self.messenger.show(msg, kind="warning", priority=8, icon="⚠️", anim="shake")

    def on_bg_normal(self, value):
        msg = f"BG {value} mg/dL" if value is not None else "BG OK"
        self.messenger.show(msg, kind="info", priority=2, icon="💬", anim="wink")

    def on_theme_changed(self, _payload):
        self._show("theme_changed", kind="info", priority=1, icon="🎨")

    def on_idle_tick(self, _payload):
        cfg = self.cfg_provider() or {}
        if cfg.get('mascot_no_molestar'):
            return
        personality = cfg.get('mascot_personality', 'normal')
        if personality == 'off':
            return
        if random.random() < 0.2:  # moderate initiative
            choices = {
                'discreto': ["todo tranquilo"],
                'normal': ["¿Cómo va todo?"],
                'jugueton': ["¡Hola!"],
            }
            text = random.choice(choices.get(personality, choices['normal']))
            self.messenger.show(text, kind="info", priority=1, icon="💬", anim="wink")
