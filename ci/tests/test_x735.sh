#!/usr/bin/env bash
set -euo pipefail

dest="${DESTDIR:-/tmp/ci-root}"
unit="${dest}/etc/systemd/system/x735-poweroff.service"
rm -f "${unit}"
mkdir -p "$(dirname "${unit}")"

export BASCULA_CI=1
export DESTDIR="${dest}"

bash scripts/install-1-system.sh --render-x735-service 5000

grep -Fx 'User=root' "${unit}" >/dev/null
grep -F -- '--threshold 5000' "${unit}" >/dev/null

echo "[test_x735] ok"
