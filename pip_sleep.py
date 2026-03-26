#!/usr/bin/env python3
"""
Pip Sleep — thermal protection + fatigue management.
Monitors CPU temperature and uptime, triggers sleep mode when needed.
Saves Pokémon game progress before sleeping, wakes up and resumes.

Sleep triggers:
  - CPU temp > 75°C (thermal protection)
  - Uptime > 4 hours continuous (fatigue rest)
  - Manual /sleep command

During sleep:
  - Face shows sleepy expression with Zzz
  - Pokémon game saves and pauses
  - CPU cools down / system rests
  - Wakes after cooldown period or on touch/voice
"""

import os
import time
import json
import threading
from datetime import datetime

SLEEP_LOG = os.path.expanduser("~/bmo-face/pip_sleep_log.json")

# Thresholds
TEMP_WARNING = 70       # °C — start showing warm face
TEMP_CRITICAL = 78      # °C — force sleep
MAX_UPTIME_HOURS = 4    # Hours before fatigue sleep
SLEEP_DURATION_THERMAL = 300   # 5 min cooldown for thermal
SLEEP_DURATION_FATIGUE = 600   # 10 min rest for fatigue
TEMP_WAKE_THRESHOLD = 55       # °C — cool enough to wake


def get_cpu_temp():
    """Read CPU temperature. Works on Raspberry Pi, returns None on desktop."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except (FileNotFoundError, ValueError):
        return None


def get_uptime_seconds():
    """Get system uptime in seconds."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (FileNotFoundError, ValueError):
        return 0.0


class PipSleep:
    """Manages Pip's sleep/wake cycle for health and thermal protection."""

    def __init__(self):
        self.is_sleeping = False
        self.sleep_reason = None
        self.sleep_start = 0.0
        self.sleep_duration = 0.0
        self.session_start = time.time()
        self.wake_callbacks = []
        self.sleep_callbacks = []
        self.last_temp_check = 0.0
        self.temp_check_interval = 10.0  # Check every 10 seconds
        self.current_temp = None
        self.is_warm = False
        self.sleep_log = self._load_log()
        self._monitor_thread = None
        self._running = False

    def _load_log(self):
        if os.path.exists(SLEEP_LOG):
            try:
                with open(SLEEP_LOG) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"sessions": [], "total_sleep_time": 0}

    def _save_log(self):
        os.makedirs(os.path.dirname(SLEEP_LOG), exist_ok=True)
        with open(SLEEP_LOG, "w") as f:
            json.dump(self.sleep_log, f, indent=2)

    def on_sleep(self, callback):
        """Register callback for when Pip falls asleep. callback(reason)"""
        self.sleep_callbacks.append(callback)

    def on_wake(self, callback):
        """Register callback for when Pip wakes up. callback()"""
        self.wake_callbacks.append(callback)

    def start_monitoring(self):
        """Start background thermal/fatigue monitoring."""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False

    def _monitor_loop(self):
        while self._running:
            if not self.is_sleeping:
                self._check_health()
            else:
                self._check_wake()
            time.sleep(self.temp_check_interval)

    def _check_health(self):
        """Check if Pip needs to sleep."""
        # Temperature check
        temp = get_cpu_temp()
        if temp is not None:
            self.current_temp = temp
            self.is_warm = temp >= TEMP_WARNING

            if temp >= TEMP_CRITICAL:
                self.go_to_sleep("thermal",
                                 f"CPU too hot ({temp:.1f}°C)! Taking a nap to cool down.",
                                 SLEEP_DURATION_THERMAL)
                return

        # Fatigue check — hours since session started
        session_hours = (time.time() - self.session_start) / 3600
        if session_hours >= MAX_UPTIME_HOURS:
            self.go_to_sleep("fatigue",
                             f"Been running for {session_hours:.1f} hours. Time for a rest!",
                             SLEEP_DURATION_FATIGUE)

    def _check_wake(self):
        """Check if it's time to wake up."""
        elapsed = time.time() - self.sleep_start

        if self.sleep_reason == "thermal":
            # Wake when cool enough OR sleep duration exceeded
            temp = get_cpu_temp()
            if temp is not None and temp <= TEMP_WAKE_THRESHOLD:
                self.wake_up()
                return
            if elapsed >= self.sleep_duration:
                self.wake_up()
                return
        else:
            # Fatigue sleep — wake after duration
            if elapsed >= self.sleep_duration:
                self.wake_up()

    def go_to_sleep(self, reason, message="", duration=300):
        """Put Pip to sleep."""
        if self.is_sleeping:
            return

        self.is_sleeping = True
        self.sleep_reason = reason
        self.sleep_start = time.time()
        self.sleep_duration = duration

        print(f"😴 Pip is going to sleep: {reason}")
        if message:
            print(f"   {message}")

        # Log it
        self.sleep_log["sessions"].append({
            "reason": reason,
            "message": message,
            "start": datetime.now().isoformat(),
            "temp": self.current_temp,
            "duration_planned": duration,
        })
        self._save_log()

        # Notify callbacks (face, game save, etc.)
        for cb in self.sleep_callbacks:
            try:
                cb(reason)
            except Exception as e:
                print(f"Sleep callback error: {e}")

    def wake_up(self):
        """Wake Pip up."""
        if not self.is_sleeping:
            return

        sleep_time = time.time() - self.sleep_start
        self.is_sleeping = False
        self.sleep_reason = None
        self.session_start = time.time()  # Reset session timer

        print(f"☀️ Pip is waking up! (slept {sleep_time:.0f}s)")

        # Update log
        self.sleep_log["total_sleep_time"] += sleep_time
        if self.sleep_log["sessions"]:
            self.sleep_log["sessions"][-1]["actual_duration"] = sleep_time
            self.sleep_log["sessions"][-1]["wake_time"] = datetime.now().isoformat()
        self._save_log()

        # Notify callbacks
        for cb in self.wake_callbacks:
            try:
                cb()
            except Exception as e:
                print(f"Wake callback error: {e}")

    def force_wake(self):
        """Force wake (touch or voice triggered)."""
        if self.is_sleeping:
            # Don't force wake from thermal — safety first
            if self.sleep_reason == "thermal":
                temp = get_cpu_temp()
                if temp and temp > TEMP_WARNING:
                    return False  # Still too hot
            self.wake_up()
            return True
        return False

    def get_status(self):
        """Get sleep system status."""
        session_hours = (time.time() - self.session_start) / 3600
        status = {
            "sleeping": self.is_sleeping,
            "reason": self.sleep_reason,
            "cpu_temp": f"{self.current_temp:.1f}°C" if self.current_temp else "N/A",
            "is_warm": self.is_warm,
            "session_hours": f"{session_hours:.1f}h",
            "total_sleeps": len(self.sleep_log.get("sessions", [])),
        }
        if self.is_sleeping:
            remaining = self.sleep_duration - (time.time() - self.sleep_start)
            status["sleep_remaining"] = f"{max(0, remaining):.0f}s"
        return status

    def get_sleep_response(self):
        """Get a text response about why Pip is sleeping."""
        if not self.is_sleeping:
            return None

        remaining = self.sleep_duration - (time.time() - self.sleep_start)
        mins = max(0, remaining) / 60

        if self.sleep_reason == "thermal":
            return f"Zzz... cooling down... ({mins:.0f} min left) 🌡️"
        elif self.sleep_reason == "fatigue":
            return f"Zzz... resting up... ({mins:.0f} min left) 😴"
        else:
            return f"Zzz... ({mins:.0f} min left)"
