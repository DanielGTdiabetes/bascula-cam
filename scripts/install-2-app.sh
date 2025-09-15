#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

STATUS=0
if [[ -n "${TARGET_USER:-}" ]]; then
  if ! sudo PHASE=2 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"; then
    STATUS=$?
  fi
else
  if ! sudo PHASE=2 bash "${SCRIPT_DIR}/install-all.sh" "$@"; then
    STATUS=$?
  fi
fi

if [[ ${STATUS} -eq 0 ]]; then
  cat <<'EOF'
[info] Prueba de aceptación: ejecuta estos comandos tras la instalación
which piper && ls -lh /opt/piper/models
echo 'Hola' | piper -m /opt/piper/models/${PIPER_VOICE}.onnx -f /tmp/tts.wav && aplay /tmp/tts.wav
EOF
fi

exit "${STATUS}"
