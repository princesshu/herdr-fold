// @ts-check
// Tests for the chat's timeline (timeline.js): core/chat.py's steps as the rows the chat draws, a call and its result
// in one, and each row's time in this Mac's own zone and hour style.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { bottomLayout, callWords, clock, connectorRow, format, planStrip, planWords, RHYTHM, setForms, signinRow,
  stepLayout, timeline, timelineMarkdown, userLayout } from "../mods/herdr-fold/timeline.js";

const at = (minute) => `2026-11-08T14:${String(minute).padStart(2, "0")}:00.000Z`;
const EDIT = { path: "src/books.py", lines: ["@@ -12,1 +12,1 @@", "-    return page", "+    return min(page, last)"] };
/** TEXT with the narrow space some ICU versions put before AM and PM made a plain one. @param {string} text */
const plain = (text) => text.replace(/ /g, " ");

test("a call and its result are one row: Edit and Write open, the rest folded", () => {
  const rows = timeline([
    { kind: "user", text: "Fix the page past the last one", at: at(0) },
    { kind: "tool", id: "t1", name: "Read", main: "src/books.py", input: { file_path: "src/books.py" }, at: at(1) },
    { kind: "result", id: "t1", ok: true, output: "1\tfrom lumen import store", change: null, at: at(2) },
    { kind: "tool", id: "t2", name: "Edit", main: "src/books.py", input: {}, at: at(2) },
    { kind: "result", id: "t2", ok: true, output: "The file was updated.", change: EDIT, at: at(3) },
    { kind: "text", text: "Past the last page, the last page is served.", at: at(4) },
  ]);
  assert.deepEqual(rows.map((r) => r.kind), ["user", "tool", "tool", "text"]);
  assert.deepEqual([rows[1].name, rows[1].main, rows[1].ok, rows[1].open], ["Read", "src/books.py", true, false]);
  assert.equal(rows[1].output, "1\tfrom lumen import store");
  assert.deepEqual([rows[2].open, rows[2].change], [true, EDIT]);
  assert.deepEqual([rows[0].at, rows[3].at], [at(0), at(4)]);
});

test("a call still waiting has no outcome yet; a failed one says it failed", () => {
  const rows = timeline([
    { kind: "tool", id: "t1", name: "Bash", main: "pytest -q", input: {}, at: at(1) },
    { kind: "result", id: "t1", ok: false, output: "Exit code 1", change: null, at: at(2) },
    { kind: "tool", id: "t2", name: "Bash", main: "pytest -q tests/test_books.py", input: {}, at: at(3) },
  ]);
  assert.deepEqual(rows.map((r) => r.ok), [false, null]);
  assert.equal(rows[0].output, "Exit code 1");
});

test("a thought says how long it took, past a minute in minutes and seconds", () => {
  const labels = timeline([4200, 65000, 300, null].map((ms) => ({ kind: "thought", ms, at: at(1) })))
    .map((r) => r.label);
  assert.deepEqual(labels, ["Thought for 4s", "Thought for 1m 5s", "Thought for 1s", "Thought"]);
});

test("a skill and a subagent take their results; a result with no call is left out", () => {
  const rows = timeline([
    { kind: "skill", id: "s1", name: "api-routes", at: at(1) },
    { kind: "result", id: "s1", ok: true, output: "Launching skill: api-routes", change: null, at: at(1) },
    { kind: "agent", id: "a1", name: "Explore", task: "Find the pager", at: at(2) },
    { kind: "result", id: "a1", ok: true, output: "In src/lumen/routes/books.py", change: null, at: at(3) },
    { kind: "tool", id: "t1", name: "Bash", main: "pytest -q", input: {}, at: at(3) },
    { kind: "result", id: "gone", ok: true, output: "from a call before this read", change: null, at: at(4) },
    { kind: "other", type: "compact_boundary", summary: "Chat compacted", at: at(5) },
  ]);
  assert.deepEqual(rows.map((r) => r.kind), ["skill", "agent", "tool", "other"]);
  assert.deepEqual([rows[0].ok, rows[1].ok, rows[1].output], [true, true, "In src/lumen/routes/books.py"]);
  assert.equal(rows[2].ok, null);
});

