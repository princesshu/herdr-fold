// @ts-check
// Tests for the Agents tab's Usage (report.js): money and tokens as core writes them, the charts' ticks, columns,
// tip and month line, the projects' bars, the summary's and the tables' cells, the budget's fields, the index's looks.
import test from "node:test";
import assert from "node:assert/strict";
import { amountTyped, axisLabels, budgetRows, columns, conversationCells, GAP, indexed, markedRow, modelCells, money,
  monthLine, PERIOD, projectBars, reportArgs, summaryCells, ticks, tipFor, tokensShort, whole }
  from "../mods/herdr-fold/report.js";

const OPUS = "#3987e5", SONNET = "#d95926", HAIKU = "#199e70", CODEX = "#c98500";
/** A day as core's report has it. @param {string} label @param {[string, string, number][]} models */
const day = (label, models) => ({ day: `2026-11-0${label.slice(-1)}`, label,
  total: models.reduce((sum, one) => sum + one[2], 0),
  models: models.map(([name, color, cost]) => ({ model: name.toLowerCase(), name, color, cost })) });
// usage.html's Nov 7 and Nov 8
const NOV7 = day("Nov 7", [["Opus 5.5", OPUS, 25.6], ["Sonnet 5.5", SONNET, 2.8], ["Haiku 5.5", HAIKU, 2.0],
  ["GPT-5 Codex", CODEX, 3.1]]);
const NOV8 = day("Nov 8", [["Opus 5.5", OPUS, 6.3], ["Sonnet 5.5", SONNET, 0.6], ["Haiku 5.5", HAIKU, 0.3]]);
// usage.html's November: $18.40 by the 9th of 30, a budget of $50, on pace for $46
const MONTH = { agent: "codex", name: "Codex", key: "Codex · API key", id: "2026-11", label: "November", budget: 50,
  days: 30, day: 9, spent: [[1, 1.2], [2, 3.0], [3, 4.1], [4, 6.8], [5, 8.0], [6, 9.9], [7, 12.3], [8, 15.1],
    [9, 18.4]], today: 18.4, pace: 46, over: false, line: "~$18.40 of $50 · on pace for ~$46", end: "Nov 30",
  color: CODEX };

test("money and tokens are written as core writes them", () => {
  assert.deepEqual([money(130.9), money(0), money(1234.5), money(0.004)], ["$130.90", "$0.00", "$1,234.50", "$0.00"]);
  assert.deepEqual([whole(46.2), whole(57.5), whole(1250)], ["$46", "$58", "$1,250"]);
  // a figure herdr-fold computes wears one tilde, as core's (a budget, typed in, none)
  assert.deepEqual([money(130.9, true), whole(46.2, true)], ["~$130.90", "~$46"]);
  assert.deepEqual([999, 1000, 9949, 68_000, 999_499, 38_200_000, 2_100_000_000].map(tokensShort),
    ["999", "1.0k", "9.9k", "68k", "999k", "38.2M", "2.1B"]);
});

test("an axis has clean ticks from 0 past its largest value, four steps at most", () => {
  assert.deepEqual(ticks(33.5), [0, 10, 20, 30, 40]);          // usage.html's per day
  assert.deepEqual(ticks(50), [0, 20, 40, 60]);                // and its month: the budget under the top
  assert.deepEqual(ticks(0.42), [0, 0.2, 0.4, 0.6]);
  assert.deepEqual(ticks(3), [0, 1, 2, 3]);                    // its largest value may be its top
  assert.deepEqual(ticks(0), [0, 1]);
  assert.deepEqual(ticks(1800), [0, 500, 1000, 1500, 2000]);
});

test("a day is a column of its models' segments from the baseline up, 2 px of the surface between them", () => {
  const [seven, eight, none] = columns([NOV7, NOV8, day("Nov 9", [])], 180, 40);
  assert.equal(GAP, 2);
  assert.deepEqual(seven.segments.map((one) => one.color), [OPUS, SONNET, HAIKU, CODEX]);
  assert.deepEqual(seven.segments.map((one) => one.h), [113, 11, 7, 12]);      // 25.6 of 40 is 115.2 of 180
  assert.deepEqual(seven.segments.map((one) => one.top), [false, false, false, true]);   // the last one rounded
  assert.equal(seven.segments.reduce((sum, one) => sum + one.h + GAP, 0) <= Math.ceil(33.5 / 40 * 180), true);
  assert.deepEqual(eight.segments.map((one) => one.h), [26, 1, 1]);            // a sliver is still seen
  assert.deepEqual(none.segments, []);
  assert.deepEqual(columns([NOV7], 180, 0)[0].segments.map((one) => one.h), [1, 1, 1, 1]);     // no scale: no height
});

