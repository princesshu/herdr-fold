// @ts-check
// Tests for the Agents tab's graph (graph.js): its tab and its ask, the Uses column's fold, where the nodes stand,
// an edge's path and its gate's place, a node dragged and its place kept, the keys' steps, what the inspector lists.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { contrast } from "../mods/herdr-fold/agents.js";
import { AGENT, AGENTS_TAB, agentsAsked, agentsTab, APART, askAgents, boxes, dragTo, dropLayout, EDGE, edgePath,
  extent, FIRST, folded, gateAt, gatesRoom, GROUP, INDENT, IN_ROOM, keepLayout, layout, layoutKey, nodeFor, nodeLines,
  placed, portOf, sizeOf, stepNode, tagInk, UNDER, USES_ROOM, wireColor, badgeAt, DISC, faded, FAINT, legendOf,
  measured, nodeShown, propertiesOf, running, seen, shareWidth, shownInAgent, unzoomed, VIEWS, wireLook }
  from "../mods/herdr-fold/graph.js";

/** A node as core words it. @param {string} id @param {string} column @param {string} kind @param {string} title
 * @param {Record<string, any>} [over] */
const node = (id, column, kind, title, over = {}) => ({ id, column, kind, title, icon: "file", brand: null, tag: null,
  sub: "always · 2.4k", state: null, dim: false, chips: [], parent: kind === "sub" ? AGENT : null,
  properties: { title, state: null, lines: [], text: null, error: null, actions: [] }, run: null, ...over });
/** @param {string} from @param {string} to @param {string} [style] @param {any[]} [gates] */
const edge = (from, to, style = "always", gates = []) => ({ from, to, style, gates, run: null });

// agent-graph.html's lumen-api
const LUMEN = { agent: "claude", name: "Claude", folder: "/home/dev/lumen-api", nodes: [
  node("rule:/home/dev/.claude/CLAUDE.md", "in", "rule", "CLAUDE.md"),
  node("rule:/home/dev/lumen-api/CLAUDE.md", "in", "rule", "CLAUDE.md"),
  node("rule:/home/dev/lumen-api/.claude/rules/api.md", "in", "rule", "api.md"),
  node("skill:/home/dev/lumen-api/.claude/skills/routes/SKILL.md", "in", "skill", "api-routes"),
  node("skills:more", "in", "skills", "15 more skills", { properties: { title: "15 more skills", state: null,
    lines: [["commit", "Personal", null], ["release-notes", "pr-review", null]], text: null, error: null,
    actions: [] } }),
  node(AGENT, "agents", "agent", "Claude", { chips: ["PermissionRequest → herdr-fold"] }),
  node("agent:pr-review:code-reviewer", "agents", "sub", "code-reviewer"),
  node("tool:files", "uses", "tool", "Read · Edit · Write"), node("tool:Bash", "uses", "tool", "Bash"),
  node("connector:github", "uses", "connector", "github"), node("connector:figma", "uses", "connector", "figma"),
  node("connector:sentry", "uses", "connector", "sentry")],
edges: [edge("rule:/home/dev/.claude/CLAUDE.md", AGENT), edge(AGENT, "agent:pr-review:code-reviewer", "demand"),
  edge(AGENT, "tool:files", "always", [{ text: "ask", tone: "ask" }, { text: "hook", tone: "hook" }]),
  edge(AGENT, "tool:Bash"), edge(AGENT, "connector:github"), edge(AGENT, "connector:figma", "waiting"),
  edge(AGENT, "connector:sentry", "failed"), edge("agent:pr-review:code-reviewer", "connector:github")] };
const SIZE = { width: 1280, height: 700 };
/** @param {{ nodes: any[] }} graph @param {string} id */
const byIdOf = (graph, id) => graph.nodes.find((one) => one.id === id);
const ids = (/** @type {{ nodes: any[] }} */ graph) => graph.nodes.map((one) => one.id);

