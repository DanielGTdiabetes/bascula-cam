#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_app_unit"
trap 'ci::finish' EXIT

dest="${DESTDIR:-/tmp/ci-root}"
unit="${dest}/etc/systemd/system/bascula-app.service"

if [[ ! -f "${unit}" ]]; then
  ci::log "Unit bascula-app.service no encontrada en ${unit}"
  exit 1
fi

ci::log "Validando ExecStartPre"
grep -F "ExecStartPre=/bin/bash -lc 'test -f /boot/bascula-recovery" "${unit}" >/dev/null
grep -F "ExecStartPre=/bin/bash -lc 'test -f /opt/bascula/shared/userdata/force_recovery" "${unit}" >/dev/null
grep -F "ExecStartPre=/usr/bin/install -d -m 0700 -o pi -g pi /home/pi/.local/share/xorg" "${unit}" >/dev/null

ci::log "test_app_unit completado"
