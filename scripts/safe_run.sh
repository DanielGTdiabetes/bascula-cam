#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/ui.log"
ROTATED_LOG="${LOG_FILE}.1"
MAX_SIZE=$((5 * 1024 * 1024))

cd "${REPO_ROOT}"

if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
  export DISPLAY=:0
fi

if [[ -z "${XAUTHORITY:-}" ]]; then
  export XAUTHORITY="${HOME}/.Xauthority"
fi

if [[ -f /etc/bascula/bascula.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/bascula/bascula.env
  set +a
fi

mkdir -p "${LOG_DIR}"
if [[ -f "${LOG_FILE}" ]]; then
  size=$(stat -c '%s' "${LOG_FILE}" 2>/dev/null || echo 0)
  if (( size > MAX_SIZE )); then
    mv "${LOG_FILE}" "${ROTATED_LOG}" 2>/dev/null || true
  fi
fi

touch "${LOG_FILE}"

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" main.py "$@" 2>&1 | tee -a "${LOG_FILE}"
exit "${PIPESTATUS[0]}"
