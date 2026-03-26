#!/usr/bin/env python3
"""
Pip Main — the complete BMO robot brain.
Ties together: face + brain + voice + touch + sleep + personality + news + Pokémon
"""

import os
import sys
import time
import json
import signal
import threading

from face_client import set_expression, talk, stop_talk, get_status as face_status
from pip_brain import PipBrain
from pip_touch import PipTouch
from pip_sleep import PipSleep

try:
    from pip_voice import PipVoiceSystem
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

try:
    from pokemon.pokemon_runner import PokemonRunner
    POKEMON_AVAILABLE = True
except ImportError:
    POKEMON_AVAILABLE = False


class Pip:
    """The complete Pip system — the soul of the robot."""

    def __init__(self):
        self.running = False

        # Core systems
        self.brain = PipBrain()
        self.brain.set_expression_callback(self._on_expression)
        self.touch = PipTouch()
        self.sleep_mgr = PipSleep()

        # Voice
        self.voice_system = None
        if VOICE_AVAILABLE:
            self.voice_system = PipVoiceSystem(brain=self.brain)
            self.voice_system.set_expression_callback(self._on_expression)

        # Pokémon
        self.pokemon = None
        if POKEMON_AVAILABLE:
            self.pokemon = PokemonRunner()

        # State
        self.human_present = True
        self.current_expression = "idle"

        # Wire up sleep callbacks
        self.sleep_mgr.on_sleep(self._on_sleep)
        self.sleep_mgr.on_wake(self._on_wake)

    def _on_expression(self, expression):
        if expression != self.current_expression:
            set_expression(expression)
            self.current_expression = expression

    def _on_sleep(self, reason):
        """Called when Pip goes to sleep."""
        self._on_expression("sleepy")
        if self.pokemon and self.pokemon.mode == "game":
            self.pokemon.stop_game()
        if self.voice_system:
            msg = "Getting sleepy..." if reason == "fatigue" else "Need to cool down..."
            self.voice_system.say(msg)

    def _on_wake(self):
        """Called when Pip wakes up."""
        self._on_expression("happy")
        if self.voice_system:
            self.voice_system.say("I'm back! Had a nice rest.")
        time.sleep(2)
        self._on_expression("idle")
        # Resume Pokémon if human isn't around
        if not self.human_present and self.pokemon:
            self.pokemon.switch_to_game()

    def start(self):
        self.running = True
        print("🫧" + "=" * 40)
        print("🫧  PIP is booting up!")
        print("🫧" + "=" * 40)

        self._on_expression("happy")
        time.sleep(2)

        if self.voice_system:
            print("🎤 Voice system: starting...")
            self.voice_system.start()
            self.voice_system.say("Hey! I'm Pip. Good to see you!")
        else:
            print("🎤 Voice system: not available")

        if self.pokemon:
            print("🎮 Pokémon system: ready")

        # Start sleep monitor
        self.sleep_mgr.start_monitoring()
        print("😴 Sleep monitor: active")

        # Fetch news in background
        threading.Thread(target=self._fetch_news_bg, daemon=True).start()

        status = self.brain.get_status()
        print(f"🧠 Brain: {status['brain_mode']}")
        print(f"   Personality maturity: {status['personality']['maturity']}")
        print(f"   Memories: {status['memories']}")

        time.sleep(1)
        self._on_expression("idle")
        print("\n🫧 Pip is ready!\n")

    def _fetch_news_bg(self):
        try:
            self.brain.interests.fetch_news()
            self.brain.interests.prepare_conversation_topics(ai_client=self.brain.client)
        except:
            pass

    def stop(self):
        self.running = False
        print("\n🫧 Pip is going to sleep...")
        self._on_expression("sleepy")
        if self.voice_system:
            self.voice_system.say("Goodnight!")
            self.voice_system.stop()
        if self.pokemon:
            self.pokemon.stop()
        self.sleep_mgr.stop_monitoring()
        time.sleep(2)
        print("🫧 Zzz...")

    def on_touch(self, event_type, x, y):
        """Handle touch events from the face display."""
        if self.sleep_mgr.is_sleeping:
            if self.sleep_mgr.force_wake():
                return "Oh! I'm awake!"
            return self.sleep_mgr.get_sleep_response()

        if event_type == "down":
            self.touch.on_down(x, y)
        elif event_type == "up":
            self.touch.on_up(x, y)
        elif event_type == "move":
            self.touch.on_move(x, y)
        return None

    def update_touch(self, dt):
        """Call each frame to process touch reactions."""
        reaction = self.touch.update(dt)
        if reaction:
            self._on_expression(reaction["expression"])
            if reaction.get("response") and self.voice_system:
                self.voice_system.say(reaction["response"])
            return reaction
        return None

    def on_human_detected(self, present):
        if present and not self.human_present:
            self.human_present = True
            self._on_expression("happy")
            if self.pokemon and self.pokemon.mode == "game":
                self.pokemon.switch_to_face()
            if self.voice_system:
                self.voice_system.say("Hey Brooks! Welcome back!")
            time.sleep(2)
            self._on_expression("idle")
        elif not present and self.human_present:
            self.human_present = False
            time.sleep(30)
            if not self.human_present and self.pokemon:
                self.pokemon.switch_to_game()

    def chat(self, message):
        if self.sleep_mgr.is_sleeping:
            if self.sleep_mgr.force_wake():
                return "Oh! You woke me up! What's up?"
            return self.sleep_mgr.get_sleep_response()

        reply, expression = self.brain.think(message)
        clean = self.brain.clean_response(reply)

        # Syllable-synced talking
        try:
            talk(clean)
        except:
            pass

        return clean

    def say(self, text):
        try:
            talk(text)
        except:
            pass
        if self.voice_system:
            self.voice_system.say(text)
        else:
            print(f"🫧 Pip: {text}")
        try:
            stop_talk()
        except:
            pass


