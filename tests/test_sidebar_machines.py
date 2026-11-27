"""Tests for the sidebar's Machines view (src/plugins/sidebar/machines_view.py, the pane the sidebar's ⋯ opens), as
machines.html's TUI frames at 60 and 100 cells: by network, a network off, behind, two routes, the keys and actions;
the tree g opens in the preview tab as graph.html's TUI frames; core's look and herdr stood in for, nothing reached."""
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import PACKAGE, SRC, FakeTerminal, end_jobs, inset_band, set_attrs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import layers  # noqa: E402
import machines_view  # noqa: E402
import pager  # noqa: E402
import sidebar  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402

AT = "@"                        # a user before a host: put together here, never an e-mail's look
NOW = 1_795_000_000             # the look's time, UTC
KEYS = {"build-01": "SHA256:Qm9vZ0x1" + "b" * 31 + "a7Fk", "studio": "SHA256:Lb3sT0dI" + "m" * 31 + "9qXe"}
LAN, GLOBE = "\U000f0317", ""         # the local network's and Public's Nerd Font marks (core/icons.py)
SCRIPT = os.path.join(PACKAGE, "machines.sh")
# what runs there as graph.html's TUI frames say: two spaces and Claude working on lumen-api, Codex waiting on build-01
FRAME_RUNS = {"spaces": {"lumen-api": 2}, "agents": {"lumen-api": [{"agent": "claude", "agent_status": "working"}],
                                                     "build-01": [{"agent": "codex", "agent_status": "blocked"}]}}


def route(network, address, user="root", through=None):
    return {"network": "through" if through else network, "address": address, "user": user, "port": None,
            "through": through}


def why(key, *args, command=None, todo=None):
    action = {"key": todo, "args": [], "command": command} if todo else None
    return {"key": key, "args": list(args), "action": action, "then": None}


def machine(name, network, address, os_="linux", user="root", through=None, said=None, path=None, ms=None, seen=None,
            routes=None):
    return {"name": name, "os": os_, "target": f"herdr-fold.{name}" if through else user + AT + address,
            "network": "through" if through else network, "through": through, "why": said,
            "figures": {"path": path, "relay": None, "login_ms": ms, "seen": seen},
            "routes": routes or [route(network, address, user, through)], "key": KEYS.get(name)}


def here(netbird="on", more=(), offered=()):
    """What core/networks.py's here says of machines.html's TUI machines (NETBIRD its client's state)."""
    off = netbird == "off"
    stopped = why("machines.why_netbird_off", command="netbird up", todo="machines.why_do_start") if off else None
    listed = [machine("lumen-api", "tailscale", "lumen-api.tail0000.ts.net", path="direct"),
              machine("build-01", "tailscale", "198.51.100.30", through="lumen-api"),
              machine("db-02", "tailscale", "db-02.local", through="lumen-api",
                      said=why("machines.why_no_answer", "db-02")),
              machine("harbor-web", "tailscale", "harbor-web.tail0000.ts.net", path="relayed"),
              machine("studio", "local", "studio.local", "macos", "dev",
                      routes=[route("local", "studio.local", "dev"),
                              route("tailscale", "studio.tail0000.ts.net", "dev")]),
              machine("lab-pi", "local", "lab-pi.local", user="pi"),
              machine("tidepool", "netbird", "tidepool.netbird.cloud", path=None if off else "direct",
                      ms=None if off else 22, said=stopped),
              machine("kelp-ci", "netbird", "kelp-ci.netbird.cloud", path=None if off else "relayed",
                      ms=None if off else 61, said=stopped),
              machine("vps-edge", "public", "203.0.113.40"), *more]
    return {"checked": NOW, "machines": listed,
            "networks": {"tailscale": {"installed": True, "state": "on", "why": None, "offered": list(offered)},
                         "netbird": {"installed": True, "state": netbird, "why": stopped, "offered": []},
                         "zerotier": {"installed": True, "state": "on", "why": None, "offered": []},
                         "wireguard": {"installed": False, "state": None, "why": None, "offered": []}}}


