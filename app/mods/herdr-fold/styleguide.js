// @ts-check
// The mod's styleguide: its foundations, each component in each of its states and the panels they make, drawn by the
// views' own code from made-up states whose clicks go nowhere. herdr-app do herdr-fold.styleguide opens it.
import { div } from "gpui-kit";
import { v_flex, h_flex, InputState } from "gpui-base";
import { BY_EXTENSION, BY_NAME, FILE, ICONS } from "./icons.js";
import { commitRows, conversationRows, diffRows, foldedSections, listHeight, pushOffer, RAIL, searchRows }
  from "./logic.js";
import { ConversationsView } from "./conversations.js";
import { IssuesView } from "./issues.js";
import { button, chip, fileMark, icon, small, SPACE } from "./parts.js";
import { panelTabs, rail } from "./panel.js";
import { Menus, menuPopup } from "./menus.js";
import { Preview } from "./preview.js";
import { dock, floatHead, floatPanel, sidebarTrigger, spacesFloat } from "./sidebar.js";
import { FilesView } from "./files.js";
import { SpacesView } from "./spaces.js";
import { TabsView } from "./tabs.js";
import { standIn } from "./terminal.js";

const PANEL = 368;                  // a specimen as wide as the right panel
const TAB = 540;                    // a specimen of the preview tab, two side by side
const SIDEBAR = 268;                // a specimen as wide as the left sidebar
const PAGE = "mods/herdr-fold/styleguide-page.svg";      // a PDF's page, as the app's home names it
// what the views' clicks would do: nothing, here
const INERT = ["act", "change", "choose", "commit", "fold", "later", "pick", "refresh", "reveal", "search", "show",
  "submit", "sync", "unask", "unlink", "watch", "write"];
const INERT_ISSUES = ["act", "change", "filter", "load", "open", "terminal", "toAgent", "unask"];
const INERT_CONVERSATIONS = ["ask", "copy", "load", "look", "open", "pick", "rename", "watch"];

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
  "<h2>Query parameters</h2>", "<dl>", "  <dt><code>page</code></dt>", "  <dd>The page to serve.</dd>", "</dl>"]
  .map((text, i) => ({ kind: " ", number: i + 1, text }));
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
/** The Spaces list as its view draws GROUPS, MORE its drag. @param {any[]} groups */
const spacesList = (t, groups, more = {}) => Object.assign(Object.create(SpacesView.prototype),
  { pressed: null, over: null, machines: [], mending: new Set(), ...more }).draw(t, groups);
// the tab bar's tabs: the first named as its space, an agent working there (its icon tinted), one waiting on you, a
// shell, one done and zoomed
const BAR = [{ id: "t1", name: "lumen-api", active: true, status: "working", icon: ICONS.bot, tint: true },
  { id: "t2", name: "Codex", active: false, status: "blocked", icon: ICONS.bot, tint: true },
  { id: "t3", name: "Terminal", active: false, status: null, icon: null, tint: false },
  { id: "t4", name: "notes Z", active: false, status: "done", icon: null, tint: false }];
/** The tab bar as its view draws BAR, BUTTONS the window's own (null: macOS, the traffic lights' instead), the
 * pointer on HOVERED's tab. @param {any} buttons @param {string | null} hovered */
const tabBar = (t, buttons, hovered) => Object.assign(Object.create(TabsView.prototype), { pressed: null, hovered })
  .draw(t, BAR, "s1", { lights: 12, end: 12, buttons });
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
  return state;
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
    note: null, hidden: false, loading: false, menus: new Menus() }, fields);
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

let conversationViews = 0;            // each drawn list's own slides (ConversationsView.slides)

