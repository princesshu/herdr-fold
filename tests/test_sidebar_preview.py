"""Tests for the sidebar's preview (preview.py, pager.py): files, diffs and commits go to the pager through a file named
in the tab's environment, so the typed shell line holds no path; one preview tab per workspace; the pager's line jump,
search and color-only output, with no stall on a binary or huge file."""
import json
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_child, finished, logged, set_attrs, set_env, sign_head, stubs, trap
from test_core_media import pdf, png

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import media  # noqa: E402
import pager  # noqa: E402
import preview  # noqa: E402
from vt import Key  # noqa: E402

# a workspace with a preview tab (w1:t2) beside its files tab; its pager runs ($PAGING=1) or herdr has started again
# and left a shell there
FAKE_HERDR = """#!/bin/sh
printf '%s\\n' "$*" >> "$HERDR_LOG"
case "$1 $2" in
  "tab list") echo '{"result": {"tabs": [{"tab_id": "w1:t1", "label": "files"},'\
                   '{"tab_id": "w1:t2", "label": "preview: old.md"}]}}' ;;
  "pane list") echo '{"result": {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "sidebar"},'\
                    '{"pane_id": "w1:p4", "tab_id": "w1:t2", "label": "preview"}]}}' ;;
  "pane process-info") if [ "$PAGING" = 1 ]; then name=Python; else name=-zsh; fi
                       echo '{"result": {"process_info": {"foreground_processes": [{"name": "'$name'"}]}}}' ;;
  "tab create") [ "$CREATE" = fails ] && { echo "herdr said no" >&2; exit 2; }
                echo '{"result": {"tab": {"tab_id": "w1:t3"}, "root_pane": {"pane_id": "w1:p9"}}}' ;;
  "tab close"|"tab rename"|"tab focus"|"pane run"|"pane rename") echo '{"result": {}}' ;;
  *) echo "no such command" >&2; exit 2 ;;
esac
"""


SPEC = {"title": "a.py", "line": 3, "file": "/repo/a.py", "pipeline": []}


def tools(*present):
    return lambda name: f"/opt/bin/{name}" if name in present else None


