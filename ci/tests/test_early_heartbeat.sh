#!/usr/bin/env bash
set -euo pipefail

grep -RInq 'early heartbeat' bascula/ui || { echo "Falta comentario/emitir early heartbeat"; exit 1; }

echo "[OK] test_early_heartbeat"