test("the Agents tab is the space's tab so named whose pane is the mod's; an ask reaches its space's tab once", () => {
  const space = { id: "s1", tabs: [{ id: "t1", name: "lumen-api" }, { id: "t2", name: AGENTS_TAB },
    { id: "t3", name: AGENTS_TAB }] };
  assert.equal(AGENTS_TAB, "Agents");
  // a terminal somebody named Agents is not it
  assert.equal(agentsTab(space, [{ tab: "t2", terminal: "a1" }, { tab: "t3", mod: "herdr-fold" }])?.id, "t3");
  assert.equal(agentsTab(space, [{ tab: "t2", terminal: "a1" }]), null);
  assert.equal(agentsTab(null, []), null);
  const kept = askAgents({ gone: { at: 1 }, s2: { node: "x", at: 5 } }, "s1", { node: "skill:a", session: "abc" },
    new Set(["s1", "s2"]), 1000);
  assert.deepEqual(kept, { s2: { node: "x", at: 5 }, s1: { node: "skill:a", session: "abc", at: 1000 } });
  assert.deepEqual(agentsAsked(kept, "s1", null, 1500), { node: "skill:a", session: "abc", at: 1000 });
  assert.equal(agentsAsked(kept, "s1", 1000, 1500), null);                 // answered already
  assert.equal(agentsAsked(kept, "s3", null, 1500), null);
  assert.equal(agentsAsked("junk", "s1", null, 1500), null);
  assert.equal(agentsAsked({ s1: { at: "now" } }, "s1", null, 1500), null);
});

test("the tools a conversation alone called fold into one node on a long Uses column; one alone stays itself", () => {
  assert.equal(folded(LUMEN), LUMEN);                                     // nothing to fold
  const one = { ...LUMEN, nodes: [...LUMEN.nodes, node("tool:Grep", "uses", "tool", "Grep")],
    edges: [...LUMEN.edges, edge(AGENT, "tool:Grep", "always", [{ text: "allow", tone: "allow" }])] };
  assert.equal(folded(one), one);
  const tool = (/** @type {string} */ name) => node(`tool:${name}`, "uses", "tool", name, { sub: "built-in" });
  const long = { ...LUMEN, nodes: [...LUMEN.nodes.slice(0, 9), tool("Grep"), tool("WebFetch"), tool("Glob"),
    ...LUMEN.nodes.slice(9)],
  edges: [...LUMEN.edges, edge(AGENT, "tool:Grep", "always", [{ text: "allow", tone: "allow" }]),
    edge(AGENT, "tool:WebFetch", "always", [{ text: "ask", tone: "ask" }, { text: "hook", tone: "hook" }]),
    edge(AGENT, "tool:Glob"), edge("agent:pr-review:code-reviewer", "tool:Grep"),
    edge("agent:pr-review:code-reviewer", "tool:Glob")] };
  const made = folded(long);
  // where the first of them stood: after the files' tools and Bash, before the connectors
  assert.deepEqual(ids(made).slice(7), ["tool:files", "tool:Bash", "tools:more", "connector:github",
    "connector:figma", "connector:sentry"]);
  const more = made.nodes.find((n) => n.id === "tools:more");
  assert.deepEqual([more.kind, more.column, more.title, more.sub, more.icon], ["tools", "uses", "3 more tools",
    "built-in", "wrench"]);
  assert.deepEqual(more.properties.lines, [["Grep", "allow", null], ["WebFetch", "ask, hook", null],
    ["Glob", "", null]]);
  // one edge from each node that reached any of them, no gate (each tool has its own, in the node's properties)
  assert.deepEqual(made.edges.filter((e) => e.to === "tools:more").map((e) => [e.from, e.style, e.gates]),
    [[AGENT, "always", []], ["agent:pr-review:code-reviewer", "always", []]]);
  assert.ok(!made.edges.some((e) => e.to === "tool:Grep"));
  assert.equal(made.edges.length, LUMEN.edges.length + 2);
  assert.equal(long.nodes.length, 15);                                    // core's answer as it was
});

test("three columns: In from the left, the agent in the middle with its sub-agents under it, Uses at the right",
  () => {
    const at = layout(LUMEN.nodes, SIZE), box = boxes(LUMEN.nodes, at);
    const [personal, project, api, skill, more] = LUMEN.nodes.slice(0, 5).map((n) => at[n.id]);
    assert.deepEqual(personal, { x: EDGE, y: FIRST });
    assert.equal(project.y - personal.y, sizeOf(LUMEN.nodes[0]).h + APART);
    assert.equal(skill.y - api.y, sizeOf(LUMEN.nodes[2]).h + GROUP);        // the skills a group of their own
    assert.equal(more.y - skill.y, sizeOf(LUMEN.nodes[3]).h + APART);
    assert.ok([project, api, skill, more].every((one) => one.x === EDGE));
    // the agent on the canvas's middle, its sub-agent under it and a step in
    const agent = box[AGENT], sub = box["agent:pr-review:code-reviewer"];
    assert.equal(agent.x + agent.w / 2, SIZE.width / 2);
    assert.deepEqual([sub.x - agent.x, sub.y - (agent.y + agent.h)], [INDENT, UNDER]);
    assert.equal(agent.h, sizeOf(LUMEN.nodes[0]).h + 24);                   // its chips' row
    // the agents' block centred on the tallest column beside it
    const tall = box["skills:more"].y + box["skills:more"].h - FIRST;
    assert.equal(agent.y, FIRST + (tall - (sub.y + sub.h - agent.y)) / 2);
    // Uses: their left edges in one line, the widest reaching the right edge; the connectors a group of their own
    const uses = LUMEN.nodes.slice(7).map((n) => box[n.id]);
    assert.ok(uses.every((one) => one.x === SIZE.width - EDGE - 190));
    assert.equal(uses[2].y - uses[1].y, uses[1].h + GROUP);
    assert.equal(uses[1].y - uses[0].y, uses[0].h + APART);
  });