/** The Conversations block over TALKS with FIELDS (typed, a menu open, one renamed, the archived shown, loading). */
function conversationsOf(fields = {}) {
  const view = Object.assign(Object.create(ConversationsView.prototype), { slides: `${++conversationViews}-`,
    items: TALKS, loaded: true, note: null, archived: new Set(["claude:s9"]), typed: "",
    find: InputState.new({ placeholder: "Filter conversations" }), opened: new Set(), closed: new Set(), naming: null,
    programs: {} }, fields);
  if (view.typed) view.find.set_value(view.typed);
  view.naming?.input.set_value(view.naming.item.title);
  view.showsArchived = () => fields.showArchived === true;
  view.rows = () => conversationRows(view.items, ["lumen-api", "harbor-web"], PLACES, { typed: view.typed,
    archived: view.archived, showArchived: view.showsArchived(), opened: view.opened, closed: view.closed,
    here: "lumen-api", front: new Set(["t1"]), states: { "lumen-api": "blocked", "harbor-web": "idle" } });
  for (const name of INERT_CONVERSATIONS) view[name] = () => {};
  return view;
}

/** STATE's Issues view, listing LISTED, with FIELDS (filters, a row asked about, a menu open). */
function issuesOf(state, fields) {
  const issues = Object.assign(new IssuesView(state), { listing: LISTING }, fields);
  for (const name of INERT_ISSUES) issues[name] = () => {};
  return issues;
}

/** The preview tab with FIELDS: what it shows, loading, or why nothing. */
function previewOf(fields) {
  return Object.assign(new Preview("styleguide", null), { what: { n: 0, level: 1, ranked_by: "priority: high" } },
    fields);
}

/** The made-up states the components show, made once (what is typed in them stays). @param {any} proto */
export function guide(proto) {
  const at = (fields = {}) => made(proto, fields);
  const found = { total: 3, files: 2, hits: HITS, error: null };
  const nothing = { total: 0, files: 0, hits: [], error: null };
  return {
    base: at(),
    tabs: ["files", "search", "changes", "issues"].map((shown) => [`${shown[0].toUpperCase()}${shown.slice(1)} shown`,
      { shown, github: true, changed: CHANGED }]).concat([["Not on GitHub", { shown: "changes", github: false,
      changed: CHANGED }]]),
    repository: [["In sync", at({ status: { ...STATUS, ahead: 0, behind: 0 } })], ["Behind and ahead", at()],
      ["No upstream", at({ status: { ...STATUS, upstream: null } })],
      ["Folded", at({ folded: foldedSections(["repositories"]) })]],
    composer: [["Empty", at()], ["Filled", at({ message: MESSAGE })],
      ["Writing", at({ busy: "Claude is writing the message…", writing: "Claude is writing the message…" })],
      ["Asking", at({ message: MESSAGE, asked: [".env"] })],
      ["Commit & Push", at({ message: MESSAGE, mode: "push" })],
      ["Offering a push", at({ status: { ...STATUS, staged: [], changes: [] },
        offer: pushOffer({ ...STATUS, staged: [], changes: [] }) })],
      ["Fixes an issue", at({ message: MESSAGE, linked: [42, LISTED[0].title] })]],
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
    issueList: [["Loading", at({ issues: { listing: null, asked: "styleguide" } }), 120],
    ["Busy", at({ issues: { busy: "Sending…" } }), 120], ["Closed, none", at({ issues: { listing: { issues: [],
      error: null }, query: { state: "closed", assigned: false, authored: false, label: "" } } }), 120],
    ["Error", at({ issues: { listing: { issues: [], error: "gh is not signed in: run gh auth login" } } }), 120]],
    preview: [["Diff", previewOf({ rows: DIFF }), 200], ["Commit", previewOf({ rows: COMMIT }), 200],
      ["Loading", previewOf({ loading: true }), 52], ["Error", previewOf({ note: "HTTP 404: Not Found" }), 52],
      ["A PDF, scrolled to its second page", previewOf({ pdf: { sizes: Array(12).fill([612, 792]), count: 12,
        made: Array(12).fill(PAGE), range: null, making: false, page: 1 } }), 320],
      ...[["split", "A page, its code and picture"], ["code", "Its code alone"], ["picture", "Its picture alone"]]
        .map(([shown, name]) => [name, previewOf({ rows: HTML, picture: { png: PAGE }, shown }), 320])],
    issue: previewOf({ issue: ISSUE }),
    files: [["Default", filesOf()], ["A file chosen", filesOf({ picked: "src/lumen/app.py" })],
      ["A full folder", filesOf({ open: new Set(["src", "src/lumen", "src/lumen/routes"]) })],
      ["Hidden files shown", filesOf({ hidden: true, folders: HIDDEN_FOLDERS, open: new Set() })],
      ["No folder", filesOf({ root: null })]],
    fileEdits: [["A new file", filesOf({ naming: typing("new-file", "src/lumen", "client.py") })],
      ["Renamed in its row", filesOf({ naming: typing("rename", "src/lumen/store.py", "storage.py") })],
      ["A name taken", filesOf({ note: "already there: app.py" })],
      ["Move to Trash asked", filesOf({ asking: "src/lumen/pagination.py" })]],
    conversations: [["Default", conversationsOf()], ["Filtered", conversationsOf({ typed: "fix" })],
      ["Renaming", conversationsOf({
        naming: { key: "claude:s4", item: TALKS[3], input: InputState.new({ placeholder: TALKS[3].title }) } })],
      ["Archived shown", conversationsOf({ showArchived: true, opened: new Set(["harbor-web"]) })],
      ["Loading", conversationsOf({ loaded: false, items: [] })], ["None yet", conversationsOf({ items: [] })]],
    floating: conversationsOf({ overlay: "styleguide" }),
    problem: at({ note: "Sync stopped: pull first, nothing was lost" }),
    search: at({ view: "search", found, results: searchRows(HITS), searched: SEARCHED,
      peek: "src/lumen/routes/books.py:12", peekRows: PEEK }),
    changes: at({ message: MESSAGE, open: "staged:src/lumen/routes/books.py", hovered: "changes:docs/api.md" }),
    issues: at({ view: "issues", hovered: "issue-41", issues: { chosen: 42 } }),
  };
}

