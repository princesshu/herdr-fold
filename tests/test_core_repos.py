"""Tests for core/repos.py, the search for git repositories under a folder that the folder picker and the sidebar share:
nearest first, never inside one, none in hidden, bulky or guarded folders, only the user's and root's, within its time.
"""
import os
import shutil
import sys
import tempfile
import unittest

from support import PACKAGE, set_attrs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import repos  # noqa: E402


class Repositories(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)

    def repo(self, rel):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.join(path, ".git"))
        return path

    def found(self, **kwargs):
        return sorted(repos.repositories([self.home], **kwargs))

    def test_hidden_bulky_and_guarded_folders_are_not_searched(self):
        # macOS asks for Desktop and Downloads with a question of its own: searching there would raise it
        for rel in (".cache/a", "node_modules/b", "Library/c", "Desktop/d", "Downloads/e"):
            self.repo(rel)
        self.assertEqual(self.found(), [])

    def test_never_inside_a_repository_but_inside_a_root_kept_in_git(self):
        os.makedirs(os.path.join(self.home, ".git"))                      # dotfiles in git: still searched below
        app = self.repo("code/app")
        self.repo("code/app/plugins/inner")
        self.assertEqual(self.found(), [app])

    def test_any_depth_unless_limited(self):
        near, far = self.repo("a/b/c/near"), self.repo("a/b/c/d/e/f/far")
        self.assertEqual(self.found(), [far, near])
        self.assertEqual(self.found(depth=4), [near])

    def test_the_nearest_come_first(self):
        far, near = self.repo("a/b/far"), self.repo("near")
        self.assertEqual(repos.repositories([self.home]), [near, far])

    def test_a_worktree_or_submodule_folder_counts_by_its_git_file(self):
        path = os.path.join(self.home, "work", "branch")
        os.makedirs(path)
        with open(os.path.join(path, ".git"), "w") as f:
            f.write("gitdir: /elsewhere\n")
        self.assertEqual(self.found(), [path])

    def test_a_repository_someone_else_owns_is_left_out(self):
        # on a shared server another user could put repositories under /srv to steer the picker to code of theirs: only
        # the user's own and root's count (these are the test's own, so a different user id makes them someone else's)
        self.repo("code/app")
        set_attrs(self, repos.os, getuid=lambda: os.stat(self.home).st_uid + 1)
        self.assertEqual(self.found(), [])

    def test_the_search_stops_when_its_time_is_up(self):
        self.repo("code/app")
        self.assertEqual(self.found(budget=0), [])


if __name__ == "__main__":
    unittest.main()
