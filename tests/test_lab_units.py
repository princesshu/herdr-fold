"""The lab's two unit jobs (lab/ci/units.py) run tests/ whole between them, each file once."""
import importlib.util
import os
import unittest

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("units", os.path.join(PACKAGE, "lab", "ci", "units.py"))
units = importlib.util.module_from_spec(spec)
spec.loader.exec_module(units)


class Halves(unittest.TestCase):
    def test_the_two_halves_are_tests_whole_each_file_once(self):
        installer, rest = units.files("installer"), units.files("rest")
        every = sorted(name for name in os.listdir(os.path.join(PACKAGE, "tests"))
                       if name.startswith("test_") and name.endswith(".py"))
        self.assertEqual(sorted(installer + rest), every)
        self.assertFalse(set(installer) & set(rest))

    def test_the_installers_own_go_together(self):
        installer = units.files("installer")
        for name in ("test_install.py", "test_uninstall.py", "test_machines_prepare.py", "test_install_app.py"):
            self.assertIn(name, installer)
        self.assertNotIn("test_sidebar.py", installer)
        self.assertNotIn("test_lab_units.py", installer)


    def test_a_halfs_shares_are_its_cases_whole_each_once(self):
        # the installer's half on three runners: every third case from the first, the second and the third
        whole = [case.id() for case in units.share("installer")]
        shares = [[case.id() for case in units.share("installer", k, 3)] for k in (1, 2, 3)]
        self.assertEqual(sorted(sum(shares, [])), sorted(whole))
        self.assertEqual(len(set(sum(shares, []))), len(whole))
        self.assertLessEqual(max(map(len, shares)) - min(map(len, shares)), 1)       # as even as the count allows


if __name__ == "__main__":
    unittest.main()
