#!/usr/bin/env bash
set -euo pipefail

PIN="${X735_POWER_PIN:-4}"
if command -v raspi-gpio >/dev/null 2>&1; then
  raspi-gpio set "${PIN}" op dl
  sleep 0.5
  raspi-gpio set "${PIN}" op dh
  sleep 0.5
  raspi-gpio set "${PIN}" op dl
fi
