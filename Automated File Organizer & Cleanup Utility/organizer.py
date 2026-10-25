# -*- coding: utf-8 -*-
"""
organizer.py  -  Automated File Organizer & Cleanup Utility
============================================================
Features
--------
• Scans a cluttered directory (e.g. Downloads) and classifies every file
  by its extension into category folders:
  /Documents  /Images  /Videos  /Audio  /Archives  /Code  (and /Others).
• Category subfolders are created dynamically — only when at least one
  file needs them.
• Relocates files safely with shutil.move():
    – naming collisions are resolved as 'resume (1).pdf', 'resume (2).pdf', …
    – PermissionError / FileNotFoundError are caught per file and reported,
      never crashing the whole run.
• Writes an append-style execution log to 'organizer_log.txt'.
• Prints a formatted execution summary (files relocated per category,
  skipped files, total count).

Usage
-----
    python organizer.py              # prompts for the target directory
    python organizer.py "C:\\path\\to\\folder"
"""

import os
import sys
import io
import shutil
from datetime import datetime
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

# ──────────────────────────────────────────────────────────────────────────────
# Extension → category mapping
# ──────────────────────────────────────────────────────────────────────────────

EXTENSION_MAP = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".csv",
                  ".xlsx", ".xls", ".ppt", ".pptx", ".md", ".odt", ".epub"},
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg",
                  ".webp", ".ico", ".tif", ".tiff", ".heic"},
    "Videos":    {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv",
                  ".webm", ".m4v", ".mpg"},
    "Audio":     {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "Code":      {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css",
                  ".java", ".c", ".cpp", ".h", ".cs", ".json", ".xml", ".yml",
                  ".yaml", ".sh", ".bat", ".ps1", ".sql", ".ipynb"},
}
FALLBACK_CATEGORY = "Others"

# Files this utility must never touch
_SELF_GUARDS = {"organizer.py", "organizer_log.txt", "organizer_log.md"}

_LOG_FILE = Path(__file__).resolve().parent / "organizer_log.txt"


def classify(ext: str) -> str:
    """Return the category folder name for a (lower-case, dotted) extension."""
    for category, extensions in EXTENSION_MAP.items():
        if ext in extensions:
            return category
    return FALLBACK_CATEGORY


def unique_destination(dest_dir: Path, filename: str) -> Path:
    """
    Return a destination path that does not collide with an existing file,
    appending ' (1)', ' (2)', … before the extension when needed.
    """
    candidate = dest_dir / filename
    stem, suffix = candidate.stem, candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = dest_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


# ──────────────────────────────────────────────────────────────────────────────
# Scan + preview
# ──────────────────────────────────────────────────────────────────────────────

def scan_directory(target: Path) -> dict:
    """
    Scan *target* (top level only) and return
    {category: [Path, …]} for every movable file found.
    """
    plan: dict = {}
    with os.scandir(target) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue
            if entry.name.lower() in _SELF_GUARDS:
                continue
            ext = Path(entry.name).suffix.lower()
            category = classify(ext)
            plan.setdefault(category, []).append(target / entry.name)
    return plan


def render_plan(plan: dict) -> int:
    """Print the planned work; return the total file count."""
    total = sum(len(files) for files in plan.values())
    print(bold("  Files found, sorted by destination:\n"))
    for category in plan:
        names = ", ".join(f.name for f in plan[category])
        shown = names if len(names) <= 78 else names[:75] + "…"
        print(f"    {cyan(bold(category + '/')):<12} {len(plan[category]):>3} file(s)  {dim(shown)}")
    if not plan:
        print(dim("    (nothing to organise — directory is already clean!)"))
    print()
    return total


# ──────────────────────────────────────────────────────────────────────────────
# Move engine
# ──────────────────────────────────────────────────────────────────────────────

def log_line(message: str) -> None:
    """Append one timestamped line to organizer_log.txt."""
    with _LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]  {message}\n")


