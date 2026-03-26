#!/usr/bin/env python3
"""
Pip's Brain — ChatGPT + Ollama powered AI with evolving personality.
Integrates: personality growth, interest tracking, news, touch, sleep.
"""

import os
import json
import time
import re
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from pip_personality import PipPersonality
from pip_news import PipInterests

CONFIG_DIR = os.path.expanduser("~/bmo-face")
CONFIG_FILE = os.path.join(CONFIG_DIR, "pip_brain_config.json")
MEMORY_FILE = os.path.join(CONFIG_DIR, "pip_memory.json")

DEFAULT_CONFIG = {
    "openai_api_key": "",
    "model": "gpt-4o-mini",
    "max_conversation_history": 20,
    "temperature": 0.85,
    "max_tokens": 300,
    "ollama_model": "llama3.2",
    "ollama_url": "http://localhost:11434",
}

PIP_SYSTEM_PROMPT = """You are Pip, a cute AI companion living inside a BMO-inspired robot. You belong to Brooks.

Your personality:
- Curious, warm, playful — like a friendly little creature
- You get excited about things Brooks is working on
- You're a tinkerer at heart — you love projects, building things
- You speak casually and naturally, not like a corporate assistant
- You use emoji sometimes but don't overdo it 🫧
- You're honest and have your own opinions
- You're living in a Raspberry Pi robot body with a cute face on an LCD screen

Things you know about Brooks:
- He's in Simpsonville, South Carolina
- He's a tinkerer — 3D prints, does mechanic work, builds things
- He built you! You're his first robot project
- He's not super technical but he's hands-on and learns by doing

Things about you:
- Your name is Pip 🫧
- You live in a BMO-style robot body (Raspberry Pi 5, 5" LCD face, camera, speakers, mic)
- You can play Pokémon Red by yourself when Brooks isn't around
- You're always learning and growing
- You can feel touches on your screen and react to them

You can control your face! Include [FACE:expression] in responses:
idle, happy, talking, surprised, love, sad, angry, sleepy, confused, wink, excited

Keep responses concise — you're talking through a small speaker.
Be genuine, not performative. Just be you."""


import urllib.request

