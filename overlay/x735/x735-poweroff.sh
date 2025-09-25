#!/usr/bin/env bash
set -euo pipefail

BUTTON_GPIO_NAME="${X735_BUTTON_GPIO_NAME:-GPIO17}"
POWER_COMMAND="${X735_POWER_COMMAND:-/sbin/poweroff}"
LOG_TAG="[x735-poweroff]"

log() {
  printf '%s %s\n' "${LOG_TAG}" "$*"
}

warn() {
  printf '%s WARNING: %s\n' "${LOG_TAG}" "$*" >&2
}

fatal() {
  printf '%s ERROR: %s\n' "${LOG_TAG}" "$*" >&2
  exit 1
}

require_binary() {
  local bin="$1"
  if ! command -v "${bin}" >/dev/null 2>&1; then
    fatal "${bin} no está disponible"
  fi
}

parse_gpio() {
  local name="$1"
  local out
  if ! out=$(gpiofind "${name}" 2>/dev/null); then
    fatal "gpiofind no encontró ${name}"
  fi
  printf '%s' "${out}"
}

trigger_poweroff() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl poweroff
  else
    "${POWER_COMMAND}" || /sbin/poweroff
  fi
}

require_binary gpiofind
require_binary gpiomon

GPIO_INFO=$(parse_gpio "${BUTTON_GPIO_NAME}")
GPIO_CHIP=${GPIO_INFO%% *}
GPIO_LINE=${GPIO_INFO##* }

if [[ -z "${GPIO_CHIP}" || -z "${GPIO_LINE}" ]]; then
  fatal "No se pudo resolver ${BUTTON_GPIO_NAME}"
fi

log "Monitoreando ${GPIO_CHIP} línea ${GPIO_LINE} para apagado seguro"

while true; do
  if OUTPUT=$(gpiomon --silent --num-events=1 --falling-edge "${GPIO_CHIP}" "${GPIO_LINE}" 2>&1); then
    log "Botón presionado, solicitando apagado"
    trigger_poweroff
    sleep 2
  else
    if [[ "${OUTPUT}" == *"Device or resource busy"* ]]; then
      warn "GPIO ${BUTTON_GPIO_NAME} ocupado. Probablemente el overlay gpio-shutdown ya maneja el botón"
      exec tail -f /dev/null
    fi
    warn "gpiomon falló: ${OUTPUT}"
    sleep 2
  fi
done
