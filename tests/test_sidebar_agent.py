"""Tests for the sidebar's Agent view (layers.py draws it, agent_panel.py reads it): core's layers() in cells, the head,
the sections, each row's mark, state and tag in aligned columns, the chosen row's properties and buttons; read in a
temporary home, a rule opened in the preview tab, a server checked again, the row's dot by the worst problem."""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from support import SRC, FakeTerminal, end_jobs, set_attrs, set_env, text

sys.path.insert(0, os.path.join(SRC, "plugins", "sidebar"))
import agent_panel  # noqa: E402
import agent_setup  # noqa: E402
import agent_state  # noqa: E402
import connectors  # noqa: E402
import graph  # noqa: E402
import layers  # noqa: E402
import sidebar  # noqa: E402
import usage  # noqa: E402
import widgets  # noqa: E402
from icons import glyphs  # noqa: E402
from screen import Canvas, Style  # noqa: E402
from theme import Theme  # noqa: E402
from vt import Key, Mouse  # noqa: E402
from widgets import Action  # noqa: E402

A = agent_setup
MCPJSON = "/work/lumen-api/.mcp.json"
CLAUDE_MD = "/work/lumen-api/CLAUDE.md"
NERD = glyphs(True)
WIDE = 60


def state(text_, tone):
    return {"text": text_, "tone": tone}


def tag(text_, tone):
    return {"text": text_, "tone": tone}


def lumen(skills=7, used=6):
    """lumen-api as connectors.html's TUI pane has it, in core's layers() shape: four rules, a conflict among the
    permissions, SKILLS skills (the one at USED used), five connectors (sentry failed, Box to sign in), a sub-agent."""
    project, personal, account = tag("Project", "project"), tag("Personal", "personal"), tag("claude.ai", "account")
    rules = [A.layer("rule:" + CLAUDE_MD, "file", "CLAUDE.md", A.properties(
                "CLAUDE.md", lines=[["From", "CLAUDE.md", "Project"]], text="# lumen-api\nRoutes live in src.",
                actions=[A.act("open", "Open CLAUDE.md", CLAUDE_MD)]), mark=project, tokens=1800),
             A.layer("rule:/home/dev/.claude/CLAUDE.md", "file", "CLAUDE.md", A.properties(
                "CLAUDE.md", lines=[["From", "~/.claude/CLAUDE.md", "Personal"]],
                actions=[A.act("open", "Open CLAUDE.md", "/home/dev/.claude/CLAUDE.md")]), mark=personal, tokens=2400),
             A.layer("rule:/work/lumen-api/AGENTS.md", "file", "AGENTS.md", A.properties("AGENTS.md"), mark=project,
                     tokens=1200),
             A.layer("rule:/work/lumen-api/.claude/rules/api.md", "file", "api.md", A.properties("api.md"),
                     note="when src/lumen/** is read", mark=project, tokens=700, dim=True)]
    conflict = A.layer("conflict:allow:Bash(git push:*)", "shield", "Bash(git push:*)", A.properties(
        "Bash(git push:*)", lines=[["Allow", "Bash(git push:*)", "Personal"], ["Deny", "Bash(git push:*)", "Project"]]),
        note="deny in Project hides allow in Personal", warn=True)
    permissions = [conflict] + [A.layer(f"permission:{kind}:{rule}", "shield", rule, A.properties(rule),
                                        mark=personal, state=state(kind, kind))
                                for kind, rule in (("allow", "Bash(npm test)"), ("ask", "WebSearch"))]
    skill_rows = [A.layer(f"skill:s{n}", "skill", f"skill-{n}", A.properties(f"skill-{n}"), mark=project,
                          tokens=300, used=n == used) for n in range(skills)]
    connectors = [
        A.layer("connector:sentry", "plug", "sentry", A.properties(
            "sentry", state("failed", "bad"), [["From", ".mcp.json", "Project"], ["Runs", "npx -y @sentry/mcp-server",
                                                                                    None]],
            error="npx is not on this machine's PATH",
            actions=[A.act("retry", "Retry", server="sentry"), A.act("open", "Open .mcp.json", MCPJSON)]),
            mark=project, state=state("failed", "bad"), known="sentry"),
        A.layer("connector:claude.ai Box", "plug", "Box", A.properties(
            "Box", state("sign in", "warn"), [["From", "claude.ai", "Account"], ["URL", "mcp.box.com", None]],
            actions=[A.act("connect", "Connect", server="claude.ai Box"),
                     A.act("turn-off", "Turn off in lumen-api", server="claude.ai Box")]),
            mark=account, state=state("sign in", "warn"), known="box"),
        A.layer("connector:claude.ai Google Drive", "plug", "Google Drive", A.properties(
            "Google Drive", state("on", "ok"), [["From", "claude.ai", "Account"]],
            actions=[A.act("turn-off", "Turn off in lumen-api", server="claude.ai Google Drive"),
                     A.act("sign-out", "Sign out", server="claude.ai Google Drive")]), mark=account,
                state=state("on", "ok"), known="google-drive"),
        A.layer("connector:claude.ai Notion", "plug", "Notion", A.properties(
            "Notion", actions=[A.act("turn-on", "Turn on in lumen-api", server="claude.ai Notion")]), mark=account,
                state=state("off here", "off"), dim=True, known="notion"),
        A.layer("connector:Dropbox", "plug", "Dropbox", A.properties("Dropbox"), mark=personal,
                state=state("on", "ok"), known="dropbox")]
    agents = [A.layer("agent:Claude:Explore", "bot", "Explore", A.properties("Explore"), mark=tag("Built-in", "muted"),
                      state=state("haiku", "ok"))]
    sections = [{"id": key, "title": title, "count": len(rows), "rows": rows}
                for key, title, rows in (("rules", "Rules", rules), ("permissions", "Permissions", permissions),
                                         ("skills", "Skills", skill_rows), ("connectors", "Connectors", connectors),
                                         ("agents", "Agents", agents))]
    return {"agent": "claude", "folder": "/work/lumen-api", "head": {"name": "Claude", "where": "in lumen-api"},
            "health": {"problems": [{"text": "1 failed", "tone": "bad", "row": "connector:sentry"},
                                    {"text": "1 sign in", "tone": "warn", "row": "connector:claude.ai Box"}]},
            "sections": sections, "connect": A.connecting("claude", "/work/lumen-api"), "claude": True}


def machine(key, name, **over):
    """An agent as core tells it (machine_agents()'s), with where it stands (standing()'s) as the family adds it."""
    one = {"key": key, "name": name, "installed": True, "signed_in": True, "plan": None, "login": [key, "login"],
           "install": f"npm install -g {key}", "page": f"https://lumen.example/{key}", **over}
    return {**one, "empty": agent_state.standing(one)}


# connectors.html's Ágensek: Claude on Max, Codex on Plus, Gemini CLI to sign in; and one not installed
MACHINE = [machine("claude", "Claude", plan="Max"), machine("codex", "Codex", plan="Plus"),
           machine("gemini", "Gemini CLI", signed_in=False), machine("aider", "Aider", installed=False)]


class AgentsList(unittest.TestCase):
    """The agents managed on the head's row: its list, a pick, Add an agent…, and what stands in a setup's place."""

    def setUp(self):
        self.view = layers.Layers(icons=False)
        self.view.set({**lumen(), "agents": MACHINE})

    def draw(self, cells=WIDE, rows=30):
        canvas = Canvas(cells, rows)
        self.view.draw(canvas, 0, rows, True)
        return canvas

    def lines(self, canvas):
        return [text(canvas, y).rstrip() for y in range(canvas.height)]

    def style(self, canvas, words):
        y = next(y for y in range(canvas.height) if words in text(canvas, y))
        return canvas.rows[y][text(canvas, y).index(words)][1]

    def press(self, key):
        return self.view.handle(Key(key))

    def listed(self, canvas, rows):
        """The open list's lines, each as its words between the frame's sides, one blank between them."""
        return [" ".join(line.split("│")[1].split()) if "│" in line else "" for line in self.lines(canvas)[1:rows]]

    def test_the_head_is_the_first_item_and_says_it_opens_a_list(self):
        self.assertEqual(self.view.chosen, ("section", "rules"))                # a new view: its first section still
        self.press("home")
        self.assertEqual(self.view.chosen, ("head", None))
        canvas = self.draw()
        self.assertTrue(text(canvas, 0).startswith(" Claude in lumen-api ⌄ "), text(canvas, 0))
        self.assertEqual(canvas.rows[0][1][1], Style(fg="text", bg="selection", bold=True))
        self.assertTrue(text(canvas, 0).rstrip().endswith("1 failed  1 sign in"))

    def test_enter_on_the_head_opens_the_agents_on_this_machine_installed_ones_only(self):
        self.press("home")
        self.assertIsNone(self.press("enter"))
        canvas = self.draw()
        self.assertEqual(self.listed(canvas, 8), ["", "Agents on this Mac", "✓ Claude Max", "Codex Plus",
                                                  "Gemini CLI sign in", "Add an agent…", ""])
        self.assertEqual(self.style(canvas, "Agents on this Mac").fg, "muted")
        self.assertEqual((self.style(canvas, "Plus").fg, self.style(canvas, "sign in").fg), ("muted", "modified"))
        self.assertNotIn("Aider", "\n".join(self.lines(canvas)))                # not installed: under Add an agent…
        self.assertTrue(text(canvas, 3).split("│")[1].endswith("Max "))         # the plan at the row's right end

    def test_a_pick_asks_for_that_agent_and_esc_closes_the_list(self):
        self.press("home")
        self.press("enter")
        self.press("down")
        self.assertEqual(self.press("enter"), Action("choose_agent", ("codex",)))
        self.assertIsNone(self.view.menu)
        self.press("enter")
        self.press("esc")
        self.assertIsNone(self.view.menu)

    def test_a_click_on_the_head_opens_the_list_and_a_click_picks(self):
        canvas = self.draw()
        self.view.handle(Mouse("press", 3, 0, 0))
        canvas = self.draw()
        y = next(y for y in range(canvas.height) if "Gemini CLI" in text(canvas, y))
        self.assertEqual(self.view.handle(Mouse("press", text(canvas, y).index("Gemini"), y, 0)),
                         Action("choose_agent", ("gemini",)))

    def test_add_an_agent_lists_the_ones_not_installed_and_a_pick_shows_how_it_is_installed(self):
        self.press("home")
        self.press("enter")
        self.press("up")                                                        # round to the last line
        self.assertIsNone(self.press("enter"))
        canvas = self.draw()
        self.assertEqual(self.listed(canvas, 5), ["", "Add an agent", "Aider", ""])
        self.assertIsNone(self.press("enter"))
        lines = self.lines(self.draw())
        self.assertEqual(lines[0], " Aider in lumen-api ⌄")
        self.assertEqual(lines[2], " Aider is not installed")
        self.assertIn(" npm install -g aider", lines)
        self.assertIn("  Copy    Open its page ↗", lines)
        self.assertEqual(lines[[n for n, line in enumerate(lines) if line][-1]], " herdr-fold runs no installer.")
        self.assertEqual(self.view.chosen, ("offer", "copy"))
        self.assertEqual(self.press("enter"), Action("copy_text", ("npm install -g aider",)))
        self.press("down")
        self.assertEqual(self.press("enter"), Action("open_url", ("https://lumen.example/aider",)))

    def test_with_every_agent_installed_add_an_agent_says_so(self):
        self.view.set({**lumen(), "agents": MACHINE[:3]})
        self.press("home")
        self.press("enter")
        self.press("up")
        self.press("enter")
        self.assertIn("Every agent herdr-fold knows is installed", "\n".join(self.lines(self.draw())))
        self.press("enter")
        self.assertIsNone(self.view.menu)

    def test_an_agent_not_signed_in_shows_sign_in_in_its_setups_place(self):
        self.view.set({"agent": "gemini", "folder": "/work/lumen-api", "agents": MACHINE,
                       "head": {"name": "Gemini CLI", "where": "in lumen-api"}, "empty": MACHINE[2]["empty"]})
        canvas = self.draw(48)
        lines = self.lines(canvas)
        self.assertEqual(lines[:8], [
            " Gemini CLI in lumen-api ⌄", "", " Gemini CLI is not signed in",
            " It signs in its own way: Sign in opens it in a", " terminal tab, and you finish there, or in the",
            " browser if it asks.", "", "  Sign in"])
        self.assertEqual(lines[9], " herdr-fold keeps no token.")
        self.assertEqual((self.style(canvas, "Gemini CLI is").bold, self.style(canvas, "It signs").fg,
                          self.style(canvas, "herdr-fold keeps").fg), (True, "subtext", "muted"))
        self.assertEqual(self.view.chosen, ("offer", "sign-in"))                # Enter signs in
        self.assertEqual(self.press("enter"), Action("sign_in", ("gemini",)))
        y = lines.index("  Sign in")
        self.assertEqual(self.view.handle(Mouse("press", 3, y, 0)), Action("sign_in", ("gemini",)))
        self.assertIsNone(self.view.tone())                                     # no setup read: no dot

    def test_an_agent_whose_setup_is_not_shown_has_its_head_alone(self):
        self.view.set({"agent": "gemini", "folder": "/work/lumen-api", "agents": [
            *MACHINE[:2], machine("gemini", "Gemini CLI")], "head": {"name": "Gemini CLI", "where": "in lumen-api"}})
        lines = self.lines(self.draw(48))
        self.assertEqual([line for line in lines if line.strip()], [" Gemini CLI in lumen-api ⌄"])
        self.assertEqual(self.view.chosen, layers.HEAD)                         # the agents' list, a key away
        self.assertIsNone(self.view.tone())

    def test_the_list_checks_none_while_an_agent_to_add_is_looked_at(self):
        self.assertEqual([one.get("check") for one in layers.agent_choices(MACHINE, "codex")],
                         [False, True, False, None])
        self.assertEqual([one["name"] for one in layers.add_choices(MACHINE)], ["Aider"])
        self.assertEqual(layers.agent_choices(None, "claude"), [])


