// @ts-check
// The Agents tab's Usage (usage.html's Riport): the filters, the summary row, each day by model, a month against its
// budget, the projects, two tables. The figures and words are core's (report.py), the marks' places report.js's.
import { div, PathBuilder } from "gpui-kit";
import { h_flex, v_flex, Input, InputState, Popover, ScrollHandle } from "gpui-base";
import { home, notify, readTextFile, spaces, writeTextFile } from "herdr";
import { reopenChat } from "./chats.js";
import { AGENT_STATE, COMMITS, REPORT, TOKENS } from "./helper.js";
import { chosenFill, toneInk, usageAgents } from "./layers.js";
import { said } from "./logic.js";
import { listNote, panelRow, panelSurface } from "./menus.js";
import { actButton, BUTTON, icon, PAD, savePanel, segmented, spinner, swatch } from "./parts.js";
import { amountTyped, axisLabels, budgetRows, columns, conversationCells, indexed, markedRow, modelCells, monthLine,
  PERIOD, projectBars, reportArgs, summaryCells, ticks, tipFor } from "./report.js";

const POLL = 60000;                // ms between two reads while it shows
const AGENTS_EVERY = 300000;       // ms the agents' plans are kept before they are asked again
const WIDE = 1000;                 // px: the report's column at most, usage.html's .rcol
const APART = 20;                  // px between two of its blocks
const PLOT = 180, GUTTER = 40;     // px: the days' plot's height, its ticks' column (usage.html's .plot, .ytick)
const COLUMN = 24, SLOT = "70%";   // px: a day's column at most; its share of its day's room where that is narrow
const NAMED = 10;                  // days named under their columns at most: past them every few
const HEAD = 20, FOOT = 20;        // px over and under the month's plot: the budget's words, the days' names
const CLEAR = 20;                  // px from the pace's end to its words
const HALF = 320;                  // px: the month and the projects side by side from this much room each
const TIP = 168;                   // px: a day's tip at least
const MONTH = 170;                 // px: the month's plot's height
const DOT = 8, RING = 2;           // px: today's point, the surface's ring round it
const PACE = "66";                 // the pace's line: its model's color at 40%
const NAMES = 90, BAR = 0.7;       // px: the projects' names' column; the longest bar's share of its room
const BUDGET = 300, FIELD = 28;    // px: the budget's popover, a field's line (the Agent panel's add form's)
const LIST = 240;                  // px: the scope's list
// px: the tables' columns after the first, in core's order (report.py's COLUMNS); the first takes the rest
const TALKS = [110, 56, 52, 60, 52, 104, 150, 84], MODELS = [150, 70, 90, 90, 70, 110];
const FIRST = 160;                 // px a table's first column keeps at least
const RIGHT = { conversations: [false, false, true, true, true, true, true, true],
  models: [false, true, true, true, true, true] };     // the columns of numbers, right-aligned

/** What draw() takes besides the view's own state: the app's programs (their icons). @typedef {{ programs:
 * Record<string, any> }} Look */

/** PATH (a PathBuilder's) painted over its whole box in COLOR. @param {any} path @param {string} color */
const painted = (path, color) => window.paint_path(path.build(), color).absolute().top_0().left_0().size_full();

export class UsageView {
  /** CORE runs core/'s code (main.js's python: its JSON answer), TEXT the same for what it prints (a CSV).
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<string>} text */
  constructor(core, text) {
    this.core = core;
    this.text = text;
    this.period = PERIOD;
    /** @type {string | null} the agent filtered to; null: all */
    this.agent = null;
    /** @type {string | null} the space's folder filtered to; null: all spaces */
    this.folder = null;
    /** @type {string | null} what was asked for last: the period, the agent, the folder and the theme, as JSON */
    this.key = null;
    /** @type {any} core's report; null: not read yet */
    this.report = null;
    /** @type {string | null} why the read failed, while nothing is shown */
    this.error = null;
    this.busy = false; this.again = false; this.readAt = 0;
    /** @type {any[] | null} the agents on this Mac as core tells them (their plans: value or spent) */
    this.agents = null;
    this.agentsAt = 0;
    /** @type {{ left: number | null } | null} the conversations being read into the index: the bytes left */
    this.indexing = null;
    this.indexedAt = 0;
    /** @type {{ surface: string, foreground: string } | null} the theme's card and text, as last drawn */
    this.theme = null;
    /** @type {number | null} the day's column the pointer is on: its tip */
    this.tip = null;
    /** @type {string | null} the conversation Open in Usage and Usage › asked for: its row marked */
    this.marked = null;
    this.widened = false;                         // the period made longer once to find that row
    this.reveal = false; this.revealed = false;   // its table to scroll to at the next draw; done once an ask
    /** @type {{ rows: { key: string, name: string, input: any }[], error: string | null, busy: boolean } | null}
     * the budget's popover while open */
    this.budget = null;
    this.listing = false;                         // the scope's list open
    /** @type {number | null} */
    this.cursor = null;
    this.listPlaces = []; this.listScroll = null;
    this.scroll = ScrollHandle.new();
    this.still = false;                           // the styleguide's: nothing read, nothing pressed
  }

