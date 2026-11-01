"""Tests for new_workspace.py's folder picker screen: the folder as title, a claude │ codex toggle marking the chosen
agent, the filter only while typing, and one short line for the keys that are not obvious (Tab, →).
"""
import os
import shutil
import tempfile
import unittest

from support import ANSI, set_attrs, set_env

import herdrlib
import new_workspace


class Screen(unittest.TestCase):
    def setUp(self):
        set_attrs(self, new_workspace, HOME="/home/dev", is_repo=lambda path: path.endswith("app"))

    def screen(self, filt="", agent="claude", names=(".", "app", "notes")):
        return new_workspace.screen("/home/dev/projects", list(names), 1, 0, filt, agent, set(), 10, 80)

    def lines(self, **kwargs):
        return ANSI.sub("", self.screen(**kwargs)).split("\n")

    def test_a_workspace_is_named_after_its_folder_and_the_home_folder_home(self):
        self.assertEqual(herdrlib.free_label("/home/dev/projects/app", set(), "/home/dev"), "app")
        self.assertEqual(herdrlib.free_label("/home/dev", set(), "/home/dev"), "home")   # never ~ or the user's name
        self.assertEqual(herdrlib.free_label("/", set(), "/home/dev"), "/")

    def test_cancel_and_open_buttons_end_the_screen_and_take_a_click(self):
        last = self.lines()[-1]
        self.assertTrue(last.rstrip().endswith("Cancel    Open"), last)
        row = new_workspace.FIRST_ROW + 3 + 1                                 # three folders shown, then a blank row
        column = last.index("Open") + 1
        self.assertEqual(new_workspace.hit(column, row, "~/projects", 80, 0, 3), ("button", "open"))
        self.assertEqual(new_workspace.hit(last.index("Cancel") + 1, row, "~/projects", 80, 0, 3), ("button", "cancel"))
        opened = new_workspace.clicking((0, column, row, True), 1, "claude", None, 10.0, "~/projects", 80, 0, 3)
        self.assertEqual(opened, (1, "claude", None, "open"))                # the folder chosen, opened

    def test_a_click_lands_on_the_toggle_or_a_folder_row(self):
        # the title row with the toggle at its right end, the filter row, then the folders from the top one shown
        title, width = "~/projects", 60
        toggle = 60 - len(" claude │ codex ") + 1                             # its first column, 1-based
        self.assertEqual(new_workspace.hit(toggle + 2, 1, title, width, 0, 3), ("agent", "claude"))
        self.assertEqual(new_workspace.hit(toggle + 12, 1, title, width, 0, 3), ("agent", "codex"))
        self.assertIsNone(new_workspace.hit(3, 1, title, width, 0, 3))         # the title itself
        self.assertEqual(new_workspace.hit(5, 3, title, width, 0, 3), ("row", 0))
        self.assertEqual(new_workspace.hit(5, 5, title, width, 4, 3), ("row", 6))
        self.assertIsNone(new_workspace.hit(5, 6, title, width, 0, 3))         # below the rows shown
        self.assertIsNone(new_workspace.hit(5, 2, title, width, 0, 3))         # the filter row

    def test_a_click_chooses_a_second_one_opens_and_the_wheel_moves(self):
        def press(row, now, chosen=0, last=None, button=0, pressed=True):
            return new_workspace.clicking((button, 5, row, pressed), chosen, "claude", last, now, "~/p", 60, 0, 3)
        chosen, agent, last, opened = press(4, 10.0)
        self.assertEqual((chosen, agent, opened), (1, "claude", None))
        self.assertEqual(press(4, 10.3, chosen, last)[3], "open")              # the same row again, at once: open
        self.assertEqual(press(4, 11.0, chosen, last)[3], None)                # too late: chosen again
        self.assertEqual(press(5, 10.3, chosen, last)[:1], (2,))               # another row: chosen
        self.assertEqual(press(4, 10.0, button=0, pressed=False)[0], 0)        # a release does nothing
        self.assertEqual(press(4, 10.0, chosen=1, button=65)[0], 2)            # the wheel down
        self.assertEqual(press(4, 10.0, chosen=1, button=64)[0], 0)            # and up
        toggle = 60 - len(" claude │ codex ") + 1
        switched = new_workspace.clicking((0, toggle + 12, 1, True), 0, "claude", None, 10.0, "~/p", 60, 0, 3)
        self.assertEqual(switched[1], "codex")

    def test_esc_goes_back_to_the_workspace_it_was_opened_from(self):
        calls = []

        def herdr(*args, **kwargs):
            calls.append(args)
            return {"workspaces": [{"workspace_id": "w1"}, {"workspace_id": "w2"}, {"workspace_id": "w9"}]}
        set_attrs(self, new_workspace, herdr=herdr)
        set_env(self, HERDR_CAME_FROM="w1")
        new_workspace.close_placeholder("w9", back=True)
        self.assertEqual([c for c in calls if c[0] == "workspace" and c[1] != "list"],
                         [("workspace", "focus", "w1"), ("workspace", "close", "w9")])
        calls.clear()
        new_workspace.close_placeholder("w9")                                   # a folder chosen: it is in front
        self.assertEqual([c for c in calls if c[0] == "workspace" and c[1] != "list"], [("workspace", "close", "w9")])

    def test_new_workspace_from_the_sidebar_starts_on_its_folder(self):
        # the sidebar's New Workspace: the folder's own row chosen in its parent, the rest as the new button shows it
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        for name in ("alpha", "beta", "gamma"):
            os.makedirs(os.path.join(tmp, name))
        folder, chosen = new_workspace.start_on(os.path.join(tmp, "beta"), tmp, [])
        self.assertEqual(folder, tmp)
        self.assertEqual(new_workspace.listing(folder, "", tmp, [])[chosen], "beta")
        self.assertEqual(new_workspace.start_on(None, tmp, []), (tmp, 0))                  # the new button
        self.assertEqual(new_workspace.start_on(os.path.join(tmp, "gone"), tmp, []), (tmp, 0))

    def test_the_title_is_the_folder(self):
        self.assertTrue(self.lines()[0].startswith("~/projects"))

    def test_the_agent_is_a_toggle_with_the_chosen_one_marked(self):
        first = self.screen().split("\n")[0]
        self.assertIn(new_workspace.INVERT + " claude " + new_workspace.RESET, first)
        self.assertNotIn(new_workspace.INVERT + " codex ", first)
        self.assertIn(new_workspace.INVERT + " codex " + new_workspace.RESET, self.screen(agent="codex").split("\n")[0])
        self.assertTrue(self.lines()[0].rstrip().endswith("codex"))              # on the right of the title row

    def test_the_filter_shows_only_while_typing(self):
        self.assertNotIn("filter", " ".join(self.lines()).lower())
        typed = self.lines(filt="no", names=("notes",))
        self.assertIn("no", typed[1])

    def test_one_short_line_for_the_keys_that_are_not_obvious(self):
        keys = [line for line in self.lines() if line.strip()][-1]
        self.assertIn("Tab", keys)
        self.assertIn("→", keys)
        for obvious in ("Enter", "Esc", "↑", "↓"):
            self.assertNotIn(obvious, keys)

    def test_no_helper_text_in_the_list(self):
        text = " ".join(self.lines())
        self.assertNotIn("(this folder)", text)
        self.assertIn("git", text)                                               # what a folder is: data, kept

    def test_a_repository_elsewhere_shows_under_home_as_tilde(self):
        shown = self.lines(names=("/home/dev/code/tool", ".", "app"))
        self.assertTrue(shown[2].strip().startswith("~/code/tool"), shown[2])

    def test_a_folder_name_cannot_send_terminal_codes(self):
        # a downloaded repository's folder name may hold escape codes (a clipboard write, a title): they show as ?
        evil = "\x1b]52;c;ZWNobyBoaQ==\x07app"
        shown = new_workspace.screen("/home/dev/pro\x1b]0;x\x07jects", [".", evil], 1, 0, "", "claude", set(), 10, 80)
        self.assertNotIn("\x1b]", shown)
        self.assertNotIn("\x07", shown)
        self.assertIn("?]52;c;ZWNobyBoaQ==?app", shown)

if __name__ == "__main__":
    unittest.main()


class Listing(unittest.TestCase):
    """The rows of a folder: in the start folder the repositories found elsewhere come first; typing filters
    what shows."""

    def setUp(self):
        set_attrs(self, new_workspace, HOME="/home/dev", subfolders=lambda path: ["app", "notes"])
        self.top, self.others = "/home/dev/projects", ["/home/dev/code/tool"]

    def rows(self, folder, filt=""):
        return new_workspace.listing(folder, filt, self.top, self.others)

    def test_the_start_folder_lists_the_repositories_elsewhere_first(self):
        self.assertEqual(self.rows(self.top), ["/home/dev/code/tool", ".", "app", "notes"])

    def test_another_folder_lists_only_its_own(self):
        self.assertEqual(self.rows("/home/dev/projects/app"), [".", "app", "notes"])

    def test_typing_filters_by_what_shows(self):
        self.assertEqual(self.rows(self.top, "to"), ["/home/dev/code/tool"])          # ~/code/tool
        self.assertEqual(self.rows(self.top, "no"), ["notes"])
        self.assertEqual(self.rows(self.top, "dev"), [])                               # the home folder shows as ~
