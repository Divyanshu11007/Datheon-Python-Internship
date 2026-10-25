# -*- coding: utf-8 -*-
"""
chatbot.py  -  Rule-Based Interactive Terminal Assistant
=========================================================
Features
--------
• Intent data is loaded from 'sample_faq.json' (greetings + FAQ pairs);
  graceful fallback to built-in defaults if the dataset is missing/broken.
• User input is normalised (lowercase, punctuation stripped, whitespace
  collapsed) and parsed for keywords with regular expressions.
• Rule-based intent matching with scores → supports MULTIPLE intents in a
  single message (e.g. "hours and certificate please" answers both).
• Conversational state management:
  greeting → intent identification → resolution → exit.
  Short conversational memory lets the user ask for "more" about the
  previously served topics.
• Low-confidence (unrecognised) queries get friendly fallback replies with
  hints of known topics.
• Clean exit commands: 'bye', 'exit', 'quit' (+ Ctrl+C / Ctrl+Z handled).

Usage
-----
    python chatbot.py
"""

import json
import random
import re
import sys
import io
from pathlib import Path

# ── Force UTF-8 output on Windows so Unicode symbols print correctly ──────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ──────────────────────────────────────────────────────────────────────────────

_USE_COLOUR = True

def _c(code: str, text: str) -> str:
    """Wrap *text* in an ANSI escape *code* when colour is enabled."""
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def red(t):    return _c("91", t)
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def cyan(t):   return _c("96", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)
def magenta(t):return _c("95", t)

# ──────────────────────────────────────────────────────────────────────────────
# Data loading (with graceful fallback)
# ──────────────────────────────────────────────────────────────────────────────

_DATASET = Path(__file__).with_name("sample_faq.json")

DEFAULT_DATA = {
    "greetings": ["hello", "hi", "hey", "good morning", "good afternoon"],
    "faqs": [
        {"question": "What are your hours of operation?",
         "answer": "We operate Monday through Friday from 9:00 AM to 6:00 PM IST."},
        {"question": "How do I submit my internship project?",
         "answer": "You can submit your public GitHub repository link through your Student Workspace."},
        {"question": "When will I receive my certificate?",
         "answer": "Certificates are reviewed and issued within 3-5 business days after your code review."},
    ],
}


def load_dataset() -> dict:
    """Load the FAQ dataset; fall back to defaults if unavailable/corrupt."""
    try:
        with _DATASET.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("faqs"), list) or not data["faqs"]:
            raise ValueError("no 'faqs' list found")
        if not isinstance(data.get("greetings"), list):
            data["greetings"] = DEFAULT_DATA["greetings"]
        return data
    except FileNotFoundError:
        print(yellow(f"⚠  '{_DATASET.name}' not found — using built-in defaults.\n"))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(yellow(f"⚠  Could not read dataset ({type(exc).__name__}) — using built-in defaults.\n"))
    return DEFAULT_DATA


# ──────────────────────────────────────────────────────────────────────────────
# Intent construction
# ──────────────────────────────────────────────────────────────────────────────

STOPWORDS = {
    "what", "are", "your", "the", "how", "do", "i", "my", "when", "will",
    "is", "a", "an", "of", "to", "for", "in", "on", "and", "you", "get",
    "receive", "tell", "me", "it", "that", "this", "can", "with", "please",
}

def word_stem(word: str) -> str:
    """Naive English stemmer (strip plural / verb endings) for regex matching."""
    for suffix in ("sses", "ies", "ses", "ing", "ers", "er", "ed", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix in ("ies", "ses") else "")
    if len(word) > 4 and word.endswith("e"):
        return word[:-1]
    return word


def topic_label(question: str) -> str:
    """Turn a question into a short topic label, e.g. 'BUSINESS HOURS?'."""
    strip = re.sub(r"^(what|how|when|where|who|why|do|does|is|are)\s+\w*[^\w]*", "", question.lower())
    words = strip.replace("?", "").split()
    keep = [w for w in words if w not in STOPWORDS][:2]
    return " ".join(keep).upper() if keep else question.upper()


def build_intents(data: dict) -> list:
    """
    Compile the intent list:
      • built-in housekeeping intents (greet / thanks / help / exit)
      • one intent per FAQ entry, with keyword-stem regex patterns
    """
    intents = [
        {"name": "GREETING", "reply": "Hello! I'm your rule-based assistant. Ask me about our services, or type 'help'.",
         "patterns": [rf"\b{re.escape(word_stem(g.split()[0]))}\w*\b" for g in data["greetings"]],
         "keywords": set(data["greetings"]), "type": "greeting"},
        {"name": "THANKS", "reply": "You're welcome! Anything else I can help with?",
         "patterns": [r"\bthank(?:s| you)?\b", r"\bthx\b", r"\bty\b"],
         "keywords": {"thanks", "thank"}, "type": "thanks"},
        {"name": "HELP", "reply": ("Available commands:\n"
                                   "  • ask in plain English (e.g. 'what are your hours?')\n"
                                   "  • topics     — list everything I know\n"
                                   "  • more       — repeat details of the last answer\n"
                                   "  • bye / exit / quit — end the chat"),
         "patterns": [r"\bhelp\b", r"\bcommands?\b", r"\bwhat can you do\b"],
         "keywords": {"help"}, "type": "help"},
        {"name": "EXIT", "reply": "", "patterns": [r"\b(bye|goodbye|exit|quit|stop|close)\b"],
         "keywords": {"bye"}, "type": "exit"},
    ]

    extra_hours = re.compile(r"\b(open|timings?|operations?|working)\b", re.I)
    for faq in data["faqs"]:
        question = (faq.get("question") or "").strip()
        answer   = (faq.get("answer") or "").strip()
        keywords = {w for w in re.findall(r"[a-z]+", question.lower()) if w not in STOPWORDS and len(w) > 2}
        patterns = [rf"\b\w*{re.escape(word_stem(kw))}\w*\b" for kw in keywords]
        label = topic_label(question)
        # Extend the hours FAQ with common phrasings ("when are you open?")
        if "hour" in keywords or "timing" in keywords:
            patterns.append(r"\b\w*(hour|timing|operation|open|close|schedul)\w*\b")
        elif extra_hours.search(answer):
            patterns.append(extra_hours.pattern)
        intents.append({
            "name": label, "reply": answer, "patterns": patterns,
            "keywords": keywords, "type": "faq", "question": question,
        })
    return intents


