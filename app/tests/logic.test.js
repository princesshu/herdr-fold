// @ts-check
// Tests for the mod's logic that needs no window: node --test in app/ (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterCommit, background, branchLabel, changeColor, changeName, commitMode, commitRows, conversationChoices,
  conversationRows, coreAgents, diffRows, excerpt, fileRows, floatHeight, folderIcon, foldedSections, foldedWidth,
  folderSpaces, issueAgent, lastLine, launcher, letter, machineOf, marked, MODES, PANEL, panelShown, previewName,
  previewTab, priorityColor, pushOffer, pythonCommand, railed, resumeArgv, rowActions, safeMarkdown, said, searchRows,
  searchSummary, secretQuestion, shownTab, strays, syncLabel, tabLabel, TALL, terminalId, TERMINALS, urgent, withMax,
  withoutTabs, withTerminal, written, waited, nextWaits, toggleUnread, spaceWaits, placeLabel, nested, folderKey,
  placeKey, spaceColors, avatarFill, MARK, listBody, listHeight, panelRailed, railFollow, railToggle, RAIL, RAIL_BLOCK,
  PANEL_PX, activeTerminal, hovering, tabRows, lightsRoom, toggleRoom, mediaKind, aboutLines, stacks, swapDraft,
  browsable, opener, changeSides, fileIcon, stillResumed, CHAT_TAB, orphanChats, menuPlace, menuHeight, GROUPS_APP,
  GROUP_WEIGHTS, GROUP_HEAD, FOLDED_GROUP, DOCK, DOCK_HEAD, groupTabs, groupFolded, groupSize, shownPanels,
  panelsFollow, pickCommands, foldCommands, panelChoices, hideCommands, keptTabs, PAD }
  from "../mods/herdr-fold/logic.js";

test("a tab nobody named after its program, an agent's first, else Terminal; an agent's icon; zoomed marked", () => {
  const space = { tabs: [{ id: "t1", name: "1", named: false, active: true, status: "working" },
    { id: "t2", name: "2", named: false }, { id: "t3", name: "notes", named: true, zoomed: true, status: "done" }] };
  const panes = [{ tab: "t1", program: { name: "zsh" } }, { tab: "t1", program: { name: "Claude", agent: true,
    icon: "claude.svg", tint: true } }, { tab: "t3", program: { name: "vim", icon: "vim.png" } }];
  assert.deepEqual(tabRows(space, panes), [
    { id: "t1", name: "Claude", active: true, status: "working", icon: "claude.svg", tint: true },
    { id: "t2", name: "Terminal", active: false, status: null, icon: null, tint: false },
    { id: "t3", name: "notes Z", active: false, status: "done", icon: null, tint: false }]);
  assert.deepEqual(tabRows(undefined, panes), []);
});

test("a chat tab wears its agent's icon and state, its agent being a terminal with no pane", () => {
  const space = { tabs: [{ id: "t4", name: "Fix the page past the last one", named: true }] };
  const chats = { t4: { status: "working", program: { name: "Claude", agent: true, icon: "claude.svg", tint: true } } };
  assert.deepEqual(tabRows(space, [{ tab: "t4", program: { name: "herdr-fold" } }], chats), [
    { id: "t4", name: "Fix the page past the last one", active: false, status: "working", icon: "claude.svg",
      tint: true }]);
});

test("an SVG's or a page's code goes above its picture as chosen, else where the room is taller than wide", () => {
  assert.equal(stacks(null, { width: 800, height: 600 }), false);
  assert.equal(stacks(null, { width: 400, height: 900 }), true);
  assert.equal(stacks(true, { width: 800, height: 600 }), true);
  assert.equal(stacks(false, { width: 400, height: 900 }), false);
  assert.equal(stacks(null, null), false);                          // not measured yet: side by side
});

test("the panel menu names herdr-fold's version, a newer one once out, and switches the update check", () => {
  const found = { version: "0.3.0", latest: "0.3.0", newer: false, on: true, releases: "https://example.com/r" };
  assert.deepEqual(aboutLines(found), [{ label: "herdr-fold 0.3.0", url: "https://example.com/r" },
    { label: "Check for Updates", on: true }]);
  assert.equal(aboutLines({ ...found, latest: "0.4.0", newer: true })[0].label, "herdr-fold 0.4.0 is out");
  assert.deepEqual(aboutLines({ ...found, version: null }), []);              // never installed here
  assert.deepEqual(aboutLines(null), []);                                      // not looked at yet
});

