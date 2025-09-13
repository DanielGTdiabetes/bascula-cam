#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Forward TARGET_USER if provided, else let install-all.sh default to SUDO_USER or pi
if [[ -n "${TARGET_USER:-}" ]]; then
  exec sudo PHASE=1 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"
else
  exec sudo PHASE=1 bash "${SCRIPT_DIR}/install-all.sh" "$@"
fi
