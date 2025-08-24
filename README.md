# Báscula HX711 + Raspberry Pi Zero 2 W

- Script principal: `scale_hx711_pi.py`
- Comandos en ejecución: `t` (tara), `c` (calibrar), `i` (info), `r` (reset), `s` (invertir signo), `q` (salir)
- Persistencia: `scale_store.json` (ignorada por git)

## Requisitos en la Pi
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-rpi.gpio git
