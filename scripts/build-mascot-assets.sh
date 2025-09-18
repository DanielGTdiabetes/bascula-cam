#!/usr/bin/env bash
set -euo pipefail
ASSETS_DIR="${1:-$(dirname "$0")/../bascula/ui/assets/mascota}"
OUT_DIR="${ASSETS_DIR}/_gen"
mkdir -p "$OUT_DIR"
command -v rsvg-convert >/dev/null 2>&1 || { echo "[err] rsvg-convert no disponible"; exit 1; }
sizes=("512" "1024")  # @1x y @2x
for svg in "$ASSETS_DIR"/*.svg; do
  base="$(basename "$svg" .svg)"
  for s in "${sizes[@]}"; do
    png="${OUT_DIR}/${base}@${s}.png"
    rsvg-convert -w "$s" -h "$s" -o "$png" "$svg"
    echo "[ok] ${png}"
  done
done
