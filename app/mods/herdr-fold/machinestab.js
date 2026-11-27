// @ts-check
// The main area's Machines tab, one a window (remote-machines-mockups/graph.html): how this Mac reaches its machines,
// core's graph (machine_graph.py over networks.py's look, on this Mac) on the Agents tab's canvas; graph.js its rules.
import { div, PathBuilder } from "gpui-kit";
import { h_flex, v_flex, Popover } from "gpui-base";
import { agents, exec, hc, home, panes, readTextFile, setShared, settings, shared, spaces, run as command }
  from "herdr";
import { mixColor } from "./agents.js";
import { boxes, dashOf, dragTo, dropLayout, edgePath, extent, GRAPH_LAYOUT, HEADS, keepLayout, labelAt, LABEL_HIGH,
  litEdges, MACHINES, MACHINES_ASK, machinesAsked, machinesLayout, machinesPlaced, machinesTab, measured, networkUnder,
  portOf, sizeOf, stepNode, unzoomed, wireColor, wireLook } from "./graph.js";
import { MACHINE_GRAPH, MACHINE_WORDS, NETWORKS } from "./helper.js";
import { toneInk } from "./layers.js";
import { appMachines, graphPipe, importCommand, lastLine, machineCommand, machineRuns, machinesKept, NOTE_MS, said,
  setupFolder } from "./logic.js";
import { panelSurface } from "./menus.js";
import { actButton, BUTTON, codeFont, icon, networkMark, PAD, viewId } from "./parts.js";
import { showInSpaces } from "./sidebar.js";

const POLL = 60000;                // ms between two looks while it shows a look with no login (none in the background)
const LOOK_MS = 90000;             // ms a look takes at most: each network's client 5 s, a route 2 s a machine
const CHECK_MS = 120000;           // ms the status check takes at most: a login to each machine, ssh's 10 s to connect
const GRID = 20;                   // px between two of the canvas's dots, agent-graph.html's
const RING = 2;                    // px: the chosen node's ring round it, a border (a dimmed node shows no fill)
const MOST = 300;                  // px: a node's width at most, its words cut past it
const LABELS = 320;                // px: the room an edge's label is centred in
const INSPECTOR = 300, LABEL = 70;         // px: the chosen node's properties, their labels' column (the Agents tab's)
// the properties at the canvas's lower left, as the Agents tab's (graph.html's .insp)
const MAC_TINT = 0.06, MAC_EDGE = "99";    // This Mac's node: the accent's 6% of a node, its edge at 60%, the agent's
const STATE_EDGE = /** @type {Record<string, [string, string]>} */ ({ bad: ["ansi1", "99"], warn: ["ansi3", "80"] });
// core's tones (machine_graph.py's words) as toneInk() reads them; text the text's own color
const TONES = /** @type {Record<string, string>} */ ({ muted: "muted", warn: "warn", ok: "allow", bad: "bad" });
const PAINTED = ["standby", "always", "demand", "failed"];       // the edges drawn in this order: the faint ones first
const LIT = 2;                     // px: the chosen machine's route in use, in the accent over the others (.lit)
const LIST_FILE = ".config/herdr-fold/machines.txt", SETUP_FILE = ".config/herdr-fold/setup-folder";
const LOADING = "Loading machines…", FAILED = "Couldn't read the machines";       // the TUI view's words
const NO_PACKAGE = "herdr-fold's package is not found here: this comes with herdr-fold's installer";
const REFRESH_TIP = "Log in to each machine to see how it answers, two minutes at most";
const SHOW = "Show in Spaces", COPY = "Copy", COPIED = "Copied", MORE = "More";

/** @typedef {import("./graph.js").Node & { parts?: [string, string][], network?: string | null }} Node */
/** @typedef {import("./graph.js").Box} Box */

/** The app's zoom now: what is set is drawn that many times as large, what is measured is the window's own px. */
const zoom = () => Number(settings().zoom ?? 1);

/** PATH (a PathBuilder's) painted over the whole canvas in COLOR. @param {any} path @param {string} color */
const painted = (path, color) => window.paint_path(path.build(), color).absolute().top_0().left_0().size_full();

/** A time core told (seconds since the epoch) as this Mac's clock says it: 9:14. @param {number} seconds */
const clock = (seconds) => {
  const at = new Date(seconds * 1000);
  return `${at.getHours()}:${String(at.getMinutes()).padStart(2, "0")}`;
};

