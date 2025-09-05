#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# ============================================================================
# Instalador "Todo en Uno" para la Báscula Digital Pro (Raspberry Pi OS)
# - Objetivo: Dejar mini‑web + UI kiosco funcionando en una Pi limpia (Bookworm)
# - Uso:
#     curl -fsSL https://<TU_URL>/install-all.sh -o install.sh
#     sudo bash install.sh
# - Opciones por variable de entorno (antes de ejecutar):
#     BASCULA_USER=pi BASCULA_REPO_URL=... sudo bash install.sh
# ============================================================================

log() { echo "=> $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

on_err() {
  local ec=$?
  echo "[ERROR] Falló en línea ${BASH_LINENO[0]} (código $ec)." >&2
  exit $ec
}
trap on_err ERR

# --- Configuración ---
BASCULA_USER="${BASCULA_USER:-bascula}"
BASCULA_HOME="/home/${BASCULA_USER}"
BASCULA_REPO_URL="${BASCULA_REPO_URL:-https://github.com/DanielGTdiabetes/bascula-cam.git}"
BASCULA_REPO_DIR="${BASCULA_REPO_DIR:-${BASCULA_HOME}/bascula-cam}"
# Clave SSH embebida (opcional) y URL SSH alternativa (para repos privados)
GIT_SSH_KEY_BASE64="${GIT_SSH_KEY_BASE64:-}"
BASCULA_REPO_SSH_URL="${BASCULA_REPO_SSH_URL:-}"

# Opciones adicionales
ENABLE_UART="${ENABLE_UART:-1}"
ENABLE_I2S="${ENABLE_I2S:-1}"
BASCULA_AP_SSID="${BASCULA_AP_SSID:-BasculaAP}"
BASCULA_AP_PSK="${BASCULA_AP_PSK:-12345678}"
BASCULA_APLAY_DEVICE="${BASCULA_APLAY_DEVICE:-}"

[ "$(id -u)" -eq 0 ] || die "Ejecuta como root (sudo)."

log "Iniciando instalación completa (usuario: ${BASCULA_USER})"

# 1) Paquetes del sistema
log "Instalando paquetes del sistema..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git ca-certificates \
  xserver-xorg xinit python3-tk \
  network-manager policykit-1 \
  python3-venv python3-pip \
  rpicam-apps python3-picamera2 \
  alsa-utils espeak-ng \
  unclutter-xfixes

# Herramientas utiles
apt-get install -y --no-install-recommends curl jq make

# 2) Usuario de servicio
if id "${BASCULA_USER}" &>/dev/null; then
  log "Usuario '${BASCULA_USER}' ya existe."
else
  log "Creando usuario '${BASCULA_USER}'..."
  adduser --disabled-password --gecos "Bascula" "${BASCULA_USER}"
fi
log "Añadiendo grupos tty,dialout,video,gpio,audio..."
usermod -aG tty,dialout,video,gpio,audio "${BASCULA_USER}"

# 3) Código del proyecto
# 3a) Si viene clave SSH embebida, prepara ~/.ssh y cambia REPO_URL a SSH
if [ -n "${GIT_SSH_KEY_BASE64}" ]; then
  log "Configurando clave SSH para Git (repo privado)..."
  # Convertir HTTPS a SSH si no se especificó una URL SSH explícita
  if [ -z "${BASCULA_REPO_SSH_URL}" ]; then
    BASCULA_REPO_SSH_URL="$(echo "${BASCULA_REPO_URL}" | sed -E 's#https://github.com/([^/]+)/([^/]+)#git@github.com:\\1/\\2#')"
  fi
  REPO_URL="${BASCULA_REPO_SSH_URL}"
  # Crear ~/.ssh en el usuario de servicio y escribir la clave como id_ed25519
  sudo -u "${BASCULA_USER}" -H bash -lc "\
    set -e; \
    umask 077; \
    mkdir -p ~/.ssh; chmod 700 ~/.ssh; \
    echo '${GIT_SSH_KEY_BASE64}' | base64 -d > ~/.ssh/id_ed25519; \
    chmod 600 ~/.ssh/id_ed25519; \
    touch ~/.ssh/known_hosts; \
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null || true; \
    cat > ~/.ssh/config <<SCFG\nHost github.com\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/id_ed25519\n  StrictHostKeyChecking accept-new\nSCFG\n    chmod 600 ~/.ssh/config; \
    true"
fi

log "Clonando/actualizando repo en ${BASCULA_REPO_DIR}..."
sudo -u "${BASCULA_USER}" -H bash -lc "\
  set -e; \
  if [ -d '${BASCULA_REPO_DIR}/.git' ]; then \
    cd '${BASCULA_REPO_DIR}' && git pull --ff-only; \
  else \
    mkdir -p '${BASCULA_HOME}'; \
    git clone '${REPO_URL:-${BASCULA_REPO_URL}}' '${BASCULA_REPO_DIR}'; \
  fi"
chown -R "${BASCULA_USER}:${BASCULA_USER}" "${BASCULA_REPO_DIR}"

# 3b) Config Git + SSH para el usuario de servicio
log "Configurando Git y SSH para ${BASCULA_USER}..."
sudo -u "${BASCULA_USER}" -H bash -lc "\
  set -e; \
  git config --global user.name '${GIT_USER_NAME:-Bascula}' || true; \
  git config --global user.email '${GIT_USER_EMAIL:-bascula@local}' || true; \
  mkdir -p ~/.ssh; chmod 700 ~/.ssh; \
  if [ ! -f ~/.ssh/id_ed25519 ]; then \
    ssh-keygen -t ed25519 -N '' -C 'bascula@'\"$(hostname)\" -f ~/.ssh/id_ed25519 >/dev/null; \
  fi; \
  cat > ~/.ssh/config <<SCFG\nHost github.com\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/id_ed25519\n  StrictHostKeyChecking accept-new\nSCFG\n  chmod 600 ~/.ssh/config; \
  echo 'Clave publica SSH (añadir en GitHub: Settings > SSH and GPG keys):'; \
  cat ~/.ssh/id_ed25519.pub || true; \
  true"

# 4) Entorno Python (venv con system-site-packages para picamera2)
log "Creando venv (.venv) con system‑site‑packages y dependencias..."
sudo -u "${BASCULA_USER}" -H bash -lc "\
  set -e; cd '${BASCULA_REPO_DIR}'; \
  if [ -d .venv ]; then \
    echo '(ya existe .venv)'; \
  else \
    python3 -m venv --system-site-packages .venv; \
  fi; \
  source .venv/bin/activate; \
  python -m pip install -U pip setuptools wheel; \
  python -m pip install -r requirements.txt; \
  deactivate"

# 5) Polkit (NetworkManager sin sudo)
log "Instalando regla de polkit para NetworkManager..."
cat >/etc/polkit-1/rules.d/50-bascula-nm.rules <<EOF
polkit.addRule(function(action, subject) {
  if (subject.user == "${BASCULA_USER}" || subject.isInGroup("${BASCULA_USER}")) {
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" ||
        action.id == "org.freedesktop.NetworkManager.network-control" ||
        action.id == "org.freedesktop.NetworkManager.enable-disable-wifi") {
      return polkit.Result.YES;
    }
  }
});
EOF

