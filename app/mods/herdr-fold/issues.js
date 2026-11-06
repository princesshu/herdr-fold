// @ts-check
// The Issues view, as the TUI sidebar's: GitHub's issues by priority with its filters; a click opens one in the preview
// tab, its buttons and right click's menu hand it to the tab's agent, the browser, a reply, assign, close or reopen.
import { div } from "gpui-kit";
import { v_flex, h_flex, InputState } from "gpui-base";
import { agents, focused, hc, run as command } from "herdr";
import { COMMIT_MESSAGE, GITHUB } from "./helper.js";
import { hovering, issueAgent, priorityColor, said } from "./logic.js";
import { button, field, GAP, icon, small } from "./parts.js";
import { showPreview } from "./preview.js";

const LEVELS = ["Urgent", "High", "Medium", "Low"];      // GitHub's Priority field's options, core/github.py's ranks
const STATES = { open: "Open", closed: "Closed" };
const BUSY = { close: "Closing…", reopen: "Reopening…", assign: "Assigning…" };
const DONE = { close: "Closed", reopen: "Reopened", assign: "Assigned to you:" };

/** @typedef {{ number: number, title: string, labels: string[], assignees: string[], state: string, url: string,
 * level: number | null, ranked_by: string | null, said: string, ago: string }} Listed */

export class IssuesView {
  /** HOST: the view it shows in, for the repository (root, on, github), its core calls (core), the row the mouse is
   * on (hovered) and the Changes' link (linked). @param {any} host */
  constructor(host) {
    this.host = host;
    this.query = { state: "open", assigned: false, authored: false, label: "" };
    /** @type {number | null} the priority shown (its rank), or all */
    this.level = null;
    /** @type {{ issues: Listed[], error: string | null } | null} */
    this.listing = null;
    this.asked = null;
    this.find = InputState.new({ placeholder: "Search issues" });
    this.words = [];
    this.find.on("change", (_e, cx) => {
      this.words = this.find.value().toLowerCase().split(/\s+/).filter(Boolean);
      cx.notify();
    });
    /** @type {number | null} the issue last opened, marked */
    this.chosen = null;
    /** @type {{ number: number, what: string } | null} the close or reopen asked about first */
    this.confirm = null;
    this.note = null; this.busy = null;
  }

  /** Another repository's: nothing of this one's listed or chosen (the filters stay, as in the TUI sidebar). */
  reset() {
    Object.assign(this, { listing: null, asked: null, chosen: null, confirm: null, note: null });
  }

