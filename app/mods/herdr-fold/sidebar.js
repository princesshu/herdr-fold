// @ts-check
// The sidebar folded to a rail, as Adobe's collapsed panel dock: Spaces and Conversations as icons, each floating
// beside it when pressed; its toggle left of the tabs. While it is open, the app's own Spaces list, toggle and footer.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { closeOverlay, layout, openOverlay, setShared, shared, spaces, updates, window, run as command } from "herdr";
import { avatarFill, floatHeight, foldedWidth, railed, sidebarPx, urgent, waited } from "./logic.js";
import { GAP, icon, iconButton, iconTab, listName, stateMark } from "./parts.js";
import { spaceColorsKept, waitsBySpace } from "./spaces.js";

const FOLDED = ["sidebar-trigger"];       // the layout's blocks shown while folded
const OPEN = ["spaces", "sidebar-footer"];     // and the app's own, shown while open: folded, the dock has them
const FLOAT = 300;                 // a panel floating beside the rail: as wide as the open sidebar

/** The blocks of the folded sidebar shown, or the open one's, as FOLDED says. @param {boolean} folded */
export function followFold(folded) {
  for (const id of FOLDED) command(folded ? "layout.show" : "layout.hide", { id });
  for (const id of OPEN) command(folded ? "layout.hide" : "layout.show", { id });
}

/** Whether the sidebar is a rail now: folded by its toggle, or dragged as narrow. */
export const folded = () => railed(layout());

/** The sidebar folded to its rail, or opened again to the width it had, as the app's own toggle does it. */
function foldSidebar() {
  const root = layout(), now = railed(root);
  if (!now) setShared("sidebar.width", sidebarPx(root));
  setShared("sidebar.collapsed", !now);         // what mods made before the rail went by width read
  command("layout.resize", { id: "sidebar", px: foldedWidth(root, window()?.platform === "macos",
    shared("sidebar.width") ?? undefined) });
}

/** The tab bar's left end while the sidebar is a rail: its toggle, as a sidebar's trigger. */
export function sidebarTrigger(t) {
  return v_flex().size_full().items_center().justify_center()
    .child(iconButton(t, "sidebar-open", "panel-left", "Show sidebar", foldSidebar, { size: 15 }));
}

/** PANEL ("spaces", "conversations") floating beside the folded rail, level with BOUNDS, as Adobe's collapsed panels
 * open: one at a time, in the other's place, HEIGHT as its content, THEN ("focus": its filter takes the keys); dragged
 * by its head, it stays where dropped until its ×. @param {string} panel @param {any} bounds @param {number} height */
export function openFloat(panel, bounds, height, then = undefined) {
  const props = { part: "float", panel, height, then };
  openOverlay({ mod: "herdr-fold", kind: "window", key: "herdr-fold.dock", props,
    at: { x: (sidebarPx(layout()) ?? 76) + 6, y: Math.max(8, bounds?.y ?? 8) }, width: FLOAT, height });
}

/** A floating panel's head, as Adobe's: NAME, BUTTONS, and × closing it (OVERLAY); it drags the panel.
 * @param {string} name @param {string} overlay @param {any[]} buttons */
export function floatHead(t, name, overlay, buttons) {
  return h_flex().w_full().h(36).flex_none().pl(16).pr(6).gap(GAP).items_center()
    .child(listName(t, name).flex_1()).children(buttons)
    .child(iconButton(t, "float-close", "x", "Close", () => closeOverlay(overlay)));
}

/** A panel floating beside a rail (OVERLAY, a window HEIGHT high, else its window's height): its head, then BODY, which
 * keeps its presses. @param {string} name @param {string} overlay @param {number | undefined} height
 * @param {any[]} buttons @param {any} body */
export function floatPanel(t, name, overlay, height, buttons, body) {
  return (height ? v_flex().w_full().h(height) : v_flex().size_full()).text_size(13)   // on the window's own fill
    .child(floatHead(t, name, overlay, buttons))
    .child(v_flex().flex_1().min_h(0).on_mouse_down("left", (_e, cx) => cx.stop_propagation()).child(body));
}

