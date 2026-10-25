# Rule-Based Interactive Terminal Assistant / Chatbot

A conversational, rule-based customer-support assistant that runs in your terminal — parses your input with keywords and regular expressions, answers FAQ questions from a JSON dataset, and keeps conversational context.

## How It Works

1. **Dataset loading** — intents come from `sample_faq.json` (greetings + FAQ pairs). If the file is missing or corrupted the bot falls back to built-in defaults (never crashes).
2. **Input normalisation** — every message is lowercased, punctuation is stripped, and extra whitespace collapses before matching (`re.sub`).
3. **Rule-based intent matching** — each FAQ entry gets regex patterns built from keyword *stems* (so `certificate` also matches `certificates`, `working` matches `work`), then the best-scoring intents win.
4. **Multi-intent recognition** — *"hours and certificate please"* returns **both** answers in one reply (up to 3 intents per message, strongest first).
5. **Conversational state** — greeting → intent identification → resolution → exit. The bot remembers the last 3 served topics so `more` repeats recent answers, and greets only once per session.
6. **Graceful fallbacks** — unmatched queries get friendly "I didn't catch that" replies with hints (`topics` command lists everything known).
7. **Clean exit** — `bye`, `exit`, `quit`, `stop` end the session; Ctrl+C / Ctrl+Z are handled as a graceful goodbye too.

## Sample Session

```
  You →  hi
  Bot →  Hello! I'm your rule-based assistant. Ask me about our services, or type 'help'.

  You →  what are your hours of operation?
  Bot →  •  We operate Monday through Friday from 9:00 AM to 6:00 PM IST.

  You →  hours and certificate please
  Bot →  •  We operate Monday through Friday from 9:00 AM to 6:00 PM IST.
         •  Certificates are reviewed and issued within 3-5 business days after your code review.

  You →  my pet dog is purple
  Bot →  I couldn't match any keywords there. Rephrase it, or type 'help'.

  You →  bye
  Bot →  Goodbye! Thanks for chatting with me. 👋
```

## Getting Started

**Requirements:** Python 3 (standard library only — `re`, `json`, `random`)

```bash
git clone https://github.com/Divyanshu11007/Datheon-Python-Internship.git
cd "Datheon-Python-Internship/Rule-Based Interactive Terminal Assistant(Chatbot)"
python chatbot.py
```

## Commands

| Command | What it does |
|---------|--------------|
| *(plain English)* | Freely-asked questions, multi-intent supported |
| `topics` | Lists every FAQ subject the bot knows |
| `more` | Repeats the details of recent answers |
| `help` | Shows the command list |
| `bye` / `exit` / `quit` | Ends the conversation |

## Project Structure

```
Rule-Based Interactive Terminal Assistant(Chatbot)/
├── chatbot.py          # Main script — intent engine + conversation loop
└── sample_faq.json     # FAQ dataset (greetings + question/answer pairs)
```

## Built With

- Python 3 — `re` (regex), `json`, `random`
