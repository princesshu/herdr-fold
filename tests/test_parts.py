"""Tests for src/parts.py: which of herdr-fold's parts are installed (the TUI, the Herdr app), read from the installer's
records, so nothing records it twice; and where the Herdr app keeps its home."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, set_env

sys.path.insert(0, SRC)
import parts  # noqa: E402


class Installed(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def record(self, name, *lines):
        with open(os.path.join(self.state, name), "w") as f:
            f.write("".join(f"{line}\n" for line in lines))

    def test_nothing_installed_is_no_part(self):
        self.assertEqual(parts.installed(self.state), set())
        self.assertEqual(parts.installed(os.path.join(self.state, "gone")), set())

    def test_the_tui_is_on_the_record(self):
        self.record("installed.txt", ".config/ghostty/config", ".config/herdr-fold/statusline.py")
        self.assertEqual(parts.installed(self.state), {"tui"})

    def test_a_tui_record_missing_a_file_still_reads_as_the_tui(self):
        self.record("installed.txt", ".config/herdr-fold/plugins/sidebar/sidebar.py")
        self.assertEqual(parts.installed(self.state), {"tui"})
        os.remove(os.path.join(self.state, "installed.txt"))
        self.record("plugins.txt", "herdr-fold.sidebar")
        self.assertEqual(parts.installed(self.state), {"tui"})

    def test_the_app_is_on_the_record(self):
        self.record("plugins.txt", "herdr-fold.app")
        self.assertEqual(parts.installed(self.state), {"app"})
        self.record("plugins.txt", "declined:herdr-fold.app")
        self.assertEqual(parts.installed(self.state), set())

    def test_shared_files_alone_are_no_part(self):
        self.record("installed.txt", ".config/herdr-fold/statusline.py", ".config/herdr-fold/themes/apply.py")
        self.assertEqual(parts.installed(self.state), set())

    def test_the_command_line_prints_them_the_tui_first(self):
        self.record("installed.txt", ".config/ghostty/config")
        self.record("plugins.txt", "herdr-fold.sidebar", "herdr-fold.app")
        out = subprocess.run([sys.executable, "-B", parts.__file__, self.state], capture_output=True, text=True)
        self.assertEqual((out.returncode, out.stdout), (0, "tui\napp\n"))


class AppHome(unittest.TestCase):
    def test_the_app_home_is_herdr_app_home_or_its_own(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        set_env(self, HERDR_APP_HOME=os.path.join(home, "app"))
        self.assertEqual(parts.app_home(), os.path.join(home, "app"))
        set_env(self, HERDR_APP_HOME=None, HOME=home)
        self.assertEqual(parts.app_home(), os.path.join(home, ".config", "herdr-app"))


if __name__ == "__main__":
    unittest.main()