class Commands(unittest.TestCase):
    def test_a_file_with_bat_or_plain(self):
        spec = preview.file_spec("/repo", "/repo/a.py", 40, which=tools("bat"))
        self.assertEqual(spec["pipeline"][0][:2], ["/opt/bin/bat", "--color=always"])
        self.assertEqual((spec["line"], spec["title"]), (40, "a.py"))
        plain = preview.file_spec("/repo", "/repo/a.py", None, which=tools())
        self.assertEqual((plain["pipeline"], plain["file"]), ([], "/repo/a.py"))

    def test_over_ssh_no_page_offers_a_browser(self):
        set_env(self, SSH_CONNECTION="the client and this machine")
        self.assertNotIn("open", preview.file_spec("/repo", "/repo/site/index.html", None, which=tools("bat")))

    def test_a_page_opens_in_the_browser_with_o(self):
        set_env(self, SSH_CONNECTION=None, SSH_CLIENT=None)
        spec = preview.file_spec("/repo", "/repo/site/index.html", None, which=tools("bat"))
        self.assertEqual(spec["open"], "/repo/site/index.html")
        self.assertNotIn("open", preview.file_spec("/repo", "/repo/a.py", None, which=tools("bat")))
        page = pager.Pager(["<html>"], "index.html", opens="/repo/site/index.html")
        self.assertIn("o: open in browser", page.status())
        with mock.patch.object(pager.media, "open_in_browser", return_value=True) as opened:
            page.handle(Key("char", "o"))
        opened.assert_called_once_with("/repo/site/index.html")

    def test_an_image_or_a_pdf_is_a_picture(self):
        spec = preview.file_spec("/repo", "/repo/docs/shot.webp", None, which=tools("bat"))
        self.assertEqual((spec["picture"], spec["title"]), ("/repo/docs/shot.webp", "docs/shot.webp"))
        self.assertEqual(preview.file_spec("/repo", "/repo/a.pdf", None, which=tools("bat"))["picture"], "/repo/a.pdf")
        self.assertNotIn("picture", preview.file_spec("/repo", "/repo/a.py", None, which=tools("bat")))

    def test_an_svg_or_a_page_is_a_picture_with_its_code(self):
        set_env(self, SSH_CONNECTION=None, SSH_CLIENT=None)
        for name in ("logo.svg", "site/index.html"):
            spec = preview.file_spec("/repo", f"/repo/{name}", None, which=tools("bat"))
            self.assertEqual((spec["picture"], spec["open"]), (f"/repo/{name}", f"/repo/{name}"))
            self.assertEqual(spec["pipeline"][0][:2], ["/opt/bin/bat", "--color=always"])

    @unittest.skipIf(os.name == "nt", "no named pipes here on Windows")
    def test_a_pipe_is_never_handed_to_bat(self):
        # bat would wait on it for good; the pager says what it is instead
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        os.mkfifo(os.path.join(folder, "pipe"))
        spec = preview.file_spec(folder, os.path.join(folder, "pipe"), None, which=tools("bat"))
        self.assertEqual((spec["pipeline"], spec["file"]), ([], os.path.join(folder, "pipe")))

    def test_bat_marks_the_line_and_keeps_one_row_per_line(self):
        argv = preview.file_spec("/repo", "/repo/a.py", 40, which=tools("bat"))["pipeline"][0]
        self.assertEqual(argv[argv.index("--highlight-line") + 1], "40")
        self.assertIn("--wrap=never", argv)
        unmarked = preview.file_spec("/repo", "/repo/a.py", None, which=tools("bat"))
        self.assertNotIn("--highlight-line", unmarked["pipeline"][0])

    def test_a_diff_with_delta_or_git_colors(self):
        spec = preview.diff_spec("/repo", "a.py", staged=True, which=tools("git", "delta"))
        git = spec["pipeline"][0]
        self.assertEqual((git[0], git[git.index("-C") + 1]), ("/opt/bin/git", "/repo"))
        self.assertEqual(git[git.index("diff"):][-3:], ["--cached", "--", "a.py"])
        self.assertEqual(spec["pipeline"][1][0], "/opt/bin/delta")
        plain = preview.diff_spec("/repo", "a.py", staged=False, which=tools("git"))
        self.assertEqual(len(plain["pipeline"]), 1)
        self.assertIn("--color=always", plain["pipeline"][0])

    def test_delta_numbers_the_lines_and_heads_a_hunk_without_a_box(self):
        # delta's own hunk header is a box open on the left, its line number flush against the edge: it read as
        # shifted; the lines numbered as GitHub's, a hunk headed by its function alone
        for spec in (preview.diff_spec("/repo", "a.py", staged=True, which=tools("git", "delta")),
                     preview.commit_spec("/repo", "abc1234", which=tools("git", "delta"))):
            self.assertEqual(spec["pipeline"][1], ["/opt/bin/delta", "--paging=never", "--line-numbers",
                                                   "--hunk-header-decoration-style=none",
                                                   "--hunk-header-style=syntax"])

    def test_a_diff_reads_the_name_as_a_name(self):
        argv = preview.diff_spec("/repo", "pages/[id].tsx", staged=False, which=tools("git"))["pipeline"][0]
        self.assertLess(argv.index("--literal-pathspecs"), argv.index("diff"))

    def test_powershell_quotes_its_curly_quotes_too(self):
        launch = preview.interactive(["gh", "issue", "comment", "O\u2019Brien"], windows=True)
        self.assertIn("'O\u2019\u2019Brien'", launch.line)

    def test_a_commit(self):
        argv = preview.commit_spec("/repo", "abc1234", which=tools("git"))["pipeline"][0]
        self.assertEqual(argv[argv.index("show"):][-2:], ["--color=always", "abc1234"])

    def test_the_typed_line_holds_no_path_and_nothing_shown(self):
        # the line shows on screen and stays in the shell's history: a path may name the account (a home folder)
        path = "/srv/someone/state/preview-w1.json"
        for windows in (False, True):
            launch = preview.command(path, windows=windows)
            self.assertNotIn("/", launch.line.replace("$env:", ""))
            self.assertNotIn("someone", launch.line)
            self.assertEqual(launch.env["HERDR_FOLD_SPEC_FILE"], path)
            self.assertEqual(launch.env["HERDR_FOLD_PAGER"], preview.PAGER)

    def test_the_pager_leaves_no_python_cache_next_to_the_plugin(self):
        for windows in (False, True):
            self.assertIn(" -B ", preview.command("/state/preview-w1.json", windows=windows).line)

    def test_an_interactive_command_closes_its_tab_only_when_it_ends_well(self):
        unix = preview.interactive(["/srv/someone/bin/gh", "issue", "comment", "42"], windows=False)
        self.assertEqual(unix.line, '"$HERDR_FOLD_PROGRAM" issue comment 42 && exit')
        self.assertEqual(unix.env, {"HERDR_FOLD_PROGRAM": "/srv/someone/bin/gh"})
        windows = preview.interactive(["D:\\tools\\gh.exe", "issue", "create"], windows=True)
        self.assertEqual(windows.line, "& $env:HERDR_FOLD_PROGRAM 'issue' 'create'; if ($?) { exit }")

    def test_the_shell_ends_with_the_pager_but_not_after_an_error(self):
        self.assertTrue(preview.command("/state/p.json", windows=False).line.endswith(" && exit"))
        self.assertTrue(preview.command("/state/p.json", windows=True).line.endswith("; if ($?) { exit }"))

    def test_a_shell_runs_the_typed_line_with_the_tabs_environment(self):
        launch = preview.command("/state/preview-w1.json", windows=False)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        stubs(tmp, {"python": '#!/bin/sh\nprintf "%s|" "$@"; echo "$HERDR_FOLD_SPEC_FILE"\n'})
        env = {**launch.env, "HERDR_FOLD_PYTHON": os.path.join(tmp, "python"), "PATH": "/usr/bin:/bin"}
        out = subprocess.run(["/bin/sh", "-c", launch.line.replace(" && exit", "")], env=env, capture_output=True,
                             text=True).stdout
        self.assertEqual(out, f"-B|{preview.PAGER}|/state/preview-w1.json\n")


