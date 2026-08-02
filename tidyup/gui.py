"""
Desktop GUI for tidyup, built with tkinter (Python standard library —
no extra dependencies, same as the CLI).

Run with:  tidyup-gui
or:        python -m tidyup.gui
"""

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

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

# ---------------------------------------------------------------------------
# Color palette — light and dark, kept as plain dicts so ScrolledText
# (which ttk styling can't reach) can be recolored manually too.
# ---------------------------------------------------------------------------

LIGHT = {
    "bg": "#F4F5F9",
    "card": "#FFFFFF",
    "border": "#E1E3EA",
    "text": "#1F2430",
    "muted": "#6B7080",
    "accent": "#4C5FD5",
    "accent_hover": "#3E4FBD",
    "accent_text": "#FFFFFF",
    "output_bg": "#FFFFFF",
    "output_fg": "#1F2430",
    "danger": "#D64545",
    "success": "#2E9E6D",
}

DARK = {
    "bg": "#1B1D27",
    "card": "#242733",
    "border": "#343849",
    "text": "#E8E9F0",
    "muted": "#9A9DB0",
    "accent": "#7C8CF5",
    "accent_hover": "#909EF7",
    "accent_text": "#12131A",
    "output_bg": "#14151D",
    "output_fg": "#DCDEEA",
    "danger": "#F0685F",
    "success": "#4FCE97",
}

