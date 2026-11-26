// @ts-check
// The Agent panel's own rules, pure: which agent it shows, which of a section's rows, what a filter finds, each
// tone's color. The words, their order and the properties are core's (agent_layers.py's layers()), the TUI's too.
import { contrast, mixColor, readableOn } from "./agents.js";
import { money, whole } from "./report.js";

export const AGENT_CHOSEN = "herdr-fold.agent-chosen";   // shared: each space's agent, picked in the panel's head
export const AGENT_OPEN = "herdr-fold.agent-open";       // shared: {space: {section: open}}, a fold kept per space
export const AGENT_ASK = "herdr-fold.agent-ask";         // shared: {space, section, row, look, at}: openAgentPanel()'s
export const AGENT_PROBLEMS = "herdr-fold.agent-problems";   // shared: {space: {tone, said}}, the tab's and rail's dot
// the actions core offers that this client does
export const WORKS = ["open", "retry", "connect", "sign-out", "graph", "usage"];
export const CLAUDES = ["retry"];                       // Claude's own commands: never on another agent's row
const TURNS = ["turn-off", "turn-on"];                  // core's actions the connector's form stands for: its switch
export const WAITS = ["reopen", "cancel"];              // what a row signing in offers instead (core's connecting())
// a sign-in's terminal (no pane): its server's name, whose it is, when it started (ms), as its labels
export const MCP_LOGIN = "herdr-fold.mcp-login", MCP_AGENT = "herdr-fold.mcp-agent", MCP_AT = "herdr-fold.mcp-at";
export const SIGNING_MS = 600000;                       // ms a sign-in waits for its browser at most
export const ASK_MS = 10000;      // ms an ask waits for its panel (a view's copy starts once it first shows)
export const SERVER = "connector:";                     // a server's row id: this, then its name, as core's
const CONFLICT = "conflict:";                           // a conflict's row id starts so, as core's
const USAGE = "usage:";                                 // a Usage row's id: this, then its agent's key
export const MODEL = "model", RULE = "rule", HOOKS = "hooks";    // the forms no row has: the head's, +'s, Hooks' head's
const OWN = ["Global", "Project", "Local", "Managed"];  // core's layers: a subagent from one is no plugin's
const UNAPPROVED = "not approved";                      // core's state of a project's server nobody answered for yet
export const DEFAULT = "Default";                       // core's tag of what no file sets
export const READ = ["claude", "codex", "opencode"];    // the agents core reads a setup of (the panel's layers)
export const GRAPHED = ["claude", "codex"];             // those graph.py draws (agent_setup.py's READ)
const EDITED = ["claude", "codex"];                     // those whose harness core changes (harness.py)
export const NAMES = /** @type {Record<string, string>} */ ({ claude: "Claude", codex: "Codex",
  opencode: "OpenCode" });                              // as core's
export const FOLDED = ["subagents"];                    // folded till opened, as center-chat.html's Agent panel
export const FIRST = 5;           // rows a section shows before "N more": its problems and used ones always
export const TAG = 12;            // characters of a tag at most (a plugin's name may be long), as the TUI's cells
export const NARROW = 300;        // px: a panel under it drops its tags; the states and the costs stay
// px: a section's head, a row, a conflict's two lines, "N more", a group's head (Hooks); what a section's rows take
// sprung open (bodyHeight)
export const HEAD_H = 28, ROW_H = 26, WARN_H = 40, MORE_H = 24, GROUP_H = 22;
export const USAGE_LINE = 20;     // px: a line under a Usage row (a yellow or red window's reset, a pace too high)
const RANK = /** @type {Record<string, number>} */ ({ ok: 1, warn: 2, bad: 3 });   // how near its end a level is
export const LABEL = 64;          // px: the properties' labels' column ("Imported by"), connectors.html's .ikv.w
// under the home folder, what each agent's setup is read from: a change there is a new read
export const WATCHED = /** @type {Record<string, string>} */ ({ claude: ".claude", codex: ".codex",
  opencode: ".config/opencode" });
