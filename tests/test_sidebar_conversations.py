"""Tests for conversations.py in a temporary HOME: the Claude Code and Codex conversations with title, folder, time and
state; a file read again only where it grew, unreadable files and damaged lines skipped, none of their files written."""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, finished, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import conversations  # noqa: E402


def read(path):
    with open(path, "rb") as f:
        return f.read()


def line(entry):
    return json.dumps(entry, separators=(",", ":")) + "\n"          # the way Claude and Codex write their lines


def prompt(text, sidechain=False):
    return line({"type": "user", "isSidechain": sidechain, "cwd": "/repo/app", "message": {"content": text}})


class Conversations(unittest.TestCase):
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
            f.write(line({"type": "session_meta", "payload": meta}) + "".join(lines))
        if changed:
            os.utime(path, (changed, changed))
        return path

    def listed(self, agents=()):
        return {c.id: c for c in conversations.local(self.state, agents)}

    def test_a_claude_conversation_goes_by_its_rename_its_ai_title_or_its_first_prompt(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Fix the login"), line({"type": "ai-title", "aiTitle": "Login redirect fix"}))
        self.claude("s3", prompt("Fix the login"), line({"type": "ai-title", "aiTitle": "Login redirect fix"}),
                    line({"type": "custom-title", "customTitle": "safari"}))
        found = self.listed()
        self.assertEqual({k: c.title for k, c in found.items()},
                         {"s1": "Fix the login", "s2": "Login redirect fix", "s3": "safari"})
        self.assertEqual({(c.agent, c.folder, c.state) for c in found.values()}, {("claude", "/repo/app", "")})

    def test_the_index_keeps_no_more_of_a_prompt_than_a_row_can_show(self):
        # the index is the plugin's own copy of every conversation's start: a whole pasted prompt does not belong there
        self.claude("s1", prompt("Fix the login " + "x" * 5000))
        self.listed()
        with open(os.path.join(self.state, conversations.INDEX)) as f:
            kept = [entry.get("prompt") or "" for entry in json.load(f)["files"].values()]
        self.assertEqual([len(text) <= conversations.PROMPT for text in kept], [True])
        self.assertTrue(kept[0].startswith("Fix the login"))

    def test_a_claude_file_without_a_prompt_is_no_conversation(self):
        self.claude("s1", prompt("<command-name>/clear</command-name>"), prompt("subagent's", sidechain=True))
        self.assertEqual(self.listed(), {})

    def test_a_codex_conversation_goes_by_its_thread_name_or_its_first_prompt(self):
        self.codex("a", {"id": "c1", "cwd": "/repo/app"},
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "<environment_context>x"}]}}),
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Price list\nmore"}]}}))
        self.codex("b", {"id": "c2", "cwd": "/repo/app"},
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Old prompt"}]}}))
        self.codex("c", {"id": "c3", "cwd": "/repo/app", "source": {"subagent": {"other": "guardian"}}},
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Review this"}]}}))
        index = os.path.join(self.home, ".codex", "session_index.jsonl")
        with open(index, "w") as f:
            f.write(line({"id": "c2", "thread_name": "Invoices"}))
        found = self.listed()
        self.assertEqual({k: (c.agent, c.title) for k, c in found.items()},
                         {"c1": ("codex", "Price list"), "c2": ("codex", "Invoices")})      # no helper (subagent)

    def test_a_name_given_in_herdr_wins(self):
        self.claude("s1", prompt("Fix the login"), line({"type": "custom-title", "customTitle": "safari"}))
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
        conversations.name_session("s1", "Login, by hand")
        self.assertEqual(json.loads(self.names()), {"s2": {"name": "Prices", "given": True},
                                                    "s1": {"name": "Login, by hand", "given": False}})
        self.assertEqual(self.listed()["s1"].title, "Login, by hand")

    def test_a_name_is_given_without_a_names_file_too(self):
        conversations.name_session("c1", "Invoices")
        self.assertEqual(json.loads(self.names()), {"c1": {"name": "Invoices", "given": False}})

    def test_a_names_file_that_cannot_be_read_is_left_as_it_is(self):
        self.names("{broken")
        with self.assertRaises(OSError):
            conversations.name_session("s1", "Login, by hand")
        self.assertEqual(self.names(), "{broken")

    def test_the_running_ones_have_herdrs_state_and_pane(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Old one"))
        self.codex("a", {"id": "c1", "cwd": "/repo/app"},
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Price list"}]}}))
        agents = [{"pane_id": "w1:p1", "agent": "claude", "agent_status": "working", "cwd": "/repo/app",
                   "agent_session": {"value": "s1"}},
                  {"pane_id": "w1:p4", "agent": "codex", "agent_status": "idle", "cwd": "/repo/app"}]
        found = self.listed(agents)
        self.assertEqual((found["s1"].state, found["s1"].pane), ("working", "w1:p1"))
        self.assertEqual((found["s2"].state, found["s2"].pane), ("", ""))
        # herdr was not told the Codex one's session: the newest Codex conversation of its folder is it
        self.assertEqual((found["c1"].state, found["c1"].pane), ("idle", "w1:p4"))

    def test_a_reopened_one_is_known_by_its_pane_before_herdr_knows_its_session(self):
        self.claude("s1", prompt("Fix the login"))
        self.claude("s2", prompt("Old one"))
        agents = [{"pane_id": "w1:p9", "agent": "claude", "agent_status": "blocked", "cwd": "/repo/app"}]
        found = {item.id: item for item in conversations.local(self.state, agents, {"w1:p9": "s2"})}
        self.assertEqual((found["s2"].state, found["s2"].pane), ("blocked", "w1:p9"))   # waits at a question
        self.assertEqual(found["s1"].state, "")                     # not the newest of its folder

    def test_a_growing_file_is_read_on_from_where_it_was_left(self):
        path = self.claude("s1", prompt("Fix the login"))
        self.assertEqual(self.listed()["s1"].title, "Fix the login")
        with open(os.path.join(self.state, conversations.INDEX)) as f:
            read = json.load(f)["files"][path]["offset"]
        self.assertEqual(read, os.path.getsize(path))
        self.claude("s1", line({"type": "custom-title", "customTitle": "safari"}))
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
        # a pipe named like a conversation would hold the column for good; an unreadable file or a folder would end it
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
        self.claude("s1", line({"type": "custom-title", "customTitle": {"x": 1}}),
                    line({"type": "ai-title", "aiTitle": 7}),
                    line({"type": "user", "isSidechain": False, "message": "a text, not an object", "cwd": 5}),
                    line({"type": "user", "isSidechain": False, "message": {"content": 5}}),
                    line({"type": "user", "isSidechain": False, "message": {"content": {"text": "x"}}}),
                    prompt("Fix the login"))
        self.codex("a", ["not", "an", "object"])
        self.codex("b", {"id": 5, "cwd": ["/repo"]})
        self.codex("c", {"id": "c1", "cwd": "/repo/app"},
                   line({"payload": {"type": "message", "role": "user", "content": "text, not parts"}}),
                   line({"payload": {"type": "message", "role": "user",
                                     "content": [{"type": "input_text", "text": "Fix the logout"}]}}))
        found = finished(self, self.listed)
        self.assertEqual({k: (c.title, c.folder) for k, c in found.items()},
                         {"s1": ("Fix the login", "/repo/app"), "c1": ("Fix the logout", "/repo/app")})

    def test_an_index_of_another_version_is_read_again(self):
        # what an earlier version kept, of other types or shape, is not taken for this one's: the files are read anew
        path = self.claude("s1", prompt("Fix the login"))
        os.makedirs(self.state)
        with open(os.path.join(self.state, conversations.INDEX), "w") as f:
            json.dump({path: {"offset": "x", "size": os.path.getsize(path), "mtime": os.path.getmtime(path),
                              "prompt": 5, "custom": ["a"]}}, f)
        self.assertEqual(self.listed()["s1"].title, "Fix the login")

    def test_nothing_is_written_where_the_conversations_are(self):
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


class Readers(unittest.TestCase):
    """Where the conversations live (shared with herdr-fold's Cmd+Shift+R and its formatted copy)."""

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
        self.assertEqual(conversations.claude_project_dir("/Users/a_b/my repo"),
                         os.path.join(self.home, ".claude", "projects", "-Users-a-b-my-repo"))

    def test_a_sessions_files_are_found_by_kind(self):
        claude = self.write(".claude/projects/-x/s1.jsonl", "{}\n")
        codex = self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", "{}\n")
        self.assertEqual(conversations.session_files("claude", "s1"), [claude])
        self.assertEqual(conversations.session_files("codex", "c1"), [codex])
        self.assertEqual(conversations.session_files("other", "s1"), [])

    def test_damaged_lines_are_skipped(self):
        path = self.write(".claude/projects/-x/s1.jsonl", '{"a": 1}\n{"cut\nnot json\n{"b": 2}\n')
        self.assertEqual(list(conversations.read_jsonl(path)), [{"a": 1}, {"b": 2}])
        self.assertEqual(conversations.parse("[1, 2]"), {})
        self.assertEqual(conversations.parse("[" * 100_000 + "]" * 100_000), {})

    def test_a_codex_files_first_line_is_read_only_so_far(self):
        # its first line names the folder; one with no end would be read whole, hundreds of megabytes
        meta = json.dumps({"type": "session_meta", "payload": {"id": "c1", "cwd": "/repo/app"}})
        self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", meta[:-1] + ', "x": "' + "y" * 9_000_000 + '"}\n')
        self.assertEqual(list(conversations.folder_files("codex", "/repo/app")), [])

    def test_the_replies_of_a_long_conversation_are_read_from_its_end(self):
        lines = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "the first reply"}]}},
                 {"type": "user", "message": {"content": "x" * 20_000_000}},
                 {"type": "assistant", "message": {"content": [{"type": "text", "text": "the last reply"}]}}]
        path = self.write(".claude/projects/-x/s1.jsonl", "".join(json.dumps(entry) + "\n" for entry in lines))
        tail = [text for _, text in conversations.messages("claude", path, tail=conversations.TAIL)]
        self.assertEqual(tail, ["the last reply"])
        self.assertIn("the first reply", [text for _, text in conversations.messages("claude", path)])

    def test_a_pipe_is_not_read(self):
        pipe = os.path.join(self.home, "pipe.jsonl")
        os.mkfifo(pipe)
        with self.assertRaises(OSError):
            finished(self, lambda: list(conversations.read_jsonl(pipe)))

    def test_a_folders_files_are_the_readable_ones(self):
        meta = json.dumps({"type": "session_meta", "payload": {"id": "c1", "cwd": "/repo/app"}}) + "\n"
        codex = self.write(".codex/sessions/2026/10/22/rollout-1-c1.jsonl", meta)
        claude = self.write(".claude/projects/-repo-app/s1.jsonl", "{}\n")
        for folder in (".codex/sessions/2026/10/22/rollout-", ".claude/projects/-repo-app/"):
            os.mkfifo(os.path.join(self.home, folder + "pipe.jsonl"))
            os.symlink(os.path.join(self.home, "gone"), os.path.join(self.home, folder + "gone.jsonl"))
        os.chmod(self.write(".codex/sessions/2026/10/22/rollout-2-c2.jsonl", meta), 0)
        self.assertEqual(finished(self, lambda: list(conversations.folder_files("codex", "/repo/app"))), [codex])
        self.assertEqual(finished(self, lambda: list(conversations.folder_files("claude", "/repo/app"))), [claude])


