#!/usr/bin/env python3
"""
Pip Voice System v2 — online AND offline speech.

Text-to-Speech:
  Online:  OpenAI TTS (nova voice — warm and chill)
  Offline: Piper TTS (free, runs locally, sounds natural)

Speech-to-Text:
  Online:  OpenAI Whisper API
  Offline: Vosk (free, runs locally on Pi)

Install for offline:
  pip install vosk piper-tts
  # Or on Pi:
  pip install vosk
  pip install piper-tts

Piper voices (chill/relaxed):
  - en_US-lessac-medium (smooth male)
  - en_US-amy-medium (warm female)
  - en_GB-alan-medium (chill British male)
  Download: https://github.com/rhasspy/piper/blob/master/VOICES.md
"""

import os
import sys
import json
import time
import threading
import tempfile
import subprocess
import wave

# --- Configuration ---
CONFIG_FILE = os.path.expanduser("~/bmo-face/pip_brain_config.json")
VOSK_MODEL_DIR = os.path.expanduser("~/bmo-face/models/vosk")
PIPER_VOICE_DIR = os.path.expanduser("~/bmo-face/models/piper")

# Piper voice — chill and natural
# Download from: https://huggingface.co/rhasspy/piper-voices
PIPER_VOICE = "en_US-lessac-medium"  # Smooth, relaxed male voice

# OpenAI TTS voice — nova is warm and chill
OPENAI_VOICE = "nova"
OPENAI_VOICE_SPEED = 0.95  # Slightly slower = more chill


def load_api_key():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            return config.get("openai_api_key", "")
    return os.environ.get("OPENAI_API_KEY", "")


