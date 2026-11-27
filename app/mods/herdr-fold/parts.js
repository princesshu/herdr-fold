// @ts-check
// herdr-fold's own parts, which its views and its styleguide draw with: an icon, a button, a row's button, a chip, a
// choice of a few.
import { div, image, PathBuilder, svg } from "gpui-kit";
import { h_flex, HoverCard, Input } from "gpui-base";
import { closeOverlay, exec, layout, settings, run as command } from "herdr";
import { ringArc } from "./agents.js";
import { BRANDS, ICONS } from "./icons.js";
import { tile } from "./layers.js";

/** @typedef {import("./icons.js").IconName} IconName */
import { avatarFill, BADGE, badgeSpot, lastLine, LIST, networkLook, NOTE_MS, PAD, shortCount } from "./logic.js";

export const GAP = 4;              // between two hover backgrounds side by side, everywhere: tabs, icon buttons
// fixed-width text's one font, every view's and the styleguide's: the layout's terminals' (herdr-fold's own, which
// fonts/ brings), else the person's
export const CODE_FONT = "herdr-fold Mono";
/** @returns {string} */
export const codeFont = () => /** @type {any} */ (layout())?.font ?? settings().font_family ?? CODE_FONT;
// the scales every view keeps to, which the styleguide shows: padding and gaps on a 4 px grid, the type sizes, the
// corners (tests/test_app.py checks each value against them)
export const SPACE = [2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64];
export const TEXT = [10, 11, 12, 13, 15, 20, 28];
export const RADII = [4, 6, 8, 10];
// a card's inside, the same on every side (a row's hover pad halfway in): from logic.js, whose dock sizes need it
export { PAD };

/** The mod's icon NAME (icons.js's, Lucide's), SIZE square, in the text's color.
 * @param {import("./icons.js").IconName} name @param {number} [size] */
export const icon = (name, size = 14) => svg(ICONS[name]).size(size).flex_none();

/** A key as a cap (KEY: 1, esc, ↩), its edge seen on a lit row too; HIGH 18, 16 on a list row's line.
 * @param {string} key @param {number} [high] */
export const keyCap = (t, key, high = 18) => div().h(high).min_w(high).px(4).flex_none().flex().items_center()
  .justify_center().rounded(4).border(1).border_color(t.dim + "80").text_size(11).text_color(t.muted).child(key);

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

/** A connector's mark, SIZE square (connectors.html's .tile.xs): its BRAND's logo (icons.js's BRANDS), a one-color
 * mark in the text's; else (no brand, or no logo its licence gives) NAME's letter on a tile in the avatars' colors.
 * @param {string | null | undefined} brand @param {string} name @param {number} [size] */
export function brandMark(t, brand, name, size = 16) {
  const known = /** @type {Record<string, { logo: string | null, mono: boolean }>} */ (BRANDS)[brand ?? ""];
  if (known?.logo) {
    return known.mono ? svg(known.logo).size(size).flex_none().text_color(t.foreground)
      : image(known.logo).size(size).flex_none();
  }
  const { letter, color } = tile(name);
  return div().size(size).flex_none().flex().items_center().justify_center().rounded(4).bg(avatarFill(color, t))
    .text_size(10).line_height(`${size}px`).font_bold().text_color("#ffffff").child(letter);
}

/** A network's mark, SIZE square, as brandMark draws a connector's: its logo with no tile (one-color in its color or
 * the text's), a plain icon in muted, else its letter muted on a raised tile (WireGuard, Cloudflare); none for none
 * known. @param {string | null | undefined} network @param {number} [size] */
export function networkMark(t, network, size = 16) {
  const look = networkLook(network);
  if (!look) return null;
  const tint = (/** @type {string} */ tone) => tone.startsWith("#") ? tone : t[tone];
  if (look.path) {
    return look.image ? image(look.path).size(size).flex_none()
      : svg(look.path).size(size).flex_none().text_color(tint(String(look.tint)));
  }
  return div().size(size).flex_none().flex().items_center().justify_center().rounded(4).bg(t.raised)
    .text_size(10).line_height(`${size}px`).font_bold().text_color(tint(String(look.tint))).child(look.letter);
}

