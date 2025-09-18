from __future__ import annotations

import argparse
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
handler.setFormatter(logging.Formatter("[check_scale][%(levelname)s] %(message)s"))
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnóstico ligero de la báscula")
    parser.add_argument(
        "--safe",
        action="store_true",
        help="Evita lecturas activas; solo inicializa el servicio",
    )
    parser.add_argument(
        "--reads",
        type=int,
        default=5,
        help="Número de lecturas a solicitar (ignorado en modo --safe)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    device_env = os.getenv("BASCULA_DEVICE") or "<no definido>"
    LOG.info("BASCULA_DEVICE=%s", device_env)

    try:
        service = ScaleService.safe_create(logger=LOG, fail_fast=False)
    except Exception as exc:  # pragma: no cover - import error
        LOG.error("No se pudo crear ScaleService: %s", exc)
        return 1

    if not service:
        service = NullScaleService()

    if isinstance(service, NullScaleService):
        LOG.warning("Servicio de báscula en modo seguro (NullScaleService)")
        return 0

    if args.safe:
        LOG.info("Modo seguro: omitiendo lecturas activas")
        return 0

    try:
        if hasattr(service, "start"):
            with suppress(Exception):
                service.start()
        LOG.info("Esperando lecturas…")
        for idx in range(max(1, args.reads)):
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
            LOG.info(
                "Lectura %02d: %.3f g (estable=%s)",
                idx + 1,
                weight,
                "sí" if stable else "no",
            )
    finally:
        if hasattr(service, "stop"):
            with suppress(Exception):
                service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
