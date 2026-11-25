"""Tests for core/agent_setup.py in a temporary home, folder and managed folder: Claude's rules, skills, mode,
permissions with their conflicts, subagents, MCP servers with their state and what a conversation used; Codex's setup
from a stand-in codex; nothing of theirs written."""
import contextlib
import io
import json
import os
import shutil
import sys
import unittest

from support import PACKAGE, AgentHome, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_setup    # noqa: E402


class AgentSetup(AgentHome, unittest.TestCase):
    def setup(self):
        return agent_setup.claude_setup(self.folder, self.home)

    def test_the_rules_come_with_their_scope_in_claudes_order(self):
        personal = self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "x" * 400)
        above = self.put(os.path.join(os.path.dirname(self.folder), "CLAUDE.md"), "Above")
        project = self.put(os.path.join(self.folder, "CLAUDE.md"), "Project")
        agents = self.put(os.path.join(self.folder, "AGENTS.md"), "Agents")
        api = self.put(os.path.join(self.folder, ".claude", "rules", "api.md"),
                       "---\npaths:\n  - \"src/lumen/**\"\n  - tests/**\n---\nRoutes")
        style = self.put(os.path.join(self.folder, ".claude", "rules", "style.md"), "---\npaths: \"**/*.css\"\n---\n")
        local = self.put(os.path.join(self.folder, "CLAUDE.local.md"), "Mine")
        found = self.setup()["rules"]
        self.assertEqual([(r["path"], r["scope"]) for r in found],
                         [(personal, "Global"), (above, "Project"), (project, "Project"), (agents, "Project"),
                          (api, "Project"), (style, "Project"), (local, "Local")])
        self.assertEqual(found[0]["tokens"], 100)
        self.assertEqual({r["path"]: r["paths"] for r in found if r["paths"]},
                         {api: ["src/lumen/**", "tests/**"], style: ["**/*.css"]})

    def test_a_rule_reached_twice_is_listed_once(self):
        self.put(os.path.join(self.folder, "CLAUDE.md"), "Project")
        os.symlink(os.path.join(self.folder, "CLAUDE.md"), os.path.join(self.folder, "AGENTS.md"))
        self.assertEqual([os.path.basename(r["path"]) for r in self.setup()["rules"]], ["CLAUDE.md"])

    def test_a_skill_has_its_front_matters_name_and_description_or_its_folders_name(self):
        self.put(os.path.join(self.folder, ".claude", "skills", "routes", "SKILL.md"),
                 "---\nname: api-routes\ndescription: >\n  How lumen-api's routes\n  are written\n---\n# Routes")
        self.put(os.path.join(self.home, ".claude", "skills", "notes", "SKILL.md"), "# Just notes")
        self.put(os.path.join(self.home, ".claude", "skills", "empty", "README.md"), "not a skill")
        found = self.setup()["skills"]
        self.assertEqual([(s["name"], s["description"], s["scope"], s["source"]) for s in found],
                         [("notes", "", "Global", "Global"),
                          ("api-routes", "How lumen-api's routes are written", "Project", "Project")])
        self.assertEqual(found[1]["tokens"], round(len("api-routes" + found[1]["description"]) / 4))

    def test_an_enabled_plugins_skills_carry_its_name_a_disabled_ones_are_left_out(self):
        for name in ("design", "ops"):
            self.put(os.path.join(self.home, ".claude", "plugins", "cache", "market", name, "1.0", "skills", "look",
                                  "SKILL.md"), f"---\nname: {name}-look\ndescription: '{name} skill'\n---\n")
        self.put(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), json.dumps(
            {"version": 2, "plugins": {f"{name}@market": [
                {"scope": "user", "installPath": os.path.join(self.home, ".claude", "plugins", "cache", "market",
                                                              name, "1.0")}] for name in ("design", "ops")}}))
        self.put(os.path.join(self.home, ".claude", "settings.json"),
                 json.dumps({"enabledPlugins": {"design@market": True, "ops@market": True}}))
        self.put(os.path.join(self.folder, ".claude", "settings.local.json"),
                 json.dumps({"enabledPlugins": {"ops@market": False}}))
        before = self.files()
        self.assertEqual([(s["name"], s["description"], s["source"]) for s in self.setup()["skills"]],
                         [("design-look", "design skill", "design")])
        self.assertEqual(self.files(), before)

    def test_damaged_settings_and_unreadable_files_are_left_out(self):
        self.put(os.path.join(self.home, ".claude", "settings.json"), "{not json")
        self.put(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), "[1, 2]")
        os.makedirs(os.path.join(self.folder, "CLAUDE.md"))
        os.mkfifo(os.path.join(self.folder, "AGENTS.md"))
        self.assertEqual(self.setup(), {"model": None, "effort": None, "rules": [], "skills": [], "agents": [],
                                        "permissions": {"allow": 0, "ask": 0, "deny": 0, "mode": None, "rules": [],
                                                        "conflicts": []}, "sandbox": None, "hooks": [],
                                        "stopped": [],
                                        "off": {"skills": [], "agents": [], "servers": [], "hooks": False},
                                        "servers": [], "use": {"skills": {}, "servers": {}, "agents": {}},
                                        "start": {"tokens": None, "model": None, "window": None, "effort": None},
                                        "unread": []})

    def test_the_mode_claude_starts_in_is_the_last_settings_files_that_names_one(self):
        user = os.path.join(self.home, ".claude", "settings.json")
        project = os.path.join(self.folder, ".claude", "settings.json")
        local = os.path.join(self.folder, ".claude", "settings.local.json")
        self.assertIsNone(self.setup()["permissions"]["mode"])
        self.put(user, json.dumps({"permissions": {"defaultMode": "plan"}}))
        self.assertEqual(self.setup()["permissions"]["mode"], "plan")
        self.put(project, json.dumps({"permissions": {"defaultMode": "acceptEdits", "allow": []}}))
        self.put(local, json.dumps({"permissions": {"defaultMode": "everything"}}))    # no mode Claude has
        self.assertEqual(self.setup()["permissions"]["mode"], "acceptEdits")
        self.put(local, json.dumps({"permissions": {"defaultMode": "auto"}}))
        before = self.files()
        self.assertEqual(self.setup()["permissions"]["mode"], "auto")
        self.assertEqual(self.files(), before)
        for damaged in ({"permissions": ["plan"]}, {"permissions": {"defaultMode": 2}}):
            self.put(user, json.dumps(damaged))
            self.put(project, "{not json")
            self.put(local, "")
            self.assertIsNone(self.setup()["permissions"]["mode"])

    def permissions(self):
        return agent_setup.permissions(self.folder, self.home)

    def hidden(self):
        """Each conflict as {the rule it hides: the rule that hides it}."""
        return {c["hides"]["rule"]: c["rule"] for c in self.permissions()["conflicts"]}

    def test_each_rule_counts_once_by_its_behavior(self):
        user = self.settings("user", permissions={"allow": ["Bash(npm test)", "Read(src/**)", "Bash(npm test)"],
                                                  "ask": ["Bash(git commit *)"]})
        project = self.settings("project", permissions={"allow": ["Bash(npm test)"], "deny": ["WebFetch"]})
        local = self.settings("local", permissions={"allow": ["Bash(ls *)"], "defaultMode": "acceptEdits"})
        before = self.files()
        found = self.permissions()
        self.assertEqual({k: found[k] for k in ("allow", "ask", "deny", "mode", "conflicts")},
                         {"allow": 3, "ask": 1, "deny": 1, "mode": "acceptEdits", "conflicts": []})
        self.assertEqual(found["rules"], [
            {"rule": "Bash(npm test)", "behavior": "allow", "scope": "Global", "path": user},
            {"rule": "Read(src/**)", "behavior": "allow", "scope": "Global", "path": user},
            {"rule": "Bash(git commit *)", "behavior": "ask", "scope": "Global", "path": user},
            {"rule": "WebFetch", "behavior": "deny", "scope": "Project", "path": project},
            {"rule": "Bash(ls *)", "behavior": "allow", "scope": "Local", "path": local}])
        self.assertEqual(self.setup()["permissions"], found)
        self.assertEqual(self.files(), before)

    def test_a_deny_hides_the_allow_it_covers_and_says_where(self):
        user = self.settings("user", permissions={"allow": ["Bash(git push *)", "WebFetch(domain:docs.lumen.dev)",
                                                            "Read(src/**)"]})
        project = self.settings("project", permissions={"deny": ["Bash(git push *)", "WebFetch",
                                                                 "Read(src/secrets/**)"]})
        found = self.permissions()
        self.assertEqual(found["conflicts"][0], {
            "rule": "Bash(git push *)", "behavior": "deny", "scope": "Project", "path": project,
            "hides": {"rule": "Bash(git push *)", "behavior": "allow", "scope": "Global", "path": user},
            "text": "deny in Project hides allow in Global"})
        # a deny narrower than the allow is its exception, not a conflict
        self.assertEqual(self.hidden(), {"Bash(git push *)": "Bash(git push *)",
                                         "WebFetch(domain:docs.lumen.dev)": "WebFetch"})

    def test_an_ask_hides_the_allow_and_a_deny_the_ask_it_covers(self):
        self.settings("user", permissions={"allow": ["Edit(docs/*)"], "ask": ["Bash(rm -rf build)"]})
        self.settings("project", permissions={"deny": ["Bash(rm *)"]})
        self.settings("local", permissions={"ask": ["Edit(docs/**)"]})
        self.assertEqual([c["text"] for c in self.permissions()["conflicts"]],
                         ["ask in Local hides allow in Global", "deny in Project hides ask in Global"])

    def test_a_prefix_rule_covers_the_commands_it_starts(self):
        self.settings("user", permissions={
            "deny": ["Bash(git push:*)", "Bash(npm run *)", "Bash(docker * prune)", "Grep", "mcp__sentry",
                     "mcp__linear__*", "Read(src/*)", "Edit(build/**)"],
            "allow": ["Bash(git push origin main)", "Bash(git push)", "Bash(git push --force *)", "Bash(git pushx)",
                      "Bash(git status)", "Bash(npm run build)", "Bash(npm run)", "Bash(npm runner)",
                      "Bash(docker system prune)", "Grep(TODO)", "mcp__sentry__search_issues",
                      "mcp__linear__get_issue", "mcp__lineartools__get_issue", "Read(src/app.py)",
                      "Read(src/lumen/app.py)", "Read(src/**)", "Edit(build/lumen/out.js)"]})
        self.assertEqual(sorted(self.hidden().items()), sorted({
            "Bash(git push origin main)": "Bash(git push:*)", "Bash(git push)": "Bash(git push:*)",
            "Bash(git push --force *)": "Bash(git push:*)", "Bash(npm run build)": "Bash(npm run *)",
            "Bash(npm run)": "Bash(npm run *)", "Bash(docker system prune)": "Bash(docker * prune)",
            "Grep(TODO)": "Grep", "mcp__sentry__search_issues": "mcp__sentry",
            "mcp__linear__get_issue": "mcp__linear__*", "Read(src/app.py)": "Read(src/*)",
            "Edit(build/lumen/out.js)": "Edit(build/**)"}.items()))

    def test_managed_settings_count_with_their_scope(self):
        managed = self.settings("managed", permissions={"deny": ["Bash(curl *)"], "allow": ["Bash(npm test)"],
                                                        "defaultMode": "plan"})
        drop_in = self.put(os.path.join(self.managed, "managed-settings.d", "10-tidepool.json"),
                           json.dumps({"permissions": {"ask": ["WebFetch"]}}))
        self.put(os.path.join(self.managed, "managed-settings.d", "notes.txt"), json.dumps(
            {"permissions": {"ask": ["Bash"]}}))
        user = self.settings("user", permissions={"allow": ["Bash(curl lumen.dev)"], "defaultMode": "acceptEdits"})
        self.settings("local", permissions={"defaultMode": "auto"})
        found = self.permissions()
        self.assertEqual([(r["rule"], r["scope"], r["path"]) for r in found["rules"]],
                         [("Bash(npm test)", "Managed", managed), ("Bash(curl *)", "Managed", managed),
                          ("WebFetch", "Managed", drop_in), ("Bash(curl lumen.dev)", "Global", user)])
        self.assertEqual((found["allow"], found["ask"], found["deny"], found["mode"]), (2, 1, 1, "plan"))
        self.assertEqual([c["text"] for c in found["conflicts"]], ["deny in Managed hides allow in Global"])
        self.assertEqual(self.setup()["permissions"]["mode"], "plan")

    def test_sub_agents_from_each_place_with_model_and_tools(self):
        personal, project = os.path.join(self.home, ".claude", "agents"), os.path.join(self.folder, ".claude", "agents")
        writer = self.agent_file(personal, "docs.md", name="docs-writer",
                                 description=">\n  Writes the docs\n  of a change", tools=["Read", "Write"])
        self.agent_file(personal, "reviewer.md", name="reviewer", description="The user's reviewer", model="sonnet",
                        tools="Read, Grep, Glob")
        self.put(os.path.join(personal, "notes.txt"), "not an agent")
        migrations = self.agent_file(project, "migrations.md", name="migrations", description="Writes migrations")
        reviewer = self.agent_file(project, "reviewer.md", name="reviewer", description="lumen-api's reviewer",
                                   model="opus", tools='["Read", "Bash"]')
        roots = self.install("pr-review", "ops")
        plugin = self.agent_file(os.path.join(roots["pr-review"], "agents"), "code-reviewer.md", name="code-reviewer",
                                 description="'Reviews a pull request'", model="inherit", tools="[Read, Grep]")
        self.agent_file(os.path.join(roots["ops"], "agents"), "deploy.md", name="deploy", description="Deploys")
        self.settings("user", enabledPlugins={"pr-review@market": True, "ops@market": False})
        before = self.files()
        self.assertEqual(self.setup()["agents"], [
            {"name": "docs-writer", "description": "Writes the docs of a change", "model": None,
             "tools": ["Read", "Write"], "scope": "Global", "source": "Global", "path": writer, "off": False},
            # the user's reviewer is not listed: the project's of that name is the one Claude starts
            {"name": "migrations", "description": "Writes migrations", "model": None, "tools": [], "scope": "Project",
             "source": "Project", "path": migrations, "off": False},
            {"name": "reviewer", "description": "lumen-api's reviewer", "model": "opus", "tools": ["Read", "Bash"],
             "scope": "Project", "source": "Project", "path": reviewer, "off": False},
            {"name": "code-reviewer", "description": "Reviews a pull request", "model": "inherit",
             "tools": ["Read", "Grep"], "scope": "Global", "source": "pr-review", "path": plugin, "off": False}])
        self.assertEqual(self.files(), before)

    def test_built_in_agents_come_from_the_session_line(self):
        explore = ("Explore", "Fast read-only search (Tools: All tools except Edit, Write)")
        plan = ("Plan", "Plans an implementation (Tools: Read, Grep, Glob)")
        general = ("general-purpose", "Researches a question (Tools: *)")
        reviewer = ("pr-review:code-reviewer", "Reviews a pull request (Tools: All tools)")
        status = ("statusline-setup", "Sets up the status line (Tools: Read, Edit)")
        session = self.put(os.path.join(self.home, ".claude", "projects", "lumen", "a1.jsonl"), "\n".join([
            json.dumps({"type": "user", "message": {"role": "user", "content": "agent_listing_delta"}}),
            self.listing([explore, plan, general, reviewer], ["Explore", "Plan", "general-purpose"], initial=True),
            '{"type": "attachment", "attachment": {"type": "agent_listing_delta", "addedTypes": [',
            self.listing(removed=["Plan"]),
            self.listing([status], ["statusline-setup"])]) + "\n")
        self.agent_file(os.path.join(self.home, ".claude", "agents"), "general.md", name="general-purpose",
                        description="The user's own")
        before = self.files()
        found = agent_setup.agents(self.folder, self.home, session)
        self.assertEqual([(a["name"], a["scope"]) for a in found],
                         [("general-purpose", "Global"), ("Explore", "Built-in"), ("statusline-setup", "Built-in")])
        self.assertEqual(found[1], {"name": "Explore", "description": "Fast read-only search", "model": None,
                                    "tools": [], "scope": "Built-in", "source": "Claude", "path": None})
        self.assertEqual(found[2]["tools"], ["Read", "Edit"])
        self.assertEqual(agent_setup.claude_setup(self.folder, self.home, session)["agents"],
                         [{**one, "off": False} for one in found])
        self.assertEqual(self.files(), before)
        # a listing marked initial starts over (a compacted conversation's)
        again = self.put(os.path.join(self.home, ".claude", "projects", "lumen", "b2.jsonl"), "\n".join([
            self.listing([explore, plan], ["Explore", "Plan"], initial=True),
            self.listing([status], ["statusline-setup"]), self.listing([plan], ["Plan"], initial=True)]))
        self.assertEqual([a["name"] for a in agent_setup.agents(self.folder, self.home, again)],
                         ["general-purpose", "Plan"])
        self.assertEqual([a["name"] for a in agent_setup.agents(self.folder, self.home)], ["general-purpose"])

    def test_damaged_files_and_wrong_types_are_left_out(self):
        self.settings("user", permissions={"allow": "Bash", "ask": {"Bash": True}, "deny": [
            1, None, "", "  ", "Bash(", "Bash()", "(ls)", "Read(x)y", "Bash(ls\x1b[2J)", " WebFetch "]})
        self.settings("project", permissions=["allow"])
        self.put(os.path.join(self.folder, ".claude", "settings.local.json"), "{not json")
        os.makedirs(os.path.join(self.managed, "managed-settings.json"))
        personal = os.path.join(self.home, ".claude", "agents")
        self.put(os.path.join(personal, "plain.md"), "No front matter")
        self.agent_file(personal, "unnamed.md", description="No name")
        self.agent_file(personal, "silent.md", name="silent")
        self.agent_file(personal, "option.md", name="-rf", description="Like an option")
        self.agent_file(personal, "colon.md", name="a:b", description="A plugin's form")
        self.agent_file(personal, "typed.md", name="typed", description="A model of a wrong type",
                        model=["opus", "sonnet"])
        os.makedirs(os.path.join(personal, "folder.md"))
        os.mkfifo(os.path.join(personal, "pipe.md"))
        session = os.path.join(self.home, ".claude", "projects", "lumen", "c3.jsonl")
        os.makedirs(session)
        found = self.permissions()
        self.assertEqual([r["rule"] for r in found["rules"]], ["WebFetch"])
        self.assertEqual((found["allow"], found["ask"], found["deny"], found["mode"]), (0, 0, 1, None))
        self.assertEqual([(a["name"], a["model"], a["tools"]) for a in agent_setup.agents(self.folder, self.home,
                                                                                            session)],
                         [("typed", None, [])])

    def plugin_servers(self, name, servers, flat=False):
        """The plugin NAME installed and enabled for the user, SERVERS in its .mcp.json (FLAT: not under mcpServers,
        as some plugins keep it); the file's path."""
        root = self.install(name)[name]
        self.settings("user", enabledPlugins={f"{name}@market": True})
        return self.put(os.path.join(root, ".mcp.json"), json.dumps(servers if flat else {"mcpServers": servers}))

    def compacted(self):
        return self.line(type="system", subtype="compact_boundary", content="Conversation compacted", level="info",
                         logicalParentUuid="0a1c", compactMetadata={"trigger": "auto"})

    def servers(self, session=None):
        return agent_setup.server_rows(self.folder, self.home, agent_setup.use(session)["servers"])

    def by_name(self, *keys, session=None):
        """Each server's KEYS by its name."""
        return {s["name"]: tuple(s[key] for key in keys) for s in self.servers(session)}

    def test_each_place_names_its_servers_with_scope_and_source(self):
        config = self.claude_json(
            mcpServers={"Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"}},
            claudeAiMcpEverConnected=["claude.ai Google Drive"],
            projects={self.folder: {"mcpServers": {"tidepool-db": {"command": "tidepool-mcp"}}},
                      os.path.join(self.home, "harbor-web"): {"mcpServers": {"harbor": {"command": "harbor-mcp"}}}})
        project = self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]},
                                    Analytics={"type": "sse", "url": "https://mcp.lumen.dev/sse"})
        roots = self.install("figma", "ops")
        figma = self.put(os.path.join(roots["figma"], ".mcp.json"),
                         json.dumps({"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}))   # no mcpServers
        ops = self.put(os.path.join(roots["ops"], ".claude-plugin", "plugin.json"), json.dumps(
            {"name": "ops", "mcpServers": {"harbor-status": {"command": "node",
                                                             "args": ["${CLAUDE_PLUGIN_ROOT}/status.js"]}}}))
        self.settings("user", enabledPlugins={"figma@market": True, "ops@market": True})
        before = self.files()
        found = self.servers()
        # in Claude's /mcp order: the project's, the local ones, the user's, then claude.ai's and the plugins', each
        # by name
        self.assertEqual([(s["name"], s["label"], s["kind"], s["scope"], s["source"], s["path"]) for s in found], [
            ("Analytics", "Analytics", "sse", "Project", "Project", project),
            ("sentry", "sentry", "stdio", "Project", "Project", project),
            ("tidepool-db", "tidepool-db", "stdio", "Local", "Local", config),
            ("Dropbox", "Dropbox", "http", "Global", "Global", config),
            ("claude.ai Google Drive", "Google Drive", "claude.ai", "Account", "claude.ai", None),
            ("plugin:figma:figma", "figma", "http", "Global", "figma", figma),
            ("plugin:ops:harbor-status", "harbor-status", "stdio", "Global", "ops", ops)])
        self.assertEqual(self.setup()["servers"], found)
        self.assertEqual(self.files(), before)
        # the organization's managed-mcp.json, where there is one, is the only place Claude takes servers from
        managed = self.put(os.path.join(self.managed, "managed-mcp.json"), json.dumps(
            {"mcpServers": {"lumen-docs": {"type": "http", "url": "https://docs.lumen.dev/mcp"}}}))
        self.assertEqual([(s["name"], s["scope"], s["source"], s["path"]) for s in self.servers()],
                         [("lumen-docs", "Managed", "Managed", managed)])

    def test_a_server_shows_its_command_and_host_never_env_headers_or_query(self):
        self.claude_json(mcpServers={
            "Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp/?token=sl.abc123#lumen-frag",
                        "headers": {"Authorization": "Bearer sl.def456"}},
            "sentry": {"type": "stdio", "command": "npx", "args": ["-y", "@sentry/mcp-server", "--org", "lumen labs"],
                       "env": {"SENTRY_AUTH_TOKEN": "sntrys_ghi789"}},
            "figma-desktop": {"type": "sse", "url": "http://localhost:3845/sse"},
            "Notion": {"type": "streamable-http", "url": "https://mcp.notion.com/mcp"},
            "harbor": {"type": "ws", "url": "wss://lumen:hunter2@harbor.example.com"}})
        self.assertEqual(self.by_name("kind", "runs", "url"), {
            "Dropbox": ("http", None, "mcp.dropbox.com/mcp"),
            "sentry": ("stdio", "npx -y @sentry/mcp-server --org 'lumen labs'", None),
            "figma-desktop": ("sse", None, "localhost:3845/sse"),
            "Notion": ("http", None, "mcp.notion.com/mcp"),
            "harbor": ("ws", None, "harbor.example.com")})
        told = json.dumps(self.setup())
        for secret in ("hunter2", "sl.abc123", "sl.def456", "lumen-frag", "sntrys_ghi789", "SENTRY_AUTH_TOKEN",
                       "Authorization"):
            self.assertNotIn(secret, told)

    def test_session_lines_give_tools_failure_sign_in_and_pending(self):
        config = {"mcpServers": {"Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"},
                                 "harbor-api": {"type": "http", "url": "https://api.harbor.dev/mcp"}},
                  "projects": {self.folder: {"mcpServers": {"tidepool-db": {"command": "tidepool-mcp"}}}}}
        self.claude_json(**config)
        project = self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        self.settings("local", enabledMcpjsonServers=["sentry"])
        self.plugin_servers("figma", {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}})
        self.session("a0", self.delta(["mcp__Dropbox__search"], failed=[("Dropbox", "an older session's")]), age=300)
        self.session("b1", self.delta(
            ["Read", "mcp__Dropbox__search", "mcp__Dropbox__fetch", "mcp__tidepool-db__query",
             "mcp__tidepool-db__drop"],
            failed=[("sentry", "npx ENOENT")], sign_in=["harbor-api", "plugin:figma:figma"], pending=[]),
            self.instructions({"Dropbox": "Search before you fetch."}),
            self.delta(["mcp__tidepool-db__schema"], ["mcp__Dropbox__fetch"], failed=[("sentry", "npx ENOENT")],
                       sign_in=["harbor-api"], pending=["plugin:figma:figma"]),
            # compacted, the conversation starts its list over: the tools dropped meanwhile are gone
            self.compacted(),
            self.delta(["Read", "mcp__Dropbox__search", "mcp__tidepool-db__query", "mcp__tidepool-db__schema"]),
            self.instructions({"Dropbox": "Search before you fetch."}),
            # a subagent's own line, where an older Claude wrote it into the conversation's file
            self.line(type="attachment", isSidechain=True, attachment={
                "type": "deferred_tools_delta", "addedNames": [], "removedNames": ["mcp__Dropbox__search"],
                "failedMcpServers": [{"name": "Dropbox", "error": "a subagent's"}]}), age=200)
        self.session("c2", self.line(type="user", message={"role": "user", "content": "A run with no servers"}),
                     age=100)
        before = self.files()
        found = {s["name"]: s for s in self.servers()}
        self.assertEqual(found["sentry"], {
            "name": "sentry", "label": "sentry", "kind": "stdio", "scope": "Project", "source": "Project",
            "path": project, "runs": "npx -y @sentry/mcp-server", "url": None, "brand": "sentry", "state": "failed",
            "tools": None, "tokens": None, "error": "npx ENOENT", "used": 0})
        # a known service by its name, else by its address (core/connectors.py's brands); any other has none
        self.assertEqual({name: s["brand"] for name, s in found.items() if s["brand"]},
                         {"sentry": "sentry", "Dropbox": "dropbox", "plugin:figma:figma": "figma"})
        # tokens: its tool lines and its instructions, a token for every 4 characters
        self.assertEqual({name: (s["state"], s["tools"], s["tokens"], s["error"]) for name, s in found.items()}, {
            "sentry": ("failed", None, None, "npx ENOENT"),
            "tidepool-db": ("on", 2, round(len("mcp__tidepool-db__query\nmcp__tidepool-db__schema") / 4), None),
            "Dropbox": ("on", 1, round(len("mcp__Dropbox__search\nSearch before you fetch.") / 4), None),
            "harbor-api": ("sign in", None, None, None),
            # Claude still connecting it when it wrote the line: pending, not a .mcp.json server waiting for its yes
            "plugin:figma:figma": ("pending", None, None, None)})
        self.assertEqual(self.files(), before)

    def test_a_claude_ai_connector_is_named_from_its_lines(self):
        self.claude_json(claudeAiMcpEverConnected=["claude.ai Google Drive", "claude.ai Notion"])
        # the folder's own session is older: the account's connectors are as the newest session anywhere says
        self.session("a0", self.delta(["mcp__claude_ai_Box__search"], failed=[], sign_in=[], pending=[]), age=100)
        self.session("b1", self.delta(
            ["mcp__claude_ai_Google_Drive__search_files", "mcp__claude_ai_Google_Drive__read_file",
             "mcp__claude_ai_Linear__list_issues", "mcp__ide__getDiagnostics"],
            failed=[], sign_in=["claude.ai Box"], pending=[]),
            self.instructions({"claude.ai Linear": "Name the team first."}),
            folder=os.path.join(self.home, "harbor-web"))
        self.assertEqual(self.by_name("label", "kind", "state", "tools", "tokens"), {
            "claude.ai Box": ("Box", "claude.ai", "sign in", None, None),
            "claude.ai Google Drive": ("Google Drive", "claude.ai", "on", 2, round(len(
                "mcp__claude_ai_Google_Drive__search_files\nmcp__claude_ai_Google_Drive__read_file") / 4)),
            "claude.ai Linear": ("Linear", "claude.ai", "on", 1,
                                 round(len("mcp__claude_ai_Linear__list_issues\nName the team first.") / 4)),
            "claude.ai Notion": ("Notion", "claude.ai", "not checked", None, None)})

    def test_off_here_and_not_approved_come_from_the_project_entry(self):
        # the folder is a worktree: Claude keeps its project's settings under the main checkout's folder
        main = os.path.join(os.path.dirname(self.folder), "lumen")
        self.put(os.path.join(main, ".git", "HEAD"), "ref: refs/heads/main\n")
        worktree = os.path.join(main, ".git", "worktrees", "lumen-api")
        self.put(os.path.join(worktree, "HEAD"), "ref: refs/heads/paging\n")
        self.put(os.path.join(self.folder, ".git"), f"gitdir: {worktree}\n")
        self.claude_json(
            mcpServers={"Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"}},
            claudeAiMcpEverConnected=["claude.ai Notion"],
            projects={main: {"disabledMcpServers": ["Dropbox", "claude.ai Notion"],
                             "disabledMcpjsonServers": ["metrics"]},
                      self.folder: {"disabledMcpServers": ["sentry"]}})
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]},
                          metrics={"command": "lumen-metrics"},
                          **{"harbor-api": {"type": "http", "url": "https://api.harbor.dev/mcp"}})
        # a plugin installed for this project: its servers are the plugin's, nothing of .mcp.json's to approve
        root = os.path.join(self.home, ".claude", "plugins", "cache", "market", "ops", "1.0")
        self.put(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), json.dumps(
            {"version": 2, "plugins": {"ops@market": [{"scope": "project", "projectPath": self.folder,
                                                       "installPath": root}]}}))
        self.put(os.path.join(root, ".mcp.json"), json.dumps({"mcpServers": {"status": {"command": "ops-status"}}}))
        self.settings("project", enabledPlugins={"ops@market": True})
        self.settings("local", enabledMcpjsonServers=["sentry", "metrics"])
        self.session("a0", self.delta(["mcp__Dropbox__search", "mcp__claude_ai_Notion__search"], failed=[],
                                      sign_in=[], pending=[]))
        self.assertEqual(self.by_name("scope", "state", "tools"), {
            "harbor-api": ("Project", "not approved", None), "metrics": ("Project", "off here", None),
            "sentry": ("Project", "not checked", None), "Dropbox": ("Global", "off here", None),
            "claude.ai Notion": ("Account", "off here", None), "plugin:ops:status": ("Project", "not checked", None)})
        # every server of the project's file approved: a refused one stays off
        self.settings("user", enableAllProjectMcpServers=True)
        self.assertEqual(self.by_name("state")["harbor-api"], ("not checked",))
        self.assertEqual(self.by_name("state")["metrics"], ("off here",))

    def test_a_conversation_uses_skills_servers_and_agents(self):
        self.claude_json(claudeAiMcpEverConnected=["claude.ai Box"])
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        search = self.call("mcp__sentry__search_issues", "02", query="paging")
        session = self.session("a0", *[
            self.call("Skill", "01", skill="api-routes"),
            search, search,                     # Claude writes a message's line again: one call
            self.call("Agent", "03", description="Find the routes", prompt="…", subagent_type="Explore"),
            self.call("Task", "04", description="Find the tests", prompt="…", subagent_type="Explore"),
            self.call("Agent", "05", description="Write the docs", prompt="…"),      # Claude's general-purpose
            self.call("Skill", "06", "2026-11-12T10:30:00.000Z", skill="api-routes", args="v2"),
            self.call("Skill", "07", "2026-11-12T10:00:00.000Z", skill="figma:look"),
            self.call("Skill", "08", skill=["not", "a", "name"]),
            self.call("mcp__claude_ai_Box__search", "09", query="design notes"),
            self.call("mcp__sentry__get_issue", "10", id="LUMEN-42"),
            self.line(type="user", message={"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_02", "content": "mcp__sentry__search_issues"}]})])
        used = {"skills": {"api-routes": "2026-11-12T10:30:00.000Z", "figma:look": "2026-11-12T10:00:00.000Z"},
                "servers": {"sentry": 2, "claude_ai_Box": 1}, "agents": {"Explore": 2, "general-purpose": 1}}
        self.assertEqual(agent_setup.use(session), used)
        self.assertEqual(agent_setup.use(None), {"skills": {}, "servers": {}, "agents": {}})
        self.assertEqual(self.by_name("used", session=session), {"sentry": (2,), "claude.ai Box": (1,)})
        self.assertEqual(agent_setup.claude_setup(self.folder, self.home, session)["use"], used)

    def calls(self, log):
        try:
            with open(log, encoding="utf-8") as f:
                return [json.loads(line) for line in f]
        except FileNotFoundError:
            return []

    def test_a_damaged_line_and_a_long_error(self):
        self.claude_json(mcpServers={
            "sentry": {"command": "npx", "args": "-y"},              # args of a wrong type: as none
            "Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"},
            "no-url": {"type": "http"}, "typed": {"command": 3}, "listed": ["npx"],
            "kind": {"type": ["http"], "url": "https://mcp.lumen.dev/mcp"}, "evil\x1b[2J": {"command": "npx"}})
        self.put(os.path.join(self.folder, ".mcp.json"), "{not json")
        long = "x" * 150 + "\x1b[31m\n" + "y" * 150
        self.session("a0", *[
            '{"type": "attachment", "attachment": {"type": "deferred_tools_delta", "addedNames": [',
            "[1, 2]", self.line(type="attachment", attachment=[]),
            self.line(type="attachment", attachment={
                "type": "deferred_tools_delta", "addedNames": [3, None, "mcp__Dropbox__search"], "addedLines": "x",
                "removedNames": {"mcp__Dropbox__search": True}, "failedMcpServers": [3, {"name": 4}, {"name": "sentry",
                                                                                                    "error": long}],
                "needsAuthMcpServers": "Dropbox", "pendingMcpServers": [None]}),
            self.line(type="attachment", attachment={"type": "mcp_instructions_delta", "addedNames": ["Dropbox"],
                                                     "addedBlocks": [7], "removedNames": None})])
        os.mkfifo(os.path.join(os.path.dirname(self.session("b1", "")), "c2.jsonl"))
        self.assertEqual(self.by_name("runs", "state", "tools", "error"), {
            "sentry": ("npx", "failed", None, "x" * 150 + " " + "y" * 48 + "…"),
            "Dropbox": (None, "on", 1, None)})

    def test_the_cli_answers_in_json(self):
        self.put(os.path.join(self.folder, "CLAUDE.md"), "Project")
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        session = self.session("a0", self.call("mcp__sentry__search_issues", "01", query="paging"))
        set_env(self, HOME=self.home)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_setup.main(["agent_setup.py", "claude", self.folder]), 0)
            self.assertEqual(agent_setup.main(["agent_setup.py", "claude", self.folder, session]), 0)
        first, second = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([r["scope"] for r in first["rules"]], ["Project"])
        self.assertEqual([(s["name"], s["used"]) for s in first["servers"]], [("sentry", 0)])
        self.assertEqual([(s["name"], s["used"]) for s in second["servers"]], [("sentry", 1)])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(agent_setup.main(["agent_setup.py", "codex"]), 2)
            # the agents and a server's check are agent_state.py's
            self.assertEqual(agent_setup.main(["agent_setup.py", "agents"]), 2)
            self.assertEqual(agent_setup.main(["agent_setup.py", "check", "claude", self.folder, "sentry"]), 2)

    def test_codex_rules_skills_and_permissions(self):
        self.programs({"codex": {"mcp list --json": ["[]", "", 0]}})
        work = os.path.dirname(self.folder)
        self.put(os.path.join(work, ".git", "HEAD"), "ref: refs/heads/main\n")        # the repository's top
        self.put(os.path.join(os.path.dirname(work), "AGENTS.md"), "Above the repository: never read")
        personal = self.put(self.codex_home("AGENTS.override.md"), "Mine, for now")
        self.put(self.codex_home("AGENTS.md"), "Mine")
        top = self.put(os.path.join(work, "AGENTS.md"), "x" * 400)
        self.put(os.path.join(work, "src", "AGENTS.md"), "Beside the folder: not on its way")
        here = self.put(os.path.join(self.folder, "AGENTS.md"), "lumen-api")
        self.put(os.path.join(self.folder, "AGENTS.override.md"), "  \n")           # empty: the next one read
        self.put(os.path.join(self.folder, "CLAUDE.md"), "Claude's alone")
        own = self.put(self.codex_home("skills", "notes", "SKILL.md"),
                       "---\nname: lumen-notes\ndescription: Notes\n---")
        self.put(self.codex_home("skills", ".system", "openai-docs", "SKILL.md"), "---\nname: openai-docs\n---")
        shared = self.put(os.path.join(self.home, ".agents", "skills", "review", "SKILL.md"),
                          "---\nname: review\ndescription: Reviews a change\n---")
        routes = self.put(os.path.join(work, ".agents", "skills", "routes", "SKILL.md"),
                          "---\nname: api-routes\ndescription: Routes\n---")
        migrations = self.put(os.path.join(self.folder, ".agents", "skills", "migrations", "SKILL.md"), "# Migrations")
        default = self.put(self.codex_home("rules", "default.rules"), "\n".join([
            'prefix_rule(pattern=["git", "status"], decision="allow")',
            'prefix_rule(pattern=["git", "push"], decision="allow")',
            'prefix_rule(pattern=["npm", "test"])',
            'prefix_rule(pattern=["git", "commit", "-m", "wip fix"], decision="allow")',
            "# what the team asked",
            "prefix_rule(",
            '    pattern = ["gh", "pr", ["view", "list"]],',
            '    decision = "prompt",',
            '    justification = "Reads a pull request",',
            ")",
            'prefix_rule(pattern=["rm", "-rf"], decision="forbidden")',
            'prefix_rule(pattern=["git", "status"], decision="allow")',
            'prefix_rule(pattern=PATTERN, decision="allow")',
            'prefix_rule(pattern=["curl"], decision="maybe")',
            'prefix_rule(pattern=[], decision="allow")',
            'prefix_rule(pattern=["ls\\x1b[2J"], decision="allow")',
            'prefix_rule(pattern=["ls", 3], decision="allow")',
            'prefix_rule(pattern=["ls", []], decision="allow")',
            'host_executable(name="git", paths=["/usr/bin/git"])', ""]))
        team = self.put(self.codex_home("rules", "team.rules"),
                        'prefix_rule(pattern=["git", "push"], decision="prompt")\n'
                        'prefix_rule(pattern=["gh", "pr"], decision="forbidden")\n')
        self.put(self.codex_home("rules", "broken.rules"), 'prefix_rule(pattern=["ls"')
        self.put(self.codex_home("rules", "notes.txt"), 'prefix_rule(pattern=["ls"], decision="allow")')
        before = self.files()
        found = agent_setup.codex_setup(self.folder, self.home)
        # Codex's own home's, then from the repository's top down to the folder: one file in each, the override first
        self.assertEqual(found["rules"], [
            {"path": personal, "scope": "Global", "tokens": round(len("Mine, for now") / 4), "paths": [], "via": None},
            {"path": top, "scope": "Project", "tokens": 100, "paths": [], "via": None},
            {"path": here, "scope": "Project", "tokens": round(len("lumen-api") / 4), "paths": [], "via": None}])
        self.assertEqual([(s["name"], s["description"], s["scope"], s["source"], s["path"]) for s in found["skills"]], [
            ("lumen-notes", "Notes", "Global", "Global", own),
            ("review", "Reviews a change", "Global", "Global", shared),
            ("api-routes", "Routes", "Project", "Project", routes),
            ("migrations", "", "Project", "Project", migrations)])
        permissions = found["permissions"]
        self.assertEqual([(r["rule"], r["behavior"], r["scope"], r["path"]) for r in permissions["rules"]], [
            ("git status", "allow", "Global", default), ("git push", "allow", "Global", default),
            ("npm test", "allow", "Global", default), ("git commit -m 'wip fix'", "allow", "Global", default),
            ("gh pr {view,list}", "ask", "Global", default), ("rm -rf", "deny", "Global", default),
            ("git push", "ask", "Global", team), ("gh pr", "deny", "Global", team)])
        self.assertEqual({k: permissions[k] for k in ("allow", "ask", "deny", "mode")},
                         {"allow": 4, "ask": 2, "deny": 2, "mode": None})       # no config.toml: no policy
        # the most restrictive rule that matches decides, as Claude's deny before ask before allow
        self.assertEqual([(c["rule"], c["hides"]["rule"], c["text"]) for c in permissions["conflicts"]], [
            ("git push", "git push", "ask in Global hides allow in Global"),
            ("gh pr", "gh pr {view,list}", "deny in Global hides ask in Global")])
        self.assertEqual((found["agents"], found["servers"]), ([], []))
        self.assertEqual({k: v for k, v in self.files().items() if not k.endswith("agent-calls")}, before)
        # outside a repository, the folder's own alone; CODEX_HOME where Codex is told to keep its own
        shutil.rmtree(os.path.join(work, ".git"))
        elsewhere = self.put(os.path.join(self.home, "codex-elsewhere", "AGENTS.md"), "Elsewhere")
        set_env(self, CODEX_HOME=os.path.dirname(elsewhere))
        self.assertEqual([r["path"] for r in agent_setup.codex_setup(self.folder, self.home)["rules"]],
                         [elsewhere, here])

    def test_codex_servers_from_its_own_list(self):
        listed = [
            {"name": "sentry", "enabled": True, "disabled_reason": None, "transport": {
                "type": "stdio", "command": "npx", "args": ["-y", "@sentry/mcp-server", "--org", "lumen labs"],
                "env": {"SENTRY_AUTH_TOKEN": "sntrys_ghi789"}, "env_vars": ["SENTRY_ORG"], "cwd": None},
             "startup_timeout_sec": None, "tool_timeout_sec": None, "auth_status": "unsupported"},
            {"name": "linear", "enabled": True, "disabled_reason": None, "transport": {
                "type": "streamable_http", "url": "https://mcp.linear.app/mcp?token=lin_abc123#lumen",
                "bearer_token_env_var": "LINEAR_TOKEN", "http_headers": {"X-Api-Key": "lin_def456"},
                "env_http_headers": None}, "startup_timeout_sec": 20.0, "tool_timeout_sec": None,
             "auth_status": "not_logged_in"},
            {"name": "notion", "enabled": False, "disabled_reason": "disabled in config", "transport": {
                "type": "streamable_http", "url": "https://mcp.notion.com/mcp"}, "auth_status": "not_logged_in"},
            {"name": "figma", "enabled": True, "disabled_reason": None, "transport": {
                "type": "streamable_http", "url": "https://mcp.figma.com/mcp"}, "auth_status": "o_auth"},
            {"name": 3}, "sentry", {"name": "pigeon", "enabled": True, "transport": {"type": ["stdio"]}},
            {"name": "evil\x1b[2J", "enabled": True, "transport": {"type": "stdio", "command": "npx"}},
            {"name": "nothing", "enabled": True, "transport": {"type": "stdio"}}]
        log = self.programs({"codex": {"mcp list --json": [json.dumps(listed), "", 0]}})
        found = agent_setup.codex_setup(self.folder, self.home)["servers"]
        self.assertEqual(found[0], {
            "name": "sentry", "label": "sentry", "kind": "stdio", "scope": "Global", "source": "Global",
            "path": self.codex_home("config.toml"), "runs": "npx -y @sentry/mcp-server --org 'lumen labs'",
            "url": None, "brand": "sentry", "state": "on", "tools": None, "tokens": None, "error": None, "used": 0})
        self.assertEqual([s["brand"] for s in found][:4], ["sentry", "linear", "notion", "figma"])
        self.assertEqual([(s["name"], s["kind"], s["url"], s["state"]) for s in found], [
            ("sentry", "stdio", None, "on"), ("linear", "http", "mcp.linear.app/mcp", "sign in"),
            ("notion", "http", "mcp.notion.com/mcp", "off"), ("figma", "http", "mcp.figma.com/mcp", "on")])
        for secret in ("sntrys_ghi789", "SENTRY_AUTH_TOKEN", "SENTRY_ORG", "lin_abc123", "lin_def456", "LINEAR_TOKEN",
                       "X-Api-Key"):
            self.assertNotIn(secret, json.dumps(found))
        self.assertEqual(self.calls(log), [{"program": "codex", "cwd": os.path.realpath(self.folder),
                                            "argv": ["mcp", "list", "--json"]}])
        self.assertFalse(agent_setup.codex_setup(self.folder, self.home)["unlisted"])
        # a list Codex could not give: none, and said so (never "it has none")
        for answer in (["", "Error: config.toml: invalid", 1], ["not json", "", 0], ['{"name": "sentry"}', "", 0]):
            with self.subTest(answer):
                self.answer({"codex": {"mcp list --json": answer}})
                found = agent_setup.codex_setup(self.folder, self.home)
                self.assertEqual((found["servers"], found["unlisted"]), ([], True))

    def test_what_both_read_carries_both_agents(self):
        log = self.programs({"claude": {}, "codex": {"mcp list --json": [json.dumps([
            {"name": "sentry", "enabled": True, "transport": {"type": "stdio", "command": "npx",
                                                              "args": ["-y", "@sentry/mcp-server"]}},
            {"name": "dropbox", "enabled": True, "transport": {"type": "streamable_http",
                                                               "url": "https://mcp.dropbox.com/mcp?via=codex"}},
            {"name": "linear", "enabled": True, "transport": {"type": "streamable_http",
                                                              "url": "https://mcp.linear.app/mcp"}}]), "", 0]}})
        self.claude_json(mcpServers={"sentry": {"command": "npx", "args": ["-y", "@sentry/mcp-server"]},
                                     "Dropbox": {"type": "http", "url": "https://mcp.dropbox.com/mcp"},
                                     "Notion": {"type": "http", "url": "https://mcp.notion.com/mcp"}})
        mine = self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "Mine")
        os.makedirs(self.codex_home())
        os.symlink(mine, self.codex_home("AGENTS.md"))               # one file for both, as many keep it
        agents_md = self.put(os.path.join(self.folder, "AGENTS.md"), "lumen-api")
        claude_md = self.put(os.path.join(self.folder, "CLAUDE.md"), "Claude's alone")
        before = self.files()
        both = ["claude", "codex"]
        claude = agent_setup.setup("claude", self.folder, self.home)
        self.assertEqual([(r["path"], r["agents"]) for r in claude["rules"]],
                         [(mine, both), (claude_md, ["claude"]), (agents_md, both)])
        self.assertEqual({s["name"]: s["agents"] for s in claude["servers"]},
                         {"sentry": both, "Dropbox": both, "Notion": ["claude"]})
        codex = agent_setup.setup("codex", self.folder, self.home)
        self.assertEqual([(r["path"], r["agents"]) for r in codex["rules"]],
                         [(self.codex_home("AGENTS.md"), both), (agents_md, both)])
        self.assertEqual({s["name"]: s["agents"] for s in codex["servers"]},
                         {"sentry": both, "dropbox": both, "linear": ["codex"]})
        self.assertEqual({k: v for k, v in self.files().items() if k != log}, before)
        with self.assertRaises(ValueError):
            agent_setup.setup("gemini", self.folder, self.home)

    def test_no_codex_is_no_codex_setup(self):
        self.programs({"claude": {}})
        self.put(os.path.join(self.folder, "AGENTS.md"), "lumen-api")
        self.put(self.codex_home("AGENTS.md"), "Mine")
        self.assertIsNone(agent_setup.codex_setup(self.folder, self.home))
        self.assertIsNone(agent_setup.setup("codex", self.folder, self.home))
        self.assertEqual([r["agents"] for r in agent_setup.setup("claude", self.folder, self.home)["rules"]],
                         [["claude"]])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_setup.main(["agent_setup.py", "codex", self.folder]), 0)
        self.assertIsNone(json.loads(out.getvalue()))
        # Codex here and Claude not: nothing of Codex's is marked Claude's
        os.remove(os.path.join(self.bin, "claude"))
        self.programs({"codex": {"mcp list --json": ["[]", "", 0]}})
        self.assertEqual([r["agents"] for r in agent_setup.setup("codex", self.folder, self.home)["rules"]],
                         [["codex"], ["codex"]])

    def test_the_cli_answers_for_codex(self):
        self.programs({"claude": {}, "codex": {"mcp list --json": ["[]", "", 0]}})
        self.put(os.path.join(self.folder, "AGENTS.md"), "lumen-api")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_setup.main(["agent_setup.py", "codex", self.folder]), 0)
            self.assertEqual(agent_setup.main(["agent_setup.py", "claude", self.folder]), 0)
        codex, claude = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(sorted(codex), ["agents", "effort", "hooks", "model", "permissions", "rules", "sandbox",
                                         "servers", "skills", "start", "unlisted", "unread", "use"])
        self.assertEqual([(r["scope"], r["agents"]) for r in codex["rules"]], [("Project", ["claude", "codex"])])
        self.assertEqual([r["agents"] for r in claude["rules"]], [["claude", "codex"]])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(agent_setup.main(["agent_setup.py", "codex", self.folder, "a0.jsonl"]), 2)

    def test_the_open_conversation_is_found_by_its_file_its_id_or_as_the_folders_newest(self):
        """The app tells a chat's conversation by its id, a terminal's agent by none: its file in the folder's place,
        else the folder's newest; an id is never a path."""
        old = self.session("a1", json.dumps({"type": "user"}), age=60)
        new = self.session("b2", json.dumps({"type": "user"}))
        other = self.session("c3", json.dumps({"type": "user"}), folder=os.path.join(self.home, "harbor-web"))
        found = lambda session: agent_setup.conversation(self.folder, session, self.home)    # noqa: E731
        self.assertEqual([found(old), found("a1"), found(None), found("gone")], [old, old, new, new])
        self.assertEqual(found("../" + os.path.basename(os.path.dirname(other)) + "/c3"), new)
        self.assertIsNone(agent_setup.conversation(os.path.join(self.home, "tidepool"), "a1", self.home))

    def test_the_model_and_effort_as_the_settings_and_the_environment_tell_them(self):
        found = lambda: (agent_setup.claude_setup(self.folder, self.home)["model"],      # noqa: E731
                         agent_setup.claude_setup(self.folder, self.home)["effort"])
        self.assertEqual(found(), (None, None))
        self.settings("user", model="sonnet", effortLevel="medium")
        self.assertEqual(found(), ("sonnet", "medium"))
        self.settings("project", model="claude-sonnet-5", effortLevel="xhigh")
        self.assertEqual(found(), ("claude-sonnet-5", "xhigh"))
        # the environment over the settings' model and effortLevel; a settings file's env over the environment
        set_env(self, ANTHROPIC_MODEL="claude-haiku-5-5", CLAUDE_CODE_EFFORT_LEVEL="max")
        self.assertEqual(found(), ("claude-haiku-5-5", "max"))
        self.settings("local", env={"ANTHROPIC_MODEL": "opus[1m]", "CLAUDE_CODE_EFFORT_LEVEL": "low"})
        self.assertEqual(found(), ("opus[1m]", "low"))
        # the organization's over every other; an effort Claude has not is none
        self.settings("managed", model="claude-sonnet-5-5", env={"CLAUDE_CODE_EFFORT_LEVEL": "extreme"})
        self.assertEqual(found(), ("opus[1m]", None))
        self.settings("local", env={})
        set_env(self, ANTHROPIC_MODEL=None, CLAUDE_CODE_EFFORT_LEVEL=None)
        self.settings("managed", model="claude-sonnet-5-5")
        self.assertEqual(found(), ("claude-sonnet-5-5", "xhigh"))

    def test_opus_5_5_and_later_take_the_effort_kept_under_their_own_id(self):
        """Claude reads modelSettings.<id>.effortLevel for these and passes the settings' one effortLevel by: the
        reader takes the one in effect for the model in use, an alias's by the newest id the price table has."""
        effort = lambda: agent_setup.claude_setup(self.folder, self.home)["effort"]      # noqa: E731
        self.settings("user", model="opus", effortLevel="low")
        self.assertIsNone(effort())
        self.settings("user", model="opus", effortLevel="low", modelSettings={
            "claude-opus-5-5": {"effortLevel": "high"}, "claude-sonnet-5-5": {"effortLevel": "medium"}})
        self.assertEqual(effort(), "high")
        self.settings("local", modelSettings={"claude-opus-5-5": {"effortLevel": "xhigh"}, "claude-opus-5": 5})
        self.assertEqual(effort(), "xhigh")
        for model, said in (("claude-opus-5-5[1m]", "xhigh"), ("claude-opus-5", "low"), ("sonnet", "low"),
                            ("claude-opus-4-8", "low")):
            self.settings("project", model=model)
            self.assertEqual(effort(), said, model)
        self.settings("project", model="opus")
        set_env(self, CLAUDE_CODE_EFFORT_LEVEL="medium")           # the environment over either
        self.assertEqual(effort(), "medium")
        set_env(self, CLAUDE_CODE_EFFORT_LEVEL=None)
        os.unlink(os.path.join(self.folder, ".claude", "settings.json"))
        self.settings("user", effortLevel="low", modelSettings={"claude-opus-5-5": {"effortLevel": "high"}})
        self.assertEqual(effort(), "low")                           # no model named, none run yet
        self.session("a1", json.dumps({"type": "assistant", "message": {
            "model": "claude-opus-5-5", "usage": {"input_tokens": 10}}}))
        self.assertEqual(effort(), "xhigh")                         # the newest chat's is the one in use

    def test_what_the_settings_files_turn_off_is_read_by_the_keys_the_forms_write(self):
        self.put(os.path.join(self.home, ".claude", "skills", "release-notes", "SKILL.md"), "---\nname: notes\n---\n")
        self.agent_file(os.path.join(self.folder, ".claude", "agents"), "docs.md", name="doc-checker",
                        description="Checks the docs")
        self.claude_json(mcpServers={"github": {"type": "http", "url": "https://mcp.github.example/mcp"}})
        self.settings("user", hooks={"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "./scripts/guard.sh"}]}]})
        found = self.setup()
        self.assertEqual(found["off"], {"skills": [], "agents": [], "servers": [], "hooks": False})
        self.assertEqual(([one["off"] for one in found["skills"] + found["agents"]], found["servers"][0]["state"],
                          len(found["hooks"]), found["stopped"]), ([False, False], "not checked", 1, []))
        self.settings("project", skillOverrides={"notes": "off", "other": "on"},
                      permissions={"deny": ["Agent(doc-checker)", "Bash(rm:*)"]})
        self.settings("local", skillOverrides={"notes": "off"}, deniedMcpServers=[{"serverName": "github"}, "x"],
                      disableAllHooks=True)
        found = self.setup()
        self.assertEqual(found["off"], {"skills": ["notes", "notes"], "agents": ["doc-checker"],
                                        "servers": ["github"], "hooks": True})
        self.assertEqual(([one["off"] for one in found["skills"] + found["agents"]], found["servers"][0]["state"]),
                         ([True, True], "off here"))
        self.assertEqual((found["hooks"], [one["name"] for one in found["stopped"]]), ([], ["guard.sh"]))

    def test_codexs_project_config_is_read_where_codex_trusts_the_folder(self):
        own = self.put(os.path.join(self.home, ".codex", "config.toml"),
                       'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n')
        project = self.put(os.path.join(self.folder, ".codex", "config.toml"),
                           'model = "gpt-5.3-codex"\nsandbox_mode = "read-only"\n')
        read = lambda: agent_setup.codex_config(self.home, self.folder)      # noqa: E731
        self.assertFalse(agent_setup.codex_trusted(self.folder, self.home))
        self.assertEqual(read(), {"model": "gpt-5.2-codex", "approval_policy": "on-request"})
        for head, trusted in ((f"[projects.{json.dumps(self.folder)}]", True), (f"[projects.'{self.folder}']", True),
                              (f"[projects.{json.dumps(self.home)}]", False)):
            self.put(own, f'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n\n{head}\n'
                          'trust_level = "trusted"\n')
            self.assertEqual(agent_setup.codex_trusted(self.folder, self.home), trusted, head)
            self.assertEqual(read().get("sandbox_mode"), "read-only" if trusted else None)
        self.put(own, f'model = "gpt-5.2-codex"\napproval_policy = "on-request"\n\n'
                      f'[projects.{json.dumps(self.folder)}]\ntrust_level = "trusted"\n')
        self.assertEqual((read()["model"], read()["approval_policy"]), ("gpt-5.3-codex", "on-request"))
        self.assertEqual(agent_setup.codex_told(self.home, self.folder, "model"), {"scope": "Project", "path": project})
        self.assertEqual(agent_setup.codex_told(self.home, self.folder, "approval_policy"),
                         {"scope": "Global", "path": own})
        self.assertIsNone(agent_setup.codex_told(self.home, self.folder, "model_reasoning_effort"))
        self.assertEqual(agent_setup.codex_sandbox(self.folder, self.home, read())["scope"], "Project")
        self.assertEqual(agent_setup.codex_permissions(self.home, self.folder)["told"],
                         {"scope": "Global", "path": own})
        self.assertEqual(agent_setup.codex_config(self.home)["model"], "gpt-5.2-codex")     # no folder: its home's
        self.put(own, f'profile = "deep"\nmodel = "gpt-5.2-codex"\n\n[projects.{json.dumps(self.folder)}]\n'
                      'trust_level = "trusted"\n')
        self.assertEqual(read(), {"model": "gpt-5.3-codex", "sandbox_mode": "read-only"})  # over a profile too

    def test_hooks_from_every_settings_layer_and_each_enabled_plugin(self):
        guard = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "./scripts/guard.sh"}]}]}
        project = self.settings("project", hooks=guard)
        user = self.settings("user", enabledPlugins={"notes@market": True}, hooks={
            "SessionStart": [{"hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/context.py --x"}]}],
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "notify-send done"},
                                               {"type": "prompt", "prompt": "Was it done?"}]}],
            "Broken": "not a list", "Notification": [{"hooks": [{"type": "command", "command": ""}, 3]}]})
        root = self.install("notes")["notes"]
        plugin = self.put(os.path.join(root, "hooks", "hooks.json"), json.dumps({"hooks": {"PostToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command",
                                                 "command": "${CLAUDE_PLUGIN_ROOT}/bin/fmt.sh"}]}]}}))
        found = agent_setup.hooks(self.folder, self.home)
        self.assertEqual([(h["event"], h["matcher"], h["name"], h["kind"], h["scope"], h["source"], h["path"])
                          for h in found], [
            ("SessionStart", None, "context.py", "context", "Global", "Global", user),
            ("Stop", None, "notify-send", "watch", "Global", "Global", user),
            ("Stop", None, "prompt", "watch", "Global", "Global", user),
            ("PreToolUse", "Bash", "guard.sh", "gate", "Project", "Project", project),
            ("PostToolUse", "Edit|Write", "fmt.sh", "watch", "Global", "notes", plugin)])
        self.assertEqual(found[0]["command"], "python3 ~/.claude/hooks/context.py --x")
        # one file turns them all off; the organization may keep its own alone
        self.settings("local", disableAllHooks=True)
        self.assertEqual(agent_setup.hooks(self.folder, self.home), [])
        self.settings("local")
        managed = self.settings("managed", allowManagedHooksOnly=True, hooks=guard)
        self.assertEqual([(h["name"], h["scope"], h["path"]) for h in agent_setup.hooks(self.folder, self.home)],
                         [("guard.sh", "Managed", managed)])


if __name__ == "__main__":
    unittest.main()
