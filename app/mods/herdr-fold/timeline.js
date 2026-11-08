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
