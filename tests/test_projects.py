"""Tests for projects.py: the folder picker starts, unasked, at the folder holding the most git repositories under a
temporary home.
"""
import os
import shutil
import tempfile
import unittest

from support import set_attrs, set_env

import projects


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

    def found(self, **kwargs):
        return sorted(projects.repositories([self.home], **kwargs))

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

    def test_hidden_bulky_and_guarded_folders_are_not_searched(self):
        # macOS asks for Desktop and Downloads with a question of its own: searching there would raise it
        for rel in (".cache/a", "node_modules/b", "Library/c", "Desktop/d", "Downloads/e"):
            self.repo(rel)
        self.assertEqual(self.found(), [])

    def test_never_inside_a_repository_but_inside_a_home_kept_in_git(self):
        os.makedirs(os.path.join(self.home, ".git"))                      # dotfiles in git: still searched below
        app = self.repo("code/app")
        self.repo("code/app/plugins/inner")
        self.assertEqual(self.found(), [app])

    def test_only_a_few_levels_deep(self):
        near = self.repo("a/b/c/near")
        self.repo("a/b/c/d/far")
        self.assertEqual(self.found(), [near])

    def test_a_repository_someone_else_owns_is_left_out(self):
        # on a shared server another user could put repositories under /srv to steer the picker to code of theirs: only
        # the user's own and root's count (these are the test's own, so a different user id makes them someone else's)
        self.repo("code/app")
        set_attrs(self, projects.os, getuid=lambda: os.stat(self.home).st_uid + 1)
        self.assertEqual(self.found(), [])

    def test_the_search_stops_when_its_time_is_up(self):
        self.repo("code/app")
        self.assertEqual(self.found(budget=0), [])

    def test_linux_searches_the_server_folders_too(self):
        self.assertEqual(projects.roots("linux"), [self.home, "/srv", "/opt", "/var/www"])
        self.assertEqual(projects.roots("darwin"), [self.home])


if __name__ == "__main__":
    unittest.main()
