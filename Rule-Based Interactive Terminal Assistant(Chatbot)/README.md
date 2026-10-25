# Rule-Based Interactive Terminal Assistant / Chatbot — Advanced Edition

A conversational, rule-based customer-support assistant for the terminal. Parses free-text with regular expressions, tolerates typos, answers several topics at once, and adapts its answers to the real system clock.

## Engine Highlights

### 1. Multi-stage NLP pipeline (stdlib only)
- **Normalisation** — lowercase, punctuation stripped, whitespace collapsed (`re`).
- **Tokenisation + stopword filter** — extracts meaningful keywords.
- **Custom stemmer** — `certificates → certificat`, so one rule covers inflections.
- **Fuzzy typo tolerance** — Levenshtein edit-distance ≤ 2 against keyword-stem variants: *"when is my certficate coming?"* resolves 🡒 `[fuzzy→CERTIFICATE]`.

### 2. Ranked, multi-intent matching
- Every intent is scored (direct hits = 2, fuzzy = 1) and up to **3 intents resolve per message**:
  *"hours and certificate please"* → **both** answers in one reply.
- Each bullet is transparently tagged `[matched: …]` / `[fuzzy→…]`.

### 3. Live business-hours intelligence
The hours answer changes with the real clock (computed via `datetime`):
- *"is it open right now?"* → `OPEN right now — it's 2:31 PM IST…` or `CLOSED — reopens Monday 9:00 AM`
- *"are you open on sunday?"* / *"friday?"* / *"and tomorrow?"* — per-day replies, weekends detected
- Weekday/weekend and today/tomorrow logic handled.

### 4. Conversational state machine
```
greeting ──▶ intent identification ──▶ resolution ──▶ follow-up offer ──▶ exit
             (greet once, time-aware)   (per intent)   (yes / no pending)  (bye/exit/quit)
```
- **Time-of-day greeting** — "Good evening! I'm your rule-based assistant…"
- **Follow-up offers** — after answering, the bot offers a related topic: *"Would you like to know about HOURS OPERATION too? (yes / no)"* → a simple `yes` resolves it; stale offers are cancelled when you pick a topic manually.
- **Context memory** — `more` repeats up to the last 3 served topics (deduplicated).

### 5. Low-confidence fallbacks with transparency
Unmatched input gets a friendly fallback **echoing exactly which words weren't recognised**:
*"my pet dog is purple"* → `I couldn't match any keywords (unrecognised: purple).`

### 6. Robustness & operability
- Dataset loaded from `sample_faq.json`; **missing/corrupt file falls back to defaults** (never crashes); every FAQ row validated.
- `yes`/`no` outside an offer gets a normalising hint, not a fallback.
- Ctrl+C / Ctrl+Z end the session gracefully.
- Full **session transcript log** (`chatbot_log.txt`) + closing **session summary**: messages, matched intents, multi-intent count, fuzzy recoveries, fallbacks, duration.

## Quick Feature Tour

```
  You →  hi
  Bot →  Good evening! I'm your rule-based assistant — ask me anything…

  You →  when is my certficate coming?          (typo, still works)
  Bot →  •  Certificates are reviewed…         [fuzzy→CERTIFICATE]
         Would you like to know about HOURS OPERATION too? (yes / no)

  You →  yes
  Bot →  •  We operate Monday–Friday 9:00 AM – 6:00 PM IST.
         ▸ CLOSED right now — it's 6:14 PM IST. We reopen on Monday at 9:00 AM.

  You →  how about tomorrow?
  Bot →  ▸ Tomorrow (Monday) we operate 9:00 AM – 6:00 PM IST.

  You →  bye
  Bot →  Goodbye! Thanks for chatting with me. 👋
```

## Commands

| Command | What it does |
|---------|--------------|
| *(plain English, typos OK)* | Freely-asked questions — multi-intent supported |
| `are you open on sunday?` / `is it open right now?` / `tomorrow?` | Live clock-aware availability answers |
| `yes` / `no` | Respond to the bot's follow-up offers |
| `topics` | Lists every FAQ subject (numbered) |
| `tell me 2` | Jump straight to a numbered subject |
| `more` | Repeats details of recent answers |
| `help` | Command list |
| `clear` | Wipes the screen |
| `bye` / `exit` / `quit` | Ends the conversation |

## Getting Started

**Requirements:** Python 3 (standard library only — `re`, `json`, `datetime`, `random`)

```bash
git clone https://github.com/Divyanshu11007/Datheon-Python-Internship.git
cd "Datheon-Python-Internship/Rule-Based Interactive Terminal Assistant(Chatbot)"
python chatbot.py
```

## Project Structure

```
Rule-Based Interactive Terminal Assistant(Chatbot)/
├── chatbot.py          # Intent engine, fuzzy matcher, state machine, session log
└── sample_faq.json     # FAQ dataset (greetings + question/answer pairs)
```
