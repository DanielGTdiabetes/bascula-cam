#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
ARTIFACT_DIR="$ROOT_DIR/artifacts"
mkdir -p "$ARTIFACT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

DEPS_MARKER="$VENV_DIR/.smoke-deps"
if [[ ! -f "$DEPS_MARKER" ]]; then
  python -m pip install --upgrade pip --retries 1 --timeout 20 >&2 || true
  python -m pip install --retries 1 --timeout 20 PyYAML Pillow fastapi uvicorn qrcode[pil] >&2 || true
  touch "$DEPS_MARKER"
fi

SMOKE_SCRIPT="${SMOKE_RUNNER_OVERRIDE:-$ROOT_DIR/tools/smoke_score.py}"
python "$SMOKE_SCRIPT" >"$ARTIFACT_DIR/smoke.json"

SCORE=$(python -c 'import json,sys; print(json.load(sys.stdin)["score"])' <"$ARTIFACT_DIR/smoke.json")
echo "SCORE=$SCORE"
