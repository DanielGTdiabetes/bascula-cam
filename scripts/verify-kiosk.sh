#!/usr/bin/env bash
# Diagnóstico del modo kiosco y de la instalación de Báscula Digital Pro
# No cambia nada; solo informa PASS/FAIL y consejos.

set -euo pipefail

USER_NAME="${BASCULA_USER:-bascula}"
HOME_DIR="/home/${USER_NAME}"
REPO_DIR="${BASCULA_REPO_DIR:-${HOME_DIR}/bascula-cam}"
REPORT="/tmp/bascula-kiosk-report.txt"

green() { printf "\e[32m%s\e[0m\n" "$*"; }
red()   { printf "\e[31m%s\e[0m\n" "$*"; }
yellow(){ printf "\e[33m%s\e[0m\n" "$*"; }
note()  { printf "  - %s\n" "$*"; }

pass() { green "[OK]  $*"; }
fail() { red   "[FAIL] $*"; }
warn() { yellow"[WARN] $*"; }

exec > >(tee "$REPORT") 2>&1
echo "=== Báscula Kiosk Verify === $(date)"
echo "User=${USER_NAME} Home=${HOME_DIR} Repo=${REPO_DIR}"
echo "OS: $(. /etc/os-release; echo "$PRETTY_NAME")"
echo

# 1) Usuario y grupos
if id "$USER_NAME" >/dev/null 2>&1; then
  pass "Usuario '$USER_NAME' existe"
  GROUPS_OUT=$(id "$USER_NAME")
  echo "    $GROUPS_OUT"
  for g in video audio input tty dialout; do
    id -nG "$USER_NAME" | grep -qw "$g" && pass "Grupo '$g' presente" || warn "Grupo '$g' faltante"
  done
else
  fail "Usuario '$USER_NAME' NO existe"; exit 1
fi
echo

# 2) Autologin TTY1
OVRD="/etc/systemd/system/getty@tty1.service.d/override.conf"
if [[ -f "$OVRD" ]]; then
  if grep -q -- "--autologin ${USER_NAME}" "$OVRD"; then
    pass "Autologin en TTY1 configurado"
  else
    warn "Autologin no encontrado en $OVRD"
  fi
else
  fail "Falta $OVRD"
fi
systemctl is-enabled getty@tty1 >/dev/null 2>&1 && pass "getty@tty1 enabled" || warn "getty@tty1 no enabled"
systemctl is-active  getty@tty1 >/dev/null 2>&1 && pass "getty@tty1 activo" || warn "getty@tty1 no activo"
echo

# 3) Archivos de arranque del usuario
BF="$HOME_DIR/.bash_profile"; XI="$HOME_DIR/.xinitrc"
[[ -f "$BF" ]] && pass ".bash_profile existe" || fail "Falta $BF"
[[ -f "$XI" ]] && pass ".xinitrc existe" || fail "Falta $XI"
if [[ -f "$BF" ]]; then
  grep -q "startx" "$BF" && pass "bash_profile contiene startx" || warn "bash_profile no invoca startx"
fi
if [[ -f "$XI" ]]; then
  grep -q "run-ui.sh" "$XI" && pass "xinitrc invoca run-ui.sh" || warn "xinitrc no invoca run-ui.sh"
  [[ -x "$XI" ]] && pass ".xinitrc es ejecutable" || warn ".xinitrc no es ejecutable"
fi
echo

# 4) Repo y lanzador
if [[ -d "$REPO_DIR" ]]; then
  pass "Repo presente: $REPO_DIR"
  if [[ -d "$REPO_DIR/.git" ]]; then
    ORIGIN=$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)
    echo "    origin=$ORIGIN"
    [[ "$ORIGIN" =~ ^git@github.com: ]] && pass "origin usa SSH" || warn "origin no SSH (HTTPS)"
  else
    warn "Repo sin .git (posible clon fallido)"
  fi
  [[ -x "$REPO_DIR/scripts/run-ui.sh" ]] && pass "run-ui.sh ejecutable" || warn "run-ui.sh no ejecutable"
else
  fail "No existe $REPO_DIR"
fi
echo

# 5) Xorg prerrequisitos
if ls /tmp/.X11-unix/X0 >/dev/null 2>&1; then
  pass "Socket X :0 existe (sesión gráfica activa)"
else
  warn "No hay socket X :0 (arrancará con startx desde TTY1)"
fi
command -v startx >/dev/null 2>&1 && pass "startx disponible" || fail "startx no encontrado (xinit)"
command -v Xorg  >/dev/null 2>&1 && pass "Xorg disponible"  || fail "Xorg no encontrado"
echo

# 6) Servicios
systemctl is-active bascula-web >/dev/null 2>&1 && pass "bascula-web activo" || warn "bascula-web no activo"
echo

echo "=== Fin. Informe guardado en $REPORT ==="