test("a node is as large as it was measured; a narrow canvas keeps the columns apart and grows", () => {
  const sizes = { "tool:files": { w: 240, h: 54 }, [AGENT]: { w: 300, h: 80 } };
  assert.deepEqual(sizeOf(LUMEN.nodes[7], sizes), { w: 240, h: 54 });
  assert.deepEqual([sizeOf(LUMEN.nodes[6]).w, sizeOf(LUMEN.nodes[5]).w, sizeOf(LUMEN.nodes[0]).w], [230, 250, 190]);
  const at = layout(LUMEN.nodes, SIZE, sizes), box = boxes(LUMEN.nodes, at, sizes);
  assert.equal(box["tool:Bash"].x, SIZE.width - EDGE - 240);               // the column as wide as its widest
  const narrow = layout(LUMEN.nodes, { width: 500, height: 300 }), small = boxes(LUMEN.nodes, narrow);
  assert.equal(small[AGENT].x, EDGE + 190 + IN_ROOM);
  assert.equal(small["tool:files"].x, small[AGENT].x + 250 + USES_ROOM);
  const room = extent(small, { width: 500, height: 300 });
  assert.equal(room.width, small["tool:files"].x + 190 + EDGE);
  assert.equal(room.height, small["skills:more"].y + small["skills:more"].h + EDGE);
  assert.deepEqual(extent(box, SIZE), SIZE);                                // never smaller than its frame
  // a column taller than the frame: the agent in the frame's middle, seen before any scrolling
  const many = [...LUMEN.nodes, ...Array.from({ length: 20 }, (_, n) => node(`rule:${n}`, "in", "rule", "r.md"))];
  const tall = boxes(many, layout(many, SIZE)), block = tall["agent:pr-review:code-reviewer"].y
    + tall["agent:pr-review:code-reviewer"].h - tall[AGENT].y;
  assert.equal(tall[AGENT].y, FIRST + (SIZE.height - FIRST - EDGE - block) / 2);
});

test("the columns stand as far apart as the widest gate needs; with nothing going in, the agent from the edge", () => {
  assert.equal(gatesRoom([]), IN_ROOM);                                   // no gate: the edges' room alone
  assert.equal(gatesRoom([{ gates: [{ text: "auto" }] }, { gates: [] }]), IN_ROOM);
  assert.equal(gatesRoom(LUMEN.edges), IN_ROOM);                          // ask, hook: two short pills
  const wide = gatesRoom([{ gates: [{ text: "ask · pytest allowed" }, { text: "deny git push" }] }]);
  assert.ok(wide > 240 && wide <= USES_ROOM, String(wide));
  assert.equal(gatesRoom([{ gates: [{ text: "x".repeat(80) }] }]), USES_ROOM);      // never wider
  const narrow = { width: 500, height: 300 };
  const close = boxes(LUMEN.nodes, layout(LUMEN.nodes, narrow, {}, IN_ROOM));
  assert.equal(close["tool:files"].x, close[AGENT].x + 250 + IN_ROOM);
  const alone = LUMEN.nodes.filter((one) => one.column !== "in");
  assert.equal(layout(alone, narrow)[AGENT].x, EDGE);
});

