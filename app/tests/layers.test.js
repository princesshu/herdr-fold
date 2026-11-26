// @ts-check
// Tests for the Agent panel's own rules (layers.js): the agent shown, a section's rows, groups and fold, the filter,
// the tags' column, the bar's colors, which changes are a new read; a row's properties, the dot, an ask, Usage.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { contrast } from "../mods/herdr-fold/agents.js";
import { agentList, agentOf, ASK_MS, asked, bodyHeight, CHIP_LIFT, chipColors, chosenAgent, chosenFill,
  chosenRow, doable, errorColors, FIRST, FOLDED, GROUP_H, HEAD_H, keepAgent, keepOpen, keepProblems, matches, MORE_H,
  partColor, problem, problemTone, propertyLines, READ, ROW_H, sectionOpen, serverOf, shown, signInTab, tabAgent,
  tagRoom, tagWord, toneColor, toneInk, touches, USAGE_LINE, levelColor, levelFill, levelInk, resetWords, usageAgents,
  usageHeight, WARN_H, WORKS, actionLook, claudeIn, loginRun, MCP_AGENT, MCP_AT, MCP_LOGIN, overdue, printedAddress,
  SIGNING_MS, signingRow, signIns, tile, checkedOver, plusMenu, switched, graphAgent, usageRows, usageFigure, headline,
  usageLine, usageRow, afterSave, approves, asking, filePath, footWords, formAsk, headParts, HOOKS, layersShown, MODEL,
  RULE, removable, rowless, sayOnly, sentence, switchShown, GRAPHED }
  from "../mods/herdr-fold/layers.js";

/** A row as core words it, OVER changing it. @param {string} name @param {Record<string, any>} [over] */
const row = (name, over = {}) => ({ id: `skill:${name}`, icon: "skill", name, note: null, tag: "Project", mark: null,
  state: null, brand: null, tokens: 300, cost: "300", agents: ["claude"], dim: false, ...over });
/** A section of ROWS. @param {any[]} rows @param {Record<string, any>} [over] */
const section = (rows, over = {}) => ({ id: "skills", title: "Skills", count: rows.length, tokens: 4000, cost: "4.0k",
  swatch: "skills", summary: [], rows, groups: [], ...over });
/** A conflict as core words it: its mark and its sentence. @param {string} rule */
const conflict = (rule) => row(rule, { id: `conflict:allow:${rule}`, icon: "shield", mark: "warn", tag: null,
  cost: null, tokens: null, note: "deny in Project hides allow in Global" });
const names = (/** @type {{ rows: any[] }} */ found) => found.rows.map((r) => r.name);

test("a section shows its first five rows, then N more; its marked rows always; never 1 more", () => {
  const sixteen = section(Array.from({ length: 16 }, (_, n) => row(`skill-${n}`)));
  assert.equal(FIRST, 5);
  assert.deepEqual([shown(sixteen).rows.length, shown(sixteen).more], [5, 11]);
  const all = shown(sixteen, { more: new Set(["skills"]) });
  assert.deepEqual([all.rows.length, all.more], [16, 0]);
  const marked = section(sixteen.rows.map((r, n) => (n === 9 ? { ...r, mark: "ok" } : n === 12 ? { ...r,
    mark: "bad", state: { text: "failed", tone: "bad" } } : n === 14 ? { ...r, mark: "warn" } : r)));
  assert.deepEqual(names(shown(marked)).slice(5), ["skill-9", "skill-12", "skill-14"]);    // in their own order
  assert.equal(shown(marked).more, 8);
  const six = section(sixteen.rows.slice(0, 6));        // one past five: its line would show the row itself
  assert.deepEqual([shown(six).rows.length, shown(six).more], [6, 0]);
  const seven = shown(section(sixteen.rows.slice(0, 7)));
  assert.deepEqual([seven.rows.length, seven.more], [5, 2]);
  assert.deepEqual(shown(section([])), { rows: [], more: 0, groups: [] });
});

test("a problem is a row core marks failed (bad) or to sign in or in conflict (warn), never one used or plain", () => {
  assert.ok(problem(row("sentry", { mark: "bad", state: { text: "failed", tone: "bad" } })));
  assert.ok(problem(row("Box", { mark: "warn", state: { text: "sign in", tone: "warn" } })));
  assert.ok(problem(conflict("Bash(git push:*)")));
  assert.ok(!problem(row("github", { mark: "ok", state: { text: "32 tools", tone: "ok" } })));
  assert.ok(!problem(row("Bash(rm -rf *)", { state: { text: "deny", tone: "deny" } })));   // a rule, not a problem
});

test("Codex's approval is a row of Permissions as core words it: read, found by its words, Open its one action", () => {
  const open = { id: "open", label: "Open config.toml", path: "/home/dev/.codex/config.toml", server: null,
    primary: true };
  const approval = row("Approval", { id: "approval", icon: "shield", note: "Ask on request", cost: null,
    agents: ["codex"], tag: "Global", properties: { title: "Approval", state: null,
      lines: [["From", "~/.codex/config.toml", "Global"]], text: null, error: null, actions: [open] } });
  const rules = Array.from({ length: 7 }, (_, n) => row(`git ${n}`, { id: `permission:allow:git ${n}`,
    state: { text: "allow", tone: "allow" } }));
  const found = shown(section([approval, ...rules], { id: "permissions", title: "Permissions" }));
  assert.equal(found.rows[0], approval);                                       // first: never under "N more"
  assert.deepEqual([problem(approval), serverOf(approval)], [false, null]);
  assert.ok(matches(approval, "ask request") && matches(approval, "approval global"));
  assert.equal(bodyHeight({ rows: [approval], more: 0, groups: [] }), ROW_H);  // one line, as a rule's
  assert.deepEqual(propertyLines(approval), [["From", "~/.codex/config.toml", "Global"]]);
  assert.deepEqual(doable(approval, "codex").map((one) => one.id), ["open"]);  // nothing that sets it
});

test("the filter finds a row by every word typed, in its name, note, state or tag; found rows all show", () => {
  const api = row("api.md", { note: "when src/lumen/** is read", dim: true });
  assert.ok(matches(api, "API"));
  assert.ok(matches(api, "lumen project"));
  assert.ok(!matches(api, "lumen global"));
  assert.ok(matches(row("sentry", { state: { text: "failed", tone: "bad" } }), "fail"));
  assert.ok(matches(api, "  "));
  const many = section(Array.from({ length: 16 }, (_, n) => row(n % 2 ? `route-${n}` : `store-${n}`)));
  assert.deepEqual([shown(many, { query: "route" }).rows.length, shown(many, { query: "route" }).more], [8, 0]);
  assert.deepEqual(shown(many, { query: "nothing" }), { rows: [], more: 0, groups: [] });
});

test("a section's rows spring to their own height: a row 26, a conflict's two lines 40, N more 24, none one line",
  () => {
    assert.deepEqual([HEAD_H, ROW_H, WARN_H, MORE_H, GROUP_H], [28, 26, 40, 24, 22]);
    assert.equal(bodyHeight({ rows: [row("a"), conflict("Bash(git push:*)"), row("b")], more: 0, groups: [] }),
      26 + 40 + 26);
    assert.equal(bodyHeight({ rows: [row("a")], more: 14, groups: [] }), 26 + 24);
    assert.equal(bodyHeight({ rows: [], more: 0, groups: [] }), 26);
    // a group under the rows: its head, its rows, its own N more
    assert.equal(bodyHeight({ rows: [row("a")], more: 0, groups: [{ id: "hooks", title: "Hooks", count: 7,
      rows: [row("h1"), row("h2")], more: 5 }] }), 26 + 22 + 26 + 26 + 24);
  });

