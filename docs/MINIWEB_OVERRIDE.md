# Mini‑web: override de systemd menos estricto

Este proyecto instala un servicio systemd `bascula-web.service` que, por defecto,
viene endurecido para exponer la API solo en `127.0.0.1:8080` (loopback).

Para abrir la mini‑web a la red (escuchar en `0.0.0.0`) y relajar los filtros
de red de systemd, se crea un override (`/etc/systemd/system/bascula-web.service.d/override.conf`).

## Opción 1: Instalar y abrir en un paso

```bash
make install-web-open            # instala y crea override menos estricto
make show-url                    # muestra URL accesible en la LAN
make show-pin                    # muestra el PIN de acceso
```

## Opción 2: Si ya está instalado, abrir después

```bash
make allow-lan                   # crea override con BASCULA_WEB_HOST=0.0.0.0
make show-url && make show-pin
```

El override que se genera contiene:

```ini
[Service]
Environment=BASCULA_WEB_HOST=0.0.0.0
# Menos estricto: sin filtros IP a nivel de systemd
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressAllow=
IPAddressDeny=
```

Esto borra los filtros `IPAddressAllow/Deny` definidos en la unidad base y
permite atender conexiones desde cualquier IP de las interfaces del equipo.
Además, permite IPv4 e IPv6 (añadiendo `AF_INET6`).

## Volver a modo local (más seguro)

```bash
make local-only                  # elimina el override y reinicia el servicio
```

## Notas de seguridad

- Con el override activo, la API queda disponible en la red. Mantén el PIN,
  restringe la red (VLAN/Firewall) si procede y evita exponerlo a Internet sin
  una capa adicional (reverse proxy con autenticación, TLS, etc.).
- El resto de directivas de hardening del servicio (p. ej. `NoNewPrivileges`,
  `ProtectSystem`, etc.) permanecen activas; solo se relajan los filtros de IP
  y el host de escucha.