test("tasks added one after another are one row, a step done its own, an approved plan with its call", () => {
  const rows = timeline([
    { kind: "tool", id: "p1", name: "ExitPlanMode", main: null, input: {}, at: at(1) },
    { kind: "result", id: "p1", ok: true, output: "Approved.", change: null, plan: 4, at: at(1) },
    { kind: "tasks", id: "k1", added: 1, at: at(2) },
    { kind: "result", id: "k1", ok: true, output: "Task #1 created successfully", change: null, at: at(2) },
    { kind: "tasks", id: "k2", added: 1, at: at(2) },
    { kind: "task", id: "k3", text: "Keep the page inside 1…pages", at: at(3) },
    { kind: "result", id: "k3", ok: true, output: "Updated task #1 status", change: null, at: at(3) },
    { kind: "tasks", id: "k4", added: 1, at: at(4) },
  ]);
  assert.deepEqual(rows.map((r) => [r.kind, r.added ?? r.text ?? r.plan]),
    [["tool", 4], ["tasks", 2], ["task", "Keep the page inside 1…pages"], ["tasks", 1]]);
  assert.equal(rows[1].at, at(2));
  assert.deepEqual([4, 1, 0].map(planWords), ["approved · 4 steps", "approved · 1 step", "approved"]);
});

const PLAN = { steps: [{ text: "Keep the page inside 1…pages", state: "done", after: null },
  { text: "Add the tests past the end", state: "now", after: null },
  { text: "Run the whole suite", state: "next", after: "after Add the tests past the end" }],
note: null, done: "1 done", count: "1 of 3 done", finished: false, plan: 4 };

test("the plan strip folded is the step at work and how many are done", () => {
  assert.equal(planStrip(null, false, false), null);
  assert.equal(planStrip({ ...PLAN, steps: [] }, true, false), null);
  assert.deepEqual(planStrip(PLAN, false, true), { head: { state: "now", text: "Add the tests past the end",
    count: "1 of 3 done" }, rows: [] });
  const waiting = { ...PLAN, steps: PLAN.steps.map((step) => ({ ...step, state: step.state === "now" ? "next"
    : step.state })) };
  assert.equal(planStrip(waiting, false, false)?.head.state, "next");            // none at work: the next one
  const all = { ...PLAN, steps: PLAN.steps.map((step) => ({ ...step, state: "done" })), count: "All 3 done" };
  assert.deepEqual(planStrip(all, false, false)?.head, { state: "done", text: "All 3 done", count: "" });
});

test("the plan strip open folds the done steps into one row over the rest, its head not counting again", () => {
  const open = planStrip(PLAN, true, false);
  assert.deepEqual(open?.head, { state: null, text: "Plan", count: "" });
  assert.deepEqual(open?.rows.map((row) => [row.kind, row.text]), [["fold", "1 done"],
    ["now", "Add the tests past the end"], ["next", "Run the whole suite"]]);
  assert.equal(open?.rows[2].after, "after Add the tests past the end");
  assert.deepEqual(planStrip(PLAN, true, true)?.rows.map((row) => row.kind), ["fold", "done", "now", "next"]);
  const none = { ...PLAN, steps: PLAN.steps.slice(1), done: null };
  assert.deepEqual(planStrip(none, true, true)?.rows.map((row) => row.kind), ["now", "next"]);
});

/** RUN with this Mac in New York, the system's forms FORMS (none: not known yet), both put back after it.
 * @param {any} forms @param {() => void} run */
function inNewYork(forms, run) {
  const zone = process.env.TZ;
  process.env.TZ = "America/New_York";
  setForms(forms);
  try {
    run();
  } finally {
    setForms(null);
    if (zone === undefined) delete process.env.TZ;
    else process.env.TZ = zone;
  }
}

