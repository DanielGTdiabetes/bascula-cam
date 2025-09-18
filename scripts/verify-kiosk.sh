#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${TARGET_USER:-pi}"
TARGET_HOME="${TARGET_HOME:-/home/${TARGET_USER}}"
REPO_DIR="${REPO_DIR:-${TARGET_HOME}/bascula-cam}"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

log "Verificando entorno kiosko"

if [[ -S /tmp/.X11-unix/X0 ]]; then
  ok "Socket X0 disponible"
else
  warn "No se detecta /tmp/.X11-unix/X0"
fi

if command -v startx >/dev/null 2>&1; then
  ok "startx disponible"
else
  warn "startx no encontrado"
fi

if command -v Xorg >/dev/null 2>&1; then
  ok "Xorg disponible"
else
  warn "Xorg no disponible"
fi

if [[ -d /tmp/.X11-unix ]]; then
  ls /tmp/.X11-unix 2>/dev/null | sed 's/^/[ok] Socket X: /' || true
else
  warn "No se encuentra /tmp/.X11-unix"
fi

log "Probando Tkinter"
if command -v python3 >/dev/null 2>&1; then
  if sudo -u "${TARGET_USER}" DISPLAY="${DISPLAY:-:0}" python3 <<'PY' >/tmp/bascula-tk.log 2>&1; then
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.after(10, root.destroy)
root.mainloop()
PY
    ok "Tkinter ejecutó ventana básica"
  else
    warn "Tkinter no pudo abrir ventana (ver /tmp/bascula-tk.log)"
  fi
else
  warn "python3 no disponible"
fi

if [[ -n "${DISPLAY:-}" && -x "${REPO_DIR}/.venv/bin/python" && -f "${REPO_DIR}/tools/smoke_ui_imports.py" ]]; then
  log "Smoke-test de imports UI"
  if sudo -u "${TARGET_USER}" DISPLAY="${DISPLAY}" "${REPO_DIR}/.venv/bin/python" "${REPO_DIR}/tools/smoke_ui_imports.py"; then
    ok "Imports UI básicos correctos"
  else
    warn "Smoke-test de imports UI falló"
  fi
fi

log "Cámara"
if command -v libcamera-hello >/dev/null 2>&1; then
  if libcamera-hello --version >/dev/null 2>&1; then
    libcamera-hello --version 2>&1 | head -n1 | sed 's/^/[ok] /'
  else
    warn "libcamera-hello no detecta cámara"
  fi
else
  warn "libcamera-hello no disponible"
fi

log "Audio"
if command -v aplay >/dev/null 2>&1; then
  if aplay -l >/dev/null 2>&1; then
    aplay -l 2>/dev/null | sed 's/^/[ok] /'
  else
    warn "aplay no lista tarjetas"
  fi
else
  warn "aplay no instalado"
fi

log "Piper"
if which piper >/dev/null 2>&1; then
  ok "piper en $(which piper)"
else
  warn "piper no encontrado"
fi
which piper >/dev/null 2>&1 || echo "[warn] piper no está en PATH"

MODELS_DIR="/opt/piper/models"
if [[ -f "${MODELS_DIR}/.default-voice" ]]; then
  DEF=$(cat "${MODELS_DIR}/.default-voice" 2>/dev/null || true)
  if [[ -n "${DEF}" && -s "${MODELS_DIR}/${DEF}.onnx" && -s "${MODELS_DIR}/${DEF}.onnx.json" ]]; then
    ok "default-voice=${DEF} presente"
  else
    warn ".default-voice apunta a una voz inexistente o incompleta: '${DEF}'"
  fi
else
  warn ".default-voice no existe"
fi

if [[ -d "${MODELS_DIR}" ]]; then
  any_onnx=false
  pair_found=false
  while IFS= read -r onnx; do
    any_onnx=true
    base="${onnx%.onnx}"
    json="${base}.onnx.json"
    if [[ -f "${json}" ]]; then
      ok "Modelo Piper disponible: $(basename "${onnx}") + $(basename "${json}")"
      pair_found=true
    else
      warn "Falta $(basename "${json}") para $(basename "${onnx}")"
    fi
  done < <(find "${MODELS_DIR}" -maxdepth 1 -type f -name '*.onnx' -print | sort)
  if [[ "${pair_found}" == false && "${any_onnx}" == true ]]; then
    warn "No se encontraron pares completos onnx/json"
  fi
else
  warn "Directorio ${MODELS_DIR} no existe"
fi

