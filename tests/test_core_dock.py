"""Tests for core/dock.py: the panels both clients draw and the groups they stand in, defined once."""
import os
import sys
import unittest

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import dock  # noqa: E402
import icons  # noqa: E402

RAIL = 8                      # the cells a short name has under its icon on the narrowest rail


class Panels(unittest.TestCase):
    def test_every_group_names_known_panels_once(self):
        named = [panel for _group, panels in dock.GROUPS for panel in panels]
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(set(named), set(dock.PANELS))
        self.assertEqual(len({group for group, _panels in dock.GROUPS}), len(dock.GROUPS))

    def test_a_short_name_fits_the_rail(self):
        for panel in dock.PANELS.values():
            with self.subTest(panel["title"]):
                self.assertLessEqual(len(panel["short"]), RAIL)

    def test_each_panel_has_a_tui_glyph(self):
        for name, panel in dock.PANELS.items():
            with self.subTest(name):
                self.assertIn(panel["glyph"], icons.NERD_GLYPHS)


if __name__ == "__main__":
    unittest.main()
