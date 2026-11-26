"""Tests for core/chats.py in a temporary HOME: the Claude Code, Codex and OpenCode chats with title, folder,
time and state; a file read again only where it grew, unreadable files and damaged lines skipped, none of their files
written."""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import PACKAGE, at_once, finished, jsonl, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import chats          # noqa: E402
import fileops        # noqa: E402


def read(path):
    with open(path, "rb") as f:
        return f.read()


def prompt(text, sidechain=False):
    return jsonl({"type": "user", "isSidechain": sidechain, "cwd": "/repo/app", "message": {"content": text}})


class Chats(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)
        self.state = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")

    def claude(self, session, *lines, folder="-repo-app", changed=None):
        path = os.path.join(self.home, ".claude", "projects", folder, f"{session}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("".join(lines))
        if changed:
            os.utime(path, (changed, changed))
        return path

    def codex(self, name, meta, *lines, changed=None):
        path = os.path.join(self.home, ".codex", "sessions", "2026", "10", "26", f"rollout-{name}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(jsonl({"type": "session_meta", "payload": meta}) + "".join(lines))
        if changed:
            os.utime(path, (changed, changed))
        return path

    def listed(self, agents=()):
        return {c.id: c for c in chats.local(self.state, agents)}

    def test_a_claude_chat_goes_by_its_rename_its_ai_title_or_its_first_prompt(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Fix the login"), jsonl({"type": "ai-title", "aiTitle": "Login redirect fix"}))
        self.claude("s3", prompt("Fix the login"), jsonl({"type": "ai-title", "aiTitle": "Login redirect fix"}),
                    jsonl({"type": "custom-title", "customTitle": "safari"}))
        found = self.listed()
        self.assertEqual({k: c.title for k, c in found.items()},
                         {"s1": "Fix the login", "s2": "Login redirect fix", "s3": "safari"})
        self.assertEqual({(c.agent, c.folder, c.state) for c in found.values()}, {("claude", "/repo/app", "")})

    def test_the_index_keeps_no_more_of_a_prompt_than_a_row_can_show(self):
        # the index is the plugin's own copy of every chat's start: a whole pasted prompt does not belong there
        self.claude("s1", prompt("Fix the login " + "x" * 5000))
        self.listed()
        with open(os.path.join(self.state, chats.INDEX)) as f:
            kept = [entry.get("prompt") or "" for entry in json.load(f)["files"].values()]
        self.assertEqual([len(text) <= chats.PROMPT for text in kept], [True])
        self.assertTrue(kept[0].startswith("Fix the login"))

    def test_a_claude_file_without_a_prompt_is_no_chat(self):
        self.claude("s1", prompt("<command-name>/clear</command-name>"), prompt("subagent's", sidechain=True))
        self.assertEqual(self.listed(), {})

    def test_a_project_folder_linked_to_another_lists_its_chats_once(self):
        # a folder's chats shared with another's by a link (projects/-repo-app-web -> -repo-app): one file, one row
        path = self.claude("s1", prompt("Fix the login"))
        os.symlink(os.path.dirname(path), os.path.join(self.home, ".claude", "projects", "-repo-app-web"))
        self.assertEqual([c.id for c in chats.local(self.state)], ["s1"])
        with open(os.path.join(self.state, chats.INDEX)) as f:
            self.assertEqual(list(json.load(f)["files"]), [path])             # read once, kept once

    def test_a_programs_run_through_the_agent_sdk_is_no_chat(self):
        # a hook's review of every change, run through the Agent SDK, titles itself after the work it reviews: dozens
        # of rows named like the chat they came from. claude -p's and the editors' are the user's own
        def started(entrypoint):
            return jsonl({"type": "user", "isSidechain": False, "cwd": "/repo/app", "entrypoint": entrypoint,
                          "message": {"content": "Review this change"}}) \
                + jsonl({"type": "ai-title", "aiTitle": "Login redirect fix"})
        for session, entrypoint in (("s1", "cli"), ("s2", "sdk-py"), ("s3", "sdk-ts"), ("s4", "sdk-cli"),
                                    ("s5", "claude-vscode"), ("s6", ["sdk-py"])):
            self.claude(session, started(entrypoint))
        self.assertEqual(sorted(self.listed()), ["s1", "s4", "s5", "s6"])

    def test_what_a_version_before_kept_of_a_programs_run_is_read_again(self):
        # 0.3.0's index knows no way a chat was started: kept as it is, a program's runs would stay listed
        path = self.claude("s2", jsonl({"type": "user", "isSidechain": False, "cwd": "/repo/app",
                                        "entrypoint": "sdk-py", "message": {"content": "Review this change"}}))
        os.makedirs(self.state)
        with open(os.path.join(self.state, chats.INDEX), "w") as f:
            json.dump({"version": 2, "files": {path: {
                "offset": os.path.getsize(path), "size": os.path.getsize(path), "mtime": os.path.getmtime(path),
                "prompt": "Review this change", "folder": "/repo/app"}}}, f)
        self.assertEqual(self.listed(), {})

    def test_a_compacted_and_reopened_chat_stays_one_row_under_its_id(self):
        # Claude Code 2.1 compacts and resumes in the chat's own file, under its id: its archive, its name hold
        self.claude("s1", prompt("Fix the login"), changed=1000)
        chats.archive(self.state, {"claude:s1"})
        self.claude("s1", jsonl({"type": "system", "subtype": "compact_boundary", "parentUuid": None}),
                    jsonl({"type": "user", "isSidechain": False, "isCompactSummary": True, "cwd": "/repo/app",
                           "message": {"content": "This session is being continued from a previous one."}}),
                    prompt("And the logout"), changed=2000)
        self.assertEqual([(c.id, c.title, c.time) for c in chats.local(self.state)], [("s1", "Fix the login", 2000)])
        self.assertEqual(chats.archived(self.state), {"claude:s1"})

    def test_two_chats_begun_with_the_same_words_stay_two_rows(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Fix the login"))
        for name, session in (("a", "c1"), ("b", "c2")):
            self.codex(name, {"id": session, "cwd": "/repo/app"},
                       jsonl({"payload": {"type": "message", "role": "user",
                                         "content": [{"type": "input_text", "text": "Fix the login"}]}}))
        self.assertEqual(sorted(self.listed()), ["c1", "c2", "s1", "s2"])

    def test_a_codex_chat_goes_by_its_thread_name_or_its_first_prompt(self):
        self.codex("a", {"id": "c1", "cwd": "/repo/app"},
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "<environment_context>x"}]}}),
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Price list\nmore"}]}}))
        self.codex("b", {"id": "c2", "cwd": "/repo/app"},
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Old prompt"}]}}))
        self.codex("c", {"id": "c3", "cwd": "/repo/app", "source": {"subagent": {"other": "guardian"}}},
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Review this"}]}}))
        index = os.path.join(self.home, ".codex", "session_index.jsonl")
        with open(index, "w") as f:
            f.write(jsonl({"id": "c2", "thread_name": "Invoices"}))
        found = self.listed()
        self.assertEqual({k: (c.agent, c.title) for k, c in found.items()},
                         {"c1": ("codex", "Price list"), "c2": ("codex", "Invoices")})      # no helper (subagent)

    def test_a_name_given_in_herdr_wins(self):
        self.claude("s1", prompt("Fix the login"), jsonl({"type": "custom-title", "customTitle": "safari"}))
        names = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view")
        os.makedirs(names)
        with open(os.path.join(names, "names.json"), "w") as f:
            json.dump({"s1": {"name": "Login, by hand", "given": False}}, f)
        self.assertEqual(self.listed()["s1"].title, "Login, by hand")

    def names(self, value=None):
        """AI Sessions' names.json: written with VALUE, or read."""
        path = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sessions-view",
                            "names.json")
        if value is None:
            with open(path, encoding="utf-8") as f:
                return f.read()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(value)

    def test_a_name_given_here_is_kept_with_herdrs(self):
        # as herdr's Rename pane gives one: AI Sessions keeps it and shows it too; its other names stay
        self.claude("s1", prompt("Fix the login"))
        self.names(json.dumps({"s2": {"name": "Prices", "given": True}}))
        chats.name_session("s1", "Login, by hand")
        self.assertEqual(json.loads(self.names()), {"s2": {"name": "Prices", "given": True},
                                                    "s1": {"name": "Login, by hand", "given": False}})
        self.assertEqual(self.listed()["s1"].title, "Login, by hand")

    def test_a_name_is_given_without_a_names_file_too(self):
        chats.name_session("c1", "Invoices")
        self.assertEqual(json.loads(self.names()), {"c1": {"name": "Invoices", "given": False}})

    def test_a_names_file_that_cannot_be_read_is_left_as_it_is(self):
        self.names("{broken")
        with self.assertRaises(OSError):
            chats.name_session("s1", "Login, by hand")
        self.assertEqual(self.names(), "{broken")

    def test_the_running_ones_have_herdrs_state_and_pane(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Old one"))
        self.codex("a", {"id": "c1", "cwd": "/repo/app"},
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Price list"}]}}))
        agents = [{"pane_id": "w1:p1", "agent": "claude", "agent_status": "working", "cwd": "/repo/app",
                   "agent_session": {"value": "s1"}},
                  {"pane_id": "w1:p4", "agent": "codex", "agent_status": "idle", "cwd": "/repo/app"}]
        found = self.listed(agents)
        self.assertEqual((found["s1"].state, found["s1"].pane), ("working", "w1:p1"))
        self.assertEqual((found["s2"].state, found["s2"].pane), ("", ""))
        # herdr was not told the Codex one's session: the newest Codex chat of its folder is it
        self.assertEqual((found["c1"].state, found["c1"].pane), ("idle", "w1:p4"))

    def test_a_reopened_one_is_known_by_its_pane_before_herdr_knows_its_session(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Old one"))
        agents = [{"pane_id": "w1:p9", "agent": "claude", "agent_status": "blocked", "cwd": "/repo/app"}]
        found = {item.id: item for item in chats.local(self.state, agents, {"w1:p9": "s2"})}
        self.assertEqual((found["s2"].state, found["s2"].pane), ("blocked", "w1:p9"))   # waits at a question
        self.assertEqual(found["s1"].state, "")                     # not the newest of its folder

    def test_a_growing_file_is_read_on_from_where_it_was_left(self):
        path = self.claude("s1", prompt("Fix the login"))
        self.assertEqual(self.listed()["s1"].title, "Fix the login")
        with open(os.path.join(self.state, chats.INDEX)) as f:
            read = json.load(f)["files"][path]["offset"]
        self.assertEqual(read, os.path.getsize(path))
        self.claude("s1", jsonl({"type": "custom-title", "customTitle": "safari"}))
        with open(path, "r+b") as f:                     # what was read already: changed, never read again
            f.write(b"X")
        self.assertEqual(self.listed()["s1"].title, "safari")

    def test_a_line_still_being_written_waits_for_the_next_read(self):
        path = self.claude("s1", prompt("Fix the login"))
        with open(path, "a") as f:
            f.write('{"type":"custom-title","customTitle":"saf')
        self.assertEqual(self.listed()["s1"].title, "Fix the login")
        with open(path, "a") as f:
            f.write('ari"}\n')
        self.assertEqual(self.listed()["s1"].title, "safari")

    def test_cut_off_lines_and_foreign_bytes_are_skipped(self):
        path = self.claude("s1", prompt("Fix the login"))
        with open(path, "ab") as f:
            f.write(b'{"type":"ai-title","aiTitle":"Lo\n\xff\xfe not UTF-8\n')
        self.assertEqual(self.listed()["s1"].title, "Fix the login")

    def test_a_file_that_cannot_be_read_leaves_the_others_listed(self):
        # a pipe named like a chat would hold the column for good; an unreadable file or a folder would end it
        self.claude("s1", prompt("Fix the login"))
        project = os.path.join(self.home, ".claude", "projects", "-repo-app")
        os.mkfifo(os.path.join(project, "pipe.jsonl"))
        os.mkdir(os.path.join(project, "folder.jsonl"))
        os.chmod(self.claude("s2", prompt("Locked away")), 0)
        self.codex("a", {"id": "c1", "cwd": "/repo/app"})
        os.mkfifo(os.path.join(self.home, ".codex", "sessions", "2026", "10", "26", "rollout-pipe.jsonl"))
        self.assertEqual(set(finished(self, self.listed)), {"s1"})

    def test_a_line_nested_too_deep_is_skipped(self):
        deep = '{"type":"user","isSidechain":false,"message":' + "[" * 100_000 + "]" * 100_000 + "}\n"
        self.claude("s1", deep, prompt("Fix the login"))
        self.assertEqual(self.listed()["s1"].title, "Fix the login")

    def test_fields_of_another_type_are_passed_over(self):
        # a file of another version, or damaged: where a text belongs, a number, a list or an object
        self.claude("s1", jsonl({"type": "custom-title", "customTitle": {"x": 1}}),
                    jsonl({"type": "ai-title", "aiTitle": 7}),
                    jsonl({"type": "user", "isSidechain": False, "message": "a text, not an object", "cwd": 5}),
                    jsonl({"type": "user", "isSidechain": False, "message": {"content": 5}}),
                    jsonl({"type": "user", "isSidechain": False, "message": {"content": {"text": "x"}}}),
                    prompt("Fix the login"))
        self.codex("a", ["not", "an", "object"])
        self.codex("b", {"id": 5, "cwd": ["/repo"]})
        self.codex("c", {"id": "c1", "cwd": "/repo/app"},
                   jsonl({"payload": {"type": "message", "role": "user", "content": "text, not parts"}}),
                   jsonl({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Fix the logout"}]}}))
        found = finished(self, self.listed)
        self.assertEqual({k: (c.title, c.folder) for k, c in found.items()},
                         {"s1": ("Fix the login", "/repo/app"), "c1": ("Fix the logout", "/repo/app")})

    def test_an_index_of_another_version_is_read_again(self):
        # what an earlier version kept, of other types or shape, is not taken for this one's: the files are read anew
        path = self.claude("s1", prompt("Fix the login"))
        os.makedirs(self.state)
        with open(os.path.join(self.state, chats.INDEX), "w") as f:
            json.dump({path: {"offset": "x", "size": os.path.getsize(path), "mtime": os.path.getmtime(path),
                              "prompt": 5, "custom": ["a"]}}, f)
        self.assertEqual(self.listed()["s1"].title, "Fix the login")

    def test_nothing_is_written_where_the_chats_are(self):
        paths = [self.claude("s1", prompt("Fix the login")),
                 self.codex("a", {"id": "c1", "cwd": "/repo/app"})]
        def snapshot():
            return [(read(p), os.stat(p).st_mtime_ns) for p in paths]
        before = snapshot()
        self.listed([{"pane_id": "w1:p1", "agent": "claude", "agent_status": "idle", "agent_session": {"value": "s1"}}])
        self.assertEqual(snapshot(), before)
        for top in (".claude", ".codex"):
            for root, _, files in os.walk(os.path.join(self.home, top)):
                for name in files:
                    self.assertIn(os.path.join(root, name), paths)


class Kept(Chats):
    def test_a_job_and_the_main_thread_keeping_at_once_lose_neither(self):
        # the Chats panel's read job notes a reopened pane while the main thread archives a chat
        at_once(chats.statefile, lambda: chats.keep(self.state, resumed={"w1:p9": "s2"}),
                lambda: chats.archive(self.state, {"claude:s1"}))
        self.assertEqual(chats.setting(self.state), {"resumed": {"w1:p9": "s2"}, "archived": ["claude:s1"]})


class Deleting(Chats):
    """Delete…: a closed chat's own file to the system's Trash (a stand-in here: a folder outside the temporary HOME),
    never a running one's, and what was kept for it (its archive, its name) dropped."""

    def setUp(self):
        super().setUp()
        self.bin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.bin)

    def delete(self, kind, session, agents=(), recycle=None):
        return chats.delete(self.state, kind, session, agents, system="darwin",
                            recycle=recycle or (lambda path: shutil.move(path, self.bin)))

    def rollout(self, session, text="Price list", name=None):
        return self.codex(name or f"2026-10-26T10-00-00-{session}", {"id": session, "cwd": "/repo/app"}, jsonl(
            {"payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}}))

    def test_a_claude_chat_goes_to_the_trash_with_its_sub_agents_folder(self):
        path = self.claude("s1", prompt("Fix the login"))
        kept = self.claude("s2", prompt("Price list"))
        helpers = os.path.join(os.path.dirname(path), "s1", "subagents")
        os.makedirs(helpers)
        with open(os.path.join(helpers, "agent-a1.jsonl"), "w") as f:
            f.write(prompt("Look it up", sidechain=True))
        self.assertEqual(self.delete("claude", "s1"), "Trash")
        self.assertEqual(sorted(os.listdir(self.bin)), ["s1", "s1.jsonl"])
        self.assertEqual(os.listdir(os.path.join(self.bin, "s1", "subagents")), ["agent-a1.jsonl"])
        self.assertEqual(sorted(os.listdir(os.path.dirname(path))), ["s2.jsonl"])
        self.assertEqual(list(self.listed()), ["s2"])
        self.assertTrue(os.path.isfile(kept))

    def test_a_codex_chat_is_its_rollout_file(self):
        path, other = self.rollout("c1"), self.rollout("c2")
        self.delete("codex", "c1")
        self.assertEqual(os.listdir(self.bin), [os.path.basename(path)])
        self.assertTrue(os.path.isfile(other))
        self.assertEqual(list(self.listed()), ["c2"])

    def test_a_codex_file_only_named_like_it_stays(self):
        # the name ends as the id does, the chat inside is another: the file says whose it is
        self.rollout("c1")
        other = self.rollout("xc1")
        self.delete("codex", "c1")
        self.assertTrue(os.path.isfile(other))
        self.assertEqual(list(self.listed()), ["xc1"])

    def test_a_running_chat_is_refused(self):
        told = self.claude("s1", prompt("Fix the login"), changed=100)
        newest = self.claude("s2", prompt("Price list"), folder="-repo-web", changed=200)
        agents = [{"agent": "claude", "agent_status": "idle", "pane_id": "p1", "cwd": "/repo/web",
                   "agent_session": {"value": "s1"}},
                  {"agent": "claude", "agent_status": "working", "pane_id": "p2", "cwd": "/repo/app"}]
        for session in ("s1", "s2"):               # the one herdr names, and the one it only knows the folder of
            with self.assertRaises(fileops.Refused) as refused:
                self.delete("claude", session, agents)
            self.assertIn("running", str(refused.exception))
        self.assertTrue(os.path.isfile(told) and os.path.isfile(newest))
        self.assertEqual(os.listdir(self.bin), [])

    def test_what_is_no_chat_of_the_list_is_refused(self):
        program = self.claude("s1", jsonl({"type": "user", "isSidechain": False, "cwd": "/repo/app",
                                           "entrypoint": "sdk-py", "message": {"content": "Review this change"}}))
        for kind, session in (("claude", "s1"), ("claude", "gone"), ("claude", "*"), ("claude", "../x"),
                              ("gemini", "s1"), ("codex", "s1")):
            with self.assertRaises(fileops.Refused, msg=(kind, session)):
                self.delete(kind, session)
        self.assertTrue(os.path.isfile(program))
        self.assertEqual(os.listdir(self.bin), [])

    def test_a_chat_in_a_linked_project_folder_goes_once_from_its_real_place(self):
        path = self.claude("s1", prompt("Fix the login"))
        link = os.path.join(self.home, ".claude", "projects", "-repo")
        os.symlink(os.path.dirname(path), link)
        self.delete("claude", "s1")
        self.assertEqual(os.listdir(self.bin), ["s1.jsonl"])
        self.assertEqual(os.listdir(os.path.dirname(path)), [])
        self.assertTrue(os.path.islink(link))
        self.assertEqual(self.listed(), {})

    def test_a_project_folder_linked_out_of_claudes_is_refused(self):
        outside = os.path.join(self.bin, "elsewhere")
        os.makedirs(outside)
        os.makedirs(os.path.join(self.home, ".claude", "projects"))
        os.symlink(outside, os.path.join(self.home, ".claude", "projects", "-repo-app"))
        path = self.claude("s1", prompt("Fix the login"))
        self.assertEqual(list(self.listed()), ["s1"])
        with self.assertRaises(fileops.Refused):
            self.delete("claude", "s1")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.listdir(outside), ["s1.jsonl"])

    def test_an_archived_one_goes_too_and_its_archive_and_name_are_dropped(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Price list"))
        chats.archive(self.state, {"claude:s1", "claude:s2"})
        chats.name_session("s1", "Login fix")
        chats.name_session("s2", "Prices")
        self.delete("claude", "s1")
        self.assertEqual(chats.archived(self.state), {"claude:s2"})
        self.assertEqual(chats.manual_names(), {"s2": "Prices"})

    def test_no_names_file_is_made_for_it(self):
        self.claude("s1", prompt("Fix the login"))
        self.delete("claude", "s1")
        self.assertFalse(os.path.exists(os.path.dirname(chats.names_path())))

    def test_a_trash_that_refuses_leaves_the_chat_as_it_was(self):
        path = self.claude("s1", prompt("Fix the login"))
        chats.archive(self.state, {"claude:s1"})
        chats.name_session("s1", "Login fix")

        def full(_):
            raise fileops.Refused("the Trash is full")
        with self.assertRaises(fileops.Refused) as refused:
            self.delete("claude", "s1", recycle=full)
        self.assertEqual(str(refused.exception), "the Trash is full")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual((chats.archived(self.state), chats.manual_names()), ({"claude:s1"}, {"s1": "Login fix"}))


class CommandLine(Chats):
    """The app mod's: its answers as JSON on stdout, in the same state folder as the TUI's column."""

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = chats.main(["chats.py", *args])
        return code, json.loads(out.getvalue()) if code == 0 else None

    def test_the_list_marks_the_running_ones_and_names_the_archived(self):
        self.claude("s1", prompt("Fix the login"), changed=100)
        self.claude("s2", prompt("Price list"), changed=200)
        chats.archive(self.state, {"claude:s1"})
        agents = [{"agent": "claude", "agent_status": "working", "pane_id": "p1", "cwd": "/repo/app"}]
        code, answer = self.cli("list", json.dumps(agents), "{}")
        self.assertEqual([(c["id"], c["state"], c["pane"]) for c in answer["chats"]],
                         [("s2", "working", "p1"), ("s1", "", "")])            # the newest in the folder runs
        self.assertEqual(answer["archived"], ["claude:s1"])

    def test_the_list_says_how_long_ago_each_changed(self):
        self.claude("s1", prompt("Fix the login"), changed=time.time() - 2 * 3600)
        self.assertEqual([c["ago"] for c in self.cli("list", "[]", "{}")[1]["chats"]], ["2h"])

    def test_one_is_archived_and_brought_back(self):
        self.assertEqual(self.cli("archive", "claude:s1", "codex:c2"), (0, {"ok": True}))
        self.cli("unarchive", "claude:s1")
        self.assertEqual(chats.archived(self.state), {"codex:c2"})

    def test_a_rename_is_kept_with_herdrs_names(self):
        self.claude("s1", prompt("Fix the login"))
        self.assertEqual(self.cli("rename", "s1", "Login fix"), (0, {"ok": True, "advice": None}))
        self.assertEqual(self.listed()["s1"].title, "Login fix")

    def test_the_markdown_is_the_whole_chat_or_none(self):
        self.claude("s1", prompt("Fix the login"))
        self.assertTrue(self.cli("markdown", "claude", "s1")[1]["markdown"].startswith("# Fix the login"))
        self.assertEqual(self.cli("markdown", "claude", "gone"), (0, {"markdown": None}))

    def test_one_is_deleted_into_the_trash_unless_it_runs(self):
        path, running = self.claude("s1", prompt("Fix the login")), self.claude("s2", prompt("Price list"),
                                                                                folder="-repo-web")
        trashed = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, trashed)
        set_env(self, XDG_DATA_HOME=None)                  # Linux's Trash: under the temporary home
        stand_in = lambda path: shutil.move(path, trashed)                     # noqa: E731
        agents = json.dumps([{"agent": "claude", "agent_status": "working", "pane_id": "p1",
                              "agent_session": {"value": "s2"}}])
        with mock.patch.object(fileops, "mac_trash", stand_in), mock.patch.object(fileops, "windows_recycle", stand_in):
            code, answer = self.cli("delete", "claude", "s2", agents, "{}")
            self.assertEqual((code, answer["ok"]), (0, False))
            self.assertIn("running", answer["advice"])
            self.assertEqual(self.cli("delete", "claude", "s1", agents, "{}"), (0, {"ok": True}))
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.isfile(running))

    def test_anything_else_is_a_usage_error(self):
        for args in ((), ("list",), ("list", "{}", "{}"), ("rename", "s1"), ("archive",), ("eat",),
                     ("delete", "claude", "s1"), ("delete", "claude", "s1", "{}", "{}")):
            self.assertEqual(self.cli(*args)[0], 2, args)


class Readers(unittest.TestCase):
    """Where the chats live (shared with herdr-fold's Cmd+Shift+R and its formatted copy)."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_a_folder_maps_to_claudes_project_folder(self):
        self.assertEqual(chats.claude_project_dir("/Users/a_b/my repo"),
                         os.path.join(self.home, ".claude", "projects", "-Users-a-b-my-repo"))

    def test_a_sessions_files_are_found_by_kind(self):
        claude = self.write(".claude/projects/-x/s1.jsonl", "{}\n")
        codex = self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", "{}\n")
        self.assertEqual(chats.session_files("claude", "s1"), [claude])
        self.assertEqual(chats.session_files("codex", "c1"), [codex])
        self.assertEqual(chats.session_files("other", "s1"), [])

    def test_a_sessions_file_in_a_linked_project_folder_is_found_once(self):
        claude = self.write(".claude/projects/-x/s1.jsonl", "{}\n")
        os.symlink(os.path.dirname(claude), os.path.join(self.home, ".claude", "projects", "-x-web"))
        self.assertEqual(chats.session_files("claude", "s1"), [claude])

    def test_damaged_lines_are_skipped(self):
        path = self.write(".claude/projects/-x/s1.jsonl", '{"a": 1}\n{"cut\nnot json\n{"b": 2}\n')
        self.assertEqual(list(chats.read_jsonl(path)), [{"a": 1}, {"b": 2}])
        self.assertEqual(chats.parse("[1, 2]"), {})
        self.assertEqual(chats.parse("[" * 100_000 + "]" * 100_000), {})

    def test_a_codex_files_first_line_is_read_only_so_far(self):
        # its first line names the folder; one with no end would be read whole, hundreds of megabytes
        meta = json.dumps({"type": "session_meta", "payload": {"id": "c1", "cwd": "/repo/app"}})
        self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", meta[:-1] + ', "x": "' + "y" * 9_000_000 + '"}\n')
        self.assertEqual(list(chats.folder_files("codex", "/repo/app")), [])

    def test_the_replies_of_a_long_chat_are_read_from_its_end(self):
        lines = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "the first reply"}]}},
                 {"type": "user", "message": {"content": "x" * 20_000_000}},
                 {"type": "assistant", "message": {"content": [{"type": "text", "text": "the last reply"}]}}]
        path = self.write(".claude/projects/-x/s1.jsonl", "".join(json.dumps(entry) + "\n" for entry in lines))
        tail = [text for _, text in chats.messages("claude", path, tail=chats.TAIL)]
        self.assertEqual(tail, ["the last reply"])
        self.assertIn("the first reply", [text for _, text in chats.messages("claude", path)])

    def test_a_pipe_is_not_read(self):
        pipe = os.path.join(self.home, "pipe.jsonl")
        os.mkfifo(pipe)
        with self.assertRaises(OSError):
            finished(self, lambda: list(chats.read_jsonl(pipe)))

    def test_a_folders_files_are_the_readable_ones(self):
        meta = json.dumps({"type": "session_meta", "payload": {"id": "c1", "cwd": "/repo/app"}}) + "\n"
        codex = self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", meta)
        claude = self.write(".claude/projects/-repo-app/s1.jsonl", "{}\n")
        for folder in (".codex/sessions/2026/10/22/rollout-", ".claude/projects/-repo-app/"):
            os.mkfifo(os.path.join(self.home, folder + "pipe.jsonl"))
            os.symlink(os.path.join(self.home, "gone"), os.path.join(self.home, folder + "gone.jsonl"))
        os.chmod(self.write(".codex/sessions/2026/10/22/rollout-2-c2.jsonl", meta), 0)
        self.assertEqual(finished(self, lambda: list(chats.folder_files("codex", "/repo/app"))), [codex])
        self.assertEqual(finished(self, lambda: list(chats.folder_files("claude", "/repo/app"))), [claude])


class Transcript(unittest.TestCase):
    """A whole chat for Copy chat: the user's prompts and the agent's replies, nothing else."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        set_env(self, HOME=self.dir)

    def write(self, name, *entries):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(jsonl(entry) for entry in entries))
        return path

    def test_claude_the_prompts_and_replies_without_tools_helpers_or_system_text(self):
        path = self.write("s1.jsonl",
                          {"type": "user", "message": {"content": "Fix the login"}},
                          {"type": "user", "isMeta": True, "message": {"content": "Caveat: local commands below"}},
                          {"type": "user", "message": {"content": "<command-name>/clear</command-name>"}},
                          {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
                          {"type": "user", "message": {"content": [{"type": "tool_result", "content": "file"}]}},
                          {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "text",
                                                                                              "text": "helper"}]}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "Found it."}]}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "**Fixed.**"}]}},
                          {"type": "user", "message": {"content": "[Request interrupted by user]"}},
                          {"type": "summary", "summary": "a title"})
        self.assertEqual(list(chats.messages("claude", path)),
                         [("user", "Fix the login"), ("assistant", "Found it."), ("assistant", "**Fixed.**")])

    def test_claude_without_a_compactions_summary(self):
        # the summary Claude writes itself when a chat is compacted, in the user's place: the chat so far, again
        path = self.write("s1.jsonl",
                          {"type": "user", "uuid": "u1", "message": {"content": "Fix the login"}},
                          {"type": "assistant", "uuid": "u2", "message": {"content": [{"type": "text",
                                                                                       "text": "Found it."}]}},
                          {"type": "system", "subtype": "compact_boundary", "uuid": "u3"},
                          {"type": "user", "uuid": "u4", "isCompactSummary": True,
                           "message": {"content": "This session is being continued from a previous one."}},
                          {"type": "user", "uuid": "u5", "message": {"content": "And the logout"}})
        self.assertEqual(list(chats.messages("claude", path)),
                         [("user", "Fix the login"), ("assistant", "Found it."), ("user", "And the logout")])

    def test_claude_a_message_written_again_is_there_once(self):
        # a compaction writes the messages it keeps again after its summary, under the ids they had
        said = [{"type": "user", "uuid": "u1", "message": {"content": "Fix the login"}},
                {"type": "assistant", "uuid": "u2", "message": {"content": [{"type": "text", "text": "Found it."},
                                                                             {"type": "text", "text": "Fixed."}]}}]
        path = self.write("s1.jsonl", *said, {"type": "system", "subtype": "compact_boundary", "uuid": "u3"}, *said,
                          {"type": "user", "message": {"content": "Fix the login"}},      # said again: no id, kept
                          {"type": "user", "uuid": ["u1"], "message": {"content": "Thanks"}})
        self.assertEqual(list(chats.messages("claude", path)),
                         [("user", "Fix the login"), ("assistant", "Found it."), ("assistant", "Fixed."),
                          ("user", "Fix the login"), ("user", "Thanks")])

    def test_codex_the_prompts_and_replies_without_its_instructions(self):
        path = self.write("rollout.jsonl",
                          {"type": "session_meta", "payload": {"id": "c1"}},
                          {"payload": {"type": "message", "role": "user", "content": [
                              {"type": "input_text", "text": "# AGENTS.md instructions"},
                              {"type": "input_text", "text": "<environment_context>…</environment_context>"}]}},
                          {"payload": {"type": "message", "role": "user", "content": [{"type": "input_text",
                                                                                      "text": "Price list"}]}},
                          {"payload": {"type": "function_call", "name": "shell"}},
                          {"payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text",
                                                                                           "text": "Done."}]}})
        self.assertEqual(list(chats.messages("codex", path)), [("user", "Price list"), ("assistant", "Done.")])

    def test_as_markdown_the_title_then_each_turn_under_who_said_it(self):
        self.write(".claude/projects/-repo-app/s1.jsonl",
                          {"type": "user", "message": {"content": "Fix the login"}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "Found it."}]}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "**Fixed.**"}]}})
        item = chats.Chat("claude", "s1", "Login fix", "/repo/app", 0)
        self.assertEqual(chats.markdown(item),
                         "# Login fix\n\n**You**\n\nFix the login\n\n**Claude**\n\nFound it.\n\n**Fixed.**\n")
        self.assertIsNone(chats.markdown(chats.Chat("claude", "gone", "Gone", "/repo/app", 0)))

    def test_as_markdown_no_control_character_but_line_breaks_and_tabs(self):
        # pasted into a terminal, a code a chat holds would run there: set the title, write the clipboard
        self.write(".claude/projects/-repo-app/s1.jsonl",
                   {"type": "user", "message": {"content": "Fix \x1b]2;owned\x07it"}},
                   {"type": "assistant", "message": {"content": [{"type": "text", "text": "a\tb\x9b\x1b[31m"}]}})
        item = chats.Chat("claude", "s1", "Login\x1b]0;x\x07 fix", "/repo/app", 0)
        self.assertEqual(chats.markdown(item),
                         "# Login]0;x fix\n\n**You**\n\nFix ]2;ownedit\n\n**Claude**\n\na\tb[31m\n")


