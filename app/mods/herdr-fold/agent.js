// @ts-check
// The Agent panel, the dock's fifth view: what the space's agent starts with in its folder, as a design tool's layers,
// the chosen row's properties under them. Core words it (agent_setup.py's layers()), the TUI's Agent view too.
import { div, image, svg } from "gpui-kit";
import { h_flex, v_flex, Input, InputState, Popover, ScrollHandle } from "gpui-base";
import { agents as paneAgents, exec, focused, hc, home, knownAgents, layout, panes, setShared, shared, spaces,
  terminals, watchFolder, run as command } from "herdr";
import { kilo, panelStep, RECENT_AGENTS, tagColors } from "./agents.js";
import { AGENT_SETUP, AGENT_STATE, CONNECTORS, REPORT, TOKENS, USAGE } from "./helper.js";
import { actionLook, addList, AGENT_ASK, AGENT_CHOSEN, AGENT_OPEN, AGENT_PROBLEMS, agentList, agentOf, asked, barParts,
  bodyHeight, CHIP_LIFT, chipColors, chosenAgent, chosenFill, chosenRow, claudeIn, doable, errorColors, HEAD_H,
  keepAgent, keepOpen, keepProblems, LABEL, levelFill, levelInk, loginRun, MORE_H, NAMES, NARROW, overdue,
  printedAddress, propertyLines, READ, resetWords, ROW_H, sectionOpen, SERVER, serverOf, shown, signingRow, signIns,
  signInTab, summarized, tabAgent, tagRoom, tagWord, toneInk, toneOf, touches, USAGE_LINE, USAGE_ROW,
  usageAgents, usageHeight, usageLine, usageOpen, usageRows, WARN_H, WATCHED, COST_BAR, COST_LINE, costGlance,
  costLines, headline, tightest }
  from "./layers.js";
import { indexed, reportArgs } from "./report.js";
import { CHAT_LABEL, CHAT_TAB, DOCK, find, lastLine, PANEL_PX, panelPx, panelRailed, panelShown,
  said } from "./logic.js";
import { listNote, panelRow, panelSurface, rule } from "./menus.js";
import { actButton, ACTION, brandMark, BUTTON, codeFont, field, fold, icon, iconButton, PAD, propertyLine, scopeTag,
  spinner, SPRING, systemForms } from "./parts.js";
import { showPreview } from "./preview.js";
import { format, setForms, written } from "./timeline.js";

const POLL = 30000;                // ms between two reads while it shows, as the TUI's
const AWAY = 300000;               // ms between two reads behind another view, for the tab's dot alone, as the TUI's
const PHRASES = ["Used"];          // the properties whose value is a phrase, in the text's font; the others are code
const QUIET = 5000;                // ms at least between two reads a change asks for (a conversation writes a lot)
const COST = 40;                   // px: the costs' column at a row's and a section's end
const NOTE_SHRINK = 100;           // a row's note gives way this much before its name does
const SIGNING = 5000;              // ms between two looks at the agents while one signs in in its terminal tab
const SIGNING_MS = 600000;         // ms a sign-in is waited for at most
const LIST = 300;                  // px: the agents' list, connectors.html's .agm
const MARK = 28;                   // px: the agent's icon over what its panel says instead of a setup
const SAID = 272;                  // px: those words' column at most (connectors.html's .signin p: 270)
const COPIED = 2000;               // ms the install line's Copy shows its check
const WATCH = 2000;                // ms between two looks at the sign-ins running: one ended is asked about again
const SETTLE = [2000, 6000];       // ms after Claude was told to turn a server off or on: its setup read again
const LOGO = 16;                   // px: a connector's logo or letter tile, connectors.html's .tile.xs
const ADD = 22;                    // px: Connectors' + at its head's end, connectors.html's .lsec .add
const ADD_MENU = 200;              // px: what it opens, connectors.html's .addm
const FIELD = 28;                  // px: the add form's fields, connectors.html's .fld .in
const READ_LINES = "200";          // rows over a sign-in's screen its address is looked for in
const FIVE = 52, WEEK = 52;        // px: Usage's two columns at a row's end: "5h" and its percent, "wk" and the week's
const NAME = 44;                   // px: where a row's name starts (its 24 in, its icon, 6), Usage's bar under it
const COSTS_EVERY = 60000;         // ms an agent's cost lines are kept before core is asked again
const GLANCE = "7d";               // the report the cost lines are read from: this week, and each month in it
/** A row's icon by core's name for it. @type {Record<string, import("./icons.js").IconName>} */
const ICON = { file: "file", shield: "shield", skill: "sparkle", plug: "plug", bot: "bot" };
/** The health bar's parts in the tags' colors: rules the accent, skills teal, connectors blue (center-chat.html's).
 * @type {Record<string, import("./agents.js").TagRole>} */
const PART = { rules: "personal", skills: "project", connectors: "account" };
/** A tag's color role (agents.js's tagColors) by core's tone for it.
 * @type {Record<string, import("./agents.js").TagRole>} */
