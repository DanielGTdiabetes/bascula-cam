#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_uart"
trap 'ci::finish' EXIT

root_dir="${ci_repo_root}"
dest="${DESTDIR:-/tmp/ci-root}"
rm -rf "${dest}/boot"
mkdir -p "${dest}/boot"
cp "${root_dir}/ci/fixtures/boot/config.txt" "${dest}/boot/config.txt"

export BASCULA_CI=1 DESTDIR="${dest}" SYSTEMCTL="${root_dir}/ci/mocks/systemctl"
export BASCULA_CI_LOGDIR="${BASCULA_CI_LOGDIR:-${root_dir}/ci-logs}"
mkdir -p "${BASCULA_CI_LOGDIR}"
rm -f "${BASCULA_CI_LOGDIR}/systemctl.log"

ci::log "Aplicando configuración UART"
bash "${root_dir}/scripts/install-1-system.sh" --apply-uart

cfg="${dest}/boot/config.txt"
grep -Fx 'enable_uart=1' "${cfg}" >/dev/null
grep -Fx 'dtoverlay=disable-bt' "${cfg}" >/dev/null

log_file="${BASCULA_CI_LOGDIR}/systemctl.log"
for svc in hciuart.service serial-getty@ttyAMA0.service serial-getty@ttyS0.service serial-getty@serial0.service; do
  grep -F "disable --now ${svc}" "${log_file}" >/dev/null
done

ci::log "test_uart completado"
