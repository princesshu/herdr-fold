"""Tests for the sessions plugin's sync_names (fake herdr): a Sessions row shows only the pane name (herdr 0.9.5+) and a
resumed conversation resends no title, so names come from the conversation's files, skipping pipes and damaged lines.
"""
import glob
import json
import os
import shutil
import sys
import tempfile
import unittest

from support import SRC, finished, set_attrs, set_env

sys.path.insert(0, os.path.join(SRC, "plugins", "sessions-view"))
import sessions  # noqa: E402


class SyncNames(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        set_env(self, HERDR_PLUGIN_STATE_DIR=self.state, HOME=self.home)
        self.renames, self.labels, self.tabs, self.tab_renames = [], {}, [], []

        def call(method, params):
            if method == "pane.list":
                return {"result": {"panes": [{"pane_id": p, "label": l} for p, l in self.labels.items()]}}
            if method == "pane.rename":
                self.renames.append((params["pane_id"], params["label"]))
            if method == "tab.list":
                return {"result": {"tabs": self.tabs}}
            if method == "tab.rename":
                self.tab_renames.append((params["tab_id"], params["label"]))
            if method == "notification.show":
                self.notes.append(params)
            return {"result": {}}
        self.notes = []
        set_attrs(self, sessions, call=call)

    def write(self, rel, lines):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(line) + "\n" for line in lines))

    def agent(self, pane, title, kind="claude", session="s1"):
        return {"pane_id": pane, "tab_id": "w1:t2", "agent": kind, "terminal_title_stripped": title,
                "agent_session": {"value": session}}

    def tab(self, label, number=2):
        """The agents' tab, w1:t2, showing LABEL (herdr's number for it while unnamed); number 1 is the main tab."""
        self.tabs = [{"tab_id": "w1:t2", "label": label, "number": number}]

    def test_unnamed_new_claude_pane_gets_the_agent_name(self):
        self.labels = {"w1:p1": ""}
        sessions.sync_names([self.agent("w1:p1", "Claude Code")])
        self.assertEqual(self.renames, [("w1:p1", "claude")])

    def test_unnamed_codex_pane_gets_codex(self):
        self.labels = {"w1:p2": ""}
        sessions.sync_names([self.agent("w1:p2", "", kind="codex", session="s2")])
        self.assertEqual(self.renames, [("w1:p2", "codex")])

    def test_conversation_title_replaces_the_placeholder(self):
        self.labels = {"w1:p1": "claude"}
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.renames, [("w1:p1", "Colors of fruits")])

    def test_manual_name_is_kept(self):
        self.labels = {"w1:p1": "My own name"}
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.renames, [])

    def test_a_windows_shell_path_is_not_a_title(self):
        # a Windows console shows the shell's path as its title
        self.labels = {"w1:p1": ""}
        sessions.sync_names([self.agent("w1:p1", "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe")])
        self.assertEqual(self.renames, [("w1:p1", "claude")])

    def test_a_shell_path_named_earlier_goes_back_to_the_agent_name(self):
        path = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        with open(os.path.join(self.state, "names.json"), "w", encoding="utf-8") as f:
            json.dump({"s1": {"name": path, "given": True}}, f)
        self.labels = {"w1:p1": path}
        sessions.sync_names([self.agent("w1:p1", path)])
        self.assertEqual(self.renames, [("w1:p1", "claude")])

    def test_a_shell_path_title_is_no_conversation(self):
        self.assertFalse(sessions.has_session(self.agent("w1:p1", "/bin/zsh")))

    def save_names(self, names):
        with open(os.path.join(self.state, "names.json"), "w", encoding="utf-8") as f:
            json.dump(names, f)

    def test_a_damaged_names_file_is_set_aside_and_said(self):
        path = sessions.names_path()
        damaged = '{"s9": {"name": "My own name", "given": false}'           # cut short
        with open(path, "w") as f:
            f.write(damaged)
        self.labels = {"w1:p1": ""}
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        aside = glob.glob(path + ".damaged-*")
        self.assertEqual(len(aside), 1)
        with open(aside[0]) as f:
            self.assertEqual(f.read(), damaged)                               # the names in it are kept
        with open(path) as f:
            self.assertEqual(json.load(f), {"s1": {"name": "Colors of fruits", "given": True}})   # naming goes on
        self.assertEqual(len(self.notes), 1)
        self.assertIn(os.path.basename(aside[0]), self.notes[0].get("body", ""))

    def test_a_name_saved_meanwhile_by_another_run_survives(self):
        self.save_names({"s9": {"name": "Kept by the other run", "given": False}})
        self.labels = {"w1:p1": ""}

        def call(method, params):
            if method == "pane.list":                     # another plugin run saves a name while this one works
                with open(sessions.names_path()) as f:
                    names = json.load(f)
                names["s8"] = {"name": "Saved meanwhile", "given": False}
                with open(sessions.names_path(), "w") as f:
                    json.dump(names, f)
                return {"result": {"panes": [{"pane_id": p, "label": l} for p, l in self.labels.items()]}}
            if method == "pane.rename":
                self.renames.append((params["pane_id"], params["label"]))
            return {"result": {}}
        sessions.call = call
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        with open(sessions.names_path()) as f:
            names = json.load(f)
        self.assertEqual(names["s8"]["name"], "Saved meanwhile")
        self.assertEqual(names["s9"]["name"], "Kept by the other run")
        self.assertEqual(names["s1"]["name"], "Colors of fruits")
        self.assertEqual([n for n in os.listdir(self.state) if n.startswith(".names.")], [])

    def test_a_new_conversation_in_the_pane_replaces_the_old_title(self):
        # the pane still carries the title given to its previous conversation (s0); now s1 runs in it (/clear, /resume)
        self.save_names({"s0": {"name": "Colors of fruits", "given": True}})
        self.labels = {"w1:p1": "Colors of fruits"}
        sessions.sync_names([self.agent("w1:p1", "Fix the login", session="s1")])
        self.assertEqual(self.renames, [("w1:p1", "Fix the login")])

    def test_a_new_conversation_without_a_title_yet_gets_the_agent_name(self):
        self.save_names({"s0": {"name": "Colors of fruits", "given": True}})
        self.labels = {"w1:p1": "Colors of fruits"}
        sessions.sync_names([self.agent("w1:p1", "Claude Code", session="s1")])
        self.assertEqual(self.renames, [("w1:p1", "claude")])

    def test_a_manual_name_survives_a_new_conversation(self):
        self.save_names({"s0": {"name": "My own name", "given": False}})
        self.labels = {"w1:p1": "My own name"}
        sessions.sync_names([self.agent("w1:p1", "Fix the login", session="s1")])
        self.assertEqual(self.renames, [])

    def test_a_transcript_without_messages_is_no_conversation(self):
        self.write(".claude/projects/-x/s1.jsonl", [{"type": "permission-mode"}, {"type": "mode"}, {"type": "system"}])
        self.assertFalse(sessions.has_session(self.agent("w1:p1", "Claude Code")))
        self.write(".claude/projects/-x/s1.jsonl", [{"type": "mode"}, {"type": "user"}])
        self.assertTrue(sessions.has_session(self.agent("w1:p1", "Claude Code")))

    def test_title_of_a_resumed_claude_conversation_comes_from_its_transcript(self):
        self.write(".claude/projects/-x/s1.jsonl", [{"type": "ai-title", "aiTitle": "First idea"}, {"type": "user"},
                                                  {"type": "ai-title", "aiTitle": "Colors of fruits"}])
        self.labels = {"w1:p1": "claude"}
        sessions.sync_names([self.agent("w1:p1", "")])
        self.assertEqual(self.renames, [("w1:p1", "Colors of fruits")])

    def test_claude_rename_wins_over_the_generated_title(self):
        self.write(".claude/projects/-x/s1.jsonl", [{"type": "custom-title", "customTitle": "My task"},
                                                  {"type": "ai-title", "aiTitle": "Colors of fruits"}])
        self.labels = {"w1:p1": "claude"}
        sessions.sync_names([self.agent("w1:p1", "")])
        self.assertEqual(self.renames, [("w1:p1", "My task")])

    def test_a_pipe_or_a_damaged_line_is_no_title(self):
        # a pipe named like a transcript would hold the plugin for good; a line nested too deep or not an object ends it
        project = os.path.join(self.home, ".claude", "projects", "-x")
        os.makedirs(project)
        os.mkfifo(os.path.join(project, "s1.jsonl"))
        self.assertFalse(finished(self, lambda: sessions.has_messages(self.agent("w1:p1", ""))))
        self.assertEqual(finished(self, lambda: sessions.conversation_title(self.agent("w1:p1", ""))), "")
        os.remove(os.path.join(project, "s1.jsonl"))
        with open(os.path.join(project, "s1.jsonl"), "w") as f:
            f.write("[" * 100_000 + "]" * 100_000 + "\n[1]\n" + json.dumps({"type": "ai-title", "aiTitle": "Fruits"})
                    + "\n")
        self.assertEqual(sessions.conversation_title(self.agent("w1:p1", "")), "Fruits")

    def test_a_claude_title_is_read_in_one_pass(self):
        # a transcript is hundreds of megabytes: its rename and its generated title come from the same reading
        self.write(".claude/projects/-x/s1.jsonl", [{"type": "ai-title", "aiTitle": "Colors of fruits"}])
        opened = []
        real = sessions.open_regular
        set_attrs(self, sessions, open_regular=lambda *a, **k: opened.append(a[0]) or real(*a, **k))
        self.assertEqual(sessions.conversation_title(self.agent("w1:p1", "")), "Colors of fruits")
        self.assertEqual(len(opened), 1)

    def test_codex_thread_name_comes_from_its_index(self):
        self.write(".codex/session_index.jsonl", [{"id": "s2", "thread_name": "Old name"},
                                                  {"id": "s9", "thread_name": "x"},
                                                  {"id": "s2", "thread_name": "Fix the login"}])
        self.labels = {"w1:p2": "codex"}
        sessions.sync_names([self.agent("w1:p2", "", kind="codex", session="s2")])
        self.assertEqual(self.renames, [("w1:p2", "Fix the login")])

    # --- the conversation's tab

    def test_a_conversation_names_the_tab_it_has_to_itself(self):
        self.labels = {"w1:p1": "claude"}
        self.tab("2")
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.tab_renames, [("w1:t2", "Colors of fruits")])

    def test_the_main_tab_keeps_the_workspaces_name(self):
        self.labels = {"w1:p1": "claude"}
        self.tab("app", number=1)
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.tab_renames, [])

    def test_a_tab_two_agents_share_keeps_its_name(self):
        self.labels = {"w1:p1": "claude", "w1:p3": "claude"}
        self.tab("2")
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits"), self.agent("w1:p3", "Claude Code", session="s3")])
        self.assertEqual(self.tab_renames, [])

    def test_a_conversation_without_a_title_leaves_its_tab_as_it_is(self):
        self.labels = {"w1:p1": ""}
        self.tab("2")
        sessions.sync_names([self.agent("w1:p1", "Claude Code")])
        self.assertEqual(self.tab_renames, [])

    def test_the_tab_follows_the_title_while_it_shows_it(self):
        self.save_names({"s1": {"name": "Colors of fruits", "given": True}})
        self.labels = {"w1:p1": "Colors of fruits"}
        self.tab("Colors of fruits")
        sessions.sync_names([self.agent("w1:p1", "Fruit price list")])
        self.assertEqual(self.tab_renames, [("w1:t2", "Fruit price list")])

    def test_a_tab_named_by_hand_keeps_its_name_when_the_title_changes(self):
        self.save_names({"s1": {"name": "Colors of fruits", "given": True}})
        self.labels = {"w1:p1": "Colors of fruits"}
        self.tab("backend")
        sessions.sync_names([self.agent("w1:p1", "Fruit price list")])
        self.assertEqual(self.renames, [("w1:p1", "Fruit price list")])
        self.assertEqual(self.tab_renames, [])

    def test_a_name_given_in_herdr_goes_on_the_tab_whatever_it_shows(self):
        self.labels = {"w1:p1": "My own name"}                    # Rename pane, since the last run
        self.tab("backend")
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.tab_renames, [("w1:t2", "My own name")])
        self.tab_renames.clear()
        self.tab("api")                                           # the tab renamed by hand afterwards: it stays
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.tab_renames, [])

    def test_after_clear_pane_name_the_tab_takes_the_title_back(self):
        self.save_names({"s1": {"name": "My own name", "given": False}})
        self.labels = {"w1:p1": ""}
        self.tab("My own name")
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits")])
        self.assertEqual(self.tab_renames, [("w1:t2", "Colors of fruits")])

    def test_a_long_name_is_cut_on_the_tab(self):
        self.labels = {"w1:p1": "claude"}
        self.tab("2")
        sessions.sync_names([self.agent("w1:p1", "Colors of fruits and vegetables in spring")])
        self.assertEqual(self.tab_renames, [("w1:t2", "Colors of fruits and ve…")])
        self.assertEqual(len(self.tab_renames[0][1]), sessions.TAB_NAME)


