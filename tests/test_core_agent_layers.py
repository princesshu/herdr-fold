"""Tests for core/agent_layers.py in a temporary home, folder and managed folder: the Agent panel's layers of what
agent_setup.py reads, in both clients' words: the head, the sections with their rows, properties and actions, the
command the app runs; nothing of the agents' written."""
import contextlib
import io
import json
import os
import sys
import unittest

from support import PACKAGE, AgentHome

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_layers    # noqa: E402
import agent_layers_cli    # noqa: E402
import agent_setup    # noqa: E402

# a row the graph draws ends with its way there, the first only where it is the row's one action
SHOW = {"id": "graph", "label": "Show in graph", "path": None, "server": None, "primary": False}


class AgentLayers(AgentHome, unittest.TestCase):
    def lumen(self):
        """lumen-api as center-chat.html's Agent panel has it: four rules, 17 permissions with a conflict, two skills,
        four servers (sentry failed, figma to sign in), five subagents; the open conversation's file."""
        self.rule_files = {
            "global": self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "x" * 9600),
            "project": self.put(os.path.join(self.folder, "CLAUDE.md"), (
                "# lumen-api\n\nRoutes live in src/lumen/routes.\nEvery route answers JSON.\nKeep tests close.\n"
            ).ljust(7200, "y")),
            "agents": self.put(os.path.join(self.folder, "AGENTS.md"), "z" * 4800),
            "api": self.put(os.path.join(self.folder, ".claude", "rules", "api.md"), (
                '---\npaths:\n  - "src/lumen/**"\n---\n\n# Routes\x1b[31m\n\nEach route answers JSON.\n'
            ).ljust(2800, "w"))}
        roots = self.install("pr-review", "figma")
        self.agent_file(os.path.join(roots["pr-review"], "agents"), "code-reviewer.md", name="code-reviewer",
                        description="Reviews a pull request", model="sonnet", tools="Read, Grep")
        self.put(os.path.join(roots["figma"], ".mcp.json"),
                 json.dumps({"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}))
        self.settings("user", enabledPlugins={"pr-review@market": True, "figma@market": True}, permissions={"allow": [
            "Bash(git push:*)", "Bash(npm test)", "Bash(npm run lint)", "Read(src/**)", "Edit(src/**)",
            "Bash(git status)", "Bash(git diff *)", "Bash(git log *)", "WebFetch(domain:docs.lumen.dev)", "Bash(ls *)",
            "Bash(pytest *)", "Grep"]})
        self.settings("project", permissions={"deny": ["Bash(git push:*)", "Bash(rm -rf *)"]})
        self.settings("local", enabledMcpjsonServers=["sentry"],
                      permissions={"ask": ["Bash(git commit *)", "Bash(docker *)", "WebSearch"]})
        self.put(os.path.join(self.folder, ".claude", "skills", "routes", "SKILL.md"),
                 "---\nname: api-routes\ndescription: " + "How lumen-api's routes are written. ".ljust(1190, "r") +
                 "\n---\n")
        self.put(os.path.join(self.home, ".claude", "skills", "design", "SKILL.md"),
                 "---\nname: frontend-design\ndescription: " + "Distinctive interfaces. ".ljust(785, "d") + "\n---\n")
        self.claude_json(mcpServers={"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
                                     "chrome-devtools": {"command": "npx", "args": ["chrome-devtools-mcp@latest"]}})
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        explore = ("Explore", "Fast read-only search (Tools: All tools except Edit, Write)")
        general = ("general-purpose", "Researches a question (Tools: *)")
        plan = ("Plan", "Plans an implementation (Tools: Read, Grep, Glob)")
        status = ("statusline-setup", "Sets up the status line (Tools: Read, Edit)")
        return self.session("a0", *[
            self.listing([explore, general, plan, status], [name for name, _ in (explore, general, plan, status)],
                         initial=True),
            self.delta(["Read", "mcp__github__get_issue", "mcp__github__list_pulls",
                        "mcp__chrome-devtools__take_screenshot"],
                       failed=[("sentry", "spawn npx ENOENT: npx is not on this machine's PATH")],
                       sign_in=["plugin:figma:figma"], pending=[]),
            # github's instructions: its tools and these, 16,000 tokens
            self.instructions({"github": "g" * (64000 - len("mcp__github__get_issue\nmcp__github__list_pulls\n"))}),
            self.call("Skill", "01", skill="api-routes"),
            self.call("mcp__chrome-devtools__take_screenshot", "02"),
            self.call("Agent", "03", description="Find the routes", prompt="…", subagent_type="Explore")])

    def layers(self, agent="claude", session=None):
        return agent_layers.layers(agent_setup.setup(agent, self.folder, self.home, session), agent, self.folder,
                                  self.home)

    @staticmethod
    def section(found, key):
        return next(s for s in found["sections"] if s["id"] == key)

    @staticmethod
    def chosen(section, name):
        return next(r for r in section["rows"] if r["name"] == name)

    def test_the_sections_in_order_with_their_counts_costs_and_rows(self):
        session = self.lumen()
        before = self.files()
        found = self.layers(session=session)
        self.assertEqual(self.files(), before)
        # Rules count and cost what loads always (api.md is read with its paths alone); Permissions has no count
        self.assertEqual([(s["id"], s["title"], s["count"], s["tokens"], s["cost"], s["swatch"])
                          for s in found["sections"]], [
            ("subagents", "Subagents", 5, None, None, None), ("rules", "Rules", 3, 5400, "5.4k", "rules"),
            ("skills", "Skills", 2, 500, "500", "skills"), ("permissions", "Permissions", None, None, None, None),
            ("connectors", "Connectors", 4, 16009, "16.0k", "connectors")])
        rules = self.section(found, "rules")
        self.assertEqual([(r["id"], r["icon"], r["name"], r["note"], r["tag"], r["state"], r["tokens"], r["cost"],
                           r["dim"], r["mark"], r["agents"]) for r in rules["rows"]], [
            ("rule:" + self.rule_files["global"], "file", "~/.claude/CLAUDE.md", None,     # never two of one name
             "Global", None, 2400, "2.4k", False, None, ["claude"]),
            ("rule:" + self.rule_files["project"], "file", "CLAUDE.md", None, "Project", None, 1800, "1.8k", False,
             None, ["claude"]),
            ("rule:" + self.rule_files["agents"], "file", "AGENTS.md", None, "Project", None, 1200, "1.2k", False,
             None, ["claude"]),
            # read only with the files it names: dim, its cost not loaded at start
            ("rule:" + self.rule_files["api"], "file", "api.md", "when src/lumen/** is read", "Project", None, 700,
             "700", True, None, ["claude"])])
        skills = self.section(found, "skills")
        self.assertEqual([(r["icon"], r["name"], r["tag"], r["cost"], r["mark"]) for r in skills["rows"]], [
            ("skill", "frontend-design", "Global", "200", None), ("skill", "api-routes", "Project", "300", "ok")])
        # your own subagents each a row with their model and tools; Claude's own folded into one, used in this chat
        agents = self.section(found, "subagents")
        self.assertEqual(agents["summary"], [])
        self.assertEqual([(r["id"], r["name"], r["note"], r["tag"], r["mark"], r["state"]) for r in agents["rows"]], [
            ("subagent:pr-review:code-reviewer", "code-reviewer", "Sonnet · read-only", "pr-review", None, None),
            ("subagent:built-in", "Explore, general-purpose, Plan", "1 more", "Built-in", "ok", None)])
        self.assertEqual(agents["rows"][1]["names"], ["Explore", "general-purpose", "Plan", "statusline-setup"])
        self.assertEqual(agents["rows"][1]["properties"]["lines"], [
            ["From", "Claude", "Built-in"], ["Explore", "", None], ["general-purpose", "", None],
            ["Plan", "read-only", None], ["statusline-setup", "2 tools", None], ["Used", "once in this chat", None]])
        self.assertEqual(agents["rows"][1]["properties"]["actions"], [])         # no one node of the graph's
        self.assertEqual([s["summary"] for s in found["sections"] if s["id"] in ("rules", "skills", "connectors")],
                         [[], [], []])

    def test_a_failed_and_a_sign_in_connector_come_first_with_their_words(self):
        found = self.layers(session=self.lumen())
        connectors = self.section(found, "connectors")
        self.assertEqual([(r["id"], r["icon"], r["name"], r["state"], r["tag"], r["cost"], r["mark"], r["dim"])
                          for r in connectors["rows"]], [
            ("connector:sentry", "plug", "sentry", {"text": "failed", "tone": "bad"}, "Project", None, "bad", False),
            ("connector:plugin:figma:figma", "plug", "figma", {"text": "sign in", "tone": "warn"}, "figma", None,
             "warn", False),
            # then Claude's own /mcp order
            ("connector:chrome-devtools", "plug", "chrome-devtools", {"text": "1 tool", "tone": "ok"}, "Global", "9",
             "ok", False),
            ("connector:github", "plug", "github", {"text": "2 tools", "tone": "ok"}, "Global", "16.0k", None,
             False)])
        # a known service's brand, for its logo (the app) or its glyph (the TUI); a rule or a skill has none
        self.assertEqual([r["brand"] for r in connectors["rows"]], ["sentry", "figma", None, None])
        self.assertEqual({r["brand"] for s in found["sections"] if s["id"] != "connectors" for r in s["rows"]}, {None})
        # what loads at start, by part, each one's share: the rules read always, every skill's listing, the
        # connectors' tools and instructions
        self.assertEqual([(one["part"], one["tokens"], round(one["share"], 3)) for one in found["bar"]],
                         [("rules", 5400, 0.246), ("skills", 500, 0.023), ("connectors", 16009, 0.731)])
        self.assertEqual(found["head"]["problems"], [
            {"text": "1 failed", "tone": "bad", "row": "connector:sentry"},
            {"text": "1 sign in", "tone": "warn", "row": "connector:plugin:figma:figma"}])
        # the sentry's error as Claude said it, no file in it
        self.assertEqual(connectors["rows"][0]["properties"]["error"],
                         "spawn npx ENOENT: npx is not on this machine's PATH")

    def test_a_server_added_by_url_says_where_claude_signs_it_out_and_has_no_button_for_it(self):
        self.claude_json(
            mcpServers={"harbor": {"type": "http", "url": "https://api.harbor.dev/mcp"}},
            claudeAiMcpEverConnected=["claude.ai Box"],
            projects={self.folder: {"mcpServers": {"tidepool-db": {"command": "tidepool-mcp"}}}})
        tools = ["mcp__harbor__list_ports", "mcp__tidepool-db__query", "mcp__claude_ai_Box__search"]
        found = self.layers(session=self.session("a0", self.delta(tools, failed=[], sign_in=[], pending=[])))
        rows = {r["name"]: r["properties"] for r in self.section(found, "connectors")["rows"]}
        # signing out is Claude's own: its command on a line, never a button of herdr-fold's
        self.assertEqual(rows["harbor"]["lines"], [["From", "~/.claude.json", "Global"],
                                                   ["URL", "api.harbor.dev/mcp", None],
                                                   ["Sign out", "claude mcp logout harbor", None]])
        self.assertEqual([one["id"] for one in rows["harbor"]["actions"]], ["turn-off", "graph"])
        # a server that runs a program signs in nowhere; a claude.ai connector keeps its button and needs no line
        self.assertEqual(rows["tidepool-db"]["lines"], [["From", "~/.claude.json", "Local"],
                                                        ["Runs", "tidepool-mcp", None]])
        self.assertEqual(rows["Box"]["lines"], [["From", "claude.ai", "Account"]])
        self.assertEqual([one["id"] for one in rows["Box"]["actions"]], ["turn-off", "sign-out", "graph"])

    def test_each_state_has_its_word_and_the_actions_it_allows(self):
        self.claude_json(
            mcpServers={"Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"}},
            claudeAiMcpEverConnected=["claude.ai Box", "claude.ai Google Drive", "claude.ai Notion"],
            projects={self.folder: {"mcpServers": {"tidepool-db": {"command": "tidepool-mcp"}},
                                    "disabledMcpServers": ["claude.ai Notion"]}})
        mcp = self.project_file(**{"harbor-api": {"type": "http", "url": "https://api.harbor.dev/mcp"}},
                                sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        self.settings("local", enabledMcpjsonServers=["sentry"])
        drive = ["mcp__claude_ai_Google_Drive__search_files", "mcp__claude_ai_Google_Drive__read_file"]
        session = self.session("a0", self.delta(["mcp__tidepool-db__query"] + drive, failed=[],
                                                sign_in=["claude.ai Box"], pending=["sentry"]),
                               self.call(drive[0], "01", query="paging"), self.call(drive[1], "02", id="spec"))
        found = self.layers(session=session)
        # nothing else to show: a section with no rows is left out; Permissions (the mode and the sandbox, a file's
        # or Claude's own) and Connectors (where one is added) never
        self.assertEqual([s["id"] for s in found["sections"]], ["permissions", "connectors"])
        rows = {r["name"]: r for r in self.section(found, "connectors")["rows"]}
        self.assertEqual([(name, r["state"], r["tag"], r["mark"], r["dim"]) for name, r in rows.items()], [
            ("Box", {"text": "sign in", "tone": "warn"}, "claude.ai", "warn", False),
            # a .mcp.json server waiting for its yes, and one Claude was still connecting
            ("harbor-api", {"text": "not approved", "tone": "off"}, "Project", None, True),
            ("sentry", {"text": "connecting", "tone": "busy"}, "Project", None, False),
            ("tidepool-db", {"text": "1 tool", "tone": "ok"}, "Local", None, False),
            ("Dropbox", {"text": "not checked", "tone": "off"}, "Global", None, False),
            # used in this chat: its one mark; on or off has none (off is the dim name)
            ("Google Drive", {"text": "2 tools", "tone": "ok"}, "claude.ai", "ok", False),
            ("Notion", {"text": "off here", "tone": "off"}, "claude.ai", None, True)])

        def action(one, label, path=None, primary=False):
            return {"id": one, "label": label, "path": path, "server": None if one == "open" else server,
                    "primary": primary}
        server = "claude.ai Box"
        self.assertEqual(rows["Box"]["properties"], {
            "title": "Box", "state": {"text": "sign in", "tone": "warn"}, "lines": [["From", "claude.ai", "Account"]],
            "text": None, "error": None, "tip": None,
            "actions": [action("connect", "Connect", primary=True), action("turn-off", "Turn off in lumen-api"),
                        SHOW]})
        server = "claude.ai Google Drive"
        self.assertEqual(rows["Google Drive"]["properties"]["lines"],
                         [["From", "claude.ai", "Account"], ["Used", "2 times in this chat", None]])
        self.assertEqual(rows["Google Drive"]["properties"]["actions"],
                         [action("turn-off", "Turn off in lumen-api", primary=True), action("sign-out", "Sign out"),
                          SHOW])
        server = "claude.ai Notion"
        self.assertEqual(rows["Notion"]["properties"]["actions"],
                         [action("turn-on", "Turn on in lumen-api", primary=True), SHOW])
        self.assertEqual(rows["harbor-api"]["properties"]["lines"],
                         [["From", ".mcp.json", "Project"], ["URL", "api.harbor.dev/mcp", None]])
        self.assertEqual(rows["harbor-api"]["properties"]["actions"],
                         [action("open", "Open .mcp.json", mcp, True), SHOW])
        server = "sentry"
        self.assertEqual(rows["sentry"]["properties"]["actions"],
                         [action("retry", "Retry", primary=True), action("open", "Open .mcp.json", mcp), SHOW])
        server = "Dropbox"
        self.assertEqual(rows["Dropbox"]["properties"]["actions"], [action("retry", "Retry", primary=True), SHOW])
        server = "tidepool-db"
        self.assertEqual(rows["tidepool-db"]["properties"]["lines"],
                         [["From", "~/.claude.json", "Local"], ["Runs", "tidepool-mcp", None]])
        self.assertEqual(rows["tidepool-db"]["properties"]["actions"],
                         [action("turn-off", "Turn off in lumen-api", primary=True), SHOW])
        self.assertEqual(found["head"]["problems"],
                         [{"text": "1 sign in", "tone": "warn", "row": "connector:claude.ai Box"}])
        self.assertEqual(found["connect"], {
            "state": {"text": "signing in", "tone": "busy"}, "words": "Finish in your browser",
            "actions": [{"id": "reopen", "label": "Open the page again"}, {"id": "cancel", "label": "Cancel"}],
            "needs": {"turn-off": "Start a chat in lumen-api to turn it off",
                      "turn-on": "Start a chat in lumen-api to turn it on"},
            "add": {"tip": "Add a connector", "title": "Add a connector", "menu": [
                {"id": "claude-ai", "label": "From claude.ai…", "url": "https://claude.ai/settings/connectors"},
                {"id": "url", "label": "By URL…", "url": None}],
                "fields": {"name": "Name", "url": "URL", "scope": "For"},
                "scopes": [{"id": "local", "label": "lumen-api"}, {"id": "user", "label": "All projects"}],
                "submit": "Add and connect", "cancel": "Cancel"}})

    def test_nothing_set_up_is_claudes_defaults_and_an_empty_connectors_section(self):
        found = self.layers()
        self.assertEqual(found["sections"][1:], [{"id": "connectors", "title": "Connectors", "count": 0,
                                                  "tokens": None, "cost": None, "swatch": "connectors", "summary": [],
                                                  "rows": [], "groups": []}])
        # the mode and the sandbox no file sets: Claude's own default, a way in to set them, no file to open
        permissions = found["sections"][0]
        self.assertEqual((permissions["id"], permissions["summary"], permissions["groups"]), ("permissions", [], []))
        self.assertEqual([(r["id"], r["name"], r["note"], r["tag"], r["dim"], r["properties"]["lines"],
                           r["properties"]["actions"]) for r in permissions["rows"]], [
            ("mode", "Mode", "Manual", "Default", False, [["From", "Claude's default", None]], []),
            ("sandbox", "Sandbox", "off", "Default", False, [["From", "Claude's default", None]], [])])
        self.assertEqual(found["bar"], [{"part": "rules", "tokens": 0, "share": 0},
                                        {"part": "skills", "tokens": 0, "share": 0},
                                        {"part": "connectors", "tokens": 0, "share": 0}])
        # no chat yet: what it starts with estimated from what loads at start, no model nor window known
        self.assertEqual(found["head"], {"name": "Claude", "where": "in lumen-api", "model": None, "runs": None,
                                         "effort": None,
                                         "starts": 0, "measured": False, "window": None, "line": "starts at ~0",
                                         "problems": []})
        self.assertIsNone(found["error"])

    def test_the_conflict_row_stands_for_the_rule_it_hides(self):
        found = self.layers(session=self.lumen())
        permissions = self.section(found, "permissions")
        self.assertEqual(permissions["summary"], [{"text": "12 allow", "tone": "allow"},
                                                  {"text": "3 ask", "tone": "ask"}, {"text": "2 deny", "tone": "deny"}])
        rows = permissions["rows"][2:]              # after the mode and the sandbox
        user = os.path.join(self.home, ".claude", "settings.json")
        project = os.path.join(self.folder, ".claude", "settings.json")
        self.assertEqual(rows[0], {
            "id": "conflict:allow:Bash(git push:*)", "icon": "shield", "name": "Bash(git push:*)",
            "note": "deny in Project hides allow in Global", "tag": None, "mark": "warn", "state": None,
            "brand": None, "tokens": None, "cost": None, "agents": ["claude"], "dim": False,
            "properties": {
                "title": "Bash(git push:*)", "state": None,
                "lines": [["Allow", "Bash(git push:*)", "Global"], ["Deny", "Bash(git push:*)", "Project"]],
                "text": None, "error": None, "tip": None, "actions": [
                    # the two files hold a settings.json each: each named by where it is
                    {"id": "open", "label": "Open .claude/settings.json", "path": project, "server": None,
                     "primary": True},
                    {"id": "open", "label": "Open ~/.claude/settings.json", "path": user, "server": None,
                     "primary": False}]}})
        # then every rule in Claude's order, the one it hides not again
        self.assertEqual(len(rows), 17)
        self.assertEqual([(r["name"], r["state"], r["tag"], r["mark"]) for r in rows[1:3] + rows[11:15]], [
            ("Bash(npm test)", {"text": "allow", "tone": "allow"}, "Global", None),
            ("Bash(npm run lint)", {"text": "allow", "tone": "allow"}, "Global", None),
            ("Grep", {"text": "allow", "tone": "allow"}, "Global", None),
            ("Bash(git push:*)", {"text": "deny", "tone": "deny"}, "Project", None),
            ("Bash(rm -rf *)", {"text": "deny", "tone": "deny"}, "Project", None),
            ("Bash(git commit *)", {"text": "ask", "tone": "ask"}, "Local", None)])
        self.assertEqual(rows[1]["id"], "permission:allow:Bash(npm test)")
        self.assertEqual(rows[1]["properties"], {
            "title": "Bash(npm test)", "state": {"text": "allow", "tone": "allow"},
            "lines": [["From", "~/.claude/settings.json", "Global"]], "text": None, "error": None, "tip": None,
            "actions": [{"id": "open", "label": "Open settings.json", "path": user, "server": None, "primary": True}]})

    def test_each_kinds_properties(self):
        found = self.layers(session=self.lumen())
        rules, skills = self.section(found, "rules"), self.section(found, "skills")
        open_ = lambda label, path: {"id": "open", "label": label, "path": path, "server": None,  # noqa: E731
                                     "primary": True}
        self.assertEqual(rules["rows"][0]["properties"]["lines"], [["From", "~/.claude/CLAUDE.md", "Global"]])
        # a rule: where it is, its first lines (no front matter, no blank line, as text, each cut)
        self.assertEqual(rules["rows"][1]["properties"], {
            "title": "CLAUDE.md", "state": None, "lines": [["From", "CLAUDE.md", "Project"]],
            "text": "# lumen-api\nRoutes live in src/lumen/routes.\nEvery route answers JSON.", "error": None,
            "tip": None, "actions": [open_("Open CLAUDE.md", self.rule_files["project"]), SHOW]})
        self.assertEqual(rules["rows"][3]["properties"], {
            "title": "api.md", "state": None,
            "lines": [["From", ".claude/rules/api.md", "Project"], ["Paths", "src/lumen/**", None]],
            "text": "# Routes\nEach route answers JSON.\n" + "w" * 119 + "…", "error": None, "tip": None,
            "actions": [open_("Open api.md", self.rule_files["api"]), SHOW]})
        # a skill: its description, used in the open chat
        routes = self.chosen(skills, "api-routes")["properties"]
        self.assertEqual(routes["lines"], [["From", ".claude/skills/routes/SKILL.md", "Project"],
                                           ["Used", "in this chat", None]])
        self.assertEqual(routes["text"][:35], "How lumen-api's routes are written.")
        self.assertEqual(routes["actions"], [open_("Open SKILL.md", os.path.join(
            self.folder, ".claude", "skills", "routes", "SKILL.md")), SHOW])
        # a subagent: its model and tools
        agents = self.section(found, "subagents")
        reviewer = os.path.join(self.home, ".claude", "plugins", "cache", "market", "pr-review", "1.0", "agents",
                                "code-reviewer.md")
        self.assertEqual(self.chosen(agents, "code-reviewer")["properties"], {
            "title": "code-reviewer", "state": None,
            "lines": [["From", "pr-review", "Plugin"], ["Model", "sonnet", None], ["Tools", "Read, Grep", None]],
            "text": "Reviews a pull request", "error": None, "tip": None,
            "actions": [open_("Open code-reviewer.md", reviewer), SHOW]})
        # a permission is a gate on the graph's edges, no node of its own: no way there from its row
        self.assertNotIn("graph", [one["id"] for row in self.section(found, "permissions")["rows"]
                                   for one in row["properties"]["actions"]])
        # a server: where it is, what it runs, its error, Retry and its file
        connectors = self.section(found, "connectors")
        self.assertEqual(self.chosen(connectors, "sentry")["properties"], {
            "title": "sentry", "state": {"text": "failed", "tone": "bad"},
            "lines": [["From", ".mcp.json", "Project"], ["Runs", "npx -y @sentry/mcp-server", None]],
            "text": None, "error": "spawn npx ENOENT: npx is not on this machine's PATH", "tip": None, "actions": [
                {"id": "retry", "label": "Retry", "path": None, "server": "sentry", "primary": True},
                {"id": "open", "label": "Open .mcp.json", "path": os.path.join(self.folder, ".mcp.json"),
                 "server": None, "primary": False}, SHOW]})
        self.assertEqual(self.chosen(connectors, "figma")["properties"]["lines"],
                         [["From", "figma", "Plugin"], ["URL", "mcp.figma.com/mcp", None]])
        self.assertEqual(self.chosen(connectors, "chrome-devtools")["properties"]["lines"], [
            ["From", "~/.claude.json", "Global"], ["Runs", "npx chrome-devtools-mcp@latest", None],
            ["Used", "once in this chat", None]])

    def test_codex_rows_have_none_of_claudes_own_actions(self):
        self.programs({"claude": {}, "codex": {"mcp list --json": [json.dumps([
            {"name": "sentry", "enabled": True, "transport": {"type": "stdio", "command": "npx",
                                                              "args": ["-y", "@sentry/mcp-server"]}},
            {"name": "linear", "enabled": True, "auth_status": "not_logged_in",
             "transport": {"type": "streamable_http", "url": "https://mcp.linear.app/mcp"}},
            {"name": "notion", "enabled": False, "transport": {"type": "streamable_http",
                                                               "url": "https://mcp.notion.com/mcp"}},
            {"name": "figma", "enabled": True, "auth_status": "o_auth",
             "transport": {"type": "streamable_http", "url": "https://mcp.figma.com/mcp"}}]), "", 0]}})
        mine = self.put(self.codex_home("AGENTS.md"), "Mine")
        here = self.put(os.path.join(self.folder, "AGENTS.md"), "lumen-api")
        rules = self.put(self.codex_home("rules", "default.rules"), 'prefix_rule(pattern=["git", "push"])\n'
                         'prefix_rule(pattern=["git"], decision="prompt")\n')
        found = self.layers("codex")
        self.assertEqual((found["head"]["name"], found["head"]["where"]), ("Codex", "in lumen-api"))
        self.assertEqual([s["id"] for s in found["sections"]], ["rules", "permissions", "connectors"])
        self.assertEqual([(r["name"], r["tag"], r["agents"], r["properties"]["lines"])
                          for r in self.section(found, "rules")["rows"]], [
            ("~/.codex/AGENTS.md", "Global", ["codex"], [["From", "~/.codex/AGENTS.md", "Global"]]),   # not two
            ("AGENTS.md", "Project", ["claude", "codex"], [["From", "AGENTS.md", "Project"]])])
        self.assertEqual(self.section(found, "rules")["rows"][0]["properties"]["actions"][0]["path"], mine)
        self.assertEqual(self.section(found, "rules")["rows"][1]["properties"]["actions"][0]["path"], here)
        # a behavior with no rule is not counted aloud
        self.assertEqual(self.section(found, "permissions")["summary"],
                         [{"text": "1 allow", "tone": "allow"}, {"text": "1 ask", "tone": "ask"}])
        permissions = self.section(found, "permissions")["rows"]
        self.assertEqual([(r["name"], r["note"], r["state"]) for r in permissions], [
            ("Approval", "Codex's default", None), ("Sandbox", "Codex's default", None),
            ("git push", "ask in Global hides allow in Global", None),
            ("git", None, {"text": "ask", "tone": "ask"})])
        self.assertEqual(permissions[3]["properties"]["actions"][0]["label"], "Open default.rules")
        self.assertEqual(permissions[3]["properties"]["actions"][0]["path"], rules)
        config = self.codex_home("config.toml")
        connectors = self.section(found, "connectors")["rows"]
        self.assertEqual([(r["name"], r["state"], r["dim"], r["properties"]["actions"]) for r in connectors], [
            ("linear", {"text": "sign in", "tone": "warn"}, False, [
                {"id": "connect", "label": "Connect", "path": None, "server": "linear", "primary": True},
                {"id": "open", "label": "Open config.toml", "path": config, "server": None, "primary": False},
                SHOW]),
            ("sentry", {"text": "on", "tone": "ok"}, False, [
                {"id": "open", "label": "Open config.toml", "path": config, "server": None, "primary": True}, SHOW]),
            ("notion", {"text": "off", "tone": "off"}, True, [
                {"id": "open", "label": "Open config.toml", "path": config, "server": None, "primary": True}, SHOW]),
            # signed in through Codex's own OAuth: its own sign-out, never Claude's Turn off
            ("figma", {"text": "on", "tone": "ok"}, False, [
                {"id": "sign-out", "label": "Sign out", "path": None, "server": "figma", "primary": True},
                {"id": "open", "label": "Open config.toml", "path": config, "server": None, "primary": False},
                SHOW])])
        # what a sign-in and the add form say, in both clients' words: Codex adds for every folder, by its address
        self.assertEqual(found["connect"]["add"]["menu"], [{"id": "url", "label": "By URL…", "url": None}])
        self.assertEqual(found["connect"]["add"]["scopes"], [])
        self.assertEqual(connectors[0]["properties"]["lines"],
                         [["From", "~/.codex/config.toml", "Global"], ["URL", "mcp.linear.app/mcp", None]])
        self.assertEqual(found["head"]["problems"],
                         [{"text": "1 sign in", "tone": "warn", "row": "connector:linear"}])

    def test_servers_codex_could_not_list_are_not_read_never_none(self):
        self.programs({"claude": {}, "codex": {"mcp list --json": ["", "Error: config.toml: invalid", 1]}})
        section = self.section(self.layers("codex"), "connectors")
        self.assertIsNone(section["count"])                 # not "0": how many it has is not known
        row, = section["rows"]
        state = {"text": "not read", "tone": "off"}
        self.assertEqual((row["id"], row["name"], row["state"], row["dim"]),
                         ("unread:connectors", "Codex's servers", state, True))
        self.assertEqual(row["properties"], {
            "title": "Connectors", "state": state, "lines": [], "error": None, "tip": None, "actions": [],
            "text": "`codex mcp list` gave no list, so which servers Codex has is not known here."})

    def test_codexs_approval_policy_leads_its_permissions(self):
        # config.toml's top level, in the graph's words; read only: Open is its one action, as a rule's
        log = self.programs({"claude": {}, "codex": {"mcp list --json": ["[]", "", 0]}})
        self.put(self.codex_home("rules", "default.rules"), 'prefix_rule(pattern=["git", "push"])\n'
                 'prefix_rule(pattern=["git"], decision="prompt")\n')
        config = self.put(self.codex_home("config.toml"), 'approval_policy = "on-request"\n\n[tui]\n'
                          'approval_policy = "never"\n\n[mcp_servers.sentry.env]\nSENTRY_TOKEN = "invented"\n')
        self.assertEqual(agent_setup.codex_permissions(self.home)["mode"], "on-request")
        before = {path: text for path, text in self.files().items() if path != log}
        found = self.layers("codex")
        section = self.section(found, "permissions")
        self.assertEqual([(r["id"], r["name"], r["note"], r["state"]) for r in section["rows"]], [
            ("approval", "Approval", "Ask on request", None), ("sandbox", "Sandbox", "Codex's default", None),
            ("conflict:allow:git push", "git push", "ask in Global hides allow in Global", None),
            ("permission:ask:git", "git", None, {"text": "ask", "tone": "ask"})])
        row = section["rows"][0]
        self.assertEqual((row["icon"], row["tag"], row["mark"], row["dim"], row["agents"]),
                         ("shield", "Global", None, False, ["codex"]))
        self.assertEqual(row["properties"], {
            "title": "Approval", "state": None, "lines": [["From", "~/.codex/config.toml", "Global"]],
            "text": None, "error": None, "tip": None,
            "actions": [{"id": "open", "label": "Open config.toml", "path": config, "server": None,
                         "primary": True}]})
        # no count after the title; the head's words stay the rules' by behavior
        self.assertEqual((section["count"], section["summary"]),
                         (None, [{"text": "1 allow", "tone": "allow"}, {"text": "1 ask", "tone": "ask"}]))
        self.assertNotIn("invented", json.dumps(found))
        self.assertEqual({path: text for path, text in self.files().items() if path != log}, before)
        for policy, words in (("untrusted", "Ask unless trusted"), ("on-failure", "Ask on failure"),
                              ("never", "Never ask")):
            self.put(config, f"approval_policy = '{policy}'\n")
            self.assertEqual(self.section(self.layers("codex"), "permissions")["rows"][0]["note"], words)
        # with no rule the policy and the sandbox are the section
        os.remove(self.codex_home("rules", "default.rules"))
        alone = self.section(self.layers("codex"), "permissions")
        self.assertEqual(([r["id"] for r in alone["rows"]], alone["count"], alone["summary"]),
                         (["approval", "sandbox"], None, []))
        # a profile named, a policy with no word, none set: Codex's own default, a way in to set one
        for text in ('profile = "careful"\napproval_policy = "never"\n', 'approval_policy = "lumen-policy"\n', ""):
            with self.subTest(text):
                self.put(config, text)
                row = self.section(self.layers("codex"), "permissions")["rows"][0]
                self.assertEqual((row["id"], row["note"], row["tag"], row["properties"]["lines"],
                                  row["properties"]["actions"]),
                                 ("approval", "Codex's default", "Default", [["From", "Codex's default", None]], []))
        # the policy is Codex's: Claude's mode is its own default where no settings file names one
        self.put(config, 'approval_policy = "never"\n')
        self.settings("user", permissions={"allow": ["Read"]})
        self.assertEqual([(r["id"], r["note"], r["tag"]) for r in self.section(self.layers(), "permissions")["rows"]],
                         [("mode", "Manual", "Default"), ("sandbox", "off", "Default"),
                          ("permission:allow:Read", None, "Global")])

    def test_claudes_mode_leads_its_permissions(self):
        # the same row for Claude: the mode it starts in, where a settings file names one, in the chat's words
        self.programs({"claude": {}})
        user = self.settings("user", permissions={"allow": ["Read"], "defaultMode": "plan"})
        before = self.files()
        section = self.section(self.layers(), "permissions")
        self.assertEqual([(r["id"], r["name"], r["note"], r["state"]) for r in section["rows"]], [
            ("mode", "Mode", "Plan", None), ("sandbox", "Sandbox", "off", None),
            ("permission:allow:Read", "Read", None, {"text": "allow", "tone": "allow"})])
        row = section["rows"][0]
        self.assertEqual((row["icon"], row["tag"], row["mark"], row["dim"], row["agents"]),
                         ("shield", "Global", None, False, ["claude"]))
        self.assertEqual(row["properties"]["lines"], [["From", "~/.claude/settings.json", "Global"]])
        self.assertEqual([(a["id"], a["label"], a["path"]) for a in row["properties"]["actions"]],
                         [("open", "Open settings.json", user)])
        self.assertEqual(self.files(), before)                                   # read, never set
        # the file that wins tells it: the project's over the user's; a mode Claude has not is none told
        project = self.settings("project", permissions={"defaultMode": "acceptEdits"})
        row = self.section(self.layers(), "permissions")["rows"][0]
        self.assertEqual((row["note"], row["tag"], row["properties"]["actions"][0]["path"]),
                         ("Edit automatically", "Project", project))
        self.settings("project", permissions={"defaultMode": "everything"})
        self.assertEqual(self.section(self.layers(), "permissions")["rows"][0]["note"], "Plan")
        self.settings("user", permissions={"allow": ["Read"]})
        self.assertEqual([(r["id"], r["note"]) for r in self.section(self.layers(), "permissions")["rows"]],
                         [("mode", "Manual"), ("sandbox", "off"), ("permission:allow:Read", None)])

    def test_what_is_turned_off_in_this_folder_stays_a_row_off_here(self):
        """A skill, a subagent and a connector the settings files turn off (the keys harness.py's forms write) are
        dim rows that say so; with disableAllHooks the Hooks group stays, off here, its hooks dim."""
        self.programs({"claude": {}})
        self.put(os.path.join(self.home, ".claude", "skills", "notes", "SKILL.md"),
                 "---\nname: release-notes\ndescription: when you ask for notes\n---\n")
        self.put(os.path.join(self.folder, ".claude", "skills", "routes", "SKILL.md"), "---\nname: api-routes\n---\n")
        self.agent_file(os.path.join(self.folder, ".claude", "agents"), "docs.md", name="doc-checker",
                        description="Checks the docs")
        self.claude_json(mcpServers={"github": {"type": "http", "url": "https://mcp.github.example/mcp"}})
        hook = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "./scripts/guard.sh"}]}]}
        self.settings("user", hooks=hook)
        session = self.session("a1", self.listing([("Explore", "Fast search (Tools: Read)")], ["Explore"],
                                                  initial=True))
        self.settings("local", skillOverrides={"release-notes": "off"}, disableAllHooks=True,
                      deniedMcpServers=[{"serverName": "github"}],
                      permissions={"deny": ["Agent(doc-checker)", "Agent(Explore)"]})
        found = self.layers(session=session)
        off = {"text": "off here", "tone": "off"}
        skills, agents = self.section(found, "skills"), self.section(found, "subagents")
        self.assertEqual([(r["name"], r["state"], r["dim"], r["properties"]["state"]) for r in skills["rows"]],
                         [("release-notes", off, True, off), ("api-routes", None, False, None)])
        # what is off loads nothing at start: out of the section's cost and the bar
        self.assertEqual((skills["tokens"], found["bar"][1]["tokens"]), (2, 2))
        self.assertEqual([(r["name"], r["state"], r["dim"]) for r in agents["rows"]],
                         [("doc-checker", off, True), ("Explore", None, False)])
        self.assertEqual((agents["rows"][1]["off"], agents["rows"][1]["properties"]["lines"][1]),
                         (["Explore"], ["Explore", "read-only", "off here"]))
        server = self.chosen(self.section(found, "connectors"), "github")
        self.assertEqual((server["state"], server["dim"], server["properties"]["actions"][0]["label"]),
                         (off, True, "Turn on in lumen-api"))
        [group] = self.section(found, "permissions")["groups"]
        self.assertEqual((group["count"], group["state"], [(r["name"], r["dim"]) for r in group["rows"]]),
                         (1, off, [("guard.sh", True)]))
        self.settings("local")
        found = self.layers(session=session)
        self.assertEqual([r["dim"] for key in ("skills", "subagents", "connectors") for r in self.section(
            found, key)["rows"]], [False] * 5)
        self.assertIsNone(self.section(found, "permissions")["groups"][0]["state"])

    def test_the_cli_prints_the_layers(self):
        self.programs({"claude": {}})
        session = self.lumen()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_layers_cli.main(["agent_layers_cli.py", "claude", self.folder, session]), 0)
            self.assertEqual(agent_layers_cli.main(["agent_layers_cli.py", "codex", self.folder]), 0)
        claude, codex = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(sorted(claude), ["agent", "bar", "connect", "error", "folder", "head", "sections", "states"])
        self.assertEqual((claude["agent"], claude["folder"]), ("claude", self.folder))
        self.assertEqual([r["mark"] for r in self.section(claude, "skills")["rows"]], [None, "ok"])
        self.assertIsNone(codex)                    # no Codex here
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in (["gemini", self.folder], ["codex", self.folder, session], ["claude"],
                         ["layers", "claude", self.folder]):
                self.assertEqual(agent_layers_cli.main(["agent_layers_cli.py"] + argv), 2)

    def test_a_checked_server_shows_claudes_answer_until_its_state_changes(self):
        """The app keeps check()'s answer with the state the server had then: the next read shows it over that state
        alone, the server first among the problems, its own state told beside."""
        self.programs({"claude": {}})
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        self.settings("local", enabledMcpjsonServers=["sentry"])

        def read(*more):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(agent_layers_cli.main(["agent_layers_cli.py", "claude", self.folder, *more]), 0)
            found = json.loads(out.getvalue())
            return found["states"], self.section(found, "connectors")["rows"][0], found["head"]["problems"]

        said = {"sentry": {"base": "not checked", "state": "failed", "error": "spawn npx ENOENT\x1b[0m"}}
        self.assertEqual(read()[0], {"sentry": "not checked"})
        states, row, problems = read("--checked", json.dumps(said))
        self.assertEqual(states, {"sentry": "not checked"})         # its own state, what the next check starts from
        self.assertEqual((row["name"], row["state"], row["properties"]["error"]),
                         ("sentry", {"text": "failed", "tone": "bad"}, "spawn npx ENOENT"))
        self.assertEqual(problems, [{"text": "1 failed", "tone": "bad", "row": "connector:sentry"}])
        for stale in ({"sentry": {**said["sentry"], "base": "on"}}, {"sentry": {**said["sentry"], "state": "great"}},
                      {"sentry": "failed"}, ["sentry"]):
            self.assertEqual(read("--checked", json.dumps(stale))[1]["state"], {"text": "not checked", "tone": "off"})
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in (["claude", self.folder, "--checked", "{"], ["codex", self.folder, "--checked", "{}"]):
                self.assertEqual(agent_layers_cli.main(["agent_layers_cli.py"] + argv), 2)

    def answer_line(self, model="claude-opus-5-5", side=False, **usage):
        """The assistant line of an answer by MODEL, its USAGE (SIDE: a subagent's, in the main file)."""
        return self.line(type="assistant", isSidechain=side, message={
            "id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": [],
            "usage": {"input_tokens": 4, "output_tokens": 30, **usage}})

    def test_the_bash_sandbox_and_its_hosts(self):
        self.assertIsNone(agent_setup.sandbox(self.folder, self.home))
        user = self.settings("user", sandbox={"network": {"allowedDomains": ["pypi.org"]}},
                             permissions={"allow": ["WebFetch(domain:docs.lumen.dev)", "Read"]})
        self.assertIsNone(agent_setup.sandbox(self.folder, self.home))            # hosts, but not turned on
        project = self.settings("project", sandbox={"enabled": True, "network": {"allowedDomains": [
            "github.com", "pypi.org", 3]}})
        self.assertEqual(agent_setup.sandbox(self.folder, self.home), {
            "on": True, "scope": "Project", "path": project, "hosts": ["pypi.org", "docs.lumen.dev", "github.com"]})
        self.settings("local", sandbox={"enabled": False})
        self.assertEqual(agent_setup.sandbox(self.folder, self.home)["on"], False)
        found = self.section(self.layers(), "permissions")["rows"]
        self.assertEqual([(r["id"], r["name"], r["note"], r["tag"]) for r in found[:2]],
                         [("mode", "Mode", "Manual", "Default"), ("sandbox", "Sandbox", "off", "Local")])
        self.settings("local", sandbox={"enabled": True})
        row = self.section(self.layers(), "permissions")["rows"][1]
        self.assertEqual((row["note"], row["properties"]["lines"]), ("Bash · 3 hosts", [
            ["From", ".claude/settings.local.json", "Local"], ["Hosts", "pypi.org, docs.lumen.dev, github.com", None]]))
        self.assertTrue(os.path.isfile(user))

    def test_the_hooks_group_closes_permissions_the_gates_first(self):
        session = self.session("0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e", json.dumps({"type": "user"}))
        self.put(os.path.join(self.home, ".local", "state", "herdr-fold", "chat",
                              "0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e", "status.json"), "{}")
        project = self.settings("project", permissions={"allow": ["Read"]}, hooks={
            "Stop": [{"hooks": [{"type": "command", "command": "notify.sh"}]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": "context.sh"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "./scripts/guard.sh"}]}]})
        section = self.section(self.layers(session=session), "permissions")
        self.assertEqual([r["id"] for r in section["rows"]], ["mode", "sandbox", "permission:allow:Read"])
        [group] = section["groups"]
        self.assertEqual((group["id"], group["title"], group["count"], group["state"]), ("hooks", "Hooks", 4, None))
        # herdr-fold's own, passed with its chat: there where the open chat is one of its
        self.assertEqual([(r["name"], r["note"], r["state"], r["tag"]) for r in group["rows"]], [
            ("guard.sh", "on PreToolUse · Bash", {"text": "hook", "tone": "muted"}, "Project"),
            ("herdr-fold", "on PermissionRequest", {"text": "hook", "tone": "muted"}, "herdr-fold"),
            ("notify.sh", "on Stop", {"text": "hook", "tone": "muted"}, "Project"),
            ("context.sh", "SessionStart · adds context", {"text": "hook", "tone": "muted"}, "Project")])
        self.assertEqual(group["rows"][0]["properties"]["lines"], [
            ["On", "PreToolUse · Bash", None], ["From", ".claude/settings.json", "Project"],
            ["Runs", "./scripts/guard.sh", None]])
        self.assertEqual([(a["id"], a["label"], a["path"]) for a in group["rows"][0]["properties"]["actions"]],
                         [("open", "Open settings.json", project), ("graph", "Show in graph", None)])
        self.assertEqual(group["rows"][1]["properties"]["lines"], [["On", "PermissionRequest", None],
                                                                  ["From", "this chat's settings", "herdr-fold"]])
        self.assertEqual(self.section(self.layers(), "permissions")["groups"][0]["count"], 3)    # another chat's

    def test_a_rules_imports_load_with_it(self):
        global_rule = self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "Mine. @~/notes/style.md")
        style = self.put(os.path.join(self.home, "notes", "style.md"), "s" * 400 + "\n" + "@deeper.md")
        deeper = self.put(os.path.join(self.home, "notes", "deeper.md"), "d" * 40)
        here = self.put(os.path.join(self.folder, "CLAUDE.md"), "See @docs/api.md and @missing.md, mail "
                        "dev@example.com.\n"
                        "```\n@docs/never.md\n```\nNot `@docs/never.md` either. Again: @~/notes/style.md")
        api = self.put(os.path.join(self.folder, "docs", "api.md"), "a" * 800)
        self.put(os.path.join(self.folder, "docs", "never.md"), "inside code: never read")
        found = agent_setup.rules(self.folder, self.home)
        self.assertEqual([(r["path"], r["scope"], r["via"], r["paths"]) for r in found], [
            (global_rule, "Global", None, []), (style, "Global", global_rule, []), (deeper, "Global", style, []),
            (here, "Project", None, []), (api, "Project", here, [])])
        rules = self.section(self.layers(), "rules")
        # they load at start: counted, their cost in the section's and the bar's
        self.assertEqual((rules["count"], rules["tokens"]), (5, sum(r["tokens"] for r in found)))
        self.assertEqual([(r["name"], r["note"]) for r in rules["rows"]][1:3], [
            ("~/notes/style.md", "imported by ~/.claude/CLAUDE.md"),
            ("~/notes/deeper.md", "imported by ~/notes/style.md")])
        self.assertEqual(rules["rows"][4]["properties"]["lines"], [["From", "docs/api.md", "Project"],
                                                                  ["Imported by", "CLAUDE.md", None]])
        # a path-scoped rule's imports load with it alone
        self.put(os.path.join(self.folder, ".claude", "rules", "db.md"), '---\npaths: "src/db/**"\n---\n@../../db.md')
        notes = self.put(os.path.join(self.folder, "db.md"), "n" * 80)
        self.assertEqual(next(r["paths"] for r in agent_setup.rules(self.folder, self.home) if r["path"] == notes),
                         ["src/db/**"])

    def test_the_head_says_the_model_effort_and_what_the_newest_chat_started_from(self):
        self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "x" * 4000)
        self.session("old", self.answer_line("claude-sonnet-5-5", cache_read_input_tokens=9000), age=60)
        newest = self.session("new", json.dumps({"type": "user"}),
                              self.answer_line(side=True, input_tokens=50),
                              self.answer_line(input_tokens=200, cache_creation_input_tokens=30000,
                                               cache_read_input_tokens=4000),
                              self.answer_line(input_tokens=9, cache_read_input_tokens=99000))
        self.assertEqual(agent_setup.first_turn("claude", newest),
                         {"tokens": 34200, "model": "claude-opus-5-5", "window": None, "effort": None})
        self.settings("user", effortLevel="low", modelSettings={"claude-opus-5-5": {"effortLevel": "high"}})
        head = self.layers()["head"]
        self.assertEqual(head["runs"], "claude-opus-5-5")           # the id a form's effort is kept under
        window = agent_setup.words.window("claude-opus-5-5")
        self.assertEqual((head["model"], head["effort"], head["starts"], head["measured"], head["window"]),
                         ("Opus 5.5", "High", 34200, True, window))
        self.assertEqual(head["line"], f"Opus 5.5 · High · starts at 34.2k of {window // 1000000}M")
        # an alias as the chat ran it; another family, or a whole id, as the setting says
        self.settings("user", model="opus")
        self.assertEqual(self.layers()["head"]["model"], "Opus 5.5")
        self.settings("user", model="opus[1m]")
        self.assertEqual((self.layers()["head"]["model"], self.layers()["head"]["window"]), ("Opus 5.5", 1_000_000))
        self.settings("user", model="sonnet")
        self.assertEqual((self.layers()["head"]["model"], self.layers()["head"]["window"]), ("Sonnet", None))
        self.settings("user", model="claude-sonnet-4-5")
        self.assertEqual(self.layers()["head"]["line"], "Sonnet 4.5 · starts at 34.2k of 200k")
        # herdr-fold's chat keeps what its status line told: the window, the effort where no setting says one
        self.settings("user")
        chat = self.session("0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e", self.answer_line(input_tokens=21000))
        self.put(os.path.join(self.home, ".local", "state", "herdr-fold", "chat",
                              "0b9f6d1e-1c2a-4f3b-8d4e-5f6a7b8c9d0e", "status.json"),
                 json.dumps({"window": 500000, "effort": "xhigh", "model": "Opus 5.5"}))
        self.assertEqual(agent_setup.claude_setup(self.folder, self.home)["start"],
                         {"tokens": 21000, "model": "claude-opus-5-5", "window": 500000, "effort": "xhigh"})
        self.assertEqual(self.layers()["head"]["line"], "Opus 5.5 · Extra high · starts at 21.0k of 500k")
        # no chat in the folder: the estimate, what loads at start
        for path in (newest, chat, os.path.join(os.path.dirname(newest), "old.jsonl")):
            os.remove(path)
        self.assertEqual(self.layers()["head"]["line"], "starts at ~1.0k")

    def test_codexs_model_effort_sandbox_and_first_turn(self):
        self.programs({"codex": {"mcp list --json": ["[]", "", 0]}})
        config = self.put(self.codex_home("config.toml"), "\n".join([
            'model = "gpt-5.2-codex"', "model_reasoning_effort = 'high'  # thinks", 'sandbox_mode = "workspace-write"',
            'approval_policy = "on-request"', "", "[sandbox_workspace_write]",
            'writable_roots = ["/home/dev/cache", \'/home/dev/out\']', "network_access = false", "",
            "[tui]", 'model = "never read"', "[mcp_servers.sentry.env]", 'SENTRY_TOKEN = "invented"', ""]))
        self.assertEqual(agent_setup.codex_config(self.home), {
            "model": "gpt-5.2-codex", "model_reasoning_effort": "high", "sandbox_mode": "workspace-write",
            "approval_policy": "on-request",
            "sandbox_workspace_write": {"writable_roots": ["/home/dev/cache", "/home/dev/out"],
                                        "network_access": False},
            "tui": {"model": "never read"}, "mcp_servers.sentry.env": {"SENTRY_TOKEN": "invented"}})
        rollout = self.put(self.codex_home("sessions", "2026", "11", "20", "rollout-a.jsonl"), "\n".join(json.dumps(
            one) for one in [{"type": "session_meta", "payload": {"id": "a", "cwd": self.folder}},
                             {"type": "turn_context", "payload": {"model": "gpt-5.2-codex"}},
                             {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
                             {"type": "event_msg", "payload": {"type": "token_count", "info": {
                                 "last_token_usage": {"input_tokens": 9600, "cached_input_tokens": 9000},
                                 "model_context_window": 272000}}}]) + "\n")
        self.assertEqual(agent_setup.rollout(self.folder, self.home), rollout)
        found = self.layers("codex")
        self.assertEqual(found["head"]["line"], "GPT-5.2 Codex · High · starts at 9.6k of 272k")
        sandbox = self.section(found, "permissions")["rows"][1]
        self.assertEqual((sandbox["name"], sandbox["note"], sandbox["tag"]), ("Sandbox", "Workspace write", "Global"))
        self.assertEqual(sandbox["properties"]["lines"], [
            ["From", "~/.codex/config.toml", "Global"],
            ["Writes", "lumen-api, /tmp, /home/dev/cache, /home/dev/out", None], ["Network", "off", None]])
        self.assertEqual(sandbox["properties"]["actions"][0]["path"], config)
        self.assertNotIn("invented", json.dumps(found))
        # its hooks.json's hooks, Global
        hooks = self.put(self.codex_home("hooks.json"), json.dumps({"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "/home/dev/.codex/herdr-agent-state.sh start"}]}]}}))
        [group] = self.section(self.layers("codex"), "permissions")["groups"]
        self.assertEqual([(r["name"], r["note"], r["tag"], r["properties"]["actions"][0]["path"])
                          for r in group["rows"]], [("herdr-agent-state.sh", "SessionStart · adds context", "Global",
                                                     hooks)])

    def test_a_sub_agents_model_and_tools_in_a_few_words(self):
        said = lambda model, tools: agent_layers.subagent_said({"model": model, "tools": tools})     # noqa: E731
        self.assertEqual([said("opus", ["Read", "Edit", "Bash", "Grep"]), said("haiku", ["Read", "Grep", "Glob"]),
                          said("claude-sonnet-5-5", ["Read"]), said("inherit", ["Bash"]), said(None, []),
                          said("opus", [])],
                         ["Opus · 4 tools", "Haiku · read-only", "Sonnet 5.5 · read-only", "1 tool", None, "Opus"])

    def test_an_error_names_no_file_the_file_its_tip(self):
        self.assertEqual(agent_layers.apart("Failed to read '/home/dev/.mcp.json': EACCES"),
                         ("Failed to read: EACCES", "/home/dev/.mcp.json"))
        self.assertEqual(agent_layers.apart("spawn npx ENOENT"), ("spawn npx ENOENT", None))
        self.assertEqual(agent_layers.apart("/home/dev/bin/tool"), ("failed", "/home/dev/bin/tool"))
        self.assertEqual(agent_layers.apart(None), (None, None))
        settings = self.settings("user", permissions={"allow": ["Read"]})
        self.assertIsNone(self.layers()["error"])
        os.chmod(settings, 0)
        self.addCleanup(os.chmod, settings, 0o600)
        if os.access(settings, os.R_OK):
            self.skipTest("this user reads every file")
        self.assertEqual(self.layers()["error"], {"text": "Couldn't read Claude's setup: permission denied",
                                                  "tip": "~/.claude/settings.json"})


if __name__ == "__main__":
    unittest.main()
