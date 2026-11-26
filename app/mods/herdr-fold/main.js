// @ts-check
// herdr-fold for the Herdr app, the TUI sidebar's views; a diff, a commit or an issue opens in the space's preview tab
// (preview.js), a text file in an editor tab (editor.js). It runs on the space's machine, with core's code (helper.js).
import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, Scrollbar, v_virtual_list } from "gpui-base";
import { spaces, panes, focused, exec, hc, home, nextCommand, theme, layout, props, closeOverlay,
  shared, setShared, readTextFile, run as command } from "herdr";
import { COMMIT_MESSAGE, FILEOPS, GIT, SEARCH } from "./helper.js";
import { activeTerminal, afterCommit, background, branchLabel, changeColor, changeName, commitMode, excerpt, fileIcon,
  floatStale, foldedSections, hovering, lastLine, launcher, letter, marked, MODES, PANEL_NAMES, panelPx,
  panelsFollow, pushOffer, pythonCommand, railed, railFollow, rowActions, said, searchRows, searchSummary,
  secretQuestion, shortCount, sidebarFollow, sidebarPx, swapDraft, syncLabel, written, noteShown }
  from "./logic.js";
import { button, chip, codeFont, END, field, fileMark, fold, footNote, GAP, icon, iconButton, INDENT, noteToast, PAD,
  segmented, small, SPINNER, SPRING } from "./parts.js";
import { forgetMenus, MENU_LIVE, menuGone, Menus, menuFind, menuPopup } from "./menus.js";
import { askChats, bottomChoice, checkUpdates, chosenView, FloatSize, followFolder, keepBottom, liveDockTabs, liveRail,
  foldDock, openAgents, RepoLook, restDock, restFollow, restorePanels, sizedFloat, summon, tell, toggleChats,
  toggleColumn, SUMMON, tabsState } from "./panel.js";
import { followNotes, forgetSettings, openSettings, SettingsView, UPDATES, whatsNew } from "./settings.js";
import { AgentLook, AgentView } from "./agent.js";
import { AgentsView } from "./agentstab.js";
import { Chat, firstChat, newAgentIn } from "./chat.js";
import { StartView } from "./start.js";
import { ChatsView } from "./chats.js";
import { FilesView } from "./files.js";
import { addMachine, forgetFloat, forgetFloats, liveDock, restSide, sidebarFoot, sidebarHead, spacesBody,
  spacesButtons, toggleSidebar } from "./sidebar.js";
import { IssuesView, fixesChip } from "./issues.js";
import { BranchPull, PullsView } from "./pulls.js";
import { isHome, markUnread, pickSpace, SpacesView } from "./spaces.js";
import { liveStatus, watchRuns } from "./status.js";
import { TabsView } from "./tabs.js";
import { Palette, pickTheme, TitleView, togglePalette } from "./title.js";
import { openNamed, Preview, showPreview } from "./preview.js";
import { EditorTab, sweepDrafts } from "./editor.js";
import { guide, styleguide } from "./styleguide.js";
import { standIn, TerminalFollower } from "./terminal.js";

const REFRESH = 10000;             // ms between two looks when no folder change says so (another machine's space)
const POLL = 1500;                 // ms between two looks at the message being written
const WRITING = 6 * 60 * 1000;     // ms the message may take: both AIs, each asked twice
const LINES = 1500;                // a hit's file's lines shown at most
const MODE = "herdr-fold.commit_mode", FOLDED = "herdr-fold.folded";   // kept (shared)
const BOARD = "herdr-fold.board";       // the Issues tab's list shown, kept (shared) as Changes' sections are
/** A key's command, and the view whose copy runs it (the tab bar hands it on: a view hidden or folded hears none). */
const VIEWS = { write: "changes", "commit-push": "changes", commit: "changes", sync: "changes", changes: "changes",
  "pull-request": "changes", search: "search", issues: "issues", files: "files", agent: "agent" };
/** @type {[string, string][]} the Issues tab's two lists, its view switch's */
const BOARDS = [["issues", "Issues"], ["pulls", "Pull requests"]];
/** The styleguide's tab, named: a mod's tab nobody named is called Terminal. */
const STYLEGUIDE = { name: "Styleguide", mod: "herdr-fold", props: { part: "styleguide" } };
const FRESH = 5000;                // ms a key's ask waits for its view to show (a copy starting on it too)
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

/** A row's key, the one chosen marked: "staged:PATH", "changes:PATH" or "commit:HASH". @param {string} kind
 * @param {string} id */
const shown = (kind, id) => `${kind}:${id}`;

/** ARGV run in ROOT on machine ON. @param {string[]} argv @param {string} root @param {string | null} on */
const TICK = 20000;               // ms: a wait's label redrawn this often, as the TUI's
const UPDATES_EVERY = 3600000;     // ms between two looks at core/update.py's check (GitHub itself once a day at most)
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

/** core/'s SOURCE run with ARGS where the repository is: what it printed (a CSV's text).
 * @param {string} source @param {string[]} args @param {string} root @param {string | null} on */
async function pythonText(source, args, root, on) {
  const out = await run([...pythonCommand(await pythonOn(on)), source, ...args], root, on);
  if (out.code !== 0) throw new Error(lastLine(out));
  return out.stdout;
}

/** core/'s SOURCE run with ARGS where the repository is: its JSON answer.
 * @param {string} source @param {string[]} args @param {string} root @param {string | null} on */
