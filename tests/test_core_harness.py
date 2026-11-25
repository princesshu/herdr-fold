"""Tests for core/harness.py in a temporary home and folder: each form's plan (its choices, its layers, the lines it
takes out and puts in, when it applies, what overrides it, why it is refused) written nowhere until applied, what
agent_setup.py reads of it afterwards, Undo, and the command both clients run."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import PACKAGE, set_env

sys.path.insert(0, os.path.join(PACKAGE, "core"))
import agent_setup    # noqa: E402
import harness_edit    # noqa: E402
import harness    # noqa: E402


class Harness(unittest.TestCase):
    def setUp(self):
        top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, top)
        self.home = os.path.join(top, "home")
        self.folder = os.path.join(top, "work", "lumen-api")
        self.managed = os.path.join(top, "managed")     # the organization's folder, never this machine's own
        os.makedirs(self.folder)
        patch = mock.patch.object(agent_setup, "MANAGED_DIR", self.managed)
        patch.start()
        self.addCleanup(patch.stop)
        set_env(self, CODEX_HOME=None, ANTHROPIC_MODEL=None, CLAUDE_CODE_EFFORT_LEVEL=None)
        self.paths = {"managed": os.path.join(self.managed, "managed-settings.json"),
                      "user": os.path.join(self.home, ".claude", "settings.json"),
                      "project": os.path.join(self.folder, ".claude", "settings.json"),
                      "local": os.path.join(self.folder, ".claude", "settings.local.json"),
                      "codex": os.path.join(self.home, ".codex", "config.toml")}

    def put(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def settings(self, scope, **values):
        return self.put(self.paths[scope], json.dumps(values, indent=2))

    def read(self, scope):
        with open(self.paths[scope], encoding="utf-8") as f:
            return f.read() if scope == "codex" else json.load(f)

    def files(self):
        found = {}
        for base in (self.home, self.folder, self.managed):
            for here, _, names in os.walk(base):
                for name in names:
                    with open(os.path.join(here, name), encoding="utf-8") as f:
                        found[os.path.join(here, name)] = f.read()
        return found

    def plan(self, action, agent="claude", **asked):
        """The plan of ACTION, which writes nothing."""
        before = self.files()
        made = harness.plan(agent, self.folder, self.home, {"action": action, **asked})
        self.assertEqual(self.files(), before)
        json.dumps(made)                        # all of it goes to a client as JSON
        return made

    def save(self, action, agent="claude", **asked):
        """ACTION planned and applied: the plan, with what apply() answered as "saved"."""
        made = self.plan(action, agent, **asked)
        self.assertIsNone(made["error"])
        return {**made, "saved": harness_edit.apply(agent, self.folder, self.home, made["edits"])}

    def lines(self, made):
        return [(one["path"], one["lines"]) for one in made["changes"]]

    def field(self, made, key="value"):
        return next(one for one in made["fields"] if one["id"] == key)


class Mode(Harness):
    def test_the_form_opens_on_the_layer_that_sets_it(self):
        self.settings("project", permissions={"defaultMode": "acceptEdits"})
        made = self.plan("mode")
        mode = self.field(made)
        self.assertEqual((mode["label"], mode["kind"], mode["value"]), ("Mode", "choice", "acceptEdits"))
        self.assertEqual([(one["id"], one["label"], one["off"]) for one in mode["choices"]], [
            ("default", "Manual", None), ("acceptEdits", "Edit automatically", None), ("plan", "Plan", None),
            ("auto", "Auto", "Auto and Bypass permissions work only in Global"), ("dontAsk", "Don't ask", None),
            ("bypassPermissions", "Bypass", "Auto and Bypass permissions work only in Global")])
        self.assertEqual(mode["hint"], "Auto and Bypass permissions work only in Global")
        self.assertEqual(made["layers"], [
            {"id": "Global", "label": "Global", "path": "~/.claude/settings.json", "chosen": False},
            {"id": "Project", "label": "Project", "path": ".claude/settings.json", "chosen": True},
            {"id": "Local", "label": "Local", "path": ".claude/settings.local.json", "chosen": False}])
        self.assertEqual((made["saved"], made["cancel"], made["submit"], made["edits"], made["changes"]),
                         ("Saved in", "Cancel", None, [], []))
        self.assertEqual(self.field(self.plan("mode", layer="Global"))["hint"], None)

    def test_a_mode_is_saved_where_asked_and_read_back(self):
        self.settings("local", permissions={"defaultMode": "plan", "allow": ["Read"]})
        made = self.save("mode", layer="Project", value="acceptEdits")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["+", '"defaultMode": "acceptEdits"']])])
        self.assertEqual((made["when"], made["submit"]), ("From the next session", "Save"))
        self.assertEqual(made["warns"], ['Local sets "plan": it wins in this folder'])
        self.assertTrue(made["saved"]["applied"])
        made = self.save("mode", layer="Local", value="default")
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [
            ["-", '"defaultMode": "plan"'], ["+", '"defaultMode": "default"']])])
        self.assertEqual(made["warns"], [])
        self.assertEqual(agent_setup.mode_told(self.folder, self.home)["mode"], "default")
        self.assertEqual(self.read("local")["permissions"]["allow"], ["Read"])
        self.assertEqual(self.plan("mode", layer="Local", value="default")["edits"], [])

    def test_a_file_that_cannot_take_the_change_says_so_before_it_is_saved(self):
        self.put(self.paths["project"], '{"permissions": []}')
        os.makedirs(os.path.dirname(self.paths["user"]))
        os.symlink(self.paths["project"], self.paths["user"])
        for layer, error in (("Project", ".claude/settings.json is not written in a way herdr-fold changes: change it "
                              "in the file"),
                             ("Global", "~/.claude/settings.json is a link: change it where it lives")):
            made = self.plan("mode", layer=layer, value="plan")
            self.assertEqual((made["error"], made["edits"], made["changes"], made["submit"]), (error, [], [], None))

    def test_auto_and_bypass_are_the_global_files_alone(self):
        for layer in ("Project", "Local"):
            made = self.plan("mode", layer=layer, value="bypassPermissions")
            self.assertEqual((made["error"], made["edits"], made["submit"]),
                             ("Auto and Bypass permissions work only in Global", [], None))
        made = self.save("mode", layer="Global", value="auto")
        self.assertEqual(self.read("user"), {"permissions": {"defaultMode": "auto"}})

    def test_the_organizations_mode_is_said_to_win(self):
        self.settings("managed", permissions={"defaultMode": "default"})
        self.assertEqual(self.plan("mode", layer="Local", value="plan")["warns"],
                         ['Managed sets "default": it wins in this folder'])
        for asked in ({"value": "everything"}, {"layer": "Managed", "value": "plan"}, {"layer": "/tmp/x"}):
            with self.assertRaises(ValueError):
                self.plan("mode", **asked)


class Model(Harness):
    def test_an_effort_is_kept_where_its_model_reads_it(self):
        """Opus 5.5 and later read modelSettings.<id>.effortLevel and pass the one effortLevel by: the change line
        names the key written, by the model chosen, else the files', else the one the head says runs."""
        self.settings("project", model="opus", effortLevel="low")
        made = self.plan("model")
        self.assertEqual(self.field(made, "effort")["value"], None)            # the one effortLevel is not Opus's
        made = self.save("model", effort="high")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["+", '"modelSettings": {"claude-opus-5-5": {"effortLevel": "high"}}']])])
        self.assertEqual(self.read("project"), {"model": "opus", "effortLevel": "low",
                                                "modelSettings": {"claude-opus-5-5": {"effortLevel": "high"}}})
        self.assertEqual(agent_setup.claude_setup(self.folder, self.home)["effort"], "high")
        self.assertEqual(self.field(self.plan("model"), "effort")["value"], "high")
        made = self.plan("model", effort="xhigh")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["-", '"modelSettings": {"claude-opus-5-5": {"effortLevel": "high"}}'],
            ["+", '"modelSettings": {"claude-opus-5-5": {"effortLevel": "xhigh"}}']])])
        text = self.files()
        saved = harness_edit.apply("claude", self.folder, self.home, made["edits"])
        harness_edit.apply("claude", self.folder, self.home, saved["undo"])
        self.assertEqual(self.files(), text)
        # the model changed with it: the effort goes where the new one reads it
        made = self.plan("model", model="sonnet", effort="medium")
        self.assertEqual(self.lines(made)[0][1], [["-", '"model": "opus"'], ["+", '"model": "sonnet"'],
                                                  ["-", '"effortLevel": "low"'], ["+", '"effortLevel": "medium"']])
        made = self.plan("model", model="claude-opus-5-5[1m]", effort="medium", layer="Local")
        self.assertEqual(self.lines(made)[0][1][1], [
            "+", '"modelSettings": {"claude-opus-5-5": {"effortLevel": "medium"}}'])
        # no file names a model: the one the head says runs
        os.unlink(self.paths["project"])
        for runs, line in (("claude-opus-5-5", '"modelSettings": {"claude-opus-5-5": {"effortLevel": "low"}}'),
                           ("claude-sonnet-5-5", '"effortLevel": "low"'), (None, '"effortLevel": "low"')):
            made = self.plan("model", effort="low", **({"runs": runs} if runs else {}))
            self.assertEqual(self.lines(made), [(".claude/settings.json", [["+", line]])], runs)
        with self.assertRaises(ValueError):
            self.plan("model", runs="opus\n")

    def test_claudes_model_and_effort_are_two_lines_of_one_file(self):
        self.settings("project", model="sonnet", unknown=True)
        made = self.plan("model")
        self.assertEqual([(one["id"], one["label"]) for one in self.field(made, "model")["choices"]],
                         [("opus", "Opus"), ("sonnet", "Sonnet"), ("haiku", "Haiku")])
        self.assertEqual([one["label"] for one in self.field(made, "effort")["choices"]],
                         ["Low", "Medium", "High", "Extra high"])
        self.assertEqual((self.field(made, "model")["value"], self.field(made, "effort")["value"]), ("sonnet", None))
        self.assertTrue(made["layers"][1]["chosen"])
        made = self.save("model", model="haiku", effort="high")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["-", '"model": "sonnet"'], ["+", '"model": "haiku"'], ["+", '"effortLevel": "high"']])])
        self.assertEqual((made["when"], made["say"], made["now"]),
                         ("From the next session", ["/model haiku", "/effort high"], "Switch this chat now"))
        self.assertEqual(self.read("project"), {"model": "haiku", "unknown": True, "effortLevel": "high"})
        found = agent_setup.claude_setup(self.folder, self.home)
        self.assertEqual((found["model"], found["effort"]), ("haiku", "high"))
        self.assertTrue(harness_edit.apply("claude", self.folder, self.home, made["saved"]["undo"])["applied"])
        self.assertEqual(self.read("project"), {"model": "sonnet", "unknown": True})

    def test_a_model_by_its_id_is_a_choice_too_and_the_environment_wins(self):
        self.settings("user", model="claude-opus-5-5[1m]", env={"CLAUDE_CODE_EFFORT_LEVEL": "low"})
        set_env(self, ANTHROPIC_MODEL="claude-haiku-5-5")
        made = self.plan("model", effort="xhigh")
        self.assertEqual(self.field(made, "model")["choices"][-1],
                         {"id": "claude-opus-5-5[1m]", "label": "Opus 5.5", "off": None})
        self.assertEqual(made["warns"], ["ANTHROPIC_MODEL is set: it wins over every file",
                                         "CLAUDE_CODE_EFFORT_LEVEL is set: it wins over every file"])
        self.assertEqual(made["say"], ["/effort xhigh"])
        for asked in ({"model": "opus\n"}, {"effort": "max"}, {"model": ["opus"]}):
            with self.assertRaises(ValueError):
                self.plan("model", **asked)

    def test_codexs_are_lines_of_its_config(self):
        self.put(self.paths["codex"], 'profile = "deep"\nmodel = "gpt-5.2-codex"\n\n[tui]\nnotifications = true\n')
        made = self.plan("model", "codex")
        self.assertEqual([one["id"] for one in made["layers"] if one["chosen"]], ["Global"])
        self.assertEqual([(one["id"], one["path"]) for one in made["layers"]],
                         [("Global", "~/.codex/config.toml"), ("Project", ".codex/config.toml")])
        self.assertIn({"id": "gpt-5.2-codex", "label": "GPT-5.2 Codex", "off": None},
                      self.field(made, "model")["choices"])
        self.assertEqual([one["label"] for one in self.field(made, "effort")["choices"]],
                         ["Low", "Medium", "High", "Extra high", "Max"])
        made = self.save("model", "codex", model="gpt-5.2", effort="max")
        self.assertEqual(made["changes"], [{"path": "~/.codex/config.toml", "lines": [
            ["-", 'model = "gpt-5.2-codex"'], ["+", 'model = "gpt-5.2"'], ["+", 'model_reasoning_effort = "max"']]}])
        self.assertEqual((made["when"], made["say"], made["now"]), ("From the next session", [], None))
        self.assertEqual(made["warns"], ["Profile deep wins over Global, not over Project"])
        self.assertEqual(self.read("codex"), 'profile = "deep"\nmodel = "gpt-5.2"\nmodel_reasoning_effort = "max"\n\n'
                         '[tui]\nnotifications = true\n')
        # a project's file is read once Codex trusts the folder: said until then, and it is over a profile
        self.assertEqual(self.plan("model", "codex", layer="Project", model="gpt-5.2")["warns"],
                         ["Codex reads it once it trusts lumen-api"])
        self.put(self.paths["codex"], f'[projects.{json.dumps(self.folder)}]\ntrust_level = "trusted"\n')
        made = self.save("model", "codex", layer="Project", model="gpt-5.3-codex")
        self.assertEqual((made["warns"], self.lines(made)), ([], [(".codex/config.toml", [
            ["+", 'model = "gpt-5.3-codex"']])]))
        self.assertEqual(agent_setup.codex_config(self.home, self.folder)["model"], "gpt-5.3-codex")
        self.assertTrue(self.plan("model", "codex")["layers"][1]["chosen"])


