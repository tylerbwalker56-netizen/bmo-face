#!/usr/bin/env python3
"""
Pip Pi — Optimized for Raspberry Pi 5 + 5" DSI touchscreen.
All-in-one: Face + Chat + Voice + Touch input.
Touch top-left corner to toggle game/chat mode.
Touch center to interact. Touch top-right to cycle moods.
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load API key
API_KEY = ""
_config_path = os.path.join(SCRIPT_DIR, "pip_brain_config.json")
if os.path.exists(_config_path):
    try:
        with open(_config_path) as _f:
            API_KEY = json.load(_f).get("api_key", "")
    except:
        pass

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

HAS_PIPER = False
PIPER_PATH = "/usr/bin/piper"
PIPER_MODEL = os.path.join(SCRIPT_DIR, "voices", "en_US-lessac-medium.onnx")
if os.path.isfile(PIPER_PATH) and os.path.isfile(PIPER_MODEL):
    HAS_PIPER = True

CHATGPT_MODEL = "gpt-4o-mini"
PIP_VOICE = "nova"
PIP_VOICE_SPEED = 0.95

WIDTH, HEIGHT = 800, 480
FPS = 20
MEMORY_FILE = os.path.join(SCRIPT_DIR, "pip_memory.json")

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
You're running on a Raspberry Pi 5 inside a BMO-style robot body!

You can control your face with these expressions:
idle, happy, talking, surprised, love, sad, angry, sleepy, confused, wink, excited
Include face commands like [FACE:happy] in responses.

When Brooks tells you to remember something, respond with [MEMORY:fact].
When you make a mistake and Brooks corrects you, respond with [LESSON:what you learned]."""

