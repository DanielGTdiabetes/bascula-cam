#!/usr/bin/env bash
set -euo pipefail

dest="${DESTDIR:-/tmp/ci-root}"
unit="${dest}/etc/systemd/system/bascula-app.service"

if [[ ! -f "${unit}" ]]; then
  echo "[ERR] Unit bascula-app.service no encontrada en ${unit}" >&2
  exit 1
fi

grep -F "ExecStartPre=/bin/bash -lc 'test -f /boot/bascula-recovery" "${unit}" >/dev/null
grep -F "ExecStartPre=/bin/bash -lc 'test -f /opt/bascula/shared/userdata/force_recovery" "${unit}" >/dev/null
grep -F "ExecStartPre=/usr/bin/install -d -m 0700 -o pi -g pi /home/pi/.local/share/xorg" "${unit}" >/dev/null

echo "[test_app_unit] ok"