FONT_FAMILY = "Segoe UI"  # falls back gracefully on macOS/Linux to a system default


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
        self.dark_mode = False
        self.palette = LIGHT

        self.root.title(f"tidyup {__version__}")
        self.root.geometry("820x640")
        self.root.minsize(680, 520)

        self.folder_var = tk.StringVar()
        self.by_var = tk.StringVar(value="type")
        self.recursive_var = tk.BooleanVar(value=False)
        self.smart_names_var = tk.BooleanVar(value=False)
        self.stale_days_var = tk.StringVar(value="90")

        self.recent_folders = []

        self._watch_thread = None
        self._watch_stop_event = threading.Event()

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self._build_menu()
        self._build_layout()
        self._apply_palette()

    # ---------- menu ----------

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose Folder...", command=self._browse_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About tidyup", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _show_about(self):
        messagebox.showinfo(
            "About tidyup",
            f"tidyup {__version__}\n\n"
            "A smart file organizer — CLI and GUI, same engine, zero dependencies.\n\n"
            "Organizes by type, date, or filename pattern, with duplicate detection,\n"
            "stale-file finding, live watch mode, and multi-step undo history.",
        )

    # ---------- layout ----------

    def _build_layout(self):
        self.root.configure(padx=0, pady=0)

        # Header banner
        self.header = tk.Frame(self.root, height=64)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        self.title_label = tk.Label(
            self.header, text="🧹  tidyup",
            font=(FONT_FAMILY, 16, "bold"),
        )
        self.title_label.pack(side="left", padx=20, pady=14)

        self.subtitle_label = tk.Label(
            self.header, text="Organize any folder in one click",
            font=(FONT_FAMILY, 9),
        )
        self.subtitle_label.pack(side="left", pady=14)

        self.theme_button = tk.Button(
            self.header, text="🌙", relief="flat", borderwidth=0,
            font=(FONT_FAMILY, 12), command=self.toggle_dark_mode, cursor="hand2",
        )
        self.theme_button.pack(side="right", padx=16)

        # Scrollable body so the window can shrink gracefully
        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # --- Folder card ---
        self.folder_card = self._make_card(body, "📁  Folder")
        self.folder_card.pack(fill="x", pady=(0, 10))

        folder_row = tk.Frame(self.folder_card, bg=self.folder_card["bg"])
        folder_row.pack(fill="x", padx=14, pady=(0, 12))

        self.folder_combo = ttk.Combobox(
            folder_row, textvariable=self.folder_var, values=self.recent_folders,
        )
        self.folder_combo.pack(side="left", fill="x", expand=True, ipady=3)
        self.folder_combo.bind("<Return>", lambda e: self.action_preview())

        self.browse_btn = self._make_button(folder_row, "Browse...", self._browse_folder, primary=False)
        self.browse_btn.pack(side="left", padx=(8, 0))

        # --- Options card ---
        self.options_card = self._make_card(body, "⚙️  Options")
        self.options_card.pack(fill="x", pady=(0, 10))

        opts_row = tk.Frame(self.options_card, bg=self.options_card["bg"])
        opts_row.pack(fill="x", padx=14, pady=(0, 12))

        self.by_label = tk.Label(opts_row, text="Organize by:", font=(FONT_FAMILY, 9))
        self.by_label.grid(row=0, column=0, sticky="w", padx=(0, 6))
        by_combo = ttk.Combobox(
            opts_row, textvariable=self.by_var,
            values=["type", "date", "both"], state="readonly", width=8,
        )
        by_combo.grid(row=0, column=1, sticky="w", padx=(0, 18))

        self.recursive_check = ttk.Checkbutton(
            opts_row, text="Include subfolders", variable=self.recursive_var,
        )
        self.recursive_check.grid(row=0, column=2, sticky="w", padx=(0, 18))

        self.smart_check = ttk.Checkbutton(
            opts_row, text="Smart filename categorization", variable=self.smart_names_var,
        )
        self.smart_check.grid(row=0, column=3, sticky="w")

        # --- Actions card ---
        self.actions_card = self._make_card(body, "⚡  Actions")
        self.actions_card.pack(fill="x", pady=(0, 10))

        actions_body = tk.Frame(self.actions_card, bg=self.actions_card["bg"])
        actions_body.pack(fill="x", padx=14, pady=(0, 12))

        primary_row = tk.Frame(actions_body, bg=self.actions_card["bg"])
        primary_row.pack(fill="x", pady=(0, 6))
        self._make_button(primary_row, "👁  Preview", self.action_preview, primary=False).pack(side="left", padx=(0, 6))
        self._make_button(primary_row, "✅  Organize Now", self.action_organize, primary=True).pack(side="left", padx=(0, 6))
        self._make_button(primary_row, "↩  Undo Last", self.action_undo, primary=False).pack(side="left", padx=(0, 6))
        self._make_button(primary_row, "📜  History", self.action_history, primary=False).pack(side="left")

        secondary_row = tk.Frame(actions_body, bg=self.actions_card["bg"])
        secondary_row.pack(fill="x", pady=(0, 6))
        self._make_button(secondary_row, "📊  Stats", self.action_stats, primary=False).pack(side="left", padx=(0, 6))
        self._make_button(secondary_row, "🔍  Duplicates", self.action_duplicates, primary=False).pack(side="left", padx=(0, 6))
        self._make_button(secondary_row, "🧹  Clean Empty", self.action_clean_empty, primary=False).pack(side="left")

        stale_row = tk.Frame(actions_body, bg=self.actions_card["bg"])
        stale_row.pack(fill="x")
        self.stale_label = tk.Label(stale_row, text="Stale after (days):", font=(FONT_FAMILY, 9))
        self.stale_label.pack(side="left", padx=(0, 4))
        stale_entry = ttk.Entry(stale_row, textvariable=self.stale_days_var, width=6)
        stale_entry.pack(side="left", padx=(0, 6))
        self._make_button(stale_row, "🕰  Find Stale Files", self.action_stale, primary=False).pack(side="left", padx=(0, 12))

        self.watch_button = self._make_button(stale_row, "👀  Start Watching", self.toggle_watch, primary=False)
        self.watch_button.pack(side="left")

        # --- Output card ---
        self.output_card = self._make_card(body, "🖥️  Output", expand=True)
        self.output_card.pack(fill="both", expand=True)

        output_toolbar = tk.Frame(self.output_card, bg=self.output_card["bg"])
        output_toolbar.pack(fill="x", padx=14)
        self._make_button(output_toolbar, "Clear", self._clear_output, primary=False, small=True).pack(side="right")
        self._make_button(output_toolbar, "Save Log...", self._save_output, primary=False, small=True).pack(side="right", padx=(0, 6))

        output_wrap = tk.Frame(self.output_card, bg=self.output_card["bg"])
        output_wrap.pack(fill="both", expand=True, padx=14, pady=(6, 14))

        self.output = ScrolledText(
            output_wrap, wrap="word", state="disabled",
            font=("Consolas", 10) if self._font_exists("Consolas") else ("Courier New", 10),
            relief="flat", borderwidth=0,
        )
        self.output.pack(fill="both", expand=True)

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Ready.")
        self.status_bar = tk.Label(
            self.root, textvariable=self.status_var, anchor="w",
            font=(FONT_FAMILY, 9), padx=14, pady=6,
        )
        self.status_bar.pack(fill="x", side="bottom")

    def _font_exists(self, name: str) -> bool:
        try:
            import tkinter.font as tkfont
            return name in tkfont.families()
        except Exception:
            return False

    def _make_card(self, parent, title, expand=False):
        card = tk.Frame(parent, highlightthickness=1, bd=0)
        header = tk.Label(card, text=title, font=(FONT_FAMILY, 10, "bold"), anchor="w")
        header.pack(fill="x", padx=14, pady=(10, 6))
        card._header_label = header
        return card

    def _make_button(self, parent, text, command, primary=False, small=False):
        btn = tk.Button(
            parent, text=text, command=command, cursor="hand2",
            relief="flat", borderwidth=0,
            font=(FONT_FAMILY, 8 if small else 9),
            padx=10 if small else 14, pady=4 if small else 7,
        )
        btn._is_primary = primary
        return btn

    # ---------- theming ----------

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.palette = DARK if self.dark_mode else LIGHT
        self.theme_button.config(text="☀️" if self.dark_mode else "🌙")
        self._apply_palette()

    def _apply_palette(self):
        p = self.palette

        self.root.configure(bg=p["bg"])
        self.header.configure(bg=p["card"], highlightbackground=p["border"], highlightthickness=1)
        self.title_label.configure(bg=p["card"], fg=p["text"])
        self.subtitle_label.configure(bg=p["card"], fg=p["muted"])
        self.theme_button.configure(bg=p["card"], fg=p["text"], activebackground=p["card"])
        self.status_bar.configure(bg=p["card"], fg=p["muted"])

        for card in [self.folder_card, self.options_card, self.actions_card, self.output_card]:
            card.configure(bg=p["card"], highlightbackground=p["border"])
            card._header_label.configure(bg=p["card"], fg=p["text"])
            self._recolor_children(card, p)

        self.output.configure(bg=p["output_bg"], fg=p["output_fg"], insertbackground=p["output_fg"])

        self._style_ttk(p)

    def _recolor_children(self, widget, p):
        for child in widget.winfo_children():
            cls = child.winfo_class()
            if cls == "Frame":
                child.configure(bg=p["card"])
                self._recolor_children(child, p)
            elif cls == "Label":
                muted = child is getattr(self, "stale_label", None)
                child.configure(bg=p["card"], fg=p["muted"] if muted else p["text"])
            elif cls == "Button":
                is_primary = getattr(child, "_is_primary", False)
                if is_primary:
                    child.configure(
                        bg=p["accent"], fg=p["accent_text"],
                        activebackground=p["accent_hover"], activeforeground=p["accent_text"],
                    )
                else:
                    child.configure(
                        bg=p["bg"], fg=p["text"],
                        activebackground=p["border"], activeforeground=p["text"],
                    )

    def _style_ttk(self, p):
        self.style.configure("TCombobox", fieldbackground=p["card"], background=p["card"])
        self.style.configure("TCheckbutton", background=p["card"], foreground=p["text"])
        self.style.configure("TEntry", fieldbackground=p["card"])

    # ---------- helpers ----------

    def _browse_folder(self):
        chosen = filedialog.askdirectory()
        if chosen:
            self.folder_var.set(chosen)
            self._remember_folder(chosen)

    def _remember_folder(self, folder: str):
        if folder and folder not in self.recent_folders:
            self.recent_folders.insert(0, folder)
            self.recent_folders = self.recent_folders[:8]
            self.folder_combo.configure(values=self.recent_folders)

    def _get_folder(self):
        raw = self.folder_var.get().strip()
        if not raw:
            messagebox.showwarning("No folder selected", "Please choose a folder first.")
            return None
        folder = Path(raw).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("Invalid folder", f"'{folder}' is not a valid directory.")
            return None
        self._remember_folder(str(folder))
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

    def _clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _save_output(self):
        content = self.output.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Nothing to save", "The output panel is empty.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile="tidyup-log.txt",
        )
        if not path:
            return
        Path(path).write_text(content, encoding="utf-8")
        self._set_status(f"Log saved to {path}")

    def _set_status(self, text: str, kind: str = "muted"):
        self.status_var.set(text)
        color = self.palette.get(kind, self.palette["muted"])
        self.status_bar.configure(fg=color)

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
            f"Move {len(moves)} file(s) in {folder}?\n\nThis can be undone with 'Undo Last'.",
        ):
            return

        performed = execute_moves(moves, dry_run=False)
        write_log(folder, performed)

        self._log(f"Organized {len(performed)} file(s) in {folder}:", clear=True)
        for src, dest in performed:
            self._log(f"  {Path(src).name}  ->  {Path(dest).relative_to(folder)}")
        self._set_status(f"Done. Moved {len(performed)} file(s).", kind="success")

    def action_undo(self):
        folder = self._get_folder()
        if not folder:
            return
        restored, error = undo_steps(folder, steps=1)
        if error:
            self._log(error, clear=True)
            self._set_status(error, kind="danger")
            return
        self._log(f"Restored {len(restored)} file(s) to their original location.", clear=True)
        self._set_status(f"Undo complete: {len(restored)} file(s) restored.", kind="success")

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
            self.watch_button.config(text="👀  Start Watching")
            self._set_status("Watch mode stopped.")
            return

        folder = self._get_folder()
        if not folder:
            return

        self._watch_stop_event.clear()
        self._log(f"Watching {folder} for new files...", clear=True)
        self.watch_button.config(text="⏹  Stop Watching")
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
    root = tk.Tk()
    TidyupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
