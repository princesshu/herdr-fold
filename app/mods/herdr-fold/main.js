// @ts-check
// herdr-fold for the Herdr app, the TUI sidebar's counterpart: the space's changes, a commit message Claude or Codex
// writes, and a sync that loses nothing. The git work runs on the space's machine, with core/'s code (helper.js).
import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, Scrollbar, v_virtual_list } from "gpui-base";
import { spaces, panes, focused, exec, hc, home, watchFolder, nextCommand, theme, settings, layout, props, closeOverlay,
  run as command } from "herdr";
import { COMMIT_MESSAGE, GIT } from "./helper.js";
import { background, changedFiles, diffRows, panelToggle, pythonCommand, secretQuestion, syncLabel, written }
  from "./logic.js";

const REFRESH = 10000;             // ms between two looks when no folder change says so (another machine's space)
const POLL = 1500;                 // ms between two looks at the message being written
const WRITING = 6 * 60 * 1000;     // ms the message may take: both AIs, each asked twice
const LINES = 1500;                // a diff's lines shown at most

/** The focused pane's folder, and the machine its space is on (null: this one). */
function place() {
  const space = spaces().find((s) => s.active), now = focused();
  const pane = now?.pane ? panes().find((p) => p.pane === now.pane) : null;
  return { cwd: pane?.cwd || space?.folder || null, on: space?.machine ?? null };
}

/** @param {{ code: number, stdout: string, stderr: string }} out */
const lastLine = (out) => (out.stderr || out.stdout).trim().split("\n").pop() || `exit ${out.code}`;

/** @param {unknown} e */
const said = (e) => String(e instanceof Error ? e.message : e);

/** ARGV run in ROOT on machine ON. @param {string[]} argv @param {string} root @param {string | null} on */
const run = (argv, root, on) => exec(argv[0], argv.slice(1), { cwd: root, on });

/** The Python core/'s code runs with on each machine (null: this one), asked once; an unreachable one is asked again.
 * @type {Map<string | null, Promise<string>>} */
const pythons = new Map();

/** @param {string | null} on */
function pythonOn(on) {
  let found = pythons.get(on);
  if (!found) {
    pythons.set(on, (found = findPython(on)));
    found.catch(() => pythons.delete(on));
  }
  return found;
}

/** python3, or on Windows (its shell knows %OS%) the Python herdr-fold's python.ps1 names there, else python.
 * @param {string | null} on */
