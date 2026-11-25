// @ts-check
// The Chats list the dock row's Chats opens in the view's place, as the TUI's: this Mac's chats by space under a
// filter; a click goes to a running one or reopens a closed one, and it closes; Delete…, asked in its row, trashes one.
import { div, image, svg } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, ScrollHandle } from "gpui-base";
import { agents, closeOverlay, home, knownAgents, layout, openOverlay, panes, setShared, shared, spaces, terminals,
  watchFolder, run as command } from "herdr";
import { AGENTS_OPEN, agentsOpen, reopensAs } from "./agents.js";
import { chatWaits, openChat, usedAgent } from "./chat.js";
import { CHATS } from "./helper.js";
import { NAMES } from "./layers.js";
import { archiveKey, CHAT_TAB, chatAgents, chatChoices, chatRows, chatsAsked, coreAgents, deleteOff, folderSpaces,
  groupPlace, resumeArgv, said, stillLeaving, stillResumed, tabLabel, waitingChats, withoutLeaving } from "./logic.js";
import { Menus } from "./menus.js";
import { field, fold, footNote, GAP, keepNote, PAD, small, SPRING, stateMark } from "./parts.js";

// the archived ones shown or not, the reopened ones' terminals, and those reopened whose agent is not there yet
const KEPT = "herdr-fold.chats";
// when the list last opened, and the group a chat's clock asked for: { at, space } (panel.js's toggleChats)
export const OPENED = "herdr-fold.chats-opened";
const PENDING = 120000;            // ms a reopened chat's agent may take to start before it is given up
const WATCHED = [".claude/projects", ".codex/sessions"];      // under the home folder, where the agents write them
const ACTIONS = { Open: "open", "Copy chat": "copy", Rename: "rename", Archive: "archive",
  Unarchive: "unarchive", "Delete…": "delete" };
const STATES = { working: "Working", blocked: "Blocked", done: "Done", idle: "Idle" };   // a mark's, in words
const SPACE_ROW = 26, CHAT_ROW = 24;          // px: a space's row, a chat's
const CHEVRON = 14;                           // px: a space's chevron, leftmost (Lucide's)
const UNDER = PAD / 2 + CHEVRON + 6;          // a chat's row in, its mark under its space's name (pad, chevron, gap)
const AGENT = 44, AGE = 48;                   // px: a chat's two columns at its end, its agent's name and its age

/** Whether the archived ones are shown, as the list's right click or More left it. */
const showsArchived = () => shared(KEPT)?.showArchived === true;

/** More's Show archived while Chats shows: its ✓ while the archived ones are, a press shows or hides them. */
export const archivedChoice = () => ({ label: "Show archived", on: showsArchived(),
  act: () => setShared(KEPT, { ...shared(KEPT), showArchived: !showsArchived() }) });

/** @typedef {import("./logic.js").Chat & { ago: string }} Listed */

/** This Mac's spaces' ids. */
const local = () => new Set(spaces().filter((s) => s.machine === null).map((s) => s.id));

/** The ✦'s count: the chats waiting on you, in panes and in chat tabs. */
export const waiting = () => waitingChats(agents(), local(), chatWaits().agents);

/** The running chats as core/chats.py marks them: the agents in panes, and the chat tabs' (chat.js's). */
const running = () => [...coreAgents(agents(), panes(), local()), ...chatAgents(terminals(), chatWaits().agents)];

/** The chat tab whose agent is at ADDRESS, if it is one. @param {string} address */
const chatTab = (address) => terminals().find((t) => t.address === address && t.state === "live")?.labels?.[CHAT_TAB];

/** ITEM shown: a chat tab's its tab, a running one's agent, else a new tab in its folder's space, its agent resuming
 * it as Settings' Open agents in says (a chat; Codex's, until its adapter, a terminal). Why it could not be, or null.
 * @param {Listed} item @returns {string | null} */
