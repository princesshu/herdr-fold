"""Tests for install.sh's first question, the TUI, the Herdr app or both: its default, its page in the browser, the
switch that answers it, and what an update or a step-by-step run of an earlier install does with it."""
import os
import re
import subprocess
import sys
import unittest

from support import PACKAGE, AppInstall, catalog_text, run_in_terminal, stubs


class FirstQuestion(AppInstall, unittest.TestCase):
    def asked(self, replies=None):
        """The installer in a terminal: what REPLIES gives for a question its text is in typed there, Enter
        elsewhere; its output."""
        env = {k: v for k, v in self.env.items() if k != "HERDR_FOLD_YES"}
        replies = {catalog_text(key): reply for key, reply in (replies or {}).items()}
        shown, ended = run_in_terminal(["/bin/bash", os.path.join(self.pkg, "install.sh")], env,
                                       lambda line: next((r for text, r in replies.items() if text in line), ""),
                                       timeout=240)
        self.assertTrue(ended, shown[-2000:])
        return shown

    def parts(self):
        state = os.path.join(self.home, ".local", "state", "herdr-fold")
        out = subprocess.run([sys.executable, "-B", os.path.join(self.pkg, "src", "parts.py"), state],
                             capture_output=True, text=True, check=True)
        return out.stdout.split()

    def with_parts(self, parts):
        self.env["HERDR_FOLD_PARTS"] = parts
        out = self.run_script("install.sh")
        del self.env["HERDR_FOLD_PARTS"]
        return out

    def test_with_the_app_found_both_is_the_default(self):
        self.with_app()
        out = self.asked()
        self.assertIn(f"{catalog_text('install.parts_ask')} [3]", out)
        self.assertEqual(self.parts(), ["tui", "app"])

    def test_without_it_the_tui_is(self):
        out = self.asked()
        self.assertIn(f"{catalog_text('install.parts_ask')} [1]", out)
        self.assertEqual(self.parts(), ["tui"])

    def test_the_page_opens_with_what_is_there(self):
        self.with_app()
        opened = os.path.join(self.tmp, "opened")
        stubs(self.fakes, {"open": f'#!/bin/sh\necho "$*" >> {opened}\n'})
        self.asked()
        with open(opened) as f:
            pages = [line for line in f.read().splitlines() if "/src/install/parts.html" in line]
        self.assertEqual(len(pages), 1, pages)
        self.assertTrue(pages[0].startswith("file://") and pages[0].endswith("#found"), pages)

    def test_the_switch_answers_it(self):
        self.with_app()
        out = self.with_parts("app")
        self.assertNotIn(catalog_text("install.parts_ask"), out)
        self.assertIn(catalog_text("install.parts_set_app"), out)
        self.assertIn("herdr-fold.app", self.recorded())

    def test_a_switch_it_does_not_know_is_said_and_the_default_taken(self):
        out = self.with_parts("all")
        self.assertIn(catalog_text("install.parts_unknown", "all"), out)
        self.assertIn(catalog_text("install.parts_set_tui"), out)

    def test_an_update_keeps_the_parts_and_asks_nothing(self):
        self.with_app()
        self.run_script("install.sh")
        out = self.asked()
        self.assertNotIn(catalog_text("install.parts_ask"), out)
        self.assertEqual(self.parts(), ["tui", "app"])

    def test_fewer_parts_keep_what_is_there(self):
        self.with_app()
        self.with_parts("tui")
        out = self.asked({"install.update_ask": "n", "install.parts_ask": "2"})
        self.assertIn(catalog_text("install.parts_kept_tui"), out)
        self.assertEqual(self.parts(), ["tui", "app"])

    def test_the_app_added_to_a_tui_install(self):
        self.with_app()
        self.with_parts("tui")
        self.assertNotIn("herdr-fold.app", self.recorded())
        out = self.asked({"install.update_ask": "n", "install.parts_ask": "3"})
        self.assertIn(f"{catalog_text('install.parts_ask')} [1]", out)
        self.assertEqual(self.parts(), ["tui", "app"])


class Page(unittest.TestCase):
    def test_the_page_loads_nothing_from_outside(self):
        """src/install/parts.html: no address of another place, and every picture it shows is the package's own."""
        page = os.path.join(PACKAGE, "src", "install", "parts.html")
        with open(page, encoding="utf-8") as f:
            text = f.read()
        self.assertNotRegex(text, r"https?:|//[\w.-]+\.\w")
        pictures = re.findall(r'src="([^"]+)"', text)
        self.assertEqual(len(pictures), 2)
        for rel in pictures:
            path = os.path.normpath(os.path.join(os.path.dirname(page), rel))
            self.assertTrue(path.startswith(PACKAGE + os.sep) and os.path.isfile(path), rel)


if __name__ == "__main__":
    unittest.main()
