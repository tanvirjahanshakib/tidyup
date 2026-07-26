"""
Desktop GUI for tidyup, built with CustomTkinter.

Run with:  tidyup-gui
or:        python -m tidyup.gui
"""

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from tidyup import __version__
from tidyup.categories import DEFAULT_CATEGORIES, load_categories, find_project_config
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
)

# CustomTkinter থিম ও ডার্ক মোড সেটআপ
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


class TidyupApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"tidyup {__version__}")
        self.root.geometry("800x680")
        self.root.minsize(700, 550)

        self.folder_var = tk.StringVar()
        self.by_var = tk.StringVar(value="type")
        self.recursive_var = tk.BooleanVar(value=False)
        self.smart_names_var = tk.BooleanVar(value=False)
        self.stale_days_var = tk.StringVar(value="90")

        self._watch_thread = None
        self._watch_stop_event = threading.Event()

        self._build_layout()

    # ---------- layout ----------

    def _build_layout(self):
        pad = {"padx": 12, "pady": 8}

        # 1. Folder Selection Frame
        folder_frame = ctk.CTkFrame(self.root)
        folder_frame.pack(fill="x", **pad)

        ctk.CTkLabel(folder_frame, text="Folder:", font=("Segoe UI", 13, "bold")).pack(side="left", padx=(10, 5))
        entry = ctk.CTkEntry(folder_frame, textvariable=self.folder_var, placeholder_text="Select directory to clean...")
        entry.pack(side="left", fill="x", expand=True, padx=6, pady=8)
        ctk.CTkButton(folder_frame, text="Browse...", width=90, command=self._browse_folder).pack(side="left", padx=(0, 10))

        # 2. Options Frame
        options_frame = ctk.CTkFrame(self.root)
        options_frame.pack(fill="x", **pad)

        ctk.CTkLabel(options_frame, text="Organize by:", font=("Segoe UI", 12)).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        by_combo = ctk.CTkOptionMenu(
            options_frame,
            variable=self.by_var,
            values=["type", "date", "both"],
            width=110
        )
        by_combo.grid(row=0, column=1, sticky="w", padx=6, pady=8)

        ctk.CTkSwitch(
            options_frame, text="Include subfolders (recursive)", variable=self.recursive_var
        ).grid(row=0, column=2, sticky="w", padx=15, pady=8)

        ctk.CTkSwitch(
            options_frame, text="Smart filename categorization", variable=self.smart_names_var
        ).grid(row=0, column=3, sticky="w", padx=15, pady=8)

        # 3. Actions Frame
        actions_frame = ctk.CTkFrame(self.root)
        actions_frame.pack(fill="x", **pad)

        row1 = ctk.CTkFrame(actions_frame, fg_color="transparent")
        row1.pack(fill="x", pady=4, padx=6)
        ctk.CTkButton(row1, text="Preview (dry run)", fg_color="#4A5568", hover_color="#2D3748", command=self.action_preview).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="Organize Now", fg_color="#2B6CB0", hover_color="#2C5282", command=self.action_organize).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="Undo Last Run", fg_color="#C53030", hover_color="#9B2C2C", command=self.action_undo).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="Show History", fg_color="#4A5568", hover_color="#2D3748", command=self.action_history).pack(side="left", padx=4)

        row2 = ctk.CTkFrame(actions_frame, fg_color="transparent")
        row2.pack(fill="x", pady=4, padx=6)
        ctk.CTkButton(row2, text="Stats", command=self.action_stats).pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Find Duplicates", command=self.action_duplicates).pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Clean Empty Folders", command=self.action_clean_empty).pack(side="left", padx=4)

        row3 = ctk.CTkFrame(actions_frame, fg_color="transparent")
        row3.pack(fill="x", pady=4, padx=6)
        ctk.CTkLabel(row3, text="Stale after (days):").pack(side="left", padx=(4, 2))
        ctk.CTkEntry(row3, textvariable=self.stale_days_var, width=60).pack(side="left")
        ctk.CTkButton(row3, text="Find Stale Files", command=self.action_stale).pack(side="left", padx=8)

        self.watch_button = ctk.CTkButton(
            row3, text="Start Watching", fg_color="#2F855A", hover_color="#22543D", command=self.toggle_watch
        )
        self.watch_button.pack(side="left", padx=8)

        # 4. Output / Console Frame
        output_frame = ctk.CTkFrame(self.root)
        output_frame.pack(fill="both", expand=True, **pad)

        ctk.CTkLabel(output_frame, text="Activity Log", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(6, 2))

        self.output = ctk.CTkTextbox(output_frame, wrap="word", font=("Consolas", 11))
        self.output.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.output.configure(state="disabled")

        # 5. Status Bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ctk.CTkLabel(self.root, textvariable=self.status_var, anchor="w", fg_color="#1A202C", text_color="#A0AEC0", height=24)
        status_bar.pack(fill="x", side="bottom")

    # ---------- helpers ----------

    def _browse_folder(self):
        chosen = filedialog.askdirectory()
        if chosen:
            self.folder_var.set(chosen)

    def _get_folder(self):
        raw = self.folder_var.get().strip()
        if not raw:
            messagebox.showwarning("No folder selected", "Please choose a folder first.")
            return None
        folder = Path(raw).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("Invalid folder", f"'{folder}' is not a valid directory.")
            return None
        return folder

    def _get_categories(self, folder: Path):
        auto = find_project_config(folder)
        if auto:
            try:
                return load_categories(auto), auto
            except (OSError, ValueError):
                pass
        return DEFAULT_CATEGORIES, None

    def _log(self, text: str, clear: bool = False):
        self.output.configure(state="normal")
        if clear:
            self.output.delete("1.0", "end")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _set_status(self, text: str):
        self.status_var.set(f"  Status: {text}")

    # ---------- actions ----------

    def action_preview(self):
        folder = self._get_folder()
        if not folder:
            return
        categories, source = self._get_categories(folder)
        moves = plan_moves(
            folder,
            by=self.by_var.get(),
            categories=categories,
            recursive=self.recursive_var.get(),
            smart_names=self.smart_names_var.get(),
        )

        header = f"[PREVIEW] {len(moves)} file(s) would be organized in {folder}"
        if source:
            header += f"  (using categories from {source})"
        self._log(header, clear=True)

        if not moves:
            self._log("Nothing to organize — folder is already tidy (or empty).")
        else:
            for src, dest in moves:
                self._log(f"  {src.name}  ->  {dest.relative_to(folder)}")
        self._set_status(f"Preview: {len(moves)} file(s) would move.")

    def action_organize(self):
        folder = self._get_folder()
        if not folder:
            return
        categories, source = self._get_categories(folder)
        moves = plan_moves(
            folder,
            by=self.by_var.get(),
            categories=categories,
            recursive=self.recursive_var.get(),
            smart_names=self.smart_names_var.get(),
        )

        if not moves:
            self._log("Nothing to organize — folder is already tidy (or empty).", clear=True)
            self._set_status("Nothing to organize.")
            return

        if not messagebox.askyesno(
            "Confirm organize",
            f"Move {len(moves)} file(s) in {folder}?\n\nThis can be undone with 'Undo Last Run'.",
        ):
            return

        performed = execute_moves(moves, dry_run=False)
        write_log(folder, performed)

        self._log(f"Organized {len(performed)} file(s) in {folder}:", clear=True)
        for src, dest in performed:
            self._log(f"  {Path(src).name}  ->  {Path(dest).relative_to(folder)}")
        self._set_status(f"Done. Moved {len(performed)} file(s).")

    def action_undo(self):
        folder = self._get_folder()
        if not folder:
            return
        restored, error = undo_steps(folder, steps=1)
        if error:
            self._log(error, clear=True)
            self._set_status(error)
            return
        self._log(f"Restored {len(restored)} file(s) to their original location.", clear=True)
        self._set_status(f"Undo complete: {len(restored)} file(s) restored.")

    def action_history(self):
        folder = self._get_folder()
        if not folder:
            return
        history = list_history(folder)
        self._log(f"Run history for {folder}:", clear=True)
        if not history:
            self._log("  No tidyup runs recorded in this folder.")
        else:
            for i, entry in enumerate(history, start=1):
                steps_back = len(history) - i + 1
                self._log(f"  [{steps_back}] {entry['timestamp']}  —  {len(entry['moves'])} file(s) moved")
        self._set_status(f"{len(history)} run(s) recorded.")

    def action_stats(self):
        folder = self._get_folder()
        if not folder:
            return
        categories, _ = self._get_categories(folder)
        breakdown = folder_stats(folder, categories=categories, recursive=self.recursive_var.get())
        total = breakdown.pop("_total")

        self._log(f"Breakdown of {folder}:", clear=True)
        if total["count"] == 0:
            self._log("  Folder is empty.")
        else:
            rows = sorted(breakdown.items(), key=lambda kv: kv[1]["size"], reverse=True)
            for cat, info in rows:
                pct = (info["size"] / total["size"] * 100) if total["size"] else 0
                self._log(f"  {cat:<12} {info['count']:>4} files   {_human_size(info['size']):>8}   {pct:.0f}%")
            self._log(f"\n  Total: {total['count']} files, {_human_size(total['size'])}")
        self._set_status("Stats generated.")

    def action_duplicates(self):
        folder = self._get_folder()
        if not folder:
            return
        dupes = find_duplicates(folder, recursive=self.recursive_var.get())
        self._log(f"Duplicate scan of {folder}:", clear=True)

        if not dupes:
            self._log("  No duplicate files found.")
            self._set_status("No duplicates found.")
            return

        total_wasted = 0
        for paths in dupes.values():
            original, *copies = paths
            self._log(f"  {original}  (original)")
            for copy in copies:
                size = copy.stat().st_size
                total_wasted += size
                self._log(f"    {copy}  ({_human_size(size)}, duplicate)")
        self._log(f"\nTotal wasted space: {_human_size(total_wasted)}")
        self._log("Tip: tidyup never deletes files automatically — review and remove manually.")
        self._set_status(f"Found {len(dupes)} duplicate set(s).")

    def action_stale(self):
        folder = self._get_folder()
        if not folder:
            return
        try:
            days = int(self.stale_days_var.get())
        except ValueError:
            messagebox.showerror("Invalid value", "Stale days must be a whole number.")
            return

        stale = find_stale_files(folder, days=days, recursive=self.recursive_var.get())
        self._log(f"Files not touched in {days}+ days:", clear=True)

        if not stale:
            self._log("  None found.")
        else:
            total_size = 0
            for path, age_days in stale:
                size = path.stat().st_size
                total_size += size
                self._log(f"  {path}  ({age_days}d old, {_human_size(size)})")
            self._log(f"\nTotal size: {_human_size(total_size)}")
        self._set_status(f"{len(stale)} stale file(s) found.")

    def action_clean_empty(self):
        folder = self._get_folder()
        if not folder:
            return
        removed = clean_empty_folders(folder, dry_run=False)
        self._log(f"Empty-folder cleanup in {folder}:", clear=True)
        if not removed:
            self._log("  No empty folders found.")
        else:
            for path in removed:
                self._log(f"  Removed: {path}")
        self._set_status(f"Removed {len(removed)} empty folder(s).")

    # ---------- watch mode ----------

    def toggle_watch(self):
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_stop_event.set()
            self.watch_button.configure(text="Start Watching", fg_color="#2F855A", hover_color="#22543D")
            self._set_status("Watch mode stopped.")
            return

        folder = self._get_folder()
        if not folder:
            return

        self._watch_stop_event.clear()
        self._log(f"Watching {folder} for new files...", clear=True)
        self.watch_button.configure(text="Stop Watching", fg_color="#C53030", hover_color="#9B2C2C")
        self._set_status("Watching for new files...")

        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(folder,), daemon=True
        )
        self._watch_thread.start()

    def _watch_loop(self, folder: Path):
        categories, _ = self._get_categories(folder)
        while not self._watch_stop_event.is_set():
            moves = plan_moves(
                folder,
                by=self.by_var.get(),
                categories=categories,
                recursive=self.recursive_var.get(),
                smart_names=self.smart_names_var.get(),
            )
            if moves:
                performed = execute_moves(moves, dry_run=False)
                write_log(folder, performed)
                timestamp = time.strftime("%H:%M:%S")
                self.root.after(0, self._log, f"[{timestamp}] Organized {len(performed)} new file(s).")
            self._watch_stop_event.wait(5)


def main():
    root = ctk.CTk()
    TidyupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()