export function showChat(item) {
  const tab = item.pane ? chatTab(item.pane) : null;
  if (tab) return void command("tab.select", { id: tab }) ?? null;
  if (item.state && item.pane) return void command("agent.focus", { terminal: item.pane }) ?? null;
  const name = folderSpaces(spaces(), panes())[item.folder];
  const space = spaces().find((s) => s.machine === null && s.name === name);
  if (!space) return "Its space is gone";
  const label = tabLabel(item.title), kept = /** @type {any} */ (shared(KEPT) ?? {});
  if (reopensAs(item, agentsOpen(shared(AGENTS_OPEN))) === "chat") {
    openChat({ space: space.id, agent: item.agent, session: item.id, resume: true, name: label,
      folder: item.folder });
    return null;
  }
  command("tab.new", { space: space.id, name: label, folder: item.folder, argv: resumeArgv(item) });
  usedAgent(item.agent);
  setShared(KEPT, { ...kept, pending: [...(kept.pending ?? []), { space: space.id, tab: label, agent: item.agent,
    id: item.id, at: Date.now() }] });
  return null;
}

/** AGENT's conversation SESSION shown as Chats shows one (showChat()), found in core's list (CORE: main.js's
 * python); why it could not be, or null. @param {any} core @param {string} agent @param {string} session */
export async function reopenChat(core, agent, session) {
  const resumed = stillResumed(shared(KEPT)?.resumed ?? {}, new Set(agents().map((a) => a.address)));
  const answer = await core(CHATS, ["list", JSON.stringify(running()), JSON.stringify(resumed)], home(), null);
  const item = (answer.chats ?? []).find((/** @type {Listed} */ one) => one.id === session && one.agent === agent);
  return item ? showChat(item) : "Its conversation is not in Chats";
}

