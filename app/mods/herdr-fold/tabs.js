// @ts-check
// The tab bar where the app's own was, drawn as the app draws it: the space's tabs as pills, dragged into order, a
// double click renaming one, a right click the app's menu, the wheel stepping through them; each button with its tip.
import { div, image, svg } from "gpui-kit";
import { h_flex } from "gpui-base";
import { layout, openOverlay, panes, settings, spaces, window, run as command } from "herdr";
import { lightsRoom, tabRows } from "./logic.js";
import { icon, iconButton } from "./parts.js";

/** @typedef {ReturnType<typeof tabRows>[number]} Tab */

export class TabsView {
  constructor() {
    /** @type {number | null} the tab pressed, while it may be dropped on another */
    this.pressed = null;
  }

  render(t) {
    const space = spaces().find((s) => s.active), w = window();
    return this.draw(t, tabRows(space, panes()), space?.id ?? null, lightsRoom(layout(), w, settings().zoom),
      w?.buttons ? w : null);
  }

  /** ROWS (tabRows') of SPACE, ROOM px before them for the traffic lights, and window W's own buttons where the app
   * draws them (W: null on macOS). @param {Tab[]} rows @param {string | null} space @param {number} room
   * @param {any} w */
  draw(t, rows, space, room, w) {
    return h_flex().size_full().min_w(0).pl(room).pr(10).gap(3).items_center().bg(t.chrome).border_b(1)
      .border_color(t.border)
      .on_mouse_up("left", () => {
        this.pressed = null;
      })
      .on_scroll_wheel((e) => {
        if (Math.abs(e.delta.y) >= 1) command(e.delta.y > 0 ? "tab.prev" : "tab.next");
      })
      .child(h_flex().id("tab-scroll").flex_1().min_w(0).h_full().items_center().gap(3).overflow_x_scrollbar()
        .children(rows.map((r, i) => this.tab(t, r, i, rows, space))))
      .child(iconButton(t, "tab-new", "plus", "New tab", () => openOverlay({ mod: "new-menu", kind: "popup",
        width: 250, height: 512 }), { size: 15 }))
      .when(Boolean(w), (e) => e
        .child(iconButton(t, "window-minimize", "minus", "Minimize", () => command("window.minimize")))
        .child(iconButton(t, "window-maximize", w.maximized ? "copy" : "square", w.maximized ? "Restore" : "Maximize",
          () => command("window.maximize"), { size: 13 }))
        .child(iconButton(t, "window-close", "x", "Close", () => command("window.close"))));
  }

  /** A tab's pill: its program's icon, its name, a working agent's spinner or a state's dot, the shown one's ×.
   * @param {Tab} r @param {number} i @param {Tab[]} rows @param {string | null} space */
  tab(t, r, i, rows, space) {
    return h_flex().id(`tab-${r.id}`).h(29).px(10).gap(7).rounded(7).items_center().flex_none().text_size(12.8)
      .border(1).border_color(r.active ? t.border : t.chrome).bg(r.active ? t.raised : t.chrome)
      .text_color(r.active ? t.foreground : t.muted).cursor_pointer().hover((s) => s.bg(t.hover))
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
      .when(Boolean(r.icon), (e) => e.child(r.tint ? svg(String(r.icon)).size(14).text_color(t.muted)
        : image(String(r.icon)).size(14)))
      .child(div().max_w(170).truncate().child(r.name))
      .when(r.status === "working", (e) => e.child(icon("loader-circle", 12).text_color(t.working).spin(900)))
      .when(r.status === "blocked" || r.status === "done", (e) => e.child(div().size(6).rounded(3)
        .bg(t[String(r.status)])))
      .when(r.active, (e) => e.child(div().id(`close-${r.id}`).flex_none().rounded(4).text_color(t.dim)
        .cursor_pointer().tooltip("Close tab").hover((s) => s.text_color(t.foreground))
        .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
        .on_click((_e, cx) => {
          cx.stop_propagation();
          command("tab.close", { id: r.id });
        })
        .child(icon("x", 12))));
  }
}