const python = async (source, args, root, on) => JSON.parse(await pythonText(source, args, root, on));

/** core/commit_message.py with ARGS in the background on ON's machine, in a core terminal of its own (the AIs may take
 * minutes), its answer looked for every POLL ms for WRITING ms at most: that answer, its JSON read. */
async function writer(cx, args, root, on) {
  const job = background(await pythonOn(on), COMMIT_MESSAGE, args);
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
      if (out.code !== 0) throw new Error(`Nothing written: ${lastLine(out)}`);
      return JSON.parse(out.stdout);
    }
    throw new Error("Nothing written: the AIs took longer than six minutes");
  } finally {
    await run(job.clear(folder), root, on);
    if (terminal) await hc(["kill", terminal]);
  }
}

/** core/git.py's COMMAND on ROOT: null when it worked, else what to do. @param {string} command @param {string} root
 * @param {string | null} on @param {string[]} [rest] */
async function git(command, root, on, rest = []) {
  const done = await python(GIT, [command, root, ...rest], root, on);
  return done.ok ? null : done.advice;
}

/** What the tab bar's look at the focused folder (panel.js's RepoLook) and Changes ask there: its repository's root
 * (its own, else the one inside it, as the Spaces row names it), its status, its GitHub name. */
const ASK = {
  top: async (/** @type {string} */ cwd, /** @type {string | null} */ on) =>
    (await python(GIT, ["top", cwd], cwd, on)).root,
  status: (/** @type {string} */ root, /** @type {string | null} */ on) => python(GIT, ["status", root], root, on),
  github: async (/** @type {string} */ root, /** @type {string | null} */ on) =>
    (await python(GIT, ["github", root], root, on)).name,
};

/** With nothing staged, every change staged, as a commit takes them (core/git.py's stage_all).
 * @param {string} root @param {string | null} on */
async function stage(root, on) {
  const advice = await git("stage", root, on);
  if (advice) throw new Error(advice);
}