/** A sign-in's spinner (connectors.html's .spin): 12, in the accent, a turn in 0.9 s. */
export const spinner = (t) => icon("loader-circle", 12).text_color(t.accent).spin(900);

/** A file's icon (logic.js's fileIcon, a path), 16 square, in its own colors. @param {string} path */
export const fileMark = (path) => image(path).size(16).flex_none();

export const BUTTON = 26;          // an icon button's square
export const DOT = 7, RINGED = DOT + 4;  // an icon button's dot, ringed 2 round, its centre on the icon's corner
export const INDENT = 6 + 14 + 6;  // a row's content under its section's name: the head's padding, chevron and gap

/** An icon (NAME) button, 26 square, TIP its tip (LEFT: to its left, as the bar's end has them; null: none); its press
 * (PRESS gets it) never drags what it sits on; LIT in the accent; DOT a mark in that color on its icon's top-right
 * corner, ringed in the bar's fill (canvas). @param {IconName} name @param {string | null} tip @param {any} act */
export const iconButton = (t, id, name, tip, act, { size = 14, color = t.muted, left = false, lit = false,
  dot = /** @type {string | null} */ (null), press = /** @type {((e: any) => void) | null} */ (null) } = {}) => {
  const button = div().id(id).relative().size(BUTTON).flex_none().flex().items_center().justify_center().rounded(6)
    .text_color(lit ? t.accent : color).cursor_pointer().when(!left && tip !== null, (e) => e.tooltip(String(tip)))
    .hover((s) => s.bg(t.hover).text_color(lit ? t.accent : t.foreground))
    .on_mouse_down("left", (e, cx) => {
      cx.stop_propagation();
      press?.(e);
    }).on_click((_e, cx) => act(cx)).child(icon(name, size))
    .when(Boolean(dot), (e) => e.child(div().absolute().left((BUTTON + size - RINGED) / 2)
      .top((BUTTON - size - RINGED) / 2).size(RINGED).rounded_full().bg(String(dot)).border_2()
      .border_color(t.canvas)));
  return left && tip !== null ? HoverCard.new(`${id}-tip`).anchor("top_right").open_delay(500).close_delay(0)
    .trigger(button).content(div().mt(4).px(8).py(2).rounded(6).border_1().border_color(t.border)
      .bg(t.popover ?? t.raised).text_size(12).text_color(t.foreground).child(tip)) : button;
};

/** A list's or a floating panel's NAME, as the app's lists: 11, medium, muted. @param {string} name */
export const listName = (t, name) => div().text_size(11).font_medium().text_color(t.muted).child(name);

/** A sidebar list's head, as Spaces has it: its NAME and its BUTTONS at the end.
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

/** @typedef {{ text: string, error: boolean, done?: boolean }} Note what was done (ERROR: what went wrong; DONE: a
 * change made, its check before it) */

/** NOTE under a list, on the card's foot, as the TUI's last row and Files' and Changes' problems: never over the rows,
 * so none moves; PAD in, PAD / 2 over it, 11, muted (an error ansi1), wrapping; a change DONE in the text's color,
 * after the check in ansi2 (12, centred on the words' line). @param {Note} note */
export const footNote = (t, note) => note.done && !note.error
  ? h_flex().flex_none().px(PAD).pt(PAD / 2).pb(PAD).gap(6).items_center().text_size(11).text_color(t.foreground)
    .child(icon("check", 12).text_color(t.ansi2)).child(div().min_w(0).child(note.text))
  : div().flex_none().px(PAD).pt(PAD / 2).pb(PAD).text_size(11).text_color(note.error ? t.ansi1 : t.muted)
    .child(note.text);

/** NOTE (or none) on HOLDER's line, a done thing's gone after NOTE_MS unless another came meanwhile, an error's kept.
 * @param {{ note: Note | null }} holder @param {Note | null} note */
export function keepNote(holder, note, cx) {
  holder.note = note;
  if (note && !note.error) {
    cx.timer.after(NOTE_MS, (/** @type {any} */ cx) => {
      if (holder.note !== note) return;
      holder.note = null;
      cx.notify();
    });
  }
  cx.notify();
}