test("the days' names stand under the columns, every few where there are many, today's always", () => {
  const days = (/** @type {number} */ n) => Array.from({ length: n }, (_, d) => ({ label: `Nov ${d + 1}` }));
  assert.deepEqual(axisLabels(days(7), 10), ["Nov 1", "Nov 2", "Nov 3", "Nov 4", "Nov 5", "Nov 6", "Nov 7"]);
  const thirty = axisLabels(days(30), 10);
  assert.deepEqual(thirty.filter(Boolean), ["Nov 1", "Nov 5", "Nov 10", "Nov 15", "Nov 20", "Nov 25", "Nov 30"]);
  assert.equal(thirty.length, 30);
  assert.deepEqual(axisLabels([], 10), []);
});

test("the first day, a month's 1st and the last day are always named, the rest evenly where they fit", () => {
  // 30 days over a month's end: Oct 21 to Nov 19, the TUI's rule (day_labels)
  const span = [...Array.from({ length: 11 }, (_, d) => ({ label: `Oct ${d + 21}` })),
    ...Array.from({ length: 19 }, (_, d) => ({ label: `Nov ${d + 1}` }))];
  assert.deepEqual(axisLabels(span, 10).filter(Boolean), ["Oct 21", "Oct 25", "Nov 1", "Nov 5", "Nov 10", "Nov 15",
    "Nov 19"]);                                  // Oct 30 gives way to the 1st
  assert.deepEqual(axisLabels(span.slice(1, -1), 10).filter(Boolean), ["Oct 22", "Oct 25", "Nov 1", "Nov 5",
    "Nov 10", "Nov 15", "Nov 18"]);
  assert.deepEqual(axisLabels(span.slice(10, 13), 2).filter(Boolean), ["Oct 31", "Nov 2"]);    // the ends first
  for (const most of [1, 3, 10, 30]) {
    const named = axisLabels(span, most), at = named.flatMap((name, n) => (name ? [n] : []));
    assert.equal(named[29], "Nov 19");
    assert.ok(at.every((n, k) => k === 0 || n - at[k - 1] >= Math.ceil(30 / most)), `colliding at ${most}`);
  }
});

test("a day's tip is its date and sum (an estimate's tilde), then each model with its swatch and cost", () => {
  assert.deepEqual(tipFor(NOV7), { title: "Nov 7 · ~$33.50", rows: [{ name: "Opus 5.5", color: OPUS, text: "$25.60" },
    { name: "Sonnet 5.5", color: SONNET, text: "$2.80" }, { name: "Haiku 5.5", color: HAIKU, text: "$2.00" },
    { name: "GPT-5 Codex", color: CODEX, text: "$3.10" }] });
  assert.deepEqual(tipFor(day("Nov 9", [])), { title: "Nov 9 · ~$0.00", rows: [] });
});

test("the month's line runs to today, its pace on to the month's end, the budget a line across", () => {
  const drawn = monthLine(MONTH);                 // places as shares of its plot: x from the left, y from the top
  assert.deepEqual(drawn.ticks.map((one) => [one.label, one.y]), [["$0", 1], ["$20", 1 - 20 / 60],
    ["$40", 1 - 40 / 60], ["$60", 0]]);
  assert.equal(drawn.spent.length, 10);                                        // the month's start, then nine days
  assert.deepEqual(drawn.spent[0], [0, 1]);
  const y = (/** @type {number} */ v) => 1 - v / 60, x = (/** @type {number} */ d) => d / 30;
  assert.deepEqual(drawn.spent[9], [x(9), y(18.4)]);
  assert.deepEqual(drawn.today, { x: x(9), y: y(18.4), label: "~$18.40 today" });
  assert.deepEqual(drawn.pace, { from: [x(9), y(18.4)], to: [1, y(46)], label: "on pace for ~$46" });
  assert.deepEqual(drawn.budget, { y: y(50), label: "Budget $50" });          // the budget, the ticks: no tilde
  assert.deepEqual([drawn.first, drawn.last], ["Nov 1", "Nov 30"]);
});

