"""The lab's machine itself: it answers over SSH with what a remote machine of herdr-fold's needs. Run by
python3 lab/lab.py test, on the lab's machine (a container, or a runner's own: lab/ci)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LAB)
import lab  # noqa: E402


class Machine(unittest.TestCase):
    def test_it_answers_over_ssh_with_python_git_and_the_stand_in_claude(self):
        # the stand-in where Claude Code's installer puts it, or on the PATH (the container's /usr/local/bin)
        out = lab.Lab().ssh('PATH="$HOME/.local/bin:$PATH"; python3 --version && git --version && claude -p x '
                            "</dev/null")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Python 3", out.stdout)
        self.assertIn("feat: change the lab files", out.stdout)

    def test_a_key_is_read_end_to_end_through_it(self):
        # ./machines.sh through reads a machine's key through the machine in front of it before trusting it: here the
        # one behind is the lab machine's own SSH server, at the address and port SSH names on the machine itself
        machine = lab.Lab()
        where = machine.ssh("echo $SSH_CONNECTION").stdout.split()
        self.assertEqual(len(where), 4, where)
        with open(os.path.join(machine.home, "known_hosts")) as f:
            own = " ".join(f.read().split()[1:3])
        home = tempfile.mkdtemp(prefix="through-", dir=machine.home)
        self.addCleanup(shutil.rmtree, home)
        done = subprocess.run(["bash", "-c", '. ./machines.sh; through_key behind lab dev "$1" "$2"', "machines.sh",
                               where[2], where[3]], cwd=os.path.dirname(LAB), capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=120,
                              env={"HOME": home, "PATH": f"{machine.bin}:/usr/bin:/bin"})
        self.assertEqual(done.stdout.strip(), own, done.stderr)


if __name__ == "__main__":
    unittest.main()
