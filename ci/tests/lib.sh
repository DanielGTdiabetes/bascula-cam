#!/usr/bin/env bash
# shellcheck disable=SC2148 # library sourced by test scripts

ci_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ci_repo_root="$(cd "${ci_lib_dir}/../.." && pwd)"
CI_LOG_DIR="${CI_LOG_DIR:-${ci_repo_root}/ci-logs}"
mkdir -p "${CI_LOG_DIR}"

ci::_ensure_path_mock() {
  case ":${PATH}:" in
    *":${ci_repo_root}/ci/mocks:"*) ;;
    *) export PATH="${ci_repo_root}/ci/mocks:${PATH}" ;;
  esac
}

ci::doctor() {
  local stage="${1:-ci-test}"
  ci::_ensure_path_mock
  "${ci_repo_root}/ci/bin/ci-doctor.sh" "${stage}"
}

ci::init_test() {
  local stage_name="$1"
  CI_TEST_NAME="${stage_name}"
  ci::_ensure_path_mock
  local log_file="${CI_LOG_DIR}/${stage_name}.log"
  export CI_CURRENT_LOG="${log_file}"
  mkdir -p "$(dirname "${log_file}")"
  # Redirect stdout/stderr to tee log
  exec > >(tee -a "${log_file}")
  exec 2>&1
  printf '[TEST] === %s ===\n' "${stage_name}"
  ci::doctor "${stage_name}"
}

ci::log() {
  printf '[TEST] %s\n' "$*"
}

ci::cleanup_flags() {
  local dest_root="${DESTDIR:-/tmp/ci-root}"
  rm -f /tmp/bascula_force_recovery || true
  rm -f "${dest_root%/}/opt/bascula/shared/userdata/force_recovery" || true
  rm -f "${dest_root%/}/boot/bascula-recovery" || true
}

ci::cleanup_dest() {
  local dest_root="${DESTDIR:-/tmp/ci-root}"
  if [[ -d "${dest_root}" ]]; then
    rm -rf "${dest_root}"/* || true
  fi
}

ci::finish() {
  ci::log "cleanup"
  ci::cleanup_flags
}