class View(unittest.TestCase):
    """The view alone, from a stand-in answer, drawn on a canvas."""

    def setUp(self):
        ticks = iter(range(10 ** 6))                                            # a second on at every look:
        set_attrs(self, widgets, TURNS=widgets.Turns(clock=lambda: float(next(ticks))))    # a chevron at rest
        self.view = layers.Layers(icons=True)
        self.view.set(lumen())

    def draw(self, cells=WIDE, rows=40):
        canvas = Canvas(cells, rows)
        self.view.draw(canvas, 0, rows, True)
        return canvas

    def lines(self, canvas):
        return [text(canvas, y).rstrip() for y in range(canvas.height)]

    def at(self, canvas, words):
        """The row and column WORDS start on."""
        for y in range(canvas.height):
            if words in text(canvas, y):
                return y, text(canvas, y).index(words)
        self.fail(f"{words!r} not drawn:\n" + "\n".join(self.lines(canvas)))

    def look(self, canvas, words, row=None):
        """The style WORDS are drawn in: their first place, or on the row of the item named ROW."""
        if row is None:
            y, x = self.at(canvas, words)
        else:
            y, start = self.at(canvas, row)
            x = text(canvas, y).index(words, start + len(row))
        return canvas.rows[y][x][1]

    def press(self, key, **mods):
        return self.view.handle(Key(key, **mods) if len(key) > 1 else Key("char", key))

    def choose(self, key):
        """KEY's item chosen by the keys, from the first one down."""
        self.press("home")
        for _ in range(60):
            if self.view.chosen == key:
                return
            self.press("down")
        self.fail(f"{key} never chosen")

    def test_it_says_it_is_loading_on_the_heads_row_before_the_first_answer(self):
        view = layers.Layers()
        canvas = Canvas(WIDE, 10)
        view.draw(canvas, 0, 10, True)
        self.assertEqual(text(canvas, 0).rstrip(), " Loading setup…")
        self.assertEqual(canvas.rows[0][1][1].fg, "muted")

    def test_the_head_names_the_agent_and_its_folder_its_problems_at_the_right(self):
        canvas = self.draw()
        head = text(canvas, 0)
        self.assertTrue(head.startswith(" Claude in lumen-api "), head)
        self.assertTrue(head.endswith("1 failed  1 sign in "), head)             # a cell in from the pane's side
        self.assertEqual([self.look(canvas, words) for words in ("Claude", "in lumen-api", "1 failed", "1 sign in")],
                         [Style(fg="text", bold=True), Style(fg="muted"), Style(fg="deleted"), Style(fg="modified")])
        self.assertEqual(text(canvas, 1).strip(), "")                           # a blank row under it

    def test_the_sections_in_cores_order_connectors_open_the_rest_folded_problems_first(self):
        lines = self.lines(self.draw())
        closed, opened = NERD["closed"], NERD["open"]
        sentry, drive, notion, dropbox = (connectors.BRANDS[key]["glyph"] for key in (
            "sentry", "google-drive", "notion", "dropbox"))
        self.assertEqual([line[:20].rstrip() for line in lines[2:13]], [        # a connector's brand before its name
            f" {closed}  Rules", f" {closed}  Permissions", f" {closed}  Skills", f" {opened}  Connectors",
            f"    ✕ {sentry} sentry", "    ● B Box", f"    ● {drive} Google Drive", f"    ○ {notion} Notion",
            f"    ● {dropbox} Dropbox", f" {closed}  Agents", ""])
        self.assertEqual([line[-2:].strip() for line in lines[2:6]], ["4", "3", "7", "5"])   # counts at the right
        self.assertEqual(len(lines[2]), WIDE - 1)

    def test_a_connectors_mark_wears_its_states_color_a_row_off_here_dim(self):
        canvas = self.draw()
        marks = {name: canvas.rows[self.at(canvas, name)[0]][4][1].fg
                 for name in ("sentry", "Box", "Google Drive", "Notion", "Dropbox")}
        self.assertEqual(marks, {"sentry": "deleted", "Box": "modified", "Google Drive": "added", "Notion": "muted",
                                 "Dropbox": "added"})
        self.assertEqual((self.look(canvas, "Notion").fg, self.look(canvas, "Dropbox").fg), ("muted", "text"))
        self.assertEqual([self.look(canvas, words).fg for words in ("failed", "sign in", "off here", "Project",
                                                                     "claude.ai", "Personal")],
                         ["deleted", "modified", "muted", "done", "account", "accent"])

    def test_what_the_open_conversation_used_wears_a_green_dot_in_the_mark_column(self):
        # a skill, a sub-agent, a connector: the app's dot, under the section's title; nothing moves for it, and a
        # connector's problem keeps its own mark
        setup = lumen()
        rows = {section["id"]: section["rows"] for section in setup["sections"]}
        rows["agents"][0]["used"] = rows["connectors"][0]["used"] = rows["connectors"][4]["used"] = True
        self.view.set(setup)
        for section in ("skills", "agents"):
            self.choose(("section", section))
            self.press("enter")
        canvas = self.draw()
        marks = {name: canvas.rows[self.at(canvas, name)[0]][4] for name in ("skill-6", "skill-5", "Explore",
                                                                              "sentry", "Dropbox")}
        dot = ("●", Style(fg="added"))
        self.assertEqual(marks, {"skill-6": dot, "skill-5": (" ", Style()), "Explore": dot,
                                 "sentry": ("✕", Style(fg="deleted")), "Dropbox": dot})
        self.assertEqual({self.at(canvas, name)[1] for name in ("skill-6", "skill-5", "Explore")}, {6})

    def test_the_states_and_tags_stand_in_aligned_columns_the_tags_at_the_right(self):
        canvas = self.draw()
        rows = [text(canvas, self.at(canvas, name)[0]) for name in ("sentry", "Box", "Google Drive", "Dropbox")]
        self.assertEqual({len(row.rstrip()) for row in rows}, {WIDE - 1})     # each tag ends a cell in
        states = {re.search(r"(failed|sign in|on)\s+\S+\s*$", row).end(1) for row in rows}
        self.assertEqual(states, {WIDE - 1 - len("claude.ai") - 2})             # the widest tag's column, 2 cells off
        self.assertIn("sign in  claude.ai", rows[1])
        self.view.folded.discard("permissions")                                # one column in every section
        canvas = self.draw()
        self.assertEqual(text(canvas, self.at(canvas, "Bash(npm test)")[0]).index("allow") + len("allow"),
                         states.pop())

    def test_the_chosen_rows_properties_lie_under_it_label_and_value_its_error_its_buttons(self):
        self.choose(("row", "connector:sentry"))
        canvas = self.draw()
        y = self.at(canvas, "sentry")[0]
        self.assertEqual(canvas.rows[y][0][1].bg, "selection")                 # the chosen row, edge to edge
        self.assertEqual(canvas.rows[y][WIDE - 1][1].bg, "selection")
        under = [text(canvas, y + n).rstrip() for n in range(1, 5)]
        # under its name, past its brand's cell
        self.assertEqual(under[0], "        From  .mcp.json")                      # its tag says Project above
        self.assertEqual(under[1], "        Runs  npx -y @sentry/mcp-server")
        self.assertEqual(under[2], "        npx is not on this machine's PATH")
        self.assertEqual(under[3], "         Retry    Open .mcp.json")
        self.assertEqual(canvas.rows[y + 3][8][1].fg, "deleted")
        self.assertEqual([canvas.rows[y + 1][x][1].fg for x in (8, 14)], ["muted", "text"])
        # each button a block of its own, a cell of air each side of its label, two cells between two
        buttons = canvas.rows[y + 4]
        self.assertEqual([x for x in range(WIDE) if buttons[x][1].bg == "input"],
                         list(range(8, 15)) + list(range(17, 33)))
        self.assertTrue(text(canvas, y + 5).startswith("    ● B Box "))       # the next row right after

    def test_only_what_works_here_is_a_button(self):
        # an action this client does not know (a newer core's) is no button; a row with none has no buttons' line
        row = A.layer("connector:harbor", "plug", "harbor", A.properties("harbor", actions=[
            A.act("remove", "Remove", server="harbor"), A.act("retry", "Retry", server="harbor")]))
        self.assertEqual([one["id"] for one in layers.doable(row)], ["retry"])
        self.choose(("row", "connector:Dropbox"))
        canvas = self.draw()
        y = self.at(canvas, "Dropbox")[0]
        self.assertIn("Agents", text(canvas, y + 1))                            # nothing under it: the next head
        self.assertIsNone(self.press("enter"))

    def test_the_tuis_own_words_on_a_button_else_cores(self):
        # connectors.html's TUI pane: "Turn off here" for the app's "Turn off in lumen-api" (Task 14 makes it work)
        self.assertEqual([layers.label(A.act(kind, words)) for kind, words in (
            ("turn-off", "Turn off in lumen-api"), ("turn-on", "Turn on in lumen-api"), ("open", "Open .mcp.json"))],
            ["Turn off here", "Turn on here", "Open .mcp.json"])

    def test_a_property_the_row_shows_already_is_left_out_a_conflict_keeps_both_rules(self):
        # a rule's From is its own name, a plugin's skill's its tag, a sub-agent's Model its state word: said above
        answer = lumen()
        answer["sections"][2]["rows"][0]["properties"]["lines"] = [["From", "atlas", "Plugin"]]
        answer["sections"][2]["rows"][0]["tag"] = tag("atlas", "plugin")
        answer["sections"][4]["rows"][0]["properties"]["lines"] = [["From", "Claude", "Built-in"],
                                                                   ["Model", "haiku", None], ["Tools", "Read", None]]
        self.view.set(answer)
        self.view.folded.clear()
        found = {}
        for key in ("rule:" + CLAUDE_MD, "skill:s0", "agent:Claude:Explore", "conflict:allow:Bash(git push:*)"):
            self.choose(("row", key))
            row = self.view.chosen_row()
            found[key] = [line for kind, line in self.view.properties(row, WIDE) if kind == "property"]
        self.assertEqual(found, {
            "rule:" + CLAUDE_MD: [], "skill:s0": [],
            "agent:Claude:Explore": [(["From", "Claude", None], 5), (["Tools", "Read", None], 5)],
            "conflict:allow:Bash(git push:*)": [(["Allow", "Bash(git push:*)", "Personal"], 5),
                                                (["Deny", "Bash(git push:*)", "Project"], 5)]})

    def test_right_and_enter_open_a_section_left_folds_it_or_goes_up_to_it(self):
        self.choose(("section", "rules"))
        self.press("right")
        self.assertNotIn("rules", self.view.folded)
        self.assertIn(("row", "rule:" + CLAUDE_MD), [key for key, _ in self.view.items()])
        self.press("right")                                                     # open: on to its first row
        self.assertEqual(self.view.chosen, ("row", "rule:" + CLAUDE_MD))
        self.press("left")                                                      # a row: up to its section
        self.assertEqual(self.view.chosen, ("section", "rules"))
        action = self.press("left")                                             # open: folded, kept
        self.assertIn("rules", self.view.folded)
        self.assertEqual(action, Action("remember_agent_folded", (sorted(self.view.folded),)))
        self.press("enter")
        self.assertNotIn("rules", self.view.folded)

    def test_enter_on_a_row_does_its_first_action_a_rule_opens_its_file(self):
        self.choose(("section", "rules"))
        self.press("right")
        self.press("down")
        self.assertEqual(self.press("enter"), Action("open_setup", (CLAUDE_MD,)))

    def test_a_long_section_shows_five_rows_its_problems_and_used_ones_always_then_n_more(self):
        self.view.set(lumen(skills=9, used=7))
        self.choose(("section", "skills"))
        self.press("enter")
        lines = [line.strip() for line in self.lines(self.draw())]
        start = next(n for n, line in enumerate(lines) if "Skills" in line)
        self.assertEqual([line.lstrip("● ").split()[0] for line in lines[start + 1:start + 8]],     # the used one's dot
                         ["skill-0", "skill-1", "skill-2", "skill-3", "skill-4", "skill-7", "3"])
        self.assertEqual(lines[start + 7], "3 more")
        self.choose(("more", "skills"))
        self.press("enter")
        lines = [line.strip() for line in self.lines(self.draw())]
        self.assertEqual([line.lstrip("● ").split()[0] for line in lines[start + 1:start + 10]],
                         [f"skill-{n}" for n in range(9)])
        self.assertEqual(self.view.chosen, ("row", "skill:s5"))                 # the first one it showed

    def test_one_row_is_never_folded_under_one_more_its_line_shows_it(self):
        self.choose(("section", "skills"))                                      # seven, the used one sixth
        self.press("enter")
        lines = [line.strip() for line in self.lines(self.draw())]
        start = next(n for n, line in enumerate(lines) if "Skills" in line)
        self.assertEqual([line.lstrip("● ").split()[0] for line in lines[start + 1:start + 8]],
                         [f"skill-{n}" for n in range(7)])
        self.assertEqual((lines[start + 8].split()[-2:], ("more", "skills") in dict(self.view.items())),
                         (["Connectors", "5"], False))

    def test_a_conflict_says_its_sentence_under_it_in_yellow(self):
        self.choose(("section", "permissions"))
        self.press("right")
        canvas = self.draw()
        y = self.at(canvas, "Bash(git push:*)")[0]
        self.assertEqual(text(canvas, y)[4], "●")
        self.assertEqual(canvas.rows[y][4][1].fg, "modified")
        self.assertEqual(text(canvas, y + 1).strip(), "deny in Project hides allow in Personal")
        self.assertEqual(self.look(canvas, "deny in Project").fg, "modified")
        self.assertEqual([self.look(canvas, "allow", "Bash(npm test)").fg, self.look(canvas, "ask", "WebSearch").fg],
                         ["added", "modified"])

    def test_codexs_approval_is_a_permissions_row_to_read_with_open_alone(self):
        found, path = lumen(), "/home/dev/.codex/config.toml"
        section = next(one for one in found["sections"] if one["id"] == "permissions")
        section["rows"].insert(0, A.layer("approval", "shield", "Approval", A.properties(
            "Approval", lines=[["From", "~/.codex/config.toml", "Personal"]],
            actions=[A.act("open", "Open config.toml", path)]), note="Ask on request", mark=tag("Personal", "personal"),
            agents=["codex"]))
        self.view.set({**found, "agent": "codex"})
        self.choose(("section", "permissions"))
        self.press("right")
        canvas = self.draw()
        y, x = self.at(canvas, "Approval")
        self.assertLess(y, self.at(canvas, "Bash(git push:*)")[0])              # before the rules, a conflict too
        self.assertEqual(text(canvas, y).split(), ["Approval", "Ask", "on", "request", "Personal"])
        self.assertEqual(text(canvas, y)[4], " ")                               # no mark: nothing is wrong with it
        self.assertEqual((canvas.rows[y][x][1].fg, self.look(canvas, "Ask on request").fg), ("text", "muted"))
        self.assertEqual(self.look(canvas, "Personal", "Approval").fg, "accent")
        # its row says its words and whose it is; under it where it is set, and Open, nothing that changes it
        self.choose(("row", "approval"))
        canvas = self.draw()
        y = self.at(canvas, "Approval")[0]
        self.assertEqual(text(canvas, y + 1).split(), ["From", "~/.codex/config.toml"])
        self.assertEqual(text(canvas, y + 2).split(), ["Open", "config.toml"])
        self.assertEqual([one["id"] for one in self.view.doable(section["rows"][0])], ["open"])
        self.assertEqual(self.press("enter"), Action("open_setup", (path,)))

    def test_a_buttons_press_does_its_action(self):
        self.choose(("row", "connector:sentry"))
        canvas = self.draw()
        y, x = self.at(canvas, "Retry")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("retry_server", ("sentry",)))
        y, x = self.at(canvas, "Open .mcp.json")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("open_setup", (MCPJSON,)))

    def test_a_click_chooses_a_row_and_opens_or_folds_a_section(self):
        canvas = self.draw()
        y, x = self.at(canvas, "Dropbox")
        self.assertIsNone(self.view.handle(Mouse("press", x, y, 0)))
        self.assertEqual(self.view.chosen, ("row", "connector:Dropbox"))
        y, x = self.at(canvas, "Rules")
        self.view.handle(Mouse("press", x, y, 0))
        self.assertEqual((self.view.chosen, "rules" in self.view.folded), (("section", "rules"), False))

    def test_a_right_click_on_a_row_offers_its_actions(self):
        canvas = self.draw()
        y, x = self.at(canvas, "sentry")
        self.view.handle(Mouse("press", x, y, 2))
        self.assertEqual(self.view.menu.menu.choices, ["Retry", "Open .mcp.json"])
        self.assertEqual(self.press("enter"), Action("retry_server", ("sentry",)))
        y, x = self.at(self.draw(), "Dropbox")
        self.view.handle(Mouse("press", x, y, 2))                               # nothing to do on it: no menu
        self.assertIsNone(self.view.menu)

    def test_a_problem_chip_chooses_its_row(self):
        self.view.folded.add("connectors")
        canvas = self.draw()
        y, x = self.at(canvas, "1 sign in")
        self.view.handle(Mouse("press", x, y, 0))
        self.assertEqual(self.view.chosen, ("row", "connector:claude.ai Box"))
        self.assertNotIn("connectors", self.view.folded)

    def test_the_worst_problem_gives_the_tone_red_over_yellow(self):
        self.assertEqual(self.view.tone(), "bad")
        answer = lumen()
        answer["health"]["problems"] = answer["health"]["problems"][1:]
        self.view.set(answer)
        self.assertEqual((self.view.tone(), self.view.problems()), ("warn", ["1 sign in"]))
        answer["health"]["problems"] = []
        self.view.set(answer)
        self.assertIsNone(self.view.tone())

    def test_a_server_being_checked_spins_in_its_marks_place(self):
        self.view.checking.add("sentry")
        self.view.frame = "⠙"
        canvas = self.draw()
        y = self.at(canvas, "sentry")[0]
        self.assertEqual((text(canvas, y)[4], canvas.rows[y][4][1].fg), ("⠙", "accent"))

    def test_the_chosen_row_stays_chosen_through_a_new_answer(self):
        self.choose(("row", "connector:claude.ai Google Drive"))
        answer = lumen()
        connectors = answer["sections"][3]["rows"]
        connectors.insert(0, connectors.pop(3))                                 # Notion now first
        self.view.set(answer)
        self.assertEqual(self.view.chosen, ("row", "connector:claude.ai Google Drive"))

    def test_an_agent_not_here_says_so_under_its_head(self):
        gone = machine("codex", "Codex", installed=False)
        self.view.set({"agent": "codex", "folder": "/work/lumen-api", "agents": [gone], "empty": gone["empty"],
                       "head": {"name": "Codex", "where": "in lumen-api"}})
        lines = self.lines(self.draw())
        self.assertTrue(lines[0].startswith(" Codex in lumen-api "), lines[0])
        self.assertEqual(lines[1:3], ["", " Codex is not installed"])

    def test_at_the_columns_least_every_row_keeps_a_cell_in_from_each_side(self):
        for cells in (sidebar.column.FEWEST, sidebar.column.NARROWEST, sidebar.column.IDEAL):
            self.choose(("row", "connector:sentry"))
            canvas = self.draw(cells)
            with self.subTest(cells=cells):
                for y in range(canvas.height):
                    row = text(canvas, y)
                    self.assertEqual((row[0], row[cells - 1]), (" ", " "), row)
                self.assertIn("sentry", text(canvas, self.at(canvas, "sentry")[0]))

    def test_where_a_name_would_have_too_little_room_the_tags_go_first_the_states_stay(self):
        canvas = self.draw(sidebar.column.FEWEST)                              # the column's least: room for all
        self.assertIn("claude.ai", text(canvas, self.at(canvas, "Google Drive")[0]))
        canvas = self.draw(34)                                                  # a window narrower than that
        row = text(canvas, self.at(canvas, "Google Drive")[0])
        self.assertEqual(len(row.rstrip()), 33, row)
        self.assertTrue(row.rstrip().endswith(" on"), row)
        self.assertNotIn("claude.ai", row)

    def test_the_wheel_scrolls_the_list_under_the_head(self):
        self.view.folded.clear()
        for _ in range(3):
            self.view.handle(Mouse("wheel_down", 5, 10, 0))
        canvas = self.draw(rows=12)
        self.assertEqual(text(canvas, 0).split()[0], "Claude")                  # the head stays
        self.assertNotIn("Rules", "\n".join(self.lines(canvas)))

    def test_its_place_is_handed_over(self):
        self.choose(("row", "connector:Dropbox"))
        self.view.more.add("skills")
        other = layers.Layers()
        other.take(json.loads(json.dumps(self.view.kept())))
        other.set(lumen())
        self.assertEqual((other.chosen, other.more), (("row", "connector:Dropbox"), {"skills"}))