// in the space's folder, what a setup is read from: these folders, and files so named at any depth
const SETUP_DIRS = [".claude", ".codex", ".opencode"];
const SETUP_FILES = ["CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".mcp.json", "opencode.json", "opencode.jsonc"];
const TAG_CHAR = 6, TAG_PAD = 12;     // px: a tag's character at 11 at most, and its padding (parts.js's scopeTag)

/** A row's action, as core offers it: open PATH, or Claude's command on SERVER. @typedef {{ id: string, label: string,
 * path: string | null, server: string | null, primary: boolean }} Action */
/** A state or a summary's part in core's words and tone. @typedef {{ text: string, tone: string }} Said */
/** A row's properties: lines [label, value, third], a text, an error (its files the TIP); WORDS while signing in.
 * @typedef {{ title: string, state: Said | null, lines: [string, string, string | null][], text: string | null,
 * error: string | null, tip?: string | null, actions: Action[], words?: string }} Properties */
/** A row, MARK bad, warn or ok. @typedef {{ id: string, icon: string | null, name: string, note: string | null,
 * dim: boolean, tag: string | null, mark: string | null, state: Said | null, cost: string | null, agents: string[],
 * brand?: string | null, names?: string[], tokens?: number | null, properties?: Properties }} Row */
/** A group of a section's rows under their own head (Permissions' Hooks; STATE: off here). @typedef {{ id: string,
 * title: string, count: number, rows: Row[], state?: Said | null }} Group */
/** What a form asks of core (harness.py's plan): its action, then what its controls chose.
 * @typedef {{ action: string } & Record<string, any>} Ask */
/** A choice of a form's control (OFF: why it is grey), and a sandbox's host.
 * @typedef {{ id: string, label: string, off: string | null }} Choice */
/** @typedef {{ host: string, layer: string, rule: string | null }} Host */
/** A form's control as core words it: a choice, a text (a sandbox's hosts its ITEMS), a switch (TURN: both ways).
 * @typedef {{ id: string, label: string, kind: string, value: any, choices?: Choice[], hint?: string | null,
 * items?: Host[], turn?: { on: string, off: string } }} Field */
/** What a plan's save changes, by file, with its words and the edits a save passes on unread. @typedef {{
 * changes: { path: string, lines: [string, string][] }[], when: string | null, warns: string[], edits: any[],
 * done: string | null, undo: string, say: string[] }} Change */
/** A layer a form offers, its file as the form names it.
 * @typedef {{ id: string, label: string, path: string, chosen: boolean }} Layer */
/** harness.py's plan: the form and its buttons' words, and what saving it changes. @typedef {{ fields: Field[],
 * saved: string, layers: Layer[], ask: string | null, submit: string | null, cancel: string, remove: string | null,
 * error: string | null, more: { label: string, path: string } | null } & Change} Plan */
/** A section. @typedef {{ id: string, title: string, count: number | null, cost: string | null,
 * swatch: string | null, summary: { text: string, tone: string }[], rows: Row[], groups: Group[] }} Section */
/** A section as shown: its rows, how many wait under "N more", its groups each so. @typedef {{ rows: Row[],
 * more: number, groups: (Group & { more: number })[] }} Shown */

/** Whether ROW is a problem: failed, to sign in, a conflict. @param {Row} row */
export const problem = (row) => row.mark === "bad" || row.mark === "warn";

/** Whether ROW is a conflict, its sentence under its name. @param {Row} row */
export const conflicted = (row) => row.id.startsWith(CONFLICT);

/** Whether ROW holds every word of QUERY, case aside: in its name, note, state or tag. @param {Row} row
 * @param {string} query */
export function matches(row, query) {
  const said = [row.name, row.note, row.state?.text, row.tag].filter(Boolean).join("\n").toLowerCase();
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => said.includes(word));
}

/** ROWS shown and how many wait under "N more": the first FIRST, the marked ones and the CHOSEN one, all once OPEN;
 * never "1 more"; with a QUERY, every row it finds. @param {Row[]} rows @param {string} query @param {boolean} open
 * @param {string | null} chosen */
function some(rows, query, open, chosen) {
  if (query.trim()) return { rows: rows.filter((row) => matches(row, query)), more: 0 };
  if (open || rows.length <= FIRST) return { rows, more: 0 };
  const kept = rows.filter((row, n) => n < FIRST || row.mark || row.id === chosen);
  return rows.length - kept.length > 1 ? { rows: kept, more: rows.length - kept.length } : { rows, more: 0 };
}

