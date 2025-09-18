#!/usr/bin/env python3
"""Quick smoke test for the scale service.

It initialises :class:`ScaleService` using the same safe factory employed by the
UI, starts the worker thread and prints a handful of readings.  The script never
raises even when the hardware is not connected which makes it suitable for
diagnostics from SSH sessions.
"""

from __future__ import annotations

import time

from bascula.services.scale import ScaleService


def main() -> None:
    service = ScaleService.safe_create()
    device = getattr(service, "device", None)
    print(f"device: {device}")
    try:
        service.start()
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"err: no se pudo iniciar la báscula: {exc}")
        return

    try:
        for _ in range(10):
            try:
                weight = service.get_weight()
                print(f"weight: {weight}")
            except Exception as error:  # pragma: no cover - defensive
                print(f"err: {error}")
            time.sleep(0.2)
    finally:
        try:
            service.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()

