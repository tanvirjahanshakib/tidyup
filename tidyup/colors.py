"""Minimal ANSI color helpers — no external dependencies.
Falls back gracefully; colors just won't show on terminals that don't
support ANSI codes (Windows cmd.exe pre-10 mostly), but won't error.
"""

import os
import sys


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


_ENABLED = _supports_color()

_CODES = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "red": "\033[91m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def color(text: str, name: str) -> str:
    if not _ENABLED:
        return text
    return f"{_CODES.get(name, '')}{text}{_CODES['reset']}"