test("a space's first tab, while nobody named it, takes the space's name, as the TUI's main tab", () => {
  const space = { name: "lumen-api", tabs: [{ id: "t1", name: "1", named: false, status: "working" },
    { id: "t2", name: "2", named: false }] };
  const panes = [{ tab: "t1", program: { name: "Claude", agent: true, icon: "claude.svg", tint: true } }];
  assert.deepEqual(tabRows(space, panes).map((r) => [r.name, r.icon]), [["lumen-api", "claude.svg"],
    ["Terminal", null]]);
  Object.assign(space.tabs[0], { name: "review", named: true });     // named by hand: that name
  assert.equal(tabRows(space, panes)[0].name, "review");
});

test("the tab bar's room for the traffic lights: what the sidebar beside them leaves, 10 at least, macOS only", () => {
  const root = (sidebar, trigger) => ({ traffic_lights: [12, 16], children: [{ id: "sidebar", size: { px: sidebar } },
    { id: "sidebar-trigger", size: { px: 40 }, hidden: !trigger }] });
  const mac = { platform: "macos", titlebar: "none", fullscreen: false };
  assert.equal(lightsRoom(root(268, false), mac, 1), 10);
  assert.equal(lightsRoom(root(0, true), mac, 1), 36);
  assert.equal(lightsRoom(root(0, true), mac, 2), 10);
  assert.equal(lightsRoom(root(0, true), { ...mac, fullscreen: true }, 1), 10);
  assert.equal(lightsRoom(root(0, true), { ...mac, platform: "linux" }, 1), 10);
});

test("the tab bar's end leaves room so its panel toggle, a BUTTON wide, sits over the rail's middle", () => {
  assert.equal(toggleRoom({ children: [{ id: "work-body", padding: 8 }] }, 26), 8 + (RAIL - 26) / 2);
  assert.equal(toggleRoom({ children: [] }, 26), (RAIL - 26) / 2);
});

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