def main():
    pip = Pip()

    def signal_handler(sig, frame):
        pip.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    pip.start()

    print("Commands:")
    print("  Type anything to chat with Pip")
    print("  /say <text>       — Make Pip speak")
    print("  /expression <x>   — Change face")
    print("  /game             — Switch to Pokémon")
    print("  /face             — Switch to face")
    print("  /sleep            — Manual sleep")
    print("  /wake             — Force wake")
    print("  /news             — Show prepared topics")
    print("  /interests        — Show tracked interests")
    print("  /personality      — Show personality stats")
    print("  /status           — Show system status")
    print("  /quit             — Shut down")
    print()

    while pip.running:
        try:
            user_input = input("Brooks: ").strip()
            if not user_input:
                continue

            if user_input == "/quit":
                break
            elif user_input.startswith("/say "):
                pip.say(user_input[5:])
            elif user_input.startswith("/expression "):
                pip._on_expression(user_input[12:].strip())
            elif user_input == "/game" and pip.pokemon:
                pip.pokemon.switch_to_game()
            elif user_input == "/face" and pip.pokemon:
                pip.pokemon.switch_to_face()
            elif user_input == "/sleep":
                pip.sleep_mgr.go_to_sleep("manual", "Taking a nap!", 120)
            elif user_input == "/wake":
                pip.sleep_mgr.force_wake()
            elif user_input == "/news":
                topics = pip.brain.get_news_topics()
                for t in topics[:5]:
                    print(f"  [{t['category']}] {t['starter']}")
                if not topics:
                    print("  No topics yet — still fetching!")
            elif user_input == "/interests":
                print(pip.brain.interests.get_interests_summary())
            elif user_input == "/personality":
                for k, v in pip.brain.personality.get_status().items():
                    print(f"  {k}: {v}")
            elif user_input == "/status":
                status = pip.brain.get_status()
                for k, v in status.items():
                    print(f"  {k}: {v}")
                sleep_status = pip.sleep_mgr.get_status()
                for k, v in sleep_status.items():
                    print(f"  {k}: {v}")
            else:
                reply = pip.chat(user_input)
                print(f"Pip: {reply}\n")

        except (EOFError, KeyboardInterrupt):
            break

    pip.stop()


if __name__ == "__main__":
    main()