/** SECTION as shown (some()'s, the ids in MORE opened past their "N more"), each group so under its rows; with a
 * QUERY a group it finds nothing in left out. @param {Section} section
 * @param {{ query?: string, more?: Set<string>, chosen?: string | null }} [how] @returns {Shown} */
export function shown(section, { query = "", more = new Set(), chosen = null } = {}) {
  const groups = (section.groups ?? []).map((group) => ({ ...group, ...some(group.rows, query, more.has(group.id),
    chosen) })).filter((group) => !query.trim() || group.rows.length);
  return { ...some(section.rows, query, more.has(section.id), chosen), groups };
}

/** What a section as SHOWN takes under its head, px: its rows (a conflict's two lines), "N more", each group's head,
 * rows and "N more"; none: the line saying so. @param {Shown} shown */
export function bodyHeight({ rows, more, groups }) {
  const high = (/** @type {Row[]} */ some, /** @type {number} */ left) => some.reduce((px, row) => px
    + (conflicted(row) ? WARN_H : ROW_H), 0) + (left ? MORE_H : 0);
  return (rows.length || groups.length ? high(rows, more) : ROW_H) + groups.reduce((px, group) => px + GROUP_H
    + high(group.rows, group.more), 0);
}

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

/** The tags' column of SECTION, px: as wide as the widest tag of its rows and its groups', shown or under "N more",
 * so its states stand in one column before it and nothing moves as "N more" opens; 0 with no tag.
 * @param {Section} section */
export function tagRoom(section) {
  const rows = [...section.rows, ...(section.groups ?? []).flatMap((group) => group.rows)];
  const widest = Math.max(0, ...rows.map((row) => (row.tag ? [...tagWord(row.tag)].length : 0)));
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

/** A state's or a problem's TONE as theme T's color: failed and deny red, sign in and ask yellow, allow and used
 * green, connecting the accent, off dim, any other muted. @param {Record<string, string>} t @param {string} tone */
export const toneColor = (t, tone) => ({ bad: t.ansi1, deny: t.ansi1, warn: t.ansi3, ask: t.ansi3, allow: t.ansi2,
  busy: t.accent, off: t.dim })[tone] ?? t.muted;

/** The color of a PART of what loads (the Agent panel's bar and swatches, the Context panel's bar): rules the accent,
 * skills teal, connectors blue, the rest muted, as connectors.html's and center-chat.html's.
 * @param {Record<string, string>} t @param {string} part */
export const partColor = (t, part) => ({ rules: t.accent, skills: t.ansi6, connectors: t.ansi4 })[part] ?? t.muted;

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
  const tones = new Set((layers?.head?.problems ?? []).map((/** @type {any} */ one) => one.tone));
  return tones.has("bad") ? "bad" : tones.has("warn") ? "warn" : null;
}

/** KEPT ({space: {tone, said}}) with SPACE's problems as core's LAYERS has them (none: left out), the spaces no longer
 * LIVE left out; KEPT itself where nothing changed. @param {any} kept @param {string} space @param {any} layers
 * @param {Set<string>} live */
export function keepProblems(kept, space, layers, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {}, tone = problemTone(layers);
  const next = Object.fromEntries(Object.entries(was).filter(([id]) => live.has(id) && id !== space));
  if (tone) next[space] = { tone, said: layers.head.problems.map((/** @type {any} */ one) => one.text).join(", ") };
  return JSON.stringify(next) === JSON.stringify(kept) ? kept : next;
}

/** The row ID among SECTIONS (their groups' too) with its section, or null. @param {Section[]} sections
 * @param {string | null} id @returns {{ section: Section, row: Row } | null} */
export function chosenRow(sections, id) {
  for (const section of id ? sections : []) {
    const row = [...section.rows, ...(section.groups ?? []).flatMap((group) => group.rows)].find((one) => one.id
      === id);
    if (row) return { section, row };
  }
  return null;
}

/** ROW's actions done here, in core's order: core's (WORKS), a sign-in's own (WAITS); Claude's own commands on
 * Claude's rows alone (AGENT: whose panel). @param {Row} row @param {string} [agent] @returns {Action[]} */
export const doable = (row, agent = "claude") => (row.properties?.actions ?? []).filter((one) =>
  [...WORKS, ...WAITS].includes(one.id) && (agent === "claude" || !CLAUDES.includes(one.id)));

