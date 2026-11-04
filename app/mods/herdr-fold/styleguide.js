// @ts-check
// The mod's styleguide: its foundations, each component in each of its states and the panels they make, drawn by the
// views' own code from made-up states whose clicks go nowhere. herdr-app do herdr-fold.styleguide opens it.
import { div } from "gpui-kit";
import { v_flex, h_flex, InputState } from "gpui-base";
import { home, terminals } from "herdr";
import { BY_EXTENSION, NERD, PLAIN } from "./icons.js";
import { diffRows, foldedSections, marks, searchRows } from "./logic.js";
import { button, chip, glyph, small } from "./parts.js";
import { TerminalHeader } from "./terminal.js";

const PANEL = 368;                  // a specimen as wide as the right panel
// what the views' clicks would do: nothing, here
const INERT = ["act", "change", "choose", "commit", "fold", "later", "load", "pick", "refresh", "reveal", "search",
  "show", "sync", "unask", "watch", "write"];

const STAGED = [{ path: "src/lumen/routes/books.py", code: "M" }];
const CHANGES = [{ path: "docs/api.md", code: "M" }, { path: "src/lumen/pagination.py", code: "?" },
  { path: "src/lumen/store.py", code: "U" }, { path: "tests/test_shelves.py", code: "D" }];
const STATUS = { upstream: "origin/main", ahead: 2, behind: 1, staged: STAGED, changes: CHANGES };
const COMMITS = [
  { hash: "4f1c2ab", subject: "refactor(store): keep books in the order added", author: "Ada", refs: ["main"],
    head: true },
  { hash: "9e8d7c6", subject: "test(shelves): cover an empty shelf", author: "Ada", refs: ["origin/main"],
    head: false },
  { hash: "1a2b3c4", subject: "fix(errors): answer with problem details", author: "Lin", refs: [], head: false }];
const DIFF = diffRows(["@@ -1,4 +1,5 @@", ' """GET /books: the books, by title."""', "-PAGE = 10", "+PAGE = 20",
  "+LAST = None", " from .. import store"]);
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
 * @param {any} proto @param {string | null} font @param {Record<string, any>} fields */
function made(proto, font, fields = {}) {
  const state = Object.assign(Object.create(proto), {
    font, m: marks(font), view: "changes", root: "/work/lumen-api", on: null, key: "styleguide", status: STATUS,
    rows: DIFF, commits: COMMITS, message: "", busy: null, asked: null, confirm: null, open: null, hovered: null,
    menu: false, mode: "commit", folded: foldedSections([]), note: null, loading: false, searching: false,
    switches: { case: false, word: false, regex: false }, found: null, searched: null, results: [], peek: null,
    peekRows: [], input: InputState.new({ placeholder: "Commit message" }),
    find: InputState.new({ placeholder: "Search" }),
  }, fields);
  for (const name of INERT) state[name] = () => {};
  if (state.message) state.input.set_value(state.message);
  return state;
}

/** The made-up states the components show, made once (what is typed in them stays), their icons in FONT (a Nerd
 * Font, or null). @param {any} proto @param {string | null} font */
