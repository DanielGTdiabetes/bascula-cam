    #!/usr/bin/env bash
    set -euo pipefail
    #
    # install-all_fixed.sh
    # - Corrige conflictos de libcamera (purga libcamera-ipa/libcamera0.5)
    # - Intenta instalar rpicam-apps, fallback a libcamera-apps
    # - Ajusta permisos del árbol OTA siempre
    # - Crea /var/log/bascula
    #

    log()  { printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
    warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
    err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
      err "Ejecuta con sudo: sudo ./install-all_fixed.sh"
      exit 1
    fi

    TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
    TARGET_GROUP="$(id -gn "$TARGET_USER")"
    TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

    BASCULA_ROOT="/opt/bascula"
    BASCULA_RELEASES_DIR="${BASCULA_ROOT}/releases"
    BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"
    XSESSION="/usr/local/bin/bascula-xsession"
    SERVICE="/etc/systemd/system/bascula-app.service"
    XWRAPPER="/etc/X11/Xwrapper.config"
    TMPFILES="/etc/tmpfiles.d/bascula.conf"
    HDMI_W="${HDMI_W:-800}"
    HDMI_H="${HDMI_H:-480}"
    HDMI_FPS="${HDMI_FPS:-60}"
    BOOTDIR="/boot/firmware"
    [[ -d "$BOOTDIR" ]] || BOOTDIR="/boot"

    log "Usuario objetivo : $TARGET_USER ($TARGET_GROUP)"
    log "HOME objetivo    : $TARGET_HOME"
    log "OTA current link : $BASCULA_CURRENT_LINK"

    log "Actualizando sistema..."
    apt-get update -y
    apt-get full-upgrade -y
    apt-get install -y git

    log "Limpiando caché de apt..."
    apt-get clean

    PKGS_CORE=(python3 python3-venv python3-pip python3-tk libjpeg-dev zlib1g-dev libpng-dev)
    PKGS_X=(xserver-xorg x11-xserver-utils xinit openbox fonts-dejavu unclutter)
    PKGS_NET=(network-manager)

    log "Configurando directorio OTA..."
    install -d -m 0755 "${BASCULA_RELEASES_DIR}"
    if [[ ! -e "$BASCULA_CURRENT_LINK" ]]; then
      if ping -c 1 github.com >/dev/null 2>&1; then
        log "Clonando repositorio en ${BASCULA_RELEASES_DIR}/v1..."
        git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${BASCULA_RELEASES_DIR}/v1"
        ln -s "${BASCULA_RELEASES_DIR}/v1" "$BASCULA_CURRENT_LINK"
      else
        err "No hay conexión a internet para clonar el repositorio. Configura manualmente $BASCULA_CURRENT_LINK."
        exit 1
      fi
    fi
    chown -R "$TARGET_USER:$TARGET_GROUP" "$BASCULA_ROOT"
    install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_GROUP" /var/log/bascula

    log "Instalando paquetes base..."
    apt-get install -y "${PKGS_CORE[@]}"

    log "Saneando libcamera si hay mezclas..."
    for p in libcamera0 libcamera-ipa libcamera0.5 rpicam-apps libcamera-apps python3-picamera2; do
      apt-mark unhold "$p" 2>/dev/null || true
    done
    apt-get remove --purge -y libcamera-ipa libcamera0.5 || true
    apt-get autoremove -y
    apt-get clean
    apt-get update -y
    apt --fix-broken install -y

    log "Instalando paquetes de cámara..."
    if ! apt-get install -y libcamera0 python3-picamera2 rpicam-apps; then
      warn "rpicam-apps no disponible; usando libcamera-apps como fallback"
      apt-get install -y libcamera0 python3-picamera2 libcamera-apps
    fi

    if ! dpkg -s network-manager >/dev/null 2>&1; then
      log "Instalando network-manager..."
      apt-get install -y "${PKGS_NET[@]}"
    fi

    if ! dpkg -s xserver-xorg >/dev/null 2>&1; then
      log "Instalando entorno gráfico mínimo..."
      apt-get install -y "${PKGS_X[@]}"
    else
      log "Xorg ya está instalado."
      apt-get install -y x11-xserver-utils unclutter fonts-dejavu || true
    fi

    log "Habilitando UART..."
    CONF="$BOOTDIR/config.txt"
    if [[ -f "$CONF" ]] && ! grep -q "^enable_uart=1" "$CONF"; then
      echo "enable_uart=1" >> "$CONF"
      log "UART habilitado en $CONF"
    fi
    if [[ -f "$BOOTDIR/cmdline.txt" ]]; then
      sed -i 's/console=serial0,115200 //g' "$BOOTDIR/cmdline.txt" || true
    fi
    if command -v raspi-config >/dev/null 2>&1; then
      raspi-config nonint do_serial 0 || true
    fi
    if ls /dev/ttyS* /dev/ttyAMA* >/dev/null 2>&1; then
      log "Puertos UART detectados: $(ls /dev/ttyS* /dev/ttyAMA* 2>/dev/null | xargs echo)"
    else
      warn "No se detectaron puertos UART ahora (puede requerir reinicio)."
    fi

    log "Habilitando la cámara..."
    if command -v raspi-config >/dev/null 2>&1; then
      raspi-config nonint do_camera 0 || true
    fi

    log "Configurando entorno virtual..."
    if [[ -d "$BASCULA_CURRENT_LINK" ]]; then
      cd "$BASCULA_CURRENT_LINK"
      if [[ ! -d ".venv" ]]; then
        python3 -m venv --system-site-packages .venv
      fi
      source .venv/bin/activate
      python -m pip install --no-cache-dir --upgrade pip wheel setuptools
      python -m pip install --no-cache-dir pyserial
      if [[ -f "requirements.txt" ]]; then
        python -m pip install --no-cache-dir -r requirements.txt || true
      fi
      deactivate
    else
      err "Directorio $BASCULA_CURRENT_LINK no encontrado."
      exit 1
    fi

    log "Configurando ${XWRAPPER}..."
    install -d -m 0755 /etc/X11
    cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

    if [[ -f "$CONF" ]] && command -v vcgencmd >/dev/null 2>&1; then
      log "Ajustando HDMI/KMS en $CONF..."
      sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d' "$CONF"
      {
        echo ""
        echo "# --- Bascula: HDMI forzado y KMS ---"
        echo "hdmi_force_hotplug=1"
        echo "hdmi_group=2"
        echo "hdmi_mode=87"
        echo "hdmi_cvt=$HDMI_W $HDMI_H $HDMI_FPS 3 0 0 0"
        echo "dtoverlay=vc4-kms-v3d"
      } >> "$CONF"
    fi

    log "Creando $TMPFILES..."
    cat > "$TMPFILES" <<EOF
d /run/bascula 0755 $TARGET_USER $TARGET_GROUP -
f /run/bascula.alive 0666 $TARGET_USER $TARGET_GROUP -
EOF
    systemd-tmpfiles --create "$TMPFILES" || true

    log "Escribiendo $XSESSION..."
    cat > "$XSESSION" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0
xset s off || true
xset -dpms || true
xset s noblank || true
unclutter -idle 0 -root &
if [[ -L "/opt/bascula/current" || -d "/opt/bascula/current" ]]; then
  cd /opt/bascula/current || true
fi
if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
fi
if [[ -x "scripts/run-ui.sh" ]]; then
  exec scripts/run-ui.sh
fi
if python3 - <<'PY'
import importlib, sys
sys.path.insert(0, '/opt/bascula/current')
importlib.import_module('bascula.ui.app')
PY
then
  exec python3 -m bascula.ui.app
else
  exec python3 -m bascula.ui.recovery_ui
fi
EOF
    chmod 0755 "$XSESSION"
    chown root:root "$XSESSION"

    log "Creando servicio $SERVICE..."
    cat > "$SERVICE" <<EOF
[Unit]
Description=Bascula Digital Pro Main Application (X on tty1)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$TARGET_USER
Group=$TARGET_GROUP
WorkingDirectory=/opt/bascula/current
Environment=PYTHONPATH=/opt/bascula/current
RuntimeDirectory=bascula
RuntimeDirectoryMode=0755
Environment=BASCULA_RUNTIME_DIR=/run/bascula
ExecStart=/usr/bin/xinit $XSESSION -- :0 vt1 -nolisten tcp
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable bascula-app.service
    if systemctl start bascula-app.service && systemctl is-active --quiet bascula-app.service; then
      log "Servicio bascula-app.service activo."
    else
      err "Servicio bascula-app.service no se inició. Verifica con: systemctl status bascula-app.service"
    fi

    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "----------------------------------------------------"
    echo "Instalación completada."
    echo "Logs: /var/log/bascula (si existen)"
    echo "Config persistente (si OTA): $TARGET_HOME/.bascula/config.json"
    echo "Release activa (symlink): $BASCULA_CURRENT_LINK"
    echo "URL mini-web (si tu build la incluye): http://${IP:-<IP>}:8080/"
    echo "Reinicia para arrancar la UI en modo kiosco: sudo reboot"
    read -p "Reiniciar ahora? [s/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
      log "Reiniciando..."
      reboot
    fi
