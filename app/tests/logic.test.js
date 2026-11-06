// @ts-check
// Tests for the mod's logic that needs no window: node --test in app/ (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterCommit, background, branchLabel, changeColor, changeName, commitMode, commitRows, conversationChoices,
  conversationRows, coreAgents, diffRows, excerpt, fileRows, floatHeight, folderIcon, foldedSections, foldedWidth,
  folderSpaces, issueAgent, lastLine, launcher, letter, machineOf, marked, MODES, PANEL, PANEL_BODY, panelShown,
  panelToggle, previewName, previewTab, priorityColor, pushOffer, pythonCommand, railed, resumeArgv, rowActions,
  safeMarkdown, said, searchRows, searchSummary, secretQuestion, shownTab, strays, syncLabel, tabLabel, TALL,
  terminalId, TERMINALS, urgent, withMax, withoutTabs, withTerminal, written, waited, nextWaits, toggleUnread,
  spaceWaits, placeLabel, nested, spaceColors, avatarFill, MARK, listBody, listHeight, panelRailed, railFollow,
  railToggle, RAIL, RAIL_BLOCK, PANEL_PX, activeTerminal, hovering }
  from "../mods/herdr-fold/logic.js";

test("a row hovered: its key while the pointer is over it, let go only by its own leaving", () => {
  const holder = { hovered: null }, drawn = [], cx = { notify: () => drawn.push(holder.hovered) };
  hovering(holder, "a")(true, cx);
  hovering(holder, "b")(true, cx);
  hovering(holder, "a")(false, cx);
  assert.equal(holder.hovered, "b");
  hovering(holder, "b")(false, cx);
  assert.deepEqual(drawn, ["a", "b", "b", null]);
});

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
const tree = () => ({ id: "root", children: [{ id: PANEL, children: [{ id: PANEL_BODY, children: [] },
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

test("the tab's terminal the stack shows, for the rail's float: none while the stand-in shows", () => {
  const two = withTerminal(tree(), "tb1", "lab/t1").tree;
  assert.equal(activeTerminal(two), null);
  two.children[0].children[1].active = terminalId("tb1");
  assert.equal(activeTerminal(two), "lab/t1");
  assert.equal(activeTerminal({ id: "root" }), null);
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

test("a terminal's machine from its address: the name before the slash, none on this computer", () => {
  assert.equal(machineOf("lab/t7"), "lab");
  assert.equal(machineOf("t7"), null);
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

test("the sync button says how far the branch is from its upstream, as VS Code's (its icon alone when even)", () => {
  assert.equal(syncLabel({ upstream: "origin/main", ahead: 2, behind: 1 }), "1↓ 2↑");
  assert.equal(syncLabel({ upstream: "origin/main", ahead: 0, behind: 0 }), "");
  assert.equal(syncLabel({ upstream: null, ahead: 0, behind: 0 }), "");
  assert.equal(syncLabel(null), "");
});

test("nothing to commit with commits ahead offers their push, as the TUI's Cmd + Shift + C does", () => {
  const status = { staged: [], changes: [], upstream: "origin/main", ahead: 2, behind: 0 };
  assert.equal(pushOffer(status), "Nothing to commit. Push 2 commits?");
  assert.equal(pushOffer({ ...status, ahead: 1 }), "Nothing to commit. Push 1 commit?");
  assert.equal(pushOffer({ ...status, ahead: 0 }), null);
  assert.equal(pushOffer({ ...status, upstream: null }), null);
  assert.equal(pushOffer({ ...status, changes: [{ path: "a.txt", code: "M" }] }), null);
  assert.equal(pushOffer(null), null);
});

test("the repository row's branch, as the TUI's footer names it: * with changes, detached without one", () => {
  const status = (branch, staged, changes) => ({ branch, staged: Array(staged).fill({}),
    changes: Array(changes).fill({}) });
  assert.equal(branchLabel(status("main", 0, 0)), "main");
  assert.equal(branchLabel(status("main", 1, 0)), "main*");
  assert.equal(branchLabel(status(null, 0, 2)), "detached*");
  assert.equal(branchLabel(null), "");
});

test("the folded sections as kept, as the TUI sidebar keeps them: staged, changes, graph; nothing else", () => {
  assert.deepEqual([...foldedSections(["graph", "staged", "x", 3, "repositories"])],
    ["graph", "staged", "repositories"]);
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
    assert.equal(previewName({ ...at, kind: "file", path: "README.md" }), "preview: README.md");
    assert.equal(previewName({ ...at, kind: "issue", github: "o/r", number: 42, title: "Login fails" }),
      "preview: #42 Login fails");
    assert.equal(previewName({ ...at, kind: "issue", github: "o/r", number: 7, title: "Pagination returns an empty" }),
      "preview: #7 Pagination returns…");
  });

test("a change's color, as the TUI's: new green, deleted or in conflict red, any other change yellow", () => {
  const t = { ansi1: "red", ansi2: "green", ansi3: "yellow" };
  assert.deepEqual(["A", "?", "D", "U", "M", "R"].map((code) => changeColor(t, code)),
    ["green", "green", "red", "red", "yellow", "yellow"]);
});

test("a folder's icon, Catppuccin Icons' closed or open", () => {
  assert.equal(folderIcon(false), "mods/herdr-fold/icons/catppuccin/folder.svg");
  assert.equal(folderIcon(true), "mods/herdr-fold/icons/catppuccin/folder-open.svg");
});

test("the Files tree's rows as the TUI's: an open folder's entries under it, a very full one's count of the rest last",
  () => {
    const entry = (name, dir = false, mark = null) => ({ name, dir, mark, ignored: false });
    const folders = { "": { entries: [entry("src", true, "M"), entry("a.txt")], more: 0 },
      src: { entries: [entry("app.py", false, "M")], more: 2 } };
    assert.deepEqual(fileRows(folders, new Set()).map((r) => r.path), ["src", "a.txt"]);
    const open = fileRows(folders, new Set(["src"]));
    assert.deepEqual(open.map((r) => [r.path, r.depth]), [["src", 0], ["src/app.py", 1], [null, 1], ["a.txt", 0]]);
    assert.equal(open[0].open, true);
    assert.equal(open[2].more, 2);
    assert.deepEqual(fileRows({ "": folders[""] }, new Set(["src"])).map((r) => r.path), ["src", "a.txt"]);
    assert.deepEqual(fileRows({}, new Set()), []);
  });

test("a priority's color as the TUI sidebar's traffic light: urgent and high red, medium yellow, low green", () => {
  const t = { ansi1: "red", ansi3: "yellow", ansi2: "green", blocked: "red", accent: "accent" };
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

test("Cmd+Shift+G opens the right panel at Changes, or folds it to its rail from there", () => {
  /** @param {boolean} hidden @param {string} active @param {number} [px] */
  const tree = (hidden, active, px = PANEL_PX) => ({ id: "root", children: [{ id: "work", children: [{ id: PANEL,
    hidden, size: { px }, children: [{ id: PANEL_BODY, type: "stack", active, children: [{ id: "files" },
      { id: "changes" }] }] }] }] });
  const select = ["layout.select", { stack: PANEL_BODY, child: "changes" }];
  assert.deepEqual(panelToggle(tree(true, "changes"), undefined),
    [select, ["layout.show", { id: PANEL }], ["layout.resize", { id: PANEL, px: PANEL_PX }]]);
  assert.deepEqual(panelToggle(tree(false, "files"), undefined), [select]);
  assert.deepEqual(panelToggle(tree(false, "changes"), undefined),
    [["layout.resize", { id: PANEL, px: RAIL }], ["layout.hide", { id: PANEL_BODY }]]);
  assert.deepEqual(panelToggle(tree(false, "changes", RAIL), 400), [select, ["layout.resize", { id: PANEL, px: 400 }]]);
  assert.deepEqual([PANEL, PANEL_BODY], ["fold-panel", "fold-panel-body"]);     // not the app's: its tab bar keeps out
  assert.equal(panelShown(tree(false, "files")), true);
  assert.equal(panelShown(tree(true, "changes")), false);
  assert.equal(panelShown({ id: "root" }), false);
});

test("the right panel folds to its rail and opens again, as its toggle and a drag do it", () => {
  /** @param {number} px @param {{ hidden?: boolean, rail?: boolean }} [shown] */
  const tree = (px, { hidden = false, rail = false } = {}) => ({ id: "root", children: [{ id: PANEL, hidden,
    size: { px }, children: [{ id: PANEL_BODY, hidden: rail }, { id: TERMINALS, hidden: rail },
      { id: RAIL_BLOCK, hidden: !rail }] }] });
  /** @param {boolean} open */
  const blocks = (open) => [[open ? "layout.show" : "layout.hide", { id: PANEL_BODY }],
    [open ? "layout.show" : "layout.hide", { id: TERMINALS }],
    [open ? "layout.hide" : "layout.show", { id: RAIL_BLOCK }]];
  assert.equal(panelRailed(tree(RAIL, { rail: true })), true);
  assert.equal(panelRailed(tree(PANEL_PX)), false);
  assert.deepEqual(railToggle(tree(420), 368), [["layout.resize", { id: PANEL, px: RAIL }], ...blocks(false)]);
  assert.deepEqual(railToggle(tree(RAIL, { rail: true }), 420), [["layout.resize", { id: PANEL, px: 420 }],
    ...blocks(true)]);
  assert.deepEqual(railToggle(tree(RAIL, { rail: true }), undefined)[0],
    ["layout.resize", { id: PANEL, px: PANEL_PX }]);
  assert.deepEqual(railToggle(tree(420, { hidden: true }), 368), [["layout.show", { id: PANEL }],
    ["layout.resize", { id: PANEL, px: 420 }]]);
  // dragged narrow: the rail, at its own width; dragged wide again: the stacks; hidden: nothing
  assert.deepEqual(railFollow(tree(120)), [...blocks(false), ["layout.resize", { id: PANEL, px: RAIL }]]);
  assert.deepEqual(railFollow(tree(300, { rail: true })), blocks(true));
  assert.deepEqual(railFollow(tree(RAIL, { rail: true })), []);
  assert.deepEqual(railFollow(tree(120, { hidden: true })), []);
});

test("the right panel's tab shown: Files while the app's Files shows, else the view kept, Issues on GitHub", () => {
  const tree = (active) => ({ id: "root", children: [{ id: PANEL, children: [{ id: PANEL_BODY, active }] }] });
  assert.equal(shownTab(tree("files"), "search", true), "files");
  assert.equal(shownTab(tree("changes"), "search", true), "search");
  assert.equal(shownTab(tree("changes"), "issues", true), "issues");
  assert.equal(shownTab(tree("changes"), "issues", false), "changes");
  assert.equal(shownTab(tree("changes"), null, false), "changes");
  assert.equal(shownTab(tree("changes"), "bogus", true), "changes");
});

test("a floating panel as tall as its content, up to TALL: Spaces' rows, Conversations' groups and open ones", () => {
  assert.equal(floatHeight("spaces", 2), 36 + 2 * 29 + 8);
  const group = (open, n) => ({ kind: "group", open, items: Array(n).fill({}) });
  assert.equal(floatHeight("conversations", [group(true, 3), { kind: "row" }, group(false, 2)]),
    36 + 38 + (26 + 3 * 24) + 26 + 8);
  assert.equal(floatHeight("conversations", []), 36 + 38 + 28 + 8);       // "No conversations"
  assert.equal(floatHeight("spaces", 40), TALL);
});

test("the Spaces list's height, as the app's: a machine's head once another is there, a worktree's row lower", () => {
  const group = (machine, rows, more = {}) => ({ machine, rows, folded: false, rebuilt: false, loading: false,
    ...more });
  const row = { tree: false }, tree = { tree: true };
  assert.equal(listHeight([group(null, [row, row])]), 31 + 2 * 30 + 14);
  assert.equal(listHeight([group(null, [row, tree]), group("lab", [row]), group("mini", [])]),
    31 + 3 * 26 + 30 + 28 + 30 + 28 + 14);                      // mini: "New space there"
  assert.equal(listHeight([group(null, [row]), group("lab", [row], { folded: true }),
    group("old", [row], { rebuilt: true })]), 31 + 3 * 26 + 30 + 14);
  assert.equal(listHeight([group(null, [], { loading: true })]), 31 + 28 + 14);
  assert.equal(listBody(group(null, []), false), "none");
});

test("a layout node's max set in a copy of the tree, and whether that changed it", () => {
  const tree = { id: "root", children: [{ id: "spaces", min: 90 }] };
  const next = withMax(tree, "spaces", 150);
  assert.equal(next.changed, true);
  assert.equal(next.tree.children[0].max, 150);
  assert.equal(tree.children[0].max, undefined);
  assert.equal(withMax(next.tree, "spaces", 150).changed, false);
  assert.equal(withMax(tree, "gone", 150).changed, false);
  assert.equal(withMax(tree, "spaces", 40).tree.children[0].max, 90);         // never under its min
});

test("a change's letter named, as the mouse resting on it says it: git's code, the TUI's letter for it", () => {
  assert.deepEqual(["M", "A", "D", "?", "U", "R"].map(changeName),
    ["Modified", "Added", "Deleted", "Untracked", "Conflict", "Renamed"]);
  assert.equal(changeName("X"), "X");
});

test("Cmd+Shift+G's launcher is the popup mod.open makes, not the mod's own (a folded sidebar's panel)", () => {
  assert.equal(launcher({ overlay: "o1" }), "o1");
  assert.equal(launcher({ overlay: "o2", part: "flyout", panel: "spaces" }), null);
  assert.equal(launcher({ part: "conversations" }), null);
  assert.equal(launcher(undefined), null);
});

const talk = (id, folder, time, state = "", pane = "") =>
  ({ agent: "claude", id, title: `Talk ${id}`, folder, time, state, pane });
const shown = (rows) => rows.map((r) => (r.kind === "group" ? `${r.name} ${r.items.length} ${r.open}` : r.item.id));
const PLACE = { "/repo/shop": "shop", "/repo/api": "api" };

test("the app's agents as core/conversations.py takes herdr's: Claude and Codex on this Mac, with their pane's folder",
  () => {
    const agents = [{ address: "t1", pane: "p1", space: "s1", status: "working", program: { key: "claude" } },
      { address: "t2", pane: "p2", space: "s1", status: "idle", program: { key: "pi" } },
      { address: "box/t3", pane: "p3", space: "s2", status: "blocked", program: { key: "codex" } }];
    const panes = [{ pane: "p1", cwd: "/repo/app" }, { pane: "p3", cwd: "/srv" }];
    assert.deepEqual(coreAgents(agents, panes, new Set(["s1"])),
      [{ agent: "claude", agent_status: "working", pane_id: "t1", cwd: "/repo/app" }]);
  });

test("a folder is the first of this Mac's spaces with a pane there, as the TUI's column reads it", () => {
  const spaces = [{ id: "s1", name: "shop", machine: null, tabs: [{ id: "a" }] },
    { id: "s2", name: "api", machine: null, tabs: [{ id: "b" }] },
    { id: "s3", name: "far", machine: "box", tabs: [{ id: "c" }] }];
  const panes = [{ tab: "a", cwd: "/repo/shop" }, { tab: "b", cwd: "/repo/shop" }, { tab: "b", cwd: "/repo/api" },
    { tab: "c", cwd: "/srv" }, { tab: "a", cwd: null }];
  assert.deepEqual(folderSpaces(spaces, panes), { "/repo/shop": "shop", "/repo/api": "api" });
});

test("each space's conversations in the Spaces order, the front tab's first, then the newest; one elsewhere not",
  () => {
    const items = [talk("a", "/repo/shop", 300), talk("b", "/repo/shop", 100, "working", "t9"),
      talk("x", "/elsewhere", 500), talk("d", "/repo/api", 200)];
    const front = new Set(["t9"]);
    assert.deepEqual(shown(conversationRows(items, ["shop", "api", "notes"], PLACE, { here: "shop", front })),
      ["shop 2 true", "b", "a", "api 1 false", "notes 0 false"]);
  });

test("typing narrows every space and opens them; an archived one only while typed for or shown", () => {
  const items = [talk("a", "/repo/shop", 300), talk("d", "/repo/api", 200)], archived = new Set(["claude:a"]);
  const rows = (more) => shown(conversationRows(items, ["shop", "api"], PLACE, { here: "shop", archived, ...more }));
  assert.deepEqual(rows({}), ["shop 0 true", "api 1 false"]);
  assert.deepEqual(rows({ typed: "talk" }), ["shop 1 true", "a", "api 1 true", "d"]);
  assert.deepEqual(rows({ typed: "API" }), ["api 1 true", "d"]);
  assert.deepEqual(rows({ typed: "archived" }), ["shop 1 true", "a"]);
  assert.deepEqual(rows({ showArchived: true }), ["shop 1 true", "a", "api 1 false"]);
});

test("a space's row has its most urgent agent's state, as the Spaces list marks it", () => {
  const rows = conversationRows([], ["shop", "api"], PLACE, { states: { shop: "working" } });
  assert.deepEqual(rows.map((r) => r.state), ["working", null]);
});

test("a space opened or closed by hand stays so, the one here open unless closed", () => {
  const items = [talk("a", "/repo/shop", 300), talk("d", "/repo/api", 200)];
  assert.deepEqual(shown(conversationRows(items, ["shop", "api"], PLACE,
    { here: "shop", opened: new Set(["api"]), closed: new Set(["shop"]) })), ["shop 1 false", "api 1 true", "d"]);
});

test("a closed one reopens with its agent's resume, its id never an option, a space or a control code", () => {
  assert.deepEqual(resumeArgv({ agent: "claude", id: "0a1b-2c" }), ["claude", "--resume", "0a1b-2c"]);
  assert.deepEqual(resumeArgv({ agent: "codex", id: "019a.x_y" }), ["codex", "resume", "019a.x_y"]);
  for (const id of ["--help", "-x", "a b", "a\u001b[2J", ""]) {
    assert.throws(() => resumeArgv({ agent: "claude", id }), id);
  }
});

test("a right click: Open, Copy conversation, Rename, then Archive or Unarchive; elsewhere the archived shown or not",
  () => {
    const archived = new Set(["claude:c"]), first = ["Open", "Copy conversation", "Rename"];
    assert.deepEqual(conversationChoices(talk("r", "/x", 1, "working"), archived, false), first);
    assert.deepEqual(conversationChoices(talk("o", "/x", 1), archived, false), [...first, "Archive"]);
    assert.deepEqual(conversationChoices(talk("c", "/x", 1), archived, false), [...first, "Unarchive"]);
    assert.deepEqual(conversationChoices(null, archived, false), ["Show archived"]);
    assert.deepEqual(conversationChoices(null, archived, true), ["Hide archived"]);
    assert.deepEqual(conversationChoices(null, new Set(), false), []);
  });

test("a reopened conversation's tab: its title, printable, no leading dash, cut at 24 with an ellipsis", () => {
  assert.equal(tabLabel("- Fix\u001b the login"), "Fix the login");
  assert.equal(tabLabel("A very long conversation title here"), "A very long conversatio…");
});

test("the sidebar is a rail narrower than 160 px, as the app's own mods draw it", () => {
  const at = (px) => ({ id: "root", children: [{ id: "sidebar", size: { px } }] });
  assert.equal(railed(at(76)), true);
  assert.equal(railed(at(268)), false);
  assert.equal(railed({ id: "root" }), false);
});

test("folded, the sidebar is as wide as the traffic lights on macOS; opened, the width it had", () => {
  const at = (px) => ({ id: "root", children: [{ id: "sidebar", size: { px } }] });
  assert.equal(foldedWidth(at(268), true, 300), 76);
  assert.equal(foldedWidth(at(268), false, 300), 44);
  assert.equal(foldedWidth(at(76), true, 300), 300);
  assert.equal(foldedWidth(at(76), true, undefined), 268);
});

test("a panel's most urgent state, as the app orders a space's: blocked, done, working, then idle", () => {
  assert.equal(urgent(["idle", "working", null, "blocked"]), "blocked");
  assert.equal(urgent(["idle", "done", "working"]), "done");
  assert.equal(urgent(["idle", ""]), "idle");
  assert.equal(urgent([null, ""]), null);
});

test("a wait as a Space row says it, as the TUI's: under a minute, then minutes, hours, days", () => {
  assert.deepEqual([30e3, 60e3, 12 * 60e3, 61 * 60e3, 25 * 3600e3].map(waited),
    ["waiting <1m", "waiting 1m", "waiting 12m", "waiting 1h", "waiting 1d"]);
});

test("an agent waits on you since its last change while blocked or done, and no longer once it works or idles", () => {
  const agent = (status, seq) => ({ address: "t1", pane: "p1", space: "s1", status, seq });
  let waits = nextWaits({}, [agent("done", 4)], 1000, null);
  assert.deepEqual(waits, { t1: { seq: 4, since: 1000 } });
  waits = nextWaits(waits, [agent("done", 4)], 5000, null);
  assert.equal(waits.t1.since, 1000);                          // the same wait: its start kept
  assert.equal(nextWaits(waits, [agent("blocked", 5)], 9000, null).t1.since, 9000);
  assert.deepEqual(nextWaits(waits, [agent("idle", 6)], 9000, "p1"), {});
});

test("marked unread, an agent waits until its pane is left and come back to; marked again, the mark goes", () => {
  const agent = { address: "t1", pane: "p1", space: "s1", status: "idle", seq: 7 };
  let waits = toggleUnread({}, agent, 2000);
  assert.deepEqual(waits, { t1: { seq: 7, since: 2000, unread: true, left: false } });
  assert.deepEqual(nextWaits(waits, [agent], 3000, "p1"), waits);       // still on it
  waits = nextWaits(waits, [agent], 4000, "p2");
  assert.equal(waits.t1.left, true);
  assert.deepEqual(nextWaits(waits, [agent], 5000, "p1"), {});          // back on it: read
  assert.deepEqual(toggleUnread(toggleUnread({}, agent, 1), agent, 2), {});
  assert.equal(toggleUnread({ t1: { seq: 7, since: 500 } }, agent, 2000).t1.since, 500);    // from when it waits
});

test("a space's wait is its longest: since when its first agent waits", () => {
  const agents = [{ address: "a", space: "s1" }, { address: "b", space: "s1" }, { address: "c", space: "s2" }];
  assert.deepEqual(spaceWaits({ a: { since: 300 }, b: { since: 100 } }, agents), { s1: 100 });
});

test("after a space's name, only what is unusual: the repository, the branch, never main or a name it has", () => {
  assert.equal(placeLabel({ name: "lumen-api", branch: "main" }, false, "lumen-api"), "");
  assert.equal(placeLabel({ name: "lumen-api", branch: "fix-login" }, false, "api"), "lumen-api · fix-login");
  assert.equal(placeLabel({ name: "lumen-api", branch: "fix-login" }, true, "fix-login"), "");
  assert.equal(placeLabel({ name: "lumen-api", branch: null }, false, "lumen-api"), "detached");
});

test("a worktree's space under its checkout's, in order; one whose checkout has no space stays where it is", () => {
  const row = (id, g) => ({ w: { id }, g });
  const rows = nested([row("wt1", { repo: "r", linked: true }), row("main", { repo: "r", linked: false }),
    row("other", null), row("wt2", { repo: "r", linked: true }), row("lone", { repo: "q", linked: true })]);
  assert.deepEqual(rows.map((r) => [r.w.id, r.tree]),
    [["main", false], ["wt1", true], ["wt2", true], ["other", false], ["lone", false]]);
});

test("a space without a color gets the one fewest use, as every app mod gives it; the home folder's none", () => {
  const list = [{ id: "a", name: "x" }, { id: "b", name: "y" }, { id: "c", name: "~" }];
  assert.deepEqual(spaceColors(list, { a: "ansi6", gone: "ansi3" }), { a: "ansi6", b: "ansi3" });
  assert.equal(spaceColors(list.slice(0, 1), { a: "ansi6" }), null);    // nothing to write
});

test("an avatar's fill: the app's strong color for a theme color's name, a picked one as it is", () => {
  assert.equal(avatarFill("ansi3", {}), MARK.ansi3);
  assert.equal(avatarFill("#123456", {}), "#123456");
});
