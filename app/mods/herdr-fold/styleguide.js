// @ts-check
// The mod's styleguide: its foundations, each component in each of its states and the panels they make, drawn by the
// views' own code from made-up states whose clicks go nowhere. herdr-app do herdr-fold.styleguide opens it.
import { div } from "gpui-kit";
import { EditorState, v_flex, h_flex, InputState, ScrollHandle, TextareaState } from "gpui-base";
import { home } from "herdr";
import { BY_EXTENSION, BY_NAME, FILE, ICONS } from "./icons.js";
import { agentsSaid, commitRows, chatRows, diffRows, fieldWidth, findAll, FLOAT_GRIP, floatHeight, foldedSections,
  listHeight, menuHeight, paletteEntries, paletteKey, PALETTE_NAMED, panelChoices, pushOffer, RAIL,
  searchRows, SETTINGS, shortCount, TABS_H, updateReady, VIEWS_APP } from "./logic.js";
import { AgentView } from "./agent.js";
import { AgentsView } from "./agentstab.js";
import { Answer } from "./card.js";
import { Chat } from "./chat.js";
import { ChatsView } from "./chats.js";
import { IssuesView } from "./issues.js";
import { BranchPull, PullsView } from "./pulls.js";
import { Review } from "./review.js";
import { contrast } from "./agents.js";
import { button, chip, CODE_FONT, fileMark, icon, listName, noteToast, PAD, scopeTag, small, SPACE } from "./parts.js";
import { dockTabs, floatGrip, FloatSize, rail } from "./panel.js";
import { Menus, menuPopup } from "./menus.js";
import { Preview } from "./preview.js";
import { Editing } from "./editor.js";
import { UsageView } from "./usageview.js";
import { money, whole } from "./report.js";
import { SettingsView } from "./settings.js";
import { dock, floatHead, floatPanel, sidebarFoot, sidebarHead, spacesBody, spacesButtons } from "./sidebar.js";
import { FilesView } from "./files.js";
import { SpacesView } from "./spaces.js";
import { barEnd, TabsView } from "./tabs.js";
import { statusBar } from "./status.js";
import { standIn } from "./terminal.js";
import { Palette, PALETTE_WIDE, titleRow, WINDOW_BUTTONS } from "./title.js";
import { timeline } from "./timeline.js";

const PANEL = 368;                  // a specimen as wide as the right panel
const COST_END = 52;                // Connectors' + from its head's end: the costs' column, a gap, the head's 6 in
const TAB = 540;                    // a specimen of the preview tab, two side by side
const SIDEBAR = 268;                // a specimen as wide as the left sidebar
const CHAT = 600;                   // a specimen of the chat's column: its prompt, a card, its timeline
const MENU = 180;                   // a menu's width
/** A rail's specimen as the layout grounds it (CHILD): RAIL wide, chrome, rounded 10. @param {any} child */
const onRail = (t, child) => div().w(RAIL).h(380).bg(t.chrome).rounded(10).child(child);
const SHOWN = 4;                    // Settings' specimens in a part: two rows of two
const AGENT_LIST = 240;             // a new chat's agent list (chat.js's)
const CONTEXT = 430, COMMANDS = 520;  // the Context panel, the / menu (chat.js's)
const PLUS = 380;                   // the + menu (chat.js's)
const APART = 40;                   // px between two groups of a part, and over and under it
const INDEX = 180;                  // px: the page's index of its parts
// the parts too tall for one picture, each shown in two halves: a part of the page each, named by the part's id and
// what the half shows (its picture's name); a half [its name, the places of its specimens in the part, its groups'
// one after another], the second the rest
const HALVES = {
  "agent-properties": [["connector", [0, 1, 6]], ["rule-skill-agent"]],
  "agent-connectors": [["states", [0, 1, 2, 3, 4, 5, 6, 14, 15]], ["adding"]],
  "agent-editing": [["rules", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]], ["settings"]],
  "agents-graph": [["wiring", [0, 1, 2, 6, 7, 8, 9]], ["conversation"]],
  "agents-usage": [["report", [0, 1, 2, 7, 8, 9, 10, 11]], ["budget"]],
  chats: [["list", [0, 1, 2, 3, 4]], ["states"]],
  "chat-plus": [["menu", [0, 1, 2, 3, 4, 5, 6]], ["context"]],
  "chat-panel": [["model-and-modes", [0, 1, 2, 3, 4, 5, 6]], ["commands"]],
  "chat-context": [["rules", [0, 3, 4, 5, 6]], ["costs"]],
  "chat-timeline": [["chat", [0]], ["connectors"]],
};
const PAGE = "mods/herdr-fold/styleguide-page.svg";      // a PDF's page, as the app's home names it
// what the views' clicks would do: nothing, here
const INERT = ["act", "change", "choose", "commit", "fold", "later", "pick", "refresh", "reveal", "search", "show",
  "submit", "sync", "unask", "unlink", "watch", "write"];
const INERT_ISSUES = ["act", "change", "filter", "load", "open", "terminal", "toAgent", "unask"];
const INERT_PULLS = ["cancel", "create", "load", "look", "open", "start", "toAgent", "write"];
const INERT_CHATS = ["ask", "close", "copy", "delete", "load", "look", "open", "pick", "rename", "unask", "watch"];
const INERT_TABS = { pick: () => {} };       // the dock tabs' clicks
const INERT_END = { chats: () => {}, more: () => {}, press: () => {}, away: () => {}, fold: () => {} };  // bar end's
/** The tab bar's end as it first shows: no chat waiting, the dock open, More's menu shut. */
const END = { waiting: 0, listed: false, open: true, menu: false };
/** A layout's right dock with Search hidden from More's menu, for its views. */
const DOCKED = { id: "root", children: VIEWS_APP
  .map((id) => ({ id, hidden: id === "search" })) };

const STAGED = [{ path: "src/lumen/routes/books.py", code: "M" }];
const CHANGES = [{ path: "docs/api.md", code: "M" }, { path: "src/lumen/pagination.py", code: "?" },
  { path: "src/lumen/store.py", code: "U" }, { path: "tests/test_shelves.py", code: "D" }];
const STATUS = { branch: "main", upstream: "origin/main", ahead: 2, behind: 1, staged: STAGED, changes: CHANGES };
const CHANGED = STAGED.length + CHANGES.length;        // the count on the Changes tab
const COMMITS = [
  { hash: "4f1c2ab", subject: "refactor(store): keep books in the order added", author: "Ada", refs: ["main"],
    head: true },
  { hash: "9e8d7c6", subject: "test(shelves): cover an empty shelf", author: "Ada", refs: ["origin/main"],
    head: false },
  { hash: "1a2b3c4", subject: "fix(errors): answer with problem details", author: "Lin", refs: [], head: false }];
const DIFF = diffRows(["@@ -1,4 +1,5 @@", ' """GET /books: the books, by title."""', "-PAGE = 10", "+PAGE = 20",
  "+LAST = None", " from .. import store", "@@ -30,2 +31,2 @@", "-    return books[start:]",
  "+    return books[start:end]"]);
const HTML = ["<!doctype html>", "<title>Lumen API: pagination</title>", "<link rel=\"stylesheet\" href=\"docs.css\">",
  "<h1>Pagination</h1>", "<p>Every list route answers one page at a time,", "  twenty items to a page.</p>",
  "<h2>Query parameters</h2>", "<dl>", "  <dt><code>page</code></dt>", "  <dd>The page to serve.</dd>", "</dl>", ""]
  .join("\n");
// config/limits.json in the editor, typed into (20 made 25), and the disk's copy an agent wrote meanwhile
const LIMITS = "{\n  \"page\": {\n    \"size\": 25,\n    \"max_page\": 100,\n    \"last_page\": \"clamp\"\n  },\n"
  + "  \"rate\": {\n    \"per_minute\": 60,\n    \"burst\": 10\n  },\n  \"strict\": true\n}\n";
const LOG = ["2026-11-24T09:12:03Z GET /books?page=2 200 12ms", "2026-11-24T09:12:04Z GET /books?page=3 200 9ms",
  "2026-11-24T09:12:09Z GET /shelves 200 4ms", "2026-11-24T09:12:11Z GET /books?page=9 200 8ms", ""].join("\n");
const SETTINGS_JSON = "{\n  \"permissions\": {\n    \"allow\": [\"Bash(pytest:*)\", \"Read(src/**)\"],\n"
  + "    \"deny\": [\"Read(.env)\"]\n  },\n  \"hooks\": {\n    \"PostToolUse\": []\n  }\n}\n";
// the tab bar over an editor: its tab typed into, the dot in its ×'s place
const EDITED = [{ id: "e1", name: "Fix the page past the last one", active: false, status: "working",
  icon: ICONS.bot, tint: true, unsaved: false }, { id: "e2", name: "config/limits.json", active: true, status: null,
  icon: null, tint: false, unsaved: true }, { id: "e3", name: "config/logging.toml", active: false, status: null,
  icon: null, tint: false, unsaved: true }];
const COMMIT = commitRows(["4f1c2ab  Ada  2 hours ago", "", "refactor(store): keep books in the order added", "",
  "diff --git a/src/lumen/store.py b/src/lumen/store.py", "index 1..2 100644", "--- a/src/lumen/store.py",
  "+++ b/src/lumen/store.py", "@@ -4,2 +4,2 @@", "-books = set()", "+books = []", " def add(book):"].join("\n"));
const LISTED = [
  [42, "Pagination returns an empty page past the last one", ["priority: high", "bug"], ["mira-quillon"], 1, "2h"],
  [35, "Rate limit the public routes", ["priority: high", "enhancement", "security"], [], 1, "1w"],
  [41, "Add a /search route for titles and authors", ["priority: medium", "enhancement"], ["mira-quillon"], 2, "1d"],
  [39, "Shelf names are case-sensitive", ["priority: low", "bug"], [], 3, "3d"],
  [37, "Document the error format", ["docs"], ["mira-quillon"], null, "5d"]].map(([number, title, labels, assignees,
  level, ago]) => ({ number, title, labels, assignees, state: "OPEN", url: `https://example.com/issues/${number}`,
  level, ranked_by: level === null ? null : labels[0], said: String(title).toLowerCase(), ago }));
const LISTING = { issues: LISTED, error: null };
// the repository's pull requests, as core/github.py's pull_listed gives them: one waiting on your review, your draft
// with its checks running, one with changes asked for, one approved
const PULLED = [
  [57, "Group books by shelf", "feat/shelves", "ada", "passed", "3 checks passed", "yours", "2h"],
  [58, "Keep a page past the last one in range", "fix/page-past-end", "you", "running", "checks 2 of 3", "draft", "5m"],
  [55, "Problem details for errors", "fix/errors", "tomas", "failed", "1 check failed", "changes", "1d"],
  [53, "Describe the routes", "docs/routes", "you", "passed", "3 checks passed", "approved", "2d"]]
  .map(([number, title, branch, author, mark, checks, review, ago]) => ({ number, title, branch, author, mark,
    checks_said: checks, review, ago, state: "OPEN", url: `https://example.com/pull/${number}`,
    said: String(title).toLowerCase() }));
const BRANCH = { ...STATUS, branch: "fix/page-past-end", upstream: "origin/fix/page-past-end", ahead: 0, behind: 0,
  staged: [], changes: [] };
const PR_BODY = "Past the last page, /books answered an empty list; now it answers the last page, and a page below "
  + "one answers the first.\n\nTests cover both ends.\n\nFixes #42";
// a review on its line, and its reply folded under it
const THREAD = { id: "t1", resolved: false, path: "src/lumen/routes/shelves.py", line: 30, side: "RIGHT", comments: [
  { id: 901, author: "tomas", body: "This loads every shelf at once; page it like `/books`?", ago: "1h" },
  { id: 902, author: "ada", body: "Will do.", ago: "40m" }] };
const REVIEWED = { number: 57, title: "Group books by shelf", branch: "feat/shelves", base: "main", author: "ada",
  mark: "passed", checks_said: "3 checks passed", review: "yours", mine: false, head: "3f2c1a9", files: [
    { path: "src/lumen/routes/shelves.py", added: 62, removed: 9, cut: 0, loose: [], rows: [
      { kind: "@", old: null, new: null, text: "@@ -29,3 +29,4 @@ def list_shelves(request):" },
      { kind: " ", old: 29, new: 29, text: "def list_shelves(request):" },
      { kind: "-", old: 30, new: null, text: "    shelves = store.all_shelves()" },
      { kind: "+", old: null, new: 30, text: "    shelves = store.shelves(order=\"name\")", threads: [THREAD] },
      { kind: "+", old: null, new: 31, text: "    return {\"shelves\": shelves[:50]}" }] }] };
// your own: a reviewer's changes asked for, sent to the agent
const ASKED = { ...THREAD, id: "t2", path: "src/lumen/routes/books.py", line: 31, comments: [{ id: 911,
  author: "ada", body: "`end` can pass `len(books)`; the slice is fine, but say so, or clamp it.", ago: "20m" }] };
const OWN = { ...REVIEWED, number: 58, title: "Keep a page past the last one in range", branch: "fix/page-past-end",
  author: "you", mark: "running", checks_said: "checks 2 of 3", review: "changes", mine: true, files: [
    { path: "src/lumen/routes/books.py", added: 3, removed: 1, cut: 0, loose: [], rows: [
      { kind: "@", old: null, new: null, text: "@@ -30,2 +30,4 @@ def list_books(request):" },
      { kind: " ", old: 30, new: 30, text: "    start = (page - 1) * PAGE" },
      { kind: "+", old: null, new: 31, text: "    end = start + PAGE", threads: [ASKED] }] }] };
const TALKS = [
  { agent: "claude", id: "s1", title: "Fix the page past the last one", folder: "/work/lumen-api", time: 6,
    state: "working", pane: "t1", ago: "now" },
  { agent: "codex", id: "s2", title: "Rate limit the public routes", folder: "/work/lumen-api", time: 5,
    state: "blocked", pane: "t2", ago: "12m" },
  { agent: "claude", id: "s3", title: "Document the error format", folder: "/work/lumen-api", time: 4, state: "",
    pane: "", ago: "2h" },
  { agent: "claude", id: "s4", title: "Login redirect fix", folder: "/work/lumen-api", time: 3, state: "", pane: "",
    ago: "1d" },
  { agent: "claude", id: "s9", title: "Shelves as tags, a spike", folder: "/work/lumen-api", time: 1, state: "",
    pane: "", ago: "3w" },
  { agent: "codex", id: "s5", title: "Harbor map tiles", folder: "/work/harbor-web", time: 2, state: "idle",
    pane: "t5", ago: "5m" }];
const PLACES = { "/work/lumen-api": "lumen-api", "/work/harbor-web": "harbor-web" };
const SPACES = [{ id: "s1", name: "lumen-api", active: true, status: "blocked" },
  { id: "s2", name: "harbor-web", active: false, status: "idle" },
  { id: "s3", name: "notes", active: false, status: null }];
const COLORS = { s1: "ansi6", s2: "ansi3", s3: "ansi4" };
const WAITING = { s1: Date.now() - 12 * 60000 };
// the Spaces list's groups: this computer, a machine with a space, one folded while a space there waits, one asleep,
// one rebuilt
const GROUP = { connected: true, state: "connected", rebuilt: false, error: null, busy: false, folded: false,
  wait: null, loading: false };
const ROW = { active: false, color: "ansi6", tree: false, label: "main", ahead: 0, behind: 0, wait: null };
const LOCAL = { ...GROUP, machine: null, rows: [{ ...ROW, id: "s1", name: "lumen-api", active: true, ahead: 2 },
  { ...ROW, id: "s4", name: "fix-login", tree: true, label: "", wait: "waiting 12m" },
  { ...ROW, id: "s2", name: "harbor-web", color: "ansi3", label: "spike", behind: 1, wait: "waiting 3m" },
  { ...ROW, id: "s3", name: "notes", color: "ansi4" }] };
const MACHINES = [LOCAL,
  { ...GROUP, machine: "lab", rows: [{ ...ROW, id: "s5", name: "lumen-ci", color: "ansi5", label: "lumen-api · ci" }] },
  { ...GROUP, machine: "mini", folded: true, wait: "waiting 1h", rows: [{ ...ROW, id: "s6", name: "render" }] },
  { ...GROUP, machine: "nas", connected: false, state: "asleep", rows: [] },
  { ...GROUP, machine: "old", connected: false, state: "unreachable", rebuilt: true, rows: [] }];
// a machine's home, first among its spaces: one open there, and its stand-in with nothing open; a root's space, named
// by a word, its avatar in home's color as the app's model gives it
const HOME_ROW = { ...ROW, id: "s0", name: "~", label: "", home: true };
const HOME_EMPTY = { ...HOME_ROW, id: "home:", empty: true, machine: null };
const ROOT_ROW = { ...ROW, label: "", color: "ansi6" };
const AT_HOME = [{ ...LOCAL, rows: [HOME_EMPTY, ...LOCAL.rows.slice(0, 1)] },
  { ...GROUP, machine: "lab", rows: [{ ...HOME_ROW, id: "s7" }, { ...ROOT_ROW, id: "s8", name: "/" },
    MACHINES[1].rows[0]] },
  { ...GROUP, machine: "mini", rows: [{ ...HOME_EMPTY, id: "home:mini", machine: "mini" }] },
  { ...GROUP, machine: "win", rows: [{ ...ROOT_ROW, id: "s9", name: "C:\\" }] }];
/** The Spaces list as its view draws GROUPS, MORE its drag. @param {any[]} groups */
const spacesList = (t, groups, more = {}) => Object.assign(Object.create(SpacesView.prototype),
  { pressed: null, over: null, machines: [], mending: new Set(), ...more }).draw(t, groups);
// the tab bar's tabs: the first named as its space, an agent working there (its icon tinted), one waiting on you, a
// shell, one done and zoomed
const BAR = [{ id: "t1", name: "lumen-api", active: true, status: "working", icon: ICONS.bot, tint: true },
  { id: "t2", name: "Codex", active: false, status: "blocked", icon: ICONS.bot, tint: true },
  { id: "t3", name: "Terminal", active: false, status: null, icon: null, tint: false },
  { id: "t4", name: "notes Z", active: false, status: "done", icon: null, tint: false }];
/** The tab bar as its view draws BAR, the pointer on HOVERED's tab, its end as END says.
 * @param {string | null} hovered */
const tabBar = (t, hovered, end = END, rows = BAR) => Object.assign(Object.create(TabsView.prototype),
  { pressed: null, hovered }).draw(t, rows, "s1", { start: 12, end: 12 }, { tip: "New chat", act: () => {} }, end,
  INERT_END);

/** The editor's states, each [name, its Editing, height, width]: typed into, its find bar, the disk changed (a draft
 * taken back too), an agent's settings file, read only, not text, a narrow one's find bar. */
function editorStates() {
  const finding = (/** @type {number} */ width) => {
    const matches = findAll(LIMITS, "page"), editing = editingOf("config/limits.json", LIMITS, { dirty: true, width,
      query: InputState.new({ placeholder: "Find", value: "page" }), finder: { matches, at: 1, from: 0 } });
    editing.state.set_selected_range({ start: matches[1][0], end: matches[1][1] });
    return editing;
  };
  return [["Typed into: its tab's dot (the tab bar's); ⌘ S saves it in place, no window",
    editingOf("config/limits.json", LIMITS, { dirty: true }), 300, TAB],
  ["⌘ F: the find bar over its top right, the match selected; ↩ the next, ⇧ ↩ the previous, esc closes it",
    finding(TAB), 300, TAB],
  ["Changed on disk while unsaved, or a draft taken back the disk has changed since: Reload or Keep mine; ⌘ S waits",
    editingOf("config/limits.json", LIMITS, { dirty: true, newer: "{}\n" }), 300, TAB],
  ["An agent's settings file: a quiet line, the checked way a press away",
    editingOf(".claude/settings.json", SETTINGS_JSON, { settings: true }), 300, TAB],
  ["Over 1 MiB: its start, read only, a word why", editingOf("logs/requests.log", LOG, { why: "large" }), 180, TAB],
  ["Not a text file: a word why, no editor", editingOf("assets/lumen.woff2", "", { why: "binary", state: null }), 60,
    TAB],
  ["A narrow editor: the find bar across it", finding(360), 240, 360]];
}

/** PATH's TEXT in the editor as Editing draws it, FIELDS its state (unsaved, the find bar, the disk changed, read
 * only); its buttons do nothing here. Its states are made at the page's start (a host call). */
function editingOf(path, text, fields = {}) {
  const state = EditorState.new({ language: path.endsWith(".html") ? "html" : "json", value: text,
    readonly: Boolean(fields.why), font_family: CODE_FONT, tab_size: 2 });
  return Object.assign(Object.create(Editing.prototype), { what: { root: "/work/lumen-api", path, on: null, n: 0 },
    state, disk: text, newer: undefined, dirty: false, why: null, settings: false, real: `/work/lumen-api/${path}`,
    note: null, loading: false, finder: null, query: null, width: TAB, reload: () => {}, keep: () => {},
    step: () => {}, closeFind: () => {}, showAgent: () => {} }, fields);
}
// the app's default keys (keys.json's global and terminal sections, the ones its palette shows) and herdr-fold's
// layout's, the TUI's navigation keys among them
const APP_KEYS = [...Object.entries({ "cmd-t": "tab.new", "cmd-p": "mod.open:picker", f2: "tab.rename",
  "cmd-w": "tab.close", "cmd-shift-]": "tab.next", "cmd-shift-[": "tab.prev", "cmd-d": "pane.split:right",
  "cmd-shift-d": "pane.split:down", "cmd-shift-w": "pane.close", "cmd-shift-enter": "pane.zoom",
  "cmd-alt-left": "pane.go:left", "cmd-alt-right": "pane.go:right", "cmd-alt-up": "pane.go:up",
  "cmd-alt-down": "pane.go:down", "cmd-n": "space.new", "shift-f2": "space.rename", "cmd-alt-]": "space.next",
  "cmd-alt-[": "space.prev", "cmd-shift-l": "layout.switch", "cmd-]": "agent.next", "cmd-[": "agent.prev",
  "cmd-,": "app.settings", "cmd-/": "app.help", "cmd-=": "app.zoom_in", "cmd--": "app.zoom_out",
  "cmd-0": "app.zoom_reset", "cmd-q": "app.quit", "cmd-shift-p": "app.palette" })
  .map(([keys, action]) => ({ section: "global", keys, action })),
...Object.entries({ "cmd-f": "terminal.search", "cmd-c": "terminal.copy", "cmd-v": "terminal.paste",
  "ctrl-v": "terminal.paste_image" }).map(([keys, action]) => ({ section: "terminal", keys, action })),
...Object.entries({ "cmd-n": "herdr-fold.new-agent", "cmd-,": "herdr-fold.settings",
  "cmd-shift-p": "herdr-fold.palette", "cmd-shift-f": "herdr-fold.search", "cmd-shift-g": "herdr-fold.changes",
  "cmd-shift-i": "herdr-fold.issues",
  "cmd-shift-r": "herdr-fold.chats", "cmd-shift-u": "herdr-fold.unread", "cmd-shift-c": "herdr-fold.commit-push",
  "ctrl-b shift-n": "herdr-fold.new-space", "ctrl-b shift-m": "herdr-fold.add-machine",
  "cmd-shift-e": "herdr-fold.column", "cmd-shift-o": "herdr-fold.restore", "cmd-shift-l": "herdr-fold.open-file",
  "cmd-k cmd-t": "herdr-fold.theme",
  ...Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => [`cmd-${n}`, `space.select:${n}`])),
  "cmd-down": "space.next", "cmd-up": "space.prev", "cmd-t": "tab.next", "cmd-r": "tab.prev", "cmd-d": "agent.next",
  "cmd-e": "agent.prev",
  ...Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => [`ctrl-b ${n}`, `tab.select:${n}`])),
  "ctrl-b w": "mod.open:picker" })
  .map(([keys, action]) => ({ section: "layout:herdr-fold", keys, action }))];
/** The palette's key as herdr-fold's keys bind it, on macOS (MAC) or elsewhere. @param {boolean} mac */
const PALETTE_KEY = (mac) => paletteKey(APP_KEYS, mac, "herdr-fold");
// the palette's entries: the app's commands its palette names, its layouts, on macOS, then herdr-fold's own
const PALETTE_ENTRIES = paletteEntries([...new Set(PALETTE_NAMED.map(([name]) => name))].map((name) => ({ name,
  args: [], about: "" })), ["main", "herdr-fold", "terminals", "win98"], true, { github: true, plus: "New chat" });
// the palette's specimens, each [name, what is typed, the stage's height]: open onto the field, typed, nothing found
const PALETTES = [["Open onto the field: the app's commands in its groups, each its key at its end, the first lit", "",
  476], ["Typed: what it finds, the best first and lit, each its group as a tag, herdr-fold's own among the app's",
  "new", 302],
["Nothing found", "deploy", 120]];
const PALETTE_SIDE = 20;           // px: the stage round the palette's specimen, the title row under it
// the title row, each [name, what it draws, its width]: on macOS (the lights the system's, at the row's start), narrow,
// and elsewhere with the window's buttons; the field as the row's width leaves it (fieldWidth)
const LIGHTS = 17 + 64;             // the traffic lights' room at 1x (logic.js's titleSide, the layout's x)
const TITLES = [["On macOS: the traffic lights at its start, the field on the window's centre, the space's name "
  + "faint in it", { mac: true, name: "lumen-api", key: PALETTE_KEY(true), field: fieldWidth(2 * PANEL, LIGHTS),
  buttons: null }, 2 * PANEL],
["A narrow window: the field's mark alone, its tip the key", { mac: true, name: "lumen-api", key: PALETTE_KEY(true),
  field: fieldWidth(240, LIGHTS), buttons: null }, 240],
["Off macOS: the palette's search mark, the window's buttons at the row's end", { mac: false, name: "lumen-api",
  key: PALETTE_KEY(false), field: fieldWidth(2 * PANEL, WINDOW_BUTTONS), buttons: { maximized: false } }, 2 * PANEL]];
