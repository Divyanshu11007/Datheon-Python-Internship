# -*- coding: utf-8 -*-
"""
chatbot.py  -  Rule-Based Interactive Terminal Assistant (Advanced)
====================================================================
A rule-based conversational assistant with multi-intent recognition.

Engine
------
• Intent dataset loaded from 'sample_faq.json' (graceful built-in fallback
  if the file is missing or corrupted).
• Input normalisation → tokenisation → keyword extraction (stopword filter).
• Ranked intent matching: regex keyword *stems* (custom stemmer) + FUZZY
  edit-distance matching (Levenshtein ≤ 2) so typos still resolve, e.g.
  'certficate' → CERTIFICATE.
• MULTI-INTENT replies: several topics in one message are answered together,
  each bullet showing which intent matched (and when via fuzzy correction).
• LIVE BUSINESS-HOURS logic: the hours answer adapts to the real clock —
  open/closed status right now, per-day questions ('are you open on
  sunday?'), tomorrow availability.
• Conversational state machine:
      greeting → intent identification → resolution → follow-up offer → exit
  Yes/no answers resolve pending offers ('Would you like to know about
  certificates too?'), recent topics are remembered for 'more'.
• Graceful fallbacks echo the words the bot could NOT match.
• Session transcript logged to 'chatbot_log.txt' + closing session summary.
• Clean exit commands: 'bye', 'exit', 'quit', 'stop', plus Ctrl+C / Ctrl+Z.

Usage
-----
    python chatbot.py
"""

import json
import os
import random
import re
import sys
import io
from datetime import datetime
from pathlib import Path

# ── Force UTF-8 output on Windows so Unicode symbols print correctly ──────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
_USE_COLOUR = sys.stdout.isatty() or os.environ.get("FORCE_COLOUR") == "1"

# ──────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ──────────────────────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def red(t):    return _c("91", t)
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def cyan(t):   return _c("96", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("90",  t)
def magenta(t):return _c("95", t)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration & constants
# ──────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_DATASET = _SCRIPT_DIR / "sample_faq.json"
_LOG_FILE = _SCRIPT_DIR / "chatbot_log.txt"

MAX_REPLIES    = 3     # intents resolved per message
CONTEXT_DEPTH  = 3     # topics remembered for 'more'
FUZZY_MAX_DIST = 2     # Levenshtein distance cutoff
FUZZY_MIN_LEN  = 6     # only fuzzy-check reasonably long tokens
OPEN_HOUR      = 9     # business hours (IST)
CLOSE_HOUR     = 18

STOPWORDS = {
    "what", "are", "your", "the", "how", "do", "i", "my", "me", "when", "will",
    "is", "a", "an", "of", "to", "for", "in", "on", "and", "you", "get", "does",
    "receive", "it", "that", "this", "can", "with", "please", "there", "be",
    "about", "so", "from", "was", "am", "could", "would", "any", "at",
}

YES_WORDS = {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "please", "go ahead", "why not"}
NO_WORDS  = {"no", "n", "nope", "nah", "later", "not now", "skip"}

DAY_TOKENS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2,
    "wed": 2, "thursday": 3, "thu": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
    "weekday": 7, "weekdays": 7, "weekend": 8, "today": 9, "tomorrow": 10,
}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

OPEN_WORDS = {"open", "opens", "opened", "closed", "closes", "close", "timing",
              "timings", "working", "schedule", "schedule", "availability"}
OPEN_RE = re.compile(r"\b(open|clos|timing|schedul|availab|operat|hour)\w*", re.I)

EXIT_RE = re.compile(r"^(bye|goodbye|good bye|exit|quit|stop|close|logout|see ya|see you)$", re.IGNORECASE)

AGAIN_RE = re.compile(r"^(?:tell me |topic |number |about )?(\d)$", re.IGNORECASE)

FALLBACKS = [
    "Hmm, I'm not sure I understood that{echo}. Try 'topics' to see what I know!",
    "That's outside my rule set{echo} — ask me about submissions, certificates, or hours?",
    "I couldn't match any keywords{echo}. Rephrase it, or type 'help'.",
]