# =====================
#  TEXT-TO-SPEECH
# =====================
class PipVoice:
    """Pip's voice — speaks out loud. Online or offline."""

    def __init__(self, api_key=None):
        self.speaking = False
        self.openai_client = None
        self.has_piper = False
        self.has_pyttsx3 = False
        self.mode = "none"

        # Try OpenAI
        key = api_key or load_api_key()
        if key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=key)
                self.mode = "openai"
            except ImportError:
                pass

        # Try Piper (offline, natural voice)
        if not self.openai_client:
            try:
                self._check_piper()
                if self.has_piper:
                    self.mode = "piper"
            except:
                pass

        # Try pyttsx3 (offline, robotic but works everywhere)
        if self.mode == "none":
            try:
                import pyttsx3
                self.has_pyttsx3 = True
                self.mode = "pyttsx3"
            except ImportError:
                pass

        print(f"🔊 Voice mode: {self.mode}")

    def _check_piper(self):
        """Check if Piper TTS is available."""
        try:
            result = subprocess.run(["piper", "--help"], capture_output=True, timeout=3)
            self.has_piper = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Try Python module
            try:
                import piper
                self.has_piper = True
            except ImportError:
                self.has_piper = False

    def speak(self, text, callback_start=None, callback_end=None):
        """Speak text out loud. Callbacks for face animation sync."""
        if not text.strip():
            return
        self.speaking = True
        if callback_start:
            callback_start(text)

        try:
            if self.mode == "openai":
                self._speak_openai(text)
            elif self.mode == "piper":
                self._speak_piper(text)
            elif self.mode == "pyttsx3":
                self._speak_pyttsx3(text)
            else:
                print(f"🔊 (no voice) Pip: {text}")
        except Exception as e:
            # Fallback chain: openai -> piper -> pyttsx3
            if self.mode == "openai":
                try:
                    if self.has_piper:
                        self._speak_piper(text)
                    elif self.has_pyttsx3:
                        self._speak_pyttsx3(text)
                except:
                    print(f"🔊 Voice error: {e}")
            else:
                print(f"🔊 Voice error: {e}")
        finally:
            self.speaking = False
            if callback_end:
                callback_end()

    def _speak_openai(self, text):
        """Natural voice using OpenAI TTS — chill nova voice."""
        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice=OPENAI_VOICE,
            input=text,
            speed=OPENAI_VOICE_SPEED,
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            response.stream_to_file(tmp_path)
            self._play_audio(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _speak_piper(self, text):
        """Offline natural voice using Piper TTS."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            # Check for local model file
            model_path = os.path.join(PIPER_VOICE_DIR, f"{PIPER_VOICE}.onnx")
            if os.path.exists(model_path):
                cmd = ["piper", "--model", model_path, "--output_file", tmp_path]
            else:
                # Use model name (piper downloads automatically)
                cmd = ["piper", "--model", PIPER_VOICE, "--output_file", tmp_path]

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(input=text.encode("utf-8"), timeout=15)
            self._play_audio(tmp_path)
        except Exception as e:
            # Try Python piper module
            try:
                from piper import PiperVoice
                voice = PiperVoice.load(model_path)
                with wave.open(tmp_path, "w") as wav:
                    voice.synthesize(text, wav)
                self._play_audio(tmp_path)
            except:
                raise e
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _speak_pyttsx3(self, text):
        """Offline robotic voice — last resort."""
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)  # Slower = more chill
        engine.setProperty("volume", 0.9)
        # Try to find a smoother voice
        voices = engine.getProperty("voices")
        for v in voices:
            if "zira" in v.name.lower() or "david" in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
        engine.stop()

    def _play_audio(self, path):
        """Play audio file through speakers."""
        if sys.platform == "win32":
            # Windows — try pygame mixer first
            try:
                import pygame
                if pygame.mixer.get_init():
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    pygame.mixer.music.unload()
                    return
            except:
                pass
            # Fallback: Windows Media Player
            try:
                os.startfile(path)
                time.sleep(2)
                return
            except:
                pass
        else:
            # Linux/Pi — try mpv, then aplay
            for player in [
                ["mpv", "--no-video", "--really-quiet", path],
                ["aplay", path],
                ["paplay", path],
            ]:
                try:
                    subprocess.run(player, capture_output=True, timeout=30)
                    return
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue

    def stop(self):
        self.speaking = False


# =====================
#  SPEECH-TO-TEXT
# =====================
class PipEars:
    """Pip's ears — listens through the mic. Online or offline."""

    def __init__(self, api_key=None):
        self.openai_client = None
        self.vosk_model = None
        self.mode = "none"
        self.listening = False
        self.sample_rate = 16000

        # Try OpenAI Whisper
        key = api_key or load_api_key()
        if key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=key)
                self.mode = "whisper"
            except ImportError:
                pass

        # Try Vosk (offline)
        if self.mode == "none":
            try:
                self._init_vosk()
                if self.vosk_model:
                    self.mode = "vosk"
            except:
                pass

        print(f"🎤 Ears mode: {self.mode}")

    def _init_vosk(self):
        """Initialize Vosk offline speech recognition."""
        try:
            from vosk import Model, KaldiRecognizer

            # Check for downloaded model
            if os.path.isdir(VOSK_MODEL_DIR):
                self.vosk_model = Model(VOSK_MODEL_DIR)
            else:
                # Try small English model (auto-download)
                self.vosk_model = Model(lang="en-us")
        except Exception as e:
            print(f"🎤 Vosk init failed: {e}")
            self.vosk_model = None

    def listen_once(self, duration=5):
        """Record audio and transcribe."""
        audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name

        try:
            # Record audio
            if sys.platform == "win32":
                self._record_windows(audio_path, duration)
            else:
                self._record_linux(audio_path, duration)

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
                return ""

            # Transcribe
            if self.mode == "whisper":
                return self._transcribe_whisper(audio_path)
            elif self.mode == "vosk":
                return self._transcribe_vosk(audio_path)
            return ""

        except Exception as e:
            print(f"🎤 Listen error: {e}")
            return ""
        finally:
            try:
                os.unlink(audio_path)
            except:
                pass

    def _record_linux(self, path, duration):
        """Record on Linux/Pi using arecord."""
        subprocess.run([
            "arecord", "-D", "default", "-f", "S16_LE",
            "-r", str(self.sample_rate), "-c", "1",
            "-d", str(duration), path
        ], capture_output=True, timeout=duration + 3)

    def _record_windows(self, path, duration):
        """Record on Windows using sounddevice or pyaudio."""
        try:
            import sounddevice as sd
            import numpy as np
            print("🎤 Listening...")
            audio = sd.rec(int(duration * self.sample_rate),
                          samplerate=self.sample_rate, channels=1, dtype='int16')
            sd.wait()
            with wave.open(path, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio.tobytes())
        except ImportError:
            print("🎤 Need sounddevice: pip install sounddevice")

    def _transcribe_whisper(self, path):
        """Online transcription with OpenAI Whisper."""
        with open(path, "rb") as f:
            result = self.openai_client.audio.transcriptions.create(
                model="whisper-1", file=f, language="en")
        return result.text.strip()

    def _transcribe_vosk(self, path):
        """Offline transcription with Vosk."""
        from vosk import KaldiRecognizer
        rec = KaldiRecognizer(self.vosk_model, self.sample_rate)

        with wave.open(path, "rb") as wf:
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                rec.AcceptWaveform(data)

        result = json.loads(rec.FinalResult())
        return result.get("text", "").strip()

    def listen_continuous(self, callback, stop_event=None):
        """Continuously listen and call callback(text) on speech."""
        if stop_event is None:
            stop_event = threading.Event()
        self.listening = True
        print("🎤 Continuous listening started...")

        while not stop_event.is_set() and self.listening:
            text = self.listen_once(duration=4)
            if text and text.strip():
                callback(text.strip())
            time.sleep(0.2)

    def stop(self):
        self.listening = False


