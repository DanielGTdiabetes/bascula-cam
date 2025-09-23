#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_safe_run"
trap 'ci::finish' EXIT

dest="${DESTDIR:-/tmp/ci-root}"
repo_root="${ci_repo_root}"
safe_run="${dest}/opt/bascula/current/scripts/safe_run.sh"
mkdir -p "$(dirname "${safe_run}")" "${dest}/opt/bascula/shared/userdata" "${dest}/boot"
cp "${repo_root}/scripts/safe_run.sh" "${safe_run}"
chmod +x "${safe_run}"

temp_flag="/tmp/bascula_force_recovery"
persistent_flag="${dest}/opt/bascula/shared/userdata/force_recovery"
boot_flag="${dest}/boot/bascula-recovery"

common_env=(
  "BASCULA_CI=1"
  "DESTDIR=${dest}"
  "SYSTEMCTL=${repo_root}/ci/mocks/systemctl"
  "CI_SYSTEMCTL_ALLOW=bascula-recovery.target"
  "PERSISTENT_RECOVERY_FLAG=${persistent_flag}"
  "BOOT_RECOVERY_FLAG=${boot_flag}"
  "TEMP_RECOVERY_FLAG=${temp_flag}"
)

ci::log "Limpieza inicial de flags"
rm -f "${temp_flag}" "${persistent_flag}" "${boot_flag}"

ci::log "check elimina flag temporal obsoleta"
>"${temp_flag}"
env "${common_env[@]}" "${safe_run}" check >/dev/null 2>&1 || true
[[ -f "${temp_flag}" ]] && { ci::log "[TEST] Flag temporal no eliminada por check"; exit 1; }

ci::log "trigger watchdog crea flag temporal y falla si systemctl falla"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=1 env "${common_env[@]}" \
  "CI_REQUIRE_ROOT_FOR_SYSTEMCTL=1" "${safe_run}" trigger watchdog && {
    ci::log "[TEST] trigger watchdog debería fallar con systemctl denegado"
    exit 1
  }
[[ -f "${temp_flag}" ]] || { ci::log "[TEST] Flag temporal no creada en watchdog"; exit 1; }

ci::log "trigger external limpia flag temporal"
>"${persistent_flag}"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0 env "${common_env[@]}" \
  "CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0" "${safe_run}" trigger external
status=$?
if [[ ${status} -ne 0 ]]; then
  ci::log "[TEST] trigger external devolvió ${status}"
  exit 1
fi
[[ -f "${temp_flag}" ]] && { ci::log "[TEST] Flag temporal persiste tras external"; exit 1; }

ci::log "trigger watchdog success cuando mock permite"
rm -f "${persistent_flag}" "${boot_flag}" "${temp_flag}"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0 env "${common_env[@]}" \
  "CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0" "${safe_run}" trigger watchdog
status=$?
if [[ ${status} -ne 0 ]]; then
  ci::log "[TEST] trigger watchdog debería devolver 0, obtuvo ${status}"
  exit 1
fi
[[ -f "${temp_flag}" ]] || { ci::log "[TEST] Flag temporal no creada en watchdog exitoso"; exit 1; }

ci::log "test_safe_run completado"
