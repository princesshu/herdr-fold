// @ts-check
// The Agents tab's graph, pure: its tab and what it is asked to show, where its nodes stand (three columns, a dragged
// one where it was left), an edge's path, its gate's place. The nodes, edges and words are core's (graph.py).
import { contrast, mixColor } from "./agents.js";
import { ASK_MS } from "./layers.js";

export const AGENTS_TAB = "Agents";                  // the tab's name, usage.html's: one a space
export const AGENTS_ASK = "herdr-fold.agents-ask";   // shared: {space: {node, session, at}}, openAgents()'s ask
export const GRAPH_LAYOUT = "herdr-fold.graph-layout";       // shared: {"space|folder|agent": {node: {x, y}}}
export const AGENT = "agent";                        // the agent's own node, as core names it
export const MORE_TOOLS = "tools:more";              // the node the tools a chat alone called fold into
// px: the canvas's edge to a column, the columns' names' and the first node's top, between two nodes, two groups
export const EDGE = 24, HEADS = 48, FIRST = 80, APART = 12, GROUP = 32;
export const UNDER = 48, INDENT = 16;                // px: a subagent under its agent, and in from its left
export const IN_ROOM = 96, USES_ROOM = 264;          // px at least between two columns: the edges', the gates' too
export const TIGHT = 48;                             // px at least between two columns on a canvas too narrow for those
export const GATES_MOST = 2 * USES_ROOM;             // px at most a row of gates keeps: two named, a deny and a hook
const NODE = 190, HIGH = 54, CHIPS = 24;             // px: a node's width at least, its height, its chips' row
const WIDE = /** @type {Record<string, number>} */ ({ agent: 250, sub: 230, subs: 230 });
const HANDLE = 120, SHORT = 40;                      // px: an edge's handles, agent-graph.html's; at least
const SPREAD = 4, PORTS = 5;                         // px between two edges leaving a node, and how many apart
const DROP = 24, CORNER = 12;                        // px: a subagent's edge from its left, a corner kept clear
const GATE = 0.55, STEPS = 40;                       // a gate's place along its edge; the pieces it is measured in
const PILL_CHAR = 6.2, PILL_PAD = 14;                // px: a gate's character at 11, its pill's padding and edge
const SHAKE = 4;                                     // px a press may move and still be a click
const SEEN = 3;                                      // a mark's contrast on what it stands on (WCAG's, not text)
const FIXED = ["tool:files", "tool:Bash", "tool:shell"];     // the tools every graph has (core's ids)
const FOLDS = /** @type {Record<string, string>} */ ({ skill: "skills:more", agent: "agents:more",
  tool: MORE_TOOLS });
const LISTS = ["skills", "subs", "tools"];           // a folded node's kinds: its properties a list of names
const HEX = /^#[0-9a-f]{6}$/i;
export const VIEWS = ["wiring", "run"];              // the graph's two views, core's words' keys (graph.py's)
export const DISC = 18;                              // px: a first use's number, on its node's top right corner
export const FAINT = "59";                           // an edge that did not run, This chat's: at 35%
const WIRE = 1.5, RAN = 2, RUNNING = 3;              // px: an edge's line; one that ran; the one running now
const STYLES = ["always", "demand", "waiting", "failed"];     // an edge's styles, core's; any other as on demand

/** A node as core words it: TAG its source's word. @typedef {{ id: string, column: string, kind: string,
 * title: string, dim: boolean, icon: string | null, brand: string | null, tag: string | null, sub: string | null,
 * run: any, state: string | null, chips: string[], parent: string | null, properties: any }} Node */
/** An edge. @typedef {{ from: string, to: string, style: string, gates: { text: string, tone: string }[],
 * run: any }} Edge */
/** @typedef {{ x: number, y: number }} Point */
/** @typedef {{ x: number, y: number, w: number, h: number }} Box */
/** @typedef {{ w: number, h: number }} Size */
/** @typedef {[number, number][]} Path a cubic: its start, its two handles, its end */

/** SPACE's Agents tab: the one so named whose pane is herdr-fold's (a terminal somebody named so is not it); null.
 * @param {any} space @param {any[]} panes */
export const agentsTab = (space, panes) => space?.tabs?.find((/** @type {any} */ tab) => tab.name === AGENTS_TAB
  && panes.some((pane) => pane.tab === tab.id && pane.mod === "herdr-fold")) ?? null;

