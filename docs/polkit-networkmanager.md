# Permisos mínimos para gestionar Wi‑Fi con nmcli

Para permitir que el usuario `bascula` conecte redes Wi‑Fi sin `sudo`, añade una regla de polkit.

1) Crea el archivo (como root): `/etc/polkit-1/rules.d/50-bascula-nm.rules`

Contenido sugerido:

```
polkit.addRule(function(action, subject) {
  if (subject.isInGroup("bascula") || subject.user == "bascula") {
    // Permitir gestión de conexiones Wi‑Fi con NetworkManager
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" ||
        action.id == "org.freedesktop.NetworkManager.network-control") {
      return polkit.Result.YES;
    }
  }
});
```

2) Crea el usuario/grupo si no existe y añade el servicio/UI a ese usuario.

3) Reinicia polkit/NetworkManager:

```
sudo systemctl restart polkit
sudo systemctl restart NetworkManager
```

Con esto, las llamadas `nmcli dev wifi connect …` desde el usuario `bascula` no requerirán contraseña, limitadas a las acciones indicadas.

