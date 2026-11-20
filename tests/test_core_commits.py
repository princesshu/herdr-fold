"""Tests for core/commits.py and the report's commits in a temporary HOME with a temporary repository: the commits a
conversation made itself and the ones that followed its edits, each file read once, git only read and run with no
program the repository's config names. The sessions are invented; git runs without the user's own config."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from support import PACKAGE, set_attrs, set_env, sign_head, trap

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import commits  # noqa: E402
import report  # noqa: E402
import test_core_report as used  # noqa: E402
import test_core_tokens as made  # noqa: E402
import tokens  # noqa: E402

DAY, HOUR = 86400, 3600
NOW = used.NOW                  # Thursday, 12 November 2026, 12:00 UTC
TENTH = NOW - 2 * DAY - 2 * HOUR                # Tuesday the 10th, 10:00 UTC
SESSION, OTHER, THREAD = made.SESSION, made.OTHER, made.THREAD


def stamp(at):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(at))


def edit(path, at, tool="Edit", session=SESSION, id="msg_e1"):
    """Claude's call that changes PATH, as a session's line."""
    given = {"file_path": path, "content": "x"} if tool == "Write" else \
        {"file_path": path, "old_string": "a", "new_string": "b"}
    return made.line({"parentUuid": None, "isSidechain": False, "type": "assistant", "timestamp": stamp(at),
                      "sessionId": session,
                      "message": {"model": used.OPUS, "id": id, "type": "message", "role": "assistant",
                                  "content": [{"type": "tool_use", "id": "toolu_01", "name": tool, "input": given}]}})


def ran(output, at, session=SESSION):
    """A Bash call's result, as a session's line: what git commit printed."""
    return made.line({"parentUuid": None, "isSidechain": False, "type": "user", "timestamp": stamp(at),
                      "sessionId": session,
                      "message": {"role": "user", "content": [{"tool_use_id": "toolu_02", "type": "tool_result",
                                                               "content": output, "is_error": False}]},
                      "toolUseResult": {"stdout": output, "stderr": "", "interrupted": False, "isImage": False}})


def committed(sha, branch="main", words="Fix the last page"):
    return f"[{branch} {sha[:7]}] {words}\n 1 file changed, 2 insertions(+), 1 deletion(-)"


class Repo(made.Home):
    """A home, and a repository with src/books.py committed on the 9th."""

    def setUp(self):
        super().setUp()
        set_env(self, TZ="UTC", HERDR_FOLD_NO_UPDATE_CHECK="1", HERDR_PLUGIN_STATE_DIR=None,
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="dev",
                GIT_AUTHOR_EMAIL="dev@example.com", GIT_COMMITTER_NAME="dev", GIT_COMMITTER_EMAIL="dev@example.com")
        time.tzset()
        self.addCleanup(time.tzset)
        self.repo = os.path.join(os.path.realpath(self.home), "lumen-api")
        self.books = os.path.join(self.repo, "src", "books.py")
        os.makedirs(os.path.dirname(self.books))
        self.git("init", "-q", "-b", "main")
        self.first = self.commit({"src/books.py": "a\nb\n", "README.md": "lumen\n"}, TENTH - DAY)

    def git(self, *args, at=None):
        env = {**os.environ, **({"GIT_AUTHOR_DATE": f"{at} +0000", "GIT_COMMITTER_DATE": f"{at} +0000"} if at else {})}
        return subprocess.run(["git", "-C", self.repo, *args], capture_output=True, text=True, check=True,
                              env=env).stdout.strip()

    def commit(self, files, at, words="Change"):
        """FILES ({path: text}) committed at AT: the commit's id."""
        for rel, text in files.items():
            path = os.path.join(self.repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        self.git("add", "--", *files)
        self.git("commit", "-q", "-m", words, at=at)
        return self.git("rev-parse", "HEAD")

    def found(self, made=(), edits=None, others=None, **more):
        return commits.commits(self.repo, list(made), edits or {}, others or {}, **more)


class Told(made.Home):
    def test_a_sessions_edits_and_the_commits_its_results_name(self):
        path = self.session(
            made.asked() + edit("/Users/dev/lumen-api/src/books.py", TENTH)
            + edit("/Users/dev/lumen-api/src/pages.py", TENTH + 60, "Write")
            + edit("/Users/dev/lumen-api/src/books.py", TENTH + 120, "MultiEdit")
            + ran(committed("a1b2c3d4e5"), TENTH + 180)
            + ran("[detached HEAD 0f9e8d7] Try\n 2 files changed, 9 insertions(+)", TENTH + 240)
            + ran("[main (root-commit) 1a2b3c4] Start\n 1 file changed, 1 insertion(+)", TENTH + 300))
        edits, named, offset = commits.told(path)
        self.assertEqual(edits, [(TENTH, "/Users/dev/lumen-api/src/books.py"),
                                 (TENTH + 60, "/Users/dev/lumen-api/src/pages.py"),
                                 (TENTH + 120, "/Users/dev/lumen-api/src/books.py")])
        self.assertEqual((named, offset), (["a1b2c3d", "0f9e8d7", "1a2b3c4"], os.path.getsize(path)))

    def test_what_only_looks_like_one_is_not_read(self):
        shown = {"type": "user", "timestamp": stamp(TENTH),
                 "toolUseResult": {"file": {"content": committed("a1b2c3d")}},
                 "message": {"role": "user", "content": [{"type": "tool_result", "content": committed("a1b2c3d")}]}}
        blob = {"type": "api-request-blob", "timestamp": stamp(TENTH),
                "body": json.loads(edit("/Users/dev/lumen-api/a.py", TENTH))["message"]}
        relative = edit("src/books.py", TENTH)
        other = json.loads(edit("/Users/dev/lumen-api/a.py", TENTH))
        other["message"]["content"][0]["name"] = "Read"
        path = self.session(made.line(shown) + made.line(blob) + relative + made.line(other)
                            + ran("see [main a1b2c3d] in the log, 1 file changed", TENTH)
                            + ran("[main A1B2C3D] Shout\n 1 file changed", TENTH)
                            + edit("/Users/dev/lumen-api/b.py", TENTH)[:-9])       # still being written
        edits, named, offset = commits.told(path)
        self.assertEqual((edits, named), ([], []))
        self.assertLess(offset, os.path.getsize(path))

    def test_a_sub_agents_file_is_its_parents_session(self):
        self.session(edit("/Users/dev/lumen-api/a.py", TENTH))
        self.sub(edit("/Users/dev/lumen-api/b.py", TENTH + 60) + ran(committed("a1b2c3d"), TENTH + 90))
        self.assertEqual(commits.index(self.state, self.home)["files"], 2)
        self.assertEqual(commits.sessions(commits.load(self.state)), {SESSION: {
            "edits": {"/Users/dev/lumen-api/a.py": [TENTH], "/Users/dev/lumen-api/b.py": [TENTH + 60]},
            "made": ["a1b2c3d"]}})


class Index(made.Home):
    def test_a_file_is_read_on_from_where_it_stopped(self):
        path = self.session(edit("/Users/dev/lumen-api/a.py", TENTH))
        first = commits.index(self.state, self.home)
        self.assertEqual((first["files"], first["read"], first["left"]), (1, os.path.getsize(path), 0))
        self.assertEqual(commits.index(self.state, self.home)["read"], 0)
        more = edit("/Users/dev/lumen-api/a.py", TENTH + 60) + ran(committed("a1b2c3d"), TENTH + 90)
        self.session(more, mode="a")
        self.assertEqual(commits.index(self.state, self.home)["read"], len(more))
        self.assertEqual(commits.sessions(commits.load(self.state))[SESSION],
                         {"edits": {"/Users/dev/lumen-api/a.py": [TENTH, TENTH + 60]}, "made": ["a1b2c3d"]})

    def test_a_file_gone_is_dropped_and_one_begun_anew_read_again(self):
        path = self.session(edit("/Users/dev/lumen-api/a.py", TENTH) + edit("/Users/dev/lumen-api/b.py", TENTH))
        other = self.session(edit("/Users/dev/lumen-api/c.py", TENTH, session=OTHER), session=OTHER)
        commits.index(self.state, self.home)
        os.unlink(other)
        self.session(edit("/Users/dev/lumen-api/d.py", TENTH))
        commits.index(self.state, self.home)
        self.assertEqual(commits.sessions(commits.load(self.state)),
                         {SESSION: {"edits": {"/Users/dev/lumen-api/d.py": [TENTH]}, "made": []}})
        self.assertEqual(list(commits.load(self.state)["files"]), [path])

    def test_only_the_index_is_written_its_owners_only(self):
        self.session(edit("/Users/dev/lumen-api/a.py", TENTH))

        def tree():
            return sorted(os.path.join(folder, name) for folder, _, names in os.walk(self.home) for name in names)
        before = tree()
        commits.index(self.state, self.home)
        kept = os.path.join(self.state, "commits-index.json")
        self.assertEqual(sorted(set(tree()) - set(before)), [kept, kept + ".lock"])
        self.assertEqual(os.stat(kept).st_mode & 0o777, 0o600)

    def test_a_damaged_index_or_another_versions_is_none(self):
        self.session(edit("/Users/dev/lumen-api/a.py", TENTH))
        commits.index(self.state, self.home)
        kept = os.path.join(self.state, "commits-index.json")
        with open(kept, encoding="utf-8") as f:
            index = json.load(f)
        for text in ("{", "[]", json.dumps({**index, "version": 0}),
                     json.dumps({"version": 1, "files": {"a": {"offset": "0"}, "b": 7,
                                                         "c": {"offset": 0, "session": "s", "edits": [], "made": []},
                                                         "d": {"offset": 0, "session": "s", "edits": {"p": ["x"]},
                                                               "made": []}}})):
            with self.subTest(text=text[:20]):
                with open(kept, "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertEqual(commits.load(self.state), {"version": 1, "files": {}, "lines": {}})

    def test_the_cli_brings_it_up_to_date(self):
        self.session(edit("/Users/dev/lumen-api/a.py", TENTH))
        done = subprocess.run([sys.executable, os.path.join(PACKAGE, "core", "commits.py"), "index"],
                              capture_output=True, text=True, env={**os.environ, "HOME": self.home}, timeout=60)
        self.assertEqual((done.returncode, json.loads(done.stdout)["files"], done.stderr), (0, 1, ""))
        self.assertEqual(subprocess.run([sys.executable, os.path.join(PACKAGE, "core", "commits.py")],
                                        capture_output=True, env={**os.environ, "HOME": self.home}).returncode, 2)


class Found(Repo):
    def test_a_commit_made_in_the_conversation(self):
        sha = self.commit({"src/books.py": "a\nc\nd\n"}, TENTH + 600)
        self.assertEqual(self.found([sha[:7]]),
                         [{"sha": sha, "added": 2, "removed": 1, "at": TENTH + 600, "how": "made"}])

    def test_a_commit_named_that_this_repository_does_not_have_is_not_counted(self):
        sha = self.commit({"src/books.py": "a\nc\n"}, TENTH + 600)
        self.assertEqual([one["sha"] for one in self.found(["0f9e8d7", sha[:7], "--all", sha[:7]])], [sha])

    def test_a_commit_by_hand_after_its_edit(self):
        sha = self.commit({"src/books.py": "a\nc\nd\ne\n", "bin.dat": "\0\1"}, TENTH + 5 * HOUR)
        self.assertEqual(self.found(edits={self.books: [TENTH, TENTH + HOUR]}),
                         [{"sha": sha, "added": 3, "removed": 1, "at": TENTH + 5 * HOUR, "how": "after"}])

    def test_a_commit_that_touched_none_of_its_files_is_not_counted(self):
        self.commit({"README.md": "lumen-api\n"}, TENTH + HOUR)
        self.assertEqual(self.found(edits={self.books: [TENTH]}), [])
        self.assertEqual(self.found(edits={os.path.join(self.home, "elsewhere", "README.md"): [TENTH]}), [])

    def test_a_commit_before_the_edit_or_past_a_day_after_it_is_not_counted(self):
        self.commit({"src/books.py": "a\nc\n"}, TENTH - HOUR)
        late = self.commit({"src/books.py": "a\nd\n"}, TENTH + DAY + 60)
        self.assertEqual(self.found(edits={self.books: [TENTH]}), [])
        self.assertEqual([one["sha"] for one in self.found(edits={self.books: [TENTH, TENTH + HOUR]})], [late])

    def test_a_file_another_conversation_edited_since_is_that_ones(self):
        sha = self.commit({"src/books.py": "a\nc\n"}, TENTH + 3 * HOUR)
        mine, theirs = {self.books: [TENTH]}, {self.books: [TENTH + HOUR]}
        self.assertEqual(self.found(edits=mine, others=theirs), [])
        self.assertEqual([one["sha"] for one in self.found(edits=theirs, others=mine)], [sha])
        self.assertEqual([one["sha"] for one in self.found(edits=mine, others={self.books: [TENTH - HOUR,
                                                                                               TENTH + 4 * HOUR]})],
                         [sha])

    def test_a_commit_it_made_and_that_followed_its_edit_is_one_made(self):
        sha = self.commit({"src/books.py": "a\nc\n"}, TENTH + 600)
        hand = self.commit({"src/books.py": "a\nd\n"}, TENTH + HOUR)
        self.assertEqual([(one["sha"], one["how"]) for one in self.found([sha[:7]], {self.books: [TENTH]})],
                         [(sha, "made"), (hand, "after")])

    def test_a_commit_on_another_branch_counts_and_a_stash_does_not(self):
        self.git("checkout", "-q", "-b", "spike")
        sha = self.commit({"src/books.py": "a\nc\n"}, TENTH + HOUR)
        self.git("checkout", "-q", "main")
        with open(self.books, "w", encoding="utf-8") as f:
            f.write("a\nz\n")
        self.git("stash", at=TENTH + 2 * HOUR)
        self.assertEqual([one["sha"] for one in self.found(edits={self.books: [TENTH]})], [sha])

    def test_only_the_time_asked_for(self):
        early = self.commit({"src/books.py": "a\nc\n"}, TENTH + HOUR)
        late = self.commit({"src/books.py": "a\nd\n"}, TENTH + 3 * HOUR)
        found = self.found([early[:7], late[:7]], {self.books: [TENTH]}, since=TENTH + 2 * HOUR, until=TENTH + DAY)
        self.assertEqual([one["sha"] for one in found], [late])

    def test_no_git_and_no_repository_are_not_known(self):
        self.assertIsNone(commits.commits(self.home, [], {self.books: [TENTH]}, {}))
        self.assertIsNone(commits.commits(os.path.join(self.home, "gone"), ["a1b2c3d"], {}, {}))
        set_attrs(self, commits, GIT=os.path.join(self.home, "no-git"))
        self.assertIsNone(self.found(edits={self.books: [TENTH]}))

    def test_nothing_the_repositorys_config_names_runs_and_nothing_is_written(self):
        sha = self.commit({"src/books.py": "a\nc\n"}, TENTH + HOUR)
        sign_head(self.repo)
        programs = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, programs)
        marks = [trap(self.repo, key, programs) for key in ("core.fsmonitor", "diff.external", "gpg.program",
                                                            "core.pager")]
        self.git("config", "log.showSignature", "true")
        head = self.git("rev-parse", "HEAD")

        def tree():
            return {os.path.join(folder, name): os.stat(os.path.join(folder, name)).st_mtime_ns
                    for folder, _, names in os.walk(self.repo) for name in names}
        before = tree()
        found = self.found([sha[:7], head[:7]], {self.books: [TENTH]})
        self.assertEqual(sorted(one["sha"] for one in found), sorted([sha, head]))
        self.assertEqual([mark for mark in marks if os.path.exists(mark)], [])
        self.assertEqual(tree(), before)


class Reported(Repo):
    """The repository's conversations in the report: one that edited books.py and committed, one that only read, and a
    Codex one."""

    def setUp(self):
        super().setUp()
        self.made = self.commit({"src/books.py": "a\nc\nd\n"}, TENTH + 600, "Fix the last page")
        self.hand = self.commit({"src/books.py": "a\nc\nd\ne\nf\ng\n"}, TENTH + 5 * HOUR)
        self.session(used.said("msg_01", stamp(TENTH), folder=self.repo, input=200_000) + edit(self.books, TENTH + 60)
                     + ran(committed(self.made), TENTH + 600))
        self.write(f".claude/projects/-Users-dev-lumen-api/{OTHER}.jsonl",
                   used.said("msg_02", stamp(TENTH + HOUR), session=OTHER, folder=self.repo, input=100_000))
        self.write(f".codex/sessions/2026/11/10/rollout-2026-11-10T10-00-00-{THREAD}.jsonl",
                   used.meta(self.repo) + used.turn(used.GPT, "turn-1", stamp(TENTH), self.repo)
                   + used.record("resp_01", stamp(TENTH), input_tokens=100_000))
        tokens.index(self.state, self.home)

    def report(self, period="7d", **more):
        return report.report(self.state, self.home, period, now=NOW, agents=used.AGENTS, table=used.TABLE, **more)

    def rows(self, found):
        return {one["session"]: {key: one[key] for key in ("commits", "about", "commits_text", "added", "removed",
                                                           "changed", "per_commit", "commits_tip")}
                for one in found["conversations"]}

    def test_a_conversations_commits_its_lines_and_what_one_cost(self):
        commits.index(self.state, self.home)
        found = self.report()
        rows = self.rows(found)
        self.assertEqual(rows[SESSION], {"commits": 2, "about": True, "commits_text": "about 2", "added": 5,
                                         "removed": 1, "changed": "+5 −1", "per_commit": 1.0,
                                         "commits_tip": "1 made in the conversation · 1 after its edits"})
        self.assertEqual(rows[OTHER], {"commits": 0, "about": False, "commits_text": "none yet", "added": 0,
                                       "removed": 0, "changed": "", "per_commit": None, "commits_tip": ""})
        self.assertEqual(rows[THREAD], {"commits": None, "about": False, "commits_text": "–", "added": None,
                                        "removed": None, "changed": "", "per_commit": None, "commits_tip": ""})
        self.assertEqual(found["summary"][-1], {"key": "Commits from these conversations", "value": 2,
                                                "text": "about 2", "about": True, "line": "~$2.00 each, API value"})
        self.assertEqual([(one["name"], one["commits"]) for one in found["projects"]], [("lumen-api", 2)])

    def test_only_its_own_commits_are_not_about(self):
        self.git("reset", "-q", "--hard", self.made)
        self.git("reflog", "expire", "--expire=now", "--all")
        commits.index(self.state, self.home)
        found = self.report(agent="claude")
        self.assertEqual(self.rows(found)[SESSION]["commits_text"], "1")
        self.assertEqual(found["summary"][-1]["text"], "1")
        self.assertEqual(found["summary"][-1]["line"], "~$3.00 each, API value")

    def test_with_an_api_key_alone_a_commits_cost_is_spent(self):
        commits.index(self.state, self.home)
        keys = [{"key": "claude", "plan": "API key"}, {"key": "codex", "plan": "API key"}]
        found = report.report(self.state, self.home, "7d", now=NOW, agents=keys, table=used.TABLE)
        self.assertEqual(found["summary"][-1]["line"], "~$2.00 each, spent")

    def test_a_commit_outside_the_period_is_not_in_it(self):
        commits.index(self.state, self.home)
        self.session(used.said("msg_09", stamp(NOW - HOUR), folder=self.repo, input=100_000), mode="a")
        tokens.index(self.state, self.home)
        commits.index(self.state, self.home)
        found = self.report("today")
        self.assertEqual(self.rows(found)[SESSION]["commits_text"], "none yet")
        self.assertEqual(found["summary"][-1], {"key": "Commits from these conversations", "value": 0,
                                                "text": "none yet", "about": False, "line": ""})

    def test_sessions_not_read_yet_and_a_folder_that_is_no_repository_are_not_known(self):
        found = self.report()                           # commits.index() has not run
        self.assertEqual({one["commits_text"] for one in found["conversations"]}, {"–"})
        self.assertEqual(found["summary"][-1], {"key": "Commits from these conversations", "value": None,
                                                "text": "–", "about": False, "line": ""})
        self.assertEqual(found["projects"][0]["commits"], None)
        commits.index(self.state, self.home)
        shutil.rmtree(os.path.join(self.repo, ".git"))
        self.assertEqual({one["commits_text"] for one in self.report()["conversations"]}, {"–"})

    def test_a_conversation_started_above_its_repository_is_found_by_the_files_it_edited(self):
        above, session = os.path.dirname(self.repo), "9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
        late = self.commit({"README.md": "lumen-api\n"}, TENTH + 7 * HOUR)
        self.write(f".claude/projects/-Users-dev/{session}.jsonl",
                   used.said("msg_05", stamp(TENTH + 6 * HOUR), session=session, folder=above, input=100_000)
                   + edit(os.path.join(self.repo, "README.md"), TENTH + 6 * HOUR + 60, session=session)
                   + edit(os.path.join(above, "notes", "plan.md"), TENTH + 6 * HOUR + 90, session=session))
        tokens.index(self.state, self.home)
        commits.index(self.state, self.home)
        found = self.report()
        self.assertEqual(self.rows(found)[session]["commits_text"], "about 1")
        self.assertEqual(found["summary"][-1]["value"], 3)
        self.assertEqual(commits.found(commits.sessions(commits.load(self.state)), {session: above}, TENTH,
                                       TENTH + DAY)[session],
                         [{"sha": late, "added": 1, "removed": 1, "at": TENTH + 7 * HOUR, "how": "after"}])

    def test_a_commits_lines_are_counted_once_and_kept(self):
        commits.index(self.state, self.home)
        first = self.report()
        self.assertEqual(commits.load(self.state)["lines"], {self.made: [TENTH + 600, 2, 1],
                                                             self.hand: [TENTH + 5 * HOUR, 3, 0]})
        ran_, run = [], commits.run
        set_attrs(self, commits, run=lambda repo, *args, **more: ran_.append(args[0]) or run(repo, *args, **more))
        self.assertEqual(self.report()["conversations"], first["conversations"])
        self.assertEqual(sorted(ran_), ["cat-file", "log"])
        self.session(edit(self.books, NOW - HOUR), mode="a")
        commits.index(self.state, self.home)            # the sessions read on: the lines stay
        self.assertEqual(sorted(commits.load(self.state)["lines"]), sorted([self.made, self.hand]))

    def test_lines_kept_in_another_shape_are_counted_again(self):
        commits.index(self.state, self.home)
        kept = os.path.join(self.state, "commits-index.json")
        with open(kept, encoding="utf-8") as f:
            index = json.load(f)
        with open(kept, "w", encoding="utf-8") as f:
            json.dump({**index, "lines": {self.made: [TENTH, "2", 1], "main": [TENTH, 9, 9], self.hand: [1, 2]}}, f)
        self.assertEqual(commits.load(self.state)["lines"], {})
        self.assertEqual(self.rows(self.report())[SESSION]["changed"], "+5 −1")

    def test_the_report_runs_git_once_a_repository_not_once_a_conversation(self):
        commits.index(self.state, self.home)
        ran_, run = [], commits.run
        set_attrs(self, commits, run=lambda repo, *args, **more: ran_.append(args[0]) or run(repo, *args, **more))
        self.report()
        self.assertEqual(sorted(ran_), ["cat-file", "log", "log"])
