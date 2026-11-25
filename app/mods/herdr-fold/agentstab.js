// @ts-check
// The main area's Agents tab, one a space (usage.html's): Graph (Wiring, or This chat with its costs), Usage
// (usageview.js) and Runs (runsview.js). Core words the nodes and edges (graph.py, costs.py), graph.js has the rules.
import { div, PathBuilder } from "gpui-kit";
import { h_flex, v_flex, Popover } from "gpui-base";
import { panes, setShared, settings, shared, spaces } from "herdr";
import { agentMark, programs, watchSetup } from "./agent.js";
import { mixColor, panelStep, RECENT_AGENTS } from "./agents.js";
import { AGENT, AGENTS_ASK, agentsAsked, agentsTab, badgeAt, boxes, DISC, dragTo, dropLayout, EDGE, edgePath, extent,
  faded, gateAt, gatesRoom, GRAPH_LAYOUT, HEADS, keepLayout, layout, layoutKey, legendOf, nodeFor, nodeLines,
  measured, nodeShown, placed, portOf, propertiesOf, running, seen, shareWidth, shownInAgent, sizeOf, stepNode,
  unzoomed, viewWords, VIEWS, wireColor, wireLook } from "./graph.js";
import { AGENT_STATE, COSTS, GRAPH } from "./helper.js";
import { AGENT_CHOSEN, agentList, errorColors, graphAgent, keepAgent, NAMES, READ, tagWord, toneInk, usageAgents }
  from "./layers.js";
import { said } from "./logic.js";
import { listNote, panelRow, panelSurface } from "./menus.js";
import { openAgentPanel } from "./panel.js";
import { actButton, brandMark, BUTTON, codeFont, icon, PAD, propertyLine, scopeTag, segmented, swatch }
  from "./parts.js";
import { showPreview } from "./preview.js";
import { RunsView } from "./runsview.js";
import { UsageView } from "./usageview.js";

const POLL = 30000;                // ms between two reads while it shows, as the Agent panel's
const SLOW = 10;                   // a read no sooner than this many times what the last took (a long session's)
const GRID = 20;                   // px between two of the canvas's dots, agent-graph.html's
const QUICK = 5000;                // ms between two reads of This chat while something runs in it
const DASH = [5, 5];               // px: an on-demand, waiting or failed edge's dashes
const RUN_INSPECTOR = 340, RUN_LABEL = 82;         // px: This chat's properties (usage.html's .ginsp, .kv)
const PARTS = /** @type {[string, string][]} */ ([["graph", "Graph"], ["usage", "Usage"], ["runs", "Runs"]]);
const RING = 2;                    // px: the chosen node's ring round it
const MOST = 300;                  // px: a node's width at most, its words cut past it
const GATES = 320;                 // px: the room a gate's pills are centred in
const INSPECTOR = 300, LABEL = 70;         // px: the chosen node's properties, their labels' column (.insp, .kv)
const LISTED = 240;                // px: a folded node's names at most, scrolled past it
const LIST = 300;                  // px: the head's agents' list, the Agent panel's
const AGENT_TINT = 0.06, AGENT_EDGE = "99";        // the agent's node: the accent's 6% of a node, its edge at 60%
const STATE_EDGE = /** @type {Record<string, [string, string]>} */ ({ bad: ["ansi1", "99"], warn: ["ansi3", "80"] });
/** A node's icon by core's name for it, the In column's types told apart (a skill Lucide's scroll-text).
 * @type {Record<string, import("./icons.js").IconName>} */
const ICON = { file: "file", skill: "scroll-text", hook: "zap", bot: "bot", terminal: "terminal", wrench: "wrench" };

/** @typedef {import("./graph.js").Node} Node */
/** @typedef {import("./graph.js").Box} Box */
/** core/'s code run: its source, its arguments, where, on which machine. @template T @typedef {(source: string,
 * args: string[], root: string, on: string | null) => Promise<T>} Runner */
/** What draw() takes besides the view's own state: the agent shown, the app's programs (their icons), the spaces
 * Usage's scope lists, the tab's space (Runs' folder). @typedef {{ agent: string, programs: Record<string, any>,
 * scopes?: { name: string, folder: string }[], space?: any }} Look */

/** The app's zoom now: what is set (a place, a size, a path's point) is drawn that many times as large, what is
 * measured (on_size_change's, a pointer's) is the window's own px. */
const zoom = () => Number(settings().zoom ?? 1);

/** PATH (a PathBuilder's) painted over the whole canvas in COLOR. @param {any} path @param {string} color */
const painted = (path, color) => window.paint_path(path.build(), color).absolute().top_0().left_0().size_full();

// AgentsView instances drawn: each one's measured elements an id of its own, as the app keeps an element's last size
// by its id and tells a second canvas of the same size none (the styleguide's specimens, made without the
// constructor, drew empty); taken on its first canvas
let views = 0;

