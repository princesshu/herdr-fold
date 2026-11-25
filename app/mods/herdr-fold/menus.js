// @ts-check
// The mod's menus, popups under the button pressed or at the pointer, a choice run back in the copy that opened it
// (herdr-fold.menu-TOKEN-N); and the panels' list form, the chat bar's panels' and the command palette's.
import { div, image, svg } from "gpui-kit";
import { h_flex, InputState, v_flex } from "gpui-base";
import { closeOverlay, openOverlay, setShared, shared, run as command } from "herdr";
import { keyMenuBounds, menuHeight, menuPlace } from "./logic.js";
import { toneInk } from "./layers.js";
import { checked, field, icon, listName, scopeTag } from "./parts.js";
import { RHYTHM as R } from "./timeline.js";

const MENU = 180;                  // a menu's width: its longest choice, Commit & Sync, with its check
const ROW = 28;
const MENUS = "herdr-fold.menus-open";     // shared: the mod's menus up now, by their popups' ids (a float keeps them)

/** The mod's menus up now (their popups' ids). @returns {string[]} */
export const menusOpen = () => {
  const open = shared(MENUS);
  return Array.isArray(open) ? open : [];
};

/** Menu OVERLAY gone, however it went (a choice, Esc, a press beside). @param {string} overlay */
export function menuGone(overlay) {
  if (menusOpen().includes(overlay)) setShared(MENUS, menusOpen().filter((id) => id !== overlay));
}

/** The menus a last run left marked are gone (the tab bar's copy says so once, as it starts). */
export const forgetMenus = () => void (menusOpen().length && setShared(MENUS, []));

/** @typedef {{ label: string, act?: (cx: any) => void, url?: string, on?: boolean, color?: string, off?: boolean,
 *   dim?: boolean, icon?: { path: string, tint: boolean, dim?: boolean }, note?: string, tone?: string,
 *   tip?: string }} Item */
// a choice (null among them: a rule): its ACT (run where the menu opened) or URL, a check when ON can be set, its
// COLOR, OFF shown not chosen (its TIP saying why, the mouse resting on it), DIM muted and still chosen; an ICON
// (picture or tinted glyph, DIM: muted) before it, a NOTE (in its TONE's color)
/** A menu's own filter: its field, what is typed in it, what it says when nothing matches. @typedef {{ input: any,
 * typed: string, none: string }} Find */

export class Menus {
  constructor() {
    /** @type {string | null} the menu open now, the one a choice may answer */
    this.token = null;
    /** @type {((cx: any) => void)[]} */
    this.acts = [];
  }

  /** @typedef {{ width?: number, find?: string, none?: string }} How WIDTH its longest choice's; FIND, a filter's words
   * on top (typed into at once), NONE what it says when nothing matches */
  /** ITEMS opened as a menu under BOUNDS (the pressed button's; above, where it does not fit), else at the pointer,
   * HEAD (what they act on, its NOTE at its right) above them. @param {(Item | null)[]} items @param {any} [bounds]
   * @param {{ label: string, note?: string }} [head] @param {How} [how] */
  open(items, bounds, head, { width = MENU, find = undefined, none = "No match" } = {}) {
    const token = (this.token = Math.random().toString(36).slice(2, 10));
    this.acts = items.map((item) => item?.act ?? (() => {}));
    const rows = items.map((item, n) => item && { label: item.label, url: item.url, on: item.on, color: item.color,
      off: item.off, dim: item.dim, icon: item.icon, note: item.note, tone: item.tone, tip: item.tip,
      command: `menu-${token}-${n}` });
    const height = menuHeight(items, head, Boolean(find));
    setShared(MENUS, [...menusOpen(), openOverlay({ mod: "herdr-fold", kind: "popup", props: { part: "menu",
      items: rows, head, find, none }, width, height,
    ...(bounds ? { at: menuPlace(bounds, height, window.viewport_size(), width) } : {}) })]);
  }

