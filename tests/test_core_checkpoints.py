"""Tests for core/checkpoints.py in a temporary HOME: a Claude chat's checkpoints read from its file (lines built the
way Claude writes them), Claude's dry run and --rewind-files asked as the Agent SDK asks them, and the one Undo. A
stand-in answers for claude; the chat, its folder and its files are invented."""
import contextlib
import io
import json
import os
import sys

from support import PACKAGE, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import checkpoints  # noqa: E402
from test_core_tokens import SESSION, Home, line, stamp  # noqa: E402

FIRST, FIX, TEST, NOTE = ("1a2b3c4d-0001-4a5b-8c6d-7e8f9a0b1c2d", "1a2b3c4d-0002-4a5b-8c6d-7e8f9a0b1c2d",
                          "1a2b3c4d-0003-4a5b-8c6d-7e8f9a0b1c2d", "1a2b3c4d-0004-4a5b-8c6d-7e8f9a0b1c2d")
# a stand-in for claude: logs how it was run; answers the dry run's request by the message it names, and takes
# --rewind-files by writing and removing what its plan says (or failing with its words)
STAND_IN = "\n".join([
    "#!/usr/bin/python3 -B", "import json, os, sys",
    "with open(os.environ['CHECKPOINTS_LOG'], 'a') as f:",
    "    f.write(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:],",
    "                        'flag': os.environ.get('CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING')}) + '\\n')",
    "plan = json.load(open(os.environ['CHECKPOINTS_PLAN']))",
    "if '--rewind-files' in sys.argv:",
    "    if plan.get('error'):",
    "        sys.stderr.write('Error: ' + plan['error'] + '\\n'); sys.exit(1)",
    "    for path, text in plan['write'].items():",
    "        open(path, 'w').write(text)",
    "    for path in plan['remove']:",
    "        os.remove(path)",
    "    print('Files rewound to state at message ' + sys.argv[-1]); sys.exit(0)",
    "asked = json.loads(sys.stdin.readline())",
    "point = asked['request']['user_message_id']",
    "print(json.dumps({'type': 'system', 'subtype': 'init'}))",
    "print(json.dumps({'type': 'control_response', 'response': {'subtype': 'success',",
    "    'request_id': asked['request_id'], 'response': plan['ask'].get(point,",
    "    {'canRewind': False, 'error': 'No file checkpoint found for this message.'})}}))", ""])


def user(uuid, words, minute, **extra):
    return line({"type": "user", "uuid": uuid, "isSidechain": False, "timestamp": stamp(minute),
                 "message": {"role": "user", "content": words}, **extra})


def tool(name, minute, **told):
    return line({"type": "assistant", "isSidechain": False, "timestamp": stamp(minute),
                 "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"t{minute}", "name": name,
                                                               "input": told}]}})


def snapshot(uuid):
    return line({"type": "file-history-snapshot", "messageId": uuid,
                 "snapshot": {"messageId": uuid, "trackedFileBackups": {}}, "isSnapshotUpdate": False})


