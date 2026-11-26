// @ts-check
// The Issues view, as the TUI sidebar's: issues by priority, each one's type an icon before its number, the funnel's
// filters; a click previews one, its buttons and menu: to the agent, the browser, reply, assign, set, close, reopen.
import { div } from "gpui-kit";
import { v_flex, h_flex, InputState } from "gpui-base";
import { agents, focused, hc, setShared, shared, spaces, terminals, theme, run as command } from "herdr";
import { newAgentIn } from "./chat.js";
import { COMMIT_MESSAGE, GITHUB, ISSUES_STALE } from "./helper.js";
import { CENTRED, chipGroups, counted, filterGroups, hovering, issueAgent, issueFacets, issueSearch, issueSet,
  ISSUE_GROUPS, issuesParts, LEVELS, listStale, ME, passes, priorityColor, said, toggled, TYPE_ICON, TYPES }
  from "./logic.js";
import { BUTTON, button, choices, field, footNote, GAP, icon, iconButton, keepNote, PAD, small, SPINNER }
  from "./parts.js";
import { showPreview } from "./preview.js";

const BUSY = { close: "Closing…", reopen: "Reopening…", assign: "Assigning…" };
const DONE = { close: "Closed", reopen: "Reopened", assign: "Assigned to you:" };
const ROW = 48;                   // px: an issue's row, and what is said in the first one's place
const [LINE, TYPE] = CENTRED.typeIcon;     // px: its title's line, a type's icon in a column of its own on it
const UNDER = 16;                 // px: the line under the title; with the gap, its bar's 36
const FILTERS = "herdr-fold.issue-filters";      // shared: each list's state and the values on, as the TUI keeps them
const FILTER_MENU = 220;          // px: the filters' menu, issue-types.html's
const SET_MENU = 236;             // px: Priority… and Type…, the issue's number and title in its head
export const NAMES = { level: "Priority", type: "Type", label: "Label", review: "Review", checks: "Checks" };
export const MINE = { assigned: "Assigned to me", authored: "Created by me" };
const done = (/** @type {string} */ text) => ({ text, error: false });          // a Note of what was under way
const made = (/** @type {string} */ text) => ({ text, error: false, done: true });   // of a change made
const failed = (/** @type {string} */ text) => ({ text, error: true });         // and of what went wrong

/** @typedef {{ number: number, title: string, labels: string[], assignees: string[], state: string, url: string,
 * level: number | null, ranked_by: string | null, priority: string, issue_type: string, node: string, author: string,
 * type: string, typed_by: string | null, shown: string[], said: string, ago: string }} Listed */
/** @typedef {{ issues: Listed[], error: string | null, narrowed?: Listed[] | null, settable?: any, me?: string,
 * limit?: number }} Listing */

/** A list's filters as they were kept (LIST: issues or pulls), its GROUPS each a list. @param {string} list
 * @param {string[]} groups */
export function keptFilters(list, groups) {
  const kept = /** @type {any} */ (shared(FILTERS))?.[list] ?? {};
  const chosen = Object.fromEntries(groups.map((group) => [group, Array.isArray(kept.chosen?.[group])
    ? kept.chosen[group] : []]));
  return { state: kept.state === "closed" ? "closed" : "open", chosen };
}

/** LIST's state and CHOSEN values kept for its next copy. @param {string} list @param {string} state
 * @param {any} chosen */
export const keepFilters = (list, state, chosen) => setShared(FILTERS, { .../** @type {any} */ (shared(FILTERS) ?? {}),
  [list]: { state, chosen } });

/** The funnel at the field's end: in the accent while a filter is ON, its press opening the menu (OPEN: on the hover
 * fill while it is up); 24 square in the field's 30, the icon 14 in it (5 round). @param {string} id
 * @param {(e: any) => void} press @param {() => void} act */
export const funnel = (t, id, on, open, press, act) => div().id(id).size(CENTRED.funnel[1]).flex_none().flex()
  .items_center()
  .justify_center().rounded(6).cursor_pointer().text_color(on ? t.accent : t.muted).when(open, (e) => e.bg(t.hover))
  .hover((s) => s.bg(t.hover).text_color(on ? t.accent : t.foreground)).tooltip("Filters")
  .on_mouse_down("left", (e, cx) => {
    cx.stop_propagation();
    press(e);
  }).on_click(() => act()).child(icon("list-filter", CENTRED.funnelIcon[1]));

