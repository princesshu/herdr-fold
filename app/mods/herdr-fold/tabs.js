// @ts-check
// The tab bar where the app's own was, under the title row (title.js): the space's tabs as pills (dragged, renamed,
// the app's menu, the wheel), + and >_ after them; at its end, over the dock, Chats, More and » (« on the rail).
import { div, image, svg } from "gpui-kit";
import { h_flex } from "gpui-base";
import { knownAgents, layout, openOverlay, panes, shared, spaces, terminals, run as command } from "herdr";
import { ADAPTERS, AGENTS_OPEN, agentsOpen, newAgent, RECENT_AGENTS } from "./agents.js";
import { chatWaits, newAgentIn } from "./chat.js";
import { waiting } from "./chats.js";
import { agentsTab } from "./graph.js";
import { ICONS } from "./icons.js";
import { CHAT_TAB, hovering, tabRows, toggleRoom } from "./logic.js";
import { Menus } from "./menus.js";
import { askChats, chatsShown, dockOpen, foldDock, openMore, panelToggle } from "./panel.js";
import { BUTTON, GAP, icon, iconButton } from "./parts.js";

const START = 10;                  // px before the first tab, as the app's own bar has it

/** @typedef {ReturnType<typeof tabRows>[number]} Tab */
/** @typedef {{ start: number, end: number }} Room the room before the first tab, and after » (the rail's middle
 * under it) */
/** @typedef {{ tip: string, act: () => void }} Plus what + says and does: a new chat, or the latest agent's terminal */
/** @typedef {{ waiting: number, listed: boolean, open: boolean, menu: boolean }} End the bar's end: the chats WAITING
 * on you, whether Chats' list is LISTED in the dock, the dock OPEN, More's MENU up (its tip quiet till the pointer
 * leaves it) */
/** @typedef {{ chats: () => void, more: (cx: any) => void, press: (e: any) => void, away: (cx: any) => void,
 * fold: () => void }} EndActs what Chats, More (its PRESS first, the pointer AWAY after) and » / « do */

/** The tab bar's end over the dock (END), as center-chat.html's: ✦ Chats, its dot in ansi3 while chats wait (their
 * number in its tip), lit while its list shows; ⋯ More, its menu under it (a newer herdr-fold is the status bar's to
 * say); then » / «. @param {End} end @param {EndActs} acts */
export const barEnd = (t, { waiting, listed, open, menu }, acts) => h_flex().flex_none().gap(GAP).items_center()
  .child(iconButton(t, "bar-chats", "sparkle", waiting ? `Chats · ${waiting} waiting` : "Chats", () => acts.chats(),
    { size: 15, left: true, lit: listed, dot: waiting ? t.ansi3 : null }))
  .child(div().id("bar-more-room").on_hover((over, cx) => void (!over && acts.away(cx)))
    .child(iconButton(t, "bar-more", "ellipsis", menu ? null : "More", (/** @type {any} */ cx) => acts.more(cx),
      { size: 15, left: true, press: acts.press })))
  .child(panelToggle(t, open, acts.fold));

export class TabsView {
  constructor() {
    /** @type {number | null} the tab pressed, while it may be dropped on another */
    this.pressed = null;
    /** @type {string | null} the tab the pointer is on (hovering's): its × shown */
    this.hovered = null;
    /** @type {Record<string, string> | null} the agents' names (knownAgents'), +'s tip in a terminal's way */
    this.names = null;
    this.menus = new Menus();                    // More's, its choice answered from main.js's loop
    /** @type {any} More's bounds as pressed, its menu under it */
    this.more = null;
    this.menuUp = false;                         // More's menu opened, its tip quiet till the pointer leaves it
  }

  /** What + says and does in SPACE, as Settings' Open agents in has it: New chat (Cmd+N), or the agent used last in a
   * terminal tab, named. @param {any} space @returns {Plus} */
  plus(space) {
    if (!this.names) {
      this.names = {};
      knownAgents().then((list) => void (this.names = Object.fromEntries(list.map((a) => [a.key, a.name]))))
        .catch(() => {});
    }
    const { agent, as } = newAgent(shared(RECENT_AGENTS), agentsOpen(shared(AGENTS_OPEN)), space?.machine ?? null);
    const name = this.names[agent] ?? ADAPTERS[agent]?.name ?? agent;
    return { tip: as === "chat" ? "New chat" : `New ${name}`,
      act: () => void (space && newAgentIn(space).catch(() => {})) };
  }

  render(t) {
    const space = spaces().find((s) => s.active);
    const chats = Object.fromEntries(terminals().filter((c) => c.state === "live" && c.labels?.[CHAT_TAB])
      .map((c) => [c.labels[CHAT_TAB], c]));                // a chat tab's agent: a terminal with no pane
    const agents = agentsTab(space, panes())?.id;           // the Agents tab wears Lucide's share-2, usage.html's
    const rows = tabRows(space, panes(), chats, chatWaits().tabs).map((row) => (row.id === agents
      ? { ...row, icon: ICONS["share-2"], tint: true } : row));
    return this.draw(t, rows, space?.id ?? null,
      { start: START, end: toggleRoom(layout(), BUTTON) }, this.plus(space), { waiting: waiting(),
        listed: chatsShown(), open: dockOpen(), menu: this.menuUp }, this.endActs());
  }

