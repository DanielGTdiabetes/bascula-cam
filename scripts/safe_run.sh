#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/safe_run.log"

mkdir -p "${LOG_DIR}"

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
