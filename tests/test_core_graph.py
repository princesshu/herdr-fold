"""Tests for core/graph.py in a temporary home and folder: an agent's wiring as nodes and edges with their gates
(agent-graph.html's lumen-api), what a conversation ran in order with its costs laid in (usage.html's), Codex's through
the same shapes from a stand-in; nothing of the agents' written. Every name, file and figure here is invented."""
import calendar
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_layers    # noqa: E402
import agent_setup    # noqa: E402
import graph    # noqa: E402
import graph_cli    # noqa: E402

SESSION = "5f0c6d9e-1b2a-4c3d-8e9f-0a1b2c3d4e5f"
THREAD = "0199a1b2-c3d4-7e5f-8a6b-9c0d1e2f3a4b"
REVIEWER = "pr-review-toolkit:code-reviewer"
# costs.py's answer for usage.html's conversation, as the client hands it in
COSTS = {"session": SESSION, "kind": "API value", "text": "~$4.12", "tokens": "1.2M", "agent": {
    "cost": 3.7, "text": "~$3.70", "title": "~$3.70 API value", "turns": 38, "tokens": 1_000_000, "share": 0.9,
    "model": {"id": "claude-opus-5-5", "name": "Opus 5.5", "color": "#3987e5"},
    "sub": "Opus 5.5 · 38 turns · 1.0M tokens",
    "lines": [["Model", "Opus 5.5", None], ["Input", "30k", None], ["Share", "90% of this chat", None]]},
    "subs": {REVIEWER: {"cost": 0.42, "text": "~$0.42", "title": "~$0.42 API value", "turns": 3, "tokens": 210_000,
                        "share": 0.1, "model": {"id": "claude-haiku-5-5", "name": "Haiku 5.5", "color": "#199e70"},
                        "sub": "Haiku 5.5 · 210k tokens",
                        "lines": [["Model", "Haiku 5.5", None], ["Share", "10% of this chat", None]]}}}


def at(minute):
    return f"2026-11-12T13:{minute:02d}:00.000Z"


class Folder(unittest.TestCase):
    def setUp(self):
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        self.home, self.folder = os.path.join(top, "home"), os.path.join(top, "work", "lumen-api")
        os.makedirs(self.folder)
        self.bin = os.path.join(self.home, "bin")       # the stand-in programs: the only ones a test finds
        for patch in (mock.patch.object(agent_setup, "MANAGED_DIR", os.path.join(top, "managed")),
                      mock.patch.object(agent_setup, "find", lambda name: shutil.which(name, path=self.bin))):
            patch.start()
            self.addCleanup(patch.stop)
        set_env(self, HOME=self.home, CODEX_HOME=None)

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def files(self):
        found = {}
        for base in (self.home, self.folder):
            for here, _, names in os.walk(base):
                found.update({os.path.join(here, name): os.stat(os.path.join(here, name)).st_mtime_ns
                              for name in names})
        return found

    def line(self, **fields):
        return json.dumps({"parentUuid": None, "isSidechain": False, "userType": "external", "cwd": self.folder,
                           "sessionId": SESSION, "version": "2.1.325", "timestamp": at(0), "uuid": "0b1d", **fields},
                          separators=(",", ":"))          # compact, as Claude writes a line

    def call(self, name, key, minute=0, **given):
        """An assistant line holding one tool call: the tool NAME, its id's end KEY, its input GIVEN."""
        return self.line(type="assistant", timestamp=at(minute), requestId=f"req_{key}", message={
            "id": f"msg_{key}", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "tool_use", "id": f"toolu_{key}", "name": name, "input": given}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 3, "output_tokens": 40}})

    def result(self, key, minute=0):
        return self.line(type="user", timestamp=at(minute), toolUseResult={"stdout": "ok"}, message={
            "role": "user", "content": [{"tool_use_id": f"toolu_{key}", "type": "tool_result", "content": "ok"}]})

    def done(self, name, key, minute=0, **given):
        return [self.call(name, key, minute, **given), self.result(key, minute)]

    def session(self, *lines, name=SESSION):
        place = os.path.join(self.home, ".claude", "projects", re.sub(r"[^A-Za-z0-9-]", "-", self.folder))
        return self.put(os.path.join(place, f"{name}.jsonl"), "\n".join(lines) + "\n")

    def sub(self, kind, call, *lines, id="a1b2c3"):
        """A subagent's file of the session, of KIND, started by the call whose id ends in CALL."""
        place = os.path.join(self.home, ".claude", "projects", re.sub(r"[^A-Za-z0-9-]", "-", self.folder), SESSION,
                             "subagents", f"agent-{id}")
        self.put(place + ".meta.json", json.dumps({"agentType": kind, "description": "Review the paging change",
                                                   "toolUseId": f"toolu_{call}", "spawnDepth": 1}))
        return self.put(place + ".jsonl", "\n".join(lines) + "\n")

    def graph(self, session=None, costs=None, agent="claude"):
        return graph.graph(agent, self.folder, self.home, session, costs)


def titled(found, key="sub"):
    return [(node["title"], node[key]) for node in found["nodes"]]


def node(found, title, nth=0):
    return [one for one in found["nodes"] if one["title"] == title][nth]


def edge(found, start, end):
    """The edge between the nodes titled START and END (the last of that title)."""
    ids = [[one["id"] for one in found["nodes"] if one["title"] == title][-1] for title in (start, end)]
    return next(one for one in found["edges"] if [one["from"], one["to"]] == ids)