async function findPython(on) {
  const shell = await hc(["exec", ...(on ? ["--on", on] : []), "echo %OS%"]);
  if (shell.code !== 0) throw new Error(lastLine(shell));
  if (!shell.stdout.includes("Windows_NT")) return "python3";
  const found = await exec("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    ".config/herdr-fold/python.ps1"], { cwd: on ? undefined : home(), on });
  return (found.code === 0 && found.stdout.trim()) || "python";
}

/** core/'s SOURCE run with ARGS where the repository is: its JSON answer.
 * @param {string} source @param {string[]} args @param {string} root @param {string | null} on */
async function python(source, args, root, on) {
  const out = await run([...pythonCommand(await pythonOn(on)), source, ...args], root, on);
  if (out.code !== 0) throw new Error(lastLine(out));
  return JSON.parse(out.stdout);
}

/** With nothing staged, every change staged, as a commit takes them (core/git.py's stage_all).
 * @param {string} root @param {string | null} on */
async function stage(root, on) {
  const staged = await python(GIT, ["stage", root], root, on);
  if (!staged.ok) throw new Error(staged.advice);
}

export default class HerdrFold extends View {
  init(_props, cx) {
    if ((this.launcher = props()?.overlay)) {     // Cmd+Shift+G (mod.open): the right panel at herdr-fold, then gone
      for (const [name, args] of panelToggle(layout())) command(name, args);
      return void closeOverlay(this.launcher);
    }
    this.files = []; this.rows = []; this.status = null; this.message = "";
    this.input = InputState.new({ placeholder: "Commit message" });
    this.input.on("change", (_e, cx) => {
      const had = Boolean(this.message.trim());
      this.message = this.input.value();
      if (had !== Boolean(this.message.trim())) cx.notify();
    });
    this.input.on("submit", (_e, cx) => this.commit(cx));
    this.refresh(cx);
    cx.timer.every(REFRESH, (cx) => this.refresh(cx));
    cx.spawn(async (cx) => {
      for (;;) {                                  // "herdr-fold.<command>": a bound key, or herdr-app do
        const command = await nextCommand();
        if (command === "write") this.write(cx);
        else if (command === "commit") this.commit(cx);
        else if (command === "sync") this.sync(cx);
      }
    });
  }

  /** The repository of the focused pane, its changes and how far it is from its upstream, from core/git.py. */
  refresh(cx) {
    if (this.loading || this.busy) return;
    const here = place(), key = JSON.stringify(here);
    if (key !== this.key) {
      Object.assign(this, { key, root: null, files: [], rows: [], status: null, open: null, note: null, asked: null });
    }
    if (!here.cwd) return;
    this.loading = true;
    cx.spawn(async (cx) => {
      try {
        const top = await run(["git", "rev-parse", "--show-toplevel"], here.cwd, here.on);
        if (key !== this.key) return;
        if (top.code !== 0) return void (this.note = "Not a git repository");
        const root = top.stdout.trim(), status = await python(GIT, ["status", root], root, here.on);
        if (key !== this.key) return;
        Object.assign(this, { root, on: here.on, status, files: changedFiles(status) });
        this.watch(cx);
        if (!this.files.some((f) => f.path === this.open)) this.open = this.files[0]?.path ?? null;
        if (this.open) await this.load(this.open, key);
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.loading = false;
        cx.notify();
      }
    });
  }

  /** A folder change on this machine looks again at once (another machine's space waits for REFRESH). */
  watch(cx) {
    if (this.on || this.watched === this.root) return;
    const root = this.watched = this.root;
    cx.spawn(async (cx) => {
      try {
        while (this.watched === root) {
          await watchFolder(root);
          if (this.watched === root) this.refresh(cx);
        }
      } catch {
        this.watched = null;
      }
    });
  }

  /** PATH's diff, from core/git.py: shown unasked, it runs nothing the repository's config names. */
  async load(path, key) {
    const { text, error } = await python(GIT, ["diff", this.root, path], this.root, this.on);
    if (key !== this.key || path !== this.open) return;
    const lines = text.replace(/\n$/, "").split("\n"), hunk = lines.findIndex((l) => l.startsWith("@@"));
    this.rows = diffRows(hunk < 0 ? [error ?? "No text diff"] : lines.slice(hunk, hunk + LINES));
  }

  pick(path, cx) {
    this.open = path;
    this.rows = [];
    const key = this.key;
    cx.spawn(async (cx) => {
      await this.load(path, key).catch((e) => {
        if (key === this.key) this.note = said(e);
      });
      cx.notify();
    });
    cx.notify();
  }

  /** WORK while LABEL shows, one at a time; what it returns is the note, then a fresh look. */
  act(cx, label, work) {
    if (this.busy || !this.root) return;
    const key = this.key;
    this.busy = label;
    this.note = null;
    cx.spawn(async (cx) => {
      try {
        const note = await work(cx);
        if (key === this.key) this.note = note;
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.busy = null;
        this.refresh(cx);
        cx.notify();
      }
    });
    cx.notify();
  }

  /** The staged changes committed, or every change with none staged (core/git.py); files named like secrets are asked
   * about first, as the TUI sidebar does: Commit again. */
  commit(cx) {
    const message = this.message.trim(), asked = this.asked;
    if (!message) return;
    this.asked = null;
    this.act(cx, "Committing…", async () => {
      const { root, on } = this;
      await stage(root, on);
      const question = secretQuestion((await python(COMMIT_MESSAGE, ["secrets", root], root, on)).secret_looking);
      if (question && question !== asked) {
        this.asked = question;
        return question;
      }
      const done = await python(GIT, ["commit", root, message], root, on);
      if (!done.ok) throw new Error(done.advice);
      this.input.set_value("");
      this.message = "";
      return null;
    });
  }

  /** The message core/commit_message.py has Claude or Codex write for what a commit takes, in the background. */
  write(cx) {
    this.act(cx, "Writing the message…", async (cx) => {
      const { root, on, key } = this;
      await stage(root, on);
      const job = background(await pythonOn(on), COMMIT_MESSAGE, ["write", root]);
      const prepared = await run(job.prepare, root, on);
      if (prepared.code !== 0) throw new Error(lastLine(prepared));
      const folder = prepared.stdout.trim();
      /** @type {string | null} the core's terminal the job runs in: stopped once its answer is read */
      let terminal = null;
      try {
        const started = await hc(job.start(folder, root, on));
        if (started.code !== 0) throw new Error(lastLine(started));
        terminal = JSON.parse(started.stdout).address;
        for (let waited = 0; waited < WRITING; waited += POLL) {
          await new Promise((done) => cx.timer.after(POLL, () => done(null)));
          const out = await run(job.poll(folder), root, on);
          if (out.code === 3) continue;
          if (out.code !== 0) throw new Error(`No message: ${lastLine(out)}`);
          const answer = written(JSON.parse(out.stdout));
          if (answer.message && key === this.key) {
            this.input.set_value(answer.message);
            this.message = answer.message;
          }
          return answer.note;
        }
        throw new Error("No message: the AIs took longer than six minutes");
      } finally {
        await run(job.clear(folder), root, on);
        if (terminal) await hc(["kill", terminal]);
      }
    });
  }

  sync(cx) {
    this.act(cx, "Syncing…", async () => {
      const done = await python(GIT, ["sync", this.root], this.root, this.on);
      return done.ok ? null : done.advice;
    });
  }

  render(cx) {
    if (this.launcher) return div();
    if (JSON.stringify(place()) !== this.key) this.refresh(cx);
    const t = theme();
    return v_flex().id("herdr-fold").size_full().min_h(0).rounded(10).overflow_hidden().bg(t.background).border_1()
      .border_color(t.border).text_color(t.foreground).text_size(13)
      .child(this.header(t)).child(this.list(t)).child(this.diff(t))
      .when(Boolean(this.note && this.root), (e) => e.child(div().px(10).py(6).text_size(11).text_color(t.ansi1)
        .child(this.note)))
      .child(this.footer(t));
  }

  get ready() {
    return Boolean(this.root && !this.busy && !this.loading);
  }

  header(t) {
    return h_flex().h(42).flex_none().px(14).gap(8).items_center().border_b(1).border_color(t.border)
      .child(div().font_semibold().child("Changes"))
      .child(div().px(5).py(1).rounded(4).border_1().border_color(t.border).text_size(10).text_color(t.muted)
        .child(`${this.files.length} files`))
      .child(div().flex_1())
      .child(button(t, "sync", syncLabel(this.status), this.ready, false, (cx) => this.sync(cx)));
  }

  list(t) {
    const empty = this.loading ? "Loading changes…" : this.root ? "No uncommitted changes" : this.note || "No folder";
    return v_flex().id("changed").flex_none().h(Math.min(200, Math.max(44, this.files.length * 28 + 12)))
      .overflow_y_scrollbar().p(6).border_b(1).border_color(t.border)
      .children(this.files.map((f) => this.file(t, f)))
      .when(!this.files.length, (e) => e.child(div().p(8).text_color(t.dim).child(empty)));
  }

  file(t, { path, code }) {
    const parts = path.split("/"), name = parts.pop();
    const color = code === "A" || code === "?" ? t.ansi2 : code === "D" || code === "U" ? t.ansi1 : t.blocked;
    return h_flex().id(`file-${path}`).h(28).flex_none().px(8).gap(8).items_center().rounded(7).cursor_pointer()
      .when(this.open === path, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover)).tooltip(path)
      .on_click((_e, cx) => this.pick(path, cx))
      .child(div().w(14).text_size(11).text_color(color).child(code === "?" ? "A" : code))
      .child(h_flex().flex_1().min_w(0)
        .child(div().text_color(t.dim).truncate().child(parts.length ? `${parts.join("/")}/` : ""))
        .child(div().min_w(0).truncate().child(name)));
  }

  diff(t) {
    const row = ({ kind, number, text }) => kind === "@"
      ? div().w_full().px(12).h(20).flex_none().truncate().bg(t.raised).text_color(t.dim).child(text)
      : h_flex().w_full().h(20).flex_none().gap(10)
        .when(kind === "+", (e) => e.bg(t.ansi2 + "18")).when(kind === "-", (e) => e.bg(t.ansi1 + "18"))
        .child(div().w(30).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
        .child(div().flex_1().min_w(0).truncate().child(text));
    return div().flex_1().min_h(0).relative().font_family(settings().font_family ?? "JetBrains Mono").text_size(11)
      .child(v_virtual_list("diff", this.rows.length, 20, (i) => String(i),
        (range) => this.rows.slice(range.start, range.end).map(row)).size_full())
      .child(Scrollbar.vertical("diff").viewport_from_layout().absolute().inset_0());
  }

  footer(t) {
    const commit = this.ready && Boolean(this.message.trim());
    return h_flex().flex_none().p(10).gap(8).border_t(1).border_color(t.border)
      .child(div().id("message").flex_1().min_w(0).h(32).px(10).flex().items_center().rounded(8).border_1()
        .border_color(t.border).cursor_text()
        .child(Input.new(this.input).h_full().text_size(12).text_color(t.foreground)))
      .child(button(t, "write", "✦", this.ready, false, (cx) => this.write(cx)))
      .child(button(t, "commit", this.busy ?? (this.asked ? "Commit anyway" : "Commit"), commit, true,
        (cx) => this.commit(cx)));
  }
}

/** A button: SOLID for the one Enter presses too, faint while it cannot be pressed. */
function button(t, id, label, enabled, solid, onClick) {
  return div().id(id).h(32).px(12).flex().items_center().rounded(8).text_size(12)
    .bg(enabled && solid ? t.solid : t.raised).text_color(!enabled ? t.dim : solid ? t.solid_foreground : t.foreground)
    .when(enabled, (e) => e.cursor_pointer().on_click((_e, cx) => onClick(cx))).child(label);
}
