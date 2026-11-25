// @ts-check
// The Agents tab's Usage, pure: core's report (report.py) as its charts and tables draw it. The figures and the
// words are core's; here are the marks' places (usage.html's Riport) and the index's looks before a report.

export const PERIOD = "7d";        // the period the view opens on, usage.html's
export const GAP = 2;              // px of the surface between two segments of a column
export const STEPS = 4;            // steps an axis has at most
const DAY_STEPS = [1, 2, 5, 10, 15];        // days between two of a month's named days: the smallest that fits
export const LOOKS = 200;          // looks at the index a read makes at most (core reads 256 MB a look)
const API_KEY = "API key";         // the agents' list's word for an agent on an API key, as core's
const ABOUT = "~";                 // before a dollar figure herdr-fold computes, an estimate (core's prices.ABOUT)

/** @typedef {{ name: string, color: string, cost: number }} Part a model's share of a day */
/** @typedef {{ label: string, total: number, models: Part[] }} Day */

/** DIGITS (a whole number's) with a comma before every three from the end: the app's engine knows no locale.
 * @param {string} digits */
const grouped = (digits) => digits.replace(/\B(?=(\d{3})+$)/g, ",");

/** DOLLARS as core writes them: $130.90, $1,234.50; ABOUT, one herdr-fold computed: ~$130.90.
 * @param {number} dollars @param {boolean} [about] */
export function money(dollars, about = false) {
  const [units, cents] = dollars.toFixed(2).split(".");
  return `${about ? ABOUT : ""}$${grouped(units)}.${cents}`;
}

/** DOLLARS to the nearest one, as a pace and a round budget are said: $46; ABOUT (a pace): ~$46.
 * @param {number} dollars @param {boolean} [about] */
export const whole = (dollars, about = false) => `${about ? ABOUT : ""}$${grouped(String(Math.floor(dollars + 0.5)))}`;

/** VALUE to PLACES decimals as Python formats it: an exact half to even (toFixed takes it up). It is an exact half
 * only where VALUE times 2^(PLACES+1) is an odd whole number. @param {number} value @param {number} places */
function fixed(value, places) {
  const halves = value * 2 ** (places + 1);
  if (!Number.isInteger(halves) || halves % 2 === 0) return value.toFixed(places);
  const low = Math.floor(value * 10 ** places);
  return ((low % 2 === 0 ? low : low + 1) / 10 ** places).toFixed(places);
}

/** COUNT tokens by the number rule, core's words.tokens: 850, 5.9k, 21.4k, 120k, 1.2M, 2.1B. @param {number} count */
export function tokens(count) {
  if (count < 1000) return String(count);
  if (count < 99_950) return `${fixed(count / 1e3, 1)}k`;
  if (count < 999_500) return `${fixed(count / 1e3, 0)}k`;
  return count < 999_950_000 ? `${fixed(count / 1e6, 1)}M` : `${fixed(count / 1e9, 1)}B`;
}

/** An axis's ticks from 0 up to MAX or past it: the smallest clean step (1, 2 or 5 times a power of ten) that takes
 * STEPS steps at most. @param {number} max @returns {number[]} */
export function ticks(max) {
  if (!(max > 0)) return [0, 1];
  for (let power = Math.floor(Math.log10(max)) - 1; ; power += 1) {
    for (const lead of [1, 2, 5]) {
      const step = lead * 10 ** power, count = Math.ceil(Number((max / step).toPrecision(12)));
      if (count <= STEPS) {
        return Array.from({ length: count + 1 }, (_, n) => Number((n * step).toPrecision(12)));
      }
    }
  }
}

/** A tick's VALUE as the axis writes it: whole dollars, cents on an axis under a dollar a step.
 * @param {number} value @param {number[]} all */
const tickLabel = (value, all) => ((all[1] ?? 1) < 1 ? money(value) : whole(value));