/** The styleguide page: Foundations, Components and Patterns; or only the part ONLY names, alone (its picture in
 * docs/styleguide.md). @param {ReturnType<typeof guide>} g @param {string | null} [only] */
export function styleguide(g, t, only = null) {
  const page = v_flex().id("styleguide").size_full().overflow_y_scrollbar().bg(t.canvas ?? t.background)
    .text_color(t.foreground).text_size(13);
  const parts = sections(g, t), body = v_flex().w_full().max_w(1400).px(48).py(40);
  const alone = parts.flatMap(([, items]) => items).find(([id]) => id === only);
  if (alone) return page.child(body.gap(40).children(alone[1]));
  return page.child(body.gap(64)
    .child(v_flex().gap(4).child(div().text_size(13).text_color(t.muted).child("herdr-fold"))
      .child(div().text_size(28).font_bold().child("Styleguide")))
    .children(parts.map(([title, items]) => v_flex().gap(40).child(div().text_size(20).font_bold().child(title))
      .children(items.flatMap(([, groups]) => groups)))));
}

/** A group of specimens under its name, side by side as room allows. */
function group(t, name, specimens) {
  return v_flex().gap(16).child(div().text_size(15).font_weight(700).text_color(t.foreground).child(name))
    .child(h_flex().flex_wrap().items_start().gap(24).children(specimens));
}

/** One specimen: CONTENT on the panel's own background, its state's NAME under it and what it is made of (SPEC); a
 * control (SMALL) at its own size in the middle of a stage of one height. */
function specimen(t, id, name, content, { width = PANEL, spec = "", small = false } = {}) {
  const stage = div().w_full().rounded(10).overflow_hidden().bg(t.background).border_1().border_color(t.border);
  return v_flex().id(id).w(width).flex_none().gap(8)
    .child(small ? stage.h(72).flex().items_center().justify_center().child(content) : stage.child(content))
    .child(v_flex().gap(2).child(div().text_size(12).child(name))
      .when(Boolean(spec), (e) => e.child(div().text_size(11).text_color(t.dim).child(spec))));
}

