"""Tests for panes.py: the right column (the sidebar above a terminal) built in a new tab as wide as in the others,
the panes a tab lacks brought back, Restore panels, the tip on a pane closed by hand, the commands typed into a
pane, a new tab laid out, the dock back when herdr starts. herdr is a recorder."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SRC, FakeHerdrSocket, set_attrs, set_env, stubs

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import conversations  # noqa: E402
import panels  # noqa: E402
import panes  # noqa: E402


class Herdr:
    """Two tabs, each an agent and the right column (sidebar above terminal). Panes: t1 agent p1, sidebar p2,
    terminal p3; t2 p4, p5, p7. New panes are new1, new2…, listed once named."""

    def __init__(self, current="w1:t2", terminal=True):
        self.calls, self.split, self.current = [], 0, current
        self.new_in = {}                                                    # a new pane → its tab
        self.panes = []
        for tab, agent, side, term in (("w1:t1", "p1", "p2", "p3"), ("w1:t2", "p4", "p5", "p7")):
            folder = f"/repo/{tab[-1]}"
            self.panes += [{"pane_id": f"w1:{agent}", "tab_id": tab, "label": "claude", "cwd": folder},
                           {"pane_id": f"w1:{side}", "tab_id": tab, "label": "sidebar", "cwd": folder}]
            if terminal:
                self.panes.append({"pane_id": f"w1:{term}", "tab_id": tab, "label": "terminal", "cwd": folder})

    def only(self, tab, *labels):
        """TAB left with the panes of LABELS only."""
        self.panes = [p for p in self.panes if p["tab_id"] != tab or p["label"] in labels]

    def tab_of(self, pane):
        return next((p["tab_id"] for p in self.panes if p["pane_id"] == pane), None) or self.new_in.get(pane)

    def __call__(self, *args):
        self.calls.append(" ".join(args))
        if args[:2] == ("pane", "list"):
            return {"panes": self.panes}
        if args[:2] == ("pane", "current"):
            return {"pane": {"tab_id": self.current}}
        if args[:2] == ("pane", "get"):
            return {"pane": {"pane_id": args[2], "tab_id": self.tab_of(args[2])}}
        if args[:2] == ("pane", "rename") and args[2] in self.new_in:
            self.panes.append({"pane_id": args[2], "tab_id": self.new_in[args[2]], "label": args[3]})
        if args[:2] == ("pane", "split"):
            self.split += 1
            self.new_in[f"new{self.split}"] = self.tab_of(args[3])
            return {"pane": {"pane_id": f"new{self.split}", "tab_id": self.new_in[f"new{self.split}"]}}
        return {}

    def changes(self):
        return [call for call in self.calls if not call.startswith(("pane list", "pane current", "pane get"))]


class Panes(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def write(self, data, name=conversations.SETTINGS):
        with open(os.path.join(self.state, name), "w") as f:
            json.dump(data, f)

    def test_the_panes_reopening_a_conversation_are_kept_with_the_rest(self):
        self.write({"show_archived": True, "resumed": ["of another shape"]})
        self.assertEqual(panes.resumed(self.state), {})
        panes.resume(self.state, "w1:p9", "s2")
        panes.resume(self.state, "w2:p3", "c1")
        self.assertEqual(panes.resumed(self.state), {"w1:p9": "s2", "w2:p3": "c1"})
        self.assertTrue(conversations.setting(self.state)["show_archived"])

    def test_a_tab_built_here_gets_the_right_column_as_wide_as_the_others(self):
        herdr = Herdr()
        self.assertEqual(panes.build(herdr, "w1:p1", "/repo/app", self.state), "new1")
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo/app --no-focus",
            "pane split --pane new1 --direction down --ratio 0.5 --cwd /repo/app --no-focus",
            "pane rename new2 terminal", "pane rename new1 sidebar", f"pane run new1 {panes.sidebar_command()}"])
        self.write({"ratio": 0.8}, "column.json")                     # dragged: the right column 20%
        herdr = Herdr()
        panes.build(herdr, "w1:p1", None, self.state, sidebar_run="launcher")
        self.assertEqual(herdr.changes()[0], "pane split --pane w1:p1 --direction right --ratio 0.8 --no-focus")
        self.assertEqual(herdr.changes()[-1], "pane run new1 launcher")

    def test_a_tab_built_here_is_noted_as_having_every_pane(self):
        panes.build(Herdr(), "w1:p1", "/repo/app", self.state)
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))
        panes.build(Herdr(), "w1:p1", "/repo/app", self.state, scope="mini")       # a machine's tabs apart
        self.assertEqual(panels.had(self.state, "w1:t1", "mini"), set(panels.KINDS))

    def test_a_terminal_back_under_the_sidebar(self):
        herdr = Herdr(terminal=False)                                        # t1: an agent and the sidebar only
        self.assertEqual(panes.bring(herdr, "w1:t1", {"terminal"}, self.state), {"terminal"})
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p2 --direction down --ratio 0.5 --cwd /repo/1 --no-focus",
            "pane rename new1 terminal"])
        self.assertEqual(panels.had(self.state, "w1:t1"), {"terminal"})

    def test_the_sidebar_back_above_its_terminal(self):
        herdr = Herdr()
        herdr.only("w1:t1", "claude", "terminal")
        self.assertEqual(panes.bring(herdr, "w1:t1", {"sidebar"}, self.state), {"sidebar"})
        self.assertEqual(herdr.changes(), [
            "pane split --pane w1:p3 --direction down --ratio 0.5 --cwd /repo/1 --no-focus",
            "pane swap --source-pane new1 --target-pane w1:p3",              # the terminal keeps what runs in it
            "pane rename new1 sidebar", f"pane run new1 {panes.sidebar_command()}"])

    def test_a_tab_with_neither_gets_the_whole_column(self):
        herdr = Herdr()
        herdr.only("w1:t1", "claude")
        self.assertEqual(panes.bring(herdr, "w1:t1", set(panels.KINDS), self.state), set(panels.KINDS))
        self.assertEqual(herdr.changes()[0],
                         "pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo/1 --no-focus")

    def test_one_already_there_is_not_brought_again(self):
        herdr = Herdr()
        self.assertEqual(panes.bring(herdr, "w1:t1", set(panels.KINDS), self.state), set())
        self.assertEqual(herdr.changes(), [])

    def test_restore_panels_brings_back_every_pane_closed_in_the_tab_and_shows_the_column(self):
        herdr = Herdr(current="w1:t1", terminal=False)                       # t1: the terminal closed
        snapshot = {"snapshot": {"layouts": [{"tab_id": "w1:t1", "zoomed": True, "focused_pane_id": "w1:p1"}]}}
        call = lambda *args: snapshot if args[:2] == ("api", "snapshot") else herdr(*args)   # noqa: E731
        self.assertEqual(panes.restore(call, self.state), {"terminal"})
        self.assertEqual(herdr.calls[1], "pane zoom w1:p1 --toggle")          # the column hidden: shown first
        self.assertIn("pane rename new1 terminal", herdr.calls)

    def closed_tip(self):
        """The tip herdr shows when t1's terminal is closed by hand."""
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}})
        herdr = Herdr()
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        herdr.only("w1:t1", "claude", "sidebar")
        panes.tell(herdr, self.state, "w1", lambda _: None)
        return [call for call in herdr.calls if call.startswith("notification show")]

    def test_the_tip_names_the_key_only_where_herdr_has_it(self):
        # herdr-fold binds Restore panels to Cmd+Shift+O in herdr's config; the sidebar installed alone has the menus
        home = os.path.join(self.state, "home")
        set_env(self, HOME=home)
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Restore panels in the ⋯ or right-click menu brings them back"])
        os.makedirs(os.path.join(home, ".config", "herdr"))
        with open(os.path.join(home, ".config", "herdr", "config.toml"), "w") as f:
            f.write('type = "plugin_action"\ncommand = "herdr-fold.sidebar.restore-panels"\n')
        os.remove(os.path.join(self.state, conversations.SETTINGS))            # told once: shown again here
        self.assertEqual(self.closed_tip(), ["notification show Closed panels stay closed in their tab --body "
                                             "Cmd+Shift+O brings them back"])

    def test_the_first_pane_closed_by_hand_brings_a_tip_once(self):
        set_env(self, HOME=os.path.join(self.state, "home"))
        panels.note(self.state, {"w1:t1": {"sidebar", "terminal"}, "w1:t2": {"sidebar", "terminal"}})
        herdr, waited = Herdr(), []
        for listed in herdr.panes:
            listed["workspace_id"] = "w1"
        self.assertFalse(panes.tell(herdr, self.state, "w1", waited.append))        # every pane still there
        herdr.only("w1:t1", "claude", "sidebar")                                     # t1's terminal closed
        self.assertTrue(panes.tell(herdr, self.state, "w1", waited.append))
        self.assertEqual(waited, [panes.SETTLE, panes.SETTLE])      # looked at once the plugin's own moves are done
        tip = [call for call in herdr.calls if call.startswith("notification show")]
        self.assertEqual(len(tip), 1)
        self.assertFalse(panes.tell(herdr, self.state, "w1", waited.append))         # never again
        self.assertEqual(len(waited), 2)

    def command_line(self, flag, answers, **env):
        """panes.py FLAG run as herdr runs it, with ENV; herdr a stub giving ANSWERS ({"pane list": its result, …}, by
        its first two words). herdr's calls."""
        bin_dir, log = os.path.join(self.state, "bin"), os.path.join(self.state, "herdr.log")
        cases = "".join(f"  '{asked}') echo '{json.dumps({'result': result})}' ;;\n"
                        for asked, result in answers.items())
        stubs(bin_dir, {"herdr": "#!/bin/sh\n"
                                 f"printf '%s\\n' \"$*\" >> '{log}'\n"
                                 'case "$1 $2" in\n' + cases +
                                 "  *) echo '{\"result\": {}}' ;;\n"
                                 "esac\n"})
        done = subprocess.run([sys.executable, panes.__file__, flag], timeout=30, capture_output=True,
                              env={"PATH": "/usr/bin:/bin", "HERDR_BIN_PATH": os.path.join(bin_dir, "herdr"),
                                   "HERDR_PLUGIN_STATE_DIR": self.state, "HOME": self.state, **env})
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(log) as f:
            return f.read().splitlines()

    def test_restore_from_the_command_line_builds_the_column(self):
        # herdr's Restore panels action: the tab the key is pressed in, its right column back
        calls = self.command_line("--restore", {
            "pane list": {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude", "cwd": "/repo"}]},
            "pane current": {"pane": {"pane_id": "w1:p1", "tab_id": "w1:t1"}},
            "pane split": {"pane": {"pane_id": "w1:p9", "tab_id": "w1:t1"}}})
        self.assertIn("pane split --pane w1:p1 --direction right --ratio 0.75 --cwd /repo --no-focus", calls)
        self.assertIn("pane rename w1:p9 sidebar", calls)
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))
        wrong = subprocess.run([sys.executable, panes.__file__, "--bring"], capture_output=True, text=True)
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("Usage:", wrong.stderr)

    def test_a_new_tab_from_the_command_line_gets_the_column(self):
        # herdr's tab.created runs panes.py --new-tab, the event in HERDR_PLUGIN_EVENT_JSON
        calls = self.command_line("--new-tab", {
            "workspace list": {"workspaces": [{"workspace_id": "w1", "label": "repo", "tab_count": 2,
                                               "pane_count": 4}]},
            "pane list": {"panes": [{"pane_id": "w1:p5", "tab_id": "w1:t2", "label": None, "cwd": "/repo"}]},
            "pane process-info": {"process_info": {"foreground_processes": [{"name": "-zsh"}]}},
            "pane split": {"pane": {"pane_id": "w1:p9", "tab_id": "w1:t2"}}},
            HERDR_PLUGIN_EVENT_JSON=json.dumps({"event": "tab.created", "data": {"tab": {"tab_id": "w1:t2"}}}))
        self.assertIn("pane split --pane w1:p5 --direction right --ratio 0.75 --cwd /repo --no-focus", calls)

    def test_herdrs_start_from_the_command_line_brings_the_dock_back(self):
        # herdr's [[startup]] runs panes.py --startup: a column whose sidebar was never there gets one
        calls = self.command_line("--startup", {
            "workspace list": {"workspaces": [{"workspace_id": "w1", "label": "repo"}]},
            "pane list": {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1", "label": "claude", "cwd": "/repo"},
                                    {"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "terminal", "cwd": "/repo"}]},
            "pane split": {"pane": {"pane_id": "w1:p9", "tab_id": "w1:t1"}}})
        self.assertIn("pane split --pane w1:p2 --direction down --ratio 0.5 --cwd /repo --no-focus", calls)
        self.assertIn("pane rename w1:p9 sidebar", calls)

    def test_its_command_runs_the_sidebar_with_this_python(self):
        self.assertTrue(panes.sidebar_command(windows=False).endswith("/sidebar.py"))
        self.assertTrue(panes.sidebar_command(windows=True).startswith("& '"))
        self.assertTrue(panes.sidebar_command(windows=True).endswith("sidebar.py'"))

    def test_its_command_names_no_account(self):
        # typed into a pane's shell, the line stays in its history: a path from the home folder goes as ~ ($HOME)
        self.assertNotIn(os.path.expanduser("~") + os.sep, panes.sidebar_command(windows=False))
        mac, windows = "/Us" + "ers/dev", "C:\\Us" + "ers\\dev"
        self.assertEqual(panes.typed(mac + "/.config/x y/sidebar.py", windows=False, home=mac),
                         "~/'.config/x y/sidebar.py'")
        self.assertEqual(panes.typed("/usr/bin/python3", windows=False, home=mac), "/usr/bin/python3")
        self.assertEqual(panes.typed(windows + "\\a$b`c\\s.py", windows=True, home=windows), '"$HOME\\a`$b``c\\s.py"')
        self.assertEqual(panes.typed("D:\\py\\python.exe", windows=True, home=windows), "'D:\\py\\python.exe'")
        here = os.path.expanduser("~/.a b/c")
        out = subprocess.run(["/bin/sh", "-c", "printf %s " + panes.typed(here, windows=False)], capture_output=True,
                             text=True).stdout
        self.assertEqual(out, here)                                                 # the shell finds it again

    def test_a_folders_name_is_never_typed_into_a_pane(self):
        # herdr types a pane's command into its shell: control characters in a folder's name (a downloaded
        # repository's) would edit that line and run what follows, quotes or not; the folder goes as --cwd only
        herdr = Herdr()
        folder = "/repo/a\x15touch owned\r"
        herdr.only("w1:t1", "claude", "terminal")
        for p in herdr.panes:
            p["cwd"] = folder
        panes.bring(herdr, "w1:t1", {"sidebar"}, self.state)
        typed = [call for call in herdr.calls if call.startswith("pane run")]
        self.assertTrue(typed)
        self.assertEqual([call for call in typed if "repo" in call or "owned" in call], [])
        self.assertIn(f"--cwd {folder}", " ".join(c for c in herdr.calls if c.startswith("pane split")))


class Shells(unittest.TestCase):
    def test_a_shell_alone_is_only_a_shell(self):
        for names in (["-zsh"], ["C:\\Program Files\\PowerShell\\7\\pwsh.exe"], ["powershell.exe"], ["bash", "sh"]):
            self.assertTrue(panes.only_shells([{"name": n} for n in names]), names)

    def test_a_program_in_the_foreground_is_not(self):
        self.assertFalse(panes.only_shells([{"name": "pwsh.exe"}, {"name": "node.exe"}]))
        self.assertFalse(panes.only_shells([]))

    def test_program_names_are_plain(self):
        self.assertEqual(panes.program_names([{"name": "C:\\Tools\\Node.EXE"}, {"name": "-zsh"}]), ["node", "zsh"])

    def test_a_folder_tells_a_windows_machine(self):
        set_attrs(self, os, name="posix")
        self.assertTrue(panes.on_windows("C:\\Users\\dev\\app"))
        self.assertTrue(panes.on_windows("D:/projects"))
        self.assertFalse(panes.on_windows("/home/dev/app"))
        self.assertFalse(panes.on_windows(None))


class NewTab(unittest.TestCase):
    """herdr's tab.created: a new tab gets the right column on every platform, but for the new button's workspace
    while Workspaces' folder picker is open (herdr-fold.workspaces' tests cover the picker)."""

    def setUp(self):
        self.columns, self.waited, self.label = [], [], "app"
        self.cwd, self.shell, self.named = "/work/app", "zsh", None
        set_attrs(self, panes, build=lambda call, pane, cwd, state_dir: self.columns.append((pane, cwd, state_dir)))
        set_attrs(self, os, name="posix")

    def herdr(self, *args):
        if args[:2] == ("workspace", "list"):
            return {"workspaces": [{"workspace_id": "w2", "label": self.label, "tab_count": 1, "pane_count": 1}]}
        if args[:2] == ("pane", "list"):
            return {"panes": [{"pane_id": "w2:p1", "tab_id": "w2:t1", "label": self.named, "cwd": self.cwd}]}
        if args[:2] == ("pane", "process-info"):
            return {"process_info": {"foreground_processes": [{"name": self.shell}]}}
        return {}

    def new_tab(self):
        panes.new_tab(self.herdr, {"data": {"tab": {"tab_id": "w2:t1"}}}, "/state", self.waited.append)

    def test_a_new_tab_gets_the_column(self):
        self.new_tab()
        self.assertEqual(self.columns, [("w2:p1", "/work/app", "/state")])
        self.assertEqual(self.waited, [panes.NEW_TAB])                  # looked at once a builder has had its turn

    def test_a_new_tab_on_windows_gets_the_column_too(self):
        os.name, self.cwd, self.shell = "nt", "C:\\Users\\dev\\app", "pwsh.exe"
        self.new_tab()
        self.assertEqual(self.columns, [("w2:p1", "C:\\Users\\dev\\app", "/state")])

    def test_a_tab_a_builder_named_or_runs_in_is_left_alone(self):
        # the sidebar's preview or an issue's tab: its pane named first, or a program already in it
        self.named = "preview"
        self.new_tab()
        self.named, self.shell = None, "less"
        self.new_tab()
        self.assertEqual(self.columns, [])

    def test_the_new_buttons_workspace_is_left_to_the_folder_picker(self):
        # Workspaces names it new and builds the chosen folder's workspace, then closes this one
        self.label = "new"
        self.new_tab()
        self.assertEqual(self.columns, [])


class Steady(unittest.TestCase):
    """At herdr's start a pane is decided about only once it stays the same: herdr is still resuming conversations."""

    def setUp(self):
        set_attrs(self, panes, POLL=0)

    def watch(self, states, starting, pane=None):
        """when_steady over one pane whose foreground programs are STATES, one per look (the last one stays); what
        was done to it."""
        pane, states, acted = pane or {"pane_id": "w1:p1"}, list(states), []

        def herdr(*args):
            names = states.pop(0) if len(states) > 1 else states[0]
            return {"process_info": {"foreground_processes": [{"name": n} for n in names.split(",") if n]}}
        panes.when_steady(herdr, starting, lambda: [(pane, "sidebar")], lambda *done: acted.append(done))
        return acted

    def test_a_shell_is_acted_on_at_once_without_herdr_starting(self):
        self.assertEqual(self.watch(["zsh"], False), [({"pane_id": "w1:p1"}, "sidebar")])
        self.assertEqual(self.watch(["Python"], False), [])                    # running already: left as it is

    def test_at_herdrs_start_a_pane_is_acted_on_once_steady(self):
        self.assertEqual(len(self.watch(["", "claude", "zsh", "zsh", "zsh"], True)), 1)
        self.assertEqual(self.watch(["zsh", "Python"], True), [])              # the sidebar came back by itself

    def test_a_pane_herdr_may_still_resume_a_conversation_in_is_waited_for(self):
        set_attrs(self, panes, STARTUP_LIMIT=0)
        self.assertEqual(self.watch(["zsh"], True, {"pane_id": "w1:p1", "agent_session": "s1"}), [])


class RestoreAll(unittest.TestCase):
    """restore_all (fake herdr): only the dock's panes, beside agents named by `herdr agent start` (a pane's own name
    does not count): missing columns and their programs rebuilt, a pane closed by hand left closed."""

    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        set_attrs(self, panes, POLL=0)

    def restore(self, found, agents=None, cwd=None, starting=False, space="app"):
        """FOUND: (tab, label, foreground programs, comma-separated) per pane of workspace w1, all in folder CWD;
        AGENTS: {pane: name or None}, the agents herdr reports (a name: one started so); SPACE: the workspace's
        name. herdr's calls; what it said is in self.said."""
        calls, agents = [], agents or {}
        listed = [{"pane_id": f"w1:p{n}", "tab_id": tab, "label": label, **({"cwd": cwd} if cwd else {})}
                  for n, (tab, label, _) in enumerate(found, 1)]
        programs = {f"w1:p{n}": program for n, (_, _, program) in enumerate(found, 1)}

        def herdr(*args):
            calls.append(args)
            if args[:2] == ("workspace", "list"):
                return {"workspaces": [{"workspace_id": "w1", "label": space}]}
            if args[:2] == ("pane", "list"):
                return {"panes": listed}
            if args[:2] == ("agent", "list"):
                return {"agents": [{"pane_id": p, "agent": "claude", **({"name": n} if n else {})}
                                   for p, n in agents.items()]}
            if args[:2] == ("pane", "process-info"):
                return {"process_info": {"foreground_processes": [{"name": n} for n in programs[args[3]].split(",")]}}
            if args[:2] == ("pane", "split"):
                return {"pane": {"pane_id": f"new{len(calls)}"}}
            if args[:2] == ("pane", "close"):
                listed[:] = [p for p in listed if p["pane_id"] != args[2]]
            return {}
        self.said = []
        panes.restore_all(herdr, self.state, starting=starting, say=lambda *told: self.said.append(told))
        return calls

    def splits_of(self, calls):
        """Where the right columns were built: beside a pane of the tab."""
        return [c[3] for c in calls if c[:2] == ("pane", "split") and "right" in c and not c[3].startswith("new")]

    def changes(self, calls):
        return [c for c in calls if c[:2] not in (("workspace", "list"), ("pane", "list"), ("agent", "list"),
                                                  ("pane", "process-info"), ("pane", "get"))]

    def sidebars_made(self, calls):
        """The new sidebar panes: split off, then named "sidebar"."""
        return [c[2] for c in calls if c[:2] == ("pane", "rename") and c[3] == "sidebar" and c[2].startswith("new")]

    def test_a_started_agent_alone_in_its_tab_gets_the_column(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), ["w1:p1"])
        self.assertEqual(self.said, [("ok", "column_next_to", "app", "claude")])

    def test_a_started_agent_by_herdrs_record_not_by_the_pane_name(self):
        calls = self.restore([("w1:t1", "Colors of fruits", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), ["w1:p1"])

    def test_a_users_own_agent_alone_gets_no_column(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t2", "", "zsh")], agents={"w1:p1": None})
        self.assertEqual(self.changes(calls), [])

    def test_an_agents_pane_is_left_to_its_agent(self):
        # herdr-fold's Workspaces starts it again (restore_panes.py); the dock never types into it
        calls = self.restore([("w1:t1", "claude", "zsh"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app-claude"})
        self.assertEqual(self.changes(calls), [])

    def test_an_older_installs_conversations_column_goes_its_room_back_to_the_agent(self):
        # before it was a panel of the sidebar, the Conversations column stood between the agent and the right
        # column: closed, its room goes to the right column, set back to the width remembered on this machine
        tmp = tempfile.mkdtemp(dir="/tmp")                  # a short path: a socket's name has room for 104 bytes
        self.addCleanup(shutil.rmtree, tmp)
        set_env(self, HERDR_SOCKET_PATH=os.path.join(tmp, "h.sock"))
        column = {"type": "split", "direction": "down", "ratio": 0.5, "first": {"type": "pane", "pane_id": "w1:p3",
                  "label": "sidebar"}, "second": {"type": "pane", "pane_id": "w1:p4", "label": "terminal"}}
        after = {"type": "split", "direction": "right", "ratio": 0.525, "second": column,     # as herdr leaves it
                 "first": {"type": "pane", "pane_id": "w1:p1", "label": "claude"}}
        fake = FakeHerdrSocket(os.path.join(tmp, "h.sock"), {"w1:t1": (after, False)})
        self.addCleanup(fake.server.close)
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "conversations", "Python"),
                              ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.changes(calls), [("pane", "close", "w1:p2")])
        self.assertEqual([params for method, params in fake.calls if method == "layout.set_split_ratio"],
                         [{"tab_id": "w1:t1", "path": [], "ratio": 0.75}])
        self.assertEqual(self.said, [("ok", "column_gone", "app")])

    def test_a_pane_the_user_named_conversations_stays(self):
        # herdr's Rename pane: an agent's pane named "conversations" is no old column; the old column's is Python's
        calls = self.restore([("w1:t1", "conversations", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": None})
        self.assertNotIn(("pane", "close", "w1:p1"), calls)

    def test_what_an_older_install_kept_for_its_column_goes(self):
        # the column's width and fold in conversations.json: gone at once, the rest kept; no file made where none was
        conversations.keep(self.state, archived=["claude:s1"])
        with open(os.path.join(self.state, conversations.SETTINGS)) as f:
            kept = {**json.load(f), "ratio": 0.62, "collapsed": True}
        with open(os.path.join(self.state, conversations.SETTINGS), "w") as f:
            json.dump(kept, f)
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(conversations.setting(self.state), {"archived": ["claude:s1"]})
        os.remove(os.path.join(self.state, conversations.SETTINGS))
        self.restore([("w1:t1", "claude", "claude")], agents={"w1:p1": "app"})
        self.assertFalse(os.path.exists(os.path.join(self.state, conversations.SETTINGS)))

    def test_a_sidebar_running_another_program_keeps_its_tab_as_it_is(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "herdr-sidebar"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual([c for c in calls if c[:2] in (("pane", "close"), ("pane", "split"))], [])

    def test_a_fresh_herdrs_only_shell_gets_the_column(self):
        # herdr makes its very first workspace before the plugins start, so the new-tab event never reaches it
        self.assertEqual(self.splits_of(self.restore([("w1:t1", "", "zsh")])), ["w1:p1"])
        self.assertEqual(self.said, [("ok", "done", "app", "column")])

    def test_a_users_own_shell_tabs_get_no_column(self):
        self.assertEqual(self.changes(self.restore([("w1:t1", "", "zsh"), ("w1:t2", "", "zsh")])), [])

    def test_a_tab_with_its_column_is_left_alone(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.splits_of(calls), [])

    def test_a_pane_already_running_is_not_told_of(self):
        # nothing was done to it, and what program runs there is none of the user's business
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(self.said, [])

    def test_a_lone_other_program_is_left_alone(self):
        # e.g. the sidebar's file preview tab
        self.assertEqual(self.splits_of(self.restore([("w1:t2", "", "less")])), [])

    def test_an_empty_sidebar_runs_the_sidebar_again(self):
        # herdr brings a plain pane back as a shell after a restart
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "zsh"),
                              ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.changes(calls), [("pane", "run", "w1:p2", panes.sidebar_command())])
        self.assertEqual(self.said, [("ok", "done", "app", "sidebar")])

    def test_a_missing_terminal_is_added_under_the_sidebar(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python")], agents={"w1:p1": "app"})
        splits = [c for c in calls if c[:2] == ("pane", "split")]
        self.assertEqual([(c[3], c[5]) for c in splits], [("w1:p2", "down")])
        self.assertIn("terminal", [c[3] for c in calls if c[:2] == ("pane", "rename")])
        self.assertEqual(self.said, [("ok", "terminal_added", "app")])

    def test_a_terminal_whose_sidebar_is_gone_gets_it_back_above(self):
        # e.g. closed by hand: the terminal keeps what runs in it, a new sidebar goes on top
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        split = [c for c in calls if c[:2] == ("pane", "split")]
        self.assertEqual([(c[3], "down" in c) for c in split], [("w1:p2", True)])
        new = f"new{calls.index(split[0]) + 1}"
        self.assertIn(("pane", "swap", "--source-pane", new, "--target-pane", "w1:p2"), calls)
        self.assertIn(("pane", "rename", new, "sidebar"), calls)
        self.assertEqual([c[2] for c in calls if c[:2] == ("pane", "run")], [new])
        self.assertEqual(self.said, [("ok", "sidebar_back", "app")])

    def closed_by_hand(self):
        """The tab w1:t1 has had every pane: one missing now was closed by hand."""
        panels.note(self.state, {"w1:t1": set(panels.KINDS)})

    def test_a_sidebar_closed_by_hand_stays_closed(self):
        self.closed_by_hand()
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "terminal", "zsh")], agents={"w1:p1": "app"})
        self.assertEqual(self.sidebars_made(calls), [])

    def test_a_terminal_closed_by_hand_stays_closed(self):
        self.closed_by_hand()
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python")], agents={"w1:p1": "app"})
        self.assertNotIn("terminal", [c[3] for c in calls if c[:2] == ("pane", "rename")])

    def test_an_agent_whose_panes_were_all_closed_by_hand_gets_none_back(self):
        self.closed_by_hand()
        self.assertEqual(self.splits_of(self.restore([("w1:t1", "claude", "claude")], agents={"w1:p1": "app"})), [])

    def test_what_each_tab_has_is_kept(self):
        self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "Python"), ("w1:t1", "terminal", "zsh")],
                     agents={"w1:p1": "app"})
        self.assertEqual(panels.had(self.state, "w1:t1"), set(panels.KINDS))

    def test_a_sidebar_on_windows_is_not_typed_into(self):
        # herdr on Windows names only the shell for a program that is not an agent: the sidebar may be running
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh")], agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app")
        self.assertEqual([c for c in calls if c[:2] == ("pane", "run")], [])

    def test_a_sidebar_on_windows_starts_when_herdr_starts(self):
        calls = self.restore([("w1:t1", "claude", "claude"), ("w1:t1", "sidebar", "pwsh"),
                              ("w1:t1", "terminal", "pwsh")], agents={"w1:p1": "app"}, cwd="C:\\Users\\dev\\app",
                             starting=True)
        self.assertEqual([c[2] for c in calls if c[:2] == ("pane", "run")], ["w1:p2"])


if __name__ == "__main__":
    unittest.main()
