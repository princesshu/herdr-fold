// @ts-check
// The Agent panel's own rules, pure: which agent it shows, which of a section's rows, what a filter finds, each
// tone's color. The words, their order and the properties are core's (agent_setup.py's layers()), the TUI's too.
import { contrast, mixColor, readableOn } from "./agents.js";

export const AGENT_CHOSEN = "herdr-fold.agent-chosen";   // shared: each space's agent, picked in the panel's head
export const AGENT_OPEN = "herdr-fold.agent-open";       // shared: {space: {section: open}}, a fold kept per space
export const AGENT_ASK = "herdr-fold.agent-ask";         // shared: {space, section, row, at}: openAgentPanel()'s ask
export const AGENT_PROBLEMS = "herdr-fold.agent-problems";   // shared: {space: {tone, said}}, the tab's and rail's dot
// the actions core offers that this client does
export const WORKS = ["open", "retry", "connect", "turn-off", "turn-on", "sign-out", "graph"];
export const CLAUDES = ["retry", "turn-off", "turn-on"];    // Claude's own commands: never on another agent's row
export const WAITS = ["reopen", "cancel"];              // what a row signing in offers instead (core's connecting())
// a sign-in's terminal (no pane): its server's name, whose it is, when it started (ms), as its labels
export const MCP_LOGIN = "herdr-fold.mcp-login", MCP_AGENT = "herdr-fold.mcp-agent", MCP_AT = "herdr-fold.mcp-at";
export const SIGNING_MS = 600000;                       // ms a sign-in waits for its browser at most
export const ASK_MS = 10000;      // ms an ask waits for its panel (a view's copy starts once it first shows)
export const SERVER = "connector:";                     // a server's row id: this, then its name, as core's
export const READ = ["claude", "codex"];                // the agents core reads a setup of (agent_setup.py's setup())
export const NAMES = /** @type {Record<string, string>} */ ({ claude: "Claude", codex: "Codex" });    // as core's
export const FOLDED = ["agents"];                       // folded till opened, as center-chat.html's Agent panel
export const FIRST = 5;           // rows a section shows before "N more": its problems and used ones always
export const TAG = 12;            // characters of a tag at most (a plugin's name may be long), as the TUI's cells
export const NARROW = 300;        // px: a panel under it drops its tags; the states and the costs stay
// px: a section's head, a row, a conflict's two lines, "N more"; what a section's rows take sprung open (bodyHeight)
export const HEAD_H = 28, ROW_H = 26, WARN_H = 40, MORE_H = 24;
// px: a Usage row (an open one's bar on its lower edge), a line of words under one (when it resets, a reading's age)
export const USAGE_ROW = 28, USAGE_LINE = 16;
const RANK = /** @type {Record<string, number>} */ ({ ok: 1, warn: 2, bad: 3 });   // how near its end a level is
export const LABEL = 44;          // px: the properties' labels' column, center-chat.html's .ikv
// under the home folder, what each agent's setup is read from: a change there is a new read
export const WATCHED = /** @type {Record<string, string>} */ ({ claude: ".claude", codex: ".codex" });
// in the space's folder, what a setup is read from: these folders, and files so named at any depth
const SETUP_DIRS = [".claude", ".codex"], SETUP_FILES = ["CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".mcp.json"];
const TAG_CHAR = 6, TAG_PAD = 12;     // px: a tag's character at 11 at most, and its padding (parts.js's scopeTag)

/** A row's action, as core offers it: open PATH, or Claude's command on SERVER. @typedef {{ id: string, label: string,
 * path: string | null, server: string | null, primary: boolean }} Action */
/** A row's properties: its lines [label, value, a third or null], a text, an error; WORDS while it signs in.
 * @typedef {{ title: string, state: { text: string, tone: string } | null, lines: [string, string, string | null][],
 * text: string | null, error: string | null, actions: Action[], words?: string }} Properties */
/** A row as core words it. @typedef {{ id: string, icon: string, name: string, note: string | null, dim: boolean,
 * tag: { text: string, tone: string } | null, state: { text: string, tone: string } | null, cost: string | null,
 * used: boolean, agents: string[], warn: boolean, brand?: string | null, properties?: Properties }} Row */
/** A section. @typedef {{ id: string, title: string, count: number | null, cost: string | null,
 * summary: { text: string, tone: string }[], rows: Row[] }} Section */

/** Whether ROW is a problem: failed, to sign in, a conflict. @param {Row} row */
export const problem = (row) => row.warn || ["bad", "warn"].includes(row.state?.tone ?? "");

/** Whether ROW holds every word of QUERY, case aside: in its name, note, state or tag. @param {Row} row
 * @param {string} query */
export function matches(row, query) {
  const said = [row.name, row.note, row.state?.text, row.tag?.text].filter(Boolean).join("\n").toLowerCase();
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => said.includes(word));
}

