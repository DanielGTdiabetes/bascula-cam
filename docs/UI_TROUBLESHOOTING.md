# Guía de Solución de Problemas - UI Báscula Digital Pro

## Problema: Pantalla Negra con Cursor

### Síntomas
- La aplicación se inicia pero solo muestra una pantalla negra
- Se ve un cursor del mouse
- Los logs no muestran errores críticos

### Soluciones

#### 1. Verificación Rápida del Display

```bash
# Verificar que X11 esté funcionando
xset q

# Si falla, verificar la variable DISPLAY
echo $DISPLAY

# Configurar DISPLAY si es necesario
export DISPLAY=:0
```

#### 2. Usar el Script de Diagnóstico

```bash
cd /opt/bascula/current  # o tu directorio de instalación
python3 scripts/test_ui.py
```

Este script ejecutará pruebas progresivas:
- ✅ Prueba básica de Tkinter
- ✅ Prueba de modo pantalla completa
- ✅ Prueba de la UI completa

#### 3. Usar el Nuevo Script de Inicio Optimizado

```bash
# En lugar de safe_run.sh, usar:
bash scripts/kiosk_start.sh
```

#### 4. Configuración Manual del Entorno Kiosk

```bash
# Configurar variables de entorno
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export XAUTHORITY=$HOME/.Xauthority

# Desactivar protector de pantalla
xset s off -dpms s noblank

# Ocultar cursor
unclutter -idle 1 -root &

# Configurar resolución
xrandr --output HDMI-1 --mode 1024x600

# Fondo negro
xsetroot -solid black
```

## Scripts Disponibles

### 1. `scripts/test_ui.py`
Script de diagnóstico completo que verifica:
- Entorno gráfico
- Funcionalidad básica de Tkinter
- Modo pantalla completa
- UI completa de la báscula

### 2. `scripts/kiosk_start.sh`
Script optimizado para inicio en kiosk que:
- Espera automáticamente a que X11 esté disponible
- Configura el entorno kiosk correctamente
- Maneja errores de display comunes
- Aplica configuración de resolución automática

### 3. `scripts/safe_run.sh` (Mejorado)
Script original mejorado con:
- Verificación de display mejorada
- Reintentos automáticos
- Mejor manejo de errores
- Configuración de pantalla robusta

## Cambios Realizados en la UI

### 1. Configuración Kiosk Robusta
- Modo pantalla completa automático
- Cursor oculto por defecto
- Ventana siempre al frente
- Manejo de errores mejorado

### 2. UI Rediseñada
- **Pantalla de Inicio**: Botones más grandes con iconos
- **Pantalla de Báscula**: Display de peso mejorado con estado
- **Pantalla de Escáner**: Interfaz más clara e intuitiva
- **Pantalla de Configuración**: Organización mejorada con secciones

### 3. Temas Optimizados
- **Tema Moderno**: Colores oscuros con acentos verdes
- **Tema Retro**: Estilo terminal verde sobre negro
- Mejor contraste para pantallas pequeñas

## Comandos de Solución de Problemas

### Verificar Estado del Sistema
```bash
# Verificar procesos X11
ps aux | grep X

# Verificar servicios systemd
systemctl status bascula-ui.service

# Ver logs en tiempo real
tail -f /var/log/bascula/app.log
```

### Reiniciar Servicios
```bash
# Reiniciar servicio de la báscula
sudo systemctl restart bascula-ui.service

# Reiniciar X11 (cuidado - cerrará todas las aplicaciones gráficas)
sudo systemctl restart lightdm
```

### Configuración de Resolución Manual
```bash
# Listar resoluciones disponibles
xrandr

# Configurar resolución específica
xrandr --output HDMI-1 --mode 1024x600

# Configurar resolución personalizada si es necesario
xrandr --newmode "1024x600_60.00" 49.00 1024 1072 1168 1312 600 603 613 624 -hsync +vsync
xrandr --addmode HDMI-1 "1024x600_60.00"
xrandr --output HDMI-1 --mode "1024x600_60.00"
```

## Configuración Systemd Recomendada

Crear/actualizar `/etc/systemd/system/bascula-ui.service`:

```ini
[Unit]
Description=Bascula Digital Pro UI
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/bascula/current
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/1000
ExecStartPre=/bin/sleep 10
ExecStart=/opt/bascula/current/scripts/kiosk_start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

## Logs y Depuración

### Ubicaciones de Logs
- **Aplicación**: `/var/log/bascula/app.log`
- **Kiosk**: `/var/log/bascula/kiosk.log`
- **Sistema**: `journalctl -u bascula-ui.service`

### Activar Modo Debug
```bash
# Ejecutar con logging detallado
PYTHONPATH=/opt/bascula/current python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from bascula.ui.app import BasculaApp
app = BasculaApp()
app.run()
"
```

## Contacto y Soporte

Si los problemas persisten después de seguir esta guía:

1. Ejecutar `scripts/test_ui.py` y guardar la salida
2. Revisar `/var/log/bascula/app.log` para errores específicos
3. Verificar la configuración del hardware (pantalla, resolución)
4. Considerar reinstalar dependencias de Tkinter: `sudo apt install python3-tk`
