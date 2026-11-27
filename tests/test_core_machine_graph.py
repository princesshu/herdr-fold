"""Tests for core/machine_graph.py: the machines' graph of graph.html's lumen-api world (Wiring, NetBird off, two
routes, behind), its nodes in four columns, its edges' styles and labels, each node's properties the Machines view's
rows; the app's command. Invented machines and addresses, the catalog's own words."""
import contextlib
import io
import json
import os
import sys
import time
import unittest

from support import PACKAGE, catalog_text, set_attrs, set_env

sys.path.insert(0, os.path.join(PACKAGE, "tools"))          # build.py's words (MACHINE_WORDS), behind core's own
sys.path.insert(0, os.path.join(PACKAGE, "core"))           # icons: core's, not tools/icons.py
import build  # noqa: E402
import machine_graph  # noqa: E402

AT = "@"                        # a user before a host: put together here, never an e-mail's look
NOW = 1_795_000_000             # the look's time, UTC
KEYS = {"build-01": "SHA256:Qm9vZ0x1" + "b" * 31 + "a7Fk", "studio": "SHA256:Lb3sT0dI" + "m" * 31 + "9qXe"}
KEPT = {name: True for name in ("lumen-api", "build-01", "db-02", "harbor-web", "studio", "lab-pi", "tidepool",
                                "kelp-ci", "vps-edge")}
RUNS = {"lumen-api": {"spaces": 2, "agents": [["claude", "working"]]}, "build-01": {"spaces": 1, "agents": [
    ["codex", "blocked"]]}, "studio": {"spaces": 1, "agents": []}}


def route(network, address, user="root", through=None):
    return {"network": "through" if through else network, "address": address, "user": user, "port": None,
            "through": through}


def why(key, *args, command=None, todo=None):
    action = {"key": todo, "args": [], "command": command} if todo else None
    return {"key": key, "args": list(args), "action": action, "then": None}


def machine(name, network, address, os_="linux", user="root", through=None, said=None, path=None, ms=None,
            routes=None):
    return {"name": name, "os": os_, "target": f"herdr-fold.{name}" if through else user + AT + address,
            "network": "through" if through else network, "through": through, "why": said,
            "figures": {"path": path, "relay": None, "login_ms": ms, "seen": None},
            "routes": routes or [route(network, address, user, through)], "key": KEYS.get(name)}


def here(netbird="on"):
    """What core/networks.py's here says of graph.html's machines (NETBIRD its client's state)."""
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
              machine("vps-edge", "public", "203.0.113.40")]
    return {"checked": NOW, "machines": listed,
            "networks": {"tailscale": {"installed": True, "state": "on", "why": None, "offered": []},
                         "netbird": {"installed": True, "state": netbird, "why": stopped, "offered": []},
                         "zerotier": {"installed": True, "state": "on", "why": None, "offered": []},
                         "wireguard": {"installed": False, "state": None, "why": None, "offered": []}}}


def drawn(said=None, runs=RUNS, kept=KEPT):
    return machine_graph.graph(machine_graph.seen(said or here()), catalog_text, runs, kept, NOW)


def nodes(graph):
    return {one["id"]: one for one in graph["nodes"]}


def edges(graph):
    return [(one["from"], one["to"], one["style"], one["label"]) for one in graph["edges"]]


