"""Tests for conversation_list.py: the Conversations panel's list (the Spaces list's workspaces and their
conversations), the filter, opening by key or click, the right-click menu, and archiving."""
import os
import re
import sys
import unittest

from support import SRC, set_attrs, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from conversation_list import ConversationList  # noqa: E402
import widgets  # noqa: E402
from icons import glyphs  # noqa: E402
from conversations import Conversation  # noqa: E402
from screen import Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

NOW = 1_800_000_000
LOGIN = Conversation("claude", "s1", "Login redirect fix", "/repo/shop", NOW - 7200, "working", "w1:p1")
PRICES = Conversation("codex", "c1", "Price list", "/repo/shop", NOW - 86400)
RATES = Conversation("claude", "s2", "Rate limits", "/repo/api", NOW - 3600, "blocked", "w2:p1")
REVIEW = Conversation("codex", "c2", "Review the API", "/repo/api", NOW - 600, "done", "w2:p2")
OLD = Conversation("claude", "s3", "Old notes", "/notes", NOW - 30 * 86400)
STRAY = Conversation("claude", "s4", "Somewhere else", "/tmp/other", NOW)
DRAFT = Conversation("claude", "s5", "Draft the README", "/repo/shop", NOW - 9000)
PLACES = {"/repo/shop": "shop", "/repo/api": "api", "/notes": "notes"}
SPACES = ["notes", "shop", "api", "empty"]                   # as the Spaces list has them
HEADER = 3                                                   # the filter, tall as the dock's other fields


