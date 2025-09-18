from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import suppress
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.services.scale import NullScaleService, ScaleService

LOG = logging.getLogger("bascula.tools.check_scale")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[check_scale] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)


def main() -> int:
    device_env = os.getenv("BASCULA_DEVICE") or "<no definido>"
    LOG.info("BASCULA_DEVICE=%s", device_env)

    try:
        service = ScaleService.safe_create(logger=LOG, fail_fast=False)
    except Exception as exc:  # pragma: no cover - import error
        LOG.error("No se pudo crear ScaleService: %s", exc)
        return 1

    if isinstance(service, NullScaleService):
        LOG.warning("Servicio de báscula en modo seguro (NullScaleService)")
        return 0

    try:
        if hasattr(service, "start"):
            with suppress(Exception):
                service.start()
        LOG.info("Esperando lecturas…")
        for idx in range(5):
            time.sleep(0.2)
            try:
                weight = float(service.get_weight())
            except Exception as exc:  # pragma: no cover - diagnóstico
                LOG.error("Lectura fallida: %s", exc)
                return 1
            stable = False
            if hasattr(service, "is_stable"):
                with suppress(Exception):
                    stable = bool(service.is_stable())
            LOG.info("Lectura %02d: %.3f g (estable=%s)", idx + 1, weight, "sí" if stable else "no")
    finally:
        if hasattr(service, "stop"):
            with suppress(Exception):
                service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
