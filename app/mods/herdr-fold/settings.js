// @ts-check
// The one Settings, the window the sidebar's Settings and Cmd+, open (settings.html), one size: General, how agents
// open; Notifications; About in the TUI's words; under Application the app's own sections, each opening them there.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { appHome, closeOverlay, home, openOverlay, props, readTextFile, setShared, shared, writeTextFile,
  run as command } from "herdr";
import { AGENTS_OPEN, agentsOpen } from "./agents.js";
import { UPDATE } from "./helper.js";
import { ABOUT, aboutState, APP_SECTIONS, layoutToast, licenseOf, SECTIONS, sectionStep, SETTINGS, settingsSection,
  settingsTargets, soundsFor } from "./logic.js";
import { button, choices, icon, iconButton, SPINNER } from "./parts.js";
import { showPreview } from "./preview.js";

export const UPDATES = "herdr-fold.updates";      // core/update.py's last check: About, the status bar's item (shared)
const SECTION = "herdr-fold.settings-section";    // shared: the section shown, the one it opens at again
const OPEN = "herdr-fold.settings-open";          // shared: its dialog while it is open, so a second ask opens none
const FAILED = "GitHub did not answer";           // core/update.py's, for a look that did not answer at all
const SWITCH = "Check for updates automatically";
const OPENS = /** @type {[string, string][]} */ ([["chat", "Chat"], ["terminal", "Terminal"]]);
const OPENS_NOTE = "+, Chats, Issues' To agent and the agent list open agents this way, and a space starts on one. "
  + "Codex has no chat yet and always opens in a terminal.";
const NOTES = "herdr-fold.agent-notes";           // shared: false while An agent waits on you is off
const SOUNDS_KEPT = "herdr-fold.sounds-kept";     // shared: the app's sounds as the switch found them, given back on
const ON_OFF = /** @type {[string, string][]} */ ([["on", "On"], ["off", "Off"]]);
const NOTES_NOTE = "A note at the window's corner and a sound, when an agent in another tab asks or finishes. Errors "
  + "always show.";
/** @type {Promise<any> | null} the mod's own LICENSE, read once: its holder's name and page for the version line */
let license = null;

/** Whether An agent waits on you is on (the default): the app's notes and sounds, and a chat's own. */
export const notesOn = () => shared(NOTES) !== false;

/** herdr-fold's layout file with its root's toast as the switch has it (layoutToast's): from the tab bar's copy at
 * start too, as an install writes the file anew. */
export async function followNotes() {
  const path = `${appHome()}/layouts/herdr-fold.json`, text = await readTextFile(path);
  const next = text && layoutToast(text, notesOn(), "herdr-fold");
  if (next) await writeTextFile(path, next, text);
}

/** An agent waits on you turned ON or off: kept, the layout's toast following, the app's sounds with it (the person's
 * own value kept while off, soundsFor's). @param {boolean} on */
async function setNotes(on) {
  setShared(NOTES, on);
  await followNotes();
  const path = `${appHome()}/settings.json`, text = await readTextFile(path);
  const next = soundsFor(text, on, /** @type {boolean | null} */ (shared(SOUNDS_KEPT) ?? null));
  setShared(SOUNDS_KEPT, next.kept);
  await writeTextFile(path, next.text, text);
}

/** Settings opened over the window at SECTION (none: the one last looked at); open already, it shows SECTION.
 * @param {string} [section] */
export function openSettings(section) {
  if (section) setShared(SECTION, section);
  if (typeof shared(OPEN) === "string") return;
  setShared(OPEN, openOverlay({ mod: "herdr-fold", kind: "dialog", width: SETTINGS.wide, height: SETTINGS.high,
    props: { part: "settings" } }));
}

/** Whether Settings is open now (a float beside a rail takes a press in it as its own). */
export const settingsOpen = () => typeof shared(OPEN) === "string";

/** A Settings the app's last run left open is gone (the tab bar's copy says so once, as it starts). */
export const forgetSettings = () => void (shared(OPEN) && setShared(OPEN, null));

/** The CHANGELOG at VERSION's section in the shown space's preview tab (CORE: main.js's python), as the TUI's What's
 * new opens it. @param {string} version */
export async function whatsNew(core, version) {
  const { path, line } = await core(UPDATE, ["section", version], home(), null);
  const cut = path.lastIndexOf("/");
  showPreview({ kind: "file", root: path.slice(0, cut), path: path.slice(cut + 1), on: null,
    ...(line ? { line } : {}) });
}

