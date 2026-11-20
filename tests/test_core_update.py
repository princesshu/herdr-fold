"""Tests for core/update.py: the installed version, and the newest release asked of GitHub at most once a day, never
with the check switched off, and at once by hand; nothing here reaches the network (the asking is handed in)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

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
        at_once(update.statefile, lambda: update.keep(seen="0.4.0"), lambda: update.keep(on=False))
        self.assertEqual({key: update.kept().get(key) for key in ("seen", "on")}, {"seen": "0.4.0", "on": False})

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
        self.assertEqual((found["version"], found["latest"], found["newer"], found["on"], found["checked"]),
                         ("0.3.0", "0.4.0", True, True, 1000 * DAY))
        self.assertTrue(found["releases"].endswith("/releases/tag/v0.4.0"))           # the newer one's notes
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
        update.switch(False)                                               # About's Check for updates automatically
        self.assertEqual((update.check(now=1000 * DAY, ask=self.ask())["on"], self.asked), (False, []))
        update.switch(True)
        self.assertTrue(update.check(now=1000 * DAY, ask=self.ask())["newer"])

    def test_switched_off_the_look_is_forgotten_and_on_again_it_asks_at_once(self):
        """Off, About says Checked by hand only, not an automatic look's answer; on again, it looks without waiting."""
        update.check(now=1000 * DAY, ask=self.ask())
        update.switch(False)
        found = update.check(now=1000 * DAY + 60, ask=self.ask())
        self.assertEqual((found["latest"], found["newer"], found["checked"]), (None, False, None))
        update.switch(True)
        self.assertTrue(update.check(now=1000 * DAY + 120, ask=self.ask())["newer"])
        self.assertEqual(len(self.asked), 2)

    def test_without_an_install_here_nothing_is_asked(self):
        """A machine the installer never ran on (a remote one's sidebar) has no version to compare."""
        os.remove(os.path.join(self.state, "version"))
        found = update.check(now=1000 * DAY, ask=self.ask())
        self.assertEqual((found["version"], found["newer"], self.asked), (None, False, []))

    def test_check_now_asks_github_inside_the_day(self):
        update.check(now=1000 * DAY, ask=self.ask("0.3.0"))
        found = update.check(now=1000 * DAY + 60, ask=self.ask(), force=True)
        self.assertEqual((found["latest"], found["newer"], found["checked"], len(self.asked)),
                         ("0.4.0", True, 1000 * DAY + 60, 2))
        update.switch(False)                                          # by hand it asks while switched off too
        found = update.check(now=1000 * DAY + 120, ask=self.ask("0.5.0"), force=True)
        self.assertEqual((found["on"], found["latest"], len(self.asked)), (False, "0.5.0", 3))
        os.remove(os.path.join(self.state, "version"))                # nothing to compare: nothing asked
        update.check(now=1000 * DAY + 180, ask=self.ask(), force=True)
        self.assertEqual(len(self.asked), 3)

    def test_a_failed_look_keeps_the_last_good_one_and_says_so(self):
        """GitHub not reached: About says Couldn't check, with the time of the last good look; the next look waits a
        day as after a good one, and a good one clears the failure."""
        update.check(now=1000 * DAY, ask=self.ask())
        found = update.check(now=1001 * DAY, ask=self.ask(None))
        self.assertEqual((found["latest"], found["newer"], found["checked"]), ("0.4.0", True, 1000 * DAY))
        self.assertTrue(found["error"])
        update.check(now=1001 * DAY + 60, ask=self.ask(None))
        self.assertEqual(len(self.asked), 2)
        found = update.check(now=1001 * DAY + 120, ask=self.ask(), force=True)
        self.assertEqual((found["error"], found["checked"]), (None, 1001 * DAY + 120))

    def test_an_update_is_told_once(self):
        """Updated to herdr-fold X is said once, by the first sidebar or the app to see it; a new install says nothing,
        an install from before seen was kept (its update.json there) says it."""
        self.assertIsNone(update.check(now=1000 * DAY, ask=self.ask())["updated"])
        self.installed("0.4.0")
        self.assertEqual(update.check(now=1000 * DAY, ask=self.ask())["updated"], "0.4.0")
        said = []                                      # two sidebars at once: one of them says it
        at_once(update.statefile, lambda: said.append(update.seen("0.4.0")), lambda: said.append(update.seen("0.4.0")))
        self.assertEqual(sorted(said), [False, True])
        self.assertIsNone(update.check(now=1000 * DAY, ask=self.ask())["updated"])
        update.keep(seen=None)
        self.assertEqual(update.check(now=1000 * DAY, ask=self.ask())["updated"], "0.4.0")
        os.remove(os.path.join(self.state, "version"))
        self.assertIsNone(update.check(now=1000 * DAY, ask=self.ask())["updated"])

    def test_the_changelog_section_of_a_version(self):
        """What's new: the installed CHANGELOG at the line of the version's heading, in the preview tab."""
        folder = os.path.join(self.tmp, ".config", "herdr-fold")
        os.makedirs(folder)
        with open(os.path.join(folder, "CHANGELOG.md"), "w") as f:
            f.write("# Changelog\n\n## [Unreleased]\n\n- Soon.\n\n## [0.4.0] - 2026-12-01\n\n- A box.\n\n"
                    "## [0.3.0] - 2026-11-08\n\n- A row.\n\n[0.3.0]: https://example.com/b\n")
        self.assertEqual(update.changelog(), os.path.join(folder, "CHANGELOG.md"))
        self.assertEqual((update.section("0.4.0"), update.section("v0.3.0")), (7, 11))
        self.assertIsNone(update.section("0.4"))
        os.remove(os.path.join(folder, "CHANGELOG.md"))
        self.assertIsNone(update.section("0.4.0"))

    def test_the_command_line(self):
        def run(*args):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                status = update.main(["update.py", *args])
            return status, out.getvalue()
        with mock.patch.object(update, "check", return_value={"version": "0.3.0"}) as check:
            self.assertEqual(run("check", "--now"), (0, '{"version": "0.3.0"}\n'))
            run("check")
        self.assertEqual([c.kwargs for c in check.call_args_list], [{"force": True}, {"force": False}])
        self.assertEqual(run("seen", "0.4.0"), (0, '{"seen": "0.4.0", "said": true}\n'))
        self.assertEqual(run("seen", "0.4.0"), (0, '{"seen": "0.4.0", "said": false}\n'))
        self.assertEqual(run("section", "0.4.0"), (0, json.dumps({"path": update.changelog(), "line": None}) + "\n"))
        for wrong in (("told", "0.4.0"), ("seen", "x"), ("section", "x"), ("check", "--later"), ()):
            with self.subTest(wrong=wrong):
                self.assertEqual(run(*wrong)[0], 2)

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
