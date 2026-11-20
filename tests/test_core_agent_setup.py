"""Tests for core/agent_setup.py in a temporary home, folder and managed folder: Claude's rules, skills, mode,
permissions with their conflicts, sub-agents, MCP servers with their state and what a conversation used; Codex's setup
from a stand-in codex; the Agent panel's layers; nothing of theirs written."""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import PACKAGE, set_env, stubs

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_setup    # noqa: E402

# a row the graph draws ends with its way there, the first only where it is the row's one action
SHOW = {"id": "graph", "label": "Show graph", "path": None, "server": None, "primary": False}


class AgentSetup(unittest.TestCase):
    def setUp(self):
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        self.home = os.path.join(top, "home")
        self.folder = os.path.join(top, "work", "lumen-api")
        self.managed = os.path.join(top, "managed")     # the organization's folder, never this machine's own
        os.makedirs(self.folder)
        self.bin = os.path.join(self.home, "bin")       # the stand-in programs: the only ones a test finds
        for patch in (mock.patch.object(agent_setup, "MANAGED_DIR", self.managed),
                      mock.patch.object(agent_setup, "find", lambda name: shutil.which(name, path=self.bin))):
            patch.start()
            self.addCleanup(patch.stop)
        set_env(self, CODEX_HOME=None)

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def settings(self, scope, **values):
        """A settings file of SCOPE (managed, user, project, local) holding VALUES; its path."""
        path = {"managed": os.path.join(self.managed, "managed-settings.json"),
                "user": os.path.join(self.home, ".claude", "settings.json"),
                "project": os.path.join(self.folder, ".claude", "settings.json"),
                "local": os.path.join(self.folder, ".claude", "settings.local.json")}[scope]
        return self.put(path, json.dumps(values))

    def files(self):
        """Every file under the home, the folder and the managed folder, with its text: what a test checks nothing
        wrote."""
        found = {}
        for base in (self.home, self.folder, self.managed):
            for here, _, names in os.walk(base):
                for name in names:
                    with open(os.path.join(here, name), encoding="utf-8") as f:
                        found[os.path.join(here, name)] = f.read()
        return found

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
                         [(personal, "Personal"), (above, "Project"), (project, "Project"), (agents, "Project"),
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
                         [("notes", "", "Personal", "Personal"),
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
        self.assertEqual(self.setup(), {"rules": [], "skills": [], "default_mode": None, "agents": [],
                                        "permissions": {"allow": 0, "ask": 0, "deny": 0, "mode": None, "rules": [],
                                                        "conflicts": []},
                                        "servers": [], "use": {"skills": {}, "servers": {}, "agents": {}}})

    def test_the_mode_claude_starts_in_is_the_last_settings_files_that_names_one(self):
        user = os.path.join(self.home, ".claude", "settings.json")
        project = os.path.join(self.folder, ".claude", "settings.json")
        local = os.path.join(self.folder, ".claude", "settings.local.json")
        self.assertIsNone(self.setup()["default_mode"])
        self.put(user, json.dumps({"permissions": {"defaultMode": "plan"}}))
        self.assertEqual(self.setup()["default_mode"], "plan")
        self.put(project, json.dumps({"permissions": {"defaultMode": "acceptEdits", "allow": []}}))
        self.put(local, json.dumps({"permissions": {"defaultMode": "everything"}}))    # no mode Claude has
        self.assertEqual(self.setup()["default_mode"], "acceptEdits")
        self.put(local, json.dumps({"permissions": {"defaultMode": "auto"}}))
        before = self.files()
        self.assertEqual(self.setup()["default_mode"], "auto")
        self.assertEqual(self.files(), before)
        for damaged in ({"permissions": ["plan"]}, {"permissions": {"defaultMode": 2}}):
            self.put(user, json.dumps(damaged))
            self.put(project, "{not json")
            self.put(local, "")
            self.assertIsNone(self.setup()["default_mode"])

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
            {"rule": "Bash(npm test)", "behavior": "allow", "scope": "Personal", "path": user},
            {"rule": "Read(src/**)", "behavior": "allow", "scope": "Personal", "path": user},
            {"rule": "Bash(git commit *)", "behavior": "ask", "scope": "Personal", "path": user},
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
            "hides": {"rule": "Bash(git push *)", "behavior": "allow", "scope": "Personal", "path": user},
            "text": "deny in Project hides allow in Personal"})
        # a deny narrower than the allow is its exception, not a conflict
        self.assertEqual(self.hidden(), {"Bash(git push *)": "Bash(git push *)",
                                         "WebFetch(domain:docs.lumen.dev)": "WebFetch"})

    def test_an_ask_hides_the_allow_and_a_deny_the_ask_it_covers(self):
        self.settings("user", permissions={"allow": ["Edit(docs/*)"], "ask": ["Bash(rm -rf build)"]})
        self.settings("project", permissions={"deny": ["Bash(rm *)"]})
        self.settings("local", permissions={"ask": ["Edit(docs/**)"]})
        self.assertEqual([c["text"] for c in self.permissions()["conflicts"]],
                         ["ask in Local hides allow in Personal", "deny in Project hides ask in Personal"])

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
                          ("WebFetch", "Managed", drop_in), ("Bash(curl lumen.dev)", "Personal", user)])
        self.assertEqual((found["allow"], found["ask"], found["deny"], found["mode"]), (2, 1, 1, "plan"))
        self.assertEqual([c["text"] for c in found["conflicts"]], ["deny in Managed hides allow in Personal"])
        self.assertEqual(self.setup()["default_mode"], "plan")

    def agent_file(self, base, file, **meta):
        """An agent's file in BASE: META as its front matter (a list as `- item` lines), then its prompt."""
        lines = ["---"]
        for key, value in meta.items():
            lines += [f"{key}:"] + [f"  - {one}" for one in value] if isinstance(value, list) else [f"{key}: {value}"]
        return self.put(os.path.join(base, file), "\n".join(lines + ["---", "You review lumen-api's changes."]))

    def install(self, *names):
        """The plugins NAMES installed for the user from the market, enabled; each installed copy's folder."""
        roots = {name: os.path.join(self.home, ".claude", "plugins", "cache", "market", name, "1.0") for name in names}
        self.put(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), json.dumps(
            {"version": 2, "plugins": {f"{name}@market": [{"scope": "user", "installPath": root}]
                                       for name, root in roots.items()}}))
        return roots

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
             "tools": ["Read", "Write"], "scope": "Personal", "source": "Personal", "path": writer},
            # the user's reviewer is not listed: the project's of that name is the one Claude starts
            {"name": "migrations", "description": "Writes migrations", "model": None, "tools": [], "scope": "Project",
             "source": "Project", "path": migrations},
            {"name": "reviewer", "description": "lumen-api's reviewer", "model": "opus", "tools": ["Read", "Bash"],
             "scope": "Project", "source": "Project", "path": reviewer},
            {"name": "code-reviewer", "description": "Reviews a pull request", "model": "inherit",
             "tools": ["Read", "Grep"], "scope": "Personal", "source": "pr-review", "path": plugin}])
        self.assertEqual(self.files(), before)

    def listing(self, added=(), built_in=(), removed=(), initial=False):
        """A session's agent_listing_delta line, as Claude writes one: each added type with its line."""
        lines = [f"- {name}: {words}" for name, words in added]
        return json.dumps({"type": "attachment", "attachment": {
            "type": "agent_listing_delta", "addedTypes": [name for name, _ in added], "addedLines": lines,
            "builtInTypes": list(built_in), "builtInPluginTypes": [], "removedTypes": list(removed),
            "isInitial": initial, "showConcurrencyNote": False}})

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
                         [("general-purpose", "Personal"), ("Explore", "Built-in"), ("statusline-setup", "Built-in")])
        self.assertEqual(found[1], {"name": "Explore", "description": "Fast read-only search", "model": None,
                                    "tools": [], "scope": "Built-in", "source": "Claude", "path": None})
        self.assertEqual(found[2]["tools"], ["Read", "Edit"])
        self.assertEqual(agent_setup.claude_setup(self.folder, self.home, session)["agents"], found)
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

    # --- the MCP servers

    def claude_json(self, **values):
        """Claude's own ~/.claude.json in the stand-in home, holding VALUES; its path."""
        return self.put(os.path.join(self.home, ".claude.json"), json.dumps(values))

    def project_file(self, **found):
        """The folder's .mcp.json, its servers FOUND; its path."""
        return self.put(os.path.join(self.folder, ".mcp.json"), json.dumps({"mcpServers": found}))

    def plugin_servers(self, name, servers, flat=False):
        """The plugin NAME installed and enabled for the user, SERVERS in its .mcp.json (FLAT: not under mcpServers,
        as some plugins keep it); the file's path."""
        root = self.install(name)[name]
        self.settings("user", enabledPlugins={f"{name}@market": True})
        return self.put(os.path.join(root, ".mcp.json"), json.dumps(servers if flat else {"mcpServers": servers}))

    def line(self, **fields):
        """A session line as Claude writes one: FIELDS with the keys every line carries."""
        return json.dumps({"parentUuid": None, "isSidechain": False, "userType": "external", "cwd": self.folder,
                           "sessionId": "5e551011", "version": "2.1.325", "gitBranch": "main",
                           "timestamp": "2026-11-12T09:00:00.000Z", "uuid": "0b1d", **fields})

    def delta(self, added=(), removed=(), failed=None, sign_in=None, pending=None):
        """A deferred_tools_delta line, as measured: one line per tool added (its name), the servers' lists only where
        given (a compacted conversation's first one names none)."""
        attachment = {"type": "deferred_tools_delta", "addedNames": list(added), "addedLines": list(added),
                      "removedNames": list(removed), "readdedNames": [], "surfacedNames": [], "wireHiddenNames": []}
        if failed is not None:
            attachment["failedMcpServers"] = [{"name": name, "error": error} for name, error in failed]
        if sign_in is not None:
            attachment["needsAuthMcpServers"] = list(sign_in)
        if pending is not None:
            attachment["pendingMcpServers"] = list(pending)
        return self.line(type="attachment", attachment=attachment)

    def instructions(self, added=None, removed=()):
        """An mcp_instructions_delta line: each server's block of instructions ADDED ({name: block})."""
        added = added or {}
        return self.line(type="attachment", attachment={"type": "mcp_instructions_delta", "addedNames": list(added),
                                                        "addedBlocks": list(added.values()),
                                                        "removedNames": list(removed)})

    def compacted(self):
        return self.line(type="system", subtype="compact_boundary", content="Conversation compacted", level="info",
                         logicalParentUuid="0a1c", compactMetadata={"trigger": "auto"})

    def session(self, name, *lines, folder=None, age=0):
        """A session file of the chats started in FOLDER (else the folder), LINES its lines, changed AGE seconds ago;
        its path."""
        projects = os.path.join(self.home, ".claude", "projects")
        path = self.put(os.path.join(projects, re.sub(r"[^A-Za-z0-9-]", "-", folder or self.folder), f"{name}.jsonl"),
                        "\n".join(lines) + "\n")
        os.utime(path, (time.time() - age, time.time() - age))
        return path

    def servers(self, session=None):
        return agent_setup.servers(self.folder, self.home, session)

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
            ("Dropbox", "Dropbox", "http", "Personal", "Personal", config),
            ("claude.ai Google Drive", "Google Drive", "claude.ai", "Account", "claude.ai", None),
            ("plugin:figma:figma", "figma", "http", "Personal", "figma", figma),
            ("plugin:ops:harbor-status", "harbor-status", "stdio", "Personal", "ops", ops)])
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
            # a sub-agent's own line, where an older Claude wrote it into the conversation's file
            self.line(type="attachment", isSidechain=True, attachment={
                "type": "deferred_tools_delta", "addedNames": [], "removedNames": ["mcp__Dropbox__search"],
                "failedMcpServers": [{"name": "Dropbox", "error": "a sub-agent's"}]}), age=200)
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
            "sentry": ("Project", "not checked", None), "Dropbox": ("Personal", "off here", None),
            "claude.ai Notion": ("Account", "off here", None), "plugin:ops:status": ("Project", "not checked", None)})
        # every server of the project's file approved: a refused one stays off
        self.settings("user", enableAllProjectMcpServers=True)
        self.assertEqual(self.by_name("state")["harbor-api"], ("not checked",))
        self.assertEqual(self.by_name("state")["metrics"], ("off here",))

    def call(self, name, key, when="2026-11-12T09:00:00.000Z", **given):
        """An assistant line holding one tool call: the tool NAME, its id's end KEY, made WHEN, its input GIVEN."""
        return self.line(type="assistant", timestamp=when, requestId=f"req_{key}", message={
            "id": f"msg_{key}", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "tool_use", "id": f"toolu_{key}", "name": name, "input": given}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 3, "output_tokens": 40}})

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

    # --- Codex's setup, from stand-in agents

    def programs(self, answers):
        """Stand-in agents in the test's bin, one for each of ANSWERS ({program: {its arguments: [out, error, exit code]
        or [out, error, exit code, seconds it waits first]}}), read at each call; each call's program, folder and
        arguments go to the log, whose path it returns."""
        log, self.answers = os.path.join(self.home, "agent-calls"), os.path.join(self.home, "agent-answers.json")
        self.answer(answers)
        script = "\n".join([
            "#!/usr/bin/python3 -B", "import json, os, sys, time",
            "name = os.path.basename(sys.argv[0])",
            "with open(os.environ['AGENT_STAND_IN_LOG'], 'a') as f:",
            "    f.write(json.dumps({'program': name, 'cwd': os.getcwd(), 'argv': sys.argv[1:]}) + '\\n')",
            "with open(os.environ['AGENT_STAND_IN_ANSWERS']) as f:",
            "    out, error, code, *wait = json.load(f).get(name, {}).get(' '.join(sys.argv[1:]), ['', 'unknown', 2])",
            "time.sleep(wait[0] if wait else 0)",
            "sys.stdout.write(out)", "sys.stderr.write(error)", "sys.exit(code)", ""])
        stubs(self.bin, dict.fromkeys(answers, script))
        set_env(self, HOME=self.home, AGENT_STAND_IN_LOG=log, AGENT_STAND_IN_ANSWERS=self.answers)
        return log

    def answer(self, answers):
        """What the stand-in agents answer from now on (programs()'s ANSWERS)."""
        self.put(self.answers, json.dumps(answers))

    def codex_home(self, *parts):
        return os.path.join(self.home, ".codex", *parts)

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
            {"path": personal, "scope": "Personal", "tokens": round(len("Mine, for now") / 4), "paths": []},
            {"path": top, "scope": "Project", "tokens": 100, "paths": []},
            {"path": here, "scope": "Project", "tokens": round(len("lumen-api") / 4), "paths": []}])
        self.assertEqual([(s["name"], s["description"], s["scope"], s["source"], s["path"]) for s in found["skills"]], [
            ("lumen-notes", "Notes", "Personal", "Personal", own),
            ("review", "Reviews a change", "Personal", "Personal", shared),
            ("api-routes", "Routes", "Project", "Project", routes),
            ("migrations", "", "Project", "Project", migrations)])
        permissions = found["permissions"]
        self.assertEqual([(r["rule"], r["behavior"], r["scope"], r["path"]) for r in permissions["rules"]], [
            ("git status", "allow", "Personal", default), ("git push", "allow", "Personal", default),
            ("npm test", "allow", "Personal", default), ("git commit -m 'wip fix'", "allow", "Personal", default),
            ("gh pr {view,list}", "ask", "Personal", default), ("rm -rf", "deny", "Personal", default),
            ("git push", "ask", "Personal", team), ("gh pr", "deny", "Personal", team)])
        self.assertEqual({k: permissions[k] for k in ("allow", "ask", "deny", "mode")},
                         {"allow": 4, "ask": 2, "deny": 2, "mode": None})       # no config.toml: no policy
        # the most restrictive rule that matches decides, as Claude's deny before ask before allow
        self.assertEqual([(c["rule"], c["hides"]["rule"], c["text"]) for c in permissions["conflicts"]], [
            ("git push", "git push", "ask in Personal hides allow in Personal"),
            ("gh pr", "gh pr {view,list}", "deny in Personal hides ask in Personal")])
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
            "name": "sentry", "label": "sentry", "kind": "stdio", "scope": "Personal", "source": "Personal",
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
        # a list Codex could not give: none
        for answer in (["", "Error: config.toml: invalid", 1], ["not json", "", 0], ['{"name": "sentry"}', "", 0]):
            with self.subTest(answer):
                self.answer({"codex": {"mcp list --json": answer}})
                self.assertEqual(agent_setup.codex_setup(self.folder, self.home)["servers"], [])

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
        self.assertEqual(sorted(codex), ["agents", "permissions", "rules", "servers", "skills"])
        self.assertEqual([(r["scope"], r["agents"]) for r in codex["rules"]], [("Project", ["claude", "codex"])])
        self.assertEqual([r["agents"] for r in claude["rules"]], [["claude", "codex"]])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(agent_setup.main(["agent_setup.py", "codex", self.folder, "a0.jsonl"]), 2)

    # --- the Agent panel's layers

    def lumen(self):
        """lumen-api as center-chat.html's Agent panel has it: four rules, 17 permissions with a conflict, two skills,
        four servers (sentry failed, figma to sign in), five sub-agents; the open conversation's file."""
        self.rule_files = {
            "personal": self.put(os.path.join(self.home, ".claude", "CLAUDE.md"), "x" * 9600),
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
        return agent_setup.layers(agent_setup.setup(agent, self.folder, self.home, session), agent, self.folder,
                                  self.home)

    @staticmethod
    def section(found, key):
        return next(s for s in found["sections"] if s["id"] == key)

    @staticmethod
    def chosen(section, name):
        return next(r for r in section["rows"] if r["name"] == name)

    def test_costs_read_in_thousands_of_tokens(self):
        self.assertEqual([agent_setup.kilo(n) for n in (2400, 700, 11400, 4000, 2450, 30, 0)],
                         ["2.4k", "0.7k", "11.4k", "4.0k", "2.5k", "<0.1k", "0k"])
        # the health line's: whole from ten thousand
        self.assertEqual([agent_setup.kilo(n, whole=True) for n in (21909, 22500, 9949, 9950, 6100)],
                         ["22k", "23k", "9.9k", "10k", "6.1k"])

    def test_the_sections_in_order_with_their_counts_costs_and_rows(self):
        session = self.lumen()
        before = self.files()
        found = self.layers(session=session)
        self.assertEqual(self.files(), before)
        self.assertEqual(found["head"], {"name": "Claude", "where": "in lumen-api"})
        self.assertEqual([(s["id"], s["title"], s["count"], s["tokens"], s["cost"]) for s in found["sections"]], [
            ("rules", "Rules", 4, 6100, "6.1k"), ("permissions", "Permissions", 17, None, None),
            ("skills", "Skills", 2, 500, "0.5k"), ("connectors", "Connectors", 4, 16009, "16.0k"),
            ("agents", "Agents", 5, None, None)])
        rules = self.section(found, "rules")
        self.assertEqual([(r["id"], r["icon"], r["name"], r["note"], r["tag"], r["state"], r["tokens"], r["cost"],
                           r["dim"], r["warn"], r["used"], r["agents"]) for r in rules["rows"]], [
            ("rule:" + self.rule_files["personal"], "file", "CLAUDE.md", None,
             {"text": "Personal", "tone": "personal"}, None, 2400, "2.4k", False, False, False, ["claude"]),
            ("rule:" + self.rule_files["project"], "file", "CLAUDE.md", None, {"text": "Project", "tone": "project"},
             None, 1800, "1.8k", False, False, False, ["claude"]),
            ("rule:" + self.rule_files["agents"], "file", "AGENTS.md", None, {"text": "Project", "tone": "project"},
             None, 1200, "1.2k", False, False, False, ["claude"]),
            # read only with the files it names: dim, its cost not loaded at start
            ("rule:" + self.rule_files["api"], "file", "api.md", "when src/lumen/** is read",
             {"text": "Project", "tone": "project"}, None, 700, "0.7k", True, False, False, ["claude"])])
        skills = self.section(found, "skills")
        self.assertEqual([(r["icon"], r["name"], r["tag"], r["cost"], r["used"]) for r in skills["rows"]], [
            ("skill", "frontend-design", {"text": "Personal", "tone": "personal"}, "0.2k", False),
            ("skill", "api-routes", {"text": "Project", "tone": "project"}, "0.3k", True)])
        agents = self.section(found, "agents")
        self.assertEqual(agents["summary"], [{"text": "code-reviewer, Explore, 3 more", "tone": "ok"}])
        self.assertEqual([(r["icon"], r["name"], r["state"], r["tag"], r["used"]) for r in agents["rows"]], [
            ("bot", "code-reviewer", {"text": "sonnet", "tone": "ok"}, {"text": "pr-review", "tone": "plugin"},
             False),
            ("bot", "Explore", None, {"text": "Built-in", "tone": "muted"}, True),
            ("bot", "general-purpose", None, {"text": "Built-in", "tone": "muted"}, False),
            ("bot", "Plan", None, {"text": "Built-in", "tone": "muted"}, False),
            ("bot", "statusline-setup", None, {"text": "Built-in", "tone": "muted"}, False)])
        self.assertEqual([s["summary"] for s in found["sections"] if s["id"] in ("rules", "skills", "connectors")],
                         [[], [], []])

    def test_a_failed_and_a_sign_in_connector_come_first_with_their_words(self):
        found = self.layers(session=self.lumen())
        connectors = self.section(found, "connectors")
        self.assertEqual([(r["id"], r["icon"], r["name"], r["state"], r["tag"], r["cost"], r["used"], r["dim"])
                          for r in connectors["rows"]], [
            ("connector:sentry", "plug", "sentry", {"text": "failed", "tone": "bad"},
             {"text": "Project", "tone": "project"}, None, False, False),
            ("connector:plugin:figma:figma", "plug", "figma", {"text": "sign in", "tone": "warn"},
             {"text": "figma", "tone": "plugin"}, None, False, False),
            # then Claude's own /mcp order
            ("connector:chrome-devtools", "plug", "chrome-devtools", {"text": "1 tool", "tone": "ok"},
             {"text": "Personal", "tone": "personal"}, "<0.1k", True, False),
            ("connector:github", "plug", "github", {"text": "2 tools", "tone": "ok"},
             {"text": "Personal", "tone": "personal"}, "16.0k", False, False)])
        # a known service's brand, for its logo (the app) or its glyph (the TUI); a rule or a skill has none
        self.assertEqual([r["brand"] for r in connectors["rows"]], ["sentry", "figma", None, None])
        self.assertEqual({r["brand"] for s in found["sections"] if s["id"] != "connectors" for r in s["rows"]}, {None})
        # what loads at start: the rules read always, every skill's listing, the connectors' tools and instructions
        self.assertEqual(found["health"], {
            "loaded": 21909, "text": "22k loaded at start",
            "bar": [{"part": "rules", "tokens": 5400}, {"part": "skills", "tokens": 500},
                    {"part": "connectors", "tokens": 16009}],
            "problems": [{"text": "1 failed", "tone": "bad", "row": "connector:sentry"},
                         {"text": "1 sign in", "tone": "warn", "row": "connector:plugin:figma:figma"}]})

    def test_a_server_added_by_url_says_where_claude_signs_it_out_and_has_no_button_for_it(self):
        self.claude_json(
            mcpServers={"harbor": {"type": "http", "url": "https://api.harbor.dev/mcp"}},
            claudeAiMcpEverConnected=["claude.ai Box"],
            projects={self.folder: {"mcpServers": {"tidepool-db": {"command": "tidepool-mcp"}}}})
        tools = ["mcp__harbor__list_ports", "mcp__tidepool-db__query", "mcp__claude_ai_Box__search"]
        found = self.layers(session=self.session("a0", self.delta(tools, failed=[], sign_in=[], pending=[])))
        rows = {r["name"]: r["properties"] for r in self.section(found, "connectors")["rows"]}
        # signing out is Claude's own: its command on a line, never a button of herdr-fold's
        self.assertEqual(rows["harbor"]["lines"], [["From", "~/.claude.json", "Personal"],
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
        # nothing else to show: a section with no rows is left out, Connectors (where one is added) never
        self.assertEqual([s["id"] for s in found["sections"]], ["connectors"])
        rows = {r["name"]: r for r in self.section(found, "connectors")["rows"]}
        self.assertEqual([(name, r["state"], r["tag"], r["dim"]) for name, r in rows.items()], [
            ("Box", {"text": "sign in", "tone": "warn"}, {"text": "claude.ai", "tone": "account"}, False),
            # a .mcp.json server waiting for its yes, and one Claude was still connecting
            ("harbor-api", {"text": "not approved", "tone": "off"}, {"text": "Project", "tone": "project"}, True),
            ("sentry", {"text": "connecting", "tone": "busy"}, {"text": "Project", "tone": "project"}, False),
            ("tidepool-db", {"text": "1 tool", "tone": "ok"}, {"text": "Local", "tone": "muted"}, False),
            ("Dropbox", {"text": "not checked", "tone": "off"}, {"text": "Personal", "tone": "personal"}, False),
            ("Google Drive", {"text": "2 tools", "tone": "ok"}, {"text": "claude.ai", "tone": "account"}, False),
            ("Notion", {"text": "off here", "tone": "off"}, {"text": "claude.ai", "tone": "account"}, True)])

        def action(one, label, path=None, primary=False):
            return {"id": one, "label": label, "path": path, "server": None if one == "open" else server,
                    "primary": primary}
        server = "claude.ai Box"
        self.assertEqual(rows["Box"]["properties"], {
            "title": "Box", "state": {"text": "sign in", "tone": "warn"}, "lines": [["From", "claude.ai", "Account"]],
            "text": None, "error": None,
            "actions": [action("connect", "Connect", primary=True), action("turn-off", "Turn off in lumen-api"),
                        SHOW]})
        server = "claude.ai Google Drive"
        self.assertEqual(rows["Google Drive"]["properties"]["lines"],
                         [["From", "claude.ai", "Account"], ["Used", "2 times in this conversation", None]])
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
        self.assertEqual(found["health"]["problems"],
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

    def test_nothing_set_up_is_an_empty_connectors_section(self):
        found = self.layers()
        self.assertEqual(found["sections"], [{"id": "connectors", "title": "Connectors", "count": 0, "tokens": None,
                                              "cost": None, "summary": [], "rows": []}])
        self.assertEqual(found["health"], {"loaded": 0, "text": "0k loaded at start", "bar": [
            {"part": "rules", "tokens": 0}, {"part": "skills", "tokens": 0}, {"part": "connectors", "tokens": 0}],
            "problems": []})

    def test_the_conflict_row_stands_for_the_rule_it_hides(self):
        found = self.layers(session=self.lumen())
        permissions = self.section(found, "permissions")
        self.assertEqual(permissions["summary"], [{"text": "12 allow", "tone": "allow"},
                                                  {"text": "3 ask", "tone": "ask"}, {"text": "2 deny", "tone": "deny"}])
        rows = permissions["rows"]
        user = os.path.join(self.home, ".claude", "settings.json")
        project = os.path.join(self.folder, ".claude", "settings.json")
        self.assertEqual(rows[0], {
            "id": "conflict:allow:Bash(git push:*)", "icon": "shield", "name": "Bash(git push:*)",
            "note": "deny in Project hides allow in Personal", "tag": None, "state": None, "brand": None,
            "tokens": None, "cost": None, "used": False, "agents": ["claude"], "dim": False, "warn": True,
            "properties": {
                "title": "Bash(git push:*)", "state": None,
                "lines": [["Allow", "Bash(git push:*)", "Personal"], ["Deny", "Bash(git push:*)", "Project"]],
                "text": None, "error": None, "actions": [
                    # the two files hold a settings.json each: each named by where it is
                    {"id": "open", "label": "Open .claude/settings.json", "path": project, "server": None,
                     "primary": True},
                    {"id": "open", "label": "Open ~/.claude/settings.json", "path": user, "server": None,
                     "primary": False}]}})
        # then every rule in Claude's order, the one it hides not again
        self.assertEqual(len(rows), 17)
        self.assertEqual([(r["name"], r["state"], r["tag"]["text"], r["warn"]) for r in rows[1:3] + rows[11:15]], [
            ("Bash(npm test)", {"text": "allow", "tone": "allow"}, "Personal", False),
            ("Bash(npm run lint)", {"text": "allow", "tone": "allow"}, "Personal", False),
            ("Grep", {"text": "allow", "tone": "allow"}, "Personal", False),
            ("Bash(git push:*)", {"text": "deny", "tone": "deny"}, "Project", False),
            ("Bash(rm -rf *)", {"text": "deny", "tone": "deny"}, "Project", False),
            ("Bash(git commit *)", {"text": "ask", "tone": "ask"}, "Local", False)])
        self.assertEqual(rows[1]["id"], "permission:allow:Bash(npm test)")
        self.assertEqual(rows[1]["properties"], {
            "title": "Bash(npm test)", "state": {"text": "allow", "tone": "allow"},
            "lines": [["From", "~/.claude/settings.json", "Personal"]], "text": None, "error": None,
            "actions": [{"id": "open", "label": "Open settings.json", "path": user, "server": None, "primary": True}]})

    def test_each_kinds_properties(self):
        found = self.layers(session=self.lumen())
        rules, skills = self.section(found, "rules"), self.section(found, "skills")
        open_ = lambda label, path: {"id": "open", "label": label, "path": path, "server": None,  # noqa: E731
                                     "primary": True}
        self.assertEqual(rules["rows"][0]["properties"]["lines"], [["From", "~/.claude/CLAUDE.md", "Personal"]])
        # a rule: where it is, its first lines (no front matter, no blank line, as text, each cut)
        self.assertEqual(rules["rows"][1]["properties"], {
            "title": "CLAUDE.md", "state": None, "lines": [["From", "CLAUDE.md", "Project"]],
            "text": "# lumen-api\nRoutes live in src/lumen/routes.\nEvery route answers JSON.", "error": None,
            "actions": [open_("Open CLAUDE.md", self.rule_files["project"]), SHOW]})
        self.assertEqual(rules["rows"][3]["properties"], {
            "title": "api.md", "state": None,
            "lines": [["From", ".claude/rules/api.md", "Project"], ["Paths", "src/lumen/**", None]],
            "text": "# Routes\nEach route answers JSON.\n" + "w" * 119 + "…", "error": None,
            "actions": [open_("Open api.md", self.rule_files["api"]), SHOW]})
        # a skill: its description, used in the open conversation
        routes = self.chosen(skills, "api-routes")["properties"]
        self.assertEqual(routes["lines"], [["From", ".claude/skills/routes/SKILL.md", "Project"],
                                           ["Used", "in this conversation", None]])
        self.assertEqual(routes["text"][:35], "How lumen-api's routes are written.")
        self.assertEqual(routes["actions"], [open_("Open SKILL.md", os.path.join(
            self.folder, ".claude", "skills", "routes", "SKILL.md")), SHOW])
        # a sub-agent: its model and tools; Claude's own has no file
        agents = self.section(found, "agents")
        reviewer = os.path.join(self.home, ".claude", "plugins", "cache", "market", "pr-review", "1.0", "agents",
                                "code-reviewer.md")
        self.assertEqual(self.chosen(agents, "code-reviewer")["properties"], {
            "title": "code-reviewer", "state": {"text": "sonnet", "tone": "ok"},
            "lines": [["From", "pr-review", "Plugin"], ["Model", "sonnet", None], ["Tools", "Read, Grep", None]],
            "text": "Reviews a pull request", "error": None,
            "actions": [open_("Open code-reviewer.md", reviewer), SHOW]})
        self.assertEqual(self.chosen(agents, "Explore")["properties"], {
            "title": "Explore", "state": None,
            "lines": [["From", "Claude", "Built-in"], ["Used", "once in this conversation", None]],
            "text": "Fast read-only search", "error": None, "actions": [{**SHOW, "primary": True}]})
        # a permission is a gate on the graph's edges, no node of its own: no way there from its row
        self.assertNotIn("graph", [one["id"] for row in self.section(found, "permissions")["rows"]
                                   for one in row["properties"]["actions"]])
        self.assertEqual(self.chosen(agents, "Plan")["properties"]["lines"],
                         [["From", "Claude", "Built-in"], ["Tools", "Read, Grep, Glob", None]])
        # a server: where it is, what it runs, its error, Retry and its file
        connectors = self.section(found, "connectors")
        self.assertEqual(self.chosen(connectors, "sentry")["properties"], {
            "title": "sentry", "state": {"text": "failed", "tone": "bad"},
            "lines": [["From", ".mcp.json", "Project"], ["Runs", "npx -y @sentry/mcp-server", None]],
            "text": None, "error": "spawn npx ENOENT: npx is not on this machine's PATH", "actions": [
                {"id": "retry", "label": "Retry", "path": None, "server": "sentry", "primary": True},
                {"id": "open", "label": "Open .mcp.json", "path": os.path.join(self.folder, ".mcp.json"),
                 "server": None, "primary": False}, SHOW]})
        self.assertEqual(self.chosen(connectors, "figma")["properties"]["lines"],
                         [["From", "figma", "Plugin"], ["URL", "mcp.figma.com/mcp", None]])
        self.assertEqual(self.chosen(connectors, "chrome-devtools")["properties"]["lines"], [
            ["From", "~/.claude.json", "Personal"], ["Runs", "npx chrome-devtools-mcp@latest", None],
            ["Used", "once in this conversation", None]])

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
        self.assertEqual(found["head"], {"name": "Codex", "where": "in lumen-api"})
        self.assertEqual([s["id"] for s in found["sections"]], ["rules", "permissions", "connectors"])
        self.assertEqual([(r["name"], r["tag"]["text"], r["agents"], r["properties"]["lines"])
                          for r in self.section(found, "rules")["rows"]], [
            ("AGENTS.md", "Personal", ["codex"], [["From", "~/.codex/AGENTS.md", "Personal"]]),
            ("AGENTS.md", "Project", ["claude", "codex"], [["From", "AGENTS.md", "Project"]])])
        self.assertEqual(self.section(found, "rules")["rows"][0]["properties"]["actions"][0]["path"], mine)
        self.assertEqual(self.section(found, "rules")["rows"][1]["properties"]["actions"][0]["path"], here)
        # a behavior with no rule is not counted aloud
        self.assertEqual(self.section(found, "permissions")["summary"],
                         [{"text": "1 allow", "tone": "allow"}, {"text": "1 ask", "tone": "ask"}])
        permissions = self.section(found, "permissions")["rows"]
        self.assertEqual([(r["name"], r["note"], r["state"]) for r in permissions], [
            ("git push", "ask in Personal hides allow in Personal", None),
            ("git", None, {"text": "ask", "tone": "ask"})])
        self.assertEqual(permissions[1]["properties"]["actions"][0]["label"], "Open default.rules")
        self.assertEqual(permissions[1]["properties"]["actions"][0]["path"], rules)
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
                         [["From", "~/.codex/config.toml", "Personal"], ["URL", "mcp.linear.app/mcp", None]])
        self.assertEqual(found["health"]["problems"],
                         [{"text": "1 sign in", "tone": "warn", "row": "connector:linear"}])

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
            ("approval", "Approval", "Ask on request", None),
            ("conflict:allow:git push", "git push", "ask in Personal hides allow in Personal", None),
            ("permission:ask:git", "git", None, {"text": "ask", "tone": "ask"})])
        row = section["rows"][0]
        self.assertEqual((row["icon"], row["tag"], row["warn"], row["dim"], row["agents"]),
                         ("shield", {"text": "Personal", "tone": "personal"}, False, False, ["codex"]))
        self.assertEqual(row["properties"], {
            "title": "Approval", "state": None, "lines": [["From", "~/.codex/config.toml", "Personal"]],
            "text": None, "error": None,
            "actions": [{"id": "open", "label": "Open config.toml", "path": config, "server": None,
                         "primary": True}]})
        # a row as the others: counted with them; the head's words stay the rules' by behavior
        self.assertEqual((section["count"], section["summary"]),
                         (3, [{"text": "1 allow", "tone": "allow"}, {"text": "1 ask", "tone": "ask"}]))
        self.assertNotIn("invented", json.dumps(found))
        self.assertEqual({path: text for path, text in self.files().items() if path != log}, before)
        for policy, words in (("untrusted", "Ask unless trusted"), ("on-failure", "Ask on failure"),
                              ("never", "Never ask")):
            self.put(config, f"approval_policy = '{policy}'\n")
            self.assertEqual(self.section(self.layers("codex"), "permissions")["rows"][0]["note"], words)
        # with no rule the policy alone is the section
        os.remove(self.codex_home("rules", "default.rules"))
        alone = self.section(self.layers("codex"), "permissions")
        self.assertEqual(([r["id"] for r in alone["rows"]], alone["count"], alone["summary"]), (["approval"], 1, []))
        # a profile named, a policy with no word, none set: no row, and no section with no rule
        for text in ('profile = "careful"\napproval_policy = "never"\n', 'approval_policy = "lumen-policy"\n', ""):
            with self.subTest(text):
                self.put(config, text)
                self.assertNotIn("permissions", [s["id"] for s in self.layers("codex")["sections"]])
        # the policy is Codex's: Claude's rows are its rules where no settings file names a mode
        self.put(config, 'approval_policy = "never"\n')
        self.settings("user", permissions={"allow": ["Read"]})
        self.assertEqual([r["id"] for r in self.section(self.layers(), "permissions")["rows"]],
                         ["permission:allow:Read"])

    def test_claudes_mode_leads_its_permissions(self):
        # the same row for Claude: the mode it starts in, where a settings file names one, in the chat's words
        self.programs({"claude": {}})
        user = self.settings("user", permissions={"allow": ["Read"], "defaultMode": "plan"})
        before = self.files()
        section = self.section(self.layers(), "permissions")
        self.assertEqual([(r["id"], r["name"], r["note"], r["state"]) for r in section["rows"]], [
            ("mode", "Mode", "Plan", None),
            ("permission:allow:Read", "Read", None, {"text": "allow", "tone": "allow"})])
        row = section["rows"][0]
        self.assertEqual((row["icon"], row["tag"], row["warn"], row["dim"], row["agents"]),
                         ("shield", {"text": "Personal", "tone": "personal"}, False, False, ["claude"]))
        self.assertEqual(row["properties"]["lines"], [["From", "~/.claude/settings.json", "Personal"]])
        self.assertEqual([(a["id"], a["label"], a["path"]) for a in row["properties"]["actions"]],
                         [("open", "Open settings.json", user)])
        self.assertEqual(self.files(), before)                                   # read, never set
        # the file that wins tells it: the project's over the user's; a mode Claude has not is no row
        project = self.settings("project", permissions={"defaultMode": "acceptEdits"})
        row = self.section(self.layers(), "permissions")["rows"][0]
        self.assertEqual((row["note"], row["tag"]["text"], row["properties"]["actions"][0]["path"]),
                         ("Edit automatically", "Project", project))
        self.settings("project", permissions={"defaultMode": "everything"})
        self.assertEqual(self.section(self.layers(), "permissions")["rows"][0]["note"], "Plan")
        self.settings("user", permissions={"allow": ["Read"]})
        self.assertEqual([r["id"] for r in self.section(self.layers(), "permissions")["rows"]],
                         ["permission:allow:Read"])

    def test_the_cli_prints_the_layers(self):
        self.programs({"claude": {}})
        session = self.lumen()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(agent_setup.main(["agent_setup.py", "layers", "claude", self.folder, session]), 0)
            self.assertEqual(agent_setup.main(["agent_setup.py", "layers", "codex", self.folder]), 0)
        claude, codex = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(sorted(claude), ["agent", "connect", "folder", "head", "health", "sections", "states"])
        self.assertEqual((claude["agent"], claude["folder"]), ("claude", self.folder))
        self.assertEqual(claude["health"]["text"], "22k loaded at start")
        self.assertEqual([r["used"] for r in self.section(claude, "skills")["rows"]], [False, True])
        self.assertIsNone(codex)                    # no Codex here
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in (["layers", "gemini", self.folder], ["layers", "codex", self.folder, session],
                         ["layers", "claude"]):
                self.assertEqual(agent_setup.main(["agent_setup.py"] + argv), 2)

    def test_a_checked_server_shows_claudes_answer_until_its_state_changes(self):
        """The app keeps check()'s answer with the state the server had then: the next read shows it over that state
        alone, the server first among the problems, its own state told beside."""
        self.programs({"claude": {}})
        self.project_file(sentry={"command": "npx", "args": ["-y", "@sentry/mcp-server"]})
        self.settings("local", enabledMcpjsonServers=["sentry"])

        def read(*more):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(agent_setup.main(["agent_setup.py", "layers", "claude", self.folder, *more]), 0)
            found = json.loads(out.getvalue())
            return found["states"], self.section(found, "connectors")["rows"][0], found["health"]["problems"]

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
            for argv in (["layers", "claude", self.folder, "--checked", "{"],
                         ["layers", "codex", self.folder, "--checked", "{}"]):
                self.assertEqual(agent_setup.main(["agent_setup.py"] + argv), 2)

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


if __name__ == "__main__":
    unittest.main()
