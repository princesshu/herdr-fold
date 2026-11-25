// @ts-check
// A Claude chat's checkpoints (core/checkpoints.py): a prompt's quiet Restore files to here, the card in the prompt's
// place with Claude's dry run (which files change, what stays), and the row after the restore with its one Undo.
import { div } from "gpui-kit";
import { v_flex, h_flex } from "gpui-base";
import { said } from "./logic.js";
import { fold, icon, keyCap, spinner } from "./parts.js";
import { CARD_HEAD, clock, filePlace, restorable, restoredWords, restoreLabel, RHYTHM as R, stays }
  from "./timeline.js";

const LISTED = 160;                   // px: the card's files at most, scrolled past it
const ROW = 22;                       // px: a file's row, the mockup's (.files .f)
const ACT = 16;                       // px: the prompt's label line, its actions and its time

/** @typedef {{ point: any, words: string, asked: any, busy: boolean, error: string | null, folded: boolean }} Card */

export class Checkpoints {
  /** RUN asks core/checkpoints.py about the chat (its command and args, the answer's JSON); ROOT is the chat's folder,
   * the files named from it; BACK gives the keys back to the prompt once the card closes.
   * @param {(args: string[]) => Promise<any>} run @param {() => string} root @param {() => void} back */
  constructor(run, root, back, cx) {
    this.run = run;
    this.root = root;
    this.back = back;
    this.focus = cx.focus_handle();
    /** @type {Map<string, any>} core's points by their prompt's id, and the newest one's id */
    this.points = new Map();
    this.last = null;
    /** @type {any} the restore that can be undone (core's undoable), and the words of what was done since */
    this.undo = null;
    /** @type {{ text: string, error: boolean } | null} */
    this.told = null;
    this.readAt = -1;                 // the chat's steps when the points were last read
    /** @type {number | null} the prompt's row under the mouse */
    this.over = null;
    /** @type {Card | null} the restore asked for, in the prompt's place */
    this.card = null;
  }

