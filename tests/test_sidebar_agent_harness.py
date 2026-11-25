"""Tests for the Agent view's forms (agent_form.py under layers.py's chosen item; agent_panel.py plans and saves):
core's plans in cells as harness-editing.html's TUI frames, their keys and presses, the save, the foot line and its
Undo, the rows core marks off; all in a temporary home and folder."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_jobs, set_attrs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import agent_layers  # noqa: E402
import agent_setup  # noqa: E402
import agent_state  # noqa: E402
import harness  # noqa: E402
import layers  # noqa: E402
import sidebar  # noqa: E402
import widgets  # noqa: E402
from screen import Canvas  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

LEAST = 43                    # the cells a tab's sidebar takes at least (column.py's FEWEST)
WIDE = 60
MODE, SANDBOX, HOOKS = ("row", "mode"), ("row", "sandbox"), ("group", "hooks")
CURL, PYTEST = ("row", "permission:ask:Bash(curl:*)"), ("row", "permission:allow:Bash(pytest:*)")
CONFLICT = ("row", "conflict:allow:Bash(git push:*)")
GLOBAL = {"model": "opus", "permissions": {"allow": ["Bash(git push:*)", "Bash(pytest:*)"]},
          "sandbox": {"network": {"allowedDomains": ["github.com"]}}}
PROJECT = {"permissions": {"defaultMode": "acceptEdits", "ask": ["Bash(curl:*)"], "deny": ["Bash(git push:*)"]},
           "sandbox": {"enabled": True, "network": {"allowedDomains": ["pypi.org"]}},
           "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command",
                                                                  "command": "./scripts/guard.sh"}]}]}}
SKILL = "---\nname: release-notes\ndescription: when you ask for notes\n---\nWrite them.\n"
CHECKER = "---\nname: doc-checker\ndescription: checks the docs\nmodel: haiku\ntools: Read, Grep\n---\nCheck.\n"
CODEX = 'model = "gpt-5.2-codex"\napproval_policy = "on-request"\nsandbox_mode = "workspace-write"\n'


class Home(unittest.TestCase):
    """A temporary home and lumen-api folder with Claude's settings in three files; the view reads them through core,
    and plan() does what the family does before a draw."""

    agent = "claude"

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.home, self.state = os.path.join(tmp, "home"), os.path.join(tmp, "state")
        self.folder = os.path.realpath(os.path.join(tmp, "lumen-api"))
        set_attrs(self, agent_setup, MANAGED_DIR=os.path.join(tmp, "managed"))
        set_env(self, HOME=self.home, HERDR_PANE_ID=None, CODEX_HOME=None, HERDR_WORKSPACE_ID=None,
                ANTHROPIC_MODEL=None, CLAUDE_CODE_EFFORT_LEVEL=None)
        ticks = iter(range(10 ** 6))
        set_attrs(self, widgets, TURNS=widgets.Turns(clock=lambda: float(next(ticks))))
        self.globals = self.put(os.path.join(self.home, ".claude", "settings.json"), GLOBAL)
        self.project = self.put(os.path.join(self.folder, ".claude", "settings.json"), PROJECT)
        self.local = os.path.join(self.folder, ".claude", "settings.local.json")
        self.put(os.path.join(self.folder, ".claude", "skills", "release-notes", "SKILL.md"), SKILL)
        self.put(os.path.join(self.folder, ".claude", "agents", "doc-checker.md"), CHECKER)
        self.put(os.path.join(self.folder, ".mcp.json"), {"mcpServers": {"sentry": {"command": "npx"}}})
        self.put(os.path.join(self.home, ".codex", "config.toml"), CODEX)
        self.view = layers.Layers(icons=True, folded=())
        self.read()

    def put(self, path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body if isinstance(body, str) else json.dumps(body, indent=2) + "\n")
        return path

    def raw(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def kept(self, path):
        return json.loads(self.raw(path))

    def read(self):
        setup = agent_setup.claude_setup(self.folder, self.home, None) if self.agent == "claude" \
            else agent_setup.codex_setup(self.folder, self.home)
        self.view.set({"agent": self.agent, "folder": self.folder, "agents": [], "claude": True,
                       **agent_layers.layers(setup, self.agent, self.folder, self.home)})
        self.plan()

    def plan(self):
        asked = self.view.asks()
        if asked is not None:
            try:
                made = harness.plan(self.agent, self.folder, self.home, asked)
            except ValueError:
                made = None
            self.view.planned(asked, made)

    def press(self, *keys):
        """KEYS pressed, each planned; what the last one asked for."""
        for key in keys:
            action = self.view.handle(Key(key) if len(key) > 1 else Key("char", key))
            self.plan()
        return action

    def type(self, words):
        self.press(*words)

    def choose(self, key):
        self.press("home")
        for _ in range(80):
            if self.view.chosen == key:
                return
            self.press("down")
        self.fail(f"{key} never chosen")

    def save(self, action, undone=False):
        """What the family does with a save: core's apply(), the view told, the setup read again."""
        said = harness.apply(self.agent, self.folder, self.home, action.args[0])
        self.view.saved(said, undone)
        self.read()
        return said

    def draw(self, cells=WIDE, rows=70):
        canvas = Canvas(cells, rows)
        self.view.draw(canvas, 0, rows, True)
        return canvas

    def at(self, canvas, words):
        for y in range(canvas.height):
            if words in text(canvas, y):
                return y, text(canvas, y).index(words)
        self.fail(f"{words!r} not drawn:\n" + "\n".join(text(canvas, y).rstrip() for y in range(canvas.height)))

    def under(self, words, rows, cells=WIDE):
        """The ROWS lines under the one WORDS are on, without their indent."""
        canvas = self.draw(cells)
        y = self.at(canvas, words)[0]
        return [text(canvas, y + n).strip() for n in range(1, rows + 1)]

    def click(self, words, cells=WIDE):
        canvas = self.draw(cells)
        y, x = self.at(canvas, words)
        action = self.view.handle(Mouse("press", x, y, 0))
        self.plan()
        return action


