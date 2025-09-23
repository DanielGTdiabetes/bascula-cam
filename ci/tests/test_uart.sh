#!/usr/bin/env bash
set -euo pipefail

root_dir="$(pwd)"
dest="${DESTDIR:-/tmp/ci-root}"
rm -rf "${dest}/boot"
mkdir -p "${dest}/boot"
cp ci/fixtures/boot/config.txt "${dest}/boot/config.txt"

export BASCULA_CI=1
export DESTDIR="${dest}"
export SYSTEMCTL="${root_dir}/ci/mocks/systemctl"
export BASCULA_CI_LOGDIR="${BASCULA_CI_LOGDIR:-/tmp/ci-logs}"
mkdir -p "${BASCULA_CI_LOGDIR}"
rm -f "${BASCULA_CI_LOGDIR}/systemctl.log"

bash scripts/install-1-system.sh --apply-uart

cfg="${dest}/boot/config.txt"
grep -Fx 'enable_uart=1' "${cfg}" >/dev/null
grep -Fx 'dtoverlay=disable-bt' "${cfg}" >/dev/null

log_file="${BASCULA_CI_LOGDIR:-/tmp/ci-logs}/systemctl.log"
for svc in hciuart.service serial-getty@ttyAMA0.service serial-getty@ttyS0.service serial-getty@serial0.service; do
  grep -F "disable --now ${svc}" "${log_file}" >/dev/null
done

echo "[test_uart] ok"