EXIT_REPLIES = [
    "Goodbye! Thanks for chatting with me. 👋",
    "See you later — have a great day!",
    "Bye! Come back anytime you need help.",
]

THANKS_REPLIES = ["You're welcome!", "Anytime!", "Happy to help!"]

# ──────────────────────────────────────────────────────────────────────────────
# Dataset loading (graceful fallback on any error)
# ──────────────────────────────────────────────────────────────────────────────

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
    """Load FAQ data; on any problem return safe defaults with a warning."""
    try:
        with _DATASET.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data.get("faqs"), list) or not data["faqs"]:
            raise ValueError("no 'faqs' list found")
        if not isinstance(data.get("greetings"), list) or not data["greetings"]:
            data["greetings"] = DEFAULT_DATA["greetings"]
        for faq in data["faqs"]:                       # validate every row
            if not faq.get("question") or not faq.get("answer"):
                raise ValueError("malformed FAQ entry")
        return data
    except FileNotFoundError:
        print(yellow(f"⚠  '{_DATASET.name}' not found — using built-in defaults.\n"))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(yellow(f"⚠  Dataset problem ({type(exc).__name__}: {exc}) — using defaults.\n"))
    return json.loads(json.dumps(DEFAULT_DATA))


# ──────────────────────────────────────────────────────────────────────────────
# Text utilities: normalise, stem, fuzzy distance
# ──────────────────────────────────────────────────────────────────────────────

def normalise(text: str) -> str:
    """Lowercase, drop apostrophes, strip non-alphanumerics, collapse spaces."""
    text = re.sub(r"['’`]", "", text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenise(text: str) -> list:
    """Return meaningful tokens (skip stopwords & 1-2 letter words)."""
    return [t for t in normalise(text).split()
            if t not in STOPWORDS and len(t) > 2]


def word_stem(word: str) -> str:
    """Hand-rolled stemmer: strips plural / inflection endings."""
    if len(word) > 4 and word.startswith("un"):
        return word[2:]
    for suffix, extra in (("sses", "s"), ("ies", "y"), ("ves", "f"),
                          ("ses", ""), ("ing", ""), ("ers", ""),
                          ("er", ""), ("ed", ""), ("s", "")):
        if len(word) > 4 and word.endswith(suffix):
            stem = word[: -len(suffix)]
            return stem + extra
    if len(word) > 4 and word.endswith("e") and not word.endswith("ee"):
        return word[:-1]
    return word


def levenshtein(a: str, b: str) -> int:
    """Edit distance; long length-gaps short-circuit above the fuzzy cutoff."""
    if abs(len(a) - len(b)) > FUZZY_MAX_DIST:
        return FUZZY_MAX_DIST + 1
    prev = list(range(len(b) + 1))
    for char in a:
        cur = [prev[0] + 1]
        for j, other in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (char != other)))
        prev = cur
    return prev[-1]


# ──────────────────────────────────────────────────────────────────────────────
# Business-hours intelligence (dynamic, clock-aware)
# ──────────────────────────────────────────────────────────────────────────────

