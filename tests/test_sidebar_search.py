"""Tests for the sidebar's search (src/plugins/sidebar/search.py): ripgrep, git grep and the built-in search agree on
switches, ignored files, the limit, errors and folders of repositories; nothing outside the folder is read, and no
program can wait on the terminal or run past its time."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from support import SRC, set_env, stubs, trap

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import search as module  # noqa: E402
from search import Query, search  # noqa: E402

FILES = {"app/page.tsx": "<Hero title=\"x\" />\n",
         "components/Hero.tsx": "export function Hero() {\n  const hero = 1\n}\n",
         "components/Heroic.tsx": "Heroic\n", "notes.local": "Hero in an ignored file\n", ".gitignore": "notes.local\n"}


# ripgrep's own output shape (--null --line-number --no-heading), for one hit
FAKE_RG = "#!/bin/sh\nprintf './components/Hero.tsx\\0001:export function Hero() {\\n'\n"
# an rg that complains a lot (unreadable folders, say) before its hit, one with a Windows path, and one run in a
# folder (its paths from there)
NOISY_RG = "#!/bin/sh\nhead -c 300000 /dev/zero | tr '\\0' 'x' >&2\nprintf 'a.txt\\0001:Hero\\n'\n"
WINDOWS_RG = "#!/bin/sh\nprintf '.\\\\components\\\\Hero.tsx\\0001:Hero\\n'\n"
FOLDER_RG = "#!/bin/sh\nprintf './Hero.tsx\\0001:export function Hero() {\\n'\n"
# a git without Perl regex support: its grep -P fails the way such a git does, everything else is the real git
FAKE_GIT = """#!/bin/sh
case " $* " in *" grep "*" -P "*)
  echo "fatal: cannot use Perl-compatible regexes when not compiled with USE_LIBPCRE" >&2; exit 128 ;; esac
