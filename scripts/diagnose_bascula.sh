#!/usr/bin/env bash
# diagnose_bascula.sh — Diagnóstico integral de arranque de Báscula Digital Pro
# NO aplica cambios; solo comprueba y resume causas probables de que no arranque.

set -euo pipefail
RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[34m'; NOC=$'\e[0m'
log(){ printf "%s[diag]%s %s\n" "$BLU" "$NOC" "$*"; }
ok(){  printf "%s[ ok ]%s %s\n" "$GRN" "$NOC" "$*"; }
warn(){printf "%s[warn]%s %s\n" "$YLW" "$NOC" "$*"; }
err(){ printf "%s[FAIL]%s %s\n" "$RED" "$NOC" "$*"; }

USER_HOME="/home/pi"
REPO_DIR="$USER_HOME/bascula-cam"
VENV_DIR="$REPO_DIR/.venv"
STATE_DIR="$USER_HOME/.bascula"
LOG_DIR="$STATE_DIR/logs"
LAUNCH="$REPO_DIR/safe_run.sh"

OUT="$REPO_DIR/_diagnose_report.txt"
: > "$OUT"

section(){ echo -e "\n===== $1 =====" | tee -a "$OUT"; }

section "Contexto"
echo "Fecha: $(date -Is)" | tee -a "$OUT"
echo "Usuario: $(id -un) (uid=$(id -u))" | tee -a "$OUT"
echo "PWD: $PWD" | tee -a "$OUT"
echo "Repo: $REPO_DIR" | tee -a "$OUT"

section "Estructura y permisos"
for d in "$REPO_DIR" "$STATE_DIR" "$LOG_DIR" "$USER_HOME/.config/bascula"; do
  if [ -e "$d" ]; then
    stat -c '%U:%G %A %n' "$d" | tee -a "$OUT"
  else
    echo "NO EXISTE: $d" | tee -a "$OUT"
  fi
done

section "Archivos clave"
for f in "$REPO_DIR/main.py" "$REPO_DIR/bascula/ui/app.py" "$REPO_DIR/bascula/ui/screens_tabs_ext.py" "$LAUNCH"; do
  if [ -e "$f" ]; then
    stat -c '%U:%G %A %n' "$f" | tee -a "$OUT"
  else
    echo "NO EXISTE: $f" | tee -a "$OUT"
  fi
done

section "Compilación rápida Python (syntax/import-time)"
# Solo compila el código de la app; ignora tmp y scripts auxiliares que no sean .py válidos
FAILS=0
mapfile -t PYFILES < <(cd "$REPO_DIR" && git ls-files "*.py" 2>/dev/null || find "$REPO_DIR" -name "*.py")
for p in "${PYFILES[@]}"; do
  # ignora posibles snippets temporales
  if [[ "$p" =~ tmp_.*\.py$ ]]; then continue; fi
  if ! python3 -m py_compile "$p" 2>>"$OUT"; then
    echo "Compile FAIL: $p" | tee -a "$OUT"
    FAILS=$((FAILS+1))
  fi
done
if [ "$FAILS" -eq 0 ]; then ok "Compilación Python OK"; else err "Compilación Python con errores ($FAILS). Ver $OUT"; fi

section "Servidor gráfico y DISPLAY"
DISPLAY_VAL="${DISPLAY:-<vacío>}"
echo "DISPLAY actual: $DISPLAY_VAL" | tee -a "$OUT"
echo "Procesos X: " | tee -a "$OUT"
pgrep -a Xorg || true | tee -a "$OUT"
pgrep -a Xwayland || true | tee -a "$OUT"
pgrep -a wayfire || true | tee -a "$OUT"
if [ -f "$USER_HOME/.Xauthority" ]; then
  stat -c '%U:%G %A %n' "$USER_HOME/.Xauthority" | tee -a "$OUT"
else
  echo "NO EXISTE: $USER_HOME/.Xauthority" | tee -a "$OUT"
fi

section "Prueba mínima Tkinter"
python3 - <<'PY' 2>>"$OUT" | tee -a "$OUT"
import os, sys, traceback
print("DISPLAY_env =", os.environ.get("DISPLAY"))
try:
    import tkinter as tk
    root = tk.Tk()  # Esto falla si no hay servidor gráfico
    root.after(10, root.destroy)
    root.mainloop()
    print("TK_MIN_OK")
except Exception as e:
    print("TK_MIN_FAIL:", repr(e))
    traceback.print_exc()
PY

section "Venv y lanzador"
if [ -x "$LAUNCH" ]; then ok "safe_run.sh existe y es ejecutable"; else err "safe_run.sh no existe o no es ejecutable"; fi
if [ -d "$VENV_DIR" ]; then ok "Venv encontrado"; else warn "No hay venv en $VENV_DIR (no bloquea, pero recomendable)"; fi

section "Logs de la app (últimas 120 líneas si existe)"
if [ -f "$LOG_DIR/app.log" ]; then
  tail -n 120 "$LOG_DIR/app.log" | tee -a "$OUT"
else
  echo "No existe $LOG_DIR/app.log aún" | tee -a "$OUT"
fi

section "Autostart / servicios"
if systemctl list-units --type=service | grep -q bascula; then
  systemctl status bascula-kiosk.service --no-pager 2>/dev/null | sed -n '1,60p' | tee -a "$OUT" || true
  systemctl status bascula.service --no-pager 2>/dev/null | sed -n '1,60p' | tee -a "$OUT" || true
else
  echo "No hay servicios *bascula*. OK si usas startx/Openbox." | tee -a "$OUT"
fi
for a in "$USER_HOME/.config/openbox/autostart" "$USER_HOME/.config/lxsession/LXDE-pi/autostart"; do
  if [ -f "$a" ]; then
    echo "--- $a ---" | tee -a "$OUT"
    sed -n '1,120p' "$a" | tee -a "$OUT"
  fi
done

section "Conclusión preliminar"
CONCL="INDETERMINADO"
if ! pgrep -a Xorg >/dev/null && ! pgrep -a Xwayland >/dev/null && ! pgrep -a wayfire >/dev/null; then
  CONCL="NO_X_SERVER: No hay servidor gráfico activo → Tk/Tkinter no puede crear la ventana. Esperado error 'no $DISPLAY'."
elif python3 - <<'PY' >/dev/null 2>&1
import os, tkinter as tk
root = tk.Tk(); root.destroy()
PY
then
  CONCL="X_OK: Hay servidor gráfico y Tk mínimo funciona. Si la app falla, revisa app.log o exceptions en bascula/ui/*."
else
  CONCL="X_PRESENT_PERO_TK_FALLA: Hay X pero Tk no pudo abrir (posible XAUTHORITY/permiso del display o DISPLAY incorrecto)."
fi
echo "$CONCL" | tee -a "$OUT"

echo
echo "Reporte guardado en: $OUT"
