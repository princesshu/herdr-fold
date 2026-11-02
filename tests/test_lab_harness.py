"""Tests for lab/lab.py, herdr-fold's test lab, with a stand-in container program: a start that fails still takes its
machine down, SSH reads only the lab's own settings (never ~/.ssh), and drop removes only a folder the lab made."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import PACKAGE, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "lab"))
import lab  # noqa: E402

# the container program: logs its calls; its services run; no image, no machine
FAKE_CONTAINER = """#!/bin/sh
echo "container $*" >> "$LAB_LOG"
case "$1 $2" in
  "image list") echo '[]' ;;
  "list --all") echo '[]' ;;
esac
exit 0
"""


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.log = os.path.join(self.tmp, "calls")
        fakes = stubs(os.path.join(self.tmp, "bin"), {"container": FAKE_CONTAINER})
        set_env(self, PATH=f"{fakes}:/usr/bin:/bin", LAB_LOG=self.log)
        self.home = os.path.join(self.tmp, "lab home")

    def calls(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def test_a_start_that_fails_still_takes_its_machine_down(self):
        machine = lab.Lab(self.home, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()                                          # nothing answers SSH at its port
        self.assertIn(f"container stop {lab.NAME}", self.calls())
        self.assertIn(f"container rm {lab.NAME}", self.calls())

    def test_ssh_reads_only_the_labs_own_settings(self):
        machine = lab.Lab(self.home, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()
        ssh = os.path.join(self.home, "bin", "ssh")
        resolved = subprocess.run([ssh, "-G", "lab"], capture_output=True, text=True).stdout     # ssh -G: no connection
        self.assertIn("hostname 127.0.0.1", resolved)
        self.assertIn("user dev", resolved)
        theirs = os.path.join(self.tmp, "theirs.config")                    # a caller's own, as herdr gives one
        with open(theirs, "w") as f:
            f.write("Host *\n  ServerAliveInterval 42\n")
        resolved = subprocess.run([ssh, "-F", theirs, "-G", "lab"], capture_output=True, text=True).stdout
        self.assertIn("hostname 127.0.0.1", resolved)
        self.assertIn("serveraliveinterval 42", resolved)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "bin", "scp")))
        with open(os.path.join(self.home, "ssh_config")) as f:
            config = f.read()
        self.assertIn("IdentitiesOnly yes", config)
        self.assertIn(f'UserKnownHostsFile "{os.path.join(self.home, "known_hosts")}"', config)
        self.assertNotIn("~/.ssh", config)

    def test_drop_removes_only_a_folder_the_lab_made(self):
        os.makedirs(self.home)
        with open(os.path.join(self.home, "mine.txt"), "w") as f:
            f.write("not the lab's\n")
        with self.assertRaises(lab.LabError):
            lab.Lab(self.home).drop()
        self.assertTrue(os.path.exists(os.path.join(self.home, "mine.txt")))
        made = os.path.join(self.tmp, "made")
        machine = lab.Lab(made, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()
        machine.drop()
        self.assertFalse(os.path.exists(made))


if __name__ == "__main__":
    unittest.main()