# Permitir gestionar solo bascula-web.service (start/stop/restart/reload) sin contraseña
cat >/etc/polkit-1/rules.d/51-bascula-web.rules <<EOF
polkit.addRule(function(action, subject) {
  if ((subject.user == "${BASCULA_USER}" || subject.isInGroup("${BASCULA_USER}")) &&
      action.id == "org.freedesktop.systemd1.manage-units") {
    var unit = action.lookup("unit");
    var verb = action.lookup("verb");
    if (unit == "bascula-web.service" && (
        verb == "start" || verb == "stop" || verb == "restart" || verb == "reload")) {
      return polkit.Result.YES;
    }
  }
});
EOF

systemctl restart polkit || true

# 6) Mini‑web (systemd) abierto en 0.0.0.0
log "Instalando servicio mini‑web (abierto a la red, con venv)..."
cp "${BASCULA_REPO_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
sed -i -e "s/^User=.*/User=${BASCULA_USER}/" -e "s/^Group=.*/Group=${BASCULA_USER}/" /etc/systemd/system/bascula-web.service
mkdir -p /etc/systemd/system/bascula-web.service.d
cat >/etc/systemd/system/bascula-web.service.d/10-venv-and-lan.conf <<EOF
[Service]
ExecStart=
ExecStart=${BASCULA_REPO_DIR}/.venv/bin/python3 -m bascula.services.wifi_config
Environment=BASCULA_WEB_HOST=0.0.0.0
# Menos estricto: elimina filtros IP de la unidad base y permite IPv4+IPv6
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressAllow=
IPAddressDeny=
EOF
systemctl daemon-reload
systemctl enable --now bascula-web.service

# 7) Kiosco (autologin tty1 + xinit)
log "Configurando modo kiosco (.bash_profile + .xinitrc)..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat >/etc/systemd/system/getty@tty1.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${BASCULA_USER} --noclear %I \$TERM
Type=idle
EOF
systemctl daemon-reload
systemctl restart getty@tty1