/** SECTION's rows shown and how many wait under "N more": its first FIRST, its problems, used ones and the CHOSEN one,
 * all once MORE; never "1 more"; with a QUERY, every row it finds. @param {Section} section
 * @param {{ query?: string, more?: boolean, chosen?: string | null }} [how] @returns {{ rows: Row[], more: number }} */
export function shown(section, { query = "", more = false, chosen = null } = {}) {
  const rows = section.rows;
  if (query.trim()) return { rows: rows.filter((row) => matches(row, query)), more: 0 };
  if (more || rows.length <= FIRST) return { rows, more: 0 };
  const kept = rows.filter((row, n) => n < FIRST || problem(row) || row.used || row.id === chosen);
  return rows.length - kept.length > 1 ? { rows: kept, more: rows.length - kept.length } : { rows, more: 0 };
}

/** What ROWS and "N more" (MORE of them) take under a section's head, px; none: the line saying so.
 * @param {Row[]} rows @param {number} more */
export const bodyHeight = (rows, more) => (rows.length ? rows.reduce((px, row) => px + (row.warn && row.note ? WARN_H
  : ROW_H), 0) : ROW_H) + (more ? MORE_H : 0);

/** Whether SECTION's summary shows beside its count: the permissions' behaviors always, the sub-agents' names only
 * while it is folded (OPEN, the rows name them). @param {Section} section @param {boolean} open */
export const summarized = (section, open) => section.summary.length > 0
  && (!open || section.summary.some((one) => one.tone !== "ok"));

/** Whether SECTION is open in SPACE: as KEPT ({space: {section: open}}) has it, else all but FOLDED.
 * @param {any} kept @param {string | null} space @param {string} section */
export function sectionOpen(kept, space, section) {
  const mine = kept && typeof kept === "object" && space !== null ? kept[space] : null;
  return typeof mine?.[section] === "boolean" ? mine[section] : !FOLDED.includes(section);
}

/** KEPT with SECTION open or not (OPEN) in SPACE, the spaces no longer LIVE left out. @param {any} kept
 * @param {string} space @param {string} section @param {boolean} open @param {Set<string>} live */
export function keepOpen(kept, space, section, open, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  const mine = was[space] && typeof was[space] === "object" ? was[space] : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([id, v]) => live.has(id) && v && typeof v === "object")),
    [space]: { ...mine, [section]: open } };
}

/** A tag's WORD as its column holds it: TAG characters at most. @param {string} word */
export const tagWord = (word) => ([...word].length > TAG ? `${[...word].slice(0, TAG - 1).join("")}…` : word);

/** The tags' column of SECTION, px: as wide as the widest tag of its rows, shown or under "N more", so its states stand
 * in one column before it and nothing moves as "N more" opens; 0 with no tag. @param {Section} section */
export function tagRoom(section) {
  const widest = Math.max(0, ...section.rows.map((row) => (row.tag ? [...tagWord(row.tag.text)].length : 0)));
  return widest ? widest * TAG_CHAR + TAG_PAD : 0;
}

/** Whether PATHS, changed under the watched ROOT, touch a setup: in the space's FOLDER only its rules and settings
 * (the agent edits the rest all day), in an agent's own folder anything; ROOT itself: everything changed.
 * @param {string[]} paths @param {string} root @param {string | null} folder */
export function touches(paths, root, folder) {
  if (root !== folder) return paths.length > 0;
  return paths.some((path) => {
    const parts = path === root ? [] : path.slice(root.length + 1).split("/");
    return !parts.length || SETUP_DIRS.includes(parts[0]) || SETUP_FILES.includes(parts[parts.length - 1]);
  });
}

/** A state's or a problem's TONE as theme T's color: failed and deny red, sign in and ask yellow, allow green,
 * connecting the accent, off dim, any other muted. @param {Record<string, string>} t @param {string} tone */
export const toneColor = (t, tone) => ({ bad: t.ansi1, deny: t.ansi1, warn: t.ansi3, ask: t.ansi3, allow: t.ansi2,
  busy: t.accent, off: t.dim })[tone] ?? t.muted;

const TINTS = /** @type {Record<string, number>} */ ({ bad: 0.12, warn: 0.1 });    // a problem chip's fill, of its tone
const HEX = /^#[0-9a-f]{6}$/i;

