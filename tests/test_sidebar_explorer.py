"""Tests for the sidebar's file view (src/plugins/sidebar/explorer.py) at 45 and 24 columns: the header, git's marks,
ignored and long names, and what keys and the mouse do (preview, new, rename, Trash, copy path, open, scroll)."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import SRC, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import explorer  # noqa: E402
from explorer import Explorer  # noqa: E402
from git import Change, Status  # noqa: E402
from tree import git_marks  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import Canvas  # noqa: E402
from tree import Tree  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

LONG = "a-very-long-file-name-that-does-not-fit.txt"


def key(name):
    return Key("char", name) if len(name) == 1 else Key(name)


class View(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.root = os.path.join(tmp, "project")
        for path in ("src/app.py", "src/util.py", "docs/guide.md", "build/out.bin", "README.md", LONG, ".hidden"):
            os.makedirs(os.path.dirname(os.path.join(self.root, path)), exist_ok=True)
            with open(os.path.join(self.root, path), "w") as f:
                f.write("x\n")
        self.status = Status(branch="main", changes=[Change("src/app.py", "M"), Change(LONG, "?")],
                             ignored={"build/"})
        self.view = Explorer(Tree(self.root), icons=False)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def draw(self, width=45, height=12):
        self.canvas = Canvas(width, height)
        self.view.draw(self.canvas, 0, height, self.status)
        return self.canvas

    def row_of(self, name):
        return next(y for y in range(self.canvas.height) if name in text(self.canvas, y))

    def press(self, *names):
        actions = [self.view.handle(key(name)) for name in names]
        return actions[-1]

    def click(self, name, button=0):
        y = self.row_of(name)
        return self.view.handle(Mouse("press", text(self.canvas, y).index(name), y, button))

    def test_the_header_names_the_root(self):
        self.assertTrue(text(self.draw(), 0).strip().startswith("project"))

    def test_a_header_button_under_the_mouse_lights_up(self):
        canvas = self.draw()
        marks = [glyphs(self.view.icons)[name] for name in ("new_file", "new_folder", "refresh", "collapse")]
        x = text(canvas, 0).index(marks[2])
        self.view.handle(Mouse("move", x, 0, 3))
        canvas = self.draw()
        colors = [canvas.rows[0][text(canvas, 0).index(mark)][1].fg for mark in marks]
        self.assertEqual(colors, ["muted", "muted", "text", "muted"])

    def test_the_tree_starts_right_under_its_header(self):
        canvas = self.draw()
        self.assertNotEqual(text(canvas, 1).strip(), "")
        self.assertEqual(canvas.hit(5, 1), ("row", 0))                      # the first entry

    def test_a_nerd_font_icon_keeps_a_cell_of_air_before_the_name(self):
        # the terminal draws a Nerd Font icon two cells wide, over the blank after it: a second blank keeps the air
        self.view = Explorer(Tree(self.root), icons=True)
        canvas = self.draw()
        line = text(canvas, self.row_of("README.md"))
        name = line.index("README.md")
        self.assertEqual(line[name - 2:name], "  ")
        self.assertNotEqual(line[name - 3], " ")                            # the icon, right before the two blanks

    def test_the_chosen_row_is_a_square_band_across_the_pane(self):
        self.view.focus = "list"
        canvas = self.draw()
        y = next(y for y in range(canvas.height) if canvas.rows[y][5][1].bg == "selection")
        ends = (canvas.rows[y][0], canvas.rows[y][canvas.width - 1])
        self.assertEqual([(ch, style.bg) for ch, style in ends], [(" ", "selection"), (" ", "selection")])

    def test_the_header_icons_have_room_between_them(self):
        canvas = self.draw()
        icons = [x for x, (ch, _) in enumerate(canvas.rows[0]) if ch.strip() and x > 20]
        self.assertEqual(len(icons), 4)
        self.assertTrue(all(b - a >= 3 for a, b in zip(icons, icons[1:])), icons)

    def test_git_marks_on_the_right_edge(self):
        canvas = self.draw()
        y = self.row_of("src")
        self.assertEqual(text(canvas, y)[43], "●")
        self.assertEqual(canvas.rows[y][43][1].fg, "modified")
        self.press("down", "down", "enter")                       # open src
        canvas = self.draw()
        y = self.row_of("app.py")
        self.assertEqual(text(canvas, y)[43], "M")
        self.assertEqual(canvas.rows[y][43][1].fg, "modified")
        self.assertEqual(text(canvas, self.row_of("util.py"))[43], " ")

    def test_the_stronger_change_gives_the_mark(self):
        self.status = Status(staged=[Change("src/util.py", "A")],
                             changes=[Change("src/util.py", "M"), Change("src/app.py", "U")])
        self.press("down", "down", "enter")
        canvas = self.draw()
        self.assertEqual(text(canvas, self.row_of("util.py"))[43], "A")       # added, then edited: still new
        self.assertEqual(text(canvas, self.row_of("app.py"))[43], "!")
        self.assertEqual(canvas.rows[self.row_of("src")][43][1].fg, "conflict")

    def test_marks_worked_out_off_the_main_thread_are_not_worked_out_again(self):
        marks = git_marks(self.status, self.root, self.root)
        self.view.take(self.status, marks)
        with mock.patch.object(explorer, "git_marks", side_effect=AssertionError("worked out again")):
            canvas = self.draw()
        self.assertEqual(text(canvas, self.row_of("src"))[43], "●")

    def test_an_ignored_row_is_faint(self):
        canvas = self.draw()
        y = self.row_of("build")
        x = text(canvas, y).index("build")
        self.assertEqual(canvas.rows[y][x][1].fg, "ignored")

    def test_nothing_runs_past_the_edge_at_24_columns(self):
        canvas = self.draw(width=24)
        y = self.row_of("a-very")
        self.assertIn("…", text(canvas, y))
        self.assertEqual(text(canvas, y)[22], "U")
        self.assertEqual(canvas.rows[y][22][1].fg, "added")
        self.assertTrue(text(canvas, 0).strip().startswith("project"))

    def test_enter_opens_a_folder_and_previews_a_file(self):
        self.draw()
        self.assertIsNone(self.press("down", "down", "enter"))
        self.draw()
        self.assertEqual(self.row_of("app.py"), self.row_of("src") + 1)
        self.assertEqual(self.press("down", "enter"), Action("preview_file", (self.path("src/app.py"),)))

    def test_left_and_right_walk_the_tree(self):
        self.draw()
        self.press("down", "down", "right", "right")             # open src, then step into it
        self.assertEqual(self.view.list.selected().path, self.path("src/app.py"))
        self.press("left")
        self.assertEqual(self.view.list.selected().path, self.path("src"))
        self.press("left")
        self.draw()
        self.assertFalse(any("app.py" in text(self.canvas, y) for y in range(12)))

    def test_a_click_previews_a_file_and_opens_a_folder(self):
        self.draw()
        self.assertEqual(self.click("README.md"), Action("preview_file", (self.path("README.md"),)))
        self.assertIsNone(self.click("docs"))
        self.draw()
        self.assertIn("guide.md", text(self.canvas, self.row_of("docs") + 1))

    def test_n_names_a_new_file_in_the_chosen_folder(self):
        self.draw()
        self.press("down", "down", "n")                           # src chosen
        for ch in "new.txt":
            self.press(ch)
        self.draw()
        self.assertEqual(self.row_of("new.txt"), self.row_of("src") + 1)
        self.assertEqual(self.press("enter"), Action("new_file", (self.path("src"), "new.txt")))

    def test_shift_n_names_a_new_folder_next_to_a_file_and_esc_cancels(self):
        self.draw()
        self.press("end", "N", "x")
        self.press("esc")
        self.draw()
        self.assertFalse(any(text(self.canvas, y).strip() == "x" for y in range(12)))
        self.press("N", "x")
        self.assertEqual(self.press("enter"), Action("new_folder", (self.root, "x")))

    def test_a_name_a_question_or_a_menu_takes_the_keys(self):
        self.draw()
        self.assertFalse(self.view.editing)
        self.press("n")
        self.assertTrue(self.view.editing)
        self.press("esc")
        self.assertFalse(self.view.editing)
        self.press("delete")                                     # a question or a menu holds the keys too
        self.assertTrue(self.view.editing)
        self.press("esc", "m")
        self.assertTrue(self.view.editing)

    def test_r_renames(self):
        self.draw()
        self.press("end", "r", "backspace", "backspace", "T", "X", "T")       # the cursor starts at the end
        self.assertEqual(self.press("enter"), Action("rename", (self.path("README.md"), "README.TXT")))

    def test_delete_asks_before_the_trash(self):
        self.draw()
        self.assertIsNone(self.press("end", "delete"))
        self.draw()
        self.assertTrue(any("Move README.md to the Trash?" in text(self.canvas, y) for y in range(12)))
        self.assertEqual(self.press("y"), Action("trash", (self.path("README.md"),)))
        self.assertIsNone(self.press("delete", "enter"))          # Enter presses Cancel unless Tab chose Move
        self.assertIsNone(self.press("delete", "esc"))
        self.draw()
        self.assertFalse(any("Trash?" in text(self.canvas, y) for y in range(12)))

    def test_the_right_click_menu_copies_the_path(self):
        self.draw()
        self.assertIsNone(self.click("README.md", button=2))
        self.draw()
        self.assertEqual(self.click("Copy Path"), Action("copy_path", (self.path("README.md"),)))
        self.draw()
        self.assertFalse(any("Copy Path" in text(self.canvas, y) for y in range(12)))

    def test_a_folders_menu_offers_a_new_workspace_once_herdr_folds_picker_is_there(self):
        def menu_of(name):
            self.view.close_menu()
            self.draw()
            self.click(name, button=2)
            self.draw()
            return [y for y in range(12) if "New Workspace" in text(self.canvas, y)]
        self.assertEqual(menu_of("src"), [])                     # the sidebar on its own: no folder picker
        self.view.opens_workspace = True
        self.assertTrue(menu_of("src"))
        self.assertEqual(self.click("New Workspace"), Action("new_workspace", (self.path("src"),)))
        self.assertEqual(menu_of("README.md"), [])               # a file is no workspace

    def test_the_wheel_scrolls_the_list(self):
        for i in range(30):
            with open(self.path(f"file{i:02d}.txt"), "w"):
                pass
        self.view.tree.reload()
        self.draw(height=6)
        first = text(self.canvas, 1)                                        # the first entry, under the header
        self.view.handle(Mouse("wheel_down", 5, 3))
        self.draw(height=6)
        self.assertNotEqual(text(self.canvas, 1), first)
        self.assertEqual(self.view.list.index, 0)

    def test_dot_shows_hidden_files_and_the_header_buttons_work(self):
        self.draw()
        self.assertEqual(self.press("."), Action("show_hidden", (True,)))
        self.draw()
        self.row_of(".hidden")
        self.assertEqual(self.press("R"), Action("refresh"))
        self.assertEqual(self.press("i"), Action("icons", (True,)))
        self.press("down", "down", "enter")
        self.draw()
        targets = {target: (x0, y) for y, x0, _, target in self.canvas.regions if isinstance(target, str)}
        self.view.handle(Mouse("press", *targets["collapse"]))
        self.draw()
        self.assertFalse(any("app.py" in text(self.canvas, y) for y in range(12)))
        self.assertEqual(self.view.handle(Mouse("press", *targets["refresh"])), Action("refresh"))


if __name__ == "__main__":
    unittest.main()
