// @ts-check
// The chat's timeline without the window: core/chat.py's steps as the rows it draws (a call and its result in one) and
// each row's time in this Mac's zone and hour style, as the system shows a time.

/** A row: a step, a call with its outcome (ok null while it runs), a thought with its label.
 * @typedef {{ kind: string, at?: string | null, ok?: boolean | null, open?: boolean, label?: string,
 *   [key: string]: any }} Moment */

const OPEN = new Set(["Edit", "MultiEdit", "Write"]);      // a change's call: its diff open from the start
const CALLS = new Set(["tool", "skill", "agent", "todo"]); // the steps a result answers, by the call's id
const DAY = 86400000;
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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

/** Whether this system writes hours as 12, with AM and PM: the runtime's own form of a time is its one clue (the
 * Herdr app's leaves toLocaleTimeString's options aside). */
const twelve = () => /[AP]M/i.test(new Date(2000, 0, 1, 13).toLocaleTimeString());

/** WHEN's hours and minutes, in the system's 12 or 24 hours. @param {Date} when */
export function hours(when) {
  const hour = when.getHours(), minutes = String(when.getMinutes()).padStart(2, "0");
  return twelve() ? `${hour % 12 || 12}:${minutes} ${hour < 12 ? "AM" : "PM"}`
    : `${String(hour).padStart(2, "0")}:${minutes}`;
}

/** ISO's time as a row shows it: the time alone today, "Yesterday" and the time, else the date (the year when not
 * this one) and the time; "" for no time. @param {string | null | undefined} iso @param {Date} [now] */
export function clock(iso, now = new Date()) {
  const when = new Date(iso ?? "");
  if (!iso || Number.isNaN(when.getTime())) return "";
  const midnight = (/** @type {Date} */ d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(now) - midnight(when)) / DAY);      // a day of 23 or 25 hours still one
  if (days === 0) return hours(when);
  if (days === 1) return `Yesterday ${hours(when)}`;
  const year = when.getFullYear() === now.getFullYear() ? "" : `, ${when.getFullYear()}`;
  return `${MONTHS[when.getMonth()]} ${when.getDate()}${year}, ${hours(when)}`;
}
