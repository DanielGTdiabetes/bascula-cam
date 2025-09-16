#!/usr/bin/env bash
set -euo pipefail

UNIT=/etc/systemd/system/bascula-ui.service

sudo tee "$UNIT" >/dev/null <<'UNIT'
[Unit]
Description=Bascula UI (Tkinter)
After=network-online.target sound.target kiosk-xorg.service
Wants=kiosk-xorg.service

[Service]
User=pi
Group=audio
WorkingDirectory=/home/pi/bascula-cam
Environment=BASCULA_CFG_DIR=/home/pi/.config/bascula
Environment=DISPLAY=:0
# Descomenta si quieres fijar la tarjeta ALSA
#Environment=BASCULA_APLAY_DEVICE=plughw:1,0

ExecStart=/bin/bash -lc 'if [ -x /home/pi/bascula-cam/.venv/bin/python ]; then /home/pi/bascula-cam/.venv/bin/python /home/pi/bascula-cam/bascula/main.py; else python3 /home/pi/bascula-cam/bascula/main.py; fi'

Restart=on-failure
RestartSec=3
DeviceAllow=char-116:*     # /dev/snd/*
ProtectHome=no

[Install]
WantedBy=graphical.target multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now bascula-ui.service
sudo systemctl restart bascula-ui.service
systemctl status bascula-ui.service --no-pager -l || true
