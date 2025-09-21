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