class Sandbox(Harness):
    def test_claudes_sandbox_is_a_switch_and_each_layers_hosts(self):
        self.settings("user", sandbox={"network": {"allowedDomains": ["github.com"]}},
                      permissions={"allow": ["WebFetch(domain:docs.lumen.example)"]})
        self.settings("project", sandbox={"enabled": True, "network": {"allowedDomains": ["pypi.org"]}})
        made = self.plan("sandbox")
        self.assertEqual([(one["id"], one["label"], one["kind"], one["value"]) for one in made["fields"]],
                         [("on", "Bash sandbox", "switch", True), ("add", "Hosts", "text", "")])
        self.assertEqual(self.field(made, "add")["items"], [
            {"host": "github.com", "layer": "Global", "rule": None},
            {"host": "docs.lumen.example", "layer": "Global", "rule": "WebFetch(domain:docs.lumen.example)"},
            {"host": "pypi.org", "layer": "Project", "rule": None}])
        self.assertEqual(made["more"], {"label": "More options", "path": self.paths["project"]})
        made = self.save("sandbox", add=" files.pythonhosted.org ")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["+", 'allowedDomains "files.pythonhosted.org"']])])
        self.assertEqual(made["when"], "Applies now · adds to Global's hosts")
        self.assertEqual(agent_setup.sandbox(self.folder, self.home)["hosts"],
                         ["github.com", "docs.lumen.example", "pypi.org", "files.pythonhosted.org"])
        made = self.save("sandbox", layer="Global", remove="github.com")
        self.assertEqual(self.lines(made), [("~/.claude/settings.json", [["-", 'allowedDomains "github.com"']])])
        self.assertEqual(made["when"], "Applies now")
        made = self.save("sandbox", on=False)
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["-", '"enabled": true'],
                                                                       ["+", '"enabled": false']])])
        self.assertFalse(agent_setup.sandbox(self.folder, self.home)["on"])

    def test_a_host_is_checked_before_it_is_offered(self):
        self.settings("user", sandbox={"network": {"allowedDomains": ["github.com"]}})
        for host, error in (("github.com", "Already in Global"), ("not a host", "Not a host's name"),
                            ("https://pypi.org/simple", "Not a host's name")):
            made = self.plan("sandbox", add=host)
            self.assertEqual((made["error"], made["edits"], made["submit"]), (error, [], None))
        self.assertIsNone(self.plan("sandbox", add="*.lumen.example")["error"])
        for asked in ({"on": 1}, {"remove": "github.com"}, {"layer": "Global", "remove": "pypi.org"}):
            with self.assertRaises(ValueError):                 # a host is taken out of its own layer alone
                self.plan("sandbox", **asked)

    def test_codexs_sandbox_and_approval(self):
        self.put(self.paths["codex"], 'sandbox_mode = "workspace-write"\napproval_policy = "on-failure"\n')
        made = self.plan("sandbox", "codex")
        self.assertEqual([(one["id"], one["label"]) for one in self.field(made)["choices"]], [
            ("read-only", "Read only"), ("workspace-write", "Workspace write"), ("danger-full-access", "Full access")])
        self.assertEqual((self.field(made)["label"], self.field(made)["value"]), ("Sandbox", "workspace-write"))
        made = self.save("sandbox", "codex", value="danger-full-access")
        self.assertEqual(made["changes"][0]["lines"], [["-", 'sandbox_mode = "workspace-write"'],
                                                       ["+", 'sandbox_mode = "danger-full-access"']])
        self.assertRegex(made["warns"][0], r"^No sandbox: commands can change any file on this (Mac|computer) and "
                         r"reach the network$")
        self.assertEqual(agent_setup.codex_config(self.home)["sandbox_mode"], "danger-full-access")
        made = self.plan("approval", "codex")
        self.assertEqual([(one["id"], one["label"], one["off"]) for one in self.field(made)["choices"]], [
            ("on-request", "Ask on request", None), ("never", "Never ask", None),
            ("granular", "Granular", "Granular is set in the file")])
        self.assertEqual((self.field(made)["label"], self.field(made)["value"]), ("Approval", "on-failure"))
        self.assertEqual(self.plan("approval", "codex", value="granular")["error"], "Granular is set in the file")
        self.save("approval", "codex", value="never")
        self.assertEqual(agent_setup.codex_config(self.home)["approval_policy"], "never")
        with self.assertRaises(ValueError):
            self.plan("trust", "codex", value="untrusted")      # a folder's trust is not changed from here

    def test_a_granular_approval_is_the_files(self):
        self.put(self.paths["codex"], "[approval_policy.granular]\nrules = true\n")
        made = self.plan("approval", "codex", value="never")
        self.assertEqual((made["error"], made["edits"]), (
            "~/.codex/config.toml is not written in a way herdr-fold changes: change it in the file", []))


