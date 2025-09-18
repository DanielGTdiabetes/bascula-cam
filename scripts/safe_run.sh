#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/ui.log"
ROTATED_LOG="${LOG_FILE}.1"
MAX_SIZE=$((5 * 1024 * 1024))

cd "${REPO_ROOT}"

if [[ -d ".venv" && -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
  export DISPLAY=:0
fi

if [[ -z "${XAUTHORITY:-}" ]]; then
  export XAUTHORITY="${HOME}/.Xauthority"
fi

mkdir -p "${LOG_DIR}"
if [[ -f "${LOG_FILE}" ]]; then
  current_size=$(stat -c '%s' "${LOG_FILE}" 2>/dev/null || echo 0)
  if (( current_size > MAX_SIZE )); then
    mv "${LOG_FILE}" "${ROTATED_LOG}" 2>/dev/null || true
  fi
fi

touch "${LOG_FILE}"

max_attempts=2
attempt=1
exit_code=0

while (( attempt <= max_attempts )); do
  python3 main.py "$@" 2>&1 | tee -a "${LOG_FILE}"
  exit_code=${PIPESTATUS[0]}

  if (( exit_code == 0 )); then
    break
  fi

  printf '%s\n' "${exit_code}" > "${LOG_DIR}/last_exit_code"
  if (( attempt == max_attempts )); then
    break
  fi

  backoff=$((3 * attempt))
  printf 'Reintentando en %ss...\n' "${backoff}" | tee -a "${LOG_FILE}"
  sleep "${backoff}"
  ((attempt++))
done

if (( exit_code == 0 )); then
  rm -f "${LOG_DIR}/last_exit_code"
fi

exit "${exit_code}"
