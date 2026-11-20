"""Tests for tools/icons.py, which fetches the Herdr app mod's icons from Iconify by name: the SVG files it writes keep
to the repository's line width with their drawing unchanged, the icons folders hold what its lists name, and a set
is fetched alone by its name."""
import importlib.util
import os
import re
import unittest
import xml.etree.ElementTree as ET

from support import PACKAGE

# by its path, under a name of its own: the core's and the sidebar's icons.py go by "icons" in the same run
SPEC = importlib.util.spec_from_file_location("tools_icons", os.path.join(PACKAGE, "tools", "icons.py"))
icons = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(icons)

PATH = "M1 2" + "".join(f"l1.5e-3 {n}c1 2 3 4 5 6" for n in range(40)) + "z"


class Svg(unittest.TestCase):
    def test_a_long_path_breaks_before_its_commands_and_draws_the_same(self):
        text = icons.svg(f'<path fill="none" stroke="currentColor" d="{PATH}"/>', 24, 24)
        lines = text.splitlines()
        self.assertLessEqual(max(map(len, lines)), icons.WIDTH)
        self.assertFalse([line for line in lines if line.strip().startswith("e")])       # an exponent stays whole
        path = ET.fromstring(text)[0]
        self.assertEqual(re.sub(r"\s+", "", path.get("d")), re.sub(r"\s+", "", PATH))
        self.assertEqual((path.get("fill"), path.get("stroke")), ("none", "currentColor"))

    def test_a_short_icon_is_an_element_a_line(self):
        self.assertEqual(icons.svg('<path d="M5 12h14"/>', 24, 24).splitlines(), [
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">',
            '  <path d="M5 12h14" />', "</svg>"])

    def test_an_answer_with_a_dtd_or_an_entity_is_refused(self):
        with self.assertRaises(ValueError):
            icons.svg('<!ENTITY x "y"><path d="M0 0"/>', 24, 24)


class Sets(unittest.TestCase):
    def test_the_logos_are_the_brands_core_knows(self):
        spec = importlib.util.spec_from_file_location("core_connectors", os.path.join(PACKAGE, "core", "connectors.py"))
        connectors = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(connectors)
        self.assertEqual(sorted(icons.sets()["logos"]), sorted(one["logo"] for one in connectors.BRANDS.values()))
        self.assertEqual(sorted(icons.sets()), ["catppuccin", "logos", "lucide"])

    def test_a_set_is_fetched_alone_by_its_name(self):
        # a set fetched again may have moved on at Iconify: one named leaves the others' files as they are
        self.assertEqual(icons.chosen(["logos"]), {"logos": icons.sets()["logos"]})
        self.assertEqual(icons.chosen(["lucide", "logos"]), {name: icons.sets()[name] for name in ("lucide", "logos")})
        self.assertEqual(icons.chosen([]), icons.sets())
        with self.assertRaises(SystemExit):
            icons.chosen(["logos", "simple-icons"])

    def test_the_request_names_a_tool_not_a_person(self):
        self.assertRegex(icons.AGENT, r"^[a-z-]+$")


class Folders(unittest.TestCase):
    def test_each_folder_holds_what_its_list_names(self):
        for prefix, names in icons.sets().items():
            with self.subTest(prefix):
                held = sorted(name[:-len(".svg")] for name in os.listdir(os.path.join(icons.ICONS, prefix)))
                self.assertEqual(held, sorted(names), "out of date: /usr/bin/python3 tools/icons.py")


if __name__ == "__main__":
    unittest.main()
