// @ts-check
// herdr-fold for the Herdr app, the TUI sidebar's Changes: staging, the message Claude or Codex writes, a commit that
// may push or sync after, the last commits; the git work runs on the space's machine, with core/'s code (helper.js).
import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, Scrollbar, v_virtual_list } from "gpui-base";
import { spaces, panes, focused, exec, hc, home, watchFolder, nextCommand, theme, settings, layout, props, closeOverlay,
  shared, setShared, run as command } from "herdr";
import { COMMIT_MESSAGE, FILEOPS, GIT } from "./helper.js";
import { afterCommit, background, changedFiles, commitMode, commitRows, diffRows, MODES, panelToggle, pythonCommand,
  rowActions, secretQuestion, syncLabel, written } from "./logic.js";

const REFRESH = 10000;             // ms between two looks when no folder change says so (another machine's space)
const POLL = 1500;                 // ms between two looks at the message being written
const WRITING = 6 * 60 * 1000;     // ms the message may take: both AIs, each asked twice
const LINES = 1500;                // a diff's lines shown at most
const MODE = "herdr-fold.commit_mode", GRAPH = "herdr-fold.graph_folded";    // kept by the app (shared)
const BUSY = { stage: "Staging…", unstage: "Unstaging…", discard: "Discarding…" };
const ICONS = { stage: "+", unstage: "−", discard: "↶" };
const TIPS = { stage: "Stage", unstage: "Unstage", discard: "Discard changes" };

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

/** What the diff below shows, as a key: "staged:PATH", "changes:PATH" or "commit:HASH". @param {string} kind
 * @param {string} id */
const shown = (kind, id) => `${kind}:${id}`;

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

/** core/git.py's COMMAND on ROOT: null when it worked, else what to do. @param {string} command @param {string} root
 * @param {string | null} on @param {string[]} [rest] */
async function git(command, root, on, rest = []) {
  const done = await python(GIT, [command, root, ...rest], root, on);
  return done.ok ? null : done.advice;
}

/** With nothing staged, every change staged, as a commit takes them (core/git.py's stage_all).
 * @param {string} root @param {string | null} on */
async function stage(root, on) {
  const advice = await git("stage", root, on);
  if (advice) throw new Error(advice);
}