  /** Whether the last read is old. */
  due() {
    return Date.now() - this.readAt > POLL;
  }

  /** From render, while the view shows: the report read once another period, agent, folder or theme is asked for;
   * the conversations read into the index and the report read again every POLL. */
  follow(t, cx) {
    const theme = { surface: t.surface, foreground: t.foreground };
    const key = JSON.stringify([this.period, this.agent, this.folder, theme]);
    this.theme = theme;
    if (key !== this.key) {
      Object.assign(this, { key, tip: null });
      this.read(cx);
    }
    if (Date.now() - this.indexedAt > POLL) this.bringUp(cx);
  }

  /** SESSION's row asked for (Open in Usage, Usage ›): every agent and space shown, its row marked once read.
   * @param {string | null} session */
  ask(session) {
    Object.assign(this, { marked: session, widened: false, agent: null, folder: null, revealed: false });
  }

  /** The agents' plans asked of core where they are not known or old: an agent on an API key reads "spent". */
  async plans() {
    if (this.agents && Date.now() - this.agentsAt < AGENTS_EVERY) return;
    try {
      const agents = await this.core(AGENT_STATE, ["agents"], home(), null);
      Object.assign(this, { agents: Array.isArray(agents) ? agents : [], agentsAt: Date.now() });
    } catch {
      this.agents = this.agents ?? [];            // not told: every cost reads "API value", never "spent"
    }
  }

