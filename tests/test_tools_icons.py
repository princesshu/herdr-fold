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

    def test_a_makers_own_file_is_written_as_an_iconify_one_its_drawing_unchanged(self):
        # square, its own box centered in it, what its root gave every shape (fill="none") kept on a group round them
        made = icons.from_file(f'<svg width="30" height="20" viewBox="0 0 30 20" fill="none" xmlns="{icons.SVG}">\n'
                               '<path d="M1 1L29 1L15 19Z" fill="#F68330"/>\n</svg>\n')
        self.assertEqual(made.splitlines(), [
            '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 -5 30 30">',
            '  <g fill="none">', '    <path d="M1 1L29 1L15 19Z" fill="#F68330" />', "  </g>", "</svg>"])
        plain = icons.from_file(f'<svg xmlns="{icons.SVG}" viewBox="0 0 24 24"><path d="M5 12h14"/></svg>')
        self.assertEqual(plain, icons.svg('<path d="M5 12h14"/>', 24, 24))

    def test_a_makers_file_that_is_no_plain_drawing_is_refused(self):
        for text in ('<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 2"/>',
                     f'<svg xmlns="{icons.SVG}" viewBox="1 1 2 2"><path d="M0 0"/></svg>',     # not from 0 0
                     f'<svg xmlns="{icons.SVG}"><path d="M0 0"/></svg>',                        # no viewBox
                     f'<svg xmlns="{icons.SVG}" xmlns:x="urn:x" viewBox="0 0 2 2"><x:a x:b="c"/></svg>',
                     '<html><path d="M0 0"/></html>'):
            with self.subTest(text), self.assertRaises(ValueError):
                icons.from_file(text)


class Sets(unittest.TestCase):
    def test_the_logos_are_the_brands_core_knows(self):
        # a connector's (core/connectors.py) and a network's (core/icons.py); one drawn by its letter has none
        brands, networks = icons.core("connectors").BRANDS, icons.core("icons").NETWORKS
        self.assertEqual(sorted(icons.sets()["logos"]), sorted(one["logo"] for table in (brands, networks)
                                                               for one in table.values() if one["logo"]))
        self.assertLessEqual({"tailscale", "netbird", "zerotier"}, set(icons.sets()["logos"]))
        self.assertEqual(sorted(icons.sets()), ["catppuccin", "logos", "lucide"])

    def test_a_networks_plain_icon_is_lucides(self):
        self.assertLessEqual({"network", "globe", "shield"}, set(icons.sets()["lucide"]))

    def test_a_mark_svg_logos_lacks_comes_from_a_set_under_cc0_or_its_makers_own_file_at_a_tag(self):
        # ZeroTier's from Simple Icons, NetBird's from its repository (BSD-3-Clause) at a release, never a branch
        self.assertEqual(icons.ELSEWHERE["zerotier"], "simple-icons:zerotier")
        self.assertRegex(icons.ELSEWHERE["netbird"], r"^https://raw\.githubusercontent\.com/netbirdio/netbird/"
                                                     r"v\d+\.\d+\.\d+/client/.+/netbird\.svg$")
        self.assertLessEqual(set(icons.ELSEWHERE), set(icons.sets()["logos"]))

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
