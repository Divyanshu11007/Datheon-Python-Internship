# -*- coding: utf-8 -*-
"""
hangman.py  -  Terminal Hangman Game
======================================
Features
--------
• Loads words from 'google-10000-english-no-swears.txt' (same directory).
• Three difficulty levels  →  Easy (8 lives), Normal (6 lives), Hard (4 lives).
• ASCII gallows art that updates with each wrong guess.
• Colour-coded output (ANSI codes; graceful fallback on Windows CMD).
• Tracks correctly guessed letters, wrong guesses, and lives remaining.
• Prevents duplicate-guess penalty.
• Clean victory / defeat screens with option to replay.

Usage
-----
    python hangman.py
"""

import random
import os
import sys
import io
from pathlib import Path

# ── Force UTF-8 output on Windows so Unicode symbols print correctly ──────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers (Forced to True because Colab supports ANSI output escape codes)
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
# ASCII gallows stages (index = number of wrong guesses)
# ──────────────────────────────────────────────────────────────────────────────

_STAGES_8 = [
    # 0 wrong
    r"""
  +-------+
  |       |
  |
  |
  |
  |
  |
=========""",
    # 1
    r"""
  +-------+
  |       |
  |       O
  |
  |
  |
  |
=========""",
    # 2
    r"""
  +-------+
  |       |
  |       O
  |       |
  |
  |
  |
=========""",
    # 3
    r"""
  +-------+
  |       |
  |       O
  |      /|
  |
  |
  |
=========""",
    # 4
    r"""
  +-------+
  |       |
  |       O
  |      /|\
  |
  |
  |
=========""",
    # 5
    r"""
  +-------+
  |       |
  |       O
  |      /|\
  |      /
  |
  |
=========""",
    # 6
    r"""
  +-------+
  |       |
  |       O
  |      /|\
  |      / \
  |
  |
=========""",
    # 7
    r"""
  +-------+
  |       |
  |       O
  |    --/|\
  |      / \
  |
  |
=========""",
    # 8  (dead)
    r"""
  +-------+
  |       |
  |       O
  |    --/|\--
  |      / \
  |
  |
=========""",
]

_STAGES_6 = [_STAGES_8[i] for i in [0, 1, 2, 4, 5, 6, 8]]  # 7 frames for 6 lives
_STAGES_4 = [_STAGES_8[i] for i in [0, 2, 4, 6, 8]]         # 5 frames for 4 lives

# ──────────────────────────────────────────────────────────────────────────────
# Word loading
# ──────────────────────────────────────────────────────────────────────────────

def load_words(min_len: int = 4, max_len: int = 14) -> list:
    """Return a list of words from the bundled word-list file."""
    if "__file__" in globals():
        word_file = Path(__file__).with_name("google-10000-english-no-swears.txt")
    else:
        word_file = Path.cwd() / "google-10000-english-no-swears.txt"

    if not word_file.exists():
        # Friendly fallback – tiny built-in list so the game still runs.
        fallback = [
            "python", "hangman", "keyboard", "monitor", "algorithm",
            "function", "variable", "terminal", "chocolate", "adventure",
        ]
        print(yellow(f"Warning: Word list not found at '{word_file}'.  Using built-in fallback words.\n"))
        return fallback
    with word_file.open(encoding="utf-8") as fh:
        words = [
            w.strip().lower()
            for w in fh
            if min_len <= len(w.strip()) <= max_len and w.strip().isalpha()
        ]
    return words

# ──────────────────────────────────────────────────────────────────────────────
# Game logic helpers
# ──────────────────────────────────────────────────────────────────────────────

DIFFICULTY = {
    "1": ("Easy",   8, _STAGES_8),
    "2": ("Normal", 6, _STAGES_6),
    "3": ("Hard",   4, _STAGES_4),
}


def masked_word(secret: str, guessed: set) -> str:
    """Return the word with un-guessed letters replaced by underscores."""
    return "  ".join(
        green(bold(ch)) if ch in guessed else yellow("_")
        for ch in secret
    )


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def banner() -> None:
    print(cyan(bold("""
  ██╗  ██╗ █████╗ ███╗   ██╗ ██████╗ ███╗   ███╗ █████╗ ███╗   ██╗
  ██║  ██║██╔══██╗████╗  ██║██╔════╝ ████╗ ████║██╔══██╗████╗  ██║
  ███████║███████║██╔██╗ ██║██║  ███╗██╔████╔██║███████║██╔██╗ ██║
  ██╔══██║██╔══██║██║╚██╗██║██║   ██║██║╚██╔╝██║██╔══██║██║╚██╗██║
  ██║  ██║██║  ██║██║ ╚████║╚██████╔╝██║ ╚═╝ ██║██║  ██║██║ ╚████║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
""")))


def draw_state(
    stage_art: str,
    secret: str,
    guessed_correct: set,
    guessed_wrong: set,
    lives: int,
    max_lives: int,
) -> None:
    """Render the full gallows board to stdout."""
    clear()
    banner()

    # Gallows
    for line in stage_art.splitlines():
        print(red(line) if lives < max_lives else dim(line))

    print()
    # Masked word
    print("  Word:   ", masked_word(secret, guessed_correct))
    print()

    # Lives bar
    hearts = "hearts " * lives + dim("heart ") * (max_lives - lives)
    hearts_display = ("♥ " * lives) + (dim("♡ ") * (max_lives - lives))
    colour = green if lives > max_lives // 2 else (yellow if lives > 1 else red)
    print(f"  Lives:  {colour(('♥ ' * lives).strip())}  {dim(('♡ ' * (max_lives - lives)).strip())}  ({lives}/{max_lives})")
    print()

    # Wrong guesses
    if guessed_wrong:
        wrong_str = "  ".join(sorted(guessed_wrong))
        print(f"  Wrong guesses:  {red(wrong_str)}")
    else:
        print(f"  Wrong guesses:  {dim('none yet')}")
    print()


