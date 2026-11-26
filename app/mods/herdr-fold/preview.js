// @ts-check
// The preview tab, as the TUI sidebar's: one a space, showing a picture, a clip (an agent's with where it came from), a
// PDF, a page, an SVG or Markdown, a diff, a commit, an issue or a review (review.js); a text file opens in the editor.
import { div, image } from "gpui-kit";
import { v_flex, h_flex, h_resizable, resizable_panel, Scrollbar, TextView, v_resizable, v_virtual_list }
  from "gpui-base";
import { hc, home, panes, playSound, setShared, shared, spaces, terminals, window, run as command } from "herdr";
import { Editing, openEditor } from "./editor.js";
import { CONNECTORS, GIT, GITHUB, MEDIA, MEDIA_SERVICES, NAMED_FILES, OUTPUT_LINES, RUNS } from "./helper.js";
import { BRANDS } from "./icons.js";
import { browsable, CHAT_LABEL, CHAT_TAB, changeSides, clipTime, commitRows, diffRows, editsInTab, lastLine,
  markdownFile, mediaKind, opener, previewName, previewTab, priorityColor, said, safeMarkdown, stacks }
  from "./logic.js";
import { Menus } from "./menus.js";
import { Review } from "./review.js";
import { actButton, chip, choices, icon, iconButton, keepNote, small, viewId } from "./parts.js";

const PREVIEWS = "herdr-fold.previews";   // what each space's preview tab shows, by the space's id (shared)
const LINES = 1500;                       // a diff's or a commit's lines shown at most
const PICTURE = 1600;                     // pixels: an image's or a PDF page's width as core/media.py makes it
const GAP = 16;                           // px between two of a PDF's pages, as the TUI's row
const MARGIN = 32;                        // px each side of a PDF's page: its air, the scrollbar's room on the right
const INSET = 24;                         // px of the board round a picture
const FIT = 250;                          // ms the board's size stays before an SVG or a page is drawn for it
const TICK = 200;                         // ms between two looks at the PDF's pages in view
const NAMED = 360;                        // px: Cmd+Shift+L's list of files, a path and its line
const LABEL = 72;                         // px: the label column of where a picture or a clip came from
const BARS = 80;                          // audio's waveform's bars, each its steps' loudest
/** @type {[string, string][]} a page's, an SVG's or Markdown's views: its code, both side by side, its picture */
const VIEWS = [["code", "Code"], ["split", "Split"], ["picture", "Picture"]];

/** WHAT in the shown space's preview tab, as the TUI sidebar opens it: that tab named for it and shown, else a new
 * one; a text file in an editor tab. @param {import("./logic.js").Shown} what */