// views drawn: each one's measured elements an id of its own, as the app keeps an element's last size by its id and
// tells a second one of that id and size none (two chats or previews side by side, the styleguide's specimens)
let views = 0;
/** VIEW's own number, taken on its first draw (a specimen is made without its constructor). @param {any} view */
export const viewId = (view) => (view.uid ??= views++);

export const SPINNER = [..."⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"];     // a request under way, as the TUI's: ✦ writing, Issues loading
export const SPRING = { response: 240, damping: 1 };   // a fold opening or shutting, sprung by the app, no overshoot

/** A fold's chevron, SIZE square in COLOR: SHUT's icon while shut, OPEN's while open, the one fading into the other as
 * the app springs its section (GPUI turns nothing once, so the two cross). @param {string} id @param {boolean} open
 * @param {number} [size] @param {string} [color] @param {[IconName, IconName]} [names] */
export const fold = (id, open, size = 14, color = undefined, names = ["chevron-right", "chevron-down"]) =>
  div().id(id).relative().size(size).flex_none().when(Boolean(color), (e) => e.text_color(String(color)))
    .children(names.map((name, n) => icon(name, size).id(`${id}-${n}`).absolute().top_0().left_0()
      .opacity(Number(open) === n ? 1 : 0).spring("opacity", SPRING)));

/** COUNT in a round badge, short when large (1.2k), the accent's: as VS Code's activity bar has them on an icon,
 * BADGE high and at least as wide, its number 10 semibold; after a tab's name HIGH (TAB_COUNT) and its number TEXT.
 * @param {number} count */
export const badge = (t, count, high = BADGE, text = 10) => div().h(high).min_w(high).px(4).flex().items_center()
  .justify_center().rounded_full().bg(t.accent).text_color(t.accent_foreground ?? t.background)
  .text_size(text).line_height(`${high}px`).font_semibold().child(shortCount(count));

/** COUNT's badge on an icon whose top-right corner is at X, Y in its relative box (logic.js's badgeSpot), none at 0;
 * out of the flow, so the icon, its name and the buttons beside stay as a badge comes, goes or grows.
 * @param {number} count @param {number} x @param {number} y */
export const countBadge = (t, count, x, y, spot = badgeSpot(x, y)) => div().absolute().left(spot.left).top(spot.top)
  .when(count > 0, (e) => e.child(badge(t, count)));

/** A square tab, as the panel heads its views and a folded side shows its panels: CONTENT (a GLYPH square icon), SIZE
 * square, the shown one (ACTIVE) on the selection, a state's DOT at its corner or a COUNT's badge on the icon's; the
 * mouse on it names it (TIP). @param {any} content @param {any} how */
export function iconTab(t, id, content, { size = 30, glyph = 15, active = false, dot = null, count = 0, tip, act }) {
  return div().id(id).relative().size(size).flex_none().flex().items_center().justify_center().rounded(6)
    .cursor_pointer().tooltip(tip).text_size(15).bg(active ? t.selected : t.raised)
    .text_color(active ? t.foreground : t.muted).hover((s) => s.bg(t.hover)).on_click((_e, cx) => act(cx))
    .child(content)
    .when(Boolean(dot), (e) => e.child(div().absolute().top(-3).right(-3).size(9).rounded_full()
      .bg(/** @type {string} */ (dot)).border_2().border_color(t.chrome)))
    .child(countBadge(t, count, (size + glyph) / 2, (size - glyph) / 2));
}

/** A state's mark, as herdr marks an agent's: a disc in its color (working, blocked, done), a ring when idle, a faint
 * dot when closed or none (STATE empty). @param {string | null | undefined} state */
export function stateMark(t, state) {
  const color = state ? t[state] ?? t.dim : t.dim;
  const mark = state === "idle" ? div().size(7).rounded_full().border_1().border_color(color)
    : div().size(state ? 7 : 5).rounded_full().bg(color);
  return div().w(STATE_MARK).flex_none().flex().items_center().justify_center().child(mark);
}
export const STATE_MARK = 10;      // px: a state mark's room

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

// a switch's pill, its knob and the knob's inset: center-chat.html's Ultracode's, and connectors.html's .sw on a
// list's 16 line (the + menu's connectors)
const SWITCH = { row: { wide: 34, high: 20, knob: 14, inset: 3 }, line: { wide: 28, high: 16, knob: 12, inset: 2 } };