/** A remove's question, the TUI view's words. @param {string} name */
const removeAsk = (name) => `Take ${name} off the list, and herdr-fold off it?`;

export class MachinesView {
  /** HERE gives this Mac's Python (main.js's, asked once). @param {() => Promise<string>} here */
  constructor(here, cx) {
    this.here = here;
    /** @type {any} core's graph; null: not read yet */
    this.found = null;
    /** @type {string | null} why the last look failed */
    this.error = null;
    this.busy = false;                            // a look on its way
    this.checking = false;                        // ... and it logs in to each machine (Refresh)
    this.logged = false;                          // the graph shown is the status check's, kept till the next one
    /** the canvas's frame as last measured, and each node's own size: in px as set (graph.js's unzoomed()) */
    this.size = { width: 0, height: 0 };
    /** @type {Record<string, import("./graph.js").Size>} */
    this.sizes = {};
    /** @type {{ id: string, from: import("./graph.js").Point, at: import("./graph.js").Point,
     * to: import("./graph.js").Point | null } | null} the node pressed: where, and where it is dragged to */
    this.drag = null;
    /** @type {string | null} the chosen node's id: its properties at the canvas's lower left */
    this.chosen = null;
    /** @type {number | null} the last ask answered (openMachines()'s), by its time */
    this.answered = null;
    /** @type {string | null} the node an ask wants chosen, once the graph has it */
    this.wants = null;
    /** @type {string | null} the machine Remove asks about, in the properties */
    this.removing = null;
    this.copiedAt = 0;                            // when a command went on the clipboard: Copied, a moment
    /** @type {string | null} the package's folder with its machines.sh: the actions' (none: they wait for it) */
    this.folder = null;
    this.menuOpen = false;                        // ⋯'s menu, Look around from here
    this.focus = cx.focus_handle();               // the canvas's: the arrows step its nodes
    this.still = false;                           // the styleguide's: nothing pressed, no place kept
    cx.timer.after(0, (/** @type {any} */ cx) => this.look(false, cx));
    cx.timer.every(POLL, (/** @type {any} */ cx) => void (this.shows() && !this.logged && this.look(false, cx)));
  }

  /** Whether the tab shows now: its space the shown one, its tab the space's shown one. */
  shows() {
    const at = machinesTab(spaces(), panes());
    return Boolean(at?.space.active && at.tab.active);
  }

