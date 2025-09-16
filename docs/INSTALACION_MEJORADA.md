# Guía de Instalación Mejorada - Bascula Cam

Esta guía incluye las correcciones para evitar los errores comunes de instalación relacionados con permisos y configuración X11.

## Problemas Corregidos

### 1. Error de directorio de logs
- **Problema**: `Failed to create log directory: /home/pi/.bascula/logs`
- **Solución**: El script ahora crea directorios de logs tanto en el home del usuario como en `/var/log/bascula` con permisos correctos.

### 2. Error de conexión X11
- **Problema**: `ERROR: No se puede conectar al display :0`
- **Solución**: Mejorada la detección y configuración automática de X11 con reintentos y fallbacks.

### 3. Error de permisos de servicio
- **Problema**: `Permission denied` al cambiar directorio de trabajo
- **Solución**: Configuración explícita de permisos y variables de entorno en el servicio systemd.

## Instalación

### Prerrequisitos
1. Raspberry Pi con Raspberry Pi OS instalado
2. Usuario `pi` configurado
3. Entorno gráfico funcionando (X11)
4. Conexión a internet

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

### Verificación Post-Instalación

1. **Verificar estado del servicio**:
```bash
sudo systemctl status bascula-ui
```

2. **Verificar logs**:
```bash
journalctl -u bascula-ui -n 20 --no-pager
```

3. **Verificar permisos**:
```bash
ls -la /home/pi/.bascula/logs/
ls -la /var/log/bascula/
```

4. **Verificar X11**:
```bash
echo $DISPLAY
xset -q
```

## Solución de Problemas

### Si el servicio no inicia

1. **Verificar permisos de directorio**:
```bash
sudo chown -R pi:audio /home/pi/bascula-cam
sudo chmod 755 /home/pi/bascula-cam
```

2. **Verificar X11**:
```bash
export DISPLAY=:0
xhost +local:pi
```

3. **Recrear directorios de logs**:
```bash
sudo mkdir -p /home/pi/.bascula/logs
sudo chown pi:audio /home/pi/.bascula/logs
sudo chmod 755 /home/pi/.bascula/logs
```

4. **Reiniciar servicio**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart bascula-ui
```

### Si hay errores de X11

1. **Verificar que X11 está ejecutándose**:
```bash
ps aux | grep X
```

2. **Verificar permisos de .Xauthority**:
```bash
ls -la /home/pi/.Xauthority
sudo chown pi:pi /home/pi/.Xauthority
sudo chmod 600 /home/pi/.Xauthority
```

3. **Configurar acceso X11**:
```bash
xhost +local:pi
```

## Cambios Realizados

### En `install-2-app.sh`:
- Creación de directorio de logs en el home del usuario
- Configuración automática de X11 para el usuario
- Verificación de permisos antes de iniciar el servicio
- Espera adicional antes de iniciar el servicio

### En `safe_run.sh`:
- Mejor detección y manejo de displays X11
- Reintentos automáticos para conexión X11
- Manejo robusto de errores de display
- Configuración mejorada de variables de entorno

### En `bascula-ui.service`:
- Configuración explícita de variables de entorno
- Mejores permisos de seguridad
- Configuración robusta de directorio de trabajo

## Logs y Diagnóstico

Los logs se guardan en:
- `/home/pi/.bascula/logs/app.log` (principal)
- `/var/log/bascula/` (fallback)
- `/tmp/bascula-logs/` (último recurso)

Para ver logs en tiempo real:
```bash
tail -f /home/pi/.bascula/logs/app.log
```

Para diagnóstico completo:
```bash
sudo journalctl -u bascula-ui -f
```