/** What ROW's form (by its ID, as core makes it; MODEL, RULE and HOOKS have none) asks core for as it opens, or null;
 * NAME: the built-in subagent picked. Codex has its model, approval and sandbox alone, OpenCode none (EDITED). @param
 * {string} agent @param {string | null} id @param {Row | null} row @param {any} head @param {string | null} [name] */
export function formAsk(agent, id, row, head, name = null) {
  if (!EDITED.includes(agent)) return null;
  if (id === MODEL) return { action: "model", ...(head?.runs ? { runs: head.runs } : {}) };
  if (id === "sandbox" || id === (agent === "claude" ? "mode" : "approval")) return { action: id };
  if (agent !== "claude" || !id) return null;
  if (id === RULE || id === HOOKS) return { action: id };
  const [kind, second, ...more] = id.split(":"), rest = more.join(":");
  if (kind === "permission") return { action: "rule", was: { rule: rest, behavior: second, layer: row?.tag } };
  if (kind === "conflict") return { action: "conflict", behavior: second, rule: rest };
  if (kind === "skill" && row) return { action: "skill", name: row.name };
  if (kind === "subagent" && row?.names) return name && row.names.includes(name) ? { action: "subagent", name } : null;
  if (kind === "subagent" && row) return OWN.includes(second) ? { action: "subagent", name: row.name } : null;
  if (kind !== "connector" || !row || !(approves(row) || turnedOff(row) !== null)) return null;
  return { action: "connector", name: id.slice(SERVER.length), ...(typeof head?.starts === "number"
    ? { starts: head.starts } : {}), ...(typeof row.tokens === "number" ? { tokens: row.tokens } : {}) };
}

/** Whether core's ROW is turned off in this folder (it offers Turn on), or on (Turn off); null: neither is offered.
 * @param {Row | null} row */
const turnedOff = (row) => {
  const turn = (row?.properties?.actions ?? []).find((one) => TURNS.includes(one.id));
  return turn ? turn.id === "turn-on" : null;
};

/** Whether ROW is a project's server waiting for an answer: approved or kept off, asked both ways.
 * @param {Row | null} row */
export const approves = (row) => row?.state?.text === UNAPPROVED;

/** ASK with OVER chosen in a control: a value set, an emptied or taken-back one left out (it stays as the files have
 * it). @param {Ask} ask @param {Record<string, any>} over @returns {Ask} */
export const asking = (ask, over) => /** @type {Ask} */ (Object.fromEntries(Object.entries({ ...ask, ...over })
  .filter(([, value]) => value !== "" && value !== undefined)));

/** Whether a form offers its layers: once a control was TOUCHED (less till then); a rule's always, its layer being
 * one of its fields. @param {Ask} ask @param {boolean} touched */
export const layersShown = (ask, touched) => touched || ask.action === "rule";

/** What a switch FIELD shows: what was asked once TOUCHED; till then the files' word, and off where core's ROW says
 * so (Claude's own state turned its server off: no file tells). @param {Field} field @param {Row | null} row
 * @param {boolean} touched */
export const switchShown = (field, row, touched) => Boolean(field.value) && (touched || turnedOff(row) !== true);

/** Whether PLAN is Claude's own command alone (a server its own state turned off): told to its chat, no file changed.
 * @param {Plan} plan */
export const sayOnly = (plan) => plan.say.length > 0 && !plan.edits.length;

/** Whether a form's row is none of the layers': the head's, the +'s, Hooks' head's. @param {string | null} id */
export const rowless = (id) => id === MODEL || id === RULE || id === HOOKS;

/** Whether a sandbox's host (core's item) is taken out here: a file's own; one from an allow rule goes with its rule,
 * the organization's never. @param {Host} item */
export const removable = (item) => !item.rule && item.layer !== "Managed";

/** After PLAN (ASK's, of a form opened with BASE) was saved: the form to open anew and the row to choose (null: the
 * one chosen); a rule's own new row; null after a removal or a conflict solved: their row is gone. @param {Ask} base
 * @param {Ask} ask @param {Plan} plan @returns {{ chosen: string | null, ask: Ask } | null} */
