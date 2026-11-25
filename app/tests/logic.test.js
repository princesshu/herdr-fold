// @ts-check
// Tests for the mod's logic that needs no window: node --test in app/ (tests/test_app.py runs them, Node there).
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterCommit, background, branchLabel, changeColor, changeName, commitMode, commitRows, chatChoices,
  chatRows, chatsAsked, coreAgents, deleteOff, folderGroup, groupPlace, stillLeaving, withoutLeaving,
  diffRows, excerpt, fileRows, floatHeight, folderIcon, foldedSections, foldedWidth,
  folderSpaces, issueAgent, lastLine, launcher, letter, machineOf, marked, MODES, PANEL, panelShown, previewName,
  previewTab, priorityColor, pushOffer, pythonCommand, railed, resumeArgv, rowActions, safeMarkdown, said, searchRows,
  searchSummary, secretQuestion, shownView, strays, syncLabel, tabLabel, TALL, terminalId, TERMINALS, urgent,
  withoutTabs, withTerminal, written, waited, nextWaits, toggleUnread, spaceWaits, placeLabel, nested, folderKey,
  atHome, homeFirst, homeId, homesEmpty, homesSeen, withHomes, HOME_NAME, spaceLabel, spaceColor,
  placeKey, spaceColors, avatarFill, MARK, listBody, listHeight, panelRailed, railFollow, railToggle, RAIL, RAIL_BLOCK,
  PANEL_PX, activeTerminal, hovering, tabRows, titleSide, fieldWidth, FIELD, FIELD_LEAST, paletteKey, toggleRoom,
  keyNames, keyWord, paletteEntries, entryKey, palettePlace, PALETTE_NAMED, PALETTE_GROUPS, PALETTE_OWNED,
  mediaKind, aboutState, stacks, swapDraft,
  browsable, opener, changeSides, fileIcon, stillResumed, CHAT_TAB, orphanChats, menuPlace, menuHeight, VIEWS_APP,
  CHATS_BLOCK, BADGE, badgeSpot, DOCK, TAB_COUNT, TAB_GAP, TAB_H, TAB_IN, TABS_H, TABS_IN, TABS_PAD, TABS_SIDE,
  shownPanels, panelsFollow, pickCommands, panelChoices, hideCommands, PAD, waitingChats, shortCount, chosenFor,
  keepChosen, chatsToggle, tabFit, repoTold, issuesParts, NOTE_MS, CENTER, BOTTOM_PX, TERMINALS_WEIGHT,
  floatMin, floatMax, railFloatPx, keepFloat, dragPx, FLOAT_GRIP, restWidth, UNFOLD, SETTLE, dockRest, sidebarRest,
  sidebarRail, SIDEBAR_PX, sidebarFollow, sidebarToggle, floatStale, floating, floatX, floatTop, FLOAT_GAP, restAt,
  pressCloses, foldCommands, fitFloatPx,
  terminalsAt, bottomPx, bottomShown, placeTerminals, bottomToggle, find, CHAT_LABEL, chatWait, keepWait, WAY_OUT,
  waiting, chatAgents, updateNotice, ABOUT, aboutHeight, licenseOf, aboutTargets, agentsSaid, updateReady, SETTINGS,
  SECTIONS, APP_SECTIONS, settingsSection, sectionStep, settingsTargets, columnToggle, restoreCommands, keyMenuBounds,
  themeChoices, layoutToast, soundsFor, noteShown, modTab, unsavedKey, unsavedTabs, editsInTab, markdownFile,
  editorLanguage, indentOf, withEnds, findAll, nextMatch, findCount, FOUND_MOST, draftName, commentAt, reviewReady,
  loginColor }
  from "../mods/herdr-fold/logic.js";
import { format } from "../mods/herdr-fold/timeline.js";

test("a tab nobody named after its program, an agent's first, else Terminal; an agent's icon; zoomed marked", () => {
  const space = { tabs: [{ id: "t1", name: "1", named: false, active: true, status: "working" },
    { id: "t2", name: "2", named: false }, { id: "t3", name: "notes", named: true, zoomed: true, status: "done" }] };
  const panes = [{ tab: "t1", program: { name: "zsh" } }, { tab: "t1", program: { name: "Claude", agent: true,
    icon: "claude.svg", tint: true } }, { tab: "t3", program: { name: "vim", icon: "vim.png" } }];
  assert.deepEqual(tabRows(space, panes), [
    { id: "t1", name: "Claude", active: true, status: "working", icon: "claude.svg", tint: true, unsaved: false },
    { id: "t2", name: "Terminal", active: false, status: null, icon: null, tint: false, unsaved: false },
    { id: "t3", name: "notes Z", active: false, status: "done", icon: null, tint: false, unsaved: false }]);
  assert.deepEqual(tabRows(undefined, panes), []);
});

test("a chat tab wears its agent's icon and state, its agent being a terminal with no pane", () => {
  const space = { tabs: [{ id: "t4", name: "Fix the page past the last one", named: true }] };
  const chats = { t4: { status: "working", program: { name: "Claude", agent: true, icon: "claude.svg", tint: true } } };
  assert.deepEqual(tabRows(space, [{ tab: "t4", program: { name: "herdr-fold" } }], chats), [
    { id: "t4", name: "Fix the page past the last one", active: false, status: "working", icon: "claude.svg",
      tint: true, unsaved: false }]);
});

test("an editor's tab: named for its file, herdr-fold its pane; its × a dot while unsaved", () => {
  const space = { id: "s1", tabs: [{ id: "t1", name: "config/limits.json" }, { id: "t2", name: "README.md" },
    { id: "t3", name: "config/logging.toml" }] };
  const panes = [{ tab: "t1", mod: "herdr-fold" }, { tab: "t2" }, { tab: "t3", mod: "herdr-fold" }];
  assert.equal(modTab(space, "config/limits.json", panes), "t1");
  assert.equal(modTab(space, "README.md", panes), null);                 // a terminal so named is no editor
  const unsaved = { [unsavedKey("s1", "config/limits.json")]: true, [unsavedKey("s2", "config/logging.toml")]: true };
  assert.deepEqual([...unsavedTabs(space, unsaved)], ["t1"]);
  assert.deepEqual(tabRows(space, panes, {}, new Set(), unsavedTabs(space, unsaved)).map((row) => row.unsaved),
    [true, false, false]);
});

test("a text file opens in the editor; what the preview draws stays there, its code a view away", () => {
  assert.deepEqual(["config/limits.json", "pyproject.toml", "Makefile", ".env", "docs/a.png", "docs/p.pdf",
    "docs/pagination.html", "icon.svg", "README.md", "notes.markdown"].map(editsInTab),
  [true, true, true, true, false, false, false, false, false, false]);
  assert.deepEqual(["README.md", "a.MARKDOWN", "a.txt"].map(markdownFile), [true, true, false]);
  assert.deepEqual(["a.json", "b.TOML", "c.py", "Makefile", "d.svg"].map(editorLanguage),
    ["json", "toml", "python", "text", "html"]);
});

test("a file's indent as its lines have it", () => {
  assert.deepEqual(indentOf('{\n  "page": {\n    "size": 25\n  }\n}\n'), { size: 2, hard: false });
  assert.deepEqual(indentOf("def a():\n    return 1\n"), { size: 4, hard: false });
  assert.deepEqual(indentOf("a:\n\tb\n\tc\n"), { size: 2, hard: true });
  assert.deepEqual(indentOf("plain\n"), { size: 2, hard: false });
});

test("a save keeps the file's line ends: a line typed into a CRLF file is written CRLF", () => {
  assert.equal(withEnds("a\r\nb\nc\n", "a\r\nb\r\n"), "a\r\nb\r\nc\r\n");
  assert.equal(withEnds("a\nb\n", "a\n"), "a\nb\n");
  assert.equal(withEnds("a\nb", null), "a\nb");
});

test("find: case aside, the next match from the cursor and back, round past either end", () => {
  const text = "page 1, Page 2, PAGE 3", matches = findAll(text, "page");
  assert.deepEqual(matches, [[0, 4], [8, 12], [16, 20]]);
  assert.deepEqual(findAll("a+b a+b", "a+b"), [[0, 3], [4, 7]]);       // the query is text, not a pattern
  assert.deepEqual(findAll(text, ""), []);
  assert.equal(findAll("aaaa", "a", 3).length, 3);
  assert.deepEqual([nextMatch(matches, 0), nextMatch(matches, 5), nextMatch(matches, 17)], [0, 1, 0]);
  assert.deepEqual([nextMatch(matches, 8, true), nextMatch(matches, 0, true), nextMatch(matches, 30, true)],
    [0, 2, 2]);
  assert.equal(nextMatch([], 0), -1);
  assert.deepEqual([findCount(1, matches, "page"), findCount(-1, [], "zz"), findCount(-1, [], "")],
    ["2 of 3", "No results", ""]);
  assert.equal(findCount(0, Array(FOUND_MOST).fill([0, 1]), "a"), `1 of ${FOUND_MOST}+`);
});

test("a draft's name is its file's hash, the same for the same path, no path in it", () => {
  const name = draftName("/Users/dev/lumen-api/.env");
  assert.match(name, /^[0-9a-f]{14}\.json$/);
  assert.equal(draftName("/Users/dev/lumen-api/.env"), name);
  assert.notEqual(draftName("/Users/dev/lumen-api/.env.local"), name);
});

test("an SVG's or a page's code goes above its picture as chosen, else where the room is taller than wide", () => {
  assert.equal(stacks(null, { width: 800, height: 600 }), false);
  assert.equal(stacks(null, { width: 400, height: 900 }), true);
  assert.equal(stacks(true, { width: 800, height: 600 }), true);
  assert.equal(stacks(false, { width: 400, height: 900 }), false);
  assert.equal(stacks(null, null), false);                          // not measured yet: side by side
});

// Settings' About (Panels Task 10): its rows in each state, the update said once
const NOON = Date.UTC(2026, 10, 13, 17, 30) / 1000;                  // a look's time, epoch seconds
const FOUND = { version: "0.3.0", latest: "0.3.0", newer: false, on: true, checked: NOON, error: null, updated: null,
  releases: "https://example.com/releases", how: "git pull in its folder, then ./install.sh" };
const at = (seconds) => `at ${format(new Date(seconds * 1000), "HH:mm")}`;

test("About says up to date and when it looked, or a newer one and how, or checked by hand", () => {
  const now = (NOON + 600) * 1000;                                            // ms, as Date.now()
  const current = aboutState(FOUND, { now });
  assert.deepEqual(current.state, { mark: "ok", title: "Up to date", note: `Checked ${at(NOON)}`, tone: "foreground",
    spin: false });
  assert.deepEqual(current.buttons.map((b) => b.label), ["What's new", "Check now"]);
  assert.equal(current.how, null);
  assert.equal(current.box, true);
  assert.deepEqual(current.credits, [[{ text: "Version 0.3.0" }]]);          // the LICENSE not read yet: no name
  const license = licenseOf(readFileSync(new URL("../mods/herdr-fold/LICENSE", import.meta.url), "utf8"));
  assert.deepEqual(aboutState(FOUND, { now, license }).credits, [[{ text: "Version 0.3.0" }],
    [{ text: `© ${license?.year}` }, { text: String(license?.name), url: license?.url }], [{ text: "MIT License" }]]);
  const newer = aboutState({ ...FOUND, latest: "0.4.0", newer: true }, { now });
  assert.deepEqual([newer.state.mark, newer.state.title, newer.how], ["up", "0.4.0 is out", FOUND.how]);
  assert.deepEqual(newer.buttons[0], { id: "first", label: "Release notes ↗", url: FOUND.releases });
  const earlier = aboutState(FOUND, { now: (NOON + 3 * 86400) * 1000 });
  assert.equal(earlier.state.note, `Checked on ${format(new Date(NOON * 1000), "MMM d")}`);   // another day: the day
  const hand = aboutState({ ...FOUND, on: false, checked: null, latest: null }, { now });
  assert.deepEqual([hand.state.title, hand.state.tone, hand.state.mark, hand.box], ["Checked by hand only", "muted",
    null, false]);
});

test("About says a failed look in the error's color with the last good one, a look under way with a spinner", () => {
  const now = (NOON + 600) * 1000;
  const failed = aboutState({ ...FOUND, error: "GitHub did not answer" }, { now });
  assert.deepEqual(failed.state, { mark: null, title: "Couldn't check", note: `Last checked ${at(NOON)}`,
    tone: "ansi1", spin: false });
  assert.equal(aboutState({ ...FOUND, error: "GitHub did not answer", checked: null }, { now }).state.note,
    "GitHub did not answer");
  assert.equal(aboutState({ ...FOUND, error: "GitHub did not answer", latest: "0.4.0", newer: true }, { now }).how,
    `0.4.0 is out: ${FOUND.how}`);
  const looking = aboutState(FOUND, { now, checking: true });
  assert.deepEqual([looking.state.title, looking.state.spin, looking.state.note], ["Checking for updates…", true, ""]);
  assert.equal(aboutState(null, { now }).state.spin, true);                   // not looked yet: looking
  const none = aboutState({ ...FOUND, version: null }, { now });              // never installed by the installer here
  assert.deepEqual([none.credits, none.buttons, none.box], [[], [], null]);
});

test("About's author is the mod's LICENSE's holder, a link to their page; the keys step its links and buttons", () => {
  assert.deepEqual(licenseOf("MIT License\n\nCopyright (c) 2026 Ada Lane (https://example.com/ada)\n\nPermission"),
    { kind: "MIT License", year: "2026", name: "Ada Lane", url: "https://example.com/ada" });
  assert.deepEqual(licenseOf("MIT License\n\nCopyright (c) 2025 Ada Lane\n"), { kind: "MIT License", year: "2025",
    name: "Ada Lane", url: null });
  assert.equal(licenseOf("no license here"), null);
  const license = { kind: "MIT License", year: "2026", name: "Ada Lane", url: "https://example.com/ada" };
  const now = NOON * 1000;
  assert.deepEqual(aboutTargets(aboutState(FOUND, { now, license })), ["author", "first", "check", "box", "notices"]);
  assert.deepEqual(aboutTargets(aboutState({ ...FOUND, version: null }, { now, license })), ["author", "notices"]);
  assert.deepEqual(aboutTargets(aboutState(FOUND, { now, license: { ...license, url: null } })),
    ["first", "check", "box", "notices"]);                                     // a name with no page: no link
});

test("Settings keeps one size, 600 × 380: its sections and the Herdr app's beside About's tallest state", () => {
  const now = NOON * 1000, room = SETTINGS.high - SETTINGS.head - 2 * SETTINGS.pad;
  const plain = aboutHeight(aboutState(FOUND, { now })), newer = aboutHeight(aboutState({ ...FOUND, latest: "0.4.0",
    newer: true }, { now }));
  assert.deepEqual([SETTINGS.wide, SETTINGS.high], [600, 380]);
  assert.equal(plain, ABOUT.head + ABOUT.gap + ABOUT.state + ABOUT.gap + ABOUT.box + ABOUT.gap + ABOUT.legal);
  assert.equal(newer - plain, ABOUT.howGap + ABOUT.how);
  assert.ok(newer <= room);                                                 // nothing grows, nothing is cut
  const rows = SECTIONS.length + 1 + APP_SECTIONS.length;                   // Application, their title, a row too
  assert.ok(rows * SETTINGS.row + (rows - 1) * 2 + SETTINGS.apart <= room, "every section in the list");
  for (const more of [{ error: "GitHub did not answer", latest: "0.4.0", newer: true }, { version: null },
    { on: false, checked: null }]) {
    assert.ok(aboutHeight(aboutState({ ...FOUND, ...more }, { now })) <= room);
  }
});

test("Settings opens at the section last looked at, General at first; ↑ ↓ step them, Tab its controls", () => {
  assert.deepEqual(SECTIONS, [["general", "General"], ["notifications", "Notifications"], ["about", "About"]]);
  // the app's own, under Application: each opens the app's Settings there (app.settings' sections), never shown here;
  // Alerts is Notifications' Herdr app alerts
  assert.deepEqual(APP_SECTIONS, [["look", "Look"], ["machines", "Machines"], ["updates", "Updates"],
    ["privacy", "Privacy"]]);
  assert.deepEqual([settingsSection(null), settingsSection("about"), settingsSection("gone"),
    settingsSection("look")], ["general", "about", "general", "general"]);
  assert.deepEqual([sectionStep("general", 1), sectionStep("about", 1), sectionStep("about", -1),
    sectionStep("general", -1)], ["notifications", "about", "notifications", "general"]);
  const about = aboutState(FOUND, { now: NOON * 1000 });
  assert.deepEqual(settingsTargets("general", about), ["opens"]);
  assert.deepEqual(settingsTargets("notifications", about), ["notes", "alerts"]);
  assert.deepEqual(settingsTargets("about", about), aboutTargets(about));
});

