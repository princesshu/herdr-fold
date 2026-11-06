// @ts-check
// The Conversations block of the left sidebar, as the TUI's column: this Mac's conversations, running or closed, by
// space under a filter; a click goes to a running one or reopens a closed one in a new tab of its space.
import { div, image, svg } from "gpui-kit";
import { v_flex, h_flex, InputState, Input } from "gpui-base";
import { agents, home, knownAgents, panes, setShared, shared, spaces, watchFolder, run as command }
  from "herdr";
import { CONVERSATIONS } from "./helper.js";
import { archiveKey, conversationChoices, conversationRows, coreAgents, floatHeight, folderSpaces, resumeArgv, said,
  tabLabel } from "./logic.js";
import { Menus } from "./menus.js";
import { field, icon, SLIDE, stateMark } from "./parts.js";
import { dock, folded, followFold } from "./sidebar.js";
import { trackWaits } from "./spaces.js";

const KEPT = "herdr-fold.conversations";      // the archived ones shown or not, and the reopened ones' terminals
const WATCHED = [".claude/projects", ".codex/sessions"];      // under the home folder, where the agents write them
const ACTIONS = { Open: "open", "Copy conversation": "copy", Rename: "rename", Archive: "archive",
  Unarchive: "unarchive" };
const STATES = { working: "Working", blocked: "Blocked", done: "Done", idle: "Idle" };   // a mark's, in words

/** @typedef {import("./logic.js").Conversation & { ago: string }} Listed */

export class ConversationsView {
  /** CORE runs core/'s code on this Mac (main.js's python); OVERLAY, the popup it shows in when opened beside the
   * folded rail, closed once one is opened. @param {(source: string, args: string[], root: string,
   * on: string | null) => Promise<any>} core @param {string | null} overlay */
  constructor(core, cx, overlay = null) {
    this.core = core;
    this.overlay = overlay;
    /** @type {Listed[]} */
    this.items = [];
    /** @type {Set<string>} archiveKey's */
    this.archived = new Set();
    this.loaded = false;
    /** @type {string | null} what was done, or what went wrong */
    this.note = null;
    this.typed = "";
    this.find = InputState.new({ placeholder: "Filter conversations" });
    this.find.on("change", (_e, cx) => {
      this.typed = this.find.value().trim();
      cx.notify();
    });
    this.find.on("submit", (_e, cx) => {
      const first = this.rows().find((row) => row.kind === "item");
      if (first) this.open(first.item, cx);
    });
    /** @type {Set<string>} the spaces opened and closed by hand */
    this.opened = new Set();
    this.closed = new Set();
    this.menus = new Menus();             // a right click's, on a conversation or on the list
    /** @type {{ key: string, item: Listed, input: any } | null} the one being renamed */
    this.naming = null;
    /** @type {{ space: string, tab: string, agent: string, id: string }[]} reopened, their terminal not yet known */
    this.pending = [];
    this.seen = "";                               // the agents the list was last read with
    /** @type {boolean | null} whether the sidebar was a rail at the last look */
    this.folded = null;
    /** @type {Record<string, any>} the agents' programs by key, their icons for the rail */
    this.programs = {};
    cx.spawn(async (cx) => {
      try {
        this.programs = Object.fromEntries((await knownAgents()).map((p) => [p.key, p]));
      } catch {
        // no icons: the rail numbers them
      } finally {
        cx.notify();
      }
    });
    for (const rel of WATCHED) this.watch(`${home()}/${rel}`, cx);
  }

  /** FOLDER's changes, each a new look; a folder that is not there (no Codex) is not watched. */
  watch(folder, cx) {
    cx.spawn(async (cx) => {
      try {
        for (;;) {
          await watchFolder(folder);
          this.load(cx);
        }
      } catch {
        // no such folder: nothing of that agent's to watch
      }
    });
  }

  /** The ids of this Mac's spaces. */
  local() {
    return new Set(spaces().filter((s) => s.machine === null).map((s) => s.id));
  }

  /** {terminal: conversation id} of the ones reopened here, their agents still running. */
  resumed() {
    const kept = shared(KEPT)?.resumed ?? {}, live = new Set(agents().map((a) => a.address));
    return Object.fromEntries(Object.entries(kept).filter(([terminal]) => live.has(terminal)));
  }

  /** From render: a reopened one's terminal learned once its agent is there, and the list read again whenever the
   * agents changed (a new one, another state), after the render, as that redraws. */
  look(cx) {
    const now = !this.overlay && folded();
    if (now !== this.folded) {                    // the dock and the toggle beside it, or the open sidebar's blocks
      this.folded = now;
      if (!this.overlay) cx.timer.after(0, () => followFold(now));
    }
    if (!this.overlay) trackWaits();             // the Spaces list's waits, kept while it is folded away too
    const live = agents(), resumed = this.resumed();
    this.pending = this.pending.filter((p) => {
      const found = live.find((a) => a.space === p.space && a.tab_name === p.tab && a.program?.key === p.agent);
      if (found) resumed[found.address] = p.id;
      return !found;
    });
    const sig = JSON.stringify([coreAgents(live, panes(), this.local()), resumed]);
    if (sig === this.seen) return;
    this.seen = sig;
    setShared(KEPT, { ...shared(KEPT), resumed });
    cx.timer.after(0, (cx) => this.load(cx));
  }

