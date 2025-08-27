
# Arranque automático de SMART BÁSCULA CAM (Raspberry Pi)

Hay dos métodos. **Recomendado: systemd (usuario).** Alternativa: Autostart (.desktop).

## 1) Método recomendado — systemd (usuario)
1. Copia esta carpeta `bascula-cam-systemd` en tu HOME del Pi (ej. `/home/pi/`).
2. Crea la carpeta de unidades de usuario:
   ```bash
   mkdir -p ~/.config/systemd/user
   ```
3. Copia el servicio:
   ```bash
   cp ~/bascula-cam-systemd/systemd/bascula-cam.service ~/.config/systemd/user/
   ```
4. Habilita el modo de "user lingering" (para que arranque al inicio):
   ```bash
   sudo loginctl enable-linger $USER
   ```
5. Habilita y arranca el servicio:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable bascula-cam.service
   systemctl --user start bascula-cam.service
   ```
6. Logs:
   ```bash
   journalctl --user -u bascula-cam -f
   ```

**Notas:**
- El servicio asume que tu proyecto vive en `~/bascula-cam` y el venv en `~/bascula-cam/venv`.
- El script `scripts/run-bascula.sh` exporta `DISPLAY=:0` y ejecuta `main.py`.
- Si tu entorno X exige autorización, descomenta `XAUTHORITY=%h/.Xauthority` en el servicio.

## 2) Alternativa — Autostart (LXDE/LXQt)
1. Copia el `.desktop`:
   ```bash
   mkdir -p ~/.config/autostart
   cp ~/bascula-cam-systemd/systemd/bascula-cam.desktop ~/.config/autostart/
   ```
2. **Edita** la ruta `Exec=` del `.desktop` para tu usuario (ej. `/home/pi/...`).

## Variables útiles
- `APP_DIR`: carpeta del proyecto (por defecto `~/bascula-cam`).
- `VENV_DIR`: venv (por defecto `~/bascula-cam/venv`).
- `PYTHON_BIN`: binario python a usar.
- `MAIN_FILE`: ruta a `main.py`.

Puedes sobreescribirlas en el propio servicio con líneas `Environment=`.

## Troubleshooting
- Si la ventana no aparece, ejecuta manualmente:
  ```bash
  DISPLAY=:0 ~/bascula-cam-systemd/scripts/run-bascula.sh
  ```
- Comprueba que el usuario tiene sesión gráfica iniciada y permisos sobre `:0`.
- Revisa `journalctl --user -u bascula-cam -e` para errores de Python/Tk.
