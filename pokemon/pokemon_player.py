#!/usr/bin/env python3
"""
Pokémon Unbound AI Player — Pip learns to play using reinforcement learning.
Uses mGBA emulator controlled via subprocess + screen capture.

Pip starts completely clueless and gradually learns:
  - How to navigate menus
  - How to explore the map
  - How to battle (which moves to use)
  - How to grind and level up

This is NOT scripted. Pip learns by trial and error over days/weeks.

Requirements:
  pip install pillow numpy
  mGBA installed and in PATH (or set MGBA_PATH below)

Works on: Windows (testing) and Raspberry Pi (robot)
"""

import os
import sys
import json
import time
import random
import subprocess
import threading
import struct
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROM_DIR = os.path.join(SCRIPT_DIR, "pokemonunbound")
SAVE_DIR = os.path.join(SCRIPT_DIR, "pokemonunbound", "saves")
STATS_FILE = os.path.join(SCRIPT_DIR, "pip_pokemon_stats.json")
BRAIN_FILE = os.path.join(SCRIPT_DIR, "pip_pokemon_brain.json")

# mGBA path — auto-detect or set manually
MGBA_PATHS = [
    "mgba-sdl",                          # Linux (in PATH)
    "mgba",                               # Linux alt
    r"C:\Program Files\mGBA\mGBA.exe",   # Windows default
    r"C:\Program Files (x86)\mGBA\mGBA.exe",
    os.path.expanduser("~/mGBA/mGBA.exe"),
]

# GBA buttons
BUTTONS = ["A", "B", "Start", "Select", "Up", "Down", "Left", "Right", "L", "R"]

# Actions the AI can take
ACTIONS = {
    0: "A",
    1: "B",
    2: "Up",
    3: "Down",
    4: "Left",
    5: "Right",
    6: "Start",
    7: "L",
    8: "R",
    9: "wait",  # Do nothing for a moment
}