test("Permissions' Hooks group: its rows under the section's own, each shown five at a time, found by the filter",
  () => {
    const hooks = Array.from({ length: 8 }, (_, n) => row(`hook-${n}`, { id: `hook:/p:Stop::hook-${n}`,
      icon: "hook", state: { text: "hook", tone: "muted" } }));
    const permissions = section([row("Mode", { id: "mode" }), conflict("Bash(git push:*)")], { id: "permissions",
      title: "Permissions", count: null, groups: [{ id: "hooks", title: "Hooks", count: 8, rows: hooks }] });
    const found = shown(permissions);
    assert.deepEqual([found.rows.length, found.groups.length, found.groups[0].rows.length, found.groups[0].more],
      [2, 1, 5, 3]);
    assert.equal(shown(permissions, { more: new Set(["hooks"]) }).groups[0].more, 0);
    assert.deepEqual(shown(permissions, { query: "hook-6" }).groups[0].rows.map((r) => r.name), ["hook-6"]);
    assert.deepEqual(shown(permissions, { query: "Mode" }).groups, []);        // a group with nothing found goes
    assert.equal(chosenRow([permissions], "hook:/p:Stop::hook-6")?.row.name, "hook-6");
    assert.deepEqual(shown(permissions, { chosen: "hook:/p:Stop::hook-6" }).groups[0].rows.length, 6);
  });

test("a section's fold is kept per space: all open but Subagents till folded by hand, a space gone forgotten", () => {
  assert.deepEqual(FOLDED, ["subagents"]);
  assert.deepEqual(["rules", "subagents"].map((id) => sectionOpen(null, "sp1", id)), [true, false]);
  const kept = keepOpen({ gone: { rules: false }, sp1: { skills: false } }, "sp1", "subagents", true,
    new Set(["sp1"]));
  assert.deepEqual(kept, { sp1: { skills: false, subagents: true } });
  assert.deepEqual(["rules", "skills", "subagents"].map((id) => sectionOpen(kept, "sp1", id)), [true, false, true]);
  assert.equal(sectionOpen(kept, "sp2", "skills"), true);            // another space: its own
  assert.deepEqual(keepOpen("x", "sp1", "rules", false, new Set(["sp1"])), { sp1: { rules: false } });
});

test("a long tag is cut to its column; a tone is its theme's color; a part of what loads its bar's", () => {
  assert.equal(tagWord("Project"), "Project");
  assert.equal(tagWord("chrome-devtools-mcp"), "chrome-devt…");
  const t = { ansi1: "red", ansi2: "green", ansi3: "yellow", ansi4: "blue", ansi6: "teal", accent: "accent",
    dim: "dim", muted: "muted" };
  assert.deepEqual(["bad", "deny", "warn", "ask", "allow", "busy", "off", "ok", "muted", "else"].map((tone) =>
    toneColor(t, tone)), ["red", "red", "yellow", "yellow", "green", "accent", "dim", "muted", "muted", "muted"]);
  // the Agent panel's bar and swatches and the Context panel's bar, as connectors.html's and center-chat.html's
  assert.deepEqual(["rules", "skills", "connectors", "rest"].map((part) => partColor(t, part)),
    ["accent", "teal", "blue", "muted"]);
});

test("a section's tags stand in one column as wide as its widest tag; a change touches a setup or not", () => {
  const plugin = row("d", { tag: "chrome-devtools-mcp" });
  assert.equal(tagRoom(section([row("c", { tag: null }), plugin])), 12 * 6 + 12);     // the cut tag's twelve
  assert.equal(tagRoom(section([row("a"), row("b", { tag: "claude.ai" })])), 9 * 6 + 12);
  assert.equal(tagRoom(section(Array.from({ length: 9 }, (_, n) => (n === 8 ? plugin : row(`s${n}`))))),
    12 * 6 + 12);                                         // under "N more" too: nothing moves as it opens
  assert.equal(tagRoom(section([row("c", { tag: null })])), 0);
  assert.equal(tagRoom(section([row("c", { tag: null })], { groups: [{ id: "hooks", title: "Hooks", count: 1,
    rows: [row("h", { tag: "Global" })] }] })), 6 * 6 + 12);       // a group's rows in the section's one column
  const folder = "/work/lumen-api";
  assert.ok(touches([`${folder}/.claude/settings.json`], folder, folder));
  assert.ok(touches([`${folder}/docs/CLAUDE.md`], folder, folder));
  assert.ok(touches([`${folder}/.mcp.json`], folder, folder));
  assert.ok(touches([`${folder}/opencode.json`], folder, folder));                // OpenCode's project config
  assert.ok(touches([folder], folder, folder));                       // too many changes to name: everything
  assert.ok(!touches([`${folder}/src/lumen/routes/books.py`, `${folder}/.git/index`], folder, folder));
  assert.ok(touches(["/home/dev/.claude/projects/-work-lumen-api/a1.jsonl"], "/home/dev/.claude", folder));
  assert.ok(!touches([], "/home/dev/.claude", folder));
});

test("a tone's small words and a problem's chip read 4.5:1 in every theme; the faint tones stay the theme's", () => {
  const dir = new URL("../themes/", import.meta.url);
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".json"))) {
    const theme = JSON.parse(readFileSync(new URL(name, dir), "utf8"));
    const t = { ...theme.colors, ...Object.fromEntries(theme.ansi.map((/** @type {string} */ hex,
      /** @type {number} */ n) => [`ansi${n}`, hex])) };
    for (const tone of ["bad", "warn", "allow", "ask", "deny", "busy"]) {
      assert.ok(contrast(toneInk(t, tone), t.surface) >= 4.5, `${name}: ${tone} on the card`);
    }
    for (const tone of ["bad", "warn"]) {
      const { fill, ink } = chipColors(t, tone);
      assert.ok(contrast(ink, fill) >= 4.5, `${name}: the ${tone} chip`);
      assert.notEqual(fill, t.surface);
    }
    assert.deepEqual([toneInk(t, "off"), toneInk(t, "ok"), toneInk(t, "muted")], [t.dim, t.muted, t.muted]);
  }
  assert.equal(toneInk({ ansi1: "red", foreground: "white", surface: "black" }, "bad"), "red");   // no hex: as given
});

test("the agent shown: the one kept for the space, else the focused tab's, else the one used last, else Claude", () => {
  assert.deepEqual(READ, ["claude", "codex", "opencode"]);
  assert.equal(chosenAgent({ kept: {}, space: "sp1", focused: "opencode", recent: ["claude"] }), "opencode");
  assert.equal(chosenAgent({ kept: { sp1: "codex" }, space: "sp1", focused: "claude", recent: ["claude"] }), "codex");
  assert.equal(chosenAgent({ kept: { sp2: "codex" }, space: "sp1", focused: "claude", recent: ["codex"] }), "claude");
  assert.equal(chosenAgent({ kept: {}, space: "sp1", focused: "gemini", recent: ["gemini", "codex"] }),
    "codex");                                 // one core reads no setup of shows only once picked in the list
  assert.equal(chosenAgent({ kept: "codex", space: "sp1", focused: "aider", recent: "codex" }), "claude");
  assert.equal(chosenAgent({}), "claude");
});

test("the Agents tab draws an agent graph.py draws: the space's where it is one, else the last used that is", () => {
  assert.deepEqual(GRAPHED, ["claude", "codex"]);
  assert.equal(graphAgent({ kept: { s1: "codex" }, space: "s1", recent: ["claude"] }), "codex");
  // OpenCode's setup is read for the panel, but no graph is drawn of it
  assert.equal(graphAgent({ kept: { s1: "opencode" }, space: "s1", recent: ["opencode", "codex"] }), "codex");
  assert.equal(graphAgent({ kept: {}, space: "s1", recent: ["opencode"] }), "claude");
  assert.equal(graphAgent({ kept: { s1: "gemini" }, space: "s1", recent: ["gemini", "codex"] }), "codex");
  assert.equal(graphAgent({ kept: { s1: "gemini" }, space: "s1", recent: [] }), "claude");
  assert.equal(graphAgent({ kept: null, space: "s1", recent: null }), "claude");
});

test("no part of the mod announces what is not built", () => {
  const dir = new URL("../mods/herdr-fold/", import.meta.url);
  for (const file of ["agent.js", "agentstab.js", "layers.js", "styleguide.js"]) {
    assert.doesNotMatch(readFileSync(new URL(file, dir), "utf8"), /not shown yet|So far herdr-fold/, file);
  }
});

