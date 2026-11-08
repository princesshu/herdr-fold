// @ts-check
// Tests for the chat's timeline (timeline.js): core/chat.py's steps as the rows the chat draws, a call and its result
// in one, and each row's time in this Mac's own zone and hour style.
import { test } from "node:test";
import assert from "node:assert/strict";
import { clock, format, setForms, timeline } from "../mods/herdr-fold/timeline.js";

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