class Rules(Harness):
    def test_a_rule_is_added_where_asked_and_what_hides_it_is_said(self):
        self.settings("user", permissions={"deny": ["Bash(npm *)"]})
        made = self.plan("rule")
        self.assertEqual([(one["id"], one["label"], one["kind"], one["value"]) for one in made["fields"]],
                         [("rule", "Rule", "text", ""), ("behavior", "Behavior", "choice", "allow")])
        self.assertEqual([one["id"] for one in made["layers"] if one["chosen"]], ["Project"])
        made = self.save("rule", rule=" Bash(npm run test:*) ", behavior="allow")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["+", 'allow "Bash(npm run test:*)"']])])
        self.assertEqual((made["when"], made["submit"], made["remove"]), ("Applies now", "Add", None))
        self.assertEqual(made["warns"], ["deny Bash(npm *) in Global hides it: this rule would never apply"])
        found = agent_setup.permissions(self.folder, self.home)
        self.assertEqual([(one["rule"], one["behavior"], one["scope"]) for one in found["rules"]],
                         [("Bash(npm *)", "deny", "Global"), ("Bash(npm run test:*)", "allow", "Project")])
        self.assertEqual(self.plan("rule", rule="Bash(npm run test:*)")["error"], "Already in Project")
        self.assertEqual(self.plan("rule", rule="Bash(npm run test:*)", layer="Local")["warns"], made["warns"])
        self.assertEqual(self.plan("rule", rule="not a rule (")["error"], "Not a rule Claude takes")
        self.assertEqual(self.plan("rule", rule="Read", behavior="ask", layer="Local")["warns"], [])

    def test_a_rule_is_changed_in_place_or_moved_to_another_layer(self):
        self.settings("project", permissions={"allow": ["Read", "Bash(pytest:*)", "Edit"]})
        was = {"rule": "Bash(pytest:*)", "behavior": "allow", "layer": "Project"}
        made = self.plan("rule", was=was)
        self.assertEqual((self.field(made, "rule")["value"], self.field(made, "behavior")["value"], made["remove"],
                          made["edits"]), ("Bash(pytest:*)", "allow", "Remove", []))
        self.assertEqual(self.plan("rule", was=was, rule="Bash(pytest:*)")["edits"], [])
        made = self.plan("rule", was=was, rule="Bash(python -m pytest:*)", layer="Local")
        self.assertEqual(self.lines(made), [
            (".claude/settings.json", [["-", 'allow "Bash(pytest:*)"']]),
            (".claude/settings.local.json", [["+", 'allow "Bash(python -m pytest:*)"']])])
        self.assertEqual((made["submit"], made["when"]), ("Save", "Applies now"))
        made = self.save("rule", was=was, rule="Bash(python -m pytest:*)")
        self.assertEqual(self.read("project")["permissions"]["allow"], ["Read", "Bash(python -m pytest:*)", "Edit"])
        made = self.save("rule", was={**was, "rule": "Bash(python -m pytest:*)"}, behavior="ask")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["-", 'allow "Bash(python -m pytest:*)"'], ["+", 'ask "Bash(python -m pytest:*)"']])])
        self.assertEqual(self.read("project")["permissions"], {"allow": ["Read", "Edit"],
                                                               "ask": ["Bash(python -m pytest:*)"]})
        self.assertEqual(self.plan("rule", was=was, rule="Bash(tox:*)")["error"], "No longer in Project")

    def test_a_rule_is_removed_after_one_question_and_comes_back(self):
        self.settings("project", permissions={"ask": ["Bash(curl:*)"], "allow": ["Read"]})
        text = self.files()
        was = {"rule": "Bash(curl:*)", "behavior": "ask", "layer": "Project"}
        made = self.save("rule", was=was, remove=True)
        self.assertEqual((made["ask"], made["submit"], made["done"], made["undo"], made["warns"]), (
            "Remove from Project?", "Remove", "Removed Bash(curl:*) from Project", "Undo", []))
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["-", 'ask "Bash(curl:*)"']])])
        self.assertEqual(self.read("project")["permissions"]["ask"], [])
        self.assertTrue(harness_edit.apply("claude", self.folder, self.home, made["saved"]["undo"])["applied"])
        self.assertEqual(self.files(), text)
        self.put(os.path.join(self.folder, ".git", "HEAD"), "ref: refs/heads/main\n")
        self.assertEqual(self.plan("rule", was=was, remove=True)["warns"],
                         ["In git: your team gets it with your next commit"])

    def test_the_organizations_rule_is_locked_and_codexs_is_its_files(self):
        self.settings("managed", permissions={"deny": ["Read(./.env)"]})
        was = {"rule": "Read(./.env)", "behavior": "deny", "layer": "Managed"}
        for asked in ({}, {"remove": True}, {"rule": "Read(./.env.example)"}):
            made = self.plan("rule", was=was, **asked)
            self.assertEqual((made["error"], made["edits"], made["layers"], made["submit"]),
                             ("Set by your organization", [], [], None))
        made = self.plan("rule", "codex", was={"rule": "git push", "behavior": "ask", "layer": "Global"})
        self.assertEqual((made["error"], made["edits"]),
                         ("Codex keeps its rules in a file of their own: change it there", []))
        for asked in ({"was": {"rule": "Read"}}, {"remove": True}, {"rule": "Read", "behavior": "forbid"},
                      {"rule": "Read", "layer": "Managed"}, {"was": "Read"}):
            with self.assertRaises(ValueError):
                self.plan("rule", **asked)

    def test_a_conflict_is_resolved_one_of_two_ways(self):
        self.settings("user", permissions={"allow": ["Bash(git push:*)"]})
        self.settings("project", permissions={"deny": ["Bash(git:*)", "Read(./.env)"]})
        made = self.plan("conflict", behavior="allow", rule="Bash(git push:*)")
        way = self.field(made, "way")
        self.assertEqual((way["label"], way["value"], made["layers"], made["edits"]),
                         ("deny in Project hides allow in Global", None, [], []))
        self.assertEqual([(one["id"], one["label"], one["off"]) for one in way["choices"]],
                         [("remove", "Remove the deny in Project", None), ("narrow", "Narrow the deny", None)])
        made = self.plan("conflict", behavior="allow", rule="Bash(git push:*)", way="remove")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["-", 'deny "Bash(git:*)"']])])
        self.assertEqual((made["when"], made["submit"]), ("Applies now", "Save"))
        narrow = lambda to=None: self.plan("conflict", behavior="allow", rule="Bash(git push:*)", way="narrow", to=to)
        self.assertEqual((self.field(narrow(), "to")["label"], self.field(narrow(), "to")["value"], narrow()["edits"]),
                         ("Rule", "Bash(git:*)", []))
        self.assertEqual(narrow("Bash(git:*)")["error"], "Not narrower than Bash(git:*)")
        self.assertEqual(narrow("Bash(npm:*)")["error"], "Not narrower than Bash(git:*)")
        self.assertEqual(narrow("Bash(git push:*)")["error"], "Still hides allow Bash(git push:*)")
        self.assertEqual(narrow("Bash(")["error"], "Not a rule Claude takes")
        made = narrow("Bash(git reset:*)")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [
            ["-", 'deny "Bash(git:*)"'], ["+", 'deny "Bash(git reset:*)"']])])
        harness_edit.apply("claude", self.folder, self.home, made["edits"])
        self.assertEqual(self.read("project")["permissions"]["deny"], ["Bash(git reset:*)", "Read(./.env)"])
        self.assertEqual(agent_setup.permissions(self.folder, self.home)["conflicts"], [])
        self.assertEqual(self.plan("conflict", behavior="allow", rule="Bash(git push:*)")["error"],
                         "No longer hidden")

    def test_the_organizations_deny_stays(self):
        self.settings("managed", permissions={"deny": ["Bash(git:*)"]})
        self.settings("user", permissions={"allow": ["Bash(git push:*)"]})
        made = self.plan("conflict", behavior="allow", rule="Bash(git push:*)", way="remove")
        self.assertEqual((made["error"], made["edits"]), ("Set by your organization", []))
        self.assertEqual({one["off"] for one in self.field(made, "way")["choices"]}, {"Set by your organization"})


