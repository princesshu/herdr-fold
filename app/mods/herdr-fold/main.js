// @ts-check
// herdr-fold for the Herdr app, the TUI sidebar's Changes, Search and Issues; a diff, a commit or an issue opens in the
// space's preview tab (preview.js). It runs on the space's machine, with core/'s code (helper.js).
import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, Scrollbar, v_virtual_list } from "gpui-base";
import { spaces, panes, focused, exec, hc, home, nextCommand, theme, settings, layout, props, closeOverlay,
  shared, setShared, readTextFile, run as command } from "herdr";
import { COMMIT_MESSAGE, FILEOPS, GIT, SEARCH } from "./helper.js";
import { activeTerminal, afterCommit, background, branchLabel, changeColor, changeName, commitMode, excerpt, fileIcon,
  foldedSections, hovering, lastLine, launcher, letter, marked, MODES, panelRailed, panelToggle, pushOffer,
  pythonCommand, railFollow, rowActions, said, searchRows, searchSummary, secretQuestion, syncLabel, written }
  from "./logic.js";
import { button, chip, END, field, fileMark, GAP, icon, SLIDE, small } from "./parts.js";
import { Menus, menuPopup } from "./menus.js";
import { followFolder, giveBack, keptWidth, liveTabs, openRail, panelTrigger, rail, runPanel, TABS, tabsState,
  takeAppButtons, VIEW, VIEW_NAMES } from "./panel.js";
import { ConversationsView } from "./conversations.js";
import { FilesView } from "./files.js";
import { floatHead, floatPanel, sidebarTrigger, spacesFloat } from "./sidebar.js";
import { IssuesView, fixesLine } from "./issues.js";
import { markUnread, SpacesView } from "./spaces.js";
import { Preview, showPreview } from "./preview.js";
import { guide, styleguide } from "./styleguide.js";
import { standIn, TerminalFollower } from "./terminal.js";

const REFRESH = 10000;             // ms between two looks when no folder change says so (another machine's space)
const POLL = 1500;                 // ms between two looks at the message being written
const WRITING = 6 * 60 * 1000;     // ms the message may take: both AIs, each asked twice
const LINES = 1500;                // a hit's file's lines shown at most
const MODE = "herdr-fold.commit_mode", FOLDED = "herdr-fold.folded";   // kept (shared)
/** The view's commands a folded panel hands to a float of the view that shows them, as its rail opens one. */
const RAILED = { write: "changes", "commit-push": "changes", commit: "changes", sync: "changes", changes: "changes",
  search: "search", issues: "issues" };
const QUIET = 150;                 // ms after typing stops before the search runs (Enter: at once)
const FOUND = 1000;                // the hits a search brings at most (the count goes on)
const ABOVE = 12;                  // a hit's file shown from these lines above it
const BUSY = { stage: "Staging…", unstage: "Unstaging…", discard: "Discarding…" };
const TIPS = { stage: "Stage", unstage: "Unstage", discard: "Discard changes" };
const REMOTE = { sync: "Syncing…", pull: "Pulling…", push: "Pushing…" };
/** @type {Record<string, import("./icons.js").IconName>} */
const ACTION_ICONS = { stage: "plus", unstage: "minus", discard: "undo-2" };

/** The focused pane's folder, and the machine its space is on (null: this one). */
function place() {
  const space = spaces().find((s) => s.active), now = focused();
  const pane = now?.pane ? panes().find((p) => p.pane === now.pane) : null;
  return { cwd: pane?.cwd || space?.folder || null, on: space?.machine ?? null };
}

/** The code's font: the layout's (herdr-fold's is Menlo, as VS Code's), else the person's, else Menlo. */
const codeFont = () => /** @type {any} */ (layout())?.font ?? settings().font_family ?? "Menlo";

/** A row's key, the one chosen marked: "staged:PATH", "changes:PATH" or "commit:HASH". @param {string} kind
 * @param {string} id */
const shown = (kind, id) => `${kind}:${id}`;

