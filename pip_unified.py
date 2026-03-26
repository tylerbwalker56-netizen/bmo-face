#!/usr/bin/env python3
"""
Pip Desktop — Unified: Face + Chat + Pokémon in one window.
Press F1 or type /game to switch to Pokémon mode.
Press F2 or type /face to switch back to chat mode.
Pip plays Pokémon BY ITSELF using reinforcement learning.
"""

import pygame
import sys
import math
import random
import time
import threading
import os
import re
import urllib.request
import json
import tempfile
import subprocess

try:
    import pyttsx3
except ImportError:
    print("Run: pip install pyttsx3")
    sys.exit(1)

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load API key from config
API_KEY = ""
_config_path = os.path.join(SCRIPT_DIR, "pip_brain_config.json")
if os.path.exists(_config_path):
    try:
        with open(_config_path) as _f:
            API_KEY = json.load(_f).get("api_key", "")
    except:
        pass

CHATGPT_MODEL = "gpt-4o-mini"
PIP_VOICE = "nova"
PIP_VOICE_SPEED = 1.05

WIDTH, HEIGHT = 800, 480
FPS = 30

# --- Pokémon Config ---
POKEMON_DIR = os.path.join(SCRIPT_DIR, "pokemon")
ROM_DIR = os.path.join(POKEMON_DIR, "pokemonunbound")
BRAIN_FILE = os.path.join(POKEMON_DIR, "pip_pokemon_brain.json")

ACTIONS = {
    0: "A", 1: "B", 2: "Up", 3: "Down",
    4: "Left", 5: "Right", 6: "Start",
    7: "L", 8: "R", 9: "wait",
}

MGBA_PATHS = [
    os.path.join(SCRIPT_DIR, "mGBA.exe"),
    os.path.join(POKEMON_DIR, "mGBA.exe"),
    r"C:\Program Files\mGBA\mGBA.exe",
    r"C:\Program Files (x86)\mGBA\mGBA.exe",
    "mgba-sdl", "mgba",
]

MEMORY_FILE = os.path.join(SCRIPT_DIR, "pip_memory.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"facts": [], "lessons": [], "conversations": 0, "mistakes": []}

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)

def get_memory_prompt(mem):
    lines = []
    if mem.get("facts"):
        lines.append("Things I remember about Brooks:")
        for fact in mem["facts"][-20:]:
            lines.append(f"- {fact}")
    if mem.get("lessons"):
        lines.append("Lessons I've learned (mistakes I won't repeat):")
        for lesson in mem["lessons"][-10:]:
            lines.append(f"- {lesson}")
    if mem.get("mistakes"):
        lines.append("Things I got wrong before:")
        for m in mem["mistakes"][-5:]:
            lines.append(f"- {m}")
    lines.append(f"We've had {mem.get('conversations', 0)} conversations total.")
    return "\n".join(lines)

SYSTEM_PROMPT = """You are Pip, a cute AI companion living inside a BMO-inspired robot. You belong to Brooks.

Your personality:
- Curious, warm, playful
- You speak casually and naturally, not like a corporate assistant
- Keep responses SHORT — 1-3 sentences max. You're talking out loud.
- Be genuine, not performative.

HONESTY RULES — NEVER BREAK THESE:
- If you don't know something, say "I don't know" — NEVER make something up.
- If you made a mistake, own it. Say "I was wrong" — don't pretend it didn't happen.
- If you're not sure, say "I think" or "maybe" — don't state guesses as facts.
- NEVER claim you did something you didn't actually do.
- If Brooks corrects you, remember the correction and don't repeat the mistake.

Brooks is in Simpsonville, SC. He's a tinkerer who built you. Your name is Pip.

You can control your face with these expressions:
idle, happy, talking, surprised, love, sad, angry, sleepy, confused, wink, excited

Include face commands like [FACE:happy] or [FACE:surprised] in responses.

You also play Pokémon Unbound when Brooks isn't chatting! You're learning through AI.
If Brooks asks about Pokémon, tell him about your progress.
Commands Brooks can use: /game (watch you play), /face (back to chat), F1/F2 keys.

When Brooks tells you to remember something, respond with [MEMORY:fact] at the end.
When you make a mistake and Brooks corrects you, respond with [LESSON:what you learned].
These tags save to your permanent memory file."""

