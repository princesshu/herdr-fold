// @ts-check
// The sidebar folded to a rail, as Adobe's collapsed panel dock: Spaces as an icon, floating beside it when pressed,
// its toggle in its head over it. Open: its head (Herdr's mark and name, Go to space or tab, the toggle), Spaces, foot.
import { div, image } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { closeOverlay, layout, openOverlay, setShared, shared, spaces, window as appWindow, run as command }
  from "herdr";
import { avatarFill, find, FLOAT_GRIP, floatHeight, floating, floatTop, floatX, HOME_NAME, pressCloses, railed,
  sidebarRest,
  sidebarPx, sidebarToggle, spaceColor, spaceLabel, toggleRoom, urgent, waited } from "./logic.js";
import { menusOpen } from "./menus.js";
import { BUTTON, GAP, icon, iconButton, iconTab, listName, stateMark } from "./parts.js";
import { newSpace } from "./chat.js";
import { openSettings, settingsOpen } from "./settings.js";
import { FOLDED, floatSpaces, openHome, spaceColorsKept, waitsBySpace } from "./spaces.js";
import { NETWORKS_FOLDED } from "./logic.js";
import { openMachines } from "./panel.js";

const FLOAT = 300;                 // Spaces floating beside the rail: as wide as the open sidebar
const EDGE = 8;                    // px a float keeps from the window's foot
const HERDR_MARK = "frame/welcome/herdr.png";    // Herdr's mark, the app's own picture (its sidebar head's)
// shared, while one floats ({ panel, overlay }): Spaces beside the folded sidebar, a view beside the right rail
export const DOCK_FLOAT = "herdr-fold.dock-float", RAIL_FLOAT = "herdr-fold.rail-float";

/** Whether the sidebar is a rail now: folded by its toggle, or dragged as narrow. */
const folded = () => railed(layout());

/** The width the open sidebar had, which its toggle and a widening drag open it to again. */
const kept = () => /** @type {number | undefined} */ (shared("sidebar.width") ?? undefined);

/** The tab bar's end over the dock (✦, More and » / «), from the window's edge: the right float's own controls. */
const barEnd = () => toggleRoom(layout(), BUTTON) + 3 * BUTTON + 2 * GAP;

/** Whether a menu or a window of the mod is up: a press there is a float's own, never one beside it. */
const held = () => menusOpen().length > 0 || settingsOpen();

/** The sidebar's toggle and Cmd+B: folded to its rail, or opened again to the width it had, as the app's own toggle
 * does it; hidden (by the app's own command), shown open. */
export function toggleSidebar() {
  const root = layout(), now = railed(root), hidden = Boolean(find(root, "sidebar")?.hidden);
  if (!now && !hidden) setShared("sidebar.width", sidebarPx(root));
  setShared("sidebar.collapsed", !now && !hidden);       // what mods made before the rail went by width read
  for (const [name, args] of sidebarToggle(root, appWindow()?.platform === "macos", kept())) command(name, args);
}

/** The sidebar let go of after a drag, rested FROM px wide last (the tab bar's restFollow): a rail widened past UNFOLD
 * opened as its toggle opens it, else narrower than a rail starts its rail; open, its width kept for the toggle.
 * @param {number | null} from */
export function restSide(from) {
  const { to, open, commands } = sidebarRest(layout(), from, kept(), appWindow()?.platform === "macos");
  for (const [name, args] of commands) command(name, args);
  if (commands.length) setShared("sidebar.collapsed", !open);
  else if (open && to !== shared("sidebar.width")) setShared("sidebar.width", to);
  return to;
}

/** The float the side's shared value KEY names closed and forgotten, as its lit icon closes it. @param {string} key */
export function shutFloat(key) {
  const open = floating(shared(key));
  if (open) closeOverlay(open.overlay);
  if (shared(key)) setShared(key, null);
}

/** Float window OVERLAY gone, however it went (×, Esc, its icon, a layout switch): its icon no longer lit.
 * @param {string} overlay */
export function forgetFloat(overlay) {
  for (const key of [DOCK_FLOAT, RAIL_FLOAT]) if (floating(shared(key))?.overlay === overlay) setShared(key, null);
}

/** The floats a last run left marked are gone (the tab bar's copy says so once, as it starts). */
export function forgetFloats() {
  for (const key of [DOCK_FLOAT, RAIL_FLOAT]) if (shared(key)) setShared(key, null);
}

/** The sidebar's head on the tab row's line: open, Herdr's mark and name in the Spaces rows' columns (over their
 * avatars and names), Go to space or tab and the toggle at its end, over Spaces' +; folded, the toggle alone, centred
 * over the rail, as the right's « over its own (OPEN: the sidebar's own state, unless given). */
