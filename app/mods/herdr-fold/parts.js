// @ts-check
// herdr-fold's own parts, which its views and its styleguide draw with: an icon, a button, a row's button, a chip, a
// choice of a few.
import { div, image, PathBuilder, svg } from "gpui-kit";
import { h_flex, HoverCard, Input } from "gpui-base";
import { ringArc } from "./agents.js";
import { ICONS } from "./icons.js";
import { LIST } from "./logic.js";

export const GAP = 4;              // between two hover backgrounds side by side, everywhere: tabs, icon buttons
// the scales every view keeps to, which the styleguide shows: padding and gaps on a 4 px grid, the type sizes, the
// corners (tests/test_app.py checks each value against them)
export const SPACE = [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64];
export const TEXT = [10, 11, 12, 13, 15, 20, 28];
export const RADII = [4, 6, 8, 10];

/** The mod's icon NAME (icons.js's, Lucide's), SIZE square, in the text's color.
 * @param {import("./icons.js").IconName} name @param {number} [size] */
export const icon = (name, size = 14) => svg(ICONS[name]).size(size).flex_none();

/** A key as a cap (KEY: 1, esc, ↩), its edge seen on a lit row too. @param {string} key */
export const keyCap = (t, key) => div().h(18).min_w(18).px(4).flex_none().flex().items_center().justify_center()
  .rounded(4).border(1).border_color(t.dim + "80").text_size(11).text_color(t.muted).child(key);

/** The context ring, 16 square: its track, and PERCENT of it from the top clockwise in COLOR, painted as GPUI paints
 * a path. @param {number} percent @param {string} color */
export function ring(t, percent, color) {
  const circle = () => PathBuilder.stroke(2).move_to(8, 2).arc_to(6, 6, 0, false, true, 8, 14)
    .arc_to(6, 6, 0, false, true, 8, 2);
  const arc = ringArc(percent);
  const share = arc === "whole" ? circle().build()
    : arc && PathBuilder.stroke(2).move_to(8, 2).arc_to(6, 6, 0, arc.large, true, arc.x, arc.y).build();
  const layer = (/** @type {any} */ path, /** @type {string} */ tone) => window.paint_path(path, tone).absolute()
    .top_0().left_0().size_full();
  return div().relative().size(16).flex_none().child(layer(circle().build(), t.raised))
    .when(Boolean(share), (e) => e.child(layer(share, color)));
}

/** A file's icon (logic.js's fileIcon, a path), 16 square, in its own colors. @param {string} path */
export const fileMark = (path) => image(path).size(16).flex_none();

export const BUTTON = 26;          // an icon button's square
export const INDENT = 6 + 14 + 6;  // a row's content under its section's name: the head's padding, chevron and gap

/** A button that is an icon (NAME), 26 square, saying TIP while the mouse rests on it (LEFT: to its left, as the
 * tab bar's end has them all, where the app's own tooltip picks its side itself); its press never drags what it sits
 * on. @param {import("./icons.js").IconName} name @param {string} tip @param {(cx: any) => void} act */
export const iconButton = (t, id, name, tip, act, { size = 14, color = t.muted, left = false } = {}) => {
  const button = div().id(id).relative().size(BUTTON).flex_none().flex().items_center().justify_center().rounded(6)
    .text_color(color).cursor_pointer().when(!left, (e) => e.tooltip(tip))
    .hover((s) => s.bg(t.hover).text_color(t.foreground))
    .on_mouse_down("left", (_e, cx) => cx.stop_propagation()).on_click((_e, cx) => act(cx)).child(icon(name, size));
  return left ? HoverCard.new(`${id}-tip`).anchor("top_right").open_delay(500).close_delay(0).trigger(button)
    .content(div().mt(4).px(8).py(2).rounded(6).border_1().border_color(t.border).bg(t.popover ?? t.raised)
      .text_size(12).text_color(t.foreground).child(tip)) : button;
};

/** A list's or a floating panel's NAME, as the app's lists: 11, medium, dim. @param {string} name */
export const listName = (t, name) => div().text_size(11).font_medium().text_color(t.dim).child(name);

/** A sidebar list's head, Spaces' and Conversations' alike: its NAME and its BUTTONS at the end.
 * @param {string} name @param {...any} buttons */
export const listHead = (t, name, ...buttons) => h_flex().h(LIST.head).flex_none().pl(16).pr(8).items_center()
  .justify_between().child(listName(t, name)).children(buttons);

/** A menu choice's mark: a check while it is ON, else its room. @param {boolean} on */
export const checked = (t, on) => div().size(14).flex_none().text_color(t.accent)
  .when(on, (e) => e.child(icon("check")));

/** A button, its words bold as the TUI's: SOLID in the accent, as the TUI's Commit and its arrow, even while it
 * cannot be pressed; the others faint then. */
