#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATUS=0

declare -A STEP_STATUS=()
declare -A STEP_DETAIL=()

RESULT_ORDER=(
  "py_compile"
  "verify-installers"
  "verify-services"
  "verify-kiosk"
  "verify-scale"
  "verify-piper"
  "verify-miniweb"
  "verify-ota"
  "verify-x735"
  "smoke-nav"
  "smoke-mascot"
)

log_result() {
  local name="$1"
  local status="$2"
  local detail="$3"
  STEP_STATUS["$name"]="$status"
  STEP_DETAIL["$name"]="$detail"
  printf '[verify][RESULT] %s: %s%s\n' "$name" "$status" "${detail:+ ($detail)}"
}

run_step() {
  local name="$1"
  shift
  local tmp
  tmp="$(mktemp)"
  local exit_code=0
  "${@}" > >(tee "$tmp") 2> >(tee -a "$tmp" >&2) || exit_code=$?

  local status detail
  if (( exit_code != 0 )); then
    status="FAIL"
    detail="exit ${exit_code}"
    STATUS=1
  else
    local has_warn has_err
    if grep -qi '\[warn' "$tmp"; then
      has_warn=1
    else
      has_warn=0
    fi
    if grep -qi '\[err' "$tmp"; then
      has_err=1
    else
      has_err=0
    fi
    if (( has_err )); then
      status="WARN"
      detail="errores reportados"
    elif (( has_warn )); then
      status="WARN"
      detail="avisos"
    else
      status="OK"
      detail="OK"
    fi
  fi
  log_result "$name" "$status" "$detail"
  rm -f "$tmp"
}

# Python syntax
mapfile -t PY_FILES < <(git ls-files '*.py')
if (( ${#PY_FILES[@]} == 0 )); then
  log_result "py_compile" "INFO" "sin archivos"
else
  run_step "py_compile" python3 -m py_compile "${PY_FILES[@]}"
fi

run_step "verify-installers" bash scripts/verify-installers.sh
run_step "verify-services" bash scripts/verify-services.sh
run_step "verify-kiosk" bash scripts/verify-kiosk.sh
run_step "verify-scale" bash scripts/verify-scale.sh
run_step "verify-piper" bash scripts/verify-piper.sh
run_step "verify-miniweb" bash scripts/verify-miniweb.sh
run_step "verify-ota" bash scripts/verify-ota.sh
run_step "verify-x735" bash scripts/verify-x735.sh
run_step "smoke-nav" python3 tools/smoke_nav.py
run_step "smoke-mascot" python3 tools/smoke_mascot.py

printf '\n[verify] Resumen general:\n'
for name in "${RESULT_ORDER[@]}"; do
  status="${STEP_STATUS[$name]:-INFO}"
  detail="${STEP_DETAIL[$name]:-}"
  printf ' - %-16s %s%s\n' "$name" "$status" "${detail:+ ($detail)}"
  if [[ "$status" == "FAIL" ]]; then
    STATUS=1
  fi
done

if (( STATUS == 0 )); then
  printf '\n[verify] Auditoría completada sin fallos críticos\n'
else
  printf '\n[verify][WARN] Auditoría con incidencias\n'
fi

exit "$STATUS"
