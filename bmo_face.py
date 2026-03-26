#!/usr/bin/env python3
"""
BMO Face — Pip's animated face display.
Inspired by BMO from Adventure Time.
Built by Brooks, polished by Pip 🫧

Controls:
  Left/Right arrows — cycle moods
  F — toggle fullscreen
  Escape — quit

v2 — Enhanced animations:
  - Syllable-synced talking mouth
  - Eye drifting / pupil tracking
  - Breathing animation
  - Emotional particles (sparkles, tears, hearts)
  - Per-mood micro-animations
"""

import pygame
import sys
import math
import random
import time

pygame.init()

# --- Screen ---
WIDTH, HEIGHT = 800, 480
FPS = 30

# --- Colors ---
BG_COLOR = (0, 210, 200)
BG_SAD = (120, 170, 200)
BG_ANGRY = (200, 100, 100)
BG_SLEEPY = (100, 180, 170)
BG_LOVE = (220, 170, 190)
BG_EXCITED = (50, 220, 180)

BLACK = (15, 25, 20)
WHITE = (240, 250, 245)
BLUSH = (220, 130, 150)
HEART = (230, 70, 100)

# --- Fonts ---
font = pygame.font.SysFont("monospace", 24, bold=True)
small_font = pygame.font.SysFont("monospace", 18)

# --- Moods ---
MOODS = [
    "idle", "happy", "talking", "surprised",
    "love", "sad", "angry", "sleepy",
    "confused", "wink", "excited"
]


def get_bg(mood):
    colors = {
        "sad": BG_SAD, "angry": BG_ANGRY,
        "sleepy": BG_SLEEPY, "love": BG_LOVE,
        "excited": BG_EXCITED,
    }
    return colors.get(mood, BG_COLOR)


# =====================
#  SYLLABLE ESTIMATOR
# =====================
def estimate_syllables(text):
    """Rough syllable count per word — drives mouth open/close timing."""
    text = text.lower().strip()
    if not text:
        return []
    words = text.split()
    result = []
    for word in words:
        clean = ''.join(c for c in word if c.isalpha())
        if not clean:
            continue
        count = 0
        prev_vowel = False
        for ch in clean:
            is_vowel = ch in 'aeiouy'
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if clean.endswith('e') and count > 1:
            count -= 1
        result.append(max(1, count))
    return result