/** TONE's color as small words read it on the card: toneColor's, moved toward the text until it reads 4.5:1 on GROUND
 * (the card's surface unless given), as a source's tag is; the faint tones (off, any other) as they are.
 * @param {Record<string, string>} t @param {string} tone @param {string} [ground] */
export function toneInk(t, tone, ground = t.surface) {
  const color = toneColor(t, tone);
  if (color === t.dim || color === t.muted || ![color, t.foreground, ground].every((hex) => HEX.test(hex ?? ""))) {
    return color;
  }
  return readableOn(color, t.foreground, ground);
}

/** A problem chip of TONE in theme T: its fill (the tone's tint of the card, center-chat.html's 12% and 10%) and its
 * words, read 4.5:1 on that fill; LIFT more of the tone under the pointer; on GROUND where it is not the card.
 * @param {Record<string, string>} t @param {string} tone @param {number} [lift] @param {string} [ground] */
export function chipColors(t, tone, lift = 0, ground = t.surface) {
  const color = toneColor(t, tone);
  const fill = [color, ground].every((hex) => HEX.test(hex ?? "")) ? mixColor(ground, color, (TINTS[tone] ?? 0.1)
    + lift) : t.raised;
  return { fill, ink: toneInk(t, tone, fill) };
}

export const CHIP_LIFT = 0.06;    // a pressable chip under the pointer: this much more of its tone (words still read)
const ERROR_TINT = 0.08 - TINTS.bad;      // the properties' error box: red's 8% (center-chat.html's .ierr)

/** The properties' error box in theme T, on the properties' GROUND: its fill and its words, as a chip's.
 * @param {Record<string, string>} t @param {string} ground */
export const errorColors = (t, ground) => chipColors(t, "bad", ERROR_TINT, ground);

/** The chosen row's fill in theme T: the accent's 14% on the card (center-chat.html's .lrow.sel).
 * @param {Record<string, string>} t */
export const chosenFill = (t) => ([t.accent, t.surface].every((hex) => HEX.test(hex ?? ""))
  ? mixColor(t.surface, t.accent, 0.14) : t.selected ?? t.raised);

/** The worst problem's tone in core's LAYERS, for the tab's and the rail's dot: "bad" over "warn", else null.
 * @param {any} layers @returns {"bad" | "warn" | null} */
export function problemTone(layers) {
  const tones = new Set((layers?.health?.problems ?? []).map((/** @type {any} */ one) => one.tone));
  return tones.has("bad") ? "bad" : tones.has("warn") ? "warn" : null;
}

/** KEPT ({space: {tone, said}}) with SPACE's problems as core's LAYERS has them (none: left out), the spaces no longer
 * LIVE left out; KEPT itself where nothing changed. @param {any} kept @param {string} space @param {any} layers
 * @param {Set<string>} live */
export function keepProblems(kept, space, layers, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {}, tone = problemTone(layers);
  const next = Object.fromEntries(Object.entries(was).filter(([id]) => live.has(id) && id !== space));
  if (tone) next[space] = { tone, said: layers.health.problems.map((/** @type {any} */ one) => one.text).join(", ") };
  return JSON.stringify(next) === JSON.stringify(kept) ? kept : next;
}

/** The row ID among SECTIONS with its section, or null. @param {Section[]} sections @param {string | null} id
 * @returns {{ section: Section, row: Row } | null} */
export function chosenRow(sections, id) {
  for (const section of id ? sections : []) {
    const row = section.rows.find((one) => one.id === id);
    if (row) return { section, row };
  }
  return null;
}

/** ROW's actions done here, in core's order: core's (WORKS), a sign-in's own (WAITS); Claude's own commands on
 * Claude's rows alone (AGENT: whose panel). @param {Row} row @param {string} [agent] @returns {Action[]} */
export const doable = (row, agent = "claude") => (row.properties?.actions ?? []).filter((one) =>
  [...WORKS, ...WAITS].includes(one.id) && (agent === "claude" || !CLAUDES.includes(one.id)));

/** `hc run`'s arguments for ARGV (the agent's own login, core's) in a terminal with no pane, in FOLDER: labelled with
 * its server's NAME, its AGENT and when it started (AT, ms). @param {string[]} argv
 * @param {{ agent: string, name: string, folder: string, at: number }} how */
export const loginRun = (argv, { agent, name, folder, at }) => ["run", "--bg", "--json", "--rm", "--cwd", folder,
  "--label", `${MCP_LOGIN}=${name}`, "--label", `${MCP_AGENT}=${agent}`, "--label", `${MCP_AT}=${at}`, "--", ...argv];

/** The sign-ins of AGENT running among TERMINALS (the app's), by server: {name: {address, at}}; one per server.
 * @param {any[]} terminals @param {string} agent @returns {Record<string, { address: string, at: number }>} */