/** ARGV run in ROOT on machine ON. @param {string[]} argv @param {string} root @param {string | null} on */
const TICK = 20000;               // ms: a wait's label redrawn this often, as the TUI's
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
    if ((this.launcher = launcher(props()))) {    // Cmd+Shift+G (mod.open): the right panel at herdr-fold, then gone
      runPanel(panelToggle(layout(), keptWidth()));
      return void closeOverlay(this.launcher);
    }
    const part = props()?.part;                   // the layout's terminal stack: its header, its stand-in
    if (part === "terminal") {
      this.terminal = new TerminalFollower();
      return void cx.timer.every(REFRESH, (cx) => this.terminal.look(cx));
    }
    if ((this.blank = part === "none")) return;
    if ((this.tabs = part === "panel-tabs")) return;     // the right panel's stack: its header, the group's tabs
    if (part === "menu") return void (this.popup = { overlay: props().overlay, items: props().items });
    if ((this.toggle = part === "panel-trigger")) return void takeAppButtons();   // the tab bar's right end
    if (part === "preview") return void (this.preview = new Preview(props().space, python));
    if ((this.trigger = part === "trigger")) return;    // left of the tabs: the folded sidebar's toggle
    if ((this.rail = part === "rail")) return;          // the right panel folded: its rail
    if (part === "float-head") return void (this.head = { name: props().name, overlay: props().overlay });
    if (part === "float") {                       // a folded side's panel, floating beside its rail
      this.float = { panel: props().panel, overlay: props().overlay, height: props().height, then: props().then };
      const { panel, overlay } = this.float;
      if (panel === "spaces") return void cx.timer.every(TICK, (cx) => cx.notify());     // its waits, a minute on
      if (panel === "conversations" || panel === "files") {
        const view = panel === "files" ? (this.files = new FilesView(python, cx))
          : (this.conversations = new ConversationsView(python, cx, overlay));
        return void cx.spawn(async (cx) => {
          for (;;) view.menus.answer(await nextCommand(), cx);                    // its right click's choices
        });
      }                                           // Search, Changes or Issues: the view below, that one only
    }
    if (part === "conversations") {               // the left sidebar's block: Cmd+Shift+R gives its filter the keys
      this.conversations = new ConversationsView(python, cx);
      return void cx.spawn(async (cx) => {
        for (;;) {
          const asked = await nextCommand();
          if (this.conversations.menus.answer(asked, cx)) continue;
          if (asked === "conversations") this.conversations.focus();
          else if (asked === "unread") markUnread();      // this block always shows: the key reaches it once
        }
      });
    }
    if (part === "spaces") return void (this.spaces = new SpacesView(python, cx));    // the sidebar's, the app's place
    if (part === "files") {                       // the right panel's Files, where the app's own was
      this.files = new FilesView(python, cx);
      return void cx.spawn(async (cx) => {
        for (;;) this.files.menus.answer(await nextCommand(), cx);              // its right click's choices
      });
    }
    if (part === "styleguide") {                  // all of it, or its section props().section names (a picture of it)
      this.only = props()?.section ?? null;
      return void (this.guide = guide(HerdrFold.prototype));
    }
    this.commits = []; this.status = null; this.message = ""; this.menus = new Menus();
    const kept = this.float?.panel ?? shared(VIEW);
    this.view = ["search", "issues"].includes(kept) ? kept : "changes";
    this.core = python;                           // the Issues view asks core/ through it
    this.issues = new IssuesView(this);
    this.switches = { case: false, word: false, regex: false };
    this.found = null; this.results = []; this.peek = null; this.peekRows = []; this.asking = 0;
    this.find = InputState.new({ placeholder: "Search" });
    this.find.on("change", (_e, cx) => this.later(cx));
    this.find.on("submit", (_e, cx) => this.search(cx));
    this.mode = commitMode(shared(MODE));
    /** @type {"push" | null} Cmd + Shift + C's mode, for its one commit */
    this.once = null;
    /** @type {string | null} Cmd + Shift + C's question with nothing to commit: a push of the commits ahead */
    this.offer = null;
    this.folded = foldedSections(shared(FOLDED));
    /** @type {string | null} the row or section the pointer is on (hovering's): its buttons shown */
    this.hovered = null;
    this.input = InputState.new({ placeholder: "Commit message" });
    this.input.on("change", (_e, cx) => {
      const had = Boolean(this.message.trim());
      this.message = this.input.value();
      if (this.message.trim()) this.offer = null;          // a message typed gives the push asked about up
      if (had !== Boolean(this.message.trim())) cx.notify();
    });
    this.input.on("submit", (_e, cx) => this.submit(cx));
    this.refresh(cx);
    cx.timer.every(REFRESH, (cx) => this.refresh(cx));
    cx.spawn(async (cx) => {
      for (;;) {                                  // "herdr-fold.<command>": a bound key, or herdr-app do
        const asked = await nextCommand();
        if (this.menus.answer(asked, cx) || this.float) continue;    // a float's menus only: the panel's copy has keys
        if (RAILED[asked] && panelRailed(layout())) openRail(RAILED[asked], null, null, asked);   // folded: it shows
        else this.dispatch(asked, cx);
      }
    });
  }

  /** A command of the view's ("herdr-fold.<command>": a bound key, herdr-app do, or the rail's for its float). */
  dispatch(asked, cx) {
    if (asked === "write") this.write(cx);
    else if (asked === "commit-push") this.commitPush(cx);
    else if (asked === "commit") this.commit(cx);
    else if (asked === "sync") this.sync(cx);
    else if (asked === "changes" || asked === "search" || asked === "issues") this.show(asked, cx);
    else if (asked === "styleguide") command("tab.new", { mod: "herdr-fold", props: { part: "styleguide" } });
  }

  /** The repository of the focused pane, its changes, how far it is from its upstream and its last commits, from
   * core/git.py. */
  refresh(cx) {
    if (this.loading || this.busy) return;
    const here = place(), key = JSON.stringify(here);
    if (key !== this.key) {
      Object.assign(this, { key, root: null, commits: [], status: null, open: null, note: null,
        asked: null, confirm: null, github: null, linked: null, head: null, once: null, offer: null });
      this.issues.reset();
      this.publish();
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
        const github = this.root === root ? this.github : (await python(GIT, ["github", root], root, here.on)).name;
        // the issue the next commit fixes, unlinked once a commit made anywhere closed it (core/commit_message.py)
        const settled = github ? await python(COMMIT_MESSAGE, ["settle", root, ...(this.head ? [this.head] : [])],
          root, here.on) : { linked: null, head: null };
        if (key !== this.key) return;
        Object.assign(this, { root, on: here.on, status, commits, github, linked: settled.linked,
          head: settled.head ?? this.head, offer: this.offer && pushOffer(status) });   // asked anew: pushed, changed
        if (this.view === "issues" && github && !this.issues.listing && !this.issues.asked) this.issues.load(cx);
        followFolder(this, (cx) => this.refresh(cx), cx);   // another machine's space waits for REFRESH
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.loading = false;
        this.publish();
        const then = this.float?.then;
        if (then && this.root) cx.timer.after(0, (cx) => this.dispatch(then, cx));    // the rail's, once, now
        if (this.float) this.float.then = undefined;
        cx.notify();
      }
    });
  }

  /** What the panel's tabs (panel.js, another copy) show of it: Issues or not, and the changed files' count. */
  publish() {
    const told = { github: Boolean(this.github), changed: this.changed };
    if (JSON.stringify(shared(TABS)) !== JSON.stringify(told)) setShared(TABS, told);
  }

  /** The view the panel's tabs picked (VIEW, set in another copy) shown, once the render is over. */
  follow(cx) {
    const asked = shared(VIEW);
    if (this.due || !asked || asked === this.view) return;
    this.due = true;
    cx.timer.after(0, (cx) => {
      this.due = false;
      this.show(/** @type {string} */ (asked), cx);
    });
  }

  /** The row KEY chosen, and WHAT it is (a change's diff, a commit) shown in the space's preview tab, as the TUI
   * sidebar opens it. @param {string} key @param {any} what */
  pick(key, what, cx) {
    this.open = key;
    showPreview({ ...what, root: this.root, on: this.on });
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

  /** A row's or section's button: stage or unstage FILES, or once ASKING (Discard pressed again) undo their changes,
   * a new file sent to the Trash as the TUI sidebar does (core/fileops.py). @param {string} action
   * @param {{ path: string, code: string }[]} files @param {string} asking */
  change(action, files, asking, cx) {
    if (action === "discard" && this.confirm !== asking) {
      this.confirm = asking;
      return void cx.notify();
    }
    this.confirm = null;
    this.act(cx, BUSY[action], async () => {
      if (action !== "discard") return git(action, this.root, this.on, files.map((f) => f.path));
      for (const { path, code } of files) {
        const advice = code !== "?" ? await git("discard", this.root, this.on, [path])
          : await python(FILEOPS, ["trash", this.root, path], this.root, this.on).then((d) => (d.ok ? null : d.advice));
        if (advice) return advice;
      }
      return null;
    });
  }

  /** The staged changes committed, or every change with none staged (core/git.py), then pushed or synced as the mode
   * says; files named like secrets are asked about first, as the TUI sidebar does: Commit again. */
  commit(cx) {
    const message = this.message.trim(), asked = this.asked;
    if (!message) return;
    this.asked = null;
    this.act(cx, "Committing…", async (cx) => {
      const { root, on } = this, then = afterCommit(this.once ?? this.mode);
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
      this.once = null;
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

  /** Commit and push in one step, as the TUI's Cmd + Shift + C: the message written into the field, and Commit & Push
   * for this one commit; Enter commits and pushes, the field changes it, ✦ writes another, Esc cancels. With nothing
   * to commit, the commits ahead are offered to push, as there: Enter or Push pushes them. */
  commitPush(cx) {
    if (this.busy || !this.root) return;            // as act(): a key never lost to a refresh under way
    if (!this.changed) {
      this.offer = pushOffer(this.status);
      this.note = this.offer ? null : "Nothing to commit";
      if (this.offer) this.input.focus();
      return void cx.notify();
    }
    this.once = "push";
    this.input.focus();
    this.write(cx);
  }

  /** Enter or the Commit button: the push Cmd + Shift + C asked about, else the commit. */
  submit(cx) {
    if (!this.offer) return this.commit(cx);
    this.offer = null;
    this.sync(cx, "push");
  }

  /** Cmd + Shift + C's commit or push given up (Esc): the message gone, the mode the kept one. */
  cancel(cx) {
    if (!(this.once || this.offer) || this.busy) return;
    Object.assign(this, { once: null, offer: null, message: "", note: null });
    this.input.set_value("");
    cx.notify();
  }

  /** The branch synced with its upstream (pulled, fast-forward only, then pushed), or only pulled or pushed (the
   * repository row's ⋯), as core/git.py does it. @param {"sync" | "pull" | "push"} [how] */
  sync(cx, how = "sync") {
    this.act(cx, REMOTE[how], () => git(how, this.root, this.on));
  }

  /** The view shown, kept for the next start; Search takes the keys. @param {string} view */
  show(view, cx) {
    this.view = ["search", "issues"].includes(view) ? view : "changes";
    setShared(VIEW, this.view);
    if (this.view === "search") this.find.focus();
    if (this.view === "issues" && !this.issues.listing) this.issues.load(cx);
    cx.notify();
  }

  /** The issue the next commit would fix, unlinked by its line's ×: the next commit fixes none. */
  unlink(cx) {
    const { root, on } = this;
    if (!root) return;
    this.linked = null;
    cx.spawn(async (cx) => {
      try {
        await python(COMMIT_MESSAGE, ["unlink", root], root, on);
      } catch (e) {
        this.note = said(e);
      } finally {
        cx.notify();
      }
    });
    cx.notify();
  }

  /** The search QUIET ms after the last key, unless another key came meanwhile. */
  later(cx) {
    const asked = ++this.asking;
    cx.timer.after(QUIET, (cx) => {
      if (asked === this.asking) this.search(cx);
    });
  }

  /** The query in the focused pane's folder, on its machine (core/search.py): an older answer is dropped. */
  search(cx) {
    const text = this.find.value(), here = place(), asked = ++this.asking;
    if (!text || !here.cwd) {
      Object.assign(this, { found: null, results: [], peek: null, peekRows: [], searching: false });
      return void cx.notify();
    }
    this.searching = true;
    this.searched = here;
    cx.spawn(async (cx) => {
      try {
        const found = await python(SEARCH, [here.cwd, JSON.stringify({ text, ...this.switches, limit: FOUND })],
          here.cwd, here.on);
        if (asked !== this.asking) return;
        Object.assign(this, { found, results: searchRows(found.hits), peek: null, peekRows: [] });
      } catch (e) {
        if (asked === this.asking) Object.assign(this, { found: { hits: [], total: 0, files: 0, error: said(e) },
        results: [], peek: null, peekRows: [] });
      } finally {
        if (asked === this.asking) this.searching = false;
        cx.notify();
      }
    });
    cx.notify();
  }

  /** HIT's file below the hits, from a few lines above it, its line marked; read on its machine. */
  reveal(hit, cx) {
    const key = `${hit.path}:${hit.line}`, { cwd, on } = this.searched;
    this.peek = key;
    this.peekRows = [];
    cx.spawn(async (cx) => {
      try {
        const text = await readTextFile(`${cwd}/${hit.path}`, { on });
        if (this.peek !== key) return;
        if (text === null) return void (this.peekRows = [{ text: "This file is no longer there" }]);
        const { start, lines } = excerpt(text, hit.line, ABOVE, LINES);
        this.peekRows = lines.map((line, i) => ({ number: start + i, text: line,
          spans: start + i === hit.line ? hit.spans : null }));
      } catch (e) {
        if (this.peek === key) this.peekRows = [{ text: said(e) }];
      } finally {
        cx.notify();
      }
    });
    cx.notify();
  }

  /** @param {string} mode */
  choose(mode, cx) {
    this.mode = commitMode(mode);
    this.once = null;
    setShared(MODE, this.mode);
    cx.notify();
  }

  /** As the layout goes (another shown, the app quitting): the app's own panel buttons back as they were. */
  async close() {
    if (this.toggle) giveBack();
  }

  render(cx) {
    if (this.terminal) {
      this.terminal.watch(cx);
      return div();
    }
    if (this.launcher) return div();
    const t = theme();
    if (this.blank) return standIn(t);
    if (this.tabs) return liveTabs(t);
    if (this.popup) return menuPopup(t, this.popup.overlay, this.popup.items);
    if (this.toggle) {
      this.followRail(cx);
      return panelTrigger(t);
    }
    if (this.rail) return rail(t, tabsState(), activeTerminal(layout()));
    if (this.head) {
      this.offRail(this.head.overlay, cx);
      return floatHead(t, this.head.name, this.head.overlay, []);
    }
    if (this.guide) return styleguide(this.guide, t, this.only);
    if (this.preview) {
      this.preview.watch(cx);
      return this.preview.render(t, codeFont());
    }
    const float = this.float;
    if (float && !["spaces", "conversations"].includes(float.panel)) this.offRail(float.overlay, cx);
    if (float?.panel === "spaces") return spacesFloat(t, float.overlay, float.height);
    if (this.conversations) return float ? floatPanel(t, "Conversations", float.overlay, float.height, [],
      this.conversations.render(t, cx)) : this.conversations.render(t, cx);
    if (this.spaces) return this.spaces.render(t, cx);
    if (this.files) return float ? floatPanel(t, "Files", float.overlay, undefined, [], this.files.render(t, cx))
      : this.files.render(t, cx);
    if (this.trigger) return sidebarTrigger(t);
    if (JSON.stringify(place()) !== this.key) this.refresh(cx);
    if (float) return floatPanel(t, VIEW_NAMES[this.view], float.overlay, undefined, [], this.panel(t));
    this.follow(cx);
    return this.panel(t);
  }

  /** A float of the right panel's rail (OVERLAY) closed once the panel opens again: its views are in it then.
   * @param {string} overlay */
  offRail(overlay, cx) {
    if (!panelRailed(layout())) cx.timer.after(0, () => closeOverlay(overlay));
  }

  /** The right panel shown as its width says, a drag's too (logic.js's railFollow): from the tab bar's toggle, which
   * every layout of herdr-fold's draws. */
  followRail(cx) {
    const commands = railFollow(layout());
    if (!commands.length || this.railing) return;
    this.railing = true;
    cx.timer.after(0, () => {
      for (const [name, args] of commands) command(name, args);
      this.railing = false;
    });
  }

  /** The view shown, under the stack's tabs (panel.js): Changes, Search, or Issues for a repository on GitHub (else
   * Changes). */
  panel(t) {
    const frame = v_flex().id("herdr-fold").size_full().min_h(0).text_color(t.foreground).text_size(13);
    if (this.view === "issues" && this.github) return frame.child(this.issues.render(t));
    if (this.view === "search") return frame.child(this.query(t)).child(this.hits(t)).when(Boolean(this.peek),
      (e) => e.child(this.lines(t)));
    return frame.child(this.repository(t)).child(this.composer(t))
      .child(v_flex().flex_1().min_h(0).child(this.list(t)).child(this.graph(t)))
      .when(Boolean(this.note && this.root), (e) => e.child(this.problem(t)));
  }

  /** What went wrong last (a sync, a commit), and what to do. */
  problem(t) {
    return div().px(10).py(6).text_size(11).text_color(t.ansi1).child(this.note ?? "");
  }

  /** Section KIND (staged, changes, graph) folded or opened again, and kept so, as the TUI sidebar keeps it.
   * @param {string} kind */
  fold(kind, cx) {
    if (!this.folded.delete(kind)) this.folded.add(kind);
    setShared(FOLDED, [...this.folded]);
    cx.notify();
  }

  get ready() {
    return Boolean(this.root && !this.busy && !this.loading);
  }

  /** How many files a commit could take: staged or not. */
  get changed() {
    return (this.status?.staged?.length ?? 0) + (this.status?.changes?.length ?? 0);
  }

  /** The search field with its switches (Aa, ab, .*), then the folder searched or what the search found. */
  query(t) {
    const toggle = (name, label, tip) => div().id(`switch-${name}`).h(24).px(6).flex().items_center().rounded(5)
      .text_size(12).cursor_pointer().tooltip(tip).text_color(this.switches[name] ? t.accent : t.muted)
      .when(this.switches[name], (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
      .on_click((_e, cx) => {
        cx.stop_propagation();
        this.switches[name] = !this.switches[name];
        this.search(cx);
      })
      .child(label);
    const folder = (this.found ? this.searched?.cwd : place().cwd)?.split(/[\\/]/).pop() ?? "";
    const status = this.searching ? "Searching…" : this.found ? searchSummary(this.found) : `in ${folder}`;
    return v_flex().flex_none().p(10).gap(6).border_b(1).border_color(t.border)
      .child(field(t, "search", this.find, toggle("case", "Aa", "Match case"), toggle("word", "ab", "Whole word"),
        toggle("regex", ".*", "Regular expression")))
      .child(div().text_size(11).text_color(this.found?.error ? t.ansi1 : t.dim).truncate().child(status));
  }

  /** The hits by file, the matches marked; a click shows the file there. */
  hits(t) {
    const row = (r) => r.kind === "file"
      ? h_flex().id(`found-${r.path}`).w_full().h(24).flex_none().px(10).gap(6).items_center().tooltip(r.path)
        .child(fileMark(fileIcon(r.path.split("/").pop())))
        .child(div().font_semibold().child(r.path.split("/").pop()))
        .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(t.dim)
          .child(r.path.includes("/") ? r.path.slice(0, r.path.lastIndexOf("/")) : ""))
        .child(div().px(5).rounded(4).text_size(10).bg(t.raised).text_color(t.muted).child(String(r.count)))
      : h_flex().id(`hit-${r.path}:${r.line}`).w_full().h(24).flex_none().pl(10).pr(10).gap(8).items_center()
        .rounded(6).cursor_pointer().hover((s) => s.bg(t.hover))
        .when(this.peek === `${r.path}:${r.line}`, (e) => e.bg(t.selected))
        .child(div().w(34).flex_none().text_right().text_size(11).text_color(t.dim).child(String(r.line)))
        .child(this.line(t, r.text, r.spans));
    return div().flex_1().min_h(0).relative().text_size(12)
      .child(v_virtual_list("results", this.results.length, 24, (i) => String(i),
        (range) => this.results.slice(range.start, range.end).map(row)).size_full()
        .on_item_click((key, cx) => {                   // the list's own: a row may register no handler
          const hit = this.results[Number(key)];
          if (hit?.kind === "hit") this.reveal(hit, cx);
        }))
      .child(Scrollbar.vertical("results").viewport_from_layout().absolute().inset_0());
  }

  /** TEXT in one row, the matches (SPANS) marked. */
  line(t, text, spans) {
    return h_flex().flex_1().min_w(0).overflow_hidden().font_family(codeFont())
      .children(marked(text, spans ?? []).map(({ text, hit }) => div().flex_none().child(text)
        .when(hit, (e) => e.bg(t.selection).text_color(t.foreground).font_semibold())));
  }

  /** The hit's file from a few lines above it, numbered, its line marked. */
  lines(t) {
    const row = ({ number, text, spans }) => h_flex().w_full().h(20).flex_none().gap(10)
      .when(Boolean(spans), (e) => e.bg(t.selected))
      .child(div().w(34).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
      .child(this.line(t, text, spans));
    return div().flex_1().min_h(0).relative().border_t(1).border_color(t.border).text_size(11)
      .child(v_virtual_list("lines", this.peekRows.length, 20, (i) => String(i),
        (range) => this.peekRows.slice(range.start, range.end).map(row)).size_full())
      .child(Scrollbar.vertical("lines").viewport_from_layout().absolute().inset_0());
  }

  /** The changes in two sections, as the TUI sidebar lists them: Staged changes, then Changes. */
  list(t) {
    const empty = this.loading ? "Loading changes…" : this.root ? "No uncommitted changes" : this.note || "No folder";
    const staged = this.status?.staged ?? [], changes = this.status?.changes ?? [];
    const shownRows = (kind, files) => (files.length ? 1 + (this.folded.has(kind) ? 0 : files.length) : 0);
    const rows = shownRows("staged", staged) + shownRows("changes", changes);
    const part = (kind, title, files) => (e) => e.child(this.section(t, kind, title, files))
      .child(v_flex().id(`${kind}-files`).flex_none().overflow_hidden().h(this.folded.has(kind) ? 0 : files.length * 26)
        .transition("height", SLIDE).children(files.map((f) => this.file(t, kind, f))));
    // as tall as its rows, less when the panel is short: the open Graph below keeps a third
    return v_flex().id("changed").flex_grow(0).flex_shrink(1).h(Math.max(44, rows * 26 + 12))
      .transition("height", SLIDE).min_h(44).overflow_y_scrollbar().p(6)
      .when(staged.length > 0, part("staged", "Staged changes", staged))
      .when(changes.length > 0, part("changes", "Changes", changes))
      .when(!rows, (e) => e.child(div().p(8).text_color(t.dim).child(empty)));
  }

  /** A section's heading, as the TUI sidebar's: its chevron folds it, its count on a chip; with the mouse on it, what
   * it does to all its FILES. @param {string} kind @param {string} title
   * @param {{ path: string, code: string }[]} files */
  section(t, kind, title, files) {
    const key = `section-${kind}`, asking = this.confirm === key;
    const actions = { staged: ["unstage"], changes: ["discard", "stage"] }[kind] ?? [];
    return h_flex().id(key).h(26).flex_none().pl(6).pr(8).gap(6).items_center().rounded(6).cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_hover(hovering(this, key))
      .on_click((_e, cx) => this.fold(kind, cx))
      .child(icon(this.folded.has(kind) ? "chevron-right" : "chevron-down").text_color(t.muted))
      .child(div().flex_1().min_w(0).truncate().font_bold().child(title))
      .when(asking, (e) => e.child(div().text_size(11).text_color(t.ansi1).child("Discard all?")))
      .when((this.hovered === key || asking) && files.length > 0, (e) => e.child(h_flex().gap(GAP)
        .when(asking, (e) => e.child(small(t, `${key}-cancel`, "Cancel", "Keep changes", this.ready,
          (cx) => this.unask(cx))))
        .children(actions.map((action) => small(t, `${key}-${action}`,
          asking && action === "discard" ? "Discard" : icon(ACTION_ICONS[action]), `${TIPS[action]} (all)`, this.ready,
          (cx) => this.change(action, files, key, cx))))))
      .when(files.length > 0, (e) => e.child(div().w(END).flex_none().flex().justify_center()
        .child(chip(t, String(files.length)))));
  }

  /** A changed file's row, as the TUI sidebar's: under its section's name, its type's icon, its name (struck through
   * when deleted) and folder; with the mouse on it, its buttons; its letter under the section's count. */
  file(t, kind, { path, code }) {
    const parts = path.split("/"), name = parts.pop(), key = shown(kind, path);
    const color = changeColor(t, code);
    const asking = this.confirm === key;
    return h_flex().id(`file-${key}`).h(26).flex_none().pl(26).pr(8).gap(6).items_center().rounded(6).cursor_pointer()
      .when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover)).tooltip(path)
      .on_hover(hovering(this, key))
      .on_click((_e, cx) => this.pick(key, { kind: "diff", path }, cx))
      .child(fileMark(fileIcon(name)))
      .child(h_flex().flex_1().min_w(0).gap(6).items_center()
        .child(div().flex_none().when(code === "D", (e) => e.line_through()).child(name))
        .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(t.dim).child(parts.join("/"))))
      .when(asking, (e) => e.child(div().text_size(11).text_color(t.ansi1).child("Discard?")))
      .when(this.hovered === key || asking, (e) => e.child(h_flex().gap(GAP)
        .when(asking, (e) => e.child(small(t, `${key}-cancel`, "Cancel", "Keep change", this.ready,
          (cx) => this.unask(cx))))
        .children(rowActions(kind, code)
        .map((action) => small(t, `${key}-${action}`,
          asking && action === "discard" ? "Discard" : icon(ACTION_ICONS[action]),
          action === "discard" && code === "?" ? "Move to Trash" : TIPS[action], this.ready,
          (cx) => this.change(action, [{ path, code }], key, cx))))))
      .child(div().id(`${key}-letter`).w(END).flex_none().text_center().text_size(11).text_color(color)
        .tooltip(changeName(code)).child(letter(code)));
  }

  /** The question a Discard asked dropped: nothing undone. */
  unask(cx) {
    this.confirm = null;
    cx.notify();
  }

  /** The last commits, as the TUI sidebar's Graph: at the panel's bottom, folded by its heading and kept so; each
   * commit in the files' column, HEAD's marked, with its branches and tags and its author; a click previews it. */
  graph(t) {
    const folded = this.folded.has("graph");
    const heading = h_flex().id("graph").h(26).flex_none().pl(12).pr(8).gap(6).items_center().cursor_pointer()
      .border_t(1).border_color(t.border).hover((s) => s.bg(t.hover)).on_click((_e, cx) => this.fold("graph", cx))
      .child(icon(folded ? "chevron-right" : "chevron-down").text_color(t.muted))
      .child(div().font_bold().child("Graph"));
    const commit = ({ hash, subject, author, refs, head }) => {
      const key = shown("commit", hash);
      return h_flex().id(`commit-${hash}`).h(24).flex_none().pl(26).pr(8).gap(6).items_center().rounded(6)
        .cursor_pointer().when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
        .tooltip(`${hash} ${subject}`).on_click((_e, cx) => this.pick(key, { kind: "commit", hash }, cx))
        .child(div().w(14).flex_none().text_color(head ? t.accent : t.muted).child(head ? "◉" : "○"))
        .child(div().flex_1().min_w(0).truncate().child(subject))
        .when(refs.length > 0, (e) => e.child(div().flex_none().text_size(11).text_color(t.accent)
          .child(refs.join(" "))))
        .child(div().flex_none().text_size(11).text_color(t.muted).child(author));
    };
    // at the bottom, as the TUI sidebar's: the room the changes leave, a third at least when open, its heading on top
    return v_flex().flex_grow(1).flex_shrink(0).flex_basis(folded ? 26 : "33%").min_h(26).justify_end().child(heading)
      .when(this.commits.length > 0, (e) => e.child(v_flex().id("commits").flex_grow(0).flex_shrink(1)
        .h(folded ? 0 : this.commits.length * 24 + 6).transition("height", SLIDE).min_h(0).overflow_y_scrollbar()
        .px(6).children(this.commits.map(commit)).child(div().h(6).flex_none())));
  }

  /** The Commit button's modes, its arrow's menu: a choice is kept for the next commit. */
  get modes() {
    return Object.entries(MODES).map(([mode, label]) => ({ label, on: (this.once ?? this.mode) === mode,
      act: (cx) => this.choose(mode, cx) }));
  }

  /** The repository row's ⋯: pull or push alone, and its page on GitHub. */
  get remote() {
    return [{ label: "Pull", act: (cx) => this.sync(cx, "pull") },
      { label: "Push", act: (cx) => this.sync(cx, "push") },
      ...(this.github ? [{ label: "Open on GitHub", url: `https://github.com/${this.github}` }] : [])];
  }

  /** On top, as VS Code's Repositories: the repository's name, ⎇ its branch, the sync (how far the branch is from its
   * upstream, when it is) and ⋯ its other ways to the remote; its heading folds it. */
  repository(t) {
    const sync = syncLabel(this.status), name = this.root?.split(/[\\/]/).pop() ?? "";
    const row = h_flex().id("repository").h(26).flex_none().pl(26).pr(8).gap(6).items_center().rounded(6)
      .hover((s) => s.bg(t.hover)).tooltip(this.root ?? "")
      .child(icon("book-marked").text_color(t.muted)).child(div().flex_1().min_w(0).truncate().font_semibold()
        .child(name))
      .child(h_flex().flex_none().gap(4).items_center().text_size(12).text_color(t.muted).child(icon("git-branch", 13))
        .child(branchLabel(this.status)))
      .child(h_flex().flex_none().gap(GAP)
        .child(small(t, "repository-sync", h_flex().gap(4).items_center().child(icon("refresh-cw"))
          .when(Boolean(sync), (e) => e.child(sync)), "Sync", this.ready, (cx) => this.sync(cx)))
        .child(small(t, "repository-more", icon("ellipsis"), "More actions", this.ready,
          () => this.menus.open(this.remote, this.pressed)).on_mouse_down("left", (e) => (this.pressed = e.bounds))));
    const folded = this.folded.has("repositories");
    return v_flex().flex_none().px(6).pt(6).child(this.section(t, "repositories", "Repositories", []))
      .when(!folded && Boolean(this.root), (e) => e.child(row));
  }

  /** Under the repository, as the TUI sidebar has it: the message and its ✦, then Commit across, its arrow choosing
   * the mode; under them Cmd + Shift + C's question, when it asks to push. */
  composer(t) {
    const commit = this.ready && (Boolean(this.message.trim()) || Boolean(this.offer));
    const label = this.busy ?? h_flex().gap(8).items_center().child(icon("check"))
      .child(this.offer ? "Push" : `${MODES[this.once ?? this.mode]}${this.asked ? " anyway" : ""}`);
    return v_flex().flex_none().p(10).gap(8).border_b(1).border_color(t.border)
      .child(h_flex().gap(8)
        .child(div().id("message").flex_1().min_w(0).h(32).px(10).flex().items_center().rounded(8).border_1()
          .border_color(t.border).cursor_text().on_key_down((e, cx) => e.key === "escape" && this.cancel(cx))
          .child(Input.new(this.input).h_full().text_size(12).text_color(t.foreground)))
        .child(button(t, "write", icon("sparkles", 15), this.ready, false, (cx) => this.write(cx))
          .bg(t.selection).text_color(this.ready ? t.accent : t.muted).tooltip("Write message")))
      .child(h_flex().gap(8)
        .child(button(t, "commit", label, commit, true, (cx) => this.submit(cx)).flex_1().justify_center())
        .child(button(t, "mode", icon("chevron-down"), this.ready, true,
          () => this.menus.open(this.modes, this.pressed))
          .on_mouse_down("left", (e) => (this.pressed = e.bounds)).tooltip("Commit mode")))
      .when(Boolean(this.offer), (e) => e.child(div().text_size(12).text_color(t.foreground).child(this.offer ?? "")))
      .when(Boolean(this.linked), (e) => e.child(fixesLine(t, this.linked, (cx) => this.unlink(cx))));
  }
}
