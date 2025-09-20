#!/usr/bin/env bash
# Ejecuta la batería de verificaciones rápidas para la UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS=0

run_check() {
    local name=$1
    shift
    echo "[verify-all] Ejecutando ${name}..."
    if "$@"; then
        echo "[verify-all] ${name}: OK"
    else
        echo "[verify-all] ${name}: ERROR"
        STATUS=1
    fi
    echo
}

run_check "verify-kiosk" "${SCRIPT_DIR}/verify-kiosk.sh"

exit ${STATUS}
