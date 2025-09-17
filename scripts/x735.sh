#!/usr/bin/env bash
set -euo pipefail

LOG() { printf '[x735] %s\n' "$*"; }
WARN() { printf '[warn] %s\n' "$*"; }

FAN_PIN="${X735_FAN_PIN:-18}"
BUTTON_PIN="${X735_BUTTON_PIN:-26}"
POWER_PIN="${X735_POWER_PIN:-4}"
FAN_ON_TEMP="${X735_FAN_ON:-60}"
FAN_OFF_TEMP="${X735_FAN_OFF:-50}"
BUTTON_HOLD_SEC="${X735_BUTTON_HOLD:-3}"

command -v raspi-gpio >/dev/null 2>&1 || { WARN "raspi-gpio no disponible"; exit 0; }

setup_pins() {
  raspi-gpio set "${FAN_PIN}" op dl
  raspi-gpio set "${POWER_PIN}" op dh
  raspi-gpio set "${BUTTON_PIN}" ip pu
}

read_temp() {
  if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp 2>/dev/null | sed -E 's/.*=([0-9]+\.?[0-9]*).*/\1/'
  elif [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
    awk '{ printf "%.1f", $1/1000 }' /sys/class/thermal/thermal_zone0/temp
  else
    echo "0"
  fi
}

fan_state=0
set_fan() {
  local new_state="$1"
  if [[ "${new_state}" -eq 1 && "${fan_state}" -ne 1 ]]; then
    raspi-gpio set "${FAN_PIN}" op dh
    fan_state=1
    LOG "Ventilador encendido"
  elif [[ "${new_state}" -eq 0 && "${fan_state}" -ne 0 ]]; then
    raspi-gpio set "${FAN_PIN}" op dl
    fan_state=0
    LOG "Ventilador apagado"
  fi
}

button_pressed() {
  raspi-gpio get "${BUTTON_PIN}" 2>/dev/null | grep -q 'level=0'
}

setup_pins
LOG "Controlador X735 iniciado (fan pin=${FAN_PIN})"

hold_counter=0
while true; do
  temp="$(read_temp)"
  if [[ "${temp%.*}" -ge "${FAN_ON_TEMP}" ]]; then
    set_fan 1
  elif [[ "${temp%.*}" -le "${FAN_OFF_TEMP}" ]]; then
    set_fan 0
  fi

  if button_pressed; then
    hold_counter=$((hold_counter + 1))
    if [[ "${hold_counter}" -ge "${BUTTON_HOLD_SEC}" ]]; then
      LOG "Botón de apagado mantenido; enviando poweroff"
      systemctl poweroff
    fi
  else
    hold_counter=0
  fi

  sleep 1
done
