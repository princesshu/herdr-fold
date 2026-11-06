"""Tests for herdr's own pbcopy (src/bin/pbcopy) — with a fake "system pbcopy" and a fake formatter,
without the real clipboard. Run: /usr/bin/python3 -m unittest discover -s tests
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

PACKAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SHIM = os.path.join(PACKAGE, "src", "bin", "pbcopy")


class ClipShim(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        herdr = os.path.join(self.dir, "herdr")
        os.makedirs(os.path.join(herdr, "bin"))
        shutil.copy(SHIM, os.path.join(herdr, "bin", "pbcopy"))
        os.chmod(os.path.join(herdr, "bin", "pbcopy"), 0o755)
        self.out = os.path.join(self.dir, "out")
        # fake formatter: records what it got, and is slow — pbcopy must not wait for it
        with open(os.path.join(herdr, "rich_clipboard.py"), "w") as f:
            f.write("import sys, time\ntext = sys.stdin.read()\ntime.sleep(1.5)\n"
                    f"open({os.path.join(self.dir, 'upgraded')!r}, 'w').write(text)\n")
        # fake system pbcopy: writes out the text and options it received
        system = os.path.join(self.dir, "system")
        os.makedirs(system)
        with open(os.path.join(system, "pbcopy"), "w") as f:
            f.write(f'#!/bin/sh\necho "$*" > {self.out}.args\ncat > {self.out}\n')
        os.chmod(os.path.join(system, "pbcopy"), 0o755)
        self.path = f"{os.path.join(herdr, 'bin')}:{system}:/usr/bin:/bin"
        self.tmp = os.path.join(self.dir, "tmp")
        os.makedirs(self.tmp)
        self.shim = os.path.join(herdr, "bin", "pbcopy")
        self.formatting = False

    def tearDown(self):
        # a formatter the shim left in the background starts in this folder: it ends first (its mark), then the folder
        # goes; gone before, the formatter's Python would make it again for its cache
        for _ in range(50 if self.formatting else 0):
            if os.path.exists(os.path.join(self.dir, "upgraded")):
                break
            time.sleep(0.1)
        shutil.rmtree(self.dir)

    def run_shim(self, text, *args):
        self.formatting = self.formatting or not args          # with no option it starts the formatter
        start = time.time()
        done = subprocess.run([self.shim, *args], input=text, text=True, capture_output=True, timeout=10,
                              env={"PATH": self.path, "HOME": self.dir, "TMPDIR": self.tmp})
        return done, time.time() - start

    def test_selection_reaches_the_system_pbcopy_unchanged(self):
        done, _ = self.run_shim("first line\nsecond ✓\n")
        self.assertEqual(done.returncode, 0)
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(f.read(), "first line\nsecond ✓\n")

    def test_upgrade_runs_in_the_background_with_the_selection(self):
        _, took = self.run_shim("format me")
        self.assertLess(took, 1.0)
        upgraded = os.path.join(self.dir, "upgraded")
        for _ in range(40):
            if os.path.exists(upgraded):
                break
            time.sleep(0.1)
        with open(upgraded, encoding="utf-8") as f:
            self.assertEqual(f.read(), "format me")

    def test_the_selection_is_left_nowhere_on_disk(self):
        # a copied secret would stay in the temporary folder until the formatter ends, and for good if it failed
        self.run_shim("password: hunter2")
        self.assertEqual(os.listdir(self.tmp), [])

    def test_options_are_passed_through_without_upgrade(self):
        self.run_shim("search", "-pboard", "find")
        with open(self.out + ".args") as f:
            self.assertEqual(f.read().strip(), "-pboard find")
        time.sleep(2)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "upgraded")))


    def test_a_path_entry_written_differently_does_not_make_it_call_itself(self):
        # with options the shim execs the system pbcopy at once: were it to find itself, it would loop in one process
        self.path = self.path.replace("bin:", "bin/:", 1)          # the same folder, with a trailing slash
        done, _ = self.run_shim("search", "-pboard", "find")
        self.assertEqual(done.returncode, 0)
        with open(self.out + ".args") as f:
            self.assertEqual(f.read().strip(), "-pboard find")


if __name__ == "__main__":
    unittest.main()