# OpenCode 2.4's tables as far as Chats reads them, with their own columns' names and types
OPENCODE_SCHEMA = """
create table if not exists session_v2 (id text primary key, project_id text not null, parent_id text,
  slug text not null, directory text not null, title text, version text not null, time_created integer not null,
  time_updated integer not null, time_archived integer);
create table if not exists session_message (id text primary key, session_id text not null, type text not null,
  seq integer not null, time_created integer not null, time_updated integer not null, data text not null);
create table if not exists session_part (message_id text not null, session_id text not null, ordinal integer not null,
  type text not null, call_id text, time_created integer not null, time_updated integer not null, data text not null,
  primary key (message_id, ordinal));
"""


class OpenCode(unittest.TestCase):
    """OpenCode's chats as its database holds them (an invented one in V2's tables), only read: named, listed with the
    others, marked running, copied; never deleted from here."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home, XDG_DATA_HOME=None)
        self.state = os.path.join(self.home, ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
        self.db = os.path.join(self.home, ".local", "share", "opencode", "opencode.db")

    def session(self, id, updated, *turns, title=None, parent=None, archived=None, folder="/Users/dev/lumen-api"):
        """A chat in OpenCode's database changed at UPDATED (ms), in WAL mode as OpenCode keeps it: TURNS each (role,
        text), the user's text in its message, a reply's in a text part."""
        os.makedirs(os.path.dirname(self.db), exist_ok=True)
        with contextlib.closing(sqlite3.connect(self.db)) as db, db:
            db.execute("pragma journal_mode = wal")
            db.executescript(OPENCODE_SCHEMA)
            db.execute("insert into session_v2 values (?, 'p1', ?, 'misty-forest', ?, ?, '2.4.1', ?, ?, ?)",
                       (id, parent, folder, title, updated - 1000, updated, archived))
            for n, (role, said) in enumerate(turns):
                data = {"text": said, "files": []} if role == "user" else {"agent": "build", "finish": "stop"}
                db.execute("insert into session_message values (?, ?, ?, ?, ?, ?, ?)",
                           (f"msg_{id}_{n}", id, role, n * 3 + 1, updated, updated, json.dumps(data)))
                if role == "assistant":
                    db.execute("insert into session_part values (?, ?, 0, 'text', null, ?, ?, ?)",
                               (f"msg_{id}_{n}", id, updated, updated, json.dumps({"type": "text", "text": said})))

    def listed(self, agents=()):
        return {c.id: c for c in chats.local(self.state, agents) if c.agent == "opencode"}

    def test_a_chat_goes_by_a_name_given_in_herdr_its_title_or_its_first_prompt(self):
        self.session("ses_a1", 1795600000000, ("user", "Where is the health check?"),
                     ("assistant", "In src/health.py."), title="Health check endpoint")
        self.session("ses_b2", 1795600100000, ("user", "Add a readiness probe\nthen test it"))
        self.session("ses_c3", 1795600200000, ("user", "Rate limits"), title="Rate limiter")
        chats.name_session("ses_c3", "Throttle")
        found = self.listed()
        self.assertEqual({k: (c.title, c.folder, c.time) for k, c in found.items()},
                         {"ses_a1": ("Health check endpoint", "/Users/dev/lumen-api", 1795600000.0),
                          "ses_b2": ("Add a readiness probe", "/Users/dev/lumen-api", 1795600100.0),
                          "ses_c3": ("Throttle", "/Users/dev/lumen-api", 1795600200.0)})

    def test_its_subagents_archived_and_empty_chats_are_no_rows(self):
        self.session("ses_a1", 1795600000000, ("user", "Fix the login"))
        self.session("ses_s1", 1795600000500, ("user", "Search the code"), parent="ses_a1")     # a subagent's
        self.session("ses_r1", 1795600001000, ("user", "Nightly report"), archived=1795600002000)
        self.session("ses_e1", 1795600003000, title="New session")                              # nothing asked yet
        self.assertEqual(list(self.listed()), ["ses_a1"])

    def test_it_is_listed_with_the_others_the_newest_first_and_marked_running(self):
        path = os.path.join(self.home, ".claude", "projects", "-Users-dev-lumen-api", "s1.jsonl")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsonl({"type": "user", "isSidechain": False, "cwd": "/Users/dev/lumen-api",
                           "message": {"content": "Fix the login"}}))
        os.utime(path, (1795600050, 1795600050))
        self.session("ses_a1", 1795600100000, ("user", "Health check"))
        self.session("ses_b2", 1795600000000, ("user", "Readiness probe"))
        agents = [{"agent": "opencode", "agent_status": "working", "pane_id": "p1", "cwd": "/Users/dev/lumen-api"}]
        found = chats.local(self.state, agents)
        self.assertEqual([(c.agent, c.id, c.state, c.pane) for c in found],
                         [("opencode", "ses_a1", "working", "p1"), ("claude", "s1", "", ""),
                          ("opencode", "ses_b2", "", "")])               # its newest in the folder runs
        told = [{"agent": "opencode", "agent_status": "blocked", "pane_id": "p2", "agent_session": {"value": "ses_b2"}}]
        self.assertEqual([(c.id, c.state) for c in chats.local(self.state, told) if c.state], [("ses_b2", "blocked")])

    def test_copy_chat_is_its_prompts_and_replies_in_order(self):
        self.session("ses_a1", 1795600000000, ("user", "Where is the health check?"),
                     ("assistant", "In src/health.py."), ("user", "And the readiness probe?"),
                     ("assistant", "Not there yet."), title="Health check")
        item = self.listed()["ses_a1"]
        self.assertEqual(chats.markdown(item), "# Health check\n\n**You**\n\nWhere is the health check?\n\n"
                         "**OpenCode**\n\nIn src/health.py.\n\n**You**\n\nAnd the readiness probe?\n\n"
                         "**OpenCode**\n\nNot there yet.\n")
        self.assertIsNone(chats.markdown(chats.Chat("opencode", "ses_gone", "Gone", "/Users/dev/lumen-api", 0)))

    def test_its_database_is_only_read(self):
        self.session("ses_a1", 1795600000000, ("user", "Health check"))
        folder = os.path.dirname(self.db)
        before = {name: read(os.path.join(folder, name)) for name in ("opencode.db", "opencode.db-wal")}
        self.listed()
        chats.markdown(self.listed()["ses_a1"])
        self.assertEqual({name: read(os.path.join(folder, name)) for name in before}, before)

    def test_no_database_or_another_kind_of_file_lists_no_opencode_chat(self):
        self.assertEqual(self.listed(), {})
        os.makedirs(os.path.dirname(self.db))
        with open(self.db, "w", encoding="utf-8") as f:
            f.write("not a database")
        self.assertEqual(self.listed(), {})
        os.remove(self.db)
        with contextlib.closing(sqlite3.connect(self.db)) as db, db:      # OpenCode 1's tables: none of V2's
            db.execute("create table session (id text primary key, directory text, title text)")
        self.assertEqual(self.listed(), {})

    def test_it_is_found_where_xdg_data_home_says(self):
        set_env(self, XDG_DATA_HOME=os.path.join(self.home, "data"))
        self.db = os.path.join(self.home, "data", "opencode", "opencode.db")
        self.session("ses_a1", 1795600000000, ("user", "Health check"))
        self.assertEqual(list(self.listed()), ["ses_a1"])

    def test_one_is_never_deleted_from_here(self):
        self.session("ses_a1", 1795600000000, ("user", "Health check"))
        with self.assertRaises(fileops.Refused):
            chats.delete(self.state, "opencode", "ses_a1")
        self.assertEqual(list(self.listed()), ["ses_a1"])

    def test_the_cli_lists_and_copies_it(self):
        self.session("ses_a1", 1795600000000, ("user", "Health check"), ("assistant", "In src/health.py."))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(chats.main(["chats.py", "list", "[]", "{}"]), 0)
        self.assertEqual([(c["agent"], c["id"]) for c in json.loads(out.getvalue())["chats"]], [("opencode", "ses_a1")])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(chats.main(["chats.py", "markdown", "opencode", "ses_a1"]), 0)
        self.assertIn("**OpenCode**\n\nIn src/health.py.", json.loads(out.getvalue())["markdown"])


if __name__ == "__main__":
    unittest.main()
