"""Tests for core/plan.py: a chat's task list and its approved plan read from the agent's own file (lines built the
way Claude and Codex write them), as both clients show them."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import PACKAGE, jsonl

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import plan  # noqa: E402

PLAN = "# Keep a page past the last one in range\n\n1. Keep the page inside 1…pages\n2. Add the tests\n\nNo more."


def said(*blocks, **extra):
    return {"type": "assistant", "uuid": extra.pop("uuid", None), "message": {"role": "assistant",
                                                                              "content": list(blocks)}, **extra}


def use(call_id, name, **args):
    return {"type": "tool_use", "id": call_id, "name": name, "input": args}


def result(call_id, content, error=False, **extra):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": error}]}, **extra}


def prompt(words):
    return {"type": "user", "message": {"role": "user", "content": words}}


def created(call_id, number, subject):
    return [said(use(call_id, "TaskCreate", subject=subject, description="…", activeForm="Doing it")),
            result(call_id, f"Task #{number} created successfully: {subject}")]


def update(steps, explanation=None):
    args = {"plan": [{"step": step, "status": status} for step, status in steps]}
    return {"type": "response_item", "payload": {"type": "function_call", "name": "update_plan", "call_id": "c1",
                                                 "arguments": json.dumps({**args, **({"explanation": explanation}
                                                                                     if explanation else {})})}}


def typed(words):
    return {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                 "content": [{"type": "input_text", "text": words}]}}


def folded(*entries, kind="claude"):
    state = plan.new()
    for entry in entries:
        (plan.claude if kind == "claude" else plan.codex)(state, entry)
    return state


LIST = [*created("t1", 1, "Keep the page inside 1…pages"), *created("t2", 2, "Add the tests past the end"),
        *created("t3", 3, "Run the whole suite")]


class ClaudeTasks(unittest.TestCase):
    def test_a_task_is_on_the_list_once_claude_numbered_it(self):
        state = plan.new()
        told = plan.claude(state, LIST[0])
        self.assertEqual(told, {"t1": {"kind": "tasks", "id": "t1", "added": 1}})
        self.assertIsNone(plan.shown(state))                         # no number yet: not on the list
        plan.claude(state, LIST[1])
        self.assertEqual(plan.shown(state)["steps"], [{"text": "Keep the page inside 1…pages", "state": "next",
                                                       "after": None}])

    def test_a_task_refused_is_not_on_the_list(self):
        state = folded(said(use("t1", "TaskCreate", subject="Keep the page")), result("t1", "No.", error=True))
        self.assertIsNone(plan.shown(state))

    def test_the_list_counts_what_is_done_and_names_what_runs(self):
        state = folded(*LIST, said(use("u1", "TaskUpdate", taskId="1", status="completed")),
                       said(use("u2", "TaskUpdate", taskId="2", status="in_progress")))
        shown = plan.shown(state)
        self.assertEqual([step["state"] for step in shown["steps"]], ["done", "now", "next"])
        self.assertEqual((shown["count"], shown["done"], shown["finished"]), ("1 of 3 done", "1 done", False))

    def test_only_a_step_done_is_a_change_the_timeline_tells(self):
        state = folded(*LIST)
        self.assertEqual(plan.claude(state, said(use("u1", "TaskUpdate", taskId="2", status="in_progress"))), {})
        done = said(use("u2", "TaskUpdate", taskId="2", status="completed"))
        self.assertEqual(plan.claude(state, done), {"u2": {"kind": "task", "id": "u2",
                                                           "text": "Add the tests past the end"}})
        self.assertEqual(plan.claude(state, done), {})               # done already: no change
        self.assertEqual(plan.claude(state, said(use("l1", "TaskList"))), {})

    def test_a_step_waits_for_the_ones_it_names_until_they_are_done(self):
        state = folded(*LIST, said(use("u1", "TaskUpdate", taskId="3", addBlockedBy=["2"])))
        self.assertEqual(plan.shown(state)["steps"][2]["after"], "after Add the tests past the end")
        plan.claude(state, said(use("u2", "TaskUpdate", taskId="1", addBlocks=["3"])))
        self.assertEqual(plan.shown(state)["steps"][2]["after"], "after 2 steps")
        for number in "12":
            plan.claude(state, said(use(f"d{number}", "TaskUpdate", taskId=number, status="completed")))
        self.assertIsNone(plan.shown(state)["steps"][2]["after"])

    def test_a_task_renamed_or_deleted(self):
        state = folded(*LIST, said(use("u1", "TaskUpdate", taskId="1", subject="Clamp the page")),
                       said(use("u2", "TaskUpdate", taskId="3", status="deleted")),
                       said(use("u3", "TaskUpdate", taskId="9", status="completed")))      # one it never made
        self.assertEqual([step["text"] for step in plan.shown(state)["steps"]],
                         ["Clamp the page", "Add the tests past the end"])

    def test_a_finished_list_stays_until_the_next_message(self):
        state = folded(*LIST, *(said(use(f"d{n}", "TaskUpdate", taskId=n, status="completed")) for n in "123"))
        self.assertEqual((plan.shown(state)["count"], plan.shown(state)["finished"]), ("All 3 done", True))
        plan.claude(state, result("x1", "ok"))                       # a tool's answer is not a message
        plan.claude(state, prompt("<system-reminder>Careful.</system-reminder>"))
        self.assertIsNotNone(plan.shown(state))
        plan.claude(state, prompt("Now the docs."))
        self.assertIsNone(plan.shown(state))

    def test_an_unfinished_list_outlives_a_message_and_a_helper_has_none(self):
        state = folded(*LIST, prompt("Go on."), said(use("s1", "TaskCreate", subject="Its own"), isSidechain=True),
                       result("s1", "Task #4 created successfully: Its own", isSidechain=True))
        self.assertEqual(len(plan.shown(state)["steps"]), 3)

    def test_fields_of_a_wrong_type_are_missing(self):
        state = folded(said(use("t1", "TaskCreate", subject=7)), result("t1", "Task #1 created successfully"),
                       said(use("u1", "TaskUpdate", taskId=1, status=["completed"], addBlockedBy="2")),
                       said({"type": "tool_use", "id": "u2", "name": "TaskUpdate", "input": "x"}), {"type": "user"})
        self.assertEqual(plan.shown(state)["steps"], [{"text": "", "state": "next", "after": None}])


class ApprovedPlan(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def write(self, *entries):
        path = os.path.join(self.folder, "chat.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(jsonl(entry) for entry in entries))
        return path

    def approved(self, call_id="p1", words=PLAN, **extra):
        return result(call_id, "Approved.", toolUseResult={"plan": words, "isAgent": False,
                                                            "filePath": "/Users/dev/.claude/plans/calm-red-fox.md"},
                      **extra)

    def test_an_approved_plan_tells_its_steps_at_its_answer(self):
        state = plan.new()
        self.assertEqual(plan.claude(state, said(use("p1", "ExitPlanMode"))), {})
        self.assertEqual(plan.claude(state, self.approved()), {"p1": 2})
        self.assertEqual(state["plan"], 2)

    def test_a_plan_turned_down_is_none(self):
        state = folded(said(use("p1", "ExitPlanMode")),
                       result("p1", "Keep planning.", error=True, toolUseResult="Error: keep planning"))
        self.assertIsNone(state["plan"])

    def test_the_plan_is_kept_as_a_document_of_herdr_folds_own(self):
        kept = os.path.join(self.folder, "state", "chat")
        path = plan.document(self.write(said(use("p0", "ExitPlanMode")), self.approved("p0", "1. An older one"),
                                        said(use("p1", "ExitPlanMode")), self.approved()), kept)
        self.assertEqual(path, os.path.join(kept, "plan.md"))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), PLAN + "\n")
        self.assertEqual(os.listdir(kept), ["plan.md"])              # nothing left beside it
        if os.name != "nt":
            self.assertEqual(os.stat(path).st_mode & 0o077, 0)

    def test_a_chat_without_a_plan_has_no_document(self):
        self.assertIsNone(plan.document(self.write(*LIST), os.path.join(self.folder, "state")))
        self.assertIsNone(plan.document(os.path.join(self.folder, "gone.jsonl"), os.path.join(self.folder, "state")))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "state")))


class CodexPlan(unittest.TestCase):
    def test_each_update_is_the_whole_list_with_its_note(self):
        state = folded(update([("Page /tides by station", "in_progress"), ("Document the page size", "pending")],
                              "Tables first."),
                       update([("Page /tides by station", "completed"), ("Document the page size", "in_progress")]),
                       kind="codex")
        shown = plan.shown(state)
        self.assertEqual(shown["steps"], [{"text": "Page /tides by station", "state": "done", "after": None},
                                          {"text": "Document the page size", "state": "now", "after": None}])
        self.assertEqual((shown["note"], shown["count"]), (None, "1 of 2 done"))

    def test_its_note_is_shown_while_it_has_one(self):
        state = folded(update([("Page /tides by station", "pending")], "Tables first."), kind="codex")
        self.assertEqual(plan.shown(state)["note"], "Tables first.")

    def test_a_finished_one_goes_with_the_next_message_and_damage_is_no_update(self):
        state = folded(update([("Page /tides by station", "completed")]),
                       {"type": "response_item", "payload": {"type": "function_call", "name": "update_plan",
                                                             "arguments": "{\"plan\": 3"}},
                       typed("<environment_context>…</environment_context>"), kind="codex")
        self.assertEqual(plan.shown(state)["count"], "All 1 done")
        plan.codex(state, typed("Now the docs."))
        self.assertIsNone(plan.shown(state))


class Read(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.path = os.path.join(self.folder, "chat.jsonl")

    def add(self, *entries, end="\n"):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("".join(jsonl(entry) for entry in entries)[:-1] + end)

    def test_a_file_is_read_on_from_where_the_last_read_stopped(self):
        self.add(said({"type": "text", "text": "The page is clamped."}), *LIST[:2])
        first = plan.read("claude", self.path)
        self.assertEqual(first["offset"], os.path.getsize(self.path))
        self.add(*LIST[2:4])
        second = plan.read("claude", self.path, first)
        self.assertEqual(len(plan.shown(second["state"])["steps"]), 2)
        self.assertEqual(len(plan.shown(first["state"])["steps"]), 1)            # the earlier read's is its own

    def test_a_line_still_being_written_waits_and_a_line_written_again_is_not_read_twice(self):
        self.add(*LIST[:2], said(use("u1", "TaskUpdate", taskId="1", status="completed"), uuid="a1"),
                 said(use("u2", "TaskUpdate", taskId="1", status="in_progress"), uuid="a2"),
                 said(use("u1", "TaskUpdate", taskId="1", status="completed"), uuid="a1"))     # a compaction's copy
        whole = os.path.getsize(self.path)
        self.add(said(use("u3", "TaskUpdate", taskId="1", status="completed"), uuid="a3"), end="")
        got = plan.read("claude", self.path)
        self.assertEqual((plan.shown(got["state"])["steps"][0]["state"], got["offset"]), ("now", whole))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("\n")                                            # the line's end
        self.assertEqual(plan.shown(plan.read("claude", self.path, got)["state"])["steps"][0]["state"], "done")

    def test_a_read_stops_where_it_is_told_to(self):
        self.add(*LIST[:2])
        end = os.path.getsize(self.path)
        self.add(*LIST[2:])
        self.assertEqual(len(plan.shown(plan.read("claude", self.path, end=end)["state"])["steps"]), 1)

    def test_codex_and_a_file_that_is_gone(self):
        self.add(typed("Paginate the tide tables."), update([("Page /tides by station", "in_progress")]))
        self.assertEqual(plan.shown(plan.read("codex", self.path)["state"])["count"], "0 of 1 done")
        self.assertIsNone(plan.shown(plan.read("claude", os.path.join(self.folder, "gone.jsonl"))["state"]))


if __name__ == "__main__":
    unittest.main()
