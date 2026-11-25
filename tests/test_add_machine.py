"""Tests for add_machine.py (Ctrl+B, Shift+M): it runs ./machines.sh new from the package folder the installer
recorded, or says how to get the package back. Runs in a pty, as herdr's popup does.
"""
import fcntl
import os
import pty
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import unittest
from unittest import mock

from support import end_child

PACKAGE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HERDR_DIR = os.path.join(PACKAGE, "src")
sys.path.insert(0, HERDR_DIR)
import add_machine  # noqa: E402


class OpenPopup(unittest.TestCase):
    def test_asked_again_while_herdr_is_busy_with_another_popup(self):
        answers = [RuntimeError("ui_busy: a popup pane is already open"), RuntimeError("ui_busy"), {"type": "ok"}]
        with mock.patch.object(add_machine, "herdr", side_effect=answers) as asked, \
                mock.patch.object(add_machine.time, "sleep"):
            self.assertEqual(add_machine.open_popup(), {"type": "ok"})
        self.assertEqual(asked.call_count, 3)

    def test_another_refusal_is_not_asked_again(self):
        with mock.patch.object(add_machine, "herdr", side_effect=RuntimeError("no such plugin")) as asked:
            self.assertIsNone(add_machine.open_popup())
        self.assertEqual(asked.call_count, 1)

    def test_it_waits_for_the_pickers_process_first(self):
        picker = subprocess.Popen(["/bin/sleep", "0.3"])
        threading.Thread(target=picker.wait).start()                  # reaped as it ends, as herdr reaps its own
        asked = []
        with mock.patch.object(add_machine, "herdr", side_effect=lambda *_: asked.append(picker.poll()) or {}):
            add_machine.open_popup(after=picker.pid)
        self.assertEqual(asked, [0])                                  # asked once it had ended


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
        out, end = b"", time.monotonic() + 15
        while time.monotonic() < end:
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
        return out.decode("utf-8", "replace").replace("\r", ""), end_child(pid, fd)

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

    def asking(self, keys_after):
        """add_machine.py over a stand-in machines.sh that asks a question; KEYS_AFTER(fd) once it is asked.
        (what the window showed, its exit status)"""
        with open(os.path.join(self.package, "machines.sh"), "w") as f:
            f.write('#!/bin/bash\nprintf "user [root]: "\nread -r who\necho "got $who"\n')
        self.record(self.package)
        pid, fd = pty.fork()
        if pid == 0:
            os.execve("/usr/bin/python3", ["python3", os.path.join(self.herdr, "add_machine.py")],
                      {"HOME": self.home, "PATH": "/usr/bin:/bin", "TERM": "xterm-256color"})
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))     # herdr's popup has its size
        out, end, sent = b"", time.monotonic() + 15, False
        while time.monotonic() < end:
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            if not sent and b"user [root]:" in out:
                sent = True
                keys_after(fd)
        return out.decode("utf-8", "replace"), end_child(pid, fd)

    def test_what_is_typed_reaches_its_questions(self):
        out, code = self.asking(lambda fd: os.write(fd, b"admin\r"))
        self.assertIn("got admin", out)
        self.assertEqual(code, 0)

    def test_esc_ends_it_at_any_question_as_settings_closes(self):
        out, code = self.asking(lambda fd: os.write(fd, b"\x1b"))
        self.assertNotIn("got", out)
        self.assertEqual(code, 130)

    def test_its_close_button_ends_it_too(self):
        # a click on the button's cells on the first row (tui.CloseButton's span), as the mouse sends it
        out, code = self.asking(lambda fd: os.write(fd, b"\x1b[<0;79;1M\x1b[<0;79;1m"))
        self.assertNotIn("got", out)
        self.assertEqual(code, 130)

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
