\
    #!/usr/bin/env bash
    set -euo pipefail
    #
    # install-all_complete_autodetect.sh
    # - Instalador completo para Bascula (OTA) con autodetección de serie libcamera.
    # - Seguro para instalaciones limpias de Raspberry Pi OS (Bookworm, Lite/Desktop).
    # - Puntos clave:
    #   * Cámara: autodetecta serie NUEVA (libcamera0.5 + libcamera-ipa) o VIEJA (libcamera0).
    #   * UI: stack gráfico mínimo (Xorg+xinit+openbox+x11-utils+fonts+unclutter) + python3-tk.
    #   * UART: habilitado (enable_uart, do_serial) y verificación ttyS*/ttyAMA*.
    #   * OTA: clona repo en /opt/bascula/releases, crea symlink /opt/bascula/current.
    #   * Venv: --system-site-packages (para Picamera2 de APT), pip/wheel/setuptools + pyserial + requirements.txt.
    #   * Xwrapper, HDMI/KMS condicional, /run (tmpfiles), xsession y servicio systemd con WorkingDirectory/PYTHONPATH.
    #   * Crea /var/log/bascula, corrige permisos de /opt/bascula.
    #

    log()  { printf "\\033[1;34m[inst]\\033[0m %s\\n" "$*"; }
    warn() { printf "\\033[1;33m[warn]\\033[0m %s\\n" "$*"; }
    err()  { printf "\\033[1;31m[ERR ]\\033[0m %s\\n" "$*"; }

    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
      err "Ejecuta con sudo: sudo ./install-all_complete_autodetect.sh"
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

    if [[ -d /boot/firmware ]]; then
      BOOTDIR="/boot/firmware"
    else
      BOOTDIR="/boot"
    fi

    log "Usuario objetivo : $TARGET_USER ($TARGET_GROUP)"
    log "HOME objetivo    : $TARGET_HOME"
    log "OTA current link : $BASCULA_CURRENT_LINK"

    log "Actualizando índices APT…"
    apt-get update -y

    # Paquetes base ligeros y necesarios
    PKGS_CORE=(
      git python3 python3-venv python3-pip python3-tk
      x11-xserver-utils unclutter fonts-dejavu
      libjpeg-dev zlib1g-dev libpng-dev
    )
    apt-get install -y "${PKGS_CORE[@]}"

    # NetworkManager (si no está instalado)
    if ! dpkg -s network-manager >/dev/null 2>&1; then
      log "Instalando network-manager…"
      apt-get install -y network-manager
    fi

    # Xorg mínimo (si falta)
    if ! dpkg -s xserver-xorg >/dev/null 2>&1; then
      log "Instalando entorno gráfico mínimo…"
      apt-get install -y xserver-xorg xinit openbox
    else
      log "Xorg ya está instalado."
    fi

    # Xwrapper para permitir X desde servicio
    log "Configurando ${XWRAPPER}…"
    install -d -m 0755 /etc/X11
    cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

    # OTA: clonar repo si no existe enlace current
    log "Configurando estructura OTA en ${BASCULA_ROOT}…"
    install -d -m 0755 "${BASCULA_RELEASES_DIR}"
    if [[ ! -e "${BASCULA_CURRENT_LINK}" ]]; then
      if git ls-remote https://github.com/DanielGTdiabetes/bascula-cam.git >/dev/null 2>&1; then
        log "Clonando repositorio en ${BASCULA_RELEASES_DIR}/v1…"
        git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${BASCULA_RELEASES_DIR}/v1"
        ln -s "${BASCULA_RELEASES_DIR}/v1" "${BASCULA_CURRENT_LINK}"
      else
        err "No hay acceso a GitHub. Crea/ajusta ${BASCULA_CURRENT_LINK} manualmente y reintenta."
        exit 1
      fi
    fi
    chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"
    install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula

    # UART
    log "Habilitando UART…"
    CONF="${BOOTDIR}/config.txt"
    if [[ -f "${CONF}" ]] && ! grep -q "^enable_uart=1" "${CONF}"; then
      echo "enable_uart=1" >> "${CONF}"
      log "UART habilitado en ${CONF}"
    fi
    if [[ -f "${BOOTDIR}/cmdline.txt" ]]; then
      sed -i 's/console=serial0,115200 //g' "${BOOTDIR}/cmdline.txt" || true
    fi
    if command -v raspi-config >/dev/null 2>&1; then
      raspi-config nonint do_serial 0 || true
    fi
    if ls /dev/ttyS* /dev/ttyAMA* >/dev/null 2>&1; then
      log "Puertos UART detectados: $(ls /dev/ttyS* /dev/ttyAMA* 2>/dev/null | xargs echo)"
    else
      warn "No se detectaron puertos UART ahora (puede requerir reinicio)."
    fi

    # Cámara: AUTODETECCIÓN de serie disponible
    log "Instalando paquetes de cámara (autodetección de serie)…"
    for p in libcamera0 libcamera0.5 libcamera-ipa rpicam-apps libcamera-apps python3-picamera2; do
      apt-mark unhold "$p" 2>/dev/null || true
    done
    if apt-cache policy libcamera0.5 2>/dev/null | grep -q 'Candidate:'; then
      log "Detectada SERIE NUEVA: libcamera0.5 + libcamera-ipa"
      if ! apt-get install -y libcamera0.5 libcamera-ipa python3-picamera2 rpicam-apps; then
        warn "rpicam-apps no disponible; usando libcamera-apps"
        apt-get install -y libcamera0.5 libcamera-ipa python3-picamera2 libcamera-apps
      fi
    else
      log "Detectada SERIE VIEJA: libcamera0"
      if ! apt-get install -y libcamera0 python3-picamera2 rpicam-apps; then
        warn "rpicam-apps no disponible; usando libcamera-apps"
        apt-get install -y libcamera0 python3-picamera2 libcamera-apps
      fi
    fi

    # Habilitar cámara (no siempre necesario en Bookworm, pero no daña)
    log "Habilitando la cámara (raspi-config)…"
    if command -v raspi-config >/dev/null 2>&1; then
      raspi-config nonint do_camera 0 || true
      if [[ -f "${CONF}" ]] && grep -q "camera_auto_detect=1" "${CONF}"; then
        log "Cámara habilitada (auto-detect)."
      else
        warn "No se detectó camera_auto_detect=1 (puede aparecer tras reinicio)."
      fi
    fi

    # HDMI/KMS condicional
    if [[ -f "${CONF}" ]] && command -v vcgencmd >/dev/null 2>&1; then
      log "Ajustando HDMI/KMS en ${CONF}…"
      sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d' "${CONF}"
      {
        echo ""
        echo "# --- Bascula: HDMI forzado y KMS ---"
        echo "hdmi_force_hotplug=1"
        echo "hdmi_group=2"
        echo "hdmi_mode=87"
        echo "hdmi_cvt=${HDMI_W} ${HDMI_H} ${HDMI_FPS} 3 0 0 0"
        echo "dtoverlay=vc4-kms-v3d"
      } >> "${CONF}"
    else
      warn "No se aplicó HDMI/KMS (falta vcgencmd o ${CONF})."
    fi

    # Venv
    log "Configurando entorno virtual en ${BASCULA_CURRENT_LINK}…"
    if [[ -d "${BASCULA_CURRENT_LINK}" ]]; then
      cd "${BASCULA_CURRENT_LINK}"
      if [[ ! -d ".venv" ]]; then
        python3 -m venv --system-site-packages .venv
      fi
      source .venv/bin/activate
      python -m pip install --upgrade --no-cache-dir pip wheel setuptools
      python -m pip install --no-cache-dir pyserial
      if [[ -f "requirements.txt" ]]; then
        python -m pip install --no-cache-dir -r requirements.txt || true
      fi
      deactivate
    else
      err "Directorio ${BASCULA_CURRENT_LINK} no encontrado."
      exit 1
    fi

    # /run (tmpfiles) para heartbeat
    log "Creando ${TMPFILES}…"
    cat > "${TMPFILES}" <<EOF