class Choices(Home):
    """The mode, the model and the effort: a choice, its layer, the change, when, what overrides it, Save."""

    def test_the_chosen_mode_row_shows_its_choices_and_enter_puts_the_keys_in_them(self):
        self.choose(MODE)
        self.assertEqual(self.under("Mode Edit automatically", 3), [
            "From  .claude/settings.json", "Manual  Edit automatically  Plan  Auto  Don't ask", "Bypass"])
        self.assertFalse(self.view.editing)
        self.assertIsNone(self.press("enter"))                                  # no Open beside it: into the form
        self.assertTrue(self.view.editing)
        self.assertEqual(self.under("Mode Edit automatically", 4), [
            "Manual  Edit automatically  Plan  Auto  Don't ask", "Bypass",
            "Auto and Bypass permissions work only in Global", "Saved in ‹ Project ›  .claude/settings.json"])
        canvas = self.draw()
        y, x = self.at(canvas, "Edit automatically  Plan")
        self.assertEqual(canvas.cursor, (y, x))                                 # the keys in the one held
        held = canvas.rows[y][x][1]
        self.assertEqual((held.bg, held.bold), ("button", True))

    def test_right_chooses_tab_moves_the_layer_and_the_change_shows_before_save(self):
        self.choose(MODE)
        self.press("enter", "right", "tab")
        self.assertEqual(self.under("Bypass", 5)[1:], [
            "Saved in ‹ Local ›  .claude/settings.local.json", '+ "defaultMode": "plan"', "from the next session",
            "Save"])
        self.press("backtab")                                                   # in Project: over what it holds
        self.assertEqual(self.under("Saved in ‹ Project ›", 3), [
            '− "defaultMode": "acceptEdits"', '+ "defaultMode": "plan"', "from the next session"])
        self.assertEqual(self.press("enter"), Action("save_harness", ([
            {"layer": "Project", "key": ["permissions", "defaultMode"], "before": "acceptEdits", "after": "plan"}],)))

    def test_a_grey_choice_is_passed_over_and_a_stronger_layer_is_said_in_yellow(self):
        self.put(self.local, {"permissions": {"defaultMode": "plan"}})
        self.read()
        self.choose(MODE)
        self.press("enter", "backtab", "left")                                  # Project, where Auto is grey
        canvas = self.draw()
        self.assertEqual(canvas.rows[self.at(canvas, "Auto")[0]][self.at(canvas, "Auto")[1]][1].fg, "muted")
        self.press("end")
        self.press("right", "right", "right", "right", "right")                 # never onto Auto or Bypass
        self.assertEqual(self.view.edit.asked["value"], "dontAsk")
        y, x = self.at(self.draw(), 'Local sets "plan": it wins in this folder')
        self.assertEqual(self.draw().rows[y][x][1].fg, "modified")

    def test_saving_writes_the_file_shows_the_row_and_a_foot_line_whose_undo_puts_it_back(self):
        before = self.raw(self.project)
        self.choose(MODE)
        self.assertEqual(self.save(self.press("enter", "right", "enter"))["applied"], True)
        self.assertEqual(self.kept(self.project)["permissions"]["defaultMode"], "plan")
        self.assertFalse(self.view.editing)
        canvas = self.draw(rows=30)
        self.assertIn("Mode Plan", text(canvas, self.at(canvas, "Mode")[0]))
        self.assertEqual(text(canvas, 29).split(), ["from", "the", "next", "session", "u", "Undo"])
        self.assertIsNone(self.press("U"))                                      # Usage's key: none to open here
        self.assertTrue(self.view.foot)
        undo = self.press("u")
        self.assertEqual(undo.name, "undo_harness")
        self.save(undo, undone=True)
        self.assertEqual(self.raw(self.project), before)
        self.assertIsNone(self.view.foot)
        self.assertEqual(text(self.draw(rows=30), 29).strip(), "")

    def test_a_refused_save_says_cores_words_in_the_form_and_esc_leaves_it_as_it_opened(self):
        self.choose(MODE)
        save = self.press("enter", "right", "enter")
        self.put(self.project, {**PROJECT, "permissions": {"defaultMode": "dontAsk"}})      # changed meanwhile
        said = harness.apply("claude", self.folder, self.home, save.args[0])
        self.view.saved(said)
        self.assertEqual(said["error"], ".claude/settings.json changed since: nothing saved")
        self.assertIn(said["error"], self.under("from the next session", 1))
        self.assertTrue(self.view.editing)
        self.assertIsNone(self.view.foot)
        self.press("esc")
        self.assertFalse(self.view.editing)
        self.assertEqual(self.view.edit.asked, {"action": "mode"})

    def test_the_heads_line_opens_the_model_and_the_effort_and_offers_the_chat_its_command(self):
        self.assertEqual([key for key, _ in self.view.items()][:2], [layers.HEAD, layers.MODEL])
        self.choose(layers.MODEL)
        self.assertEqual(self.under("━━━", 2), ["Model   Opus  Sonnet  Haiku", "Effort  Low  Medium  High  Extra high"])
        self.press("enter", "right", "down", "right", "right")
        self.assertEqual(self.under("Effort  Low", 6), [
            "Saved in ‹ Global ›  ~/.claude/settings.json", '− "model": "opus"', '+ "model": "sonnet"',
            '+ "effortLevel": "medium"', "from the next session", "Save    Switch this chat now"])
        self.press("down")                                                      # onto the quiet button
        self.assertEqual(self.press("enter"), Action("type_command", ("/model sonnet",)))
        self.assertEqual(self.press("enter"), Action("type_command", ("/effort medium",)))
        self.view.answer["claude"] = False                                      # no Claude in the tab: not offered
        self.assertEqual(self.under("from the next session", 1), ["Save"])

    def test_a_mode_no_file_sets_is_claudes_default_tagged_so_and_saved_in_project_first(self):
        self.put(self.project, {})
        self.read()
        self.choose(MODE)
        canvas = self.draw()
        self.assertEqual(text(canvas, self.at(canvas, "Mode Manual")[0]).split()[-1], "Default")
        self.assertEqual(self.under("Mode Manual", 1), ["From  Claude's default"])
        self.press("enter", "right")
        self.assertEqual(self.view.edit.asked, {"action": "mode", "value": "default"})
        self.assertIn("Saved in ‹ Project ›  .claude/settings.json", self.under("Bypass", 3))

    def test_a_press_on_a_choice_makes_it_and_one_on_the_layers_file_opens_it(self):
        self.choose(MODE)
        self.assertIsNone(self.click("Plan"))
        self.assertTrue(self.view.editing)
        self.assertEqual(self.view.edit.asked, {"action": "mode", "value": "plan"})
        self.assertIsNone(self.click("‹ Project ›"))
        self.assertEqual(self.view.edit.asked["layer"], "Local")
        self.assertEqual(self.click(".claude/settings.local.json"), Action("open_layer", ("Local",)))
        self.assertEqual(self.click(" Save ").name, "save_harness")


