# Procedimiento de Rollback

Si la nueva interfaz táctil presenta problemas críticos se recomienda revertir al release anterior siguiendo estos pasos.

## 1. Detener servicios
```bash
sudo systemctl stop bascula-ui.service
sudo systemctl stop bascula-miniweb.service
```

## 2. Restaurar código
```bash
cd ~/bascula-cam
git fetch --tags
git checkout <tag-estable-anterior>
```
Sustituya `<tag-estable-anterior>` por la etiqueta o commit validado previamente (por ejemplo `v2023.12`).

## 3. Restaurar configuración y assets
- Reemplace `~/.config/bascula/` con la copia de seguridad realizada antes de la migración.
- Elimine la carpeta generada `bascula/ui/assets/mascota/_gen/` si no existía en la versión previa.

## 4. Dependencias
Dentro del repositorio ejecuta:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Asegúrese de reinstalar cualquier paquete adicional usado por la versión anterior (por ejemplo `tkmacosx`).

## 5. Verificación del rollback
Ejecute los diagnósticos originales:
```bash
python tools/check_scale.py
python tools/smoke_nav.py
```
Confirme que la antigua interfaz aparece al ejecutar `python main.py`.

## 6. Rehabilitar servicios
```bash
sudo systemctl daemon-reload
sudo systemctl start bascula-miniweb.service
sudo systemctl start bascula-ui.service
```

## 7. Registro del incidente
Documente en el runbook los motivos del rollback y los logs relevantes (`logs/ui.log`, `journalctl -u bascula-ui`).

