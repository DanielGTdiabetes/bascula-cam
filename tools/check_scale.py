#!/usr/bin/env python3
"""Diagnóstico rápido de la báscula serie."""

from __future__ import annotations

import logging
import os
import sys
import time

from bascula.services.scale import NullScaleService, ScaleService

LOG = logging.getLogger("bascula.tools.check_scale")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[check_scale] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)


def main() -> int:
    device_env = os.getenv("BASCULA_DEVICE")
    LOG.info("BASCULA_DEVICE=%s", device_env or "<no definido>")

    service = ScaleService.safe_create(logger=LOG, fail_fast=False)
    if isinstance(service, NullScaleService):
        LOG.warning("Servicio de báscula en modo seguro (sin lecturas reales)")
        return 0

    if hasattr(service, "start"):
        try:
            service.start()
        except Exception as exc:  # pragma: no cover - diagnóstico
            LOG.warning("No se pudo iniciar la báscula: %s", exc)
            return 1

    LOG.info("Esperando lecturas…")
    time.sleep(1.0)
    try:
        weight = service.get_weight()
    except Exception as exc:  # pragma: no cover
        LOG.warning("Lectura fallida: %s", exc)
        return 1

    LOG.info("Peso actual: %.3f g", weight)
    if hasattr(service, "stop"):
        try:
            service.stop()
        except Exception:  # pragma: no cover - limpieza
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
