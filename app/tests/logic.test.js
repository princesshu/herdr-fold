// @ts-check
// Tests for the mod's logic that needs no window: node --test app/tests (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PYTHON, background, changedFiles, diffRows, secretQuestion, syncLabel, written }
  from "../mods/herdr-fold/logic.js";

test("a diff's lines numbered once, old and new apart", () => {
  const rows = diffRows(["@@ -3,2 +3,3 @@", " same", "-old", "+new", "+more"]);
  assert.deepEqual(rows.map((r) => [r.kind, r.number ?? null]), [["@", null], [" ", 3], ["-", 4], ["+", 4], ["+", 5]]);
});

test("each changed file once, staged or not, in the order git gives them", () => {
  const status = { staged: [{ path: "b.txt", code: "A" }, { path: "a.txt", code: "M" }],
    changes: [{ path: "a.txt", code: "M" }, { path: "new.txt", code: "?" }] };
  assert.deepEqual(changedFiles(status), [{ path: "b.txt", code: "A" }, { path: "a.txt", code: "M" },
    { path: "new.txt", code: "?" }]);
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

test("a long job runs in the background, answers 3 until done, then its output; clear removes its folder", () => {
  const job = background("import sys, time; time.sleep(0.3); print(sys.argv[1])", ["/srv/app"]);
  const folder = run(job.start).stdout.trim();
  assert.match(folder, /\/herdr-fold\.[A-Za-z0-9]+$/);
  assert.equal(run(job.poll(folder)).code, 3);
  const done = finished(job, folder);
  assert.deepEqual([done.code, done.stdout], [0, "/srv/app\n"]);
  run(job.clear(folder));
  assert.equal(existsSync(folder), false);
});

test("a failed job answers 4 with its error's last lines; clear removes only a job's folder", () => {
  const job = background("raise SystemExit('broken here')", []);
  const folder = run(job.start).stdout.trim();
  const done = finished(job, folder);
  assert.deepEqual([done.code, done.stderr.trim()], [4, "broken here"]);
  run(job.clear(folder));
  const other = mkdtempSync(join(tmpdir(), "other-"));
  run(job.clear(other));
  assert.equal(existsSync(other), true);
  rmSync(other, { recursive: true });
});

test("a job's folder removes itself a while after the job ends, should the mod be gone and never clear it", () => {
  const job = background("print(1)", [], 1), folder = run(job.start).stdout.trim();
  assert.equal(finished(job, folder).code, 0);
  run(["sleep", "1.5"]);
  assert.equal(existsSync(folder), false);
});

test("the helpers run in the repository's folder but never import a module it holds (a json.py) for Python's", () => {
  const repo = mkdtempSync(join(tmpdir(), "repo-")), mark = join(repo, "ran");
  writeFileSync(join(repo, "json.py"), `open(${JSON.stringify(mark)}, "w")\n`);
  const source = "import json; print(json.dumps(1))";
  assert.equal(run([...PYTHON, source], repo).stdout, "1\n");
  const job = background(source, []), folder = run(job.start, repo).stdout.trim(), done = finished(job, folder);
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
