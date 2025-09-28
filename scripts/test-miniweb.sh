#!/usr/bin/env bash
set -euo pipefail
H="${1:-127.0.0.1}"
P="${2:-8080}"
curl -sf "http://$H:$P/health" >/dev/null
curl -sf "http://$H:$P/info" >/dev/null
echo "[ok] miniweb responde en http://$H:$P"