export function afterSave(base, ask, plan) {
  if (ask.remove === true || ask.action === "conflict") return null;
  if (ask.action !== "rule") return { chosen: null, ask: base };
  const value = (/** @type {string} */ id) => plan.fields.find((field) => field.id === id)?.value;
  const was = { rule: value("rule"), behavior: value("behavior"), layer: plan.layers.find((one) => one.chosen)?.id };
  return { chosen: `permission:${was.behavior}:${was.rule}`, ask: { action: "rule", was } };
}

/** A change's line as it is drawn: its sign (a true minus), then core's text. @param {[string, string]} line */
export const changeLine = ([sign, text]) => `${sign === "-" ? "−" : sign} ${text}`;

/** The foot's words after PLAN was saved: core's own (a removal's), else the change's first line, as CODE.
 * @param {Plan} plan */
export function footWords(plan) {
  const first = plan.changes[0]?.lines[0];
  return plan.done ? { text: plan.done, code: false } : { text: first ? changeLine(first) : "", code: true };
}

/** Core's WORDS as a sentence, as the mockup ends its notes and warnings: a period where they end with no mark.
 * @param {string} words */
export const sentence = (words) => (/[.?!…]$/.test(words) ? words : `${words}.`);

/** A layer's file as a form names it (PATH: under ~, in FOLDER, or whole) by its whole path, to open.
 * @param {string} path @param {string} folder @param {string} home */
export const filePath = (path, folder, home) => (path.startsWith("~/") ? `${home}${path.slice(1)}`
  : path.startsWith("/") ? path : `${folder}/${path}`);

/** HEAD's line in two: its model and effort (the model form's way in; "" with neither known), then the rest.
 * @param {{ model?: string | null, effort?: string | null, line: string }} head @returns {[string, string]} */
export function headParts(head) {
  const first = [head.model, head.effort].filter(Boolean).join(" · ");
  return first && head.line.startsWith(first) ? [first, head.line.slice(first.length)] : ["", head.line];
}

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
  return { ...row, state: connect.state, mark: null, dim: false, properties: { title: row.properties?.title ?? row.name,
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
  return conflicted(row) ? lines : lines.filter(([, value]) => !titled.includes(value));
}

/** The server a connector's ROW stands for (what Claude checks again), or null. @param {Row} row */
export const serverOf = (row) => (row.id.startsWith(SERVER) ? row.id.slice(SERVER.length) : null);

/** ASK (openAgentPanel()'s: {space, section, row, look, at}) where this panel answers it: SPACE's, newer than the
 * LAST one answered, no older than ASK_MS at NOW; else null. @param {any} ask @param {string | null} space
 * @param {number | null} last @param {number} now */
export const asked = (ask, space, last, now) => (ask && typeof ask === "object" && ask.space === space
  && typeof ask.at === "number" && ask.at !== last && now - ask.at <= ASK_MS && now >= ask.at ? ask : null);

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

/** The agent the Agents tab draws in SPACE: chosenAgent()'s where graph.py draws it, else the one used last that it
 * draws (GRAPHED), else Claude. @param {{ kept?: any, space?: string | null, recent?: unknown }} how */
export function graphAgent({ kept = null, space = null, recent = null }) {
  const picked = chosenAgent({ kept, space, recent });
  return GRAPHED.includes(picked) ? picked
    : (Array.isArray(recent) ? recent : []).find((key) => GRAPHED.includes(key)) ?? GRAPHED[0];
}

/** KEPT ({space: agent}) with AGENT picked for SPACE, the spaces no longer LIVE left out. @param {any} kept
 * @param {string} space @param {string} agent @param {Set<string>} live */
export function keepAgent(kept, space, agent, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([id]) => live.has(id))), [space]: agent };
}

/** Where an agent stands with no setup to show (core's standing()). @typedef {{ kind: string, title: string,
 * words: string, command: string | null, foot: string | null, actions: { id: string, label: string }[] }} Standing */
/** An agent's row in the list, in core's words (agent_state.py's listed()). @typedef {{ group: string, dim: boolean,
 * word: string | null, tone: string | null }} Told */
/** An agent as core tells it (agent_state.py agents); "empty" null: its setup shows. @typedef {{ key: string,
 * name: string, installed: boolean, signed_in: boolean | null, plan: string | null, login: string[], install: string,
 * page: string, empty: Standing | null, listed: Told }} Machine */