/** The status bar on MACHINE (null: this computer) and BRANCH, its agents' STATUSES, U Herdr's updates as updates()
 * has them, FOUND herdr-fold's own check. @param {string | null} machine @param {string} branch
 * @param {(string | null)[]} statuses @param {any} [found] */
const bar = (machine, branch, statuses, u = {}, found = null) => ({ machine, branch, agents: agentsSaid(statuses),
  update: updateReady(u, found) });
const BARS = [["This computer, its branch, two agents", bar(null, "main", ["idle", "idle"])],
  ["One of two agents working", bar(null, "main", ["working", "idle"])],
  ["On another machine, one waiting for you", bar("lab", "spike", ["blocked", "working", "idle"])],
  ["herdr-core's update ready: a press updates it, the terminals running", bar(null, "main", ["idle", "idle"],
    { core: { ready: "0.1.21" } })],
  ["Herdr's update ready: a press restarts into it", bar(null, "main", ["idle", "idle"], { app: { ready: "0.1.16" } })],
  ["herdr-core updating: a spinner, no press", bar(null, "main", ["idle", "idle"],
    { core: { ready: "0.1.21", updating: true } })],
  ["A newer herdr-fold out: a press opens Settings at About", bar(null, "main", ["idle", "idle"], {},
    { version: "0.4.0", latest: "0.5.0", newer: true })]];
const ISSUE = { ago: ["1d", "4h"], issue: { number: 42, title: LISTED[0].title, state: "OPEN", author: "noa-berg",
  labels: ["priority: high", "bug"], body: "Steps:\n\n1. Ask `GET /books?page=99`\n2. The answer is an empty page" +
    "\n\nExpected: the last page, as `pages` says.",
  comments: [{ author: "tomasz-kowal", body: "Same with `page=0`." }] } };
const HITS = [
  { path: "src/lumen/routes/books.py", line: 12, text: "    page = min(max(1, page), last)",
    spans: [[4, 8], [22, 26]] },
  { path: "src/lumen/routes/books.py", line: 18, text: "    start = (page - 1) * PAGE", spans: [[13, 17]] },
  { path: "docs/api.md", line: 7, text: "`?page=N` asks for a page", spans: [[2, 6]] }];
const PEEK = [{ number: 11, text: "    last = pages(len(books), PAGE)", spans: null },
  { number: 12, text: "    page = min(max(1, page), last)", spans: [[4, 8], [22, 26]] },
  { number: 13, text: "    start = (page - 1) * PAGE", spans: null }];
const MESSAGE = "fix(books): clamp the page number to the valid range";
const SEARCHED = { cwd: "/work/lumen-api", on: null };

/** A made-up state of the views, drawn by PROTO's code (the mod's view), FIELDS over a repository with changes.
 * @param {any} proto @param {Record<string, any>} fields */
function made(proto, fields = {}) {
  const state = Object.assign(Object.create(proto), {
    view: "changes", root: "/work/lumen-api", on: null, key: "styleguide", status: STATUS,
    github: "lumenworks/lumen-api", linked: null, commits: COMMITS, message: "", busy: null, asked: null, confirm: null,
    open: null, hovered: null, offer: null, writing: null,
    mode: "commit", folded: foldedSections([]), note: null, loading: false, searching: false,
    switches: { case: false, word: false, regex: false }, found: null, searched: null, results: [], peek: null,
    peekRows: [], input: InputState.new({ placeholder: "Commit message" }),
    find: InputState.new({ placeholder: "Search" }),
  }, fields);
  for (const name of INERT) state[name] = () => {};
  if (state.message) state.input.set_value(state.message);
  state.issues = issuesOf(state, fields.issues ?? {});
  state.pulls = inert(Object.assign(new PullsView(state), { listing: { pulls: PULLED, error: null } },
    fields.pulls ?? {}));
  state.pull = inert(Object.assign(new BranchPull(state, async () => ({})), { answer: { pull: null, base: "main",
    error: null } }, fields.pull ?? {}));
  state.board = fields.board ?? "issues";
  return state;
}

/** VIEW with what its clicks would do left out (INERT_PULLS). @template T @param {T} view @returns {T} */
function inert(view) {
  for (const name of INERT_PULLS) if (name in /** @type {any} */ (view)) /** @type {any} */ (view)[name] = () => {};
  return view;
}

/** The form of a new pull request in Changes, its title and body written, FIELDS over it (writing, Ready, a note). */
function pullFormOf(fields = {}) {
  const pull = inert(Object.assign(new BranchPull({ status: BRANCH }, async () => ({})), { answer: { pull: null,
    base: "main", error: null } }));
  pull.title.set_value("Keep a page past the last one in range");
  pull.body.set_value(PR_BODY);
  pull.form = { base: "main", bases: ["main", "release"], draft: true, commits: 3, writing: null, busy: false,
    note: { text: "Claude wrote the title and the body from the branch's 3 commits; ✦ writes them again.",
      error: false }, ...fields };
  return pull;
}

/** A pull request's review as the preview tab shows it: PULL, with its SUMMARY typed and FIELDS (comments added, the
 * event, where a comment went). @param {any} pull @param {Record<string, any>} [fields] */
function reviewOf(pull, { summary = "", ...fields } = {}) {
  const review = Object.assign(new Review({ n: 0, kind: "pull" }, null), { pull, loading: false }, fields);
  review.summary.set_value(summary);
  return Object.assign(review, { act: () => {}, toAgent: () => {} });
}

const INERT_FILES = ["ask", "collapse", "copy", "drop", "look", "make", "name", "pick", "toggle", "toggleHidden",
  "trash", "workspace"];
/** An entry as core/tree.py lists it. @param {string} name @param {boolean} [dir] @param {string | null} [mark]
 * @param {boolean} [ignored] */
const entry = (name, dir = false, mark = null, ignored = false) => ({ name, dir, mark, ignored });
const FOLDERS = {
  "": { more: 0, entries: [entry("build", true, null, true), entry("docs", true, "M"), entry("src", true, "?"),
    entry("tests", true, "M"), entry("pyproject.toml"), entry("README.md")] },
  src: { more: 0, entries: [entry("lumen", true, "?")] },
  "src/lumen": { more: 0, entries: [entry("routes", true, "M"), entry("app.py", false, "M"),
    entry("pagination.py", false, "?"), entry("store.py")] },
  "src/lumen/routes": { more: 1846, entries: [entry("authors.py"), entry("books.py", false, "M")] } };
const HIDDEN_FOLDERS = { ...FOLDERS, "": { more: 0, entries: [entry(".git", true), ...FOLDERS[""].entries.slice(0, 4),
  entry(".env", false, null, true), entry(".gitignore"), ...FOLDERS[""].entries.slice(4)] } };

/** The Files view over FOLDERS with FIELDS (a file chosen, a name typed, a question asked, hidden files shown). */
function filesOf(fields = {}) {
  const view = Object.assign(Object.create(FilesView.prototype), { key: "styleguide", root: "/work/lumen-api",
    on: null, folders: FOLDERS, open: new Set(["src", "src/lumen"]), picked: null, naming: null, asking: null,
    note: null, hidden: false, loading: false, menus: new Menus(), previewTab: () => ({ id: "styleguide" }) }, fields);
  for (const name of INERT_FILES) view[name] = () => {};
  return view;
}

/** A name being typed in Files: ACTION's, for PATH, TYPED so far. @param {string} action @param {string} path
 * @param {string} typed */
function typing(action, path, typed) {
  const input = InputState.new({ placeholder: action === "rename" ? "New name" : "File name" });
  input.set_value(typed);
  return { action, path, input };
}

let chatViews = 0;                    // each drawn list's own slides (ChatsView.slides)

/** The Chats list over TALKS with FIELDS (typed, one renamed, the archived shown, loading). */
function chatsOf(fields = {}) {
  const view = Object.assign(Object.create(ChatsView.prototype), { slides: `${++chatViews}-`, overlay: "styleguide",
    items: TALKS, loaded: true, note: null, failed: null, archived: new Set(["claude:s9"]), typed: "",
    find: InputState.new({ placeholder: "Filter chats" }), opened: new Set(), closed: new Set(), naming: null,
    asking: null, leaving: new Set(), programs: {} }, fields);
  if (view.typed) view.find.set_value(view.typed);
  view.naming?.input.set_value(view.naming.item.title);
  // notes has no chat: left out
  view.rows = () => chatRows(view.items, ["lumen-api", "harbor-web", "notes"], PLACES, { typed: view.typed,
    archived: view.archived, showArchived: fields.showArchived === true, opened: view.opened, closed: view.closed,
    here: "lumen-api", front: new Set(["t1"]) });
  for (const name of INERT_CHATS) view[name] = () => {};
  return view;
}

/** STATE's Issues view, listing LISTED, with FIELDS (filters, a row asked about, a menu open). */
function issuesOf(state, fields) {
  const issues = Object.assign(new IssuesView(state), { listing: LISTING }, fields);
  for (const name of INERT_ISSUES) issues[name] = () => {};
  return issues;
}

/** The preview tab with FIELDS: what it shows, loading, or why nothing; its board's size draws nothing anew here. */
function previewOf(fields) {
  return Object.assign(new Preview("styleguide", null), { what: { n: 0, level: 1, ranked_by: "priority: high" },
    fit: () => {} }, fields);
}

/** What Claude asks: TOOL with its INPUT and SUGGESTIONS (core/chat_hook.py's request.json), in KIND's way. */
const asked = (tool, input, suggestions = [], kind = "permission") => ({ id: tool, kind, tool_name: tool,
  tool_input: input, permission_suggestions: suggestions, cwd: "/work/lumen-api" });
// Claude's change to books.py, as core/chat.py and the hook give it: its diff's lines
const CHANGE = { path: "src/lumen/routes/books.py", lines: ["@@ -12,2 +12,2 @@", "     last = store.pages(size)",
  "-    return page", "+    return min(max(page, 1), last)"] };
// what Claude waits on, a card each: a command a rule may keep, a change, a plan asked in its own dialog, a question
const WAITS = [
  ["A command, kept for the project", [asked("Bash", { command: "pytest -q", description: "Run the tests" },
    [{ type: "addRules", rules: [{ toolName: "Bash", ruleContent: "pytest:*" }], behavior: "allow",
      destination: "localSettings" }])]],
  ["A change", [{ ...asked("Edit", { file_path: "/work/lumen-api/src/lumen/routes/books.py",
    old_string: "    return page", new_string: "    return min(max(page, 1), last)" },
    [{ type: "setMode", mode: "acceptEdits", destination: "session" }]), change: CHANGE }]],
  ["A plan, in Claude's own dialog", [asked("ExitPlanMode", { plan: "1. Keep the page inside 1 to pages\n" +
    "2. Test the page past the end" }, [], "dialog"), [{ key: "1", label: "Yes, and use auto mode" },
    { key: "2", label: "Yes, manually approve edits" }, { key: "3", label: "Tell Claude what to change" }]]],
  ["A question", [asked("AskUserQuestion", { questions: [{ question: "Which page size should the list use?",
    header: "Size", options: [{ label: "20", description: "As the API's other lists" },
      { label: "50", description: "Fewer requests" }], multiSelect: false }] })]]];
const minute = (/** @type {number} */ n) => `2026-11-08T14:${String(n).padStart(2, "0")}:00.000Z`;
// a chat as core/chat.py reads it: the person's message, Claude reading, changing, testing, its words, and a
// command it waits on
const STEPS = [
  { kind: "user", text: "The last page link 404s on /books. Keep the page inside the range.", at: minute(0) },
  { kind: "skill", id: "s1", name: "api-routes", input: {}, at: minute(1) },
  { kind: "result", id: "s1", ok: true, output: "Launching skill: api-routes", change: null, at: minute(1) },
  { kind: "tool", id: "c1", name: "Read", main: "src/lumen/routes/books.py", input: {}, at: minute(1) },
  { kind: "result", id: "c1", ok: true, output: "12\t    last = store.pages(size)", change: null, at: minute(1) },
  { kind: "tool", id: "c2", name: "Edit", main: "src/lumen/routes/books.py", input: {}, at: minute(2) },
  { kind: "result", id: "c2", ok: true, output: "The file was updated.", change: CHANGE, at: minute(2) },
  { kind: "tool", id: "c3", name: "Bash", main: "pytest -q tests/test_books.py", input: {}, at: minute(3) },
  { kind: "result", id: "c3", ok: false, output: "1 failed, 11 passed", change: null, at: minute(3) },
  { kind: "text", text: "The page is kept inside 1 to pages now; one test still expects a 404 past the end.",
    at: minute(4) },
  { kind: "tool", id: "c4", name: "Bash", main: "pytest -q", input: {}, at: minute(5) }];

// a chat's task list as core/plan.py words it (plan-todo.html's), and its changes as the timeline tells them
const PLAN = { steps: [{ text: "Keep the page inside 1…pages", state: "done", after: null },
  { text: "Answer page 0 with the first page", state: "done", after: null },
  { text: "Answer a page below one with the first", state: "done", after: null },
  { text: "Add the tests past the end and below one", state: "now", after: null },
  { text: "Note it under Unreleased in CHANGELOG.md", state: "next", after: null },
  { text: "Run the whole suite", state: "next", after: "after Add the tests past the end and below one" }],
note: null, done: "3 done", count: "3 of 6 done", finished: false, plan: 4 };
const PLAN_DONE = { ...PLAN, steps: PLAN.steps.map((step) => ({ ...step, state: "done", after: null })),
  done: "6 done", count: "All 6 done", finished: true };
const PLANNED = [{ kind: "tool", id: "p1", name: "ExitPlanMode", main: null, input: {}, at: minute(1) },
  { kind: "result", id: "p1", ok: true, output: "Approved.", change: null, plan: 4, at: minute(1) },
  ...PLAN.steps.map((_step, n) => ({ kind: "tasks", id: `k${n}`, added: 1, at: minute(2) })),
  { kind: "tool", id: "c1", name: "Edit", main: "src/lumen/routes/books.py", input: {}, at: minute(3) },
  { kind: "result", id: "c1", ok: true, output: "The file was updated.", change: null, at: minute(3) },
  { kind: "task", id: "k7", text: PLAN.steps[0].text, at: minute(3) },
  { kind: "tool", id: "c2", name: "Edit", main: "tests/test_books.py", input: {}, at: minute(4) }];

// lumen-api's skills, as agent_setup.py reads them: the project's, the user's own, a plugin's, a dozen more of each
const SKILLS = [["api-routes", "How lumen-api's routes are written and tested", "Project"],
  ["frontend-design", "Distinctive, intentional visual design", "Global"],
  ["code-review", "Review a pull request", "code-review"], ["db-migrations", "Write and check a migration", "Project"],
  ["error-format", "The API's problem details, field by field", "Project"],
  ["fixtures", "Seed the test database with books and shelves", "Project"],
  ["openapi", "Keep openapi.yaml in step with the routes", "Project"],
  ["release-notes", "Write a release's notes", "Global"],
  ["commit-style", "Conventional Commits, as this repository writes them", "Global"],
  ["load-test", "Run k6 against a route and read the result", "Global"],
  ["security-review", "Review the changes for security problems", "code-review"],
  ["pr-summary", "Sum up a pull request for its description", "code-review"],
  ["brainstorming", "Turn an idea into a design before building it", "superpowers"],
  ["writing-plans", "Write a plan a task at a time", "superpowers"],
  ["systematic-debugging", "Find a bug's cause before fixing it", "superpowers"]];
/** What Claude starts with in lumen-api (agent_setup.py's), as center-chat.html's Context panel has it, the user's own
 * files under HOME (this Mac's: ~ in the panel). @param {string} mine */
const setupOf = (mine) => ({ default_mode: null,
  rules: [{ path: `${mine}/.claude/CLAUDE.md`, scope: "Global", tokens: 2400, paths: [] },
    { path: "/work/lumen-api/CLAUDE.md", scope: "Project", tokens: 1800, paths: [] },
    { path: "/work/lumen-api/.claude/rules/api.md", scope: "Project", tokens: 700, paths: ["src/lumen/**"] }],
  skills: SKILLS.map(([name, description, source]) => ({ name, description, source,
    scope: source === "Project" ? "Project" : "Global", tokens: Math.round((name + description).length / 4),
    path: `${source === "Project" ? "/work/lumen-api" : mine}/.claude/skills/${name}/SKILL.md` })) });
// lumen-api's connectors as agent_setup.py's setup tells them, connectors.html's six: one failed, one to sign in
const SERVERS = [["sentry", "sentry", "sentry", "failed"], ["claude.ai Box", "Box", "box", "sign in"],
  ["claude.ai Google Drive", "Google Drive", "google-drive", "on"], ["claude.ai Linear", "Linear", "linear", "on"],
  ["claude.ai Notion", "Notion", "notion", "off here"], ["Dropbox", "Dropbox", "dropbox", "on"]]
  .map(([name, label, brand, state]) => ({ name, label, brand, state }));
/** SERVERS with NAME in STATE. @param {string} name @param {string} state */
const serversWith = (name, state) => SERVERS.map((one) => (one.name === name ? { ...one, state } : one));
// connectors.html's chat: the spec read from Google Drive, books.py read, then Box asking for a sign-in; a
// server the setup does not name drawn by its key
const DRIVE = "mcp__claude_ai_Google_Drive__";
const CONNECTED = [
  { kind: "user", text: "Pull the paging spec from the Drive and check books.py against it.", at: minute(4) },
  { kind: "tool", id: "d1", name: `${DRIVE}search_files`, main: null, input: { query: "paging spec" }, at: minute(4) },
  { kind: "result", id: "d1", ok: true, output: "Lumen API: paging, v2", change: null, at: minute(4) },
  { kind: "tool", id: "d2", name: `${DRIVE}read_file`, main: null, input: { title: "Lumen API: paging, v2" },
    at: minute(4) },
  { kind: "result", id: "d2", ok: true, output: "A page past the last one answers the last page.", change: null,
    at: minute(4) },
  { kind: "tool", id: "d3", name: "Read", main: "src/lumen/routes/books.py", input: {}, at: minute(5) },
  { kind: "result", id: "d3", ok: true, output: "12\t    last = store.pages(size)", change: null, at: minute(5) },
  { kind: "tool", id: "d4", name: "mcp__harbor-docs__search", main: null, input: { query: "paging" }, at: minute(5) },
  { kind: "result", id: "d4", ok: true, output: "No results", change: null, at: minute(5) },
  { kind: "text", text: "The spec answers a page past the last one with the last page; `books.py` answers an empty "
    + "list. The spec cites design notes kept in Box.", at: minute(5) },
  { kind: "signin", server: "claude.ai Box", at: minute(5) }];
// Add context's list in lumen-api (core/search.py's files, core/git.py's changed ones)
const FOLDER_FILES = { changed: ["src/lumen/routes/books.py", "tests/test_books.py"],
  files: ["CLAUDE.md", "README.md", "docs/error format.md", "docs/paging.md", "openapi.yaml", "pyproject.toml",
    "src/lumen/routes/books.py", "src/lumen/routes/shelves.py", "src/lumen/store.py", "tests/test_books.py",
    "tests/test_shelves.py"] };

// a skill this chat used, today at 1:32 PM (the Context panel's "used" in this Mac's form of a time)
const USED = [{ kind: "skill", id: "s1", name: "api-routes", ok: true, open: false,
  at: new Date(new Date().setHours(13, 32, 0, 0)).toISOString() }];

/** The chat drawn by its own code: its ROWS, the CONTEXT used (%), what is TYPED (the cursor in the prompt), its
 * agent's STATE, the usage LIMITS near their end, what it WAITS on ([request, choices]; its card made with CX). */
// the app's agents (knownAgents), as a new chat's list offers them: Claude and Codex used last, Aider not installed
const KNOWN_AGENTS = [{ key: "claude", name: "Claude", icon: ICONS.sparkle, tint: true, run: ["claude"],
  installed: true }, { key: "codex", name: "Codex", icon: ICONS.bot, tint: true, run: ["codex"], installed: true },
  { key: "gemini", name: "Gemini", icon: ICONS.sparkles, tint: true, run: ["gemini"], installed: true },
  { key: "aider", name: "Aider", icon: ICONS.code, tint: true, run: ["aider"], installed: false }];
// the Agent panel's layers as core words them (agent_layers.py's layers()): Claude in lumen-api as connectors.html's
// Áttekintés has it, sentry failed, figma to sign in, a permission hidden by another
/** A layer's row, OVER its name: TAG its source's word, MARK its one mark. @param {string} icon @param {string} name
 * @param {Record<string, any>} [over] */
const layer = (icon, name, over = {}) => ({ id: `${icon}:${name}:${over.tag ?? ""}`, icon, name, note: null,
  tag: null, mark: null, state: null, brand: null, tokens: null, cost: null, agents: ["claude"], dim: false, ...over,
  properties: { title: name, state: over.state ?? null, lines: [], text: null, error: null, tip: null, actions: [],
    ...over.properties } });
const said = (/** @type {string} */ text, /** @type {string} */ tone) => ({ text, tone });
/** A row's actions, the first one primary, as core's: [id, label, its file or its server].
 * @param {...[string, string, string]} list */
const acts = (...list) => list.map(([id, label, at], n) => ({ id, label, primary: !n,
  path: id === "open" ? at : null, server: id === "open" ? null : at }));
const LUMEN = "/work/lumen-api";
const GRAPHED = /** @type {[string, string, string]} */ (["graph", "Show in graph", ""]);
// the rows chosen in the properties' specimens, as core words each kind
const SENTRY = layer("plug", "sentry", { id: "connector:sentry", tag: "Project", mark: "bad",
  state: said("failed", "bad"), brand: "sentry",
  properties: { lines: [["From", ".mcp.json", "Project"], ["Runs", "npx -y @sentry/mcp-server", null]],
    error: "spawn npx ENOENT: npx is not on this machine's PATH",
    actions: acts(["retry", "Retry", "sentry"], ["open", "Open .mcp.json", `${LUMEN}/.mcp.json`], GRAPHED) } });
const FIGMA = layer("plug", "figma", { id: "connector:figma", tag: "figma", mark: "warn",
  state: said("sign in", "warn"), brand: "figma",
  properties: { lines: [["From", "figma", "Plugin"], ["URL", "mcp.figma.com", null]],
    actions: acts(["connect", "Connect", "figma"], ["turn-off", "Turn off in lumen-api", "figma"], GRAPHED) } });
const API_RULE = layer("file", "api.md", { tag: "Project", tokens: 700, cost: "700", note: "when src/lumen/** is read",
  dim: true, properties: { lines: [["From", ".claude/rules/api.md", "Project"], ["Paths", "src/lumen/**", null]],
    text: "# The API's routes\nEvery route answers JSON, an error as problem details (RFC 9457).\n"
      + "A list is paged: `page` and `size`, the last page for one past it.",
    actions: acts(["open", "Open api.md", `${LUMEN}/.claude/rules/api.md`], GRAPHED) } });
const API_SKILL = layer("skill", "api-routes", { tag: "Project", mark: "ok", tokens: 300, cost: "300",
  properties: { lines: [["From", ".claude/skills/api-routes/SKILL.md", "Project"], ["Used", "in this chat", null]],
    text: "How lumen-api's routes are written and tested: the handler, its schema, its problem details "
      + "and the test beside it. Use when adding or changing a route.",
    actions: acts(["open", "Open SKILL.md", `${LUMEN}/.claude/skills/api-routes/SKILL.md`], GRAPHED) } });
const REVIEWER = layer("bot", "code-reviewer", { id: "subagent:pr-review:code-reviewer", tag: "pr-review",
  note: "Opus · 4 tools", mark: "ok",
  properties: { lines: [["From", "pr-review", "Plugin"], ["Model", "opus", null], ["Tools", "Read, Grep, Glob, Bash",
    null], ["Used", "2 times in this chat", null]],
  text: "Reviews the changes for bugs, the project's conventions and missing tests.",
  actions: acts(["open", "Open code-reviewer.md", "/home/dev/.claude/plugins/pr-review/agents/code-reviewer.md"],
    GRAPHED) } });
const BUILT_IN = ["Explore", "Plan", "general-purpose", "statusline-setup", "output-style-setup"];
const BUILT_INS = { ...layer("bot", BUILT_IN.slice(0, 3).join(", "), { id: "subagent:built-in", tag: "Built-in",
  note: "2 more", properties: { title: "Built-in", lines: [["From", "Claude", "Built-in"], ["Explore",
    "Haiku · read-only", null], ["Plan", "read-only", null], ["general-purpose", "", null], ["statusline-setup",
    "2 tools", null], ["output-style-setup", "4 tools", null]] } }), names: BUILT_IN };
const CONFLICT = layer("shield", "Bash(git push:*)", { id: "conflict:allow:Bash(git push:*)", mark: "warn",
  note: "deny in Project hides allow in Global", properties: {
    lines: [["Allow", "Bash(git push:*)", "Global"], ["Deny", "Bash(git push:*)", "Project"]],
    actions: acts(["open", "Open .claude/settings.json", `${LUMEN}/.claude/settings.json`],
      ["open", "Open ~/.claude/settings.json", "/home/dev/.claude/settings.json"]) } });