test("an edge leaves a node's right for the next one's left; a sub-agent's drops from its agent's foot", () => {
  const a = { x: 100, y: 100, w: 200, h: 50 }, b = { x: 600, y: 300, w: 190, h: 54 };
  assert.deepEqual(edgePath(a, b, 2), [[300, 125], [420, 125], [480, 327], [600, 327]]);
  // the agent's edges leave a little apart, as agent-graph.html's
  assert.deepEqual(edgePath(a, b, 0)[0], [300, 117]);
  assert.deepEqual(edgePath(a, b, 4)[0], [300, 133]);
  assert.deepEqual(edgePath(a, b, 7)[0], [300, 125]);
  // close together: the handles half the way
  assert.deepEqual(edgePath(a, { ...b, x: 400 }, 2), [[300, 125], [350, 125], [350, 327], [400, 327]]);
  // under it: straight down, 24 in from the lower one's left
  const under = { x: 116, y: 200, w: 180, h: 54 };
  assert.deepEqual(edgePath(a, under, 2), [[140, 150], [140, 150], [140, 200], [140, 200]]);
  // dragged left of it: from its left to the other's right
  const left = { x: -300, y: 300, w: 190, h: 54 };
  assert.deepEqual(edgePath(a, left, 2), [[100, 125], [-5, 125], [-5, 327], [-110, 327]]);
});

test("a node's edges leave it in their targets' order, round its middle; many share its five places", () => {
  assert.deepEqual([portOf(1, 0)], [2]);                                  // one alone from the middle
  assert.deepEqual([0, 1].map((n) => portOf(2, n)), [1, 2]);
  assert.deepEqual([0, 1, 2].map((n) => portOf(3, n)), [1, 2, 3]);
  assert.deepEqual([0, 1, 2, 3, 4].map((n) => portOf(5, n)), [0, 1, 2, 3, 4]);
  assert.deepEqual([0, 4, 8, 12].map((n) => portOf(13, n)), [0, 1, 3, 4]);     // the top ones from the top
});

test("a gate stands 55% along its edge", () => {
  assert.deepEqual(gateAt([[0, 0], [0, 0], [100, 0], [100, 0]]), { x: 55, y: 0 });
  const curve = edgePath({ x: 100, y: 100, w: 200, h: 50 }, { x: 600, y: 300, w: 190, h: 54 }, 2), at = gateAt(curve);
  assert.ok(at.x > 450 && at.x < 480 && at.y > 226 && at.y < 250, JSON.stringify(at));
});

test("a node dragged follows the pointer from where it was pressed, kept once it moved", () => {
  const drag = { id: "tool:Bash", from: { x: 500, y: 300 }, at: { x: 986, y: 146 } };
  assert.equal(dragTo(drag, { x: 502, y: 301 }), null);                    // a press that shook: still a click
  assert.deepEqual(dragTo(drag, { x: 460, y: 380 }), { x: 946, y: 226 });
  assert.deepEqual(dragTo(drag, { x: -900, y: -500 }), { x: 0, y: 0 });      // never off the canvas's corner
});

test("what the app measures is told in the px a place is set in, at any zoom", () => {
  // as the demo app told a node set 250 wide, 54 high at 100% (a float's zoom, as settings() gives it): at 80% its
  // rows are drawn on whole px, and it is 55 of the px a place is set in
  assert.deepEqual(measured({ width: 200, height: 44 }, 0.800000011920929), { w: 250, h: 55 });
  assert.deepEqual(measured({ width: 225, height: 48.5 }, 0.8999999761581421), { w: 250, h: 54 });
  assert.deepEqual(measured({ width: 250, height: 54 }, 1), { w: 250, h: 54 });
  assert.deepEqual(measured({ width: 312.5, height: 67.5 }, 1.25), { w: 250, h: 54 });
  assert.deepEqual(measured({ width: 250, height: 54 }), { w: 250, h: 54 });
  assert.equal(unzoomed(920, 0.8), 1150);
  assert.equal(unzoomed(781, 1), 781);
  for (const none of [0, -1, NaN, Infinity]) assert.equal(unzoomed(781, none), 781);      // no zoom told: as 1
});

test("zoomed, the nodes are laid out as at 100%: the same boxes from what is measured there", () => {
  const set = Object.fromEntries(LUMEN.nodes.map((one) => [one.id, sizeOf(one)]));
  const plain = boxes(LUMEN.nodes, layout(LUMEN.nodes, SIZE, set), set);
  for (const zoom of [0.8, 1, 1.25]) {
    const sizes = Object.fromEntries(Object.entries(set).map(([id, { w, h }]) => [id,
      measured({ width: w * zoom, height: h * zoom }, zoom)]));
    const size = { width: unzoomed(SIZE.width * zoom, zoom), height: unzoomed(SIZE.height * zoom, zoom) };
    const all = boxes(LUMEN.nodes, layout(LUMEN.nodes, size, sizes), sizes);
    assert.deepEqual(all, plain, `at ${zoom}`);
    const list = Object.values(all);                                       // and none on another
    assert.ok(list.every((a, i) => list.every((b, j) => i === j || a.x + a.w <= b.x || b.x + b.w <= a.x
      || a.y + a.h <= b.y || b.y + b.h <= a.y)), `at ${zoom}`);
  }
});

