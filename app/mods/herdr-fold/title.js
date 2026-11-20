// @ts-check
// The window's own title row (commands.html's B): the traffic lights or the window's buttons, at its centre the command
// field; a press opens herdr-fold's command palette onto it, as Nyitva draws it (docs/styleguide.md).
import { div } from "gpui-kit";
import { h_flex, Input, InputState, ScrollHandle, v_flex } from "gpui-base";
import { closeOverlay, commands, keys, layout, layouts, openOverlay, settings, setShared, shared, spaces,
  window as appWindow, run as command } from "herdr";
import { ADAPTERS, AGENTS_OPEN, agentsOpen, newAgent, panelStep, RECENT_AGENTS, slashMenu } from "./agents.js";
import { entryKey, fieldWidth, hovering, keyNames, paletteEntries, paletteKey, palettePlace, titleSide, spaceLabel }
  from "./logic.js";
import { groupHead, keepInView, LINE, LISTED, listNote, listWords, panelList, panelRow, panelSurface }
  from "./menus.js";
import { tabsState } from "./panel.js";
import { BUTTON, GAP, icon, iconButton, keyCap, scopeTag } from "./parts.js";
import { RHYTHM as R } from "./timeline.js";

const EDGE = 8;                    // px: the window's own buttons in from the row's end
const FIELD_HIGH = 25;             // px: the field, 5 under the row's top and 5 over its hairline, as drawn
/** The room the window's own buttons keep at the row's end, the field's gap to them with it (and as much at its
 * start, so the field stays on the window's centre). */
export const WINDOW_BUTTONS = 3 * BUTTON + 2 * GAP + 2 * EDGE;

// the palette (Nyitva): 600 wide on the window's centre from its top, its field 4 inside its edge, so 5 down where
// the title row's is; under a hairline the panels' list, LISTED high at most; room round it for its shadow
export const PALETTE_WIDE = 600;
const PALETTE_HEAD = 1 + R.pad + FIELD_HIGH + R.pad + 1;      // px: its edge, its field 4 inside, the hairline
const PALETTE_FOOT = 2 * R.pad + 1;                          // px: the list's room over and under it, its edge
const SHADE = 24;                  // px: the popup's room round the palette for its shadow, a press there beside it
const OPEN = "herdr-fold.palette-open";   // shared: the palette's popup while it is open, the field handed over
/** @type {{ width: number, height: number } | null} the window's room, as the title row last saw it */
let room = null;

/** @typedef {{ mac: boolean, name: string | null, key: string | null, field: number, buttons: { maximized: boolean }
 * | null, open?: boolean }} Title ⌘ or the search (MAC), the space's NAME, the palette's KEY, the FIELD's width (0: its
 * mark alone), the window's own BUTTONS where the app draws none, the palette OPEN (the field handed over to it) */

export class TitleView {
  constructor() {
    /** @type {number | null} the row's width, as last measured */
    this.wide = null;
    /** @type {string | null} the field while the pointer is on it (hovering's): its mark lit with its words */
    this.hovered = null;
    if (shared(OPEN)) setShared(OPEN, null);        // a palette the app's last run left open is gone
  }

  /** The row as the window, the shown space, the keys and its width have it now. */
  render(t) {
    const w = appWindow(), mac = w?.platform === "macos", buttons = w?.buttons ? w : null;
    const side = titleSide(layout(), w, Number(settings().zoom ?? 1), WINDOW_BUTTONS);
    room = window.viewport_size();                // where the palette opens, from a key's command too
    return titleRow(t, { mac, name: spaceLabel(spaces().find((s) => s.active)?.name) || null,
      key: paletteKey(keys(), mac, shared("layout")), field: fieldWidth(this.wide, side), buttons,
      open: typeof shared(OPEN) === "string" }, this);
  }
}

/** The palette opened onto the title row's field (its press, its key), or closed again if open. */
export function togglePalette() {
  const open = shared(OPEN);
  if (typeof open === "string") {
    closeOverlay(open);
    return void setShared(OPEN, null);
  }
  const area = room ?? { width: 1280, height: 800 };
  const place = palettePlace(area, PALETTE_WIDE, PALETTE_HEAD + LISTED + PALETTE_FOOT);
  const shade = Math.min(SHADE, place.x);         // its room inside the window, so the app moves nothing
  setShared(OPEN, openOverlay({ mod: "herdr-fold", kind: "popup", frame: "none", props: { part: "palette",
    wide: place.width, most: Math.max(0, place.height - PALETTE_HEAD - PALETTE_FOOT), shade },
  at: { x: place.x - shade, y: place.y }, width: place.width + 2 * shade,
  height: Math.min(area.height - place.y, place.height + shade) }));
}