export class ChatsView {
  /** CORE runs core/'s code on this Mac (main.js's python); OVERLAY, the window beside the right rail it shows in,
   * closed once a chat is opened; in the dock (none), BACK brings the view it stands in for back (Esc, a chat opened).
   * @param {any} core @param {{ overlay?: string | null, back?: (() => void) | null }} [how] */
  constructor(core, cx, { overlay = null, back = null } = {}) {
    this.core = core;
    this.overlay = overlay;
    this.back = back;
    this.slides = "";            // its slides' ids' prefix: a slide is kept by its element's id (the styleguide's own)
    /** @type {Listed[]} */
    this.items = [];
    /** @type {Set<string>} archiveKey's */
    this.archived = new Set();
    this.loaded = false;
    /** @type {import("./parts.js").Note | null} what was done, or what went wrong, under the list */
    this.note = null;
    /** @type {string | null} why the list could not be read, in its first row's place */
    this.failed = null;
    this.typed = "";
    this.find = InputState.new({ placeholder: "Filter chats" });
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
    this.menus = new Menus();             // a right click's, on a chat or on the list
    this.scroll = ScrollHandle.new();     // the list's: the group a chat's clock asked for scrolled to
    /** @type {number | null} the opening (its time) answered last */
    this.opening = null;
    /** @type {{ key: string, item: Listed, input: any } | null} the one being renamed */
    this.naming = null;
    /** @type {string | null} the one Delete… asks about, in its row (archiveKey's) */
    this.asking = null;
    /** @type {Set<string>} the ones on their way to the Trash, their rows gone already (archiveKey's) */
    this.leaving = new Set();
    this.seen = "";                               // the agents the list was last read with
    /** @type {Record<string, any>} the agents' programs by key, their icons in the rows */
    this.programs = {};
    cx.spawn(async (cx) => {
      try {
        this.programs = Object.fromEntries((await knownAgents()).map((p) => [p.key, p]));
      } catch {
        // no icons: a row names its agent
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

  /** {terminal: chat id} of the ones reopened here, their agents still running. */
  resumed() {
    return stillResumed(shared(KEPT)?.resumed ?? {}, new Set(agents().map((a) => a.address)));
  }

  /** From render: a reopened one's terminal learned once its agent is there, by any list's look (the list that
   * reopened it may be gone), and the list read again whenever the agents changed (a new one, another state), after
   * the render, as that redraws. */
  look(cx) {
    const live = agents(), resumed = this.resumed(), kept = /** @type {any} */ (shared(KEPT) ?? {}), now = Date.now();
    const asked = /** @type {{ space: string, tab: string, agent: string, id: string, at: number }[]} */
      (kept.pending ?? []);
    const pending = asked.filter((p) => {
      const found = live.find((a) => a.space === p.space && a.tab_name === p.tab && a.program?.key === p.agent);
      if (found) resumed[found.address] = p.id;
      return !found && now - p.at < PENDING;
    });
    const sig = JSON.stringify([running(), resumed]);
    if (sig === this.seen && pending.length === asked.length) return;
    this.seen = sig;
    setShared(KEPT, { ...kept, resumed, pending });
    cx.timer.after(0, (cx) => this.load(cx));
  }

  /** The chats from core/chats.py, the running ones marked; an answer for an older look kept. */
  load(cx) {
    const list = running();
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(CHATS, ["list", JSON.stringify(list), JSON.stringify(this.resumed())],
          home(), null);
        this.items = answer.chats;
        this.leaving = stillLeaving(this.leaving, this.items);
        this.archived = new Set(answer.archived);
        this.loaded = true;
        this.failed = null;
      } catch (e) {
        if (this.loaded) keepNote(this, { text: said(e), error: true }, cx);       // the list kept, why under it
        else this.failed = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** The rows shown: every space of this Mac with chats, as the TUI's column lists them. */
  rows() {
    const all = spaces(), here = all.find((s) => s.active)?.name ?? null;
    const actives = new Set(all.map((s) => s.tabs.find((tab) => tab.active)?.id));
    const front = new Set([...agents().filter((a) => actives.has(a.tab)).map((a) => a.address),
      ...terminals().filter((c) => actives.has(c.labels?.[CHAT_TAB])).map((c) => c.address)]);
    return chatRows(withoutLeaving(this.items, this.leaving), all.filter((s) => s.machine === null).map((s) => s.name),
      folderSpaces(all, panes()), { typed: this.typed, archived: this.archived, showArchived: showsArchived(),
        opened: this.opened, closed: this.closed, here, front });
  }

  /** ITEM shown (showChat()), the list closed then; why it could not be, under the list. @param {Listed} item */
  open(item, cx) {
    try {
      const failed = showChat(item);
      if (failed) keepNote(this, { text: failed, error: true }, cx);
      else this.close();
    } catch (e) {
      keepNote(this, { text: said(e), error: true }, cx);
    }
  }

  /** The window it shows in closed, or in the dock, the view it stands in for back. */
  close() {
    if (this.overlay) closeOverlay(this.overlay);
    else this.back?.();
  }

  /** ITEM's whole chat on the clipboard, as Markdown. @param {Listed} item */
  copy(item, cx) {
    this.ask(["markdown", item.agent, item.id], cx, (answer, cx) => {
      if (answer.markdown === null) throw new Error("Its file is gone");
      cx.write_to_clipboard(answer.markdown);
      return "Chat copied";
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
      else if (action === "delete") Object.assign(this, { asking: archiveKey(item), naming: null });
      else this.ask([action, archiveKey(item)], cx, () => `${action === "archive" ? "Archived" : "Unarchived"} "${
        item.title.replace(/\p{Cc}/gu, "?")}"`);
    }
    cx.notify();
  }

  /** The Delete… asked about dropped: nothing moved. */
  unask(cx) {
    this.asking = null;
    cx.notify();
  }

  /** ITEM's file to the Trash (core/chats.py's delete, which asks herdr's agents once more whether it runs): its row
   * gone at once, back with why under the list when the Trash did not take it. @param {Listed} item */
  delete(item, cx) {
    const key = archiveKey(item);
    this.asking = null;
    this.leaving.add(key);
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(CHATS, ["delete", item.agent, item.id, JSON.stringify(running()),
          JSON.stringify(this.resumed())], home(), null);
        if (answer.ok === false) throw new Error(answer.advice);
        keepNote(this, { text: "Moved to Trash", error: false }, cx);
      } catch (e) {
        this.leaving.delete(key);
        keepNote(this, { text: said(e), error: true }, cx);
      } finally {
        this.load(cx);
      }
    });
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

  /** core/chats.py's ARGS, then DONE with its answer (what to say, or null) under the list, and the list read again. */
  ask(args, cx, done) {
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(CHATS, args, home(), null);
        if (answer.ok === false) throw new Error(answer.advice);
        const text = done(answer, cx);
        keepNote(this, text ? { text, error: false } : null, cx);
      } catch (e) {
        keepNote(this, { text: said(e), error: true }, cx);
      } finally {
        this.load(cx);
      }
    });
  }

  /** The Filter field taking the keys, as the TUI's list opens. */
  focus() {
    this.find.focus();
  }

  /** Esc in the list or its filter: a name being typed or a Delete… asked about dropped, else the list closed, the
   * view back in the dock. */
  escape(e, cx) {
    if (e.key !== "escape") return;
    cx.stop_propagation();
    if (this.naming || this.asking) {
      this.naming = this.asking = null;
      this.focus();                               // the keys back in the filter, whose next Esc closes the list
      return void cx.notify();
    }
    if (this.typed) {
      this.find.set_value("");                    // the filter's words first
      this.typed = "";
      return void cx.notify();
    }
    this.close();
  }

  render(t, cx) {
    this.look(cx);
    const asked = chatsAsked(shared(OPENED));     // the list opened again: the filter takes the keys again
    if (asked.at !== this.opening) {
      this.opening = asked.at;
      if (!this.overlay) cx.timer.after(0, () => this.focus());
      if (asked.space) this.reveal(asked.space, cx);
    }
    return this.list(t, this.rows());
  }

  /** Group NAME (a chat's clock asked for its folder's chats) opened and scrolled to: from the list's end
   * back to its head, so it stands first in view (groupPlace's). @param {string} name */
  reveal(name, cx) {
    this.opened.add(name);
    this.closed.delete(name);
    const place = groupPlace(this.rows(), name);
    if (!place) return;
    cx.timer.after(0, (/** @type {any} */ cx) => {
      this.scroll.scroll_to_item(place.last);
      cx.notify();
      cx.timer.after(0, (/** @type {any} */ cx) => {
        this.scroll.scroll_to_item(place.head);
        cx.notify();
      });
    });
  }

  /** ITEM's agent's icon, Claude Code's or Codex's, as the app draws a program's; null while the app has not named
   * them. @param {Listed} item @param {number} size */
  agentIcon(item, size) {
    const p = this.programs[item.agent];
    if (!p?.icon) return null;
    return p.tint ? svg(p.icon).size(size).flex_none() : image(p.icon).w(size).h(size).flex_none();
  }

  /** The list: the filter (beside the rail, the window's head has its ×), ROWS (what there is to say instead in the
   * first one's place: loading, the list's failure, none), then what was done under them, moving none. */
  list(t, rows) {
    const empty = !this.loaded ? (this.failed ? `Couldn't read the chats: ${this.failed}` : "Loading chats…")
      : rows.length ? null : this.typed ? "No chat matches" : "No chats";
    return v_flex().size_full().min_h(0).text_color(t.foreground).text_size(13)
      .on_key_down((e, cx) => this.escape(e, cx))
      .child(h_flex().flex_none().p(PAD).pb(6).gap(4).items_center()
        .child(field(t, "chats-filter", this.find).flex_1()))
      .child(v_flex().id("chats").flex_1().min_h(0).overflow_y_scrollbar().px(PAD / 2).pb(PAD / 2)
        .when(Boolean(this.scroll), (e) => e.track_scroll(this.scroll))
        .on_mouse_down("right", () => this.menus.open(this.choices(null)))
        .when(Boolean(empty), (e) => e.child(h_flex().min_h(SPACE_ROW).py(2).px(PAD / 2).items_center().text_size(12)
          .text_color(this.failed && !this.loaded ? t.ansi1 : t.muted).child(empty ?? "")))
        .children(rows.filter((row) => row.kind === "group").flatMap((row) => [this.group(t, row),
          this.members(t, row)])))
      .when(Boolean(this.note), (e) => e.child(footNote(t, this.note)));
  }

  /** ROW's chats under it, sliding open and shut as the Changes' sections do. */
  members(t, row) {
    return v_flex().id(`members-${this.slides}${row.name}`).flex_none().overflow_hidden()
      .h(row.open ? row.items.length * CHAT_ROW : 0).spring("height", SPRING)
      .children(row.items.map((item) => this.row(t, item)));
  }

  /** A space as the TUI's column has it: its chevron leftmost, its name (the one shown bold), how many it holds; a
   * click folds or opens it. */
  group(t, row) {
    const here = row.here;
    return h_flex().id(`space-${row.name}`).h(SPACE_ROW).flex_none().px(PAD / 2).gap(6).items_center().rounded(6)
      .cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_click((_e, cx) => {
        const set = row.open ? this.closed : this.opened, other = row.open ? this.opened : this.closed;
        set.add(row.name);
        other.delete(row.name);
        cx.notify();
      })
      .child(fold(`space-${row.name}-fold`, row.open, CHEVRON, t.dim))
      .child(div().flex_1().min_w(0).truncate().text_color(here ? t.foreground : t.muted)
        .when(here, (e) => e.font_bold()).child(row.name))
      .child(div().flex_none().text_size(11).text_color(t.muted).child(String(row.items.length)));
  }

  /** A chat: its state's mark, its agent's icon, its name; at its end its agent (with no icon) and its age, two
   * right-aligned columns; a click shows it, a right click its menu; Delete… asked in its place, as Files asks.
   * @param {Listed} item */
  row(t, item) {
    const key = archiveKey(item), archived = this.archived.has(key), asking = this.asking === key;
    const title = item.title.replace(/\p{Cc}/gu, "?");    // a title's escape codes shown, never run
    const look = archived ? t.muted : item.state ? t.foreground : t.muted, agent = this.agentIcon(item, 13);
    const named = NAMES[item.agent] ?? `${item.agent.slice(0, 1).toUpperCase()}${item.agent.slice(1)}`;
    return h_flex().id(`chat-${key}`).h(CHAT_ROW).flex_none().pl(UNDER).pr(PAD / 2).gap(6).items_center().rounded(6)
      .cursor_pointer().hover((s) => s.bg(t.hover)).on_click((_e, cx) => (asking ? null : this.open(item, cx)))
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
      .when(asking, (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi1).child("Move to Trash?"))
        .child(h_flex().flex_none().gap(GAP)
          .child(small(t, `chat-${key}-keep`, "Cancel", "Keep it", true, (cx) => this.unask(cx)))
          .child(small(t, `chat-${key}-trash`, "Move", `Move “${title}” to the Trash`, true,
            (cx) => this.delete(item, cx)))))
      .when(!asking && !agent, (e) => e.child(div().w(AGENT).flex_none().text_right().truncate().text_size(11)
        .text_color(t.muted).child(named)))
      .when(!asking, (e) => e.child(div().w(AGE).flex_none().text_right().truncate().text_size(11)
        .text_color(t.muted).child(archived ? "archived" : item.ago)));
  }

  /** The right click's menu: on ITEM what can be done with it (a running one's Delete… off, its tip saying why), on
   * the list (null) the archived shown or hidden. @param {Listed | null} item @returns {import("./menus.js").Item[]} */
  choices(item) {
    const choices = chatChoices(item, this.archived, showsArchived());
    const off = item ? deleteOff(item) : null;
    if (!choices.length) return [{ label: "Nothing archived", off: true }];
    return choices.map((choice) => (choice === "Delete…" && off ? { label: choice, off: true, tip: off }
      : { label: choice, act: (cx) => this.pick(choice, item, cx) }));
  }
}