class Checkpoints(Home):
    def setUp(self):
        super().setUp()
        self.folder = os.path.join(self.home, "lumen-api")
        os.makedirs(os.path.join(self.folder, "tests"))
        self.log, self.plan = os.path.join(self.home, "calls"), os.path.join(self.home, "plan.json")
        programs = stubs(os.path.join(self.home, "bin"), {"claude": STAND_IN})
        set_env(self, PATH=os.pathsep.join([programs, "/usr/bin", "/bin"]), CHECKPOINTS_LOG=self.log,
                CHECKPOINTS_PLAN=self.plan)
        self.books, self.tests, self.paging = (os.path.join(self.folder, rel) for rel in (
            "books.py", "tests/test_books.py", "tests/test_paging.py"))

    def chat(self, *lines):
        first = line({"type": "permission-mode", "permissionMode": "default", "sessionId": SESSION})
        cwd = line({"type": "system", "subtype": "init", "cwd": self.folder, "timestamp": stamp(0)})
        return self.write(f".claude/projects/-lumen-api/{SESSION}.jsonl", first + cwd + "".join(lines))

    def story(self):
        """Four prompts: one reads, one edits books.py and writes test_paging.py and runs the tests, one edits a test
        through a subagent too, one with no snapshot of Claude's (sent while it worked)."""
        return self.chat(
            snapshot(FIRST), user(FIRST, "Read the paging spec in docs/api.md first.", 30),
            tool("Read", 30, file_path=os.path.join(self.folder, "docs/api.md")),
            user("2b3c4d5e-0000-4a5b-8c6d-7e8f9a0b1c2d", [{"type": "tool_result", "tool_use_id": "t30"}], 31),
            snapshot(FIX), user(FIX, "Fix #42: past the last page the API should answer the last page.", 32),
            tool("Edit", 33, file_path=self.books), tool("Edit", 34, file_path=self.books),
            tool("Write", 35, file_path=self.paging, content=""), tool("Bash", 36, command="python3 -m unittest"),
            user("3c4d5e6f-0000-4a5b-8c6d-7e8f9a0b1c2d", "<command-name>/model</command-name>", 37),
            user(TEST, "Add a test for a page below one, too.", 40), snapshot(TEST),
            tool("Agent", 41, prompt="Check the tests"), tool("MultiEdit", 42, file_path=self.tests),
            tool("Bash", 43, command="python3 -m unittest"),
            user("4d5e6f7a-0000-4a5b-8c6d-7e8f9a0b1c2d", "A side question", 44, isSidechain=True),
            user(NOTE, [{"type": "text", "text": "Note it under Unreleased.\nIn CHANGELOG.md."}], 50),
            tool("Edit", 51, file_path=os.path.join(self.folder, "CHANGELOG.md")))

    def answer(self, **plan):
        with open(self.plan, "w") as f:
            json.dump({"ask": {}, "write": {}, "remove": [], **plan}, f)

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [json.loads(row) for row in f]

    def put(self, path, text):
        with open(path, "w") as f:
            f.write(text)

    def read(self, path):
        with open(path) as f:
            return f.read()


class Points(Checkpoints):
    def test_each_prompt_that_starts_a_turn_with_what_its_turn_wrote_and_what_ran_from_it_on(self):
        found = checkpoints.points(self.story())
        self.assertEqual([(p["id"], p["files"], p["bash"], p["agents"], p["kept"]) for p in found], [
            (FIRST, 0, 2, 1, True), (FIX, 2, 2, 1, True), (TEST, 1, 1, 1, True), (NOTE, 1, 0, 0, False)])
        self.assertEqual((found[1]["at"], found[1]["text"]),
                         (stamp(32), "Fix #42: past the last page the API should answer the last page."))
        self.assertEqual(found[3]["text"], "Note it under Unreleased.")

    def test_only_the_newest_hundred_are_kept_as_claude_keeps_them(self):
        ids = [f"5e6f7a8b-{n:04d}-4a5b-8c6d-7e8f9a0b1c2d" for n in range(checkpoints.KEEPS + 2)]
        found = checkpoints.points(self.chat(*(snapshot(one) + user(one, f"Step {n}", 1) for n, one in enumerate(ids))))
        self.assertEqual([p["kept"] for p in found], [False, False] + [True] * checkpoints.KEEPS)

    def test_a_chat_never_restored_has_no_undo_and_a_wrong_id_reads_nothing(self):
        self.story()
        self.assertIsNone(checkpoints.listed(SESSION)["undo"])
        with self.assertRaises(ValueError):
            checkpoints.listed("../etc")