/** DAILY (core's days) as columns on a plot HEIGHT px high whose axis ends at TOP dollars: each day's models from
 * the baseline up, a segment its cost's height less the GAP over it, 1 px at least, the last one the rounded one.
 * @param {Day[]} daily @param {number} height @param {number} top */
export const columns = (daily, height, top) => daily.map((day) => ({ label: day.label, total: day.total,
  segments: day.models.filter((one) => one.cost > 0).map((one, n, all) => ({ color: one.color,
    h: top > 0 ? Math.max(1, Math.round(one.cost / top * height - GAP)) : 1, top: n === all.length - 1 })) }));

/** The names under DAILY's columns, as the TUI's day_labels: the last day, the first and each month's 1st always; a
 * month's days between them at the smallest of DAY_STEPS that leaves MOST names at most, each clear of the next, the
 * one named first giving way last. @param {{ label: string }[]} daily @param {number} most @returns {string[]} */
export function axisLabels(daily, most) {
  const days = daily.map((day) => Number(day.label.split(" ").pop())), last = days.length - 1;
  const clear = Math.max(1, Math.ceil(days.length / Math.max(1, most)));
  const step = DAY_STEPS.find((one) => one >= clear);
  const rank = (/** @type {number} */ n) => (n === last ? 0 : n === 0 ? 1 : days[n] === 1 ? 2 : 3);
  const stepped = (/** @type {number} */ n) => step !== undefined && days[n] % step === (step === 2 ? 1 : 0);
  /** @type {number[]} */
  const named = [];
  for (const n of days.map((_, at) => at).sort((a, b) => rank(a) - rank(b) || a - b)) {
    if ((rank(n) < 3 || stepped(n)) && named.every((other) => Math.abs(other - n) >= clear)) named.push(n);
  }
  return daily.map((day, n) => (named.includes(n) ? day.label : ""));
}

/** DAY's tip (usage.html's .tip): its date and sum (an estimate), then each model with its color and cost, a
 * table's cells. @param {Day} day */
export const tipFor = (day) => ({ title: `${day.label} · ${money(day.total, true)}`,
  rows: day.models.map((one) => ({ name: one.name, color: one.color, text: money(one.cost) })) });

/** MONTH (core's: an API-key agent's month against its budget) as its plot draws it, each place a share of the plot
 * (x from its left, y from its top): its ticks, what was spent by each day's end, today's point, the pace on to the
 * month's end and the budget's line; null with no month. @param {any} month */
export function monthLine(month) {
  if (!month) return null;
  const marks = ticks(Math.max(month.budget ?? 0, month.pace, month.today)), top = marks[marks.length - 1];
  const x = (/** @type {number} */ d) => d / month.days, y = (/** @type {number} */ v) => 1 - v / top;
  const now = /** @type {[number, number]} */ ([x(month.day), y(month.today)]);
  return { ticks: marks.map((value) => ({ y: y(value), label: tickLabel(value, marks) })),
    spent: [[0, 1], ...month.spent.map((/** @type {[number, number]} */ [d, v]) => [x(d), y(v)])],
    today: { x: now[0], y: now[1], label: `${money(month.today, true)} today` },
    pace: month.day < month.days ? { from: now, to: [1, y(month.pace)],
      label: `on pace for ${whole(month.pace, true)}` } : null,
    budget: month.budget ? { y: y(month.budget), label: `Budget ${whole(month.budget)}` } : null,
    first: `${String(month.end).split(" ")[0]} 1`, last: String(month.end) };
}

/** PROJECTS (core's, the most first) as bars: each one's share of the largest and the value at its tip; one with no
 * price its tokens alone. @param {{ name: string, cost: number | null, tokens: number }[]} projects */
export function projectBars(projects) {
  const most = Math.max(0, ...projects.map((one) => one.cost ?? 0));
  return projects.map((one) => ({ name: one.name, share: most > 0 && one.cost ? one.cost / most : 0,
    text: one.cost === null ? `${tokens(one.tokens)} tokens` : money(one.cost) }));
}

