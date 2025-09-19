#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/ui.log"
ROTATED_LOG="${LOG_FILE}.1"
MAX_SIZE=$((5 * 1024 * 1024))
WAIT_TIMEOUT=30
DISPLAY_SOCKET="/tmp/.X11-unix/X0"
DEFAULT_DISPLAY=":0"
DEFAULT_XAUTH="/home/pi/.Xauthority"

mkdir -p "${LOG_DIR}"
if [[ -f "${LOG_FILE}" ]]; then
  size=$(stat -c '%s' "${LOG_FILE}" 2>/dev/null || echo 0)
  if (( size > MAX_SIZE )); then
    mv "${LOG_FILE}" "${ROTATED_LOG}" 2>/dev/null || true
  fi
fi

touch "${LOG_FILE}"

log_msg() {
  local level="$1"
  shift
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '%s [%s] %s\n' "${timestamp}" "${level}" "$*" | tee -a "${LOG_FILE}"
}

cd "${REPO_ROOT}"

if [[ -f /etc/bascula/bascula.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/bascula/bascula.env
  set +a
fi

if [[ -z "${XAUTHORITY:-}" ]]; then
  export XAUTHORITY="${DEFAULT_XAUTH}"
fi

wait_for_display() {
  local deadline
  deadline=$((SECONDS + WAIT_TIMEOUT))
  while (( SECONDS < deadline )); do
    if [[ -S "${DISPLAY_SOCKET}" ]]; then
      export DISPLAY="${DEFAULT_DISPLAY}"
      return 0
    fi
    sleep 1
  done
  return 1
}

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

need_headless=false
if wait_for_display; then
  tmp_out="$(mktemp)"
  trap 'rm -f "${tmp_out}"' EXIT
  "${PYTHON_BIN}" main.py "$@" 2>&1 | tee -a "${LOG_FILE}" | tee "${tmp_out}"
  exit_code=${PIPESTATUS[0]}
  if (( exit_code != 0 )) && grep -qiE 'tclerror|tkinter' "${tmp_out}"; then
    log_msg "WARNING" "Fallo de Tk detectado (exit ${exit_code}). Reintentando en modo headless."
    need_headless=true
  elif (( exit_code != 0 )); then
    exit "${exit_code}"
  else
    exit 0
  fi
  rm -f "${tmp_out}"
  trap - EXIT
else
  log_msg "WARNING" "No se detectó un servidor X tras ${WAIT_TIMEOUT}s. Ejecutando en modo headless."
  need_headless=true
fi

if ${need_headless}; then
  "${PYTHON_BIN}" main.py --headless "$@" 2>&1 | tee -a "${LOG_FILE}"
  exit "${PIPESTATUS[0]}"
fi