class Herdr:
    """herdr's command line as the view asks it: the machines it keeps, each one's workspaces and agents, a tab."""

    def __init__(self, saved=("lumen-api", "build-01", "db-02", "harbor-web", "studio", "lab-pi", "tidepool",
                              "kelp-ci", "vps-edge"), agents=None, spaces=None):
        self.saved, self.calls, self.spaces = saved, [], spaces or {}
        self.agents = {"build-01": [{"agent": "codex", "agent_status": "blocked"}]} if agents is None else agents

    def text(self, *args):
        self.calls.append(args)
        if args == ("machine", "list", "--json"):
            return json.dumps([{"id": f"m{n}", "label": name, "target": "x", "enabled": True}
                               for n, name in enumerate(self.saved)])
        return ""

    def call(self, *args):
        self.calls.append(args)
        if args[:1] == ("--machine",) and args[2:] == ("workspace", "list"):
            count = self.spaces.get(args[1], 1)
            return {"workspaces": [{"workspace_id": f"w{n}", "label": "api"} for n in range(count)]}
        if args[:1] == ("--machine",) and args[2:] == ("agent", "list"):
            return {"agents": self.agents.get(args[1], [])}
        if args[:2] == ("tab", "create"):
            return {"tab": {"tab_id": "w1:t9"}, "root_pane": {"pane_id": "w1:p9"}}
        return {}


