\
    #!/usr/bin/env bash
    set -euo pipefail
    #
    # install-all_OTA_fixed_v2.sh
    # - Corrige:
    #   * Heartbeat en /run/bascula(.alive) → tmpfiles + RuntimeDirectory
    #   * ImportError 'bascula' → WorkingDirectory + PYTHONPATH=/opt/bascula/current
    # - Instala stack gráfico mínimo si falta (Xorg+xinit+openbox+x11-utils+fonts+unclutter+python3-tk)
    # - Configura Xwrapper y HDMI/KMS
    # - Crea xsession que activa venv y lanza la UI (o recovery ui como fallback)
    #
    # Raspberry Pi OS Bookworm (Lite o Desktop). Ejecutar con sudo.

    log()  { printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
    warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
    err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
      err "Ejecuta con sudo: sudo ./install-all_OTA_fixed_v2.sh"
      exit 1
    fi

    TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
    TARGET_GROUP="$(id -gn "$TARGET_USER")"
    TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

    # OTA layout
    BASCULA_ROOT="/opt/bascula"
    BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"
    BASCULA_RELEASES_DIR="${BASCULA_ROOT}/releases"

    # X session & service
    XSESSION="/usr/local/bin/bascula-xsession"
    SERVICE="/etc/systemd/system/bascula-app.service"
    XWRAPPER="/etc/X11/Xwrapper.config"
    TMPFILES="/etc/tmpfiles.d/bascula.conf"

    # HDMI defaults (puedes sobreescribir con variables de entorno)
    HDMI_W="${HDMI_W:-1024}"
    HDMI_H="${HDMI_H:-600}"
    HDMI_FPS="${HDMI_FPS:-60}"

    # Detect BOOT dir
    if [[ -d /boot/firmware ]]; then
      BOOTDIR="/boot/firmware"
    else
      BOOTDIR="/boot"
    fi

    log "Usuario objetivo : $TARGET_USER ($TARGET_GROUP)"
    log "HOME objetivo    : $TARGET_HOME"
    log "OTA current link : $BASCULA_CURRENT_LINK"

    apt-get update -y

    # Paquetes base
    PKGS_CORE=(
      python3 python3-venv python3-pip git
      libatlas-base-dev libopenblas-dev liblapack-dev
      libjpeg-dev zlib1g-dev libpng-dev libtiff5-dev
      libfreetype6-dev liblcms2-dev libwebp-dev
      libharfbuzz-dev libfribidi-dev libxcb1-dev
      python3-tk
    )
    PKGS_CAM=(
      libcamera0 libcamera-apps python3-picamera2
    )
    PKGS_X=(
      xserver-xorg x11-xserver-utils xinit openbox
      fonts-dejavu fonts-dejavu-core fonts-dejavu-extra
      unclutter
    )
    PKGS_NET=(
      network-manager
    )

    log "Instalando paquetes base…"
    apt-get install -y "${PKGS_CORE[@]}" "${PKGS_CAM[@]}" "${PKGS_NET[@]}"
    if ! dpkg -l | grep -qi '^ii\s\+xserver-xorg\b'; then
      log "No se detecta Xorg → instalando entorno gráfico mínimo…"
      apt-get install -y "${PKGS_X[@]}"
    else
      log "Xorg ya está instalado."
    fi

    # Xwrapper (para lanzar X desde servicios)
    log "Configurando ${XWRAPPER}…"
    install -d -m 0755 /etc/X11
    cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

    # HDMI/KMS
    CONF="${BOOTDIR}/config.txt"
    if [[ -f "$CONF" ]]; then
      log "Ajustando HDMI/KMS en ${CONF}…"
      # Limpia entradas previas para evitar duplicados
      sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d' "$CONF"
      {
        echo ""
        echo "# --- Bascula: HDMI forzado y KMS ---"
        echo "hdmi_force_hotplug=1"
        echo "hdmi_group=2"
        echo "hdmi_mode=87"
        echo "hdmi_cvt=${HDMI_W} ${HDMI_H} ${HDMI_FPS} 3 0 0 0"
        echo "dtoverlay=vc4-kms-v3d"
      } >> "$CONF"
    else
      warn "No se encontró ${CONF}; omito HDMI."
    fi

    # tmpfiles para /run (heartbeat)
    log "Creando ${TMPFILES} para /run…"
    cat > "${TMPFILES}" <<EOF
# directorio de runtime para la app
d /run/bascula 0755 ${TARGET_USER} ${TARGET_GROUP} -
# archivo heartbeat (si tu app usa /run/bascula.alive)
f /run/bascula.alive 0666 ${TARGET_USER} ${TARGET_GROUP} -
EOF
    systemd-tmpfiles --create "${TMPFILES}" || true

    # X session que lanza la app
    log "Escribiendo ${XSESSION}…"
    cat > "${XSESSION}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0
# Ajustes visuales
xset s off || true
xset -dpms || true
xset s noblank || true
unclutter -idle 0 -root &
# Ir a la release activa
if [[ -L "/opt/bascula/current" || -d "/opt/bascula/current" ]]; then
  cd /opt/bascula/current || true
fi
# Activar venv si existe
if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi
# Intentar lanzador del repo si existe
if [[ -x "scripts/run-ui.sh" ]]; then
  exec "scripts/run-ui.sh"
fi
# Fallback: arrancar UI principal si existe módulo; sino, recovery
if python3 - <<'PY'
import importlib, sys
sys.path.insert(0, '/opt/bascula/current')
importlib.import_module('bascula.ui.app')
PY
then
  exec python3 -m bascula.ui.app
else
  exec python3 -m bascula.ui.recovery_ui || python3 -m bascula.ui.app || python3 -m bascula.ui.recovery_ui
fi
EOF
    chmod 0755 "${XSESSION}"
    chown root:root "${XSESSION}"

    # Servicio systemd principal
    log "Creando servicio ${SERVICE}…"
    cat > "${SERVICE}" <<EOF
[Unit]
Description=Bascula Digital Pro Main Application (X on tty1)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
# Directorio OTA activo (para que Python encuentre 'bascula')
WorkingDirectory=/opt/bascula/current
# PYTHONPATH para importar el paquete 'bascula'
Environment=PYTHONPATH=/opt/bascula/current
# Directorio de runtime bajo /run (creado automáticamente por systemd)
RuntimeDirectory=bascula
RuntimeDirectoryMode=0755
# Export opcional por si la app lo usa
Environment=BASCULA_RUNTIME_DIR=/run/bascula
# Lanzar servidor X y la sesión
ExecStart=/usr/bin/xinit ${XSESSION} -- :0 vt1 -nolisten tcp
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable bascula-app.service

    # Salida de cortesía
    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "----------------------------------------------------"
    echo "Instalación completada."
    echo "Logs: /var/log/bascula (si existen)"
    echo "Config persistente (si OTA): ${TARGET_HOME}/.bascula/config.json"
    echo "Release activa (symlink): ${BASCULA_CURRENT_LINK}"
    echo "URL mini-web (si tu build la incluye): http://${IP:-<IP>}:8080/"
    echo "Reinicia para arrancar la UI en modo kiosco: sudo reboot"
