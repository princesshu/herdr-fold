"""Tests for core/tokens.py in a temporary HOME: every message's tokens from Claude's sessions, their subagents'
files and Codex's token records, each message once, kept by the hour in an index that reads a file only where it grew;
nothing of the agents' files written. The sessions are invented, in the shapes measured."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import tokens  # noqa: E402

HOUR = 3600
TEN = 1794564000                # Friday, 13 November 2026, 10:00 UTC
SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
OTHER = "7a1b2c3d-4e5f-4a6b-9c8d-0e1f2a3b4c5d"
THREAD = "0199a1b2-c3d4-7e5f-8a6b-9c0d1e2f3a4b"
FOLDER = "/Users/dev/lumen-api"
OPUS, HAIKU, GPT = "claude-opus-5-5", "claude-haiku-5-5", "gpt-6-astra"
KINDS = ("input", "write_5m", "write_1h", "read", "output", "reasoning", "searches")


def line(entry):
    """ENTRY as the agents write a line: compact JSON."""
    return json.dumps(entry, separators=(",", ":")) + "\n"


def stamp(minute, hour=10):
    return f"2026-11-13T{hour:02d}:{minute:02d}:00.000Z"


def usage(input=0, write_5m=0, write_1h=0, read=0, output=0, thinking=0, searches=0):
    """A Claude message's usage, as Claude 2.1.325 writes it."""
    return {"input_tokens": input, "cache_creation_input_tokens": write_5m + write_1h,
            "cache_read_input_tokens": read, "output_tokens": output,
            "output_tokens_details": {"thinking_tokens": thinking},
            "server_tool_use": {"web_search_requests": searches, "web_fetch_requests": 0}, "service_tier": "standard",
            "cache_creation": {"ephemeral_1h_input_tokens": write_1h, "ephemeral_5m_input_tokens": write_5m},
            "speed": "standard"}


def said(id, minute=0, model=OPUS, session=SESSION, hour=10, sidechain=False, folder=FOLDER, **counts):
    """One line of a Claude message: an assistant entry with the message's usage."""
    return line({"parentUuid": None, "isSidechain": sidechain,
                 "message": {"model": model, "id": id, "type": "message", "role": "assistant",
                             "content": [{"type": "text", "text": "Done."}], "usage": usage(**counts)},
                 "requestId": "req_011", "type": "assistant", "uuid": "0d0c0b0a-0908-4706-8504-030201000000",
                 "timestamp": stamp(minute, hour), "cwd": folder, "sessionId": session})


def asked(text="Fix the page past the last one", minute=0):
    return line({"parentUuid": None, "isSidechain": False, "type": "user", "timestamp": stamp(minute),
                 "message": {"role": "user", "content": text}, "cwd": FOLDER, "sessionId": SESSION})


def record(response, minute=0, turn="turn-1", hour=10, **counts):
    """A Codex response's token record, as Codex 0.166 writes it."""
    counts = {"input_tokens": 0, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "output_tokens": 0,
              "reasoning_output_tokens": 0, **counts}
    counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
    return line({"timestamp": stamp(minute, hour), "ordinal": 7, "type": "token_usage_record",
                 "payload": {"thread_id": THREAD, "turn_id": turn, "session_id": THREAD, "response_id": response,
                             "usage": counts, "turn_token_usage": counts, "thread_token_usage": counts}})


def turn(model, id="turn-1", minute=0):
    return line({"timestamp": stamp(minute), "type": "turn_context",
                 "payload": {"turn_id": id, "cwd": FOLDER, "model": model, "effort": "high"}})


def meta(source="cli", id=THREAD):
    return line({"timestamp": stamp(0), "type": "session_meta",
                 "payload": {"id": id, "timestamp": stamp(0), "cwd": FOLDER, "originator": "codex_cli_rs",
                             "cli_version": "0.166.0", "instructions": None, "source": source}})


def counts(message):
    return tuple(message[kind] for kind in KINDS)


