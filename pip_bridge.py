#!/usr/bin/env python3
"""
Pip Bridge — connects the Pi to Pip (cloud) via Telegram.
This is the brain link: sends what the Pi sees/hears to Pip,
and receives responses back to control the face/voice.

This runs on the Pi and acts as middleware between:
  - The BMO face (via face_client)
  - The microphone (speech-to-text)
  - The speaker (text-to-speech)
  - The camera (image capture)
  - Pip cloud brain (via Telegram Bot API or OpenClaw gateway)

Phase 1: Basic text chat relay
Phase 2: Voice input/output
Phase 3: Camera vision
Phase 4: Full autonomy
"""

import os
import sys
import json
import time
import threading
import subprocess
import urllib.request
import urllib.parse

# Local imports
from face_client import set_expression

# --- Configuration ---

CONFIG_FILE = os.path.expanduser("~/bmo-face/pip_config.json")

DEFAULT_CONFIG = {
    "mode": "telegram",       # "telegram" or "gateway" (direct OpenClaw connection)
    "telegram_token": "",     # Same bot token as OpenClaw uses
    "telegram_chat_id": "",   # Brooks's Telegram chat ID
    "gateway_url": "",        # OpenClaw gateway URL (for future direct connection)
    "gateway_token": "",      # OpenClaw gateway auth token
    "tts_enabled": False,     # Text-to-speech on Pi
    "stt_enabled": False,     # Speech-to-text on Pi
    "camera_enabled": False,  # Camera capture
}


def load_config():
    """Load or create config file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save config to file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


class PipBridge:
    """Main bridge between Pi hardware and Pip cloud brain."""

    def __init__(self):
        self.config = load_config()
        self.running = False
        self.last_expression = "idle"

    def start(self):
        """Start the bridge."""
        self.running = True
        print("🛸 Pip Bridge starting...")
        print(f"   Mode: {self.config['mode']}")

        # Set happy face on startup
        set_expression("happy")
        time.sleep(2)
        set_expression("idle")

        print("🛸 Pip Bridge ready!")
        print("   Waiting for interactions...")

    def stop(self):
        """Stop the bridge."""
        self.running = False
        set_expression("sleepy")
        print("🛸 Pip Bridge stopped.")

    def express(self, expression):
        """Change face expression."""
        if expression != self.last_expression:
            set_expression(expression)
            self.last_expression = expression

    def on_hearing(self, text):
        """Called when speech-to-text detects spoken words."""
        print(f"[Heard] {text}")
        self.express("talking")
        # TODO: Send to Pip brain and get response
        # TODO: Speak the response via TTS
        time.sleep(1)
        self.express("idle")

    def on_seeing(self, image_path):
        """Called when camera captures something interesting."""
        print(f"[Saw] {image_path}")
        self.express("surprised")
        # TODO: Send image to Pip brain for analysis
        time.sleep(1)
        self.express("idle")


def main():
    bridge = PipBridge()

    try:
        bridge.start()
        # Keep running
        while bridge.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛸 Shutting down...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