/** KEPT ({space: ask}) with ASK for SPACE's tab at NOW, the spaces no longer LIVE left out. @param {any} kept
 * @param {string} space @param {Record<string, any>} ask @param {Set<string>} live @param {number} now */
export function askAgents(kept, space, ask, live, now) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([id]) => live.has(id) && id !== space)),
    [space]: { ...ask, at: now } };
}

/** SPACE's ask in KEPT where its tab answers it: newer than the LAST one answered, no older than ASK_MS at NOW; else
 * null. @param {any} kept @param {string} space @param {number | null} last @param {number} now */
export function agentsAsked(kept, space, last, now) {
  const ask = kept && typeof kept === "object" ? kept[space] : null;
  return ask && typeof ask === "object" && typeof ask.at === "number" && ask.at !== last && now >= ask.at
    && now - ask.at <= ASK_MS ? ask : null;
}

/** GRAPH (core's) as Wiring draws it: the built-in tools a chat alone called (every one but FIXED) as one
 * node where there are two or more, each with its gates in that node's properties, one edge from whatever reached
 * any. @template {{ nodes: any[], edges: any[] }} G @param {G} graph @returns {G} */
export function folded(graph) {
  const extra = graph.nodes.filter((one) => one.column === "uses" && one.kind === "tool" && !FIXED.includes(one.id));
  if (extra.length < 2) return graph;
  const gone = new Set(extra.map((one) => one.id)), title = `${extra.length} more tools`;
  const gates = (/** @type {string} */ id) => (graph.edges.find((edge) => edge.from === AGENT && edge.to === id)
    ?.gates ?? []).map((/** @type {any} */ gate) => gate.text).join(", ");
  const more = { id: MORE_TOOLS, column: "uses", kind: "tools", title, icon: "wrench", brand: null, tag: null,
    sub: extra[0].sub, state: null, dim: false, chips: [], parent: null, run: null, properties: { title,
      state: null, lines: extra.map((one) => [one.title, gates(one.id), null]), text: null, error: null,
      actions: [] } };
  const seen = new Set();
  const edges = graph.edges.map((edge) => (gone.has(edge.to) ? { ...edge, to: MORE_TOOLS, style: "always", gates: [],
    run: null } : edge)).filter((edge) => {
    const key = `${edge.from}|${edge.to}`;
    return edge.to !== MORE_TOOLS || (!seen.has(key) && Boolean(seen.add(key)));
  });
  return { ...graph, nodes: graph.nodes.flatMap((one) => (one.id === extra[0].id ? [more] : gone.has(one.id) ? []
    : [one])), edges };
}

/** NODE's size: as measured (SIZES, by id), else its kind's width at least and a node's height, its chips' row more.
 * @param {Node} node @param {Record<string, Size>} [sizes] @returns {Size} */
export const sizeOf = (node, sizes = {}) => sizes[node.id] ?? { w: WIDE[node.kind] ?? NODE,
  h: HIGH + (node.chips?.length ? CHIPS : 0) };

/** PX the app measured (on_size_change's, a pointer's: the window's own) in the px a place and a size are set in,
 * which the app's ZOOM scales (250 set is 200 measured at 0.8); a zoom that is none counts as 1.
 * @param {number} px @param {number} [zoom] */
export const unzoomed = (px, zoom = 1) => (Number.isFinite(zoom) && zoom > 0 ? px / zoom : px);

/** A node's size as measured ({width, height}, the window's px) at ZOOM, in whole px as set: sizeOf()'s sizes.
 * @param {{ width: number, height: number }} size @param {number} [zoom] @returns {Size} */
export const measured = (size, zoom = 1) => ({ w: Math.round(unzoomed(size.width, zoom)),
  h: Math.round(unzoomed(size.height, zoom)) });

/** NODES in a column from Y down, a new group (GROUPS: each one's kinds) GROUP apart: each one's y, and the foot.
 * @param {Node[]} nodes @param {string[][]} groups @param {Record<string, Size>} sizes @param {number} y */
function stack(nodes, groups, sizes, y) {
  /** @type {Record<string, number>} */
  const tops = {};
  let foot = y, last = -1;
  for (const one of nodes) {
    const group = groups.findIndex((kinds) => kinds.includes(one.kind));
    tops[one.id] = foot + (last < 0 ? 0 : group === last ? APART : GROUP);
    foot = tops[one.id] + sizeOf(one, sizes).h;
    last = group;
  }
  return { tops, foot };
}

