#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick diagnostic utility for the serial scale."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bascula.core.scale_serial import SerialScale


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnóstico de báscula serie")
    parser.add_argument("--device", help="Puerto serie a usar (auto si se omite)")
    parser.add_argument("--baud", type=int, help="Baudios del puerto (auto si se omite)")
    parser.add_argument("--seconds", type=float, default=5.0, help="Segundos de muestreo (por defecto 5)")
    parser.add_argument("--raw", action="store_true", help="Mostrar línea cruda leída del puerto")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("check_scale")

    try:
        scale = SerialScale(
            device=args.device,
            baudrate=args.baud,
            simulate_if_unavailable=True,
            logger=log,
        )
    except Exception as exc:
        log.error("No se pudo crear SerialScale: %s", exc)
        return 1

    try:
        scale.start()
    except Exception as exc:
        log.error("Error iniciando báscula: %s", exc)
        return 2

    log.info(
        "Leyendo de %s @ %s (modo %s)",
        scale.device or args.device or "auto",
        scale.baudrate or args.baud or "auto",
        "simulado" if scale.is_simulated else "hardware",
    )

    last_weight = 0.0
    last_stable = False
    samples = 0
    start = time.time()
    try:
        while time.time() - start < max(0.5, float(args.seconds)):
            weight = scale.read_weight()
            stable = scale.stable
            last_weight = weight
            last_stable = stable
            samples += 1
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            line = f"{ts} | {weight:8.2f} g | {'Estable' if stable else 'Leyendo'}"
            if args.raw:
                raw_line = scale.last_raw_line
                if raw_line:
                    line += f" | raw={raw_line!r}"
            print(line)
            time.sleep(0.2)
    except KeyboardInterrupt:
        log.info("Interrumpido por usuario")
    finally:
        scale.stop()

    print("\nResumen:")
    print(f"  Puerto: {scale.device or 'auto'}")
    print(f"  Baudios: {scale.baudrate or 'auto'}")
    print(f"  Modo: {'Simulación' if scale.is_simulated else 'Hardware'}")
    print(f"  Lecturas: {samples}")
    print(f"  Último peso: {last_weight:.2f} g")
    print(f"  Estado final: {'Estable' if last_stable else 'Leyendo'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
