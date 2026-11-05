// @ts-check
// The mod's dropdown menus, as the app's own open: a popup under the button pressed, its right edge with the button's,
// over what is below it, closed by a press beside it; a choice runs the panel's command (herdr-fold.<name>).
import { h_flex, v_flex } from "gpui-base";
import { closeOverlay, openOverlay, run as command } from "herdr";
import { checked } from "./parts.js";

const MENU = 180;                  // a menu's width: its longest choice, Commit & Sync, with its check
const ROW = 28;

/** @typedef {{ label: string, command?: string, url?: string, on?: boolean }} Item */

/** ITEMS opened as a menu under BOUNDS (the pressed button's). @param {Item[]} items @param {any} bounds */
export function openMenu(items, bounds) {
  if (!bounds) return;
  openOverlay({ mod: "herdr-fold", kind: "popup", props: { part: "menu", items },
    at: { x: Math.max(8, bounds.x + bounds.width - MENU), y: bounds.y + bounds.height + 4 }, width: MENU,
    height: items.length * (ROW + 2) + 8 });
}

/** The menu (OVERLAY, its popup): ITEMS a row each, a check before the ones on when any can be; a choice runs its
 * command, or opens its URL, and closes it. @param {string} overlay @param {Item[]} items */
export function menuPopup(t, overlay, items) {
  const checks = items.some((item) => "on" in item);
  return v_flex().size_full().p(4).gap(2).text_size(12).text_color(t.foreground)
    .children(items.map((item, i) => h_flex().id(`menu-${i}`).h(ROW).flex_none().px(10).gap(8).items_center()
      .rounded(6).cursor_pointer().hover((s) => s.bg(t.hover)).on_click((_e, cx) => {
        if (item.url) cx.open_url(item.url);
        else if (item.command) command(`herdr-fold.${item.command}`);
        closeOverlay(overlay);
      })
      .when(checks, (e) => e.child(checked(t, Boolean(item.on)))).child(item.label)));
}