/** A switch: a pill (34 × 20, its 14 px knob 3 in; on a list's LINE 28 × 16, the knob 12, 2 in), the knob at the left
 * while off, at the right on the accent while ON; while it cannot be pressed (ENABLED false), faint.
 * @param {boolean} [line] */
export const toggle = (t, id, on, enabled, act, line = false, { wide, high, knob, inset } = SWITCH[line ? "line"
  : "row"]) => div().id(id).w(wide).h(high).flex_none().relative().rounded_full()
  .bg(on ? t.accent : t.raised).when(!enabled, (e) => e.opacity(0.5))
  .when(enabled, (e) => e.cursor_pointer().on_click((_e, cx) => act(cx)))
  .child(div().absolute().top(inset).left(on ? wide - knob - inset : inset).size(knob).rounded_full()
    .bg(on ? t.accent_foreground ?? t.background : t.muted));

/** A source's tag (connectors.html's .tagb), never in a hue: its WORD, 11, 16 high, muted on a raised chip.
 * @param {string} word */
export const scopeTag = (t, word) => div().h(16).flex_none().px(6).flex().items_center().rounded(4).bg(t.raised)
  .text_size(11).line_height("16px").text_color(t.muted).child(word);

export const ACTION = 26;          // px: a properties button, center-chat.html's .btn

/** A properties button (connectors.html's .btn, .go2, .ghost), ACTION high: LOOK "solid" on the accent, "raised",
 * or "plain" in muted; one that cannot be pressed now (USABLE false) faint, a TIP saying why. @param {string} id
 * @param {string} label @param {string} look @param {(cx: any) => void} press @param {string | null} [tip] */
export function actButton(t, id, label, look, usable, press, tip = null) {
  const solid = look === "solid", raised = look === "raised";
  return div().id(id).h(ACTION).min_w(0).px(PAD).flex().items_center().rounded(8)
    .when(solid, (e) => e.bg(t.solid).font_bold()).when(raised, (e) => e.bg(t.raised))
    .text_color(solid ? t.solid_foreground : !usable ? t.dim : raised ? t.foreground : t.muted)
    .when(usable, (e) => e.cursor_pointer().on_click((/** @type {any} */ _e, /** @type {any} */ cx) => press(cx)))
    .when(usable && !solid, (e) => e.hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground)))
    .when(Boolean(tip), (e) => e.tooltip(tip ?? ""))
    .child(div().min_w(0).truncate().child(label));
}

/** A properties LINE ([label, value, a third or null]), 20 high: its label muted in a column LABEL px wide, its value
 * in the CODE font 11 (null: a phrase, in the text's), the third muted at the end. @param {string} id
 * @param {[string, string, string | null]} line @param {number} label @param {string | null} code */
export const propertyLine = (t, id, [name, value, third], label, code) => h_flex().id(id).h(20).flex_none().gap(8)
  .items_center().tooltip(value).child(div().w(label).flex_none().truncate().text_color(t.muted).child(name))
  .child(code ? div().flex_1().min_w(0).truncate().font_family(code).text_size(11).child(value)
    : div().flex_1().min_w(0).truncate().child(value))
  .when(Boolean(third), (e) => e.child(div().flex_none().text_color(t.muted).child(third ?? "")));

/** A count on a chip, as the TUI sidebar's sections show theirs. */
export function chip(t, text) {
  return div().flex_none().px(6).rounded(4).text_size(11).font_semibold().bg(t.raised).text_color(t.foreground)
    .child(text);
}

/** A choice of a few as one control (usage.html's .seg): LIST's [value, label] on the window's level, BUTTON high;
 * the CHOSEN one raised, a press on another gives PICK its value, OFF's greyed. @param {string} id @param {any[]} [off]
 * @param {[string, string][]} list @param {string | null} chosen @param {(value: string, cx: any) => void} pick */