/** The page's parts, each [title, items], an item [id, groups]: the id names its picture. @param {ReturnType<typeof
 * guide>} g */
function sections(g, t) {
  const b = g.base;
  const fixed = (h, content) => div().h(h).flex().flex_col().child(content);
  // a view as the right panel's stack frames it, under the group's tabs
  const stack = (shown, view) => fixed(600, v_flex().size_full().rounded(10).overflow_hidden().border_1()
    .border_color(t.border).child(div().h(40).flex_none()
      .child(panelTabs(t, { shown, github: true, changed: CHANGED }))).child(view));
  const trees = (id, list, spec) => list.map(([name, view], i) => specimen(t, `${id}-${i}`, name,
    fixed(320, view.draw(t)), { spec: i ? "" : spec }));
  const [lucide, fileTypes] = icons(t);
  return [["Foundations", [["color", [colors(t)]], ["type", [type(t)]], ["shape", [spacing(t), shape(t)]],
    ["icons", [lucide]], ["file-types", [fileTypes]]]], ["Components", [
    ["buttons", [
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
    ["files", [group(t, "Files", trees("files", g.files,
      "h 26 a row · 12 a level · Catppuccin Icons' · git's colors"))]],
    ["file-edits", [group(t, "Files: a name typed in its row, Move to Trash asked", trees("file-edits", g.fileEdits,
      "typed in its row, as VS Code's · ⏎ makes it, esc drops it"))]],
    ["repository", [group(t, "Repository", g.repository.map(([name, state], i) => specimen(t, `repository-${i}`,
      name, state.repository(t), { spec: i ? "" : "as VS Code's Repositories · h 26 · ⋯ its menu" })))]],
    ["commit", [group(t, "Commit", g.composer.map(([name, state], i) => specimen(t, `composer-${i}`, name,
      state.composer(t))))]],
    ["tab-bar", [group(t, "Tab bar", [
      specimen(t, "tab-bar", "The space's tabs: the first named as the space, an agent working there, one waiting, "
        + "a shell under the pointer, one done",
        div().h(42).child(tabBar(t, null, "t3")),
        { width: 2 * PANEL, spec: "h 28 · px 12, 8 by the × · radius 6 · gap 4, 6 inside · × shown and on hover" }),
      specimen(t, "tab-bar-buttons", "Off macOS: the window's buttons",
        div().h(42).child(tabBar(t, { maximized: false }, null)),
        { width: 2 * PANEL, spec: "+ after the last tab · the panel's toggle, the window's own: tips to the left" }),
    ])]],
    ["tabs", [group(t, "Panel tabs", [...g.tabs.map(([name, state], i) => specimen(t, `tabs-${i}`, name,
        div().h(40).child(panelTabs(t, state)), { spec: i ? "" : "h 28 · radius 6 · gap 4 · the shown one raised" }))]),
      group(t, "Search field", g.query.map(([name, state], i) => specimen(t, `query-${i}`, name, state.query(t))))]],
    ["rail", [group(t, "The panel folded to its rail", [
        specimen(t, "rail-github", "On GitHub, with changes", div().w(RAIL).h(330).child(rail(t,
          { github: true, changed: 6 }, "t1")), { width: 120, spec: `w ${RAIL} · as the left sidebar folded` }),
        specimen(t, "rail-plain", "No GitHub, no terminal yet", div().w(RAIL).h(330).child(rail(t,
          { github: false, changed: 0 }, null)), { width: 120 }),
        specimen(t, "rail-float", "A view floating beside it", div().w(PANEL).child(floatHead(t, "Changes", "", [])),
          { spec: "as wide as the panel · its head drags it" })])]],
    ["sections", [
      group(t, "Section header", g.sections.map(([name, state], i) => specimen(t, `section-${i}`, name,
        div().p(6).child(state.section(t, "changes", "Changes", CHANGES)),
        { spec: i ? "" : "h 26 · 13 bold · chip" }))),
      group(t, "Count chip", [specimen(t, "chip", "Default", h_flex().gap(8).child(chip(t, "1")).child(chip(t, "12")),
        { width: 180, small: true, spec: "raised · px 6 · radius 4 · 11 semibold" })])]],
    ["rows", [group(t, "File row", g.rows.map(([name, kind, file, state], i) => specimen(t, `row-${i}`, name,
        div().p(6).child(state.file(t, kind, file)), { spec: i ? "" : "h 26 · icon, name, folder, letter" })))]],
    ["graph", [group(t, "Graph", g.graph.map(([name, state], i) => specimen(t, `graph-${i}`, name,
        fixed(state.folded.has("graph") ? 26 : 32 + COMMITS.length * 24, state.graph(t)))))]],
    ["menus", [group(t, "Menus", [["Commit's arrow", b.modes], ["The repository's ⋯", b.remote],
      ["Issues' filters", g.issues.issues.filters(t)], ["An issue's right click", b.issues.picks(LISTED[0])],
      ["A conversation's right click", g.conversations[0][1].choices(TALKS[3])],
      ["The list's right click", g.conversations[0][1].choices(null)]]
      .map(([name, items], i) => specimen(t, `menu-${i}`, name, div().p(20).child(div().w(180)
        .h(items.length * 30 + 8).rounded(8).border_1().border_color(t.border).bg(t.popover ?? t.raised)
        .child(menuPopup(t, "", items))),
      { width: 220, spec: i ? "" : "a popup under its button, right-aligned; a right click's at it" })))]],
    ["content", [
      group(t, "Problem", [specimen(t, "problem", "Under the Graph, until the next try", g.problem.problem(t),
        { spec: "11 · ansi1" })]),
      group(t, "Empty states", g.empty.map(([name, state], i) => specimen(t, `empty-${i}`, name,
        fixed(56, state.list(t)))))]],
    ["issues", [
      group(t, "Issue row", g.issueRows.map(([name, state, issue], i) => specimen(t, `issue-row-${i}`, name,
        div().p(6).child(state.issues.row(t, issue)),
        { spec: i ? "" : "h 48 · priority bar 3 · number in its color" })))]],
    ["issue-list", [group(t, "Issue list", g.issueList.map(([name, state, h], i) => specimen(t, `issue-list-${i}`,
      name, fixed(h, state.issues.render(t)))))]],
    ["preview", [group(t, "Preview tab", g.preview.map(([name, preview, h], i) => specimen(t, `preview-${i}`, name,
      fixed(h, preview.render(t, "Menlo")), { width: TAB, spec: i ? "" : "Menlo 13 · h 22 · numbered once" })))]],
    ["preview-issue", [group(t, "An issue in the preview tab", [specimen(t, "preview-issue", "Issue",
      fixed(330, g.issue.render(t, "Menlo")), { width: 2 * TAB + 24 })])]],
    ["spaces", [group(t, "Spaces", [
      specimen(t, "spaces-machines", "By machine, the waits beside the branch, lab's head hovered",
        fixed(listHeight(MACHINES), spacesList(t, MACHINES, { hovered: "lab" })),
        { width: SIDEBAR, spec: "h 32 a row · 28 a worktree's and a machine's · + on its hover · ansi3" }),
      specimen(t, "spaces-local", "This computer only", fixed(listHeight([LOCAL]), spacesList(t, [LOCAL])),
        { width: SIDEBAR }),
      specimen(t, "spaces-drag", "notes dragged over harbor-web", fixed(listHeight([LOCAL]), spacesList(t, [LOCAL],
        { pressed: "s3", over: "s2" })), { width: SIDEBAR, spec: "the line where it goes, between two rows" }),
      specimen(t, "spaces-loading", "Loading", fixed(listHeight([{ ...GROUP, machine: null, rows: [], loading: true }]),
        spacesList(t, [{ ...GROUP, machine: null, rows: [], loading: true }])), { width: SIDEBAR })])]],
    ["conversations", [group(t, "Conversations", [...g.conversations.map(([name, view], i) => specimen(t,
      `conversations-${i}`, name, fixed(260, view.list(t, view.rows())), { width: SIDEBAR,
        spec: i ? "" : "h 24 a row · a state's mark in herdr's colors" }))])]],
    ["sidebar-folded", [group(t, "The sidebar folded", [
      specimen(t, "conversations-dock", "A dock of its panels", fixed(260, dock(t, SPACES.map((space) => space.status),
        TALKS.map((talk) => talk.state), 300)), { width: 76 }),
      specimen(t, "spaces-float", "Spaces, floating beside it", spacesFloat(t, "", 160, SPACES, COLORS, WAITING),
        { width: 300 }),
      specimen(t, "conversations-float", "Conversations, floating beside it", floatPanel(t, "Conversations", "", 300,
        [], g.floating.list(t, g.floating.rows())), { width: 300, spec: "its head drags it · × closes it" }),
      specimen(t, "conversations-trigger", "Its toggle", div().w(40).h(42).child(sidebarTrigger(t)),
        { width: 120, small: true, spec: "left of the tabs" })])]],
    ["search", [group(t, "Search results", [specimen(t, "hits", "Hits, one shown at its line",
      fixed(300, v_flex().size_full().child(g.search.hits(t)).child(g.search.lines(t))))])]],
    ["terminal", [group(t, "The tab's terminal", [specimen(t, "terminal-none", "When it could not start",
      div().h(60).child(standIn(t, "No terminal: the machine is not reachable")),
      { spec: "12 · ansi1, in its place" })])]]]],
    ["Patterns", [["panels", [group(t, "Panels", [
      specimen(t, "panel-changes", "Changes", stack("changes", g.changes.panel(t))),
      specimen(t, "panel-search", "Search", stack("search", g.search.panel(t))),
      specimen(t, "panel-issues", "Issues", stack("issues", g.issues.panel(t))),
    ])]]]],
  ];
}

/** The theme's colors by role, each with its token, value and use. */
function colors(t) {
  const swatch = (token, use) => v_flex().w(148).flex_none().gap(6)
    .child(div().h(56).rounded(8).bg(t[token] ?? t.background).border_1().border_color(t.border))
    .child(v_flex().gap(2).child(div().text_size(12).font_bold().child(token))
      .child(div().text_size(11).text_color(t.dim).child(String(t[token] ?? "")))
      .child(div().text_size(11).text_color(t.muted).child(use)));
  const row = (name, tokens) => v_flex().gap(12).child(div().text_size(12).text_color(t.muted).child(name))
    .child(h_flex().gap(16).children(tokens.map(([token, use]) => swatch(token, use))));
  return group(t, "Color", [v_flex().gap(24)
    .child(row("Surface", [["background", "Panels, fields"], ["raised", "Buttons, chips"], ["hover", "Under the mouse"],
      ["selected", "The chosen row"], ["selection", "Matches, the icon button"], ["border", "Frames, rules"]]))
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
    .child(line("PAGE = 20", "Code · Menlo 13, the preview tab", (e) => e.text_size(13).font_family("Menlo")))
    .child(line("PAGE = 20", "Code · Menlo 11, a hit's file", (e) => e.text_size(11).font_family("Menlo")))
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
      "end · 12 inside a panel · 16 a list's start"))]);
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
    v_flex().gap(12).children([[48, "Issue"], [40, "Panel tabs"], [32, "Control"], [28, "Tab"], [26, "Row"],
      [24, "Commit, hit"], [22, "Preview line"], [20, "A hit's file line"]].map(([px, use]) =>
      height(/** @type {number} */ (px), /** @type {string} */ (use))))]);
}

/** The icons as icons.js has them: the views' by name, Lucide's, and each file type's, Catppuccin Icons'. */
function icons(t) {
  const cell = (mark, name) => v_flex().w(88).h(68).flex_none().items_center().justify_center().gap(6)
    .rounded(8).bg(t.background).border_1().border_color(t.border).child(mark)
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
