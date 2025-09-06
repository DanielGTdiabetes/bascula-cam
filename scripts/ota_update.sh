#!/usr/bin/env bash
set -euo pipefail

# Ir a la raíz del repo (scripts/..)
cd "$(dirname "$0")/.."
repo_dir="$(pwd)"
parent_dir="$(dirname "$repo_dir")"
clone_dir="${parent_dir}/bascula-cam-update"
backup_dir="${parent_dir}/bascula-cam-backup"

# Limpieza previa
rm -rf "$clone_dir" "$backup_dir"

# Comprobar estado git local (abortamos si hay cambios sin commit)
if ! git -C "$repo_dir" diff --quiet; then
    echo "LOCAL_CHANGES"
    exit 2
fi

# Obtener URL del remoto
remote_url="$(git -C "$repo_dir" config --get remote.origin.url || true)"
if [[ -z "$remote_url" ]]; then
    echo "No se pudo obtener la URL 'origin' del repositorio." >&2
    exit 1
fi

# Obtener rama actual y rama de seguimiento (si existe)
current_branch="$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD || echo "")"
remote_branch=""
if [[ -n "$current_branch" && "$current_branch" != "HEAD" ]]; then
    tracking="$(git -C "$repo_dir" rev-parse --abbrev-ref @{u} 2>/dev/null || echo "")"
    if [[ -n "$tracking" ]]; then
        remote_branch="${tracking#origin/}"
    fi
fi

# Clonar el repo en directorio temporal
if [[ -n "$remote_branch" ]]; then
    git clone --quiet -b "$remote_branch" "$remote_url" "$clone_dir" || {
        echo "No se pudo clonar la última versión desde GitHub." >&2
        rm -rf "$clone_dir"
        exit 1
    }
else
    git clone --quiet "$remote_url" "$clone_dir" || {
        echo "No se pudo clonar la última versión desde GitHub." >&2
        rm -rf "$clone_dir"
        exit 1
    }
fi

# Backup del código actual
mv "$repo_dir" "$backup_dir" || {
    echo "No se pudo mover el directorio actual a backup." >&2
    rm -rf "$clone_dir"
    exit 1
}

# Poner nueva versión en el directorio original
mv "$clone_dir" "$repo_dir" || {
    echo "No se pudo colocar la nueva versión en el directorio original." >&2
    mv "$backup_dir" "$repo_dir" || echo "Error crítico: no se pudo restaurar el directorio original." >&2
    rm -rf "$clone_dir"
    exit 1
}

# Mover entorno virtual (.venv) del backup a la nueva versión (si existe)
env_moved=false
if [[ -d "$backup_dir/.venv" ]]; then
    mv "$backup_dir/.venv" "$repo_dir" || {
        echo "No se pudo mover el entorno virtual al nuevo código." >&2
        mv "$repo_dir" "${repo_dir}.new" 2>/dev/null || true
        mv "$backup_dir" "$repo_dir" || echo "Error crítico: no se pudo restaurar el directorio original." >&2
        rm -rf "${repo_dir}.new"
        rm -rf "$clone_dir"
        exit 1
    }
    env_moved=true
fi

# Copiar archivo de configuración (config.json) del backup a la nueva versión, si existe
if [[ -f "$backup_dir/config.json" ]]; then
    cp "$backup_dir/config.json" "$repo_dir/" || {
        echo "No se pudo copiar el archivo de configuración del usuario." >&2
        $env_moved && mv "$repo_dir/.venv" "$backup_dir" 2>/dev/null || true
        rm -rf "$repo_dir"
        mv "$backup_dir" "$repo_dir" || echo "Error crítico: no se pudo restaurar el directorio original." >&2
        rm -rf "$clone_dir"
        echo "UPDATE_FAILED"
        exit 1
    }
fi

# Actualizar dependencias si hay requirements.txt
if [[ -f "$repo_dir/requirements.txt" ]]; then
    set +e
    if [[ -x "$repo_dir/.venv/bin/python3" ]]; then
        "$repo_dir/.venv/bin/python3" -m pip install -U -r "$repo_dir/requirements.txt"
    else
        python3 -m pip install -U -r "$repo_dir/requirements.txt"
    fi
    set -e
fi

# Verificar que la app carga correctamente con la nueva versión
if [[ -x "$repo_dir/.venv/bin/python3" ]]; then
    "$repo_dir/.venv/bin/python3" - <<'PY' || {
        # Revertir a la versión anterior si falla
        $env_moved && mv "$repo_dir/.venv" "$backup_dir" 2>/dev/null || true
        rm -rf "$repo_dir"
        mv "$backup_dir" "$repo_dir" || echo "Error crítico: no se pudo restaurar el directorio original." >&2
        rm -rf "$clone_dir"
        echo "UPDATE_FAILED"
        exit 1
    }
import importlib
import sys
import traceback
try:
    import bascula.ui.app  # punto de entrada principal
except Exception:
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
PY
else
    python3 - <<'PY' || {
        $env_moved && mv "$repo_dir/.venv" "$backup_dir" 2>/dev/null || true
        rm -rf "$repo_dir"
        mv "$backup_dir" "$repo_dir" || echo "Error crítico: no se pudo restaurar el directorio original." >&2
        rm -rf "$clone_dir"
        echo "UPDATE_FAILED"
        exit 1
    }
import importlib
import sys
import traceback
try:
    import bascula.ui.app
except Exception:
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
PY
fi

# Éxito: eliminar backup
rm -rf "$backup_dir"
echo "UPDATE_OK"
exit 0