class Transcript(unittest.TestCase):
    """A whole conversation for Copy conversation: the user's prompts and the agent's replies, nothing else."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, *entries):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(line(entry) for entry in entries))
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
        self.assertEqual(list(conversations.messages("claude", path)),
                         [("user", "Fix the login"), ("assistant", "Found it."), ("assistant", "**Fixed.**")])

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
        self.assertEqual(list(conversations.messages("codex", path)), [("user", "Price list"), ("assistant", "Done.")])

    def test_as_markdown_the_title_then_each_turn_under_who_said_it(self):
        path = self.write("s1.jsonl",
                          {"type": "user", "message": {"content": "Fix the login"}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "Found it."}]}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "**Fixed.**"}]}})
        item = conversations.Conversation("claude", "s1", "Login fix", "/repo/app", 0)
        self.assertEqual(conversations.markdown(item, path),
                         "# Login fix\n\n**You**\n\nFix the login\n\n**Claude**\n\nFound it.\n\n**Fixed.**\n")

    def test_as_markdown_no_control_character_but_line_breaks_and_tabs(self):
        # pasted into a terminal, a code a conversation holds would run there: set the title, write the clipboard
        path = self.write("s1.jsonl",
                          {"type": "user", "message": {"content": "Fix \x1b]2;owned\x07it"}},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": "a\tb\x9b\x1b[31m"}]}})
        item = conversations.Conversation("claude", "s1", "Login\x1b]0;x\x07 fix", "/repo/app", 0)
        self.assertEqual(conversations.markdown(item, path),
                         "# Login]0;x fix\n\n**You**\n\nFix ]2;ownedit\n\n**Claude**\n\na\tb[31m\n")


if __name__ == "__main__":
    unittest.main()
