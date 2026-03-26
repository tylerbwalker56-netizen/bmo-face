# Pip Quick Start Guide 🫧
### For Brooks — all the commands you need

---

## 🖥️ Run Pip's Face (Windows Desktop)

```
cd C:\Users\tyler\Desktop\bmo-face-main
C:\Users\tyler\AppData\Local\Programs\Python\Python314\python.exe pip_desktop.py
```

---

## 🎮 Run Pokémon Player (Windows Desktop)

### First time setup (only do once):
```
C:\Users\tyler\AppData\Local\Programs\Python\Python314\python.exe -m pip install pillow numpy
```

### Make sure these exist:
- mGBA installed on your PC
- ROM file at: `C:\Users\tyler\Desktop\bmo-face-main\pokemon\pokemonunbound\Pokemon Unbound (v2.1.1.1).gba`

### Run it:
```
cd C:\Users\tyler\Desktop\bmo-face-main\pokemon
C:\Users\tyler\AppData\Local\Programs\Python\Python314\python.exe pokemon_player.py
```

### Stop it:
- Press **Ctrl+C** in the command prompt window

---

## 🍓 Raspberry Pi Setup (when SD card is working)

### Step 1 — Flash SD Card
1. Open **Raspberry Pi Imager** on your PC
2. Device: **Raspberry Pi 5**
3. OS: **Raspberry Pi OS (64-bit)** (the Recommended one)
4. Storage: your SD card
5. Click Next → Edit Settings:
   - Set username & password
   - Enter Wi-Fi name & password
   - Services tab → Enable SSH
6. Write it, wait for verify, safely eject

### Step 2 — Update Bootloader (if Pi won't boot)
1. In Raspberry Pi Imager, Choose OS → scroll to **Misc utility images**
2. **Bootloader** → **Pi 5 family** → **SD Card Boot**
3. Flash to SD card
4. Put in Pi, power on
5. Wait for green LED to go **solid green** (~10 sec)
6. Power off, then re-flash with the real OS (Step 1)

### Step 3 — First Boot
1. Put SD card in Pi, plug in power
2. Green LED should flicker fast (booting)
3. Wait 2-3 minutes for first boot

### Step 4 — Get Code on Pi
**Easy way:**
- Open browser on Pi
- Go to: https://github.com/tylerbwalker56-netizen/bmo-face
- Green Code button → Download ZIP
- Extract to home folder

**Or terminal way:**
```
git clone https://github.com/tylerbwalker56-netizen/bmo-face.git
```

### Step 5 — Run Setup Script
```
cd bmo-face
chmod +x setup_pi.sh
./setup_pi.sh
```

### Step 6 — Add API Key
Create the file `pip_brain_config.json` in the bmo-face folder:
```
nano pip_brain_config.json
```
Type this (all one line):
```
{"api_key": "YOUR-OPENAI-API-KEY-HERE"}
```
Press **Ctrl+X**, then **Y**, then **Enter** to save.

### Step 7 — Run Pip
```
cd bmo-face
python3 pip_desktop.py
```

---

## 🔌 Display Connection (Hosyond 5" DSI)
- Uses **ribbon cable only** (no HDMI, no extra wires)
- Connect to **DISP 0** or **DISP 1** on the Pi
- Metal contacts on ribbon face **toward the board**
- If no picture, try **flipping the ribbon 180°** or the **other DISP port**
- GND/PWM pins on display = backlight brightness only, not required

---

## 📁 Important Files
| File | What it does |
|------|-------------|
| `pip_desktop.py` | Pip's face + chat (runs on PC or Pi) |
| `pip_brain_config.json` | Your OpenAI API key (keep secret!) |
| `pokemon/pokemon_player.py` | Pokémon AI player |
| `setup_pi.sh` | One-shot Pi setup script |

---

## 🔑 Your Info (for reference)
- **Python path:** `C:\Users\tyler\AppData\Local\Programs\Python\Python314\python.exe`
- **GitHub:** github.com/tylerbwalker56-netizen/bmo-face
- **Project folder (PC):** `C:\Users\tyler\Desktop\bmo-face-main\`

---

## ❓ Troubleshooting
- **"No module named X"** → Install it: `python.exe -m pip install X`
- **API key error** → Check `pip_brain_config.json` exists in the bmo-face folder
- **Pi won't boot (blinking pattern)** → Re-flash SD card, try bootloader update
- **Display black** → Try other DISP port, flip ribbon cable
- **Need help** → Come talk to me! I'm always here 🫧
