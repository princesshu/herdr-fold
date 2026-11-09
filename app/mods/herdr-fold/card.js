// @ts-check
// What Claude waits on, answered in the chat's prompt place: the card agents.js makes of the request, its options by
// click or key, a kept rule's scope, a No's words, a question's answers; the reply goes back through the hook.
import { div } from "gpui-kit";
import { v_flex, h_flex, Textarea, TextareaState, TextView } from "gpui-base";
import { cardFor, nextScope, promptText, replyFor } from "./agents.js";
import { diffRows } from "./logic.js";
import { fold, icon, keyCap } from "./parts.js";

const LINES = 8;                      // a change's old and new text: their lines shown at most, each
const PLAN = 240;                     // px: a plan's height at most, scrolled past it
const SCOPES = { session: "this conversation", project: "this project", user: "all projects" };

export class Answer {
  /** The card of what Claude waits on, if anything; SEND takes its reply.
   * @param {(reply: any, cx: any) => void} send */
  constructor(send, cx) {
    this.send = send;
    this.focus = cx.focus_handle();
    this.words = TextareaState.new({ placeholder: "Tell Claude what to do instead" });
    this.words.set_auto_grow(1, 4);
    this.words.on("submit", (event, cx) => {
      if (!event.shift) this.choose(this.no(), cx);
    });
    /** @type {import("./agents.js").Card | null} */
    this.card = null;
    this.reset(null);
  }

  /** REQUEST (request.json's, or none) as the card shown, nothing chosen on it yet; CHOICES those of Claude's own
   * dialog when it asks there. @param {any} request @param {{ key: string, label: string }[]} [choices] */
  reset(request, choices) {
    this.card = request ? cardFor(request, choices) : null;
    this.chosen = 0;                              // the option the arrows are on
    this.scope = this.card?.options.find((o) => o.scope)?.scope ?? "project";
    this.asking = false;                          // No chosen: its words asked for
    this.folded = false;
    this.question = 0;                            // a question card's tab
    /** @type {Record<string, string[]>} each question's answer, its options' labels */
    this.answers = {};
    this.words.set_value("");
  }

  /** Whether REQUEST is the one shown (none when nothing waits), with CHOICES as its dialog's when given.
   * @param {any} request @param {{ key: string, label: string }[]} [choices] */
  shows(request, choices) {
    return (this.card?.id ?? null) === (request?.id ?? null)
      && (!choices || !this.card?.dialog || this.card.options.length === choices.length);
  }

  no() {
    return /** @type {import("./agents.js").Option} */ (this.card?.options.find((o) => o.choice === "deny"));
  }

  /** OPTION answered: a No asks for its words first, a Submit waits for every question's answer.
   * @param {import("./agents.js").Option} option */
  choose(option, cx) {
    const card = this.card;
    if (!card || !option) return;
    if (option.choice === "deny" && !this.asking) {
      this.asking = true;
      this.words.focus();
      return void cx.notify();
    }
    const questions = card.questions ?? [];
    if (option.choice !== "deny" && questions.some((q) => !this.answers[q.question]?.length)) return;
    const answers = card.kind === "question" ? Object.fromEntries(Object.entries(this.answers)
      .map(([question, labels]) => [question, labels.join(", ")])) : undefined;
    this.send(replyFor(card, option, { scope: this.scope, answers,
      text: option.choice === "deny" ? promptText(this.words.value()) : undefined }), cx);
  }

  /** A question's option LABEL picked: one of several taken or left, the only one taken and the next question shown.
   * @param {any} question @param {string} label */
  pick(question, label, cx) {
    const had = this.answers[question.question] ?? [];
    this.answers[question.question] = question.multiSelect
      ? (had.includes(label) ? had.filter((l) => l !== label) : [...had, label]) : [label];
    if (!question.multiSelect) this.question = Math.min(this.question + 1, (this.card?.questions?.length ?? 1) - 1);
    cx.notify();
  }

  /** The card's keys: 1 2 3 (a question's options), the arrows, Enter, Esc (No, or back from its words), Tab (the next
   * question), Option-Down and Option-Up (folded to a line and open). */
  key(event, cx) {
    const card = this.card;
    if (!card) return;
    const { key } = event;
    if (event.modifiers.alt && (key === "down" || key === "up")) {
      this.folded = key === "down";
      return void cx.notify();
    }
    if (this.asking) {
      if (key === "escape") this.asking = false;
      return void cx.notify();
    }
    const question = card.questions?.[this.question];
    if (/^[1-9]$/.test(key)) {
      const picked = question ? question.options?.[Number(key) - 1]?.label : null;
      if (question && picked) return this.pick(question, picked, cx);
      const option = card.options.find((o) => o.key === key);
      if (option) this.choose(option, cx);
      return;
    }
    if (key === "up" || key === "down") {
      this.chosen = (this.chosen + (key === "down" ? 1 : -1) + card.options.length) % card.options.length;
    } else if ((key === "left" || key === "right") && card.options[this.chosen]?.scope) {
      this.scope = nextScope(this.scope, key === "right" ? 1 : -1);
    } else if (key === "tab" && card.questions?.length) {
      this.question = (this.question + 1) % card.questions.length;
    } else if (key === "enter") {
      return this.choose(card.options[this.chosen], cx);
    } else if (key === "escape") {
      return this.choose(this.no(), cx);
    }
    cx.notify();
  }

