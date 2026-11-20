// @ts-check
// The sidebar folded to a rail, as Adobe's collapsed panel dock: Spaces as an icon, floating beside it when pressed,
// its toggle left of the tabs. Open: its head (Herdr's mark and name, Go to space or tab, its toggle), Spaces, footer.
import { div, image } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { closeOverlay, layout, openOverlay, setShared, shared, window, run as command } from "herdr";
import { avatarFill, floatHeight, foldedWidth, HOME_NAME, railed, sidebarPx, spaceLabel, urgent, waited }
  from "./logic.js";
import { GAP, icon, iconButton, iconTab, listName, stateMark } from "./parts.js";
import { floatSpaces, openHome, spaceColorsKept, waitsBySpace } from "./spaces.js";

const FOLDED = ["sidebar-trigger"];       // the layout's blocks shown while folded
const OPEN = ["sidebar-footer"];          // and the app's own, shown while open: folded, the dock has its buttons
const FLOAT = 300;                 // Spaces floating beside the rail: as wide as the open sidebar
const HERDR_MARK = "frame/welcome/herdr.png";    // Herdr's mark, the app's own picture (its sidebar head's)

/** The blocks of the folded sidebar shown (RAIL), or the open one's. @param {boolean} rail */
function followFold(rail) {
  for (const id of FOLDED) command(rail ? "layout.show" : "layout.hide", { id });
  for (const id of OPEN) command(rail ? "layout.hide" : "layout.show", { id });
}

/** Whether the sidebar is a rail now: folded by its toggle, or dragged as narrow. */
const folded = () => railed(layout());

/** From the Spaces block's render: whether the sidebar is a rail, the blocks beside it shown or hidden once that
 * changed since HOLDER's last look, after the render. @param {{ railed?: boolean }} holder */
export function trackFold(holder, cx) {
  const now = folded();
  if (now !== holder.railed) {
    holder.railed = now;
    cx.timer.after(0, () => followFold(now));
  }
  return now;
}

/** The sidebar folded to its rail, or opened again to the width it had, as the app's own toggle does it. */
function foldSidebar() {
  const root = layout(), now = railed(root);
  if (!now) setShared("sidebar.width", sidebarPx(root));
  setShared("sidebar.collapsed", !now);         // what mods made before the rail went by width read
  command("layout.resize", { id: "sidebar", px: foldedWidth(root, window()?.platform === "macos",
    shared("sidebar.width") ?? undefined) });
}

/** The open sidebar's head on the tab row's line: Herdr's mark and name in the Spaces rows' columns (over their avatars
 * and names), Go to space or tab and the toggle at its end (.brand), the toggle over Spaces' +. Folded, empty: the
 * toggle is left of the tabs then (OPEN: the sidebar's own state, unless given). */
export function sidebarHead(t, open = !folded()) {
  return h_flex().size_full().pl(16).pr(8).gap(GAP).items_center().bg(t.chrome).text_size(13)
    .when(open, (e) => e
      .child(h_flex().flex_1().min_w(0).gap(8).items_center()
        .child(image(HERDR_MARK).size(18).flex_none().rounded(4))
        .child(div().min_w(0).truncate().font_semibold().text_color(t.foreground).child("Herdr")))
      .child(iconButton(t, "sidebar-search", "search", "Go to space or tab",
        () => command("mod.open", { name: "picker" }), { size: 15 }))
      .child(iconButton(t, "sidebar-hide", "panel-left", "Hide sidebar", foldSidebar, { size: 15 })));
}

/** The tab bar's left end while the sidebar is a rail: its toggle, as a sidebar's trigger. */
export function sidebarTrigger(t) {
  return v_flex().size_full().items_center().justify_center()
    .child(iconButton(t, "sidebar-open", "panel-left", "Show sidebar", foldSidebar, { size: 15 }));
}

/** Spaces floating beside the folded rail, level with BOUNDS, as Adobe's collapsed panels open, HEIGHT as its rows;
 * dragged by its head, it stays where dropped until its ×. @param {any} bounds @param {number} height */
function openFloat(bounds, height) {
  openOverlay({ mod: "herdr-fold", kind: "window", key: "herdr-fold.dock", props: { part: "float", panel: "spaces",
    height }, at: { x: (sidebarPx(layout()) ?? 76) + 6, y: Math.max(8, bounds?.y ?? 8) }, width: FLOAT, height });
}

/** A floating panel's head, as Adobe's: NAME, BUTTONS, and × closing it (OVERLAY); it drags the panel.
 * @param {string} name @param {string} overlay @param {any[]} buttons */