/** The SUMMARY row's cells (core's): the first the wide one (usage.html's 1.4fr); a unit only beside a figure.
 * @param {any[]} summary */
export const summaryCells = (summary) => summary.map((cell, n) => ({ key: String(cell.key), text: String(cell.text),
  grow: n ? 1 : 1.4, unit: cell.value === null ? "" : String(cell.unit ?? ""), line: String(cell.line ?? "") }));

/** A chat's ROW (core's) as the table's cells; WORDS core's. @param {any} row @param {{ no_price: string }} words */
export const chatCells = (row, words) => ({ title: String(row.title), space: String(row.space),
  models: (row.models ?? []).map((/** @type {{ color: string }} */ one) => one.color), turns: String(row.turns),
  tokens: tokens(row.tokens), cache: row.cache === null ? "–" : `${row.cache}%`,
  cost: row.cost === null ? words.no_price : money(row.cost), kind: row.cost === null ? "" : String(row.kind) });

/** A model's ROW (core's) as the table's cells: each kind of token short, – for none. @param {any} row */
export function modelCells(row) {
  const count = (/** @type {number} */ n) => (n ? tokens(n) : "–");
  return { name: String(row.name), color: String(row.color), agent: String(row.agent), input: count(row.input),
    write: count(row.write), read: count(row.read), output: count(row.output), cost: String(row.text),
    kind: row.cost === null ? "" : String(row.kind), priced: row.cost !== null };
}

/** report.py's arguments for COMMAND (report, csv): the period, the agent and the folder ("" for every one), the
 * agents' plans and, for a report, the THEME's card and text. @param {string} command @param {{ period: string,
 * agent: string | null, folder: string | null, agents: unknown, theme: Record<string, string> | null }} asked */
export const reportArgs = (command, { period, agent, folder, agents, theme }) => [command, period, agent ?? "",
  folder ?? "", `--agents=${JSON.stringify(Array.isArray(agents) ? agents : [])}`,
  ...(theme ? [`--surface=${theme.surface}`, `--text=${theme.foreground}`] : [])];

/** The budget's fields: one for each of AGENTS (core's list) on an API key, with what BUDGETS (core's) keeps for
 * it as it is typed. @param {unknown} agents @param {Record<string, number>} budgets */
export const budgetRows = (agents, budgets) => (Array.isArray(agents) ? agents : [])
  .filter((one) => one?.plan === API_KEY && typeof one.key === "string")
  .map((one) => ({ key: String(one.key), name: String(one.name ?? one.key),
    value: !budgets?.[one.key] ? "" : Number.isInteger(budgets[one.key]) ? String(budgets[one.key])
      : budgets[one.key].toFixed(2) }));

/** Where SESSION's row is among CHATS (core's); -1 for none. @param {any[] | null | undefined} chats
 * @param {string | null | undefined} session */
export const markedRow = (chats, session) => (session ? (chats ?? [])
  .findIndex((one) => one?.session === session) : -1);

/** An index brought up to date: LOOK (one call of core's index) again until nothing is left, a look read nothing,
 * or MOST looks; EACH hears what is left after every look. @param {() => Promise<{ read: number, left: number }>} look
 * @param {number} [most] @param {(left: number) => void} [each] */
export async function indexed(look, most = LOOKS, each = () => {}) {
  let looks = 0, read = 0, left = 0;
  do {
    const answer = await look();
    looks += 1;
    read += answer.read;
    left = answer.left;
    each(left);
    if (answer.read <= 0) break;
  } while (left > 0 && looks < most);
  return { looks, left, read };
}

/** Whether TEXT, as typed into a budget's field, is an amount core takes (50, $50, 1,250.50) or nothing (the budget
 * taken away). @param {string} text */
export const amountTyped = (text) => /^(\$?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?)?$/.test(text.trim());