const HOOK = /** @type {{ text: string, tone: string }} */ (said("hook", "muted"));
/** A hook's row as core words it: its event (and matcher) its note. @param {string} name @param {string} note
 * @param {string} tag @param {Record<string, any>} [over] */
const hookOf = (name, note, tag, over = {}) => layer("hook", name, { id: `hook:${tag}:${note}:${name}`, note, tag,
  state: HOOK, ...over });
const GUARD = hookOf("guard.sh", "on PreToolUse · Bash", "Project", { properties: { lines: [["On",
  "PreToolUse · Bash", null], ["From", ".claude/settings.json", "Project"], ["Runs", "./scripts/guard.sh", null]],
actions: acts(["open", "Open settings.json", `${LUMEN}/.claude/settings.json`], GRAPHED) } });
const HOOKS = [GUARD, hookOf("herdr-fold", "on PermissionRequest", "Global"),
  hookOf("context.sh", "SessionStart · adds context", "Global"), hookOf("notify.sh", "on Stop", "Global")];
const ALLOWED = ["Bash(npm test)", "Bash(npm run lint)", "Read(src/**)", "Edit(src/**)", "Bash(git status)",
  "Bash(git diff *)", "Bash(git log *)", "WebFetch(domain:docs.lumen.dev)", "Bash(ls *)", "Bash(pytest *)", "Grep"];
// what a sign-in and the add form say (agent_layers.py's connecting()), Claude's and Codex's
const CONNECT = { state: said("signing in", "busy"), words: "Finish in your browser",
  actions: [{ id: "reopen", label: "Open the page again" }, { id: "cancel", label: "Cancel" }],
  needs: { "turn-off": "Start a chat in lumen-api to turn it off",
    "turn-on": "Start a chat in lumen-api to turn it on" },
  add: { tip: "Add a connector", title: "Add a connector", menu: [{ id: "claude-ai", label: "From claude.ai…",
    url: "https://claude.ai/settings/connectors" }, { id: "url", label: "By URL…", url: null }],
  fields: { name: "Name", url: "URL", scope: "For" }, scopes: [{ id: "local", label: "lumen-api" },
    { id: "user", label: "All projects" }], submit: "Add and connect", cancel: "Cancel" } };
const CODEX_CONNECT = { ...CONNECT, add: { ...CONNECT.add, menu: CONNECT.add.menu.slice(1), scopes: [] } };
/** The head as core words it: the agent, its LINE, the PROBLEMS (each [text, tone, row]).
 * @param {string} name @param {string} where @param {string} line @param {[string, string, string][]} problems */
const headOf = (name, where, line, problems) => ({ name, where, line, model: line.split(" · ")[0],
  effort: line.split(" · ")[1], problems: problems.map(([text, tone, row]) => ({ text, tone, row })) });
/** What loads at start, each part's TOKENS and share (core's bar). @param {number[]} tokens */
const barOf = (...tokens) => ["rules", "skills", "connectors"].map((part, n) => ({ part, tokens: tokens[n],
  share: tokens[n] / Math.max(1, tokens.reduce((sum, one) => sum + one, 0)) }));
/** A section as core words it, its swatch its own bar part's. @param {string} id @param {string} title
 * @param {number | null} count @param {string | null} cost @param {any[]} rows @param {Record<string, any>} [over] */
const sectionOf = (id, title, count, cost, rows, over = {}) => ({ id, title, count, tokens: null, cost,
  swatch: ["rules", "skills", "connectors"].includes(id) ? id : null, summary: [], rows, groups: [], ...over });
const PROBLEMS_SAID = /** @type {[string, string, string][]} */ ([["1 failed", "bad", "connector:sentry"],
  ["1 sign in", "warn", "connector:figma"]]);
const LAYERS = { head: headOf("Claude", "in lumen-api", "Opus 5.5 · High · starts at 34.2k of 1M", PROBLEMS_SAID),
  bar: barOf(5400, 4000, 11400), error: null, connect: CONNECT,
  sections: [
    sectionOf("subagents", "Subagents", 7, null, [REVIEWER, layer("bot", "doc-checker", { id:
      "subagent:Project:doc-checker", tag: "Project", note: "Haiku · read-only" }), BUILT_INS]),
    sectionOf("rules", "Rules", 3, "5.4k", [
      layer("file", "~/.claude/CLAUDE.md", { tag: "Global", tokens: 2400, cost: "2.4k" }),
      layer("file", "CLAUDE.md", { tag: "Project", tokens: 1800, cost: "1.8k" }),
      layer("file", "AGENTS.md", { tag: "Project", tokens: 1200, cost: "1.2k", agents: ["claude", "codex"] }),
      API_RULE]),
    sectionOf("skills", "Skills", SKILLS.length + 1, "4.0k", [
      API_SKILL, ...SKILLS.slice(1).map(([name, , source], n) => layer("skill", name, { tag: source,
        tokens: 200 - Math.min(n, 1) * 100, cost: String(200 - Math.min(n, 1) * 100) })),
      layer("skill", "changelog", { tag: "Global", tokens: 100, cost: "100" })]),
    sectionOf("permissions", "Permissions", null, null, [
      layer("shield", "Mode", { id: "mode", note: "Edit automatically", tag: "Project" }),
      layer("shield", "Sandbox", { id: "sandbox", note: "Bash · 2 hosts", tag: "Project" }),
      CONFLICT,
      ...["Bash(git push:*)", "Bash(rm -rf *)"].map((name) => layer("shield", name, { tag: "Project",
        state: said("deny", "deny") })),
      ...["Bash(git commit *)", "Bash(docker *)", "WebFetch"].map((name) => layer("shield", name,
        { tag: "Project", state: said("ask", "ask") })),
      ...ALLOWED.map((name) => layer("shield", name, { tag: "Global", state: said("allow", "allow") }))],
    { summary: [said("12 allow", "allow"), said("3 ask", "ask"), said("2 deny", "deny")],
      groups: [{ id: "hooks", title: "Hooks", count: HOOKS.length, rows: HOOKS }] }),
    sectionOf("connectors", "Connectors", 4, "11.4k", [
      SENTRY, FIGMA,
      layer("plug", "github", { tag: "Global", state: said("32 tools", "ok"), tokens: 6800, cost: "6.8k",
        agents: ["claude", "codex"] }),
      layer("plug", "chrome-devtools", { tag: "chrome-devtools-mcp", state: said("26 tools", "ok"), tokens: 4600,
        cost: "4.6k", mark: "ok" })])] };
// Codex in tidepool, as its own setup reads: its rules, its approval and sandbox, a server off; nothing of claude.ai's
const CODEX_LAYERS = { head: headOf("Codex", "in tidepool", "GPT-5.2 Codex · High · starts at 3.1k of 400k", []),
  bar: barOf(1900, 0, 1200), error: null, connect: CODEX_CONNECT,
  sections: [
    sectionOf("rules", "Rules", 2, "1.9k", [
      layer("file", "~/.codex/AGENTS.md", { tag: "Global", tokens: 700, cost: "700" }),
      layer("file", "AGENTS.md", { tag: "Project", tokens: 1200, cost: "1.2k", agents: ["claude", "codex"] })]),
    sectionOf("permissions", "Permissions", null, null, [
      layer("shield", "Approval", { id: "approval", note: "Ask on request", tag: "Global" }),
      layer("shield", "Sandbox", { id: "sandbox", note: "Workspace write", tag: "Global" }),
      layer("shield", "git status", { tag: "Global", state: said("allow", "allow") }),
      layer("shield", "git push", { tag: "Global", state: said("ask", "ask") })],
    { summary: [said("1 allow", "allow"), said("1 ask", "ask")] }),
    sectionOf("connectors", "Connectors", 2, "1.2k", [
      layer("plug", "linear", { tag: "Global", state: said("on", "ok"), tokens: 1200, cost: "1.2k", brand: "linear",
        id: "connector:linear", properties: { lines: [["From", "~/.codex/config.toml", "Global"],
          ["URL", "mcp.linear.app/mcp", null]], actions: acts(["sign-out", "Sign out", "linear"],
          ["open", "Open config.toml", "/home/dev/.codex/config.toml"], GRAPHED) } }),
      layer("plug", "notion", { tag: "Global", state: said("off", "off"), dim: true, brand: "notion" })])] };
// Codex where `codex mcp list` gave no list, as core says it: Connectors one dim row, not read, no count
const UNLISTED = layer("plug", "Codex's servers", { id: "unread:connectors", state: said("not read", "off"),
  dim: true, agents: ["codex"], properties: { title: "Connectors", text: "`codex mcp list` gave no list, so which "
    + "servers Codex has is not known here." } });
const CODEX_UNLISTED = { ...CODEX_LAYERS, bar: barOf(1900, 0, 0), sections: CODEX_LAYERS.sections.map((section) =>
  (section.id !== "connectors" ? section : { ...section, count: null, cost: null, rows: [UNLISTED] })) };
// lumen-api's connectors as connectors.html's Agent panel has them: sentry failed, Box to sign in, Google Drive used,
// Linear on, Notion off here, Dropbox the user's own; STATE and ACTS Box's, as each frame has it
/** @param {{ text: string, tone: string }} state @param {[string, string, string][]} does
 * @param {[string, string, string | null][]} [more] */
const boxOf = (state, does, more = []) => layer("plug", "Box", { id: "connector:claude.ai Box", tag: "claude.ai",
  brand: "box", state, mark: state.tone === "warn" ? "warn" : more.length ? "ok" : null, properties: { lines: [
    ["From", "claude.ai", "Account"], ["URL", "mcp.box.com", null], ...more], actions: acts(...does) } });
const BOX = "claude.ai Box";
const BOX_IN = boxOf(said("sign in", "warn"), [["connect", "Connect", BOX], ["turn-off", "Turn off in lumen-api",
  BOX]]);
const BOX_ON = boxOf(said("on", "ok"), [["turn-off", "Turn off in lumen-api", BOX], ["sign-out", "Sign out", BOX]],
  [["Used", "once in this chat", null]]);
const NOTION = layer("plug", "Notion", { id: "connector:claude.ai Notion", tag: "claude.ai", brand: "notion",
  dim: true, state: said("off here", "off"), properties: { lines: [["From", "claude.ai", "Account"],
    ["URL", "mcp.notion.com", null]], actions: acts(["turn-on", "Turn on in lumen-api", "claude.ai Notion"]) } });
/** The panel's layers with BOX as given, the other sections folded away. @param {any} box */
const connectorsOf = (box) => ({ ...LAYERS, head: { ...LAYERS.head, problems: [LAYERS.head.problems[0],
  ...(box.state.tone === "warn" ? [{ ...said("1 sign in", "warn"), row: box.id }] : [])] },
sections: LAYERS.sections.map((section) => (section.id !== "connectors" ? section : { ...section, count: 6, rows: [
  SENTRY, box,
  layer("plug", "Google Drive", { tag: "claude.ai", brand: "google-drive", state: said("on", "ok"), mark: "ok",
    tokens: 3200, cost: "3.2k" }),
  layer("plug", "Linear", { tag: "claude.ai", brand: "linear", state: said("on", "ok"), tokens: 2900, cost: "2.9k" }),
  NOTION,
  layer("plug", "Dropbox", { tag: "Global", brand: "dropbox", state: said("on", "ok"), tokens: 1100,
    cost: "1.1k" })] })) });
/** The add form as typed: NAME and URL, the keys in FOCUS. @param {string} name @param {string} url
 * @param {Record<string, any>} [over] */
function formOf(name, url, over = {}) {
  const fields = { name: InputState.new({ placeholder: "" }), url: InputState.new({ placeholder: "" }) };
  if (name) fields.name.set_value(name);
  if (url) fields.url.set_value(url);
  return { ...fields, scope: "local", focus: "url", error: null, busy: false, ...over };
}
const OTHERS = ["rules", "permissions", "skills", "subagents"];     // folded, Connectors alone open
const SECTIONS = ["subagents", "rules", "skills", "permissions", "connectors"];      // every section folded
// Usage as core words it (usage.py's section()), as usage-agents.html's frames: Claude on Max at 72% of its 5 hours,
// Codex on an API key from the report's month; a window is [used, level], used null: "–"
const RESETS = new Date(2026, 10, 13, 14, 46).getTime() / 1000, WEEK_RESETS = new Date(2026, 10, 16, 9, 0).getTime()
  / 1000;
/** @param {string} label @param {[number | null, string] | null} one @param {number} at */
const windowOf = (label, one, at) => one && { label, used: one[0], text: one[0] === null ? "–" : `${one[0]}%`,
  level: one[0] === null ? null : one[1], resets: one[0] === null ? null : { at, words: label === "5h"
    ? "5h resets {time}" : "Week resets {day} {time}" } };
/** An agent's row: its windows, the tighter, the reset shown under it while that one is yellow or red.
 * @param {string} key @param {string} name @param {string | null} plan @param {[number | null, string] | null} five
 * @param {[number | null, string] | null} week @param {Record<string, any>} [over] */
const meter = (key, name, plan, five, week, over = {}) => {
  const told = { five: windowOf("5h", five, RESETS), week: windowOf("wk", week, WEEK_RESETS) };
  const known = [told.five, told.week].filter((one) => one && one.used !== null);
  const tight = known.reduce((most, one) => (!most || Number(one?.used) > Number(most.used) ? one : most), null);
  return { key, name, plan, current: key === "claude", ...told, tight,
    reset: tight && ["warn", "bad"].includes(String(tight.level)) ? tight.resets : null, age: "Read 3 min ago",
    ...over };
};
const UNTOLD = { text: "limits not told", why: "Codex tells its limits in a chat's token counts: none of its newest "
  + "chats holds one yet." };
const CLAUDE_USE = meter("claude", "Claude", "Max", [72, "warn"], [16, "ok"]);
const usageOf = (/** @type {any[]} */ ...rows) => ({ id: "usage", title: "Usage", none: "Not known yet", rows });
const USAGE = usageOf(CLAUDE_USE);
const INERT_AGENT = ["act", "add", "answer", "cancel", "change", "check", "choose", "connect", "drop", "dropForm",
  "focusField", "follow", "list", "listKey", "offer", "open", "pick", "plan", "read", "readAgents", "readUsage",
  "readMonths", "reopen", "reveal", "run", "save", "search", "settle", "showWays", "signOut", "start", "submit",
  "tell", "toggle", "undo", "watch", "watchSignIns", "waysKey"];
// a row's form as core plans it (harness.py's plan), as harness-editing.html's frames: a plan of FIELDS, OVER
// changing it; a choice's field ([id, label, why it is grey]), a text's, a switch's; the layers, CHOSEN's file shown
/** @param {any[]} fields @param {Record<string, any>} [over] */
const planOf = (fields, over = {}) => ({ fields, saved: "Saved in", layers: [], changes: [], when: null, warns: [],
  ask: null, submit: null, cancel: "Cancel", remove: null, error: null, edits: [], done: null, undo: "Undo", say: [],
  now: null, more: null, ...over });
/** @param {string} id @param {string} label @param {string | null} value
 * @param {[string, string, (string | null)?][]} list @param {string | null} [hint] */
const choiceOf = (id, label, value, list, hint = null) => ({ id, label, kind: "choice", value, hint,
  choices: list.map(([id, label, off = null]) => ({ id, label, off })) });
const textOf = (/** @type {string} */ id, /** @type {string} */ label, /** @type {any[]} */ items = []) =>
  ({ id, label, kind: "text", value: "", items });
const switchOf = (/** @type {boolean} */ value, label = "On in lumen-api", turn = { on: "Turn on in lumen-api",
  off: "Turn off in lumen-api" }) => ({ id: "on", label, kind: "switch", value, short: "On here", turn });
const FILES = { Global: "~/.claude/settings.json", Project: ".claude/settings.json",
  Local: ".claude/settings.local.json" };
const savedIn = (/** @type {string} */ chosen, names = ["Global", "Project", "Local"], files = FILES) =>
  names.map((id) => ({ id, label: id, path: /** @type {any} */ (files)[id], chosen: id === chosen }));
/** A file's change, a line [sign, text]. @param {string} path @param {...[string, string]} lines */
const changed = (path, ...lines) => ({ path, lines });
/** A form on PLAN, touched unless OVER says not; TYPED its text fields' words. @param {any} plan
 * @param {Record<string, any>} [over] @param {Record<string, string>} [typed] */
function editOf(plan, over = {}, typed = {}) {
  const inputs = Object.fromEntries(Object.entries(typed).map(([id, words]) => {
    const input = InputState.new({ placeholder: "" });
    if (words) input.set_value(words);
    return [id, input];
  }));
  return { base: { action: "" }, ask: { action: "" }, name: null, plan, inputs, typed, focus: null, touched: true,
    busy: false, error: null, note: null, submit: plan.submit, serial: 0, planned: 0, ...over };
}
const MODES = /** @type {[string, string, (string | null)?][]} */ ([["default", "Manual"], ["acceptEdits",
  "Edit automatically"], ["plan", "Plan"], ["auto", "Auto"], ["dontAsk", "Don't ask"], ["bypassPermissions",
  "Bypass"]]);
const ONLY_GLOBAL = "Auto and Bypass permissions work only in Global";
const MODE_IN = choiceOf("value", "Mode", "acceptEdits", MODES.map(([id, label]) => [id, label,
  ["auto", "bypassPermissions"].includes(id) ? ONLY_GLOBAL : null]), ONLY_GLOBAL);
const BEHAVIORS = /** @type {[string, string][]} */ ([["allow", "allow"], ["ask", "ask"], ["deny", "deny"]]);
const ruleOf = (/** @type {string} */ behavior) => [textOf("rule", "Rule"), choiceOf("behavior", "Behavior", behavior,
  BEHAVIORS)];
const WAYS = /** @type {[string, string][]} */ ([["remove", "Remove the deny in Project"], ["narrow",
  "Narrow the deny"]]);
const wayOf = (/** @type {string | null} */ value) => choiceOf("way", "deny in Project hides allow in Global", value,
  WAYS);
const EFFORTS = /** @type {[string, string][]} */ ([["low", "Low"], ["medium", "Medium"], ["high", "High"],
  ["xhigh", "Extra high"]]);
// the layers the forms' specimens stand on: Permissions alone open, a few rules, an organization's, no hooks
const PYTEST = layer("shield", "Bash(pytest:*)", { id: "permission:allow:Bash(pytest:*)", tag: "Project",
  state: said("allow", "allow"), properties: { lines: [["From", ".claude/settings.json", "Project"]],
    actions: acts(["open", "Open settings.json", `${LUMEN}/.claude/settings.json`]) } });
const CURL = layer("shield", "Bash(curl:*)", { id: "permission:ask:Bash(curl:*)", tag: "Project",
  state: said("ask", "ask"), properties: PYTEST.properties });
const ENV = layer("shield", "Read(./.env)", { id: "permission:deny:Read(./.env)", tag: "Managed",
  state: said("deny", "deny"), properties: { lines: [["From",
    "/Library/Application Support/ClaudeCode/managed-settings.json", "Managed"]] } });
/** LAYERS with section ID changed by OVER. @param {string} id @param {(section: any) => Record<string, any>} over */
const layersWith = (id, over, found = LAYERS) => ({ ...found,
  sections: found.sections.map((/** @type {any} */ one) => (one.id === id ? { ...one, ...over(one) } : one)) });
const RULED = layersWith("permissions", (one) => ({ rows: [...one.rows.slice(0, 3), PYTEST, CURL, ENV], groups: [] }));
const UNSET = layersWith("permissions", () => ({ groups: [], rows: [
  layer("shield", "Mode", { id: "mode", note: "Manual", tag: "Default", properties: { lines: [["From",
    "Claude's default", null]] } }),
  layer("shield", "Sandbox", { id: "sandbox", note: "off", tag: "Default" })] }));
const HOOKS_OFF = layersWith("permissions", (one) => ({ rows: one.rows.slice(0, 2), groups: [{ ...one.groups[0],
  state: said("off here", "off"), rows: HOOKS.map((hook) => ({ ...hook, dim: true })) }] }));
const CHANGELOG_OFF = layer("skill", "changelog", { id: "skill:changelog", tag: "Project", dim: true,
  state: said("off here", "off"), tokens: 100, cost: "100", properties: { lines: [["From",
    ".claude/skills/changelog/SKILL.md", "Project"]], text: "Writes the changelog's next entry from the commits.",
  actions: acts(["open", "Open SKILL.md", `${LUMEN}/.claude/skills/changelog/SKILL.md`]) } });
const SKILLED = layersWith("skills", (one) => ({ rows: [one.rows[0], CHANGELOG_OFF] }));
const BUILT_OFF = layersWith("subagents", (one) => ({ rows: [...one.rows.slice(0, 2), { ...BUILT_INS,
  off: ["Plan"], properties: { ...BUILT_INS.properties, lines: BUILT_INS.properties.lines.map((line) =>
    (line[0] === "Plan" ? ["Plan", "read-only", "off here"] : line)) } }] }));
const PENDING = layer("plug", "lumen-db", { id: "connector:lumen-db", tag: "Project", dim: true,
  state: said("not approved", "off"), properties: { lines: [["From", ".mcp.json", "Project"],
    ["Runs", "npx -y @lumen/db-mcp", null]], actions: acts(["open", "Open .mcp.json", `${LUMEN}/.mcp.json`]) } });
const GITHUB = "layer-github";
const SERVED = layersWith("connectors", (one) => ({ rows: [{ ...one.rows[2], id: GITHUB, properties: {
  ...one.rows[2].properties, lines: [["From", "~/.claude.json", "Global"], ["URL", "api.example.com/mcp", null]],
  actions: acts(["turn-off", "Turn off in lumen-api", "github"]) } }, PENDING] }));
const NOT_PERMS = ["rules", "skills", "connectors", "subagents"];
const LOCAL_SKILL = { layers: savedIn("Local", ["Project", "Local"]), when: "From the next session",
  submit: "Save" };
// the agents on this Mac as core tells them (agent_state.py agents), as agent-picker.html's list: Claude on Max,
// Codex on Plus, Gemini CLI to sign in, Aider not installed; OVER changes one, its row in the list as core words it
/** @param {string} key @param {string} name @param {Record<string, any>} [over] */
const machine = (key, name, over = {}) => {
  const one = { key, name, installed: true, signed_in: true, plan: null, login: [key, "login"],
    install: `npm install -g ${key}`, page: "https://example.com/agent", empty: null, ...over };
  const out = one.signed_in === false;
  return { ...one, listed: one.installed ? { group: "Agents on this Mac", dim: false, word: out ? "sign in"
    : one.plan, tone: out ? "warn" : null } : { group: "Not installed", dim: true, word: null, tone: null } };
};
const SIGN_IN = { kind: "sign-in", title: "Gemini CLI is not signed in", words: "It signs in its own way: Sign in "
  + "opens it in a terminal tab, and you finish there, or in the browser if it asks.", command: null,
  foot: "herdr-fold keeps no token.", actions: [{ id: "sign-in", label: "Sign in" }] };
const NOT_HERE = { kind: "install", title: "Codex is not installed", words: "It installs its own way: run its "
  + "command in a terminal, then choose it in the list.", command: "npm install -g @openai/codex",
  foot: "herdr-fold runs no installer.", actions: [{ id: "copy", label: "Copy" },
    { id: "page", label: "Open its page" }] };
const MACHINE = [machine("claude", "Claude", { plan: "Max" }), machine("codex", "Codex", { plan: "Plus" }),
  machine("gemini", "Gemini CLI", { signed_in: false, empty: SIGN_IN })];
const KNOWN_MACHINE = [...MACHINE, machine("aider", "Aider", { installed: false })];    // and one not installed
const PROBLEMS = { tone: "bad", said: "1 failed, 1 sign in" };       // the Agent tab's and the rail's dot
let agentViews = 0;                   // each drawn panel's own slides (AgentView.slides)

/** The Agent panel over FOUND (core's layers) with FIELDS (a filter typed, loading, not installed, a failed read),
 * drawn for AGENT. @param {any} found @param {Record<string, any>} [fields] @param {string} [agent] */
function agentOf(found, fields = {}, agent = "claude") {
  const view = Object.assign(Object.create(AgentView.prototype), { found, missing: false, error: null, query: "",
    slides: `${++agentViews}-`, more: new Set(), finding: Boolean(fields.query), chosen: null, failed: null,
    checking: new Set(), scroll: ScrollHandle.new(), agents: null, agentsError: null, listing: false, cursor: null,
    listPlaces: [], listScroll: null, looking: null, signing: null, copied: false, still: true, folder: LUMEN,
    usage: null, usageError: null, report: null, signed: new Set(), wants: null, addMenu: false, form: null, agent,
    due: [], edit: null, foot: null, addList: { cursor: null, listPlaces: [], listScroll: null },
    find: InputState.new({ placeholder: "Filter setup" }) }, fields);
  if (view.query) view.find.set_value(view.query);
  for (const name of INERT_AGENT) view[name] = () => {};
  // the servers signing in
  view.signingIn = () => Object.fromEntries((fields.signingIn ?? []).map((/** @type {string} */ name) => [name,
    { address: "t7", at: 0 }]));
  const look = { agent, programs: Object.fromEntries(KNOWN_AGENTS.map((p) => [p.key, p])), px: fields.px ?? PANEL,
    open: (/** @type {string} */ section) => !(fields.folded ?? ["subagents"]).includes(section) };
  return { draw: (/** @type {any} */ t) => view.draw(t, look),
    // Usage alone, in the layers' own frame
    limits: (/** @type {any} */ t) => v_flex().px(PAD / 2).py(4).gap(2).text_size(12).children(view.limits(t,
      view.usageRows(), look)),
    // Connectors' head with its + lit, the menu it opens drawn under it at the head's end
    ways: (/** @type {any} */ t) => v_flex().px(PAD / 2).py(4).gap(4).text_size(12)
      .child(view.section(t, found.sections.find((/** @type {any} */ one) => one.id === "connectors"), true,
        found.connect.add))
      .child(h_flex().justify_end().child(view.ways(t, found.connect.add)).child(div().w(COST_END).flex_none())),
    // its head with the chip lit, the list it opens drawn under it as it lies over the layers
    listed: (/** @type {any} */ t) => v_flex().size_full().child(view.head(t, found.head, look))
      .child(div().pl(PAD / 2).pt(4).child(view.listed(t, look))) };
}
// About's made-up check: this version, looked at today at noon
const ABOUT_FOUND = { version: "0.4.0", latest: "0.4.0", newer: false, on: true, error: null, updated: null,
  checked: new Date(2026, 10, 13, 12, 30).getTime() / 1000, releases: "https://example.com/releases",
  how: "git pull in its folder, then ./install.sh" };

