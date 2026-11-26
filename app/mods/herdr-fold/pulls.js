// @ts-check
// Pull requests in the dock, as the TUI sidebar's: the Issues tab's Pull requests (the repository's; a press opens
// one's review in the preview tab) and Changes' row and form (the branch's; a new one's title and body by the agent).
import { div } from "gpui-kit";
import { v_flex, h_flex, Input, InputState, Textarea, TextareaState } from "gpui-base";
import { theme } from "herdr";
import { COMMIT_MESSAGE, GIT, GITHUB, ISSUES_STALE } from "./helper.js";
import { CENTRED, chipGroups, counted, filterGroups, hovering, issuesParts, listStale, ME, passes, primaryLit,
  PULL_GROUPS, pullFacets, pullSearch, said, toggled } from "./logic.js";
import { button, BUTTON, choices, field, footNote, GAP, icon, iconButton, keepNote, PAD, segmented, small, SPINNER }
  from "./parts.js";
import { chipMark, filterChips, filterMenu, funnel, keepFilters, keptFilters, MINE, sendToAgent, tabAgent }
  from "./issues.js";
import { showPreview } from "./preview.js";

const ROW = 48;                   // px: a pull request's row, as an issue's
const LOOK = 60000;               // ms between two looks at the branch's pull request while nothing changed
const AS = /** @type {[string, string][]} */ ([["draft", "Draft"], ["ready", "Ready for review"]]);
/** a review's state, core/github.py's review_state, in words and the role of their color (none: a neutral tag) */
export const REVIEW = { draft: ["Draft", null], yours: ["your review", "ansi3"],
  changes: ["changes requested", "ansi1"], approved: ["approved", "ansi2"], merged: ["merged", "muted"],
  closed: ["closed", "muted"] };
/** the checks' mark (core/github.py's pull_listed) and its color's role: passed and failed lucide's check and x,
 * running a filled dot */
export const MARKS = { passed: ["check", "ansi2"], running: ["●", "ansi3"], failed: ["x", "ansi1"] };
const [COLUMN, MARK] = CENTRED.checksMark;        // px: the checks' column, its check and x
const RUNNING = CENTRED.checksDot[1];             // px: the running checks' disc, in that column
/** the Review group's values in the filters' menu: its words and their role, as the rows' (REVIEW) in full */
const REVIEWS = { draft: ["Draft", null], yours: ["Your review", "ansi3"], approved: ["Approved", "ansi2"],
  changes: ["Changes requested", "ansi1"] };
const CHECKS = { passed: "Passing", running: "Running", failed: "Failing" };      // the Checks group's, with MARKS
const FILTER_MENU = 228;          // px: its filters' menu, issue-types.html's

/** @typedef {{ number: number, title: string, branch: string, author: string, state: string, url: string,
 * mark: string, checks_said: string, review: string, said: string, ago: string, labels?: string[],
 * assignees?: string[], authored?: boolean }} Listed */

/** A pull request's review state as one word on the right: Draft a neutral tag, the rest in their color. */
export function reviewWord(t, review) {
  const [word, role] = REVIEW[/** @type {keyof typeof REVIEW} */ (review)] ?? ["", null];
  if (!word) return div();
  return role ? div().flex_none().text_size(12).text_color(t[role]).child(word)
    : div().flex_none().h(18).px(6).flex().items_center().rounded(4).bg(t.raised).text_size(11).text_color(t.muted)
      .child(word);
}

/** The checks' mark in the mark column, 14 wide: a check in green, a dot in yellow while they run, an x in red (the
 * check and the x 12, as every icon's check, centred); its room without checks. */
export function checksMark(t, mark) {
  const [glyph, role] = MARKS[/** @type {keyof typeof MARKS} */ (mark)] ?? ["", "dim"];
  return div().w(COLUMN).flex_none().flex().items_center().justify_center().text_color(t[role])
    .when(Boolean(glyph), (e) => e.child(markGlyph(glyph, t[role])));
}

/** A checks' mark's GLYPH: the check and the x as icons, the running dot a disc of RUNNING (as the 9 px ● was) in
 * COLOR. @param {string} glyph @param {string} color */
const markGlyph = (glyph, color) => (glyph === "check" || glyph === "x" ? icon(glyph, MARK)
  : div().size(RUNNING).flex_none().rounded_full().bg(color));

