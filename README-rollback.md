# Rollback a arranque minimalista (Xorg + Tk) — sin LightDM ni Openbox

Este documento devuelve la **Báscula Digital Pro** al modo anterior: arranque rápido, sin gestor de sesiones ni de ventanas, con Xorg “pelado”, cursor oculto y sin saver/DPMS. Es la configuración recomendada para Raspberry Pi Zero 2 W.

## Qué hace

- Desactiva (y opcionalmente **purga**) `lightdm` y `openbox`.
- Configura **autologin en TTY1**.
- Instala `unclutter-xfixes` para ocultar el puntero de forma robusta.
- Crea `~/.bash_profile` para lanzar `startx -- -nocursor` sólo en TTY1.
- Crea `~/.xinitrc` minimalista (xset, fondo negro y `python3 .../main.py`).
- Limpia restos de autostart de Openbox para evitar que reaparezca el puntero o el screensaver.
- Deja logs de la app en `~/app_main.log`.

## Requisitos

- Haber actualizado el repositorio con estos archivos:
