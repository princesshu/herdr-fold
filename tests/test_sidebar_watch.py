"""Tests for the sidebar's change watching (watch.py): the watcher's changed folders and git changes, slowing down when
idle, and git status timing."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
from watch import Watcher  # noqa: E402


def make(root, rel):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("x\n")


class Watching(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.now = 0.0

    def clock(self):
        return self.now

    def test_a_new_file_changes_its_folder(self):
        watcher = Watcher(lambda: [self.root], None)
        self.assertEqual(watcher.poll(), set())
        make(self.root, "new.txt")
        os.utime(self.root, ns=(1, 1))                         # a different mtime, whatever the clock's resolution
        self.assertEqual(watcher.poll(), {self.root})

    def test_a_commit_changes_git(self):
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-C", self.root, "-c", "user.name=dev", "-c", "user.email=dev@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        make(self.root, "a.txt")
        watcher = Watcher(lambda: [], os.path.join(self.root, ".git"))
        watcher.poll()
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        self.assertIn("git", watcher.poll())

    def test_the_pace_slows_when_nothing_happens(self):
        watcher = Watcher(lambda: [], None, clock=self.clock)
        watcher.touch()
        self.assertEqual(watcher.interval(), 1.0)
        self.now = 31
        self.assertEqual(watcher.interval(), 3.0)
        self.now = 400
        self.assertEqual(watcher.interval(), 10.0)

    def test_git_status_is_due_on_a_change_and_on_a_slow_beat(self):
        watcher = Watcher(lambda: [], None, clock=self.clock)
        self.assertTrue(watcher.status_due(changed=False, scm_shown=False))        # never run yet
        watcher.status_done(started=0.0, finished=0.05)
        self.now = 1
        self.assertFalse(watcher.status_due(changed=False, scm_shown=True))
        self.assertTrue(watcher.status_due(changed=True, scm_shown=False))
        watcher.status_done(started=1, finished=1.05)                              # the one it asked for
        self.now = 7
        self.assertTrue(watcher.status_due(changed=False, scm_shown=True))         # the 5 s beat
        self.assertFalse(watcher.status_due(changed=False, scm_shown=False))       # 15 s when not shown
        watcher.status_done(started=7, finished=8)                                 # a slow repository: 1 s
        self.now = 30
        self.assertFalse(watcher.status_due(changed=False, scm_shown=True))        # at least 50 × 1 s apart
        self.now = 58.5
        self.assertTrue(watcher.status_due(changed=False, scm_shown=True))

    def test_a_change_seen_too_soon_waits_for_its_status_and_is_never_dropped(self):
        # git init just after a status: its change comes before the gap allows another one; it gets its status once
        # the gap allows, not on the slow beat
        watcher = Watcher(lambda: [], None, clock=self.clock)
        watcher.status_done(started=0.0, finished=0.1)                             # 0.1 s: changes 1 s apart
        self.now = 0.5
        self.assertFalse(watcher.status_due(changed=True, scm_shown=True))          # too soon
        self.now = 1.2
        self.assertTrue(watcher.status_due(changed=False, scm_shown=True))         # kept, not forgotten
        watcher.status_done(started=1.2, finished=1.3)
        self.now = 3
        self.assertFalse(watcher.status_due(changed=False, scm_shown=True))        # answered: the beat again


if __name__ == "__main__":
    unittest.main()