  /** The networks looked at on this Mac and drawn by core: the list and the app's own machines, what runs on each, the
   * machines herdr keeps; LOGIN, a login to each (the status check, on a press alone). One at a time. */
  look(login, cx) {
    if (this.busy) return;
    Object.assign(this, { busy: true, checking: login });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const listed = await hc(["machine", "ls", "--json"]);
        const app = listed.code === 0 ? JSON.parse(listed.stdout) : null;
        const setup = setupFolder(await readTextFile(`${home()}/${SETUP_FILE}`));
        const folder = setup && await readTextFile(`${setup}/machines.sh`) ? setup : null;
        const given = /** @type {[string, string, string]} */ ([JSON.stringify(MACHINE_WORDS),
          `--runs=${JSON.stringify(machineRuns(spaces(), agents()))}`, `--kept=${JSON.stringify(machinesKept(app))}`]);
        const [name, args] = graphPipe(await this.here(), MACHINE_GRAPH, given, NETWORKS, [`${home()}/${LIST_FILE}`,
          ...(login ? ["--login"] : []), ...appMachines(app).flat()]);
        const done = await exec(name, args, { cwd: home(), timeout: login ? CHECK_MS : LOOK_MS });
        if (done.code !== 0) throw new Error(lastLine(done) || `exit ${done.code}`);
        Object.assign(this, { found: JSON.parse(done.stdout), error: null, logged: login, folder });
      } catch (e) {
        this.error = said(e);
      } finally {
        Object.assign(this, { busy: false, checking: false });
        cx.notify();
      }
    });
  }

  /** Refresh, or a node's Check again: the status check (a login to each machine), or again as the graph shown was
   * looked at. @param {boolean} login */
  check(login, cx) {
    if (this.still) return;
    this.look(login, cx);
    cx.notify();
  }

  render(t, cx) {
    const ask = machinesAsked(shared(MACHINES_ASK), this.answered, Date.now());
    if (ask) Object.assign(this, { answered: ask.at, wants: ask.node, chosen: ask.node ? this.chosen : null });
    if (this.wants && this.found) {
      if (this.found.nodes.some((/** @type {Node} */ one) => one.id === this.wants)) this.chosen = this.wants;
      this.wants = null;
    }
    return this.draw(t);
  }

  /** The tab: the canvas with the graph, Refresh at its top left, the legend at its right, the chosen node's
   * properties at its lower left; in the graph's place what it says instead (loading, the look's failure). */
  draw(t) {
    const frame = div().id("machines").relative().size_full().min_h(0).overflow_hidden().bg(t.surface)
      .text_color(t.foreground).text_size(13);
    if (this.found) return frame.child(this.canvas(t, this.found));
    return frame.child(this.dots(t, { width: 2400, height: 1600 })).child(this.tools(t, null))
      .child(div().absolute().top(HEADS).left(PAD).text_size(12)
        .text_color(this.error ? toneInk(t, "bad") : t.muted)
        .child(this.error ? `${FAILED}: ${this.error}` : LOADING));
  }

  /** GRAPH on the canvas (graph.html's): a grid of dots, scrolled where the graph needs more room; the edges under the
   * nodes, their labels over them; a node drags, a double click beside them lays them out again. @param {any} graph */
  canvas(t, graph) {
    /** @type {Node[]} */
    const nodes = graph.nodes, size = this.size;
    const at = machinesPlaced(this.still ? null : shared(GRAPH_LAYOUT), nodes, graph.edges, size, this.sizes);
    if (this.drag?.to) at[this.drag.id] = this.drag.to;
    const all = boxes(nodes, at, this.sizes), room = extent(all, size);
    const chosen = nodes.find((one) => one.id === this.chosen) ?? null, top = this.drag?.id ?? this.chosen;
    const { wires, labels } = this.wires(t, graph.edges, all);
    const content = div().id("machines-content").relative().w(room.width).h(room.height)
      .when(!this.still, (e) => e.on_mouse_down("left", (/** @type {any} */ e, /** @type {any} */ cx) =>
        this.pressed(e, cx)))
      .child(this.dots(t, room)).children(wires)
      .children(this.heads(t, graph.words.columns, nodes, boxes(nodes, machinesLayout(nodes, graph.edges, size,
        this.sizes), this.sizes)))
      .children([...nodes.filter((one) => one.id !== top), ...nodes.filter((one) => one.id === top)]
        .map((one) => this.node(t, one, all[one.id])))
      .children(labels);
    return div().id("machines-frame").relative().size_full().overflow_hidden()
      .when(!this.still, (e) => e.track_focus(this.focus)
        .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => this.keyed(e, cx, all))
        .on_mouse_move((/** @type {any} */ e, /** @type {any} */ cx) => this.moved(e, cx))
        .on_mouse_up("left", (/** @type {any} */ _e, /** @type {any} */ cx) => this.drop(true, cx))
        .on_hover((/** @type {boolean} */ over, /** @type {any} */ cx) => void (!over && this.drop(false, cx))))
      .child(div().id(`machines-canvas-${viewId(this)}`).size_full().overflow_scrollbar()
        .on_size_change((/** @type {{ width: number, height: number }} */ now, /** @type {any} */ cx) => {
          const width = unzoomed(now.width, zoom()), height = unzoomed(now.height, zoom());
          if (width === size.width && height === size.height) return;
          this.size = { width, height };
          cx.notify();
        })
        .when(size.width > 0, (e) => e.child(content)))
      .child(this.tools(t, graph))
      .child(this.legend(t, graph.words.legend))
      .when(Boolean(chosen), (e) => e.child(this.inspector(t, /** @type {Node} */ (chosen), graph)));
  }

  /** The canvas's dots, GRID apart (.canvasbox's): one dashed path, the text's color at 5%.
   * @param {{ width: number, height: number }} room */
  dots(t, room) {
    let path = PathBuilder.stroke(2).dash_array([2, GRID - 2]);
    for (let y = GRID / 2; y < room.height; y += GRID) path = path.move_to(GRID / 2, y).line_to(room.width, y);
    return painted(path, `${t.foreground}0d`);
  }

  /** EDGES between the boxes ALL (wireLook()'s, a standby route dotted and faint; the chosen machine's route in use lit
   * in the accent), a node's edges leaving it in their targets' order, each one's label at its middle.
   * @param {any[]} edges @param {Record<string, Box>} all */
  wires(t, edges, all) {
    const lit = litEdges(edges, this.chosen);
    /** @type {Map<string, any[]>} */
    const out = new Map();
    for (const edge of edges) {
      if (all[edge.from] && all[edge.to]) out.set(edge.from, [...(out.get(edge.from) ?? []), edge]);
    }
    /** @type {Record<string, { path: any, color: string }>} */
    const paths = {};
    const labels = [];
    const middle = (/** @type {string} */ id) => all[id].y + all[id].h / 2;
    for (const list of out.values()) {
      list.sort((a, b) => middle(a.to) - middle(b.to));
      for (const [n, edge] of list.entries()) {
        const path = edgePath(all[edge.from], all[edge.to], portOf(list.length, n)), [from, a, b, to] = path;
        const look = wireLook(t, edge, "wiring"), drawn = lit.has(`${edge.from}>${edge.to}`) ? { ...look,
          key: `lit-${look.key}`, color: t.accent, width: LIT } : look, was = paths[drawn.key]?.path ?? (drawn.dashed
          ? PathBuilder.stroke(drawn.width).dash_array(dashOf(drawn.key)) : PathBuilder.stroke(drawn.width));
        paths[drawn.key] = { color: drawn.color, path: was.move_to(from[0], from[1])
          .cubic_bezier_to(to[0], to[1], a[0], a[1], b[0], b[1]) };
        if (edge.label) labels.push(this.label(t, labelAt(path), String(edge.label)));
      }
    }
    const rank = (/** @type {string} */ key) => (key.startsWith("lit") ? PAINTED.length : PAINTED.indexOf(key));
    const order = Object.keys(paths).sort((a, b) => rank(a) - rank(b));
    return { wires: order.map((key) => painted(paths[key].path, paths[key].color)), labels };
  }

  /** An edge's label at AT (graph.html's .lab): the way and the time, a pill as a gate's, muted, centred on the edge.
   * @param {import("./graph.js").Point} at @param {string} text */
  label(t, at, text) {
    return div().absolute().left(at.x - LABELS / 2).top(at.y - LABEL_HIGH / 2).w(LABELS).flex().justify_center()
      .child(div().h(LABEL_HIGH).flex_none().px(6).flex().items_center().rounded(4).border_1().border_color(t.border)
        .bg(t.canvas).text_size(11).line_height("16px").whitespace_nowrap().text_color(t.muted).child(text));
  }

  /** The columns' names (.cols), 11 muted, HEADS down, each over its column's left edge as laid out (LAID).
   * @param {Record<string, string>} words @param {Node[]} nodes @param {Record<string, Box>} laid */
  heads(t, words, nodes, laid) {
    return ["mac", "networks", "machines", "through"].flatMap((column) => {
      const first = nodes.find((one) => one.column === column && laid[one.id]);
      return first ? [div().absolute().top(HEADS).left(laid[first.id].x).text_size(11).line_height("16px")
        .text_color(t.muted).child(String(words[column] ?? ""))] : [];
    });
  }

  /** Refresh at the canvas's top left (graph.html's .tools): the status check, a login to each machine; Checking… while
   * it runs; its tip when the graph was looked at; a look that failed, why, beside it. @param {any} graph */
  tools(t, graph) {
    const tip = graph?.checked ? `${REFRESH_TIP}\nChecked ${clock(graph.checked)}${this.logged
      ? ", with a login to each" : ""}` : REFRESH_TIP;
    return h_flex().absolute().top(PAD).left(PAD).h(BUTTON).gap(PAD).items_center().text_size(12)
      .child(actButton(t, "machines-refresh", this.checking ? "Checking…" : "Refresh", "raised", !this.busy,
        (/** @type {any} */ cx) => this.check(true, cx), tip))
      .when(Boolean(graph && this.error), (e) => e.child(div().id("machines-failed").max_w(INSPECTOR).truncate()
        .text_color(toneInk(t, "bad")).tooltip(String(this.error)).child(`${FAILED}: ${this.error}`)));
  }

  /** The legend at the canvas's top right (.legend), the Agents tab's: each kind of edge's sample and its word, 11
   * muted, on the nodes' level at 90%; a standby route's dotted and faint. @param {[string, string][]} legend */
  legend(t, legend) {
    const sample = (/** @type {string} */ style) => {
      const drawn = wireLook(t, { from: "", to: "", style, gates: [], run: null }, "wiring");
      const [piece] = dashOf(drawn.key);                  // dashes 5 or dots 2, 4 apart: 22 wide
      return drawn.dashed ? h_flex().gap(4).children(Array.from({ length: piece < 5 ? 4 : 3 },
        () => div().w(piece).h(2).bg(drawn.color))) : div().w(22).h(2).bg(drawn.color);
    };
    return h_flex().absolute().top(PAD).right(PAD).h(BUTTON).px(PAD).gap(PAD).items_center().rounded(8).border_1()
      .border_color(t.border).bg(`${t.chrome}e6`).text_size(11).text_color(t.muted)
      .children(legend.map(([style, word]) => h_flex().gap(6).items_center().child(sample(style)).child(word)));
  }

  /** NODE's mark, 14: This Mac's monitor, a network's (parts.js's networkMark), a machine's server, muted.
   * @param {Node} node */
  mark(t, node, size = 14) {
    return node.kind === "network" ? networkMark(t, node.network, size)
      : icon(node.kind === "mac" ? "monitor" : "server", size).text_color(t.muted);
  }

  /** PARTS ([[words, tone]], core's) side by side in their tones on GROUND, BASE for the text's own.
   * @param {[string, string][]} parts @param {string} ground @param {string} base */
  words(t, parts, ground, base) {
    return parts.map(([words, tone]) => div().flex_none().whitespace_nowrap()
      .text_color(TONES[tone] ? toneInk(t, TONES[tone], ground) : base).child(words));
  }

  /** NODE at BOX (graph.html's .node, the Agents tab's): This Mac on the accent's tint, a state's edge (away red, a
   * network to act on yellow), its tag at its top right (a system, a network's state), its line in core's tones; half
   * strength while its network is not on. A press chooses it, a drag moves it. @param {Node} node @param {Box} box */
  node(t, node, box) {
    const mac = node.kind === "mac", chosen = node.id === this.chosen, [color, alpha] = STATE_EDGE[node.state ?? ""]
      ?? [];
    const ground = mac ? mixColor(t.chrome, t.accent, MAC_TINT) : t.chrome, mark = this.mark(t, node);
    const edge = color ? `${t[color]}${alpha}` : mac ? `${t.accent}${MAC_EDGE}` : wireColor(t, "always");
    const tagInk = node.kind === "network" && node.state === "warn" ? toneInk(t, "warn", ground) : t.muted;
    const parts = node.parts?.length ? node.parts : node.sub ? [[node.sub, "muted"]] : [];
    const card = v_flex().id(`machines-node-${viewId(this)}-${node.id}`).min_w(sizeOf(node).w).max_w(MOST).py(8)
      .px(PAD).rounded(10).border_1().border_color(edge).bg(ground).shadow_md()
      .on_size_change((/** @type {{ width: number, height: number }} */ size, /** @type {any} */ cx) => {
        const { w, h } = measured(size, zoom()), was = this.sizes[node.id];
        if (was?.w === w && was?.h === h) return;
        this.sizes = { ...this.sizes, [node.id]: { w, h } };
        cx.notify();
      })
      .child(h_flex().h(18).gap(6).items_center().when(Boolean(mark), (e) => e.child(mark))
        .child(div().min_w(0).truncate().text_size(12).font_semibold().child(node.title))
        .when(Boolean(node.tag), (e) => e.child(div().flex_1().min_w(PAD)).child(div().flex_none().text_size(11)
          .text_color(tagInk).child(String(node.tag)))))
      .when(parts.length > 0, (e) => e.child(h_flex().h(16).mt(2).min_w(0).overflow_hidden().text_size(11)
        .line_height("16px").children(this.words(t, /** @type {[string, string][]} */ (parts), ground, t.muted))));
    return div().absolute().left(box.x - RING).top(box.y - RING).rounded(10).border_2()        // RING: its 2 px
      .border_color(chosen ? t.accent : `${t.accent}00`)
      .child((this.still ? card : card.when(this.drag?.id === node.id, (e) => e.cursor_grabbing())
        .when(this.drag?.id !== node.id, (e) => e.cursor_grab())
        .on_mouse_down("left", (/** @type {any} */ e, /** @type {any} */ cx) => this.grab(node, { x: box.x,
          y: box.y }, e, cx))).when(node.dim, (e) => e.opacity(0.5)));
  }

  /** The chosen NODE's properties at the canvas's lower left, as the Agents tab's (graph.html's .insp): its title
   * with its state and ×, why it is away and what to do (a command with Copy), its lines as core gives them (label
   * left, value right), its actions. @param {Node} node @param {any} graph */
  inspector(t, node, graph) {
    const props = node.properties ?? {}, ground = t.popover ?? t.raised, state = props.state ?? null;
    const lines = /** @type {any[]} */ (props.lines ?? []), why = /** @type {any[]} */ (props.why ?? []);
    const buttons = this.buttons(t, node, props, graph), mark = this.mark(t, node);
    const bare = !lines.length && !why.length && !buttons && Boolean(node.sub);
    return v_flex().id("machines-inspector").absolute().left(PAD).bottom(PAD).w(INSPECTOR).p(PAD).gap(6).rounded(10)
      .border_1().border_color(t.border).bg(ground).shadow_lg().text_size(12)
      .on_mouse_down("left", (/** @type {any} */ _e, /** @type {any} */ cx) => cx.stop_propagation())
      .child(h_flex().h(20).flex_none().gap(8).items_center()
        .when(Boolean(mark), (e) => e.child(mark))
        .child(div().flex_1().min_w(0).truncate().font_semibold().child(props.title ?? node.title))
        .when(Boolean(state), (e) => e.child(div().flex_none().text_size(11)
          .text_color(TONES[state?.tone ?? ""] ? toneInk(t, TONES[state.tone], ground) : t.foreground)
          .child(state?.text ?? "")))
        .child(div().id("machines-inspector-close").size(16).flex_none().flex().items_center().justify_center()
          .rounded(4).text_color(t.dim).cursor_pointer().tooltip("Close")
          .hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(null, cx)).child(icon("x", 12))))
      .when(bare, (e) => e.child(div().text_color(t.muted).child(String(node.sub))))
      .when(why.length > 0, (e) => e.child(this.why(t, why, ground)))
      .when(lines.length > 0, (e) => e.child(v_flex().flex_none().children(lines.map((line, n) => this.line(t,
        line, n, node, graph)))))
      .when(Boolean(buttons), (e) => e.child(buttons));
  }

  /** WHY's lines (core's): the sentence in yellow, wrapping; then each line after it muted, one with a command in its
   * box (graph.html's .cmd): its words, the command in the code font, Copy at its end. @param {any[]} why
   * @param {string} ground */
  why(t, why, ground) {
    const code = codeFont(), copied = Date.now() - this.copiedAt < NOTE_MS;
    return v_flex().flex_none().gap(6).children(why.map((/** @type {[string, string][]} */ line, n) => {
      const command = line.find(([, tone]) => tone === "text")?.[0] ?? null;
      const said = line.filter(([, tone]) => tone !== "text").map(([words]) => words).join("").trim();
      if (!n) return div().text_color(toneInk(t, "warn", ground)).child(said);
      if (!command) return div().text_color(t.muted).child(said);
      return h_flex().id(`machines-command-${n}`).min_h(BUTTON).flex_none().px(8).gap(6).items_center().rounded(6)
        .border_1().border_color(t.border).bg(t.canvas)
        .when(Boolean(said), (e) => e.child(div().flex_none().text_color(t.muted).child(said)))
        .child(div().flex_1().min_w(0).truncate().font_family(code).text_size(11).child(command))
        .child(div().id(`machines-copy-${n}`).flex_none().text_color(copied ? t.foreground : t.muted)
          .when(!this.still, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.text_color(t.foreground))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.copy(command, cx)))
          .child(copied ? COPIED : COPY));
    }));
  }

  /** A properties LINE (core's [label, parts, right, mark]), 20 high: its label muted in LABEL, a route's network mark
   * before its value, a fingerprint in the code font, the way behind another with its network's mark, what it says at
   * its right at the end. @param {any[]} line @param {number} n @param {Node} node @param {any} graph */
  line(t, [label, parts, right, mark], n, node, graph) {
    const ground = t.popover ?? t.raised, said = parts.map((/** @type {[string, string]} */ one) => one[0]).join("");
    const value = label === "Key" ? [div().min_w(0).truncate().font_family(codeFont()).text_size(11).child(said)]
      : label === "Path" ? this.path(t, said, networkUnder(graph.nodes, node.id))
        : parts.length === 1 ? [div().min_w(0).truncate().text_color(TONES[parts[0][1]] ? toneInk(t,
          TONES[parts[0][1]], ground) : t.foreground).child(said)] : this.words(t, parts, ground, t.foreground);
    const marked = mark ? networkMark(t, mark, 12) ?? (mark === "through" ? icon("corner-down-right", 12)
      .text_color(t.muted) : null) : null;
    return h_flex().id(`machines-property-${n}`).min_h(20).flex_none().gap(8).items_start().line_height("20px")
      .child(div().w(LABEL).flex_none().truncate().text_color(t.muted).child(label))
      .child(h_flex().flex_1().min_w(0).gap(6).items_center().when(Boolean(marked), (e) => e.child(marked))
        .child(h_flex().min_w(0).flex_wrap().items_center().children(value)))
      .when(right.length > 0, (e) => e.child(h_flex().flex_none().text_size(11)
        .children(this.words(t, right, ground, t.foreground))));
  }

  /** The way to a machine behind another (core's words: This Mac › Tailscale › lumen-api › build-01), each › dim, the
   * NETWORK's mark before its name. @param {string} words @param {string | null} network */
  path(t, words, network) {
    const name = network ? /** @type {Record<string, string>} */ (MACHINE_WORDS)[`machines.network_${network}`] : null;
    const parts = words.split(" › ");
    return parts.map((part, n) => h_flex().flex_none().gap(4).items_center()
      .when(part === name, (e) => e.child(networkMark(t, network, 12) ?? div())).child(part)
      .when(n < parts.length - 1, (e) => e.child(div().pr(4).text_color(t.dim).child("›"))));
  }

  /** NODE's buttons in one row (.ibtns), core's actions (PROPS'): Status, Set up again, Check again, machines to add
   * raised, Remove… plain, a machine's ⋯ (Show in Spaces, Look around from here…), the TUI view's row; those needing
   * machines.sh wait for it; Remove asks. @param {Node} node @param {any} props @param {any} graph */
  buttons(t, node, props, graph) {
    const machine = node.kind === "machine", name = String(node.title);
    const actions = /** @type {any[]} */ (props.actions ?? []).filter((one) => one.id !== "copy");
    if (machine && this.removing === name) {
      return v_flex().flex_none().pt(2).gap(6).child(div().text_color(toneInk(t, "bad", t.popover ?? t.raised))
        .child(removeAsk(name)))
        .child(h_flex().gap(6).child(actButton(t, "machines-remove-yes", "Remove", "raised", true,
          (/** @type {any} */ cx) => this.act("remove-yes", node, graph, cx)))
          .child(actButton(t, "machines-remove-no", "Cancel", "plain", true, (/** @type {any} */ cx) =>
            this.ask(null, cx))));
    }
    const shown = actions.filter((one) => one.id !== "through"), around = actions.find((one) => one.id === "through");
    const look = (/** @type {string} */ id) => (id === "remove" ? "plain" : "raised");
    const needs = (/** @type {string} */ id) => id !== "check";
    const buttons = shown.map((one) => [one.id, one.id === "remove" ? `${one.label}…` : one.label]);
    if (!buttons.length && !machine) return null;
    return h_flex().flex_none().pt(2).gap(6)
      .children(buttons.map(([id, label]) => {
        const usable = needs(id) ? Boolean(this.folder) : !(id === "check" && this.busy);
        return actButton(t, `machines-act-${id}`, label, look(id), usable, (/** @type {any} */ cx) => this.act(id,
          node, graph, cx), needs(id) && !this.folder ? NO_PACKAGE : null);
      }))
      .when(machine, (e) => e.child(this.more(t, node, around ? String(around.label) : null, graph)));
  }

  /** ⋯ after a machine's buttons, its menu over it: Show in Spaces, and Look around from here… (./machines.sh
   * through; LABEL, null where the machine cannot look around), as the TUI view's ⋯.
   * @param {Node} node @param {string | null} label @param {any} graph */
  more(t, node, label, graph) {
    const trigger = div().id("machines-more").size(BUTTON).flex_none().flex().items_center().justify_center()
      .rounded(8).text_color(t.muted).cursor_pointer().tooltip(MORE).when(this.menuOpen, (e) => e.bg(t.raised))
      .hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground)).child(icon("ellipsis", 14));
    if (this.still) return trigger;
    const row = (/** @type {string} */ id, /** @type {string} */ words, /** @type {boolean} */ usable,
      /** @type {() => void} */ press) => h_flex().id(`machines-${id}`).h(28).px(8).items_center().rounded(6)
      .text_size(13).text_color(usable ? t.foreground : t.dim).when(!usable, (e) => e.tooltip(NO_PACKAGE))
      .when(usable, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
          this.menuOpen = false;
          press();
          cx.notify();
        }))
      .child(words);
    return Popover.new("machines-more-menu").anchor("bottom_left").open(this.menuOpen)
      .on_open_change((/** @type {boolean} */ open, /** @type {any} */ cx) => {
        this.menuOpen = open;
        cx.notify();
      })
      .trigger(trigger).when(this.menuOpen, (/** @type {any} */ e) => e.content(panelSurface(t,
        "machines-more-surface", 220).mb(4).p(4).gap(2)
        .child(row("show", SHOW, true, () => this.act("show", node, graph)))
        .when(Boolean(label), (e) => e.child(row("through", String(label), Boolean(this.folder),
          () => this.act("through", node, graph))))));
  }

  /** Action ID on NODE: machines.sh in a terminal tab on this Mac (Remove asked first), a network's machines to add
   * asked about, Check again, Show in Spaces. @param {string} id @param {Node} node @param {any} graph */
  act(id, node, graph, cx = null) {
    const name = String(node.title), folder = this.folder;
    if (this.still) return;
    if (id === "remove") return void this.ask(name, cx);
    if (id === "check") return void (cx && this.check(this.logged, cx));
    if (id === "show") return void showInSpaces(name, networkUnder(graph.nodes, node.id));
    this.menuOpen = false;
    this.removing = null;
    if (!folder) return;
    const made = id === "add" ? importCommand(String(node.network), folder, spaces())
      : machineCommand(id === "remove-yes" ? "remove" : id, name, folder, spaces());
    if (made) command(made[0], made[1]);
    cx?.notify();
  }

  /** Remove's question about NAME in the properties (null: put away). @param {string | null} name */
  ask(name, cx) {
    if (this.still) return;
    this.removing = name;
    cx?.notify();
  }

  /** TEXT, a command, on the clipboard: Copied in Copy's place a moment. @param {string} text */
  copy(text, cx) {
    cx.write_to_clipboard(text);
    this.copiedAt = Date.now();
    cx.notify();
    cx.timer.after(NOTE_MS, (/** @type {any} */ cx) => cx.notify());
  }

  /** Node ID chosen (null: none), its properties at the canvas's lower left. @param {string | null} id */
  choose(id, cx) {
    if (id === this.chosen) return;
    Object.assign(this, { chosen: id, removing: null, menuOpen: false });
    cx.notify();
  }

  /** A press on the canvas beside the nodes: the keys its own, no node chosen; a double one lays the graph out again
   * (its kept places dropped). */
  pressed(e, cx) {
    this.focus.focus();
    const kept = /** @type {any} */ (shared(GRAPH_LAYOUT));
    if (e.click_count === 2 && kept?.[MACHINES]) setShared(GRAPH_LAYOUT, dropLayout(kept, MACHINES));
    this.choose(null, cx);
  }

  /** NODE pressed where it stands (AT): a drag may start. @param {Node} node @param {import("./graph.js").Point} at */
  grab(node, at, e, cx) {
    cx.stop_propagation();                        // the node's press, never the canvas's
    this.focus.focus();
    this.drag = { id: node.id, from: e.position, at, to: null };
  }

  /** The pointer at E while a node is pressed: the node follows it, its edges with it. */
  moved(e, cx) {
    const to = this.drag && dragTo(this.drag, e.position, zoom());
    if (!this.drag || !to || (to.x === this.drag.to?.x && to.y === this.drag.to?.y)) return;
    this.drag.to = to;
    cx.notify();
  }

  /** The press over: a node dragged is kept where it was let go (under MACHINES); one only pressed (CLICKED) chosen.
   * @param {boolean} clicked */
  drop(clicked, cx) {
    const drag = this.drag;
    if (!drag) return;
    this.drag = null;
    if (drag.to) {
      setShared(GRAPH_LAYOUT, keepLayout(shared(GRAPH_LAYOUT), MACHINES, { [drag.id]: drag.to },
        new Set(spaces().map((s) => s.id))));
    } else if (clicked) return void this.choose(drag.id, cx);
    cx.notify();
  }

  /** A key on the canvas: the arrows step to the nearest node that way, Esc puts the question, then the properties
   * away. @param {Record<string, Box>} all */
  keyed(e, cx, all) {
    if (e.key === "escape" && this.removing) this.ask(null, cx);
    else if (e.key === "escape" && this.chosen) this.choose(null, cx);
    else if (["up", "down", "left", "right"].includes(e.key)) this.choose(stepNode(all, this.chosen, e.key), cx);
    else return;
    cx.stop_propagation();
  }
}
