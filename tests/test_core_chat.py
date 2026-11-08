"""Tests for core/chat.py: a Claude Code session file read into the steps the app's chat draws, only where it grew
(lines built the way Claude writes them); the request, answer and status files a chat's hook and the app share."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, jsonl, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chat  # noqa: E402
import statefile  # noqa: E402

BOOKS = "src/lumen/routes/books.py"
SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
REQUEST = {"id": "r1", "kind": "permission", "tool_name": "Bash", "tool_input": {"command": "pytest -q"}}


def cli(*args):
    """chat.py's command line: its exit code, and its answer when it gave one."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = chat.main(["chat.py", *args])
    return code, json.loads(out.getvalue()) if code == 0 else None


def at(minute):
    return f"2026-11-08T14:{minute:02d}:00.000Z"


def prompt(content, minute=0, **extra):
    return jsonl({"type": "user", "isSidechain": False, "timestamp": at(minute), "permissionMode": "auto",
                  "message": {"role": "user", "content": content}, **extra})


def said(block, minute=1, **extra):
    return jsonl({"type": "assistant", "isSidechain": False, "timestamp": at(minute), "effort": "xhigh",
                  "requestedModel": "claude-opus-5-5", "message": {"model": "claude-opus-5-5", "role": "assistant",
                                                                   "content": [block]}, **extra})


def call(tool_id, name, minute=1, **tool_input):
    return said({"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}, minute)


def answered(tool_id, content, error=False, minute=2, **extra):
    return jsonl({"type": "user", "isSidechain": False, "timestamp": at(minute),
                  "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id,
                                                           "content": content, "is_error": error}]}, **extra})


USER = prompt("Why does page 4 answer page 3?")
THOUGHT = said({"type": "thinking", "thinking": "", "signature": "x"}, thinkingDurationMs=4200)
READ = call("t1", "Read", file_path=BOOKS)
READ_OK = answered("t1", "1\tfrom lumen import store")
ANSWER = said({"type": "text", "text": "Page 4 is past the last one, so the last page is served."}, minute=3)


