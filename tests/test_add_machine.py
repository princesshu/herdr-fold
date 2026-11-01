"""Tests for add_machine.py (Ctrl+B, Shift+M): it runs ./machines.sh new from the package folder the installer
recorded, or says how to get the package back. Runs in a pty, as herdr's popup does.
"""
import os
import pty
import select
import shutil
import tempfile
import time
import unittest

PACKAGE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HERDR_DIR = os.path.join(PACKAGE, "src")


class AddMachine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.herdr = os.path.join(self.home, ".config", "herdr-fold")
        shutil.copytree(HERDR_DIR, self.herdr, ignore=shutil.ignore_patterns("__pycache__"))
        self.package = os.path.join(self.tmp, "herdr-fold")
        os.makedirs(self.package)
        with open(os.path.join(self.package, "machines.sh"), "w") as f:     # a stand-in that shows how it was run
            f.write('#!/bin/bash\necho "ARGS=$*"\necho "PATH=$PATH"\n')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def record(self, folder):
        with open(os.path.join(self.herdr, "setup-folder"), "w") as f:
            f.write(folder + "\n")

    def run_popup(self):
        """add_machine.py in a terminal, with herdr's bare-bones PATH; a key press once it waits for one."""
        pid, fd = pty.fork()
        if pid == 0:
            os.execve("/usr/bin/python3", ["python3", os.path.join(self.herdr, "add_machine.py")],
                      {"HOME": self.home, "PATH": "/usr/bin:/bin", "TERM": "dumb",
                       "HERDR_BIN_PATH": "/somewhere/bin/herdr"})
        out, end = b"", time.time() + 15
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            elif b"Press any key" in out:
                os.write(fd, b" ")
        _, status = os.waitpid(pid, 0)
        return out.decode("utf-8", "replace").replace("\r", ""), os.waitstatus_to_exitcode(status)

    def test_runs_the_packages_new_machine_flow(self):
        self.record(self.package)
        out, code = self.run_popup()
        self.assertIn("ARGS=new", out)
        self.assertEqual(code, 0)

    def test_finds_herdr_and_the_homebrew_tools(self):
        # herdr runs the popup with a bare-bones PATH; machines.sh calls herdr, ssh, python3 by name
        self.record(self.package)
        path = next(line for line in self.run_popup()[0].splitlines() if line.startswith("PATH="))
        self.assertIn("/somewhere/bin", path)
        self.assertIn("/opt/homebrew/bin", path)

    def test_without_the_package_it_says_how_to_get_it_back(self):
        self.record(os.path.join(self.tmp, "deleted"))
        out, code = self.run_popup()
        self.assertIn("herdr-fold folder", out)
        self.assertIn("./install.sh", out)
        self.assertNotEqual(code, 0)

    def test_without_a_record_too(self):
        out, code = self.run_popup()
        self.assertIn("./install.sh", out)
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
