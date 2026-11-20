#!/usr/bin/env python3
"""tests/ in two halves for the lab's two unit jobs, side by side on GitHub's runners: `installer` (install, uninstall,
machines_prepare: the slow ones) or `rest`; together they are tests/ whole. Usage: units.py installer|rest"""
import fnmatch
import os
import sys
import unittest

TESTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests")
INSTALLER = ("test_install*.py", "test_uninstall*.py", "test_machines_prepare*.py")


def files(half, folder=TESTS):
    """The test files of HALF ("installer" or "rest") in FOLDER, sorted."""
    every = sorted(name for name in os.listdir(folder) if fnmatch.fnmatch(name, "test_*.py"))
    slow = [name for name in every if any(fnmatch.fnmatch(name, pattern) for pattern in INSTALLER)]
    return slow if half == "installer" else [name for name in every if name not in slow]


def main(argv):
    if argv[1:] not in (["installer"], ["rest"]):
        sys.exit("usage: units.py installer|rest")
    sys.path.insert(0, TESTS)                    # as `unittest discover -s tests` imports them
    suite = unittest.defaultTestLoader.loadTestsFromNames([name[:-3] for name in files(argv[1])])
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
