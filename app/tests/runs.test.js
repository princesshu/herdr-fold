// @ts-check
// Tests for the Agents tab's Runs (runs.js): which runs a space's scope and an agent's filter show, the buttons a
// run's properties offer, the sentence under New run's choices, the status bar's words. The runs are invented.
import test from "node:test";
import assert from "node:assert/strict";
import { formNote, runActions, runShown, runsWorking } from "../mods/herdr-fold/runs.js";

/** A run as core lists it (runs.py's row()), with MORE. @param {Record<string, any>} more */
const run = (more) => /** @type {import("../mods/herdr-fold/runs.js").Run} */ ({ key: "claude:7c5dcf5d",
  agent: "claude", name: "Claude", id: "7c5dcf5d", kind: "background", title: "Update the API docs", prompt: "",
  folder: "/Users/dev/lumen-api", place: "lumen-api", group: "Today", day: "Today", time: "14:02", took: "6 min",
  state: "done", said: "done", made: "2 files", files: [], media: [], pr: null, cost: "~$0.31", cost_line: "",
  ran_as: "Background session · Claude · Opus 5.5", now: null, ...more });
const ids = (/** @type {[string, string, string][]} */ found) => found.map(([id]) => id);

test("a space's scope shows the runs in its folder, a cloud task by its environment's name", () => {
  const cloud = run({ agent: "codex", kind: "cloud", folder: "", place: "lumen-api" });
  assert.ok(runShown(run({}), null, null));
  assert.ok(runShown(run({ folder: "/Users/dev/lumen-api/docs" }), "/Users/dev/lumen-api", "claude"));
  assert.ok(!runShown(run({ folder: "/Users/dev/lumen-api-old" }), "/Users/dev/lumen-api", null));
  assert.ok(runShown(cloud, "/Users/dev/lumen-api", "codex"));
  assert.ok(!runShown(cloud, "/Users/dev/harbor-web", null));
  assert.ok(!runShown(run({}), null, "codex"));
});

test("a run's buttons: Attach and Stop while it works, Open as chat and Run again once done, a cloud task's", () => {
  assert.deepEqual(ids(runActions(run({ state: "running" }), "lumen-api")), ["attach", "stop"]);
  assert.deepEqual(ids(runActions(run({ state: "blocked" }), "lumen-api")), ["attach", "stop"]);
  assert.deepEqual(ids(runActions(run({}), "lumen-api")), ["chat", "again", "remove"]);
  assert.deepEqual(ids(runActions(run({ kind: "exec", agent: "codex", state: "running" }), "lumen-api")), []);
  assert.deepEqual(ids(runActions(run({ kind: "exec", agent: "codex", pr: { number: 61, url: "u" } }), "lumen-api")),
    ["chat", "again", "pr"]);
  const cloud = run({ kind: "cloud", agent: "codex", state: "ready", url: "https://codex.example/tasks/t" });
  assert.deepEqual(runActions(cloud, "lumen-api"), [["diff", "Show diff", "raised"],
    ["apply", "Apply to lumen-api", "raised"], ["web", "Open on the web", "plain"]]);
  assert.deepEqual(ids(runActions({ ...cloud, state: "applied" }, "lumen-api")), ["diff", "web"]);
  assert.deepEqual(ids(runActions({ ...cloud, state: "failed" }, "lumen-api")), ["again", "web"]);
});

test("New run says what starts where: Claude's schedule is its own /schedule, Codex's its app's", () => {
  const form = { agent: "claude", where: "here", when: "now", env: null, busy: false, note: null };
  assert.match(formNote(form, "lumen-api"), /in the background; Attach/);
  assert.match(formNote({ ...form, when: "schedule" }, "lumen-api"), /\/schedule and your words/);
  assert.equal(formNote({ ...form, agent: "codex", when: "schedule" }, "lumen-api"),
    "Codex schedules only in its own app.");
  assert.equal(formNote({ ...form, agent: "codex", where: "cloud" }, "lumen-api"),
    "Codex makes a diff in the cloud; Apply brings it into lumen-api.");
  assert.match(formNote({ ...form, agent: "codex" }, "lumen-api"), /codex exec/);
});

test("the status bar counts the runs working", () => {
  assert.deepEqual([1, 2].map(runsWorking), ["1 run working", "2 runs working"]);
});
