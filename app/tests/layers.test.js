// @ts-check
// Tests for the Agent panel's own rules (layers.js): the agent shown, a section's rows and its fold, the filter, the
// tags' column, the health bar's parts, which changes are a new read; a row's properties, the dot, an ask.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { contrast } from "../mods/herdr-fold/agents.js";
import { addList, agentList, agentOf, ASK_MS, asked, barParts, bodyHeight, CHIP_LIFT, chipColors, chosenAgent,
  chosenFill, chosenRow, doable, errorColors, FIRST, FOLDED, HEAD_H, keepAgent, keepOpen, keepProblems, matches,
  MORE_H, problem, problemTone, propertyLines, READ, ROW_H, sectionOpen, serverOf, shown, signInTab, summarized,
  tabAgent, tagRoom, tagWord, toneColor, toneInk, touches, USAGE_LINE, USAGE_ROW, levelColor,
  levelFill, levelInk, resetWords, usageAgents, usageHeight, WARN_H, WORKS, actionLook, claudeIn,
  loginRun, MCP_AGENT, MCP_AT, MCP_LOGIN, overdue, printedAddress, SIGNING_MS, signingRow, signIns, tile, toneOf,
  checkedOver, plusMenu, switched, COST_BAR, COST_LINE, costHeight, costLines, graphAgent, usageRows, usageOpen,
  costGlance, tightest, headline }
  from "../mods/herdr-fold/layers.js";

/** A row as core words it, OVER changing it. @param {string} name @param {Record<string, any>} [over] */
const row = (name, over = {}) => ({ id: `skill:${name}`, icon: "skill", name, note: null, tag: { text: "Project",
  tone: "project" }, state: null, cost: "0.3k", used: false, agents: ["claude"], dim: false, warn: false, ...over });
/** A section of ROWS. @param {any[]} rows @param {Record<string, any>} [over] */
const section = (rows, over = {}) => ({ id: "skills", title: "Skills", count: rows.length, cost: "4.0k", summary: [],
  rows, ...over });
const names = (/** @type {{ rows: any[] }} */ found) => found.rows.map((r) => r.name);

test("a section shows its first five rows, then N more; its problems and used rows always; never 1 more", () => {
  const sixteen = section(Array.from({ length: 16 }, (_, n) => row(`skill-${n}`)));
  assert.equal(FIRST, 5);
  assert.deepEqual([shown(sixteen).rows.length, shown(sixteen).more], [5, 11]);
  assert.deepEqual([shown(sixteen, { more: true }).rows.length, shown(sixteen, { more: true }).more], [16, 0]);
  const marked = section(sixteen.rows.map((r, n) => (n === 9 ? { ...r, used: true } : n === 12 ? { ...r,
    state: { text: "failed", tone: "bad" } } : n === 14 ? { ...r, warn: true } : r)));
  assert.deepEqual(names(shown(marked)).slice(5), ["skill-9", "skill-12", "skill-14"]);    // in their own order
  assert.equal(shown(marked).more, 8);
  const six = section(sixteen.rows.slice(0, 6));        // one past five: its line would show the row itself
  assert.deepEqual([shown(six).rows.length, shown(six).more], [6, 0]);
  const seven = shown(section(sixteen.rows.slice(0, 7)));
  assert.deepEqual([seven.rows.length, seven.more], [5, 2]);
  assert.deepEqual(shown(section([])), { rows: [], more: 0 });
});

test("a problem is a failed or sign-in state or a conflict, never a plain state", () => {
  assert.ok(problem(row("sentry", { state: { text: "failed", tone: "bad" } })));
  assert.ok(problem(row("Box", { state: { text: "sign in", tone: "warn" } })));
  assert.ok(problem(row("Bash(git push:*)", { warn: true, tag: null })));
  assert.ok(!problem(row("github", { state: { text: "32 tools", tone: "ok" } })));
  assert.ok(!problem(row("Bash(rm -rf *)", { state: { text: "deny", tone: "deny" } })));   // a rule, not a problem
});