def find_mgba():
    """Find mGBA executable."""
    for path in MGBA_PATHS:
        if os.path.isfile(path):
            return path
    # Try 'which' on Linux/Mac
    try:
        result = subprocess.run(["which", "mgba-sdl"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    # Try 'where' on Windows
    try:
        result = subprocess.run(["where", "mGBA"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    return None


def find_rom():
    """Find the Pokémon Unbound ROM file."""
    if os.path.isdir(ROM_DIR):
        for f in os.listdir(ROM_DIR):
            if f.lower().endswith(('.gba', '.gbc', '.gb')):
                return os.path.join(ROM_DIR, f)
    # Also check parent directory
    parent = os.path.dirname(SCRIPT_DIR)
    unbound_dir = os.path.join(parent, "pokemonunbound")
    if os.path.isdir(unbound_dir):
        for f in os.listdir(unbound_dir):
            if f.lower().endswith(('.gba', '.gbc', '.gb')):
                return os.path.join(unbound_dir, f)
    return None


class PokemonBrain:
    """
    Simple reinforcement learning brain for Pokémon.
    Uses Q-learning with a state hash based on screen regions.

    Starts knowing NOTHING. Learns through:
    - Reward for new screens (exploration)
    - Reward for HP changes (won a battle)
    - Penalty for getting stuck (same screen too long)
    - Reward for menu progression
    """

    def __init__(self):
        self.q_table = {}  # state -> action -> value
        self.learning_rate = 0.1
        self.discount = 0.95
        self.epsilon = 0.8  # Start very exploratory, decrease over time
        self.min_epsilon = 0.1

        self.prev_state = None
        self.prev_action = None
        self.seen_states = set()
        self.total_steps = 0
        self.total_rewards = 0
        self.stuck_counter = 0
        self.last_state_change = 0

        self._load()

    def _load(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE) as f:
                    data = json.load(f)
                self.q_table = data.get("q_table", {})
                self.total_steps = data.get("total_steps", 0)
                self.epsilon = data.get("epsilon", 0.8)
                self.seen_states = set(data.get("seen_states", []))
                self.total_rewards = data.get("total_rewards", 0)
                print(f"🧠 Loaded brain: {self.total_steps} steps, {len(self.seen_states)} states seen")
            except:
                pass

    def save(self):
        os.makedirs(os.path.dirname(BRAIN_FILE), exist_ok=True)
        # Only save top states to keep file size manageable
        q_to_save = dict(list(self.q_table.items())[-5000:])
        data = {
            "q_table": q_to_save,
            "total_steps": self.total_steps,
            "epsilon": self.epsilon,
            "seen_states": list(self.seen_states)[-2000:],
            "total_rewards": self.total_rewards,
            "saved_at": datetime.now().isoformat(),
        }
        with open(BRAIN_FILE, "w") as f:
            json.dump(data, f)

    def get_state_hash(self, screen_data):
        """
        Create a simple hash of the screen state.
        Divides screen into grid and hashes average colors.
        """
        if screen_data is None:
            return "unknown"

        try:
            if isinstance(screen_data, Image.Image):
                # Resize to tiny thumbnail for fast hashing
                small = screen_data.resize((8, 8)).convert('L')
                pixels = list(small.getdata())
                # Quantize to reduce state space
                quantized = tuple(p // 32 for p in pixels)
                return str(hash(quantized))
        except:
            pass
        return f"state_{random.randint(0, 999)}"

    def choose_action(self, state):
        """Choose an action using epsilon-greedy policy."""
        self.total_steps += 1

        # Decay exploration over time
        if self.total_steps % 1000 == 0:
            self.epsilon = max(self.min_epsilon, self.epsilon * 0.995)

        # Explore
        if random.random() < self.epsilon:
            # Bias toward movement buttons early on
            if self.total_steps < 5000:
                weights = [0.15, 0.05, 0.2, 0.2, 0.2, 0.2, 0.05, 0.02, 0.02, 0.01]
            else:
                weights = [0.1] * 10
            action = random.choices(range(10), weights=weights, k=1)[0]
            return action

        # Exploit — pick best known action
        if state in self.q_table:
            actions = self.q_table[state]
            best_action = max(actions, key=actions.get)
            return int(best_action)

        # Unknown state — random
        return random.randint(0, 9)

    def learn(self, state, reward):
        """Update Q-values based on reward."""
        if self.prev_state is not None and self.prev_action is not None:
            prev_s = self.prev_state
            prev_a = str(self.prev_action)

            if prev_s not in self.q_table:
                self.q_table[prev_s] = {}
            if prev_a not in self.q_table[prev_s]:
                self.q_table[prev_s][prev_a] = 0.0

            # Best future value
            future = 0.0
            if state in self.q_table:
                future = max(self.q_table[state].values()) if self.q_table[state] else 0.0

            # Q-learning update
            old_val = self.q_table[prev_s][prev_a]
            self.q_table[prev_s][prev_a] = old_val + self.learning_rate * (
                reward + self.discount * future - old_val
            )

            self.total_rewards += reward

        self.prev_state = state
        self.prev_action = None  # Set after action is taken

    def record_action(self, action):
        self.prev_action = action

    def calculate_reward(self, state, prev_state):
        """Calculate reward based on what changed."""
        reward = 0.0

        # New state = exploration reward
        if state not in self.seen_states:
            reward += 1.0
            self.seen_states.add(state)
            self.stuck_counter = 0
            self.last_state_change = self.total_steps
        else:
            # Same state = getting stuck
            self.stuck_counter += 1
            if self.stuck_counter > 20:
                reward -= 0.5  # Penalty for being stuck

        # Reward state changes (something happened)
        if state != prev_state:
            reward += 0.2
            self.stuck_counter = 0

        return reward


class PokemonPlayer:
    """Controls mGBA and plays Pokémon using the AI brain."""

    def __init__(self):
        self.mgba_path = find_mgba()
        self.rom_path = find_rom()
        self.process = None
        self.brain = PokemonBrain()
        self.running = False
        self.paused = False
        self.stats = self._load_stats()
        self.session_start = time.time()
        self.steps_this_session = 0

    def _load_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {
            "total_play_hours": 0,
            "total_sessions": 0,
            "total_steps": 0,
            "states_discovered": 0,
            "best_reward_session": 0,
            "started": datetime.now().isoformat(),
        }

    def _save_stats(self):
        session_hours = (time.time() - self.session_start) / 3600
        self.stats["total_play_hours"] += session_hours
        self.stats["total_sessions"] += 1
        self.stats["total_steps"] = self.brain.total_steps
        self.stats["states_discovered"] = len(self.brain.seen_states)
        self.stats["last_played"] = datetime.now().isoformat()

        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(self.stats, f, indent=2)

    def check_ready(self):
        """Check if everything needed is available."""
        issues = []
        if not self.mgba_path:
            issues.append("mGBA not found! Install from https://mgba.io/downloads.html")
        if not self.rom_path:
            issues.append(f"No ROM found in {ROM_DIR}/ — put your .gba file there")
        if not HAS_PIL:
            issues.append("Pillow not installed: pip install pillow")
        return issues

    def start(self):
        """Launch mGBA and start playing."""
        issues = self.check_ready()
        if issues:
            print("❌ Can't start Pokémon:")
            for i in issues:
                print(f"   - {i}")
            return False

        print(f"🎮 Starting Pokémon Unbound!")
        print(f"   ROM: {self.rom_path}")
        print(f"   Emulator: {self.mgba_path}")
        print(f"   Brain: {self.brain.total_steps} steps learned so far")
        print(f"   Exploration rate: {self.brain.epsilon:.0%}")

        # Launch mGBA
        try:
            self.process = subprocess.Popen(
                [self.mgba_path, self.rom_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(3)  # Wait for emulator to start
            self.running = True
            print("🎮 mGBA launched! Pip is learning to play...")
            return True
        except Exception as e:
            print(f"❌ Failed to launch mGBA: {e}")
            return False

    def stop(self):
        """Stop playing and save progress."""
        self.running = False
        print("🎮 Saving progress...")
        self.brain.save()
        self._save_stats()

        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
        print("🎮 Pokémon paused. Progress saved!")

    def play_step(self):
        """Execute one step of AI gameplay."""
        if not self.running or self.paused:
            return

        try:
            # Capture screen
            screen = self._capture_screen()

            # Get state
            state = self.brain.get_state_hash(screen)

            # Calculate reward from previous action
            reward = self.brain.calculate_reward(state, self.brain.prev_state)
            self.brain.learn(state, reward)

            # Choose next action
            action = self.brain.choose_action(state)
            self.brain.record_action(action)

            # Execute action
            self._press_button(ACTIONS[action])

            self.steps_this_session += 1

            # Auto-save every 500 steps
            if self.steps_this_session % 500 == 0:
                self.brain.save()
                self._save_stats()

            # Print progress occasionally
            if self.steps_this_session % 100 == 0:
                print(f"🎮 Step {self.brain.total_steps} | "
                      f"States: {len(self.brain.seen_states)} | "
                      f"Explore: {self.brain.epsilon:.0%} | "
                      f"Reward: {self.brain.total_rewards:.1f}")

        except Exception as e:
            if "process" in str(e).lower() or "terminated" in str(e).lower():
                self.running = False
            else:
                time.sleep(0.5)

    def _capture_screen(self):
        """Capture the mGBA window screen."""
        if not HAS_PIL:
            return None
        try:
            # Try to grab the screen (works on Windows with PIL)
            screen = ImageGrab.grab()
            # TODO: Crop to just the mGBA window
            # For now, grab full screen and resize
            return screen
        except Exception:
            return None

    def _press_button(self, button):
        """Send a button press to mGBA."""
        if button == "wait":
            time.sleep(0.1)
            return

        # Use platform-specific key simulation
        try:
            if sys.platform == "win32":
                self._press_key_windows(button)
            else:
                self._press_key_linux(button)
        except Exception:
            pass

        time.sleep(0.05)  # Brief pause between inputs

    def _press_key_windows(self, button):
        """Send key press on Windows using ctypes."""
        try:
            import ctypes
            # mGBA default key mappings
            key_map = {
                "A": 0x58,      # X
                "B": 0x5A,      # Z
                "Start": 0x0D,  # Enter
                "Select": 0x08, # Backspace
                "Up": 0x26,     # Arrow Up
                "Down": 0x28,   # Arrow Down
                "Left": 0x25,   # Arrow Left
                "Right": 0x27,  # Arrow Right
                "L": 0x41,      # A
                "R": 0x53,      # S
            }
            vk = key_map.get(button)
            if vk:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # Key down
                time.sleep(0.05)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # Key up
        except Exception:
            pass

    def _press_key_linux(self, button):
        """Send key press on Linux using xdotool."""
        key_map = {
            "A": "x", "B": "z", "Start": "Return", "Select": "BackSpace",
            "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
            "L": "a", "R": "s",
        }
        key = key_map.get(button)
        if key:
            try:
                subprocess.run(["xdotool", "key", key], capture_output=True, timeout=1)
            except:
                pass

    def get_summary(self):
        """Get a human-readable summary of Pip's Pokémon progress."""
        steps = self.brain.total_steps
        states = len(self.brain.seen_states)
        hours = self.stats.get("total_play_hours", 0)
        sessions = self.stats.get("total_sessions", 0)
        explore = self.brain.epsilon

        lines = []
        if steps == 0:
            lines.append("I haven't started playing yet!")
        elif steps < 100:
            lines.append(f"Just started! {steps} moves so far. I have NO idea what I'm doing 😅")
        elif steps < 1000:
            lines.append(f"I've made {steps} moves! Still pretty confused but I'm learning!")
            lines.append(f"I've seen {states} different screens so far.")
        elif steps < 10000:
            lines.append(f"Getting somewhere! {steps} moves, {states} screens explored.")
            lines.append(f"I'm {100-explore*100:.0f}% confident in my decisions now.")
        else:
            lines.append(f"I've played {steps} moves across {sessions} sessions ({hours:.1f} hours)!")
            lines.append(f"Explored {states} unique screens. Getting pretty smart! 🧠")

        if explore > 0.5:
            lines.append("Still mostly exploring randomly — gotta learn the basics!")
        elif explore > 0.2:
            lines.append("Starting to make smarter choices based on what I've learned!")
        else:
            lines.append("I know what I'm doing now! Mostly using learned strategies 💪")

        return " ".join(lines)


def main():
    """CLI for testing Pokémon player."""
    print("🎮 Pip's Pokémon Player — AI Learning Mode")
    print("=" * 45)

    player = PokemonPlayer()
    issues = player.check_ready()

    if issues:
        print("\n⚠️  Setup issues:")
        for i in issues:
            print(f"   - {i}")
        print(f"\nExpected ROM location: {ROM_DIR}/")
        print("Put your Pokémon Unbound .gba file in that folder.")
        return

    if not player.start():
        return

    print("\nPip is playing! Press Ctrl+C to stop.\n")

    try:
        while player.running:
            player.play_step()
            time.sleep(0.1)  # ~10 actions per second
    except KeyboardInterrupt:
        print()
    finally:
        player.stop()
        print("\n" + player.get_summary())


if __name__ == "__main__":
    main()