# =====================
#  PARTICLE SYSTEM
# =====================
class Particle:
    __slots__ = ['x', 'y', 'vx', 'vy', 'life', 'max_life', 'kind', 'size']

    def __init__(self, x, y, vx, vy, life, kind, size=4):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.kind = kind
        self.size = size

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.kind == 'tear':
            self.vy += 120 * dt
        return self.life > 0

    def draw(self, screen):
        a = max(0.0, self.life / self.max_life)
        ix, iy = int(self.x), int(self.y)
        if self.kind == 'sparkle':
            s = int(self.size * a)
            if s > 0:
                c = (int(255 * a), int(255 * a), int(200 * a))
                pygame.draw.line(screen, c, (ix - s, iy), (ix + s, iy), 2)
                pygame.draw.line(screen, c, (ix, iy - s), (ix, iy + s), 2)
                d = int(s * 0.7)
                pygame.draw.line(screen, c, (ix - d, iy - d), (ix + d, iy + d), 1)
                pygame.draw.line(screen, c, (ix + d, iy - d), (ix - d, iy + d), 1)
        elif self.kind == 'tear':
            s = int(3 * a + 1)
            c = (int(100 + 80 * a), int(180 + 50 * a), 230)
            pygame.draw.circle(screen, c, (ix, iy), s)
        elif self.kind == 'heart':
            s = int(8 * a + 4)
            c = (int(230 * a + 20), int(70 * a + 30), int(100 * a + 40))
            pygame.draw.circle(screen, c, (ix - s // 4, iy), s // 3)
            pygame.draw.circle(screen, c, (ix + s // 4, iy), s // 3)
            pts = [(ix - s // 2, iy + 2), (ix + s // 2, iy + 2), (ix, iy + s // 2 + 3)]
            pygame.draw.polygon(screen, c, pts)
        elif self.kind == 'anger':
            s = int(self.size * a)
            if s > 1:
                c = (220, 60, 40)
                pygame.draw.line(screen, c, (ix - s, iy - s), (ix + s, iy + s), 3)
                pygame.draw.line(screen, c, (ix + s, iy - s), (ix - s, iy + s), 3)


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, kind, count=1, spread=30, speed=40, life=1.0, size=4):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            sp = random.uniform(speed * 0.5, speed * 1.5)
            vx = math.cos(angle) * sp + random.uniform(-spread, spread)
            vy = math.sin(angle) * sp - abs(random.uniform(0, speed))
            l = life * random.uniform(0.6, 1.0)
            s = size * random.uniform(0.7, 1.3)
            self.particles.append(Particle(x, y, vx, vy, l, kind, s))

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)


# =====================
#  TALK ANIMATOR
# =====================
class TalkAnimator:
    """Drives syllable-synced mouth animation from text."""

    def __init__(self):
        self.total_syllables = 0
        self.time_per_syllable = 0.12
        self.timer = 0.0
        self.active = False
        self.phase_in_syllable = 0.0

    def start_talking(self, text, duration_hint=None):
        word_syllables = estimate_syllables(text)
        total = sum(word_syllables)
        if total == 0:
            return
        self.total_syllables = total
        self.timer = 0.0
        self.active = True
        if duration_hint and duration_hint > 0:
            self.time_per_syllable = duration_hint / total
        else:
            self.time_per_syllable = 0.12
        self.time_per_syllable = max(0.06, min(0.3, self.time_per_syllable))

    def stop_talking(self):
        self.active = False

    def update(self, dt):
        if not self.active:
            return
        self.timer += dt
        if int(self.timer / self.time_per_syllable) >= self.total_syllables:
            self.active = False
            return
        self.phase_in_syllable = (self.timer % self.time_per_syllable) / self.time_per_syllable

    def get_openness(self):
        if not self.active:
            return 0.0
        p = self.phase_in_syllable
        return math.sin((p / 0.6) * math.pi) if p < 0.6 else 0.0


# =====================
#  BMO FACE
# =====================
class BMOFace:
    def __init__(self, screen):
        self.screen = screen
        self.w = WIDTH
        self.h = HEIGHT

        # Timers
        self.talk_phase = 0.0
        self.bob_phase = 0.0
        self.blink_timer = time.time() + random.uniform(2, 5)
        self.blink_progress = 0.0
        self.is_blinking = False
        self.idle_timer = 0.0
        self.zzz_phase = 0.0
        self.breath_phase = 0.0

        # Eye drift
        self.eye_drift_x = 0.0
        self.eye_drift_y = 0.0
        self.eye_drift_target_x = 0.0
        self.eye_drift_target_y = 0.0
        self.eye_drift_timer = time.time() + random.uniform(1, 3)

        # Shake (angry/excited)
        self.shake_offset = 0.0

        # Systems
        self.particles = ParticleSystem()
        self.particle_timer = 0.0
        self.talk_anim = TalkAnimator()

    def start_talking(self, text, duration_hint=None):
        self.talk_anim.start_talking(text, duration_hint)

    def stop_talking(self):
        self.talk_anim.stop_talking()

    def update(self, dt, mood):
        self.talk_phase += dt * 6
        self.bob_phase += dt * 1.5
        self.idle_timer += dt
        self.zzz_phase += dt * 2
        self.breath_phase += dt * 0.8
        self.particle_timer += dt
        self.talk_anim.update(dt)

        # Shake
        if mood == "angry":
            self.shake_offset = random.uniform(-2, 2)
        elif mood == "excited":
            self.shake_offset = random.uniform(-3, 3)
        else:
            self.shake_offset *= 0.8

        # Eye drift
        if mood in ("idle", "talking", "confused"):
            now = time.time()
            if now >= self.eye_drift_timer:
                self.eye_drift_target_x = random.uniform(-8, 8)
                self.eye_drift_target_y = random.uniform(-5, 5)
                self.eye_drift_timer = now + random.uniform(1.5, 4)
            self.eye_drift_x += (self.eye_drift_target_x - self.eye_drift_x) * dt * 2
            self.eye_drift_y += (self.eye_drift_target_y - self.eye_drift_y) * dt * 2
        else:
            self.eye_drift_x *= 0.9
            self.eye_drift_y *= 0.9

        # Blinking
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

        # Mood particles
        if mood in ("happy", "excited"):
            if self.particle_timer > 0.3:
                self.particle_timer = 0.0
                self.particles.emit(
                    random.randint(100, WIDTH - 100), random.randint(50, 200),
                    'sparkle', count=2, speed=20, life=0.8, size=6)
        elif mood == "sad":
            if self.particle_timer > 1.2:
                self.particle_timer = 0.0
                side = random.choice([-70, 70])
                self.particles.emit(
                    self.w // 2 + side, self.h // 2 - 40,
                    'tear', count=1, speed=5, spread=3, life=1.5, size=3)
        elif mood == "love":
            if self.particle_timer > 0.5:
                self.particle_timer = 0.0
                self.particles.emit(
                    random.randint(150, WIDTH - 150), random.randint(100, HEIGHT - 100),
                    'heart', count=1, speed=15, life=1.2, size=6)
        elif mood == "angry":
            if self.particle_timer > 0.6:
                self.particle_timer = 0.0
                self.particles.emit(
                    random.randint(100, WIDTH - 100), random.randint(40, 160),
                    'anger', count=1, speed=10, life=0.7, size=5)

        self.particles.update(dt)

    def get_blink(self):
        if not self.is_blinking:
            return 1.0
        return 1.0 - self.blink_progress if self.blink_progress < 1.0 else self.blink_progress - 1.0

    def draw(self, mood):
        self.screen.fill(get_bg(mood))

        breath = math.sin(self.breath_phase) * 2
        bob_speed = 3.0 if mood == "excited" else 1.0
        bob_amp = 5 if mood == "excited" else 3
        bob = int(math.sin(self.bob_phase * bob_speed) * bob_amp)
        shake_x = int(self.shake_offset)

        cx = self.w // 2 + shake_x
        cy = self.h // 2 - 20 + bob + int(breath)
        lx, rx = cx - 70, cx + 70
        ey = cy - 30
        my = cy + 55
        edx, edy = int(self.eye_drift_x), int(self.eye_drift_y)

        self._draw_brows(lx, rx, ey, mood)
        self._draw_eyes(lx, rx, ey, edx, edy, mood)
        self._draw_cheeks(cx, cy, mood)
        self._draw_mouth(cx, my, mood)
        self._draw_extras(cx, cy, mood)
        self.particles.draw(self.screen)

    # ---- EYES ----
    def _draw_eyes(self, lx, rx, ey, edx, edy, mood):
        blink = self.get_blink()

        if mood in ("idle", "talking", "confused", "excited"):
            ew, eh = 30, int(34 * blink)
            if eh > 2:
                pygame.draw.ellipse(self.screen, BLACK, (lx - ew, ey - eh, ew * 2, eh * 2))
                pygame.draw.ellipse(self.screen, BLACK, (rx - ew, ey - eh, ew * 2, eh * 2))
                if eh > 10:
                    hx, hy = 8 + edx // 2, -8 + edy // 2
                    pygame.draw.circle(self.screen, WHITE, (lx + hx, ey + hy), 7)
                    pygame.draw.circle(self.screen, WHITE, (rx + hx, ey + hy), 7)
                    pygame.draw.circle(self.screen, WHITE, (lx + hx - 10, ey + hy + 12), 3)
                    pygame.draw.circle(self.screen, WHITE, (rx + hx - 10, ey + hy + 12), 3)
            else:
                pygame.draw.line(self.screen, BLACK, (lx - 28, ey), (lx + 28, ey), 4)
                pygame.draw.line(self.screen, BLACK, (rx - 28, ey), (rx + 28, ey), 4)

        elif mood == "happy":
            off = int(math.sin(self.idle_timer * 2) * 1.5)
            pygame.draw.arc(self.screen, BLACK, (lx - 26, ey - 14 + off, 52, 28), 0.3, math.pi - 0.3, 6)
            pygame.draw.arc(self.screen, BLACK, (rx - 26, ey - 14 + off, 52, 28), 0.3, math.pi - 0.3, 6)

        elif mood == "sad":
            pygame.draw.ellipse(self.screen, BLACK, (lx - 22, ey - 10, 44, 24))
            pygame.draw.ellipse(self.screen, BLACK, (rx - 22, ey - 10, 44, 24))
            pygame.draw.circle(self.screen, WHITE, (lx + 4, ey + 2), 5)
            pygame.draw.circle(self.screen, WHITE, (rx + 4, ey + 2), 5)
            pygame.draw.line(self.screen, BLACK, (lx - 28, ey - 26), (lx + 16, ey - 36), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 16, ey - 36), (rx + 28, ey - 26), 4)

        elif mood == "angry":
            pygame.draw.ellipse(self.screen, BLACK, (lx - 22, ey - 12, 44, 28))
            pygame.draw.ellipse(self.screen, BLACK, (rx - 22, ey - 12, 44, 28))
            pygame.draw.circle(self.screen, (255, 100, 80), (lx + 6, ey - 4), 4)
            pygame.draw.circle(self.screen, (255, 100, 80), (rx + 6, ey - 4), 4)

        elif mood == "sleepy":
            droop = int(math.sin(self.idle_timer * 0.5) * 2)
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey + 4 + droop), (lx + 26, ey + 4 + droop), 5)
            pygame.draw.line(self.screen, BLACK, (rx - 26, ey + 4 + droop), (rx + 26, ey + 4 + droop), 5)
            pygame.draw.line(self.screen, BLACK, (lx - 28, ey - 6 + droop), (lx + 28, ey + 2 + droop), 3)
            pygame.draw.line(self.screen, BLACK, (rx - 28, ey + 2 + droop), (rx + 28, ey - 6 + droop), 3)

        elif mood == "surprised":
            pulse = int(math.sin(self.idle_timer * 4) * 3)
            r = 32 + pulse
            pygame.draw.ellipse(self.screen, BLACK, (lx - r, ey - r - 4, r * 2, r * 2 + 4), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx - r, ey - r - 4, r * 2, r * 2 + 4), 5)
            pygame.draw.circle(self.screen, WHITE, (lx + 10, ey - 10), 10)
            pygame.draw.circle(self.screen, WHITE, (rx + 10, ey - 10), 10)
            pygame.draw.circle(self.screen, WHITE, (lx - 6, ey + 6), 5)
            pygame.draw.circle(self.screen, WHITE, (rx - 6, ey + 6), 5)

        elif mood == "wink":
            wy = int(math.sin(self.idle_timer * 3) * 1)
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey + wy), (lx + 26, ey + wy), 5)
            pygame.draw.ellipse(self.screen, BLACK, (rx - 28, ey - 30, 56, 56))
            pygame.draw.circle(self.screen, WHITE, (rx + 8, ey - 8), 7)
            pygame.draw.circle(self.screen, WHITE, (rx - 4, ey + 6), 3)

        elif mood == "love":
            pulse = 1.0 + math.sin(self.idle_timer * 3) * 0.15
            sz = int(28 * pulse)
            self._draw_heart(lx, ey, sz, HEART)
            self._draw_heart(rx, ey, sz, HEART)

    # ---- BROWS ----
    def _draw_brows(self, lx, rx, ey, mood):
        if mood == "angry":
            tw = int(math.sin(self.idle_timer * 8) * 1.5)
            pygame.draw.line(self.screen, BLACK, (lx - 32, ey - 36 + tw), (lx + 16, ey - 20), 7)
            pygame.draw.line(self.screen, BLACK, (rx - 16, ey - 20), (rx + 32, ey - 36 + tw), 7)
        elif mood == "confused":
            b = int(math.sin(self.idle_timer * 2) * 3)
            pygame.draw.line(self.screen, BLACK, (lx - 26, ey - 38 + b), (lx + 20, ey - 44 + b), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 20, ey - 34), (rx + 26, ey - 34), 4)
        elif mood == "excited":
            b = int(math.sin(self.idle_timer * 5) * 3)
            pygame.draw.line(self.screen, BLACK, (lx - 24, ey - 40 + b), (lx + 24, ey - 46 + b), 4)
            pygame.draw.line(self.screen, BLACK, (rx - 24, ey - 46 + b), (rx + 24, ey - 40 + b), 4)

    # ---- MOUTH ----
    def _draw_mouth(self, cx, my, mood):
        if mood == "idle":
            br = math.sin(self.breath_phase) * 1
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 25, int(my - 8 + br), 50, 24),
                            math.pi + 0.4, 2 * math.pi - 0.4, 3)

        elif mood in ("happy", "wink"):
            bounce = int(math.sin(self.idle_timer * 2.5) * 2)
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 50, my - 16 + bounce, 100, 46),
                            math.pi + 0.2, 2 * math.pi - 0.2, 5)

        elif mood == "excited":
            bounce = abs(math.sin(self.idle_timer * 4)) * 8
            h = int(16 + bounce)
            pygame.draw.ellipse(self.screen, BLACK, (cx - 40, my - 4, 80, h))
            if h > 12:
                pygame.draw.line(self.screen, WHITE, (cx - 30, my + h // 3), (cx + 30, my + h // 3), 2)

        elif mood == "talking":
            # SYLLABLE-SYNCED MOUTH
            if self.talk_anim.active:
                openness = self.talk_anim.get_openness()
            else:
                openness = abs(math.sin(self.talk_phase))

            h = int(6 + 24 * openness)
            w = int(18 + 10 * openness)
            if h > 4:
                pygame.draw.ellipse(self.screen, BLACK, (cx - w, my - h // 2, w * 2, h))
                if openness > 0.6:
                    th = int(h * 0.3)
                    pygame.draw.ellipse(self.screen, (180, 80, 90),
                                        (cx - w // 2, my + h // 4 - th // 2, w, th))
            else:
                pygame.draw.line(self.screen, BLACK, (cx - 16, my), (cx + 16, my), 3)

        elif mood == "sad":
            tr = int(math.sin(self.idle_timer * 5) * 1.5)
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 30, my + 4 + tr, 60, 30),
                            0.4, math.pi - 0.4, 4)

        elif mood == "angry":
            # Tense flat line — teeth-grit twitch
            tw = int(math.sin(self.idle_timer * 10) * 1)
            pygame.draw.line(self.screen, BLACK, (cx - 30, my + tw), (cx + 30, my + tw), 6)

        elif mood == "sleepy":
            points = []
            for i in range(20):
                x = cx - 20 + (i * 40 / 19)
                y = my + math.sin(i * 0.8 + self.idle_timer * 2) * 4
                points.append((int(x), int(y)))
            if len(points) > 1:
                pygame.draw.lines(self.screen, BLACK, False, points, 3)

        elif mood == "surprised":
            # Small O that pulses
            pulse = int(math.sin(self.idle_timer * 3) * 3)
            pygame.draw.ellipse(self.screen, BLACK, (cx - 14, my - 4, 28, 30 + pulse), 4)

        elif mood == "confused":
            points = []
            for i in range(16):
                x = cx - 24 + (i * 48 / 15)
                y = my + math.sin(i * 1.2 + self.idle_timer) * 6
                points.append((int(x), int(y)))
            pygame.draw.lines(self.screen, BLACK, False, points, 4)

        elif mood == "love":
            pygame.draw.arc(self.screen, BLACK,
                            (cx - 35, my - 10, 70, 36),
                            math.pi + 0.3, 2 * math.pi - 0.3, 4)

    # ---- CHEEKS ----
    def _draw_cheeks(self, cx, cy, mood):
        if mood in ("happy", "love", "wink", "excited"):
            # Pulsing blush
            pulse = int(math.sin(self.idle_timer * 2) * 3)
            r = 20 + pulse
            pygame.draw.circle(self.screen, BLUSH, (cx - 120, cy + 10), r)
            pygame.draw.circle(self.screen, BLUSH, (cx + 120, cy + 10), r)

    # ---- EXTRAS ----
    def _draw_extras(self, cx, cy, mood):
        if mood == "sleepy":
            zx, zy = cx + 110, cy - 60
            for i, char in enumerate("Zzz"):
                off = math.sin(self.zzz_phase + i * 0.8) * 6
                size = 28 - i * 4
                f = pygame.font.SysFont("monospace", size, bold=True)
                surf = f.render(char, True, BLACK)
                self.screen.blit(surf, (zx + i * 20, int(zy - i * 22 + off)))

        elif mood == "confused":
            f = pygame.font.SysFont("monospace", 36, bold=True)
            off = math.sin(self.idle_timer * 3) * 5
            # Rotating ? effect via slight horizontal wobble
            wx = math.sin(self.idle_timer * 2) * 3
            surf = f.render("?", True, BLACK)
            self.screen.blit(surf, (int(cx + 100 + wx), int(cy - 80 + off)))

        elif mood == "excited":
            f = pygame.font.SysFont("monospace", 30, bold=True)
            off = math.sin(self.idle_timer * 4) * 4
            surf = f.render("!!", True, BLACK)
            self.screen.blit(surf, (cx + 100, int(cy - 70 + off)))

    # ---- HEART SHAPE ----
    def _draw_heart(self, cx, cy, size, color):
        s = size
        pygame.draw.circle(self.screen, color, (cx - s // 4, cy - s // 5), s // 3)
        pygame.draw.circle(self.screen, color, (cx + s // 4, cy - s // 5), s // 3)
        points = [
            (cx - s // 2 - 2, cy + 2),
            (cx + s // 2 + 2, cy + 2),
            (cx, cy + s // 2 + 8)
        ]
        pygame.draw.polygon(self.screen, color, points)


# =====================
#  MAIN LOOP
# =====================
def main():
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        fullscreen = True
    except Exception:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        fullscreen = False

    pygame.display.set_caption("Pip — BMO Face")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    face = BMOFace(screen)
    mood_idx = 0

    # Import control server if available
    try:
        from face_control import FaceControlServer
        current_mood = ["idle"]

        def on_command(cmd):
            action = cmd.get("action", "expression")
            if action == "expression":
                expr = cmd.get("value", "idle")
                if expr in MOODS:
                    current_mood[0] = expr
            elif action == "talk":
                # Syllable-synced talking: {"action":"talk","text":"Hello!","duration":1.5}
                text = cmd.get("text", "")
                duration = cmd.get("duration", None)
                if text:
                    current_mood[0] = "talking"
                    face.start_talking(text, duration_hint=duration)
            elif action == "stop_talk":
                face.stop_talking()
                current_mood[0] = "idle"

        control = FaceControlServer(callback=on_command)
        control.start()
        has_control = True
    except ImportError:
        has_control = False
        current_mood = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    mood_idx = (mood_idx + 1) % len(MOODS)
                    if has_control:
                        current_mood[0] = MOODS[mood_idx]
                elif event.key == pygame.K_LEFT:
                    mood_idx = (mood_idx - 1) % len(MOODS)
                    if has_control:
                        current_mood[0] = MOODS[mood_idx]
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((WIDTH, HEIGHT))
                    face.screen = screen
                elif event.key == pygame.K_t:
                    # Test syllable talking with T key
                    face.start_talking("Hello! I am Pip, your friendly robot companion!")
                    if has_control:
                        current_mood[0] = "talking"

        # Get mood
        if has_control:
            mood = current_mood[0]
        else:
            mood = MOODS[mood_idx]

        # Auto-return to idle when talk animation finishes
        if mood == "talking" and not face.talk_anim.active and has_control:
            # Only auto-idle if talk_anim was being used (not legacy mode)
            pass  # Keep talking expression for legacy sine-wave mode

        face.update(dt, mood)
        face.draw(mood)

        # Show current mood label
        label = small_font.render(mood, True, (40, 60, 50))
        screen.blit(label, (10, HEIGHT - 28))

        pygame.display.flip()

    if has_control:
        control.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()