export default class HerdrFold extends View {
  init(_props, cx) {
    if ((this.launcher = props()?.overlay)) {     // Cmd+Shift+G (mod.open): the right panel at herdr-fold, then gone
      for (const [name, args] of panelToggle(layout())) command(name, args);
      return void closeOverlay(this.launcher);
    }
    this.files = []; this.rows = []; this.commits = []; this.status = null; this.message = "";
    this.mode = commitMode(shared(MODE));
    this.folded = shared(GRAPH) === true;
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

  /** The repository of the focused pane, its changes, how far it is from its upstream and its last commits, from
   * core/git.py. */
  refresh(cx) {
    if (this.loading || this.busy) return;
    const here = place(), key = JSON.stringify(here);
    if (key !== this.key) {
      Object.assign(this, { key, root: null, files: [], rows: [], commits: [], status: null, open: null, note: null,
        asked: null, confirm: null });
    }
    if (!here.cwd) return;
    this.loading = true;
    cx.spawn(async (cx) => {
      try {
        const top = await run(["git", "rev-parse", "--show-toplevel"], here.cwd, here.on);
        if (key !== this.key) return;
        if (top.code !== 0) return void (this.note = "Not a git repository");
        const root = top.stdout.trim(), status = await python(GIT, ["status", root], root, here.on);
        const { commits } = await python(GIT, ["graph", root], root, here.on);
        if (key !== this.key) return;
        Object.assign(this, { root, on: here.on, status, commits, files: changedFiles(status) });
        this.watch(cx);
        if (!this.showing(this.open)) this.open = this.first();
        if (this.open) await this.load(this.open, key);
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.loading = false;
        cx.notify();
      }
    });
  }

  /** Whether OPEN is still there to show: a change of the kind it was, or one of the last commits.
   * @param {string | null} open */
  showing(open) {
    if (!open || !this.status) return false;
    const at = open.indexOf(":"), kind = open.slice(0, at), id = open.slice(at + 1);
    if (kind === "commit") return this.commits.some((c) => c.hash === id);
    return (kind === "staged" ? this.status.staged : this.status.changes).some((f) => f.path === id);
  }

  /** The first change's key, a staged one before the rest, or null. */
  first() {
    const staged = this.status?.staged[0], change = this.status?.changes[0];
    return staged ? shown("staged", staged.path) : change ? shown("changes", change.path) : null;
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

  /** OPEN's diff, a file's or a commit's, from core/git.py: shown unasked, it runs nothing the repository's config
   * names. @param {string} open @param {string} key */
  async load(open, key) {
    const at = open.indexOf(":"), kind = open.slice(0, at), id = open.slice(at + 1);
    const { text, error } = await python(GIT, [kind === "commit" ? "show" : "diff", this.root, id], this.root, this.on);
    if (key !== this.key || open !== this.open) return;
    if (kind === "commit") return void (this.rows = error ? diffRows([error]) : commitRows(text).slice(0, LINES));
    const lines = text.replace(/\n$/, "").split("\n"), hunk = lines.findIndex((l) => l.startsWith("@@"));
    this.rows = diffRows(hunk < 0 ? [error ?? "No text diff"] : lines.slice(hunk, hunk + LINES));
  }

  /** @param {string} open */
  pick(open, cx) {
    this.open = open;
    this.rows = [];
    const key = this.key;
    cx.spawn(async (cx) => {
      await this.load(open, key).catch((e) => {
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

  /** A row's button: stage or unstage PATH, or once asked (a second press of Discard) undo its change, a new file
   * (CODE ?) sent to the Trash as the TUI sidebar does (core/fileops.py). @param {string} action @param {string} path
   * @param {string} code */
  change(action, path, code, cx) {
    if (action === "discard" && this.confirm !== path) {
      this.confirm = path;
      return void cx.notify();
    }
    this.confirm = null;
    this.act(cx, BUSY[action], async () => {
      if (action !== "discard" || code !== "?") return git(action, this.root, this.on, [path]);
      const done = await python(FILEOPS, ["trash", this.root, path], this.root, this.on);
      return done.ok ? null : done.advice;
    });
  }

  /** The staged changes committed, or every change with none staged (core/git.py), then pushed or synced as the mode
   * says; files named like secrets are asked about first, as the TUI sidebar does: Commit again. */
  commit(cx) {
    const message = this.message.trim(), asked = this.asked;
    if (!message) return;
    this.asked = null;
    this.act(cx, "Committing…", async (cx) => {
      const { root, on } = this, then = afterCommit(this.mode);
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
      if (!then) return null;
      this.busy = then === "push" ? "Pushing…" : "Syncing…";
      cx.notify();
      return git(then, root, on);
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
    this.act(cx, "Syncing…", () => git("sync", this.root, this.on));
  }

  /** @param {string} mode */
  choose(mode, cx) {
    this.mode = commitMode(mode);
    this.menu = false;
    setShared(MODE, this.mode);
    cx.notify();
  }

  render(cx) {
    if (this.launcher) return div();
    if (JSON.stringify(place()) !== this.key) this.refresh(cx);
    const t = theme();
    return v_flex().id("herdr-fold").size_full().min_h(0).rounded(10).overflow_hidden().bg(t.background).border_1()
      .border_color(t.border).text_color(t.foreground).text_size(13)
      .child(this.header(t)).child(this.list(t)).child(this.diff(t)).child(this.graph(t))
      .when(Boolean(this.note && this.root), (e) => e.child(div().px(10).py(6).text_size(11).text_color(t.ansi1)
        .child(this.note)))
      .when(Boolean(this.menu), (e) => e.child(this.modes(t)))
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

  /** The changes in two sections, as the TUI sidebar lists them: Staged Changes, then Changes. */
  list(t) {
    const empty = this.loading ? "Loading changes…" : this.root ? "No uncommitted changes" : this.note || "No folder";
    const staged = this.status?.staged ?? [], changes = this.status?.changes ?? [];
    const rows = (staged.length ? 1 + staged.length : 0) + (changes.length ? 1 + changes.length : 0);
    return v_flex().id("changed").flex_none().h(Math.min(240, Math.max(44, rows * 28 + 12)))
      .overflow_y_scrollbar().p(6).border_b(1).border_color(t.border)
      .when(staged.length > 0, (e) => e.child(section(t, "Staged Changes", staged.length))
        .children(staged.map((f) => this.file(t, "staged", f))))
      .when(changes.length > 0, (e) => e.child(section(t, "Changes", changes.length))
        .children(changes.map((f) => this.file(t, "changes", f))))
      .when(!rows, (e) => e.child(div().p(8).text_color(t.dim).child(empty)));
  }

  file(t, kind, { path, code }) {
    const parts = path.split("/"), name = parts.pop(), key = shown(kind, path);
    const color = code === "A" || code === "?" ? t.ansi2 : code === "D" || code === "U" ? t.ansi1 : t.blocked;
    const asking = kind === "changes" && this.confirm === path;
    return h_flex().id(`file-${key}`).h(28).flex_none().px(8).gap(8).items_center().rounded(7).cursor_pointer()
      .when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover)).tooltip(path)
      .on_click((_e, cx) => this.pick(key, cx))
      .child(div().w(14).text_size(11).text_color(color).child(code === "?" ? "A" : code))
      .child(h_flex().flex_1().min_w(0)
        .child(div().text_color(t.dim).truncate().child(parts.length ? `${parts.join("/")}/` : ""))
        .child(div().min_w(0).truncate().child(name)))
      .when(asking, (e) => e.child(div().text_size(11).text_color(t.ansi1).child("Discard?"))
        .child(small(t, `${key}-cancel`, "Cancel", "Keep the change", this.ready, (cx) => {
          this.confirm = null;
          cx.notify();
        })))
      .children(rowActions(kind, code).map((action) => small(t, `${key}-${action}`,
        asking && action === "discard" ? "Discard" : ICONS[action],
        action === "discard" && code === "?" ? "Move to the Trash" : TIPS[action], this.ready,
        (cx) => this.change(action, path, code, cx))));
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

  /** The last commits, as the TUI sidebar's Graph: HEAD's marked, each with its branches and tags; a click shows its
   * diff above. Folded and opened by its heading, kept so. */
  graph(t) {
    const heading = h_flex().id("graph").h(28).flex_none().px(14).gap(6).items_center().cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_click((_e, cx) => {
        this.folded = !this.folded;
        setShared(GRAPH, this.folded);
        cx.notify();
      })
      .child(div().w(10).text_color(t.dim).child(this.folded ? "▸" : "▾"))
      .child(div().font_semibold().child("Graph"))
      .child(div().text_size(11).text_color(t.dim).child(String(this.commits.length)));
    const commit = ({ hash, subject, author, refs, head }) => {
      const key = shown("commit", hash);
      return h_flex().id(`commit-${hash}`).h(24).flex_none().px(8).gap(8).items_center().rounded(6).cursor_pointer()
        .when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover)).tooltip(`${hash} ${subject}`)
        .on_click((_e, cx) => this.pick(key, cx))
        .child(div().w(12).text_color(head ? t.accent : t.dim).child(head ? "◉" : "○"))
        .child(div().flex_1().min_w(0).truncate().child(subject))
        .children(refs.map((ref) => div().px(5).rounded(4).text_size(10).bg(t.raised).text_color(t.accent).child(ref)))
        .child(div().flex_none().text_size(11).text_color(t.dim).child(author));
    };
    return v_flex().flex_none().border_t(1).border_color(t.border).child(heading)
      .when(!this.folded && this.commits.length > 0, (e) => e.child(v_flex().id("commits").flex_none()
        .h(Math.min(150, this.commits.length * 24 + 8)).overflow_y_scrollbar().px(6).pb(6)
        .children(this.commits.map(commit))));
  }

  /** The Commit button's modes, opened by its arrow: a choice is kept for the next commit. */
  modes(t) {
    return v_flex().flex_none().p(6).gap(2).border_t(1).border_color(t.border).bg(t.raised)
      .children(Object.entries(MODES).map(([mode, label]) => h_flex().id(`mode-${mode}`).h(28).px(10).gap(8)
        .items_center().rounded(6).cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => this.choose(mode, cx))
        .child(div().w(12).text_color(t.accent).child(this.mode === mode ? "✓" : "")).child(label)));
  }

  footer(t) {
    const commit = this.ready && Boolean(this.message.trim());
    const label = this.busy ?? (this.asked ? `${MODES[this.mode]} anyway` : MODES[this.mode]);
    return h_flex().flex_none().p(10).gap(8).border_t(1).border_color(t.border)
      .child(div().id("message").flex_1().min_w(0).h(32).px(10).flex().items_center().rounded(8).border_1()
        .border_color(t.border).cursor_text()
        .child(Input.new(this.input).h_full().text_size(12).text_color(t.foreground)))
      .child(button(t, "write", "✦", this.ready, false, (cx) => this.write(cx)))
      .child(button(t, "commit", label, commit, true, (cx) => this.commit(cx)))
      .child(button(t, "mode", this.menu ? "▴" : "▾", this.ready, false, (cx) => {
        this.menu = !this.menu;
        cx.notify();
      }));
  }
}

/** A button: SOLID for the one Enter presses too, faint while it cannot be pressed. */
function button(t, id, label, enabled, solid, onClick) {
  return div().id(id).h(32).px(12).flex().items_center().rounded(8).text_size(12)
    .bg(enabled && solid ? t.solid : t.raised).text_color(!enabled ? t.dim : solid ? t.solid_foreground : t.foreground)
    .when(enabled, (e) => e.cursor_pointer().on_click((_e, cx) => onClick(cx))).child(label);
}

/** A row's own small button, saying what it does when the mouse rests on it. */
function small(t, id, label, tip, enabled, onClick) {
  return div().id(id).h(20).min_w(20).px(5).flex().items_center().justify_center().rounded(5).text_size(12)
    .text_color(enabled ? t.muted : t.dim).tooltip(tip)
    .when(enabled, (e) => e.cursor_pointer().hover((s) => s.bg(t.raised).text_color(t.foreground))
      .on_click((_e, cx) => {
        cx.stop_propagation();                          // the row's own click (its diff) stays out of it
        onClick(cx);
      }))
    .child(label);
}

/** A section's heading in the list, with how many files it holds. */
function section(t, title, count) {
  return h_flex().h(24).flex_none().px(8).gap(6).items_center().text_size(11).text_color(t.muted)
    .child(div().font_semibold().child(title)).child(div().text_color(t.dim).child(String(count)));
}
