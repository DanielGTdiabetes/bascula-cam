# Pantalla HDMI en Raspberry Pi (Bookworm)

Si la UI no aparece o la Pi entra en un bucle al intentar arrancar X, puede que el monitor/touch no esté anunciando un modo compatible. Para forzar una resolución típica de pantallas 1024x600, añade estas líneas a `config.txt`.

Ruta del archivo según distro:
- Raspberry Pi OS Bookworm: `/boot/firmware/config.txt`
- Versiones antiguas: `/boot/config.txt`

Contenido recomendado (1024x600 @ 60Hz, KMS moderno):

```
# Forzar salida HDMI en 1024x600 @ 60Hz
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 600 60 6 0 0 0

# Usar KMS moderno (aceleración)
dtoverlay=vc4-kms-v3d
```

Después de editar, reinicia:

```
sudo reboot
```

Notas
- Ajusta `hdmi_cvt` a la resolución real de tu panel si no es 1024x600.
- Si usas dos pantallas o adaptadores, valida que el cable/convertidor soporte el modo.
- Para volver a la configuración por defecto, elimina o comenta estas líneas.

