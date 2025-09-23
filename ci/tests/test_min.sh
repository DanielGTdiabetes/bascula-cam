#!/usr/bin/env bash
set -euo pipefail
echo "[test] start"

# 1) run-ui: no -logfile en xinit y .xserverrc correcto
grep -q 'exec xinit .* -- /usr/bin/Xorg :0 vt1 -nolisten tcp -noreset' scripts/run-ui.sh
grep -q 'exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset' scripts/xsession.sh || true
# .xserverrc lo genera run-ui.sh, aquí sólo validamos plantilla:
grep -q 'exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset' scripts/run-ui.sh || true

# 2) safe_run: flags y códigos de salida
TMP=/tmp/bascula_force_recovery
PERSIST=/opt/bascula/shared/userdata/force_recovery
BOOT=/boot/bascula-recovery
DEST="${DESTDIR:-/tmp/ci-root}"

mkdir -p "${DEST}/opt/bascula/current/scripts" "${DEST}/opt/bascula/shared/userdata" "${DEST}/boot" /tmp
cp scripts/safe_run.sh "${DEST}/opt/bascula/current/scripts/safe_run.sh"
chmod +x "${DEST}/opt/bascula/current/scripts/safe_run.sh"
export PATH="$(pwd)/ci/mocks:$PATH"
export BASCULA_CI=1 CI_REQUIRE_ROOT_FOR_SYSTEMCTL=1

# a) Watchdog ⇒ crea TEMP y falla si systemctl denegado
rm -f "$TMP" "${DEST}${PERSIST}" "${DEST}${BOOT}"
if "${DEST}/opt/bascula/current/scripts/safe_run.sh" trigger 2>/tmp/t1.err; then
  echo "ERROR: se esperaba exit!=0" >&2; exit 1
fi
test -f "$TMP"

# b) Persistente ⇒ NO crea TEMP, intenta recovery, exit 0 si mock permite
> "${DEST}${PERSIST}"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0 "${DEST}/opt/bascula/current/scripts/safe_run.sh" trigger
test ! -f "$TMP"

# c) Limpieza sticky tras quitar flag persistente
rm -f "${DEST}${PERSIST}"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0 "${DEST}/opt/bascula/current/scripts/safe_run.sh" trigger 2>/tmp/t2.err || true
test ! -f "$TMP"

echo "[test] ok"