  /** The points read again once the chat is idle with steps (STEPS of them) not read yet. @param {number} steps */
  read(steps, cx) {
    if (steps === this.readAt) return;
    this.readAt = steps;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const got = await this.run(["points"]);
        if (got.error) return;
        const last = got.points.length ? got.points[got.points.length - 1].id : null;
        if (last !== this.last && this.last !== null) this.told = null;       // a prompt since: its words are old
        this.points = new Map(got.points.map((/** @type {any} */ p) => [p.id, p]));
        this.last = last;
        this.undo = got.undo;
        cx.notify();
      } catch {
        this.readAt = -1;                                                       // read again next time
      }
    });
  }

  /** The quiet actions on the label line of a prompt (ROW, at INDEX): shown under the mouse while the chat is IDLE,
   * no card up, only where its turn wrote files Claude still keeps. */
  actions(t, row, index, idle) {
    const point = this.points.get(row.id);
    if (!idle || this.card || this.over !== index || !restorable(point)) return null;
    return h_flex().id(`restore-${index}`).gap(4).items_center().text_color(t.muted).cursor_pointer()
      .hover((s) => s.text_color(t.foreground)).child(icon("rotate-ccw", 12)).child("Restore files to here")
      .on_click((_e, cx) => this.open(point, row.text, cx));
  }

  /** The label line over a prompt: its actions at the left, its time at the right. */
  label(t, row, index, idle) {
    const actions = this.actions(t, row, index, idle);
    return h_flex().h(ACT).gap(12).items_center().text_size(11).text_color(t.dim)
      .when(Boolean(actions), (e) => e.child(actions)).child(div().flex_1()).child(clock(row.at));
  }

  /** The prompt's row under the mouse (OVER) or not. @param {number} index @param {boolean} over */
  hover(index, over, cx) {
    const next = over ? index : this.over === index ? null : this.over;
    if (next === this.over) return;
    this.over = next;
    cx.notify();
  }

  /** The card for POINT, its prompt's WORDS in its head, and Claude's dry run asked at once. */
  open(point, words, cx) {
    /** @type {Card} */
    const card = { point, words: String(words ?? "").split("\n")[0], asked: null, busy: false, error: null,
      folded: false };
    this.card = card;
    this.over = null;
    this.focus.focus();
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const asked = await this.run(["ask", point.id]);
        card.asked = asked.error ? null : asked;
        card.error = asked.error ?? null;
      } catch (e) {
        card.error = said(e);
      }
      cx.notify();
    });
  }

  /** The card closed, nothing done: the keys back to the prompt. */
  close(cx) {
    this.card = null;
    this.back();
    cx.notify();
  }

  /** Whether the card's restore can be pressed now: the dry run in, a file to change, nothing under way. */
  ready() {
    return Boolean(this.card?.asked?.files?.length && !this.card.busy);
  }

  /** The files taken back to the card's point: Claude's own rewind, the files set aside first for the Undo. */
  restore(cx) {
    const card = this.card;
    if (!card || !this.ready()) return;
    card.busy = true;
    card.error = null;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const done = await this.run(["restore", card.point.id, String(this.last ?? card.point.id)]);
        if (done.error) throw new Error(done.error);
        this.card = null;
        this.back();
        this.told = { text: restoredWords(done.files, card.point.at), error: false };
        this.readAt = -1;
      } catch (e) {
        card.error = said(e);
      }
      card.busy = false;
      cx.notify();
    });
  }

  /** The last restore undone: its files back as they were before it, once. */
  undone(cx) {
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const done = await this.run(["undo"]);
        if (done.error) throw new Error(done.error);
        this.told = { text: `Undid the restore: ${done.files} file${done.files === 1 ? "" : "s"} back as they were`,
          error: false };
      } catch (e) {
        this.told = { text: said(e), error: true };
      }
      this.undo = null;
      this.readAt = -1;
      cx.notify();
    });
  }

  /** The card's keys: Enter restores, Esc cancels, Option-Down and Option-Up fold it to its head and open it. */
  key(event, cx) {
    const card = this.card;
    if (!card) return;
    if (event.modifiers.alt && (event.key === "down" || event.key === "up")) {
      card.folded = event.key === "down";
      cx.notify();
    } else if (event.key === "enter") {
      this.restore(cx);
    } else if (event.key === "escape") {
      this.close(cx);
    }
  }

  /** What the row after the timeline says: what was just done, else the restore that can be undone; null for none. */
  rowWords() {
    if (this.told) return { ...this.told, undo: Boolean(this.undo) && !this.told.error };
    const point = this.undo ? this.points.get(this.undo.point) : null;
    return point ? { text: restoredWords(this.undo.files, point.at), error: false, undo: true } : null;
  }

  /** The row's words (rowWords()) with its Undo, as a step's line draws them. @param {Record<string, string>} t
   * @param {(t: any) => string} link the links' ink */
  row(t, link) {
    const words = this.rowWords();
    if (!words) return null;
    return h_flex().min_h(R.line).gap(6).items_center().text_size(12)
      .text_color(words.error ? t.ansi1 : t.muted).child(icon("rotate-ccw", 12))
      .child(div().min_w(0).child(words.text))
      .when(words.undo, (e) => e.child(div().id("restore-undo").flex_none().px(4).rounded(4).cursor_pointer()
        .text_color(link(t)).hover((s) => s.bg(t.hover)).child("Undo").on_click((_e, cx) => this.undone(cx))));
  }

  /** The card in the prompt's place, its border neutral (Claude does not wait on it): its question and prompt, the
   * files Claude would change and the lines in all, what stays as it is, Esc cancel and the restore. */
  render(t, code) {
    const card = /** @type {Card} */ (this.card), files = card.asked?.files ?? [];
    const head = h_flex().h(CARD_HEAD).flex_none().pl(R.card).pr(R.gap).gap(R.gap).items_center()
      .child(icon("rotate-ccw", 14).text_color(t.muted))
      .child(div().flex_none().font_semibold().child(`Restore files to before ${clock(card.point.at)}?`))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(card.words))
      .child(div().id("restore-fold").size(24).flex_none().flex().items_center().justify_center().rounded(6)
        .cursor_pointer().hover((s) => s.bg(t.hover)).tooltip(card.folded ? "Open (⌥↑)" : "Fold (⌥↓)")
        .on_click((_e, cx) => {
          card.folded = !card.folded;
          cx.notify();
        }).child(fold("restore-fold-mark", !card.folded, 14, t.dim, ["chevron-up", "chevron-down"])));
    const box = v_flex().id("restore").track_focus(this.focus).on_key_down((e, cx) => this.key(e, cx)).rounded(10)
      .border(1).border_color(t.border).bg(t.chrome).text_size(13).overflow_hidden().child(head);
    if (card.folded) return box;
    const place = (/** @type {string} */ path, /** @type {number} */ n) => {
      const { name, folder } = filePlace(path, this.root());
      return h_flex().id(`restore-file-${n}`).h(ROW).flex_none().gap(R.gap).items_center().text_size(12)
        .tooltip(path).child(div().flex_none().font_family(code).child(name))
        .child(div().min_w(0).truncate().text_color(t.muted).child(folder));
    };
    const body = v_flex().px(R.card).pt(R.inset).pb(R.inset).gap(R.inset).border_t(1).border_color(t.border)
      .when(!card.asked && !card.error, (e) => e.child(h_flex().gap(R.gap).items_center().text_size(12)
        .text_color(t.muted).child(spinner(t)).child("Asking Claude which files would change…")))
      .when(Boolean(card.asked), (e) => e.child(v_flex()
        .child(div().id("restore-files").max_h(LISTED).overflow_y_scrollbar()
          .child(v_flex().children(files.map(place))))
        .child(h_flex().mt(2).pt(6).gap(R.gap).border_t(1).border_color(t.border).text_size(12).text_color(t.muted)
          .child(div().flex_1().child(`${files.length} file${files.length === 1 ? "" : "s"}`))
          .child(div().text_color(t.ansi2).child(`+${card.asked.insertions}`))
          .child(div().text_color(t.ansi1).child(`−${card.asked.deletions}`))))
        .child(v_flex().gap(R.pad).text_size(12).text_color(t.muted)
          .child(div().child(`Stays as it is: ${stays(card.point)}.`))
          .child(div().child("This chat keeps the later turns in mind."))))
      .when(Boolean(card.error), (e) => e.child(div().text_size(12).text_color(t.ansi1).child(card.error ?? "")));
    const ready = this.ready();
    const go = h_flex().id("restore-go").h(28).px(12).gap(R.gap).flex_none().items_center().rounded(8).text_size(12)
      .font_semibold().bg(ready ? t.solid : t.raised).text_color(ready ? t.solid_foreground : t.dim)
      .child(card.busy ? "Restoring…" : card.asked ? restoreLabel(files.length) : "Restore files")
      .when(ready, (e) => e.cursor_pointer().on_click((_e, cx) => this.restore(cx))
        .child(keyCap(t, "↩").border_color(t.solid_foreground + "80").text_color(t.solid_foreground)));
    const foot = h_flex().pl(R.card).pr(R.gap).pt(R.gap).pb(R.gap).gap(R.inset).items_center().border_t(1)
      .border_color(t.border).text_size(12).text_color(t.muted)
      .child(h_flex().id("restore-cancel").gap(6).items_center().cursor_pointer()
        .hover((s) => s.text_color(t.foreground)).on_click((_e, cx) => this.close(cx)).child(keyCap(t, "esc"))
        .child("Cancel"))
      .child(div().flex_1()).child(go);
    return box.child(body).child(foot);
  }
}