/** The room between the agents and Uses for EDGES' gates: the widest edge's pills (PILL_CHAR a character, PILL_PAD
 * round each, 4 apart), 8 at each end, so no pill lies over a node; IN_ROOM at least (TIGHT for a canvas too narrow),
 * GATES_MOST at most. @param {{ gates: { text: string }[] }[]} edges @param {boolean} [tight] */
export const gatesRoom = (edges, tight = false) => Math.min(GATES_MOST, Math.max(tight ? TIGHT : IN_ROOM,
  ...edges.map((edge) => (edge.gates.length ? Math.ceil(edge.gates.reduce((sum, gate) => sum + [...gate.text].length
    * PILL_CHAR + PILL_PAD + 4, 12)) : 0))));

/** Where NODES stand on a canvas SIZE large, agent-graph.html's three columns (docs/styleguide.md, The Agents tab),
 * IN_ROOM and ROOM apart; nearer on a canvas too narrow for that, to TIGHT and LEAST (gatesRoom()'s), then grown.
 * @param {Node[]} nodes @param {{ width: number, height: number }} size @param {Record<string, Size>} [sizes] */
export function layout(nodes, size, sizes = {}, room = USES_ROOM, least = room) {
  const of = (/** @type {string} */ column) => nodes.filter((one) => one.column === column);
  const widest = (/** @type {Node[]} */ some) => Math.max(0, ...some.map((one) => sizeOf(one, sizes).w));
  const ins = of("in"), uses = of("uses"), agents = of("agents");
  const subs = agents.filter((one) => one.id !== AGENT), agent = agents.find((one) => one.id === AGENT);
  const wide = Math.max(agent ? sizeOf(agent, sizes).w : 0, subs.length ? INDENT + widest(subs) : 0);
  const [most, fewest] = [(ins.length ? IN_ROOM : 0) + room, (ins.length ? TIGHT : 0) + least];
  const spare = size.width - 2 * EDGE - (ins.length ? widest(ins) : 0) - wide - widest(uses);
  const share = most > fewest ? Math.min(1, Math.max(0, (spare - fewest) / (most - fewest))) : 1;
  const apart = (/** @type {number} */ far, /** @type {number} */ near) => near + Math.floor((far - near) * share);
  const inRoom = apart(IN_ROOM, TIGHT), usesRoom = apart(room, least);
  const start = EDGE + (ins.length ? widest(ins) + inRoom : 0);
  const right = Math.max(size.width - EDGE - widest(uses), start + wide + usesRoom);
  const middle = Math.round((size.width - (agent ? sizeOf(agent, sizes).w : wide)) / 2);
  const x = Math.max(start, Math.min(middle, right - usesRoom - wide));
  const left = stack(ins, [["rule"], ["skill", "skills"]], sizes, FIRST);
  const used = stack(uses, [["tool", "tools"], ["connector"]], sizes, FIRST);
  const high = agents.reduce((sum, one, n) => sum + sizeOf(one, sizes).h + (n === 0 ? 0 : n === 1 && agent ? UNDER
    : APART), 0);
  const seen = Math.min(Math.max(left.foot, used.foot), size.height - EDGE) - FIRST;     // with no scrolling
  const top = FIRST + Math.max(0, Math.round((seen - high) / 2));
  /** @type {Record<string, Point>} */
  const at = {};
  for (const one of ins) at[one.id] = { x: EDGE, y: left.tops[one.id] };
  for (const one of uses) at[one.id] = { x: right, y: used.tops[one.id] };
  let y = top;
  for (const [n, one] of [...(agent ? [agent] : []), ...subs].entries()) {
    y += n === 0 ? 0 : n === 1 && agent ? UNDER : APART;
    at[one.id] = { x: one.id === AGENT ? x : x + INDENT, y };
    y += sizeOf(one, sizes).h;
  }
  return at;
}

/** Each of NODES' box: where it stands (AT) and how large it is. @param {Node[]} nodes
 * @param {Record<string, Point>} at @param {Record<string, Size>} [sizes] @returns {Record<string, Box>} */
export const boxes = (nodes, at, sizes = {}) => Object.fromEntries(nodes.filter((one) => at[one.id])
  .map((one) => [one.id, { ...at[one.id], ...sizeOf(one, sizes) }]));

/** The room BOXES need, EDGE round the outermost; never smaller than its frame's SIZE (scrolled past it).
 * @param {Record<string, Box>} all @param {{ width: number, height: number }} size */
