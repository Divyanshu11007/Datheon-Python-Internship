# Hangman Word Guessing Game (Console)

A terminal-based Hangman game written in Python — guess the hidden word letter by letter before you run out of lives!

## How It Works

- A secret word is picked at random from a bundled list of the **10,000 most common English words (no swears)**.
- You guess one letter at a time. Correct letters are revealed in the masked word (e.g. `_ A _ _ H E O N`).
- Every wrong guess brings the little man one step closer to the gallows — the **ASCII art updates** with each miss.
- Duplicate guesses are detected and **not penalized**.

## Difficulty Levels

| Level  | Lives | Gallows Art      |
|--------|-------|------------------|
| Easy   | 8     | 9 stages         |
| Normal | 6     | 7 stages         |
| Hard   | 4     | 5 stages         |

## Features

- Modular, clean code with input validation (single alphabetic characters only)
- Live gallows ASCII art + masked-word display, hearts-based lives bar
- Colour-coded ANSI output (green = hit, red = miss, yellow = warning)
- Clean **VICTORY / GAME OVER** banner screens
- Replay option after each round
- Graceful fallback to a built-in word list if the text file is missing

## Getting Started

**Requirements:** Python 3 (standard library only — no external packages)

```bash
git clone https://github.com/Divyanshu11007/Hangman-game.git
cd Hangman-game
python hangman.py
```

## Project Structure

```
Hangman-game/
├── hangman.py                            # Game source code
├── google-10000-english-no-swears.txt    # Word list used to pick secret words
└── README.md
```

## Built With

- Python 3 — `random`, `os`, `sys`, `io`, `pathlib`
- VS Code / PyCharm

---

*Built as part of the Datheon 4-week program — Task 1: Hangman Word Guessing Game (Console).*
