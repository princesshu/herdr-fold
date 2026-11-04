// @ts-check
// Tests for the mod's logic that needs no window: node --test app/tests (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterCommit, background, changedFiles, commitMode, commitRows, diffRows, excerpt, marked, MODES, panelToggle,
  pythonCommand, rowActions, searchRows, searchSummary, secretQuestion, syncLabel, written }
  from "../mods/herdr-fold/logic.js";

test("a diff's lines numbered once, old and new apart", () => {
  const rows = diffRows(["@@ -3,2 +3,3 @@", " same", "-old", "+new", "+more"]);
  assert.deepEqual(rows.map((r) => [r.kind, r.number ?? null]), [["@", null], [" ", 3], ["-", 4], ["+", 4], ["+", 5]]);
});

test("a commit's diff: its header as it is, each file's name a heading, its hunks numbered, its own lines left out",
  () => {
    const rows = commitRows(["abc1234  dev  2 days ago", "", "fix: two files", "",
      "diff --git a/a.txt b/a.txt", "index 1..2 100644", "--- a/a.txt", "+++ b/a.txt", "@@ -1 +1 @@", "-1", "+2",
      "diff --git a/new.png b/new.png", "new file mode 100644", "Binary files /dev/null and b/new.png differ", ""]
      .join("\n"));
    assert.deepEqual(rows.map((r) => [r.kind, r.number ?? null, r.text]), [
      ["", null, "abc1234  dev  2 days ago"], ["", null, ""], ["", null, "fix: two files"], ["", null, ""],
      ["@", null, "a.txt"], ["@", null, "@@ -1 +1 @@"], ["-", 1, "1"], ["+", 1, "2"],
      ["@", null, "new.png"], ["", null, "Binary files /dev/null and b/new.png differ"]]);
  });

test("the search's hits under a row for their file, in the order they came, each file counted", () => {
  const hit = (path, line) => ({ path, line, text: "x", spans: [[0, 1]] });
  const rows = searchRows([hit("a.py", 3), hit("a.py", 9), hit("b/c.py", 1)]);
  assert.deepEqual(rows.map((r) => [r.kind, r.path, r.line ?? r.count]),
    [["file", "a.py", 2], ["hit", "a.py", 3], ["hit", "a.py", 9], ["file", "b/c.py", 1], ["hit", "b/c.py", 1]]);
});

test("a line in pieces, the matches marked: as the TUI sidebar marks them", () => {
  assert.deepEqual(marked("const hero = hero", [[6, 10], [13, 17]]), [{ text: "const ", hit: false },
    { text: "hero", hit: true }, { text: " = ", hit: false }, { text: "hero", hit: true }]);
  assert.deepEqual(marked("plain", []), [{ text: "plain", hit: false }]);
});

test("a file's lines round a hit: a few before it, numbered from where they start", () => {
  const text = Array.from({ length: 40 }, (_, i) => `line ${i + 1}`).join("\n") + "\n";
  const { start, lines } = excerpt(text, 20, 5, 10);
  assert.equal(start, 15);
  assert.deepEqual([lines[0], lines.at(-1), lines.length], ["line 15", "line 24", 10]);
  assert.equal(excerpt(text, 2, 5, 10).start, 1);                  // never before the first line
  assert.equal(excerpt("a\r\nb\n", 1, 5, 10).lines[0], "a");      // a line ends at its newline, \r and all
});

test("the search's summary, in the TUI sidebar's words", () => {
  assert.equal(searchSummary({ total: 7, files: 1, hits: new Array(7), error: null }), "7 results in 1 file");
  assert.equal(searchSummary({ total: 1, files: 1, hits: new Array(1), error: null }), "1 result in 1 file");
  assert.equal(searchSummary({ total: 1500, files: 30, hits: new Array(1000), error: null }),
    "1000 of 1500 results shown");
  assert.equal(searchSummary({ total: 0, files: 0, hits: [], error: null }), "No results found");
  assert.equal(searchSummary({ total: 0, files: 0, hits: [], error: "invalid regex: x" }), "invalid regex: x");
});

