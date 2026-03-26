#!/bin/bash
# Pip Pi Setup — Run this once on a fresh Raspberry Pi 5
# Usage: chmod +x setup.sh && ./setup.sh

set -e
echo "🫧 Setting up Pip on Raspberry Pi 5..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pygame python3-pip espeak git

# Install Python packages
pip3 install --break-system-packages openai pillow

# Optional: Install Piper TTS for offline voice
echo "Installing Piper TTS for offline voice..."
sudo apt install -y piper || echo "Piper not in repo — will use espeak as fallback"

# Create voices directory
mkdir -p voices

# Download Piper voice model (if piper installed)
if command -v piper &> /dev/null; then
    if [ ! -f voices/en_US-lessac-medium.onnx ]; then
        echo "Downloading voice model..."
        wget -q -O voices/en_US-lessac-medium.onnx \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" || true
        wget -q -O voices/en_US-lessac-medium.onnx.json \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" || true
    fi
fi

# Create systemd service for autostart
sudo tee /etc/systemd/system/pip.service > /dev/null << 'EOF'
[Unit]
Description=Pip BMO Companion
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/pip-pi
ExecStart=/usr/bin/python3 /home/pi/pip-pi/pip_pi.py
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=SDL_FBDEV=/dev/fb0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pip.service

echo ""
echo "🫧 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Create pip_brain_config.json with your API key:"
echo '     echo {"api_key": "YOUR-KEY-HERE"} > pip_brain_config.json'
echo "  2. Test it: python3 pip_pi.py"
echo "  3. Reboot to auto-start: sudo reboot"
echo ""