export function button(t, id, label, enabled, solid, onClick) {
  return div().id(id).h(32).px(12).flex().items_center().rounded(8).text_size(12).font_bold()
    .bg(solid ? t.solid : t.raised).text_color(solid ? t.solid_foreground : enabled ? t.foreground : t.dim)
    .when(enabled, (e) => e.cursor_pointer().on_click((_e, cx) => onClick(cx))).child(label);
}

export const SLIDE = { duration: 180, easing: "ease-out" };   // a section folding or opening, drawn by the app itself

/** COUNT in a round badge, as VS Code's on its Source Control. @param {number} count */
export const badge = (t, count) => div().h(16).min_w(16).px(4).flex().items_center().justify_center().rounded_full()
  .bg(t.accent).text_color(t.accent_foreground ?? t.background).text_size(10).font_bold().child(String(count));

/** A square tab, as the panel heads its views and a folded side shows its panels: CONTENT, SIZE square, the shown one
 * (ACTIVE) on the selection, a state's DOT or a COUNT's badge at its corner; the mouse on it names it (TIP).
 * @param {any} content @param {any} how */
export function iconTab(t, id, content, { size = 30, active = false, dot = null, count = 0, tip, act }) {
  return div().id(id).relative().size(size).flex_none().flex().items_center().justify_center().rounded(6)
    .cursor_pointer().tooltip(tip).text_size(15).bg(active ? t.selected : t.raised)
    .text_color(active ? t.foreground : t.muted).hover((s) => s.bg(t.hover)).on_click((_e, cx) => act(cx))
    .child(content)
    .when(Boolean(dot), (e) => e.child(div().absolute().top(-3).right(-3).size(9).rounded_full()
      .bg(/** @type {string} */ (dot)).border_2().border_color(t.chrome ?? t.background)))
    .when(count > 0, (e) => e.child(badge(t, count).absolute().top(-6).right(-8)));
}

/** A state's mark, as herdr marks an agent's: a disc in its color (working, blocked, done), a ring when idle, a faint
 * dot when closed or none (STATE empty). @param {string | null | undefined} state */
export function stateMark(t, state) {
  const color = state ? t[state] ?? t.dim : t.dim;
  const mark = state === "idle" ? div().size(7).rounded_full().border_1().border_color(color)
    : div().size(state ? 7 : 5).rounded_full().bg(color);
  return div().w(10).flex_none().flex().items_center().justify_center().child(mark);
}

/** A text field, as each of the mod's: bordered, no fill of its own, 32 high; INPUT, then MORE (switches) inside it.
 * @param {any} input @param {...any} more */
export function field(t, id, input, ...more) {
  return h_flex().id(id).h(32).pl(12).pr(more.length ? 4 : 12).gap(2).items_center().rounded(8).border_1()
    .border_color(t.border).cursor_text()
    .child(Input.new(input).flex_1().h_full().text_size(12).text_color(t.foreground)).children(more);
}

/** A row's own small button, saying what it does when the mouse rests on it. */
export function small(t, id, label, tip, enabled, onClick) {
  return div().id(id).h(20).min_w(20).px(6).flex().items_center().justify_center().rounded(4).text_size(12)
    .font_semibold().text_color(enabled ? t.foreground : t.dim).tooltip(tip)
    .when(enabled, (e) => e.cursor_pointer().hover((s) => s.bg(t.raised).text_color(t.foreground))
      .on_click((_e, cx) => {
        cx.stop_propagation();                          // the row's own click (its diff) stays out of it
        onClick(cx);
      }))
    .child(label);
}

export const END = 24;             // a row's last column: a section's count, its files' letters centered under it

/** A choice of a few, as GitHub's Open and Closed: LIST's [value, label] side by side, the CHOSEN one filled; a click
 * on another gives PICK its value. @param {[string, string][]} list @param {(value: string, cx: any) => void} pick */
export function choices(t, id, list, chosen, pick) {
  return h_flex().flex_none().gap(6).children(list.map(([value, label]) => div().id(`${id}-${value}`).h(24).px(8)
    .flex().items_center().rounded(6).text_size(12).cursor_pointer()
    .when(value === chosen, (e) => e.bg(t.solid).text_color(t.solid_foreground).font_bold())
    .when(value !== chosen, (e) => e.text_color(t.muted).hover((s) => s.bg(t.hover))
      .on_click((_e, cx) => pick(value, cx)))
    .child(label)));
}

/** A count on a chip, as the TUI sidebar's sections show theirs. */
export function chip(t, text) {
  return div().flex_none().px(6).rounded(4).text_size(11).font_semibold().bg(t.raised).text_color(t.foreground)
    .child(text);
}
