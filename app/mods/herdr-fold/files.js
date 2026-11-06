// @ts-check
// The right panel's Files, as the TUI sidebar's: the space's folder as a tree read on its machine (core/tree.py),
// Catppuccin Icons' files and folders, git's letter on a changed file and a dot on a folder holding changes.
import { div } from "gpui-kit";
import { h_flex, v_flex, Input, InputState } from "gpui-base";
import { home, setShared, shared, spaces, run as command } from "herdr";
import { FILEOPS, TREE } from "./helper.js";
import { changeColor, changeName, fileIcon, fileRows, folderIcon, letter, said } from "./logic.js";
import { END, fileMark, GAP, icon, iconButton, small } from "./parts.js";
import { Menus } from "./menus.js";
import { followFolder } from "./panel.js";
import { showPreview } from "./preview.js";

const HIDDEN = "herdr-fold.files-hidden";   // hidden files shown or not, kept (shared), as the TUI keeps its own
const LOOK = 10000;                          // ms between two looks at another machine's folder
const LIMIT = 1000;                          // a folder's entries drawn at most (every row is drawn), the rest counted
const ROW = 26;
const INDENT = 12;                           // a level deeper in the tree
const NAMING = { "new-file": "File name", "new-folder": "Folder name", rename: "New name" };

/** PATH's folder, from the root ("" the root itself). @param {string} path */
const folderOf = (path) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");

export class FilesView {
  /** The active space's folder; PYTHON runs core/'s code on its machine (main.js's python).
   * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} python */
  constructor(python, cx) {
    this.python = python;
    this.menus = new Menus();
    /** @type {string | null} */
    this.key = null;
    /** @type {string | null} the space's folder */
    this.root = null;
    /** @type {string | null} its machine (null: this one) */
    this.on = null;
    /** @type {Record<string, { entries: import("./logic.js").Entry[], more: number }>} each folder read, by its path */
    this.folders = {};
    /** @type {Set<string>} the open folders */
    this.open = new Set();
    /** @type {string | null} the file the preview tab shows */
    this.picked = null;
    /** @type {{ action: "new-file" | "new-folder" | "rename", path: string, input: any } | null} a name typed in its
     * row: a new file's or folder's in the folder PATH, or PATH's new one */
    this.naming = null;
    /** @type {string | null} the path Move to Trash asks about, on its row */
    this.asking = null;
    /** @type {string | null} what went wrong last */
    this.note = null;
    this.hidden = shared(HIDDEN) === true;
    this.loading = false;
    /** @type {string | null} the folder followed on this computer (panel.js's followFolder) */
    this.watched = null;
    cx.timer.every(LOOK, (cx) => this.on && this.look(cx));
    this.look(cx);
  }

  /** The active space's folder and its machine. */
  static here() {
    const space = spaces().find((s) => s.active);
    return { root: space?.folder ?? null, on: space?.machine ?? null };
  }

