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
import plan  # noqa: E402
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


def needs(servers, minute=0, **extra):
    """A deferred tools line as Claude writes one: SERVERS need a sign-in (None: it names no such list)."""
    attachment = {"type": "deferred_tools_delta", "addedNames": [], "addedLines": [], "removedNames": []}
    if servers is not None:
        attachment["needsAuthMcpServers"] = servers
    return jsonl({"type": "attachment", "isSidechain": False, "timestamp": at(minute), "attachment": attachment,
                  **extra})


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

    def test_a_file_in_claudes_folder_is_named_from_there_one_outside_whole(self):
        inside = said({"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/repo/lumen/src/a.py"}},
                      cwd="/repo/lumen")
        outside = said({"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/etc/hosts"}},
                       cwd="/repo/lumen")
        steps = chat.steps(self.write(inside, outside))["steps"]
        self.assertEqual([step["main"] for step in steps], ["src/a.py", "/etc/hosts"])

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

    def test_a_skill_and_a_subagent(self):
        steps = chat.steps(self.write(
            call("t7", "Skill", skill="release"),
            call("t8", "Agent", subagent_type="Explore", description="Find the pager", prompt="Where is it?"),
            call("t9", "Task", subagent_type="general-purpose", description="Read the docs",
                 prompt="Read them")))["steps"]
        self.assertEqual(steps[0], {"kind": "skill", "id": "t7", "name": "release", "at": at(1)})
        self.assertEqual(steps[1], {"kind": "agent", "id": "t8", "name": "Explore", "task": "Find the pager",
                                    "at": at(1)})
        self.assertEqual((steps[2]["kind"], steps[2]["name"]), ("agent", "general-purpose"))   # its name before 2.1

    def test_the_task_list_is_the_chats_own_and_only_its_changes_are_steps(self):
        answer = chat.steps(self.write(
            call("k1", "TaskCreate", subject="Keep the page inside 1…pages", description="…", activeForm="Keeping"),
            answered("k1", "Task #1 created successfully: Keep the page inside 1…pages"),
            call("k2", "TaskCreate", subject="Add the tests past the end"),
            answered("k2", "Task #2 created successfully: Add the tests past the end"),
            call("k3", "TaskUpdate", taskId="1", status="in_progress"), answered("k3", "Updated task #1 status"),
            call("k4", "TaskList"), answered("k4", "#1 [in_progress] Keep the page"),
            call("k5", "TaskUpdate", taskId="1", status="completed"), answered("k5", "Updated task #1 status")))
        calls = [step for step in answer["steps"] if step["kind"] != "result"]
        self.assertEqual(calls, [{"kind": "tasks", "id": "k1", "added": 1, "at": at(1)},
                                 {"kind": "tasks", "id": "k2", "added": 1, "at": at(1)},
                                 {"kind": "task", "id": "k5", "text": "Keep the page inside 1…pages", "at": at(1)}])
        self.assertEqual((answer["plan"]["count"], [step["state"] for step in answer["plan"]["steps"]]),
                         ("1 of 2 done", ["done", "next"]))

    def test_an_approved_plan_tells_its_steps_at_its_answer(self):
        steps = chat.steps(self.write(call("p1", "ExitPlanMode"), answered("p1", "Approved.", toolUseResult={
            "plan": "1. Keep the page in range\n2. Test it", "isAgent": False,
            "filePath": "/Users/dev/.claude/plans/calm-red-fox.md"}), READ, READ_OK))["steps"]
        self.assertEqual([step.get("plan") for step in steps if step["kind"] == "result"], [2, None])
        self.assertNotIn("plan", steps[3])

    def test_a_question_and_a_plan_say_their_first_words(self):
        steps = chat.steps(self.write(
            call("q1", "AskUserQuestion", questions=[{"question": "Which page size?", "options": []}]),
            call("p1", "ExitPlanMode", plan="## The plan\n\n1. Keep the page inside its range\n2. Test it")))["steps"]
        self.assertEqual([s["main"] for s in steps], ["Which page size?", "Keep the page inside its range"])

    def test_an_unknown_block_is_a_plain_step_and_metadata_is_skipped(self):
        steps = chat.steps(self.write(
            jsonl({"type": "attachment", "attachment": {"type": "file"}, "timestamp": at(0)}),
            jsonl({"type": "queue-operation", "operation": "enqueue", "content": "next"}),
            jsonl({"type": "api-request-blob", "message": {"content": [{"type": "text", "text": "a request"}]}}),
            jsonl({"type": "ai-title", "aiTitle": "Pagination"}),
            said({"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "pagination"}}),
            jsonl({"type": "system", "subtype": "turn_duration", "durationMs": 9000, "timestamp": at(2)}),
            jsonl({"type": "system", "subtype": "compact_boundary", "content": "Chat compacted",
                   "timestamp": at(4)})))["steps"]
        self.assertEqual(steps, [{"kind": "other", "type": "server_tool_use", "summary": "web_search", "at": at(1)},
                                 {"kind": "other", "type": "compact_boundary", "summary": "Chat compacted",
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
                         {"offset": answer["offset"], "steps": [], "model": None, "effort": None, "mode": None,
                          "plan": None})

    def test_helpers_and_meta_lines_are_left_out(self):
        self.assertEqual(self.kinds(
            prompt("Look into the pager", isSidechain=True), said({"type": "text", "text": "Done"}, isSidechain=True),
            prompt("Caveat: the messages below were generated by the user", isMeta=True),
            prompt("<command-name>/model</command-name>"), prompt("[Request interrupted by user]"),
            prompt("This session is being continued from a previous chat", isCompactSummary=True),
            prompt([{"type": "text", "text": "<ide_opened_file>books.py</ide_opened_file>"},
                    {"type": "text", "text": "Fix it"}])), ["user"])

    def test_a_server_that_comes_to_need_a_sign_in_is_a_step(self):
        """The servers to sign in at the chat's start are its setup's (the Agent panel's); one added to the
        list later is a step, where Claude ran into it."""
        first = needs(["claude.ai Notion"], minute=0)
        answer = chat.steps(self.write(first, USER, ANSWER, needs(["claude.ai Notion", "claude.ai Box"], minute=4)))
        self.assertEqual([s for s in answer["steps"] if s["kind"] == "signin"],
                         [{"kind": "signin", "server": "claude.ai Box", "at": at(4)}])
        self.assertEqual([s["kind"] for s in answer["steps"]], ["user", "text", "signin"])

    def test_the_list_before_a_read_is_looked_up_in_the_file(self):
        first = chat.steps(self.write(needs([], minute=0), USER))
        self.write(needs(["sentry", "claude.ai Box"], minute=3))
        rest = chat.steps(self.path, first["offset"])
        self.assertEqual(rest["steps"], [{"kind": "signin", "server": "claude.ai Box", "at": at(3)},
                                         {"kind": "signin", "server": "sentry", "at": at(3)}])
        self.write(needs(["sentry"], minute=5), needs(["sentry", "claude.ai Box"], minute=6))
        again = chat.steps(self.path, rest["offset"])
        self.assertEqual(again["steps"], [{"kind": "signin", "server": "claude.ai Box", "at": at(6)}])

    def test_a_tools_line_that_names_no_list_and_a_sub_agents_own_change_nothing(self):
        lines = [needs(["sentry"], minute=0), needs(None, minute=1),
                 needs(["sentry", "Box"], minute=2, isSidechain=True), needs("Box", minute=3),
                 needs(["sentry", 4, None, "Bo\x1b[2Jx"], minute=4)]
        answer = chat.steps(self.write(*lines))
        self.assertEqual(answer["steps"], [{"kind": "signin", "server": "Bo[2Jx", "at": at(4)}])

    def test_a_file_that_is_not_there_yet_has_no_steps(self):
        self.assertEqual(chat.steps(self.path, 0)["steps"], [])


def uuid(n):
    return f"0d0c0b0a-0908-4706-8504-{n:012d}"


class WrittenAgain(Case):
    """Claude writes lines it wrote before into the file again, under the ids they had (the messages a compaction
    keeps, before its boundary; a chat taken up in another folder, its start with the new folder): each is a step once,
    in one read or over several."""

    def turn(self, **extra):
        read = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": BOOKS}}
        return [needs(["sentry"], minute=0, uuid=uuid(1), **extra),
                prompt("Why is page 4 empty?", uuid=uuid(2), **extra),
                said({"type": "text", "text": "It is past the last one."}, 1, uuid=uuid(3), **extra),
                said(read, 1, uuid=uuid(4), **extra),
                answered("t1", "1\tfrom lumen import store", uuid=uuid(5), **extra)]

    def compaction(self, n=6):
        return [jsonl({"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted",
                       "isSidechain": False, "timestamp": at(5), "uuid": uuid(n), "parentUuid": None,
                       "logicalParentUuid": uuid(n - 1), "compactMetadata": {
                           "trigger": "auto", "preTokens": 180000, "postTokens": 9000,
                           "preservedSegment": {"headUuid": uuid(2), "anchorUuid": uuid(n + 1), "tailUuid": uuid(5)}}}),
                prompt("This session is being continued from a previous conversation.", 5, uuid=uuid(n + 1),
                       parentUuid=uuid(n), isCompactSummary=True, isVisibleInTranscriptOnly=True)]

    def test_the_messages_a_compaction_keeps_are_there_once(self):
        first = self.turn(cwd="/Users/dev/lumen-api", slug="quiet-harbor")
        kept = self.turn(cwd="/Users/dev/lumen-api/.claude/worktrees/pager", slug="pager")
        after = prompt("And page 5?", 6, uuid=uuid(8))
        steps = chat.steps(self.write(*first, *kept[1:], *self.compaction(), *kept, after))["steps"]
        self.assertEqual([step["kind"] for step in steps], ["user", "text", "tool", "result", "other", "user"])
        self.assertEqual((steps[4]["type"], steps[5]["text"]), ("compact_boundary", "And page 5?"))

    def test_a_line_read_before_is_not_a_step_of_a_later_read(self):
        first = chat.steps(self.write(*self.turn(), *self.compaction()))
        self.write(*self.turn(slug="pager"), prompt("And page 5?", 6, uuid=uuid(8)))
        rest = chat.steps(self.path, first["offset"])
        self.assertEqual([(step["kind"], step.get("text")) for step in rest["steps"]], [("user", "And page 5?")])
        self.assertEqual(chat.steps(self.path, rest["offset"])["steps"], [])

    def test_a_line_with_no_id_or_an_id_that_is_not_text_is_always_a_step(self):
        twice = prompt("Again", uuid=["u1"]) * 2 + prompt("Again") * 2
        self.assertEqual([step["kind"] for step in chat.steps(self.write(twice))["steps"]], ["user"] * 4)

    def test_what_an_older_line_names_is_not_brought_back(self):
        """A reply written again names the model of its day, a tools line the servers of its day: neither is the
        chat's newest, and no server comes to need a sign-in by it."""
        old = said({"type": "text", "text": "Planning."}, 1, uuid=uuid(3), requestedModel="claude-haiku-5-5",
                   effort="low", permissionMode="plan")
        first = chat.steps(self.write(needs(["sentry"], minute=0, uuid=uuid(1)), old))
        self.write(needs(["sentry", "claude.ai Box"], minute=2, uuid=uuid(4)),
                   said({"type": "text", "text": "Done."}, 3, uuid=uuid(5), permissionMode="auto"))
        newer = chat.steps(self.path, first["offset"])
        self.assertEqual([step["kind"] for step in newer["steps"]], ["signin", "text"])
        self.write(needs(["sentry"], minute=0, uuid=uuid(1)), old)
        again = chat.steps(self.path, newer["offset"])
        self.assertEqual(again, {"offset": os.path.getsize(self.path), "steps": [], "model": None, "effort": None,
                                 "mode": None, "plan": None})
        self.write(needs(["sentry", "claude.ai Box"], minute=6, uuid=uuid(6)))      # the list as it stood: no step
        self.assertEqual(chat.steps(self.path, again["offset"])["steps"], [])
        whole = chat.steps(self.path)
        self.assertEqual([step["kind"] for step in whole["steps"]], ["text", "signin", "text"])
        self.assertEqual((whole["model"], whole["effort"], whole["mode"]), ("claude-opus-5-5", "xhigh", "auto"))

    def test_the_ids_before_a_read_are_found_across_the_files_blocks(self):
        lines = [prompt(f"Question {n}", uuid=uuid(n)) for n in range(40)]
        first = chat.steps(self.write(*lines))
        self.write(*lines[::-1], prompt("The last one", uuid=uuid(99)))
        for block in (64, 100, 257, chat.READ):
            with self.subTest(block), mock.patch.object(chat, "READ", block):
                self.assertEqual(chat.ids_before(self.path, first["offset"]), {uuid(n) for n in range(40)})
        self.assertEqual([step["text"] for step in chat.steps(self.path, first["offset"])["steps"]], ["The last one"])
        self.assertEqual(chat.ids_before(self.path, 0), set())
        self.assertEqual(chat.ids_before(os.path.join(self.home, "none.jsonl"), 10), set())


class Kept(Case):
    """The ids a read found are kept in the chat's own folder for the next (the command line's): the file is not
    read from its start at every poll; what was kept for another place in the file is not used."""

    def setUp(self):
        super().setUp()
        set_env(self, HOME=self.home)
        self.path = os.path.join(self.home, ".claude", "projects", "-Users-dev-lumen-api", f"{SESSION}.jsonl")
        os.makedirs(os.path.dirname(self.path))
        self.kept = os.path.join(chat.chat_dir(SESSION), chat.SEEN)
        self.lines = [prompt(f"Question {n}", uuid=uuid(n)) for n in range(3)]

    def texts(self, offset):
        code, answer = cli("steps", SESSION, str(offset))
        self.assertEqual(code, 0)
        return [step["text"] for step in answer["steps"]], answer["offset"]

    def test_a_poll_keeps_the_ids_and_the_next_reads_them_not_the_file(self):
        self.write(*self.lines)
        texts, offset = self.texts(0)
        self.assertEqual(texts, ["Question 0", "Question 1", "Question 2"])
        self.assertEqual(statefile.read(self.kept), {"offset": offset, "ids": [uuid(0), uuid(1), uuid(2)],
                                                     "plan": plan.new()})
        self.assertEqual(os.stat(self.kept).st_mode & 0o777, 0o600)
        self.write(self.lines[1], prompt("Question 3", uuid=uuid(3)))
        with mock.patch.object(chat, "ids_before", side_effect=AssertionError("read from the file")), \
                mock.patch.object(plan, "read", side_effect=AssertionError("read from the file")):
            texts, end = self.texts(offset)
        self.assertEqual(texts, ["Question 3"])
        self.assertEqual(statefile.read(self.kept), {"offset": end, "ids": [uuid(n) for n in range(4)],
                                                     "plan": plan.new()})
        with mock.patch.object(statefile, "write", side_effect=AssertionError("written")):
            self.assertEqual(self.texts(end), ([], end))                # nothing new: nothing read, nothing written

    def test_the_list_is_kept_with_the_ids_and_read_from_the_file_when_it_is_not(self):
        self.write(said({"type": "tool_use", "id": "k1", "name": "TaskCreate",
                         "input": {"subject": "Keep the page in range"}}, uuid=uuid(1)),
                   answered("k1", "Task #1 created successfully", uuid=uuid(2)))
        code, first = cli("steps", SESSION, "0")
        self.write(said({"type": "tool_use", "id": "k2", "name": "TaskUpdate",
                         "input": {"taskId": "1", "status": "completed"}}, uuid=uuid(3)))
        for kept in (True, False):
            with self.subTest(kept):
                if not kept:
                    os.unlink(self.kept)
                _, answer = cli("steps", SESSION, str(first["offset"]))
                self.assertEqual((answer["plan"]["count"], [step["kind"] for step in answer["steps"]]),
                                 ("All 1 done", ["task"]))
        _, idle = cli("steps", SESSION, str(answer["offset"]))
        self.assertEqual((idle["steps"], idle["plan"]), ([], answer["plan"]))       # no new line: the list all the same

    def test_what_was_kept_for_another_place_is_read_from_the_file(self):
        self.write(*self.lines)
        _, offset = self.texts(0)
        self.write(self.lines[0], prompt("Question 3", uuid=uuid(3)))
        for kept in ({"offset": offset + 1, "ids": []}, {"offset": offset, "ids": "0"}, {"offset": offset}, None):
            with self.subTest(kept):
                if kept is None:
                    os.unlink(self.kept)
                else:
                    statefile.write(self.kept, kept)
                self.assertEqual(self.texts(offset)[0], ["Question 3"])
        self.assertEqual(self.texts(0)[0], [f"Question {n}" for n in range(4)])         # from the start: none kept

    def test_a_folder_that_cannot_be_written_costs_only_the_reading(self):
        self.write(*self.lines)
        with mock.patch.object(statefile, "write", side_effect=PermissionError("read-only")):
            texts, offset = self.texts(0)
            self.write(self.lines[2], prompt("Question 3", uuid=uuid(3)))
            self.assertEqual((texts[-1], self.texts(offset)[0]), ("Question 2", ["Question 3"]))


class CommandLine(Case):
    """The app mod's: the steps of a session's chat as JSON on stdout, found wherever Claude keeps it."""

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

    def test_the_approved_plan_is_a_file_in_the_chats_folder(self):
        set_env(self, HOME=self.home)
        self.assertEqual(cli("plan", SESSION), (0, {"path": None}))                # Claude has not written it yet
        self.path = os.path.join(self.home, ".claude", "projects", "-work-lumen-api", f"{SESSION}.jsonl")
        os.makedirs(os.path.dirname(self.path))
        self.write(call("p1", "ExitPlanMode"), answered("p1", "Approved.", toolUseResult={
            "plan": "1. Keep the page in range", "isAgent": False,
            "filePath": "/Users/dev/.claude/plans/calm-red-fox.md"}))
        path = cli("plan", SESSION)[1]["path"]
        self.assertEqual(path, os.path.join(chat.chat_dir(SESSION), "plan.md"))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "1. Keep the page in range\n")
        self.assertEqual(cli("plan", "../x")[0], 2)


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

    def test_an_answer_to_one_claude_asks_in_its_own_dialog_takes_it_away(self):
        self.ask({**REQUEST, "kind": "dialog"})                  # its card answers by keys in Claude's terminal
        self.assertTrue(chat.answer(SESSION, {"id": "r1", "choice": "key"}))
        self.assertIsNone(chat.pending(SESSION))
        self.assertEqual(os.listdir(self.folder), [])

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

    def test_one_read_brings_the_steps_what_claude_waits_on_and_the_status(self):
        """The chat polls one command: its steps, what Claude waits on, the status line's numbers, together."""
        self.assertEqual({key: cli("steps", SESSION, "0")[1][key] for key in ("pending", "status")},
                         {"pending": None, "status": None})
        self.ask()
        statefile.write(chat.status_path(SESSION), {"context": 42})
        answer = cli("steps", SESSION, "0")[1]
        self.assertEqual((answer["pending"], answer["status"]), (REQUEST, {"context": 42}))

    def test_a_waiting_edit_brings_its_change_numbered_by_the_file(self):
        """What Claude asks to change, as the chat's card shows it: its lines numbered where they stand in the file."""
        path = os.path.join(self.home, "books.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(f"line {n}\n" for n in range(1, 31)))
        self.ask({**REQUEST, "tool_name": "Edit", "tool_input": {"file_path": path, "old_string": "line 12\n",
                                                                 "new_string": "line 12\nline 12b\n"}})
        change = cli("steps", SESSION, "0")[1]["pending"]["change"]
        self.assertEqual(change, {"path": path, "lines": ["@@ -12,1 +12,2 @@", " line 12", "+line 12b"]})
        self.ask({**REQUEST, "tool_name": "Write", "tool_input": {"file_path": os.path.join(self.home, "new.md"),
                                                                  "content": "# New\n"}})
        self.assertEqual(cli("steps", SESSION, "0")[1]["pending"]["change"]["lines"], ["@@ -0,0 +1,1 @@", "+# New"])
        self.ask()                                                              # a command: no change
        self.assertNotIn("change", cli("steps", SESSION, "0")[1]["pending"])

    def test_the_command_line_answers(self):
        self.ask()
        self.assertEqual(cli("answer", SESSION, json.dumps({"id": "older"})), (0, {"ok": False}))
        self.assertEqual(cli("answer", SESSION, json.dumps({"id": "r1", "choice": "allow"})), (0, {"ok": True}))
        for bad in (("answer", SESSION, "{not json"), ("answer", "../x", "{}"), ("pending", SESSION),
                    ("status", SESSION), ("answer", SESSION)):
            with self.subTest(bad):
                self.assertEqual(cli(*bad)[0], 2)


if __name__ == "__main__":
    unittest.main()
