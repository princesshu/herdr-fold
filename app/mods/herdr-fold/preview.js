// @ts-check
// The preview tab, as the TUI sidebar's: one a space, showing what Files, Changes, the Graph or Issues opened in it (a
// file, a picture, a PDF's pages, a diff, a commit, an issue with its comments), herdr-fold's panel beside it.
import { div, image } from "gpui-kit";
import { v_flex, h_flex, Scrollbar, TextView, v_virtual_list } from "gpui-base";
import { home, panes, readTextFile, setShared, shared, spaces, run as command } from "herdr";
import { GIT, GITHUB, MEDIA } from "./helper.js";
import { commitRows, diffRows, mediaKind, previewName, previewTab, priorityColor, said, safeMarkdown }
  from "./logic.js";
import { chip, iconButton, small } from "./parts.js";

const PREVIEWS = "herdr-fold.previews";   // what each space's preview tab shows, by the space's id (shared)
const LINES = 1500;                       // a diff's or a file's lines shown at most
const PICTURE = 1600;                     // pixels: an image's or a PDF page's width as core/media.py makes it

/** WHAT in the shown space's preview tab, as the TUI sidebar opens it: that tab named for it and shown, else a new
 * one. @param {import("./logic.js").Shown} what */
export function showPreview(what) {
  const all = spaces(), space = all.find((s) => s.active);
  if (!space) return;
  const kept = /** @type {Record<string, any>} */ (shared(PREVIEWS) ?? {});
  const live = Object.fromEntries(Object.entries(kept).filter(([id]) => all.some((s) => s.id === id)));
  setShared(PREVIEWS, { ...live, [space.id]: { ...what, n: (kept[space.id]?.n ?? 0) + 1 } });
  const tab = previewTab(space, panes()), name = previewName(what);
  if (!tab) return void command("tab.new", { name, mod: "herdr-fold", props: { part: "preview", space: space.id } });
  command("tab.rename", { id: tab.id, name });
  command("tab.select", { id: tab.id });
}