/** What is on, a chip a group (CHIPS: [id, mark, words, ×]), Clear at the row's end (issue-types.html's .fc): 22 high,
 * its words 8 in and 6 after its mark, the × 12 in a 16 square 6 after them and 4 from the end. @param {string} id
 * @param {[string, any, string, (cx: any) => void][]} chips @param {(cx: any) => void} clear */
export const filterChips = (t, id, chips, clear) => h_flex().id(id).flex_none().flex_wrap().px(PAD).pb(8).gap(6)
  .items_center().children(chips.map(([key, mark, words, drop]) => h_flex().id(`${id}-${key}`).h(CENTRED.chip[0])
    .pl(8).pr(2)
    .flex_none().items_center().rounded(6).bg(t.raised).text_size(12)
    .child(h_flex().gap(6).items_center().when(Boolean(mark), (e) => e.child(mark)).child(div().child(words)))
    .child(div().id(`${id}-${key}-x`).size(CENTRED.chipX[0]).ml(4).flex_none().flex().items_center().justify_center()
      .rounded(4)
      .cursor_pointer().text_color(t.dim).hover((s) => s.bg(t.hover).text_color(t.foreground)).tooltip("Remove")
      .on_click((_e, cx) => drop(cx)).child(icon("x", CENTRED.chipX[1])))))
  .child(div().flex_1())
  .child(div().id(`${id}-clear`).text_size(12).text_color(t.muted).cursor_pointer()
    .hover((s) => s.text_color(t.foreground)).on_click((_e, cx) => clear(cx)).child("Clear"));

/** A filter's mark in a chip: the menu's (a dot in its color, an icon), 14 square. @param {any} mark */
export const chipMark = (mark) => div().size(CENTRED.chipMark[1]).flex_none().flex().items_center().justify_center()
  .text_color(mark.color).when(Boolean(mark.icon), (e) => e.child(icon(mark.icon, CENTRED.chipMark[1])))
  .when(Boolean(mark.text), (e) => e.text_size(11).child(mark.text));

export class IssuesView {
  /** HOST: the view it shows in, for the repository (root, on, github), its core calls (core), the row the mouse is
   * on (hovered) and the Changes' link (linked). @param {any} host */
  constructor(host) {
    this.host = host;
    const kept = keptFilters("issues", ISSUE_GROUPS);
    this.query = { state: kept.state, search: "" };
    /** @type {Record<string, any[]>} the filters' values on, each group's (Assigned to me, Created by me: [true]) */
    this.filters = kept.chosen;
    /** the labels past the first six shown in the menu; the menu up (its popup), the funnel's press */
    this.more = false; this.filtering = null; this.pressed = null;
    /** @type {Listing | null} */
    this.listing = null;
    /** @type {string | null} the query asked now; the one the listing answers; when it came (ms) */
    this.asked = null; this.answered = null; this.at = null;
    /** @type {{ open: number, closed: number } | null} the repository's open and closed issues, as last told */
    this.totals = null;
    this.find = InputState.new({ placeholder: "Filter issues" });
    this.words = [];
    this.find.on("change", (_e, cx) => {
      this.words = this.find.value().toLowerCase().split(/\s+/).filter(Boolean);
      cx.notify();
    });
    /** @type {number | null} the issue last opened, marked */
    this.chosen = null;
    /** @type {{ number: number, what: string } | null} the close or reopen asked about first */
    this.confirm = null;
    /** @type {import("./parts.js").Note | null} what was done last, or went wrong; what is under way */
    this.note = null; this.busy = null;
  }

  /** Another repository's: nothing of this one's listed or chosen (the filters stay, as in the TUI sidebar). */
  reset() {
    Object.assign(this, { listing: null, asked: null, answered: null, at: null, chosen: null, confirm: null,
      note: null, totals: null });
  }