export class AgentsView {
  /** SPACE's Agents tab; CORE runs core/'s code (main.js's python), TEXT the same for what it prints (a CSV).
   * @param {string | null} space @param {Runner<any>} core @param {Runner<string>} text */
  constructor(space, core, cx, text) {
    this.space = space;
    this.core = core;
    /** @type {"graph" | "usage" | "runs"} the view shown, and the graph's own (Wiring, This chat) */
    this.view = "graph";
    this.mode = VIEWS[0];
    this.usage = new UsageView(core, text);
    this.runs = new RunsView(core, this.usage);           // the two share the agents' plans and the spaces' scope
    /** @type {{ surface: string, foreground: string } | null} the theme's card and text, as last drawn */
    this.theme = null;
    /** @type {string | null} what was asked for last: the agent, the folder and the chat, as JSON */
    this.key = null;
    this.agent = READ[0];
    /** @type {string | null} */
    this.folder = null;
    /** @type {string | null} the chat Show graph came from; null: the folder's newest */
    this.session = null;
    /** @type {any} core's graph; null: not read yet, or the agent is not installed (missing) */
    this.found = null;
    this.missing = false;
    /** @type {string | null} why the read failed, while nothing is shown */
    this.error = null;
    this.busy = false; this.again = false; this.readAt = 0; this.took = 0; this.waiting = false;
    /** the canvas's frame as last measured, and each node's own size: in px as set (graph.js's unzoomed()) */
    this.size = { width: 0, height: 0 };
    /** @type {Record<string, import("./graph.js").Size>} */
    this.sizes = {};
    /** @type {{ id: string, from: import("./graph.js").Point, at: import("./graph.js").Point,
     * to: import("./graph.js").Point | null } | null} the node pressed: where, and where it is dragged to */
    this.drag = null;
    /** @type {string | null} the chosen node's id: its properties at the canvas's foot */
    this.chosen = null;
    /** @type {number | null} the last ask answered (openAgents()'s), by its time */
    this.answered = null;
    /** @type {string | null} the row an ask wants chosen, once the graph is read */
    this.wants = null;
    /** @type {any[] | null} the agents on this Mac as core tells them, for the head's list; null: not yet */
    this.agents = null;
    /** @type {string | null} */
    this.agentsError = null;
    this.agentsBusy = false;
    this.listing = false;
    /** @type {number | null} the list's row the keys are on (menus.js's Lister) */
    this.cursor = null;
    this.listPlaces = []; this.listScroll = null;
    this.listFocus = cx.focus_handle();
    this.focus = cx.focus_handle();              // the canvas's: the arrows step its nodes
    this.still = false;                           // the styleguide's: nothing pressed, no place kept
    /** @type {Map<string, object>} the folders watched, each with its watch's token */
    this.watches = new Map();
    cx.timer.every(POLL, (/** @type {any} */ cx) => {
      if (!this.shows()) return;
      if (this.view === "usage") this.usage.bringUp(cx);
      else if (this.view === "graph" && this.due()) this.read(cx);
    });
    cx.timer.every(QUICK, (/** @type {any} */ cx) => {
      if (this.shows() && this.view === "runs") this.runs.follow(cx);      // it reads when due, sooner while one works
      else if (this.shows() && this.view === "graph" && this.mode === "run" && this.found && running(this.found)
        && Date.now() - this.readAt > Math.max(QUICK, SLOW * this.took)) this.read(cx);
    });
  }

  /** Whether the tab shows now: its space the shown one, its tab the space's shown one. */
  shows() {
    const space = spaces().find((s) => s.id === this.space);
    return Boolean(space?.active && agentsTab(space, panes())?.active);
  }

  /** Whether the last read is old: POLL, or SLOW times what it took (a long session is read in seconds). */
  due() {
    return Date.now() - this.readAt > Math.max(POLL, SLOW * this.took);
  }

  /** From render: AGENT in SPACE read once it is another agent, folder or chat than the last, or the last
   * read is old. @param {any} space @param {string} agent */
  follow(space, agent, cx) {
    const folder = space.machine ? null : space.folder || null;
    const key = JSON.stringify([agent, folder, this.session]);
    if (key !== this.key) {
      Object.assign(this, { key, agent, folder, found: null, missing: false, error: null, chosen: null, drag: null,
        sizes: {} });
      watchSetup(this, cx);
      this.read(cx);
    } else if (this.due()) this.read(cx);
  }

  /** What the chat SESSION cost, for This chat (costs.py, which reads on in the token index first;
   * the agents' plans tell value from spent, the theme's card and text carry the models' colors); null where it
   * cannot be told now. @param {string} agent @param {string} session @param {string} folder */
  async cost(agent, session, folder) {
    try {
      await this.usage.plans();
      return await this.core(COSTS, [agent, session, `--agents=${JSON.stringify(usageAgents(this.usage.agents))}`,
        ...(this.theme ? [`--surface=${this.theme.surface}`, `--text=${this.theme.foreground}`] : [])], folder, null);
    } catch {
      return null;                                // the graph still tells what ran, with no figures
    }
  }

