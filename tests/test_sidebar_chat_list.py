"""Tests for chat_list.py: the Chats list (the Spaces list's workspaces and their chats), the
filter, opening by key or click, the right-click menu, archiving, and the chosen chat's plan under it."""
import os
import re
import sys
import unittest

from support import SRC, inset_band, set_attrs, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from chat_list import ChatList                  # noqa: E402
import widgets  # noqa: E402
from icons import glyphs  # noqa: E402
from chats import Chat                  # noqa: E402
from screen import Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

NOW = 1_800_000_000
LOGIN = Chat("claude", "s1", "Login redirect fix", "/repo/shop", NOW - 7200, "working", "w1:p1")
PRICES = Chat("codex", "c1", "Price list", "/repo/shop", NOW - 86400)
RATES = Chat("claude", "s2", "Rate limits", "/repo/api", NOW - 3600, "blocked", "w2:p1")
REVIEW = Chat("codex", "c2", "Review the API", "/repo/api", NOW - 600, "done", "w2:p2")
OLD = Chat("claude", "s3", "Old notes", "/notes", NOW - 30 * 86400)
STRAY = Chat("claude", "s4", "Somewhere else", "/tmp/other", NOW)
DRAFT = Chat("claude", "s5", "Draft the README", "/repo/shop", NOW - 9000)
PROBE = Chat("opencode", "ses_b2", "Readiness probe", "/repo/shop", NOW - 5000)     # a row of OpenCode's database
TILES = Chat("copilot", "0cb916db", "Tile cache", "/repo/shop", NOW - 6000)       # a folder of Copilot's store
PLACES = {"/repo/shop": "shop", "/repo/api": "api", "/notes": "notes"}
SPACES = ["notes", "shop", "api", "empty"]                   # as the Spaces list has them
HEADER = 3                                                   # the filter, tall as the dock's other fields


