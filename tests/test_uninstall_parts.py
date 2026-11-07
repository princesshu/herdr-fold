"""Tests for uninstall.sh's parts: the TUI or the Herdr app taken off alone, or both, in a temporary HOME (herdr,
herdr-app and gh are stubs); what both share goes with the last part only."""
import json
import os
import unittest

from support import PartsInstall, catalog_text


class UninstallParts(PartsInstall, unittest.TestCase):
    SIDEBAR = os.path.join(".local", "state", "herdr", "plugins", "herdr-fold.sidebar")

    def setUp(self):
        super().setUp()
        self.with_app()
        with open(self.env["STUB_PLUGINS"], "w") as f:                 # what herdr has: herdr-fold's, once linked
            json.dump({"result": {"plugins": [{"plugin_id": f"herdr-fold.{name}"}
                                              for name in ("sidebar", "sessions-view", "tab-layout")]}}, f)

    def there(self, rel):
        return os.path.exists(self.path(rel))

    def herdr_calls(self):
        log = os.path.join(self.tmp, "herdr-calls")
        if not os.path.exists(log):
            return []
        with open(log) as f:
            return f.read().splitlines()

    def test_the_tui_alone_leaves_the_app_and_the_shared(self):
        self.with_parts("both")
        out = self.with_parts("tui", "uninstall.sh")
        self.assertFalse(self.there(".config/ghostty/config"))
        self.assertNotIn("herdr-fold", self.read(".zshrc") if self.there(".zshrc") else "")
        self.assertIn("herdr plugin unlink herdr-fold.sidebar", self.herdr_calls())
        self.assertTrue(self.there(".config/herdr-fold/statusline.py"))
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))
        self.assertEqual(self.parts(), ["app"])
        self.assertNotIn(catalog_text("uninstall.done"), out)
        self.assertIn(catalog_text("uninstall.part_off_tui"), out)

    def test_the_app_alone_leaves_the_tui(self):
        self.with_parts("both")
        self.with_parts("app", "uninstall.sh")
        self.assertFalse(self.in_app("mods/herdr-fold/main.js"))
        self.assertTrue(self.there(".config/ghostty/config"))
        self.assertTrue(self.there(".config/herdr-fold/statusline.py"))
        self.assertEqual([call for call in self.herdr_calls() if "unlink" in call], [])
        self.assertEqual(self.parts(), ["tui"])

    def test_both_leave_nothing_but_yours(self):
        self.with_parts("both")
        self.write(".cache/herdr-fold/pdf-pages-0123456789ab", "the PDF helper, compiled on first use")
        self.write(".local/state/herdr-fold/update.json", '{"checked": 1, "latest": "0.4.0"}')
        out = self.with_parts("both", "uninstall.sh")
        self.assertFalse(self.in_app("mods/herdr-fold/main.js"))
        for rel in (".config/ghostty/config", ".config/herdr-fold/statusline.py", ".cache/herdr-fold",
                    ".local/state/herdr-fold/installed.txt", ".local/state/herdr-fold/plugins.txt",
                    ".local/state/herdr-fold/update.json"):
            with self.subTest(rel=rel):
                self.assertFalse(self.there(rel))
        self.assertIn(catalog_text("uninstall.done"), out)

    def test_the_question_defaults_to_both(self):
        self.with_parts("both")
        out = self.asked(script="uninstall.sh")
        self.assertIn(f"{catalog_text('uninstall.parts_ask')} [3]", out)
        self.assertNotIn(catalog_text("uninstall.ready"), out)
        self.assertFalse(self.there(".config/ghostty/config"))
        self.assertFalse(self.in_app("mods/herdr-fold/main.js"))

    def test_one_part_is_asked_as_today(self):
        self.with_parts("tui")
        out = self.asked(script="uninstall.sh")
        self.assertIn(catalog_text("uninstall.ready"), out)
        self.assertNotIn(catalog_text("uninstall.parts_ask"), out)
        self.assertFalse(self.there(".config/ghostty/config"))

    def test_the_tui_off_and_on_again_finds_nothing_dropped(self):
        self.with_parts("both")
        self.with_parts("tui", "uninstall.sh")
        out = self.with_parts("tui")
        self.assertNotIn(catalog_text("install.dropped_heading"), out)
        self.assertTrue(self.in_app("mods/herdr-fold/main.js"))
        self.assertEqual(self.parts(), ["tui", "app"])

    def test_conversations_archived_in_the_app_stay(self):
        """The Conversations' state (archived ones, the index) is the TUI's and the app's alike: it goes with the last
        part only; the conversation names stay even then."""
        self.with_parts("both")
        kept = {"archived": ["claude:abc"]}
        self.write(os.path.join(self.SIDEBAR, "conversations.json"), json.dumps(kept))
        self.with_parts("tui", "uninstall.sh")
        self.assertEqual(json.loads(self.read(os.path.join(self.SIDEBAR, "conversations.json"))), kept)
        self.with_parts("app", "uninstall.sh")
        self.assertFalse(self.there(os.path.join(self.SIDEBAR, "conversations.json")))

    def test_the_linked_issues_stay_with_the_app(self):
        """The sidebar's settings hold the issue a repository's next commit fixes, which the app links too: they go
        with the last part; the sidebar's own state (the theme's colors) goes with the TUI."""
        self.with_parts("both")
        self.write(os.path.join(self.SIDEBAR, "settings.json"), json.dumps({"linked": {"harbor": [7, "Fix"]}}))
        self.write(os.path.join(self.SIDEBAR, "colors.json"), "{}")
        self.with_parts("tui", "uninstall.sh")
        self.assertTrue(self.there(os.path.join(self.SIDEBAR, "settings.json")))
        self.assertFalse(self.there(os.path.join(self.SIDEBAR, "colors.json")))

    def test_the_app_taken_off_stays_off_on_an_update(self):
        self.with_parts("both")
        self.with_parts("app", "uninstall.sh")
        out = self.asked()
        self.assertNotIn(catalog_text("install.app_ask"), out)
        self.assertEqual(self.parts(), ["tui"])

    def test_a_wrong_answer_takes_nothing_off(self):
        self.with_parts("both")
        out = self.asked({"uninstall.parts_ask": "4"}, script="uninstall.sh")
        self.assertIn(catalog_text("uninstall.parts_unknown", "4"), out)
        out = self.with_parts("all", "uninstall.sh")
        self.assertIn(catalog_text("uninstall.parts_unknown", "all"), out)
        self.assertEqual(self.parts(), ["tui", "app"])
        self.assertTrue(self.there(".config/ghostty/config"))


if __name__ == "__main__":
    unittest.main()
