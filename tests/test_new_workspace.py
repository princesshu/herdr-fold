"""Tests for new_workspace.py's folder picker screen: the folder as title, a claude │ codex toggle marking the chosen
agent, the filter only while typing, and one short line for the keys that are not obvious (Tab, →).
"""
import unittest

from support import ANSI, set_attrs

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