exec /usr/bin/git "$@"
"""


def no_rg(name):
    return None if name == "rg" else shutil.which(name)


def nothing(name):
    return None


class Search(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull)
        for rel, text in FILES.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)

    def files(self, query, **kwargs):
        result = search(self.root, query, **kwargs)
        return sorted({hit.path for hit in result.hits}), result

    def test_git_grep_finds_the_files_and_skips_ignored_ones(self):
        files, result = self.files(Query("Hero"), which=no_rg)
        self.assertEqual(files, ["app/page.tsx", "components/Hero.tsx", "components/Heroic.tsx"])
        self.assertIsNone(result.error)

    @unittest.skipUnless(shutil.which("rg"), "ripgrep is not installed")
    def test_ripgrep_gives_the_same_files(self):
        self.assertEqual(self.files(Query("Hero"))[0], self.files(Query("Hero"), which=no_rg)[0])

    def test_ripgrep_output_is_read(self):
        fake = os.path.join(stubs(os.path.join(self.root, ".bin"), {"rg": FAKE_RG}), "rg")
        result = search(self.root, Query("Hero"), which=lambda name: fake if name == "rg" else None)
        self.assertEqual([(h.path, h.line_no) for h in result.hits], [("components/Hero.tsx", 1)])

    def test_a_downloaded_folders_fsmonitor_does_not_run_on_a_search(self):
        # git's own grep, and its file list when that git has no Perl regex
        fake = os.path.join(stubs(os.path.join(self.root, ".bin"), {"git": FAKE_GIT}), "git")
        programs = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, programs)
        mark = trap(self.root, "core.fsmonitor", programs)
        search(self.root, Query("Hero"), which=no_rg)
        search(self.root, Query("export func\\w+", regex=True), which=lambda name: fake if name == "git" else None)
        self.assertFalse(os.path.exists(mark))

    def test_a_git_without_perl_regex_falls_back_to_its_file_list(self):
        fake = os.path.join(stubs(os.path.join(self.root, ".bin"), {"git": FAKE_GIT}), "git")
        result = search(self.root, Query("export func\\w+", regex=True),
                        which=lambda name: fake if name == "git" else None)
        self.assertEqual((result.error, sorted({h.path for h in result.hits})), (None, ["components/Hero.tsx"]))

    def test_the_built_in_search_outside_a_repository(self):
        shutil.rmtree(os.path.join(self.root, ".git"))
        files, _ = self.files(Query("Hero"), which=nothing)
        self.assertIn("components/Hero.tsx", files)

    def outside_with_a_repository(self):
        """The root as a folder holding a repository (project/) with an ignored node_modules, and a file of its own;
        the repository's own git, as a downloaded folder's could, has an fsmonitor; returns that trap's mark."""
        shutil.rmtree(os.path.join(self.root, ".git"))
        project = os.path.join(self.root, "project")
        for rel, text in (("src/a.ts", "Hero\n"), ("node_modules/lib/x.js", "Hero\n"),
                          (".gitignore", "node_modules/\n")):
            os.makedirs(os.path.dirname(os.path.join(project, rel)), exist_ok=True)
            with open(os.path.join(project, rel), "w") as f:
                f.write(text)
        subprocess.run(["git", "-C", project, "init", "-q"], check=True)
        programs = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, programs)
        return trap(project, "core.fsmonitor", programs)

    def test_outside_a_repository_a_repository_in_it_keeps_its_ignored_files_out(self):
        # a folder of projects: each one's node_modules and build output are no hits, and are not read at all
        mark = self.outside_with_a_repository()
        files, _ = self.files(Query("Hero"), which=no_rg)
        self.assertIn("project/src/a.ts", files)
        self.assertIn("components/Hero.tsx", files)                     # the folder's own files as ever
        self.assertNotIn("project/node_modules/lib/x.js", files)
        self.assertFalse(os.path.exists(mark))

    def test_a_folder_alone_with_its_paths_from_the_root(self):
        self.assertEqual(self.files(Query("Hero"), place="components", which=no_rg)[0],
                         ["components/Hero.tsx", "components/Heroic.tsx"])
        self.assertEqual(self.files(Query("Hero"), place="components", which=self.rg(FOLDER_RG))[0],
                         ["components/Hero.tsx"])                       # ripgrep run in the folder: ./Hero.tsx
        self.outside_with_a_repository()
        self.assertEqual(self.files(Query("Hero"), place="project", which=no_rg)[0], ["project/src/a.ts"])
        self.assertEqual(self.files(Query("Hero"), place="components", which=nothing)[0],
                         ["components/Hero.tsx", "components/Heroic.tsx"])

    def test_a_file_alone(self):
        # a file chosen in Files: only its lines, its path from the root, an ignored one too (it was asked for)
        for which in (no_rg, nothing):
            files, result = self.files(Query("Hero"), place="components/Hero.tsx", which=which)
            self.assertEqual((files, result.total), (["components/Hero.tsx"], 2), which)
        self.assertEqual(self.files(Query("Hero"), place="notes.local", which=no_rg)[0], ["notes.local"])

    def test_nothing_outside_the_folder_is_read(self):
        # a downloaded folder: a link in it, or a repository's own list (its index), may name a file outside
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        secret = os.path.join(outside, "secret.txt")
        with open(secret, "w") as f:
            f.write("Hero outside\n")
        os.symlink(secret, os.path.join(self.root, "link.txt"))
        os.symlink(outside, os.path.join(self.root, "away"))
        shutil.rmtree(os.path.join(self.root, ".git"))
        files, _ = self.files(Query("Hero"), which=nothing)
        self.assertNotIn("link.txt", files)
        self.assertFalse([path for path in files if path.startswith("away")])
        with mock.patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, b"\0".join([b"../secret.txt", secret.encode(), b"sub/../../x", b"away/secret.txt",
                                    b"components/Hero.tsx"]), b"")):
            self.assertEqual(module.repo_files("git", self.root), ["away/secret.txt", "components/Hero.tsx"])
        collector = module.Collector(module.pattern(Query("Hero")), 10)
        module.scan(self.root, ["away/secret.txt", "components/Hero.tsx"], None, collector)
        self.assertEqual({hit.path for hit in collector.result.hits}, {"components/Hero.tsx"})

    def test_a_link_or_a_way_out_is_no_place_to_search(self):
        # a link chosen in Files (shown as a file) would lead every search to its target, outside the folder
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside)
        with open(os.path.join(outside, "secret.txt"), "w") as f:
            f.write("Hero outside\n")
        os.symlink(outside, os.path.join(self.root, "evil"))
        os.symlink(os.path.join(outside, "secret.txt"), os.path.join(self.root, "evil.txt"))
        for place in ("evil", "evil.txt", "../" + os.path.basename(outside)):
            for which in (no_rg, nothing, self.rg(FOLDER_RG)):
                self.assertEqual(search(self.root, Query("Hero"), place=place, which=which).hits, [], place)

    @unittest.skipIf(os.name == "nt", "no process groups on Windows")
    def test_a_program_that_leaves_one_holding_its_output_is_stopped_in_time(self):
        # its child keeps the output open after it ends: stopping only the program would leave the search waiting
        rg = self.rg("#!/bin/sh\nsleep 60 &\nprintf 'a.txt\\0001:Hero\\n'\n")
        with mock.patch.object(module, "TIMEOUT", 1):
            started = time.monotonic()
            result = search(self.root, Query("Hero"), which=rg)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual([hit.path for hit in result.hits], ["a.txt"])

    def test_a_repositorys_config_cannot_make_git_wait_on_the_terminal(self):
        # [include] path = /dev/stdin (or /dev/tty): git would read the sidebar's own terminal, its keys, for good
        subprocess.run(["git", "-C", self.root, "config", "include.path", "/dev/stdin"], check=True)
        code = (f"import shutil, sys; sys.path.insert(0, {os.path.join(SRC, 'plugins', 'sidebar')!r}); "
                f"from search import Query, search; "
                f"print(search({self.root!r}, Query('Hero'), which=lambda n: None if n == 'rg' else shutil.which(n))"
                f".total)")
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
        self.assertEqual(proc.stdout.read().strip(), "4")
        proc.stdout.close()

    @unittest.skipIf(os.name == "nt", "no named pipes here on Windows")
    def test_a_git_that_never_answers_is_stopped_in_time(self):
        # [include] path = a named pipe nobody writes to: git waits for good; the search does not
        fifo = os.path.join(tempfile.mkdtemp(), "pipe")
        self.addCleanup(shutil.rmtree, os.path.dirname(fifo))
        os.mkfifo(fifo)
        subprocess.run(["git", "-C", self.root, "config", "include.path", fifo], check=True)
        with mock.patch.object(module, "TIMEOUT", 1), mock.patch.object(module, "QUICK", 1):
            started = time.monotonic()
            result = search(self.root, Query("Hero"), which=no_rg)
        self.assertLess(time.monotonic() - started, 8)
        self.assertIn("components/Hero.tsx", {hit.path for hit in result.hits})       # the folder walked instead

    def test_case_word_and_regex(self):
        self.assertIn("components/Hero.tsx", self.files(Query("hero", case=False), which=no_rg)[0])
        self.assertEqual(self.files(Query("hero", case=True), which=no_rg)[0], ["components/Hero.tsx"])
        self.assertNotIn("components/Heroic.tsx", self.files(Query("Hero", word=True), which=no_rg)[0])
        self.assertEqual(self.files(Query("export func\\w+", regex=True), which=no_rg)[0], ["components/Hero.tsx"])

    def test_the_match_is_marked_on_its_line(self):
        hit = next(h for h in search(self.root, Query("Hero"), which=no_rg).hits if h.path == "app/page.tsx")
        self.assertEqual((hit.line_no, hit.text[slice(*hit.spans[0])]), (1, "Hero"))

    def test_the_limit_stops_the_hits_not_the_count(self):
        result = search(self.root, Query("Hero"), limit=2, which=no_rg)
        self.assertEqual((len(result.hits), result.total, result.files), (2, 4, 3))

    def test_a_broken_regex_is_an_error_not_a_crash(self):
        result = search(self.root, Query("(", regex=True), which=no_rg)
        self.assertEqual(result.hits, [])
        self.assertTrue(result.error)

    def test_a_cancelled_search_stops(self):
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(search(self.root, Query("Hero"), cancel=cancel, which=no_rg).hits, [])

    def rg(self, script):
        fake = os.path.join(stubs(os.path.join(self.root, ".bin"), {"rg": script}), "rg")
        return lambda name: fake if name == "rg" else None

    def test_a_flood_of_errors_does_not_stall_it(self):
        found = []
        worker = threading.Thread(target=lambda: found.append(search(self.root, Query("Hero"),
                                                                     which=self.rg(NOISY_RG))), daemon=True)
        worker.start()
        worker.join(5)
        self.assertEqual([(h.path, h.line_no) for h in found[0].hits] if found else "stalled", [("a.txt", 1)])

    def test_ripgreps_windows_paths_lose_their_dot(self):
        hit = search(self.root, Query("Hero"), which=self.rg(WINDOWS_RG)).hits[0]
        self.assertFalse(hit.path.startswith("."), hit.path)

    def test_a_line_is_what_ends_in_a_newline(self):
        with open(os.path.join(self.root, "paged.txt"), "w") as f:
            f.write("one\ftwo\nHero here\n")                         # a form feed is not a new line
        shutil.rmtree(os.path.join(self.root, ".git"))
        hit = next(h for h in search(self.root, Query("Hero here"), which=nothing).hits)
        self.assertEqual((hit.path, hit.line_no), ("paged.txt", 2))

    def test_an_empty_query_finds_nothing(self):
        self.assertEqual(search(self.root, Query(""), which=no_rg).total, 0)


if __name__ == "__main__":
    unittest.main()
