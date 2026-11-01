"""Tests for tools/sync.sh, which copies this machine's settings into a copy of the package: a missing one is a [!]
line, an uncommitted package edit is left alone, the copied files are named, and the privacy check runs on them."""
import os
import shutil
import subprocess
import tempfile
import unittest

from support import PACKAGE, catalog_text, copy_package


class Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pkg = copy_package(os.path.join(self.tmp, "pkg"))
        shutil.copytree(os.path.join(PACKAGE, "tests"), os.path.join(self.pkg, "tests"),
                        ignore=shutil.ignore_patterns("__pycache__"))                 # the privacy check is there
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.home, ".config", "herdr-fold"))
        with open(os.path.join(self.home, ".config", "herdr-fold", "tui.py"), "w") as f:
            f.write("# changed on this machine\n")

    def sync(self):
        return subprocess.run(["bash", os.path.join(self.pkg, "tools", "sync.sh")], capture_output=True, text=True,
                              env={"HOME": self.home, "PATH": "/usr/bin:/bin", "TERM": "dumb"}, timeout=120).stdout

    def test_a_package_file_edited_and_not_committed_stays(self):
        env = {"HOME": self.home, "PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "dev",
               "GIT_AUTHOR_EMAIL": "dev@example.com", "GIT_COMMITTER_NAME": "dev",
               "GIT_COMMITTER_EMAIL": "dev@example.com"}
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "start"]):
            subprocess.run(["git", "-C", self.pkg, *args], env=env, check=True, capture_output=True)
        with open(os.path.join(self.pkg, "src", "tui.py"), "a") as f:
            f.write("# being written in the package\n")
        with open(os.path.join(self.pkg, "src", "tui.py")) as f:
            edited = f.read()
        out = self.sync()
        with open(os.path.join(self.pkg, "src", "tui.py")) as f:
            self.assertEqual(f.read(), edited)
        self.assertIn("  [!] " + catalog_text("sync.edited", "src/tui.py"), out)

    def test_without_the_check_it_says_so(self):
        shutil.rmtree(os.path.join(self.pkg, "tests"))
        self.assertIn("  [!] " + catalog_text("sync.private_unchecked"), self.sync())

    def test_what_it_brought_is_checked_for_private_data(self):
        with open(os.path.join(self.home, ".config", "herdr-fold", "tui.py"), "w") as f:
            f.write("# my address: " + ".".join(("192", "168", "1", "23")) + "\n")   # whole only on this machine
        out = self.sync()
        self.assertIn("  [!] " + catalog_text("sync.private_found"), out)
        self.assertIn("src/tui.py:1", out)
        with open(os.path.join(self.home, ".config", "herdr-fold", "tui.py"), "w") as f:
            f.write("# changed on this machine\n")
        self.assertIn("  [✓] " + catalog_text("sync.private_clean"), self.sync())

    def test_a_setting_of_this_machine_goes_back_into_the_package(self):
        self.sync()
        with open(os.path.join(self.pkg, "src", "tui.py")) as f:
            self.assertEqual(f.read(), "# changed on this machine\n")

    def test_settings_merged_into_your_own_stay_out_of_the_package(self):
        # herdr settings of your own with herdr-fold's added between marks (the installer's "add" mode): yours would
        # go public
        theirs = ("# mine\n[keys]\nnext_agent = [\"ctrl+n\"]\n"
                  "# >>> herdr-fold >>>\n# herdr-fold's\n# <<< herdr-fold <<<\n")
        os.makedirs(os.path.join(self.home, ".config", "herdr"))
        with open(os.path.join(self.home, ".config", "herdr", "config.toml"), "w") as f:
            f.write(theirs)
        with open(os.path.join(self.pkg, "config", "herdr", "config.toml")) as f:
            package = f.read()
        out = self.sync()
        with open(os.path.join(self.pkg, "config", "herdr", "config.toml")) as f:
            self.assertEqual(f.read(), package)
        self.assertIn("  [!] " + catalog_text("sync.merged", ".config/herdr/config.toml"), out)

    def test_one_missing_here_is_said(self):
        out = self.sync()
        self.assertIn("  [!] " + catalog_text("sync.not_here", ".config/herdr-fold/herdrlib.py"), out)


if __name__ == "__main__":
    unittest.main()