// macOS's own patterns for its user (NSDateFormatter's, from the templates jmm, MMMdjmm, yMMMdjmm, EEEMMMdjmm)
const US = { time: "h:mm a", day: "MMM d, h:mm a", year: "MMM d, y, h:mm a", weekday: "EEE, MMM d, h:mm a" };
const US_24 = { time: "HH:mm", day: "MMM d, HH:mm", year: "MMM d, y, HH:mm", weekday: "EEE, MMM d, HH:mm" };
const GB = { time: "HH:mm", day: "d MMM, HH:mm", year: "d MMM y, HH:mm", weekday: "EEE d MMM, HH:mm" };

test("a time today is the time alone, yesterday's says so, an older one its date: as this Mac's settings say", () => {
  const now = new Date("2026-11-08T14:00:00Z");                         // 9 AM in New York
  inNewYork(US, () => assert.deepEqual(["2026-11-08T13:32:00Z", "2026-11-08T03:30:00Z", "2026-11-06T21:10:00Z",
    "2025-11-06T21:10:00Z"].map((iso) => clock(iso, now)), ["8:32 AM", "Yesterday 10:30 PM", "Nov 6, 4:10 PM",
    "Nov 6, 2025, 4:10 PM"]));
  inNewYork(US_24, () => assert.deepEqual(["2026-11-08T13:32:00Z", "2026-11-06T21:10:00Z"]
    .map((iso) => clock(iso, now)), ["08:32", "Nov 6, 16:10"]));       // a US Mac set to 24 hours
  inNewYork(GB, () => assert.equal(clock("2026-11-06T21:10:00Z", now), "6 Nov, 16:10"));
  inNewYork(null, () => assert.deepEqual([clock("2026-11-06T21:10:00Z", now), clock("not a time", now),
    clock(null, now)], ["6 Nov, 16:10", "", ""]));                       // the system not asked yet: 24 hours
});

test("a pattern's letters are the time's parts, a quoted word as it is", () => {
  inNewYork(null, () => {
    const when = new Date("2026-11-10T01:05:00Z");                        // Mon, Nov 9, 8:05 PM there
    assert.equal(format(when, "EEEE, MMMM d, y 'at' h:mm a"), "Monday, November 9, 2026 at 8:05 PM");
    assert.equal(format(when, "EEE dd.MM.yy H.mm"), "Mon 09.11.26 20.05");
    assert.equal(format(when, "''hh:mm''"), "'08:05'");
  });
});

// every kind of step the timeline draws with a dot on its line (the person's message has none: a turn starts there)
const KINDS = ["thought", "tool", "skill", "agent", "tasks", "task", "text", "other"];

test("every step's dot stands on the middle of its first line, whatever its kind", () => {
  for (const kind of KINDS) {
    const step = stepLayout(kind);
    assert.equal(step.dotTop + step.dot / 2, step.pad + step.line / 2, kind);          // the dot's centre, the line's
    assert.ok(Number.isInteger(step.dotTop), kind);                                     // whole pixels: a sharp dot
  }
});

test("a one-line step has as much line above its dot as below it, the gap between steps split evenly", () => {
  for (const kind of KINDS) {
    const step = stepLayout(kind), high = step.pad + step.line + step.pad;             // the row of a one-line step
    assert.equal(step.dotTop, high - step.dotTop - step.dot, kind);
  }
});

test("a call's line is 24 high, Claude's words' 20, as center-chat.html has them; each dot on its middle", () => {
  assert.deepEqual([stepLayout("tool").line, stepLayout("text").line, stepLayout("tool").dot], [24, 20, 8]);
  for (const kind of KINDS.filter((k) => k !== "text")) assert.equal(stepLayout(kind).line, 24, kind);
  assert.equal(stepLayout("tool").pad, 8);                                   // two steps 16 apart, the mockup's
});