test("An agent waits on you: off, the layout's toast is herdr-fold's, closing each note; the sounds go", () => {
  const layout = `${JSON.stringify({ theme: "herdr-fold", children: [] }, null, 2)}\n`;
  const off = layoutToast(layout, false, "herdr-fold");
  assert.deepEqual(JSON.parse(String(off)), { theme: "herdr-fold", children: [], toast: "herdr-fold" });
  assert.equal(layoutToast(String(off), false, "herdr-fold"), null);                  // so already: nothing written
  assert.equal(layoutToast(String(off), true, "herdr-fold"), layout);                 // on: the app's own toast
  assert.equal(layoutToast(layout, true, "herdr-fold"), null);
  const mine = JSON.stringify({ toast: "my-toast" });
  assert.equal(layoutToast(mine, true, "herdr-fold"), null);                          // another mod's: left alone
  // the sounds: off keeps the person's own value to give back; on gives it back (theirs off: still off)
  const settings = JSON.stringify({ zoom: 1, sounds: { enabled: true, done: "a.mp3" } });
  const quiet = soundsFor(settings, false, null);
  assert.deepEqual([JSON.parse(quiet.text).sounds, quiet.kept, JSON.parse(quiet.text).zoom],
    [{ enabled: false, done: "a.mp3" }, true, 1]);
  assert.deepEqual([JSON.parse(soundsFor(quiet.text, true, true).text).sounds.enabled,
    soundsFor(quiet.text, true, true).kept], [true, null]);
  assert.equal(JSON.parse(soundsFor(quiet.text, true, false).text).sounds.enabled, false);
  assert.deepEqual([JSON.parse(soundsFor(null, false, null).text), soundsFor(null, false, null).kept],
    [{ sounds: { enabled: false } }, true]);                                            // no file yet: the default on
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  assert.match(source("main.js"), /"level" in shown && !shown\.part[^]*?closeOverlay\(shown\.overlay\)/);
  // errors always show: an error or a warning (notify()'s levels) drawn by herdr-fold's part, as the app's toast
  assert.deepEqual(["error", "warning", "info", "success", undefined].map((level) => noteShown(level)),
    [true, true, false, false, false]);
  assert.match(source("main.js"), /if \(noteShown\(shown\.level\)\) return void \(this\.note = shown\);/);
  assert.match(source("main.js"), /if \(this\.note\) return noteToast\(t, this\.note\);/);
  assert.match(source("settings.js"), /when an agent in another tab asks or finishes\. Errors "\s*\+ "always show\."/);
  assert.match(source("main.js"), /followNotes\(\)/);                                // at start: an install rewrote it
  assert.match(source("settings.js"), /"Herdr app alerts", false, \(\) => this\.appSection\("alerts"\)/);
});

test("one Settings: the sidebar's Settings, open or on its rail, and ⌘, open herdr-fold's; the app's from it", () => {
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const sidebar = source("sidebar.js"), settings = source("settings.js");
  const keys = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"));
  assert.equal(keys["layout:herdr-fold"]["cmd-,"], "herdr-fold.settings");
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  assert.deepEqual(find(root, "sidebar-footer")?.content, { mod: "herdr-fold", props: { part: "footer" } });
  assert.doesNotMatch(JSON.stringify(root), /workspace-chrome/);                // the app's footer ran app.settings
  assert.doesNotMatch(sidebar, /app\.settings/);
  assert.match(sidebar, /\["settings", "settings", "Settings",\s*\(\) => openSettings\(\)\]/);
  assert.match(sidebar, /\["machine", "plus", "Add machine…", \(\) => addMachine\(\)\]/);    // it opens a window
  assert.equal(sidebar.match(/FOOT\.map\(/g)?.length, 2);                        // open, and on its rail
  assert.match(settings, /\.child\("Settings"\)/);                                // its title, the one Settings
  assert.match(settings, /command\("app\.settings", \{ section \}\)/);           // Look … Privacy: the app's, there
});

test("the TUI's six in the app, a key each: a new space in a folder, Add machine, the dock, Restore, a file, a theme",
  () => {
    const keys = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"))["layout:herdr-fold"];
    assert.deepEqual(["ctrl-b shift-n", "ctrl-b shift-m", "cmd-shift-e", "cmd-shift-o", "cmd-shift-l", "cmd-k cmd-t"]
      .map((key) => keys[key]), ["herdr-fold.new-space", "herdr-fold.add-machine", "herdr-fold.column",
      "herdr-fold.restore", "herdr-fold.open-file", "herdr-fold.theme"]);
    const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
    for (const asked of ["new-space", "add-machine", "column", "restore", "open-file", "theme"]) {
      assert.match(main, new RegExp(`asked === "${asked}"`), asked);
    }
    // a list a key opens stands where the palette does, at the window's top centre
    const room = { width: 1280, height: 820 };
    assert.deepEqual(menuPlace(keyMenuBounds(room, 320), 200, room, 320),
      { x: 480, y: palettePlace(room, 320, 200).y });
  });

test("the TUI's navigation keys in herdr-fold's layout: spaces, tabs and agents, each shown in the palette", () => {
  const all = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"))["layout:herdr-fold"];
  const app = Object.fromEntries(Object.entries(all).filter(([, action]) => !String(action).startsWith("herdr-fold.")));
  assert.deepEqual(app, { ...Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => [`cmd-${n}`,
    `space.select:${n}`])), "cmd-down": "space.next", "cmd-up": "space.prev", "cmd-t": "tab.next", "cmd-r": "tab.prev",
  "cmd-d": "agent.next", "cmd-e": "agent.prev",
  ...Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => [`ctrl-b ${n}`, `tab.select:${n}`])),
  "ctrl-b w": "mod.open:picker" });
  // Cmd+← → stay the terminal's line start and end (the app's): its pane.go steps only a tab's splits, and the TUI's
  // cycle (the tab, the dock's view, its terminal) needs a view's focus the app does not report; the keys of two
  // strokes are the TUI's own, Ctrl+B's and Cmd+K's (the owner tried Ctrl+B, then w, from a terminal)
  const terminal = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8")).terminal;
  assert.ok(!["cmd-left", "cmd-right"].some((keys) => keys in terminal || keys in all));
  assert.ok(Object.keys(all).filter((keys) => keys.includes(" ")).every((keys) => /^(ctrl-b|cmd-k) \S+$/.test(keys)));
  assert.ok(!["cmd-shift-n", "cmd-shift-m", "cmd-shift-t"].some((keys) => keys in all));     // no stand-ins left
  const bound = Object.entries(all).map(([keys, action]) => ({ section: "layout:herdr-fold", keys, action }));
  const named = paletteEntries(["space.next", "tab.prev", "agent.next"].map((name) => ({ name, args: [], about: "" })),
    [], true);
  assert.deepEqual(Object.fromEntries(named.map((entry) => [entry.name, entryKey(entry, bound, "herdr-fold")])),
    { "space.next": "cmd-down", "tab.prev": "cmd-r", "agent.next": "cmd-d" });
});

test("Cmd+Shift+E hides the dock entirely or shows it as it was; Cmd+Shift+O brings back all that was hidden", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  assert.deepEqual(columnToggle(root), [["layout.hide", { id: PANEL }]]);
  const hidden = JSON.parse(JSON.stringify(root));
  find(hidden, PANEL).hidden = true;
  const shown = JSON.parse(JSON.stringify(root));
  const bottom = { shown: true, px: BOTTOM_PX };
  assert.deepEqual(columnToggle(hidden, bottom), [["layout.show", { id: PANEL }], ...railFollow(shown, bottom)]);
  // Restore panels: the views More hid (Issues on GitHub only), the dock, the terminal under the tab on its rail
  for (const view of ["search", "issues"]) find(hidden, view).hidden = true;
  assert.deepEqual(restoreCommands(hidden, false, bottom), [["layout.show", { id: "search" }],
    ["layout.show", { id: PANEL }], ...railFollow(shown, bottom)]);
  assert.deepEqual(restoreCommands(hidden, true, bottom).slice(0, 3).map(([, args]) => args.id),
    ["search", "issues", PANEL]);
  assert.deepEqual(restoreCommands(root, true, bottom), railFollow(root, bottom));
});

test("the theme picker: herdr-fold's themes by the TUI's names, in its order, the one in use checked", () => {
  const list = [{ name: "graphite", light: false, colors: { a: "1" } }, { name: "herdr-fold-nord", light: false,
    colors: { a: "2" } }, { name: "herdr-fold-dracula", light: false, colors: { a: "3" } },
  { name: "herdr-fold", light: false, colors: { a: "3" } }];
  const names = { "herdr-fold-dracula": "Dracula", "herdr-fold-nord": "Nord", "herdr-fold-gone": "Gone" };
  assert.deepEqual(themeChoices(list, names, "herdr-fold"), [{ name: "herdr-fold-dracula", label: "Dracula", on: true },
    { name: "herdr-fold-nord", label: "Nord", on: false }]);        // the layout's own: the one of its colors
  assert.deepEqual(themeChoices(list, names, "graphite").map((c) => c.on), [false, false]);
});

