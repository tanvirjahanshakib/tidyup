"""Command-line interface for tidyup."""

import argparse
import sys
import time
from pathlib import Path

from tidyup import __version__
from tidyup.categories import DEFAULT_CATEGORIES, load_categories, find_project_config
from tidyup.colors import color
from tidyup.organizer import (
    plan_moves,
    execute_moves,
    write_log,
    undo_steps,
    list_history,
    find_duplicates,
    folder_stats,
    find_stale_files,
    clean_empty_folders,
    export_plan,
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tidyup",
        description="Organize a messy folder by file type and/or date.",
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Folder to organize (default: current directory)",
    )
    parser.add_argument(
        "--by",
        choices=["type", "date", "both"],
        default="type",
        help="How to organize files (default: type)",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Also organize files inside subfolders",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to a JSON file defining custom categories (merged with defaults). "
             "If omitted, tidyup looks for a .tidyup.json file inside the target folder.",
    )
    parser.add_argument(
        "--smart-names",
        action="store_true",
        help="Categorize by filename pattern first (e.g. 'Screenshot...', 'invoice...'), "
             "falling back to extension when no pattern matches",
    )
    parser.add_argument(
        "--no-ignore-file",
        action="store_true",
        help="Ignore any .tidyupignore file present in the folder",
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Find duplicate files (by content) instead of organizing",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show a size/count breakdown by category instead of organizing",
    )
    parser.add_argument(
        "--stale",
        metavar="DAYS",
        type=int,
        help="List files not modified in DAYS days (report only, nothing is moved or deleted)",
    )
    parser.add_argument(
        "--clean-empty",
        action="store_true",
        help="Remove empty subfolders left behind after organizing",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch the folder continuously and auto-organize new files as they appear (Ctrl+C to stop)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between checks in --watch mode (default: 5)",
    )
    parser.add_argument(
        "--export-plan",
        metavar="PATH",
        help="Write the planned moves to a JSON file (audit trail) instead of moving files",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would happen without moving any files",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the most recent tidyup run(s) in this folder — see --steps",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1,
        metavar="N",
        help="Number of past runs to undo with --undo (default: 1)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="List past tidyup runs recorded in this folder",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tidyup {__version__}",
    )
    return parser


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def resolve_categories(folder: Path, config_arg):
    """Decide which category mapping to use: explicit --config wins,
    otherwise auto-detect a .tidyup.json inside the folder, otherwise defaults."""
    if config_arg:
        return load_categories(config_arg), config_arg

    auto = find_project_config(folder)
    if auto:
        return load_categories(auto), auto

    return DEFAULT_CATEGORIES, None


def handle_duplicates(folder: Path, recursive: bool) -> int:
    dupes = find_duplicates(folder, recursive=recursive)
    if not dupes:
        print(color("No duplicate files found.", "green"))
        return 0

    total_wasted = 0
    print(color(f"Found {len(dupes)} set(s) of duplicate files:\n", "yellow"))
    for paths in dupes.values():
        original, *copies = paths
        print(f"  {color(str(original), 'cyan')}  (original)")
        for copy in copies:
            size = copy.stat().st_size
            total_wasted += size
            print(f"    {color(str(copy), 'red')}  ({_human_size(size)}, duplicate)")
        print()

    print(f"Total wasted space: {color(_human_size(total_wasted), 'yellow')}")
    print("Tip: review the list above and delete duplicates manually — tidyup never deletes files for you.")
    return 0


def handle_stats(folder: Path, categories: dict, recursive: bool) -> int:
    breakdown = folder_stats(folder, categories=categories, recursive=recursive)
    total = breakdown.pop("_total")

    if total["count"] == 0:
        print(color("Folder is empty.", "green"))
        return 0

    print(color(f"Breakdown of {folder}:\n", "cyan"))
    rows = sorted(breakdown.items(), key=lambda kv: kv[1]["size"], reverse=True)
    for cat, info in rows:
        pct = (info["size"] / total["size"] * 100) if total["size"] else 0
        bar_len = int(pct / 4)
        bar = color("█" * bar_len, "cyan")
        print(f"  {cat:<12} {info['count']:>4} files   {_human_size(info['size']):>8}   {bar} {pct:.0f}%")

    print(f"\n  {'Total':<12} {total['count']:>4} files   {_human_size(total['size']):>8}")
    return 0


def handle_stale(folder: Path, days: int, recursive: bool) -> int:
    stale = find_stale_files(folder, days=days, recursive=recursive)
    if not stale:
        print(color(f"No files older than {days} days.", "green"))
        return 0

    print(color(f"Files not touched in {days}+ days ({len(stale)} found):\n", "yellow"))
    total_size = 0
    for path, age_days in stale:
        size = path.stat().st_size
        total_size += size
        print(f"  {color(str(path), 'cyan')}  ({age_days}d old, {_human_size(size)})")

    print(f"\nTotal size: {color(_human_size(total_size), 'yellow')}")
    print("Tip: review the list above — tidyup only reports stale files, it never deletes them.")
    return 0


