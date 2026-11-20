// @ts-check
// The chat's timeline without the window: core/chat.py's steps as the rows it draws (a call and its result in one) and
// each row's time in this Mac's zone, written as its Language & Region settings write a time.

/** A row: a step, a call with its outcome (ok null while it runs), a thought with its label.
 * @typedef {{ kind: string, at?: string | null, ok?: boolean | null, open?: boolean, label?: string,
 *   [key: string]: any }} Moment */

const OPEN = new Set(["Edit", "MultiEdit", "Write"]);      // a change's call: its diff open from the start
const CALLS = new Set(["tool", "skill", "agent", "todo"]); // the steps a result answers, by the call's id
const DAY = 86400000;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
// how a time is written until the system says (setForms): the international 24 hours
const INTERNATIONAL = { time: "HH:mm", day: "d MMM, HH:mm", year: "d MMM y, HH:mm", weekday: "EEE d MMM, HH:mm" };
let forms = INTERNATIONAL;

// the chat view's spacing, px: one scale every part of it keeps to (tests/timeline.test.js holds each part to it),
// the timeline's from center-chat.html: a call's line 24 high with an 8 px dot on its middle, steps 16 apart
export const RHYTHM = {
  line: 24,      // a step's first line: a call's head, a thought, a status line (13 px words)
  text: 20,      // a line of Claude's words (13 px markdown), a todo's, its time at the first one's end
  dot: 8,
  step: 16,      // the step gap: step to step, the person's message to the next step, the last step to a card
  stepPad: 8,    // a step's own padding over and under it: half the step gap
  pad: 4,        // a label over its box; a bar's tight gaps
  gap: 8,        // a box's inside, up and down; a bar's sides
  inner: 8,      // inside a step: its head to what it opens; a notice's inside, up and down
  inset: 12,     // a box's sides inside: the person's message, the prompt, a notice, a pill; a card's body over it
  card: 16,      // a card's sides inside, as the mockup's
  turn: 24,      // over the person's message and the prompt, from the last step's line: a new turn
  foot: 20,      // under the prompt or the card, to the window's foot, as the mockup's
  edge: 24,      // the column's sides; the empty chat's inside
};
export const CARD_HEAD = 44;   // px: a card's head, the mockup's (.rtop), its fold button in it

/** How a step of KIND stands on the line: its padding, its first line's height (Claude's words their own line, calls
 * and statuses theirs), the dot and its top, on the middle of that line. @param {string} kind */
export function stepLayout(kind) {
  const line = kind === "text" ? RHYTHM.text : RHYTHM.line;
  return { pad: RHYTHM.stepPad, line, dot: RHYTHM.dot, dotTop: RHYTHM.stepPad + (line - RHYTHM.dot) / 2 };
}

/** The prompt's place under the timeline (CARD: Claude waits on a card there): the rows' room under the last step,
 * the place's own top, and the line's stub there: a card a step gap under the last step, the line reaching its edge;
 * the prompt a turn under it, where the next turn starts, off the line. @param {boolean} card */
export const bottomLayout = (card) => (card ? { rows: 0, top: RHYTHM.step - RHYTHM.stepPad,
  line: RHYTHM.step - RHYTHM.stepPad } : { rows: RHYTHM.stepPad, top: RHYTHM.turn - 2 * RHYTHM.stepPad, line: 0 });

/** The person's message's row: a turn over it from the last step's line, its time a pad over its box, a step gap under
 * it to the next step's line (that step's own pad in it). */
export const userLayout = () => ({ top: RHYTHM.turn - RHYTHM.stepPad, label: RHYTHM.pad,
  bottom: RHYTHM.step - RHYTHM.stepPad, inset: RHYTHM.inset, boxY: RHYTHM.gap });