test("a tab's agent: a chat tab's with its conversation, else one in a pane; a shell's or another agent's none", () => {
  const labels = { tab: "herdr-fold.chat-tab", session: "herdr-fold.chat" };
  const chat = { state: "live", program: { key: "claude" }, labels: { [labels.tab]: "t1", [labels.session]: "a1" } };
  const panes = [{ tab: "t2", program: { key: "shell" } }, { tab: "t2", program: { key: "codex" } },
    { tab: "t3", program: { key: "gemini" } }];
  assert.deepEqual(tabAgent("t1", panes, [chat], labels), { agent: "claude", session: "a1" });
  assert.deepEqual(tabAgent("t2", panes, [chat], labels), { agent: "codex", session: null });
  assert.equal(tabAgent("t3", panes, [chat], labels), null);
  assert.equal(tabAgent("t1", panes, [{ ...chat, state: "closed" }], labels), null);
  assert.equal(tabAgent(null, panes, [chat], labels), null);
});

/** Core's properties of a row: LINES, its ACTIONS as [id, label]. @param {string} title @param {any[]} lines
 * @param {[string, string][]} actions @param {Record<string, any>} [over] */
const props = (title, lines, actions, over = {}) => ({ title, state: null, lines, text: null, error: null,
  actions: actions.map(([id, label], n) => ({ id, label, path: id === "open" ? `/work/lumen-api/${label.slice(5)}`
    : null, server: id === "open" ? null : title, primary: !n })), ...over });

test("the dot is the worst problem's tone, red over yellow; kept per space in words, a space gone forgotten", () => {
  const health = (/** @type {[string, string][]} */ ...problems) => ({ head: { problems: problems.map(([text,
    tone]) => ({ text, tone, row: "connector:x" })) } });
  assert.equal(problemTone(health(["1 sign in", "warn"], ["1 failed", "bad"])), "bad");
  assert.equal(problemTone(health(["1 sign in", "warn"])), "warn");
  assert.equal(problemTone(health()), null);
  assert.equal(problemTone(null), null);              // an agent not on this machine
  const live = new Set(["s1", "s2"]);
  const kept = keepProblems({ s9: { tone: "bad", said: "1 failed" } }, "s1", health(["1 failed", "bad"],
    ["1 sign in", "warn"]), live);
  assert.deepEqual(kept, { s1: { tone: "bad", said: "1 failed, 1 sign in" } });
  assert.equal(keepProblems(kept, "s1", health(["1 failed", "bad"], ["1 sign in", "warn"]), live), kept);   // no write
  assert.deepEqual(keepProblems(kept, "s2", health(["1 sign in", "warn"]), live),
    { ...kept, s2: { tone: "warn", said: "1 sign in" } });
  assert.deepEqual(keepProblems(kept, "s1", health(), live), {});     // solved: its dot goes
  assert.deepEqual(keepProblems("junk", "s1", null, live), {});
});

test("the chosen row is found with its section, and shows past the first five", () => {
  const skills = section(Array.from({ length: 16 }, (_, n) => row(`skill-${n}`)));
  const servers = section([row("sentry", { id: "connector:sentry" })], { id: "connectors" });
  assert.equal(chosenRow([skills, servers], "connector:sentry")?.section.id, "connectors");
  assert.equal(chosenRow([skills, servers], "skill:skill-9")?.row.name, "skill-9");
  assert.equal(chosenRow([skills, servers], "skill:gone"), null);       // a read later, the row is no more
  assert.equal(chosenRow([skills, servers], null), null);
  assert.deepEqual(names(shown(skills, { chosen: "skill:skill-9" })).slice(5), ["skill-9"]);
  assert.equal(shown(skills, { chosen: "skill:skill-9" }).more, 10);
  assert.equal(serverOf(servers.rows[0]), "sentry");
  assert.equal(serverOf(skills.rows[0]), null);
});

test("the properties draw core's lines but what their title says; a conflict's both rules; only the actions done yet",
  () => {
    const sentry = row("sentry", { id: "connector:sentry", state: { text: "failed", tone: "bad" },
      properties: props("sentry", [["From", ".mcp.json", "Project"], ["Runs", "npx -y @sentry/mcp-server", null]],
        [["retry", "Retry"], ["open", "Open .mcp.json"]], { state: { text: "failed", tone: "bad" },
          error: "spawn npx ENOENT" }) });
    assert.deepEqual(propertyLines(sentry), [["From", ".mcp.json", "Project"],      // as center-chat.html draws them
      ["Runs", "npx -y @sentry/mcp-server", null]]);
    assert.deepEqual(doable(sentry).map((one) => [one.id, one.label, one.server, one.path]),
      [["retry", "Retry", "sentry", null], ["open", "Open .mcp.json", null, "/work/lumen-api/.mcp.json"]]);
    // a subagent's model is its state, a project's rule is from the file it is named after: said once
    const reviewer = row("code-reviewer", { properties: props("code-reviewer", [["From", "pr-review", "Plugin"],
      ["Model", "sonnet", null], ["Tools", "Read, Grep", null]], [], { state: { text: "sonnet", tone: "ok" } }) });
    assert.deepEqual(propertyLines(reviewer).map(([label]) => label), ["From", "Tools"]);
    const rule = row("CLAUDE.md", { properties: props("CLAUDE.md", [["From", "CLAUDE.md", "Project"]],
      [["open", "Open CLAUDE.md"]]) });
    assert.deepEqual(propertyLines(rule), []);
    const hidden = { ...conflict("Bash(git push:*)"), properties: props("Bash(git push:*)",
      [["Deny", "Bash(git push:*)", "Project"], ["Allow", "Bash(git push:*)", "Global"]], []) };
    assert.equal(propertyLines(hidden).length, 2);
    // every action core offers is done here; Claude's own commands never on another agent's row
    // (Turn off and on are the connector's form, its switch: never a button beside it)
    const box = row("Box", { properties: props("claude.ai Box", [], [["connect", "Connect"],
      ["turn-off", "Turn off in lumen-api"]]) });
    assert.deepEqual(WORKS, ["open", "retry", "connect", "sign-out", "graph", "usage"]);
    assert.deepEqual(doable(box).map((one) => one.id), ["connect"]);
    assert.deepEqual(doable(box, "codex").map((one) => one.id), ["connect"]);
    // Show graph, the last on a row the graph draws: Codex's rows too, after the row's own (never the raised one)
    const drawn = row("github", { properties: props("github", [], [["retry", "Retry"],
      ["graph", "Show in graph"]]) });
    assert.deepEqual(doable(drawn, "codex").map((one) => one.id), ["graph"]);
    assert.deepEqual(doable(drawn).map((one, n) => actionLook(one, n)), ["raised", "plain"]);
    const on = row("Linear", { properties: props("Linear", [], [["turn-off", "Turn off in lumen-api"],
      ["sign-out", "Sign out"], ["retry", "Retry"], ["turn-on", "Turn on in lumen-api"], ["remove", "Remove"]]) });
    assert.deepEqual(doable(on).map((one) => one.id), ["sign-out", "retry"]);
    assert.deepEqual(doable(on, "codex").map((one) => one.id), ["sign-out"]);
    assert.deepEqual(doable(row("old")), []);           // a row with no properties (an older core's)
    assert.deepEqual(propertyLines(row("old")), []);
  });

test("an ask to show a row is answered once, by its space's panel, while it is new", () => {
  const ask = { space: "s1", section: null, row: "connector:sentry", at: 1000 };
  assert.equal(asked(ask, "s1", null, 1200), ask);
  assert.equal(asked(ask, "s1", 1000, 1200), null);           // answered already
  assert.equal(asked(ask, "s2", null, 1200), null);           // another space's
  assert.equal(asked(ask, "s1", null, 1000 + ASK_MS + 1), null);      // a panel first shown long after
  assert.equal(asked(null, "s1", null, 1200), null);
  assert.equal(asked({ space: "s1" }, "s1", null, 1200), null);
});