class Shape(unittest.TestCase):
    def setUp(self):
        set_env(self, TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)

    def test_this_mac_the_networks_the_machines_and_those_behind_in_four_columns(self):
        # the networks in the routes' order and the machines by name, as the Machines view lists them (the owner's
        # rulings for Tasks 10 and 11); a machine behind another in Through, under its jump host
        graph = drawn()
        self.assertEqual(graph["columns"], ["mac", "networks", "machines", "through"])
        self.assertEqual(graph["words"]["columns"], {"mac": "This Mac", "networks": "Networks", "machines": "Machines",
                                                     "through": "Through"})
        self.assertEqual(graph["words"]["legend"], [["always", "direct"], ["demand", "relayed"],
                                                    ["standby", "standby route"], ["failed", "away"]])
        self.assertEqual(graph["checked"], NOW)
        self.assertEqual([(one["id"], one["column"]) for one in graph["nodes"]], [
            ("mac", "mac"), ("network:local", "networks"), ("network:tailscale", "networks"),
            ("network:netbird", "networks"), ("network:zerotier", "networks"), ("network:public", "networks"),
            ("machine:lab-pi", "machines"), ("machine:studio", "machines"), ("machine:harbor-web", "machines"),
            ("machine:lumen-api", "machines"), ("machine:build-01", "through"), ("machine:db-02", "through"),
            ("machine:kelp-ci", "machines"), ("machine:tidepool", "machines"), ("machine:vps-edge", "machines")])

    def test_each_node_in_core_graphs_shape(self):
        # graph.py's node: what graph.js and the sidebar's tree already read; a network's mark by its word
        for one in drawn()["nodes"]:
            with self.subTest(one["id"]):
                self.assertLessEqual({"id", "column", "kind", "title", "icon", "brand", "tag", "sub", "state", "dim",
                                      "chips", "parent", "properties", "run"}, set(one))
        shown = nodes(drawn())
        self.assertEqual([shown["mac"][key] for key in ("kind", "title", "icon", "sub", "parent")],
                         ["mac", "This Mac", "monitor", "5 networks, 9 machines", None])
        self.assertEqual({key: [shown[f"network:{key}"][field] for field in ("title", "network", "sub", "tag")]
                          for key in ("local", "tailscale", "netbird", "zerotier", "public")}, {
            "local": ["Local network", "local", "2 machines", None],
            "tailscale": ["Tailscale", "tailscale", "4 machines", None],
            "netbird": ["NetBird", "netbird", "2 machines", None],
            "zerotier": ["ZeroTier", "zerotier", "none yet: add one by its address", None],
            "public": ["Public", "public", "1 machine", None]})
        self.assertEqual({one["parent"] for one in shown.values() if one["kind"] == "network"}, {"mac"})
        lumen, build_01 = shown["machine:lumen-api"], shown["machine:build-01"]
        self.assertEqual([lumen[key] for key in ("kind", "title", "icon", "tag", "sub", "state", "dim", "parent")],
                         ["machine", "lumen-api", "server", "linux", "2 spaces, Claude working", None, False,
                          "network:tailscale"])
        self.assertEqual(build_01["parent"], "machine:lumen-api")
        self.assertEqual(shown["machine:studio"]["tag"], "macos")

    def test_what_runs_on_a_machine_and_one_that_is_away(self):
        shown = nodes(drawn())
        build_01, db_02 = shown["machine:build-01"], shown["machine:db-02"]
        self.assertEqual((build_01["sub"], build_01["state"]), ("1 space, Codex waiting", "warn"))
        self.assertEqual(build_01["parts"], [["1 space", "text"], [", ", "text"], ["Codex waiting", "warn"]])
        self.assertEqual((db_02["sub"], db_02["state"], db_02["dim"]), ("unreachable", "bad", False))


class Edges(unittest.TestCase):
    def test_wiring_the_mac_to_each_network_each_machine_by_the_route_in_use(self):
        # direct solid, relayed dashed, its label the path word and the time its network tells (no login: none
        # measured); the machine's other route standby, no label; behind another solid, away failed, no label
        self.assertEqual(edges(drawn()), [
            ("mac", "network:local", "always", None), ("mac", "network:tailscale", "always", None),
            ("mac", "network:netbird", "always", None), ("mac", "network:zerotier", "always", None),
            ("mac", "network:public", "always", None),
            ("network:local", "machine:lab-pi", "always", None), ("network:local", "machine:studio", "always", None),
            ("network:tailscale", "machine:harbor-web", "demand", "relayed"),
            ("network:tailscale", "machine:lumen-api", "always", "direct"),
            ("machine:lumen-api", "machine:build-01", "always", None),
            ("machine:lumen-api", "machine:db-02", "failed", None),
            ("network:netbird", "machine:kelp-ci", "demand", "relayed 61 ms"),
            ("network:netbird", "machine:tidepool", "always", "direct 22 ms"),
            ("network:public", "machine:vps-edge", "always", None),
            ("network:tailscale", "machine:studio", "standby", None)])
        for one in drawn()["edges"]:
            self.assertEqual((one["gates"], one["run"]), ([], None))       # graph.py's edge

    def test_a_login_the_status_check_measured_labels_its_edge(self):
        said = here()
        said["machines"][1]["figures"]["login_ms"] = 19          # build-01, through lumen-api
        said["machines"][5]["figures"]["login_ms"] = 5           # lab-pi, on the local network
        found = edges(drawn(said))
        self.assertIn(("machine:lumen-api", "machine:build-01", "always", "19 ms"), found)
        self.assertIn(("network:local", "machine:lab-pi", "always", "5 ms"), found)