/** The command palette, herdr-fold's own (commands.html's Nyitva): its field over the title row's, the app's commands
 * and herdr-fold's own under it in their groups, each its key at its end, the first lit; what is typed finds them as
 * the / menu finds its rows, the best first; Enter runs the lit one, ↑ ↓ move it, Esc or a press beside closes it. */
export class Palette {
  /** @param {string | null} overlay its popup (null: a picture of it, the styleguide's) @param {{ wide?: number,
   * most?: number, shade?: number, typed?: string }} [how] its WIDE, its list MOST high, its SHADE's room, TYPED */
  constructor(overlay, { wide = PALETTE_WIDE, most = LISTED, shade = 0, typed = "" } = {}) {
    this.overlay = overlay;
    this.wide = wide;
    this.most = most;
    this.shade = shade;
    this.input = InputState.new({ placeholder: "Type a command…" });
    if (typed) this.input.set_value(typed);
    this.typed = typed;
    /** @type {number | null} the row the keys are on */
    this.cursor = 0;
    /** @type {number[]} each row's place in the list */
    this.listPlaces = [];
    this.listScroll = ScrollHandle.new();
    /** @type {import("./logic.js").PaletteEntry[]} the rows as last drawn: what each runs */
    this.shown = [];
    this.input.on("change", (_e, cx) => {
      const now = this.input.value().trim();
      if (now === this.typed) return;
      [this.typed, this.cursor] = [now, 0];       // the best found lit
      this.listScroll.scroll_to_item(0);
      cx.notify();
    });
    this.input.on("submit", () => this.run(this.shown[this.cursor ?? -1]));
  }

  /** The palette as the app's commands, layouts and keys are now, herdr-fold's own after them: Issues where the
   * repository is on GitHub (the dock's tabs', panel.js's TABS), the new agent as + names it in the space shown. */
  render(t) {
    const mac = appWindow()?.platform === "macos";
    const { agent, as } = newAgent(shared(RECENT_AGENTS), agentsOpen(shared(AGENTS_OPEN)),
      spaces().find((s) => s.active)?.machine ?? null);
    const own = { github: tabsState().github,
      plus: as === "chat" ? "New chat" : `New ${ADAPTERS[agent]?.name ?? agent}` };
    return this.draw(t, paletteEntries(commands(), layouts(), mac, own), keys(), shared("layout"), mac);
  }

  /** The palette of ENTRIES, each with its key as LIST binds it where layout NAME shows, MAC's ⌘ or the search.
   * @param {import("./logic.js").PaletteEntry[]} entries @param {{ section: string, keys: string, action: string }[]}
   * list @param {unknown} name @param {boolean} mac */
  draw(t, entries, list, name, mac) {
    const typed = Boolean(this.typed);
    const menu = slashMenu(entries.map((entry) => ({ part: entry.group, name: entry.title, typed: entry.name,
      line: "", words: entry.words, entry })), this.typed || null, Infinity);
    /** @type {any[]} */
    const drawn = [], places = [];
    this.shown = [];
    for (const part of menu.parts) {
      if (part.name) drawn.push(groupHead(t, part.name));
      for (const { name: title, part: group, entry } of part.items) {
        const n = this.shown.push(entry) - 1, key = entryKey(entry, list, name);
        places.push(drawn.length);
        drawn.push(panelRow(t, this, n, true).cursor_pointer().on_click(() => this.run(entry))
          .children(listWords(t, null, title, "", null))
          .when(typed, (e) => e.child(scopeTag(t, group, t.muted)))             // found: its group, as a tag
          .when(Boolean(key), (e) => e.child(h_flex().flex_none().gap(GAP)          // the keys' row's in its words'
            .children(keyNames(String(key), mac).flat().map((cap) => keyCap(t, cap, LINE)        // color: >= 4.5
              .text_color(this.cursor === n ? t.foreground : t.muted))))));
      }
    }
    if (this.cursor === null || this.cursor >= this.shown.length) this.cursor = this.shown.length ? 0 : null;
    return v_flex().id("palette").size_full().px(this.shade).pb(this.shade)
      .on_mouse_down("left", () => this.close())                    // the shadow's room: a press beside it
      .on_key_down((e, cx) => {
        if (e.key === "escape") this.close();
        else if ((e.key === "up" || e.key === "down") && this.shown.length) {
          this.cursor = panelStep(this.shown.length, this.cursor, e.key === "down" ? 1 : -1, () => false, 0);
          keepInView(this);
        } else return;
        cx.stop_propagation();
        cx.notify();
      })
      .child(panelSurface(t, "palette-surface", this.wide).flex_none()
        .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
        .child(h_flex().flex_none().p(R.pad).border_b(1).border_color(t.border)
          .child(h_flex().w_full().h(FIELD_HIGH).px(8).gap(6).items_center().rounded(6).border_1()
            .border_color(t.input ?? t.border).text_size(12).text_color(t.dim)
            .child(icon(mac ? "command" : "search", 14).text_color(t.muted))
            .child(Input.new(this.input).flex_1().h_full().text_size(12).text_color(t.foreground))
            .child(div().flex_none().text_size(11).child("Esc"))))
        .child(v_flex().px(R.pad).pb(R.pad).when(typed, (e) => e.pt(R.pad))
          .child(this.shown.length ? panelList(this, "palette-list", drawn, places, this.most)
            : listNote(t, "No command matches", false, R.inset).py(R.gap).line_height(`${LINE}px`))));
  }