/** A row of the agents' list. @typedef {{ key: string, name: string, icon: string | null, tint: boolean,
 * group: string, dim: boolean, word: string | null, warn: boolean, check: boolean }} Listed */

const PLAN = /^[A-Za-z][A-Za-z ]{0,23}$/;   // a word beside a name: letters alone, so never an e-mail or an id

/** AGENTS' (core's) record of KEY, null while none is told. @param {unknown} agents @param {string} key
 * @returns {Machine | null} */
export const agentOf = (agents, key) => (Array.isArray(agents) ? agents : []).find((a) => a?.key === key) ?? null;

/** PROGRAM's (the app's knownAgents') icon for a list's row. @param {any} program */
const mark = (program) => ({ icon: typeof program?.icon === "string" ? program.icon : null,
  tint: Boolean(program?.tint) });

/** The agents' list in core's words (each of AGENTS' "listed"): the installed in its order, its plan's word or sign
 * in (WARN) beside it, then the others dim, each under its GROUP; the app's icon (KNOWN, by key), a check on CURRENT.
 * @param {unknown} agents @param {Record<string, any>} known @param {string} current @returns {Listed[]} */
export function agentList(agents, known, current) {
  const rows = (Array.isArray(agents) ? agents : [])
    .filter((a) => typeof a?.key === "string" && typeof a.listed?.group === "string")
    .map((a) => ({ key: a.key, name: String(a.name ?? a.key), ...mark(known?.[a.key]), group: a.listed.group,
      dim: a.listed.dim === true, word: typeof a.listed.word === "string" && PLAN.test(a.listed.word)
        ? a.listed.word : null, warn: a.listed.tone === "warn", check: a.key === current }));
  return [...rows.filter((row) => !row.dim), ...rows.filter((row) => row.dim)];
}

/** tab.new's arguments for AGENT's own sign-in in a terminal tab of SPACE, in FOLDER: its login's words as one argv;
 * null where they are not words. @param {{ name: string, login: unknown }} agent
 * @param {{ space?: string, folder?: string | null }} where */
export function signInTab(agent, { space, folder = null }) {
  const argv = agent.login;
  if (!Array.isArray(argv) || !argv.length || !argv.every((word) => typeof word === "string" && word)) return null;
  return { name: `Sign in to ${agent.name}`, ...(space ? { space } : {}), ...(folder ? { folder } : {}), argv };
}

/** When a window resets: seconds since 1970, core's words. @typedef {{ at: number, words: string }} Resets */
/** A window of a plan's limits, as core words it: "–" with USED null (something ran since its reset, no reading
 * since). @typedef {{ label: string, used: number | null, text: string, level: string | null,
 * resets: Resets | null }} Meter */
/** An API-key agent's month (core's report's): spent OF its budget in its LEVEL, USED its share, PACE only while
 * past or heading past it. @typedef {{ figure: string, of: string, level: string | null, used: number | null,
 * pace: { text: string, narrow: string } | null, budget: number | null }} Month */
/** A Usage row with no reading: core's words in its place, and why. @typedef {{ text: string, why: string }} Untold */
/** A row of Usage: a plan's (section(): windows, the tighter, RESET while yellow or red, age) or an API key's (MONTH).
 * @typedef {{ key: string, name: string, plan: string | null, current: boolean, five: Meter | null, week: Meter |
 * null, tight: Meter | null, reset: Resets | null, age: string | null, month: Month | null, untold?: Untold }} Usage */

/** Usage's rows: SECTION's (core's), then each agent on an API key with a month in REPORT (core's report, in the
 * place of a row with no reading), named as AGENTS tell it; the CURRENT agent's first. @param {any} section
 * @param {any} report @param {unknown} agents @param {string | null} current @returns {Usage[]} */
