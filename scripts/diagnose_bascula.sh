#!/usr/bin/env bash
# Quick health check for BasculaCam installations.

set -u

STATUS_OK="OK"
STATUS_FAIL="FAIL"
STATUS_SIM="SIM"
STATUS_WARN="WARN"

print_status() {
    local status="$1"
    local title="$2"
    local hint="$3"
    printf "[%-4s] %-35s %s\n" "$status" "$title" "$hint"
}

check_port() {
    local port="$1"
    local label="$2"
    local listener=""
    if command -v ss >/dev/null 2>&1; then
        listener=$(ss -ltn 2>/dev/null | awk '{print $4"|"$5}' | grep -E ":${port}(\\||$)" || true)
    elif command -v netstat >/dev/null 2>&1; then
        listener=$(netstat -ltn 2>/dev/null | awk '{print $4"|"$6}' | grep -E ":${port}(\\||$)" || true)
    fi
    if [[ -n "$listener" ]]; then
        print_status "$STATUS_OK" "Puerto ${port} (${label})" "Servicio escuchando"
    else
        print_status "$STATUS_OK" "Puerto ${port} (${label})" "Libre; inicia el servicio si corresponde"
    fi
}

check_directory() {
    local path="$1"
    local label="$2"
    if [[ -d "$path" ]]; then
        if [[ -w "$path" ]]; then
            print_status "$STATUS_OK" "$label" "Acceso correcto en $path"
        else
            print_status "$STATUS_FAIL" "$label" "Sin permisos de escritura; usa 'sudo chown -R $(whoami) $path'"
        fi
    else
        print_status "$STATUS_SIM" "$label" "$path no existe (se crea en primer arranque)"
    fi
}

check_serial() {
    local device="/dev/serial0"
    if [[ -e "$device" ]]; then
        if [[ -r "$device" && -w "$device" ]]; then
            print_status "$STATUS_OK" "Puerto serie" "$device listo"
        else
            print_status "$STATUS_FAIL" "Puerto serie" "Sin acceso a $device; añade el usuario a 'dialout'"
        fi
    else
        print_status "$STATUS_SIM" "Puerto serie" "$device no detectado (modo simulado)"
    fi
}

check_camera() {
    if command -v libcamera-hello >/dev/null 2>&1; then
        if libcamera-hello --version >/dev/null 2>&1; then
            print_status "$STATUS_OK" "Cámara" "libcamera disponible"
        else
            print_status "$STATUS_WARN" "Cámara" "libcamera instalado, pero no responde; comprueba la cámara"
        fi
    else
        print_status "$STATUS_SIM" "Cámara" "libcamera-hello no encontrado; funcionamiento simulado"
    fi
}

check_tts() {
    local piper_bin
    piper_bin=$(command -v "${PIPER_BIN:-piper}" 2>/dev/null || true)
    if [[ -z "$piper_bin" ]]; then
        print_status "$STATUS_SIM" "TTS" "Piper no encontrado en PATH; la voz quedará desactivada"
        return
    fi
    local model="${PIPER_MODEL:-${PIPER_VOICE:-}}"
    if [[ -z "$model" ]]; then
        for candidate in "/usr/share/piper/voices" "$HOME/piper" "$HOME/.local/share/piper"; do
            model=$(find "$candidate" -maxdepth 1 -type f -name '*.onnx' 2>/dev/null | head -n 1)
            [[ -n "$model" ]] && break
        done
    fi
    if [[ -n "$model" && -f "$model" ]]; then
        print_status "$STATUS_OK" "TTS" "Piper en $piper_bin con voz $(basename "$model")"
    else
        print_status "$STATUS_WARN" "TTS" "Piper encontrado pero sin modelo (.onnx); define PIPER_MODEL"
    fi
}

check_nightscout() {
    local cfg="$HOME/.config/bascula/nightscout.json"
    if [[ ! -f "$cfg" ]]; then
        print_status "$STATUS_SIM" "Nightscout" "Sin configuración; omitiendo pruebas de API"
        return
    fi
    local result
    result=$(NS_CFG="$cfg" python3 - <<'PY'
import json
import os
import sys
cfg_path = os.environ["NS_CFG"]
try:
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception as exc:  # pragma: no cover - diagnostics only
    sys.exit(f"ERROR: {exc}")
url = str(data.get("url") or "").strip()
token = str(data.get("token") or "").strip()
if not url:
    sys.exit("MISSING_URL")
print("OK")
PY
    )
    if [[ "$result" == "OK" ]]; then
        print_status "$STATUS_OK" "Nightscout" "Config válida en $cfg"
    elif [[ "$result" == "MISSING_URL" ]]; then
        print_status "$STATUS_WARN" "Nightscout" "Falta 'url' en $cfg"
    else
        print_status "$STATUS_FAIL" "Nightscout" "No se pudo leer $cfg ($result)"
    fi
}

main() {
    echo "Diagnóstico BasculaCam"
    echo "----------------------"
    local web_port="${PORT:-8000}"
    check_port "$web_port" "web"
    check_port 8078 "ocr-service"
    check_directory "$HOME/.config" "Directorio ~/.config"
    check_directory "$HOME/.local/share/xorg" "Directorio Xorg"
    check_serial
    check_camera
    check_tts
    check_nightscout
}

main "$@"