test("Codex's approval is a row of Permissions as core words it: read, found by its words, Open its one action", () => {
  const open = { id: "open", label: "Open config.toml", path: "/home/dev/.codex/config.toml", server: null,
    primary: true };
  const approval = row("Approval", { id: "approval", icon: "shield", note: "Ask on request", cost: null,
    agents: ["codex"], tag: { text: "Personal", tone: "personal" }, properties: { title: "Approval", state: null,
      lines: [["From", "~/.codex/config.toml", "Personal"]], text: null, error: null, actions: [open] } });
  const rules = Array.from({ length: 7 }, (_, n) => row(`git ${n}`, { id: `permission:allow:git ${n}`,
    state: { text: "allow", tone: "allow" } }));
  const found = shown(section([approval, ...rules], { id: "permissions", title: "Permissions" }));
  assert.equal(found.rows[0], approval);                                       // first: never under "N more"
  assert.deepEqual([problem(approval), toneOf(approval), serverOf(approval)], [false, "", null]);
  assert.ok(matches(approval, "ask request") && matches(approval, "approval personal"));
  assert.equal(bodyHeight([approval], 0), ROW_H);                              // one line, as a rule's
  assert.deepEqual(propertyLines(approval), [["From", "~/.codex/config.toml", "Personal"]]);
  assert.deepEqual(doable(approval, "codex").map((one) => one.id), ["open"]);  // nothing that sets it
});

test("the filter finds a row by every word typed, in its name, note, state or tag; found rows all show", () => {
  const api = row("api.md", { note: "when src/lumen/** is read", dim: true });
  assert.ok(matches(api, "API"));
  assert.ok(matches(api, "lumen project"));
  assert.ok(!matches(api, "lumen personal"));
  assert.ok(matches(row("sentry", { state: { text: "failed", tone: "bad" } }), "fail"));
  assert.ok(matches(api, "  "));
  const many = section(Array.from({ length: 16 }, (_, n) => row(n % 2 ? `route-${n}` : `store-${n}`)));
  assert.deepEqual([shown(many, { query: "route" }).rows.length, shown(many, { query: "route" }).more], [8, 0]);
  assert.deepEqual(shown(many, { query: "nothing" }), { rows: [], more: 0 });
});

test("a section's rows spring to their own height: a row 26, a conflict's two lines 40, N more 24, none one line",
  () => {
    assert.deepEqual([HEAD_H, ROW_H, WARN_H, MORE_H], [28, 26, 40, 24]);
    const conflict = row("Bash(git push:*)", { warn: true, note: "deny in Project hides allow in Personal" });
    assert.equal(bodyHeight([row("a"), conflict, row("b")], 0), 26 + 40 + 26);
    assert.equal(bodyHeight([row("a")], 14), 26 + 24);
    assert.equal(bodyHeight([], 0), 26);
  });

test("a head's summary: the permissions' behaviors always, the sub-agents' names only while folded", () => {
  const permissions = section([], { id: "permissions", summary: [{ text: "12 allow", tone: "allow" },
    { text: "2 deny", tone: "deny" }] });
  const agents = section([], { id: "agents", summary: [{ text: "code-reviewer, Explore, 3 more", tone: "ok" }] });
  assert.deepEqual([summarized(permissions, true), summarized(permissions, false)], [true, true]);
  assert.deepEqual([summarized(agents, true), summarized(agents, false)], [false, true]);
  assert.equal(summarized(section([]), false), false);
});

test("a section's fold is kept per space: all open but Agents till folded by hand, a space gone forgotten", () => {
  assert.deepEqual(FOLDED, ["agents"]);
  assert.deepEqual(["rules", "agents"].map((id) => sectionOpen(null, "sp1", id)), [true, false]);
  const kept = keepOpen({ gone: { rules: false }, sp1: { skills: false } }, "sp1", "agents", true, new Set(["sp1"]));
  assert.deepEqual(kept, { sp1: { skills: false, agents: true } });
  assert.deepEqual(["rules", "skills", "agents"].map((id) => sectionOpen(kept, "sp1", id)), [true, false, true]);
  assert.equal(sectionOpen(kept, "sp2", "skills"), true);            // another space: its own
  assert.deepEqual(keepOpen("x", "sp1", "rules", false, new Set(["sp1"])), { sp1: { rules: false } });
});