class Sandbox(Home):
    def test_claudes_sandbox_is_a_switch_and_its_hosts_each_with_its_layer_a_new_one_typed(self):
        self.choose(SANDBOX)
        self.assertEqual(self.under("Sandbox Bash", 3), ["From   .claude/settings.json", "Hosts  github.com, pypi.org",
                                                         "Bash sandbox  on  off"])
        self.press("enter", "down", "down", "down")
        self.type("files.pythonhosted.org")
        self.assertEqual(self.under("Sandbox Bash", 8), [
            "Bash sandbox  on  off", "Hosts  github.com  Global  ×", "pypi.org  Project  ×", "files.pythonhosted.org",
            "Saved in ‹ Project ›  .claude/settings.json", '+ allowedDomains "files.pythonhosted.org"',
            "applies now · adds to Global's hosts", "Save    More options ›"])
        self.type("!")
        self.assertIn("Not a host's name", self.under("Saved in", 1))
        self.assertNotIn("Save", self.under("Not a host's name", 1)[0])

    def test_x_on_a_host_takes_it_out_of_its_own_layers_file_and_more_options_opens_the_file(self):
        self.choose(SANDBOX)
        self.press("enter", "down", "x")
        self.assertEqual(self.under("pypi.org  Project", 3)[1:], ["Saved in ‹ Global ›  ~/.claude/settings.json",
                                                                  '− allowedDomains "github.com"'])
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.globals)["sandbox"]["network"]["allowedDomains"], [])
        self.press("enter", "down", "down", "down")
        self.assertEqual(self.press("enter"), Action("open_layer", ("Project",)))