export function showPreview(what) {
  if (what.kind === "file" && editsInTab(what.path)) return openEditor(what);
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

/** Cmd+Shift+L, as the TUI's: the files the focused terminal's recent rows name that are there (core/named_files.py
 * on its machine; CORE: main.js's python), the newest first, in a list at the window's top that typing narrows; one
 * picked in the preview tab at its line. @param {import("./menus.js").Menus} menus the tab bar's, hearing the pick */
export async function openNamed(core, menus) {
  const pane = panes().find((p) => p.focused && p.terminal);
  if (!pane?.terminal || !pane.cwd) return;
  const on = spaces().find((s) => s.active)?.machine ?? null;
  const read = await hc(["read", pane.terminal, "--lines", String(OUTPUT_LINES)]);
  const { files } = await core(NAMED_FILES, [pane.cwd, read.stdout ?? ""], pane.cwd, on);
  const items = files.map((/** @type {{ path: string, line: number | null, name: string }} */ file) => ({
    label: file.name, act: () => showPreview({ kind: "file", root: file.path.slice(0, file.path.lastIndexOf("/")),
      path: file.path.slice(file.path.lastIndexOf("/") + 1), on, ...(file.line ? { line: file.line } : {}) }) }));
  menus.atTop(items.length ? items : [{ label: "No file named in the output", off: true }],
    { width: NAMED, ...(items.length ? { find: "Filter files" } : {}) });
}

/** PICTURE ({ png, size }: core/media.py's) on the canvas, as a design tool's artboard: sized to the room, never
 * larger than it is, centered, the room round it the canvas's color. */
function artboard(t, id, picture) {
  const { png = null, size = null } = picture ?? {};
  return div().id(id).flex_1().min_h(0).relative().bg(t.canvas)
    .when(Boolean(png), (e) => e.child(div().absolute().inset(INSET).flex().items_center().justify_center()
      .child(image(String(png)).size_full().when(Boolean(size), (e) => e.max_w(size?.[0] ?? 0)
        .max_h(size?.[1] ?? 0)))));
}

/** The shown space's preview tab, or null (Files offers Close Preview while there is one). */
export function shownPreviewTab() {
  return previewTab(spaces().find((s) => s.active), panes());
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
    /** @type {Review | null} a pull request's review */
    this.review = null;
    /** @type {{ png: string, size?: number[] | null } | null} core/media.py's PNG, in the app's home, and its size in
     * pixels */
    this.picture = null;
    /** @type {{ before: any, after: any } | null} a changed picture's last commit and file, each core/media.py's */
    this.change = null;
    /** @type {{ png: string | null, size: number[] | null, pixels: number[] | null, seconds: number | null,
     * levels: number[] | null } | null} audio's or a video's (core/media.py's): a video's frame, audio's levels */
    this.clip = null;
    /** @type {any} where an agent's picture or clip came from (core/runs.py's origin), its "brand" (connectors.py's) */
    this.origin = null;
    /** @type {number | null} when its audio began to play (ms), while it plays */
    this.played = null;
    /** @type {any} the ticks that light its waveform meanwhile */
    this.playing = null;
    /** @type {{ note: import("./parts.js").Note | null }} what a button under a picture or a clip did */
    this.done = { note: null };
    /** @type {{ sizes: number[][], count: number | null, made: (string | undefined)[], range: any, making: boolean,
     * page: number, room: number | null } | null} a PDF's pages: each one's size in points, its PNG once made ("" where
     * it cannot be); the list's width (logical px) once it is known */
    this.pdf = null;
    /** @type {any} the ticks that make the PDF's pages in view */
    this.ticking = null;
    /** @type {Editing | null} a page's, an SVG's or Markdown's code, in the editor */
    this.editing = null;
    /** an SVG or a page on this Mac, drawn for the board's size once it is known */
    this.drawing = false;
    /** Markdown, drawn beside its code */
    this.markdown = false;
    /** @type {{ width: number, height: number } | null} the board's size the picture was drawn for */
    this.drawnFor = null;
    /** @type {{ width: number, height: number } | null} the board's size as last laid out */
    this.board = null;
    /** @type {any} the wait before it is drawn for a new size */
    this.fitting = null;
    /** an SVG's or a page's view (VIEWS'), kept for the next one */
    this.shown = "split";
    /** @type {boolean | null} its code above its picture, as chosen (kept for the next one); null: by the room */
    this.stacked = null;
    /** @type {{ width: number, height: number } | null} the room the two share, as last measured */
    this.room = null;
    this.loading = false;
    this.menus = new Menus();                     // its right click's
    /** @type {string | null} why there is nothing to show */
    this.note = null;
  }

  /** From render: the space's latest request, asked for once it is new (after the render, as that redraws). */
  watch(cx) {
    if (this.pdf && !this.ticking) this.ticking = cx.timer.every(TICK, (cx) => this.tick(cx));
    const what = /** @type {any} */ (shared(PREVIEWS))?.[this.space];
    if (!what || what.n === this.n) return;
    this.n = what.n;
    cx.timer.after(0, (cx) => this.load(what, cx));
  }

  /** WHAT from its machine: a file, or from core/ a diff, a commit, an issue or a pull request; an answer for an older
   * one dropped. */
  load(what, cx) {
    this.ticking?.cancel();
    this.fitting?.cancel();
    this.editing?.release();
    this.playing?.cancel();
    Object.assign(this, { what, rows: [], issue: null, review: null, picture: null, change: null, pdf: null,
      ticking: null, editing: null, drawing: false, markdown: false, drawnFor: null, fitting: null, loading: true,
      note: null, clip: null, origin: null, played: null, playing: null, done: { note: null } });
    cx.spawn(async (cx) => {
      try {
        const kind = what.kind === "file" ? mediaKind(what.path) ?? "" : "";
        if (["image", "pdf", "audio", "video"].includes(kind)) {
          const clip = kind === "audio" || kind === "video";
          if (what.on) return void (this.note = `${clip ? "A clip" : "A picture"} on another machine: only those `
            + "on this Mac are shown");
          await this.paint(what);
          if (kind !== "pdf") this.trace(what, cx);
          return;
        }
        if (what.kind === "file") {                // a page, an SVG or Markdown: its code in the editor, drawn beside
          const editing = (this.editing = new Editing(what, this.core, { space: this.space, tab: previewName(what),
            saved: (cx) => this.drawAgain(cx) }));
          await editing.load(cx);
          if (what.n !== this.n) return;
          this.markdown = markdownFile(what.path);
          this.drawing = !this.markdown && !what.on;   // beside, for the board
          return;
        }
        if (what.kind === "pull") {
          const review = new Review(what, this.core);
          await review.load(cx);
          if (what.n === this.n) this.review = review;
          return;
        }
        if (what.kind === "issue") {
          const answer = await this.core(GITHUB, ["view", what.github, String(what.number)], what.root, what.on);
          if (what.n === this.n) Object.assign(this, { issue: answer.issue ? answer : null, note: answer.error });
          return;
        }
        if (what.kind === "diff" && mediaKind(what.path) === "image") {
          if (what.on) return void (this.note = "A picture on another machine: only those on this Mac are shown");
          return void (await this.compare(what));
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

  /** WHAT as a PNG made on this Mac (core/media.py), in the app's home: a PDF's first page, with each page's size; an
   * SVG or a page for a board of SIZE (logical px), one that cannot be drawn leaving its code alone.
   * @param {{ width: number, height: number } | null} [size] */
  async paint(what, size = null) {
    const room = size ? [size.width, size.height].map((n) => String(Math.max(1, Math.round(n - 2 * INSET)) * 2))
      : [String(PICTURE)];
    const answer = await this.core(MEDIA, ["picture", `${what.root}/${what.path}`, "0", ...room], home(), null);
    if (what.n !== this.n) return;
    if (size) Object.assign(this, { drawnFor: size, drawing: Boolean(answer.png) });
    if (answer.kind === "audio" || answer.kind === "video") {
      this.clip = answer.png || answer.levels ? answer : null;
      return void (this.note = this.clip ? null : "This clip cannot be read here");
    }
    const [w, h] = answer.size ?? [1, 1];                 // no helper: the first page alone, through sips
    if (answer.kind === "pdf" && answer.png) {
      this.pdf = { sizes: answer.pages ?? [[612, Math.round((612 * h) / w)]], count: answer.pages?.length ?? null,
        made: [answer.png], range: null, making: false, page: 0, room: null };
    } else this.picture = answer.png ? { png: answer.png, size: answer.size, pixels: answer.pixels } : null;
    this.note = answer.png || this.editing ? null : "This picture cannot be shown";
  }

  /** Where WHAT, a picture or a clip, came from, as the chat that made it tells it (core/runs.py), with its brand
   * (core/connectors.py); nothing where none tells it. */
  trace(what, cx) {
    cx.spawn(async (cx) => {
      try {
        const told = await this.core(RUNS, ["origin", `${what.root}/${what.path}`], home(), null);
        if (!told || what.n !== this.n) return;
        const brand = await this.core(CONNECTORS, ["brand", told.server], home(), null);
        if (what.n === this.n) this.origin = { ...told, brand };
      } catch {
        // none told: the file alone
      } finally {
        cx.notify();
      }
    });
  }

  /** A changed picture's before (its last commit's) and after (the file's), as VS Code's image diff: either may be
   * missing, a new one's before and a deleted one's after. */
  async compare(what) {
    const [before, after] = await Promise.all([
      this.core(MEDIA, ["committed", what.root, what.path, String(PICTURE)], home(), null),
      this.core(MEDIA, ["picture", `${what.root}/${what.path}`, "0", String(PICTURE)], home(), null)]);
    if (what.n !== this.n) return;
    const side = (/** @type {any} */ answer) => (answer?.png ? answer : null);
    this.change = { before: side(before), after: side(after) };
    this.note = this.change.before || this.change.after ? null : "This picture cannot be shown";
  }

  /** The board's SIZE (logical px), as the canvas reports it: an SVG or a page drawn for the room in it, a moment
   * after it settles (a dragged divider's, once it stops). */
  fit(size, cx) {
    const made = this.drawnFor, what = this.what;
    this.board = size;
    if (!this.drawing || made && Math.abs(made.width - size.width) < 8 && Math.abs(made.height - size.height) < 8) {
      return;
    }
    this.fitting?.cancel();
    this.fitting = cx.timer.after(FIT, (cx) => cx.spawn(async (cx) => {
      try {
        await this.paint(what, size);
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    }));
  }

  /** While a PDF is shown: the bar's page kept up with the scrolled list, and a page in view or next to it made, one
   * at a time. */
  tick(cx) {
    const { pdf, what } = this;
    if (!pdf?.range) return;
    if (pdf.range.start !== pdf.page) {
      pdf.page = pdf.range.start;
      cx.notify();
    }
    const near = Array.from({ length: pdf.range.end - pdf.range.start + 2 }, (_, i) => pdf.range.start - 1 + i);
    const n = near.find((i) => i >= 0 && i < pdf.sizes.length && pdf.made[i] === undefined);
    if (pdf.making || n === undefined) return;
    pdf.making = true;
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(MEDIA, ["picture", `${what.root}/${what.path}`, String(n), String(PICTURE)],
          home(), null);
        pdf.made[n] = answer.png ?? "";
      } catch {
        pdf.made[n] = "";
      } finally {
        pdf.making = false;
        cx.notify();
      }
    });
  }

  /** Cmd+S or Cmd+F ("save", "find") for its code, while its tab is the one shown: whether it was its to do. */
  command(asked, cx) {
    return Boolean(this.editing?.command(asked, cx));
  }

  /** The file opened where opener() says (core/media.py): the browser, Preview, the player. */
  browse(cx) {
    const { what } = this, where = opener(what.path, window()?.platform);
    cx.spawn(async (cx) => {
      try {
        const done = await this.core(MEDIA, ["open", `${what.root}/${what.path}`], home(), null);
        keepNote(this.done, done.opened ? { text: `Opened in ${where}`, error: false } : { text: where === "Player"
          ? "Not opened: it is not a clip a player plays" : `No ${where.toLowerCase()} to open it in`, error: true },
        cx);
      } catch (e) {
        keepNote(this.done, { text: said(e), error: true }, cx);
      }
    });
  }

  /** The file shown in the Finder, chosen in its folder (core/media.py). */
  reveal(cx) {
    const { what } = this;
    cx.spawn(async (cx) => {
      try {
        const done = await this.core(MEDIA, ["reveal", `${what.root}/${what.path}`], home(), null);
        keepNote(this.done, done.shown ? { text: "Shown in the Finder", error: false }
          : { text: "The Finder is not on this machine", error: true }, cx);
      } catch (e) {
        keepNote(this.done, { text: said(e), error: true }, cx);
      }
    });
  }

  /** Ask for another: core's request sent to the chat that made it (CHAT, its live terminal), its tab shown. */
  again(chat, cx) {
    const origin = this.origin;
    cx.spawn(async (cx) => {
      try {
        const sent = await hc(["send", chat.address, origin.again]);
        if (sent.code !== 0) throw new Error(lastLine(sent));
        command("tab.select", { id: chat.labels[CHAT_TAB] });
        keepNote(this.done, { text: `Asked in “${origin.title}”`, error: false }, cx);
      } catch (e) {
        keepNote(this.done, { text: `Couldn't ask in “${origin.title}”: ${said(e)}`, error: true }, cx);
      }
    });
  }

  /** Audio played by the app (an MP3, as playSound plays), its waveform lit as far as it has played. */
  play(cx) {
    playSound(`${this.what.root}/${this.what.path}`);
    this.played = Date.now();
    this.playing = cx.timer.every(TICK, (/** @type {any} */ cx) => {
      if (Date.now() - Number(this.played) >= (this.clip?.seconds ?? 0) * 1000) {
        this.playing?.cancel();
        Object.assign(this, { played: null, playing: null });
      }
      cx.notify();
    });
    cx.notify();
  }

  /** The issue, the picture, or the file's, diff's or commit's rows in CODE (the code's font); else what is happening
   * instead. */
  render(t, code) {
    const frame = v_flex().id("preview").size_full().min_h(0).text_color(t.foreground).text_size(13)  // the pane's fill
      .on_mouse_down("right", () => this.menus.open(this.items()));
    if (this.issue) return frame.child(this.issueView(t));
    if (this.review) return frame.child(this.review.render(t, code));
    if (this.change && !this.note) return frame.child(this.changeView(t));
    if (this.editing && !this.loading) return frame.child(this.codeAndPicture(t, code));
    if (this.picture || this.clip) return frame.child(this.mediaView(t));
    if (this.pdf) return frame.child(this.pdfView(t));
    if (this.rows.length) return frame.child(this.diff(t, code));
    const line = this.loading ? "Loading…" : this.note ?? (this.what ? "" : "Nothing chosen to preview");
    return frame.child(div().p(16).text_size(12).text_color(this.note ? t.ansi1 : t.dim).child(line));
  }

  /** What a right click on the tab offers, as the TUI's: an SVG's or a page's views, the file in the browser, the tab
   * closed. @returns {import("./menus.js").Item[]} */
  items() {
    const both = this.paired(), down = stacks(this.stacked, this.room);
    const turn = (stacked) => (cx) => {
      this.stacked = stacked;
      cx.notify();
    };
    return [...(both ? VIEWS.map(([view, label]) => ({ label, on: this.shown === view, act: (cx) => {
      this.shown = view;
      cx.notify();
    } })) : []),
    ...(both || this.change?.before && this.change?.after
      ? [{ label: "Side by Side", on: !down, act: turn(false) }, { label: "Stacked", on: down, act: turn(true) }] : []),
    ...(browsable(this.what) ? [{ label: this.opens(), act: (cx) => this.browse(cx) }] : []),
    { label: "Close Preview", act: () => {
      const tab = shownPreviewTab();
      if (tab) command("tab.close", { id: tab.id });
    } }];
  }

  /** The bar above a page or a picture: an SVG's or a page's views, the PDF's page in view, and Open in Browser at its
   * end. */
  bar(t) {
    const { pdf } = this;
    return h_flex().h(40).flex_none().px(12).gap(4).items_center().border_b(1).border_color(t.border)
      .when(this.paired(), (e) => e.child(choices(t, "preview", VIEWS, this.shown,
        (shown, cx) => {
          this.shown = shown;
          cx.notify();
        })))
      .when(this.twoParts(), (e) => {
        const down = stacks(this.stacked, this.room);
        return e.child(iconButton(t, "preview-turn", down ? "columns-2" : "rows-2", down ? "Side by side" : "Stacked",
          (cx) => {
            this.stacked = !down;
            cx.notify();
          }));
      })
      .when(Boolean(pdf), (e) => e.child(div().px(4).text_size(12).text_color(t.muted)
        .child(`Page ${(pdf?.page ?? 0) + 1} of ${pdf?.count ?? "?"}`)))
      .child(div().flex_1())
      .when(browsable(this.what), (e) => e.child(iconButton(t, "browse", "external-link", this.opens(),
        (cx) => this.browse(cx), { left: true })));
  }

  /** Whether its code has a picture beside it: a page or an SVG on this Mac, or Markdown, read as text. */
  paired() {
    return Boolean(this.editing?.state) && (this.drawing || this.markdown);
  }

  /** The page or the SVG drawn again for the saved file (as the disk has it); Markdown is drawn from the editor. */
  drawAgain(cx) {
    if (!this.drawing || !this.board) return void cx.notify();
    this.drawnFor = null;
    this.fit(this.board, cx);
  }

  /** Whether two parts share the room: a page's, an SVG's or Markdown's code and picture, or a changed picture's
   * before and after. */
  twoParts() {
    return (this.paired() && this.shown === "split") ||
      Boolean(this.change?.before && this.change?.after);
  }

  /** Open in Browser, or Preview for a picture no browser shows (opener()). */
  opens() {
    return `Open in ${opener(this.what?.path ?? "", window()?.platform)}`;
  }

  /** A picture, audio or a video (media-generation's preview): its bar (its pixels or length, the chat it came from),
   * the picture or the frame on the board or audio's waveform, where it came from, and its buttons. */
  mediaView(t) {
    const { clip, origin, what } = this, shape = (clip ?? this.picture)?.pixels;
    const facts = [shape ? `${shape[0]}×${shape[1]}` : null, clip?.seconds ? clipTime(clip.seconds) : null];
    return v_flex().size_full().min_h(0)
      .child(h_flex().h(40).flex_none().px(16).gap(8).items_center().border_b(1).border_color(t.border).text_size(12)
        .child(div().min_w(0).truncate().font_semibold().child(what.path))
        .child(div().flex_none().text_color(t.muted).child(facts.filter(Boolean).join(" · ")))
        .child(div().flex_1())
        .when(Boolean(origin?.title), (e) => e.child(div().min_w(0).truncate().text_color(t.muted)
          .tooltip(origin?.title ?? "").child(`from the chat “${origin?.title}”`))))
      .child(mediaKind(what.path) === "audio" ? this.wave(t) : artboard(t, "board", clip ?? this.picture))
      .when(Boolean(origin), (e) => e.child(this.about(t)))
      .child(this.buttons(t));
  }

  /** Audio's waveform on the board, as its card: Play (an MP3, which the app plays), its levels (the loudest the
   * whole height) lit in the accent as far as it has played, its time. */
  wave(t) {
    const { clip, played, what } = this, levels = clip?.levels ?? [], seconds = clip?.seconds ?? 0;
    const bars = levels.length ? Array.from({ length: BARS }, (_, n) => Math.max(...levels.slice(
      Math.floor((n * levels.length) / BARS), Math.max(Math.floor((n * levels.length) / BARS) + 1,
        Math.floor(((n + 1) * levels.length) / BARS))))) : [];
    const at = played === null ? 0 : Math.min(seconds, (Date.now() - played) / 1000), lit = seconds ? at / seconds : 0;
    const mp3 = what.path.toLowerCase().endsWith(".mp3");
    return div().id("board").flex_1().min_h(0).flex().items_center().justify_center().p(INSET).bg(t.canvas)
      .child(h_flex().w_full().max_w(720).h(56).px(12).gap(12).items_center().rounded(10).bg(t.surface)
        .border_1().border_color(t.border)
        .when(mp3, (e) => e.child(small(t, "preview-play", icon("play", 12), played === null ? "Play" : "Playing",
          played === null, (cx) => this.play(cx))))
        .child(h_flex().flex_1().min_w(0).h(32).gap(2).items_center().children(bars.map((level, n) =>
          div().flex_1().min_w(0).h(Math.max(2, (level * 32) / Math.max(1, ...bars))).rounded_xs()
            .bg(n < lit * BARS ? t.accent : t.border))))
        .child(div().flex_none().text_size(12).text_color(t.muted)
          .child(played === null ? clipTime(seconds) : `${clipTime(at)} / ${clipTime(seconds)}`)));
  }

  /** Where an agent's picture or clip came from, as its chat tells it: the model and service, the prompt, the skill
   * in use, the calls (a media service bills in credits). */
  about(t) {
    const { origin } = this;
    const name = /** @type {Record<string, { name: string }>} */ (BRANDS)[origin.brand ?? ""]?.name ?? origin.server;
    const credits = Object.hasOwn(MEDIA_SERVICES, origin.brand ?? "") ? ` · ${name} bills in credits` : "";
    const lines = [["Model", [origin.model, name].filter(Boolean).join(" · ")], ["Prompt", origin.prompt],
      ["Skill", origin.skill], ["Calls", `${origin.calls}${credits}`]].filter(([, value]) => value);
    return v_flex().flex_none().px(16).pt(12).gap(4).border_t(1).border_color(t.border).text_size(12)
      .children(lines.map(([label, value], n) => h_flex().id(`preview-about-${n}`).gap(12).items_start()
        .child(div().w(LABEL).flex_none().text_color(t.muted).child(label))
        .child(div().flex_1().min_w(0).child(value))));
  }

  /** What a picture or a clip can be done with, what was done at the left: Show in Finder, Ask for another (lit while
   * the chat that made it runs here as a chat), Open at the right end. */
  buttons(t) {
    const { origin } = this, note = this.done.note;
    const chat = origin ? terminals().find((one) => one.labels?.[CHAT_LABEL] === origin.session
      && one.state === "live") : null;
    return h_flex().flex_none().px(16).py(12).gap(8).items_center()
      .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(note?.error ? t.ansi1 : t.muted)
        .child(note?.text ?? ""))
      .when(window()?.platform === "macos", (e) => e.child(actButton(t, "preview-finder", "Show in Finder", "raised",
        true, (cx) => this.reveal(cx))))
      .when(Boolean(origin), (e) => e.child(actButton(t, "preview-again", "Ask for another", "raised", Boolean(chat),
        (cx) => this.again(chat, cx), chat ? null : `“${origin?.title}” is not open as a chat: Chats opens it`)))
      .child(actButton(t, "preview-open", this.opens(), "solid", true, (cx) => this.browse(cx)));
  }

  /** A PDF's pages one under another at their own size, GAP apart, scrolled; each drawn once it is made (a page's
   * shape until then), as it comes into view. */
  pdfView(t) {
    const pdf = /** @type {NonNullable<Preview["pdf"]>} */ (this.pdf), list = `pdf-${this.what.n}`;  // new: at its top
    const shown = pdf.sizes.map(([w, h]) => {       // at their own size, smaller where the room is narrower
      const k = pdf.room ? Math.min(1, Math.max(1, pdf.room - 2 * MARGIN) / w) : 1;
      return [w * k, h * k];
    });
    const page = (n) => {
      const [w, h] = shown[n], made = pdf.made[n];
      return div().w_full().h(h + GAP).flex_none().pt(GAP).flex().justify_center()
        .child((made ? image(made) : div().bg(t.raised)).w(w).h(h).shadow_md());              // a page on the board
    };
    return v_flex().size_full().min_h(0)
      .child(this.bar(t))
      .child(div().id(`${list}-room-${viewId(this)}`).flex_1().min_h(0).relative().bg(t.canvas)
        .on_size_change((size, cx) => {
          if (size.width === pdf.room) return;
          pdf.room = size.width;
          cx.notify();
        })
        .child(v_virtual_list(list, pdf.sizes.length, shown.map(([, h]) => h + GAP), (n) => String(n), (range) => {
          pdf.range = range;                                    // the ticks make what is in view
          return Array.from({ length: range.end - range.start }, (_, i) => page(range.start + i));
        }).size_full())
        .child(Scrollbar.vertical(list).viewport_from_layout().absolute().inset_0()));
  }

  /** A page's, an SVG's or Markdown's code in the editor and its picture, as VS Code's preview to the side: side by
   * side, or the code above where the room is taller than wide (or as chosen), the divider dragged (the window keeps
   * where); or either alone, as the bar's views have it; its code alone where it cannot be drawn. */
  codeAndPicture(t, code) {
    const editing = /** @type {Editing} */ (this.editing);
    const lines = v_flex().size_full().min_w(0).min_h(0).child(editing.render(t, code));
    if (!this.paired()) {
      return v_flex().size_full().min_h(0).when(browsable(this.what), (e) => e.child(this.bar(t))).child(lines);
    }
    const board = v_flex().size_full().min_w(0).min_h(0).child(this.markdown ? this.page(t, editing) : this.canvas(t));
    const parts = stacks(this.stacked, this.room) ? v_resizable("preview-split-stacked") : h_resizable("preview-split");
    return v_flex().size_full().min_h(0)
      .child(this.bar(t))
      .child(this.shown === "split"
        ? div().id(`preview-room-${viewId(this)}`).flex_1().min_h(0)
          .on_size_change((size, cx) => this.measure(size, cx))
          .child(parts.size_full().child(resizable_panel().child(lines)).child(resizable_panel().child(board)))
        : v_flex().flex_1().min_h(0).child(this.shown === "code" ? lines : board));
  }

  /** EDITING's Markdown drawn as the issues' text is (safe: no image fetched, no HTML), as its editor holds it. */
  page(t, editing) {
    return div().id("preview-page").flex_1().min_h(0).overflow_y_scrollbar().bg(t.canvas)
      .child(v_flex().w_full().max_w(860).px(24).py(20).text_size(13).text_color(t.foreground)
        .child(TextView.markdown(`page-${this.what.n}`, safeMarkdown(editing.text())).selectable()));
  }

  /** The room the code and the picture share, SIZE (logical px): which way they part, by its shape, follows it. */
  measure(size, cx) {
    if (this.room && this.room.width === size.width && this.room.height === size.height) return;
    this.room = size;
    cx.notify();
  }

  /** The picture on the board, as a design tool's artboard: as large as the room allows and never larger than it is,
   * centered, the room round it the canvas's color. */
  canvas(t) {
    return artboard(t, `board-${viewId(this)}`, this.picture).on_size_change((room, cx) => this.fit(room, cx));
  }

  /** A changed picture, as VS Code's image diff: its before and after side by side, or one above the other where the
   * room is taller than wide (or as chosen), each on the canvas over its caption; a new one's after alone. */
  changeView(t) {
    const sides = changeSides(/** @type {any} */ (this.change)), down = stacks(this.stacked, this.room);
    return v_flex().size_full().min_h(0)
      .child(this.bar(t))
      .child(div().id(`preview-room-${viewId(this)}`).flex_1().min_h(0)
        .on_size_change((size, cx) => this.measure(size, cx))
        .child((down ? v_flex() : h_flex()).size_full().children(sides.map(([caption, side], i) =>
          v_flex().flex_1().min_w(0).min_h(0).when(i > 0, (e) => (down ? e.border_t(1) : e.border_l(1))
            .border_color(t.border))
            .child(artboard(t, `change-${i}`, side))
            .child(div().h(32).flex_none().px(16).flex().items_center().text_size(12).text_color(t.muted)
              .bg(t.canvas).child(caption))))));
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