export class SettingsView {
  /** The window (props: its overlay); CORE runs core/update.py (main.js's python); KEYS: it takes the keys, SECTION
   * the one it shows whatever was looked at last (the styleguide's copies).
   * @param {{ keys?: boolean, section?: string | null }} [how] */
  constructor(core, cx = null, { keys = true, section = null } = {}) {
    this.core = core;
    this.fixed = section;
    /** @type {any} the LICENSE's holder, once read */
    this.license = null;
    /** @type {string | null} what Tab has the keys on (settingsTargets'); null: nothing ringed till Tab is pressed */
    this.chosen = null;
    this.focus = cx && keys ? cx.focus_handle() : null;
    if (cx) {
      if (this.focus) cx.timer.after(0, () => this.focus.focus());      // the keys: ↑ ↓, Tab, Enter, Space, Esc
      cx.spawn(async (cx) => {
        license ??= readTextFile(`${appHome()}/mods/herdr-fold/LICENSE`).then((text) => licenseOf(text ?? ""))
          .catch(() => null);
        this.license = await license;
        cx.notify();
      });
    }
    this.overlay = props()?.overlay;
    this.checking = false;                        // a look asked for here, until it answers
    /** @type {boolean | null} the box as last pressed, until the look after it answers */
    this.on = null;
    /** @type {any} the check it shows, as the styleguide gives it; undefined: the last one, kept */
    this.found = undefined;
    /** @type {string | undefined} how agents open, as the styleguide gives it; undefined: as kept */
    this.opens = undefined;
    /** @type {boolean | undefined} An agent waits on you, as the styleguide gives it; undefined: as kept */
    this.notes = undefined;
  }

  /** The section shown: the styleguide's, else the one last looked at. */
  section() {
    return this.fixed ?? settingsSection(shared(SECTION));
  }

  /** SECTION shown, nothing ringed in it yet (a styleguide's copy keeps its own). @param {string} section */
  show(section, cx) {
    if (this.fixed || section === this.section()) return;
    this.chosen = null;
    setShared(SECTION, section);
    cx.notify();
  }

  /** The app's own Settings at SECTION (APP_SECTIONS'), in this one's place (a styleguide's copy: nowhere).
   * @param {string} section */
  appSection(section) {
    if (!this.core) return;
    this.shut();
    command("app.settings", { section });
  }

  /** The window closed. */
  shut() {
    closeOverlay(this.overlay);
    this.closed();
  }

  /** Once its dialog is gone, however it went (the app's Esc, a click beside): the next ask opens it again. */
  closed() {
    if (this.overlay && shared(OPEN) === this.overlay) setShared(OPEN, null);
  }