def pick_difficulty():
    """Prompt the user to pick a difficulty level."""
    clear()
    banner()
    print(bold("  Select difficulty:\n"))
    for key, (name, lives, _) in DIFFICULTY.items():
        bar = "♥ " * lives
        print(f"    {cyan(bold(key))}.  {bold(name):8s}  {green(bar.strip())}  ({lives} lives)")
    print()
    while True:
        choice = input(bold("  Enter 1 / 2 / 3 → ")).strip()
        if choice in DIFFICULTY:
            return DIFFICULTY[choice]
        print(red("  Invalid choice – please enter 1, 2, or 3."))


def victory_screen(secret: str, guesses: int) -> None:
    clear()
    print(green(bold("""
  ██╗   ██╗ ██████╗ ██╗   ██╗    ██╗    ██╗ ██████╗ ███╗   ██╗ ██╗
  ╚██╗ ██╔╝██╔═══██╗██║   ██║    ██║    ██║██╔═══██╗████╗  ██║ ██║
   ╚████╔╝ ██║   ██║██║   ██║    ██║ █╗ ██║██║   ██║██╔██╗ ██║ ██║
    ╚██╔╝  ██║   ██║██║   ██║    ██║███╗██║██║   ██║██║╚██╗██║ ╚═╝
     ██║   ╚██████╔╝╚██████╔╝    ╚███╔███╔╝╚██████╔╝██║ ╚████║ ██╗
     ╚═╝    ╚═════╝  ╚═════╝      ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═╝
""")))
    print(green(bold("  " + "*" * 58)))
    print(f"\n  The secret word was: {green(bold(secret.upper()))}")
    print(f"  You solved it in {cyan(bold(str(guesses)))} guess(es).\n")


def defeat_screen(secret: str) -> None:
    clear()
    print(red(bold("""
   ██████╗  █████╗ ███╗   ███╗███████╗    ██████╗ ██╗   ██╗███████╗██████╗ ██╗
  ██╔════╝ ██╔══██╗████╗ ████║██╔════╝   ██╔═══██╗██║   ██║██╔════╝██╔══██╗██║
  ██║  ███╗███████║██╔████╔██║█████╗     ██║   ██║██║   ██║█████╗  ██████╔╝██║
  ██║   ██║██╔══██║██║╚██╔╝██║██╔══╝     ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚═╝
  ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗   ╚██████╔╝ ╚████╔╝ ███████╗██║  ██║██╗
   ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝    ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝╚═╝
""")))
    print(red(bold("  " + "*" * 58)))
    print(f"\n  The word was: {green(bold(secret.upper()))}")
    print(f"  Better luck next time!\n")


# ──────────────────────────────────────────────────────────────────────────────
# Main game loop
# ──────────────────────────────────────────────────────────────────────────────

def play(words: list) -> None:
    """Run one complete round of Hangman."""
    diff_name, max_lives, stages = pick_difficulty()
    secret = random.choice(words)

    guessed_correct = set()
    guessed_wrong   = set()
    lives = max_lives
    total_guesses = 0

    while True:
        wrong_count = len(guessed_wrong)
        art = stages[min(wrong_count, len(stages) - 1)]
        draw_state(art, secret, guessed_correct, guessed_wrong, lives, max_lives)

        # Win check
        if all(ch in guessed_correct for ch in secret):
            victory_screen(secret, total_guesses)
            return

        # Lose check
        if lives <= 0:
            defeat_screen(secret)
            return

        # Prompt
        raw = input(bold("  Guess a letter → ")).strip().lower()

        # Validation
        if len(raw) != 1 or not raw.isalpha():
            print(red("  ✘  Please enter a single letter."))
            input(dim("  (press Enter to continue)"))
            continue

        if raw in guessed_correct or raw in guessed_wrong:
            print(yellow(f"  ⚠  You already guessed '{raw}'.  No penalty."))
            input(dim("  (press Enter to continue)"))
            continue

        total_guesses += 1

        if raw in secret:
            guessed_correct.add(raw)
            new_count = secret.count(raw)
            print(green(f"  ✔  '{raw}' is in the word! ({new_count} occurrence{'s' if new_count > 1 else ''})"))
        else:
            guessed_wrong.add(raw)
            lives -= 1
            print(red(f"  ✘  '{raw}' is not in the word.  {lives} {'life' if lives == 1 else 'lives'} left."))

        input(dim("  (press Enter to continue)"))


def main() -> None:
    words = load_words()
    if not words:
        print(red("Error: no words loaded.  Check the word-list file path."))
        sys.exit(1)

    while True:
        play(words)
        print()
        again = input(bold("  Play again? (yes / no) → ")).strip().lower()
        if again not in ("yes"):
            clear()
            print(cyan(bold("\n  Thanks for playing Hangman!\n")))
            break


if __name__ == "__main__":
    main()
