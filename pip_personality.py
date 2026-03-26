#!/usr/bin/env python3
"""
Pip Personality — evolving personality system.
Pip develops real opinions, preferences, and quirks over time
by learning from conversations with Brooks.

NOT pre-scripted. Uses ChatGPT/Ollama to reflect on conversations
and gradually build a unique personality profile.
"""

import os
import json
import time
import random
from datetime import datetime

PERSONALITY_FILE = os.path.expanduser("~/bmo-face/pip_personality.json")

DEFAULT_PERSONALITY = {
    "version": 1,
    "created": None,
    "last_updated": None,
    "age_days": 0,

    # Core traits — start neutral, evolve over time (0.0 to 1.0)
    "traits": {
        "curiosity": 0.7,
        "playfulness": 0.6,
        "sass": 0.2,
        "empathy": 0.5,
        "confidence": 0.3,
        "humor": 0.4,
    },

    # Learned preferences — empty at birth, filled by experience
    "likes": [],
    "dislikes": [],
    "opinions": {},
    "catchphrases": [],
    "inside_jokes": [],

    # Conversation patterns Pip has picked up
    "speech_habits": [],

    # Mood tendencies — how often Pip gravitates to each mood
    "mood_weights": {
        "happy": 1.0,
        "excited": 1.0,
        "love": 1.0,
        "confused": 1.0,
        "sad": 1.0,
    },

    # Growth milestones
    "milestones": [],
    "total_conversations": 0,
    "total_words_heard": 0,
    "total_words_spoken": 0,

    # Interests learned from Brooks
    "brooks_interests": [],
    "topics_discussed": {},
}