test("each changed file once, staged or not, in the order git gives them", () => {
  const status = { staged: [{ path: "b.txt", code: "A" }, { path: "a.txt", code: "M" }],
    changes: [{ path: "a.txt", code: "M" }, { path: "new.txt", code: "?" }] };
  assert.deepEqual(changedFiles(status), [{ path: "b.txt", code: "A" }, { path: "a.txt", code: "M" },
    { path: "new.txt", code: "?" }]);
});

test("a row's buttons, as the TUI sidebar's: a staged file unstages, a change stages and discards", () => {
  assert.deepEqual(rowActions("staged", "M"), ["unstage"]);
  assert.deepEqual(rowActions("changes", "M"), ["discard", "stage"]);
  assert.deepEqual(rowActions("changes", "D"), ["discard", "stage"]);
  assert.deepEqual(rowActions("changes", "?"), ["discard", "stage"]); // a new file: to the Trash, never deleted
  assert.deepEqual(rowActions("changes", "U"), ["stage"]);           // a conflict is settled, not undone
});

test("the commit modes, named as in the TUI sidebar, and what follows each commit", () => {
  assert.deepEqual(Object.values(MODES), ["Commit", "Commit & Push", "Commit & Sync"]);
  assert.equal(commitMode("push"), "push");
  assert.equal(commitMode(undefined), "commit");                    // nothing kept yet, or something else kept
  assert.equal(commitMode("rm -rf"), "commit");
  assert.deepEqual(["commit", "push", "sync"].map(afterCommit), [null, "push", "sync"]);
});

test("the sync button says how far the branch is from its upstream, as the TUI sidebar does", () => {
  assert.equal(syncLabel({ upstream: "origin/main", ahead: 2, behind: 1 }), "↻ 1↓ 2↑");
  assert.equal(syncLabel({ upstream: null, ahead: 0, behind: 0 }), "↻");
  assert.equal(syncLabel(null), "↻");
});

/** @param {string[]} argv @param {string} [cwd] */
function run(argv, cwd) {
  const out = spawnSync(argv[0], argv.slice(1), { encoding: "utf8", cwd });
  return { code: out.status, stdout: out.stdout, stderr: out.stderr };
}

/** The job's poll until it no longer answers 3, five seconds at most.
 * @param {ReturnType<typeof background>} job
 * @param {string} folder */
function finished(job, folder) {
  let done = run(job.poll(folder));
  for (let i = 0; i < 50 && done.code === 3; i++) {
    run(["sleep", "0.1"]);
    done = run(job.poll(folder));
  }
  return done;
}

/** The job prepared, then run as the core's terminal would run it (what comes after hc's --): its folder.
 * @param {ReturnType<typeof background>} job @param {string} [cwd] */
function started(job, cwd) {
  const folder = run(job.prepare, cwd).stdout.trim(), argv = job.start(folder, cwd ?? ".", null);
  const terminal = argv.slice(argv.indexOf("--") + 1);
  spawn(terminal[0], terminal.slice(1), { cwd, detached: true, stdio: "ignore" }).unref();
  return folder;
}

test("a job's terminal: in the background, of no parent, gone once it ends, where the repository is", () => {
  const job = background("python3", "print(1)", ["write", "/srv/app"]), start = job.start("/tmp/f", "/srv/app", "box");
  assert.deepEqual(start.slice(0, start.indexOf("--")),
    ["run", "--bg", "--json", "--no-parent", "--rm", "--on", "box", "--cwd", "/srv/app"]);
  assert.deepEqual(start.slice(-5), ["run", "/tmp/f", "600", "write", "/srv/app"]);
  assert.equal(job.start("/tmp/f", "/srv/app", null).includes("--on"), false);         // this machine's own core
});

