# BMO Face 🎮

A cute, animated BMO-style face for Raspberry Pi 5 + 5" LCD touchscreen.

## What's In Here

| File | What It Does |
|------|-------------|
| `bmo_face.py` | Main face animation — 7 expressions, blinking, bouncing |
| `face_control.py` | TCP control server — lets other programs change the face |
| `face_client.py` | Python client + CLI tool to send face commands |
| `pip_bridge.py` | Connection between Pi hardware and Pip (cloud brain) |
| `setup_pi.sh` | One-shot Pi setup — installs everything, configures autostart |

## Quick Start

On your Raspberry Pi 5:

```bash
# 1. Clone or copy this folder to the Pi
# 2. Run the setup script
chmod +x setup_pi.sh
./setup_pi.sh

# 3. Reboot — BMO face starts automatically
sudo reboot
```

## Expressions

| Key | Expression | Description |
|-----|-----------|-------------|
| 1 | happy | Squinty eyes, big smile, pink blush |
| 2 | talking | Mouth opens/closes rhythmically |
| 3 | surprised | Wide eyes with highlights, O mouth |
| 4 | love | Heart eyes, blush, gentle smile |
| 5 | sleepy | Droopy eyes, wavy mouth, floating Zzz |
| 6 | angry | Angled eyebrows, frown |
| Space | idle | Default face, natural blinking |
| F | — | Toggle fullscreen |
| Q/Esc | — | Quit |

## Remote Control (from other scripts)

```bash
# Simple — just pipe expression name
echo "happy" | nc localhost 5555
echo "surprised" | nc localhost 5555

# CLI tool
python3 face_client.py happy
python3 face_client.py sleepy

# Python
from face_client import set_expression
set_expression("love")
```

## Architecture

```
┌──────────────┐     ┌──────────────┐
│  Microphone  │────▶│              │
│  (STT)       │     │    Pip     │
├──────────────┤     │   Bridge     │
│   Camera     │────▶│              │
│  (Vision)    │     │  cosmo_      │
├──────────────┤     │  bridge.py   │
│   Pip      │◀───▶│              │
│  (Cloud AI)  │     └──────┬───────┘
└──────────────┘            │
                            │ TCP :5555
                    ┌───────▼───────┐
                    │   BMO Face    │
                    │  bmo_face.py  │
                    │               │
                    │  ┌─────────┐  │
                    │  │  5" LCD │  │
                    │  │  😊🎮  │  │
                    │  └─────────┘  │
                    └───────────────┘
```

## Service Management

```bash
sudo systemctl start bmo-face    # Start face
sudo systemctl stop bmo-face     # Stop face
sudo systemctl status bmo-face   # Check status
journalctl -u bmo-face -f        # Live logs
```

## Hardware

- Raspberry Pi 5 (8GB)
- Hosyond 5" Touchscreen (800x480, HDMI)
- USB Mini Speaker
- USB Mini Microphone
- Arducam Pi AI Camera
- Raspberry Pi AI HAT+ 2

## Roadmap

- [x] Animated face with 7 expressions
- [x] Control server for remote expression changes
- [x] Auto-start on boot
- [x] Setup script
- [ ] Speech-to-text (mic input)
- [ ] Text-to-speech (speaker output)
- [ ] Camera face detection
- [ ] Pip cloud brain integration
- [ ] Wheeled robot body
- [ ] Local AI inference via AI HAT+

---
*Built by Brooks & Pip 🛸*