export function segmented(t, id, list, chosen, pick, off = []) {
  return h_flex().id(id).h(BUTTON).flex_none().p(2).gap(2).items_center().rounded(8).border_1()
    .border_color(t.border).bg(t.canvas).children(list.map(([value, label]) => div().id(`${id}-${value}`).h_full()
      .px(8).flex().items_center().rounded(6).text_size(12).whitespace_nowrap()
      .when(value === chosen, (e) => e.bg(t.raised).text_color(t.foreground))
      .when(off.includes(value) && value !== chosen, (e) => e.text_color(t.dim))
      .when(value !== chosen && !off.includes(value), (e) => e.text_color(t.muted).cursor_pointer()
        .hover((/** @type {any} */ s) => s.bg(t.hover).text_color(t.foreground))
        .on_click((/** @type {any} */ _e, /** @type {any} */ cx) => pick(value, cx)))
      .child(label)));
}

/** A model's or a part's swatch (usage.html's .sw2): SIZE square, its corners 2, in COLOR. @param {string} color
 * @param {number} [size] */
export const swatch = (color, size = 8) => div().size(size).flex_none().rounded_xs().bg(color);

export const SAVING = 600000;         // ms macOS's save panel or chooser waits: the most exec() waits
// macOS's save panel (osascript's): ARGV its prompt, the file's name and the folder it opens on; "" for none
// (cancelled)
const SAVE = "function run(argv) { const app = Application.currentApplication(); app.includeStandardAdditions = true; "
  + "app.activate(); try { return app.chooseFileName({ withPrompt: argv[0], defaultName: argv[1], "
  + "defaultLocation: Path(argv[2]) }).toString(); } catch (e) { if (e.errorNumber === -128) return ''; throw e; } }";

/** The file macOS's save panel names (PROMPT its words, NAME the file's at first, in FOLDER at first; a file there
 * replaced only as the panel asks); "" when cancelled. Throws why it could not ask. @param {string} prompt
 * @param {string} name @param {string} folder */
export async function savePanel(prompt, name, folder) {
  const done = await exec("osascript", ["-l", "JavaScript", "-e", SAVE, prompt, name, folder], { timeout: SAVING });
  if (done.code !== 0) throw new Error(lastLine(done));
  return done.stdout.trim();
}

// how this Mac's user has a time written (Language & Region): macOS's own pattern for each template, asked once a run
const FORMS = "ObjC.import('Foundation'); const f = (t) => $.NSDateFormatter.dateFormatFromTemplateOptionsLocale(t, 0, "
  + "$.NSLocale.currentLocale).js; JSON.stringify({ time: f('jmm'), day: f('MMMdjmm'), year: f('yMMMdjmm'), "
  + "weekday: f('EEEMMMdjmm') })";
/** @type {Promise<any> | null} */
let forms = null;

/** This Mac's forms of a time (timeline.js's setForms), asked of macOS once; null where it cannot say. */
export function systemForms() {
  forms = forms ?? exec("osascript", ["-l", "JavaScript", "-e", FORMS])
    .then((done) => (done.code === 0 ? JSON.parse(done.stdout) : null)).catch(() => null);
  return forms;
}

const NOTE_DOT = { error: "blocked", warning: "working" };   // a note's level's color, as the app's toast has it

/** A NOTE (a toast's props) as the app's own toast draws it, while An agent waits on you is off: its icon (else its
 * level's dot), the title and the body's first line; a click runs its action and closes it. @param {{ title?: string,
 * body?: string, level?: string, icon?: string, overlay?: string, action?: { name: string, args?: any } }} note */
export const noteToast = (t, note) => h_flex().id("note").size_full().px(16).gap(12).items_center().bg(t.popover)
  .cursor_pointer().hover((s) => s.bg(t.hover)).on_click(() => {
    if (note.action?.name) command(note.action.name, note.action.args ?? {});
    if (note.overlay) closeOverlay(note.overlay);
  })
  .child(note.icon ? image(note.icon).w(18).h(18).flex_none()
    : div().size(8).rounded(4).flex_none().bg(t[NOTE_DOT[/** @type {"error" | "warning"} */ (note.level)] ?? "accent"]))
  .child(div().flex_1().min_w(0).flex().flex_col()
    .child(div().truncate().font_semibold().text_size(13).text_color(t.foreground).child(note.title ?? ""))
    .when(Boolean(note.body), (e) => e.child(div().truncate().text_size(12).text_color(t.muted)
      .child(String(note.body).split("\n", 1)[0]))));