class DryRun(Checkpoints):
    def test_claude_is_asked_as_the_agent_sdk_asks_it_in_the_chats_folder(self):
        self.story()
        self.answer(ask={FIX: {"canRewind": True, "filesChanged": [self.books, self.paging], "insertions": 1,
                               "deletions": 13}})
        self.assertEqual(checkpoints.ask(SESSION, FIX),
                         {"files": [self.books, self.paging], "insertions": 1, "deletions": 13})
        call = self.calls()[0]
        self.assertEqual((call["cwd"], call["flag"]), (os.path.realpath(self.folder), "true"))
        self.assertEqual(call["argv"][call["argv"].index("--resume") + 1], SESSION)
        self.assertIn("stream-json", call["argv"])

    def test_a_point_claude_no_longer_keeps_says_so_in_claudes_words(self):
        self.story()
        self.answer()
        self.assertEqual(checkpoints.ask(SESSION, NOTE), {"error": "No file checkpoint found for this message."})

    def test_what_is_not_a_checkpoint_never_reaches_claude(self):
        self.story()
        self.answer()
        for point in ("--help", "../x", ""):
            self.assertEqual(checkpoints.ask(SESSION, point), {"error": "not a checkpoint"})
        self.assertEqual(self.calls(), [])


class Restore(Checkpoints):
    def setUp(self):
        super().setUp()
        self.story()
        self.put(self.books, "clamped\n")
        self.put(self.paging, "new\n")
        self.answer(ask={FIX: {"canRewind": True, "filesChanged": [self.books, self.paging, self.tests],
                               "insertions": 1, "deletions": 13}},
                    write={self.books: "unclamped\n", self.tests: "one test\n"}, remove=[self.paging])

    def test_the_files_go_back_and_one_undo_puts_them_as_they_were(self):
        self.assertEqual(checkpoints.restore(SESSION, FIX, NOTE), {"files": 3})
        self.assertEqual((self.read(self.books), self.read(self.tests)), ("unclamped\n", "one test\n"))
        self.assertFalse(os.path.exists(self.paging))
        self.assertEqual(self.calls()[-1]["argv"], ["-p", "--resume", SESSION, "--rewind-files", FIX])
        self.assertEqual(checkpoints.undoable(SESSION, NOTE), {"point": FIX, "files": 3})
        self.assertEqual(checkpoints.undo(SESSION), {"files": 3})
        self.assertEqual((self.read(self.books), self.read(self.paging)), ("clamped\n", "new\n"))
        self.assertFalse(os.path.exists(self.tests))            # not there before the restore: gone again
        self.assertEqual(checkpoints.undo(SESSION), {"error": "Nothing to undo"})

    def test_a_prompt_since_the_restore_ends_its_undo(self):
        checkpoints.restore(SESSION, FIX, NOTE)
        self.assertIsNone(checkpoints.undoable(SESSION, "6f7a8b9c-0000-4a5b-8c6d-7e8f9a0b1c2d"))

    def test_claudes_refusal_is_said_in_its_words_and_nothing_is_kept(self):
        self.answer(ask={FIX: {"canRewind": True, "filesChanged": [self.books], "insertions": 0, "deletions": 2}},
                    error="The file backups are still being copied. Nothing was changed. Try again in a moment.")
        self.assertEqual(checkpoints.restore(SESSION, FIX, NOTE), {
            "error": "The file backups are still being copied. Nothing was changed. Try again in a moment."})
        self.assertEqual(self.read(self.books), "clamped\n")
        self.assertIsNone(checkpoints.undoable(SESSION, NOTE))

    def test_nothing_to_change_restores_nothing(self):
        self.answer(ask={FIX: {"canRewind": True, "filesChanged": [], "insertions": 0, "deletions": 0}})
        self.assertEqual(checkpoints.restore(SESSION, FIX, NOTE),
                         {"error": "The files are already as they were there"})
        self.assertFalse(any("--rewind-files" in call["argv"] for call in self.calls()))


class CommandLine(Checkpoints):
    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = checkpoints.main(["checkpoints.py", *args])
        return code, json.loads(out.getvalue()) if code == 0 else None

    def test_the_apps_commands_answer_in_json(self):
        self.story()
        code, found = self.cli("points", SESSION)
        self.assertEqual((code, [p["id"] for p in found["points"]], found["undo"]), (0, [FIRST, FIX, TEST, NOTE], None))
        self.assertEqual(self.cli("points", "not-a-session"), (0, {"error": "not a session id"}))
        self.assertEqual(self.cli("rewind", SESSION), (2, None))
