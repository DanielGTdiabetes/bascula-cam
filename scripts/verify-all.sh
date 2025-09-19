#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

STATUS=0

log() { printf '[verify] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

fail() {
  STATUS=1
  err "$1"
}

log "Comprobando elipsis prohibidas"
if grep -R -n -E '^\s*\.\.\.\s*$' .; then
  err "Se detectaron elipsis en el repositorio"
  exit 2
fi

log "Compilando módulos Python"
if ! python - <<'PY2'
import compileall, sys
sys.exit(0 if compileall.compile_dir('.', maxlevels=20, quiet=1) else 1)
PY2
then
  fail "compileall devolvió error"
fi

log "Verificando permisos ejecutables en scripts/*.sh"
missing_exec=false
while IFS= read -r file; do
  if [[ ! -x "${file}" ]]; then
    err "Sin permiso de ejecución: ${file}"
    missing_exec=true
  fi
done < <(find scripts -maxdepth 1 -type f -name '*.sh' -print)
if ${missing_exec}; then
  fail "Se encontraron scripts sin bit ejecutable"
fi

log "Validando unidades systemd"
if command -v systemd-analyze >/dev/null 2>&1; then
  shopt -s nullglob
  units=(/etc/systemd/system/bascula-*.service)
  shopt -u nullglob
  if (( ${#units[@]} == 0 )); then
    err "No se encontraron unidades systemd bascula-*.service para validar"
  else
    for unit in "${units[@]}"; do
      if ! systemd-analyze verify "${unit}"; then
        fail "systemd-analyze reportó errores en ${unit}"
      fi
    done
  fi
else
  err "systemd-analyze no disponible; omitiendo verificación"
fi

log "Prueba rápida de Tk"
if [[ -S /tmp/.X11-unix/X0 ]]; then
  if ! python - <<'PY3'
import os
os.environ.setdefault('DISPLAY', ':0')
from tkinter import Tk
root = Tk()
root.withdraw()
print('TK_OK')
root.destroy()
PY3
  then
    fail "Tkinter no pudo inicializarse"
  fi
else
  log "Socket X11 no encontrado, prueba Tk omitida"
fi

log "Prueba de modo headless"
if ! python - <<'PY4'
from bascula.services.headless_main import main as hmain
print('HEADLESS_OK' if callable(hmain) else 'HEADLESS_MISSING')
PY4
then
  fail "Headless main no disponible"
fi

log "Verificando fallback de puerto en miniweb"
tmp_root="$(mktemp -d)"
tmp_script="$(mktemp)"
tmp_log="${tmp_root}/miniweb_args"
fake_ss_dir=""
cleanup() {
  rm -f "${tmp_script}" 2>/dev/null || true
  rm -rf "${tmp_root}" 2>/dev/null || true
  if [[ -n "${fake_ss_dir}" ]]; then
    rm -rf "${fake_ss_dir}" 2>/dev/null || true
  fi
  if [[ -n "${server_pid:-}" ]]; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
sed 's|ROOT="/home/pi/bascula-cam"|ROOT="'"${tmp_root}"'"|' scripts/run-miniweb.sh > "${tmp_script}"
chmod +x "${tmp_script}"
mkdir -p "${tmp_root}/.venv/bin"
cat <<SH > "${tmp_root}/.venv/bin/python"
#!/usr/bin/env bash
echo "\$@" > "${tmp_root}/miniweb_args"
exit 0
SH
chmod +x "${tmp_root}/.venv/bin/python"
runner=()
if command -v ss >/dev/null 2>&1; then
  python3 -m http.server 8080 >/dev/null 2>&1 &
  server_pid=$!
  sleep 1
  runner=("${tmp_script}")
else
  fake_ss_dir="$(mktemp -d)"
  cat <<'SH' > "${fake_ss_dir}/ss"
#!/usr/bin/env bash
printf 'tcp LISTEN 0 0 0.0.0.0:8080 0.0.0.0:* users:(("stub",pid=1,fd=3))\n'
exit 0
SH
  chmod +x "${fake_ss_dir}/ss"
  runner=(env PATH="${fake_ss_dir}:${PATH}" "${tmp_script}")
fi
if ! "${runner[@]}"; then
  fail "run-miniweb.sh modificado no pudo ejecutarse"
fi
if [[ ! -f "${tmp_log}" ]]; then
  fail "No se capturaron argumentos de miniweb"
else
  if ! grep -q -- '--port 8078' "${tmp_log}"; then
    fail "Miniweb no seleccionó el puerto 8078 con 8080 ocupado"
  fi
fi
trap - EXIT
cleanup

if (( STATUS == 0 )); then
  log "Verificación completada sin errores"
else
  err "Verificación completada con fallos"
fi

exit "${STATUS}"
