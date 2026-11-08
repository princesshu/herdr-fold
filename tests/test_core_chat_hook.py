"""Tests for core/chat_hook.py in a temporary HOME: Claude's PermissionRequest answered from the app's answer file as
Claude's decision, nothing printed when no answer comes; the status line's numbers kept for the app, nothing else."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chat  # noqa: E402
import chat_hook  # noqa: E402
import statefile  # noqa: E402

SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
RULE = {"type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "pytest:*"}], "behavior": "allow",
        "destination": "localSettings"}
BASH = {"session_id": SESSION, "hook_event_name": "PermissionRequest", "cwd": "/repo/lumen",
        "transcript_path": "/repo/x.jsonl", "tool_name": "Bash",
        "tool_input": {"command": "pytest -q", "description": "Run the tests"}, "permission_suggestions": [RULE]}
QUESTION = {**BASH, "tool_name": "AskUserQuestion", "permission_suggestions": [], "tool_input": {"questions": [
    {"question": "Which page size?", "header": "Size", "options": [{"label": "20"}, {"label": "50"}],
     "multiSelect": False}]}}
PLAN = {**BASH, "tool_name": "ExitPlanMode", "permission_suggestions": [], "tool_input": {"plan": "1. Cap the page"}}


def decided(decision):
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


class Decision(unittest.TestCase):
    def test_yes(self):
        out = chat_hook.claude_decision(BASH, {"id": "r", "choice": "allow"})
        self.assertEqual(out, decided({"behavior": "allow"}))

    def test_yes_and_keep_the_rule_where_chosen(self):
        for scope, destination in (("session", "session"), ("project", "localSettings"), ("user", "userSettings")):
            with self.subTest(scope):
                out = chat_hook.claude_decision(BASH, {"id": "r", "choice": "keep", "scope": scope})
                self.assertEqual(out, decided({"behavior": "allow",
                                               "updatedPermissions": [{**RULE, "destination": destination}]}))

    def test_only_what_the_card_says_is_kept(self):
        # one rule, or edits for this conversation: a directory, two rules or a mode kept anywhere else stay unkept
        dirs = {"type": "addDirectories", "directories": ["/elsewhere"], "destination": "session"}
        two = {**RULE, "rules": RULE["rules"] + [{"toolName": "Bash", "ruleContent": "rm:*"}]}
        for suggestion in (dirs, two):
            with self.subTest(suggestion["type"]):
                out = chat_hook.claude_decision({**BASH, "permission_suggestions": [suggestion]},
                                                {"id": "r", "choice": "keep", "scope": "user"})
                self.assertEqual(out, decided({"behavior": "allow"}))
        edits = {"type": "setMode", "mode": "acceptEdits", "destination": "localSettings"}
        out = chat_hook.claude_decision({**BASH, "tool_name": "Edit", "permission_suggestions": [edits]},
                                        {"id": "r", "choice": "keep", "scope": "user"})
        self.assertEqual(out, decided({"behavior": "allow",
                                       "updatedPermissions": [{**edits, "destination": "session"}]}))

    def test_keep_without_a_rule_to_keep_is_a_plain_yes(self):
        out = chat_hook.claude_decision({**BASH, "permission_suggestions": []}, {"id": "r", "choice": "keep"})
        self.assertEqual(out, decided({"behavior": "allow"}))

    def test_no_with_the_users_words(self):
        out = chat_hook.claude_decision(BASH, {"id": "r", "choice": "deny", "text": "Run only the pager's tests"})
        self.assertEqual(out, decided({"behavior": "deny", "message": "Run only the pager's tests"}))
        out = chat_hook.claude_decision(BASH, {"id": "r", "choice": "deny"})
        self.assertEqual(out, decided({"behavior": "deny", "message": "The user said no."}))

    def test_a_questions_answers(self):
        out = chat_hook.claude_decision(QUESTION, {"id": "r", "choice": "allow", "answers": {"Which page size?": "20"}})
        self.assertEqual(out, decided({"behavior": "allow", "updatedInput": {
            "questions": QUESTION["tool_input"]["questions"], "answers": {"Which page size?": "20"}}}))


class Waiting(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)
        self.folder = chat.chat_dir(SESSION)

    def later(self, do):
        """DO run once the request is there, as the app would; the thread joined after the test."""
        def run():
            end = time.monotonic() + 5
            while not chat.pending(SESSION) and time.monotonic() < end:
                time.sleep(0.02)
            do(chat.pending(SESSION))
        thread = threading.Thread(target=run)
        thread.start()
        self.addCleanup(thread.join)

    def test_the_apps_answer_comes_back_and_both_files_go(self):
        self.later(lambda asked: chat.answer(SESSION, {"id": asked["id"], "choice": "allow"}))
        reply = chat_hook.wait_for(BASH, timeout=5, poll=0.02)
        self.assertEqual(reply["choice"], "allow")
        self.assertEqual(os.listdir(self.folder), [])

    def test_the_request_holds_what_the_card_shows_and_nothing_more(self):
        seen = []
        self.later(lambda asked: seen.append(asked) or chat.answer(SESSION, {"id": asked["id"], "choice": "deny"}))
        chat_hook.wait_for(BASH, timeout=5, poll=0.02)
        self.assertEqual(sorted(seen[0]), ["cwd", "id", "kind", "permission_suggestions", "tool_input", "tool_name"])
        self.assertEqual((seen[0]["kind"], seen[0]["tool_input"]), ("permission", BASH["tool_input"]))

    def test_no_answer_in_time_prints_nothing(self):
        self.assertIsNone(chat_hook.wait_for(BASH, timeout=0.3, poll=0.02))
        self.assertEqual(os.listdir(self.folder), [])            # the card goes: Claude asks in its terminal
        out = io.StringIO()
        with mock.patch.object(chat_hook, "TIMEOUT", 0.3), mock.patch("sys.stdin", io.StringIO(json.dumps(BASH))), \
                contextlib.redirect_stdout(out):
            self.assertEqual(chat_hook.main(["chat_hook.py", "permission"]), 0)
        self.assertEqual(out.getvalue(), "")

    def test_a_plan_is_posted_for_its_card_and_left_to_claudes_own_dialog(self):
        # Claude takes no hook's yes to leave plan mode: the card answers in its terminal, the hook returns at once
        out = io.StringIO()
        started = time.monotonic()
        with mock.patch.object(chat_hook, "TIMEOUT", 3), mock.patch("sys.stdin", io.StringIO(json.dumps(PLAN))), \
                contextlib.redirect_stdout(out):
            self.assertEqual(chat_hook.main(["chat_hook.py", "permission"]), 0)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(out.getvalue(), "")
        asked = chat.pending(SESSION)
        self.assertEqual((asked["kind"], asked["tool_input"]), ("dialog", PLAN["tool_input"]))

    def test_a_strangers_answer_is_ignored(self):
        self.later(lambda asked: statefile.write(os.path.join(self.folder, "answer.json"),
                                                 {"id": "other", "choice": "allow"}))
        self.assertIsNone(chat_hook.wait_for(BASH, timeout=0.5, poll=0.02))

    def test_a_request_asked_after_it_takes_its_place(self):
        newer = {"id": "newer", "kind": "permission", "tool_name": "Bash"}
        self.later(lambda asked: statefile.write(os.path.join(self.folder, "request.json"), newer))
        started = time.monotonic()
        self.assertIsNone(chat_hook.wait_for(BASH, timeout=10, poll=0.02))
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(chat.pending(SESSION), newer)            # the newer one stays for its own hook

    def test_an_answer_left_from_before_is_cleared_first(self):
        statefile.write(os.path.join(self.folder, "answer.json"), {"id": "old", "choice": "allow"})
        self.assertIsNone(chat_hook.wait_for(BASH, timeout=0.2, poll=0.02))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "answer.json")))

    def test_the_hook_answers_claude_on_stdout(self):
        self.later(lambda asked: chat.answer(SESSION, {"id": asked["id"], "choice": "allow"}))
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(BASH))), contextlib.redirect_stdout(out):
            self.assertEqual(chat_hook.main(["chat_hook.py", "permission"]), 0)
        self.assertEqual(json.loads(out.getvalue()), decided({"behavior": "allow"}))

    def test_a_session_that_is_not_an_id_prints_nothing(self):
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps({**BASH, "session_id": "../x"}))), \
                contextlib.redirect_stdout(out):
            self.assertEqual(chat_hook.main(["chat_hook.py", "permission"]), 0)
        self.assertEqual(out.getvalue(), "")


class Status(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def test_the_status_line_writes_its_file_without_any_prompt_text(self):
        data = {"session_id": SESSION, "cwd": "/repo/lumen", "transcript_path": "/repo/x.jsonl",
                "workspace": {"current_dir": "/repo/lumen"}, "model": {"id": "claude-opus-5-5", "display_name": "Opus"},
                "effort": {"level": "xhigh"},
                "context_window": {"used_percentage": 42.4, "context_window_size": 200000},
                "rate_limits": {"five_hour": {"used_percentage": 12, "resets_at": 1762621200},
                                "seven_day": {"used_percentage": 40.6, "resets_at": 1763000000}}}
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(data))), contextlib.redirect_stdout(out):
            self.assertEqual(chat_hook.main(["chat_hook.py", "status"]), 0)
        self.assertEqual(out.getvalue(), "Opus · ctx 42%\n")
        kept = chat.status(SESSION)
        self.assertIsInstance(kept.pop("at"), int)
        self.assertEqual(kept, {"context": 42, "window": 200000, "model": "Opus", "effort": "xhigh",
                                "limits": {"five_hour": {"used": 12, "resets": 1762621200},
                                           "week": {"used": 41, "resets": 1763000000}}})
        with open(chat.status_path(SESSION), encoding="utf-8") as f:
            self.assertNotIn("/repo", f.read())

    def test_a_status_without_numbers_keeps_them_empty(self):
        self.assertEqual(chat_hook.write_status({"session_id": SESSION}), "Claude")
        self.assertEqual(chat.status(SESSION)["limits"], {"five_hour": {"used": None, "resets": None},
                                                          "week": {"used": None, "resets": None}})


if __name__ == "__main__":
    unittest.main()