/** The folded sidebar as Adobe's collapsed dock: Spaces and Conversations at their most urgent of SPACES' and TALKS'
 * states, each floating beside it by a press (Conversations TALL as its rows); the app's footer centered at its foot.
 * @param {(string | null)[]} spaces @param {(string | null)[]} talks @param {number} tall */
export function dock(t, spaces, talks, tall) {
  const dot = (states) => (urgent(states) ? t[/** @type {string} */ (urgent(states))] : null);
  return v_flex().id("dock").size_full().min_h(0).items_center()
    .child(v_flex().flex_1().pt(8).gap(12).items_center()
      .child(dockButton(t, "spaces", "layers", "Spaces", dot(spaces), floatHeight("spaces", spaces.length)))
      .child(dockButton(t, "conversations", "message-square", "Conversations", dot(talks), tall)))
    .child(v_flex().w_full().flex_none().items_center().gap(GAP).pt(4).pb(8).border_t(1).border_color(t.border)
      .child(iconButton(t, "dock-settings", "settings", "Settings", () => command("app.settings"))
        .when(Boolean(updates().app.ready), (e) => e.child(div().absolute().top(3).right(3).size(6).rounded_full()
          .bg(t.accent))))
      .child(iconButton(t, "dock-machine", "plus", "Add machine", () => command("mod.open", { name: "machine-add" }),
        { color: t.dim })));
}

/** A panel of the folded rail, as Adobe's collapsed dock shows one: its icon (NAME) on a square, DOT its most urgent
 * state's color, LABEL under it; a press floats it beside the rail, HEIGHT high. @param {string} panel @param {string}
 * label @param {import("./icons.js").IconName} name @param {string | null} dot @param {number} height */
function dockButton(t, panel, name, label, dot, height) {
  return v_flex().id(`dock-${panel}`).flex_none().items_center().gap(4).cursor_pointer()
    .on_mouse_down("left", (e, cx) => {
      cx.stop_propagation();
      openFloat(panel, e.bounds, height);
    })
    .child(iconTab(t, `dock-${panel}-tab`, icon(name, 15), { dot, tip: label, act: () => {} }))
    .child(div().text_size(10).text_color(t.dim).child(label));
}

/** The Spaces panel floating beside the folded rail (OVERLAY, HEIGHT high): each of LIST by its avatar (COLORS), its
 * name, how long it waits on you (SINCE) and its most urgent agent's state, the shown one selected; a click shows it.
 * @param {string} overlay @param {number} height */
export function spacesFloat(t, overlay, height, list = spaces(), colors = spaceColorsKept(), since = waitsBySpace(),
  now = Date.now()) {
  return floatPanel(t, "Spaces", overlay, height,
    [iconButton(t, "float-new-space", "plus", "New space", () => command("space.new", {}))],
    v_flex().id("float-spaces").size_full().overflow_y_scrollbar().px(8).pb(8).gap(2)
      .children(list.map((space) => h_flex().id(`float-space-${space.id}`).h(28).flex_none().px(8).gap(8)
        .items_center().rounded(6).cursor_pointer().when(space.active, (e) => e.bg(t.selected))
        .hover((s) => s.bg(t.hover)).on_click(() => command("space.select", { id: space.id }))
        .child(h_flex().size(18).flex_none().rounded(4).bg(avatarFill(colors[space.id] ?? "ansi6", t))
          .items_center().justify_center()
          .text_size(11).font_bold().text_color("#ffffff").child([...space.name][0]?.toUpperCase() ?? "?"))
        .child(div().flex_1().min_w(0).truncate().text_color(space.active ? t.foreground : t.muted)
          .when(space.active, (e) => e.font_bold()).child(space.name))
        .when(Boolean(since[space.id]), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
          .child(waited(now - since[space.id]))))
        .child(stateMark(t, space.status)))));
}
