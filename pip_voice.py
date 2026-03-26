#!/usr/bin/env python3
"""
Pip Voice System — speech-to-text and text-to-speech for the BMO robot.
Handles listening through the USB mic and speaking through the USB speaker.
"""

import os
import sys
import json
import time
import threading
import tempfile
import subprocess

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI not installed. Run: pip3 install openai")
    raise

# --- Configuration ---
CONFIG_FILE = os.path.expanduser("~/bmo-face/pip_brain_config.json")


def load_api_key():
    """Get the OpenAI API key."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            key = config.get("openai_api_key", "")
            if key:
                return key
    return os.environ.get("OPENAI_API_KEY", "")


class PipEars:
    """Speech-to-text using OpenAI Whisper API."""

    def __init__(self, api_key=None):
        self.client = OpenAI(api_key=api_key or load_api_key())
        self.listening = False
        self.sample_rate = 16000
        self.silence_threshold = 500  # Adjust based on mic sensitivity
        self.silence_duration = 1.5   # Seconds of silence before processing
        self.min_audio_length = 0.5   # Minimum seconds of audio to process

    def listen_once(self, duration=5):
        """Record audio for a set duration and transcribe it."""
        audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_path = audio_file.name
        audio_file.close()

        try:
            # Record using arecord (ALSA)
            print("🎤 Listening...")
            subprocess.run([
                "arecord",
                "-D", "default",
                "-f", "S16_LE",
                "-r", str(self.sample_rate),
                "-c", "1",
                "-d", str(duration),
                audio_path
            ], capture_output=True, timeout=duration + 2)

            # Transcribe with Whisper
            return self._transcribe(audio_path)

        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            print(f"🎤 Error: {e}")
            return ""
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    def listen_continuous(self, callback, stop_event=None):
        """
        Continuously listen and call callback(text) when speech is detected.
        Uses voice activity detection to know when to start/stop recording.
        """
        if stop_event is None:
            stop_event = threading.Event()

        self.listening = True
        print("🎤 Continuous listening started...")

        while not stop_event.is_set() and self.listening:
            text = self.listen_once(duration=4)
            if text and text.strip():
                callback(text.strip())
            time.sleep(0.2)  # Brief pause between listens

    def _transcribe(self, audio_path):
        """Transcribe audio file using Whisper API."""
        try:
            with open(audio_path, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="en",
                )
            return result.text
        except Exception as e:
            print(f"🎤 Transcription error: {e}")
            return ""

    def stop(self):
        """Stop listening."""
        self.listening = False


class PipVoice:
    """Text-to-speech using OpenAI TTS API."""

    def __init__(self, api_key=None):
        self.client = OpenAI(api_key=api_key or load_api_key())
        self.voice = "nova"      # Options: alloy, echo, fable, onyx, nova, shimmer
        self.model = "tts-1"     # tts-1 (fast) or tts-1-hd (quality)
        self.speed = 1.0
        self.speaking = False

    def speak(self, text):
        """Convert text to speech and play through speaker."""
        if not text.strip():
            return

        audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        audio_path = audio_file.name
        audio_file.close()

        try:
            self.speaking = True
            print(f"🔊 Speaking: {text[:50]}...")

            # Generate speech
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                speed=self.speed,
            )

            # Save to file
            response.stream_to_file(audio_path)

            # Play through speaker
            self._play_audio(audio_path)

        except Exception as e:
            print(f"🔊 Speech error: {e}")
        finally:
            self.speaking = False
            if os.path.exists(audio_path):
                os.unlink(audio_path)

    def _play_audio(self, audio_path):
        """Play an audio file through the default speaker."""
        try:
            # Try mpv first (best compatibility)
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", audio_path],
                capture_output=True, timeout=30
            )
        except FileNotFoundError:
            try:
                # Fall back to aplay via ffmpeg conversion
                wav_path = audio_path.replace(".mp3", ".wav")
                subprocess.run(
                    ["ffmpeg", "-i", audio_path, "-y", "-loglevel", "quiet", wav_path],
                    capture_output=True, timeout=10
                )
                subprocess.run(
                    ["aplay", wav_path],
                    capture_output=True, timeout=30
                )
                if os.path.exists(wav_path):
                    os.unlink(wav_path)
            except Exception as e:
                print(f"🔊 Playback error: {e}")
                print("   Install mpv: sudo apt install mpv")

    def set_voice(self, voice):
        """Change the TTS voice."""
        valid = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice in valid:
            self.voice = voice
            print(f"🔊 Voice set to: {voice}")
        else:
            print(f"🔊 Invalid voice. Options: {', '.join(valid)}")

    def stop(self):
        """Stop speaking."""
        self.speaking = False


class PipVoiceSystem:
    """Complete voice system — combines ears + voice + brain."""

    def __init__(self, brain=None):
        api_key = load_api_key()
        self.ears = PipEars(api_key=api_key)
        self.voice = PipVoice(api_key=api_key)
        self.brain = brain
        self.running = False
        self.expression_callback = None
        self.stop_event = threading.Event()

    def set_brain(self, brain):
        """Connect the brain for processing heard speech."""
        self.brain = brain

    def set_expression_callback(self, callback):
        """Register face expression callback."""
        self.expression_callback = callback

    def express(self, expression):
        """Change face expression."""
        if self.expression_callback:
            self.expression_callback(expression)

    def start(self):
        """Start the full voice loop: listen → think → speak."""
        self.running = True
        self.stop_event.clear()

        def on_heard(text):
            if not text or not self.brain:
                return

            print(f"\n👂 Heard: {text}")
            self.express("talking")

            # Get response from brain
            reply = self.brain.chat(text)
            print(f"🫧 Pip: {reply}")

            # Speak the response
            self.voice.speak(reply)

            # Return to idle
            time.sleep(0.5)
            self.express("idle")

        # Start listening in a thread
        listen_thread = threading.Thread(
            target=self.ears.listen_continuous,
            args=(on_heard, self.stop_event),
            daemon=True
        )
        listen_thread.start()

        print("🫧 Voice system active! Talk to Pip through the microphone.")
        return listen_thread

    def stop(self):
        """Stop the voice system."""
        self.running = False
        self.stop_event.set()
        self.ears.stop()
        self.voice.stop()
        print("🫧 Voice system stopped.")

    def say(self, text):
        """Manually make Pip say something."""
        self.express("talking")
        self.voice.speak(text)
        self.express("idle")


# --- CLI for testing ---
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pip Voice System")
    parser.add_argument("mode", choices=["listen", "speak", "chat"],
                        help="listen=test mic, speak=test speaker, chat=full voice chat")
    parser.add_argument("--text", type=str, help="Text to speak (for speak mode)")
    parser.add_argument("--voice", type=str, default="nova",
                        help="TTS voice (alloy/echo/fable/onyx/nova/shimmer)")
    args = parser.parse_args()

    if args.mode == "listen":
        ears = PipEars()
        print("🎤 Testing microphone...")
        print("   Speak now (5 seconds)...")
        text = ears.listen_once(duration=5)
        print(f"   Heard: '{text}'")

    elif args.mode == "speak":
        voice = PipVoice()
        voice.set_voice(args.voice)
        text = args.text or "Hi! I'm Pip. Nice to meet you!"
        voice.speak(text)

    elif args.mode == "chat":
        # Import brain
        from pip_brain import PipBrain
        brain = PipBrain()
        voice_system = PipVoiceSystem(brain=brain)

        try:
            voice_system.start()
            print("\nPress Ctrl+C to stop.\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print()
        finally:
            voice_system.stop()


if __name__ == "__main__":
    main()
