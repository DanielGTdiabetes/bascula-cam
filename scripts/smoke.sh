#!/usr/bin/env bash
set -euo pipefail

log() { printf '[SMOKE] %s\n' "$*"; }
warn() { printf '[WARN ] %s\n' "$*"; }
info() { printf '[INFO ] %s\n' "$*"; }
err() { printf '[ERR  ] %s\n' "$*"; }

if command -v systemctl >/dev/null 2>&1; then
  for svc in bascula-app bascula-web bascula-net-fallback; do
    if systemctl list-unit-files "${svc}.service" >/dev/null 2>&1; then
      if ! systemctl is-enabled --quiet "${svc}.service"; then
        err "${svc}.service no está habilitado"
        exit 1
      fi
      if ! systemctl is-active --quiet "${svc}.service"; then
        err "${svc}.service no está activo"
        systemctl status "${svc}.service" --no-pager || true
        exit 1
      fi
    else
      warn "${svc}.service no encontrado"
    fi
  done
else
  warn "systemctl no disponible; se omiten comprobaciones de servicios"
fi

if [[ ! -f /etc/default/bascula ]]; then
  warn "/etc/default/bascula no encontrado; usando puerto por defecto"
fi

# Verificación de integración con modo recovery
check_recovery_unit() {
  if ! systemctl list-unit-files bascula-app.service >/dev/null 2>&1; then
    return
  fi
  if ! systemctl cat bascula-app.service 2>/dev/null | grep -q 'OnFailure=bascula-recovery.target'; then
    err "bascula-app.service no apunta a bascula-recovery.target"
    exit 1
  fi
  info "OnFailure=bascula-recovery.target configurado"
}

trigger_recovery_with_flag() {
  local flag="$1"
  if ! systemctl list-unit-files bascula-recovery.service >/dev/null 2>&1; then
    warn "bascula-recovery.service no encontrado; se omite prueba de ${flag}"
    return
  fi
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    warn "Se requieren privilegios de root para probar ${flag}. Se omite"
    return
  fi
  install -D -m 0644 /dev/null "$flag"
  systemctl reset-failed bascula-app.service bascula-recovery.service || true
  if systemctl start bascula-app.service; then
    warn "bascula-app.service se inició pese a flag ${flag}"
  fi
  for _ in {1..10}; do
    if systemctl is-active --quiet bascula-recovery.service; then
      info "Recovery levantado por flag ${flag}"
      break
    fi
    sleep 1
  done
  if ! systemctl is-active --quiet bascula-recovery.service; then
    err "Recovery no arrancó tras flag ${flag}"
    exit 1
  fi
  systemctl stop bascula-recovery.service || true
  systemctl reset-failed bascula-app.service bascula-recovery.service || true
  rm -f "$flag"
}

simulate_repeated_failures() {
  if ! systemctl list-unit-files bascula-recovery.service >/dev/null 2>&1; then
    warn "bascula-recovery.service no encontrado; se omiten fallos simulados"
    return
  fi
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    warn "Se requieren privilegios de root para simular fallos repetidos. Se omite"
    return
  fi
  systemctl reset-failed bascula-app.service bascula-recovery.service || true
  for attempt in 1 2 3; do
    info "Simulando fallo ${attempt}/3"
    systemctl start bascula-app.service || true
    sleep 2
    systemctl kill bascula-app.service || true
    sleep 2
  done
  for _ in {1..15}; do
    if systemctl is-active --quiet bascula-recovery.service; then
      info "Recovery activo tras 3 fallos"
      break
    fi
    sleep 1
  done
  if ! systemctl is-active --quiet bascula-recovery.service; then
    err "Recovery no se activó después de 3 fallos"
    exit 1
  fi
  systemctl stop bascula-recovery.service || true
  systemctl reset-failed bascula-app.service bascula-recovery.service || true
}

check_recovery_unit
trigger_recovery_with_flag "/boot/bascula-recovery"
simulate_repeated_failures

# shellcheck disable=SC1091
[[ -f /etc/default/bascula ]] && source /etc/default/bascula
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"

if ! command -v curl >/dev/null 2>&1; then
  err "curl no disponible; no se puede comprobar /health"
  exit 1
fi

log "Verificando mini-web en puerto ${PORT}"
curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null

if command -v libcamera-hello >/dev/null 2>&1; then
  libcamera-hello --version >/dev/null 2>&1 || warn "libcamera-hello falló"
else
  info "libcamera-hello no instalado"
fi

if command -v zbarimg >/dev/null 2>&1; then
  zbarimg --version >/dev/null 2>&1 || warn "zbarimg falló"
else
  info "zbarimg no instalado"
fi

if command -v tesseract >/dev/null 2>&1; then
  tesseract --version >/dev/null 2>&1 || warn "tesseract falló"
else
  info "tesseract no instalado"
fi

if command -v speaker-test >/dev/null 2>&1; then
  speaker-test -t sine -l 1 >/dev/null 2>&1 || warn "speaker-test falló"
elif command -v aplay >/dev/null 2>&1; then
  aplay -l >/dev/null 2>&1 || warn "aplay falló"
else
  info "No se encontró speaker-test ni aplay"
fi

echo "SMOKE OK"
