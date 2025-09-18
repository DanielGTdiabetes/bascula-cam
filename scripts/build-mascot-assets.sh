#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS_DIR="$ROOT_DIR/bascula/ui/assets/mascota"
OUTPUT_DIR="$ASSETS_DIR/_gen"

if [[ ! -d "$ASSETS_DIR" ]]; then
  echo "[build-mascot] directorio de assets no encontrado: $ASSETS_DIR" >&2
  exit 0
fi

shopt -s nullglob
SVG_FILES=("$ASSETS_DIR"/*.svg)
if (( ${#SVG_FILES[@]} == 0 )); then
  echo "[build-mascot] sin SVG, no se generan PNG"
  exit 0
fi

mkdir -p "$OUTPUT_DIR"
if ! command -v rsvg-convert >/dev/null 2>&1; then
  echo "[build-mascot] rsvg-convert no disponible; instale librsvg2-bin" >&2
  exit 1
fi

for svg in "${SVG_FILES[@]}"; do
  base="$(basename "$svg" .svg)"
  for size in 512 1024; do
    out="$OUTPUT_DIR/${base}_${size}.png"
    echo "[build-mascot] generando $out"
    rsvg-convert -w "$size" -h "$size" "$svg" -o "$out"
  done
done

echo "[build-mascot] finalizado"