test("a node dragged in a zoomed app goes as far on the screen as the pointer did", () => {
  const drag = { id: "tool:Bash", from: { x: 500, y: 300 }, at: { x: 986, y: 146 } };
  assert.deepEqual(dragTo(drag, { x: 460, y: 380 }, 0.8), { x: 936, y: 246 });      // 40 and 80 on the screen
  assert.deepEqual(dragTo(drag, { x: 460, y: 380 }, 1.25), { x: 954, y: 210 });
  assert.deepEqual(dragTo(drag, { x: 460, y: 380 }, 1), dragTo(drag, { x: 460, y: 380 }));
  assert.equal(dragTo(drag, { x: 503, y: 300 }, 0.5), null);               // the shake is the screen's, not the zoom's
});

test("a dragged node's place is kept per space, folder and agent; the others stay laid out; a gone one dropped", () => {
  const key = layoutKey("s1", "/home/dev/lumen-api", "claude");
  assert.equal(key, "s1|/home/dev/lumen-api|claude");
  const live = new Set(["s1", "s2"]);
  const kept = keepLayout({ "gone|/x|claude": { a: { x: 1, y: 2 } }, "s2|/y|codex": { b: { x: 3, y: 4 } } }, key,
    { "tool:Bash": { x: 700.4, y: 420.6 } }, live);
  assert.deepEqual(kept, { "s2|/y|codex": { b: { x: 3, y: 4 } }, [key]: { "tool:Bash": { x: 700, y: 421 } } });
  const again = keepLayout(kept, key, { "connector:github": { x: 10, y: 20 } }, live);
  assert.deepEqual(Object.keys(again[key]), ["tool:Bash", "connector:github"]);
  const fresh = layout(LUMEN.nodes, SIZE), at = placed({ ...again, [key]: { ...again[key],
    "tool:Gone": { x: 5, y: 5 }, junk: "x" } }, key, LUMEN.nodes, SIZE);
  assert.deepEqual(at["tool:Bash"], { x: 700, y: 421 });
  assert.deepEqual(at["connector:github"], { x: 10, y: 20 });
  assert.deepEqual(at["tool:files"], fresh["tool:files"]);                 // a node nobody moved: where layout has it
  assert.ok(!("tool:Gone" in at) && !("junk" in at));
  assert.deepEqual(placed("junk", key, LUMEN.nodes, SIZE), fresh);
  // a double click on the canvas: this graph's places dropped, the others' kept
  assert.deepEqual(dropLayout(again, key), { "s2|/y|codex": { b: { x: 3, y: 4 } } });
  assert.deepEqual(dropLayout(null, key), {});
});

test("the arrows step to the nearest node that way; with none chosen, to the agent", () => {
  const box = boxes(LUMEN.nodes, layout(LUMEN.nodes, SIZE));
  assert.equal(stepNode(box, null, "down"), AGENT);
  assert.equal(stepNode(box, AGENT, "down"), "agent:pr-review:code-reviewer");
  assert.equal(stepNode(box, "agent:pr-review:code-reviewer", "up"), AGENT);
  assert.equal(stepNode(box, "skills:more", "up"), "skill:/home/dev/lumen-api/.claude/skills/routes/SKILL.md");
  assert.equal(stepNode(box, "tool:files", "down"), "tool:Bash");
  assert.equal(stepNode(box, "tool:files", "up"), "tool:files");            // none that way: it stays
  assert.equal(stepNode(box, "tool:Bash", "left"), AGENT);
  assert.equal(stepNode(box, "rule:/home/dev/.claude/CLAUDE.md", "right"), AGENT);
  assert.equal(stepNode(box, AGENT, "right"), "tool:Bash");                 // the nearest in height
  assert.equal(stepNode(box, "gone", "left"), AGENT);
});

test("the inspector lists a node's lines but what its title says; a folded node's names as a list", () => {
  const sub = node("agent:pr-review:code-reviewer", "agents", "sub", "code-reviewer", { properties: {
    title: "code-reviewer", state: { text: "opus", tone: "ok" }, lines: [["From", "pr-review", "Plugin"],
      ["Model", "opus", null], ["Tools", "Read, Grep", null]], text: null, error: null, actions: [] } });
  assert.deepEqual(nodeLines(sub), { list: false, lines: [["From", "pr-review", "Plugin"],
    ["Tools", "Read, Grep", null]] });
  assert.deepEqual(nodeLines(LUMEN.nodes[4]), { list: true, lines: [["commit", "Personal", null],
    ["release-notes", "pr-review", null]] });
  assert.deepEqual(nodeLines(node("x", "uses", "tool", "Bash", { properties: null })), { list: false, lines: [] });
});

