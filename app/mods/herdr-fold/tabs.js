// @ts-check
// The tab bar where the app's own was, drawn as the app draws it: the space's tabs as pills, dragged into order, a
// double click renaming one, a right click the app's menu, the wheel stepping through them; + after the last tab.
import { div, image, svg } from "gpui-kit";
import { h_flex } from "gpui-base";
import { layout, openOverlay, panes, settings, spaces, terminals, window, run as command } from "herdr";
import { CHAT_TAB, hovering, lightsRoom, tabRows, toggleRoom } from "./logic.js";
import { panelToggle } from "./panel.js";
import { BUTTON, GAP, icon, iconButton } from "./parts.js";

/** @typedef {ReturnType<typeof tabRows>[number]} Tab */
/** @typedef {{ lights: number, end: number, buttons: any }} Room the room before the tabs (the traffic lights'),
 * after the toggle (the rail's middle under it), and the window's own buttons where the app draws them, else null */

export class TabsView {
  constructor() {
    /** @type {number | null} the tab pressed, while it may be dropped on another */
    this.pressed = null;
    /** @type {string | null} the tab the pointer is on (hovering's): its × shown */
    this.hovered = null;
  }

  render(t) {
    const space = spaces().find((s) => s.active), w = window(), root = layout(), buttons = w?.buttons ? w : null;
    const chats = Object.fromEntries(terminals().filter((c) => c.state === "live" && c.labels?.[CHAT_TAB])
      .map((c) => [c.labels[CHAT_TAB], c]));                // a chat tab's agent: a terminal with no pane
    return this.draw(t, tabRows(space, panes(), chats), space?.id ?? null, {
      lights: lightsRoom(root, w, settings().zoom), end: buttons ? 8 : toggleRoom(root, BUTTON), buttons });
  }

  /** ROWS (tabRows') of SPACE, in ROOM. @param {Tab[]} rows @param {string | null} space @param {Room} room */
  draw(t, rows, space, { lights, end, buttons }) {
    return h_flex().size_full().min_w(0).pl(lights).pr(end).gap(GAP).items_center().bg(t.chrome)
      .on_mouse_up("left", () => {
        this.pressed = null;
      })
      .on_scroll_wheel((e) => {
        if (Math.abs(e.delta.y) >= 1) command(e.delta.y > 0 ? "tab.prev" : "tab.next");
      })
      .child(h_flex().id("tab-scroll").flex_shrink(1).min_w(0).h_full().items_center().gap(GAP)
        .overflow_x_scroll().children(rows.map((r, i) => this.tab(t, r, i, rows, space))))
      .child(iconButton(t, "tab-new", "plus", "New tab", () => openOverlay({ mod: "new-menu", kind: "popup",
        width: 250, height: 512 }), { size: 15 }))
      .child(div().flex_1())
      .child(panelToggle(t))
      .when(Boolean(buttons), (e) => e.child(h_flex().pl(8).gap(GAP)
        .child(iconButton(t, "window-minimize", "minus", "Minimize", () => command("window.minimize"), { left: true }))
        .child(iconButton(t, "window-maximize", buttons.maximized ? "copy" : "square",
          buttons.maximized ? "Restore" : "Maximize", () => command("window.maximize"), { size: 13, left: true }))
        .child(iconButton(t, "window-close", "x", "Close", () => command("window.close"), { left: true }))));
  }

  /** A tab's pill, as the panel's tabs: an agent's icon, its name, a working agent's spinner or a state's dot, and
   * the place of its ×, shown on the shown tab and under the pointer (its glyph sits inside its square: closer, so it
   * looks as far as the start's). @param {Tab} r @param {number} i @param {Tab[]} rows @param {string | null} space */
  tab(t, r, i, rows, space) {
    const closing = r.active || this.hovered === r.id;
    return h_flex().id(`tab-${r.id}`).h(28).pl(12).pr(8).gap(2).rounded(6).items_center().flex_none().text_size(13)
      .border_1().border_color(r.active ? t.border : t.chrome).bg(r.active ? t.raised : t.chrome)
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
