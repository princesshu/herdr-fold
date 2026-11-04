"""Tests for the git layer (core/git.py: the TUI sidebar's and the Herdr app mod's) in temporary repositories: status,
staging, commits, push and pull, the graph and unusual states; a file name is never a pattern, and what runs unasked
runs no program a downloaded repository's .git/config names."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env, sign_head, stubs, trap

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import git  # noqa: E402


class Repo(unittest.TestCase):
    def setUp(self):
        self.root = self.folder()
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        self.run_git("init", "-q", "-b", "main")

    def folder(self):
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path)
        return path

    def run_git(self, *args, cwd=None, check=True):
        return subprocess.run(["git", "-C", cwd or self.root, *args], capture_output=True, text=True,
                              check=check).stdout

    def write(self, rel, text="x\n", root=None):
        path = os.path.join(root or self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def touch(self, rel):
        """REL changed in time only, as a file unpacked again: git reads it to tell whether it changed."""
        path = os.path.join(self.root, rel)
        later = os.stat(path).st_mtime + 10
        os.utime(path, (later, later))

    def commit_all(self, message="init", cwd=None):
        self.run_git("add", "-A", cwd=cwd)
        self.run_git("commit", "-q", "-m", message, cwd=cwd)


class ForeignConfig(Repo):
    def test_the_repositorys_config_cannot_make_git_read_the_sidebars_terminal(self):
        """[include] path = /dev/stdin in a downloaded folder's .git/config: git would read the sidebar's input, its
        keys, until it ends, which a terminal never does."""
        self.write("a.txt")
        self.run_git("config", "include.path", "/dev/stdin")
        code = (f"import sys; sys.path.insert(0, {os.path.join(PACKAGE, 'core')!r}); import git; "
                f"print(git.status({self.root!r}).error or 'ok')")
        proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)                   # its input kept open
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            self.fail("git waited on the input")
        finally:
            proc.stdin.close()
        self.assertEqual(proc.stdout.read().strip(), "ok")
        proc.stdout.close()

    def test_the_status_does_not_start_the_repositorys_fsmonitor(self):
        """The sidebar asks for the status unasked: a downloaded folder's .git/config must not run a program then."""
        self.write("a.txt")
        mark = trap(self.root, "core.fsmonitor", self.folder())
        git.status(self.root)
        self.assertFalse(os.path.exists(mark))

    def test_the_status_does_not_run_the_repositorys_filters(self):
        """A changed file's content passes the filter .gitattributes names: a downloaded folder's .git/config could
        make that any program, as a clean filter or a long-running one, required or not."""
        self.write(".gitattributes", "*.txt filter=evil\n")
        self.write("a.txt")
        self.commit_all()
        self.touch("a.txt")                                         # as an unpacked folder's files: read to compare
        programs = self.folder()
        marks = [trap(self.root, key, programs) for key in ("filter.evil.clean", "filter.evil.process")]
        self.run_git("config", "filter.evil.required", "true")
        st = git.status(self.root)
        self.assertIsNone(st.error)
        self.assertEqual([os.path.basename(m) for m in marks if os.path.exists(m)], [])

    def test_a_files_diff_runs_none_of_the_repositorys_filters(self):
        """The Herdr app mod shows a changed file's diff unasked: as the status, it runs no filter a downloaded
        folder's .git/config names."""
        self.write(".gitattributes", "*.txt filter=evil\n")
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        programs = self.folder()
        marks = [trap(self.root, key, programs) for key in ("filter.evil.clean", "filter.evil.process")]
        self.run_git("config", "filter.evil.required", "true")
        text, error = git.diff(self.root, "a.txt")
        self.assertEqual((error, "+changed" in text), (None, True))
        self.assertEqual([os.path.basename(m) for m in marks if os.path.exists(m)], [])

    def test_a_filter_whose_name_hides_from_the_command_line_stops_the_status(self):
        """git splits -c at the first =: a driver named with one could not be turned off there, so no status is asked
        for at all."""
        self.write(".gitattributes", "*.txt filter=evil=x\n")
        self.write("a.txt")
        self.commit_all()
        self.touch("a.txt")
        mark = trap(self.root, "filter.evil=x.clean", self.folder())
        self.assertTrue(git.status(self.root).error)
        self.assertFalse(os.path.exists(mark))

    def test_a_filter_whose_name_is_read_back_otherwise_stops_the_status(self):
        """A driver's name that does not come back from git byte for byte (no UTF-8, or a character that splits a
        line in Python) could not be named on git's command line either."""
        programs = self.folder()
        for name in (b"evil\xff", b"evil\x1cx"):
            with open(os.path.join(self.root, ".gitattributes"), "wb") as f:
                f.write(b"*.txt filter=" + name + b"\n")
            self.write("a.txt")
            self.commit_all()
            self.touch("a.txt")
            mark = os.path.join(programs, "ran")
            stubs(programs, {"filter": f"#!/bin/sh\ntouch '{mark}'\ncat\n"})
            subprocess.run([b"git", b"-C", self.root.encode(), b"config", b"filter." + name + b".clean",
                            os.path.join(programs, "filter").encode()], check=True)
            self.assertTrue(git.status(self.root).error, name)
            self.assertFalse(os.path.exists(mark), name)

    def test_the_status_runs_nothing_in_a_submodule(self):
        """A submodule's own config is as foreign as the repository's: its status is not asked for."""
        sub = self.folder()
        self.run_git("init", "-q", "-b", "main", cwd=sub)
        self.write("b.txt", root=sub)
        self.commit_all(cwd=sub)
        self.run_git("-c", "protocol.file.allow=always", "submodule", "add", "-q", sub, "sub")
        self.commit_all()
        inner = os.path.join(self.root, "sub")
        self.write(".gitattributes", "*.txt filter=evil\n", root=inner)
        self.touch("sub/b.txt")
        mark = trap(inner, "filter.evil.clean", self.folder())
        self.assertIsNone(git.status(self.root).error)
        self.assertFalse(os.path.exists(mark))

    def test_a_submodules_diff_runs_nothing_in_it(self):
        """A submodule's diff would look inside it for changes: its config is as foreign, so only its commit is told."""
        sub = self.folder()
        self.run_git("init", "-q", "-b", "main", cwd=sub)
        self.write("b.txt", root=sub)
        self.commit_all(cwd=sub)
        self.run_git("-c", "protocol.file.allow=always", "submodule", "add", "-q", sub, "sub")
        self.commit_all()
        inner = os.path.join(self.root, "sub")
        self.write(".gitattributes", "*.txt filter=evil\n", root=inner)
        self.touch("sub/b.txt")
        marks = [trap(inner, key, self.folder()) for key in ("filter.evil.clean", "core.fsmonitor")]
        self.assertIsNone(git.diff(self.root, "sub")[1])
        self.assertEqual([os.path.basename(m) for m in marks if os.path.exists(m)], [])

    def test_a_signed_commit_does_not_start_the_repositorys_signature_check(self):
        """The Graph and the linked issue's check read the log: a downloaded folder's log.showSignature must not
        start the signature program its config names."""
        self.write("a.txt")
        self.commit_all()
        sign_head(self.root)
        self.run_git("config", "log.showSignature", "true")
        mark = trap(self.root, "gpg.program", self.folder())
        git.graph(self.root)
        git.head(self.root)
        self.assertFalse(os.path.exists(mark))


