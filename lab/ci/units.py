#!/usr/bin/env python3
"""tests/ in two halves for the lab's unit jobs, side by side on GitHub's runners: `installer` (install, uninstall,
machines_prepare: the slow ones) or `rest`; a half's K/N runs every Nth case from its Kth, so N runners share it.
Usage: units.py installer|rest [K/N]"""
import fnmatch
import os
import re
import sys
import unittest

TESTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tests")
INSTALLER = ("test_install*.py", "test_uninstall*.py", "test_machines_prepare*.py")


def files(half, folder=TESTS):
    """The test files of HALF ("installer" or "rest") in FOLDER, sorted."""
    every = sorted(name for name in os.listdir(folder) if fnmatch.fnmatch(name, "test_*.py"))
    slow = [name for name in every if any(fnmatch.fnmatch(name, pattern) for pattern in INSTALLER)]
    return slow if half == "installer" else [name for name in every if name not in slow]


def cases(suite):
    """Every test case in SUITE, flat, sorted by its id (the same order on every runner)."""
    found = []
    for one in suite:
        found += cases(one) if isinstance(one, unittest.TestSuite) else [one]
    return sorted(found, key=lambda case: case.id())


def share(half, shard=1, of=1):
    """HALF's cases for runner SHARD of OF: every OFth from the SHARDth; the shares are its cases whole, each once."""
    sys.path.insert(0, TESTS)                    # as `unittest discover -s tests` imports them
    every = cases(unittest.defaultTestLoader.loadTestsFromNames([name[:-3] for name in files(half)]))
    return every[shard - 1::of]


def main(argv):
    shard = re.fullmatch(r"([1-9]\d*)/([1-9]\d*)", argv[2]) if len(argv) == 3 else None
    if len(argv) not in (2, 3) or argv[1] not in ("installer", "rest") or (len(argv) == 3 and not shard) or \
            (shard and int(shard[1]) > int(shard[2])):
        sys.exit("usage: units.py installer|rest [K/N]")
    picked = share(argv[1], *(map(int, shard.groups()) if shard else ()))
    return 0 if unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(picked)).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
