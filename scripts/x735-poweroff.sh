#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

CONFIG_FILE="/etc/default/x735-poweroff"
if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

GPIO="${X735_POWER_BUTTON_GPIO:-4}"
ACTIVE_LEVEL="${X735_POWER_BUTTON_ACTIVE:-0}"
DEBOUNCE_SECONDS="${X735_DEBOUNCE_SECONDS:-2}"
POLL_SECONDS="${X735_POLL_SECONDS:-1}"
POWER_COMMAND="${X735_POWER_COMMAND:-/sbin/poweroff}"
LOW_VOLTAGE="${X735_LOW_VOLTAGE_MV:-5000}"

GPIO_PATH="/sys/class/gpio/gpio${GPIO}"

log() {
  printf '[x735-poweroff] %s\n' "$*"
  command -v logger >/dev/null 2>&1 && logger -t x735-poweroff -- "$*" || true
}

export_gpio() {
  if [[ ! -e "${GPIO_PATH}" ]]; then
    echo "${GPIO}" > /sys/class/gpio/export
  fi
  for _ in {1..10}; do
    [[ -e "${GPIO_PATH}/direction" ]] && break
    sleep 0.1
  done
  if [[ ! -e "${GPIO_PATH}/direction" ]]; then
    log "GPIO ${GPIO} no disponible"
    exit 1
  fi
  echo "in" > "${GPIO_PATH}/direction"
}

read_gpio() {
  cat "${GPIO_PATH}/value"
}

main_loop() {
  log "Monitorizando GPIO ${GPIO} (activo=${ACTIVE_LEVEL}) con umbral ${LOW_VOLTAGE} mV"
  while true; do
    local value
    value="$(read_gpio)"
    if [[ "${value}" == "${ACTIVE_LEVEL}" ]]; then
      sleep "${DEBOUNCE_SECONDS}"
      value="$(read_gpio)"
      if [[ "${value}" == "${ACTIVE_LEVEL}" ]]; then
        log "Solicitud de apagado detectada; ejecutando ${POWER_COMMAND}"
        read -r -a cmd <<<"${POWER_COMMAND}"
        if [[ ${#cmd[@]} -eq 0 ]]; then
          cmd=(/sbin/poweroff)
        fi
        "${cmd[@]}" &
        wait "$!" || true
        sleep 2
        break
      fi
    fi
    sleep "${POLL_SECONDS}"
  done
}

main() {
  export_gpio
  main_loop
}

main "$@"