  /** A look at once (Check now), or after the automatic check switched (FIRST: switch on|off); the spinner till it
   * answers, a failure Couldn't check, never a spinner left turning. @param {string[]} [first] */
  look(cx, first) {
    if (this.checking) return;
    this.checking = true;
    cx.spawn(async (cx) => {
      try {
        if (first) await this.core(UPDATE, first, home(), null);
        setShared(UPDATES, await this.core(UPDATE, first ? ["check"] : ["check", "--now"], home(), null));
      } catch {
        setShared(UPDATES, { .../** @type {any} */ (shared(UPDATES) ?? {}), error: FAILED });
      } finally {
        this.checking = false;
        this.on = null;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** How agents open now: the styleguide's, else as kept. */
  opening() {
    return this.opens ?? agentsOpen(shared(AGENTS_OPEN));
  }

  /** Agents open in VALUE (chat, terminal) from now on, for every way in (a styleguide's copy: its own picture's).
   * @param {string} value */
  open(value, cx) {
    if (this.opens !== undefined) this.opens = value;
    else setShared(AGENTS_OPEN, value);
    cx.notify();
  }

  /** TARGET (settingsTargets') pressed, by the pointer or Enter and Space: General's choice (the other one), About's
   * author's page, its buttons, the box, the notices. @param {string} target */
  act(target, cx) {
    if (target === "opens") return this.open(this.opening() === "chat" ? "terminal" : "chat", cx);
    if (target === "notes") return this.note(!this.noting(), cx);
    if (target === "alerts") return this.appSection("alerts");
    if (!this.core) return;                       // the styleguide's copies: About's presses go nowhere
    const shown = aboutState(this.shown(), { license: this.license });
    const pressed = shown.buttons.find((b) => b.id === target);
    if (pressed) return this.press(pressed, cx);
    if (target === "author") {
      const url = shown.credits.flat().find((part) => "url" in part)?.url;
      if (url) cx.open_url(url);
    } else if (target === "box" && shown.box !== null) {
      this.on = !(this.on ?? shown.box);
      this.look(cx, ["switch", this.on ? "on" : "off"]);
    } else if (target === "notices") {
      showPreview({ kind: "file", root: `${appHome()}/mods/herdr-fold`, path: "THIRD_PARTY_NOTICES.md", on: null });
      this.shut();
    }
  }

  /** The keys: ↑ ↓ the section, Tab and Shift+Tab step through the section's controls, Enter or Space presses the one
   * ringed (← → General's choice), Esc closes the window. */
  key(e, cx) {
    const section = this.section();
    if (e.key === "escape") return void this.shut();
    if (e.key === "up" || e.key === "down") return void this.show(sectionStep(section, e.key === "down" ? 1 : -1), cx);
    if (e.key === "tab") {
      const targets = settingsTargets(section, aboutState(this.shown(), { license: this.license }));
      const at = this.chosen === null ? -1 : targets.indexOf(this.chosen), step = e.modifiers.shift ? -1 : 1;
      this.chosen = targets[(at + step + targets.length) % targets.length];
      return void cx.notify();
    }
    if (!this.chosen) return;
    if (e.key === "enter" || e.key === "space") this.act(this.chosen, cx);
    else if (this.chosen === "opens" && (e.key === "left" || e.key === "right")) {
      this.open(OPENS[e.key === "left" ? 0 : 1][0], cx);
    } else if (this.chosen === "notes" && (e.key === "left" || e.key === "right")) this.note(e.key === "left", cx);
  }

  /** The check shown: the styleguide's, else the last one kept. */
  shown() {
    return this.found !== undefined ? this.found : /** @type {any} */ (shared(UPDATES));
  }

  /** ELEMENT with a ring in the accent round it while Tab has the keys on TARGET, out of the flow: nothing moves.
   * @param {string} target @param {any} element */
  ringed(t, target, element) {
    return div().relative().flex_none().child(element).when(this.chosen === target, (e) => e.child(div().absolute()
      .top(-2).bottom(-2).left(-4).right(-4).rounded(6).border(1).border_color(t.accent)));
  }

  /** A link of About's (the author, the notices): muted, the text's color under the pointer, ringed by Tab.
   * @param {string} id @param {string} words */
  link(t, id, words) {
    return this.ringed(t, id, div().id(`about-${id}`).text_color(t.muted).cursor_pointer()
      .hover((s) => s.text_color(t.foreground)).on_click((_e, cx) => this.act(id, cx)).child(words));
  }

  /** PRESSED: a newer one's release notes, What's new, Check now. @param {{ id: string, url?: string }} pressed */
  press(pressed, cx) {
    if (!this.core) return;
    const found = /** @type {any} */ (shared(UPDATES));
    if (pressed.url) {
      cx.open_url(pressed.url);
      this.shut();
    } else if (pressed.id === "first" && found?.version) {
      cx.spawn(async () => {
        try {
          await whatsNew(this.core, found.version);
        } finally {
          this.shut();
        }
      });
    } else if (pressed.id === "check") {
      this.look(cx);
    }
  }

  /** The window: its name and × over a hairline; its sections on the side's level (chrome), the shown one on the
   * selection as Spaces' row, the app's under Application; the section 24 inside. */
  render(t, code) {
    const section = this.section();
    return v_flex().id("settings").size_full().text_size(13).text_color(t.foreground)
      .when(Boolean(this.focus), (e) => e.track_focus(this.focus).on_key_down((ev, cx) => this.key(ev, cx)))
      .child(h_flex().h(SETTINGS.head).flex_none().pl(16).pr(8).items_center().border_b(1).border_color(t.border)
        .child(div().flex_1().min_w(0).truncate().font_semibold().child("Settings"))
        .child(div().mr(1).child(iconButton(t, "settings-close", "x", "Close", () => this.shut()))))
      .child(h_flex().flex_1().min_h(0).items_start()
        .child(v_flex().w(SETTINGS.side).h_full().flex_none().py(SETTINGS.pad).px(8).gap(2).bg(t.chrome).border_r(1)
          .border_color(t.border)
          .children(SECTIONS.map(([id, name]) => this.row(t, id, name, id === section, (cx) => this.show(id, cx))))
          .child(div().mt(SETTINGS.apart).h(SETTINGS.row).flex_none().px(8).flex().items_center().text_size(11)
            .text_color(t.dim).opacity(0.7).child("Application"))              // a group's name: fainter than its rows
          .children(APP_SECTIONS.map(([id, name]) => this.row(t, `app-${id}`, name, false, () => this.appSection(id)))))
        .child(v_flex().flex_1().min_w(0).h_full().p(SETTINGS.pad)
          .children(section === "about" ? this.about(t, code)
            : section === "notifications" ? this.notifications(t) : this.general(t))));
  }

  /** A row of the sections' list, ID's: LIT the one shown, else muted, the text's color under the pointer.
   * @param {string} id @param {string} name @param {boolean} lit @param {(cx: any) => void} act */
  row(t, id, name, lit, act) {
    return div().id(`settings-${id}`).h(SETTINGS.row).flex_none().px(8).flex().items_center().rounded(6)
      .cursor_pointer().when(lit, (e) => e.bg(t.selected))
      .when(!lit, (e) => e.text_color(t.muted).hover((s) => s.bg(t.hover).text_color(t.foreground)))
      .on_click((_e, cx) => act(cx)).child(name);
  }

  /** Whether An agent waits on you is on: the styleguide's, else as kept. */
  noting() {
    return this.notes ?? notesOn();
  }

  /** An agent waits on you turned ON or off (a styleguide's copy: its own picture's). @param {boolean} on */
  note(on, cx) {
    if (this.notes !== undefined) this.notes = on;
    else if (on !== notesOn()) setNotes(on).catch(() => {});
    cx.notify();
  }

  /** A setting's row, Tab's ID: its NAME, a choice of OPTIONS at its end (VALUE lit, ACT picking), NOTE under it.
   * @param {string} id @param {string} name @param {[string, string][]} options @param {string} value
   * @param {(value: string, cx: any) => void} act @param {string} note */
  setting(t, id, name, options, value, act, note) {
    return [h_flex().h(28).flex_none().gap(16).items_center().child(div().flex_1().min_w(0).child(name))
      .child(this.ringed(t, id, choices(t, `settings-${id}`, options, value, act))),
    div().mt(8).max_w(360).flex_none().text_size(12).line_height("16px").text_color(t.dim).child(note)];
  }

  /** General: how agents open. */
  general(t) {
    return this.setting(t, "opens", "Open agents in", OPENS, this.opening(), (value, cx) => this.open(value, cx),
      OPENS_NOTE);
  }

  /** Notifications: An agent waits on you, then the app's own alerts (its sounds), a quiet row 16 under it. */
  notifications(t) {
    return [...this.setting(t, "notes", "An agent waits on you", ON_OFF, this.noting() ? "on" : "off",
      (value, cx) => this.note(value === "on", cx), NOTES_NOTE),
    div().mt(16).mx(-8).flex_none().child(this.ringed(t, "alerts",
      this.row(t, "app-alerts", "Herdr app alerts", false, () => this.appSection("alerts"))))];
  }

  /** About, its rows where they were: the name and the version line, the state's row, how to update while a newer
   * one is out, the box, the notices. */
  about(t, code) {
    const shown = aboutState(this.shown(), { checking: this.checking, license: this.license });
    const on = this.on ?? shown.box, { mark, title, note, tone, spin } = shown.state;
    const credits = shown.credits.flatMap((group, n) => [...(n ? [div().text_color(t.dim).child("·")] : []),
      ...group.map((part) => ("url" in part ? this.link(t, "author", part.text)
        : div().text_color(t.dim).child(part.text)))]);
    return [v_flex().h(ABOUT.head).flex_none().gap(4)
      .child(div().text_size(20).line_height("28px").font_bold().child("herdr-fold"))
      .child(h_flex().h(20).gap(4).items_center().children(credits)),
    h_flex().id("about-state").mt(ABOUT.gap).h(ABOUT.state).flex_none().gap(8).items_center()
      .when(spin, (e) => e.child(div().w(16).flex_none().text_color(t.muted).child(div().frames(SPINNER, 100))))
      .when(Boolean(mark), (e) => e.child(icon(mark === "ok" ? "check" : "arrow-up", 16)
        .text_color(mark === "ok" ? t.done : t.accent)))
      .child(v_flex().flex_1().min_w(0)
        .child(div().line_height("20px").truncate().text_color(t[tone] ?? t.foreground).child(title))
        .when(Boolean(note), (e) => e.child(div().text_size(12).line_height("16px").truncate().text_color(t.dim)
          .child(note))))
      .child(h_flex().flex_none().gap(8).children(shown.buttons.map((b) => this.ringed(t, b.id, button(t,
        `about-${b.id}`, b.label, b.id !== "check" || !this.checking, false, (cx) => this.press(b, cx)))))),
    ...(shown.how ? [div().mt(ABOUT.howGap).h(ABOUT.how).flex_none().px(12).flex().items_center().rounded(6)
      .bg(t.background).font_family(code).text_size(12).text_color(t.muted).truncate().child(String(shown.how))] : []),
    ...(shown.box !== null ? [h_flex().mt(ABOUT.gap).h(ABOUT.box).flex_none().child(this.ringed(t, "box",
      h_flex().id("about-box").gap(8).items_center().cursor_pointer().on_click((_e, cx) => this.act("box", cx))
        .child(div().size(16).flex_none().flex().items_center().justify_center().rounded(4).border(1)
          .border_color(on ? t.accent : t.input ?? t.border).when(Boolean(on), (e) => e.bg(t.accent)
            .child(icon("check", 12).text_color(t.accent_foreground ?? t.background))))
        .child(SWITCH)))] : []),
    h_flex().mt(ABOUT.gap).h(ABOUT.legal).flex_none().text_size(12).line_height("16px")
      .child(this.link(t, "notices", "Third-party notices"))];
  }
}