test("a month with no budget has no budget line, and its last day no pace on from it", () => {
  const free = monthLine({ ...MONTH, budget: null });
  assert.equal(free.budget, null);
  assert.deepEqual(free.ticks.map((one) => one.label), ["$0", "$20", "$40", "$60"]);       // the pace still fits
  const ended = monthLine({ ...MONTH, day: 30, spent: [...MONTH.spent, [30, 44]], today: 44, pace: 44 });
  assert.equal(ended.pace, null);
  assert.equal(monthLine(null), null);
});

test("money is written the same where the engine knows no locale", () => {
  const was = Number.prototype.toLocaleString;
  Number.prototype.toLocaleString = function () { return String(this); };      // as the app's engine answers
  try {
    assert.deepEqual([money(84.2), money(1234.5), money(1_000_000), whole(1250), whole(46.2)],
      ["$84.20", "$1,234.50", "$1,000,000.00", "$1,250", "$46"]);
  } finally {
    Number.prototype.toLocaleString = was;
  }
});

test("a column is as wide as most of its day's room, the days named every few past ten", () => {
  assert.deepEqual(axisLabels(Array.from({ length: 12 }, (_, d) => ({ label: `Nov ${d + 1}` })), 10)
    .filter(Boolean), ["Nov 1", "Nov 3", "Nov 5", "Nov 7", "Nov 9", "Nov 12"]);
});

test("the projects' bars are as long as their share of the largest, the value at each one's tip", () => {
  assert.deepEqual(projectBars([{ name: "lumen-api", cost: 84.2, tokens: 1 }, { name: "harbor-web", cost: 42.1,
    tokens: 1 }, { name: "tidepool", cost: null, tokens: 14_200 }]), [
    { name: "lumen-api", share: 1, text: "$84.20" }, { name: "harbor-web", share: 0.5, text: "$42.10" },
    { name: "tidepool", share: 0, text: "14k tokens" }]);
  assert.deepEqual(projectBars([]), []);
});

test("the summary's first cell is the wide one, and a pace over its budget is told apart", () => {
  const cells = summaryCells([
    { key: "Claude · Max plan", agent: "claude", value: 130.9, text: "$130.90", unit: "API value", over: false,
      line: "no charge on the plan · week 16% of its limit" },
    { key: "Codex · API key", agent: "codex", value: 45.1, text: "$45.10", unit: "spent", over: true,
      line: "November $45.10 of $50 · on pace for $58" },
    { key: "Tokens", value: 38_200_000, text: "38.2M", line: "81% read from cache" },
    { key: "Commits from these conversations", value: 9, text: "9", about: false, line: "$15.50 each, API value" }]);
  assert.deepEqual(cells.map((one) => one.grow), [1.4, 1, 1, 1]);
  assert.deepEqual(cells[0], { key: "Claude · Max plan", text: "$130.90", unit: "API value", grow: 1.4,
    line: "no charge on the plan · week 16% of its limit", pace: "" });
  assert.deepEqual([cells[1].line, cells[1].pace], ["November $45.10 of $50 · ", "on pace for $58"]);
  assert.deepEqual([cells[2].unit, cells[3].text], ["", "9"]);
  // a model with no price: no dollars, so no word for them either
  assert.equal(summaryCells([{ key: "Codex", agent: "codex", value: null, text: "no price", unit: "API value",
    line: "" }])[0].unit, "");
});

test("a conversation's row says its cost as value or spent, its commits with their lines, or that it has none", () => {
  const words = { none_yet: "none yet", no_price: "no price" };
  const row = { session: "s1", title: "Fix the page past the last one", space: "lumen-api", turns: 38,
    models: [{ name: "Opus 5.5", color: OPUS }, { name: "Haiku 5.5", color: HAIKU }], tokens: 9_400_000, cache: 84,
    cost: 31.4, kind: "value", commits: 2, commits_text: "2", changed: "+134 −12", per_commit: 15.7 };
  assert.deepEqual(conversationCells(row, words), { title: "Fix the page past the last one", space: "lumen-api",
    models: [OPUS, HAIKU], turns: "38", tokens: "9.4M", cache: "84%", cost: "$31.40", kind: "value", commits: "2",
    changed: "+134 −12", per: "$15.70", none: false });
  const bare = conversationCells({ ...row, cost: null, cache: null, commits: 0, commits_text: "none yet", changed: "",
    per_commit: null }, words);
  assert.deepEqual([bare.cost, bare.kind, bare.cache, bare.commits, bare.per, bare.none],
    ["no price", "", "–", "none yet", "–", true]);
  assert.equal(conversationCells({ ...row, commits: null, commits_text: "–", changed: "", per_commit: null },
    words).none, true);
});