  /** The issues of QUERY (the one chosen by default) asked of GitHub again; an answer for another query is dropped. */
  load(cx, query = this.query) {
    const { root, on, github } = this.host;
    if (!github) return;
    const key = JSON.stringify([github, query]);
    this.query = query;
    this.asked = key;
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["issues", github, JSON.stringify(query)], root, on);
        if (this.asked === key) this.listing = answer;
      } catch (e) {
        if (this.asked === key) this.listing = { issues: [], error: said(e) };
      } finally {
        if (this.asked === key) this.asked = null;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** The issues shown: the answer's of the chosen priority that hold every word typed. @returns {Listed[]} */
  shown() {
    return (this.listing?.issues ?? []).filter((issue) => this.words.every((w) => issue.said.includes(w)) &&
      (this.level === null || issue.level === this.level));
  }

  /** ISSUE in the space's preview tab, its text and comments, as the TUI sidebar's o and Enter.
   * @param {Listed} issue */
  open(issue, cx) {
    const { root, on, github } = this.host;
    this.chosen = issue.number;
    showPreview({ kind: "issue", root, on, github, number: issue.number, title: issue.title, level: issue.level,
      ranked_by: issue.ranked_by });
    cx.notify();
  }

  /** WORK with LABEL showing meanwhile; its answer (a line to show, or null), then the list asked again. */
  act(cx, label, work) {
    if (this.busy) return;
    this.busy = label;
    this.note = null;
    cx.spawn(async (cx) => {
      try {
        this.note = await work(cx);
      } catch (e) {
        this.note = said(e);
      } finally {
        this.busy = null;
        this.load(cx);
        cx.notify();
      }
    });
    cx.notify();
  }

  /** ISSUE to the focused tab's Claude or Codex with core/github.py's prompt for it, and linked to the next commit (its
   * Fixes line in Changes), as the TUI sidebar's t does. @param {Listed} issue */
  toAgent(issue, cx) {
    const agent = issueAgent(agents(), focused()?.tab);
    if (!agent) return void ((this.note = "No Claude or Codex in this tab to hand the issue to"), cx.notify());
    this.act(cx, "Sending…", async () => {
      const { root, on, github } = this.host;
      const { prompt } = await this.host.core(GITHUB, ["prompt", github, String(issue.number)], root, on);
      const sent = await hc(["send", agent.address, prompt]);
      if (sent.code !== 0) return (sent.stderr || sent.stdout).trim() || "not sent";
      command("agent.focus", { terminal: agent.address });
      const answer = await this.host.core(COMMIT_MESSAGE, ["link", root, String(issue.number), issue.title], root, on);
      this.host.linked = answer.linked;
      return `Sent to ${agent.program?.name ?? "the agent"}: #${issue.number}`;
    });
  }

  /** WHAT (close, reopen, assign) done to ISSUE on GitHub; closing and reopening asked first, as in the TUI sidebar.
   * @param {Listed} issue @param {"close" | "reopen" | "assign"} what */
  change(issue, what, cx) {
    if (what !== "assign" && (this.confirm?.number !== issue.number || this.confirm.what !== what)) {
      this.confirm = { number: issue.number, what };
      return void cx.notify();
    }
    this.confirm = null;
    const { root, on, github } = this.host;
    this.act(cx, BUSY[what], async () => {
      const answer = await this.host.core(GITHUB, ["change", github, String(issue.number), what], root, on);
      return answer.ok ? `${DONE[what]} #${issue.number}` : answer.advice;
    });
  }

  /** The close or reopen asked about dropped: nothing done. */
  unask(cx) {
    this.confirm = null;
    cx.notify();
  }

  /** gh's own prompts for a reply to ISSUE, or a new issue, in a tab of their own on the space's machine.
   * @param {string[]} args */
  terminal(args, cx) {
    const { root, on, github } = this.host;
    this.act(cx, "Opening…", async () => {
      const answer = await this.host.core(GITHUB, [args[0], github, ...args.slice(1)], root, on);
      command("tab.new", { argv: answer.argv, folder: root });
      return null;
    });
  }

  /** The filter FIELD turned on or off, or set to VALUE (a label, a priority), and asked of GitHub again (but the
   * priority, picked from what is listed). @param {string} field @param {any} [value] */
  filter(field, value, cx) {
    if (field === "level") {
      this.level = value;
      return void cx.notify();
    }
    const q = this.query;
    this.load(cx, { ...q, [field]: field === "label" ? value : !q[field] });
  }

  render(t) {
    const shown = this.shown();
    return v_flex().size_full().min_h(0)
      .child(this.field(t))
      .child(this.states(t))
      .when(Boolean(this.line(shown)), (e) => e.child(this.status(t, shown)))
      .child(v_flex().id("issues").flex_1().min_h(0).overflow_y_scrollbar().px(6).pb(6)
        .children(shown.map((issue) => this.row(t, issue))));
  }

  /** The search field, the new issue's button and the filters', as the TUI sidebar has them on one line. */
  field(t) {
    const q = this.query;
    // as the TUI sidebar's, in the field: what is on (the priority in its color), else Filters, then ▾
    const on = [...(this.level !== null ? [[`● ${LEVELS[this.level]}`, priorityColor(t, this.level)]] : []),
      ...[["me", q.assigned], ["by me", q.authored], [q.label, q.label]].filter(([, is]) => is)
        .map(([word]) => [word, t.foreground])];
    const shown = on.length ? on : [["Filters", t.muted]];
    const filters = h_flex().id("issue-filters").h(24).px(8).gap(4).flex_none().items_center().rounded(5)
      .text_size(12).cursor_pointer().hover((s) => s.bg(t.hover)).on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();
        this.pressed = e.bounds;
      })
      .on_click(() => this.host.menus.open(this.filters(t), this.pressed))
      .children(shown.flatMap(([word, color], i) => [...(i ? [div().text_color(t.muted).child("·")] : []),
        div().text_color(color).child(String(word))]))
      .child(icon("chevron-down", 12).text_color(t.muted));
    return h_flex().flex_none().p(10).pb(6).gap(6).items_center()
      .child(field(t, "issue-search", this.find, filters).flex_1().min_w(0))
      .child(button(t, "issue-new", icon("plus", 15), Boolean(this.host.github), false,
        (cx) => this.terminal(["create"], cx)).tooltip("New issue"));
  }

  /** The filters' menu: each one, a check on the ones on; the labels those of the issues listed, the chosen one too.
   * @returns {import("./menus.js").Item[]} */
  filters(t) {
    const q = this.query;
    const listed = (this.listing?.issues ?? []).flatMap((i) => i.labels);
    const labels = [...new Set([...listed, ...(q.label ? [q.label] : [])])].sort((a, b) => a.localeCompare(b));
    return [{ label: "Assigned to me", on: q.assigned, act: (cx) => this.filter("assigned", null, cx) },
      { label: "Created by me", on: q.authored, act: (cx) => this.filter("authored", null, cx) },
      { label: "Any priority", on: this.level === null, act: (cx) => this.filter("level", null, cx) },
      ...LEVELS.map((name, n) => ({ label: `● ${name}`, on: this.level === n, color: priorityColor(t, n),
        act: (cx) => this.filter("level", n, cx) })),
      { label: "Any label", on: !q.label, act: (cx) => this.filter("label", "", cx) },
      ...labels.map((label) => ({ label, on: q.label === label, act: (cx) => this.filter("label", label, cx) }))];
  }

  /** Open and Closed, as GitHub's list has them: the chosen one filled. */
  states(t) {
    return h_flex().flex_none().px(10).pb(8).gap(6).children(Object.entries(STATES).map(([state, label]) =>
      div().id(`issues-${state}`).h(24).px(8).flex().items_center().rounded(6).text_size(12).cursor_pointer()
        .when(this.query.state === state, (e) => e.bg(t.solid).text_color(t.solid_foreground).font_bold())
        .when(this.query.state !== state, (e) => e.text_color(t.muted).hover((s) => s.bg(t.hover)))
        .on_click((_e, cx) => state !== this.query.state && this.load(cx, { ...this.query, state })).child(label)));
  }

  /** What to say above the list: busy, asking, a failure, nothing found, or what was done. @param {Listed[]} shown */
  line(shown) {
    if (this.busy) return [this.busy, "dim"];
    if (this.note) return [this.note, "dim"];
    if (this.asked) return ["Loading issues…", "dim"];
    if (!this.listing) return null;
    if (this.listing.error) return [this.listing.error, "ansi1"];
    if (shown.length) return null;
    const q = this.query, filtered = q.assigned || q.authored || q.label || this.level !== null || this.words.length;
    return [filtered ? "No issues match" : `No ${q.state} issues`, "dim"];
  }

  status(t, shown) {
    const [text, role] = /** @type {[string, string]} */ (this.line(shown));
    return div().flex_none().px(12).pb(6).text_size(11).truncate().text_color(t[role]).child(text);
  }

  /** An issue's two rows, as the TUI sidebar's: its priority's bar, its number in that color and its title; then its
   * priority, labels, assignee and how long ago it changed; with the mouse on it, to the agent and the browser; a close
   * or reopen asked about in its place. @param {Listed} issue */
  row(t, issue) {
    const key = `issue-${issue.number}`, color = issue.state === "CLOSED" ? t.muted : priorityColor(t, issue.level);
    const labels = issue.labels.filter((label) => label !== issue.ranked_by).join(", ");
    const people = issue.assignees.length ? `@${issue.assignees[0]}${issue.assignees.length > 1
      ? ` +${issue.assignees.length - 1}` : ""}` : "";
    const asking = this.confirm?.number === issue.number ? this.confirm.what : null;
    const verb = asking === "close" ? "Close" : "Reopen";
    return h_flex().id(key).h(48).flex_none().gap(8).items_center().rounded(6).cursor_pointer()
      .when(this.chosen === issue.number, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
      .on_hover(hovering(this.host, key)).on_click((_e, cx) => this.open(issue, cx))
      .on_mouse_down("right", () => this.host.menus.open(this.picks(issue)))
      .child(div().w(3).h(36).flex_none().rounded(2).when(issue.level !== null, (e) => e.bg(color)))
      .child(v_flex().flex_1().min_w(0).gap(2)
        .child(h_flex().gap(6).min_w(0).child(div().flex_none().font_bold().text_color(color).child(`#${issue.number}`))
          .child(div().flex_1().min_w(0).truncate().child(issue.title)))
        .child(h_flex().gap(6).min_w(0).text_size(11)
          .when(Boolean(issue.ranked_by), (e) => e.child(div().flex_none().text_color(color).child(issue.ranked_by)))
          .child(div().flex_1().min_w(0).truncate().text_color(t.dim).child([labels, people].filter(Boolean)
            .join("  ")))
          .child(div().flex_none().text_color(t.dim).child(issue.ago))))
      .when(Boolean(asking), (e) => e.child(h_flex().flex_none().gap(GAP).pr(6).items_center()
        .child(div().text_size(11).text_color(t.ansi1).child(`${verb}?`))
        .child(small(t, `${key}-yes`, verb, `${verb} #${issue.number} on GitHub`, !this.busy,
          (cx) => this.change(issue, /** @type {"close" | "reopen"} */ (asking), cx)))
        .child(small(t, `${key}-cancel`, "Cancel", "Leave it as it is", true, (cx) => this.unask(cx)))))
      .when(!asking && this.host.hovered === key, (e) => e.child(h_flex().flex_none().gap(GAP).pr(6)
        .child(small(t, `${key}-agent`, icon("bot"), "To agent", !this.busy, (cx) => this.toAgent(issue, cx)))
        .child(small(t, `${key}-web`, icon("external-link"), "Open in browser", true,
          (cx) => cx.open_url(issue.url)))));
  }

  /** The right click's menu on ISSUE, as the TUI sidebar's: all its keys do with it, and Assign to me.
   * @param {Listed} issue @returns {import("./menus.js").Item[]} */
  picks(issue) {
    const verb = issue.state === "CLOSED" ? "reopen" : "close";
    return [{ label: "Open", act: (cx) => this.open(issue, cx) }, { label: "Open in the browser", url: issue.url },
      { label: "To the agent", act: (cx) => this.toAgent(issue, cx) },
      { label: "Reply", act: (cx) => this.terminal(["reply", String(issue.number)], cx) },
      { label: "Assign to me", act: (cx) => this.change(issue, "assign", cx) },
      { label: verb === "close" ? "Close…" : "Reopen…", act: (cx) => this.change(issue, verb, cx) }];
  }
}

/** The issue NUMBER's Fixes line, as the TUI sidebar shows it under Commit: the next commit closes it; × unlinks it.
 * @param {[number, string]} linked @param {(cx: any) => void} unlink */
export function fixesLine(t, linked, unlink) {
  return h_flex().flex_none().px(10).pb(8).gap(6).items_center().text_size(12)
    .child(div().flex_1().min_w(0).truncate().text_color(t.accent).child(`Fixes #${linked[0]} ${linked[1]}`))
    .child(small(t, "unlink", icon("x"), "Next commit fixes no issue", true, unlink));
}
