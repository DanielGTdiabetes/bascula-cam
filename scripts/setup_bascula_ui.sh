#!/bin/bash
set -e

# Create config directory if it doesn't exist
mkdir -p /home/pi/.config/bascula
chown -R pi:audio /home/pi/.config/bascula
chmod 775 /home/pi/.config/bascula

# Ensure X11 permissions are set correctly
if [ -f /home/pi/.Xauthority ]; then
    chown pi:pi /home/pi/.Xauthority
    chmod 600 /home/pi/.Xauthority
fi

# Set up X11 access
xhost +local: >/dev/null 2>&1 || true

# Create log directory
mkdir -p /var/log/bascula
chown -R pi:audio /var/log/bascula
chmod 775 /var/log/bascula

# Create a symbolic link for the systemd service
if [ -f /home/pi/bascula-cam/systemd/bascula-ui.service ]; then
    sudo cp /home/pi/bascula-cam/systemd/bascula-ui.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable bascula-ui
    echo "Bascula UI service has been installed and enabled."
    echo "To start the service, run: sudo systemctl start bascula-ui"
else
    echo "Error: bascula-ui.service not found in the expected location."
    exit 1
fi

echo "Setup completed successfully!"