export const signIns = (terminals, agent) => Object.fromEntries(terminals.filter((one) => one.state === "live"
  && typeof one.labels?.[MCP_LOGIN] === "string" && one.labels[MCP_AGENT] === agent)
  .map((one) => [one.labels[MCP_LOGIN], { address: one.address, at: Number(one.labels[MCP_AT]) }]));

/** The sign-ins among TERMINALS left waiting past SIGNING_MS at NOW, or with no start told: their addresses, to end.
 * @param {any[]} terminals @param {number} now @returns {string[]} */
export const overdue = (terminals, now) => terminals.filter((one) => one.state === "live"
  && typeof one.labels?.[MCP_LOGIN] === "string" && !(now - Number(one.labels[MCP_AT]) <= SIGNING_MS))
  .map((one) => one.address);

/** ROW while its agent signs in to its server, in core's words (CONNECT, connecting()'s): its state, and for its
 * properties what to do meanwhile and the two things to press. @param {Row} row @param {any} connect @returns {Row} */
export function signingRow(row, connect) {
  const server = serverOf(row);
  return { ...row, state: connect.state, dim: false, properties: { title: row.properties?.title ?? row.name,
    state: connect.state, lines: [], text: null, error: null, words: connect.words,
    actions: connect.actions.map((/** @type {any} */ one, /** @type {number} */ n) => ({ ...one, path: null, server,
      primary: !n })) } };
}

const SWITCHED = /** @type {Record<string, boolean>} */ ({ on: true, "not checked": true, pending: true,
  "off here": false });               // a server's state (core's) as the + menu's switch: any other has none
const PILLS = [["failed", "bad"], ["sign in", "warn"]];    // the problems the + menu's head counts, as core's health

/** The chat's + menu's Connectors of SERVERS (agent_setup.py's setup): the failed and sign-in ones counted on pills,
 * the ones on or off in this folder a row each, in core's order. @param {unknown} servers */
export function plusMenu(servers) {
  const all = (Array.isArray(servers) ? servers : []).filter((one) => typeof one?.name === "string");
  return { pills: PILLS.map(([state, tone]) => ({ text: `${all.filter((one) => one.state === state).length} ${state}`,
    tone })).filter((pill) => !pill.text.startsWith("0 ")),
  rows: all.filter((one) => one.state in SWITCHED).map((one) => ({ name: one.name, label: String(one.label
    ?? one.name), brand: one.brand ?? null, on: SWITCHED[one.state] })) };
}

/** ROWS (plusMenu's) with the switches just turned (ASKED: {name: {on, at}}) shown as asked, and what of ASKED still
 * waits: not what its row shows already, nor one older than WAIT ms at NOW, nor one with no row. @param {any[]} rows
 * @param {Record<string, { on: boolean, at: number }>} asked @param {number} now @param {number} wait */
export function switched(rows, asked, now, wait) {
  const waits = Object.fromEntries(Object.entries(asked).filter(([name, one]) => now - one.at < wait
    && rows.some((row) => row.name === name && row.on !== one.on)));
  return { rows: Object.keys(waits).length ? rows.map((row) => (waits[row.name] ? { ...row, on: waits[row.name].on }
    : row)) : rows, asked: waits };
}

const STATES = ["on", "failed", "sign in", "pending", "not approved", "off here", "off", "not checked"];   // core's

/** SERVERS (agent_setup.py's setup) with Claude's own looks over them (CHECKED: {name: {base, state}}), as core's
 * checked_over: each shown while its server's state is still the one it had then. @param {unknown} servers
 * @param {Record<string, any>} checked @returns {any[]} */
export const checkedOver = (servers, checked) => (Array.isArray(servers) ? servers : []).map((one) => {
  const said = checked?.[one?.name];
  return said && STATES.includes(said.state) && said.base === one.state ? { ...one, state: said.state } : one;
});

/** ROW's tone: a conflict's yellow, else its state's. @param {Row} row */
export const toneOf = (row) => (row.warn ? "warn" : row.state?.tone ?? "");

const OPENED = /^https?:\/\/\S+$/;       // a line that is an address alone

/** The address a sign-in printed on its SCREEN (`hc read`'s rows) while it waits: a row's only word, with the rows
 * a narrow terminal wrapped it over; null until it is there. Core checks it before it is opened (login_url).
 * @param {string} screen */
export function printedAddress(screen) {
  const rows = screen.split("\n").map((row) => row.trim()), first = rows.findIndex((row) => OPENED.test(row));
  if (first < 0) return null;
  let found = rows[first];
  for (const row of rows.slice(first + 1)) {
    if (!row || /\s/.test(row)) break;
    found += row;
  }
  return found;
}