class Waits(unittest.TestCase):
    """How long an agent waits on you (blocked, or done and not seen yet), as its workspace's $waiting token: the
    theme's Space rows show it beside the branch."""

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        set_env(self, HERDR_PLUGIN_STATE_DIR=self.state)
        self.tokens, self.reports, self.agents = {"w1": {}, "w2": {}}, [], []

        def call(method, params):
            if method == "agent.list":
                return {"result": {"agents": self.agents}}
            if method == "workspace.list":
                return {"result": {"workspaces": [{"workspace_id": ws, "tokens": dict(tokens)}
                                                  for ws, tokens in self.tokens.items()]}}
            if method == "workspace.report_metadata":
                self.reports.append((params["workspace_id"], params["tokens"]["waiting"]))
                self.assertEqual(params["source"], sessions.SOURCE)
                for name, value in params["tokens"].items():
                    if value is None:
                        self.tokens[params["workspace_id"]].pop(name, None)
                    else:
                        self.tokens[params["workspace_id"]][name] = value
            return {"result": {}}
        set_attrs(self, sessions, call=call)

    def agent(self, pane, status, seq=1):
        return {"pane_id": pane, "workspace_id": pane.split(":")[0], "agent_status": status, "state_change_seq": seq}

    def test_a_wait_reads_in_minutes_then_hours_then_days(self):
        self.assertEqual(sessions.waited(59), "waiting <1m")
        self.assertEqual(sessions.waited(12 * 60 + 59), "waiting 12m")
        self.assertEqual(sessions.waited(2 * 3600 + 59 * 60), "waiting 2h")
        self.assertEqual(sessions.waited(3 * 86400 + 5), "waiting 3d")

    def test_a_blocked_agent_waits_from_its_state_change_on(self):
        self.agents = [self.agent("w1:p1", "blocked", seq=4)]
        self.assertTrue(sessions.report_waits(self.agents, 1000.0))
        self.assertTrue(sessions.report_waits(self.agents, 1000.0 + 12 * 60))
        self.assertEqual(self.reports, [("w1", "waiting <1m"), ("w1", "waiting 12m")])

    def test_a_done_agent_not_seen_yet_waits_too(self):
        sessions.report_waits([self.agent("w1:p1", "done")], 1000.0)
        self.assertEqual(self.reports, [("w1", "waiting <1m")])

    def test_working_and_idle_agents_do_not_wait(self):
        self.assertFalse(sessions.report_waits([self.agent("w1:p1", "working"), self.agent("w1:p2", "idle")], 1000.0))
        self.assertEqual(self.reports, [])

    def test_a_new_state_change_starts_the_wait_again(self):
        # answered and finished between two runs: the done agent waits from now, not from the question
        sessions.report_waits([self.agent("w1:p1", "blocked", seq=4)], 1000.0)
        sessions.report_waits([self.agent("w1:p1", "done", seq=6)], 1000.0 + 30 * 60)
        self.assertEqual(self.reports, [("w1", "waiting <1m")])

    def test_a_workspace_shows_its_longest_wait(self):
        sessions.report_waits([self.agent("w1:p1", "blocked")], 1000.0)
        sessions.report_waits([self.agent("w1:p1", "blocked"), self.agent("w1:p2", "done"),
                               self.agent("w2:p3", "done")], 1000.0 + 5 * 60)
        self.assertEqual(self.reports, [("w1", "waiting <1m"), ("w1", "waiting 5m"), ("w2", "waiting <1m")])

    def test_the_label_goes_once_no_agent_waits_there(self):
        sessions.report_waits([self.agent("w1:p1", "blocked")], 1000.0)
        self.assertFalse(sessions.report_waits([self.agent("w1:p1", "working", seq=2)], 1060.0))
        self.assertEqual(self.reports, [("w1", "waiting <1m"), ("w1", None)])
        self.assertEqual(self.tokens, {"w1": {}, "w2": {}})

    def test_a_label_already_shown_is_not_reported_again(self):
        self.tokens["w1"] = {"waiting": "waiting <1m"}
        sessions.report_waits([self.agent("w1:p1", "blocked")], 1000.0)
        self.assertEqual(self.reports, [])

    def test_a_label_left_from_before_a_restart_goes(self):
        # herdr drops tokens on a restart; a wait recorded then, whose pane no longer waits, is forgotten
        with open(os.path.join(self.state, "waits.json"), "w") as f:
            json.dump({"w1:p9": {"seq": 2, "since": 10.0}}, f)
        self.tokens["w2"] = {"waiting": "waiting 3h"}
        self.assertFalse(sessions.report_waits([], 1000.0))
        self.assertEqual(self.reports, [("w2", None)])
        with open(os.path.join(self.state, "waits.json")) as f:
            self.assertEqual(json.load(f), {})

    def test_an_agent_marked_unread_waits_until_looked_at_again(self):
        # Cmd+Shift+U while on it: it waits from now; leaving it, then coming back to it, reads it
        agents = [self.agent("w1:p1", "idle")]
        sessions.mark_unread("w1:p1", agents, 1000.0)
        sessions.report_waits(agents, 1300.0, focused="w1:p1")                  # still on it
        sessions.report_waits(agents, 1360.0, focused="w2:p1")                  # left it
        self.assertTrue(sessions.report_waits(agents, 1500.0))                   # the clock's look
        self.assertFalse(sessions.report_waits(agents, 1600.0, focused="w1:p1"))
        self.assertEqual(self.reports, [("w1", "waiting <1m"), ("w1", "waiting 5m"), ("w1", "waiting 6m"),
                                        ("w1", "waiting 8m"), ("w1", None)])

    def test_marking_it_again_takes_the_mark_off(self):
        agents = [self.agent("w1:p1", "idle")]
        sessions.mark_unread("w1:p1", agents, 1000.0)
        sessions.mark_unread("w1:p1", agents, 1060.0)
        self.assertEqual(self.reports, [("w1", "waiting <1m"), ("w1", None)])

    def test_a_marked_agent_stays_marked_while_it_works_and_goes_with_its_pane(self):
        sessions.mark_unread("w1:p1", [self.agent("w1:p1", "idle")], 1000.0)
        self.assertTrue(sessions.report_waits([self.agent("w1:p1", "working", seq=2)], 1100.0, focused="w2:p1"))
        self.assertFalse(sessions.report_waits([], 1200.0))
        self.assertEqual(self.reports[-1], ("w1", None))

    def test_only_an_agent_can_be_marked_unread(self):
        sessions.mark_unread("w1:p9", [self.agent("w1:p1", "idle")], 1000.0)
        self.assertEqual(self.reports, [])
        self.assertEqual(sessions.load_waits(), {})

    def test_the_clock_runs_while_an_agent_waits_and_ends_when_none_does(self):
        now, slept = [1000.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds
            if len(slept) == 3:                      # answered after the third tick
                self.agents = [self.agent("w1:p1", "working", seq=2)]
        self.agents = [self.agent("w1:p1", "blocked")]
        sessions.report_waits(self.agents, now[0])
        finished(self, lambda: sessions.keep_time(clock=lambda: now[0], sleep=sleep))
        self.assertEqual(len(slept), 3)
        self.assertEqual(self.reports[0], ("w1", "waiting <1m"))
        self.assertEqual(self.reports[-1], ("w1", None))

    def test_one_run_keeps_the_clock_at_a_time(self):
        self.agents = [self.agent("w1:p1", "blocked")]
        sessions.report_waits(self.agents, 1000.0)
        with sessions.locked(os.path.join(self.state, "clock.lock")) as mine:
            self.assertTrue(mine)
            finished(self, lambda: sessions.keep_time(clock=lambda: 2000.0, sleep=self.fail))

    def test_the_clock_ends_when_herdr_stops_answering(self):
        self.agents = [self.agent("w1:p1", "blocked")]
        sessions.report_waits(self.agents, 1000.0)

        def gone(method, params):
            raise ConnectionRefusedError
        sessions.call = gone
        finished(self, lambda: sessions.keep_time(clock=lambda: 2000.0, sleep=lambda seconds: None))

    def test_the_clock_ends_when_the_plugin_is_updated_or_removed(self):
        self.agents = [self.agent("w1:p1", "blocked")]
        sessions.report_waits(self.agents, 1000.0)
        stamps = iter(["old", "new"])
        set_attrs(self, sessions, code_stamp=lambda: next(stamps))
        finished(self, lambda: sessions.keep_time(clock=lambda: 2000.0, sleep=lambda seconds: None))
        self.assertEqual(self.reports, [("w1", "waiting <1m")])


class WindowsPipe(unittest.TestCase):
    def test_the_pipe_is_named_after_the_socket_path(self):
        # as herdr's own plugin examples do: \\.\pipe\ + HERDR_SOCKET_PATH
        self.assertEqual(sessions.pipe_name("C:\\Users\\a\\.config\\herdr\\herdr.sock"),
                         "\\\\.\\pipe\\C:\\Users\\a\\.config\\herdr\\herdr.sock")


class Manifest(unittest.TestCase):
    def blocks(self):
        with open(os.path.join(os.path.dirname(sessions.__file__), "herdr-plugin.toml"), encoding="utf-8") as f:
            return f.read().split("[[")

    def test_windows_can_reapply_the_view(self):
        self.assertTrue([b for b in self.blocks() if b.startswith("actions]") and 'id = "apply-windows"' in b
                         and 'platforms = ["windows"]' in b])

    def test_mark_unread_is_an_action_everywhere(self):
        actions = [b for b in self.blocks() if b.startswith("actions]") and "sessions.py\", \"--unread\"]" in b]
        self.assertEqual(sorted(b.split('id = "')[1].split('"')[0] for b in actions),
                         ["mark-unread", "mark-unread-windows"])


if __name__ == "__main__":
    unittest.main()