  /** The conversations from core/conversations.py, the running ones marked; an answer for an older look kept. */
  load(cx) {
    const list = coreAgents(agents(), panes(), this.local());
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(CONVERSATIONS, ["list", JSON.stringify(list), JSON.stringify(this.resumed())],
          home(), null);
        this.items = answer.conversations;
        this.archived = new Set(answer.archived);
        this.loaded = true;
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** The rows shown: every space of this Mac with its conversations, as the TUI's column lists them. */
  rows() {
    const all = spaces(), here = all.find((s) => s.active)?.name ?? null;
    const actives = new Set(all.map((s) => s.tabs.find((tab) => tab.active)?.id));
    const front = new Set(agents().filter((a) => actives.has(a.tab)).map((a) => a.address));
    return conversationRows(this.items, all.filter((s) => s.machine === null).map((s) => s.name),
      folderSpaces(all, panes()), { typed: this.typed, archived: this.archived, showArchived: this.showsArchived(),
        opened: this.opened, closed: this.closed, here, front,
        states: Object.fromEntries(all.map((s) => [s.name, s.status])) });
  }

  /** Whether the archived ones are shown, as the list's right click left it. */
  showsArchived() {
    return shared(KEPT)?.showArchived === true;
  }

  /** ITEM shown: a running one's agent, else a new tab in its folder's space, its agent resuming it.
   * @param {Listed} item */
  open(item, cx) {
    if (item.state && item.pane) return void command("agent.focus", { terminal: item.pane });
    const name = folderSpaces(spaces(), panes())[item.folder];
    const space = spaces().find((s) => s.machine === null && s.name === name);
    if (!space) return void this.say("Its space is gone", cx);
    try {
      const tab = tabLabel(item.title);
      command("tab.new", { space: space.id, name: tab, folder: item.folder, argv: resumeArgv(item) });
      this.pending.push({ space: space.id, tab, agent: item.agent, id: item.id });
    } catch (e) {
      this.say(said(e), cx);
    }
  }

  /** ITEM's whole conversation on the clipboard, as Markdown. @param {Listed} item */
  copy(item, cx) {
    this.ask(["markdown", item.agent, item.id], cx, (answer, cx) => {
      if (answer.markdown === null) throw new Error("Its file is gone");
      cx.write_to_clipboard(answer.markdown);
      return "Conversation copied";
    });
  }

  /** CHOICE of the right click's menu, on ITEM (null: the list's own).
   * @param {string} choice @param {Listed | null} item */
  pick(choice, item, cx) {
    if (choice === "Show archived" || choice === "Hide archived") {
      setShared(KEPT, { ...shared(KEPT), showArchived: choice === "Show archived" });
    } else if (item) {
      const action = ACTIONS[/** @type {keyof typeof ACTIONS} */ (choice)];
      if (action === "open") this.open(item, cx);
      else if (action === "copy") this.copy(item, cx);
      else if (action === "rename") this.rename(item, cx);
      else this.ask([action, archiveKey(item)], cx, () => (action === "archive" ? "Archived" : "Unarchived"));
    }
    cx.notify();
  }

  /** ITEM's name typed in its row: Enter keeps it (as herdr's Rename pane names it), leaving the field drops it.
   * @param {Listed} item */
  rename(item, cx) {
    const input = InputState.new({ placeholder: item.title });
    input.set_value(item.title);
    input.on("submit", (_e, cx) => {
      const name = input.value().trim();
      this.naming = null;
      if (name && name !== item.title) this.ask(["rename", item.id, name], cx, () => null);
      cx.notify();
    });
    input.on("blur", (_e, cx) => {
      this.naming = null;
      cx.notify();
    });
    this.naming = { key: archiveKey(item), item, input };
    input.focus();
  }

  /** core/conversations.py's ARGS, then DONE with its answer (what to say, or null), and the list read again. */
  ask(args, cx, done) {
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(CONVERSATIONS, args, home(), null);
        if (answer.ok === false) throw new Error(answer.advice);
        this.note = done(answer, cx);
      } catch (e) {
        this.note = said(e);
      } finally {
        this.load(cx);
      }
    });
  }

  say(note, cx) {
    this.note = note;
    cx.notify();
  }

  /** The Filter field taking the keys (Cmd+Shift+R, as the TUI's column). */
  focus() {
    this.find.focus();
  }

  render(t, cx) {
    this.look(cx);
    return this.folded ? dock(t, spaces().map((space) => space.status), this.items.map((item) => item.state),
      floatHeight("conversations", this.rows())) : this.list(t, this.rows());
  }

  /** ITEM's agent's icon, Claude Code's or Codex's, as the app draws a program's; null while the app has not named
   * them. @param {Listed} item @param {number} size */
  agentIcon(item, size) {
    const p = this.programs[item.agent];
    if (!p?.icon) return null;
    return p.tint ? svg(p.icon).size(size).flex_none() : image(p.icon).w(size).h(size).flex_none();
  }

  /** The block: its heading, the filter, what was done, and ROWS. */
  list(t, rows) {
    const empty = !this.loaded ? "Loading conversations…" : rows.length ? null
      : this.typed ? "No conversation matches" : "No conversations";
    const docked = !this.overlay;                 // floating, its panel's head names it
    return v_flex().size_full().min_h(0).text_color(t.foreground).text_size(13)
      .when(docked, (e) => e.child(h_flex().flex_none().h(41).px(16).pt(14).pb(5).items_center()   // the app's lists'
        .child(div().text_size(11.5).font_medium().text_color(t.dim).child("Conversations"))))
      .child(div().flex_none().px(8).pb(6).child(field(t, "conversations-filter", this.find)))
      .when(Boolean(this.note), (e) => e.child(div().flex_none().px(16).pb(6).text_size(11).truncate()
        .text_color(t.dim).child(this.note ?? "")))
      .child(v_flex().id("conversations").flex_1().min_h(0).overflow_y_scrollbar().px(8).pb(8)
        .on_mouse_down("right", () => this.menus.open(this.choices(null)))
        .when(Boolean(empty), (e) => e.child(div().px(8).py(4).text_size(12).text_color(t.dim).child(empty ?? "")))
        .children(rows.filter((row) => row.kind === "group").flatMap((row) => [this.group(t, row),
          this.members(t, row)])));
  }

  /** ROW's conversations under it, sliding open and shut as the Changes' sections do. */
  members(t, row) {
    return v_flex().id(`members-${row.name}`).flex_none().overflow_hidden()
      .h(row.open ? row.items.length * 24 : 0).transition("height", SLIDE)
      .children(row.items.map((item) => this.row(t, item)));
  }

  /** A space as the TUI's column has it: its most urgent agent's state mark (none: a faint dot), its name (the one
   * shown bold), how many it holds and its chevron; a click folds or opens it. */
  group(t, row) {
    const here = row.here;
    return h_flex().id(`space-${row.name}`).h(26).flex_none().px(8).gap(6).items_center().rounded(6).cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_click((_e, cx) => {
        const set = row.open ? this.closed : this.opened, other = row.open ? this.opened : this.closed;
        set.add(row.name);
        other.delete(row.name);
        cx.notify();
      })
      .child(stateMark(t, row.state))
      .child(div().flex_1().min_w(0).truncate().text_color(here ? t.foreground : t.muted)
        .when(here, (e) => e.font_bold()).child(row.name))
      .child(div().flex_none().text_size(11).text_color(t.dim).child(String(row.items.length)))
      .child(icon(row.open ? "chevron-down" : "chevron-right", 12).text_color(t.accent));
  }

  /** A conversation: its state's mark (a closed one's faint dot), its agent's icon, its name (a closed one's fainter)
   * and how long ago; a click shows it, a right click opens its menu. @param {Listed} item */
  row(t, item) {
    const key = archiveKey(item), archived = this.archived.has(key);
    const title = item.title.replace(/\p{Cc}/gu, "?");    // a title's escape codes shown, never run
    const look = archived ? t.dim : item.state ? t.foreground : t.muted, agent = this.agentIcon(item, 13);
    return h_flex().id(`conversation-${key}`).h(24).flex_none().pl(22).pr(8).gap(6).items_center().rounded(6)
      .cursor_pointer().hover((s) => s.bg(t.hover)).on_click((_e, cx) => this.open(item, cx))
      .tooltip(`${title} · ${STATES[item.state] ?? "Closed"}`)              // its whole name, its mark in words
      .on_mouse_down("right", (_e, cx) => {
        cx.stop_propagation();                        // not the list's own menu
        this.menus.open(this.choices(item));
      })
      .child(stateMark(t, item.state))
      .when(Boolean(agent), (e) => e.child(div().flex_none().text_color(t.muted).child(agent)))
      .child(this.naming?.key === key
        ? div().flex_1().min_w(0).h(20).px(4).flex().items_center().rounded(4).border_1().border_color(t.border)
          .child(Input.new(this.naming.input).h_full().text_size(12))
        : div().flex_1().min_w(0).truncate().text_color(look).child(title))
      .child(div().flex_none().text_size(11).text_color(t.dim)
        .child(archived ? "archived" : agent ? item.ago : `${item.agent} · ${item.ago}`));
  }

  /** The right click's menu: on ITEM what can be done with it, on the list (null) the archived shown or hidden.
   * @param {Listed | null} item @returns {import("./menus.js").Item[]} */
  choices(item) {
    const choices = conversationChoices(item, this.archived, this.showsArchived());
    return choices.length ? choices.map((choice) => ({ label: choice, act: (cx) => this.pick(choice, item, cx) }))
      : [{ label: "Nothing archived", off: true }];
  }
}