class View(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.beside = os.path.join(self.tmp, "home", ".config", "herdr-fold")
        os.makedirs(self.beside)
        with open(os.path.join(self.beside, "setup-folder"), "w") as f:
            f.write(PACKAGE + "\n")
        set_env(self, HOME=os.path.join(self.tmp, "home"), HERDR_WORKSPACE_ID="w1", TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)
        set_attrs(self, machines_view, BESIDE=self.beside)
        self.said, self.looked = here(), []
        patch = mock.patch.object(machines_view, "look", lambda folder, listed: (
            self.looked.append((folder, listed)), self.said)[1])
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(end_jobs)

    def open(self, cells=100, rows=48, herdr=None):
        self.herdr = herdr or Herdr()
        app = machines_view.MachinesView(FakeTerminal(cells, rows), self.herdr, os.path.join(self.tmp, "plugin"),
                                         clock=lambda: 100.0, now=lambda: NOW)
        self.settle(app)
        return app

    def settle(self, app):
        for _ in range(3):
            end_jobs()
            app.collect()
        app.draw()

    def rows(self, app):
        return [text(app.canvas, y).rstrip() for y in range(app.canvas.height)]

    def row(self, app, words):
        return next(y for y, row in enumerate(self.rows(app)) if words in row)

    def keys(self, app, *names):
        for name in names:
            app.key(Key("char", name) if len(name) == 1 else Key(name))
        self.settle(app)

    @staticmethod
    def line(*parts, right="", cells=100):
        """A row as drawn: each (column, words) where it starts, RIGHT ending a cell inside the highlight's end."""
        row = [" "] * cells
        for x, words in parts + ((cells - 2 - len(right), right),):
            row[x:x + len(words)] = words
        return "".join(row).rstrip()

    # --- the list (frame: grouped and behind)

    def test_the_machines_by_network_in_the_routes_order(self):
        # the networks in the order a machine's routes are tried (the app's), a machine under the route it is reached
        # by, those behind another under it with └, by name; the marks: a brand's letter, else its Nerd Font glyph
        app = self.open()
        shown = self.rows(app)
        line = self.line
        self.assertEqual(shown[1:16], [
            line((1, LAN), (4, "Local network"), right="2"),
            line((4, "●"), (6, "lab-pi"), (20, "linux")),
            line((4, "●"), (6, "studio"), (20, "macos")),
            line((1, "T"), (4, "Tailscale"), right="4"),
            line((4, "●"), (6, "harbor-web"), (20, "linux"), right="relayed"),
            line((4, "●"), (6, "lumen-api"), (20, "linux"), right="direct"),
            line((6, "└"), (8, "●"), (10, "build-01"), (20, "linux"), right="waiting"),
            line((6, "└"), (8, "○"), (10, "db-02"), (20, "linux"), right="unreachable"),
            line((1, "N"), (4, "NetBird"), right="2"),
            line((4, "●"), (6, "kelp-ci"), (20, "linux"), right="relayed 61 ms"),
            line((4, "●"), (6, "tidepool"), (20, "linux"), right="direct 22 ms"),
            line((1, "Z"), (4, "ZeroTier")),                   # none of its own: no count
            line((4, "none yet: add one by its address")),
            line((1, GLOBE), (4, "Public"), right="1"),
            line((4, "●"), (6, "vps-edge"), (20, "linux"))])
        self.assertEqual(shown[16], "")
        # the colors: a dot green while nothing is wrong, dim away; waiting yellow; NetBird's letter its own orange
        cells = app.canvas.rows
        self.assertEqual(cells[5][4][1].fg, "added")
        self.assertEqual((cells[8][8][1].fg, cells[8][10][1].fg), ("muted", "muted"))
        self.assertEqual(cells[7][91][1].fg, "modified")
        self.assertEqual(cells[9][1][1].fg, "#f68330")
        self.assertTrue(cells[9][4][1].bold)
        self.assertEqual(self.looked, [(PACKAGE, os.path.join(self.beside, "machines.txt"))])

    def test_at_60_cells_a_long_name_is_cut_and_its_system_and_state_stay(self):
        self.said = here(more=[machine("lumen-api-staging-eu-west-replica-02", "public", "203.0.113.41")])
        app = self.open(cells=60)
        shown = self.rows(app)
        self.assertIn(self.line((1, "T"), (4, "Tailscale"), right="4", cells=60), shown)
        self.assertIn(self.line((4, "●"), (6, "kelp-ci"), (38, "linux"), right="relayed 61 ms", cells=60), shown)
        cut = next(row for row in shown if "lumen-api-staging" in row)
        self.assertEqual(cut, self.line((4, "●"), (6, "lumen-api-staging-eu-west-rep…"), (38, "linux"), cells=60))

    def test_the_cursor_is_the_chosen_machine_a_cell_in_from_each_side(self):
        app = self.open()
        inset_band(self, app.canvas, self.row(app, "lab-pi"))
        self.keys(app, "down", "down", "down")
        inset_band(self, app.canvas, self.row(app, "lumen-api"))
        self.keys(app, "up", "up", "up", "up")                  # the heads are no stop: it stays on the first one
        inset_band(self, app.canvas, self.row(app, "lab-pi"))

    # --- the chosen machine's properties

    def properties(self, app):
        shown = self.rows(app)
        return shown[shown.index("", 1) + 1:]

    def test_a_machine_behind_another_says_its_way_and_what_runs_there(self):
        app = self.open()
        self.keys(app, "down", "down", "down", "down")          # lab-pi, studio, harbor-web, lumen-api, build-01
        got = self.properties(app)
        self.assertEqual(got[:8], [
            self.line((1, "build-01"), right="connected"),
            self.line((4, "Address"), (14, "198.51.100.30")),
            self.line((4, "User"), (14, "root")),
            self.line((4, "Network"), (14, "through lumen-api")),
            self.line((4, "Path"), (14, "This Mac › Tailscale › lumen-api › build-01")),
            self.line((4, "Key"), (14, "SHA256:Qm9vZ0x1…a7Fk")),
            self.line((4, "Runs"), (14, "1 space, Codex waiting")),
            self.line((4, " Status   Set up again   Remove   ⋯ "))])
        y, head = self.row(app, "Runs "), self.rows(app).index("", 1) + 1
        self.assertEqual(app.canvas.rows[y][27][1].fg, "modified")              # Codex waiting: yellow
        self.assertEqual(app.canvas.rows[head][89][1].fg, "added")              # connected: green
        buttons = self.row(app, " Status ")
        self.assertEqual(app.canvas.rows[buttons][5][1].bg, "button")           # the first, the one Enter presses
        self.assertIn(("--machine", "build-01", "agent", "list"), self.herdr.calls)
        self.assertNotIn(("--machine", "db-02", "agent", "list"), self.herdr.calls)     # away: herdr not asked

    def test_one_machine_on_two_routes_lists_them_the_one_in_use_first(self):
        app = self.open()
        self.keys(app, "down")
        got = self.properties(app)
        self.assertEqual(got[:6], [
            self.line((1, "studio"), right="connected"),
            self.line((4, "Routes"), (14, LAN), (17, "studio.local"), right="in use"),
            self.line((14, "T"), (17, "studio.tail0000.ts.net"), right="standby"),
            self.line((4, "User"), (14, "dev")),
            self.line((4, "Key"), (14, "SHA256:Lb3sT0dI…9qXe")),
            self.line((4, "Runs"), (14, "1 space"))])
        self.assertNotIn("Address", "\n".join(got))             # its routes say where and on which network

    def test_a_machine_herdr_does_not_keep_is_not_connected(self):
        app = self.open(herdr=Herdr(saved=("lumen-api",)))
        self.assertEqual(self.properties(app)[0], self.line((1, "lab-pi"), right="not connected"))
        self.assertNotIn("Runs", "\n".join(self.properties(app)))

    # --- a network off (frame: NetBird off)

    def test_a_network_off_says_so_its_machines_away_with_the_ladders_sentence(self):
        self.said = here(netbird="off")
        app = self.open()
        shown = self.rows(app)
        head = self.row(app, "NetBird")
        self.assertEqual(shown[head], self.line((1, "N"), (4, "NetBird"), (13, "off"), right="2"))
        self.assertEqual([app.canvas.rows[head][x][1].fg for x in (4, 13)], ["muted", "muted"])
        self.assertEqual(shown[head + 2], self.line((4, "○"), (6, "tidepool"), (20, "linux"), right="unreachable"))
        self.keys(app, *["down"] * 7)                           # past db-02 and kelp-ci, to tidepool
        got = self.properties(app)
        self.assertEqual(got[:8], [
            self.line((1, "tidepool"), right="unreachable"),
            self.line((4, "NetBird is not running on this Mac.")),
            self.line((4, "Start it: netbird up")),
            "",
            self.line((4, "Address"), (14, "tidepool.netbird.cloud")),
            self.line((4, "User"), (14, "root")),
            self.line((4, "Network"), (14, "NetBird")),
            self.line((4, " Check again   Copy command "))])
        y = self.row(app, "Start it")
        self.assertEqual([app.canvas.rows[y][x][1].fg for x in (4, 14)], ["muted", "text"])
        self.assertEqual(app.canvas.rows[self.row(app, "is not running")][4][1].fg, "modified")
        copied = []
        app.clipboard = lambda words: copied.append(words) or True
        self.keys(app, "right", "enter")
        self.assertEqual(copied, ["netbird up"])
        self.assertIn("Copied", "\n".join(self.rows(app)))
        looks = len(self.looked)
        self.keys(app, "left", "enter")                         # Check again: the networks looked at once more
        self.assertEqual(len(self.looked), looks + 1)

    def test_a_network_signed_out_says_it_in_yellow_and_an_empty_one_offers_its_machines(self):
        self.said = here(offered=["reef-mac", "kelp-ci"])
        self.said["networks"]["tailscale"]["state"] = "signed_out"
        self.said["machines"] = [one for one in self.said["machines"] if one["network"] != "netbird"]
        self.said["networks"]["netbird"]["offered"] = ["kelp-ci", "tidepool", "reef-mac"]
        app = self.open()
        head = self.row(app, "Tailscale")
        self.assertEqual(self.rows(app)[head], self.line((1, "T"), (4, "Tailscale"), (15, "signed out"), right="4"))
        self.assertEqual(app.canvas.rows[head][15][1].fg, "modified")
        netbird = self.row(app, "NetBird")
        self.assertEqual(self.rows(app)[netbird], self.line((1, "N"), (4, "NetBird")))
        self.assertEqual(self.rows(app)[netbird + 1], self.line((4, "+ Add 3 machines…")))
        for _ in range(12):
            if "+ Add " in self.rows(app)[app_cursor(app)]:
                break
            self.keys(app, "down")
        self.keys(app, "enter")
        self.assertEqual(self.ran(), ("NetBird", ["/bin/bash", SCRIPT, "netbird"]))

    def test_with_no_machine_on_the_list_it_says_so_and_enter_starts_nothing_unasked(self):
        # the owner's ruling (2026-11-27): the list's empty state at the top in the catalog's words, no count of 0, and
        # the row to add a stop the keys reach only on ↓ or a click, as it starts ./machines.sh's questions
        self.said = here(offered=["reef-mac", "kelp-ci", "tide-box", "studio"])
        self.said["machines"] = []
        app = self.open()
        self.assertEqual(self.rows(app)[1:6], [
            self.line((1, "No machine on the list yet.")),
            self.line((1, "T"), (4, "Tailscale")),
            self.line((4, "+ Add 4 machines…")),
            self.line((1, "Z"), (4, "ZeroTier")),
            self.line((4, "none yet: add one by its address"))])
        y = self.row(app, "+ Add ")
        self.assertIsNone(app.canvas.rows[y][1][1].bg)                          # not chosen
        self.keys(app, "enter")
        self.assertEqual([call for call in self.herdr.calls if call[:2] == ("tab", "create")], [])
        self.keys(app, "down")
        inset_band(self, app.canvas, y)
        self.keys(app, "enter")
        self.assertEqual(self.ran(), ("Tailscale", ["/bin/bash", SCRIPT, "tailscale"]))
        self.said["networks"]["tailscale"]["offered"] = []                      # nothing offered: how to add one
        self.said["networks"]["zerotier"]["state"] = "off"
        app = self.open()
        self.assertEqual(self.rows(app)[1:4], [self.line((1, "No machine on the list yet.")),
                                               self.line((1, "Ctrl+B, Shift+M adds one")), ""])

    # --- the actions: ./machines.sh in a terminal tab on this Mac

    def ran(self):
        """The tab the last action opened: its label and the argv its pane ran."""
        made = [call for call in self.herdr.calls if call[:2] == ("tab", "create")][-1]
        run = [call for call in self.herdr.calls if call[:2] == ("pane", "run")][-1]
        self.assertEqual(made[2:6], ("--workspace", "w1", "--cwd", PACKAGE))
        self.assertIn(("pane", "rename", "w1:p9", "machines"), self.herdr.calls)  # the dock leaves the tab alone
        self.assertIn(("tab", "focus", "w1:t9"), self.herdr.calls)
        return made[made.index("--label") + 1], shlex.split(run[3])

    def test_enter_runs_its_status_in_a_tab_and_s_does_too(self):
        app = self.open()
        self.keys(app, "down", "down", "down", "down", "enter")
        self.assertEqual(self.ran(), ("Status build-01", ["/bin/bash", SCRIPT, "status", "build-01"]))
        self.herdr.calls.clear()
        self.keys(app, "up", "s")
        self.assertEqual(self.ran(), ("Status lumen-api", ["/bin/bash", SCRIPT, "status", "lumen-api"]))

    def test_set_up_again_and_remove_once_asked(self):
        app = self.open()
        self.keys(app, "right", "enter")
        self.assertEqual(self.ran(), ("Set up again lab-pi", ["/bin/bash", SCRIPT, "add", "lab-pi"]))
        self.herdr.calls.clear()
        self.keys(app, "right", "enter")                        # Remove asks first; Enter alone is Cancel
        self.assertIn("Take lab-pi off the list", "\n".join(self.rows(app)))
        self.keys(app, "enter")
        self.assertEqual([call for call in self.herdr.calls if call[:2] == ("pane", "run")], [])
        self.keys(app, "enter", "left", "enter")
        self.assertEqual(self.ran(), ("Remove lab-pi", ["/bin/bash", SCRIPT, "remove", "lab-pi"]))

    def test_look_around_from_here_is_in_its_more_menu(self):
        app = self.open()
        self.keys(app, "right", "right", "right", "enter")
        self.assertIn("Look around from here…", "\n".join(self.rows(app)))
        self.keys(app, "enter")
        self.assertEqual(self.ran(), ("Look around from lab-pi", ["/bin/bash", SCRIPT, "through", "lab-pi"]))

    def test_a_click_chooses_a_machine_and_presses_its_button_esc_closes(self):
        app = self.open()
        app.handle(Mouse("press", 30, self.row(app, "harbor-web"), 0))
        app.draw()
        self.assertEqual(self.properties(app)[0], self.line((1, "harbor-web"), right="connected"))
        y = self.row(app, " Status ")
        app.handle(Mouse("press", self.rows(app)[y].index("Set up again"), y, 0))
        self.settle(app)
        self.assertEqual(self.ran(), ("Set up again harbor-web", ["/bin/bash", SCRIPT, "add", "harbor-web"]))
        app.handle(Focus(True))
        self.keys(app, "esc")
        self.assertTrue(app.quit)

    def test_a_click_outside_closes_it(self):
        app = self.open()
        app.handle(Focus(False))
        self.assertTrue(app.quit)

    # --- how they connect: g, the tree in the preview tab (graph.html's TUI frames: normal, NetBird off)

    def tree(self, cells=100):
        """What g opens: open_preview's arguments, the tree's lines as written (with their colors) and as read."""
        app = self.open(cells=cells, herdr=Herdr(**FRAME_RUNS))
        with mock.patch.object(machines_view.preview, "open_preview") as opened:
            self.keys(app, "g")
        args = opened.call_args.args
        written = args[3]["views"][0]["lines"]
        return app, args, written, [pager.plain(line) for line in written]

    def test_g_shows_how_they_connect_as_a_tree_in_the_preview_tab(self):
        # This Mac, the networks in the routes' order, each one's machines by name, one behind another under its jump
        # host, its system, the way its network tells, what runs there; studio's other route dim under Tailscale
        app, args, written, shown = self.tree()
        line = self.line
        self.assertEqual(shown, [
            "This Mac  5 networks, 9 machines",
            line((0, "├ " + LAN), (5, "Local network")),
            line((0, "│ ├ lab-pi"), (16, "linux"), (38, "1 space")),
            line((0, "│ └ studio"), (16, "macos"), (38, "1 space")),
            line((0, "├ T"), (5, "Tailscale")),
            line((0, "│ ├ harbor-web"), (16, "linux"), (23, "relayed"), (38, "1 space")),
            line((0, "│ ├ lumen-api"), (16, "linux"), (23, "direct"), (38, "2 spaces, Claude working")),
            line((0, "│ │ ├ build-01"), (16, "linux"), (38, "1 space, Codex waiting")),
            line((0, "│ │ └ db-02"), (16, "linux"), (23, "unreachable")),
            line((0, "│ └ studio"), (16, "macos"), (23, "standby, in use: Local network")),
            line((0, "├ N"), (5, "NetBird")),
            line((0, "│ ├ kelp-ci"), (16, "linux"), (23, "relayed 61 ms"), (38, "1 space")),
            line((0, "│ └ tidepool"), (16, "linux"), (23, "direct 22 ms"), (38, "1 space")),
            line((0, "├ Z"), (5, "ZeroTier  none yet: add one by its address")),
            line((0, "└ " + GLOBE), (5, "Public")),
            line((0, "  └ vps-edge"), (16, "linux"), (38, "1 space")),
            "",
            "Checked today 11:06"])
        # the colors: the tree's lines dim, This Mac and a network bold, NetBird's letter its orange, a glyph muted; an
        # away machine red, an agent waiting yellow, a standby route dim throughout
        self.assertTrue(written[0].startswith("\x1b[1mThis Mac\x1b[0m"))
        self.assertTrue(written[2].startswith("\x1b[90m│ ├ \x1b[0m"))
        self.assertIn(f"\x1b[90m{LAN}\x1b[0m", written[1])
        self.assertIn("\x1b[1mTailscale\x1b[0m", written[4])
        self.assertIn("\x1b[38;2;246;131;48mN\x1b[0m", written[10])
        self.assertIn("\x1b[31mdb-02\x1b[0m", written[8])
        self.assertIn("\x1b[31munreachable\x1b[0m", written[8])
        self.assertIn("\x1b[33mCodex waiting\x1b[0m", written[7])
        self.assertIn("\x1b[90mstudio\x1b[0m", written[9])
        self.assertIn("\x1b[90mstandby, in use: Local network\x1b[0m", written[9])
        # in the preview tab of the workspace it was opened from, then out of the way
        self.assertEqual(args[1:3], ("w1", os.path.join(self.tmp, "home")))
        self.assertEqual(args[3]["title"], "machines")
        json.dumps(args[3])                                                     # it goes through a file
        self.assertTrue(app.quit)

    def test_a_network_off_says_why_in_the_tree_and_its_machines_are_dim(self):
        self.said = here(netbird="off")
        _, _, written, shown = self.tree()
        line = self.line
        self.assertEqual(shown[10:15], [                                        # under its name, as the view breaks it
            line((0, "├ N"), (5, "NetBird  off")),
            line((0, "│"), (5, "NetBird is not running on this Mac.")),
            line((0, "│"), (5, "Start it: netbird up")),
            line((0, "│ ├ kelp-ci"), (16, "linux"), (23, "unreachable")),
            line((0, "│ └ tidepool"), (16, "linux"), (23, "unreachable"))])
        self.assertEqual(shown[6], line((0, "│ ├ lumen-api"), (16, "linux"), (23, "direct"),
                                        (32, "2 spaces, Claude working")))
        self.assertIn("\x1b[1;90mNetBird\x1b[0m", written[10])                 # its name dimmed, off muted: the list's
        self.assertIn("\x1b[90moff\x1b[0m", written[10])
        self.assertIn("\x1b[33mNetBird is not running on this Mac.\x1b[0m", written[11])
        self.assertTrue(written[12].endswith("\x1b[90mStart it: \x1b[0mnetbird up"))
        self.assertIn("\x1b[90mkelp-ci\x1b[0m", written[13])
        self.assertIn("\x1b[90munreachable\x1b[0m", written[13])
        self.assertNotIn("\x1b[31m", written[13])

    # --- its foot: each key with its word, a click does it

    def test_its_keys_stand_at_its_foot_and_a_click_does_each(self):
        for cells in (100, 60):
            with self.subTest(cells=cells):
                app = self.open(cells=cells)
                y = app.canvas.height - 1
                self.assertEqual(self.rows(app)[y], self.line((1, "g Graph   s Status   Esc"), cells=cells))
                row = app.canvas.rows[y]
                self.assertEqual([(row[x][1].fg, row[x][1].bold) for x in (1, 3, 11, 13, 22)],
                                 [("text", True), ("subtext", False), ("text", True), ("subtext", False),
                                  ("text", True)])
        app.handle(Mouse("move", 4, y, 0))                      # the word under the mouse lit
        app.draw()
        self.assertEqual(app.canvas.rows[y][3][1].fg, "text")
        app.handle(Mouse("press", 12, y, 0))                    # s Status: the chosen machine's, in a tab
        self.settle(app)
        self.assertEqual(self.ran(), ("Status lab-pi", ["/bin/bash", SCRIPT, "status", "lab-pi"]))
        with mock.patch.object(machines_view.preview, "open_preview") as opened:
            app.handle(Mouse("press", 4, y, 0))                 # g Graph: the tree in the preview tab
            self.settle(app)
        self.assertEqual(opened.call_args.args[3]["title"], "machines")
        self.assertTrue(app.quit)
        app = self.open(cells=60)
        app.handle(Mouse("press", 23, app.canvas.height - 1, 0))       # Esc: closed
        self.assertTrue(app.quit)

    # --- what reaches a command, and the screen

    def test_what_a_network_or_the_list_says_is_checked(self):
        crafted = [machine("-oProxyCommand=x", "public", "203.0.113.50"), machine("a;b", "public", "203.0.113.51"),
                   machine("evil", "public", "evil box"),
                   machine("ok-box", "public", "203.0.113.52", said=why("machines.why_other", "ok-box",
                                                                        "\x1b]52;c;aGk=\x07refused"))]
        self.said = here(more=crafted, offered=["-oX", "fine-one"])
        found = machines_view.seen(self.said)
        names = [one["name"] for one in found["machines"]]
        self.assertNotIn("-oProxyCommand=x", names)
        self.assertNotIn("a;b", names)
        self.assertEqual(next(one for one in found["machines"] if one["name"] == "evil")["routes"], [])
        said = next(one for one in found["machines"] if one["name"] == "ok-box")["why"]
        self.assertEqual(said["args"], ["ok-box", "]52;c;aGk=refused"])           # no escape reaches the screen
        self.assertEqual(found["networks"]["tailscale"]["offered"], ["fine-one"])
        self.assertIsNone(machines_view.seen({"machines": [{"name": "x", "why": {"key": "rm -rf", "args": []}}]})[
            "machines"][0]["why"])

    def test_core_is_run_with_its_arguments_alone_and_its_failure_said(self):
        asked = []

        def run(argv, **kwargs):
            asked.append((argv, kwargs.get("env", {}).get("PATH", "")))
            return mock.Mock(returncode=0, stdout=json.dumps(here()), stderr="")
        found = machines_view.read_look(PACKAGE, "/tmp/list.txt", run)
        self.assertEqual(found["checked"], NOW)
        argv, path = asked[0]
        self.assertEqual(argv, [sys.executable, os.path.join(PACKAGE, "core", "networks.py"), "here", "/tmp/list.txt"])
        self.assertIn("/usr/sbin", path.split(os.pathsep))       # route and ifconfig, as a shell would find them
        with self.assertRaisesRegex(RuntimeError, "no such list"):
            machines_view.read_look(PACKAGE, "x", lambda argv, **kwargs: mock.Mock(returncode=2, stdout="",
                                                                                  stderr="no such list\n"))

    def test_without_the_package_it_says_where_to_get_it(self):
        os.remove(os.path.join(self.beside, "setup-folder"))
        app = self.open()
        self.assertIn("herdr-fold's installer", "\n".join(self.rows(app)))
        self.assertEqual(self.looked, [])
        y = app.canvas.height - 1                               # nothing to graph, none chosen: g and s muted
        self.assertEqual([app.canvas.rows[y][x][1].fg for x in (1, 3, 11, 22)], ["muted", "muted", "muted", "text"])
        with mock.patch.object(machines_view.preview, "open_preview") as opened:
            self.keys(app, "g")
            app.handle(Mouse("press", 4, y, 0))
            self.settle(app)
        opened.assert_not_called()

    def test_last_seen_reads_as_a_day_and_a_time(self):
        day = 86400
        self.assertEqual(machines_view.seen_words(NOW - 3600, NOW), "today " + time.strftime(
            "%-H:%M", time.localtime(NOW - 3600)))
        self.assertTrue(machines_view.seen_words(NOW - 3 * day, NOW).startswith(time.strftime(
            "%b %-d", time.localtime(NOW - 3 * day))))

    def test_a_standby_route_says_the_route_in_use_through_a_jump_host_too(self):
        nodes = {"network:local": {"kind": "network", "title": "Local network"},
                 "machine:lumen-api": {"kind": "machine", "title": "lumen-api"}}
        self.assertEqual(layers.standby_words(nodes, {"parent": "network:local"}),
                         "standby, in use: Local network")
        self.assertEqual(layers.standby_words(nodes, {"parent": "machine:lumen-api"}),
                         "standby, in use: through lumen-api")

    def test_it_starts_on_the_loops_own_run(self):
        # main() calls run() with no arguments: an action's method of that name broke the view's start
        self.assertIs(machines_view.MachinesView.run, machines_view.Loop.run)

    def test_nothing_it_keeps_hides_the_loops_own_methods(self):
        # an attribute or a method named as one of Loop's hides it (run() once did); only these three take Loop's on
        own = {name for name in dir(machines_view.Loop) if callable(getattr(machines_view.Loop, name))}
        app = self.open()
        self.assertEqual(sorted(own & set(vars(app))), [])
        self.assertEqual(sorted(own & set(vars(machines_view.MachinesView))), ["__init__", "collect", "deadlines"])


def app_cursor(app):
    """The row the keys are on, as last drawn."""
    return next(y for y in range(app.canvas.height) if app.canvas.rows[y][1][1].bg == "selection")


class InTheSidebar(unittest.TestCase):
    """The sidebar's ⋯ offers Machines… over Settings… where herdr-fold's package is, and opens the view."""

    class Herdr:
        def __init__(self):
            self.calls = []

        def call(self, *args):
            self.calls.append(args)
            return {"panes": [{"pane_id": "w1:p2", "tab_id": "w1:t1", "label": "sidebar"}]} if args[:2] == (
                "pane", "list") else {}

        def text(self, *args):
            self.calls.append(args)
            return ""                                           # herdr keeps no machine

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        set_env(self, HERDR_PANE_ID="w1:p2", HOME=self.tmp)
        self.beside = os.path.join(self.tmp, ".config", "herdr-fold")
        os.makedirs(self.beside)
        set_attrs(self, machines_view, BESIDE=self.beside)
        self.addCleanup(end_jobs)
        self.herdr = self.Herdr()
        self.app = sidebar.App(self.tmp, FakeTerminal(80, 30), self.herdr, os.path.join(self.tmp, "state"))

    def test_machines_is_offered_only_with_the_package(self):
        self.app.open_menu(0, 0)
        self.assertNotIn(machines_view.MACHINES, self.app.menu[0].choices)
        with open(os.path.join(self.beside, "setup-folder"), "w") as f:
            f.write(PACKAGE + "\n")
        self.app.open_menu(0, 0)
        self.assertEqual(self.app.menu[0].choices[-4:], [None, "Machines…", "Machines graph", "Settings…"])
        menu = self.app.menu[0]
        menu.index = menu.choices.index("Machines…")
        self.app.answer_menu(Key("enter"))
        end_jobs()
        self.assertIn(("plugin", "pane", "open", "--plugin", "herdr-fold.sidebar", "--entrypoint", "machines",
                       "--focus"), self.herdr.calls)

    def test_its_machines_graph_opens_the_tree_in_the_preview_tab(self):
        # the line under Machines…: the networks looked at afresh, then the tree the view's g opens, by one function
        with open(os.path.join(self.beside, "setup-folder"), "w") as f:
            f.write(PACKAGE + "\n")
        self.app.open_menu(0, 0)
        menu = self.app.menu[0]
        menu.index = menu.choices.index("Machines graph")
        with mock.patch.object(machines_view, "look", lambda folder, listed: here()), \
                mock.patch.object(self.app, "open_preview") as opened:
            self.app.answer_menu(Key("enter"))
            self.assertEqual(self.app.note, "Loading machines…")
            end_jobs()
            self.app.collect()
        spec, cwd = opened.call_args.args
        self.assertEqual((spec["title"], cwd), ("machines", self.app.root))
        shown = [pager.plain(line) for line in spec["views"][0]["lines"]]
        self.assertEqual(shown[:2], ["This Mac  5 networks, 9 machines", "├ " + LAN + "  Local network"])
        self.assertIn("│ │ └ db-02     linux  unreachable", shown)


    def test_its_loading_note_stays_while_the_look_runs_and_goes_with_it(self):
        # a slow look (up to 90 s) keeps "Loading machines…" past a note's 4 s; it ends, the note goes (a failure's
        # error line says why); any other note still goes by itself
        self.app.note = machines_view.LOADING
        self.app.running.add("machines-graph")
        self.app.note_due(100.0)
        self.assertFalse(self.app.note_due(100.0 + sidebar.NOTE + 60))
        self.assertEqual(self.app.note, "Loading machines…")
        self.app.running.discard("machines-graph")
        self.assertTrue(self.app.note_due(200.0))
        self.assertIsNone(self.app.note)
        self.app.note = "Archived"
        self.app.note_due(300.0)
        self.assertTrue(self.app.note_due(300.0 + sidebar.NOTE))
        self.assertIsNone(self.app.note)

if __name__ == "__main__":
    unittest.main()
