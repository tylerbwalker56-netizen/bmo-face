#!/usr/bin/env python3
"""
Pip News — interest tracker + news/topic fetcher.
Learns what Brooks is interested in over time, fetches relevant news,
and prepares conversation topics Pip can bring up naturally.

Uses free APIs (no keys needed):
  - DuckDuckGo Instant Answers
  - Wikipedia snippets
  - RSS feeds from common sources
"""

import os
import json
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime

INTERESTS_FILE = os.path.expanduser("~/bmo-face/pip_interests.json")
NEWS_CACHE_FILE = os.path.expanduser("~/bmo-face/pip_news_cache.json")

# How often to refresh news (seconds)
NEWS_REFRESH_INTERVAL = 3600  # 1 hour

# Free RSS feeds by category
RSS_FEEDS = {
    "tech": [
        "https://hnrss.org/frontpage?count=5",
        "https://feeds.arstechnica.com/arstechnica/index",
    ],
    "gaming": [
        "https://www.gamespot.com/feeds/mashup/",
    ],
    "science": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    ],
    "3d_printing": [
        "https://all3dp.com/feed/",
    ],
    "raspberry_pi": [
        "https://www.raspberrypi.com/feed/",
    ],
    "cars": [
        "https://www.autoblog.com/rss.xml",
    ],
    "ai": [
        "https://hnrss.org/newest?q=AI+OR+LLM&count=5",
    ],
    "general": [
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    ],
}


