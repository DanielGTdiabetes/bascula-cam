#!/usr/bin/env bash
set -euo pipefail

FAN_GPIO_NAME="${X735_FAN_GPIO_NAME:-GPIO18}"
FAN_TEMP_ON="${X735_FAN_TEMP_ON:-55}"
FAN_TEMP_OFF="${X735_FAN_TEMP_OFF:-48}"
FAN_POLL_INTERVAL="${X735_FAN_POLL_INTERVAL:-5}"
LOG_TAG="[x735-fan]"

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

parse_gpiofind() {
  local name="$1"
  local out
  if ! out=$(gpiofind "${name}" 2>/dev/null); then
    fatal "gpiofind no encontró ${name}"
  fi
  printf '%s' "${out}"
}

read_temperature() {
  local raw
  if command -v vcgencmd >/dev/null 2>&1; then
    raw=$(vcgencmd measure_temp 2>/dev/null || true)
    raw=${raw#temp=}
    raw=${raw%%'*C'*}
    raw=${raw//[^0-9.]/}
    if [[ -n "${raw}" ]]; then
      printf '%d' "${raw%%.*}"
      return 0
    fi
  fi

  if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
    raw=$(< /sys/class/thermal/thermal_zone0/temp)
    if [[ -n "${raw}" ]]; then
      printf '%d' $((raw / 1000))
      return 0
    fi
  fi

  return 1
}

cleanup() {
  stop_fan || true
}

start_fan() {
  if [[ -n "${FAN_PID:-}" ]] && kill -0 "${FAN_PID}" 2>/dev/null; then
    return 0
  fi

  gpioset --mode=signal --consumer="x735-fan" "${GPIO_CHIP}" "${GPIO_LINE}=1" &
  FAN_PID=$!
  sleep 0.1
  if ! kill -0 "${FAN_PID}" 2>/dev/null; then
    wait "${FAN_PID}" || true
    FAN_PID=""
    return 1
  fi
  return 0
}

stop_fan() {
  if [[ -n "${FAN_PID:-}" ]]; then
    if kill -0 "${FAN_PID}" 2>/dev/null; then
      kill "${FAN_PID}" 2>/dev/null || true
      wait "${FAN_PID}" 2>/dev/null || true
    fi
    FAN_PID=""
  fi
  gpioset "${GPIO_CHIP}" "${GPIO_LINE}=0" >/dev/null 2>&1 || true
}

require_binary gpioset
require_binary gpiofind

GPIO_INFO=$(parse_gpiofind "${FAN_GPIO_NAME}")
GPIO_CHIP=${GPIO_INFO%% *}
GPIO_LINE=${GPIO_INFO##* }

if [[ -z "${GPIO_CHIP}" || -z "${GPIO_LINE}" ]]; then
  fatal "No se pudo resolver ${FAN_GPIO_NAME}"
fi

if ! INIT_OUTPUT=$(gpioset "${GPIO_CHIP}" "${GPIO_LINE}=0" 2>&1); then
  if [[ "${INIT_OUTPUT}" == *"Device or resource busy"* ]]; then
    warn "GPIO ${FAN_GPIO_NAME} ocupado. Revisa overlays duplicados en config.txt"
  else
    warn "gpioset falló: ${INIT_OUTPUT}"
  fi
  exec tail -f /dev/null
fi

trap cleanup EXIT INT TERM

log "Usando ${GPIO_CHIP} línea ${GPIO_LINE} (on>=${FAN_TEMP_ON}°C, off<=${FAN_TEMP_OFF}°C)"

temp_failures=0
fan_state=0
while true; do
  if ! temp=$(read_temperature); then
    if (( temp_failures == 0 )); then
      warn "No se pudo leer temperatura del SoC"
    fi
    temp_failures=$((temp_failures + 1))
    sleep "${FAN_POLL_INTERVAL}"
    continue
  fi
  temp_failures=0

  if (( temp >= FAN_TEMP_ON )); then
    if (( fan_state == 0 )); then
      if start_fan; then
        log "Ventilador activado a ${temp}°C"
        fan_state=1
      else
        warn "No se pudo activar el ventilador"
      fi
    fi
  elif (( fan_state == 1 && temp <= FAN_TEMP_OFF )); then
    stop_fan
    log "Ventilador detenido a ${temp}°C"
    fan_state=0
  fi

  sleep "${FAN_POLL_INTERVAL}"
done
