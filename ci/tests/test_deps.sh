#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ci/tests/lib.sh
source "${script_dir}/lib.sh"

ci::init_test "test_deps"
trap 'ci::finish' EXIT

export PYTHONPATH="${ci_repo_root}/ci/fixtures/python${PYTHONPATH:+:${PYTHONPATH}}"
export TFLITE_OPTIONAL=1

ci::log "Ejecutando check_python_deps.py"
python3 "${ci_repo_root}/scripts/check_python_deps.py"

ci::log "test_deps completado"