NOW = 1794571200                # Friday, 13 November 2026, 12:00 UTC
FIVE, WEEK = NOW + 2 * 3600 + 46 * 60, NOW + 3 * 86400 + 5 * 3600       # 14:46 UTC; Monday, 17:00 UTC


def reading(agent, five=None, week=None, source="status", at=NOW - 60):
    """AGENT's limits as core's limits() tells them: FIVE and WEEK each a percent used, or None."""
    return {"agent": agent, "five_hour": five is not None and {"used": five, "resets": FIVE} or None,
            "week": week is not None and {"used": week, "resets": WEEK} or None, "at": at, "source": source}


def metered(*readings, current="claude", twelve=True, kept=None):
    """lumen-api with its Usage as the family answers it: core's section(), each reset said in local time; KEPT: the
    blocks the user opened or folded, as core keeps them."""
    found = usage.section(list(readings), MACHINE, current, NOW, kept)
    for row in found["rows"]:
        if row["resets"]:
            row["resets"]["said"] = usage.reset_said(row["resets"], twelve)
    return {**lumen(), "agent": current, "agents": MACHINE, "usage": found}


class Usage(unittest.TestCase):
    """Usage, the view's first section, as usage.html's TUI pane and usage-agents.html: the agent in use open, its
    name and plan, then both windows' bars and percents in their levels' colors; another agent one row, folded."""

    draw, lines, at, look, press, choose = View.draw, View.lines, View.at, View.look, View.press, View.choose

    def setUp(self):
        ticks = iter(range(10 ** 6))
        set_attrs(self, widgets, TURNS=widgets.Turns(clock=lambda: float(next(ticks))))
        self.addCleanup(time.tzset)
        set_env(self, TZ="UTC")
        time.tzset()
        self.view = layers.Layers(icons=True)
        self.view.set(metered(reading("claude", 72, 16), reading("codex", 8, 3)))

    def test_it_is_the_first_section_open_the_agent_in_use_open_another_one_row(self):
        lines = self.lines(self.draw())
        self.assertEqual(lines[2], f" {NERD['open']}  Usage" + "7 days".rjust(WIDE - 1 - 9))    # its period, no count
        self.assertEqual(lines[3], "    ▾ Claude Max" + "5 hour resets at 2:46 PM".rjust(WIDE - 1 - 16))
        self.assertEqual(lines[4], "      5h ▰▰▰▰▰▱▱ 72%  wk ▰▱▱▱▱▱▱ 16%")
        self.assertEqual(lines[5], "    ▸ Codex Plus" + "5h 8%  wk 3%".rjust(WIDE - 1 - 16))
        self.assertTrue(lines[6].startswith(f" {NERD['closed']}  Rules"), lines[6])

    def test_a_bar_and_its_percent_wear_the_levels_color_the_labels_and_the_plan_dim(self):
        self.view.set(metered(reading("claude", 72, 91), reading("codex", 8, 3)))
        canvas = self.draw()
        y = self.at(canvas, "5h ▰")[0]
        styles = {words: canvas.rows[y][text(canvas, y).index(words)][1]
                  for words in ("5h", "▰▰▰▰▰▱▱", "72%", "wk", "▰▰▰▰▰▰▱", "91%")}
        self.assertEqual(styles, {"5h": Style(fg="muted"), "▰▰▰▰▰▱▱": Style(fg="modified"),
                                  "72%": Style(fg="modified"), "wk": Style(fg="muted"),
                                  "▰▰▰▰▰▰▱": Style(fg="deleted"), "91%": Style(fg="deleted")})
        self.assertEqual([self.look(canvas, words) for words in ("▾", "Claude", "Max", "5 hour resets")],
                         [Style(fg="muted"), Style(fg="text", bold=True), Style(fg="muted"), Style(fg="muted")])

    def test_a_folded_rows_figures_wear_the_levels_colors_the_labels_dim_no_other_mark(self):
        self.view.set(metered(reading("claude", 72, 16), reading("codex", 55, 91)))
        canvas = self.draw()
        self.assertEqual([self.look(canvas, words, row="Codex") for words in ("5h", "55%", "wk", "91%")],
                         [Style(fg="muted"), Style(fg="modified"), Style(fg="muted"), Style(fg="deleted")])
        self.assertEqual(self.look(canvas, "▸"), Style(fg="muted"))
        self.assertEqual(self.lines(canvas)[5], "    ▸ Codex Plus" + "5h 55%  wk 91%".rjust(WIDE - 1 - 16))

    def test_a_bar_fills_by_its_percent_never_empty_with_some_used_full_only_at_all(self):
        self.assertEqual([layers.bar(used) for used in (0, 1, 8, 16, 50, 72, 96, 99, 100, 140)],
                         ["▱▱▱▱▱▱▱", "▰▱▱▱▱▱▱", "▰▱▱▱▱▱▱", "▰▱▱▱▱▱▱", "▰▰▰▰▱▱▱", "▰▰▰▰▰▱▱", "▰▰▰▰▰▰▱", "▰▰▰▰▰▰▱",
                          "▰▰▰▰▰▰▰", "▰▰▰▰▰▰▰"])

    def test_a_window_past_its_reset_leaves_its_place_empty_the_other_keeps_its_column(self):
        self.view.set(metered(reading("claude", None, 16), reading("codex", 100, None), kept={"codex": True}))
        lines = self.lines(self.draw())
        self.assertEqual(lines[3], "    ▾ Claude Max" + "Week resets Mon at 5:00 PM".rjust(WIDE - 1 - 16))
        self.assertEqual(lines[4], "                      wk ▰▱▱▱▱▱▱ 16%")
        self.assertEqual(lines[5], "    ▾ Codex Plus" + "5 hour resets at 2:46 PM".rjust(WIDE - 1 - 16))
        self.assertEqual(lines[6], "      5h ▰▰▰▰▰▰▰100%")
        self.view.set(metered(reading("claude", None, 16), reading("codex", 100, None)))
        self.assertEqual(self.lines(self.draw())[5], "    ▸ Codex Plus" + "5h 100%".rjust(WIDE - 1 - 16))

    def test_hours_as_the_machine_writes_them(self):
        self.view.set(metered(reading("claude", 72, 16), twelve=False))
        self.assertTrue(self.lines(self.draw())[3].endswith("5 hour resets at 14:46"))

    def test_claudes_own_cache_says_its_age_before_the_reset_and_keeps_it_where_only_one_fits(self):
        self.view.set(metered(reading("codex", 8, 3), reading("claude", 72, 16, source="claude", at=NOW - 43 * 60),
                              current="codex", kept={"claude": True}))
        lines = self.lines(self.draw())
        self.assertEqual(lines[3], "    ▾ Codex Plus" + "5 hour resets at 2:46 PM".rjust(WIDE - 1 - 16))
        self.assertEqual(lines[5], "    ▾ Claude Max" + "as of 43 min ago".rjust(WIDE - 1 - 16))
        self.view.set(metered(reading("claude", 72, 16, source="claude", at=NOW - 43 * 60)))
        self.assertTrue(self.lines(self.draw(70))[3].endswith("  as of 43 min ago  5 hour resets at 2:46 PM"))
        self.assertEqual(self.lines(self.draw(48))[3], "    ▾ Claude Max" + "as of 43 min ago".rjust(48 - 1 - 16))
        self.assertEqual(self.lines(self.draw(30))[3], "    ▾ Claude Max")      # no room: the name

    def test_a_narrow_pane_keeps_the_percents_and_drops_the_bars_a_folded_row_its_tightest(self):
        lines = self.lines(self.draw(34))
        self.assertEqual(lines[4], "      5h  72%  wk  16%")
        self.assertEqual(lines[5], "    ▸ Codex Plus" + "5h 8%  wk 3%".rjust(33 - 16))
        self.assertTrue(all(len(line) <= 33 for line in lines))
        self.assertEqual(self.lines(self.draw(30))[5], "    ▸ Codex Plus" + "5h 8%".rjust(29 - 16))
        self.assertEqual(self.lines(self.draw(22))[5], "    ▸ Codex Plus")

    def test_every_agent_is_a_row_of_its_own_and_none_waits_under_more(self):
        five = [reading(agent, 8, 3) for agent in ("claude", "codex", "gemini", "amp", "aider")]
        self.view.set(metered(*five))
        lines = self.lines(self.draw())
        self.assertEqual([line[:16] for line in lines[3:9]],
                         ["    ▾ Claude Max", "      5h ▰▱▱▱▱▱▱", "    ▸ Codex Plus", "    ▸ Gemini CLI",
                          "    ▸ amp" + " " * 7, "    ▸ Aider" + " " * 5])
        self.assertTrue(lines[9].startswith(f" {NERD['closed']}  Rules"), lines[9])
        self.assertTrue(all(line.endswith("5h 8%  wk 3%") for line in lines[5:9]), lines[5:9])
        self.assertEqual([key for key, _ in self.view.items()][1:7],
                         [("section", "usage"), ("usage", "claude"), ("usage", "codex"), ("usage", "gemini"),
                          ("usage", "amp"), ("usage", "aider")])

    def test_with_no_reading_it_says_not_known_yet(self):
        self.view.set(metered())
        canvas = self.draw()
        self.assertEqual(self.lines(canvas)[3], "      Not known yet")
        self.assertEqual(self.look(canvas, "Not known yet"), Style(fg="muted"))

    def test_the_keys_walk_its_head_and_agents_and_fold_it_kept_as_the_others(self):
        keys = [key for key, _ in self.view.items()]
        self.assertEqual(keys[:5], [layers.HEAD, ("section", "usage"), ("usage", "claude"), ("usage", "codex"),
                                    ("section", "rules")])
        self.choose(("section", "usage"))
        self.assertIsNone(self.press("right"))                                  # open: on to its first agent
        self.assertEqual(self.view.chosen, ("usage", "claude"))
        self.choose(("section", "usage"))
        action = self.press("left")                                             # Enter is its view's (Costs)
        self.assertEqual(action, Action("remember_agent_folded", (sorted(self.view.folded),)))
        self.assertIn("usage", self.view.folded)
        self.assertEqual([key for key, _ in self.view.items()][2], ("section", "rules"))
        lines = self.lines(self.draw())
        self.assertEqual(lines[3][:9], f" {NERD['closed']}  Rules")

    def test_enter_or_right_opens_an_agent_left_folds_it_then_goes_up_kept_for_both_clients(self):
        self.choose(("usage", "codex"))
        self.assertEqual(self.press("right"), Action("usage_open", ("codex", True)))
        self.assertEqual(self.lines(self.draw())[5:7], ["    ▾ Codex Plus" + "5 hour resets at 2:46 PM".rjust(
            WIDE - 1 - 16), "      5h ▰▱▱▱▱▱▱  8%  wk ▰▱▱▱▱▱▱  3%"])
        self.assertIsNone(self.press("right"))                                  # open already: stays
        self.assertEqual(self.press("left"), Action("usage_open", ("codex", False)))
        self.assertIsNone(self.press("left"))                                   # folded: up to its section
        self.assertEqual(self.view.chosen, ("section", "usage"))
        self.choose(("usage", "claude"))
        self.assertEqual(self.press("enter"), Action("usage_open", ("claude", False)))
        self.assertEqual(self.lines(self.draw())[3], "    ▸ Claude Max" + "5h 72%  wk 16%".rjust(WIDE - 1 - 16))
        self.assertEqual(self.press("enter"), Action("usage_open", ("claude", True)))

    def test_a_press_on_an_agents_row_opens_or_folds_it_lit_under_the_mouse(self):
        canvas = self.draw()
        y, x = self.at(canvas, "Codex")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("usage_open", ("codex", True)))
        self.assertEqual(self.view.chosen, ("usage", "codex"))
        self.assertEqual(self.draw().rows[y][0][1].bg, "selection")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("usage_open", ("codex", False)))

    def test_the_blocks_are_as_core_keeps_them_a_turn_shown_at_once_till_core_tells_it(self):
        self.view.set(metered(reading("claude", 72, 16), reading("codex", 8, 3), kept={"claude": False,
                                                                                         "codex": True}))
        lines = self.lines(self.draw())
        self.assertEqual((lines[3][:16], lines[4][:16]), ("    ▸ Claude Max", "    ▾ Codex Plus"))
        self.choose(("usage", "claude"))
        self.press("enter")
        stale = metered(reading("claude", 72, 16), reading("codex", 8, 3), kept={"claude": False, "codex": True})
        self.view.set(stale)                                                    # read before the change was kept
        self.assertEqual(self.lines(self.draw())[3][:16], "    ▾ Claude Max")
        self.view.set(metered(reading("claude", 72, 16), reading("codex", 8, 3), kept={"claude": True}))
        self.assertEqual(self.view.opened, {})                                  # core tells it now
        self.view.set(metered(reading("claude", 72, 16), reading("codex", 8, 3), kept={"claude": False}))
        self.assertEqual(self.lines(self.draw())[3][:16], "    ▸ Claude Max")   # another client folded it

    def test_folded_whole_its_head_shows_the_agent_in_uses_tightest_figure_open_none(self):
        self.choose(("section", "usage"))
        self.press("left")
        self.press("home")                                                      # the head's band off its row
        canvas = self.draw()
        self.assertEqual(self.lines(canvas)[2], f" {NERD['closed']}  Usage" + "Claude 5h 72%".rjust(WIDE - 1 - 9))
        self.assertEqual([self.look(canvas, words) for words in ("Claude 5h", "72%")],
                         [Style(fg="muted"), Style(fg="modified")])
        self.assertEqual(self.press("p"), Action("usage_period", ("30d",)))    # its period steps, unseen
        self.assertTrue(self.lines(self.draw())[2].endswith("Claude 5h 72%"))
        self.view.set(metered(reading("claude", 12, 64), reading("codex", 8, 3)))
        self.assertTrue(self.lines(self.draw())[2].endswith("Claude wk 64%"))  # the tighter window

    def test_folded_whole_another_agent_stands_there_when_yellow_or_red_and_worse(self):
        self.view.folded.add("usage")
        for claude, codex, shown in ((40, 8, "Codex 5h 8%"), (72, 8, "Claude 5h 72%"), (72, 60, "Claude 5h 72%"),
                                     (91, 60, "Claude 5h 91%"), (40, 50, "Codex 5h 50%"), (60, 60, "Codex 5h 60%")):
            self.view.set(metered(reading("claude", claude, 3), reading("codex", codex, 3), current="codex"))
            self.assertTrue(self.lines(self.draw())[2].endswith(shown), (claude, codex, self.lines(self.draw())[2]))
        self.view.set(metered(current="codex"))
        self.assertEqual(self.lines(self.draw())[2], f" {NERD['closed']}  Usage")      # nothing known: no figure

    def test_an_answer_without_it_draws_no_usage(self):
        self.view.set(lumen())
        self.assertNotIn("Usage", "\n".join(self.lines(self.draw())))


