"""Tests for new_workspace.py's folder picker: a tree as the sidebar's Files view shows it, under the folder as title
and a claude │ codex toggle; the filter only while typing; the keys, the mouse, Cancel and Open; and where it starts
(projects.py): unasked, at the folder holding the most git repositories, under a temporary home."""
import os
import shutil
import tempfile
import unittest

from support import ANSI, set_attrs, set_env

import herdrlib
import new_workspace
import widgets  # noqa: E402  the sidebar's, on the path herdrlib gives
from icons import glyphs  # noqa: E402  the sidebar's, on the path herdrlib gives

OPEN, CLOSED = glyphs(False)["open"], glyphs(False)["closed"]     # its folds without a Nerd Font
import projects


class Tree(unittest.TestCase):
    """The picker as a tree, as the sidebar's Files view: the folder on top, open, its subfolders under it; → opens a
    folder or steps into an open one, ← closes one or steps to its parent, and on the top row goes up a folder."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = os.path.join(self.tmp, "projects")
        for rel in ("archives/old", "archives/site", "claude", ".hidden"):
            os.makedirs(os.path.join(self.root, rel))
        self.picker = new_workspace.Picker(self.root)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def shown(self):
        return [(row.name, row.depth, row.open) for row in self.picker.rows()]

    def press(self, *keys):
        return [self.picker.press(key, 10) for key in keys][-1]

    def test_the_folder_on_top_open_its_subfolders_closed_under_it_hidden_last(self):
        self.assertEqual(self.shown(), [("projects", 0, True), ("archives", 1, False), ("claude", 1, False),
                                        (".hidden", 1, False)])
        self.assertEqual(self.picker.chosen_path(), self.root)                 # Enter opens the folder itself

    def test_right_opens_a_folder_then_steps_into_it(self):
        self.press("\x1b[B", "\x1b[C")
        self.assertEqual(self.shown()[1:4], [("archives", 1, True), ("old", 2, False), ("site", 2, False)])
        self.press("\x1b[C")
        self.assertEqual(self.picker.chosen_path(), self.path("archives", "old"))

    def test_left_steps_to_the_parent_then_closes_it(self):
        self.press("\x1b[B", "\x1b[C", "\x1b[C", "\x1b[D")
        self.assertEqual(self.picker.chosen_path(), self.path("archives"))
        self.press("\x1b[D")
        self.assertEqual(self.shown()[1], ("archives", 1, False))

    def test_left_on_the_top_row_goes_up_a_folder_this_one_open_and_chosen(self):
        self.press("\x1b[D")
        self.assertEqual(self.picker.root, self.tmp)
        self.assertEqual(self.picker.chosen_path(), self.root)
        self.assertIn(("projects", 1, True), self.shown())

    def test_enter_opens_the_chosen_folder_esc_cancels_or_first_clears_what_was_typed(self):
        self.assertEqual(self.press("\x1b[B", "\r"), "open")
        self.assertEqual(self.picker.chosen_path(), self.path("archives"))
        self.press("c", "l")
        self.assertEqual(self.shown(), [("claude", 1, False)])                  # the rows shown, filtered
        self.assertIsNone(self.press("\x1b"))
        self.assertEqual(len(self.shown()), 4)
        self.assertEqual(self.press("\x1b"), "cancel")

    def test_tab_switches_the_agent(self):
        self.press("\t")
        self.assertEqual(self.picker.agent, "codex")

    def test_new_workspace_from_the_sidebar_starts_on_its_folder_in_its_parent(self):
        picker = new_workspace.Picker(self.tmp, self.path("claude"))
        self.assertEqual((picker.root, picker.chosen_path()), (self.root, self.path("claude")))
        self.assertEqual(new_workspace.Picker(self.root, self.path("gone")).chosen_path(), self.root)


class Mouse(unittest.TestCase):
    """A click chooses a row, a second one on it at once opens it, a click on its chevron opens or closes it; the toggle
    chooses the agent, the buttons open or cancel, the wheel moves."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in ("archives/old", "claude"):
            os.makedirs(os.path.join(self.tmp, "projects", rel))
        self.picker = new_workspace.Picker(os.path.join(self.tmp, "projects"))
        set_attrs(self, new_workspace, icons_on=lambda state_dir: False)

    def lines(self):
        return ANSI.sub("", new_workspace.screen(self.picker, set(), 10, 60)).split("\n")

    def click(self, column, row, now=10.0, button=0):
        return self.picker.click((button, column, row, True), now, 60, 10)

    def row_of(self, name):
        return next(n for n, line in enumerate(self.lines(), 1) if f" {name}" in line and n > 2)

    def test_a_click_chooses_a_second_one_at_once_opens_it(self):
        row = self.row_of("claude")
        self.assertIsNone(self.click(10, row))
        self.assertTrue(self.picker.chosen_path().endswith("claude"))
        self.assertEqual(self.click(10, row, 10.3), "open")
        self.assertIsNone(self.click(10, row, 11.0))                           # too late: chosen again

    def test_a_click_on_the_mark_opens_or_closes_the_folder(self):
        row = self.row_of("archives")
        mark = self.lines()[row - 1].index(CLOSED) + 1
        shows_old = lambda: any(line.rstrip().endswith(" old") for line in self.lines()[2:])  # noqa: E731
        self.click(mark, row)
        self.assertTrue(shows_old())
        self.click(mark, row, 20.0)
        self.assertFalse(shows_old())

    def test_a_folder_opened_turns_its_chevron_through_45_degrees(self):
        now = [5.0]
        set_attrs(self, widgets, TURN=0.08, TURNS=widgets.Turns(clock=lambda: now[0]))
        row = self.row_of("archives")
        self.click(self.lines()[row - 1].index(CLOSED) + 1, row)
        self.assertIn("⌟", self.lines()[row - 1])
        now[0] += widgets.TURN
        self.assertIn(OPEN, self.lines()[row - 1])

    def test_the_toggle_the_buttons_and_the_wheel(self):
        lines = self.lines()
        self.click(lines[0].index("codex") + 1, 1)
        self.assertEqual(self.picker.agent, "codex")
        buttons = len(lines)
        self.assertEqual(self.click(lines[-1].index("Open") + 1, buttons), "open")
        self.assertEqual(self.click(lines[-1].index("Cancel") + 1, buttons), "cancel")
        self.click(1, 4, button=65)
        self.assertEqual(self.picker.chosen, 1)
        self.click(1, 4, button=64)
        self.assertEqual(self.picker.chosen, 0)
        self.assertIsNone(self.click(5, 2))                                    # the filter row: nothing


