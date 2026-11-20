"""Tests for core/dock.py: the panels both clients draw and the groups they stand in, defined once."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import dock  # noqa: E402
import icons  # noqa: E402

RAIL = 8                      # the cells a name has under its icon on the narrowest rail


class Panels(unittest.TestCase):
    def test_every_group_names_known_panels_once(self):
        named = [panel for _group, panels in dock.GROUPS for panel in panels]
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(set(named), set(dock.PANELS))
        self.assertEqual(len({group for group, _panels in dock.GROUPS}), len(dock.GROUPS))

    def test_a_name_fits_the_rail(self):
        # one short name a panel: under its icon in the row and on the rail, and in the ⋯'s Panels
        for name, panel in dock.PANELS.items():
            with self.subTest(name):
                self.assertEqual(set(panel), {"name", "glyph"})
                self.assertLessEqual(len(panel["name"]), RAIL)

    def test_an_older_versions_id_names_a_panel_of_today(self):
        self.assertEqual(dock.FORMER, {"conversations": "chats"})
        self.assertLessEqual(set(dock.FORMER.values()), set(dock.PANELS))

    def test_the_row_goes_files_search_changes_issues_agent_chats(self):
        # the TUI's row and rail in this order, More after them; the Agent view under its own robot
        self.assertEqual([panel for _group, panels in dock.GROUPS for panel in panels],
                         ["files", "search", "changes", "issues", "agent", "chats"])
        self.assertEqual(dock.PANELS["agent"], {"name": "Agent", "glyph": "robot"})

    def test_each_panel_has_a_tui_glyph(self):
        for name, panel in dock.PANELS.items():
            with self.subTest(name):
                self.assertIn(panel["glyph"], icons.NERD_GLYPHS)


if __name__ == "__main__":
    unittest.main()
