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
import struct
import io

try:
    import pyttsx3
except ImportError:
    print("Run: pip install pyttsx3")
    sys.exit(1)

# Try to import OpenAI — not required if offline only
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Load API key from config file
API_KEY = ""
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pip_brain_config.json")
if os.path.exists(_config_path):
    try:
        with open(_config_path) as _f:
            API_KEY = json.load(_f).get("api_key", "")
    except:
        pass
CHATGPT_MODEL = "gpt-4o-mini"
OLLAMA_MODEL = "llama3.2"  # Change this to whatever model you download in Ollama
OLLAMA_URL = "http://localhost:11434"

# Voice settings — pick your favorite!
# Options: alloy, echo, fable, onyx, nova, shimmer
PIP_VOICE = "nova"  # Warm, friendly — perfect for Pip
PIP_VOICE_SPEED = 1.05  # Slightly faster than default for a peppy feel

WIDTH, HEIGHT = 800, 480
FPS = 30

SYSTEM_PROMPT = """You are Pip, a cute AI companion living inside a BMO-inspired robot. You belong to Brooks.

Your personality:
- Curious, warm, playful
- You speak casually and naturally, not like a corporate assistant
- Keep responses SHORT — 1-3 sentences max. You're talking out loud.
- Be genuine, not performative.

Brooks is in Simpsonville, SC. He's a tinkerer who built you. Your name is Pip.

IMPORTANT — You can control your face! You have these expressions:
idle, happy, talking, surprised, love, sad, angry, sleepy, confused, wink, excited

When Brooks asks you to make a face or show an emotion, include a face command in your response like this:
[FACE:angry] or [FACE:happy] or [FACE:surprised] etc.

Examples:
- "Show me your angry face" -> "Grr! How's this? [FACE:angry]"
- "Look happy" -> "Like this? [FACE:happy]"
- "Wink at me" -> "Hey there! [FACE:wink]"

You can also change your face to match your mood naturally. If you're excited about something, add [FACE:excited]. If something is sad, add [FACE:sad].

You also have access to current info that will be provided to you. Use it to answer questions about weather, time, etc."""

BG_COLOR = (0, 210, 200)
BG_SAD = (120, 170, 200)
BG_ANGRY = (200, 100, 100)
BG_SLEEPY = (100, 180, 170)
BG_LOVE = (220, 170, 190)

BLACK = (15, 25, 20)
WHITE = (240, 250, 245)
BLUSH = (220, 130, 150)
HEART = (230, 70, 100)
INPUT_BG = (0, 180, 175)
INPUT_BORDER = (0, 150, 148)
ONLINE_COLOR = (50, 200, 50)
OFFLINE_COLOR = (200, 100, 50)

MOODS = ["idle","happy","talking","surprised","love","sad","angry","sleepy","confused","wink","excited"]

def get_bg(mood):
    return {"sad":BG_SAD,"angry":BG_ANGRY,"sleepy":BG_SLEEPY,"love":BG_LOVE}.get(mood, BG_COLOR)

def check_internet():
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        return True
    except:
        return False

def check_ollama():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
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