def execute_plan(plan: dict) -> dict:
    """
    Move every planned file into its category folder. Returns stats:
    {'moved': int, 'skipped': int, 'renamed': int, 'per_category': {…}}
    """
    stats = {"moved": 0, "skipped": 0, "renamed": 0, "per_category": {}}

    for category, files in plan.items():
        dest_dir = Path(files[0]).parent / category
        dest_dir.mkdir(exist_ok=True)          # created dynamically, on demand

        per_cat = 0
        for file_path in files:
            destination = unique_destination(dest_dir, file_path.name)
            renamed = destination.name != file_path.name
            try:
                shutil.move(str(file_path), str(destination))
                arrow = dim("→") + f" {destination.name}" if renamed else ""
                print(f"  {green('✔')}  {file_path.name:<44} {dim('→')} {cyan(category + '/')} {arrow}")
                log_line(f"MOVED  {file_path}  →  {destination}")
                per_cat += 1
                stats["moved"] += 1
                if renamed:
                    stats["renamed"] += 1
            except (PermissionError, FileNotFoundError, shutil.Error, OSError) as exc:
                print(f"  {red('✘')}  {file_path.name:<44} {red(f'skipped ({type(exc).__name__})')}")
                log_line(f"SKIPPED  {file_path}  ({type(exc).__name__}: {exc})")
                stats["skipped"] += 1
        stats["per_category"][category] = per_cat

    return stats


def render_summary(target: Path, stats: dict, elapsed: float) -> None:
    """Print the formatted end-of-run execution summary."""
    print()
    print(bold("  " + "═" * 62))
    print(bold(cyan("  EXECUTION SUMMARY")))
    print(bold("  " + "═" * 62))
    print(f"  Target directory      : {bold(str(target))}")
    for category, count in stats["per_category"].items():
        print(f"  {category + '/':<22}: {count:>3} file(s) relocated")
    print()
    print(f"  Total files relocated : {bold(str(stats['moved']))}")
    print(f"  Collisions renamed    : {stats['renamed']}")
    print(f"  Skipped (errors)      : {stats['skipped']}")
    print(f"  Time taken            : {elapsed:.2f} s")
    print(f"  Log file              : {_LOG_FILE.name}")
    print(bold("  " + "═" * 62))
    log_line(f"SUMMARY  moved={stats['moved']}  renamed={stats['renamed']}  "
             f"skipped={stats['skipped']}  target={target}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(bold(cyan("""
  ╔════════════════════════════════════════════════╗
  ║        FILE  ORGANIZER  &  CLEANUP             ║
  ║            U T I L I T Y                       ║
  ╚════════════════════════════════════════════════╝
""")))

    # 1) Pick the target directory
    default_dir = Path.cwd()
    raw = input(bold(f"  Directory to organise (Enter = {default_dir}):\n  → ")).strip().strip('"')
    target = Path(raw) if raw else default_dir

    if not target.is_dir():
        print(red(f"\n  ✘  '{target}' is not a valid directory."))
        sys.exit(1)

    # 2) Preview the plan
    log_line(f"START  scan  target={target}")
    plan = scan_directory(target)
    total = render_plan(plan)
    if total == 0:
        print(green("  Nothing to do — all clean.\n"))
        log_line("ABORT  nothing to move")
        return

    # 3) Confirm before touching anything
    confirm = input(bold(f"  Move {total} file(s) now? (y / n) → ")).strip().lower()
    if confirm != "y":
        print(dim("\n  Cancelled — no files were moved.\n"))
        log_line("ABORT  user cancelled")
        return

    print()
    started = datetime.now()
    stats = execute_plan(plan)
    elapsed = (datetime.now() - started).total_seconds()
    render_summary(target, stats, elapsed)
    print(green(bold("\n  ✔  Organisation complete!\n")))


if __name__ == "__main__":
    main()
