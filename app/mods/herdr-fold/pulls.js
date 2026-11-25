// @ts-check
// Pull requests in the dock, as the TUI sidebar's: the Issues tab's Pull requests (the repository's; a press opens
// one's review in the preview tab) and Changes' row and form (the branch's; a new one's title and body by the agent).
import { div } from "gpui-kit";
import { v_flex, h_flex, Input, InputState, Textarea, TextareaState } from "gpui-base";
import { COMMIT_MESSAGE, GIT, GITHUB } from "./helper.js";
import { hovering, issuesParts, said } from "./logic.js";
import { button, BUTTON, choices, field, footNote, GAP, icon, iconButton, keepNote, PAD, segmented, small, SPINNER }
  from "./parts.js";
import { sendToAgent, tabAgent } from "./issues.js";
import { showPreview } from "./preview.js";

const STATES = { open: "Open", closed: "Closed" };
const ROW = 48;                   // px: a pull request's row, as an issue's
const LOOK = 60000;               // ms between two looks at the branch's pull request while nothing changed
const AS = /** @type {[string, string][]} */ ([["draft", "Draft"], ["ready", "Ready for review"]]);
/** a review's state, core/github.py's review_state, in words and the role of their color (none: a neutral tag) */
export const REVIEW = { draft: ["Draft", null], yours: ["your review", "ansi3"],
  changes: ["changes requested", "ansi1"], approved: ["approved", "ansi2"], merged: ["merged", "muted"],
  closed: ["closed", "muted"] };
/** the checks' mark (core/github.py's pull_listed) and its color's role: passed, running, failed */
export const MARKS = { passed: ["✓", "ansi2"], running: ["●", "ansi3"], failed: ["✕", "ansi1"] };

/** @typedef {{ number: number, title: string, branch: string, author: string, state: string, url: string,
 * mark: string, checks_said: string, review: string, said: string, ago: string }} Listed */

/** A pull request's review state as one word on the right: Draft a neutral tag, the rest in their color. */
export function reviewWord(t, review) {
  const [word, role] = REVIEW[/** @type {keyof typeof REVIEW} */ (review)] ?? ["", null];
  if (!word) return div();
  return role ? div().flex_none().text_size(12).text_color(t[role]).child(word)
    : div().flex_none().h(18).px(6).flex().items_center().rounded(4).bg(t.raised).text_size(11).text_color(t.muted)
      .child(word);
}

/** The checks' mark in the mark column: ✓ green, ● yellow while they run, ✕ red; its room without checks. */
export function checksMark(t, mark) {
  const [glyph, role] = MARKS[/** @type {keyof typeof MARKS} */ (mark)] ?? ["", "dim"];
  return div().w(14).flex_none().flex().justify_center().text_size(mark === "running" ? 9 : 11).text_color(t[role])
    .child(glyph);
}

export class PullsView {
  /** HOST: the view it shows in, for the repository (root, on, github), its core calls (core), the row the mouse is
   * on (hovered), and the way to Changes' form (newPull). @param {any} host */
  constructor(host) {
    this.host = host;
    this.state = "open";
    /** @type {{ pulls: Listed[], error: string | null } | null} */
    this.listing = null;
    this.asked = null;
    this.find = InputState.new({ placeholder: "Filter pull requests" });
    this.words = [];
    this.find.on("change", (_e, cx) => {
      this.words = this.find.value().toLowerCase().split(/\s+/).filter(Boolean);
      cx.notify();
    });
    /** @type {number | null} the one last opened, marked */
    this.chosen = null;
    /** @type {import("./parts.js").Note | null} */
    this.note = null; this.busy = null;
  }

  /** Another repository's: nothing of this one's listed or chosen. */
  reset() {
    Object.assign(this, { listing: null, asked: null, chosen: null, note: null });
  }

