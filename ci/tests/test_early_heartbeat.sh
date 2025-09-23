#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_early_heartbeat"
trap 'ci::finish' EXIT

if ! grep -RInq 'early heartbeat' "${ci_repo_root}/bascula/ui"; then
  ci::log "Falta comentario/emitir early heartbeat"
  exit 1
fi

ci::log "test_early_heartbeat completado"
