"""Recipe helper orchestration for the interactive mode."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List


@dataclass
class RecipeStep:
    description: str
    requires_scale: bool = False


@dataclass
class RecipeSession:
    name: str
    steps: List[RecipeStep] = field(default_factory=list)
    current_index: int = 0

    def current(self) -> RecipeStep:
        return self.steps[self.current_index]

    def next(self) -> RecipeStep:
        if self.current_index < len(self.steps) - 1:
            self.current_index += 1
        return self.current()

    def repeat(self) -> RecipeStep:
        return self.current()


class RecipeEngine:
    """Very small engine to walk through interactive recipes."""

    def __init__(self) -> None:
        self._listeners: List[Callable[[RecipeStep], None]] = []
        self.session: RecipeSession | None = None

    def start(self, recipe_name: str) -> RecipeSession:
        self.session = RecipeSession(
            name=recipe_name,
            steps=[
                RecipeStep("Prepara los ingredientes."),
                RecipeStep("Pesa los ingredientes principales", requires_scale=True),
                RecipeStep("Sigue la cocción según las indicaciones."),
            ],
        )
        self._notify()
        return self.session

    def next_step(self) -> RecipeStep:
        if not self.session:
            raise RuntimeError("No hay receta activa")
        step = self.session.next()
        self._notify()
        return step

    def repeat_step(self) -> RecipeStep:
        if not self.session:
            raise RuntimeError("No hay receta activa")
        step = self.session.repeat()
        self._notify()
        return step

    def subscribe(self, callback: Callable[[RecipeStep], None]) -> None:
        self._listeners.append(callback)
        if self.session:
            callback(self.session.current())

    def _notify(self) -> None:
        if not self.session:
            return
        for callback in list(self._listeners):
            callback(self.session.current())


__all__ = ["RecipeEngine", "RecipeSession", "RecipeStep"]