OPUS, SONNET, CODEX = "#3987e5", "#d95926", "#c98500"
DAYS = (16.75, 29.3, 12.6, 25.1, 33.5, 8.4, 16.75)      # usage.html's row of blocks: ▄▇▃▆█▂▄


def month(today=18.4, pace=46.0, budget=50):
    """Codex's November as core's report tells it (month_of()'s), TODAY spent on the way to PACE."""
    over = bool(budget) and max(pace, today) > budget
    return {"agent": "codex", "name": "Codex", "key": "Codex · API key", "id": "2026-11", "label": "November",
            "budget": budget, "days": 30, "day": 12, "today": today, "pace": pace, "over": over,
            "words": {"spent": f"~${today:,.2f}", "of": f"of ${budget}" if budget else "",
                      "pace": f"on pace for ~${int(pace + 0.5)}"},
            "level": ("warn" if over else "ok") if budget else None, "end": "Nov 30", "color": CODEX}


def reported(months=None, projects=None, none=None, days=DAYS, claude=130.9):
    """A week as core's report() tells it, the parts Usage draws: usage.html's TUI sidebar pane's figures."""
    months = [month()] if months is None else months
    daily = [{"day": f"2026-11-{n + 3:02d}", "label": f"Nov {n + 3}", "total": cost, "models": [
        {"model": "claude-opus-5-5", "name": "Opus 5.5", "color": OPUS, "cost": cost * (0.2 if n == 3 else 0.8)},
        {"model": "claude-sonnet-5-5", "name": "Sonnet 5.5", "color": SONNET, "cost": cost * (0.8 if n == 3 else 0.2)}]
              if cost else []} for n, cost in enumerate(days)]
    project = [("lumen-api", 84.2, 5, False), ("harbor-web", 41.1, 2, False), ("tidepool", 14.2, 0, False)]
    return {"period": {"id": "7d", "label": "7 days"}, "prices_as_of": "Nov 9, 2026", "none": none,
            "summary": [{"key": "Claude · Max plan", "agent": "claude", "value": claude,
                         "text": "no price" if claude is None else f"~${claude:,.2f}", "unit": "API value", "line": "",
                         "over": False}]
            + [{"key": "Codex · API key", "agent": "codex", "value": 8.6, "text": "~$8.60", "unit": "spent",
                "line": "", "over": one["over"]} for one in months]
            + [{"key": "Tokens", "value": 38200000, "text": "38.2M", "line": "81% read from cache"}],
            "daily": daily, "months": months, "month": months[0] if months else None,
            "projects": [{"folder": f"/work/{name}", "name": name, "cost": cost, "tokens": 1000, "commits": commits,
                          "about": about, "commits_text": f"{'about ' * about}{commits}" if commits else "none yet"}
                         for name, cost, commits, about in (project if projects is None else projects)]}


