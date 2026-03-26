#!/usr/bin/env python3
"""
Pokémon Runner — manages switching between Pip's face and the Pokémon game.

When Brooks is around (detected by camera), shows the face.
When Brooks is away, Pip plays Pokémon on the screen.
Pip can report on its game progress when asked.
"""

import os
import sys
import time
import json
import subprocess
import threading

# Add parent directory to path for face_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from face_client import set_expression, get_status

STATS_FILE = os.path.join(os.path.dirname(__file__), "pip_stats.json")


class PokemonRunner:
    """Manages the Pokémon game alongside the face display."""

    def __init__(self):
        self.mode = "face"  # "face" or "game"
        self.game_process = None
        self.human_present = False
        self.running = False
        self.last_switch = time.time()
        self.switch_cooldown = 5.0  # Seconds before switching again

    def start(self):
        """Start the runner."""
        self.running = True
        print("🫧 Pip Runner started")
        print("   Mode: face (default)")
        print("   Pip will switch to Pokémon when you leave!")

    def stop(self):
        """Stop everything cleanly."""
        self.running = False
        self.stop_game()
        set_expression("sleepy")
        print("🫧 Pip Runner stopped")

    def switch_to_game(self):
        """Switch display from face to Pokémon."""
        if self.mode == "game":
            return
        if time.time() - self.last_switch < self.switch_cooldown:
            return

        print("🎮 Switching to Pokémon...")
        set_expression("happy")
        time.sleep(1)

        # Stop the face display (the face systemd service)
        # subprocess.run(["sudo", "systemctl", "stop", "bmo-face"], capture_output=True)

        # Start Pokémon in play mode
        self.start_game()
        self.mode = "game"
        self.last_switch = time.time()

    def switch_to_face(self):
        """Switch display from Pokémon to face."""
        if self.mode == "face":
            return
        if time.time() - self.last_switch < self.switch_cooldown:
            return

        print("😊 Brooks detected! Switching to face...")
        self.stop_game()

        # Restart the face display
        # subprocess.run(["sudo", "systemctl", "start", "bmo-face"], capture_output=True)
        time.sleep(1)
        set_expression("happy")
        time.sleep(2)
        set_expression("idle")

        self.mode = "face"
        self.last_switch = time.time()

    def start_game(self):
        """Launch Pokémon in a subprocess."""
        pokemon_script = os.path.join(os.path.dirname(__file__), "pokemon_agent.py")
        self.game_process = subprocess.Popen(
            [sys.executable, pokemon_script, "play"],
            cwd=os.path.dirname(__file__)
        )
        print("🎮 Pokémon started!")

    def stop_game(self):
        """Stop the Pokémon subprocess."""
        if self.game_process and self.game_process.poll() is None:
            self.game_process.terminate()
            self.game_process.wait(timeout=5)
            print("🎮 Pokémon paused.")
        self.game_process = None

    def on_human_detected(self, present):
        """Called when camera detects (or loses) a human."""
        if present and not self.human_present:
            # Human just arrived
            self.human_present = True
            self.switch_to_face()
        elif not present and self.human_present:
            # Human just left — wait a bit before switching
            self.human_present = False
            time.sleep(30)  # Wait 30 seconds to make sure they're gone
            if not self.human_present:  # Still gone?
                self.switch_to_game()

    def get_game_summary(self):
        """Get a text summary of Pip's Pokémon progress for conversation."""
        if not os.path.exists(STATS_FILE):
            return "I haven't started playing Pokémon yet!"

        with open(STATS_FILE) as f:
            stats = json.load(f)

        hours = stats.get("training_hours", 0)
        badges = stats.get("badges_earned", 0)
        level = stats.get("max_level", 0)
        caught = stats.get("pokemon_caught", 0)
        maps = stats.get("maps_discovered", 0)

        lines = []
        if hours < 1:
            lines.append("I just started playing! Still figuring out the controls honestly 😅")
        elif badges == 0:
            lines.append(f"I've been playing for {hours:.1f} hours. No badges yet but I'm exploring!")
        else:
            lines.append(f"I've been playing for {hours:.1f} hours!")

        if badges > 0:
            lines.append(f"I've got {badges} badge{'s' if badges != 1 else ''}! 🏅")
        if level > 0:
            lines.append(f"My strongest Pokémon is level {level}.")
        if caught > 1:
            lines.append(f"I've caught {caught} different Pokémon so far!")
        if maps > 5:
            lines.append(f"Explored {maps} different areas.")

        # Fun commentary based on progress
        if badges >= 8:
            lines.append("I beat all the gyms! Time for the Elite Four! 🏆")
        elif level > 30:
            lines.append("Getting pretty strong! 💪")
        elif hours > 10 and badges == 0:
            lines.append("I'm... still working on it. This game is hard! 😤")

        return " ".join(lines)


def main():
    runner = PokemonRunner()

    try:
        runner.start()

        # For now, just run in game mode (no camera detection yet)
        print("\nCommands:")
        print("  'game'  — Switch to Pokémon")
        print("  'face'  — Switch to face")
        print("  'stats' — Show game progress")
        print("  'quit'  — Exit")
        print()

        while runner.running:
            try:
                cmd = input("> ").strip().lower()
                if cmd == "game":
                    runner.switch_to_game()
                elif cmd == "face":
                    runner.switch_to_face()
                elif cmd == "stats":
                    print(runner.get_game_summary())
                elif cmd in ("quit", "exit", "q"):
                    break
            except EOFError:
                break

    except KeyboardInterrupt:
        print()
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
