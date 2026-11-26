"""Tests for checkpoint_list.py: a Claude chat's checkpoints in the Chats list's place, Restore files to here… with
Claude's dry run under the chosen prompt, the restore, the foot's line with its Undo, and the way back to the list."""
import os
import sys
import time
import unittest

from support import SRC, inset_band, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from chat_list import ChatList                  # noqa: E402
from chats import Chat                  # noqa: E402
from checkpoint_list import CheckpointList, clock  # noqa: E402
from screen import Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

FOLDER = "/Users/dev/lumen-api"
FIX = Chat("claude", "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f", "Fix the page past the last one", FOLDER,
           1_800_000_000)
RUNNING = Chat("claude", FIX.id, FIX.title, FOLDER, FIX.time, "idle", "w1:p1")


def point(n, minute, words, files=0, kept=True, bash=0, agents=0):
    return {"id": f"1a2b3c4d-000{n}-4a5b-8c6d-7e8f9a0b1c2d", "at": f"2026-11-25T13:{minute:02d}:00.000Z",
            "text": words, "files": files, "bash": bash, "agents": agents, "kept": kept}


READ = point(1, 30, "Read the paging spec")
PAGE = point(2, 32, "Fix #42: past the last page the API should answer the last page", files=2, bash=2)
TEST = point(3, 58, "Add a test below page one", files=2, bash=1)
NOTE = point(4, 59, "Note it under Unreleased", files=1, kept=False)
DRY = {"files": [f"{FOLDER}/src/lumen/routes/books.py", f"{FOLDER}/tests/test_books.py"], "insertions": 1,
       "deletions": 13}


