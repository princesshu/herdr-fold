// @ts-check
// A text file in the app's own editor, as VS Code's: Cmd+S saves in place, Cmd+F finds, a dot while unsaved, a draft
// in herdr-fold's state folder so closing asks nothing; in a tab of its own, or as the preview's Code view.
import { div } from "gpui-kit";
import { Editor, EditorState, h_flex, Input, InputState, v_flex } from "gpui-base";
import { focused, home, panes, readTextFile, setShared, shared, spaces, theme, watchFolder, writeTextFile,
  run as command } from "herdr";
import { MEDIA, STATEFILE } from "./helper.js";
import { draftName, editorLanguage, findAll, findCount, indentOf, modTab, nextMatch, said, unsavedKey, unsavedTabs,
  withEnds } from "./logic.js";
import { openAgentPanel } from "./panel.js";
import { actButton, codeFont, icon, iconButton } from "./parts.js";

/** shared: each editor tab's file by its slot ({ space, root, path, on, line, n }) */
const EDITORS = "herdr-fold.editors";
const UNSAVED = "herdr-fold.unsaved";      // shared: the tabs with unsaved changes, by unsavedKey()
const DRAFT = 1000;                        // ms between two writes of a draft while typing
const LOOK = 10000;                        // ms between two looks at another machine's file (no watch there)
const FIND = 190;                          // px: the find bar's field
const NARROW = 400;                        // px: an editor narrower has its find bar across it
/** Why a file is read only, in words (core/media.py's text()'s, and another machine's) */
const WHY = { large: "Over 1 MiB: its start, read only", binary: "Not a text file",
  remote: "On another machine: read only", link: "A link out of the folder: read only" };
const SETTINGS = "Changes here are not checked; the Agent panel's forms are, with Undo";

/** @type {Promise<string> | null} the drafts' folder, made its owner's only once (core/statefile.py's) */
let drafts = null;

/** The drafts' folder, in herdr-fold's state folder (CORE: main.js's python). */
function draftFolder(core) {
  drafts ??= core(STATEFILE, ["folder", "drafts"], home(), null).then((made) => String(made.folder));
  drafts.catch(() => (drafts = null));
  return drafts;
}

/** SPACE's tabs with unsaved changes (their × a dot). @param {any} space */
export const unsavedIn = (space) => unsavedTabs(space, /** @type {Record<string, boolean>} */ (shared(UNSAVED) ?? {}));

/** At the app's start: the drafts of files that are gone dropped (CORE: main.js's python). */
export const sweepDrafts = (core) => core(STATEFILE, ["sweep", "drafts"], home(), null).catch(() => {});