class Costs(unittest.TestCase):
    """Usage with what the agents cost, as usage.html's TUI sidebar pane: each agent's figure at its name's right, an
    API-key agent's month under it, the days as a row of blocks, the projects, the cache's share and the prices'
    day; its period stepped on its head, Enter there for the Usage view."""

    draw, lines, at, look, press, choose = View.draw, View.lines, View.at, View.look, View.press, View.choose
    setUp = Usage.setUp

    def cost(self, report=None, left=False, kept=None):
        keyed = [machine("codex", "Codex", plan="API key") if one["key"] == "codex" else one for one in MACHINE]
        self.view.set({**metered(reading("claude", 72, 16), kept=kept), "agents": keyed})
        self.view.costs, self.view.reading = reported() if report is None else report, left

    def test_the_section_as_the_mockup_draws_it(self):
        self.cost()
        lines, edge = self.lines(self.draw()), WIDE - 1
        self.assertEqual(lines[2], f" {NERD['open']}  Usage" + "7 days".rjust(edge - 9))
        self.assertEqual(lines[3], "    ▾ Claude Max" + "~$130.90 API value".rjust(edge - 16))
        self.assertEqual(lines[4], "      5h ▰▰▰▰▰▱▱ 72%  wk ▰▱▱▱▱▱▱ 16%")
        self.assertEqual(lines[5], "    ▸ Codex API key" + "~$18.40 of $50".rjust(edge - 19))
        self.assertEqual(lines[6:9], ["", "      per day", "      ▄▇▃▆█▂▄  Nov 3 – 9"])
        self.assertEqual(lines[9:13], ["", "      lumen-api" + "~$84.20  5 commits".rjust(edge - 15),
                                       "      harbor-web" + "~$41.10  2 commits".rjust(edge - 16),
                                       "      tidepool" + "~$14.20  none yet".rjust(edge - 15)])
        self.assertEqual(lines[13:15], ["", "      81% read from cache · prices Nov 9"])
        self.assertTrue(lines[15].startswith(f" {NERD['closed']}  Rules"), lines[15])
        self.cost(kept={"codex": True})                                         # opened: its month under it
        lines = self.lines(self.draw())
        self.assertEqual(lines[5:7], ["    ▾ Codex API key" + "~$18.40 of $50".rjust(edge - 19),
                                      "      Nov ▰▰▰▱▱▱▱  on pace for ~$46"])

    def test_an_agent_on_an_api_key_in_use_is_first_and_open(self):
        keyed = [machine("codex", "Codex", plan="API key") if one["key"] == "codex" else one for one in MACHINE]
        self.view.set({**metered(reading("claude", 72, 16), current="codex"), "agents": keyed})
        self.view.costs = reported()
        lines = self.lines(self.draw())
        self.assertEqual(lines[3:6], ["    ▾ Codex API key" + "~$18.40 of $50".rjust(WIDE - 1 - 19),
                                      "      Nov ▰▰▰▱▱▱▱  on pace for ~$46",
                                      "    ▸ Claude Max" + "5h 72%  wk 16%".rjust(WIDE - 1 - 16)])
        self.assertEqual([key for key, _ in self.view.items()][2:4], [("usage", "codex"), ("usage", "claude")])

    def test_only_the_figures_and_names_are_lit_the_rest_dim_the_blocks_in_their_models_colors(self):
        self.cost(kept={"codex": True})
        self.view.choose(layers.HEAD)
        canvas = self.draw()
        self.assertEqual([self.look(canvas, words) for words in (
            "7 days", "~$130.90", "API value", "API key", "~$18.40", "of $50", "Nov ", "▰▰▰▱▱▱▱", "on pace", "per day",
            "Nov 3", "harbor-web", "~$41.10", "2 commits", "81% read")],
            [Style(fg="muted"), Style(fg="text"), Style(fg="muted"), Style(fg="muted"), Style(fg="text"),
             Style(fg="muted"), Style(fg="muted"), Style(fg="added"), Style(fg="muted"), Style(fg="muted"),
             Style(fg="muted"), Style(fg="text"), Style(fg="text"), Style(fg="muted"), Style(fg="muted")])
        y, x = self.at(canvas, "▄▇▃▆█▂▄")
        self.assertEqual([canvas.rows[y][x + n][1] for n in range(7)],
                         [Style(fg=OPUS)] * 3 + [Style(fg=SONNET)] + [Style(fg=OPUS)] * 3)     # each day's largest

    def test_a_folded_api_keys_figure_is_green_yellow_once_over_its_budget_no_budget_plain(self):
        for one, role in ((month(), "added"), (month(45.1, 58.0), "modified"), (month(budget=None), "text")):
            self.cost(reported([one]))
            canvas = self.draw()
            self.assertEqual(self.look(canvas, one["words"]["spent"], row="Codex"), Style(fg=role), one)
        self.assertEqual(self.lines(canvas)[5], "    ▸ Codex API key" + "~$18.40".rjust(WIDE - 1 - 19))

    def test_a_month_over_its_pace_turns_its_bar_and_pace_yellow(self):
        self.cost(reported([month(45.1, 58.0)]), kept={"codex": True})
        canvas = self.draw()
        lines = self.lines(canvas)
        self.assertEqual(lines[5], "    ▾ Codex API key" + "~$45.10 of $50".rjust(WIDE - 1 - 19))
        self.assertEqual(lines[6], "      Nov ▰▰▰▰▰▰▱  on pace for ~$58")
        self.assertEqual([self.look(canvas, words) for words in ("▰▰▰▰▰▰▱", "on pace for ~$58", "~$45.10")],
                         [Style(fg="modified"), Style(fg="modified"), Style(fg="text")])

    def test_a_month_with_no_budget_says_spent_and_draws_no_bar(self):
        self.cost(reported([month(budget=None)]), kept={"codex": True})
        lines = self.lines(self.draw())
        self.assertEqual(lines[5:7], ["    ▾ Codex API key" + "~$18.40 spent".rjust(WIDE - 1 - 19),
                                      "      Nov  on pace for ~$46"])

    def test_an_agent_with_no_price_keeps_its_reset_and_is_never_zero(self):
        self.cost(reported([], claude=None))
        lines = self.lines(self.draw())
        self.assertEqual(lines[3], "    ▾ Claude Max" + "5 hour resets at 2:46 PM".rjust(WIDE - 1 - 16))
        self.assertNotIn("$0", "\n".join(lines))

    def test_a_wide_pane_keeps_the_reset_after_the_bars(self):
        self.cost()
        lines = self.lines(self.draw(80))
        self.assertEqual(lines[4], "      5h ▰▰▰▰▰▱▱ 72%  wk ▰▱▱▱▱▱▱ 16%" + "5 hour resets at 2:46 PM".rjust(79 - 36))

    def test_a_narrow_pane_drops_the_figures_word_then_the_commits_and_the_bar(self):
        self.cost()
        lines = self.lines(self.draw(34))
        self.assertEqual(lines[3], "    ▾ Claude Max" + "~$130.90".rjust(33 - 16))
        self.assertEqual(lines[5], "    ▸ Codex API key" + "~$18.40".rjust(33 - 19))
        self.assertEqual(lines[10], "      lumen-api" + "~$84.20".rjust(33 - 15))
        self.assertTrue(all(len(line) <= 33 for line in lines), lines)
        self.cost(kept={"codex": True})
        lines = self.lines(self.draw(34))
        self.assertEqual(lines[5:7], ["    ▾ Codex API key" + "~$18.40".rjust(33 - 19), "      Nov  on pace for ~$46"])

    def test_commits_say_about_one_and_not_known(self):
        self.cost(reported(projects=[("lumen-api", 84.2, 2, True), ("harbor-web", 41.1, 1, False),
                                     ("tidepool", None, 0, False)]))
        lines = self.lines(self.draw())
        self.assertEqual(lines[10:13], ["      lumen-api" + "~$84.20  about 2 commits".rjust(WIDE - 1 - 15),
                                        "      harbor-web" + "~$41.10  1 commit".rjust(WIDE - 1 - 16 - 7),
                                        "      tidepool" + "no price  none yet".rjust(WIDE - 1 - 14 - 7)])
        self.assertEqual(layers.commits_said({"commits": None, "commits_text": "–"}), "–")

    def test_the_days_they_span_and_a_day_with_no_cost(self):
        self.assertEqual(layers.days_said([{"label": "Oct 28"}, {"label": "Nov 3"}]), "Oct 28 – Nov 3")
        self.assertEqual(layers.days_said([{"label": "Nov 9"}]), "Nov 9")
        daily = reported(days=(0, 0.2, 33.5))["daily"]
        self.assertEqual([block for block, _ in layers.spark(daily, 30)], [" ", "▁", "█"])
        self.assertEqual([block for block, _ in layers.spark(daily, 2)], ["▁", "█"])        # the last that fit

    def test_a_narrow_pane_names_the_days_it_draws(self):
        self.cost(reported(days=(1.0,) * 20))                  # Nov 3 to 22: 30 cells have no room for twenty blocks
        lines = self.lines(self.draw(30))
        self.assertIn("      " + "█" * 10 + "  Nov 13 – 22", lines)
        self.assertIn("      " + "█" * 20 + "  Nov 3 – 22", self.lines(self.draw()))

    def test_nothing_used_says_so_and_conversations_still_read_say_that(self):
        self.cost(reported([], none="Nothing used in this period", claude=None, projects=[], days=(0,) * 7))
        lines = self.lines(self.draw())
        self.assertEqual(lines[5], "      Nothing used in this period")
        self.assertTrue(lines[6].startswith(f" {NERD['closed']}  Rules"), lines[6])
        self.view.reading = True
        self.assertEqual(self.lines(self.draw())[5], "      Reading the conversations…")
        self.cost(left=True)
        self.assertEqual(self.lines(self.draw())[14], "      Reading the conversations…")

    def test_before_the_report_it_is_the_limits_alone(self):
        self.cost()
        self.view.costs = None
        lines = self.lines(self.draw())
        self.assertEqual(lines[3], "    ▾ Claude Max" + "5 hour resets at 2:46 PM".rjust(WIDE - 1 - 16))
        self.assertTrue(lines[5].startswith(f" {NERD['closed']}  Rules"), lines[5])

    def test_p_and_a_press_on_the_period_step_it_round_and_ask_for_its_costs(self):
        self.cost()
        self.assertEqual(self.press("p"), Action("usage_period", ("30d",)))
        self.assertTrue(self.lines(self.draw())[2].endswith("30 days"))
        canvas = self.draw()
        y, x = self.at(canvas, "30 days")
        self.assertEqual(self.view.handle(Mouse("press", x + 1, y, 0)), Action("usage_period", ("month",)))
        self.assertTrue(self.lines(self.draw())[2].endswith(time.strftime("%b")))
        self.assertEqual(self.view.handle(Key("char", "p")), Action("usage_period", ("7d",)))
        self.assertNotIn("usage", self.view.folded)                             # the press did not fold it

    def test_enter_on_its_head_opens_the_usage_view_a_press_folds_it_a_right_click_offers_the_view(self):
        self.cost()
        self.choose(("section", "usage"))
        self.assertEqual(self.press("enter"), Action("open_usage", ("7d",)))
        canvas = self.draw()
        y, x = self.at(canvas, "Usage")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 2)), None)
        self.assertEqual(self.view.menu.menu.choices, ["Open Usage"])
        self.assertEqual(self.view.handle(Key("enter")), Action("open_usage", ("7d",)))
        folded = self.view.handle(Mouse("press", x, y, 0))
        self.assertEqual((folded.name, "usage" in self.view.folded), ("remember_agent_folded", True))

    def test_its_period_is_handed_over(self):
        self.cost()
        self.view.handle(Key("char", "p"))
        other = layers.Layers()
        other.take(json.loads(json.dumps(self.view.kept())))
        self.assertEqual(other.period, "30d")
        other.take({"period": "today"})                                         # not one its head steps through
        self.assertEqual(other.period, "30d")


def wired(ran=False):
    """lumen-api's graph as agent-graph.html draws it, in core's shape (graph.py's node() and edge()); RAN: with what
    usage.html's conversation ran laid in, as core's run() does."""
    G, tagged = graph, lambda text_: {"tag": tag(text_, "muted")}
    made = [
        G.node("rule:p", "in", "rule", "CLAUDE.md", "always · 2.4k", tagged("Personal")),
        G.node("rule:l", "in", "rule", "CLAUDE.md", "always · 1.8k", tagged("Project")),
        G.node("rule:a", "in", "rule", "api.md", "when src/lumen/** is read", tagged("Project")),
        G.node("skill:api", "in", "skill", "api-routes", "skill · when routes change", tagged("Project")),
        G.node("skills:more", "in", "skills", "15 more skills", "on demand · 3.7k"),
        G.node("agent", "agents", "agent", "Claude", "Opus 5.5 · Extra high · Manual"),
        G.node("agent:rev", "agents", "sub", "code-reviewer", "sub-agent · Opus · reads, github",
               tagged("pr-review-toolkit")),
        G.node("tool:files", "uses", "tool", "Read · Edit · Write", "built-in"),
        G.node("tool:Bash", "uses", "tool", "Bash", "built-in"),
        G.node("connector:github", "uses", "connector", "github", "MCP · 32 tools · 6.1k", tagged("Personal")),
        G.node("connector:figma", "uses", "connector", "figma", "needs sign-in", tagged("figma"), state="warn"),
        G.node("connector:sentry", "uses", "connector", "sentry", "failed · spawn npx ENOENT", tagged("Project"),
               state="bad"),
        G.node("connector:notion", "uses", "connector", "Notion", "off here", tagged("claude.ai"), dim=True)]
    made[5]["chips"] = ["PermissionRequest → herdr-fold"]
    gate = lambda *words: [{"text": text_, "tone": text_.split()[0]} for text_ in words]     # noqa: E731
    edges = [G.edge(one["id"], "agent", "always") for one in made[:5]] + [
        G.edge("agent", "agent:rev", "demand"), G.edge("agent", "tool:files", "always", gate("ask", "hook")),
        G.edge("agent", "tool:Bash", "always", gate("ask · pytest allowed", "deny git push", "hook")),
        G.edge("agent", "connector:github", "always", gate("allow")), G.edge("agent", "connector:figma", "waiting"),
        G.edge("agent", "connector:sentry", "failed"), G.edge("agent:rev", "connector:github", "always")]
    ran_ = {"skill:api": 0, "tool:files": 14, "tool:Bash": 6, "agent:rev": 0, "connector:github": 2}
    for one in made:
        del one["then"]
        at = list(ran_).index(one["id"]) + 1 if one["id"] in ran_ else None
        count = ran_.get(one["id"], 0)
        one["run"] = ran and {"ran": bool(at) or one["id"] in ("agent", "rule:p", "rule:l"), "order": at,
                              "sub": one["sub"], "tag": None, "count": count,
                              "started": NOW + 5760 if at == 4 else None,
                              "calls": f"{count} call{'s' * (count != 1)}" if count else None, "cost": None,
                              "model": None, "share": None, "properties": None}
    if ran:
        made[5]["run"].update(sub="Opus 5.5 · 38 turns · 1.2M tokens", properties=A.properties(
            "Claude", state("~$3.70 API value", "ok"), [
                ["Model", "Opus 5.5 · Extra high", None], ["Input", "0.08M", None],
                ["Cache write", "0.31M", "1 hour 0.25M · 5 min 0.06M"], ["Cache read", "2.40M", "84% of its input"],
                ["Output", "0.03M", None], ["Share", "90% of this conversation", None]]))
        made[6]["run"].update(sub="Haiku 5.5 · sub-agent · 0.4M tokens", properties=A.properties(
            "code-reviewer", state("~$0.42 API value", "ok"), [
                ["From", "pr-review-toolkit", "plugin"], ["Started", "by Claude at {time}, step 4", None],
                ["Share", "10% of this conversation", None]]))
    return {"agent": "claude", "name": "Claude", "folder": "/work/lumen-api", "session": "c1" if ran else None,
            "run": ran, "words": graph.WORDS, "nodes": made, "edges": edges, "path": list(ran_) if ran else []}