export function guide(proto, font) {
  const at = (fields = {}, own = font) => made(proto, own, fields);
  const found = { total: 3, files: 2, hits: HITS, error: null };
  const nothing = { total: 0, files: 0, hits: [], error: null };
  return {
    font,
    base: at(),
    plain: at({}, null),
    header: [["Changes selected", at()], ["Search selected", at({ view: "search" })],
      ["No upstream", at({ status: { ...STATUS, upstream: null } })], ["Busy", at({ busy: "Syncing…" })]],
    composer: [["Empty", at()], ["Filled", at({ message: MESSAGE })], ["Busy", at({ busy: "Writing the message…" })],
      ["Asking", at({ message: MESSAGE, asked: [".env"] })], ["Mode menu open", at({ message: MESSAGE, menu: true })],
      ["Commit & Push", at({ message: MESSAGE, mode: "push" })]],
    sections: [["Default", at()], ["Hover", at({ hovered: "section-changes" })],
      ["Asking", at({ confirm: "section-changes" })], ["Folded", at({ folded: foldedSections(["changes"]) })]],
    rows: [["Default", "changes", CHANGES[0], at()], ["Hover", "changes", CHANGES[0],
      at({ hovered: "changes:docs/api.md" })], ["Selected", "staged", STAGED[0],
      at({ open: "staged:src/lumen/routes/books.py" })], ["Untracked", "changes", CHANGES[1], at()],
    ["Conflict", "changes", CHANGES[2], at()], ["Deleted", "changes", CHANGES[3], at()],
    ["Asking", "changes", CHANGES[1], at({ confirm: "changes:src/lumen/pagination.py" })],
    ["Plain marks", "changes", CHANGES[0], at({ hovered: "changes:docs/api.md" }, null)]],
    graph: [["Default", at()], ["Selected", at({ open: "commit:9e8d7c6" })],
      ["Folded", at({ folded: foldedSections(["graph"]) })]],
    empty: [["Loading", at({ status: null, loading: true })],
      ["Nothing to commit", at({ status: { ...STATUS, staged: [], changes: [] } })],
      ["Not a repository", at({ root: null, status: null, note: "Not a git repository" })]],
    query: [["Default", at({ view: "search", found, searched: SEARCHED })],
      ["Switches on, busy", at({ view: "search", searching: true,
        switches: { case: true, word: true, regex: false } })],
      ["No results", at({ view: "search", found: nothing, searched: SEARCHED })],
      ["Error", at({ view: "search", found: { ...nothing, error: "invalid regex: (" }, searched: SEARCHED })]],
    problem: at({ note: "Sync stopped: pull first, nothing was lost" }),
    search: at({ view: "search", found, results: searchRows(HITS), searched: SEARCHED,
      peek: "src/lumen/routes/books.py:12", peekRows: PEEK }),
    changes: at({ message: MESSAGE, open: "staged:src/lumen/routes/books.py", hovered: "changes:docs/api.md" }),
  };
}

/** The styleguide page: Foundations, Components and Patterns; or only the part ONLY names, alone (its picture in
 * docs/styleguide.md). @param {ReturnType<typeof guide>} g @param {string | null} [only] */
export function styleguide(g, t, only = null) {
  const page = v_flex().id("styleguide").size_full().overflow_y_scrollbar().bg(t.canvas ?? t.background)
    .text_color(t.foreground).text_size(13);
  const parts = sections(g, t), body = v_flex().w_full().max_w(1400).px(48).py(40);
  const alone = parts.flatMap(([, items]) => items).find(([id]) => id === only);
  if (alone) return page.child(body.gap(36).children(alone[1]));
  return page.child(body.gap(64)
    .child(v_flex().gap(4).child(div().text_size(13).text_color(t.muted).child("herdr-fold"))
      .child(div().text_size(28).font_bold().child("Styleguide")))
    .children(parts.map(([title, items]) => v_flex().gap(36).child(div().text_size(20).font_bold().child(title))
      .children(items.flatMap(([, groups]) => groups)))));
}

