#!/usr/bin/env bash
set -euo pipefail

# Instala voces de Piper desde carpeta local, repo Git (voices/<VOICE>/) o Hugging Face.
# Uso típico:
#   sudo ./install-piper-voices.sh --voices es_ES-mls_10246-low
#   sudo ./install-piper-voices.sh --voices es_ES-mls_10246-low --dest /usr/share/piper/voices
#   sudo ./install-piper-voices.sh --voices es_ES-mls_10246-low --local /ruta/voices
#   sudo ./install-piper-voices.sh --voices es_ES-mls_10246-low --repo https://github.com/USER/REPO.git --ref main

log(){ printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err(){ printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

VOICES=""
REPO_URL=""
REF="main"
LOCAL_DIR=""
DEST="/usr/share/piper/voices"   # <-- destino por defecto apt
DEFAULT_VOICE=""
FORCE=0
NO_HF=0

for arg in "$@"; do
  case "$arg" in
    --voices=*) VOICES="${arg#*=}" ;;
    --repo=*)   REPO_URL="${arg#*=}" ;;
    --ref=*)    REF="${arg#*=}" ;;
    --local=*)  LOCAL_DIR="${arg#*=}" ;;
    --dest=*)   DEST="${arg#*=}" ;;
    --default=*)DEFAULT_VOICE="${arg#*=}" ;;
    --force=*)  FORCE="${arg#*=}" ;;
    --no-hf=*)  NO_HF="${arg#*=}" ;;
    -h|--help) sed -n '1,120p' "$0"; exit 0 ;;
  esac
done

[[ -n "$VOICES" ]] || { err "--voices es obligatorio (ej: --voices es_ES-mls_10246-low)"; exit 2; }
IFS=',' read -r -a VOICE_LIST <<< "$VOICES"
[[ -n "$DEFAULT_VOICE" ]] || DEFAULT_VOICE="${VOICE_LIST[0]}"

install -d -m 0755 "$DEST"

fetch_from_local(){
  local voice="$1" base="$2" dest="$3"
  local src_dir="${base}/${voice}"
  local onnx="${src_dir}/${voice}.onnx"
  local json="${src_dir}/${voice}.onnx.json"
  if [[ -f "$onnx" && -f "$json" ]]; then
    if [[ -f "${dest}/${voice}.onnx" && -f "${dest}/${voice}.onnx.json" && "$FORCE" != "1" ]]; then
      log "Voz ${voice} ya existe en ${dest} (usa --force=1 para sobrescribir)"
    else
      install -m 0644 "$onnx" "${dest}/${voice}.onnx"
      install -m 0644 "$json" "${dest}/${voice}.onnx.json"
      log "Copiada voz ${voice} desde local: ${base}"
    fi
    return 0
  fi
  return 1
}

fetch_from_repo(){
  local voice="$1" repo="$2" ref="$3" dest="$4"
  local tmp="/tmp/piper-voices-$$"
  rm -rf "$tmp"; mkdir -p "$tmp"
  if command -v git >/dev/null 2>&1; then
    log "Clonando repo (ref=${ref}) ${repo}"
    git init -q "$tmp"
    (cd "$tmp" && git remote add origin "$repo" && git fetch -q --depth 1 origin "$ref" && git checkout -q FETCH_HEAD)
    (cd "$tmp" && git sparse-checkout init --cone >/dev/null 2>&1 || true)
    (cd "$tmp" && git sparse-checkout set "voices/${voice}" >/dev/null 2>&1 || true)
    (cd "$tmp" && git pull -q origin "$ref" || true)
    local base="${tmp}/voices"
    if fetch_from_local "$voice" "$base" "$dest"; then
      rm -rf "$tmp"; return 0
    else
      warn "No encontré voices/${voice} en el repo"
    fi
    rm -rf "$tmp"
  else
    warn "git no está instalado; salto repo"
  fi
  return 1
}

fetch_from_hf(){
  local voice="$1" dest="$2"
  [[ "$NO_HF" == "1" ]] && return 1
  # Descompone es_ES-mls_10246-low => locale=es_ES corpus=mls_10246 quality=low
  local locale="${voice%%-*}"
  local rest="${voice#*-}"
  local quality="${rest##*-}"
  local corpus="${rest%-${quality}}"
  local base="https://huggingface.co/rhasspy/piper-voices/resolve/main"
  local u_onnx="${base}/es/${locale}/${corpus}/${quality}/${voice}.onnx"
  local u_json="${base}/es/${locale}/${corpus}/${quality}/${voice}.onnx.json"
  log "HF: ${u_onnx}"

  curl -fsSL --retry 3 -o "${dest}/${voice}.onnx"      "$u_onnx"  || return 1
  curl -fsSL --retry 3 -o "${dest}/${voice}.onnx.json" "$u_json"  || return 1

  # Verificación rápida: el ONNX no debe ser texto
  if file "${dest}/${voice}.onnx" | grep -qi 'text'; then
    err "Descarga inválida (HTML?) para ${voice}.onnx"; return 1
  fi
  log "Descargada voz ${voice} desde Hugging Face"
  return 0
}

for V in "${VOICE_LIST[@]}"; do
  ok=0
  [[ -n "$LOCAL_DIR" ]] && fetch_from_local "$V" "$LOCAL_DIR" "$DEST" && ok=1 || true
  [[ $ok -eq 0 && -n "$REPO_URL" ]] && fetch_from_repo "$V" "$REPO_URL" "$REF" "$DEST" && ok=1 || true
  [[ $ok -eq 0 ]] && fetch_from_hf "$V" "$DEST" && ok=1 || true
  if [[ $ok -eq 0 ]]; then
    err "No pude obtener la voz ${V}"
  fi
done

if [[ -f "${DEST}/${DEFAULT_VOICE}.onnx" && -f "${DEST}/${DEFAULT_VOICE}.onnx.json" ]]; then
  echo "${DEFAULT_VOICE}" > "${DEST}/.default-voice"
  log "Voz por defecto: ${DEFAULT_VOICE}"
else
  warn "No marco voz por defecto (faltan ficheros de ${DEFAULT_VOICE})"
fi

log "Listo. Voces en: ${DEST}"
