#!/usr/bin/env bash
set -euo pipefail
H="${1:-127.0.0.1}"
P="${2:-8080}"
T="${3:-}"
HDR=()
if [[ -n "$T" ]]; then
  HDR=(-H "X-API-Token: $T")
fi
curl -sf "http://$H:$P/config" >/dev/null
curl -sf "http://$H:$P/config/wifi/status" "${HDR[@]}" >/dev/null
echo "[ok] config wifi/status"