class Home(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)
        self.state = os.path.join(self.home, ".local", "state", "herdr-fold")

    def write(self, rel, text, mode="w"):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode, encoding="utf-8") as f:
            f.write(text)
        return path

    def session(self, text, session=SESSION, mode="w"):
        return self.write(f".claude/projects/-Users-dev-lumen-api/{session}.jsonl", text, mode)

    def sub(self, text, agent="a1b2c3", kind="Explore", session=SESSION):
        folder = f".claude/projects/-Users-dev-lumen-api/{session}/subagents"
        if kind is not None:
            self.write(f"{folder}/agent-{agent}.meta.json", json.dumps({
                "agentType": kind, "isBuiltIn": True, "description": "Look for the routes",
                "toolUseId": "toolu_01", "spawnDepth": 1}))
        return self.write(f"{folder}/agent-{agent}.jsonl", text)

    def rollout(self, text, id=THREAD, mode="w"):
        return self.write(f".codex/sessions/2026/11/13/rollout-2026-11-13T10-00-00-{id}.jsonl", text, mode)

    def rows(self, since=0, until=1 << 40):
        return tokens.rows(tokens.load(self.state), since, until)

    def total(self, kind="output"):
        return sum(row[kind] for row in self.rows())


class ClaudeMessages(Home):
    def test_a_messages_repeated_lines_are_counted_once(self):
        # a message is written a line per part, its usage on each: the last line's is the whole
        path = self.session(asked() + said("msg_01A", output=4, input=10) + said("msg_01A", output=120, input=10)
                            + said("msg_01B", 1, output=30, input=5))
        found, offset = tokens.claude_messages(path)
        self.assertEqual([(one["id"], one["input"], one["output"]) for one in found],
                         [("msg_01A", 10, 120), ("msg_01B", 5, 30)])
        self.assertEqual(offset, os.path.getsize(path))

    def test_each_kind_of_token_is_told_apart(self):
        path = self.session(said("msg_01A", 5, input=7, write_5m=300, write_1h=900, read=4000, output=250,
                                 thinking=200, searches=2))
        (one,), _ = tokens.claude_messages(path)
        self.assertEqual(counts(one), (7, 300, 900, 4000, 250, 200, 2))
        self.assertEqual((one["agent"], one["session"], one["folder"], one["model"], one["sub"], one["at"]),
                         ("claude", SESSION, FOLDER, OPUS, None, TEN + 5 * 60))

    def test_an_earlier_claudes_cache_write_is_the_five_minute_one(self):
        entry = json.loads(said("msg_01A", write_5m=40))
        del entry["message"]["usage"]["cache_creation"]
        (one,), _ = tokens.claude_messages(self.session(line(entry)))
        self.assertEqual((one["write_5m"], one["write_1h"]), (40, 0))

    def test_a_long_prompt_tells_the_step_it_is_over(self):
        # some models cost more past a prompt's size (LiteLLM's above_272k_tokens): the largest step it is over
        path = self.session(said("msg_01A", input=1000, read=90_000) + said("msg_01B", input=1, read=100_000)
                            + said("msg_01C", write_1h=250_000, read=30_000))
        found, _ = tokens.claude_messages(path)
        self.assertEqual([one["over"] for one in found], [0, 100, 272])

    def test_only_an_assistants_own_lines_count(self):
        # Claude's own made-up answers ("<synthetic>"), a prompt quoting a line, a damaged line: none is a message
        quoted = asked('{"type":"assistant","message":{"id":"msg_01Z","usage":{"output_tokens":9}}}')
        path = self.session(quoted + said("uuid-1", model="<synthetic>", output=5) + '{"type":"assistant","mess\n'
                            + line({"type": "assistant", "message": "none"}) + said("msg_01A", output=3))
        found, _ = tokens.claude_messages(path)
        self.assertEqual([one["id"] for one in found], ["msg_01A"])

    def test_a_sub_agents_file_tells_its_type_and_its_parents_session(self):
        path = self.sub(said("msg_01S", 2, model=HAIKU, sidechain=True, input=50, output=20))
        (one,), _ = tokens.claude_messages(path)
        self.assertEqual((one["sub"], one["session"], one["model"], one["output"]), ("Explore", SESSION, HAIKU, 20))

    def test_a_sub_agent_with_no_meta_file_is_still_one(self):
        (one,), _ = tokens.claude_messages(self.sub(said("msg_01S", sidechain=True, output=1), kind=None))
        self.assertEqual(one["sub"], "agent")

    def test_a_sub_agents_type_is_shown_as_text(self):
        (one,), _ = tokens.claude_messages(self.sub(said("msg_01S", output=1), kind="Ex\x1b[31mplore\n" + "x" * 90))
        self.assertEqual(one["sub"], ("Ex[31mplore" + "x" * 90)[:tokens.NAME])

    def test_a_half_written_last_line_waits(self):
        whole = said("msg_01A", output=3)
        path = self.session(whole + said("msg_01B", output=5)[:-20])
        found, offset = tokens.claude_messages(path)
        self.assertEqual(([one["id"] for one in found], offset), (["msg_01A"], len(whole)))
        self.session(said("msg_01B", output=5)[-20:], mode="a")
        found, offset = tokens.claude_messages(path, offset)
        self.assertEqual(([one["id"] for one in found], offset), (["msg_01B"], os.path.getsize(path)))

    def test_a_call_reads_so_many_bytes_and_ends_on_a_whole_line(self):
        first, second = said("msg_01A", output=3), said("msg_01B", output=5)
        path = self.session(first + second)
        found, offset = tokens.claude_messages(path, 0, most=10)
        self.assertEqual(([one["id"] for one in found], offset), (["msg_01A"], len(first)))
        found, offset = tokens.claude_messages(path, offset, most=10)
        self.assertEqual(([one["id"] for one in found], offset), (["msg_01B"], len(first + second)))

    def test_a_pipe_named_like_a_session_is_refused(self):
        path = os.path.join(self.home, "pipe.jsonl")
        os.mkfifo(path)
        with self.assertRaises(OSError):
            tokens.claude_messages(path)