class List(unittest.TestCase):
    def setUp(self):
        set_attrs(self, widgets, TURN=0)                  # each fold at rest at once: Turning has the turn's own tests
        self.view = ConversationList(now=lambda: NOW)
        self.view.set([LOGIN, RATES, PRICES, OLD, STRAY], SPACES, PLACES.get, "shop")
        self.view.states = {"shop": "working", "api": "blocked"}            # as herdr's Spaces list has them

    def draw(self, cells=44, rows=24, roomy=True):
        self.canvas = Canvas(cells, rows)
        self.view.draw(self.canvas, 0, rows, roomy)
        return [text(self.canvas, y).rstrip() for y in range(rows)]

    def row_of(self, part):
        return next(y for y in range(self.canvas.height) if part in text(self.canvas, y))

    def style(self, part, at=None):
        """The style of PART's first character on the row that holds AT (or PART)."""
        y = self.row_of(at or part)
        return self.canvas.rows[y][text(self.canvas, y).index(part)][1]

    def press(self, name, char=""):
        return self.view.handle(Key(name, char))

    def type(self, word):
        for ch in word:
            self.press("char", ch)

    def click(self, x, y, button=0):
        return self.view.handle(Mouse("press", x, y, button))

    def test_the_filter_then_the_spaces(self):
        rows = self.draw()
        self.assertIn("Filter", rows[1])                                     # the field's row, as the dock's fields
        self.assertEqual(rows[HEADER].split()[1], "notes", rows)
        self.assertNotIn("Conversations", "\n".join(rows))                  # its group's head names it
        low = self.draw(roomy=False)                                         # a low pane: the field a chip
        self.assertIn("Filter", low[0])
        self.assertEqual(low[2].split()[1], "notes", low)

    def test_the_spaces_in_their_order_the_current_one_open(self):
        shown = [line for line in self.draw()[HEADER:] if line.strip()]
        groups = [line.split() for line in shown if not line.startswith("   ")]
        self.assertEqual([words[1] for words in groups], ["notes", "shop", "api", "empty"])
        closed, opened = glyphs(True)["closed"], glyphs(True)["open"]          # the file tree's chevrons, as every fold
        self.assertEqual([words[-2:] for words in groups], [["1", closed], ["2", opened], ["1", closed], ["0", closed]])
        self.assertEqual([line[:6] for line in shown[2:4]], ["   ├─ ", "   └─ "])     # its own, the newest first
        self.assertIn("Login redirect fix", shown[2])
        self.assertIn("Price list", shown[3])

    def test_a_space_opened_turns_its_chevron_through_45_degrees(self):
        now = [5.0]
        set_attrs(self, widgets, TURN=0.08, TURNS=widgets.Turns(clock=lambda: now[0]))
        self.view.toggle("notes")
        def marks():
            return [line.split()[-1] for line in self.draw()[HEADER:] if line.split()[1:2] == ["notes"]]
        self.assertEqual(marks(), ["⌟"])
        now[0] += widgets.TURN
        self.assertEqual(marks(), [glyphs(True)["open"]])

    def test_without_icons_a_space_folds_with_the_plain_marks_the_tree_has(self):
        self.view.icons = False
        groups = [line.split() for line in self.draw()[HEADER:] if line.strip() and not line.startswith("   ")]
        self.assertEqual([words[-1] for words in groups], [glyphs(False)["closed"], glyphs(False)["open"],
                                                           glyphs(False)["closed"], glyphs(False)["closed"]])

    def test_the_spaces_as_herdrs_spaces_list_types_them(self):
        self.draw()
        shop, notes = self.style("shop"), self.style("notes")
        self.assertEqual((shop.fg, shop.bold), ("text", True))                    # the current one: bold
        self.assertEqual((notes.fg, notes.bold), ("subtext", False))
        self.assertEqual(self.style(glyphs(True)["open"]).fg, "accent")
        self.assertEqual(self.style("├─").fg, "guide")
        self.assertEqual(self.style("·", at="notes").fg, "ignored")              # no agent there: herdr's overlay0
        self.assertEqual(self.style("●", at="shop").fg, "modified")              # working

    def test_a_space_is_marked_as_herdrs_spaces_list_marks_it_from_all_of_its_agents(self):
        self.view.states = {"notes": "idle", "shop": "done"}     # an agent with no conversation yet counts there too
        self.draw()
        self.assertEqual((self.style("○", at="notes").fg, self.style("●", at="shop").fg), ("added", "done"))
        self.assertEqual(self.style("·", at="api").fg, "ignored")                # its state not known

    def test_the_conversation_of_the_workspaces_active_tab_leads_its_group(self):
        newer = Conversation("claude", "s5", "Newer notes", "/repo/shop", NOW)     # written to a moment ago
        self.view.set([LOGIN, RATES, PRICES, newer], SPACES, PLACES.get, "shop")
        self.draw()
        self.assertLess(self.row_of("Newer notes"), self.row_of("Login redirect fix"))   # by time alone
        self.view.front = {"w1:p1"}                                         # Login's pane: its tab is the active one
        self.view.rebuild()
        self.draw()
        self.assertLess(self.row_of("Login redirect fix"), self.row_of("Newer notes"))
        self.assertLess(self.row_of("Newer notes"), self.row_of("Price list"))           # the rest by time

    def test_a_conversation_outside_every_space_is_not_shown(self):
        self.type("somewhere")
        self.assertNotIn("Somewhere else", "\n".join(self.draw()))

    def test_a_running_one_is_lit_in_its_states_color_and_a_closed_one_faint(self):
        self.draw()
        self.assertEqual(self.style("●", at="Login redirect fix").fg, "modified")  # working
        self.assertEqual(self.style("Login redirect fix").fg, "subtext")
        self.assertEqual(self.style("·", at="Price list").fg, "guide")
        self.assertEqual(self.style("Price list").fg, "muted")

    def test_each_row_says_how_long_ago_and_which_agent(self):
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Login")).rstrip().endswith("· claude · 2h"))    # a dot after the
        self.assertTrue(text(self.canvas, self.row_of("Price")).rstrip().endswith("· codex · 1d"))     # name too
        self.assertEqual((self.style("claude", at="Login").fg, self.style("2h", at="Login").fg), ("guide", "muted"))
        self.press("down")                                                  # chosen: still legible on its band
        self.draw()
        self.assertEqual(self.style("claude", at="Login").fg, "muted")
        self.draw(cells=24)                                                 # narrow: how long ago only
        self.assertTrue(text(self.canvas, self.row_of("Login")).rstrip().endswith(" 2h"))
        self.assertNotIn("claude", text(self.canvas, self.row_of("Login")))

    def test_enter_opens_a_conversation_and_toggles_a_group(self):
        self.draw()                                                         # chosen: the current space
        self.press("down")
        self.assertEqual(self.press("enter"), Action("open", (LOGIN,)))
        self.press("down")
        self.press("down")                                                  # the api group
        self.assertIsNone(self.press("enter"))
        self.assertIn("Rate limits", "\n".join(self.draw()))

    def test_left_closes_a_group_and_right_opens_it(self):
        self.draw()
        self.press("down")
        self.press("left")                                                  # from a conversation: to its group
        self.press("left")
        self.assertNotIn("Login redirect fix", "\n".join(self.draw()))
        self.press("right")
        self.assertIn("Login redirect fix", "\n".join(self.draw()))

    def test_typing_filters_every_group_and_esc_brings_them_back(self):
        self.type("rate")
        rows = self.draw()
        self.assertIn("rate", rows[1])                                      # in the field
        self.assertIn("Rate limits", "\n".join(rows))
        self.assertNotIn("Login redirect fix", "\n".join(rows))
        self.press("backspace")
        self.press("esc")
        self.assertEqual(self.view.typed, "")
        self.assertIn("Login redirect fix", "\n".join(self.draw()))

    def test_a_click_opens_a_conversation_or_a_group(self):
        self.draw()
        self.assertEqual(self.click(5, self.row_of("Login redirect fix")), Action("open", (LOGIN,)))
        self.assertIsNone(self.click(3, self.row_of("api")))
        self.assertIn("Rate limits", "\n".join(self.draw()))

    def menu_of(self, part):
        """The right click's menu on the row of PART: its choices, as drawn."""
        self.draw()
        y = self.row_of(part)
        self.assertIsNone(self.click(5, y, button=2))
        choices, rows = self.view.menu.menu.choices, self.draw()
        return y, [re.search(r"│([^│]+)│", rows[y + n]).group(1).strip() for n in range(1, len(choices) + 1)]

    def test_a_right_click_offers_open_copy_and_for_a_closed_one_archive(self):
        self.draw()
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Open", "Copy conversation", "Rename", "Archive"])
        self.assertEqual(self.click(7, y + 2), Action("copy", (PRICES,)))      # the menu opens where clicked
        self.click(5, y, button=2)
        self.draw()
        self.assertEqual(self.press("enter"), Action("open", (PRICES,)))   # the menu takes the keys meanwhile
        _, shown = self.menu_of("Login redirect fix")                     # running: no Archive
        self.assertEqual(shown[:2], ["Open", "Copy conversation"])
        self.assertNotIn("Archive", shown)

    def test_its_menu_closes_when_the_pane_loses_the_keys(self):
        y, _ = self.menu_of("Price list")
        self.view.close_menu()                                              # a click in another pane
        self.assertNotIn("Copy conversation", "\n".join(self.draw()))
        self.assertEqual(self.click(5, y), Action("open", (PRICES,)))       # a click acts again at once

    def test_an_archived_one_is_off_the_list_and_typing_finds_it(self):
        self.view.archived = {"codex:c1"}
        self.view.rebuild()
        rows = "\n".join(self.draw())
        self.assertNotIn("Price list", rows)
        self.assertIn(f"1 {glyphs(True)['open']}", rows)                  # shop holds the running one only
        self.type("archived")
        rows = self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Price list")).rstrip().endswith("· archived"))   # over the time
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown[2:], ["Rename", "Unarchive"])
        self.assertEqual(self.click(7, y + 4), Action("unarchive", (PRICES,)))

    def test_a_right_click_beside_the_conversations_offers_the_archived_ones_while_any_is(self):
        self.draw()
        self.assertIsNone(self.click(5, self.row_of("shop"), button=2))     # nothing archived: no menu at all
        self.assertIsNone(self.view.menu)
        self.view.archived = {"codex:c1"}
        self.view.rebuild()
        y, shown = self.menu_of("shop")
        self.assertEqual(shown, ["Show archived"])
        self.assertEqual(self.click(7, y + 1), Action("show_archived", (True,)))
        self.view.show_archived = True                                      # the app keeps it, for every tab
        self.view.rebuild()
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Price list")).rstrip().endswith("· archived"))
        self.assertEqual(self.style("Price list").fg, "archived")                 # a shade further back
        _, shown = self.menu_of("Price list")                                 # a conversation's: its own only
        self.assertEqual(shown, ["Open", "Copy conversation", "Rename", "Unarchive"])
        self.press("esc")
        empty = len(self.draw()) - 2                                          # an empty row below the list
        self.assertIsNone(self.click(5, empty, button=2))
        self.assertEqual(list(self.view.menu.menu.choices), ["Hide archived"])
        self.draw()
        self.assertEqual(self.press("enter"), Action("show_archived", (False,)))

    def marking(self):
        """shop with two closed conversations under its running one: Draft the README, then Price list."""
        self.view.set([LOGIN, RATES, PRICES, OLD, DRAFT], SPACES, PLACES.get, "shop")
        return self.draw()

    def test_space_marks_a_closed_one_and_shift_arrows_mark_on_the_way(self):
        self.marking()
        self.press("down")                                                  # Login redirect fix: running
        self.press("char", " ")
        self.assertEqual(self.view.marked, set())                           # it cannot be archived
        self.press("down")
        self.view.handle(Key("down", shift=True))                           # Draft the README, then Price list
        self.assertEqual(self.view.marked, {"claude:s5", "codex:c1"})
        self.press("char", " ")                                             # Price list again: unmarked
        self.assertEqual(self.view.marked, {"claude:s5"})
        rows = self.draw()
        self.assertEqual(rows[self.row_of("Draft the README")][1], "■")
        self.assertEqual(rows[self.row_of("Price list")][1], "□")         # while any is marked, every closed one's box
        self.assertEqual(rows[self.row_of("Login redirect fix")][1], " ")
        self.assertEqual(self.style("■", "Draft the README").fg, "accent")
        self.press("esc")                                                   # nothing typed: the marks go
        self.assertEqual(self.view.marked, set())
        self.assertNotIn("□", "\n".join(self.draw()))

    def test_once_something_is_typed_space_types(self):
        self.marking()
        self.type("rate limits")
        self.assertEqual(self.view.typed, "rate limits")
        self.assertEqual(self.view.marked, set())

    def test_a_closed_rows_box_shows_under_the_pointer_and_a_click_on_it_marks_it(self):
        self.marking()
        y = self.row_of("Price list")
        self.view.handle(Mouse("move", 12, y, 0))
        rows = self.draw()
        self.assertEqual(rows[y][1], "□")
        self.assertEqual(rows[self.row_of("Draft the README")][1], " ")    # only the one under the pointer
        self.assertIsNone(self.click(1, y))                                 # marked, not opened
        self.assertEqual(self.view.marked, {"codex:c1"})
        self.assertEqual(self.click(12, y), Action("open", (PRICES,)))    # the rest of the row as before
        y = self.row_of("Login redirect fix")
        self.view.handle(Mouse("move", 12, y, 0))
        self.assertEqual(self.click(1, y), Action("open", (LOGIN,)))      # a running one has no box
        self.assertEqual(self.view.marked, {"codex:c1"})

    def test_a_right_click_on_a_marked_row_archives_every_marked_one(self):
        self.marking()
        self.view.marked = {"claude:s5", "codex:c1"}
        _, shown = self.menu_of("Login redirect fix")                       # an unmarked row: its own menu
        self.assertEqual(shown[:2], ["Open", "Copy conversation"])
        self.press("esc")
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Archive 2 conversations", "Unmark all"])
        self.assertEqual(self.click(7, y + 1), Action("archive", (DRAFT, PRICES)))    # in the list's order
        self.assertEqual(self.view.marked, set())
        self.view.marked = {"claude:s5", "codex:c1"}
        y, _ = self.menu_of("Price list")
        self.assertIsNone(self.click(7, y + 2))                             # Unmark all
        self.assertEqual(self.view.marked, set())

    def test_the_marked_menu_counts_what_is_in_sight_and_unarchives_the_archived(self):
        self.marking()
        self.view.archived, self.view.show_archived = {"codex:c1"}, True
        self.view.marked = {"claude:s5", "codex:c1", "claude:s3"}           # Old notes: in a closed group
        self.view.rebuild()
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Archive 1 conversation", "Unarchive 1 conversation", "Unmark all"])
        self.assertEqual(self.click(7, y + 2), Action("unarchive", (PRICES,)))
        self.assertEqual(self.view.marked, {"claude:s5", "claude:s3"})
        self.type("price")                                                  # one marked one in sight: its own menu
        self.view.marked.add("codex:c1")
        _, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Open", "Copy conversation", "Rename", "Unarchive"])

    def rename(self, part):
        """Rename, from the right click's menu on the row of PART."""
        y, shown = self.menu_of(part)
        self.assertIsNone(self.click(7, y + 1 + shown.index("Rename")))
        return y

    def test_rename_edits_the_name_in_its_row(self):
        y = self.rename("Price list")
        self.draw()
        self.assertEqual(self.style("Price list").bg, "input")              # in a field, as it is now
        for _ in "list":
            self.press("backspace")
        self.type("sheet")
        self.assertEqual(self.view.typed, "")                               # not the filter's
        self.assertEqual(self.press("enter"), Action("rename", (PRICES, "Price sheet")))
        self.draw()
        self.assertNotEqual(self.style("Price list").bg, "input")           # the app gives it its new name
        self.assertEqual(self.row_of("Price list"), y)

    def test_a_running_one_is_renamed_too(self):
        self.rename("Login redirect fix")
        self.type(" now")
        self.assertEqual(self.press("enter"), Action("rename", (LOGIN, "Login redirect fix now")))

    def test_esc_an_empty_or_the_same_name_renames_nothing(self):
        self.rename("Price list")
        self.type(" now")
        self.assertIsNone(self.press("esc"))
        self.draw()
        self.assertNotEqual(self.style("Price list").bg, "input")
        self.rename("Price list")
        self.assertIsNone(self.press("enter"))                              # the same name
        self.rename("Price list")
        for _ in "Price list":
            self.press("backspace")
        self.assertIsNone(self.press("enter"))                              # nothing

    def test_a_click_outside_the_field_ends_the_rename(self):
        y = self.rename("Price list")
        self.draw()
        self.assertIsNone(self.click(12, y))                                # the field: it stays
        self.assertEqual(self.style("Price list").bg, "input")
        self.assertIsNone(self.click(12, self.row_of("Login redirect fix")))   # elsewhere: it ends, nothing opens
        self.draw()
        self.assertNotEqual(self.style("Price list").bg, "input")

    def test_before_anything_is_read_with_none_or_none_matching_it_says_so_as_the_app(self):
        view = ConversationList(now=lambda: NOW)
        canvas = Canvas(40, 10)
        shown = lambda: "\n".join(text(canvas, y) for y in range(10))      # noqa: E731
        view.draw(canvas, 0, 10, False)
        self.assertIn("Loading conversations…", shown())
        view.set([], [], PLACES.get, None)                                  # no workspace (outside herdr)
        view.draw(canvas, 0, 10, False)
        self.assertIn("No conversations", shown())
        view.set([LOGIN], SPACES, PLACES.get, "shop")
        view.field.insert("zzz")
        view.rebuild()
        view.draw(canvas, 0, 10, False)
        self.assertIn("No conversation matches", shown())

    def test_a_title_cannot_send_terminal_codes(self):
        evil = Conversation("claude", "s9", "Fix\x1b]52;c;ZXZpbA==\x07 it", "/repo/shop", NOW)
        self.view.set([evil], SPACES, PLACES.get, "shop")
        shown = "\n".join(self.draw())
        self.assertNotIn("\x1b", shown)
        self.assertNotIn("\x07", shown)


if __name__ == "__main__":
    unittest.main()