export class PullsView {
  /** HOST: the view it shows in, for the repository (root, on, github), its core calls (core), the row the mouse is
   * on (hovered), and the way to Changes' form (newPull). @param {any} host */
  constructor(host) {
    this.host = host;
    const kept = keptFilters("pulls", PULL_GROUPS);
    this.state = kept.state;
    /** @type {Record<string, any[]>} the filters' values on, each group's, as Issues' */
    this.filters = kept.chosen;
    /** the query's search asked, the one the listing answers; the labels past six shown; its menu up; the funnel's */
    this.search = ""; this.answered = null; this.more = false; this.filtering = null; this.pressed = null;
    /** @type {{ pulls: Listed[], error: string | null, narrowed?: Listed[] | null, me?: string, limit?: number }
     * | null} */
    this.listing = null;
    /** @type {string | null} the query asked now; when its answer came (ms) */
    this.asked = null; this.at = null;
    /** @type {{ open: number, closed: number } | null} the repository's open and closed (and merged) ones */
    this.totals = null;
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
    Object.assign(this, { listing: null, asked: null, answered: null, at: null, chosen: null, note: null,
      totals: null });
  }

  /** The pull requests of STATE (its SEARCH too, once the list is full) asked of GitHub again, the list shown staying
   * till the answer comes; an answer for another repository or query is dropped. */
  load(cx, state = this.state, search = this.search) {
    const { root, on, github } = this.host;
    if (!github) return;
    const key = JSON.stringify([github, state, search]);
    Object.assign(this, { state, search, asked: key });
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["pulls", github, JSON.stringify({ state, search })], root, on);
        if (this.asked === key) Object.assign(this, { listing: answer, answered: search,
          totals: answer.totals ?? this.totals });
      } catch (e) {
        if (this.asked === key) this.listing = { pulls: [], error: said(e) };
      } finally {
        if (this.asked === key) {
          Object.assign(this, { asked: null, at: Date.now() });
          this.follow(cx);
          this.liveMenu();
        }
        cx.notify();
      }
    });
    cx.notify();
  }

  /** Whether its answer is older than ISSUES_STALE seconds, none on its way: asked again while it shows. */
  stale() {
    return listStale(this.at, Date.now(), Boolean(this.asked), ISSUES_STALE);
  }

  /** Whether the latest answer filled its LIMIT (the menu counts the latest LIMIT, its search asked for the rest). */
  full() {
    return Boolean(this.listing && !this.listing.error && this.listing.pulls.length >= (this.listing.limit ?? 100));
  }

  /** The list asked again where the values on want another search (or none), once it is full. */
  follow(cx) {
    const search = this.full() ? pullSearch(this.filters) : "";
    if (search !== this.search) this.load(cx, this.state, search);
  }

  /** The facets its menu counts and its rows narrow by. @param {Listed[]} [rows] */
  facets(rows = this.listing?.pulls ?? []) {
    return rows.map((pull) => pullFacets(pull, this.listing?.me ?? ""));
  }

  /** @returns {Listed[]} the answer's (its search's, once asked) the filters keep that hold every word typed */
  shown() {
    const listing = this.listing, narrowed = listing?.narrowed && this.answered === this.search;
    const rows = (narrowed ? listing?.narrowed : listing?.pulls) ?? [];
    const facets = this.facets(rows);
    return rows.filter((pull, n) => this.words.every((w) => pull.said.includes(w)) && passes(facets[n], this.filters));
  }

  /** GROUP's VALUE turned on, or off when on, the menu staying open, as Issues'. @param {string} group
   * @param {any} value */
  toggle(group, value, cx) {
    this.filters = toggled(this.filters, group, value);
    this.changed(cx);
  }

  /** The values on changed (kept): narrowed, its search asked where it is full, the menu's counts anew. */
  changed(cx) {
    keepFilters("pulls", this.state, this.filters);
    this.follow(cx);
    this.liveMenu();
    cx.notify();
  }

  /** GROUP's chip taken off. @param {string} group */
  drop(group, cx) {
    this.filters = { ...this.filters, [group]: [] };
    this.changed(cx);
  }

  /** Every filter off. */
  clear(cx) {
    this.filters = Object.fromEntries(PULL_GROUPS.map((group) => [group, []]));
    this.changed(cx);
  }

  /** How a filter's VALUE reads in GROUP: a review's word in its row's color, the checks' mark.
   * @param {string} group @param {any} value @returns {{ words: string, mark: any, color?: string }} */
  look(t, group, value) {
    if (ME.includes(group)) return { words: MINE[/** @type {keyof typeof MINE} */ (group)], mark: null };
    if (group === "review") {
      const [words, role] = REVIEWS[/** @type {keyof typeof REVIEWS} */ (value)];
      return { words, mark: null, ...(role ? { color: t[role] } : {}) };
    }
    if (group === "checks") {
      const [glyph, role] = MARKS[/** @type {keyof typeof MARKS} */ (value)];
      return { words: CHECKS[/** @type {keyof typeof CHECKS} */ (value)], mark: glyph === "●"
        ? { text: glyph, color: t[role] } : { icon: glyph, color: t[role] } };
    }
    return { words: String(value), mark: null };
  }

  /** Its filters' menu, as Issues': Assigned to me, Created by me, Review, Checks, Label.
   * @returns {(import("./menus.js").Item | null)[]} */
  filterItems(t) {
    return filterMenu(t, filterGroups(this.facets(), this.filters, PULL_GROUPS, this.more),
      (group, value) => this.look(t, group, value), (group, value, cx) => this.toggle(group, value, cx), () => {
        this.more = true;
        this.liveMenu();
      }, this.full() ? this.listing?.limit ?? 100 : 0);
  }

  /** The funnel's menu opened under it (BOUNDS: its press's). @param {any} bounds */
  openFilters(t, bounds) {
    this.more = false;
    const menus = this.host.menus;
    menus.open(this.filterItems(t), bounds, undefined,
      { width: FILTER_MENU, find: filterGroups(this.facets(), this.filters, PULL_GROUPS).find ? "Find" : undefined });
    this.filtering = menus.overlay;
  }

  /** Its filters' menu, while it is up, made anew. */
  liveMenu() {
    const menus = this.host.menus;
    if (!this.filtering || menus.overlay !== this.filtering || !menus.up) return void (this.filtering = null);
    menus.update(this.filterItems(theme()));
    this.filtering = menus.overlay;
  }

  /** Whether its filters' menu is up. */
  menuUp() {
    return Boolean(this.filtering && this.host.menus.overlay === this.filtering && this.host.menus.up);
  }

  /** The chips of what is on, as Issues'. @returns {[string, any, string, any][]} */
  chips(t) {
    return chipGroups(this.filters, PULL_GROUPS).map(({ group, values }) => {
      const looks = values.map((value) => this.look(t, group, value));
      return [group, looks[0].mark && chipMark(looks[0].mark), looks.map((one) => one.words).join(", "),
        (/** @type {any} */ cx) => this.drop(group, cx)];
    });
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
    const filtered = Object.values(this.filters).some((values) => values.length);
    const { refresh, say } = issuesParts({ asked: Boolean(this.asked), listing: this.listing, shown: shown.length,
      state: this.state, filtered: filtered || Boolean(this.words.length), noun: "pull requests" });
    const press = (/** @type {any} */ e) => (this.pressed = e.bounds);
    return v_flex().size_full().min_h(0)
      .child(h_flex().flex_none().p(PAD).pb(6).gap(6).items_center()
        .child(field(t, "pull-search", this.find, funnel(t, "pull-filters", filtered, this.menuUp(), press,
          () => this.openFilters(t, this.pressed))).flex_1().min_w(0).on_key_down((e, cx) => {
          const last = chipGroups(this.filters, PULL_GROUPS).at(-1);
          if (e.key === "backspace" && !this.find.value() && last) this.drop(last.group, cx);
        }))
        .child(button(t, "pull-new", icon("plus", 15), Boolean(this.host.github), false,
          (cx) => this.host.newPull(cx)).tooltip("New pull request: in Changes")))
      .when(filtered, (e) => e.child(filterChips(t, "pull-chips", this.chips(t), (cx) => this.clear(cx))))
      .child(h_flex().flex_none().pl(PAD).pr(PAD / 2).pb(8).gap(GAP).items_center()
        .child(choices(t, "pulls", counted(this.totals), this.state, (state, cx) => {
          keepFilters("pulls", state, this.filters);
          this.load(cx, state, "");
        }))
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
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child("No pull request"))
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
      .child(h_flex().flex_wrap().gap(8).items_center().justify_end()      // the one button at the right end
        .child(small(t, "pull-cancel", "Cancel", "Open none", true, (cx) => this.cancel(cx)))
        .child(button(t, "pull-open", form.busy ? "Opening…" : form.draft ? "Create draft pull request"
          : "Create pull request", ready, primaryLit(ready, form.busy), (cx) => this.create(cx))
          .max_w("100%").truncate()));                // narrow: on a line of its own, never past the dock's edge
  }
}
