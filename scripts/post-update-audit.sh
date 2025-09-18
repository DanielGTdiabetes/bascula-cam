#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

declare -A RESULT_STATUS=()
declare -A RESULT_DETAIL=()

mkdir -p "$ROOT/audit"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$ROOT/audit/audit_${TIMESTAMP}.log"
SUMMARY_FILE="$ROOT/audit/SUMMARY.md"

log() { printf '[post-audit] %s\n' "$*"; }
warn() { printf '[post-audit][WARN] %s\n' "$*"; }

bash "$ROOT/scripts/verify-all.sh" | tee "$LOG_FILE"
audit_status=${PIPESTATUS[0]:-0}

while IFS= read -r line; do
  [[ "$line" == "[verify][RESULT] "* ]] || continue
  payload="${line#'[verify][RESULT] '}"
  name="${payload%%:*}"
  rest="${payload#*: }"
  status="${rest%% *}"
  RESULT_STATUS["$name"]="$status"
  RESULT_DETAIL["$name"]="$rest"
done <"$LOG_FILE"

steps=(
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

icon_for() {
  case "$1" in
    OK) printf '✅';;
    INFO) printf 'ℹ️';;
    WARN) printf '⚠️';;
    FAIL) printf '❌';;
    *) printf '⚠️';;
  esac
}

aggregate_status() {
  local status="OK"
  for name in "$@"; do
    local value="${RESULT_STATUS[$name]:-INFO}"
    if [[ "$value" == "FAIL" ]]; then
      status="FAIL"
      break
    elif [[ "$value" == "WARN" && "$status" != "FAIL" ]]; then
      status="WARN"
    elif [[ "$value" == "INFO" && "$status" == "OK" ]]; then
      status="INFO"
    fi
  done
  printf '%s' "$status"
}

printf '# Auditoría post-actualización (%s)\n\n' "$(date)" >"$SUMMARY_FILE"
printf '| Verificador | Estado |\n' >>"$SUMMARY_FILE"
printf '| --- | --- |\n' >>"$SUMMARY_FILE"
for name in "${steps[@]}"; do
  status="${RESULT_STATUS[$name]:-INFO}"
  detail="${RESULT_DETAIL[$name]:-$status}"
  icon="$(icon_for "$status")"
  printf '| %s | %s %s |\n' "$name" "$icon" "$detail" >>"$SUMMARY_FILE"
done

ui_status=$(aggregate_status py_compile verify-kiosk verify-scale smoke-nav smoke-mascot)
services_status=$(aggregate_status verify-services)
install_status=$(aggregate_status verify-installers)
voice_status=$(aggregate_status verify-piper)
miniweb_status=$(aggregate_status verify-miniweb)
ota_status=$(aggregate_status verify-ota)
x735_status=$(aggregate_status verify-x735)

summary_line() {
  local category="$1"
  local status="$2"
  local ok_msg="$3"
  local warn_msg="$4"
  local fail_msg="$5"
  local icon="$(icon_for "$status")"
  case "$status" in
    OK|INFO)
      printf -- '- %s **%s**: %s\n' "$icon" "$category" "$ok_msg" >>"$SUMMARY_FILE"
      ;;
    WARN)
      printf -- '- %s **%s**: %s\n' "$icon" "$category" "$warn_msg" >>"$SUMMARY_FILE"
      ;;
    FAIL)
      printf -- '- %s **%s**: %s\n' "$icon" "$category" "$fail_msg" >>"$SUMMARY_FILE"
      ;;
    *)
      printf -- '- %s **%s**: %s\n' "$icon" "$category" "$warn_msg" >>"$SUMMARY_FILE"
      ;;
  esac
}

printf '\n## Pistas rápidas\n' >>"$SUMMARY_FILE"
summary_line \
  "UI" \
  "$ui_status" \
  "Smokes y overlay sin errores." \
  "Revisa logs de verify-kiosk/verificar escala y dependencias Tk/X11." \
  "Corrige fallos en pantallas registradas o dependencias Tk." \

summary_line \
  "Servicios" \
  "$services_status" \
  "Unidades systemd presentes." \
  "Confirma rutas de unidades y variables DISPLAY/XAUTHORITY." \
  "Instala o corrige unidades systemd bascula-*." \

summary_line \
  "Instaladores" \
  "$install_status" \
  "Scripts set -euo pipefail y sintaxis OK." \
  "Ajusta permisos y rutas en instaladores." \
  "Revisa errores de sintaxis en instaladores." \

summary_line \
  "Voz" \
  "$voice_status" \
  "Modelos Piper detectados." \
  "Verifica /opt/piper/models y .default-voice." \
  "Vuelve a instalar modelos Piper o binario." \

summary_line \
  "Miniweb" \
  "$miniweb_status" \
  "Uvicorn y módulo miniweb disponibles." \
  "Instala uvicorn o revisa import de bascula.services.miniweb." \
  "Corrige errores al importar bascula.services.miniweb." \

summary_line \
  "OTA" \
  "$ota_status" \
  "ota.sh listo y repo limpio." \
  "Revisa git status y ejecución de ota.sh --help." \
  "Corrige ota.sh o el estado del repositorio." \

summary_line \
  "x735" \
  "$x735_status" \
  "Servicio y script detectados." \
  "Comprueba unidad x735-fan y script /usr/local/bin/x735.sh." \
  "Instala o habilita x735-fan.service y scripts asociados." \

log "Resumen disponible en $SUMMARY_FILE"
log "Log detallado en $LOG_FILE"

if command -v gh >/dev/null 2>&1 && [[ "${GITHUB_ACTIONS:-}" == "true" ]] && [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
  pr_number=""
  if [[ -n "${GITHUB_EVENT_PATH:-}" && -f "${GITHUB_EVENT_PATH}" ]]; then
    pr_number="$(python3 - <<'PY'
import json
import os
path = os.environ.get('GITHUB_EVENT_PATH')
if not path:
    raise SystemExit
with open(path, 'r', encoding='utf-8') as handle:
    data = json.load(handle)
number = data.get('number') or data.get('pull_request', {}).get('number')
if number:
    print(number)
PY
    )"
  fi
  if [[ -n "$pr_number" ]]; then
    if ! gh pr comment "$pr_number" --body-file "$SUMMARY_FILE"; then
      warn "No se pudo publicar comentario en PR #$pr_number"
    else
      log "Comentario publicado en PR #$pr_number"
    fi
  else
    warn 'No se pudo determinar el número de PR para comentar'
  fi
fi

exit "$audit_status"