const HEADING = /^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$/;     // an ATX heading: its words, closing #s dropped
const UNDERLINE = /^ {0,3}(?:=+|-+)[ \t]*$/;                         // a setext heading's underline
const FENCE = /^ {0,3}(```|~~~)/;
const BLOCK = /^\s*(?:[-*+>|]|\d+[.)])(?:\s|$)/;                    // a list item, a quote, a table: never a heading

/** TEXT (Claude's markdown) as the timeline draws it: a heading's words bold on a line of its own, so it keeps the
 * step's line and margins (TextView's headings are larger, with margins of their own); code fences left alone.
 * @param {string} text */
export function timelineMarkdown(text) {
  const out = [];
  let fence = null;
  for (const line of text.split("\n")) {
    const opens = FENCE.exec(line);
    if (fence) {
      if (opens && opens[1] === fence) fence = null;
      out.push(line);
    } else if (opens) {
      fence = opens[1];
      out.push(line);
    } else if (HEADING.test(line) && HEADING.exec(line)?.[1]) {
      out.push(`**${HEADING.exec(line)?.[1]}**`);
    } else if (UNDERLINE.test(line) && out.length && out[out.length - 1].trim() && !BLOCK.test(out[out.length - 1])) {
      out.push(`**${out.pop()?.trim()}**`);
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

/** How long a thought took, as the extension says it. @param {number | null | undefined} ms */
function thought(ms) {
  if (typeof ms !== "number") return "Thought";
  const seconds = Math.max(1, Math.round(ms / 1000));
  return seconds < 60 ? `Thought for ${seconds}s` : `Thought for ${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

/** STEPS (core/chat.py's, in order) as the timeline's rows: a call with its result, a result with no call left out.
 * @param {any[]} steps @returns {Moment[]} */
export function timeline(steps) {
  /** @type {Moment[]} */
  const rows = [];
  /** @type {Map<string, Moment>} */
  const calls = new Map();
  for (const step of steps) {
    if (step.kind === "result") {
      const call = calls.get(step.id);
      if (call) Object.assign(call, { ok: step.ok, output: step.output, change: step.change });
      continue;
    }
    /** @type {Moment} */
    const row = step.kind === "thought" ? { kind: "thought", label: thought(step.ms), at: step.at }
      : CALLS.has(step.kind) ? { ...step, ok: null, output: "", change: null, open: OPEN.has(step.name) } : { ...step };
    if (CALLS.has(step.kind) && step.id) calls.set(step.id, row);
    rows.push(row);
  }
  return rows;
}

const MCP = "mcp__";                 // what a server's tool's name starts with, then the server's key, "__", the tool
const WORDS = 80;                    // characters of a connector's call's first words

/** A server's NAME as its tools carry it (core's tool_key): every character but a letter, digit, _ or - as _.
 * @param {string} name */
const toolKey = (name) => name.replace(/[^A-Za-z0-9_-]/g, "_");

/** The connector a call of the tool NAME is of, among SERVERS (agent_setup.py's setup, the longest key first): its
 * server, label and brand, the tool's own name; one the setup does not name by its key (a letter tile's); null for
 * any other tool. @param {string} name @param {unknown} servers */
export function connectorRow(name, servers) {
  if (typeof name !== "string" || !name.startsWith(MCP)) return null;
  const rest = name.slice(MCP.length), known = (Array.isArray(servers) ? servers : [])
    .filter((one) => typeof one?.name === "string").map((one) => ({ one, key: toolKey(one.name) }))
    .filter(({ key }) => rest.startsWith(`${key}__`) && rest.length > key.length + 2)
    .sort((a, b) => b.key.length - a.key.length)[0];
  if (known) {
    return { server: known.one.name, label: String(known.one.label ?? known.one.name), brand: known.one.brand ?? null,
      tool: rest.slice(known.key.length + 2) };
  }
  const cut = rest.indexOf("__");
  return cut > 0 && cut + 2 < rest.length ? { server: null, label: rest.slice(0, cut), brand: null,
    tool: rest.slice(cut + 2) } : null;
}

/** What a connector's call says after its tool: its INPUT's first text (core keeps the texts), its first line, WORDS
 * characters at most, a control code shown as ?; "" for none. @param {unknown} input */
export function callWords(input) {
  const first = Object.values(input && typeof input === "object" ? input : {})
    .find((value) => typeof value === "string" && value.trim());
  const line = String(first ?? "").trim().split("\n")[0].trim().replace(/\p{Cc}/gu, "?");
  return [...line].length > WORDS ? `${[...line].slice(0, WORDS - 1).join("")}…` : line;
}

/** How a sign-in's step is told: the sign-ins running and why one could not start, by server; NEWER: asked after the
 * setup was last read. @typedef {{ signing?: Record<string, any>, failed?: Record<string, string>,
 * newer?: boolean }} SigningIn */
/** A sign-in's step for SERVER (Claude's name for it) as it stands among SERVERS (the setup's): "busy" while its agent
 * signs in, "ask" while it is to sign in (or NEWER), "done" once it is on, else "past"; why it could not start.
 * @param {string} server @param {unknown} servers @param {SigningIn} [how] */
export function signinRow(server, servers, { signing = {}, failed = {}, newer = false } = {}) {
  const one = (Array.isArray(servers) ? servers : []).find((s) => s?.name === server);
  const state = signing[server] ? "busy" : newer || one?.state === "sign in" ? "ask" : one?.state === "on" ? "done"
    : "past";
  const words = { busy: "signing in…", ask: "needs you to sign in", done: "signed in", past: "needed a sign-in" };
  return { server, label: String(one?.label ?? server), brand: one?.brand ?? null, state, words: words[state],
    error: state === "ask" ? failed[server] ?? null : null };
}

/** FORMS as every time is written: macOS's patterns for this Mac's user (time, day, year, weekday: chat.js asks for
 * them); null: not known. @param {{ time: string, day: string, year: string, weekday: string } | null} next */
export function setForms(next) {
  forms = next ? { ...INTERNATIONAL, ...next } : INTERNATIONAL;
}

/** WHEN as PATTERN says (a Unicode date pattern: each letter run a part, a quoted word as it is), in English.
 * @param {Date} when @param {string} pattern */
export function format(when, pattern) {
  const hour = when.getHours(), month = when.getMonth();
  return pattern.replace(/'([^']*)'|([A-Za-z])\2*/g, (run, quoted, letter) => {
    if (quoted !== undefined) return quoted || "'";
    const pad = (/** @type {number} */ value) => String(value).padStart(Math.min(run.length, 2), "0");
    switch (letter) {
      case "E": case "c": return run.length >= 4 ? WEEKDAYS[when.getDay()] : WEEKDAYS[when.getDay()].slice(0, 3);
      case "M": case "L": return run.length >= 4 ? MONTHS[month] : run.length === 3 ? MONTHS[month].slice(0, 3)
        : pad(month + 1);
      case "d": return pad(when.getDate());
      case "y": return run.length === 2 ? String(when.getFullYear()).slice(-2) : String(when.getFullYear());
      case "H": return pad(hour);
      case "k": return pad(hour || 24);
      case "h": return pad(hour % 12 || 12);
      case "K": return pad(hour % 12);
      case "m": return pad(when.getMinutes());
      case "a": case "b": case "B": return hour < 12 ? "AM" : "PM";
      default: return "";
    }
  });
}

/** WHEN in the system's FORM of a time (time, day, year or weekday). @param {Date} when
 * @param {"time" | "day" | "year" | "weekday"} form */
export const written = (when, form) => format(when, forms[form]);

/** ISO's time as a row shows it: the time alone today, "Yesterday" and the time, else the date (the year when not
 * this one) and the time; "" for no time. @param {string | null | undefined} iso @param {Date} [now] */
export function clock(iso, now = new Date()) {
  const when = new Date(iso ?? "");
  if (!iso || Number.isNaN(when.getTime())) return "";
  const midnight = (/** @type {Date} */ d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(when)) / DAY);      // a day of 23 or 25 hours still one
  if (days === 0) return written(when, "time");
  if (days === 1) return `Yesterday ${written(when, "time")}`;
  return written(when, when.getFullYear() === now.getFullYear() ? "day" : "year");
}
