"""Tests for install.sh's first question, the TUI, the Herdr app or both: its default, its page in the browser, the
switch that answers it, and what an update or a step-by-step run of an earlier install does with it."""
import os
import re
import subprocess
import sys
import unittest

from support import APP_STUB, PACKAGE, AppInstall, catalog_text, run_in_terminal, stubs


class PartsInstall(AppInstall):
    """install.sh run as a person runs it (asked), or with HERDR_FOLD_PARTS (with_parts); the parts on its record."""

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


class FirstQuestion(PartsInstall, unittest.TestCase):
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


class MissingApp(PartsInstall, unittest.TestCase):
    """The Herdr app chosen and not on this Mac: its own installer (a curl stub whose script puts a herdr-app
    command line where the app's installer does) offered after a yes, in a terminal only."""

    def setUp(self):
        super().setUp()
        self.curl_log = os.path.join(self.tmp, "curl-calls")
        fake = os.path.join(self.tmp, "fake-herdr-app")
        with open(fake, "w") as f:
            f.write(APP_STUB)
        os.chmod(fake, 0o755)
        script = f'mkdir -p "$HOME/.local/bin" && cp {fake} "$HOME/.local/bin/herdr-app"'
        stubs(self.fakes, {"curl": f'#!/bin/sh\necho "curl $*" >> {self.curl_log}\necho \'{script}\'\n'})

    def curls(self):
        if not os.path.exists(self.curl_log):
            return []
        with open(self.curl_log) as f:
            return f.read().splitlines()

    def test_a_missing_app_is_offered_its_installer(self):
        out = self.asked({"install.parts_ask": "3"})
        self.assertIn(catalog_text("install.app_install_ask"), out)
        self.assertEqual(self.curls(), ["curl -fsSL https://releases.herdr.dev/app/install.sh"])
        self.assertIn("herdr-fold.app", self.recorded())
        self.assertEqual(self.parts(), ["tui", "app"])

    def test_without_a_terminal_the_installer_never_runs(self):
        out = self.with_parts("both")
        self.assertEqual(self.curls(), [])
        later = catalog_text("install.app_install_later", "curl -fsSL https://releases.herdr.dev/app/install.sh | sh")
        self.assertIn(later, out)
        self.assertEqual(self.parts(), ["tui"])


class ChosenParts(PartsInstall, unittest.TestCase):
    """Each step does what the chosen parts need: the TUI's files, programs, shell block, plugins and integrations
    with the TUI only; the app's part with the app only; the status line and GitHub for both."""

    def herdr_calls(self):
        log = os.path.join(self.tmp, "herdr-calls")
        if not os.path.exists(log):
            return []
        with open(log) as f:
            return f.read().splitlines()

    def test_the_app_alone_writes_no_tui_file(self):
        self.with_app()
        self.with_parts("app")
        self.assertFalse(os.path.exists(self.path(".config/ghostty/config")))
        self.assertFalse(os.path.exists(self.path(".config/starship.toml")))
        self.assertNotIn("herdr-fold", self.read(".zshrc") if os.path.exists(self.path(".zshrc")) else "")
        self.assertEqual([call for call in self.herdr_calls() if "plugin link" in call], [])
        self.assertTrue(os.path.isfile(self.path(".config/herdr-fold/statusline.py")))
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))
        self.assertEqual(self.parts(), ["app"])

    def test_the_app_alone_without_herdr_runs_no_herdr(self):
        os.remove(os.path.join(self.fakes, "herdr"))
        self.with_app()
        out = self.with_parts("app")
        said = [line for line in out.splitlines() if re.search(r"\bherdr\b(?!-)", line) and re.search("[!✗]", line)]
        self.assertEqual(said, [])
        self.assertEqual(self.parts(), ["app"])

    def test_the_tui_alone_puts_nothing_in_the_app(self):
        self.with_app()
        self.with_parts("tui")
        self.assertFalse(os.path.exists(self.app_home))
        self.assertIn("declined:herdr-fold.app", self.recorded())
        self.assertEqual(self.parts(), ["tui"])

    def test_both_set_up_both(self):
        self.with_app()
        self.with_parts("both")
        self.assertTrue(os.path.isfile(self.path(".config/ghostty/config")))
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))
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
