// @ts-check
// The Agent panel, the dock's fifth view: what the space's agent starts with in its folder, as a design tool's layers,
// the chosen row's properties under them. Core words it (agent_layers.py's layers()), the TUI's Agent view too.
import { div, image, svg } from "gpui-kit";
import { h_flex, v_flex, Input, InputState, Popover, ScrollHandle } from "gpui-base";
import { agents as paneAgents, exec, focused, hc, home, knownAgents, layout, panes, setShared, shared, spaces,
  terminals, watchFolder, run as command } from "herdr";
import { panelStep, RECENT_AGENTS } from "./agents.js";
import { AGENT_LAYERS, AGENT_STATE, CONNECTORS, HARNESS, REPORT, TOKENS, USAGE } from "./helper.js";
import { actionLook, afterSave, AGENT_ASK, AGENT_CHOSEN, AGENT_OPEN, AGENT_PROBLEMS, agentList, agentOf,
  approves, asked, asking, bodyHeight, changeLine, CHIP_LIFT, chipColors, chosenAgent, chosenFill, chosenRow, claudeIn,
  conflicted, DEFAULT, doable, errorColors, filePath, footWords, formAsk, GROUP_H, HEAD_H, headline, headParts,
  keepAgent, keepOpen, keepProblems, LABEL, layersShown, levelFill, levelInk, loginRun, MODEL, MORE_H, NAMES, NARROW,
  overdue, partColor, printedAddress, propertyLines, READ, removable, resetWords, ROW_H, rowless, RULE, sayOnly,
  sectionOpen, sentence, SERVER, serverOf, shown, signingRow, signIns, signInTab, switchShown, tabAgent, tagRoom,
  tagWord, toneInk, touches, USAGE_LINE, usageAgents, usageFigure, usageHeight, usageLine, usageRow, usageRows, WARN_H,
  WATCHED }
  from "./layers.js";
import { indexed, reportArgs } from "./report.js";
import { CHAT_LABEL, CHAT_TAB, DOCK, find, lastLine, PANEL_PX, panelPx, panelRailed, panelShown,
  said } from "./logic.js";
import { listNote, panelRow, panelSurface, rule } from "./menus.js";
import { actButton, ACTION, brandMark, BUTTON, codeFont, field, fold, icon, iconButton, PAD, propertyLine, scopeTag,
  spinner, SPRING, systemForms, toggle } from "./parts.js";
import { showPreview } from "./preview.js";
import { format, setForms, written } from "./timeline.js";

const POLL = 30000;                // ms between two reads while it shows, as the TUI's
const AWAY = 300000;               // ms between two reads behind another view, for the tab's dot alone, as the TUI's
// the properties whose value is a phrase, in the text's font; the others (a file, a command, an address) are code
const PHRASES = ["Used", "On", "Network", "Plan", "Budget", "Read", "5h", "Week"];
const QUIET = 5000;                // ms at least between two reads a change asks for (a conversation writes a lot)
const COST = 52;                   // px: the costs' column at a row's and a section's end, its swatch in a head's
const SWATCH = 7;                  // px: a head's swatch before its cost, in its part's bar color (connectors.html's)
const INSET = 10, MARKS = 12;      // px: a row's start, its mark's column (connectors.html's .lrow, .mk)
const NAME_IN = INSET + MARKS + 6;           // px: a row's name, and the words under rows, from the layers' edge
const NOTE_SHRINK = 100;           // a row's note gives way this much before its name does
const SIGNING = 5000;              // ms between two looks at the agents while one signs in in its terminal tab
const SIGNING_MS = 600000;         // ms a sign-in is waited for at most
const LIST = 300;                  // px: the agents' list, agent-picker.html's .agm
const CHECK = 12;                  // px: its rows' first column, ✓ on the agent shown
const MARK = 28;                   // px: the agent's icon over what its panel says instead of a setup
const SAID = 272;                  // px: those words' column at most (connectors.html's .signin p: 270)
const COPIED = 2000;               // ms the install line's Copy shows its check
const WATCH = 2000;                // ms between two looks at the sign-ins running: one ended is asked about again
const SETTLE = [2000, 6000];       // ms after Claude was told to turn a server on: its setup read again
const TYPING = 250;                // ms a form's typed field rests before core plans it
const FOOT = 32;                   // px: the foot after a save, the mockup's .pfoot
const LOGO = 16;                   // px: a connector's logo or letter tile, connectors.html's .tile.xs
const ADD = 22;                    // px: Connectors' + at its head's end, connectors.html's .lsec .add
const ADD_MENU = 200;              // px: what it opens, connectors.html's .addm
const FIELD = 28;                  // px: a form's fields and lines, connectors.html's .fld .in
const READ_LINES = "200";          // rows over a sign-in's screen its address is looked for in
const WINDOW = 74, METER = 22;     // px: a Usage window's column ("5h", its bar, its percent), its bar
const MONTHS_EVERY = 60000;        // ms the API keys' months are kept before core is asked again
const MONTHS = "today";            // the report the months are read from (each API-key agent's, whatever the period)

/** @type {Record<string, any> | null} the app's agents by key (knownAgents'), asked once: their icons */
let known = null;

/** The app's agents by key, asked for once (CX draws again when they come); none yet, or the app's answer failed: {}.
 * @returns {Record<string, any>} */
export function programs(cx) {
  if (known) return known;
  known = {};
  cx.spawn(async (/** @type {any} */ cx) => {
    try {
      known = Object.fromEntries((await knownAgents()).map((p) => [p.key, p]));
      cx.notify();
    } catch {
      // no icons: the tab wears Lucide's bot, the head names the agent
    }
  });
  return known;
}

/** PROGRAM's icon (the app's own for the agent), SIZE square, a tinted one in the text's color; null while not known.
 * @param {any} program @param {number} size */
export const agentMark = (program, size) => (!program?.icon ? null : program.tint
  ? svg(program.icon).size(size).flex_none() : image(program.icon).size(size).flex_none());

/** The space shown, the agent its panel shows there (chosenAgent's) and the open conversation's id: the focused chat's
 * when it is that agent's, else none (core takes the folder's newest). */
export function agentHere() {
  const space = spaces().find((s) => s.active) ?? null;
  const tab = tabAgent(focused()?.tab, panes(), terminals(), { tab: CHAT_TAB, session: CHAT_LABEL });
  const agent = chosenAgent({ kept: shared(AGENT_CHOSEN), space: space?.id ?? null, focused: tab?.agent ?? null,
    recent: shared(RECENT_AGENTS) });
  return { space, agent, session: tab?.agent === agent ? tab.session : null };
}

/** SPACE's problems as core's layers FOUND has them, told to the dock's tab and the rail (their dot), where changed.
 * @param {string} space @param {any} found */
function tellProblems(space, found) {
  const kept = shared(AGENT_PROBLEMS), next = keepProblems(kept, space, found, new Set(spaces().map((s) => s.id)));
  if (next !== kept) setShared(AGENT_PROBLEMS, next);
}

/** The shown space's problems for the tab's and the rail's dot: {tone, said}, or null. */
export const problemsHere = () => {
  const space = spaces().find((s) => s.active)?.id;
  return (space && /** @type {any} */ (shared(AGENT_PROBLEMS))?.[space]) || null;
};

/** The file PATH in the preview tab: a row's Open, a form's layer, More options. @param {string} path */
function showFile(path) {
  const cut = path.lastIndexOf("/");
  showPreview({ kind: "file", root: path.slice(0, cut) || "/", path: path.slice(cut + 1), on: null });
}

/** Whether the open dock's stack is on the Agent panel. */
function docked() {
  const root = layout();
  return panelShown(root) && !panelRailed(root) && find(root, DOCK)?.active === "agent";
}

/** The setup's problems looked at behind the views, by the tab bar (it always shows; a view's copy starts once it
 * first shows): the shown space's agent's, read when it becomes another and every AWAY, for the tab's dot. */
export class AgentLook {
  /** @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
  constructor(core) {
    this.core = core;
    /** @type {string | null} */
    this.key = null;
    this.readAt = 0; this.busy = false;
  }

  /** From the tab bar's render and its timer: read where the space or its agent is another, or the last is old;
   * never while the dock's panel shows (it reads itself, with what Claude answered a Retry). */
  follow(cx) {
    const { space, agent, session } = agentHere(), folder = space?.machine ? null : space?.folder ?? null;
    const key = JSON.stringify([space?.id, agent, folder]);
    if (!space || !folder || this.busy || docked() || (key === this.key && Date.now() - this.readAt < AWAY)) return;
    if (!READ.includes(agent)) return void tellProblems(space.id, null);      // no setup read: no dot
    Object.assign(this, { key, busy: true, readAt: Date.now() });
    cx.spawn(async () => {
      try {
        tellProblems(space.id, await this.core(AGENT_LAYERS, [agent, folder,
          ...(agent === "claude" && session ? [session] : [])], folder, null));
      } catch {
        // no Python, or the read failed: the dot as it was, the panel says why once shown
      } finally {
        this.busy = false;
      }
    });
  }
}

/** What reads an agent's setup in a folder and shows it: the Agent panel, the Agents tab. @typedef {{ folder:
 * string | null, agent: string, watches: Map<string, object>, readAt: number, waiting: boolean, shows: () => boolean,
 * read: (cx: any) => void }} Reader */

/** READER's folder and its agent's own folder under the home watched, each change that touches the setup a new read
 * (setupChanged()); the folders of an earlier agent or space let go. @param {Reader} reader */
export function watchSetup(reader, cx) {
  const wanted = reader.folder ? [reader.folder, `${home()}/${WATCHED[reader.agent]}`] : [];
  for (const path of [...reader.watches.keys()]) if (!wanted.includes(path)) reader.watches.delete(path);
  for (const path of wanted.filter((p) => !reader.watches.has(p))) {
    const token = {};
    reader.watches.set(path, token);
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        while (reader.watches.get(path) === token) {
          const paths = await watchFolder(path);
          if (reader.watches.get(path) === token && touches(paths, path, reader.folder)) setupChanged(reader, cx);
        }
      } catch {
        if (reader.watches.get(path) === token) reader.watches.delete(path);   // no such folder: the timer reads
      }
    });
  }
}

/** Something of READER's setup changed: read now, or once QUIET has passed since the last read; hidden, on show.
 * @param {Reader} reader */
function setupChanged(reader, cx) {
  if (!reader.shows() || reader.waiting) return;
  const wait = reader.readAt + QUIET - Date.now();
  if (wait <= 0) return void reader.read(cx);
  reader.waiting = true;
  cx.timer.after(wait, (/** @type {any} */ cx) => {
    reader.waiting = false;
    if (reader.shows()) reader.read(cx);
  });
}

/** @typedef {import("./layers.js").Section} Section */
/** @typedef {import("./layers.js").Row} Row */
/** @typedef {import("./layers.js").Usage} Usage */
/** "By URL…"'s form: its two fields, Claude's scope, the field the keys are in, what was refused (FIELD null: the
 * agent's own words), its command running. @typedef {{ name: any, url: any, scope: string,
 * focus: "name" | "url" | null, error: { field: string | null, error: string } | null, busy: boolean }} Form */
/** @typedef {import("./layers.js").Ask} Ask */
/** @typedef {import("./layers.js").Plan} Plan */
/** How an open form stands: touched, saving, what was refused or noted, its button's last word, the asks counted
 * (PLANNED: the one its plan answers). @typedef {{ touched: boolean, busy: boolean, error: string | null,
 * note: string | null, submit: string | null, serial: number, planned: number }} Standing */
/** A row's form as core plans it (harness.py): what it opened with and asks now, a built-in subagent's NAME, the
 * newest PLAN, its text fields' INPUTS. @typedef {{ base: Ask, ask: Ask, name: string | null, plan: Plan | null,
 * inputs: Record<string, any>, typed: Record<string, string>, focus: string | null } & Standing} Edit */
/** The last save: its words (CODE: a change's line), core's way back and its word, a way back refused.
 * @typedef {{ text: string, code: boolean, undo: any[], word: string, error: string | null, busy: boolean }} Foot */