def ollama_chat(messages):
    """Send a chat request to Ollama running locally."""
    try:
        data = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.85, "num_predict": 200}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"Offline brain error: {e}"


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
        if mood in ("idle","talking","confused","excited"):
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
        if self.blink_progress < 1.0: return 1.0 - self.blink_progress
        return self.blink_progress - 1.0

    def draw(self, mood, subtitle="", input_text="", is_online=True, brain_mode=""):
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

        # Status indicator (top right)
        status_color = ONLINE_COLOR if is_online else OFFLINE_COLOR
        pygame.draw.circle(self.screen, status_color, (WIDTH - 25, 20), 8)
        sf = pygame.font.SysFont("monospace", 14)
        status_text = f"{'Online' if is_online else 'Offline'} ({brain_mode})"
        surf = sf.render(status_text, True, (40, 60, 50))
        self.screen.blit(surf, (WIDTH - 25 - surf.get_width() - 15, 13))

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
            if current: lines.append(current)
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
        if mood in ("idle","talking","confused","excited"):
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
            pygame.draw.line(self.screen, BLACK, (lx-28, ey-6), (lx+28, ey+2), 3)
            pygame.draw.line(self.screen, BLACK, (rx-28, ey+2), (rx+28, ey-6), 3)
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
            self._draw_heart(lx, ey, 28, HEART)
            self._draw_heart(rx, ey, 28, HEART)

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
        elif mood in ("happy","wink","excited"):
            pygame.draw.arc(self.screen, BLACK, (cx-50, my-16, 100, 46), math.pi+0.2, 2*math.pi-0.2, 5)
        elif mood == "talking":
            o = abs(math.sin(self.talk_phase))
            h = int(6 + 22*o)
            w = int(18 + 8*o)
            pygame.draw.ellipse(self.screen, BLACK, (cx-w, my-h//2, w*2, h))
        elif mood == "sad":
            pygame.draw.arc(self.screen, BLACK, (cx-30, my+4, 60, 30), 0.4, math.pi-0.4, 4)
        elif mood == "angry":
            pygame.draw.line(self.screen, BLACK, (cx-30, my), (cx+30, my), 6)
        elif mood == "sleepy":
            pts = [(int(cx-20+i*40/19), int(my+math.sin(i*0.8+self.idle_timer*2)*4)) for i in range(20)]
            if len(pts)>1: pygame.draw.lines(self.screen, BLACK, False, pts, 3)
        elif mood == "surprised":
            pygame.draw.ellipse(self.screen, BLACK, (cx-14, my-4, 28, 30), 4)
        elif mood == "confused":
            pts = [(int(cx-24+i*48/15), int(my+math.sin(i*1.2)*6)) for i in range(16)]
            pygame.draw.lines(self.screen, BLACK, False, pts, 4)
        elif mood == "love":
            pygame.draw.arc(self.screen, BLACK, (cx-35, my-10, 70, 36), math.pi+0.3, 2*math.pi-0.3, 4)

    def _draw_cheeks(self, cx, cy, mood):
        if mood in ("happy","love","wink","excited"):
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
            o = math.sin(self.idle_timer*3) * 5
            self.screen.blit(f.render("?", True, BLACK), (cx+100, int(cy-80+o)))
        elif mood == "excited":
            f = pygame.font.SysFont("monospace", 30, bold=True)
            o = math.sin(self.idle_timer*4) * 4
            self.screen.blit(f.render("!!", True, BLACK), (cx+100, int(cy-70+o)))

    def _draw_heart(self, cx, cy, size, color):
        s = size
        pygame.draw.circle(self.screen, color, (cx-s//4, cy-s//5), s//3)
        pygame.draw.circle(self.screen, color, (cx+s//4, cy-s//5), s//3)
        pygame.draw.polygon(self.screen, color, [(cx-s//2-2,cy+2),(cx+s//2+2,cy+2),(cx,cy+s//2+8)])


class PipBrain:
    def __init__(self):
        self.history = []
        self.context = ""
        self.is_online = False
        self.has_ollama = False
        self.brain_mode = "none"
        self.openai_client = None

        # Check what's available
        self._check_connections()

    def _check_connections(self):
        """Check internet and Ollama availability."""
        self.is_online = check_internet()
        self.has_ollama = check_ollama()

        if self.is_online and HAS_OPENAI and API_KEY:
            self.brain_mode = "ChatGPT"
            if not self.openai_client:
                self.openai_client = OpenAI(api_key=API_KEY)
        elif self.has_ollama:
            self.brain_mode = "Ollama"
        else:
            self.brain_mode = "none"

        # Get context
        self.context = get_context(self.is_online)

    def think(self, text):
        # Recheck connections every message
        self._check_connections()

        self.history.append({"role": "user", "content": text})
        if len(self.history) > 20:
            self.history = self.history[-20:]

        system = SYSTEM_PROMPT
        if self.context:
            system += f"\n\nCurrent info:\n{self.context}"

        messages = [{"role": "system", "content": system}] + self.history

        try:
            if self.brain_mode == "ChatGPT":
                reply = self._think_chatgpt(messages)
            elif self.brain_mode == "Ollama":
                reply = self._think_ollama(messages)
            else:
                reply = "My brain isn't connected! I need either internet (ChatGPT) or Ollama running locally. [FACE:sad]"

            self.history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            # If ChatGPT fails, try Ollama as fallback
            if self.brain_mode == "ChatGPT" and self.has_ollama:
                try:
                    self.brain_mode = "Ollama"
                    reply = self._think_ollama(messages)
                    self.history.append({"role": "assistant", "content": reply})
                    return reply
                except:
                    pass
            return f"Brain glitch: {e} [FACE:confused]"

    def _think_chatgpt(self, messages):
        r = self.openai_client.chat.completions.create(
            model=CHATGPT_MODEL,
            messages=messages,
            temperature=0.85, max_tokens=200)
        return r.choices[0].message.content.strip()

    def _think_ollama(self, messages):
        return ollama_chat(messages)

    def parse_face_command(self, text):
        match = re.search(r'\[FACE:(\w+)\]', text)
        if match:
            face = match.group(1).lower()
            if face in MOODS:
                return face
        return None

    def clean_response(self, text):
        return re.sub(r'\s*\[FACE:\w+\]\s*', ' ', text).strip()

    def detect_mood(self, text):
        t = text.lower()
        if any(w in t for w in ["love","aww","sweet"]): return "love"
        if any(w in t for w in ["haha","lol","funny"]): return "happy"
        if any(w in t for w in ["wow","whoa","really","no way"]): return "surprised"
        if any(w in t for w in ["sorry","sad","miss"]): return "sad"
        if any(w in t for w in ["great","awesome","cool","excited","!"]): return "happy"
        if any(w in t for w in ["hmm","well","maybe","not sure"]): return "confused"
        return "idle"


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
        except Exception as e:
            # If OpenAI TTS fails, fall back to local
            try:
                self._speak_local(text)
            except:
                pass
        self.speaking = False

    def _speak_openai(self, text):
        """Natural voice using OpenAI TTS API — sounds like a real person."""
        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice=PIP_VOICE,
            input=text,
            speed=PIP_VOICE_SPEED,
        )
        # Save to temp file and play with pygame mixer
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            response.stream_to_file(tmp_path)
            # Use pygame mixer to play audio
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
        """Fallback robot voice using pyttsx3 — works offline."""
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


def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pip")
    clock = pygame.time.Clock()
    face = BMOFace(screen)
    brain = PipBrain()
    voice = PipVoice()

    mood = "happy"
    input_text = ""
    is_speaking = False
    idle_timer = 0
    reply_text = ""
    face_hold_timer = 0
    face_hold_mood = None

    # Startup message based on what's available
    if brain.brain_mode == "ChatGPT":
        subtitle = "Hi! I'm Pip. Online with ChatGPT!"
        startup_msg = "Hi! I'm Pip. I'm online with ChatGPT! Type something and press Enter!"
    elif brain.brain_mode == "Ollama":
        subtitle = "Hi! I'm Pip. Running offline with Ollama!"
        startup_msg = "Hi! I'm Pip. I'm running offline with Ollama! Type something and press Enter!"
    else:
        subtitle = "Hi! I'm Pip. No brain connected yet!"
        startup_msg = "Hi! I'm Pip. I need either internet or Ollama to think! Check my setup!"

    lock = threading.Lock()

    def speak_worker(text, result_mood):
        nonlocal mood, is_speaking
        with lock: mood = "talking"
        voice.speak(text, is_online=brain.is_online)
        with lock:
            mood = result_mood
            is_speaking = False

    is_speaking = True
    threading.Thread(target=speak_worker, args=(startup_msg, "idle"), daemon=True).start()

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
                elif event.key == pygame.K_RETURN and input_text.strip() and not is_speaking:
                    msg = input_text.strip()
                    input_text = ""
                    subtitle = "Thinking..."
                    mood = "idle"

                    reply = brain.think(msg)
                    reply_text = reply

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

        if not is_speaking and not face_hold_mood and idle_timer > 10:
            with lock: mood = "idle"

        with lock: current_mood = mood
        if face_hold_mood and not is_speaking:
            current_mood = face_hold_mood

        face.update(dt, current_mood)
        face.draw(current_mood, subtitle=subtitle, input_text=input_text,
                  is_online=brain.is_online, brain_mode=brain.brain_mode)
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
