"""Core logic for planning and executing file organization."""

import json
import shutil
from datetime import datetime
from pathlib import Path

from tidyup.categories import DEFAULT_CATEGORIES, category_for_extension
from tidyup.ignore import load_ignore_patterns, is_ignored
from tidyup.naming_rules import category_for_filename

LOG_FILENAME = ".tidyup_log.json"


def _iter_files(folder: Path, recursive: bool):
    """Yield files directly in `folder`, or recursively if requested.
    Skips hidden files and the tidyup log file."""
    walker = folder.rglob("*") if recursive else folder.iterdir()
    for item in sorted(walker):
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        if item.name == LOG_FILENAME:
            continue
        yield item


def plan_moves(
    folder: Path,
    by: str = "type",
    categories: dict = None,
    recursive: bool = False,
    smart_names: bool = False,
    use_ignore_file: bool = True,
):
    """
    Build a list of (source_path, destination_path) moves for files
    inside `folder` (skips hidden files, the log file itself, and
    files already sitting inside a category/date folder tidyup made).

    by: "type" | "date" | "both"
    recursive: if True, also organize files inside subfolders (their
    original subfolder structure is flattened into the destination).
    smart_names: if True, filename patterns (e.g. "Screenshot...",
    "invoice...") take priority over plain extension matching.
    use_ignore_file: if True, honor a `.tidyupignore` file in `folder`.
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    known_dest_roots = set(categories.keys()) | {"Others"}
    ignore_patterns = load_ignore_patterns(folder) if use_ignore_file else []

    moves = []
    for item in _iter_files(folder, recursive):
        # Skip files that already live inside a folder tidyup created,
        # so re-running tidyup doesn't try to re-sort its own output.
        if recursive and set(p.name for p in item.relative_to(folder).parents) & known_dest_roots:
            continue

        if ignore_patterns and is_ignored(item, folder, ignore_patterns):
            continue

        dest_parts = []

        if by in ("type", "both"):
            cat = None
            if smart_names:
                cat = category_for_filename(item.name)
            if cat is None:
                cat = category_for_extension(item.suffix, categories)
            dest_parts.append(cat)

        if by in ("date", "both"):
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            dest_parts.append(mtime.strftime("%Y-%m"))

        if not dest_parts:
            continue

        dest_dir = folder.joinpath(*dest_parts)
        dest_path = dest_dir / item.name
        moves.append((item, dest_path))

    return moves


def find_duplicates(folder: Path, recursive: bool = False):
    """
    Find duplicate files by content hash (MD5). Returns a dict mapping
    hash -> list of file paths (only entries with 2+ files, i.e. actual
    duplicates). The first file in each list is treated as the
    "original"; the rest are considered duplicates.
    """
    import hashlib

    hashes = {}
    for item in _iter_files(folder, recursive):
        try:
            digest = hashlib.md5(item.read_bytes()).hexdigest()
        except OSError:
            continue
        hashes.setdefault(digest, []).append(item)

    return {h: paths for h, paths in hashes.items() if len(paths) > 1}


def folder_stats(folder: Path, categories: dict = None, recursive: bool = False):
    """
    Return a breakdown of the folder's contents by category:
    {category: {"count": int, "size": int}}, plus a "_total" key with
    the overall count and size. Read-only — moves nothing.
    """
    if categories is None:
        categories = DEFAULT_CATEGORIES

    breakdown = {}
    total_count = 0
    total_size = 0

    for item in _iter_files(folder, recursive):
        cat = category_for_extension(item.suffix, categories)
        size = item.stat().st_size
        entry = breakdown.setdefault(cat, {"count": 0, "size": 0})
        entry["count"] += 1
        entry["size"] += size
        total_count += 1
        total_size += size

    breakdown["_total"] = {"count": total_count, "size": total_size}
    return breakdown


def find_stale_files(folder: Path, days: int, recursive: bool = False):
    """
    Return files that haven't been modified in at least `days` days,
    sorted oldest-first. Each entry is (path, days_since_modified).
    Read-only — never moves or deletes anything.
    """
    now = datetime.now().timestamp()
    threshold_seconds = days * 86400

    stale = []
    for item in _iter_files(folder, recursive):
        age_seconds = now - item.stat().st_mtime
        if age_seconds >= threshold_seconds:
            stale.append((item, int(age_seconds // 86400)))

    stale.sort(key=lambda pair: pair[1], reverse=True)
    return stale


def clean_empty_folders(folder: Path, dry_run: bool = False):
    """
    Remove empty subfolders left behind after organizing (e.g. an
    "Images" folder that's now empty because all its files were moved
    or deleted elsewhere). Only removes folders tidyup itself is aware
    of having created — never touches folders it didn't recognize as
    empty, and never touches the top-level `folder` itself.
    Returns the list of removed folder paths.
    """
    removed = []
    # Walk bottom-up so nested empty folders get removed before their parents.
    for path in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path == folder or not path.is_dir():
            continue
        try:
            is_empty = not any(path.iterdir())
        except OSError:
            continue
        if is_empty:
            removed.append(str(path))
            if not dry_run:
                path.rmdir()

    return removed


def export_plan(moves, folder: Path, path: Path):
    """
    Write the given (src, dest) moves to a JSON file as an audit-trail
    manifest, without moving anything. Useful for review or record-keeping.
    """
    manifest = {
        "generated": datetime.now().isoformat(),
        "folder": str(folder),
        "moves": [
            {"from": str(src), "to": str(dest)} for src, dest in moves
        ],
    }
    Path(path).write_text(json.dumps(manifest, indent=2))
    return path


def execute_moves(moves, dry_run: bool = False):
    """
    Execute a list of (source, destination) moves. Returns the list of
    moves actually performed (useful for logging / undo).
    Skips a move if the destination already exists with the same name
    (renames with a numeric suffix instead of overwriting).
    """
    performed = []
    for src, dest in moves:
        final_dest = dest
        counter = 1
        while final_dest.exists():
            final_dest = dest.with_stem(f"{dest.stem}_{counter}")
            counter += 1

        if not dry_run:
            final_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(final_dest))

        performed.append((str(src), str(final_dest)))

    return performed


def write_log(folder: Path, performed_moves):
    log_path = folder / LOG_FILENAME
    entry = {
        "timestamp": datetime.now().isoformat(),
        "moves": performed_moves,
    }

    history = []
    if log_path.exists():
        try:
            history = json.loads(log_path.read_text())
        except (json.JSONDecodeError, OSError):
            history = []

    history.append(entry)
    log_path.write_text(json.dumps(history, indent=2))


def list_history(folder: Path):
    """Return the full run history (list of {timestamp, moves} entries),
    most recent last. Empty list if no log exists."""
    log_path = folder / LOG_FILENAME
    if not log_path.exists():
        return []
    try:
        return json.loads(log_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def undo_steps(folder: Path, steps: int = 1):
    """
    Reverse the most recent `steps` batches of moves recorded in the
    log file (most recent first). Returns (restored_moves, error).
    restored_moves is a flat list of (from, to) pairs across all
    reversed steps. If fewer than `steps` runs exist, reverses as many
    as are available.
    """
    log_path = folder / LOG_FILENAME
    if not log_path.exists():
        return None, "No tidyup log found in this folder."

    try:
        history = json.loads(log_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, "Could not read the tidyup log file."

    if not history:
        return None, "Nothing to undo."

    steps = max(1, steps)
    restored = []

    for _ in range(min(steps, len(history))):
        entry = history.pop()
        for src, dest in entry["moves"]:
            dest_path = Path(dest)
            src_path = Path(src)
            if dest_path.exists():
                src_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest_path), str(src_path))
                restored.append((dest, src))

    log_path.write_text(json.dumps(history, indent=2))
    return restored, None


def undo_last(folder: Path):
    """Reverse the most recent batch of moves recorded in the log file.
    Kept for backwards compatibility — equivalent to undo_steps(folder, 1)."""
    return undo_steps(folder, steps=1)