function chatOf(cx, { rows = [], context = 34, typed = "", state = "idle", limits = null, waits = null, asks = false,
  shown = false, switches = {}, refused = {}, fresh = false, lit = null, cursor = null, folded = 0,
  model = ["claude-opus-5-5", "Opus 5.5"], effort = "high", first = {}, setup = null, setupError = null,
  menu = /** @type {string | null} */ (null), files = /** @type {string[]} */ ([]),
  mention = /** @type {string | null} */ (null), listed = /** @type {any} */ (null),
  listError = /** @type {string | null} */ (null), signing = {}, connectFailed = {}, toTell = [],
  budget = /** @type {any} */ (null), costs = /** @type {any} */ (null) } = {}) {
  const started = { address: "t1", named: { model: model[0], effort, mode: "default" },
    status: { model: model[1], effort, context, window: 200000, limits } };
  const props = { session: "styleguide", agent: "claude", folder: "/work/lumen-api" };
  const chat = Object.assign(new Chat(props, null, null), {
    rows, typing: Boolean(typed), input: TextareaState.new({ placeholder: "" }), fresh,
    known: KNOWN_AGENTS, branch: "main" }, fresh ? {} : started);
  if (fresh) Object.defineProperty(chat, "space", { value: { name: "lumen-api", folder: "/work/lumen-api" } });
  Object.defineProperty(chat, "agent", { value: { status: state } });         // a terminal's, as herdr says it
  for (const name of ["send", "tell", "reply", "showTerminal", "flip", "pickModel", "pickMode", "setEffort",
    "cycleMode", "act", "readSetup", "fit", "upload", "connect", "history", "listFiles", "readBudget", "readCosts",
    "closeBudget"]) chat[name] = () => {};
  chat.signingIn = () => signing;                         // the sign-ins running, by server
  Object.assign(chat, { files, listed, listError, connectFailed, toTell });   // attached, Add context's, a switch
  Object.assign(chat, { budget, costs });                  // a budget's notice, what the chat cost
  chat.terminalShown = () => shown;                       // Claude's terminal under the chat, or not
  chat.panelFocus = cx.focus_handle();                    // a real one: the panels track it
  Object.assign(chat, { litShown: lit, cursor, folded, setup, setupError }, first);  // lit, the keys' row, a narrow bar
  chat.switched = () => switches;                         // Ultracode on, or not
  chat.refused = refused;                                 // Ultracode refused by Claude: why
  if (asks) chat.waits = "terminal";                      // Claude asking in its own terminal, no card
  if (typed) chat.input.set_value(typed);
  chat.promptEvents();                                    // typed into, its / menu follows
  // the / menu open on MENU, what follows the "/" typed (its first row lit, unless the keys are on another), over the
  // prompt in the page's flow, on its specimen's stage
  if (menu !== null) Object.assign(chat, { open: "commands", typedMenu: true, query: menu, cursor: cursor ?? 0,
    inPlace: true });
  // Add context's list open on MENTION, what follows the "@" typed, as the / menu
  if (mention !== null) Object.assign(chat, { open: "mention", query: mention, cursor: cursor ?? 0, inPlace: true });
  if (waits) {
    chat.answer = new Answer(() => {}, cx);
    chat.answer.reset(waits[0], waits[1]);
  }
  return chat;
}

/** The made-up states the components show, made once (what is typed in them stays); CX makes the chat's cards.
 * @param {any} proto */