# Compile patterns once for speed
def compile_intents(intents: list) -> None:
    for intent in intents:
        intent["regexes"] = [re.compile(p, re.IGNORECASE) for p in intent["patterns"]]


# ──────────────────────────────────────────────────────────────────────────────
# Matching engine
# ──────────────────────────────────────────────────────────────────────────────

def normalise(text: str) -> str:
    """Lowercase, strip stray punctuation, collapse whitespace."""
    text = re.sub(r"['’`]", "", text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_intents(text: str, intents: list) -> list:
    """
    Score every intent against the input and return strong matches
    sorted by score (multi-intent friendly).
    """
    hits = []
    for intent in intents:
        score = sum(1 for rx in intent["regexes"] if rx.search(text))
        if score:
            hits.append((intent, score))
    hits.sort(key=lambda pair: pair[1], reverse=True)
    return hits[:3]


# ──────────────────────────────────────────────────────────────────────────────
# Conversation loop (state: greeting → identification → resolution → exit)
# ──────────────────────────────────────────────────────────────────────────────

FALLBACKS = [
    "Hmm, I'm not sure I understood that. Try 'topics' to see what I know!",
    "That one's outside my rule set — ask me about submissions, certificates, or hours?",
    "I couldn't match any keywords there. Rephrase it, or type 'help'.",
]

EXIT_REPLIES = [
    "Goodbye! Thanks for chatting with me. 👋",
    "See you later — have a great day!",
]


class ChatSession:
    """Holds conversational state for one user session."""

    def __init__(self, intents: list):
        self.intents  = intents
        self.active   = True           # session on/off (ends on exit intent)
        self.greeted  = False          # has the bot greeted yet?
        self.context  = []             # recently served FAQ intents ("more")
        self.serving  = 0              # messages served

    def respond(self, raw: str) -> str:
        """Process one user message; return the bot's reply text."""
        text = normalise(raw)
        if not text:
            return f"{yellow('[bot]')}  Say something and I'll try my best!"

        if text in ("more", "tell me more", "repeat", "again"):
            if self.context:
                return "\n  ".join(f"{green('•')}  {i['reply']}" for i in self.context)
            return f"{yellow('[bot]')}  Nothing to repeat yet — ask me something first."

        if text in ("topics", "topics list", "topics?"):
            lines = [f"{green('•')}  {i['name']:<12} — {i.get('question', i['name'])}"
                     for i in self.intents if i["type"] in ("faq", "help")]
            return "Here's what I know about:\n  " + "\n  ".join(lines)

        hits = match_intents(text, self.intents)
        if not hits:                                   # ← low-confidence fallback
            return f"{magenta(random.choice(FALLBACKS))}"

        parts = []
        for intent, score in hits:
            kind = intent["type"]
            if kind == "exit":
                self.active = False
                parts.append(green(random.choice(EXIT_REPLIES)))
            elif kind == "greeting":
                if not self.greeted:
                    parts.append(cyan(intent["reply"]))
                    self.greeted = True
            else:
                parts.append(f"{green('•')}  {intent['reply']}")
                if kind == "faq":
                    self.context = [intent] + [i for i in self.context if i is not intent]
                    self.context = self.context[:3]

        self.serving += 1
        return "\n  ".join(p for p in parts if p) or random.choice(FALLBACKS)


def read_line(prompt: str):
    """input() wrapper — Ctrl+C / Ctrl+Z end the session gracefully."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return "bye"


def main() -> None:
    data = load_dataset()
    intents = build_intents(data)
    compile_intents(intents)
    session = ChatSession(intents)

    print(bold(cyan("""
  ╔════════════════════════════════════════════════╗
  ║     RULE-BASED  TERMINAL  ASSISTANT            ║
  ║              ( C H A T B O T )                 ║
  ╚════════════════════════════════════════════════╝
""")))
    print(dim("  Type 'help' for commands, 'topics' to see known subjects.\n"))

    while session.active:
        raw = read_line(bold(f"  {cyan('You')} {dim('→')} "))
        reply = session.respond(raw)
        print(f"  {bold(cyan('Bot'))} {dim('→')}  {reply}\n")

    print(cyan(bold("  Session ended. Goodbye!\n")))


if __name__ == "__main__":
    main()