/** A layout as herdr-fold's has it: the panel, its groups above, its tabs' terminals below (the stand-in first). */
const tree = () => ({ id: "root", children: [{ id: PANEL, children: [{ id: "fold-project", children: [] },
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

/** The right dock as the layout has it: its head, the dock (the two groups, the terminals), the rail; OVER changes a
 * node by its id. @param {Record<string, any>} [over] */
function dock(over = {}) {
  const node = (/** @type {string} */ id, rest = {}) => ({ id, ...rest, ...(over[id] ?? {}) });
  const group = (/** @type {"project" | "work"} */ g) => node(`fold-${g}`, { type: "column",
    size: { weight: GROUP_WEIGHTS[g] }, children: [node(`fold-${g}-head`), node(`fold-${g}-body`, { type: "stack",
      active: GROUPS_APP[g][0], children: GROUPS_APP[g].map((id) => node(id)) })] });
  return { id: "root", children: [node(PANEL, { size: { px: PANEL_PX }, children: [node(DOCK_HEAD),
    node(DOCK, { children: [group("project"), group("work"), node(TERMINALS)] }),
    node(RAIL_BLOCK, { hidden: true })] })] };
}

test("a group's head shows its tabs, the shown one, its fold", () => {
  assert.deepEqual(GROUPS_APP, { project: ["files", "search"], work: ["changes", "issues"] });    // core/dock.py's
  const root = dock();
  assert.deepEqual(groupTabs(root, "work", true), ["changes", "issues"]);
  assert.deepEqual(groupTabs(root, "work", false), ["changes"]);                  // Issues on GitHub only
  assert.equal(shownTab(root, "project", true), "files");
  assert.equal(groupFolded(root, "project"), false);
  const folded = dock({ "fold-project-body": { hidden: true, active: "search" }, files: { hidden: true } });
  assert.equal(groupFolded(folded, "project"), true);                             // its tabs still there
  assert.deepEqual(groupTabs(folded, "project", true), ["search"]);               // hidden in the ⋯: no tab
  assert.equal(shownTab(folded, "project", true), "search");
  assert.equal(shownTab(dock({ "fold-work-body": { active: "issues" } }), "work", false), "changes");
  assert.equal(shownTab(dock({ files: { hidden: true }, search: { hidden: true } }), "project", true), null);
  assert.deepEqual(shownPanels(dock({ search: { hidden: true } }), false), ["files", "changes"]);
  assert.deepEqual(groupTabs({ id: "root" }, "work", true), []);                  // another layout: none
});

test("a key picks its group's tab and unfolds it", () => {
  const folded = dock({ "fold-project-body": { hidden: true }, "fold-project": { size: { px: FOLDED_GROUP } } });
  assert.deepEqual(pickCommands(folded, "search", { github: true, sizes: { project: { weight: 4 } } }), [
    ["layout.select", { stack: "fold-project-body", child: "search" }],
    ["layout.show", { id: "fold-project-body" }], ["layout.resize", { id: "fold-project", weight: 4 }]]);
  assert.deepEqual(pickCommands(folded, "files", { github: true })[1], ["layout.resize",
    { id: "fold-project", weight: GROUP_WEIGHTS.project }]);                       // shown already: only unfolded
  assert.deepEqual(pickCommands(dock(), "files", { github: true }), []);           // shown and open: nothing to do
  assert.deepEqual(pickCommands(dock({ changes: { hidden: true }, issues: { hidden: true },
    "fold-work": { hidden: true } }), "changes", { github: true }),
  [["layout.show", { id: "changes" }], ["layout.show", { id: "fold-work" }]]);    // hidden in the ⋯: shown again
  assert.deepEqual(pickCommands(dock(), "issues", { github: false }), []);         // off GitHub: left as it is
  assert.deepEqual(pickCommands(dock(), "bogus", { github: true }), []);
  const railed = dock({ [PANEL]: { size: { px: RAIL } }, [DOCK_HEAD]: { hidden: true }, [DOCK]: { hidden: true },
    [RAIL_BLOCK]: { hidden: false } });
  assert.deepEqual(pickCommands(railed, "issues", { github: true, kept: 420 }), [
    ["layout.select", { stack: "fold-work-body", child: "issues" }], ["layout.resize", { id: PANEL, px: 420 }],
    ["layout.show", { id: DOCK_HEAD }], ["layout.show", { id: DOCK }], ["layout.hide", { id: RAIL_BLOCK }]]);
  assert.deepEqual(pickCommands(dock({ [PANEL]: { hidden: true } }), "changes", { github: true }),
    [["layout.show", { id: PANEL }], ["layout.resize", { id: PANEL, px: PANEL_PX }]]);
});

test("a group folds to its head and opens again to the size it had", () => {
  assert.equal(FOLDED_GROUP, GROUP_HEAD + PAD + 2);                               // its head, PAD, its frame
  assert.deepEqual(foldCommands(dock(), "work", undefined), [["layout.hide", { id: "fold-work-body" }],
    ["layout.resize", { id: "fold-work", px: FOLDED_GROUP }]]);
  const folded = dock({ "fold-work-body": { hidden: true }, "fold-work": { size: { px: FOLDED_GROUP } } });
  const open = (/** @type {any} */ size) => [["layout.show", { id: "fold-work-body" }],
    ["layout.resize", { id: "fold-work", ...size }]];
  assert.deepEqual(foldCommands(folded, "work", { weight: 5 }), open({ weight: 5 }));
  assert.deepEqual(foldCommands(folded, "work", { px: 300 }), open({ px: 300 }));
  assert.deepEqual(foldCommands(folded, "work", { px: FOLDED_GROUP }), open({ weight: GROUP_WEIGHTS.work }));
  assert.deepEqual(foldCommands(folded, "work", undefined), open({ weight: GROUP_WEIGHTS.work }));
  assert.deepEqual(groupSize(dock(), "work"), { weight: GROUP_WEIGHTS.work });
  assert.deepEqual(foldCommands({ id: "root" }, "work", undefined), []);
});

test("the dock's ⋯ lists the panels with their ✓; one hidden takes its tab, its group once empty, never the last",
  () => {
  assert.deepEqual(panelChoices(dock({ search: { hidden: true } }), true), [
    { panel: "files", label: "Files", on: true, off: false },
    { panel: "search", label: "Search", on: false, off: false },
    { panel: "changes", label: "Changes", on: true, off: false },
    { panel: "issues", label: "Issues", on: true, off: false }]);
  assert.deepEqual(panelChoices(dock(), false).map((c) => c.panel), ["files", "search", "changes"]);
  const last = dock({ files: { hidden: true }, search: { hidden: true }, issues: { hidden: true } });
  assert.deepEqual(panelChoices(last, true)[2], { panel: "changes", label: "Changes", on: true, off: true });
  assert.deepEqual(hideCommands(dock(), "files", true, true), [["layout.hide", { id: "files" }],
    ["layout.select", { stack: "fold-project-body", child: "search" }]]);       // its group shows the other
  assert.deepEqual(hideCommands(dock({ search: { hidden: true } }), "files", true, true),
    [["layout.hide", { id: "files" }], ["layout.hide", { id: "fold-project" }]]);  // its group's last: the group
  assert.deepEqual(hideCommands(last, "changes", true, true), []);                // one panel stays shown
  assert.deepEqual(hideCommands(dock({ files: { hidden: true }, search: { hidden: true },
    "fold-project": { hidden: true } }), "search", false, true), [["layout.show", { id: "search" }],
    ["layout.show", { id: "fold-project" }], ["layout.select", { stack: "fold-project-body", child: "search" }]]);
});

test("the groups follow their panels: one with none shown hidden, a stack never on a tab it cannot show", () => {
  assert.deepEqual(panelsFollow(dock(), true), []);
  assert.deepEqual(panelsFollow(dock({ "fold-work-body": { active: "issues" } }), false),
    [["layout.select", { stack: "fold-work-body", child: "changes" }]]);       // off GitHub: Changes
  assert.deepEqual(panelsFollow(dock({ changes: { hidden: true }, "fold-work-body": { active: "issues" } }), false),
    [["layout.hide", { id: "fold-work" }]]);
  assert.deepEqual(panelsFollow({ id: "root" }, true), []);
});

test("a group keeps the tab picked: off GitHub Issues gives way to Changes, back on GitHub Issues shows again", () => {
  const onIssues = dock({ "fold-work-body": { active: "issues" } }), onChanges = dock();
  assert.deepEqual(keptTabs(onIssues, {}), { project: "files", work: "issues" });   // none picked: the stacks' own
  assert.deepEqual(keptTabs(onIssues, { work: "changes" }), { project: "files", work: "changes" });
  assert.deepEqual(keptTabs({ id: "root" }, {}), {});
  assert.deepEqual(panelsFollow(onIssues, false, { work: "issues" }),
    [["layout.select", { stack: "fold-work-body", child: "changes" }]]);         // off GitHub: Changes meanwhile
  assert.deepEqual(panelsFollow(onChanges, false, { work: "issues" }), []);       // still off: Changes stays
  assert.deepEqual(panelsFollow(onChanges, true, { work: "issues" }),
    [["layout.select", { stack: "fold-work-body", child: "issues" }]]);          // back on GitHub: Issues again
  assert.deepEqual(panelsFollow(onChanges, true, { work: "changes" }), []);
  assert.deepEqual(panelsFollow(dock({ issues: { hidden: true } }), true, { work: "issues" }), []);  // off in the ⋯
  // a pick is the new choice: the one kept before never takes the group back
  assert.deepEqual(pickCommands(onIssues, "changes", { github: true, chosen: { work: "issues" } }),
    [["layout.select", { stack: "fold-work-body", child: "changes" }]]);
  assert.deepEqual(hideCommands(dock({ issues: { hidden: true } }), "issues", false, true, { work: "issues" }),
    [["layout.show", { id: "issues" }], ["layout.select", { stack: "fold-work-body", child: "issues" }]]);
});

test("a card keeps PAD inside on every side: the terminals' text, a group's tabs, under a folded group's head", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  const parts = readFileSync(new URL("../mods/herdr-fold/parts.js", import.meta.url), "utf8");
  const space = /^export const SPACE = \[([\d, ]+)\];/m.exec(parts)?.[1].split(",").map(Number) ?? [];
  assert.ok(space.includes(PAD) && space.includes(PAD / 2), "PAD and a row's pad, halfway in, on the scale");
  assert.ok(/^export \{ PAD \};/m.test(parts), "parts.js hands logic.js's PAD to the views, no value of its own");
  assert.deepEqual(root.terminal_padding, [PAD, PAD]);                          // the centre's and the dock's
  assert.equal(GROUP_HEAD, PAD + 24);                                           // its tabs, 24 high, PAD under the top
  assert.equal(FOLDED_GROUP, GROUP_HEAD + PAD + 2);                             // folded: PAD under them, in its frame
});

test("the right dock folds to its rail and opens again, as its » and « and a drag do it", () => {
  /** @param {number} px @param {{ hidden?: boolean, rail?: boolean }} [shown] */
  const tree = (px, { hidden = false, rail = false } = {}) => dock({ [PANEL]: { hidden, size: { px } },
    [DOCK_HEAD]: { hidden: rail }, [DOCK]: { hidden: rail }, [RAIL_BLOCK]: { hidden: !rail } });
  /** @param {boolean} open */
  const blocks = (open) => [[open ? "layout.show" : "layout.hide", { id: DOCK_HEAD }],
    [open ? "layout.show" : "layout.hide", { id: DOCK }], [open ? "layout.hide" : "layout.show", { id: RAIL_BLOCK }]];
  assert.equal(panelRailed(tree(RAIL, { rail: true })), true);
  assert.equal(panelRailed(tree(PANEL_PX)), false);
  assert.deepEqual(railToggle(tree(420), 368), [["layout.resize", { id: PANEL, px: RAIL }], ...blocks(false)]);
  assert.deepEqual(railToggle(tree(RAIL, { rail: true }), 420), [["layout.resize", { id: PANEL, px: 420 }],
    ...blocks(true)]);
  assert.deepEqual(railToggle(tree(RAIL, { rail: true }), undefined)[0],
    ["layout.resize", { id: PANEL, px: PANEL_PX }]);
  assert.deepEqual(railToggle(tree(420, { hidden: true }), 368), [["layout.show", { id: PANEL }],
    ["layout.resize", { id: PANEL, px: 420 }]]);
  // dragged narrow: the rail, at its own width; dragged wide again: the dock; hidden: nothing
  assert.deepEqual(railFollow(tree(120)), [...blocks(false), ["layout.resize", { id: PANEL, px: RAIL }]]);
  assert.deepEqual(railFollow(tree(300, { rail: true })), blocks(true));
  assert.deepEqual(railFollow(tree(RAIL, { rail: true })), []);
  assert.deepEqual(railFollow(tree(120, { hidden: true })), []);
  assert.equal(panelShown(tree(420)), true);
  assert.equal(panelShown(tree(420, { hidden: true })), false);
  assert.equal(panelShown({ id: "root" }), false);
  assert.equal(PANEL, "fold-panel");                       // herdr-fold's own id: the app's Settings leaves it alone
});

test("the layout's right dock: its head, the two groups, each a head over a stack of its panels, the terminals", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  /** @type {Map<string, any>} */
  const nodes = new Map();
  const walk = (/** @type {any} */ node) => {
    assert.equal(nodes.has(node.id), false, `${node.id} twice`);
    nodes.set(node.id, node);
    (node.children ?? []).forEach(walk);
  };
  walk(root);
  const ids = (/** @type {string} */ id) => nodes.get(id).children.map((/** @type {any} */ c) => c.id);
  assert.deepEqual(ids(PANEL), [DOCK_HEAD, DOCK, RAIL_BLOCK]);
  assert.equal(nodes.get(PANEL).resizable, false);                               // the dock's head never drags
  assert.deepEqual(nodes.get(DOCK_HEAD).content, { mod: "herdr-fold", props: { part: "dock-head" } });
  assert.deepEqual(ids(DOCK), ["fold-project", "fold-work", TERMINALS]);
  for (const [group, panels] of Object.entries(GROUPS_APP)) {
    const column = nodes.get(`fold-${group}`), [head, body] = column.children;
    assert.deepEqual([column.resizable, column.size], [false, { weight: GROUP_WEIGHTS[group] }]);
    assert.deepEqual([head.size, head.content.props], [{ px: GROUP_HEAD }, { part: "group-head", group }]);
    assert.deepEqual([body.id, body.type, body.active], [`fold-${group}-body`, "stack", panels[0]]);
    assert.deepEqual(body.children.map((/** @type {any} */ c) => [c.id, c.content.props]), panels.map((id) =>
      [id, id === "files" ? { part: "files" } : { view: id }]));
  }
});

test("a menu as tall as its rows, a rule between its parts thinner", () => {
  assert.equal(menuHeight([{ label: "a" }, { label: "b" }]), 2 * 30 + 8);
  assert.equal(menuHeight([{ label: "a" }, null, { label: "b" }]), 2 * 30 + 11 + 8);
  assert.equal(menuHeight([{ label: "a" }], { label: "head" }), 2 * 30 + 8);
});

test("a floating panel as tall as its content, up to TALL: Spaces' rows, Conversations' groups and open ones", () => {
  assert.equal(floatHeight("spaces", 2), 36 + 2 * 29 + 8);
  const group = (open, n) => ({ kind: "group", open, items: Array(n).fill({}) });
  assert.equal(floatHeight("conversations", [group(true, 3), { kind: "row" }, group(false, 2)]),
    36 + 38 + (26 + 3 * 24) + 26 + 8);
  assert.equal(floatHeight("conversations", []), 36 + 38 + 28 + 8);       // "No conversations"
  assert.equal(floatHeight("spaces", 40), TALL);
});

test("the Spaces list's height, on the grid: a machine's head once another is there, a worktree's row lower", () => {
  const group = (machine, rows, more = {}) => ({ machine, rows, folded: false, rebuilt: false, loading: false,
    ...more });
  const row = { tree: false }, tree = { tree: true };
  assert.equal(listHeight([group(null, [row, row])]), 32 + 2 * 32 + 16);
  assert.equal(listHeight([group(null, [row, tree]), group("lab", [row]), group("mini", [])]),
    32 + 3 * 28 + 32 + 28 + 32 + 28 + 16);                      // mini: "New space there"
  assert.equal(listHeight([group(null, [row]), group("lab", [row], { folded: true }),
    group("old", [row], { rebuilt: true })]), 32 + 3 * 28 + 32 + 16);
  assert.equal(listHeight([group(null, [], { loading: true })]), 32 + 28 + 16);
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

test("after a space's name its branch, main too, as the TUI's; its repository where unusual; never the name", () => {
  assert.equal(placeLabel({ name: "lumen-api", branch: "main" }, false, "lumen-api"), "main");
  assert.equal(placeLabel({ name: "lumen-api", branch: "master" }, false, "lumen-api"), "master");
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

test("a space showing the repository inside its folder is no checkout, nor a worktree under one", () => {
  // its folder is no repository: core/git.py's place found one inside it (marked inside), which its row names
  const row = (id, g) => ({ w: { id }, g });
  const rows = nested([row("archive", { repo: "r", linked: false, inside: true }),
    row("wt", { repo: "r", linked: true }), row("box", { repo: "r", linked: true, inside: true }),
    row("main", { repo: "r", linked: false })]);
  assert.deepEqual(rows.map((r) => [r.w.id, r.tree]),
    [["archive", false], ["box", false], ["main", false], ["wt", true]]);
});

test("a space whose folder is no repository is looked up with its active pane's folder too", () => {
  // the repository inside it shown is the one its active pane (the focused one of its shown tab) is in
  const s = { machine: null, folder: "/w/made-in", tabs: [{ id: "t1", active: false }, { id: "t2", active: true }] };
  const ps = [{ tab: "t1", cwd: "/w/archive" }, { tab: "t2", cwd: "/w/archive/one/src", focused: true },
    { tab: "t1", cwd: "/w/archive/two", focused: true }];
  const plain = JSON.stringify([null, "/w/archive"]);
  const active = JSON.stringify([null, "/w/archive", "/w/archive/one/src"]);
  assert.equal(folderKey(s, ps), plain);                                   // its first terminal's live folder
  assert.equal(folderKey({ ...s, machine: "lab" }, []), JSON.stringify(["lab", "/w/made-in"]));
  assert.equal(placeKey(s, ps, {}), plain);                                // not looked at yet
  assert.equal(placeKey(s, ps, { [plain]: { repo: "r", inside: false } }), plain);     // a repository: its own
  assert.equal(placeKey(s, ps, { [plain]: null }), active);
  assert.equal(placeKey(s, ps, { [plain]: { repo: "r", inside: true } }), active);
  assert.equal(placeKey(s, [ps[0], { ...ps[1], cwd: "/w/archive" }], { [plain]: null }), plain);   // in the folder
  assert.equal(placeKey(s, [ps[0], ps[2]], { [plain]: null }), plain);    // no pane focused in its shown tab
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

test("a picture, a PDF or a page by its name, as core/media.py has them", () => {
  assert.deepEqual(["docs/shot.WEBP", "a.pdf", "site/index.html", "logo.svg", "notes.md", ".bashrc", "src.png/app"]
    .map(mediaKind), ["image", "pdf", "html", "svg", null, null, null]);
});

test("the message field keeps each space's own draft, a message written for one waiting there", () => {
  const drafts = new Map();
  assert.equal(swapDraft(drafts, null, "a", ""), "");                     // the first space: an empty field
  assert.equal(swapDraft(drafts, "a", "b", "fix: a"), "");                 // a's typed message kept, b's new
  drafts.set("a", "feat: written for a");                                  // the AI's answer, come while on b
  assert.equal(swapDraft(drafts, "b", "a", ""), "feat: written for a");
  assert.equal(swapDraft(drafts, "a", "b", "feat: written for a"), "");    // b's was empty: nothing kept for it
  assert.equal(drafts.has("b"), false);
});

test("a page, a PDF or a picture on this Mac opens in the browser, nothing else and nothing on another machine", () => {
  const file = (path, on = null) => ({ kind: "file", path, on });
  const asked = [file("site/index.html"), file("a.pdf"), file("shot.png"), file("a.py"), file("index.html", "lab"),
    { kind: "commit", path: "index.html", on: null }, null];
  assert.deepEqual(asked.map(browsable), [true, true, true, false, false, false, false]);
});

test("a picture no browser shows opens in Preview, the web's own in the browser, as the TUI's", () => {
  assert.deepEqual(["art.PSD", "render.exr", "photo.dng", "shot.png", "logo.svg", "a.pdf", "site/index.html"]
    .map((path) => opener(path, "macos")),
  ["Preview", "Preview", "Preview", "Browser", "Browser", "Browser", "Browser"]);
  assert.equal(opener("art.psd", "linux"), "Browser");                     // the desktop's own opener there
});

test("a changed picture's sides: its last commit's and the file's, each with its pixels, either one missing", () => {
  const side = (w, h) => ({ png: "herdr-fold-pictures/x.png", size: [w, h], pixels: [w * 4, h * 4] });
  const [before, after] = [side(160, 120), side(120, 160)];
  assert.deepEqual(changeSides({ before, after }), [["HEAD · 640 × 480", before], ["Working Tree · 480 × 640", after]]);
  assert.deepEqual(changeSides({ before: null, after }).map(([caption]) => caption), ["Working Tree · 480 × 640"]);
  const deleted = { before: { png: "p", size: null, pixels: null }, after: null };   // its pixels not known
  assert.deepEqual(changeSides(deleted).map(([caption]) => caption), ["HEAD"]);
});

test("a file named for an object's own property gets the plain file icon, never that property", () => {
  for (const name of ["x.constructor", "x.toString", "x.__proto__", "x.hasOwnProperty"]) {
    assert.equal(fileIcon(name), fileIcon("x.unknown-kind"), name);
  }
});

test("a reopened conversation is forgotten once its agent is gone, never for a moment's empty list", () => {
  const kept = { t1: "talk-1", t2: "talk-2" };
  assert.deepEqual(stillResumed(kept, new Set(["t1", "t9"])), { t1: "talk-1" });
  assert.deepEqual(stillResumed(kept, new Set()), kept);                   // the app starting, its core reconnecting
});

test("a chat's agent whose tab is gone is ended; one whose tab is there, or that has ended, stays", () => {
  const agent = (address, tab, state = "live") => ({ address, state, labels: { [CHAT_TAB]: tab } });
  assert.deepEqual(orphanChats([agent("t1", "tb1"), agent("t2", "tb2"), agent("t3", "tb3", "exited"),
    { address: "t4", state: "live", labels: {} }], ["tb1"]), ["t2"]);
});

test("a menu opens under its button where it fits there, else above it, else as far in as the window lets it", () => {
  const room = { width: 1200, height: 800 };
  const button = (y) => ({ x: 600, y, width: 60, height: 24 });
  assert.deepEqual(menuPlace(button(100), 120, room, 180), { x: 480, y: 128 });            // under, right edges in line
  assert.deepEqual(menuPlace(button(740), 120, room, 180), { x: 480, y: 616 });            // the chat's bar: above
  assert.deepEqual(menuPlace(button(60), 760, room, 180), { x: 480, y: 32 });              // neither: in the window
  assert.deepEqual(menuPlace({ x: 2, y: 100, width: 24, height: 24 }, 120, room, 180).x, 8);   // the left edge kept
});