/** The Claude that SPACE's folder's `/mcp` command is typed to: a chat of the space (TERMINALS, its tab under the
 * label TAB), or Claude in a pane there (AGENTS, PANES), an idle one first; its terminal's address, or null.
 * @param {any} space @param {any[]} agents @param {any[]} panes @param {any[]} terminals @param {string} tab */
export function claudeIn(space, agents, panes, terminals, tab) {
  if (!space?.folder) return null;
  const tabs = new Set((space.tabs ?? []).map((/** @type {any} */ one) => one.id));
  const found = [...agents.filter((a) => a.space === space.id && a.program?.key === "claude"
    && panes.find((p) => p.pane === a.pane)?.cwd === space.folder),
  ...terminals.filter((c) => c.state === "live" && tabs.has(c.labels?.[tab]) && c.program?.key === "claude")];
  return (found.find((one) => one.status === "idle") ?? found[0])?.address ?? null;
}

/** How ACTION, the N-th of its row, is drawn (connectors.html's .go2, .btn, .btn.ghost): Connect on the accent, else
 * the first raised and the rest plain. @param {{ id: string }} action @param {number} n */
export const actionLook = (action, n) => (action.id === "connect" ? "solid" : n ? "plain" : "raised");

const TILES = ["ansi6", "ansi3", "ansi4", "ansi5", "ansi2", "ansi1"];    // the spaces' avatars' (logic.js's MARK)

/** A connector with no known brand: NAME's first letter on a tile, its color by its name. @param {string} name */
export function tile(name) {
  const sum = [...name].reduce((all, ch) => (all * 31 + (ch.codePointAt(0) ?? 0)) % 9973, 7);
  return { letter: [...name.trim()][0]?.toUpperCase() ?? "?", color: TILES[sum % TILES.length] };
}

/** ROW's property lines as its properties draw them under their title: one saying only what that title says (its
 * name, its state) left out, as the TUI leaves out what the row shows; a conflict's all (both rules, each with where
 * it is). @param {Row} row */
export function propertyLines(row) {
  const lines = row.properties?.lines ?? [], titled = [row.properties?.title, row.properties?.state?.text];
  return row.warn ? lines : lines.filter(([, value]) => !titled.includes(value));
}

/** The server a connector's ROW stands for (what Claude checks again), or null. @param {Row} row */
export const serverOf = (row) => (row.id.startsWith(SERVER) ? row.id.slice(SERVER.length) : null);

/** ASK (openAgentPanel()'s: {space, section, row, at}) where this panel answers it: SPACE's, newer than the LAST one
 * answered, no older than ASK_MS at NOW; else null. @param {any} ask @param {string | null} space
 * @param {number | null} last @param {number} now */
export const asked = (ask, space, last, now) => (ask && typeof ask === "object" && ask.space === space
  && typeof ask.at === "number" && ask.at !== last && now - ask.at <= ASK_MS && now >= ask.at ? ask : null);

/** The health bar's parts, each with its share of what loads at start (BAR, core's): none of 0 tokens.
 * @param {{ part: string, tokens: number }[]} bar */
export function barParts(bar) {
  const all = bar.reduce((sum, one) => sum + one.tokens, 0);
  return bar.filter((one) => one.tokens > 0).map((one) => ({ ...one, share: one.tokens / all }));
}

/** The agent in TAB, of those core reads: a chat tab's (TERMINALS, the app's; its conversation's id its SESSION), else
 * one in a pane (PANES); null. LABELS: the chat's labels' names. @param {string | null | undefined} tab
 * @param {any[]} panes @param {any[]} terminals @param {{ tab: string, session: string }} labels */
export function tabAgent(tab, panes, terminals, labels) {
  if (!tab) return null;
  const chat = terminals.find((c) => c.state === "live" && c.labels?.[labels.tab] === tab
    && READ.includes(c.program?.key ?? ""));
  if (chat) return { agent: chat.program.key, session: chat.labels?.[labels.session] ?? null };
  const pane = panes.find((p) => p.tab === tab && READ.includes(p.program?.key ?? ""));
  return pane ? { agent: pane.program.key, session: null } : null;
}

const KEY = /^[a-z][a-z0-9_-]{0,63}$/;      // an agent's key as a space keeps it: never an option or a stray value

/** The agent the panel shows in SPACE: the one KEPT for it ({space: agent}, picked in its head's list; one core does
 * not read too), else the FOCUSED tab's, else the one used last (RECENT's first that core reads), else Claude.
 * @param {{ kept?: any, space?: string | null, focused?: string | null, recent?: unknown }} how @returns {string} */