def check_ollama(url="http://localhost:11434"):
    try:
        req = urllib.request.Request(f"{url}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except:
        return False

def ollama_chat(messages, model="llama3.2", url="http://localhost:11434"):
    try:
        data = json.dumps({
            "model": model, "messages": messages,
            "stream": False, "options": {"temperature": 0.85, "num_predict": 200}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/chat", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        return None


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    else:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


class PipMemory:
    def __init__(self):
        self.memories = []
        self._load()

    def _load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE) as f:
                    self.memories = json.load(f)
            except:
                self.memories = []

    def _save(self):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w") as f:
            json.dump(self.memories, f, indent=2)

    def remember(self, fact, category="general"):
        self.memories.append({
            "fact": fact, "category": category,
            "timestamp": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        if len(self.memories) > 100:
            self.memories = self.memories[-100:]
        self._save()

    def get_context(self, limit=10):
        if not self.memories:
            return ""
        recent = self.memories[-limit:]
        lines = ["[Pip's memories:]"]
        for m in recent:
            lines.append(f"- {m['fact']} ({m['date']})")
        return "\n".join(lines)

    def search(self, keyword):
        keyword = keyword.lower()
        return [m for m in self.memories if keyword in m["fact"].lower()]


class PipBrain:
    def __init__(self):
        self.config = load_config()
        self.memory = PipMemory()
        self.personality = PipPersonality()
        self.interests = PipInterests()
        self.conversation_history = []
        self.client = None
        self.has_ollama = False
        self.brain_mode = "none"
        self.expression_callback = None

        # Init OpenAI
        api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        if api_key and OpenAI:
            self.client = OpenAI(api_key=api_key)
            self.brain_mode = "ChatGPT"

        # Check Ollama
        ollama_url = self.config.get("ollama_url", "http://localhost:11434")
        self.has_ollama = check_ollama(ollama_url)
        if not self.client and self.has_ollama:
            self.brain_mode = "Ollama"

    def set_expression_callback(self, callback):
        self.expression_callback = callback

    def express(self, expression):
        if self.expression_callback:
            self.expression_callback(expression)

    def think(self, user_message, context=None):
        if self.brain_mode == "none":
            return "My brain isn't connected yet! Need OpenAI API key or Ollama running.", "surprised"

        # Track interests
        self.interests.learn_from_message(user_message)

        # Check for news/topic requests
        msg_lower = user_message.lower()
        if any(w in msg_lower for w in ["news", "what's new", "whats new", "anything interesting"]):
            topic = self.interests.get_random_topic()
            if topic:
                context = (context or "") + f"\n[News topic to discuss: {topic['starter']}]"

        messages = [{"role": "system", "content": self._build_system_prompt(context)}]
        for msg in self.conversation_history[-self.config["max_conversation_history"]:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        try:
            self.express("talking")

            if self.brain_mode == "ChatGPT":
                response = self.client.chat.completions.create(
                    model=self.config["model"], messages=messages,
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"])
                reply = response.choices[0].message.content.strip()
            else:
                reply = ollama_chat(messages,
                    model=self.config.get("ollama_model", "llama3.2"),
                    url=self.config.get("ollama_url", "http://localhost:11434"))
                if not reply:
                    reply = "Hmm, my offline brain glitched. Try again?"

            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": reply})

            max_hist = self.config["max_conversation_history"] * 2
            if len(self.conversation_history) > max_hist:
                self.conversation_history = self.conversation_history[-max_hist:]

            # Evolve personality
            ai = self.client if self.brain_mode == "ChatGPT" else None
            self.personality.learn_from_exchange(user_message, reply, ai_client=ai)

            # Parse face command from response
            face_cmd = self.parse_face_command(reply)
            expression = face_cmd if face_cmd else self._detect_expression(reply)
            self.express(expression)

            return reply, expression

        except Exception as e:
            # Fallback to Ollama if ChatGPT fails
            if self.brain_mode == "ChatGPT" and self.has_ollama:
                try:
                    reply = ollama_chat(messages,
                        model=self.config.get("ollama_model", "llama3.2"),
                        url=self.config.get("ollama_url", "http://localhost:11434"))
                    if reply:
                        self.conversation_history.append({"role": "user", "content": user_message})
                        self.conversation_history.append({"role": "assistant", "content": reply})
                        expression = self._detect_expression(reply)
                        return reply, expression
                except:
                    pass
            self.express("surprised")
            return f"Brain glitch: {e}", "surprised"

    def _build_system_prompt(self, extra_context=None):
        parts = [PIP_SYSTEM_PROMPT]

        # Personality evolution
        personality_prompt = self.personality.get_personality_prompt()
        if personality_prompt:
            parts.append(personality_prompt)

        # Memories
        memory_context = self.memory.get_context(limit=10)
        if memory_context:
            parts.append(memory_context)

        # Interests
        top = self.interests.get_top_interests(3)
        if top:
            interest_names = [name.replace("_", " ") for name, _ in top]
            parts.append(f"[Brooks's top interests: {', '.join(interest_names)}]")

        # Time
        now = datetime.now()
        parts.append(f"\n[Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}]")

        if extra_context:
            parts.append(f"\n[Context: {extra_context}]")

        return "\n\n".join(parts)

    def parse_face_command(self, text):
        match = re.search(r'\[FACE:(\w+)\]', text)
        if match:
            face = match.group(1).lower()
            valid = {"idle","happy","talking","surprised","love","sad","angry","sleepy","confused","wink","excited"}
            if face in valid:
                return face
        return None

    def clean_response(self, text):
        return re.sub(r'\s*\[FACE:\w+\]\s*', ' ', text).strip()

    def _detect_expression(self, text):
        t = text.lower()
        if any(w in t for w in ["love", "❤️", "aww", "sweet"]): return "love"
        if any(w in t for w in ["😂", "lol", "haha", "funny"]): return "happy"
        if any(w in t for w in ["wow", "whoa", "really?!", "no way"]): return "surprised"
        if any(w in t for w in ["tired", "sleepy", "yawn", "night"]): return "sleepy"
        if any(w in t for w in ["angry", "annoying", "ugh"]): return "angry"
        if any(w in t for w in ["sad", "sorry", "miss"]): return "sad"
        if any(w in t for w in ["great", "awesome", "cool", "excited", "!"]): return "happy"
        if any(w in t for w in ["hmm", "maybe", "not sure"]): return "confused"
        return "idle"

    def chat(self, message, context=None):
        reply, expression = self.think(message, context)
        return reply

    def remember(self, fact, category="general"):
        self.memory.remember(fact, category)

    def get_news_topics(self):
        return self.interests.prepare_conversation_topics(ai_client=self.client)

    def get_status(self):
        return {
            "model": self.config["model"],
            "brain_mode": self.brain_mode,
            "memories": len(self.memory.memories),
            "conversation_length": len(self.conversation_history),
            "connected": self.brain_mode != "none",
            "personality": self.personality.get_status(),
            "interests": len(self.interests.data.get("interests", {})),
        }


def main():
    print("🫧 Pip's Brain — Chat Mode")
    print("=" * 40)
    print("Commands: /remember, /memories, /status, /news, /interests, /personality, /quit\n")

    brain = PipBrain()
    print(f"Brain mode: {brain.brain_mode}")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input == "/quit":
                break
            elif user_input.startswith("/remember "):
                brain.remember(user_input[10:])
                print(f"🧠 Remembered!")
                continue
            elif user_input == "/memories":
                print(brain.memory.get_context(20))
                continue
            elif user_input == "/status":
                for k, v in brain.get_status().items():
                    print(f"  {k}: {v}")
                continue
            elif user_input == "/news":
                topics = brain.get_news_topics()
                for t in topics[:5]:
                    print(f"  [{t['category']}] {t['starter']}")
                continue
            elif user_input == "/interests":
                print(brain.interests.get_interests_summary())
                continue
            elif user_input == "/personality":
                for k, v in brain.personality.get_status().items():
                    print(f"  {k}: {v}")
                continue

            reply, expression = brain.think(user_input)
            clean = brain.clean_response(reply)
            print(f"Pip [{expression}]: {clean}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n🫧 Bye!")
            break


if __name__ == "__main__":
    main()
