#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-8080}"
IP="$(hostname -I | awk '{print $1}')"
echo "[info] Probing http://127.0.0.1:${PORT}/health"
curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null && echo "OK local"

echo "[info] Probing http://${IP}:${PORT}/health (LAN/AP)"
curl -fsS "http://${IP}:${PORT}/health" >/dev/null && echo "OK LAN/AP"

echo "[info] Listening sockets"
ss -tulpen | grep -E "(:${PORT})\\b" || true