def handle_clean_empty(folder: Path, dry_run: bool) -> int:
    removed = clean_empty_folders(folder, dry_run=dry_run)
    if not removed:
        print(color("No empty folders found.", "green"))
        return 0

    prefix = "[DRY RUN] Would remove" if dry_run else "Removed"
    print(color(f"{prefix} {len(removed)} empty folder(s):", "yellow"))
    for path in removed:
        print(f"  {path}")
    return 0


def handle_history(folder: Path) -> int:
    history = list_history(folder)
    if not history:
        print(color("No tidyup runs recorded in this folder.", "green"))
        return 0

    print(color(f"{len(history)} run(s) recorded in {folder} (most recent last):\n", "cyan"))
    for i, entry in enumerate(history, start=1):
        steps_back = len(history) - i + 1
        print(f"  [{steps_back}] {entry['timestamp']}  —  {len(entry['moves'])} file(s) moved")

    print(f"\nRun 'tidyup --undo --steps N' to undo the N most recent runs.")
    return 0


def handle_undo(folder: Path, steps: int) -> int:
    restored, error = undo_steps(folder, steps=steps)
    if error:
        print(color(error, "red"))
        return 1
    print(color(f"Restored {len(restored)} file(s) to their original location ({steps} run(s) undone).", "green"))
    return 0


def run_organize(folder: Path, args, categories: dict, config_source) -> int:
    moves = plan_moves(
        folder,
        by=args.by,
        categories=categories,
        recursive=args.recursive,
        smart_names=args.smart_names,
        use_ignore_file=not args.no_ignore_file,
    )

    if not moves:
        print(color("Nothing to organize — folder is already tidy (or empty).", "green"))
        return 0

    if args.export_plan:
        export_plan(moves, folder, Path(args.export_plan))
        print(color(f"Plan for {len(moves)} file(s) written to {args.export_plan} (no files moved).", "cyan"))
        return 0

    prefix = color("[DRY RUN] ", "yellow") if args.dry_run else ""
    header = f"{prefix}Organizing {len(moves)} file(s) in {folder} (by {args.by})"
    if config_source:
        header += color(f"  [using categories from {config_source}]", "cyan")
    print(header + ":\n")

    for src, dest in moves:
        rel_dest = dest.relative_to(folder)
        print(f"  {src.name}  {color('->', 'cyan')}  {rel_dest}")

    performed = execute_moves(moves, dry_run=args.dry_run)

    if not args.dry_run:
        write_log(folder, performed)
        print(color(f"\nDone. Moved {len(performed)} file(s). Run 'tidyup --undo' to reverse this.", "green"))
    else:
        print(color("\nDry run complete. No files were moved. Remove --dry-run to apply.", "yellow"))

    return 0


def run_watch(folder: Path, args, categories: dict) -> int:
    print(color(f"Watching {folder} — new files will be organized automatically.", "cyan"))
    print(f"Checking every {args.interval}s. Press Ctrl+C to stop.\n")
    try:
        while True:
            moves = plan_moves(
                folder,
                by=args.by,
                categories=categories,
                recursive=args.recursive,
                smart_names=args.smart_names,
                use_ignore_file=not args.no_ignore_file,
            )
            if moves:
                performed = execute_moves(moves, dry_run=False)
                write_log(folder, performed)
                timestamp = time.strftime("%H:%M:%S")
                print(color(f"[{timestamp}] Organized {len(performed)} new file(s):", "green"))
                for src, dest in performed:
                    print(f"  {Path(src).name}  {color('->', 'cyan')}  {Path(dest).relative_to(folder)}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(color("\nStopped watching.", "yellow"))
        return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(color(f"Error: '{folder}' is not a valid directory.", "red"), file=sys.stderr)
        return 1

    if args.history:
        return handle_history(folder)

    if args.undo:
        return handle_undo(folder, steps=args.steps)

    categories, config_source = resolve_categories(folder, args.config)

    if args.duplicates:
        return handle_duplicates(folder, recursive=args.recursive)

    if args.stats:
        return handle_stats(folder, categories=categories, recursive=args.recursive)

    if args.stale is not None:
        return handle_stale(folder, days=args.stale, recursive=args.recursive)

    if args.clean_empty:
        return handle_clean_empty(folder, dry_run=args.dry_run)

    if args.watch:
        return run_watch(folder, args, categories)

    return run_organize(folder, args, categories, config_source)


if __name__ == "__main__":
    sys.exit(main())