class Case(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        self.path = os.path.join(self.home, f"{SESSION}.jsonl")

    def write(self, *lines):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("".join(lines))
        return self.path


class Steps(Case):
    def kinds(self, *lines):
        return [step["kind"] for step in chat.steps(self.write(*lines))["steps"]]

    def test_a_turn_becomes_its_steps(self):
        answer = chat.steps(self.write(USER, THOUGHT, READ, READ_OK, ANSWER))
        steps = answer["steps"]
        self.assertEqual([s["kind"] for s in steps], ["user", "thought", "tool", "result", "text"])
        self.assertEqual(steps[0], {"kind": "user", "text": "Why does page 4 answer page 3?", "at": at(0)})
        self.assertEqual(steps[1]["ms"], 4200)
        self.assertEqual((steps[2]["id"], steps[2]["name"], steps[2]["main"]), ("t1", "Read", BOOKS))
        self.assertEqual(steps[2]["input"], {"file_path": BOOKS})
        self.assertEqual((steps[3]["id"], steps[3]["ok"]), ("t1", True))
        self.assertEqual(steps[3]["output"], "1\tfrom lumen import store")
        self.assertEqual(steps[4]["text"], "Page 4 is past the last one, so the last page is served.")
        self.assertEqual(steps[4]["at"], at(3))
        self.assertEqual(answer["offset"], os.path.getsize(self.path))

    def test_a_failed_command_says_so_with_its_output(self):
        steps = chat.steps(self.write(call("t2", "Bash", command="pytest -q", description="Run the tests"),
                                      answered("t2", [{"type": "text", "text": "Exit code 1"},
                                                      {"type": "text", "text": "FAILED tests/test_books.py"}],
                                               error=True)))["steps"]
        self.assertEqual(steps[0]["main"], "pytest -q")
        self.assertFalse(steps[1]["ok"])
        self.assertIn("Exit code 1", steps[1]["output"])
        self.assertIn("FAILED tests/test_books.py", steps[1]["output"])

    def test_a_long_output_and_a_long_input_keep_their_start_and_end(self):
        long = "first line\n" + "x" * 10000 + "\nlast line"
        steps = chat.steps(self.write(call("t3", "Bash", command=long), answered("t3", long)))["steps"]
        self.assertLessEqual(len(steps[0]["input"]["command"]), chat.INPUT)
        self.assertLessEqual(len(steps[1]["output"]), chat.OUTPUT)
        self.assertTrue(steps[1]["output"].startswith("first line") and steps[1]["output"].endswith("last line"))

    def test_an_edit_carries_its_change_numbered_by_the_file(self):
        patch = [{"oldStart": 12, "oldLines": 1, "newStart": 12, "newLines": 1,
                  "lines": ["-    return page", "+    return min(page, last)"]}]
        steps = chat.steps(self.write(
            call("t4", "Edit", file_path=BOOKS, old_string="    return page", new_string="    return min(page, last)"),
            answered("t4", "The file was updated.", toolUseResult={"filePath": BOOKS, "structuredPatch": patch})))
        self.assertEqual(steps["steps"][1]["change"], {"path": BOOKS, "lines": [
            "@@ -12,1 +12,1 @@", "-    return page", "+    return min(page, last)"]})

    def test_a_new_file_is_all_added_lines(self):
        steps = chat.steps(self.write(
            call("t5", "Write", file_path="docs/pagination.md", content="# Pagination\nTwenty to a page.\n"),
            answered("t5", "File created.", toolUseResult={"type": "create", "filePath": "docs/pagination.md",
                                                            "content": "# Pagination\nTwenty to a page.\n",
                                                            "structuredPatch": []})))["steps"]
        self.assertEqual(steps[1]["change"], {"path": "docs/pagination.md", "lines": [
            "@@ -0,0 +1,2 @@", "+# Pagination", "+Twenty to a page."]})

    def test_a_result_without_a_change_has_none(self):
        steps = chat.steps(self.write(READ, READ_OK, call("t6", "Edit", file_path=BOOKS, old_string="a",
                                                          new_string="b"),
                                      answered("t6", "String not found", error=True)))["steps"]
        self.assertEqual([s["change"] for s in steps if s["kind"] == "result"], [None, None])

    def test_a_skill_a_sub_agent_and_a_todo_list(self):
        steps = chat.steps(self.write(
            call("t7", "Skill", skill="release"),
            call("t8", "Agent", subagent_type="Explore", description="Find the pager", prompt="Where is it?"),
            call("t9", "Task", subagent_type="general-purpose", description="Read the docs", prompt="Read them"),
            call("t10", "TodoWrite", todos=[{"content": "Write the test", "status": "completed"},
                                            {"content": "Make it pass", "status": "in_progress"}])))["steps"]
        self.assertEqual(steps[0], {"kind": "skill", "id": "t7", "name": "release", "at": at(1)})
        self.assertEqual(steps[1], {"kind": "agent", "id": "t8", "name": "Explore", "task": "Find the pager",
                                    "at": at(1)})
        self.assertEqual((steps[2]["kind"], steps[2]["name"]), ("agent", "general-purpose"))   # its name before 2.1
        self.assertEqual(steps[3]["items"], [{"text": "Write the test", "done": True},
                                             {"text": "Make it pass", "done": False}])

    def test_an_unknown_block_is_a_plain_step_and_metadata_is_skipped(self):
        steps = chat.steps(self.write(
            jsonl({"type": "attachment", "attachment": {"type": "file"}, "timestamp": at(0)}),
            jsonl({"type": "queue-operation", "operation": "enqueue", "content": "next"}),
            jsonl({"type": "api-request-blob", "message": {"content": [{"type": "text", "text": "a request"}]}}),
            jsonl({"type": "ai-title", "aiTitle": "Pagination"}),
            said({"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "pagination"}}),
            jsonl({"type": "system", "subtype": "turn_duration", "durationMs": 9000, "timestamp": at(2)}),
            jsonl({"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted",
                   "timestamp": at(4)})))["steps"]
        self.assertEqual(steps, [{"kind": "other", "type": "server_tool_use", "summary": "web_search", "at": at(1)},
                                 {"kind": "other", "type": "compact_boundary", "summary": "Conversation compacted",
                                  "at": at(4)}])

    def test_a_damaged_line_is_left_out_and_the_rest_read(self):
        self.assertEqual(self.kinds(USER, "{not json\n", "[1, 2]\n", ANSWER), ["user", "text"])

    def test_a_half_written_last_line_waits_for_the_next_read(self):
        first = chat.steps(self.write(USER, ANSWER[:30]))
        self.assertEqual([s["kind"] for s in first["steps"]], ["user"])
        self.assertEqual(first["offset"], len(USER.encode()))
        self.write(ANSWER[30:])
        rest = chat.steps(self.path, first["offset"])
        self.assertEqual([s["kind"] for s in rest["steps"]], ["text"])
        self.assertEqual(rest["offset"], os.path.getsize(self.path))

    def test_a_line_longer_than_a_read_is_read_whole(self):
        with mock.patch.object(chat, "READ", 64):
            answer = chat.steps(self.write(said({"type": "text", "text": "y" * 500}), ANSWER))
        self.assertEqual([s["kind"] for s in answer["steps"]], ["text"])     # the next line waits for the next read
        self.assertEqual(len(answer["steps"][0]["text"]), 500)

    def test_the_newest_model_effort_and_mode_come_along(self):
        answer = chat.steps(self.write(
            USER, jsonl({"type": "permission-mode", "permissionMode": "plan", "sessionId": "s"}),
            said({"type": "text", "text": "Planning."}, requestedModel="claude-opus-5-5[1m]", effort="high")))
        self.assertEqual((answer["model"], answer["effort"], answer["mode"]), ("claude-opus-5-5[1m]", "high", "plan"))
        self.assertEqual(chat.steps(self.path, answer["offset"]),
                         {"offset": answer["offset"], "steps": [], "model": None, "effort": None, "mode": None})

    def test_helpers_and_meta_lines_are_left_out(self):
        self.assertEqual(self.kinds(
            prompt("Look into the pager", isSidechain=True), said({"type": "text", "text": "Done"}, isSidechain=True),
            prompt("Caveat: the messages below were generated by the user", isMeta=True),
            prompt("<command-name>/model</command-name>"), prompt("[Request interrupted by user]"),
            prompt("This session is being continued from a previous conversation", isCompactSummary=True),
            prompt([{"type": "text", "text": "<ide_opened_file>books.py</ide_opened_file>"},
                    {"type": "text", "text": "Fix it"}])), ["user"])

    def test_a_file_that_is_not_there_yet_has_no_steps(self):
        self.assertEqual(chat.steps(self.path, 0)["steps"], [])


class CommandLine(Case):
    """The app mod's: the steps of a session's conversation as JSON on stdout, found wherever Claude keeps it."""

    def test_the_command_line_prints_the_steps_of_a_session(self):
        set_env(self, HOME=self.home)
        self.assertEqual(cli("steps", SESSION, "0")[1]["steps"], [])               # Claude has not written it yet
        self.path = os.path.join(self.home, ".claude", "projects", "-work-lumen-api", f"{SESSION}.jsonl")
        os.makedirs(os.path.dirname(self.path))
        self.write(USER, ANSWER)
        code, answer = cli("steps", SESSION, "0")
        self.assertEqual(code, 0)
        self.assertEqual([s["kind"] for s in answer["steps"]], ["user", "text"])
        self.assertEqual(cli("steps", SESSION, str(answer["offset"]))[1]["steps"], [])
        for bad in (("steps", SESSION, "-1"), ("steps", "../x", "0"), ("steps",)):
            with self.subTest(bad):
                self.assertEqual(cli(*bad)[0], 2)


class Files(unittest.TestCase):
    """What Claude waits on, the app's answer and the status line's numbers: a chat's own files, its user's only."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)
        self.folder = os.path.join(self.home, ".local", "state", "herdr-fold", "chat", SESSION)

    def ask(self, request=REQUEST):
        statefile.write(os.path.join(chat.chat_dir(SESSION), "request.json"), request)     # as the hook does

    def test_a_session_id_must_be_a_uuid(self):
        self.assertEqual(chat.chat_dir(SESSION), self.folder)
        for bad in ("../x", "a" * 36, "", SESSION.upper(), SESSION + "/..", f"../{SESSION[3:]}"):
            with self.subTest(bad), self.assertRaises(ValueError):
                chat.chat_dir(bad)

    def test_a_request_is_read_and_answered(self):
        self.assertIsNone(chat.pending(SESSION))
        self.ask()
        self.assertEqual(chat.pending(SESSION), REQUEST)
        self.assertTrue(chat.answer(SESSION, {"id": "r1", "choice": "allow"}))
        with open(os.path.join(self.folder, "answer.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"id": "r1", "choice": "allow"})

    def test_an_answer_for_another_request_is_refused(self):
        self.assertFalse(chat.answer(SESSION, {"id": "r1", "choice": "allow"}))         # nothing asked
        self.ask()
        for reply in ({"id": "older", "choice": "allow"}, {"choice": "allow"}, ["r1"]):
            with self.subTest(reply):
                self.assertFalse(chat.answer(SESSION, reply))
        self.ask({**REQUEST, "id": None})
        self.assertFalse(chat.answer(SESSION, {"id": None, "choice": "allow"}))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "answer.json")))

    @unittest.skipIf(os.name == "nt", "POSIX modes")
    def test_its_files_are_private_to_the_user(self):
        mask = os.umask(0)
        self.addCleanup(os.umask, mask)
        self.ask()
        chat.answer(SESSION, {"id": "r1", "choice": "deny"})
        self.assertEqual(os.stat(self.folder).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(os.path.join(self.folder, "answer.json")).st_mode & 0o777, 0o600)

    def test_the_status_line_numbers_are_read_from_their_file(self):
        self.assertIsNone(chat.status(SESSION))
        statefile.write(chat.status_path(SESSION), {"context": 42, "model": "claude-opus-5-5"})
        self.assertEqual(chat.status(SESSION), {"context": 42, "model": "claude-opus-5-5"})
        with open(chat.status_path(SESSION), "w", encoding="utf-8") as f:
            f.write("[1, 2")
        self.assertIsNone(chat.status(SESSION))

    def test_the_command_line_answers(self):
        self.assertEqual(cli("pending", SESSION), (0, None))
        self.ask()
        self.assertEqual(cli("pending", SESSION), (0, REQUEST))
        self.assertEqual(cli("answer", SESSION, json.dumps({"id": "older"})), (0, {"ok": False}))
        self.assertEqual(cli("answer", SESSION, json.dumps({"id": "r1", "choice": "allow"})), (0, {"ok": True}))
        self.assertEqual(cli("status", SESSION), (0, None))
        for bad in (("answer", SESSION, "{not json"), ("pending", "../x"), ("status",), ("answer", SESSION)):
            with self.subTest(bad):
                self.assertEqual(cli(*bad)[0], 2)


if __name__ == "__main__":
    unittest.main()