  /** ITEMS a key opens (Cmd+Shift+L's files, Cmd+K Cmd+T's themes) where the palette stands, at the window's top.
   * @param {(Item | null)[]} items @param {How} [how] */
  atTop(items, how = {}) {
    this.open(items, keyMenuBounds(window.viewport_size(), how.width ?? MENU), undefined, how);
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

/** The ITEMS a menu's filter shows for TYPED: those whose label holds it, no rule; all of them while nothing is.
 * @template T @param {(T & { label: string } | null)[]} items @param {string} typed */
export const filtered = (items, typed) => (typed ? items.filter((item) => item?.label.toLowerCase()
  .includes(typed.toLowerCase())) : items);

/** ITEM's choice made in the menu OVERLAY: its command sent back, or its URL opened; the menu closed.
 * @param {Item & { command?: string }} item @param {string} overlay */
function choose(item, overlay, cx) {
  if (item.url) cx.open_url(item.url);
  else command(`herdr-fold.${item.command}`);
  closeOverlay(overlay);
}

/** The menu (OVERLAY, its popup): FIND's filter (Enter its first choice, Esc closes), its HEAD, ITEMS a row each (null:
 * a rule; a check before the ones on when any can be): a choice sends its command back or opens its URL, and closes.
 * @param {string} overlay @param {any[]} items @param {any} [head] @param {any} [find] */
export function menuPopup(t, overlay, items, head, find = null) {
  const checks = items.some((item) => item?.on !== undefined), shown = filtered(items, find?.typed ?? "");
  return v_flex().size_full().p(4).gap(2).text_size(12).text_color(t.foreground)
    .on_key_down((e, cx) => {
      if (e.key !== "escape") return;
      cx.stop_propagation();
      closeOverlay(overlay);
    })
    .when(Boolean(find), (e) => e.child(field(t, "menu-find", find?.input).flex_none()))
    .when(Boolean(head), (e) => e.child(h_flex().h(ROW).flex_none().px(8).gap(8).items_center()
      .child(div().font_semibold().child(head?.label ?? "")).child(div().flex_1())
      .child(div().text_color(t.muted).child(head?.note ?? ""))))
    .when(Boolean(find) && !shown.some(Boolean), (e) => e.child(h_flex().h(ROW).flex_none().px(8).items_center()
      .text_color(t.dim).child(find?.none ?? "")))
    .children(shown.map((item) => !item ? rule(t) : h_flex().id(`menu-${items.indexOf(item)}`).h(ROW).flex_none()
      .px(8).gap(8).items_center().rounded(6).when(Boolean(item.off), (e) => e.text_color(t.dim))
      .when(Boolean(item.tip), (e) => e.tooltip(item.tip))
      .when(!item.off, (e) => e.cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => choose(item, overlay, cx)))
      .when(checks, (e) => e.child(checked(t, Boolean(item.on))))
      .when(Boolean(item.icon), (e) => e.child((item.icon?.tint
        ? svg(item.icon.path).size(14).flex_none().text_color(item.off ? t.dim : item.icon.dim ? t.muted
          : t.foreground)
        : image(String(item.icon?.path)).size(14).flex_none()).when(Boolean(item.dim), (e) => e.opacity(0.6))))
      .child(div().truncate().when(Boolean(item.color), (e) => e.text_color(item.color))
        .when(Boolean(item.dim), (e) => e.text_color(t.muted)).child(item.label))
      .when(Boolean(item.note), (e) => e.child(div().flex_1()).child(div().flex_none().text_size(11)
        .text_color(item.tone ? toneInk(t, item.tone, t.popover ?? t.raised) : t.dim).child(item.note ?? "")))));
}

/** The first choice FIND's filter shows in ITEMS, the one Enter picks; null for none. @param {Find} find
 * @param {((Item & { command?: string }) | null)[]} items */
export const firstChoice = (find, items) => filtered(items, find.typed).find((item) => item && !item.off) ?? null;

/** A filter for the menu OVERLAY of ITEMS, its words WORDS, saying NONE when nothing matches: what is typed shown at
 * once, Enter its first choice. @param {string} words @param {string} none
 * @param {((Item & { command?: string }) | null)[]} items @param {string} overlay @returns {Find} */
export function menuFind(words, none, items, overlay) {
  const find = { input: InputState.new({ placeholder: words }), typed: "", none };
  find.input.on("change", (_e, cx) => {
    find.typed = find.input.value().trim();
    cx.notify();
  });
  find.input.on("submit", (_e, cx) => {
    const first = firstChoice(find, items);
    if (first) choose(first, overlay, cx);
  });
  return find;
}

/** A rule between two parts of a menu (or the model chip's panel), as the TUI's ⋯ has them: 9 high, the line in its
 * middle. */
export const rule = (t) => div().h(9).flex_none().py(4).px(8).child(div().h(1).w_full().bg(t.border));

// the panels' list form: a row on a 16 line (its name, its line, its icon, its tag), 8 over and under it: 32, as a
// Modes row is 8 over and under its two lines; a list LISTED high at most (about ten rows), scrolled past it
export const LINE = 16;
export const LISTED = 384;
export const NAME_IN = R.inset + LINE + R.gap;     // px: a list row's name from its edge (12 in, its icon, a gap)

/** What draws a panel's list keeps: the row the keys are on (CURSOR), each row's place in the list (LISTPLACES), the
 * list's scroll (LISTSCROLL). @typedef {{ cursor: number | null, listPlaces: number[], listScroll: any }} Lister */

/** A panel's surface, WIDE px, as the chat bar's panels and the palette have it: the popover's, a hairline round it,
 * rounded 10, lifted; 13 in the text's color. @param {string} id @param {number} wide */
export const panelSurface = (t, id, wide) => v_flex().id(id).w(wide).rounded(10).border_1().border_color(t.border)
  .bg(t.popover ?? t.raised).shadow_lg().text_size(13).text_color(t.foreground);

/** Row N, every panel's one (.mrow, .mset, .prow): 8 over and under what it holds, 12 in, rounded 6; the keys' row
 * (LISTER's) on the hover fill, the pointer moving it (USABLE), the one in use (ON) on the accent's tint.
 * @param {Lister} lister @param {number | string} n @param {boolean} usable @param {boolean} [on] */
export function panelRow(t, lister, n, usable, on = false) {
  return h_flex().id(`panel-${n}`).flex_none().py(R.gap).px(R.inset).gap(R.gap).items_center().rounded(6)
    .when(on, (e) => e.bg(`${t.accent}24`)).when(!on && lister.cursor === n, (e) => e.bg(t.hover))
    .when(usable && typeof n === "number", (e) => e.on_mouse_move((_e, cx) => {
      if (lister.cursor === n) return;
      lister.cursor = /** @type {number} */ (n);
      cx.notify();
    }));
}

/** A list row's words on one LINE (center-chat.html's .nm, .ds, .src): its MARK (16, muted; null: none), its NAME,
 * its LINE muted after it, cut where long, its source's TAG at the end. @param {import("./icons.js").IconName | null}
 * mark @param {string} name @param {string} line @param {string | null} tag */
export function listWords(t, mark, name, line, tag) {
  return [...(mark ? [icon(mark, LINE).text_color(t.muted)] : []), h_flex().flex_1().min_w(0).gap(R.gap)
    .items_center().line_height(`${LINE}px`).child(div().flex_none().child(name))
    .when(Boolean(line), (e) => e.child(div().min_w(0).truncate().text_size(12).text_color(t.muted).child(line))),
  ...(tag ? [scopeTag(t, tag)] : [])];
}

/** A list's part named (center-chat.html's .pgroup), as the app's lists name theirs: 8 over it, 4 under.
 * @param {string} name */
export const groupHead = (t, name) => div().flex_none().px(R.inset).pt(R.gap).pb(R.pad).child(listName(t, name));

/** What a list's part says in its rows' place or after them (center-chat.html's .pmore): 12, muted (an ERROR in ansi1),
 * under the rows' names (FROM the list's edge). @param {string} text @param {boolean} [error] @param {number} [from] */
export const listNote = (t, text, error = false, from = NAME_IN) => div().flex_none().pl(from).pr(R.inset).pt(2)
  .pb(R.pad).text_size(12).text_color(error ? t.ansi1 : t.muted).child(text);

/** A panel's list (ID), ITEMS, its rows at PLACES in it (kept in LISTER for its keys): MOST high at most, scrolled past
 * it, the keys' row kept in view (listStep's). @param {Lister} lister @param {string} id @param {any[]} items
 * @param {number[]} places @param {number} [most] */
export function panelList(lister, id, items, places, most = LISTED) {
  lister.listPlaces = places;
  return v_flex().id(id).flex_none().max_h(most).overflow_y_scroll().gap(2)
    .when(Boolean(lister.listScroll), (e) => e.track_scroll(lister.listScroll)).children(items);
}

/** LISTER's keys' row scrolled into its list's view (a long list's), as ↑ ↓ moved it. @param {Lister} lister */
export function keepInView(lister) {
  const place = lister.listPlaces[lister.cursor ?? -1];
  if (place !== undefined) lister.listScroll?.scroll_to_item(place);
}
