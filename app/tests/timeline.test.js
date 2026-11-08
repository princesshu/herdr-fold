// @ts-check
// Tests for the chat's timeline (timeline.js): core/chat.py's steps as the rows the chat draws, a call and its result
// in one, and each row's time in this Mac's own zone and hour style.
import { test } from "node:test";
import assert from "node:assert/strict";
import { clock, timeline } from "../mods/herdr-fold/timeline.js";

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

test("a skill, a sub-agent and a todo list take their results; a result with no call is left out", () => {
  const rows = timeline([
    { kind: "skill", id: "s1", name: "api-routes", at: at(1) },
    { kind: "result", id: "s1", ok: true, output: "Launching skill: api-routes", change: null, at: at(1) },
    { kind: "agent", id: "a1", name: "Explore", task: "Find the pager", at: at(2) },
    { kind: "result", id: "a1", ok: true, output: "In src/lumen/routes/books.py", change: null, at: at(3) },
    { kind: "todo", id: "d1", items: [{ text: "Write the test", done: true }], at: at(3) },
    { kind: "result", id: "gone", ok: true, output: "from a call before this read", change: null, at: at(4) },
    { kind: "other", type: "compact_boundary", summary: "Conversation compacted", at: at(5) },
  ]);
  assert.deepEqual(rows.map((r) => r.kind), ["skill", "agent", "todo", "other"]);
  assert.deepEqual([rows[0].ok, rows[1].ok, rows[1].output], [true, true, "In src/lumen/routes/books.py"]);
  assert.equal(rows[2].ok, null);
});

test("a time is its hours and minutes in the system's 12 or 24 hours, whatever the runtime's options do", () => {
  const zone = process.env.TZ, own = Date.prototype.toLocaleTimeString;
  process.env.TZ = "America/New_York";
  try {
    const now = new Date("2026-11-08T14:00:00Z");
    // the Herdr app's runtime: its own fixed form, seconds and all, the options left aside
    Date.prototype.toLocaleTimeString = function () { return own.call(this, "en-US", { hour12: true }); };
    assert.equal(clock("2026-11-08T13:05:00Z", now), "8:05 AM");
    Date.prototype.toLocaleTimeString = function () { return own.call(this, "en-GB"); };
    assert.equal(clock("2026-11-08T13:05:00Z", now), "08:05");
    assert.equal(clock("2026-11-06T21:10:00Z", now), "Nov 6, 16:10");
  } finally {
    Date.prototype.toLocaleTimeString = own;
    if (zone === undefined) delete process.env.TZ;
    else process.env.TZ = zone;
  }
});

test("a time today is the time alone, yesterday's says so, an older one its date", () => {
  const zone = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    const now = new Date("2026-11-08T14:00:00Z");                       // 9 AM in New York
    assert.equal(plain(clock("2026-11-08T13:32:00Z", now)), "8:32 AM");
    assert.equal(plain(clock("2026-11-08T03:30:00Z", now)), "Yesterday 10:30 PM");    // the evening before, there
    assert.equal(plain(clock("2026-11-06T21:10:00Z", now)), "Nov 6, 4:10 PM");
    assert.equal(plain(clock("2025-11-06T21:10:00Z", now)), "Nov 6, 2025, 4:10 PM");
    assert.equal(clock("not a time", now), "");
    assert.equal(clock(null, now), "");
  } finally {
    if (zone === undefined) delete process.env.TZ;
    else process.env.TZ = zone;
  }
});