class Rules(Home):
    """A permission rule added, changed, moved, removed; a conflict's two ways; a locked one."""

    def test_a_on_permissions_adds_a_rule_under_its_head_and_says_what_hides_it(self):
        self.choose(MODE)
        self.assertIsNone(self.press("a"))
        self.assertEqual(self.view.chosen, ("section", "permissions"))
        self.type("Bash(git push:*)")
        self.assertEqual(self.under("Permissions", 7), [
            "Rule      Bash(git push:*)", "Behavior  allow  ask  deny", "Saved in ‹ Project ›  .claude/settings.json",
            '+ allow "Bash(git push:*)"', "applies now",
            "deny Bash(git push:*) in Project hides it: this rule", "would never apply"])
        self.press("esc")
        self.assertIsNone(self.view.edit)
        self.press("a")
        self.type("Bash(npm run test:*)")
        self.press("down", "right")
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.project)["permissions"]["ask"], ["Bash(curl:*)", "Bash(npm run test:*)"])
        self.assertIsNone(self.view.edit)

    def test_the_heads_plus_opens_the_same_form_and_a_elsewhere_still_adds_a_connector(self):
        canvas = self.draw()
        y = self.at(canvas, "Permissions")[0]
        self.assertTrue(text(canvas, y).rstrip().endswith("1 deny  +"))
        self.view.handle(Mouse("press", text(canvas, y).rindex("+"), y, 0))
        self.assertEqual((self.view.edit.key, self.view.edit.base), (("section", "permissions"), {"action": "rule"}))
        self.press("esc")
        self.choose(("section", "connectors"))
        self.press("a")
        self.assertTrue(self.view.form)

    def test_a_rule_is_changed_and_moved_between_layers_as_two_changes(self):
        self.choose(PYTEST)
        self.assertEqual(self.under("Bash(pytest:*)", 2), ["From  ~/.claude/settings.json",
                                                            "Behavior  allow  ask  deny"])
        self.press("enter", "backspace", "backspace", "backspace")
        self.type(" -q:*)")
        self.press("tab", "tab")
        self.assertEqual(self.under("Behavior  allow", 7), [
            "Saved in ‹ Local ›", "~/.claude/settings.json", '− allow "Bash(pytest:*)"',
            ".claude/settings.local.json", '+ allow "Bash(pytest -q:*)"', "applies now", "Save   x Remove"])
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.globals)["permissions"]["allow"], ["Bash(git push:*)"])
        self.assertEqual(self.kept(self.local)["permissions"]["allow"], ["Bash(pytest -q:*)"])

    def test_x_asks_once_before_a_removal_and_the_foot_says_it_with_undo(self):
        self.choose(CURL)
        self.assertIsNone(self.press("x"))
        self.assertEqual(self.under("Bash(curl:*)", 5), [
            "Remove from Project?", ".claude/settings.json", '− ask "Bash(curl:*)"', "applies now", "Remove"])
        self.press("esc")                                                       # not removed
        self.assertEqual(self.kept(self.project)["permissions"]["ask"], ["Bash(curl:*)"])
        self.press("x")
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.project)["permissions"]["ask"], [])
        canvas = self.draw(rows=30)
        self.assertEqual(text(canvas, 29).split("  ")[0].strip(), "Removed Bash(curl:*) from Project")
        y, x = self.at(canvas, "Undo")
        undo = self.view.handle(Mouse("press", x, y, 0))
        self.save(undo, undone=True)
        self.assertEqual(self.kept(self.project)["permissions"]["ask"], ["Bash(curl:*)"])

    def test_a_conflict_offers_its_two_ways_and_shows_the_chosen_ones_change_alone(self):
        self.choose(CONFLICT)
        lines = self.under("deny in Project hides", 4)                          # both rules, the ways, no Open
        self.assertEqual((lines[2], lines[3].split()[0]), ("Remove the deny in Project  Narrow the deny",
                                                           "Bash(pytest:*)"))
        self.press("enter", "right")
        self.assertEqual(self.under("Remove the deny in Project", 4), [
            ".claude/settings.json", '− deny "Bash(git push:*)"', "applies now", "Save"])
        self.press("right", "down", "backspace", "backspace", "backspace")
        self.type(" -f:*)")
        self.assertEqual(self.under("Remove the deny in Project", 6), [
            "Rule  Bash(git push -f:*)", ".claude/settings.json", '− deny "Bash(git push:*)"',
            '+ deny "Bash(git push -f:*)"', "applies now", "Save"])
        self.type("x")
        self.assertIn("Not a rule Claude takes", self.under("Rule  Bash(git push", 1))
        self.press("backspace")
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.project)["permissions"]["deny"], ["Bash(git push -f:*)"])

    def test_the_organizations_rule_is_locked_in_cores_words_with_its_file(self):
        managed = self.put(os.path.join(agent_setup.MANAGED_DIR, "managed-settings.json"),
                           {"permissions": {"deny": ["Read(./.env)"]}})
        self.read()
        self.choose(("row", "permission:deny:Read(./.env)"))
        lines = self.under("Read(./.env)", 3)
        self.assertEqual(lines[1], "Set by your organization")
        self.assertIn("Open managed-settings.json", lines[2])
        self.press("right")
        self.assertFalse(self.view.editing)
        self.assertEqual(self.press("enter"), Action("open_setup", (managed,)))


