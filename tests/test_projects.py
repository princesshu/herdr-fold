"""Tests for projects.py: the folder picker starts, unasked, at the folder holding the most git repositories under a
temporary home, found a few levels down (the search itself: test_core_repos.py).
"""
import os
import shutil
import tempfile
import unittest

from support import set_env

import projects
from repos import repositories


class Projects(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def repo(self, rel, changed=None):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.join(path, ".git"))
        if changed:
            os.utime(os.path.join(path, ".git"), (changed, changed))
        return path

    def found(self):
        return sorted(repositories([self.home], projects.DEPTH, projects.BUDGET))

    def test_the_folder_holding_the_most_repositories_is_the_start(self):
        self.repo("srv/crm/api")
        self.repo("srv/crm/web")
        self.repo("code/tool")
        self.assertEqual(projects.start(self.found()), os.path.join(self.home, "srv", "crm"))

    def test_a_tie_goes_to_the_folder_nearer_the_root(self):
        self.repo("work/old/one")
        self.repo("code/two")
        self.assertEqual(projects.start(self.found()), os.path.join(self.home, "code"))

    def test_without_repositories_documents_or_else_home(self):
        self.assertEqual(projects.start([]), self.home)
        os.makedirs(os.path.join(self.home, "Documents"))
        self.assertEqual(projects.start([]), os.path.join(self.home, "Documents"))

    def test_only_a_few_levels_deep(self):
        near = self.repo("a/b/c/near")
        self.repo("a/b/c/d/far")
        self.assertEqual(self.found(), [near])

    def test_linux_searches_the_server_folders_too(self):
        self.assertEqual(projects.roots("linux"), [self.home, "/srv", "/opt", "/var/www"])
        self.assertEqual(projects.roots("darwin"), [self.home])


if __name__ == "__main__":
    unittest.main()
