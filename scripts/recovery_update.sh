#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bascula/current}"
OTA_DIR="${OTA_DIR:-/opt/bascula/shared/ota}"
TMP_DIR=""

log() { printf '[recovery-update] %s\n' "$*"; }
cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

ensure_dirs() {
  install -d -m 0755 "$APP_DIR"
}

select_source() {
  local latest_archive latest_dir
  if [[ -d "$OTA_DIR" ]]; then
    latest_archive=$(find "$OTA_DIR" -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | awk '{print $2}')
    latest_dir=$(find "$OTA_DIR" -maxdepth 1 -mindepth 1 -type d -name 'latest*' -o -name 'release*' | head -n1)
  fi

  if [[ -n "$latest_archive" ]]; then
    TMP_DIR="$(mktemp -d)"
    log "Extrayendo ${latest_archive}"
    tar -xzf "$latest_archive" -C "$TMP_DIR"
    local first_dir
    first_dir=$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1)
    if [[ -n "$first_dir" ]]; then
      echo "$first_dir"
      return 0
    fi
    echo "$TMP_DIR"
    return 0
  fi

  if [[ -n "$latest_dir" ]]; then
    echo "$latest_dir"
    return 0
  fi

  if [[ -d "$OTA_DIR" ]]; then
    echo "$OTA_DIR"
    return 0
  fi

  return 1
}

main() {
  ensure_dirs
  local src
  if ! src=$(select_source); then
    log "No se encontró paquete OTA en $OTA_DIR"
    exit 1
  fi
  log "Sincronizando desde ${src}"

  rsync -a --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'shared/models' \
    --exclude 'shared/userdata' \
    --exclude 'shared/config' \
    "$src"/ "$APP_DIR"/

  if [[ -x "$APP_DIR/.venv/bin/pip" && -f "$APP_DIR/requirements.txt" ]]; then
    log "Actualizando dependencias"
    "$APP_DIR/.venv/bin/pip" install --upgrade -r "$APP_DIR/requirements.txt"
  fi

  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
  fi

  log "Actualización finalizada"
}

main "$@"