const TAG_ROLE = { personal: "personal", project: "project", plugin: "plugin", account: "account", muted: "local" };
const PART_NAMES = /** @type {Record<string, string>} */ ({ rules: "Rules", skills: "Skills",
  connectors: "Connectors" });

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
        tellProblems(space.id, await this.core(AGENT_SETUP, ["layers", agent, folder,
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
    /** @type {"agents" | "add" | null} the head's list open: the installed agents, or the ones to add */
    this.listing = null;
    /** @type {number | null} the list's row the keys are on (menus.js's Lister) */
    this.cursor = null;
    this.listPlaces = []; this.listScroll = null;
    this.listFocus = cx.focus_handle();
    /** @type {string | null} an agent picked under Add an agent…: how it is installed, until another is picked */
    this.adding = null;
    /** @type {{ key: string, until: number } | null} the agent signing in in its terminal tab, looked at till then */
    this.signing = null;
    this.copied = false;
    this.still = false;                           // the styleguide's: the chip lit, its list drawn beside, not opened
    /** @type {{ none: string, rows: Usage[], open?: Record<string, boolean> } | null} core's Usage; null: not read */
    this.usage = null;
    /** @type {string | null} why the limits could not be read, while none are shown */
    this.usageError = null;
    this.usageBusy = false;
    /** @type {Record<string, boolean>} Usage's blocks opened or folded here, till core's answer tells it */
    this.turned = {};
    /** @type {Record<string, import("./layers.js").CostLine[]>} each agent's cost lines under its row (costLines()) */
    this.costs = {};
    /** @type {Record<string, import("./layers.js").Glance>} each agent's figure on its folded row (costGlance()) */
    this.glances = {};
    this.costsAt = 0;
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
        signed: new Set(), wants: null, addMenu: false, form: null, due: [] });
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
        if (this.adding && agentOf(agents, this.adding)?.installed !== false) this.adding = null;
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
        const turned = Object.fromEntries(Object.entries(this.turned).filter(([key, on]) => usage?.open?.[key] !== on));
        Object.assign(this, { usage, usageError: null, turned });
        if (!same) cx.notify();
        await this.readCosts(cx);
      } catch (e) {
        if (this.usage) return;
        this.usageError = said(e);
        cx.notify();
      } finally {
        this.usageBusy = false;
      }
    });
  }

  /** What the agents cost, for Usage's lines (core's 7-day report, after the token index is read on), every
   * COSTS_EVERY at most; kept where a read fails: the limits stand without them. */
  async readCosts(cx) {
    if (Date.now() - this.costsAt < COSTS_EVERY) return;
    this.costsAt = Date.now();
    try {
      await indexed(() => this.core(TOKENS, ["index"], home(), null));
      const report = await this.core(REPORT, reportArgs("report", { period: GLANCE, agent: null, folder: null,
        agents: usageAgents(this.agents), theme: null }), home(), null);
      const costs = costLines(report), glances = costGlance(report);
      if (JSON.stringify([costs, glances]) === JSON.stringify([this.costs, this.glances])) return;
      Object.assign(this, { costs, glances });
      cx.notify();
    } catch {
      // not told now: the next read asks again
    }
  }

  /** The head's list shown (WHICH: the agents, or the ones to add) or shut (null): the keys on no row till an arrow,
   * the agents asked for again as it opens. @param {"agents" | "add" | null} which */
  list(which, cx) {
    Object.assign(this, { listing: which, cursor: null, listPlaces: [] });
    if (which) this.readAgents(cx);
    cx.notify();
  }

  /** Agent KEY picked in the list: the whole panel its own, kept for the space shown. @param {string} key */
  pick(key, cx) {
    const space = spaces().find((s) => s.active)?.id;
    const live = new Set(spaces().map((s) => s.id));
    if (space) setShared(AGENT_CHOSEN, keepAgent(shared(AGENT_CHOSEN), space, key, live));
    Object.assign(this, { adding: null, failed: null });
    this.list(null, cx);
  }

  /** The list's rows the keys walk, in order: each agent, then Add an agent…; under it, the ones to add.
   * @param {Look} look @returns {{ id: string, act: (cx: any) => void, row: any }[]} */
  listRows(look) {
    if (this.listing === "add") {
      return addList(this.agents, look.programs).map((row) => ({ id: row.key, row, act: (cx) => {
        Object.assign(this, { adding: row.key, failed: null });
        this.list(null, cx);
      } }));
    }
    return [...agentList(this.agents, look.programs, this.adding ? "" : look.agent).map((row) => ({ id: row.key, row,
      act: (/** @type {any} */ cx) => this.pick(row.key, cx) })),
    ...(this.agents ? [{ id: "add", row: null, act: (/** @type {any} */ cx) => this.list("add", cx) }] : [])];
  }

  /** A key in the open list: ↑ ↓ step its rows (from the one in use), Enter or Space picks, Esc shuts it.
   * @param {ReturnType<AgentView["listRows"]>} rows */
  listKey(e, cx, rows) {
    if (e.key === "escape") this.list(null, cx);
    else if (e.key === "up" || e.key === "down") {
      this.cursor = panelStep(rows.length, this.cursor, e.key === "down" ? 1 : -1, () => false,
        rows.findIndex((one) => one.row?.check));
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
        const found = await this.core(AGENT_SETUP, ["layers", agent, folder,
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

  /** Whether agent KEY's block in Usage is open (usageOpen()). @param {string} key */
  opens(key) {
    return usageOpen(key, this.usage?.open, this.turned, this.agent ?? null);
  }

  /** Agent KEY's block in Usage opened or folded, at once; core keeps it for both clients (usage.py open), and a
   * failure leaves it so here till the next read. @param {string} key */
  turnBlock(key, cx) {
    const on = !this.opens(key), folder = this.folder ?? home();
    this.turned = { ...this.turned, [key]: on };
    cx.notify();
    cx.spawn(async () => {
      try {
        await this.core(USAGE, ["open", key, on ? "on" : "off"], folder, null);
      } catch {
        // not kept: shown as turned till core's next answer
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

  /** Row ID chosen, its properties under the layers; the chosen one again: none. @param {string} id */
  choose(id, cx) {
    Object.assign(this, { chosen: this.chosen === id ? null : id, failed: null });
    cx.notify();
  }

  /** ROW of SECTION shown and chosen, as a problem's chip and openAgentPanel() ask: the filter emptied, its section
   * opened and scrolled to (a problem stands first in it). @param {string | null} section @param {string | null} row */
  reveal(section, row, cx) {
    const sections = /** @type {Section[]} */ (this.found?.sections ?? []);
    const inside = chosenRow(sections, row)?.section.id ?? section, space = spaces().find((s) => s.active)?.id;
    if (this.finding) this.search(cx);
    if (row && chosenRow(sections, row)) Object.assign(this, { chosen: row, failed: null });
    const at = sections.findIndex((one) => one.id === inside);
    if (at >= 0 && space && !sectionOpen(shared(AGENT_OPEN), space, String(inside))) this.toggle(String(inside), cx);
    const lead = this.usage || this.usageError ? 2 : 0;         // Usage over them, its head and its rows
    if (at >= 0) this.scroll.scroll_to_item(lead + at * 2);     // a section is its head, then its rows
    cx.notify();
  }

  /** From render: openAgentPanel()'s ask for SPACE answered once (after the first read, where a row is asked for).
   * @param {string} space */
  answer(space, cx) {
    const ask = asked(shared(AGENT_ASK), space, this.answered, Date.now());
    if (ask) Object.assign(this, { answered: ask.at, waits: { section: ask.section ?? null, row: ask.row ?? null } });
    if (ask?.list && !this.listing) cx.timer.after(0, (/** @type {any} */ cx) => this.list("agents", cx));
    if (!this.waits || !this.found) return;
    const { section, row } = this.waits;
    this.waits = null;
    cx.timer.after(0, (/** @type {any} */ cx) => this.reveal(section, row, cx));
  }

  /** ACTION of the chosen row done: a file in the preview tab, its node in the Agents tab's graph, else the agent's
   * own command on its server (core's words for each: connectors.py). @param {import("./layers.js").Action} action */
  act(action, cx) {
    if (action.id === "graph") {
      return void (this.chosen && this.graph?.({ node: this.chosen, session: this.session ?? null }));
    }
    if (action.id === "open" && action.path) {
      const cut = action.path.lastIndexOf("/");
      return showPreview({ kind: "file", root: action.path.slice(0, cut) || "/", path: action.path.slice(cut + 1),
        on: null });
    }
    const name = action.server;
    if (!name || !this.folder) return;
    if (action.id === "retry") this.check(name, cx);
    else if (action.id === "connect") this.connect(name, cx);
    else if (action.id === "reopen") this.reopen(name, cx);
    else if (action.id === "cancel") this.cancel(name, cx);
    else if (action.id === "sign-out") this.signOut(name, cx);
    else if (action.id === "turn-off" || action.id === "turn-on") this.turn(name, action.id === "turn-on", cx);
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

  /** The folder's Claude a server is turned off or on through (claudeIn's): a chat of the space shown, or Claude in a
   * pane there; null with none, where the button waits (core's words say why). */
  chat() {
    return this.agent === "claude" ? claudeIn(spaces().find((s) => s.active) ?? null, paneAgents(), panes(),
      terminals(), CHAT_TAB) : null;
  }

  /** Turn off or on in this folder: Claude's own `/mcp` command (core's words) sent to the folder's Claude once it
   * is idle; the setup read again as Claude writes it. @param {string} name @param {boolean} on */
  turn(name, on, cx) {
    const { folder } = this, to = this.chat();
    if (!folder || !to) return;
    this.run(name, "Couldn't tell Claude", cx, async () => {
      const words = await this.core(CONNECTORS, ["toggle", name, on ? "on" : "off"], folder, null);
      const sent = await hc(["send", "--if", "idle", to, words]);
      if (sent.code !== 0) throw new Error(lastLine(sent));
      this.due = SETTLE.map((ms) => Date.now() + ms);
    });
  }

  /** Connectors' + pressed: its menu shown or shut, the keys on no row; Codex adds one way: the form at once.
   * @param {boolean} open */
  showWays(open, cx) {
    const ways = this.found?.connect?.add.menu ?? [];
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
    const scoped = (this.found?.connect?.add.scopes ?? []).length > 0;
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

  /** The panel as LOOK has it: the head, the filter while asked for, the health line, the layers and under them the
   * chosen row's properties or the add form; in their place what it says instead (loading, the read's failure; under
   * the head, where the agent stands: not installed, not signed in). @param {Look} look */
  draw(t, look) {
    const found = this.found, frame = this.frame(t), sections = found ? this.sections(found) : [];
    const chosen = chosenRow(sections, this.chosen), add = found?.connect?.add ?? null;
    const agent = agentOf(this.agents, this.adding ?? look.agent);
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
    return frame.child(this.head(t, found.head, look))
      .when(this.finding, (e) => e.child(div().flex_none().px(PAD).pb(8).child(field(t, "agent-filter", this.find))))
      .child(this.health(t, found.health))
      .child(this.layers(t, sections, look))
      .when(Boolean(this.form && add), (e) => e.child(this.adder(t, add)))
      .when(Boolean(chosen) && !this.form, (e) => e.child(this.properties(t, /** @type {Row} */ (chosen?.row), look)));
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
  say(t, words, color = t.dim) {
    return div().flex_none().p(PAD).text_size(12).text_color(color).child(words);
  }

  /** The head: the agent's chip (its icon, its name and where, core's words, ⌄: a press opens the agents' list under
   * it, lit while open), the search at its end where there is a setup to FILTER, lit while it does.
   * @param {{ name: string, where: string }} head @param {Look} look @param {boolean} [filter] */
  head(t, head, look, filter = true) {
    const mark = agentMark(look.programs[look.agent], 14), open = Boolean(this.listing), clear = `${t.accent}00`;
    const chip = h_flex().id(`agent-chip-${this.slides}`).h(BUTTON).min_w(0)
      .max_w(look.px - 2 * PAD - (filter ? BUTTON + 8 : 0)).px(6).gap(6).items_center().rounded(6).border_1()
      .border_color(open ? t.accent : clear).cursor_pointer()
      .when(open, (e) => e.bg(t.raised)).hover((/** @type {any} */ s) => s.bg(open ? t.raised : t.hover))
      .when(Boolean(mark), (e) => e.child(mark))
      .child(div().flex_none().font_semibold().child(head.name))
      .child(div().min_w(0).truncate().text_color(t.dim).child(head.where))
      .child(icon("chevron-down", 12).text_color(t.dim));
    return h_flex().flex_none().mt(PAD).mb(6).px(PAD / 2).gap(8).items_center()
      .child(h_flex().flex_1().min_w(0).child(Popover.new(`agent-list-${this.slides}`).anchor("top_left").open(open)
        .when(!this.still, (/** @type {any} */ e) => e.track_focus(this.listFocus))
        .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) =>
          this.list(opened ? this.listing ?? "agents" : null, cx))
        .trigger(chip).when(open && !this.still, (/** @type {any} */ e) => e.content(this.listed(t, look).mt(4)))))
      .when(filter, (e) => e.child(div().pr(PAD / 2).child(iconButton(t, "agent-search", "search", "Filter setup",
        (/** @type {any} */ cx) => this.search(cx), { lit: this.finding }))));
  }

  /** The head's list (connectors.html's .agm, the chat bar's panels' form): "Agents on this Mac", the installed
   * ones (its icon, its name, its plan's word dim; sign in where it must, else ✓ on the one shown), a rule, Add an
   * agent…; or the ones to add. A press or Enter picks; ↑ ↓ step. @param {Look} look */
  listed(t, look) {
    const rows = this.listRows(look), adding = this.listing === "add", ground = t.popover ?? t.raised;
    const warn = chipColors(t, "warn", 0, ground);
    const drawn = rows.map(({ id, row, act }, n) => {
      const line = panelRow(t, this, n, true, Boolean(row?.check)).id(`agent-pick-${this.slides}${id}`)
        .line_height("16px").cursor_pointer().on_click((/** @type {any} */ _e, /** @type {any} */ cx) => act(cx));
      if (!row) return line.child(icon("plus", 16).text_color(t.muted)).child("Add an agent…");
      return line.child(agentMark(look.programs[row.key], 16) ?? icon("bot", 16).text_color(t.muted))
        .child(div().flex_none().child(row.name))
        .when(Boolean(row.plan), (e) => e.child(div().min_w(0).truncate().text_size(12).text_color(t.dim)
          .child(row.plan ?? "")))
        .child(div().flex_1())
        .when(Boolean(row.signIn), (e) => e.child(div().h(16).flex_none().px(6).flex().items_center().rounded(4)
          .bg(warn.fill).text_size(11).line_height("16px").font_medium().text_color(warn.ink).child("sign in")))
        .when(Boolean(row.check) && !row.signIn, (e) => e.child(icon("check", 14).text_color(t.accent)));
    });
    const none = this.agentsError ? listNote(t, `Couldn't list the agents: ${this.agentsError}`, true, PAD)
      : !this.agents ? listNote(t, "Loading agents…", false, PAD)
        : adding && !rows.length ? listNote(t, "Every agent herdr-fold knows is installed", false, PAD) : null;
    return panelSurface(t, `agent-list-surface-${this.slides}`, Math.min(LIST, look.px - PAD)).p(4).gap(2)
      .when(!this.still, (e) => e.track_focus(this.listFocus).on_key_down((/** @type {any} */ e,
        /** @type {any} */ cx) => this.listKey(e, cx, rows)))
      .child(div().flex_none().px(PAD).pt(6).pb(4).text_size(12).line_height("16px").font_semibold()
        .text_color(t.muted)
        .child(adding ? "Add an agent" : "Agents on this Mac"))
      .when(Boolean(none), (e) => e.child(none))
      .children(adding ? drawn : [...drawn.slice(0, -1), ...(drawn.length > 1 ? [rule(t)] : []), ...drawn.slice(-1)]);
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
      .when(Boolean(says.foot), (e) => e.child(div().text_size(11).text_color(t.dim).text_center()
        .child(says.foot ?? "")));
  }

  /** The health line: what loads at start as a bar of its parts (each its share, named in its tip), core's words for
   * it, and the problems as chips in their tones, a press choosing a chip's row. @param {any} health */
  health(t, health) {
    const colors = tagColors(t);
    return v_flex().flex_none().px(PAD).pt(2).pb(8).gap(6).border_b(1).border_color(t.border)
      .child(h_flex().h(6).flex_none().gap(2).rounded_full().bg(t.canvas)
        .children(barParts(health.bar).map((part) => div().id(`agent-bar-${part.part}`).h_full().min_w(6)
          .flex_basis(0).flex_grow(part.tokens).rounded_full().bg(colors[PART[part.part]] ?? t.muted)
          .tooltip(`${PART_NAMES[part.part] ?? part.part} ${kilo(part.tokens)}`))))
      .child(h_flex().gap(6).items_center()
        .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(t.dim).child(health.text))
        .children(health.problems.map((/** @type {any} */ one, /** @type {number} */ n) => {
          const { fill, ink } = chipColors(t, one.tone), over = chipColors(t, one.tone, CHIP_LIFT);
          return div().id(`agent-problem-${this.slides}${n}`).h(16).flex_none().px(6).flex().items_center()
            .rounded(4).bg(fill).text_size(11).line_height("16px").font_medium().text_color(ink).cursor_pointer()
            .hover((/** @type {any} */ s) => s.bg(over.fill).text_color(over.ink))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.reveal(null, one.row, cx))
            .child(one.text);
        })));
  }

  /** The sections, each its head and its rows sprung open under it; with a filter typed, those with a row it finds,
   * all open; none found, said in the first one's place. @param {Section[]} sections @param {Look} look */
  layers(t, sections, look) {
    const wide = look.px >= NARROW;
    const parts = sections.map((section) => ({ section, ...shown(section, { query: this.query,
      more: this.more.has(section.id), chosen: this.chosen }) })).filter((part) => !this.query || part.rows.length);
    return v_flex().id("agent-layers").flex_1().min_h(0).overflow_y_scrollbar().track_scroll(this.scroll)
      .px(PAD / 2).py(4).gap(2).text_size(12)
      .when(!parts.length, (e) => e.child(h_flex().h(ROW_H).flex_none().px(PAD / 2).text_color(t.dim)
        .child("Nothing matches")))
      .when(!this.query && Boolean(this.usage || this.usageError), (e) => e.children(this.limits(t, look)))
      .children(parts.flatMap(({ section, rows, more }) => {
        const open = Boolean(this.query) || look.open(section.id);
        const add = section.id === "connectors" ? this.found?.connect?.add ?? null : null;
        return [this.section(t, section, open, add), v_flex().id(`agent-rows-${this.slides}${section.id}`).flex_none()
          .overflow_hidden().h(open ? bodyHeight(rows, more) : 0).spring("height", SPRING)
          .when(!rows.length, (e) => e.child(this.line(t, `No ${section.title.toLowerCase()}`, ROW_H)))
          .children(rows.map((row, n) => this.row(t, section, row, n, wide ? tagRoom(section) : 0, look)))
          .when(more > 0, (e) => e.child(this.line(t, `${more} more`, MORE_H).id(`agent-more-${section.id}`).rounded(6)
            .cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
              this.more.add(section.id);
              cx.notify();
            })))];
      }));
  }

  /** Usage, the first section (usage-agents.html; core's words): its head with Open Usage at its end, folded with one
   * figure before it (headline()); a row an agent, the one in use open, each turned by a press and kept for both
   * clients; none known, or the read failed: said in their place. @param {Look} look */
  limits(t, look) {
    const rows = usageRows(this.usage?.rows, usageAgents(this.agents), this.costs, this.agent ?? null);
    const open = look.open("usage"), shown = open ? null : headline(rows, this.glances, this.agent ?? null);
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
    return [this.section(t, { id: "usage", title: "Usage", count: null, cost: null, summary: [], rows: [] }, open,
      null, end),
    v_flex().id(`agent-usage-${this.slides}`).flex_none().overflow_hidden()
      .h(open ? usageHeight(rows, (key) => this.opens(key), this.costs) : 0)
        .spring("height", SPRING)
        .when(!rows.length, (e) => e.child(this.line(t, none, ROW_H)
          .when(Boolean(this.usageError), (e) => e.text_color(toneInk(t, "bad")))))
        .children(rows.flatMap((row, n) => this.meter(t, row, n, look)))];
  }

  /** Usage's head folded (usage-agents.html's .hfig): ROW's agent's mark, then its tightest figure, its words muted
   * and the figure semibold in its level's color; a press opens the section. @param {Usage} row @param {Look} look */
  headFigure(t, row, look) {
    const one = tightest(row, this.glances[row.key]);
    return h_flex().id(`agent-usage-head-${this.slides}`).flex_none().gap(6).items_center().text_size(11)
      .text_color(t.muted).when(!this.still, (e) => e.cursor_pointer()
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.toggle("usage", cx)))
      .child(agentMark(look.programs[row.key], 14) ?? icon("bot", 14).text_color(t.muted))
      .child(this.figure(t, one?.label ?? "", one?.figure ?? "", one?.level ?? null, one?.after ?? "", t.surface));
  }

  /** A figure as Usage's rows end with it: LABEL muted, the FIGURE semibold in LEVEL's color read on GROUND (the
   * text's with none), AFTER muted. @param {string} label @param {string} figure @param {string | null} level
   * @param {string} after @param {string} ground */
  figure(t, label, figure, level, after, ground) {
    return h_flex().flex_none().gap(4).justify_end().text_size(11).text_color(t.muted)
      .when(Boolean(label), (e) => e.child(div().child(label)))
      .child(div().font_semibold().text_color(level ? levelInk(t, level, ground) : t.foreground).child(figure))
      .when(Boolean(after), (e) => e.child(div().child(after)));
  }

  /** An agent's row (ROW, the N-th): icon, name, plan; at its end a plan's windows in their columns (folded: an API
   * key's month of its budget), its chevron; the one in use lit, a press turns it. Open: its bar on its lower edge,
   * its reset and age under it, its cost lines. @param {Usage} row @param {number} n @param {Look} look */
  meter(t, row, n, look) {
    const open = this.opens(row.key), glance = this.glances[row.key];
    const ground = row.current ? t.raised : t.surface, when = new Date((row.resets?.at ?? 0) * 1000);
    const used = Math.max(0, Math.min(100, row.bar?.used ?? 0));
    const resets = resetWords(row.resets, written(when, "time"), format(when, "EEE"));
    const column = (/** @type {import("./layers.js").Meter | null} */ one, /** @type {number} */ px) => (one
      ? this.figure(t, one.label, one.text, one.level, "", ground).w(px) : div().w(px).flex_none());
    return [h_flex().id(`agent-usage-${this.slides}${n}`).h(USAGE_ROW).flex_none().pl(24).pr(PAD / 2).gap(6)
      .items_center().rounded(6).relative().when(row.current, (e) => e.bg(ground))
      .when(!this.still, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.turnBlock(row.key, cx)))
      .tooltip([[row.name, row.plan].filter(Boolean).join(" "), row.said].filter(Boolean).join(": "))
      .child(agentMark(look.programs[row.key], 14) ?? icon("bot", 14).text_color(t.muted))
      .child(h_flex().flex_1().min_w(0).gap(6).items_center()
        .child(div().flex_none().child(row.name))
        .when(Boolean(row.plan), (e) => e.child(div().min_w(0).truncate().text_size(11).text_color(t.dim)
          .child(row.plan ?? ""))))
      .when(Boolean(row.five || row.week), (e) => e.child(column(row.five, FIVE)).child(column(row.week, WEEK)))
      .when(!row.five && !row.week && !open && Boolean(glance), (e) => e.child(this.figure(t, "",
        glance?.figure ?? "", glance?.level ?? null, glance?.after ?? "", ground)))
      .child(fold(`agent-usage-fold-${this.slides}${n}`, open, 14, t.dim))
      .when(open && Boolean(row.bar), (e) => e.child(h_flex().absolute().bottom(0).left(NAME).right(PAD / 2).h(3)
        .rounded_full().overflow_hidden().bg(t.canvas)
        .child(div().h_full().flex_basis(0).flex_grow(used).bg(levelFill(t, row.bar?.level ?? "")))
        .child(div().h_full().flex_basis(0).flex_grow(100 - used)))),
    ...(open && usageLine(row) ? [h_flex().h(USAGE_LINE).flex_none().pl(NAME).pr(PAD / 2).gap(8).items_center()
      .text_size(10).text_color(t.dim)
      .when(Boolean(row.resets), (e) => e.child(div().flex_1().min_w(0).truncate().child(resets)))
      .when(Boolean(row.age), (e) => e.child(div().flex_none().child(row.age ?? "")))] : []),
    ...(open ? (this.costs[row.key] ?? []).map((line) => this.cost(t, line)) : [])];
  }

  /** A cost LINE under an agent's row (usage.html's glance, as a Properties row): its label left in muted and its
   * figure right, semibold, with its unit; a budget's bar as the limits' (yellow once over); the budget's words 10
   * in dim, the pace in yellow once over. @param {import("./layers.js").CostLine} line */
  cost(t, line) {
    const warn = levelInk(t, "warn", t.surface), row = h_flex().flex_none().pl(NAME).pr(PAD / 2).items_center();
    if (line.kind === "bar") {
      const share = Math.round(line.share * 100);
      return row.h(COST_BAR).child(h_flex().flex_1().h(3).rounded_full().overflow_hidden().bg(t.canvas)
        .child(div().h_full().flex_basis(0).flex_grow(share).bg(levelFill(t, line.over ? "warn" : "ok")))
        .child(div().h_full().flex_basis(0).flex_grow(100 - share)));
    }
    if (line.kind === "words") {
      return row.h(USAGE_LINE).text_size(10).text_color(t.dim).child(line.text)
        .child(div().min_w(0).truncate().when(line.over, (e) => e.text_color(warn)).child(line.pace));
    }
    return row.h(COST_LINE).gap(6).text_size(11)
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(line.label))
      .child(div().flex_none().font_semibold().when(line.over, (e) => e.text_color(warn)).child(line.figure))
      .when(Boolean(line.unit), (e) => e.child(div().flex_none().text_color(t.muted).child(line.unit)));
  }

  /** A line under a section in its rows' name column, HIGH px: "N more", or that it has none. @param {string} words
   * @param {number} high */
  line(t, words, high) {
    return h_flex().h(high).flex_none().pl(24).pr(6).gap(6).items_center()
      .text_size(11).text_color(t.dim).child(div().size(14).flex_none()).child(words);
  }

  /** SECTION's head: its chevron, title and count (Usage has none), its summary (summarized()) in its tones,
   * Connectors' + (ADD: core's words), a head's own button (END: Usage's Open Usage), its cost; a click folds it (not
   * under a filter). @param {Section} section @param {boolean} open @param {any} [add] @param {any} [end] */
  section(t, section, open, add = null, end = null) {
    const key = `agent-section-${this.slides}${section.id}`;
    return h_flex().id(key).h(HEAD_H).flex_none().px(PAD / 2).gap(6).items_center().rounded(6)
      .when(!this.query, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
      .child(h_flex().id(`${key}-head`).flex_1().min_w(0).h_full().gap(6).items_center()
        .when(!this.query, (e) => e.cursor_pointer()
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.toggle(section.id, cx)))
        .child(fold(`${key}-fold`, open, 14, t.dim))
        .child(div().flex_none().font_bold().child(section.title))
        .when(section.count !== null, (e) => e.child(div().flex_none().text_size(11).text_color(t.dim)
          .child(String(section.count))))
        .child(h_flex().flex_1().min_w(0).gap(8).justify_end().overflow_hidden().text_size(11)
          .when(summarized(section, open), (e) => e.children(section.summary.map((one) => div().min_w(0).truncate()
            .text_color(toneInk(t, one.tone)).child(one.text))))))
      .when(Boolean(add), (e) => e.child(this.plus(t, add))).when(Boolean(end), (e) => e.child(end))
      .when(section.cost !== null, (e) => e.child(div().w(COST).flex_none().text_right().text_size(11)
        .text_color(t.dim).child(section.cost ?? "")));
  }

  /** Connectors' + (connectors.html's .lsec .add): ADD px square, raised with a hairline in the accent while its menu
   * is open under it, its right edge with the button's. @param {any} add */
  plus(t, add) {
    const open = this.addMenu, clear = `${t.accent}00`;
    const button = div().id(`agent-add-${this.slides}`).size(ADD).flex_none().flex().items_center().justify_center()
      .rounded(6).border_1().border_color(open ? t.accent : clear).text_color(open ? t.foreground : t.muted)
      .cursor_pointer().when(open, (e) => e.bg(t.raised)).when(!open, (e) => e.tooltip(add.tip))
      .hover((/** @type {any} */ s) => s.bg(t.raised).text_color(t.foreground)).child(icon("plus", 14));
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
    if (e.key === "escape") this.showWays(false, cx);
    else if (e.key === "up" || e.key === "down") {
      list.cursor = panelStep(ways.length, list.cursor, e.key === "down" ? 1 : -1, () => false);
    } else if ((e.key === "enter" || e.key === "space") && list.cursor !== null) this.add(ways[list.cursor], cx);
    else return;
    cx.stop_propagation();
    cx.notify();
  }

  /** A source's tag (parts.js's scopeTag) of WORD in TONE's color, cut to its column, its tip the whole word then.
   * @param {string} word @param {string} tone @param {string} id */
  tag(t, word, tone, id) {
    const cut = tagWord(word), tag = scopeTag(t, cut, tagColors(t)[TAG_ROLE[tone] ?? "local"]);
    return cut === word ? tag : tag.id(id).tooltip(word);
  }

  /** ROW of SECTION (its N-th shown): its icon (a connector's logo), name and note, both agents' icons, the used dot;
   * its state (a spinner while its agent works on its server, or signs in), its tag in the tags' column (TAGS px; 0:
   * none), its cost. A conflict: its sentence under its name. A press chooses it. @param {Row} row */
  row(t, section, row, n, tags, look) {
    const conflict = Boolean(row.warn && row.note), tone = row.state?.tone ?? "", chosen = row.id === this.chosen;
    const checking = this.checking.has(serverOf(row) ?? ""), signing = Boolean(row.properties?.words);
    const name = div().min_w(0).truncate().text_color(row.dim ? t.muted : t.foreground).child(row.name);
    const note = div().min_w(0).flex_shrink(NOTE_SHRINK).truncate().text_size(11);
    const both = row.agents.length > 1 ? row.agents.map((key) => agentMark(look.programs[key], 12)).filter(Boolean)
      : [];
    const words = conflict ? v_flex().flex_1().min_w(0).child(name)
      .child(note.text_color(toneInk(t, "warn")).child(row.note ?? ""))
      : h_flex().flex_1().min_w(0).gap(6).items_center().child(name)
        .when(Boolean(row.note), (e) => e.child(note.text_color(t.dim).child(row.note ?? "")))
        .when(both.length > 1, (e) => e.child(h_flex().id(`agent-both-${section.id}-${n}`).flex_none().gap(2)
          .items_center().text_color(t.muted).children(both)
          .tooltip(`${row.agents.map((key) => NAMES[key] ?? key).join(" and ")} both read it`)))
        .when(row.used, (e) => e.child(div().id(`agent-used-${section.id}-${n}`).size(6).flex_none().rounded_full()
          .bg(t.ansi2).tooltip("Used in this conversation")));
    return h_flex().id(`agent-row-${this.slides}${section.id}-${n}`).h(conflict ? WARN_H : ROW_H).flex_none().pl(24)
      .pr(PAD / 2).gap(6).items_center().rounded(6).cursor_pointer()
      .when(chosen, (e) => e.bg(chosenFill(t))).when(!chosen, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover)))
      .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(row.id, cx))
      .when(Boolean(row.note), (e) => e.tooltip(`${row.name}: ${row.note}`))
      .child(row.icon === "plug" ? brandMark(t, row.brand, row.name, LOGO) : icon(ICON[row.icon] ?? "file", 14)
        .text_color(row.warn ? toneInk(t, "warn") : tone === "bad" ? toneInk(t, "bad") : t.muted))
      .child(words)
      .when(checking || signing, (e) => e.child(spinner(t)))
      .when(Boolean(row.state) && !checking, (e) => e.child(div().flex_none().text_size(11)
        .text_color(toneInk(t, tone, chosen ? chosenFill(t) : t.surface)).child(row.state?.text ?? "")))
      .when(tags > 0 && !conflict, (e) => e.child(h_flex().w(tags).flex_none().justify_end()
        .when(Boolean(row.tag), (e) => e.child(this.tag(t, row.tag?.text ?? "", row.tag?.tone ?? "",
          `agent-tag-${section.id}-${n}`)))))
      .when(section.cost !== null && !conflict, (e) => e.child(div().w(COST).flex_none().text_right().text_size(11)
        .text_color(t.dim).child(row.cost ?? "")));
  }

  /** The chosen ROW's properties (center-chat.html's and connectors.html's .insp) on the side's level: its title, its
   * lines as a design tool's Properties (the label in LABEL px, the value, a third column), what to do while it signs
   * in, its error, a rule's first lines or a description, what can be done (doable()). @param {Row} row */
  properties(t, row, look) {
    const props = row.properties, ground = t.chrome, tone = toneOf(row);
    const lines = propertyLines(row), acts = doable(row, look.agent), error = errorColors(t, ground);
    const checking = this.checking.has(serverOf(row) ?? ""), code = codeFont();
    const excerpt = row.icon === "file" ? (props?.text ?? "").split("\n").filter(Boolean) : [];
    const chat = acts.some((one) => one.id.startsWith("turn-")) ? this.chat() : null;
    return v_flex().id(`agent-properties-${this.slides}`).flex_none().p(PAD).gap(6).border_t(1)
      .border_color(t.border).bg(ground).text_size(12)
      .child(h_flex().h(20).flex_none().gap(8).items_center()
        .child(row.icon === "plug" ? brandMark(t, row.brand, row.name, LOGO) : icon(ICON[row.icon] ?? "file", 14)
          .text_color(tone === "warn" || tone === "bad" ? toneInk(t, tone, ground) : t.muted))
        .child(div().flex_1().min_w(0).truncate().font_bold().child(props?.title ?? row.name))
        .when(checking, (e) => e.child(spinner(t)))
        .when(Boolean(row.state) && !checking, (e) => e.child(div().flex_none().text_size(11)
          .text_color(toneInk(t, row.state?.tone ?? "", ground)).child(row.state?.text ?? ""))))
      .when(lines.length > 0, (e) => e.child(v_flex().flex_none().children(lines.map((line, n) =>
        propertyLine(t, `agent-property-${this.slides}${n}`, line, LABEL, PHRASES.includes(line[0]) ? null : code)))))
      .when(Boolean(props?.words), (e) => e.child(h_flex().h(20).flex_none().gap(8).items_center()
        .child(spinner(t)).child(div().min_w(0).truncate().child(props?.words ?? ""))))
      .when(Boolean(props?.error), (e) => e.child(div().flex_none().px(8).py(6).rounded(6).bg(error.fill)
        .font_family(code).text_size(11).text_color(error.ink).child(props?.error ?? "")))
      .when(excerpt.length > 0, (e) => e.child(v_flex().flex_none().font_family(code).text_size(11)
        .text_color(t.muted).children(excerpt.map((line) => div().h(16).truncate().child(line)))))
      .when(Boolean(props?.text) && !excerpt.length, (e) => e.child(div().flex_none().max_h(48).overflow_hidden()
        .text_size(11).line_height("16px").text_color(t.muted).child(props?.text ?? "")))
      .when(Boolean(this.failed), (e) => e.child(div().flex_none().text_size(11)
        .text_color(toneInk(t, "bad", ground)).child(this.failed ?? "")))
      .when(acts.length > 0, (e) => e.child(h_flex().flex_none().pt(2).gap(6).flex_wrap().children(acts.map((one,
        n) => {
        // Turn off or on is Claude's own command in a conversation: with no Claude in the folder it waits
        const waits = one.id.startsWith("turn-") && !chat, needs = this.found?.connect?.needs?.[one.id];
        return actButton(t, `agent-act-${this.slides}${n}`, one.id === "retry" && checking ? "Checking…"
          : one.label, actionLook(one, n), !checking && !waits, (/** @type {any} */ cx) => this.act(one, cx),
        waits ? needs : null);
      }))));
  }

  /** "By URL…" (connectors.html's Hozzáadás) in the properties' place, in core's words (ADD): Name and URL, fields
   * FIELD high on the window's level (the keys' one edged in the accent, a refused one in red, why under them), For
   * as a two-part switch, Add and connect, Cancel. Enter adds, Tab steps on, Esc cancels. @param {any} add */
  adder(t, add) {
    const form = /** @type {Form} */ (this.form), ground = t.chrome, key = `agent-form-${this.slides}`;
    const bad = toneInk(t, "bad", ground), code = codeFont();
    const line = (/** @type {string} */ label, /** @type {any} */ value) => h_flex().h(FIELD).flex_none().gap(8)
      .items_center().child(div().w(LABEL).flex_none().text_color(t.dim).child(label)).child(value);
    const typed = (/** @type {"name" | "url"} */ id) => line(add.fields[id], h_flex().id(`${key}-${id}`).flex_1()
      .min_w(0).h_full().px(8).items_center().rounded(8).border_1().bg(t.canvas).cursor_text()
      .border_color(form.error?.field === id ? bad : form.focus === id ? t.accent : t.border)
      .on_mouse_down("left", (/** @type {any} */ _e, /** @type {any} */ cx) => {
        form.focus = id;
        cx.notify();
      })
      .child(Input.new(form[id]).flex_1().h_full().font_family(code).text_size(11).text_color(t.foreground)));
    const scopes = h_flex().flex_none().max_w_full().p(2).gap(2).rounded(6).bg(t.canvas)
      .children(add.scopes.map((/** @type {{ id: string, label: string }} */ one) => {
        const on = one.id === form.scope;
        return div().id(`${key}-for-${one.id}`).h(20).min_w(0).px(6).flex().items_center().rounded(4)
          .when(on, (e) => e.bg(t.raised).text_color(t.foreground))
          .when(!on, (e) => e.text_color(t.dim).cursor_pointer()
            .hover((/** @type {any} */ s) => s.text_color(t.foreground))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
              form.scope = one.id;
              cx.notify();
            }))
          .child(div().min_w(0).truncate().child(one.label));
      }));
    return v_flex().id(key).flex_none().p(PAD).gap(6).border_t(1).border_color(t.border).bg(ground).text_size(12)
      .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => {
        if (e.key === "escape") this.dropForm(cx);
        else if (e.key === "tab") this.focusField(form.focus === "name" ? "url" : "name", cx);
        else return;
        cx.stop_propagation();
      })
      .child(h_flex().h(20).flex_none().gap(8).items_center().child(icon("link", 14).text_color(t.muted))
        .child(div().flex_1().min_w(0).truncate().font_bold().child(add.title)))
      .child(typed("name")).child(typed("url"))
      .when(add.scopes.length > 0, (e) => e.child(line(add.fields.scope, scopes)))
      .when(Boolean(form.error), (e) => e.child(div().flex_none().text_size(11).text_color(bad)
        .child(form.error?.error ?? "")))
      .child(h_flex().flex_none().pt(2).gap(6).flex_wrap()
        .child(actButton(t, `${key}-add`, form.busy ? "Adding…" : add.submit, "solid", !form.busy,
          (/** @type {any} */ cx) => this.submit(cx)))
        .child(actButton(t, `${key}-cancel`, add.cancel, "plain", true,
          (/** @type {any} */ cx) => this.dropForm(cx))));
  }
}