test("Show graph chooses its row's node, or the fold that holds it", () => {
  assert.equal(nodeFor(LUMEN.nodes, "connector:github"), "connector:github");
  assert.equal(nodeFor(LUMEN.nodes, "skill:/home/dev/.claude/skills/commit/SKILL.md"), "skills:more");
  assert.equal(nodeFor(LUMEN.nodes, "agent:Claude:Plan"), null);            // no fold of sub-agents here
  assert.equal(nodeFor([...LUMEN.nodes, node("agents:more", "agents", "subs", "5 more sub-agents")],
    "agent:Claude:Plan"), "agents:more");
  assert.equal(nodeFor(LUMEN.nodes, null), null);
});

test("Show in Agent leads to the node's row by core's id, the agent's to its panel; a node with no row has none",
  () => {
    const show = (/** @type {string | null} */ row) => ({ id: "agent", label: "Show in Agent", path: null,
      server: null, primary: false, row });
    const props = (/** @type {any[]} */ actions) => ({ title: "x", state: null, lines: [], text: null, error: null,
      actions });
    const github = node("connector:github", "uses", "connector", "github", { properties: props([
      { id: "turn-off", label: "Turn off in lumen-api" }, show("connector:github")]) });
    assert.deepEqual(shownInAgent(github), { label: "Show in Agent", row: "connector:github" });
    const agent = node(AGENT, "agents", "agent", "Claude", { properties: props([show(null)]),
      run: { properties: props([{ id: "usage", label: "Open in Usage" }, show(null)]) } });
    assert.deepEqual(shownInAgent(agent), { label: "Show in Agent", row: null });
    assert.deepEqual(shownInAgent(agent, "run"), { label: "Show in Agent", row: null });
    // a built-in tool, a fold, a node with nothing told: no row in the panel, no way there
    assert.equal(shownInAgent(byIdOf(LUMEN, "tool:Bash")), null);
    assert.equal(shownInAgent(byIdOf(LUMEN, "skills:more")), null);
    assert.equal(shownInAgent(node("x", "uses", "tool", "Bash", { properties: null })), null);
    assert.equal(shownInAgent(node("x", "uses", "tool", "Bash", { properties: props([show(null)]),
      run: { properties: props([]) } }), "run"), null);            // what it ran has no row either
  });

test("an edge is seen 3:1 on the canvas and a node's tag reads 4.5:1 on it, in every theme", () => {
  const dir = new URL("../themes/", import.meta.url);
  const themes = readdirSync(dir).filter((name) => name.endsWith(".json"));
  assert.equal(themes.length, 13);
  for (const name of themes) {
    const theme = JSON.parse(readFileSync(new URL(name, dir), "utf8"));
    const t = { ...theme.colors, ...Object.fromEntries(theme.ansi.map((/** @type {string} */ hex,
      /** @type {number} */ n) => [`ansi${n}`, hex])) };
    for (const style of ["always", "demand", "waiting", "failed"]) {
      assert.ok(contrast(wireColor(t, style), t.surface) >= 3, `${name}: a ${style} edge`);
    }
    for (const role of ["personal", "project", "plugin", "account", "local"]) {
      assert.ok(contrast(tagInk(t, role, t.chrome), t.chrome) >= 4.5, `${name}: a ${role} tag on a node`);
    }
    assert.ok(contrast(t.foreground, t.chrome) >= 4.5 && contrast(t.muted, t.chrome) >= 4.5, `${name}: a node`);
    // This conversation: a lit edge on the canvas, a first use's number on its disc, the projects' bars on a card
    assert.ok(contrast(wireLook(t, { from: "a", to: "b", style: "always", gates: [], run: { ran: true } }, "run")
      .color, t.surface) >= 3, `${name}: an edge that ran`);
    assert.ok(contrast(t.accent_foreground ?? t.background, t.accent) >= 4.5, `${name}: a first use's number`);
    assert.ok(contrast(t.muted, t.surface) >= 3, `${name}: a project's bar`);
  }
  assert.equal(wireColor({ dim: "dim" }, "always"), "dim");                 // a theme with no hex: as it is
});

