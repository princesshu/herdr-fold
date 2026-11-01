"""Tests for tools/check_updates.py: a newer starship or herdr than pinned, a new major Claude Code or Codex (patch
and minor stay quiet), a failed lookup as a failure. The releases are made up; nothing goes to the network.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from support import PACKAGE

sys.path.insert(0, os.path.join(PACKAGE, "tools"))
import check_updates  # noqa: E402


def latest(**newer):
    """What the releases say: the package's own versions, but NEWER ones where given."""
    found = {"starship": check_updates.pinned_starship(), "herdr": check_updates.HERDR,
             "claude": f"{check_updates.CLAUDE_MAJOR}.1.312", "codex": f"{check_updates.CODEX_MAJOR}.166.0"}
    found.update(newer)
    return lambda name: found[name]


def run(fetch):
    out = io.StringIO()
    with redirect_stdout(out):
        status = check_updates.main(fetch)
    return status, out.getvalue()


class CheckUpdates(unittest.TestCase):
    def test_the_starship_pin_is_read_from_the_fetch_script(self):
        self.assertRegex(check_updates.pinned_starship(), r"^v\d+\.\d+\.\d+$")

    def test_nothing_newer_says_so_and_passes(self):
        status, out = run(latest())
        self.assertEqual(status, 0)
        self.assertEqual(out.count("up to date"), 4, out)

    def test_a_newer_starship_names_what_to_change(self):
        status, out = run(latest(starship="v99.0.0"))
        self.assertEqual(status, 1)
        line = next(line for line in out.splitlines() if line.startswith("starship"))
        self.assertIn("v99.0.0", line)
        self.assertIn("remote/fetch-tool.sh", line)

    def test_a_newer_herdr_asks_for_a_try(self):
        status, out = run(latest(herdr="v99.0.0"))
        self.assertEqual(status, 1)
        self.assertIn("HERDR in tools/check_updates.py", next(line for line in out.splitlines()
                                                              if line.startswith("herdr")))

    def test_claude_code_and_codex_speak_up_only_at_a_new_major_version(self):
        quiet = latest(claude=f"{check_updates.CLAUDE_MAJOR}.99.0", codex=f"{check_updates.CODEX_MAJOR}.999.0")
        self.assertEqual(run(quiet)[0], 0)
        for name, major in (("claude", check_updates.CLAUDE_MAJOR), ("codex", check_updates.CODEX_MAJOR)):
            status, out = run(latest(**{name: f"{major + 1}.0.0"}))
            self.assertEqual(status, 1, name)
            self.assertIn(f"{major + 1}.0.0", out)

    def test_a_look_that_cannot_be_made_fails_apart(self):
        def offline(name):
            raise OSError("network unreachable")
        status, out = run(offline)
        self.assertEqual(status, 2)
        self.assertIn("network unreachable", out)
        for odd in (AttributeError("'list' object has no attribute 'get'"), TypeError("not a version")):
            def answer(name, odd=odd):
                raise odd
            self.assertEqual(run(answer)[0], 2, odd)                      # an answer of another shape: no "to do"

    def test_the_token_never_follows_a_redirect(self):
        # urllib carries an ordinary header across a redirect, to another host too
        os.environ["GITHUB_TOKEN"] = "made-up"
        self.addCleanup(os.environ.pop, "GITHUB_TOKEN", None)
        seen = []

        def urlopen(request, timeout):
            seen.append(request)
            raise OSError("offline")
        with mock.patch.object(check_updates.urllib.request, "urlopen", urlopen):
            with self.assertRaises(OSError):
                check_updates.released("herdr")
        self.assertEqual(seen[0].unredirected_hdrs.get("Authorization"), "Bearer made-up")
        self.assertNotIn("Authorization", seen[0].headers)


if __name__ == "__main__":
    unittest.main()