/** What draw() takes besides the view's own state: the agent, the app's programs, each section's fold, the panel's
 * width (under NARROW its tags go). @typedef {{ agent: string, programs: Record<string, any>,
 * open: (section: string) => boolean, px: number }} Look */

export class AgentView {
  /** CORE: main.js's python (its JSON answer); FLOATING: beside the rail; GRAPH: a row's Show graph (openAgents).
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core
   * @param {boolean} [floating] @param {((ask: { node: string, session: string | null }) => void) | null} [graph] */
  constructor(core, cx, floating = false, graph = null) {
    this.core = core;
    this.floating = floating;
    this.graph = graph;
    /** @type {string | null} what was asked for last: the agent, the folder and the conversation, as JSON */
    this.key = null;
    /** @type {any} core's layers for it; null: not read yet, or not installed (missing) */
    this.found = null;
    this.missing = false;
    /** @type {string | null} why the read failed, while nothing is shown */
    this.error = null;
    this.busy = false; this.again = false; this.readAt = 0; this.waiting = false;
    /** @type {Set<string>} the sections opened past their "N more" */
    this.more = new Set();
    this.finding = false; this.query = "";
    this.find = InputState.new({ placeholder: "Filter setup" });
    this.find.on("change", (_e, cx) => {
      this.query = this.find.value().trim();
      cx.notify();
    });
    this.slides = "";                             // its springs' own name: an element's id keeps a slide
    /** @type {string | null} the chosen row's id: its properties under the layers */
    this.chosen = null;
    /** @type {Set<string>} the servers Claude checks again, their state a spinner meanwhile */
    this.checking = new Set();
    /** @type {Record<string, { base: string | null, state: string, error: string | null }>} Claude's answers to
     * Retry, each with the state its server had then: core shows one until a newer session says otherwise */
    this.checked = {};
    /** @type {Record<string, string>} each server's own state as last read */
    this.states = {};
    /** @type {string | null} what an action could not do, in the properties */
    this.failed = null;
    /** @type {number | null} the last ask answered (openAgentPanel()'s), by its time */
    this.answered = null;
    /** @type {{ section: string | null, row: string | null } | null} an ask waiting for the first read */
    this.waits = null;
    this.scroll = ScrollHandle.new();             // the layers': a problem's section scrolled to
    /** @type {import("./layers.js").Machine[] | null} the agents on this Mac as core tells them; null: not yet */
    this.agents = null;
    /** @type {string | null} why they could not be listed, in the list */
    this.agentsError = null;
    this.agentsAt = 0; this.agentsBusy = false;
    this.listing = false;                         // the head's list open
    /** @type {number | null} the list's row the keys are on (menus.js's Lister) */
    this.cursor = null;
    this.listPlaces = []; this.listScroll = null;
    this.listFocus = cx.focus_handle();
    /** @type {string | null} a not-installed agent picked in the list: how it is installed, till another is */
    this.looking = null;
    /** @type {{ key: string, until: number } | null} the agent signing in in its terminal tab, looked at till then */
    this.signing = null;
    this.copied = false;
    this.still = false;                           // the styleguide's: the chip lit, its list drawn beside, not opened
    /** @type {{ none: string, rows: any[] } | null} core's Usage (usage.py's section()); null: not read */
    this.usage = null;
    /** @type {string | null} why the limits could not be read, while none are shown */
    this.usageError = null;
    this.usageBusy = false;
    /** @type {any} core's report of today, its API keys' months (Usage's rows of them); null: not read */
    this.report = null;
    this.reportAt = 0;
    /** @type {Set<string>} the servers seen signing in (the app's terminals tell which): one ended is asked about */
    this.signed = new Set();
    /** @type {string | null} a server added a moment ago: signed in to once its agent says it must be */
    this.wants = null;
    this.addMenu = false;                         // Connectors' + pressed: From claude.ai…, By URL…
    this.addList = { cursor: /** @type {number | null} */ (null), listPlaces: [], listScroll: null };  // its keys' row
    this.addFocus = cx.focus_handle();
    /** @type {number[]} when (ms) the setup is read again: after Claude was told to turn a server off or on */
    this.due = [];
    /** @type {Form | null} "By URL…": the form in the properties' place */
    this.form = null;
    /** @type {Edit | null} the chosen row's form in its properties (the head's, the +'s, Hooks' head's: alone) */
    this.edit = null;
    /** @type {Foot | null} what was saved last, with its way back */
    this.foot = null;
    cx.timer.every(WATCH, (/** @type {any} */ cx) => this.watchSignIns(cx));
    cx.spawn(async (/** @type {any} */ cx) => {
      setForms(await systemForms());              // a reset's time as this Mac writes it
      cx.notify();
    });
    cx.timer.every(SIGNING, (/** @type {any} */ cx) => void (this.signing && this.shows() && this.readAgents(cx)));
    /** @type {Map<string, object>} the folders watched, each with its watch's token */
    this.watches = new Map();
    cx.timer.every(POLL, (/** @type {any} */ cx) => void (this.shows() && this.read(cx)));
  }

  /** Whether the panel shows now: floating, or the open dock's stack on it. */
  shows() {
    return this.floating || docked();
  }

  /** From render: HERE (agentHere's) read once it is another agent, folder or conversation than the last, or the
   * last read is older than a change may wait (shown again). */
  follow(here, cx) {
    const folder = here.space?.machine ? null : here.space?.folder ?? null;
    const key = JSON.stringify([here.agent, folder, here.session]);
    if (key !== this.key) {
      Object.assign(this, { key, agent: here.agent, folder, session: here.session, found: null, missing: false,
        error: null, more: new Set(), chosen: null, checking: new Set(), checked: {}, states: {}, failed: null,
        signed: new Set(), wants: null, addMenu: false, form: null, due: [], edit: null, foot: null });
      this.watch(cx);
      this.read(cx);
    } else if (Date.now() - this.readAt > POLL) this.read(cx);
    if (folder && Date.now() - this.agentsAt > AWAY) this.readAgents(cx);
  }

