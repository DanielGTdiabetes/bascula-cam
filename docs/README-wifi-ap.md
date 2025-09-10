# Fallback WiFi AP — Paquete para repo

Este paquete está pensado para residir **dentro del repositorio** y que el instalador copie los archivos al sistema cuando se ejecute con `WITH_WIFI_AP=1`.

## Estructura
```
bascula/services/wifi_ap/wifi_ap.py
scripts/wifi_ap/wifi_ap_fallback.sh
system/wifi/wifi-ap.service
system/wifi/wifi-web.service
```

## Variables opcionales
- `AP_SSID` (por defecto `BasculaCam-Setup`)
- `AP_PASS` (por defecto `bascula1234`)
- `AP_IFACE` (por defecto `wlan0`)

Estas variables pueden definirse **antes** de ejecutar el instalador.

## Flujo
1. Si no hay Internet al arrancar, se levanta un AP en `192.168.50.1`.
2. Te conectas al SSID y abres `http://192.168.50.1`.
3. Introduces SSID/clave de tu WiFi real y la Pi intenta conectarse.
