"""Mascot brain reacting to EventBus events with optional LLM support."""

from __future__ import annotations

import random
from typing import Any, Dict


class MascotBrain:
    """Simple reactive brain for the on–screen mascot.

    The brain listens to events on the provided ``EventBus`` and decides when
    to show small messages through ``app.messenger``.  A basic rate limit is
    enforced so the mascot does not become intrusive.  Optionally an external
    LLM client can be used to generate text.
    """

    def __init__(self, app, event_bus):
        self.app = app
        self.bus = event_bus
        cfg = app.get_cfg() if hasattr(app, "get_cfg") else {}
        self.mood = 0.0  # -1..+1
        self.personality = cfg.get("mascot_persona", "discreto")
        self.max_per_hour = int(cfg.get("mascot_max_per_hour", 3))
        self.no_disturb = bool(cfg.get("mascot_dnd", False))
        self.use_llm = bool(cfg.get("mascot_llm_enabled", False))
        self.allow_health = bool(cfg.get("mascot_llm_send_health", False))
        self._timestamps: list[float] = []
        self._install()

    # ------------------------------------------------------------------
    def _install(self) -> None:
        self.bus.subscribe("IDLE_TICK", self.on_idle)
        self.bus.subscribe("WEIGHT_CAPTURED", self.on_capture)
        self.bus.subscribe("TARA", lambda _: self.say("Tara aplicada.", kind="info"))
        self.bus.subscribe("SCANNER_OPEN", lambda _: self.say("Pasa el código por el recuadro.", icon="🎯"))
        self.bus.subscribe(
            "SCANNER_DETECTED", lambda _: self.say("Código detectado.", icon="✅", priority=5)
        )
        self.bus.subscribe("BG_UPDATE", self.on_bg)
        self.bus.subscribe(
            "BG_HYPO", lambda bg: self.say("Hipoglucemia. Sigue 15/15.", icon="🍬", priority=7)
        )
        self.bus.subscribe(
            "TIMER_STARTED",
            lambda s: self.say(f"Temporizador {s//60:02d}:{s%60:02d} iniciado.", icon="⏱"),
        )
        self.bus.subscribe(
            "TIMER_FINISHED", lambda _: self.say("Tiempo cumplido.", icon="⏱", priority=5)
        )

    # ------------------------------------------------------------------
    def on_idle(self, _payload: Any) -> None:
        if self.no_disturb or not self._quota_ok():
            return
        p = {"off": 0.0, "discreto": 0.05, "normal": 0.12, "jugueton": 0.22}.get(
            self.personality, 0.05
        )
        if random.random() < p:
            self._playful_ping()

    def on_capture(self, grams: Any) -> None:
        try:
            g = float(grams)
        except Exception:
            g = 0.0
        self.mood = min(1.0, self.mood + 0.1)
        self.say(f"Capturado: {int(g)} g.", icon="✅", priority=5)

    def on_bg(self, data: Dict[str, Any]) -> None:
        trend = data.get("trend") if isinstance(data, dict) else None
        if trend == "up":
            self.say("Flecha ↑, ojo con subidas.", icon="🩸")
        elif trend == "down":
            self.say("Flecha ↓, prudencia.", icon="🩸")

    # ------------------------------------------------------------------
    def _playful_ping(self) -> None:
        ctx = self._build_context()
        text = self._gen_text(ctx)
        if text:
            self.say(text, icon="💬")

    def _gen_text(self, ctx: Dict[str, Any]) -> str:
        if self.use_llm:
            return self._llm_text(ctx)
        bank = [
            "¿Probamos el escáner?",
            "Recuerda el temporizador si cocinas.",
            "Tema retro listo. Verde que te quiero verde.",
            "Pulsa Tara si cambias de recipiente.",
        ]
        return random.choice(bank)

    def _llm_text(self, ctx: Dict[str, Any]) -> str:
        client = getattr(self.app, "llm_client", None)
        if not client:
            return ""
        prompt = self._persona_prompt(ctx)
        try:
            return client.generate(prompt)[:120]
        except Exception:
            return ""

    def _persona_prompt(self, ctx: Dict[str, Any]) -> str:
        safe_ctx = {k: v for k, v in ctx.items() if self.allow_health or k not in ("bg", "trend")}
        return (
            "Eres una mascota asistente en una app de báscula táctil. "
            "Tono cercano, breve, útil, una o dos frases. No des consejos médicos. "
            f"Contexto: {safe_ctx}. Responde en español."
        )

    # ------------------------------------------------------------------
    def say(self, text: str, kind: str = "info", priority: int = 3, icon: str = "💬") -> None:
        if not text or self.no_disturb or not self._quota_ok():
            return
        self._timestamps.append(self._now())
        try:
            self.app.messenger.show(text, kind=kind, priority=priority, icon=icon)
            try:
                self.app.mascot.wink()
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _quota_ok(self) -> bool:
        import time

        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 3600]
        return len(self._timestamps) < self.max_per_hour

    def _now(self) -> float:
        import time

        return time.time()

    def _build_context(self) -> Dict[str, Any]:
        st = self.app.get_state() if hasattr(self.app, "get_state") else {}
        ctx = {
            "screen": getattr(self.app, "current_screen_name", "home"),
            "theme": self.app.get_cfg().get("ui_theme", "modern"),
            "timer_active": bool(st.get("timer_active", False)),
            "last_capture_g": st.get("last_capture_g", None),
        }
        if self.allow_health:
            ctx.update({"bg": st.get("bg_value"), "trend": st.get("bg_trend")})
        return ctx


__all__ = ["MascotBrain"]