class CodexMessages(Home):
    def test_cached_input_is_taken_out_of_the_input(self):
        path = self.rollout(meta() + turn(GPT) + record("resp_1", 3, input_tokens=1000, cached_input_tokens=800,
                                                        cache_write_input_tokens=50, output_tokens=90,
                                                        reasoning_output_tokens=60))
        (one,), offset, model = tokens.codex_messages(path)
        self.assertEqual(counts(one), (200, 50, 0, 800, 90, 60, 0))
        self.assertEqual((one["agent"], one["id"], one["session"], one["folder"], one["model"], one["sub"], one["at"]),
                         ("codex", "resp_1", THREAD, FOLDER, GPT, None, TEN + 3 * 60))
        self.assertEqual((offset, model), (os.path.getsize(path), GPT))

    def test_a_record_is_its_turns_model(self):
        path = self.rollout(meta() + turn("gpt-6.1-sol") + record("resp_1", output_tokens=1)
                            + turn(GPT, "turn-2") + record("resp_2", turn="turn-2", output_tokens=2))
        found, _, _ = tokens.codex_messages(path)
        self.assertEqual([(one["model"], one["output"]) for one in found], [("gpt-6.1-sol", 1), (GPT, 2)])

    def test_reading_on_keeps_the_turns_model(self):
        head = meta() + turn(GPT)
        path = self.rollout(head)
        found, offset, model = tokens.codex_messages(path)
        self.assertEqual((found, offset, model), ([], len(head), GPT))
        self.rollout(record("resp_1", output_tokens=4), mode="a")
        (one,), _, _ = tokens.codex_messages(path, offset, model=model)
        self.assertEqual((one["model"], one["output"], one["folder"]), (GPT, 4, FOLDER))

    def test_a_helpers_file_tells_what_it_is(self):
        # Codex's own helper (its approvals reviewer) and an agent a thread started, that one in its parent's session
        helper = self.rollout(meta({"subagent": {"other": "guardian"}}, OTHER) + turn("codex-auto-review")
                              + record("resp_1", output_tokens=1), id=OTHER)
        (one,), _, _ = tokens.codex_messages(helper)
        self.assertEqual((one["sub"], one["session"], one["model"]), ("guardian", OTHER, "codex-auto-review"))
        spawned = {"subagent": {"thread_spawn": {"agent_nickname": "Wren", "agent_path": "x", "agent_role": None,
                                                 "depth": 1, "parent_thread_id": THREAD}}}
        (one,), _, _ = tokens.codex_messages(self.rollout(meta(spawned, OTHER) + turn(GPT)
                                                          + record("resp_2", output_tokens=1), id=OTHER))
        self.assertEqual((one["sub"], one["session"]), ("agent", THREAD))

    def test_a_long_prompt_counts_its_cached_part(self):
        path = self.rollout(meta() + turn(GPT) + record("resp_1", input_tokens=300_000, cached_input_tokens=299_000))
        (one,), _, _ = tokens.codex_messages(path)
        self.assertEqual((one["over"], one["input"], one["read"]), (272, 1000, 299_000))

    def test_more_reasoning_than_output_is_the_output(self):
        path = self.rollout(meta() + turn(GPT) + record("resp_1", output_tokens=5, reasoning_output_tokens=9,
                                                        input_tokens=3, cached_input_tokens=8))
        (one,), _, _ = tokens.codex_messages(path)
        self.assertEqual((one["reasoning"], one["input"], one["read"]), (5, 0, 3))