class Switches(Home):
    """A skill, a subagent, every hook and a connector turned off and on for the folder."""

    def skill(self):
        return next(key for key, _ in self.view.items() if key[1] and key[1].startswith("skill:"))

    def test_a_skill_is_turned_off_stays_as_a_dim_row_off_here_and_is_turned_on_again(self):
        self.choose(self.skill())
        self.assertEqual(self.under("release-notes", 4)[2:], ["On here  on  off", "Open SKILL.md    Show in graph"])
        self.assertEqual(self.press("enter").name, "open_setup")                # Enter still opens its file
        self.press("right", "right")
        self.assertEqual(self.under("release-notes", 5), [
            "On here  on  off", "Saved in ‹ Local ›  .claude/settings.local.json",
            '+ "skillOverrides": {"release-notes": "off"}', "from the next session", "Save"])
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.local), {"skillOverrides": {"release-notes": "off"}})
        canvas = self.draw()
        y, x = self.at(canvas, "release-notes")
        self.assertIn("off here", text(canvas, y))
        self.assertEqual(canvas.rows[y][x][1].fg, "muted_row")                  # dim, on the chosen row's band
        self.press("right", "left")                                             # on again: out of where it is
        self.assertEqual(self.under("On here  on  off", 2), [".claude/settings.local.json",
                                                             '− "skillOverrides": {"release-notes": "off"}'])
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.local), {"skillOverrides": {}})

    def test_a_sub_agent_of_ones_own_is_turned_off_by_a_deny_rule(self):
        self.choose(("row", "subagent:Project:doc-checker"))
        self.press("right", "right")
        self.assertIn('+ deny "Agent(doc-checker)"', self.under("On here  on  off", 2))
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.local), {"permissions": {"deny": ["Agent(doc-checker)"]}})
        self.assertIn("off here", text(self.draw(), self.at(self.draw(), "doc-checker")[0]))

    def test_claudes_own_sub_agents_are_switched_one_at_a_time_by_name(self):
        row = {**agent_layers.layer("subagent:built-in", "bot", "Explore, Plan", agent_layers.properties(
            "Built-in", lines=[["From", "Claude", "Built-in"]]), place="Built-in"), "names": ["Explore", "Plan"]}
        self.view.answer["sections"][0]["rows"].append(row)
        self.choose(("row", "subagent:built-in"))
        self.assertEqual(self.under("Explore, Plan", 3)[1:], ["‹ Explore ›", "On here  on  off"])
        self.press("enter", "right")
        self.assertEqual(self.view.edit.asked, {"action": "subagent", "name": "Plan"})
        self.press("down", "right")
        self.assertIn('+ deny "Agent(Plan)"', self.under("On here  on  off", 2))

    def test_a_plugins_sub_agent_has_no_switch(self):
        row = agent_layers.layer("subagent:pr-review:code-reviewer", "bot", "code-reviewer", agent_layers.properties(
            "code-reviewer", lines=[["From", "pr-review", "Plugin"]]), place="pr-review")
        self.view.answer["sections"][0]["rows"].append(row)
        self.choose(("row", "subagent:pr-review:code-reviewer"))
        self.assertIsNone(self.view.edit)

    def test_every_hook_goes_off_from_the_hooks_groups_head_which_then_says_so_and_brings_them_back(self):
        self.choose(HOOKS)
        self.assertEqual(self.under("Hooks 1", 1), ["All hooks here  on  off"])
        self.press("enter", "right")
        self.assertEqual(self.under("All hooks here", 6, LEAST), [
            "Saved in ‹ Local ›", ".claude/settings.local.json", '+ "disableAllHooks": true', "applies now",
            "Also stops herdr-fold's own hook:", "decisions go back to Claude's"])
        self.save(self.press("enter"))
        canvas = self.draw()
        y = self.at(canvas, "Hooks 1")[0]
        self.assertTrue(text(canvas, y).rstrip().endswith("off here"))
        self.assertEqual(canvas.rows[y + 2][self.at(canvas, "guard.sh")[1]][1].fg, "muted")       # stopped: dim
        self.assertEqual(self.view.chosen, HOOKS)
        self.press("enter", "left")
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.local), {})
        self.assertFalse(text(self.draw(), self.at(self.draw(), "Hooks 1")[0]).rstrip().endswith("off here"))

    def test_a_project_server_not_approved_yet_offers_cores_two_words_then_is_the_ordinary_switch(self):
        self.choose(("row", "connector:sentry"))
        self.assertIn("Approve in lumen-api  Keep off", self.under("sentry", 3))
        self.assertNotIn("On here", "".join(self.under("sentry", 4)))
        canvas = self.draw()
        y, x = self.at(canvas, "Keep off")
        self.assertIsNone(canvas.rows[y][x][1].bg)                              # neither is held before one is chosen
        self.press("right", "right")
        self.assertEqual(self.under("Approve in lumen-api  Keep off", 2), [".claude/settings.local.json",
                                                                           '+ enabledMcpjsonServers "sentry"'])
        self.press("right")                                                     # kept off
        self.assertIn('+ disabledMcpjsonServers "sentry"', self.under("Approve in lumen-api  Keep off", 2))
        self.press("esc")
        self.click("Approve in lumen-api")
        self.save(self.press("enter"))
        self.assertEqual(self.kept(self.local), {"enabledMcpjsonServers": ["sentry"]})
        self.assertIn("On here  on  off", self.under("sentry", 4))              # approved: off or on for the folder
        self.assertNotIn("Approve", "".join(self.under("sentry", 4)))

    def test_a_server_claudes_own_state_turns_off_is_turned_on_in_the_chat(self):
        self.put(os.path.join(self.home, ".claude.json"), {
            "mcpServers": {"github": {"type": "http", "url": "https://mcp.lumen.example/github"}},
            "projects": {agent_setup.project_key(self.folder): {"disabledMcpServers": ["github"]}}})
        self.read()
        self.choose(("row", "connector:github"))
        self.press("right", "left")
        self.assertEqual(self.under("On here  on  off", 2), ["/mcp enable github", "Turn on in lumen-api"])
        self.assertEqual(self.press("enter"), Action("turn_server", ("github",)))
        self.view.answer["claude"] = False
        self.assertEqual(self.press("enter"), Action("say", ("Start a chat in lumen-api to turn it on",)))