/** The editor's colors from the theme T's (concrete hex only, as EditorState takes them). */
const syntax = (t) => Object.fromEntries(Object.entries({ keyword: t.ansi5, string: t.ansi2, comment: t.dim,
  function: t.ansi4, type: t.ansi3, number: t.ansi3, constant: t.ansi3, boolean: t.ansi5, variable: t.foreground,
  operator: t.muted, punctuation: t.muted, "string.escape": t.ansi6, heading: t.ansi4, code: t.ansi2, quote: t.dim,
  list: t.ansi5, link: t.ansi6 }).filter(([, hex]) => /^#[0-9a-f]{6}([0-9a-f]{2})?$/i.test(String(hex ?? ""))));

/** WHAT ({ root, path, on, line }) in an editor tab of the shown space: its own tab shown (at LINE), else a new one,
 * named for the file: every file a tab of its own, never one taking another's. */
export function openEditor(what) {
  const all = spaces(), space = all.find((s) => s.active);
  if (!space) return;
  const kept = /** @type {Record<string, any>} */ (shared(EDITORS) ?? {}), live = panes();
  const shown = Object.entries(kept).filter(([, one]) => one.space === space.id && modTab(space, one.path, live));
  const [slot, was] = shown.find(([, one]) => one.root === what.root && one.path === what.path && one.on === what.on)
    ?? [`${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, null];
  const left = Object.entries(kept).filter(([id, one]) => all.some((s) => s.id === one.space)
    && (one.space !== space.id || shown.some(([mine]) => mine === id)));
  setShared(EDITORS, { ...Object.fromEntries(left), [slot]: { ...what, space: space.id, n: (was?.n ?? 0) + 1 } });
  const tab = was ? modTab(space, was.path, live) : null;
  if (!tab) return void command("tab.new", { name: what.path, mod: "herdr-fold", props: { part: "editor", slot } });
  command("tab.select", { id: tab });
}

/** An editor tab: the file its slot names (openEditor()'s), opened anew when another takes the tab, at a LINE asked. */
export class EditorTab {
  /** SLOT's tab; CORE: main.js's python. @param {{ slot: string }} props */
  constructor(props, core) {
    this.slot = props.slot;
    this.core = core;
    /** @type {number | null} the slot's ask shown */
    this.n = null;
    /** @type {Editing | null} */
    this.editing = null;
  }

  /** From render: the slot's newest ask, after the render (which it redraws). */
  watch(cx) {
    const what = /** @type {any} */ (shared(EDITORS))?.[this.slot];
    if (!what || what.n === this.n) return;
    this.n = what.n;
    const was = this.editing?.what, same = was && was.root === what.root && was.path === what.path;
    cx.timer.after(0, (cx) => {
      if (same) return this.editing?.goTo(what.line, cx);
      this.editing?.release();
      this.editing = new Editing(what, this.core, { space: what.space, tab: what.path });
      this.editing.load(cx);
    });
  }

  render(t, code) {
    return this.editing ? this.editing.render(t, code) : div();
  }
}

/** One file in the editor: read (core/media.py's text() says what of it can be edited), its draft taken back,
 * saved over what it was read as (writeTextFile's expected), followed on disk. */
export class Editing {
  /** WHAT's file ({ root, path, on, line }) in the tab named TAB of SPACE; CORE: main.js's python. SAVED(cx): written
   * or read anew (the preview draws it again).
   * @param {{ space: string, tab: string, saved?: ((cx: any) => void) | null }} where */
  constructor(what, core, { space, tab, saved = null }) {
    this.what = what;
    this.core = core;
    this.space = space;
    this.tab = tab;
    this.onSaved = saved;
    /** @type {any} the EditorState, once read */
    this.state = null;
    /** @type {string | null} the file's text as read or last written: what a save expects there */
    this.disk = null;
    /** @type {string | null | undefined} the disk's newer text (null: gone) while the bar asks Reload or Keep mine */
    this.newer = undefined;
    this.dirty = false;
    /** @type {string | null} why it is read only (WHY's key) */
    this.why = null;
    this.settings = false;                   // an agent's settings file: the Agent panel's forms are its checked way
    /** @type {string | null} the path written: the file, or a link's target in the folder */
    this.real = null;
    /** @type {string | null} what went wrong, or that the file is gone */
    this.note = null;
    this.loading = true;
    this.busy = false;
    this.live = true;                        // until released
    /** @type {string | null} the draft's path, and its text as last written there (its next write's expected) */
    this.draft = null;
    /** @type {string | null} */
    this.drafted = null;
    /** @type {any} the draft's write waiting, the disk's watch or timer */
    this.pending = null;
    /** @type {any} */
    this.watching = null;
    /** @type {any} */
    this.ticking = null;
    /** @type {any} the find bar's field, made once */
    this.query = null;
    /** @type {{ matches: [number, number][], at: number, from: number } | null} the find bar while open */
    this.finder = null;
    this.width = 0;                          // px, as last laid out
  }

  /** The file read and shown: its draft taken back where there is one (the bar too where the disk changed since). */
  async load(cx) {
    const { root, path, on } = this.what;
    try {
      const look = await this.core(MEDIA, ["text", root, `${root}/${path}`], root, on);
      if (!this.live) return;
      Object.assign(this, { real: look.real, settings: look.settings, why: look.why ?? (on ? "remote" : null) });
      if (look.why === "gone") return void this.vanish();
      if (look.why === "binary") return;
      const text = look.why === "large" ? look.start : await readTextFile(look.real, { on });
      if (text === null) return void this.vanish();
      this.disk = text;
      const draft = this.why ? null : await this.readDraft();
      this.state = this.made(draft?.text ?? text);
      if (draft) {
        this.dirty = withEnds(draft.text, text) !== text;
        if (draft.base !== text && this.dirty) this.newer = text;
        if (!this.dirty) this.dropDraft();
      }
      const at = draft?.cursor ?? lineStart(text, this.what.line);
      this.state.set_selected_range({ start: at, end: at });
      this.follow(cx);
    } catch (e) {
      this.note = said(e);
    } finally {
      this.loading = false;
      this.publish();
      cx.notify();
    }
  }

  /** The editor holding TEXT: the file's language, indent and the theme's colors; read only where WHY says. */
  made(text) {
    const indent = indentOf(text), t = theme();
    const state = EditorState.new({ language: editorLanguage(this.what.path), value: text, readonly: Boolean(this.why),
      font_family: codeFont(), tab_size: indent.size, hard_tabs: indent.hard, syntax: syntax(t) });
    state.on("change", (_e, cx) => this.edited(cx));
    return state;
  }

  /** The draft kept for this file, or null (none, or another file's under the same name). */
  async readDraft() {
    this.draft = `${await draftFolder(this.core)}/${draftName(String(this.real))}`;
    this.drafted = await readTextFile(this.draft).catch(() => null);
    try {
      const draft = JSON.parse(this.drafted ?? "null");
      return draft?.path === this.real && typeof draft.text === "string" ? draft : null;
    } catch {
      return null;
    }
  }

  /** A change typed: the dot (shared) once it differs from the disk, the find's matches anew, the draft written
   * within DRAFT (Markdown drawn again then). */
  edited(cx) {
    if (!this.state || this.why) return;
    const dirty = withEnds(this.state.value(), this.disk) !== this.disk;
    if (dirty !== this.dirty) {
      this.dirty = dirty;
      this.publish();
      cx.notify();
    }
    if (this.finder) this.search(false);
    this.pending ??= cx.timer.after(DRAFT, (cx) => {
      this.pending = null;
      this.keepDraft();
      cx.notify();
    });
  }

  /** The draft written (its text, what the disk held, the cursor), or dropped once nothing is unsaved. */
  async keepDraft() {
    if (!this.draft || !this.state) return;
    if (!this.dirty) return this.dropDraft();
    const body = JSON.stringify({ path: this.real, text: this.state.value(), base: this.disk,
      cursor: this.state.selected_range().start });
    try {
      await writeTextFile(this.draft, body, this.drafted);
      this.drafted = body;
    } catch {
      this.drafted = await readTextFile(this.draft).catch(() => null);      // the next write goes over it
    }
  }

  /** The draft gone: after a save, a Reload, or with its file. */
  dropDraft() {
    if (this.drafted === null || !this.draft) return;
    this.drafted = null;
    this.core(STATEFILE, ["remove", "drafts", this.draft.slice(this.draft.lastIndexOf("/") + 1)], home(), null)
      .catch(() => {});
  }

  /** Whether the dot shows on this editor's tab, written to UNSAVED (shared) when that changes. */
  publish() {
    const all = /** @type {Record<string, boolean>} */ (shared(UNSAVED) ?? {}), key = unsavedKey(this.space, this.tab);
    if (Boolean(all[key]) === this.dirty) return;
    const { [key]: _, ...rest } = all;
    setShared(UNSAVED, this.dirty ? { ...rest, [key]: true } : rest);
  }

  /** Cmd+S ("save") or Cmd+F ("find"), for the tab shown only: whether it was this editor's to do. */
  command(asked, cx) {
    if (!this.state) return false;
    const space = spaces().find((s) => s.id === this.space);
    if (!space || focused()?.tab !== modTab(space, this.tab, panes())) return false;
    if (asked === "save") this.save(cx);
    else this.openFind(cx);
    return true;
  }

  /** Written in place over what it was read as, its line ends kept; while the bar asks, nothing is written over. */
  save(cx) {
    if (!this.state || this.why || !this.dirty || this.newer !== undefined || this.busy) return;
    const text = withEnds(this.state.value(), this.disk), real = String(this.real);
    this.busy = true;
    cx.spawn(async (cx) => {
      try {
        await writeTextFile(real, text, this.disk);
        Object.assign(this, { disk: text, note: null, dirty: withEnds(this.state.value(), text) !== text });
        if (this.dirty) await this.keepDraft();
        else this.dropDraft();
        this.onSaved?.(cx);
      } catch (e) {
        const now = await readTextFile(real, { on: this.what.on }).catch(() => undefined);
        if (now !== undefined && now !== this.disk) this.newer = now;           // the disk changed: the bar asks
        else this.note = `Could not save: ${said(e)}`;
      } finally {
        this.busy = false;
        this.publish();
        cx.notify();
      }
    });
  }

  /** The disk's text shown, what was typed dropped (Reload). */
  reload(cx) {
    const newer = this.newer;
    this.newer = undefined;
    if (newer === null || newer === undefined) return void (newer === null && this.vanish(cx));
    Object.assign(this, { disk: newer, dirty: false });
    this.put(newer);
    this.dropDraft();
    this.publish();
    this.onSaved?.(cx);
    cx.notify();
  }

  /** What was typed kept: the next save goes over the disk's newer text (Keep mine). */
  keep(cx) {
    const disk = this.newer ?? null;
    Object.assign(this, { disk, newer: undefined, dirty: withEnds(this.state.value(), disk) !== disk });
    this.publish();
    cx.notify();
  }

  /** The file is gone: nothing to edit, its draft dropped. */
  vanish(cx = null) {
    Object.assign(this, { state: null, note: "This file is no longer there", dirty: false });
    this.dropDraft();
    this.publish();
    cx?.notify();
  }

  /** TEXT in the editor, the cursor where it was. @param {string} text */
  put(text) {
    const { start, end } = this.state.selected_range();
    this.state.set_value(text);
    this.state.set_selected_range({ start: Math.min(start, text.length), end: Math.min(end, text.length) });
  }

  /** The cursor at LINE's start (a reopened file asked at a line). */
  goTo(line, cx) {
    if (!this.state || !line) return;
    const at = lineStart(this.state.value(), line);
    this.state.set_selected_range({ start: at, end: at });
    cx.notify();
  }

  /** The disk followed: its folder watched here (another machine's file looked at on a timer); a change shown at once
   * where nothing is unsaved, else asked about by the bar. */
  follow(cx) {
    const real = String(this.real), dir = real.slice(0, real.lastIndexOf("/")) || "/";
    const timer = () => (this.ticking = cx.timer.every(LOOK, (cx) => this.look(cx)));
    if (this.what.on) return void timer();
    cx.spawn(async (cx) => {
      while (this.live) {
        this.watching = watchFolder(dir);
        const changed = await this.watching.catch(() => null);
        if (!this.live) return;
        if (changed === null) return void timer();                        // no watch there: a look now and then
        if (changed.includes(real) || changed.includes(dir)) this.look(cx);
      }
    });
  }

  /** The disk read again: a real change shown (nothing unsaved) or asked about (the bar); a touch is no change. */
  look(cx) {
    if (!this.state || this.busy) return;
    cx.spawn(async (cx) => {
      const now = await readTextFile(String(this.real), { on: this.what.on }).catch(() => undefined);
      if (!this.state || now === undefined || now === this.disk || now === this.newer) return;
      if (now === null && !this.dirty) this.vanish();
      else if (now === null || this.dirty && withEnds(this.state.value(), now) !== now) this.newer = now;
      else {                                       // nothing unsaved, or what was typed is what is there now
        if (!this.dirty) this.put(now);
        Object.assign(this, { disk: now, dirty: false });
        this.dropDraft();
        this.publish();
        this.onSaved?.(cx);
      }
      cx.notify();
    });
  }

  /** Cmd+F: the find bar over the editor's top right, what is selected (one line) its query, typing replacing it. */
  openFind(cx) {
    if (!this.query) {
      this.query = InputState.new({ placeholder: "Find" });
      this.query.on("change", (_e, cx) => {
        this.search(true);
        cx.notify();
      });
      this.query.on("submit", (e, cx) => this.step(Boolean(e.shift), cx));
    }
    const { start, end } = this.state.selected_range(), picked = this.state.value().slice(start, end);
    if (picked && picked.length <= 200 && !picked.includes("\n")) this.query.set_value(picked);
    this.finder = { matches: [], at: -1, from: start };
    this.search(false);
    this.query.focus();
    this.query.set_selected_range({ start: 0, end: this.query.value().length });
    cx.notify();
  }

  /** The query's matches anew; TYPED: the first from where the find opened selected, as VS Code finds as you type. */
  search(typed) {
    const finder = /** @type {NonNullable<Editing["finder"]>} */ (this.finder);
    finder.matches = findAll(this.state.value(), this.query.value());
    finder.at = typed ? this.select(nextMatch(finder.matches, finder.from))
      : finder.matches.findIndex(([start, end]) => {
        const chosen = this.state.selected_range();
        return start === chosen.start && end === chosen.end;
      });
  }

  /** Enter (BACK: Shift+Enter, ↑): the next or the previous match selected, round past either end. */
  step(back, cx) {
    const finder = this.finder;
    if (!finder?.matches.length) return;
    const n = finder.matches.length;
    finder.at = this.select(finder.at < 0 ? nextMatch(finder.matches, this.state.selected_range().start, back)
      : (finder.at + (back ? n - 1 : 1)) % n);
    cx.notify();
  }

  /** Match N selected in the editor: N. @param {number} n */
  select(n) {
    const match = this.finder?.matches[n];
    if (match) this.state.set_selected_range({ start: match[0], end: match[1] });
    return n;
  }

  /** Esc: the bar closed, the keys back in the editor, the cursor on the match. */
  closeFind(cx) {
    this.finder = null;
    this.state?.focus();
    cx.notify();
  }

  /** Its watch, timers and states given up (the tab closed, another file in it). */
  release() {
    this.live = false;
    this.watching?.cancel();
    this.ticking?.cancel();
    if (this.pending) {
      this.pending.cancel();
      this.keepDraft();
    }
    this.state?.release();
    this.query?.release();
  }

  /** Show in Agent: the Agent panel on this settings file's agent, Permissions (its settings' section) open. */
  showAgent() {
    const agent = String(this.real ?? this.what.path).includes("/.codex/") ? "codex" : "claude";
    openAgentPanel({ agent, section: "permissions" });
  }

  /** The text as the editor has it now (Markdown drawn beside it). */
  text() {
    return this.state?.value() ?? "";
  }

  /** A quiet line over the editor (edit.html's .over): an icon, WORDS, the ACTS at its end. */
  line(t, id, name, words, ...acts) {
    return h_flex().id(id).flex_none().min_h(36).pl(16).pr(8).py(4).gap(8).items_center().bg(t.chrome)
      .border_b(1).border_color(t.border).text_size(12).text_color(t.muted)
      .child(icon(name, 14).text_color(t.dim)).child(div().flex_1().min_w(0).child(words)).children(acts);
  }

  /** The lines over the editor (an agent's settings file, why it is read only, the disk changed, what went wrong),
   * the editor under them, its find bar over its top right. */
  render(t, code) {
    if (this.loading) return div().p(16).text_size(12).text_color(t.dim).child("Loading…");
    return v_flex().size_full().min_h(0).min_w(0)
      .when(this.settings, (e) => e.child(this.line(t, "edit-settings", "settings", SETTINGS, actButton(t,
        "edit-agent", "Show in Agent", "plain", true, () => this.showAgent()))))
      .when(Boolean(this.why) && Boolean(this.state), (e) => e.child(this.line(t, "edit-why", "eye",
        WHY[/** @type {keyof typeof WHY} */ (this.why)])))
      .when(this.newer !== undefined, (e) => e.child(this.line(t, "edit-disk", "refresh-cw", this.newer === null
        ? "Deleted on disk while you were editing" : "Changed on disk while you were editing",
      actButton(t, "edit-reload", "Reload", "raised", true, (cx) => this.reload(cx)),
      actButton(t, "edit-keep", "Keep mine", "raised", true, (cx) => this.keep(cx)))))
      .when(this.why === "binary", (e) => e.child(div().px(16).py(12).text_size(12).text_color(t.dim)
        .child(WHY.binary)))
      .when(Boolean(this.note), (e) => e.child(div().px(16).py(12).text_size(12).text_color(t.ansi1)
        .child(this.note ?? "")))
      .when(Boolean(this.state), (e) => e.child(div().id("edit-room").flex_1().min_h(0).min_w(0).relative()
        .font_family(code).on_size_change((size, cx) => {
          if (Math.abs(size.width - this.width) < 1) return;
          this.width = size.width;
          cx.notify();
        })
        .child(Editor.new(this.state).size_full())
        .when(Boolean(this.finder), (e) => e.child(this.findBar(t, code)))));
  }

  /** The find bar (edit.html's .find): the query, the count, ↑ ↓ and ×; Esc closes it. Across a narrow editor. */
  findBar(t, code) {
    const finder = /** @type {NonNullable<Editing["finder"]>} */ (this.finder), narrow = this.width < NARROW;
    return h_flex().id("edit-find").absolute().top(8).right(narrow ? 8 : 14).when(narrow, (e) => e.left(8)).p(4)
      .gap(2).items_center().rounded(8).border_1().border_color(t.border).bg(t.popover ?? t.raised).shadow_lg()
      .on_key_down((e, cx) => {
        if (e.key !== "escape") return;
        cx.stop_propagation();
        this.closeFind(cx);
      })
      .child(h_flex().when(!narrow, (e) => e.w(FIND)).when(narrow, (e) => e.flex_1()).min_w(0).h(26).px(8)
        .items_center().rounded(6).border_1().border_color(t.border).bg(t.canvas)
        .child(Input.new(this.query).flex_1().h_full().font_family(code).text_size(12).text_color(t.foreground)))
      .child(div().flex_none().px(8).text_size(12).text_color(t.muted)
        .child(findCount(finder.at, finder.matches, this.query.value())))
      .child(iconButton(t, "edit-find-up", "chevron-up", "Previous (⇧↩)", (cx) => this.step(true, cx)))
      .child(iconButton(t, "edit-find-down", "chevron-down", "Next (↩)", (cx) => this.step(false, cx)))
      .child(iconButton(t, "edit-find-close", "x", "Close (Esc)", (cx) => this.closeFind(cx), { size: 12 }));
  }
}

/** The offset LINE (from 1) starts at in TEXT; 0 without one. @param {string} text @param {number | undefined} line */
function lineStart(text, line) {
  let at = 0;
  for (let n = 1; n < (line ?? 1) && at >= 0; n++) at = text.indexOf("\n", at) + 1 || -1;
  return at < 0 ? text.length : at;
}
