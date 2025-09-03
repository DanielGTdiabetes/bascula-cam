# Permisos mínimos para gestionar Wi‑Fi con nmcli

Para permitir que el usuario de la app conecte redes Wi‑Fi sin `sudo`, añade una regla de polkit para NetworkManager.

## Opción rápida (Makefile)

Desde la raíz del repo:

```
make install-polkit                 # usa BASCULA_USER=bascula por defecto
make install-polkit BASCULA_USER=pi # si quieres usar 'pi'
make restart-nm                     # reinicia NetworkManager (opcional)
```

Esto crea `/etc/polkit-1/rules.d/50-bascula-nm.rules` con permisos para:
- `org.freedesktop.NetworkManager.settings.modify.system`
- `org.freedesktop.NetworkManager.network-control`
- `org.freedesktop.NetworkManager.enable-disable-wifi`

## Opción manual

1) Crea el archivo (como root): `/etc/polkit-1/rules.d/50-bascula-nm.rules`

Contenido sugerido (sustituye `bascula` por tu usuario si aplica):

```
polkit.addRule(function(action, subject) {
  if (subject.user == "bascula" || subject.isInGroup("bascula")) {
    // Permitir gestión Wi‑Fi con NetworkManager
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" ||
        action.id == "org.freedesktop.NetworkManager.network-control" ||
        action.id == "org.freedesktop.NetworkManager.enable-disable-wifi") {
      return polkit.Result.YES;
    }
  }
});
```

2) Reinicia polkit/NetworkManager:

```
sudo systemctl restart polkit
sudo systemctl restart NetworkManager
```

Con esto, las llamadas `nmcli dev wifi connect …` desde el usuario configurado no requerirán contraseña (limitadas a las acciones indicadas).
