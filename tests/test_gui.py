"""
Headless logic test for tidyup/gui.py.

CI runners have no real display, so this stubs out tkinter with
minimal fake widgets that just record calls, then drives TidyupApp's
action_* methods against a real temp folder. This verifies the
*logic* is correct (right functions called, files actually moved and
restored on disk, no AttributeErrors from widget-API typos) — it does
not verify visual rendering, which needs a real display and manual
testing.
"""

import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock


def _install_fake_tkinter():
    class FakeVar:
        def __init__(self, value=None):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    class FakeWidget(MagicMock):
        """A MagicMock that also supports being used as a widget:
        safe to construct with positional args (parent/master), and
        returns sane defaults for the introspection calls the app makes
        (winfo_children/winfo_class) so recursive styling code doesn't
        iterate over auto-mocked garbage."""
        def __init__(self, *a, **k):
            super().__init__()
            self.winfo_children = MagicMock(return_value=[])
            self.winfo_class = MagicMock(return_value="Unknown")

    fake_tk = types.ModuleType("tkinter")
    fake_tk.Tk = MagicMock
    fake_tk.StringVar = FakeVar
    fake_tk.BooleanVar = FakeVar
    fake_tk.Frame = FakeWidget
    fake_tk.Label = FakeWidget
    fake_tk.Button = FakeWidget
    fake_tk.Menu = FakeWidget
    fake_tk.TclError = type("TclError", (Exception,), {})

    fake_ttk = types.ModuleType("tkinter.ttk")
    for name in ["Frame", "Label", "Entry", "Button", "LabelFrame", "Combobox", "Checkbutton", "Style"]:
        setattr(fake_ttk, name, FakeWidget)

    fake_filedialog = types.ModuleType("tkinter.filedialog")
    fake_filedialog.askdirectory = MagicMock(return_value="")
    fake_filedialog.asksaveasfilename = MagicMock(return_value="")

    fake_messagebox = types.ModuleType("tkinter.messagebox")
    fake_messagebox.showwarning = MagicMock()
    fake_messagebox.showerror = MagicMock()
    fake_messagebox.showinfo = MagicMock()
    fake_messagebox.askyesno = MagicMock(return_value=True)

    fake_scrolledtext = types.ModuleType("tkinter.scrolledtext")

    class FakeScrolledText(FakeWidget):
        def __init__(self, *a, **k):
            super().__init__()
            self._lines = []

        def configure(self, **k):
            pass

        def delete(self, *a, **k):
            self._lines = []

        def insert(self, index, text):
            self._lines.append(text)

        def see(self, *a, **k):
            pass

        def get(self, start=None, end=None):
            return "\n".join(self._lines)

    fake_scrolledtext.ScrolledText = FakeScrolledText

    fake_tk.ttk = fake_ttk
    fake_tk.filedialog = fake_filedialog
    fake_tk.messagebox = fake_messagebox
    fake_tk.scrolledtext = fake_scrolledtext

    sys.modules["tkinter"] = fake_tk
    sys.modules["tkinter.ttk"] = fake_ttk
    sys.modules["tkinter.filedialog"] = fake_filedialog
    sys.modules["tkinter.messagebox"] = fake_messagebox
    sys.modules["tkinter.scrolledtext"] = fake_scrolledtext


_install_fake_tkinter()

# Import must happen after the fake tkinter is installed.
from tidyup.gui import TidyupApp  # noqa: E402


class TestGuiLogic(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        (self.tmp_dir / "photo.jpg").write_text("fake image")
        (self.tmp_dir / "report.pdf").write_text("fake pdf")
        (self.tmp_dir / "dup1.txt").write_text("same")
        (self.tmp_dir / "dup2.txt").write_text("same")

        self.app = TidyupApp(MagicMock())
        self.app.folder_var.set(str(self.tmp_dir))

    def tearDown(self):
        if self.app._watch_thread and self.app._watch_thread.is_alive():
            self.app._watch_stop_event.set()
            self.app._watch_thread.join(timeout=2)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _output_lines(self):
        return self.app.output._lines

    def test_preview_lists_files_without_moving(self):
        self.app.action_preview()
        self.assertTrue(any("photo.jpg" in line for line in self._output_lines()))
        self.assertTrue((self.tmp_dir / "photo.jpg").exists())

    def test_stats_shows_categories(self):
        self.app.action_stats()
        self.assertTrue(any("Images" in line for line in self._output_lines()))

    def test_duplicates_detected(self):
        self.app.action_duplicates()
        lines = self._output_lines()
        self.assertTrue(any("dup1.txt" in line or "dup2.txt" in line for line in lines))

    def test_stale_files_detected_with_zero_day_threshold(self):
        self.app.stale_days_var.set("0")
        self.app.action_stale()
        self.assertTrue(any("d old" in line for line in self._output_lines()))

    def test_organize_actually_moves_files(self):
        self.app.action_organize()
        self.assertTrue((self.tmp_dir / "Images" / "photo.jpg").exists())
        self.assertFalse((self.tmp_dir / "photo.jpg").exists())

    def test_undo_restores_after_organize(self):
        self.app.action_organize()
        self.app.action_undo()
        self.assertTrue((self.tmp_dir / "photo.jpg").exists())

    def test_history_lists_runs(self):
        self.app.action_organize()
        self.app.action_history()
        self.assertTrue(any("file(s) moved" in line for line in self._output_lines()))

    def test_clean_empty_does_not_crash_on_no_empty_folders(self):
        self.app.action_clean_empty()  # should not raise

    def test_watch_starts_and_stops_cleanly(self):
        self.app.toggle_watch()
        self.assertTrue(self.app._watch_thread.is_alive())
        self.app.toggle_watch()
        self.app._watch_thread.join(timeout=2)
        self.assertFalse(self.app._watch_thread.is_alive())

    def test_invalid_folder_returns_none_without_crashing(self):
        self.app.folder_var.set("/this/path/does/not/exist/at/all")
        self.assertIsNone(self.app._get_folder())

    def test_toggle_dark_mode_switches_palette_without_crashing(self):
        self.assertFalse(self.app.dark_mode)
        self.app.toggle_dark_mode()
        self.assertTrue(self.app.dark_mode)
        self.app.toggle_dark_mode()
        self.assertFalse(self.app.dark_mode)

    def test_show_about_does_not_crash(self):
        self.app._show_about()  # should not raise

    def test_recent_folders_remembers_used_folder(self):
        self.app._get_folder()
        self.assertIn(str(self.tmp_dir), self.app.recent_folders)

    def test_recent_folders_caps_at_eight(self):
        for i in range(10):
            self.app._remember_folder(f"/fake/folder/{i}")
        self.assertLessEqual(len(self.app.recent_folders), 8)

    def test_clear_output_empties_the_log(self):
        self.app.action_preview()
        self.assertTrue(len(self._output_lines()) > 0)
        self.app._clear_output()
        self.assertEqual(len(self._output_lines()), 0)

    def test_save_output_writes_file(self):
        import tempfile as _tempfile
        save_path = Path(_tempfile.mkdtemp()) / "log.txt"
        self.app.action_preview()

        import tidyup.gui as gui_module
        gui_module.filedialog.asksaveasfilename = MagicMock(return_value=str(save_path))
        self.app._save_output()

        self.assertTrue(save_path.exists())
        self.assertIn("photo.jpg", save_path.read_text())


if __name__ == "__main__":
    unittest.main()
