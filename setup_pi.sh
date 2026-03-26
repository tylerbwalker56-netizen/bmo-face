#!/bin/bash
# ============================================================
#  BMO Setup Script for Raspberry Pi 5
#  Run this once after flashing Raspberry Pi OS.
#  
#  Usage: 
#    chmod +x setup_pi.sh
#    ./setup_pi.sh
# ============================================================

set -e

echo ""
echo "🎮 BMO Setup Script"
echo "==================="
echo ""

# --- 1. System update ---
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# --- 2. Install dependencies ---
echo "[2/6] Installing dependencies..."
sudo apt install -y \
    python3-pygame \
    python3-pip \
    python3-venv \
    git \
    curl \
    net-tools \
    pulseaudio \
    alsa-utils \
    mpv \
    ffmpeg

# Python packages
pip3 install --break-system-packages \
    openai \
    pyboy \
    stable-baselines3 \
    gymnasium \
    numpy

# --- 3. Configure 5" HDMI touchscreen ---
echo "[3/6] Configuring display..."

CONFIG_FILE="/boot/firmware/config.txt"

# Check if display settings already added
if grep -q "# BMO Display Config" "$CONFIG_FILE" 2>/dev/null; then
    echo "  Display config already present, skipping."
else
    echo "  Adding display configuration..."
    sudo tee -a "$CONFIG_FILE" > /dev/null << 'EOF'

# BMO Display Config
hdmi_group=2
hdmi_mode=87
hdmi_cvt 800 480 60 6 0 0 0
hdmi_drive=1
EOF
    echo "  Display config added to $CONFIG_FILE"
    echo "  NOTE: If your Hosyond screen uses a different driver, we may"
    echo "  need to adjust this. The screen should work on first boot —"
    echo "  if not, we'll troubleshoot together."
fi

# --- 4. Set up BMO face directory ---
echo "[4/6] Setting up BMO face..."
BMO_DIR="$HOME/bmo-face"
if [ ! -d "$BMO_DIR" ]; then
    mkdir -p "$BMO_DIR"
    echo "  Created $BMO_DIR"
fi

# Copy files if running from the repo
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/bmo_face.py" ]; then
    cp "$SCRIPT_DIR/bmo_face.py" "$BMO_DIR/"
    cp "$SCRIPT_DIR/face_control.py" "$BMO_DIR/"
    cp "$SCRIPT_DIR/face_client.py" "$BMO_DIR/"
    echo "  Copied BMO face files to $BMO_DIR"
fi

# --- 5. Set up auto-start on boot ---
echo "[5/6] Configuring auto-start..."

# Create systemd service for BMO face
sudo tee /etc/systemd/system/bmo-face.service > /dev/null << EOF
[Unit]
Description=BMO Face Animation
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u)
WorkingDirectory=$BMO_DIR
ExecStart=/usr/bin/python3 $BMO_DIR/bmo_face.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable bmo-face.service
echo "  BMO face will auto-start on boot"

# --- 6. Audio setup ---
echo "[6/6] Setting up audio..."
# Make sure audio is enabled and USB speaker will be detected
if ! grep -q "dtparam=audio=on" "$CONFIG_FILE"; then
    echo "dtparam=audio=on" | sudo tee -a "$CONFIG_FILE" > /dev/null
fi
echo "  Audio enabled. USB speaker will be configured when plugged in."

# --- Done ---
echo ""
echo "============================================"
echo "🎮 BMO setup complete!"
echo "============================================"
echo ""
echo "What's next:"
echo "  1. Connect your 5\" screen to the Pi"
echo "  2. Reboot:  sudo reboot"
echo "  3. BMO face should start automatically!"
echo ""
echo "Manual controls:"
echo "  Start:   sudo systemctl start bmo-face"
echo "  Stop:    sudo systemctl stop bmo-face"
echo "  Status:  sudo systemctl status bmo-face"
echo "  Logs:    journalctl -u bmo-face -f"
echo ""
echo "Set your OpenAI API key:"
echo "  nano ~/bmo-face/pip_brain_config.json"
echo "  (paste your key in the openai_api_key field)"
echo ""
echo "Start Pip's full system:"
echo "  cd ~/bmo-face && python3 pip_main.py"
echo ""
echo "Change expressions from terminal:"
echo "  echo 'happy' | nc localhost 5555"
echo "  python3 ~/bmo-face/face_client.py surprised"
echo ""
echo "🫧 Pip says: Let's bring BMO to life!"
echo ""
