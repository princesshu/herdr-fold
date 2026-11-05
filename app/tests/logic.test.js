// @ts-check
// Tests for the mod's logic that needs no window: node --test app/tests (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterCommit, background, commitMode, commitRows, diffRows, excerpt, foldedSections, folderName, issueAgent,
  lastLine, letter, machineOf, marked, marks, MODES, nerdFont, panelToggle, previewName, previewTab, priorityColor,
  pythonCommand, rowActions, safeMarkdown, said, searchRows, searchSummary, secretQuestion, strays, syncLabel,
  TERMINALS, terminalId, withoutTabs, withTerminal, written } from "../mods/herdr-fold/logic.js";

test("a diff's lines numbered once, old and new apart; no hunk header, a gap between two hunks", () => {
  const rows = diffRows(["@@ -3,2 +3,3 @@ def index():", " same", "-old", "+new", "+more", "@@ -20 +21 @@", "-x",
    "+y"]);
  assert.deepEqual(rows.map((r) => [r.kind, r.number ?? null]),
    [[" ", 3], ["-", 4], ["+", 4], ["+", 5], ["gap", null], ["-", 20], ["+", 21]]);
});

test("a commit's diff: its header as it is, each file's name a heading, its hunks numbered, its own lines left out",
  () => {
    const rows = commitRows(["abc1234  dev  2 days ago", "", "fix: two files", "",
      "diff --git a/a.txt b/a.txt", "index 1..2 100644", "--- a/a.txt", "+++ b/a.txt", "@@ -1 +1 @@", "-1", "+2",
      "diff --git a/new.png b/new.png", "new file mode 100644", "Binary files /dev/null and b/new.png differ", ""]
      .join("\n"));
    assert.deepEqual(rows.map((r) => [r.kind, r.number ?? null, r.text]), [
      ["", null, "abc1234  dev  2 days ago"], ["", null, ""], ["", null, "fix: two files"], ["", null, ""],
      ["@", null, "a.txt"], ["-", 1, "1"], ["+", 1, "2"],
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

/** A layout as herdr-fold's has it: the panel, its views above, its tabs' terminals below (the stand-in first). */
const tree = () => ({ id: "root", children: [{ id: "panel", children: [{ id: "panel-body", children: [] },
  { id: TERMINALS, active: "fold-terminal-none",
    children: [{ id: "fold-terminal-none", content: { mod: "x" } }] }] }] });

test("a tab's terminal in the panel's stack: added once, its address kept up to date", () => {
  const first = withTerminal(tree(), "tb42", "lab/t7");
  assert.equal(first.changed, true);
  const stack = first.tree.children[0].children[1];
  assert.deepEqual(stack.children.map((c) => c.id), ["fold-terminal-none", terminalId("tb42")]);
  assert.deepEqual(stack.children[1], { id: terminalId("tb42"), type: "block", content: { terminal: "lab/t7" } });
  assert.equal(withTerminal(first.tree, "tb42", "lab/t7").changed, false);       // nothing to write again
  const moved = withTerminal(first.tree, "tb42", "lab/t9");
  assert.equal(moved.changed, true);
  assert.deepEqual(moved.tree.children[0].children[1].children[1].content, { terminal: "lab/t9" });
});

test("the terminals of tabs that are gone come out of the stack; the stand-in and the live ones stay", () => {
  const two = withTerminal(withTerminal(tree(), "tb1", "t1").tree, "tb2", "t2").tree;
  const { tree: left, gone } = withoutTabs(two, ["tb2"], new Set([null]));
  assert.deepEqual(gone, [terminalId("tb1")]);
  assert.deepEqual(left.children[0].children[1].children.map((c) => c.id), ["fold-terminal-none", terminalId("tb2")]);
  assert.deepEqual(withoutTabs(left, ["tb2"], new Set([null])).gone, []);
});

test("a terminal on a machine away stays, its tabs not listed meanwhile; it goes once the machine is back", () => {
  const away = withTerminal(withTerminal(tree(), "lab/tb1", "lab/t1").tree, "tb2", "t2").tree;
  assert.deepEqual(withoutTabs(away, ["tb2"], new Set([null])).gone, []);
  assert.deepEqual(withoutTabs(away, ["tb2"], new Set([null, "lab"])).gone, [terminalId("lab/tb1")]);
});

test("a second terminal started for a tab ends while the one its block shows is live, not while that one is gone",
  () => {
    const shown = withTerminal(tree(), "tb1", "t2").tree;
    const one = (address, live) => ({ address, tab: "tb1", live });
    assert.deepEqual(strays(shown, [one("t1", true), one("t2", true), one("t0", false)]), ["t1"]);
    assert.deepEqual(strays(shown, [one("t1", true), one("t2", false)]), []);       // t1 may be the one replacing it
    assert.deepEqual(strays(tree(), [one("t1", true)]), []);                        // no block yet: it is coming
  });

test("what a failed program said: its error's last line, else its output's, else its exit code", () => {
  assert.equal(lastLine({ code: 1, stdout: "out\n", stderr: "warning\nno machine: lab\n" }), "no machine: lab");
  assert.equal(lastLine({ code: 2, stdout: "first\nlast\n", stderr: "" }), "last");
  assert.equal(lastLine({ code: 3, stdout: "", stderr: "  \n" }), "exit 3");
  assert.equal(said(new Error("gone")), "gone");
  assert.equal(said("plain"), "plain");
});

test("the icons: the TUI's Nerd Font glyphs with such a font installed, a one-cell Mono one first; else its marks",
  () => {
    assert.equal(nerdFont(["Menlo", "JetBrainsMono Nerd Font", "JetBrainsMono Nerd Font Mono"]),
      "JetBrainsMono Nerd Font Mono");
    assert.equal(nerdFont(["Hack Nerd Font", "Symbols Nerd Font Mono", "Hack Nerd Font Mono"]),
      "Symbols Nerd Font Mono");
    assert.equal(nerdFont(["Menlo", "JetBrains Mono"]), null);
    assert.equal(marks("JetBrainsMono Nerd Font Mono").stage, "\uea60");
    assert.equal(marks(null).stage, "+");
  });

test("a terminal's machine from its address: the name before the slash, none on this computer", () => {
  assert.equal(machineOf("lab/t7"), "lab");
  assert.equal(machineOf("t7"), null);
});

test("a terminal's folder as the app's pane header names it: under the home folder from ~", () => {
  assert.equal(folderName("/Users/dev/work/api", "/Users/dev"), "~/work/api");
  assert.equal(folderName("/Users/dev", "/Users/dev"), "~");
  assert.equal(folderName("/Users/a_b/x", "/Users/a"), "/Users/a_b/x");
  assert.equal(folderName("/srv/api", null), "/srv/api");
  assert.equal(folderName(null, "/Users/dev"), "");
});

test("a tab's id makes a layout id of letters, digits and dashes only", () => {
  assert.equal(terminalId("tb4223ef"), "fold-terminal-tb4223ef");
  assert.match(terminalId("lab/tb 1:x"), /^fold-terminal-[a-z0-9-]+$/);
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

test("the sync button says how far the branch is from its upstream, as the TUI sidebar does (after its icon)", () => {
  assert.equal(syncLabel({ upstream: "origin/main", ahead: 2, behind: 1 }), "1↓ 2↑");
  assert.equal(syncLabel({ upstream: null, ahead: 0, behind: 0 }), "");
  assert.equal(syncLabel(null), "");
});

test("the folded sections as kept, as the TUI sidebar keeps them: staged, changes, graph; nothing else", () => {
  assert.deepEqual([...foldedSections(["graph", "staged", "x", 3])], ["graph", "staged"]);
  assert.deepEqual([...foldedSections(true)], []);
  assert.deepEqual([...foldedSections(undefined)], []);
});

test("an issue's text has no image to fetch and no HTML, in code or not, and reads as written", () => {
  // what a parser may take as code where a filter would not (an escaped or unmatched backtick, an open fence)
  const written = ['See ![shot](https://x.example/a.png "t") here', "![](https://x.example/p.gif)",
    "![logo][1]\n\n[1]: https://x.example/l.png", "![logo]\n\n[logo]: https://x.example/l.png",
    "![a [b] c](https://x.example/n.png)", "\\`![x](https://x.example/e.png)\\`", "`![x](https://x.example/u.png)``",
    "text ```![x](https://x.example/f.png)", '<img src="https://x.example/t.gif"> <b>hi</b>', "<IMG SRC=x>",
    "</b><!-- c --><?x?>", "\\`<img src=x>\\`", "```html\n<img src=x>\n```", "use `<div>` here"];
  for (const markdown of written) {
    const safe = safeMarkdown(markdown);
    assert.doesNotMatch(safe, /!\[|<[A-Za-z/!?]/, markdown);
    assert.equal(safe.replaceAll("\u2060", ""), markdown);
  }
  const plain = "a < b, x <3, see [docs](https://x.example)";
  assert.equal(safeMarkdown(plain), plain);
});

test("an issue goes to the focused tab's own Claude or Codex, not another tab's nor another program", () => {
  const agents = [{ tab: "t1", address: "t3", program: { key: "claude" } },
    { tab: "t2", address: "t4", program: { key: "codex" } }, { tab: "t2", address: "t5", program: { key: "pi" } }];
  assert.equal(issueAgent(agents, "t1")?.address, "t3");
  assert.equal(issueAgent(agents, "t2")?.address, "t4");
  assert.equal(issueAgent(agents, "t9"), null);
});

test("the preview tab named as the TUI sidebar names it: the file, the commit, the issue's number and title's start",
  () => {
    const at = { root: "/r", on: null };
    assert.equal(previewName({ ...at, kind: "diff", path: "src/app.py" }), "preview: src/app.py");
    assert.equal(previewName({ ...at, kind: "commit", hash: "abc1234" }), "preview: abc1234");
    assert.equal(previewName({ ...at, kind: "issue", github: "o/r", number: 42, title: "Login fails" }),
      "preview: #42 Login fails");
    assert.equal(previewName({ ...at, kind: "issue", github: "o/r", number: 7, title: "Pagination returns an empty" }),
      "preview: #7 Pagination returns…");
  });

test("a priority's color as the TUI sidebar's traffic light: urgent and high red, medium yellow, low green", () => {
  const t = { ansi1: "red", blocked: "yellow", ansi2: "green", accent: "accent" };
  assert.deepEqual([0, 1, 2, 3, null, undefined].map((level) => priorityColor(t, level)),
    ["red", "red", "yellow", "green", "accent", "accent"]);
});

test("a space's preview tab: named as one, herdr-fold its pane; another tab so named is not it", () => {
  const space = { tabs: [{ id: "t1", name: "1" }, { id: "t2", name: "preview: notes" },
    { id: "t3", name: "preview: a" }] };
  const panes = [{ tab: "t1", mod: undefined }, { tab: "t2", mod: undefined }, { tab: "t3", mod: "herdr-fold" }];
  assert.equal(previewTab(space, panes)?.id, "t3");
  assert.equal(previewTab(space, panes.slice(0, 2)), null);
  assert.equal(previewTab(undefined, panes), null);
});

test("a change's letter as the TUI sidebar shows it: an untracked file U, a conflict !", () => {
  assert.deepEqual(["?", "U", "M", "A", "D"].map(letter), ["U", "!", "M", "A", "D"]);
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