export function extent(all, size) {
  const list = Object.values(all);
  return { width: Math.max(size.width, ...list.map((one) => one.x + one.w + EDGE)),
    height: Math.max(size.height, ...list.map((one) => one.y + one.h + EDGE)) };
}

/** The edge from box A to box B as a cubic: from A's right to B's left (from its K-th port), handles HANDLE long, half
 * the way where close; B under A (a subagent): straight down from A's foot, DROP in from B's left; B left of A: from
 * A's left to B's right. @param {Box} a @param {Box} b @param {number} [k] @returns {Path} */
export function edgePath(a, b, k = 0) {
  if (b.y >= a.y + a.h && b.x < a.x + a.w && b.x + b.w > a.x) {
    const x = Math.max(a.x + CORNER, Math.min(b.x + DROP, a.x + a.w - CORNER));
    return [[x, a.y + a.h], [x, a.y + a.h], [x, b.y], [x, b.y]];
  }
  const back = b.x + b.w / 2 < a.x + a.w / 2, way = back ? -1 : 1;
  const x0 = back ? a.x : a.x + a.w, x1 = back ? b.x + b.w : b.x;
  const y0 = a.y + a.h / 2 + ((k % PORTS) - (PORTS - 1) / 2) * SPREAD, y1 = b.y + b.h / 2;
  const handle = way * Math.min(HANDLE, Math.max(Math.abs(x1 - x0) / 2, SHORT));
  return [[x0, y0], [x0 + handle, y0], [x1 - handle, y1], [x1, y1]];
}

/** Which of a node's PORTS its I-th edge of N (in their targets' order, top first) leaves from, edgePath()'s K: one
 * alone the middle, a few round it, many spread over them all. @param {number} n @param {number} i */
export const portOf = (n, i) => (n > PORTS ? Math.round((i * (PORTS - 1)) / (n - 1))
  : i + Math.floor((PORTS - n) / 2));

/** The point at T (0 to 1) of the cubic PATH. @param {Path} path @param {number} t @returns {[number, number]} */
function pointAt([p0, p1, p2, p3], t) {
  const u = 1 - t, a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t;
  return [a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]];
}

/** Where a gate stands on its edge PATH: GATE of its length along (agent-graph.html's 55%), in whole px.
 * @param {Path} path @returns {Point} */
export function gateAt(path) {
  const points = Array.from({ length: STEPS + 1 }, (_, n) => pointAt(path, n / STEPS));
  const lengths = points.slice(1).map((p, n) => Math.hypot(p[0] - points[n][0], p[1] - points[n][1]));
  let left = lengths.reduce((sum, one) => sum + one, 0) * GATE;
  for (const [n, piece] of lengths.entries()) {
    if (left <= piece || n === lengths.length - 1) {
      const share = piece ? Math.min(1, left / piece) : 0, [from, to] = [points[n], points[n + 1]];
      return { x: Math.round(from[0] + (to[0] - from[0]) * share), y: Math.round(from[1] + (to[1] - from[1]) * share) };
    }
    left -= piece;
  }
  return { x: Math.round(path[0][0]), y: Math.round(path[0][1]) };
}

/** Where DRAG's node ({from: the pointer as pressed, at: the node then}) stands with the pointer at POINT: as far on
 * the screen at ZOOM as the pointer went, never past the canvas's corner; null while the press has not moved SHAKE
 * (still a click). @param {{ from: Point, at: Point }} drag @param {Point} point @param {number} [zoom] */
export function dragTo(drag, point, zoom = 1) {
  const dx = point.x - drag.from.x, dy = point.y - drag.from.y;
  return Math.hypot(dx, dy) < SHAKE ? null : { x: Math.max(0, Math.round(drag.at.x + unzoomed(dx, zoom))),
    y: Math.max(0, Math.round(drag.at.y + unzoomed(dy, zoom))) };
}

/** A graph's key in the kept places: its space, folder and agent. @param {string} space @param {string} folder
 * @param {string} agent */
export const layoutKey = (space, folder, agent) => `${space}|${folder}|${agent}`;

/** @param {any} kept @returns {Record<string, Record<string, Point>>} */
const places = (kept) => (kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {});

/** KEPT ({key: {node: {x, y}}}) with the dragged nodes' POSITIONS added under KEY, in whole px; the graphs of spaces
 * no longer LIVE left out. @param {any} kept @param {string} key @param {Record<string, Point>} positions
 * @param {Set<string>} live */