# /run/bascula para heartbeat
d /run/bascula 0755 ${TARGET_USER} ${TARGET_GROUP} -
# Si la app usa /run/bascula.alive directamente
f /run/bascula.alive 0666 ${TARGET_USER} ${TARGET_GROUP} -
EOF
    systemd-tmpfiles --create "${TMPFILES}" || true

    # xsession
    log "Escribiendo ${XSESSION}…"
    cat > "${XSESSION}" <<'EOF'
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
  source ".venv/bin/activate"
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
    chmod 0755 "${XSESSION}"
    chown root:root "${XSESSION}"

    # Servicio systemd
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
WorkingDirectory=/opt/bascula/current
Environment=PYTHONPATH=/opt/bascula/current
RuntimeDirectory=bascula
RuntimeDirectoryMode=0755
Environment=BASCULA_RUNTIME_DIR=/run/bascula
ExecStart=/usr/bin/xinit ${XSESSION} -- :0 vt1 -nolisten tcp
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
      err "Servicio bascula-app.service no se inició. Revisa: systemctl status bascula-app.service"
    fi

    IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "----------------------------------------------------"
    echo "Instalación completada."
    echo "Logs: /var/log/bascula"
    echo "Config persistente (si OTA): ${TARGET_HOME}/.bascula/config.json"
    echo "Release activa (symlink): ${BASCULA_CURRENT_LINK}"
    echo "URL mini-web (si tu build la incluye): http://${IP:-<IP>}:8080/"
    echo "Reinicia para arrancar la UI en modo kiosco: sudo reboot"