  /** ENTRY run once the palette is closed: Duplicate mod asks for the mod's name, Duplicate layout copies the one
   * shown, a rename asks for its name (the app's). @param {import("./logic.js").PaletteEntry | undefined} entry */
  run(entry) {
    if (!entry) return;
    this.close();
    if (entry.name === "mod.clone") {
      openOverlay({ mod: "prompt", kind: "dialog", width: 380, props: { title: "Duplicate mod",
        hint: "Mod to copy; creates <name>-copy", command: { name: "mod.clone", args: {} } } });
    } else command(entry.name, entry.name === "layout.clone" ? { name: shared("layout") ?? "main" } : entry.args);
  }

  /** The palette closed (none in the styleguide). */
  close() {
    if (!this.overlay) return;
    closeOverlay(this.overlay);
    this.closed();
  }

  /** Once its popup is gone, however it went: the field no longer lit. */
  closed() {
    if (this.overlay && shared(OPEN) === this.overlay) setShared(OPEN, null);
  }
}

/** The title row (TITLE), its width and the pointer on its field kept in HOLDER (none in the styleguide): 36 high
 * with its hairline, the window's level (canvas), the field on its middle line, as the traffic lights the layout puts
 * there. @param {Title} title @param {{ wide: number | null, hovered: string | null } | null} holder */
export function titleRow(t, { mac, name, key, field, buttons, open = false }, holder = null) {
  const mark = mac ? "command" : "search";
  return h_flex().id("title").size_full().relative().items_center().justify_center().bg(t.canvas).border_b(1)
    .border_color(t.border)
    .when(Boolean(holder), (e) => e.on_size_change((/** @type {any} */ size, /** @type {any} */ cx) => {
      if (!holder || holder.wide === size.width) return;
      holder.wide = size.width;
      cx.notify();
    }))
    .child(open ? div().w(field || BUTTON).h(FIELD_HIGH).flex_none()      // handed over to the palette's own field
      : field ? commandField(t, mark, name, key, field, holder)
        : iconButton(t, "title-commands", mark, key ? `Commands  ${key}` : "Commands", togglePalette))
    .when(Boolean(buttons), (e) => e.child(h_flex().absolute().top(0).bottom(0).right(EDGE).gap(GAP).items_center()
      .child(iconButton(t, "window-minimize", "minus", "Minimize", () => command("window.minimize"), { left: true }))
      .child(iconButton(t, "window-maximize", buttons?.maximized ? "copy" : "square",
        buttons?.maximized ? "Restore" : "Maximize", () => command("window.maximize"), { size: 13, left: true }))
      .child(iconButton(t, "window-close", "x", "Close", () => command("window.close"), { left: true }))));
}

/** The command field, WIDTH wide: the palette's MARK, the space's NAME faint, its KEY; lit under the pointer
 * (HOLDER's); a press opens the palette. @param {"command" | "search"} mark @param {any} name
 * @param {string | null} key @param {number} width @param {any} holder */
function commandField(t, mark, name, key, width, holder) {
  const lit = holder?.hovered === "field";
  return h_flex().id("title-commands").w(width).h(FIELD_HIGH).flex_none().px(8).gap(6).items_center().rounded(6)
    .border_1().border_color(t.border).text_size(12).text_color(t.dim)
    .cursor_pointer().tooltip("Commands")
    .hover((s) => s.bg(t.hover).text_color(t.foreground)).active((s) => s.bg(t.selected))
    .when(Boolean(holder), (e) => e.on_hover(hovering(/** @type {any} */ (holder), "field")))
    .on_mouse_down("left", (_e, cx) => cx.stop_propagation())
    .on_click(togglePalette)
    .child(icon(mark, 14).text_color(lit ? t.foreground : t.muted))
    .child(div().flex_1().min_w(0).truncate().child(name ?? "Commands"))
    .when(Boolean(key), (e) => e.child(div().flex_none().text_size(11).child(String(key))));
}