test("a model's row says each kind of token, – for none, and no price where it has none", () => {
  const row = { name: "GPT-5 Codex", color: CODEX, agent: "Codex", input: 400_000, write: 0, read: 1_400_000,
    output: 90_000, cost: 8.6, kind: "spent", text: "$8.60" };
  assert.deepEqual(modelCells(row), { name: "GPT-5 Codex", color: CODEX, agent: "Codex", input: "400k", write: "–",
    read: "1.4M", output: "90k", cost: "$8.60", kind: "spent", priced: true });
  assert.deepEqual(modelCells({ ...row, name: "codex-auto-review", cost: null, text: "no price" }).cost, "no price");
  assert.equal(modelCells({ ...row, cost: null, text: "no price" }).kind, "");
  assert.equal(modelCells({ ...row, cost: null, text: "no price" }).priced, false);
});

test("the report is asked for with its period, agent, folder, the agents' plans and the theme's card and text", () => {
  const agents = [{ key: "codex", name: "Codex", plan: "API key" }];
  assert.equal(PERIOD, "7d");
  assert.deepEqual(reportArgs("report", { period: "7d", agent: null, folder: null, agents,
    theme: { surface: "#1e1e2e", foreground: "#cdd6f4" } }), ["report", "7d", "", "",
    `--agents=${JSON.stringify(agents)}`, "--surface=#1e1e2e", "--text=#cdd6f4"]);
  assert.deepEqual(reportArgs("csv", { period: "month", agent: "codex", folder: "/home/dev/lumen-api", agents: null,
    theme: null }), ["csv", "month", "codex", "/home/dev/lumen-api", "--agents=[]"]);
});

test("a budget has a field for each agent on an API key, and no other", () => {
  const agents = [{ key: "claude", name: "Claude", plan: "Max" }, { key: "codex", name: "Codex", plan: "API key" }];
  assert.deepEqual(budgetRows(agents, { codex: 50 }), [{ key: "codex", name: "Codex", value: "50" }]);
  assert.deepEqual(budgetRows(agents, {}), [{ key: "codex", name: "Codex", value: "" }]);
  assert.deepEqual(budgetRows(agents, { codex: 1250.5 }), [{ key: "codex", name: "Codex", value: "1250.50" }]);
  assert.deepEqual(budgetRows(null, { codex: 50 }), []);
});

test("the row asked for is found among the conversations by its session", () => {
  const rows = [{ session: "a" }, { session: "b" }];
  assert.deepEqual([markedRow(rows, "b"), markedRow(rows, "z"), markedRow(rows, null), markedRow(null, "a")],
    [1, -1, -1, -1]);
});

test("the index is looked at again until nothing is left, stopped where a look read nothing", async () => {
  const answers = [{ read: 256, left: 300 }, { read: 256, left: 44 }, { read: 44, left: 0 }];
  let looks = 0;
  assert.deepEqual(await indexed(async () => answers[looks++]), { looks: 3, left: 0, read: 556 });
  looks = 0;
  assert.deepEqual(await indexed(async () => (looks++, { read: 0, left: 0 })), { looks: 1, left: 0, read: 0 });
  looks = 0;
  assert.deepEqual(await indexed(async () => (looks++, { read: 0, left: 90 })), { looks: 1, left: 90, read: 0 });
  looks = 0;
  assert.deepEqual(await indexed(async () => (looks++, { read: 1, left: 5 }), 4), { looks: 4, left: 5, read: 4 });
  const seen = [];
  await indexed(async () => answers[seen.length], 9, (left) => seen.push(left));
  assert.deepEqual(seen, [300, 44, 0]);
});

test("a budget typed is an amount as core takes one, or nothing (no budget)", () => {
  for (const good of ["50", "$50", "1,250.50", " 12.5 ", "", "  ", "0"]) assert.equal(amountTyped(good), true, good);
  for (const bad of ["12x", "-5", "1,25", "$", "5 0", "1e3"]) assert.equal(amountTyped(bad), false, bad);
});
