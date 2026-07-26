"""Support for .tidyupignore files — gitignore-style exclude patterns."""

import fnmatch
from pathlib import Path

IGNORE_FILENAME = ".tidyupignore"


def load_ignore_patterns(folder: Path):
    """
    Read patterns from a `.tidyupignore` file in `folder`, if present.
    Blank lines and lines starting with # are skipped. Returns a list
    of glob patterns (fnmatch-style, matched against the file name and
    against the path relative to `folder`).
    """
    ignore_path = folder / IGNORE_FILENAME
    if not ignore_path.exists():
        return []

    patterns = []
    for line in ignore_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def is_ignored(path: Path, folder: Path, patterns) -> bool:
    """Check whether `path` (a file under `folder`) matches any ignore pattern."""
    if not patterns:
        return False

    rel = path.relative_to(folder).as_posix()
    name = path.name

    for pattern in patterns:
        pattern = pattern.rstrip("/")
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
            return True
        # Directory-style pattern ("Photos/") should match anything under that folder
        if any(fnmatch.fnmatch(part, pattern) for part in path.relative_to(folder).parts[:-1]):
            return True

    return False