# =====================
#  COMPLETE VOICE SYSTEM
# =====================
class PipVoiceSystem:
    """Full voice loop: listen → think → speak."""

    def __init__(self, brain=None):
        api_key = load_api_key()
        self.ears = PipEars(api_key=api_key)
        self.voice = PipVoice(api_key=api_key)
        self.brain = brain
        self.running = False
        self.expression_callback = None
        self.talk_callback = None  # For syllable-synced mouth
        self.stop_event = threading.Event()

    def set_brain(self, brain):
        self.brain = brain

    def set_expression_callback(self, callback):
        self.expression_callback = callback

    def set_talk_callback(self, callback):
        """Register callback for talk animation: callback(text) on start, callback(None) on end."""
        self.talk_callback = callback

    def express(self, expression):
        if self.expression_callback:
            self.expression_callback(expression)

    def start(self):
        """Start the full voice loop."""
        self.running = True
        self.stop_event.clear()

        def on_heard(text):
            if not text or not self.brain:
                return
            print(f"\n👂 Heard: {text}")
            self.express("talking")

            reply = self.brain.chat(text)
            clean = reply
            if hasattr(self.brain, 'clean_response'):
                clean = self.brain.clean_response(reply)
            print(f"🫧 Pip: {clean}")

            # Speak with face animation sync
            def on_talk_start(t):
                if self.talk_callback:
                    self.talk_callback(t)

            def on_talk_end():
                if self.talk_callback:
                    self.talk_callback(None)
                time.sleep(0.5)
                self.express("idle")

            self.voice.speak(clean,
                           callback_start=on_talk_start,
                           callback_end=on_talk_end)

        listen_thread = threading.Thread(
            target=self.ears.listen_continuous,
            args=(on_heard, self.stop_event),
            daemon=True)
        listen_thread.start()

        print("🫧 Voice system active! Talk to Pip through the microphone.")
        return listen_thread

    def stop(self):
        self.running = False
        self.stop_event.set()
        self.ears.stop()
        self.voice.stop()
        print("🫧 Voice system stopped.")

    def say(self, text):
        """Manually make Pip say something."""
        self.express("talking")

        def on_end():
            self.express("idle")

        self.voice.speak(text, callback_end=on_end)


# --- CLI for testing ---
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pip Voice System v2")
    parser.add_argument("mode", choices=["listen", "speak", "chat", "status"],
                        help="listen=test mic, speak=test speaker, chat=full voice, status=check setup")
    parser.add_argument("--text", type=str, help="Text to speak")
    args = parser.parse_args()

    if args.mode == "status":
        print("Checking voice setup...")
        voice = PipVoice()
        ears = PipEars()
        print(f"  Voice: {voice.mode}")
        print(f"  Ears: {ears.mode}")
        print(f"\nFor offline voice: pip install piper-tts vosk")
        print(f"For online voice: set OpenAI API key in pip_brain_config.json")

    elif args.mode == "listen":
        ears = PipEars()
        print("🎤 Speak now (5 seconds)...")
        text = ears.listen_once(duration=5)
        print(f"   Heard: '{text}'")

    elif args.mode == "speak":
        voice = PipVoice()
        text = args.text or "Hey, I'm Pip. Just chillin. How's it going?"
        voice.speak(text)

    elif args.mode == "chat":
        from pip_brain import PipBrain
        brain = PipBrain()
        system = PipVoiceSystem(brain=brain)
        try:
            system.start()
            print("\nPress Ctrl+C to stop.\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            system.stop()


if __name__ == "__main__":
    main()
