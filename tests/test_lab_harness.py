"""Tests for lab/lab.py, herdr-fold's test lab, with a stand-in container program: a start that fails still takes its
machine down, SSH reads only the lab's own settings (never ~/.ssh), and drop removes only a folder the lab made."""
import os
import shutil
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
        for program in ("ssh", "scp"):
            with open(os.path.join(self.home, "bin", program)) as f:
                wrapper = f.read()
            self.assertIn(f"-F '{os.path.join(self.home, 'ssh_config')}'", wrapper, program)
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