  /** The root and each open folder read again; another space's folder from its top, closed. */
  look(cx) {
    const here = FilesView.here(), key = JSON.stringify(here);
    if (key !== this.key) {
      Object.assign(this, { key, ...here, folders: {}, open: new Set(), picked: null, naming: null, asking: null,
        note: null, watched: null });
    }
    if (!this.root || this.loading) return void cx.notify();
    const { root, on } = this, asked = ["", ...this.open];
    this.loading = true;
    cx.spawn(async (cx) => {
      try {
        const answer = await this.python(TREE, ["list", root, ...(this.hidden ? ["--hidden"] : []), "--limit",
          String(LIMIT), ...asked], root, on);
        if (key !== this.key) return;
        this.folders = answer.folders;
        const listed = (path) => this.folders[folderOf(path)]?.entries.some((e) => e.dir && e.name === path.split("/")
          .pop());
        this.open = new Set([...this.open].filter(listed));          // a folder gone, or renamed, closes
        this.note = null;
        followFolder(this, (cx) => this.look(cx), cx);
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.loading = false;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** Folder PATH opened (read then) or closed. @param {string} path */
  toggle(path, cx) {
    if (this.open.delete(path)) return void cx.notify();
    this.open.add(path);
    this.look(cx);
  }

  /** File PATH shown in the space's preview tab, its lines numbered, as the TUI opens it. @param {string} path */
  pick(path, cx) {
    this.picked = path;
    showPreview({ kind: "file", path, root: /** @type {string} */ (this.root), on: this.on });
    cx.notify();
  }

  /** What a right click on ROW offers, as the TUI's menu: a new file or folder where it is, a rename, its path, the
   * Trash; a folder a new workspace in it. @param {{ path: string, dir: boolean }} row */
  items({ path, dir }) {
    const folder = dir ? path : folderOf(path);
    return [{ label: "New File", act: (cx) => this.name("new-file", folder, cx) },
      { label: "New Folder", act: (cx) => this.name("new-folder", folder, cx) },
      { label: "Rename", act: (cx) => this.name("rename", path, cx) },
      { label: "Copy Path", act: (cx) => this.copy(path, cx) },
      { label: "Move to Trash", act: (cx) => this.ask(path, cx) },
      ...(dir ? [{ label: "New Workspace", act: () => this.workspace(path) }] : [])];
  }

  /** A name typed in its row for ACTION: a new file or folder in folder PATH (opened), or PATH renamed.
   * @param {"new-file" | "new-folder" | "rename"} action @param {string} path */
  name(action, path, cx) {
    const input = InputState.new({ placeholder: NAMING[action] });
    if (action === "rename") input.set_value(path.split("/").pop() ?? "");
    input.on("submit", (_e, cx) => this.make(cx));
    Object.assign(this, { naming: { action, path, input }, asking: null });
    if (action !== "rename" && path && !this.open.has(path)) this.toggle(path, cx);
    cx.timer.after(0, () => input.focus());
    cx.notify();
  }

  /** The name typed made into a file or folder, or given, on the space's machine (core/fileops.py). */
  make(cx) {
    const naming = this.naming, root = this.root;
    const name = naming?.input.value().trim();
    if (!naming || !root || !name) return this.drop(cx);
    cx.spawn(async (cx) => {
      try {
        const done = await this.python(FILEOPS, [naming.action, root, naming.path, name], root, this.on);
        if (!done.ok) return void (this.note = done.advice);
        this.naming = null;
        if (naming.action === "new-file") this.pick(done.path, cx);
        this.look(cx);
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** Move to Trash asked about on PATH's row first, as Discard is. @param {string} path */
  ask(path, cx) {
    Object.assign(this, { asking: path, naming: null });
    cx.notify();
  }

  /** PATH to the Trash of its machine, as the TUI sends it. @param {string} path */
  trash(path, cx) {
    const root = /** @type {string} */ (this.root);
    this.asking = null;
    cx.spawn(async (cx) => {
      try {
        const done = await this.python(FILEOPS, ["trash", root, path], root, this.on);
        this.note = done.ok ? null : done.advice;
        this.look(cx);
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
    cx.notify();
  }

  /** PATH, as its machine writes it, on this computer's clipboard. @param {string} path */
  copy(path, cx) {
    cx.spawn(async (cx) => {
      try {
        const done = await this.python(FILEOPS, ["copy", `${this.root}/${path}`], home(), null);
        this.note = done.ok ? null : "No clipboard program on this computer";
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
  }

  /** A new workspace in folder PATH, on its machine, as the TUI's New Workspace makes one. @param {string} path */
  workspace(path) {
    command("space.new", { folder: `${this.root}/${path}`, machine: this.on ?? "" });
  }

  /** A name being typed or a question asked given up (Esc). */
  drop(cx) {
    Object.assign(this, { naming: null, asking: null });
    cx.notify();
  }

  /** Every folder closed. */
  collapse(cx) {
    this.open.clear();
    cx.notify();
  }

  /** Hidden files shown or not, kept for the next start. */
  toggleHidden(cx) {
    this.hidden = !this.hidden;
    setShared(HIDDEN, this.hidden);
    this.look(cx);
  }

  render(t, cx) {
    if (JSON.stringify(FilesView.here()) !== this.key) cx.timer.after(0, (cx) => this.look(cx));
    return this.draw(t);
  }

  /** The view as it is: its toolbar, the tree, what went wrong last. */
  draw(t) {
    return v_flex().id("files").size_full().min_h(0).text_color(t.foreground).text_size(13)
      .on_key_down((e, cx) => e.key === "escape" && this.drop(cx))
      .child(this.toolbar(t))
      .child(this.root ? this.tree(t) : div().p(16).text_size(12).text_color(t.dim).child("No folder"))
      .when(Boolean(this.note), (e) => e.child(div().px(12).py(6).text_size(11).text_color(t.ansi1)
        .child(this.note ?? "")));
  }

  /** The folder's name, and as VS Code's Explorer has them: New File, New Folder, Refresh, Collapse; hidden files. */
  toolbar(t) {
    const name = this.root?.split(/[\\/]/).pop() ?? "";
    return h_flex().h(36).flex_none().px(8).gap(GAP).items_center()
      .child(div().flex_1().min_w(0).truncate().text_size(11).font_semibold().text_color(t.muted)
        .child(name.toUpperCase()))
      .child(iconButton(t, "files-new-file", "file-plus", "New File", (cx) => this.name("new-file", "", cx)))
      .child(iconButton(t, "files-new-folder", "folder-plus", "New Folder", (cx) => this.name("new-folder", "", cx)))
      .child(iconButton(t, "files-refresh", "refresh-cw", "Refresh", (cx) => this.look(cx)))
      .child(iconButton(t, "files-collapse", "chevrons-down-up", "Collapse Folders", (cx) => this.collapse(cx)))
      .child(iconButton(t, "files-hidden", this.hidden ? "eye" : "eye-off",
        this.hidden ? "Hide Hidden Files" : "Show Hidden Files", (cx) => this.toggleHidden(cx)));
  }

  /** The rows, a new name's typed in its folder's first place. */
  tree(t) {
    const rows = /** @type {any[]} */ (fileRows(this.folders, this.open));
    const naming = this.naming;
    if (naming && naming.action !== "rename") {
      const at = naming.path ? rows.findIndex((r) => r.path === naming.path) + 1 : 0;
      const depth = naming.path ? (rows[at - 1]?.depth ?? -1) + 1 : 0;
      rows.splice(at, 0, { naming: true, depth, dir: naming.action === "new-folder" });
    }
    const draw = (r) => (r.naming ? this.newRow(t, r) : r.path === null ? this.moreRow(t, r) : this.row(t, r));
    return v_flex().id("files-tree").flex_1().min_h(0).overflow_y_scrollbar().px(4).pb(6).children(rows.map(draw));
  }

  /** An entry's row, as the TUI's: a folder's arrow, its icon, its name in git's color (what git ignores faint); a
   * changed file's letter, a folder's dot; its name typed in place for a rename, Move to Trash asked about here. */
  row(t, r) {
    const { path, name, dir, depth, open, mark, ignored } = r;
    const color = ignored ? t.dim : mark ? changeColor(t, mark) : t.foreground;
    const renaming = this.naming?.action === "rename" && this.naming.path === path, asking = this.asking === path;
    return h_flex().id(`file-${path}`).h(ROW).flex_none().pl(6 + depth * INDENT).pr(8).gap(6).items_center()
      .rounded(6).cursor_pointer().when(this.picked === path, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
      .tooltip(path)
      .on_click((_e, cx) => (dir ? this.toggle(path, cx) : this.pick(path, cx)))
      .on_mouse_down("right", () => this.menus.open(this.items(r)))
      .child(div().w(12).flex_none().when(dir, (e) => e.child(icon(open ? "chevron-down" : "chevron-right", 12))))
      .child(fileMark(dir ? folderIcon(open) : fileIcon(name)))
      .child(renaming ? this.field(t) : div().flex_1().min_w(0).truncate().text_color(color).child(name))
      .when(asking, (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi1).child("Move to Trash?"))
        .child(h_flex().gap(GAP)
          .child(small(t, `${path}-keep`, "Cancel", "Keep it", true, (cx) => this.drop(cx)))
          .child(small(t, `${path}-trash`, "Move", "Move to Trash", true, (cx) => this.trash(path, cx)))))
      .when(!asking && Boolean(mark), (e) => e.child(div().id(`${path}-mark`).w(END).flex_none().text_center()
        .text_size(dir ? 9 : 11).text_color(color).tooltip(changeName(/** @type {string} */ (mark)))
        .child(dir ? "●" : letter(/** @type {string} */ (mark)))));
  }

  /** The row a new file's or folder's name is typed in, where it will be. */
  newRow(t, { depth, dir }) {
    return h_flex().id("file-new").h(ROW).flex_none().pl(6 + depth * INDENT).pr(8).gap(6).items_center()
      .child(div().w(12).flex_none())
      .child(fileMark(dir ? folderIcon(false) : fileIcon(this.naming?.input.value() ?? "")))
      .child(this.field(t));
  }

  /** A very full folder's last row: how many it leaves out, as the TUI says it. */
  moreRow(t, { depth, more }) {
    return div().h(ROW).flex_none().pl(24 + depth * INDENT).flex().items_center().text_size(12).text_color(t.dim)
      .child(`… ${more} more`);
  }

  /** The name being typed: Enter makes it, Esc gives it up. */
  field(t) {
    return div().flex_1().min_w(0).h(22).px(6).flex().items_center().rounded(4).border_1().border_color(t.accent)
      .child(Input.new(this.naming?.input).h_full().text_size(12).text_color(t.foreground));
  }
}