export function chosenAgent({ kept = null, space = null, focused = null, recent = null }) {
  const mine = kept && typeof kept === "object" && space !== null ? kept[space] : null;
  if (typeof mine === "string" && KEY.test(mine)) return mine;
  if (focused && READ.includes(focused)) return focused;
  return (Array.isArray(recent) ? recent : []).find((key) => READ.includes(key)) ?? READ[0];
}

/** The agent the Agents tab draws in SPACE: chosenAgent()'s where core reads it, else the one used last that core
 * reads (a graph is drawn of those alone). @param {{ kept?: any, space?: string | null, recent?: unknown }} how */
export function graphAgent({ kept = null, space = null, recent = null }) {
  const picked = chosenAgent({ kept, space, recent });
  return READ.includes(picked) ? picked : chosenAgent({ recent });
}

/** KEPT ({space: agent}) with AGENT picked for SPACE, the spaces no longer LIVE left out. @param {any} kept
 * @param {string} space @param {string} agent @param {Set<string>} live */
export function keepAgent(kept, space, agent, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([id]) => live.has(id))), [space]: agent };
}

/** Where an agent stands with no setup to show (core's standing()). @typedef {{ kind: string, title: string,
 * words: string, command: string | null, foot: string | null, actions: { id: string, label: string }[] }} Standing */
/** An agent as core tells it (agent_state.py agents); "empty" null: its setup shows. @typedef {{ key: string,
 * name: string, installed: boolean, signed_in: boolean | null, plan: string | null, login: string[], install: string,
 * page: string, empty: Standing | null }} Machine */
/** A row of the agents' list. @typedef {{ key: string, name: string, icon: string | null, tint: boolean,
 * plan: string | null, check: boolean, signIn: boolean }} Listed */

const PLAN = /^[A-Za-z][A-Za-z ]{0,23}$/;   // a plan's word: letters alone, so never an e-mail or an id

/** AGENTS' (core's) record of KEY, null while none is told. @param {unknown} agents @param {string} key
 * @returns {Machine | null} */
export const agentOf = (agents, key) => (Array.isArray(agents) ? agents : []).find((a) => a?.key === key) ?? null;

/** PROGRAM's (the app's knownAgents') icon for a list's row. @param {any} program */
const mark = (program) => ({ icon: typeof program?.icon === "string" ? program.icon : null,
  tint: Boolean(program?.tint) });

/** "Agents on this Mac": AGENTS (core's) installed, in its order, each with the app's icon (KNOWN, by key), its plan's
 * word, a check on the CURRENT one, sign in where core says it is not. @param {unknown} agents
 * @param {Record<string, any>} known @param {string} current @returns {Listed[]} */
export const agentList = (agents, known, current) => (Array.isArray(agents) ? agents : [])
  .filter((a) => typeof a?.key === "string" && a.installed === true)
  .map((a) => ({ key: a.key, name: String(a.name ?? a.key), ...mark(known?.[a.key]),
    plan: typeof a.plan === "string" && PLAN.test(a.plan) ? a.plan : null, check: a.key === current,
    signIn: a.signed_in === false }));

/** "Add an agent…": AGENTS (core's) not installed, in its order, each with the app's icon. @param {unknown} agents
 * @param {Record<string, any>} known */
export const addList = (agents, known) => (Array.isArray(agents) ? agents : [])
  .filter((a) => typeof a?.key === "string" && a.installed === false)
  .map((a) => ({ key: a.key, name: String(a.name ?? a.key), ...mark(known?.[a.key]) }));

/** tab.new's arguments for AGENT's own sign-in in a terminal tab of SPACE, in FOLDER: its login's words as one argv;
 * null where they are not words. @param {{ name: string, login: unknown }} agent
 * @param {{ space?: string, folder?: string | null }} where */
export function signInTab(agent, { space, folder = null }) {
  const argv = agent.login;
  if (!Array.isArray(argv) || !argv.length || !argv.every((word) => typeof word === "string" && word)) return null;
  return { name: `Sign in to ${agent.name}`, ...(space ? { space } : {}), ...(folder ? { folder } : {}), argv };
}

/** A window of an agent's limits, as core words it. @typedef {{ label: string, used: number, text: string,
 * level: string }} Meter */
/** An open block's bar and when its window resets. @typedef {{ bar: { used: number, level: string } | null,
 * resets: { at: number, words: string } | null }} First */
/** A row of Usage (usage.py's section()): an agent with its limits, the tighter window too. @typedef {First & {
 * key: string, name: string, plan: string | null, current: boolean, five: Meter | null, week: Meter | null,
 * tight?: Meter | null, age: string | null, said: string }} Usage */

