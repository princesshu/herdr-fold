"""The Agent view's work in the dock (layers.py draws it): the folder's agent, its setup, the agents here, their limits
and costs read on a job's thread through core's readers (agent_setup.py, agent_state.py, usage.py, report.py) while
shown; a file opened, a server checked, a sign-in or a command of a connector's run, the Usage view and the graph."""
import base64
import glob
import os
import re
import subprocess
import sys
import time

import agent_setup
import agent_state
import connectors
import costs
import graph
import jsonl
import media
import panes
import preview
import statefile
import tokens
import usage
from family import Family
from fileops import system_clipboard
from layers import NEEDS, SERVER, Layers, tree_rows
from screen import SPIN, SPINNER
from usage_view import PERIOD_ENV, figures

POLL = 30.0                   # seconds between two reads while shown, as the Herdr app's panel reads
AWAY = 300.0                  # the same behind another view: the row's dot alone needs it
COSTS = 60.0                  # seconds between two reads of what the agents cost, while shown
PLUGIN = "herdr-fold.sidebar"
SIGNING = 5.0                 # seconds between two looks at the agents while one signs in in its tab
SIGNING_FOR = 600.0           # seconds a sign-in is waited for at most
WATCH = 2.0                   # seconds between two looks at the sign-ins' tabs: one gone is asked about again
READ_ROWS = "200"             # rows of a sign-in's pane its address is looked for in
NOT_PRINTED = "Its address is not printed yet"
TYPED = "Typed into Claude: Enter sends it"
GRAPHING, NO_GRAPH = "Reading the graph…", "No graph to show here"
SESSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")     # a session's id, as herdr tells it: never a path


def tab_agent(call, pane):
    """The Claude or Codex in PANE's tab, as herdr's lists have it: (kind, its folder, its session's id), or None."""
    listed = call("pane", "list").get("panes") or []
    tab = next((p.get("tab_id") for p in listed if p.get("pane_id") == pane), None)
    agents = call("agent", "list").get("agents") or []
    found = next((a for a in agents if tab and a.get("tab_id") == tab and a.get("agent") in panes.AGENTS), None)
    return (found["agent"], found.get("cwd"), (found.get("agent_session") or {}).get("value")) if found else None


def tab_claude(call, pane):
    """The pane of the Claude in PANE's tab (where its /mcp command is typed), or None."""
    listed = call("pane", "list").get("panes") or []
    tab = next((p.get("tab_id") for p in listed if p.get("pane_id") == pane), None)
    agents = call("agent", "list").get("agents") or []
    return next((a.get("pane_id") for a in agents if tab and a.get("tab_id") == tab and a.get("agent") == "claude"),
                None)


def last_line(code, out, err):
    """What a command that failed said last, for one line."""
    lines = [line for line in ((err or "").strip() or (out or "").strip()).splitlines() if line.strip()]
    return agent_setup.clean(lines[-1]) if lines else f"exit {code}"


def session_file(folder, session, home):
    """Claude's file of the conversation SESSION in FOLDER, else the folder's newest one; None where it has none."""
    place = jsonl.claude_project_dir(folder, home)
    named = os.path.join(place, f"{session}.jsonl") if isinstance(session, str) and SESSION.fullmatch(session) \
        else None
    if named and os.path.isfile(named):
        return named
    newest = jsonl.newest_first(glob.glob(os.path.join(place, "*.jsonl")))
    return newest[0] if newest else None


def limits(agents, agent, home):
    """Usage as core words it (usage.py's section()) for AGENT shown, AGENTS telling the names and plans, its blocks as
    the user left them in either client; a reset said in this machine's time, its hours as the status line's."""
    now = int(time.time())
    found = usage.section(usage.limits(home, now), agents, agent, now, usage.kept_open(statefile.folder()))
    twelve = usage.twelve_hours(home)
    for row in found["rows"]:
        if row["resets"]:
            row["resets"]["said"] = usage.reset_said(row["resets"], twelve)
    return found