def fetch_url(url, timeout=10):
    """Fetch a URL and return the text content."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Pip/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def parse_rss_simple(xml_text):
    """Dead-simple RSS parser — no external deps needed."""
    items = []
    if not xml_text:
        return items

    # Find all <item> or <entry> blocks
    import re
    # Try <item> (RSS 2.0)
    item_blocks = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if not item_blocks:
        # Try <entry> (Atom)
        item_blocks = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

    for block in item_blocks[:10]:  # Max 10 items
        title = re.search(r'<title[^>]*>(.*?)</title>', block, re.DOTALL)
        link = re.search(r'<link[^>]*>(.*?)</link>', block, re.DOTALL)
        if not link:
            link = re.search(r'<link[^>]*href="([^"]*)"', block)
        desc = re.search(r'<description[^>]*>(.*?)</description>', block, re.DOTALL)
        if not desc:
            desc = re.search(r'<summary[^>]*>(.*?)</summary>', block, re.DOTALL)

        if title:
            # Clean HTML from text
            title_text = re.sub(r'<[^>]+>', '', title.group(1)).strip()
            title_text = title_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            title_text = title_text.replace('&#39;', "'").replace('&quot;', '"')

            link_text = ""
            if link:
                link_text = re.sub(r'<[^>]+>', '', link.group(1)).strip()

            desc_text = ""
            if desc:
                desc_text = re.sub(r'<[^>]+>', '', desc.group(1)).strip()[:200]
                desc_text = desc_text.replace('&amp;', '&').replace('&lt;', '<')

            items.append({
                "title": title_text,
                "link": link_text,
                "summary": desc_text,
            })

    return items


def ddg_instant(query):
    """DuckDuckGo Instant Answer API — no key needed."""
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        data = fetch_url(url)
        if data:
            result = json.loads(data)
            abstract = result.get("AbstractText", "")
            if abstract:
                return abstract[:300]
            # Try related topics
            topics = result.get("RelatedTopics", [])
            if topics and isinstance(topics[0], dict):
                return topics[0].get("Text", "")[:300]
    except Exception:
        pass
    return None


class PipInterests:
    """Tracks and learns Brooks's interests over time."""

    def __init__(self):
        self.data = self._load()
        self.news_cache = self._load_news_cache()

    def _load(self):
        if os.path.exists(INTERESTS_FILE):
            try:
                with open(INTERESTS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "interests": {
                # Start with known interests from Brooks's profile
                "3d_printing": {"score": 5, "last_mentioned": None},
                "raspberry_pi": {"score": 5, "last_mentioned": None},
                "cars": {"score": 3, "last_mentioned": None},
                "gaming": {"score": 3, "last_mentioned": None},
                "ai": {"score": 4, "last_mentioned": None},
            },
            "keywords": {},  # word -> mention count
            "topics_fetched": [],
            "conversations_prepared": [],
            "last_news_fetch": 0,
        }

    def _save(self):
        os.makedirs(os.path.dirname(INTERESTS_FILE), exist_ok=True)
        with open(INTERESTS_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _load_news_cache(self):
        if os.path.exists(NEWS_CACHE_FILE):
            try:
                with open(NEWS_CACHE_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"articles": [], "fetched_at": 0, "prepared_topics": []}

    def _save_news_cache(self):
        os.makedirs(os.path.dirname(NEWS_CACHE_FILE), exist_ok=True)
        with open(NEWS_CACHE_FILE, "w") as f:
            json.dump(self.news_cache, f, indent=2)

    def learn_from_message(self, message):
        """Extract interest signals from a user message."""
        msg = message.lower()
        words = msg.split()

        # Interest keyword detection
        interest_keywords = {
            "3d_printing": ["3d", "print", "printer", "filament", "pla", "stl", "thingiverse",
                            "cura", "slicer", "nozzle", "bed", "layer"],
            "raspberry_pi": ["raspberry", "pi", "gpio", "hat", "raspbian", "pi5"],
            "cars": ["car", "truck", "engine", "mechanic", "motor", "oil", "brake",
                     "transmission", "wrench", "garage", "tire"],
            "gaming": ["game", "pokemon", "nintendo", "play", "xbox", "ps5",
                       "controller", "steam", "switch"],
            "ai": ["ai", "chatgpt", "llm", "neural", "model", "training", "ollama",
                   "openai", "machine learning"],
            "tech": ["code", "python", "linux", "server", "api", "program", "software",
                     "hardware", "computer", "laptop"],
            "robots": ["robot", "servo", "motor", "sensor", "arduino", "actuator",
                       "lidar", "autonomous"],
            "science": ["space", "nasa", "physics", "chemistry", "biology", "quantum",
                        "experiment"],
        }

        for category, keywords in interest_keywords.items():
            for keyword in keywords:
                if keyword in words or keyword in msg:
                    if category not in self.data["interests"]:
                        self.data["interests"][category] = {"score": 0, "last_mentioned": None}
                    self.data["interests"][category]["score"] += 1
                    self.data["interests"][category]["last_mentioned"] = datetime.now().isoformat()
                    break  # Only count once per category per message

        self._save()

    def get_top_interests(self, n=5):
        """Get Brooks's top N interests by score."""
        interests = self.data["interests"]
        sorted_interests = sorted(interests.items(), key=lambda x: x[1]["score"], reverse=True)
        return sorted_interests[:n]

    def fetch_news(self, force=False):
        """Fetch news articles for Brooks's top interests."""
        now = time.time()
        if not force and now - self.data.get("last_news_fetch", 0) < NEWS_REFRESH_INTERVAL:
            return self.news_cache.get("articles", [])

        print("📰 Fetching news for Brooks's interests...")
        articles = []
        top_interests = self.get_top_interests(3)

        for interest_name, _data in top_interests:
            feeds = RSS_FEEDS.get(interest_name, RSS_FEEDS.get("general", []))
            for feed_url in feeds[:1]:  # One feed per interest
                xml = fetch_url(feed_url)
                items = parse_rss_simple(xml)
                for item in items[:3]:  # Top 3 per feed
                    item["category"] = interest_name
                    articles.append(item)

        self.data["last_news_fetch"] = now
        self.news_cache["articles"] = articles
        self.news_cache["fetched_at"] = now
        self._save()
        self._save_news_cache()

        print(f"📰 Found {len(articles)} articles")
        return articles

    def prepare_conversation_topics(self, ai_client=None):
        """
        Prepare conversation starters based on news + interests.
        If ai_client is available, uses AI to make them conversational.
        """
        articles = self.fetch_news()
        if not articles:
            return []

        topics = []
        used_titles = set()

        for article in articles[:6]:
            if article["title"] in used_titles:
                continue
            used_titles.add(article["title"])

            if ai_client:
                # Use AI to make it conversational
                try:
                    prompt = f"""You are Pip, a curious AI companion. Turn this news headline into
a casual conversation starter for your human Brooks (who likes {article['category']}).
Keep it to 1-2 sentences. Be natural, not newscaster-y.

Headline: {article['title']}
Summary: {article.get('summary', '')}"""

                    response = ai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.9,
                        max_tokens=100,
                    )
                    starter = response.choices[0].message.content.strip()
                    topics.append({
                        "topic": article["title"],
                        "starter": starter,
                        "category": article["category"],
                        "link": article.get("link", ""),
                    })
                except Exception:
                    # Fallback — just use the headline
                    topics.append({
                        "topic": article["title"],
                        "starter": f"Hey, did you see this? {article['title']}",
                        "category": article["category"],
                        "link": article.get("link", ""),
                    })
            else:
                topics.append({
                    "topic": article["title"],
                    "starter": f"Hey, did you see this? {article['title']}",
                    "category": article["category"],
                    "link": article.get("link", ""),
                })

        self.news_cache["prepared_topics"] = topics
        self._save_news_cache()
        return topics

    def get_random_topic(self):
        """Get a random prepared conversation topic."""
        topics = self.news_cache.get("prepared_topics", [])
        if not topics:
            topics = self.prepare_conversation_topics()
        if topics:
            return random.choice(topics)
        return None

    def get_topic_context(self, query):
        """Look up a topic for conversation using DuckDuckGo."""
        result = ddg_instant(query)
        if result:
            return result
        return None

    def get_interests_summary(self):
        """Get a readable summary of Brooks's interests."""
        top = self.get_top_interests(5)
        if not top:
            return "I'm still learning what you're into!"

        lines = ["Here's what I know you're interested in:"]
        for name, data in top:
            score = data["score"]
            label = name.replace("_", " ").title()
            bar = "█" * min(score, 10)
            lines.append(f"  {label}: {bar} ({score})")
        return "\n".join(lines)