class BusinessHours:
    """Answers 'open / closed / which day' questions from the system clock."""

    def __init__(self):
        now = datetime.now()
        self.today_idx = now.weekday()                   # 0 = Monday
        self.hour      = now.hour + now.minute / 60
        self.clock     = now.strftime("%I:%M %p").lstrip("0")

    def is_open_now(self) -> bool:
        return self.today_idx <= 4 and OPEN_HOUR <= self.hour < CLOSE_HOUR

    def status(self) -> str:
        """One-line real-time open/closed status."""
        if self.is_open_now():
            return (f"{green('OPEN')} right now — it's {self.clock} IST, "
                    f"support runs until 6:00 PM.")
        if self.today_idx <= 4 and self.hour < OPEN_HOUR:
            return (f"{yellow('CLOSED')} right now — it's {self.clock} IST. "
                    f"We open today at 9:00 AM IST.")
        for add in range(1, 8):
            day = (self.today_idx + add) % 7
            if day <= 4:
                return (f"{yellow('CLOSED')} right now — it's {self.clock} IST. "
                        f"We reopen on {DAY_NAMES[day]} at 9:00 AM IST.")

    def day_answer(self, code: int) -> str:
        """Per-day availability replies (codes: 0-6 days, 7 weekdays, 8 weekend, 9 today, 10 tomorrow)."""
        if code == 7:
            return "On weekdays (Mon–Fri) we're available 9:00 AM – 6:00 PM IST."
        if code == 8:
            return "Weekends (Sat–Sun) are off. Our support team works Monday–Friday only."
        if code == 9:
            return f"Today ({DAY_NAMES[self.today_idx]}) status: {self.status()}"
        if code == 10:
            day = (self.today_idx + 1) % 7
            if day >= 5:
                return (f"Tomorrow is {DAY_NAMES[day]} — closed. "
                        f"Next opening is Monday 9:00 AM IST.")
            return f"Tomorrow ({DAY_NAMES[day]}) we operate 9:00 AM – 6:00 PM IST."
        name = DAY_NAMES[code]
        if code <= 4:
            return f"On {name}s we operate 9:00 AM – 6:00 PM IST."
        return f"We're {red('closed')} on {name}s — support runs Monday–Friday only."


def time_greeting() -> str:
    hour = datetime.now().hour
    phase = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return f"Good {phase}"


# ──────────────────────────────────────────────────────────────────────────────
# Intent construction
# ──────────────────────────────────────────────────────────────────────────────

def topic_label(question: str) -> str:
    """"What are your hours of operation?" → "HOURS OPERATION"."""
    stripped = re.sub(r"^(what|how|when|where|who|why|do|does|is|are)\s+\w*[^\w]*", "", question.lower())
    words = stripped.replace("?", "").split()
    keep = [w for w in words if w not in STOPWORDS][:2]
    return " ".join(keep).upper() if keep else question.upper()


def build_intents(data: dict) -> list:
    """Compile built-in intents + one intent per FAQ entry."""
    intents = [
        {"name": "GREETING", "type": "greeting", "reply": "",
         "patterns": [rf"\b\w*{re.escape(word_stem(g.split()[0]))}\w*\b" for g in data["greetings"]]
                     + [r"\bgood (morning|afternoon|evening)\b"],
         "keywords": {word_stem(g) for g in data["greetings"]}, "stems": set()},
        {"name": "THANKS", "type": "thanks", "reply": "",
         "patterns": [r"\bthank(?:s|you| you)?\b", r"\bthx\b", r"\bappreciate\b"],
         "keywords": {"thank"}, "stems": set()},
        {"name": "HELP", "type": "help", "reply": "",
         "patterns": [r"\bhelp\b", r"\bcommands?\b", r"\bwhat can you do\b", r"\bhow do i (use|start|work)\b"],
         "keywords": {"help", "command"}, "stems": set()},
        {"name": "EXIT", "type": "exit", "reply": "",
         "patterns": [EXIT_RE.pattern], "keywords": {"bye"}, "stems": set()},
    ]

    hours_like = re.compile(r"\b(hour|timing|operation|open|close|schedul)\w*", re.I)
    for faq in data["faqs"]:
        question = faq["question"].strip()
        answer   = faq["answer"].strip()
        keywords = {w for w in re.findall(r"[a-z]+", question.lower())
                    if w not in STOPWORDS and len(w) > 2}
        stems    = {word_stem(kw) for kw in keywords}
        patterns = [rf"\b\w*{re.escape(s)}\w*\b" for s in stems]
        aliases  = faq.get("aliases", []) or []
        alias_stems = {word_stem(w) for w in re.findall(r"[a-z]+", " ".join(aliases).lower())
                       if len(w) > 2} - stems
        patterns += [rf"\b\w*{re.escape(s)}\w*\b" for s in alias_stems]
        stems |= alias_stems
        # Fuzzy targets keep both the stem and its restored-e twins, so a typo
        # chain like certficate → certificat (stem) costs only ONE extra edit.
        fuzzy_stems = stems | {s + "e" for s in stems if len(s) > 4}
        intent = {"name": topic_label(question), "type": "faq", "reply": answer,
                   "patterns": patterns, "keywords": keywords, "stems": stems,
                  "fuzzy_stems": fuzzy_stems,
                  "question": question}
        if any(s in ("hour", "timing", "operat") for s in stems) or hours_like.search(answer):
            intent["is_hours"] = True
            patterns += [r"\b\w*(hour|timing|operation|open|clos|schedul)\w*\b"]
        intents.append(intent)
    return intents