  /** The graph read (one read at a time, once more after it when asked meanwhile): drawn anew where it changed, kept
   * where a read fails. This chat: its costs asked first (by the chat the last read told, so its
   * first read is made twice) and handed to core's graph. */
  read(cx) {
    if (!this.folder || !READ.includes(this.agent)) return;
    if (this.busy) return void (this.again = true);
    const { key, agent, folder, session, mode } = this, began = Date.now();
    Object.assign(this, { busy: true, readAt: began });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const asked = agent === "claude" && session ? [session] : [];
        const read = async (/** @type {string | null} */ of) => {
          const costs = mode === "run" && of ? await this.cost(agent, of, folder) : null;
          return [await this.core(GRAPH, [agent, folder, ...asked, ...(costs ? [`--costs=${JSON.stringify(costs)}`]
            : [])], folder, null), costs];
        };
        let [found, costs] = await read(this.found?.session ?? null);
        if (mode === "run" && found?.session && costs?.session !== found.session) {
          [found, costs] = await read(found.session);
        }
        if (key !== this.key) return;
        if (!this.error && this.missing === !found && JSON.stringify(found) === JSON.stringify(this.found)) return;
        Object.assign(this, { found, missing: !found, error: null });
        cx.notify();
      } catch (e) {
        if (key !== this.key || this.found) return;
        this.error = said(e);
        cx.notify();
      } finally {
        this.busy = false;
        this.took = Date.now() - began;
        if (this.again) {
          this.again = false;
          this.read(cx);
        }
      }
    });
  }

  /** The head's list shown or shut: the keys on no row till an arrow, the agents asked for as it opens.
   * @param {boolean} open */
  list(open, cx) {
    Object.assign(this, { listing: open, cursor: null, listPlaces: [] });
    if (open && !this.agentsBusy && this.folder) {
      const folder = this.folder;
      this.agentsBusy = true;
      cx.spawn(async (/** @type {any} */ cx) => {
        try {
          const agents = await this.core(AGENT_STATE, ["agents"], folder, null);
          Object.assign(this, { agents: Array.isArray(agents) ? agents : [], agentsError: null });
        } catch (e) {
          if (!this.agents) this.agentsError = said(e);
        } finally {
          this.agentsBusy = false;
          cx.notify();
        }
      });
    }
    cx.notify();
  }

  /** Agent KEY picked in the list: the space's agent from now on, the Agent panel's too. @param {string} key */
  pick(key, cx) {
    if (this.space) {
      setShared(AGENT_CHOSEN, keepAgent(shared(AGENT_CHOSEN), this.space, key, new Set(spaces().map((s) => s.id))));
    }
    this.list(false, cx);
  }

  /** A key in the open list: ↑ ↓ step its rows (from the one shown), Enter or Space picks, Esc shuts it.
   * @param {import("./layers.js").Listed[]} rows */
  listKey(e, cx, rows) {
    if (e.key === "escape") this.list(false, cx);
    else if (e.key === "up" || e.key === "down") {
      this.cursor = panelStep(rows.length, this.cursor, e.key === "down" ? 1 : -1, () => false,
        rows.findIndex((one) => one.check));
    } else if ((e.key === "enter" || e.key === "space") && this.cursor !== null && rows[this.cursor]) {
      this.pick(rows[this.cursor].key, cx);
    } else return;
    cx.stop_propagation();
    cx.notify();
  }

  /** The graph's view picked: Wiring, or This chat (read again with its costs). @param {string} mode */
  see(mode, cx) {
    if (mode === this.mode || !VIEWS.includes(mode)) return;
    Object.assign(this, { mode, chosen: null, drag: null });
    this.read(cx);
    cx.notify();
  }

  /** The tab's view picked: Graph, Usage or Runs. @param {string} view */
  show(view, cx) {
    this.view = view === "usage" || view === "runs" ? view : "graph";
    cx.notify();
  }

  /** Open in Usage: the Usage view with the chat SESSION's row marked. @param {string | null} session */
  showUsage(session, cx) {
    this.usage.ask(session);
    this.show("usage", cx);
  }

  /** Show in Agent: the dock's Agent panel as this graph's agent's, ROW (core's id, its node's) chosen and scrolled
   * to; null: the agent's own node, its panel as it stands. @param {string | null} row */
  showAgent(row) {
    if (!this.still) openAgentPanel({ agent: this.agent, row });
  }

  /** Node ID chosen (null: none), its properties at the canvas's foot. @param {string | null} id */
  choose(id, cx) {
    if (id === this.chosen) return;
    this.chosen = id;
    cx.notify();
  }

  /** This graph's key in the kept places. */
  kept() {
    return layoutKey(String(this.space), String(this.folder), this.agent);
  }

  /** A press on the canvas beside the nodes: the keys its own, no node chosen; a double one lays the graph out again
   * (its kept places dropped). */
  pressed(e, cx) {
    this.focus.focus();
    const kept = /** @type {any} */ (shared(GRAPH_LAYOUT));
    if (e.click_count === 2 && kept?.[this.kept()]) setShared(GRAPH_LAYOUT, dropLayout(kept, this.kept()));
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

  /** The press over: a node dragged is kept where it was let go; one only pressed (CLICKED) is chosen.
   * @param {boolean} clicked */
  drop(clicked, cx) {
    const drag = this.drag;
    if (!drag) return;
    this.drag = null;
    if (drag.to) {
      setShared(GRAPH_LAYOUT, keepLayout(shared(GRAPH_LAYOUT), this.kept(), { [drag.id]: drag.to },
        new Set(spaces().map((s) => s.id))));
    } else if (clicked) this.chosen = drag.id;
    cx.notify();
  }

  /** A key on the canvas: the arrows step to the nearest node that way, Esc puts the properties away.
   * @param {Record<string, import("./graph.js").Box>} all */
  keyed(e, cx, all) {
    if (e.key === "escape" && this.chosen) this.choose(null, cx);
    else if (["up", "down", "left", "right"].includes(e.key)) this.choose(stepNode(all, this.chosen, e.key), cx);
    else return;
    cx.stop_propagation();
  }

  /** NODE's file in the space's preview tab. @param {string} path */
  open(path) {
    const cut = path.lastIndexOf("/");
    showPreview({ kind: "file", root: path.slice(0, cut) || "/", path: path.slice(cut + 1), on: null });
  }

  render(t, cx) {
    const space = spaces().find((s) => s.id === this.space) ?? null;
    if (!space?.folder || space.machine) {        // another machine's setup is read with a later version
      return this.frame(t).child(this.say(t, space?.machine ? `On ${space.machine}: with a later version`
        : "No folder"));
    }
    const ask = agentsAsked(shared(AGENTS_ASK), space.id, this.answered, Date.now());
    if (ask?.view === "usage") {                  // Open Usage, Usage: the Usage view, a chat's row marked
      this.answered = ask.at;
      this.view = "usage";
      this.usage.ask(typeof ask.session === "string" ? ask.session : null);
    } else if (ask?.view === "runs") {            // the palette's Runs, the status bar's runs working
      Object.assign(this, { answered: ask.at, view: "runs" });
    } else if (ask) {
      Object.assign(this, { answered: ask.at, wants: typeof ask.node === "string" ? ask.node : null, view: "graph",
        session: "session" in ask ? (typeof ask.session === "string" ? ask.session : null) : this.session });
    }
    const agent = graphAgent({ kept: shared(AGENT_CHOSEN), space: space.id, recent: shared(RECENT_AGENTS) });
    this.theme = { surface: t.surface, foreground: t.foreground };
    if (this.view === "usage") this.usage.follow(t, cx);
    else if (this.view === "runs") this.runs.follow(cx);
    else this.follow(space, agent, cx);
    if (this.wants && this.found) {
      this.chosen = nodeFor(seen(this.found, this.mode).nodes, this.wants) ?? this.chosen;
      this.wants = null;
    }
    return this.draw(t, { agent, programs: programs(cx), scopes: this.usage.scopes(), space });
  }

  /** The tab's frame: a card, as a chat's. */
  frame(t) {
    return v_flex().id("agents").size_full().min_h(0).bg(t.surface).text_color(t.foreground).text_size(13);
  }

  /** WORDS in the graph's place, as every view says what it has instead. @param {string} words
   * @param {string} [color] */
  say(t, words, color = t.muted) {
    return div().flex_none().p(PAD).text_size(12).text_color(color).child(words);
  }

  /** The tab as LOOK has it: the head, and under it Usage's report, the runs, or the graph on its canvas; in the
   * graph's place what it says instead (loading, the read's failure, an agent not installed). @param {Look} look */
  draw(t, look) {
    if (this.view !== "graph") {
      const head = this.head(t, this.usage.scope(t, look.scopes ?? []), null, true);
      return this.frame(t).child(this.view === "usage" ? this.usage.draw(t, head)
        : this.runs.draw(t, head, look.space));
    }
    const found = this.found, name = found?.name ?? NAMES[look.agent] ?? look.programs[look.agent]?.name ?? look.agent;
    const views = found?.run && found.words?.views?.run ? segmented(t, "agents-view", viewWords(found), this.mode,
      (mode, cx) => this.see(mode, cx)) : null;
    const frame = this.frame(t).child(this.head(t, this.scope(t, `${name} in ${(this.folder ?? "").split("/")
      .pop()}`, look), views));
    if (found) return frame.child(this.canvas(t, seen(found, found.run ? this.mode : VIEWS[0]), look));
    return frame.child(this.missing ? this.say(t, `${name} is not installed`)
      : this.error ? this.say(t, `Couldn't read the graph: ${this.error}`, toneInk(t, "bad"))
        : this.say(t, "Loading graph…"));
  }

  /** The head (usage.html's .ahdr): SCOPE (a chip with its list), the graph's VIEWS beside it (none in Usage or
   * Runs), and at its end Graph, Usage and Runs, 13, the shown one over a 2 px line in the accent. COLUMN: in Usage's
   * or Runs' column, its edges the column's. @param {any} scope @param {any} views @param {boolean} [column] */
  head(t, scope, views, column = false) {
    const clear = `${t.accent}00`;
    return h_flex().flex_none().mt(PAD).mb(8).when(!column, (e) => e.px(PAD / 2)).gap(PAD).items_center()
      .child(scope).when(Boolean(views), (e) => e.child(views)).child(div().flex_1())
      .child(h_flex().flex_none().when(!column, (e) => e.pr(PAD / 2)).gap(16).children(PARTS.map(([view,
        word]) => div()
        .id(`agents-part-${view}`).h(BUTTON).flex().items_center().border_b_2()
        .border_color(view === this.view ? t.accent : clear).text_color(view === this.view ? t.foreground : t.muted)
        .when(view !== this.view && !this.still, (e) => e.cursor_pointer()
          .hover((/** @type {any} */ s) => s.text_color(t.foreground))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.show(view, cx)))
        .child(word))));
  }

  /** The graph's scope: WORDS ("Claude in lumen-api") after the agent's icon, 15 semibold, ⌄; a press opens the
   * agents core reads under it, lit while open. @param {string} words @param {Look} look */
  scope(t, words, look) {
    const mark = agentMark(look.programs[look.agent], 16), open = this.listing, clear = `${t.accent}00`;
    const chip = h_flex().id("agents-scope").h(BUTTON).min_w(0).px(6).gap(6).items_center().rounded(6).border_1()
      .border_color(open ? t.accent : clear).cursor_pointer().text_size(15).font_semibold()
      .when(open, (e) => e.bg(t.raised)).hover((/** @type {any} */ s) => s.bg(open ? t.raised : t.hover))
      .when(Boolean(mark), (e) => e.child(mark))
      .child(div().min_w(0).truncate().child(words))
      .child(icon("chevron-down", 14).text_color(t.dim));
    return Popover.new("agents-list").anchor("top_left").open(open)
      .when(!this.still, (/** @type {any} */ e) => e.track_focus(this.listFocus))
      .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) => this.list(opened, cx))
      .trigger(chip).when(open && !this.still, (/** @type {any} */ e) => e.content(this.listed(t, look).mt(4)));
  }

  /** The head's list, the Agent panel's form (agent-picker.html's .agm) under core's head: the installed agents core
   * reads, each with its icon, its name and its plan's word, ✓ on the one shown. A press or Enter picks; ↑ ↓ step.
   * @param {Look} look */
  listed(t, look) {
    const rows = agentList(this.agents, look.programs, look.agent).filter((row) => !row.dim
      && READ.includes(row.key));
    const none = this.agentsError ? listNote(t, `Couldn't list the agents: ${this.agentsError}`, true, PAD)
      : !this.agents ? listNote(t, "Loading agents…", false, PAD) : null;
    return panelSurface(t, "agents-list-surface", LIST).p(4).gap(2).track_focus(this.listFocus)
      .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => this.listKey(e, cx, rows))
      .when(rows.length > 0, (e) => e.child(div().flex_none().px(PAD).pt(6).pb(4).text_size(12).line_height("16px")
        .font_semibold().text_color(t.muted).child(rows[0].group)))
      .when(Boolean(none), (e) => e.child(none))
      .children(rows.map((row, n) => panelRow(t, this, n, true, row.check).id(`agents-pick-${row.key}`)
        .line_height("16px").cursor_pointer()
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.pick(row.key, cx))
        .child(agentMark(look.programs[row.key], 16) ?? icon("bot", 16).text_color(t.muted))
        .child(div().flex_none().child(row.name))
        .when(Boolean(row.word) && !row.warn, (e) => e.child(div().min_w(0).truncate().text_size(12)
          .text_color(t.muted).child(row.word ?? "")))
        .child(div().flex_1())
        .when(row.check, (e) => e.child(icon("check", 14).text_color(t.accent)))));
  }

  /** GRAPH on its canvas (.gcanvas): a hairline frame with a grid of dots, scrolled where the graph needs more room;
   * the edges under the nodes, the gates over them; the legend at its top right, the chosen node's properties at its
   * foot. A node drags, a double click beside them lays them out again. @param {any} graph @param {Look} look */
  canvas(t, graph, look) {
    /** @type {Node[]} */
    this.uid ??= views++;
    const nodes = graph.nodes, size = this.size, apart = gatesRoom(graph.edges), near = gatesRoom(graph.edges, true);
    const at = placed(this.still ? null : shared(GRAPH_LAYOUT), this.kept(), nodes, size, this.sizes, apart, near);
    if (this.drag?.to) at[this.drag.id] = this.drag.to;
    const all = boxes(nodes, at, this.sizes), room = extent(all, size);
    const chosen = nodes.find((one) => one.id === this.chosen) ?? null, top = this.drag?.id ?? this.chosen;
    const view = graph.run ? this.mode : VIEWS[0];
    const { wires, gates } = this.wires(t, graph.edges, all, view);
    const content = div().id("agents-content").relative().w(room.width).h(room.height)
      .when(!this.still, (e) => e.on_mouse_down("left", (/** @type {any} */ e, /** @type {any} */ cx) =>
        this.pressed(e, cx)))
      .child(this.dots(t, room)).children(wires)
      .children(this.heads(t, graph.words.columns, boxes(nodes, layout(nodes, size, this.sizes, apart, near),
        this.sizes), room))
      .children([...nodes.filter((one) => one.id !== top), ...nodes.filter((one) => one.id === top)]
        .map((one) => this.node(t, one, all[one.id], look, view)))
      .children(gates)
      .children(nodes.filter((one) => nodeShown(one, view).order && all[one.id]).map((one) => this.number(t,
        badgeAt(all[one.id]), nodeShown(one, view).order)));
    return div().id("agents-frame").relative().flex_1().min_h(0).mx(PAD).mb(PAD).rounded(10).border_1()
      .border_color(t.border).overflow_hidden()
      .when(!this.still, (e) => e.track_focus(this.focus)
        .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => this.keyed(e, cx, all))
        .on_mouse_move((/** @type {any} */ e, /** @type {any} */ cx) => this.moved(e, cx))
        .on_mouse_up("left", (/** @type {any} */ _e, /** @type {any} */ cx) => this.drop(true, cx))
        .on_hover((/** @type {boolean} */ over, /** @type {any} */ cx) => void (!over && this.drop(false, cx))))
      .child(div().id(`agents-canvas-${this.uid}`).size_full().overflow_scrollbar()
        .on_size_change((/** @type {{ width: number, height: number }} */ now, /** @type {any} */ cx) => {
          const width = unzoomed(now.width, zoom()), height = unzoomed(now.height, zoom());
          if (width === size.width && height === size.height) return;
          this.size = { width, height };
          cx.notify();
        })
        .when(size.width > 0, (e) => e.child(content)))
      .child(this.legend(t, legendOf(graph.words.legend, view)))
      .when(Boolean(chosen), (e) => e.child(this.inspector(t, /** @type {Node} */ (chosen), look, view)));
  }

  /** A first use's number at AT (agent-graph.html's .num): a disc DISC across in the accent, the number 11 bold in
   * the accent's own text color, over the nodes. @param {import("./graph.js").Point} at @param {number} order */
  number(t, at, order) {
    return div().absolute().left(at.x).top(at.y).size(DISC).flex().items_center().justify_center().rounded_full()
      .bg(t.accent).text_size(11).line_height(`${DISC}px`).font_bold()
      .text_color(t.accent_foreground ?? t.background).child(String(order));
  }

  /** The canvas's dots, GRID apart (.gcanvas's): one dashed path, the text's color at 5%.
   * @param {{ width: number, height: number }} room */
  dots(t, room) {
    let path = PathBuilder.stroke(2).dash_array([2, GRID - 2]);
    for (let y = GRID / 2; y < room.height; y += GRID) path = path.move_to(GRID / 2, y).line_to(room.width, y);
    return painted(path, `${t.foreground}0d`);
  }

  /** EDGES between the boxes ALL in VIEW: a path a look (wireLook()), a node's edges leaving it in their targets'
   * order; each edge's gates on it, pills centred 55% along (in This chat on the edges that ran alone).
   * @param {import("./graph.js").Edge[]} edges @param {Record<string, Box>} all @param {string} view */
  wires(t, edges, all, view) {
    /** @type {Map<string, import("./graph.js").Edge[]>} */
    const out = new Map();
    for (const edge of edges) {
      if (all[edge.from] && all[edge.to]) out.set(edge.from, [...(out.get(edge.from) ?? []), edge]);
    }
    /** @type {Record<string, { path: any, color: string }>} */
    const paths = {};
    const gates = [];
    const middle = (/** @type {string} */ id) => all[id].y + all[id].h / 2;
    for (const list of out.values()) {
      list.sort((a, b) => middle(a.to) - middle(b.to));
      for (const [n, edge] of list.entries()) {
        const [from, a, b, to] = edgePath(all[edge.from], all[edge.to], portOf(list.length, n));
        const drawn = wireLook(t, edge, view), was = paths[drawn.key]?.path ?? (drawn.dashed
          ? PathBuilder.stroke(drawn.width).dash_array(DASH) : PathBuilder.stroke(drawn.width));
        paths[drawn.key] = { color: drawn.color, path: was.move_to(from[0], from[1])
          .cubic_bezier_to(to[0], to[1], a[0], a[1], b[0], b[1]) };
        if (edge.gates.length && (view !== "run" || edge.run?.ran)) {
          gates.push(this.gate(t, gateAt([from, a, b, to]), edge.gates));
        }
      }
    }
    // the faint ones first, the lit ones over them
    const order = Object.keys(paths).sort((a, b) => Number(["ran", "running"].includes(a))
      - Number(["ran", "running"].includes(b)));
    return { wires: order.map((key) => painted(paths[key].path, paths[key].color)), gates };
  }

  /** An edge's GATES at AT (agent-graph.html's .gate): pills on the window's level with a hairline, verb and object
   * in its tone (ask yellow, allow green, deny red, a hook muted), 4 apart, centred on the edge.
   * @param {import("./graph.js").Point} at @param {{ text: string, tone: string }[]} gates */
  gate(t, at, gates) {
    return div().absolute().left(at.x - GATES / 2).top(at.y - 9).w(GATES).flex().justify_center()
      .child(h_flex().flex_none().gap(4).children(gates.map((one) => div().h(18).flex_none().px(6).flex()
        .items_center().rounded(4).border_1().border_color(t.border).bg(t.canvas).text_size(11).line_height("16px")
        .whitespace_nowrap().text_color(toneInk(t, one.tone, t.canvas)).child(one.text))));
  }

  /** The columns' names (.gcols), 11 muted, HEADS down: In from the left edge, Agents over the agent, Uses to the right
   * edge. @param {Record<string, string>} words @param {Record<string, import("./graph.js").Box>} laid
   * @param {{ width: number }} room */
  heads(t, words, laid, room) {
    const agent = laid[AGENT], wide = 120;
    const head = (/** @type {string} */ word) => div().absolute().top(HEADS).text_size(11).line_height("16px")
      .text_color(t.muted).child(word);
    return [head(words.in).left(EDGE),
      head(words.agents).left((agent ? agent.x + agent.w / 2 : room.width / 2) - wide / 2).w(wide).text_center(),
      head(words.uses).left(room.width - EDGE - wide).w(wide).text_right()];
  }

  /** The legend at the canvas's top right (.legend): each kind of edge's sample and its word, 11 muted, on the nodes'
   * level at 90%; "ran here", in the accent, in This chat alone. @param {[string, string][]} legend */
  legend(t, legend) {
    const sample = (/** @type {string} */ style) => (style === "ran" ? div().w(22).h(2).bg(t.accent)
      : style === "always" ? div().w(22).h(2).bg(wireColor(t, style))
        : h_flex().gap(4).children([0, 1, 2].map(() => div().w(5).h(2).bg(wireColor(t, style)))));
    return h_flex().absolute().top(PAD).right(PAD).h(BUTTON).px(PAD).gap(PAD).items_center().rounded(8).border_1()
      .border_color(t.border).bg(`${t.chrome}e6`).text_size(11).text_color(t.muted)
      .children(legend.map(([style, word]) => h_flex().gap(6).items_center().child(sample(style)).child(word)));
  }

  /** NODE's mark: the agent's own icon (the app's), a connector's logo or letter tile, else its kind's icon, muted.
   * @param {Node} node @param {Look} look */
  mark(t, node, look) {
    return node.kind === "agent" ? agentMark(look.programs[look.agent], 14) ?? icon("bot").text_color(t.muted)
      : node.kind === "connector" ? brandMark(t, node.brand, node.title)
        : icon(ICON[node.icon ?? ""] ?? "file").text_color(t.muted);
  }

  /** NODE at BOX in VIEW (agent-graph.html's .node): its tag a raised chip or This chat's state in its tone; in This
   * chat its cost or calls, model's square, share's bar. A press chooses it, a drag moves it.
   * @param {Node} node @param {Box} box @param {Look} look @param {string} view */
  node(t, node, box, look, view) {
    const agent = node.kind === "agent", chosen = node.id === this.chosen, [color, alpha] = STATE_EDGE[node.state
      ?? ""] ?? [];
    const shown = nodeShown(node, view);
    const ground = agent ? mixColor(t.chrome, t.accent, AGENT_TINT) : t.chrome, code = codeFont();
    const edge = color ? `${t[color]}${alpha}` : agent ? `${t.accent}${AGENT_EDGE}` : wireColor(t, "always");
    const card = v_flex().id(`agents-node-${this.uid}-${node.id}`).min_w(sizeOf(node).w).max_w(MOST).py(8).px(PAD)
      .rounded(10).border_1().border_color(edge).bg(ground).shadow_md()
      .on_size_change((/** @type {{ width: number, height: number }} */ size, /** @type {any} */ cx) => {
        const { w, h } = measured(size, zoom()), was = this.sizes[node.id];
        if (was?.w === w && was?.h === h) return;
        this.sizes = { ...this.sizes, [node.id]: { w, h } };
        cx.notify();
      })
      .child(h_flex().h(18).gap(6).items_center().child(this.mark(t, node, look))
        .child(div().min_w(0).truncate().text_size(12).font_semibold().child(node.title))
        .when(Boolean(shown.tag ?? shown.cost ?? shown.calls), (e) => e.child(div().flex_1().min_w(6)))
        .when(typeof shown.tag === "string", (e) => e.child(scopeTag(t, tagWord(String(shown.tag)))))
        .when(Boolean(shown.tag) && typeof shown.tag === "object", (e) => e.child(div().flex_none().text_size(11)
          .text_color(toneInk(t, shown.tag?.tone ?? "", ground)).child(shown.tag?.text ?? "")))
        .when(Boolean(shown.cost), (e) => e.child(div().flex_none().text_size(12).child(shown.cost ?? "")))
        .when(Boolean(shown.calls), (e) => e.child(div().flex_none().text_size(11).text_color(t.muted)
          .child(shown.calls ?? ""))))
      .when(Boolean(shown.sub), (e) => e.child(h_flex().h(16).mt(2).gap(6).items_center().text_size(11)
        .line_height("16px").text_color(node.state ? toneInk(t, node.state, ground) : t.muted)
        .when(Boolean(shown.color), (e) => e.child(swatch(shown.color ?? "")))
        .child(div().min_w(0).truncate().child(shown.sub ?? ""))))
      .when(shown.share !== null, (e) => e.child(div().h(4).mt(6).rounded_full().overflow_hidden().bg(t.raised)
        .child(div().h_full().w(`${shareWidth(shown.share, 100)}%`).rounded_full().bg(shown.color ?? t.muted))))
      .when(node.chips.length > 0, (e) => e.child(h_flex().mt(6).gap(4).flex_wrap().children(node.chips.map((chip) =>
        div().h(18).px(6).flex().items_center().rounded(4).bg(t.canvas).font_family(code).text_size(11)
          .text_color(t.muted).whitespace_nowrap().child(chip)))));
    return div().absolute().left(box.x - RING).top(box.y - RING).p(RING).rounded(10)
      .when(chosen, (e) => e.bg(t.accent)).when(faded(node, view), (e) => e.opacity(0.5))
      .child(this.still ? card : card.when(this.drag?.id === node.id, (e) => e.cursor_grabbing())
        .when(this.drag?.id !== node.id, (e) => e.cursor_grab())
        .on_mouse_down("left", (/** @type {any} */ e, /** @type {any} */ cx) => this.grab(node, { x: box.x,
          y: box.y }, e, cx)));
  }

  /** The chosen NODE's properties in VIEW at the canvas's foot (agent-graph.html's .insp): its title with ×, its
   * lines as the Agent panel's, a folded node's names, an error, Open; what it ran as usage.html's .ginsp, with Open
   * in Usage; last Show in Agent, by its row. @param {Node} node @param {Look} look @param {string} view */
  inspector(t, node, look, view) {
    const props = propertiesOf(node, view), ran = props !== node.properties, ground = t.popover ?? t.raised;
    const code = codeFont(), { list, lines } = nodeLines(node, view);
    const opens = (props?.actions ?? []).filter((/** @type {any} */ one) => one.id === "open" && one.path);
    const usage = (props?.actions ?? []).find((/** @type {any} */ one) => one.id === "usage");
    const panel = shownInAgent(node, view), first = opens.length === 0 && !usage;
    const error = errorColors(t, ground), state = props?.state ?? null;
    const told = (/** @type {[string, string, string | null]} */ [name, value, note], /** @type {number} */ n) =>
      h_flex().id(`agents-ran-${n}`).h(20).flex_none().gap(8).items_center()
        .child(div().w(RUN_LABEL).flex_none().text_color(t.muted).child(name))
        .child(div().flex_none().max_w_full().truncate().child(value))
        .when(Boolean(note), (e) => e.child(div().min_w(0).truncate().text_color(t.muted).child(note ?? "")));
    return v_flex().id("agents-inspector").absolute().left(PAD).bottom(PAD).w(ran ? RUN_INSPECTOR : INSPECTOR)
      .p(PAD).gap(6).rounded(10)
      .border_1().border_color(t.border).bg(ground).shadow_lg().text_size(12)
      .on_mouse_down("left", (/** @type {any} */ _e, /** @type {any} */ cx) => cx.stop_propagation())
      .child(h_flex().h(20).flex_none().gap(8).items_center()
        .child(this.mark(t, node, look))
        .child(div().flex_1().min_w(0).truncate().font_semibold().child(props?.title ?? node.title))
        .when(Boolean(state), (e) => e.child(div().flex_none().text_size(ran ? 12 : 11)
          .text_color(toneInk(t, state?.tone ?? "", ground)).child(state?.text ?? "")))
        .child(div().id("agents-inspector-close").size(16).flex_none().flex().items_center().justify_center()
          .rounded(4).text_color(t.dim).cursor_pointer().tooltip("Close")
          .hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(null, cx)).child(icon("x", 12))))
      .when(lines.length > 0, (e) => e.child(v_flex().id("agents-inspector-lines").flex_none().max_h(LISTED)
        .overflow_y_scroll().children(lines.map((line, n) => (list ? h_flex().h(20).flex_none().gap(8).items_center()
          .child(div().flex_1().min_w(0).truncate().child(line[0]))
          .child(div().flex_none().text_color(t.muted).child(line[1]))
          : ran ? told(line, n) : propertyLine(t, `agents-property-${n}`, line, LABEL, code))))))
      .when(Boolean(props?.error), (e) => e.child(div().id("agents-inspector-error").flex_none().px(8).py(6)
        .rounded(6).bg(error.fill).font_family(code).text_size(11).text_color(error.ink)
        .when(Boolean(props?.tip), (e) => e.tooltip(props?.tip ?? "")).child(props?.error ?? "")))
      .when(!first || Boolean(panel), (e) => e.child(h_flex().flex_none().pt(2).gap(6).flex_wrap()
        .children(opens.map((/** @type {any} */ one, /** @type {number} */ n) => actButton(t, `agents-open-${n}`,
          one.label, n ? "plain" : "raised", true, () => this.open(String(one.path)))))
        .when(Boolean(usage), (e) => e.child(actButton(t, "agents-open-usage", usage?.label ?? "", "plain", true,
          (/** @type {any} */ cx) => this.showUsage(typeof usage?.session === "string" ? usage.session : null,
            cx))))
        .when(Boolean(panel), (e) => e.child(actButton(t, "agents-show-agent", panel?.label ?? "",
          first ? "raised" : "plain", true, () => this.showAgent(panel?.row ?? null))))));
  }
}
