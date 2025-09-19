#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/ui.log"
ROTATED_LOG="${LOG_FILE}.1"
MAX_SIZE=$((5 * 1024 * 1024))

cd "${REPO_ROOT}"

if [[ -z "${XAUTHORITY:-}" ]]; then
  export XAUTHORITY="${HOME}/.Xauthority"
fi

wait_for_display() {
  local timeout="${WAIT_FOR_DISPLAY_TIMEOUT:-10}"
  local interval=1
  local deadline=$((SECONDS + timeout))
  local sockets

  while (( SECONDS < deadline )); do
    if xset q >/dev/null 2>&1; then
      return 0
    fi

    sockets=()
    while IFS= read -r -d '' socket; do
      sockets+=("${socket}")
    done < <( (find /tmp/.X11-unix -maxdepth 1 -type s -name 'X*' -print0 2>/dev/null) || true )

    if (( ${#sockets[@]} > 0 )); then
      local socket display
      for socket in "${sockets[@]}"; do
        display=":${socket##*/X}"
        export DISPLAY="${display}"
        if xset q >/dev/null 2>&1; then
          return 0
        fi
      done
    fi

    sleep "${interval}"
  done

  return 1
}

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

if ! wait_for_display; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: No se pudo detectar un servidor X tras ${WAIT_FOR_DISPLAY_TIMEOUT:-10} segundos." | tee -a "${LOG_FILE}" >&2
  exit 1
fi

"${PYTHON_BIN}" main.py "$@" 2>&1 | tee -a "${LOG_FILE}"
exit "${PIPESTATUS[0]}"