export function guide(proto, cx) {
  const at = (fields = {}) => made(proto, fields);
  // the budget's fields: what core keeps, and one typed that is no amount
  const budgetInput = InputState.new({ placeholder: "none", value: "50" });
  const oddInput = InputState.new({ placeholder: "none", value: "5o" });
  const found = { total: 3, files: 2, hits: HITS, error: null };
  const nothing = { total: 0, files: 0, hits: [], error: null };
  const setup = setupOf(home());                              // lumen-api's rules and skills
  const g = {
    /** @type {string | null} the part the page shows, picked in its index; null: its first */
    part: null,
    base: at(),
    heads: [["Files shown", { shown: "files" }], ["Changes shown, its count after its name", { shown: "changes" }],
      ["Search under the pointer", { shown: "files", hovered: "search" }],
      ["Chats' list in the view's place: no tab shown", { shown: "files", opened: true }],
      ["Agent shown, wearing its agent's icon", { shown: "agent" }],
      ["No agent known yet: Lucide's bot", { shown: "files", agent: null }],
      ["Agent's setup has a problem: a dot after its name, red over yellow", { shown: "changes",
        problems: PROBLEMS }],
      ["A server to sign in alone: yellow", { shown: "agent", problems: { tone: "warn", said: "1 sign in" } }],
      ["Not on GitHub: no Issues", { shown: "changes", views: ["files", "search", "changes", "agent"] }],
      ["A large count, short: 1.2k", { shown: "changes", count: 1234 }],
      ["A narrow card: the last tabs left out, never the shown one", { shown: "issues", px: 200 }]],
    // the tab bar's end: as it first shows, two chats waiting, Chats' list shown, the dock a rail
    ends: [["Chats, More, »", END], ["Two chats waiting: Chats' dot, its tip says how many", { ...END, waiting: 2 }],
      ["Chats' list shown in the dock: Chats lit", { ...END, listed: true }],
      ["The dock a rail: « opens it", { ...END, open: false }]],
    // Settings: General and About in its three states; then the states beside them (the keys' ring, a failed look,
    // a look under way)
    settings: [["General: agents open in a chat", "general", {}],
      ["About: up to date", "about", {}], ["About: a newer one out", "about", { latest: "0.5.0", newer: true }],
      ["Notifications: An agent waits on you, on; under it the app's own alerts", "notifications", {}],
      ["General: in a terminal, Tab on the choice (← → or Enter change it)", "general", {}, false, "opens", "terminal"],
      ["About: couldn't check", "about", { error: "GitHub did not answer" }], ["About: checking", "about", {}, true],
      ["About: Tab on the author's link", "about", {}, false, "author"]]
      .map(([name, section, more, checking, chosen, opens = "chat"]) => [name, Object.assign(new SettingsView(null, cx,
        { keys: false, section }), { found: { ...ABOUT_FOUND, ...more }, checking: Boolean(checking),
        chosen: chosen ?? null, opens, notes: true })]),
    repository: [["In sync", at({ status: { ...STATUS, ahead: 0, behind: 0 } })], ["Behind and ahead", at()],
      ["No upstream", at({ status: { ...STATUS, upstream: null } })],
      ["Folded", at({ folded: foldedSections(["repositories"]) })]],
    composer: [["Empty", at()], ["Filled", at({ message: MESSAGE })],
      ["Nothing to commit: not lit, the pull request's row the way on", at({ status: BRANCH })],
      ["Writing", at({ busy: "Claude is writing the message…", writing: "Claude is writing the message…" })],
      ["Asking", at({ message: MESSAGE, asked: [".env"] })],
      ["Commit & Push", at({ message: MESSAGE, mode: "push" })],
      ["Offering a push", at({ status: { ...STATUS, staged: [], changes: [] },
        offer: pushOffer({ ...STATUS, staged: [], changes: [] }) })],
      ["Fixes an issue", at({ message: MESSAGE, linked: [42, LISTED[0].title] })]],
    branchPull: [["No pull request: the way to open one", at({ status: BRANCH })],
      ["A draft, its checks running", at({ status: BRANCH, pull: { answer: { pull: PULLED[1], base: "main",
        error: null } } })],
      ["Changes asked for, a check failed", at({ status: BRANCH, pull: { answer: { pull: PULLED[2], base: "main",
        error: null } } })]],
    pullForm: [["Written by Claude, a draft", pullFormOf(), 330],
      ["Ready for review", pullFormOf({ draft: false }), 330],
      ["Writing", pullFormOf({ writing: "Claude is writing the pull request…", note: null }), 330],
      ["Not opened: gh's words", pullFormOf({ note: { text: "a pull request for branch \"fix/page-past-end\" into "
        + "branch \"main\" already exists", error: true } }), 330]],
    sections: [["Default", at()], ["Hover", at({ hovered: "section-changes" })],
      ["Asking", at({ confirm: "section-changes" })], ["Folded", at({ folded: foldedSections(["changes"]) })]],
    rows: [["Default", "changes", CHANGES[0], at()], ["Hover", "changes", CHANGES[0],
      at({ hovered: "changes:docs/api.md" })], ["Selected", "staged", STAGED[0],
      at({ open: "staged:src/lumen/routes/books.py" })], ["Untracked", "changes", CHANGES[1], at()],
    ["Conflict", "changes", CHANGES[2], at()], ["Deleted", "changes", CHANGES[3], at()],
    ["Asking", "changes", CHANGES[1], at({ confirm: "changes:src/lumen/pagination.py" })]],
    graph: [["Default", at()], ["Selected", at({ open: "commit:9e8d7c6" })],
      // no commits, as it shows them: a slide is kept by its element's id, and the open ones' list has the same
      ["Folded", at({ folded: foldedSections(["graph"]), commits: [] })]],
    empty: [["Loading", at({ status: null, loading: true })],
      ["Nothing to commit", at({ status: { ...STATUS, staged: [], changes: [] } })],
      ["Not a repository", at({ root: null, status: null, note: "Not a git repository" })]],
    query: [["Default", at({ view: "search", found, searched: SEARCHED })],
      ["Switches on, busy", at({ view: "search", searching: true,
        switches: { case: true, word: true, regex: false } })],
      ["No results", at({ view: "search", found: nothing, searched: SEARCHED })],
      ["Error", at({ view: "search", found: { ...nothing, error: "invalid regex: (" }, searched: SEARCHED })]],
    issueRows: [["Default", at(), LISTED[0]], ["Hover", at({ hovered: "issue-42" }), LISTED[0]],
      ["Selected", at({ issues: { chosen: 42 } }), LISTED[0]],
      ["Asking", at({ issues: { confirm: { number: 42, what: "close" } } }), LISTED[0]],
      ["Closed", at(), { ...LISTED[0], state: "CLOSED" }], ["No priority", at(), LISTED[4]]],
    // the head as it always is, what there is to say in the first row's place, a refresh's spinner in the button's
    issueList: [["Loading", at({ issues: { listing: null, asked: "styleguide" } }), 140],
    ["Refreshing", at({ issues: { asked: "styleguide" } }), 140], ["Busy", at({ issues: { busy: "Sending…" } }), 140],
    ["Closed, none", at({ issues: { listing: { issues: [], error: null },
      query: { state: "closed", assigned: false, authored: false, label: "" } } }), 140],
    ["Error", at({ issues: { listing: { issues: [], error: "gh is not signed in: run gh auth login" } } }), 140]],
    pullRows: [["Waiting on your review", at(), PULLED[0]], ["Your draft, its checks running", at(), PULLED[1]],
      ["Changes requested", at(), PULLED[2]], ["Approved", at(), PULLED[3]],
      ["Hover: to the agent, in the browser", at({ hovered: "pull-57" }), PULLED[0]],
      ["Selected", at({ pulls: { chosen: 57 } }), PULLED[0]]],
    pullList: [["Loading", at({ pulls: { listing: null, asked: "styleguide" } }), 140],
      ["Closed, none", at({ pulls: { listing: { pulls: [], error: null }, state: "closed" } }), 140],
      ["Error", at({ pulls: { listing: { pulls: [], error: "gh is not signed in: run gh auth login" } } }), 140]],
    reviews: [["Waiting on your review: a thread, a comment added, Request changes", previewOf({ review: reviewOf(
      REVIEWED, { summary: "Page the shelves as the books", event: "request", pending: [{ path: THREAD.path,
        line: 31, side: "RIGHT", body: "Name the 50: PAGE_SIZE is shared with /books." }] }) }), 420],
    ["Your own: no Approve, To agent on a comment, where it went", previewOf({ review: reviewOf(OWN,
      { sent: { t2: "Sent to Claude: #58 · books.py:31" } }) }), 300]],
    preview: [["Diff", previewOf({ rows: DIFF }), 200], ["Commit", previewOf({ rows: COMMIT }), 200],
      ["Loading", previewOf({ loading: true }), 52], ["Error", previewOf({ note: "HTTP 404: Not Found" }), 52],
      ["A PDF, scrolled to its second page", previewOf({ pdf: { sizes: Array(12).fill([612, 792]), count: 12,
        made: Array(12).fill(PAGE), range: null, making: false, page: 1, room: null } }), 320]],
    pageViews: [["Its code and picture side by side", "split", false, 280],
      ["Its code above its picture", "split", true, 400], ["Its code alone", "code", null, 280],
      ["Its picture alone", "picture", null, 280]]
      .map(([name, shown, stacked, h]) => [name, previewOf({ picture: { png: PAGE }, drawing: true, shown, stacked }),
        h]),
    issue: previewOf({ issue: ISSUE }),
    page: previewOf({ picture: { png: PAGE }, drawing: true, shown: "split", what: { n: 0, kind: "file",
      path: "docs/pagination.html", root: "/work/lumen-api", on: null } }),
    /** @type {[string, Editing, number, number][]} the editor's states, made once the page has started */
    editors: /** @type {[string, Editing, number, number][]} */ ([]),
    files: [["Default", filesOf()], ["A file chosen", filesOf({ picked: "src/lumen/app.py" })],
      ["A full folder", filesOf({ open: new Set(["src", "src/lumen", "src/lumen/routes"]) })],
      ["Hidden files shown", filesOf({ hidden: true, folders: HIDDEN_FOLDERS, open: new Set() })],
      ["No folder", filesOf({ root: null })]],
    fileEdits: [["A new file", filesOf({ naming: typing("new-file", "src/lumen", "client.py") })],
      ["Renamed in its row", filesOf({ naming: typing("rename", "src/lumen/store.py", "storage.py") })],
      ["A name taken", filesOf({ note: "already there: app.py" })],
      ["Move to Trash asked", filesOf({ asking: "src/lumen/pagination.py" })]],
    chats: [["Open in the dock: by space, a space with no chat left out; each chat's agent and age at its end",
      chatsOf()],
      ["The agents' icons known: the age alone at the end", chatsOf({ programs: Object.fromEntries(KNOWN_AGENTS
        .map((p) => [p.key, p])) })],
      ["Filtered", chatsOf({ typed: "fix" })],
      ["One renamed in its row", chatsOf({
        naming: { key: "claude:s4", item: TALKS[3], input: InputState.new({ placeholder: TALKS[3].title }) } })],
      ["The archived shown", chatsOf({ showArchived: true, opened: new Set(["harbor-web"]) })],
      ["Delete… asked about in its row", chatsOf({ asking: "claude:s3" })],
      ["Loading", chatsOf({ loaded: false, items: [] })],
      ["Empty", chatsOf({ items: [] })],
      ["Archived: said under the list, moving no row", chatsOf({ note: { text: 'Archived "Login redirect fix"',
        error: false } })],
      ["Not read", chatsOf({ loaded: false, items: [], failed: "chats.py: no such file" })]],
    floating: chatsOf(),
    problem: at({ note: "Sync stopped: pull first, nothing was lost" }),
    search: at({ view: "search", found, results: searchRows(HITS), searched: SEARCHED,
      peek: "src/lumen/routes/books.py:12", peekRows: PEEK }),
    changes: at({ message: MESSAGE, open: "staged:src/lumen/routes/books.py", hovered: "changes:docs/api.md" }),
    issues: at({ view: "issues", hovered: "issue-41", issues: { chosen: 42 } }),
    pulls: at({ view: "issues", board: "pulls", pulls: { chosen: 58 } }),
    plans: [["Folded: the step at work, how many are done", chatOf(cx, { state: "working", first: { plan: PLAN } })],
      ["Open: the done steps one row, the rest in order, what a step waits for, the approved plan's link",
        chatOf(cx, { state: "working", first: { plan: PLAN, planOpen: true } })],
      ["Its done steps listed", chatOf(cx, { state: "working", first: { plan: PLAN, planOpen: true,
        doneOpen: true } })],
      ["All done, until the next message", chatOf(cx, { first: { plan: PLAN_DONE } })],
      ["Narrow: the step's words cut, the count whole", chatOf(cx, { state: "working", first: { plan: PLAN } }), 320],
      ["Narrow and open: what a step waits for gives way first", chatOf(cx, { state: "working",
        first: { plan: PLAN, planOpen: true } }), 320]],
    planned: chatOf(cx, { rows: timeline(PLANNED), state: "working" }),
    prompts: [["Empty: Message and the agent's name", chatOf(cx)],
      ["Typed, the cursor in it", chatOf(cx, { typed: "Also cap the page size at 100" })],
      ["While Claude works: a message queued, esc stops it", chatOf(cx, { state: "working", context: 72 })],
      ["A usage limit near its end, the context nearly full", chatOf(cx, { context: 92,
        limits: { five_hour: { used: 86, resets: null } } })],
      ["A budget near its end (usage.html's Keret): Codex's month, its pace past it", chatOf(cx,
        { budget: BUDGET_NOTICE })],
      ["Both: the limit's, then the budget's, each closed by its ×", chatOf(cx, { context: 92,
        limits: { five_hour: { used: 86, resets: null } }, budget: BUDGET_NOTICE })],
      ["Claude's terminal shown under the chat: its button lit", chatOf(cx, { shown: true })],
      ["The model chip's panel open: the chip ringed in the accent", chatOf(cx, { lit: "model" })],
      ["The Modes panel open: the mode chip raised, ringed in the accent", chatOf(cx, { lit: "modes" })],
      ["/ typed: the / menu over the prompt, its button ringed in the accent", chatOf(cx, { lit: "commands",
        typed: "/", menu: "", setup, rows: USED })],
      ["The Context panel open: the meter raised, ringed in the accent", chatOf(cx, { lit: "context" })],
      ["A narrow chat: the context's words left out first, its tip says them", chatOf(cx, { effort: "xhigh",
        folded: 1 }), 480],
      ["Narrower: the chip's level left out too, its tip says it", chatOf(cx, { effort: "xhigh", folded: 2 }), 420]],
    // the / menu: this chat, the skills lumen-api has (the one used first), Claude's own commands
    commands: [["/ typed: this chat, a few skills (Lucide's scroll-text), Claude's commands, the first row lit",
      chatOf(cx, { setup, rows: USED, typed: "/", menu: "" })],
    ["/rev typed: what it finds, the best first, lit: Enter picks it",
      chatOf(cx, { setup, rows: USED, typed: "/rev", menu: "rev" })],
    ["The keys on a plugin's skill: Enter puts it in the prompt",
      chatOf(cx, { setup, rows: USED, typed: "/", menu: "", cursor: 3 })],
    ["The skills not read yet: this chat and Claude's commands",
      chatOf(cx, { rows: USED, typed: "/", menu: "" })]],
    // the Context panel: the use and its parts in the Agent panel's colors, what the chat cost, Compact
    contexts: [["lumen-api: the use, its rules, skills and connectors by color; Show all in Agent lists them",
      chatOf(cx, { setup: { ...setup, servers: SERVERS }, rows: USED })],
      ["What the chat cost (usage.html's Áttekintés): its whole, a row a model, Usage", chatOf(cx, { setup,
        rows: USED, costs: COSTS })],
      ["With an API key the whole is spent; a model with no price says so", chatOf(cx, { setup, rows: USED,
        costs: { ...COSTS, kind: "spent", subs: { review: { cost: null, text: "no price",
          model: { id: "codex-auto-review", name: "codex-auto-review", color: "#8b8b8b" } } } } })],
      ["The setup not read yet: the use as one part", chatOf(cx)]],
    // the model chip's panel: Claude's models
    models: [["Opus 5.5 in use, the keys on Sonnet", chatOf(cx, { cursor: 3 })],
      ["Before Claude runs: Default, Claude's own", chatOf(cx, { fresh: true })],
      ["A model Claude's list lacks: the one in use, on top", chatOf(cx, { model: ["claude-opus-4-8", "Opus 4.8"],
        effort: "medium" })]],
    // the mode chip's panel: Claude's modes, its effort, Ultracode
    modes: [["Manual in use at High", chatOf(cx)],
      ["Ultracode on, the keys on Effort: ← → step it", chatOf(cx, { switches: { ultracode: true }, cursor: 4 })],
      ["Ultracode refused: faint, Claude's reason its tip", chatOf(cx, {
        refused: { ultracode: "Ultracode needs dynamic workflows enabled (see /config)" } })],
      ["Before Claude runs: Plan and Extra high picked for its start", chatOf(cx, { fresh: true,
        first: { firstMode: "plan", firstEffort: "xhigh" } })]],
    // the + menu: connectors.html's six, the keys, a switch just turned, the read's states, an agent with no files
    plus: [["Open: Upload, Add context, the connectors on or off here; the keys on its first row", chatOf(cx, {
      setup: { ...setup, servers: SERVERS }, cursor: 0 })],
    ["The keys on Linear: Enter or Space turns it", chatOf(cx, { setup: { ...setup, servers: SERVERS }, cursor: 4 })],
    ["Notion turned on, Claude at work: shown as asked, told once idle", chatOf(cx, { setup: { ...setup,
      servers: SERVERS }, toTell: [{ name: "claude.ai Notion", on: true }] })],
    ["No problem, none off: no pill", chatOf(cx, { setup: { ...setup, servers: SERVERS.slice(2, 4) } })],
    ["The connectors being read", chatOf(cx)],
    ["Not read: why, in their place", chatOf(cx, { setupError: "agent_setup.py: Permission denied" })],
    ["None in this folder: Manage leads to adding one", chatOf(cx, { setup: { ...setup, servers: [] } })]],
    attached: [["Two files attached: chips over the prompt, × takes one off", chatOf(cx, {
      files: ["/work/lumen-api/docs/paging.md", "/home/dev/notes/paging spec.pdf"],
      typed: "Check books.py against these" })],
    ["The + menu open: the + raised, ringed in the accent", chatOf(cx, { lit: "plus" })],
    ["@ typed: Add context's list over the prompt", chatOf(cx, { typed: "Check @", mention: "",
      listed: FOLDER_FILES })]],
    mentions: [["Nothing typed after @: the changed files, then the folder's", chatOf(cx, { typed: "@", mention: "",
      listed: FOLDER_FILES })],
    ["Typed: what it finds, the best first, lit", chatOf(cx, { typed: "@boo", mention: "boo", listed: FOLDER_FILES })],
    ["The keys on the third row", chatOf(cx, { typed: "@", mention: "", listed: FOLDER_FILES, cursor: 2 })],
    ["The files being listed", chatOf(cx, { typed: "@", mention: "" })],
    ["Nothing matches", chatOf(cx, { typed: "@zzz", mention: "zzz", listed: FOLDER_FILES })],
    ["Not listed: why", chatOf(cx, { typed: "@", mention: "", listError: "search.py: Permission denied" })]],
    // connectors in the timeline: Google Drive's calls by its brand, a server unknown by its letter, Box's sign-in
    connected: [["Box needs a sign-in: Connect at its step's end", chatOf(cx, { rows: timeline(CONNECTED),
      setup: { ...setup, servers: SERVERS } })],
    ["Connect pressed: signing in", chatOf(cx, { rows: timeline(CONNECTED), setup: { ...setup, servers: SERVERS },
      signing: { "claude.ai Box": { address: "t9", at: 0 } } })],
    ["Signed in: the step done", chatOf(cx, { rows: timeline(CONNECTED), setup: { ...setup,
      servers: serversWith("claude.ai Box", "on") } })],
    ["The sign-in could not start: why, Connect again", chatOf(cx, { rows: timeline(CONNECTED), setup: { ...setup,
      servers: SERVERS }, connectFailed: { "claude.ai Box": "claude: command not found" } })],
    ["Box turned off since: a thing of the past", chatOf(cx, { rows: timeline(CONNECTED), setup: { ...setup,
      servers: serversWith("claude.ai Box", "off here") } })]],
    cards: [...WAITS.map(([name, waits]) => [name, chatOf(cx, { waits })]),
      ["Asking in its own terminal, shown under the chat", chatOf(cx, { asks: true, shown: true })],
      ["Asking in its own terminal, hidden by hand", chatOf(cx, { asks: true })]],
    chat: chatOf(cx, { rows: timeline(STEPS), state: "blocked", setup }),
    fresh: chatOf(cx, { fresh: true }),
    // the Agent panel: [name, view, height, width]
    agentPanels: [["Claude in lumen-api, as connectors.html's Áttekintés: its head line and problems, the bar, Usage, "
      + "Subagents, Permissions with its Hooks, sentry failed, figma to sign in, a permission hidden",
    agentOf(LAYERS, { usage: USAGE, report: REPORT, agents: ON_KEY, folded: [] }), 1000],
    ["git typed: the rows it finds, their sections open, the rest left out", agentOf(LAYERS, { query: "git" }), 420],
    ["Connectors alone open, as a new space's dock shows a problem", agentOf(LAYERS,
      { folded: OTHERS }), 420],
    ["A narrow panel: the tags left out, the states and the costs kept", agentOf(LAYERS,
      { folded: ["permissions", "skills", "subagents"], px: 280 }), 356, 280],
    ["Codex: its own rules, approval and sandbox, servers", agentOf(CODEX_LAYERS, {}, "codex"), 356],
    ["A file it could not read: why on the head's line, the file its tip", agentOf({ ...LAYERS,
      error: { text: "Couldn't read Claude's setup: permission denied", tip: "~/.claude/settings.json" } },
    { folded: SECTIONS }), 240],
    ["Nothing found", agentOf(LAYERS, { query: "terraform" }), 164],
    ["Loading", agentOf(null), 132], ["Not on this machine", agentOf(null, { missing: true }, "codex"), 132],
    ["The read failed: why, in the rows' place", agentOf(null, { error: "agent_setup.py: Permission denied" }), 132]],
    // the Agents tab: [name, view, height, width]
    agentsGraph: [["Wiring, as agent-graph.html's: Claude in lumen-api, code-reviewer chosen; an edge always, on "
      + "demand, waiting and failed, the gates on them, a connector off here", agentsOf(GRAPH, { chosen: SUB_NODE }),
    640, 1100],
    ["A failed connector chosen: its error", agentsOf(GRAPH, { chosen: SENTRY.id }), 640, 1100],
    ["A folded node chosen: its names a list", agentsOf(GRAPH, { chosen: MORE_SKILLS }), 640, 1100],
    ["This chat, as usage.html's Gráf: its whole in the head, what ran lit and numbered in its order, the rest at "
      + "half strength, the agents' costs and shares in their models' colors, the tools' calls; Claude chosen: its "
      + "cost lines, Open in Usage", agentsOf(ranOf(), { mode: "run", chosen: "agent" }), 720, 1100],
    ["A call running: its edge wider; a tool chosen: its calls", agentsOf(ranOf(true), { mode: "run",
      chosen: "tool:files" }), 720, 1100],
    ["Wiring of a graph with a chat read: the two switches, nothing lit", agentsOf(ranOf()), 640, 1100],
    ["Codex through the same shapes", agentsOf(GRAPH_CODEX, {}, "codex"), 360, 1100],
    ["Not read yet", agentsOf(null), 96, 540],
    ["The read failed: why, in the graph's place", agentsOf(null, { error: "graph.py: Permission denied" }), 96, 540],
    ["An agent that is not installed", agentsOf(null, { missing: true }, "codex"), 96, 540]],
    // the Agents tab's Usage: [name, view, height, width]
    agentsUsage: [["Usage, as usage.html's Riport: seven days, every agent; a row asked for (Open in Usage) marked",
      agentsOf(null, { view: "usage", usage: usageViewOf(REPORT, { marked: "a1b2c3d4-0003" }) }), 1250, 1100],
    ["The pointer on Nov 7: its tip", usagePart(usageViewOf(REPORT, { tip: 4 }), "daily", REPORT), 300, 1100],
    ["Thirty days: a column a day, every few named", usagePart(usageViewOf(REPORT_MONTH), "daily", REPORT_MONTH),
      300, 1100],
    ["Over its budget (usage.html's Keret): its pace's line past the budget's", agentsOf(null,
      { view: "usage", usage: usageViewOf(REPORT_OVER) }), 880, 1100],
    ["Budget… pressed: a field an agent on an API key", usagePart(usageViewOf(REPORT, { budget: { rows: [
      { key: "codex", name: "Codex", input: budgetInput }], error: null, busy: false } }), "budgetForm"), 170, 340],
    ["What is no amount: said under the fields", usagePart(usageViewOf(REPORT, { budget: { rows: [{ key: "codex",
      name: "Codex", input: oddInput }], error: "Codex's is not an amount", busy: false } }), "budgetForm"), 190,
    340],
    ["One agent, with no budget kept: its month's line and pace alone; a narrow tab stacks the two charts and "
      + "scrolls a table sideways", agentsOf(null, { view: "usage", usage: usageViewOf(REPORT_CODEX,
      { agent: "codex" }) }), 900, 620],
    ["No model with a price: the tokens alone, no chart, never $0.00", agentsOf(null, { view: "usage",
      usage: usageViewOf(REPORT_UNPRICED) }), 520, 1100],
    ["Nothing read yet: the chats being read", agentsOf(null, { view: "usage", usage: usageViewOf(REPORT_NONE,
      { indexing: { left: 9_000_000_000 } }) }), 150, 1100],
    ["Nothing used in this period", agentsOf(null, { view: "usage", usage: usageViewOf(REPORT_NONE) }), 150, 1100],
    ["Not read yet", agentsOf(null, { view: "usage" }), 96, 540],
    ["The read failed: why, in its place", agentsOf(null, { view: "usage", usage: usageViewOf(null,
      { error: "report.py: Permission denied" }) }), 96, 540]],
    // the chosen row's properties under the layers: [name, view, height]
    agentProperties: [["sentry failed, chosen: where it is from, what it runs, its error, Retry and its file",
      agentOf(LAYERS, { chosen: SENTRY.id, folded: OTHERS }), 552],
    ["Retry pressed: Claude checking it, the state a spinner", agentOf(LAYERS, { chosen: SENTRY.id, folded: OTHERS,
      checking: new Set(["sentry"]) }), 552],
    ["A rule: its paths, its first lines", agentOf(LAYERS, { chosen: API_RULE.id,
      folded: ["permissions", "skills", "connectors", "subagents"] }), 540],
    ["A skill the chat used: its description", agentOf(LAYERS, { chosen: API_SKILL.id,
      folded: ["rules", "permissions", "connectors", "subagents"] }), 540],
    ["A subagent: its tools, how often it ran", agentOf(LAYERS, { chosen: REVIEWER.id,
      folded: ["rules", "permissions", "skills", "connectors"] }), 420],
    ["The built-in subagents, one row: each with its model and tools", agentOf(LAYERS, { chosen: BUILT_INS.id,
      folded: ["rules", "permissions", "skills", "connectors"] }), 460],
    ["A conflict: both rules, each with where it is, and both files", agentOf(LAYERS, { chosen: CONFLICT.id,
      folded: ["rules", "skills", "connectors", "subagents"] }), 640],
    ["A hook: its event, where it is set, what it runs", agentOf(LAYERS, { chosen: GUARD.id,
      folded: ["rules", "skills", "connectors", "subagents"] }), 640],
    ["A check that could not run: why, over the buttons", agentOf(LAYERS, { chosen: SENTRY.id, folded: OTHERS,
      failed: "Couldn't check sentry: no Python on this machine" }), 576]],
    // Usage, the panel's first section (usage-agents.html): [name, what draws it, height, width]
    agentUsage: [["Claude in use, its 5 hours yellow: its reset under it; Codex on an API key, its month of its "
      + "budget in green", agentOf(LAYERS, { usage: USAGE, report: REPORT, agents: ON_KEY }).limits, 116],
    ["All green: no line under any row", agentOf(LAYERS, { usage: usageOf(meter("claude", "Claude", "Max",
      [32, "ok"], [16, "ok"])), report: REPORT, agents: ON_KEY }).limits, 96],
    ["Codex heading over its budget: its month yellow, the pace under it", agentOf(LAYERS, { usage: usageOf(
      meter("claude", "Claude", "Max", [32, "ok"], [16, "ok"])), report: REPORT_OVER, agents: ON_KEY }).limits, 116],
    ["Just reset: 0% while nothing ran since, – once something ran and no reading came since", agentOf(LAYERS, {
      usage: usageOf(meter("claude", "Claude", "Max", [0, "ok"], [16, "ok"]), meter("codex", "Codex", "Business",
        [null, "ok"], [41, "ok"])) }).limits, 96],
    ["A row pressed: its properties under the layers, the plan, both resets, the reading's age, Open Usage",
      agentOf(LAYERS, { usage: USAGE, report: REPORT, agents: ON_KEY, chosen: "usage:claude", folded: SECTIONS })
        .draw, 420],
    ["Codex on a plan in use: first, its plan's word", agentOf(LAYERS, { usage: usageOf(meter("codex", "Codex",
      "Business", [12, "ok"], [41, "ok"], { current: true }), meter("claude", "Claude", "Max", [32, "ok"],
      [16, "ok"], { current: false })) }, "codex").limits, 96],
    ["A narrow panel: the bars left out, the percents kept", agentOf(LAYERS, { usage: USAGE, report: REPORT,
      agents: ON_KEY, px: 280 }).limits, 116, 280],
    ["No agent with limits", agentOf(LAYERS, { usage: usageOf() }).limits, 64],
    ["Codex shown, no reading of its limits: said in its row's place", agentOf(LAYERS, { usage: usageOf(
      meter("codex", "Codex", "Plus", null, null, { current: true, age: null, untold: UNTOLD }), meter("claude",
        "Claude", "Max", [32, "ok"], [16, "ok"], { current: false })) }, "codex").limits, 96],
    ["Its row pressed: why, in its properties", agentOf(LAYERS, { usage: usageOf(meter("codex", "Codex", "Plus",
      null, null, { current: true, age: null, untold: UNTOLD })), chosen: "usage:codex", folded: SECTIONS },
    "codex").draw, 380],
    ["Folded: the agent in use's tighter limit, its mark, at the head's end", agentOf(LAYERS, { usage: USAGE,
      folded: ["usage"] }).limits, 40],
    ["Folded, another agent worse: Codex near its budget, its figure and mark in Claude's place", agentOf(LAYERS, {
      usage: usageOf(meter("claude", "Claude", "Max", [32, "ok"], [16, "ok"])), report: REPORT_OVER, agents: ON_KEY,
      folded: ["usage"] }).limits, 40],
    ["Folded at the limit: red", agentOf(LAYERS, { usage: usageOf(meter("claude", "Claude", "Max", [100, "bad"],
      [64, "warn"])), folded: ["usage"] }).limits, 40],
    ["The read failed: why, in the rows' place", agentOf(LAYERS, { usageError: "usage.py: Permission denied" })
      .limits, 64]],
    // Connectors as connectors.html's Agent panel, Belépés, Hozzáadás and Bekapcsolva: [name, what draws it, height]
    agentConnectors: [["Box to sign in, chosen: its switch for this folder, Connect on the accent; each known "
      + "service by its logo (one of no known brand by its letter: the Agent panel's github)",
    agentOf(connectorsOf(BOX_IN), { chosen: BOX_IN.id, folded: OTHERS, edit: editOf(planOf([switchOf(true)]),
      { touched: false }) }).draw, 520],
    ["Connect pressed: signing in, its spinner; Open the page again, Cancel", agentOf(connectorsOf(BOX_IN),
      { chosen: BOX_IN.id, folded: OTHERS, signingIn: [BOX] }).draw, 476],
    ["Signed in and used: its switch on, Sign out raised", agentOf(connectorsOf(BOX_ON), { chosen: BOX_ON.id,
      folded: OTHERS, edit: editOf(planOf([switchOf(true)]), { touched: false }) }).draw, 540],
    ["Notion, off here: its switch off", agentOf(connectorsOf(BOX_ON), { chosen: NOTION.id, folded: OTHERS,
      edit: editOf(planOf([switchOf(true)]), { touched: false }) }).draw, 500],
    ["Off by Claude's own state, no Claude running in lumen-api: what turning it on waits for",
      agentOf(connectorsOf(BOX_ON), { chosen: NOTION.id, folded: OTHERS, edit: editOf(planOf([switchOf(true)]),
        { touched: false, note: CONNECT.needs["turn-on"] }) }).draw, 520],
    ["Claude running its command on a server: the state a spinner, the buttons faint", agentOf(connectorsOf(BOX_ON),
      { chosen: BOX_ON.id, folded: OTHERS, checking: new Set([BOX]) }).draw, 520],
    ["A command that failed: why, in the agent's own words, over the buttons", agentOf(connectorsOf(BOX_IN),
      { chosen: BOX_IN.id, folded: OTHERS,
        failed: "Couldn't start claude.ai Box's sign-in: claude is not on this machine's PATH" }).draw, 548],
    ["+ pressed: From claude.ai… opens its page, By URL… the form", agentOf(connectorsOf(BOX_IN),
      { addMenu: true }).ways, 116],
    ["By URL…: the form in the properties' place, the keys in URL", agentOf(connectorsOf(BOX_IN), { folded: OTHERS,
      form: formOf("dropbox", "https://mcp.dropbox.com/mcp") }).draw, 580],
    ["For: All projects", agentOf(connectorsOf(BOX_IN), { folded: OTHERS, form: formOf("dropbox",
      "https://mcp.dropbox.com/mcp", { scope: "user", focus: null }) }).draw, 580],
    ["Empty, the keys in Name", agentOf(connectorsOf(BOX_IN), { folded: OTHERS, form: formOf("", "",
      { focus: "name" }) }).draw, 580],
    ["A name refused: its field in red, why under the fields", agentOf(connectorsOf(BOX_IN), { folded: OTHERS,
      form: formOf("my dropbox", "https://mcp.dropbox.com/mcp", { focus: "name", error: { field: "name",
        error: "Letters, digits, - and _ only" } }) }).draw, 600],
    ["The agent refused it: its own words", agentOf(connectorsOf(BOX_IN), { folded: OTHERS,
      form: formOf("sentry", "https://mcp.sentry.dev/mcp", { focus: null, error: { field: null,
        error: "MCP server sentry already exists in local config" } }) }).draw, 600],
    ["Adding: the agent's own command runs", agentOf(connectorsOf(BOX_IN), { folded: OTHERS,
      form: formOf("dropbox", "https://mcp.dropbox.com/mcp", { focus: null, busy: true }) }).draw, 580],
    ["Codex: its own sign-out and its file, never Turn off; + opens the form, with no For", agentOf(CODEX_LAYERS,
      { chosen: "connector:linear", folded: ["rules", "permissions"] }, "codex").draw, 356],
    ["Codex gave no list of its servers: one dim row, not read, no count, why in its properties",
      agentOf(CODEX_UNLISTED, { chosen: UNLISTED.id, folded: ["rules", "permissions"] }, "codex").draw, 280],
    ["Codex's form: Name and URL alone", agentOf(CODEX_LAYERS, { folded: ["rules", "permissions"],
      form: formOf("figma", "https://mcp.figma.com/mcp") }, "codex").draw, 384]],
    // a row's form in its properties, as harness-editing.html's app frames: [name, what draws it, height, width]
    agentEditing: [["Mode chosen: its choices at once, the two that work only in Global faint, why under them",
      agentOf(RULED, { chosen: "mode", folded: NOT_PERMS, edit: editOf(planOf([MODE_IN],
        { layers: savedIn("Project") }), { touched: false }) }).draw, 560],
    ["A choice touched: the layers, the file, what a save writes and when it applies; a stronger layer in yellow; "
      + "Cancel and Save", agentOf(RULED, { chosen: "mode", folded: NOT_PERMS, edit: editOf(planOf(
      [{ ...MODE_IN, value: "plan" }], { layers: savedIn("Project"), submit: "Save", when: "From the next session",
        changes: [changed(FILES.Project, ["-", '"defaultMode": "acceptEdits"'], ["+", '"defaultMode": "plan"'])],
        warns: ['Local sets "acceptEdits": it wins in this folder'] })) }).draw, 700],
    ["At the dock's narrowest: the choices and the file wrap", agentOf(RULED, { chosen: "mode", folded: NOT_PERMS,
      px: 300, edit: editOf(planOf([{ ...MODE_IN, value: "plan" }], { layers: savedIn("Project"), submit: "Save",
        when: "From the next session", changes: [changed(FILES.Project, ["+", '"defaultMode": "plan"'])] })) }).draw,
    700, 300],
    ["No file sets it: Default, from Claude's default, no file to open", agentOf(UNSET, { chosen: "mode",
      folded: NOT_PERMS, edit: editOf(planOf([{ ...MODE_IN, value: null }], { layers: savedIn("Project") }),
        { touched: false }) }).draw, 440],
    ["Permissions' + pressed: a new rule, a rule that hides it in yellow", agentOf(RULED, { chosen: "rule",
      folded: NOT_PERMS, edit: editOf(planOf(ruleOf("allow"), { layers: savedIn("Project"), submit: "Add",
        when: "Applies now", changes: [changed(FILES.Project, ["+", 'allow "Bash(npm run test:*)"'])],
        warns: ["deny Bash(npm *) in Global hides it: this rule would never apply"] }), { focus: "rule" },
      { rule: "Bash(npm run test:*)" }) }).draw, 640],
    ["A rule chosen: its text, behavior and layer, Remove quiet beside its file", agentOf(RULED, { chosen: PYTEST.id,
      folded: NOT_PERMS, edit: editOf(planOf(ruleOf("allow"), { layers: savedIn("Project"), remove: "Remove" }),
        { touched: false }, { rule: "Bash(pytest:*)" }) }).draw, 620],
    ["Its text changed and moved to Local: both files' lines", agentOf(RULED, { chosen: PYTEST.id, folded: NOT_PERMS,
      edit: editOf(planOf(ruleOf("allow"), { layers: savedIn("Local"), remove: "Remove", submit: "Save",
        when: "Applies now", changes: [changed(FILES.Project, ["-", 'allow "Bash(pytest:*)"']),
          changed(FILES.Local, ["+", 'allow "Bash(python -m pytest:*)"'])] }), {},
      { rule: "Bash(python -m pytest:*)" }) }).draw, 700],
    ["Remove asks once: the line that goes, who else gets it", agentOf(RULED, { chosen: CURL.id, folded: NOT_PERMS,
      edit: editOf(planOf(ruleOf("ask"), { layers: savedIn("Project"), ask: "Remove from Project?",
        submit: "Remove", remove: "Remove", when: "Applies now", done: "Removed Bash(curl:*) from Project",
        changes: [changed(FILES.Project, ["-", 'ask "Bash(curl:*)"'])],
        warns: ["In git: your team gets it with your next commit"] })) }).draw, 620],
    ["Removed: the foot says so, Undo at its end", agentOf(layersWith("permissions", (one) => ({ rows:
      one.rows.filter((/** @type {any} */ row) => row.id !== CURL.id) }), RULED), { folded: NOT_PERMS,
      foot: { text: "Removed Bash(curl:*) from Project", code: false, undo: [], word: "Undo", error: null,
        busy: false } }).draw, 420],
    ["A conflict: its two ways, the chosen one's line with its file", agentOf(RULED, { chosen: CONFLICT.id,
      folded: NOT_PERMS, edit: editOf(planOf([wayOf("remove")], { submit: "Save", when: "Applies now",
        changes: [changed(FILES.Project, ["-", 'deny "Bash(git push:*)"'])] })) }).draw, 700],
    ["Narrow the deny: the rule typed, one that still hides it refused in red", agentOf(RULED, {
      chosen: CONFLICT.id, folded: NOT_PERMS, edit: editOf(planOf([wayOf("narrow"), textOf("to", "Rule")],
        { error: "Still hides allow Bash(git push:*)" }), { focus: "to", submit: "Save" },
      { to: "Bash(git push*)" }) }).draw, 700],
    ["The organization's rule: why it cannot be changed, alone", agentOf(RULED, { chosen: ENV.id, folded: NOT_PERMS,
      edit: editOf(planOf(ruleOf("deny"), { error: "Set by your organization" }), { touched: false }) }).draw, 520],
    ["The sandbox: its switch, each layer's hosts with ×, a new one typed, More options its file", agentOf(RULED, {
      chosen: "sandbox", folded: NOT_PERMS, edit: editOf(planOf([switchOf(true, "Bash sandbox"), textOf("add",
        "Hosts", [{ host: "pypi.org", layer: "Project", rule: null }, { host: "github.com", layer: "Global",
          rule: null }, { host: "docs.lumen.dev", layer: "Global", rule: "WebFetch(domain:docs.lumen.dev)" }])],
      { layers: savedIn("Project"), submit: "Save", when: "Applies now · adds to Global's hosts",
        changes: [changed(FILES.Project, ["+", 'allowedDomains "files.pythonhosted.org"'])],
        more: { label: "More options", path: `${LUMEN}/.claude/settings.json` } }), { focus: "add" },
      { add: "files.pythonhosted.org" }) }).draw, 700],
    ["The head's model and effort pressed: both choices, the environment's word over every file", agentOf(RULED, {
      chosen: "model", folded: SECTIONS, edit: editOf(planOf([choiceOf("model", "Model", "sonnet", [["opus", "Opus"],
        ["sonnet", "Sonnet"], ["haiku", "Haiku"]]), choiceOf("effort", "Effort", "high", EFFORTS)],
      { layers: savedIn("Project"), submit: "Save", when: "From the next session",
        changes: [changed(FILES.Project, ["-", '"model": "opus"'], ["+", '"model": "sonnet"'],
          ["+", '"effortLevel": "high"'])], warns: ["ANTHROPIC_MODEL is set: it wins over every file"] })) }).draw,
    520],
    ["Saved: the head says it, the foot the line written, Undo", agentOf({ ...RULED, head: { ...RULED.head,
      model: "Sonnet", line: "Sonnet · High · starts at 34.2k of 1M" } }, { folded: SECTIONS,
      foot: { text: '− "model": "opus"', code: true, undo: [], word: "Undo", error: null, busy: false } }).draw,
    260],
    ["The file changed since: the way back refused, core's words in the foot", agentOf(RULED, { folded: SECTIONS,
      foot: { text: "", code: true, undo: [], word: "Undo", busy: false,
        error: ".claude/settings.json changed since: nothing saved" } }).draw, 260],
    ["A skill turned off for the folder: the layers it can be off in", agentOf(SKILLED, { chosen: API_SKILL.id,
      folded: ["rules", "permissions", "connectors", "subagents"], edit: editOf(planOf([switchOf(false)],
        { ...LOCAL_SKILL, changes: [changed(FILES.Local, ["+", '"skillOverrides": {"api-routes": "off"}'])] })) })
      .draw, 560],
    ["Off here: its row dim, its switch off; back on takes it out of the file that has it", agentOf(SKILLED, {
      chosen: CHANGELOG_OFF.id, folded: ["rules", "permissions", "connectors", "subagents"],
      edit: editOf(planOf([switchOf(true)], { submit: "Save", when: "From the next session",
        changes: [changed(FILES.Project, ["-", '"skillOverrides": {"changelog": "off"}'])] })) }).draw, 560],
    ["A plugin's skill: why it has no switch", agentOf(LAYERS, { chosen: LAYERS.sections[2].rows[2].id,
      folded: ["rules", "permissions", "connectors", "subagents"], edit: editOf(planOf([switchOf(true)],
        { error: "Turns off with its plugin" }), { touched: false }) }).draw, 480],
    ["A built-in subagent picked in its list: its switch under it; Plan off here", agentOf(BUILT_OFF, {
      chosen: BUILT_INS.id, folded: ["rules", "permissions", "skills", "connectors"],
      edit: editOf(planOf([switchOf(true)], { layers: savedIn("Local", ["Project", "Local"]) }),
        { touched: false, name: "Explore" }) }).draw, 520],
    ["Hooks' head pressed: all hooks off in the folder, what else stops", agentOf(layersWith("permissions",
      (one) => ({ rows: one.rows.slice(0, 2) })), { chosen: "hooks", folded: NOT_PERMS,
      edit: editOf(planOf([switchOf(false, "All hooks in lumen-api")], { layers: savedIn("Local"), submit: "Save",
        when: "Applies now", changes: [changed(FILES.Local, ["+", '"disableAllHooks": true'])],
        warns: ["Also stops herdr-fold's own hook: decisions go back to Claude's terminal"] })) }).draw, 660],
    ["Hooks off here: the head says so, its rows dim; the switch is the way back", agentOf(HOOKS_OFF, {
      chosen: "hooks", folded: NOT_PERMS, edit: editOf(planOf([switchOf(false, "All hooks in lumen-api")],
        { layers: savedIn("Local") }), { touched: false }) }).draw, 520],
    ["A connector turned off for the folder: what new chats then start at", agentOf(SERVED, { chosen: GITHUB,
      folded: OTHERS, edit: editOf(planOf([switchOf(false)], { ...LOCAL_SKILL,
        when: "From the next session · new chats start at ~27.4k",
        changes: [changed(FILES.Local, ["+", 'deniedMcpServers {"serverName": "github"}'])] })) }).draw, 520],
    ["A project's server nobody answered for: approved or kept off, asked both ways", agentOf(SERVED, {
      chosen: PENDING.id, folded: OTHERS, edit: editOf(planOf([switchOf(false, "On in lumen-api",
        { on: "Approve in lumen-api", off: "Keep off" })], { layers: savedIn("Local", ["Project", "Local"]) }),
      { touched: false }) }).draw, 440],
    ["Codex's sandbox: Full access warned of before it is saved", agentOf(CODEX_LAYERS, { chosen: "sandbox",
      folded: ["rules", "connectors"], edit: editOf(planOf([choiceOf("value", "Sandbox", "danger-full-access",
        [["read-only", "Read only"], ["workspace-write", "Workspace write"], ["danger-full-access", "Full access"]])],
      { layers: savedIn("Global", ["Global", "Project"], { Global: "~/.codex/config.toml",
        Project: ".codex/config.toml" }), submit: "Save", when: "From the next session",
      changes: [changed("~/.codex/config.toml", ["-", 'sandbox_mode = "workspace-write"'],
        ["+", 'sandbox_mode = "danger-full-access"'])],
      warns: ["No sandbox: commands can change any file on this Mac and reach the network"] })) }, "codex").draw,
    520],
    ["Codex's approval: Granular grey, set in the file", agentOf(CODEX_LAYERS, { chosen: "approval",
      folded: ["rules", "connectors"], edit: editOf(planOf([choiceOf("value", "Approval", "on-request",
        [["on-request", "Ask on request"], ["never", "Never ask"], ["granular", "Granular",
          "Granular is set in the file"]])]), { touched: false }) }, "codex").draw, 360]],
    // the agents' list and where an agent stands in its setup's place: [name, what draws it, height]
    agentLists: [["The head's chip pressed: the installed agents, Claude shown, Gemini CLI to sign in; then the one "
      + "not installed, dim", agentOf(LAYERS, { listing: true, agents: KNOWN_MACHINE }).listed, 276],
    ["The keys on Codex", agentOf(LAYERS, { listing: true, agents: KNOWN_MACHINE, cursor: 1 }).listed, 276],
    ["One not installed looked at: the check its own", agentOf(LAYERS, { listing: true, agents: KNOWN_MACHINE,
      looking: "aider" }).listed, 276],
    ["Every agent installed: one group", agentOf(LAYERS, { listing: true, agents: MACHINE }).listed, 204],
    ["A narrow panel, 200: a long name cut, its word kept", agentOf(LAYERS, { listing: true, agents: KNOWN_MACHINE,
      px: 200 }).listed, 276, 200],
    ["Before the agents are told", agentOf(LAYERS, { listing: true }).listed, 124]],
    agentStates: [["Gemini CLI, not signed in: Sign in runs its own login in a terminal tab", agentOf(null,
      { agents: MACHINE }, "gemini").draw, 356],
    ["Codex, not installed: its vendor's line to copy, its page", agentOf(null, { agents: [MACHINE[0],
      machine("codex", "Codex", { installed: false, empty: NOT_HERE })] }, "codex").draw, 356],
    ["The line copied", agentOf(null, { copied: true, agents: [MACHINE[0],
      machine("codex", "Codex", { installed: false, empty: NOT_HERE })] }, "codex").draw, 356]],
    palettes: PALETTES.map(([name, typed, high]) => [name, new Palette(null, { typed: String(typed) }), high]),
    agents: { items: Object.assign(chatOf(cx, { fresh: true }), { machine: KNOWN_MACHINE })
      .agentList(["claude", "codex"]),
      find: { input: InputState.new({ placeholder: "Search agents" }), typed: "", none: "No agent matches" } },
  };
  cx.timer.after(0, (cx) => {                     // the editors after the page's start, which has its time limit
    g.editors = editorStates();
    for (const preview of [g.page, ...g.pageViews.map(([, one]) => one)]) {
      preview.editing = editingOf("docs/pagination.html", HTML);
    }
    cx.notify();
  });
  return g;
}