test("a long tag is cut to its column; a tone is its theme's color", () => {
  assert.equal(tagWord("Project"), "Project");
  assert.equal(tagWord("chrome-devtools-mcp"), "chrome-devt…");
  const t = { ansi1: "red", ansi2: "green", ansi3: "yellow", accent: "accent", dim: "dim", muted: "muted" };
  assert.deepEqual(["bad", "deny", "warn", "ask", "allow", "busy", "off", "ok", "else"].map((tone) =>
    toneColor(t, tone)), ["red", "red", "yellow", "yellow", "green", "accent", "dim", "muted", "muted"]);
});

test("a section's tags stand in one column as wide as its widest tag; a change touches a setup or not", () => {
  const plugin = row("d", { tag: { text: "chrome-devtools-mcp", tone: "plugin" } });
  assert.equal(tagRoom(section([row("c", { tag: null }), plugin])), 12 * 6 + 12);     // the cut tag's twelve
  assert.equal(tagRoom(section([row("a"), row("b", { tag: { text: "claude.ai", tone: "account" } })])), 9 * 6 + 12);
  assert.equal(tagRoom(section(Array.from({ length: 9 }, (_, n) => (n === 8 ? plugin : row(`s${n}`))))),
    12 * 6 + 12);                                         // under "N more" too: nothing moves as it opens
  assert.equal(tagRoom(section([row("c", { tag: null })])), 0);
  const folder = "/work/lumen-api";
  assert.ok(touches([`${folder}/.claude/settings.json`], folder, folder));
  assert.ok(touches([`${folder}/docs/CLAUDE.md`], folder, folder));
  assert.ok(touches([`${folder}/.mcp.json`], folder, folder));
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
    assert.deepEqual([toneInk(t, "off"), toneInk(t, "ok")], [t.dim, t.muted]);
  }
  assert.equal(toneInk({ ansi1: "red", foreground: "white", surface: "black" }, "bad"), "red");   // no hex: as given
});

test("the health bar's parts share what loads at start, an empty part left out", () => {
  const parts = barParts([{ part: "rules", tokens: 5400 }, { part: "skills", tokens: 0 },
    { part: "connectors", tokens: 16200 }]);
  assert.deepEqual(parts.map((p) => [p.part, p.share]), [["rules", 0.25], ["connectors", 0.75]]);
  assert.deepEqual(barParts([{ part: "rules", tokens: 0 }]), []);
});

test("the agent shown: the one kept for the space, else the focused tab's, else the one used last, else Claude", () => {
  assert.deepEqual(READ, ["claude", "codex"]);
  assert.equal(chosenAgent({ kept: { sp1: "codex" }, space: "sp1", focused: "claude", recent: ["claude"] }), "codex");
  assert.equal(chosenAgent({ kept: { sp2: "codex" }, space: "sp1", focused: "claude", recent: ["codex"] }), "claude");
  assert.equal(chosenAgent({ kept: {}, space: "sp1", focused: "gemini", recent: ["gemini", "codex"] }),
    "codex");                                 // one core reads no setup of shows only once picked in the list
  assert.equal(chosenAgent({ kept: "codex", space: "sp1", focused: "aider", recent: "codex" }), "claude");
  assert.equal(chosenAgent({}), "claude");
});

