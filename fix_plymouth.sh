#!/usr/bin/env bash
set -euo pipefail

echo "== Bascula: Fix Plymouth quiet/splash on Raspberry Pi Bookworm =="

# 0) Paths (handle both /boot/firmware and /boot)
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONF_FILE="/boot/firmware/config.txt"
if [ ! -f "$CMDLINE_FILE" ]; then CMDLINE_FILE="/boot/cmdline.txt"; fi
if [ ! -f "$CONF_FILE" ]; then CONF_FILE="/boot/config.txt"; fi

echo "[1/7] Install Plymouth (if missing)"
sudo apt-get update
sudo apt-get install -y plymouth plymouth-themes

echo "[2/7] Ensure KMS overlay enabled (vc4-kms-v3d)"
if ! grep -q '^dtoverlay=vc4-kms-v3d' "$CONF_FILE"; then
  echo "dtoverlay=vc4-kms-v3d" | sudo tee -a "$CONF_FILE" >/dev/null
  echo "   + Added dtoverlay=vc4-kms-v3d"
else
  echo "   = Already present"
fi

echo "[3/7] Tweak cmdline flags (single line) -> quiet splash + move console to tty3 + ignore serial console"
# Ensure only one line
sudo sed -zi 's/\n/ /g' "$CMDLINE_FILE" || true

# Remove any duplicate spaces
sudo sed -i 's/  */ /g' "$CMDLINE_FILE"

# Remove serial console if present (prevents spam)
sudo sed -i 's/console=serial0,[0-9]\+//g; s/console=ttyAMA0,[0-9]\+//g' "$CMDLINE_FILE"

# Move console to tty3
if grep -q 'console=tty1' "$CMDLINE_FILE"; then
  sudo sed -i 's/console=tty1/console=tty3/g' "$CMDLINE_FILE"
elif ! grep -q 'console=tty3' "$CMDLINE_FILE"; then
  sudo sed -i '1 s|$| console=tty3|' "$CMDLINE_FILE"
fi

# Add flags if missing
add_flag() {
  local flag="$1"
  if ! grep -q " $flag" "$CMDLINE_FILE"; then
    sudo sed -i "1 s|$| $flag|" "$CMDLINE_FILE"
    echo "   + Added $flag"
  else
    echo "   = $flag already set"
  fi
}
add_flag "quiet"
add_flag "splash"
add_flag "plymouth.ignore-serial-consoles"
add_flag "vt.global_cursor_default=0"
add_flag "logo.nologo"
add_flag "loglevel=3"

echo "[4/7] Ensure initramfs usage + hide rainbow splash"
if ! grep -q '^initramfs initrd.img followkernel' "$CONF_FILE"; then
  echo "initramfs initrd.img followkernel" | sudo tee -a "$CONF_FILE" >/dev/null
  echo "   + Added initramfs line"
else
  echo "   = initramfs already declared"
fi

if ! grep -q '^disable_splash=' "$CONF_FILE"; then
  echo "disable_splash=1" | sudo tee -a "$CONF_FILE" >/dev/null
  echo "   + Added disable_splash=1"
fi

echo "[5/7] Rebuild initramfs (hooks will include Plymouth)"
sudo update-initramfs -u

echo "[6/7] Set theme to spinner (safe default) and rebuild"
sudo plymouth-set-default-theme spinner -R

echo "[7/7] Show summary:"
echo "  - Config file: $CONF_FILE"
echo "  - Cmdline file: $CMDLINE_FILE"
echo "  - Preview cmdline:"
sed -n '1p' "$CMDLINE_FILE"

echo
echo "Quick manual test (should flash a splash for ~2s):"
echo "  sudo plymouthd; sudo plymouth --show-splash; sleep 2; sudo plymouth --quit"
echo
echo "Done. Reboot to test boot splash: sudo reboot"