class NetworkOff(unittest.TestCase):
    """graph.html's Hálózat le: NetBird off on this Mac, its edge and its machines' failed, its node saying why."""

    def setUp(self):
        set_env(self, TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)
        self.graph = drawn(here(netbird="off"))

    def test_its_edge_failed_its_machines_away_and_dim(self):
        found = edges(self.graph)
        self.assertIn(("mac", "network:netbird", "failed", None), found)
        self.assertIn(("network:netbird", "machine:tidepool", "failed", None), found)
        self.assertIn(("network:netbird", "machine:kelp-ci", "failed", None), found)
        shown = nodes(self.graph)
        netbird, tidepool = shown["network:netbird"], shown["machine:tidepool"]
        self.assertEqual([netbird[key] for key in ("tag", "state", "dim", "sub")], ["off", None, True, "2 machines"])
        self.assertEqual([tidepool[key] for key in ("sub", "state", "dim")], ["unreachable", "bad", True])
        self.assertFalse(shown["machine:db-02"]["dim"])          # away on its own: its network is on

    def test_its_properties_say_why_and_what_to_do(self):
        props = nodes(self.graph)["network:netbird"]["properties"]
        self.assertEqual((props["title"], props["state"]), ("NetBird", {"text": "off", "tone": "muted"}))
        self.assertEqual(props["why"], [[["NetBird is not running on this Mac.", "warn"]],
                                        [["Start it: ", "muted"], ["netbird up", "text"]]])
        self.assertEqual(props["command"], "netbird up")
        self.assertEqual(props["lines"], [["Machines", [["kelp-ci, tidepool", "text"]], [], None],
                                          ["Checked", [["today 11:06", "text"]], [], None]])
        self.assertEqual([(one["id"], one["label"], one["primary"]) for one in props["actions"]],
                         [("check", "Check again", True), ("copy", "Copy command", False)])

    def test_a_machine_away_says_its_sentence_and_offers_to_look_again(self):
        props = nodes(self.graph)["machine:tidepool"]["properties"]
        self.assertEqual(props["state"], {"text": "unreachable", "tone": "muted"})
        self.assertEqual(props["why"][0], [["NetBird is not running on this Mac.", "warn"]])
        self.assertEqual([one["id"] for one in props["actions"]], ["check", "copy"])