test("the properties' words, a pressed chip's and the chosen row's state read 4.5:1 in every theme", () => {
  const dir = new URL("../themes/", import.meta.url);
  const themes = readdirSync(dir).filter((name) => name.endsWith(".json"));
  assert.equal(themes.length, 13);
  for (const name of themes) {
    const theme = JSON.parse(readFileSync(new URL(name, dir), "utf8"));
    const t = { ...theme.colors, ...Object.fromEntries(theme.ansi.map((/** @type {string} */ hex,
      /** @type {number} */ n) => [`ansi${n}`, hex])) };
    for (const tone of ["bad", "warn", "allow", "ask", "deny", "busy"]) {
      assert.ok(contrast(toneInk(t, tone, t.chrome), t.chrome) >= 4.5, `${name}: ${tone} on the side's level`);
      assert.ok(contrast(toneInk(t, tone, chosenFill(t)), chosenFill(t)) >= 4.5, `${name}: ${tone} on the chosen row`);
    }
    for (const tone of ["bad", "warn"]) {
      const over = chipColors(t, tone, CHIP_LIFT);
      assert.ok(contrast(over.ink, over.fill) >= 4.5, `${name}: the ${tone} chip under the pointer`);
      assert.notEqual(over.fill, chipColors(t, tone).fill);
    }
    const error = errorColors(t, t.chrome);
    assert.ok(contrast(error.ink, error.fill) >= 4.5, `${name}: the error`);
    assert.ok(contrast(t.foreground, chosenFill(t)) >= 4.5, `${name}: the chosen row's name`);
  }
});

// the agents as core tells them (agent_state.py agents): Claude on Max, Codex on Plus, Gemini CLI telling nothing
const MACHINE = [
  { key: "claude", name: "Claude", installed: true, signed_in: true, plan: "Max", login: ["claude", "auth", "login"],
    install: "npm install -g @anthropic-ai/claude-code", page: "https://lumen.example/claude", empty: null,
    listed: { group: "Agents on this Mac", dim: false, word: "Max", tone: null } },
  { key: "codex", name: "Codex", installed: true, signed_in: false, plan: null, login: ["codex", "login"],
    install: "npm install -g @openai/codex", page: "https://lumen.example/codex",
    empty: { kind: "sign-in", title: "Codex is not signed in" },
    listed: { group: "Agents on this Mac", dim: false, word: "sign in", tone: "warn" } },
  { key: "gemini", name: "Gemini CLI", installed: false, signed_in: null, plan: null, login: ["gemini"],
    install: "npm install -g @google/gemini-cli", page: "https://lumen.example/gemini",
    empty: { kind: "install", title: "Gemini CLI is not installed" },
    listed: { group: "Not installed", dim: true, word: null, tone: null } }];
const APP = { claude: { key: "claude", icon: "icons/claude.svg", tint: false },
  codex: { key: "codex", icon: "icons/codex.svg", tint: true } };

test("the agents' list in core's words: the installed first, then the others dim under their head, one checked", () => {
  const here = { group: "Agents on this Mac", dim: false }, mark = { icon: null, tint: false };
  assert.deepEqual(agentList([MACHINE[2], ...MACHINE.slice(0, 2)], APP, "claude"), [
    { key: "claude", name: "Claude", icon: "icons/claude.svg", tint: false, ...here, word: "Max", warn: false,
      check: true },
    { key: "codex", name: "Codex", icon: "icons/codex.svg", tint: true, ...here, word: "sign in", warn: true,
      check: false },
    { key: "gemini", name: "Gemini CLI", ...mark, group: "Not installed", dim: true, word: null, warn: false,
      check: false }]);
  // one not installed looked at: the check is its own; nothing told yet, or a record core did not word: no rows
  assert.deepEqual(agentList(MACHINE, {}, "gemini").map((a) => [a.key, a.icon, a.check]),
    [["claude", null, false], ["codex", null, false], ["gemini", null, true]]);
  assert.deepEqual([agentList(null, APP, "claude"), agentList("nonsense", APP, "claude"),
    agentList([{ key: "claude", name: "Claude" }], APP, "claude")], [[], [], []]);
});

test("the agents' list never shows an e-mail: a word of letters alone beside a name", () => {
  const word = (/** @type {unknown} */ said) => ({ ...MACHINE[0], listed: { ...MACHINE[0].listed, word: said } });
  assert.deepEqual(agentList([word("dev@lumen.example"), word(7)], APP, "claude").map((a) => a.word), [null, null]);
});

test("an agent's record by its key, null while none is told", () => {
  assert.equal(agentOf(MACHINE, "codex")?.name, "Codex");
  assert.deepEqual([agentOf(MACHINE, "amp"), agentOf(null, "claude")], [null, null]);
});

test("Sign in is the agent's own login in a terminal tab of the space's folder, its words one argv", () => {
  assert.deepEqual(signInTab(MACHINE[1], { space: "s1", folder: "/work/lumen-api" }),
    { name: "Sign in to Codex", space: "s1", folder: "/work/lumen-api", argv: ["codex", "login"] });
  assert.deepEqual(signInTab(MACHINE[0], {}), { name: "Sign in to Claude", argv: ["claude", "auth", "login"] });
  // a login that is not words (core's answer broken): nothing run
  for (const login of [[], "claude auth login", ["claude", 7], null, ["claude", ""]]) {
    assert.equal(signInTab({ ...MACHINE[0], login }, { space: "s1" }), null);
  }
});

test("a space keeps the agent picked for it; the spaces gone are left out", () => {
  const live = new Set(["s1", "s2"]);
  assert.deepEqual(keepAgent({ s1: "claude", s9: "codex" }, "s2", "codex", live), { s1: "claude", s2: "codex" });
  assert.deepEqual(keepAgent("nonsense", "s1", "gemini", live), { s1: "gemini" });
});

test("the panel shows the agent kept for its space, one core does not read too; never a stray value", () => {
  assert.equal(chosenAgent({ kept: { s1: "gemini" }, space: "s1", focused: "claude" }), "gemini");
  for (const stray of [7, "", "--help", "a b", "x".repeat(65), null]) {
    assert.equal(chosenAgent({ kept: { s1: stray }, space: "s1", focused: "codex" }), "codex");
  }
});

test("an ask may name an agent only to look at, as a dim one picked in the list", () => {
  const ask = { space: "s1", section: null, row: null, look: "gemini", at: 1000 };
  assert.equal(asked(ask, "s1", null, 1500)?.look, "gemini");
  assert.equal(asked(ask, "s2", null, 1500), null);                 // another space's
  assert.equal(asked(ask, "s1", 1000, 1500), null);                 // answered already
});

/** A window as core words it (usage.py's section()): USED percent at LEVEL, RESETS at a time. @param {string} label
 * @param {number | null} used @param {string | null} level @param {number | null} [at] */
const window = (label, used, level, at = null) => ({ label, used, text: used === null ? "–" : `${used}%`, level,
  resets: at && { at, words: label === "5h" ? "5h resets {time}" : "Week resets {day} {time}" } });
/** A Usage row as core words it (usage.py's section()), OVER changing it. @param {string} key
 * @param {Record<string, any>} [over] */
const meter = (key, over = {}) => ({ key, name: key, plan: null, current: false, five: window("5h", 8, "ok", 100),
  week: window("wk", 3, "ok", 200), tight: window("5h", 8, "ok", 100), reset: null, age: "Read 3 min ago", ...over });
const FIRST_METER = meter("claude", { name: "Claude", plan: "Max", current: true,
  five: window("5h", 72, "warn", 100), tight: window("5h", 72, "warn", 100),
  reset: { at: 100, words: "5h resets {time}" } });