class Switches(Harness):
    def test_a_skill_is_turned_off_in_this_folder_and_on_again(self):
        self.put(os.path.join(self.home, ".claude", "skills", "release-notes", "SKILL.md"),
                 "---\nname: release-notes\ndescription: when you ask for notes\n---\n")
        made = self.plan("skill", name="release-notes")
        self.assertEqual(self.field(made, "on"), {
            "id": "on", "label": "On in lumen-api", "short": "On here", "kind": "switch", "value": True,
            "turn": {"on": "Turn on in lumen-api", "off": "Turn off in lumen-api"}})
        self.assertEqual([(one["id"], one["chosen"]) for one in made["layers"]], [("Project", False), ("Local", True)])
        made = self.save("skill", name="release-notes", on=False)
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [
            ["+", '"skillOverrides": {"release-notes": "off"}']])])
        self.assertEqual(made["when"], "From the next session")
        self.assertEqual(self.read("local"), {"skillOverrides": {"release-notes": "off"}})
        self.assertEqual(agent_setup.turned_off(self.folder, self.home), {
            "skills": ["release-notes"], "agents": [], "servers": [], "hooks": False})
        self.assertEqual([one["off"] for one in agent_setup.claude_setup(self.folder, self.home)["skills"]], [True])
        self.assertFalse(self.field(self.plan("skill", name="release-notes"), "on")["value"])
        self.assertEqual(self.plan("skill", name="release-notes", on=False)["edits"], [])
        self.save("skill", name="release-notes", on=False, layer="Project")
        made = self.save("skill", name="release-notes", on=True)
        self.assertEqual(self.lines(made), [
            (".claude/settings.json", [["-", '"skillOverrides": {"release-notes": "off"}']]),
            (".claude/settings.local.json", [["-", '"skillOverrides": {"release-notes": "off"}']])])
        self.assertEqual(made["layers"], [])
        self.assertEqual(agent_setup.turned_off(self.folder, self.home)["skills"], [])
        for asked in ({"name": "release-notes", "on": False, "layer": "Global"}, {"name": ""}, {"on": False},
                      {"name": "release-notes", "on": "off"}):
            with self.assertRaises(ValueError):
                self.plan("skill", **asked)

    def test_a_plugins_skill_turns_off_with_its_plugin(self):
        root = os.path.join(self.home, ".claude", "plugins", "cache", "acme-tools", "pr-review")
        self.put(os.path.join(root, "skills", "review-pr", "SKILL.md"), "---\nname: review-pr\n---\n")
        self.put(os.path.join(self.home, ".claude", "plugins", "installed_plugins.json"), json.dumps(
            {"plugins": {"pr-review@acme-tools": [{"scope": "user", "installPath": root}]}}))
        self.settings("user", enabledPlugins={"pr-review@acme-tools": True})
        made = self.plan("skill", name="review-pr", on=False)
        self.assertEqual((made["error"], made["edits"]), ("Turns off with its plugin", []))

    def test_a_sub_agent_is_turned_off_by_a_deny_rule(self):
        self.settings("user", permissions={"deny": ["Agent(Explore)"]})
        made = self.save("subagent", name="doc-checker", on=False, layer="Project")
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["+", 'deny "Agent(doc-checker)"']])])
        self.assertEqual(agent_setup.turned_off(self.folder, self.home)["agents"], ["Explore", "doc-checker"])
        made = self.save("subagent", name="Explore", on=True)
        self.assertEqual(self.lines(made), [("~/.claude/settings.json", [["-", 'deny "Agent(Explore)"']])])
        self.settings("managed", permissions={"deny": ["Agent(doc-checker)"]})
        made = self.plan("subagent", name="doc-checker", on=True)
        self.assertEqual((made["error"], made["edits"]), ("Set by your organization", []))
        with self.assertRaises(ValueError):
            self.plan("subagent", name="a) Bash(", on=False)

    def test_every_hook_is_turned_off_in_one_files_reach(self):
        made = self.plan("hooks")
        self.assertEqual((self.field(made, "on")["label"], self.field(made, "on")["short"],
                          self.field(made, "on")["value"]), ("All hooks in lumen-api", "All hooks here", True))
        self.assertEqual([(one["id"], one["chosen"]) for one in made["layers"]],
                         [("Global", False), ("Project", False), ("Local", True)])
        made = self.save("hooks", on=False)
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [["+", '"disableAllHooks": true']])])
        self.assertEqual((made["when"], made["warns"]), ("Applies now", [
            "Also stops herdr-fold's own hook: decisions go back to Claude's terminal"]))
        self.assertTrue(agent_setup.turned_off(self.folder, self.home)["hooks"])
        self.assertEqual(agent_setup.hooks(self.folder, self.home), [])
        made = self.save("hooks", on=True)
        self.assertEqual((self.lines(made), made["warns"]),
                         ([(".claude/settings.local.json", [["-", '"disableAllHooks": true']])], []))
        self.assertEqual(self.read("local"), {})