class List(unittest.TestCase):
    def setUp(self):
        set_attrs(self, widgets, TURN=0)                  # each fold at rest at once: Turning has the turn's own tests
        self.view = ChatList(now=lambda: NOW)
        self.view.set([LOGIN, RATES, PRICES, OLD, STRAY], SPACES, PLACES.get, "shop")

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

    def index(self, found):
        return next(i for i, row in enumerate(self.view.list.items) if found(row))

    def test_a_chosen_row_stands_a_cell_in_from_each_side_its_content_a_cell_inside(self):
        # as the filter stands above it: a space's chevron and count, a chat's mark, name, agent and age, a closed
        # one's box under the mouse, each a cell inside the highlight
        self.draw()
        self.view.list.index = self.index(lambda row: row[0] == "group" and row[1] == "shop")
        self.draw()
        inset_band(self, self.canvas, self.row_of("shop"))
        self.view.list.index = self.index(lambda row: row[1] == LOGIN)
        self.draw()
        inset_band(self, self.canvas, self.row_of("Login redirect fix"))
        self.view.hover = self.index(lambda row: row[1] == PRICES)          # closed: its box at the row's start
        self.draw()
        inset_band(self, self.canvas, self.row_of("Price list"), lit="hover")

    def test_the_filter_then_the_spaces(self):
        rows = self.draw()
        self.assertIn("Filter chats", rows[1])                               # the field's row, as the dock's fields
        self.assertEqual(rows[HEADER].split()[1], "notes", rows)
        self.assertNotIn("Chats", "\n".join(rows))                          # the frame round it names it
        low = self.draw(roomy=False)                                         # a low pane: the field a chip
        self.assertIn("Filter chats", low[0])
        self.assertEqual(low[2].split()[1], "notes", low)

    def test_the_spaces_with_chats_in_their_order_the_current_one_open_its_chats_under_its_name(self):
        shown = [line for line in self.draw()[HEADER:] if line.strip()]
        groups = [line.split() for line in shown if not line.startswith("   ")]
        self.assertEqual([words[1] for words in groups], ["notes", "shop", "api"])       # "empty" has none
        closed, opened = glyphs(True)["closed"], glyphs(True)["open"]          # the file tree's chevrons, as every fold
        self.assertEqual([(words[0], words[-1]) for words in groups], [(closed, "1"), (opened, "2"), (closed, "1")])
        self.assertEqual([line[:6] for line in shown[2:4]], ["    ● ", "    · "])   # its own, the newest first
        self.assertIn("Login redirect fix", shown[2])
        self.assertIn("Price list", shown[3])

    def test_a_space_opened_turns_its_chevron_through_45_degrees(self):
        now = [5.0]
        set_attrs(self, widgets, TURN=0.08, TURNS=widgets.Turns(clock=lambda: now[0]))
        self.view.toggle("notes")
        def marks():
            return [line.split()[0] for line in self.draw()[HEADER:] if line.split()[1:2] == ["notes"]]
        self.assertEqual(marks(), ["⌟"])
        now[0] += widgets.TURN
        self.assertEqual(marks(), [glyphs(True)["open"]])

    def test_without_icons_a_space_folds_with_the_plain_marks_the_tree_has(self):
        self.view.icons = False
        groups = [line.split() for line in self.draw()[HEADER:] if line.strip() and not line.startswith("   ")]
        self.assertEqual([words[0] for words in groups], [glyphs(False)["closed"], glyphs(False)["open"],
                                                          glyphs(False)["closed"]])

    def test_a_space_is_its_dim_chevron_its_name_the_current_one_bold_and_its_count_no_dot(self):
        rows = self.draw()
        shop, notes = self.style("shop"), self.style("notes")
        self.assertEqual((shop.fg, shop.bold), ("text", True))                    # the current one: bold
        self.assertEqual((notes.fg, notes.bold), ("subtext", False))
        self.assertEqual((self.style(glyphs(True)["closed"], at="notes").fg, self.style("1", at="notes").fg),
                         ("muted", "muted"))
        self.assertEqual((self.style(glyphs(True)["open"], at="shop").fg, self.style("2", at="shop").fg),
                         ("muted_row", "muted_row"))                        # the chosen one's: readable on its band
        self.assertEqual(rows[self.row_of("shop")][:8], f"  {glyphs(True)['open']} shop")  # the chevron first

    def test_the_chat_of_the_workspaces_active_tab_leads_its_group(self):
        newer = Chat("claude", "s5", "Newer notes", "/repo/shop", NOW)             # written to a moment ago
        self.view.set([LOGIN, RATES, PRICES, newer], SPACES, PLACES.get, "shop")
        self.draw()
        self.assertLess(self.row_of("Newer notes"), self.row_of("Login redirect fix"))   # by time alone
        self.view.front = {"w1:p1"}                                         # Login's pane: its tab is the active one
        self.view.rebuild()
        self.draw()
        self.assertLess(self.row_of("Login redirect fix"), self.row_of("Newer notes"))
        self.assertLess(self.row_of("Newer notes"), self.row_of("Price list"))           # the rest by time

    def test_a_chat_outside_every_space_is_not_shown(self):
        self.type("somewhere")
        self.assertNotIn("Somewhere else", "\n".join(self.draw()))

    def test_a_running_one_is_lit_in_its_states_color_and_a_closed_one_faint(self):
        self.draw()
        self.assertEqual(self.style("●", at="Login redirect fix").fg, "modified")  # working
        self.assertEqual(self.style("Login redirect fix").fg, "subtext")
        self.assertEqual(self.style("·", at="Price list").fg, "guide")
        self.assertEqual(self.style("Price list").fg, "muted")

    def test_each_row_says_its_agent_and_how_long_ago_in_two_right_aligned_columns(self):
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Login")).rstrip().endswith("Claude  2h"))
        self.assertTrue(text(self.canvas, self.row_of("Price")).rstrip().endswith(" Codex  1d"))
        self.assertEqual((self.style("Claude", at="Login").fg, self.style("2h", at="Login").fg), ("muted", "muted"))
        self.press("down")                                                  # chosen: still legible on its band
        self.draw()
        self.assertEqual((self.style("Claude", at="Login").fg, self.style("2h", at="Login").fg),
                         ("muted_row", "muted_row"))
        self.draw(cells=24)                                                 # narrow: how long ago only
        self.assertTrue(text(self.canvas, self.row_of("Login")).rstrip().endswith(" 2h"))
        self.assertNotIn("Claude", text(self.canvas, self.row_of("Login")))

    def test_enter_opens_a_chat_and_toggles_a_group(self):
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
        self.press("left")                                                  # from a chat: to its group
        self.press("left")
        self.assertNotIn("Login redirect fix", "\n".join(self.draw()))
        self.press("right")
        self.assertIn("Login redirect fix", "\n".join(self.draw()))

    def test_typing_filters_every_group_and_deleting_it_brings_them_back(self):
        self.type("rate")
        rows = self.draw()
        self.assertIn("rate", rows[1])                                      # in the field
        self.assertIn("Rate limits", "\n".join(rows))
        self.assertNotIn("Login redirect fix", "\n".join(rows))
        for _ in "rate":
            self.press("backspace")
        self.assertEqual(self.view.typed, "")
        self.assertIn("Login redirect fix", "\n".join(self.draw()))

    def test_a_click_opens_a_chat_or_a_group(self):
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
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Archive", "Delete…"])
        self.assertEqual(self.click(7, y + 2), Action("copy", (PRICES,)))      # the menu opens where clicked
        self.click(5, y, button=2)
        self.draw()
        self.assertEqual(self.press("enter"), Action("open", (PRICES,)))   # the menu takes the keys meanwhile
        _, shown = self.menu_of("Login redirect fix")                     # running: no Archive; Claude's: Checkpoints…
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Checkpoints…"])

    def test_its_menu_closes_when_the_pane_loses_the_keys(self):
        y, _ = self.menu_of("Price list")
        self.view.close_menu()                                              # a click in another pane
        self.assertNotIn("Copy chat", "\n".join(self.draw()))
        self.assertEqual(self.click(5, y), Action("open", (PRICES,)))       # a click acts again at once

    def test_an_archived_one_is_off_the_list_and_typing_finds_it(self):
        self.view.archived = {"codex:c1"}
        self.view.rebuild()
        rows = "\n".join(self.draw())
        self.assertNotIn("Price list", rows)
        self.assertTrue(text(self.canvas, self.row_of("shop")).rstrip().endswith(" 1"))    # the running one only
        self.type("archived")
        rows = self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Price list")).rstrip().endswith("Codex  archived"))  # its age
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown[2:], ["Rename", "Unarchive", "Delete…"])
        self.assertEqual(self.click(7, y + 4), Action("unarchive", (PRICES,)))

    def test_a_right_click_beside_the_chats_offers_the_archived_ones_while_any_is(self):
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
        self.assertTrue(text(self.canvas, self.row_of("Price list")).rstrip().endswith("Codex  archived"))
        self.assertEqual(self.style("Price list").fg, "archived")                 # a shade further back
        _, shown = self.menu_of("Price list")                                 # a chat's: its own only
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Unarchive", "Delete…"])
        self.press("esc")
        empty = len(self.draw()) - 2                                          # an empty row below the list
        self.assertIsNone(self.click(5, empty, button=2))
        self.assertEqual(list(self.view.menu.menu.choices), ["Hide archived"])
        self.draw()
        self.assertEqual(self.press("enter"), Action("show_archived", (False,)))

    def test_more_lists_show_archived_while_any_is_and_hide_archived_while_they_show(self):
        self.assertEqual(self.view.menu_lines(), [])
        self.view.archived = {"codex:c1"}
        self.assertEqual(self.view.menu_lines(), ["Show archived"])
        self.assertEqual(self.view.menu_pick("Show archived"), Action("show_archived", (True,)))
        self.view.show_archived = True
        self.assertEqual(self.view.menu_lines(), ["Hide archived"])
        self.assertEqual(self.view.menu_pick("Hide archived"), Action("show_archived", (False,)))

    def marking(self):
        """shop with two closed chats under its running one: Draft the README, then Price list."""
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
        self.assertEqual(rows[self.row_of("Draft the README")][2], "■")
        self.assertEqual(rows[self.row_of("Price list")][2], "□")         # while any is marked, every closed one's box
        self.assertEqual(rows[self.row_of("Login redirect fix")][2], " ")
        self.assertEqual(self.style("■", "Draft the README").fg, "accent")
        self.view.shut()                                                    # the list closed: the marks go
        self.assertEqual(self.view.marked, set())
        self.assertNotIn("□", "\n".join(self.draw()))

    def test_closed_its_menu_and_a_name_being_typed_go_what_was_typed_stays(self):
        self.type("rate")
        _, shown = self.menu_of("Rate limits")
        self.view.shut()
        self.assertEqual((self.view.menu, self.view.typed), (None, "rate"))
        self.click(7, self.menu_of("Rate limits")[0] + 1 + shown.index("Rename"))
        self.assertIsNotNone(self.view.naming)
        self.view.shut()
        self.assertIsNone(self.view.naming)

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
        self.assertEqual(rows[y][2], "□")
        self.assertEqual(rows[self.row_of("Draft the README")][2], " ")    # only the one under the pointer
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
        self.assertEqual(shown[:2], ["Open", "Copy chat"])
        self.press("esc")
        y, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Archive 2 chats", "Unmark all"])
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
        self.assertEqual(shown, ["Archive 1 chat", "Unarchive 1 chat", "Unmark all"])
        self.assertEqual(self.click(7, y + 2), Action("unarchive", (PRICES,)))
        self.assertEqual(self.view.marked, {"claude:s5", "claude:s3"})
        self.type("price")                                                  # one marked one in sight: its own menu
        self.view.marked.add("codex:c1")
        _, shown = self.menu_of("Price list")
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Unarchive", "Delete…"])

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

    def ask(self, part="Price list"):
        """Delete… of the right click's menu on the row of PART: the screen then."""
        y, shown = self.menu_of(part)
        self.assertIsNone(self.click(7, y + 1 + shown.index("Delete…")))
        return self.draw()

    def test_delete_asks_first_by_the_chats_name_cancel_chosen(self):
        rows = self.ask()
        asked = "\n".join(rows)
        self.assertIn("Move the chat “Price list” to the Trash?", asked)
        self.assertEqual(rows[-1].split(), ["Move", "Cancel"])              # the dock's own question, at its foot
        self.assertEqual(self.style("Cancel").bg, "button")
        self.assertIsNone(self.press("enter"))                              # Cancel: nothing done
        rows = "\n".join(self.draw())
        self.assertNotIn("to the Trash?", rows)
        self.assertIn("Price list", rows)

    def test_a_yes_takes_the_row_off_at_once_and_the_list_stays_where_it_was(self):
        self.view.set([LOGIN, DRAFT, PRICES, RATES, OLD], SPACES, PLACES.get, "shop")
        self.draw()
        self.view.list.index = self.row_of("Draft the README") - HEADER
        before = self.draw()
        self.ask("Draft the README")
        self.assertEqual(self.press("char", "y"), Action("delete", (DRAFT,)))
        after = self.draw()
        self.assertNotIn("Draft the README", "\n".join(after))
        y = self.row_of("Price list")
        self.assertEqual(before[y - 1], after[y - 1])                       # the rows above as they were
        self.assertIn("Draft the README", before[y])                        # and the next one in its place, chosen
        self.assertEqual(self.view.list.selected()[1], PRICES)

    def test_the_questions_buttons_take_a_click_and_esc_gives_it_up(self):
        rows = self.ask()
        y = len(rows) - 1
        self.assertIsNone(self.click(rows[y].index("Cancel"), y))
        self.assertIsNone(self.view.confirm)
        rows = self.ask()
        self.assertIsNone(self.click(5, self.row_of("Login redirect fix")))  # a click beside them: still asked
        self.assertIsNotNone(self.view.confirm)
        self.assertEqual(self.click(rows[y].index("Move"), y), Action("delete", (PRICES,)))

    def test_the_delete_key_asks_for_a_closed_one_while_nothing_is_typed(self):
        self.draw()
        self.view.list.index = self.row_of("Price list") - HEADER
        self.assertIsNone(self.press("delete"))
        self.assertIn("Move the chat “Price list” to the Trash?", "\n".join(self.draw()))
        self.assertIsNone(self.press("esc"))
        self.assertIsNone(self.view.confirm)
        self.view.list.index = self.row_of("Login redirect fix") - HEADER   # a running one: told, never asked
        self.assertEqual(self.press("delete"), Action("no_delete", (LOGIN,)))
        self.assertIsNone(self.view.confirm)
        self.view.list.index = self.row_of("shop") - HEADER                 # a space: nothing
        self.assertIsNone(self.press("delete"))
        self.assertIsNone(self.view.confirm)

    def test_an_opencode_chat_is_archived_never_deleted_here(self):
        # OpenCode keeps its chats in its database, no file of its own to move to the Trash
        self.view.set([LOGIN, PROBE, PRICES], SPACES, PLACES.get, "shop")
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Readiness probe")).rstrip().endswith("OpenCode  1h"))
        _, shown = self.menu_of("Readiness probe")
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Archive"])
        self.press("esc")
        self.draw()
        self.view.list.index = self.row_of("Readiness probe") - HEADER
        self.assertEqual(self.press("delete"), Action("no_delete", (PROBE,)))
        self.assertIsNone(self.view.confirm)

    def test_a_copilot_chat_is_archived_never_deleted_here(self):
        # Copilot keeps each chat in its session store, which its own /session delete keeps in order
        self.view.set([LOGIN, TILES, PRICES], SPACES, PLACES.get, "shop")
        self.draw()
        self.assertTrue(text(self.canvas, self.row_of("Tile cache")).rstrip().endswith("Copilot  1h"))
        _, shown = self.menu_of("Tile cache")
        self.assertEqual(shown, ["Open", "Copy chat", "Rename", "Archive"])
        self.press("esc")
        self.draw()
        self.view.list.index = self.row_of("Tile cache") - HEADER
        self.assertEqual(self.press("delete"), Action("no_delete", (TILES,)))
        self.assertIsNone(self.view.confirm)

    def test_once_something_is_typed_delete_edits_the_filter(self):
        self.type("price")
        self.draw()
        self.view.list.index = self.row_of("Price list") - HEADER
        self.assertIsNone(self.press("delete"))
        self.assertIsNone(self.view.confirm)

    def test_a_long_name_is_cut_in_the_question(self):
        long = Chat("claude", "s8", "Rewrite the importer so that every row is checked " * 4, "/repo/shop", NOW - 5)
        self.view.set([long], SPACES, PLACES.get, "shop")
        self.draw()
        self.view.list.index = self.row_of("Rewrite") - HEADER
        self.press("delete")
        asked = [row for row in self.draw() if "“" in row or "”" in row or "Trash?" in row]
        self.assertLessEqual(len(asked), 3)
        self.assertIn("…”", "\n".join(asked))

    def test_a_deleted_one_stays_off_until_the_list_is_read_without_it_and_comes_back_if_it_failed(self):
        self.ask()
        self.press("char", "y")
        self.view.set([LOGIN, RATES, PRICES, OLD], SPACES, PLACES.get, "shop")      # a read begun before it went
        self.assertNotIn("Price list", "\n".join(self.draw()))
        self.view.set([LOGIN, RATES, OLD], SPACES, PLACES.get, "shop")              # the file is gone
        self.assertEqual(self.view.gone, set())
        self.view.gone = {"codex:c1"}
        self.view.set([LOGIN, RATES, PRICES, OLD], SPACES, PLACES.get, "shop")
        self.view.back(PRICES)                                                      # the Trash refused it
        self.assertIn("Price list", "\n".join(self.draw()))

    def test_closed_the_question_goes(self):
        self.ask()
        self.view.shut()
        self.assertIsNone(self.view.confirm)
        self.assertNotIn("to the Trash?", "\n".join(self.draw()))

    def test_before_anything_is_read_with_none_or_none_matching_it_says_so_as_the_app(self):
        view = ChatList(now=lambda: NOW)
        canvas = Canvas(40, 10)
        shown = lambda: "\n".join(text(canvas, y) for y in range(10))      # noqa: E731
        view.draw(canvas, 0, 10, False)
        self.assertIn("Loading chats…", shown())
        view.set([], [], PLACES.get, None)                                  # no workspace (outside herdr)
        view.draw(canvas, 0, 10, False)
        self.assertIn("No chats", shown())
        view.set([LOGIN], SPACES, PLACES.get, "shop")
        view.field.insert("zzz")
        view.rebuild()
        view.draw(canvas, 0, 10, False)
        self.assertIn("No chat matches", shown())

    def test_a_title_cannot_send_terminal_codes(self):
        evil = Chat("claude", "s9", "Fix\x1b]52;c;ZXZpbA==\x07 it", "/repo/shop", NOW)
        self.view.set([evil], SPACES, PLACES.get, "shop")
        shown = "\n".join(self.draw())
        self.assertNotIn("\x1b", shown)
        self.assertNotIn("\x07", shown)


