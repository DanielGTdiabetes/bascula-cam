#!/usr/bin/env bash
set -euo pipefail
export BASCULA_CI=1
export DESTDIR="${DESTDIR:-/tmp/ci-root}"
export PATH="$(pwd)/ci/mocks:$PATH"
LOG="/tmp/ci-logs/safe_run_test.log"; mkdir -p /tmp/ci-logs

cp scripts/safe_run.sh /tmp/safe_run.sh
chmod +x /tmp/safe_run.sh

TMP=/tmp/bascula_force_recovery
PERSIST="${DESTDIR}/opt/bascula/shared/userdata/force_recovery"
BOOT="${DESTDIR}/boot/bascula-recovery"
mkdir -p "$(dirname "$PERSIST")" "$(dirname "$BOOT")"

/bin/rm -f "$TMP" "$PERSIST" "$BOOT"

# A) Arranque sin flags debe limpiar TEMP obsoleto
touch "$TMP"
( /tmp/safe_run.sh check >/dev/null 2>&1 || true )
test ! -f "$TMP" || { echo "TEMP no limpiado" | tee -a "$LOG"; exit 1; }

# B) Watchdog dispara recovery: crea TEMP y si systemctl denegado -> exit != 0
export CI_REQUIRE_ROOT_FOR_SYSTEMCTL=1
if /tmp/safe_run.sh trigger; then
  echo "Se esperaba fallo cuando systemctl denegado" | tee -a "$LOG"
  exit 1
fi
test -f "$TMP" || { echo "TEMP no creado tras trigger" | tee -a "$LOG"; exit 1; }

# C) Persistente: NO crea TEMP y si mock permite -> exit 0
> "$PERSIST"
export CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0
/tmp/safe_run.sh trigger
test ! -f "$TMP" || { echo "TEMP creado cuando existe flag persistente" | tee -a "$LOG"; exit 1; }

rm -f /tmp/safe_run.sh

echo "[OK] test_safe_run" | tee -a "$LOG"