class Connectors(Harness):
    def setUp(self):
        super().setUp()
        self.state = self.put(os.path.join(self.home, ".claude.json"), json.dumps({
            "mcpServers": {"github": {"type": "http", "url": "https://mcp.github.example/mcp"}},
            "projects": {self.folder: {"disabledMcpServers": ["chrome-devtools"]}}}))
        self.put(os.path.join(self.folder, ".mcp.json"), json.dumps({"mcpServers": {
            "lumen-db": {"command": "node", "args": ["scripts/db-mcp.js"]}, "sentry": {"command": "sentry-mcp"}}}))
        self.settings("project", enabledMcpjsonServers=["sentry"])

    def tearDown(self):
        with open(self.state, encoding="utf-8") as f:           # Claude's own state is read, never written
            self.assertIn("chrome-devtools", f.read())

    def state_of(self, name):
        return next(one["state"] for one in agent_setup.claude_setup(self.folder, self.home)["servers"]
                    if one["name"] == name)

    def test_a_server_is_denied_in_this_folder_and_let_back(self):
        made = self.save("connector", name="github", on=False, starts=34200, tokens=6800)
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [
            ["+", 'deniedMcpServers {"serverName": "github"}']])])
        self.assertEqual(made["when"], "From the next session · new chats start at ~27.4k")
        self.assertEqual(agent_setup.turned_off(self.folder, self.home)["servers"], ["github"])
        self.assertEqual(self.state_of("github"), "off here")
        self.assertFalse(self.field(self.plan("connector", name="github"), "on")["value"])
        made = self.save("connector", name="github", on=True)
        self.assertEqual((self.lines(made), made["when"], made["say"]), ([(".claude/settings.local.json", [
            ["-", 'deniedMcpServers {"serverName": "github"}']])], "From the next session", []))
        self.assertEqual(self.plan("connector", name="claude.ai Box", on=False, layer="Project")["edits"], [
            {"layer": "Project", "key": ["deniedMcpServers"], "add": {"serverName": "claude.ai Box"}}])

    def test_one_claudes_own_state_turns_off_is_turned_on_in_a_chat(self):
        made = self.plan("connector", name="chrome-devtools", on=True)
        self.assertEqual((made["say"], made["edits"], made["error"]), (["/mcp enable chrome-devtools"], [], None))

    def test_a_projects_server_is_approved_or_kept_off(self):
        self.assertEqual(self.state_of("lumen-db"), "not approved")
        made = self.plan("connector", name="lumen-db")
        self.assertEqual((self.field(made, "on")["value"], self.field(made, "on")["turn"]),
                         (False, {"on": "Approve in lumen-api", "off": "Keep off"}))
        made = self.save("connector", name="lumen-db", on=False)
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [
            ["+", 'disabledMcpjsonServers "lumen-db"']])])
        self.assertEqual(self.state_of("lumen-db"), "off here")
        made = self.save("connector", name="lumen-db", on=True)
        self.assertEqual(self.lines(made), [(".claude/settings.local.json", [
            ["-", 'disabledMcpjsonServers "lumen-db"'], ["+", 'enabledMcpjsonServers "lumen-db"']])])
        self.assertEqual(made["when"], "From the next session")
        self.assertNotIn(self.state_of("lumen-db"), ("not approved", "off here"))
        self.assertEqual(self.field(self.plan("connector", name="lumen-db"), "on")["turn"],
                         {"on": "Turn on in lumen-api", "off": "Turn off in lumen-api"})
        made = self.save("connector", name="sentry", on=False, layer="Project")
        self.assertEqual(self.read("project"), {"enabledMcpjsonServers": ["sentry"],
                                                "disabledMcpjsonServers": ["sentry"]})
        self.assertEqual(self.state_of("sentry"), "off here")
        made = self.save("connector", name="sentry", on=True)
        self.assertEqual(self.lines(made), [(".claude/settings.json", [["-", 'disabledMcpjsonServers "sentry"']])])

    def test_the_organizations_server_is_locked(self):
        self.put(os.path.join(self.managed, "managed-mcp.json"),
                 json.dumps({"mcpServers": {"audit": {"command": "audit-mcp"}}}))
        made = self.plan("connector", name="audit", on=False)
        self.assertEqual((made["error"], made["edits"]), ("Set by your organization", []))


