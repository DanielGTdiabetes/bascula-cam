#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

bash "${SCRIPT_DIR}/install-1-system.sh"
bash "${SCRIPT_DIR}/install-2-app.sh" "$@"