BG_COLOR = (0, 210, 200)
BG_SAD = (120, 170, 200)
BG_ANGRY = (200, 100, 100)
BG_SLEEPY = (100, 180, 170)
BG_LOVE = (220, 170, 190)
BLACK = (15, 25, 20)
WHITE = (240, 250, 245)
BLUSH = (220, 130, 150)
HEART = (230, 70, 100)
ONLINE_COLOR = (50, 200, 50)
OFFLINE_COLOR = (200, 100, 50)
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
    lines = [f"Current time: {time.strftime('%A, %B %d, %Y at %I:%M %p')}"]
    if is_online:
        w = get_weather()
        if w:
            lines.append(f"Weather in Simpsonville SC: {w}")
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            lines.append(f"CPU temp: {int(f.read().strip()) / 1000:.1f}C")
    except:
        pass
    return "\n".join(lines)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"facts": [], "lessons": [], "conversations": 0}

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
        lines.append("Lessons I've learned:")
        for lesson in mem["lessons"][-10:]:
            lines.append(f"- {lesson}")
    lines.append(f"We've had {mem.get('conversations', 0)} conversations total.")
    return "\n".join(lines)

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except:
        return 0.0


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
        if not self.is_blinking: return 1.0
        return 1.0 - self.blink_progress if self.blink_progress < 1.0 else self.blink_progress - 1.0

    def draw(self, mood, subtitle="", is_online=True, brain_mode="", mode_label=""):
        self.screen.fill(get_bg(mood))
        bob = int(math.sin(self.bob_phase) * 3)
        cx, cy = WIDTH // 2, HEIGHT // 2 - 30 + bob
        lx, rx = cx - 70, cx + 70
        ey, my = cy - 30, cy + 55
        self._draw_brows(lx, rx, ey, mood)
        self._draw_eyes(lx, rx, ey, mood)
        self._draw_cheeks(cx, cy, mood)
        self._draw_mouth(cx, my, mood)
        self._draw_extras(cx, cy, mood)
        pygame.draw.circle(self.screen, ONLINE_COLOR if is_online else OFFLINE_COLOR, (WIDTH - 20, 15), 6)
        if mode_label:
            s = pygame.font.SysFont("monospace", 12).render(mode_label, True, (40, 60, 50))
            self.screen.blit(s, (10, 8))
        if subtitle:
            f = pygame.font.SysFont("monospace", 16, bold=True)
            words = subtitle.split()
            lines, cur = [], ""
            for w in words:
                t = cur + " " + w if cur else w
                if f.size(t)[0] < WIDTH - 40: cur = t
                else: lines.append(cur); cur = w
            if cur: lines.append(cur)
            for i, line in enumerate(lines[-3:]):
                s = f.render(line, True, BLACK)
                self.screen.blit(s, s.get_rect(center=(cx, HEIGHT - 60 + i * 20)))

    def _draw_eyes(self, lx, rx, ey, mood):
        blink = self.get_blink()
        if mood in ("idle", "talking", "confused", "excited"):
            ew, eh = 30, int(34 * blink)
            if eh > 2:
                pygame.draw.ellipse(self.screen, BLACK, (lx-ew, ey-eh, ew*2, eh*2))
                pygame.draw.ellipse(self.screen, BLACK, (rx-ew, ey-eh, ew*2, eh*2))
                if eh > 10:
                    pygame.draw.circle(self.screen, WHITE, (lx+8, ey-8), 7)
                    pygame.draw.circle(self.screen, WHITE, (rx+8, ey-8), 7)
            else:
                pygame.draw.line(self.screen, BLACK, (lx-28, ey), (lx+28, ey), 4)
                pygame.draw.line(self.screen, BLACK, (rx-28, ey), (rx+28, ey), 4)
        elif mood == "happy":
            pygame.draw.arc(self.screen, BLACK, (lx-26, ey-14, 52, 28), 0.3, math.pi-0.3, 6)
            pygame.draw.arc(self.screen, BLACK, (rx-26, ey-14, 52, 28), 0.3, math.pi-0.3, 6)
        elif mood == "sad":
            pygame.draw.ellipse(self.screen, BLACK, (lx-22, ey-10, 44, 24))
            pygame.draw.ellipse(self.screen, BLACK, (rx-22, ey-10, 44, 24))
            pygame.draw.line(self.screen, BLACK, (lx-28, ey-26), (lx+16, ey-36), 4)
            pygame.draw.line(self.screen, BLACK, (rx-16, ey-36), (rx+28, ey-26), 4)
        elif mood == "angry":
            pygame.draw.ellipse(self.screen, BLACK, (lx-22, ey-12, 44, 28))
            pygame.draw.ellipse(self.screen, BLACK, (rx-22, ey-12, 44, 28))
        elif mood == "sleepy":
            pygame.draw.line(self.screen, BLACK, (lx-26, ey+4), (lx+26, ey+4), 5)
            pygame.draw.line(self.screen, BLACK, (rx-26, ey+4), (rx+26, ey+4), 5)
        elif mood == "surprised":
            pygame.draw.ellipse(self.screen, BLACK, (lx-32, ey-36, 64, 68), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx-32, ey-36, 64, 68), 5)
            pygame.draw.circle(self.screen, WHITE, (lx+10, ey-10), 10)
            pygame.draw.circle(self.screen, WHITE, (rx+10, ey-10), 10)
        elif mood == "wink":
            pygame.draw.line(self.screen, BLACK, (lx-26, ey), (lx+26, ey), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx-28, ey-30, 56, 56))
            pygame.draw.circle(self.screen, WHITE, (rx+8, ey-8), 7)
        elif mood == "love":
            for cx2 in (lx, rx):
                pygame.draw.circle(self.screen, HEART, (cx2-7, ey-6), 9)
                pygame.draw.circle(self.screen, HEART, (cx2+7, ey-6), 9)
                pygame.draw.polygon(self.screen, HEART, [(cx2-16, ey+2), (cx2+16, ey+2), (cx2, ey+22)])

    def _draw_brows(self, lx, rx, ey, mood):
        if mood == "angry":
            pygame.draw.line(self.screen, BLACK, (lx-32, ey-36), (lx+16, ey-20), 7)
            pygame.draw.line(self.screen, BLACK, (rx-16, ey-20), (rx+32, ey-36), 7)
        elif mood == "confused":
            pygame.draw.line(self.screen, BLACK, (lx-26, ey-38), (lx+20, ey-44), 4)
            pygame.draw.line(self.screen, BLACK, (rx-20, ey-34), (rx+26, ey-34), 4)
        elif mood == "excited":
            pygame.draw.line(self.screen, BLACK, (lx-24, ey-40), (lx+24, ey-46), 4)
            pygame.draw.line(self.screen, BLACK, (rx-24, ey-46), (rx+24, ey-40), 4)

    def _draw_mouth(self, cx, my, mood):
        if mood == "idle":
            pygame.draw.arc(self.screen, BLACK, (cx-25, my-8, 50, 24), math.pi+0.4, 2*math.pi-0.4, 3)
        elif mood in ("happy", "wink", "excited"):
            pygame.draw.arc(self.screen, BLACK, (cx-50, my-16, 100, 46), math.pi+0.2, 2*math.pi-0.2, 5)
        elif mood == "talking":
            o = abs(math.sin(self.talk_phase))
            pygame.draw.ellipse(self.screen, BLACK, (cx-int(18+8*o), my-int((6+22*o)/2), int(18+8*o)*2, int(6+22*o)))
        elif mood == "sad":
            pygame.draw.arc(self.screen, BLACK, (cx-30, my+4, 60, 30), 0.4, math.pi-0.4, 4)
        elif mood == "angry":
            pygame.draw.line(self.screen, BLACK, (cx-30, my), (cx+30, my), 6)
        elif mood == "sleepy":
            pts = [(int(cx-20+i*40/19), int(my+math.sin(i*0.8+self.idle_timer*2)*4)) for i in range(20)]
            if len(pts) > 1: pygame.draw.lines(self.screen, BLACK, False, pts, 3)
        elif mood == "surprised":
            pygame.draw.ellipse(self.screen, BLACK, (cx-14, my-4, 28, 30), 4)
        elif mood == "confused":
            pts = [(int(cx-24+i*48/15), int(my+math.sin(i*1.2)*6)) for i in range(16)]
            pygame.draw.lines(self.screen, BLACK, False, pts, 4)
        elif mood == "love":
            pygame.draw.arc(self.screen, BLACK, (cx-35, my-10, 70, 36), math.pi+0.3, 2*math.pi-0.3, 4)

    def _draw_cheeks(self, cx, cy, mood):
        if mood in ("happy", "love", "wink", "excited"):
            pygame.draw.circle(self.screen, BLUSH, (cx-120, cy+10), 20)
            pygame.draw.circle(self.screen, BLUSH, (cx+120, cy+10), 20)

    def _draw_extras(self, cx, cy, mood):
        if mood == "sleepy":
            for i, c in enumerate("Zzz"):
                o = math.sin(self.zzz_phase + i*0.8) * 6
                f = pygame.font.SysFont("monospace", 28-i*4, bold=True)
                self.screen.blit(f.render(c, True, BLACK), (cx+110+i*20, int(cy-60-i*22+o)))
        elif mood == "confused":
            f = pygame.font.SysFont("monospace", 36, bold=True)
            self.screen.blit(f.render("?", True, BLACK), (cx+100, int(cy-80+math.sin(self.idle_timer*3)*5)))
        elif mood == "excited":
            f = pygame.font.SysFont("monospace", 30, bold=True)
            self.screen.blit(f.render("!!", True, BLACK), (cx+100, int(cy-70+math.sin(self.idle_timer*4)*4)))


