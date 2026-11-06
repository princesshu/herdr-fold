// @ts-check
// The mod's menus: a popup over what is below, right-aligned under the button pressed or at the pointer; a choice comes
// back to the copy that opened it as herdr-fold.menu-TOKEN-N, which runs it.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { closeOverlay, openOverlay, run as command } from "herdr";
import { checked } from "./parts.js";

const MENU = 180;                  // a menu's width: its longest choice, Commit & Sync, with its check
const ROW = 28;

/** A choice: what it does (ACT, run where the menu was opened; or URL, opened), a check when ON can be set, its
 * label's COLOR, or OFF: shown, not chosen. @typedef {{ label: string, act?: (cx: any) => void, url?: string,
 * on?: boolean, color?: string, off?: boolean }} Item */

export class Menus {
  constructor() {
    /** @type {string | null} the menu open now, the one a choice may answer */
    this.token = null;
    /** @type {((cx: any) => void)[]} */
    this.acts = [];
  }

  /** ITEMS opened as a menu under BOUNDS (the pressed button's), else at the pointer. @param {Item[]} items
   * @param {any} [bounds] */
  open(items, bounds) {
    const token = (this.token = Math.random().toString(36).slice(2, 10));
    this.acts = items.map((item) => item.act ?? (() => {}));
    const rows = items.map(({ label, url, on, color, off }, n) => ({ label, url, on, color, off,
      command: `menu-${token}-${n}` }));
    openOverlay({ mod: "herdr-fold", kind: "popup", props: { part: "menu", items: rows }, width: MENU,
      height: items.length * (ROW + 2) + 8,
      ...(bounds ? { at: { x: Math.max(8, bounds.x + bounds.width - MENU), y: bounds.y + bounds.height + 4 } } : {}) });
  }

  /** Whether ASKED (nextCommand's) is a choice of this copy's open menu; it runs then. @param {string} asked */
  answer(asked, cx) {
    const chosen = /^menu-(\w+)-(\d+)$/.exec(asked);
    if (!chosen || chosen[1] !== this.token) return false;
    this.token = null;
    this.acts[Number(chosen[2])]?.(cx);
    cx.notify();
    return true;
  }
}

/** The menu (OVERLAY, its popup): ITEMS a row each, a check before the ones on when any can be; a choice sends its
 * command back, or opens its URL, and closes it. @param {string} overlay
 * @param {(Item & { command?: string })[]} items */
export function menuPopup(t, overlay, items) {
  const checks = items.some((item) => item.on !== undefined);
  return v_flex().size_full().p(4).gap(2).text_size(12).text_color(t.foreground)
    .children(items.map((item, i) => h_flex().id(`menu-${i}`).h(ROW).flex_none().px(10).gap(8).items_center()
      .rounded(6).when(Boolean(item.off), (e) => e.text_color(t.dim))
      .when(!item.off, (e) => e.cursor_pointer().hover((s) => s.bg(t.hover)).on_click((_e, cx) => {
        if (item.url) cx.open_url(item.url);
        else command(`herdr-fold.${item.command}`);
        closeOverlay(overlay);
      }))
      .when(checks, (e) => e.child(checked(t, Boolean(item.on))))
      .child(div().truncate().when(Boolean(item.color), (e) => e.text_color(item.color)).child(item.label))));
}