  /** The issues of QUERY (the one chosen by default) asked of GitHub again, the list shown staying (and where it is
   * scrolled) till the answer comes; an answer for another query is dropped; then its search asked, once it is full. */
  load(cx, query = this.query) {
    const { root, on, github } = this.host;
    if (!github) return;
    const key = JSON.stringify([github, query]);
    this.query = query;
    this.asked = key;
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["issues", github, JSON.stringify(query)], root, on);
        if (this.asked === key) Object.assign(this, { listing: answer, answered: query.search,
          totals: answer.totals ?? this.totals });
      } catch (e) {
        if (this.asked === key) this.listing = { issues: [], error: said(e) };
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

  /** Whether its answer is older than ISSUES_STALE seconds, none on its way: asked again while it shows, as the TUI's
   * (a new issue on GitHub shows up). */
  stale() {
    return listStale(this.at, Date.now(), Boolean(this.asked), ISSUES_STALE);
  }

  /** Whether the latest answer filled its LIMIT: the menu counts the latest LIMIT, its search asked for the rest. */
  full() {
    return Boolean(this.listing && !this.listing.error && this.listing.issues.length >= (this.listing.limit ?? 100));
  }

  /** The list asked again where the values on want another search (or none), once it is full. */
  follow(cx) {
    const search = this.full() ? issueSearch(this.filters) : "";
    if (search !== this.query.search) this.load(cx, { ...this.query, search });
  }

  /** The facets the menu counts and the rows narrow by: the latest answer's, its search's once that is the one asked.
   * @param {Listed[]} [rows] */
  facets(rows = this.listing?.issues ?? []) {
    return rows.map((issue) => issueFacets(issue, this.listing?.me ?? ""));
  }

  /** The issues shown: the answer's (its search's, once asked) the filters keep that hold every word typed.
   * @returns {Listed[]} */
  shown() {
    const listing = this.listing, narrowed = listing?.narrowed && this.answered === this.query.search;
    const rows = (narrowed ? listing?.narrowed : listing?.issues) ?? [];
    const facets = this.facets(rows);
    return rows.filter((issue, n) => this.words.every((w) => issue.said.includes(w))
      && passes(facets[n], this.filters));
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

  /** WORK with LABEL on the foot's line meanwhile; its answer there (done, failed, or none), the list asked again. */
  act(cx, label, work) {
    if (this.busy) return;
    this.busy = label;
    keepNote(this, null, cx);
    cx.spawn(async (cx) => {
      let note = null;
      try {
        note = await work(cx);
      } catch (e) {
        note = failed(said(e));
      } finally {
        this.busy = null;
        keepNote(this, note, cx);
        this.load(cx);
      }
    });
  }

  /** ISSUE to the focused tab's Claude or Codex (a pane's, or its chat's) with core/github.py's prompt for it, else to
   * a new agent as + starts one (a chat, or a terminal), and linked to the next commit (its Fixes line in Changes), as
   * the TUI sidebar's t does. @param {Listed} issue */
  toAgent(issue, cx) {
    const agent = tabAgent();
    this.act(cx, "Sending…", async () => {
      const { root, on, github } = this.host;
      const { prompt } = await this.host.core(GITHUB, ["prompt", github, String(issue.number)], root, on);
      const to = await sendToAgent(agent, prompt, root);
      const answer = await this.host.core(COMMIT_MESSAGE, ["link", root, String(issue.number), issue.title], root, on);
      this.host.linked = answer.linked;
      return done(`${to}: #${issue.number}`);
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
      return answer.ok ? made(`${DONE[what]} #${issue.number}`) : failed(answer.advice);
    });
  }

  /** ISSUE's priority or type (WHAT) set to VALUE (an option's or a type's id; null: none, WORDS its name): its row as
   * set at once, then asked of GitHub; a failure says why on the foot's line, and the list is asked again.
   * @param {Listed} issue @param {"priority" | "type"} what @param {string | null} value @param {string} words */
  set(issue, what, value, words, cx) {
    const listing = this.listing;
    if (!listing || this.busy) return;
    const changed = issueSet(issue, what === "priority" ? { priority: value ? words : "" }
      : { issue_type: value ? words : "" });
    const swap = (/** @type {Listed[] | null | undefined} */ rows) => rows?.map((one) => (one.number === issue.number
      ? changed : one)) ?? rows;
    this.listing = { ...listing, issues: swap(listing.issues) ?? [], narrowed: swap(listing.narrowed) };
    const { root, on } = this.host, field = listing.settable?.field ?? "";
    keepNote(this, null, cx);
    cx.spawn(async (cx) => {
      try {
        const answer = await this.host.core(GITHUB, ["set", JSON.stringify({ issue: issue.node, what, value,
          field })], root, on);
        if (!answer.ok) throw new Error(answer.advice);
        keepNote(this, made(`Set #${issue.number} to ${words}`), cx);
      } catch (e) {
        keepNote(this, failed(said(e)), cx);
        this.load(cx);
      }
    });
    cx.notify();
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

  // --- the filters

  /** GROUP's VALUE turned on, or off when on, the menu staying open; narrowed at once (asked again where the list is
   * full and its search must widen). @param {string} group @param {any} value */
  toggle(group, value, cx) {
    this.filters = toggled(this.filters, group, value);
    this.changed(cx);
  }

  /** The values on changed (kept for the next copy): the list narrowed, its search asked, the menu's counts anew. */
  changed(cx) {
    keepFilters("issues", this.query.state, this.filters);
    this.follow(cx);
    this.liveMenu();
    cx.notify();
  }

  /** GROUP's chip taken off (its ×, or Backspace in the empty field for the last). @param {string} group */
  drop(group, cx) {
    this.filters = { ...this.filters, [group]: [] };
    this.changed(cx);
  }

  /** Every filter off (the chips' Clear). */
  clear(cx) {
    this.filters = Object.fromEntries(ISSUE_GROUPS.map((group) => [group, []]));
    this.changed(cx);
  }

  /** How a filter's VALUE reads in GROUP: its words, its mark (a priority's dot, a type's icon), its words' color.
   * @param {string} group @param {any} value @returns {{ words: string, mark: any, color?: string }} */
  look(t, group, value) {
    if (ME.includes(group)) return { words: MINE[/** @type {keyof typeof MINE} */ (group)], mark: null };
    if (group === "level") return { words: LEVELS[value], mark: { text: "●", color: priorityColor(t, value) },
      color: priorityColor(t, value) };
    if (group === "type") return { words: value, mark: TYPES.includes(value) ? { icon: TYPE_ICON[
      /** @type {keyof typeof TYPE_ICON} */ (value)], color: t.muted } : null };
    return { words: String(value), mark: null };
  }

  /** The filters' menu (issue-types.html's): Assigned to me and Created by me, then each group in the list with its
   * values and how many would stay; the menu stays open while they are pressed.
   * @returns {(import("./menus.js").Item | null)[]} */
  filterItems(t) {
    return filterMenu(t, filterGroups(this.facets(), this.filters, ISSUE_GROUPS, this.more),
      (group, value) => this.look(t, group, value), (group, value, cx) => this.toggle(group, value, cx),
      () => this.showMore(), this.full() ? this.listing?.limit ?? 100 : 0);
  }

  /** The labels past the first six shown: the menu opened again where it is, as tall as they need. */
  showMore() {
    this.more = true;
    this.liveMenu();
  }

  /** The funnel's menu opened under it (BOUNDS: its press's). @param {any} bounds */
  openFilters(t, bounds) {
    this.more = false;
    const menus = this.host.menus;
    menus.open(this.filterItems(t), bounds, undefined,
      { width: FILTER_MENU, find: filterGroups(this.facets(), this.filters, ISSUE_GROUPS).find ? "Find" : undefined });
    this.filtering = menus.overlay;
  }

  /** The filters' menu, while it is up, made anew (a value turned, an answer came, its labels shown). */
  liveMenu() {
    const menus = this.host.menus;
    if (!this.filtering || menus.overlay !== this.filtering || !menus.up) return void (this.filtering = null);
    menus.update(this.filterItems(theme()));
    this.filtering = menus.overlay;
  }

  /** Whether the filters' menu is up (the funnel on the hover fill). */
  menuUp() {
    return Boolean(this.filtering && this.host.menus.overlay === this.filtering && this.host.menus.up);
  }

  render(t) {
    const shown = this.shown(), q = this.query, foot = this.busy ? done(this.busy) : this.note;
    const filtered = Object.values(this.filters).some((values) => values.length), slot = this.slotted();
    const parts = issuesParts({ asked: Boolean(this.asked), listing: this.listing, shown: shown.length, state: q.state,
      filtered: filtered || Boolean(this.words.length) });
    return v_flex().size_full().min_h(0)
      .child(this.field(t, filtered))
      .when(filtered, (e) => e.child(filterChips(t, "issue-chips", this.chips(t), (cx) => this.clear(cx))))
      .child(this.states(t, parts))
      .child(v_flex().id("issues").flex_1().min_h(0).overflow_y_scrollbar().px(PAD / 2).pb(PAD / 2)
        .when(Boolean(parts.say), (e) => e.child(this.say(t, parts.say)))
        .children(shown.map((issue) => this.row(t, issue, slot))))
      .when(Boolean(foot), (e) => e.child(footNote(t, foot)));
  }

  /** The chips of what is on: [its group, its mark, its words, its ×]. @returns {[string, any, string, any][]} */
  chips(t) {
    return chipGroups(this.filters, ISSUE_GROUPS).map(({ group, values }) => {
      const looks = values.map((value) => this.look(t, group, value));
      return [group, looks[0].mark && chipMark(looks[0].mark), looks.map((one) => one.words).join(", "),
        (/** @type {any} */ cx) => this.drop(group, cx)];
    });
  }

  /** The filter field with its funnel, Backspace in it while empty taking the last chip off, and the new issue's
   * button, as the TUI sidebar has them on one line. @param {boolean} filtered */
  field(t, filtered) {
    const press = (/** @type {any} */ e) => (this.pressed = e.bounds);
    return h_flex().flex_none().p(PAD).pb(6).gap(6).items_center()
      .child(field(t, "issue-search", this.find, funnel(t, "issue-filters", filtered, this.menuUp(), press,
        () => this.openFilters(t, this.pressed))).flex_1().min_w(0).on_key_down((e, cx) => {
        const last = chipGroups(this.filters, ISSUE_GROUPS).at(-1);
        if (e.key === "backspace" && !this.find.value() && last) this.drop(last.group, cx);
      }))
      .child(button(t, "issue-new", icon("plus", 15), Boolean(this.host.github), false,
        (cx) => this.terminal(["create"], cx)).tooltip("New issue"));
  }

  /** Open and Closed, as GitHub's list has them (the chosen one filled), and the refresh at their row's end: a
   * spinner in its place, as big, while a list shown is asked for again (PARTS, logic.js's issuesParts). */
  states(t, parts) {
    return h_flex().flex_none().pl(PAD).pr(PAD / 2).pb(8).gap(GAP).items_center()
      .child(choices(t, "issues", counted(this.totals), this.query.state, (state, cx) => {
        keepFilters("issues", state, this.filters);
        this.load(cx, { state, search: "" });
      }))
      .child(div().flex_1())
      .child(parts.refresh === "spinner"
        ? div().id("issue-loading").size(BUTTON).flex_none().flex().items_center().justify_center()
          .text_size(15).text_color(t.muted).tooltip("Loading issues…").child(div().frames(SPINNER, 100))
        : iconButton(t, "issue-refresh", "refresh-cw", "Refresh", (cx) => this.load(cx)));
  }

  /** SAY's words and their role in the first row's place, as tall as a row: the rows take it in place.
   * @param {[string, string]} say */
  say(t, [text, role]) {
    return h_flex().min_h(ROW).flex_none().px(PAD / 2).py(6).items_center().text_size(12).text_color(t[role])
      .child(text);
  }

  /** Whether the rows keep a type's icon column: any issue listed has a type with an icon, so the numbers stand in one
   * column; none, and a row is as a list without types. */
  slotted() {
    const listing = this.listing;
    return [...listing?.issues ?? [], ...listing?.narrowed ?? []].some((issue) => TYPES.includes(issue.type));
  }

  /** An issue's two rows, as the TUI sidebar's: its bar, its type's icon (SLOT: the list keeps its column), number and
   * title; its priority, an icon-less type's word, labels, assignee, age; on hover To agent and the browser; a close
   * asked in its place; a closed one's marks muted. @param {Listed} issue @param {boolean} slot */
  row(t, issue, slot) {
    const key = `issue-${issue.number}`, color = issue.state === "CLOSED" ? t.muted : priorityColor(t, issue.level);
    const iconed = TYPES.includes(issue.type);
    const people = issue.assignees.length ? `@${issue.assignees[0]}${issue.assignees.length > 1
      ? ` +${issue.assignees.length - 1}` : ""}` : "";
    const asking = this.confirm?.number === issue.number ? this.confirm.what : null;
    const verb = asking === "close" ? "Close" : "Reopen";
    return h_flex().id(key).h(ROW).flex_none().px(PAD / 2).gap(8).items_center().rounded(6).cursor_pointer()
      .when(this.chosen === issue.number, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
      .on_hover(hovering(this.host, key)).on_click((_e, cx) => this.open(issue, cx))
      .on_mouse_down("right", (e) => this.host.menus.open(this.picks(t, issue), undefined, undefined,
        { point: e.position }))
      .child(div().w(3).h(LINE + 2 + UNDER).flex_none().rounded_full().when(issue.level !== null, (e) => e.bg(color)))
      .when(slot, (e) => e.child(v_flex().w(TYPE).h(LINE + 2 + UNDER).flex_none()
        .child(div().h(LINE).flex_none().flex().items_center().justify_center()
          .when(iconed, (e) => e.child(icon(TYPE_ICON[/** @type {keyof typeof TYPE_ICON} */ (issue.type)], TYPE)
            .text_color(t.muted))))))
      .child(v_flex().flex_1().min_w(0).gap(2)
        .child(h_flex().h(LINE).gap(6).min_w(0).items_center()
          .child(div().flex_none().font_bold().text_color(color).child(`#${issue.number}`))
          .child(div().flex_1().min_w(0).truncate().child(issue.title)))
        .child(h_flex().h(UNDER).gap(6).min_w(0).items_center().text_size(11)
          .when(Boolean(issue.ranked_by), (e) => e.child(div().flex_none().text_color(color).child(issue.ranked_by)))
          .child(div().flex_1().min_w(0).truncate().text_color(t.dim).child([iconed ? "" : issue.type,
            issue.shown.join(", "), people].filter(Boolean).join(" · ")))
          .child(div().flex_none().text_color(t.dim).child(issue.ago))))
      .when(Boolean(asking), (e) => e.child(h_flex().flex_none().gap(GAP).items_center()
        .child(div().text_size(11).text_color(t.ansi1).child(`${verb}?`))
        .child(small(t, `${key}-yes`, verb, `${verb} #${issue.number} on GitHub`, !this.busy,
          (cx) => this.change(issue, /** @type {"close" | "reopen"} */ (asking), cx)))
        .child(small(t, `${key}-cancel`, "Cancel", "Leave it as it is", true, (cx) => this.unask(cx)))))
      .when(!asking && this.host.hovered === key, (e) => e.child(h_flex().flex_none().gap(GAP)
        .child(small(t, `${key}-agent`, icon("bot"), "To agent", !this.busy, (cx) => this.toAgent(issue, cx)))
        .child(small(t, `${key}-web`, icon("external-link"), "Open in browser", true,
          (cx) => cx.open_url(issue.url)))));
  }

  /** The right click's menu on ISSUE, as the TUI sidebar's: all its keys do with it, Assign to me, and Priority… and
   * Type… where the organization has the field or types and the user a role that sets them, each a second menu in
   * this one's place. @param {Listed} issue @returns {(import("./menus.js").Item | null)[]} */
  picks(t, issue) {
    const verb = issue.state === "CLOSED" ? "reopen" : "close", settable = this.listing?.settable;
    return [{ label: "Open", act: (cx) => this.open(issue, cx) }, { label: "Open in the browser", url: issue.url },
      { label: "To the agent", act: (cx) => this.toAgent(issue, cx) },
      { label: "Reply", act: (cx) => this.terminal(["reply", String(issue.number)], cx) },
      { label: "Assign to me", act: (cx) => this.change(issue, "assign", cx) },
      ...(settable?.options?.length ? [{ label: "Priority…", act: () => this.setMenu(t, issue, "priority") }] : []),
      ...(settable?.types?.length ? [{ label: "Type…", act: () => this.setMenu(t, issue, "type") }] : []),
      { label: verb === "close" ? "Close…" : "Reopen…", act: (cx) => this.change(issue, verb, cx) }];
  }

  /** Priority… or Type… (WHAT) of ISSUE: a second menu where the right click's was, its head the issue's number and
   * title with what it sets, then none of them and the options, a check on the one it has.
   * @param {Listed} issue @param {"priority" | "type"} what */
  setMenu(t, issue, what) {
    this.host.menus.chain(setItems(t, issue, what, this.listing?.settable,
      (value, words, cx) => this.set(issue, what, value, words, cx)),
    { label: `#${issue.number} ${issue.title}`, note: what === "priority" ? "Priority" : "Type" }, { width: SET_MENU });
  }
}

/** The chained menu of ISSUE's priority or type (WHAT) from SETTABLE (core's): a rule, "No priority" (where the dots
 * stand) or "No type", each option (a priority's dot in its color); PICK sets it. @param {any} issue @param {any} pick
 * @param {any} settable @param {"priority" | "type"} what */
export function setItems(t, issue, what, settable, pick) {
  const current = what === "priority" ? issue.priority : issue.issue_type;
  const options = /** @type {[string, string][]} */ ((what === "priority" ? settable?.options : settable?.types)
    ?? []);
  const none = what === "priority" ? "No priority" : "No type";
  const rank = (/** @type {string} */ words) => LEVELS.findIndex((name) => name.toLowerCase() === words.toLowerCase());
  return [null, { label: none, on: !current, wide: true, act: (cx) => pick(null, none.toLowerCase(), cx) },
    ...options.map(([id, words]) => ({ label: words, on: current === words, act: (/** @type {any} */ cx) =>
      pick(id, words, cx), ...(what === "priority" && rank(words) >= 0
      ? { mark: { text: "●", color: priorityColor(t, rank(words)) } } : {}) }))];
}

/** A filters' menu from GROUPS (filterGroups'): the two of yours, each group's name and values with their counts (a
 * zero faint), past six labels "N more", the foot of the latest LIMIT's (0: none); LOOK reads, TOGGLE turns, MORE
 * shows. @param {any} groups @param {any} look @param {any} toggle @param {any} more @param {number} limit */
export function filterMenu(t, groups, look, toggle, more, limit) {
  /** @type {(import("./menus.js").Item | null)[]} */
  const items = groups.mine.map((/** @type {any} */ { group, on }) => ({ label: look(group, true).words, on,
    keep: true, act: (/** @type {any} */ cx) => toggle(group, true, cx) }));
  for (const { group, values, hidden } of groups.groups) {
    items.push({ label: NAMES[/** @type {keyof typeof NAMES} */ (group)], group: true });
    for (const { value, count, on, hidden: past } of values) {
      const { words, mark, color } = look(group, value);
      items.push({ label: words, on, keep: true, note: String(count), faint: !count, hidden: past,
        act: (cx) => toggle(group, value, cx), ...(mark ? { mark } : {}), ...(color ? { color } : {}) });
    }
    if (hidden) items.push({ label: `${hidden} more`, more: true, keep: true, color: t.muted, act: () => more() });
  }
  if (limit) items.push(null, { label: `Counts from the latest ${limit}`, group: true });
  return items;
}

/** The focused tab's Claude or Codex (a pane's, or its chat's), or null: where To agent sends. */
export const tabAgent = () => issueAgent(agents(), focused()?.tab, terminals());

/** PROMPT to AGENT (tabAgent's), else to a new agent as + starts one (a chat, or a terminal) in ROOT: where it went,
 * in words (Sent to Claude); an error when it was not sent. @param {any} agent @param {string} prompt */
export async function sendToAgent(agent, prompt, root) {
  if (agent) {
    const sent = await hc(["send", agent.address, prompt]);
    if (sent.code !== 0) throw new Error((sent.stderr || sent.stdout).trim() || "not sent");
    if (!agent.chat) command("agent.focus", { terminal: agent.address });       // a chat's is in front already
    return `Sent to ${agent.program?.name ?? "the agent"}`;
  }
  const space = spaces().find((s) => s.active);
  if (!space) throw new Error("No space to start an agent in");
  const opened = await newAgentIn(space, prompt, root);
  return opened === "chat" ? "Sent to a new chat" : `Sent to a new ${opened}`;
}

/** The issue the next commit closes (LINKED: its number, its title), in the message field's end: Fixes #N in the
 * accent, its title in the tip; × unlinks it. Inside the field, so it moves nothing.
 * @param {[number, string]} linked @param {(cx: any) => void} unlink */
export function fixesChip(t, linked, unlink) {
  return h_flex().id("fixes").flex_none().gap(2).items_center().text_size(11)
    .tooltip(`Fixes #${linked[0]} ${linked[1]}: the next commit closes it`)
    .child(div().text_color(t.accent).child(`Fixes #${linked[0]}`))
    .child(small(t, "unlink", icon("x", 12), "Next commit fixes no issue", true, unlink));
}
