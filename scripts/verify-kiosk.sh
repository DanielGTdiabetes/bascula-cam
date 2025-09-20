#!/usr/bin/env bash
# Verificación simple del modo kiosko para la UI Tk

set -euo pipefail

PYTHON_BIN=${PYTHON:-python3}

OUTPUT=$(
${PYTHON_BIN} - <<'PY'
import sys
try:
    import tkinter as tk
except ImportError as exc:  # pragma: no cover - tkinter debería existir
    print(f"TK_IMPORT_ERROR:{exc}")
    sys.exit(1)

try:
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-fullscreen", True)
    root.destroy()
    print("KIOSK_OK")
except tk.TclError:
    print("NO_DISPLAY")
    sys.exit(0)
PY
) || {
    echo "[verify-kiosk] [err] Python lanzó un error inesperado"
    exit 1
}

if [[ "$OUTPUT" == *"KIOSK_OK"* ]]; then
    echo "[verify-kiosk] [ok] Tk soporta fullscreen y override redirect"
elif [[ "$OUTPUT" == *"NO_DISPLAY"* ]]; then
    echo "[verify-kiosk] [warn] No hay servidor X disponible (modo headless)"
else
    echo "[verify-kiosk] [err] Salida inesperada: $OUTPUT"
    exit 1
fi
