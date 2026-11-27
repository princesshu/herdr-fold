"""herdr-fold's Machines view in the TUI (the sidebar's ⋯ opens it over the tab: Machines…), as machines.html's TUI
frames: the list's machines by network from core/networks.py's look (no login, nothing scanned), the chosen one's
properties under them, its actions ./machines.sh in a terminal tab. ↑ ↓ step, ← → a button, Enter, s Status, Esc."""
import base64
import concurrent.futures
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # no __pycache__ beside the installed files
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fileops  # noqa: E402
import preview  # noqa: E402
from icons import NETWORKS, glyphs, network_mark  # noqa: E402
from loop import Loop  # noqa: E402
from screen import CONTENT, INSET, SPIN, SPINNER, Canvas, Style, after, icons_on, truncate, width  # noqa: E402
from settings import CLOSE_CELLS  # noqa: E402
from usage_view import Row  # noqa: E402
from vt import Focus, Key, Mouse  # noqa: E402
from widgets import Confirm, Menu, wrap  # noqa: E402

# two folders up from the plugin, where herdr-fold installs it: the package's record (install.sh's setup-folder) and
# the machine list; a sidebar installed on its own has neither, and its ⋯ offers no Machines…
BESIDE = os.path.normpath(os.path.join(HERE, "..", ".."))
POLL = 60.0                   # seconds between two looks while it is open, as the app's; none in the background
LOOK_SECONDS = 90             # core's look at most: each network's client 5 s, a route 2 s a machine
MOST = 256                    # the machines, and a network's names to add, one look gives at most
ROUTES = 8                    # a machine's routes, at most
AT_ONCE = 8                   # machines herdr is asked about at once (what runs there)
TOP = 1                       # the list's first row: the close button's row above it
LABEL = 10                    # cells of a property's label (Last seen)
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")                     # a machine's name, core/machines.py's
HOST = re.compile(r"(?!-)[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*")    # a host name or an IPv4 address
IP6 = re.compile(r"[0-9A-Fa-f:.]{2,45}")
USER = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}")
KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{1,64}")                           # a host key's fingerprint
WHY = re.compile(r"machines\.why_[a-z_]{1,40}")                           # a ladder's sentence, by its catalog key
CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
STATES = ("on", "off", "signed_out", "expired", "approval", "no_management")      # a network client's, core's
WITH_CLIENT = ("tailscale", "netbird", "zerotier")      # the networks whose client on this Mac has a state
OSES, PATHS = ("linux", "macos", "windows"), ("direct", "relayed")
LOOKS_AROUND = ("linux", "macos")                       # ./machines.sh through reads these (Windows comes later)
AGENTS = {"claude": "Claude", "codex": "Codex", "opencode": "OpenCode", "copilot": "Copilot"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

MACHINES = "Machines…"        # the sidebar's ⋯ line that opens it, over Settings…
LOADING, FAILED = "Loading machines…", "Couldn't read the machines"
NO_PACKAGE = "herdr-fold's package is not found here: the Machines view comes with herdr-fold's installer"
NONE = "No machines on the list yet: Ctrl+B, Shift+M adds one"
BY_ADDRESS = "none yet: add one by its address"          # ZeroTier and WireGuard name no machine to offer
OTHER, THIS_MAC, BETWEEN = "Other", "This Mac", " › "
CONNECTED, NOT_CONNECTED, AWAY, WAITING = "connected", "not connected", "unreachable", "waiting"
IN_USE, STANDBY = "in use", "standby"
LOOK_AROUND = "Look around from here…"
OPENED, COPIED = "Opened in a new tab", "Copied"
NO_TAB = "It opens in a herdr tab: open Machines in herdr"
BUTTONS = {"status": "Status", "again": "Set up again", "remove": "Remove", "more": "⋯", "check": "Check again",
           "copy": "Copy command"}
COMMANDS = {"status": "status", "again": "add", "remove": "remove", "through": "through"}     # machines.sh's
TABS = {"status": "Status", "again": "Set up again", "remove": "Remove", "through": "Look around from"}


# --- what it reads

def package(beside=None):
    """The package's folder its record names (beside the plugin, where herdr-fold installs it): one absolute path with
    its machines.sh, core/networks.py and catalog; None for none, or anything else."""
    try:
        with open(os.path.join(beside or BESIDE, "setup-folder"), encoding="utf-8") as f:
            folder = f.read(2048).strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not folder.startswith("/") or len(folder) > 1024 or CONTROLS.search(folder):
        return None
    needed = ("machines.sh", os.path.join("core", "networks.py"), os.path.join("src", "i18n.py"))
    return folder if all(os.path.isfile(os.path.join(folder, one)) for one in needed) else None


def catalog(folder):
    """The package's own t() (FOLDER/src/i18n.py, its lang/ beside it): core's keys in the words machines.sh says."""
    spec = importlib.util.spec_from_file_location("machines_i18n", os.path.join(folder, "src", "i18n.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded.t


def last_line(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return clean(lines[-1]) if lines else ""


def read_look(folder, listed, run=subprocess.run):
    """On a job's thread: core/networks.py's here over the machine list LISTED, its JSON (its arguments alone, no
    shell; PATH as a shell has it, for route and ifconfig); RuntimeError with what it said last."""
    path = os.pathsep.join([os.environ.get("PATH", ""), "/usr/bin", "/bin", "/usr/sbin", "/sbin", "/opt/homebrew/bin",
                            "/usr/local/bin"])
    try:
        done = run([sys.executable, os.path.join(folder, "core", "networks.py"), "here", listed],
                   capture_output=True, text=True, timeout=LOOK_SECONDS, env=dict(os.environ, PATH=path))
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RuntimeError(str(err)) from err
    if done.returncode != 0:
        raise RuntimeError(last_line(done.stderr or done.stdout) or f"exit {done.returncode}")
    try:
        return json.loads(done.stdout)
    except ValueError as err:
        raise RuntimeError("its answer is no JSON") from err


def look(folder, listed):
    return read_look(folder, listed)


def clean(value, most=300):
    """VALUE a network or a machine said, safe to show: its control characters dropped, cut at MOST."""
    return CONTROLS.sub("", str(value))[:most]


def name_ok(value):
    return isinstance(value, str) and bool(NAME.fullmatch(value))


def address_ok(value):
    return isinstance(value, str) and len(value) <= 253 and bool(HOST.fullmatch(value) or IP6.fullmatch(value))


def listed(value, most=MOST):
    return value[:most] if isinstance(value, list) else []


def kind_of(word):
    """A network's word (core/icons.py's NETWORKS, in the routes' order), through for one behind another; else None."""
    return word if isinstance(word, str) and (word in NETWORKS or word == "through") else None


def checked_why(said, depth=0):
    """A ladder's sentence (core's why()), checked: its catalog key, its arguments cleaned, what to do and what caused
    it (three deep at most); None for anything else."""
    if not isinstance(said, dict) or depth > 3 or not (isinstance(said.get("key"), str) and WHY.fullmatch(said["key"])):
        return None
    args = lambda values: [clean(one) for one in listed(values, 8)]          # noqa: E731
    action = said.get("action")
    todo = {"key": action["key"], "args": args(action.get("args")),
            "command": clean(action["command"]) if isinstance(action.get("command"), str) else None} \
        if isinstance(action, dict) and isinstance(action.get("key"), str) and WHY.fullmatch(action["key"]) else None
    return {"key": said["key"], "args": args(said.get("args")), "action": todo,
            "then": checked_why(said.get("then"), depth + 1)}


def checked_routes(routes):
    found = []
    for one in (one for one in listed(routes, ROUTES) if isinstance(one, dict) and address_ok(one.get("address"))):
        network = kind_of(one.get("network"))
        found.append({"network": network, "address": one["address"],
                      "user": one["user"] if isinstance(one.get("user"), str) and USER.fullmatch(one["user"]) else None,
                      "through": one["through"] if network == "through" and name_ok(one.get("through")) else None})
    return found


def number(value, most):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= most else None


def seen(said):
    """What core/networks.py's here answered (SAID), checked as everything a network or a machine says is: a name, an
    address, a user, a key, a network and a state of their shapes, a sentence by its catalog key with its arguments
    cleaned, each list capped; anything else dropped."""
    said = said if isinstance(said, dict) else {}
    machines, names = [], set()
    for one in (one for one in listed(said.get("machines")) if isinstance(one, dict)):
        if not name_ok(one.get("name")) or one["name"] in names:
            continue
        names.add(one["name"])
        network, figures = kind_of(one.get("network")), one.get("figures") if isinstance(one.get("figures"), dict) \
            else {}
        machines.append({"name": one["name"], "os": one["os"] if one.get("os") in OSES else "", "network": network,
                         "through": one["through"] if network == "through" and name_ok(one.get("through")) else None,
                         "key": one["key"] if isinstance(one.get("key"), str) and KEY.fullmatch(one["key"]) else None,
                         "why": checked_why(one.get("why")), "routes": checked_routes(one.get("routes")),
                         "figures": {"path": figures.get("path") if figures.get("path") in PATHS else None,
                                     "login_ms": number(figures.get("login_ms"), 10 ** 6),
                                     "seen": number(figures.get("seen"), 10 ** 11)}})
    told = said.get("networks") if isinstance(said.get("networks"), dict) else {}
    networks = {}
    for kind in (kind for kind in NETWORKS if isinstance(told.get(kind), dict)):
        one = told[kind]
        networks[kind] = {"installed": one.get("installed") is True if "installed" in one else None,
                          "state": one.get("state") if one.get("state") in STATES else None,
                          "why": checked_why(one.get("why")),
                          "offered": list(dict.fromkeys(name for name in listed(one.get("offered")) if name_ok(name)))}
    return {"machines": machines, "networks": networks}


def kept(text):
    """The machines herdr keeps (`herdr machine list --json`'s TEXT): {label: enabled}; None where herdr said none."""
    try:
        found = json.loads(text) if text else None
    except ValueError:
        return None
    if not isinstance(found, list):
        return None
    return {one["label"]: one.get("enabled") is not False for one in found[:MOST]
            if isinstance(one, dict) and name_ok(one.get("label"))}


def machine_runs(call, label):
    """On a job's thread: what runs on machine LABEL as herdr's own list tells (its workspaces, its agents' states);
    None where herdr cannot tell."""
    try:
        spaces = call("--machine", label, "workspace", "list").get("workspaces")
        agents = call("--machine", label, "agent", "list").get("agents")
    except RuntimeError:
        return None
    return {"spaces": len(listed(spaces)), "agents": [(one.get("agent"), one.get("agent_status"))
                                                      for one in listed(agents) if isinstance(one, dict)]}


# --- how it says it

def grouped(found):
    """FOUND's machines (seen()'s) as the app groups them: the networks in the routes' order, a machine under the route
    it is reached by, one behind another under its jump host (by name; jump hosts that go round nest none), those no
    network tells last; an empty network where it offers machines to add or names none (added by address)."""
    machines = {one["name"]: one for one in found["machines"]}

    def parent(one):
        up = one["through"]
        return up if one["network"] == "through" and up in machines and up != one["name"] else None

    def nests(one):
        passed, up = {one["name"]}, parent(one)
        while up:
            if up in passed:
                return False
            passed.add(up)
            up = parent(machines[up])
        return parent(one) is not None

    top, behind = [], {}
    for one in sorted(machines.values(), key=lambda one: one["name"].casefold()):
        (behind.setdefault(one["through"], []) if nests(one) else top).append(one)

    def under(one):
        """The network a machine on top stands under: its own, else the one of the jump host it goes through."""
        if one["network"] in NETWORKS:
            return one["network"]
        jump = machines.get(one["through"]) if one["network"] == "through" else None
        return jump["network"] if jump and jump["network"] in NETWORKS else None

    def flat(one, depth=0):
        return [(one, depth)] + [found for below in behind.get(one["name"], []) for found in flat(below, depth + 1)]

    groups = []
    for kind in NETWORKS:
        net, mine = found["networks"].get(kind) or {}, [one for one in top if under(one) == kind]
        offered = net.get("offered", []) if net.get("state") == "on" and not mine else []
        bare = not mine and net.get("installed") and (kind == "wireguard" or net.get("state") == "on") \
            and kind in ("zerotier", "wireguard")
        if mine or offered or bare:
            groups.append({"network": kind, "net": net, "offered": offered,
                           "machines": [found for one in mine for found in flat(one)]})
    rest = [one for one in top if under(one) is None]
    if rest:
        groups.append({"network": None, "net": {}, "offered": [], "machines": [found for one in rest
                                                                             for found in flat(one)]})
    return groups


def state_words(network, net, t):
    """How a network's head says NET's state while it is not on (the app's words and tones): off or not installed
    quietly, one to act on in yellow; None while on, and for a network with no client of its own."""
    if network not in WITH_CLIENT:
        return None
    if net.get("installed") is False:
        return t("machines.state_missing"), "muted"
    return {"off": (t("machines.state_off"), "muted"),
            "signed_out": (t("machines.state_signed_out"), "modified"),
            "expired": (t("machines.state_expired"), "modified"),
            "approval": (t("machines.state_approval"), "modified"),
            "no_management": (t("machines.state_no_management"), "modified")}.get(net.get("state"))


def to_add(count, t):
    return t("machines.to_add_one", count) if count == 1 else t("machines.to_add", count)


def why_lines(why, t):
    """WHY as machines.sh says it, a line each [(words, role)]: the sentence in yellow, then what caused it or what to
    do, each one's own after it, a command in the text's color after its words."""
    lines, follow = [[(t(why["key"], *why["args"]), "modified")]], why["then"] or why["action"]
    while follow:
        if follow.get("command"):
            lines.append([(t(follow["key"], *follow["args"], "\0").split("\0")[0], "muted"),
                          (follow["command"], "text")])
        else:
            lines.append([(t(follow["key"], *follow["args"]), "muted")])
        follow = follow.get("then") or follow.get("action")
    return lines


def first_command(why):
    """The first command WHY's sentences give to run (Start it: netbird up); None for none."""
    follow = why and (why["then"] or why["action"])
    while follow:
        if follow.get("command"):
            return follow["command"]
        follow = follow.get("then") or follow.get("action")
    return None


def right_words(one, runs):
    """What a machine's row says at its right: unreachable while away, waiting while an agent there waits on you, else
    the way to it as its network tells (direct, relayed) and its time."""
    if one["why"]:
        return AWAY, "muted"
    if any(status == "blocked" for _, status in (runs or {}).get("agents", ())):
        return WAITING, "modified"
    figures = one["figures"]
    return " ".join(filter(None, [figures["path"], None if figures["login_ms"] is None
                                  else f"{figures['login_ms']} ms"])), "muted"


def runs_parts(runs):
    """What runs on a machine in words [(words, role)]: its workspaces, then each agent working or waiting on you."""
    count = runs["spaces"]
    parts = [(f"{count} workspace{'' if count == 1 else 's'}", "text")]
    for agent, status in runs["agents"]:
        if agent in AGENTS and status in ("blocked", "working"):
            parts += [(", ", "text"), (f"{AGENTS[agent]} {'waiting' if status == 'blocked' else 'working'}",
                                       "modified" if status == "blocked" else "text")]
    return parts


def path_words(one, machines, t):
    """The way to a machine behind another: This Mac › Tailscale › lumen-api › build-01."""
    chain, up = [one["name"]], one
    while up["network"] == "through" and up["through"] in machines and up["through"] not in chain:
        up = machines[up["through"]]
        chain.insert(0, up["name"])
    return BETWEEN.join([THIS_MAC] + ([t(f"machines.network_{up['network']}")] if up["network"] in NETWORKS else [])
                        + chain)


def short_key(key):
    """A fingerprint cut to what tells it apart at a glance: SHA256:Qm9vZ0x1…a7Fk."""
    body = key[len("SHA256:"):]
    return f"SHA256:{body[:8]}…{body[-4:]}" if len(body) > 13 else key


def seen_words(when, now, local=time.localtime):
    """When a machine was seen last: today 8:02, else Nov 26 8:02 (this Mac's time)."""
    then, today = local(when), local(now)
    clock = f"{then.tm_hour}:{then.tm_min:02d}"
    if (then.tm_year, then.tm_yday) == (today.tm_year, today.tm_yday):
        return f"today {clock}"
    return f"{MONTHS[then.tm_mon - 1]} {then.tm_mday} {clock}"


def actions(one):
    """The buttons a machine's properties offer, [(id, words)]: away, looking again and its sentence's command; else
    Status, Set up again, Remove, and ⋯ (Look around from here) on a machine that can look around."""
    if one["why"]:
        return [("check", BUTTONS["check"])] + ([("copy", BUTTONS["copy"])] if first_command(one["why"]) else [])
    return [(id, BUTTONS[id]) for id in ("status", "again", "remove")] \
        + ([("more", BUTTONS["more"])] if one["os"] in LOOKS_AROUND else [])


def in_tab(herdr, workspace, folder, name, argv):
    """ARGV in a new tab of WORKSPACE in FOLDER, labeled NAME, shown; its pane named, so the dock leaves it a plain
    terminal, which stays open once the command ends (its words to read)."""
    made = herdr.call("tab", "create", "--workspace", workspace, "--cwd", folder, "--label",
                      preview.label(name)[:40], "--no-focus")
    pane = made["root_pane"]["pane_id"]
    herdr.call("pane", "rename", pane, "machines")
    herdr.call("pane", "run", pane, shlex.join(argv))
    herdr.call("tab", "focus", made["tab"]["tab_id"])


class MachinesView(Loop):
    def __init__(self, terminal, herdr, state_dir, clock=time.monotonic, beside=None, now=time.time):
        super().__init__(terminal, herdr, state_dir, clock)
        self.beside, self.now = beside or BESIDE, now
        self.folder = package(self.beside)
        self.t = catalog(self.folder) if self.folder else None
        self.icons = icons_on(state_dir)
        self.clipboard = fileops.system_clipboard(sys.platform)
        self.found = self.herdr_kept = None    # core's look, checked; the machines herdr keeps (None: not told)
        self.runs = {}                         # what runs on each machine herdr keeps, as its list tells
        self.failed = None                     # why the last look gave nothing
        self.read_at = clock()
        self.at = None                         # the stop the keys are on: ("machine", name) or ("add", network)
        self.button = 0                        # the chosen machine's button the keys are on
        self.menu = self.confirm = None        # ⋯'s menu (Menu, y, x); Remove's question (Confirm, name)
        self.said = None                       # what an action did, or why it did not: (words, failed)
        self.pointed = None
        self.top, self.height, self.count, self.follow = 0, 1, 0, True
        self.more_at = (TOP, INSET)            # under ⋯ as drawn last, and its right edge: where its menu opens
        self.ask()

    # --- reading

    def ask(self):
        """The networks looked at on a job's thread, with the machines herdr keeps; once more when asked while that
        runs."""
        self.read_at = self.clock()
        if not self.folder:
            return
        if "look" in self.running:
            self.again.add("look")
            return
        folder, path, herdr = self.folder, os.path.join(self.beside, "machines.txt"), self.herdr

        def work():
            return {"found": seen(look(folder, path)), "kept": kept(herdr.text("machine", "list", "--json"))}

        self.job("look", work, self.got)

    def got(self, answer):
        if answer:
            self.found, self.herdr_kept, self.failed, self.follow = answer["found"], answer["kept"], None, True
            self.ask_runs()
        if "look" in self.again:
            self.again.discard("look")
            self.ask()

    def ask_runs(self):
        """What runs on each machine herdr keeps that nothing keeps away, herdr asked about AT_ONCE at a time."""
        names = [one["name"] for one in self.found["machines"] if not one["why"]
                 and (self.herdr_kept or {}).get(one["name"])]
        if not names or "runs" in self.running:
            return
        call = self.herdr.call

        def work():
            with concurrent.futures.ThreadPoolExecutor(AT_ONCE) as pool:
                return dict(zip(names, pool.map(lambda name: machine_runs(call, name), names)))

        self.job("runs", work, lambda found: setattr(self, "runs", {k: v for k, v in found.items() if v}))

    def collect(self):
        """A look that failed says so in the list's place; an action's failure under its buttons."""
        answered = super().collect()
        if self.error:
            if self.found is None:
                self.failed = self.error
            else:
                self.said = (self.error, True)
            self.error = None
        return answered

    def stops(self):
        """The rows the keys step through, in order: each machine's, each network's machines to add."""
        found = []
        for group in grouped(self.found) if self.found else ():
            found += [("add", group["network"])] if group["offered"] else []
            found += [("machine", one["name"]) for one, _ in group["machines"]]
        return found

    def chosen(self):
        """The machine the keys are on (the first stop until one is chosen); None on a row to add, or none."""
        stops = self.stops()
        at = self.at if self.at in stops else (stops[0] if stops else None)
        return next((one for one in self.found["machines"] if at == ("machine", one["name"])), None) if at else None

    # --- what it does

    def handle(self, event):
        if isinstance(event, Focus):
            self.quit = self.quit or not event.gained          # a click outside: the pane clicked has the keys now
        elif isinstance(event, Key):
            self.key(event)
        elif isinstance(event, Mouse):
            target = self.canvas.hit(event.x, event.y) if self.canvas else None
            if event.kind == "move":
                self.pointed = target
                if self.menu:
                    self.menu[0].point(target)
            elif event.kind in ("wheel_up", "wheel_down"):
                self.scroll(3 if event.kind == "wheel_down" else -3)
            elif event.kind == "press" and event.button == 0:
                self.press(target)

    def key(self, key):
        if self.confirm:
            answer = self.confirm[0].handle(key)
            if answer is not None:
                self.answer(answer)
            return
        if self.menu:
            choice = self.menu[0].handle(key)
            if choice is not None:
                self.menu = None
                if choice == LOOK_AROUND:
                    self.launch("through", self.chosen())
            return
        name = key.char if key.name == "char" and not (key.ctrl or key.alt) else key.name
        stops, one = self.stops(), self.chosen()
        if name in ("esc", "q") or (key.name == "char" and key.ctrl and key.char == "c"):
            self.quit = True
        elif name in ("up", "down") and stops:
            now = stops.index(self.at) if self.at in stops else 0
            self.choose(stops[max(0, min(len(stops) - 1, now + (1 if name == "down" else -1)))])
        elif name in ("left", "right") and one:
            self.button = max(0, min(len(actions(one)) - 1, self.button + (1 if name == "right" else -1)))
        elif name == "enter" and one:
            self.act(actions(one)[min(self.button, len(actions(one)) - 1)][0], one)
        elif name == "enter" and stops and (self.at if self.at in stops else stops[0])[0] == "add":
            self.add((self.at if self.at in stops else stops[0])[1])
        elif name == "s" and one:
            self.launch("status", one)
        elif name in ("pageup", "pagedown"):
            self.scroll(self.height if name == "pagedown" else -self.height)

    def choose(self, stop):
        self.at, self.button, self.said, self.follow = stop, 0, None, True

    def scroll(self, rows):
        self.top = max(0, min(self.top + rows, self.count - self.height))

    def press(self, target):
        if self.menu:
            choice = self.menu[0].choices[int(target[5:])] if str(target).startswith("menu:") else None
            self.menu = None
            if choice == LOOK_AROUND:
                self.launch("through", self.chosen())
            return
        if self.confirm:
            if target in ("confirm:yes", "confirm:no"):
                self.answer(target == "confirm:yes")
            return
        kind, value = target if isinstance(target, tuple) else (target, None)
        if kind == "close":
            self.quit = True
        elif kind == "machine":
            self.choose(("machine", value))
        elif kind == "add":
            self.choose(("add", value))
            self.add(value)
        elif kind == "button" and self.chosen():
            self.button = next((n for n, (id, _) in enumerate(actions(self.chosen())) if id == value), 0)
            self.act(value, self.chosen())

    def act(self, what, one):
        """WHAT done to machine ONE from its properties: ⋯'s menu, a look again, its command copied, Remove asked
        first, the others ./machines.sh in a terminal tab."""
        if what == "more":                              # under ⋯, its right edge with the button's
            menu, (y, right) = Menu([LOOK_AROUND]), self.more_at
            self.menu = (menu, y, right - menu.width())
        elif what == "check":
            self.said = None
            self.ask()
        elif what == "copy":
            words = first_command(one["why"])
            if words and not self.clipboard(words):        # no clipboard program: the terminal's own
                self.term.write("\x1b]52;c;" + base64.b64encode(words.encode("utf-8")).decode("ascii") + "\x07")
            self.said = (COPIED, False)
        elif what == "remove":
            self.confirm = (Confirm(f"Take {one['name']} off the list, and herdr-fold off it?", BUTTONS["remove"]),
                            one["name"])
        else:
            self.launch(what, one)

    def answer(self, yes):
        _, name = self.confirm
        self.confirm = None
        one = next((one for one in (self.found or {}).get("machines", ()) if one["name"] == name), None)
        if yes and one:
            self.launch("remove", one)

    def launch(self, what, one):
        """./machines.sh WHAT for machine ONE in a terminal tab on this Mac, its questions and fingerprints there."""
        if one and name_ok(one["name"]):
            self.in_tab(f"{TABS[what]} {one['name']}",
                        ["/bin/bash", os.path.join(self.folder, "machines.sh"), COMMANDS[what], one["name"]])

    def add(self, network):
        """A network's machines to add, asked about by ./machines.sh in a terminal tab, as the app's row does."""
        if network in ("tailscale", "netbird"):
            self.in_tab(self.t(f"machines.network_{network}"),
                        ["/bin/bash", os.path.join(self.folder, "machines.sh"), network])

    def in_tab(self, name, argv):
        workspace = os.environ.get("HERDR_WORKSPACE_ID")
        if not workspace:
            self.said = (NO_TAB, True)
            return
        herdr, folder = self.herdr, self.folder
        self.said = None
        self.job(f"tab-{argv[2]}", lambda: in_tab(herdr, workspace, folder, name, argv),
                 lambda _: setattr(self, "said", (OPENED, False)))

    # --- the loop's

    def tick(self):
        """The networks looked at again when due; the spinner's next frame while the first look runs."""
        if self.folder and self.clock() >= self.read_at + POLL and not self.confirm:
            self.ask()
        return bool(self.folder) and self.found is None and not self.failed

    def deadlines(self):
        spin = [self.clock() + SPIN] if self.folder and self.found is None and not self.failed else []
        return spin + [self.read_at + POLL]

    # --- drawing

    def draw(self):
        cells, rows = self.term.size()
        canvas = Canvas(cells, rows)
        corner, lit = cells - CLOSE_CELLS, self.pointed == "close"
        canvas.put(0, corner, f" {glyphs(self.icons)['close']} ", Style(fg="text" if lit else "subtext",
                                                                        bg="hover" if lit else None))
        canvas.region(0, corner, cells, "close")
        asked = self.confirm_canvas(cells, rows) if self.confirm else None
        lines = self.lines(cells)
        self.count, self.height = len(lines), max(1, rows - TOP - (asked.height + 1 if asked else 0))
        at = next((n for n, line in enumerate(lines) if getattr(line, "chosen", False)), None)
        if self.follow and at is not None:               # the chosen row in view, its properties as far as they fit
            self.top, self.follow = min(at, max(0, self.count - self.height)), False
        self.scroll(0)
        for n, line in enumerate(lines[self.top:self.top + self.height]):
            if getattr(line, "band", None):
                canvas.band(TOP + n, line.band)
            line.draw(canvas, TOP + n)
            if getattr(line, "more", None) is not None:
                self.more_at = (TOP + n + 1, line.more)
        if asked:
            y = rows - asked.height
            canvas.put(y - 1, INSET, "─" * (cells - 2 * INSET), Style(fg="muted"))
            canvas.paste(asked, y, 0)
        if self.menu:
            menu, y, x = self.menu
            y, x, wide = menu.at(y, x, cells, TOP, rows, INSET)
            menu.draw(canvas, y, x, wide)
        self.canvas = canvas
        self.term.write(self.renderer.frame(canvas))
        self.term.flush()

    def confirm_canvas(self, cells, rows):
        """Remove's question with its two buttons, as the sidebar asks before something cannot be undone."""
        part = Canvas(cells, rows)
        used = self.confirm[0].draw(part, 0, 0, cells)
        made = Canvas(cells, used)
        made.paste(part)
        made.regions = [region for region in part.regions if region[0] < used]
        return made

    @staticmethod
    def words_row(cells, words, role, x=INSET):
        row = Row()
        row.put(x, truncate(words, cells - x - INSET), Style(fg=role))
        return row

    def lines(self, cells):
        """The networks' heads, each one's machines and what it offers to add, the chosen machine's properties under
        them; before a look, what stands in its place."""
        if not self.folder:
            return [self.words_row(cells, NO_PACKAGE, "muted")]
        if self.found is None:
            if self.failed:
                return [self.words_row(cells, f"{FAILED}: {self.failed}", "deleted")]
            return [self.words_row(cells, f"{SPINNER[int(self.clock() / SPIN) % len(SPINNER)]} {LOADING}", "muted")]
        groups = grouped(self.found)
        if not groups:
            return [self.words_row(cells, NONE, "muted")]
        stops, end, one = self.stops(), cells - CONTENT, self.chosen()
        at = self.at if self.at in stops else stops[0] if stops else None
        x = INSET + 1 + len(after(self.icons))          # under a head's name: its machines' dots
        rows = [found for group in groups for found in group["machines"]]
        rights = {found["name"]: right_words(found, self.runs.get(found["name"])) for found, _ in rows}
        system = max([width(found["os"]) for found, _ in rows] + [0])
        widest = max([width(words) for words, _ in rights.values()] + [0])
        natural = max([x + 4 * depth + 2 + width(found["name"]) for found, depth in rows] + [0]) + 2
        column = max(x + 4, min(natural, end - widest - 2 - system))     # the systems' column, the same for all
        lines = []
        for group in groups:
            lines.append(self.head(group, x, end))
            if group["offered"]:
                lines.append(self.add_row(group, x, cells, at))
            elif not group["machines"]:
                lines.append(self.words_row(cells, BY_ADDRESS, "muted", x))
            for found, depth in group["machines"]:
                lines.append(self.machine_row(found, depth, x, column, end, cells, rights[found["name"]],
                                              at == ("machine", found["name"])))
        if one:
            lines += [Row()] + self.properties(one, x, end, cells)
        elif self.said:
            lines += [Row(), self.words_row(cells, self.said[0], "deleted" if self.said[1] else "muted")]
        return lines

    def head(self, group, x, end):
        """A network's head: its mark in its color, its name bold (dimmed while off), its state, its count."""
        row, kind, net = Row(), group["network"], group["net"]
        mark = network_mark(kind, self.icons) if kind else None
        if mark:
            row.put(INSET, mark[0], Style(fg=mark[1]))
        said = state_words(kind, net, self.t) if kind else None
        quiet = net.get("installed") is False or net.get("state") == "off"
        at = row.put(x, self.t(f"machines.network_{kind}") if kind else OTHER, Style(fg="muted" if quiet else "text",
                                                                                     bold=True))
        if said:
            row.put(at + 2, said[0], Style(fg=said[1]))
        row.right(end, str(len(group["machines"])), Style(fg="muted"))
        return row

    def add_row(self, group, x, cells, at):
        """A network's machines to add, a stop: Enter or a click asks about each in a terminal tab."""
        row, stop = Row(), ("add", group["network"])
        row.chosen = at == stop
        row.band = bg = "selection" if row.chosen else "hover" if self.pointed == stop else None
        row.put(x, truncate("+ " + to_add(len(group["offered"]), self.t), cells - x - CONTENT),
                Style(fg="muted_row" if bg else "muted", bg=bg))
        row.regions.append((0, cells, stop))
        return row

    def machine_row(self, one, depth, x, column, end, cells, right, chosen):
        """A machine's row: └ behind another, its dot (● green, ○ away), its name, its system in one column for all,
        at its right its state or the way to it; on its highlight while chosen, a cell in from each side."""
        row = Row()
        row.chosen = chosen
        row.band = bg = "selection" if chosen else "hover" if self.pointed == ("machine", one["name"]) else None
        faint, away, dot = "muted_row" if bg else "muted", bool(one["why"]), x + 4 * depth
        if depth:
            row.put(dot - 2, "└", Style(fg=faint, bg=bg))
        row.put(dot, "○" if away else "●", Style(fg=faint if away else "added", bg=bg))
        row.put(dot + 2, truncate(one["name"], max(1, column - 2 - dot - 2)), Style(fg=faint if away else "text",
                                                                                     bg=bg))
        row.put(column, one["os"], Style(fg=faint, bg=bg))
        words, role = right
        row.right(end, words, Style(fg=faint if role == "muted" else role, bg=bg))
        row.regions.append((0, cells, ("machine", one["name"])))
        return row

    def properties(self, one, x, end, cells):
        """ONE's properties under the list, label left and value right in aligned columns: why it is away, its
        address or routes, user, network, the way behind another, key, when seen, what runs; its buttons."""
        machines, value, lines = {found["name"]: found for found in self.found["machines"]}, x + LABEL, []
        head = Row()
        head.put(INSET, truncate(one["name"], end - INSET - 16), Style(fg="text", bold=True))
        known = self.herdr_kept is not None
        state = (AWAY, "muted") if one["why"] else (CONNECTED, "added") if (self.herdr_kept or {}).get(one["name"]) \
            else (NOT_CONNECTED, "muted") if known else None
        if state:
            head.right(end, state[0], Style(fg=state[1]))
        lines.append(head)

        def line(label, parts):
            row, at = Row(), value
            row.put(x, label, Style(fg="muted"))
            for words, role in parts:
                at = row.put(at, truncate(words, max(0, end - at)), Style(fg=role))
            lines.append(row)

        if one["why"]:
            for parts in why_lines(one["why"], self.t):
                if len(parts) == 1:
                    words, role = parts[0]
                    for start, stop in wrap(words, max(1, end - x)) or [(0, 0)]:
                        lines.append(self.words_row(cells, words[start:stop].rstrip(), role, x))
                else:
                    row, at = Row(), x
                    for words, role in parts:
                        at = row.put(at, truncate(words, max(0, end - at)), Style(fg=role))
                    lines.append(row)
            lines.append(Row())
        routes, first = one["routes"], (one["routes"] or [{}])[0]
        if len(routes) > 1:
            for n, route in enumerate(routes):
                lines.append(self.route_row(one, route, n, x, value, end))
        elif first.get("address"):
            line("Address", [(first["address"], "text")])
        if first.get("user"):
            line("User", [(first["user"], "text")])
        if len(routes) <= 1 and (one["network"] in NETWORKS or one["through"]):
            line("Network", [(self.t("machines.network_through", one["through"]) if one["network"] == "through"
                              else self.t(f"machines.network_{one['network']}"), "text")])
        if one["network"] == "through" and one["through"]:
            line("Path", [(path_words(one, machines, self.t), "text")])
        if one["key"]:
            line("Key", [(short_key(one["key"]), "text")])
        seen_at = one["figures"]["seen"]
        if seen_at and (one["why"] or {}).get("key") not in ("machines.why_offline", "machines.why_offline_unseen"):
            line("Last seen", [(seen_words(seen_at, self.now()), "text")])
        if self.runs.get(one["name"]) and not one["why"]:
            line("Runs", runs_parts(self.runs[one["name"]]))
        lines.append(self.buttons(one, x, cells))
        if self.said:
            lines.append(self.words_row(cells, self.said[0], "deleted" if self.said[1] else "muted", x))
        return lines

    def route_row(self, one, route, n, x, value, end):
        """One of a machine's routes: its network's mark, its address; the one in use first, the others standby."""
        row = Row()
        if not n:
            row.put(x, "Routes", Style(fg="muted"))
        mark = network_mark(route["network"], self.icons)
        if mark:
            row.put(value, mark[0], Style(fg=mark[1]))
        at = row.put(value + 1 + len(after(self.icons)), route["address"], Style(fg="text"))
        if route["through"]:
            row.put(at + 2, self.t("machines.network_through", route["through"]), Style(fg="muted"))
        ms = one["figures"]["login_ms"]
        if n:
            row.right(end, STANDBY, Style(fg="muted"))
        elif ms is not None:
            row.right(row.right(end, f"{ms} ms", Style(fg="muted")) - 2, IN_USE, Style(fg="text"))
        else:
            row.right(end, IN_USE, Style(fg="text"))
        return row

    def buttons(self, one, x, cells):
        """Its buttons: the first the one Enter presses (the accent), the one the keys or the mouse are on lit."""
        row, at = Row(), x
        for n, (id, words) in enumerate(actions(one)):
            lit = n and (n == self.button or self.pointed == ("button", id))
            style = Style(fg="button_text", bg="button", bold=True) if not n else Style(
                fg="text" if lit else "subtext", bg="hover" if lit else "input")
            if id == "more":
                row.more = at + width(words) + 2
            row.put(at, f" {words} ", style)
            row.regions.append((at, at + width(words) + 2, ("button", id)))
            at += width(words) + 3
        return row


def main():
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "herdr", "plugins", "herdr-fold.sidebar")
    if os.name == "nt":
        from keys_windows import WindowsTerminal as Terminal
    else:
        from keys_unix import UnixTerminal as Terminal
    MachinesView(Terminal(), preview.Herdr(), state).run()


if __name__ == "__main__":
    main()
