#!/bin/bash
set -e

# Create Xauthority file if it doesn't exist
if [ ! -f /home/pi/.Xauthority ]; then
    echo "Creating Xauthority file…"
    touch /home/pi/.Xauthority
    chmod 600 /home/pi/.Xauthority
    chown pi:pi /home/pi/.Xauthority
    
    # Generate X11 magic cookie
    mcookie | sed -e 's/^/add :0 . /' | xauth -q
fi

# Fix X11 permissions
xhost +local:

# Ensure the display is accessible
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority

# Set up pulseaudio permissions
if [ -S /run/user/1000/pulse/native ]; then
    chmod 660 /run/user/1000/pulse/native
    chown pi:audio /run/user/1000/pulse/native
fi

echo "X11 setup complete. You can now start the bascula-ui service."