class Agent(Family):
    PANELS = ("agent",)

    def __init__(self, host):
        super().__init__(host)
        self.view = Layers(host.settings["icons"], host.settings["agent_folded"])
        self.views = {"agent": self.view}
        self.read_at = None                   # when the setup was last asked for
        self.states = {}                      # each server's state as last read, before any check
        self.checked = {}                     # {server: (its state when checked, Claude's answer)}
        self.spun = 0.0                       # when a checked server's mark last turned
        self.signing = None                   # (agent, until when): signing in in its tab, asked about till then
        self.connecting = {}                  # {server: {"pane", "tab", "until"}}: its agent's sign-in in a tab
        self.looked = 0.0                     # when those tabs were last looked at
        self.wants = None                     # a server Codex added a moment ago: signed in to where it must be
        self.costs_at = None                  # when the agents' costs were last asked for
        self.clipboard = system_clipboard(sys.platform)

    def tick(self, now):
        """The setup asked for when due; a checked server's mark turned. Whether anything shown changed."""
        if now >= self.next_read():
            self.read_at = now
            self.ask(fresh=bool(self.signing))
        if self.connecting and now >= self.looked + WATCH and "signins" not in self.host.running:
            self.looked = now
            self.look()
        if now >= self.next_costs():
            self.ask_costs()
        if self.view.checking and now >= self.spun + SPIN:
            self.spun = now
            self.view.frame = SPINNER[int(now / SPIN) % len(SPINNER)]
            return True
        return False

    def next_read(self):
        """When the setup is read next: at once, then every POLL or AWAY seconds; never while More leaves Agent off the
        row (no dot to keep there)."""
        if "agent" not in self.host.row():
            return float("inf")
        if self.read_at is None:
            return 0.0
        if self.signing and self.host.showing("agent"):
            return self.read_at + SIGNING
        return self.read_at + (POLL if self.host.showing("agent") else AWAY)

    def next_costs(self):
        """When the agents' costs are read next: once Usage is on screen (the view shown, its setup read), then every
        COSTS seconds; never behind another view (the Usage view reads its own)."""
        if not self.host.showing("agent") or not (self.view.answer or {}).get("usage"):
            return float("inf")
        return 0.0 if self.costs_at is None else self.costs_at + COSTS

    def deadlines(self):
        costs = self.next_costs()
        return [self.next_read()] + ([self.spun + SPIN] if self.view.checking else []) + (
            [self.looked + WATCH] if self.connecting else []) + ([costs] if costs != float("inf") else [])

    def came(self, panel):
        self.read_at = self.host.clock()
        self.ask()

    def reload(self, folders=None):
        if self.host.showing("agent"):
            self.read_at = self.host.clock()
            self.ask()

    def ask(self, fresh=False):
        """The setup read on a job's thread; once more when asked while that runs, so the last change lands last.
        FRESH: the agents asked again, not the minute's answer (one is signing in)."""
        if "agent" in self.host.running:
            self.host.again.add("agent")
            return
        pane, checked = os.environ.get("HERDR_PANE_ID"), dict(self.checked)
        chosen = self.host.settings["agent_chosen"].get(self.host.root)
        self.host.job("agent", lambda: self.read(pane, checked, chosen, fresh), self.got)

    def read(self, pane, checked, chosen=None, fresh=False):
        """On the job's thread: the agents on this machine, each with where it stands; the folder's agent (CHOSEN in
        the head's list, else the tab's by herdr's lists, else the one started last) and its setup as core's layers()
        words it, a server Claude checked since as Claude said; or what stands in its place (standing())."""
        root, home, found = self.host.root, os.path.expanduser("~"), None
        agents = [{**one, "empty": agent_state.standing(one)} for one in agent_state.machine_agents(home, fresh=fresh)]
        told = {one["key"]: one for one in agents}
        if pane:
            try:
                found = tab_agent(self.host.herdr.call, pane)
            except RuntimeError:
                pass
        agent, cwd, session = found or (panes.last_agent(self.host.state_dir), None, None)
        if chosen in told and chosen != agent:
            agent, cwd, session = chosen, None, None
        claude = False
        if pane:
            try:
                claude = bool(tab_claude(self.host.herdr.call, pane))
            except RuntimeError:
                pass
        said = {"agent": agent, "folder": root, "agents": agents, "states": {}, "claude": claude,
                "head": {"name": agent_setup.KNOWN[agent]["name"], "where": f"in {os.path.basename(root)}"}}
        if told[agent]["empty"]:
            return {**said, "empty": told[agent]["empty"]}
        if agent not in agent_setup.READ:     # no setup of it is read: its head alone
            return said
        if agent == "claude":
            setup = agent_setup.claude_setup(root, home, session_file(cwd or root, session, home))
        else:
            setup = agent_setup.codex_setup(root, home)
        if setup is None:                     # Codex gone since the agents were told
            return {**said, "empty": agent_state.standing({**told[agent], "installed": False})}
        states = {one["name"]: one["state"] for one in setup["servers"]}
        for one in setup["servers"]:
            base, answered = checked.get(one["name"], (None, None))
            if answered and one["state"] == base:
                one.update(state=answered["state"], error=answered["error"])
        return {**said, "states": states, "usage": limits(agents, agent, home),
                **agent_setup.layers(setup, agent, root, home)}

    def got(self, answer):
        if answer is not None:
            if self.signing:                  # in, or waited long enough: the usual pace again
                key, until = self.signing
                now = next((one for one in answer["agents"] if one["key"] == key), None)
                if not now or now["signed_in"] is not False or self.host.clock() >= until:
                    self.signing = None
            self.states = answer.pop("states", {})
            self.checked = {name: kept for name, kept in self.checked.items() if self.states.get(name) == kept[0]}
            self.view.set(answer)
            wanted, self.wants = self.wants, None
            if wanted and self.states.get(wanted) == agent_setup.SIGN_IN:       # Codex's own list says it must
                self.do_connect_server(wanted)
        if "agent" in self.host.again:
            self.host.again.discard("agent")
            self.ask()

    def ask_costs(self):
        """What the agents cost read on a job's thread (figures()), for the view's period; once more when asked while
        that runs (the period stepped), and at once while conversations are left to read (usage_view's figures())."""
        self.costs_at = self.host.clock()
        if "costs" in self.host.running:
            self.host.again.add("costs")
            return
        colors = self.host.renderer.theme.colors          # button_text is the pane's own ground (the theme setter's)
        period, agents = self.view.period, (self.view.answer or {}).get("agents")
        theme, home = (colors.get("button_text"), colors.get("text")), os.path.expanduser("~")
        self.host.job("costs", lambda: figures(period, agents, theme, home), lambda found: self.cost(period, found))

    def cost(self, period, found):
        again = "costs" in self.host.again
        self.host.again.discard("costs")
        if found and period == self.view.period:
            self.view.costs, self.view.reading = found["report"], bool(found["left"])
        if again or found and found["left"]:
            self.ask_costs()

    def do_usage_period(self, period):
        """Usage's period stepped on its head: its costs read for it."""
        self.ask_costs()

    def do_usage_open(self, agent, on):
        """AGENT's block in Usage opened (ON) or folded: kept by core on a job's thread, the Herdr app's too."""
        self.host.job("usage-open", lambda: usage.keep_open(statefile.folder(), agent, on))

    def do_open_usage(self, period):
        """The Usage view (usage_view.py, the plugin's pane `usage`) opened over the tab on PERIOD; not on Windows,
        where the plugin has no pane of its own (Settings neither)."""
        if os.name == "nt":
            return
        self.host.job("usage-view", lambda: self.host.herdr.call(
            "plugin", "pane", "open", "--plugin", PLUGIN, "--entrypoint", "usage", "--env", f"{PERIOD_ENV}={period}",
            "--focus"))

    def do_show_graph(self):
        """The shown agent's graph (graph.py's) read on a job's thread with the tab's conversation, else the folder's
        newest, and what that cost (costs.py's, after one look of the token index); then its tree in the preview tab."""
        if "graph" in self.host.running:
            return
        agent, root, home = self.view.agent(), self.host.root, os.path.expanduser("~")
        pane, agents, call = os.environ.get("HERDR_PANE_ID"), (self.view.answer or {}).get("agents"), \
            self.host.herdr.call
        self.host.note = GRAPHING

        def work():
            found = None
            if pane:
                try:
                    found = tab_agent(call, pane)
                except RuntimeError:
                    pass
            _, cwd, session = found if found and found[0] == agent else (None, None, None)
            talk = session_file(cwd or root, session, home) if agent == "claude" else graph.rollout(root, home)
            cost = None
            if talk:
                state = statefile.folder()
                tokens.index(state, home)
                cost = costs.costs(state, agent, talk, agents)
            return graph.graph(agent, root, home, talk, cost)

        def then(made):
            twelve = usage.twelve_hours(home)
            self.host.note = None if made else NO_GRAPH
            if made:
                self.host.open_preview(preview.graph_spec(made, lambda run: tree_rows(made, run, twelve)), root)

        self.host.job("graph", work, then)

    def tone(self):
        """The worst problem's tone, for the row's and the rail's dot: "bad", "warn" or None."""
        return self.view.tone()

    def left(self):
        return {"agent": self.view.kept()}

    def take(self, left):
        if isinstance(left.get("agent"), dict):
            self.view.take(left["agent"])

    # --- what the view asks for

    def do_open_setup(self, path):
        """PATH (a rule, a settings file, .mcp.json) in the preview tab, named as the properties name it."""
        root = self.host.root
        spec = preview.file_spec(root, path, None)
        self.host.open_preview({**spec, "title": agent_setup.shown(path, root, os.path.expanduser("~"))}, root)

    def do_retry_server(self, name, after=None):
        """Claude's own look at the server NAME (`claude mcp get`), its mark spinning meanwhile; its answer shown
        until a newer session says otherwise, and handed to AFTER."""
        if name in self.view.checking:
            return
        self.view.checking.add(name)
        root = self.host.root

        def work():
            try:
                return agent_state.check(root, name)
            except ValueError:                # not a server's name: nothing asked
                return None

        def then(said):
            self.view.checking.discard(name)
            if said:
                self.checked[name] = (self.states.get(name), said)
            self.ask()
            if said and after:
                after(said)

        self.host.job(f"check-{name}", work, then)

    # --- a connector's own commands (connectors.py builds each; nothing of the agent's is written here)

    def do_say(self, words):
        self.host.note = words

    def do_refresh_agent(self):
        self.read_at = self.host.clock()
        self.ask()

    def settle(self, name):
        """Server NAME's state asked for anew after its agent's command ended: Claude checks it (a session's lines
        tell nothing new), Codex's own list is read again."""
        if self.view.agent() == "claude":
            self.do_retry_server(name)
        else:
            self.ask()

    def do_connect_server(self, name):
        """The agent's own login for its server NAME (it needs a terminal and opens the browser) in a herdr tab of its
        own, one per server; its row signs in until that tab is gone."""
        if name in self.connecting:
            return
        try:
            argv = connectors.login(self.view.agent(), name)
        except ValueError:                    # not a server's name, or an agent with no such command
            return
        now = self.host.clock()
        self.connecting[name] = {"pane": None, "tab": None, "until": now + SIGNING_FOR}
        self.view.signing.add(name)
        self.looked = now
        self.host.open_tab(f"Sign in to {self.view.label_of(name)}", argv, lambda made: self.began(name, made))

    def began(self, name, made):
        """NAME's sign-in has its tab (MADE: its pane and tab; None: none could open); cancelled meanwhile: closed."""
        one = self.connecting.get(name)
        if made and one:
            one["pane"], one["tab"] = made
        elif made:
            self.host.job(f"close-{name}", lambda: self.host.herdr.call("tab", "close", made[1]))
        else:
            self.ended(name)

    def look(self):
        """On a job's thread: the sign-ins whose pane is gone (signed in, or cancelled there: its exit tells neither),
        and those left waiting past their time, their tabs closed; each asked about again."""
        watched, now, call = {name: dict(one) for name, one in self.connecting.items()}, self.host.clock(), \
            self.host.herdr.call

        def work():
            panes = {pane.get("pane_id") for pane in call("pane", "list").get("panes") or []}
            gone = [name for name, one in watched.items() if one["pane"] and one["pane"] not in panes]
            late = [name for name, one in watched.items() if name not in gone and now >= one["until"]]
            for name in late:
                if watched[name]["tab"]:
                    call("tab", "close", watched[name]["tab"])
            return gone + late

        self.host.job("signins", work, lambda names: [self.ended(name) for name in names or ()])

    def ended(self, name):
        if self.connecting.pop(name, None) is not None:
            self.view.signing.discard(name)
            self.settle(name)

    def do_cancel_sign_in(self, name):
        """NAME's sign-in ended: its tab closed, its server asked about again."""
        tab = (self.connecting.get(name) or {}).get("tab")
        if tab:
            self.host.job(f"close-{name}", lambda: self.host.herdr.call("tab", "close", tab))
        self.ended(name)

    def do_reopen_sign_in(self, name):
        """The address NAME's sign-in printed in its pane (core finds and checks it), in the browser; never kept."""
        pane, herdr = (self.connecting.get(name) or {}).get("pane"), self.host.herdr
        if not pane:
            self.host.note = NOT_PRINTED
            return

        def work():
            rows = herdr.text("pane", "read", pane, "--source", "recent-unwrapped", "--lines", READ_ROWS)
            return connectors.login_url(rows + "\n")

        def then(url):
            self.host.note = NOT_PRINTED if not url else "Opened in the browser" if media.open_in_browser(url) \
                else "No browser to open it in"

        self.host.job(f"reopen-{name}", work, then)

    def do_turn_server(self, name, on):
        """Claude's own `/mcp enable|disable NAME` typed into the tab's Claude, not sent (the TUI's way), and the keys
        there; with no Claude in the tab, what it waits for."""
        try:
            words = connectors.toggle(name, on)
        except ValueError:
            return
        me, herdr = os.environ.get("HERDR_PANE_ID"), self.host.herdr

        def work():
            target = tab_claude(herdr.call, me) if me else None
            if not target:
                return NEEDS["turn-on" if on else "turn-off"]
            herdr.call("pane", "send-text", target, words)
            herdr.call("agent", "focus", target)
            return TYPED

        def then(said):
            self.host.note = said

        self.host.job(f"turn-{name}", work, then)

    def command(self, kind, argv, then):
        """ARGV (an agent's own command, one argv) run in the folder on a job's thread; THEN gets None where it worked,
        else what it said last."""
        root = self.host.root

        def work():
            try:
                code, out, err = agent_setup.run(argv, root)
            except subprocess.TimeoutExpired:
                return "No answer"
            except OSError as error:
                return agent_setup.clean(error.strerror or str(error)) or "It could not start"
            return last_line(code, out, err) if code else None

        self.host.job(kind, work, then)

    def do_sign_out_server(self, name):
        """The agent's own logout for its server NAME, its mark spinning meanwhile; then its state asked for anew."""
        if name in self.view.checking:
            return
        try:
            argv = connectors.logout(self.view.agent(), name)
        except ValueError:
            return
        self.view.checking.add(name)

        def then(failed):
            self.view.checking.discard(name)
            if failed:
                self.host.error = f"Couldn't sign out of {self.view.label_of(name)}: {failed}"
            else:
                self.settle(name)

        self.command(f"logout-{name}", argv, then)

    def do_add_connector(self, name, url, scope):
        """The form's NAME and URL checked by core (a refused field said in the form), then the agent's own `mcp add`
        run in the folder (its failure said in the form, in its words); added: its row chosen once read, and signed
        in to where its agent says it must be."""
        agent = self.view.agent()
        try:
            made = connectors.form(agent, name, url, scope)
        except ValueError:                    # an agent or a scope the form does not offer
            return
        if "error" in made:
            self.view.refuse(made)
            return

        def then(failed):
            if failed:
                self.view.refuse({"field": None, "error": failed})
                return
            self.view.form, self.view.wanted = None, ("row", SERVER + made["name"])
            if agent == "claude":             # no session knows it yet: Claude looks at it
                self.do_retry_server(made["name"], lambda said: said["state"] == agent_setup.SIGN_IN
                                     and self.do_connect_server(made["name"]))
            else:
                self.wants = made["name"]
                self.ask()

        self.command("add-connector", made["argv"], then)

    def do_choose_agent(self, key):
        """KEY picked in the head's list: this folder's agent from now on (settings.json), its setup read."""
        if key not in agent_setup.KNOWN:
            return
        root = self.host.root
        self.host.save(lambda kept: {**kept, "agent_chosen": {**kept["agent_chosen"], root: key}})
        self.read_at = self.host.clock()
        self.ask()

    def do_sign_in(self, key):
        """The agent KEY's own login in a herdr tab of its own (core's words for it, nothing of herdr-fold's in
        between); the agents asked again every SIGNING seconds till it is in."""
        agent = self.view.agent_of(key)
        if not agent or key not in agent_setup.KNOWN:
            return
        self.host.open_tab(f"Sign in to {agent['name']}", list(agent["login"]))
        self.signing, self.read_at = (key, self.host.clock() + SIGNING_FOR), self.host.clock()

    def do_copy_text(self, words):
        """WORDS (an install line) on the clipboard; with no clipboard program, through the terminal's own."""
        if not self.clipboard(words):
            self.host.term.write("\x1b]52;c;" + base64.b64encode(words.encode("utf-8")).decode("ascii") + "\x07")
        self.host.note = "Copied"

    def do_remember_agent_folded(self, folded):
        self.host.save(agent_folded=folded)