export function sidebarHead(t, open = !folded()) {
  return h_flex().size_full().gap(GAP).items_center().bg(t.chrome).text_size(13)
    .when(open, (e) => e.pl(16).pr(8)
      .child(h_flex().flex_1().min_w(0).gap(8).items_center()
        .child(image(HERDR_MARK).size(18).flex_none().rounded(4))
        .child(div().min_w(0).truncate().font_semibold().text_color(t.foreground).child("Herdr")))
      .child(iconButton(t, "sidebar-search", "search", "Go to space or tab",
        () => command("mod.open", { name: "picker" }), { size: 15 })))
    .when(!open, (e) => e.justify_center())
    .child(iconButton(t, "sidebar-toggle", "panel-left", open ? "Collapse to icons" : "Expand panels", toggleSidebar,
      { size: 15 }));
}

/** Spaces floating beside the folded rail every time, level with the right rail's floats, as Adobe's collapsed panels
 * open, one before closed first: as tall as kept, else as its SHOWN rows fit, the window's room under it at most (its
 * grip sizes it); dragged by its head, it stays where dropped until closed; marked, so its icon is lit. */
function openFloat(/** @type {number} */ shown) {
  const root = layout(), room = window.viewport_size(), y = floatTop(root), most = room.height - y - EDGE;
  const fit = floatHeight(shown, most - FLOAT_GRIP) + FLOAT_GRIP;
  shutFloat(DOCK_FLOAT);
  setShared(DOCK_FLOAT, { panel: "spaces", overlay: openOverlay({ mod: "herdr-fold", kind: "window",
    props: { part: "float", panel: "spaces", fit, most }, at: { x: floatX("spaces", root, room.width, FLOAT), y },
    width: FLOAT }) });
}

/** A floating panel's head, as Adobe's: NAME, BUTTONS, and × closing it (OVERLAY); it drags the panel.
 * @param {string} name @param {string} overlay @param {any[]} buttons */
export function floatHead(t, name, overlay, buttons) {
  return h_flex().w_full().h(36).flex_none().pl(16).pr(6).gap(GAP).items_center()
    .child(listName(t, name).flex_1()).children(buttons)
    .child(iconButton(t, "float-close", "x", "Close", () => closeOverlay(overlay)));
}

/** A panel floating beside a rail (OVERLAY, HEIGHT high, else its window's): its head, BODY, FOOT (a grip); FOCUS takes
 * the keys as it opens, a press beside it closes it (pressCloses: PANEL's; never while OWNS says its view has a list
 * up). @param {string} name @param {string} overlay @param {any[]} buttons @param {any} [how] */
export function floatPanel(t, name, overlay, height, buttons, body, { foot = null, focus = null, panel = null,
  owns = null } = {}) {
  return (height ? v_flex().w_full().h(height) : v_flex().size_full()).rounded(10).bg(t.surface)    // a card
    .text_size(13)
    .when(Boolean(focus), (e) => e.track_focus(focus))
    .when(Boolean(panel && overlay), (e) => e.on_mouse_down_out((e) => {
      if (pressCloses(panel, e.position, layout(), window.viewport_size().width, barEnd(), held() || owns?.())) {
        closeOverlay(overlay);
      }
    }))
    .on_key_down((e, cx) => {                  // Esc with the float's keys: closed
      if (e.key !== "escape") return;
      cx.stop_propagation();
      closeOverlay(overlay);
    })
    .child(floatHead(t, name, overlay, buttons))
    .child(v_flex().flex_1().min_h(0).on_mouse_down("left", (_e, cx) => cx.stop_propagation())
      // Esc in its view (a field, a name, a list): the view's first, then the keys back to the float, whose next Esc
      // closes it
      .on_key_down((e, cx) => {
        if (e.key !== "escape" || !focus) return;
        cx.stop_propagation();
        focus.focus();
      })
      .child(body))
    .when(Boolean(foot), (e) => e.child(foot));
}

/** The app's Add machine: the foot's, and Ctrl+B, Shift+M's, as the TUI's. */
export const addMachine = () => command("mod.open", { name: "machine-add" });

/** The sidebar's foot, open (sidebarFoot) or on its rail (dock), each [id, icon, name, act]: Settings, the one
 * Settings (herdr-fold's, the app's own in it), with no dot (the status bar says an update is ready), then Add
 * machine, dim. */
const FOOT = /** @type {[string, string, string, () => void][]} */ ([["settings", "settings", "Settings",
  () => openSettings()], ["machine", "plus", "Add machine…", () => addMachine()]]);

/** The open sidebar's foot (the layout's sidebar-footer), as the app's own footer drew it: FOOT's rows 28 high, an
 * icon 14 and its name 8 apart, on the side's level under a hairline. */
export const sidebarFoot = (t) => v_flex().size_full().bg(t.chrome).border_t(1).border_color(t.border).px(8).pt(4)
  .pb(8).text_size(13).children(FOOT.map(([id, glyph, name, act], n) => h_flex().id(`foot-${id}`).h(28).px(8).gap(8)
    .items_center().rounded(8).text_color(n ? t.dim : t.muted).cursor_pointer()
    .hover((s) => s.bg(t.hover).text_color(t.foreground)).on_click(() => act()).child(icon(glyph, 14)).child(name)));

