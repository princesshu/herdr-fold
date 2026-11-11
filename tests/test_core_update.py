"""Tests for core/update.py: the installed version, and the newest release asked of GitHub at most once a day, never
with the check switched off; nothing here reaches the network (the asking is handed in)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import PACKAGE, at_once, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import update  # noqa: E402

DAY = 86400


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HOME=self.tmp, HERDR_FOLD_NO_UPDATE_CHECK=None)
        self.state = os.path.join(self.tmp, ".local", "state", "herdr-fold")
        os.makedirs(self.state)
        self.installed("0.3.0")
        self.asked = []

    def test_two_changes_at_once_are_both_kept(self):
        # one sidebar says a version was told while another, or the app, switches the check off
        at_once(update.statefile, lambda: update.keep(told="0.4.0"), lambda: update.keep(on=False))
        self.assertEqual({key: update.kept().get(key) for key in ("told", "on")}, {"told": "0.4.0", "on": False})

    def installed(self, version):
        with open(os.path.join(self.state, "version"), "w") as f:
            f.write(f"{version}\n")

    def ask(self, answer="0.4.0"):
        def asking():
            self.asked.append(1)
            return answer
        return asking

    def test_a_newer_release_is_found_and_asked_for_once_a_day(self):
        found = update.check(now=1000 * DAY, ask=self.ask())
        self.assertEqual((found["version"], found["latest"], found["newer"], found["on"]),
                         ("0.3.0", "0.4.0", True, True))
        update.check(now=1000 * DAY + DAY - 1, ask=self.ask())
        self.assertEqual(len(self.asked), 1)
        update.check(now=1001 * DAY, ask=self.ask())
        self.assertEqual(len(self.asked), 2)

    def test_the_same_or_an_older_one_is_not_newer(self):
        for latest, newer in (("0.3.0", False), ("0.2.9", False), ("0.10.0", True), ("1.0", True), ("x", False)):
            with self.subTest(latest=latest):
                self.assertEqual(update.newer(latest, "0.3.0"), newer)

    def test_switched_off_nothing_is_asked(self):
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK="1")
        found = update.check(now=1000 * DAY, ask=self.ask())
        self.assertEqual((found["on"], found["latest"], found["newer"], self.asked), (False, None, False, []))
        set_env(self, HERDR_FOLD_NO_UPDATE_CHECK=None)
        update.switch(False)                                               # the menus' Check for Updates
        self.assertEqual((update.check(now=1000 * DAY, ask=self.ask())["on"], self.asked), (False, []))
        update.switch(True)
        self.assertTrue(update.check(now=1000 * DAY, ask=self.ask())["newer"])

    def test_without_an_install_here_nothing_is_asked(self):
        """A machine the installer never ran on (a remote one's sidebar) has no version to compare."""
        os.remove(os.path.join(self.state, "version"))
        found = update.check(now=1000 * DAY, ask=self.ask())
        self.assertEqual((found["version"], found["newer"], self.asked), (None, False, []))

    def test_a_failed_ask_keeps_what_was_known_and_waits_a_day(self):
        update.check(now=1000 * DAY, ask=self.ask())
        found = update.check(now=1001 * DAY, ask=self.ask(None))
        self.assertEqual(found["latest"], "0.4.0")
        update.check(now=1001 * DAY + 60, ask=self.ask(None))
        self.assertEqual(len(self.asked), 2)

    def test_a_version_is_told_once(self):
        """Every sidebar and the app see the same file: the first to tell about 0.4.0 tells it for all of them."""
        self.assertIsNone(update.check(now=1000 * DAY, ask=self.ask())["told"])
        update.told("0.4.0")
        self.assertEqual(update.check(now=1000 * DAY, ask=self.ask())["told"], "0.4.0")

    def test_the_state_is_its_owners_only(self):
        update.check(now=1000 * DAY, ask=self.ask())
        with open(os.path.join(self.state, "update.json")) as f:
            self.assertEqual(json.load(f)["latest"], "0.4.0")
        self.assertEqual(os.stat(os.path.join(self.state, "update.json")).st_mode & 0o077, 0)

    def test_a_tag_is_read_as_a_version(self):
        self.assertEqual(update.version_of({"tag_name": "v0.4.0"}), "0.4.0")
        self.assertIsNone(update.version_of({"tag_name": "nightly"}))
        self.assertIsNone(update.version_of(["not", "an", "answer"]))


if __name__ == "__main__":
    unittest.main()