class Codex(Home):
    agent = "codex"

    def test_the_sandbox_and_the_approval_are_choices_saved_in_codexs_file_with_its_warning(self):
        self.choose(SANDBOX)
        self.assertIn("Read only  Workspace write  Full access", self.under("Sandbox Workspace write", 4))
        self.press("enter", "right")
        lines = self.under("Full access", 5, LEAST)
        self.assertEqual(lines[:5], ["Saved in ‹ Global ›", "~/.codex/config.toml",
                                     '− sandbox_mode = "workspace-write"', '+ sandbox_mode =',
                                     '"danger-full-access"'])
        self.assertIn("No sandbox: commands can change any", " ".join(self.under("from the next session", 2, LEAST)))
        self.save(self.press("enter"))
        self.assertIn('sandbox_mode = "danger-full-access"', self.raw(os.path.join(self.home, ".codex", "config.toml")))
        self.choose(("row", "approval"))
        canvas = self.draw()
        y, x = self.at(canvas, "Granular")
        self.assertEqual(canvas.rows[y][x][1].fg, "muted")                      # the file's: never chosen here
        self.press("enter", "right", "right")
        self.assertEqual(self.view.edit.asked["value"], "never")

    def test_a_codex_rule_says_where_it_is_changed_and_the_head_has_no_plus(self):
        self.put(os.path.join(self.home, ".codex", "rules", "default.rules"),
                 'prefix_rule(pattern=["git", "push"], decision="prompt")\n')
        self.read()
        rule = next((key for key, _ in self.view.items() if key[1] and key[1].startswith("permission:")), None)
        if rule is None:
            self.skipTest("core lists no Codex rule from this file")
        self.choose(rule)
        self.assertIn("Codex keeps its rules in a file of their", " ".join(self.under("git push", 4, LEAST)))
        self.assertFalse(text(self.draw(), self.at(self.draw(), "Permissions")[0]).rstrip().endswith("+"))
        self.press("a")
        self.assertFalse(self.view.editing and self.view.edit)                  # `a` adds a connector, as elsewhere


