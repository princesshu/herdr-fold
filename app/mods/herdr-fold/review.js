// @ts-check
// A pull request's review in the preview tab, as GitHub's Files changed: its head (number, title, state, branches,
// checks), its diff by file with each thread on its line, the comments added to the review, and the review's bar.
import { div } from "gpui-kit";
import { v_flex, h_flex, Input, InputState, Textarea, TextareaState, TextView } from "gpui-base";
import { GITHUB } from "./helper.js";
import { commentAt, loginColor, reviewReady, said, safeMarkdown } from "./logic.js";
import { button, field, icon, PAD, segmented, small } from "./parts.js";
import { sendToAgent, tabAgent } from "./issues.js";
import { checksMark, reviewWord } from "./pulls.js";

const EVENTS = /** @type {[string, string][]} */ ([["comment", "Comment"], ["approve", "Approve"],
  ["request", "Request changes"]]);
const ROW = 20;                   // px: a diff's line, center-chat.html's code
const NUMBER = 44;                // px: its number's column, a press there starts a comment
const INSET = 16;                 // px: the side padding of the head, a file's bar and its lines

/** @typedef {{ path: string, line: number, side: "LEFT" | "RIGHT", body: string }} Pending */

export class Review {
  /** WHAT (a Shown pull request) reviewed; CORE runs core/'s code where the repository is (main.js's python).
   * @param {any} what
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
  constructor(what, core) {
    this.what = what;
    this.core = core;
    /** @type {any} core/github.py's review(): the pull request, its files with their threads */
    this.pull = null;
    /** @type {string | null} why there is nothing to show, or what went wrong last */
    this.note = null;
    this.loading = true;
    /** @type {Pending[]} the comments added to the review, sent with it */
    this.pending = [];
    /** @type {{ path: string, line: number, side: "LEFT" | "RIGHT" } | null} the line a comment is written on */
    this.at = null;
    this.words = TextareaState.new({ placeholder: "Leave a comment" });
    this.words.set_auto_grow(2, 8);
    this.summary = InputState.new({ placeholder: "Summary" });
    this.summary.on("change", (_e, cx) => cx.notify());       // Submit follows whether there is one
    this.event = "comment";
    /** @type {string | null} the thread a reply is written in */
    this.replying = null;
    this.reply = TextareaState.new({ placeholder: "Reply" });
    this.reply.set_auto_grow(2, 8);
    /** @type {Record<string, string>} where each thread's comment went with To agent, by the thread */
    this.sent = {};
    /** @type {Set<string>} the threads whose replies (or, resolved, all of it) are shown */
    this.unfolded = new Set();
    /** @type {string | null} what is under way: a review sent, a reply, a thread resolved */
    this.busy = null;
  }

  /** The pull request asked of GitHub (again, after a change made here). */
  async load(cx) {
    const { root, on, github, number } = this.what;
    try {
      const answer = await this.core(GITHUB, ["review", github, String(number)], root, on);
      Object.assign(this, { pull: answer.pull, note: answer.error });
      if (this.pull?.mine && this.event === "approve") this.event = "comment";
    } catch (e) {
      this.note = said(e);
    } finally {
      this.loading = false;
      cx.notify();
    }
  }

  /** WORK with LABEL meanwhile; its error on the bar, else the pull request asked for again. */
  act(cx, label, work) {
    if (this.busy) return;
    this.busy = label;
    this.note = null;
    cx.spawn(async (cx) => {
      try {
        const error = await work();
        if (error) this.note = error;
        else await this.load(cx);
      } catch (e) {
        this.note = said(e);
      } finally {
        this.busy = null;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** The review sent: its summary, the comments added, Comment, Approve or Request changes, on the commit shown. */
  submit(cx) {
    const { root, on, github, number } = this.what, body = this.summary.value().trim();
    if (!reviewReady(this.event, body, this.pull.mine)) return;
    const asked = { event: this.event, body, comments: this.pending, head: this.pull.head };
    this.act(cx, "Sending the review…", async () => {
      const answer = await this.core(GITHUB, ["submit", github, String(number), JSON.stringify(asked)], root, on);
      if (!answer.ok) return answer.advice;
      this.pending = [];
      this.summary.set_value("");
      return null;
    });
  }

  /** The comment written on the line chosen, added to the review (sent with it). */
  add(cx) {
    const body = this.words.value().trim();
    if (!this.at || !body) return;
    this.pending.push({ ...this.at, body });
    this.at = null;
    this.words.set_value("");
    cx.notify();
  }

  /** A comment started on ROW of PATH (a press on its number), the field taking the keys. */
  comment(path, row, cx) {
    const place = commentAt(row);
    if (!place) return;
    this.at = { path, ...place };
    this.words.set_value("");
    this.words.focus();
    cx.notify();
  }

  /** THREAD's reply sent at once, as GitHub's own Reply does. */
  answer(thread, cx) {
    const { root, on, github, number } = this.what, body = this.reply.value().trim();
    if (!body) return;
    this.act(cx, "Replying…", async () => {
      const answer = await this.core(GITHUB, ["answer", github, String(number), String(thread.comments[0].id), body],
        root, on);
      if (!answer.ok) return answer.advice;
      this.replying = null;
      this.reply.set_value("");
      return null;
    });
  }

  /** THREAD marked resolved on GitHub. */
  resolve(thread, cx) {
    const { root, on } = this.what;
    this.act(cx, "Resolving…", async () => {
      const answer = await this.core(GITHUB, ["resolve", thread.id], root, on);
      return answer.ok ? null : answer.advice;
    });
  }

  /** THREAD's first comment to the focused tab's agent (else a new one), as Issues' To agent: core/github.py's prompt
   * names where it is and how to read it; the thread then says where it went. */
  toAgent(thread, cx) {
    const agent = tabAgent(), { root, on, github, number } = this.what, first = thread.comments[0];
    const comment = { id: first.id, author: first.author, path: thread.path, line: thread.line };
    if (this.busy) return;
    this.busy = "Sending…";
    cx.spawn(async (cx) => {
      try {
        const { prompt } = await this.core(GITHUB, ["address", github, String(number), JSON.stringify(comment)], root,
          on);
        const file = thread.path.split("/").pop();
        this.sent[thread.id] = `${await sendToAgent(agent, prompt, root)}: #${number} · ${file}:${thread.line}`;
      } catch (e) {
        this.note = said(e);
      } finally {
        this.busy = null;
        cx.notify();
      }
    });
    cx.notify();
  }

  render(t, code) {
    if (!this.pull) return div().p(16).text_size(12).text_color(this.note ? t.ansi1 : t.dim)
      .child(this.loading ? "Loading…" : this.note ?? "");
    return v_flex().size_full().min_h(0)
      .child(this.head(t))
      .child(v_flex().id("review").flex_1().min_h(0).overflow_y_scrollbar()
        .children(this.pull.files.map((file) => this.file(t, code, file))))
      .child(this.bar(t));
  }

  /** The head: its number, title and review's state; its branches, author, checks and files. */
  head(t) {
    const pull = this.pull, files = pull.files.length;
    return v_flex().flex_none().px(INSET).pt(12).pb(8).gap(4).border_b(1).border_color(t.border)
      .child(h_flex().gap(8).items_center().text_size(15)
        .child(div().flex_none().text_color(t.muted).child(`#${pull.number}`))
        .child(div().flex_1().min_w(0).truncate().font_semibold().child(pull.title))
        .child(reviewWord(t, pull.review)))
      .child(h_flex().gap(6).items_center().text_size(12).text_color(t.muted)
        .child(div().flex_none().child(`${pull.branch} → ${pull.base} · ${pull.author}`))
        .when(Boolean(pull.checks_said), (e) => e.child("·").child(checksMark(t, pull.mark))
          .child(div().flex_none().child(pull.checks_said)))
        .child(div().flex_none().child(`· ${files === 1 ? "1 file" : `${files} files`}`)));
  }

  /** FILE's bar (its path, lines added and removed), its lines, each thread and comment under its line. */
  file(t, code, file) {
    const bar = h_flex().h(32).flex_none().px(INSET).gap(8).items_center().bg(t.chrome).border_b(1)
      .border_color(t.border).text_size(12)
      .child(div().flex_1().min_w(0).truncate().font_family(code).child(file.path))
      .child(div().flex_none().text_color(t.ansi2).child(`+${file.added}`))
      .child(div().flex_none().text_color(t.ansi1).child(`−${file.removed}`));
    return v_flex().flex_none()
      .child(bar)
      .child(v_flex().py(4).text_size(12).children(file.rows.flatMap((row, n) => [this.line(t, code, file.path, row, n),
        ...this.under(t, file.path, row)])))
      .when(file.cut > 0, (e) => e.child(div().px(INSET).pb(8).text_size(12).text_color(t.dim)
        .child(`${file.cut} more lines: in the browser`)))
      .children(file.loose.map((thread) => this.thread(t, thread)));
  }

  /** ROW of PATH in CODE (the code's font): its number (a press starts a comment there), its text; added green,
   * removed red, a hunk's head muted. */
  line(t, code, path, row, n) {
    if (row.kind === "@") return div().h(ROW).px(INSET).flex().items_center().truncate().font_family(code)
      .text_color(t.muted).child(row.text);
    const number = String(row.kind === "-" ? row.old : row.new);
    return h_flex().id(`${path}:${n}`).h(ROW).px(INSET).items_center().font_family(code)
      .when(row.kind === "+", (e) => e.bg(t.ansi2 + "1c")).when(row.kind === "-", (e) => e.bg(t.ansi1 + "1f"))
      .child(div().id(`${path}:${n}:number`).w(NUMBER).flex_none().text_color(t.dim).cursor_pointer()
        .hover((s) => s.text_color(t.foreground)).tooltip("Comment on this line")
        .on_click((_e, cx) => this.comment(path, row, cx)).child(number))
      .child(div().w(14).flex_none().text_color(row.kind === "+" ? t.ansi2 : row.kind === "-" ? t.ansi1 : t.dim)
        .child(row.kind === " " ? "" : row.kind))
      .child(div().flex_1().min_w(0).truncate().whitespace_nowrap().child(row.text));
  }

  /** What sits under ROW of PATH: its threads, the comments added on it, the one being written. */
  under(t, path, row) {
    const place = commentAt(row);
    if (!place) return [];
    const here = (/** @type {{ path: string, line: number, side: string }} */ p) => p.path === path &&
      p.line === place.line && p.side === place.side;
    return [...(row.threads ?? []).map((thread) => this.thread(t, thread)),
      ...this.pending.filter(here).map((pending) => this.pendingCard(t, pending)),
      ...(this.at && here(this.at) ? [this.editor(t)] : [])];
  }

  /** A comment: its author's mark, name and age, BUTTONS beside them; its words as markdown (safe: no image fetched,
   * no HTML). */
  said(t, id, comment, buttons = []) {
    return v_flex().px(12).py(8).gap(4)
      .child(h_flex().gap(8).items_center().text_size(12).text_color(t.muted)
        .child(div().size(18).flex_none().flex().items_center().justify_center().rounded_full()
          .bg(loginColor(comment.author)).text_size(10).font_bold().text_color(t.background)
          .child((comment.author[0] ?? "?").toUpperCase()))
        .child(div().flex_none().font_semibold().text_color(t.foreground).child(comment.author))
        .child(div().flex_1().min_w(0).truncate().child(comment.ago))
        .children(buttons))
      .child(TextView.markdown(id, safeMarkdown(comment.body)).selectable());
  }

  /** A thread under its line: its first comment with Reply, To agent (on one's own pull request) and Resolve, its
   * replies folded; where To agent sent it; a resolved one folded to one line. */
  thread(t, thread) {
    const open = this.unfolded.has(thread.id), [first, ...replies] = thread.comments;
    const card = v_flex().ml(INSET + NUMBER).mr(INSET).my(6).flex_none().rounded(8).border_1().border_color(t.border)
      .bg(t.chrome).text_size(12);
    const fold = (cx) => {
      if (!this.unfolded.delete(thread.id)) this.unfolded.add(thread.id);
      cx.notify();
    };
    if (thread.resolved && !open) return card.child(h_flex().id(`${thread.id}-resolved`).h(32).px(12).gap(6)
      .items_center().text_color(t.muted).cursor_pointer().on_click((_e, cx) => fold(cx))
      .child(icon("check", 12)).child(`Resolved · ${first.author}${replies.length ? ` and ${replies.length} more`
        : ""}`));
    const id = thread.id, enabled = !this.busy;
    const buttons = [small(t, `${id}-reply`, "Reply", "Reply in this thread", enabled, (cx) => {
      this.replying = id;
      this.reply.set_value("");
      this.reply.focus();
      cx.notify();
    }),
    ...(this.pull.mine ? [small(t, `${id}-agent`, "To agent", "To the agent: it reads the comment with gh", enabled,
      (cx) => this.toAgent(thread, cx))] : []),
    ...(thread.resolved ? [] : [small(t, `${id}-resolve`, "Resolve", "Mark this thread resolved", enabled,
      (cx) => this.resolve(thread, cx))])];
    return card.child(this.said(t, `${id}-0`, first, buttons))
      .when(Boolean(replies.length), (e) => e.child(open
        ? v_flex().children(replies.map((reply, n) => this.said(t, `${id}-${n + 1}`, reply).border_t(1)
          .border_color(t.border)))
        : div().id(`${id}-more`).px(12).pb(8).text_color(t.muted).cursor_pointer().on_click((_e, cx) => fold(cx))
          .child(replies.length === 1 ? "1 reply" : `${replies.length} replies`)))
      .when(Boolean(this.sent[id]), (e) => e.child(h_flex().px(12).pb(8).gap(6).items_center().text_color(t.muted)
        .child(icon("check", 12)).child(this.sent[id])))
      .when(this.replying === id, (e) => e.child(this.writer(t, this.reply, "Reply", (cx) => this.answer(thread, cx),
        (cx) => {
          this.replying = null;
          cx.notify();
        })));
  }

  /** A comment added to the review, not sent yet: You · pending, its words, × takes it back.
   * @param {Pending} pending */
  pendingCard(t, pending) {
    const n = this.pending.indexOf(pending);
    return v_flex().ml(INSET + NUMBER).mr(INSET).my(6).flex_none().rounded(8).border_1().border_color(t.border)
      .bg(t.chrome).px(12).py(8).gap(4).text_size(12)
      .child(h_flex().gap(8).items_center().text_color(t.muted).child(div().flex_1().child("You · pending"))
        .child(small(t, `pending-${n}`, icon("x", 12), "Take it back", true, (cx) => {
          this.pending.splice(n, 1);
          cx.notify();
        })))
      .child(div().child(pending.body));
  }

  /** The comment written on the line chosen: its field, Cancel, Add to review. */
  editor(t) {
    return v_flex().ml(INSET + NUMBER).mr(INSET).my(6).flex_none().rounded(8).border_1().border_color(t.border)
      .bg(t.chrome).child(this.writer(t, this.words, "Add to review", (cx) => this.add(cx), (cx) => {
        this.at = null;
        cx.notify();
      }));
  }

  /** WORDS' field, then Cancel and LABEL (DONE), as a reply's and a comment's. */
  writer(t, words, label, done, cancel) {
    return v_flex().px(12).py(8).gap(8).text_size(12)
      .child(div().rounded(6).border_1().border_color(t.border).bg(t.background)
        .child(Textarea.new(words).px(8).py(6).text_size(12)))
      .child(h_flex().gap(8).justify_end().items_center()
        .child(small(t, `${label}-cancel`, "Cancel", "Leave it", true, cancel))
        .child(button(t, `${label}-done`, label, !this.busy, false, done)));
  }

  /** The review's bar: its summary, how many comments it holds, Comment, Approve (not on one's own) or Request
   * changes, and Submit review, the one primary button; what went wrong last above it. */
  bar(t) {
    const count = this.pending.length, events = EVENTS.filter(([event]) => event !== "approve" || !this.pull.mine);
    const ready = reviewReady(this.event, this.summary.value(), this.pull.mine) && !this.busy;
    return v_flex().flex_none().border_t(1).border_color(t.border).bg(t.chrome)
      .when(Boolean(this.note || this.busy), (e) => e.child(div().px(PAD).pt(8).text_size(11)
        .text_color(this.busy ? t.muted : t.ansi1).child(this.busy ?? this.note ?? "")))
      .child(h_flex().flex_wrap().px(PAD).py(8).gap(8).items_center()
        .child(field(t, "review-summary", this.summary).flex_1().min_w(140))
        .child(div().flex_none().text_size(12).text_color(t.muted).child(`Review · ${count === 1 ? "1 comment"
          : `${count} comments`}`))
        .child(segmented(t, "review-event", events, this.event, (event, cx) => {
          this.event = event;
          cx.notify();
        }))
        .child(button(t, "review-submit", "Submit review", ready, true, (cx) => this.submit(cx))
          .tooltip(ready || this.busy ? "Send the review to GitHub" : "Comment and Request changes need a summary")));
  }
}
