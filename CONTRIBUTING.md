# Contributing to tidyup

Thanks for considering a contribution! 🎉

## Setup

```bash
git clone https://github.com/your-username/tidyup.git
cd tidyup
pip install -e .
```

## Running tests

```bash
python -m unittest discover -s tests
```

Please add or update tests for any behavior change.

## Ideas for contributions

- Interactive mode — confirm each move before it happens
- Export `--stats` / `--duplicates` reports as CSV
- More `--smart-names` patterns (see `tidyup/naming_rules.py`)
- Redo (reverse of undo) support
- Better collision handling strategies
- Windows-specific testing/fixes
- Packaging for Homebrew / Scoop
- Desktop notifications when `--watch` organizes new files
- GUI polish: drag-and-drop a folder onto the window, dark mode, a proper icon, saved recent folders
- GUI: surface `.tidyupignore` / `.tidyup.json` config editing from the window instead of just the CLI

Note: `tidyup/gui.py` is a thin Tk window over the same `tidyup/organizer.py` engine the CLI uses — new organizing features should go in `organizer.py` first, then get wired into both `cli.py` and `gui.py`.

## Pull requests

1. Fork the repo and create a branch from `main`
2. Make your change with a clear, focused commit
3. Make sure tests pass: `python -m unittest discover -s tests`
4. Open a PR with a short description of what and why

## Reporting bugs

Open an issue with:
- What you ran (the exact command)
- What you expected
- What actually happened
- Your OS and Python version

Thanks for helping make tidyup better!
