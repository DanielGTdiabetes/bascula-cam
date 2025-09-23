#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_x735"
trap 'ci::finish' EXIT

dest="${DESTDIR:-/tmp/ci-root}"
unit="${dest}/etc/systemd/system/x735-poweroff.service"
rm -f "${unit}"
mkdir -p "$(dirname "${unit}")"

export BASCULA_CI=1 DESTDIR="${dest}"

ci::log "Renderizando servicio x735"
bash "${ci_repo_root}/scripts/install-1-system.sh" --render-x735-service 5000

grep -Fx 'User=root' "${unit}" >/dev/null
grep -F -- '--threshold 5000' "${unit}" >/dev/null

ci::log "test_x735 completado"