export function keepLayout(kept, key, positions, live) {
  const was = Object.fromEntries(Object.entries(places(kept)).filter(([id]) => live.has(id.split("|")[0])));
  return { ...was, [key]: { ...(was[key] ?? {}), ...Object.fromEntries(Object.entries(positions)
    .map(([id, at]) => [id, { x: Math.round(at.x), y: Math.round(at.y) }])) } };
}

/** KEPT without KEY's places: its graph laid out again. @param {any} kept @param {string} key */
export const dropLayout = (kept, key) => Object.fromEntries(Object.entries(places(kept))
  .filter(([id]) => id !== key));

/** Where NODES stand: a dragged one where KEPT has it under KEY, every other (a new one too) where layout() puts it;
 * a kept place of a node gone is not drawn. @param {any} kept @param {string} key @param {Node[]} nodes
 * @param {{ width: number, height: number }} size @param {Record<string, Size>} [sizes] @param {number} [room] */
export function placed(kept, key, nodes, size, sizes = {}, room = USES_ROOM, least = room) {
  const mine = places(kept)[key] ?? {}, at = layout(nodes, size, sizes, room, least);
  for (const one of nodes) {
    const was = mine[one.id];
    if (Number.isFinite(was?.x) && Number.isFinite(was?.y)) at[one.id] = { x: was.x, y: was.y };
  }
  return at;
}

/** The node an arrow KEY (up, down, left, right) steps to from CHOSEN among BOXES: the nearest that way, one off to
 * the side counting double; CHOSEN where there is none; with none chosen, the agent. @param {Record<string, Box>} all
 * @param {string | null} chosen @param {string} key @returns {string | null} */
export function stepNode(all, chosen, key) {
  const from = chosen ? all[chosen] : null;
  if (!from) return AGENT in all ? AGENT : Object.keys(all)[0] ?? null;
  const [dx, dy] = /** @type {Record<string, number[]>} */ ({ up: [0, -1], down: [0, 1], left: [-1, 0],
    right: [1, 0] })[key] ?? [0, 0];
  let best = chosen, least = Infinity;
  for (const [id, box] of Object.entries(all)) {
    const x = box.x + box.w / 2 - (from.x + from.w / 2), y = box.y + box.h / 2 - (from.y + from.h / 2);
    const along = x * dx + y * dy, aside = Math.abs(x * dy) + Math.abs(y * dx);
    if (id !== chosen && along > 0 && aside <= 2 * along && along + 2 * aside < least) {
      [best, least] = [id, along + 2 * aside];
    }
  }
  return best;
}

/** NODE's properties in VIEW: what it ran, where This chat tells them (an agent's cost lines, a tool's
 * calls), else its setup's. @param {Node} node @param {string} [view] */
export const propertiesOf = (node, view = "wiring") => (view === "run" && node.run?.properties) || node.properties;

/** NODE's Show in Agent in VIEW (core's action "agent"): its label and the Agent panel's ROW it leads to, by core's
 * id (null: the agent's own node, its panel); null where the panel has no row of it. @param {Node} node
 * @param {string} [view] @returns {{ label: string, row: string | null } | null} */
export function shownInAgent(node, view = "wiring") {
  const one = (propertiesOf(node, view)?.actions ?? []).find((/** @type {any} */ act) => act.id === "agent");
  return one ? { label: String(one.label), row: typeof one.row === "string" ? one.row : null } : null;
}

/** NODE's lines as the inspector draws them in VIEW: a folded node's names as a LIST (each with its source or its
 * gates); else its properties' lines but what its title says (its name, its state), as the Agent panel's.
 * @param {Node} node @param {string} [view] @returns {{ list: boolean, lines: [string, string, string | null][] }} */
export function nodeLines(node, view = "wiring") {
  const props = propertiesOf(node, view), lines = props?.lines ?? [];
  if (LISTS.includes(node.kind)) return { list: true, lines };
  const titled = [props?.title, props?.state?.text];
  return { list: false, lines: lines.filter(([, value]) => !titled.includes(value)) };
}

/** The node the Agent panel's ROW is in NODES: its own (a row's id is its node's), else the fold that holds it; null.
 * @param {Node[]} nodes @param {string | null | undefined} row */
export function nodeFor(nodes, row) {
  if (!row) return null;
  const fold = FOLDS[row.split(":")[0]];
  return nodes.some((one) => one.id === row) ? row : nodes.some((one) => one.id === fold) ? fold : null;
}