PAIRS=$(ls -1 "${MODELS_DIR}"/*.onnx 2>/dev/null | wc -l || true)
if [[ "${PAIRS:-0}" -gt 0 ]]; then
  ok "Modelos Piper detectados en ${MODELS_DIR}"
else
  warn "No hay modelos Piper instalados en ${MODELS_DIR}"
fi

log "Servicios"
if systemctl list-units --type=service --all | grep -q '^x735-fan.service'; then
  if systemctl is-active x735-fan.service >/dev/null 2>&1; then
    ok "x735-fan activo"
  else
    warn "x735-fan no activo (¿hardware presente? revisar systemctl status x735-fan)"
  fi
else
  warn "x735-fan.service no existe"
fi

if systemctl list-units --type=service --all | grep -q '^bascula-miniweb.service'; then
  if systemctl is-active bascula-miniweb.service >/dev/null 2>&1; then
    ok "bascula-miniweb activo"
  else
    warn "bascula-miniweb no activo (systemctl status bascula-miniweb)"
  fi
else
  warn "bascula-miniweb.service no existe"
fi

# miniweb
if systemctl is-active bascula-miniweb >/dev/null 2>&1; then
  echo "[ok] miniweb activo"
else
  echo "[warn] miniweb inactivo"
fi
# uvicorn en venv
if [ -x /home/pi/bascula-cam/.venv/bin/python ] && /home/pi/bascula-cam/.venv/bin/python -c "import uvicorn" >/dev/null 2>&1; then
  echo "[ok] uvicorn en venv"
else
  echo "[err] uvicorn no instalado"
fi
# x735
if [ -x /usr/local/bin/x735.sh ]; then
  echo "[ok] x735.sh presente"
else
  echo "[err] falta /usr/local/bin/x735.sh"
fi
if systemctl is-active x735-fan >/dev/null 2>&1; then
  echo "[ok] x735-fan activo"
else
  echo "[warn] x735-fan inactivo"
fi

if systemctl list-units --type=service --all | grep -q '^bascula-ui.service'; then
  env_output=$(systemctl show bascula-ui.service -p Environment 2>/dev/null || true)
  if grep -q 'DISPLAY=:0' <<<"${env_output}"; then
    ok "bascula-ui con DISPLAY=:0"
  else
    warn "bascula-ui sin DISPLAY=:0"
  fi
  if grep -q 'XAUTHORITY=' <<<"${env_output}"; then
    ok "bascula-ui con XAUTHORITY"
  else
    warn "bascula-ui sin XAUTHORITY"
  fi
  if systemctl is-active bascula-ui.service >/dev/null 2>&1; then
    ok "bascula-ui activo"
  else
    warn "bascula-ui no activo (revisar systemctl status bascula-ui)"
  fi
else
  warn "bascula-ui.service no existe"
fi

VENV="$HOME/bascula-cam/.venv/bin/python"
if [[ -x "$VENV" ]]; then
  OWNER=$(stat -c '%U' "$VENV" || echo root)
  if [[ "$OWNER" != "$USER" ]]; then
    echo "[warn] .venv pertenece a $OWNER; se recomienda crearlo como $USER"
  else
    echo "[ok] .venv pertenece a $USER"
  fi
fi

if [[ -d "$HOME/.cache/pip" ]]; then
  COWN=$(stat -c '%U' "$HOME/.cache/pip" || echo root)
  if [[ "$COWN" = "$USER" ]]; then
    echo "[ok] cache pip propiedad de $USER"
  else
    echo "[warn] cache pip propiedad de $COWN"
  fi
fi

if systemctl list-units --type=service --all | grep -q '^bascula-recovery.service'; then
  if systemctl is-enabled bascula-recovery.service >/dev/null 2>&1; then
    env_output=$(systemctl show bascula-recovery.service -p Environment 2>/dev/null || true)
    if grep -q 'DISPLAY=:0' <<<"${env_output}"; then
      ok "bascula-recovery con DISPLAY=:0"
    else
      warn "bascula-recovery sin DISPLAY=:0"
    fi
    if grep -q 'XAUTHORITY=' <<<"${env_output}"; then
      ok "bascula-recovery con XAUTHORITY"
    else
      warn "bascula-recovery sin XAUTHORITY"
    fi
    if [[ -S /tmp/.X11-unix/X0 ]]; then
      ok "Socket X0 disponible"
    else
      warn "Socket X0 no encontrado"
    fi
    if systemctl is-active bascula-recovery.service >/dev/null 2>&1; then
      ok "bascula-recovery activo"
    else
      warn "bascula-recovery no activo (revisar systemctl status bascula-recovery)"
    fi
  else
    warn "bascula-recovery.service existe pero no está habilitado"
  fi
else
  log "bascula-recovery.service no existe"
fi

if [[ -d "${REPO_DIR}" ]]; then
  ok "Repositorio presente en ${REPO_DIR}"
else
  warn "Repositorio no encontrado en ${REPO_DIR}"
fi

log "Estado del repositorio bascula-cam"
if command -v git >/dev/null 2>&1; then
  status_list=$(git -C "${REPO_DIR}" status --porcelain 2>/dev/null || true)
  repo_changes=$(printf '%s\n' "${status_list}" | sed '/^$/d' | wc -l | tr -d '[:space:]')
  repo_changes=${repo_changes:-0}
  if [[ "${repo_changes}" == "0" ]]; then
    ok "Repositorio limpio tras OTA"
  else
    warn "Repositorio con ${repo_changes} cambios pendientes"
  fi
else
  warn "git no está disponible para verificar el estado del repositorio"
fi

ok "Diagnóstico completado"
