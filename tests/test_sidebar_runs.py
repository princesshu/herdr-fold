"""Tests for the sidebar's Runs view (src/plugins/sidebar/runs_view.py, the pane the Agent view's More opens), as
runs.html's TUI frames: core's runs in cells, a run's properties and buttons, New run's form; core stood in for, a
temporary home and state, no agent run."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_jobs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import runs_view  # noqa: E402
from vt import Key  # noqa: E402

FOLDER = "/Users/dev/lumen-api"


def run(key, title, state="done", **more):
    agent, id = key.split(":")
    return {"key": key, "agent": agent, "name": agent.capitalize(), "id": id, "kind": "background", "title": title,
            "prompt": title, "folder": FOLDER, "place": "lumen-api", "group": "Today", "day": "Today", "time": "14:02",
            "took": "4 min", "state": state, "said": state, "made": "2 files", "files": [f"{FOLDER}/docs/api.md"],
            "media": [], "pr": None, "cost": "~$0.31", "cost_line": "~$0.31 API value",
            "ran_as": "Background session · Claude · Opus 5.5", "now": None, "session": "5f0c6d9e", **more}


LISTED = {"runs": [run("claude:7c5dcf5d", "Update the API docs from the routes", "running", group="Running",
                       now="Edit docs/api.md"),
                   run("claude:1a2b3c4d", "Bump dependencies, run the tests", made="PR #61"),
                   run("codex:0199", "Draft the release notes", "failed", kind="exec", made="failed")],
          "working": 1, "notes": [], "envs": [{"id": "env_lumen", "label": "lumen-api"}],
          "scheduled": "Scheduled cloud runs are not listed: Claude keeps its routines at claude.ai, Codex its "
                       "scheduled tasks in its app.", "left": 0}


class View(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HOME=os.path.join(self.tmp, "home"))
        self.addCleanup(end_jobs)
        self.started, self.acted = [], []
        for patch in (mock.patch.object(runs_view.runs, "runs", lambda agents, fresh=False: LISTED),
                      mock.patch.object(runs_view.agent_state, "machine_agents", lambda home: []),
                      mock.patch.object(runs_view.runs, "start", lambda *args: (
                          self.started.append(args), {"ok": True, "said": "Started in the background"})[1]),
                      mock.patch.object(runs_view.runs, "act", lambda *args: (
                          self.acted.append(args), {"ok": True, "said": "Stopped"})[1])):
            patch.start()
            self.addCleanup(patch.stop)

    def open(self, cells=60, rows=40):
        app = runs_view.RunsView(FakeTerminal(cells, rows), mock.Mock(), os.path.join(self.tmp, "plugin"),
                                 clock=lambda: 100.0, folder=FOLDER, home=os.path.join(self.tmp, "home"))
        self.settle(app)
        return app

    def settle(self, app):
        for _ in range(2):
            end_jobs()
            app.collect()
        app.draw()

    def rows(self, app):
        return [text(app.canvas, y).rstrip() for y in range(app.canvas.height)]

    def keys(self, app, *names):
        for name in names:
            app.key(Key("char", name) if len(name) == 1 else Key(name))
        self.settle(app)

    def test_the_runs_under_their_days_with_their_marks_and_columns(self):
        shown = "\n".join(self.rows(self.open()))
        for words in ("All agents", "Running", "Today", "Update the API docs", "PR #61", "✕ Draft the release",
                      "~$0.31", "Scheduled cloud runs are not listed", "n New run · o opens a file · Esc closes"):
            self.assertIn(words, shown)

    def test_a_working_run_opened_says_what_it_does_now_and_stop_is_its_agents_command(self):
        app = self.open()
        self.keys(app, "enter")
        shown = "\n".join(self.rows(app))
        for words in ("Ran as  Background session · Claude · Opus 5.5", "Now     Edit docs/api.md",
                      "So far  docs/api.md", "Attach   Stop"):
            self.assertIn(words, shown)
        self.keys(app, "right", "enter")
        self.assertEqual(self.acted, [("stop", "7c5dcf5d", None)])
        self.assertIn("Stopped", "\n".join(self.rows(app)))

    def test_a_narrow_pane_keeps_the_runs_name_and_lets_the_agent_go(self):
        shown = "\n".join(self.rows(self.open(cells=40)))
        self.assertIn("Update the …", shown)
        self.assertNotIn("Claude 14:02", shown)
        self.assertIn("n New run · o opens a file · Esc\n closes", shown)          # the keys wrap, never cut

    def test_new_run_starts_claudes_in_the_background_once_a_prompt_is_typed(self):
        app = self.open()
        self.keys(app, "n")
        self.assertIn("Runs on this Mac in the background", "\n".join(self.rows(app)))
        self.keys(app, "enter")
        self.assertEqual(self.started, [])                  # no prompt: Start is not lit
        for ch in "Fix the docs":
            app.key(Key("char", ch))
        self.keys(app, "enter")
        self.assertEqual(self.started, [("claude", "here", FOLDER, "Fix the docs", "env_lumen")])
        self.assertIn("Started in the background", "\n".join(self.rows(app)))

    def test_codex_schedules_only_in_its_own_app(self):
        app = self.open()
        self.keys(app, "n", "backtab", "right", "tab", "tab", "tab", "right")
        self.assertEqual((app.form["agent"], app.form["at"], app.form["when"]), ("codex", "when", "now"))
        shown = "\n".join(self.rows(app))
        self.assertIn("When     Now   On a schedule", shown)            # there, but never chosen
        self.assertIn("Runs on this Mac with codex exec", shown)