class Index(Home):
    def test_the_first_look_reads_every_file_into_hours(self):
        self.session(said("msg_01A", 5, input=10, output=100) + said("msg_01B", 50, output=20)
                     + said("msg_01C", 0, hour=11, model=HAIKU, output=7))
        self.sub(said("msg_01S", 30, model=HAIKU, sidechain=True, output=40, read=900))
        self.rollout(meta() + turn(GPT) + record("resp_1", 10, input_tokens=500, cached_input_tokens=100,
                                                 output_tokens=60))
        done = tokens.index(self.state, self.home)
        self.assertEqual((done["files"], done["left"]), (3, 0))
        rows = sorted(self.rows(), key=lambda row: (row["agent"], row["sub"] or "", row["hour"]))
        self.assertEqual([(row["agent"], row["model"], row["sub"], row["session"], row["folder"], row["hour"],
                           row["output"], row["messages"]) for row in rows],
                         [("claude", OPUS, None, SESSION, FOLDER, TEN, 120, 2),
                          ("claude", HAIKU, None, SESSION, FOLDER, TEN + HOUR, 7, 1),
                          ("claude", HAIKU, "Explore", SESSION, FOLDER, TEN, 40, 1),
                          ("codex", GPT, None, THREAD, FOLDER, TEN, 60, 1)])
        self.assertEqual((rows[0]["input"], rows[2]["read"], rows[3]["input"], rows[3]["read"]), (10, 900, 400, 100))

    def test_rows_are_the_hours_asked_for(self):
        self.session(said("msg_01A", 59, output=1) + said("msg_01B", 0, hour=11, output=2)
                     + said("msg_01C", 0, hour=12, output=4))
        tokens.index(self.state, self.home)
        self.assertEqual(sorted(row["output"] for row in self.rows(TEN + HOUR, TEN + 2 * HOUR)), [2])
        self.assertEqual(sorted(row["output"] for row in self.rows(TEN, TEN + 2 * HOUR)), [1, 2])

    def test_a_file_that_did_not_change_is_not_opened_again(self):
        self.session(said("msg_01A", output=1))
        self.rollout(meta() + turn(GPT) + record("resp_1", output_tokens=1))
        tokens.index(self.state, self.home)
        with mock.patch.object(tokens, "open_regular", side_effect=AssertionError("opened")):
            done = tokens.index(self.state, self.home)
        self.assertEqual((done["read"], self.total()), (0, 2))

    def test_a_file_that_grew_is_read_on_from_where_it_stopped(self):
        first = said("msg_01A", output=1)
        path = self.session(first)
        tokens.index(self.state, self.home)
        self.session(said("msg_01B", output=2), mode="a")
        done = tokens.index(self.state, self.home)
        self.assertEqual((done["read"], self.total()), (os.path.getsize(path) - len(first), 3))

    def test_a_message_that_went_on_after_a_look_is_still_one(self):
        # the look came between a message's lines: its later line's usage is the whole, the count stays one
        self.session(said("msg_01A", input=10, output=4))
        tokens.index(self.state, self.home)
        self.session(said("msg_01A", input=10, output=120), mode="a")
        tokens.index(self.state, self.home)
        (row,) = self.rows()
        self.assertEqual((row["input"], row["output"], row["messages"]), (10, 120, 1))

    def test_a_resumed_sessions_copied_messages_are_counted_once(self):
        # a session going on in a new file starts with the old one's messages, under their own ids
        old = said("msg_01A", output=10) + said("msg_01B", 1, output=20)
        self.session(old)
        os.utime(self.session(old), (TEN, TEN))
        self.session(old.replace(SESSION, OTHER) + said("msg_01C", 2, session=OTHER, output=40), session=OTHER)
        tokens.index(self.state, self.home)
        self.assertEqual(sorted((row["session"], row["output"]) for row in self.rows()),
                         [(SESSION, 30), (OTHER, 40)])
        tokens.index(self.state, self.home)
        self.assertEqual(self.total(), 70)

    def test_messages_a_file_holds_again_are_counted_once(self):
        # Claude writes lines again into the chat's own file, under their ids (what a compaction keeps, a chat taken
        # up in another folder): in the look that read them first, in a later one, and the file's last message too
        first = said("msg_01A", output=10, input=3) + said("msg_01B", 1, output=20, input=5)
        again = first.replace(FOLDER, FOLDER + "/.claude/worktrees/pager")
        boundary = line({"type": "system", "subtype": "compact_boundary", "timestamp": stamp(2), "sessionId": SESSION,
                         "compactMetadata": {"trigger": "auto", "preTokens": 180000}})
        self.session(first + again + boundary)
        tokens.index(self.state, self.home)
        self.assertEqual([(row["input"], row["output"], row["messages"]) for row in self.rows()], [(8, 30, 2)])
        self.session(again + said("msg_01C", 3, output=40) + again, mode="a")
        tokens.index(self.state, self.home)
        self.assertEqual([(row["input"], row["output"], row["messages"], row["folder"]) for row in self.rows()],
                         [(8, 70, 3, FOLDER)])

    def test_a_sub_agents_messages_are_not_its_parents_too(self):
        # the parent's file holds the Agent call's result with the subagent's totals: no message, never counted
        result = line({"type": "user", "timestamp": stamp(9), "sessionId": SESSION, "cwd": FOLDER,
                       "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_01"}]},
                       "toolUseResult": {"totalTokens": 960, "usage": usage(output=40, read=900)}})
        self.session(said("msg_01A", output=10) + result)
        self.sub(said("msg_01S", 5, model=HAIKU, sidechain=True, output=40, read=900))
        tokens.index(self.state, self.home)
        self.assertEqual(sorted((row["sub"] or "", row["output"], row["read"]) for row in self.rows()),
                         [("", 10, 0), ("Explore", 40, 900)])

    def test_a_file_that_is_gone_is_dropped(self):
        path = self.session(said("msg_01A", output=10))
        self.session(said("msg_01B", output=20), session=OTHER)
        tokens.index(self.state, self.home)
        os.unlink(path)
        tokens.index(self.state, self.home)
        self.assertEqual([(row["session"], row["output"]) for row in self.rows()], [(OTHER, 20)])
        self.assertEqual(list(tokens.load(self.state)["files"]), [self.session("", OTHER, "a")])

    def test_a_copy_is_counted_once_its_first_file_is_gone(self):
        old = said("msg_01A", output=10)
        os.utime(self.session(old), (TEN, TEN))
        self.session(old.replace(SESSION, OTHER) + said("msg_01C", 2, session=OTHER, output=40), session=OTHER)
        tokens.index(self.state, self.home)
        os.unlink(self.session("", mode="a"))
        tokens.index(self.state, self.home)
        self.assertEqual([(row["session"], row["output"]) for row in self.rows()], [(OTHER, 50)])

    def test_a_file_that_got_shorter_is_read_again_from_its_start(self):
        self.session(said("msg_01A", output=10) + said("msg_01B", 1, output=20))
        tokens.index(self.state, self.home)
        self.session(said("msg_01D", 2, output=5))
        tokens.index(self.state, self.home)
        self.assertEqual(self.total(), 5)

    def test_a_half_written_line_is_counted_when_it_is_whole(self):
        whole = said("msg_01B", 1, output=20)
        self.session(said("msg_01A", output=10) + whole[:30])
        tokens.index(self.state, self.home)
        self.assertEqual(self.total(), 10)
        self.session(whole[30:], mode="a")
        tokens.index(self.state, self.home)
        self.assertEqual(self.total(), 30)

    def test_a_look_reads_so_much_and_the_next_goes_on(self):
        self.session(said("msg_01A", output=10) + said("msg_01B", 1, output=20))
        self.session(said("msg_01C", output=40), session=OTHER)
        done = tokens.index(self.state, self.home, most=10)
        self.assertGreater(done["left"], 0)
        looks = 1
        while done["left"]:
            done, looks = tokens.index(self.state, self.home, most=10), looks + 1
        self.assertEqual((self.total(), looks), (70, 3))

    def test_a_codex_file_read_on_keeps_its_turns_model(self):
        self.rollout(meta() + turn(GPT) + record("resp_1", output_tokens=1))
        tokens.index(self.state, self.home)
        self.rollout(record("resp_2", 1, output_tokens=2) + record("resp_2", 1, output_tokens=2), mode="a")
        tokens.index(self.state, self.home)
        (row,) = self.rows()
        self.assertEqual((row["model"], row["output"], row["messages"]), (GPT, 3, 2))

    def test_nothing_is_written_but_the_index(self):
        self.session(said("msg_01A", output=10))
        self.sub(said("msg_01S", sidechain=True, output=1))
        self.rollout(meta() + turn(GPT) + record("resp_1", output_tokens=1))

        def tree(root):
            found = {}
            for folder, _, names in os.walk(root):
                for name in names:
                    path = os.path.join(folder, name)
                    with open(path, "rb") as f:
                        found[path] = (f.read(), os.stat(path).st_mtime_ns)
            return found

        before = {root: tree(os.path.join(self.home, root)) for root in (".claude", ".codex")}
        tokens.index(self.state, self.home)
        self.assertEqual({root: tree(os.path.join(self.home, root)) for root in before}, before)
        self.assertEqual(sorted(os.listdir(self.state)), ["usage-index.json", "usage-index.json.lock"])
        self.assertEqual(os.stat(os.path.join(self.state, "usage-index.json")).st_mode & 0o777, 0o600)

    def test_another_versions_index_is_not_read(self):
        self.session(said("msg_01A", output=10))
        tokens.index(self.state, self.home)
        path = os.path.join(self.state, "usage-index.json")
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**kept, "version": kept["version"] + 1}, f)
        self.assertEqual(tokens.load(self.state)["files"], {})
        tokens.index(self.state, self.home)
        self.assertEqual(self.total(), 10)

    def test_a_damaged_index_is_as_none(self):
        os.makedirs(self.state)
        for text in ("{", "[]", json.dumps({"version": tokens.VERSION, "files": {"x": 3, "y": {"hours": {"z": 1}}}})):
            with open(os.path.join(self.state, "usage-index.json"), "w", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(self.rows(), [])

    def test_the_command_reads_and_tells_what_is_left(self):
        self.session(said("msg_01A", output=10))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tokens.main(["tokens.py", "index"]), 0)
        self.assertEqual(json.loads(out.getvalue()), {"files": 1, "read": len(said("msg_01A", output=10)), "left": 0})
        self.assertEqual(self.total(), 10)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(tokens.main(["tokens.py", "nope"]), 2)
        self.assertIn("usage: tokens.py", err.getvalue())


if __name__ == "__main__":
    unittest.main()