class CommandLine(Repo):
    """herdr-fold's Herdr app mod runs this layer on the repository's machine: python3 git.py status|sync|push ROOT,
    answering in JSON, so it lists and syncs as the TUI sidebar does."""

    def cli(self, *args):
        out = subprocess.run([sys.executable, "-B", git.__file__, *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_the_branch_how_far_from_its_upstream_and_the_changes(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write("b.txt")
        self.run_git("add", "b.txt")
        self.assertEqual(self.cli("status", self.root), {
            "branch": "main", "upstream": None, "ahead": 0, "behind": 0, "error": None, "ignored": [],
            "staged": [{"path": "b.txt", "code": "A"}], "changes": [{"path": "a.txt", "code": "M"}]})

    def test_a_files_diff_a_new_ones_as_all_added(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write("new.txt", "fresh\n")
        changed, new = self.cli("diff", self.root, "a.txt"), self.cli("diff", self.root, "new.txt")
        self.assertEqual((changed["error"], new["error"]), (None, None))
        self.assertIn("+changed", changed["text"])
        self.assertIn("+fresh", new["text"])

    def test_a_commit_and_what_to_do_when_it_fails(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.assertEqual(self.cli("commit", self.root, "fix: change a"), {"ok": True, "advice": None})
        self.assertEqual(self.run_git("log", "-1", "--format=%s").strip(), "fix: change a")
        self.assertFalse(self.cli("commit", self.root, "fix: nothing")["ok"])

    def test_a_sync_and_what_to_do_when_it_fails(self):
        self.write("a.txt")
        self.commit_all()
        self.assertEqual(self.cli("sync", self.root), {"ok": False, "advice": git.advice("no remote")})
        remote = self.folder()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
        self.run_git("remote", "add", "origin", remote)
        self.assertEqual(self.cli("push", self.root), {"ok": True, "advice": None})
        self.assertEqual(self.cli("status", self.root)["upstream"], "origin/main")

    def test_named_files_staged_and_unstaged_the_rest_left(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write("b.txt")
        self.assertEqual(self.cli("stage", self.root, "b.txt"), {"ok": True, "advice": None})
        status = self.cli("status", self.root)
        self.assertEqual((status["staged"], status["changes"]),
                         ([{"path": "b.txt", "code": "A"}], [{"path": "a.txt", "code": "M"}]))
        self.assertEqual(self.cli("unstage", self.root, "b.txt"), {"ok": True, "advice": None})
        self.assertEqual(self.cli("status", self.root)["staged"], [])
        self.assertEqual(self.cli("stage", self.root), {"ok": True, "advice": None})     # no name: every change
        self.assertEqual(len(self.cli("status", self.root)["staged"]), 2)

    def test_a_tracked_files_change_discarded_a_new_file_never_touched(self):
        self.write("a.txt", "kept\n")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write("new.txt", "mine\n")
        self.assertEqual(self.cli("discard", self.root, "a.txt"), {"ok": True, "advice": None})
        with open(os.path.join(self.root, "a.txt")) as f:
            self.assertEqual(f.read(), "kept\n")
        self.assertFalse(self.cli("discard", self.root, "new.txt")["ok"])
        self.assertTrue(os.path.exists(os.path.join(self.root, "new.txt")))

    def test_the_graph_newest_first(self):
        self.write("a.txt")
        self.commit_all("one")
        self.write("a.txt", "2\n")
        self.commit_all("two")
        commits = self.cli("graph", self.root)["commits"]
        self.assertEqual([(c["subject"], c["author"], c["head"]) for c in commits],
                         [("two", "dev", True), ("one", "dev", False)])
        self.assertEqual(commits[0]["refs"], ["main"])
        self.assertEqual(commits[0]["hash"], self.run_git("rev-parse", "--short", "HEAD").strip())

    def test_a_commits_diff_by_its_hash_and_by_nothing_else(self):
        self.write("a.txt", "1\n")
        self.commit_all("one")
        self.write("a.txt", "2\n")
        self.commit_all("two")
        shown = self.cli("show", self.root, self.run_git("rev-parse", "--short", "HEAD").strip())
        self.assertIsNone(shown["error"])
        self.assertIn("two", shown["text"])
        self.assertIn("+2", shown["text"])
        self.assertNotIn("dev@example.com", shown["text"])               # the author by name, never by address
        written = os.path.join(self.folder(), "out")
        for rev in (f"--output={written}", "HEAD~1", "main"):        # an option or a name: never handed to git
            self.assertEqual(self.cli("show", self.root, rev), {"text": "", "error": "Not a commit"})
        self.assertFalse(os.path.exists(written))


class Status(Repo):
    def test_every_kind_of_change(self):
        for name in ("kept.txt", "gone.txt", "moved.txt"):
            self.write(name)
        self.write(".gitignore", "build/\n")
        self.commit_all()
        self.write("kept.txt", "changed\n")
        os.remove(os.path.join(self.root, "gone.txt"))
        self.run_git("mv", "moved.txt", "renamed.txt")
        self.write("new.txt")
        self.write("build/out.bin")
        st = git.status(self.root)
        self.assertEqual({(c.path, c.code) for c in st.staged}, {("renamed.txt", "R")})
        self.assertEqual({(c.path, c.code) for c in st.changes},
                         {("kept.txt", "M"), ("gone.txt", "D"), ("new.txt", "?")})
        self.assertIn("build/", st.ignored)
        self.assertEqual((st.branch, st.error), ("main", None))

    def test_an_ignored_file_is_no_change_even_tracked(self):
        """A file .gitignore names is no change, even one committed before it named it: an edit of it shows nowhere."""
        self.write("secret.cfg")
        self.commit_all()
        self.write(".gitignore", "secret.cfg\n")
        self.write("secret.cfg", "changed\n")
        self.assertEqual([c.path for c in git.status(self.root).changes], [".gitignore"])

    def test_no_commit_yet_and_a_detached_head(self):
        self.write("a.txt")
        self.assertIsNone(git.status(self.root).error)
        self.assertEqual(git.graph(self.root), [])
        self.commit_all()
        self.write("a.txt", "2\n")
        self.commit_all("two")
        self.run_git("checkout", "-q", "HEAD~1")
        self.assertIsNone(git.status(self.root).branch)

    def test_a_conflict_is_listed(self):
        self.write("a.txt", "base\n")
        self.commit_all()
        self.run_git("checkout", "-q", "-b", "other")
        self.write("a.txt", "other\n")
        self.commit_all("other")
        self.run_git("checkout", "-q", "main")
        self.write("a.txt", "main\n")
        self.commit_all("main")
        self.run_git("merge", "-q", "other", check=False)
        self.assertIn(("a.txt", "U"), {(c.path, c.code) for c in git.status(self.root).changes})

    def test_outside_a_repository(self):
        folder = self.folder()
        self.assertIsNone(git.top(folder))
        self.assertIsNone(git.git_dir(folder))
        self.assertEqual(git.git_dir(self.root), os.path.join(os.path.realpath(self.root), ".git"))
        self.assertIsNotNone(git.status(folder).error)


    def test_without_git(self):
        missing = os.path.join(self.folder(), "git")
        with mock.patch.object(git, "GIT", missing):
            self.assertEqual(git.status(self.root).error, "git is not installed")


class Actions(Repo):
    def test_stage_unstage_discard_commit(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        git.stage(self.root, ["a.txt"])
        self.assertEqual([c.path for c in git.status(self.root).staged], ["a.txt"])
        git.unstage(self.root, ["a.txt"])
        self.assertEqual(git.status(self.root).staged, [])
        self.assertIsNone(git.discard(self.root, "a.txt"))
        with open(os.path.join(self.root, "a.txt")) as f:
            self.assertEqual(f.read(), "x\n")
        self.write("b.txt")
        git.stage(self.root, ["b.txt"])
        self.assertTrue(git.commit(self.root, "feat: add b\n\n- Add b.txt")[0])
        self.assertEqual(git.graph(self.root)[0].subject, "feat: add b")

    def test_a_commit_with_nothing_staged_takes_every_change(self):
        """As GitHub Desktop commits: the changed, deleted and new files, never an ignored one."""
        for name in ("a.txt", "gone.txt", ".gitignore"):
            self.write(name, "x\n" if name != ".gitignore" else "notes.local\n")
        self.commit_all()
        self.write("a.txt", "changed\n")
        os.remove(os.path.join(self.root, "gone.txt"))
        self.write("new.txt", "new\n")                                    # not gone.txt's: no rename
        self.write("notes.local", "mine\n")
        self.run_git("init", "-q", "-b", "main", "inner")                  # a repository of its own inside: not added
        self.write("inner/c.txt")
        self.assertTrue(git.commit(self.root, "feat: everything")[0])
        shown = self.run_git("show", "--name-status", "--format=", "HEAD").split()
        self.assertEqual(sorted(zip(shown[::2], shown[1::2])), [("A", "new.txt"), ("D", "gone.txt"), ("M", "a.txt")])

    def test_a_commit_takes_the_paths_it_was_given_not_one_come_since(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write(".env", "TOKEN=1\n")                                    # come after the question was asked
        self.assertTrue(git.commit(self.root, "fix: a", ["a.txt"])[0])
        self.assertEqual(self.run_git("show", "--name-only", "--format=", "HEAD").split(), ["a.txt"])
        self.assertEqual([c.path for c in git.status(self.root).changes], [".env"])

    def test_a_commit_takes_only_what_is_staged_when_something_is(self):
        self.write("a.txt")
        self.commit_all()
        self.write("a.txt", "changed\n")
        self.write("b.txt")
        git.stage(self.root, ["b.txt"])
        self.assertTrue(git.commit(self.root, "feat: b only")[0])
        self.assertEqual(self.run_git("show", "--name-only", "--format=", "HEAD").split(), ["b.txt"])
        self.assertEqual([c.path for c in git.status(self.root).changes], ["a.txt"])

    def test_a_name_is_a_name_not_a_pattern(self):
        for name in ("pages/[id].tsx", "pages/i.tsx", "pages/d.tsx"):
            self.write(name)
        self.commit_all()
        for name in ("pages/[id].tsx", "pages/i.tsx", "pages/d.tsx"):
            self.write(name, "changed\n")
        self.assertIsNone(git.stage(self.root, ["pages/[id].tsx"]))
        self.assertEqual([c.path for c in git.status(self.root).staged], ["pages/[id].tsx"])
        self.assertIsNone(git.unstage(self.root, ["pages/[id].tsx"]))
        self.assertIsNone(git.discard(self.root, "pages/[id].tsx"))
        self.assertEqual(sorted(c.path for c in git.status(self.root).changes), ["pages/d.tsx", "pages/i.tsx"])

    def test_unstage_before_the_first_commit(self):
        self.write("a.txt")
        git.stage(self.root, ["a.txt"])
        git.unstage(self.root, ["a.txt"])
        self.assertEqual(git.status(self.root).staged, [])

    def test_push_and_pull_fast_forward_only(self):
        remote = self.folder()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
        self.write("a.txt")
        self.commit_all()
        self.assertEqual(git.push(self.root), (False, "no remote"))
        self.run_git("remote", "add", "origin", remote)
        self.assertTrue(git.push(self.root)[0])                         # the first push sets the upstream
        self.assertEqual(git.status(self.root).upstream, "origin/main")
        other = self.folder()
        subprocess.run(["git", "clone", "-q", remote, other], check=True)
        self.write("b.txt", root=other)
        self.commit_all("b", cwd=other)
        self.run_git("push", "-q", cwd=other)
        self.write("c.txt")
        self.commit_all("c")                                            # the two have diverged now
        ok, message = git.pull(self.root)
        self.assertFalse(ok)
        self.assertTrue(message)
        self.assertNotIn("Unmerged", self.run_git("status"))           # nothing was merged

    def test_sync_pulls_then_pushes_and_starts_an_upstream(self):
        remote = self.folder()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
        self.write("a.txt")
        self.commit_all()
        self.run_git("remote", "add", "origin", remote)
        self.assertTrue(git.sync(self.root)[0])                         # no upstream yet: only the push, with -u
        self.assertEqual(git.status(self.root).upstream, "origin/main")
        other = self.folder()
        subprocess.run(["git", "clone", "-q", remote, other], check=True)
        self.write("b.txt", root=other)
        self.commit_all("b", cwd=other)
        self.run_git("push", "-q", cwd=other)
        self.write("c.txt")
        self.commit_all("c")
        self.run_git("reset", "-q", "--soft", "HEAD~1")                 # c undone: only behind now
        self.run_git("stash", "-q", "--include-untracked")
        self.assertTrue(git.sync(self.root)[0])                         # pulled b, nothing to push
        self.assertTrue(os.path.exists(os.path.join(self.root, "b.txt")))
        self.write("d.txt")
        self.commit_all("d")
        self.write("e.txt", root=other)
        self.commit_all("e", cwd=other)
        self.run_git("push", "-q", cwd=other)
        ok, _ = git.sync(self.root)                                      # diverged: stops, nothing merged
        self.assertFalse(ok)
        self.assertNotIn("e.txt", self.run_git("ls-files"))

    def test_sync_does_not_bring_back_a_branch_deleted_on_the_remote(self):
        remote = self.folder()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", remote], check=True)
        self.write("a.txt")
        self.commit_all()
        self.run_git("remote", "add", "origin", remote)
        self.run_git("push", "-q", "-u", "origin", "main")
        self.run_git("switch", "-q", "-c", "feature")
        self.write("b.txt")
        self.commit_all("b")
        self.run_git("push", "-q", "-u", "origin", "feature")
        self.run_git("push", "-q", "origin", "--delete", "feature")                  # merged and deleted there
        self.run_git("fetch", "-q", "--prune")
        for step in (git.sync, git.push):
            ok, line = step(self.root)
            self.assertFalse(ok)
            self.assertIn("gone", line)
        self.assertNotIn("feature", subprocess.run(["git", "-C", remote, "branch"], capture_output=True,
                                                   text=True).stdout)

    def test_a_failed_sync_says_what_to_do(self):
        self.assertIn("merge or rebase", git.advice("fatal: Not possible to fast-forward, aborting."))
        self.assertIn("git remote add", git.advice("no remote"))
        self.assertIn("sign in", git.advice("fatal: Authentication failed for 'https://example.com/r.git/'"))
        self.assertIn("deleted on the remote", git.advice("its upstream branch is gone from the remote"))
        self.assertEqual(git.advice("error: something else"), "error: something else")

    def test_the_graph_marks_head_and_refs(self):
        self.write("a.txt")
        self.commit_all("one")
        self.write("a.txt", "2\n")
        self.commit_all("two")
        graph = git.graph(self.root)
        self.assertEqual([c.subject for c in graph], ["two", "one"])
        self.assertTrue(graph[0].head)
        self.assertFalse(graph[1].head)
        self.assertIn("main", graph[0].refs)
        self.assertEqual(graph[0].author, "dev")


class GitHubName(unittest.TestCase):
    """The repository's name on GitHub, from git's config: nothing of the repository's runs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q")

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True)

    def test_the_github_name_from_any_form_of_its_address(self):
        for url in ("https://github.com/acme/app.git", "https://github.com/acme/app", "git@github.com:acme/app.git",
                    "ssh://git@github.com/acme/app.git", "https://git@github.com/acme/app/"):
            if self.remotes():
                self.git("remote", "remove", "origin")
            self.git("remote", "add", "origin", url)
            self.assertEqual(git.github_name(self.root), "acme/app", url)

    def remotes(self):
        return subprocess.run(["git", "-C", self.root, "remote"], capture_output=True, text=True).stdout.split()

    def test_origin_wins_over_another_github_remote(self):
        self.git("remote", "add", "fork", "https://github.com/someone/app.git")
        self.git("remote", "add", "origin", "https://github.com/acme/app.git")
        self.assertEqual(git.github_name(self.root), "acme/app")

    def test_another_github_remote_when_origin_is_elsewhere(self):
        self.git("remote", "add", "origin", "https://gitlab.com/acme/app.git")
        self.git("remote", "add", "hub", "git@github.com:acme/app.git")
        self.assertEqual(git.github_name(self.root), "acme/app")

    def test_no_github_remote_is_no_name(self):
        self.assertIsNone(git.github_name(self.root))
        self.git("remote", "add", "origin", "https://gitlab.com/acme/app.git")
        self.assertIsNone(git.github_name(self.root))
        self.git("remote", "add", "lookalike", "https://github.com.example.com/acme/app.git")
        self.assertIsNone(git.github_name(self.root))

    def test_a_folder_outside_a_repository_has_none(self):
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        self.assertIsNone(git.github_name(outside))


if __name__ == "__main__":
    unittest.main()
