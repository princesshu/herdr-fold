"""Tests for the sidebar's Issues view (issues.py), keyed like GitHub's list, by priority, each one's type before its
number; its filters (filters.py), Priority… and Type…; its Pull requests (pulls.py); its own part (issue_work.py): the
latest answer kept for the repository's other sidebars, and what a tab of its opens."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace

from support import SRC, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import github  # noqa: E402
import issue_work  # noqa: E402
import pager  # noqa: E402
from github import Issue, Listing, Pull, Pulls, Query  # noqa: E402
from issues import NO_PRIORITY, TEXT, Issues  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import PAD, SPINNER, Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action, Heading, Row  # noqa: E402

FUNNEL = glyphs(True)["funnel"]               # the filters' funnel at the field's end

NOW = github.parse_time("2026-10-24T12:00:00Z")
SAFARI = Issue(42, "Login fails on Safari", ("auth", "ui"), ("dev",), "2026-10-22T10:00:00Z", "OPEN",
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

    def lines(self):
        return [text(self.canvas, y) for y in range(self.canvas.height)]

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
        self.view.ask(Query())
        self.view.show(Listing((SAFARI, low, urgent, DARK, high, medium)), Query())   # gh's: latest change first
        self.draw(height=20)
        order = sorted((self.row_of(f"#{n} "), n) for n in (42, 38, 50, 51, 52, 53))
        self.assertEqual([n for _, n in order], [51, 52, 53, 50, 42, 38])

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
        urgent = Issue(51, "Payments are down", ("ui", "urgent"), (), "2026-10-18T10:00:00Z", "OPEN", "")
        self.shown(Listing((urgent, DARK)))
        y = self.row_of("#51 ")
        # the bar inside the pane's margin, a cell of air beside it, then the number
        self.assertEqual([self.canvas.rows[r][x][0] for r in (y, y + 1) for x in (0, 1, 2)], [" ", "▌", " "] * 2)
        self.assertEqual({self.canvas.rows[r][1][1].fg for r in (y, y + 1)}, {"deleted"})
        self.assertEqual((text(self.canvas, y).index("#51"), self.canvas.rows[y][3][1].fg), (3, "deleted"))
        details = text(self.canvas, y + 1)
        self.assertEqual(self.canvas.rows[y + 1][details.index("urgent")][1].fg, "deleted")
        self.assertEqual(self.canvas.rows[y + 1][details.index("ui")][1].fg, "muted")
        dark = self.row_of("#38 ")                     # no priority: a quiet bar all the same, its number plain text
        self.assertEqual([(self.canvas.rows[r][1][0], self.canvas.rows[r][1][1].fg) for r in (dark, dark + 1)],
                         [("▌", NO_PRIORITY)] * 2)
        self.assertEqual((NO_PRIORITY, self.canvas.rows[dark][3][1].fg), ("guide", "text"))

    def test_each_priority_has_its_color_as_a_traffic_light(self):
        # red, yellow, green: three colors every theme keeps apart (GitHub Dark's high and medium were one color)
        for label, role in (("critical", "deleted"), ("P1", "deleted"), ("priority: high", "deleted"),
                            ("priority: medium", "modified"), ("Low", "added")):
            self.view = Issues(now=lambda: NOW)
            self.shown(Listing((Issue(9, "Something", (label,), (), "2026-10-22T10:00:00Z", "OPEN", ""),)))
            y = self.row_of("#9 ")
            self.assertEqual((self.canvas.rows[y][1][1].fg, self.canvas.rows[y][3][1].fg), (role, role), label)

    def test_githubs_priority_field_shows_first_in_its_color(self):
        # an organization's Priority field (Urgent, High, Medium, Low) is GitHub's own: before the labels
        self.shown(Listing((Issue(71, "Payments down", ("ui",), (), "2026-10-18T10:00:00Z", "OPEN", "", "Urgent"),)))
        y = self.row_of("#71 ")
        details = text(self.canvas, y + 1)
        self.assertTrue(details[3 + len("#71 "):].startswith("Urgent  ui"), details)        # two cells apart
        self.assertEqual(self.canvas.rows[y + 1][details.index("Urgent")][1].fg, "deleted")

    def test_the_filter_field_and_its_funnel_then_open_and_closed(self):
        self.draw()
        field = self.row_of("Filter issues")
        row = text(self.canvas, field)
        self.assertEqual((row.index(FUNNEL), self.canvas.rows[field][row.index(FUNNEL)][1].fg), (45 - 3, "muted"))
        states = text(self.canvas, self.row_of("Open"))
        self.assertGreater(self.row_of("Open"), field)
        self.assertLess(states.index("Open"), states.index("Closed"))
        self.assertNotIn("Mine", states)                                    # GitHub's: a filter, not a state
        self.assertEqual(self.view.ask(), Action("load_issues", (Query(),)))

    def test_the_first_ask_and_its_answers_say_so_where_the_first_issue_stands(self):
        # "Loading issues…" on the first issue's row, from the content's inset as every view's line, then the issues
        # in its place, or what was found: nothing, or why not; never a row more or less above the list
        self.shown()
        first = self.row_of("#42")
        for query, listing, said in ((Query(), None, "Loading issues…"), (Query(), Listing(()), "No open issues"),
                                     (Query(), Listing(error=github.SIGNED_OUT), github.SIGNED_OUT[:20])):
            with self.subTest(said=said):
                self.view = Issues(now=lambda: NOW)
                self.view.ask(query)
                if listing is not None:
                    self.view.show(listing, query)
                self.draw()
                self.assertEqual((self.row_of(said), text(self.canvas, first).index(said[:7])), (first, PAD))
        self.view.show(TWO, Query())
        self.draw()
        self.assertEqual((self.row_of("#42"), text(self.canvas, first).index("#42")), (first, TEXT))

    def test_another_state_or_filter_asked_shows_no_issue_of_the_last_one_meanwhile(self):
        self.shown()
        first = self.row_of("#42")
        self.press("right")                                                     # Closed asked for
        self.draw()
        self.assertEqual((self.row_of("Loading issues…"), any("#42" in line for line in self.lines())), (first, False))

    def test_the_list_stays_put_while_a_refresh_asks_a_spinner_in_the_refresh_buttons_cell(self):
        # no row comes or goes above the list: the refresh button at the right end of Open and Closed, as Files'
        # header has one, turns into a spinner while gh runs, its tip saying so; then back, the list where it was
        self.shown()
        first, states, refresh = self.row_of("#42"), self.row_of("Open"), glyphs(True)["refresh"]
        self.assertEqual((text(self.canvas, states)[43], self.canvas.hit(43, states), self.view.tip("refresh")),
                         (refresh, "refresh", None))
        self.assertEqual(self.click(refresh, states), Action("load_issues", (Query(),)))
        self.draw()
        self.assertEqual((self.row_of("#42"), text(self.canvas, states)[43] in SPINNER, self.view.tip("refresh")),
                         (first, True, "Loading issues…"))
        self.assertIsNone(self.click(text(self.canvas, states)[43], states))      # asked already: once
        self.view.show(TWO, Query())
        self.draw()
        self.assertEqual((self.row_of("#42"), text(self.canvas, states)[43]), (first, refresh))

    def test_the_arrows_switch_open_and_closed_and_ask_again(self):
        self.assertEqual(self.press("right"), Action("load_issues", (Query("closed"),)))
        self.assertIsNone(self.press("right"))                         # the last one stays
        self.assertEqual(self.press("left"), Action("load_issues", (Query(),)))

    def test_open_and_closed_each_with_the_repositorys_count_the_word_alone_till_it_is_known(self):
        # as GitHub's list: both sides counted (a list left on Closed still says how many are open); the chosen one
        # filled, the other's words and number muted; each chip a cell of air round its words, whatever the count
        self.draw()
        self.assertEqual(text(self.canvas, self.row_of("Open")).split()[:2], ["Open", "Closed"])
        for totals in ({"open": 2, "closed": 1}, {"open": 12, "closed": 340}, {"open": 0, "closed": 7}):
            self.view.ask()
            self.view.show(replace(TWO, totals=totals), Query())
            self.draw()
            y = self.row_of("Open")
            line = text(self.canvas, y)
            self.assertIn(f"Open {totals['open']}   Closed {totals['closed']}", line)
            row = self.canvas.rows[y]
            filled = [x for x, (_, style) in enumerate(row) if style.bg == "button"]
            self.assertEqual((row[filled[0]][0], row[filled[-1]][0], row[filled[0] + 1][0], row[filled[-1] - 1][0]),
                             (" ", " ", "O", str(totals["open"])[-1]), totals)
            closed = line.index("Closed")
            self.assertEqual({row[x][1].fg for x in range(closed, closed + len(f"Closed {totals['closed']}"))},
                             {"muted"})
        self.view.ask(Query("closed"))                                       # the other side: its counts kept
        self.draw()
        self.assertIn("Open 0   Closed 7", text(self.canvas, self.row_of("Open")))

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
        for part in ("auth, ui", "@dev", "2d"):
            self.assertIn(part, below)
        y = self.row_of("#38 Add a dark mode toggle")
        self.assertEqual(text(self.canvas, y + 1).split(), ["▌", "5d"])          # no priority: its quiet bar, the age

    def test_an_answer_for_another_query_is_dropped(self):
        self.press("right")                                             # Closed is being asked for
        self.view.show(TWO, Query())
        self.draw()
        self.assertFalse(any("#42" in text(self.canvas, y) for y in range(16)))

    def test_empty_and_failed_answers_in_one_line(self):
        for query, said in ((Query(), "No open issues"), (Query("closed"), "No closed issues")):
            self.shown(Listing(()), query)
            self.row_of(said)
        self.view.filters.chosen["assigned"] = (True,)
        self.shown(Listing(()))
        self.row_of("No issues match")
        self.view.filters.chosen["assigned"] = ()
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
        for word, found in (("dark", [38]), ("#42", [42]), ("ui", [42]), ("@dev", [42]), ("safari auth", [42])):
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

    def test_the_funnel_and_its_menu_assigned_and_created_first_a_click_turns_one_and_it_stays_open(self):
        self.shown()
        self.assertIsNone(self.click("Filter issues"))
        self.assertTrue(self.view.searching)
        self.assertIsNone(self.click(FUNNEL))
        self.assertFalse(self.view.searching)
        self.draw()
        self.assertEqual(self.view.menu.menu.choices[:2], ["Assigned to me", "Created by me"])
        self.assertIsNone(self.click("Created by me", self.row_of("Created by me")))      # narrowed here, not asked
        self.draw()
        self.assertIsNotNone(self.view.menu)
        self.assertEqual(self.view.filters.chosen["authored"], (True,))
        self.assertEqual(self.view.menu.menu.choices[1].on, True)

    def test_the_filters_menu_opens_under_the_field_their_right_edges_in_one_line(self):
        for roomy in (False, True):                                         # a tall field has a border row below
            self.draw(roomy=roomy)
            self.view.open_filters()
            self.draw(roomy=roomy)
            field = self.row_of("Filter issues")
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


# issue-types.html's list: #42 Urgent Bug (GitHub's type), #47 High Feature (its enhancement label), #39 Medium Task,
# #51 Low Bug (its bug label), #53 none; the organization's Priority field and types, which the user may set
TYPED = Listing((Issue(42, "Page past the last one answers an empty list", ("api",), ("you",), "2026-10-24T10:00:00Z",
                       "OPEN", "", "Urgent", "Bug", "I_42"),
                 Issue(47, "Group books by shelf", ("shelves", "enhancement"), ("ada",), "2026-10-23T12:00:00Z",
                       "OPEN", "", "High", "", "I_47", "you"),
                 Issue(39, "Describe the routes in the README", ("docs",), (), "2026-10-21T12:00:00Z", "OPEN", "",
                       "Medium", "Task", "I_39"),
                 Issue(51, "Export dates in UTC", ("export", "bug"), ("tomas",), "2026-10-19T12:00:00Z", "OPEN", "",
                       "Low", "", "I_51"),
                 Issue(53, "Page size from the config?", ("question",), (), "2026-10-18T12:00:00Z")),
                settable={"field": "PF_1", "options": [["PO_1", "Urgent"], ["PO_2", "High"], ["PO_3", "Medium"],
                                                       ["PO_4", "Low"]],
                          "types": [["IT_1", "Bug"], ["IT_2", "Feature"], ["IT_3", "Task"]]}, me="you")


class Types(unittest.TestCase):
    """Each issue's type a mono, muted icon before its number (its column there while any issue listed has one), its
    word under the title where no icon says it; a closed one's marks all muted; the row's highlight a cell in."""
    setUp, draw, row_of, lines, click, press = View.setUp, View.draw, View.row_of, View.lines, View.click, View.press

    def shown(self, listing=TYPED, icons=True):
        self.view = Issues(icons=icons, now=lambda: NOW)
        self.view.ask()
        self.view.show(listing, Query())
        return self.draw(width=44, height=20)

    def test_each_ones_icon_before_its_number_the_numbers_in_one_column(self):
        self.shown()
        for number, kind in ((42, "Bug"), (47, "Feature"), (39, "Task"), (51, "Bug"), (53, None)):
            y = self.row_of(f"#{number} ")
            line = text(self.canvas, y)
            self.assertEqual(line.index(f"#{number}"), TEXT + 2, number)            # the icon and a cell of air
            self.assertEqual(line[TEXT], glyphs(True)[kind] if kind else " ", number)
            if kind:
                self.assertEqual(self.canvas.rows[y][TEXT][1].fg, "muted")
            under = text(self.canvas, y + 1)                                    # under the title
            self.assertEqual(len(under) - len(under.lstrip(" ▌")), TEXT + 2 + len(f"#{number} "), number)
        self.assertNotIn("enhancement", text(self.canvas, self.row_of("#47 ") + 1))      # its type now: one signal
        self.assertNotIn("bug", text(self.canvas, self.row_of("#51 ") + 1))

    def test_no_type_listed_no_column(self):
        self.shown(Listing((SAFARI, DARK)))
        self.assertEqual(text(self.canvas, self.row_of("#42 ")).index("#42"), TEXT)

    def test_without_icons_the_types_word_after_the_priority(self):
        self.shown(icons=False)
        y = self.row_of("#42 ")
        self.assertEqual(text(self.canvas, y).index("#42"), TEXT)                           # no column
        under = text(self.canvas, y + 1)
        self.assertIn("Urgent  Bug  api  @you", under)
        self.assertEqual(self.canvas.rows[y + 1][under.index("Bug")][1].fg, "muted")
        self.assertIn("High  Feature  shelves", text(self.canvas, self.row_of("#47 ") + 1))

    def test_an_organizations_own_type_its_word_no_icon(self):
        epic = Issue(60, "Search across shelves", ("search",), (), "2026-10-24T10:00:00Z", issue_type="Epic")
        self.shown(Listing(TYPED.issues + (epic,)))
        y = self.row_of("#60 ")
        self.assertEqual(text(self.canvas, y)[TEXT], " ")
        self.assertIn("Epic  search", text(self.canvas, y + 1))

    def test_a_closed_ones_marks_all_muted(self):
        closed = replace(TYPED.issues[0], state="CLOSED")
        self.shown(Listing((closed,)))
        y = self.row_of("#42 ")
        under = text(self.canvas, y + 1)
        for row, x in ((y, 1), (y + 1, 1), (y, TEXT), (y, TEXT + 2), (y + 1, under.index("Urgent"))):
            self.assertEqual(self.canvas.rows[row][x][1].fg, "muted", (row, x))

    def test_the_rows_highlight_a_cell_in_from_each_side_its_content_a_cell_inside_it(self):
        # as Changes' field and button stand: the bar (or the room for one) at the highlight's edge, the age a cell
        # inside its end
        self.shown()
        for number in (42, 53):                                                      # with a bar, without one
            index = next(n for n, issue in enumerate(self.view.list.items) if issue.number == number)
            self.view.list.index = index
            self.draw(width=44, height=20)
            for y in (self.row_of(f"#{number} "), self.row_of(f"#{number} ") + 1):
                row = self.canvas.rows[y]
                self.assertEqual((row[0][1].bg, row[43][1].bg), (None, None), number)
                self.assertTrue(all(row[x][1].bg == "selection" for x in range(1, 43)), number)
            age = text(self.canvas, self.row_of(f"#{number} ") + 1)
            self.assertEqual(len(age.rstrip()), 44 - 2, number)                     # ends at width - 3

    def test_a_hovered_ones_buttons_inside_the_highlight(self):
        self.shown()
        y = self.row_of("#47 ")
        self.view.handle(Mouse("move", 5, y, 3))
        self.draw(width=44, height=20)
        line = text(self.canvas, y)
        self.assertEqual(len(line.rstrip()) - 1, line.index(glyphs(True)["web"]))
        self.assertLessEqual(line.index(glyphs(True)["web"]), 44 - 3)


class Filtering(unittest.TestCase):
    """The funnel's menu: Assigned to me and Created by me, then the groups the list holds, each value with how many
    would stay (the other groups' filters counted, not its own); several values of a group, every group; it stays open
    while values are pressed; what is on as chips under the field."""
    setUp, draw, row_of, lines, click, press, type = (View.setUp, View.draw, View.row_of, View.lines, View.click,
                                                      View.press, View.type)

    def shown(self, listing=TYPED):
        self.view.ask()
        self.view.show(listing, Query())
        return self.draw(width=44, height=30)

    def menu(self):
        return self.view.menu.menu.choices

    def counts(self, group):
        """GROUP's rows in the menu: [(words, count, on, faint)]."""
        choices = self.menu()
        start = choices.index(group) + 1
        rows = []
        for choice in choices[start:]:
            if not isinstance(choice, Row):
                break
            rows.append((str(choice), choice.count, choice.on, choice.faint))
        return rows

    def pick(self, words):
        return self.view.pick(next(choice for choice in self.menu() if choice == words))

    def test_the_groups_only_as_the_list_holds_them(self):
        self.shown()
        self.press("char", "a")
        self.assertEqual([str(c) for c in self.menu() if isinstance(c, Heading)], ["Priority", "Type", "Label"])
        self.assertEqual(self.counts("Priority"), [("Urgent", 1, False, False), ("High", 1, False, False),
                                                   ("Medium", 1, False, False), ("Low", 1, False, False)])
        self.assertEqual(self.counts("Type"), [("Bug", 2, False, False), ("Feature", 1, False, False),
                                               ("Task", 1, False, False)])
        self.view.close_menu()
        self.shown(Listing((SAFARI, DARK)))                         # no priority, no type: no group for them
        self.press("char", "a")
        self.assertEqual([str(c) for c in self.menu() if isinstance(c, Heading)], ["Label"])

    def test_urgent_or_high_and_bug_the_menu_open_throughout(self):
        self.shown()
        self.press("char", "a")
        for words in ("Urgent", "High", "Bug"):
            self.assertIsNone(self.pick(words))
            self.assertIsNotNone(self.view.menu)                     # it stays open
        self.assertEqual(self.counts("Priority"), [("Urgent", 1, True, False), ("High", 0, True, True),
                                                   ("Medium", 0, False, True), ("Low", 1, False, False)])
        self.assertEqual(self.counts("Type"), [("Bug", 1, True, False), ("Feature", 1, False, False),
                                               ("Task", 0, False, True)])
        self.assertEqual([issue.number for issue in self.view.list.items], [42])
        self.assertIsNone(self.pick("Bug"))                          # pressed again: off
        self.assertEqual([issue.number for issue in self.view.list.items], [42, 47])

    def test_every_values_words_on_one_column_its_count_at_the_end(self):
        self.shown()
        self.press("char", "a")
        self.pick("Urgent")
        self.draw(width=44, height=30)
        inside = [line[line.index("│"):] for line in self.lines() if "│" in line]       # the menu's rows alone
        columns = {line.index(words) for words in ("Assigned to me", "Urgent", "Bug", "api") for line in inside
                   if words in line}
        self.assertEqual(len(columns), 1, columns)
        urgent = next(line for line in inside if "Urgent" in line)
        self.assertEqual(urgent[urgent.index("Urgent") - 4], "✓")               # the check, then the dot's slot
        self.assertTrue(urgent.rstrip().endswith("1 │"), urgent)

    def test_chips_one_a_group_x_takes_one_off_clear_all_backspace_the_last(self):
        self.shown()
        self.press("char", "a")
        for words in ("Created by me", "Urgent", "High", "Bug"):
            self.pick(words)
        self.press("esc")
        self.draw(width=44, height=30)
        first = self.row_of("Created by me ×")                                  # a cell between two chips, each
        self.assertIn("Created by me ×   ● Urgent, High ×", text(self.canvas, first))      # one's air its own
        self.assertIn(glyphs(True)["Bug"] + " Bug ×", text(self.canvas, first + 1))     # no room: the next row
        self.assertTrue(text(self.canvas, first + 1).rstrip().endswith("Clear"))
        self.assertEqual(text(self.canvas, first + 2).split()[:2], ["Open", "Closed"])
        field = self.row_of("Filter issues")
        self.assertEqual(self.canvas.rows[field][44 - 3][1].fg, "accent")         # the funnel: a filter is on
        y = self.row_of("Created by me ×")
        self.click("×", y)                                                       # the first chip's ×
        self.assertEqual(self.view.filters.chosen["authored"], ())
        self.press("char", "/")
        self.press("backspace")                                                  # the empty field: the last chip
        self.assertEqual(self.view.filters.chosen["type"], ())
        self.press("esc")
        self.draw(width=44, height=30)
        self.click("Clear", self.row_of("Clear"))
        self.assertFalse(self.view.filters.on())
        self.draw(width=44, height=30)
        self.assertEqual(self.canvas.rows[field][44 - 3][1].fg, "muted")

    def test_a_chip_holds_its_words_between_a_cell_of_air_each_side(self):
        # each label's length, with a mark and without: the chip's first and last cells air on its fill, its
        # content between them (the TUI centres nothing else in it)
        for words in ("a", "ab", "api", "docs", "shelves", "good first issue"):
            for group in ("label", "level"):
                self.view = Issues(now=lambda: NOW)
                self.view.filters.chosen[group] = (words,) if group == "label" else (1,)
                canvas = Canvas(60, 4)
                self.view.filters.draw_chips(canvas, 0, True, None)
                row = canvas.rows[0]
                painted = [x for x, (_, style) in enumerate(row) if style.bg == "input"]
                start, end = painted[0], painted[-1]
                self.assertEqual((row[start][0], row[end][0], row[end - 1][0]), (" ", " ", "×"), (words, group))
                self.assertNotEqual(row[start + 1][0], " ", (words, group))
                self.assertEqual(row[end - 2][0], " ", (words, group))

    def test_past_six_labels_the_six_most_used_n_more_and_a_find_field(self):
        many = Listing(tuple(Issue(n, f"Issue {n}", (label, "api") if n < 66 else (label,))
                             for n, label in enumerate(("docs", "export", "question", "shelves", "search", "auth",
                                                        "perf", "ui"), 60)))
        self.shown(many)
        self.press("char", "l")
        labels = self.counts("Label")
        self.assertEqual([words for words, *_ in labels], ["api", "auth", "docs", "export", "perf", "question",
                                                           "3 more"])
        self.assertIsNotNone(self.view.menu.menu.find)
        self.pick("3 more")
        self.assertEqual(len(self.counts("Label")), 9)
        for ch in "per":
            self.press("char", ch)                                               # typed into its find field
        self.assertEqual([str(c) for c in self.menu() if isinstance(c, Row)], ["perf"])

    def test_counts_from_the_latest_hundred_then_its_search_asked(self):
        full = Listing(tuple(Issue(n, f"Issue {n}", ("docs",) if n % 2 else ("api",)) for n in range(1, 101)))
        self.view.ask()
        asked = self.view.show(full, Query())
        self.assertIsNone(asked)                                                 # nothing on: no search
        self.press("char", "l")
        self.assertEqual(self.menu()[-1], "Counts from the latest 100")
        asked = self.pick("docs")
        self.assertEqual(asked, Action("load_issues", (Query(search='label:"docs"'),)))
        self.assertEqual(len(self.view.list.items), 50)                          # the loaded list narrowed meanwhile
        more = Listing(full.issues, narrowed=tuple(Issue(n, f"Issue {n}", ("docs",)) for n in range(101, 181)))
        self.assertIsNone(self.view.show(more, Query(search='label:"docs"')))
        self.assertEqual(len(self.view.list.items), 80)                          # the search's, narrowed exactly

    def test_the_filters_come_back_and_older_single_values_become_one(self):
        self.view.filters.chosen.update(level=(0, 1), label=("api",), authored=(True,))
        kept = self.view.kept()
        again = Issues(now=lambda: NOW)
        again.take(json.loads(json.dumps(kept)))
        self.assertEqual(again.filters.chosen, {**self.view.filters.chosen})
        older = Issues(now=lambda: NOW)
        older.take({"state": "closed", "assigned": True, "authored": False, "label": "bug", "level": 2,
                    "board": "pulls"})
        self.assertEqual((older.query, older.board), (Query("closed"), "pulls"))
        self.assertEqual(older.filters.chosen, {"assigned": (True,), "authored": (), "level": (2,), "type": (),
                                                "label": ("bug",)})
        older.take({"chosen": {"level": [True, 9, "x"], "label": ["", 3, "ok"], "assigned": [1]}})
        self.assertEqual(older.filters.chosen["level"] + older.filters.chosen["label"] + older.filters.chosen[
            "assigned"], ("ok",))


class Setting(unittest.TestCase):
    """The right click's Priority… and Type…, where the organization has them: a second menu in the first one's place,
    its head the issue's number with what it sets, none first, a check on the one it has; the row set at once."""
    setUp, draw, row_of, lines, click, press = View.setUp, View.draw, View.row_of, View.lines, View.click, View.press

    def shown(self, listing=TYPED):
        self.view.ask()
        self.view.show(listing, Query())
        return self.draw(width=44, height=30)

    def right_click(self, number):
        y = self.row_of(f"#{number} ")
        self.view.handle(Mouse("press", 9, y, 2))
        self.draw(width=44, height=30)
        return self.view.menu.menu.choices

    def test_priority_and_type_between_assign_and_close_only_where_they_can_be_set(self):
        self.shown()
        self.assertEqual(self.right_click(42), ["Open", "Open in the browser", "To the agent", "Reply", "Assign to me",
                                                "Priority…", "Type…", "Close…"])
        self.view.close_menu()
        self.shown(replace(TYPED, settable={"field": "", "options": [], "types": [["IT_1", "Bug"]]}))
        self.assertNotIn("Priority…", self.right_click(42))
        self.view.close_menu()
        self.shown(replace(TYPED, settable=None))                               # a personal repository, or a reader
        self.assertEqual(self.right_click(42)[-3:], ["Reply", "Assign to me", "Close…"])

    def test_priority_opens_where_the_first_menu_was_none_first_a_check_on_its_own(self):
        self.shown()
        self.right_click(42)
        first = next(y for y in range(30) if "┌" in text(self.canvas, y))
        corner = text(self.canvas, first).index("┌")
        self.view.pick("Priority…")
        self.draw(width=44, height=30)
        self.assertEqual((next(y for y in range(30) if "┌" in text(self.canvas, y)),
                          text(self.canvas, first).index("┌")), (first, corner))
        choices = self.view.menu.menu.choices
        self.assertEqual([str(c) for c in choices if c is not None], ["#42 · Priority", "No priority", "Urgent", "High",
                                                                       "Medium", "Low"])
        self.assertEqual([c.on for c in choices if isinstance(c, Row)], [False, True, False, False, False])
        inside = [line[line.index("│"):] for line in self.lines() if "│" in line]       # the menu's rows alone
        none = next(line for line in inside if "No priority" in line)
        urgent = next(line for line in inside if "Urgent" in line)
        self.assertEqual((none.index("●"), none.index("No priority")), (urgent.index("●"), urgent.index("Urgent")))
        self.assertEqual(next(c for c in choices if isinstance(c, Row)).mark, ("●", NO_PRIORITY))   # the bar's grey

    def test_a_choice_sets_the_row_at_once_and_asks_github(self):
        self.shown()
        self.right_click(42)
        self.view.pick("Priority…")
        asked = self.view.pick(next(c for c in self.view.menu.menu.choices if c == "Medium"))
        changed = replace(TYPED.issues[0], priority="Medium")
        self.assertEqual(asked, Action("issue_set", (changed, "priority", "PO_3", "Medium", "PF_1")))
        self.assertIsNone(self.view.menu)
        self.draw(width=44, height=30)
        y = self.row_of("#42 ")
        self.assertEqual(self.canvas.rows[y][1][1].fg, "modified")                  # its new color, at once
        self.right_click(42)
        self.view.pick("Type…")
        asked = self.view.pick(next(c for c in self.view.menu.menu.choices if c == "No type"))
        self.assertEqual(asked.args[1:], ("type", None, "no type", ""))
        self.assertEqual(asked.args[0].issue_type, "")


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


SHELVES = Pull(57, "Group books by shelf", "feat/shelves", "ada", "2026-10-24T10:00:00Z", checks=(3, 0, 0), yours=True)
PAGE = Pull(58, "Keep a page past the last one in range", "fix/page-past-end", "dev", "2026-10-24T11:55:00Z",
            draft=True, checks=(2, 1, 0), url="https://github.com/acme/app/pull/58")
ERRORS = Pull(55, "Problem details for errors", "fix/errors", "tomas", "2026-10-23T12:00:00Z",
              decision="CHANGES_REQUESTED", checks=(1, 0, 1))


class PullRequests(unittest.TestCase):
    """The Issues view's other list, its switch on top: each pull request's checks, number, title and review's state,
    its branch, author and age under them; keyed as the issues, a new one in Changes."""
    setUp, draw, row_of, lines, click, press, type = (View.setUp, View.draw, View.row_of, View.lines, View.click,
                                                      View.press, View.type)

    def pulls(self, found=(SHELVES, PAGE, ERRORS), error=None):
        self.assertEqual(self.press("char", "p"), Action("load_pulls", (Query(),)))
        self.view.pulls.show(Pulls(found, "dev", error), Query())
        return self.draw(width=50)

    def test_p_or_a_press_on_the_switch_shows_them_asked_for_once(self):
        self.draw()
        self.assertIn("Issues   Pull requests", self.lines()[0])
        self.assertEqual(self.click("Pull requests", 0), Action("load_pulls", (Query(),)))
        self.assertEqual(self.view.board, "pulls")
        self.draw()
        self.assertIn("Filter pull requests", "".join(self.lines()))
        self.assertIsNone(self.press("char", "p"))              # back to the issues: they are there already
        self.assertEqual(self.view.board, "issues")

    def test_a_row_its_checks_number_title_and_review(self):
        self.pulls()
        for pull, glyph, word in ((SHELVES, "✓", "your review"), (PAGE, "●", "Draft"), (ERRORS, "✕", "changes")):
            with self.subTest(pull.number):
                y = self.row_of(f"#{pull.number} ")
                self.assertEqual(self.lines()[y][1], glyph)
                self.assertTrue(self.lines()[y].rstrip().endswith(word))
        self.assertEqual(self.canvas.rows[self.row_of("#57 ")][46][1].fg, "modified")      # it waits on you
        self.assertIn("fix/page-past-end · you · 5m · checks 2 of 3", self.lines()[self.row_of("#58 ") + 1])
        self.assertNotIn("checks", self.lines()[self.row_of("#57 ") + 1])                  # passed: not said

    def test_keyed_as_the_issues_a_new_one_in_changes(self):
        self.pulls()
        self.press("down")
        self.assertEqual(self.press("enter"), Action("preview_pull", (PAGE,)))
        self.assertEqual(self.press("char", "t"), Action("pull_to_agent", (PAGE,)))
        self.assertEqual(self.press("char", "b"), Action("pull_web", (PAGE,)))
        self.assertEqual(self.press("char", "c"), Action("new_pull", ()))
        self.assertEqual(self.press("right"), Action("load_pulls", (Query("closed"),)))
        self.assertEqual(self.click("+"), Action("new_pull", ()))

    def test_the_filter_finds_them_by_number_title_branch_and_author(self):
        self.pulls()
        self.press("char", "/")
        self.type("you")
        self.draw(width=50)
        self.assertEqual([pull.number for pull in self.view.pulls.list.items], [58])

    def test_loading_a_failure_or_none_on_the_first_rows_place(self):
        self.press("char", "p")
        self.draw()
        self.row_of("Loading pull requests…")
        self.view.pulls.show(Pulls(error=github.SIGNED_OUT), Query())
        self.draw()
        self.row_of(github.SIGNED_OUT[:30])
        self.view.pulls.show(Pulls(), Query())
        self.draw()
        self.row_of("No open pull requests")

    def test_filtered_as_the_issues_review_in_its_colors_checks_with_their_marks(self):
        self.pulls()
        self.press("char", "a")
        choices = self.view.pulls.menu.menu.choices
        self.assertEqual([str(c) for c in choices if isinstance(c, Heading)], ["Review", "Checks"])
        rows = {str(c): c for c in choices if isinstance(c, Row)}
        self.assertEqual([(w, rows[w].role, rows[w].count) for w in ("Draft", "Your review", "Changes requested")],
                         [("Draft", None, 1), ("Your review", "modified", 1), ("Changes requested", "deleted", 1)])
        self.assertEqual([(w, rows[w].mark) for w in ("Passing", "Running", "Failing")],
                         [("Passing", ("✓", "added")), ("Running", ("●", "modified")), ("Failing", ("✕", "deleted"))])
        for words in ("Created by me", "Running"):                       # PAGE: yours (dev's), its checks running
            self.view.pulls.pick(next(c for c in self.view.pulls.menu.menu.choices if c == words))
        self.assertEqual([pull.number for pull in self.view.pulls.list.items], [58])
        self.press("esc")
        self.draw(width=50)
        self.assertIn("Created by me ×   ● Running ×", text(self.canvas, self.row_of("Clear")))

    def test_its_rows_highlight_a_cell_in_from_each_side(self):
        self.pulls()
        y = self.row_of("#57 ")
        for row in (self.canvas.rows[y], self.canvas.rows[y + 1]):
            self.assertEqual((row[0][1].bg, row[49][1].bg), (None, None))
            self.assertTrue(all(row[x][1].bg == "selection" for x in range(1, 49)))
        self.assertEqual(len(self.lines()[y].rstrip()), 50 - 2)                  # its review's word a cell inside

    def test_its_review_in_the_preview_tab_read_only_with_each_thread_on_its_line(self):
        thread = {"id": "t1", "resolved": False, "path": "src/a.py", "line": 30, "side": "RIGHT",
                  "comments": [{"id": 1, "author": "tomas\x1b[2J", "ago": "1h", "body": "Page it\x1b]0;x\x07 too"}]}
        review = {**github.pull_listed(SHELVES, "dev"), "base": "main\x1b]0;x\x07", "head": "3f2c1a9", "mine": False,
                  "files": [{"path": "src/a.py", "added": 1, "removed": 1, "cut": 0, "loose": [], "rows": [
                      {"kind": "@", "old": None, "new": None, "text": "@@ -30 +30 @@"},
                      {"kind": "-", "old": 30, "new": None, "text": "a = 1"},
                      {"kind": "+", "old": None, "new": 30, "text": "a = 2", "threads": [thread]}]}]}
        spec = issue_work.pull_spec(review)
        self.assertEqual((spec["title"], spec["pipeline"], spec["view"]), ("#57 Group books by shelf", [], "r"))
        plain = [re.sub(r"\x1b\[[\d;]*m", "", line) for line in spec["views"][0]["lines"]]
        self.assertEqual(plain[0], "#57 Group books by shelf  your review")
        self.assertEqual(plain[1], "feat/shelves → main]0;x · ada · ✓ 3 checks passed · 1 file")   # no escapes
        self.assertEqual(plain[4:], ["      @@ -30 +30 @@", "   30 - a = 1", "   30 + a = 2", "      ┃ tomas[2J · 1h",
                                     "      ┃ Page it]0;x too"])

    def test_a_review_wraps_in_a_narrow_pane_its_comments_read_whole_a_resolved_thread_said_once(self):
        said = "end can pass len(books); the slice is fine, but say so, or clamp it."
        thread = {"id": "t1", "resolved": True, "path": "src/a.py", "line": 12, "side": "RIGHT", "comments": [
            {"id": 1, "author": "lena", "ago": "20m", "body": said}, {"id": 2, "author": "noa", "ago": "5m",
                                                                     "body": "Clamped."}]}
        review = {**github.pull_listed(SHELVES, "dev"), "base": "main", "head": "3f2c1a9", "mine": True,
                  "files": [{"path": "src/a.py", "added": 1, "removed": 0, "cut": 0, "loose": [], "rows": [
                      {"kind": "+", "old": None, "new": 12, "text": "end = start + PAGE  # " + "x" * 40,
                       "threads": [thread]}]}]}
        shown = pager.viewer(issue_work.pull_spec(review))
        rows = [pager.plain(row) for row in shown.rows(40, 30)]
        self.assertEqual(rows[5:8], ["   12 + end = start + PAGE  #", "        " + "x" * 32, "        " + "x" * 8])
        self.assertEqual(rows[8:14], ["      ┃ lena · 20m · resolved", "      ┃ end can pass len(books); the",
                                      "      ┃ slice is fine, but say so, or", "      ┃ clamp it.", "      ┃ noa · 5m",
                                      "      ┃ Clamped."])                    # at a space, under the text, said once
        self.assertTrue(all(len(row) <= 40 for row in rows))


if __name__ == "__main__":
    unittest.main()