/** Whether agent KEY's block in Usage is open: as TURNED here till core tells it, else as core keeps it (OPEN, its
 * section's), else the CURRENT agent's alone. @param {string} key @param {Record<string, boolean> | null | undefined}
 * open @param {Record<string, boolean>} turned @param {string | null} current */
export const usageOpen = (key, open, turned, current) => (key in turned ? turned[key]
  : open?.[key] ?? key === current);

/** Whether ROW has a line of words under it: when its window resets, or its reading's age. @param {Usage} row */
export const usageLine = (row) => Boolean(row.resets || row.age);

/** What Usage's ROWS take under its head, px: a row each, an open one (OPEN: by key) its line of words and its cost
 * LINES too; none: the line saying so. @param {Usage[]} rows @param {(key: string) => boolean} open
 * @param {Record<string, CostLine[]>} [lines] */
export const usageHeight = (rows, open, lines = {}) => (rows.length ? rows.reduce((px, row) => px + USAGE_ROW
  + (open(row.key) ? (usageLine(row) ? USAGE_LINE : 0) + costHeight(lines[row.key]) : 0), 0) : ROW_H);

export const COST_LINE = 20, COST_BAR = 8;       // px: a cost's figure line, as a property's; its budget bar's room
const WEEK = "This week";                        // the 7-day report's figure, usage.html's
/** A line under an agent's row in Usage. @typedef {{ kind: "figure", label: string, figure: string, unit: string,
 * over: boolean } | { kind: "bar", share: number, over: boolean } | { kind: "words", text: string, pace: string,
 * over: boolean }} CostLine */

/** Each agent's cost lines from core's 7-day REPORT (report.py), in its words: on an API key its month's spending,
 * its budget's bar and the pace (marked once over); else this week's figure in core's word for it (API value on a
 * plan). An agent with no price to tell has none. @param {any} report @returns {Record<string, CostLine[]>} */
export function costLines(report) {
  /** @type {Record<string, CostLine[]>} */
  const found = {};
  for (const cell of Array.isArray(report?.summary) ? report.summary : []) {
    const month = (report.months ?? []).find((/** @type {any} */ one) => one.agent === cell.agent);
    if (typeof cell.agent !== "string" || (!month && typeof cell.value !== "number")) continue;
    if (!month) {
      found[cell.agent] = [{ kind: "figure", label: WEEK, figure: String(cell.text), unit: String(cell.unit ?? ""),
        over: false }];
      continue;
    }
    const over = Boolean(month.over), words = month.words ?? {};
    found[cell.agent] = [{ kind: "figure", label: String(month.label), figure: String(words.spent), unit: "", over },
      ...(month.budget ? [/** @type {CostLine} */ ({ kind: "bar", share: Math.min(1, month.today / month.budget),
        over })] : []),
      { kind: "words", text: words.of ? `${words.of} · ` : "", pace: String(words.pace), over }];
  }
  return found;
}

/** A folded agent's figure from its cost. @typedef {{ figure: string, after: string, level: string | null,
 * used: number | null }} Glance */

/** Each agent's figure for its folded row from core's 7-day REPORT, in its words: on an API key its month's spent,
 * "of" its budget and its level (yellow once over), the share used; else what it cost, its word after it.
 * @param {any} report @returns {Record<string, Glance>} */
export function costGlance(report) {
  /** @type {Record<string, Glance>} */
  const found = {};
  for (const cell of Array.isArray(report?.summary) ? report.summary : []) {
    const month = (report.months ?? []).find((/** @type {any} */ one) => one.agent === cell.agent);
    if (typeof cell.agent !== "string" || (!month && typeof cell.value !== "number")) continue;
    found[cell.agent] = month ? { figure: String(month.words?.spent ?? ""), after: String(month.words?.of ?? ""),
      level: month.level ?? null, used: month.budget ? month.today / month.budget * 100 : null }
      : { figure: String(cell.text), after: String(cell.unit ?? ""), level: null, used: null };
  }
  return found;
}

/** ROW's one figure for Usage's head folded: a plan's tighter window, else its cost's (GLANCE); null for none.
 * @param {Usage} row @param {Glance | undefined} glance
 * @returns {{ label: string, figure: string, level: string | null, after: string } | null} */
export function tightest(row, glance) {
  if (row.tight) return { label: row.tight.label, figure: row.tight.text, level: row.tight.level, after: "" };
  return glance ? { label: "", figure: glance.figure, level: glance.level, after: glance.after } : null;
}

/** How near its end ROW stands, to compare: its tighter window's or its month's level, then the share used.
 * @param {Usage} row @param {Glance | undefined} glance @returns {[number, number]} */