def compile_intents(intents: list) -> None:
    for intent in intents:
        intent["regexes"] = [re.compile(p, re.IGNORECASE) for p in intent["patterns"]]


# ──────────────────────────────────────────────────────────────────────────────
# Semantic matching with scoring + fuzzy recovery
# ──────────────────────────────────────────────────────────────────────────────

def match_intents(text: str, tokens: list, intents: list):
    """
    Score every intent: direct regex hits count 2 (searched on the whole
    normalised text, so short tokens like 'hi' still resolve), fuzzy hits 1.
    Returns (hits, fuzzy_any) with hits = [(intent, score, fuzzy_flag)],
    strongest first, capped at MAX_REPLIES.
    """
    hits = []
    fuzzy_any = False
    for intent in intents:
        direct = any(rx.search(text) for rx in intent["regexes"])
        score = 2 if direct else 0
        fuzzy_hit = False
        if not direct and intent["type"] == "faq":
            for tok in tokens:
                if len(tok) >= FUZZY_MIN_LEN:
                    for stem in intent.get("fuzzy_stems", intent["stems"]):
                        if levenshtein(tok, stem) <= FUZZY_MAX_DIST:
                            score = 1
                            fuzzy_hit = True
                            break
        if score:
            hits.append((intent, score, fuzzy_hit))
            fuzzy_any = fuzzy_any or fuzzy_hit
    hits.sort(key=lambda h: h[1], reverse=True)
    return hits[:MAX_REPLIES], fuzzy_any


# ──────────────────────────────────────────────────────────────────────────────
# Conversation state machine
# ──────────────────────────────────────────────────────────────────────────────