export default class HerdrFold extends View {
  init(_props, cx) {
    const shown = props() ?? {};
    if ("level" in shown && !shown.part) {        // a note, while An agent waits on you is off: an error or a
      if (noteShown(shown.level)) return void (this.note = shown);  // warning drawn here, the rest closed at once
      closeOverlay(shown.overlay);
      return void (this.blank = true);
    }
    if ((this.launcher = launcher(props()))) {    // mod.open: Changes shown, as Cmd+Shift+G, then gone
      summon("changes");
      return void closeOverlay(this.launcher);
    }
    const part = props()?.part;                   // the layout's terminal stack: its header, its stand-in
    if (part === "terminal") {
      this.terminal = new TerminalFollower();
      return void cx.timer.every(REFRESH, (cx) => this.terminal.look(cx));
    }
    if ((this.blank = part === "none")) return;
    if ((this.dock = part === "dock-head")) return;      // the right dock's tabs, its views' stack's header
    if (part === "menu") {                        // a menu; its filter, the keys in it (a new chat's agent list)
      const { overlay, items, head, find, none, token } = props();
      this.popup = { overlay, items, head, token, find: find ? menuFind(find, none, () => this.menuItems(), overlay)
        : null };
      return void cx.timer.after(0, () => this.popup.find?.input.focus());
    }
    if (part === "settings") return void (this.settings = new SettingsView(python, cx));   // the one Settings
    if (part === "tabs") {                        // the tab bar, where the app's own was: always there, so it looks
      const bar = (this.bar = new TabsView());    // for herdr-fold's newer releases and at the repository for the
      this.repo = new RepoLook(ASK);              // dock's tabs too, and hands the keys on (More's choices its own)
      this.setup = new AgentLook(python);         // the Agent tab's dot: its setup's problems, behind the views
      forgetSettings();
      forgetFloats();
      forgetMenus();
      cx.timer.every(REFRESH, (cx) => (this.repo.look(place(), cx), this.setup.follow(cx)));
      cx.timer.after(0, () => void checkUpdates(python).then(() => sweepDrafts(python)));
      followNotes().catch(() => {});              // the layout's toast as Notifications has it: an install rewrote it
      cx.spawn(async (cx) => {
        for (;;) {
          const asked = await nextCommand();
          if (!bar.menus.answer(asked, cx)) this.route(asked);
        }
      });
      return void cx.timer.every(UPDATES_EVERY, () => void checkUpdates(python));
    }
    if (part === "preview") {
      const preview = (this.preview = new Preview(props().space, python));
      return void cx.spawn(async (cx) => {
        for (;;) {                                // its right click's choices, Cmd+S and Cmd+F for its code
          const asked = await nextCommand();
          if (!preview.menus.answer(asked, cx) && (asked === "save" || asked === "find")) preview.command(asked, cx);
        }
      });
    }
    if (part === "editor") {                      // an editor tab: a text file (editor.js), Cmd+S and Cmd+F its own
      const tab = (this.editorTab = new EditorTab(props(), python));
      return void cx.spawn(async (cx) => {
        for (;;) {
          const asked = await nextCommand();
          if (asked === "save" || asked === "find") tab.editing?.command(asked, cx);
        }
      });
    }
    // the Agents tab: its graph and its usage (a CSV's text read as it is)
    if (part === "agents") return void (this.agents = new AgentsView(props().space, python, cx, pythonText));
    if (part === "start") return void (this.start = new StartView(python, cx));    // a home's first tab (start.js)
    if (part === "chat") {                        // a chat tab: an agent's chat as a timeline (chat.js)
      const chat = (this.chat = new Chat(props(), python, pythonOn));
      chat.init(cx);
      return void cx.spawn(async (cx) => {
        for (;;) chat.menus.answer(await nextCommand(), cx);                // its mode's and commands' menus
      });
    }
    if ((this.sideHead = part === "head")) return;      // the sidebar's head: its toggle (folded: over its rail)
    if ((this.sideFoot = part === "footer")) return;    // the open sidebar's foot: Settings, Add machine
    if ((this.bottom = part === "status")) return void watchRuns(python, cx);   // the window's status bar
    if (part === "title") return void (this.titleRow = new TitleView());    // the window's own title row
    if (part === "palette") {                     // the command palette, opened onto the title row's field
      const { overlay, wide, most, shade } = props();
      const palette = (this.palette = new Palette(overlay, { wide, most, shade }));
      return void cx.timer.after(0, () => palette.input.focus());
    }
    if ((this.rail = part === "rail")) return;          // the right panel folded: its rail
    if (part === "float") {                       // a folded side's panel, floating beside its rail
      this.float = { panel: props().panel, overlay: props().overlay };
      this.pending = props().then;                // the rail's key's command, run once its view has looked
      const { panel, overlay } = this.float;
      this.floatFocus = cx.focus_handle();       // the keys as it opens, so Esc closes it, not the agent's terminal
      if (panel !== "chats") cx.timer.after(0, () => this.floatFocus.focus());       // Chats: its filter takes them
      this.floatSize = new FloatSize(panel, { fit: props().fit, most: props().most });   // as dragged, kept for it
      if (panel === "spaces") return void cx.timer.every(TICK, (cx) => cx.notify());     // its waits, a minute on
      if (panel === "chats" || panel === "files") {
        const view = panel === "files" ? (this.files = new FilesView(python, cx))
          : (this.chats = new ChatsView(python, cx, { overlay }));
        this.chats?.focus();                      // Chats beside the rail with the keys, as the TUI's list opens
        return void cx.spawn(async (cx) => {
          for (;;) view.menus.answer(await nextCommand(), cx);                    // its right click's choices
        });
      }                                           // Agent, Search, Changes or Issues: the view below, that one only
    }
    if (part === "chats") {                       // the list in the dock, in the view's place, Chats lit
      const chats = (this.chats = new ChatsView(python, cx, { back: () => toggleChats() }));
      chats.focus();
      return void cx.spawn(async (cx) => {
        for (;;) chats.menus.answer(await nextCommand(), cx);                // its right click's choices
      });
    }
    if (part === "spaces") return void (this.spaces = new SpacesView(python, cx));    // the sidebar's: folded, its dock
    if (part === "files") {                       // the right panel's Files, where the app's own was
      this.files = new FilesView(python, cx);
      return void cx.spawn(async (cx) => {
        for (;;) this.files.menus.answer(await nextCommand(), cx);              // its right click's choices
      });
    }
    if (part === "styleguide") {                  // all of it, or its section props().section names (a picture of it)
      this.only = props()?.section ?? null;
      this.from = Number(props()?.from) || 0;     // a tall section's picture, a screen of it: drawn from px FROM down
      return void (this.guide = guide(HerdrFold.prototype, cx));
    }
    const view = this.float?.panel ?? props()?.view;               // the layout's block of a view, or a float's
    if (view === "agent") return void (this.agent = new AgentView(python, cx, Boolean(this.float), openAgents));
    this.commits = []; this.status = null; this.message = ""; this.menus = new Menus();
    this.view = ["search", "issues"].includes(view) ? view : "changes";
    /** a copy in a pane of its own (no layout's block, no float): its keys its own, its views switched in place */
    this.alone = !this.float && !props()?.view;
    this.core = python;                           // the Issues view asks core/ through it
    this.issues = new IssuesView(this);
    this.pulls = new PullsView(this);             // the Issues tab's other list, its switch's
    /** the Issues tab's list shown: its issues, or its pull requests (the one shown last) */
    this.board = shared(BOARD) === "pulls" ? "pulls" : "issues";
    this.pull = new BranchPull(this, (cx, args) => writer(cx, args, this.root, this.on));    // Changes' row and form
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
    /** @type {string | null} while ✦ writes: who writes the message (core/commit_message.py writing) */
    this.writing = null;
    /** @type {string | null} the space shown, place() as JSON; the one ✦ writes for */
    this.key = null; this.writingKey = null;
    /** @type {Map<string, string>} each other space's message, kept while another is shown (swapDraft) */
    this.drafts = new Map();
    this.input = InputState.new({ placeholder: "" });        // its words drawn over it while empty (composer())
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
        if (this.menus.answer(asked, cx)) continue;
        if (this.alone) this.dispatch(asked, cx);       // in the layout the tab bar hands the keys on (summon)
      }
    });
  }

  /** A key's command handed on (VIEWS) by the tab bar, which always shows, once: the view shown, its copy running it;
   * Chats beside the rail while the dock is one (open, its row's copy opens them in the dock); the focused agent
   * unread; Cmd+N's new agent, as + starts it. */
  route(asked) {
    if (Object.hasOwn(VIEWS, asked)) summon(VIEWS[asked], asked);
    else if (asked === "new-agent") {
      const space = spaces().find((s) => s.active);
      if (space) newAgentIn(space).catch(() => {});
    }
    else if (asked === "chats") askChats();                         // Cmd+Shift+R, as the tab bar's Chats
    else if (asked === "sidebar") toggleSidebar();                  // Cmd+B: the left dock folded or opened
    else if (asked === "panels") foldDock();                        // Cmd+Option+B: the right one
    else if (asked === "agents") openAgents();                      // the palette's Agents: the space's Agents tab
    else if (asked === "usage") openAgents({ view: "usage" });      // the palette's Usage: that tab's Usage
    else if (asked === "runs") openAgents({ view: "runs" });        // the palette's Runs: that tab's Runs
    else if (asked === "unread") markUnread();
    else if (asked === "settings") openSettings();                  // Cmd+, and the palette: the one Settings
    else if (asked === "new-space") pickSpace().catch(() => {});    // Ctrl+B, Shift+N: a folder picked, a space there
    else if (asked === "add-machine") addMachine();                 // Ctrl+B, Shift+M: the app's Add machine
    else if (asked === "column") toggleColumn();                    // Cmd+Shift+E: the dock hidden or shown again
    else if (asked === "restore") restorePanels();                  // Cmd+Shift+O: all that was hidden back
    else if (asked === "open-file") openNamed(python, this.bar.menus).catch(() => {});      // Cmd+Shift+L
    else if (asked === "theme") pickTheme(this.bar.menus);          // Cmd+K, Cmd+T: herdr-fold's themes
    else if (asked === "whats-new") {                              // the update's toast: this version's CHANGELOG
      const version = /** @type {any} */ (shared(UPDATES))?.version;
      if (version) whatsNew(python, version).catch(() => {});
    }
    else if (asked === "styleguide") command("tab.new", STYLEGUIDE);
    else if (asked === "palette") togglePalette();                  // the palette's key: onto the title row's field
  }

  /** A command of the view's ("herdr-fold.<command>": a bound key, herdr-app do, or the rail's for its float). */
  dispatch(asked, cx) {
    if (asked === "write") this.write(cx);
    else if (asked === "commit-push") this.commitPush(cx);
    else if (asked === "commit") this.commit(cx);
    else if (asked === "sync") this.sync(cx);
    else if (asked === "changes" || asked === "search" || asked === "issues") this.show(asked, cx);
    else if (asked === "pull-request") this.pull.start(cx);
    else if (asked === "styleguide") command("tab.new", STYLEGUIDE);
  }

  /** The repository of the focused pane, its changes, how far it is from its upstream and its last commits, from
   * core/git.py. */
  refresh(cx) {
    if (this.view === "search") return this.runPending(cx);      // a search asks git nothing
    const here = place(), key = JSON.stringify(here);
    if (key !== this.key) {                       // while ✦ writes too: its message never lands in another space
      const message = swapDraft(this.drafts, this.key, key, this.message);
      Object.assign(this, { key, root: null, commits: [], status: null, open: null, note: null, message,
        asked: null, confirm: null, github: null, linked: null, head: null, once: null, offer: null });
      this.input.set_value(message);
      this.issues.reset();
      this.pulls.reset();
      this.pull.reset();
      this.publish();
    }
    if (this.loading || this.busy || !here.cwd) return;
    this.loading = true;
    cx.spawn(async (cx) => {
      try {
        const root = await ASK.top(here.cwd, here.on);
        if (key !== this.key) return;
        if (!root) return void (this.note = "Not a git repository");
        const status = await python(GIT, ["status", root], root, here.on);
        const changes = this.view === "changes";                     // Issues: the count for the row, no Graph
        const { commits } = changes ? await python(GIT, ["graph", root], root, here.on) : { commits: [] };
        const github = this.root === root ? this.github : (await python(GIT, ["github", root], root, here.on)).name;
        // the issue the next commit fixes, unlinked once a commit made anywhere closed it (core/commit_message.py)
        const settled = github && changes ? await python(COMMIT_MESSAGE, ["settle", root,
          ...(this.head ? [this.head] : [])], root, here.on) : { linked: null, head: null };
        if (key !== this.key) return;
        Object.assign(this, { root, on: here.on, status, commits, github, linked: settled.linked,
          head: settled.head ?? this.head, offer: this.offer && pushOffer(status) });   // asked anew: pushed, changed
        const board = this.board === "pulls" ? this.pulls : this.issues;      // asked once, then each minute
        if (this.view === "issues" && github && (!board.listing && !board.asked || board.stale())) board.load(cx);
        if (changes) this.pull.look(cx, commits[0]?.hash ?? null);
        followFolder(this, (cx) => this.refresh(cx), cx);   // another machine's space waits for REFRESH
      } catch (e) {
        if (key === this.key) this.note = said(e);
      } finally {
        this.loading = false;
        this.publish();
        this.runPending(cx);
        cx.notify();
      }
    });
  }

  /** What the row and the rail (panel.js) show of its repository once looked at: Issues or not, the changed files'
   * count, at once after a commit or a stage (the tab bar's look tells them for any view, this one shown or not). */
  publish() {
    if (this.view !== "search" && this.root) tell({ github: Boolean(this.github), changed: this.changed });
  }

  /** The command waiting for the view's first look (a key's, the rail's), run once, now: without a repository, none. */
  runPending(cx) {
    const then = this.pending;
    this.pending = undefined;
    if (then && (this.root || this.view === "search")) cx.timer.after(0, (cx) => this.dispatch(then, cx));
  }

  /** A key's ask for this view (SUMMON, the tab bar's), once, while fresh: run now, or once the view has looked. */
  answer(cx) {
    const asked = /** @type {{ view: string, command: string, at: number } | null} */ (shared(SUMMON));
    if (this.alone || this.float || !asked || asked.view !== this.view || asked.at === this.answered ||
      Date.now() - asked.at > FRESH) return;
    this.answered = asked.at;
    this.pending = asked.command;
    if (this.root || this.view === "search") this.runPending(cx);
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
        this.busy = this.writing = null;
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
      this.busy = this.writing = (await python(COMMIT_MESSAGE, ["writing", root], root, on)).writing;
      this.writingKey = key;
      cx.notify();
      await stage(root, on);
      const answer = written(await writer(cx, ["write", root], root, on));
      if (answer.message && key === this.key) {
        this.input.set_value(answer.message);
        this.message = answer.message;
      } else if (answer.message) this.drafts.set(key, answer.message);      // waiting there for its space
      return answer.note;
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

  /** Cmd + Shift + C's commit or push given up (Esc): the message gone, the mode the kept one; whether there was one
   * (else Esc goes on: a float closes). */
  cancel(cx) {
    if (!(this.once || this.offer) || this.busy) return false;
    Object.assign(this, { once: null, offer: null, message: "", note: null });
    this.input.set_value("");
    cx.notify();
    return true;
  }

  /** The branch synced with its upstream (pulled, fast-forward only, then pushed), or only pulled or pushed (the
   * repository row's ⋯), as core/git.py does it. @param {"sync" | "pull" | "push"} [how] */
  sync(cx, how = "sync") {
    this.act(cx, REMOTE[how], () => git(how, this.root, this.on));
  }

  /** The view shown (a copy alone switches; a layout's has its own); Search takes the keys. @param {string} view */
  show(view, cx) {
    const was = this.view;
    this.view = ["search", "issues"].includes(view) ? view : "changes";
    if (this.view === "search") this.find.focus();
    const board = this.board === "pulls" ? this.pulls : this.issues;
    if (this.view === "issues" && !board.listing) board.load(cx);
    if (this.view !== was && this.view !== "search") this.refresh(cx);
    cx.notify();
  }

  /** The Issues tab's list BOARD shown (issues, pulls), asked for once. @param {string} board */
  switchBoard(board, cx) {
    this.board = board;
    setShared(BOARD, board);
    const shown = board === "pulls" ? this.pulls : this.issues;
    if (!shown.listing && !shown.asked) shown.load(cx);
    cx.notify();
  }

  /** The Pull requests list's +: Changes shown with its form open, as a key's command reaches it. */
  newPull(cx) {
    if (!this.alone) return summon("changes", "pull-request");
    this.show("changes", cx);
    this.pending = "pull-request";              // once Changes has looked at the branch's pull request
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

  /** The menu's rows as they are now: a menu that stays open (a filter's) takes its opener's anew (MENU_LIVE). */
  menuItems() {
    const live = /** @type {any} */ (shared(MENU_LIVE));
    return live && live.token === this.popup.token ? live.items : this.popup.items;
  }

  /** Its block or popup gone: the palette's, however it closed (the app's Esc, a press beside), unlights the field;
   * Settings' lets the next ask open it again. */
  async close() {
    this.palette?.closed();
    this.settings?.closed();
    if (this.float) forgetFloat(this.float.overlay);
    if (this.popup) menuGone(this.popup.overlay);
  }

  render(cx) {
    if (this.terminal) {
      this.terminal.watch(cx);
      return div();
    }
    if (this.launcher) return div();
    const t = theme();
    if (this.note) return noteToast(t, this.note);
    if (this.blank) return standIn(t);
    if (this.dock) return liveDockTabs(t, cx);
    if (this.popup) return menuPopup(t, this.popup.overlay, this.menuItems(), this.popup.head, this.popup.find);
    if (this.settings) return this.settings.render(t, codeFont());
    if (this.rail) return liveRail(t, activeTerminal(layout()));
    if (this.guide) return styleguide(this.guide, t, this.only, this.from);
    if (this.preview) {
      this.preview.watch(cx);
      return this.preview.render(t, codeFont());
    }
    if (this.editorTab) {
      this.editorTab.watch(cx);
      return this.editorTab.render(t, codeFont());
    }
    if (this.chat) return this.chat.render(t, codeFont());
    if (this.agents) return this.agents.render(t, cx);
    if (this.start) return this.start.render(t);
    const float = this.float;
    if (float && floatStale(float.panel, layout())) cx.timer.after(0, () => closeOverlay(float.overlay));
    const own = { focus: this.floatFocus, panel: float?.panel };       // a float's keys and its side
    if (float?.panel === "spaces") return sizedFloat(t, this.floatSize, "Spaces", float.overlay, spacesBody(t),
      { ...own, buttons: spacesButtons(t) });
    if (this.chats) return float ? sizedFloat(t, this.floatSize, "Chats", float.overlay, this.chats.render(t, cx), own)
      : this.chats.render(t, cx);
    if (this.spaces) return railed(layout()) ? liveDock(t) : this.spaces.render(t);
    if (this.bar) {
      this.repo.follow(place(), cx);
      this.setup.follow(cx);
      this.followDock(cx);
      if (!this.chatting) {                       // the space shown: its chat first, once (after this render)
        this.chatting = true;
        cx.timer.after(0, () => void ((this.chatting = false), firstChat(isHome)));
      }
      return this.bar.render(t);
    }
    if (this.files) return float ? sizedFloat(t, this.floatSize, "Files", float.overlay, this.files.render(t, cx), own)
      : this.files.render(t, cx);
    if (this.agent) return float ? sizedFloat(t, this.floatSize, "Agent", float.overlay, this.agent.render(t, cx),
      { ...own, owns: () => Boolean(this.agent.listing || this.agent.addMenu) }) : this.agent.render(t, cx);
    if (this.sideHead) return sidebarHead(t);
    if (this.sideFoot) return sidebarFoot(t);
    if (this.bottom) return liveStatus(t);
    if (this.titleRow) return this.titleRow.render(t);
    if (this.palette) return this.palette.render(t);
    if (this.view !== "search" && JSON.stringify(place()) !== this.key) this.refresh(cx);
    if (float) return sizedFloat(t, this.floatSize, PANEL_NAMES[this.view], float.overlay, this.panel(t), own);
    this.answer(cx);
    return this.panel(t);
  }

  /** Both sides shown as their widths say (railFollow, sidebarFollow; folded, the dock's terminal under the centre as
   * kept), each width set once a drag lets go (restFollow), the dock on the view the space chose (panelsFollow): from
   * the tab bar, which every layout of herdr-fold's draws, a hidden sidebar too. */
  followDock(cx) {
    const root = layout();
    keepBottom(root);
    restFollow("dock", panelPx(root), restDock, cx);
    restFollow("side", sidebarPx(root), restSide, cx);
    const commands = [...railFollow(root, bottomChoice()), ...panelsFollow(root, tabsState().github, chosenView()),
      ...sidebarFollow(root)];
    if (!commands.length || this.railing) return;
    this.railing = true;
    cx.timer.after(0, () => {
      for (const [name, args] of commands) command(name, args);
      this.railing = false;
    });
  }

  /** The view shown, under the dock's row (panel.js): Changes, Search, or Issues for a repository on GitHub (else
   * Changes). */
  panel(t) {
    const frame = v_flex().id("herdr-fold").size_full().min_h(0).text_color(t.foreground).text_size(13);
    if (this.view === "issues" && this.github) return frame
      .child(h_flex().flex_none().px(PAD).pt(PAD).child(segmented(t, "board", BOARDS, this.board,
        (board, cx) => this.switchBoard(board, cx))))
      .child(this.board === "pulls" ? this.pulls.render(t) : this.issues.render(t));
    if (this.view === "search") return frame.child(this.query(t)).child(this.hits(t)).when(Boolean(this.peek),
      (e) => e.child(this.lines(t)));
    return frame.relative().child(this.repository(t)).child(this.pull.form ? this.pull.formView(t) : this.composer(t))
      .child(v_flex().flex_1().min_h(0).child(this.list(t)).child(this.graph(t)))
      .when(Boolean(this.note && this.root), (e) => e.child(this.problem(t)));
  }

  /** What went wrong last (a sync, a commit) and what to do: the dock's foot line, over the card's last strip, so the
   * list and the Graph stay where they are; red until the next action, or its ×, as the TUI's foot line till a key. */
  problem(t) {
    return h_flex().absolute().left_0().right_0().bottom_0().items_start().pr(PAD / 2).bg(t.surface).border_t(1)
      .border_color(t.border)
      .child(footNote(t, { text: this.note ?? "", error: true }).flex_1().min_w(0))
      .child(div().pt(2).child(iconButton(t, "problem-close", "x", "Dismiss", (cx) => {
        this.note = null;
        cx.notify();
      }, { size: 12 })));
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
    const toggle = (name, label, tip) => div().id(`switch-${name}`).h(24).px(6).flex().items_center().rounded(4)
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
    return v_flex().flex_none().p(PAD).gap(6).border_b(1).border_color(t.border)
      .child(field(t, "search", this.find, toggle("case", "Aa", "Match case"), toggle("word", "ab", "Whole word"),
        toggle("regex", ".*", "Regular expression")))
      .child(div().text_size(11).text_color(this.found?.error ? t.ansi1 : t.dim).truncate().child(status));
  }

  /** The hits by file, the matches marked; a click shows the file there. */
  hits(t) {
    const row = (r) => r.kind === "file"
      ? h_flex().id(`found-${r.path}`).w_full().h(24).flex_none().px(PAD / 2).gap(6).items_center().tooltip(r.path)
        .child(fileMark(fileIcon(r.path.split("/").pop())))
        .child(div().font_semibold().child(r.path.split("/").pop()))
        .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(t.dim)
          .child(r.path.includes("/") ? r.path.slice(0, r.path.lastIndexOf("/")) : ""))
        .child(div().px(6).rounded(4).text_size(10).bg(t.raised).text_color(t.muted).child(String(r.count)))
      : h_flex().id(`hit-${r.path}:${r.line}`).w_full().h(24).flex_none().px(PAD / 2).gap(8).items_center()
        .rounded(6).cursor_pointer().hover((s) => s.bg(t.hover))
        .when(this.peek === `${r.path}:${r.line}`, (e) => e.bg(t.selected))
        .child(div().w(34).flex_none().text_right().text_size(11).text_color(t.dim).child(String(r.line)))
        .child(this.line(t, r.text, r.spans));
    return div().flex_1().min_h(0).relative().px(PAD / 2).pb(PAD / 2).text_size(12)
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
    const row = ({ number, text, spans }) => h_flex().w_full().h(20).flex_none().gap(12)
      .when(Boolean(spans), (e) => e.bg(t.selected))
      .child(div().w(34).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
      .child(this.line(t, text, spans));
    return div().flex_1().min_h(0).relative().pb(PAD / 2).border_t(1).border_color(t.border).text_size(11)
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
        .spring("height", SPRING).children(files.map((f) => this.file(t, kind, f))));
    // as tall as its rows, less when the panel is short: the open Graph below keeps a third
    return v_flex().id("changed").flex_grow(0).flex_shrink(1).h(Math.max(44, rows * 26 + PAD))
      .spring("height", SPRING).min_h(44).overflow_y_scrollbar().p(PAD / 2)
      .when(staged.length > 0, part("staged", "Staged changes", staged))
      .when(changes.length > 0, part("changes", "Changes", changes))
      .when(!rows, (e) => e.child(div().px(PAD / 2).py(8).text_color(t.dim).child(empty)));
  }

  /** A section's heading, as the TUI sidebar's: its chevron folds it, its count on a chip; with the mouse on it, what
   * it does to all its FILES. @param {string} kind @param {string} title
   * @param {{ path: string, code: string }[]} files */
  section(t, kind, title, files) {
    const key = `section-${kind}`, asking = this.confirm === key;
    const actions = { staged: ["unstage"], changes: ["discard", "stage"] }[kind] ?? [];
    return h_flex().id(key).h(26).flex_none().px(PAD / 2).gap(6).items_center().rounded(6).cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_hover(hovering(this, key))
      .on_click((_e, cx) => this.fold(kind, cx))
      .child(fold(`${key}-fold`, !this.folded.has(kind), 14, t.muted))
      .child(div().flex_1().min_w(0).truncate().font_bold().child(title))
      .when(asking, (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi1).child("Discard all?")))
      .when((this.hovered === key || asking) && files.length > 0, (e) => e.child(h_flex().gap(GAP)
        .when(asking, (e) => e.child(small(t, `${key}-cancel`, "Cancel", "Keep changes", this.ready,
          (cx) => this.unask(cx))))
        .children(actions.map((action) => small(t, `${key}-${action}`,
          asking && action === "discard" ? "Discard" : icon(ACTION_ICONS[action]), `${TIPS[action]} (all)`, this.ready,
          (cx) => this.change(action, files, key, cx))))))
      .when(files.length > 0, (e) => e.child(div().w(END).flex_none().flex().justify_center()
        .child(chip(t, shortCount(files.length)))));
  }

  /** A changed file's row, as the TUI sidebar's: under its section's name, its type's icon, its name (struck through
   * when deleted) and folder; with the mouse on it, its buttons; its letter under the section's count. */
  file(t, kind, { path, code }) {
    const parts = path.split("/"), name = parts.pop(), key = shown(kind, path);
    const color = changeColor(t, code);
    const asking = this.confirm === key;
    return h_flex().id(`file-${key}`).h(26).flex_none().pl(INDENT).pr(PAD / 2).gap(6).items_center().rounded(6)
      .cursor_pointer().when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover)).tooltip(path)
      .on_hover(hovering(this, key))
      .on_click((_e, cx) => this.pick(key, { kind: "diff", path }, cx))
      .child(fileMark(fileIcon(name)))
      .child(h_flex().flex_1().min_w(0).gap(6).items_center()
        .child(div().min_w(0).truncate().when(code === "D", (e) => e.line_through()).child(name))
        .child(div().flex_1().min_w(0).truncate().text_size(11).text_color(t.dim).child(parts.join("/"))))
      .when(asking, (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi1).child("Discard?")))
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
    const heading = h_flex().id("graph").h(26).flex_none().px(PAD).gap(6).items_center().cursor_pointer()
      .border_t(1).border_color(t.border).hover((s) => s.bg(t.hover)).on_click((_e, cx) => this.fold("graph", cx))
      .child(fold("graph-fold", !folded, 14, t.muted))
      .child(div().font_bold().child("Graph"));
    const commit = ({ hash, subject, author, refs, head }) => {
      const key = shown("commit", hash);
      return h_flex().id(`commit-${hash}`).h(24).flex_none().pl(INDENT).pr(PAD / 2).gap(6).items_center().rounded(6)
        .cursor_pointer().when(this.open === key, (e) => e.bg(t.selected)).hover((s) => s.bg(t.hover))
        .tooltip(`${hash} ${subject}`).on_click((_e, cx) => this.pick(key, { kind: "commit", hash }, cx))
        .child(div().w(14).flex_none().text_color(head ? t.accent : t.muted).child(head ? "◉" : "○"))
        .child(div().flex_1().min_w(0).truncate().child(subject))
        .when(refs.length > 0, (e) => e.child(div().min_w(0).max_w("45%").truncate().text_size(11)
          .text_color(t.accent).child(refs.join(" "))))      // the subject keeps the rest
        .child(div().flex_none().text_size(11).text_color(t.muted).child(author));
    };
    // at the bottom, as the TUI sidebar's: the room the changes leave, a third at least when open, its heading on top;
    // a row's pad under its last row, folded or not, as at the sides
    return v_flex().flex_grow(1).flex_shrink(0).flex_basis(folded ? 26 + PAD / 2 : "33%").min_h(26 + PAD / 2)
      .pb(PAD / 2).justify_end().child(heading)
      .when(this.commits.length > 0, (e) => e.child(v_flex().id("commits").flex_grow(0).flex_shrink(1)
        .h(folded ? 0 : this.commits.length * 24).spring("height", SPRING).min_h(0).overflow_y_scrollbar()
        .px(PAD / 2).children(this.commits.map(commit))));
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
    const step = this.busy && !this.writing ? this.busy : null;      // a commit, a sync, a pull or a push under way
    const row = h_flex().id("repository").h(26).flex_none().pl(INDENT).pr(PAD / 2).gap(6).items_center().rounded(6)
      .hover((s) => s.bg(t.hover)).tooltip(this.root ?? "")
      .child(icon("book-marked").text_color(t.muted)).child(div().flex_1().min_w(0).truncate().font_semibold()
        .child(name))
      .child(h_flex().flex_none().gap(4).items_center().text_size(12).text_color(t.muted).child(icon("git-branch", 13))
        .child(branchLabel(this.status)))
      .child(h_flex().flex_none().gap(GAP)
        .child(small(t, "repository-sync", h_flex().gap(4).items_center()
          .child(step ? div().size(14).flex().items_center().justify_center().child(div().frames(SPINNER, 100))
            : icon("refresh-cw"))
          .when(Boolean(sync), (e) => e.child(sync)), step ?? "Sync", this.ready, (cx) => this.sync(cx)))
        .child(small(t, "repository-more", icon("ellipsis"), "More actions", this.ready,
          () => this.menus.open(this.remote, this.pressed)).on_mouse_down("left", (e) => (this.pressed = e.bounds))));
    const folded = this.folded.has("repositories");
    return v_flex().flex_none().px(PAD / 2).pt(PAD / 2).child(this.section(t, "repositories", "Repositories", []))
      .when(!folded && Boolean(this.root), (e) => e.child(row))
      .when(!folded && this.pull.shown && !this.pull.form, (e) => e.child(this.pull.row(t)));
  }

  /** Under the repository, as the TUI sidebar has it: the message and its ✦, then Commit across, its arrow choosing
   * the mode; two rows whatever happens: the push Cmd + Shift + C offers said in the empty field, the issue the next
   * commit fixes a chip at its end, who writes in it while empty, else in ✦'s tip (a spinner in ✦ meanwhile). */
  composer(t) {
    const commit = this.ready && (Boolean(this.message.trim()) || Boolean(this.offer));
    const lit = Boolean(this.changed || this.offer);            // nothing to commit: the pull request's row the way on
    const label = h_flex().gap(8).items_center().child(icon("check"))
      .child(this.offer ? "Push" : `${MODES[this.once ?? this.mode]}${this.asked ? " anyway" : ""}`);
    const writing = this.writing && this.writingKey === this.key ? this.writing : null, empty = !this.message;
    return v_flex().flex_none().p(PAD).gap(8).border_b(1).border_color(t.border)
      .child(h_flex().gap(8)
        .child(div().id("message").flex_1().min_w(0).h(32).pl(12).pr(this.linked ? 4 : 12).gap(6).flex().items_center()
          .rounded(8).border_1().border_color(t.border).cursor_text()
          .on_key_down((e, cx) => {
            if (e.key === "escape") this.cancel(cx);        // then the float beside a rail takes the keys back
          })
          .child(writing && empty                                       // who writes in it
            ? h_flex().flex_1().min_w(0).gap(6).items_center().text_size(12).text_color(t.muted)
              .child(div().frames(SPINNER, 100)).child(writing)
            : div().flex_1().min_w(0).h_full().relative().child(Input.new(this.input).h_full().text_size(12)
              .text_color(t.foreground))
              .when(empty, (e) => e.child(h_flex().absolute().top_0().bottom_0().left_0().items_center().text_size(12)
                .text_color(this.offer ? t.muted : t.dim).child(this.offer ?? "Commit message"))))
          .when(Boolean(this.linked), (e) => e.child(fixesChip(t, this.linked, (cx) => this.unlink(cx)))))
        .child(button(t, "write", writing && !empty ? div().size(15).flex().items_center().justify_center()
          .child(div().frames(SPINNER, 100)) : icon("sparkles", 15), this.ready, false, (cx) => this.write(cx))
          .bg(t.selection).text_color(this.ready || writing ? t.accent : t.muted).tooltip(writing ?? "Write message")))
      .child(h_flex().gap(8)
        .child(button(t, "commit", label, commit, lit, (cx) => this.submit(cx)).flex_1().justify_center())
        .child(button(t, "mode", icon("chevron-down"), this.ready, lit,
          () => this.menus.open(this.modes, this.pressed))
          .on_mouse_down("left", (e) => (this.pressed = e.bounds)).tooltip("Commit mode")));
  }
}
