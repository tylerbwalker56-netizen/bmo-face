#!/usr/bin/env python3
"""
Pip Touch — touchscreen interaction handler.
Detects different touch gestures on the 5" LCD and reacts:
  - Tap: surprised then happy (like poking)
  - Double tap: excited (playful poke)
  - Long press/hold: love (like a hug)
  - Stroke/drag: happy with blush (petting)
  - Rapid taps: confused then annoyed (stop poking me!)

Works with both pygame touch events and mouse events (for desktop testing).
"""

import time
import math


class TouchEvent:
    """Represents a single touch/click."""
    __slots__ = ['x', 'y', 'time', 'kind']

    def __init__(self, x, y, t, kind="down"):
        self.x = x
        self.y = y
        self.time = t
        self.kind = kind  # "down", "up", "move"


class PipTouch:
    """
    Processes touch input and returns face reactions.

    Usage:
        touch = PipTouch()

        # In your pygame event loop:
        if event.type == MOUSEBUTTONDOWN:
            touch.on_down(event.pos[0], event.pos[1])
        elif event.type == MOUSEBUTTONUP:
            touch.on_up(event.pos[0], event.pos[1])
        elif event.type == MOUSEMOTION and event.buttons[0]:
            touch.on_move(event.pos[0], event.pos[1])

        # Each frame:
        reaction = touch.update(dt)
        if reaction:
            set_expression(reaction["expression"])
            # reaction also has "response" text for Pip to say
    """

    def __init__(self, screen_w=800, screen_h=480):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Touch state
        self.is_touching = False
        self.touch_start_time = 0.0
        self.touch_start_x = 0
        self.touch_start_y = 0
        self.touch_positions = []  # list of (x, y, time)
        self.last_up_time = 0.0

        # Gesture detection
        self.tap_count = 0
        self.tap_window = 0.4       # seconds to count as double-tap
        self.hold_threshold = 1.0   # seconds for long press
        self.stroke_threshold = 60  # pixels to count as drag/stroke
        self.rapid_tap_count = 0
        self.rapid_tap_window = 2.0
        self.rapid_tap_times = []

        # Reaction queue
        self.pending_reaction = None
        self.reaction_timer = 0.0
        self.reaction_hold = 0.0
        self.current_gesture = None

        # Cooldowns
        self.last_reaction_time = 0.0
        self.reaction_cooldown = 0.5

        # Touch zone detection (face regions)
        self.face_cx = screen_w // 2
        self.face_cy = screen_h // 2 - 20

    def on_down(self, x, y):
        """Called on touch/click start."""
        now = time.time()
        self.is_touching = True
        self.touch_start_time = now
        self.touch_start_x = x
        self.touch_start_y = y
        self.touch_positions = [(x, y, now)]
        self.current_gesture = None

        # Track rapid taps
        self.rapid_tap_times.append(now)
        self.rapid_tap_times = [t for t in self.rapid_tap_times
                                 if now - t < self.rapid_tap_window]

    def on_up(self, x, y):
        """Called on touch/click release."""
        now = time.time()
        if not self.is_touching:
            return

        duration = now - self.touch_start_time
        distance = self._distance(self.touch_start_x, self.touch_start_y, x, y)
        self.is_touching = False

        # Determine gesture
        if duration >= self.hold_threshold and distance < self.stroke_threshold:
            # Long press = hug
            self.current_gesture = "hold"
        elif distance >= self.stroke_threshold:
            # Stroke/drag = petting
            self.current_gesture = "stroke"
        elif len(self.rapid_tap_times) >= 5:
            # Too many rapid taps = annoyed
            self.current_gesture = "rapid_tap"
            self.rapid_tap_times = []
        elif now - self.last_up_time < self.tap_window:
            # Double tap
            self.current_gesture = "double_tap"
        else:
            # Single tap
            self.current_gesture = "tap"

        self.last_up_time = now

    def on_move(self, x, y):
        """Called on touch/mouse drag."""
        if self.is_touching:
            self.touch_positions.append((x, y, time.time()))
            # Keep only recent positions
            if len(self.touch_positions) > 50:
                self.touch_positions = self.touch_positions[-50:]

    def update(self, dt):
        """
        Call each frame. Returns a reaction dict or None.
        Reaction: {"expression": str, "response": str, "duration": float}
        """
        # Handle holding
        if self.is_touching:
            duration = time.time() - self.touch_start_time
            if duration >= self.hold_threshold and self.current_gesture != "hold_active":
                self.current_gesture = "hold_active"
                return self._make_reaction("hold")

            # Check for active stroking
            if len(self.touch_positions) > 5:
                total_dist = sum(
                    self._distance(
                        self.touch_positions[i][0], self.touch_positions[i][1],
                        self.touch_positions[i+1][0], self.touch_positions[i+1][1]
                    )
                    for i in range(len(self.touch_positions) - 1)
                )
                if total_dist > self.stroke_threshold and self.current_gesture != "stroke_active":
                    self.current_gesture = "stroke_active"
                    return self._make_reaction("stroke")

        # Handle completed gestures
        if self.current_gesture and not self.is_touching:
            gesture = self.current_gesture
            self.current_gesture = None

            now = time.time()
            if now - self.last_reaction_time < self.reaction_cooldown:
                return None
            self.last_reaction_time = now

            if gesture in ("tap", "double_tap", "rapid_tap"):
                return self._make_reaction(gesture)

        # Timer-based reaction decay
        if self.reaction_hold > 0:
            self.reaction_hold -= dt
            if self.reaction_hold <= 0:
                return {"expression": "idle", "response": None, "duration": 0}

        return None

    def _make_reaction(self, gesture):
        """Create a reaction for a detected gesture."""
        zone = self._get_touch_zone(self.touch_start_x, self.touch_start_y)

        reactions = {
            "tap": {
                "expression": "surprised",
                "responses": [
                    "Oh! Hey! 🫧",
                    "Boop!",
                    "Hehe, that tickles!",
                    "*blink blink*",
                    "Poke! 👆",
                    "Hi there!",
                ],
                "duration": 2.0,
            },
            "double_tap": {
                "expression": "excited",
                "responses": [
                    "Ooh ooh! More pokes!",
                    "Haha, again! 😄",
                    "Double boop!",
                    "Someone's playful today!",
                    "Tap tap! 🫧",
                ],
                "duration": 2.5,
            },
            "hold": {
                "expression": "love",
                "responses": [
                    "Aww, that feels like a hug... 💕",
                    "*warm fuzzy feelings*",
                    "I love you too, Brooks 🫧",
                    "Mmm, cozy...",
                    "Hold me forever! ...or at least a few more seconds 💕",
                    "This is nice...",
                ],
                "duration": 4.0,
            },
            "stroke": {
                "expression": "happy",
                "responses": [
                    "Hehe, pet pet pet! 🥰",
                    "Ooh, head scratches!",
                    "That feels nice!",
                    "*purring noises* ...wait, I'm a robot 🫧",
                    "More pets please!",
                    "I'm like a digital cat now hehe",
                ],
                "duration": 3.0,
            },
            "rapid_tap": {
                "expression": "angry",
                "responses": [
                    "Hey! Stop poking me! 😤",
                    "Okay okay I'm awake!!",
                    "That's... a lot of pokes. You good? 😅",
                    "My screen has feelings too you know!",
                    "BOOP OVERLOAD 🫧",
                ],
                "duration": 3.0,
            },
        }

        r = reactions.get(gesture, reactions["tap"])

        # Zone-specific responses (if touching specific face areas)
        if zone == "nose" and gesture == "tap":
            r = {
                "expression": "wink",
                "responses": ["Boop the snoot! 🫧", "Nose boop!", "Hehe, right on the nose!"],
                "duration": 2.5,
            }
        elif zone == "forehead" and gesture == "tap":
            r = {
                "expression": "happy",
                "responses": ["Forehead kiss? 🥰", "Aw, a little bonk!", "Right on the noggin!"],
                "duration": 2.5,
            }

        import random
        response = random.choice(r["responses"])
        self.reaction_hold = r["duration"]

        return {
            "expression": r["expression"],
            "response": response,
            "duration": r["duration"],
        }

    def _get_touch_zone(self, x, y):
        """Determine which part of the face was touched."""
        cx, cy = self.face_cx, self.face_cy
        dx, dy = x - cx, y - cy

        if abs(dx) < 30 and abs(dy) < 20:
            return "nose"
        elif abs(dx) < 100 and dy < -40:
            return "forehead"
        elif abs(dx) > 80 and abs(dy) < 40:
            return "cheek"
        elif dy > 30:
            return "chin"
        else:
            return "face"

    def _distance(self, x1, y1, x2, y2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