const standing = (row, glance) => (row.tight ? [RANK[row.tight.level] ?? 0, row.tight.used]
  : [RANK[glance?.level ?? ""] ?? 0, glance?.used ?? 0]);

/** The row whose figure Usage's head shows folded: the CURRENT agent's, or another's that is yellow or red and stands
 * worse (GLANCES: costGlance()'s); null with neither. @param {Usage[]} rows @param {Record<string, Glance>} glances
 * @param {string | null} current */
export function headline(rows, glances, current) {
  const mine = rows.find((row) => row.key === current && tightest(row, glances[row.key])) ?? null;
  const worse = (/** @type {[number, number]} */ a, /** @type {[number, number]} */ b) => a[0] - b[0] || a[1] - b[1];
  let worst = null;
  for (const row of rows) {
    const at = standing(row, glances[row.key]);
    if (row !== mine && at[0] >= RANK.warn && (!worst || worse(at, standing(worst, glances[worst.key])) > 0)) {
      worst = row;
    }
  }
  return worst && (!mine || worse(standing(worst, glances[worst.key]), standing(mine, glances[mine.key])) > 0)
    ? worst : mine;
}

/** What an agent's cost LINES take under its row, px. @param {CostLine[] | undefined} lines */
export const costHeight = (lines) => (lines ?? []).reduce((px, line) => px + (line.kind === "figure" ? COST_LINE
  : line.kind === "bar" ? COST_BAR : USAGE_LINE), 0);

/** Usage's ROWS with a row for each agent that has cost LINES and no limits (an API key), named as AGENTS tell it:
 * after the meters', the CURRENT one first. @param {Usage[] | null | undefined} rows @param {unknown} agents
 * @param {Record<string, CostLine[]>} lines @param {string | null} [current] @returns {Usage[]} */
export function usageRows(rows, agents, lines, current = null) {
  const all = rows ?? [], told = Array.isArray(agents) ? agents : [];
  const made = READ.filter((key) => lines[key] && !all.some((row) => row.key === key)).map((key) => {
    const known = told.find((one) => one?.key === key);
    return { key, name: String(known?.name ?? NAMES[key] ?? key), plan: typeof known?.plan === "string" ? known.plan
      : null, current: key === current, five: null, week: null, tight: null, bar: null, resets: null, age: null,
    said: "" };
  });
  return [...made.filter((row) => row.current), ...all, ...made.filter((row) => !row.current)];
}

/** RESETS' words (core's, "5 hour resets at {time}") with this Mac's TIME and DAY in them; "" for none.
 * @param {{ words: string } | null | undefined} resets @param {string} time @param {string} day */
export const resetWords = (resets, time, day) => (resets?.words ?? "").replace("{time}", time).replace("{day}", day);

/** A percent's LEVEL as theme T's color, the status line's: ok green, warn yellow, bad red; any other muted.
 * @param {Record<string, string>} t @param {string} level */
export const levelColor = (t, level) => ({ ok: t.ansi2, warn: t.ansi3, bad: t.ansi1 })[level] ?? t.muted;

/** LEVEL's color as a percent's small words read it on GROUND: moved toward the text until it reads 4.5:1.
 * @param {Record<string, string>} t @param {string} level @param {string} ground */
export function levelInk(t, level, ground) {
  const color = levelColor(t, level);
  return [color, t.foreground, ground].every((hex) => HEX.test(hex ?? "")) ? readableOn(color, t.foreground, ground)
    : color;
}

const SEEN = 3;                    // a mark's contrast on what it stands on (WCAG's for what is not text)

/** LEVEL's color as the bar's fill on its track (the canvas, as the health bar's): moved toward the text by tenths
 * until it is seen 3:1 there. @param {Record<string, string>} t @param {string} level */
export function levelFill(t, level) {
  const color = levelColor(t, level);
  if (![color, t.foreground, t.canvas].every((hex) => HEX.test(hex ?? ""))) return color;
  for (let tenth = 0; tenth < 10; tenth += 1) {
    const made = mixColor(color, t.foreground, tenth / 10);
    if (contrast(made, t.canvas) >= SEEN) return made;
  }
  return t.foreground;
}

/** AGENTS (core's) as Usage's read tells them to core: each key, name and plan's word alone. @param {unknown} agents */
export const usageAgents = (agents) => (Array.isArray(agents) ? agents : [])
  .filter((a) => typeof a?.key === "string")
  .map((a) => ({ key: a.key, name: String(a.name ?? a.key), plan: typeof a.plan === "string" && PLAN.test(a.plan)
    ? a.plan : null }));
