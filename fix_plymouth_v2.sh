#!/usr/bin/env bash
set -euo pipefail

RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; NC=$'\e[0m'

say() { echo -e "${YLW}[*]${NC} $*"; }
ok()  { echo -e "${GRN}[OK]${NC} $*"; }
err() { echo -e "${RED}[!!]${NC} $*"; }

CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONF_FILE="/boot/firmware/config.txt"
BOOT_DIR="/boot/firmware"
if [ ! -f "$CMDLINE_FILE" ]; then CMDLINE_FILE="/boot/cmdline.txt"; BOOT_DIR="/boot"; fi
if [ ! -f "$CONF_FILE" ]; then CONF_FILE="/boot/config.txt"; fi

say "Archivos detectados:"
echo "  - cmdline: $CMDLINE_FILE"
echo "  - config : $CONF_FILE"
echo "  - bootdir: $BOOT_DIR"
echo

say "[1/8] Instalando Plymouth si falta…"
sudo apt-get update -y >/dev/null
sudo apt-get install -y plymouth plymouth-themes initramfs-tools >/dev/null
ok "Plymouth instalado"

say "[2/8] Habilitando KMS (vc4-kms-v3d)…"
if grep -q '^dtoverlay=vc4-kms-v3d' "$CONF_FILE"; then
  ok "KMS ya presente"
else
  echo "dtoverlay=vc4-kms-v3d" | sudo tee -a "$CONF_FILE" >/dev/null
  ok "Añadido dtoverlay=vc4-kms-v3d"
fi

say "[3/8] Asegurando initramfs…"
if grep -q '^initramfs initrd.img' "$CONF_FILE"; then
  ok "initramfs ya declarado en config.txt"
else
  echo "initramfs initrd.img followkernel" | sudo tee -a "$CONF_FILE" >/dev/null
  ok "Añadido 'initramfs initrd.img followkernel'"
fi
if ! grep -q '^disable_splash=' "$CONF_FILE"; then
  echo "disable_splash=1" | sudo tee -a "$CONF_FILE" >/dev/null
  ok "Añadido disable_splash=1 (oculta arcoíris)"
fi

say "[4/8] Editando cmdline (UNA sola línea)"
# Compactar a una línea
sudo sed -zi 's/\n/ /g' "$CMDLINE_FILE" || true
sudo sed -i 's/  */ /g' "$CMDLINE_FILE"
# Quitar consolas serie
sudo sed -i 's/console=serial0,[0-9]\+//g; s/console=ttyAMA0,[0-9]\+//g' "$CMDLINE_FILE"
# Cambiar tty1 a tty3 o añadir si no existe
if grep -q 'console=tty1' "$CMDLINE_FILE"; then
  sudo sed -i 's/console=tty1/console=tty3/g' "$CMDLINE_FILE"
elif ! grep -q 'console=tty3' "$CMDLINE_FILE"; then
  sudo sed -i '1 s|$| console=tty3|' "$CMDLINE_FILE"
fi
add_flag() {
  local flag="$1"
  if ! grep -q " $flag" "$CMDLINE_FILE"; then
    sudo sed -i "1 s|$| $flag|" "$CMDLINE_FILE"
    echo "   + Añadido $flag"
  fi
}
add_flag "quiet"
add_flag "splash"
add_flag "plymouth.ignore-serial-consoles"
add_flag "vt.global_cursor_default=0"
add_flag "logo.nologo"
add_flag "loglevel=3"
# Opcional: mapear VTs para que tty1 quede limpio
add_flag "fbcon=map:3"

ok "cmdline preparado"
echo "cmdline actual:"
sed -n '1p' "$CMDLINE_FILE"
echo

say "[5/8] Estableciendo tema 'spinner' y reconstruyendo initramfs…"
sudo plymouth-set-default-theme spinner >/dev/null
sudo update-initramfs -c -k "$(uname -r)" >/dev/null || sudo update-initramfs -u >/dev/null
ok "initramfs actualizado"

say "[6/8] Verificando que plymouthd está dentro del initramfs…"
INITRD="$BOOT_DIR/initrd.img-$(uname -r)"
[ -f "$INITRD" ] || INITRD="$BOOT_DIR/initrd.img"
if [ -f "$INITRD" ]; then
  if lsinitramfs "$INITRD" | grep -q '/sbin/plymouthd'; then
    ok "plymouthd presente en $INITRD"
  else
    err "plymouthd NO aparece dentro del initramfs. Reintentando forzar…"
    echo "FRAMEBUFFER=y" | sudo tee /etc/initramfs-tools/conf.d/plymouth >/dev/null
    sudo update-initramfs -u >/dev/null
    if lsinitramfs "$INITRD" | grep -q '/sbin/plymouthd'; then
      ok "Ahora plymouthd sí está en $INITRD"
    else
      err "Sigue sin estar. Esto suele indicar problemas con initramfs en la distro/versión."
    fi
  fi
else
  err "No encuentro $INITRD. ¿Se creó initramfs correctamente?"
fi
echo

say "[7/8] Habilitando unidades de systemd relacionadas…"
sudo systemctl enable plymouth-start.service plymouth-quit-wait.service >/dev/null || true
ok "Unidades habilitadas (si aplica)"

say "[8/8] Prueba manual rápida del splash:"
echo "  sudo plymouthd; sudo plymouth --show-splash; sleep 2; sudo plymouth --quit"
echo
ok "Listo. Reinicia: sudo reboot"
echo "Si aún ves mensajes, comparte la salida de: cat /proc/cmdline"