export function floatHead(t, name, overlay, buttons) {
  return h_flex().w_full().h(36).flex_none().pl(16).pr(6).gap(GAP).items_center()
    .child(listName(t, name).flex_1()).children(buttons)
    .child(iconButton(t, "float-close", "x", "Close", () => closeOverlay(overlay)));
}

/** A panel floating beside a rail (OVERLAY, a window HEIGHT high, else its window's height): its head, then BODY, which
 * keeps its presses, then FOOT (a grip), if any. @param {string} name @param {string} overlay
 * @param {number | undefined} height @param {any[]} buttons @param {any} body @param {any} [foot] */
export function floatPanel(t, name, overlay, height, buttons, body, foot = null) {
  return (height ? v_flex().w_full().h(height) : v_flex().size_full()).rounded(10).bg(t.surface)    // a card
    .text_size(13)
    .child(floatHead(t, name, overlay, buttons))
    .child(v_flex().flex_1().min_h(0).on_mouse_down("left", (_e, cx) => cx.stop_propagation()).child(body))
    .when(Boolean(foot), (e) => e.child(foot));
}

/** The folded sidebar as Adobe's collapsed dock: Spaces at the most urgent of SPACES' states, floating beside it by a
 * press; the app's footer at its foot, Settings with no dot (the status bar says an update is ready).
 * @param {(string | null)[]} spaces */
export function dock(t, spaces) {
  const state = urgent(spaces);
  return v_flex().id("dock").size_full().min_h(0).items_center()
    .child(v_flex().flex_1().pt(8).gap(12).items_center()
      .child(dockButton(t, state ? t[state] : null)))
    .child(v_flex().w_full().flex_none().items_center().gap(GAP).pt(4).pb(8).border_t(1).border_color(t.border)
      .child(iconButton(t, "dock-settings", "settings", "Settings", () => command("app.settings")))
      .child(iconButton(t, "dock-machine", "plus", "Add machine", () => command("mod.open", { name: "machine-add" }),
        { color: t.dim })));
}

/** Spaces on the folded rail, as Adobe's collapsed dock shows a panel: its icon on a square, DOT its most urgent
 * state's color, its name under it; a press floats it beside the rail, as high as its rows.
 * @param {string | null} dot */
function dockButton(t, dot) {
  return v_flex().id("dock-spaces").flex_none().items_center().gap(4).cursor_pointer()
    .on_mouse_down("left", (e, cx) => {
      cx.stop_propagation();
      openFloat(e.bounds, floatHeight(floatSpaces().length));
    })
    .child(iconTab(t, "dock-spaces-tab", icon("layers", 15), { dot, tip: "Spaces", act: () => {} }))
    .child(div().text_size(10).text_color(t.dim).child("Spaces"));
}

/** The Spaces panel floating beside the folded rail (OVERLAY, HEIGHT high): each of LIST by its avatar (COLORS), its
 * name, its wait (SINCE) and its most urgent agent's state, the shown one selected; a click shows it. A home with
 * nothing open: as the list's stand-in (spaces.js). @param {string} overlay @param {number} height */
export function spacesFloat(t, overlay, height, list = floatSpaces(), colors = spaceColorsKept(),
  since = waitsBySpace(), now = Date.now()) {
  return floatPanel(t, "Spaces", overlay, height,
    [iconButton(t, "float-new-space", "plus", "New space", () => command("space.new", {}))],
    v_flex().id("float-spaces").size_full().overflow_y_scrollbar().px(8).pb(8).gap(2)
      .children(list.map((space) => h_flex().id(`float-space-${space.id}`).h(28).flex_none().px(8).gap(8)
        .items_center().rounded(6).cursor_pointer().when(space.active, (e) => e.bg(t.selected))
        .hover((s) => s.bg(t.hover)).on_click(() => (space.empty ? openHome(space.machine ?? null)
          : command("space.select", { id: space.id })))
        .when(!space.empty, (e) => e.child(h_flex().size(18).flex_none().rounded(4)
          .bg(avatarFill(colors[space.id] ?? "ansi6", t)).items_center().justify_center()
          .text_size(11).font_bold().text_color("#ffffff").child([...space.name][0]?.toUpperCase() ?? "?")))
        .when(Boolean(space.empty), (e) => e.child(h_flex().size(18).flex_none().rounded(4).border(1)
          .border_color(t.border).items_center().justify_center().text_size(11).font_bold().text_color(t.dim)
          .child(HOME_NAME)).tooltip("Nothing open in the home folder. Click to open a terminal there."))
        .child(div().flex_1().min_w(0).truncate()
          .text_color(space.active ? t.foreground : space.empty ? t.dim : t.muted)
          .when(space.active, (e) => e.font_bold()).child(spaceLabel(space.name)))
        .when(Boolean(since[space.id]), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
          .child(waited(now - since[space.id]))))
        .child(stateMark(t, space.status)))));
}
