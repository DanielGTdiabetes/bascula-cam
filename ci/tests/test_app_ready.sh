#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_app_ready"
trap 'ci::finish' EXIT

dest="${DESTDIR:-/tmp/ci-root}"
unit="${dest}/etc/systemd/system/bascula-app.service"

ci::log "Validando condiciones APP_READY"
grep -q 'ConditionPathExists=/etc/bascula/APP_READY' "$unit"
grep -q 'ExecStartPre=.*/boot/bascula-recovery' "$unit"
grep -q 'ExecStartPre=.*/shared/userdata/force_recovery' "$unit"
grep -q 'ExecStartPre=.*/install -d -m 0700 -o pi -g pi /home/pi/.local/share/xorg' "$unit"

ci::log "test_app_ready completado"
