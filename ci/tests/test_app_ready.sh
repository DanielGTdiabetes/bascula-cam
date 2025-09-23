#!/usr/bin/env bash
set -euo pipefail
DEST="${DESTDIR:-/tmp/ci-root}"
UNIT="${DEST}/etc/systemd/system/bascula-app.service"

grep -q 'ConditionPathExists=/etc/bascula/APP_READY' "$UNIT"
grep -q 'ExecStartPre=.*/boot/bascula-recovery' "$UNIT"
grep -q 'ExecStartPre=.*/shared/userdata/force_recovery' "$UNIT"
grep -q 'ExecStartPre=.*/install -d -m 0700 -o pi -g pi /home/pi/.local/share/xorg' "$UNIT"

echo "[OK] test_app_ready"