test("the Agents tab draws an agent core reads: the space's where it is one, else the one used last that is", () => {
  assert.equal(graphAgent({ kept: { s1: "codex" }, space: "s1", recent: ["claude"] }), "codex");
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
  const health = (/** @type {[string, string][]} */ ...problems) => ({ health: { problems: problems.map(([text,
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
    // a sub-agent's model is its state, a project's rule is from the file it is named after: said once
    const reviewer = row("code-reviewer", { properties: props("code-reviewer", [["From", "pr-review", "Plugin"],
      ["Model", "sonnet", null], ["Tools", "Read, Grep", null]], [], { state: { text: "sonnet", tone: "ok" } }) });
    assert.deepEqual(propertyLines(reviewer).map(([label]) => label), ["From", "Tools"]);
    const rule = row("CLAUDE.md", { properties: props("CLAUDE.md", [["From", "CLAUDE.md", "Project"]],
      [["open", "Open CLAUDE.md"]]) });
    assert.deepEqual(propertyLines(rule), []);
    const conflict = row("Bash(git push:*)", { warn: true, tag: null, properties: props("Bash(git push:*)",
      [["Deny", "Bash(git push:*)", "Project"], ["Allow", "Bash(git push:*)", "Personal"]], []) });
    assert.equal(propertyLines(conflict).length, 2);
    // every action core offers is done here; Claude's own commands never on another agent's row
    const box = row("Box", { properties: props("claude.ai Box", [], [["connect", "Connect"],
      ["turn-off", "Turn off in lumen-api"]]) });
    assert.deepEqual(WORKS, ["open", "retry", "connect", "turn-off", "turn-on", "sign-out", "graph"]);
    assert.deepEqual(doable(box).map((one) => one.id), ["connect", "turn-off"]);
    assert.deepEqual(doable(box, "codex").map((one) => one.id), ["connect"]);
    // Show graph, the last on a row the graph draws: Codex's rows too, after the row's own (never the raised one)
    const drawn = row("github", { properties: props("github", [], [["turn-off", "Turn off in lumen-api"],
      ["graph", "Show graph"]]) });
    assert.deepEqual(doable(drawn, "codex").map((one) => one.id), ["graph"]);
    assert.deepEqual(doable(drawn).map((one, n) => actionLook(one, n)), ["raised", "plain"]);
    const on = row("Linear", { properties: props("Linear", [], [["turn-off", "Turn off in lumen-api"],
      ["sign-out", "Sign out"], ["retry", "Retry"], ["turn-on", "Turn on in lumen-api"], ["remove", "Remove"]]) });
    assert.deepEqual(doable(on).map((one) => one.id), ["turn-off", "sign-out", "retry", "turn-on"]);
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
    install: "npm install -g @anthropic-ai/claude-code", page: "https://lumen.example/claude", empty: null },
  { key: "codex", name: "Codex", installed: true, signed_in: false, plan: null, login: ["codex", "login"],
    install: "npm install -g @openai/codex", page: "https://lumen.example/codex",
    empty: { kind: "sign-in", title: "Codex is not signed in" } },
  { key: "gemini", name: "Gemini CLI", installed: false, signed_in: null, plan: null, login: ["gemini"],
    install: "npm install -g @google/gemini-cli", page: "https://lumen.example/gemini",
    empty: { kind: "install", title: "Gemini CLI is not installed" } }];
const APP = { claude: { key: "claude", icon: "icons/claude.svg", tint: false },
  codex: { key: "codex", icon: "icons/codex.svg", tint: true } };

test("the agents' list: installed ones only, a check on the one in use, the plan's word, sign in where told", () => {
  assert.deepEqual(agentList(MACHINE, APP, "claude"), [
    { key: "claude", name: "Claude", icon: "icons/claude.svg", tint: false, plan: "Max", check: true, signIn: false },
    { key: "codex", name: "Codex", icon: "icons/codex.svg", tint: true, plan: null, check: false, signIn: true }]);
  // an agent the app draws no icon for: none; nothing told yet: no rows
  const here = MACHINE.map((a) => ({ ...a, installed: true, signed_in: null }));
  assert.deepEqual(agentList(here, {}, "gemini").map((a) => [a.key, a.icon, a.check, a.signIn]),
    [["claude", null, false, false], ["codex", null, false, false], ["gemini", null, true, false]]);
  assert.deepEqual([agentList(null, APP, "claude"), agentList("nonsense", APP, "claude")], [[], []]);
});

test("the agents' list never shows an e-mail: a plan's word alone, as core gives it", () => {
  const leaky = [{ ...MACHINE[0], plan: "dev@lumen.example" }, { ...MACHINE[1], installed: true, plan: 7 }];
  assert.deepEqual(agentList(leaky, APP, "claude").map((a) => a.plan), [null, null]);
});

test("Add an agent lists the ones not installed, in core's order", () => {
  assert.deepEqual(addList(MACHINE, APP), [{ key: "gemini", name: "Gemini CLI", icon: null, tint: false }]);
  assert.deepEqual(addList(null, APP), []);
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

test("an ask may name the agent to show and open the agents' list", () => {
  const ask = { space: "s1", section: null, row: null, agent: "codex", list: true, at: 1000 };
  assert.equal(asked(ask, "s1", null, 1500)?.list, true);
  assert.equal(asked(ask, "s1", null, 1500)?.agent, "codex");
});

/** A Usage row as core words it (usage.py's section()), OVER changing it. @param {string} key
 * @param {Record<string, any>} [over] */
const meter = (key, over = {}) => ({ key, name: key, plan: null, current: false, five: { label: "5h", used: 8,
  text: "8%", level: "ok" }, week: { label: "wk", used: 3, text: "3%", level: "ok" },
  tight: { label: "5h", used: 8, text: "8%", level: "ok" }, bar: { used: 8, level: "ok" },
  resets: { at: 1794581160, words: "5 hour resets at {time}" }, age: null, said: "5 hour 8%, week 3%", ...over });
const FIRST_METER = meter("claude", { current: true, five: { label: "5h", used: 72, text: "72%", level: "warn" },
  tight: { label: "5h", used: 72, text: "72%", level: "warn" }, bar: { used: 72, level: "warn" } });
const OPEN = { claude: true, codex: false };     // core's: the agent in use open, the others folded

test("Usage has a row for every agent, none waiting under +N more", () => {
  const five = [FIRST_METER, ...["codex", "gemini", "amp", "aider"].map((key) => meter(key))];
  assert.deepEqual(usageRows(five, [], {}).map((r) => r.key), ["claude", "codex", "gemini", "amp", "aider"]);
  assert.deepEqual(usageRows(null, [], {}), []);                          // not read yet
});

test("an agent's block is open as turned here till core tells it, else as core keeps it, else the one in use's", () => {
  assert.deepEqual(["claude", "codex"].map((key) => usageOpen(key, OPEN, {}, "claude")), [true, false]);
  assert.deepEqual(["claude", "codex"].map((key) => usageOpen(key, OPEN, { codex: true }, "claude")), [true, true]);
  assert.deepEqual(["claude", "gemini"].map((key) => usageOpen(key, null, {}, "gemini")), [false, true]);
});

test("Usage springs to its rows' height: a row 28, an open one its line of words 16 and its cost lines", () => {
  assert.deepEqual([USAGE_ROW, USAGE_LINE], [28, 16]);
  const open = (/** @type {string} */ key) => key === "claude";
  assert.equal(usageHeight([FIRST_METER, meter("codex")], open), 28 + 16 + 28);
  assert.equal(usageHeight([FIRST_METER, meter("codex")], () => true), 28 + 16 + 28 + 16);
  assert.equal(usageHeight([FIRST_METER, meter("codex")], () => false), 28 + 28);              // each one row
  assert.equal(usageHeight([meter("codex", { resets: null, age: "as of 43 min ago" })], () => true), 28 + 16);
  assert.equal(usageHeight([{ ...FIRST_METER, resets: null }], open), 28);                    // a reset not told
  assert.equal(usageHeight([], open), ROW_H);                                                  // "Not known yet"
});

test("a reset's words name this Mac's time, and its day where core asks for it", () => {
  assert.equal(resetWords({ at: 0, words: "5 hour resets at {time}" }, "2:46 PM", "Mon"), "5 hour resets at 2:46 PM");
  assert.equal(resetWords({ at: 0, words: "Week resets {day} at {time}" }, "17:00", "Mon"),
    "Week resets Mon at 17:00");
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

// what core says of a sign-in and the add form (agent_setup.py's connecting()), as connectors.html's frames
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

test("a row signing in says so in the accent, and its properties what to do: finish in the browser, or cancel", () => {
  const box = row("Box", { id: "connector:claude.ai Box", dim: true, state: { text: "sign in", tone: "warn" },
    properties: props("Box", [["From", "claude.ai", "Account"]], [["connect", "Connect"]],
      { state: { text: "sign in", tone: "warn" } }) });
  const made = signingRow(box, CONNECT);
  assert.deepEqual([made.state, made.dim, made.name, made.tag], [CONNECT.state, false, "Box", box.tag]);
  assert.deepEqual(made.properties, { title: "Box", state: CONNECT.state, lines: [], text: null, error: null,
    words: "Finish in your browser", actions: [
      { id: "reopen", label: "Open the page again", path: null, server: "claude.ai Box", primary: true },
      { id: "cancel", label: "Cancel", path: null, server: "claude.ai Box", primary: false }] });
  assert.deepEqual(doable(made).map((one) => one.id), ["reopen", "cancel"]);
  assert.equal(box.state.text, "sign in");              // core's row as it was
  assert.equal(toneOf(made), "busy");
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
  assert.deepEqual(acts("connect", "turn-off"), ["solid", "plain"]);
  assert.deepEqual(acts("turn-off", "sign-out"), ["raised", "plain"]);
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

// usage.html's Áttekintés as core's 7-day report tells it: Claude on a plan, Codex on an API key with a budget
/** Codex's month as core words it (report.py's month_of()): TODAY of BUDGET on its way to PACE.
 * @param {number} today @param {number} pace @param {number | null} budget */
const monthOf = (today, pace, budget = 50) => {
  const over = Boolean(budget) && Math.max(pace, today) > /** @type {number} */ (budget);
  return { agent: "codex", label: "November", budget, today, pace, over, level: budget ? (over ? "warn" : "ok") : null,
    words: { spent: `~$${today.toFixed(2)}`, of: budget ? `of $${budget}` : "",
      pace: `on pace for ~$${Math.round(pace)}` } };
};
const CODEX_MONTH = monthOf(18.4, 46);
const WEEK = { period: { id: "7d" }, summary: [
  { key: "Claude · Max plan", agent: "claude", value: 130.9, text: "~$130.90", unit: "API value" },
  { key: "Codex · API key", agent: "codex", value: 8.6, text: "~$8.60", unit: "spent" },
  { key: "Tokens", value: 1, text: "1" }], months: [CODEX_MONTH] };

test("under an agent on a plan Usage says this week's API value, never spent", () => {
  assert.deepEqual(costLines(WEEK).claude, [{ kind: "figure", label: "This week", figure: "~$130.90",
    unit: "API value", over: false }]);
  assert.equal(JSON.stringify(costLines(WEEK).claude).includes("spent"), false);
});

test("under an agent on an API key: the month's spending, its budget's bar, and the pace, in core's words", () => {
  assert.deepEqual(costLines(WEEK).codex, [
    { kind: "figure", label: "November", figure: "~$18.40", unit: "", over: false },
    { kind: "bar", share: 18.4 / 50, over: false },
    { kind: "words", text: "of $50 · ", pace: "on pace for ~$46", over: false }]);
});

test("over its budget, or on pace to be, the figure, bar and pace are marked; the bar never past its end", () => {
  const over = costLines({ ...WEEK, months: [monthOf(45.1, 58)] }).codex;
  assert.deepEqual(over, [{ kind: "figure", label: "November", figure: "~$45.10", unit: "", over: true },
    { kind: "bar", share: 45.1 / 50, over: true },
    { kind: "words", text: "of $50 · ", pace: "on pace for ~$58", over: true }]);
  const past = costLines({ ...WEEK, months: [monthOf(61, 70)] }).codex;
  assert.equal(past[1].share, 1);
});

test("with no budget the month has no bar; an agent with nothing used has no line; no report, none", () => {
  assert.deepEqual(costLines({ ...WEEK, months: [monthOf(18.4, 46, null)] }).codex, [
    { kind: "figure", label: "November", figure: "~$18.40", unit: "", over: false },
    { kind: "words", text: "", pace: "on pace for ~$46", over: false }]);
  assert.deepEqual(costLines({ ...WEEK, summary: [WEEK.summary[2]], months: [] }), {});
  assert.deepEqual(costLines(null), {});
  // a model with no price: its tokens are no dollars, so no figure is made up
  assert.deepEqual(costLines({ ...WEEK, months: [], summary: [{ key: "Codex", agent: "codex", value: null,
    text: "no price", unit: "API value" }] }), {});
  // spent this week but nothing yet this month (its first day): the week's, as spent
  assert.deepEqual(costLines({ ...WEEK, months: [] }).codex, [{ kind: "figure", label: "This week",
    figure: "~$8.60", unit: "spent", over: false }]);
});

test("an agent with costs and no limits (an API key) has a row of its own: after the meters, first in use", () => {
  const lines = costLines(WEEK), agents = [{ key: "codex", name: "Codex", plan: "API key" }];
  const rows = usageRows([FIRST_METER], agents, lines, "claude");
  assert.deepEqual(rows.map((r) => r.key), ["claude", "codex"]);
  assert.deepEqual([rows[1].name, rows[1].plan, rows[1].five, rows[1].week, rows[1].bar, rows[1].current],
    ["Codex", "API key", null, null, null, false]);
  const using = usageRows([{ ...FIRST_METER, current: false }], agents, lines, "codex");
  assert.deepEqual(using.map((r) => [r.key, r.current]), [["codex", true], ["claude", false]]);
  assert.deepEqual(usageRows([FIRST_METER, meter("codex")], agents, lines).map((r) => r.key), ["claude", "codex"]);
  assert.deepEqual(usageRows(null, agents, {}), []);
  assert.equal(usageRows([], [], lines)[1].name, "Codex");                  // not told: its own name
});

test("Usage is as high as its rows with an open one's cost lines", () => {
  const lines = costLines(WEEK);
  assert.deepEqual([COST_LINE, COST_BAR], [20, 8]);
  assert.deepEqual([costHeight(lines.claude), costHeight(lines.codex), costHeight(undefined)], [20, 20 + 8 + 16, 0]);
  const rows = usageRows([FIRST_METER], [], lines, "claude");
  assert.equal(usageHeight(rows, () => true, lines), 28 + 16 + 20 + 28 + 20 + 8 + 16);
  assert.equal(usageHeight(rows, (key) => key === "claude", lines), 28 + 16 + 20 + 28);
  assert.equal(usageHeight(rows, () => true), 28 + 16 + 28);
});

test("a folded agent's figure: an API key's month of its budget in its level, a plan's week's value plainly", () => {
  assert.deepEqual(costGlance(WEEK), { claude: { figure: "~$130.90", after: "API value", level: null, used: null },
    codex: { figure: "~$18.40", after: "of $50", level: "ok", used: 18.4 / 50 * 100 } });
  assert.deepEqual(costGlance({ ...WEEK, months: [monthOf(45.1, 58)] }).codex.level, "warn");    // yellow once over
  assert.deepEqual(costGlance({ ...WEEK, months: [monthOf(18.4, 46, null)] }).codex,
    { figure: "~$18.40", after: "", level: null, used: null });                                // no budget: alone
  assert.deepEqual(costGlance(null), {});
});

test("an agent's tightest figure: a plan's tighter window, else its cost's; none with neither", () => {
  const glances = costGlance(WEEK);
  assert.deepEqual(tightest(FIRST_METER, glances.claude), { label: "5h", figure: "72%", level: "warn", after: "" });
  assert.deepEqual(tightest({ ...meter("codex"), five: null, week: null, tight: null }, glances.codex),
    { label: "", figure: "~$18.40", level: "ok", after: "of $50" });
  assert.equal(tightest({ ...meter("codex"), tight: null }, undefined), null);
});

test("Usage's head folded shows the agent in use's figure, another's that is yellow or red and stands worse", () => {
  const glances = costGlance(WEEK);
  const plan = (/** @type {string} */ key, /** @type {number} */ used, /** @type {string} */ level) => meter(key, {
    tight: { label: "5h", used, text: `${used}%`, level } });
  const shown = (/** @type {any[]} */ rows, /** @type {string} */ current, /** @type {any} */ costs = {}) =>
    headline(rows, costs, current)?.key ?? null;
  assert.equal(shown([plan("claude", 40, "ok"), plan("codex", 8, "ok")], "codex"), "codex");
  assert.equal(shown([plan("claude", 72, "warn"), plan("codex", 8, "ok")], "codex"), "claude");
  assert.equal(shown([plan("claude", 72, "warn"), plan("codex", 60, "warn")], "codex"), "claude");
  assert.equal(shown([plan("claude", 60, "warn"), plan("codex", 60, "warn")], "codex"), "codex");   // a tie: in use
  assert.equal(shown([plan("claude", 91, "bad"), plan("codex", 60, "warn")], "codex"), "claude");
  const key = { ...meter("codex"), five: null, week: null, tight: null };
  const over = costGlance({ ...WEEK, months: [monthOf(45.1, 58)] });
  assert.equal(shown([plan("claude", 72, "warn"), key], "claude", over), "codex");                 // 90% of it
  assert.equal(shown([plan("claude", 72, "warn"), key], "claude", glances), "claude");
  assert.equal(shown([], "claude"), null);                                                       // nothing known
  assert.equal(shown([key], "claude"), null);                    // the one in use unknown, the other not yellow
});
