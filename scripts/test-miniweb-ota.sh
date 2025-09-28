#!/usr/bin/env bash
set -euo pipefail
H="${1:-127.0.0.1}"
P="${2:-8080}"
T="${3:-}"
HDR=()
if [[ -n "$T" ]]; then
  HDR=(-H "X-API-Token: $T")
fi
curl -sf "http://$H:$P/ota/status" "${HDR[@]}" >/dev/null
curl -sf -X POST "http://$H:$P/ota/check" "${HDR[@]}" >/dev/null
echo "[ok] OTA status & check"
