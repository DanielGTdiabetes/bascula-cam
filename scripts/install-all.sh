#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
export LANG=C.UTF-8 LC_ALL=C.UTF-8

# =============================================================================
# Instalador "Todo en Uno" v2.1 para la Báscula Digital Pro (Raspberry Pi OS)
# - CORRECCIÓN: config.json persistente en ~/.bascula/config.json + symlink en cada release
# - OTA A/B por GIT, rollback, health y UI de recuperación
# - Kiosco gráfico gestionado por systemd (X iniciado en tty1 de forma robusta)
# =============================================================================

log() { echo "=> $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }
on_err() { local ec=$?; echo "[ERROR] Falló en línea ${BASH_LINENO[0]} (código $ec)." >&2; exit $ec; }
trap on_err ERR

# ---- Config ----
if [[ -z "${BASCULA_USER:-}" ]]; then
  if [[ -n "${SUDO_USER:-}" ]] && id -u "${SUDO_USER}" &>/dev/null; then
    BASCULA_USER="${SUDO_USER}"
  elif id -u pi &>/dev/null; then
    BASCULA_USER="pi"
  else
    BASCULA_USER="bascula"
  fi
fi
BASCULA_HOME="/home/${BASCULA_USER}"
BASCULA_REPO_URL="${BASCULA_REPO_URL:-https://github.com/DanielGTdiabetes/bascula-cam.git}"
BASCULA_REPO_DIR="${BASCULA_REPO_DIR:-${BASCULA_HOME}/bascula-cam}" # Directorio de bootstrap
BASCULA_REPO_SSH_URL="${BASCULA_REPO_SSH_URL:-}"
GIT_SSH_KEY_BASE64="${GIT_SSH_KEY_BASE64:-}"
ENABLE_UART="${ENABLE_UART:-1}"
ENABLE_I2S="${ENABLE_I2S:-1}"
BASCULA_FORCE_CLEAN="${BASCULA_FORCE_CLEAN:-0}"

# OTA (A/B) rutas
BASCULA_OPT_BASE="/opt/bascula"
BASCULA_RELEASES_DIR="${BASCULA_OPT_BASE}/releases"
BASCULA_CURRENT_LINK="${BASCULA_OPT_BASE}/current"
BASCULA_STATE_DIR="/var/lib/bascula-updater"
BASCULA_LOG_DIR="/var/log/bascula"
BASCULA_RUN_DIR="/run/bascula"

# Config persistente (coincide con el proyecto: ~/.bascula/config.json)
PERSIST_CFG_DIR="${BASCULA_HOME}/.bascula"
PERSIST_CFG_PATH="${PERSIST_CFG_DIR}/config.json"

[[ "$(id -u)" -eq 0 ]] || die "Ejecuta como root (sudo)."
log "Iniciando instalación v2.1 (usuario: ${BASCULA_USER})"

# ---- Paquetes ----
log "Instalando paquetes del sistema..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends   git ca-certificates jq curl rsync make   xserver-xorg xinit xserver-xorg-video-fbdev x11-xserver-utils python3-tk   network-manager policykit-1   python3-venv python3-pip   rpicam-apps python3-picamera2   alsa-utils espeak-ng   unclutter-xfixes fonts-dejavu-core fonts-dejavu-extra fonts-noto-color-emoji   picocom

# ---- Usuario y Directorios ----
if id "${BASCULA_USER}" &>/dev/null; then
  log "Usuario '${BASCULA_USER}' ya existe."
else
  log "Creando usuario '${BASCULA_USER}'..."
  adduser --disabled-password --gecos "Bascula" "${BASCULA_USER}"
fi
log "Añadiendo grupos tty,dialout,video,gpio,audio,input..."
usermod -aG tty,dialout,video,gpio,audio,input "${BASCULA_USER}" || true

log "Creando directorios OTA y de logs..."
mkdir -p "${BASCULA_RELEASES_DIR}" "${BASCULA_STATE_DIR}" "${BASCULA_LOG_DIR}" "${BASCULA_RUN_DIR}"
chown -R "${BASCULA_USER}:${BASCULA_USER}" "${BASCULA_OPT_BASE}" "${BASCULA_STATE_DIR}" "${BASCULA_LOG_DIR}" "${BASCULA_RUN_DIR}"

# ---- SSH (si se usa) ----
REPO_URL="${BASCULA_REPO_URL}"
if [[ "${BASCULA_USE_SSH:-0}" == "1" || -n "${GIT_SSH_KEY_BASE64}" ]]; then
  log "Preparando SSH para clonado..."
  if [[ -z "${BASCULA_REPO_SSH_URL}" ]]; then
    BASCULA_REPO_SSH_URL="$(echo "${BASCULA_REPO_URL}" | sed -E 's#https://github.com/([^/]+)/([^/]+)(\.git)?$#git@github.com:\1/\2.git#')"
  fi
  REPO_URL="${BASCULA_REPO_SSH_URL}"
  sudo -u "${BASCULA_USER}" -H bash -s <<'EOS'
set -e; umask 077
mkdir -p ~/.ssh; chmod 700 ~/.ssh
touch ~/.ssh/known_hosts; ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null || true
if [[ -n "${GIT_SSH_KEY_BASE64}" ]]; then
  echo "${GIT_SSH_KEY_BASE64}" | base64 -d > ~/.ssh/id_ed25519; chmod 600 ~/.ssh/id_ed25519
else
  [[ -f ~/.ssh/id_ed25519 ]] || ssh-keygen -t ed25519 -N '' -C "bascula@$(hostname)" -f ~/.ssh/id_ed25519 >/dev/null
fi
cat > ~/.ssh/config <<CFG
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new
CFG
chmod 600 ~/.ssh/config
echo "Clave SSH pública (añádela en GitHub → Settings → SSH and GPG keys):"
cat ~/.ssh/id_ed25519.pub || true
if [[ -z "${GIT_SSH_KEY_BASE64}" ]]; then
  echo "PAUSA: pega la clave en GitHub y pulsa ENTER para continuar."; read -r _ < /dev/tty || true
fi
EOS
fi

# ---- Clonado inicial para Bootstrap ----
log "Clonando/actualizando repo de bootstrap en ${BASCULA_REPO_DIR}..."
install -d -o "${BASCULA_USER}" -g "${BASCULA_USER}" "$(dirname "${BASCULA_REPO_DIR}")" 2>/dev/null || true
if [[ "${BASCULA_FORCE_CLEAN}" == "1" ]]; then rm -rf "${BASCULA_REPO_DIR}"; fi
if [[ -d "${BASCULA_REPO_DIR}" && ! -d "${BASCULA_REPO_DIR}/.git" ]]; then rm -rf "${BASCULA_REPO_DIR}"; fi

if [[ -d "${BASCULA_REPO_DIR}/.git" ]]; then
  sudo -u "${BASCULA_USER}" -H bash -lc "cd '${BASCULA_REPO_DIR}' && git fetch --all --prune && git reset --hard origin/HEAD && git pull --ff-only"
else
  sudo -u "${BASCULA_USER}" -H bash -lc "git clone '${REPO_URL}' '${BASCULA_REPO_DIR}'"
fi
chown -R "${BASCULA_USER}:${BASCULA_USER}" "${BASCULA_REPO_DIR}" || true

# ---- Despliegue de la Primera Release ----
log "Desplegando primera versión en estructura A/B..."
cd "${BASCULA_REPO_DIR}"
VER="$(git describe --tags --abbrev=0 2>/dev/null || date +%Y%m%d%H%M)"
DEST="${BASCULA_RELEASES_DIR}/v${VER}"
rm -rf "${DEST}"
mkdir -p "${DEST}"
rsync -a --delete --exclude '.git' ./ "${DEST}/"
chown -R "${BASCULA_USER}:${BASCULA_USER}" "${DEST}"

log "Creando venv en v${VER} e instalando dependencias..."
sudo -u "${BASCULA_USER}" -H bash -lc "  set -e; cd '${DEST}';   python3 -m venv --system-site-packages .venv;   source .venv/bin/activate;   python3 -m pip install -U pip setuptools wheel;   if [[ -f requirements.txt ]]; then python3 -m pip install -r requirements.txt; fi;   deactivate"
ln -sfn "${DEST}" "${BASCULA_CURRENT_LINK}"
ln -sfn "${DEST}" "${BASCULA_OPT_BASE}/rollback"

# ---- Generación de Scripts de OTA en la Release ----
log "Instalando scripts OTA/health/recovery en la release activa..."
install -d "${DEST}/scripts"

# 1) health-check.sh
cat >"${DEST}/scripts/health-check.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STATE_FILE="/var/lib/bascula-updater/state.json"
ALIVE_FILE="/run/bascula.alive"
RECOVERY_FLAG="/var/lib/bascula-updater/force_recovery"
mkdir -p "$(dirname "$STATE_FILE")"

now=$(date +%s)
is_alive=false
if [[ -f "$ALIVE_FILE" ]]; then
  last_beat=$(stat -c %Y "$ALIVE_FILE" 2>/dev/null || echo 0)
  if (( now - last_beat <= 15 )); then
    is_alive=true
  fi
fi

if $is_alive && systemctl is-active --quiet bascula-app.service; then
    tmp=$(mktemp); jq '.last_health="up" | .fail_count=0' "$STATE_FILE" 2>/dev/null >"$tmp" || echo '{"last_health":"up","fail_count":0}' >"$tmp"; mv "$tmp" "$STATE_FILE"
    exit 0
fi

# Unhealthy
tmp=$(mktemp)
jq '.last_health="down" | .fail_count=((.fail_count // 0)+1)' "$STATE_FILE" 2>/dev/null >"$tmp" || echo '{"last_health":"down","fail_count":1}' >"$tmp"
mv "$tmp" "$STATE_FILE"

fail_count=$(jq -r '.fail_count // 0' "$STATE_FILE" 2>/dev/null || echo 0)
if [[ "$fail_count" -ge 3 ]]; then
  echo "Health check falló 3 veces. Forzando recuperación."
  touch "$RECOVERY_FLAG"
  systemctl restart bascula-app.service || true
fi
exit 1
EOF
chmod +x "${DEST}/scripts/health-check.sh"

# 2) ota-update-git.sh
cat >"${DEST}/scripts/ota-update-git.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: "${REPO_URL:?REPO_URL no definido (ej. https://github.com/OWNER/REPO.git)}"
REPO_BRANCH="${REPO_BRANCH:-main}"
BASE=/opt/bascula
REL="$BASE/releases"
CUR_LINK="$BASE/current"
ROLLBACK_LINK="$BASE/rollback"
STATE_FILE=/var/lib/bascula-updater/state.json

log(){ echo "[$(date +'%F %T')] $*"; }
TARGET_TAG="$(git ls-remote --tags --refs "$REPO_URL" | awk -F/ '{print $3}' | sort -V | tail -n1 || true)"

if [[ -n "$TARGET_TAG" ]]; then
  VERSION="v${TARGET_TAG#v}"; CHECKOUT_REF="$TARGET_TAG"
else
  VERSION="$(date +%Y%m%d%H%M)-${REPO_BRANCH}"; CHECKOUT_REF="$REPO_BRANCH"
fi

DEST="$REL/${VERSION}"
CUR_VERSION="$(readlink -f "$CUR_LINK" 2>/dev/null | xargs basename || echo 'none')"
if [[ "$CUR_VERSION" == "$VERSION" ]]; then
  log "Ya en la versión objetivo: $VERSION"; exit 0
fi

log "Preparando release en: $DEST"
rm -rf "$DEST"; mkdir -p "$DEST"
TMP_CLONE="$(mktemp -d)"
log "Clonando $REPO_URL (ref: $CHECKOUT_REF)..."
git clone --depth 1 --branch "$CHECKOUT_REF" "$REPO_URL" "$TMP_CLONE"
rsync -a --exclude='.git' "$TMP_CLONE"/ "$DEST"/
rm -rf "$TMP_CLONE"

log "Creando venv e instalando requirements..."
python3 -m venv --system-site-packages "$DEST/.venv"
"$DEST/.venv/bin/pip" install -U pip wheel
if [[ -f "$DEST/requirements.txt" ]]; then
  "$DEST/.venv/bin/pip" install -r "$DEST/requirements.txt"
fi

OLD_RELEASE="$(readlink -f "$CUR_LINK" || true)"
log "Estableciendo $OLD_RELEASE como rollback y activando $VERSION."
if [[ -n "$OLD_RELEASE" ]]; then ln -sfn "$OLD_RELEASE" "$ROLLBACK_LINK"; fi
ln -sfn "$DEST" "$CUR_LINK"

log "Reiniciando bascula-app.service..."
systemctl restart bascula-app.service

log "Esperando 30s para health check..."
sleep 30

if ! systemctl is-active --quiet bascula-app.service || [[ -f /var/lib/bascula-updater/force_recovery ]]; then
  log "Health FAIL. Rollback a $OLD_RELEASE."
  if [[ -n "$OLD_RELEASE" ]]; then ln -sfn "$OLD_RELEASE" "$CUR_LINK"; fi
  systemctl restart bascula-app.service
  tmp=$(mktemp); jq --arg v "$VERSION" '.last_update_result="rollback"' "$STATE_FILE" 2>/dev/null >"$tmp" || echo '{"last_update_result":"rollback"}'>"$tmp"; mv "$tmp" "$STATE_FILE"
  exit 1
fi

tmp=$(mktemp); jq --arg v "$VERSION" '.last_update_result="promoted" | .current_version=$v' "$STATE_FILE" 2>/dev/null >"$tmp" || echo "{}">"$tmp"; mv "$tmp" "$STATE_FILE"
log "Actualización OK -> $VERSION"
exit 0
EOF
chmod +x "${DEST}/scripts/ota-update-git.sh"

# 3) safe_run.sh
cat >"${DEST}/scripts/safe_run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/bascula/current"
PY="$APP_DIR/.venv/bin/python3"
RECOVERY_FLAG="/var/lib/bascula-updater/force_recovery"
ALIVE="/run/bascula.alive"
export PYTHONUNBUFFERED=1

# Smoke test: verifica que el punto de entrada existe
smoke_test() {
    [[ -r "$APP_DIR/main.py" ]]
}

# Si se fuerza recuperación o el smoke test falla -> recovery UI
if [[ -f "$RECOVERY_FLAG" ]] || ! smoke_test; then
  exec "$PY" -m bascula.ui.recovery_ui
fi

# Si el latido es muy antiguo -> recovery UI
if [[ -f "$ALIVE" ]]; then
  now=$(date +%s); last=$(stat -c %Y "$ALIVE" 2>/dev/null || echo 0)
  (( now - last > 15 )) && exec "$PY" -m bascula.ui.recovery_ui
fi

# Ejecutar la aplicación principal (main.py, no app.py)
exec "$PY" "$APP_DIR/main.py"
EOF
chmod +x "${DEST}/scripts/safe_run.sh"

# 4) recovery_ui.py
install -d "${DEST}/bascula/ui"
cat >"${DEST}/bascula/ui/recovery_ui.py" <<'EOF'
import tkinter as tk
import subprocess
import os
import time
from pathlib import Path

class RecoveryApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Modo Recuperación")
        self.root.configure(bg="#0a0e1a")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass

        card = tk.Frame(self.root, bg="#141823", highlightbackground="#2a3142", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Modo Recuperación", bg="#141823", fg="#00d4aa", font=("DejaVu Sans", 18, "bold")).grid(row=0, column=0, columnspan=3, padx=40, pady=(20, 10))
        self.status = tk.Label(card, text="La aplicación no pudo iniciarse.\nPuedes intentar actualizar, reiniciar o reintentar.", bg="#141823", fg="#f0f4f8", font=("DejaVu Sans", 13), wraplength=450, justify="left")
        self.status.grid(row=1, column=0, columnspan=3, padx=40, pady=10, sticky="w")

        self.update_btn = tk.Button(card, text="Actualizar", width=18, height=2, command=self.run_update)
        self.update_btn.grid(row=2, column=0, padx=(40, 5), pady=20)

        self.reboot_btn = tk.Button(card, text="Reiniciar Sistema", width=18, height=2, command=self.reboot_system)
        self.reboot_btn.grid(row=2, column=1, padx=5, pady=20)

        self.retry_btn = tk.Button(card, text="Reintentar App", width=18, height=2, command=self.try_app)
        self.retry_btn.grid(row=2, column=2, padx=(5, 40), pady=20)

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    def try_app(self):
        self.set_status("Eliminando flag de recuperación y reiniciando app...")
        try:
            Path("/var/lib/bascula-updater/force_recovery").unlink(missing_ok=True)
        except Exception:
            pass
        os.system("sync")
        time.sleep(0.5)
        os.system("systemctl restart bascula-app.service")

    def run_update(self):
        self.set_status("Invocando servicio de actualización (bascula-updater.service)...")
        self.update_btn.config(state="disabled")
        self.retry_btn.config(state="disabled")
        self.reboot_btn.config(state="disabled")
        rc = subprocess.call(["systemctl", "start", "bascula-updater.service"])
        if rc != 0:
            self.set_status(f"Error al iniciar el actualizador (código {rc}).\nRevisa la conexión de red o los logs del sistema.")
            self.update_btn.config(state="normal")
            self.retry_btn.config(state="normal")
            self.reboot_btn.config(state="normal")
        else:
            self.set_status("Actualización en progreso...\nEl sistema se reiniciará automáticamente al finalizar.")

    def reboot_system(self):
        self.set_status("Reiniciando el sistema...")
        self.update_btn.config(state="disabled")
        self.retry_btn.config(state="disabled")
        self.reboot_btn.config(state="disabled")
        os.system("systemctl reboot")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    RecoveryApp().run()
EOF

# ---- Kiosco con Systemd (X en tty1) ----
log "Configurando kiosco con systemd (X en tty1)..."
# No deshabilitamos getty, lo aprovechamos para tener el VT disponible
# Creamos .xinitrc del usuario que arrancará la app
sudo -u "${BASCULA_USER}" -H bash -s <<'EOS'
set -e
cat > "$HOME/.xinitrc" <<'XRC'
#!/usr/bin/env bash
set -e
xset -dpms
xset s off
xset s noblank
unclutter -idle 0 -root &
exec /opt/bascula/current/scripts/safe_run.sh >> "$HOME/app.log" 2>&1
XRC
chmod +x "$HOME/.xinitrc"
EOS

# Servicio que lanza X en tty1 y ejecuta .xinitrc del usuario
cat >/etc/systemd/system/bascula-app.service <<EOF
[Unit]
Description=Bascula Digital Pro Main Application (X on tty1)
After=systemd-user-sessions.service getty@tty1.service
Conflicts=getty@tty1.service

[Service]
User=${BASCULA_USER}
Group=${BASCULA_USER}
Type=simple
WorkingDirectory=${BASCULA_HOME}
Environment=HOME=${BASCULA_HOME}
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u ${BASCULA_USER})
# Exporta la ruta de configuración persistente para que la app la respete
Environment=BASCULA_CFG_DIR=${PERSIST_CFG_DIR}
TTYPath=/dev/tty1
StandardInput=tty
TTYReset=yes
TTYVHangup=yes
# Lanza X en :0 usando vt1 y manteniendo el tty para startx/xinit
ExecStart=/usr/bin/xinit ${BASCULA_HOME}/.xinitrc -- :0 vt1 -keeptty
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ---- Mini-web / Wi-Fi service ----
cat >/etc/systemd/system/bascula-web.service <<EOF
[Unit]
Description=Bascula Mini-Web (Wi-Fi/APIs)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${BASCULA_USER}
Group=${BASCULA_USER}
WorkingDirectory=${BASCULA_CURRENT_LINK}
Environment=BASCULA_CFG_DIR=${PERSIST_CFG_DIR}
Environment=BASCULA_WEB_HOST=0.0.0.0
ExecStart=${BASCULA_CURRENT_LINK}/.venv/bin/python3 -m bascula.services.wifi_config
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF

# ---- Health & Updater ----
cat >/etc/systemd/system/bascula-health.service <<EOF
[Unit]
Description=Bascula Health Check
[Service]
Type=oneshot
User=${BASCULA_USER}
ExecStart=${BASCULA_CURRENT_LINK}/scripts/health-check.sh
StandardOutput=append:${BASCULA_LOG_DIR}/health.log
StandardError=append:${BASCULA_LOG_DIR}/health.err
EOF
cat >/etc/systemd/system/bascula-health.timer <<EOF
[Unit]
Description=Run Bascula health check every 30s
[Timer]
OnBootSec=60s
OnUnitActiveSec=30s
AccuracySec=5s
Persistent=true
[Install]
WantedBy=timers.target
EOF

cat >/etc/systemd/system/bascula-updater.service <<EOF
[Unit]
Description=Bascula OTA Updater (Git)
After=network-online.target
[Service]
Type=oneshot
User=${BASCULA_USER}
Environment=REPO_URL=${REPO_URL}
Environment=REPO_BRANCH=main
ExecStart=${BASCULA_CURRENT_LINK}/scripts/ota-update-git.sh
StandardOutput=append:${BASCULA_LOG_DIR}/updater.log
StandardError=append:${BASCULA_LOG_DIR}/updater.err
EOF
cat >/etc/systemd/system/bascula-updater.timer <<'EOF'
[Unit]
Description=Check Bascula updates daily
[Timer]
OnCalendar=*-*-* 03:30:00
RandomizedDelaySec=60m
Persistent=true
[Install]
WantedBy=timers.target
EOF

# ---- Polkit ----
log "Instalando reglas de Polkit..."
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

cat >/etc/polkit-1/rules.d/51-bascula-manage-units.rules <<EOF
polkit.addRule(function(action, subject) {
  if (subject.user == "${BASCULA_USER}" || subject.isInGroup("${BASCULA_USER}")) {
    if (action.id == "org.freedesktop.systemd1.manage-units") {
      var verb = action.lookup("verb");
      if (verb == "start" || verb == "stop" || verb == "restart" || verb == "reload") {
        return polkit.Result.YES;
      }
    }
  }
});
EOF

cat >/etc/polkit-1/rules.d/52-bascula-login1.rules <<EOF
polkit.addRule(function(action, subject) {
  if (subject.user == "${BASCULA_USER}" || subject.isInGroup("${BASCULA_USER}")) {
    if (action.id == "org.freedesktop.login1.reboot" ||
        action.id == "org.freedesktop.login1.power-off" ||
        action.id == "org.freedesktop.login1.reboot-multiple-sessions" ||
        action.id == "org.freedesktop.login1.power-off-multiple-sessions") {
      return polkit.Result.YES;
    }
  }
});
EOF
systemctl restart polkit || true

# ---- Activación de Servicios ----
systemctl daemon-reload
systemctl enable --now bascula-app.service bascula-web.service bascula-health.timer bascula-updater.timer

# ---- Configuración Hardware ----
if [[ "${ENABLE_UART}" == "1" ]]; then
  log "Habilitando UART y removiendo consola serie..."
  for CFG_FILE in /boot/firmware/config.txt /boot/config.txt; do [ -f "$CFG_FILE" ] || continue; grep -q '^enable_uart=1' "$CFG_FILE" 2>/dev/null || printf '\nenable_uart=1\ndtoverlay=disable-bt\n' >> "$CFG_FILE" || true; done
  for F in /boot/firmware/cmdline.txt /boot/cmdline.txt; do [ -f "$F" ] || continue; sed -i -E 's/\s*console=(serial0|ttyAMA0|ttyS0),[^\s]+//g; s/\s*kgdboc=(serial0|ttyAMA0|ttyS0),[^\s]+//g' "$F" || true; done
  systemctl disable --now serial-getty@ttyAMA0.service serial-getty@ttyS0.service 2>/dev/null || true
fi
if [[ "${ENABLE_I2S}" == "1" ]]; then
  log "Habilitando I2S (hifiberry-dac)..."
  for CFG_FILE in /boot/firmware/config.txt /boot/config.txt; do [ -f "$CFG_FILE" ] || continue; grep -q '^dtparam=audio=off' "$CFG_FILE" 2>/dev/null || printf '\ndtparam=audio=off\ndtoverlay=hifiberry-dac\n' >> "$CFG_FILE" || true; done
fi

# ---- Configuración Persistente ----
log "Creando configuración persistente por defecto..."
install -d -m 0700 -o "${BASCULA_USER}" -g "${BASCULA_USER}" "${PERSIST_CFG_DIR}"
# Detectar puerto serie candidato
for p in /dev/serial0 /dev/ttyAMA0 /dev/ttyS0 /dev/ttyACM0 /dev/ttyUSB0; do [ -e "$p" ] && PORT_CAND="$p" && break; done
PORT_CAND="${PORT_CAND:-/dev/serial0}"
# Si no existe, crear config base
if [[ ! -f "${PERSIST_CFG_PATH}" ]]; then
  sudo -u "${BASCULA_USER}" -H bash -c "cat > '${PERSIST_CFG_PATH}' <<JSON
{
  \"port\": \"${PORT_CAND}\",
  \"baud\": 115200,
  \"calib_factor\": 1.0,
  \"smoothing\": 5,
  \"decimals\": 0,
  \"no_emoji\": false
}
JSON"
fi

# Enlazar config.json dentro de la release activa para compatibilidad
ln -sfn "${PERSIST_CFG_PATH}" "${DEST}/config.json"

# ---- Mensaje final ----
log "Instalación v2.1 completada."
IP=$(hostname -I | awk '{print $1}') || true
echo "URL mini-web: http://${IP:-<IP>}:8080/"
echo "Logs: ${BASCULA_LOG_DIR}"
echo "Configuración persistente: ${PERSIST_CFG_PATH}"
echo "Release activa: $(readlink -f ${BASCULA_CURRENT_LINK} || echo '<no symlink>')"
echo "Reinicia para activar el modo kiosco: sudo reboot
# ")
