"""Tests for rich_clipboard.py: text selected on screen → the answer's original Markdown excerpt → formatted clipboard.
Selections mimic Claude Code's drawing: two-space indent, "⏺ " first, boxed tables, wrapped lines, no Markdown marks.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import finished, set_attrs, set_env

import rich_clipboard as rc

ANSWER = ("""The color of the dots depends on **what the agent** is doing:

| Mark | Color | State |
|---|---|---|
| ● | yellow | **working** |
| ○ | green | **waiting**, and you have seen it |

- **Filled or hollow:** a filled dot means something is happening there, or it needs your attention. """
          """A hollow dot means all is calm.
- The colors come from the theme.

If you click the pane and type `claude --continue`, the last conversation goes on.

Details: [the herdr guide](https://herdr.dev/docs/agents/) and the README.

```bash
herdr workspace list
herdr agent list
```

Done.""")

TABLE_ON_SCREEN = """  ┌──────┬────────┬──────────────────────────────┐
  │ Mark │ Color  │            State             │
  ├──────┼────────┼──────────────────────────────┤
  │ ●    │ yellow │ working                      │
  ├──────┼────────┼──────────────────────────────┤
  │ ○    │ green  │ waiting, and you have seen it │
  └──────┴────────┴──────────────────────────────┘"""


class FindSource(unittest.TestCase):
    def test_whole_table_comes_back_as_markdown_table(self):
        self.assertEqual(rc.find_source(TABLE_ON_SCREEN, [ANSWER]),
                         "| Mark | Color | State |\n|---|---|---|\n| ● | yellow | **working** |\n"
                         "| ○ | green | **waiting**, and you have seen it |")

    def test_table_row_brings_the_header_along(self):
        sel = "  │ ○    │ green  │ waiting, and you have seen it │"
        self.assertEqual(rc.find_source(sel, [ANSWER]),
                         "| Mark | Color | State |\n|---|---|---|\n| ○ | green | **waiting**, and you have seen it |")

    def test_wrapped_list_item_keeps_its_bullet_and_bold(self):
        sel = ("  - Filled or hollow: a filled dot means something is happening there, or it needs your\n"
               "    attention. A hollow dot means all is calm.")
        self.assertEqual(rc.find_source(sel, [ANSWER]),
                         "- **Filled or hollow:** a filled dot means something is happening there, or it needs your "
                         "attention. A hollow dot means all is calm.")

    def test_selection_from_mid_sentence_keeps_only_the_selected_words(self):
        self.assertEqual(rc.find_source("click the pane and type", [ANSWER]), "click the pane and type")

    def test_selection_ending_inside_inline_code_closes_the_code(self):
        self.assertEqual(rc.find_source("pane and type claude --cont", [ANSWER]), "pane and type `claude --continue`")

    def test_selection_starting_inside_bold_opens_the_bold(self):
        self.assertEqual(rc.find_source("the agent is doing:", [ANSWER]), "**what the agent** is doing:")

    def test_link_target_hidden_on_screen_is_found(self):
        sel = "  Details: the herdr guide and the README."
        self.assertEqual(rc.find_source(sel, [ANSWER]),
                         "Details: [the herdr guide](https://herdr.dev/docs/agents/) and the README.")

    def test_code_lines_keep_their_code_block(self):
        sel = "  herdr workspace list\n  herdr agent list"
        self.assertEqual(rc.find_source(sel, [ANSWER]), "```bash\nherdr workspace list\nherdr agent list\n```")

    def test_whole_answer_with_bullet_marker(self):
        sel = "⏺ The color of the dots depends on what the agent is doing:\n\n" + TABLE_ON_SCREEN + "\n\n  - Filled"
        self.assertTrue(rc.find_source(sel, [ANSWER]).startswith("The color of the dots depends on **what the agent**"))

    def test_text_not_from_any_answer_gives_nothing(self):
        self.assertIsNone(rc.find_source("❯ which dashboard opens by default", [ANSWER]))

    def test_single_word_gives_nothing(self):
        self.assertIsNone(rc.find_source("dots", [ANSWER]))

    def test_newest_answer_wins(self):
        older, newer = "Old: the very same sentence here, first.", "New: the very **same sentence here**, second."
        self.assertEqual(rc.find_source("the very same sentence here", [newer, older]),
                         "the very **same sentence here**")

    def test_selection_cut_mid_word_at_both_ends(self):
        self.assertEqual(rc.find_source("olor of the dots depen", [ANSWER]), "color of the dots depends")


def jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class Replies(unittest.TestCase):
    def test_claude_replies_newest_first_without_sidechains(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.jsonl")
            jsonl(path, [
                {"type": "user", "message": {"content": "question"}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
                {"type": "assistant", "isSidechain": True,
                 "message": {"content": [{"type": "text", "text": "subagent"}]}},
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "second"}]}},
            ])
            self.assertEqual(rc.replies("claude", path), ["second", "first"])

    def test_codex_replies_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rollout.jsonl")
            jsonl(path, [
                {"payload": {"type": "message", "role": "user",
                             "content": [{"type": "input_text", "text": "question"}]}},
                {"payload": {"type": "message", "role": "assistant",
                             "content": [{"type": "output_text", "text": "one"}]}},
                {"payload": {"type": "message", "role": "assistant",
                             "content": [{"type": "output_text", "text": "two"}]}},
            ])
            self.assertEqual(rc.replies("codex", path), ["two", "one"])


class Upgrade(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "the formatted copy is made on a Mac only")
    def test_a_conversation_that_cannot_be_read_is_passed_over(self):
        with tempfile.TemporaryDirectory() as d:
            pipe, path = os.path.join(d, "pipe.jsonl"), os.path.join(d, "s.jsonl")
            os.mkfifo(pipe)
            jsonl(path, [{"type": "assistant", "message": {"content": [{"type": "text",
                                                                        "text": "The **dots** are green."}]}}])
            copied = []
            set_attrs(self, rc, open_sessions=lambda: [("claude", pipe), ("claude", path)],
                      copy_rich=lambda source, selection: copied.append(source) or True)
            self.assertTrue(finished(self, lambda: rc.upgrade("The dots are green.")))
            self.assertEqual(copied, ["The **dots** are green."])


class OpenSessions(unittest.TestCase):
    """The conversation files a selection is looked for in: the one herdr names for each agent, or, where herdr has
    none for it, the newest few started in the agent's folder."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HOME=self.home)

    def codex_file(self, name, meta, mtime):
        folder = os.path.join(self.home, ".codex", "sessions", "2026", "10", "21")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"rollout-{name}.jsonl")
        jsonl(path, [{"type": "session_meta", "payload": meta}])
        os.utime(path, (mtime, mtime))
        return path

    def running(self, **agent):
        set_attrs(self, rc, agents=lambda: [{"pane_id": "w1:p1", "cwd": "/repo/app", **agent}])

    def test_a_codex_herdr_names_no_conversation_of_is_looked_for_in_its_folder(self):
        older = self.codex_file("a", {"id": "a", "cwd": "/repo/app"}, 1000)
        newer = self.codex_file("b", {"id": "b", "cwd": "/repo/app"}, 2000)
        self.codex_file("c", {"id": "c", "cwd": "/repo/other"}, 3000)
        self.codex_file("d", {"id": "d", "cwd": "/repo/app", "source": {"subagent": {"other": "guardian"}}}, 4000)
        self.running(agent="codex")
        self.assertEqual(rc.open_sessions(), [("codex", newer), ("codex", older)])

    def test_only_the_newest_three_of_the_folder(self):
        paths = [self.codex_file(name, {"id": name, "cwd": "/repo/app"}, 1000 + n) for n, name in enumerate("abcd")]
        self.running(agent="codex")
        self.assertEqual(rc.open_sessions(), [("codex", path) for path in paths[:0:-1]])

    def test_a_claude_herdr_names_no_conversation_of_is_looked_for_in_its_folder(self):
        project = os.path.join(self.home, ".claude", "projects", "-repo-app")
        os.makedirs(project)
        path = os.path.join(project, "s1.jsonl")
        jsonl(path, [{"type": "user", "message": {"content": "question"}}])
        self.running(agent="claude")
        self.assertEqual(rc.open_sessions(), [("claude", path)])

    def test_the_conversation_herdr_names_comes_alone(self):
        named = self.codex_file("b", {"id": "b", "cwd": "/repo/app"}, 2000)
        self.codex_file("e", {"id": "e", "cwd": "/repo/app"}, 3000)
        self.running(agent="codex", agent_session={"value": "b"})
        self.assertEqual(rc.open_sessions(), [("codex", named)])


if __name__ == "__main__":
    unittest.main()
