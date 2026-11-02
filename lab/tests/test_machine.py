"""The lab's machine itself: it answers over SSH with what a remote machine of herdr-fold's needs. Run by
python3 lab/lab.py test, on a machine brought up for it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lab  # noqa: E402


class Machine(unittest.TestCase):
    def test_it_answers_over_ssh_with_python_git_and_the_stand_in_claude(self):
        out = lab.Lab().ssh("python3 --version && git --version && claude -p x </dev/null")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Python 3", out.stdout)
        self.assertIn("feat: change the lab files", out.stdout)


if __name__ == "__main__":
    unittest.main()
