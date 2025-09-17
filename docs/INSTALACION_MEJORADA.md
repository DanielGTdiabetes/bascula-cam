# Guía de Instalación Mejorada - Bascula Cam

Esta guía resume las mejoras aplicadas a la instalación para evitar fallos de permisos,
arranques incompletos de X11 o mensajes como `Only console users are allowed to run the X
server`. El objetivo es que la UI Tk arranque de forma fiable mediante autologin en
`tty1` + `startx`.

## Problemas Corregidos

### 1. Error de directorio de logs
- **Problema**: `Failed to create log directory: /home/pi/.bascula/logs`
- **Solución**: El instalador crea directorios de logs tanto en el home del usuario como
en `/var/log/bascula` con permisos correctos.

### 2. Error de conexión X11
- **Problema**: `ERROR: No se puede conectar al display :0`
- **Solución**: `safe_run.sh` espera a que X11 esté listo, aplica `xset` y oculta el
  cursor automáticamente.

### 3. Arranque gráfico poco fiable
- **Problema**: Servicios systemd que intentaban lanzar Xorg provocaban errores de
  permisos o condiciones de carrera.
- **Solución**: El instalador configura autologin en `tty1`, genera `~/.bash_profile`
  para ejecutar `startx` y crea `~/.xinitrc` que lanza `scripts/safe_run.sh`.

## Instalación

### Prerrequisitos
1. Raspberry Pi con Raspberry Pi OS instalado
2. Usuario `pi` configurado
3. Conexión a internet

### Pasos de Instalación

1. **Clonar el repositorio**:
```bash
cd /home/pi
git clone https://github.com/DanielGTdiabetes/bascula-cam.git
cd bascula-cam
```

2. **Ejecutar instalación completa**:
```bash
sudo TARGET_USER=pi bash ./scripts/install-all.sh --audio=max98357a
```

## Verificación Post-Instalación

1. **Autologin en tty1**:
   ```bash
   sudo systemctl cat getty@tty1.service | sed -n '/\[Service\]/,$p'
   ```
   Debe mostrar la línea `ExecStart=-/sbin/agetty --autologin pi ...`.

2. **`~/.bash_profile` del usuario**:
   ```bash
   cat ~/.bash_profile
   ```
   Debe contener el bloque que ejecuta `startx` sólo cuando no existe `$DISPLAY` y se
   está en `/dev/tty1`.

3. **`~/.xinitrc`**:
   ```bash
   cat ~/.xinitrc
   ```
   Verifica que el archivo ejecuta `scripts/safe_run.sh` y, si procede, exporta
   `BASCULA_APLAY_DEVICE`.

4. **Sesión X activa**:
   ```bash
   pgrep -af startx
   ps -fu pi | grep python | grep bascula-cam
   ```

5. **Logs**:
   ```bash
   tail -n 50 ~/.bascula/logs/xinit.log
   tail -n 50 ~/.bascula/logs/app.log
   ```

## Solución de Problemas

### Si la UI no aparece tras el arranque
1. Comprueba que la sesión de `pi` está en `tty1` con `who`.
2. Revisa `~/.bash_profile` y `~/.xinitrc` en busca de errores de sintaxis.
3. Inspecciona `~/.bascula/logs/xinit.log` para ver si `safe_run.sh` reporta
   problemas de X11.
4. Asegúrate de que `startx` está instalado: `command -v startx`.

### Reiniciar la sesión gráfica manualmente
```bash
sudo pkill -f startx    # termina la sesión X actual
sudo loginctl terminate-user pi  # reinicia completamente la sesión del usuario
```
Después de ejecutar cualquiera de los comandos anteriores, el autologin volverá a
iniciar `startx`.

### Errores de X11
1. **Comprobar que X11 está ejecutándose**:
   ```bash
   ps aux | grep '[X]org'
   ```
2. **Permisos de `.Xauthority`**:
   ```bash
   ls -la ~/.Xauthority
   chmod 600 ~/.Xauthority 2>/dev/null || true
   chown pi:pi ~/.Xauthority 2>/dev/null || true
   ```
3. **Permitir conexiones locales (sólo durante depuración)**:
   ```bash
   xhost +local:
   ```

## Cambios Realizados

### En `install-2-app.sh`:
- Creación de directorios de logs en el home del usuario y en `/var/log/bascula`.
- Configuración de autologin en `tty1`.
- Generación automática de `~/.bash_profile` y `~/.xinitrc`.
- Instalación de los paquetes mínimos (`xserver-xorg`, `xinit`, `unclutter`, etc.).

### En `safe_run.sh`:
- Mejor detección y manejo de displays X11.
- Reintentos automáticos para conexión X11.
- Manejo robusto de errores de display.
- Configuración mejorada de variables de entorno.

## Logs y Diagnóstico

Los logs principales se guardan en:
- `~/.bascula/logs/app.log`
- `~/.bascula/logs/xinit.log`
- `/var/log/bascula/`

Para ver logs en tiempo real:
```bash
tail -f ~/.bascula/logs/app.log
```

Diagnóstico del servicio de autologin (útil si `tty1` no inicia sesión solo):
```bash
sudo journalctl -u getty@tty1 -f
```