test("every new agent's way in decides by Open agents in in one place; a new space starts one, >_ a terminal", () => {
  const folder = new URL("../mods/herdr-fold/", import.meta.url);
  const mods = Object.fromEntries(readdirSync(folder).filter((name) => name.endsWith(".js") && name !== "helper.js")
    .map((name) => [name, readFileSync(new URL(name, folder), "utf8")]));
  const all = Object.values(mods).join("\n");
  assert.equal(all.match(/newAgent\(shared\(RECENT_AGENTS\), agentsOpen\(shared\(AGENTS_OPEN\)\)/g)?.length, 1);
  assert.match(mods["chat.js"], /export const nextAgent = /);
  for (const name of ["tabs.js", "title.js"]) assert.match(mods[name], /nextAgent\(/, name);
  // a space shown with shells alone gets its chat first, once (chat.js's firstChat, from the tab bar's copy): so does
  // one newSpace or the app's own picker made; newSpace itself starts only Terminal's CLI
  assert.match(mods["chat.js"], /export function firstChat\(/);
  assert.match(mods["main.js"], /firstChat\(/);
  assert.equal(all.match(/openChat\(\{ space: space\.id, agent, first: true \}\)/g)?.length, 1);
  const spaceMade = mods["chat.js"].slice(mods["chat.js"].indexOf("export async function newSpace"));
  assert.doesNotMatch(spaceMade.slice(0, spaceMade.indexOf("\n}\n")), /openChat/);
  // a space made by herdr-fold starts its agent too (newSpace), but home's stand-in, a terminal in the home folder
  const made = Object.entries(mods).flatMap(([name, text]) => (text.match(/command\("space\.new"/g) ?? [])
    .map(() => name));
  assert.deepEqual(made.sort(), ["chat.js", "spaces.js"]);
  assert.match(mods["spaces.js"], /export function openHome[^]*?command\("space\.new"/);
  for (const name of ["spaces.js", "sidebar.js", "files.js", "title.js"]) assert.match(mods[name], /newSpace\(/, name);
  assert.doesNotMatch(all, /mod: "new-menu"/);              // the app's list started each agent's CLI, as it was
});

test("an update's toast is said once: by the copy that marked it seen, with What's new", () => {
  const updated = { ...FOUND, updated: "0.3.0" };
  assert.deepEqual(updateNotice(updated, true), { title: "Updated to herdr-fold 0.3.0", body: "What's new",
    level: "success", action: { name: "herdr-fold.whats-new" } });
  assert.equal(updateNotice(updated, false), null);                          // another copy, or a sidebar, said it
  assert.equal(updateNotice(FOUND, true), null);                             // nothing new installed
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

test("the title row keeps the traffic lights' room at each end on macOS, else the window's buttons', else PAD", () => {
  const root = { traffic_lights: [17, 9.5] }, mac = { platform: "macos", titlebar: "none", fullscreen: false };
  assert.equal(titleSide(root, mac, 1, 102), 81);
  assert.equal(titleSide(root, mac, 2, 102), 40.5);                   // the mod's px follow the zoom, the lights not
  assert.equal(titleSide(root, { ...mac, fullscreen: true }, 1, 102), PAD);
  assert.equal(titleSide({}, mac, 1, 102), PAD);
  assert.equal(titleSide(root, { platform: "linux", titlebar: "none", buttons: true }, 1, 102), 102);
  assert.equal(titleSide(root, { platform: "linux", titlebar: "system", buttons: false }, 1, 102), PAD);
});

test("the command field: as drawn, else the room between the row's ends, else its mark alone (0)", () => {
  assert.equal(FIELD, 300);                                            // commands.html's B
  assert.equal(fieldWidth(null, 81), FIELD);                           // not measured yet
  assert.equal(fieldWidth(1470, 81), FIELD);
  assert.equal(fieldWidth(2 * 81 + 200, 81), 200);
  assert.equal(fieldWidth(2 * 81 + FIELD_LEAST, 81), FIELD_LEAST);
  assert.equal(fieldWidth(2 * 81 + FIELD_LEAST - 1, 81), 0);
});

test("the palette's key: herdr-fold's own as bound, the layout's over global, in the platform's words", () => {
  const own = { section: "layout:herdr-fold", keys: "cmd-shift-p", action: "herdr-fold.palette" };
  const app = { section: "global", keys: "cmd-shift-p", action: "app.palette" };
  assert.equal(paletteKey([app, own], true, "herdr-fold"), "⌘⇧P");
  assert.equal(paletteKey([app, own], false, "herdr-fold"), "Ctrl+Shift+P");
  assert.equal(paletteKey([app, own], true, "main"), null);           // the app's own palette's key: not this one
  assert.equal(paletteKey([{ ...own, section: "global" }], true, "main"), "⌘⇧P");
  assert.equal(paletteKey([own, { ...own, section: "global", keys: "cmd-k" }], true, "herdr-fold"), "⌘⇧P");
  assert.equal(paletteKey([{ ...own, keys: "cmd--" }], true, "herdr-fold"), "⌘-");
  assert.equal(paletteKey([{ ...own, keys: "cmd-k cmd-p" }], true, "herdr-fold"), "⌘K ⌘P");
  assert.equal(paletteKey([], true, "herdr-fold"), null);
});

test("a key's parts as its caps read: macOS's signs, else words; a named key by its sign or name", () => {
  assert.deepEqual(keyNames("cmd-shift-]", true), [["⌘", "⇧", "]"]]);
  assert.deepEqual(keyNames("cmd-shift-]", false), [["Ctrl", "Shift", "]"]]);
  assert.deepEqual(keyNames("f2", true), [["F2"]]);
  assert.deepEqual(keyNames("cmd-shift-enter", true), [["⌘", "⇧", "↩"]]);
  assert.deepEqual(keyNames("cmd-alt-left", false), [["Ctrl", "Alt", "←"]]);
  assert.deepEqual(keyNames("cmd--", true), [["⌘", "-"]]);
  assert.deepEqual(keyNames("cmd-k cmd-t", true), [["⌘", "K"], ["⌘", "T"]]);
  assert.equal(keyWord("cmd-shift-p", true), "⌘⇧P");
  assert.equal(keyWord("ctrl-shift-p", false), "Ctrl+Shift+P");
});

test("the palette's entries: the app's, named and grouped as its palette, a layout each, the rest titled", () => {
  const commands = ["tab.new", "pane.split", "pane.go", "mod.open", "window.close", "layout.switch", "app.theme",
    "space.move", "tab.select", "terminal.kill", "app.palette", "app.frobnicate", "space.new"].map((name) => ({ name,
    args: name === "space.move" ? [{ name: "id", required: true }] : name === "terminal.kill"
      ? [{ name: "terminal", required: true }] : [], about: name === "app.frobnicate" ? "Twist the knobs." : "" }));
  const mac = paletteEntries(commands, ["main", "herdr-fold"], true);
  assert.deepEqual(mac.map((e) => e.title), ["New tab", "Go to space or tab…", "Split right", "Split down",
    "Focus pane left", "Focus pane right", "Focus pane up", "Focus pane down", "New space", "Next layout",
    "Layout: Herdr", "Layout: herdr-fold", "Theme: graphite", "Theme: ink", "Theme: moss", "Theme: atom one dark",
    "Frobnicate app"]);
  assert.deepEqual([...new Set(mac.map((e) => e.group))], ["Tab", "Pane", "Space", "Layout", "App"]);
  assert.equal(mac.find((e) => e.title === "Frobnicate app")?.words, "Twist the knobs.");
  assert.deepEqual(mac.find((e) => e.title === "Split down")?.args, { direction: "down" });
  assert.equal(mac.find((e) => e.title === "Split down")?.id, 'pane.split:{"direction":"down"}');
  const other = paletteEntries(commands, [], false);
  assert.ok(other.some((e) => e.title === "Close window"));          // the window's own buttons' commands off macOS
  assert.ok(!mac.some((e) => e.name === "window.close"));
  assert.ok(PALETTE_NAMED.every(([, , group]) => PALETTE_GROUPS.includes(group)));
  assert.equal(new Set(PALETTE_NAMED.map(([, , , title]) => title)).size, PALETTE_NAMED.length);   // one name each
  // one Settings: herdr-fold's, the app's sections in it, found by the app's words too
  assert.ok(!PALETTE_NAMED.some(([name]) => name === "app.settings"));
  assert.ok(!paletteEntries([{ name: "app.settings", args: [], about: "" }], [], true).length);
  assert.match(String(PALETTE_OWNED.find(([name]) => name === "herdr-fold.settings")?.[2]), /\btheme\b.*\bmachines\b/);
});

test("the palette's own group: herdr-fold's commands after the app's groups, in their order, each its real key", () => {
  const commands = ["tab.new", "app.quit", "app.frobnicate", "zeta.run"].map((name) => ({ name, args: [], about: "" }));
  const own = paletteEntries(commands, [], true, { github: true, plus: "New chat" });
  assert.deepEqual([...new Set(own.map((e) => e.group))], ["Tab", "App", "herdr-fold", "Zeta"]);
  assert.equal(PALETTE_GROUPS.at(-1), "herdr-fold");                  // after App: the app's groups stay first
  assert.deepEqual(own.filter((e) => e.group === "herdr-fold").map((e) => [e.title, e.name]), [
    ["Settings…", "herdr-fold.settings"], ["Files", "herdr-fold.files"], ["Search", "herdr-fold.search"],
    ["Changes", "herdr-fold.changes"], ["Issues", "herdr-fold.issues"], ["Agent", "herdr-fold.agent"],
    ["Agents", "herdr-fold.agents"], ["Usage", "herdr-fold.usage"], ["Chats", "herdr-fold.chats"],
    ["Collapse or expand sidebar", "herdr-fold.sidebar"], ["Collapse or expand panels", "herdr-fold.panels"],
    ["Show or hide the dock", "herdr-fold.column"], ["Restore panels", "herdr-fold.restore"],
    ["New chat", "herdr-fold.new-agent"], ["New space in a folder…", "herdr-fold.new-space"],
    ["Add machine…", "herdr-fold.add-machine"], ["Open file from output…", "herdr-fold.open-file"],
    ["Color theme…", "herdr-fold.theme"],
    ["Styleguide", "herdr-fold.styleguide"],
    ["Mark agent unread", "herdr-fold.unread"], ["Commit and push", "herdr-fold.commit-push"],
    ["Write commit message", "herdr-fold.write"]]);
  assert.ok(!paletteEntries(commands, [], true).some((e) => e.group === "herdr-fold"));      // asked for, else none
  const local = paletteEntries(commands, [], true, { github: false, plus: "New Codex" });
  assert.ok(!local.some((e) => e.name === "herdr-fold.issues"));     // off GitHub the key shows nothing: no row
  assert.equal(local.find((e) => e.name === "herdr-fold.new-agent")?.title, "New Codex");    // as + names it
  // what is not for a list: the palette itself, Commit (its message is typed in Changes), the update toast's
  for (const out of ["palette", "commit", "whats-new"]) {
    assert.ok(!PALETTE_OWNED.some(([name]) => name === `herdr-fold.${out}`));
  }
  // each key keys.json binds in the layout is a row's, but the palette's own; a row shows it (entryKey)
  const bound = Object.entries(JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"))[
    "layout:herdr-fold"]).map(([keys, action]) => ({ section: "layout:herdr-fold", keys, action: String(action) }));
  const mine = (/** @type {string} */ action) => /^herdr-fold\./.test(action) && action !== "herdr-fold.palette";
  for (const { keys, action } of bound.filter((k) => mine(k.action))) {
    assert.equal(entryKey(/** @type {any} */ (own.find((e) => e.name === action)), bound, "herdr-fold"), keys);
  }
});

test("an entry's key: the layout's own, else a global one the layout leaves, else a terminal's; none", () => {
  const list = [{ section: "global", keys: "cmd-t", action: "tab.new" },
    { section: "global", keys: "cmd-d", action: "pane.split:right" },
    { section: "global", keys: "cmd-n", action: "space.new" },
    { section: "global", keys: "cmd-p", action: "mod.open:picker" },
    { section: "layout:herdr-fold", keys: "cmd-n", action: "herdr-fold.new-agent" },
    { section: "layout:herdr-fold", keys: "cmd-shift-t", action: "tab.new" },
    { section: "terminal", keys: "cmd-f", action: "terminal.search" }];
  const at = (/** @type {string} */ name, args = {}) => entryKey({ name, args }, list, "herdr-fold");
  assert.equal(at("tab.new"), "cmd-shift-t");                         // the layout's own over global
  assert.equal(entryKey({ name: "tab.new", args: {} }, list, "main"), "cmd-t");
  assert.equal(at("pane.split", { direction: "right" }), "cmd-d");   // its first argument's value in the action
  assert.equal(at("pane.split", { direction: "down" }), null);
  assert.equal(at("mod.open", { name: "picker" }), "cmd-p");
  assert.equal(at("space.new"), null);                                // cmd-n starts an agent in the layout
  assert.equal(entryKey({ name: "space.new", args: {} }, list, "main"), "cmd-n");
  assert.equal(at("terminal.search"), "cmd-f");                       // a terminal's key, the one that runs it
});

test("the palette opens on the window's centre, 8 under its top (the app's least), over the title row's field", () => {
  assert.deepEqual(palettePlace({ width: 1470, height: 836 }, 600, 428), { x: 435, y: 8, width: 600, height: 428 });
  assert.deepEqual(palettePlace({ width: 500, height: 300 }, 600, 428), { x: 8, y: 8, width: 484, height: 284 });
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
  // a chat tab's agent, a terminal with no pane: the tab's own when no pane's agent is there; an ended one is not
  const chats = [{ address: "t8", state: "live", labels: { [CHAT_TAB]: "t9" } },
    { address: "t7", state: "exited", labels: { [CHAT_TAB]: "t6" } }];
  assert.deepEqual(issueAgent(agents, "t9", chats), { ...chats[0], chat: true });
  assert.equal(issueAgent(agents, "t1", chats)?.address, "t3");
  assert.equal(issueAgent(agents, "t6", chats), null);
  assert.equal(issueAgent(agents, undefined, chats), null);
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

/** The right dock as the layout has it: its card, one stack of the views and the Chats list under the row (its
 * header), the terminals, the rail; OVER changes a node by its id. @param {Record<string, any>} [over] */
function dock(over = {}) {
  const node = (/** @type {string} */ id, rest = {}) => ({ id, ...rest, ...(over[id] ?? {}) });
  return { id: "root", children: [node(PANEL, { size: { px: PANEL_PX }, children: [
    node(DOCK, { type: "stack", active: "files", children: [...VIEWS_APP, CHATS_BLOCK].map((id) => node(id)) }),
    node(TERMINALS), node(RAIL_BLOCK, { hidden: true })] })] };
}

test("one stack of views under the row: the shown ones, Issues on GitHub only, the chosen one while it can", () => {
  assert.deepEqual(VIEWS_APP, ["files", "search", "changes", "issues", "agent"]);       // the TUI's row, Chats aside
  assert.deepEqual(shownPanels(dock(), true), ["files", "search", "changes", "issues", "agent"]);
  assert.deepEqual(shownPanels(dock({ search: { hidden: true } }), false), ["files", "changes", "agent"]);
  assert.deepEqual(pickCommands(dock(), "agent", { github: false }),                  // Agent: off GitHub too
    [["layout.select", { stack: DOCK, child: "agent" }]]);
  assert.equal(shownView(dock(), true), "files");
  assert.equal(shownView(dock(), true, "changes"), "changes");                    // a space's own choice
  assert.equal(shownView(dock({ [DOCK]: { active: "issues" } }), false), "files"); // off GitHub: another
  assert.deepEqual(shownPanels({ id: "root" }, true), []);                       // another layout: none
});

test("a view's button or key shows it in the stack, hidden in More: shown again, the dock opened from its rail", () => {
  assert.deepEqual(pickCommands(dock(), "changes", { github: true }),
    [["layout.select", { stack: DOCK, child: "changes" }]]);
  assert.deepEqual(pickCommands(dock(), "files", { github: true }), []);          // shown already: nothing
  assert.deepEqual(pickCommands(dock({ search: { hidden: true } }), "search", { github: true }),
    [["layout.show", { id: "search" }], ["layout.select", { stack: DOCK, child: "search" }]]);
  assert.deepEqual(pickCommands(dock(), "issues", { github: false }), []);       // off GitHub: left as it is
  assert.deepEqual(pickCommands(dock(), "chats", { github: true }), []);         // the list: its own button's
  const railed = dock({ [PANEL]: { size: { px: RAIL } } });
  assert.deepEqual(pickCommands(railed, "issues", { github: true, kept: 420 }).slice(0, 2),
    [["layout.select", { stack: DOCK, child: "issues" }], ["layout.resize", { id: PANEL, px: 420 }]]);
});

test("More's views as the TUI's, each with its check; the last one shown stays; hidden, the stack moves on", () => {
  assert.deepEqual(panelChoices(dock({ search: { hidden: true } }), true).map((c) => [c.panel, c.on]),
    [["files", true], ["search", false], ["changes", true], ["issues", true], ["agent", true]]);
  assert.deepEqual(panelChoices(dock(), false).map((c) => c.panel), ["files", "search", "changes", "agent"]);
  const last = dock({ files: { hidden: true }, search: { hidden: true }, issues: { hidden: true },
    agent: { hidden: true } });
  assert.deepEqual(panelChoices(last, true)[2], { panel: "changes", label: "Changes", on: true, off: true });
  assert.deepEqual(hideCommands(dock(), "files", true, true), [["layout.hide", { id: "files" }],
    ["layout.select", { stack: DOCK, child: "search" }]]);
  assert.deepEqual(hideCommands(last, "changes", true, true), []);                // one view stays shown
  assert.deepEqual(panelsFollow(dock({ [DOCK]: { active: "issues" } }), false, "issues"),
    [["layout.select", { stack: DOCK, child: "files" }]]);                       // off GitHub meanwhile
  assert.deepEqual(panelsFollow(dock({ [DOCK]: { active: CHATS_BLOCK } }), true, "changes"), []);   // the list stays
});

test("each space keeps its own view, a new one starting on Files; spaces gone drop out as one is kept", () => {
  assert.equal(chosenFor({ sp1: "changes", sp2: "search" }, "sp2"), "search");
  assert.equal(chosenFor({ sp1: "changes" }, "sp3"), "files");                   // a new space
  assert.equal(chosenFor("changes", "sp1"), "files");                           // an older version's one for all
  assert.equal(chosenFor(null, null), "files");
  assert.deepEqual(keepChosen({ sp1: "changes", gone: "issues" }, "sp2", "search", new Set(["sp1", "sp2"])),
    { sp1: "changes", sp2: "search" });
  assert.deepEqual(keepChosen("changes", "sp1", "issues", new Set(["sp1"])), { sp1: "issues" });
  // as the TUI's: the kept one while it is on the row, else Files, else the row's first; never another space's
  assert.equal(shownView(dock({ [DOCK]: { active: "changes" } }), true, chosenFor({}, "sp9")), "files");
  assert.equal(shownView(dock({ files: { hidden: true } }), true, "issues"), "issues");
  assert.equal(shownView(dock({ files: { hidden: true }, [DOCK]: { active: "changes" } }), false, "issues"),
    "search");
});

test("Chats over the view: its button again, Esc or another button brings a view back; shut, it opens", () => {
  const open = dock({ [DOCK]: { active: CHATS_BLOCK } });
  assert.deepEqual(chatsToggle(open, true, "changes"), [["layout.select", { stack: DOCK, child: "changes" }]]);
  assert.deepEqual(chatsToggle(open, false, "issues"), [["layout.select", { stack: DOCK, child: "files" }]]);
  assert.deepEqual(chatsToggle(dock(), true, "files"), [["layout.select", { stack: DOCK, child: CHATS_BLOCK }]]);
  const railed = dock({ [PANEL]: { size: { px: RAIL } } });
  assert.deepEqual(chatsToggle(railed, true, "files", 420).slice(0, 2),
    [["layout.select", { stack: DOCK, child: CHATS_BLOCK }], ["layout.resize", { id: PANEL, px: 420 }]]);
  // another button while the list shows: that view in its place
  assert.deepEqual(pickCommands(open, "search", { github: true }),
    [["layout.select", { stack: DOCK, child: "search" }]]);
  assert.deepEqual(pickCommands(dock({ [DOCK]: { active: CHATS_BLOCK }, search: { hidden: true } }), "search"),
    [["layout.show", { id: "search" }], ["layout.select", { stack: DOCK, child: "search" }]]);
});

test("Esc in the Chats list, or in its filter, closes it; Esc while a chat is renamed drops the name only", () => {
  const chats = readFileSync(new URL("../mods/herdr-fold/chats.js", import.meta.url), "utf8");
  const list = chats.slice(chats.indexOf("  list(t, rows)"), chats.indexOf("  members(t, row)"));
  assert.match(list, /on_key_down\(\(e, cx\) => this\.escape\(e, cx\)\)/);
  const at = chats.indexOf("  escape(e, cx)"), escape = chats.slice(at, chats.indexOf("\n  }\n", at));
  assert.match(escape, /e\.key !== "escape"/);
  assert.ok(escape.indexOf("this.naming") < escape.indexOf("this.close()"), "a name being typed is dropped first");
});

test("» and « sit at the tab bar's end, the left toggle's row, open, folded or hidden: never moving", () => {
  const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
  const at = panel.indexOf("export function panelToggle"), toggle = panel.slice(at, panel.indexOf("\n}\n", at));
  assert.doesNotMatch(toggle, /return div\(\)/, "drawn in every state");
  assert.match(toggle, /"chevrons-right"/);
  assert.match(toggle, /"chevrons-left"/);
  assert.doesNotMatch(panel, /"dock-fold"|"rail-open"/, "none in the dock's head or on the rail");
});

// the tabs' widths at 13 in the app's font (macOS's system font, measured), each with px 6 a side; Changes with its
// count after it (6 apart, 18 wide), Agent (Task 7) with its 14 px icon 6 before its name
const WORDS = /** @type {[string, number][]} */ ([["files", 27.79 + 12], ["search", 42.11 + 12],
  ["changes", 53.33 + 6 + TAB_COUNT + 12], ["issues", 38.32 + 12], ["agent", 14 + 6 + 35.65 + 12]]);

test("the dock's tabs, each as wide as its words; past the card's width the last leave, never the shown one", () => {
  const ids = WORDS.map(([id]) => id), need = WORDS.reduce((sum, [, w]) => sum + w, 0) + TAB_GAP * (WORDS.length - 1);
  assert.ok(need <= PANEL_PX - 2 * TABS_IN, `five tabs fit the card as it first opens: ${need.toFixed(1)}`);
  assert.deepEqual(tabFit(PANEL_PX, WORDS, "files"), { tabs: ids });
  assert.deepEqual(tabFit(200, WORDS, "files"), { tabs: ["files", "search"] });                 // the last first
  assert.deepEqual(tabFit(200, WORDS, "agent"), { tabs: ["files", "search", "agent"] });        // never the shown
  assert.deepEqual(tabFit(60, WORDS, "issues"), { tabs: ["issues"] });                         // the shown alone
  assert.deepEqual(tabFit(200, WORDS, null), { tabs: ["files", "search"] });                    // Chats' list shown
  assert.deepEqual(tabFit(120, WORDS.map(([id]) => [id, 0]), "files"), { tabs: ids });  // not drawn yet: all, then
});

test("a dock tab: h 28, px 6, radius 8, 13, its count after its name 18 high; the row 8 over and under, 6 at the "
  + "sides, the tabs 2 apart", () => {
  assert.deepEqual([TAB_H, TABS_PAD, TABS_SIDE, TAB_IN, TAB_GAP, TAB_COUNT], [28, 8, 6, 6, 2, 18]);
  assert.equal(TABS_H - 1 - TAB_H, 2 * TABS_PAD);                  // as much room above the tabs as under them
  assert.equal(TABS_IN + TAB_IN, 1 + PAD);       // the first tab's words in line with the views' words under them
  const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
  const at = panel.indexOf("const viewTab"), tab = panel.slice(at, panel.indexOf("\n\n", at));
  assert.match(tab, new RegExp(String.raw`\.h\(TAB_H\)\.px\(TAB_IN\)\.gap\(6\)\s*\.flex_none\(\)\.items_center\(\)`
    + String.raw`\.rounded\(8\)\.text_size\(13\)`));
  assert.match(tab, /text_color\(shown \|\| hovered \? t\.foreground : t\.muted\)/);     // muted, the shown one not
  assert.match(tab, /e\.bg\(hovered \? t\.hover\s*: t\.raised\)/);                          // the shown one raised
  assert.match(tab, /\.hover\(\(s\) => s\.bg\(t\.hover\)\.text_color\(t\.foreground\)\)/);
  assert.match(tab, /badge\(t, count, TAB_COUNT, 11\)/);
  assert.doesNotMatch(tab, /font_(bold|semibold)/, "the shown one by its pill, not its weight");
});

test("a list's rows stand 12 in on both sides: the list 6 in, a row 6 more, a tree's indent at the left", () => {
  for (const name of ["files.js", "main.js", "issues.js", "chats.js"]) {
    const source = readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /\.pl\(6\)|\.pr\(8\)|\.pl\(6 \+/, `${name}: a row's right as its left`);
  }
});

test("the tab bar's end over the dock: Chats, More, then » or «; the rail without Chats", () => {
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const tabs = source("tabs.js"), panel = source("panel.js"), parts = source("parts.js");
  const end = tabs.slice(tabs.indexOf("export const barEnd"), tabs.indexOf("\nexport class TabsView"));
  const order = ['"bar-chats", "sparkle"', '"bar-more", "ellipsis"', "panelToggle(t, open, acts.fold)"]
    .map((part) => end.indexOf(part));
  assert.ok(order.every((at, i) => at > 0 && (i === 0 || at > order[i - 1])), "Chats, More, » in that order");
  assert.match(end, /waiting \? `Chats · \$\{waiting\} waiting` : "Chats"/);              // the number in its tip
  assert.match(end, /lit: listed, dot: waiting \? t\.ansi3 : null/);
  // More has no dot: a newer herdr-fold is the status bar's to say, and its menu's one line under the views opens
  // Settings at About (Settings itself is the sidebar's and ⌘,'s)
  assert.match(end, /\{ size: 15, left: true, press: acts\.press \}/);
  assert.match(end, /menu \? null : "More"/);                             // its tip never over its own menu
  assert.match(panel, new RegExp(String.raw`\[\.\.\.\(chats \? \[chats, null\] : \[\]\), \.\.\.panels, null,\s*`
    + String.raw`\{ label: "About herdr-fold", act: \(\) => openSettings\("about"\) \}\], bounds\)`));
  assert.doesNotMatch(tabs + panel, /Settings…|Agents open in:/);
  assert.match(tabs, /\.child\(div\(\)\.flex_1\(\)\)\s*\.child\(barEnd\(t, bar, acts/);       // at the bar's end
  // the dot as center-chat.html's .wdot, 7 with a 2 px ring of the bar's fill (the window's level, canvas), its
  // centre on the icon's top-right corner as a count's badge sits: clear of the sparkle's arms and the ellipsis' dot
  assert.match(parts, /export const DOT = 7, RINGED = DOT \+ 4;/);
  assert.match(parts, new RegExp(String.raw`\.left\(\(BUTTON \+ size - RINGED\) / 2\)\s*`
    + String.raw`\.top\(\(BUTTON - size - RINGED\) / 2\)\.size\(RINGED\)\.rounded_full\(\)\.bg\(String\(dot\)\)`
    + String.raw`\.border_2\(\)\s*\.border_color\(t\.canvas\)`));
  assert.doesNotMatch(panel.slice(panel.indexOf("const RAILED")), /"chats", "sparkle"/);
  assert.doesNotMatch(panel, /function rowButton|"more", "ellipsis"/, "nothing of the bar's end in the dock");
});

test("a count's badge, as VS Code's activity bar's: 14 high, its centre on the icon's top-right corner", () => {
  assert.equal(BADGE, 14);
  const { left, top } = badgeSpot(14, 0);                           // a 14 icon, its top-right corner at 14, 0
  assert.deepEqual([left + BADGE / 2, top + BADGE / 2], [14, 0]);
  assert.ok(left < 14 && top + BADGE > 0 && left > 0, "over the icon's corner, a quarter of it");
  assert.deepEqual(badgeSpot(22.5, 7.5), { left: 15.5, top: 0.5 });    // the rail's: a 15 icon in its 30 square
  const parts = readFileSync(new URL("../mods/herdr-fold/parts.js", import.meta.url), "utf8");
  /** parts.js's statement NAME starts, to its end @param {string} name */
  const piece = (name) => parts.slice(parts.indexOf(name), parts.indexOf(";\n", parts.indexOf(name)));
  // round, BADGE high and at least as wide, its number 10 semibold on a line as high; out of the flow
  assert.match(piece("export const badge ="), /high = BADGE, text = 10\) => div\(\)\.h\(high\)\.min_w\(high\)/);
  assert.match(piece("export const badge ="), /\.text_size\(text\)\.line_height\(`\$\{high\}px`\)\.font_semibold\(\)/);
  assert.match(piece("export const countBadge ="), /div\(\)\.absolute\(\)\.left\(spot\.left\)\.top\(spot\.top\)/);
  // the rail's icon stands where it would without it: the badge hangs off the icon's own box
  const from = parts.indexOf("export function iconTab"), tab = parts.slice(from, parts.indexOf("\n}\n", from));
  assert.match(tab, /countBadge\(t, count, \(size \+ glyph\) \/ 2, \(size - glyph\) \/ 2\)/);
});

test("the dock's lists keep one inset: a head's field 12 in, a row's highlight 6 in, its first mark or word 12", () => {
  const src = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const chats = src("chats.js"), issues = src("issues.js"), files = src("files.js"), main = src("main.js");
  const raw = (/** @type {string[]} */ ...parts) => new RegExp(parts.join(""));
  // the heads: the field (Files' folder name) PAD from the card's top and sides
  assert.match(chats, raw(String.raw`h_flex\(\)\.flex_none\(\)\.p\(PAD\)\.pb\(6\)\.gap\(4\)\.items_center\(\)\s*`,
    String.raw`\.child\(field\(t, "chats-filter"`));
  assert.match(issues, raw(String.raw`h_flex\(\)\.flex_none\(\)\.p\(PAD\)\.pb\(6\)\.gap\(6\)\.items_center\(\)\s*`,
    String.raw`\.child\(field\(t, "issue-search"`));
  assert.match(main, raw(String.raw`v_flex\(\)\.flex_none\(\)\.p\(PAD\)\.gap\(6\)[^\n]*\n\s*`,
    String.raw`\.child\(field\(t, "search"`));
  assert.match(files, /h_flex\(\)\.h\(PAD \+ BUTTON\)\.flex_none\(\)\.pl\(PAD\)/);
  // the lists PAD / 2 in, where a row's highlight starts; its first mark or word PAD / 2 further in
  const scrolled = (/** @type {string} */ id) => raw(String.raw`id\("${id}"\)\.flex_1\(\)\.min_h\(0\)`,
    String.raw`\.overflow_y_scrollbar\(\)\.px\(PAD / 2\)\.pb\(PAD / 2\)`);
  assert.match(chats, scrolled("chats"));
  assert.match(issues, scrolled("issues"));
  assert.match(files, scrolled("files-tree"));
  assert.match(main, /div\(\)\.flex_1\(\)\.min_h\(0\)\.relative\(\)\.px\(PAD \/ 2\)\.pb\(PAD \/ 2\)\.text_size\(12\)/);
  assert.match(main, /id\(`hit-\$\{r\.path\}:\$\{r\.line\}`\)\.w_full\(\)\.h\(24\)\.flex_none\(\)\.px\(PAD \/ 2\)/);
  assert.match(files, /\.pl\(PAD \/ 2 \+ depth \* INDENT\)\.pr\(PAD \/ 2\)/);         // a tree's indent at the left
  assert.match(chats, /id\(`space-\$\{row\.name\}`\)\.h\(SPACE_ROW\)\.flex_none\(\)\.px\(PAD \/ 2\)/);
  assert.match(chats, /id\(`chat-\$\{key\}`\)\.h\(CHAT_ROW\)\.flex_none\(\)\.pl\(UNDER\)\.pr\(PAD \/ 2\)/);
  assert.match(chats, /const UNDER = PAD \/ 2 \+ CHEVRON \+ 6;/);      // a chat's mark under its space's name
  // what a list says in its first row's place, its words PAD in, as Issues'
  assert.match(chats, /h_flex\(\)\.min_h\(SPACE_ROW\)\.py\(2\)\.px\(PAD \/ 2\)\.items_center\(\)\.text_size\(12\)/);
  assert.match(issues, /h_flex\(\)\.min_h\(ROW\)\.flex_none\(\)\.px\(PAD \/ 2\)/);
  assert.doesNotMatch(chats, /\.p[xytblr]?\(8\)/, "Chats on the 12 px rhythm, none of its old 8s");
});

test("what was done or went wrong stands under the list, never over its rows: Issues and Chats, as the TUI's foot",
  () => {
    assert.equal(NOTE_MS, 4000);                  // as the TUI's last row: a done thing's line goes, an error stays
    const src = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
      "utf8");
    const issues = src("issues.js"), chats = src("chats.js"), parts = src("parts.js");
    const body = (/** @type {string} */ source, /** @type {string} */ name) => source.slice(source.indexOf(name),
      source.indexOf("\n  }\n", source.indexOf(name)));
    // Issues: its head, its list, then the foot's line; nothing of it beside Open and Closed
    assert.match(body(issues, "  render(t) {"), new RegExp(String.raw`\.children\(shown\.map\(\(issue\) => `
      + String.raw`this\.row\(t, issue\)\)\)\)\s*\.when\(Boolean\(foot\), \(e\) => e\.child\(footNote\(t, foot\)\)\)`));
    assert.doesNotMatch(body(issues, "  states(t, parts) {"), /this\.busy|this\.note/);
    // Chats: the filter right over the list, the line after it; the list's own failure in its first row's place
    const list = body(chats, "  list(t, rows) {");
    assert.ok(list.indexOf("this.note") > list.indexOf('id("chats")'), "the line under the list, not over it");
    assert.match(list, /\.when\(Boolean\(this\.note\), \(e\) => e\.child\(footNote\(t, this\.note\)\)\)/);
    assert.match(list, /this\.failed \? `Couldn't read the chats: \$\{this\.failed\}` : "Loading chats…"/);
    // one line for both, as Files' and Changes' problems: PAD in, PAD / 2 over it, 11, dim or ansi1; done things go
    assert.match(parts, new RegExp(String.raw`export const footNote = \(t, note\) => div\(\)\.flex_none\(\)`
      + String.raw`\.px\(PAD\)\.pt\(PAD / 2\)\.pb\(PAD\)`));
    assert.match(body(parts, "export function keepNote"), /!note\.error[^]*cx\.timer\.after\(NOTE_MS/);
    for (const [name, source] of [["issues.js", issues], ["chats.js", chats]]) {
      assert.doesNotMatch(source, /this\.note = (?!null)/, `${name}: its notes through keepNote()`);
    }
  });

test("Issues loading moves nothing: the list's first row stays put, the head's refresh turns to a spinner", () => {
  const one = { issues: [{ number: 42 }], error: null };
  const two = { issues: [{ number: 42 }, { number: 41 }], error: null };
  const parts = (/** @type {any} */ s) => issuesParts({ asked: false, listing: null, shown: 0, filtered: false,
    state: "open", ...s });
  // a refresh with a list shown: before, during, after, the list's first row is its first issue, nothing over it
  assert.deepEqual(parts({ listing: one, shown: 1 }), { refresh: "button", say: null });
  assert.deepEqual(parts({ asked: true, listing: one, shown: 1 }), { refresh: "spinner", say: null });
  assert.deepEqual(parts({ listing: two, shown: 2 }), { refresh: "button", say: null });
  // the first load, a failure, none found: said in the first row's place, which the rows then take, faint as the
  // TUI's and the other views' empty lists; the first load says it there alone, Refresh as it is
  assert.deepEqual(parts({ asked: true }), { refresh: "button", say: ["Loading issues…", "dim"] });
  assert.deepEqual(parts({ asked: true, listing: { issues: [], error: "x" } }).refresh, "spinner");
  assert.deepEqual(parts({ listing: { issues: [], error: "gh: not signed in" } }).say, ["gh: not signed in", "ansi1"]);
  assert.deepEqual(parts({ listing: { issues: [], error: null } }).say, ["No open issues", "dim"]);
  assert.deepEqual(parts({ listing: one, filtered: true }).say, ["No issues match", "dim"]);
  // drawn so: the head (the field, then Open and Closed with the refresh at their end) right over the list, no row
  // that comes and goes between them; what there is to say first in the list; the spinner as big as the button
  const issues = readFileSync(new URL("../mods/herdr-fold/issues.js", import.meta.url), "utf8");
  const body = (/** @type {string} */ name) => issues.slice(issues.indexOf(name), issues.indexOf("\n  }\n",
    issues.indexOf(name)));
  const render = body("  render(t) {");
  assert.match(render, new RegExp(String.raw`\.child\(this\.field\(t\)\)\s*\.child\(this\.states\(t, parts\)\)\s*`
    + String.raw`\.child\(v_flex\(\)\.id\("issues"\)`));
  assert.match(render, new RegExp(String.raw`\.when\(Boolean\(parts\.say\), \(e\) => e\.child\(this\.say\(t, `
    + String.raw`parts\.say\)\)\)\s*\.children\(`));
  assert.match(body("  states(t, parts) {"), /parts\.refresh === "spinner"/);
  assert.match(body("  states(t, parts) {"), /div\(\)\.id\("issue-loading"\)\.size\(BUTTON\)/);
  assert.match(body("  states(t, parts) {"), /tooltip\("Loading issues…"\)/);
  assert.match(body("  states(t, parts) {"), /iconButton\(t, "issue-refresh", "refresh-cw", "Refresh"/);
  assert.match(body("  say(t, [text, role]) {"), /\.min_h\(ROW\)/);              // a row's height, its words PAD in
});

test("the row's counts and Issues come from the focused folder's repository, no view having shown yet", async () => {
  /** @type {string[]} */
  const asked = [];
  const ask = {
    top: async (/** @type {string} */ cwd) => (asked.push(`top ${cwd}`), cwd.startsWith("/repo") ? "/repo" : null),
    status: async () => (asked.push("status"), { staged: [{}, {}], changes: [{}] }),
    github: async () => (asked.push("github"), "lumenworks/lumen-api"),
  };
  const known = new Map();
  assert.deepEqual(await repoTold({ cwd: "/repo/src", on: null }, ask, known),
    { root: "/repo", github: true, changed: 3 });
  assert.deepEqual(await repoTold({ cwd: "/repo", on: null }, ask, known),
    { root: "/repo", github: true, changed: 3 });
  assert.equal(asked.filter((a) => a === "github").length, 1);              // a repository's GitHub asked once
  assert.deepEqual(await repoTold({ cwd: "/tmp", on: null }, ask, known), { root: null, github: false, changed: 0 });
  assert.deepEqual(await repoTold({ cwd: null, on: null }, ask, known), { root: null, github: false, changed: 0 });
  const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
  const bar = main.slice(main.indexOf('if (part === "tabs")'), main.indexOf('if (part === "preview")'));
  assert.match(bar, /new RepoLook\(/, "the tab bar, which always shows, looks at the repository");
});

test("the layout with a terminal stays within the host's 16 levels for layout.set", () => {
  // the host refuses an argument nested deeper ("a host argument may not nest more than 16 levels deep", measured in
  // the demo: 16 by this count passes, 17 throws): {layout: tree}, the tree after withTerminal() added the tab's, at
  // the dock's foot or under the centre
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  const depth = (/** @type {any} */ v) => (v && typeof v === "object"
    ? 1 + Math.max(0, ...Object.values(v).map(depth)) : 0);
  const { tree } = withTerminal(root, "w1:t1", "w1/t1");
  for (const shown of [tree, placeTerminals(tree, "bottom").tree]) {
    assert.ok(depth({ layout: shown }) <= 16, `depth ${depth({ layout: shown })}`);
  }
});

test("a card keeps PAD inside on every side: the terminals' text, a view's words", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  const parts = readFileSync(new URL("../mods/herdr-fold/parts.js", import.meta.url), "utf8");
  const space = /^export const SPACE = \[([\d, ]+)\];/m.exec(parts)?.[1].split(",").map(Number) ?? [];
  assert.ok(space.includes(PAD) && space.includes(PAD / 2), "PAD and a row's pad, halfway in, on the scale");
  assert.ok(/^export \{ PAD \};/m.test(parts), "parts.js hands logic.js's PAD to the views, no value of its own");
  assert.deepEqual(root.terminal_padding, [PAD, PAD]);                          // the centre's and the dock's
});

/** herdr-fold's layout as the app has it, its tab's terminal in its stack, shown (withTerminal's, the follower's). */
function shipped() {
  const tree = withTerminal(JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8")),
    "w1:t1", "w1/t1").tree;
  find(tree, TERMINALS).active = terminalId("w1:t1");
  return tree;
}
/** The ids of node ID's children in ROOT. @param {any} root @param {string} id */
const kids = (root, id) => find(root, id).children.map((/** @type {any} */ c) => c.id);

test("folded to its rail, the dock puts the tab's terminal under the centre, as VS Code's panel; open, back", () => {
  const open = shipped();
  assert.deepEqual(kids(open, CENTER), ["main"]);                          // the tab alone while the dock is open
  assert.equal(terminalsAt(open), "dock");
  assert.equal(find(open, TERMINALS).size.weight, TERMINALS_WEIGHT);
  assert.equal(find(open, CENTER).gap, 8);                                  // the dock's gap over the terminal's card
  const down = placeTerminals(open, "bottom", { shown: true, px: 300 });
  assert.equal(down.changed, true);
  assert.deepEqual(kids(down.tree, CENTER), ["main", TERMINALS]);           // the centre's width, under the tab
  assert.deepEqual([find(down.tree, TERMINALS).size, find(down.tree, TERMINALS).hidden], [{ px: 300 }, false]);
  assert.deepEqual(kids(down.tree, PANEL), [DOCK, RAIL_BLOCK]);
  assert.equal(find(down.tree, TERMINALS).children.length, 2);             // its terminals go with it
  assert.equal(placeTerminals(down.tree, "bottom").changed, false);         // there already: nothing to write
  assert.equal(find(placeTerminals(open, "bottom", { shown: false }).tree, TERMINALS).hidden, true);   // as chosen
  const back = placeTerminals(down.tree, "dock");
  assert.deepEqual(kids(back.tree, PANEL), [DOCK, TERMINALS, RAIL_BLOCK]);  // back at the dock's foot, as it was
  assert.deepEqual([find(back.tree, TERMINALS).size, find(back.tree, TERMINALS).hidden],
    [{ weight: TERMINALS_WEIGHT }, false]);
  const depth = (/** @type {any} */ v) => (v && typeof v === "object" ? 1 + Math.max(0, ...Object.values(v).map(depth))
    : 0);
  assert.ok(depth({ layout: down.tree }) <= 16, `depth ${depth({ layout: down.tree })}`);   // the host's most
});

test("the dock's » folds it with its terminal under the centre at the height last dragged; « brings it back", () => {
  const open = shipped();
  const folded = railToggle(open, 368, { shown: true, px: 300 });
  assert.deepEqual(folded[0], ["layout.resize", { id: PANEL, px: RAIL }]);
  const set = folded.find(([name]) => name === "layout.set");
  assert.ok(set, "the terminal moved by a layout.set");
  assert.equal(terminalsAt(set[1].layout), "bottom");
  assert.deepEqual(folded.filter(([name, args]) => args.id === TERMINALS && name !== "layout.set"),
    [["layout.resize", { id: TERMINALS, px: 300 }], ["layout.show", { id: TERMINALS }]]);
  assert.deepEqual(folded.filter(([, args]) => [DOCK, RAIL_BLOCK].includes(args.id)),
    [["layout.hide", { id: DOCK }], ["layout.show", { id: RAIL_BLOCK }]]);
  // as the app has it then: the height dragged kept, hidden by the rail's Terminal kept for the next fold
  const railed = set[1].layout;
  Object.assign(find(railed, PANEL), { size: { px: RAIL } });
  Object.assign(find(railed, DOCK), { hidden: true });
  Object.assign(find(railed, RAIL_BLOCK), { hidden: false });
  find(railed, TERMINALS).size = { px: 280 };
  assert.equal(bottomPx(railed), 280);
  assert.equal(bottomPx(open), null);
  assert.deepEqual(railFollow(railed, { shown: true, px: 280 }), []);          // as it should be: nothing to do
  assert.equal(bottomShown(railed), true);
  assert.deepEqual(bottomToggle(railed), { commands: [["layout.hide", { id: TERMINALS }]], shown: false });
  find(railed, TERMINALS).hidden = true;
  assert.equal(bottomShown(railed), false);
  assert.deepEqual(railFollow(railed, { shown: false, px: 280 }), []);         // hidden stays hidden
  assert.deepEqual(bottomToggle(railed), { commands: [["layout.show", { id: TERMINALS }]], shown: true });
  assert.deepEqual(bottomToggle(open), { commands: [], shown: null });          // the dock open: its own foot's
  const opened = railToggle(railed, 368, { shown: false, px: 280 });
  const back = opened.find(([name]) => name === "layout.set");
  assert.ok(back && terminalsAt(back[1].layout) === "dock");
  assert.deepEqual(opened.filter(([name, args]) => args.id === TERMINALS && name !== "layout.set"),
    [["layout.resize", { id: TERMINALS, weight: TERMINALS_WEIGHT }], ["layout.show", { id: TERMINALS }]]);
  assert.equal(BOTTOM_PX, 240);                                                // its first height
});

test("Changes moves nothing: its list and Graph keep their place through a run, a failure, typing, an offer, a link",
  () => {
    const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
    const issues = readFileSync(new URL("../mods/herdr-fold/issues.js", import.meta.url), "utf8");
    const body = (/** @type {string} */ source, /** @type {string} */ name) => source.slice(source.indexOf(name),
      source.indexOf("\n  }\n", source.indexOf(name)));
    const composer = body(main, "  composer(t) {"), repository = body(main, "  repository(t) {");
    // above the list, two rows of the composer and nothing that comes and goes: the push offered is said in the
    // empty field, the issue the next commit fixes is a chip in it
    assert.equal(composer.match(/\.child\(h_flex\(\)\.gap\(8\)/g)?.length, 2);
    assert.doesNotMatch(composer, /fixesLine\(|\.when\(Boolean\(this\.offer\), \(e\) => e\.child\(div\(\)/);
    assert.match(composer, /this\.offer \?\? "Commit message"/);
    assert.match(composer, /\.when\(Boolean\(this\.linked\), \(e\) => e\.child\(fixesChip\(t, /);
    assert.match(issues, /export function fixesChip\(t, linked, unlink\)/);
    // a run: the sync's glyph a spinner, its tip the step; Commit keeps its own words
    assert.match(repository, /step \? div\(\)\.size\(14\)[^]*?frames\(SPINNER, 100\)[^]*?: icon\("refresh-cw"\)/);
    assert.match(repository, /step \?\? "Sync"/);
    assert.doesNotMatch(composer, /this\.busy \?\?/);
    // who writes, in ✦'s tip while the field holds words, a spinner in it then
    assert.match(composer, /\.tooltip\(writing \?\? "Write message"\)/);
    // a failure: the dock's foot line over the card's last strip, red until the next action or its ×
    assert.match(body(main, "  problem(t) {"), /\.absolute\(\)\.left_0\(\)\.right_0\(\)\.bottom_0\(\)/);
    assert.match(body(main, "  panel(t) {"), /return frame\.relative\(\)\.child\(this\.repository\(t\)\)/);
  });

test("folded, a tab with no terminal leaves the centre whole: no stand-in under it; one coming back shows it", () => {
  const open = shipped();
  const railed = (/** @type {string} */ active) => {
    const tree = placeTerminals(open, "bottom", { shown: true, px: 240 }).tree;
    Object.assign(find(tree, PANEL), { size: { px: RAIL } });
    Object.assign(find(tree, DOCK), { hidden: true });
    Object.assign(find(tree, RAIL_BLOCK), { hidden: false });
    find(tree, TERMINALS).active = active;
    return tree;
  };
  const none = railed("fold-terminal-none"), one = railed(terminalId("w1:t1"));
  assert.deepEqual(railFollow(none, { shown: true, px: 240 }), [["layout.hide", { id: TERMINALS }]]);
  find(none, TERMINALS).hidden = true;
  assert.deepEqual(railFollow(none, { shown: true, px: 240 }), []);            // stays out while there is none
  find(one, TERMINALS).hidden = true;                                          // as it was while there was none
  assert.deepEqual(railFollow(one, { shown: true, px: 240 }), [["layout.show", { id: TERMINALS }]]);
  assert.deepEqual(railFollow(one, { shown: false, px: 240 }), []);           // unless the rail's Terminal hid it
  // folded with none: it goes under the centre hidden, the choice kept as it was
  const nothing = JSON.parse(JSON.stringify(open));
  find(nothing, TERMINALS).active = "fold-terminal-none";
  const folded = railToggle(nothing, 368, { shown: true, px: 240 });
  assert.equal(find(folded.find(([name]) => name === "layout.set")[1].layout, TERMINALS).hidden, true);
  assert.deepEqual(folded.filter(([name, args]) => args.id === TERMINALS && name === "layout.hide").length, 1);
});

test("a view floating beside the rail is as tall as dragged: its head and 3 rows at least, the rail's height at most",
  () => {
    // the least: the float's head (36), the view's own head, 3 of its rows, the grip; each view's own
    const views = ["files", "chats", "search", "issues", "changes", "agent"];
    assert.deepEqual(Object.fromEntries(views.map((v) => [v, floatMin(v)])),
      { files: 36 + 38 + 3 * 26 + 12, chats: 36 + 50 + 26 + 2 * 24 + 12, search: 36 + 81 + 3 * 24 + 12,
        issues: 36 + 38 + 84 + 3 * 48 + 12, changes: 36 + 58 + 97 + 3 * 26 + 12 + 12,
        agent: 36 + 44 + 37 + 4 + 28 + 2 * 26 + 12 });       // its head, its health line, a section and two rows
    assert.equal(FLOAT_GRIP, 12);
    // the most: the rail's height, from the centre card's top under the tab bar to its foot over the status bar
    const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
    assert.equal(floatMax(700, root), 700);
    // as kept for the view, inside those; else the most; the rail not measured yet: a height that fits a laptop
    assert.equal(railFloatPx("files", { files: 300 }, 700, root), 300);
    assert.equal(railFloatPx("files", { files: 90 }, 700, root), floatMin("files"));
    assert.equal(railFloatPx("files", { files: 5000 }, 700, root), floatMax(700, root));
    assert.equal(railFloatPx("search", { files: 300 }, 700, root), floatMax(700, root));
    assert.equal(railFloatPx("files", null, null, root), 560);
    // kept per view, the others as they were; a drag clamped to the same bounds
    assert.deepEqual(keepFloat({ files: 300, gone: "x" }, "issues", 420), { files: 300, issues: 420 });
    assert.deepEqual(keepFloat("old", "files", 250), { files: 250 });
    assert.equal(dragPx({ y: 500, px: 400 }, 560, 200, 700), 460);
    assert.equal(dragPx({ y: 500, px: 400 }, 100, 200, 700), 200);
    assert.equal(dragPx({ y: 500, px: 400 }, 900, 200, 700), 700);
    // drawn so: the window as tall as its content (no height of its own), the grip at the panel's foot
    const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
    const at = panel.indexOf("export function openRail"), open = panel.slice(at, panel.indexOf("\n}\n", at));
    assert.doesNotMatch(open, /height:/);
    assert.match(panel, /cursor_row_resize\(\)/);
    assert.match(panel, /e\.click_count === 2 \? size\.toggle\(cx\) : size\.press\(e\)/);
  });

test("the rail's Terminal shows and hides the terminal under the centre, lit while shown; no window of its own", () => {
  const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
  const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
  assert.doesNotMatch(panel, /rail-terminal|float-head/);
  assert.doesNotMatch(main, /float-head/);
  const at = panel.indexOf("export function rail("), rail = panel.slice(at, panel.indexOf("\n}\n", at));
  assert.match(rail, /panel === "terminal" \? terminalPress\(\) : railPress\(panel, e\.bounds\)/);
  assert.match(rail, /active: lit/);
  assert.match(rail, /tip: off \? "No terminal in this tab" : label/);
});

test("the right dock folds to its rail and opens again, as its » and « and a drag do it", () => {
  /** @param {number} px @param {{ hidden?: boolean, rail?: boolean }} [shown] */
  const tree = (px, { hidden = false, rail = false } = {}) => dock({ [PANEL]: { hidden, size: { px } },
    [DOCK]: { hidden: rail }, [TERMINALS]: { hidden: rail }, [RAIL_BLOCK]: { hidden: !rail } });
  /** @param {boolean} open the card (its row over its view) and the terminal's, else the rail */
  const blocks = (open) => [[open ? "layout.show" : "layout.hide", { id: DOCK }],
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
  // dragged narrow: the rail's blocks at once, its width once let go (dockRest), never fighting the drag; dragged
  // wide again: the dock; hidden: nothing
  assert.deepEqual(railFollow(tree(120)), blocks(false));
  assert.deepEqual(railFollow(tree(300, { rail: true })), blocks(true));
  assert.deepEqual(railFollow(tree(RAIL, { rail: true })), []);
  assert.deepEqual(railFollow(tree(120, { hidden: true })), []);
  assert.equal(panelShown(tree(420)), true);
  assert.equal(panelShown(tree(420, { hidden: true })), false);
  assert.equal(panelShown({ id: "root" }), false);
  assert.equal(PANEL, "fold-panel");                       // herdr-fold's own id: the app's Settings leaves it alone
});

test("a side let go of comes to rest as the TUI's: a rail widened past 24 px opens as its toggle does, else the rail",
  () => {
    assert.deepEqual([UNFOLD, SETTLE], [24, 300]);         // the TUI's 3 cells; a drag's width unchanged that long
    // from its rail: a nudge back to the rail, a drag past UNFOLD the width it had open, however far it went
    assert.equal(restWidth(RAIL + UNFOLD, RAIL, RAIL, 368), RAIL);
    assert.equal(restWidth(RAIL + UNFOLD + 1, RAIL, RAIL, 368), 368);
    assert.equal(restWidth(300, RAIL, RAIL, 368), 368);
    assert.equal(restWidth(368, RAIL, RAIL, 368), null);   // « or a view's key opened it: as it is
    // from open: narrower than 160 the rail, else as dragged
    assert.equal(restWidth(120, 368, RAIL, 368), RAIL);
    assert.equal(restWidth(200, 368, RAIL, 368), null);
    // first seen (a start): a rail at its own width, an open one as it is; none: nothing
    assert.equal(restWidth(120, null, RAIL, 368), RAIL);
    assert.equal(restWidth(RAIL, null, RAIL, 368), null);
    assert.equal(restWidth(420, null, RAIL, 368), null);
    assert.equal(restWidth(null, RAIL, RAIL, 368), null);
  });

test("a side's rest counts once its own setting held: a pause mid-drag never turns a fold into an unfold", () => {
  const rest = (/** @type {number | null} */ from, /** @type {number} */ px) => {
    const to = restWidth(px, from, RAIL, 368);
    return to ?? px;
  };
  /** @param {any} seen @param {number} px */
  const step = (seen, px) => restAt(seen, px, (/** @type {number | null} */ from) => rest(from, px));
  // let go narrower than 160: set to the rail, which counts once it holds there
  const seen = { px: null, from: 368, pending: null };
  step(seen, 150);
  assert.deepEqual([seen.from, seen.pending], [368, RAIL]);
  step(seen, RAIL);
  assert.deepEqual([seen.from, seen.pending], [RAIL, null]);
  // a pause at 150 mid-drag set the rail, the drag went on to 145 and let go: still a fold, from the open width
  const paused = { px: null, from: 368, pending: null };
  step(paused, 150);
  step(paused, 145);
  assert.deepEqual([paused.from, paused.pending], [368, RAIL]);
  // a rail widened and let go: open as « opens it, which counts once it holds
  const rail = { px: null, from: RAIL, pending: null };
  step(rail, 130);
  assert.equal(rail.pending, 368);
  step(rail, 368);
  assert.deepEqual([rail.from, rail.pending], [368, null]);
  // let go where it may stay: rested there at once
  const open = { px: null, from: 368, pending: null };
  step(open, 300);
  assert.deepEqual([open.from, open.pending], [300, null]);
});

test("the right dock let go of: narrowed under 160 its rail, a rail widened the dock as « opens it; hidden, as it is",
  () => {
    /** @param {number} px @param {{ hidden?: boolean, rail?: boolean }} [shown] */
    const tree = (px, { hidden = false, rail = false } = {}) => dock({ [PANEL]: { hidden, size: { px } },
      [DOCK]: { hidden: rail }, [TERMINALS]: { hidden: rail }, [RAIL_BLOCK]: { hidden: !rail } });
    // narrowed while open: the rail's blocks came at once (railFollow), its width once let go
    assert.deepEqual(dockRest(tree(120, { rail: true }), 368, 420),
      { to: RAIL, open: false, commands: [["layout.resize", { id: PANEL, px: RAIL }]] });
    // a rail widened: the dock at the width it had, its card and terminal back, the rail gone
    assert.deepEqual(dockRest(tree(130, { rail: true }), RAIL, 420), { to: 420, open: true, commands: [
      ["layout.resize", { id: PANEL, px: 420 }], ["layout.show", { id: DOCK }], ["layout.show", { id: TERMINALS }],
      ["layout.hide", { id: RAIL_BLOCK }]] });
    assert.deepEqual(dockRest(tree(130, { rail: true }), RAIL, undefined).to, PANEL_PX);
    // a nudge: back to the rail; open as dragged: nothing to do, its width the one « opens to
    assert.deepEqual(dockRest(tree(90, { rail: true }), RAIL, 420).commands,
      [["layout.resize", { id: PANEL, px: RAIL }]]);
    assert.deepEqual(dockRest(tree(300), 368, 420), { to: 300, open: true, commands: [] });
    assert.deepEqual(dockRest(tree(120, { hidden: true }), 368, 420), { to: 120, open: false, commands: [] });
    // its terminal moves back from under the centre with it
    const folded = placeTerminals(shipped(), "bottom", { shown: true, px: 240 }).tree;
    Object.assign(find(folded, PANEL), { size: { px: 140 } });
    Object.assign(find(folded, DOCK), { hidden: true });
    Object.assign(find(folded, RAIL_BLOCK), { hidden: false });
    const back = dockRest(folded, RAIL, 400, { shown: true, px: 240 }).commands;
    assert.equal(terminalsAt(back.find(([name]) => name === "layout.set")[1].layout), "dock");
  });

test("the left sidebar let go of as the right dock: under 160 its rail, a rail widened past 24 px open again", () => {
  /** @param {number} px @param {boolean} [hidden] */
  const at = (px, hidden = false) => ({ id: "root", children: [{ id: "sidebar", size: { px }, hidden }] });
  assert.deepEqual([sidebarRail(true), sidebarRail(false), SIDEBAR_PX], [76, 44, 268]);
  assert.deepEqual(sidebarRest(at(140), 268, 300, true), { to: 76, open: false,
    commands: [["layout.resize", { id: "sidebar", px: 76 }]] });
  assert.deepEqual(sidebarRest(at(130), 76, 300, true), { to: 300, open: true,
    commands: [["layout.resize", { id: "sidebar", px: 300 }]] });
  assert.equal(sidebarRest(at(130), 76, undefined, true).to, SIDEBAR_PX);
  assert.deepEqual(sidebarRest(at(90), 76, 300, true).commands, [["layout.resize", { id: "sidebar", px: 76 }]]);
  assert.deepEqual(sidebarRest(at(320), 268, 300, true), { to: 320, open: true, commands: [] });
  assert.deepEqual(sidebarRest(at(140, true), 268, 300, true), { to: 140, open: false, commands: [] });
  assert.deepEqual(sidebarRest({ id: "root" }, null, 300, true), { to: null, open: false, commands: [] });
  // off macOS the rail is 44, but never under the layout's least (76 here): a nudge from there stays a nudge
  const least = (/** @type {number} */ px) => ({ id: "root", children: [{ id: "sidebar", size: { px }, min: 76 }] });
  assert.deepEqual(sidebarRest(least(90), 76, 300, false).commands, [["layout.resize", { id: "sidebar", px: 76 }]]);
  assert.equal(sidebarRest(least(110), 76, 300, false).to, 300);
});

test("the left sidebar is open or a rail, never hidden: shown again at once; its footer while open", () => {
  /** @param {number} px @param {{ hidden?: boolean, footer?: boolean }} [how] */
  const at = (px, { hidden = false, footer = true } = {}) => ({ id: "root", children: [
    { id: "sidebar", size: { px }, hidden, children: [{ id: "sidebar-footer", hidden: !footer }] }] });
  assert.deepEqual(sidebarFollow(at(76)), [["layout.hide", { id: "sidebar-footer" }]]);
  assert.deepEqual(sidebarFollow(at(76, { footer: false })), []);
  assert.deepEqual(sidebarFollow(at(268, { footer: false })), [["layout.show", { id: "sidebar-footer" }]]);
  assert.deepEqual(sidebarFollow(at(268)), []);
  assert.deepEqual(sidebarFollow(at(268, { hidden: true })), [["layout.show", { id: "sidebar" }]]);
  assert.deepEqual(sidebarFollow({ id: "root" }), []);
  // the toggle: open, folded to its rail; a rail, open the width it had; hidden (the app's own key), shown open
  assert.deepEqual(sidebarToggle(at(268), true, 300), [["layout.resize", { id: "sidebar", px: 76 }]]);
  assert.deepEqual(sidebarToggle(at(76), true, 300), [["layout.resize", { id: "sidebar", px: 300 }]]);
  assert.deepEqual(sidebarToggle(at(76), false, undefined), [["layout.resize", { id: "sidebar", px: SIDEBAR_PX }]]);
  assert.deepEqual(sidebarToggle(at(268, { hidden: true }), true, 300), [["layout.show", { id: "sidebar" }]]);
  assert.deepEqual(sidebarToggle(at(76, { hidden: true }), true, 300), [["layout.show", { id: "sidebar" }],
    ["layout.resize", { id: "sidebar", px: 300 }]]);
  assert.deepEqual(sidebarToggle({ id: "root" }, true, 300), []);
});

test("a float beside a rail is gone once its side opens or hides: never the panel and its float at once", () => {
  const side = (px, hidden = false) => ({ id: "root", children: [{ id: "sidebar", size: { px }, hidden }] });
  assert.equal(floatStale("spaces", side(76)), false);
  assert.equal(floatStale("spaces", side(268)), true);
  assert.equal(floatStale("spaces", side(76, true)), true);
  const right = (px, hidden = false) => dock({ [PANEL]: { hidden, size: { px } } });
  for (const view of ["files", "changes", "chats"]) {
    assert.equal(floatStale(view, right(RAIL)), false);
    assert.equal(floatStale(view, right(PANEL_PX)), true);
    assert.equal(floatStale(view, right(RAIL, true)), true);
  }
  // a side's float as its shared value names it, else none
  assert.deepEqual(floating({ panel: "changes", overlay: "o7" }), { panel: "changes", overlay: "o7" });
  assert.equal(floating({ panel: "changes" }), null);
  assert.equal(floating("o7"), null);
  assert.equal(floating(null), null);
});

test("a press outside a float closes it, never one in a menu it opened nor on its side's own controls", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  Object.assign(find(root, PANEL), { size: { px: RAIL } });
  Object.assign(find(root, "sidebar"), { size: { px: RAIL } });
  const end = toggleRoom(root, 26) + 3 * 26 + 2 * 4;      // the tab bar's ✦, More and «, from the window's edge
  const at = (/** @type {number} */ x, /** @type {number} */ y) => ({ x, y });
  // a view's float: the centre, a tab, the title row close it; the rail's column and the bar's end are its own
  assert.equal(pressCloses("changes", at(500, 400), root, 1280, end, false), true);
  assert.equal(pressCloses("changes", at(300, 60), root, 1280, end, false), true);       // a tab
  assert.equal(pressCloses("changes", at(1250, 20), root, 1280, end, false), true);      // the title row
  assert.equal(pressCloses("changes", at(1230, 300), root, 1280, end, false), false);    // a rail icon
  assert.equal(pressCloses("changes", at(1170, 60), root, 1280, end, false), false);     // ✦
  assert.equal(pressCloses("changes", at(1230, 60), root, 1280, end, false), false);     // «
  assert.equal(pressCloses("changes", at(40, 300), root, 1280, end, false), true);       // the left rail
  // Spaces' float: the left rail and its head (its toggle) are its own; the right rail is not
  assert.equal(pressCloses("spaces", at(40, 300), root, 1280, end, false), false);
  assert.equal(pressCloses("spaces", at(40, 60), root, 1280, end, false), false);
  assert.equal(pressCloses("spaces", at(1230, 300), root, 1280, end, false), true);
  assert.equal(pressCloses("spaces", at(40, 20), root, 1280, end, false), true);
  // while a menu or a window of the mod is up, a press anywhere is the float's own (a choice in its menu)
  assert.equal(pressCloses("changes", at(500, 400), root, 1280, end, true), false);
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const sidebar = source("sidebar.js"), menus = source("menus.js"), main = source("main.js");
  assert.match(sidebar, /\.on_mouse_down_out\(\(e\) => \{\s+if \(pressCloses\(panel, e\.position, layout\(\)/);
  assert.match(sidebar, /menusOpen\(\)\.length > 0 \|\| settingsOpen\(\)/);
  // a menu marked up as it opens, forgotten however it closes (its choice, Esc, a press beside); none after a start
  assert.match(menus, /setShared\(MENUS, \[\.\.\.menusOpen\(\), openOverlay\(/);
  assert.match(main.slice(main.indexOf("  async close() {")), /if \(this\.popup\) menuGone\(this\.popup\.overlay\);/);
  assert.match(main, /forgetFloats\(\);\s+forgetMenus\(\);/);
});

test("a float always opens beside its rail, the one floating before closed first: no window kept by its key", () => {
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const body = (/** @type {string} */ text, /** @type {string} */ name) => text.slice(text.indexOf(name),
    text.indexOf("\n}\n", text.indexOf(name)));
  const rail = body(source("panel.js"), "export function openRail("), dock = body(source("sidebar.js"),
    "function openFloat(");
  for (const [open, mark] of [[rail, "RAIL_FLOAT"], [dock, "DOCK_FLOAT"]]) {
    assert.doesNotMatch(open, /key:/);
    assert.match(open, new RegExp(`shutFloat\\(${mark}\\);`));
    assert.ok(open.indexOf("shutFloat(") < open.indexOf("openOverlay("));
  }
  assert.doesNotMatch(rail, /bounds \?/);                  // a key's float beside the rail too
});

test("both rails as one: on the side's level, their first icons level, each toggle over its rail, one pair of tips",
  () => {
    const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
    const rail = find(root, RAIL_BLOCK);
    assert.deepEqual([find(root, "sidebar").background, rail.background, rail.radius], ["chrome", "chrome", 10]);
    assert.equal(rail.border, undefined);                  // its icons start where the left's do: no edge over them
    assert.equal(find(root, "sidebar-trigger"), null);    // the left's toggle is in its head, over its rail
    assert.deepEqual(find(root, "top").children.map((/** @type {any} */ c) => c.id), ["tabs"]);
    const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
      "utf8");
    const sidebar = source("sidebar.js"), panel = source("panel.js");
    // the first icon: the left one under its head, the right one inside the work body's pad, both at one height
    const left = Number(/v_flex\(\)\.flex_1\(\)\.pt\((\d+)\)\.gap\(12\)\.items_center\(\)/.exec(sidebar)?.[1]);
    const right = Number(/id\("panel-rail"\)\.size_full\(\)\.items_center\(\)\.pt\((\d+)\)/.exec(panel)?.[1]);
    assert.equal(find(root, "title").size.px + find(root, "sidebar-head").size.px + left,
      find(root, "title").size.px + find(root, "top").size.px + find(root, "work-body").padding + right);
    // the toggles: the left's in its head, centred over its rail when folded, as the right's « over its own
    const head = sidebar.slice(sidebar.indexOf("export function sidebarHead"), sidebar.indexOf("\n}\n",
      sidebar.indexOf("export function sidebarHead")));
    assert.match(head, /\.when\(!open, \(e\) => e\.justify_center\(\)\)/);
    assert.match(head, /open \? "Collapse to icons" : "Expand panels"/);
    assert.match(panel, /open \? "Collapse to icons"\s+: "Expand panels"/);
    assert.doesNotMatch(sidebar, /Hide sidebar|Show sidebar|sidebarTrigger/);
  });

test("Cmd+Option+B folds and opens the right dock, Cmd+B's twin for the left", () => {
  const keys = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"));
  assert.equal(keys["layout:herdr-fold"]["cmd-alt-b"], "herdr-fold.panels");
  const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
  assert.match(main, /else if \(asked === "panels"\) foldDock\(\);/);
});

test("with Chats open, a press on a rail icon, » or « closes it and does its own action at once; More keeps it",
  () => {
    // » with the list in the dock's view place: the view back, then the fold; « opens; a rail never has the list
    const tree = (/** @type {number} */ px, /** @type {string} */ active) => dock({ [PANEL]: { size: { px } },
      [DOCK]: { active, hidden: px < 160 }, [TERMINALS]: { hidden: px < 160 }, [RAIL_BLOCK]: { hidden: px >= 160 } });
    const folded = foldCommands(tree(368, CHATS_BLOCK), false, "changes", 368);
    assert.deepEqual(folded[0], ["layout.select", { stack: DOCK, child: "changes" }]);
    assert.deepEqual(folded.slice(1), railToggle(tree(368, CHATS_BLOCK), 368));
    assert.deepEqual(foldCommands(tree(368, "files"), false, "files", 368), railToggle(tree(368, "files"), 368));
    assert.deepEqual(foldCommands(tree(RAIL, "files"), false, "files", 400), railToggle(tree(RAIL, "files"), 400));
    const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
      "utf8");
    const panel = source("panel.js"), tabs = source("tabs.js"), sidebar = source("sidebar.js");
    assert.match(panel, /export const foldDock = \(\) => runPanel\(foldCommands\(layout\(\)/);
    // More: the float or the list closed, its menu opened; while Chats shows, kept, More listing Show archived first;
    // the rail's Terminal: the float closed, the terminal toggled
    assert.match(tabs, new RegExp(String.raw`if \(!listed\) closeChats\(\);\s*`
      + String.raw`openMore\(this\.menus, this\.more, listed \? archivedChoice\(\) : null\);`));
    assert.match(panel.slice(panel.indexOf("export function closeChats")),
      /shutFloat\(RAIL_FLOAT\);\s+if \(chatsShown\(\)\) toggleChats\(\);/);
    assert.match(panel.slice(panel.indexOf("export function terminalPress")),
      /shutFloat\(RAIL_FLOAT\);\s+toggleBottom\(\);/);
    // the folded sidebar's own buttons close Spaces' float as they act
    assert.match(sidebar, /`dock-\$\{id\}`, glyph, name,\s*\(\) => \(shutFloat\(DOCK_FLOAT\), act\(\)\)/);
  });

test("Esc in a float goes to its view first (a field, a name, a list), the keys back to the float: the next closes it",
  () => {
    const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
      "utf8");
    const sidebar = source("sidebar.js"), agent = source("agent.js"), chats = source("chats.js");
    const float = sidebar.slice(sidebar.indexOf("export function floatPanel("));
    // the body: an Esc its view let go on (Search's query, the commit message, a name dropped) hands the keys back
    assert.match(float, /\.on_key_down\(\(e, cx\) => \{\s+if \(e\.key !== "escape" \|\| !focus\) return;\s+/);
    assert.match(float, /!focus\) return;\s+cx\.stop_propagation\(\);\s+focus\.focus\(\);/);
    // the Agent view's list, its ways to add, its form: shut by Esc, which goes on to the float
    assert.match(agent, /if \(e\.key === "escape"\) return void this\.list\(false, cx\);/);
    assert.match(agent, /if \(e\.key === "escape"\) return void this\.showWays\(false, cx\);/);
    assert.match(agent, /if \(e\.key === "escape"\) return void this\.dropForm\(cx\);/);
    // Chats: a name or a question dropped, the filter's words cleared, else the list (the float) closed
    const from = chats.indexOf("  escape(e, cx) {"), escape = chats.slice(from, chats.indexOf("\n  }\n", from));
    assert.match(escape, /this\.naming = this\.asking = null;\s+this\.focus\(\);/);
    assert.match(escape, /if \(this\.typed\) \{\s+this\.find\.set_value\(""\);/);
  });

test("a float's height dragged is kept for its panel, Spaces' too; it opens beside its rail at that height", () => {
  assert.equal(floatMin("spaces"), 36 + 30 + 6 + 12);       // its head, a row and the list's foot, the grip
  assert.equal(fitFloatPx("spaces", { spaces: 300 }, 200, 400), 300);
  assert.equal(fitFloatPx("spaces", { spaces: 900 }, 200, 400), 400);
  assert.equal(fitFloatPx("spaces", {}, 200, 400), 200);    // as tall as its rows until dragged
  assert.equal(fitFloatPx("spaces", null, 20, 400), floatMin("spaces"));
  const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`, import.meta.url),
    "utf8");
  const sidebar = source("sidebar.js"), main = source("main.js");
  const open = sidebar.slice(sidebar.indexOf("function openFloat("), sidebar.indexOf("\n}\n",
    sidebar.indexOf("function openFloat(")));
  assert.match(open, /props: \{ part: "float", panel: "spaces", fit, most \}/);
  assert.doesNotMatch(open.slice(open.indexOf("openOverlay(")), /height/);    // as tall as its content: its grip
  assert.match(main, /this\.floatSize = new FloatSize\(panel, \{ fit: props\(\)\.fit, most: props\(\)\.most \}\);/);
  assert.match(main, /sizedFloat\(t, this\.floatSize, "Spaces", float\.overlay, spacesBody\(t\)/);
});

test("Cmd+B in herdr-fold's layout folds and opens the left dock, as its toggle; never the app's hide", () => {
  const keys = JSON.parse(readFileSync(new URL("../keys.json", import.meta.url), "utf8"));
  assert.equal(keys["layout:herdr-fold"]["cmd-b"], "herdr-fold.sidebar");
  const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
  assert.match(main, /else if \(asked === "sidebar"\) toggleSidebar\(\);/);
});

test("a float stands beside its rail on the centre card's edges, under the tab bar: the bar's end stays in reach",
  () => {
    const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
    Object.assign(find(root, PANEL), { size: { px: RAIL } });
    Object.assign(find(root, "sidebar"), { size: { px: RAIL } });
    // a view: FLOAT_GAP left of the rail, whichever icon was pressed; Spaces: as far right of the sidebar's divider
    assert.equal(FLOAT_GAP, 8);
    assert.equal(floatX("changes", root, 1280, PANEL_PX), 1280 - 8 - RAIL - 8 - PANEL_PX);
    assert.equal(floatX("files", root, 1280, PANEL_PX), floatX("changes", root, 1280, PANEL_PX));
    assert.equal(floatX("spaces", root, 1280, 300), RAIL + 1 + 8);
    assert.equal(floatX("changes", root, 300, PANEL_PX), FLOAT_GAP);          // a narrow window: inside it
    // both at the centre card's top, under the title row and the tab bar (their ✦, More and » uncovered)
    assert.equal(floatTop(root), 36 + 42 + 8);
    const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
    const at = panel.indexOf("export function openRail"), open = panel.slice(at, panel.indexOf("\n}\n", at));
    assert.ok(open.includes("at: { x: floatX(panel, root, window.viewport_size().width, PANEL_PX), "
      + "y: floatTop(root) }"));
    const sidebar = readFileSync(new URL("../mods/herdr-fold/sidebar.js", import.meta.url), "utf8");
    assert.match(sidebar, /at: \{ x: floatX\("spaces", root, room\.width, FLOAT\), y \}/);
  });

test("Spaces floating beside the folded sidebar is as tall as its rows, no scroll, inside the window", () => {
  // its head 36, a row 28 and 2 after it, the list's foot 8 less the last gap
  assert.equal(floatHeight(1), 36 + 28 + 8);
  assert.equal(floatHeight(5), 36 + 5 * 28 + 4 * 2 + 8);
  assert.equal(floatHeight(40), TALL);
  assert.equal(floatHeight(5, 150), 150);                  // the window's room under its top: then it scrolls
  assert.equal(floatHeight(5, 20), floatHeight(1));        // a row at least
  const sidebar = readFileSync(new URL("../mods/herdr-fold/sidebar.js", import.meta.url), "utf8");
  assert.match(sidebar, /\.px\(8\)\.pb\(8\)\.gap\(2\)/);
  assert.match(sidebar, /h_flex\(\)\.id\(`float-space-\$\{space\.id\}`\)\.h\(28\)/);
});

test("a rail's icon floats its panel, lit while it floats; the lit icon again, Esc or its × closes it, both sides",
  () => {
    const source = (/** @type {string} */ name) => readFileSync(new URL(`../mods/herdr-fold/${name}`,
      import.meta.url), "utf8");
    const panel = source("panel.js"), sidebar = source("sidebar.js"), main = source("main.js");
    const tabs = source("tabs.js");
    const body = (/** @type {string} */ text, /** @type {string} */ name) => text.slice(text.indexOf(name),
      text.indexOf("\n}\n", text.indexOf(name)));
    // the right rail: the icon of the view floating lit, as Terminal is while it shows; a press on it closes it
    const rail = body(panel, "export function rail(");
    assert.match(rail, /lit = panel === "terminal" \? !off && bottom : panel === floating/);
    assert.match(body(panel, "export function railPress("),
      /if \(open\?\.panel === panel\) return void shutFloat\(RAIL_FLOAT\)/);
    assert.match(body(panel, "export function openRail("), /setShared\(RAIL_FLOAT, \{ panel, overlay: openOverlay\(/);
    assert.match(panel, /export const liveRail = [^]*?floatingView\(\)/);
    // ✦ lit while Chats floats; pressed again it closes it (a chat's clock only ever shows it)
    assert.match(tabs, /listed: chatsShown\(\) \|\| floatingView\(\) === "chats"/);
    assert.match(body(panel, "export function askChats("),
      /if \(!to\.space && floatingView\(\) === "chats"\) return void shutFloat/);
    // the left rail: Spaces lit while it floats, a press on it closes it
    assert.match(body(sidebar, "function dockButton("), /lit \? shutFloat\(DOCK_FLOAT\) : openFloat\(/);
    assert.match(body(sidebar, "function openFloat("),
      /setShared\(DOCK_FLOAT, \{ panel: "spaces", overlay: openOverlay\(/);
    // Esc: a float takes the keys as it opens (Chats its filter), Esc closes it once its view has none to drop
    const float = body(sidebar, "export function floatPanel(");
    assert.match(float, /\.when\(Boolean\(focus\), \(e\) => e\.track_focus\(focus\)\)/);
    assert.match(float, /if \(e\.key !== "escape"\) return;\s+cx\.stop_propagation\(\);\s+closeOverlay\(overlay\);/);
    assert.match(main, /this\.floatFocus = cx\.focus_handle\(\);/);
    assert.match(main, /cx\.timer\.after\(0, \(\) => this\.floatFocus\.focus\(\)\)/);
    assert.ok(source("files.js").includes('if (e.key === "escape" && (this.naming || this.asking)) this.drop(cx);'));
    assert.match(main, /if \(e\.key === "escape"\) this\.cancel\(cx\);/);
    // gone however it closes (×, Esc, its icon, a layout switch): its mark forgotten; a start forgets a last run's
    assert.match(body(main, "  async close() {"), /if \(this\.float\) forgetFloat\(this\.float\.overlay\);/);
    assert.match(main, /forgetSettings\(\);\s+forgetFloats\(\);/);
    // its side opened or hidden: closed (floatStale), Spaces too
    assert.ok(main.includes("if (float && floatStale(float.panel, layout())) cx.timer.after(0, () => "
      + "closeOverlay(float.overlay));"));
  });

test("the tab bar, which always shows, follows both sides: their blocks at once, their widths once let go", () => {
  const main = readFileSync(new URL("../mods/herdr-fold/main.js", import.meta.url), "utf8");
  const at = main.indexOf("  followDock(cx) {"), follow = main.slice(at, main.indexOf("\n  }\n", at));
  assert.match(follow, /\.\.\.sidebarFollow\(root\)/);
  assert.match(follow, /restFollow\("dock", panelPx\(root\), restDock, cx\);/);
  assert.match(follow, /restFollow\("side", sidebarPx\(root\), restSide, cx\);/);
  const sidebar = readFileSync(new URL("../mods/herdr-fold/sidebar.js", import.meta.url), "utf8");
  assert.doesNotMatch(sidebar, /trackFold|followFold/);    // not from Spaces' block, which a hidden sidebar draws not
});

/** Layout ROOT's nodes by id, each once. @param {any} root @returns {Map<string, any>} */
function layoutNodes(root) {
  const nodes = new Map();
  const walk = (/** @type {any} */ node) => {
    assert.equal(nodes.has(node.id), false, `${node.id} twice`);
    nodes.set(node.id, node);
    (node.children ?? []).forEach(walk);
  };
  walk(root);
  return nodes;
}

test("the layout's right dock: one stack of the views and the Chats list under the row, the terminals, the rail",
  () => {
    const nodes = layoutNodes(JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8")));
    const ids = (/** @type {string} */ id) => nodes.get(id).children.map((/** @type {any} */ c) => c.id);
    assert.deepEqual(ids(PANEL), [DOCK, TERMINALS, RAIL_BLOCK]);
    assert.equal(nodes.get(PANEL).resizable, undefined);     // the views and the terminal drag apart, as the TUI's
    assert.deepEqual(nodes.get(DOCK).header, { content: { mod: "herdr-fold", props: { part: "dock-head" } },
      height: TABS_H });                                                           // the tabs: the stack's own
    assert.deepEqual([nodes.get(DOCK).type, nodes.get(DOCK).active], ["stack", "files"]);
    assert.deepEqual(nodes.get(DOCK).children.map((/** @type {any} */ c) => [c.id, c.content.props]),
      [...VIEWS_APP.map((id) => [id, id === "files" ? { part: "files" } : { view: id }]),
        [CHATS_BLOCK, { part: "chats" }]]);
  });

test("the dock's tabs and its view are one card, as the tab's and the terminal's, its top at the tab's card's", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  const nodes = layoutNodes(root), pane = nodes.get("main").content.pane;
  const look = (/** @type {any} */ n) => ({ border: n.border, radius: n.radius });
  assert.deepEqual(look(nodes.get(DOCK)), look(pane));
  assert.deepEqual(look(nodes.get(TERMINALS)), look(pane));
  // the levels (tools/build.py LEVELS): the window canvas, the left sidebar chrome, the dock a card (surface); a
  // terminal and the pane round it in the terminals' own background, as Herdr paints a terminal
  assert.deepEqual([root.background, nodes.get("sidebar").background, nodes.get(DOCK).background],
    ["canvas", "chrome", "surface"]);
  assert.deepEqual([pane.background, nodes.get(TERMINALS).background], ["background", "background"]);
  /** px from the window's top to node ID's edge: each column's padding, the shown nodes above it and their gaps
   * @param {string} id @returns {number} */
  const top = (id, node = root) => {
    if (node.id === id) return 0;
    const at = (node.children ?? []).findIndex((/** @type {any} */ c) => JSON.stringify(c).includes(`"${id}"`));
    if (at < 0) return NaN;
    const above = node.type === "column" ? node.children.slice(0, at).filter((/** @type {any} */ c) => !c.hidden)
      : [];
    const pad = [node.padding ?? 0].flat()[0];
    return pad + above.reduce((y, /** @type {any} */ c) => y + c.size.px + (node.gap ?? 0), 0)
      + top(id, node.children[at]);
  };
  assert.equal(top(DOCK), top("main"));
  assert.equal(top("main"), nodes.get("title").size.px + nodes.get("top").size.px + nodes.get("work-body").padding);
  // in the card's border, the tabs TABS_PAD in over and under and TABS_SIDE at the sides, as center-chat.html's
  // .ptabs (narrowed so the first tab's words stand over the views'); then a hairline, as a view's head has one
  assert.deepEqual([nodes.get(DOCK).border.width, root.terminal_padding], [pane.border.width, [PAD, PAD]]);
  assert.deepEqual([TABS_H, TABS_IN], [TABS_PAD + TAB_H + TABS_PAD + 1, nodes.get(DOCK).border.width + TABS_SIDE]);
  const panel = readFileSync(new URL("../mods/herdr-fold/panel.js", import.meta.url), "utf8");
  const at = panel.indexOf("export function dockTabs"), row = panel.slice(at, panel.indexOf("\n}\n", at));
  assert.match(row, new RegExp(String.raw`\.py\(TABS_PAD\)\.px\(TABS_SIDE\)\.gap\(TAB_GAP\)\.items_center\(\)\s*`
    + String.raw`\.overflow_hidden\(\)`
    + String.raw`\.border_b\(1\)\.border_color\(t\.border\)`));
});

test("a menu as tall as its rows, a rule between its parts thinner", () => {
  assert.equal(menuHeight([{ label: "a" }, { label: "b" }]), 2 * 30 + 8);
  assert.equal(menuHeight([{ label: "a" }, null, { label: "b" }]), 2 * 30 + 11 + 8);
  assert.equal(menuHeight([{ label: "a" }], { label: "head" }), 2 * 30 + 8);
  assert.equal(menuHeight([{ label: "a" }], undefined, true), 30 + 34 + 8);       // a filter on top, a field
});

test("a count short when large, as the TUI's: as it is to 999, then k and m, a decimal under ten, 4 characters", () => {
  const cases = [[0, "0"], [7, "7"], [999, "999"], [1000, "1k"], [1234, "1.2k"], [9999, "9.9k"], [18432, "18k"],
    [111000, "111k"], [999999, "999k"], [1000000, "1m"], [1300000, "1.3m"], [12000000, "12m"]];
  assert.deepEqual(cases.map(([n]) => shortCount(Number(n))), cases.map(([, said]) => said));
  assert.equal(shortCount(5e9), "999m");                                   // never past 4 characters
});

test("the ✦'s count is the chats waiting on you: this Mac's Claude and Codex blocked, as the TUI's", () => {
  const agent = (/** @type {string} */ space, /** @type {string} */ key, /** @type {string} */ status) =>
    ({ address: `${space}-${key}-${status}`, space, status, program: { key } });
  const agents = [agent("s1", "claude", "blocked"), agent("s1", "codex", "blocked"), agent("s1", "claude", "done"),
    agent("s2", "claude", "blocked"), agent("s1", "aider", "blocked"),
    { address: "t9", space: "s1", status: "blocked" }];
  assert.equal(waitingChats(agents, new Set(["s1"])), 2);                 // s2 is another machine's
  assert.equal(waitingChats([], new Set(["s1"])), 0);
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

test("the title row across the whole window: 36 with its hairline, dragging the window, the lights on its line", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  assert.deepEqual([root.type, root.resizable, root.titlebar], ["column", false, "none"]);   // it never drags
  const [title, below] = root.children;
  assert.deepEqual([title.id, title.size, title.window_drag, title.content],
    ["title", { px: 36 }, true, { mod: "herdr-fold", props: { part: "title" } }]);
  assert.deepEqual(below.children.map((/** @type {any} */ c) => c.id), ["sidebar", "work"]);
  assert.deepEqual(below.divider, { width: 1, color: "border" });                  // between them, not through it
  // macOS draws the lights in a frame 16 high, their circles 1 in from its left and 2 under its top (measured in the
  // demo): 18 in, as commands.html's B draws them, their middle on the row's, its hairline under it
  assert.deepEqual([root.traffic_lights[0] + 1, root.traffic_lights[1] + 8], [18, (title.size.px - 1) / 2]);
});

test("the layout's left sidebar: its head, Spaces by an id of its own, the app's footer; no Chats", () => {
  const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
  const sidebar = find(root, "sidebar");
  assert.deepEqual(sidebar.children.map((/** @type {any} */ c) => c.id), ["sidebar-head", "fold-spaces",
    "sidebar-footer"]);
  // the head on the tab row's line: as high as the tab bar beside it, under the title row
  assert.equal(sidebar.children[0].size.px, find(root, "top").size.px);
  assert.deepEqual(sidebar.children[0].content, { mod: "herdr-fold", props: { part: "head" } });
  const spaces = sidebar.children[1];
  assert.deepEqual([spaces.type, spaces.size, spaces.content], ["block", { weight: 1 },
    { mod: "herdr-fold", props: { part: "spaces" } }]);
  assert.equal(JSON.stringify(sidebar).includes('"part":"chats"'), false);   // Chats: the right dock's, in its stack
});

test("a change's letter named, as the mouse resting on it says it: git's code, the TUI's letter for it", () => {
  assert.deepEqual(["M", "A", "D", "?", "U", "R"].map(changeName),
    ["Modified", "Added", "Deleted", "Untracked", "Conflict", "Renamed"]);
  assert.equal(changeName("X"), "X");
});

test("Cmd+Shift+G's launcher is the popup mod.open makes, not the mod's own (a folded sidebar's panel)", () => {
  assert.equal(launcher({ overlay: "o1" }), "o1");
  assert.equal(launcher({ overlay: "o2", part: "flyout", panel: "spaces" }), null);
  assert.equal(launcher({ part: "chats" }), null);
  assert.equal(launcher(undefined), null);
});

const talk = (id, folder, time, state = "", pane = "") =>
  ({ agent: "claude", id, title: `Talk ${id}`, folder, time, state, pane });
const shown = (rows) => rows.map((r) => (r.kind === "group" ? `${r.name} ${r.items.length} ${r.open}` : r.item.id));
const PLACE = { "/repo/shop": "shop", "/repo/api": "api" };

test("the app's agents as core/chats.py takes herdr's: Claude and Codex on this Mac, with their pane's folder",
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

test("each space's chats in the Spaces order, the front tab's first, then the newest; one elsewhere by its folder",
  () => {
    const items = [talk("a", "/repo/shop", 300), talk("b", "/repo/shop", 100, "working", "t9"),
      talk("x", "/elsewhere", 500), talk("d", "/repo/api", 200)];
    const front = new Set(["t9"]);
    assert.deepEqual(shown(chatRows(items, ["shop", "api", "notes"], PLACE, { here: "shop", front })),
      ["shop 2 true", "b", "a", "api 1 false", "elsewhere 1 false"]);       // notes, with none, left out
  });

test("a space with no chat shown is left out: none at all while the list is still read, never a false 0", () => {
  assert.deepEqual(chatRows([], ["shop", "api"], PLACE, { here: "shop" }), []);
});

test("with no space open every chat is still listed, by its project's folder, the newest project first", () => {
  // the owner's app: no space open, ~/.claude/projects full of chats
  const items = [talk("a", "/repo/shop", 300), talk("b", "/repo/api", 500), talk("c", "/repo/shop", 100)];
  const rows = chatRows(items, [], {}, { opened: new Set(["api", "shop"]) });
  assert.deepEqual(shown(rows), ["api 1 true", "b", "shop 2 true", "a", "c"]);
});

test("typing narrows every space and opens them; an archived one only while typed for or shown", () => {
  const items = [talk("a", "/repo/shop", 300), talk("d", "/repo/api", 200)], archived = new Set(["claude:a"]);
  const rows = (more) => shown(chatRows(items, ["shop", "api"], PLACE, { here: "shop", archived, ...more }));
  assert.deepEqual(rows({}), ["api 1 false"]);                             // shop's one archived: shop left out
  assert.deepEqual(rows({ typed: "talk" }), ["shop 1 true", "a", "api 1 true", "d"]);
  assert.deepEqual(rows({ typed: "API" }), ["api 1 true", "d"]);
  assert.deepEqual(rows({ typed: "archived" }), ["shop 1 true", "a"]);
  assert.deepEqual(rows({ showArchived: true }), ["shop 1 true", "a", "api 1 false"]);
});

test("a space opened or closed by hand stays so, the one here open unless closed", () => {
  const items = [talk("a", "/repo/shop", 300), talk("d", "/repo/api", 200)];
  assert.deepEqual(shown(chatRows(items, ["shop", "api"], PLACE,
    { here: "shop", opened: new Set(["api"]), closed: new Set(["shop"]) })), ["shop 1 false", "api 1 true", "d"]);
});

test("a closed one reopens with its agent's resume, its id never an option, a space or a control code", () => {
  assert.deepEqual(resumeArgv({ agent: "claude", id: "0a1b-2c" }), ["claude", "--resume", "0a1b-2c"]);
  assert.deepEqual(resumeArgv({ agent: "codex", id: "019a.x_y" }), ["codex", "resume", "019a.x_y"]);
  for (const id of ["--help", "-x", "a b", "a\u001b[2J", ""]) {
    assert.throws(() => resumeArgv({ agent: "claude", id }), id);
  }
});

test("a right click: Open, Copy chat, Rename, Archive or Unarchive, then Delete…; elsewhere the archived shown or not",
  () => {
    const archived = new Set(["claude:c"]), first = ["Open", "Copy chat", "Rename"];
    assert.deepEqual(chatChoices(talk("r", "/x", 1, "working"), archived, false), [...first, "Delete…"]);
    assert.deepEqual(chatChoices(talk("o", "/x", 1), archived, false), [...first, "Archive", "Delete…"]);
    assert.deepEqual(chatChoices(talk("c", "/x", 1), archived, false), [...first, "Unarchive", "Delete…"]);
    assert.deepEqual(chatChoices(null, archived, false), ["Show archived"]);
    assert.deepEqual(chatChoices(null, archived, true), ["Hide archived"]);
    assert.deepEqual(chatChoices(null, new Set(), false), []);
  });

test("Delete… is off for a running chat, its tip saying why; a closed or an archived one's is on", () => {
  assert.equal(deleteOff(talk("r", "/x", 1, "working")), "A running chat is not deleted: close it first");
  assert.equal(deleteOff(talk("i", "/x", 1, "idle")), "A running chat is not deleted: close it first");
  assert.equal(deleteOff(talk("o", "/x", 1)), null);
});

test("a chat on its way to the Trash is no row, its space counting one fewer", () => {
  const items = [talk("a", "/x", 2), talk("b", "/x", 1)];
  assert.deepEqual(withoutLeaving(items, new Set(["claude:a"])).map((c) => c.id), ["b"]);
  assert.deepEqual(withoutLeaving(items, new Set()).map((c) => c.id), ["a", "b"]);
  // read again without it: no longer waited for; one still listed (a read begun before it left) stays hidden
  assert.deepEqual([...stillLeaving(new Set(["claude:a", "claude:z"]), items)], ["claude:a"]);
});

test("a reopened chat's tab: its title, printable, no leading dash, cut at 24 with an ellipsis", () => {
  assert.equal(tabLabel("- Fix\u001b the login"), "Fix the login");
  assert.equal(tabLabel("A very long chat title for its tab"), "A very long chat title …");
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

test("a machine's home is first among its machine's rows, a stand-in where no space is there", () => {
  const space = (id, machine, name, more = {}) => ({ id, machine, name, named: false, folder: `/work/${name}`,
    ...more });
  const list = [space("api", null, "lumen-api"), space("root", null, "~", { folder: "/Users/dev" }),
    space("named", null, "scratch", { named: true, folder: "/Users/dev/" }), space("ci", "lab", "lumen-ci"),
    space("tilde", null, "~", { named: true, folder: "/work/tilde" })];
  // the app's own "~" (nobody named it), or one in the machine's known home folder; a space named ~ elsewhere is not
  const homes = homesSeen({ "": "/Users/dev" }, list, []), home = (s) => atHome(s, [], homes);
  assert.deepEqual(list.filter(home).map((s) => s.id), ["root", "named"]);
  // a machine's home is learned from its own "~", so a named space there is known by it afterwards
  const lab = homesSeen({}, [space("r", "lab", "~", { folder: "/home/dev" })], []);
  assert.deepEqual(lab, { lab: "/home/dev" });
  assert.equal(atHome(space("box", "lab", "box", { named: true, folder: "/home/dev" }), [], lab), true);
  assert.equal(atHome(space("box", "lab", "box", { named: true, folder: "/home/dev" }), [], {}), false);
  // first among its machine's, the others in their order; a checkout's worktrees go with it
  const rows = [{ w: list[0] }, { w: list[1] }, { w: { id: "wt", machine: null }, tree: true }, { w: list[3] }];
  assert.deepEqual(homeFirst(rows, (r) => r.w.id === "root").map((r) => r.w.id), ["root", "wt", "api", "ci"]);
  assert.deepEqual(homeFirst(rows, () => false), rows);
  // the homes with nothing open, of the machines a terminal can start on
  assert.deepEqual(homesEmpty([null, "lab"], list, home), ["lab"]);
  assert.deepEqual(homesEmpty([null, "lab"], [list[0]], home), [null, "lab"]);
  // the flat list: by machine, this computer first, each home first, a stand-in at an empty one's head
  const flat = withHomes([list[0], list[1], list[3]], ["mini", "lab"], home);
  assert.deepEqual(flat.map((s) => [s.id, Boolean(s.empty)]),
    [["root", false], ["api", false], [homeId("lab"), true], ["ci", false], [homeId("mini"), true]]);
  assert.deepEqual(flat[4], { id: "home:mini", name: HOME_NAME, machine: "mini", active: false, status: null,
    empty: true });
  assert.equal(homeId(null), "home:");
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

test("a space without a color gets the one fewest use, as every app mod gives it; home's and a root's none", () => {
  const list = [{ id: "a", name: "x" }, { id: "b", name: "y" }, { id: "c", name: "~" }, { id: "d", name: "/" },
    { id: "e", name: "C:\\" }];
  assert.deepEqual(spaceColors(list, { a: "ansi6", gone: "ansi3" }), { a: "ansi6", b: "ansi3" });
  assert.equal(spaceColors(list.slice(0, 1), { a: "ansi6" }), null);    // nothing to write
});

test("a root's space is named by a word, as the TUI names it: root, a drive's letter; home for ~", () => {
  // the app names one as its path, as herdr does; a name given by hand shows as it is
  assert.deepEqual(["/", "C:\\", "d:\\", "~", "lab", "/srv", "C:", undefined].map(spaceLabel),
    ["root", "C:", "d:", "home", "lab", "/srv", "C:", ""]);
});

test("home's and a root's avatar is a glyph tile in home's color, whatever color is kept for it", () => {
  const colors = { a: "ansi3", c: "ansi4", d: "ansi5" };
  assert.deepEqual([{ id: "a", name: "lab" }, { id: "b", name: "x" }, { id: "c", name: "/" }, { id: "d", name: "C:\\" },
    { id: "e", name: "~" }].map((s) => spaceColor(s, colors)), ["ansi3", "ansi6", "ansi6", "ansi6", "ansi6"]);
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

test("a reopened chat is forgotten once its agent is gone, never for a moment's empty list", () => {
  const kept = { t1: "talk-1", t2: "talk-2" };
  assert.deepEqual(stillResumed(kept, new Set(["t1", "t9"])), { t1: "talk-1" });
  assert.deepEqual(stillResumed(kept, new Set()), kept);                   // the app starting, its core reconnecting
});

test("a chat's agent whose tab is gone is ended; one whose tab is there, or that has ended, stays", () => {
  const agent = (address, tab, state = "live") => ({ address, state, labels: { [CHAT_TAB]: tab } });
  assert.deepEqual(orphanChats([agent("t1", "tb1"), agent("t2", "tb2"), agent("t3", "tb3", "exited"),
    { address: "t4", state: "live", labels: {} }], ["tb1"]), ["t2"]);
});

// the chats waiting on you (Task 8): a card asking, or the agent asking in its own terminal

/** A chat tab's agent as terminals() lists it. */
const chatAgent = (address, tab, session, more = {}) => ({ address, state: "live", status: "working",
  labels: { [CHAT_TAB]: tab, [CHAT_LABEL]: session }, ...more });

test("a chat waits on you while a card asks, and once its agent has asked in its own terminal for 2 s", () => {
  assert.equal(chatWait({ id: "r1" }, null, 1000), "request");
  assert.equal(chatWait({ id: "r1" }, 0, 9000), "request");                 // a card first: it is drawn
  assert.equal(chatWait(null, 1000, 1000 + WAY_OUT - 1), null);             // a card may come yet
  assert.equal(chatWait(null, 1000, 1000 + WAY_OUT), "terminal");
  assert.equal(chatWait(null, null, 9000), null);
});

test("a chat's wait is kept by its tab, gone once answered; a closed chat's is dropped", () => {
  const wait = { space: "s1", address: "t1", since: 500 };
  let kept = keepWait({}, "tb1", wait, new Set(["t1"]));
  assert.deepEqual(kept, { tb1: wait });
  kept = keepWait(kept, "tb2", { space: "s2", address: "t2", since: 900 }, new Set(["t2"]));
  assert.deepEqual(Object.keys(kept), ["tb2"]);                             // t1 has ended: its tab is gone
  assert.deepEqual(keepWait(kept, "tb2", null, new Set(["t2"])), {});
  assert.deepEqual(keepWait(null, "tb1", null, new Set()), {});
});

test("the chats waiting mark their tabs and spaces (the longest wait) while their agents run", () => {
  const kept = { tb1: { space: "s1", address: "t1", since: 300 }, tb2: { space: "s1", address: "t2", since: 100 },
    tb3: { space: "s2", address: "t3", since: 50 } };
  const found = waiting(kept, [chatAgent("t1", "tb1", "a"), chatAgent("t2", "tb2", "b"),
    chatAgent("t3", "tb3", "c", { state: "finished" })]);
  assert.deepEqual([...found.tabs], ["tb1", "tb2"]);
  assert.deepEqual(found.spaces, { s1: 100 });
  assert.deepEqual([...found.agents], ["t1", "t2"]);
  assert.deepEqual(waiting(undefined, []).spaces, {});
});

test("a waiting chat's tab shows blocked, not its agent's spinner, as a waiting agent's tab does", () => {
  const space = { tabs: [{ id: "t4", name: "Book tests", named: true }, { id: "t5", name: "Notes", named: true }] };
  const chats = { t4: { status: "working", program: { name: "Claude", agent: true, icon: "claude.svg", tint: true } },
    t5: { status: "working", program: { name: "Claude", agent: true, icon: "claude.svg", tint: true } } };
  assert.deepEqual(tabRows(space, [], chats, new Set(["t4"])).map((r) => r.status), ["blocked", "working"]);
});

test("a space's wait counts its chats waiting too, the longest one", () => {
  const agents = [{ address: "a", space: "s1" }];
  assert.deepEqual(spaceWaits({ a: { since: 300 } }, agents, { s1: 200, s2: 700 }), { s1: 200, s2: 700 });
  assert.deepEqual(spaceWaits({ a: { since: 300 } }, agents, { s1: 900 }), { s1: 300 });
});

test("the ✦'s count adds the chats waiting on you, each agent once", () => {
  const agents = [{ address: "t1", space: "s1", status: "blocked", program: { key: "claude" } }];
  assert.equal(waitingChats(agents, new Set(["s1"]), new Set(["t7", "t8"])), 3);
  assert.equal(waitingChats(agents, new Set(["s1"]), new Set(["t1"])), 1);         // its terminal shown in a pane
});

test("a chat tab's agent reaches the Chats list by its session, blocked while its chat waits on you", () => {
  const terminals = [chatAgent("t1", "tb1", "aaaa-1"), chatAgent("t2", "tb2", "bbbb-2", { status: null }),
    chatAgent("t3", "tb3", "cccc-3", { state: "finished" }), { address: "t4", state: "live", labels: {} },
    chatAgent("t5", "tb5", "dddd-5", { program: { key: "codex" } })];
  assert.deepEqual(chatAgents(terminals, new Set(["t2"])), [
    { agent: "claude", agent_status: "working", pane_id: "t1", agent_session: { value: "aaaa-1" } },
    { agent: "claude", agent_status: "blocked", pane_id: "t2", agent_session: { value: "bbbb-2" } },
    { agent: "codex", agent_status: "working", pane_id: "t5", agent_session: { value: "dddd-5" } }]);
});

test("a menu opens under its button where it fits there, else above it, else as far in as the window lets it", () => {
  const room = { width: 1200, height: 800 };
  const button = (y) => ({ x: 600, y, width: 60, height: 24 });
  assert.deepEqual(menuPlace(button(100), 120, room, 180), { x: 480, y: 128 });            // under, right edges in line
  assert.deepEqual(menuPlace(button(740), 120, room, 180), { x: 480, y: 616 });            // the chat's bar: above
  assert.deepEqual(menuPlace(button(60), 760, room, 180), { x: 480, y: 32 });              // neither: in the window
  assert.deepEqual(menuPlace({ x: 2, y: 100, width: 24, height: 24 }, 120, room, 180).x, 8);   // the left edge kept
});

test("the status bar says the agents as the mockups' bar does: those waiting first, then those working, else how many",
  () => {
    assert.deepEqual(agentsSaid([]), { words: "No agents", role: null });
    assert.deepEqual(agentsSaid(["idle"]), { words: "1 agent", role: null });
    assert.deepEqual(agentsSaid(["idle", "done"]), { words: "2 agents", role: null });
    assert.deepEqual(agentsSaid(["working"]), { words: "1 agent working", role: "working" });
    assert.deepEqual(agentsSaid(["working", "idle"]), { words: "1 of 2 agents working", role: "working" });
    assert.deepEqual(agentsSaid(["blocked"]), { words: "1 agent waiting for you", role: "waiting" });
    assert.deepEqual(agentsSaid(["blocked", "blocked"]), { words: "2 agents waiting for you", role: "waiting" });
    assert.deepEqual(agentsSaid(["working", "blocked", "idle"]),
      { words: "1 of 3 agents waiting for you", role: "waiting" });
  });

test("an update Herdr has ready is one item: the app's a restart (its core along), the core's an update, none managed",
  () => {
    const app = (/** @type {string | null} */ ready) => ({ version: "0.1.15", ready, updates: true });
    const core = (/** @type {any} */ more) => ({ version: "0.1.20", managed: null, ready: null, updating: false,
      error: null, ...more });
    assert.equal(updateReady({ app: app(null), core: core({}) }), null);
    assert.equal(updateReady(null), null);
    assert.deepEqual(updateReady({ app: app(null), core: core({ ready: "0.1.21" }) }),
      { words: "Update ready: herdr-core 0.1.21", command: "app.update_core", busy: false,
        tip: "Update herdr-core to 0.1.21 now; your terminals keep running" });
    assert.equal(updateReady({ app: app(null), core: core({ ready: "0.1.21", managed: "homebrew" }) }), null);
    assert.deepEqual(updateReady({ app: app(null), core: core({ ready: "0.1.21", updating: true }) }),
      { words: "Updating herdr-core to 0.1.21…", command: "app.update_core", busy: true,
        tip: "Update herdr-core to 0.1.21 now; your terminals keep running" });
    assert.deepEqual(updateReady({ app: app("0.1.16"), core: core({}) }),
      { words: "Update ready: Herdr 0.1.16", command: "app.update", busy: false,
        tip: "Restart into Herdr 0.1.16; your terminals keep running" });
    assert.equal(updateReady({ app: app("0.1.16"), core: core({ ready: "0.1.21" }) }).tip,
      "Restart into Herdr 0.1.16 and herdr-core 0.1.21; your terminals keep running");
  });

test("a newer herdr-fold is the status bar's item after Herdr's and herdr-core's: a press opens Settings at About",
  () => {
    const newer = { ...FOUND, latest: "0.4.0", newer: true };
    const none = { app: { ready: null }, core: { ready: null } };
    assert.deepEqual(updateReady(none, newer), { words: "herdr-fold 0.4.0 is out", opens: "about", busy: false,
      tip: "Open herdr-fold's Settings at About" });
    assert.equal(updateReady(null, newer)?.opens, "about");
    assert.equal(updateReady(none, FOUND), null);                              // up to date: the item's place empty
    assert.equal(updateReady(none, { ...newer, version: null }), null);        // not installed by the installer
    assert.equal(updateReady({ app: { ready: "0.1.16" }, core: {} }, newer)?.command, "app.update");
    assert.equal(updateReady({ app: {}, core: { ready: "0.1.21" } }, newer)?.command, "app.update_core");
    assert.equal(updateReady({ app: {}, core: { ready: "0.1.21", managed: "homebrew" } }, newer)?.opens, "about");
  });

test("the status bar is herdr-fold's, where the app's own was, and the one place in the mod that says an update",
  () => {
    const root = JSON.parse(readFileSync(new URL("../layouts/herdr-fold.json", import.meta.url), "utf8"));
    assert.deepEqual(find(root, "status")?.content, { mod: "herdr-fold", props: { part: "status" } });
    const mod = new URL("../mods/herdr-fold/", import.meta.url);
    const reading = readdirSync(mod).filter((name) => name.endsWith(".js") && name !== "helper.js"
      && /import \{[^}]*\bupdates\b[^}]*\} from "herdr"/.test(readFileSync(new URL(name, mod), "utf8")));
    assert.deepEqual(reading, ["status.js"]);
    const status = readFileSync(new URL("status.js", mod), "utf8");          // herdr-fold's own check: there too
    assert.match(status, /updateReady\(updates\(\), shared\(UPDATES\)\)/);
    assert.match(status, /update\.opens \? openSettings\(update\.opens\) : command\(/);
  });

test("the clock's ask names its folder's group: its space's, else the folder's own name, as the list names it", () => {
  assert.equal(folderGroup("/repo/shop", PLACE), "shop");
  assert.equal(folderGroup("/elsewhere/tidepool", PLACE), "tidepool");
  assert.equal(folderGroup("", PLACE), null);
});

test("the list's opening as kept: when, and the group asked for; an older number is a when alone", () => {
  assert.deepEqual(chatsAsked({ at: 1700, space: "api" }), { at: 1700, space: "api" });
  assert.deepEqual(chatsAsked(1700), { at: 1700, space: null });
  assert.deepEqual(chatsAsked({ at: 1700, space: 4 }), { at: 1700, space: null });
  assert.deepEqual(chatsAsked(null), { at: null, space: null });
});

test("the group the clock asked for is open, and scrolled to: from the list's end back to its head, so first", () => {
  const items = [talk("a", "/repo/shop", 300), talk("d", "/repo/api", 200), talk("e", "/repo/api", 100)];
  const opened = new Set([chatsAsked({ at: 1, space: "api" }).space]);
  const rows = chatRows(items, ["shop", "api", "notes"], PLACE, { here: "shop", opened });
  assert.deepEqual(shown(rows), ["shop 1 true", "a", "api 2 true", "d", "e"]);
  // the list draws a group as its head, then its chats' block: two children each
  assert.deepEqual(groupPlace(rows, "api"), { head: 2, last: 3 });
  assert.deepEqual(groupPlace(rows, "shop"), { head: 0, last: 3 });
  assert.equal(groupPlace(rows, "harbor"), null);
});

/** The classes in SOURCE with a field named as one of their own methods: `this.name = …` or a key Object.assign gives
 * `this`. Such a field hides the method, and its call is "not a function". @param {string} source */
function hiddenMethods(source) {
  /** @type {string[]} */
  const found = [];
  for (const [, name, body] of source.matchAll(/^(?:export (?:default )?)?class (\w+)[^\n]*\{\n([\s\S]*?)\n\}$/gm)) {
    const methods = new Set([...body.matchAll(/^ {2}(?:static )?(?:async )?(?:get |set )?\*?(\w+)\(/gm)]
      .map((m) => m[1]));
    const fields = new Set([...body.matchAll(/\bthis\.(\w+)\s*(?:[-+*/%|&?]{1,2})?=(?![=>])/g)].map((m) => m[1]));
    for (const given of body.matchAll(/Object\.assign\(this, \{/g)) {
      let depth = 1, at = given.index + given[0].length, key = true;
      for (; depth > 0 && at < body.length; at++) {
        const ch = body[at];
        if (depth === 1 && key && /\w/.test(ch)) {
          const word = /^\w+/.exec(body.slice(at))?.[0] ?? "";
          fields.add(word);
          at += word.length - 1;
          key = false;
        } else if ("'\"`".includes(ch)) at = body.indexOf(ch, at + 1);
        else if ("{[(".includes(ch)) depth++;
        else if ("}])".includes(ch)) depth--;
        else if (ch === "," && depth === 1) key = true;
        else if (ch === "." && depth === 1) key = false;          // a spread: no key
      }
    }
    found.push(...[...methods].filter((method) => method !== "constructor" && fields.has(method))
      .map((method) => `${name}.${method}`));
  }
  return found;
}

test("no view keeps a field under one of its methods' names: the field would hide the method", () => {
  // AgentView once had signing() beside this.signing: every tick of its watch was "not a function" in the app's log
  const hides = "export class Sample {\n  constructor() {\n    this.busy = false;\n    this.signing = null;\n  }\n\n"
    + "  signing() {\n    return {};\n  }\n\n  read(cx) {\n    Object.assign(this, { busy: true, waits: { read: 1 },\n"
    + "      watch: 2 });\n    if (this.busy === true) this.watch = () => this.read(cx);\n  }\n\n  watch() {}\n}\n";
  assert.deepEqual(hiddenMethods(hides), ["Sample.signing", "Sample.watch"]);
  const mod = new URL("../mods/herdr-fold/", import.meta.url);
  const sources = readdirSync(mod).filter((name) => name.endsWith(".js"));
  assert.ok(sources.includes("agent.js") && sources.includes("chat.js"));
  for (const name of sources) {
    assert.deepEqual(hiddenMethods(readFileSync(new URL(name, mod), "utf8")), [], name);
  }
});

test("a pull request's lists say so in their own words: loading, none open, none matching", () => {
  const parts = (/** @type {any} */ s) => issuesParts({ asked: false, listing: null, shown: 0, filtered: false,
    state: "open", noun: "pull requests", ...s });
  assert.deepEqual(parts({ asked: true }).say, ["Loading pull requests…", "dim"]);
  assert.deepEqual(parts({ listing: { error: null } }).say, ["No open pull requests", "dim"]);
  assert.deepEqual(parts({ listing: { error: null }, filtered: true }).say, ["No pull requests match", "dim"]);
});

test("a review comment goes on its line: a removed one's in the old file, LEFT; none on a hunk's head", () => {
  assert.deepEqual(commentAt({ kind: "+", old: null, new: 31 }), { line: 31, side: "RIGHT" });
  assert.deepEqual(commentAt({ kind: " ", old: 29, new: 30 }), { line: 30, side: "RIGHT" });
  assert.deepEqual(commentAt({ kind: "-", old: 30, new: null }), { line: 30, side: "LEFT" });
  assert.equal(commentAt({ kind: "@", old: null, new: null }), null);
});

test("a review goes as GitHub takes it: Approve never on one's own, Comment and Request changes with a summary", () => {
  assert.equal(reviewReady("approve", "", false), true);
  assert.equal(reviewReady("approve", "", true), false);
  assert.equal(reviewReady("comment", "  ", false), false);
  assert.equal(reviewReady("request", "Page it", true), true);
});

test("a login's avatar color is one of the spaces' and the same every time", () => {
  assert.ok(Object.values(MARK).includes(loginColor("ada")));
  assert.equal(loginColor("tomas"), loginColor("tomas"));
});