class Command(Harness):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(os.path, "expanduser", lambda path: path.replace("~", self.home, 1)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = harness.main(["harness.py", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_a_plan_is_answered_in_json_and_writes_nothing(self):
        self.settings("project", permissions={"allow": ["Read"]})
        text = self.files()
        code, out, _ = self.run_main("plan", "claude", self.folder, json.dumps(
            {"action": "rule", "rule": "Bash(pytest:*)", "behavior": "allow", "layer": "Project"}))
        made = json.loads(out)
        self.assertEqual((code, made["submit"], made["when"], self.files()), (0, "Add", "Applies now", text))
        self.assertEqual(made["edits"], [{"layer": "Project", "key": ["permissions", "allow"],
                                          "add": "Bash(pytest:*)"}])
        self.assertEqual(made["changes"], [{"path": ".claude/settings.json",
                                            "lines": [["+", 'allow "Bash(pytest:*)"']]}])

    def test_edits_are_made_and_taken_back_through_the_command(self):
        self.settings("user", permissions={"allow": ["Read"]})
        text = self.files()
        code, out, _ = self.run_main("apply", "claude", self.folder, json.dumps(
            [{"layer": "Global", "key": ["permissions", "allow"], "add": "Bash(pytest:*)"}]))
        saved = json.loads(out)
        self.assertEqual((code, saved["applied"], saved["error"]), (0, True, None))
        self.assertEqual(self.read("user")["permissions"]["allow"], ["Read", "Bash(pytest:*)"])
        code, out, _ = self.run_main("apply", "claude", self.folder, json.dumps(saved["undo"]))
        self.assertEqual((code, json.loads(out)["applied"], self.files()), (0, True, text))
        code, out, _ = self.run_main("apply", "claude", self.folder, json.dumps(saved["undo"]))
        self.assertEqual((code, json.loads(out)), (0, {
            "applied": False, "undo": [], "error": "~/.claude/settings.json changed since: nothing saved"}))
        self.assertEqual(self.files(), text)

    def test_what_no_form_makes_is_the_usage(self):
        self.put(self.paths["project"], '{"hooks": {}}')
        before = self.files()
        hook = [{"layer": "Project", "key": ["hooks"], "before": {}, "after": None}]
        path = [{"layer": self.paths["project"], "key": ["model"], "before": None, "after": "opus"}]
        for argv in (["apply", "claude", self.folder, "["], ["apply", "claude", self.folder, "[]"],
                     ["apply", "claude", self.folder, "{}"], ["apply", "claude", self.folder, json.dumps(hook)],
                     ["apply", "claude", self.folder, json.dumps(path)], ["apply", "claude", "lumen-api", "[]"],
                     ["apply", "gemini", self.folder, json.dumps(path)], ["apply", "claude", self.folder],
                     ["plan", "claude", self.folder, "{"], ["plan", "claude", self.folder, '{"action": "hook"}'],
                     ["plan", "gemini", self.folder, '{"action": "model"}'],
                     ["plan", "codex", self.folder, '{"action": "mode"}'],
                     ["plan", "claude", "lumen-api", '{"action": "mode"}'],
                     ["plan", "claude", self.folder, '["mode"]'],
                     ["plan", "claude", self.folder, '{"action": "mode", "layer": "Managed"}'],
                     ["off", self.folder], ["plan"], []):
            code, out, err = self.run_main(*argv)
            self.assertEqual((code, out, err), (2, "", "usage: harness.py plan AGENT FOLDER REQUEST | apply AGENT "
                             "FOLDER EDITS\n"), argv)
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
