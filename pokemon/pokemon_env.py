#!/usr/bin/env python3
"""
Pokémon Red Gymnasium Environment for Reinforcement Learning.
Wraps PyBoy Game Boy emulator as an RL environment so Pip can learn to play.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces

try:
    from pyboy import PyBoy
except ImportError:
    print("PyBoy not installed. Run: pip3 install pyboy")
    raise


# Game Boy button mappings
ACTIONS = [
    "a",        # 0 - A button
    "b",        # 1 - B button
    "up",       # 2 - D-pad up
    "down",     # 3 - D-pad down
    "left",     # 4 - D-pad left
    "right",    # 5 - D-pad right
    "start",    # 6 - Start
    "select",   # 7 - Select
    "nothing",  # 8 - Do nothing (wait)
]

# Pokémon Red memory addresses
MEMORY_MAP = {
    # Player state
    "player_x":        0xD362,
    "player_y":        0xD361,
    "map_id":          0xD35E,

    # Party Pokémon
    "party_count":     0xD163,
    "party_hp_1":      0xD16C,  # Current HP of first Pokémon (2 bytes)
    "party_max_hp_1":  0xD18D,  # Max HP of first Pokémon (2 bytes)
    "party_level_1":   0xD18C,  # Level of first Pokémon

    # Experience
    "party_exp_1":     0xD179,  # Experience of first Pokémon (3 bytes)

    # Badges
    "badges":          0xD356,  # Bit flags for 8 badges

    # Battle state
    "in_battle":       0xD057,  # 0 = not in battle, 1 = wild, 2 = trainer
    "enemy_hp":        0xCFE6,  # Enemy current HP (2 bytes)

    # Items
    "money":           0xD347,  # Money (3 bytes, BCD)

    # Progress
    "pokedex_owned":   0xD2F7,  # Pokédex owned count

    # Event flags
    "event_flags":     0xD747,  # Various story progress flags

    # Menu/text state
    "text_progress":   0xC6AC,  # Text box progress indicator
}


class PokemonRedEnv(gym.Env):
    """
    Gymnasium environment for Pokémon Red.
    Pip observes the screen and game state, takes actions (button presses),
    and receives rewards for making progress.
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, rom_path="pokemon_red.gb", render_mode=None,
                 headless=True, emulation_speed=0, max_steps=20000):
        super().__init__()

        self.rom_path = rom_path
        self.render_mode = render_mode
        self.headless = headless
        self.emulation_speed = emulation_speed
        self.max_steps = max_steps
        self.current_step = 0

        # Action space: 9 possible buttons
        self.action_space = spaces.Discrete(len(ACTIONS))

        # Observation space: downscaled Game Boy screen (36x40x3 RGB)
        # Original is 160x144, we scale down to save memory/compute
        self.obs_width = 40
        self.obs_height = 36
        self.observation_space = spaces.Box(
            low=0, high=255,
            shape=(self.obs_height, self.obs_width, 3),
            dtype=np.uint8
        )

        # Game state tracking (for rewards)
        self.prev_state = {}
        self.visited_maps = set()
        self.visited_coords = set()
        self.total_rewards = 0.0
        self.episode_count = 0

        # PyBoy instance (created on reset)
        self.pyboy = None

    def _start_emulator(self):
        """Initialize or restart the PyBoy emulator."""
        if self.pyboy is not None:
            self.pyboy.stop()

        window = "null" if self.headless else "SDL2"
        self.pyboy = PyBoy(
            self.rom_path,
            window=window,
        )
        self.pyboy.set_emulation_speed(self.emulation_speed)

    def _read_memory(self, address):
        """Read a single byte from game memory."""
        return self.pyboy.memory[address]

    def _read_memory_16(self, address):
        """Read a 16-bit value (big-endian) from game memory."""
        high = self.pyboy.memory[address]
        low = self.pyboy.memory[address + 1]
        return (high << 8) | low

    def _read_memory_24(self, address):
        """Read a 24-bit value from game memory."""
        b1 = self.pyboy.memory[address]
        b2 = self.pyboy.memory[address + 1]
        b3 = self.pyboy.memory[address + 2]
        return (b1 << 16) | (b2 << 8) | b3

    def _get_game_state(self):
        """Read current game state from memory."""
        state = {
            "player_x": self._read_memory(MEMORY_MAP["player_x"]),
            "player_y": self._read_memory(MEMORY_MAP["player_y"]),
            "map_id": self._read_memory(MEMORY_MAP["map_id"]),
            "party_count": self._read_memory(MEMORY_MAP["party_count"]),
            "party_level": self._read_memory(MEMORY_MAP["party_level_1"]),
            "party_hp": self._read_memory_16(MEMORY_MAP["party_hp_1"]),
            "party_max_hp": self._read_memory_16(MEMORY_MAP["party_max_hp_1"]),
            "party_exp": self._read_memory_24(MEMORY_MAP["party_exp_1"]),
            "badges": bin(self._read_memory(MEMORY_MAP["badges"])).count("1"),
            "in_battle": self._read_memory(MEMORY_MAP["in_battle"]),
            "enemy_hp": self._read_memory_16(MEMORY_MAP["enemy_hp"]),
            "pokedex_owned": self._read_memory(MEMORY_MAP["pokedex_owned"]),
        }
        return state

    def _get_observation(self):
        """Get the current screen as a downscaled numpy array."""
        screen = self.pyboy.screen.ndarray  # 144x160x3
        # Simple downscale by slicing
        obs = screen[::4, ::4, :]  # 36x40x3
        return obs.astype(np.uint8)

    def reset(self, seed=None, options=None):
        """Reset the environment for a new episode."""
        super().reset(seed=seed)
        self._start_emulator()

        # Skip through intro/title screen
        # Press start a bunch of times to get past the opening
        for _ in range(500):
            self.pyboy.tick(1, False)

        # Initialize state tracking
        self.prev_state = self._get_game_state()
        self.visited_maps = {self.prev_state["map_id"]}
        self.visited_coords = {
            (self.prev_state["map_id"],
             self.prev_state["player_x"],
             self.prev_state["player_y"])
        }
        self.current_step = 0
        self.total_rewards = 0.0
        self.episode_count += 1

        obs = self._get_observation()
        info = {"state": self.prev_state}
        return obs, info

    def step(self, action):
        """Execute one action and return the result."""
        self.current_step += 1

        # Press the button
        action_name = ACTIONS[action]
        if action_name != "nothing":
            self.pyboy.button(action_name)

        # Advance emulation (several frames per action for responsiveness)
        for _ in range(24):  # ~24 frames per action
            self.pyboy.tick(1, False)

        # Read new state
        new_state = self._get_game_state()

        # Calculate reward
        reward = self._calculate_reward(self.prev_state, new_state)
        self.total_rewards += reward

        # Track exploration
        coord = (new_state["map_id"], new_state["player_x"], new_state["player_y"])
        self.visited_maps.add(new_state["map_id"])
        self.visited_coords.add(coord)

        # Check if episode is done
        terminated = False
        truncated = self.current_step >= self.max_steps

        # Update previous state
        self.prev_state = new_state

        obs = self._get_observation()
        info = {
            "state": new_state,
            "maps_visited": len(self.visited_maps),
            "tiles_visited": len(self.visited_coords),
            "total_rewards": self.total_rewards,
            "episode": self.episode_count,
        }

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, prev, curr):
        """Calculate reward based on game progress."""
        reward = 0.0

        # Exploration — visiting new places
        coord = (curr["map_id"], curr["player_x"], curr["player_y"])
        if coord not in self.visited_coords:
            reward += 0.1  # Small reward for new tiles

        if curr["map_id"] not in self.visited_maps:
            reward += 5.0  # Big reward for new maps

        # Leveling up
        level_diff = curr["party_level"] - prev["party_level"]
        if level_diff > 0:
            reward += level_diff * 10.0

        # Gaining experience
        exp_diff = curr["party_exp"] - prev["party_exp"]
        if exp_diff > 0:
            reward += exp_diff * 0.01

        # Catching Pokémon
        pokedex_diff = curr["pokedex_owned"] - prev["pokedex_owned"]
        if pokedex_diff > 0:
            reward += pokedex_diff * 20.0

        # Getting badges (HUGE reward)
        badge_diff = curr["badges"] - prev["badges"]
        if badge_diff > 0:
            reward += badge_diff * 100.0

        # Winning battles (enemy HP goes to 0)
        if prev["in_battle"] > 0 and curr["in_battle"] == 0:
            if prev["enemy_hp"] > 0:
                reward += 5.0  # Won the battle

        # Losing HP (small penalty)
        if curr["party_hp"] < prev["party_hp"]:
            hp_loss = prev["party_hp"] - curr["party_hp"]
            reward -= hp_loss * 0.01

        # Party wiped (bigger penalty)
        if curr["party_hp"] == 0 and prev["party_hp"] > 0:
            reward -= 10.0

        # Standing still penalty (encourage movement)
        if (curr["player_x"] == prev["player_x"] and
                curr["player_y"] == prev["player_y"] and
                curr["map_id"] == prev["map_id"] and
                curr["in_battle"] == 0):
            reward -= 0.01

        return reward

    def render(self):
        """Return the current screen for display."""
        if self.render_mode == "rgb_array":
            return self.pyboy.screen.ndarray
        return None

    def close(self):
        """Clean up."""
        if self.pyboy is not None:
            self.pyboy.stop()
            self.pyboy = None