sudo -u "${BASCULA_USER}" -H bash -lc "\
  cat > '${BASCULA_HOME}/.bash_profile' <<'BRC'\nif [ -z "${DISPLAY}" ] && [ "${XDG_VTNR:-0}" = "1" ]; then\n  exec startx -- -nocursor\nfi\nBRC\n  chmod 0644 '${BASCULA_HOME}/.bash_profile'"

sudo -u "${BASCULA_USER}" -H bash -lc "\
  cat > '${BASCULA_HOME}/.xinitrc' <<XRC\n#!/usr/bin/env bash\nset -e\nexport PYTHONUNBUFFERED=1\n# Ahorro de energía desactivado + cursor oculto\nxset -dpms; xset s off; xset s noblank\nunclutter -idle 0 -root &\nexec '${BASCULA_REPO_DIR}/scripts/run-ui.sh' >> '${BASCULA_HOME}/app.log' 2>&1\nXRC\n  chmod +x '${BASCULA_HOME}/.xinitrc'"

# 8) (Opcional) Config ALSA por defecto para aplay (si tienes MAX98357A)
if [ -x "${BASCULA_REPO_DIR}/scripts/install-asound-default.sh" ]; then
  log "Configurando ALSA por defecto (opcional)..."
  bash "${BASCULA_REPO_DIR}/scripts/install-asound-default.sh" || true
fi

# 9) AP de emergencia (fallback) y dispatcher
log "Instalando script de dispatcher para AP fallback..."
install -m 0755 -D "${BASCULA_REPO_DIR}/scripts/nm-dispatcher/90-bascula-ap-fallback" \
  /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback || true

if command -v nmcli >/dev/null 2>&1; then
  if ! nmcli -g NAME con show | grep -Fxq "${BASCULA_AP_SSID}"; then
    log "Creando conexion AP '${BASCULA_AP_SSID}' (clave ${BASCULA_AP_PSK})..."
    nmcli con add type wifi ifname "*" con-name "${BASCULA_AP_SSID}" autoconnect no ssid "${BASCULA_AP_SSID}" || true
    nmcli con modify "${BASCULA_AP_SSID}" 802-11-wireless.mode ap ipv4.method shared ipv6.method ignore || true
    nmcli con modify "${BASCULA_AP_SSID}" wifi.band bg wifi.channel 6 || true
    nmcli con modify "${BASCULA_AP_SSID}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${BASCULA_AP_PSK}" || true
  fi
fi

# 10) UART (serie) para la bascula (opcional, por defecto activado)
if [ "${ENABLE_UART}" = "1" ]; then
  log "Ajustando UART: enable_uart=1 y quitando consola serie..."
  CFG_FILE="/boot/firmware/config.txt"; [ -f /boot/config.txt ] && CFG_FILE="/boot/config.txt"
  if ! grep -q '^enable_uart=1' "$CFG_FILE" 2>/dev/null; then
    printf '\n# Bascula: habilitar UART para /dev/serial0\nenable_uart=1\n' >> "$CFG_FILE" || true
  fi
  if ! grep -q '^dtoverlay=disable-bt' "$CFG_FILE" 2>/dev/null; then
    printf 'dtoverlay=disable-bt\n' >> "$CFG_FILE" || true
  fi
  # Quitar consola serie del cmdline
  if [ -f /boot/firmware/cmdline.txt ]; then
    sed -i -E 's/\s*console=serial0,[^\s]+//g' /boot/firmware/cmdline.txt || true
  fi
  if [ -f /boot/cmdline.txt ]; then
    sed -i -E 's/\s*console=serial0,[^\s]+//g' /boot/cmdline.txt || true
  fi
fi

# 11) (Opcional) I2S overlay para MAX98357A (ENABLE_I2S=1)
if [ "${ENABLE_I2S}" = "1" ]; then
  log "Habilitando I2S (hifiberry-dac) en config.txt..."
  CFG_FILE="/boot/firmware/config.txt"; [ -f /boot/config.txt ] && CFG_FILE="/boot/config.txt"
  if ! grep -q '^dtparam=audio=off' "$CFG_FILE" 2>/dev/null; then
    printf '\n# Bascula: I2S MAX98357A\ndtparam=audio=off\n' >> "$CFG_FILE" || true
  fi
  if ! grep -q '^dtoverlay=hifiberry-dac' "$CFG_FILE" 2>/dev/null; then
    printf 'dtoverlay=hifiberry-dac\n' >> "$CFG_FILE" || true
  fi
fi

log "Instalación completada."
IP=$(hostname -I | awk '{print $1}') || true
echo "URL mini‑web: http://${IP:-<IP>}:8080/"
echo "PIN: ejecutar 'make show-pin' o ver ~/.config/bascula/pin.txt (usuario ${BASCULA_USER})"
echo "Reinicia si quieres aplicar todo: sudo reboot"