test("a heading in Claude's words keeps the step's rhythm: bold on a line of its own, no margin of its own", () => {
  assert.equal(timelineMarkdown("# Pagination\nThe last page is kept."), "**Pagination**\nThe last page is kept.");
  assert.equal(timelineMarkdown("## What changed ##\n\n### Tests"), "**What changed**\n\n**Tests**");
  assert.equal(timelineMarkdown("Summary\n=======\nDone."), "**Summary**\nDone.");          // a setext heading
  assert.equal(timelineMarkdown("Notes\n---"), "**Notes**");
  assert.equal(timelineMarkdown("Text.\n\n---\n\nMore."), "Text.\n\n---\n\nMore.");    // a rule stays one
  assert.equal(timelineMarkdown("```md\n# not a heading\n```"), "```md\n# not a heading\n```");   // code kept
  assert.equal(timelineMarkdown("#hashtag and 1. a list"), "#hashtag and 1. a list");
  assert.equal(timelineMarkdown("- an item\n---"), "- an item\n---");                     // a list, then a rule
  assert.equal(timelineMarkdown("#"), "#");
});

test("the card Claude waits on stands a step's gap under the last step, the line reaching its top edge", () => {
  const step = stepLayout("text"), between = step.pad + step.pad;                // two steps' rows apart
  const card = bottomLayout(true);
  assert.equal(step.pad + card.rows + card.top, between);                       // the last line to the card's border
  assert.equal(card.line, card.top);                                            // no break in the line before it
  const prompt = bottomLayout(false);
  assert.equal(prompt.line, 0);                                                 // the prompt is no step: no line
  assert.ok(prompt.rows + prompt.top > card.rows + card.top);                   // it floats apart: a new turn
});

test("every part of the chat keeps to one spacing scale, on the design's grid", () => {
  const r = RHYTHM, step = stepLayout("tool"), user = userLayout(), card = bottomLayout(true);
  const prompt = bottomLayout(false);
  const parts = readFileSync(new URL("../mods/herdr-fold/parts.js", import.meta.url), "utf8");
  const grid = (/export const SPACE = \[([\d, ]+)\]/.exec(parts)?.[1] ?? "").split(",").map(Number);
  for (const [name, px] of Object.entries(r)) if (!["line", "dot"].includes(name)) assert.ok(grid.includes(px), name);
  const gaps = {                          // each part: the room from the line above it to its own top, as drawn
    "step after step": step.pad + step.pad,
    "the person's message after a step": step.pad + user.top,
    "a step after the person's message": user.bottom + step.pad,
    "a card after the last step": step.pad + card.rows + card.top,
    "the prompt after the last step": step.pad + prompt.rows + prompt.top,
  };
  assert.deepEqual(gaps, { "step after step": r.step, "the person's message after a step": r.turn,
    "a step after the person's message": r.step, "a card after the last step": r.step,
    "the prompt after the last step": r.turn });
  assert.equal(user.label, r.pad);                                    // its time over its box, as a label over a box
  assert.equal(user.boxY, r.gap);
});

// the servers as agent_setup.py's setup tells them: claude.ai's by their account name, a project's by its own
const SERVERS = [{ name: "claude.ai Google Drive", label: "Google Drive", brand: "google-drive", state: "on" },
  { name: "claude.ai Box", label: "Box", brand: "box", state: "sign in" },
  { name: "tidepool", label: "tidepool", brand: null, state: "on" },
  { name: "tidepool__db", label: "tidepool db", brand: null, state: "on" }];

test("a connector's call is drawn by its brand: the server's label and logo, the tool's own name", () => {
  assert.deepEqual(connectorRow("mcp__claude_ai_Google_Drive__search_files", SERVERS),
    { server: "claude.ai Google Drive", label: "Google Drive", brand: "google-drive", tool: "search_files" });
  assert.deepEqual(connectorRow("mcp__tidepool__db__query", SERVERS),          // the longest server's key wins
    { server: "tidepool__db", label: "tidepool db", brand: null, tool: "query" });
  assert.deepEqual(connectorRow("mcp__tidepool__list_tables", SERVERS),
    { server: "tidepool", label: "tidepool", brand: null, tool: "list_tables" });
});

