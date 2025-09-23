#!/usr/bin/env bash
set -euo pipefail

UNIT="${FAIL_UNIT:-${1:-bascula-app.service}}"
THRESHOLD="${FAIL_THRESHOLD:-3}"
if ! [[ "${THRESHOLD}" =~ ^[0-9]+$ ]]; then
  THRESHOLD=3
fi

BASCULA_ROOT="/opt/bascula"
SHARED_DIR="${BASCULA_ROOT}/shared"
USERDATA_DIR="${SHARED_DIR}/userdata"
COUNT_FILE="${USERDATA_DIR}/app_fail_count"
FORCE_FLAG="${USERDATA_DIR}/force_recovery"
LAST_CRASH_FILE="${USERDATA_DIR}/last_crash.json"
LOG_DIR="/var/log/bascula"

if [[ -f /etc/default/bascula ]]; then
  # shellcheck disable=SC1091
  source /etc/default/bascula
fi
BASCULA_USER="${BASCULA_USER:-pi}"
BASCULA_GROUP="${BASCULA_GROUP:-${BASCULA_USER}}"

install -d -m 0755 "${USERDATA_DIR}"
install -d -m 0755 "${LOG_DIR}"

count=0
if [[ -f "${COUNT_FILE}" ]]; then
  if read -r value < "${COUNT_FILE}" && [[ "${value}" =~ ^[0-9]+$ ]]; then
    count="${value}"
  fi
fi
count=$((count + 1))
printf '%s\n' "${count}" > "${COUNT_FILE}"
chown "${BASCULA_USER}:${BASCULA_GROUP}" "${COUNT_FILE}" 2>/dev/null || true
chmod 0644 "${COUNT_FILE}" 2>/dev/null || true

timestamp="$(date --iso-8601=seconds 2>/dev/null || date)"
result="$(systemctl show "${UNIT}" -p Result --value 2>/dev/null || echo 'unknown')"
status="$(systemctl show "${UNIT}" -p ExecMainStatus --value 2>/dev/null || echo '')"
current_release="$(readlink -f "${BASCULA_ROOT}/current" 2>/dev/null || echo '')"
message="Fallo consecutivo ${count} en ${UNIT}"
if [[ -n "${status}" && "${status}" != "0" ]]; then
  message+=" (status=${status})"
fi
if [[ -n "${result}" && "${result}" != "success" ]]; then
  message+=" (result=${result})"
fi

printf '[app-failure] %s\n' "${message}"

printf '[%s] %s\n' "${timestamp}" "${message}" >> "${LOG_DIR}/app_failure.log"

python3 - <<'PY' "${LAST_CRASH_FILE}" "${timestamp}" "${message}" "${result}" "${count}" "${current_release}" "${BASCULA_USER}" "${BASCULA_GROUP}"
import json
import os
import sys

path, timestamp, message, result, count, release, user, group = sys.argv[1:9]
data = {
    "timestamp": timestamp,
    "message": message,
    "error": result,
    "failures": int(count),
    "versions": {},
}
if release:
    data["versions"]["app"] = release
tmp_path = path + ".tmp"
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(tmp_path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)
    fh.write("\n")
os.replace(tmp_path, path)
try:
    import pwd, grp
    os.chown(path, pwd.getpwnam(user).pw_uid, grp.getgrnam(group).gr_gid)
except Exception:
    pass
os.chmod(path, 0o644)
PY

if (( count >= THRESHOLD )); then
  printf '[app-failure] Umbral %s alcanzado (count=%s); activando recovery\n' "${THRESHOLD}" "${count}"
  mkdir -p "$(dirname "${FORCE_FLAG}")" 2>/dev/null || true
  touch "${FORCE_FLAG}"
  chown "${BASCULA_USER}:${BASCULA_GROUP}" "${FORCE_FLAG}" 2>/dev/null || true
  chmod 0644 "${FORCE_FLAG}" 2>/dev/null || true
fi

exit 0
