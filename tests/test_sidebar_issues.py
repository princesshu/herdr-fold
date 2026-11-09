"""Tests for the sidebar's Issues view (src/plugins/sidebar/issues.py), laid out and keyed like GitHub's issue list,
with the priority from GitHub's Priority field, else a priority label, a severity label or a word alone; and for its own
part (issue_work.py): the latest answer kept for the repository's other sidebars, and what a tab of its opens."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import github  # noqa: E402
import issue_work  # noqa: E402
from github import Issue, Listing, Query  # noqa: E402
from issues import Issues  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

CARET = glyphs(True)["open"]                  # a menu's caret: the folds' chevron

NOW = github.parse_time("2026-10-24T12:00:00Z")
SAFARI = Issue(42, "Login fails on Safari", ("bug", "ui"), ("dev",), "2026-10-22T10:00:00Z", "OPEN",
               "https://github.com/acme/app/issues/42")
DARK = Issue(38, "Add a dark mode toggle", (), (), "2026-10-19T09:00:00Z", "OPEN",
             "https://github.com/acme/app/issues/38")
TWO = Listing((SAFARI, DARK))


class View(unittest.TestCase):
    def setUp(self):
        self.view = Issues(now=lambda: NOW)

    def draw(self, width=45, height=16, roomy=False):
        self.canvas = Canvas(width, height)
        self.view.draw(self.canvas, 0, height, roomy)
        return self.canvas

    def row_of(self, part):
        return next(y for y in range(self.canvas.height) if part in text(self.canvas, y))

    def click(self, part, y=None):
        y = self.row_of(part) if y is None else y
        return self.view.handle(Mouse("press", text(self.canvas, y).index(part), y))

    def press(self, name, char=""):
        return self.view.handle(Key(name, char))

    def type(self, word):
        for ch in word:
            self.press("char", ch)

    def shown(self, listing=TWO, query=Query()):
        self.view.ask(query)
        self.view.show(listing, query)
        return self.draw()

    def numbers(self):
        """The issues shown, top to bottom."""
        return [n for _, n in sorted((y, issue.number) for issue in self.view.list.items
                                     for y in [self.row_of(f"#{issue.number} ")])]

    def test_open_issues_come_by_priority_then_by_their_last_change(self):
        low = Issue(50, "Typo in the footer", ("priority: low",), (), "2026-10-23T10:00:00Z", "OPEN", "")
        urgent = Issue(51, "Payments are down", ("P0",), (), "2026-10-18T10:00:00Z", "OPEN", "")
        high = Issue(52, "Slow search", ("high priority", "perf"), (), "2026-10-17T10:00:00Z", "OPEN", "")
        medium = Issue(53, "Old logo", ("Priority/Medium",), (), "2026-10-16T10:00:00Z", "OPEN", "")
        for query in (Query(), Query(assigned=True)):
            self.view.ask(query)
            self.view.show(Listing((SAFARI, low, urgent, DARK, high, medium)), query)   # gh's: latest change first
            self.draw(height=20)
            order = sorted((self.row_of(f"#{n} "), n) for n in (42, 38, 50, 51, 52, 53))
            self.assertEqual([n for _, n in order], [51, 52, 53, 50, 42, 38], query)

    def test_a_new_answer_keeps_the_chosen_issue_chosen(self):
        # the list asked for again in the background: an issue new above the chosen one does not move the choice onto
        # another (t would hand that one to the agent)
        self.shown()
        self.view.list.index = self.view.list.items.index(DARK)
        urgent = Issue(51, "Checkout is down", ("priority: high",), (), "2026-10-24T11:00:00Z", "OPEN", "")
        self.shown(Listing((urgent, SAFARI, DARK)))
        self.assertEqual(self.view.list.selected().number, 38)

    def test_closed_issues_keep_the_order_of_their_last_change(self):
        crash = Issue(60, "Old crash", ("P0",), (), "2026-10-10T10:00:00Z", "CLOSED", "")
        typo = Issue(61, "Old typo", (), (), "2026-10-12T10:00:00Z", "CLOSED", "")
        self.shown(Listing((typo, crash)), Query("closed"))
        self.assertLess(self.row_of("#61 "), self.row_of("#60 "))

    def test_a_priority_marks_its_issue_and_its_label_in_its_color(self):
        urgent = Issue(51, "Payments are down", ("bug", "urgent"), (), "2026-10-18T10:00:00Z", "OPEN", "")
        self.shown(Listing((urgent, DARK)))
        y = self.row_of("#51 ")
        self.assertEqual([self.canvas.rows[r][0] for r in (y, y + 1)], [("▌", self.canvas.rows[y][0][1])] * 2)
        self.assertEqual({self.canvas.rows[r][0][1].fg for r in (y, y + 1)}, {"deleted"})
        self.assertEqual(self.canvas.rows[y][1][1].fg, "deleted")                  # its number too
        details = text(self.canvas, y + 1)
        self.assertEqual(self.canvas.rows[y + 1][details.index("urgent")][1].fg, "deleted")
        self.assertEqual(self.canvas.rows[y + 1][details.index("bug")][1].fg, "muted")
        dark = self.row_of("#38 ")
        self.assertEqual(self.canvas.rows[dark][0][0], " ")                        # no priority: no mark
        self.assertEqual(self.canvas.rows[dark][1][1].fg, "accent")                # and its number as ever

    def test_each_priority_has_its_color_as_a_traffic_light(self):
        # red, yellow, green: three colors every theme keeps apart (GitHub Dark's high and medium were one color)
        for label, role in (("critical", "deleted"), ("P1", "deleted"), ("priority: high", "deleted"),
                            ("priority: medium", "modified"), ("Low", "added")):
            self.view = Issues(now=lambda: NOW)
            self.shown(Listing((Issue(9, "Something", (label,), (), "2026-10-22T10:00:00Z", "OPEN", ""),)))
            y = self.row_of("#9 ")
            self.assertEqual((self.canvas.rows[y][0][1].fg, self.canvas.rows[y][1][1].fg), (role, role), label)

    def test_githubs_priority_field_shows_first_in_its_color(self):
        # an organization's Priority field (Urgent, High, Medium, Low) is GitHub's own: before the labels
        self.shown(Listing((Issue(71, "Payments down", ("bug",), (), "2026-10-18T10:00:00Z", "OPEN", "", "Urgent"),)))
        y = self.row_of("#71 ")
        details = text(self.canvas, y + 1)
        self.assertTrue(details[1 + len("#71 "):].startswith("Urgent, bug"), details)
        self.assertEqual(self.canvas.rows[y + 1][details.index("Urgent")][1].fg, "deleted")

    def test_the_search_field_and_its_filters_button_then_open_and_closed(self):
        self.draw()
        field = self.row_of("Search issues")
        self.assertTrue(text(self.canvas, field).rstrip().endswith(f"Filters {CARET}"))
        states = text(self.canvas, self.row_of("Open"))
        self.assertGreater(self.row_of("Open"), field)
        self.assertLess(states.index("Open"), states.index("Closed"))
        self.assertNotIn("Mine", states)                                    # GitHub's: a filter, not a state
        self.assertEqual(self.view.ask(), Action("load_issues", (Query(),)))

    def test_while_asking_it_says_so(self):
        self.view.ask()
        self.draw()
        self.row_of("Loading issues…")

    def test_the_arrows_switch_open_and_closed_and_ask_again(self):
        self.assertEqual(self.press("right"), Action("load_issues", (Query("closed"),)))
        self.assertIsNone(self.press("right"))                         # the last one stays
        self.assertEqual(self.press("left"), Action("load_issues", (Query(),)))

    def test_a_state_under_the_mouse_lights_up(self):
        self.draw()
        y = self.row_of("Closed")
        x = text(self.canvas, y).index("Closed")
        self.view.handle(Mouse("move", x, y, 3))
        self.draw()
        style = self.canvas.rows[y][x][1]
        self.assertEqual((style.fg, style.bg), ("text", "hover"))
        chosen = self.canvas.rows[y][text(self.canvas, y).index("Open")][1]
        self.assertEqual(chosen.bg, "button")                                   # the chosen one stays filled

    def test_a_click_on_a_state(self):
        self.draw()
        self.assertEqual(self.click("Closed"), Action("load_issues", (Query("closed"),)))

    def test_two_rows_an_issue(self):
        self.shown()
        y = self.row_of("#42 Login fails on Safari")
        below = text(self.canvas, y + 1)
        for part in ("bug, ui", "@dev", "2d"):
            self.assertIn(part, below)
        y = self.row_of("#38 Add a dark mode toggle")
        self.assertEqual(text(self.canvas, y + 1).split(), ["5d"])

    def test_an_answer_for_another_query_is_dropped(self):
        self.press("right")                                             # Closed is being asked for
        self.view.show(TWO, Query())
        self.draw()
        self.assertFalse(any("#42" in text(self.canvas, y) for y in range(16)))

    def test_empty_and_failed_answers_in_one_line(self):
        for query, said in ((Query(), "No open issues"), (Query("closed"), "No closed issues"),
                            (Query(assigned=True), "No issues match")):
            self.shown(Listing(()), query)
            self.row_of(said)
        self.shown(Listing(error=github.SIGNED_OUT))
        self.row_of(github.SIGNED_OUT[:30])

    def test_enter_previews_the_chosen_one(self):
        self.shown()
        self.assertEqual(self.press("enter"), Action("preview_issue", (SAFARI,)))
        self.press("down")
        self.assertEqual(self.press("enter"), Action("preview_issue", (DARK,)))

    def test_the_keys_on_an_issue_githubs_and_herdr_folds_own(self):
        self.shown()
        for char, action in (("c", Action("new_issue", ())), ("o", Action("preview_issue", (SAFARI,))),   # GitHub's
                             ("t", Action("issue_to_agent", (SAFARI,))), ("b", Action("issue_web", (SAFARI,))),
                             ("r", Action("issue_comment", (SAFARI,))), ("R", Action("load_issues", (Query(),)))):
            self.assertEqual(self.press("char", char), action, char)
        for char in ("n", "m"):                                    # no longer keys: c makes one, the menu assigns
            self.assertIsNone(self.press("char", char), char)

    def test_slash_searches_the_issues_shown(self):
        # GitHub's / (and s, and Ctrl+/): typing narrows the list at once, letters are typed, not keys
        self.shown()
        for key in (Key("char", "/"), Key("char", "s"), Key("char", "\x7f", ctrl=True)):
            self.view.searching = False
            self.view.handle(key)
            self.assertTrue(self.view.editing, key)
        for word, found in (("dark", [38]), ("#42", [42]), ("ui", [42]), ("@dev", [42]), ("safari bug", [42])):
            self.view.field.clear()
            self.type(word)
            self.draw()
            self.assertEqual(self.numbers(), found, word)
        self.assertIsNone(self.press("enter"))                              # back to the list, the search kept
        self.assertFalse(self.view.editing)
        self.assertEqual(self.press("char", "t"), Action("issue_to_agent", (SAFARI,)))
        self.press("char", "/")
        self.type("nothing like it")
        self.draw()
        self.row_of("No issues match")
        self.press("esc")                                                   # cleared, and back to the list
        self.draw()
        self.assertEqual((self.view.editing, self.numbers()), (False, [42, 38]))

    def test_the_filters_menu_asks_github_and_narrows_by_priority(self):
        urgent = Issue(51, "Payments are down", ("bug",), (), "2026-10-18T10:00:00Z", "OPEN", "", "Urgent")
        high = Issue(52, "Slow search", ("priority: high",), (), "2026-10-17T10:00:00Z", "OPEN", "")
        self.shown(Listing((urgent, SAFARI, high)))
        self.assertIsNone(self.press("char", "a"))                          # GitHub's a: the assignee filter
        self.assertEqual(self.view.menu.menu.choices,
                         ["  Assigned to me", "  Created by me", "✓ Any priority", "  ● Urgent", "  ● High",
                          "  ● Medium", "  ● Low", "✓ Any label", "  bug", "  priority: high", "  ui"])
        self.assertEqual(self.press("enter"), Action("load_issues", (Query(assigned=True),)))
        self.view.show(Listing((urgent, SAFARI, high)), Query(assigned=True))
        self.press("char", "u")                                             # the author filter
        self.assertEqual(self.view.menu.menu.choices[self.view.menu.menu.index], "  Created by me")
        self.press("esc")
        self.press("char", "l")                                             # the labels
        self.assertEqual(self.view.menu.menu.choices[self.view.menu.menu.index], "✓ Any label")
        self.press("down")
        self.assertEqual(self.press("enter"), Action("load_issues", (Query(assigned=True, label="bug"),)))
        self.view.show(Listing((urgent, SAFARI, high)), Query(assigned=True, label="bug"))
        self.draw()
        self.view.open_filters("priority")
        for _ in range(2):
            self.press("down")
        self.assertIsNone(self.press("enter"))                              # High: shown at once, not asked
        self.draw()
        self.assertEqual(self.numbers(), [52])
        field = text(self.canvas, self.row_of("Search issues"))
        self.assertIn(f"● High · me · bug {CARET}", field)
        self.assertEqual(self.canvas.rows[self.row_of("Search issues")][field.index("●")][1].fg, "deleted")

    def test_a_click_on_the_field_and_on_the_filters_button(self):
        self.shown()
        self.assertIsNone(self.click("Search issues"))
        self.assertTrue(self.view.searching)
        self.assertIsNone(self.click("Filters"))
        self.assertFalse(self.view.searching)
        self.assertIsNotNone(self.view.menu)
        self.draw()
        y = self.row_of("Created by me")
        self.assertEqual(self.click("Created by me", y), Action("load_issues", (Query(authored=True),)))

    def test_the_filters_menu_opens_under_the_field_their_right_edges_in_one_line(self):
        for roomy in (False, True):                                         # a tall field has a border row below
            self.draw(roomy=roomy)
            self.view.open_filters()
            self.draw(roomy=roomy)
            field = self.row_of("Search issues")
            last = field + (1 if roomy else 0)                              # the field's last row
            edge = max(x for x, (_, style) in enumerate(self.canvas.rows[field]) if style.bg == "input")
            top = next(y for y in range(self.canvas.height) if "┌" in text(self.canvas, y))
            self.assertEqual(top, last + 1, roomy)                          # right under the whole field
            self.assertEqual(text(self.canvas, top).index("┐"), edge, roomy)   # its right edge with the field's
            self.view.close_menu()

    def test_its_menu_closes_when_the_sidebar_closes_every_menu(self):
        self.shown()
        self.press("char", "l")
        self.assertIsNotNone(self.view.menu)
        self.view.close_menu()                                              # a click in another pane
        self.draw()
        self.assertFalse(any("┐" in text(self.canvas, y) for y in range(self.canvas.height)))
        self.assertFalse(self.view.editing)                                 # the keys back to the list

    def test_a_right_click_on_an_issue_offers_everything_assign_to_me_too(self):
        self.shown()
        y = self.row_of("#38")
        self.assertIsNone(self.view.handle(Mouse("press", 5, y, 2)))
        self.assertEqual(self.view.menu.menu.choices,
                         ["Open", "Open in the browser", "To the agent", "Reply", "Assign to me", "Close…"])
        self.draw()
        self.assertEqual(self.click("Assign to me", self.row_of("Assign to me")),
                         Action("issue_change", (DARK, "assign")))

    def test_x_asks_before_closing_or_reopening(self):
        self.shown()
        self.assertIsNone(self.press("char", "x"))
        self.assertTrue(self.view.editing)
        self.draw()
        self.row_of("Close #42?")
        self.assertEqual(self.press("char", "y"), Action("issue_change", (SAFARI, "close")))
        self.assertFalse(self.view.editing)
        closed = Issue(7, "Old bug", state="CLOSED")
        self.shown(Listing((closed,)), Query("closed"))
        self.press("char", "x")
        self.draw()
        self.row_of("Reopen #7?")
        self.assertIsNone(self.press("esc"))
        self.assertFalse(self.view.editing)

    def test_a_click_previews_an_issue(self):
        self.shown()
        self.assertEqual(self.click("Login fails"), Action("preview_issue", (SAFARI,)))

    def test_hover_shows_the_agent_and_browser_buttons(self):
        self.shown()
        y = self.row_of("#38")
        self.view.handle(Mouse("move", 5, y, 3))
        self.draw()
        row = text(self.canvas, y)
        marks = glyphs(True)
        self.assertIn(marks["agent"], row)
        self.assertIn(marks["web"], row)
        self.assertEqual(self.click(marks["agent"], y), Action("issue_to_agent", (DARK,)))
        self.assertEqual(self.click(marks["web"], y), Action("issue_web", (DARK,)))

    def test_nothing_past_the_edge_at_24_columns(self):
        long = Issue(1234, "A very long title that never fits in a narrow sidebar", ("enhancement", "help wanted"),
                     ("someone-with-a-long-name",), "2026-10-24T11:00:00Z")
        self.view.ask()
        self.view.show(Listing((long,)), Query())
        canvas = self.draw(width=24)
        y = self.row_of("#1234")
        self.assertTrue(text(canvas, y).rstrip().endswith("…"))
        self.assertTrue(text(canvas, y + 1).rstrip().endswith("1h"))      # the age always shows

    def test_the_wheel_scrolls_the_list(self):
        many = Listing(tuple(Issue(n, f"Issue {n}") for n in range(1, 30)))
        self.shown(many)
        self.view.handle(Mouse("wheel_down", 5, 6))
        self.draw()
        self.assertFalse(any("#1 " in text(self.canvas, y) for y in range(16)))


class Shared(unittest.TestCase):
    """One question a minute for every sidebar of a repository: the latest answer kept in the state folder."""

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.listing = github.Listing((github.Issue(42, "Login fails", ("bug",), ("dev",), "2026-10-22T10:00:00Z",
                                                    "OPEN", "https://github.com/acme/app/issues/42", "High"),))

    def test_an_answer_kept_comes_back_while_fresh(self):
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        self.assertEqual(issue_work.kept(self.state, "acme/app", Query(), 60), self.listing)

    def test_nothing_kept_where_the_state_folder_is_gone(self):
        # removed with herdr-fold while a sidebar still asked: not brought back
        gone = os.path.join(self.state, "gone")
        issue_work.keep(gone, "acme/app", Query(), self.listing)
        self.assertFalse(os.path.exists(gone))

    def test_none_when_old_for_another_query_or_repository_or_damaged(self):
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 0))
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query("closed"), 60))
        self.assertIsNone(issue_work.kept(self.state, "acme/web", Query(), 60))
        for name in os.listdir(self.state):
            with open(os.path.join(self.state, name), "w") as f:
                f.write("{")
        self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 60))

    def test_none_when_it_is_not_as_kept(self):
        # a file not as keep() writes it (another version's, or edited by hand): GitHub is asked instead
        issue_work.keep(self.state, "acme/app", Query(), self.listing)
        path = issue_work.shared_path(self.state, "acme/app", Query())
        with open(path) as f:
            good = json.load(f)
        row = good["issues"][0]
        wrong = [{**good, "issues": [{**row, **change}]}
                 for change in ({"number": "42"}, {"number": True}, {"title": 7}, {"labels": "bug"},
                                {"assignees": [1]}, {"priority": None}, {"more": ""})]
        wrong += [{**good, "error": {"text": "x"}}, {**good, "issues": {"42": row}}, [good]]
        for data in wrong:
            with self.subTest(data=data):
                with open(path, "w") as f:
                    json.dump(data, f)
                self.assertIsNone(issue_work.kept(self.state, "acme/app", Query(), 60))


class Tabs(unittest.TestCase):
    def test_the_preview_shows_it_as_a_terminal_would(self):
        spec = issue_work.view_spec("acme/app", github.Issue(42, "Login fails on Safari"))
        self.assertEqual(spec["title"], "#42 Login fails on Safa…")             # a tab's name: its title cut short
        self.assertEqual(spec["pipeline"][0][1:], ["issue", "view", "42", "-R", "acme/app", "--comments"])
        self.assertTrue(os.path.isabs(spec["pipeline"][0][0]))
        self.assertTrue(spec["env"]["GH_FORCE_TTY"])


if __name__ == "__main__":
    unittest.main()
