"""Servicios de báscula tolerantes a fallos."""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PY_BACKEND = REPO_ROOT / "python_backend"
if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

try:  # Backend serie real
    from serial_scale import SerialScale  # type: ignore
except Exception:  # pragma: no cover - fallback cuando falta backend
    SerialScale = None  # type: ignore

_DEFAULT_PORTS = (
    "/dev/ttyACM0",
    "/dev/ttyUSB0",
    "/dev/ttyAMA0",
    "/dev/ttyS0",
    "/dev/serial0",
)


class NullScaleService:
    """Implementación nula utilizada cuando no hay hardware disponible."""

    name = "null"

    def __init__(self, logger: Optional[logging.Logger] = None, reason: str | None = None) -> None:
        self.logger = logger or logging.getLogger("bascula.services.scale.null")
        self._reason = reason or ""
        if self._reason:
            self.logger.info("ScaleService en modo seguro: %s", self._reason)

    def start(self) -> None:  # pragma: no cover - trivial
        return

    def stop(self) -> None:  # pragma: no cover - trivial
        return

    def get_weight(self) -> float:
        return 0.0

    def get_latest(self) -> float:
        return 0.0

    def is_stable(self) -> bool:
        return False

    def tare(self) -> bool:
        return False

    def calibrate(self, weight_grams: float) -> bool:  # pragma: no cover - compat
        return False


class ScaleService:
    """Gestor del backend serie con reconexión y lectura segura."""

    def __init__(
        self,
        *,
        port: str,
        baud: int = 115200,
        logger: Optional[logging.Logger] = None,
        sample_ms: int | None = None,
        fail_fast: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger("bascula.services.scale")
        self.port = str(port)
        self.baud = baud
        self.sample_ms = max(10, int(sample_ms or 100))
        self.fail_fast = bool(fail_fast)

        self._backend: Optional[SerialScale] = None  # type: ignore[type-arg]
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_weight = 0.0
        self._last_stable = False
        self._subs: list[Callable[[float, bool], None]] = []
        self._queue: queue.Queue[tuple[float, bool]] = queue.Queue(maxsize=1)

    # ------------------------------------------------------------------ ciclo de vida
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ScaleService", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        backend = self._backend
        if backend is not None:
            try:
                backend.stop()  # type: ignore[call-arg]
            except Exception:  # pragma: no cover - limpieza defensiva
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._backend = None
        self._thread = None

    # ------------------------------------------------------------------ datos
    def get_weight(self) -> float:
        return float(self._last_weight)

    def get_latest(self) -> float:
        return self.get_weight()

    def is_stable(self) -> bool:
        return bool(self._last_stable)

    def subscribe(self, cb: Callable[[float, bool], None]) -> None:
        if callable(cb):
            self._subs.append(cb)

    def tare(self) -> bool:  # pragma: no cover - API histórica
        return True

    def calibrate(self, weight_grams: float) -> bool:  # pragma: no cover
        return True

    # ------------------------------------------------------------------ internals
    def _loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self._ensure_backend()
                backoff = 1.0
                time.sleep(self.sample_ms / 1000.0)
                backend = self._backend
                if backend is None:
                    continue
                thread = getattr(backend, "_thread", None)
                if thread is not None and not thread.is_alive():
                    self.logger.warning("Hilo de lectura detenido; reintentando")
                    self._reset_backend()
            except Exception as exc:  # pragma: no cover - ruta de recuperación
                self.logger.warning("Error en bucle de báscula: %s", exc, exc_info=not self.fail_fast)
                self._reset_backend()
                time.sleep(backoff)
                backoff = min(backoff * 2, 8.0)

    def _ensure_backend(self) -> None:
        if self._backend is not None:
            return
        self.logger.info("Abriendo báscula en %s @ %s", self.port, self.baud)
        backend = SerialScale(self.port, baud=self.baud, logger=self.logger)  # type: ignore[call-arg]
        backend.start(self._on_read)  # type: ignore[call-arg]
        self._backend = backend

    def _reset_backend(self) -> None:
        backend = self._backend
        if backend is not None:
            try:
                backend.stop()  # type: ignore[call-arg]
            except Exception:  # pragma: no cover
                pass
        self._backend = None

    def _on_read(self, grams: float, stable: int) -> None:
        try:
            self._last_weight = float(grams)
            self._last_stable = bool(int(stable))
        except Exception:  # pragma: no cover - datos corruptos
            return
        try:
            self._queue.put_nowait((self._last_weight, self._last_stable))
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:  # pragma: no cover
                pass
            try:
                self._queue.put_nowait((self._last_weight, self._last_stable))
            except queue.Full:  # pragma: no cover
                pass
        for cb in list(self._subs):
            try:
                cb(self._last_weight, self._last_stable)
            except Exception:  # pragma: no cover
                continue

    # ------------------------------------------------------------------ helpers
    @classmethod
    def safe_create(
        cls,
        *,
        logger: Optional[logging.Logger] = None,
        fail_fast: bool = False,
        config: Optional[dict[str, object]] = None,
        **kwargs,
    ) -> ScaleService | NullScaleService:
        log = logger or logging.getLogger("bascula.services.scale")
        port = _detect_port(log, config=config, explicit=kwargs.get("port"))
        if not port:
            log.warning("No se detectó ningún puerto para la báscula")
            return NullScaleService(logger=log, reason="sin puerto detectado")
        kwargs["port"] = port
        kwargs.setdefault("logger", log)
        kwargs.setdefault("fail_fast", fail_fast)
        if SerialScale is None:
            log.warning("serial_scale no disponible; usando modo seguro")
            return NullScaleService(logger=log, reason="backend ausente")
        try:
            service = cls(**kwargs)  # type: ignore[arg-type]
            service.start()
            return service
        except Exception as exc:  # pragma: no cover - hardware ausente
            log.warning("ScaleService en modo seguro: %s", exc, exc_info=log.isEnabledFor(logging.DEBUG))
            return NullScaleService(logger=log, reason=str(exc))


def _detect_port(
    logger: logging.Logger,
    *,
    config: Optional[dict[str, object]] = None,
    explicit: Optional[object] = None,
) -> str | None:
    env_port = os.getenv("BASCULA_DEVICE", "").strip()
    if env_port:
        logger.info("Usando BASCULA_DEVICE=%s", env_port)
        return env_port

    if isinstance(explicit, str) and explicit.strip():
        logger.info("Usando puerto configurado=%s", explicit.strip())
        return explicit.strip()

    if config and isinstance(config.get("port"), str):
        value = str(config.get("port")).strip()
        if value:
            logger.info("Puerto definido en config=%s", value)
            return value

    for candidate in _DEFAULT_PORTS:
        if Path(candidate).exists():
            logger.info("Puerto autodetectado=%s", candidate)
            return candidate
    return None


__all__ = ["ScaleService", "NullScaleService"]