class Narrow(Home):
    """Every form at the least width a sidebar takes: nothing runs past the edge, nothing is cut short."""

    def test_no_line_of_a_form_is_cut_short_at_the_least_width(self):
        ways = [(layers.MODEL, ("enter", "right", "down", "right")), (MODE, ("enter", "right", "tab")),
                (SANDBOX, ("enter", "down", "x")), (PYTEST, ("enter", "tab", "tab")), (CURL, ("x",)),
                (CONFLICT, ("enter", "right")), (HOOKS, ("enter", "right")),
                (("row", "connector:sentry"), ("right", "right")),
                (("row", "subagent:Project:doc-checker"), ("right", "right"))]
        for key, keys in ways:
            with self.subTest(key=key):
                self.choose(key)
                self.press(*keys)
                self.assertTrue(self.view.editing)
                canvas = self.draw(LEAST)                                       # the head's three rows, then the lines
                rows = [text(canvas, 3 + n).rstrip() for n, (kind, _, _) in enumerate(self.view.lines(LEAST))
                        if kind == "edit"]
                self.assertTrue(any(row.strip() in ("Save", "Remove") or "Save  " in row for row in rows), rows)
                self.assertFalse([row for row in rows if "…" in row or len(row) > LEAST - 1], rows)
                self.press("esc")