/** Show in Agent as core gives it to a node of KIND the Agent panel has a row of (graph.py's show()), by its ID; the
 * agent's own leads to its panel. @param {string} kind @param {string} id */
const showsOf = (kind, id) => (["rule", "skill", "sub", "connector", "agent"].includes(kind)
  ? [{ id: "agent", label: "Show in Agent", row: kind === "agent" ? null : id }] : []);

/** A graph's node as core words it (graph.py's). @param {string} id @param {string} column @param {string} kind
 * @param {string} title @param {string | null} sub @param {Record<string, any>} [over] */
const graphNode = (id, column, kind, title, sub, over = {}) => ({ id, column, kind, title, sub, brand: null, tag: null,
  icon: { rule: "file", skill: "skill", skills: "skill", sub: "bot", subs: "bot", connector: "plug" }[kind] ?? "file",
  state: null, dim: false, chips: [], parent: null, run: null, ...over, properties: { title, state: null, lines: [],
    text: null, error: null, ...(over.properties ?? {}), actions: [...(over.properties?.actions ?? []),
      ...showsOf(kind, id)] } });
const WORDS = { columns: { in: "In", agents: "Agents", uses: "Uses" }, views: { wiring: "Wiring", run: "This chat" },
  legend: [["always", "always"], ["demand", "on demand"], ["ran", "ran here"], ["failed", "failed"],
    ["waiting", "sign in"]] };
const SUB_NODE = "agent:pr-review-toolkit:code-reviewer", MORE_SKILLS = "skills:more";
// the graph as core words it (graph.py's): agent-graph.html's Wiring of Claude in lumen-api, a chat of herdr-fold's
const GRAPH = { agent: "claude", name: "Claude", folder: LUMEN, words: WORDS, cost: null, nodes: [
  graphNode("rule:/home/dev/.claude/CLAUDE.md", "in", "rule", "~/.claude/CLAUDE.md", "always · 2.4k",
    { tag: "Global", properties: { lines: [["From", "~/.claude/CLAUDE.md", "Global"]] } }),
  graphNode(`rule:${LUMEN}/CLAUDE.md`, "in", "rule", "CLAUDE.md", "always · 1.8k", { tag: "Project" }),
  graphNode(`rule:${LUMEN}/.claude/rules/api.md`, "in", "rule", "api.md", "when src/lumen/** is read",
    { tag: "Project" }),
  graphNode(`skill:${LUMEN}/.claude/skills/routes/SKILL.md`, "in", "skill", "api-routes",
    "How lumen-api's routes are written and tested", { tag: "Project" }),
  graphNode(MORE_SKILLS, "in", "skills", "15 more skills", "listed always · 3.7k", { properties: { lines: [
    ["commit", "Global", null], ["release-notes", "Global", null], ["review-pr", "pr-review-toolkit", null],
    ["frontend-design", "frontend-design", null], ["figma-use", "figma", null], ["", "10 more", null]] } }),
  graphNode("agent", "agents", "agent", "Claude", "Opus 5.5 · High · Manual", { icon: "claude",
    chips: ["PermissionRequest → herdr-fold"], properties: {
      lines: [["Model", "Opus 5.5", null], ["Effort", "High", null], ["Mode", "Manual", null],
        ["Hook", "PermissionRequest", "herdr-fold"]] } }),
  graphNode(SUB_NODE, "agents", "sub", "code-reviewer", "Opus · 3 tools", { parent: "agent",
    tag: "pr-review-toolkit", properties: { state: null, lines: [
      ["From", "pr-review-toolkit", "Plugin"], ["Model", "opus", null], ["Tools", "Read, Grep, github", null]],
    actions: [{ id: "open", label: "Open code-reviewer.md", path: "/home/dev/agents/code-reviewer.md", server: null,
      primary: true }] } }),
  graphNode("tool:files", "uses", "tool", "Read · Edit · Write", null),
  graphNode("tool:Bash", "uses", "tool", "Bash", "sandboxed, 2 hosts", { icon: "terminal" }),
  graphNode("connector:github", "uses", "connector", "github", "32 tools · 6.8k", { tag: "Global" }),
  graphNode("connector:figma", "uses", "connector", "Figma", "sign in", { state: "warn", brand: "figma",
    tag: "figma" }),
  graphNode(SENTRY.id, "uses", "connector", "sentry", "failed · npx not found", { state: "bad", brand: "sentry",
    tag: "Project", properties: { state: { text: "failed", tone: "bad" }, lines: [["From", ".mcp.json",
      "Project"], ["Runs", "npx -y @sentry/mcp-server", null]], error: "spawn npx ENOENT: npx is not on this "
      + "machine's PATH", actions: [{ id: "open", label: "Open .mcp.json", path: `${LUMEN}/.mcp.json`, server: null,
      primary: true }] } }),
  graphNode("connector:claude.ai Notion", "uses", "connector", "Notion", "off here", { dim: true, brand: "notion",
    tag: "claude.ai" })],
edges: [[`rule:/home/dev/.claude/CLAUDE.md`, "agent", "always"], [`rule:${LUMEN}/CLAUDE.md`, "agent", "always"],
  [`rule:${LUMEN}/.claude/rules/api.md`, "agent", "demand"],
  [`skill:${LUMEN}/.claude/skills/routes/SKILL.md`, "agent", "demand"], [MORE_SKILLS, "agent", "demand"],
  ["agent", SUB_NODE, "demand"], ["agent", "tool:files", "always", ["ask", "hook"]],
  ["agent", "tool:Bash", "always", ["allow pytest, git status +1", "deny rm -rf"]],
  ["agent", "connector:github", "always", ["allow"]], ["agent", "connector:figma", "waiting"],
  ["agent", SENTRY.id, "failed"], [SUB_NODE, "connector:github", "always"]].map(([from, to, style, gates = []]) =>
  ({ from, to, style, run: null, gates: /** @type {string[]} */ (gates).map((text) => ({ text,
    tone: text.split(" ")[0] })) })) };
// Codex through the same shapes: its rules, its shell with its prefix rules, its servers; nothing of Claude's
const GRAPH_CODEX = { agent: "codex", name: "Codex", folder: LUMEN, words: WORDS, cost: null, nodes: [
  graphNode("rule:/home/dev/.codex/AGENTS.md", "in", "rule", "~/.codex/AGENTS.md", "always · 400",
    { tag: "Global" }),
  graphNode(`rule:${LUMEN}/AGENTS.md`, "in", "rule", "AGENTS.md", "always · 1.1k", { tag: "Project" }),
  graphNode("agent", "agents", "agent", "Codex", null, { icon: "codex" }),
  graphNode("tool:shell", "uses", "tool", "Shell", "Workspace write", { icon: "terminal" }),
  graphNode("connector:linear", "uses", "connector", "Linear", "sign in", { state: "warn", brand: "linear",
    tag: "Global" })],
edges: [["rule:/home/dev/.codex/AGENTS.md", "agent", "always", []], [`rule:${LUMEN}/AGENTS.md`, "agent", "always",
  []], ["agent", "tool:shell", "always", [{ text: "ask", tone: "ask" }, { text: "allow git status", tone: "allow" }]],
["agent", "connector:linear", "waiting", []]].map(([from, to, style, gates]) => ({ from, to, style, gates,
  run: null })) };

// Usage as core's report tells it (report.py): usage.html's Riport, seven days of Claude on Max and Codex on a key
const MODEL = { opus: ["claude-opus-5-5", "Opus 5.5", "#3987e5"], sonnet: ["claude-sonnet-5-5", "Sonnet 5.5",
  "#d95926"], haiku: ["claude-haiku-5-5", "Haiku 5.5", "#199e70"], codex: ["gpt-5-codex", "GPT-5 Codex", "#c98500"] };
const MODELS_IN = /** @type {(keyof typeof MODEL)[]} */ (["opus", "sonnet", "haiku", "codex"]);
const SPENT = [[14.2, 2.1, 0.9, 1.1], [22.8, 3.4, 1.6, 0], [9.1, 1.2, 0.4, 2.4], [18.4, 4.0, 1.3, 0.8],
  [25.6, 2.8, 2.0, 3.1], [6.3, 0.6, 0.3, 0], [11.8, 1.5, 0.6, 1.2]];
/** DAYS of November from FIRST on, each with its models' costs. @param {number[][]} days @param {number} first */
const dailyOf = (days, first) => days.map((costs, n) => ({ day: `2026-11-${String(first + n).padStart(2, "0")}`,
  label: `Nov ${first + n}`, total: costs.reduce((sum, cost) => sum + cost, 0),
  models: MODELS_IN.flatMap((key, m) => (costs[m] > 0 ? [{ model: MODEL[key][0], name: MODEL[key][1],
    color: MODEL[key][2], cost: costs[m] }] : [])) }));
const LEGEND = MODELS_IN.map((key, m) => ({ model: MODEL[key][0], name: MODEL[key][1], color: MODEL[key][2],
  cost: SPENT.reduce((sum, day) => sum + day[m], 0), share: [78, 11, 5, 6][m] }));
/** Codex's November as core words it (report.py's month_of()): TODAY spent by the 9th, on PACE; red once spent,
 * yellow on pace past its budget, the pace's line only then. @param {number} today @param {number} pace
 * @param {number | null} [budget] */
const monthOf = (today, pace, budget = 50) => {
  const over = Boolean(budget) && Math.max(today, pace) > Number(budget);
  const said = `on pace for ${whole(pace, true)}`;
  return { agent: "codex", name: "Codex", key: "Codex · API key", id: "2026-11", label: "November", budget, days: 30,
    day: 9, today, pace, over, end: "Nov 30", color: MODEL.codex[2], spent: [1.2, 3.0, 4.1, 6.8, 8.0, 9.9, 12.3,
      15.1, 18.4].map((sum, n) => [n + 1, sum * today / 18.4]), line: "",
    level: budget ? (today >= budget ? "bad" : over ? "warn" : "ok") : null,
    words: { spent: money(today, true), of: budget ? `of ${whole(budget)}` : "", pace: said },
    pace_line: over ? { text: `${said} by November 30`, narrow: `${said} by Nov 30` } : null };
};
/** A chat's row. @param {any[]} row */
const talk = ([session, title, space, models, turns, tokens, cache, cost, kind]) => ({
  session, agent: kind === "spent" ? "codex" : "claude", folder: `/work/${space}`, title, space, turns, tokens, cache,
  cost, kind, models: models.map((/** @type {keyof typeof MODEL} */ key) => ({ name: MODEL[key][1],
    color: MODEL[key][2] })), tip: `$${(cost / turns).toFixed(2)} a turn · ${cache}% read from cache` });
const COSTLY = [["a1b2c3d4-0001", "Fix the page past the last one", "lumen-api", ["opus", "haiku"], 38, 9_400_000, 84,
  31.4, "value"],
["a1b2c3d4-0003", "Login redirect fix", "lumen-api", ["opus"], 22, 7_100_000, 80, 24.1, "value"],
["a1b2c3d4-0002", "Document the error format", "lumen-api", ["opus", "sonnet"], 18, 4_200_000, 78, 12.3, "value"],
["a1b2c3d4-0004", "Plan the tide table", "tidepool", ["sonnet"], 14, 3_000_000, 86, 9.8, "value"],
["a1b2c3d4-0005", "Spike the search API", "harbor-web", ["codex"], 9, 1_800_000, 71, 6.2, "spent"]].map(talk);
/** A model's row. @param {any[]} row */
const priced = ([key, agent, input, write, read, output, cost, kind]) => ({ model: MODEL[key]?.[0] ?? key,
  name: MODEL[key]?.[1] ?? key, color: MODEL[key]?.[2] ?? "#8b8b8b", agent, input, write, read, output, cost, kind,
  text: cost === null ? "no price" : `$${cost.toFixed(2)}` });
const PRICED = [["opus", "Claude", 600_000, 2_900_000, 24_600_000, 410_000, 108.2, "value"],
  ["sonnet", "Claude", 200_000, 800_000, 4_100_000, 120_000, 15.6, "value"],
  ["haiku", "Claude · subagents", 300_000, 500_000, 1_600_000, 80_000, 7.1, "value"],
  ["codex", "Codex", 400_000, 0, 1_400_000, 90_000, 8.6, "spent"],
  ["codex-auto-review", "Codex", 900_000, 0, 100_000, 10_000, null, "spent"]].map(priced);
const CLAUDE_CELL = { key: "Claude · Max plan", agent: "claude", value: 130.9, text: "~$130.90", unit: "API value",
  line: "no charge on the plan" };
const CODEX_CELL = { key: "Codex · API key", agent: "codex", value: 8.6, text: "~$8.60", unit: "spent in 7 days",
  line: "" };
const TOKENS_CELL = { key: "Tokens", value: 38_200_000, text: "38.2M", line: "81% read from cache" };
const REPORT_WORDS = { daily: "Per day, by model", month: "November, against its budget", projects: "By project",
  projects_note: "API value and spend combined", chats: "Chats", chats_note: "by cost", models: "Models",
  budget: "Budget…", export: "Export CSV", no_price: "no price", foot: "~ estimated from token counts at "
    + "Anthropic's and OpenAI's list prices (Nov 9, 2026); on a plan, what the same use would cost on the API" };
const REPORT = { period: { id: "7d", label: "7 days" }, prices_as_of: "Nov 9, 2026", none: null, more: 0,
  filters: { periods: [{ id: "today", label: "Today" }, { id: "7d", label: "7 days" }, { id: "30d", label: "30 days" },
    { id: "month", label: "November" }], agents: [{ id: null, label: "All agents" }, { id: "claude", label: "Claude" },
    { id: "codex", label: "Codex" }], spaces: "All spaces" },
  summary: [CLAUDE_CELL, CODEX_CELL, TOKENS_CELL], daily: dailyOf(SPENT, 3), legend: LEGEND,
  top: { day: "2026-11-07", label: "Nov 7", total: 33.5 }, month: monthOf(18.4, 46), months: [monthOf(18.4, 46)],
  projects: [{ folder: "/work/lumen-api", name: "lumen-api", cost: 84.2, tokens: 20_700_000 },
    { folder: "/work/harbor-web", name: "harbor-web", cost: 41.1, tokens: 12_100_000 },
    { folder: "/work/tidepool", name: "tidepool", cost: 14.2, tokens: 5_400_000 }],
  chats: COSTLY, models: PRICED, csv_name: "herdr-fold usage 2026-11-03 to 2026-11-09.csv",
  columns: { chats: ["Chat", "Space", "Models", "Turns", "Tokens", "Cache", "Cost"],
    models: ["Model", "Agent", "Input", "Cache write", "Cache read", "Output", "Cost"] },
  words: REPORT_WORDS };
// the month over its budget (usage.html's Keret): ~$45.10 of $50 by the 9th, on pace for ~$58
const REPORT_OVER = { ...REPORT, month: monthOf(45.1, 58), months: [monthOf(45.1, 58)], summary: [CLAUDE_CELL,
  { ...CODEX_CELL, value: 21.4, text: "~$21.40" }, TOKENS_CELL] };
// Codex alone, with no budget kept: its month's line and pace, no budget's line
const REPORT_CODEX = { ...REPORT, legend: [{ ...LEGEND[3], share: 100 }], month: monthOf(18.4, 46, null),
  months: [monthOf(18.4, 46, null)], daily: dailyOf(SPENT.map((day) => [0, 0, 0, day[3]]), 3),
  summary: [CODEX_CELL, { ...TOKENS_CELL, value: 1_800_000,
    text: "1.8M", line: "71% read from cache" }],
  projects: [{ folder: "/work/harbor-web", name: "harbor-web", cost: 8.6, tokens: 1_800_000 }],
  chats: [COSTLY[4]], models: PRICED.slice(3), words: { ...REPORT_WORDS, projects_note: "spent" } };
// thirty days: a column a day, every third named
const REPORT_MONTH = { ...REPORT, period: { id: "30d", label: "30 days" }, daily: dailyOf(Array.from({ length: 30 },
  (_, n) => SPENT[(n * 3) % 7].map((cost, m) => Math.round(cost * (0.6 + ((n * 7 + m) % 5) / 5) * 10) / 10)), 1) };
// no model with a price: the tokens alone, never $0.00
const REPORT_UNPRICED = { ...REPORT, legend: [], months: [], month: null, daily: dailyOf(SPENT.map(() => [0, 0, 0,
  0]), 3), summary: [{ ...CODEX_CELL, key: "Codex", value: null, text: "no price", unit: "API value", line: "" },
  { ...TOKENS_CELL, value: 1_010_000, text: "1.0M", line: "10% read from cache" }], projects: [{
    folder: "/work/harbor-web", name: "harbor-web", cost: null, tokens: 1_010_000 }], chats: [{ ...COSTLY[4],
    title: "Review the search spike", cost: null, tip: "", models: [{ name: "codex-auto-review", color: "#8b8b8b" }] }],
models: PRICED.slice(4), words: { ...REPORT_WORDS, projects_note: "API value" } };
const REPORT_NONE = { ...REPORT, none: "Nothing used in this period", summary: [], daily: [], legend: [], months: [],
  month: null, projects: [], chats: [], models: [] };
const ON_KEY = [{ key: "claude", name: "Claude", plan: "Max" }, { key: "codex", name: "Codex", plan: "API key" }];
const SCOPES = [{ name: "lumen-api", folder: LUMEN }, { name: "harbor-web", folder: "/work/harbor-web" },
  { name: "tidepool", folder: "/work/tidepool" }];

/** The Agents tab's Usage over REPORT (core's) with FIELDS over a fresh view's: nothing read, nothing pressed.
 * @param {any} report @param {Record<string, any>} [fields] */
function usageViewOf(report, fields = {}) {
  const view = Object.assign(Object.create(UsageView.prototype), { period: report?.period?.id ?? "7d", agent: null,
    folder: null, report, error: null, indexing: null, agents: ON_KEY, tip: null, marked: null, budget: null,
    listing: false, cursor: null, listPlaces: [], listScroll: null, reveal: false,
    revealed: false, still: true, scroll: ScrollHandle.new() }, fields);
  for (const name of ["follow", "read", "bringUp", "pick", "list", "budgets", "save", "exportCsv", "open", "plans",
    "ask"]) view[name] = () => {};
  return view;
}

/** One part of VIEW (a Usage view) alone, drawn by its method NAME (over REPORT), 12 in.
 * @param {any} view @param {string} name @param {any} [report] */
const usagePart = (view, name, report = null) => ({ draw: (/** @type {any} */ t) => div().p(PAD)
  .child(report ? view[name](t, report) : view[name](t)) });

/** This chat of GRAPH (core's run(), usage.html's Gráf): Claude on Opus, an Explore on Haiku, the files' tools,
 * Bash (RUNNING: its call not answered yet) and github called, in that order. @param {boolean} [busy] */
function ranOf(busy = false) {
  const ran = (/** @type {Record<string, any>} */ over = {}) => ({ ran: true, order: null, sub: null, tag: null,
    calls: null, count: 0, cost: null, model: null, share: null, started: null, properties: null, ...over });
  const lines = [["Model", "Opus 5.5 · High", null], ["Input", "30.0k", null], ["Cache write", "120k", null],
    ["Cache read", "790k", "84% of its input"], ["Output", "60.0k", null], ["Share", "90% of this chat", null]];
  const explore = graphNode("agent:Claude:Explore", "agents", "sub", "Explore", "Haiku · read-only",
    { parent: "agent", run: ran({ order: 2, cost: "~$0.42", share: 0.1, sub: "Haiku 5.5 · 210k tokens",
      model: { name: MODEL.haiku[1], color: MODEL.haiku[2] }, properties: { title: "Explore",
        state: { text: "~$0.42 API value", tone: "ok" }, lines: [["Model", "Haiku 5.5", null],
          ["Started", "by Claude at 2:05 PM, step 2", null], ["Input", "210k", null],
          ["Share", "10% of this chat", null]], text: null, error: null,
        actions: showsOf("sub", "agent:Claude:Explore") } }) });
  /** @type {Record<string, any>} */
  const told = { agent: ran({ cost: "~$3.70", share: 0.9, sub: "Opus 5.5 · 38 turns · 1.0M tokens",
    model: { name: MODEL.opus[1], color: MODEL.opus[2] }, properties: { title: "Claude", text: null, error: null,
      state: { text: "~$3.70 API value", tone: "ok" }, lines, actions: [{ id: "usage", label: "Open in Usage",
        session: "a1b2c3d4-0001" }, ...showsOf("agent", "agent")] } }),
  "rule:/home/dev/.claude/CLAUDE.md": ran(), [`rule:${LUMEN}/CLAUDE.md`]: ran(),
  [`rule:${LUMEN}/.claude/rules/api.md`]: ran({ ran: false }),
  [`skill:${LUMEN}/.claude/skills/routes/SKILL.md`]: ran({ order: 1, count: 1, sub: "used once · 300" }),
  [MORE_SKILLS]: ran({ ran: false }), [SUB_NODE]: ran({ ran: false, sub: "not run in this chat" }),
  "tool:files": ran({ order: 3, count: 14, calls: "14 calls", properties: { title: "Read · Edit · Write",
    state: null, lines: [["Calls", "14", null], ["Read", "9", null], ["Edit", "5", null]], text: null, error: null,
    actions: [] } }),
  "tool:Bash": ran({ order: 4, count: 3, calls: "3 calls" }),
  "connector:github": ran({ order: 5, count: 2, calls: "2 calls", sub: "6.8k tokens in context" }),
  "connector:figma": ran({ ran: false, sub: "not used", tag: { text: "sign in", tone: "warn" } }),
  [SENTRY.id]: ran({ ran: false }), "connector:claude.ai Notion": ran({ ran: false }) };
  const went = ["rule:/home/dev/.claude/CLAUDE.md", `rule:${LUMEN}/CLAUDE.md`,
    `skill:${LUMEN}/.claude/skills/routes/SKILL.md`, "tool:files", "tool:Bash", "connector:github"];
  const nodes = GRAPH.nodes.flatMap((one) => (one.id === SUB_NODE ? [explore, { ...one, run: told[one.id] }]
    : [{ ...one, run: told[one.id] ?? ran({ ran: false }) }]));
  return { ...GRAPH, session: "a1b2c3d4-0001", run: true, cost: "~$4.12", nodes,
  edges: [...GRAPH.edges.map((edge) => ({ ...edge, run: { ran: went.includes(edge.from) || (edge.from === "agent"
    && went.includes(edge.to)), running: busy && edge.to === "tool:Bash", calls: 0 } })),
  { from: "agent", to: explore.id, style: "demand", gates: [], run: { ran: true, running: false, calls: 1 } },
  { from: explore.id, to: "tool:files", style: "always", gates: [], run: { ran: true, running: false, calls: 4 } }] };
}
// what a chat cost, as costs.py tells it: usage.html's Áttekintés
const COSTS = { session: "a1b2c3d4-0001", kind: "API value", text: "~$4.12", tokens: "1.2M",
  line: "1.2M tokens · 82% from cache", agent: { cost: 3.7, text: "~$3.70", model: { id: MODEL.opus[0],
    name: MODEL.opus[1], color: MODEL.opus[2] } }, subs: { Explore: { cost: 0.42, text: "~$0.42",
    model: { id: MODEL.haiku[0], name: MODEL.haiku[1], color: MODEL.haiku[2] } } } };