export class Preview {
  /** SPACE's preview tab; CORE runs core/'s code where the repository is (main.js's python).
   * @param {string} space
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
  constructor(space, core) {
    this.space = space;
    this.core = core;
    /** @type {number | null} the space's request shown */
    this.n = null;
    /** @type {any} what it shows (a Shown, its request's number with it) */
    this.what = null;
    /** @type {import("./logic.js").Row[]} */
    this.rows = [];
    /** @type {{ issue: any, ago: string[] } | null} core/github.py's view of the issue */
    this.issue = null;
    /** @type {{ png: string, pages: number | null, page: number } | null} core/media.py's PNG, in the app's home */
    this.picture = null;
    this.loading = false;
    /** @type {string | null} why there is nothing to show */
    this.note = null;
  }

  /** From render: the space's latest request, asked for once it is new (after the render, as that redraws). */
  watch(cx) {
    const what = /** @type {any} */ (shared(PREVIEWS))?.[this.space];
    if (!what || what.n === this.n) return;
    this.n = what.n;
    cx.timer.after(0, (cx) => this.load(what, cx));
  }

  /** WHAT from its machine: a file, or from core/ a diff, a commit or an issue; an answer for an older one dropped. */
  load(what, cx) {
    Object.assign(this, { what, rows: [], issue: null, picture: null, loading: true, note: null });
    cx.spawn(async (cx) => {
      try {
        if (what.kind === "file" && ["image", "pdf"].includes(mediaKind(what.path) ?? "")) {
          if (what.on) return void (this.note = "A picture on another machine: only those on this Mac are shown");
          return void (await this.paint(what, 0));
        }
        if (what.kind === "file") {
          const text = await readTextFile(`${what.root}/${what.path}`, { on: what.on });
          if (what.n !== this.n) return;
          if (text === null) return void (this.note = "This file is no longer there");
          return void (this.rows = text.replace(/\n$/, "").split("\n").slice(0, LINES)
            .map((line, i) => ({ kind: " ", number: i + 1, text: line })));
        }
        if (what.kind === "issue") {
          const answer = await this.core(GITHUB, ["view", what.github, String(what.number)], what.root, what.on);
          if (what.n === this.n) Object.assign(this, { issue: answer.issue ? answer : null, note: answer.error });
          return;
        }
        const commit = what.kind === "commit";
        const { text, error } = await this.core(GIT, [commit ? "show" : "diff", what.root, commit ? what.hash
          : what.path], what.root, what.on);
        if (what.n !== this.n) return;
        if (commit) return void Object.assign(this, { rows: error ? [] : commitRows(text).slice(0, LINES),
          note: error });
        const lines = text.replace(/\n$/, "").split("\n"), hunk = lines.findIndex((l) => l.startsWith("@@"));
        Object.assign(this, hunk < 0 ? { note: error ?? "No text diff" }
          : { rows: diffRows(lines.slice(hunk, hunk + LINES)) });
      } catch (e) {
        if (what.n === this.n) this.note = said(e);
      } finally {
        if (what.n === this.n) this.loading = false;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** WHAT's PAGE (an image's only one) as a PNG made on this Mac (core/media.py), in the app's home. */
  async paint(what, page) {
    const path = `${what.root}/${what.path}`;
    const answer = await this.core(MEDIA, ["picture", path, String(page), String(PICTURE)], home(), null);
    if (what.n !== this.n) return;
    this.picture = answer.png ? { png: answer.png, pages: answer.pages, page } : null;
    this.note = answer.png ? null : "This picture cannot be shown";
  }

  /** The PDF STEP pages on, within it. */
  turn(step, cx) {
    const { what, picture } = this;
    const page = picture?.pages ? Math.max(0, Math.min(picture.pages - 1, picture.page + step)) : null;
    if (page === null || page === picture?.page) return;
    cx.spawn(async (cx) => {
      try {
        await this.paint(what, page);
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** The picture's file opened in the default browser (core/media.py). */
  browse(cx) {
    const { what } = this;
    cx.spawn(async (cx) => {
      try {
        const done = await this.core(MEDIA, ["open", `${what.root}/${what.path}`], home(), null);
        this.note = done.opened ? null : "No browser to open it in";
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** The issue, the picture, or the file's, diff's or commit's rows in CODE (the code's font); else what is happening
   * instead. */
  render(t, code) {
    const frame = v_flex().size_full().min_h(0).text_color(t.foreground).text_size(13);   // on the pane's own fill
    if (this.issue) return frame.child(this.issueView(t));
    if (this.picture) return frame.child(this.pictureView(t));
    if (this.rows.length) return frame.child(this.diff(t, code));
    const line = this.loading ? "Loading…" : this.note ?? (this.what ? "" : "Nothing chosen to preview");
    return frame.child(div().p(16).text_size(12).text_color(this.note ? t.ansi1 : t.dim).child(line));
  }

  /** The picture fitted to the tab, under a bar with a PDF's pages and Open in Browser. */
  pictureView(t) {
    const { png, pages, page } = /** @type {NonNullable<Preview["picture"]>} */ (this.picture);
    return v_flex().size_full().min_h(0)
      .child(h_flex().h(40).flex_none().px(12).gap(4).items_center().border_b(1).border_color(t.border)
        .when(Boolean(pages), (e) => e
          .child(small(t, "page-back", "Previous", "Previous page", page > 0, (cx) => this.turn(-1, cx)))
          .child(div().px(6).text_size(12).text_color(t.muted).child(`${page + 1} of ${pages}`))
          .child(small(t, "page-on", "Next", "Next page", page + 1 < (pages ?? 1), (cx) => this.turn(1, cx))))
        .child(div().flex_1())
        .child(iconButton(t, "browse", "external-link", "Open in Browser", (cx) => this.browse(cx), { left: true })))
      .child(div().flex_1().min_h(0).p(16).child(image(png).size_full()))
      .when(Boolean(this.note), (e) => e.child(div().px(16).pb(12).text_size(12).text_color(t.ansi1)
        .child(this.note ?? "")));
  }

  /** The rows: a commit's file names as headings, a thin rule where lines are left out between two changes. */
  diff(t, code) {
    const row = ({ kind, number, text }) => kind === "@"
      ? div().w_full().px(16).h(22).flex_none().flex().items_center().truncate().bg(t.raised).font_bold().child(text)
      : kind === "gap" ? div().w_full().h(22).flex_none().flex().items_center().px(16)
        .child(div().w_full().h(1).bg(t.border))
      : h_flex().w_full().h(22).flex_none().gap(16)
        .when(kind === "+", (e) => e.bg(t.ansi2 + "18")).when(kind === "-", (e) => e.bg(t.ansi1 + "18"))
        .child(div().w(44).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
        .child(div().flex_1().min_w(0).truncate().child(text));
    return div().flex_1().min_h(0).relative().font_family(code)
      .child(v_virtual_list("diff", this.rows.length, 22, (i) => String(i),
        (range) => this.rows.slice(range.start, range.end).map(row)).size_full())
      .child(Scrollbar.vertical("diff").viewport_from_layout().absolute().inset_0());
  }

  /** The issue as gh shows it: its number in its priority's color and its title, its state, who wrote it and when, its
   * labels; its text and comments as markdown (safe: no image fetched, no HTML). */
  issueView(t) {
    const { issue, ago } = /** @type {{ issue: any, ago: string[] }} */ (this.issue), what = this.what;
    const closed = issue.state === "CLOSED", color = closed ? t.muted : priorityColor(t, what.level);
    const text = (markdown, n) => TextView.markdown(`issue-${what.n}-${n}`, safeMarkdown(markdown)).selectable();
    return v_flex().id("issue").flex_1().min_h(0).overflow_y_scrollbar().child(v_flex().w_full().max_w(860).px(24)
      .py(20).gap(16)
      .child(h_flex().gap(12).items_start().text_size(20)
        .child(div().flex_none().font_bold().text_color(color).child(`#${issue.number}`))
        .child(div().flex_1().min_w(0).font_semibold().child(issue.title)))
      .child(h_flex().flex_wrap().gap(8).items_center().text_size(12).text_color(t.dim)
        .child(chip(t, closed ? "Closed" : "Open")).child([issue.author, ago[0]].filter(Boolean).join(" · "))
        .children(issue.labels.map((label) => div().text_color(label === what.ranked_by ? color : t.muted)
          .child(label))))
      .child(issue.body.trim() ? text(issue.body, 0) : div().text_color(t.dim).child("No description"))
      .children(issue.comments.map((c, n) => v_flex().gap(6).pt(16).border_t(1).border_color(t.border)
        .child(div().text_size(12).text_color(t.dim).child([c.author, ago[n + 1]].filter(Boolean).join(" · ")))
        .child(text(c.body, n + 1)))));
  }
}