// core's report's month for Codex on an API key (report.py's month_of()): TODAY of BUDGET, on PACE
/** @param {number} today @param {number} pace @param {number | null} [budget] */
const monthOf = (today, pace, budget = 50) => {
  const over = Boolean(budget) && Math.max(pace, today) > /** @type {number} */ (budget);
  return { agent: "codex", name: "Codex", label: "November", budget, today, pace, over,
    level: budget ? (today >= budget ? "bad" : over ? "warn" : "ok") : null,
    words: { spent: `~$${today.toFixed(2)}`, of: budget ? `of $${budget}` : "", pace: `on pace for ~$${pace}` },
    pace_line: over ? { text: `on pace for ~$${pace} by November 30`, narrow: `on pace for ~$${pace} by Nov 30` }
      : null };
};
const AGENTS = [{ key: "claude", name: "Claude", plan: "Max" }, { key: "codex", name: "Codex", plan: "API key" }];
const SECTION = { id: "usage", title: "Usage", none: "Not known yet", rows: [FIRST_METER] };

test("Usage has a row an agent: core's on a plan, then one on an API key from its month, the one in use first", () => {
  const rows = usageRows(SECTION, { months: [monthOf(18.4, 46)] }, AGENTS, "claude");
  assert.deepEqual(rows.map((r) => [r.key, r.name, r.plan, r.current]), [["claude", "Claude", "Max", true],
    ["codex", "Codex", "API key", false]]);
  assert.deepEqual([rows[0].month, rows[1].five, rows[1].week, rows[1].tight, rows[1].reset], [null, null, null, null,
    null]);
  assert.deepEqual(rows[1].month, { figure: "~$18.40", of: "of $50", level: "ok", used: 18.4 / 50 * 100, pace: null,
    budget: 50 });
  const using = usageRows({ ...SECTION, rows: [{ ...FIRST_METER, current: false }] }, { months: [monthOf(18.4, 46)] },
    AGENTS, "codex");
  assert.deepEqual(using.map((r) => [r.key, r.current]), [["codex", true], ["claude", false]]);
  // a plan's agent never twice; nothing read yet: none; an agent not told: its month's own name
  assert.deepEqual(usageRows({ ...SECTION, rows: [FIRST_METER, meter("codex")] }, { months: [monthOf(1, 2)] },
    AGENTS, "claude").map((r) => r.key), ["claude", "codex"]);
  assert.deepEqual(usageRows(null, null, AGENTS, "claude"), []);
  assert.equal(usageRows(null, { months: [monthOf(1, 2)] }, [], null)[0].name, "Codex");
});

test("an agent with no reading says so in its row's place, the why in its properties; its month stands instead", () => {
  const untold = { text: "limits not told", why: "Codex tells its limits in a chat's token counts." };
  const silent = meter("codex", { current: true, plan: "Plus", five: null, week: null, tight: null, age: null,
    untold });
  const [row] = usageRows({ ...SECTION, rows: [silent, { ...FIRST_METER, current: false }] }, null, AGENTS, "codex");
  assert.deepEqual([row.key, row.untold, usageFigure(row)], ["codex", untold, null]);
  const shown = usageRow(row, () => "");
  assert.deepEqual([shown.properties.lines, shown.properties.text], [[["Plan", "Plus", null]], untold.why]);
  assert.equal(usageRow(usageRows(SECTION, null, AGENTS, "claude")[0], () => "5h resets 14:46").properties.text, null);
  const keyed = usageRows({ ...SECTION, rows: [silent] }, { months: [monthOf(18.4, 46)] }, AGENTS, "codex");
  assert.deepEqual(keyed.map((r) => [r.key, r.untold ?? null, r.month?.figure]), [["codex", null, "~$18.40"]]);
});

test("a line under a row only while there is trouble: a yellow or red window's reset, a pace past the budget", () => {
  const rows = usageRows({ ...SECTION, rows: [FIRST_METER, meter("gemini")] }, { months: [monthOf(45.1, 58)] },
    AGENTS, "claude");
  assert.deepEqual(rows.map(usageLine), [true, false, true]);
  assert.equal(rows[2].month?.pace?.text, "on pace for ~$58 by November 30");
  assert.deepEqual([USAGE_LINE, ROW_H], [20, 26]);
  assert.equal(usageHeight(rows), 26 + 20 + 26 + 26 + 20);
  assert.equal(usageHeight([]), ROW_H);                                // "Not known yet"
});

test("a row's figure: a plan's two windows, an API key's month of its budget in its level", () => {
  const [plan, key] = usageRows(SECTION, { months: [monthOf(45.1, 58)] }, AGENTS, "claude");
  assert.deepEqual(usageFigure(plan), { label: "5h", figure: "72%", level: "warn", after: "" });
  assert.deepEqual(usageFigure(key), { label: "", figure: "~$45.10", level: "warn", after: "of $50" });
  assert.equal(usageFigure({ ...plan, tight: null }), null);                  // neither window known
  const spent = usageRows(null, { months: [monthOf(51, 60)] }, AGENTS, "codex")[0];
  assert.equal(usageFigure(spent)?.level, "bad");                              // red once spent
});

test("a row pressed shows its properties: the plan, both resets, the reading's age, or the budget; Open Usage", () => {
  const said = (/** @type {{ words: string }} */ resets) => resetWords(resets, "14:46", "Mon");
  const [plan, key] = usageRows({ ...SECTION, rows: [{ ...FIRST_METER, week: window("wk", 16, "ok", 200) }] },
    { months: [monthOf(18.4, 46)] }, AGENTS, "claude");
  const claude = usageRow(plan, said);
  assert.equal(claude.id, "usage:claude");
  assert.deepEqual(claude.properties.lines, [["Plan", "Max", null], ["5h", "resets 14:46", null],
    ["Week", "resets Mon 14:46", null], ["Read", "3 min ago", null]]);
  assert.deepEqual(doable(claude).map((one) => [one.id, one.label]), [["usage", "Open Usage"]]);
  assert.deepEqual(usageRow(key, said).properties.lines, [["Plan", "API key", null], ["Budget", "$50", null]]);
  const none = usageRows(null, { months: [monthOf(18.4, 46, null)] }, AGENTS, "codex")[0];
  assert.deepEqual(usageRow(none, said).properties.lines.at(-1), ["Budget", "none", null]);
});

test("Usage's head folded shows the agent in use's figure, another's that is yellow or red and stands worse", () => {
  const plan = (/** @type {string} */ key, /** @type {number} */ used, /** @type {string} */ level,
    current = false) => meter(key, { current, tight: window("5h", used, level) });
  const shown = (/** @type {any[]} */ rows, /** @type {string} */ current) => headline(rows.map((one) => ({ month: null,
    ...one, current: one.key === current })))?.key ?? null;
  assert.equal(shown([plan("claude", 40, "ok"), plan("codex", 8, "ok")], "codex"), "codex");
  assert.equal(shown([plan("claude", 72, "warn"), plan("codex", 8, "ok")], "codex"), "claude");
  assert.equal(shown([plan("claude", 72, "warn"), plan("codex", 60, "warn")], "codex"), "claude");
  assert.equal(shown([plan("claude", 60, "warn"), plan("codex", 60, "warn")], "codex"), "codex");   // a tie: in use
  assert.equal(shown([plan("claude", 91, "bad"), plan("codex", 60, "warn")], "codex"), "claude");
  const over = usageRows(null, { months: [monthOf(45.1, 58)] }, AGENTS, null)[0];
  const fine = usageRows(null, { months: [monthOf(18.4, 46)] }, AGENTS, null)[0];
  assert.equal(shown([plan("claude", 72, "warn"), over], "claude"), "codex");                    // 90% of it
  assert.equal(shown([plan("claude", 72, "warn"), fine], "claude"), "claude");
  assert.equal(shown([], "claude"), null);                                                       // nothing known
  assert.equal(shown([{ ...fine, month: null }], "claude"), null);     // the one in use unknown, the other not yellow
});

test("a reset's words name this Mac's time, and its day where core asks for it", () => {
  assert.equal(resetWords({ at: 0, words: "5h resets {time}" }, "2:46 PM", "Mon"), "5h resets 2:46 PM");
  assert.equal(resetWords({ at: 0, words: "Week resets {day} {time}" }, "17:00", "Mon"), "Week resets Mon 17:00");
  assert.equal(resetWords(null, "17:00", "Mon"), "");
});