class Lumen(Folder):
    """agent-graph.html's lumen-api: three rules, a project skill and fifteen of the user's, a plugin's reviewer,
    the built-in tools, and github, figma (to sign in) and sentry (failed), in a herdr-fold chat on Opus."""

    def setUp(self):
        super().setUp()
        claude, project = os.path.join(self.home, ".claude"), os.path.join(self.folder, ".claude")
        self.put(os.path.join(claude, "CLAUDE.md"), "x" * 9600)
        self.put(os.path.join(self.folder, "CLAUDE.md"), "x" * 7200)
        front = "---\npaths: src/lumen/**\n---\n"
        self.put(os.path.join(project, "rules", "api.md"), front + "x" * (2800 - len(front)))
        self.put(os.path.join(project, "skills", "api-routes", "SKILL.md"),
                 "---\nname: api-routes\ndescription: when routes change\n---\nKeep the routes' table in step.")
        for n in range(1, 16):
            self.put(os.path.join(claude, "skills", f"skill-{n:02d}", "SKILL.md"),
                     f"---\nname: skill-{n:02d}\ndescription: {'d' * 979}\n---\n")
        roots = {name: os.path.join(claude, "plugins", "cache", "market", name, "1.0")
                 for name in ("pr-review-toolkit", "figma")}
        self.put(os.path.join(claude, "plugins", "installed_plugins.json"), json.dumps({"version": 2, "plugins": {
            f"{name}@market": [{"scope": "user", "installPath": root}] for name, root in roots.items()}}))
        self.reviewer = self.put(os.path.join(roots["pr-review-toolkit"], "agents", "code-reviewer.md"), "\n".join([
            "---", "name: code-reviewer", "description: Reviews a pull request", "model: opus",
            "tools: Read, Grep, mcp__github__get_pull_request", "---", "You review lumen-api's changes."]))
        self.put(os.path.join(roots["figma"], ".mcp.json"), json.dumps({"mcpServers": {"figma": {
            "type": "http", "url": "https://mcp.figma.example/mcp"}}}))
        self.put(os.path.join(claude, "settings.json"), json.dumps({
            "enabledPlugins": {"pr-review-toolkit@market": True, "figma@market": True},
            "permissions": {"allow": ["Bash(pytest *)", "mcp__github"], "deny": ["Bash(git push *)"]}}))
        self.put(os.path.join(self.home, ".claude.json"), json.dumps({"mcpServers": {"github": {
            "command": "github-mcp"}}}))
        self.put(os.path.join(self.folder, ".mcp.json"), json.dumps({"mcpServers": {"sentry": {
            "command": "npx", "args": ["-y", "@sentry/mcp-server"]}}}))
        self.put(os.path.join(project, "settings.local.json"), json.dumps({"enabledMcpjsonServers": ["sentry"]}))
        tools = [f"mcp__github__tool_{n:02d}" for n in range(32)]
        self.told = [self.line(type="attachment", attachment={
            "type": "deferred_tools_delta", "addedNames": tools,
            "addedLines": [f"{name}: {'d' * 827}" for name in tools],
            "removedNames": [], "failedMcpServers": [{"name": "sentry", "error": "npx not found"}],
            "needsAuthMcpServers": ["plugin:figma:figma"], "pendingMcpServers": []}),
            self.line(type="permission-mode", permissionMode="default")]
        self.ran = [*self.done("Skill", "01", 1, skill="api-routes"), *self.done("Read", "02", 2),
                    *self.done("Edit", "03", 3), *self.done("Bash", "04", 4), *self.done("Bash", "05", 5),
                    *self.done("Bash", "06", 6), *self.done("Agent", "07", 36, subagent_type=REVIEWER)]
        self.status = self.put(os.path.join(self.home, ".local", "state", "herdr-fold", "chat", SESSION,
                                            "status.json"), json.dumps({"model": "Opus 5.5", "effort": "high"}))

    def wired(self):
        return self.graph(self.session(*self.told))

    def test_wiring_has_agent_graph_htmls_nodes_in_their_columns_with_their_words(self):
        found = self.wired()
        # no type before a name nor "built-in" on a tool; a fold of skills says their listing loads always
        self.assertEqual([(n["column"], n["kind"], n["title"], n["sub"], n["tag"], n["state"])
                          for n in found["nodes"]], [
            ("in", "rule", "~/.claude/CLAUDE.md", "always · 2.4k", "Global", None),
            ("in", "rule", "CLAUDE.md", "always · 1.8k", "Project", None),
            ("in", "rule", "api.md", "when src/lumen/** is read", "Project", None),
            ("in", "skill", "api-routes", "when routes change", "Project", None),
            ("in", "skills", "15 more skills", "listed always · 3.7k", None, None),
            ("agents", "agent", "Claude", "Opus 5.5 · High · Manual", None, None),
            ("agents", "sub", "code-reviewer", "Opus · 3 tools", "pr-review-toolkit", None),
            ("uses", "tool", "Read · Edit · Write", None, None, None),
            ("uses", "tool", "Bash", None, None, None),
            ("uses", "connector", "github", "32 tools · 6.8k", "Global", None),
            ("uses", "connector", "figma", "sign in", "figma", "warn"),
            ("uses", "connector", "sentry", "failed · npx not found", "Project", "bad")])
        self.assertEqual(node(found, "Claude")["chips"], ["PermissionRequest → herdr-fold"])
        self.assertEqual(node(found, "code-reviewer")["parent"], node(found, "Claude")["id"])
        self.assertEqual(found["words"], {
            "columns": {"in": "In", "agents": "Agents", "uses": "Uses"},
            "views": {"wiring": "Wiring", "run": "This chat"},
            "legend": [["always", "always"], ["demand", "on demand"], ["ran", "ran here"], ["failed", "failed"],
                       ["waiting", "sign in"]]})
        self.assertEqual((found["agent"], found["name"], found["session"]), ("claude", "Claude", SESSION))

    def test_an_edge_is_solid_for_what_always_loads_dashed_on_demand_waiting_and_failed(self):
        found = self.wired()
        titles = {one["id"]: one["title"] for one in found["nodes"]}
        self.assertEqual([(titles[one["from"]], titles[one["to"]], one["style"]) for one in found["edges"]], [
            ("~/.claude/CLAUDE.md", "Claude", "always"), ("CLAUDE.md", "Claude", "always"),
            ("api.md", "Claude", "demand"), ("api-routes", "Claude", "demand"), ("15 more skills", "Claude", "demand"),
            ("Claude", "code-reviewer", "demand"), ("Claude", "Read · Edit · Write", "always"),
            ("Claude", "Bash", "always"), ("Claude", "github", "always"), ("Claude", "figma", "waiting"),
            ("Claude", "sentry", "failed"), ("code-reviewer", "github", "always")])

    def test_a_gate_says_the_permission_with_its_exceptions_and_the_hook_where_it_asks(self):
        found = self.wired()
        ask, hook = {"text": "ask", "tone": "ask"}, {"text": "hook", "tone": "hook"}
        self.assertEqual(edge(found, "Claude", "Read · Edit · Write")["gates"], [ask, hook])
        # each gate a verb and its object
        self.assertEqual(edge(found, "Claude", "Bash")["gates"], [
            ask, {"text": "allow pytest", "tone": "allow"}, {"text": "deny git push", "tone": "deny"}, hook])
        self.assertEqual(edge(found, "Claude", "github")["gates"], [{"text": "allow", "tone": "allow"}])
        self.assertEqual([edge(found, "Claude", name)["gates"] for name in ("figma", "sentry", "code-reviewer")],
                         [[], [], []])
        self.assertEqual(edge(found, "CLAUDE.md", "Claude")["gates"], [])

    def test_every_layers_hooks_as_gates_inputs_or_chips_and_the_sandbox_on_bash(self):
        self.put(os.path.join(self.folder, ".claude", "settings.json"), json.dumps({
            "sandbox": {"enabled": True, "network": {"allowedDomains": ["pypi.org", "github.com"]}}, "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "./scripts/guard.sh"}]},
                               {"matcher": "mcp__github__.*", "hooks": [{"type": "command", "command": "gh-guard"}]}],
                "SessionStart": [{"hooks": [{"type": "command", "command": "~/.claude/hooks/context.sh"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "notify.sh"}]}]}}))
        found = self.wired()
        context = node(found, "SessionStart hook")
        self.assertEqual((context["column"], context["kind"], context["sub"], context["tag"]),
                         ("in", "hook", "context.sh · adds context", "Project"))
        self.assertEqual(edge(found, "SessionStart hook", "Claude")["style"], "always")
        # a gate on the edges its matcher meets, a verb and its object; one for every tool and a watcher on the agent
        self.assertEqual([one["text"] for one in edge(found, "Claude", "Bash")["gates"]],
                         ["ask", "allow pytest", "deny git push", "hook guard.sh", "hook"])
        self.assertEqual([one["text"] for one in edge(found, "Claude", "github")["gates"]], ["allow", "hook gh-guard"])
        self.assertEqual(node(found, "Claude")["chips"], ["PermissionRequest → herdr-fold", "Stop → notify.sh"])
        self.assertEqual(node(found, "Bash")["sub"], "sandboxed, 2 hosts")
        # This chat: a hook that adds context ran at start
        self.assertTrue(node(self.run_graph(), "SessionStart hook")["run"]["ran"])

    def test_the_mode_and_wider_rules_change_the_gates(self):
        path = os.path.join(self.home, ".claude", "settings.json")
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
        kept["permissions"] = {"allow": ["Bash", "Bash(pytest *)", "mcp__github__tool_01", "mcp__github__tool_02"],
                               "ask": ["Bash(git push *)", "Bash(rm *)", "Bash(curl *)", "Bash(ssh *)"],
                               "deny": ["Edit", "Bash(git push *)"]}
        self.put(path, json.dumps(kept))
        os.remove(self.status)
        found = self.graph(self.session(*self.told, self.line(type="permission-mode", permissionMode="acceptEdits")))
        self.assertEqual(node(found, "Claude")["sub"], "Edit automatically")
        self.assertEqual(node(found, "Claude")["chips"], [])
        self.assertEqual([one["text"] for one in edge(found, "Claude", "Read · Edit · Write")["gates"]],
                         ["allow", "deny Edit"])
        # the ask a deny hides is not said; past two exceptions of a kind, their count
        self.assertEqual([one["text"] for one in edge(found, "Claude", "Bash")["gates"]],
                         ["allow", "ask rm, curl +1", "deny git push"])
        self.assertEqual([one["text"] for one in edge(found, "Claude", "github")["gates"]], ["ask", "allow 2 tools"])
        self.session(*self.told, self.line(type="permission-mode", permissionMode="bypassPermissions"))
        found = self.graph(os.path.join(os.path.dirname(self.status), "..", "..", "none.jsonl"))
        self.assertEqual(found["session"], None)

    def test_a_nodes_properties_are_the_agent_views_label_and_value_lines(self):
        found = self.wired()
        layers = agent_layers.layers(agent_setup.setup("claude", self.folder, self.home), "claude", self.folder,
                                    self.home)
        rows = {row["id"]: row for section in layers["sections"] for row in section["rows"]}
        for one in found["nodes"]:
            if one["kind"] in ("rule", "skill", "connector", "sub"):
                self.assertEqual(one["properties"]["lines"][0], rows[one["id"]]["properties"]["lines"][0])
        reviewer = node(found, "code-reviewer")["properties"]
        self.assertEqual(reviewer["lines"], [["From", "pr-review-toolkit", "Plugin"], ["Model", "opus", None],
                                             ["Tools", "Read, Grep, mcp__github__get_pull_request", None]])
        self.assertEqual([(one["id"], one["label"], one["path"]) for one in reviewer["actions"]],
                         [("open", "Open code-reviewer.md", self.reviewer), ("agent", "Show in Agent", None)])
        self.assertEqual(node(found, "Claude")["properties"]["lines"], [
            ["Model", "Opus 5.5", None], ["Effort", "High", None], ["Mode", "Manual", None],
            ["Hook", "PermissionRequest", "herdr-fold"]])
        self.assertEqual(node(found, "Bash")["properties"]["lines"], [
            ["Allow", "Bash(pytest *)", "Global"], ["Deny", "Bash(git push *)", "Global"]])
        self.assertEqual(node(found, "Read · Edit · Write")["properties"]["lines"], [
            ["Tools", "Read, Edit, Write, MultiEdit, NotebookEdit", None]])
        more = node(found, "15 more skills")["properties"]["lines"]
        self.assertEqual((more[0], len(more)), (["skill-01", "Global", None], 15))

    def test_a_node_the_agent_panel_has_a_row_of_leads_to_it_and_the_agents_to_its_panel(self):
        def shows(found, view=None):
            told = {}
            for one in found["nodes"]:
                props = (one["run"] or {}).get("properties") if view == "run" else one["properties"]
                told[one["id"]] = [act for act in (props or {}).get("actions", []) if act["id"] == "agent"]
            return told
        found = self.wired()
        layers = agent_layers.layers(agent_setup.setup("claude", self.folder, self.home), "claude", self.folder,
                                    self.home)
        rows = {row["id"] for section in layers["sections"] for row in section["rows"]}
        for key, acts in shows(found).items():
            if key in rows:                 # a rule, a skill, a connector, a subagent: its row, by core's own id
                self.assertEqual(acts, [{"id": "agent", "label": "Show in Agent", "path": None, "server": None,
                                         "primary": False, "row": key}], key)
        self.assertEqual({key for key, acts in shows(found).items() if acts} - rows, {graph.AGENT})
        # the agent's own: its panel, no row; a built-in tool and a fold have no row there, so no way to one
        self.assertEqual(shows(found)[graph.AGENT], [{"id": "agent", "label": "Show in Agent", "path": None,
                                                      "server": None, "primary": True, "row": None}])
        self.assertEqual([shows(found)[key] for key in ("tool:Bash", "tool:files", "skills:more")], [[], [], []])
        self.assertEqual([one["id"] for one in node(found, "sentry")["properties"]["actions"]][-1], "agent")
        # in This conversation too: beside Open in Usage on the agent, after Open on a subagent that ran
        ran = self.run_graph()
        self.assertEqual([one["id"] for one in node(ran, "Claude")["run"]["properties"]["actions"]],
                         ["usage", "agent"])
        self.assertEqual([one["id"] for one in node(ran, "code-reviewer")["run"]["properties"]["actions"]],
                         ["open", "agent"])
        self.assertEqual(shows(ran, "run")["tool:Bash"], [])

    def agent_file(self, base, name, *more):
        return self.put(os.path.join(base, ".claude", "agents", f"{name}.md"), "\n".join([
            "---", f"name: {name}", "description: Does one thing", *more, "---", "You do one thing."]))

    def test_a_sub_agent_with_no_model_or_tools_and_the_ones_past_the_first_few_as_one_node(self):
        self.agent_file(self.folder, "migrations")
        self.agent_file(self.home, "docs-writer", "model: inherit", "tools: Edit, Bash")
        found = self.wired()
        self.assertEqual([(one["title"], one["sub"]) for one in found["nodes"] if one["kind"] in ("sub", "subs")], [
            ("migrations", None), ("2 more subagents", "on demand")])
        os.remove(self.reviewer)
        self.assertEqual([(one["title"], one["sub"]) for one in self.wired()["nodes"] if one["kind"] == "sub"], [
            ("migrations", None), ("docs-writer", "2 tools")])
        self.put(self.reviewer, "---\nname: code-reviewer\ndescription: Reviews\n---\n")
        for n in range(5):
            self.agent_file(self.folder, f"helper-{n}")
        found = self.wired()
        self.assertEqual([(one["title"], one["sub"], one["parent"]) for one in found["nodes"]
                          if one["kind"] in ("sub", "subs")][-2:],
                         [("helper-3", None, "agent"),
                          ("4 more subagents", "on demand", "agent")])
        more = node(found, "4 more subagents")
        self.assertEqual(more["properties"]["lines"][-1], ["code-reviewer", "pr-review-toolkit", None])
        self.assertEqual(edge(found, "Claude", "4 more subagents")["style"], "demand")

    def test_with_no_conversation_nothing_ran_and_the_mode_is_the_one_claude_starts_in(self):
        self.put(os.path.join(self.folder, ".claude", "settings.json"),
                 json.dumps({"permissions": {"defaultMode": "plan"}}))
        found = self.graph()
        self.assertEqual((found["run"], found["session"], found["path"]), (False, None, []))
        self.assertEqual((node(found, "Claude")["sub"], node(found, "Claude")["tag"]), ("Plan", None))
        self.assertTrue(all(one["run"] is None for one in found["nodes"] + found["edges"]))
        # no session told the servers' state: none checked, their edges on demand
        self.assertEqual(node(found, "github")["sub"], "not checked")
        self.assertEqual(edge(found, "Claude", "github")["style"], "demand")

    def test_a_server_turned_off_here_is_dim_with_no_edge(self):
        self.put(os.path.join(self.home, ".claude.json"), json.dumps({
            "mcpServers": {"github": {"command": "github-mcp"}},
            "projects": {self.folder: {"disabledMcpServers": ["github"]}}}))
        found = self.wired()
        self.assertEqual((node(found, "github")["sub"], node(found, "github")["dim"]), ("off here", True))
        self.assertFalse([one for one in found["edges"] if one["to"] == node(found, "github")["id"]])
        self.assertEqual(found["nodes"][-1]["title"], "github")           # after the ones that can run

    def conversation(self, *more):
        """usage.html's conversation: a skill, two file calls, three commands, then the reviewer reading github."""
        self.sub(REVIEWER, "07", *self.done("mcp__github__get_pull_request", "08", 37),
                 *self.done("mcp__github__get_pull_request", "09", 38))
        return self.session(*self.told, *self.ran, *more)

    def run_graph(self, *more, costs=COSTS):
        return self.graph(self.conversation(*more), costs)

    def test_this_conversation_numbers_what_ran_in_order_at_its_first_use(self):
        found = self.run_graph()
        self.assertTrue(found["run"])
        ids = {one["id"]: one["title"] for one in found["nodes"]}
        self.assertEqual([ids[one] for one in found["path"]],
                         ["api-routes", "Read · Edit · Write", "Bash", "code-reviewer", "github"])
        self.assertEqual([(one["title"], one["run"]["order"]) for one in found["nodes"] if one["run"]["ran"]], [
            ("~/.claude/CLAUDE.md", None), ("CLAUDE.md", None), ("api-routes", 1), ("Claude", None),
            ("code-reviewer", 4), ("Read · Edit · Write", 2), ("Bash", 3), ("github", 5)])
        self.assertEqual([one["title"] for one in found["nodes"] if not one["run"]["ran"]],
                         ["api.md", "15 more skills", "figma", "sentry"])

    def test_this_conversations_words_are_usage_htmls(self):
        found = self.run_graph()
        self.assertEqual([(one["title"], one["run"]["sub"]) for one in found["nodes"]], [
            ("~/.claude/CLAUDE.md", "always · 2.4k tokens"), ("CLAUDE.md", "always · 1.8k tokens"),
            ("api.md", "read with src/lumen/** · 700"), ("api-routes", "used once · 7"),
            ("15 more skills", "listed always · 3.7k"), ("Claude", "Opus 5.5 · 38 turns · 1.0M tokens"),
            ("code-reviewer", "Haiku 5.5 · 210k tokens"), ("Read · Edit · Write", None), ("Bash", None),
            ("github", "6.8k tokens in context"), ("figma", "not used"), ("sentry", "not used")])
        self.assertEqual(found["cost"], "~$4.12")                           # the chat's whole, for the head
        self.assertEqual([(one["title"], one["run"]["calls"]) for one in found["nodes"] if one["run"]["calls"]],
                         [("Read · Edit · Write", "2 calls"), ("Bash", "3 calls"), ("github", "2 calls")])
        self.assertEqual([node(found, name)["run"]["tag"] for name in ("figma", "sentry", "github")],
                         [{"text": "sign in", "tone": "warn"}, {"text": "failed", "tone": "bad"}, None])

    def test_an_agents_cost_model_and_share_are_laid_in_from_costs(self):
        found = self.run_graph()
        claude, reviewer = node(found, "Claude")["run"], node(found, "code-reviewer")["run"]
        self.assertEqual((claude["cost"], claude["model"], claude["share"]),
                         ("~$3.70", {"name": "Opus 5.5", "color": "#3987e5"}, 0.9))
        self.assertEqual((reviewer["cost"], reviewer["model"]["color"], reviewer["share"]), ("~$0.42", "#199e70", 0.1))
        self.assertEqual(claude["properties"], {
            "title": "Claude", "state": {"text": "~$3.70 API value", "tone": "ok"}, "text": None, "error": None,
            "tip": None, "lines": [["Model", "Opus 5.5 · High", None], ["Input", "30k", None],
                                   ["Share", "90% of this chat", None]],
            "actions": [{"id": "usage", "label": "Open in Usage", "path": None, "server": None, "primary": True,
                         "session": SESSION},
                        {"id": "agent", "label": "Show in Agent", "path": None, "server": None, "primary": False,
                         "row": None}]})
        self.assertEqual(reviewer["started"], calendar.timegm((2026, 11, 12, 13, 36, 0)))
        self.assertEqual(reviewer["properties"]["state"], {"text": "~$0.42 API value", "tone": "ok"})
        self.assertEqual(reviewer["properties"]["lines"], [
            ["From", "pr-review-toolkit", "Plugin"], ["Model", "Haiku 5.5", None],
            ["Tools", "Read, Grep, mcp__github__get_pull_request", None],
            ["Started", "by Claude at {time}, step 4", None], ["Share", "10% of this chat", None]])
        self.assertEqual(reviewer["properties"]["actions"][0]["label"], "Open code-reviewer.md")
        self.assertEqual(node(found, "Bash")["run"]["properties"]["lines"], [["Calls", "3", None]])
        self.assertEqual(node(found, "Read · Edit · Write")["run"]["properties"]["lines"],
                         [["Calls", "2", None], ["Read", "1", None], ["Edit", "1", None]])

    def test_without_costs_the_words_say_what_ran(self):
        found = self.run_graph(costs=None)
        self.assertEqual((node(found, "Claude")["run"]["sub"], node(found, "Claude")["run"]["cost"]),
                         ("Opus 5.5 · High · Manual", None))
        self.assertEqual(node(found, "code-reviewer")["run"]["sub"], "ran once")
        self.assertIsNone(found["cost"])
        shutil.rmtree(os.path.join(os.path.dirname(self.session()), SESSION))
        found = self.graph(self.session(*self.told), None)
        self.assertEqual(node(found, "code-reviewer")["run"]["sub"], "not run in this chat")

    def test_the_edges_that_ran_and_the_one_running_now(self):
        found = self.run_graph()
        self.assertEqual([(one["title"], other["title"]) for one in found["nodes"] for other in found["nodes"]
                          for line in found["edges"] if [line["from"], line["to"]] == [one["id"], other["id"]]
                          and line["run"]["ran"]],
                         [("~/.claude/CLAUDE.md", "Claude"), ("CLAUDE.md", "Claude"), ("api-routes", "Claude"),
                          ("Claude", "code-reviewer"), ("Claude", "Read · Edit · Write"), ("Claude", "Bash"),
                          ("code-reviewer", "github")])
        self.assertFalse([one for one in found["edges"] if one["run"]["running"]])
        self.assertEqual(edge(found, "Claude", "github")["run"], {"ran": False, "running": False, "calls": 0})
        self.assertEqual(edge(found, "Claude", "Bash")["run"], {"ran": True, "running": False, "calls": 3})
        # a call with no result yet runs; one left open before later messages was given up
        found = self.run_graph(self.call("Grep", "20", 40), *self.done("Read", "21", 41), self.call("Bash", "22", 42))
        self.assertEqual([(one["from"], one["to"]) for one in found["edges"] if one["run"]["running"]],
                         [(node(found, "Claude")["id"], node(found, "Bash")["id"])])
        self.assertEqual((node(found, "Grep")["sub"], node(found, "Grep")["run"]["order"]), (None, 6))

    def test_a_sub_agent_still_out_runs_and_one_claude_does_not_list_gets_a_node(self):
        found = self.run_graph(*self.done("Agent", "31", 50),
                               self.call("Agent", "30", 51, subagent_type="Explore"))
        explore = node(found, "Explore")
        self.assertEqual((explore["kind"], explore["sub"], explore["run"]["order"], explore["parent"]),
                         ("sub", None, 7, node(found, "Claude")["id"]))
        self.assertTrue(edge(found, "Claude", "Explore")["run"]["running"])
        self.assertEqual(node(found, "general-purpose")["run"]["sub"], "ran once")

    def test_a_call_that_names_no_sub_agent_reaches_claudes_general_one_as_listed(self):
        listing = self.line(type="attachment", attachment={
            "type": "agent_listing_delta", "addedTypes": ["general-purpose"], "builtInTypes": ["general-purpose"],
            "addedLines": ["- general-purpose: For any task (Tools: *)"], "removedTypes": [], "isInitial": True})
        found = self.run_graph(listing, *self.done("Agent", "31", 50))
        general = [one for one in found["nodes"] if one["title"] == "general-purpose"]
        self.assertEqual([(one["id"], one["run"]["order"], one["run"]["sub"]) for one in general],
                         [("subagent:Claude:general-purpose", 6, "ran once")])
        # folded into one row in the Agent panel: its node leads there
        self.assertEqual(general[0]["properties"]["actions"][-1]["row"], "subagent:built-in")

    def test_a_sub_agent_that_called_nothing_still_ran_and_one_of_no_type_is_tokens_pys_agent(self):
        said = self.line(type="assistant", message={"id": "msg_90", "role": "assistant", "content": [
            {"type": "text", "text": "Nothing to change."}]})
        self.sub("Explore", "98", said, id="d4e5f6")
        self.sub(None, "99", *self.done("Bash", "91", 55), id="a7b8c9")
        costs = {**COSTS, "subs": {"Explore": COSTS["subs"][REVIEWER], "agent": COSTS["subs"][REVIEWER]}}
        found = self.run_graph(costs=costs)
        explore, other = node(found, "Explore"), node(found, "agent")
        self.assertEqual((explore["run"]["ran"], explore["run"]["order"], explore["run"]["cost"]),
                         (True, None, "~$0.42"))
        self.assertTrue(edge(found, "Claude", "Explore")["run"]["ran"])
        self.assertEqual((other["kind"], other["run"]["ran"], other["run"]["cost"]), ("sub", True, "~$0.42"))
        self.assertEqual(edge(found, "agent", "Bash")["run"]["calls"], 1)

    def test_a_call_written_twice_counts_once(self):
        found = self.run_graph(self.ran[4], self.ran[4])
        self.assertEqual(node(found, "Read · Edit · Write")["run"]["calls"], "2 calls")

    def test_a_tools_name_from_a_session_is_drawn_as_text_and_cut(self):
        found = self.run_graph(*self.done("Web\x1b[31mFetch\x07\n" + "x" * 300, "40", 45),
                               *self.done("mcp__ghost__read", "41", 46), self.line(type="assistant", message="no"),
                               '{"type":"assistant","message":{"content":[{"type":"tool_use"',
                               'not json "type":"tool_use"',
                               self.result("40", 47).replace("ok", r'{\"type\":\"tool_use\",\"id\":\"toolu_99\"}'))
        odd = found["nodes"][-2]
        self.assertEqual((odd["title"][:9], len(odd["title"]), odd["column"]), ("WebFetch ", 40, "uses"))
        self.assertTrue(odd["title"].endswith("…"))
        self.assertFalse(re.search(r"\\u00[01]|\\u007f", json.dumps(found)))     # nor in an id
        self.assertEqual((found["nodes"][-1]["title"], found["nodes"][-1]["run"]["calls"]), ("ghost", "1 call"))

    def test_nothing_of_the_agents_is_written(self):
        session = self.conversation()
        before = self.files()
        self.graph(session, COSTS)
        self.assertEqual(self.files(), before)

    def test_the_cli_answers_in_json_the_folders_newest_conversation_unless_one_is_named(self):
        self.conversation()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = graph_cli.main(["graph_cli.py", "claude", self.folder, "--costs=" + json.dumps(COSTS)])
        found = json.loads(out.getvalue())
        self.assertEqual((code, found["session"], node(found, "Claude")["run"]["cost"]), (0, SESSION, "~$3.70"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(graph_cli.main(["graph_cli.py", "claude", self.folder, SESSION]), 0)
        self.assertEqual(json.loads(out.getvalue())["path"], found["path"])
        with contextlib.redirect_stderr(io.StringIO()) as said:
            self.assertEqual(graph_cli.main(["graph_cli.py", "gemini", self.folder]), 2)
            self.assertEqual(graph_cli.main(["graph_cli.py", "claude", self.folder, "--costs=not json"]), 2)
            self.assertEqual(graph_cli.main(["graph_cli.py", "claude"]), 2)
        self.assertIn("usage: graph_cli.py", said.getvalue())


class Codex(Folder):
    """Codex in lumen-api: its two AGENTS.md, a skill, its prefix rules and a server its own list names, from a
    stand-in codex; a rollout that ran its shell."""

    def setUp(self):
        super().setUp()
        codex = os.path.join(self.home, ".codex")
        self.put(os.path.join(codex, "AGENTS.md"), "x" * 4000)
        self.put(os.path.join(self.folder, "AGENTS.md"), "x" * 2000)
        self.put(os.path.join(codex, "skills", "release-notes", "SKILL.md"),
                 "---\nname: release-notes\ndescription: Writes a release's notes\n---\n")
        self.put(os.path.join(codex, "rules", "default.rules"),
                 'prefix_rule(pattern=["git", "status"], decision="allow")\n'
                 'prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
        listed = [{"name": "sentry", "enabled": True, "disabled_reason": None, "auth_status": "unsupported",
                   "transport": {"type": "stdio", "command": "npx", "args": ["-y", "@sentry/mcp-server"],
                                 "env": {"SENTRY_TOKEN": "invented"}}}]
        stubs(self.bin, {"codex": "#!/bin/sh\ncat <<'END'\n" + json.dumps(listed) + "\nEND\n"})

    def rollout(self, *lines, policy="on-request"):
        head = [{"type": "session_meta", "payload": {"id": THREAD, "cwd": self.folder, "source": "cli"}},
                {"type": "turn_context", "payload": {"turn_id": "turn-1", "cwd": self.folder, "model": "gpt-6-astra",
                                                     "effort": "high", "approval_policy": policy}}]
        return self.put(os.path.join(self.home, ".codex", "sessions", "2026", "11", "12",
                                     f"rollout-2026-11-12T13-00-00-{THREAD}.jsonl"),
                        "\n".join(json.dumps({"timestamp": at(n), **one}) for n, one in enumerate(head + list(lines)))
                        + "\n")

    def called(self, name, key, kind="custom_tool_call", done=True):
        made = [{"type": "response_item", "payload": {"type": kind, "name": name, "call_id": f"call_{key}",
                                                      "input": "ls"}}]
        return made + [{"type": "response_item", "payload": {"type": f"{kind}_output", "call_id": f"call_{key}",
                                                             "output": "ok"}}] * done

    def test_codexs_wiring_through_the_same_shapes_with_nothing_of_claudes(self):
        found = self.graph(agent="codex")
        self.assertEqual([(n["column"], n["kind"], n["title"], n["sub"], n["tag"]) for n in found["nodes"]], [
            ("in", "rule", "~/.codex/AGENTS.md", "always · 1.0k", "Global"),
            ("in", "rule", "AGENTS.md", "always · 500", "Project"),
            ("in", "skill", "release-notes", "Writes a release's notes", "Global"),
            ("agents", "agent", "Codex", None, None), ("uses", "tool", "Shell", None, None),
            ("uses", "connector", "sentry", "on", "Global")])
        self.assertEqual((found["name"], node(found, "Codex")["chips"], found["run"]), ("Codex", [], False))
        self.assertEqual(edge(found, "Codex", "Shell")["gates"], [
            {"text": "allow git status", "tone": "allow"}, {"text": "deny git push", "tone": "deny"}])
        self.assertEqual(edge(found, "Codex", "sentry")["gates"], [])
        self.assertNotIn("invented", json.dumps(found))
        self.assertNotIn("PermissionRequest", json.dumps(found))

    def test_a_rollouts_calls_in_order_with_its_policy_on_the_gate(self):
        path = self.rollout(*self.called("exec", "01"), *self.called("exec", "02"),
                            *self.called("wait", "03", "function_call"), *self.called("exec", "04", done=False))
        costs = {"session": THREAD, "kind": "spent", "agent": {**COSTS["agent"], "title": "~$8.60 spent",
                                                               "sub": "GPT-6 Astra · 2 turns · 900k tokens"},
                 "subs": {}}
        found = self.graph(path, costs, "codex")
        self.assertEqual((found["session"], found["run"]), (THREAD, True))
        self.assertEqual([(one["title"], one["run"]["order"], one["run"]["calls"]) for one in found["nodes"]
                          if one["run"]["order"]], [("Shell", 1, "3 calls"), ("wait", 2, "1 call")])
        self.assertEqual(edge(found, "Codex", "Shell")["gates"][:2],
                         [{"text": "ask", "tone": "ask"}, {"text": "allow git status", "tone": "allow"}])
        self.assertTrue(edge(found, "Codex", "Shell")["run"]["running"])
        codex = node(found, "Codex")
        self.assertEqual((codex["tag"], codex["run"]["sub"], codex["run"]["properties"]["state"]["text"]),
                         (None, "GPT-6 Astra · 2 turns · 900k tokens", "~$8.60 spent"))
        never = self.graph(self.rollout(policy="never"), None, "codex")
        self.assertEqual(edge(never, "Codex", "Shell")["gates"][0]["text"], "allow")

    def test_codexs_line_has_its_model_effort_and_approval_as_claudes_has_its_mode(self):
        # the model and effort as the head says them (its config's, else the newest chat's first turn); the approval
        # policy the chat's last turn tells, and the gate follows it
        last = {"type": "turn_context", "payload": {"turn_id": "turn-2", "effort": "xhigh",
                                                    "approval_policy": "untrusted"}}
        found = self.graph(self.rollout(*self.called("exec", "01")), None, "codex")
        self.assertEqual(node(found, "Codex")["sub"], "GPT-6 Astra · High · Ask on request")
        self.assertEqual(node(found, "Codex")["properties"]["lines"], [
            ["Model", "GPT-6 Astra", None], ["Effort", "High", None], ["Approval", "Ask on request", None]])
        found = self.graph(self.rollout(*self.called("exec", "01"), last), COSTS, "codex")
        self.assertEqual(node(found, "Codex")["sub"].split(" · ")[1:], ["Extra high", "Ask unless trusted"])
        self.assertEqual(node(found, "Codex")["chips"], [])
        # a policy with no word shows none, never itself
        odd = self.graph(self.rollout(policy="lumen-policy"), None, "codex")
        self.assertEqual(node(odd, "Codex")["sub"], "GPT-6 Astra · High")
        # its config's over the chat's; no other table's or key's said
        config = os.path.join(self.home, ".codex", "config.toml")
        self.put(config, 'model = "gpt-6-astra"\nmodel_reasoning_effort = "medium"   # the default\n'
                         "approval_policy = 'never'\nnotify = [\"/Users/dev/bin/notify\"]\n\n[tui]\n"
                         'approval_policy = "untrusted"\n\n[mcp_servers.sentry.env]\nSENTRY_TOKEN = "invented"\n')
        found = self.graph(agent="codex")
        self.assertEqual((node(found, "Codex")["sub"], found["run"]), ("GPT-6 Astra · Medium · Never ask", False))
        # the Agent panel's Permissions says the same policy in the same words: one table, one reading
        self.assertIs(graph.setup.APPROVALS, agent_setup.APPROVALS)
        self.assertFalse(hasattr(graph, "APPROVALS"))
        self.assertEqual(agent_setup.codex_permissions(self.home)["mode"], "never")
        self.assertEqual(edge(found, "Codex", "Shell")["gates"][0]["text"], "allow")
        self.assertNotIn("invented", json.dumps(found))
        self.assertNotIn("notify", json.dumps(found))
        self.assertEqual(agent_setup.codex_config(self.home), {
            "model": "gpt-6-astra", "model_reasoning_effort": "medium", "approval_policy": "never",
            "notify": ["/Users/dev/bin/notify"], "tui": {"approval_policy": "untrusted"},
            "mcp_servers.sentry.env": {"SENTRY_TOKEN": "invented"}})
        found = self.graph(self.rollout(policy="never"), None, "codex")
        self.assertEqual(node(found, "Codex")["sub"], "GPT-6 Astra · Medium · Never ask")
        # a profile named: its table is not read, so nothing is said rather than the wrong word
        self.put(config, 'profile = "careful"\nmodel_reasoning_effort = "low"\n\n[profiles.careful]\n'
                         'approval_policy = "on-request"\n')
        self.assertEqual(agent_setup.codex_config(self.home), {})
        self.put(config, '[tui]\napproval_policy = "never"\n')
        self.assertEqual(agent_setup.codex_config(self.home), {"tui": {"approval_policy": "never"}})
        for text in ("approval_policy = 3\n", ""):
            self.put(config, text)
            self.assertEqual(agent_setup.codex_config(self.home), {})
        os.remove(config)
        self.assertEqual(agent_setup.codex_config(self.home), {})
        self.assertEqual(node(self.graph(agent="codex"), "Codex")["sub"], "GPT-6 Astra · High")

    def test_the_cli_takes_codexs_newest_rollout_in_the_folder(self):
        self.rollout(*self.called("exec", "01"))
        self.put(os.path.join(self.home, ".codex", "sessions", "2026", "11", "13",
                              "rollout-2026-11-13T09-00-00-x.jsonl"),
                 json.dumps({"type": "session_meta", "payload": {"id": "other", "cwd": "/Users/dev/tidepool"}}) + "\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(graph_cli.main(["graph_cli.py", "codex", self.folder]), 0)
        self.assertEqual(json.loads(out.getvalue())["session"], THREAD)

    def test_with_no_codex_here_there_is_no_graph(self):
        shutil.rmtree(self.bin)
        self.assertIsNone(self.graph(agent="codex"))
