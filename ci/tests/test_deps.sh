#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$(pwd)/ci/fixtures/python${PYTHONPATH:+:${PYTHONPATH}}"
export TFLITE_OPTIONAL=1

python3 scripts/check_python_deps.py

echo "[test_deps] ok"