test("a percent wears its level's color, read 4.5:1 on the card and the lit row, its bar 3:1 on the track", () => {
  const dir = new URL("../themes/", import.meta.url);
  for (const name of readdirSync(dir).filter((n) => n.endsWith(".json"))) {
    const theme = JSON.parse(readFileSync(new URL(name, dir), "utf8"));
    const t = { ...theme.colors, ...Object.fromEntries(theme.ansi.map((/** @type {string} */ hex,
      /** @type {number} */ n) => [`ansi${n}`, hex])) };
    assert.deepEqual(["ok", "warn", "bad"].map((level) => levelColor(t, level)), [t.ansi2, t.ansi3, t.ansi1]);
    for (const level of ["ok", "warn", "bad"]) {
      assert.ok(contrast(levelInk(t, level, t.surface), t.surface) >= 4.5, `${name}: ${level} on the card`);
      assert.ok(contrast(levelInk(t, level, t.raised), t.raised) >= 4.5, `${name}: ${level} on the lit row`);
      assert.ok(contrast(levelFill(t, level), t.canvas) >= 3, `${name}: the ${level} bar on its track`);
    }
  }
  assert.equal(levelInk({ ansi1: "red", foreground: "white", surface: "black" }, "bad", "black"), "red");
  assert.equal(levelColor({ muted: "#888888" }, "unknown"), "#888888");
  const mocha = JSON.parse(readFileSync(new URL("herdr-fold.json", dir), "utf8"));
  assert.equal(levelFill({ ...mocha.colors, ansi3: mocha.ansi[3] }, "warn"), mocha.ansi[3]);   // where seen: as it is
});

test("the agents told to core for Usage: each key, name and plan's word alone, never an e-mail", () => {
  assert.deepEqual(usageAgents([{ key: "claude", name: "Claude", plan: "Max", login: ["claude"], page: "x" },
    { key: "codex", name: "Codex", plan: "ada@lumen.example" }, { name: "stray" }]),
  [{ key: "claude", name: "Claude", plan: "Max" }, { key: "codex", name: "Codex", plan: null }]);
  assert.deepEqual(usageAgents(null), []);
});

// what core says of a sign-in and the add form (agent_layers.py's connecting()), as connectors.html's frames
const CONNECT = { state: { text: "signing in", tone: "busy" }, words: "Finish in your browser",
  actions: [{ id: "reopen", label: "Open the page again" }, { id: "cancel", label: "Cancel" }],
  needs: { "turn-off": "Start a chat in lumen-api to turn it off",
    "turn-on": "Start a chat in lumen-api to turn it on" } };
/** A sign-in's terminal as the app lists it. @param {string} address @param {string} name @param {number} at
 * @param {Record<string, any>} [over] */
const signIn = (address, name, at, over = {}) => ({ address, state: "live", labels: { [MCP_LOGIN]: name,
  [MCP_AGENT]: "claude", [MCP_AT]: String(at) }, ...over });

test("Connect runs the agent's own login in a terminal with no pane, labelled with its server, agent and start", () => {
  assert.deepEqual(loginRun(["claude", "mcp", "login", "claude.ai Box"], { agent: "claude", name: "claude.ai Box",
    folder: "/work/lumen-api", at: 1700000000000 }), ["run", "--bg", "--json", "--rm", "--cwd", "/work/lumen-api",
    "--label", "herdr-fold.mcp-login=claude.ai Box", "--label", "herdr-fold.mcp-agent=claude", "--label",
    "herdr-fold.mcp-at=1700000000000", "--", "claude", "mcp", "login", "claude.ai Box"]);
});

test("a row is signing in while its agent's login runs: one per server, another agent's or an ended one's not", () => {
  const list = [signIn("t7", "claude.ai Box", 5000), signIn("t8", "linear", 6000, { labels: { [MCP_LOGIN]: "linear",
    [MCP_AGENT]: "codex", [MCP_AT]: "6000" } }), signIn("t9", "sentry", 7000, { state: "exited" }),
  { address: "t1", state: "live", labels: { "herdr-fold.chat": "s1" } }, { address: "t2", state: "live" }];
  assert.deepEqual(signIns(list, "claude"), { "claude.ai Box": { address: "t7", at: 5000 } });
  assert.deepEqual(signIns(list, "codex"), { linear: { address: "t8", at: 6000 } });
  assert.deepEqual(signIns([], "claude"), {});
});

test("a sign-in left waiting past ten minutes, or one with no start told, is ended by the next look", () => {
  assert.equal(SIGNING_MS, 600000);
  const now = 1700000000000;
  const list = [signIn("t7", "Box", now - SIGNING_MS - 1), signIn("t8", "linear", now - 1000),
    signIn("t9", "sentry", Number.NaN), signIn("t10", "notion", now - SIGNING_MS - 1, { state: "exited" })];
  assert.deepEqual(overdue(list, now), ["t7", "t9"]);
});

test("a row signing in says so with the spinner, no mark; its properties what to do: finish in the browser, or cancel",
  () => {
  const box = row("Box", { id: "connector:claude.ai Box", dim: true, mark: "warn", state: { text: "sign in",
    tone: "warn" },
    properties: props("Box", [["From", "claude.ai", "Account"]], [["connect", "Connect"]],
      { state: { text: "sign in", tone: "warn" } }) });
  const made = signingRow(box, CONNECT);
  assert.deepEqual([made.state, made.dim, made.mark, made.name, made.tag], [CONNECT.state, false, null, "Box",
    box.tag]);
  assert.deepEqual(made.properties, { title: "Box", state: CONNECT.state, lines: [], text: null, error: null,
    words: "Finish in your browser", actions: [
      { id: "reopen", label: "Open the page again", path: null, server: "claude.ai Box", primary: true },
      { id: "cancel", label: "Cancel", path: null, server: "claude.ai Box", primary: false }] });
  assert.deepEqual(doable(made).map((one) => one.id), ["reopen", "cancel"]);
  assert.equal(box.state.text, "sign in");              // core's row as it was
});

test("the address a sign-in waits on is read off its screen, a long one's wrapped rows put together", () => {
  const address = "https://mcp.box.com/authorize?response_type=code&client_id=lumen&redirect_uri=http%3A%2F%2F"
    + "localhost%3A56693%2Fcallback&state=J1MQ";
  const screen = `Starting authentication for "claude.ai Box"…\nIf the browser didn't open, visit:\n  `
    + `${address.slice(0, 78)}\n${address.slice(78)}\n\nWaiting for authorization… (^C to cancel)\n`;
  assert.equal(printedAddress(screen), address);
  assert.equal(printedAddress(`visit:\n  ${address}\nWaiting for authorization…\n`), address);
  assert.equal(printedAddress('Starting authentication for "claude.ai Box"…\n'), null);
  assert.equal(printedAddress("See https://lumen.example/help for more\n"), null);     // a line's only word alone
  assert.equal(printedAddress(""), null);
});

test("Turn off is typed to the folder's Claude: a chat of the space or one in a pane there, an idle one first", () => {
  const space = { id: "w1", folder: "/work/lumen-api", tabs: [{ id: "w1:t1" }, { id: "w1:t2" }] };
  const chat = (/** @type {string} */ address, /** @type {string} */ tab, /** @type {string} */ status,
    key = "claude") => ({ address, state: "live", status, program: { key }, labels: { "herdr-fold.chat-tab": tab } });
  const paneAgent = (/** @type {string} */ address, /** @type {string} */ pane, /** @type {string} */ status,
    key = "claude") => ({ address, pane, space: "w1", status, program: { key } });
  const panes = [{ pane: "p1", cwd: "/work/lumen-api" }, { pane: "p2", cwd: "/work/harbor-web" }];
  const find = (/** @type {any[]} */ agents, /** @type {any[]} */ terminals) => claudeIn(space, agents, panes,
    terminals, "herdr-fold.chat-tab");
  assert.equal(find([], [chat("t3", "w1:t1", "working"), chat("t4", "w1:t2", "idle")]), "t4");
  assert.equal(find([], [chat("t3", "w1:t1", "working")]), "t3");
  assert.equal(find([paneAgent("t5", "p1", "idle")], [chat("t3", "w1:t1", "working")]), "t5");
  assert.equal(find([paneAgent("t6", "p2", "idle")], []), null);                // Claude in another folder
  assert.equal(find([paneAgent("t5", "p1", "idle", "codex")], [chat("t3", "w1:t1", "idle", "codex")]), null);
  assert.equal(find([], [chat("t3", "w2:t1", "idle")]), null);                  // another space's chat
  assert.equal(find([], [{ ...chat("t3", "w1:t1", "idle"), state: "exited" }]), null);
  assert.equal(claudeIn(null, [], panes, [], "herdr-fold.chat-tab"), null);
});

