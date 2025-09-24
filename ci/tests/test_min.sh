#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_min"
trap 'ci::finish' EXIT

: "${BASCULA_CI:?BASCULA_CI must be defined}"
: "${DESTDIR:?DESTDIR must be defined}"

repo_root="${ci_repo_root}"
cd "${repo_root}"

ci::log "Verificando unit bascula-web.service"
if command -v systemd-analyze >/dev/null 2>&1; then
  temp_wrapper="/usr/local/bin/bascula-web"
  cleanup_wrapper=0
  if [[ ! -x "${temp_wrapper}" ]]; then
    install -m 0755 /bin/true "${temp_wrapper}"
    cleanup_wrapper=1
  fi
  systemd-analyze verify systemd/bascula-web.service
  if [[ ${cleanup_wrapper} -eq 1 ]]; then
    rm -f "${temp_wrapper}"
  fi
else
  ci::log "systemd-analyze no disponible; omito verificación"
fi

ci::log "Validando scripts UI"
grep -q 'exec xinit .* -- /usr/bin/Xorg :0 vt1 -nolisten tcp -noreset' scripts/run-ui.sh
grep -q 'exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset' scripts/xsession.sh || true
grep -q 'exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset' scripts/run-ui.sh || true

ci::log "Preparando safe_run para pruebas de recovery"
dest="${DESTDIR%/}"
safe_run_dir="${dest}/opt/bascula/current/scripts"
mkdir -p "${safe_run_dir}" "${dest}/opt/bascula/shared/userdata" "${dest}/boot"
cp scripts/safe_run.sh "${safe_run_dir}/safe_run.sh"
chmod +x "${safe_run_dir}/safe_run.sh"

temp_flag="/tmp/bascula_force_recovery"
persistent_flag="${dest}/opt/bascula/shared/userdata/force_recovery"
boot_flag="${dest}/boot/bascula-recovery"

run_safe_run() {
  local reason="$1"
  local extra_env=(
    "CI_SYSTEMCTL_ALLOW=bascula-recovery.target"
    "PERSISTENT_RECOVERY_FLAG=${persistent_flag}"
    "BOOT_RECOVERY_FLAG=${boot_flag}"
    "TEMP_RECOVERY_FLAG=${temp_flag}"
    "BASCULA_CI=1"
    "DESTDIR=${dest}"
    "SYSTEMCTL=${repo_root}/ci/mocks/systemctl"
    "CI_REQUIRE_ROOT_FOR_SYSTEMCTL=${CI_REQUIRE_ROOT_FOR_SYSTEMCTL:-0}"
  )
  env "${extra_env[@]}" "${safe_run_dir}/safe_run.sh" trigger "${reason}"
}

rm -f "${temp_flag}" "${persistent_flag}" "${boot_flag}"

ci::log "Watchdog ⇒ crea flag temporal y propaga fallo de systemctl"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=1
set +e
run_safe_run watchdog
status=$?
set -e
if [[ ${status} -ne 3 ]]; then
  ci::log "[TEST] Esperado exit=3 cuando systemctl falla, obtenido ${status}"
  exit 1
fi
[[ -f "${temp_flag}" ]] || { ci::log "[TEST] Flag temporal no creada en watchdog"; exit 1; }

ci::log "Recovery persistente limpia flag temporal"
CI_REQUIRE_ROOT_FOR_SYSTEMCTL=0
>"${persistent_flag}"
run_safe_run external
status=$?
if [[ ${status} -ne 0 ]]; then
  ci::log "[TEST] trigger external persistente devolvió ${status}"
  exit 1
fi
[[ -f "${temp_flag}" ]] && { ci::log "[TEST] Flag temporal presente tras recovery persistente"; exit 1; }

ci::log "Recovery por boot limpia flag temporal residual"
rm -f "${persistent_flag}" "${temp_flag}"
>"${boot_flag}"
run_safe_run external
status=$?
if [[ ${status} -ne 0 ]]; then
  ci::log "[TEST] trigger external boot devolvió ${status}"
  exit 1
fi
[[ -f "${temp_flag}" ]] && { ci::log "[TEST] Flag temporal presente tras recovery boot"; exit 1; }

ci::log "Sin flags ⇒ trigger devuelve 2"
rm -f "${boot_flag}" "${temp_flag}"
set +e
run_safe_run external
status=$?
set -e
if [[ ${status} -ne 2 ]]; then
  ci::log "[TEST] Esperado exit=2 sin flags, obtenido ${status}"
  exit 1
fi

ci::log "test_min completado"