/** A node's run as core words it (graph.py's run()). @param {Record<string, any>} [over] */
const ran = (over = {}) => ({ ran: true, order: null, sub: null, tag: null, calls: null, count: 0, cost: null,
  model: null, share: null, started: null, properties: null, ...over });
// usage.html's Gráf: Claude on Opus with an Explore on Haiku, the files' tools and Bash called, Box never
const OPUS = { name: "Opus 5.5", color: "#3987e5" }, HAIKU = { name: "Haiku 5.5", color: "#199e70" };
const RUN = { nodes: [
  node("rule:a", "in", "rule", "CLAUDE.md", { tag: { text: "Personal", tone: "personal" }, run: ran() }),
  node("skill:r", "in", "skill", "api-routes", { run: ran({ order: 2, sub: "skill · used once · 0.3k" }) }),
  node(AGENT, "agents", "agent", "Claude", { tag: { text: "this conversation", tone: "muted" }, run: ran({
    cost: "$3.70", model: OPUS, share: 0.9, sub: "Opus 5.5 · 38 turns · 1.0M tokens", properties: { title: "Claude",
      state: { text: "$3.70 API value", tone: "ok" }, lines: [["Model", "Opus 5.5 · High", null],
        ["Cache read", "0.79M", "84% of its input"]], text: null, error: null,
      actions: [{ id: "usage", label: "Open in Usage", session: "abc" }] } }) }),
  node("sub:Explore", "agents", "sub", "Explore", { run: ran({ order: 3, cost: "$0.42", model: HAIKU, share: 0.1,
    sub: "Haiku 5.5 · sub-agent · 210k tokens" }) }),
  node("sub:reviewer", "agents", "sub", "code-reviewer", { tag: { text: "pr-review", tone: "plugin" },
    run: ran({ ran: false, sub: "not run in this conversation" }) }),
  node("tool:files", "uses", "tool", "Read · Edit · Write", { sub: "built-in", run: ran({ order: 1, count: 14,
    calls: "14 calls" }) }),
  node("tool:Bash", "uses", "tool", "Bash", { sub: "built-in", run: ran({ order: 4, count: 3, calls: "3 calls" }) }),
  node("tool:Grep", "uses", "tool", "Grep", { run: ran({ order: 5, count: 1, calls: "1 call" }) }),
  node("tool:Glob", "uses", "tool", "Glob", { run: ran({ order: 6, count: 2, calls: "2 calls" }) }),
  node("connector:box", "uses", "connector", "Box", { state: "warn", sub: "needs sign-in",
    tag: { text: "sign in", tone: "warn" }, run: ran({ ran: false, sub: "connector · not used" }) }),
  node("connector:notion", "uses", "connector", "Notion", { dim: true, run: ran({ ran: false }) })],
edges: [{ ...edge("rule:a", AGENT), run: { ran: true, running: false, calls: 0 } },
  { ...edge(AGENT, "tool:files"), run: { ran: true, running: false, calls: 14 } },
  { ...edge(AGENT, "tool:Bash"), run: { ran: true, running: true, calls: 3 } },
  { ...edge(AGENT, "connector:box", "waiting"), run: { ran: false, running: false, calls: 0 } },
  { ...edge(AGENT, "sub:reviewer", "demand"), run: { ran: false, running: false, calls: 0 } }] };
const byId = (/** @type {string} */ id) => /** @type {any} */ (RUN.nodes.find((one) => one.id === id));
const THEME = { accent: "#cba6f7", foreground: "#cdd6f4", surface: "#1e1e2e", dim: "#7f849c", ansi1: "#f38ba8",
  ansi3: "#f9e2af" };

test("in This conversation what did not run stands at half strength, in Wiring only what does not run here", () => {
  assert.deepEqual(VIEWS, ["wiring", "run"]);
  const faint = (/** @type {string} */ view) => RUN.nodes.filter((one) => faded(one, view)).map((one) => one.id);
  assert.deepEqual(faint("wiring"), ["connector:notion"]);
  assert.deepEqual(faint("run"), ["sub:reviewer", "connector:box", "connector:notion"]);
  assert.equal(faded(node("x", "in", "rule", "x"), "run"), false);          // no conversation read: nothing fades
});

test("a first use's number stands on its node's top right corner, clear of the edges coming in", () => {
  assert.equal(DISC, 18);
  assert.deepEqual(badgeAt({ x: 100, y: 50, w: 190, h: 54 }), { x: 281, y: 41 });       // its centre on the corner
  assert.equal(nodeShown(byId("tool:Bash"), "run").order, 4);
  assert.equal(nodeShown(byId("tool:Bash"), "wiring").order, null);
  assert.equal(nodeShown(byId(AGENT), "run").order, null);                  // the agent started it: no number
});