class Tree(unittest.TestCase):
    """The graph as a tree (agent-chat-design.md's "The TUI"): the agent, what goes in, what it uses with each edge's
    gates in brackets, its sub-agents; This conversation as the numbered path that ran, with its costs."""

    def setUp(self):
        self.addCleanup(time.tzset)
        set_env(self, TZ="UTC")
        time.tzset()

    def test_wiring_is_the_agent_then_what_goes_in_what_it_uses_and_its_sub_agents(self):
        self.assertEqual(layers.tree(wired()), [
            "Claude  Opus 5.5 · Extra high · Manual  [PermissionRequest → herdr-fold]",
            "├ in",
            "│ ├ CLAUDE.md       Personal  always · 2.4k",
            "│ ├ CLAUDE.md       Project   always · 1.8k",
            "│ ├ api.md          Project   when src/lumen/** is read",
            "│ ├ api-routes      Project   skill · when routes change",
            "│ └ 15 more skills            on demand · 3.7k",
            "├ uses",
            "│ ├ Read · Edit · Write             built-in  [ask, hook]",
            "│ ├ Bash                            built-in  [ask · pytest allowed, deny git push, hook]",
            "│ ├ github               Personal   MCP · 32 tools · 6.1k  [allow]",
            "│ ├ figma                figma      needs sign-in",
            "│ ├ sentry               Project    failed · spawn npx ENOENT",
            "│ └ Notion               claude.ai  off here",
            "└ sub-agents",
            "  └ code-reviewer  pr-review-toolkit  sub-agent · Opus · reads, github"])

    def test_a_failed_and_a_waiting_connector_wear_their_colors_one_off_here_is_dim(self):
        rows = {"".join(words for words, _ in row).split()[2]: row for row in layers.tree_rows(wired()) if len(row) > 2}
        self.assertEqual([rows[name][-1] for name in ("sentry", "figma", "Notion")],
                         [("failed · spawn npx ENOENT", "bad"), ("needs sign-in", "warn"), ("off here", "dim")])
        self.assertEqual(rows["Notion"][1][1], "dim")
        self.assertEqual((rows["Bash"][1][1], rows["Bash"][-1]),
                         (None, ("  [ask · pytest allowed, deny git push, hook]", None)))
        first = layers.tree_rows(wired())[0]
        self.assertEqual((first[0], first[1][1]), (("Claude", "bold"), "dim"))

    def test_a_graph_with_nothing_going_in_and_no_sub_agent_ends_on_uses(self):
        made = wired()
        made["nodes"] = [one for one in made["nodes"] if one["column"] == "uses" or one["id"] == "agent"]
        self.assertEqual(layers.tree(made)[1:3],
                         ["└ uses", "  ├ Read · Edit · Write             built-in  [ask, hook]"])

    def test_this_conversation_is_the_numbered_path_then_each_agents_costs_and_the_tools_calls(self):
        self.assertEqual(layers.tree(wired(True), True, twelve=True), [
            "Claude  Opus 5.5 · 38 turns · 1.2M tokens",
            "1 api-routes → 2 Read · Edit · Write → 3 Bash → 4 code-reviewer → 5 github",
            "",
            "Claude",
            "  Cost         ~$3.70 API value",
            "  Model        Opus 5.5 · Extra high",
            "  Input        0.08M",
            "  Cache write  0.31M  1 hour 0.25M · 5 min 0.06M",
            "  Cache read   2.40M  84% of its input",
            "  Output       0.03M",
            "  Share        90% of this conversation",
            "",
            "code-reviewer  Haiku 5.5 · sub-agent · 0.4M tokens",
            "  Cost     ~$0.42 API value",
            "  From     pr-review-toolkit  plugin",
            "  Started  by Claude at 1:36 PM, step 4",
            "  Share    10% of this conversation",
            "",
            "uses",
            "  Read · Edit · Write  14 calls",
            "  Bash                  6 calls",
            "  github                2 calls"])
        self.assertIn("  Started  by Claude at 13:36, step 4", layers.tree(wired(True), True))

    def test_the_path_wraps_at_an_arrow_its_numbers_in_the_accent(self):
        lines = layers.tree(wired(True), True, cells=40)
        self.assertEqual(lines[1:3],
                         ["1 api-routes → 2 Read · Edit · Write →", "  3 Bash → 4 code-reviewer → 5 github"])
        path = layers.tree_rows(wired(True), True)[1]
        self.assertEqual(path[:3], [("1", "accent"), (" api-routes", None), (" → ", "dim")])

    def test_a_conversation_with_no_costs_yet_is_its_path_and_calls(self):
        made = wired(True)
        for one in made["nodes"]:
            one["run"]["properties"] = None
        self.assertEqual(layers.tree(made, True)[2:5], ["", "uses", "  Read · Edit · Write  14 calls"])

    def test_g_and_the_heads_right_click_ask_for_the_graph_only_where_a_setup_shows(self):
        view = layers.Layers(icons=False)
        view.set({**lumen(), "agents": MACHINE})
        self.assertEqual(view.handle(Key("char", "g")), Action("show_graph", ()))
        canvas = Canvas(WIDE, 30)
        view.draw(canvas, 0, 30, True)
        self.assertIsNone(view.handle(Mouse("press", 3, 0, 2)))
        self.assertEqual(view.menu.menu.choices, ["Show graph"])
        self.assertEqual(view.handle(Key("enter")), Action("show_graph", ()))
        view.set({**lumen(), "agents": MACHINE, "agent": "gemini", "empty": MACHINE[2]["empty"]})
        self.assertIsNone(view.handle(Key("char", "g")))
        view.draw(canvas, 0, 30, True)
        view.handle(Mouse("press", 3, 0, 2))
        self.assertIsNone(view.menu)


class Reading(unittest.TestCase):
    """The family: its agent from herdr's list, its setup read in a temporary home, a rule opened, a server checked."""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.home, self.state = os.path.join(tmp, "home"), os.path.join(tmp, "state")
        self.folder = os.path.realpath(os.path.join(tmp, "lumen-api"))
        os.makedirs(self.folder)
        managed = mock.patch.object(agent_setup, "MANAGED_DIR", os.path.join(tmp, "managed"))
        managed.start()
        self.addCleanup(managed.stop)
        set_env(self, HOME=self.home, HERDR_PANE_ID=None, CODEX_HOME=None, HERDR_WORKSPACE_ID=None)
        self.addCleanup(end_jobs)                       # before the folders go: its read job reads there
        # the agents as a stand-in tells them: nothing asks this Mac's Claude or Codex
        self.machine, self.asked = [dict(one) for one in MACHINE], []
        for one in self.machine:
            one.pop("empty")
        told = mock.patch.object(agent_state, "machine_agents", lambda home, which=None, fresh=False: (
            self.asked.append(fresh), [dict(one) for one in self.machine])[1])
        told.start()
        self.addCleanup(told.stop)
        self.put(os.path.join(self.folder, "CLAUDE.md"), "# lumen-api\nRoutes live in src.\n")
        self.put(os.path.join(self.folder, ".mcp.json"), json.dumps(
            {"mcpServers": {"sentry": {"command": "npx", "args": ["-y", "@sentry/mcp-server"]}}}))
        self.put(os.path.join(self.folder, ".claude", "settings.local.json"),
                 json.dumps({"enabledMcpjsonServers": ["sentry"]}))
        self.session = self.put(os.path.join(agent_setup.claude_project_dir(self.folder, self.home), "a0.jsonl"),
                                json.dumps({"type": "attachment", "isSidechain": False, "attachment": {
                                    "type": "deferred_tools_delta", "addedNames": [], "addedLines": [],
                                    "removedNames": [], "failedMcpServers": [
                                        {"name": "sentry", "error": "spawn npx ENOENT"}],
                                    "needsAuthMcpServers": [], "pendingMcpServers": []}}) + "\n")

    def put(self, path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return path

    def app(self):
        return sidebar.App(self.folder, FakeTerminal(WIDE, 40), mock.Mock(call=lambda *args: {}), self.state)

    def read(self, app):
        app.tick()
        end_jobs()
        app.collect()

    def test_the_tabs_agent_is_herdrs_claude_or_codex_there_with_its_session(self):
        listed = {("pane", "list"): {"panes": [{"pane_id": "w1:p2", "tab_id": "w1:t1"}]},
                  ("agent", "list"): {"agents": [
                      {"pane_id": "w1:p7", "tab_id": "w1:t2", "agent": "claude"},
                      {"pane_id": "w1:p1", "tab_id": "w1:t1", "agent": "codex", "cwd": "/work/lumen-api",
                       "agent_session": {"value": "019a"}}]}}
        self.assertEqual(agent_panel.tab_agent(lambda *args: listed.get(args, {}), "w1:p2"),
                         ("codex", "/work/lumen-api", "019a"))
        self.assertIsNone(agent_panel.tab_agent(lambda *args: listed.get(args, {}), "w1:p9"))

    def test_claudes_session_is_the_tabs_else_the_folders_newest(self):
        older = self.put(os.path.join(os.path.dirname(self.session), "b1.jsonl"), "\n")
        os.utime(older, (time.time() - 60, time.time() - 60))
        self.assertEqual(agent_panel.session_file(self.folder, "b1", self.home), older)
        self.assertEqual(agent_panel.session_file(self.folder, None, self.home), self.session)
        self.assertEqual(agent_panel.session_file(self.folder, "../x", self.home), self.session)    # never a path

    def test_it_reads_the_folders_setup_and_dots_its_button_by_the_worst_problem(self):
        app = self.app()
        self.assertNotIn("agent", app.marks())
        self.read(app)
        view = app.views["agent"]
        self.assertEqual(view.answer["head"], {"name": "Claude", "where": "in lumen-api"})
        self.assertEqual(view.problems(), ["1 failed"])
        self.assertEqual(app.marks()["agent"], (sidebar.DOT, "deleted"))

    def test_its_answer_tells_the_limits_the_shown_agent_first_its_reset_in_local_time(self):
        now = int(time.time())
        usage.keep("claude", {"five_hour": {"used": 72, "resets": now + 3600},
                              "week": {"used": 16, "resets": now + 86400}}, now)
        self.put(os.path.join(self.home, ".local", "state", "herdr-fold", "time.json"), '{"twelve": true}')
        app = self.app()
        self.read(app)
        row, = app.views["agent"].answer["usage"]["rows"]
        self.assertEqual((row["name"], row["plan"], row["current"], row["five"]["text"], row["week"]["text"]),
                         ("Claude", "Max", True, "72%", "16%"))
        self.assertRegex(row["resets"]["said"], r"^5 hour resets at \d\d?:\d\d [AP]M$")

    def talk(self, name, model, at, tokens=1000):
        """A Claude conversation NAME in the folder with one answer of MODEL at AT."""
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(at))
        return self.put(os.path.join(agent_setup.claude_project_dir(self.folder, self.home), f"{name}.jsonl"),
                        json.dumps({"type": "assistant", "timestamp": stamp, "cwd": self.folder, "sessionId": name,
                                    "message": {"id": f"msg_{name}", "model": model, "usage": {
                                        "input_tokens": tokens, "output_tokens": tokens}}},
                                   separators=(",", ":")) + "\n")

    def test_what_the_agents_cost_is_read_on_a_job_once_usage_shows_then_a_minute_apart(self):
        now, clock = int(time.time()), [100.0]
        usage.keep("claude", {"five_hour": {"used": 72, "resets": now + 3600}, "week": None}, now)
        session = self.talk("c1", "claude-opus-5-5", now - 60)
        with open(session, encoding="utf-8") as f:
            was = f.read()
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 40), mock.Mock(call=lambda *args: {}), self.state,
                          clock=lambda: clock[0])
        family, view = app.work["agent"], app.views["agent"]
        self.read(app)
        self.assertEqual((view.costs, family.next_costs()), (None, float("inf")))      # behind Files: not read
        app.show("agent")
        self.read(app)
        self.read(app)
        self.assertEqual(view.costs["period"]["id"], "7d")
        self.assertEqual([one["name"] for one in view.costs["projects"]], [os.path.basename(self.folder)])
        self.assertEqual((view.reading, family.next_costs()), (False, 100.0 + agent_panel.COSTS))
        canvas = Canvas(WIDE, 40)
        view.draw(canvas, 0, 40, True)
        shown = [text(canvas, y).rstrip() for y in range(40)]
        self.assertRegex(shown[3], r"^    ▾ Claude Max +~\$\d+\.\d\d API value$")
        self.assertIn("      per day", shown)
        with open(session, encoding="utf-8") as f:
            self.assertEqual(f.read(), was)                                     # Claude's file as it was
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".local", "state", "herdr-fold", "usage-index.json")))

    def test_a_stepped_period_is_read_at_once_and_an_answer_for_another_period_is_not_shown(self):
        app = self.app()
        family, view = app.work["agent"], app.views["agent"]
        self.read(app)
        app.show("agent")
        self.read(app)
        self.read(app)
        app.act(view.handle(Key("char", "p")), "agent")
        self.assertEqual(view.costs["period"]["id"], "7d")                      # the last one, till the new is read
        family.cost("7d", {"report": {"period": {"id": "stale"}}, "left": 0})
        self.assertEqual(view.costs["period"]["id"], "7d")
        end_jobs()
        app.collect()
        self.assertEqual(view.costs["period"]["id"], "30d")

    def test_enter_on_usage_opens_the_plugins_usage_pane_on_the_period(self):
        calls = []
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 40), mock.Mock(call=lambda *args: calls.append(args) or {}),
                          self.state)
        app.act(Action("open_usage", ("30d",)), "agent")
        end_jobs()
        self.assertIn(("plugin", "pane", "open", "--plugin", "herdr-fold.sidebar", "--entrypoint", "usage", "--env",
                       "HERDR_FOLD_USAGE_PERIOD=30d", "--focus"), calls)

    def test_an_agent_opened_or_folded_is_kept_by_core_for_both_clients_and_read_back(self):
        now = int(time.time())
        usage.keep("claude", {"five_hour": {"used": 72, "resets": now + 3600}, "week": None}, now)
        app = self.app()
        app.act(Action("usage_open", ("codex", True)), "agent")
        end_jobs()
        app.collect()
        state = os.path.join(self.home, ".local", "state", "herdr-fold")
        self.assertEqual(usage.kept_open(state), {"codex": True})
        self.read(app)
        self.assertEqual(app.views["agent"].answer["usage"]["open"], {"claude": True, "codex": True})

    def test_show_graph_reads_the_folders_graph_on_a_job_and_opens_its_tree_in_the_preview_tab(self):
        app, opened = self.app(), []
        app.open_preview = lambda spec, cwd: opened.append((spec, cwd))
        self.read(app)
        app.act(Action("show_graph", ()), "agent")
        self.assertEqual(app.note, "Reading the graph…")
        end_jobs()
        app.collect()
        (spec, cwd), = opened
        self.assertEqual((cwd, spec["title"], app.note), (self.folder, "Claude in lumen-api", None))
        self.assertEqual([(one["key"], one["name"]) for one in spec["views"]],
                         [("w", "Wiring"), ("c", "This conversation")])       # the folder's newest conversation
        plain = [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in spec["views"][0]["lines"]]
        self.assertEqual(plain[:2], ["Claude  Manual", "├ in"])
        self.assertIn("│ └ CLAUDE.md  Project  always · <0.1k", plain)
        self.assertTrue(any(line.startswith("  └ sentry") and "failed" in line for line in plain), plain)

    def test_its_answer_tells_the_agents_on_this_machine_each_with_where_it_stands(self):
        app = self.app()
        self.read(app)
        agents = app.views["agent"].answer["agents"]
        self.assertEqual([(one["key"], (one["empty"] or {}).get("kind")) for one in agents],
                         [("claude", None), ("codex", None), ("gemini", "sign-in"), ("aider", "install")])
        self.assertEqual(self.asked, [False])

    def test_a_picked_agent_is_kept_for_the_folder_and_shown_in_every_read(self):
        app = self.app()
        self.read(app)
        app.act(Action("choose_agent", ("gemini",)), "agent")
        end_jobs()
        app.collect()
        answer = app.views["agent"].answer
        self.assertEqual((answer["agent"], answer["head"], answer["empty"]["title"]),
                         ("gemini", {"name": "Gemini CLI", "where": "in lumen-api"}, "Gemini CLI is not signed in"))
        self.assertNotIn("agent", app.marks())                                  # no setup read: no dot
        with open(os.path.join(self.state, "settings.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["agent_chosen"], {self.folder: "gemini"})
        other = self.app()                                                      # another tab's sidebar, later
        self.read(other)
        self.assertEqual(other.views["agent"].answer["agent"], "gemini")
        app.act(Action("choose_agent", ("--help",)), "agent")                   # not an agent: nothing kept
        self.assertEqual(app.settings["agent_chosen"], {self.folder: "gemini"})

    def test_sign_in_runs_the_agents_own_login_in_a_tab_and_asks_again_till_it_is_in(self):
        now, opened = [100.0], []
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 40), mock.Mock(call=lambda *args: {}), self.state,
                          clock=lambda: now[0])
        app.open_tab = lambda label, argv: opened.append((label, argv))
        self.read(app)
        app.show("agent")
        end_jobs()
        app.collect()
        app.act(Action("choose_agent", ("gemini",)), "agent")
        end_jobs()
        app.collect()
        del self.asked[:]
        app.act(Action("sign_in", ("gemini",)), "agent")
        self.assertEqual(opened, [("Sign in to Gemini CLI", ["gemini", "login"])])
        now[0] += agent_panel.SIGNING
        self.read(app)
        self.assertEqual(self.asked, [True])                                    # fresh: not the minute's answer
        self.machine[2]["signed_in"] = True                                     # in: the wait ends
        now[0] += agent_panel.SIGNING
        with mock.patch.object(agent_setup, "codex_setup", side_effect=AssertionError("not Codex's to read")):
            self.read(app)
        self.assertEqual(self.asked, [True, True])
        answer = app.views["agent"].answer                  # in, and no reader of its setup: nothing in its place
        self.assertEqual((answer["agent"], answer.get("empty"), answer.get("sections")), ("gemini", None, None))
        now[0] += agent_panel.SIGNING
        self.read(app)
        self.assertEqual(self.asked, [True, True])
        app.act(Action("sign_in", ("nobody",)), "agent")                        # not an agent told: nothing run
        self.assertEqual(len(opened), 1)

    def test_copy_puts_the_install_line_on_the_clipboard_and_says_so(self):
        app, copied = self.app(), []
        app.work["agent"].clipboard = lambda words: copied.append(words) or True
        app.act(Action("copy_text", ("npm install -g aider",)), "agent")
        self.assertEqual((copied, app.note), (["npm install -g aider"], "Copied"))

    def test_enter_opens_a_rule_in_the_preview_tab_named_as_its_properties_name_it(self):
        app, opened = self.app(), []
        app.open_preview = lambda spec, cwd: opened.append((spec, cwd))
        self.read(app)
        app.show("agent")
        for key in ("home", "down", "down", "right", "down", "enter"):         # the head, Usage, Rules opened, its rule
            app.handle(Key(key))
        spec, cwd = opened[0]
        self.assertEqual((spec["title"], cwd), ("CLAUDE.md", self.folder))
        self.assertIn(os.path.join(self.folder, "CLAUDE.md"), json.dumps(spec))

    def test_retry_checks_the_server_and_shows_its_answer_until_a_session_says_otherwise(self):
        app = self.app()
        self.read(app)
        checked = {"state": agent_setup.ON, "error": None, "url": None}
        with mock.patch.object(agent_state, "check", lambda folder, name: checked):
            app.act(Action("retry_server", ("sentry",)), "agent")
            self.assertIn("sentry", app.views["agent"].checking)
            for _ in range(2):
                end_jobs()
                app.collect()
        view = app.views["agent"]
        self.assertEqual((view.checking, view.problems()), (set(), []))
        sentry = next(row for section in view.answer["sections"] for row in section["rows"] if row["name"] == "sentry")
        self.assertEqual(sentry["state"]["text"], "on")
        with open(self.session, "a", encoding="utf-8") as f:                    # a new session line: Claude's word
            f.write(json.dumps({"type": "attachment", "isSidechain": False, "attachment": {
                "type": "deferred_tools_delta", "addedNames": [], "addedLines": [], "removedNames": [],
                "failedMcpServers": [], "needsAuthMcpServers": ["sentry"], "pendingMcpServers": []}}) + "\n")
        app.work["agent"].ask()
        end_jobs()
        app.collect()
        self.assertEqual(view.problems(), ["1 sign in"])

    def test_it_reads_every_poll_while_shown_less_often_behind_another_view(self):
        now, reads = [100.0], []
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 40), mock.Mock(call=lambda *args: {}), self.state,
                          clock=lambda: now[0])
        family = app.work["agent"]
        family.read = lambda *args: reads.append(now[0]) or None
        for at in (100.0, 100.0 + agent_panel.POLL, 100.0 + agent_panel.AWAY):  # behind Files: every AWAY seconds
            now[0] = at
            app.tick()
            end_jobs()
            app.collect()
        app.show("agent")                                                       # shown: at once, then every POLL
        end_jobs()
        app.collect()
        now[0] += agent_panel.POLL
        app.tick()
        end_jobs()
        self.assertEqual(reads, [100.0, 100.0 + agent_panel.AWAY, 100.0 + agent_panel.AWAY,
                                 100.0 + agent_panel.AWAY + agent_panel.POLL])


    def test_off_the_row_it_reads_nothing_until_it_is_back(self):
        app, reads = self.app(), []
        app.work["agent"].read = lambda *args: reads.append(True) or None
        app.hide("agent", True)
        app.tick()
        end_jobs()
        self.assertEqual((reads, app.work["agent"].deadlines()), ([], [float("inf")]))
        app.show("agent")                                                       # its key or More's check
        end_jobs()
        self.assertEqual(reads, [True])


