// @ts-check
// herdr-fold's own parts, which its views and its styleguide draw with: an icon, a button, a row's button, a chip.
import { div } from "gpui-kit";

/** A mark from icons.js, in FONT (a Nerd Font) when there is one. @param {string | null} font @param {string} mark */
export function glyph(font, mark) {
  return div().flex_none().flex().items_center().justify_center().when(Boolean(font), (e) => e.font_family(font))
    .child(mark);
}

/** A button, its words bold as the TUI's: SOLID in the accent, as the TUI's Commit and its arrow, even while it
 * cannot be pressed; the others faint then. */
export function button(t, id, label, enabled, solid, onClick) {
  return div().id(id).h(32).px(12).flex().items_center().rounded(8).text_size(12).font_bold()
    .bg(solid ? t.solid : t.raised).text_color(solid ? t.solid_foreground : enabled ? t.foreground : t.dim)
    .when(enabled, (e) => e.cursor_pointer().on_click((_e, cx) => onClick(cx))).child(label);
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

/** A count on a chip, as the TUI sidebar's sections show theirs. */
export function chip(t, text) {
  return div().flex_none().px(6).rounded(5).text_size(11).font_semibold().bg(t.raised).text_color(t.foreground)
    .child(text);
}