class Family(Home):
    """The family plans a form before a draw, saves it through core and reads the setup again."""

    def app(self):
        self.addCleanup(end_jobs)
        set_attrs(self, agent_state, machine_agents=lambda home, which=None, fresh=False: [
            {"key": "claude", "name": "Claude", "installed": True, "signed_in": True, "plan": None,
             "login": ["claude", "login"], "install": "npm install -g claude", "page": "https://lumen.example/claude"}])
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 60), mock.Mock(call=lambda *args: {}), self.state)
        app.show("agent")
        self.settle(app)
        return app, app.views["agent"]

    def settle(self, app):
        for _ in range(4):
            app.tick()
            end_jobs()
            app.collect()
            app.draw()

    def keys(self, app, *keys):
        for key in keys:
            app.act(app.views["agent"].handle(Key(key) if len(key) > 1 else Key("char", key)), "agent")
            self.settle(app)

    def test_a_chosen_rows_form_is_planned_on_a_job_saved_by_core_and_undone_from_the_foot(self):
        app, view = self.app()
        view.folded.clear()
        view.choose(MODE)
        self.assertEqual(view.asks(), {"action": "mode"})
        self.settle(app)
        self.assertIsNone(view.asks())
        self.assertEqual(view.edit.plan["fields"][0]["value"], "acceptEdits")
        before = self.raw(self.project)
        self.keys(app, "enter", "right", "enter")
        self.assertEqual(self.kept(self.project)["permissions"]["defaultMode"], "plan")
        self.assertEqual(view.foot["words"], "from the next session")
        row = next(row for key, (_, row) in view.items() if key == MODE)
        self.assertEqual(row["note"], "Plan")                                   # read again: the row says it
        self.assertEqual(view.edit.plan["fields"][0]["value"], "plan")
        self.keys(app, "u")
        self.assertEqual(self.raw(self.project), before)
        self.assertIsNone(view.foot)

    def test_a_refused_undo_is_said_in_cores_words_and_the_layers_file_opens_in_the_preview(self):
        app, view = self.app()
        view.folded.clear()
        view.choose(MODE)
        self.settle(app)
        self.keys(app, "enter", "right", "enter")
        self.put(self.project, PROJECT)                                         # changed since the save
        app.act(view.handle(Key("char", "u")), "agent")
        self.assertEqual(app.error, ".claude/settings.json changed since: nothing saved")
        self.assertTrue(view.foot)
        opened = []
        app.open_preview = lambda spec, root: opened.append(spec["title"])
        app.act(Action("open_layer", ("Project",)), "agent")
        app.act(Action("open_layer", ("Local",)), "agent")                      # no such file yet: nothing
        self.assertEqual(opened, [".claude/settings.json"])


if __name__ == "__main__":
    unittest.main()