class Dock(unittest.TestCase):
    """The Agent view in the dock: its button, its key, its dot and its tip."""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        set_env(self, HOME=os.path.join(tmp, "home"), HERDR_PANE_ID=None)
        self.addCleanup(end_jobs)
        self.app = sidebar.App(tmp, FakeTerminal(sidebar.column.IDEAL, 30), mock.Mock(call=lambda *args: {}),
                               os.path.join(tmp, "state"))

    def test_the_row_has_seven_buttons_agent_after_issues_its_robot_over_its_name(self):
        self.assertEqual([panel for panel, *_ in sidebar.stack.laid(sidebar.grouped(sidebar.PANELS), 80)],
                         ["files", "search", "changes", "issues", "agent", "chats", "panels"])
        self.app.draw()
        names = text(self.app.canvas, sidebar.stack.NAMES)
        self.assertEqual(names.split(), ["Files", "Search", "Changes", "Agent", "Chats", "More"])  # no Issues here
        at = names.index("Agent")
        self.assertEqual(text(self.app.canvas, sidebar.stack.ROW)[at + 2], NERD["robot"])      # its very middle

    def test_five_shows_the_agent_view_and_the_rail_raises_its_terminal_with_six(self):
        self.app.handle(Key("char", "5"))
        self.assertEqual(self.app.shown(), "agent")
        raised = []
        self.app.railed = True
        self.app.raise_terminal = lambda: raised.append(True)
        self.app.handle(Key("char", "6"))
        self.assertEqual(raised, [True])

    def test_its_buttons_tip_names_its_problems(self):
        self.app.views["agent"].set(lumen())
        self.app.draw()
        self.app.point("button:agent", 40, sidebar.stack.ROW)
        self.assertEqual(self.app.tip[1], "Agent · 1 failed, 1 sign in")
        self.assertEqual(self.app.marks()["agent"], (sidebar.DOT, "deleted"))


class Connectors(unittest.TestCase):
    """Connectors as connectors.html's TUI panes: a brand's glyph or letter, Connect, a sign-in under way, Turn off
    here, the ⋯ menu's lines and the form a connector is added with."""

    BOX = "claude.ai Box"
    setUp, draw, lines, at, look, press, choose = (View.setUp, View.draw, View.lines, View.at, View.look, View.press,
                                                   View.choose)

    def under(self, canvas, words, rows):
        y = self.at(canvas, words)[0]
        return [text(canvas, y + n).rstrip() for n in range(1, rows + 1)]

    def test_a_known_service_wears_its_glyph_in_its_color_else_its_letter_another_its_own_letter_dim(self):
        canvas = self.draw()
        self.assertTrue(text(canvas, self.at(canvas, "sentry")[0]).startswith(
            f"    ✕ {connectors.BRANDS['sentry']['glyph']} sentry"))
        self.assertEqual(self.look(canvas, connectors.BRANDS["sentry"]["glyph"]).fg, "#e1567c")
        self.assertTrue(text(canvas, self.at(canvas, "Box")[0]).startswith("    ● B Box"))      # no glyph in the font
        self.assertEqual(self.look(canvas, "B Box").fg, "#3b8fe6")
        found = lumen()                                 # one of no known brand: its own letter, dim
        found["sections"][3]["rows"][4] = A.layer("connector:tidepool-db", "plug", "tidepool-db", A.properties(
            "tidepool-db"), mark=tag("Local", "muted"), state=state("on", "ok"))
        self.view.set(found)
        canvas = self.draw()
        self.assertTrue(text(canvas, self.at(canvas, "tidepool-db")[0]).startswith("    ● T tidepool-db"))
        self.assertEqual(self.look(canvas, "T tidepool-db").fg, "muted")
        self.assertEqual(self.at(canvas, "Rules")[1], 4)                        # a section's title where it was
        self.view.icons = False                         # plain glyphs: every brand by its letter
        self.assertIn(" ✕ S sentry", text(self.draw(), self.at(self.draw(), "sentry")[0]))

    def test_a_brands_own_color_is_drawn_as_it_is_in_any_theme(self):
        self.assertEqual(Theme().sgr(Style(fg="#3b8fe6")), "\x1b[38;2;59;143;230m")
        self.assertEqual(Theme().sgr(Style(fg="muted")), "\x1b[90m")

    def test_box_to_sign_in_offers_connect_lit_and_turn_off_here(self):
        self.choose(("row", "connector:" + self.BOX))
        canvas = self.draw()
        self.assertEqual(self.under(canvas, "B Box", 2), ["        URL  mcp.box.com",
                                                          "         Connect    Turn off here"])
        lit = self.look(canvas, "Connect    Turn")
        self.assertEqual((lit.bg, lit.fg, lit.bold), ("button", "button_text", True))
        self.assertEqual((self.look(canvas, "Turn off here").bg, self.look(canvas, "Turn off here").fg),
                         ("input", "subtext"))
        self.assertEqual(self.press("enter"), Action("connect_server", (self.BOX,)))
        y, x = self.at(canvas, "Turn off here")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("turn_server", (self.BOX, False)))

    def test_with_no_claude_in_the_tab_turn_off_waits_and_says_for_what(self):
        self.view.set({**lumen(), "claude": False})
        self.choose(("row", "connector:" + self.BOX))
        canvas = self.draw()
        self.assertEqual(self.look(canvas, "Turn off here").fg, "muted")
        y, x = self.at(canvas, "Turn off here")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)),
                         Action("say", ("Start Claude in this tab to turn it off here",)))
        self.choose(("row", "connector:claude.ai Notion"))
        self.assertEqual(self.press("enter"), Action("say", ("Start Claude in this tab to turn it on here",)))

    def test_a_row_signing_in_turns_its_mark_and_says_what_to_do(self):
        self.view.signing = {self.BOX}
        self.choose(("row", "connector:" + self.BOX))
        canvas = self.draw()
        y = self.at(canvas, "B Box")[0]
        self.assertTrue(text(canvas, y).startswith("    ◐ B Box"))
        self.assertEqual(canvas.rows[y][4][1].fg, "accent")
        self.assertEqual(self.look(canvas, "signing in").fg, "accent")
        self.assertEqual(self.under(canvas, "B Box", 2), ["        Finish in your browser",
                                                          "         Open the page again    Cancel"])
        self.assertEqual(self.look(canvas, "Open the page again").bg, "input")          # neither is Connect
        self.assertEqual(self.press("enter"), Action("reopen_sign_in", (self.BOX,)))
        y, x = self.at(canvas, "Cancel")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)), Action("cancel_sign_in", (self.BOX,)))

    def test_one_signed_in_offers_turn_off_and_sign_out(self):
        self.choose(("row", "connector:claude.ai Google Drive"))
        canvas = self.draw()
        self.assertIn("         Turn off here    Sign out", self.under(canvas, "Google Drive", 2))
        self.assertEqual(self.look(canvas, "Turn off here").bg, "input")                # only Connect is lit
        y, x = self.at(canvas, "Sign out")
        self.assertEqual(self.view.handle(Mouse("press", x, y, 0)),
                         Action("sign_out_server", ("claude.ai Google Drive",)))

    def test_codex_rows_never_offer_claudes_own_commands(self):
        row = A.layer("connector:linear", "plug", "linear", A.properties("linear", actions=[
            A.act("sign-out", "Sign out", server="linear"), A.act("turn-off", "Turn off in tidepool", server="linear"),
            A.act("retry", "Retry", server="linear"),
            A.act("open", "Open config.toml", "/home/dev/.codex/config.toml")]))
        self.assertEqual([one["id"] for one in layers.doable(row, "codex")], ["sign-out", "open"])
        self.assertEqual([one["id"] for one in layers.doable(row, "claude")], ["sign-out", "turn-off", "retry", "open"])

    def test_the_more_menu_adds_a_connector_two_ways_and_reads_again(self):
        self.assertEqual(self.view.menu_lines(), ["Add from claude.ai", "Add by URL", "Refresh"])
        self.assertEqual(self.view.menu_pick("Add from claude.ai"), Action("open_url", (connectors.CLAUDE_AI,)))
        self.assertEqual(self.view.menu_pick("Refresh"), Action("refresh_agent", ()))
        self.assertIsNone(self.view.menu_pick("Add by URL"))
        self.assertTrue(self.view.form and self.view.editing)
        codex = layers.Layers(icons=True)
        codex.set({**lumen(), "agent": "codex", "connect": A.connecting("codex", "/work/lumen-api")})
        self.assertEqual(codex.menu_lines(), ["Add by URL", "Refresh"])     # claude.ai's are Claude's alone
        for none in (None, {**lumen(), "agents": MACHINE, "empty": MACHINE[2]["empty"]}):
            empty = layers.Layers(icons=True)
            if none:
                empty.set(none)
            self.assertEqual(empty.menu_lines(), [])

    def type(self, words):
        for ch in words:
            self.press(ch)

    def test_a_opens_the_form_from_the_keys_where_a_connector_can_be_added(self):
        self.press("a")
        self.assertEqual((bool(self.view.form), self.view.chosen), (True, ("section", "connectors")))
        self.press("esc")
        self.view.set({**lumen(), "agents": MACHINE, "empty": MACHINE[2]["empty"]})      # no setup: nothing to add to
        self.press("a")
        self.assertIsNone(self.view.form)

    def test_the_form_lies_under_connectors_head_and_the_keys_walk_it(self):
        self.view.menu_pick("Add by URL")
        self.type("dropbox")
        self.press("tab")
        self.type("https://mcp.dropbox.com/mcp")
        canvas = self.draw()
        self.assertEqual(self.under(canvas, "Connectors", 5), [
            "    Add a connector", "    Name  dropbox", "    URL   https://mcp.dropbox.com/mcp",
            "    For    lumen-api    All projects", "     Add and connect    Cancel"])
        self.assertEqual(self.look(canvas, "Add a connector").bold, True)
        self.assertEqual(self.look(canvas, "dropbox").bg, "input")
        self.assertEqual((self.look(canvas, "lumen-api", "    For").bg, self.look(canvas, "All projects").bg),
                         ("button", None))                                     # this folder's, till chosen otherwise
        self.assertTrue(text(canvas, self.at(canvas, "Add and connect")[0] + 2).startswith("    ✕"))   # then the rows
        self.assertEqual(canvas.cursor, (self.at(canvas, "https://")[0], self.at(canvas, "https://")[1] + 27))
        self.press("tab")                               # For: ← → choose
        self.press("right")
        self.assertEqual(self.look(self.draw(), "All projects").bg, "button")
        self.press("tab")                               # Add and connect: lit always, the cursor on it now
        canvas = self.draw()
        self.assertEqual((self.look(canvas, "Add and connect").bg, canvas.cursor),
                         ("button", self.at(canvas, "Add and connect")))
        self.assertEqual(self.press("enter"),
                         Action("add_connector", ("dropbox", "https://mcp.dropbox.com/mcp", "user")))
        self.press("tab")                               # Cancel
        self.assertIsNone(self.press("enter"))
        self.assertEqual((self.view.form, self.view.editing), (None, False))

    def test_enter_in_a_field_adds_esc_leaves_and_a_refused_field_says_why_with_the_keys_back_in_it(self):
        self.view.menu_pick("Add by URL")
        self.type("my box")
        self.assertEqual(self.press("enter"), Action("add_connector", ("my box", "", "local")))
        self.press("tab")
        self.view.refuse({"field": "name", "error": "Letters, digits, - and _ only"})
        canvas = self.draw()
        self.assertEqual(self.look(canvas, "Letters, digits, - and _ only").fg, "deleted")
        self.assertEqual(canvas.cursor[0], self.at(canvas, "my box")[0])
        self.press("q")                                 # a letter is the field's, never the dock's key
        self.assertIn("my boxq", "\n".join(self.lines(self.draw())))
        self.assertNotIn("Letters, digits", "\n".join(self.lines(self.draw())))        # typed over: no longer refused
        self.press("esc")
        self.assertIsNone(self.view.form)

    def test_codex_adds_by_its_address_alone_for_every_folder(self):
        self.view.set({**lumen(), "agent": "codex", "connect": A.connecting("codex", "/work/lumen-api")})
        self.view.menu_pick("Add by URL")
        self.type("figma")
        self.assertNotIn("For", "\n".join(self.under(self.draw(), "Connectors", 5)))
        self.assertEqual(self.press("enter"), Action("add_connector", ("figma", "", None)))

    def test_a_click_in_the_form_puts_the_keys_there_and_presses_its_buttons(self):
        self.view.menu_pick("Add by URL")
        canvas = self.draw()
        y, x = self.at(canvas, "All projects")
        self.view.handle(Mouse("press", x, y, 0))
        self.assertEqual(self.look(self.draw(), "All projects").bg, "button")
        y, x = self.at(canvas, "URL")
        self.view.handle(Mouse("press", x + 8, y, 0))
        self.type("x")
        self.assertIn("URL   x", "\n".join(self.lines(self.draw())))
        y, x = self.at(canvas, "Cancel")
        self.view.handle(Mouse("press", x, y, 0))
        self.assertIsNone(self.view.form)


