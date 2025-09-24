#!/usr/bin/env bash
set -euo pipefail

APP="${APP:-/opt/bascula/current}"
SCRIPT="${APP}/scripts/run-ui.sh"
if [[ ! -x "${SCRIPT}" ]]; then
  echo "bascula-app: no se encontró ${SCRIPT}" >&2
  exit 1
fi
exec "${SCRIPT}"