/** An edge's color in theme T by its STYLE: always and on demand the faint line, waiting yellow, failed red; each
 * moved toward the text until it is seen 3:1 on the canvas's surface. @param {Record<string, string>} t
 * @param {string} style */
export function wireColor(t, style) {
  const color = style === "failed" ? t.ansi1 : style === "waiting" ? t.ansi3 : t.dim;
  if (![color, t.foreground, t.surface].every((hex) => HEX.test(hex ?? ""))) return color;
  for (let tenth = 0; tenth < 10; tenth += 1) {
    const made = mixColor(color, t.foreground, tenth / 10);
    if (contrast(made, t.surface) >= SEEN) return made;
  }
  return t.foreground;
}

/** GRAPH (core's) as VIEW draws it: Wiring folds the tools a chat alone called (folded()), This chat keeps each, as
 * every one of them ran. @template {{ nodes: any[], edges: any[] }} G @param {G} graph
 * @param {string} view @returns {G} */
export const seen = (graph, view) => (view === "run" ? graph : folded(graph));

/** Whether NODE stands at half strength in VIEW: one that does not run here, and in This chat one that did not run
 * in it. @param {Node} node @param {string} view */
export const faded = (node, view) => Boolean(node.dim || (view === "run" && node.run && !node.run.ran));

/** What NODE shows in VIEW besides its title: its line, and at its top right its source's tag (a word) or what This
 * chat says of it ({text, tone}: sign in, failed), or there its cost (with its model's color and its share) or its
 * calls; ORDER: its first use's number there. @param {Node} node @param {string} view */
export function nodeShown(node, view) {
  const ran = view === "run" ? node.run : null, top = Boolean(ran?.cost || ran?.calls);
  return { sub: ran?.sub ?? node.sub, tag: top ? null : ran?.tag ?? node.tag, calls: ran?.calls ?? null,
    cost: ran?.cost ?? null, color: ran?.cost ? ran.model?.color ?? null : null,
    share: ran?.cost ? ran.share ?? null : null, order: ran?.order ?? null };
}

/** Where a first use's number stands on its node's BOX: its top left, the disc's centre on the box's top right
 * corner (agent-graph.html's .num). @param {Box} box @returns {Point} */
export const badgeAt = (box) => ({ x: box.x + box.w - DISC / 2, y: box.y - DISC / 2 });

/** A SHARE's bar on a track WIDTH px wide: its px, 2 at least where there is any, the track at most.
 * @param {number | null | undefined} share @param {number} width */
export const shareWidth = (share, width) => (share && share > 0 ? Math.min(width, Math.max(2, Math.round(share
  * width))) : 0);

/** How EDGE is drawn in VIEW: Wiring by its style (wireColor()); in This chat one that ran in the accent,
 * the running one wider, any other in its style's color at FAINT. KEY: the path it is drawn with.
 * @param {Record<string, string>} t @param {Edge} edge @param {string} view */
export function wireLook(t, edge, view) {
  const style = STYLES.includes(edge.style) ? edge.style : "demand", ran = view === "run" ? edge.run : null;
  if (ran?.running) return { key: "running", color: t.accent, width: RUNNING, dashed: false };
  if (ran?.ran) return { key: "ran", color: t.accent, width: RAN, dashed: false };
  return { key: view === "run" ? `${style}-faint` : style, width: WIRE, dashed: style !== "always",
    color: view === "run" ? `${wireColor(t, style)}${FAINT}` : wireColor(t, style) };
}

/** Whether anything in GRAPH runs now (a call with no answer yet): its view is read again sooner.
 * @param {{ edges: Edge[] }} graph */
export const running = (graph) => graph.edges.some((edge) => Boolean(edge.run?.running));

/** LEGEND (core's [style, word]) as VIEW shows it: "ran here" in This chat alone, where edges are lit.
 * @param {[string, string][]} legend @param {string} view */
export const legendOf = (legend, view) => legend.filter(([style]) => view === "run" || style !== "ran");

/** GRAPH's two views in core's words, the head's switch: This chat with the chat's whole after it once told.
 * @param {{ words: { views: Record<string, string> }, cost: string | null }} graph @returns {[string, string][]} */
export const viewWords = (graph) => VIEWS.map((view) => [view, view === "run" && graph.cost
  ? `${graph.words.views.run} · ${graph.cost}` : String(graph.words.views[view])]);
