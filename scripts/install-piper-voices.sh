#!/usr/bin/env bash
set -euo pipefail

log(){ printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err(){ printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

DEFAULT_VOICE="${DEFAULT_VOICE:-es_ES-mls-medium}"
VOICE_DEST="/usr/share/piper/voices"
PIPER_ROOT="/opt/piper"
BIN_DEST="${PIPER_ROOT}/bin"
LINK_PATH="/usr/local/bin/piper"

install -d -m 0755 "${BIN_DEST}" "${VOICE_DEST}"

ensure_piper_binary(){
  local existing
  if existing="$(command -v piper 2>/dev/null || true)" && [[ -n "${existing}" ]]; then
    log "piper ya disponible en ${existing}"
    return 0
  fi

  local local_bin="${BIN_DEST}/piper"
  if [[ -x "${local_bin}" ]]; then
    ln -sf "${local_bin}" "${LINK_PATH}" 2>/dev/null || true
    log "piper disponible en ${local_bin}"
    return 0
  fi

  local arch="$(uname -m)"
  local url=""
  case "${arch}" in
    aarch64) url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" ;;
    armv7l)  url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_armv7l.tar.gz" ;;
    x86_64)  url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" ;;
    *)      warn "Arquitectura ${arch} no soportada automáticamente"; return 1 ;;
  esac

  local tmp="$(mktemp -t piper_bin_XXXXXX).tgz"
  log "Descargando piper (${arch})"
  if ! curl -fsSL --retry 3 -o "${tmp}" "${url}"; then
    warn "No se pudo descargar piper (${url})"
    rm -f "${tmp}"
    return 1
  fi

  tar -xzf "${tmp}" -C "${BIN_DEST}" --strip-components=1 >/dev/null 2>&1 || true
  rm -f "${tmp}"

  local_bin="${BIN_DEST}/piper"
  if [[ -x "${local_bin}" ]]; then
    chmod +x "${local_bin}" 2>/dev/null || true
    ln -sf "${local_bin}" "${LINK_PATH}" 2>/dev/null || true
    log "piper instalado en ${local_bin}"
    return 0
  fi

  warn "No se encontró piper tras la extracción"
  return 1
}

install_default_voice(){
  local voice="${DEFAULT_VOICE}"
  local onnx="${VOICE_DEST}/${voice}.onnx"
  local json="${VOICE_DEST}/${voice}.onnx.json"

  if [[ -f "${onnx}" && -f "${json}" ]]; then
    log "Voz ${voice} ya presente en ${VOICE_DEST}"
    echo "${voice}" > "${VOICE_DEST}/.default-voice"
    return 0
  fi

  local base="https://huggingface.co/rhasspy/piper-voices/resolve/main"
  local locale="${voice%%-*}"
  local rest="${voice#*-}"
  local quality="${rest##*-}"
  local corpus="${rest%-${quality}}"
  local prefix="${base}/es/${locale}/${corpus}/${quality}"

  log "Descargando voz ${voice}"
  if ! curl -fsSL --retry 3 -o "${onnx}" "${prefix}/${voice}.onnx"; then
    warn "No se pudo descargar ${voice}.onnx"
    rm -f "${onnx}"
    return 1
  fi
  if ! curl -fsSL --retry 3 -o "${json}" "${prefix}/${voice}.onnx.json"; then
    warn "No se pudo descargar ${voice}.onnx.json"
    rm -f "${json}"
    return 1
  fi

  if command -v file >/dev/null 2>&1 && file "${onnx}" | grep -qi 'text'; then
    warn "Descarga inválida para ${voice}.onnx"
    rm -f "${onnx}" "${json}"
    return 1
  fi

  echo "${voice}" > "${VOICE_DEST}/.default-voice"
  log "Voz ${voice} instalada en ${VOICE_DEST}"
}

ensure_piper_binary || warn "piper no se pudo instalar automáticamente"
install_default_voice || warn "Fallo instalando voz por defecto"

log "Listo. Binarios en ${BIN_DEST}; voces en ${VOICE_DEST}"
