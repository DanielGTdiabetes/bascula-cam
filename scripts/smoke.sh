#!/usr/bin/env bash
set -euo pipefail

echo "[SMOKE] systemd units"
systemctl is-enabled bascula-app bascula-web bascula-net-fallback | cat
systemctl is-active bascula-web | cat

echo "[SMOKE] mini-web /health"
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"
curl -sS --max-time 5 "http://127.0.0.1:${PORT}/health" | cat

echo "[SMOKE] Xwrapper"
grep -h allowed_users /etc/Xwrapper.config /etc/X11/Xwrapper.config 2>/dev/null | cat
ls -ld /tmp/.X11-unix | cat

echo "[SMOKE] Tkinter presence"
python3 - <<'PY'
try:
    import tkinter
    print("tkinter: OK")
except Exception as e:
    print("tkinter: MISSING", e)
PY

echo "[SMOKE] alarmd env"
{ systemctl status bascula-alarmd --no-pager || true; } | sed -n '1,5p'

echo "[SMOKE] DONE"