test("a call of a server the setup does not name is drawn by its key: a letter tile's", () => {
  assert.deepEqual(connectorRow("mcp__harbor-docs__search", SERVERS),
    { server: null, label: "harbor-docs", brand: null, tool: "search" });
  assert.deepEqual(connectorRow("mcp__harbor-docs__search", null),
    { server: null, label: "harbor-docs", brand: null, tool: "search" });
});

test("Claude's own tools, and a name that is no server's tool, are no connector's", () => {
  for (const name of ["Read", "mcp__", "mcp__box", "mcp____search", "mcp__box__", "", null, undefined]) {
    assert.equal(connectorRow(/** @type {any} */ (name), SERVERS), null, String(name));
  }
});

test("a connector's call says its first words: its input's first text, one line, cut where long", () => {
  assert.equal(callWords({ query: "paging spec", limit: "5" }), "paging spec");
  assert.equal(callWords({ id: "  Lumen API: paging, v2\nmore" }), "Lumen API: paging, v2");
  assert.equal(callWords({ query: "x".repeat(200) }), `${"x".repeat(79)}…`);
  assert.equal(callWords({ query: "a\x1b[2Jb" }), "a?[2Jb");                  // an escape code shown, never run
  assert.equal(callWords({}), "");
  assert.equal(callWords(null), "");
});

test("a sign-in's step asks while its server is to sign in, turns while it signs in, is done once it is on", () => {
  const box = { server: "claude.ai Box", label: "Box", brand: "box", error: null };
  assert.deepEqual(signinRow("claude.ai Box", SERVERS), { ...box, state: "ask", words: "needs you to sign in" });
  assert.deepEqual(signinRow("claude.ai Box", SERVERS, { signing: { "claude.ai Box": { address: "t9", at: 1 } } }),
    { ...box, state: "busy", words: "signing in…" });
  const on = SERVERS.map((one) => (one.name === "claude.ai Box" ? { ...one, state: "on" } : one));
  assert.deepEqual(signinRow("claude.ai Box", on), { ...box, state: "done", words: "signed in" });
});

test("a sign-in asked after the setup was last read asks, whatever that older setup says", () => {
  const on = SERVERS.map((one) => ({ ...one, state: "on" }));
  assert.equal(signinRow("claude.ai Box", on, { newer: true }).state, "ask");
  assert.equal(signinRow("claude.ai Box", null, { newer: true }).state, "ask");
});

test("a sign-in that could not start says why and can be tried again", () => {
  const row = signinRow("claude.ai Box", SERVERS, { failed: { "claude.ai Box": "claude: command not found" } });
  assert.deepEqual([row.state, row.words, row.error], ["ask", "needs you to sign in", "claude: command not found"]);
});

test("a sign-in of a server no longer to sign in nor on is a thing of the past: no button", () => {
  const off = SERVERS.map((one) => (one.name === "claude.ai Box" ? { ...one, state: "off here" } : one));
  assert.deepEqual(signinRow("claude.ai Box", off), { server: "claude.ai Box", label: "Box", brand: "box",
    state: "past", words: "needed a sign-in", error: null });
  assert.deepEqual(signinRow("harbor-docs", SERVERS), { server: "harbor-docs", label: "harbor-docs", brand: null,
    state: "past", words: "needed a sign-in", error: null });
  assert.equal(signinRow("claude.ai Box", null).state, "past");                // the setup not read yet
});

test("a sign-in's step is a row of the timeline, in its place", () => {
  const rows = timeline([{ kind: "text", text: "The notes are in Box.", at: at(1) },
    { kind: "signin", server: "claude.ai Box", at: at(2) }]);
  assert.deepEqual(rows[1], { kind: "signin", server: "claude.ai Box", at: at(2) });
});