  /** What the bar's end does here: Chats' list, More's menu under it (its tip quiet meanwhile), » / «. */
  endActs() {
    const quiet = (/** @type {boolean} */ up, /** @type {any} */ cx) => {
      if (this.menuUp === up) return;
      this.menuUp = up;
      cx.notify();
    };
    return { chats: askChats, press: (/** @type {any} */ e) => (this.more = e.bounds), fold: foldDock,
      more: (/** @type {any} */ cx) => (openMore(this.menus, this.more), quiet(true, cx)),
      away: (/** @type {any} */ cx) => quiet(false, cx) };
  }

  /** ROWS (tabRows') of SPACE, in ROOM, PLUS +'s: + a new agent (a chat by default), >_ a new terminal (the app's own
   * list, its agents too), no menu between; at the end Chats, More and » / « (BAR, ACTS). @param {Tab[]} rows
   * @param {string | null} space @param {Room} room @param {Plus} plus @param {End} bar @param {EndActs} acts */
  draw(t, rows, space, { start, end }, plus, bar, acts) {
    return h_flex().size_full().min_w(0).pl(start).pr(end).gap(GAP).items_center().bg(t.canvas)
      .on_mouse_up("left", () => {
        this.pressed = null;
      })
      .on_scroll_wheel((e) => {
        if (Math.abs(e.delta.y) >= 1) command(e.delta.y > 0 ? "tab.prev" : "tab.next");
      })
      .child(h_flex().id("tab-scroll").flex_shrink(1).min_w(0).h_full().items_center().gap(GAP)
        .overflow_x_scroll().children(rows.map((r, i) => this.tab(t, r, i, rows, space))))
      .child(iconButton(t, "tab-new", "plus", plus.tip, () => plus.act(), { size: 15 }))
      .child(iconButton(t, "tab-terminal", "terminal", "New terminal", () => openOverlay({ mod: "new-menu",
        kind: "popup", width: 250, height: 512 }), { size: 15 }))
      .child(div().flex_1())
      .child(barEnd(t, bar, acts));
  }

  /** A tab's pill, as the panel's tabs: an agent's icon, its name, a working agent's spinner or a state's dot, and
   * the place of its ×, shown on the shown tab and under the pointer (its glyph sits inside its square: closer, so it
   * looks as far as the start's). @param {Tab} r @param {number} i @param {Tab[]} rows @param {string | null} space */
  tab(t, r, i, rows, space) {
    const closing = r.active || this.hovered === r.id;
    return h_flex().id(`tab-${r.id}`).h(28).pl(12).pr(8).gap(2).rounded(6).items_center().flex_none().text_size(13)
      .border_1().border_color(r.active ? t.border : t.canvas).bg(r.active ? t.raised : t.canvas)
      .text_color(r.active ? t.foreground : t.muted).cursor_pointer().on_hover(hovering(this, r.id))
      .hover((s) => s.bg(t.hover).border_color(r.active ? t.border : t.hover))
      .on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();                    // the tab's press, never the window's drag
        this.pressed = i;
        if (e.click_count === 2) command("tab.rename", { id: r.id });
      })
      .on_mouse_up("left", () => {
        const from = this.pressed;
        this.pressed = null;
        if (from !== null && from !== i) command("tab.move", { id: rows[from].id, index: i + 1 });
        else command("tab.select", { id: r.id });
      })
      .on_mouse_down("right", (_e, cx) => {
        cx.stop_propagation();
        openOverlay({ mod: "menu", kind: "popup", width: 200, props: { tab: "tab", target: { id: r.id, space } } });
      })
      .child(h_flex().gap(6).items_center()
        .when(Boolean(r.icon), (e) => e.child(r.tint ? svg(String(r.icon)).size(14).text_color(t.muted)
          : image(String(r.icon)).size(14)))
        .child(div().max_w(170).truncate().child(r.name))
        .when(r.status === "working", (e) => e.child(icon("loader-circle", 12).text_color(t.working).spin(900)))
        .when(r.status === "blocked" || r.status === "done", (e) => e.child(div().size(6).rounded_full()
          .bg(t[String(r.status)]))))
      .child(div().id(`close-${r.id}`).size(16).flex_none().flex().items_center().justify_center().rounded(4)
        .when(!closing, (s) => s.invisible()).text_color(t.dim).cursor_pointer().tooltip("Close tab")
        .hover((s) => s.bg(t.hover).text_color(t.foreground))
        .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
        .on_click((_e, cx) => {
          cx.stop_propagation();
          command("tab.close", { id: r.id });
        })
        .child(icon("x", 12)));
  }
}