  /** The report read (one read at a time, once more after it when asked meanwhile): drawn anew where it changed,
   * kept where a read fails. The row asked for and not in it: the 30 days tried once. */
  read(cx) {
    if (this.busy) return void (this.again = true);
    const key = this.key;
    Object.assign(this, { busy: true, readAt: Date.now() });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        await this.plans();
        const report = await this.core(REPORT, reportArgs("report", { period: this.period, agent: this.agent,
          folder: this.folder, agents: usageAgents(this.agents), theme: this.theme }), home(), null);
        if (key !== this.key) return;
        if (this.marked && !this.widened && markedRow(report.conversations, this.marked) < 0
          && this.period !== "30d") {
          Object.assign(this, { widened: true, period: "30d" });
          return void cx.notify();                // render asks for the longer period
        }
        const same = !this.error && JSON.stringify(report) === JSON.stringify(this.report);
        Object.assign(this, { report, error: null });
        const found = Boolean(this.marked) && markedRow(report.conversations, this.marked) >= 0;
        if (found && !this.revealed) this.reveal = true;         // its table scrolled to, once
        if (!same || this.reveal) cx.notify();
      } catch (e) {
        if (key !== this.key || this.report) return;
        this.error = said(e);
        cx.notify();
      } finally {
        this.busy = false;
        if (this.again) {
          this.again = false;
          this.read(cx);
        }
      }
    });
  }

  /** The conversations read into core's indexes (tokens.py's, then commits.py's; a look reads so much and says what
   * is left), the report read again after each index that read anything. Until then a cost is what was read so far
   * and a commit "–". */
  bringUp(cx) {
    if (this.indexing) return;
    Object.assign(this, { indexing: { left: null }, indexedAt: Date.now() });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        for (const source of [TOKENS, COMMITS]) {
          const done = await indexed(() => this.core(source, ["index"], home(), null), undefined, (left) => {
            const was = this.indexing?.left;
            this.indexing = { left };
            if (Boolean(was) !== Boolean(left)) cx.notify();
          });
          if (done.read > 0) this.read(cx);
        }
      } catch {
        // not read now: the report shows what the index held, the next look tries again
      } finally {
        Object.assign(this, { indexing: null, indexedAt: Date.now() });
        if (this.due()) this.read(cx);
        cx.notify();
      }
    });
  }

  /** VALUE of FILTER picked (the period, the agent): render reads the report for it. @param {"period" | "agent"}
   * filter @param {string | null} value */
  pick(filter, value, cx) {
    if (filter === "period") this.period = String(value);
    else this.agent = value;
    cx.notify();
  }

  /** The scope's list shown or shut. @param {boolean} open */
  list(open, cx) {
    Object.assign(this, { listing: open, cursor: null, listPlaces: [] });
    cx.notify();
  }

  /** The budget's popover shown (its fields filled with what core keeps) or shut. @param {boolean} open */
  budgets(open, cx) {
    if (!open) {
      this.budget = null;
      return void cx.notify();
    }
    if (this.budget) return;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const kept = await this.core(REPORT, ["budget"], home(), null);
        const rows = budgetRows(this.agents, kept).map((row) => ({ key: row.key, name: row.name,
          input: InputState.new({ placeholder: "none", value: row.value }) }));
        this.budget = { rows, error: null, busy: false };
        for (const row of rows) row.input.on("submit", (/** @type {any} */ _e, /** @type {any} */ cx) => this.save(cx));
        cx.timer.after(0, () => rows[0]?.input.focus());
      } catch (e) {
        notify({ title: "Couldn't read the budget", body: said(e), level: "error" });
      }
      cx.notify();
    });
  }

  /** The budget's fields kept by core (an empty one: no budget), the report read again; a field that is no amount
   * said under them. */
  save(cx) {
    const budget = this.budget;
    if (!budget || budget.busy) return;
    const typed = budget.rows.map((row) => ({ ...row, text: String(row.input.value()).trim() }));
    const odd = typed.find((row) => !amountTyped(row.text));
    if (odd) {
      budget.error = `${odd.name}'s is not an amount`;
      return void cx.notify();
    }
    budget.busy = true;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        for (const row of typed) await this.core(REPORT, ["budget", row.key, row.text], home(), null);
        this.budget = null;
        this.read(cx);
      } catch (e) {
        Object.assign(budget, { busy: false, error: `Couldn't keep it: ${said(e)}` });
      }
      cx.notify();
    });
  }

  /** The period's usage as CSV (core's csv: a row a day, agent, model and conversation), saved where macOS's save
   * panel says, a file there replaced only as the panel asks; a failure said in a notice. */
  exportCsv(cx) {
    const name = String(this.report?.csv_name ?? "herdr-fold usage.csv");
    cx.spawn(async () => {
      try {
        const csv = await this.text(REPORT, reportArgs("csv", { period: this.period, agent: this.agent,
          folder: this.folder, agents: usageAgents(this.agents), theme: null }), home(), null);
        const path = await savePanel("Export usage", name, home());
        if (path) await writeTextFile(path, csv, await readTextFile(path));
      } catch (e) {
        notify({ title: "Couldn't export the usage", body: said(e), level: "error" });
      }
    });
  }

  /** A conversation's ROW pressed: its chat shown as Chats shows one. @param {any} row */
  open(row, cx) {
    cx.spawn(async () => {
      try {
        const failed = await reopenChat(this.core, String(row.agent), String(row.session));
        if (failed) notify({ title: "Couldn't open the conversation", body: failed, level: "error" });
      } catch (e) {
        notify({ title: "Couldn't open the conversation", body: said(e), level: "error" });
      }
    });
  }

  /** The spaces the scope's list offers: this Mac's, each with its folder, by name. */
  scopes() {
    return spaces().filter((s) => s.machine === null && s.folder).map((s) => ({ name: String(s.name),
      folder: String(s.folder) }));
  }

  /** The head's scope (usage.html's .ahdr .scope): core's "All spaces", or the space filtered to, ⌄; a press lists
   * the spaces under it. @param {{ name: string, folder: string }[]} scopes */
  scope(t, scopes) {
    const all = String(this.report?.filters?.spaces ?? "All spaces"), open = this.listing, clear = `${t.accent}00`;
    const shown = scopes.find((one) => one.folder === this.folder)?.name ?? all;
    const rows = [{ name: all, folder: /** @type {string | null} */ (null) }, ...scopes];
    const chip = h_flex().id("usage-scope").h(BUTTON).min_w(0).px(6).gap(6).items_center().rounded(6).border_1()
      .border_color(open ? t.accent : clear).cursor_pointer().text_size(15).font_semibold()
      .when(open, (e) => e.bg(t.raised)).hover((/** @type {any} */ s) => s.bg(open ? t.raised : t.hover))
      .child(div().min_w(0).truncate().child(shown)).child(icon("chevron-down", 14).text_color(t.dim));
    return Popover.new("usage-scopes").anchor("top_left").open(open)
      .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) => this.list(opened, cx))
      .trigger(chip).when(open && !this.still, (/** @type {any} */ e) => e.content(
        panelSurface(t, "usage-scopes-surface", LIST).mt(4).p(4).gap(2)
          .children(rows.map((row, n) => panelRow(t, this, n, true, row.folder === this.folder)
            .id(`usage-scope-${n}`).line_height("16px").cursor_pointer()
            .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
              this.folder = row.folder;
              this.list(false, cx);
            })
            .child(div().flex_1().min_w(0).truncate().child(row.name))
            .when(row.folder === this.folder, (e) => e.child(icon("check", 14).text_color(t.accent)))))));
  }

  /** The view: HEAD (the tab's own, its scope and its two views) and the report's blocks in one column WIDE at most,
   * scrolled together as usage.html's; in the blocks' place what it says instead (loading, the read's failure,
   * nothing used). The table of a row asked for is scrolled to. @param {any} head */
  draw(t, head) {
    const report = this.report;
    const say = (/** @type {string} */ words, bad = false) => div().flex_none().text_size(12)
      .text_color(bad ? toneInk(t, "bad") : t.dim).child(words);
    const blocks = [head, ...(!report ? [this.error ? say(`Couldn't read the usage: ${this.error}`, true)
      : say("Loading usage…")] : [this.filters(t, report), ...(report.none ? [say(this.indexing?.left
      ? "Reading the conversations…" : report.none)] : this.blocks(t, report)), this.foot(t, report)])];
    if (this.reveal && report && !report.none) {
      this.scroll.scroll_to_item(blocks.length - 3);          // the conversations' table: before Models and the foot
      Object.assign(this, { reveal: false, revealed: true });
    }
    return v_flex().id("usage").flex_1().min_h(0).overflow_y_scroll().track_scroll(this.scroll).items_center()
      .px(PAD).pb(PAD).children(blocks.map((block, n) => div().id(`usage-block-${n}`).w_full().max_w(WIDE)
        .flex_none().when(n > 1, (e) => e.mt(APART)).child(block)));
  }

  /** REPORT's blocks under the filters: the summary row, each day by model (where a model has a price), each
   * API-key agent's month beside the projects (under one another where the tab is narrow), the two tables.
   * @param {any} report */
  blocks(t, report) {
    const months = /** @type {any[]} */ (report.months ?? []);
    const pair = [...months.map((month, n) => this.month(t, month, report, n)), this.projects(t, report)];
    return [this.summary(t, report.summary),
      ...(report.legend.length ? [this.daily(t, report)] : []),
      h_flex().id("usage-pair").w_full().items_start().flex_wrap().gap(APART)
        .children(pair.map((one) => div().flex_1().flex_basis(HALF).min_w(0).child(one))),
      this.conversations(t, report), this.models(t, report)];
  }

  /** The filters in one row (usage.html's .rtitle): the periods, the agents, then what is being read, Budget… (with
   * an agent on an API key) and Export CSV at the right. @param {any} report */
  filters(t, report) {
    const periods = report.filters.periods.map((/** @type {any} */ one) => [one.id, one.label]);
    const agents = report.filters.agents.map((/** @type {any} */ one) => [one.id ?? "", one.label]);
    const budgeted = budgetRows(this.agents, {}).length > 0, open = Boolean(this.budget);
    const budget = actButton(t, "usage-budget", report.words.budget, open ? "raised" : "plain", true,
      (/** @type {any} */ cx) => this.budgets(!open, cx));
    return h_flex().id("usage-filters").flex_none().gap(PAD).items_center().flex_wrap()
      .child(segmented(t, "usage-period", periods, report.period.id, (value, cx) => this.pick("period", value, cx)))
      .child(segmented(t, "usage-agent", agents, this.agent ?? "", (value, cx) => this.pick("agent", value || null,
        cx)))
      .child(div().flex_1())
      .when(Boolean(this.indexing?.left) && !report.none, (e) => e.child(h_flex().flex_none().gap(6).items_center()
        .text_size(11).text_color(t.dim).child(spinner(t)).child("Reading the conversations…")))
      .when(budgeted, (e) => e.child(Popover.new("usage-budget-popover").anchor("top_right").open(open)
        .on_open_change((/** @type {boolean} */ opened, /** @type {any} */ cx) => this.budgets(opened, cx))
        .trigger(budget).when(open && !this.still, (/** @type {any} */ e) => e.content(this.budgetForm(t).mt(4)))))
      .child(actButton(t, "usage-export", report.words.export, "plain", true,
        (/** @type {any} */ cx) => this.exportCsv(cx)));
  }

  /** The budget's popover (usage.html's .budget): a field for each agent on an API key, dollars a month, an empty
   * one no budget; Enter or Save keeps them, Esc or Cancel puts it away; a field that is no amount said under them. */
  budgetForm(t) {
    const budget = this.budget, ground = t.popover ?? t.raised, bad = toneInk(t, "bad", ground);
    return v_flex().id("usage-budget-form").w(BUDGET).p(PAD).gap(8).rounded(10).border_1().border_color(t.border)
      .bg(ground).shadow_lg().text_size(12)
      .on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => {
        if (e.key !== "escape") return;
        cx.stop_propagation();
        this.budgets(false, cx);
      })
      .child(div().flex_none().font_semibold().child("Monthly budget"))
      .children((budget?.rows ?? []).map((row) => h_flex().h(FIELD).flex_none().gap(8).items_center()
        .child(div().w(72).flex_none().truncate().text_color(t.muted).child(row.name))
        .child(h_flex().id(`usage-budget-${row.key}`).flex_1().min_w(0).h_full().px(8).gap(4).items_center()
          .rounded(8).border_1().border_color(t.border).bg(t.canvas).cursor_text()
          .child(div().flex_none().text_color(t.dim).child("$"))
          .child(Input.new(row.input).flex_1().h_full().text_size(12).text_color(t.foreground)))
        .child(div().flex_none().text_color(t.dim).child("a month"))))
      .when(Boolean(budget?.error), (e) => e.child(div().flex_none().text_size(11).text_color(bad)
        .child(budget?.error ?? "")))
      .child(h_flex().flex_none().pt(2).gap(6)
        .child(actButton(t, "usage-budget-save", budget?.busy ? "Saving…" : "Save", "raised", !budget?.busy,
          (/** @type {any} */ cx) => this.save(cx)))
        .child(actButton(t, "usage-budget-cancel", "Cancel", "plain", true,
          (/** @type {any} */ cx) => this.budgets(false, cx))));
  }

  /** The summary row (usage.html's .summary): one frame on the side's level, a cell an agent, then the tokens and
   * the commits; a cell's key 12 dim, its value 20 semibold with its unit, its line 12 muted, a pace over its budget
   * in yellow. @param {any[]} summary */
  summary(t, summary) {
    const warn = toneInk(t, "warn", t.chrome);
    return h_flex().id("usage-summary").flex_none().items_stretch().rounded(10).border_1().border_color(t.border)
      .bg(t.chrome).overflow_hidden().children(summaryCells(summary).map((cell, n) => v_flex().flex_basis(0)
        .flex_grow(cell.grow).min_w(0).overflow_hidden().px(16).py(PAD).gap(2)
        .when(n > 0, (e) => e.border_l_1().border_color(t.border))
        .child(div().truncate().text_size(12).text_color(t.dim).child(cell.key))
        .child(h_flex().gap(6).items_baseline().child(div().flex_none().text_size(20).line_height("28px")
          .font_semibold().child(cell.text))
          .when(Boolean(cell.unit), (e) => e.child(div().min_w(0).truncate().text_size(12).text_color(t.muted)
            .child(cell.unit))))
        .child(h_flex().min_h(16).min_w(0).flex_wrap().text_size(12).line_height("16px").text_color(t.muted)
          .when(Boolean(cell.line), (e) => e.child(div().max_w_full().child(cell.line)))
          .when(Boolean(cell.pace), (e) => e.child(div().max_w_full().font_medium().text_color(warn)
            .child(cell.pace))))));
  }

  /** A chart's or a table's card (usage.html's .chart, .tbl): a hairline frame on the tab's level, rounded 10.
   * @param {string} id */
  card(t, id) {
    return v_flex().id(id).w_full().flex_none().rounded(10).border_1().border_color(t.border).bg(t.surface);
  }

  /** A card's head: its TITLE 13 semibold, then its NOTE 12 muted. @param {string} title @param {any} [note] */
  title(t, title, note = null) {
    return h_flex().flex_none().gap(16).items_center().flex_wrap().text_size(12).text_color(t.muted)
      .child(div().flex_none().text_size(13).font_semibold().text_color(t.foreground).child(title))
      .when(Boolean(note), (e) => e.children([note].flat()));
  }

  /** Each day by model (usage.html's #daily): the legend beside the title, the plot with its ticks and hairlines, a
   * column a day (its models stacked from the baseline, the surface between two, the top one's corners 4), the days'
   * names under them; the pointer on a day shows its tip. @param {any} report */
  daily(t, report) {
    const days = /** @type {import("./report.js").Day[]} */ (report.daily);
    const marks = ticks(Math.max(...days.map((day) => day.total))), top = marks[marks.length - 1];
    const drawn = columns(days, PLOT, top), names = axisLabels(days, NAMED);
    const at = (/** @type {number} */ value) => Math.round(PLOT - value / top * PLOT);
    const word = (/** @type {number} */ value) => (marks[1] < 1 ? `$${value.toFixed(2)}` : `$${value}`);
    const legend = report.legend.map((/** @type {any} */ one) => h_flex().flex_none().gap(6).items_center()
      .child(swatch(one.color)).child(one.name));
    return this.card(t, "usage-daily").px(16).py(PAD).gap(PAD)
      .child(this.title(t, report.words.daily, legend))
      .child(h_flex().flex_none().items_start()
        .child(div().relative().w(GUTTER).h(PLOT).flex_none().children(marks.map((value) => div().absolute()
          .right(6).top(at(value) - 8).text_size(11).line_height("16px").text_color(t.dim).child(word(value)))))
        .child(div().id("usage-plot").relative().flex_1().min_w(0).h(PLOT + 1).border_b_1().border_color(t.border)
          .children(marks.slice(1).map((value) => div().absolute().left_0().right_0().top(at(value)).h(1)
            .bg(`${t.border}80`)))
          .child(h_flex().absolute().top_0().left_0().w_full().h(PLOT).items_end()
            .children(drawn.map((day, n) => v_flex().id(`usage-day-${n}`).flex_1().flex_basis(0).h_full()
              .justify_end().items_center().gap(2)
              .on_hover((/** @type {boolean} */ over, /** @type {any} */ cx) => {
                if (over ? this.tip === n : this.tip !== n) return;
                this.tip = over ? n : null;
                cx.notify();
              })
              .children([...day.segments].reverse().map((part) => div().w(SLOT).max_w(COLUMN).h(part.h)
                .flex_none().bg(part.color).when(part.top, (e) => e.rounded_t(4)))))))
          .when(this.tip !== null && Boolean(days[this.tip ?? 0]), (e) => e.child(this.dayTip(t, days,
            this.tip ?? 0)))))
      .child(h_flex().flex_none().pl(GUTTER).children(names.map((name) => div().flex_1().flex_basis(0).min_w(0)
        .flex().justify_center().text_size(11).line_height("16px").text_color(t.dim).whitespace_nowrap()
        .child(name))));
  }

  /** Day N's tip beside its column (usage.html's .tip): its date and sum, then each model's swatch, name and cost;
   * right of a column in the plot's left half, left of one in its right. @param {import("./report.js").Day[]} days
   * @param {number} n */
  dayTip(t, days, n) {
    const tip = tipFor(days[n]), middle = (n + 0.5) / days.length, right = middle > 0.5;
    const card = v_flex().absolute().top(8).min_w(TIP).px(PAD).py(8).gap(2).rounded(8).border_1()
      .border_color(t.border).bg(t.popover ?? t.raised).shadow_lg().text_size(12)
      .when(right, (e) => e.right(20)).when(!right, (e) => e.left(20))
      .child(div().pb(2).font_semibold().whitespace_nowrap().child(tip.title))
      .children(tip.rows.map((row) => h_flex().gap(8).items_center().text_color(t.muted).whitespace_nowrap()
        .child(swatch(row.color)).child(div().flex_1().child(row.name))
        .child(div().flex_none().font_medium().text_color(t.foreground).child(row.text))));
    return div().absolute().top_0().left(`${(middle * 100).toFixed(2)}%`).w(0).h_full().child(card);
  }

  /** An API-key agent's MONTH against its budget (usage.html's #month): the grid, the budget a muted hairline, what
   * was spent a 2 px line in its model's color, the pace at 40%, today's point ringed in the surface; its places
   * across a path's own percent, nothing measured. @param {any} month @param {any} report @param {number} n */
  month(t, month, report, n) {
    const drawn = monthLine(month), color = String(month.color ?? t.muted), high = MONTH - HEAD - FOOT;
    const words = (/** @type {string} */ text, /** @type {string} */ ink, size = 11) => div().absolute()
      .text_size(size).line_height("16px").text_color(ink).whitespace_nowrap().child(text);
    const card = this.card(t, `usage-month-${n}`).px(16).py(PAD).gap(PAD)
      .child(this.title(t, month.budget ? report.words.month : month.label, div().child(month.key)));
    if (!drawn) return card;
    const { today, pace, budget } = drawn, late = today.x > 0.5;
    const x = (/** @type {number} */ share) => /** @type {`${number}%`} */ (`${(share * 100).toFixed(2)}%`);
    const y = (/** @type {number} */ share) => Math.round(share * high);
    // the pace's words clear of its rising line: under its end, over it where the plot's foot is near
    const end = y(pace?.to[1] ?? 0), under = end + CLEAR + 16 <= high;
    let spent = PathBuilder.stroke(2).move_to(x(drawn.spent[0][0]), y(drawn.spent[0][1]));
    for (const [px, py] of drawn.spent.slice(1)) spent = spent.line_to(x(px), y(py));
    return card.child(h_flex().id(`usage-month-plot-${n}`).w_full().h(MONTH).flex_none().items_start()
      .child(div().relative().w(GUTTER).h_full().flex_none().children(drawn.ticks.map((tick) => words(tick.label,
        t.dim).right(6).top(HEAD + y(tick.y) - 8))))
      .child(div().relative().flex_1().min_w(0).h_full().child(div().absolute().left_0().right(8).top(HEAD).h(high)
        .children(drawn.ticks.map((tick) => div().absolute().left_0().right_0().top(y(tick.y)).h(1)
          .bg(`${t.border}80`)))
        .when(Boolean(budget), (e) => e.child(div().absolute().left_0().right_0().top(y(budget?.y ?? 0)).h(1)
          .bg(t.muted)).child(words(budget?.label ?? "", t.muted).left_0().top(y(budget?.y ?? 0) - 18)))
        .when(Boolean(pace), (e) => e.child(painted(PathBuilder.stroke(2).move_to(x(pace?.from[0] ?? 0),
          y(pace?.from[1] ?? 0)).line_to(x(pace?.to[0] ?? 0), y(pace?.to[1] ?? 0)), `${color}${PACE}`))
          .child(words(pace?.label ?? "", t.muted).right_0().top(under ? end + CLEAR : end - CLEAR)))
        .child(painted(spent, color))
        .child(div().absolute().left(x(today.x)).top(y(today.y)).w(0).h(0)
          .child(div().absolute().left(-DOT / 2 - RING).top(-DOT / 2 - RING).size(DOT + 2 * RING).rounded_full()
            .bg(color).border_2().border_color(t.surface))
          .child(late ? words(today.label, t.foreground, 12).right(8).top(-22)
            : words(today.label, t.foreground, 12).left(8).top(4)))
        .child(words(drawn.first, t.dim).left_0().top(high + 4))
        .child(words(drawn.last, t.dim).right_0().top(high + 4)))));
  }

  /** By project (usage.html's #projects): a row a project, the most first, its name in NAMES px, its bar 16 high in
   * muted as long as its share of the largest, its value at the bar's tip; under them core's note.
   * @param {any} report */
  projects(t, report) {
    return this.card(t, "usage-projects").px(16).py(PAD).gap(PAD)
      .child(this.title(t, report.words.projects, div().child(report.period.label)))
      .child(v_flex().flex_none().children(projectBars(report.projects).map((row) => h_flex().h(32).flex_none()
        .gap(PAD).items_center().child(div().w(NAMES).flex_none().truncate().child(row.name))
        .child(h_flex().flex_1().min_w(0).gap(8).items_center()
          .when(row.share > 0, (e) => e.child(div().h(16).min_w(2).w(`${(row.share * BAR * 100).toFixed(2)}%`)
            .rounded_r(4).bg(t.muted)))
          .child(div().flex_none().whitespace_nowrap().child(row.text))))))
      .child(div().flex_none().text_size(12).text_color(t.dim).child(report.words.projects_note));
  }

  /** A table's frame: its TITLE with core's NOTE, its columns' names (HEADS; WIDTHS after the first, the numbers'
   * RIGHT-aligned) and its ROWS; too narrow, scrolled sideways. @param {string} id @param {string} title @param
   * {string} note @param {string[]} heads @param {number[]} widths @param {boolean[]} right @param {any[]} rows */
  table(t, id, title, note, heads, widths, right, rows) {
    const least = FIRST + widths.reduce((sum, w) => sum + w, 0) + 2 * PAD + widths.length * 8;
    return this.card(t, id).overflow_hidden()
      .child(h_flex().h(36).flex_none().px(PAD).gap(PAD).items_center().border_b_1().border_color(t.border)
        .child(div().flex_1().min_w(0).truncate().font_semibold().child(title))
        .child(div().flex_none().text_size(12).text_color(t.dim).child(note)))
      .child(div().id(`${id}-columns`).w_full().overflow_x_scroll().child(v_flex().w_full().min_w(least)
        .child(this.line(t, heads.map((head) => div().truncate().child(head)), widths, right).h(28).text_size(11)
          .text_color(t.dim).border_b_1().border_color(t.border))
        .children(rows)));
  }

  /** A table's line: CELLS in its columns (the first takes the rest, WIDTHS the others, the numbers' right-aligned),
   * 8 apart, 12 in. @param {any[]} cells @param {number[]} widths @param {boolean[]} right */
  line(t, cells, widths, right) {
    return h_flex().flex_none().px(PAD).gap(8).items_center().text_size(12)
      .children(cells.map((cell, n) => (n === 0 ? div().flex_1().min_w(0).child(cell)
        : h_flex().w(widths[n - 1]).flex_none().min_w(0).gap(6).items_center().overflow_hidden()
          .when(right[n - 1], (e) => e.justify_end()).child(cell))));
  }

  /** A figure with its short word after it, dim (a cost's "value", a commit's lines). @param {string} figure
   * @param {string} word */
  figure(t, figure, word) {
    return h_flex().gap(6).items_baseline().whitespace_nowrap().child(figure)
      .when(Boolean(word), (e) => e.child(div().text_color(t.dim).child(word)));
  }

  /** Conversations (usage.html's): a row a conversation, the costliest first, its models as their colors' marks;
   * the row asked for on the chosen fill; a press opens its chat, its tip its cost and cache share a turn.
   * @param {any} report */
  conversations(t, report) {
    const marked = markedRow(report.conversations, this.marked), words = report.words;
    const rows = report.conversations.map((/** @type {any} */ row, /** @type {number} */ n) => {
      const cell = conversationCells(row, words), none = (/** @type {string} */ text) => div().text_color(t.dim)
        .child(text);
      return this.line(t, [div().truncate().child(cell.title), div().truncate().child(cell.space),
        h_flex().gap(2).children(cell.models.map((/** @type {string} */ color) => div().w(6).h(12).rounded_xs()
          .bg(color))),
        cell.turns, cell.tokens, cell.cache,
        cell.kind ? this.figure(t, cell.cost, cell.kind) : none(cell.cost),
        cell.none ? none(cell.commits) : this.figure(t, cell.commits, cell.changed),
        cell.per === "–" ? none(cell.per) : cell.per], TALKS, RIGHT.conversations)
        .id(`usage-talk-${n}`).h(32).when(n > 0, (e) => e.border_t_1().border_color(`${t.foreground}0d`))
        .when(n === marked, (e) => e.bg(chosenFill(t)))
        .tooltip([row.tip, row.commits_tip].filter(Boolean).join(" · ") || cell.title)
        .when(!this.still, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
          .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.open(row, cx)));
    });
    return this.table(t, "usage-conversations", words.conversations, words.conversations_note,
      report.columns.conversations, TALKS, RIGHT.conversations, [...rows, ...(report.more > 0
        ? [listNote(t, `${report.more} more`, false, PAD).pt(8)] : [])]);
  }

  /** Models (usage.html's): a row a model and agent, each kind of token, its cost with value or spent; one with no
   * price in dim, its tokens alone. @param {any} report */
  models(t, report) {
    const rows = report.models.map((/** @type {any} */ row, /** @type {number} */ n) => {
      const cell = modelCells(row), ink = cell.priced ? t.foreground : t.dim;
      return this.line(t, [h_flex().gap(8).items_center().min_w(0).when(cell.priced, (e) => e.child(swatch(
        cell.color))).child(div().min_w(0).truncate().text_color(ink).child(cell.name)),
      div().truncate().text_color(ink).child(cell.agent), cell.input, cell.write, cell.read, cell.output,
      cell.priced ? this.figure(t, cell.cost, cell.kind) : div().text_color(t.dim).child(cell.cost)], MODELS,
      RIGHT.models).id(`usage-model-${n}`).h(32).when(n > 0, (e) => e.border_t_1()
        .border_color(`${t.foreground}0d`));
    });
    return this.table(t, "usage-models", report.words.models, report.words.models_note, report.columns.models, MODELS,
      RIGHT.models, rows);
  }

  /** The foot (usage.html's .rfoot2): where the prices are from, 12 dim. @param {any} report */
  foot(t, report) {
    return div().flex_none().text_size(12).text_color(t.dim).child(report.words.foot);
  }
}