class Commands(unittest.TestCase):
    """The family runs the agent's own commands: a sign-in in a tab of its own, watched till it ends; Claude's /mcp
    typed into the tab's Claude; a sign-out and an add as plain commands; nothing of the agent's written here."""

    setUp, put, read = Reading.setUp, Reading.put, Reading.read

    def started(self, panes=("w1:p9",)):
        """An app whose herdr lists PANES (mutable), its tabs opened and closed kept; the Agent view shown."""
        self.panes, self.opened, self.calls, self.screen, self.read_of = list(panes), [], [], "", []
        self.now = 100.0

        def call(*args):
            self.calls.append(args)
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": pane, "tab_id": "w1:t9"} for pane in self.panes]}
            return {}
        herdr = mock.Mock(call=call, text=lambda *args: (self.read_of.append(args), self.screen)[1])
        app = sidebar.App(self.folder, FakeTerminal(WIDE, 40), herdr, self.state, clock=lambda: self.now)
        app.open_tab = lambda label, argv, then=None: (self.opened.append((label, argv)), then and then(
            ("w1:p9", "w1:t9")))[0]
        self.read(app)
        app.show("agent")
        self.settle(app)
        return app

    def settle(self, app):
        for _ in range(3):
            end_jobs()
            app.collect()

    def test_connect_runs_the_agents_own_login_in_a_tab_and_the_row_signs_in_till_the_tab_is_gone(self):
        app, checks = self.started(), []
        view = app.views["agent"]
        with mock.patch.object(agent_state, "check", lambda folder, name: (
                checks.append(name), {"state": agent_setup.ON, "error": None, "url": None})[1]):
            app.act(Action("connect_server", ("sentry",)), "agent")
            self.assertEqual(self.opened, [("Sign in to sentry", ["claude", "mcp", "login", "sentry"])])
            self.assertEqual(view.signing, {"sentry"})
            app.act(Action("connect_server", ("sentry",)), "agent")             # one per server
            self.assertEqual(len(self.opened), 1)
            self.now += agent_panel.WATCH
            app.tick()
            self.settle(app)
            self.assertEqual((view.signing, checks), ({"sentry"}, []))          # its pane still there
            del self.panes[:]                           # signed in or cancelled: its exit tells neither
            self.now += agent_panel.WATCH
            app.tick()
            self.settle(app)
        self.assertEqual((view.signing, checks), (set(), ["sentry"]))           # Claude asked about it again

    def test_a_name_like_an_option_starts_nothing(self):
        app = self.started()
        app.act(Action("connect_server", ("--help",)), "agent")
        self.assertEqual((self.opened, app.views["agent"].signing), ([], set()))

    def test_cancel_closes_the_sign_ins_tab_and_asks_again(self):
        app, checks = self.started(), []
        with mock.patch.object(agent_state, "check", lambda folder, name: (
                checks.append(name), {"state": agent_setup.SIGN_IN, "error": None, "url": None})[1]):
            app.act(Action("connect_server", ("sentry",)), "agent")
            app.act(Action("cancel_sign_in", ("sentry",)), "agent")
            self.settle(app)
        self.assertIn(("tab", "close", "w1:t9"), self.calls)
        self.assertEqual((app.views["agent"].signing, checks), (set(), ["sentry"]))

    def test_a_sign_in_left_waiting_ten_minutes_is_ended(self):
        app = self.started()
        with mock.patch.object(agent_state, "check", lambda folder, name: {"state": agent_setup.SIGN_IN,
                                                                           "error": None, "url": None}):
            app.act(Action("connect_server", ("sentry",)), "agent")
            self.now += agent_panel.SIGNING_FOR + 1
            app.tick()
            self.settle(app)
        self.assertIn(("tab", "close", "w1:t9"), self.calls)
        self.assertEqual(app.views["agent"].signing, set())

    def test_open_the_page_again_opens_the_address_the_sign_in_printed_never_another(self):
        app, opened = self.started(), []
        asked = "https://mcp.sentry.dev/authorize?client_id=lumen&state=J1MQ"
        with mock.patch.object(agent_panel.media, "open_in_browser", lambda url: opened.append(url) or True):
            app.act(Action("connect_server", ("sentry",)), "agent")
            self.screen = f"If the browser didn't open, visit:\n  {asked}\n\nWaiting for authorization…\n"
            app.act(Action("reopen_sign_in", ("sentry",)), "agent")
            self.settle(app)
            self.assertEqual(opened, [asked])
            self.assertEqual(self.read_of, [("pane", "read", "w1:p9", "--source", "recent-unwrapped", "--lines",
                                             "200")])
            self.screen = "Starting authentication…\n"
            app.act(Action("reopen_sign_in", ("sentry",)), "agent")
            self.settle(app)
        self.assertEqual(opened, [asked])
        self.assertEqual(app.note, "Its address is not printed yet")

    def test_turn_off_types_claudes_own_command_into_the_tabs_claude_not_sent(self):
        app = self.started()
        set_env(self, HERDR_PANE_ID="w1:p1")

        def call(*args):
            self.calls.append(args)
            if args[:2] == ("pane", "list"):
                return {"panes": [{"pane_id": "w1:p1", "tab_id": "w1:t1"}, {"pane_id": "w1:p2", "tab_id": "w1:t1"}]}
            if args[:2] == ("agent", "list"):
                return {"agents": [{"pane_id": "w1:p2", "tab_id": "w1:t1", "agent": "claude", "cwd": self.folder}]}
            return {}
        app.herdr.call = call
        app.act(Action("turn_server", ("sentry", False)), "agent")
        self.settle(app)
        self.assertIn(("pane", "send-text", "w1:p2", "/mcp disable sentry"), self.calls)
        self.assertIn(("agent", "focus", "w1:p2"), self.calls)
        self.assertFalse([args for args in self.calls if args[:2] == ("pane", "send-keys")])     # typed, not sent
        app.act(Action("turn_server", ("sentry", True)), "agent")
        self.settle(app)
        self.assertIn(("pane", "send-text", "w1:p2", "/mcp enable sentry"), self.calls)

    def test_sign_out_runs_the_agents_own_logout_then_asks_again(self):
        app, ran, checks = self.started(), [], []
        with mock.patch.object(agent_setup, "run", lambda argv, cwd=None, timeout=None, read=True: (
                ran.append((argv, cwd)), (0, 'Signed out of "sentry".', ""))[1]), \
                mock.patch.object(agent_state, "check", lambda folder, name: (
                    checks.append(name), {"state": agent_setup.SIGN_IN, "error": None, "url": None})[1]):
            app.act(Action("sign_out_server", ("sentry",)), "agent")
            self.settle(app)
        self.assertEqual(ran, [(["claude", "mcp", "logout", "sentry"], self.folder)])
        self.assertEqual(checks, ["sentry"])

    def test_a_refused_form_runs_nothing_and_says_which_field(self):
        app, ran = self.started(), []
        view = app.views["agent"]
        view.menu_pick("Add by URL")
        with mock.patch.object(agent_setup, "run", lambda *args, **more: ran.append(args) or (0, "", "")):
            app.act(Action("add_connector", ("my box", "https://mcp.box.com", "local")), "agent")
            self.settle(app)
        self.assertEqual(ran, [])
        self.assertEqual(view.form["error"], {"field": "name", "error": "Letters, digits, - and _ only"})

    def test_add_runs_the_agents_own_command_chooses_the_new_row_and_connects_where_it_must(self):
        app, ran = self.started(), []
        view = app.views["agent"]
        view.menu_pick("Add by URL")
        with mock.patch.object(agent_setup, "run", lambda argv, cwd=None, timeout=None, read=True: (
                ran.append((argv, cwd)), (0, "Added HTTP MCP server dropbox", ""))[1]), \
                mock.patch.object(agent_state, "check", lambda folder, name: {"state": agent_setup.SIGN_IN,
                                                                              "error": None, "url": None}):
            app.act(Action("add_connector", ("dropbox", "https://mcp.dropbox.com/mcp", "local")), "agent")
            self.settle(app)
        self.assertEqual(ran, [(["claude", "mcp", "add", "--transport", "http", "--scope", "local", "dropbox",
                                 "https://mcp.dropbox.com/mcp"], self.folder)])
        self.assertEqual((view.form, view.wanted), (None, ("row", "connector:dropbox")))      # chosen once read
        self.assertEqual(self.opened, [("Sign in to dropbox", ["claude", "mcp", "login", "dropbox"])])

    def test_what_the_agent_says_of_a_failed_add_stays_in_the_form(self):
        app = self.started()
        view = app.views["agent"]
        view.menu_pick("Add by URL")
        with mock.patch.object(agent_setup, "run", lambda *args, **more: (
                1, "MCP server sentry already exists in local config\n", "")):
            app.act(Action("add_connector", ("sentry", "https://mcp.sentry.dev/mcp", "local")), "agent")
            self.settle(app)
        self.assertEqual(view.form["error"], {"field": None,
                                              "error": "MCP server sentry already exists in local config"})
        self.assertEqual(self.opened, [])

    def test_refresh_reads_the_setup_again(self):
        app = self.started()
        del self.asked[:]
        app.act(Action("refresh_agent", ()), "agent")
        self.settle(app)
        self.assertEqual(len(self.asked), 1)

    def test_more_lists_the_agent_views_own_lines_first_while_it_shows(self):
        app = self.started()
        app.open_menu(0, 0)
        self.assertEqual(app.menu[0].choices[:4], ["Add from claude.ai", "Add by URL", "Refresh", None])
        app.handle(Key("down"))
        app.handle(Key("enter"))
        self.assertTrue(app.views["agent"].form)
        app.show("files")
        app.open_menu(0, 0)
        self.assertNotIn("Refresh", app.menu[0].choices)


if __name__ == "__main__":
    unittest.main()