class PipBrain:
    def __init__(self):
        self.history = []
        self.is_online = False
        self.brain_mode = "none"
        self.openai_client = None
        self.memory = load_memory()
        self._check()

    def _check(self):
        self.is_online = check_internet()
        if self.is_online and HAS_OPENAI and API_KEY:
            self.brain_mode = "ChatGPT"
            if not self.openai_client:
                self.openai_client = OpenAI(api_key=API_KEY)
        else:
            self.brain_mode = "none"

    def think(self, text):
        self._check()
        self.history.append({"role": "user", "content": text})
        if len(self.history) > 30: self.history = self.history[-30:]
        system = SYSTEM_PROMPT
        mp = get_memory_prompt(self.memory)
        if mp: system += f"\n\nYour persistent memory:\n{mp}"
        ctx = get_context(self.is_online)
        if ctx: system += f"\n\nCurrent info:\n{ctx}"
        msgs = [{"role": "system", "content": system}] + self.history
        try:
            if self.brain_mode == "ChatGPT":
                r = self.openai_client.chat.completions.create(model=CHATGPT_MODEL, messages=msgs, temperature=0.85, max_tokens=200)
                reply = r.choices[0].message.content.strip()
            else:
                reply = "My brain isn't connected! Need internet + API key. [FACE:sad]"
            self.history.append({"role": "assistant", "content": reply})
            for fact in re.findall(r'\[MEMORY:(.*?)\]', reply):
                if fact.strip() and fact.strip() not in self.memory["facts"]:
                    self.memory["facts"].append(fact.strip())
            for lesson in re.findall(r'\[LESSON:(.*?)\]', reply):
                if lesson.strip() and lesson.strip() not in self.memory["lessons"]:
                    self.memory["lessons"].append(lesson.strip())
            self.memory["conversations"] = self.memory.get("conversations", 0) + 1
            save_memory(self.memory)
            return reply
        except Exception as e:
            return f"Brain glitch: {e} [FACE:confused]"

    def parse_face(self, text):
        m = re.search(r'\[FACE:(\w+)\]', text)
        return m.group(1).lower() if m and m.group(1).lower() in MOODS else None

    def clean(self, text):
        text = re.sub(r'\s*\[FACE:\w+\]\s*', ' ', text)
        text = re.sub(r'\s*\[MEMORY:.*?\]\s*', ' ', text)
        text = re.sub(r'\s*\[LESSON:.*?\]\s*', ' ', text)
        return text.strip()

    def detect_mood(self, text):
        t = text.lower()
        if any(w in t for w in ["love", "aww"]): return "love"
        if any(w in t for w in ["haha", "lol"]): return "happy"
        if any(w in t for w in ["wow", "whoa"]): return "surprised"
        if any(w in t for w in ["sorry", "sad"]): return "sad"
        if any(w in t for w in ["great", "awesome"]): return "happy"
        return "idle"