class Points(unittest.TestCase):
    def setUp(self):
        set_env(self, TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)
        self.view = CheckpointList(FIX)
        self.view.set({"points": [READ, PAGE, TEST, NOTE], "undo": None})

    def draw(self, cells=56, rows=24):
        self.canvas = Canvas(cells, rows)
        self.view.draw(self.canvas, 0, rows)
        return [text(self.canvas, y).rstrip() for y in range(rows)]

    def row_of(self, part):
        return next(y for y in range(self.canvas.height) if part in text(self.canvas, y))

    def press(self, name, char=""):
        return self.view.handle(Key(name, char))

    def click(self, x, y):
        return self.view.handle(Mouse("press", x, y, 0))

    def test_the_newest_first_a_count_where_claude_keeps_what_the_turn_wrote(self):
        rows = self.draw()
        self.assertEqual(rows[0][:33], " ‹ Fix the page past the last one")
        self.assertTrue(rows[0].endswith("Claude"))
        listed = [" ".join(row.split()) for row in rows[2:8]]
        self.assertEqual(listed[0], "13:59 Note it under Unreleased")          # not kept: no count, no action
        self.assertEqual(listed[1], "13:58 Add a test below page one wrote 2 files")   # its turn's: chosen
        self.assertEqual(listed[2], "Restore files to here…")
        self.assertEqual(listed[4], "13:30 Read the paging spec")             # its turn wrote nothing
        self.assertEqual(" ".join(rows[-1].split()), "Enter restores files · ← back to Chats")

    def test_the_chosen_point_stands_a_cell_in_from_each_side_its_content_a_cell_inside(self):
        # as its button stands at the highlight's edge under it: its time, its words cut short and its count, each a
        # cell inside the highlight
        long = point(5, 10, "Answer every page in the order its rows were written, the last one too", files=3)
        self.view.set({"points": [long, READ], "undo": None})
        self.draw()
        inset_band(self, self.canvas, self.row_of("13:10"))
        self.assertEqual(text(self.canvas, self.row_of("13:10"))[53], "s")    # wrote 3 files: a cell inside the end

    def test_a_running_claude_is_told_to_rewind_in_its_own_pane(self):
        self.view.item = RUNNING
        rows = [" ".join(row.split()) for row in self.draw(cells=44)]
        self.assertEqual(rows[2:4], ["Claude runs in its pane: Esc Esc there", "rewinds files and chat in place"])

    def test_enter_asks_claudes_dry_run_then_shows_what_changes_and_what_stays(self):
        self.press("down")
        self.assertEqual(self.press("enter"), Action("checkpoint_ask", (FIX, PAGE)))
        self.assertIn("Asking Claude which files would", "\n".join(self.draw()))
        self.view.asked = DRY
        rows = [" ".join(row.split()) for row in self.draw()]
        start = rows.index("Files as they were before this message")
        self.assertEqual(rows[start + 1:start + 4], ["src/lumen/routes/books.py", "tests/test_books.py",
                                                      "2 files · +1 −13"])
        stays = rows.index("Stays as it is")
        self.assertEqual(rows[stays + 1:stays + 4], ["what 2 Bash commands changed", "edits made outside Claude",
                                                      "this chat: Claude keeps the later turns"])
        self.assertIn("Esc cancels Restore 2 files", rows)                    # the button at the right end
        y = self.row_of("Restore 2 files")
        self.assertEqual(self.canvas.rows[y][text(self.canvas, y).index("Restore 2")][1].bg, "button")
        self.assertEqual(self.press("enter"), Action("checkpoint_restore", (FIX, PAGE, NOTE["id"])))
        self.assertTrue(self.view.busy)
        self.assertIsNone(self.press("esc"))                                  # nothing taken while it restores

    def test_claudes_refusal_is_said_in_its_words_and_esc_cancels_then_goes_back(self):
        self.view.asked = {"error": "No file checkpoint found for this message."}
        rows = " ".join(" ".join(row.split()) for row in self.draw())
        self.assertIn("No file checkpoint found for this message.", rows)
        self.assertEqual(self.style_of("No file checkpoint").fg, "deleted")
        self.assertIsNone(self.press("esc"))
        self.assertIsNone(self.view.asked)
        self.assertEqual(self.press("esc"), "back")

    def style_of(self, part):
        y = self.row_of(part)
        return self.canvas.rows[y][text(self.canvas, y).index(part)][1]

    def test_after_a_restore_the_foot_says_so_and_u_undoes_it(self):
        self.view.set({"points": [READ, PAGE, TEST, NOTE], "undo": {"point": PAGE["id"], "files": 2}})
        rows = self.draw()
        self.assertEqual(" ".join(rows[-1].split()), "Restored 2 files to before 13:32 u Undo")
        self.assertEqual(self.press("char", "u"), Action("checkpoint_undo", (FIX,)))
        self.view.busy, self.view.undo = False, None
        self.view.told = ("Undid the restore: 2 files back as they were", False)
        self.assertEqual(" ".join(" ".join(self.draw()[-2:]).split()), "Undid the restore: 2 files back as they were")
        self.assertIsNone(self.press("char", "u"))

    def test_a_click_chooses_a_prompt_and_presses_its_button_and_the_mark_goes_back(self):
        self.draw()
        self.assertIsNone(self.click(6, self.row_of("Fix #42")))
        self.assertEqual(self.view.chosen(), PAGE)
        self.draw()
        y = self.row_of("Restore files to here…")
        self.assertEqual(self.click(text(self.canvas, y).index("Restore") + 1, y), Action("checkpoint_ask",
                                                                                          (FIX, PAGE)))
        self.assertEqual(self.click(1, 0), "back")

    def test_nothing_is_cut_at_the_narrowest_width(self):
        self.press("down")
        self.view.asked = DRY
        rows = self.draw(cells=24, rows=30)
        self.assertTrue(all(len(row) <= 24 for row in rows))
        self.assertIn("Stays as it is", "\n".join(rows))
        self.assertIn("what 2 Bash commands", "\n".join(rows))               # wrapped, not cut
        self.assertIn("…men/routes/books.py", "\n".join(rows))               # a path keeps its file's name

    def test_a_short_pane_keeps_the_restore_and_says_how_many_files_more(self):
        self.press("down")
        self.view.asked = {**DRY, "files": [f"{FOLDER}/docs/page{n}.md" for n in range(6)]}
        rows = [" ".join(row.split()) for row in self.draw(rows=16)]
        self.assertIn("Esc cancels Restore 6 files", rows)
        self.assertTrue(any(row.startswith("and ") and row.endswith(" more") for row in rows))
        self.assertIn("docs/page0.md", rows)

    def test_twelve_hours_where_the_machine_says_so(self):
        self.assertEqual(clock("2026-11-25T13:32:00.000Z", True), "1:32 PM")
        self.assertEqual(clock("not a time", False), "")


class FromChats(unittest.TestCase):
    def test_a_claude_chats_menu_and_its_right_arrow_open_its_checkpoints_and_left_comes_back(self):
        view = ChatList(now=lambda: FIX.time)
        view.set([FIX], ["lumen-api"], lambda folder: "lumen-api", "lumen-api")
        view.list.move(1)
        self.assertEqual(view.handle(Key("right", "")), Action("checkpoints", (FIX,)))
        self.assertIsInstance(view.points, CheckpointList)
        self.assertIsNone(view.handle(Key("left", "")))
        self.assertIsNone(view.points)
        self.assertEqual(view.choices(Chat("codex", "c1", "Paginate", FOLDER, 0))[:3], ("Open", "Copy chat", "Rename"))
        self.assertNotIn("Checkpoints…", view.choices(Chat("codex", "c1", "Paginate", FOLDER, 0)))


if __name__ == "__main__":
    unittest.main()