STEPS = [("Keep the page inside 1…pages", "done", None), ("Answer page 0 with the first page", "done", None),
         ("Add the tests past the end", "now", None), ("Run the whole suite", "next", "after Add the tests")]
PLAN = {"steps": [{"text": words, "state": state, "after": after} for words, state, after in STEPS], "note": None,
        "done": "2 done", "count": "2 of 4 done", "finished": False, "plan": 4}


class ChosenPlan(unittest.TestCase):
    """The chosen chat's plan (core/plan.py's list, read by the panel) under its row, and under no other."""
    draw, row_of, style, press, click = List.draw, List.row_of, List.style, List.press, List.click

    def setUp(self):
        List.setUp(self)
        self.view.list.index = next(i for i, row in enumerate(self.view.list.items) if row[1] == LOGIN)
        self.view.plan = ("claude:s1", PLAN)

    def plan_rows(self, **how):
        rows = self.draw(**how)
        start = self.row_of("Login redirect fix") + 1
        return rows[start:self.row_of("Price list")]

    def test_the_plan_stands_under_the_chosen_chat_its_done_steps_in_one_row(self):
        rows = self.plan_rows()
        self.assertEqual([" ".join(row.split()) for row in rows], [
            "Plan Open the plan", f"✓ 2 done {glyphs(True)['closed']}", "◐ Add the tests past the end",
            "○ Run the whole sui… after Add the…"])
        self.assertTrue(all(row.startswith(" " * 6) for row in rows))        # under the chat's name
        self.assertEqual((self.style("◐").fg, self.style("✓").fg, self.style("after").fg), ("accent", "done", "muted"))
        self.assertTrue(rows[3].endswith("after Add the…"))                  # what it waits for at the right edge

    def test_another_chat_chosen_shows_none_and_a_group_neither(self):
        self.press("down")
        self.assertNotIn("Plan", "\n".join(self.draw()))
        self.press("up")
        self.press("up")
        self.assertNotIn("Plan", "\n".join(self.draw()))
        self.assertIsNone(self.view.chosen())

    def test_right_lists_the_done_steps_left_puts_them_back_then_goes_to_the_group(self):
        self.press("right")
        rows = [" ".join(row.split()) for row in self.plan_rows()]
        self.assertEqual(rows[1:4], [f"✓ 2 done {glyphs(True)['open']}", "Keep the page inside 1…pages",
                                     "Answer page 0 with the first page"])
        self.press("left")
        self.assertEqual(len(self.plan_rows()), 4)
        self.assertEqual(self.view.chosen(), LOGIN)
        self.press("left")
        self.assertIsNone(self.view.chosen())                                # on its group now

    def test_a_click_on_the_done_row_lists_them_and_open_the_plan_asks_for_it(self):
        self.draw()
        y = self.row_of("2 done")
        self.assertIsNone(self.click(8, y))
        self.assertEqual(len(self.plan_rows()), 6)
        row = self.row_of("Open the plan")
        self.assertEqual(self.click(text(self.canvas, row).index("Open the plan"), row), Action("plan", (LOGIN,)))
        self.assertIsNone(self.click(6, row))                                # the plan's own lines are no chat's row
        self.assertEqual(self.view.chosen(), LOGIN)

    def test_a_finished_plan_is_one_line_and_one_never_approved_has_no_link(self):
        self.view.plan = ("claude:s1", {**PLAN, "finished": True, "count": "All 4 done", "plan": None})
        self.assertEqual([" ".join(row.split()) for row in self.plan_rows()], ["Plan All 4 done"])
        self.assertEqual(self.style("All 4 done").fg, "done")
        self.assertEqual(self.press("right"), Action("checkpoints", (LOGIN,)))   # no step to list: its checkpoints

    def test_a_note_wraps_to_two_rows_over_the_steps(self):
        self.view.plan = ("claude:s1", {**PLAN, "note": "Tables first, so the docs can quote the real page size."})
        rows = [" ".join(row.split()) for row in self.plan_rows(cells=38)]
        self.assertEqual(rows[1:3], ["Tables first, so the docs can", "quote the real page size."])

    def test_a_narrow_pane_cuts_the_words_and_leaves_out_what_a_step_waits_for(self):
        rows = self.plan_rows(cells=30)
        self.assertEqual([" ".join(row.split()) for row in rows][2:], ["◐ Add the tests past …",
                                                                       "○ Run the whole suite"])
        self.assertTrue(all(len(row) <= 28 for row in rows))                # a cell inside a highlight's end

    def test_a_low_pane_keeps_the_chosen_chat_in_sight_over_its_plan(self):
        rows = self.draw(rows=HEADER + 4)
        self.assertIn("Login redirect fix", "\n".join(rows))
        self.assertIn("Plan", rows[-1] + rows[-2] + rows[-3])


if __name__ == "__main__":
    unittest.main()
