"""Tests for the sidebar's Changes view (src/plugins/sidebar/scm.py): the message field, Commit and its menu, the
changes, staging, Discard and a secret-looking file's commit only after a question, the graph, unusual states."""
import json
import os
import sys
import time
import unittest

from support import SRC

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from git import Change, Commit, Status  # noqa: E402
from scm import Entry, Gap, Scm, Section  # noqa: E402
from screen import Canvas, glyphs  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402


def text(canvas, y):
    return "".join(ch for ch, _ in canvas.rows[y])


def key(name, **mods):
    return Key("char", name, **mods) if len(name) == 1 else Key(name, **mods)


def changes():
    return Status(branch="main", upstream="origin/main", ahead=1, staged=[Change("src/new.py", "A")],
                  changes=[Change("src/app.py", "M"), Change("old.txt", "D"), Change("notes.local", "M"),
                           Change("draft.md", "?")])


def history(n=20):
    return [Commit(f"{i:07x}", f"commit number {i}", "dev", ("main", "origin/main") if i == 0 else (), i == 0)
            for i in range(n)]


class View(unittest.TestCase):
    def setUp(self):
        self.view = Scm(icons=False)
        self.status, self.graph = changes(), history()

    def draw(self, width=45, height=40, roomy=True):
        self.canvas = Canvas(width, height)
        self.view.draw(self.canvas, 0, height, self.status, self.graph, roomy)
        return self.canvas

    def rows(self):
        return [text(self.canvas, y) for y in range(self.canvas.height)]

    def shown(self):
        """Every row's text, joined: a question may wrap onto the next row."""
        return " ".join(line.strip() for line in self.rows() if line.strip())

    def row_of(self, part):
        return next(y for y, line in enumerate(self.rows()) if part in line)

    def at(self, part, offset=0):
        y = self.row_of(part)
        return text(self.canvas, y).index(part) + offset, y

    def click(self, part, button=0):
        x, y = self.at(part)
        return self.view.handle(Mouse("press", x, y, button))

    def press(self, *names):
        return [self.view.handle(key(name)) for name in names][-1]

    def target(self, name):
        return next((x0, y) for y, x0, _, target in self.canvas.regions if target == name)

    def test_the_list_follows_the_buttons_edge_and_its_sections_stand_apart(self):
        self.draw()
        rows = self.rows()
        edge = max(self.rows_where(5, "button")) + 1                        # the button's lower edge: its air
        self.assertEqual(self.row_of("▾ Staged changes"), edge + 1)
        for header in ("▾ Changes", "▾ Graph"):
            self.assertEqual(rows[self.row_of(header) - 1].strip(), "", header)

    def test_the_keys_and_the_mouse_pass_over_the_space_between_sections(self):
        self.draw()
        self.view.focus, self.view.list.index = "list", 1                  # src/new.py, the one staged file
        self.press("down")
        self.assertEqual(self.view.list.selected().title, "Changes")
        self.press("up")
        self.assertEqual(self.view.list.selected().change.path, "src/new.py")
        for name in ("end", "pageup", "home", "pagedown", "pageup"):
            self.press(name)
            self.assertIsInstance(self.view.list.selected(), (Section, Entry, Commit), name)
        self.draw()
        gap = self.row_of("▾ Changes") - 1
        self.assertIsNone(self.view.handle(Mouse("press", 5, gap, 0)))
        self.assertEqual([target for y, _, _, target in self.canvas.regions if y == gap], [])

    def test_a_choice_that_goes_away_never_leaves_the_space_chosen(self):
        # the second of two staged files is chosen and unstaged: the rebuilt list must not choose the empty row
        self.status = Status(branch="main", staged=[Change("a.py", "A"), Change("b.py", "A")],
                             changes=[Change("c.py", "M")])
        self.draw()
        self.view.focus, self.view.list.index = "list", 2
        self.status = Status(branch="main", staged=[Change("a.py", "A")],
                             changes=[Change("b.py", "M"), Change("c.py", "M")])
        self.draw()
        self.assertNotIsInstance(self.view.list.selected(), Gap)

    def bg(self, x, y):
        return self.canvas.rows[y][x][1].bg

    def rows_where(self, x, bg, last=12):
        return [y for y in range(last) if self.bg(x, y) == bg]

    def regions_of(self, name):
        return sorted({y for y, _, _, target in self.canvas.regions if target == name})

    def test_a_roomy_pane_gives_the_message_its_square_shape_and_the_commit_half_a_row_under_it(self):
        self.draw()
        w = self.canvas.width
        side, main = w - 6, w - 8                                          # the AI's and the mode's column; the message
        self.assertEqual(text(self.canvas, 0)[1:1 + main], "▄" * main)     # a half row of edge above
        self.assertEqual(self.rows_where(5, "input"), [1])                 # the text's row between the edges
        self.assertIn("Commit message", text(self.canvas, 1))
        self.assertEqual(text(self.canvas, 2)[1:1 + main], "▀" * main)     # and below
        self.assertEqual(text(self.canvas, 0)[side:side + 5], "▄" * 5)
        self.assertEqual(self.rows_where(side + 1, "selection", 4), [1])
        self.assertEqual(text(self.canvas, 1)[side + 2], "✦")               # in its middle cell
        self.assertEqual(self.regions_of("suggest"), [0, 1, 2])
        self.assertEqual(self.rows_where(5, "button"), [3])                # the commit button: no edge above, so
        self.assertIn("✓ Commit", text(self.canvas, 3))                     # half a row of air under the message
        self.assertEqual(text(self.canvas, 4)[1:1 + main], "▀" * main)     # its edge below
        self.assertEqual((text(self.canvas, 3)[side + 2], self.bg(side + 2, 3)), ("⌄", "button"))
        self.assertIsNone(self.bg(side - 1, 3))                             # its mode is a button of its own
        self.assertEqual((self.regions_of("commit"), self.regions_of("mode")), ([3, 4], [3, 4]))
        self.assertIn("Staged changes", text(self.canvas, 5))               # right under the button's edge

    def test_the_button_shows_the_focus_only_once_the_keys_brought_it_there(self):
        self.draw()
        label = self.rows_where(5, "button")[0]
        x = text(self.canvas, label).index("Commit")
        self.assertEqual(self.bg(x, label), "button")                       # opened, or clicked: no mark
        self.view.focus, self.view.list.index = "list", 0
        self.press("up")                                                    # from the list's top to the button
        self.draw()
        mark = self.canvas.rows[label][x][1]
        self.assertEqual((mark.fg, mark.bg), ("button", "button_text"))     # the label lit the other way round
        self.view.handle(Mouse("press", 2, label + 6, 0))
        self.draw()
        self.assertEqual(self.bg(x, label), "button")

    def test_a_nerd_font_icon_keeps_a_cell_of_air_before_the_name(self):
        self.view = Scm(icons=True)
        self.draw()
        line = text(self.canvas, self.row_of("draft.md"))
        name = line.index("draft.md")
        self.assertEqual(line[name - 2:name], "  ")
        self.assertNotEqual(line[name - 3], " ")
        header = text(self.canvas, self.row_of("Changes"))
        self.assertEqual(header[header.index("Changes") - 2:header.index("Changes")], "  ")   # after the chevron

    def test_the_graph_lines_up_with_the_files(self):
        self.view = Scm(icons=True)
        self.draw()
        file_icon = text(self.canvas, self.row_of("draft.md")).index("draft.md") - 3
        dot = text(self.canvas, self.row_of("commit number 1")).index("○")
        self.assertEqual(dot, file_icon)

    def test_a_linked_issue_shows_under_the_button_and_x_unlinks_it(self):
        self.view.linked = (42, "Login fails on Safari")
        self.draw()
        line = next(row for row in self.rows() if "Fixes #42" in row)
        self.assertIn("Fixes #42 Login fails on Safari", line)
        self.assertTrue(line.rstrip().endswith("×"))
        self.assertEqual(self.click("×"), Action("unlink", ()))
        self.view.linked = None
        self.draw()
        self.assertFalse(any("Fixes #" in row for row in self.rows()))

    def test_the_ai_button_is_codicons_sparkle(self):
        self.view = Scm(icons=True)
        self.draw()
        self.assertEqual(text(self.canvas, 1)[self.canvas.width - 4], "\uec10")       # Codicons' sparkle
        self.assertEqual(glyphs(False)["ai"], "✦")                         # without a Nerd Font

    def test_a_low_pane_keeps_them_to_one_row_each(self):
        self.draw(height=16, roomy=False)
        side = self.canvas.width - 6
        self.assertEqual((self.rows_where(5, "input"), self.rows_where(side + 2, "selection", 3)), ([0], [0]))
        self.assertEqual(self.rows_where(5, "button"), [2])                 # a row of air between them still
        self.assertEqual(self.row_of("▾ Staged changes"), 4)                 # and between the button and the list

    def test_the_counts(self):
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Staged changes")).rstrip().endswith("1"))
        y = self.row_of("▾ Changes")
        self.assertTrue(text(self.canvas, y).rstrip().endswith("4"))
        badge = self.canvas.rows[y][len(text(self.canvas, y).rstrip()) - 1][1]
        self.assertEqual((badge.fg, badge.bg), ("badge_text", "badge"))

    def test_the_name_is_plain_and_the_letter_colored(self):
        canvas = self.draw()
        x, y = self.at("app.py")
        self.assertEqual(canvas.rows[y][x][1].fg, "text")
        self.assertEqual(text(canvas, y)[42], "M")
        self.assertEqual(canvas.rows[y][42][1].fg, "modified")
        x, y = self.at("old.txt")
        self.assertTrue(canvas.rows[y][x][1].strike)
        self.assertEqual(text(canvas, y)[42], "D")
        self.assertEqual(text(canvas, self.row_of("draft.md"))[42], "U")
        self.assertEqual(canvas.rows[self.row_of("draft.md")][42][1].fg, "added")

    def test_the_mode_menu_and_the_remembered_mode(self):
        self.draw()
        self.view.handle(Mouse("press", *self.target("mode")))
        self.draw()
        for mode in ("Commit & Push", "Commit & Sync"):
            self.row_of(mode)
        self.assertEqual(self.click("Commit & Push"), Action("remember_mode", ("push",)))
        self.draw()
        self.assertIn("Commit & Push", text(self.canvas, self.rows_where(5, "button")[0]))   # the button's label row
        self.view.set_message("feat: add a thing")
        self.draw()
        self.assertEqual(self.click("Commit & Push"), Action("commit", ("feat: add a thing", "push", ())))
        self.assertEqual(Scm(mode="sync").mode, "sync")

    def test_an_empty_message_does_not_commit(self):
        self.draw()
        self.assertIsNone(self.view.handle(Mouse("press", *self.target("commit"))))
        self.draw()
        line = self.row_of("message is empty")
        self.assertEqual(self.canvas.rows[line][2][1].fg, "deleted")

    def test_typing_alt_enter_and_esc(self):
        self.draw()
        self.press("c")
        self.assertTrue(self.view.editing)
        for ch in "fix: a":
            self.press(ch)
        self.press("enter")
        for ch in "- b":
            self.press(ch)
        self.assertEqual(self.view.handle(key("enter", alt=True)), Action("commit", ("fix: a\n- b", "commit", ())))
        self.press("esc")
        self.assertFalse(self.view.editing)
        self.press("right")                                       # the mode menu holds the keys
        self.assertTrue(self.view.editing)
        self.press("esc")
        self.assertFalse(self.view.editing)
        self.press("x")                                           # any other letter types into the message
        self.assertTrue(self.view.editing)

    def test_a_staged_file_named_like_a_secret_is_committed_only_when_confirmed(self):
        self.status.staged.append(Change("deploy/.env", "A"))
        self.view.set_message("feat: deploy")
        self.draw()
        self.assertIsNone(self.view.handle(Mouse("press", *self.target("commit"))))
        self.draw()
        self.assertIn(".env looks like a secret. Commit it anyway?", self.shown())
        self.assertIsNone(self.press("enter"))                    # Cancel is the default
        self.assertIsNone(self.view.handle(key("enter", alt=True)))
        self.assertEqual(self.press("y"), Action("commit", ("feat: deploy", "commit", ())))

    def test_with_nothing_staged_a_change_named_like_a_secret_is_asked_about_too(self):
        self.status = Status(branch="main", changes=[Change("deploy/.env", "?"), Change("a.txt", "M")])
        self.draw()
        self.view.set_message("feat: deploy")
        self.assertIsNone(self.view.commit())
        self.draw()
        self.assertIn(".env looks like a secret", self.shown())

    def test_with_nothing_staged_a_commit_takes_the_changes_it_showed(self):
        """Only what the question about secrets saw: a file come since (an agent's .env) waits for the next commit."""
        self.status = Status(branch="main", changes=[Change("a.txt", "M"), Change("b.txt", "?"), Change("inner/", "?")])
        self.draw()
        self.view.set_message("feat: a and b")
        self.assertEqual(self.view.commit(), Action("commit", ("feat: a and b", "commit", ("a.txt", "b.txt"))))

    def test_a_busy_line_does_not_stop_a_commit(self):
        self.view.busy("Writing the message…")
        self.view.set_message("fix: mine")
        self.draw()
        self.assertEqual(self.view.handle(Mouse("press", *self.target("commit"))),
                         Action("commit", ("fix: mine", "commit", ())))

    def test_a_nested_repository_has_its_name(self):
        self.status = Status(branch="main", changes=[Change("inner/", "?")])
        self.draw()
        self.row_of("inner")
        self.press("esc", "down", "down", "d")
        self.draw()
        self.assertIn("Move inner to the Trash?", self.shown())

    def test_a_huge_list_answers_the_mouse_at_once(self):
        self.status = Status(branch="main", changes=[Change(f"fresh/f{i}.js", "?") for i in range(50_000)])
        self.draw()
        started = time.perf_counter()
        for x in range(10):
            self.view.handle(Mouse("move", x, 5))
            self.draw()
        self.assertLess((time.perf_counter() - started) / 10, 0.02)

    def test_suggest_by_the_star_or_a(self):
        self.draw()
        self.assertEqual(self.click("✦"), Action("suggest"))
        self.press("esc")
        self.assertEqual(self.press("A"), Action("suggest"))
        self.view.busy("Writing the message…")
        self.draw()
        self.row_of("Writing the message…")
        self.assertIsNone(self.press("A"))
        self.view.busy(None)
        self.draw()
        self.assertFalse(any("Writing" in line for line in self.rows()))

    def test_enter_stages_and_unstages_and_a_click_shows_the_diff(self):
        self.draw()
        self.press("esc", "down", "down")                         # the button, then the staged header, then new.py
        self.assertEqual(self.press("enter"), Action("unstage", (("src/new.py",),)))
        self.press("down", "down")                                # the Changes header, then app.py
        self.assertEqual(self.press("enter"), Action("stage", (("src/app.py",),)))
        self.assertEqual(self.click("app.py"), Action("preview_diff", ("src/app.py", False)))
        self.assertEqual(self.click("new.py"), Action("preview_diff", ("src/new.py", True)))

    def test_the_row_icons_show_on_hover(self):
        self.draw()
        self.assertFalse(any(target[0] == "stage" for _, _, _, target in self.canvas.regions
                             if isinstance(target, tuple)))
        x, y = self.at("app.py")
        self.view.handle(Mouse("move", x, y))
        self.draw()
        stage = next((x0, ry) for ry, x0, _, target in self.canvas.regions
                     if isinstance(target, tuple) and target[0] == "stage")
        self.assertEqual(self.view.handle(Mouse("press", *stage)), Action("stage", (("src/app.py",),)))
        self.view.handle(Mouse("move", *self.at("▾ Changes")))
        self.draw()
        stage_all = next((x0, ry) for ry, x0, _, target in self.canvas.regions
                         if isinstance(target, tuple) and target[0] == "stage")
        self.assertEqual(self.view.handle(Mouse("press", *stage_all)),
                         Action("stage", (("src/app.py", "old.txt", "notes.local", "draft.md"),)))

    def test_discard_asks_first(self):
        self.draw()
        self.press("esc", "down", "down", "down", "down")         # app.py
        self.assertIsNone(self.press("d"))
        self.draw()
        self.assertIn("Discard changes in app.py? This cannot be undone.", self.shown())
        self.assertIsNone(self.press("enter"))                    # Cancel is the default
        self.press("down", "down", "down", "d")                   # draft.md, untracked
        self.draw()
        self.assertIn("Move draft.md to the Trash?", self.shown())
        self.assertEqual(self.press("y"), Action("discard", (("draft.md",),)))

    def test_the_graph(self):
        canvas = self.draw()
        head = self.row_of("commit number 0")
        self.assertIn("◉", text(canvas, head))
        self.assertIn("origin/main", text(canvas, head))
        self.assertIn("○", text(canvas, self.row_of("commit number 19")))
        self.assertEqual(self.click("commit number 7"), Action("preview_commit", ("0000007",)))

    def test_each_files_letter_stands_under_its_sections_count(self):
        self.draw()
        last = {name: len(self.rows()[self.row_of(name)].rstrip()) - 1 for name in ("▾ Staged changes", "▾ Changes",
                                                                                   "new.py", "app.py")}
        self.assertEqual(last["new.py"], last["▾ Staged changes"])
        self.assertEqual(last["app.py"], last["▾ Changes"])

    def test_a_section_folded_is_kept_by_the_app(self):
        self.draw()
        self.assertEqual(self.click("▾ Graph"), Action("remember_folded", (["graph"],)))
        self.draw()
        self.assertEqual(self.click("▸ Graph"), Action("remember_folded", ([],)))
        self.assertEqual(Scm(icons=False, folded=["graph", "elsewhere"]).folded, {"graph"})

    def test_a_new_version_comes_back_to_the_same_rows(self):
        self.draw()
        self.view.focus = "list"
        self.press("end")                                                    # draft.md
        self.press("down", "down", "down")                                   # the Graph: commit number 1
        kept = json.loads(json.dumps(self.view.kept()))                      # as the handover file carries it
        self.view = Scm(icons=False)
        self.view.take(kept)
        self.draw()
        self.assertEqual((self.view.focus, self.view.graph_list.selected().subject), ("graph", "commit number 1"))
        self.assertEqual(self.view.list.selected().change.path, "draft.md")

    def test_the_graph_stays_at_the_panels_bottom(self):
        self.draw()
        self.assertEqual(self.row_of("commit number 19"), self.canvas.height - 1)
        between = range(self.row_of("draft.md") + 1, self.row_of("▾ Graph"))
        self.assertGreater(len(between), 1)                                   # few changes: the room stays empty
        self.assertTrue(all(not self.rows()[y].strip() for y in between))

    def test_many_changes_leave_the_graph_its_room(self):
        self.status = Status(branch="main", changes=[Change(f"f{i}.txt", "M") for i in range(200)])
        self.draw()
        graph = self.row_of("▾ Graph")
        self.assertGreaterEqual(self.canvas.height - graph, 10)              # a third of the list's room at least
        self.assertEqual(self.row_of("commit number 0"), graph + 1)
        self.view.focus = "list"
        self.press("end")                                                    # the changes scroll on their own
        self.draw()
        self.assertIn("f199.txt", self.shown())
        self.assertEqual(self.row_of("▾ Graph"), graph)

    def test_the_keys_go_from_the_changes_into_the_graph_and_back(self):
        self.draw()
        self.view.focus = "list"
        self.press("end")                                                    # the last change: draft.md
        self.assertEqual(self.view.list.selected().change.path, "draft.md")
        self.press("down")
        self.assertEqual((self.view.focus, self.view.graph_list.selected().title), ("graph", "Graph"))
        self.press("down")
        self.assertEqual(self.press("enter"), Action("preview_commit", ("0000000",)))
        self.press("up", "up")
        self.assertEqual((self.view.focus, self.view.list.selected().change.path), ("list", "draft.md"))

    def test_the_unusual_states(self):
        self.status = Status(branch="main", staged=[Change("a.txt", "A")])          # no commit yet
        self.graph = []
        self.draw()
        self.row_of("Graph")
        self.status = Status(branch=None, changes=[Change("a.txt", "M")])           # detached
        self.draw()
        self.row_of("detached HEAD")
        self.status = Status(branch="main", changes=[Change("a.txt", "U")])         # a conflict
        canvas = self.draw()
        y = self.row_of("a.txt")
        self.assertEqual((text(canvas, y)[42], canvas.rows[y][42][1].fg), ("!", "conflict"))
        self.status = Status(error="fatal: not a git repository (or any of the parent directories): .git")
        self.draw()
        self.assertEqual(text(self.canvas, 0).strip(), "Not a git repository")
        self.assertFalse(any("Commit" in line for line in self.rows()))
        self.status = Status(error="git is not installed")
        self.draw()
        self.assertEqual(text(self.canvas, 0).strip(), "git is not installed")
        self.assertIsNone(self.press("A"))

    def test_nothing_runs_past_the_edge_at_24_columns(self):
        self.status.changes.append(Change("src/a-very-long-file-name-for-a-narrow-pane.py", "M"))
        canvas = self.draw(width=24)
        y = self.row_of("a-very")
        self.assertIn("…", text(canvas, y))
        self.assertEqual(text(canvas, y)[21], "M")
        self.assertTrue(text(canvas, self.rows_where(5, "button")[0]).rstrip().endswith("⌄"))
        self.assertIn("…", text(canvas, self.row_of("commit number 0")))


if __name__ == "__main__":
    unittest.main()