/** A group of specimens under its name, side by side as room allows. */
function group(t, name, specimens) {
  return v_flex().gap(14).child(div().text_size(15).font_weight(700).text_color(t.foreground).child(name))
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
  const font = g.font, m = marks(font), b = g.base;
  const fixed = (h, content) => div().h(h).flex().flex_col().child(content);
  const [codicons, plainMarks, fileTypes] = icons(t, font);
  return [["Foundations", [["color", [colors(t)]], ["type", [type(t, font), shape(t)]],
    ["icons", [codicons, plainMarks]], ["file-types", [fileTypes]]]], ["Components", [
    ["buttons", [
      group(t, "Buttons", [
        specimen(t, "b-primary", "Primary", button(t, "s-commit", h_flex().gap(8).items_center()
          .child(glyph(font, m.check)).child("Commit"), true, true, () => {}), { width: 180, small: true,
          spec: "solid · h 32 · radius 8 · 12 bold" }),
        specimen(t, "b-primary-busy", "Primary, busy", button(t, "s-busy", "Committing…", false, true, () => {}),
          { width: 180, small: true, spec: "the work's name in place" }),
        specimen(t, "b-secondary", "Secondary", button(t, "s-sync", h_flex().gap(6).items_center()
          .child(glyph(font, m.refresh)).child("1↓ 2↑"), true, false, () => {}), { width: 180, small: true,
          spec: "raised · h 32 · radius 8 · 12 bold" }),
        specimen(t, "b-disabled", "Secondary, disabled", button(t, "s-off", h_flex().gap(6).items_center()
          .child(glyph(font, m.refresh)).child("1↓ 2↑"), false, false, () => {}), { width: 180, small: true,
          spec: "dim words, no pointer" }),
        specimen(t, "b-icon", "Icon", button(t, "s-write", glyph(font, m.ai).text_size(15), true, false, () => {})
          .bg(t.selection).text_color(t.accent), { width: 180, small: true, spec: "selection · accent icon" }),
        specimen(t, "b-row", "Row buttons", h_flex().gap(4)
          .child(small(t, "s-discard", glyph(font, m.discard), "Discard changes", true, () => {}))
          .child(small(t, "s-stage", glyph(font, m.stage), "Stage", true, () => {}))
          .child(small(t, "s-unstage", glyph(font, m.unstage), "Unstage", true, () => {}))
          .child(small(t, "s-confirm", "Discard", "Discard changes", true, () => {})),
        { width: 180, small: true, spec: "h 20 · radius 5 · raised on hover" }),
      ])]],
    ["commit", [group(t, "Commit", g.composer.map(([name, state], i) =>
      specimen(t, `composer-${i}`, name, state.composer(t))))]],
    ["tabs", [group(t, "View tabs and sync", g.header.map(([name, state], i) =>
        specimen(t, `header-${i}`, name, state.header(t)))),
      group(t, "Search field", g.query.map(([name, state], i) => specimen(t, `query-${i}`, name, state.query(t))))]],
    ["sections", [
      group(t, "Section header", g.sections.map(([name, state], i) => specimen(t, `section-${i}`, name,
        div().p(6).child(state.section(t, "changes", "Changes", CHANGES)),
        { spec: i ? "" : "h 26 · 13 bold · chip" }))),
      group(t, "Count chip", [specimen(t, "chip", "Default", h_flex().gap(8).child(chip(t, "1")).child(chip(t, "12")),
        { width: 180, small: true, spec: "raised · radius 5 · 11 semibold" })])]],
    ["rows", [group(t, "File row", g.rows.map(([name, kind, file, state], i) => specimen(t, `row-${i}`, name,
        div().p(6).child(state.file(t, kind, file)), { spec: i ? "" : "h 26 · icon, name, folder, letter" })))]],
    ["graph", [group(t, "Graph", g.graph.map(([name, state], i) => specimen(t, `graph-${i}`, name, state.graph(t)))),
      group(t, "Mode menu", [specimen(t, "modes", "Open", div().p(10).child(b.modes(t)))])]],
    ["content", [
      group(t, "Diff and problem", [specimen(t, "diff", "Hunk, removed, added, context; a problem under it",
        fixed(176, v_flex().size_full().child(b.diff(t)).child(g.problem.problem(t))), { spec: "Menlo 11 · h 20" })]),
      group(t, "Empty states", g.empty.map(([name, state], i) => specimen(t, `empty-${i}`, name,
        fixed(56, state.list(t)))))]],
    ["search", [group(t, "Search results", [specimen(t, "hits", "Hits, one shown at its line",
      fixed(300, v_flex().size_full().child(g.search.hits(t)).child(g.search.lines(t))))])]],
    ["terminal", [group(t, "The tab's terminal", terminalStates(t).map(([name, header], i) =>
      specimen(t, `terminal-${i}`, name, div().h(30).child(header),
        { spec: i ? "" : "h 30 · as the app's pane header" })))]]]],
    ["Patterns", [["panels", [group(t, "Panels", [
      specimen(t, "panel-changes", "Changes", fixed(600, g.changes.panel(t))),
      specimen(t, "panel-search", "Search", fixed(600, g.search.panel(t))),
      specimen(t, "panel-plain", "Changes, plain marks", fixed(600, g.plain.panel(t))),
    ])]]]],
  ];
}

/** The theme's colors by role, each with its token, value and use. */
function colors(t) {
  const swatch = (token, use) => v_flex().w(148).flex_none().gap(6)
    .child(div().h(56).rounded(8).bg(t[token] ?? t.background).border_1().border_color(t.border))
    .child(v_flex().gap(1).child(div().text_size(12).font_bold().child(token))
      .child(div().text_size(11).text_color(t.dim).child(String(t[token] ?? "")))
      .child(div().text_size(11).text_color(t.muted).child(use)));
  const row = (name, tokens) => v_flex().gap(10).child(div().text_size(12).text_color(t.muted).child(name))
    .child(h_flex().gap(16).children(tokens.map(([token, use]) => swatch(token, use))));
  return group(t, "Color", [v_flex().gap(24)
    .child(row("Surface", [["background", "Panels, fields"], ["raised", "Buttons, chips"], ["hover", "Under the mouse"],
      ["selected", "The chosen row"], ["selection", "Matches, the icon button"], ["border", "Frames, rules"]]))
    .child(h_flex().gap(48)
      .child(row("Text", [["foreground", "Body"], ["muted", "Icons, captions"], ["dim", "Folders, line numbers"]]))
      .child(row("Accent", [["accent", "Head, branches, the star"], ["solid", "Commit"],
        ["solid_foreground", "Words on solid"]])))
    .child(row("State", [["ansi2", "Added, untracked"], ["blocked", "Modified"],
      ["ansi1", "Deleted, conflict, errors"]]))]);
}

