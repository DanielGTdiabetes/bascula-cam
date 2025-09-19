#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-${USER:-$(id -un)}}"
TARGET_HOME_RAW="${TARGET_HOME:-$(eval echo "~${TARGET_USER}")}" 
HOME_UNRESOLVED=false
if [[ "$TARGET_HOME_RAW" == ~* ]]; then
  HOME_UNRESOLVED=true
  TARGET_HOME=""
else
  TARGET_HOME="$TARGET_HOME_RAW"
fi
STATUS=0

log() { printf '[verify-kiosk] %s\n' "$*"; }
warn() { printf '[verify-kiosk][WARN] %s\n' "$*"; }
err() { printf '[verify-kiosk][ERR] %s\n' "$*" >&2; STATUS=1; }

if $HOME_UNRESOLVED; then
  warn "No se pudo resolver el home de ${TARGET_USER}"
fi

if [[ -S /tmp/.X11-unix/X0 ]]; then
  log 'Socket X0 disponible'
else
  warn 'No se encontró /tmp/.X11-unix/X0 (modo headless?)'
fi

if command -v loginctl >/dev/null 2>&1; then
  env_dump="$(loginctl show-environment 2>/dev/null || true)"
  if grep -q '^DISPLAY=:0$' <<<"$env_dump"; then
    log 'DISPLAY=:0 exportado en sesión systemd'
  else
    warn 'DISPLAY=:0 no detectado en loginctl show-environment'
  fi
else
  if [[ "${DISPLAY:-}" == ":0" ]]; then
    log 'DISPLAY=:0 disponible en la sesión actual'
  else
    warn 'DISPLAY=:0 no detectado en la sesión actual'
  fi
fi

if [[ -n "${TARGET_HOME}" && -f "${TARGET_HOME}/.Xauthority" ]]; then
  log "${TARGET_HOME}/.Xauthority presente"
else
  warn "${TARGET_HOME}/.Xauthority ausente"
fi

VENV="$ROOT_DIR/.venv"
if [[ -d "$VENV" ]]; then
  OWNER="$(stat -c %U "$VENV" 2>/dev/null || echo '?')"
  if [[ "$OWNER" == "$TARGET_USER" ]]; then
    log "Entorno virtual localizado en $VENV"
  else
    warn "El entorno virtual pertenece a $OWNER (esperado $TARGET_USER)"
  fi
  if [[ ! -r "$VENV/bin/activate" ]]; then
    warn 'bin/activate no es legible'
  fi
else
  warn "Falta entorno virtual en $VENV"
fi

SAFE_RUN="$ROOT_DIR/scripts/safe_run.sh"
if [[ -x "$SAFE_RUN" ]]; then
  log 'safe_run.sh es ejecutable'
else
  warn 'safe_run.sh no es ejecutable'
fi

if [[ -n "${TARGET_HOME}" ]]; then
  XINITRC="${TARGET_HOME}/.xinitrc"
  if [[ -f "$XINITRC" ]]; then
    if grep -q 'DISPLAY=:0' "$XINITRC" && grep -q 'XAUTHORITY=' "$XINITRC"; then
      log '~/.xinitrc exporta DISPLAY y XAUTHORITY'
    else
      warn '~/.xinitrc no configura DISPLAY/XAUTHORITY'
    fi
    if grep -q 'matchbox-window-manager' "$XINITRC"; then
      log 'matchbox-window-manager configurado en ~/.xinitrc'
    else
      warn 'matchbox-window-manager no referenciado en ~/.xinitrc'
    fi
    if grep -q 'safe_run.sh' "$XINITRC"; then
      log '~/.xinitrc inicia safe_run.sh'
    else
      warn '~/.xinitrc no ejecuta safe_run.sh'
    fi
    if [[ -x "$XINITRC" ]]; then
      log '~/.xinitrc es ejecutable'
    else
      warn '~/.xinitrc no es ejecutable'
    fi
  else
    warn "${XINITRC} ausente"
  fi

  PROFILE="${TARGET_HOME}/.bash_profile"
  if [[ -f "$PROFILE" ]]; then
    if grep -q 'startx' "$PROFILE"; then
      if grep -q 'PHASE=2_DONE' "$PROFILE"; then
        log '.bash_profile lanza startx tras completar install-2'
      else
        warn '.bash_profile lanza startx sin comprobar PHASE=2_DONE'
      fi
    else
      warn '.bash_profile no lanza startx'
    fi
  else
    warn "${PROFILE} ausente"
  fi
fi

if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  if systemctl is-active bascula-ui.service >/dev/null 2>&1; then
    log 'bascula-ui.service activo'
  else
    if [[ -n "${PROFILE:-}" ]] && [[ -f "$PROFILE" ]] && grep -q 'startx' "$PROFILE"; then
      log 'bascula-ui.service inactivo; arranque delegado a startx'
    else
      warn 'bascula-ui.service inactivo y startx no configurado'
      STATUS=1
    fi
  fi
else
  warn 'systemctl no disponible o systemd no se está ejecutando; verificación de bascula-ui.service omitida'
fi

ASSETS_DIR="$ROOT_DIR/bascula/ui/assets/mascota/_gen"
if compgen -G "$ASSETS_DIR"/*.png >/dev/null 2>&1; then
  log 'Assets de mascota generados presentes'
else
  warn 'Assets de mascota generados ausentes; se usará placeholder'
fi

RUNNER="$ROOT_DIR/scripts/run-ui.sh"
if [[ -x "$RUNNER" ]]; then
  log 'run-ui.sh es ejecutable'
else
  warn 'run-ui.sh no es ejecutable'
fi

exit "$STATUS"