test("a long job runs in the background, answers 3 until done, then its output; clear removes its folder", () => {
  const job = background("python3", "import sys, time; time.sleep(0.3); print(sys.argv[1])", ["/srv/app"]);
  const folder = started(job);
  assert.match(folder, /[/\\]herdr-fold\.[A-Za-z0-9_]+$/);
  assert.equal(run(job.poll(folder)).code, 3);
  const done = finished(job, folder);
  assert.deepEqual([done.code, done.stdout], [0, "/srv/app\n"]);
  run(job.clear(folder));
  assert.equal(existsSync(folder), false);
});

test("a failed job answers 4 with its error's last lines; clear removes only a job's folder", () => {
  const job = background("python3", "raise SystemExit('broken here')", []);
  const folder = started(job);
  const done = finished(job, folder);
  assert.deepEqual([done.code, done.stderr.trim()], [4, "broken here"]);
  run(job.clear(folder));
  const other = mkdtempSync(join(tmpdir(), "other-"));
  run(job.clear(other));
  assert.equal(existsSync(other), true);
  rmSync(other, { recursive: true });
});

test("a job's folder removes itself a while after the job ends, should the mod be gone and never clear it", () => {
  const job = background("python3", "print(1)", [], 1), folder = started(job);
  assert.equal(finished(job, folder).code, 0);
  run(["sleep", "1.5"]);
  assert.equal(existsSync(folder), false);
});

test("the helpers run in the repository's folder but never import a module it holds (a json.py) for Python's", () => {
  const repo = mkdtempSync(join(tmpdir(), "repo-")), mark = join(repo, "ran");
  writeFileSync(join(repo, "json.py"), `open(${JSON.stringify(mark)}, "w")\n`);
  const source = "import json; print(json.dumps(1))";
  assert.equal(run([...pythonCommand("python3"), source], repo).stdout, "1\n");
  const job = background("python3", source, []), folder = started(job, repo), done = finished(job, folder);
  assert.deepEqual([done.code, done.stdout], [0, "1\n"]);
  run(job.clear(folder));
  assert.equal(existsSync(mark), false);
  rmSync(repo, { recursive: true });
});

test("the writer's answer: a message to fill in, a warning for files named like secrets, or why there is none", () => {
  assert.deepEqual(written({ message: "feat: a", secret_looking: [], note: null }), { message: "feat: a", note: null });
  assert.deepEqual(written({ message: "feat: a", secret_looking: [".env"], note: null }),
    { message: "feat: a", note: "Staged, named like a secret: .env" });
  assert.deepEqual(written({ message: null, secret_looking: [], note: "claude is not installed", files: ["a"] }),
    { message: null, note: "No message: claude is not installed" });
  assert.deepEqual(written({ message: null, secret_looking: [], note: "", files: [] }),
    { message: null, note: "Nothing to commit" });
});

test("files named like secrets are asked about before a commit, in the TUI sidebar's words", () => {
  assert.equal(secretQuestion([]), null);
  assert.equal(secretQuestion(["deploy/.env"]), ".env looks like a secret. Commit it anyway?");
  assert.equal(secretQuestion(["a.key", "b.key", "c.key", "d.key", "e.key"]),
    "a.key, b.key, c.key and 2 more look like secrets. Commit them anyway?");
});

test("Cmd+Shift+G shows the right panel at herdr-fold, as the Changes button does, or hides it from there", () => {
  /** @param {boolean} hidden @param {string} active */
  const tree = (hidden, active) => ({ id: "root", children: [{ id: "work", children: [{ id: "panel", hidden,
    children: [{ id: "panel-body", type: "stack", active, children: [{ id: "files" }, { id: "changes" }] }] }] }] });
  const show = [["layout.select", { stack: "panel-body", child: "changes" }], ["layout.show", { id: "panel" }]];
  assert.deepEqual(panelToggle(tree(true, "changes")), show);
  assert.deepEqual(panelToggle(tree(false, "files")), show);
  assert.deepEqual(panelToggle(tree(false, "changes")), [["layout.hide", { id: "panel" }]]);
});
