import shutil
import tempfile
import unittest
from pathlib import Path

from tidyup.organizer import (
    plan_moves,
    execute_moves,
    write_log,
    undo_last,
    undo_steps,
    list_history,
    find_duplicates,
    folder_stats,
    find_stale_files,
    clean_empty_folders,
    export_plan,
)
from tidyup.categories import load_categories, find_project_config
from tidyup.ignore import load_ignore_patterns, is_ignored
from tidyup.naming_rules import category_for_filename


class TestOrganizer(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        (self.tmp_dir / "photo.jpg").write_text("fake image")
        (self.tmp_dir / "report.pdf").write_text("fake pdf")
        (self.tmp_dir / "song.mp3").write_text("fake audio")
        (self.tmp_dir / "unknown.xyz").write_text("fake unknown")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_plan_moves_by_type(self):
        moves = plan_moves(self.tmp_dir, by="type")
        dest_names = {src.name: dest.parent.name for src, dest in moves}
        self.assertEqual(dest_names["photo.jpg"], "Images")
        self.assertEqual(dest_names["report.pdf"], "Documents")
        self.assertEqual(dest_names["song.mp3"], "Audio")
        self.assertEqual(dest_names["unknown.xyz"], "Others")

    def test_dry_run_does_not_move_files(self):
        moves = plan_moves(self.tmp_dir, by="type")
        execute_moves(moves, dry_run=True)
        self.assertTrue((self.tmp_dir / "photo.jpg").exists())
        self.assertFalse((self.tmp_dir / "Images").exists())

    def test_execute_moves_actually_moves_files(self):
        moves = plan_moves(self.tmp_dir, by="type")
        execute_moves(moves, dry_run=False)
        self.assertTrue((self.tmp_dir / "Images" / "photo.jpg").exists())
        self.assertFalse((self.tmp_dir / "photo.jpg").exists())

    def test_undo_restores_files(self):
        moves = plan_moves(self.tmp_dir, by="type")
        performed = execute_moves(moves, dry_run=False)
        write_log(self.tmp_dir, performed)

        restored, error = undo_last(self.tmp_dir)

        self.assertIsNone(error)
        self.assertTrue((self.tmp_dir / "photo.jpg").exists())

    def test_undo_with_no_log_returns_error(self):
        empty_dir = Path(tempfile.mkdtemp())
        try:
            restored, error = undo_last(empty_dir)
            self.assertIsNone(restored)
            self.assertIsNotNone(error)
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_naming_collision_gets_suffixed(self):
        (self.tmp_dir / "Images").mkdir()
        (self.tmp_dir / "Images" / "photo.jpg").write_text("existing file")

        moves = plan_moves(self.tmp_dir, by="type")
        performed = execute_moves(moves, dry_run=False)

        performed_dests = [dest for _, dest in performed]
        self.assertTrue(any("photo_1.jpg" in d for d in performed_dests))

    def test_recursive_picks_up_nested_files(self):
        sub = self.tmp_dir / "sub"
        sub.mkdir()
        (sub / "nested.mp3").write_text("fake nested audio")

        moves_non_recursive = plan_moves(self.tmp_dir, by="type", recursive=False)
        moves_recursive = plan_moves(self.tmp_dir, by="type", recursive=True)

        non_recursive_names = {src.name for src, _ in moves_non_recursive}
        recursive_names = {src.name for src, _ in moves_recursive}

        self.assertNotIn("nested.mp3", non_recursive_names)
        self.assertIn("nested.mp3", recursive_names)

    def test_rerun_does_not_reorganize_own_output(self):
        moves = plan_moves(self.tmp_dir, by="type", recursive=True)
        execute_moves(moves, dry_run=False)

        second_pass = plan_moves(self.tmp_dir, by="type", recursive=True)
        self.assertEqual(second_pass, [])

    def test_find_duplicates_detects_identical_content(self):
        (self.tmp_dir / "dup1.txt").write_text("same content")
        (self.tmp_dir / "dup2.txt").write_text("same content")

        dupes = find_duplicates(self.tmp_dir)
        all_dupe_names = {p.name for paths in dupes.values() for p in paths}

        self.assertIn("dup1.txt", all_dupe_names)
        self.assertIn("dup2.txt", all_dupe_names)
        # unrelated files should not show up as duplicates
        self.assertNotIn("photo.jpg", all_dupe_names)

    def test_custom_categories_override_defaults(self):
        config_path = self.tmp_dir / "config.json"
        config_path.write_text('{"Memes": [".jpg"]}')

        categories = load_categories(config_path)
        moves = plan_moves(self.tmp_dir, by="type", categories=categories)

        dest_for_jpg = next(
            dest.parent.name for src, dest in moves if src.name == "photo.jpg"
        )
        self.assertEqual(dest_for_jpg, "Memes")

    def test_folder_stats_breaks_down_by_category(self):
        stats = folder_stats(self.tmp_dir)
        total = stats["_total"]

        self.assertEqual(total["count"], 4)
        self.assertIn("Images", stats)
        self.assertEqual(stats["Images"]["count"], 1)

    def test_find_stale_files_respects_threshold(self):
        import os
        import time

        old_time = time.time() - (40 * 86400)
        os.utime(self.tmp_dir / "photo.jpg", (old_time, old_time))

        stale_30 = find_stale_files(self.tmp_dir, days=30)
        stale_names_30 = {p.name for p, _ in stale_30}
        self.assertIn("photo.jpg", stale_names_30)

        stale_60 = find_stale_files(self.tmp_dir, days=60)
        stale_names_60 = {p.name for p, _ in stale_60}
        self.assertNotIn("photo.jpg", stale_names_60)

    def test_clean_empty_folders_removes_only_empty_ones(self):
        empty_dir = self.tmp_dir / "EmptyOne"
        empty_dir.mkdir()
        non_empty_dir = self.tmp_dir / "HasStuff"
        non_empty_dir.mkdir()
        (non_empty_dir / "keep.txt").write_text("keep me")

        removed = clean_empty_folders(self.tmp_dir)

        self.assertIn(str(empty_dir), removed)
        self.assertFalse(empty_dir.exists())
        self.assertTrue(non_empty_dir.exists())

    def test_clean_empty_folders_dry_run_does_not_delete(self):
        empty_dir = self.tmp_dir / "EmptyOne"
        empty_dir.mkdir()

        removed = clean_empty_folders(self.tmp_dir, dry_run=True)

        self.assertIn(str(empty_dir), removed)
        self.assertTrue(empty_dir.exists())

    def test_multi_step_undo_reverses_only_requested_steps(self):
        # Run 1: organize photo.jpg
        moves1 = plan_moves(self.tmp_dir, by="type")
        performed1 = execute_moves(moves1, dry_run=False)
        write_log(self.tmp_dir, performed1)

        # Run 2: a new file appears and gets organized separately
        (self.tmp_dir / "new_song.mp3").write_text("fake second audio")
        moves2 = plan_moves(self.tmp_dir, by="type")
        performed2 = execute_moves(moves2, dry_run=False)
        write_log(self.tmp_dir, performed2)

        # Undo only the most recent run
        restored, error = undo_steps(self.tmp_dir, steps=1)

        self.assertIsNone(error)
        self.assertTrue((self.tmp_dir / "new_song.mp3").exists())
        # first run's effects should remain untouched
        self.assertTrue((self.tmp_dir / "Images" / "photo.jpg").exists())

    def test_list_history_reflects_undo(self):
        moves = plan_moves(self.tmp_dir, by="type")
        performed = execute_moves(moves, dry_run=False)
        write_log(self.tmp_dir, performed)

        self.assertEqual(len(list_history(self.tmp_dir)), 1)

        undo_steps(self.tmp_dir, steps=1)
        self.assertEqual(len(list_history(self.tmp_dir)), 0)

    def test_ignore_file_excludes_matching_files(self):
        (self.tmp_dir / ".tidyupignore").write_text("*.pdf\n")

        patterns = load_ignore_patterns(self.tmp_dir)
        moves = plan_moves(self.tmp_dir, by="type", use_ignore_file=True)

        moved_names = {src.name for src, _ in moves}
        self.assertNotIn("report.pdf", moved_names)
        self.assertIn("photo.jpg", moved_names)

    def test_no_ignore_file_flag_includes_everything(self):
        (self.tmp_dir / ".tidyupignore").write_text("*.pdf\n")

        moves = plan_moves(self.tmp_dir, by="type", use_ignore_file=False)
        moved_names = {src.name for src, _ in moves}
        self.assertIn("report.pdf", moved_names)

    def test_smart_names_take_priority_over_extension(self):
        (self.tmp_dir / "Screenshot_2026-01-01.png").write_text("fake screenshot")

        moves = plan_moves(self.tmp_dir, by="type", smart_names=True)
        dest_for_screenshot = next(
            dest.parent.name for src, dest in moves
            if src.name == "Screenshot_2026-01-01.png"
        )
        self.assertEqual(dest_for_screenshot, "Screenshots")

    def test_find_project_config_detects_tidyup_json(self):
        self.assertIsNone(find_project_config(self.tmp_dir))

        (self.tmp_dir / ".tidyup.json").write_text('{"Memes": [".jpg"]}')
        found = find_project_config(self.tmp_dir)

        self.assertIsNotNone(found)
        self.assertEqual(found.name, ".tidyup.json")

    def test_export_plan_writes_manifest_without_moving(self):
        import json

        moves = plan_moves(self.tmp_dir, by="type")
        out_path = self.tmp_dir.parent / "plan.json"
        try:
            export_plan(moves, self.tmp_dir, out_path)

            manifest = json.loads(out_path.read_text())
            self.assertEqual(len(manifest["moves"]), len(moves))
            # nothing should have actually moved
            self.assertTrue((self.tmp_dir / "photo.jpg").exists())
        finally:
            out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
