# CI pipeline guide

## Entorno

- `BASCULA_CI=1` activa modo CI en scripts e instaladores.
- `DESTDIR=/tmp/ci-root` es el prefijo de staging utilizado para empaquetar la imagen. Todos los tests deben respetarlo y nunca escribir fuera.
- El mock de systemd (`ci/mocks/systemctl`) **debe** ser el primero en `PATH` durante los tests; `ci/bin/ci-doctor.sh` valida este requisito automáticamente.

Antes de cada paso el workflow ejecuta `ci/bin/ci-doctor.sh`. Este script registra la versión de las herramientas clave, limpia residuos (`/tmp/bascula_force_recovery`, `DESTDIR/opt/bascula/*`, flags de recovery) y guarda la salida en `ci-logs/doctor.txt`. Solo vuelca un subconjunto de variables (`BASCULA_CI`, `DESTDIR`, `SHELL`, `PWD`, `PATH`) y redacta cualquier coincidencia con patrones de credenciales antes de registrarla. Cualquier etapa local debería iniciarse llamándolo manualmente.

## Ejecutar los tests

Desde la raíz del repo:

```bash
export BASCULA_CI=1
export DESTDIR=/tmp/ci-root
mkdir -p ci-logs
PATH="$(pwd)/ci/mocks:$PATH" ci/bin/ci-doctor.sh "local-run"
PATH="$(pwd)/ci/mocks:$PATH" bash ci/tests/test_min.sh
```

Cada script bajo `ci/tests/` se auto-registra en `ci-logs/<test>.log`, limpia los flags temporales y reutiliza el mock de `systemctl`.

## Contrato `safe_run.sh`

- Flags de entrada fijas:
  - Boot: `/boot/bascula-recovery`
  - Persistente: `/opt/bascula/shared/userdata/force_recovery`
  - Temporal: `/tmp/bascula_force_recovery`
- `trigger_recovery_exit "watchdog"` crea la flag temporal y devuelve `0` al iniciar correctamente `bascula-recovery.target`, `3` si `systemctl` falla.
- `trigger_recovery_exit "external"` elimina cualquier flag temporal antes/después de llamar a `systemctl`, y retorna `0` al tener éxito, `3` si la activación falla, `2` si no existen flags.
- Códigos de salida documentados en el propio script: `0` recovery lanzado, `1` `main.py` ausente, `2` sin heartbeat, `3` fallo al lanzar recovery o heartbeat obsoleto.

Todos los tests deben ejecutarse con `set -euo pipefail` e `IFS=$'\n\t'`. Los logs generados se guardan en `ci-logs/` y el workflow solo los adjunta como artefacto cuando falla algún paso o cuando se exporta `CI_ATTACH_LOGS=1` (en verde). Esto evita subir registros innecesarios que puedan contener rutas sensibles.