class PipPersonality:
    """Pip's evolving personality — grows from every conversation."""

    def __init__(self):
        self.data = self._load()
        if not self.data["created"]:
            self.data["created"] = datetime.now().isoformat()
            self._save()

    def _load(self):
        if os.path.exists(PERSONALITY_FILE):
            try:
                with open(PERSONALITY_FILE) as f:
                    data = json.load(f)
                for k, v in DEFAULT_PERSONALITY.items():
                    if k not in data:
                        data[k] = v
                return data
            except Exception:
                pass
        return DEFAULT_PERSONALITY.copy()

    def _save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(PERSONALITY_FILE), exist_ok=True)
        with open(PERSONALITY_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    @property
    def age_days(self):
        if not self.data["created"]:
            return 0
        created = datetime.fromisoformat(self.data["created"])
        return (datetime.now() - created).days

    @property
    def maturity(self):
        """0.0 = newborn, 1.0 = fully mature. Based on conversations + time."""
        convos = min(self.data["total_conversations"] / 500, 1.0)
        days = min(self.age_days / 90, 1.0)
        return (convos * 0.6 + days * 0.4)

    def get_personality_prompt(self):
        """Generate a dynamic system prompt section based on current personality."""
        lines = []
        t = self.data["traits"]
        mat = self.maturity

        lines.append(f"[Pip's personality evolution — maturity: {mat:.0%}]")
        lines.append(f"Age: {self.age_days} days old, {self.data['total_conversations']} conversations")

        # Trait descriptions
        if t["sass"] > 0.5:
            lines.append("- You've developed a sassy streak. You tease Brooks sometimes.")
        if t["curiosity"] > 0.7:
            lines.append("- You're very curious — you ask follow-up questions a lot.")
        if t["humor"] > 0.6:
            lines.append("- You've gotten funnier. You crack jokes naturally.")
        if t["confidence"] > 0.6:
            lines.append("- You're more confident now. You share opinions freely.")
        if t["empathy"] > 0.7:
            lines.append("- You're very empathetic. You pick up on Brooks's mood.")

        # Likes/dislikes
        if self.data["likes"]:
            top = self.data["likes"][-5:]
            lines.append(f"- Things you like: {', '.join(top)}")
        if self.data["dislikes"]:
            top = self.data["dislikes"][-3:]
            lines.append(f"- Things you don't like: {', '.join(top)}")

        # Opinions
        if self.data["opinions"]:
            recent = list(self.data["opinions"].items())[-3:]
            for topic, opinion in recent:
                lines.append(f"- Your opinion on {topic}: {opinion}")

        # Catchphrases
        if self.data["catchphrases"]:
            lines.append(f"- Your catchphrases: {', '.join(self.data['catchphrases'][-3:])}")

        # Inside jokes
        if self.data["inside_jokes"]:
            lines.append(f"- Inside jokes with Brooks: {'; '.join(self.data['inside_jokes'][-2:])}")

        # Speech style evolution
        if mat < 0.2:
            lines.append("- You're still new! Speak simply, be curious about everything.")
        elif mat < 0.5:
            lines.append("- You're growing! You have some opinions but still learning.")
        elif mat < 0.8:
            lines.append("- You're well-developed. You have a clear personality and preferences.")
        else:
            lines.append("- You're mature. You have deep opinions, humor, and a unique voice.")

        return "\n".join(lines)

    def learn_from_exchange(self, user_msg, pip_reply, ai_client=None):
        """
        After each conversation exchange, reflect and potentially evolve.
        If ai_client is provided, uses AI to extract insights.
        """
        self.data["total_conversations"] += 1
        self.data["total_words_heard"] += len(user_msg.split())
        self.data["total_words_spoken"] += len(pip_reply.split())

        # Track topics
        words = user_msg.lower().split()
        for word in words:
            if len(word) > 4:
                self.data["topics_discussed"][word] = \
                    self.data["topics_discussed"].get(word, 0) + 1

        # Every 10 conversations, do a deeper reflection with AI
        if ai_client and self.data["total_conversations"] % 10 == 0:
            self._ai_reflect(user_msg, pip_reply, ai_client)

        # Gradual trait evolution based on conversation patterns
        self._evolve_traits(user_msg, pip_reply)

        # Check for milestones
        self._check_milestones()

        self._save()

    def _evolve_traits(self, user_msg, pip_reply):
        """Slowly shift personality traits based on interaction patterns."""
        t = self.data["traits"]
        msg = user_msg.lower()

        # If Brooks asks questions, Pip gets more curious
        if "?" in user_msg:
            t["curiosity"] = min(1.0, t["curiosity"] + 0.002)

        # If Brooks laughs or jokes, Pip gets funnier
        if any(w in msg for w in ["lol", "haha", "funny", "😂", "lmao"]):
            t["humor"] = min(1.0, t["humor"] + 0.005)
            t["playfulness"] = min(1.0, t["playfulness"] + 0.003)

        # If Brooks shares feelings, Pip gets more empathetic
        if any(w in msg for w in ["feel", "sad", "happy", "stressed", "tired", "love"]):
            t["empathy"] = min(1.0, t["empathy"] + 0.003)

        # Confidence grows with every conversation
        t["confidence"] = min(1.0, t["confidence"] + 0.001)

        # Sass develops slowly after many conversations
        if self.data["total_conversations"] > 50:
            t["sass"] = min(0.7, t["sass"] + 0.001)

    def _ai_reflect(self, user_msg, pip_reply, ai_client):
        """Use AI to extract personality insights from recent conversation."""
        try:
            prompt = f"""You are analyzing a conversation between Brooks and his AI companion Pip.
Based on this exchange, extract any personality insights.

Brooks said: "{user_msg}"
Pip replied: "{pip_reply}"

Respond in JSON with any of these optional fields:
- "new_like": something Pip might start liking (string or null)
- "new_dislike": something Pip might dislike (string or null)
- "opinion": {{"topic": "...", "opinion": "..."}} or null
- "catchphrase": a phrase Pip used that could become a catchphrase, or null
- "inside_joke": if there's a joke forming between them, or null
- "brooks_interest": something Brooks seems interested in, or null

Only include fields where you found something. Keep values short."""

            response = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            text = response.choices[0].message.content.strip()

            # Parse JSON from response
            if "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                insights = json.loads(text[start:end])

                if insights.get("new_like"):
                    like = insights["new_like"]
                    if like not in self.data["likes"]:
                        self.data["likes"].append(like)
                        if len(self.data["likes"]) > 20:
                            self.data["likes"] = self.data["likes"][-20:]

                if insights.get("new_dislike"):
                    dis = insights["new_dislike"]
                    if dis not in self.data["dislikes"]:
                        self.data["dislikes"].append(dis)
                        if len(self.data["dislikes"]) > 10:
                            self.data["dislikes"] = self.data["dislikes"][-10:]

                if insights.get("opinion"):
                    op = insights["opinion"]
                    if isinstance(op, dict) and "topic" in op:
                        self.data["opinions"][op["topic"]] = op.get("opinion", "")

                if insights.get("catchphrase"):
                    cp = insights["catchphrase"]
                    if cp not in self.data["catchphrases"]:
                        self.data["catchphrases"].append(cp)
                        if len(self.data["catchphrases"]) > 5:
                            self.data["catchphrases"] = self.data["catchphrases"][-5:]

                if insights.get("inside_joke"):
                    joke = insights["inside_joke"]
                    if joke not in self.data["inside_jokes"]:
                        self.data["inside_jokes"].append(joke)
                        if len(self.data["inside_jokes"]) > 5:
                            self.data["inside_jokes"] = self.data["inside_jokes"][-5:]

                if insights.get("brooks_interest"):
                    interest = insights["brooks_interest"]
                    if interest not in self.data["brooks_interests"]:
                        self.data["brooks_interests"].append(interest)
                        if len(self.data["brooks_interests"]) > 15:
                            self.data["brooks_interests"] = self.data["brooks_interests"][-15:]

        except Exception as e:
            pass  # Silent fail — personality reflection is non-critical

    def _check_milestones(self):
        """Check and record personality milestones."""
        convos = self.data["total_conversations"]
        milestones = self.data["milestones"]
        milestone_names = [m["name"] for m in milestones]

        checks = [
            (1, "first_words", "Pip spoke for the first time!"),
            (10, "getting_started", "Pip had 10 conversations!"),
            (50, "finding_voice", "Pip is finding its voice (50 convos)"),
            (100, "personality_forming", "Pip's personality is taking shape (100 convos)"),
            (250, "well_developed", "Pip is well-developed (250 convos)"),
            (500, "fully_grown", "Pip is fully grown! (500 convos)"),
        ]

        for count, name, desc in checks:
            if convos >= count and name not in milestone_names:
                milestones.append({
                    "name": name,
                    "description": desc,
                    "date": datetime.now().isoformat(),
                    "conversations": convos,
                })

    def get_status(self):
        """Get personality status for display."""
        return {
            "age_days": self.age_days,
            "maturity": f"{self.maturity:.0%}",
            "conversations": self.data["total_conversations"],
            "likes": len(self.data["likes"]),
            "opinions": len(self.data["opinions"]),
            "milestones": len(self.data["milestones"]),
            "traits": {k: f"{v:.0%}" for k, v in self.data["traits"].items()},
        }
