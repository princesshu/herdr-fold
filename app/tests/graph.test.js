// @ts-check
// Tests for the Agents tab's graph (graph.js): its tab and its ask, the Uses column's fold, where the nodes stand,
// an edge's path and its gate's place, a node dragged and its place kept, the keys' steps, what the inspector lists.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { contrast } from "../mods/herdr-fold/agents.js";
import { AGENT, AGENTS_TAB, agentsAsked, agentsTab, APART, askAgents, boxes, dragTo, dropLayout, EDGE, edgePath,
  FLOATS, floatPlace,
  extent, FIRST, folded, gateAt, gatesRoom, GROUP, INDENT, IN_ROOM, keepLayout, layout, layoutKey, nodeFor, nodeLines,
  placed, portOf, sizeOf, stepNode, TIGHT, UNDER, USES_ROOM, GATES_MOST, wireColor, badgeAt, DISC, faded,
  FAINT, legendOf, measured, nodeShown, propertiesOf, running, seen, shareWidth, shownInAgent, unzoomed, VIEWS,
  viewWords, wireLook, askMachines, dashOf, labelAt, labelWidth, LABEL_HIGH, MACHINE_ROOM, MACHINE_ROOM_MOST,
  MACHINES, MACHINES_TAB, machinesAsked, machinesLayout, machinesPlaced, machinesTab, networkUnder, litEdges }
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
    lines: [["commit", "Global", null], ["release-notes", "pr-review", null]], text: null, error: null,
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