const BUDGET_NOTICE = { notices: [{ key: "codex:2026-11", agent: "codex",
  text: "Codex has spent ~$45.10 of $50 this month · on pace for ~$58 by Nov 30" }] };

/** The Agents tab of FOUND (a graph, core's) with FIELDS over a fresh view's, for AGENT: nothing pressed, no place
 * kept; its Usage (a view of its own) shown where FIELDS give one. @param {any} found
 * @param {Record<string, any>} [fields] @param {string} [agent] */
function agentsOf(found, fields = {}, agent = "claude") {
  const view = Object.assign(Object.create(AgentsView.prototype), { space: null, found, missing: false, error: null,
    size: { width: 0, height: 0 }, sizes: {}, drag: null, chosen: null, listing: false, cursor: null, listPlaces: [],
    listScroll: null, agents: null, agentsError: null, still: true, folder: LUMEN, agent, view: "graph",
    mode: "wiring", usage: usageViewOf(null) }, fields);
  const look = { agent, programs: Object.fromEntries(KNOWN_AGENTS.map((p) => [p.key, p])), scopes: SCOPES };
  return { draw: (/** @type {any} */ t) => view.draw(t, look) };
}

/** A part's name in the page's index, from its id: "agent-panel" is Agent panel. @param {string} id */
const partName = (id) => id.charAt(0).toUpperCase() + id.slice(1).replaceAll("-", " ");

/** The styleguide page: its parts' index as Settings lists its sections, the one picked beside it (a part a render:
 * the app stops one that builds them all); or ONLY's part alone, from px FROM down (a screen of a taller one's
 * picture). @param {ReturnType<typeof guide>} g @param {string | null} [only] @param {number} [from] */
export function styleguide(g, t, only = null, from = 0) {
  const page = v_flex().id("styleguide").size_full().bg(t.canvas).text_color(t.foreground).text_size(13);
  const parts = sections(g, t), all = parts.flatMap(([, items]) => items);
  const shown = all.find(([id]) => id === (only ?? g.part)) ?? all[0];
  const body = v_flex().id(`styleguide-${shown[0]}`).flex_1().min_w(0).h_full().overflow_y_scrollbar()
    .child(v_flex().w_full().max_w(1400).px(48).py(APART).gap(APART).when(from > 0, (e) => e.relative().top(-from))
      .children(shown[1]()));
  if (only) return page.child(body);
  return page.child(h_flex().size_full().min_h(0).items_start()
    .child(v_flex().id("styleguide-index").w(INDEX).h_full().flex_none().overflow_y_scrollbar().py(PAD).px(8).gap(2)
      .bg(t.chrome).border_r(1).border_color(t.border)
      .children(parts.flatMap(([title, items]) => [
        div().flex_none().px(8).pt(8).pb(4).child(listName(t, title)),
        ...items.map(([id]) => h_flex().id(`styleguide-pick-${id}`).h(28).flex_none().px(8).items_center().rounded(6)
          .text_color(id === shown[0] ? t.foreground : t.muted)
          .when(id === shown[0], (e) => e.bg(t.selected))
          .when(id !== shown[0], (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover)
            .text_color(t.foreground))
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
              g.part = id;
              cx.notify();
            }))
          .child(div().min_w(0).truncate().child(partName(id))))])))
    .child(body));
}

/** A group of specimens under its name, side by side as room allows; none: no group. */
function group(t, name, specimens) {
  if (!specimens.length) return null;
  return v_flex().gap(16).child(div().text_size(15).font_weight(700).text_color(t.foreground).child(name))
    .child(h_flex().flex_wrap().items_start().gap(24).children(specimens));
}

/** The items of the part ID: [id, its groups], or its two halves (HALVES), each [id-half, its specimens' groups];
 * MAKE builds the groups, each group's specimens through the KEEP it is given. @param {string} id
 * @param {(keep: (specimens: any[]) => any[]) => any[]} make @returns {[string, () => any[]][]} */
function halves(id, make) {
  const split = /** @type {Record<string, [string, number[]?][]>} */ (HALVES)[id];
  if (!split) return [[id, () => make((specimens) => specimens)]];
  const first = split[0][1] ?? [];
  return split.map(([half, places]) => [`${id}-${half}`, () => {
    let place = 0;                                // a specimen's place in the part, over its groups in turn
    const kept = (/** @type {number} */ n) => (places ? places.includes(n) : !first.includes(n));
    return make((specimens) => specimens.filter(() => kept(place++))).filter(Boolean);
  }]);
}

/** CONTENT in a popover WIDE and HIGH, framed as the app frames its popups, on a stage round it. @param {number} wide
 * @param {number} high @param {any} content @param {number} [pad] the stage round it */
function popover(t, wide, high, content, pad = 20) {
  return div().p(pad).child(div().w(wide).h(high).rounded(8).border_1().border_color(t.border)
    .bg(t.popover ?? t.raised).child(content));
}

/** One specimen: CONTENT on a card (the cards' level), its state's NAME under it and what it is made of (SPEC); a
 * control (SMALL) at its own size in the middle of a stage of one height. */
function specimen(t, id, name, content, { width = PANEL, spec = "", small = false } = {}) {
  const stage = div().w_full().rounded(10).overflow_hidden().bg(t.surface).border_1().border_color(t.border);
  return v_flex().id(id).w(width).flex_none().gap(8)
    .child(small ? stage.h(72).flex().items_center().justify_center().child(content) : stage.child(content))
    .child(v_flex().gap(2).child(div().text_size(12).child(name))
      .when(Boolean(spec), (e) => e.child(div().text_size(11).text_color(t.dim).child(spec))));
}

/** The page's parts, each [title, items], an item [id, its groups made on asking]: the id names its picture, and a tab
 * of one part draws that part alone (the app stops a render that takes too long). @param {ReturnType<typeof guide>} g
 * @returns {[string, [string, () => any[]][]][]} */