test("Connect is the one solid button; else the first is raised and the rest plain, as connectors.html's", () => {
  const acts = (/** @type {string[]} */ ...ids) => ids.map((id, n) => actionLook({ id }, n));
  assert.deepEqual(acts("connect", "sign-out"), ["solid", "plain"]);
  assert.deepEqual(acts("sign-out", "open"), ["raised", "plain"]);
  assert.deepEqual(acts("reopen", "cancel"), ["raised", "plain"]);
  assert.deepEqual(acts("retry", "open"), ["raised", "plain"]);
});

test("a connector with no known brand wears its letter on a tile, the same color for the same name", () => {
  assert.deepEqual(tile("github"), { letter: "G", color: tile("github").color });
  assert.equal(tile("claude.ai harbor").letter, "C");
  assert.equal(tile("").letter, "?");
  assert.ok(/^ansi[1-6]$/.test(tile("github").color));
  assert.notEqual(tile("github").color, tile("chrome-devtools").color);
});

/** A server as agent_setup.py's setup tells it. @param {string} name @param {string} state @param {any} [over] */
const server = (name, state, over = {}) => ({ name, label: name.replace(/^claude\.ai /, ""), state, brand: null,
  ...over });
const SERVERS = [server("sentry", "failed", { brand: "sentry" }), server("claude.ai Box", "sign in", { brand: "box" }),
  server("claude.ai Google Drive", "on", { brand: "google-drive" }), server("claude.ai Linear", "on",
    { brand: "linear" }), server("claude.ai Notion", "off here", { brand: "notion" }), server("tidepool-db",
    "not checked"), server("lumen-docs", "not approved"), server("harbor", "pending")];

test("the + menu's connectors: the ones on or off here a switch each, the failed and sign-in ones its pills", () => {
  assert.deepEqual(plusMenu(SERVERS), {
    pills: [{ text: "1 failed", tone: "bad" }, { text: "1 sign in", tone: "warn" }],
    rows: [{ name: "claude.ai Google Drive", label: "Google Drive", brand: "google-drive", on: true },
      { name: "claude.ai Linear", label: "Linear", brand: "linear", on: true },
      { name: "claude.ai Notion", label: "Notion", brand: "notion", on: false },
      { name: "tidepool-db", label: "tidepool-db", brand: null, on: true },      // never seen in a session: not off
      { name: "harbor", label: "harbor", brand: null, on: true }] });           // still connecting
  assert.deepEqual(plusMenu([server("a", "failed"), server("b", "failed")]).pills, [{ text: "2 failed", tone: "bad" }]);
  assert.deepEqual(plusMenu(null), { pills: [], rows: [] });
  assert.deepEqual(plusMenu([3, { name: 4 }, server("ok", "on")]).rows.map((r) => r.name), ["ok"]);
});

test("a switch just turned shows as asked until Claude's setup says so, or its time is up", () => {
  const rows = plusMenu(SERVERS).rows, asked = { "claude.ai Notion": { on: true, at: 1000 },
    "claude.ai Linear": { on: true, at: 1000 }, gone: { on: false, at: 1000 } };
  const now = switched(rows, asked, 5000, 10000);
  assert.equal(now.rows.find((r) => r.name === "claude.ai Notion")?.on, true);
  assert.deepEqual(Object.keys(now.asked), ["claude.ai Notion"]);             // Linear is on already; gone is no row
  assert.deepEqual(switched(rows, asked, 12000, 10000), { rows, asked: {} });
});

test("Claude's own look at a server is shown over the session's word while that word is the one it had", () => {
  const checked = { "claude.ai Box": { base: "sign in", state: "on", error: null },
    sentry: { base: "on", state: "failed", error: "x" }, "claude.ai Linear": { base: "on", state: "bogus" } };
  const now = checkedOver(SERVERS, checked);
  assert.equal(now.find((s) => s.name === "claude.ai Box")?.state, "on");
  assert.equal(now.find((s) => s.name === "sentry")?.state, "failed");         // a newer session's word wins
  assert.equal(now.find((s) => s.name === "claude.ai Linear")?.state, "on");
  assert.equal(SERVERS[1].state, "sign in");                                   // a copy
  assert.deepEqual(checkedOver(null, checked), []);
});

// harness.py's answers as core words them: a plan of FIELDS, OVER changing it; a field; a layer's choice
/** @param {any[]} fields @param {Record<string, any>} [over] */
const plan = (fields, over = {}) => ({ fields, saved: "Saved in", layers: [], changes: [], when: null, warns: [],
  ask: null, submit: null, cancel: "Cancel", remove: null, error: null, edits: [], done: null, undo: "Undo", say: [],
  now: null, more: null, ...over });
const HEAD = { name: "Claude", where: "in lumen-api", model: "Opus 5.5", runs: "claude-opus-5-5", effort: "High",
  starts: 34200, line: "Opus 5.5 · High · starts at 34.2k of 1M", problems: [] };
const SWITCH = { id: "on", label: "On in lumen-api", kind: "switch", value: true, short: "On here",
  turn: { on: "Turn on in lumen-api", off: "Turn off in lumen-api" } };
const SAVED = [["Global", "~/.claude/settings.json"], ["Project", ".claude/settings.json"],
  ["Local", ".claude/settings.local.json"]].map(([id, path]) => ({ id, label: id, path, chosen: id === "Local" }));

