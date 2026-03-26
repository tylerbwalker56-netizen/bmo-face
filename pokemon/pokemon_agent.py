#!/usr/bin/env python3
"""
Pokémon RL Agent — trains Pip to play Pokémon Red using PPO.

Usage:
    python3 pokemon_agent.py train     # Train the agent
    python3 pokemon_agent.py play      # Watch Pip play
    python3 pokemon_agent.py resume    # Resume training from checkpoint
"""

import os
import sys
import json
import time
from pathlib import Path

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.vec_env import DummyVecEnv
except ImportError:
    print("stable-baselines3 not installed. Run: pip3 install stable-baselines3")
    raise

from pokemon_env import PokemonRedEnv

# --- Configuration ---
ROM_PATH = os.path.join(os.path.dirname(__file__), "pokemon_red.gb")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
STATS_FILE = os.path.join(os.path.dirname(__file__), "pip_stats.json")


class PipProgressCallback(BaseCallback):
    """
    Tracks Pip's progress and saves stats so we can report
    on how the training is going.
    """

    def __init__(self, save_freq=10000, verbose=1):
        super().__init__(verbose)
        self.save_freq = save_freq
        self.best_reward = float("-inf")
        self.episode_rewards = []
        self.stats = {
            "total_timesteps": 0,
            "episodes_completed": 0,
            "best_reward": 0,
            "badges_earned": 0,
            "max_level": 0,
            "maps_discovered": 0,
            "pokemon_caught": 0,
            "training_hours": 0,
            "started_at": time.time(),
            "milestones": [],
        }
        self._load_stats()

    def _load_stats(self):
        """Load existing stats if available."""
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE) as f:
                    saved = json.load(f)
                    self.stats.update(saved)
            except Exception:
                pass

    def _save_stats(self):
        """Save current stats to file."""
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(self.stats, f, indent=2)

    def _on_step(self):
        self.stats["total_timesteps"] = self.num_timesteps

        # Update training hours
        elapsed = time.time() - self.stats["started_at"]
        self.stats["training_hours"] = round(elapsed / 3600, 2)

        # Check environment info
        if self.locals.get("infos"):
            for info in self.locals["infos"]:
                state = info.get("state", {})

                # Track progress
                badges = state.get("badges", 0)
                level = state.get("party_level", 0)
                maps = info.get("maps_visited", 0)
                pokedex = state.get("pokedex_owned", 0)

                if badges > self.stats["badges_earned"]:
                    self.stats["badges_earned"] = badges
                    self.stats["milestones"].append({
                        "type": "badge",
                        "value": badges,
                        "timestep": self.num_timesteps,
                        "time": time.time()
                    })
                    if self.verbose:
                        print(f"\n🏅 PIP GOT BADGE #{badges}! (step {self.num_timesteps})")

                if level > self.stats["max_level"]:
                    self.stats["max_level"] = level
                    if self.verbose and level % 5 == 0:
                        print(f"\n⬆️  Pip's Pokémon reached level {level}!")

                self.stats["maps_discovered"] = max(self.stats["maps_discovered"], maps)
                self.stats["pokemon_caught"] = max(self.stats["pokemon_caught"], pokedex)

        # Save checkpoint periodically
        if self.num_timesteps % self.save_freq == 0:
            self._save_checkpoint()
            self._save_stats()

        return True

    def _save_checkpoint(self):
        """Save model checkpoint."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"pip_pokemon_{self.num_timesteps}")
        self.model.save(path)
        # Also save as 'latest'
        latest_path = os.path.join(MODEL_DIR, "pip_pokemon_latest")
        self.model.save(latest_path)
        if self.verbose:
            print(f"\n💾 Saved checkpoint at step {self.num_timesteps}")


def make_env(headless=True):
    """Create the Pokémon environment."""
    def _init():
        return PokemonRedEnv(
            rom_path=ROM_PATH,
            headless=headless,
            emulation_speed=0,  # 0 = max speed for training
            max_steps=20000,
        )
    return _init


def train(resume=False):
    """Train Pip to play Pokémon."""
    print("🎮 Pip's Pokémon Training")
    print("=" * 40)

    if not os.path.exists(ROM_PATH):
        print(f"\n❌ ROM not found at: {ROM_PATH}")
        print("Place 'pokemon_red.gb' in the pokemon/ folder.")
        return

    # Create environment
    env = DummyVecEnv([make_env(headless=True)])

    # Create or load model
    latest_model = os.path.join(MODEL_DIR, "pip_pokemon_latest.zip")
    if resume and os.path.exists(latest_model):
        print("📂 Resuming from checkpoint...")
        model = PPO.load(latest_model, env=env)
    else:
        print("🆕 Starting fresh training...")
        model = PPO(
            "CnnPolicy",
            env,
            verbose=1,
            learning_rate=2.5e-4,
            n_steps=2048,
            batch_size=64,
            n_epochs=4,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            tensorboard_log=LOG_DIR,
        )

    # Create callback
    callback = PipProgressCallback(save_freq=10000)

    print("\n🧠 Training started! Pip is learning...")
    print("   This will take a while. Let it run!\n")

    try:
        model.learn(
            total_timesteps=1_000_000,  # Start with 1M steps
            callback=callback,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("\n⏸️  Training paused. Progress saved!")
    finally:
        # Final save
        os.makedirs(MODEL_DIR, exist_ok=True)
        model.save(os.path.join(MODEL_DIR, "pip_pokemon_latest"))
        callback._save_stats()
        env.close()

    print("\n✅ Training complete!")
    print(f"   Steps: {callback.stats['total_timesteps']}")
    print(f"   Badges: {callback.stats['badges_earned']}")
    print(f"   Max Level: {callback.stats['max_level']}")
    print(f"   Maps Found: {callback.stats['maps_discovered']}")


def play():
    """Watch Pip play Pokémon with its trained model."""
    print("🎮 Watching Pip play Pokémon!")
    print("=" * 40)

    latest_model = os.path.join(MODEL_DIR, "pip_pokemon_latest.zip")
    if not os.path.exists(latest_model):
        print("❌ No trained model found. Run training first:")
        print("   python3 pokemon_agent.py train")
        return

    if not os.path.exists(ROM_PATH):
        print(f"❌ ROM not found at: {ROM_PATH}")
        return

    # Load model
    env = PokemonRedEnv(
        rom_path=ROM_PATH,
        headless=False,  # Show the game!
        emulation_speed=1,  # Normal speed for watching
        max_steps=0,  # No limit
    )
    model = PPO.load(latest_model)

    print("🫧 Pip is playing! Watch the screen...")
    print("   Press Ctrl+C to stop.\n")

    obs, info = env.reset()
    try:
        while True:
            action, _ = model.predict(obs, deterministic=False)
            obs, reward, terminated, truncated, info = env.step(action)

            if terminated or truncated:
                obs, info = env.reset()

    except KeyboardInterrupt:
        print("\n👋 Stopped watching.")
    finally:
        env.close()


def show_stats():
    """Show Pip's training stats."""
    if not os.path.exists(STATS_FILE):
        print("No stats yet — train first!")
        return

    with open(STATS_FILE) as f:
        stats = json.load(f)

    print("🫧 Pip's Pokémon Progress")
    print("=" * 40)
    print(f"  Training time:   {stats.get('training_hours', 0):.1f} hours")
    print(f"  Total steps:     {stats.get('total_timesteps', 0):,}")
    print(f"  Badges earned:   {stats.get('badges_earned', 0)}/8")
    print(f"  Max level:       {stats.get('max_level', 0)}")
    print(f"  Pokémon caught:  {stats.get('pokemon_caught', 0)}")
    print(f"  Maps discovered: {stats.get('maps_discovered', 0)}")

    milestones = stats.get("milestones", [])
    if milestones:
        print(f"\n  Milestones:")
        for m in milestones[-10:]:  # Show last 10
            print(f"    🏅 {m['type']}: {m['value']} (step {m['timestep']:,})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pokemon_agent.py <command>")
        print("Commands:")
        print("  train   — Start training Pip")
        print("  resume  — Resume training from checkpoint")
        print("  play    — Watch Pip play")
        print("  stats   — Show Pip's progress")
        return

    command = sys.argv[1].lower()
    if command == "train":
        train(resume=False)
    elif command == "resume":
        train(resume=True)
    elif command == "play":
        play()
    elif command == "stats":
        show_stats()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
