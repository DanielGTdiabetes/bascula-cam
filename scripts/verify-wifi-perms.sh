#!/usr/bin/env bash
set -euo pipefail
USER_CHECK="${1:-pi}"
echo "[polkit] NM modify perms:"
pkaction --action-id org.freedesktop.NetworkManager.settings.modify.system | sed -n '1,6p' || true
echo "[nmcli] test add/delete:"
set +e
sudo -u "${USER_CHECK}" nmcli connection add type wifi con-name bascula-test ssid BasculaTest 2>/dev/null
sudo -u "${USER_CHECK}" nmcli connection delete bascula-test 2>/dev/null
set -e
echo "OK"