test("each row opens its own form, as core's interface lists them; a row with none opens none", () => {
  const ask = (/** @type {string} */ id, over = {}, agent = "claude", name = null) =>
    formAsk(agent, id, row(id, { id, ...over }), HEAD, name);
  assert.deepEqual(ask("mode"), { action: "mode" });
  assert.deepEqual(ask("sandbox"), { action: "sandbox" });
  assert.deepEqual(ask("sandbox", {}, "codex"), { action: "sandbox" });
  assert.deepEqual(ask("approval", {}, "codex"), { action: "approval" });
  assert.deepEqual(formAsk("claude", MODEL, null, HEAD), { action: "model", runs: "claude-opus-5-5" });
  assert.deepEqual(formAsk("codex", MODEL, null, { ...HEAD, runs: null }), { action: "model" });
  assert.deepEqual(formAsk("claude", RULE, null, HEAD), { action: "rule" });
  assert.deepEqual(formAsk("claude", HOOKS, null, HEAD), { action: "hooks" });
  assert.equal(formAsk("opencode", MODEL, null, HEAD), null);          // core changes nothing of OpenCode's
  assert.equal(ask("connector:docs", {}, "opencode"), null);
  // a rule's own text may hold colons: the id's first two parts alone are its kind and its behavior
  assert.deepEqual(ask("permission:allow:Bash(git push:*)", { tag: "Global" }), { action: "rule",
    was: { rule: "Bash(git push:*)", behavior: "allow", layer: "Global" } });
  assert.deepEqual(ask("conflict:allow:Bash(git push:*)"), { action: "conflict", behavior: "allow",
    rule: "Bash(git push:*)" });
  assert.deepEqual(ask("skill:/home/dev/.claude/skills/release-notes/SKILL.md", { name: "release-notes" }),
    { action: "skill", name: "release-notes" });
  assert.deepEqual(ask("subagent:Project:doc-checker", { name: "doc-checker" }), { action: "subagent",
    name: "doc-checker" });
  assert.equal(ask("subagent:pr-review:code-reviewer", { name: "code-reviewer" }), null);     // a plugin's
  assert.equal(ask("subagent:built-in", { names: ["Explore", "Plan"] }), null);       // till one of its names is picked
  assert.deepEqual(ask("subagent:built-in", { names: ["Explore", "Plan"] }, "claude", "Plan"), { action: "subagent",
    name: "Plan" });
  assert.equal(ask("subagent:built-in", { names: ["Explore"] }, "claude", "Other"), null);
  // a connector's form where core's row can be turned off or on, or waits to be approved
  const turns = (/** @type {string} */ id) => ({ properties: props("github", [], [[id, "Turn off in lumen-api"]]) });
  assert.deepEqual(ask("connector:github", { ...turns("turn-off"), tokens: 6800 }), { action: "connector",
    name: "github", starts: 34200, tokens: 6800 });
  assert.deepEqual(ask("connector:github", { ...turns("turn-on"), tokens: null }), { action: "connector",
    name: "github", starts: 34200 });
  assert.deepEqual(ask("connector:sentry", { state: { text: "not approved", tone: "off" } }).action, "connector");
  assert.equal(ask("connector:sentry", { state: { text: "failed", tone: "bad" } }), null);
  // a file's row, a hook's and every Codex row but its two settings: none (Codex has no switch for a folder)
  for (const id of ["rule:/home/dev/lumen-api/CLAUDE.md", "hook:/home/dev/.claude/settings.json:Stop::notify.sh",
    "usage:claude"]) assert.equal(ask(id), null);
  for (const id of ["mode", "permission:allow:git status", "skill:/home/dev/.codex/skills/a/SKILL.md", RULE, HOOKS,
    "connector:linear"]) assert.equal(formAsk("codex", id, row(id, { id, ...turns("turn-off") }), HEAD), null);
});

test("a control changes what is asked: a value set, an emptied one left out, the form's own kept", () => {
  const was = { rule: "Bash(curl:*)", behavior: "ask", layer: "Project" };
  assert.deepEqual(asking({ action: "rule", was }, { layer: "Local" }), { action: "rule", was, layer: "Local" });
  assert.deepEqual(asking({ action: "rule", was, rule: "Bash(curl -s:*)" }, { rule: "" }), { action: "rule", was });
  assert.deepEqual(asking({ action: "sandbox", add: "pypi.org" }, { on: false }), { action: "sandbox",
    add: "pypi.org", on: false });
  assert.deepEqual(asking({ action: "rule", was, remove: true }, { remove: undefined }), { action: "rule", was });
});

test("the layers are offered once a control was touched; a rule's always: its layer is one of its fields", () => {
  assert.equal(layersShown({ action: "mode" }, false), false);
  assert.equal(layersShown({ action: "mode" }, true), true);
  assert.equal(layersShown({ action: "rule" }, false), true);
  assert.deepEqual([MODEL, RULE, HOOKS, "mode", null].map(rowless), [true, true, true, false, false]);
  // a sandbox's host goes with its ×, but one an allow rule gives, or the organization
  assert.deepEqual([{ layer: "Project", rule: null }, { layer: "Global", rule: "WebFetch(domain:pypi.org)" },
    { layer: "Managed", rule: null }].map(removable), [true, false, false]);
});

test("a switch shows what core's row says till it is touched; a server to approve is asked both ways", () => {
  const off = row("Notion", { properties: props("Notion", [], [["turn-on", "Turn on in lumen-api"]]) });
  const on = row("github", { properties: props("github", [], [["turn-off", "Turn off in lumen-api"]]) });
  assert.equal(switchShown(SWITCH, on, false), true);
  assert.equal(switchShown(SWITCH, off, false), false);       // off by Claude's own state: the files do not say so
  assert.equal(switchShown(SWITCH, off, true), true);         // asked on
  assert.equal(switchShown({ ...SWITCH, value: false }, row("changelog"), false), false);
  assert.equal(switchShown(SWITCH, null, false), true);       // the Hooks group's: no row
  assert.equal(approves(row("sentry", { state: { text: "not approved", tone: "off" } })), true);
  assert.equal(approves(on), false);
  assert.equal(approves(null), false);
});

test("Claude's own command alone goes to its chat: a plan that says it and changes no file", () => {
  assert.equal(sayOnly(plan([SWITCH], { say: ["/mcp enable linear"] })), true);
  assert.equal(sayOnly(plan([SWITCH], { say: ["/model sonnet"], edits: [{ layer: "Project" }] })), false);
  assert.equal(sayOnly(plan([SWITCH])), false);
});

test("after a save the form opens anew on what was written: a rule on its new row, a removal on none", () => {
  const was = { rule: "Bash(pytest:*)", behavior: "allow", layer: "Project" }, base = { action: "rule", was };
  const fields = [{ id: "rule", kind: "text", value: "Bash(python -m pytest:*)" },
    { id: "behavior", kind: "choice", value: "allow" }];
  assert.deepEqual(afterSave(base, { ...base, layer: "Local" }, plan(fields, { layers: SAVED })), {
    chosen: "permission:allow:Bash(python -m pytest:*)",
    ask: { action: "rule", was: { rule: "Bash(python -m pytest:*)", behavior: "allow", layer: "Local" } } });
  assert.deepEqual(afterSave({ action: "rule" }, { action: "rule", rule: "WebFetch" }, plan([{ id: "rule",
    kind: "text", value: "WebFetch" }, { id: "behavior", kind: "choice", value: "ask" }], { layers: SAVED })).chosen,
  "permission:ask:WebFetch");
  assert.equal(afterSave(base, { ...base, remove: true }, plan(fields, { layers: SAVED })), null);
  assert.equal(afterSave({ action: "conflict" }, { action: "conflict", way: "remove" }, plan([])), null);
  assert.deepEqual(afterSave({ action: "mode" }, { action: "mode", value: "plan" }, plan([])), { chosen: null,
    ask: { action: "mode" } });
});

test("the foot says what was saved in core's words: a removal's line, else the change's first line", () => {
  assert.deepEqual(footWords(plan([], { done: "Removed Bash(curl:*) from Project" })),
    { text: "Removed Bash(curl:*) from Project", code: false });
  assert.deepEqual(footWords(plan([], { changes: [{ path: ".claude/settings.json", lines: [["-", '"model": "opus"'],
    ["+", '"model": "sonnet"']] }] })), { text: '− "model": "opus"', code: true });
  assert.deepEqual(footWords(plan([])), { text: "", code: true });
});

test("core's sentences end as the mockup's: a period added, a question kept; a layer's file by its whole path",
  () => {
    assert.equal(sentence("Set by your organization"), "Set by your organization.");
    assert.equal(sentence("Remove from Project?"), "Remove from Project?");
    assert.equal(sentence("Done."), "Done.");
    assert.equal(filePath("~/.claude/settings.json", "/home/dev/lumen-api", "/home/dev"),
      "/home/dev/.claude/settings.json");
    assert.equal(filePath(".claude/settings.json", "/home/dev/lumen-api", "/home/dev"),
      "/home/dev/lumen-api/.claude/settings.json");
    assert.equal(filePath("/Library/managed-settings.json", "/home/dev/lumen-api", "/home/dev"),
      "/Library/managed-settings.json");
  });

test("the head's line: its model and effort the model form's way in, the rest words; no model known, no way in",
  () => {
    assert.deepEqual(headParts(HEAD), ["Opus 5.5 · High", " · starts at 34.2k of 1M"]);
    assert.deepEqual(headParts({ ...HEAD, effort: null, line: "Opus 5.5 · starts at 34.2k" }),
      ["Opus 5.5", " · starts at 34.2k"]);
    assert.deepEqual(headParts({ ...HEAD, model: null, effort: null, line: "starts at ~9" }), ["", "starts at ~9"]);
  });