  /** The pull requests of STATE asked of GitHub again; an answer for another repository or state is dropped. */
  load(cx, state = this.state) {
    const { root, on, github } = this.host;
    if (!github) return;
    const key = JSON.stringify([github, state]);
    this.state = state;
    this.asked = key;
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["pulls", github, state], root, on);
        if (this.asked === key) this.listing = answer;
      } catch (e) {
        if (this.asked === key) this.listing = { pulls: [], error: said(e) };
      } finally {
        if (this.asked === key) this.asked = null;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** @returns {Listed[]} the answer's that hold every word typed */
  shown() {
    return (this.listing?.pulls ?? []).filter((pull) => this.words.every((w) => pull.said.includes(w)));
  }

  /** PULL's review in the space's preview tab. @param {Listed} pull */
  open(pull, cx) {
    const { root, on, github } = this.host;
    this.chosen = pull.number;
    showPreview({ kind: "pull", root, on, github, number: pull.number, title: pull.title });
    cx.notify();
  }

  /** PULL to the focused tab's agent (else a new one) with core/github.py's prompt for it, as Issues' To agent.
   * @param {Listed} pull */
  toAgent(pull, cx) {
    const agent = tabAgent();
    if (this.busy) return;
    this.busy = "Sending…";
    keepNote(this, null, cx);
    cx.spawn(async (cx) => {
      let note = null;
      try {
        const { root, on, github } = this.host;
        const { prompt } = await this.host.core(GITHUB, ["pull-prompt", github, String(pull.number)], root, on);
        note = { text: `${await sendToAgent(agent, prompt, root)}: #${pull.number}`, error: false };
      } catch (e) {
        note = { text: said(e), error: true };
      } finally {
        this.busy = null;
        keepNote(this, note, cx);
      }
    });
  }

  render(t) {
    const shown = this.shown(), foot = this.busy ? { text: this.busy, error: false } : this.note;
    const { refresh, say } = issuesParts({ asked: Boolean(this.asked), listing: this.listing, shown: shown.length,
      state: this.state, filtered: Boolean(this.words.length), noun: "pull requests" });
    return v_flex().size_full().min_h(0)
      .child(h_flex().flex_none().p(PAD).pb(6).gap(6).items_center()
        .child(field(t, "pull-search", this.find).flex_1().min_w(0))
        .child(button(t, "pull-new", icon("plus", 15), Boolean(this.host.github), false,
          (cx) => this.host.newPull(cx)).tooltip("New pull request: in Changes")))
      .child(h_flex().flex_none().pl(PAD).pr(PAD / 2).pb(8).gap(GAP).items_center()
        .child(choices(t, "pulls", Object.entries(STATES), this.state, (state, cx) => this.load(cx, state)))
        .child(div().flex_1())
        .child(refresh === "spinner"
          ? div().id("pull-loading").size(BUTTON).flex_none().flex().items_center().justify_center()
            .text_size(15).text_color(t.muted).tooltip("Loading pull requests…").child(div().frames(SPINNER, 100))
          : iconButton(t, "pull-refresh", "refresh-cw", "Refresh", (cx) => this.load(cx))))
      .child(v_flex().id("pulls").flex_1().min_h(0).overflow_y_scrollbar().px(PAD / 2).pb(PAD / 2)
        .when(Boolean(say), (e) => e.child(h_flex().min_h(ROW).flex_none().px(PAD / 2).py(6).items_center()
          .text_size(12).text_color(t[say?.[1] ?? "dim"]).child(say?.[0] ?? "")))
        .children(shown.map((pull) => this.row(t, pull))))
      .when(Boolean(foot), (e) => e.child(footNote(t, /** @type {any} */ (foot))));
  }

  /** A pull request's two rows: its checks' mark, its number and title, its review's state on the right; its branch,
   * author, age and checks under them; with the mouse on it, to the agent and the browser. @param {Listed} pull */
  row(t, pull) {
    const key = `pull-${pull.number}`;
    const under = [pull.branch, pull.author, pull.ago, pull.mark === "passed" ? "" : pull.checks_said];
    return h_flex().id(key).h(ROW).flex_none().px(PAD / 2).gap(8).items_center().rounded(6).cursor_pointer()
      .when(this.chosen === pull.number, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
      .on_hover(hovering(this.host, key)).on_click((_e, cx) => this.open(pull, cx))
      .on_mouse_down("right", () => this.host.menus.open(this.picks(pull)))
      .child(v_flex().h(36).flex_none().child(checksMark(t, pull.mark)))
      .child(v_flex().flex_1().min_w(0).gap(2)
        .child(h_flex().gap(6).min_w(0).child(div().flex_none().text_color(t.muted).child(`#${pull.number}`))
          .child(div().flex_1().min_w(0).truncate().child(pull.title))
          .when(this.host.hovered !== key, (e) => e.child(reviewWord(t, pull.review))))
        .child(div().min_w(0).truncate().text_size(11).text_color(t.dim).child(under.filter(Boolean).join(" · "))))
      .when(this.host.hovered === key, (e) => e.child(h_flex().flex_none().gap(GAP)
        .child(small(t, `${key}-agent`, icon("bot"), "To agent", !this.busy, (cx) => this.toAgent(pull, cx)))
        .child(small(t, `${key}-web`, icon("external-link"), "Open in browser", true,
          (cx) => cx.open_url(pull.url)))));
  }

  /** The right click's menu on PULL: all its keys do with it. @param {Listed} pull
   * @returns {import("./menus.js").Item[]} */
  picks(pull) {
    return [{ label: "Open", act: (cx) => this.open(pull, cx) }, { label: "Open in the browser", url: pull.url },
      { label: "To the agent", act: (cx) => this.toAgent(pull, cx) }];
  }
}

/** The branch's pull request in Changes, under the repository: one row (none yet: the way to open one), and the form
 * that opens one in the composer's place, its title and body written by core/commit_message.py's writer. */
export class BranchPull {
  /** HOST: Changes (root, on, github, status, menus, notify), WRITER: its background run of the writer.
   * @param {any} host @param {(cx: any, args: string[]) => Promise<any>} writer */
  constructor(host, writer) {
    this.host = host;
    this.writer = writer;
    /** @type {{ pull: Listed | null, base: string, error: string | null } | null} the branch's, as last asked */
    this.answer = null;
    /** @type {string | null} what it was asked for (the repository, the branch, its last commit), and when */
    this.for = null; this.at = 0; this.asking = false;
    /** the form asked for before the branch's answer came (Issues' +): opened with it */
    this.wanted = false;
    /** @type {{ base: string, bases: string[], draft: boolean, commits: number, writing: string | null,
     * note: import("./parts.js").Note | null, busy: boolean } | null} the form, while open */
    this.form = null;
    this.title = InputState.new({ placeholder: "Title" });
    this.title.on("change", (_e, cx) => cx.notify());           // the button follows whether there is one
    this.body = TextareaState.new({ placeholder: "Body" });
    this.body.set_auto_grow(4, 10);
  }

  /** Another space's: nothing of this one's. */
  reset() {
    Object.assign(this, { answer: null, for: null, at: 0, form: null, wanted: false });
  }

  /** A pushed branch's asked of GitHub again once it or its last commit changed, a minute went by, or FORCE says. */
  look(cx, head, force = false) {
    const { root, on, github, status } = this.host;
    const branch = status?.upstream && status?.branch;           // never pushed: no pull request yet
    if (!github || !branch || this.asking) return;
    const key = JSON.stringify([github, branch, head]);
    if (!force && key === this.for && Date.now() - this.at < LOOK) return;
    Object.assign(this, { for: key, at: Date.now(), asking: true });
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["branch", github, branch], root, on);
        if (key === this.for) this.answer = answer;
      } catch (e) {
        if (key === this.for) this.answer = { pull: null, base: "", error: said(e) };
      } finally {
        this.asking = false;
        if (this.wanted && this.answer) this.start(cx);
        cx.notify();
      }
    });
  }

  /** Whether the row shows: on GitHub, a branch that is not the base, pushed, or with a pull request already. */
  get shown() {
    const status = this.host.status, answer = this.answer;
    return Boolean(this.host.github && status?.branch && answer && !answer.error && answer.base &&
      status.branch !== answer.base && (answer.pull || status.upstream));
  }

  /** The row: the pull request's checks' mark, number and title, its state and checks; a press opens its review. Else
   * no pull request, and the way to open one. */
  row(t) {
    const pull = this.answer?.pull;
    const frame = h_flex().id("branch-pull").h(32).flex_none().mx(PAD / 2).mt(2).mb(4).px(12).gap(8).items_center()
      .rounded(8).border_1().border_color(t.border).bg(t.chrome).text_size(12);
    if (!pull) return frame.child(icon("git-pull-request", 14).text_color(t.muted))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child("No pull request for this branch"))
      .child(small(t, "pull-create", "Create pull request…", "Open a pull request of this branch", this.host.ready,
        (cx) => this.start(cx)));
    const { root, on, github } = this.host;
    return frame.cursor_pointer().hover((s) => s.bg(t.hover)).tooltip(pull.url)
      .on_click((_e, cx) => {
        showPreview({ kind: "pull", root, on, github, number: pull.number, title: pull.title });
        cx.notify();
      })
      .child(checksMark(t, pull.mark))
      .child(div().flex_1().min_w(0).truncate().child(`#${pull.number} ${pull.title}`))
      .child(reviewWord(t, pull.review))
      .when(Boolean(pull.checks_said), (e) => e.child(div().flex_none().text_color(t.muted).child(pull.checks_said)));
  }

  /** The form opened in the composer's place, Draft chosen, Into the repository's default branch; ✦ writes. A branch
   * the row offers none for (not pushed, the base, one there already) opens none. */
  start(cx) {
    if (!this.answer) return void (this.wanted = true);          // asked before the branch's answer came
    this.wanted = false;
    if (!this.shown || this.answer.pull || this.form || !this.host.ready) return;     // none to open, or one there
    this.form = { base: this.answer.base, bases: [this.answer.base], draft: true, commits: 0, writing: null,
      note: null, busy: false };
    this.title.set_value("");
    this.body.set_value("");
    const { root, on } = this.host;
    cx.spawn(async (cx) => {
      const { bases } = await this.host.core(GIT, ["bases", root], root, on).catch(() => ({ bases: [] }));
      if (this.form) this.form.bases = [...new Set([this.form.base, ...bases])];
      cx.notify();
    });
    this.write(cx);
  }

  /** The title and the body written by Claude or Codex from the branch's commits since Into, in the background. */
  write(cx) {
    const form = this.form, { root, on } = this.host;
    if (!form || form.writing) return;
    form.note = null;
    cx.spawn(async (cx) => {
      try {
        form.writing = (await this.host.core(COMMIT_MESSAGE, ["writing", root, "pull"], root, on)).writing;
        cx.notify();
        const answer = await this.writer(cx, ["pull", root, form.base]);
        if (answer.title) this.title.set_value(answer.title);
        this.body.set_value(answer.body ?? "");
        form.commits = answer.commits ?? 0;
        const by = answer.backend === "codex" ? "Codex" : "Claude";
        form.note = answer.title ? { text: `${by} wrote the title and the body from the branch's ${form.commits === 1
          ? "commit" : `${form.commits} commits`}; ✦ writes them again.`, error: false }
          : { text: answer.note ?? "No title written", error: true };
      } catch (e) {
        form.note = { text: said(e), error: true };
      } finally {
        form.writing = null;
        cx.notify();
      }
    });
  }

  /** The pull request opened on GitHub as the form says, a draft or ready; the row asked again. */
  create(cx) {
    const form = this.form, { root, on, github, status } = this.host;
    const title = this.title.value().trim();
    if (!form || !title || form.busy) return;
    form.busy = true;
    form.note = null;
    cx.spawn(async (cx) => {
      try {
        const asked = { base: form.base, branch: status.branch, title, body: this.body.value(), draft: form.draft };
        const answer = await this.host.core(GITHUB, ["open-pull", github, JSON.stringify(asked)], root, on);
        if (answer.error) throw new Error(answer.error);
        this.form = null;
        this.look(cx, this.host.head, true);
      } catch (e) {
        form.note = { text: said(e), error: true };
      } finally {
        form.busy = false;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** The form given up: nothing opened. */
  cancel(cx) {
    this.form = null;
    cx.notify();
  }

  /** The form, as GitHub's own: Into (a menu of the remote's branches) from the branch and its commits, the Title with
   * ✦ (both written again), the Body, Draft or Ready, what wrote them; Cancel and the one button, as chosen. */
  formView(t) {
    const form = /** @type {NonNullable<BranchPull["form"]>} */ (this.form), branch = this.host.status?.branch ?? "";
    const label = (text) => div().w(44).flex_none().text_color(t.muted).child(text);
    const line = (name, ...parts) => h_flex().gap(8).items_center().child(label(name)).children(parts);
    const into = h_flex().id("pull-into").h(26).px(8).gap(6).flex_none().items_center().rounded(6).bg(t.raised)
      .cursor_pointer().hover((s) => s.bg(t.hover)).on_mouse_down("left", (e) => (this.pressed = e.bounds))
      .on_click(() => this.host.menus.open(form.bases.map((base) => ({ label: base, on: base === form.base,
        act: (cx) => {
          form.base = base;
          this.write(cx);
        } })), this.pressed))
      .child(form.base).child(icon("chevron-down", 12).text_color(t.dim));
    const spark = form.writing ? div().size(15).flex().items_center().justify_center().text_color(t.muted)
      .child(div().frames(SPINNER, 100)) : icon("sparkles", 15).text_color(t.muted);
    const ready = Boolean(this.title.value().trim()) && !form.busy && !form.writing;
    return v_flex().id("pull-form").flex_none().px(PAD).pt(6).pb(PAD).gap(8).border_b(1).border_color(t.border)
      .text_size(12).on_key_down((e, cx) => {
        if (e.key === "escape") this.cancel(cx);
      })
      .child(div().text_size(13).font_semibold().child("New pull request"))
      .child(line("Into", into, div().min_w(0).truncate().text_color(t.muted).child(`from ${branch}${form.commits
        ? ` · ${form.commits === 1 ? "1 commit" : `${form.commits} commits`}` : ""}`)))
      .child(line("Title", h_flex().flex_1().min_w(0).h(32).pl(8).pr(4).gap(4).items_center().rounded(6).border_1()
        .border_color(t.border).bg(t.background)
        .child(Input.new(this.title).flex_1().h_full().text_size(12).text_color(t.foreground))
        .child(small(t, "pull-write", spark, form.writing ?? "Write the title and the body again", !form.writing,
          (cx) => this.write(cx)))))
      .child(h_flex().gap(8).items_start().child(label("Body").pt(6))
        .child(div().flex_1().min_w(0).min_h(96).rounded(6).border_1().border_color(t.border).bg(t.background)
          .child(Textarea.new(this.body).px(8).py(6).text_size(12))))
      .child(line("As", segmented(t, "pull-as", AS, form.draft ? "draft" : "ready", (as, cx) => {
        form.draft = as === "draft";
        cx.notify();
      })))
      .when(Boolean(form.note || form.writing), (e) => e.child(div().text_size(11)
        .text_color(form.note?.error ? t.ansi1 : t.muted).child(form.writing ?? form.note?.text ?? "")))
      .child(h_flex().gap(8).items_center().justify_end()
        .child(small(t, "pull-cancel", "Cancel", "Open none", true, (cx) => this.cancel(cx)))
        .child(button(t, "pull-open", form.busy ? "Opening…" : form.draft ? "Create draft pull request"
          : "Create pull request", ready, true, (cx) => this.create(cx))));
  }
}