/** The type scale: each style's specimen and its size and weight. @param {string | null} font */
function type(t, font) {
  const m = marks(font);
  const line = (sample, spec, style) => h_flex().gap(24).items_baseline()
    .child(div().w(220).flex_none().child(style(div().child(sample))))
    .child(div().text_size(11).text_color(t.dim).child(spec));
  return group(t, "Type", [v_flex().gap(14)
    .child(line("Changes", "View name · 13 semibold", (e) => e.text_size(13).font_semibold()))
    .child(line("Staged changes", "Section · 13 bold", (e) => e.text_size(13).font_bold()))
    .child(line("books.py", "Body · 13 regular", (e) => e.text_size(13)))
    .child(line("Commit", "Button · 12 bold", (e) => e.text_size(12).font_bold()))
    .child(line("src/lumen/routes", "Meta · 11 regular, dim", (e) => e.text_size(11).text_color(t.dim)))
    .child(line("PAGE = 20", "Code · Menlo 11", (e) => e.text_size(11).font_family("Menlo")))
    .child(line([m.files, m.search, m.git, m.stage, m.ai].join("  "), font ? `Icons · ${font}, 13`
      : "Icons · plain marks, without a Nerd Font", (e) => e.text_size(13).text_color(t.muted)
      .when(Boolean(font), (e) => e.font_family(/** @type {string} */ (font)))))]);
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
    h_flex().gap(16).children([[10, "Panel"], [8, "Control"], [6, "Row"], [5, "Chip"]].map(([px, use]) =>
      radius(/** @type {number} */ (px), /** @type {string} */ (use)))),
    v_flex().gap(10).children([[46, "Header"], [32, "Control"], [30, "Terminal header"], [26, "Row"],
      [24, "Commit, hit"], [20, "Diff line"]].map(([px, use]) =>
      height(/** @type {number} */ (px), /** @type {string} */ (use))))]);
}

/** The icons as icons.js has them: the Codicons by name in FONT, the plain marks, each file type's.
 * @param {string | null} font */
function icons(t, font) {
  const cell = (mark, name, inFont) => v_flex().w(88).h(68).flex_none().items_center().justify_center().gap(6)
    .rounded(8).bg(t.background).border_1().border_color(t.border)
    .child(div().text_size(18).when(Boolean(inFont), (e) => e.font_family(/** @type {string} */ (inFont))).child(mark))
    .child(div().w_full().px(4).text_size(10).text_color(t.dim).text_center().truncate().child(name));
  /** @type {Map<string, string[]>} */
  const types = new Map();
  for (const [ext, glyph] of Object.entries(BY_EXTENSION)) types.set(glyph, [...(types.get(glyph) ?? []), ext]);
  const grid = (cells) => h_flex().flex_wrap().gap(8).children(cells);
  return [
    group(t, font ? `Codicons · ${font}` : "Codicons · no Nerd Font installed", font
      ? [grid(Object.entries(NERD).map(([name, mark]) => cell(mark, name, font)))]
      : [div().text_color(t.dim).child("Install a Nerd Font to see them; the plain marks below stand in.")]),
    group(t, "Plain marks", [grid(Object.entries(PLAIN).map(([name, mark]) => cell(mark, name, null)))]),
    group(t, "File types", font ? [grid([...types].map(([mark, exts]) => cell(mark, exts.slice(0, 3).join(" "), font)))]
      : []),
  ];
}

/** The tab's terminal header in each state: starting, shown, could not start. */
function terminalStates(t) {
  const starting = Object.assign(new TerminalHeader(), { starting: true });
  const failed = Object.assign(new TerminalHeader(), { note: "No terminal: the machine is not reachable" });
  const program = terminals().find((x) => x.program?.icon)?.program ?? { name: "zsh", icon: null };
  const shown = { address: "t1", program, cwd: `${home()}/work/lumen-api` };
  return [["Starting", starting.render(t)], ["Shown", new TerminalHeader().render(t, shown)],
    ["Error", failed.render(t)]];
}
