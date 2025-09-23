#!/usr/bin/env bash
# Bascula CI doctor: prepares environment for deterministic CI runs.
set -euo pipefail
IFS=$'\n\t'

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
log_dir="${CI_LOG_DIR:-${repo_root}/ci-logs}"
mkdir -p "${log_dir}"
log_file="${log_dir}/doctor.txt"

stage_label="${1:-}" # optional human readable stage name

ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
exec 3>>"${log_file}"
{
  printf '=== CI Doctor %s %s ===\n' "${ts}" "${stage_label}" >&2
} >&3

# Helper to mirror output to both stdout and log
tee_to_log() {
  tee -a "${log_file}" >&2
}

redact() {
  local v="${1:-}"
  if [[ "${v}" =~ (ghp_|github_pat_|AKIA[0-9A-Z]{16}|eyJhbGci|AIza|xox[pbar]-|aws_(access|secret)_key|-----BEGIN\ (?:RSA|OPENSSH|DSA|EC)\ PRIVATE\ KEY-----) ]]; then
    printf '<redacted>'
  else
    printf '%s' "${v}"
  fi
}

print_kv_safe() { # name value
  local n="${1:-}" v="${2:-}"
  if [[ "${n}" =~ ([Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Pp][Aa][Ss][Ss]|[Kk][Ee][Yy]|[Aa][Uu][Tt][Hh]|[Cc][Rr][Ee][Dd]) ]]; then
    printf '%s=<redacted>\n' "${n}"
  else
    printf '%s=%s\n' "${n}" "$(redact "${v}")"
  fi
}

{
  printf 'CI doctor invoked at %s\n' "${ts}"
  if [[ -n "${stage_label}" ]]; then
    printf 'Stage: %s\n' "${stage_label}"
  fi
  printf 'Working directory: %s\n' "${PWD}"
  printf 'Repository root: %s\n' "${repo_root}"
  printf 'Log directory: %s\n' "${log_dir}"

  printf '\n-- Tool versions --\n'
  if command -v bash >/dev/null 2>&1; then
    printf 'bash: %s\n' "$(bash --version | head -n1)"
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf 'python3: %s\n' "$(python3 --version 2>&1)"
  fi
  if command -v pip3 >/dev/null 2>&1; then
    printf 'pip3: %s\n' "$(pip3 --version 2>&1)"
  fi
  if command -v awk >/dev/null 2>&1; then
    printf 'awk: %s\n' "$(awk --version 2>&1 | head -n1)"
  fi
  if command -v sed >/dev/null 2>&1; then
    printf 'sed: %s\n' "$(sed --version 2>&1 | head -n1)"
  fi
  if command -v ls >/dev/null 2>&1; then
    printf 'coreutils(ls): %s\n' "$(ls --version 2>&1 | head -n1)"
  fi

  printf '\n-- Environment --\n'
  print_kv_safe BASCULA_CI "${BASCULA_CI:-}"
  print_kv_safe DESTDIR "${DESTDIR:-}"
  print_kv_safe SHELL "${SHELL:-}"
  print_kv_safe PWD "${PWD}"
  print_kv_safe PATH "${PATH}"
  printf 'uname=%s\n' "$(uname -a 2>/dev/null || true)"
  printf 'ci/mocks dir: %s\n' "${repo_root}/ci/mocks"
  printf 'ci mock systemctl: %s\n' "${repo_root}/ci/mocks/systemctl"

  printf '\n-- PATH check --\n'
  mock_path="${repo_root}/ci/mocks/systemctl"
  if [[ -x "${mock_path}" ]]; then
    resolved_systemctl="$(command -v systemctl || true)"
    printf 'systemctl resolved to: %s\n' "${resolved_systemctl:-<none>}"
    if [[ "${resolved_systemctl}" != "${mock_path}" ]]; then
      printf 'WARNING: systemctl mock not first in PATH (expected %s)\n' "${mock_path}"
      printf 'PATH order may be incorrect.\n'
      exit 99
    fi
  else
    printf 'ERROR: mock systemctl missing at %s\n' "${mock_path}"
    exit 99
  fi

  printf '\n-- Residue cleanup --\n'
  tmp_flag="/tmp/bascula_force_recovery"
  dest_root="${DESTDIR:-/tmp/ci-root}"
  staged_recovery="${dest_root%/}/opt/bascula/shared/userdata/force_recovery"
  staged_boot="${dest_root%/}/boot/bascula-recovery"
  staged_app_dir="${dest_root%/}/opt/bascula"

  for path in "${tmp_flag}" "${staged_recovery}" "${staged_boot}"; do
    if [[ -e "${path}" ]]; then
      printf 'Removing residue: %s\n' "${path}"
      rm -rf "${path}" || true
    fi
  done
  if [[ -d "${staged_app_dir}" ]]; then
    printf 'Purging staged app dir: %s\n' "${staged_app_dir}"
    rm -rf "${staged_app_dir}" || true
  fi
  if [[ -d "${dest_root}" && "${dest_root}" == /tmp/ci-root* ]]; then
    printf 'Ensuring DESTDIR exists: %s\n' "${dest_root}"
    mkdir -p "${dest_root}"
  fi

  printf '\n-- Shell options --\n'
  set -o

} | tee_to_log