test("a share's bar is its share of the node's width, seen where there is any", () => {
  assert.deepEqual([shareWidth(0.9, 230), shareWidth(0.1, 230), shareWidth(0.001, 230), shareWidth(0, 230),
    shareWidth(1.4, 230), shareWidth(null, 230)], [207, 23, 2, 0, 230, 0]);
});

test("a node says what it ran: its cost and model, its calls, its own line; in Wiring its setup's words", () => {
  assert.deepEqual(nodeShown(byId(AGENT), "run"), { sub: "Opus 5.5 · 38 turns · 1.0M tokens", tag: null,
    calls: null, cost: "$3.70", color: "#3987e5", share: 0.9, order: null });
  assert.deepEqual(nodeShown(byId(AGENT), "wiring"), { sub: "always · 2.4k", calls: null, cost: null, color: null,
    tag: { text: "this conversation", tone: "muted" }, share: null, order: null });
  assert.deepEqual(nodeShown(byId("tool:files"), "run"), { sub: "built-in", tag: null, calls: "14 calls", cost: null,
    color: null, share: null, order: 1 });
  const sub = nodeShown(byId("sub:reviewer"), "run"), box = nodeShown(byId("connector:box"), "run");
  assert.deepEqual([sub.sub, sub.tag?.text, sub.cost], ["not run in this conversation", "pr-review", null]);
  assert.deepEqual([box.sub, box.tag?.text], ["connector · not used", "sign in"]);
  assert.equal(nodeShown(byId("skill:r"), "run").sub, "skill · used once · 0.3k");
});

test("the edges that ran are lit, the running one stronger, the others faint; Wiring keeps its own", () => {
  const [rule, files, bash, box, reviewer] = RUN.edges;
  assert.deepEqual(wireLook(THEME, files, "run"), { key: "ran", color: THEME.accent, width: 2, dashed: false });
  assert.deepEqual(wireLook(THEME, rule, "run").key, "ran");
  assert.deepEqual(wireLook(THEME, bash, "run"), { key: "running", color: THEME.accent, width: 3, dashed: false });
  const faint = wireLook(THEME, box, "run");
  assert.deepEqual([faint.key, faint.width, faint.dashed], ["waiting-faint", 1.5, true]);
  assert.equal(faint.color, `${wireColor(THEME, "waiting")}${FAINT}`);      // at 35%
  assert.equal(FAINT, "59");
  assert.deepEqual(wireLook(THEME, reviewer, "run").key, "demand-faint");
  assert.deepEqual(wireLook(THEME, bash, "wiring"), { key: "always", color: wireColor(THEME, "always"), width: 1.5,
    dashed: false });
  assert.deepEqual(wireLook(THEME, { ...box, style: "odd" }, "wiring").key, "demand");
  assert.equal(running(RUN), true);
  assert.equal(running({ edges: [files] }), false);
});

test("This conversation keeps every tool that ran as its own node; its legend says ran here, Wiring's does not", () => {
  assert.equal(seen(RUN, "run"), RUN);
  assert.ok(seen(RUN, "wiring").nodes.some((/** @type {any} */ one) => one.id === "tools:more"));
  const legend = /** @type {[string, string][]} */ ([["always", "always"], ["demand", "on demand"],
    ["ran", "ran here"], ["failed", "failed"]]);
  assert.deepEqual(legendOf(legend, "wiring").map(([style]) => style), ["always", "demand", "failed"]);
  assert.deepEqual(legendOf(legend, "run"), legend);
});

test("the properties are what the node ran where it tells them, its setup's in Wiring", () => {
  assert.deepEqual(nodeLines(byId(AGENT), "run"), { list: false, lines: [["Model", "Opus 5.5 · High", null],
    ["Cache read", "0.79M", "84% of its input"]] });
  const told = propertiesOf(byId(AGENT), "run");
  assert.deepEqual([told.title, told.state?.text, told.actions.map((/** @type {any} */ one) => one.id)],
    ["Claude", "$3.70 API value", ["usage"]]);
  assert.deepEqual(propertiesOf(byId(AGENT), "wiring").actions, []);
  assert.equal(propertiesOf(byId("tool:Bash"), "run").title, "Bash");       // none of its own: the setup's
  assert.deepEqual(nodeLines(byId("tool:Bash"), "run"), { list: false, lines: [] });
});