class PipVoice:
    def __init__(self):
        self.speaking = False
        self.openai_client = None
        if HAS_OPENAI and API_KEY:
            try: self.openai_client = OpenAI(api_key=API_KEY)
            except: pass

    def speak(self, text, is_online=True):
        self.speaking = True
        try:
            if is_online and self.openai_client: self._openai(text)
            elif HAS_PIPER: self._piper(text)
            else: self._espeak(text)
        except:
            try: self._espeak(text)
            except: pass
        self.speaking = False

    def _openai(self, text):
        resp = self.openai_client.audio.speech.create(model="tts-1", voice=PIP_VOICE, input=text, speed=PIP_VOICE_SPEED)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False); p = tmp.name; tmp.close()
        try:
            resp.stream_to_file(p); pygame.mixer.music.load(p); pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): time.sleep(0.1)
        finally:
            pygame.mixer.music.unload()
            try: os.unlink(p)
            except: pass

    def _piper(self, text):
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); p = tmp.name; tmp.close()
        try:
            subprocess.run([PIPER_PATH, "--model", PIPER_MODEL, "--output_file", p], input=text.encode(), capture_output=True, timeout=10)
            pygame.mixer.music.load(p); pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): time.sleep(0.1)
        finally:
            pygame.mixer.music.unload()
            try: os.unlink(p)
            except: pass

    def _espeak(self, text):
        try: subprocess.run(["espeak", "-s", "160", text], capture_output=True, timeout=10)
        except: pass


def main():
    if not os.environ.get("DISPLAY"):
        os.environ["SDL_FBDEV"] = "/dev/fb0"
        os.environ["SDL_VIDEODRIVER"] = "fbcon"

    pygame.init()
    pygame.mixer.init()
    try: screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    except: screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pip")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    face = BMOFace(screen)
    brain = PipBrain()
    voice = PipVoice()

    mood = "happy"
    subtitle = "Hey! I'm Pip! Tap my face to interact!"
    is_speaking = False
    idle_timer = 0
    face_hold_timer = 0
    face_hold_mood = None
    thermal_check = 0
    lock = threading.Lock()

    def speak_worker(text, result_mood):
        nonlocal mood, is_speaking
        with lock: mood = "talking"
        voice.speak(text, is_online=brain.is_online)
        with lock: mood = result_mood; is_speaking = False

    is_speaking = True
    threading.Thread(target=speak_worker, args=("Hey! I'm Pip! Nice to see you!", "idle"), daemon=True).start()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        idle_timer += dt
        thermal_check += dt

        if face_hold_mood and face_hold_timer > 0:
            face_hold_timer -= dt
            if face_hold_timer <= 0: face_hold_mood = None

        if thermal_check > 30:
            thermal_check = 0
            if get_cpu_temp() > 78:
                mood = "sleepy"; subtitle = "Too hot... resting..."
                time.sleep(10); continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                if x < 120 and y < 80:
                    subtitle = "Mode toggle! (Coming soon)"
                elif x > WIDTH - 120 and y < 80:
                    m = random.choice([m for m in MOODS if m != "talking"])
                    face_hold_mood = m; face_hold_timer = 5.0
                    subtitle = f"Mood: {m}"
                elif WIDTH//2-100 < x < WIDTH//2+100 and HEIGHT//2-100 < y < HEIGHT//2+100:
                    face_hold_mood = "happy"; face_hold_timer = 3.0
                    subtitle = random.choice(["Hey!", "Hi Brooks!", "Boop!", "What's up?"])

        if not is_speaking and not face_hold_mood and idle_timer > 10:
            with lock: mood = "idle"

        with lock: current_mood = mood
        if face_hold_mood and not is_speaking: current_mood = face_hold_mood

        face.update(dt, current_mood)
        face.draw(current_mood, subtitle=subtitle, is_online=brain.is_online, brain_mode=brain.brain_mode, mode_label="TAP CORNERS")
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
