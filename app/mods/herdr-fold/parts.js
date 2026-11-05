// @ts-check
// herdr-fold's own parts, which its views and its styleguide draw with: an icon, a button, a row's button, a chip.
import { div, image, svg } from "gpui-kit";
import { h_flex, Input } from "gpui-base";
import { ICONS } from "./icons.js";

export const GAP = 4;              // between two hover backgrounds side by side, everywhere: tabs, icon buttons

/** The mod's icon NAME (icons.js's, Lucide's), SIZE square, in the text's color.
 * @param {import("./icons.js").IconName} name @param {number} [size] */
export const icon = (name, size = 14) => svg(ICONS[name]).size(size).flex_none();

/** A file's icon (logic.js's fileIcon, a path), 16 square, in its own colors. @param {string} path */
export const fileMark = (path) => image(path).size(16).flex_none();

/** A button that is an icon (NAME), 26 square, saying TIP while the mouse rests on it; its press never drags what it
 * sits on (the window, a floating panel). @param {import("./icons.js").IconName} name @param {string} tip
 * @param {(cx: any) => void} act */
export const iconButton = (t, id, name, tip, act, { size = 14, color = t.muted } = {}) =>
  div().id(id).relative().size(26).flex_none().flex().items_center().justify_center().rounded(6).text_color(color)
    .cursor_pointer().tooltip(tip).hover((s) => s.bg(t.hover).text_color(t.foreground))
    .on_mouse_down("left", (_e, cx) => cx.stop_propagation()).on_click((_e, cx) => act(cx)).child(icon(name, size));

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

/** A square tab, as the panel heads its views and the folded sidebar shows its spaces and conversations: CONTENT,
 * SIZE square, the shown one (ACTIVE) on the selection, a state's DOT at its corner; the mouse on it names it (TIP).
 * @param {any} content @param {any} how */
export function iconTab(t, id, content, { size = 30, active = false, dot = null, tip, act }) {
  return div().id(id).relative().size(size).flex_none().flex().items_center().justify_center().rounded(6)
    .cursor_pointer().tooltip(tip).text_size(15).bg(active ? t.selected : t.raised)
    .text_color(active ? t.foreground : t.muted).hover((s) => s.bg(t.hover)).on_click((_e, cx) => act(cx))
    .child(content)
    .when(Boolean(dot), (e) => e.child(div().absolute().top(-3).right(-3).size(9).rounded_full()
      .bg(/** @type {string} */ (dot)).border_2().border_color(t.chrome ?? t.background)));
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
  return h_flex().id(id).h(32).pl(10).pr(more.length ? 4 : 10).gap(2).items_center().rounded(8).border_1()
    .border_color(t.border).cursor_text()
    .child(Input.new(input).flex_1().h_full().text_size(12).text_color(t.foreground)).children(more);
}

/** A row's own small button, saying what it does when the mouse rests on it. */
export function small(t, id, label, tip, enabled, onClick) {
  return div().id(id).h(20).min_w(20).px(5).flex().items_center().justify_center().rounded(5).text_size(12)
    .font_semibold().text_color(enabled ? t.foreground : t.dim).tooltip(tip)
    .when(enabled, (e) => e.cursor_pointer().hover((s) => s.bg(t.raised).text_color(t.foreground))
      .on_click((_e, cx) => {
        cx.stop_propagation();                          // the row's own click (its diff) stays out of it
        onClick(cx);
      }))
    .child(label);
}

export const END = 24;             // a row's last column: a section's count, its files' letters centered under it

/** A count on a chip, as the TUI sidebar's sections show theirs. */
export function chip(t, text) {
  return div().flex_none().px(6).rounded(5).text_size(11).font_semibold().bg(t.raised).text_color(t.foreground)
    .child(text);
}