class Properties(unittest.TestCase):
    """Each machine's properties are the Machines view's rows (Task 11), label left and value right."""

    def test_a_machine_behind_another_its_way_and_what_runs_there(self):
        props = nodes(drawn())["machine:build-01"]["properties"]
        self.assertEqual((props["title"], props["state"]), ("build-01", {"text": "connected", "tone": "ok"}))
        self.assertEqual((props["why"], props["command"]), ([], None))
        self.assertEqual(props["lines"], [
            ["Address", [["198.51.100.30", "text"]], [], None],
            ["User", [["root", "text"]], [], None],
            ["Network", [["through lumen-api", "text"]], [], None],
            ["Path", [["This Mac › Tailscale › lumen-api › build-01", "text"]], [], None],
            ["Key", [["SHA256:Qm9vZ0x1…a7Fk", "text"]], [], None],
            ["Runs", [["1 space", "text"], [", ", "text"], ["Codex waiting", "warn"]], [], None]])
        self.assertEqual([(one["id"], one["label"], one["primary"]) for one in props["actions"]], [
            ("status", "Status", True), ("again", "Set up again", False), ("remove", "Remove", False),
            ("through", "Look around from here…", False)])

    def test_a_machine_on_two_routes_lists_them_the_one_in_use_first(self):
        props = nodes(drawn())["machine:studio"]["properties"]
        self.assertEqual(props["lines"], [
            ["Routes", [["studio.local", "text"]], [["in use", "text"]], "local"],
            ["", [["studio.tail0000.ts.net", "text"]], [["standby", "muted"]], "tailscale"],
            ["User", [["dev", "text"]], [], None],
            ["Key", [["SHA256:Lb3sT0dI…9qXe", "text"]], [], None],
            ["Runs", [["1 space", "text"]], [], None]])

    def test_a_route_through_another_machine_says_so_and_a_measured_one_its_time(self):
        said = here()
        studio = said["machines"][4]
        studio["routes"][1] = route(None, "198.51.100.31", "dev", through="lumen-api")
        studio["figures"]["login_ms"] = 3
        props = nodes(drawn(said))["machine:studio"]["properties"]
        self.assertEqual(props["lines"][:2], [
            ["Routes", [["studio.local", "text"]], [["in use", "text"], ["  ", "text"], ["3 ms", "muted"]], "local"],
            ["", [["198.51.100.31", "text"], ["  ", "text"], ["through lumen-api", "muted"]], [["standby", "muted"]],
             "through"]])
        self.assertIn(("machine:lumen-api", "machine:studio", "standby", None), edges(drawn(said)))

    def test_a_machine_herdr_does_not_keep_is_not_connected(self):
        shown = nodes(drawn(kept={"lumen-api": True}, runs={}))
        self.assertEqual(shown["machine:lab-pi"]["properties"]["state"], {"text": "not connected", "tone": "muted"})
        self.assertEqual(shown["machine:lab-pi"]["sub"], "not connected")
        unknown = nodes(drawn(kept=None, runs={}))["machine:lab-pi"]
        self.assertEqual((unknown["properties"]["state"], unknown["sub"]), (None, None))     # herdr told nothing

    def test_a_windows_machine_offers_no_look_around(self):
        said = here()
        said["machines"][8]["os"] = "windows"
        props = nodes(drawn(said))["machine:vps-edge"]["properties"]
        self.assertEqual([one["id"] for one in props["actions"]], ["status", "again", "remove"])


class NetworkStates(unittest.TestCase):
    def test_a_signed_out_network_warns_and_an_empty_one_offers_its_machines(self):
        said = here()
        said["networks"]["tailscale"]["state"] = "signed_out"
        said["machines"] = [one for one in said["machines"] if one["network"] != "netbird"]
        said["networks"]["netbird"]["offered"] = ["kelp-ci", "tidepool", "reef-mac"]
        graph = drawn(said)
        shown = nodes(graph)
        tailscale, netbird = shown["network:tailscale"], shown["network:netbird"]
        self.assertEqual([tailscale[key] for key in ("tag", "state", "dim")], ["signed out", "warn", False])
        self.assertIn(("mac", "network:tailscale", "failed", None), edges(graph))
        self.assertEqual(netbird["sub"], "3 machines to add")
        self.assertEqual([(one["id"], one["label"]) for one in netbird["properties"]["actions"]],
                         [("add", "3 machines to add")])
        self.assertEqual(netbird["properties"]["lines"], [])          # the names a count only, as the list's row

    def test_a_network_reached_by_a_standby_route_alone_has_its_node(self):
        said = here()
        said["machines"] = [one for one in said["machines"]
                            if one["name"] not in ("lumen-api", "build-01", "db-02", "harbor-web")]
        graph = drawn(said)
        shown = nodes(graph)
        self.assertIn("network:tailscale", shown)
        self.assertEqual(shown["network:tailscale"]["sub"], None)
        self.assertIn(("network:tailscale", "machine:studio", "standby", None), edges(graph))

    def test_a_machine_no_network_tells_stands_under_other(self):
        said = here()
        said["machines"].append(machine("reef-box", None, "198.51.100.77"))
        graph = drawn(said)
        shown = nodes(graph)
        self.assertEqual([one["id"] for one in graph["nodes"] if one["kind"] == "network"][-1], "network:other")
        self.assertEqual((shown["network:other"]["title"], shown["network:other"]["network"]), ("Other", None))
        self.assertEqual(shown["mac"]["sub"], "5 networks, 10 machines")       # Other is no network
        self.assertIn(("network:other", "machine:reef-box", "always", None), edges(graph))


