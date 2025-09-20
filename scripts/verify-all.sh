#!/usr/bin/env bash
# Ejecuta la batería de verificaciones rápidas para la UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS=0

warn() {
    echo "[verify-all][WARN] $*"
}

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

if ! id -nG "$USER" | tr ' ' '\n' | grep -qx "dialout"; then
    warn "El usuario $USER no pertenece a 'dialout'"
fi

if [[ ! -f /etc/udev/rules.d/90-bascula.rules ]]; then
    warn "Falta /etc/udev/rules.d/90-bascula.rules"
fi

if command -v raspi-config >/dev/null 2>&1; then
    serial_state="$(raspi-config nonint get_serial 2>/dev/null || echo '')"
    if [[ "${serial_state}" != "1" ]]; then
        warn "raspi-config indica consola serie habilitada (estado=${serial_state:-desconocido})"
    fi
fi

if [[ ! -e /dev/serial0 ]]; then
    warn "/dev/serial0 no existe"
fi

echo "[verify-all] Diagnóstico rápido báscula..."
if ! python3 "${SCRIPT_DIR}/../tools/check_scale.py" --seconds 2; then
    warn "tools/check_scale.py devolvió error"
fi

exit ${STATUS}