class ChatSession:
    """One user session: greeting → match → resolve → offer → exit."""

    def __init__(self, intents: list):
        self.intents = intents
        self.faqs    = [i for i in intents if i["type"] == "faq"]
        self.active  = True
        self.greeted = False
        self.context: list       = []    # most-recent first (for 'more')
        self.pending: dict|None  = None  # awaiting yes/no follow-up
        self.offered : set       = set()
        self.stats   = {"msgs": 0, "matched": 0, "fallback": 0, "fuzzy": 0, "multi": 0}
        self.started = datetime.now()

    def log(self, speaker: str, text: str) -> None:
        flat = re.sub(r"\033\[[0-9;]*m", "", text).replace("\n", " | ")
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {speaker}: {flat}\n")

    # ── static commands ──────────────────────────────────────────────────
    def cmd_help(self) -> str:
        return ("Available commands:\n"
                "  •  ask in plain English   — e.g. 'what are your hours?' (typos OK)\n"
                "  •  combine topics         — e.g. 'hours and certificate please'\n"
                "  •  are you open on sunday?  /  is it open right now?  /  and tomorrow?\n"
                "  •  topics                 — list everything I know\n"
                "  •  more                   — repeat details of recent answers\n"
                "  •  tell me 2              — jump to a numbered topic\n"
                "  •  yes / no               — respond to my follow-up suggestions\n"
                "  •  clear                  — wipe the screen\n"
                "  •  bye / exit / quit      — end the session")

    def cmd_topics(self) -> str:
        rows = [f"{green(f'{n + 1}.')} {bold(i['name']):<22} {dim(i['question'])}"
                for n, i in enumerate(self.faqs)]
        return ("Here's everything I know about:\n  " + "\n  ".join(rows) +
                "\n" + dim("  Tip: pick a number ('tell me 2') or just describe your question."))

    def cmd_more(self) -> str:
        if not self.context:
            return yellow("Nothing to repeat yet — ask me something first.")
        return "\n  ".join(f"{green('•')}  {i['reply']}" for i in self.context)

    # ── dynamic answer richness ──────────────────────────────────────────
    def render_faq(self, intent: dict) -> str:
        if intent.get("is_hours"):
            return f"{intent['reply']}\n  {green('▸')} {BusinessHours().status()}"
        return intent["reply"]

    def related_offer(self, intent: dict):
        """Suggest one other FAQ as a conversational follow-up."""
        candidates = []
        for other in self.faqs:
            if other is intent or other["name"] in self.offered \
               or other["name"] in {c["name"] for c in self.context}:
                continue
            related = bool(other["stems"] & intent["stems"])
            candidates.append((related, other))
        candidates.sort(key=lambda c: not c[0])     # keyword-related first
        matched = [c[1] for c in candidates if c[0]]
        if not matched and candidates:
            matched = [candidates[0][1]]
        if not matched:
            self.pending = None
            return None
        other = matched[0]
        self.offered.add(other["name"])
        self.pending = {"intent": other}
        return (f"{yellow('Would you like to know about ')}{yellow(bold(other['name']))}"
                f"{yellow(' too? (yes / no)')}")

    def resolve_pending(self, say_yes: bool) -> str:
        pending, self.pending = self.pending, None
        if not (say_yes and pending):
            return dim("Okay — ask me anything else, or type 'topics'.")
        intent = pending["intent"]
        self.context.insert(0, intent)
        self.context = self.context[:CONTEXT_DEPTH]
        return f"{green('•')}  {self.render_faq(intent)}"

    # ── fallback with transparency ───────────────────────────────────────
    def fallback(self, tokens: list) -> str:
        self.stats["fallback"] += 1
        known = {t for i in self.intents for t in i["stems"]}
        unknown = [t for t in tokens if t not in known and len(t) > 3][:4]
        echo = f" (unrecognised: {', '.join(unknown)})" if unknown else ""
        return magenta(random.choice(FALLBACKS).format(echo=yellow(echo)))

    # ── main entry point per message ─────────────────────────────────────
    def respond(self, raw: str) -> str:
        self.stats["msgs"] += 1
        text = normalise(raw)

        if text == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            return dim("  (screen cleared)")

        if not text:
            return yellow("Say something and I'll try my best!")

        if EXIT_RE.match(text):
            self.active = False
            return green(random.choice(EXIT_REPLIES))

        if text in ("help", "commands", "options"):
            self.stats["matched"] += 1
            return self.cmd_help()
        if text in ("topics", "topics list"):
            self.stats["matched"] += 1
            return self.cmd_topics()
        if text in ("more", "tell me more", "repeat", "again", "anything else"):
            self.stats["matched"] += 1
            return self.cmd_more()

        tokens = tokenise(text)

        # pending yes/no flow (offers made by the bot)
        if self.pending and (text in YES_WORDS or text in NO_WORDS):
            self.stats["matched"] += 1
            return self.resolve_pending(say_yes=text in YES_WORDS)

        # yes/no without a pending offer → gentle nudge
        if text in YES_WORDS or text in NO_WORDS:
            return dim("Yes/no only applies to my follow-up questions — "
                       "just ask me anything, or type 'topics'.")

        # numbered topic shortcut: 'tell me 2'
        num = AGAIN_RE.match(text)
        idx = int(num.group(1)) - 1 if num else None
        if num and 0 <= idx < len(self.faqs):
            intent = self.faqs[idx]
            self.pending = None               # manual pick cancels a stale offer
            self.context.insert(0, intent)
            self.context = self.context[:CONTEXT_DEPTH]
            self.stats["matched"] += 1
            return f"{green(f'[{idx + 1}]')}  {self.render_faq(intent)}"

        hits, fuzzy_any = match_intents(text, tokens, self.intents)
        if fuzzy_any:
            self.stats["fuzzy"] += 1

        # day-based availability questions ('are you open on sunday?', 'tomorrow?')
        days = [DAY_TOKENS[t] for t in tokens if t in DAY_TOKENS]
        if days:
            self.stats["matched"] += 1
            parts = [f"{green('▸')} {BusinessHours().day_answer(d)}" for d in days[:2]]
            # a FAQ hit about a *different* topic may still be worth showing
            other = [(i, f) for i, s, f in hits if i["type"] == "faq" and not i.get("is_hours")]
            for intent, fuzzy in other:
                tag = (dim(f"  [fuzzy→{intent['name']}]") if fuzzy
                       else dim(f"  [matched: {intent['name']}]"))
                parts.append(f"{self.render_faq(intent)}{tag}")
            return f"{green('•')}  " + "\n  ".join(p if p.startswith("▸") else f"{green('•')}  {p}" for p in parts[:3])

        if not hits:
            return self.fallback(tokens)

        self.stats["matched"] += 1
        if len(hits) > 1:
            self.stats["multi"] += 1

        parts = []
        faq_hit = None
        for intent, score, fuzzy in hits:
            kind = intent["type"]
            if kind == "exit":
                self.active = False
                parts.append(green(random.choice(EXIT_REPLIES)))
                continue
            if kind == "greeting":
                if not self.greeted:
                    greet = time_greeting() + random.choice(
                        ["! I'm your rule-based assistant — ask me anything, or type 'help'.",
                         "! I can answer FAQ questions, check opening hours, and more. Type 'help'.",
                         f"! Ask me about our services — try 'topics' to see the known subjects."])
                    parts.append(cyan(greet))
                    self.greeted = True
                continue
            if kind == "thanks":
                parts.append(f"{green(random.choice(THANKS_REPLIES))} {dim('Anything else?')}")
                continue
            if kind == "help":
                if len(hits) > 1:
                    continue          # casual 'thanks for the help' — don't dump the menu
            self.context.insert(0, intent)
            self.context = self.context[:CONTEXT_DEPTH]
            tag  = (dim(f"  [fuzzy→{intent['name']}]") if fuzzy
                    else dim(f"  [matched: {intent['name']}]"))
            parts.append(f"{green('•')}  {self.render_faq(intent)}{tag}")
            faq_hit = faq_hit or (intent, fuzzy)

        reply = "\n  ".join(parts)
        if faq_hit and len(hits) == 1:
            offer = self.related_offer(faq_hit[0])
            if offer:
                reply += f"\n  {offer}"
        return reply

    def summary(self) -> str:
        secs = (datetime.now() - self.started).total_seconds()
        s = self.stats
        return (f"Session summary: {s['msgs']} msgs • {s['matched']} matched • "
                f"{s['multi']} multi-intent • {s['fuzzy']} fuzzy • "
                f"{s['fallback']} fallbacks • {secs:.0f}s")