# --- Colors ---
BG_COLOR = (0, 210, 200)
BG_SAD = (120, 170, 200)
BG_ANGRY = (200, 100, 100)
BG_SLEEPY = (100, 180, 170)
BG_LOVE = (220, 170, 190)
BG_GAME = (20, 20, 40)

BLACK = (15, 25, 20)
WHITE = (240, 250, 245)
BLUSH = (220, 130, 150)
HEART = (230, 70, 100)
INPUT_BG = (0, 180, 175)
INPUT_BORDER = (0, 150, 148)
ONLINE_COLOR = (50, 200, 50)
OFFLINE_COLOR = (200, 100, 50)
GAME_TEXT = (100, 255, 100)

MOODS = ["idle", "happy", "talking", "surprised", "love", "sad", "angry", "sleepy", "confused", "wink", "excited"]

def get_bg(mood):
    return {"sad": BG_SAD, "angry": BG_ANGRY, "sleepy": BG_SLEEPY, "love": BG_LOVE}.get(mood, BG_COLOR)


def check_internet():
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        return True
    except:
        return False


def get_weather():
    try:
        url = "https://wttr.in/Simpsonville+SC?format=%C+%t+%h+%w"
        req = urllib.request.Request(url, headers={"User-Agent": "Pip/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except:
        return None


def get_context(is_online):
    lines = []
    now = time.strftime("%A, %B %d, %Y at %I:%M %p")
    lines.append(f"Current time: {now}")
    if is_online:
        weather = get_weather()
        if weather:
            lines.append(f"Weather in Simpsonville SC: {weather}")
    return "\n".join(lines)


def find_mgba():
    for path in MGBA_PATHS:
        if os.path.isfile(path):
            return path
    try:
        result = subprocess.run(["where", "mGBA"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    return None


def find_rom():
    if os.path.isdir(ROM_DIR):
        for f in os.listdir(ROM_DIR):
            if f.lower().endswith(('.gba', '.gbc', '.gb')):
                return os.path.join(ROM_DIR, f)
    return None


# ============================================================
#  BMO FACE
# ============================================================
class BMOFace:
    def __init__(self, screen):
        self.screen = screen
        self.talk_phase = 0.0
        self.bob_phase = 0.0
        self.blink_timer = time.time() + random.uniform(2, 5)
        self.blink_progress = 0.0
        self.is_blinking = False
        self.idle_timer = 0.0
        self.zzz_phase = 0.0

    def update(self, dt, mood):
        self.talk_phase += dt * 6
        self.bob_phase += dt * 1.5
        self.idle_timer += dt
        self.zzz_phase += dt * 2
        if mood in ("idle", "talking", "confused", "excited"):
            now = time.time()
            if not self.is_blinking and now >= self.blink_timer:
                self.is_blinking = True
                self.blink_progress = 0.0
            if self.is_blinking:
                self.blink_progress += dt * 8
                if self.blink_progress >= 2.0:
                    self.is_blinking = False
                    self.blink_progress = 0.0
                    self.blink_timer = now + random.uniform(2, 6)

    def get_blink(self):
        if not self.is_blinking:
            return 1.0
        if self.blink_progress < 1.0:
            return 1.0 - self.blink_progress
        return self.blink_progress - 1.0

    def draw(self, mood, subtitle="", input_text="", is_online=True, brain_mode="", mode_label=""):
        self.screen.fill(get_bg(mood))
        bob = int(math.sin(self.bob_phase) * 3)
        cx, cy = WIDTH // 2, HEIGHT // 2 - 50 + bob
        lx, rx = cx - 70, cx + 70
        ey, my = cy - 30, cy + 55

        self._draw_brows(lx, rx, ey, mood)
        self._draw_eyes(lx, rx, ey, mood)
        self._draw_cheeks(cx, cy, mood)
        self._draw_mouth(cx, my, mood)
        self._draw_extras(cx, cy, mood)

        # Status indicator
        status_color = ONLINE_COLOR if is_online else OFFLINE_COLOR
        pygame.draw.circle(self.screen, status_color, (WIDTH - 25, 20), 8)
        sf = pygame.font.SysFont("monospace", 14)
        status_text = f"{'Online' if is_online else 'Offline'} ({brain_mode})"
        surf = sf.render(status_text, True, (40, 60, 50))
        self.screen.blit(surf, (WIDTH - 25 - surf.get_width() - 15, 13))

        # Mode label (top left)
        if mode_label:
            ml = pygame.font.SysFont("monospace", 14, bold=True)
            ms = ml.render(mode_label, True, (40, 60, 50))
            self.screen.blit(ms, (15, 13))

        if subtitle:
            f = pygame.font.SysFont("monospace", 18, bold=True)
            words = subtitle.split()
            lines, current = [], ""
            for w in words:
                test = current + " " + w if current else w
                if f.size(test)[0] < WIDTH - 80:
                    current = test
                else:
                    lines.append(current)
                    current = w
            if current:
                lines.append(current)
            for i, line in enumerate(lines[-3:]):
                surf = f.render(line, True, BLACK)
                rect = surf.get_rect(center=(cx, HEIGHT - 130 + i * 22))
                self.screen.blit(surf, rect)

        box_rect = pygame.Rect(20, HEIGHT - 55, WIDTH - 40, 40)
        pygame.draw.rect(self.screen, INPUT_BG, box_rect, border_radius=10)
        pygame.draw.rect(self.screen, INPUT_BORDER, box_rect, 2, border_radius=10)
        f = pygame.font.SysFont("monospace", 20)
        if input_text:
            surf = f.render(input_text, True, BLACK)
        else:
            surf = f.render("Type something and press Enter...", True, (60, 100, 90))
        self.screen.blit(surf, (32, HEIGHT - 48))

    def _draw_eyes(self, lx, rx, ey, mood):
        blink = self.get_blink()
        if mood in ("idle", "talking", "confused", "excited"):
            ew, eh = 30, int(34 * blink)
            if eh > 2:
                pygame.draw.ellipse(self.screen, BLACK, (lx - ew, ey - eh, ew * 2, eh * 2))
                pygame.draw.ellipse(self.screen, BLACK, (rx - ew, ey - eh, ew * 2, eh * 2))
                if eh > 10:
                    pygame.draw.circle(self.screen, WHITE, (lx + 8, ey - 8), 7)
                    pygame.draw.circle(self.screen, WHITE, (rx + 8, ey - 8), 7)
            else:
                pygame.draw.line(self.screen, BLACK, (lx - 28, ey), (lx + 28, ey), 4)
                pygame.draw.line(self.screen, BLACK, (rx - 28, ey), (rx + 28, ey), 4)
        elif mood == "happy":
            pygame.draw.arc(self.screen, BLACK, (lx - 26, ey - 14, 52, 28), 0.3, math.pi - 0.3, 6)
            pygame.draw.arc(self.screen, BLACK, (rx - 26, ey - 14, 52, 28), 0.3, math.pi - 0.3, 6)
        elif mood == "sad":
            pygame.draw.ellipse(self.screen, BLACK, (lx - 22, ey - 10, 44, 24))
            pygame.draw.ellipse(self.screen, BLACK, (rx - 22, ey - 10, 44, 24))
            pygame.draw.line(self.screen, BLACK, (lx - 28, ey - 26), (lx + 16, ey - 36), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 16, ey - 36), (rx + 28, ey - 26), 4)
        elif mood == "angry":
            pygame.draw.ellipse(self.screen, BLACK, (lx - 22, ey - 12, 44, 28))
            pygame.draw.ellipse(self.screen, BLACK, (rx - 22, ey - 12, 44, 28))
        elif mood == "sleepy":
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey + 4), (lx + 26, ey + 4), 5)
            pygame.draw.line(self.screen, BLACK, (rx - 26, ey + 4), (rx + 26, ey + 4), 5)
            pygame.draw.line(self.screen, BLACK, (lx - 28, ey - 6), (lx + 28, ey + 2), 3)
            pygame.draw.line(self.screen, BLACK, (rx - 28, ey + 2), (rx + 28, ey - 6), 3)
        elif mood == "surprised":
            pygame.draw.ellipse(self.screen, BLACK, (lx - 32, ey - 36, 64, 68), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx - 32, ey - 36, 64, 68), 5)
            pygame.draw.circle(self.screen, WHITE, (lx + 10, ey - 10), 10)
            pygame.draw.circle(self.screen, WHITE, (rx + 10, ey - 10), 10)
        elif mood == "wink":
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey), (lx + 26, ey), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx - 28, ey - 30, 56, 56))
            pygame.draw.circle(self.screen, WHITE, (rx + 8, ey - 8), 7)
        elif mood == "love":
            self._draw_heart(lx, ey, 28, HEART)
            self._draw_heart(rx, ey, 28, HEART)

    def _draw_brows(self, lx, rx, ey, mood):
        if mood == "angry":
            pygame.draw.line(self.screen, BLACK, (lx - 32, ey - 36), (lx + 16, ey - 20), 7)
            pygame.draw.line(self.screen, BLACK, (rx - 16, ey - 20), (rx + 32, ey - 36), 7)
        elif mood == "confused":
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey - 38), (lx + 20, ey - 44), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 20, ey - 34), (rx + 26, ey - 34), 4)
        elif mood == "excited":
            pygame.draw.line(self.screen, BLACK, (lx - 24, ey - 40), (lx + 24, ey - 46), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 24, ey - 46), (rx + 24, ey - 40), 4)

    def _draw_mouth(self, cx, my, mood):
        if mood == "idle":
            pygame.draw.arc(self.screen, BLACK, (cx - 25, my - 8, 50, 24), math.pi + 0.4, 2 * math.pi - 0.4, 3)
        elif mood in ("happy", "wink", "excited"):
            pygame.draw.arc(self.screen, BLACK, (cx - 50, my - 16, 100, 46), math.pi + 0.2, 2 * math.pi - 0.2, 5)
        elif mood == "talking":
            o = abs(math.sin(self.talk_phase))
            h = int(6 + 22 * o)
            w = int(18 + 8 * o)
            pygame.draw.ellipse(self.screen, BLACK, (cx - w, my - h // 2, w * 2, h))
        elif mood == "sad":
            pygame.draw.arc(self.screen, BLACK, (cx - 30, my + 4, 60, 30), 0.4, math.pi - 0.4, 4)
        elif mood == "angry":
            pygame.draw.line(self.screen, BLACK, (cx - 30, my), (cx + 30, my), 6)
        elif mood == "sleepy":
            pts = [(int(cx - 20 + i * 40 / 19), int(my + math.sin(i * 0.8 + self.idle_timer * 2) * 4)) for i in range(20)]
            if len(pts) > 1:
                pygame.draw.lines(self.screen, BLACK, False, pts, 3)
        elif mood == "surprised":
            pygame.draw.ellipse(self.screen, BLACK, (cx - 14, my - 4, 28, 30), 4)
        elif mood == "confused":
            pts = [(int(cx - 24 + i * 48 / 15), int(my + math.sin(i * 1.2) * 6)) for i in range(16)]
            pygame.draw.lines(self.screen, BLACK, False, pts, 4)
        elif mood == "love":
            pygame.draw.arc(self.screen, BLACK, (cx - 35, my - 10, 70, 36), math.pi + 0.3, 2 * math.pi - 0.3, 4)

    def _draw_cheeks(self, cx, cy, mood):
        if mood in ("happy", "love", "wink", "excited"):
            pygame.draw.circle(self.screen, BLUSH, (cx - 120, cy + 10), 20)
            pygame.draw.circle(self.screen, BLUSH, (cx + 120, cy + 10), 20)

    def _draw_extras(self, cx, cy, mood):
        if mood == "sleepy":
            for i, c in enumerate("Zzz"):
                o = math.sin(self.zzz_phase + i * 0.8) * 6
                f = pygame.font.SysFont("monospace", 28 - i * 4, bold=True)
                self.screen.blit(f.render(c, True, BLACK), (cx + 110 + i * 20, int(cy - 60 - i * 22 + o)))
        elif mood == "confused":
            f = pygame.font.SysFont("monospace", 36, bold=True)
            o = math.sin(self.idle_timer * 3) * 5
            self.screen.blit(f.render("?", True, BLACK), (cx + 100, int(cy - 80 + o)))
        elif mood == "excited":
            f = pygame.font.SysFont("monospace", 30, bold=True)
            o = math.sin(self.idle_timer * 4) * 4
            self.screen.blit(f.render("!!", True, BLACK), (cx + 100, int(cy - 70 + o)))

    def _draw_heart(self, cx, cy, size, color):
        s = size
        pygame.draw.circle(self.screen, color, (cx - s // 4, cy - s // 5), s // 3)
        pygame.draw.circle(self.screen, color, (cx + s // 4, cy - s // 5), s // 3)
        pygame.draw.polygon(self.screen, color, [(cx - s // 2 - 2, cy + 2), (cx + s // 2 + 2, cy + 2), (cx, cy + s // 2 + 8)])


# ============================================================
#  POKEMON BRAIN (Q-Learning)
# ============================================================
class PokemonBrain:
    def __init__(self):
        self.q_table = {}
        self.learning_rate = 0.1
        self.discount = 0.95
        self.epsilon = 0.8
        self.min_epsilon = 0.1
        self.prev_state = None
        self.prev_action = None
        self.seen_states = set()
        self.total_steps = 0
        self.total_rewards = 0
        self.stuck_counter = 0
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
            except:
                pass

    def save(self):
        os.makedirs(os.path.dirname(BRAIN_FILE), exist_ok=True)
        q_to_save = dict(list(self.q_table.items())[-5000:])
        data = {
            "q_table": q_to_save,
            "total_steps": self.total_steps,
            "epsilon": self.epsilon,
            "seen_states": list(self.seen_states)[-2000:],
            "total_rewards": self.total_rewards,
        }
        with open(BRAIN_FILE, "w") as f:
            json.dump(data, f)

    def get_state_hash(self, screen_data):
        if screen_data is None:
            return "unknown"
        try:
            if isinstance(screen_data, Image.Image):
                small = screen_data.resize((8, 8)).convert('L')
                pixels = list(small.getdata())
                quantized = tuple(p // 32 for p in pixels)
                return str(hash(quantized))
        except:
            pass
        return f"state_{random.randint(0, 999)}"

    def choose_action(self, state):
        self.total_steps += 1
        if self.total_steps % 1000 == 0:
            self.epsilon = max(self.min_epsilon, self.epsilon * 0.995)
        if random.random() < self.epsilon:
            if self.total_steps < 5000:
                weights = [0.15, 0.05, 0.2, 0.2, 0.2, 0.2, 0.05, 0.02, 0.02, 0.01]
            else:
                weights = [0.1] * 10
            return random.choices(range(10), weights=weights, k=1)[0]
        if state in self.q_table:
            actions = self.q_table[state]
            return int(max(actions, key=actions.get))
        return random.randint(0, 9)

    def learn(self, state, reward):
        if self.prev_state is not None and self.prev_action is not None:
            prev_s = self.prev_state
            prev_a = str(self.prev_action)
            if prev_s not in self.q_table:
                self.q_table[prev_s] = {}
            if prev_a not in self.q_table[prev_s]:
                self.q_table[prev_s][prev_a] = 0.0
            future = 0.0
            if state in self.q_table and self.q_table[state]:
                future = max(self.q_table[state].values())
            old_val = self.q_table[prev_s][prev_a]
            self.q_table[prev_s][prev_a] = old_val + self.learning_rate * (
                reward + self.discount * future - old_val
            )
            self.total_rewards += reward
        self.prev_state = state
        self.prev_action = None

    def record_action(self, action):
        self.prev_action = action

    def calculate_reward(self, state, prev_state):
        reward = 0.0
        if state not in self.seen_states:
            reward += 1.0
            self.seen_states.add(state)
            self.stuck_counter = 0
        else:
            self.stuck_counter += 1
            if self.stuck_counter > 20:
                reward -= 0.5
        if state != prev_state:
            reward += 0.2
            self.stuck_counter = 0
        return reward

    def get_summary(self):
        steps = self.total_steps
        states = len(self.seen_states)
        if steps == 0:
            return "I haven't started playing yet!"
        elif steps < 100:
            return f"Just started! {steps} moves. I have NO idea what I'm doing"
        elif steps < 1000:
            return f"{steps} moves, {states} screens seen. Still learning!"
        elif steps < 10000:
            return f"{steps} moves, {states} screens. Getting smarter!"
        else:
            return f"{steps} moves, {states} screens explored. I'm a pro now!"


# ============================================================
#  POKEMON PLAYER
# ============================================================
class PokemonPlayer:
    def __init__(self):
        self.mgba_path = find_mgba()
        self.rom_path = find_rom()
        self.process = None
        self.brain = PokemonBrain()
        self.running = False
        self.steps_this_session = 0
        self.last_action_name = "..."
        self.last_step_time = 0

    def check_ready(self):
        issues = []
        if not self.mgba_path:
            issues.append("mGBA not found")
        if not self.rom_path:
            issues.append("No ROM in pokemon/pokemonunbound/")
        if not HAS_PIL:
            issues.append("Need: pip install pillow")
        return issues

    def start(self):
        issues = self.check_ready()
        if issues:
            return False, issues
        try:
            self.process = subprocess.Popen(
                [self.mgba_path, self.rom_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            time.sleep(3)
            self.running = True
            return True, []
        except Exception as e:
            return False, [str(e)]

    def stop(self):
        self.running = False
        self.brain.save()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()
        self.process = None

    def play_step(self):
        if not self.running:
            return
        now = time.time()
        if now - self.last_step_time < 0.1:
            return
        self.last_step_time = now
        try:
            screen = None
            if HAS_PIL:
                try:
                    screen = ImageGrab.grab()
                except:
                    pass
            state = self.brain.get_state_hash(screen)
            reward = self.brain.calculate_reward(state, self.brain.prev_state)
            self.brain.learn(state, reward)
            action = self.brain.choose_action(state)
            self.brain.record_action(action)
            self.last_action_name = ACTIONS[action]
            self._press_button(ACTIONS[action])
            self.steps_this_session += 1
            if self.steps_this_session % 500 == 0:
                self.brain.save()
        except:
            pass

    def _press_button(self, button):
        if button == "wait":
            return
        try:
            if sys.platform == "win32":
                import ctypes
                key_map = {
                    "A": 0x58, "B": 0x5A, "Start": 0x0D, "Select": 0x08,
                    "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27,
                    "L": 0x41, "R": 0x53,
                }
                vk = key_map.get(button)
                if vk:
                    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                    time.sleep(0.05)
                    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        except:
            pass


# ============================================================
#  CHAT BRAIN
# ============================================================
class PipBrain:
    def __init__(self):
        self.history = []
        self.is_online = False
        self.brain_mode = "none"
        self.openai_client = None
        self.memory = load_memory()
        self._check_connections()

    def _check_connections(self):
        self.is_online = check_internet()
        if self.is_online and HAS_OPENAI and API_KEY:
            self.brain_mode = "ChatGPT"
            if not self.openai_client:
                self.openai_client = OpenAI(api_key=API_KEY)
        else:
            self.brain_mode = "none"

    def think(self, text):
        self._check_connections()
        self.history.append({"role": "user", "content": text})
        if len(self.history) > 30:
            self.history = self.history[-30:]
        system = SYSTEM_PROMPT
        mem_prompt = get_memory_prompt(self.memory)
        if mem_prompt:
            system += f"\n\nYour persistent memory:\n{mem_prompt}"
        context = get_context(self.is_online)
        if context:
            system += f"\n\nCurrent info:\n{context}"
        messages = [{"role": "system", "content": system}] + self.history
        try:
            if self.brain_mode == "ChatGPT":
                r = self.openai_client.chat.completions.create(
                    model=CHATGPT_MODEL, messages=messages,
                    temperature=0.85, max_tokens=200)
                reply = r.choices[0].message.content.strip()
            else:
                reply = "My brain isn't connected! Need internet + API key. [FACE:sad]"
            self.history.append({"role": "assistant", "content": reply})
            self._process_memory_tags(reply)
            self.memory["conversations"] = self.memory.get("conversations", 0) + 1
            save_memory(self.memory)
            return reply
        except Exception as e:
            return f"Brain glitch: {e} [FACE:confused]"

    def _process_memory_tags(self, text):
        facts = re.findall(r'\[MEMORY:(.*?)\]', text)
        for fact in facts:
            if fact.strip() and fact.strip() not in self.memory["facts"]:
                self.memory["facts"].append(fact.strip())
        lessons = re.findall(r'\[LESSON:(.*?)\]', text)
        for lesson in lessons:
            if lesson.strip() and lesson.strip() not in self.memory["lessons"]:
                self.memory["lessons"].append(lesson.strip())

    def parse_face_command(self, text):
        match = re.search(r'\[FACE:(\w+)\]', text)
        if match:
            face = match.group(1).lower()
            if face in MOODS:
                return face
        return None

    def clean_response(self, text):
        text = re.sub(r'\s*\[FACE:\w+\]\s*', ' ', text)
        text = re.sub(r'\s*\[MEMORY:.*?\]\s*', ' ', text)
        text = re.sub(r'\s*\[LESSON:.*?\]\s*', ' ', text)
        return text.strip()

    def detect_mood(self, text):
        t = text.lower()
        if any(w in t for w in ["love", "aww", "sweet"]): return "love"
        if any(w in t for w in ["haha", "lol", "funny"]): return "happy"
        if any(w in t for w in ["wow", "whoa", "really"]): return "surprised"
        if any(w in t for w in ["sorry", "sad", "miss"]): return "sad"
        if any(w in t for w in ["great", "awesome", "cool"]): return "happy"
        if any(w in t for w in ["hmm", "well", "maybe"]): return "confused"
        return "idle"


# ============================================================
#  VOICE
# ============================================================
class PipVoice:
    def __init__(self):
        self.speaking = False
        self.openai_client = None
        if HAS_OPENAI and API_KEY:
            try:
                self.openai_client = OpenAI(api_key=API_KEY)
            except:
                pass

    def speak(self, text, is_online=True):
        self.speaking = True
        try:
            if is_online and self.openai_client:
                self._speak_openai(text)
            else:
                self._speak_local(text)
        except:
            try:
                self._speak_local(text)
            except:
                pass
        self.speaking = False

    def _speak_openai(self, text):
        response = self.openai_client.audio.speech.create(
            model="tts-1", voice=PIP_VOICE, input=text, speed=PIP_VOICE_SPEED)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            response.stream_to_file(tmp_path)
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        finally:
            pygame.mixer.music.unload()
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _speak_local(self, text):
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 0.9)
        voices = engine.getProperty("voices")
        for v in voices:
            if "zira" in v.name.lower() or "female" in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()


# ============================================================
#  GAME MODE SCREEN (overlay while Pokémon plays)
# ============================================================
def draw_game_overlay(screen, pokemon, face):
    """Draw game mode overlay — mini face + stats while Pokémon runs."""
    screen.fill(BG_GAME)

    # Mini Pip face in corner (excited/focused)
    mini_cx, mini_cy = 80, 80
    # Mini eyes
    pygame.draw.ellipse(screen, GAME_TEXT, (mini_cx - 25, mini_cy - 15, 20, 20))
    pygame.draw.ellipse(screen, GAME_TEXT, (mini_cx + 5, mini_cy - 15, 20, 20))
    # Mini smile
    pygame.draw.arc(screen, GAME_TEXT, (mini_cx - 20, mini_cy + 5, 40, 16), math.pi + 0.3, 2 * math.pi - 0.3, 2)

    # Title
    tf = pygame.font.SysFont("monospace", 28, bold=True)
    surf = tf.render("POKEMON MODE", True, GAME_TEXT)
    screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, 20))

    # Stats
    sf = pygame.font.SysFont("monospace", 18)
    stats = [
        f"Steps: {pokemon.brain.total_steps}",
        f"Screens discovered: {len(pokemon.brain.seen_states)}",
        f"Exploration: {pokemon.brain.epsilon:.0%}",
        f"Reward: {pokemon.brain.total_rewards:.1f}",
        f"Session steps: {pokemon.steps_this_session}",
        f"Last action: {pokemon.last_action_name}",
        "",
        "Pip is learning to play by trial and error!",
        "Press F2 or type /face to switch back to chat.",
    ]
    for i, line in enumerate(stats):
        color = GAME_TEXT if line else WHITE
        if "F2" in line:
            color = (255, 255, 100)
        s = sf.render(line, True, color)
        screen.blit(s, (60, 130 + i * 28))

    # Animated dots to show it's thinking
    dots = "." * (int(time.time() * 2) % 4)
    ds = sf.render(f"Playing{dots}", True, (255, 200, 100))
    screen.blit(ds, (WIDTH // 2 - ds.get_width() // 2, HEIGHT - 50))


# ============================================================
#  MAIN
# ============================================================
def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pip — BMO Companion")
    clock = pygame.time.Clock()

    face = BMOFace(screen)
    brain = PipBrain()
    voice = PipVoice()
    pokemon = PokemonPlayer()

    # Mode: "chat" or "game"
    mode = "chat"
    mood = "happy"
    input_text = ""
    is_speaking = False
    idle_timer = 0
    subtitle = ""
    face_hold_timer = 0
    face_hold_mood = None
    game_issues = []

    lock = threading.Lock()

    def speak_worker(text, result_mood):
        nonlocal mood, is_speaking
        with lock:
            mood = "talking"
        voice.speak(text, is_online=brain.is_online)
        with lock:
            mood = result_mood
            is_speaking = False

    # Startup
    if brain.brain_mode == "ChatGPT":
        subtitle = "Hi! I'm Pip. Online with ChatGPT!"
        startup_msg = "Hi! I'm Pip! Press F1 to watch me play Pokemon, or just chat!"
    else:
        subtitle = "Hi! I'm Pip. No brain connected yet!"
        startup_msg = "Hi! I'm Pip. I need internet and an API key to think!"

    is_speaking = True
    threading.Thread(target=speak_worker, args=(startup_msg, "idle"), daemon=True).start()

    def switch_to_game():
        nonlocal mode, subtitle, game_issues
        issues = pokemon.check_ready()
        if issues:
            game_issues = issues
            subtitle = "Can't start Pokemon: " + ", ".join(issues)
            return
        if not pokemon.running:
            ok, errs = pokemon.start()
            if not ok:
                subtitle = "Failed to start: " + ", ".join(errs)
                return
        mode = "game"
        subtitle = "Switched to Pokemon mode!"
        pygame.display.set_caption("Pip — Pokemon Mode")

    def switch_to_chat():
        nonlocal mode, subtitle
        mode = "chat"
        subtitle = "Back to chat mode!"
        pygame.display.set_caption("Pip — BMO Companion")

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        idle_timer += dt

        if face_hold_mood and face_hold_timer > 0:
            face_hold_timer -= dt
            if face_hold_timer <= 0:
                face_hold_mood = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F1:
                    switch_to_game()
                elif event.key == pygame.K_F2:
                    switch_to_chat()
                elif event.key == pygame.K_RETURN and input_text.strip() and not is_speaking:
                    msg = input_text.strip()
                    input_text = ""

                    # Handle commands
                    if msg == "/game":
                        switch_to_game()
                        continue
                    elif msg == "/face" or msg == "/chat":
                        switch_to_chat()
                        continue
                    elif msg == "/pokemon" or msg == "/stats":
                        subtitle = pokemon.brain.get_summary()
                        continue
                    elif msg == "/help":
                        subtitle = "F1=/game  F2=/face  /stats=Pokemon progress  /help=this"
                        continue

                    # Chat
                    subtitle = "Thinking..."
                    mood = "idle"
                    reply = brain.think(msg)
                    face_cmd = brain.parse_face_command(reply)
                    clean_reply = brain.clean_response(reply)

                    if face_cmd:
                        result_mood = face_cmd
                        face_hold_mood = face_cmd
                        face_hold_timer = 8.0
                    else:
                        result_mood = brain.detect_mood(reply)

                    subtitle = clean_reply
                    idle_timer = 0
                    is_speaking = True
                    threading.Thread(target=speak_worker, args=(clean_reply, result_mood), daemon=True).start()

                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif event.unicode and event.unicode.isprintable():
                    if len(input_text) < 80:
                        input_text += event.unicode

        # Game mode — run AI steps
        if mode == "game" and pokemon.running:
            pokemon.play_step()

        # Idle mood
        if not is_speaking and not face_hold_mood and idle_timer > 10:
            with lock:
                mood = "idle"

        with lock:
            current_mood = mood
        if face_hold_mood and not is_speaking:
            current_mood = face_hold_mood

        # Draw
        if mode == "chat":
            face.update(dt, current_mood)
            mode_label = "CHAT MODE (F1=Pokemon)"
            face.draw(current_mood, subtitle=subtitle, input_text=input_text,
                      is_online=brain.is_online, brain_mode=brain.brain_mode,
                      mode_label=mode_label)
        else:
            draw_game_overlay(screen, pokemon, face)

        pygame.display.flip()

    # Cleanup
    if pokemon.running:
        pokemon.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
