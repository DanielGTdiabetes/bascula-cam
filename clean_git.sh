#!/usr/bin/env bash
set -euo pipefail

echo "Eliminando .venv del índice de Git..."
git rm -r --cached .venv 2>/dev/null || echo "No se encontró .venv en el índice"

echo "Eliminando directorios __pycache__ del índice de Git..."
find . -type d -name '__pycache__' -print0 | while IFS= read -r -d '' dir; do
  git rm -r --cached "$dir"
done

echo "Añadiendo .gitignore actualizado..."
git add .gitignore

echo "Estado del repositorio tras la limpieza:"
git status --short