# ──────────────────────────────────────────────────────────────────────────────
# CLI driver
# ──────────────────────────────────────────────────────────────────────────────

def read_line(prompt: str) -> str:
    """input() wrapper so Ctrl+C / Ctrl+Z end things gracefully."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return "bye"


def main() -> None:
    data    = load_dataset()
    intents = build_intents(data)
    compile_intents(intents)
    session = ChatSession(intents)

    print(bold(cyan("""
  ╔════════════════════════════════════════════════╗
  ║     RULE-BASED  TERMINAL  ASSISTANT            ║
  ║        A D V A N C E D   E D I T I O N         ║
  ╚════════════════════════════════════════════════╝
""")))
    print(dim("  Typo-tolerant matching • multi-intent • live business hours • context memory\n"))
    print(dim("  Type 'help' for commands, 'topics' to list known subjects.\n"))
    session.log("SESSION", "started")

    while session.active:
        raw = read_line(bold(f"  {cyan('You')} {dim('→')} "))
        reply = session.respond(raw)
        print(f"  {bold(cyan('Bot'))} {dim('→')}  {reply}\n")
        session.log("You", raw)
        session.log("Bot", reply)

    session.log("SESSION", f"ended — {session.summary()}")
    print(cyan(bold("  " + session.summary() + "\n")))


if __name__ == "__main__":
    main()
