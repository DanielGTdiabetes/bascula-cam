#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec sudo PHASE=2 bash "${SCRIPT_DIR}/install-all.sh" "$@"

