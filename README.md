# 🧹 tidyup

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/tanvirjahanshakib/tidyup/actions/workflows/tests.yml/badge.svg)](https://github.com/tanvirjahanshakib/tidyup/actions)

**A smart file organizer for messy folders — available as both a CLI and a point-and-click desktop app. Organizes by type, date, or filename pattern, with duplicate detection, stale-file finding, live watch mode, multi-step undo history, and full audit trails. Zero dependencies.**

```
$ tidyup ~/Downloads --dry-run

[DRY RUN] Organizing 12 file(s) in /Users/you/Downloads (by type):

  resume.pdf         ->  Documents/resume.pdf
  vacation.jpg        ->  Images/vacation.jpg
  installer.exe        ->  Installers/installer.exe
  notes.py             ->  Code/notes.py
  ...

Dry run complete. No files were moved. Remove --dry-run to apply.
```

## Why tidyup?

Every "file organizer" script does the basic type-sorting thing. tidyup goes considerably further:

| Feature                                              | tidyup | most other file organizers |
|--------------------------------------------------------|:------:|:---------------------------:|
| Organize by type / date / both                          | ✅     | ⚠️ usually just type        |
| **One-command undo**                                     | ✅     | ❌ almost never              |
| **Multi-step undo history** (`--history`, `--steps`)      | ✅     | ❌ virtually unheard of       |
| Duplicate detection (MD5)                                | ✅     | ⚠️ sometimes                |
| **Stale-file finder** (`--stale`)                        | ✅     | ❌ almost never              |
| **Space/category stats report** (`--stats`)               | ✅     | ❌ rare                      |
| **Live watch mode** (`--watch`)                          | ✅     | ❌ rare, usually needs extra deps |
| **Empty-folder cleanup** (`--clean-empty`)                | ✅     | ❌ rare                      |
| **Filename-pattern categorization** (`--smart-names`)      | ✅     | ❌ essentially none          |
| **`.tidyupignore` exclude patterns**                      | ✅     | ❌ essentially none          |
| **Auto-loaded per-folder config** (`.tidyup.json`)         | ✅     | ❌ essentially none          |
| **Plan export / audit trail** (`--export-plan`)            | ✅     | ❌ essentially none          |
| Recursive mode                                           | ✅     | ⚠️ sometimes                |
| Safe re-run (won't re-shuffle its own output)             | ✅     | ⚠️ rarely                   |
| Zero external dependencies                                | ✅     | ⚠️ varies                   |
| **Desktop GUI, same engine as the CLI**                    | ✅     | ❌ most CLI organizers have no GUI at all |

## Features

- 📁 **Organize by type, date, or both**
- 🏷️ **Smart filename categorization** — recognizes patterns like `Screenshot...`, `invoice...`, `resume...`, `contract...` and sorts by *what the file actually is*, not just its extension
- 🚫 **`.tidyupignore`** — a gitignore-style file to permanently exclude patterns from a folder
- ⚙️ **Per-folder auto-config** — drop a `.tidyup.json` inside a folder once, and tidyup uses it automatically every time, no flags needed
- 🔁 **Recursive mode** — organize files inside subfolders too
- 👀 **Dry-run mode** — preview before anything moves
- 📝 **Plan export** — write the full move plan to a JSON manifest for review or record-keeping, without touching a single file
- ↩️ **Multi-step undo** — reverse the last run, or the last N runs, with one command
- 📜 **Run history** — `--history` shows every past tidyup run in a folder, with timestamps and file counts
- 🔍 **Duplicate detection** — MD5-based, reports wasted space, never deletes automatically
- 📊 **Stats report** — visual breakdown of what's taking up space, by category
- 🕰️ **Stale-file finder** — surface files you haven't touched in months
- 👁️ **Watch mode** — points at a folder and auto-organizes new files the moment they land, no extra dependencies
- 🧹 **Empty-folder cleanup** — removes leftover empty folders after you've moved things around
- 🧠 **Safe re-run** — running tidyup twice won't re-shuffle files it already organized
- ⚡ **Zero dependencies** — pure Python standard library
- 🔒 **Safe by design** — never overwrites existing files; auto-renames on conflict; duplicates/stale files are only ever reported, never deleted for you

## Installation

```bash
pip install tidyup-cli
```

Or install from source:

```bash
git clone https://github.com/tanvirjahanshakib/tidyup.git
cd tidyup
pip install -e .
```

This installs two commands: `tidyup` (CLI) and `tidyup-gui` (desktop app).

> **Linux users:** the GUI needs Tk, which some distros don't bundle with Python by default. If `tidyup-gui` fails to start, install it once with `sudo apt install python3-tk` (Debian/Ubuntu) or your distro's equivalent. macOS and Windows installs of Python normally already include it. The CLI (`tidyup`) never needs this — it has zero dependencies.

## Desktop app

```bash
tidyup-gui
```

<p align="center"><em>(screenshot — add one after your first run: File → Save Screenshot, or Cmd/Win+Shift+S)</em></p>

A point-and-click window with the same engine as the CLI — pick a folder, choose how to organize it, and click a button. No terminal required.

- **Browse** for a folder, or type/paste a path
- Choose **by type / date / both**, toggle **recursive** and **smart filename categorization**
- **Preview (dry run)** shows exactly what would happen before you commit
- **Organize Now** asks for confirmation, then moves the files
- **Undo Last Run**, **Show History**, **Stats**, **Find Duplicates**, **Find Stale Files**, and **Clean Empty Folders** are all one click away
- **Start Watching** runs the same watch-mode loop as the CLI, right in the window, with live results streaming into the output pane

The GUI is a thin window around the exact same `tidyup/organizer.py` engine the CLI uses — same tests, same guarantees, same `.tidyup_log.json` undo history (a folder organized from the CLI can be undone from the GUI and vice versa).

## CLI Usage

```bash
# Organize the current directory by file type (default)
tidyup

# Organize a specific folder, by date, recursively
tidyup ~/Downloads --by date --recursive

# Use filename-pattern smart categorization (Screenshots, Invoices, Resumes, Contracts...)
tidyup ~/Downloads --smart-names

# Preview changes without moving anything
tidyup ~/Downloads --dry-run

# Export the plan as a JSON manifest instead of moving files
tidyup ~/Downloads --export-plan plan.json

# See what's taking up space, broken down by category
tidyup ~/Downloads --stats

# Find files you haven't touched in 90+ days
tidyup ~/Downloads --stale 90

# Find duplicate files (reports only — never deletes)
tidyup ~/Downloads --duplicates

# Remove empty folders left behind after organizing
tidyup ~/Downloads --clean-empty

# Watch a folder and auto-organize new files as they land
tidyup ~/Downloads --watch

# See every past run in this folder
tidyup ~/Downloads --history

# Undo the last run
tidyup ~/Downloads --undo

# Undo the last 3 runs
tidyup ~/Downloads --undo --steps 3
```

### Options

| Flag                | Description                                             |
|----------------------|-----------------------------------------------------------|
| `folder`             | Folder to organize (default: current directory)           |
| `--by`               | `type`, `date`, or `both` (default: `type`)                 |
| `--recursive, -r`    | Also organize files inside subfolders                       |
| `--smart-names`      | Categorize by filename pattern before falling back to extension |
| `--config PATH`      | JSON file with custom categories (auto-detects `.tidyup.json` in the folder if omitted) |
| `--no-ignore-file`   | Ignore any `.tidyupignore` file present                     |
| `--duplicates`       | Find duplicate files instead of organizing                  |
| `--stats`            | Show a size/count breakdown by category                     |
| `--stale DAYS`       | List files not modified in DAYS days                         |
| `--clean-empty`      | Remove empty subfolders                                      |
| `--watch`            | Continuously watch and auto-organize new files (Ctrl+C to stop) |
| `--interval N`       | Seconds between checks in `--watch` mode (default: 5)         |
| `--export-plan PATH` | Write the plan to a JSON file instead of moving files          |
| `--dry-run, -n`      | Preview changes without moving files                         |
| `--undo`             | Reverse the most recent run(s) — see `--steps`                |
| `--steps N`          | Number of past runs to undo with `--undo` (default: 1)        |
| `--history`          | List past tidyup runs recorded in this folder                  |
| `--version`          | Show version                                                   |

## How undo & history work

Every run appends an entry to a hidden `.tidyup_log.json` file inside the organized folder, recording every move made and when. This gives you:

- `tidyup --undo` — reverse the most recent run
- `tidyup --undo --steps 3` — reverse the 3 most recent runs
- `tidyup --history` — see every run recorded, so you know exactly how far back `--steps` will take you

Safe to run even after closing your terminal or restarting your machine.

## Smart filename categorization

```bash
tidyup ~/Downloads --smart-names
```

Extension alone can't tell a screenshot from a scanned contract — both might be `.png` or `.pdf`. With `--smart-names`, tidyup checks the filename against a set of patterns first:

| Pattern in filename       | Category      |
|-----------------------------|----------------|
| `screenshot`, `cleanshot`   | Screenshots    |
| `invoice`, `receipt`        | Invoices       |
| `resume`, `cv_`             | Resumes        |
| `contract`, `agreement`, `nda` | Contracts   |

Anything that doesn't match a pattern falls back to normal extension-based categorization. See [`tidyup/naming_rules.py`](tidyup/naming_rules.py) to extend the rules.

## Ignoring files: `.tidyupignore`

Drop a `.tidyupignore` file in a folder to permanently exclude patterns (gitignore-style):

```
*.pdf
private_notes.txt
OldBackups/
```

Use `--no-ignore-file` on any run to temporarily disable it.

## Per-folder config: `.tidyup.json`

Instead of passing `--config` every time, drop a `.tidyup.json` file directly in the folder you organize — tidyup finds and uses it automatically:

```json
{
  "Screenshots": [".png"],
  "Contracts": [".pdf", ".docx"]
}
```

An explicit `--config PATH` always takes priority over the auto-detected file. Custom categories are merged with the defaults — if an extension appears in both, your custom category wins.

## Watch mode

```bash
tidyup ~/Downloads --watch --interval 10
```

Polls the folder every `--interval` seconds (default 5) and organizes any new files it finds — no `watchdog` or other OS-level dependency, just the standard library, so it works identically on macOS, Linux, and Windows. Great for a "set and forget" Downloads folder.

## Default categories

| Category    | Extensions (examples)                          |
|-------------|--------------------------------------------------|
| Images      | .jpg .png .gif .svg .webp ...                    |
| Documents   | .pdf .doc .docx .txt .xlsx ...                   |
| Videos      | .mp4 .mov .avi .mkv ...                          |
| Audio       | .mp3 .wav .flac ...                              |
| Archives    | .zip .rar .7z .tar ...                           |
| Code        | .py .js .html .css .java ...                     |
| Installers  | .exe .msi .dmg .apk ...                          |
| Others      | anything that doesn't match above                |

See [`tidyup/categories.py`](tidyup/categories.py) for the full list — PRs to extend the defaults are welcome.

## Running tests

```bash
python -m unittest discover -s tests
```

Covers the CLI/core engine (`tidyup/organizer.py`) directly, plus a headless logic test for the GUI (`tests/test_gui.py`) that stubs out Tk so it runs in CI without a display — it exercises every button's underlying action against real temp files (organize, undo, stats, duplicates, etc.), it just doesn't verify the visual layout, which you should sanity-check locally with `tidyup-gui` after UI changes.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT © [Your Name](LICENSE)