class Command(unittest.TestCase):
    """The app runs it on this Mac (helper.js's MACHINE_GRAPH): the look's JSON, the catalog's words (MACHINE_WORDS),
    what runs on each machine and the machines herdr keeps, everything checked first."""

    def run_it(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = machine_graph.main(["machine_graph.py", *args])
        return code, out.getvalue()

    def test_it_answers_the_graph_in_json(self):
        set_env(self, TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)
        code, out = self.run_it(json.dumps(here()), json.dumps(build.machine_words()), f"--runs={json.dumps(RUNS)}",
                                f"--kept={json.dumps(KEPT)}")
        self.assertEqual(code, 0)
        made = json.loads(out)
        self.assertEqual(made["nodes"][:2], json.loads(json.dumps(drawn()["nodes"][:2])))
        self.assertEqual(nodes(made)["machine:build-01"]["sub"], "1 space, Codex waiting")
        self.assertEqual(nodes(made)["network:zerotier"]["sub"], "none yet: add one by its address")

    def test_the_look_comes_through_its_input(self):
        # the app pipes networks.py's here into it (LOOK -): a look of many machines is never one argument
        set_env(self, TZ="UTC")
        time.tzset()
        self.addCleanup(time.tzset)
        set_attrs(self, sys, stdin=io.StringIO(json.dumps(here())))
        code, out = self.run_it("-", json.dumps(build.machine_words()), f"--runs={json.dumps(RUNS)}",
                                f"--kept={json.dumps(KEPT)}")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["nodes"], json.loads(json.dumps(drawn()["nodes"])))
        # more than it reads, or nothing: no look
        err = io.StringIO()
        set_attrs(self, machine_graph, LOOK_MOST=64)
        with contextlib.redirect_stderr(err):
            for given in (json.dumps(here()), ""):
                set_attrs(self, sys, stdin=io.StringIO(given))
                self.assertEqual(self.run_it("-", json.dumps(build.machine_words()))[0], 2)
        self.assertIn("usage: machine_graph.py LOOK WORDS", err.getvalue())

    def test_what_it_is_given_is_checked(self):
        runs = {"lumen-api": {"spaces": 10 ** 9, "agents": [["evil\x1b]0;x\x07", "blocked"], "x"]},
                "a;b": {"spaces": 1, "agents": []}, "kelp-ci": "many"}
        code, out = self.run_it(json.dumps(here()), json.dumps({"machines.network_local": "Local network",
                                                                "machines.x": 7}),
                                f"--runs={json.dumps(runs)}", "--kept=[1, 2]")
        self.assertEqual(code, 0)
        made = nodes(json.loads(out))
        self.assertIsNone(made["machine:lumen-api"]["sub"])      # a count past any herdr keeps, no agent: no runs
        self.assertEqual(made["machine:lab-pi"]["properties"]["state"], None)       # herdr's list not of its shape
        self.assertEqual(made["network:local"]["title"], "Local network")
        self.assertEqual(made["network:tailscale"]["title"], "")              # a word it was not given says nothing

    def test_a_wrong_call_says_how_to_call_it(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.run_it("{not json", "{}")[0], 2)
            self.assertEqual(self.run_it(json.dumps(here()))[0], 2)
        self.assertIn("usage: machine_graph.py LOOK WORDS", err.getvalue())


if __name__ == "__main__":
    unittest.main()
