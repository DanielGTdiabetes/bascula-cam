#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/safe_run.log"

mkdir -p "${LOG_DIR}"

log_msg() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$1" >>"${LOG_FILE}"
}

if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
  export DISPLAY=:0
  log_msg "DISPLAY no definido, usando DISPLAY=:0"
fi

if [[ -z "${XAUTHORITY:-}" ]]; then
  export XAUTHORITY="${HOME}/.Xauthority"
  log_msg "XAUTHORITY no definido, usando ${XAUTHORITY}"
fi

cd "${REPO_ROOT}"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

if output=$(python3 main.py "$@" 2>&1); then
  printf '%s\n' "$output"
  exit 0
else
  status=$?
  printf '%s\n' "$output" >&2
  {
    printf '[%s] bascula main.py failed with exit code %s\n' "$(date --iso-8601=seconds)" "$status"
    printf '%s\n' "$output"
    printf '\n'
  } >>"${LOG_FILE}"
  exit "$status"
fi
