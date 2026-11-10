"""The sidebar's speed on 20 000 files plus an ignored node_modules of 50 000: the first frame within 300 ms, three idle
seconds under 30 ms of processor time, the first 2000 search hits within 2 seconds."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from support import SRC, AppScreen, FakeTerminal, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import preview  # noqa: E402
import sidebar  # noqa: E402
from search import Query  # noqa: E402
from vt import Key  # noqa: E402


class Recording(FakeTerminal):
    """The stand-in terminal, noting when the first frame was written."""

    def __init__(self):
        super().__init__(45, 40)
        self.first = None

    def write(self, data):
        if self.first is None and data:
            self.first = time.perf_counter()


class Big(AppScreen, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.root = os.path.join(cls.tmp, "big")
        for folder in range(200):
            path = os.path.join(cls.root, f"pkg{folder:03d}")
            os.makedirs(path)
            for n in range(100):
                with open(os.path.join(path, f"mod{n:03d}.py"), "w") as f:
                    f.write(f"def needle_{n}():\n    return {folder}\n")
        for folder in range(500):
            path = os.path.join(cls.root, "node_modules", f"dep{folder:03d}")
            os.makedirs(path)
            for n in range(100):
                with open(os.path.join(path, f"index{n}.js"), "w"):
                    pass
        with open(os.path.join(cls.root, ".gitignore"), "w") as f:
            f.write("node_modules/\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                   GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        # gc.auto 0: 20,000 new objects would start git's own clean-up in the background, which takes the CPU while
        # the first frame is timed and deletes its gc.pid while the folder is being removed
        for args in (["init", "-q", "-b", "main"], ["config", "gc.auto", "0"], ["add", "-A"],
                     ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", "-C", cls.root, *args], check=True, env=env)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, HERDR_WORKSPACE_ID=None, HOME=os.path.join(self.state, "home"))

    def start(self):
        term = Recording()
        started = time.perf_counter()
        self.run_app(sidebar.App(self.root, term, preview.Herdr("/usr/bin/false"), self.state), term)
        return started

    def wait(self, condition, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not condition():
            time.sleep(0.01)
        return condition()

    def test_the_first_frame_within_300_ms(self):
        started = self.start()
        self.assertTrue(self.wait(lambda: self.term.first is not None, 2))
        self.assertLess(self.term.first - started, 0.3)

    def test_three_idle_seconds_cost_under_30_ms(self):
        self.start()
        self.assertTrue(self.wait(lambda: self.app.status is not None and not self.app.running, 10))
        time.sleep(0.5)
        before = time.process_time()
        time.sleep(3)
        self.assertLess(time.process_time() - before, 0.03)

    def test_the_first_2000_hits_within_2_seconds(self):
        self.start()
        self.assertTrue(self.wait(lambda: self.app.status is not None, 10))
        find = self.app.views["search"]
        started = time.monotonic()
        self.term.type(Key("char", "2"), *[Key("char", ch) for ch in "needle_"], Key("enter"))
        self.assertTrue(self.wait(lambda: find.result is not None and find.query() == Query("needle_"), 2))
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual((len(find.result.hits), find.result.total), (2000, 20000))


if __name__ == "__main__":
    unittest.main()
