#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

run() {
  echo "[verify] $*"
  "$@"
}

run python3 -m compileall bascula || { echo "[verify] bytecode compilation failed"; exit 1; }

if rg --glob='*.py' 'font="' bascula tests; then
  echo "[verify] fuentes con formato string detectadas"
  exit 1
fi

if rg --glob='*.py' '\)\.grid\(' bascula; then
  echo "[verify] uso de grid encadenado detectado"
  exit 1
fi

run pytest -q

run python3 - <<'PY'
import sys
from tkinter import Tk, TclError
from bascula.ui.lightweight_widgets import ValueLabel
try:
    root = Tk()
except TclError:
    print('TK_SMOKE_SKIPPED')
    sys.exit(0)
else:
    root.withdraw()
    ValueLabel(root, text='demo')
    root.destroy()
    print('TK_SMOKE_OK')
PY

if command -v ss >/dev/null 2>&1; then
  if ss -tuln | grep -q ':8080 '; then
    if ! curl -fsS http://127.0.0.1:8080/health >/dev/null; then
      echo "[verify] miniweb 8080 activo pero sin respuesta"
      exit 1
    fi
  elif ss -tuln | grep -q ':8078 '; then
    if ! curl -fsS http://127.0.0.1:8078/health >/dev/null; then
      echo "[verify] miniweb 8078 activo pero sin respuesta"
      exit 1
    fi
  else
    echo "[verify] miniweb no detectado, check omitido"
  fi
else
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    :
  elif curl -fsS http://127.0.0.1:8078/health >/dev/null 2>&1; then
    :
  else
    echo "[verify] miniweb no detectado (ss no disponible), check omitido"
  fi
fi
