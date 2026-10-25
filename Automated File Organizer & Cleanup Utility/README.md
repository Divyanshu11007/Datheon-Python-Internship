# Automated File Organizer & Cleanup Utility

A desktop automation utility that organizes cluttered directories (e.g. your **Downloads** folder) — every file is inspected, classified by extension, and safely relocated into category subfolders.

## How It Works

1. You pick a target directory (or just press Enter for the current one).
2. The script **scans every file with `os.scandir()`** and maps its extension to a category.
3. It shows a **preview plan** and asks for confirmation — nothing moves until you say `y`.
4. Category subfolders are **created dynamically**, only when at least one file needs them:

   | Category | Extensions (examples) |
   |----------|----------------------|
   | `Documents/` | `.pdf .docx .txt .csv .xlsx .md` … |
   | `Images/` | `.jpg .png .gif .webp .svg` … |
   | `Videos/` | `.mp4 .mkv .mov .avi` … |
   | `Audio/` | `.mp3 .wav .flac` … |
   | `Archives/` | `.zip .rar .7z .tar .gz` … |
   | `Code/` | `.py .js .html .json .sql` … |
   | `Others/` | anything unrecognized |

5. Moves are performed with **`shutil.move()`** wrapped in `try-except`:
   - **Naming collisions** are auto-resolved → `resume (1).pdf`, `resume (2).pdf`, …
   - **`PermissionError` / missing files** are caught per-file, reported, and skipped — the run never crashes.
6. Every move/skip is appended to **`organizer_log.txt`**, and a **formatted execution summary** prints the per-category and total counts.

## Sample Console Output

```
    Archives/      1 file(s)  backup.zip
    Images/        2 file(s)  image.png, photo.jpg
    Documents/     2 file(s)  report.pdf, resume.pdf
    Code/          1 file(s)  script.py

  ✔  report.pdf            → Documents/
  ✔  photo.jpg             → Images/

  ══════════════════════════════════════════════════════════
  EXECUTION SUMMARY
  ══════════════════════════════════════════════════════════
  Target directory      : C:\Users\...\Downloads
  Documents/            :   2 file(s) relocated
  ...
  Total files relocated : 9
  Collisions renamed    : 1     → report (1).pdf
  Skipped (errors)      : 0
  Time taken            : 0.02 s
```

## Safety Rules

- Never moves folders/directories — only top-level files
- Never touches its own files (`organizer.py`, `organizer_log.txt`)
- Requires explicit `y` confirmation before the first file is moved
- Destination collisions are renamed, never overwritten

## Getting Started

**Requirements:** Python 3 (standard library only — `os`, `shutil`, `pathlib`)

```bash
git clone https://github.com/Divyanshu11007/Datheon-Python-Internship.git
cd "Datheon-Python-Internship/Automated File Organizer & Cleanup Utility"
python organizer.py
# paste any folder path to organise (test it on a copy first!)
```

## Project Structure

```
Automated File Organizer & Cleanup Utility/
├── organizer.py            # Main script — scan, classify, move, log, summary
├── organizer_log.txt       # Append-style execution log (generated each run)
└── shutil — High-level file operations - Python 3.15.1 documentation.html  # Reference doc
```