function sections(g, t) {
  const b = g.base;
  const fixed = (h, content) => div().h(h).flex().flex_col().child(content);
  // the preview tab's specimens, each [name, preview, height], two side by side, the first with what it is made of
  const tabs = (id, specimens) => specimens.map(([name, preview, h], i) => specimen(t, `${id}-${i}`, name,
    fixed(h, preview.render(t, CODE_FONT)), { width: TAB, spec: i ? "" : `${CODE_FONT} 13 · h 22 · numbered once` }));
  // the dock's tabs as its stack's header draws them atop the card (a specimen's stage is the card), a view under them
  const head = ({ shown, opened = false, views = VIEWS_APP, count = CHANGED, px = PANEL, hovered = null,
    agent = KNOWN_AGENTS[0], problems = null }) =>
    div().h(TABS_H).flex_none().child(dockTabs(t, { shown, views, changed: count, opened, px, hovered, agent,
      problems }, INERT_TABS));
  const framed = (h, content) => fixed(h, v_flex().size_full().rounded(10).overflow_hidden().border_1()
    .border_color(t.border).bg(t.surface).child(content));
  const stack = (shown, view) => fixed(TABS_H + 560, v_flex().size_full().child(head({ shown }))
    .child(div().flex_1().min_h(0).flex().flex_col().child(view)));
  const trees = (id, list, spec) => list.map(([name, view], i) => specimen(t, `${id}-${i}`, name,
    fixed(320, view.draw(t)), { spec: i ? "" : spec }));
  return [["Foundations", [["color", () => [colors(t)]], ["type", () => [type(t)]],
    ["shape", () => [spacing(t), shape(t)]], ["icons", () => [icons(t)[0]]],
    ["file-types", () => [icons(t)[1]]]]], ["Components", [
    ["buttons", () => [
      group(t, "Buttons", [
        specimen(t, "b-primary", "Primary", button(t, "s-commit", h_flex().gap(8).items_center()
          .child(icon("check")).child("Commit"), true, true, () => {}), { width: 180, small: true,
          spec: "solid · h 32 · radius 8 · 12 bold" }),
        specimen(t, "b-primary-busy", "Primary, busy", button(t, "s-busy", "Committing…", false, true, () => {}),
          { width: 180, small: true, spec: "the work's name in place" }),
        specimen(t, "b-secondary", "Secondary", button(t, "s-sync", h_flex().gap(6).items_center()
          .child(icon("refresh-cw")).child("1↓ 2↑"), true, false, () => {}), { width: 180, small: true,
          spec: "raised · h 32 · radius 8 · 12 bold" }),
        specimen(t, "b-disabled", "Secondary, disabled", button(t, "s-off", h_flex().gap(6).items_center()
          .child(icon("refresh-cw")).child("1↓ 2↑"), false, false, () => {}), { width: 180, small: true,
          spec: "dim words, no pointer" }),
        specimen(t, "b-icon", "Icon", button(t, "s-write", icon("sparkles", 15), true, false, () => {})
          .bg(t.selection).text_color(t.accent), { width: 180, small: true, spec: "selection · accent icon" }),
        specimen(t, "b-row", "Row buttons", h_flex().gap(4)
          .child(small(t, "s-discard", icon("undo-2"), "Discard changes", true, () => {}))
          .child(small(t, "s-stage", icon("plus"), "Stage", true, () => {}))
          .child(small(t, "s-unstage", icon("minus"), "Unstage", true, () => {}))
          .child(small(t, "s-confirm", "Discard", "Discard changes", true, () => {})),
        { width: 180, small: true, spec: "h 20 · px 6 · radius 4 · raised on hover" }),
      ])]],
    ["files", () => [group(t, "Files", trees("files", g.files,
      "h 26 a row · 12 a level · Catppuccin Icons' · git's colors"))]],
    ["file-edits", () => [group(t, "Files: a name typed in its row, Move to Trash asked", trees("file-edits",
      g.fileEdits, "typed in its row, as VS Code's · ⏎ makes it, esc drops it"))]],
    ["repository", () => [group(t, "Repository", g.repository.map(([name, state], i) => specimen(t, `repository-${i}`,
      name, state.repository(t), { spec: i ? "" : "as VS Code's Repositories · h 26 · ⋯ its menu" })))]],
    ["commit", () => [group(t, "Commit", g.composer.map(([name, state], i) => specimen(t, `composer-${i}`, name,
      state.composer(t))))]],
    ["branch-pull", () => [group(t, "The branch's pull request", g.branchPull.map(([name, state], i) => specimen(t,
      `branch-pull-${i}`, name, state.repository(t), { spec: i ? "" : "under the repository's row, PAD / 2 in: h 32, "
        + "radius 8, a hairline, chrome · the checks' mark 14, #N and the title, the state a word or a neutral tag, "
        + "the checks 12 muted · none: its icon muted, Create pull request… a row button" })))]],
    ["pull-form", () => [group(t, "New pull request", g.pullForm.map(([name, pull, h], i) => specimen(t,
      `pull-form-${i}`, name, fixed(h, pull.formView(t)), { spec: i ? "" : "in the composer's place, PAD in, 8 "
        + "apart · its labels 12 muted in 44 · Into a menu h 26 raised · Title a field h 32 with ✦ · Body grows from "
        + "4 lines · As a choice of two · what wrote it 11 muted, gh's refusal red · Cancel plain, the one solid "
        + "button its words following the choice" })))]],
    ["title-row", () => [group(t, "Title row", TITLES.map(([name, title, width], i) => specimen(t, `title-row-${i}`,
      String(name), div().h(36).child(titleRow(t, /** @type {any} */ (title))), { width: Number(width),
        spec: i ? "" : "h 36 with its hairline, the window's level · the lights 18 in, on its middle line · the field "
          + "300 × 25 on the window's centre, px 8, gap 6, radius 6, a hairline round it · the mark 14 muted, the "
          + "space's name 12 and the key 11 dim · the hover fill, all in the text's color · narrower than 160, its "
          + "mark alone" })))]],
    ["palette", () => [group(t, "Command palette", g.palettes.map(([name, palette, high], i) => specimen(t,
      `palette-${i}`, String(name), v_flex().h(Number(high)).relative().bg(t.canvas)
        .child(div().h(36).child(titleRow(t, { mac: true, name: "lumen-api", key: PALETTE_KEY(true), field: 300,
          buttons: null, open: true })))
        .child(div().absolute().top(8).left(PALETTE_SIDE).w(PALETTE_WIDE).h(Number(high) - PALETTE_SIDE - 8)
          .child(/** @type {Palette} */ (palette).draw(t, PALETTE_ENTRIES, APP_KEYS, "herdr-fold", true))),
      { width: PALETTE_WIDE + 2 * PALETTE_SIDE, spec: i ? "" : "600 on the window's centre, 8 under its top: its field "
        + "over the title row's, 25 high, 5 in, a hairline (input) round it, the ⌘ 14 muted, Esc 11 dim · a "
        + "hairline under it · the panels' surface and list form: rows 32, a part's name 11 dim, the keys' row on "
        + "the hover fill · a key as caps, 16 high, 4 apart · typed: one list, the group a muted tag · after the app's "
        + "groups, herdr-fold's own (herdr-fold)" })))]],
    ["tab-bar", () => [group(t, "Tab bar", [
      specimen(t, "tab-bar", "The space's tabs: the first named as the space, an agent working there, one waiting, "
        + "a shell under the pointer, one done; at its end Chats with a chat waiting, More and »",
        div().h(42).child(tabBar(t, "t3", { ...END, waiting: 1 })),
        { width: 2 * PANEL, spec: "h 28 · px 12, 8 by the × · radius 6 · gap 4, 6 inside · × shown and on hover · "
          + "+ New chat, >_ New terminal · « while the dock is a rail" }),
    ]), group(t, "The tab bar's end", g.ends.map(([name, end], i) => specimen(t, `tab-bar-end-${i}`, name,
      h_flex().w_full().h(42).px(12).justify_end().items_center().bg(t.canvas).child(barEnd(t, end, INERT_END)),
      { width: 240, spec: i ? "" : "over the dock, on the window's level · each 26 square, its icon 15, 4 apart · "
        + "a dot 7 centred on the icon's top-right corner, ringed 2 in the window's level · tips to the left" })))]],
    ["status-bar", () => [group(t, "Status bar", BARS.map(([name, state], i) => specimen(t, `status-bar-${i}`,
      String(name), v_flex().h(28 + PAD).justify_end().bg(t.canvas)          // the window's foot: its hairline 12 down
        .child(div().h(28).child(statusBar(t, /** @type {any} */ (state)))),
      { width: 2 * PANEL, spec: i ? "" : "h 28 · chrome, a hairline over it · 16 in, 16 apart · 12 muted · a dot 6: "
        + "waiting ansi3, working the accent · an update's dot ansi2, the hover fill under the pointer" })))]],
    ["tabs", () => [group(t, "The dock's tabs", g.heads.map(([name, state], i) => specimen(t, `head-${i}`, name,
        fixed(TABS_H + PAD, head(state)), { width: state.px ?? PANEL,
          spec: i ? "" : `h ${TABS_H}, the card's top: 8 over and under the tabs, 6 at the sides, a hairline `
            + "under · a tab as wide as its words: h 28, px 6, radius 8, 13, 2 apart · the shown one raised · a count "
            + "after its name, h 18, 11 semibold" }))),
      group(t, "Search field", g.query.map(([name, state], i) => specimen(t, `query-${i}`, name, state.query(t))))]],
    ["rail", () => [group(t, "The panel folded to its rail", [
        specimen(t, "rail-github", "On GitHub, with changes, the terminal shown under the tab",
          onRail(t, rail(t, { github: true, changed: 6 }, "t1", null, true)),
        { width: 120, spec: `w ${RAIL} · chrome, rounded 10: as the left sidebar folded · its first icon 8 in, level `
          + "with the left's · Terminal lit while shown · Chats at the tab bar's end" }),
        specimen(t, "rail-plain", "No GitHub, no terminal yet", onRail(t, rail(t,
          { github: false, changed: 0 }, null)), { width: 120 }),
        specimen(t, "rail-problem", "Agent's setup has a problem: its dot", onRail(t, rail(t,
          { github: true, changed: 0 }, "t1", null, false, PROBLEMS)), { width: 120,
          spec: "a folded side's state dot: 9, ringed 2 · red over yellow · what it is in the tip" }),
        specimen(t, "rail-floating", "Changes floating beside it: its icon lit", onRail(t, rail(t,
          { github: true, changed: 6 }, "t1", null, false, null, "changes")), { width: 120,
          spec: "lit as Terminal shown · a press on it, Esc or its × closes it" }),
        specimen(t, "rail-float", "A view floating beside it", div().w(PANEL).child(floatHead(t, "Changes", "", [])),
          { spec: "as wide as the panel · its head drags it" }),
        specimen(t, "rail-chats", "Chats floating beside it (the tab bar's ✦), the filter taking the keys",
          floatPanel(t, "Chats", "", 300, [], g.floating.list(t, g.floating.rows()),
            { foot: floatGrip(t, new FloatSize("chats")) }),
        { spec: "its head drags it · × closes it · the grip at its foot sizes it, its head and 3 rows at least, "
          + "kept for it" })])]],
    ["sections", () => [
      group(t, "Section header", g.sections.map(([name, state], i) => specimen(t, `section-${i}`, name,
        div().p(PAD / 2).child(state.section(t, "changes", "Changes", CHANGES)),
        { spec: i ? "" : "h 26 · 13 bold · chip" }))),
      group(t, "Count chip", [specimen(t, "chip", "Default, and large: short", h_flex().gap(8).child(chip(t, "1"))
        .child(chip(t, "12")).child(chip(t, shortCount(18432))),
      { width: 180, small: true, spec: "raised · px 6 · radius 4 · 11 semibold · 1.2k, 18k" })])]],
    ["rows", () => [group(t, "File row", g.rows.map(([name, kind, file, state], i) => specimen(t, `row-${i}`, name,
        div().p(6).child(state.file(t, kind, file)), { spec: i ? "" : "h 26 · icon, name, folder, letter" })))]],
    ["graph", () => [group(t, "Graph", g.graph.map(([name, state], i) => specimen(t, `graph-${i}`, name,
        fixed(state.folded.has("graph") ? 26 : 32 + COMMITS.length * 24, state.graph(t)))))]],
    ["menus", () => [group(t, "Menus", [["Commit's arrow", b.modes], ["The repository's ⋯", b.remote],
      ["Issues' filters", g.issues.issues.filters(t)], ["An issue's right click", b.issues.picks(LISTED[0])],
      ["A file's right click, a preview open", g.files[0][1].items({ path: "docs/pagination.html", dir: false })],
      ["The preview's right click", g.page.items()],
      ["More: Search hidden", [...panelChoices(DOCKED, true), null, { label: "About herdr-fold" }]],
      ["A chat's right click", g.chats[0][1].choices(TALKS[3])],
      ["A running chat's: Delete… off, its tip says why", g.chats[0][1].choices(TALKS[0])],
      ["The list's right click", g.chats[0][1].choices(null)]]
      .map(([name, items, wide = MENU], i) => specimen(t, `menu-${i}`, name, popover(t, wide, menuHeight(items),
        menuPopup(t, "", items)), { width: 240,
        spec: i ? "" : "under its button, right-aligned, above it where it does not fit; a right click's at it" })))]],
    ["content", () => [
      group(t, "Problem", [specimen(t, "problem", "Over the card's last strip, until the next try or its ×",
        div().relative().h(56).child(g.problem.problem(t)), { spec: "11 · ansi1 · nothing under it moves" })]),
      group(t, "Empty states", g.empty.map(([name, state], i) => specimen(t, `empty-${i}`, name,
        fixed(56, state.list(t))))),
      group(t, "A note", [specimen(t, "note-error", "An error, while An agent waits on you is off: drawn by herdr-fold",
        fixed(56, noteToast(t, { title: "Couldn't export the chat", body: "The folder is read-only", level: "error" })),
        { width: 360, spec: "the app's toast: on popover, 16 in, 12 apart · its level's dot 8 (error blocked, warning "
          + "working) or its icon 18 · the title 13 semibold, the body's first line 12 muted · a click runs its action "
          + "and closes it" })])]],
    ["agent-panel", () => [group(t, "The Agent panel", g.agentPanels.map(([name, view, h, width = PANEL], i) =>
      specimen(t, `agent-panel-${i}`, String(name), fixed(Number(h), /** @type {any} */ (view).draw(t)), {
        width: Number(width),
        spec: i ? "" : "the head 12 in, its line 12 muted, the problems' chips at its end; the bar 6 high by "
          + "share (rules the accent, skills ansi6, connectors ansi4), a hairline under it · a section's head h 28: "
          + "its chevron 14 dim, the title semibold, its count 11 muted, its cost 11 muted in 52 after its part's "
          + "swatch 7 · a row h 26, 10 in: its mark in 12 (✕ red, a dot yellow or green), a connector's logo 16, the "
          + "name, its note 11 muted; the states and the tags (raised, muted) each in one column · a group's head "
          + "h 22, 11 muted" })))]],
    ...halves("agents-graph", (keep) => [group(t, "The Agents tab: the graph", keep(g.agentsGraph.map(
      ([name, view, h, width], i) => specimen(t, `agents-graph-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (view).draw(t)), {
      width: Number(width), spec: i ? "" : "the head 15 semibold, 12 in · the canvas a hairline frame, radius 10, "
        + "dots 20 apart · a node on the side's level: 8 and 12 in, radius 10, its title 12 semibold, its tag 11 at "
        + "its top right (a raised chip, muted), its line 11 muted, chips code 11 on the window's level; the agent's "
        + "edge the accent at 60% on "
        + "its 6%, the chosen one ringed 2 · an edge 1.5, seen 3:1; on demand, waiting and failed dashed 5 and 5 · a "
        + "gate h 18, 6 in, radius 4, a hairline · the legend h 26 at the top right · the properties 300 wide, a "
        + "popover, 12 in, the labels in 70 · This chat (its whole in the head's switch): an edge that ran 2 in the "
        + "accent, the running one "
        + "3, the others at 35%; a first use's number a disc 18 in the accent on its node's top right corner, 11 "
        + "bold; a cost 12 at the top right, a model's square 8 before its line, its share a 4 px bar; the "
        + "properties 340 wide, the labels in 82" }))))]),
    ...halves("agents-usage", (keep) => [group(t, "The Agents tab: Usage", keep(g.agentsUsage.map(
      ([name, view, h, width], i) =>
      specimen(t, `agents-usage-${i}`, String(name), fixed(Number(h), /** @type {any} */ (view).draw(t)), {
        width: Number(width), spec: i ? "" : "the head's two views 13, the shown one over 2 px of the accent · "
          + "the filters one row, each a switch h 26 on the window's level, a part radius 6 · the summary one frame "
          + "on the side's level, radius 10: a key 12 dim, a value 20 semibold with its unit 12, a line 12 muted · "
          + "a chart a hairline frame, 16 and 12 in: its title 13 semibold, a swatch 8 · the plot 180 high, ticks 11 "
          + "dim in 40, a column 24 at most, 2 px between segments, the top one's corners 4 · the month 170 high: "
          + "the budget a muted hairline, the line 2 px, the pace at 40%, today's point 8 ringed 2 · a project's "
          + "row 32, its bar 16 muted · a table's head 36, its columns' names 11 dim, a row 32, numbers "
          + "right-aligned · the budget 300 wide, a field h 28" }))))]),
    ...halves("agent-properties", (keep) => [group(t, "The Agent panel: the chosen row's properties",
      keep(g.agentProperties.map(
      ([name, view, h], i) => specimen(t, `agent-properties-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (view).draw(t)), { spec: i ? "" : "the chosen row on the accent's 14% · under the layers, "
          + "on the side's level, a hairline over, 12 in, 6 apart: the title h 20 (a connector's logo, 12 semibold, "
          + "its state 11 at the end) · a line h 20: its label muted in 64, its value code 11 (a phrase in the "
          + "text's), a third column muted · the error 8 and 6 in, radius 6, red on its 8%, the files it named its "
          + "tip · buttons h 26, 12 in, radius 8, the first raised" }))))]),
    ...halves("agent-connectors", (keep) => [group(t, "The Agent panel: Connectors", keep(g.agentConnectors.map(
      ([name, draw, h], i) => specimen(t, `agent-connectors-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (draw)(t)), { spec: i ? "" : "a connector's logo 16 in its own colors, a one-color mark "
          + "in the text's, an unknown one its letter 10 bold on a tile, radius 4 · signing in: a spinner 12 in the "
          + "accent, a turn in 0.9 s, before the state and before Finish in your browser · Connect h 26 bold on the "
          + "accent, else the first button raised, the rest muted; one that waits faint · + 22, radius 6, at the "
          + "head's end before the costs; its menu 200, the panels' rows, icons 16 · the form: a field h 28, radius "
          + "8, code 11 on canvas, the focused one's edge the accent, a refused one's red; For a two-part switch on "
          + "canvas, radius 6, the chosen part raised, radius 4" }))))]),
    ["agent-usage", () => [group(t, "The Agent panel: Usage, its first section", g.agentUsage.map(
      ([name, draw, h, width = PANEL], i) => specimen(t, `agent-usage-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (draw)(t)), { width: Number(width), spec: i ? "" : "the head as a section's, no count; "
          + "folded, the figure before Open Usage: icon 14, 6, its words 11 muted, the figure semibold in its level · "
          + "a row h 26, 10 in: its mark's room 12, the agent's icon 14, its name 12, the plan 11 muted; at its end "
          + "each window in 74: 5h or wk 11 muted, its bar 22 × 4 on raised (3:1), the percent 11 semibold in its "
          + "level's color (under 50 green, from 50 yellow, from 80 red), 4.5:1, – muted; on an API key its month's "
          + "figure in its level, of $150 muted · under a row only while yellow or red, h 20, 11 muted: its reset, or "
          + "the pace · the agent shown with no reading: limits not told 11 muted at its end, why in its properties "
          + "· a press chooses it, its properties under the layers · under 300 px the bars go · Open Usage 22 square"
      })))]],
    ...halves("agent-editing", (keep) => [group(t, "The Agent panel: a row's form in its properties", keep(
      g.agentEditing.map(([name, draw, h, width = PANEL], i) => specimen(t, `agent-editing-${i}`, String(name),
        fixed(Number(h), /** @type {any} */ (draw)(t)), { width: Number(width), spec: i ? "" : "the form under the "
          + "row's lines, the properties' 6 apart · a line h 28 or as high as its control wraps: its label muted in "
          + "64 · a choice its parts h 20 on canvas, 2 in and apart, radius 6, the chosen raised, radius 4, a grey "
          + "one dim · a switch 28 × 16 at its line's end · a field h 28, radius 8, code 11 · a host's line h 20: "
          + "code 11, its layer's tag, × 16 · a way h 26, radius 6, ✓ 12 in the accent, the chosen raised · the "
          + "change 8 and 6 in on canvas, radius 6: code 11, a line 16, − red, + green, then when it applies 11 "
          + "muted · a warning 11 yellow, a refusal red, a note muted · Cancel plain and the one solid button at "
          + "the end, faint while nothing can be saved · the foot h 32 under a hairline: 12 muted, a line in code "
          + "11, Undo semibold" }))))]),
    ["agent-list", () => [group(t, "The Agent panel: the agents on this Mac", g.agentLists.map(
      ([name, draw, h, width = PANEL], i) => specimen(t, `agent-list-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (draw)(t)), { width: Number(width), spec: i ? "" : "the chip h 26, 6 in, radius 6, ringed "
          + "in the accent while open · the list 300 (the panel less 12 where narrower), 4 under the chip, the "
          + "panels' form: a group's head 12 semibold muted, a row 32 (✓ 12 in the accent on the one shown, icon 16, "
          + "the name 13, cut where long; at its end the plan 12 muted, or sign in in yellow) · a rule, then Not "
          + "installed: its rows muted, the icon at 0.6" })))]],
    ["agent-states", () => [group(t, "The Agent panel: an agent with no setup to show", g.agentStates.map(
      ([name, draw, h], i) => specimen(t, `agent-states-${i}`, String(name), fixed(Number(h),
        /** @type {any} */ (draw)(t)), { spec: i ? "" : "in the setup's place, centered, 24 in, 8 apart: the "
          + "agent's icon 28, the title 13 semibold, the words 12 muted in 272, the install line code 11 on canvas "
          + "with Copy, Sign in h 26 on the accent, the last line 11 dim" })))]],
    ["issues", () => [
      group(t, "Issue row", g.issueRows.map(([name, state, issue], i) => specimen(t, `issue-row-${i}`, name,
        div().p(6).child(state.issues.row(t, issue)),
        { spec: i ? "" : "h 48 · priority bar 3 · number in its color" })))]],
    ["issue-list", () => [group(t, "Issue list", g.issueList.map(([name, state, h], i) => specimen(t, `issue-list-${i}`,
      name, fixed(h, state.issues.render(t)))))]],
    ["pulls", () => [group(t, "Pull request row", g.pullRows.map(([name, state, pull], i) => specimen(t,
      `pull-row-${i}`, name, div().p(6).child(state.pulls.row(t, pull)), { spec: i ? "" : "h 48 · the checks' mark "
        + "14: ✓ ansi2, ● ansi3 running, ✕ ansi1 · #N muted · the review a word: your review ansi3, changes "
        + "requested ansi1, approved ansi2, Draft a neutral tag · branch · author · age 11 dim" })))]],
    ["pull-list", () => [group(t, "Pull request list", g.pullList.map(([name, state, h], i) => specimen(t,
      `pull-list-${i}`, name, fixed(h, state.pulls.render(t)))))]],
    ["editor", () => [group(t, "Editor tab", g.editors.map(([name, editing, h, w], i) => specimen(t, `editor-${i}`,
      name, fixed(h, editing.render(t, CODE_FONT)), { width: w, spec: i ? "" : "EditorState + Editor, the theme's "
        + "colors, line numbers, folding · a line over it 36 high on chrome, a hairline under it, 12 muted, its icon "
        + "14 dim, its buttons raised · the find bar 8 under its top, 14 from its right: a field 190, the count 12 "
        + "muted, ↑ ↓ × 26 square, on the popover, radius 8" }))),
    group(t, "An editor's tab", [specimen(t, "editor-tab", "Named for its file; unsaved, a neutral dot in its ×'s "
      + "place, the × under the pointer; reopened, its draft and its dot back", div().h(42)
      .child(tabBar(t, null, END, EDITED)), { width: 2 * PANEL, spec: "the dot 8, the foreground, centred in the ×'s "
        + "16 square · no other mark: Files' row keeps git's letter" })])]],
    ["preview", () => [group(t, "Preview tab", tabs("preview", g.preview))]],
    ["preview-page", () => [group(t, "An SVG or a page in the preview tab", tabs("preview-page", g.pageViews))]],
    ["preview-issue", () => [group(t, "An issue in the preview tab", [specimen(t, "preview-issue", "Issue",
      fixed(330, g.issue.render(t, CODE_FONT)), { width: 2 * TAB + 24 })])]],
    ["preview-pull", () => [group(t, "A pull request's review in the preview tab", g.reviews.map(([name, preview, h],
      i) => specimen(t, `preview-pull-${i}`, name, fixed(h, preview.render(t, CODE_FONT)), { width: 2 * TAB + 24,
        spec: i ? "" : "the head 15, #N muted, the state at its end; its branches, author, checks, files 12 muted · a "
          + "file's bar h 32 on chrome, + ansi2 − ansi1 · a line 20 in code, its number 44 (a press comments) · a "
          + "thread and a comment added under their line, radius 8, a hairline, chrome · the bar: the summary, the "
          + "count, Comment, Approve, Request changes, Submit review the one solid button" })))]],
    ["spaces", () => [group(t, "Spaces", [
      specimen(t, "sidebar-head", "The sidebar's head: Herdr's mark and name, Go to space or tab, its toggle",
        div().h(42).child(sidebarHead(t, true)), { width: SIDEBAR, spec: "h 42, on the tab row's line, under the "
          + "title row · Herdr's mark 18, radius 4, 16 in, its name 13 semibold 8 after it: the Spaces rows' avatar "
          + "and name · each button 26 square, its icon 15, 4 apart · 8 from the edge, the toggle over Spaces' +" }),
      specimen(t, "spaces-machines", "By machine, the waits beside the branch, lab's head hovered",
        fixed(listHeight(MACHINES), spacesList(t, MACHINES, { hovered: "lab" })),
        { width: SIDEBAR, spec: "h 32 a row · 28 a worktree's and a machine's · + on its hover · ansi3" }),
      specimen(t, "spaces-local", "This computer only", fixed(listHeight([LOCAL]), spacesList(t, [LOCAL])),
        { width: SIDEBAR }),
      specimen(t, "spaces-home", "Each machine's home, first: nothing open on this computer and on mini, open on lab; "
        + "lab's root and win's drive", fixed(listHeight(AT_HOME), spacesList(t, AT_HOME)), { width: SIDEBAR,
        spec: "a space's row · nothing open: the avatar a 1 px outline in border, ~ and the name dim, no branch · a "
          + "click opens a terminal there · a root: root or the drive (C:), / or its letter on home's ansi6" }),
      specimen(t, "spaces-drag", "notes dragged over harbor-web", fixed(listHeight([LOCAL]), spacesList(t, [LOCAL],
        { pressed: "s3", over: "s2" })), { width: SIDEBAR, spec: "the line where it goes, between two rows" }),
      specimen(t, "spaces-loading", "Loading", fixed(listHeight([{ ...GROUP, machine: null, rows: [], loading: true }]),
        spacesList(t, [{ ...GROUP, machine: null, rows: [], loading: true }])), { width: SIDEBAR }),
      specimen(t, "sidebar-foot", "The sidebar's foot: Settings, the one Settings, and Add machine…",
        fixed(69, sidebarFoot(t)), { width: SIDEBAR, spec: "69 high, on the side's level under a hairline · a row 28, "
          + "8 in, rounded 8 · its icon 14 and name 13, 8 apart, muted · Add machine… dim" })])]],
    ...halves("chats", (keep) => [group(t, "Chats", keep(g.chats.map(([name, view], i) => specimen(t, `chats-${i}`,
      name, framed(360, view.list(t, view.rows())), { width: PANEL,
        spec: i ? "" : "in the dock, in the view's place · h 24 a row · a space's chevron leftmost, 14 dim, its "
          + "count 11 muted · a chat's agent (where no icon says it) and age two right-aligned columns, 11 muted · "
          + "marks in herdr's colors" }))))]),
    ["sidebar-folded", () => [group(t, "The sidebar folded", [
      specimen(t, "sidebar-dock", "A dock of Spaces", fixed(260, dock(t, SPACES.map((space) => space.status))),
        { width: 76 }),
      specimen(t, "sidebar-dock-lit", "Spaces floating: its icon lit",
        fixed(260, dock(t, SPACES.map((space) => space.status), true)),
        { width: 76, spec: "the selected square, its icon and name in the accent · a press closes it" }),
      specimen(t, "spaces-float", "Spaces, floating beside it, home with nothing open",
        floatPanel(t, "Spaces", "", floatHeight(1 + SPACES.length) + FLOAT_GRIP, spacesButtons(t), spacesBody(t,
          [{ id: "home:", name: "~", active: false, status: null, empty: true }, ...SPACES], COLORS, WAITING),
        { foot: floatGrip(t, new FloatSize("spaces")) }),
        { width: 300, spec: "as tall as its rows until its grip sizes it, kept · its head drags it · ×, Esc, its icon "
          + "or a press beside it closes it" }),
      specimen(t, "sidebar-head-folded", "Its toggle, in its head over the rail", div().w(RAIL).h(42)
        .child(sidebarHead(t, false)), { width: 120, small: true, spec: "centred over the rail, as the right's « · "
          + "Expand panels; open, Collapse to icons" })])]],
    ["search", () => [group(t, "Search results", [specimen(t, "hits", "Hits, one shown at its line",
      fixed(300, v_flex().size_full().child(g.search.hits(t)).child(g.search.lines(t))))])]],
    ["terminal", () => [group(t, "The tab's terminal", [specimen(t, "terminal-none", "When it could not start",
      div().h(60).child(standIn(t, "No terminal: the machine is not reachable")),
      { spec: "12 · ansi1, in its place" })])]],
    ...[["settings", "Settings", 0], ["settings-states", "Settings: the keys, a look failed or under way",
      SHOWN]].map(([id, title, from]) => [id, [group(t, title, g.settings.slice(from, from + SHOWN).map(([name, view],
      i) => specimen(t, `${id}-${i}`, name, popover(t, SETTINGS.wide, SETTINGS.high, view.render(t, CODE_FONT), 16),
      { width: SETTINGS.wide + 32, spec: i || from ? "" : "the one Settings, from the sidebar's Settings and ⌘,, "
        + "600 × 380 in every section and state · its head 44 · its sections 160 on the side's level, a row 28, the "
        + "shown one on the selection, the app's under Application (11 in dim at 0.7, 10 down), "
        + "each opening the app's Settings there · the section 24 inside · ↑ ↓ the section, Tab its controls · "
        + "×, Esc, a click beside" })))]]),
    ["chat-prompt", () => [group(t, "The chat's prompt", g.prompts.map(([name, chat, wide = CHAT], i) => specimen(t,
      `prompt-${i}`, name, chat.bottom(t, CODE_FONT), { width: wide,
        spec: i ? "" : "radius 10 · its bar: +, commands, terminal, context, clock, the model chip, mode, send" }))),
    group(t, "Files attached, the + and @", g.attached.map(([name, chat], i) => specimen(t, `attached-${i}`, name,
      chat.bottom(t, CODE_FONT), { width: CHAT, spec: i ? "" : "a chip 24 high on the raised fill, radius 6: the "
        + "type's icon 16, the name 12 (200 at most, its path its tip), × 20 · 4 apart, 12 in, wrapping" })))]],
    ...halves("chat-plus", (keep) => [group(t, "The + menu", keep(g.plus.map(([name, chat], i) => specimen(t,
      `plus-${i}`, name, div().p(20).child(chat.plusPanel(t)), { width: PLUS + 40,
      spec: i ? "" : "connectors.html's + menü · upward "
        + "from the +, left-aligned · w 380 · rows 32, icons 16 muted, the keys as caps · Connectors 12 semibold "
        + "muted, a problem's pill 16 high, Manage › in the accent · a logo 16, the switch 28 × 16" })))),
    group(t, "Add context's list", keep(g.mentions.map(([name, chat], i) => specimen(t, `mention-${i}`, name,
      div().p(20).child(chat.mentionPanel(t)), { width: COMMANDS + 40, spec: i ? "" : "the / menu's form, over the "
        + "prompt · w 520 · a file's type's icon 16, its name, its folder 12 dim · Changed, Files, 5 of each" }))))]),
    ...halves("chat-panel", (keep) => [group(t, "The model chip's panel", keep(g.models.map(([name, chat], i) =>
      specimen(t, `models-${i}`, name, div().p(20).child(chat.modelPanel(t)), { width: 360,
        spec: i ? "" : "upward from the chip · w 320 · "
        + "a name 13 medium over its line 12 dim, 8 over and under, 12 in · ✓ on the accent's tint" })))),
    group(t, "The Modes panel", keep(g.modes.map(([name, chat], i) => specimen(t, `modes-${i}`, name,
      div().p(20).child(chat.modesPanel(t)), { width: 412, spec: i ? "" : "center-chat.html's Modes · w 372 · "
        + "icons 18 muted · slider 24 high, a stop 16, knob 14 · the level 76 at the end · switch 34 × 20" })))),
    group(t, "The / menu", keep(g.commands.map(([name, chat], i) => specimen(t, `commands-${i}`, name,
      div().p(20).child(chat.commandsPanel(t)), { width: COMMANDS + 40, spec: i ? "" : "over the prompt, its left "
        + "edge with the prompt's, 8 over it · w 520 · rows 32: 8 over and under a 16 line, 12 in, icons 16 muted, "
        + "a skill's Lucide's scroll-text · a line 12 muted · a source's tag 11, 16 high, raised, muted · a part's "
        + "first 5 · 384 at most, then it scrolls" }))))]),
    ...halves("chat-context", (keep) => [group(t, "The Context panel", keep(g.contexts.map(([name, chat], i) =>
      specimen(t, `context-${i}`, name, div().p(20).child(chat.contextPanel(t)), { width: CONTEXT + 40,
        spec: i ? "" : "upward from the meter, "
        + "left-aligned · w 430 · the bar 8 high in the Agent panel's colors: rules the accent, skills ansi6, "
        + "connectors ansi4, the rest muted; the legend 12 muted, a swatch 8 · links without an arrow" }))))]),
    ["chat-plan", () => [group(t, "The plan strip", g.plans.map(([name, chat, wide = CHAT], i) => specimen(t,
      `plan-${i}`, name, chat.bottom(t, CODE_FONT), { width: wide, spec: i ? "" : "plan-todo.html's · over the "
        + "prompt, 8 apart, radius 10 on the side's level · its head 34: the step at work with a spinner 12 in the "
        + "accent, the count 12 muted, a chevron · open: a row 26, done a check in done, to do a ring 10 in dim, "
        + "what it waits for 12 dim at its end" })).concat([specimen(t, "plan-timeline",
      "In the timeline: the plan approved, tasks added in one row, a step done", fixed(230,
        g.planned.timeline(t, CODE_FONT)), { width: CHAT })]))]],
    ["chat-cards", () => [group(t, "What Claude waits on", g.cards.map(([name, chat], i) => specimen(t, `card-${i}`,
      name, chat.bottom(t, CODE_FONT), { width: CHAT, spec: i ? "" : "in the prompt's place · a digit picks" })))]],
    ...halves("chat-timeline", (keep) => [group(t, "The chat's timeline", keep([specimen(t, "timeline",
      "A chat, a command waiting", fixed(360, g.chat.timeline(t, CODE_FONT)),
      { width: CHAT, spec: "a dot a step: done, failed ansi1, running accent, waiting ansi3 and fading" })])),
    group(t, "Connectors in the timeline", keep(g.connected.map(([name, chat], i) => specimen(t, `connected-${i}`,
      name, fixed(340, chat.timeline(t, CODE_FONT)), { width: CHAT, spec: i ? "" : "connectors.html's · a call: the "
        + "brand's logo 16, its name bold, the tool in the code font 12 muted, its first words dim · a sign-in: the "
        + "dot ansi3, Connect 24 high on the raised fill, radius 6 · signing in: a spinner 12 in the accent" }))))]),
    ["chat-new", () => [group(t, "A new chat", [
      specimen(t, "new-chat", "Nothing said yet: its agent's chip, the agent started by the first message",
        fixed(300, v_flex().size_full().child(g.fresh.welcome(t)).child(g.fresh.bottom(t, CODE_FONT))),
        { width: CHAT, spec: "15 semibold, 64 down · in the space · its branch, 12 dim · the chip as the mode's" }),
      specimen(t, "new-chat-agents", "Its chip's list: the installed, recent first, a terminal's, one not installed",
        popover(t, AGENT_LIST, menuHeight(g.agents.items, undefined, true), menuPopup(t, "", g.agents.items,
          undefined, g.agents.find)), { width: AGENT_LIST + 40,
          spec: "upward from the chip · a filter, typed into at once · ⏎ its first · terminal: no chat draws it · "
            + "sign in in ansi3 · not installed: under a rule, muted, it opens the Agent panel at how it installs" }),
    ])]]]],
    ["Patterns", [["panels", () => [group(t, "Panels", [
      specimen(t, "panel-changes", "Changes", stack("changes", g.changes.panel(t))),
      specimen(t, "panel-search", "Search", stack("search", g.search.panel(t))),
      specimen(t, "panel-issues", "Issues", stack("issues", g.issues.panel(t)),
        { spec: "one card: the row on top, a hairline, one view at a time; 12 inside on every side, as the terminal" }),
      specimen(t, "panel-pulls", "Issues, its switch on Pull requests", stack("issues", g.pulls.panel(t)),
        { spec: "Issues | Pull requests on the tab's top, a choice of two; the same field, Open and Closed, refresh" }),
    ])]]]],
  ];
}

/** The theme's colors by role, each with its token, value and use; the three levels with the contrast between each
 * and the next; the scope tags, raised and muted. */
function colors(t) {
  const swatch = (token, use) => v_flex().w(148).flex_none().gap(6)
    .child(div().h(56).rounded(8).bg(t[token] ?? t.background).border_1().border_color(t.border))
    .child(v_flex().gap(2).child(div().text_size(12).font_bold().child(token))
      .child(div().text_size(11).text_color(t.dim).child(String(t[token] ?? "")))
      .child(div().text_size(11).text_color(t.muted).child(use)));
  const row = (name, tokens) => v_flex().gap(12).child(div().text_size(12).text_color(t.muted).child(name))
    .child(h_flex().items_start().gap(16).children(tokens.map(([token, use]) => swatch(token, use))));
  const step = (a, b) => `${contrast(t[a], t[b]).toFixed(2)}:1`;
  const tags = ["Global", "Project", "code-review", "claude.ai", "Local"];
  return group(t, "Color", [v_flex().gap(24)
    .child(row("Levels", [["canvas", "The window"], ["chrome", "The side, the prompt"],
      ["surface", "Cards, popovers"], ["background", "Terminals, the TUI's"]]))
    .child(div().text_size(11).text_color(t.dim).child(`Each level parts from the next by 1.05 at least: canvas to `
      + `chrome ${step("canvas", "chrome")}, chrome to surface ${step("chrome", "surface")}`))
    .child(row("Controls", [["raised", "Buttons, chips, tags"], ["hover", "Under the mouse"],
      ["selected", "The chosen row"],
      ["selection", "Matches, the icon button"], ["border", "Frames, rules"]]))
    .child(v_flex().gap(12).child(div().text_size(12).text_color(t.muted).child("Scope tags, never in a hue"))
      .child(h_flex().flex_none().self_start().p(12).gap(8).rounded(10).bg(t.surface).border_1()
        .border_color(t.border).children(tags.map((word) => scopeTag(t, word)))))
    .child(h_flex().gap(48)
      .child(row("Text", [["foreground", "Body"], ["muted", "Icons, captions"], ["dim", "Folders, line numbers"]]))
      .child(row("Accent", [["accent", "Head, branches, the star"], ["solid", "Commit"],
        ["solid_foreground", "Words on solid"]])))
    .child(row("State", [["ansi2", "Added, untracked"], ["ansi3", "Modified"],
      ["ansi1", "Deleted, conflict, errors"]]))]);
}

/** The type scale: each style's specimen and its size and weight, and the icons'. */
function type(t) {
  const line = (sample, spec, style) => h_flex().gap(24).items_baseline()
    .child(div().w(220).flex_none().child(style(div().child(sample))))
    .child(div().text_size(11).text_color(t.dim).child(spec));
  return group(t, "Type", [v_flex().gap(16)
    .child(line("Changes", "View name · 13 semibold", (e) => e.text_size(13).font_semibold()))
    .child(line("Staged changes", "Section · 13 bold", (e) => e.text_size(13).font_bold()))
    .child(line("books.py", "Body · 13 regular", (e) => e.text_size(13)))
    .child(line("Commit", "Button · 12 bold", (e) => e.text_size(12).font_bold()))
    .child(line("src/lumen/routes", "Meta · 11 regular, dim", (e) => e.text_size(11).text_color(t.dim)))
    .child(line("PAGE = 20", `Code · ${CODE_FONT} 13, the preview tab`,
      (e) => e.text_size(13).font_family(CODE_FONT)))
    .child(line("PAGE = 20", `Code · ${CODE_FONT} 11, a hit's file`, (e) => e.text_size(11).font_family(CODE_FONT)))
    .child(line(h_flex().gap(12).children(["refresh-cw", "plus", "sparkles", "check"].map((name) => icon(name))),
      "Icons · Lucide 14, 15 on a tab", (e) => e.text_color(t.muted)))]);
}

/** The spacing scale (parts.js's SPACE), each step a bar that wide, and the steps the views keep to. */
function spacing(t) {
  return group(t, "Spacing", [v_flex().gap(12)
    .child(h_flex().gap(16).items_end().children(SPACE.map((px) => v_flex().gap(6).items_center()
      .child(div().w(px).h(24).bg(t.accent)).child(div().text_size(11).text_color(t.dim)
        .child(String(px))))))
    .child(div().text_size(11).text_color(t.dim).child("4 between two buttons · 6 an icon and its words · 8 a row's " +
      "end · 12 inside a card, every side · 16 a list's start"))]);
}

/** Radii and heights, each shown at its size. */
function shape(t) {
  const radius = (px, use) => v_flex().w(110).gap(6).child(div().size(64).rounded(px).bg(t.raised)
    .border_1().border_color(t.border)).child(div().text_size(12).child(`${px}`))
    .child(div().text_size(11).text_color(t.dim).child(use));
  const height = (px, use) => h_flex().gap(16).items_center()
    .child(div().w(120).h(px).rounded(4).bg(t.raised).border_1().border_color(t.border))
    .child(div().w(40).text_size(12).child(`${px}`)).child(div().text_size(11).text_color(t.dim).child(use));
  return group(t, "Shape and size", [
    h_flex().gap(16).children([[10, "Panel"], [8, "Control"], [6, "Row"], [4, "Chip"]].map(([px, use]) =>
      radius(/** @type {number} */ (px), /** @type {string} */ (use)))),
    v_flex().gap(12).children([[48, "Issue"], [36, "Dock head, group head"], [32, "Control"], [28, "Tab"], [26, "Row"],
      [24, "Commit, hit"], [22, "Preview line"], [20, "A hit's file line"]].map(([px, use]) =>
      height(/** @type {number} */ (px), /** @type {string} */ (use))))]);
}

/** The icons as icons.js has them: the views' by name, Lucide's, and each file type's, Catppuccin Icons'. */
function icons(t) {
  const cell = (mark, name) => v_flex().w(88).h(68).flex_none().items_center().justify_center().gap(6)
    .rounded(8).bg(t.surface).border_1().border_color(t.border).child(mark)
    .child(div().w_full().px(4).text_size(10).text_color(t.dim).text_center().truncate().child(name));
  /** @type {Map<string, string[]>} */
  const types = new Map();
  for (const [ext, path] of Object.entries(BY_EXTENSION)) types.set(path, [...(types.get(path) ?? []), ext]);
  for (const [path, starts] of [...BY_NAME, [FILE, ["any other"]]]) types.set(path, [...(types.get(path) ?? []),
    .../** @type {string[]} */ (starts)]);
  const grid = (cells) => h_flex().flex_wrap().gap(8).children(cells);
  const names = /** @type {import("./icons.js").IconName[]} */ (Object.keys(ICONS));
  return [
    group(t, "Icons · Lucide", [grid(names.map((name) => cell(icon(name, 18), name)))]),
    group(t, "File types · Catppuccin Icons", [grid([...types].map(([path, exts]) =>
      cell(fileMark(path).size(22), exts.slice(0, 3).join(" "))))]),
  ];
}