class ForeignConfig(unittest.TestCase):
    def test_a_diff_or_a_commit_starts_no_program_the_repository_names(self):
        """A click on a change or a commit runs git diff or git show: a downloaded folder's .git/config must not start
        a program then (fsmonitor, an external diff, a text conversion)."""
        root, programs = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, programs)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        for name, text in (("a.txt", "a\n"), (".gitattributes", "* diff=conv\n")):
            with open(os.path.join(root, name), "w") as f:
                f.write(text)
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", "-C", root, *args], check=True)
        with open(os.path.join(root, "a.txt"), "a") as f:
            f.write("b\n")
        marks = [trap(root, key, programs) for key in ("core.fsmonitor", "diff.external", "diff.conv.textconv")]
        git_only = lambda name: shutil.which(name) if name == "git" else None  # noqa: E731
        for spec in (preview.diff_spec(root, "a.txt", False, which=git_only),
                     preview.commit_spec(root, "HEAD", which=git_only)):
            self.assertIn("a", pager.read(spec).decode())
        self.assertEqual([os.path.basename(m) for m in marks if os.path.exists(m)], [])

    def test_a_signed_commit_shown_starts_no_signature_check(self):
        """git show of a signed commit: a downloaded folder's log.showSignature must not start its gpg.program."""
        root, programs = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, programs)
        set_env(self, GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.com",
                GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        with open(os.path.join(root, "a.txt"), "w") as f:
            f.write("a\n")
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", "-C", root, *args], check=True)
        sign_head(root)
        subprocess.run(["git", "-C", root, "config", "log.showSignature", "true"], check=True)
        mark = trap(root, "gpg.program", programs)
        git_only = lambda name: shutil.which(name) if name == "git" else None  # noqa: E731
        self.assertIn("signed", pager.read(preview.commit_spec(root, "HEAD", which=git_only)).decode())
        self.assertFalse(os.path.exists(mark))


class Tabs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.log = os.path.join(self.tmp, "log")
        set_env(self, HERDR_LOG=self.log, PAGING="0")
        self.herdr = preview.Herdr(os.path.join(stubs(os.path.join(self.tmp, "bin"), {"herdr": FAKE_HERDR}), "herdr"))
        self.laid = []

    def show(self, spec=SPEC, here=None):
        def lay_out(tab):
            self.laid.append((tab, len(logged(self.log))))
        preview.open_preview(self.herdr, "w1", "/repo", spec, self.tmp, lay_out, here)

    def test_the_preview_tabs_pager_takes_up_the_next_one(self):
        # the tab stays, its columns and sidebar with it: from that sidebar the next file opens there too
        os.environ["PAGING"] = "1"
        self.show()                                                         # no file yet: a new tab
        os.remove(self.log)
        self.show()
        with open(preview.spec_file(self.tmp, "w1")) as f:
            self.assertEqual(json.load(f), SPEC)
        calls = logged(self.log)
        self.assertEqual(calls[-2:], ["tab rename w1:t2 preview: a.py", "tab focus w1:t2"])
        self.assertFalse([call for call in calls if call.startswith(("tab create", "tab close", "pane run"))])

    def test_a_pager_with_no_file_to_watch_is_replaced(self):
        # one started before this version (it watches no file), or one whose file is gone: it would show nothing new
        os.environ["PAGING"] = "1"
        self.show()
        self.assertEqual(logged(self.log)[-1], "tab close w1:t2")
        self.assertIn("pane rename w1:p9 preview", logged(self.log))

    def test_a_preview_tab_whose_pager_no_longer_runs_is_replaced_after_the_new_one_is_laid_out(self):
        self.show(here="w1:t1")
        calls, path = logged(self.log), preview.spec_file(self.tmp, "w1")
        self.assertIn(f"tab create --workspace w1 --cwd /repo --label preview: a.py --env HERDR_FOLD_PYTHON="
                      f"{sys.executable} --env HERDR_FOLD_PAGER={preview.PAGER} --env HERDR_FOLD_SPEC_FILE={path} "
                      "--no-focus", calls)
        rename, run = calls.index("pane rename w1:p9 preview"), calls.index('pane run w1:p9 "$HERDR_FOLD_PYTHON" -B '
                                                                             '"$HERDR_FOLD_PAGER" && exit')
        self.assertEqual(len(self.laid), 1)
        tab, at = self.laid[0]
        self.assertEqual(tab, "w1:t3")
        self.assertTrue(rename < at <= run, calls)                    # named (tab-layout leaves it), laid out, run
        self.assertEqual(calls[-1], "tab close w1:t2")
        self.assertNotIn("tab close w1:t1", calls)

    def seeded(self, **taken):
        """The layout a sidebar's open_preview gives: a seed for each kind of pane TAKEN names, which takes it (removes
        it) that many seconds on (None: never), noted in the log."""
        def lay_out(tab):
            for kind, after in taken.items():
                path = preview.seed_file(self.tmp, tab, kind)
                with open(path, "w") as f:
                    f.write("{}")

                def take(path=path, kind=kind):
                    os.remove(path)
                    with open(self.log, "a") as f:
                        f.write(f"{kind} took its seed\n")
                if after is not None:
                    threading.Timer(after, take).start()
        return lay_out

    def test_a_new_tab_comes_to_the_front_once_its_column_has_started(self):
        """Made in the background, laid out, its pager run, shown once its sidebar and Conversations column have
        started (each takes its seed just before it first draws): no half-drawn tab, no shell's prompt, on screen."""
        preview.open_preview(self.herdr, "w1", "/repo", SPEC, self.tmp, self.seeded(sidebar=0.2, conversations=0.4),
                             "w1:t1")
        calls = logged(self.log)
        self.assertLess(calls.index("conversations took its seed"), calls.index("tab focus w1:t3"), calls)
        self.assertLess(next(n for n, call in enumerate(calls) if call.startswith("pane run w1:p9")),
                        calls.index("sidebar took its seed"))

    def test_a_column_that_never_starts_lets_the_tab_show_all_the_same(self):
        set_attrs(self, preview, READY=0.3)
        preview.open_preview(self.herdr, "w1", "/repo", SPEC, self.tmp, self.seeded(sidebar=None), "w1:t1")
        self.assertIn("tab focus w1:t3", logged(self.log))

    def test_the_asking_panes_own_tab_closes_last(self):
        # a sidebar in the old preview tab asks: closing that tab ends it, so nothing may come after
        self.show(here="w1:t2")
        self.assertEqual(logged(self.log)[-1], "tab close w1:t2")

    def test_a_failing_layout_still_starts_the_pager_and_closes_the_old_tab(self):
        def broken(tab):
            raise RuntimeError("herdr said no")
        with self.assertRaises(RuntimeError):
            preview.open_preview(self.herdr, "w1", "/repo", SPEC, self.tmp, broken, "w1:t1")
        calls = logged(self.log)
        self.assertTrue([call for call in calls if call.startswith("pane run w1:p9")])
        self.assertEqual(calls[-1], "tab close w1:t2")

    def test_the_old_tab_stays_when_no_new_one_could_be_opened(self):
        # it may hold the asking sidebar and a terminal at work: it gives way to a new tab only
        os.environ["CREATE"] = "fails"
        self.addCleanup(os.environ.pop, "CREATE", None)
        with self.assertRaises(RuntimeError):
            self.show(here="w1:t1")
        self.assertFalse([call for call in logged(self.log) if call.startswith("tab close")])

    def test_an_answer_of_another_shape_is_no_pager(self):
        class Odd:
            def __init__(self, answer):
                self.answer = answer

            def call(self, *args):
                return self.answer
        for answer in ({"process_info": {"foreground_processes": ["Python"]}}, {"process_info": None}, []):
            self.assertFalse(preview.paging(Odd(answer), "w1:p4"), answer)

    def test_the_label_holds_no_control_characters(self):
        self.show({**SPEC, "title": "a\x1b]0;x\x07b.md"})
        create = next(call for call in logged(self.log) if call.startswith("tab create"))
        self.assertIn("--label preview: a]0;xb.md --env", create)

    def test_a_tab_of_its_own_leaves_the_others_open(self):
        # gh's own prompts (a new issue, a comment) in a tab: nothing being typed in another one is closed
        preview.open_tab(self.herdr, "w1", "/repo", "issue: new", preview.Launch("gh issue create", {}))
        calls = logged(self.log)
        self.assertFalse([call for call in calls if call.startswith("tab close")])
        self.assertIn("tab create --workspace w1 --cwd /repo --label issue: new --no-focus", calls)
        self.assertEqual(calls[1:3], ["pane rename w1:p9 issue", "pane run w1:p9 gh issue create"])
        self.assertEqual(calls[-1], "tab focus w1:t3")

    def test_a_failing_herdr_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.herdr.call("pane", "nonsense")


class Lines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def file(self, data):
        path = os.path.join(self.tmp, "file")
        with open(path, "wb") as f:
            f.write(data)
        return {"title": "file", "line": None, "file": path, "pipeline": []}

    @unittest.skipIf(os.name == "nt", "no named pipes here on Windows")
    def test_a_pipe_or_a_device_is_not_read(self):
        # a downloaded folder's pipe, or a link to a terminal: read, it would never end, and q would not work
        os.mkfifo(os.path.join(self.tmp, "pipe"))
        os.symlink("/dev/tty", os.path.join(self.tmp, "tty"))
        def shown(name):
            return finished(self, lambda: pager.load({"title": name, "line": None,
                                                      "file": os.path.join(self.tmp, name), "pipeline": []}), 10)
        self.assertEqual(shown("pipe"), ["not a plain file: a pipe or a device is not shown"])
        self.assertEqual(len(shown("tty")), 1)              # said at once (here a test has no terminal to open)

    def test_a_pipeline_that_never_ends_is_stopped(self):
        spec = {"title": "slow", "line": None, "file": None,
                "pipeline": [[sys.executable, "-c", "print('first', flush=True); import time; time.sleep(60)"]]}
        with mock.patch.object(pager, "WAIT", 1):
            started = time.monotonic()
            shown = finished(self, lambda: pager.load(spec), 10)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(shown[0], "first")

    @unittest.skipIf(os.name == "nt", "no process groups on Windows")
    def test_a_program_that_leaves_one_holding_its_output_is_stopped_in_time(self):
        code = ("import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                "print('first', flush=True)")
        spec = {"title": "slow", "line": None, "file": None, "pipeline": [[sys.executable, "-c", code]]}
        with mock.patch.object(pager, "WAIT", 1):
            started = time.monotonic()
            shown = finished(self, lambda: pager.load(spec), 10)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(shown[0], "first")

    def test_only_colors_reach_the_terminal(self):
        line = "\x1b[31mred\x1b[0m \x1b]52;c;ZXZpbA==\x07\x1b[2Jtext\x07\x9b\x1b]0;title\x1b\\"
        self.assertEqual(pager.visible(line, 80), "\x1b[31mred\x1b[0m text")
        self.assertEqual(pager.plain(line), "red text")

    def test_no_text_is_hidden(self):
        # 8 (conceal) would let a file hide a line from the preview; an 8 that is a color's number stays
        self.assertEqual(pager.visible("\x1b[31;8msecret\x1b[0m \x1b[8mhidden", 80), "\x1b[31msecret\x1b[0m hidden")
        for kept in ("\x1b[38;5;8mgray", "\x1b[38;2;8;8;8mdark", "\x1b[48:5:8mback"):
            self.assertEqual(pager.visible(kept, 80), kept)

    def test_a_line_is_what_ends_in_a_newline(self):
        self.assertEqual(pager.load(self.file(b"one\x0ctwo\r\nthree\n")), ["one\x0ctwo", "three"])

    def test_a_pipeline_gets_the_environment_its_spec_names(self):
        spec = {"title": "env", "line": None, "file": None, "env": {"GREETING": "hello"},
                "pipeline": [["/bin/sh", "-c", 'printf "%s\\n" "$GREETING"']]}
        self.assertEqual(pager.load(spec), ["hello"])

    def test_a_binary_file_is_not_shown(self):
        self.assertEqual(pager.load(self.file(b"\x7fELF\x00\x01\x02")), ["binary file"])

    def test_a_huge_file_or_output_is_cut(self):
        with mock.patch.object(pager, "LIMIT", 1000):
            lines = pager.load(self.file(b"".join(b"line %04d\n" % i for i in range(1000))))
            self.assertLess(len(lines), 110)
            self.assertEqual(lines[-1], "\u2026")
            spec = {"title": "yes", "line": None, "file": None,
                    "pipeline": [[sys.executable, "-c", "while True: print('y' * 50)"]]}
            started = time.time()
            self.assertEqual(pager.load(spec)[-1], "\u2026")
            self.assertLess(time.time() - started, 5)


class Keys(unittest.TestCase):
    def setUp(self):
        self.pager = pager.Pager([f"line {i:03d}" for i in range(1, 101)], "lines.txt")
        self.pager.height = 10

    def press(self, *keys):
        for key in keys:
            self.pager.handle(Key("char", key) if len(key) == 1 else Key(key))

    def search(self, text):
        self.press("/", *text, "enter")

    def test_n_and_shift_n_step_through_the_hits(self):
        self.search("line 05")
        self.assertEqual(self.pager.lines[self.pager.top + pager.CONTEXT], "line 050")
        self.press("n")
        self.assertEqual(self.pager.lines[self.pager.top + pager.CONTEXT], "line 051")
        self.press("N")
        self.assertEqual(self.pager.lines[self.pager.top + pager.CONTEXT], "line 050")

    def test_a_search_that_finds_nothing_says_so(self):
        self.search("nowhere")
        self.assertIn("not found", self.pager.status())
        self.press("j")
        self.assertNotIn("not found", self.pager.status())

    def test_the_status_line_is_the_title_and_the_position(self):
        self.assertEqual(self.pager.status().split(), ["lines.txt", "1-10/100"])


class Written(FakeTerminal):
    """A terminal that keeps what is written to it."""

    def __init__(self, cols, rows):
        super().__init__(cols, rows)
        self.out = ""

    def write(self, data):
        self.out += data


class Pictures(unittest.TestCase):
    """An image or a PDF's page drawn in the preview tab with the Kitty graphics protocol (herdr passes it to Ghostty):
    fitted to the pane, never past its own size, centered; a PDF paged with the pager's keys, o opening the browser."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, XDG_CACHE_HOME=os.path.join(self.tmp, "cache"))

    def test_a_picture_fits_the_pane_and_keeps_its_aspect_centered(self):
        self.assertEqual(pager.fit(80, 23, 4000, 2000), (2, 0, 80, None))          # as wide as the pane
        self.assertEqual(pager.fit(80, 23, 1000, 4000), (0, 34, None, 23))         # as tall as it
        self.assertEqual(pager.fit(80, 23, 160, 80), (10, 35, 10, None))           # a small one at its own size

    def test_a_pane_resized_while_a_picture_is_drawn_is_drawn_again(self):
        """Making a PDF's page takes a moment: a preview tab's pane narrowed meanwhile is drawn again, at its width."""
        term, widths = Written(60, 38), []

        class Slow:
            def shown(self):
                return ()

            def draw(self, term_):
                widths.append(term_.size()[0])
                term.cols = 50                                       # the column copied in beside it

        view = Slow()
        drawn = pager.redraw(view, term, None)
        drawn = pager.redraw(view, term, drawn)
        pager.redraw(view, term, drawn)
        self.assertEqual(widths, [60, 50])

    def test_a_narrow_pane_leaves_the_key_hint_out_rather_than_cut(self):
        status = "docs/pagination.pdf  page 1 of 3  o: open in browser"
        self.assertEqual(pager.bar(status, 80).strip(), status)
        self.assertEqual(pager.bar(status, 49).strip(), "docs/pagination.pdf  page 1 of 3")

    def test_a_tall_picture_is_made_big_enough_to_fill_the_panes_height(self):
        picture = pager.Picture(png(os.path.join(self.tmp, "tall.png"), 1000, 3000), "tall.png")
        self.addCleanup(picture.close, Written(46, 38))
        self.assertGreaterEqual(media.size(picture.png(46, 37))[1], round(37 * pager.CELL_PX * pager.CELL))

    def test_an_image_goes_out_in_chunks_with_its_place(self):
        shot = png(os.path.join(self.tmp, "shot.png"), 400, 300)
        term = Written(80, 24)
        picture = pager.Picture(shot, "shot.png")
        self.addCleanup(picture.close, term)
        picture.draw(term)
        self.assertIn("\x1b_Ga=T,f=100,", term.out)
        self.assertTrue(all(len(chunk) <= 4096 for chunk in re.findall(r";([A-Za-z0-9+/=]*)\x1b\\", term.out)))
        self.assertIn("shot.png", term.out)

    def test_a_pager_that_draws_no_pictures_shows_the_file_as_binary(self):
        """A preview tab opened before an update keeps its older pager: the picture's spec is a file to it."""
        spec = preview.file_spec(self.tmp, png(os.path.join(self.tmp, "shot.png"), 40, 30), None)
        self.assertEqual(pager.load({key: value for key, value in spec.items() if key != "picture"}),
                         pager.load({"file": spec["picture"]}))

    def test_over_ssh_a_picture_offers_no_browser(self):
        set_env(self, SSH_CONNECTION="the client and this machine")
        picture = pager.Picture(png(os.path.join(self.tmp, "shot.png"), 40, 30), "shot.png")
        self.addCleanup(picture.close, Written(80, 24))
        self.assertNotIn("o:", picture.status())
        with mock.patch.object(pager.media, "open_in_browser", return_value=True) as opened:
            picture.handle(Key("char", "o"))
        opened.assert_not_called()

    def test_o_opens_it_in_the_browser_and_q_closes_it(self):
        set_env(self, SSH_CONNECTION=None, SSH_CLIENT=None)
        picture = pager.Picture(png(os.path.join(self.tmp, "shot.png"), 40, 30), "shot.png")
        self.addCleanup(picture.close, Written(80, 24))
        with mock.patch.object(pager.media, "open_in_browser", return_value=True) as opened:
            self.assertTrue(picture.handle(Key("char", "o")))
        opened.assert_called_once_with(os.path.join(self.tmp, "shot.png"))
        self.assertFalse(picture.handle(Key("char", "q")))

    @unittest.skipUnless(sys.platform == "darwin", "sips: macOS")
    def test_c_turns_an_svg_between_its_picture_and_its_code(self):
        svg = os.path.join(self.tmp, "logo.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40">\n<rect width="60" height="40"/>\n'
                    '</svg>\n')
        view = pager.viewer(preview.file_spec(self.tmp, svg, None, which=tools()))
        term = Written(80, 24)
        self.addCleanup(view.close, term)
        view.draw(term)
        self.assertIn("\x1b_G", term.out)                                       # the picture
        self.assertIn("c: code", view.status())
        self.assertTrue(view.handle(Key("char", "c")))
        term.out = ""
        view.draw(term)
        self.assertIn(pager.GONE, term.out)                                    # the picture taken off for the code
        self.assertIn("<rect", term.out)
        self.assertIn("c: picture", view.status())
        view.handle(Key("char", "c"))
        self.assertIn("c: code", view.status())

    @unittest.skipUnless(sys.platform == "darwin", "sips: macOS")
    def test_a_wide_pane_shows_the_code_and_the_picture_side_by_side(self):
        svg = os.path.join(self.tmp, "logo.svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40">\n<rect width="60" height="40"/>\n'
                    '</svg>\n')
        view = pager.viewer(preview.file_spec(self.tmp, svg, None, which=tools()))
        term = Written(140, 30)
        self.addCleanup(view.close, term)
        view.draw(term)
        self.assertIn("<rect", term.out)                                       # the code, on the left
        self.assertIn("\x1b_G", term.out)                                      # the picture, on the right
        self.assertIn("│", term.out)
        self.assertNotIn("c: ", view.status())                                 # both shown: nothing to turn to

    def test_a_closed_tab_takes_the_pictures_files_away(self):
        """herdr ends a closed tab's pane with a hang-up: the picture's folder goes all the same."""
        temp = os.path.join(self.tmp, "temp")
        os.makedirs(temp)
        shot = png(os.path.join(self.tmp, "shot.png"), 40, 30)
        path = os.path.join(self.tmp, "preview-w1.json")
        with open(path, "w") as f:
            json.dump({"title": "shot.png", "line": None, "file": shot, "pipeline": [], "picture": shot}, f)
        pid, fd = pty.fork()
        if pid == 0:
            own = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
            os.execve(sys.executable, [sys.executable, os.path.join(SRC, "plugins", "sidebar", "pager.py")],
                      {**own, "TMPDIR": temp, "HERDR_FOLD_SPEC_FILE": path})
        made = lambda: [name for name in os.listdir(temp) if name.startswith("herdr-fold-picture.")]   # noqa: E731

        hung_up, done, end = False, 0, time.monotonic() + 10
        while time.monotonic() < end and not done:
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    os.read(fd, 65536)
                except OSError:
                    pass
            if made() and not hung_up:
                os.kill(pid, signal.SIGHUP)
                hung_up = True
            elif hung_up:
                done = os.waitpid(pid, os.WNOHANG)[0]
        if not done:
            os.kill(pid, signal.SIGKILL)                                   # its own: never left running
            os.waitpid(pid, 0)
        os.close(fd)
        self.assertTrue(hung_up)
        self.assertEqual(made(), [])

    def test_closing_takes_the_picture_and_its_files_away(self):
        picture = pager.Picture(png(os.path.join(self.tmp, "shot.png"), 40, 30), "shot.png")
        term = Written(80, 24)
        picture.draw(term)
        picture.close(term)
        self.assertIn("\x1b_Ga=d,", term.out)
        self.assertFalse(os.path.exists(picture.work))

    def test_a_pdf_says_it_opens_before_its_pages_are_counted(self):
        """Its first one compiles the PDF helper, for a few seconds: the pane says so meanwhile."""
        term = Written(80, 24)
        picture = pager.Picture(os.path.join(self.tmp, "a.pdf"), "a.pdf")
        self.addCleanup(picture.close, term)
        with mock.patch.object(pager.media, "pages", side_effect=lambda path: self.assertIn("Opening", term.out)) as n:
            picture.draw(term)
        n.assert_called_once()

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"), "PDFKit and swiftc: macOS")
    def test_a_pdf_pages_with_the_pagers_keys(self):
        picture = pager.Picture(pdf(os.path.join(self.tmp, "three.pdf"), 3), "three.pdf")
        term = Written(80, 24)
        self.addCleanup(picture.close, term)
        picture.draw(term)
        self.assertIn("page 1 of 3", picture.status())
        for key, page in (("down", 2), ("G", 3), ("up", 2), ("g", 1), ("pageup", 1)):
            picture.handle(Key("char", key) if len(key) == 1 else Key(key))
            self.assertIn(f"page {page} of 3", picture.status())


def run_pager(spec, keys, folder, env=None):
    """pager.py with SPEC (written to a file in FOLDER) in a pty; KEYS are typed one after another, a dict written to
    the file instead. Returns what it showed, and whether it ended."""
    path = os.path.join(folder, "preview-w1.json")
    with open(path, "w") as f:
        json.dump(spec, f)
    pid, fd = pty.fork()
    if pid == 0:
        # never the herdr this may run in: q would close that one's tab
        own = {key: value for key, value in os.environ.items() if not key.startswith("HERDR_")}
        os.execve(sys.executable, [sys.executable, os.path.join(SRC, "plugins", "sidebar", "pager.py")],
                  {**own, **(env or {}), "HERDR_FOLD_SPEC_FILE": path})
    out = b""
    for key in [b""] + keys:
        time.sleep(0.5)
        if isinstance(key, dict):
            with open(path + ".new", "w") as f:
                json.dump(key, f)
            os.replace(path + ".new", path)
        else:
            os.write(fd, key)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    ended = end_child(pid, fd, grace=2.0) is not None
    return out.decode("utf-8", "replace"), ended


class Pager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.file = os.path.join(self.tmp, "lines.txt")
        with open(self.file, "w") as f:
            f.write("".join(f"line {i:03d}\n" for i in range(1, 101)))

    def test_it_opens_at_the_line_searches_and_quits(self):
        spec = {"title": "lines.txt", "line": 40, "file": self.file, "pipeline": []}
        shown, ended = run_pager(spec, [b"/line 090\r", b"q"], self.tmp)
        first = shown.split("line 090")[0]
        self.assertIn("line 040", first)
        self.assertNotIn("line 001", first)
        self.assertIn("line 090", shown)
        self.assertTrue(ended)

    def test_a_pipeline_is_paged(self):
        spec = {"title": "echo", "line": None, "file": None,
                "pipeline": [[sys.executable, "-c", "print('from the pipeline')"]]}
        shown, ended = run_pager(spec, [b"q"], self.tmp)
        self.assertIn("from the pipeline", shown)
        self.assertTrue(ended)

    def test_a_new_one_written_to_its_file_is_shown(self):
        first = {"title": "echo", "line": None, "file": None, "pipeline": [[sys.executable, "-c", "print('first')"]]}
        second = {"title": "lines.txt", "line": 60, "file": self.file, "pipeline": []}
        shown, ended = run_pager(first, [second, b"q"], self.tmp)
        self.assertIn("first", shown)
        self.assertIn("line 060", shown.split("first", 1)[1])
        self.assertTrue(ended)

    def test_q_closes_the_preview_tab_and_forgets_what_it_showed(self):
        log = os.path.join(self.tmp, "log")
        herdr = os.path.join(stubs(os.path.join(self.tmp, "bin"), {"herdr": FAKE_HERDR}), "herdr")
        spec = {"title": "lines.txt", "line": None, "file": self.file, "pipeline": []}
        _, ended = run_pager(spec, [b"q"], self.tmp, {"HERDR_BIN_PATH": herdr, "HERDR_TAB_ID": "w1:t2",
                                                     "HERDR_LOG": log})
        self.assertTrue(ended)
        with open(log) as f:
            self.assertEqual(f.read().splitlines(), ["tab close w1:t2"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "preview-w1.json")))


if __name__ == "__main__":
    unittest.main()
