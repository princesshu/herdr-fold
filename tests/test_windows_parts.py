"""Tests for the Windows parts that run on the Mac: the sidebar launcher by the machine's OS, and the Codex status
line setup (statusline_setup.py --apply) without termios, which Windows lacks."""
import os
import subprocess
import sys
import tempfile
import unittest

HERDR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, HERDR_DIR)
import herdrlib  # noqa: E402


class SidebarCommand(unittest.TestCase):
    def test_windows_folder_gets_the_powershell_launcher(self):
        self.assertIn("sidebar.ps1", herdrlib.sidebar_command("C:\\Users\\dev\\project"))
        self.assertIn("powershell", herdrlib.sidebar_command("D:/projects"))

    def test_unix_folder_gets_the_bash_launcher(self):
        self.assertEqual(herdrlib.sidebar_command("/home/dev/project"), "bash ~/.config/herdr-fold/sidebar.sh")
        self.assertEqual(herdrlib.sidebar_command(None), "bash ~/.config/herdr-fold/sidebar.sh")


class StatuslineSetupWithoutTermios(unittest.TestCase):
    def test_apply_runs_where_termios_is_missing(self):
        with tempfile.TemporaryDirectory() as home:
            blocker = os.path.join(home, "block")
            os.makedirs(blocker)
            for name in ("termios", "tty"):                # as on Windows: these modules do not exist
                with open(os.path.join(blocker, name + ".py"), "w") as f:
                    f.write("raise ImportError('not available on this system')\n")
            done = subprocess.run(["/usr/bin/python3", os.path.join(HERDR_DIR, "statusline_setup.py"), "--apply"],
                                  env={"HOME": home, "PYTHONPATH": blocker, "PATH": "/usr/bin:/bin"},
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(os.path.exists(os.path.join(home, ".config", "herdr-fold", "statusline.json")))


if __name__ == "__main__":
    unittest.main()