test("the tools a chat alone called fold into one node on a long Uses column; one alone stays itself", () => {
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

test("three columns: In from the left, the agent in the middle with its subagents under it, Uses at the right",
  () => {
    const at = layout(LUMEN.nodes, SIZE), box = boxes(LUMEN.nodes, at);
    const [personal, project, api, skill, more] = LUMEN.nodes.slice(0, 5).map((n) => at[n.id]);
    assert.deepEqual(personal, { x: EDGE, y: FIRST });
    assert.equal(project.y - personal.y, sizeOf(LUMEN.nodes[0]).h + APART);
    assert.equal(skill.y - api.y, sizeOf(LUMEN.nodes[2]).h + GROUP);        // the skills a group of their own
    assert.equal(more.y - skill.y, sizeOf(LUMEN.nodes[3]).h + APART);
    assert.ok([project, api, skill, more].every((one) => one.x === EDGE));
    // the agent on the canvas's middle, its subagent under it and a step in
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
  assert.equal(small[AGENT].x, EDGE + 190 + TIGHT);
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
  const bash = [{ text: "ask · python3 -m pytest, git status +1 allowed" }, { text: "deny rm -rf" }, { text: "hook" }];
  assert.ok(gatesRoom([{ gates: bash }]) > USES_ROOM);                      // its three pills whole, over no node
  assert.equal(gatesRoom([{ gates: [{ text: "x".repeat(120) }] }]), GATES_MOST);     // never wider
  const narrow = { width: 500, height: 300 };
  const close = boxes(LUMEN.nodes, layout(LUMEN.nodes, narrow, {}, IN_ROOM));
  assert.equal(close["tool:files"].x, close[AGENT].x + 250 + IN_ROOM);
  const alone = LUMEN.nodes.filter((one) => one.column !== "in");
  assert.equal(layout(alone, narrow)[AGENT].x, EDGE);
});

test("a canvas narrower than the columns' room brings them nearer, to TIGHT and the gates' own; then it scrolls",
  () => {
    // the demo app's canvas with the sidebar and the panel open is 781 wide: three rules, two tools, an ask each
    const asks = LUMEN.edges.map((one) => (one.gates.length ? { ...one, gates: [{ text: "ask", tone: "ask" }] } : one));
    const [room, least] = [gatesRoom(asks), gatesRoom(asks, true)];
    assert.deepEqual([room, least, gatesRoom([], true)], [IN_ROOM, 49, TIGHT]);     // the pill's own room at least
    const ins = LUMEN.nodes.filter((one) => one.column === "in");
    for (const width of [781, 830, 860]) {
      const size = { width, height: 700 }, all = boxes(LUMEN.nodes, layout(LUMEN.nodes, size, {}, room, least));
      const agent = all[AGENT], uses = all["tool:files"];
      const apart = agent.x - Math.max(...ins.map((one) => all[one.id].x + all[one.id].w));
      assert.equal(extent(all, size).width, width, `at ${width}`);          // within the canvas: nothing cut
      assert.equal(uses.x + uses.w, width - EDGE, `at ${width}`);           // Uses at the right edge
      assert.ok(apart >= TIGHT && apart < IN_ROOM, `at ${width}: ${apart}`);
      assert.ok(uses.x - (agent.x + agent.w) >= least, `at ${width}`);       // room for the gates' pills
    }
    // narrower than the columns at their nearest: TIGHT and the gates' room apart, and the canvas scrolls
    const size = { width: 700, height: 700 }, all = boxes(LUMEN.nodes, layout(LUMEN.nodes, size, {}, room, least));
    assert.deepEqual([all[AGENT].x, all["tool:files"].x], [EDGE + 190 + TIGHT, EDGE + 190 + TIGHT + 250 + least]);
    assert.equal(extent(all, size).width, all["tool:files"].x + 190 + EDGE);
    // with room enough, as far apart as ever
    assert.deepEqual(layout(LUMEN.nodes, SIZE, {}, room, least), layout(LUMEN.nodes, SIZE, {}, room));
  });

test("an edge leaves a node's right for the next one's left; a subagent's drops from its agent's foot", () => {
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

test("a graph's properties stand lower left, or where their head was let go, never past the canvas's edges", () => {
  // the owner: "ha éppen ráfed egy részre, akkor arrébb húzható legyen más pozícióba a wrapperen belül"
  const size = { width: 300, height: 200 }, frame = { width: 1000, height: 700 };
  assert.equal(FLOATS, "herdr-fold.inspector-at");
  assert.deepEqual(floatPlace(null, size, frame, 12), { x: 12, y: 488 });            // its own place: lower left
  assert.deepEqual(floatPlace({ x: 500.4, y: 100.6 }, size, frame, 12), { x: 500, y: 101 });
  assert.deepEqual(floatPlace({ x: 900, y: 650 }, size, frame, 12), { x: 688, y: 488 });   // kept inside: right, foot
  assert.deepEqual(floatPlace({ x: -40, y: -40 }, size, frame, 12), { x: 12, y: 12 });
  // a canvas grown smaller since: back inside it; one smaller than the float itself: its top left corner
  assert.deepEqual(floatPlace({ x: 688, y: 488 }, size, { width: 700, height: 400 }, 12), { x: 388, y: 188 });
  assert.deepEqual(floatPlace({ x: 300, y: 300 }, size, { width: 200, height: 100 }, 12), { x: 12, y: 12 });
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
  assert.deepEqual(nodeLines(LUMEN.nodes[4]), { list: true, lines: [["commit", "Global", null],
    ["release-notes", "pr-review", null]] });
  assert.deepEqual(nodeLines(node("x", "uses", "tool", "Bash", { properties: null })), { list: false, lines: [] });
});

test("Show graph chooses its row's node, or the fold that holds it", () => {
  assert.equal(nodeFor(LUMEN.nodes, "connector:github"), "connector:github");
  assert.equal(nodeFor(LUMEN.nodes, "skill:/home/dev/.claude/skills/commit/SKILL.md"), "skills:more");
  assert.equal(nodeFor(LUMEN.nodes, "agent:Claude:Plan"), null);            // no fold of subagents here
  assert.equal(nodeFor([...LUMEN.nodes, node("agents:more", "agents", "subs", "5 more subagents")],
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

test("an edge is seen 3:1 on the canvas and a node's words read 4.5:1 on it, in every theme", () => {
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
    assert.ok(contrast(t.foreground, t.chrome) >= 4.5 && contrast(t.muted, t.chrome) >= 4.5, `${name}: a node`);
    // This chat: a lit edge on the canvas, a first use's number on its disc, the projects' bars on a card
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
  node("rule:a", "in", "rule", "CLAUDE.md", { tag: "Global", run: ran() }),
  node("skill:r", "in", "skill", "api-routes", { run: ran({ order: 2, sub: "used once · 300" }) }),
  node(AGENT, "agents", "agent", "Claude", { run: ran({
    cost: "$3.70", model: OPUS, share: 0.9, sub: "Opus 5.5 · 38 turns · 1.0M tokens", properties: { title: "Claude",
      state: { text: "$3.70 API value", tone: "ok" }, lines: [["Model", "Opus 5.5 · High", null],
        ["Cache read", "0.79M", "84% of its input"]], text: null, error: null,
      actions: [{ id: "usage", label: "Open in Usage", session: "abc" }] } }) }),
  node("sub:Explore", "agents", "sub", "Explore", { run: ran({ order: 3, cost: "$0.42", model: HAIKU, share: 0.1,
    sub: "Haiku 5.5 · 210k tokens" }) }),
  node("sub:reviewer", "agents", "sub", "code-reviewer", { tag: "pr-review",
    run: ran({ ran: false, sub: "not run in this chat" }) }),
  node("tool:files", "uses", "tool", "Read · Edit · Write", { sub: null, run: ran({ order: 1, count: 14,
    calls: "14 calls" }) }),
  node("tool:Bash", "uses", "tool", "Bash", { sub: "sandboxed, 2 hosts", run: ran({ order: 4, count: 3,
    calls: "3 calls" }) }),
  node("tool:Grep", "uses", "tool", "Grep", { run: ran({ order: 5, count: 1, calls: "1 call" }) }),
  node("tool:Glob", "uses", "tool", "Glob", { run: ran({ order: 6, count: 2, calls: "2 calls" }) }),
  node("connector:box", "uses", "connector", "Box", { state: "warn", sub: "sign in", tag: "claude.ai",
    run: ran({ ran: false, sub: "not used", tag: { text: "sign in", tone: "warn" } }) }),
  node("connector:notion", "uses", "connector", "Notion", { dim: true, run: ran({ ran: false }) })],
edges: [{ ...edge("rule:a", AGENT), run: { ran: true, running: false, calls: 0 } },
  { ...edge(AGENT, "tool:files"), run: { ran: true, running: false, calls: 14 } },
  { ...edge(AGENT, "tool:Bash"), run: { ran: true, running: true, calls: 3 } },
  { ...edge(AGENT, "connector:box", "waiting"), run: { ran: false, running: false, calls: 0 } },
  { ...edge(AGENT, "sub:reviewer", "demand"), run: { ran: false, running: false, calls: 0 } }] };
const byId = (/** @type {string} */ id) => /** @type {any} */ (RUN.nodes.find((one) => one.id === id));
const THEME = { accent: "#cba6f7", foreground: "#cdd6f4", surface: "#1e1e2e", dim: "#7f849c", ansi1: "#f38ba8",
  ansi3: "#f9e2af" };

test("in This chat what did not run stands at half strength, in Wiring only what does not run here", () => {
  assert.deepEqual(VIEWS, ["wiring", "run"]);
  const faint = (/** @type {string} */ view) => RUN.nodes.filter((one) => faded(one, view)).map((one) => one.id);
  assert.deepEqual(faint("wiring"), ["connector:notion"]);
  assert.deepEqual(faint("run"), ["sub:reviewer", "connector:box", "connector:notion"]);
  assert.equal(faded(node("x", "in", "rule", "x"), "run"), false);          // no chat read: nothing fades
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
    tag: null, share: null, order: null });
  assert.deepEqual(nodeShown(byId("tool:files"), "run"), { sub: null, tag: null, calls: "14 calls", cost: null,
    color: null, share: null, order: 1 });
  // a source's tag a word (its chip); what This chat says of a node a state in its tone
  const sub = nodeShown(byId("sub:reviewer"), "run"), box = nodeShown(byId("connector:box"), "run");
  assert.deepEqual([sub.sub, sub.tag, sub.cost], ["not run in this chat", "pr-review", null]);
  assert.deepEqual([box.sub, box.tag], ["not used", { text: "sign in", tone: "warn" }]);
  assert.equal(nodeShown(byId("connector:box"), "wiring").tag, "claude.ai");
  assert.equal(nodeShown(byId("skill:r"), "run").sub, "used once · 300");
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

test("This chat keeps every tool that ran as its own node; its legend says ran here, Wiring's does not", () => {
  assert.equal(seen(RUN, "run"), RUN);
  assert.ok(seen(RUN, "wiring").nodes.some((/** @type {any} */ one) => one.id === "tools:more"));
  const legend = /** @type {[string, string][]} */ ([["always", "always"], ["demand", "on demand"],
    ["ran", "ran here"], ["failed", "failed"], ["waiting", "sign in"]]);
  assert.deepEqual(legendOf(legend, "wiring").map(([, word]) => word), ["always", "on demand", "failed", "sign in"]);
  assert.deepEqual(legendOf(legend, "run"), legend);
});

test("the graph's two views in core's words, This chat with the chat's whole beside it once there is one", () => {
  const words = { views: { wiring: "Wiring", run: "This chat" } };
  assert.deepEqual(viewWords({ words, cost: "~$4.12" }), [["wiring", "Wiring"], ["run", "This chat · ~$4.12"]]);
  assert.deepEqual(viewWords({ words, cost: null }), [["wiring", "Wiring"], ["run", "This chat"]]);
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

// --- the Machines tab's graph (remote-machines-mockups/graph.html), core's (machine_graph.py)

/** A node of the machines' graph as core words it. @param {string} id @param {string} column @param {string} kind
 * @param {string | null} parent @param {Record<string, any>} [over] */
const mnode = (id, column, kind, parent, over = {}) => ({ id, column, kind, title: id.split(":").pop(), icon: null,
  brand: null, tag: null, sub: "1 space", parts: [], state: null, dim: false, chips: [], parent, network: null,
  properties: { title: id, state: null, why: [], command: null, lines: [], actions: [] }, run: null, ...over });
/** @param {string} from @param {string} to @param {string} [style] @param {string | null} [label] */
const medge = (from, to, style = "always", label = null) => ({ from, to, style, gates: [], run: null, label });
const NET = (/** @type {string} */ kind) => mnode(`network:${kind}`, "networks", "network", "mac", { network: kind });
const ON = (/** @type {string} */ name, /** @type {string} */ parent, column = "machines") => mnode(`machine:${name}`,
  column, "machine", parent);
// graph.html's lumen-api world as core/machine_graph.py draws it: the networks in the routes' order, the machines by
// name, build-01 and db-02 behind lumen-api, studio on the local network and standby on Tailscale
const WORLD = { nodes: [mnode("mac", "mac", "mac", null), NET("local"), NET("tailscale"), NET("netbird"),
  NET("zerotier"), NET("public"), ON("lab-pi", "network:local"), ON("studio", "network:local"),
  ON("harbor-web", "network:tailscale"), ON("lumen-api", "network:tailscale"),
  ON("build-01", "machine:lumen-api", "through"), ON("db-02", "machine:lumen-api", "through"),
  ON("kelp-ci", "network:netbird"), ON("tidepool", "network:netbird"), ON("vps-edge", "network:public")],
edges: [...["local", "tailscale", "netbird", "zerotier", "public"].map((kind) => medge("mac", `network:${kind}`)),
  medge("network:local", "machine:lab-pi", "always", "5 ms"), medge("network:local", "machine:studio"),
  medge("network:tailscale", "machine:harbor-web", "demand", "relayed 84 ms"),
  medge("network:tailscale", "machine:lumen-api", "always", "direct 12 ms"),
  medge("machine:lumen-api", "machine:build-01", "always", "19 ms"),
  medge("machine:lumen-api", "machine:db-02", "failed"),
  medge("network:netbird", "machine:kelp-ci", "demand", "relayed 61 ms"),
  medge("network:netbird", "machine:tidepool", "always", "direct 22 ms"),
  medge("network:public", "machine:vps-edge", "always", "41 ms"),
  medge("network:tailscale", "machine:studio", "standby")] };
const WIDE_SIZE = { width: 1416, height: 800 };
/** The boxes of GRAPH laid out on SIZE. @param {{ nodes: any[], edges: any[] }} graph */
const laidOut = (graph, size = WIDE_SIZE, sizes = {}) => boxes(graph.nodes, machinesLayout(graph.nodes, graph.edges,
  size, sizes), sizes);
/** Whether two boxes share any point. @param {import("../mods/herdr-fold/graph.js").Box} a
 * @param {import("../mods/herdr-fold/graph.js").Box} b */
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
/** Each labelled edge's label as drawn on BOXES: its box, the edge's path through its port. */
function labels(graph, all) {
  const out = graph.edges.filter((one) => all[one.from] && all[one.to]);
  return out.filter((one) => one.label).map((one) => {
    const mine = out.filter((other) => other.from === one.from)
      .sort((a, b) => all[a.to].y - all[b.to].y);
    const at = labelAt(edgePath(all[one.from], all[one.to], portOf(mine.length, mine.indexOf(one))));
    const w = labelWidth(one.label);
    return { edge: `${one.from}>${one.to}`, x: at.x - w / 2, y: at.y - LABEL_HIGH / 2, w, h: LABEL_HIGH };
  });
}

test("four columns: This Mac, the networks, the machines, those behind another; each column's left edges in one line",
  () => {
    assert.equal(MACHINES_TAB, "Machines");
    const all = laidOut(WORLD), id = (/** @type {string} */ name) => all[`machine:${name}`];
    const column = (/** @type {string} */ name) => WORLD.nodes.filter((one) => one.column === name)
      .map((one) => all[one.id]);
    const [mac, networks, machines, through] = ["mac", "networks", "machines", "through"].map(column);
    assert.equal(mac[0].x, EDGE);
    for (const list of [networks, machines, through]) assert.equal(new Set(list.map((one) => one.x)).size, 1);
    assert.ok(mac[0].x + mac[0].w < networks[0].x && networks[0].x + 190 < machines[0].x
      && machines[0].x + 190 < through[0].x);
    // the machines in core's order from FIRST down, a network's apart from the next one's
    assert.equal(id("lab-pi").y, FIRST);
    assert.equal(id("studio").y - id("lab-pi").y, id("lab-pi").h + APART);
    assert.equal(id("harbor-web").y - id("studio").y, id("studio").h + GROUP);
    assert.equal(id("vps-edge").y - id("tidepool").y, id("tidepool").h + GROUP);
    // those behind a machine from its height down, one under the other
    assert.equal(id("build-01").y, id("lumen-api").y);
    assert.equal(id("db-02").y, id("build-01").y + id("build-01").h + APART);
    // a network beside its machines' middle; one with none after those with some; This Mac beside the networks'
    const tailscale = all["network:tailscale"], middle = (id("harbor-web").y + id("lumen-api").y
      + id("lumen-api").h) / 2;
    assert.ok(Math.abs(tailscale.y + tailscale.h / 2 - middle) <= 1);
    assert.equal(all["network:zerotier"].y, all["network:public"].y + all["network:public"].h + APART);
    const span = (networks[0].y + Math.max(...networks.map((one) => one.y + one.h))) / 2;
    assert.ok(Math.abs(mac[0].y + mac[0].h / 2 - span) <= 1);
    // nothing on another, in whole px
    const list = Object.values(all);
    assert.ok(list.every((a, i) => list.every((b, j) => i === j || !overlap(a, b))));
    assert.ok(list.every((one) => Number.isInteger(one.x) && Number.isInteger(one.y)));
    // with no machine behind another, three columns
    const three = { nodes: WORLD.nodes.filter((one) => one.column !== "through"), edges: WORLD.edges };
    assert.equal(Object.values(laidOut(three)).filter((one) => one.x > id("lumen-api").x).length, 0);
  });

test("an edge's label stands at its middle, clear of every node; the columns as far apart as the widest one needs",
  () => {
    assert.deepEqual(labelAt([[0, 0], [60, 0], [140, 80], [200, 80]]), { x: 100, y: 40 });
    assert.equal(labelWidth("relayed 84 ms"), Math.ceil(13 * 6.2 + 14));
    // on graph.html's canvas, on the demo app's (781), and with nodes measured wider and narrower
    const sizes = { "network:tailscale": { w: 236, h: 54 }, "machine:lumen-api": { w: 260, h: 70 } };
    for (const [size, measured] of [[WIDE_SIZE, {}], [{ width: 781, height: 600 }, {}], [WIDE_SIZE, sizes],
      [{ width: 600, height: 400 }, sizes]]) {
      const all = laidOut(WORLD, size, measured), nodes = Object.values(all);
      for (const label of labels(WORLD, all)) {
        assert.ok(nodes.every((one) => !overlap(label, one)), `${label.edge} at ${size.width}`);
      }
    }
    // a wide canvas spreads the columns to graph.html's room, never further; a narrow one scrolls
    const wide = laidOut(WORLD), lumen = wide["machine:lumen-api"], tailscale = wide["network:tailscale"];
    assert.equal(lumen.x - (tailscale.x + tailscale.w), MACHINE_ROOM_MOST);
    const narrow = laidOut(WORLD, { width: 600, height: 400 });
    assert.ok(extent(narrow, { width: 600, height: 400 }).width > 600);
    assert.ok(narrow["machine:lumen-api"].x - (narrow["network:tailscale"].x + 190) >= MACHINE_ROOM);
  });

test("a standby route is dotted and faint, with no label; the rest as the Agents tab draws them", () => {
  const standby = wireLook(THEME, medge("network:tailscale", "machine:studio", "standby"), "wiring");
  assert.deepEqual(standby, { key: "standby", color: `${wireColor(THEME, "standby")}8c`, width: 1.5,
    dashed: true });
  assert.deepEqual([dashOf("standby"), dashOf("demand"), dashOf("failed")], [[2, 4], [5, 5], [5, 5]]);
  assert.equal(wireLook(THEME, medge("a", "b", "failed"), "wiring").color, wireColor(THEME, "failed"));
});

test("the machines' places are kept under machines, the window's one graph, beside the spaces' graphs", () => {
  assert.equal(MACHINES, "machines");
  const live = new Set(["s1"]);
  const kept = keepLayout({ "gone|/x|claude": { a: { x: 1, y: 2 } } }, MACHINES, { "machine:studio": { x: 900.4,
    y: 300.6 } }, live);
  assert.deepEqual(kept, { machines: { "machine:studio": { x: 900, y: 301 } } });
  // a space's graph kept later keeps the machines' too; a gone space's still goes
  const both = keepLayout(kept, layoutKey("s1", "/home/dev/lumen-api", "claude"), { agent: { x: 5, y: 6 } }, live);
  assert.deepEqual(Object.keys(both), ["machines", "s1|/home/dev/lumen-api|claude"]);
  const at = machinesPlaced(both, WORLD.nodes, WORLD.edges, WIDE_SIZE);
  const fresh = machinesLayout(WORLD.nodes, WORLD.edges, WIDE_SIZE);
  assert.deepEqual(at["machine:studio"], { x: 900, y: 301 });
  assert.deepEqual(at["machine:lab-pi"], fresh["machine:lab-pi"]);
  assert.deepEqual(machinesPlaced("junk", WORLD.nodes, WORLD.edges, WIDE_SIZE), fresh);
  assert.deepEqual(dropLayout(both, MACHINES), { "s1|/home/dev/lumen-api|claude": { agent: { x: 5, y: 6 } } });
});

test("the Machines tab is the window's one so named whose pane is the mod's, in any space; an ask reaches it once",
  () => {
    const list = [{ id: "s1", active: true, tabs: [{ id: "t1", name: "api" }] },
      { id: "s2", active: false, tabs: [{ id: "t2", name: MACHINES_TAB }, { id: "t3", name: MACHINES_TAB }] }];
    const found = machinesTab(list, [{ tab: "t2", terminal: "a1" }, { tab: "t3", mod: "herdr-fold" }]);
    assert.deepEqual([found?.space.id, found?.tab.id], ["s2", "t3"]);
    assert.equal(machinesTab(list, [{ tab: "t2", terminal: "a1" }]), null);       // a terminal named so is not it
    assert.equal(machinesTab([], []), null);
    const ask = askMachines("machine:lumen-api", 1000);
    assert.deepEqual(ask, { node: "machine:lumen-api", at: 1000 });
    assert.deepEqual(machinesAsked(ask, null, 1500), ask);
    assert.equal(machinesAsked(ask, 1000, 1500), null);                     // answered already
    assert.equal(machinesAsked(ask, null, 1000 + 60000), null);             // too old
    assert.equal(machinesAsked({ node: 7, at: 1000 }, null, 1500)?.node, null);
    assert.equal(machinesAsked("junk", null, 1500), null);
  });

test("a node's network is the one it hangs under: a machine behind another its jump host's", () => {
  assert.equal(networkUnder(WORLD.nodes, "machine:build-01"), "tailscale");
  assert.equal(networkUnder(WORLD.nodes, "machine:studio"), "local");
  assert.equal(networkUnder(WORLD.nodes, "network:netbird"), "netbird");
  assert.equal(networkUnder(WORLD.nodes, "mac"), null);
  const loop = [ON("a", "machine:b", "through"), ON("b", "machine:a", "through")];
  assert.equal(networkUnder(loop, "machine:a"), null);
});

test("a machine on two routes, chosen, lights the one in use (graph.html's Két út); one route lights none", () => {
  assert.deepEqual([...litEdges(WORLD.edges, "machine:studio")], ["network:local>machine:studio"]);
  assert.deepEqual([...litEdges(WORLD.edges, "machine:build-01")], []);
  assert.deepEqual([...litEdges(WORLD.edges, null)], []);
});