class Screen(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel in ("app/.git", "notes"):
            os.makedirs(os.path.join(self.tmp, "projects", rel))
        set_attrs(self, new_workspace, HOME=self.tmp, icons_on=lambda state_dir: False)
        self.picker = new_workspace.Picker(os.path.join(self.tmp, "projects"))

    def screen(self, **settings):
        for name, value in settings.items():
            setattr(self.picker, name, value)
        return new_workspace.screen(self.picker, {os.path.join(self.tmp, "projects", "app")}, 10, 80)

    def lines(self, **settings):
        return ANSI.sub("", self.screen(**settings)).split("\n")

    def test_a_workspace_is_named_after_its_folder_and_the_home_folder_home(self):
        self.assertEqual(herdrlib.free_label("/home/dev/projects/app", set(), "/home/dev"), "app")
        self.assertEqual(herdrlib.free_label("/home/dev", set(), "/home/dev"), "home")   # never ~ or the user's name
        self.assertEqual(herdrlib.free_label("/", set(), "/home/dev"), "/")

    def test_the_title_is_the_folder_the_tree_under_it_as_files_shows_it(self):
        lines = self.lines()
        self.assertTrue(lines[0].startswith(" ~/projects"))
        self.assertEqual([line.rstrip() for line in lines[2:5]],
                         [f" {OPEN} projects", f"   {CLOSED} app" + " " * 42 + "git open", f"   {CLOSED} notes"])

    def test_the_agent_is_a_toggle_with_the_chosen_one_marked(self):
        first = self.screen().split("\n")[0]
        self.assertIn(new_workspace.INVERT + " claude " + new_workspace.RESET, first)
        self.assertNotIn(new_workspace.INVERT + " codex ", first)
        self.assertIn(new_workspace.INVERT + " codex " + new_workspace.RESET, self.screen(agent="codex").split("\n")[0])
        self.assertTrue(self.lines()[0].rstrip().endswith("codex"))              # on the right of the title row

    def test_the_filter_shows_only_while_typing(self):
        self.assertNotIn("filter", " ".join(self.lines()).lower())
        self.assertIn("no", self.lines(filt="no")[1])

    def test_one_short_line_for_the_keys_that_are_not_obvious_and_the_buttons(self):
        keys = self.lines()[-1]
        self.assertIn("Tab", keys)
        self.assertIn("←", keys)
        for obvious in ("Enter", "Esc", "↑", "↓"):
            self.assertNotIn(obvious, keys)
        self.assertTrue(keys.rstrip().endswith("Cancel    Open"), keys)

    def test_the_title_and_the_toggle_keep_a_cell_clear_at_each_edge(self):
        first = self.lines()[0]
        self.assertEqual(len(first), 80)
        self.assertTrue(first.startswith(" ~/projects") and first.endswith(" codex  "), first)
        self.assertTrue(self.lines(filt="no")[1].startswith(" no"))

    def test_every_row_fits_a_narrow_window(self):
        # the popup is 70% of the terminal: a half-screen Ghostty window gives it under 60 cells
        lines = ANSI.sub("", new_workspace.screen(self.picker, {os.path.join(self.tmp, "projects", "app")}, 10, 50))
        self.assertLessEqual(max(len(line) for line in lines.split("\n")), 50)
        self.assertIn("git open", lines)

    def test_no_helper_text_and_no_dot_row(self):
        text = " ".join(self.lines())
        self.assertNotIn("(this folder)", text)
        self.assertNotIn(" . ", text)
        self.assertIn("git", text)                                               # what a folder is: data, kept

    def test_a_folder_name_cannot_send_terminal_codes(self):
        # a downloaded repository's folder name may hold escape codes (a clipboard write, a title): they show as ?
        os.makedirs(os.path.join(self.tmp, "projects", "\x1b]52;c;ZWNobyBoaQ==\x07app"))
        shown = self.screen()
        self.assertNotIn("\x1b]", shown)
        self.assertNotIn("\x07", shown)
        self.assertIn("?]52;c;ZWNobyBoaQ==?app", shown)

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


class Projects(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def repo(self, rel):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.join(path, ".git"))
        return path

    def found(self, **kwargs):
        return sorted(projects.repositories([self.home], **kwargs))

    def test_the_folder_holding_the_most_repositories_is_the_start(self):
        self.repo("srv/crm/api")
        self.repo("srv/crm/web")
        self.repo("code/tool")
        self.assertEqual(projects.start(self.found()), os.path.join(self.home, "srv", "crm"))

    def test_a_tie_goes_to_the_folder_nearer_the_root(self):
        self.repo("work/old/one")
        self.repo("code/two")
        self.assertEqual(projects.start(self.found()), os.path.join(self.home, "code"))

    def test_without_repositories_documents_or_else_home(self):
        self.assertEqual(projects.start([]), self.home)
        os.makedirs(os.path.join(self.home, "Documents"))
        self.assertEqual(projects.start([]), os.path.join(self.home, "Documents"))

    def test_hidden_bulky_and_guarded_folders_are_not_searched(self):
        # macOS asks for Desktop and Downloads with a question of its own: searching there would raise it
        for rel in (".cache/a", "node_modules/b", "Library/c", "Desktop/d", "Downloads/e"):
            self.repo(rel)
        self.assertEqual(self.found(), [])

    def test_never_inside_a_repository_but_inside_a_home_kept_in_git(self):
        os.makedirs(os.path.join(self.home, ".git"))                      # dotfiles in git: still searched below
        app = self.repo("code/app")
        self.repo("code/app/plugins/inner")
        self.assertEqual(self.found(), [app])

    def test_only_a_few_levels_deep(self):
        near = self.repo("a/b/c/near")
        self.repo("a/b/c/d/far")
        self.assertEqual(self.found(), [near])

    def test_a_repository_someone_else_owns_is_left_out(self):
        # on a shared server another user could put repositories under /srv to steer the picker to code of theirs: only
        # the user's own and root's count (these are the test's own, so a different user id makes them someone else's)
        self.repo("code/app")
        set_attrs(self, projects.os, getuid=lambda: os.stat(self.home).st_uid + 1)
        self.assertEqual(self.found(), [])

    def test_the_search_stops_when_its_time_is_up(self):
        self.repo("code/app")
        self.assertEqual(self.found(budget=0), [])

    def test_linux_searches_the_server_folders_too(self):
        self.assertEqual(projects.roots("linux"), [self.home, "/srv", "/opt", "/var/www"])
        self.assertEqual(projects.roots("darwin"), [self.home])


if __name__ == "__main__":
    unittest.main()