  /** The card as drawn in the chat's design: a header line (the question, what it is about, the fold),
   * what is asked (the command, the change, the plan, the questions), the answers; folded, its header alone. */
  render(t, code) {
    const card = /** @type {import("./agents.js").Card} */ (this.card);
    const box = v_flex().id("card").track_focus(this.focus).on_key_down((e, cx) => this.key(e, cx)).rounded(10)
      .border(1).border_color(t.ansi3 + "59").bg(t.surface).text_size(13).overflow_hidden();
    const head = h_flex().px(16).py(12).gap(8).items_center()
      .child(div().flex_none().font_semibold().child(card.title))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted)
        .font_family(card.kind === "change" && !this.folded ? code : "").child(this.about(card)))
      .child(div().id("card-fold").size(24).flex_none().flex().items_center().justify_center().rounded(6)
        .cursor_pointer().hover((s) => s.bg(t.hover)).tooltip(this.folded ? "Open (⌥↑)" : "Fold (⌥↓)")
        .on_click((_e, cx) => {
          this.folded = !this.folded;
          cx.notify();
        }).child(fold("card-fold-mark", !this.folded, 14, t.dim, ["chevron-up", "chevron-down"])));
    if (this.folded) return box.child(head);
    return box.child(head)
      .child(v_flex().px(16).pb(12).gap(8)
        .when(card.kind === "command", (e) => e.child(this.command(t, code, card)))
        .when(card.kind === "change", (e) => e.child(this.change(t, code, card)))
        .when(card.kind === "plan", (e) => e.child(div().id("plan").max_h(PLAN).overflow_y_scrollbar()
          .child(TextView.markdown("plan-text", String(card.detail)).text_size(13))))
        .when(card.kind === "question", (e) => e.child(this.questions(t))))
      .child(this.asking ? this.wordsField(t) : this.options(t));
  }

  /** What the card is about, after its question: the tool, the file, the plan's size, or folded its sentence. */
  about(card) {
    if (this.folded) return [card.sentence, card.questions?.length > 1 ? `${card.questions.length} questions` : ""]
      .filter(Boolean).join(" · ");
    const steps = String(card.detail ?? "").split("\n").filter((line) => /^\s*\d+[.)]/.test(line)).length;
    if (card.kind === "plan") return steps ? `Plan · ${steps} steps` : "Plan";
    return card.kind === "change" ? card.sentence : card.kind === "command" ? "Bash" : "";
  }

  /** A command: itself as a shell line, Claude's words for it and the folder it runs in. */
  command(t, code, card) {
    return v_flex().gap(8)
      .child(h_flex().px(12).py(8).gap(8).rounded(6).border(1).border_color(t.border).bg(t.background)
        .font_family(code).text_size(12).child(div().text_color(t.dim).child("$")).child(card.sentence))
      .when(Boolean(card.detail), (e) => e.child(h_flex().gap(8).text_size(12)
        .child(div().flex_1().min_w(0).child(String(card.detail)))));
  }

  /** A file's change as the timeline draws one: its path and counts on top, its lines numbered by the file. */
  change(t, code, card) {
    const lines = card.change?.lines ?? [], added = lines.filter((l) => l.startsWith("+")).length;
    const removed = lines.filter((l) => l.startsWith("-")).length;
    const row = ({ kind, number, text }) => kind === "gap" ? div().h(8)
      : h_flex().w_full().gap(12).px(8).when(kind === "+", (e) => e.bg(t.ansi2 + "18"))
        .when(kind === "-", (e) => e.bg(t.ansi1 + "18"))
        .child(div().w(32).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
        .child(div().w(10).flex_none().text_color(kind === "+" ? t.ansi2 : kind === "-" ? t.ansi1 : t.dim)
          .child(kind === "+" || kind === "-" ? kind : ""))
        .child(div().flex_1().min_w(0).truncate().child(text));
    return v_flex().rounded(6).border(1).border_color(t.border).bg(t.background).overflow_hidden()
      .child(h_flex().px(8).py(4).gap(8).text_size(12)
        .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(card.sentence.split("/").pop() ?? ""))
        .child(div().text_color(t.ansi2).child(`+${added}`)).child(div().text_color(t.ansi1).child(`−${removed}`)))
      .child(div().id("change").max_h(PLAN).overflow_y_scrollbar().py(4).font_family(code).text_size(12)
        .child(v_flex().children(diffRows(lines.slice(0, LINES * 6)).map(row))));
  }

  /** A question card: a tab for each question (a tick once answered), the shown one's question and its answers as
   * radio rows, each with its key; under them how many are answered, Tab to the next, Esc, Submit. */
  questions(t) {
    const all = this.card?.questions ?? [], question = all[this.question];
    const answered = all.filter((q) => this.answers[q.question]?.length).length;
    return v_flex().gap(8)
      .when(all.length > 1, (e) => e.child(h_flex().gap(16).children(all.map((q, n) => h_flex().id(`question-${n}`)
        .gap(6).pb(4).cursor_pointer().text_color(n === this.question ? t.foreground : t.muted)
        .when(n === this.question, (e) => e.border_b(2).border_color(t.accent))
        .when(Boolean(this.answers[q.question]?.length), (e) => e.child(icon("check", 12).text_color(t.done)))
        .child(String(q.header ?? n + 1)).on_click((_e, cx) => {
          this.question = n;
          cx.notify();
        })))))
      .child(div().font_semibold().child(String(question?.question ?? "")))
      .child(v_flex().gap(2).children((question?.options ?? []).map((/** @type {any} */ option, n) => {
        const picked = this.answers[question.question]?.includes(option.label);
        return h_flex().id(`pick-${n}`).gap(12).px(8).py(6).rounded(6).items_start().cursor_pointer()
          .when(Boolean(picked), (e) => e.bg(t.raised)).hover((s) => s.bg(t.hover))
          .on_click((_e, cx) => this.pick(question, option.label, cx))
          .child(div().size(16).mt(2).flex_none().rounded(8).border(2).border_color(picked ? t.accent : t.dim)
            .when(Boolean(picked), (e) => e.p(2).child(div().size_full().rounded(4).bg(t.accent))))
          .child(v_flex().flex_1().min_w(0).child(div().font_semibold().child(option.label))
            .when(Boolean(option.description), (e) => e.child(div().text_size(12).text_color(t.muted)
              .child(option.description))))
          .child(keyCap(t, String(n + 1)));
      })))
      .child(h_flex().pt(4).gap(12).items_center().text_size(12).text_color(t.muted)
        .child(`${answered} of ${all.length} answered`)
        .when(all.length > 1, (e) => e.child(h_flex().gap(6).child(keyCap(t, "⇥")).child("next question")))
        .child(div().flex_1())
        .child(h_flex().gap(6).child(keyCap(t, "esc")).child("cancel"))
        .child(h_flex().id("submit").h(28).px(12).gap(6).items_center().rounded(6).bg(t.raised)
          .text_color(answered === all.length ? t.foreground : t.dim).cursor_pointer()
          .on_click((_e, cx) => this.choose(/** @type {any} */ (this.card?.options[0]), cx))
          .child("Submit").child(keyCap(t, "↩"))));
  }

  /** A key as a small cap. @param {string} key */
  /** The card's answers (not a question's: it has its own footer), the one the arrows are on lit with ↩ beside it,
   * No with esc; a kept rule's scope under its own, ← → beside. */
  options(t) {
    if (this.card?.kind === "question") return div();
    return v_flex().px(8).pb(8).gap(2).children((this.card?.options ?? []).map((option, n) => h_flex()
      .id(`option-${n}`).gap(12).px(8).py(8).rounded(6).items_start().cursor_pointer()
      .when(n === this.chosen, (e) => e.bg(t.raised)).hover((s) => s.bg(t.hover))
      .on_click((_e, cx) => this.choose(option, cx))
      .child(keyCap(t, option.key).when(n === this.chosen, (e) => e.border_color(t.accent).text_color(t.accent)))
      .child(v_flex().flex_1().min_w(0).gap(4).child(div().font_semibold().child(option.label))
        .when(Boolean(option.scope), (e) => e.child(h_flex().gap(4).items_center().text_size(12).text_color(t.muted)
          .child("Kept for").children(Object.entries(SCOPES).map(([scope, words]) => div().id(`scope-${scope}`).px(6)
            .rounded(4).cursor_pointer().text_color(scope === this.scope ? t.foreground : t.muted)
            .when(scope === this.scope, (e) => e.bg(t.hover)).child(words).on_click((_e, cx) => {
              cx.stop_propagation();
              this.scope = scope;
              cx.notify();
            }))).child(keyCap(t, "←")).child(keyCap(t, "→")))))
      .when(n === this.chosen, (e) => e.child(keyCap(t, "↩")))
      .when(option.choice === "deny" && n !== this.chosen, (e) => e.child(keyCap(t, "esc")))));
  }

  /** A No's words for Claude, in the prompt's place: Enter sends them (none is fine), Esc goes back to the answers. */
  wordsField(t) {
    return div().m(8).rounded(8).border(1).border_color(t.accent).bg(t.canvas)
      .child(Textarea.new(this.words).px(12).py(8).text_size(13));
  }
}
