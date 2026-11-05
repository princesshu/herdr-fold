"""Tests for lab/lab.py, herdr-fold's test lab, with a stand-in container program: a start that fails still takes its
machine down, SSH reads only the lab's own settings (never ~/.ssh), and drop removes only a folder the lab made."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, logged, set_env, stubs

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

    def test_a_start_that_fails_still_takes_its_machine_down(self):
        machine = lab.Lab(self.home, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()                                          # nothing answers SSH at its port
        self.assertIn(f"container stop {lab.NAME}", logged(self.log))
        self.assertIn(f"container rm {lab.NAME}", logged(self.log))

    def test_ssh_reads_only_the_labs_own_settings(self):
        machine = lab.Lab(self.home, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()
        ssh = os.path.join(self.home, "bin", "ssh")
        out = subprocess.run([ssh, "-G", "lab"], capture_output=True, text=True)                 # ssh -G: no connection
        resolved = out.stdout
        self.assertIn("hostname 127.0.0.1", resolved, out.stderr)
        self.assertIn("user dev", resolved)
        theirs = os.path.join(self.tmp, "theirs.config")                    # a caller's own, as herdr gives one
        with open(theirs, "w") as f:
            f.write("Host *\n  ServerAliveInterval 42\n")
        out = subprocess.run([ssh, "-F", theirs, "-G", "lab"], capture_output=True, text=True)
        resolved = out.stdout
        self.assertIn("hostname 127.0.0.1", resolved, out.stderr)
        self.assertIn("serveraliveinterval 42", resolved)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "bin", "scp")))
        with open(os.path.join(self.home, "ssh_config")) as f:
            config = f.read()
        self.assertIn("IdentitiesOnly yes", config)
        self.assertIn(f'UserKnownHostsFile "{os.path.join(self.home, "known_hosts")}"', config)
        self.assertNotIn("~/.ssh", config)

    def test_a_machine_that_answers_already_is_tested_as_it_is(self):
        machine = lab.Lab(self.home, wait=0.5)
        with mock.patch.object(lab.Lab, "answers", return_value=True), \
                mock.patch.object(lab.unittest.defaultTestLoader, "discover", return_value=unittest.TestSuite()):
            self.assertTrue(machine.test())
        self.assertFalse(os.path.exists(self.log))                    # the container program never asked

    def test_connect_points_ssh_at_the_port_and_host_key_given(self):
        machine = lab.Lab(self.home, wait=0.5)
        machine.folder()
        with self.assertRaises(lab.LabError):
            machine.connect(2222, "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample lab\n")      # nothing answers there
        with open(os.path.join(self.home, "known_hosts")) as f:
            self.assertEqual(f.read(), "[127.0.0.1]:2222 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample\n")
        resolved = subprocess.run([os.path.join(self.home, "bin", "ssh"), "-G", "lab"], capture_output=True,
                                  text=True).stdout
        self.assertIn("port 2222", resolved)

    def test_the_mac_runners_machine_is_made_only_on_githubs_own_runners(self):
        stubs(os.path.join(self.tmp, "bin"), {"sudo": '#!/bin/sh\necho "sudo $*" >> "$LAB_LOG"\n'})
        env = {key: value for key, value in os.environ.items() if key != "RUNNER_ENVIRONMENT"}
        out = subprocess.run([sys.executable, os.path.join(PACKAGE, "lab", "ci", "mac_machine.py")],
                             env=dict(env, HOME=self.tmp), capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("GitHub", out.stderr)
        self.assertFalse(os.path.exists(self.log))                    # no sudo, no user, no server
        self.assertFalse(os.path.exists(os.path.join(self.tmp, ".local", "share", "herdr-fold-lab")))

    def test_a_machines_side_runs_only_on_githubs_own_runners(self):
        env = {key: value for key, value in os.environ.items() if key != "RUNNER_ENVIRONMENT"}
        out = subprocess.run([sys.executable, os.path.join(PACKAGE, "lab", "ci", "machine_side.py")],
                             env=dict(env, HOME=self.tmp, USERPROFILE=self.tmp), capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("GitHub", out.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, ".herdr-fold")))         # nothing prepared

    def test_ssh_writes_nothing_for_a_callers_own_settings_and_never_reads_ssh_folders(self):
        # herdr gives its own -F and may end ssh at any moment: nothing is left behind; an -F of the remote command
        # is no setting, so the lab's own file still stands in for ~/.ssh
        machine = lab.Lab(self.home, wait=0.5)
        with self.assertRaises(lab.LabError):
            machine.up()
        ssh, theirs = os.path.join(self.home, "bin", "ssh"), os.path.join(self.tmp, "theirs.config")
        with open(theirs, "w") as f:
            f.write("Host *\n  ServerAliveInterval 42\n")
        before = sorted(os.listdir(self.home))
        resolved = subprocess.run([ssh, "-F", theirs, "-G", "lab"], capture_output=True, text=True).stdout
        self.assertIn("serveraliveinterval 42", resolved)
        self.assertIn("port", resolved)
        self.assertEqual(sorted(os.listdir(self.home)), before)
        resolved = subprocess.run([ssh, "-G", "lab", "grep", "-F", theirs], capture_output=True, text=True).stdout
        self.assertNotIn("serveraliveinterval 42", resolved)
        self.assertIn("hostname 127.0.0.1", resolved)

    def test_status_counts_the_room_its_files_take_not_their_size(self):
        # the container tool's disk is a sparse file: its size says hundreds of GiB, the room it takes far less
        machine = lab.Lab(self.home)
        machine.folder()
        with open(os.path.join(self.home, "disk"), "wb") as f:
            f.truncate(4 * 2 ** 30)
        self.assertTrue(machine.status()["folder"].endswith("(0 MiB)"), machine.status()["folder"])

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