export function usageRows(section, report, agents, current) {
  const plans = Array.isArray(section?.rows) ? section.rows : [], told = Array.isArray(agents) ? agents : [];
  const months = (Array.isArray(report?.months) ? report.months : []).filter((/** @type {any} */ one) =>
    !plans.some((/** @type {any} */ row) => row.key === one.agent && !row.untold))
    .map((/** @type {any} */ one) => {
    const known = told.find((agent) => agent?.key === one.agent);
    return { key: String(one.agent), name: String(known?.name ?? one.name), plan: known?.plan ?? null,
      current: one.agent === current, five: null, week: null, tight: null, reset: null, age: null,
      month: { figure: String(one.words?.spent ?? ""), of: String(one.words?.of ?? ""), level: one.level ?? null,
        used: one.budget ? one.today / one.budget * 100 : null, pace: one.pace_line ?? null,
        budget: one.budget ?? null } };
  });
  const rows = [...plans.filter((/** @type {any} */ row) => !months.some((/** @type {any} */ one) =>
    one.key === row.key)).map((/** @type {any} */ row) => ({ ...row, month: null })), ...months];
  return [...rows.filter((row) => row.current), ...rows.filter((row) => !row.current)];
}

/** Whether ROW has a line under it: a yellow or red window's reset, or its month's pace past its budget.
 * @param {Usage} row */
export const usageLine = (row) => Boolean(row.reset || row.month?.pace);

/** What Usage's ROWS take under its head, px: a row each, a line under one that has it; none: the line saying so.
 * @param {Usage[]} rows */
export const usageHeight = (rows) => (rows.length ? rows.reduce((px, row) => px + ROW_H
  + (usageLine(row) ? USAGE_LINE : 0), 0) : ROW_H);

/** ROW's one figure, for Usage's head folded: a plan's tighter window, else its month of its budget; null for none.
 * @param {Usage} row @returns {{ label: string, figure: string, level: string | null, after: string } | null} */
export function usageFigure(row) {
  if (row.tight) return { label: row.tight.label, figure: row.tight.text, level: row.tight.level, after: "" };
  return row.month ? { label: "", figure: row.month.figure, level: row.month.level, after: row.month.of } : null;
}

/** How near its end ROW stands, to compare: its tighter window's or its month's level, then the share used.
 * @param {Usage} row @returns {[number, number]} */
const standing = (row) => (row.tight ? [RANK[row.tight.level ?? ""] ?? 0, row.tight.used ?? 0]
  : [RANK[row.month?.level ?? ""] ?? 0, row.month?.used ?? 0]);

/** The row whose figure Usage's head shows folded: the current agent's, or another's that is yellow or red and stands
 * worse; null with neither. @param {Usage[]} rows */
export function headline(rows) {
  const mine = rows.find((row) => row.current && usageFigure(row)) ?? null;
  const worse = (/** @type {Usage} */ a, /** @type {Usage} */ b) => standing(a)[0] - standing(b)[0]
    || standing(a)[1] - standing(b)[1];
  let worst = null;
  for (const row of rows) {
    if (row !== mine && standing(row)[0] >= RANK.warn && (!worst || worse(row, worst) > 0)) worst = row;
  }
  return worst && (!mine || worse(worst, mine) > 0) ? worst : mine;
}

/** ROW chosen (id usage:KEY): the plan, each reset in SAID's words, the age, an API key's budget, why its limits are
 * not told; Open Usage. A line's label is the words' first ("5h resets 14:46": 5h, resets 14:46). @param {Usage} row
 * @param {(resets: { at: number, words: string }) => string} said @returns {Row} */
export function usageRow(row, said) {
  const parted = (/** @type {string} */ words) => {
    const [label, ...rest] = words.split(" ");
    return /** @type {[string, string, null]} */ ([label, rest.join(" "), null]);
  };
  const budget = row.month?.budget, resets = [row.five?.resets, row.week?.resets].filter((one) => one != null);
  const lines = [...(row.plan ? [/** @type {[string, string, null]} */ (["Plan", row.plan, null])] : []),
    ...resets.map((one) => parted(said(/** @type {{ at: number, words: string }} */ (one)))),
    ...(row.month ? [/** @type {[string, string, null]} */ (["Budget", !budget ? "none" : Number.isInteger(budget)
      ? whole(budget) : money(budget), null])] : []),
    ...(row.age ? [parted(row.age)] : [])];
  return { id: `${USAGE}${row.key}`, icon: null, name: row.name, note: null, dim: false, tag: null, mark: null,
    state: null, cost: null, agents: [row.key], properties: { title: row.name, state: null, lines,
      text: row.untold?.why ?? null,
      error: null, tip: null, actions: [{ id: "usage", label: "Open Usage", path: null, server: null,
        primary: true }] } };
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