  /** The agents on this Mac asked of core (installed, signed in, on which plan): first shown, every AWAY, as the
   * list opens, and every SIGNING while one signs in (till it has, or SIGNING_MS passed); kept where a read fails. */
  readAgents(cx) {
    if (!this.folder || this.agentsBusy) return;
    const folder = this.folder;
    Object.assign(this, { agentsBusy: true, agentsAt: Date.now() });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const agents = await this.core(AGENT_STATE, ["agents"], folder, null);
        const signed = this.signing && agentOf(agents, this.signing.key)?.signed_in !== false;
        if (signed || (this.signing && Date.now() > this.signing.until)) this.signing = null;
        if (this.looking && agentOf(agents, this.looking)?.installed !== false) this.looking = null;
        const same = !this.agentsError && JSON.stringify(agents) === JSON.stringify(this.agents);
        Object.assign(this, { agents: Array.isArray(agents) ? agents : [], agentsError: null });
        if (signed) this.read(cx);
        if (!same) this.readUsage(cx);            // their plans' words
        if (!same) cx.notify();
      } catch (e) {
        if (this.agents) return;
        this.agentsError = said(e);
        cx.notify();
      } finally {
        this.agentsBusy = false;
      }
    });
  }

  /** The agents' limits asked of core (usage.py's section(): the rows in both clients' words), with every read of the
   * setup and as the agents' plans are told; kept where a read fails. */
  readUsage(cx) {
    if (!this.folder || this.usageBusy) return;
    const { folder, agent } = this;
    this.usageBusy = true;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const usage = await this.core(USAGE, ["section", agent, JSON.stringify(usageAgents(this.agents))], folder,
          null);
        const same = !this.usageError && JSON.stringify(usage) === JSON.stringify(this.usage);
        Object.assign(this, { usage, usageError: null });
        if (!same) cx.notify();
        await this.readMonths(cx);
      } catch (e) {
        if (this.usage) return;
        this.usageError = said(e);
        cx.notify();
      } finally {
        this.usageBusy = false;
      }
    });
  }

  /** The API keys' months, Usage's rows of them (core's report, after the token index is read on), every
   * MONTHS_EVERY at most; kept where a read fails: the limits stand without them. */
  async readMonths(cx) {
    if (Date.now() - this.reportAt < MONTHS_EVERY) return;
    this.reportAt = Date.now();
    try {
      await indexed(() => this.core(TOKENS, ["index"], home(), null));
      const report = await this.core(REPORT, reportArgs("report", { period: MONTHS, agent: null, folder: null,
        agents: usageAgents(this.agents), theme: null }), home(), null);
      if (JSON.stringify(report?.months) === JSON.stringify(this.report?.months)) return;
      this.report = report;
      cx.notify();
    } catch {
      // not told now: the next read asks again
    }
  }

  /** The head's list shown (OPEN) or shut: the keys on no row till an arrow, the agents asked for again as it
   * opens. @param {boolean} open */
  list(open, cx) {
    Object.assign(this, { listing: open, cursor: null, listPlaces: [] });
    if (open) this.readAgents(cx);
    cx.notify();
  }

  /** Agent KEY picked in the list: the whole panel its own, kept for the space shown. @param {string} key */
  pick(key, cx) {
    const space = spaces().find((s) => s.active)?.id;
    const live = new Set(spaces().map((s) => s.id));
    if (space) setShared(AGENT_CHOSEN, keepAgent(shared(AGENT_CHOSEN), space, key, live));
    Object.assign(this, { looking: null, failed: null });
    this.list(false, cx);
  }

  /** The list's rows the keys walk, in order (agentList()): a pick makes the panel that agent's; one not installed
   * is only looked at, the space keeping its agent. @param {Look} look */
  listRows(look) {
    return agentList(this.agents, look.programs, this.looking ?? look.agent).map((row) => ({ row,
      act: (/** @type {any} */ cx) => {
        if (!row.dim) return this.pick(row.key, cx);
        Object.assign(this, { looking: row.key, failed: null });
        this.list(false, cx);
      } }));
  }

  /** A key in the open list: ↑ ↓ step its rows (from the one in use), Enter or Space picks, Esc shuts it.
   * @param {ReturnType<AgentView["listRows"]>} rows */
  listKey(e, cx, rows) {
    if (e.key === "escape") return void this.list(false, cx);         // Esc goes on: a float takes the keys back
    if (e.key === "up" || e.key === "down") {
      this.cursor = panelStep(rows.length, this.cursor, e.key === "down" ? 1 : -1, () => false,
        rows.findIndex((one) => one.row.check));
    } else if ((e.key === "enter" || e.key === "space") && this.cursor !== null) rows[this.cursor]?.act(cx);
    else return;
    cx.stop_propagation();
    cx.notify();
  }

  /** What AGENT's panel offers in place of its setup done (ID: core's standing()'s): its own sign-in in a terminal
   * tab (looked at till it is in), its install line copied, its page opened. @param {import("./layers.js").Machine}
   * agent @param {string} id */
  offer(agent, id, cx) {
    if (id === "page") return void (/^https:\/\//.test(agent.page ?? "") && cx.open_url(agent.page));
    if (id === "copy") {
      cx.write_to_clipboard(agent.empty?.command ?? "");
      this.copied = true;
      cx.timer.after(COPIED, (/** @type {any} */ cx) => void ((this.copied = false), cx.notify()));
      return void cx.notify();
    }
    const tab = signInTab(agent, { space: spaces().find((s) => s.active)?.id, folder: this.folder });
    if (id !== "sign-in") return;
    if (!tab) return void ((this.failed = `Couldn't start ${agent.name}'s sign-in: no command for it`), cx.notify());
    command("tab.new", tab);
    this.signing = { key: agent.key, until: Date.now() + SIGNING_MS };
  }

  /** The folder and the agent's own folder under the home watched (watchSetup()). */
  watch(cx) {
    watchSetup(this, cx);
  }

  /** The setup read (one read at a time, once more after it when asked meanwhile): drawn anew where it changed, kept
   * where a read fails. */
  read(cx) {
    if (!this.folder || !READ.includes(this.agent)) return;
    if (this.busy) return void (this.again = true);
    this.readUsage(cx);
    const { key, agent, folder, session } = this, kept = Object.keys(this.checked).length > 0;
    const space = spaces().find((s) => s.active)?.id;
    Object.assign(this, { busy: true, readAt: Date.now() });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const found = await this.core(AGENT_LAYERS, [agent, folder,
          ...(agent === "claude" && session ? [session] : []),
          ...(agent === "claude" && kept ? ["--checked", JSON.stringify(this.checked)] : [])], folder, null);
        if (key !== this.key) return;
        this.states = found?.states ?? {};        // an answer is kept while its server's state is the one it had
        this.checked = Object.fromEntries(Object.entries(this.checked).filter(([name, one]) =>
          this.states[name] === one.base));
        if (space) tellProblems(space, found);
        const wanted = this.wants;
        if (wanted && wanted in this.states) {      // just added: Add and connect
          this.wants = null;
          if (this.states[wanted] === "sign in" && !this.checked[wanted]) this.connect(wanted, cx);
        }
        if (!this.error && this.missing === !found && JSON.stringify(found) === JSON.stringify(this.found)) return;
        Object.assign(this, { found, missing: !found, error: null });
        if (!this.edit?.touched) this.open(cx);     // an untouched form says what the files say now
        cx.notify();
      } catch (e) {
        if (key !== this.key || this.found) return;
        this.error = said(e);
        cx.notify();
      } finally {
        this.busy = false;
        if (this.again) {
          this.again = false;
          this.read(cx);
        }
      }
    });
  }

  /** SECTION folded or opened in the space shown, kept for it. @param {string} section */
  toggle(section, cx) {
    const space = spaces().find((s) => s.active)?.id;
    if (!space) return;
    setShared(AGENT_OPEN, keepOpen(shared(AGENT_OPEN), space, section, !sectionOpen(shared(AGENT_OPEN), space,
      section), new Set(spaces().map((s) => s.id))));
    cx.notify();
  }

  /** Row ID chosen, its properties and its form under the layers; the chosen one again: none. @param {string} id */
  choose(id, cx) {
    Object.assign(this, { chosen: this.chosen === id ? null : id, failed: null });
    this.open(cx, null);
    cx.notify();
  }

  /** The chosen row's form as core plans it (formAsk(); NAME: a built-in subagent picked), or none; an untouched
   * one of the same row planned again. @param {string | null} [name] */
  open(cx, name = this.edit?.name ?? null) {
    const row = chosenRow(this.found?.sections ?? [], this.chosen)?.row ?? null, edit = this.edit;
    const ask = formAsk(this.agent, this.chosen, row, this.found?.head ?? null, name);
    if (ask && edit && !edit.touched && JSON.stringify(ask) === JSON.stringify(edit.base)) return void this.plan(cx);
    this.start(ask, name, cx);
  }

  /** A form begun on ASK (null: none), its plan asked for. @param {Ask | null} ask @param {string | null} name */
  start(ask, name, cx) {
    this.edit = ask && { base: ask, ask, name, plan: null, inputs: {}, typed: {}, focus: null, touched: false,
      busy: false, error: null, note: null, submit: null, serial: 0, planned: 0 };
    if (ask) this.plan(cx);
  }

  /** The form's plan asked of core (harness.py plan: it writes nothing), the newest ask's answer alone kept; its text
   * fields get their inputs; Claude's own command alone goes to its chat (tell()). */
  plan(cx) {
    const edit = this.edit, { key, agent, folder } = this;
    if (!edit || !folder) return;
    const serial = ++edit.serial;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const plan = await this.core(HARNESS, ["plan", agent, folder, JSON.stringify(edit.ask)], folder, null);
        if (key !== this.key || this.edit !== edit || serial !== edit.serial) return;
        if (edit.touched && sayOnly(plan)) return void this.tell(plan.say, cx);
        Object.assign(edit, { plan, planned: serial, error: null, submit: plan.submit ?? edit.submit });
        for (const field of plan.fields) {
          if (field.kind === "text" && !edit.inputs[field.id]) this.input(edit, field, cx);
        }
      } catch (e) {
        if (this.edit === edit && serial === edit.serial) edit.error = said(e);
      }
      cx.notify();
    });
  }

  /** EDIT's input for the text FIELD, holding core's value: typed, it is planned once the keys rest (TYPING); Enter
   * saves; the keys start in a new rule's and a narrowed one's. @param {Edit} edit
   * @param {import("./layers.js").Field} field */
  input(edit, field, cx) {
    const input = (edit.inputs[field.id] = InputState.new({ placeholder: "" })), id = field.id;
    if (field.value) input.set_value(field.value);
    edit.typed[id] = field.value ?? "";
    input.on("change", (/** @type {any} */ _e, /** @type {any} */ cx) => {
      const value = input.value();
      if (this.edit !== edit || value === edit.typed[id]) return;
      edit.typed[id] = value;
      this.change({ [id]: value }, cx, TYPING);
    });
    input.on("submit", (/** @type {any} */ _e, /** @type {any} */ cx) => this.save(cx));
    input.on("blur", (/** @type {any} */ _e, /** @type {any} */ cx) => {
      if (edit.focus === id) edit.focus = null;
      cx.notify();
    });
    if (this.chosen !== RULE && id !== "to") return;
    edit.focus = id;
    cx.timer.after(0, () => input.focus());
  }

  /** A control chose OVER: planned anew (a typed field's after WAIT ms), the last save's foot gone.
   * @param {Record<string, any>} over @param {number} [wait] */
  change(over, cx, wait = 0) {
    const edit = this.edit;
    if (!edit || edit.busy) return;
    Object.assign(edit, { ask: asking(edit.ask, over), touched: true, note: null });
    this.foot = null;
    const serial = ++edit.serial;
    if (wait) cx.timer.after(wait, (/** @type {any} */ cx) => void (serial === edit.serial && this.plan(cx)));
    else this.plan(cx);
    cx.notify();
  }

  /** Cancel: a removal's question back to its form, a row's form as it opened, one with no row shut. */
  drop(cx) {
    if (this.edit?.ask.remove === true) this.change({ remove: undefined }, cx);
    else if (this.chosen && rowless(this.chosen)) this.choose(this.chosen, cx);
    else this.start(this.edit?.base ?? null, this.edit?.name ?? null, cx);
    cx.notify();
  }

  /** EDITS (a plan's, or a save's way back) passed to core unread (harness.py apply): all written, or none.
   * @param {any[]} edits @returns {Promise<{ applied: boolean, error: string | null, undo: any[] }>} */
  write(edits) {
    return this.core(HARNESS, ["apply", this.agent, String(this.folder), JSON.stringify(edits)], this.folder, null);
  }

  /** Save: the plan's edits written; the foot then says so with its way back, the setup is read again and the form
   * opens on what was written (afterSave()); refused, core's words under the form. */
  save(cx) {
    const edit = this.edit, plan = edit?.plan, { key } = this;
    if (!edit || !plan?.submit || edit.busy || edit.planned !== edit.serial || !this.folder) return;
    edit.busy = true;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const done = await this.write(plan.edits);
        if (key !== this.key) return;
        if (!done.applied) return void (edit.error = done.error);
        this.foot = { ...footWords(plan), undo: done.undo, word: plan.undo, error: null, busy: false };
        if (this.edit === edit) {
          const next = afterSave(edit.base, edit.ask, plan);
          this.chosen = next ? next.chosen ?? this.chosen : null;
          this.start(next?.ask ?? null, edit.name, cx);
        }
        this.read(cx);
      } catch (e) {
        edit.error = said(e);
      } finally {
        edit.busy = false;
        cx.notify();
      }
    });
  }

  /** Undo: the last save's way back written, the foot gone and the setup read again; refused (the file changed
   * since), core's words in the foot. */
  undo(cx) {
    const foot = this.foot, { key } = this;
    if (!foot || foot.busy || !this.folder) return;
    foot.busy = true;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const done = await this.write(foot.undo);
        if (key !== this.key || this.foot !== foot) return;
        if (!done.applied) return void (foot.error = done.error);
        this.foot = null;
        if (!this.edit?.touched) this.open(cx);
        this.read(cx);
      } catch (e) {
        foot.error = said(e);
      } finally {
        foot.busy = false;
        cx.notify();
      }
    });
  }

  /** ROW of SECTION shown and chosen, as a problem's chip and openAgentPanel() ask: the filter emptied, its section
   * opened and scrolled to (a problem stands first in it). @param {string | null} section @param {string | null} row */
  reveal(section, row, cx) {
    const sections = /** @type {Section[]} */ (this.found?.sections ?? []);
    const inside = chosenRow(sections, row)?.section.id ?? section, space = spaces().find((s) => s.active)?.id;
    if (this.finding) this.search(cx);
    if (row && chosenRow(sections, row) && row !== this.chosen) {
      Object.assign(this, { chosen: row, failed: null });
      this.open(cx, null);
    }
    const at = sections.findIndex((one) => one.id === inside);
    if (at >= 0 && space && !sectionOpen(shared(AGENT_OPEN), space, String(inside))) this.toggle(String(inside), cx);
    const lead = this.usageRows().length || this.usageError ? 2 : 0;    // Usage over them, its head and its rows
    if (at >= 0) this.scroll.scroll_to_item(lead + at * 2);     // a section is its head, then its rows
    cx.notify();
  }

  /** From render: openAgentPanel()'s ask for SPACE answered once (after the first read, where a row is asked for),
   * the agent it looks at shown (none: the panel's own). @param {string} space */
  answer(space, cx) {
    const ask = asked(shared(AGENT_ASK), space, this.answered, Date.now());
    if (ask) Object.assign(this, { answered: ask.at, waits: { section: ask.section ?? null, row: ask.row ?? null } });
    const look = typeof ask?.look === "string" ? ask.look : null;
    if (ask && look !== this.looking) Object.assign(this, { looking: look, failed: null });
    if (!this.waits || !this.found) return;
    const { section, row } = this.waits;
    this.waits = null;
    cx.timer.after(0, (/** @type {any} */ cx) => this.reveal(section, row, cx));
  }

  /** ACTION of the chosen row done: a file in the preview tab, its node in the Agents tab's graph, else the agent's
   * own command on its server (core's words for each: connectors.py). @param {import("./layers.js").Action} action */
  act(action, cx) {
    if (action.id === "usage") return void this.graph?.({ view: "usage" });
    if (action.id === "graph") {
      return void (this.chosen && this.graph?.({ node: this.chosen, session: this.session ?? null }));
    }
    if (action.id === "open" && action.path) return showFile(action.path);
    const name = action.server;
    if (!name || !this.folder) return;
    if (action.id === "retry") this.check(name, cx);
    else if (action.id === "connect") this.connect(name, cx);
    else if (action.id === "reopen") this.reopen(name, cx);
    else if (action.id === "cancel") this.cancel(name, cx);
    else if (action.id === "sign-out") this.signOut(name, cx);
  }

  /** Claude's own look at its server NAME (`claude mcp get`), its state a spinner meanwhile, its answer shown by the
   * next read; THEN gets the answer (after a server was added). @param {string} name
   * @param {((answer: any, cx: any) => void) | null} [then] */
  check(name, cx, then = null) {
    const { key, folder } = this;
    if (!folder || this.checking.has(name)) return;
    this.checking.add(name);
    this.failed = null;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      let asked = null;
      try {
        const answer = await this.core(AGENT_STATE, ["check", "claude", folder, name], folder, null);
        if (key !== this.key) return;
        this.checked[name] = { base: this.states[name] ?? null, state: answer.state, error: answer.error ?? null };
        asked = answer;
      } catch (e) {
        if (key === this.key) this.failed = `Couldn't check ${name}: ${said(e)}`;
      } finally {
        if (key === this.key) {
          this.checking.delete(name);
          this.read(cx);
          cx.notify();
        }
      }
      if (asked && key === this.key) then?.(asked, cx);
    });
  }

  /** The sign-ins running for the agent shown, by server: the app's own list of terminals tells them, so every copy
   * of the panel shows the same, and one outlives a panel drawn anew. */
  signingIn() {
    return signIns(terminals(), this.agent);
  }

  /** Every WATCH: a sign-in left waiting past its time is ended; a server seen signing in whose terminal is gone
   * (signed in, cancelled: its exit code tells neither) is asked about again. */
  watchSignIns(cx) {
    for (const address of overdue(terminals(), Date.now())) hc(["kill", "--", address]);
    const running = this.signingIn(), ended = [...this.signed].filter((name) => !running[name]);
    const now = Date.now(), due = this.due.some((at) => at <= now);
    this.signed = new Set(Object.keys(running));
    this.due = this.due.filter((at) => at > now);
    for (const name of ended) this.settle(name, cx);
    if (due) this.read(cx);
    if (ended.length) cx.notify();
  }

  /** Server NAME's state asked for anew after its agent's command ended: Claude checks it (a session's lines tell
   * nothing new), Codex's own list is read again. @param {string} name */
  settle(name, cx) {
    if (this.agent === "claude") this.check(name, cx);
    else this.read(cx);
  }

  /** The agent's own WORK on server NAME, its row's state a spinner meanwhile; what it could not do (WHY, then its
   * own last line) under the properties; what WORK answers is done once the spinner is let go. @param {string} name
   * @param {string} why @param {(cx: any) => Promise<((cx: any) => void) | void>} work */
  run(name, why, cx, work) {
    const { key } = this;
    if (this.checking.has(name)) return;
    this.checking.add(name);
    this.failed = null;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      let next;
      try {
        next = await work(cx);
      } catch (e) {
        if (key === this.key) this.failed = `${why}: ${said(e)}`;
      } finally {
        if (key === this.key) {
          this.checking.delete(name);
          cx.notify();
        }
      }
      if (next && key === this.key) next(cx);
    });
  }

  /** Connect: the agent's own login for its server NAME (`claude mcp login`, `codex mcp login`: it needs a terminal
   * and opens the browser) in a terminal with no pane, one per server; its row signs in till that ends.
   * @param {string} name */
  connect(name, cx) {
    const { agent, folder } = this;
    if (!folder || this.signingIn()[name]) return;
    this.run(name, `Couldn't start ${name}'s sign-in`, cx, async () => {
      const argv = await this.core(CONNECTORS, ["login", agent, name], folder, null);
      const done = await hc(loginRun(argv, { agent, name, folder, at: Date.now() }));
      if (done.code !== 0) throw new Error(lastLine(done));
      this.signed.add(name);
    });
  }

  /** Open the page again: the address NAME's sign-in printed on its screen, checked by core, in the browser; it is
   * never kept. @param {string} name */
  reopen(name, cx) {
    const { folder } = this, one = this.signingIn()[name];
    if (!folder || !one) return;
    this.run(name, "Couldn't open the page", cx, async (cx) => {
      const screen = await hc(["read", one.address, "--lines", READ_LINES]);
      const printed = screen.code === 0 ? printedAddress(screen.stdout) : null;
      const url = printed ? await this.core(CONNECTORS, ["login-url", `${printed}\n`], folder, null) : null;
      if (!url) throw new Error("its address is not printed yet");
      if (typeof cx.open_url === "function") cx.open_url(url);
      else await exec("open", [url]);
    });
  }

  /** Cancel: NAME's sign-in ended; the next look asks its agent about it again. @param {string} name */
  cancel(name, cx) {
    const one = this.signingIn()[name];
    if (one) hc(["kill", "--", one.address]);
    this.failed = null;
    cx.notify();
  }

  /** Sign out: the agent's own logout for its server NAME, then its state asked for anew. @param {string} name */
  signOut(name, cx) {
    const { agent, folder } = this;
    if (!folder) return;
    this.run(name, `Couldn't sign out of ${name}`, cx, async () => {
      const argv = await this.core(CONNECTORS, ["logout", agent, name], folder, null);
      const done = await exec(argv[0], argv.slice(1), { cwd: folder });
      if (done.code !== 0) throw new Error(lastLine(done));
      return (/** @type {any} */ cx) => this.settle(name, cx);
    });
  }

  /** The folder's Claude a server its own state turned off is turned on through (claudeIn's): a chat of the space
   * shown, or Claude in a pane there; null with none (core's words say what the form waits for). */
  chat() {
    return this.agent === "claude" ? claudeIn(spaces().find((s) => s.active) ?? null, paneAgents(), panes(),
      terminals(), CHAT_TAB) : null;
  }

  /** The form's server turned on by Claude's own command (SAID, a plan's: no file holds it), sent to the folder's
   * Claude once it is idle, the setup read again as Claude writes it; the form as it opened, and with no Claude
   * there core's words for what it waits for. @param {string[]} lines */
  tell(lines, cx) {
    const edit = /** @type {Edit} */ (this.edit), to = this.chat();
    this.start(edit.base, edit.name, cx);
    if (!to) return void Object.assign(this.edit ?? {}, { note: this.found?.connect?.needs?.["turn-on"] ?? null });
    this.run(edit.base.name, "Couldn't tell Claude", cx, async () => {
      for (const words of lines) {
        const sent = await hc(["send", "--if", "idle", to, words]);
        if (sent.code !== 0) throw new Error(lastLine(sent));
      }
      this.due = SETTLE.map((ms) => Date.now() + ms);
    });
  }

  /** Connectors' + pressed: its menu shown or shut, the keys on no row; Codex adds one way: the form at once.
   * @param {boolean} open */
  showWays(open, cx) {
    const ways = this.found?.connect?.add?.menu ?? [];
    if (open && ways.length === 1) return this.add(ways[0], cx);
    Object.assign(this, { addMenu: open && ways.length > 0 });
    this.addList.cursor = null;
    cx.notify();
  }

  /** A way to add a connector picked (core's: its page in the browser, or the form in the properties' place, the keys
   * in its first field). @param {{ id: string, url: string | null }} way */
  add(way, cx) {
    this.addMenu = false;
    if (way.url) cx.open_url(way.url);
    else {
      const [name, url] = [InputState.new({ placeholder: "" }), InputState.new({ placeholder: "" })];
      const form = (this.form = { name, url, scope: "local", focus: "name", error: null, busy: false });
      for (const [field, input] of /** @type {["name" | "url", any][]} */ ([["name", name], ["url", url]])) {
        input.on("submit", (/** @type {any} */ _e, /** @type {any} */ cx) => this.submit(cx));
        input.on("change", (/** @type {any} */ _e, /** @type {any} */ cx) => {
          if (form.error?.field !== field) return;
          form.error = null;                      // typed over: no longer what was refused
          cx.notify();
        });
        input.on("blur", (/** @type {any} */ _e, /** @type {any} */ cx) => {
          if (form.focus === field) form.focus = null;
          cx.notify();
        });
      }
      cx.timer.after(0, () => name.focus());
    }
    cx.notify();
  }

  /** The form's keys go to FIELD (Tab steps to the other one). @param {"name" | "url"} field */
  focusField(field, cx) {
    if (!this.form) return;
    this.form.focus = field;
    this.form[field].focus();
    cx.notify();
  }

  /** The form left as it is: nothing added. */
  dropForm(cx) {
    this.form = null;
    cx.notify();
  }

  /** Add and connect: core checks the form (a refused field says why under it, the keys back in it), then the agent's
   * own `mcp add` runs in the folder; its failure is said in the form in its own words. Added: its row chosen, and
   * signed in to once its agent says it must be. */
  submit(cx) {
    const form = this.form, { key, agent, folder } = this;
    if (!form || form.busy || !folder) return;
    const scoped = (this.found?.connect?.add?.scopes ?? []).length > 0;
    Object.assign(form, { busy: true, error: null });
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const made = await this.core(CONNECTORS, ["form", agent, form.name.value(), form.url.value(),
          ...(scoped ? [form.scope] : [])], folder, null);
        if (key !== this.key || this.form !== form) return;
        if (made.error) {
          form.error = made;
          return void this.focusField(made.field, cx);
        }
        const done = await exec(made.argv[0], made.argv.slice(1), { cwd: folder });
        if (key !== this.key) return;
        if (done.code !== 0) return void (form.error = { field: null, error: lastLine(done) });
        Object.assign(this, { form: this.form === form ? null : this.form, chosen: `${SERVER}${made.name}`,
          failed: null, wants: agent === "claude" ? null : made.name });
        if (agent !== "claude") return void this.read(cx);      // Codex's own list tells whether it must sign in
        // a session's lines do not know it yet: Claude looks at it, and says whether it must sign in
        this.check(made.name, cx, (/** @type {any} */ answer, /** @type {any} */ cx) => void (answer.state
          === "sign in" && this.connect(made.name, cx)));
      } catch (e) {
        if (this.form === form) form.error = { field: null, error: said(e) };
      } finally {
        form.busy = false;
        cx.notify();
      }
    });
  }

  /** The head's search: the filter shown with the keys, or hidden and emptied. */
  search(cx) {
    this.finding = !this.finding;
    if (this.finding) cx.timer.after(0, () => this.find.focus());
    else this.find.set_value("");
    cx.notify();
  }

  render(t, cx) {
    const here = agentHere(), space = here.space;
    this.follow(here, cx);
    if (!space?.folder || space.machine) {        // another machine's setup is read with a later version
      return this.frame(t).child(this.say(t, space?.machine ? `On ${space.machine}: with a later version`
        : "No folder"));
    }
    this.answer(space.id, cx);
    return this.draw(t, { agent: here.agent, programs: programs(cx), px: this.floating ? PANEL_PX
      : panelPx(layout()) ?? PANEL_PX, open: (section) => sectionOpen(shared(AGENT_OPEN), space.id, section) });
  }

  /** The view's frame. */
  frame(t) {
    return v_flex().id("agent").size_full().min_h(0).text_color(t.foreground).text_size(13);
  }

  /** The panel as LOOK has it: the head, the filter, its line and bar (loads()), the layers, the chosen row's
   * properties or the add form; else what it says instead (loading, a failure, not installed, not signed in).
   * @param {Look} look */
  draw(t, look) {
    const found = this.found, frame = this.frame(t), sections = found ? this.sections(found) : [];
    const usage = this.usageRows(), add = found?.connect?.add ?? null;
    const picked = usage.find((row) => `usage:${row.key}` === this.chosen);
    const chosen = picked ? usageRow(picked, (resets) => this.resetSaid(resets)) : chosenRow(sections,
      this.chosen)?.row ?? null;
    const agent = agentOf(this.agents, this.looking ?? look.agent);
    if (agent?.empty || !READ.includes(look.agent)) {       // where it stands; no setup of it read: its head alone
      const key = agent?.key ?? look.agent, name = agent?.name ?? NAMES[key] ?? look.programs[key]?.name ?? key;
      const head = frame.child(this.head(t, { name, where: `in ${(this.folder ?? "").split("/").pop()}` },
        { ...look, agent: key }, false));
      return agent?.empty ? head.child(this.standing(t, agent, look)) : head;
    }
    if (!found) {
      return frame.child(this.missing ? this.say(t, `${NAMES[look.agent] ?? look.agent} is not installed`)
        : this.error ? this.say(t, `Couldn't read the setup: ${this.error}`, t.ansi1) : this.say(t, "Loading setup…"));
    }
    const alone = !chosen && !this.form && rowless(this.chosen) ? this.editing(t, null) : [];
    return frame.child(this.head(t, found.head, look))
      .when(this.finding, (e) => e.child(div().flex_none().px(PAD).pb(8).child(field(t, "agent-filter", this.find))))
      .child(this.loads(t, found))
      .child(this.layers(t, sections, usage, look))
      .when(Boolean(this.form && add), (e) => e.child(this.adder(t, add)))
      .when(Boolean(chosen) && !this.form, (e) => e.child(this.properties(t, /** @type {Row} */ (chosen), look)))
      .when(alone.length > 0, (e) => e.child(this.sheet(t, `agent-properties-${this.slides}`).children(alone)
        .children([this.buttons(t, [], false)].filter(Boolean))))
      .when(Boolean(this.foot), (e) => e.child(this.footed(t)));
  }

  /** The properties' frame (connectors.html's .insp), a form's too: on the side's level under a hairline, 12 in, its
   * parts 6 apart; with a row's FORM in it, Esc leaves a touched one. @param {string} id @param {boolean} [form] */
  sheet(t, id, form = true) {
    return v_flex().id(id).flex_none().p(PAD).gap(6).border_t(1).border_color(t.border).bg(t.chrome).text_size(12)
      .when(form, (e) => e.on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => void (e.key === "escape"
        && this.edit?.touched && this.drop(cx))));  // Esc goes on: a float takes the keys back
  }

  /** Usage's rows (usageRows()): the agents on a plan as core read them, those on an API key from today's report. */
  usageRows() {
    return usageRows(this.usage, this.report, usageAgents(this.agents), this.agent ?? null);
  }

  /** RESETS' words with this Mac's time and day in them (resetWords()).
   * @param {{ at: number, words: string }} resets */
  resetSaid(resets) {
    const when = new Date(resets.at * 1000);
    return resetWords(resets, written(when, "time"), format(when, "EEE"));
  }

  /** FOUND's sections as they are drawn: a connector whose agent signs in now says so, in core's words.
   * @param {any} found @returns {Section[]} */
  sections(found) {
    const signing = found.connect ? this.signingIn() : {};
    return !Object.keys(signing).length ? found.sections : found.sections.map((/** @type {Section} */ section) =>
      (section.id !== "connectors" ? section : { ...section, rows: section.rows.map((row) =>
        (signing[serverOf(row) ?? ""] ? signingRow(row, found.connect) : row)) }));
  }

  /** WORDS in the first row's place, as every list says what it has instead of rows. @param {string} words
   * @param {string} [color] */
  say(t, words, color = t.muted) {
    return div().flex_none().p(PAD).text_size(12).text_color(color).child(words);
  }

  /** The head: the agent's chip (its icon, its name and where, core's words, ⌄: a press opens the agents' list under
   * it, lit while open), the search at its end where there is a setup to FILTER, lit while it does.
   * @param {{ name: string, where: string }} head @param {Look} look @param {boolean} [filter] */
  head(t, head, look, filter = true) {
    const mark = agentMark(look.programs[look.agent], 14), open = this.listing, clear = `${t.accent}00`;
    const chip = h_flex().id(`agent-chip-${this.slides}`).h(BUTTON).min_w(0)
      .max_w(look.px - 2 * PAD - (filter ? BUTTON + 8 : 0)).px(6).gap(6).items_center().rounded(6).border_1()
      .border_color(open ? t.accent : clear).cursor_pointer()
      .when(open, (e) => e.bg(t.raised)).hover((/** @type {any} */ s) => s.bg(open ? t.raised : t.hover))
      .when(Boolean(mark), (e) => e.child(mark))
      .child(div().flex_none().font_semibold().child(head.name))
      .child(div().min_w(0).truncate().text_color(t.muted).child(head.where))
      .child(icon("chevron-down", 12).text_color(t.dim));
    return h_flex().flex_none().mt(PAD).mb(6).px(PAD / 2).gap(8).items_center()
      .child(h_flex().flex_1().min_w(0).child(Popover.new(`agent-list-${this.slides}`).anchor("top_left").open(open)
        .when(!this.still, (/** @type {any} */ e) => e.track_focus(this.listFocus))
        .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) => this.list(opened, cx))
        .trigger(chip).when(open && !this.still, (/** @type {any} */ e) => e.content(this.listed(t, look).mt(4)))))
      .when(filter, (e) => e.child(div().pr(PAD / 2).child(iconButton(t, "agent-search", "search", "Filter setup",
        (/** @type {any} */ cx) => this.search(cx), { lit: this.finding }))));
  }

  /** The head's list (agent-picker.html's .agm, the chat bar's panels' form) in core's words: each group's head, a
   * rule over the second; a row ✓ on the one shown, its icon, its name, at its end its plan's word dim or sign in
   * in yellow; one not installed dim. A press or Enter picks; ↑ ↓ step. @param {Look} look */
  listed(t, look) {
    const rows = this.listRows(look), ground = t.popover ?? t.raised;
    const head = (/** @type {string} */ words) => div().flex_none().px(PAD).pt(6).pb(4).text_size(12)
      .line_height("16px").font_semibold().text_color(t.muted).child(words);
    const drawn = rows.flatMap(({ row, act }, n) => {
      const line = panelRow(t, this, n, true, row.check).id(`agent-pick-${this.slides}${row.key}`)
        .line_height("16px").cursor_pointer().on_click((/** @type {any} */ _e, /** @type {any} */ cx) => act(cx))
        .child(div().w(CHECK).flex_none().flex().justify_center()
          .when(row.check, (e) => e.child(icon("check", CHECK).text_color(t.accent))))
        .child(div().flex_none().when(row.dim, (e) => e.opacity(0.6))
          .child(agentMark(look.programs[row.key], 16) ?? icon("bot", 16).text_color(t.muted)))
        .child(div().flex_1().min_w(0).truncate().when(row.dim, (e) => e.text_color(t.muted)).child(row.name))
        .when(Boolean(row.word), (e) => e.child(div().flex_none().text_size(12)
          .text_color(row.warn ? toneInk(t, "warn", ground) : t.muted).child(row.word ?? "")));
      return row.group === rows[n - 1]?.row.group ? [line] : [...(n ? [rule(t)] : []), head(row.group), line];
    });
    const none = this.agentsError ? listNote(t, `Couldn't list the agents: ${this.agentsError}`, true, PAD)
      : !this.agents ? listNote(t, "Loading agents…", false, PAD) : null;
    return panelSurface(t, `agent-list-surface-${this.slides}`, Math.min(LIST, look.px - PAD)).p(4).gap(2)
      .when(!this.still, (e) => e.track_focus(this.listFocus).on_key_down((/** @type {any} */ e,
        /** @type {any} */ cx) => this.listKey(e, cx, rows)))
      .when(Boolean(none), (e) => e.child(none))
      .children(drawn);
  }

  /** Where AGENT stands in its setup's place (connectors.html's .signin; core's standing()'s words), centered: its
   * icon, the title, the words, its install line with Copy, what can be done (Sign in on the accent, its page), the
   * last line dim. @param {import("./layers.js").Machine} agent @param {Look} look */
  standing(t, agent, look) {
    const says = /** @type {NonNullable<import("./layers.js").Machine["empty"]>} */ (agent.empty);
    const does = (/** @type {string} */ id) => says.actions.find((one) => one.id === id);
    const signIn = does("sign-in"), page = does("page"), copy = does("copy"), key = `agent-says-${this.slides}`;
    return v_flex().id(key).flex_1().min_h(0).p(24).gap(8).items_center().justify_center().text_size(12)
      .child(agentMark(look.programs[agent.key], MARK) ?? icon("bot", MARK).text_color(t.muted))
      .child(div().pt(4).text_size(13).font_semibold().text_center().child(says.title))
      .child(div().max_w(SAID).line_height("18px").text_center().text_color(t.muted).child(says.words))
      .when(Boolean(says.command), (e) => e.child(h_flex().max_w_full().h(28).pl(8).pr(2).gap(4).items_center()
        .rounded(6).bg(t.canvas)
        .child(div().min_w(0).truncate().font_family(codeFont()).text_size(11).child(says.command ?? ""))
        .when(Boolean(copy), (e) => e.child(iconButton(t, `${key}-copy`, this.copied ? "check" : "copy",
          this.copied ? "Copied" : copy?.label ?? "", (/** @type {any} */ cx) => this.offer(agent, "copy", cx))))))
      .when(Boolean(signIn), (e) => e.child(div().id(`${key}-sign-in`).mt(4).h(ACTION).px(PAD).flex().items_center()
        .rounded(8).bg(t.solid).text_color(t.solid_foreground).font_bold().cursor_pointer()
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.offer(agent, "sign-in", cx))
        .child(signIn?.label ?? "")))
      .when(Boolean(page), (e) => e.child(h_flex().id(`${key}-page`).h(ACTION).px(PAD).gap(6).items_center()
        .rounded(8).text_color(t.muted).cursor_pointer()
        .hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.offer(agent, "page", cx))
        .child(page?.label ?? "").child(icon("external-link", 12))))
      .when(Boolean(this.failed), (e) => e.child(div().max_w(SAID).text_size(11).text_center()
        .text_color(toneInk(t, "bad")).child(this.failed ?? "")))
      .when(Boolean(says.foot), (e) => e.child(div().text_size(11).text_color(t.muted).text_center()
        .child(says.foot ?? "")));
  }

  /** What loads at start under the head (connectors.html's .kline, .health): FOUND's head line in its words, the
   * problems as chips at its end (a press chooses a chip's row), an unread file's error (the file its tip), the bar
   * of rules, skills and connectors each by its share in its part's color. @param {any} found */
  loads(t, found) {
    const parts = /** @type {{ part: string, tokens: number }[]} */ (found.bar).filter((one) => one.tokens > 0);
    const [first, rest] = headParts(found.head), lit = this.chosen === MODEL, fill = chosenFill(t);
    return v_flex().flex_none().pb(8).gap(6).border_b(1).border_color(t.border)
      .child(h_flex().h(20).pl(first ? 8 : PAD).pr(PAD).gap(8).items_center().text_size(12)
        .child(h_flex().flex_1().min_w(0).h_full().items_center().text_color(t.muted)
          .when(Boolean(first), (e) => e.child(div().id(`agent-model-${this.slides}`).h_full().flex_none().px(4)
            .flex().items_center().rounded(4).cursor_pointer().when(lit, (e) => e.bg(fill).text_color(t.foreground))
            .hover((/** @type {any} */ s) => s.bg(lit ? fill : t.hover).text_color(t.foreground))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(MODEL, cx)).child(first)))
          .child(div().min_w(0).truncate().child(rest)))
        .children(found.head.problems.map((/** @type {any} */ one, /** @type {number} */ n) => {
          const { fill, ink } = chipColors(t, one.tone), over = chipColors(t, one.tone, CHIP_LIFT);
          return div().id(`agent-problem-${this.slides}${n}`).h(18).flex_none().px(6).flex().items_center()
            .rounded(4).bg(fill).text_size(11).line_height("16px").font_medium().text_color(ink).cursor_pointer()
            .hover((/** @type {any} */ s) => s.bg(over.fill).text_color(over.ink))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.reveal(null, one.row, cx))
            .child(one.text);
        })))
      .when(Boolean(found.error), (e) => e.child(div().id(`agent-error-${this.slides}`).px(PAD).truncate()
        .text_size(12).text_color(toneInk(t, "bad")).when(Boolean(found.error?.tip), (e) => e.tooltip(found.error.tip))
        .child(found.error?.text ?? "")))
      .when(parts.length > 0, (e) => e.child(div().flex_none().px(PAD).child(h_flex().h(6).gap(2).rounded_full()
        .overflow_hidden().bg(t.canvas).children(parts.map((one, n) => div().h_full().min_w(6).flex_basis(0)
          .flex_grow(one.tokens)
          .when(n === 0, (e) => e.rounded_l(3)).when(n === parts.length - 1, (e) => e.rounded_r(3))   // its own ends:
          .bg(partColor(t, one.part)))))));                             // the track's corners do not clip a part
  }

  /** The sections, each its head and its rows sprung open under it (a group's head and rows after them), Usage first;
   * with a filter typed, those with a row it finds, all open, no Usage; none found, said in the first one's place.
   * @param {Section[]} sections @param {Usage[]} usage Usage's rows @param {Look} look */
  layers(t, sections, usage, look) {
    const wide = look.px >= NARROW;
    const parts = sections.map((section) => ({ section, ...shown(section, { query: this.query, more: this.more,
      chosen: this.chosen }) })).filter((part) => !this.query || part.rows.length || part.groups.length);
    const more = (/** @type {string} */ id, /** @type {number} */ left) => this.line(t, `${left} more`, MORE_H)
      .id(`agent-more-${this.slides}${id}`).rounded(6).cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
      .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
        this.more.add(id);
        cx.notify();
      });
    return v_flex().id("agent-layers").flex_1().min_h(0).overflow_y_scrollbar().track_scroll(this.scroll)
      .px(PAD / 2).py(4).gap(2).text_size(12)
      .when(!parts.length, (e) => e.child(h_flex().h(ROW_H).flex_none().px(PAD / 2).text_color(t.muted)
        .child("Nothing matches")))
      .when(!this.query && Boolean(usage.length || this.usage || this.usageError), (e) => e.children(this.limits(t,
        usage, look)))
      .children(parts.flatMap((part) => {
        const { section, rows, groups } = part, open = Boolean(this.query) || look.open(section.id);
        const add = section.id === "connectors" ? this.found?.connect?.add ?? null : null;
        const rule = section.id === "permissions" && formAsk(look.agent, RULE, null, null)
          ? this.plusMark(t, `agent-rule-add-${this.slides}`, this.chosen === RULE)
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(RULE, cx)) : null;
        const tags = wide ? tagRoom(section) : 0, empty = !section.rows.length && !(section.groups ?? []).length;
        const drawn = (/** @type {Row[]} */ some, /** @type {string} */ key) => some.map((row, n) => this.row(t,
          section, row, `${key}-${n}`, tags, look));
        return [this.section(t, section, open && !empty, add, rule, empty), v_flex()
          .id(`agent-rows-${this.slides}${section.id}`).flex_none().overflow_hidden()
          .h(open ? bodyHeight(part) : 0).spring("height", SPRING)
          .when(!rows.length && !groups.length, (e) => e.child(this.line(t, `No ${section.title.toLowerCase()}`,
            ROW_H)))
          .children(drawn(rows, section.id))
          .when(part.more > 0, (e) => e.child(more(section.id, part.more)))
          .children(groups.flatMap((group) => [this.group(t, group, look),
            ...drawn(group.rows, group.id), ...(group.more > 0 ? [more(group.id, group.more)] : [])]))];
      }));
  }

  /** A GROUP's head (Hooks): its title and count 11 from the names' column, its state (off here) at its end; where
   * it has a form (Claude's: all hooks off or on) a press chooses it. @param {import("./layers.js").Group} group
   * @param {Look} look */
  group(t, group, look) {
    const chosen = this.chosen === group.id, ground = chosen ? chosenFill(t) : t.surface;
    return h_flex().id(`agent-group-${this.slides}${group.id}`).h(GROUP_H).flex_none().pl(NAME_IN).pr(PAD / 2).gap(6)
      .items_center().rounded(6).text_size(11).text_color(t.muted).when(chosen, (e) => e.bg(ground))
      .when(Boolean(formAsk(look.agent, group.id, null, null)), (e) => e.cursor_pointer()
        .when(!chosen, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(group.id, cx)))
      .child(group.title).child(String(group.count)).child(div().flex_1())
      .when(Boolean(group.state), (e) => e.child(div().flex_none().text_color(toneInk(t, group.state?.tone ?? "",
        ground)).child(group.state?.text ?? "")));
  }

  /** Usage, the first section (usage-agents.html; core's words): its head with Open Usage at its end, folded with one
   * figure before it (headline()); a row an agent (USAGE), a press choosing it (its properties under the layers);
   * none known, or the read failed: said in their place. @param {Usage[]} usage @param {Look} look */
  limits(t, usage, look) {
    const open = look.open("usage"), shown = open ? null : headline(usage);
    const none = this.usageError ? `Couldn't read the limits: ${this.usageError}` : this.usage?.none ?? "";
    const opens = div().id(`agent-usage-open-${this.slides}`).size(ADD).flex_none().flex().items_center()
      .justify_center().rounded(6).text_color(t.muted).tooltip("Open Usage")
      .when(!this.still, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.raised)
        .text_color(t.foreground)).on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
        cx.stop_propagation();
        this.graph?.({ view: "usage" });
      })).child(icon("external-link", 14));
    const end = h_flex().flex_none().gap(4).items_center()
      .when(Boolean(shown), (e) => e.child(this.headFigure(t, /** @type {Usage} */ (shown), look))).child(opens);
    return [this.section(t, { id: "usage", title: "Usage", count: null, cost: null, swatch: null, summary: [],
      rows: [], groups: [] }, open, null, end),
    v_flex().id(`agent-usage-${this.slides}`).flex_none().overflow_hidden().h(open ? usageHeight(usage) : 0)
      .spring("height", SPRING)
      .when(!usage.length, (e) => e.child(this.line(t, none, ROW_H)
        .when(Boolean(this.usageError), (e) => e.text_color(toneInk(t, "bad")))))
      .children(usage.flatMap((row, n) => this.meter(t, row, n, look)))];
  }

  /** Usage's head folded (usage-agents.html's .hfig): ROW's agent's mark, then its figure, its words muted and the
   * figure semibold in its level's color; a press opens the section. @param {Usage} row @param {Look} look */
  headFigure(t, row, look) {
    const one = usageFigure(row);
    return h_flex().id(`agent-usage-head-${this.slides}`).flex_none().gap(6).items_center().text_size(11)
      .text_color(t.muted).when(!this.still, (e) => e.cursor_pointer()
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.toggle("usage", cx)))
      .child(agentMark(look.programs[row.key], 14) ?? icon("bot", 14).text_color(t.muted))
      .child(this.figure(t, one?.label ?? "", one?.figure ?? "", one?.level ?? null, one?.after ?? "", t.surface));
  }

  /** A figure as Usage's rows end with it: LABEL muted, the FIGURE semibold in LEVEL's color read on GROUND (muted
   * with none: "–"), AFTER muted. @param {string} label @param {string} figure @param {string | null} level
   * @param {string} after @param {string} ground */
  figure(t, label, figure, level, after, ground) {
    return h_flex().flex_none().gap(4).justify_end().text_size(11).text_color(t.muted)
      .when(Boolean(label), (e) => e.child(div().child(label)))
      .child(div().font_semibold().when(Boolean(level), (e) => e.text_color(levelInk(t, level ?? "", ground)))
        .child(figure))
      .when(Boolean(after), (e) => e.child(div().child(after)));
  }

  /** ROW of Usage, the N-th (usage-agents.html's): icon, name, plan; a plan's two windows in their levels (no bars
   * under NARROW), an API key's month, or core's words for no reading; under it, only while yellow or red, the reset
   * or the pace. A press chooses it. @param {Usage} row @param {number} n @param {Look} look */
  meter(t, row, n, look) {
    const id = `usage:${row.key}`, chosen = this.chosen === id, ground = chosen ? chosenFill(t) : t.surface;
    const bars = look.px >= NARROW;
    const window = (/** @type {import("./layers.js").Meter | null} */ one) => h_flex().w(WINDOW).flex_none().gap(4)
      .justify_end().items_center().text_size(11).text_color(t.muted)
      .when(Boolean(one), (e) => e.child(div().child(one?.label ?? ""))
        .when(bars, (e) => e.child(h_flex().w(METER).h(4).flex_none().rounded_full().overflow_hidden().bg(t.raised)
          .child(div().h_full().flex_basis(0).flex_grow(Math.max(0, Math.min(100, one?.used ?? 0))).rounded_full()
            .bg(levelFill(t, one?.level ?? "")))
          .child(div().h_full().flex_basis(0).flex_grow(100 - Math.max(0, Math.min(100, one?.used ?? 0))))))
        .child(div().font_semibold().when(Boolean(one?.level), (e) => e.text_color(levelInk(t, one?.level ?? "",
          ground))).child(one?.text ?? "")));
    const under = row.reset ? this.resetSaid(row.reset) : (bars ? row.month?.pace?.text : row.month?.pace?.narrow)
      ?? "";
    return [h_flex().id(`agent-usage-${this.slides}${n}`).h(ROW_H).flex_none().pl(INSET).pr(PAD / 2).gap(6)
      .items_center().rounded(6).when(chosen, (e) => e.bg(ground))
      .when(!this.still, (e) => e.cursor_pointer().when(!chosen, (e) => e.hover((/** @type {any} */ s) =>
        s.bg(t.hover))).on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(id, cx)))
      .child(div().w(MARKS).flex_none())
      .child(agentMark(look.programs[row.key], 14) ?? icon("bot", 14).text_color(t.muted))
      .child(h_flex().flex_1().min_w(0).gap(6).items_center()
        .child(div().flex_none().child(row.name))
        .when(Boolean(row.plan), (e) => e.child(div().min_w(0).truncate().text_size(11).text_color(t.muted)
          .child(row.plan ?? ""))))
      .when(Boolean(row.five || row.week), (e) => e.child(window(row.five)).child(window(row.week)))
      .when(Boolean(row.month), (e) => e.child(this.figure(t, "", row.month?.figure ?? "", row.month?.level ?? null,
        row.month?.of ?? "", ground)))
      .when(Boolean(row.untold), (e) => e.child(div().flex_none().text_size(11).text_color(t.muted)
        .child(row.untold?.text ?? ""))),
    ...(usageLine(row) ? [h_flex().h(USAGE_LINE).flex_none().pl(NAME_IN).pr(PAD / 2).pb(2).items_center()
      .text_size(11).text_color(t.muted).child(div().min_w(0).truncate().child(under))] : [])];
  }

  /** A line under a section in its rows' name column, HIGH px: "N more", or that it has none. @param {string} words
   * @param {number} high */
  line(t, words, high) {
    return h_flex().h(high).flex_none().pl(NAME_IN).pr(6).items_center().text_size(11).text_color(t.muted)
      .child(words);
  }

  /** SECTION's head (connectors.html's .lsec): chevron (none when EMPTY), title, count, summary, Connectors' + (ADD),
   * END (Usage's Open Usage, Permissions' +), its cost after its swatch; a click folds it. @param {Section} section
   * @param {boolean} open @param {any} [add] @param {any} [end] @param {boolean} [empty] */
  section(t, section, open, add = null, end = null, empty = false) {
    const key = `agent-section-${this.slides}${section.id}`, folds = !this.query && !empty;
    return h_flex().id(key).h(HEAD_H).flex_none().px(PAD / 2).gap(6).items_center().rounded(6)
      .when(folds, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
      .child(h_flex().id(`${key}-head`).flex_1().min_w(0).h_full().gap(6).items_center()
        .when(folds, (e) => e.cursor_pointer()
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.toggle(section.id, cx)))
        .child(empty ? div().size(14).flex_none() : fold(`${key}-fold`, open, 14, t.dim))
        .child(div().flex_none().font_semibold().child(section.title))
        .when(section.count !== null, (e) => e.child(div().flex_none().text_size(11).text_color(t.muted)
          .child(String(section.count))))
        .child(h_flex().flex_1().min_w(0).gap(8).justify_end().overflow_hidden().text_size(11)
          .children(section.summary.map((one) => div().min_w(0).truncate().text_color(toneInk(t, one.tone))
            .child(one.text)))))
      .when(Boolean(add), (e) => e.child(this.plus(t, add))).when(Boolean(end), (e) => e.child(end))
      .when(section.cost !== null, (e) => e.child(h_flex().w(COST).flex_none().gap(6).justify_end().items_center()
        .text_size(11).text_color(t.muted)
        .when(Boolean(section.swatch), (e) => e.child(div().size(SWATCH).flex_none().rounded_xs()
          .bg(partColor(t, section.swatch ?? ""))))
        .child(section.cost ?? "")));
  }

  /** A section's + (connectors.html's .lsec .add): ADD px square, raised with a hairline in the accent while LIT
   * (its menu or its form open). @param {string} id @param {boolean} lit */
  plusMark(t, id, lit) {
    return div().id(id).size(ADD).flex_none().flex().items_center().justify_center().rounded(6).border_1()
      .border_color(lit ? t.accent : `${t.accent}00`).text_color(lit ? t.foreground : t.muted).cursor_pointer()
      .when(lit, (e) => e.bg(t.raised))
      .hover((/** @type {any} */ s) => s.bg(t.raised).text_color(t.foreground)).child(icon("plus", 14));
  }

  /** Connectors' +: its menu under it while open, its right edge with the button's. @param {any} add */
  plus(t, add) {
    const open = this.addMenu;
    const button = this.plusMark(t, `agent-add-${this.slides}`, open).when(!open, (e) => e.tooltip(add.tip));
    return Popover.new(`agent-add-menu-${this.slides}`).anchor("top_right").open(open)
      .when(!this.still, (/** @type {any} */ e) => e.track_focus(this.addFocus))
      .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) => this.showWays(opened, cx))
      .trigger(button).when(open && !this.still, (/** @type {any} */ e) => e.content(this.ways(t, add).mt(4)));
  }

  /** The ways to add a connector (connectors.html's .addm, the agents' list's form): Claude's page for claude.ai's
   * under Lucide's external-link, the form under its link. A press or Enter picks; ↑ ↓ step. @param {any} add */
  ways(t, add) {
    /** @type {Record<string, import("./icons.js").IconName>} */
    const marks = { "claude-ai": "external-link", url: "link" };
    return panelSurface(t, `agent-add-ways-${this.slides}`, ADD_MENU).p(4).gap(2)
      .when(!this.still, (e) => e.track_focus(this.addFocus).on_key_down((/** @type {any} */ e,
        /** @type {any} */ cx) => this.waysKey(e, cx, add.menu)))
      .children(add.menu.map((/** @type {any} */ way, /** @type {number} */ n) => panelRow(t, this.addList, n, true)
        .id(`agent-add-way-${this.slides}${way.id}`).line_height("16px").cursor_pointer()
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.add(way, cx))
        .child(icon(marks[way.id] ?? "plus", 16).text_color(t.muted)).child(way.label)));
  }

  /** A key in the open menu: ↑ ↓ step its rows, Enter or Space picks, Esc shuts it. @param {any[]} ways */
  waysKey(e, cx, ways) {
    const list = this.addList;
    if (e.key === "escape") return void this.showWays(false, cx);     // Esc goes on: a float takes the keys back
    if (e.key === "up" || e.key === "down") {
      list.cursor = panelStep(ways.length, list.cursor, e.key === "down" ? 1 : -1, () => false);
    } else if ((e.key === "enter" || e.key === "space") && list.cursor !== null) this.add(ways[list.cursor], cx);
    else return;
    cx.stop_propagation();
    cx.notify();
  }

  /** A source's tag (parts.js's scopeTag) of WORD, cut to its column, its tip the whole word then.
   * @param {string} word @param {string} id */
  tag(t, word, id) {
    const cut = tagWord(word), tag = scopeTag(t, cut);
    return cut === word ? tag : tag.id(id).tooltip(word);
  }

  /** A row's mark (connectors.html's .mk), in its column: ✕ red failed, a dot yellow to sign in or a conflict, green
   * used in this chat; none, its room. @param {string | null} mark */
  mark(t, mark) {
    const room = div().w(MARKS).flex_none().flex().items_center().justify_center();
    if (mark === "bad") return room.child(icon("x", 12).text_color(toneInk(t, "bad")));
    return mark ? room.child(div().size(6).rounded_full().bg(mark === "warn" ? t.ansi3 : t.ansi2)) : room;
  }

  /** ROW of SECTION (KEY: its place): mark, a connector's logo, name and note (a subagent's at the states'), state or
   * spinner, tag (TAGS px; 0: none), cost; a conflict's sentence under its name. A press chooses it.
   * @param {Section} section @param {Row} row @param {string} key @param {number} tags @param {Look} look */
  row(t, section, row, key, tags, look) {
    const conflict = conflicted(row), tone = row.state?.tone ?? "", chosen = row.id === this.chosen;
    const checking = this.checking.has(serverOf(row) ?? ""), signing = Boolean(row.properties?.words);
    const ground = chosen ? chosenFill(t) : t.surface, aside = section.id === "subagents" && !row.names;
    const name = div().min_w(0).truncate().text_color(row.dim ? t.muted : t.foreground).child(row.name);
    const note = div().min_w(0).flex_shrink(NOTE_SHRINK).truncate().text_size(11);
    const both = row.agents.length > 1 ? row.agents.map((one) => agentMark(look.programs[one], 12)).filter(Boolean)
      : [];
    const words = conflict ? v_flex().flex_1().min_w(0).child(name)
      .child(note.text_color(toneInk(t, "warn", ground)).child(row.note ?? ""))
      : h_flex().flex_1().min_w(0).gap(6).items_center().child(name)
        .when(Boolean(row.note) && !aside, (e) => e.child(note.text_color(t.muted).child(row.note ?? "")))
        .when(both.length > 1, (e) => e.child(h_flex().id(`agent-both-${key}`).flex_none().gap(2)
          .items_center().text_color(t.muted).children(both)
          .tooltip(`${row.agents.map((one) => NAMES[one] ?? one).join(" and ")} both read it`)));
    return h_flex().id(`agent-row-${this.slides}${key}`).h(conflict ? WARN_H : ROW_H).flex_none().pl(INSET)
      .pr(PAD / 2).gap(6).items_center().rounded(6).cursor_pointer()
      .when(chosen, (e) => e.bg(ground)).when(!chosen, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
      .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(row.id, cx))
      .when(Boolean(row.note), (e) => e.tooltip(`${row.name}: ${row.note}`))
      .child(this.mark(t, row.mark))
      .when(row.icon === "plug", (e) => e.child(brandMark(t, row.brand, row.name, LOGO)))
      .child(words)
      .when(checking || signing, (e) => e.child(spinner(t)))
      .when(aside && Boolean(row.note), (e) => e.child(div().flex_none().text_size(11).text_color(t.muted)
        .child(row.note ?? "")))
      .when(Boolean(row.state) && !checking, (e) => e.child(div().flex_none().text_size(11)
        .text_color(toneInk(t, tone, ground)).child(row.state?.text ?? "")))
      .when(tags > 0 && !conflict, (e) => e.child(h_flex().w(tags).flex_none().justify_end()
        .when(Boolean(row.tag), (e) => e.child(this.tag(t, row.tag ?? "", `agent-tag-${key}`)))))
      .when(section.cost !== null && !conflict, (e) => e.child(div().w(COST).flex_none().text_right().text_size(11)
        .text_color(t.muted).child(row.cost ?? "")));
  }

  /** The chosen ROW's properties (connectors.html's .insp): title, lines (LABEL px; the built-in subagents' a list),
   * a sign-in's words, its error (the files it named its tip), a rule's first lines or a description, its form
   * (editing()), what can be done (buttons()). @param {Row} row */
  properties(t, row, look) {
    const props = row.properties, ground = t.chrome;
    const lines = propertyLines(row), acts = doable(row, look.agent), error = errorColors(t, ground);
    const checking = this.checking.has(serverOf(row) ?? ""), code = codeFont();
    const excerpt = row.icon === "file" ? (props?.text ?? "").split("\n").filter(Boolean) : [];
    const buttons = this.buttons(t, acts, checking);
    return this.sheet(t, `agent-properties-${this.slides}`)
      .child(h_flex().h(20).flex_none().gap(8).items_center()
        .when(row.icon === "plug", (e) => e.child(brandMark(t, row.brand, row.name, LOGO)))
        .child(div().flex_1().min_w(0).truncate().font_semibold().child(props?.title ?? row.name))
        .when(checking, (e) => e.child(spinner(t)))
        .when(Boolean(row.state) && !checking, (e) => e.child(div().flex_none().text_size(11)
          .text_color(toneInk(t, row.state?.tone ?? "", ground)).child(row.state?.text ?? ""))))
      .when(lines.length > 0, (e) => e.child(v_flex().flex_none().children(lines.map((line, n) => (row.names
        ? this.named(t, row, line, n, look)
        : propertyLine(t, `agent-property-${this.slides}${n}`, line, LABEL, PHRASES.includes(line[0])
          || row.tag === DEFAULT ? null : code))))))
      .when(Boolean(props?.words), (e) => e.child(h_flex().h(20).flex_none().gap(8).items_center()
        .child(spinner(t)).child(div().min_w(0).truncate().child(props?.words ?? ""))))
      .when(Boolean(props?.error), (e) => e.child(div().id(`agent-error-${this.slides}`).flex_none().px(8).py(6)
        .rounded(6).bg(error.fill).font_family(code).text_size(11).text_color(error.ink)
        .when(Boolean(props?.tip), (e) => e.tooltip(props?.tip ?? "")).child(props?.error ?? "")))
      .when(excerpt.length > 0, (e) => e.child(v_flex().flex_none().font_family(code).text_size(11)
        .text_color(t.muted).children(excerpt.map((line) => div().h(16).truncate().child(line)))))
      .when(Boolean(props?.text) && !excerpt.length, (e) => e.child(div().flex_none().max_h(48).overflow_hidden()
        .text_size(11).line_height("16px").text_color(t.muted).child(props?.text ?? "")))
      .children(this.editing(t, row))
      .when(Boolean(this.failed), (e) => e.child(div().flex_none().text_size(11)
        .text_color(toneInk(t, "bad", ground)).child(this.failed ?? "")))
      .when(Boolean(buttons), (e) => e.child(buttons));
  }

  /** A line of the built-in subagents' list (LINE N of ROW's): its name, its model and tools, off here at its end;
   * a name's line (Claude's) a press opening its form under the list, raised while it is open.
   * @param {Row} row @param {[string, string, string | null]} line @param {number} n @param {Look} look */
  named(t, row, [name, value, third], n, look) {
    const picks = look.agent === "claude" && Boolean(row.names?.includes(name)), on = picks && this.edit?.name === name;
    return h_flex().id(`agent-property-${this.slides}${n}`).h(20).flex_none().gap(8).items_center().rounded(4)
      .when(on, (e) => e.bg(t.raised))
      .when(picks, (e) => e.cursor_pointer().when(!on, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.open(cx, on ? null : name)))
      .child(div().flex_1().min_w(0).truncate().when(Boolean(third), (e) => e.text_color(t.muted)).child(name))
      .child(div().flex_none().text_color(t.muted).child(third ?? value));
  }

  /** The open form's parts in core's words, under ROW's lines (null: a form with no row): one it cannot change says
   * why, alone; a removal its question; else its controls, the layers (layersShown()), what a save changes, the
   * warnings in yellow, a refusal in red. @param {Row | null} row */
  editing(t, row) {
    const edit = this.edit, plan = edit?.plan, ground = t.chrome;
    const words = (/** @type {string} */ text, /** @type {string | null} */ tone = null) => div().flex_none()
      .text_size(11).line_height("16px").text_color(tone ? toneInk(t, tone, ground) : t.muted).child(sentence(text));
    if (!edit) return [];
    const failed = edit.error ? [words(edit.error, "bad")] : [];
    if (!plan) return failed;
    if (plan.error && !edit.touched) return [words(plan.error)];
    const named = plan.fields.length > 1;
    return [...(plan.ask ? [div().flex_none().font_semibold().child(plan.ask)]
      : plan.fields.flatMap((field) => this.control(t, field, row, named))),
    ...(plan.layers.length && !plan.ask && layersShown(edit.ask, edit.touched) ? [this.saved(t, plan)] : []),
    ...(plan.changes.length ? [this.changes(t, plan)] : []),
    ...plan.warns.map((one) => words(one, "warn")),
    ...(plan.error ? [words(plan.error, "bad")] : []), ...(edit.note ? [words(edit.note)] : []), ...failed];
  }

  /** A form's FIELD as its control: a switch on its label's line (a server to approve: both ways, as parts); a
   * conflict's ways a list; a choice as parts (NAMED: after its label), its hint under it; a text its entry, its
   * hosts over it. @param {import("./layers.js").Field} field @param {Row | null} row @param {boolean} named */
  control(t, field, row, named) {
    const edit = /** @type {Edit} */ (this.edit), key = `agent-edit-${this.slides}${field.id}`, id = field.id;
    const pick = (/** @type {any} */ value, /** @type {any} */ cx) => this.change({ [id]: value }, cx);
    if (field.kind === "switch" && approves(row)) {
      return [this.labelled(t, null, this.parts(t, key, [{ id: true, label: field.turn?.on ?? "" },
        { id: false, label: field.turn?.off ?? "" }], edit.touched ? field.value : null, pick))];
    }
    if (field.kind === "switch") {
      const on = switchShown(field, row, edit.touched);
      return [this.labelled(t, null, div().flex_1().min_w(0).truncate().child(field.label))
        .child(toggle(t, key, on, !edit.busy, (/** @type {any} */ cx) => pick(!on, cx), true))];
    }
    if (id === "way") {
      return (field.choices ?? []).map((one) => {
        const on = one.id === field.value;
        const way = h_flex().id(`${key}-${one.id}`).h(ROW_H).flex_none().px(8).gap(8).items_center().rounded(6)
          .child(div().w(MARKS).flex_none().when(on, (e) => e.child(icon("check", 12).text_color(t.accent))))
          .child(div().min_w(0).truncate().child(one.label));
        if (one.off) return way.text_color(t.dim).tooltip(sentence(one.off));
        return way.cursor_pointer().when(on, (e) => e.bg(t.raised).font_semibold())
          .when(!on, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => pick(one.id, cx));
      });
    }
    if (field.kind === "choice") {
      return [this.labelled(t, named ? field.label : null, this.parts(t, key, field.choices ?? [], field.value, pick)),
        ...(field.hint ? [div().flex_none().text_size(11).text_color(t.muted).child(sentence(field.hint))] : [])];
    }
    const input = edit.inputs[id], entry = input ? this.entry(t, key, edit, id, input) : div().flex_1();
    const hosts = (field.items ?? []).map((one, n) => h_flex().h(20).flex_none().gap(6).items_center()
      .child(div().flex_1().min_w(0).truncate().font_family(codeFont()).text_size(11).child(one.host))
      .child(scopeTag(t, one.layer))
      .child(!removable(one) ? div().size(16).flex_none() : div().id(`${key}-out-${n}`).size(16).flex_none().flex()
        .items_center().justify_center().rounded(4).text_color(t.muted).cursor_pointer()
        .hover((/** @type {any} */ s) => s.bg(t.raised).text_color(t.foreground))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.change({ remove: one.host,
          layer: one.layer }, cx)).child(icon("x", 12))));
    return [this.labelled(t, field.label, !hosts.length ? entry : v_flex().flex_1().min_w(0).gap(2).children(hosts)
      .child(h_flex().child(entry)), hosts.length > 0)];
  }

  /** A form's line, FIELD high or as high as its control wraps: LABEL (null: none) muted in the properties' column
   * (TOP: on its first line), then the CONTROL. @param {string | null} label @param {any} control
   * @param {boolean} [top] */
  labelled(t, label, control, top = false) {
    return h_flex().min_h(FIELD).flex_none().gap(8).when(!top, (e) => e.items_center())
      .when(top, (e) => e.items_start())
      .when(label !== null, (e) => e.child(div().w(LABEL).flex_none().truncate().text_color(t.muted)
        .when(top, (e) => e.h(20).line_height("20px")).child(label ?? "")))
      .child(control);
  }

  /** A choice of a few as one control that wraps (connectors.html's For): LIST's parts 20 high on the window's level,
   * the CHOSEN one raised, a press on another PICKs it; one core greys faint, why its tip. @param {string} id
   * @param {{ id: any, label: string, off?: string | null }[]} list @param {(value: any, cx: any) => void} pick */
  parts(t, id, list, chosen, pick) {
    return h_flex().min_w(0).flex_wrap().p(2).gap(2).rounded(6).bg(t.canvas).children(list.map((one) => {
      const on = one.id === chosen, words = div().min_w(0).truncate().child(one.label);
      const part = div().id(`${id}-${one.id}`).h(20).min_w(0).px(6).flex().items_center().rounded(4);
      if (one.off) return part.text_color(t.dim).tooltip(sentence(one.off)).child(words);
      return part.when(on, (e) => e.bg(t.raised).text_color(t.foreground))
        .when(!on, (e) => e.text_color(t.muted).cursor_pointer()
          .hover((/** @type {any} */ s) => s.text_color(t.foreground))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => pick(one.id, cx)))
        .child(words);
    }));
  }

  /** A form's text field (connectors.html's .fld .in): FIELD high on the window's level, the code font 11; the one
   * with HOLDER's keys (its focus: NAME) edged in the accent, a refused one (BAD) in red. @param {string} id
   * @param {{ focus: string | null }} holder @param {string} name @param {any} input @param {boolean} [bad] */
  entry(t, id, holder, name, input, bad = false) {
    return h_flex().id(id).flex_1().min_w(0).h(FIELD).px(8).items_center().rounded(8).border_1().bg(t.canvas)
      .cursor_text().border_color(bad ? toneInk(t, "bad", t.chrome) : holder.focus === name ? t.accent : t.border)
      .on_mouse_down("left", (/** @type {any} */ _e, /** @type {any} */ cx) => {
        holder.focus = name;
        cx.notify();
      })
      .child(Input.new(input).flex_1().h_full().font_family(codeFont()).text_size(11).text_color(t.foreground));
  }

  /** Saved in: PLAN's layers as one control, then the chosen one's file in the code font, a press opening it.
   * @param {Plan} plan */
  saved(t, plan) {
    const chosen = plan.layers.find((one) => one.chosen), key = `agent-edit-${this.slides}layer`;
    return this.labelled(t, plan.saved, h_flex().flex_1().min_w(0).flex_wrap().gap(6).items_center()
      .child(this.parts(t, key, plan.layers, chosen?.id ?? null, (layer, cx) => this.change({ layer }, cx)))
      .when(Boolean(chosen), (e) => e.child(div().id(`${key}-path`).min_w(0).truncate().font_family(codeFont())
        .text_size(11).text_color(t.muted).cursor_pointer()
        .hover((/** @type {any} */ s) => s.text_color(t.foreground))
        .on_click(() => showFile(filePath(chosen?.path ?? "", String(this.folder), home())))
        .child(chosen?.path ?? ""))));
  }

  /** What a save changes (the mockup's .diff): on the window's level, core's lines in the code font 11, one taken out
   * red, one put in green; each file named where the form offers no layer or two files change; under them when it
   * applies. @param {Plan} plan */
  changes(t, plan) {
    const named = !plan.layers.length || plan.changes.length > 1;
    return v_flex().flex_none().px(8).py(6).gap(4).rounded(6).bg(t.canvas).text_size(11).line_height("16px")
      .child(v_flex().font_family(codeFont()).children(plan.changes.flatMap((one) => [
        ...(named ? [div().text_color(t.muted).child(one.path)] : []),
        ...one.lines.map((line) => div().text_color(toneInk(t, line[0] === "-" ? "deny" : "allow", t.canvas))
          .child(changeLine(line)))])))
      .when(Boolean(plan.when), (e) => e.child(div().text_color(t.muted).child(plan.when ?? "")));
  }

  /** The properties' buttons: the row's own (ACTS) while its form is untouched, then the form's quiet ones (More
   * options, Remove); a touched form's, or one's with no row, Cancel and its one solid button at the end (faint while
   * nothing can be saved); null with none. @param {import("./layers.js").Action[]} acts @param {boolean} checking */
  buttons(t, acts, checking) {
    const edit = this.edit, found = edit?.plan ?? null, key = `agent-act-${this.slides}`;
    const plan = found && !(found.error && !edit?.touched) ? found : null;       // one it cannot change has none
    const ends = Boolean(plan && (edit?.touched || rowless(this.chosen))), word = plan?.submit ?? edit?.submit;
    const saves = Boolean(plan?.submit) && !edit?.busy && edit?.planned === edit?.serial;
    const more = plan && !plan.ask ? plan.more : null, remove = plan && !plan.ask ? plan.remove : null;
    const own = ends ? [] : acts.map((one, n) => actButton(t, `${key}${n}`, one.id === "retry" && checking
      ? "Checking…" : one.label, actionLook(one, n), !checking, (/** @type {any} */ cx) => this.act(one, cx)));
    if (!own.length && !more && !remove && !ends) return null;
    return h_flex().flex_none().pt(2).gap(6).flex_wrap().children(own)
      .when(Boolean(more), (e) => e.child(actButton(t, `${key}more`, more?.label ?? "", "plain", true,
        () => showFile(more?.path ?? ""))))
      .when(Boolean(remove), (e) => e.child(actButton(t, `${key}remove`, remove ?? "", "plain", !edit?.busy,
        (/** @type {any} */ cx) => this.change({ remove: true }, cx))))
      .when(ends, (e) => e.child(div().flex_1())
        .child(actButton(t, `${key}cancel`, plan?.cancel ?? "", "plain", true,
          (/** @type {any} */ cx) => this.drop(cx)))
        .when(Boolean(word), (e) => e.child(actButton(t, `${key}save`, word ?? "", "solid", saves,
          (/** @type {any} */ cx) => this.save(cx)).when(!saves, (/** @type {any} */ e) => e.opacity(0.5)))));
  }

  /** The foot after a save (the mockup's .pfoot), FOOT high under a hairline: what was written, core's words or the
   * change's line in the code font, and Undo; a way back refused, core's words in red. */
  footed(t) {
    const foot = /** @type {Foot} */ (this.foot), ground = t.chrome;
    return h_flex().id(`agent-foot-${this.slides}`).h(FOOT).flex_none().px(PAD).gap(8).items_center().border_t(1)
      .border_color(t.border).bg(ground).text_size(12)
      .child(div().flex_1().min_w(0).truncate().text_color(foot.error ? toneInk(t, "bad", ground) : t.muted)
        .when(foot.code && !foot.error, (e) => e.font_family(codeFont()).text_size(11))
        .child(foot.error ? sentence(foot.error) : foot.text))
      .child(div().id(`agent-undo-${this.slides}`).flex_none().font_semibold()
        .text_color(foot.busy ? t.dim : t.foreground)
        .when(!foot.busy, (e) => e.cursor_pointer().on_click((/** @type {any} */ _e, /** @type {any} */ cx) =>
          this.undo(cx)))
        .child(foot.word));
  }

  /** "By URL…" (connectors.html's Hozzáadás) in the properties' place, in core's words (ADD): Name and URL (entry():
   * a refused one in red, why under them), For as parts, Add and connect, Cancel. Enter adds, Tab steps on, Esc
   * cancels. @param {any} add */
  adder(t, add) {
    const form = /** @type {Form} */ (this.form), key = `agent-form-${this.slides}`;
    const typed = (/** @type {"name" | "url"} */ id) => this.labelled(t, add.fields[id], this.entry(t, `${key}-${id}`,
      form, id, form[id], form.error?.field === id));
    return this.sheet(t, key, false)
      .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => {
        if (e.key === "escape") return void this.dropForm(cx);          // Esc goes on: a float takes the keys back
        if (e.key === "tab") this.focusField(form.focus === "name" ? "url" : "name", cx);
        else return;
        cx.stop_propagation();
      })
      .child(h_flex().h(20).flex_none().gap(8).items_center().child(icon("link", 14).text_color(t.muted))
        .child(div().flex_1().min_w(0).truncate().font_bold().child(add.title)))
      .child(typed("name")).child(typed("url"))
      .when(add.scopes.length > 0, (e) => e.child(this.labelled(t, add.fields.scope, this.parts(t, `${key}-for`,
        add.scopes, form.scope, (scope, cx) => {
          form.scope = scope;
          cx.notify();
        }))))
      .when(Boolean(form.error), (e) => e.child(div().flex_none().text_size(11)
        .text_color(toneInk(t, "bad", t.chrome)).child(form.error?.error ?? "")))
      .child(h_flex().flex_none().pt(2).gap(6).flex_wrap()
        .child(actButton(t, `${key}-add`, form.busy ? "Adding…" : add.submit, "solid", !form.busy,
          (/** @type {any} */ cx) => this.submit(cx)))
        .child(actButton(t, `${key}-cancel`, add.cancel, "plain", true,
          (/** @type {any} */ cx) => this.dropForm(cx))));
  }
}