/** The folded sidebar as Adobe's collapsed dock: Spaces at the most urgent of SPACES' states, floating beside it by a
 * press, LIT while it floats; FOOT at its foot, its icons alone. @param {(string | null)[]} spaces */
export function dock(t, spaces, lit = false) {
  const state = urgent(spaces);
  return v_flex().id("dock").size_full().min_h(0).items_center()
    .child(v_flex().flex_1().pt(16).gap(12).items_center()     // its icon level with the right rail's
      .child(dockButton(t, state ? t[state] : null, lit)))
    .child(v_flex().w_full().flex_none().items_center().gap(GAP).pt(4).pb(8).border_t(1).border_color(t.border)
      .children(FOOT.map(([id, glyph, name, act], n) => iconButton(t, `dock-${id}`, glyph, name,
        () => (shutFloat(DOCK_FLOAT), act()), n ? { color: t.dim } : {}))));
}

/** The folded sidebar as the spaces are now, Spaces lit while it floats. */
export const liveDock = (t) => dock(t, spaces().map((space) => space.status), Boolean(floating(shared(DOCK_FLOAT))));

/** Spaces on the folded rail, as Adobe's collapsed dock shows a panel: its icon on a square, DOT its most urgent
 * state's color, its name under it; a press floats it beside the rail, LIT then (the selected square, its icon and name
 * in the accent, as the right rail's), and closes it. @param {string | null} dot @param {boolean} lit */
function dockButton(t, dot, lit) {
  return v_flex().id("dock-spaces").flex_none().items_center().gap(4).cursor_pointer()
    .on_mouse_down("left", (_e, cx) => {
      cx.stop_propagation();
      lit ? shutFloat(DOCK_FLOAT) : openFloat(floatSpaces().length);
    })
    .child(iconTab(t, "dock-spaces-tab", icon("layers", 15).when(lit, (e) => e.text_color(t.accent)),
      { dot, active: lit, tip: "Spaces", act: () => {} }))
    .child(div().text_size(10).text_color(lit ? t.accent : t.dim).child("Spaces"));
}

/** The Spaces float's head's buttons, the open list's: the Machines tab, a new space. */
export const spacesButtons = (t) => [iconButton(t, "float-machines", "waypoints", "Machines", () => openMachines()),
  iconButton(t, "float-new-space", "plus", "New space", () => void newSpace().catch(() => {}))];

/** The Machines tab's Show in Spaces: machine NAME's head unfolded in Spaces, its NETWORK's head too (the one it
 * stands under), the sidebar opened from its rail. @param {string} name @param {string | null} network */
export function showInSpaces(name, network) {
  const machines = new Set(/** @type {any[]} */ (shared(FOLDED) ?? [])), nets = new Set(/** @type {any[]} */ (
    shared(NETWORKS_FOLDED) ?? []));
  if (machines.delete(name)) setShared(FOLDED, [...machines]);
  if (network && nets.delete(network)) setShared(NETWORKS_FOLDED, [...nets]);
  if (folded()) toggleSidebar();
}

/** The Spaces float's list: each of LIST by its avatar (COLORS), name, wait (SINCE), its most urgent agent's state, the
 * shown one selected, a click showing it; a home with nothing open as the list's stand-in (spaces.js). */
export function spacesBody(t, list = floatSpaces(), colors = spaceColorsKept(), since = waitsBySpace(),
  now = Date.now()) {
  return v_flex().id("float-spaces").size_full().overflow_y_scrollbar().px(8).pb(8).gap(2)
    .children(list.map((space) => h_flex().id(`float-space-${space.id}`).h(28).flex_none().px(8).gap(8)
      .items_center().rounded(6).cursor_pointer().when(space.active, (e) => e.bg(t.selected))
      .hover((s) => s.bg(t.hover)).on_click(() => (space.empty ? openHome(space.machine ?? null)
        : command("space.select", { id: space.id })))
      .when(!space.empty, (e) => e.child(h_flex().size(18).flex_none().rounded(4)
        .bg(avatarFill(spaceColor(space, colors), t)).items_center().justify_center()
        .text_size(11).font_bold().text_color("#ffffff").child([...space.name][0]?.toUpperCase() ?? "?")))
      .when(Boolean(space.empty), (e) => e.child(h_flex().size(18).flex_none().rounded(4).border(1)
        .border_color(t.border).items_center().justify_center().text_size(11).font_bold().text_color(t.dim)
        .child(HOME_NAME)).tooltip("Nothing open in the home folder. Click to open a terminal there."))
      .child(div().flex_1().min_w(0).truncate()
        .text_color(space.active ? t.foreground : space.empty ? t.dim : t.muted)
        .when(space.active, (e) => e.font_bold()).child(spaceLabel(space.name)))
      .when(Boolean(since[space.id]), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
        .child(waited(now - since[space.id]))))
      .child(stateMark(t, space.status))));
}
