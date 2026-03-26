# Pip Plays Pokémon 🎮

Reinforcement learning AI that teaches Pip to play Pokémon Red on its own.

## How It Works
- PyBoy emulates Game Boy on the Pi
- A reinforcement learning agent (PPO) controls the buttons
- Pip gets rewards for progress (XP, badges, new areas, catches)
- Over time, Pip learns to play the game

## Requirements
```bash
pip3 install pyboy stable-baselines3 gymnasium numpy
```

## Files
| File | What It Does |
|------|-------------|
| `pokemon_env.py` | Gymnasium environment wrapping PyBoy |
| `pokemon_rewards.py` | Reward system — what Pip gets points for |
| `pokemon_agent.py` | RL agent training and playing |
| `pokemon_runner.py` | Main runner — manages game + face switching |

## ROM
You need a Pokémon Red ROM file (`pokemon_red.gb`). Place it in this folder.
*We can't distribute ROMs — you'll need to source your own legally.*

## Usage
```bash
# Train (Pip learns by playing)
python3 pokemon_agent.py train

# Play (watch Pip play with what it's learned)
python3 pokemon_agent.py play

# Full mode with face switching
python3 pokemon_runner.py
```
