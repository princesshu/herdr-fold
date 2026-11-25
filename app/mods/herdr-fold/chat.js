// @ts-check
// The chat tab: an agent's chat drawn as a timeline from its session file (core/chat.py, read as it grows),
// the agent itself in a core terminal with no pane, started with herdr-fold's hook and status line (agents.js).
import { div, image, svg } from "gpui-kit";
import { v_flex, h_flex, Popover, Popup, ScrollHandle, Textarea, TextareaState, TextView } from "gpui-base";
import { randomUUID } from "crypto";
import { exec, focused, hc, home, knownAgents, notify, panes, playSound, readTextFile, setShared, shared, spaces,
  terminals, theme, window, writeTextFile, run as command } from "herdr";
import { AGENT_SETUP, AGENT_STATE, CHAT, CHATS, CONNECTORS, COSTS, GIT, REPORT, SEARCH } from "./helper.js";
import { ADAPTERS, agentChoices, AGENTS_OPEN, agentsOpen, atTyped, barFolds, budgetNotice, cardFor, claudeArgv,
  contextColor, contextLine, contextParts, costBlock, DRAWABLE, effortAt, effortLabel, exportName, limitNotice,
  mentionMenu, mentionPick, mentionQuery, menuSkills, modelName, modelOf, modelRows, modeOf, modeRows, nearEffort,
  newAgent, panelStep, promptText, readableOn, RECENT_AGENTS, rememberAgent, screenChoices, screenMode, shellsOnly,
  skillCommand,
  skillOf, slashMenu, slashQuery, SLIDER, switchCommand, switchRefused, terminalSpace, terminalTab, uploadPaths,
  withFiles } from "./agents.js";
import { Answer } from "./card.js";
import { groupHead, keepInView, listNote, listWords, Menus, panelList, panelRow, panelSurface, rule }
  from "./menus.js";
import { checkedOver, chipColors, loginRun, overdue, partColor, plusMenu, signIns, switched, toneInk, usageAgents }
  from "./layers.js";
import { askChats, openAgentPanel, openAgents } from "./panel.js";
import { brandMark, BUTTON, fileMark, fold, icon, iconButton, keyCap, ring, savePanel, SAVING, spinner, swatch,
  systemForms, toggle } from "./parts.js";
import { showPreview } from "./preview.js";
import { notesOn } from "./settings.js";
import { tokens } from "./report.js";
import { bottomLayout, callWords, CARD_HEAD, clock, connectorRow, planStrip, planWords, RHYTHM as R, setForms,
  signinRow, stepLayout, timeline, timelineMarkdown, userLayout } from "./timeline.js";
import { CHAT_LABEL, CHAT_TAB, CHAT_WAITS, chatWait, diffRows, fileIcon, folderGroup, folderSpaces, keepWait,
  lastLine, said, waiting } from "./logic.js";

const WORKING = 500, IDLE = 2000;     // ms between two reads of the session file, while the agent works and not
const COLUMN = 680;                   // px: the timeline's and the prompt's width at most, mid-tab (connectors.html's)
const OUTPUT = 12;                    // an open call's output: its lines shown at most
const NAME = 40;                      // a new chat tab's name: its first prompt's characters at most
const NEW = "New chat";               // a new chat tab's name until its first message names it
const LIST = 240;                     // px: a new chat's agent list, its longest row (a name, "not installed")
const ROWS = 8;                       // the prompt's rows at most, as it grows with what is typed
const SHOWN = 200;                    // the timeline's latest rows drawn; Show earlier adds as many again
const MODELS = 320;                   // px: the model chip's panel, its longest line (Default's) with its check
const MODES = 372;                    // px: the mode chip's panel, as center-chat.html's
const CONTEXT = 430;                  // px: the Context panel, as center-chat.html's
const UNIT = 64;                      // px: its cost block's last column, a figure's word (usage.html's .crow)
const BUDGET_EVERY = 300000;          // ms between two looks at the budgets' notice (core's report.py notice)
const COMMANDS = 520;                 // px: the / menu and Add context's list, as center-chat.html's
const PLUS = 380;                     // px: the + menu, as connectors.html's
const ATTACHED = 200;                 // px: an attached file's name on its chip at most
const LISTED = 5000;                  // files Add context lists at most: its filter finds among them
const SETTLE = [2000, 6000];          // ms after Claude was told to turn a connector off or on: its setup read again
const CHAT_FIRST = "herdr-fold.chat-first";  // shared: the spaces met once with Chat, given a chat first or not
const FEW = 5;                        // the / menu's rows of a part before anything is typed: the rest found by typing
const PRESS = 400;                    // ms: a press beside the / menu closing it, its button's own (not opened again)
const CHIP_GAP = 6;                   // px: inside a chip, between its words (the model and its level, `context` and %)
const LEVEL = 76;                     // px: the effort's name at the slider's right, Extra high its longest, at 13
const REST = 500;                     // ms the slider's arrows rest before the level they reached is sent
const ASKED = 10000;                  // ms a model or an effort sent is shown before the agent says it
const SWITCHES = "herdr-fold.chat-switches";   // each chat's switches on (Ultracode), by its session: none reports it
const AFTER_SHRINK = 4;               // what a plan's step waits for gives way that much sooner than the step's words
const ANSWER = 1500;                  // ms after a switch's command before the agent's screen is read for a refusal
// macOS's file chooser (osascript's): the files attached to a message, ARGV its folder at first; a path a line, ""
// for none (cancelled)
const CHOOSE = "function run(argv) { const app = Application.currentApplication(); "
  + "app.includeStandardAdditions = true; app.activate(); try { return app.chooseFile({ "
  + "withPrompt: 'Attach files', defaultLocation: Path(argv[0]), "
  + "multipleSelectionsAllowed: true }).map((file) => file.toString()).join('\\n'); } catch (e) { "
  + "if (e.errorNumber === -128) return ''; throw e; } }";
const NEXT_MODE = "herdr_fold_next_mode", CHAT_KEYS = "HerdrFoldChat";   // ⇧ + tab in a chat: its next mode
const UPLOAD = "herdr_fold_upload";   // ⌘ U in a chat: Upload from computer…
/** A panel of the bar's, upward from its chip or button; the / menu and Add context's list over the prompt.
 * @typedef {"plus" | "model" | "modes" | "commands" | "context" | "mention"} Panel */
let bound = false;                    // that key bound, once a run (the app's keymap is one for every copy)

/** A link's words in theme T: the accent, moved toward the text until it reads on the hover's fill (the keys' row).
 * @param {Record<string, string>} t */
const linkInk = (t) => ([t.accent, t.foreground, t.hover].every((hex) => /^#[0-9a-f]{6}$/i.test(hex ?? ""))
  ? readableOn(t.accent, t.foreground, t.hover) : t.accent);


/** The chats waiting on you now (logic.js's waiting): their tabs, each space's longest wait, their agents. */
export const chatWaits = () => waiting(shared(CHAT_WAITS), terminals());

/** A chat tab's name from its first PROMPT's first line, cut to NAME; "New chat" while it has none.
 * @param {string} prompt */
const chatName = (prompt) => {
  const first = prompt.split("\n")[0].trim();
  return (first.length > NAME ? `${first.slice(0, NAME - 1)}…` : first) || NEW;
};

/** @typedef {{ space: string, agent?: string, session?: string, resume?: boolean, prompt?: string, name?: string,
 *   folder?: string | null, first?: boolean }} NewChat */
/** A new chat tab in SPACE (its id): AGENT's chat SESSION in FOLDER (the space's by default), a new one with its first
 * PROMPT, sent at once, or the empty chat (no PROMPT: its agent starts with the first message), or one it resumes;
 * FIRST: the space's first tab. @param {NewChat} chat */
export function openChat({ space, agent = DRAWABLE[0], session = randomUUID(), resume = false, prompt = "",
  name = "", folder = null, first = false }) {
  command("tab.new", { name: name || chatName(prompt), mod: "herdr-fold",
    props: { part: "chat", space, agent, session, resume, prompt, folder } });
  if (first) command("tab.move", { index: 1 });            // the new tab, shown: first of its space
}

/** KEY started by a way in: the latest agent from now on (agents.js's rememberAgent). @param {string} key */
export function usedAgent(key) {
  const kept = shared(RECENT_AGENTS), next = rememberAgent(kept, key);
  if (JSON.stringify(next) !== JSON.stringify(kept)) setShared(RECENT_AGENTS, next);
}

/** CHOICE (agentChoices') as its own CLI in a new terminal tab of SPACE, in FOLDER (the space's by default), PROMPT
 * its first message; the latest agent then. @param {import("./agents.js").Choice} choice @param {any} space
 * @param {string} [prompt] @param {string | null} [folder] */
export function openTerminal(choice, space, prompt = "", folder = null) {
  command("tab.new", terminalTab(choice, { space: space.id, folder: folder ?? space.folder, prompt }));
  usedAgent(choice.key);
}

/** AGENT as the app knows it on MACHINE (knownAgents: its name, icon and how it starts), else as herdr-fold names it.
 * @param {string} agent @param {string | null} machine */
export async function choiceOf(agent, machine) {
  const known = await knownAgents({ on: machine }).catch(() => []);
  return agentChoices(known, DRAWABLE, []).find((c) => c.key === agent)
    ?? agentChoices([{ key: agent, name: agent }], DRAWABLE, []).find((c) => c.key === agent);
}

/** The agent every way in starts in a space on MACHINE (null: this Mac), and how, by Settings' Open agents in: the
 * one place it is decided (newAgent's). @param {string | null} machine */
export const nextAgent = (machine) => newAgent(shared(RECENT_AGENTS), agentsOpen(shared(AGENTS_OPEN)), machine);

/** A new agent in SPACE as +, Cmd+N and To agent start one (nextAgent's): a new chat (PROMPT sent at once; none:
 * empty), or the latest agent in a terminal tab, PROMPT its first message, in FOLDER (the space's by default);
 * "chat", or the agent's name. @param {any} space @param {string} [prompt] @param {any} [folder] */
export async function newAgentIn(space, prompt = "", folder = null) {
  const { agent, as } = nextAgent(space.machine);
  if (as === "chat") {
    openChat({ space: space.id, agent, prompt, folder });
    return "chat";
  }
  const choice = await choiceOf(agent, space.machine);
  openTerminal(choice, space, prompt, folder);
  return choice.name;
}

/** A new space as WHERE makes it (space.new's machine and folder; none: as the app makes one), its agent started as
 * + starts one (nextAgent's): the agent's own CLI its first tab; a chat, firstChat's as it shows, as for one the app
 * makes. @param {{ machine?: string, folder?: string }} [where] */
export async function newSpace(where = {}) {
  const machine = where.machine ?? spaces().find((s) => s.active)?.machine ?? null;
  const { agent, as } = nextAgent(machine || null);
  const choice = as === "terminal" ? await choiceOf(agent, machine || null) : null;
  command("space.new", choice ? terminalSpace(choice, where) : where);
  if (choice) usedAgent(choice.key);
}

/** The space herdr-fold's layout shows, met the first time with Open agents in a chat (nextAgent's: this Mac): an
 * empty chat its first tab, shown, where it holds shells alone and is not a home (ISHOME, spaces.js's); kept once
 * (CHAT_FIRST), so a chat closed stays closed. @param {(space: any) => boolean} isHome */
export function firstChat(isHome) {
  const space = spaces().find((s) => s.active), kept = shared(CHAT_FIRST);
  const met = Array.isArray(kept) ? kept : [], { agent, as } = nextAgent(space?.machine ?? null);
  if (!space || as !== "chat" || met.includes(space.id)) return;
  const live = new Set(spaces().map((s) => s.id));
  setShared(CHAT_FIRST, [...met.filter((id) => live.has(id)), space.id]);
  if (shellsOnly(space, panes()) && !isHome(space)) openChat({ space: space.id, agent, first: true });
}

export class Chat {
  /** The chat tab PROPS opened (openChat's); CORE runs core/'s code (main.js's python), PYTHON_ON names the Python
   * there. @param {any} props @param {(source: string, args: string[], root: string, on: string | null) =>
   * Promise<any>} core @param {(on: string | null) => Promise<string>} pythonOn */
  constructor(props, core, pythonOn) {
    this.props = props;
    this.core = core;
    this.pythonOn = pythonOn;
    this.session = String(props.session);
    /** @type {string | null} the tab it is drawn in: the one focused once tab.new has selected it */
    this.tab = null;
    /** @type {string | null} the agent's terminal */
    this.address = null;
    /** @type {any[]} core/chat.py's steps so far, and where its next read starts */
    this.steps = [];
    this.offset = 0;
    /** @type {import("./timeline.js").Moment[]} */
    this.rows = [];
    this.reading = false;
    this.read = 0;                                // when the session file was last read
    /** @type {Map<string, boolean>} rows opened or folded by a click, by key */
    this.opened = new Map();
    this.shown = SHOWN;                           // the latest rows drawn
    /** px the timeline is scrolled back from its end (0: at its end, new rows in view); its own and its rows' height */
    this.back = 0;
    this.view = 0;
    this.content = 0;
    /** @type {string | null} why there is no chat */
    this.note = null;
    /** the agent (its key, an adapter's), until the first message changeable from its list */
    this.agentKey = Object.hasOwn(ADAPTERS, String(props.agent)) ? String(props.agent) : DRAWABLE[0];
    this.adapter = ADAPTERS[this.agentKey];
    /** nothing said yet: the empty chat, its agent started by the first message (a prompt given: at once) */
    this.fresh = !props.resume && !props.prompt;
    /** @type {any[]} the app's agents (knownAgents: its icon, its list); the space's branch, the empty chat's words */
    this.known = [];
    /** @type {any} the agents as core tells them (agent_state.py agents): which are to sign in; null: not told */
    this.machine = null;
    this.branch = "";
    /** @type {string | null} the model, the mode and the level picked before the agent started: its launch's */
    this.firstModel = null;
    this.firstMode = null;
    this.firstEffort = null;
    this.menus = new Menus();                     // the mode's, the commands'
    /** @type {any} the status line's numbers (core/chat.py's status); what Claude waits on (Task 7's cards) */
    this.status = null;
    this.pending = null;
    /** @type {any} its task list (core/plan.py's, null for none): the strip over the prompt, open or folded, its
     * done steps listed or in one row */
    this.plan = null;
    this.planOpen = this.doneOpen = false;
    /** @type {{ model: string | null, effort: string | null, mode: string | null }} as the session file names them */
    this.named = { model: null, effort: null, mode: null };
    /** @type {string | null} the mode asked for, and the shift+tab presses made towards it */
    this.wanted = null;
    this.presses = 0;
    this.recheck = 0;                             // reads left that look at the mode on Claude's screen (a dialog's)
    /** @type {Set<string>} limit and budget notices closed, by key */
    this.dismissed = new Set();
    /** @type {any} core's budget notices (report.py notice): an API-key agent's month near or past its budget */
    this.budget = null;
    this.budgetAt = 0;
    /** @type {any} what this chat cost (costs.py), read as the Context panel opens; null: not told */
    this.costs = null;
    /** @type {any} the bounds of the chip pressed, the menu's place */
    this.pressed = null;
    /** @type {any} the prompt (init's: a host call), and whether the cursor is in it */
    this.input = null;
    this.typing = false;
    this.blank = true;                            // the prompt empty, as last drawn: its words over it
    /** @type {Answer | null} the card in the prompt's place (init's) */
    this.answer = null;
    /** @type {string | null} the request answered last: shown no more while the hook takes the answer */
    this.answered = null;
    /** @type {number | null} since when the agent asks in its own terminal, no card; since when the chat waits */
    this.blocked = null;
    this.since = null;
    /** @type {"request" | "terminal" | null} how it waits on you (logic.js's chatWait) */
    this.waits = null;
    /** @type {string | null | undefined} the wait last told by a sound and a toast; undefined: as kept, if kept */
    this.told = undefined;
    this.given = false;                           // its terminal given a pane of its tab by the way out
    /** @type {string | null} the level the slider is on while dragged or stepped, not sent yet */
    this.draft = null;
    /** @type {{ id: string, at: number } | null} the level sent last, shown till the status line says it */
    this.asked = null;
    /** @type {{ id: string, at: number, from: string | null } | null} the model sent last, till the agent names
     * another than it did (FROM) */
    this.modelAsked = null;
    this.sliding = false;                         // the slider's knob dragged
    this.stepped = 0;                             // when an arrow last moved it
    /** @type {Panel | null} the bar's panel open: the model chip's, the mode chip's, the / menu, the Context panel */
    this.open = null;
    /** the / menu following the prompt's "/…" (else its button's, over a message), what is typed after the "/" */
    this.typedMenu = false;
    this.query = "";
    /** @type {string | null} the prompt's text the / menu was closed on (Esc, a press beside): shut till it changes */
    this.shut = null;
    this.shutAt = 0;                              // when a press beside closed it
    /** @type {Panel | null | undefined} the chip lit as while its panel is open, as the styleguide shows */
    this.litShown = undefined;
    /** the / menu over the prompt in the page's flow, not a popup (the styleguide's: a popup there lands anywhere) */
    this.inPlace = false;
    /** @type {any} what the agent starts with in the chat's folder (agent_setup.py's rules, skills and mode): null
     * while not read; why it could not be */
    this.setup = null;
    /** @type {string | null} */
    this.setupError = null;
    this.front = false;                           // in front at the last look: back in front, its setup read again
    /** @type {any} the open panel's list (the / menu's, the Context panel's), scrolled to the keys' row (init's) */
    this.listScroll = null;
    /** @type {number[]} each of the open panel's rows, its place in that list */
    this.listPlaces = [];
    /** @type {number | null} the open panel's row the keys are on */
    this.cursor = null;
    /** @type {any} the panels' keys (init's: a host call) */
    this.panelFocus = null;
    /** the bar's parts left out in a narrow chat (barFolds'), from its free px and their px as last drawn: the
     * context's words first, then the model chip's level */
    this.folded = 0;
    this.spare = 0;
    this.labelWide = 0;
    this.levelWide = 0;
    /** @type {Record<string, string>} each switch the agent refused, why (its words): drawn faint, that its tip */
    this.refused = {};
    this.hidden = false;                          // that terminal hidden by hand while the agent still asks there
    /** @type {string[]} the files attached to the next message (Upload from computer…), chips over the prompt */
    this.files = [];
    this.choosing = false;                        // macOS's chooser open
    /** @type {{ changed: string[], files: string[] } | null} Add context's list, paths from the chat's folder */
    this.listed = null;
    /** @type {string | null} why it could not be listed */
    this.listError = null;
    /** @type {Record<string, { on: boolean, at: number }>} the connectors' switches just turned, till the setup says */
    this.switching = {};
    /** @type {{ name: string, on: boolean }[]} those not told yet: Claude not started, or at work */
    this.toTell = [];
    this.telling = false;
    /** @type {number[]} when (ms) the setup is read again, after Claude was told */
    this.due = [];
    /** @type {Record<string, { base: string | null, state: string }>} Claude's own looks at a server */
    this.checked = {};
    this.setupAt = 0;                             // when (ms) the setup was last read: a sign-in asked since asks
    /** @type {Set<string>} the servers seen signing in (their terminals), those whose sign-in is being started */
    this.signed = new Set();
    this.connecting = new Set();
    /** @type {Record<string, string>} why a server's sign-in could not start */
    this.connectFailed = {};
  }

  /** Once, after tab.new has selected its tab: the agent found again (the tab drawn anew, the app opened again) or
   * started; then its file read. */
  init(cx) {
    this.input = TextareaState.new({ placeholder: "" });                // its words drawn over it (prompt())
    this.input.set_auto_grow(1, ROWS);
    this.promptEvents();
    this.answer = new Answer((reply, cx) => this.reply(reply, cx), cx);
    this.panelFocus = cx.focus_handle();
    this.listScroll = ScrollHandle.new();
    if (!bound) {
      bound = cx.bind_keys([{ keystroke: "shift-tab", action: NEXT_MODE, context: CHAT_KEYS },
        { keystroke: "cmd-u", action: UPLOAD, context: CHAT_KEYS }]) > 0;
    }
    cx.timer.after(0, (cx) => {
      this.tab = focused()?.tab ?? null;
      this.front = this.inFront() && Boolean(window()?.active);
      this.readSetup(cx);                         // its rules and skills, the mode it starts in
      cx.spawn(async (cx) => {
        try {
          if (await this.start()) this.input.focus();         // a new chat: typing goes to its prompt
          if (this.fresh) await this.empty(cx);
        } catch (e) {
          this.note = `${this.adapter.name} could not start: ${said(e)}`;
        }
        cx.notify();
      });
    });
    cx.timer.every(WORKING, (cx) => {
      this.look(cx);
      this.backInFront(cx);
      this.tellConnectors(cx);
      this.watchSignIns(cx);
    });
    cx.spawn(async (cx) => {
      setForms(await systemForms());              // its times as this Mac writes them
      cx.notify();
    });
  }

  /** What the prompt says to the chat: Enter sends it (the / menu or Add context's list open: picks its keys' row;
   * Shift+Enter: a new line), a "/" typed opens the / menu on what follows, an "@" Add context's list, the cursor in
   * it lights its edge. */
  promptEvents() {
    this.input.on("submit", (event, cx) => {
      const row = this.menuRows()[this.cursor ?? -1];
      if (event.shift) return;
      if (this.over() && row) this.act(row, cx);
      else this.send(cx);
    });
    this.input.on("change", (_e, cx) => {
      const menu = this.slashTyped(cx), list = this.mentionTyped(cx);
      if (menu || list || this.blank !== !this.input.value()) cx.notify();   // its words drawn over it, or gone
    });
    for (const [event, typing] of /** @type {const} */ ([["focus", true], ["blur", false]])) {
      this.input.on(event, (_e, cx) => {
        this.typing = typing;                     // the prompt's edge lit while the cursor is in it
        cx.notify();
      });
    }
  }

  get space() {
    return spaces().find((s) => s.id === this.props.space) ?? null;
  }

  get agent() {
    return terminals().find((t) => t.address === this.address) ?? null;
  }

  /** The agent found again (its tab the one it was started for; the keys left where they are, as the copy drawn anew
   * may not be shown) or started with its first PROMPT (the empty chat's: its first message); true when started. A tab
   * DRAWN anew whose session was started before (its agent ended since) resumes it. */
  async start(prompt = String(this.props.prompt ?? ""), drawn = true) {
    const space = this.space, folder = this.props.folder || space?.folder || (space?.machine === null ? home() : "");
    if (!folder) throw new Error("its space has no folder");
    if (space.machine) throw new Error("a chat runs on this Mac for now");
    const kept = terminals().find((t) => t.labels?.[CHAT_LABEL] === this.session && t.state === "live");
    if (kept) {
      this.address = kept.address;
      this.tab = kept.labels?.[CHAT_TAB] ?? this.tab;
      this.recheck = 1;                           // its mode as its screen says it now
      this.fresh = false;
      return false;
    }
    const before = drawn && !this.props.resume
      && (await this.core(CHAT, ["steps", this.session, "0"], folder, null)).steps.length > 0;
    if (this.fresh && !prompt && !before) return false;
    const resume = Boolean(this.props.resume) || before;
    this.fresh = false;
    const argv = claudeArgv({ python: await this.pythonOn(null), session: this.session, resume,
      prompt: resume ? "" : prompt, model: this.firstModel ?? undefined, mode: this.firstMode ?? undefined,
      effort: this.firstEffort ?? undefined, switches: this.switched() });
    // --rm: an agent ended (its tab closed, /exit) leaves nothing; it outlives the app quitting all the same
    const done = await hc(["run", "--bg", "--json", "--rm", "--no-parent", "--cwd", folder, "--label",
      `${CHAT_LABEL}=${this.session}`, ...(this.tab ? ["--label", `${CHAT_TAB}=${this.tab}`] : []), "--", ...argv]);
    if (done.code !== 0) throw new Error(lastLine(done));
    this.address = JSON.parse(done.stdout).address;
    usedAgent(this.agentKey);
    return true;
  }

  /** The empty chat: the keys in its prompt, the space's branch under its words, the app's agents for its list. */
  async empty(cx) {
    this.input.focus();
    cx.notify();
    const folder = this.props.folder || this.space?.folder;
    const [branch, known] = await Promise.all([
      exec("git", ["-C", String(folder), "branch", "--show-current"]).then((done) => (done.code === 0
        ? done.stdout.trim() : "")).catch(() => ""),
      knownAgents().catch(() => [])]);
    [this.branch, this.known] = [branch, known];
    if (this.space?.machine) return;              // this Mac's agents alone are told yet
    this.core(AGENT_STATE, ["agents"], String(folder), null).then((/** @type {any} */ told) => (this.machine = told))
      .catch(() => {});                           // not told: the list marks none to sign in
  }

  /** What the agent starts with in the chat's folder, read (agent_setup.py, the adapter's word for it): as the chat
   * opens, back in front, as its Context panel opens; drawn anew only where it changed, kept where a read fails. */
  readSetup(cx) {
    const adapter = this.adapter, folder = this.props.folder || this.space?.folder;
    if (!adapter.setup || !folder || this.space?.machine) return;
    cx.spawn(async (cx) => {
      try {
        const setup = await this.core(AGENT_SETUP, [adapter.setup, folder], folder, null);
        if (adapter !== this.adapter) return;       // another agent picked meanwhile
        const asks = this.rows.some((row) => row.kind === "signin");
        this.setupAt = Date.now();
        if (!this.setupError && JSON.stringify(setup) === JSON.stringify(this.setup)) {
          return void (asks && cx.notify());        // nothing changed: a sign-in's step is as this read says
        }
        [this.setup, this.setupError] = [setup, null];
      } catch (e) {
        if (adapter !== this.adapter || this.setup) return;
        this.setupError = said(e);
      }
      cx.notify();
    });
  }

  /** Every WORKING ms: the chat back in front (its tab shown, the app active), its setup read again: a rule or a
   * skill added meanwhile shows. */
  backInFront(cx) {
    const front = this.inFront() && Boolean(window()?.active);
    if (front && !this.front) this.readSetup(cx);
    if (front && Date.now() - this.budgetAt > BUDGET_EVERY) this.readBudget(cx);
    this.front = front;
  }

  /** The budgets' notice asked of core (its threshold and words; the agents' plans, asked first where not told, say
   * who is on an API key), every BUDGET_EVERY while the chat is in front. */
  readBudget(cx) {
    if (this.space?.machine) return;
    this.budgetAt = Date.now();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        if (!Array.isArray(this.machine)) this.machine = await this.core(AGENT_STATE, ["agents"], home(), null);
        const answer = await this.core(REPORT, ["notice", `--agents=${JSON.stringify(usageAgents(this.machine))}`],
          home(), null);
        if (JSON.stringify(answer) === JSON.stringify(this.budget)) return;
        this.budget = answer;
        cx.notify();
      } catch {
        // not told: no notice
      }
    });
  }

  /** The budget notice KEY closed for its month, in both clients (core keeps it). @param {string} key */
  closeBudget(key, cx) {
    this.dismissed.add(key);
    this.core(REPORT, ["dismiss", key], home(), null).catch(() => {});
    cx.notify();
  }

  /** What this chat cost, read as the Context panel opens (costs.py, by the session's id; the models'
   * colors read on the theme's popover); kept where a read fails. */
  readCosts(cx) {
    if (this.fresh || this.space?.machine) return;
    const t = theme(), ground = t.popover ?? t.raised;
    this.core(COSTS, [this.agentKey, this.session, `--agents=${JSON.stringify(usageAgents(this.machine))}`,
      `--surface=${ground}`, `--text=${t.foreground}`], home(), null).then((/** @type {any} */ costs) => {
      if (JSON.stringify(costs) === JSON.stringify(this.costs)) return;
      this.costs = costs;
      cx.notify();
    }).catch(() => {});
  }

  /** The empty chat's first message: its agent started with it, the tab named after it. @param {string} text */
  begin(text, cx) {
    if (this.tab && spaces().flatMap((s) => s.tabs ?? []).find((c) => c.id === this.tab)?.name === NEW) {
      command("tab.rename", { id: this.tab, name: chatName(text) });
    }
    this.fresh = false;
    cx.spawn(async (cx) => {
      try {
        await this.start(text, false);
      } catch (e) {
        this.note = `${this.adapter.name} could not start: ${said(e)}`;
      }
      cx.notify();
    });
  }

  /** The empty chat's agent list (its chip's, decisions.html's): the installed agents, the RECENT ones first, one no
   * adapter draws marked terminal, one to sign in marked so, the one chosen checked; under a rule those core lists
   * dim (not installed), in its order, each opening the Agent panel at how it installs. @param {unknown} [recent] */
  agentList(recent = shared(RECENT_AGENTS)) {
    const item = (/** @type {import("./agents.js").Choice} */ c) => ({ label: c.name, on: c.key === this.agentKey,
      note: c.signIn ? "sign in" : c.terminal ? "terminal" : undefined, tone: c.signIn ? "warn" : undefined,
      icon: c.icon ? { path: c.icon, tint: c.tint } : undefined, act: (/** @type {any} */ cx) => this.pick(c, cx) });
    const absent = (Array.isArray(this.machine) ? this.machine : []).filter((a) => a?.listed?.dim === true)
      .map((/** @type {any} */ a) => {
        const program = this.known.find((p) => p.key === a.key);
        return { label: String(a.name ?? a.key), dim: true, act: () => openAgentPanel({ look: a.key }),
          icon: typeof program?.icon === "string" ? { path: program.icon, tint: Boolean(program.tint) } : undefined };
      });
    return [...agentChoices(this.known, DRAWABLE, recent, this.machine).map(item), ...(absent.length ? [null] : []),
      ...absent];
  }

  /** CHOICE picked in the empty chat's list: the chat's agent (its models and efforts its own), or one no adapter
   * draws in a terminal tab of its own, what is typed its first message, in this chat's place; one to sign in: the
   * Agent panel as its own, where it signs in. @param {any} choice */
  pick(choice, cx) {
    if (choice.signIn) openAgentPanel({ agent: choice.key });
    if (!choice.terminal) {
      this.agentKey = choice.key;
      this.adapter = ADAPTERS[choice.key];
      [this.firstModel, this.firstMode, this.firstEffort, this.setup, this.setupError] = [null, null, null, null, null];
      this.readSetup(cx);
      return void cx.notify();
    }
    if (choice.signIn) return;
    openTerminal(choice, this.space, promptText(this.input.value()), this.props.folder || null);
    if (this.tab) command("tab.close", { id: this.tab });
  }

  /** The agent's icon as the app draws its program's (knownAgents'), SIZE square; null while not known.
   * @param {number} size */
  agentIcon(t, size) {
    const program = this.known.find((p) => p.key === this.agentKey);
    if (!program?.icon) return null;
    return program.tint ? svg(program.icon).size(size).flex_none().text_color(t.foreground)
      : image(program.icon).size(size).flex_none();
  }

  /** Every WORKING ms: the session file's new lines, what Claude waits on and the status line's numbers while the agent
   * works or a mode is asked for, every IDLE ms while it waits. */
  look(cx) {
    if (!this.address || this.reading) return;
    const waiting = ["working", "blocked"].includes(this.agent?.status);
    if (!waiting && !this.wanted && Date.now() - this.read < IDLE) return;
    this.reading = true;
    this.read = Date.now();
    cx.spawn(async (cx) => {
      try {
        const got = await this.core(CHAT, ["steps", this.session, String(this.offset)], this.space?.folder ?? "/",
          null);
        const before = JSON.stringify([this.status, this.pending, this.named, this.waits, this.terminalShown(),
          this.plan]);
        this.offset = got.offset;
        this.status = got.status;
        this.plan = got.plan ?? null;
        this.pending = got.pending?.id === this.answered ? null : got.pending;
        const choices = this.pending?.kind === "dialog"           // asked in Claude's own dialog: its choices there
          ? screenChoices((await hc(["read", String(this.address)])).stdout) : undefined;
        if (!this.answer?.shows(this.pending, choices)) {
          const fresh = !this.answer?.shows(this.pending);
          this.answer?.reset(this.pending, choices);
          if (this.pending && fresh) this.answer?.focus.focus();
        }
        this.named = { model: got.model ?? this.named.model, effort: got.effort ?? this.named.effort,
          mode: got.mode ?? this.named.mode };
        await this.asking();
        await this.turn();
        if (got.steps.length) {
          this.steps.push(...got.steps);
          this.rows = timeline(this.steps);
          if (got.steps.some((/** @type {any} */ step) => step.kind === "signin")) this.readSetup(cx);
        }
        if (got.steps.length || before !== JSON.stringify([this.status, this.pending, this.named, this.waits,
          this.terminalShown(), this.plan])) cx.notify();
      } catch (e) {
        this.note = said(e);
        cx.notify();
      } finally {
        this.reading = false;
      }
    });
  }

  /** How the chat waits on you after a look: its card (a request), or its agent asking in its own terminal (blocked, or
   * before it says any state a dialog's choices at its screen's foot: a new folder's trust question) for WAY_OUT ms;
   * kept for the tab bar, Spaces and Chats, told once by a sound and a toast, the terminal shown for it in front. */
  async asking() {
    const kept = /** @type {any} */ (shared(CHAT_WAITS) ?? {})[String(this.tab)];
    if (this.told === undefined && kept?.address === this.address) {
      [this.since, this.told] = [kept.since, kept.told];            // a copy drawn anew: the wait told already
    }
    const status = this.agent?.status, said = ["working", "blocked", "done", "idle"].includes(status);
    const dialog = !this.pending && !said
      && screenChoices((await hc(["read", String(this.address)])).stdout).length > 0;
    this.blocked = !this.pending && (status === "blocked" || dialog) ? this.blocked ?? Date.now() : null;
    this.waits = chatWait(this.pending, this.blocked, Date.now());
    this.since = this.waits ? this.since ?? Date.now() : null;
    const wait = this.waits === "request" ? `request:${this.pending?.id}` : this.waits && `terminal:${this.blocked}`;
    if (wait && wait !== this.told) this.alert(this.waits === "request" ? cardFor(this.pending).title
      : "Asks in its terminal");
    this.told = wait || null;
    this.keepWait();
    if (this.waits === "terminal" && !this.hidden && !this.terminalShown() && this.inFront()) this.showTerminal(true);
    if (this.waits !== "terminal") {
      if (this.given && this.terminalShown()) {
        command("terminal.park", { terminal: String(this.address) });
        this.input.focus();                       // answered there: the keys back to the prompt
      }
      this.given = this.hidden = false;
    }
  }

  /** The chat's wait as the tab bar, Spaces and Chats read it (CHAT_WAITS), written only when it changed. */
  keepWait() {
    if (!this.tab) return;
    const kept = /** @type {any} */ (shared(CHAT_WAITS) ?? {});
    const wait = this.since ? { space: this.props.space, address: this.address, since: this.since, told: this.told }
      : null;
    const live = new Set(terminals().filter((t) => t.state === "live").map((t) => t.address));
    const next = keepWait(kept, this.tab, wait, live);
    if (JSON.stringify(next) !== JSON.stringify(kept)) setShared(CHAT_WAITS, next);
  }

  /** A new wait told, as Herdr tells an agent's: the blocked sound, and unless the chat is in front a toast (WHAT it
   * asks, its tab's name) that shows its tab when clicked. @param {string} what */
  alert(what) {
    if (!notesOn()) return;                       // Settings' An agent waits on you off: no note, no sound
    playSound("blocked");
    if (this.inFront() && window()?.active) return;
    const tab = spaces().flatMap((s) => s.tabs ?? []).find((c) => c.id === this.tab);
    notify({ title: `${this.adapter.name} needs you`, body: tab ? `${what} · ${tab.name}` : what, level: "error",
      ...(this.tab ? { action: { name: "tab.select", args: { id: this.tab } } } : {}) });
  }

  /** Whether the chat is the tab in front, its own pane focused (a pane can be split off it there). */
  inFront() {
    const now = focused();
    return Boolean(this.tab && now?.tab === this.tab
      && panes().some((p) => p.pane === now?.pane && p.tab === this.tab));
  }

  /** Whether the agent's terminal is in a pane (of its tab: the way out's, or the bar's toggle). */
  terminalShown() {
    return panes().some((p) => p.terminal === this.address);
  }

  /** The agent's own terminal shown under the chat in its tab (WAYOUT: by the way out, put away again once its agent
   * asks there no more), or put away; by hand, hidden while its agent asks there stays hidden till it asks no more. */
  showTerminal(wayOut = false) {
    if (!this.address) return;
    if (this.terminalShown()) {
      command("terminal.park", { terminal: this.address });
      this.hidden = this.waits === "terminal";
      this.given = false;
    } else if (this.inFront()) {
      command("terminal.keep", { terminal: this.address, place: "down" });
      this.given = wayOut || this.waits === "terminal";
      this.hidden = false;
    }
  }

  /** The mode in effect, as the adapter names it; null before the session file says. */
  get mode() {
    return this.named.mode ? modeOf(this.adapter, this.named.mode) : null;
  }

  /** The mode the chip names and the Modes panel checks: the one in effect, else the launch's (the one picked before
   * the agent started, else the one its settings start it in, else the adapter's first); null for an agent without. */
  modeShown() {
    const set = this.setup?.permissions?.mode;
    return this.mode ?? this.adapter.modes.find((m) => m.id === this.firstMode)
      ?? (typeof set === "string" ? modeOf(this.adapter, set) : null) ?? this.adapter.modes[0] ?? null;
  }

  /** MODE (its id) picked in the Modes panel, which closes: Claude's own shift+tab towards it (turn's); the empty
   * chat's: its agent's launch mode. @param {string} mode */
  pickMode(mode, cx) {
    this.showPanel(null, cx);
    if (mode === this.modeShown()?.id) return;
    if (!this.address) return void (this.firstMode = mode);
    [this.wanted, this.presses] = [mode, 0];
  }

  /** ⇧ + tab, as in Claude's own prompt: the next mode, Claude's own shift+tab sent and its screen read for it; the
   * empty chat's: the adapter's next. */
  cycleMode(cx) {
    if (this.address) {
      hc(["keys", this.address, "shift+tab"]);
      [this.recheck, this.read] = [2, 0];           // its mode line read off its screen at the next look
    } else {
      const modes = this.adapter.modes, at = modes.findIndex((m) => m.id === this.modeShown()?.id);
      if (modes.length) this.firstMode = modes[(at + 1) % modes.length].id;
    }
    cx.notify();
  }

  /** The mode as Claude's screen says it (its session file says one only with the next message), after a dialog, and
   * towards the mode asked for: Claude's own shift+tab, one press a read, at most once round its cycle. */
  async turn() {
    if (!(this.wanted || this.recheck) || !this.address) return;
    const now = screenMode(this.adapter, (await hc(["read", this.address])).stdout);
    if (now) this.named.mode = now;
    this.recheck = Math.max(0, this.recheck - 1);
    if (!this.wanted) return;
    if (now === this.wanted || this.presses > this.adapter.modes.length) {
      this.wanted = null;
      return;
    }
    this.presses += 1;
    await hc(["keys", this.address, "shift+tab"]);
  }

  /** REPLY (card.js's) to what Claude waits on, through the hook, or in Claude's own dialog by its key there (a No's
   * words typed after it); the card goes, the prompt comes back. */
  reply(reply, cx) {
    this.answered = reply.id;
    this.pending = null;
    this.answer?.reset(null);
    this.input.focus();                           // the card gone: the keys back to the prompt
    this.read = 0;                                // the turn goes on: read again at once
    cx.spawn(async () => {
      if (reply.key) {
        await hc(["keys", String(this.address), reply.key]);
        if (reply.text) await hc(["send", String(this.address), reply.text]);
        this.recheck = 4;                         // a dialog may change the mode: its line read off the screen
      }
      await this.core(CHAT, ["answer", this.session, JSON.stringify(reply)], this.space?.folder ?? "/", null);
    });
    cx.notify();
  }

  /** TEXT typed to the agent and sent (a working one queues it). @param {string} text */
  tell(text) {
    if (this.address) hc(["send", this.address, text]);
  }

  /** The prompt's text to the agent, the prompt emptied; the empty chat's first message starts it. */
  send(cx) {
    const text = withFiles(promptText(this.input.value()), this.files, this.folder(), this.adapter.files ?? "@");
    if (!text || (!this.address && !this.fresh)) return;
    if (this.fresh) this.begin(text, cx);
    else this.tell(text);
    this.files = [];
    this.input.set_value("");
    cx.notify();
  }

  /** The chat's folder: its own, else its space's; "" where neither is. */
  folder() {
    return String(this.props.folder || this.space?.folder || "");
  }

  /** Upload from computer… (the + menu's, ⌘ U): macOS's own chooser, the files picked attached to the next message,
   * each once; a failure said in a notice. */
  upload(cx) {
    if (!this.adapter.files || this.choosing) return;
    this.choosing = true;
    cx.spawn(async (cx) => {
      try {
        const done = await exec("osascript", ["-l", "JavaScript", "-e", CHOOSE, this.folder() || home()],
          { timeout: SAVING });
        if (done.code !== 0) throw new Error(lastLine(done));
        this.files = [...new Set([...this.files, ...uploadPaths(done.stdout)])];
      } catch (e) {
        notify({ title: "Couldn't attach the files", body: said(e), level: "error" });
      } finally {
        this.choosing = false;
        this.input.focus();
        cx.notify();
      }
    });
  }

  /** Add context's list read: the folder's files as a search walks them (core/search.py), the repository's changed
   * ones first (core/git.py's status; a deleted one has nothing to read); the list before it kept meanwhile. */
  listFiles(cx) {
    const folder = this.folder();
    if (!folder || this.space?.machine) return;
    cx.spawn(async (cx) => {
      try {
        const [found, top] = await Promise.all([
          this.core(SEARCH, [folder, JSON.stringify({ files: true, limit: LISTED })], folder, null),
          exec("git", ["-C", folder, "rev-parse", "--show-toplevel"]).then((done) => (done.code === 0
            ? done.stdout.trim() : "")).catch(() => "")]);
        const status = top ? await this.core(GIT, ["status", top], top, null).catch(() => null) : null;
        const changed = [...(status?.staged ?? []), ...(status?.changes ?? [])].filter((one) => one.code !== "D")
          .map((one) => `${top}/${one.path}`).filter((path) => path.startsWith(`${folder}/`))
          .map((path) => path.slice(folder.length + 1));
        [this.listed, this.listError] = [{ changed: [...new Set(changed)], files: found.files }, null];
      } catch (e) {
        if (!this.listed) this.listError = said(e);
      }
      cx.notify();
    });
  }

  /** The agent's servers as its setup tells them, Claude's own looks (a sign-in's end) over them. */
  servers() {
    return checkedOver(this.setup?.servers, this.checked);
  }

  /** The sign-ins running for the chat's agent, by server (the app's terminals tell them, as the Agent panel's). */
  signingIn() {
    return signIns(terminals(), this.agentKey);
  }

  /** A sign-in's step (ROW) as it stands now (timeline.js's signinRow): asked, signing in, done. @param {any} row */
  signin(row) {
    const starting = Object.fromEntries([...this.connecting].map((name) => [name, true]));
    return signinRow(String(row.server), this.servers(), { signing: { ...this.signingIn(), ...starting },
      failed: this.connectFailed, newer: this.setupAt > 0 && Date.parse(row.at ?? "") > this.setupAt });
  }

  /** Connect on a sign-in's step: the agent's own login for its server NAME (core's argv) in a terminal with no pane,
   * as the Agent panel's Connect, one per server; why it could not start said on the step. @param {string} name */
  connect(name, cx) {
    const folder = this.folder(), agent = this.agentKey;
    if (!folder || this.connecting.has(name) || this.signingIn()[name]) return;
    this.connecting.add(name);
    this.connectFailed = Object.fromEntries(Object.entries(this.connectFailed).filter(([one]) => one !== name));
    cx.notify();
    cx.spawn(async (cx) => {
      try {
        const argv = await this.core(CONNECTORS, ["login", agent, name], folder, null);
        const done = await hc(loginRun(argv, { agent, name, folder, at: Date.now() }));
        if (done.code !== 0) throw new Error(lastLine(done));
        this.signed.add(name);
      } catch (e) {
        this.connectFailed = { ...this.connectFailed, [name]: said(e) };
      } finally {
        this.connecting.delete(name);
        cx.notify();
      }
    });
  }

  /** Every WORKING ms, while the timeline holds a sign-in's step: one left waiting past its time is ended; a server
   * seen signing in whose terminal is gone (signed in, cancelled) is asked about again (settle's). */
  watchSignIns(cx) {
    if (!this.signed.size && !this.rows.some((row) => row.kind === "signin")) return;
    const running = this.signingIn(), ended = [...this.signed].filter((name) => !running[name]);
    const changed = ended.length > 0 || Object.keys(running).some((name) => !this.signed.has(name));
    if (this.signed.size) for (const address of overdue(terminals(), Date.now())) hc(["kill", "--", address]);
    this.signed = new Set(Object.keys(running));
    for (const name of ended) this.settle(name, cx);
    if (changed) cx.notify();
  }

  /** Server NAME's state asked for anew once its sign-in ended: the agent's own look (the adapter's check; a session's
   * lines tell nothing new) kept over the setup's word, else the setup read again. @param {string} name */
  settle(name, cx) {
    const folder = this.folder(), check = this.adapter.check;
    if (!check || !folder) return this.readSetup(cx);
    cx.spawn(async (cx) => {
      try {
        const answer = await this.core(AGENT_STATE, ["check", check, folder, name], folder, null);
        const base = (this.setup?.servers ?? []).find((/** @type {any} */ one) => one.name === name)?.state ?? null;
        this.checked = { ...this.checked, [name]: { base, state: answer.state } };
      } catch {
        // not checked: the step stays as the setup says
      }
      this.readSetup(cx);
      cx.notify();
    });
  }

  /** The chat's connectors as its + menu has them (plusMenu's): Claude's own looks over the setup's, a switch just
   * turned as asked till the setup says it. */
  connectors() {
    const now = Date.now(), menu = plusMenu(checkedOver(this.setup?.servers, this.checked));
    const asked = { ...this.switching, ...Object.fromEntries(this.toTell.map((one) => [one.name, { on: one.on,
      at: now }])) };
    const shown = switched(menu.rows, asked, now, ASKED);
    this.switching = shown.asked;
    return { ...menu, rows: shown.rows };
  }

  /** A connector's switch turned: shown at once, Claude told once it is idle (tellConnectors'); the empty chat's
   * waits for its agent. @param {string} name @param {boolean} on what it is now */
  flipConnector(name, on, cx) {
    if (!this.adapter.connectors) return;
    this.toTell = [...this.toTell.filter((one) => one.name !== name), { name, on: !on }];
    this.tellConnectors(cx);
    cx.notify();
  }

  /** Every WORKING ms and at a switch's turn: the next connector not told yet is told to an idle Claude in its own
   * words (core's toggle, `/mcp enable` or `disable`), its setup read again as Claude writes it; one Claude's name
   * for it does not allow is given up, said in a notice. */
  tellConnectors(cx) {
    const now = Date.now(), next = this.toTell[0];
    if (this.due.some((at) => at <= now)) {
      this.due = this.due.filter((at) => at > now);
      this.readSetup(cx);
    }
    if (!next || this.telling || !this.address || !["idle", "done"].includes(this.agent?.status)) return;
    this.telling = true;
    cx.spawn(async (cx) => {
      try {
        const words = await this.core(CONNECTORS, ["toggle", next.name, next.on ? "on" : "off"], this.folder(), null);
        const sent = await hc(["send", "--if", "idle", String(this.address), words]);
        if (sent.code !== 0) return;                // at work again: the next look tries
        this.switching = { ...this.switching, [next.name]: { on: next.on, at: Date.now() } };
        this.due = SETTLE.map((ms) => Date.now() + ms);
        this.toTell = this.toTell.filter((one) => one !== next);
      } catch (e) {
        this.toTell = this.toTell.filter((one) => one !== next);
        notify({ title: `Couldn't turn ${next.name} ${next.on ? "on" : "off"}`, body: said(e), level: "error" });
      } finally {
        this.telling = false;
        cx.notify();
      }
    });
  }

  /** The chat's switches on, as kept for it (the agent reports none). @returns {Record<string, boolean>} */
  switched() {
    return /** @type {any} */ (shared(SWITCHES) ?? {})[this.session] ?? {};
  }

  /** Switch SW turned over: its command sent, kept for the chat (a chat started again starts with it), and the agent's
   * screen read after ANSWER ms: refused, it is turned back, faint, Claude's words its tip. @param {any} sw */
  flip(sw, cx) {
    const on = !this.switched()[sw.id], command = switchCommand(this.adapter, sw.id, on);
    if (!command || (!this.address && !this.fresh)) return;
    if (this.address) this.tell(command);           // the empty chat's: on at its launch, through --settings
    const keep = (/** @type {boolean} */ value) => {
      const live = new Set(terminals().filter((c) => c.state === "live").map((c) => c.labels?.[CHAT_LABEL]));
      const kept = Object.fromEntries(Object.entries(/** @type {any} */ (shared(SWITCHES) ?? {}))
        .filter(([session]) => live.has(session) && session !== this.session));
      setShared(SWITCHES, { ...kept, [this.session]: { ...this.switched(), [sw.id]: value } });
    };
    keep(on);
    if (on && this.address) {
      cx.timer.after(ANSWER, (cx) => cx.spawn(async (cx) => {
        const why = switchRefused(this.adapter, sw.id, (await hc(["read", String(this.address)])).stdout);
        if (why) {
          keep(false);
          this.refused = { ...this.refused, [sw.id]: why };
        }
        cx.notify();
      }));
    }
    cx.notify();
  }

  /** The level the chip and the slider show: the one dragged or stepped to, else the one sent till the status line
   * says it, else the status line's, else the session file's, else the launch's (the one picked before the agent
   * started, else the one its settings start it with: the Agent panel's). */
  effortShown() {
    const said = this.status?.effort ?? this.named.effort, set = this.setup?.effort;
    if (this.asked && (this.asked.id === said || Date.now() - this.asked.at > ASKED)) this.asked = null;
    return this.draft ?? this.asked?.id ?? said ?? this.firstEffort
      ?? (this.adapter.efforts.some((e) => e.id === set) ? set : null);
  }

  /** LEVEL sent to the agent, unless it is in effect already; the slider then shows it till the status line says it.
   * The empty chat's: its agent's launch level. @param {string | null} level */
  setEffort(level) {
    this.draft = null;
    if (!level || level === this.effortShown()) return;
    if (!this.address) return void (this.firstEffort = level);
    this.tell(`/effort ${level}`);
    this.asked = { id: level, at: Date.now() };
  }

  /** ← or → (DIRECTION) on the panel's Effort row: the slider one level on, sent once the arrows rest. */
  stepEffort(direction, cx) {
    this.draft = nearEffort(this.adapter, this.effortShown(), direction);
    const at = (this.stepped = Date.now());
    cx.timer.after(REST, (cx) => {
      if (this.stepped !== at) return;
      this.setEffort(this.draft);
      cx.notify();
    });
  }

  /** The model the chip names and the panel checks, { id, label } (id null: one the adapter does not list): the one
   * picked till the agent names another (ASKED ms at most), else the agent's, else the launch's (the one picked
   * before it started, else the one its settings name, the Agent panel's, else the adapter's first, its default). */
  modelShown() {
    const said = this.status?.model ?? this.named.model ?? null;
    const row = modelOf(this.adapter, this.status?.model) ?? modelOf(this.adapter, this.named.model);
    const asked = this.modelAsked;
    if (asked && (asked.from !== said || Date.now() - asked.at > ASKED)) this.modelAsked = null;
    const id = this.modelAsked?.id ?? (said ? row?.id : this.firstModel ?? modelOf(this.adapter, this.setup?.model)?.id
      ?? this.adapter.models[0]?.id);
    const listed = this.adapter.models.find((m) => m.id === id);
    if (listed) return { id: listed.id, label: listed.label };
    return said ? { id: null, label: this.status?.model ?? modelName(String(said)) } : null;
  }

  /** MODEL (its id; null: the one in use, not listed) picked in the panel, which closes: sent to the agent as its own
   * /model, unless in use already; the empty chat's: its agent's launch model. @param {string | null} model */
  pickModel(model, cx) {
    this.showPanel(null, cx);
    if (!model || model === this.modelShown()?.id) return;
    if (!this.address) return void (this.firstModel = model);
    this.tell(`/model ${model}`);
    this.modelAsked = { id: model, at: Date.now(), from: this.status?.model ?? this.named.model ?? null };
  }

  /** The bar's panel WHICH open (the keys on no row till an arrow, but on the + menu's first, as the mockup's; the
   * setup read again) or none (a drag let go sends its level, the keys go back to the prompt).
   * @param {Panel | null} which */
  showPanel(which, cx) {
    if (!which && this.sliding) {
      this.sliding = false;
      this.setEffort(this.draft);
    }
    this.open = which;
    this.cursor = which === "commands" || which === "plus" ? 0 : null;    // their first row lit: Enter picks it
    this.listPlaces = [];
    if (which !== "commands") [this.typedMenu, this.query] = [false, ""];
    if (!which) this.input?.focus();
    if (which === "context" || which === "commands" || which === "plus") this.readSetup(cx);
    if (which === "context") this.readCosts(cx);
    if (which === "mention") this.listFiles(cx);
    cx.notify();
  }

  /** Whether a list stands over the prompt, following what is typed: the / menu, Add context's. */
  over() {
    return this.open === "commands" || this.open === "mention";
  }

  /** Add context's list as the prompt's text says: an "@" typed at a word's start opens it on what follows (its
   * first row lit), a space or the "@" gone closes it; one shut stays shut till the text changes (slashTyped's).
   * Whether anything changed. */
  mentionTyped(cx) {
    const mark = this.adapter.files, query = mark ? mentionQuery(this.input.value(), mark) : null;
    if (query !== null && this.shut === null && (this.open === null || this.open === "mention")) {
      if (this.open === "mention" && this.query === query) return false;
      if (this.open !== "mention") this.showPanel("mention", cx);
      [this.query, this.cursor] = [query, 0];
      return true;
    }
    if (this.open !== "mention") return false;
    [this.open, this.query, this.cursor] = [null, "", null];
    return true;
  }

  /** The / menu as the prompt's text says (a started chat's): "/" typed opens it on what follows (its first row lit),
   * a space, a new line or the "/" gone closes it; one shut (Esc, a press beside) stays shut till the text changes.
   * Whether anything changed. */
  slashTyped(cx) {
    const value = this.input.value(), query = this.fresh ? null : slashQuery(value);
    if (this.shut !== null && value !== this.shut) this.shut = null;
    if (query !== null && this.shut === null && (this.open === null || this.open === "commands")) {
      if (this.open === "commands" && this.typedMenu && this.query === query) return false;
      if (this.open !== "commands") this.showPanel("commands", cx);
      [this.typedMenu, this.query, this.cursor] = [true, query, 0];
      return true;
    }
    if (this.open !== "commands" || !this.typedMenu) return false;
    [this.open, this.typedMenu, this.query, this.cursor] = [null, false, "", null];
    return true;
  }

  /** The / menu's button: the menu shut if open; else "/" typed into an empty prompt (the menu follows what comes
   * after it), or over a message the menu opened as it is (a pick goes before the message); the keys stay in the
   * prompt. */
  slashButton(cx) {
    if (this.open === "commands") return this.showPanel(null, cx);
    if (Date.now() - this.shutAt < PRESS) return;           // the press beside it that just closed it was this one
    this.shut = null;
    if (!this.input.value()) this.input.set_value("/");
    this.slashTyped(cx);
    if (this.open !== "commands") this.showPanel("commands", cx);           // over a message: the menu as it is
    this.input.focus();
    cx.notify();
  }

  /** The / menu shut on the prompt's text as it is (a press beside it, Esc): open again once that text changes.
   * @param {boolean} keys the keys back to the prompt (Esc's; a press beside goes where it went) */
  shutMenu(keys, cx) {
    [this.shut, this.shutAt] = [this.input.value(), Date.now()];
    [this.open, this.typedMenu, this.query, this.cursor] = [null, false, "", null];
    if (keys) this.input.focus();
    cx.notify();
  }

  /** A key in the prompt while the / menu shows rows: ↑ ↓ step them, Esc shuts it (and never stops a working agent
   * then: a second Esc does); else Esc stops a WORKING agent. Enter is the prompt's submit (promptEvents'). */
  promptKey(e, cx, working) {
    const rows = this.over() ? this.menuRows() : [];
    if (rows.length && (e.key === "up" || e.key === "down")) {
      this.cursor = panelStep(rows.length, this.cursor, e.key === "down" ? 1 : -1, () => false, 0);
      keepInView(this);                           // a long list: the keys' row in view
    } else if ((rows.length || this.open === "mention") && e.key === "escape") this.shutMenu(true, cx);
    else return void (e.key === "escape" && working && hc(["interrupt", String(this.address)]));
    cx.stop_propagation();
    cx.notify();
  }

  /** A panel's ROW acted on (a press, Enter, Space): a model or mode picked, a switch turned, a file previewed, a
   * command sent or put in the prompt for its words (before a message under the menu; "/…" typed goes), the chat
   * exported, the dock's Agent panel shown; the panel then closes. @param {import("./agents.js").PanelRow} row */
  act(row, cx) {
    if (row.kind === "connector") return this.flipConnector(row.name, row.on, cx);   // the menu stays: one more
    if (row.kind === "upload" || row.kind === "context" || row.kind === "manage") {
      this.showPanel(null, cx);
      if (row.kind === "upload") return this.upload(cx);
      if (row.kind === "manage") return openAgentPanel({ agent: this.agentKey, section: "connectors" });
      this.shut = null;
      this.input.set_value(atTyped(this.input.value(), this.adapter.files ?? "@"));     // its list follows the "@"
      this.mentionTyped(cx);
      return this.input.focus();
    }
    if (row.kind === "mention") {
      const picked = mentionPick(this.input.value(), row.path, this.adapter.files ?? "@");
      [this.open, this.query, this.cursor] = [null, "", null];
      this.input.set_value(picked);
      this.input.focus();
      return void cx.notify();
    }
    if (row.kind === "agent") {                   // the chat's own agent's setup, whatever the space kept
      this.showPanel(null, cx);
      return openAgentPanel({ agent: this.agentKey });
    }
    if (row.kind === "usage") {                   // the Agents tab's Usage, this chat's row marked
      this.showPanel(null, cx);
      return openAgents({ view: "usage", session: this.session });
    }
    if (row.kind === "model") return this.pickModel(row.id, cx);
    if (row.kind === "mode") return this.pickMode(row.id, cx);
    if (row.kind === "file" || row.kind === "command" || row.kind === "export") {
      const kept = this.open === "commands" && !this.typedMenu ? this.input.value() : "";
      this.showPanel(null, cx);
      if (row.kind === "file") {
        const cut = row.path.lastIndexOf("/");
        return showPreview({ kind: "file", root: row.path.slice(0, cut) || "/", path: row.path.slice(cut + 1),
          on: null });
      }
      if (row.kind === "export" || !row.words) {
        if (this.input.value() !== kept) this.input.set_value(kept);
        return row.kind === "export" ? this.exportChat(cx) : this.tell(row.text);
      }
      this.input.set_value(`${row.text} ${kept}`);           // its words typed after it
      return this.input.focus();
    }
    const sw = row.kind === "switch" && this.adapter.switches.find((s) => s.id === row.id);
    if (sw && !this.refused[sw.id]) this.flip(sw, cx);
  }

  /** A key in an open panel (its ROWS): ↑ ↓ step them (from the one in use, over a switch refused), ← → the level on
   * Effort (sent once they rest), Enter or Space acts on the keys' row, Esc closes it (⇧ + tab: NEXT_MODE's).
   * @param {import("./agents.js").PanelRow[]} rows */
  panelKey(e, cx, rows) {
    const row = this.cursor === null ? null : rows[this.cursor];
    if (e.key === "escape") this.showPanel(null, cx);
    else if (e.key === "up" || e.key === "down") {
      const off = (/** @type {number} */ n) => rows[n].kind === "switch" && Boolean(this.refused[rows[n].id]);
      const shown = this.open === "model" ? this.modelShown()?.id ?? null : this.modeShown()?.id;
      this.cursor = panelStep(rows.length, this.cursor, e.key === "down" ? 1 : -1, off,
        rows.findIndex((r) => (r.kind === "model" || r.kind === "mode") && r.id === shown));
      keepInView(this);                           // a long list: the keys' row in view
    } else if ((e.key === "left" || e.key === "right") && row?.kind === "effort") {
      this.stepEffort(e.key === "right" ? 1 : -1, cx);
    } else if ((e.key === "enter" || e.key === "space") && row) this.act(row, cx);
    else return;
    cx.stop_propagation();                          // never the prompt's (its Esc stops a working agent)
    cx.notify();
  }

  /** A panel's surface, WIDE px (the app's popover, a menu's frame), its ROWS, what is DRAWN for them, the HEAD over
   * them; its KEYS its own (the / menu's stay in the prompt). @param {number} wide
   * @param {import("./agents.js").PanelRow[]} rows @param {any[]} drawn @param {any} [head] @param {boolean} [keys] */
  surface(t, wide, rows, drawn, head = null, keys = true) {
    return panelSurface(t, `${this.open ?? "panel"}-surface`, wide).p(R.pad).gap(2)
      .when(keys, (e) => e.track_focus(this.panelFocus).key_context(CHAT_KEYS)
        .on_key_down((e, cx) => this.panelKey(e, cx, rows)))
      .when(this.open === "modes", (e) => e.on_action(NEXT_MODE, (_e, cx) => this.cycleMode(cx)))
      .when(this.open === "plus", (e) => e.on_action(UPLOAD, (_e, cx) => this.act({ kind: "upload" }, cx)))
      .when(Boolean(head), (e) => e.child(head)).children(drawn);
  }

  /** A choice's words (a model's, a mode's): its NAME, medium, its LINE dim under it, wrapping where long; ✓ at the
   * row's end on the one in use. @param {string} name @param {string} line @param {boolean} on */
  choice(t, name, line, on) {
    return [v_flex().flex_1().min_w(0).child(div().font_medium().line_height(`${R.text}px`).child(name))
      .child(div().text_size(12).line_height("16px").text_color(t.dim).child(line)),
    div().w(16).flex_none().self_center().text_color(t.foreground).when(on, (e) => e.child(icon("check", 14)))];
  }

  /** The model chip's panel, upward from it (VS Code's Claude's picker, the Modes panel's rows): the adapter's models,
   * each its name over its line, the one in use ✓ on the accent's tint; a press picks one, and it closes. */
  modelPanel(t) {
    const shown = this.modelShown(), rows = modelRows(this.adapter, shown), started = Boolean(this.address);
    return this.surface(t, MODELS, rows, rows.map((row, n) => {
      const model = /** @type {{ id: string | null, label: string, description: string }} */ (row);
      const on = model.id === (shown?.id ?? null);
      return panelRow(t, this, n, true, on).items_start().cursor_pointer().on_click((_e, cx) => this.act(row, cx))
        .when(started && model.id !== null, (e) => e.tooltip(`${this.adapter.name} may keep it as the default for `
          + "new chats, as its own /model does"))
        .children(this.choice(t, model.label, model.description, on));
    }));
  }

  /** The mode chip's panel, upward from it, as center-chat.html's Modes: its head (⇧ + tab to switch), the adapter's
   * modes (its icon, its name over its line, ✓ on the tint), a rule, Effort (its slider, the level's name at the end),
   * each switch (Ultracode, its switch at the end); none an agent lacks. Rows keep their height: nothing moves. */
  modesPanel(t) {
    const rows = modeRows(this.adapter), shown = this.modeShown(), level = this.effortShown();
    const started = Boolean(this.address), mark = (/** @type {any} */ name) => div().w(24).flex_none().flex()
      .justify_center().text_color(t.muted).child(icon(name, 18));
    const head = h_flex().h(32).flex_none().px(R.inset).gap(R.pad).items_center().text_color(t.muted)
      .child(div().flex_1().font_medium().child("Modes")).child(h_flex().gap(R.pad).items_center().text_size(11)
        .text_color(t.dim).child(keyCap(t, "⇧")).child("+").child(keyCap(t, "tab")).child("to switch"));
    const drawn = rows.map((row, n) => {
      if (row.kind === "mode") {
        const mode = /** @type {import("./agents.js").Mode} */ (this.adapter.modes.find((m) => m.id === row.id));
        const on = mode.id === shown?.id;
        return panelRow(t, this, n, true, on).items_start().cursor_pointer().on_click((_e, cx) => this.act(row, cx))
          .child(mark(mode.icon).mt(1)).children(this.choice(t, mode.label, mode.description, on));
      }
      if (row.kind === "effort") {
        return panelRow(t, this, n, true).child(mark("audio-lines")).child(div().id("effort-name").flex_1()
          .child("Effort").when(started, (e) => e.tooltip(`${this.adapter.name} keeps it as the model's default, as `
            + "its own /effort does")))
          .child(this.slider(t, level)).child(div().w(LEVEL).flex_none().text_right()
            .text_color(level ? t.foreground : t.dim).child(level ? effortLabel(this.adapter, level) : "Default"));
      }
      const sw = /** @type {import("./agents.js").Switch} */ (this.adapter.switches.find((s) => s.id === row.id));
      const why = this.refused[sw.id];
      return panelRow(t, this, n, !why).tooltip(why ?? sw.tip)
        .when(!why, (e) => e.cursor_pointer().on_click((_e, cx) => this.act(row, cx)))
        .child(mark("leaf")).child(div().flex_1().text_color(why ? t.dim : t.foreground).child(sw.label))
        .child(toggle(t, `switch-${sw.id}`, Boolean(this.switched()[sw.id]) && !why, !why, (cx) => {
          cx.stop_propagation();                    // the row's own press would turn it back
          this.act(row, cx);
        }));
    });
    const modes = this.adapter.modes.length;
    return this.surface(t, MODES, rows, [...drawn.slice(0, modes), ...(modes && modes < rows.length ? [rule(t)] : []),
      ...drawn.slice(modes)], head);
  }

  /** The effort's slider (center-chat.html's): a pill on the terminals' background, a stop for each of the agent's
   * levels (a dot, the knob on LEVEL; none: the agent's own); a press or a drag picks, sent once let go. A stop is
   * the knob's room: nothing moves. @param {string | null} level */
  slider(t, level) {
    const pick = (/** @type {any} */ e, /** @type {any} */ cx) => {
      const at = effortAt(this.adapter, e.local_position?.x ?? 0, 0);
      if (at !== this.draft) {
        this.draft = at;
        cx.notify();
      }
    };
    const letGo = (/** @type {any} */ cx) => {
      if (!this.sliding) return;
      this.sliding = false;
      this.setEffort(this.draft);
      cx.notify();
    };
    return h_flex().id("effort-track").h(SLIDER.high).px(SLIDER.pad).flex_none().items_center().rounded_full()
      .bg(t.canvas).cursor_pointer()
      .on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();
        this.sliding = true;
        pick(e, cx);
      })
      .on_mouse_move((e, cx) => void (this.sliding && pick(e, cx)))
      .on_mouse_up("left", (_e, cx) => letGo(cx))
      .on_hover((over, cx) => void (!over && letGo(cx)))
      .children(this.adapter.efforts.map((stop) => div().w(SLIDER.stop).h_full().flex().items_center()
        .justify_center().child(stop.id === level ? div().size(SLIDER.knob).rounded_full().bg(t.foreground)
          : div().size(SLIDER.dot).rounded_full().bg(t.input ?? t.border))));
  }

  /** Row N of the / menu's or the Context panel's list: the panels' one row (panelRow's) on a list's line; a press
   * acts on ROWS' N. @param {number} n @param {any[]} rows */
  listRow(t, n, rows) {
    return panelRow(t, this, n, true).cursor_pointer().on_click((_e, cx) => this.act(rows[n], cx));
  }

  /** What the / menu offers, in center-chat.html's parts: This chat (Export the chat…, once there is one), the skills
   * (those the chat used first; a skill as the agent takes it, for its words; Lucide's scroll-text among the other
   * kinds), the agent's own commands. @returns {import("./agents.js").SlashItem[]} */
  slashItems() {
    /** @type {import("./agents.js").SlashItem[]} */
    const items = [];
    if (this.rows.length) {
      items.push({ part: "This chat", name: "Export the chat…", typed: null, line: "", tag: null,
        icon: "download", row: { kind: "export" } });
    }
    const skills = (this.setup?.skills ?? []).filter((/** @type {any} */ one) => !one?.off);     // on in this folder
    for (const skill of this.adapter.skill ? menuSkills(this.adapter, this.rows, skills) : []) {
      const typed = String(skillCommand(this.adapter, skill));
      items.push({ part: "Skills", name: skill.name, typed, line: skill.description, tag: skill.source,
        icon: "scroll-text", row: { kind: "command", text: typed, words: true } });
    }
    for (const c of this.adapter.commands) {
      items.push({ part: `${this.adapter.name}'s commands`, name: c.name, typed: c.name, line: c.description,
        tag: null, icon: "square-slash", row: { kind: "command", text: c.name, words: Boolean(c.words) } });
    }
    return items;
  }

  /** The / menu as shown (slashMenu's): its parts, a few of each, or what is typed after the "/" finds. */
  slashShown() {
    return slashMenu(this.slashItems(), this.typedMenu ? this.query : null, FEW);
  }

  /** Add context's list as shown (mentionMenu's): the changed files and the folder's, a few of each, or what is typed
   * after the "@" finds. */
  mentionShown() {
    return mentionMenu(this.listed?.changed ?? [], this.listed?.files ?? [], this.query, FEW);
  }

  /** The rows of the list over the prompt as shown (the / menu's, Add context's), the keys' row among them.
   * @returns {import("./agents.js").PanelRow[]} */
  menuRows() {
    return (this.open === "mention" ? this.mentionShown() : this.slashShown()).parts.flatMap((part) =>
      part.items.map((item) => item.row));
  }

  /** Add context's list, over the prompt in the / menu's form: Changed, Files, a few of each and how many more;
   * typed after "@", what it finds, the best first, lit (a press or Enter names it in the prompt); while it is
   * read, why it could not be, or with none, a line saying so. */
  mentionPanel(t) {
    const menu = this.mentionShown();
    /** @type {import("./agents.js").PanelRow[]} */
    const rows = [];
    /** @type {any[]} */
    const items = [], places = [];
    for (const part of menu.parts) {
      if (part.name) items.push(groupHead(t, part.name));
      for (const item of part.items) {
        places.push(items.length);
        items.push(this.listRow(t, rows.push(item.row) - 1, rows).child(fileMark(fileIcon(item.name)))
          .children(listWords(t, null, item.name, item.line, null)));
      }
    }
    if (menu.more > 0) items.push(listNote(t, `${menu.more} more · type to search`).pt(6));
    if (!items.length) {
      items.push(listNote(t, this.listError ? `Couldn't list the files: ${this.listError}` : !this.listed
        ? "Listing the files…" : this.query ? "No file matches" : "No files here", Boolean(this.listError),
      R.inset).pt(R.gap));
    }
    return this.surface(t, COMMANDS, rows, [panelList(this, "mention-list", items, places)], null, false);
  }

  /** The + menu (connectors.html's), upward from the +: Upload from computer… and Add context… with their keys (an
   * agent that takes files), a rule, then Connectors (one a chat switches them of): the failed and sign-in ones on
   * pills, Manage (the Agent panel's Connectors), each one on or off in this folder with its logo and switch. */
  plusPanel(t) {
    const files = Boolean(this.adapter.files), ground = t.popover ?? t.raised;
    /** @type {import("./agents.js").PanelRow[]} */
    const rows = [];
    const row = (/** @type {import("./agents.js").PanelRow} */ next) => this.listRow(t, rows.push(next) - 1, rows);
    const keys = (/** @type {string[]} */ ...caps) => h_flex().flex_none().gap(R.pad)
      .children(caps.map((cap) => keyCap(t, cap, 16)));
    const drawn = files ? [
      row({ kind: "upload" }).children(listWords(t, "arrow-up-from-line", "Upload from computer…", "", null))
        .child(keys("⌘", "U")),
      row({ kind: "context" }).children(listWords(t, "at-sign", "Add context…", "", null)).child(keys("@"))] : [];
    if (!this.adapter.connectors) return this.surface(t, PLUS, rows, drawn);
    const menu = this.connectors(), manage = rows.push({ kind: "manage" }) - 1;
    if (files) drawn.push(rule(t));
    // its head (connectors.html's .phead): the part's name, the problems' pills, the link at the end, its words' end
    // with the switches'
    drawn.push(h_flex().h(32).flex_none().pl(R.inset).pr(R.pad).gap(6).items_center()
      .child(div().flex_none().mr(R.pad).text_size(12).font_semibold().text_color(t.muted).child("Connectors"))
      .children(menu.pills.map((pill) => {
        const { fill, ink } = chipColors(t, pill.tone, 0, ground);
        return div().h(16).flex_none().px(6).flex().items_center().rounded(4).bg(fill).text_size(11)
          .line_height("16px").font_medium().text_color(ink).child(pill.text);
      }))
      .child(div().flex_1())
      .child(div().id(`panel-${manage}`).h(24).flex_none().px(R.gap).flex().items_center().rounded(6).text_size(12)
        .text_color(linkInk(t)).cursor_pointer().when(this.cursor === manage, (e) => e.bg(t.hover))
        .on_mouse_move((_e, cx) => void (this.cursor !== manage && ((this.cursor = manage), cx.notify())))
        .on_click((_e, cx) => this.act(rows[manage], cx)).child("Manage")));
    for (const one of menu.rows) {
      const next = /** @type {const} */ ({ kind: "connector", name: one.name, on: one.on });
      drawn.push(row(next).child(brandMark(t, one.brand, one.label))
        .child(div().flex_1().min_w(0).truncate().line_height("16px").text_color(one.on ? t.foreground : t.muted)
          .child(one.label))
        .child(toggle(t, `connector-${rows.length - 1}`, one.on, true, (cx) => {
          cx.stop_propagation();                    // the row's own press would turn it back
          this.act(next, cx);
        }, true)));
    }
    if (!menu.rows.length) {
      drawn.push(listNote(t, this.setupError ? `Couldn't read the connectors: ${this.setupError}` : !this.setup
        ? "Reading the connectors…" : "None on in this folder", Boolean(this.setupError), R.inset));
    }
    return this.surface(t, PLUS, rows, drawn);
  }

  /** The / menu (center-chat.html's), over the prompt: This chat, the skills, the agent's commands, a few of
   * each and how many more; typed after "/", what it finds, the best first, lit (a press or Enter acts on it). Null
   * while nothing is shown. */
  commandsPanel(t) {
    const menu = this.slashShown();
    if (!menu.parts.length) return null;
    /** @type {import("./agents.js").PanelRow[]} */
    const rows = [];
    /** @type {any[]} */
    const items = [], places = [];
    for (const part of menu.parts) {
      if (part.name) items.push(groupHead(t, part.name));
      for (const item of part.items) {
        places.push(items.length);
        items.push(this.listRow(t, rows.push(item.row) - 1, rows)
          .children(listWords(t, /** @type {any} */ (item.icon), item.name, item.line, item.tag)));
      }
    }
    if (menu.more > 0) items.push(listNote(t, `${menu.more} more · type to search`).pt(6));
    return this.surface(t, COMMANDS, rows, [panelList(this, `${this.open ?? "panel"}-list`, items, places)], null,
      false);
  }

  /** The chat as Markdown (core/chats.py's, Copy chat's), saved where macOS's save panel says, named after
   * it in the chat's folder at first (a file there replaced as the panel asks); a failure said in a notice. */
  exportChat(cx) {
    const folder = String(this.props.folder || this.space?.folder || home());
    cx.spawn(async () => {
      try {
        const { markdown } = await this.core(CHATS, ["markdown", this.agentKey, this.session], folder, null);
        if (typeof markdown !== "string") throw new Error("its file is gone");
        const path = await savePanel("Export the chat", exportName(markdown), folder);
        if (path) await writeTextFile(path, markdown, await readTextFile(path));
      } catch (e) {
        notify({ title: "Couldn't export the chat", body: said(e), level: "error" });
      }
    });
  }

  /** The Context panel (center-chat.html's, usage.html's), upward from the context meter: the use in numbers, a bar
   * of what fills it with its legend (each part in the Agent panel's colors), what this chat cost; under a hairline
   * Compact and Show all in Agent (the dock's panel, where the rules, skills and connectors are listed). */
  contextPanel(t) {
    const parts = contextParts(this.status, this.setup), named = parts.filter((p) => p.label);
    /** @type {import("./agents.js").PanelRow[]} */
    const rows = [];
    const cost = costBlock(this.costs), usage = cost ? rows.push({ kind: "usage" }) - 1 : -1;
    const compact = this.adapter.compact, n = compact ? rows.push({ kind: "command", text: compact, words: false }) - 1
      : -1;
    const all = this.adapter.setup ? rows.push({ kind: "agent" }) - 1 : -1;
    const foot = (/** @type {number} */ at) => div().id(`panel-${at}`).h(BUTTON).px(R.inset).flex().items_center()
      .rounded(6).text_size(12).cursor_pointer()
      .on_mouse_move((_e, cx) => void (this.cursor !== at && ((this.cursor = at), cx.notify())))
      .on_click((_e, cx) => this.act(rows[at], cx));
    return this.surface(t, CONTEXT, rows, [
      // the Modes panel's head: the panel's name muted, what it says at the end (here the use, in the text's color)
      h_flex().h(32).flex_none().px(R.inset).gap(R.gap).items_center().text_color(t.muted)
        .child(div().flex_1().font_medium().child("Context"))
        .child(div().flex_none().text_size(12).text_color(t.foreground)
          .child(this.status ? contextLine(this.status) : "")),
      h_flex().h(8).flex_none().mx(R.inset).gap(2).rounded(4).bg(t.canvas).overflow_hidden()
        .children(parts.filter((p) => p.share > 0).map((p, n, shown) => div().h_full().flex_none().min_w(2)
          .when(n === 0, (e) => e.rounded_l(4)).when(n === shown.length - 1, (e) => e.rounded_r(4))
          .w(`${Math.min(100, p.share * 100)}%`).bg(partColor(t, p.key)))),
      ...(named.length ? [h_flex().flex_none().flex_wrap().px(R.inset).pt(R.gap).pb(R.pad).gap_x(R.inset)
        .gap_y(R.pad).text_size(12).text_color(t.muted).children(named.map((p) => h_flex().flex_none().gap(6)
          .items_center().child(swatch(partColor(t, p.key))).child(`${p.label} ${tokens(Math.round(p.tokens))}`)))]
        : []),
      ...(cost ? [this.costBlock(t, cost, usage)] : []),
      // under a hairline: Compact, its edge with the rows' and its word over their icons; the link at the end, in the
      // accent as words read it on the hover's fill, its end with the tags'
      ...(compact || all >= 0 ? [h_flex().flex_none().mt(R.pad).pt(R.gap).items_center().border_t_1()
        .border_color(t.border)
        .when(Boolean(compact), (e) => e.child(foot(n).bg(this.cursor === n ? t.hover : t.raised).child("Compact")))
        .child(div().flex_1())
        .when(all >= 0, (e) => e.child(foot(all).when(this.cursor === all, (e) => e.bg(t.hover))
          .text_color(linkInk(t)).child("Show all in Agent")))] : []),
    ]);
  }

  /** The Context panel's cost block (usage.html's .ctxcost) under a hairline: This chat's figure 15 semibold with
   * core's word, a row a model (square, name, figure), the tokens' line and Usage (the panel's row AT).
   * @param {NonNullable<ReturnType<typeof costBlock>>} cost @param {number} at */
  costBlock(t, cost, at) {
    const line = (/** @type {any} */ name, /** @type {any} */ figure, /** @type {string} */ unit) => h_flex().h(20)
      .flex_none().px(R.inset).gap(R.gap).items_center().child(h_flex().flex_1().min_w(0).gap(6).items_center()
        .children([name].flat()))
      .child(figure).child(div().w(UNIT).flex_none().truncate().text_color(t.muted).child(unit));
    return v_flex().flex_none().mt(R.pad).pt(R.gap).border_t_1().border_color(t.border).text_size(12)
      .text_color(t.muted)
      .child(line(div().child(cost.label), div().flex_none().text_size(15).font_semibold()
        .text_color(t.foreground).child(cost.figure), cost.unit).h(24))
      .children(cost.rows.map((row) => line([swatch(row.color), div().min_w(0).truncate().child(row.name)],
        div().flex_none().font_medium().text_color(/\d/.test(row.figure) ? t.foreground : t.muted).child(row.figure),
        "")))
      .child(h_flex().h(BUTTON).flex_none().mt(2).pl(R.inset).items_center()
        .child(div().flex_1().min_w(0).truncate().child(cost.line))
        .child(div().id(`panel-${at}`).h(BUTTON).px(R.inset).flex().items_center().rounded(6)
          .cursor_pointer().text_color(linkInk(t)).when(this.cursor === at, (e) => e.bg(t.hover))
          .on_mouse_move((_e, cx) => void (this.cursor !== at && ((this.cursor = at), cx.notify())))
          .on_click((_e, cx) => this.act({ kind: "usage" }, cx)).child("Usage")));
  }

  /** A row's key, its place in the timeline (rows only ever come after it). @param {number} index */
  key = (index) => String(index);

  /** Whether row INDEX is open: as clicked, else as it starts. @param {number} index */
  isOpen(index) {
    return this.opened.get(this.key(index)) ?? Boolean(this.rows[index]?.open);
  }

  render(t, code) {
    const frame = v_flex().id("chat").size_full().min_h(0).bg(t.surface).text_color(t.foreground).text_size(13);
    const name = this.adapter.name;
    const line = this.note ?? (this.address ? `Waiting for ${name}…` : `Starting ${name}…`);
    if (this.fresh && !this.note) return frame.child(this.welcome(t)).child(this.bottom(t, code));
    return frame.child(this.rows.length ? this.timeline(t, code)
      : div().flex_1().p(R.edge).text_size(12).text_color(this.note ? t.ansi1 : t.dim).child(line))
      .when(Boolean(this.address), (e) => e.child(this.bottom(t, code)));
  }

  /** The empty chat's words in its middle, high up, as decisions.html's: New chat, and in the space · its branch. */
  welcome(t) {
    const where = [this.space?.name ?? "", this.branch].filter(Boolean).join(" · ");
    return v_flex().id("welcome").flex_1().min_h(0).pt(64).px(R.edge).gap(R.pad).items_center()
      .child(div().text_size(15).font_semibold().child(NEW))
      .when(Boolean(where), (e) => e.child(div().text_size(12).text_color(t.dim).child(`in ${where}`)));
  }

  /** The timeline, held at its end as rows come (GPUI's scroll areas start at their top, so it scrolls itself: its
   * rows stand on its bottom edge, BACK px below it once the wheel takes them back); its latest SHOWN rows. */
  timeline(t, code) {
    const from = Math.max(0, this.rows.length - this.shown);
    const place = bottomLayout(this.carded());
    return div().id("timeline").flex_1().min_h(0).relative().overflow_hidden()
      .on_size_change((size, cx) => this.measured(size.height, this.content, cx))
      .on_scroll_wheel((event, cx) => this.scrolled(event.delta.y, cx))
      .child(v_flex().id("timeline-rows").absolute().left_0().right_0().bottom(-this.back).pb(place.rows)
        .on_size_change((size, cx) => this.measured(this.view, size.height, cx))
        .when(from > 0, (e) => e.child(div().w_full().flex().justify_center().py(R.gap)
          .child(div().id("earlier").px(R.inset).py(R.pad).rounded(10).border(1).border_color(t.border).text_size(12)
            .text_color(t.muted).cursor_pointer().hover((s) => s.bg(t.hover)).child("Show earlier")
            .on_click((_e, cx) => {
              this.shown += SHOWN;
              cx.notify();
            }))))
        .children(this.rows.slice(from).map((_row, n) => this.row(t, code, from + n))))
      .when(this.back > 0, (e) => e.child(div().absolute().bottom(R.turn).left_0().right_0().flex().justify_center()
        .child(div().id("latest").px(R.inset).py(R.pad).rounded(10).bg(t.raised).border(1).border_color(t.border)
          .text_size(12).cursor_pointer().hover((s) => s.bg(t.hover)).child("Jump to latest")
          .on_click((_e, cx) => {
            this.back = 0;
            cx.notify();
          }))));
  }

  /** The timeline VIEW px high, its rows CONTENT px: rows come while scrolled back keep the reader's place. */
  measured(view, content, cx) {
    if (view === this.view && content === this.content) return;
    if (this.back > 0 && content > this.content) this.back += content - this.content;
    this.view = view;
    this.content = content;
    this.back = Math.min(this.back, Math.max(0, content - view));
    cx.notify();
  }

  /** The wheel's DY px: back into the chat, or towards its end; never past either. */
  scrolled(dy, cx) {
    const back = Math.min(Math.max(0, this.back + dy), Math.max(0, this.content - this.view));
    if (back === this.back) return;
    this.back = back;
    cx.notify();
  }

  /** Under the timeline, as wide as its column: a usage limit near its end and a budget near or past its own (each
   * closed by its ×), the plan strip, then what Claude waits on in the prompt's place, else the prompt and its bar. */
  bottom(t, code) {
    const limit = limitNotice(this.status, this.dismissed), budget = budgetNotice(this.budget, this.dismissed);
    const place = bottomLayout(this.carded());
    const notice = (/** @type {string} */ id, /** @type {string} */ text, /** @type {(cx: any) => void} */ close) =>
      h_flex().px(R.inset).py(R.inner).gap(R.gap).rounded(8).bg(t.ansi3 + "1f").border(1)
        .border_color(t.ansi3 + "40").text_size(12).text_color(t.ansi3)
        .child(div().flex_1().min_w(0).child(text))
        .child(iconButton(t, id, "x", "Close", close, { size: 12, color: t.ansi3 }));
    return div().w_full().flex().justify_center().px(R.edge).pb(R.foot).pt(place.top)
      .child(v_flex().w_full().max_w(COLUMN).gap(R.gap).relative()
        .when(place.line > 0 && !limit && !budget, (e) => e.child(div().absolute().top(-place.line).left(4).w(1)
          .h(place.line).bg(t.border)))           // the line on to the card's edge
        .when(Boolean(limit), (e) => e.child(notice("notice-close", limit?.text ?? "", (cx) => {
          if (limit) this.dismissed.add(limit.key);
          cx.notify();
        })))
        .when(Boolean(budget), (e) => e.child(notice("budget-close", budget?.text ?? "",
          (cx) => budget && this.closeBudget(budget.key, cx))))
        .when(Boolean(this.plan), (e) => e.child(this.strip(t)))
        .child(this.answer?.card ? this.answer.render(t, code) : this.waits === "terminal" ? this.wayOut(t)
          : this.prompt(t)));
  }

  /** The plan strip, the task list's one home: folded a line (the step at work, how many are done), pressed it opens
   * upward: the done steps one row (pressed: listed, faint), the rest in order, what a step waits for at its end, the
   * approved plan's link in its head. Folded while a card waits. */
  strip(t) {
    const open = this.planOpen && !this.carded(), strip = planStrip(this.plan, open, this.doneOpen);
    if (!strip) return div();
    const mark = (/** @type {string | null} */ state) => div().w(14).flex_none().flex().justify_center()
      .child(state === "now" ? spinner(t) : state === "done" || state === "fold" ? icon("check", 12).text_color(t.done)
        : div().size(10).rounded_full().border(1).border_color(t.dim));
    const head = h_flex().id("plan-head").h(34).pl(R.inset).pr(R.gap).gap(R.gap).items_center().cursor_pointer()
      .on_click((_e, cx) => {
        this.planOpen = !open;
        cx.notify();
      })
      .when(strip.head.state !== null, (e) => e.child(mark(strip.head.state)))
      .child(div().flex_1().min_w(0).truncate().child(strip.head.text))
      .when(Boolean(strip.head.count), (e) => e.child(div().flex_none().text_size(12).text_color(t.muted)
        .child(strip.head.count)))
      .when(open && this.plan.plan !== null, (e) => e.child(this.planLink(t, "plan-open")))
      .child(icon(open ? "chevron-down" : "chevron-up", 12).text_color(t.dim));
    const row = (/** @type {{ kind: string, text: string, after: string | null }} */ one, /** @type {number} */ n) =>
      h_flex().id(`plan-${n}`).h(26).px(R.inset).gap(R.gap).items_center()
        .text_color(one.kind === "done" || one.kind === "fold" ? t.muted : t.foreground).child(mark(one.kind))
        .child(div().min_w(0).truncate().child(one.text))
        .when(one.kind === "fold", (e) => e.cursor_pointer().child(fold("plan-done", this.doneOpen, 12, t.dim))
          .on_click((_e, cx) => {
            this.doneOpen = !this.doneOpen;
            cx.notify();
          }))
        .when(Boolean(one.after), (e) => e.child(div().flex_1()).child(div().min_w(0).flex_shrink(AFTER_SHRINK)
          .truncate().text_size(12).text_color(t.dim).child(String(one.after))));
    return v_flex().id("plan").w_full().rounded(10).border(1).border_color(t.border).bg(t.chrome).text_size(13)
      .child(head)
      .when(open, (e) => e.child(v_flex().pt(R.pad).pb(R.pad).border_t(1).border_color(t.border)
        .children(strip.rows.map(row))));
  }

  /** Open the plan: the approved plan as a document in the preview tab, from the strip's head and its step. */
  planLink(t, id) {
    return div().id(id).flex_none().text_size(12).text_color(linkInk(t)).cursor_pointer().child("Open the plan")
      .on_mouse_down("left", (_e, cx) => cx.stop_propagation())      // not its row's press, nor the strip's head's
      .on_click((_e, cx) => {
        cx.spawn(async () => {
          const { path } = await this.core(CHAT, ["plan", this.session], this.space?.folder ?? "/", null);
          const cut = String(path ?? "").lastIndexOf("/");
          if (path) showPreview({ kind: "file", root: path.slice(0, cut), path: path.slice(cut + 1), on: null });
        });
      });
  }

  /** The way out, in the prompt's place while the agent asks in its own terminal: a card's head saying so, its
   * terminal shown under the chat (Hide terminal puts it away, Show terminal brings it back). */
  wayOut(t) {
    const shown = this.terminalShown();
    return h_flex().id("way-out").h(CARD_HEAD).pl(R.card).pr(R.gap).gap(R.gap).items_center().rounded(10).border(1)
      .border_color(t.ansi3 + "59").bg(t.chrome).text_size(13)
      .child(div().flex_none().font_semibold().child(`${this.adapter.name} asks in its terminal`))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(shown ? "Answer it below" : ""))
      .child(h_flex().id("way-out-terminal").h(24).px(R.gap).flex_none().items_center().rounded(6).bg(t.raised)
        .text_size(12).text_color(t.foreground).cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => {
          this.showTerminal();
          cx.notify();
        }).child(shown ? "Hide terminal" : "Show terminal"));
  }

  /** Whether a card stands in the prompt's place (what Claude waits on, or its asking in its own terminal): a step on
   * the timeline's line, a step gap under the last one. */
  carded() {
    return Boolean(this.answer?.card) || this.waits === "terminal";
  }

  /** The prompt: what is typed, its words while empty (the agent's name; a working one queues a message, Esc stops
   * it), its bar. */
  prompt(t) {
    const working = this.agent?.status === "working";
    this.blank = !this.input.value();
    // center-chat.html's .box: the field 48 high at least (16 over the words, 16 in, 12 at the right, 8 under), its
    // frame the theme's input line, lifted off the timeline by a shadow
    const box = v_flex().id("prompt").w_full().rounded(10).border(1)
      .border_color(this.typing ? t.accent : t.input ?? t.border).bg(t.chrome).shadow_lg().key_context(CHAT_KEYS)
      .on_action(NEXT_MODE, (_e, cx) => void (this.modeShown() && this.cycleMode(cx)))
      .on_action(UPLOAD, (_e, cx) => this.upload(cx))
      .on_key_down((e, cx) => this.promptKey(e, cx, working))
      .when(this.files.length > 0, (e) => e.child(this.attached(t)))
      .child(div().relative().min_h(48).child(Textarea.new(this.input).pl(16).pr(R.inset).pt(16).pb(R.gap)
        .text_size(13))
        .when(this.blank, (e) => e.child(h_flex().absolute().top(16).left(16).gap(R.inner).items_center()
          .text_size(13)
          .text_color(t.dim).when(working, (e) => e.child("Queue another message ·").child(keyCap(t, "esc"))
            .child("to interrupt")).when(!working, (e) => e.child(`Message ${this.adapter.name}`)))))
      .child(this.bar(t));
    // the / menu over the prompt, its left edge with the prompt's, 8 over it (center-chat.html's .cmds): what is
    // typed stays in view, and the keys in the prompt; a press beside it shuts it
    const menu = this.open === "commands" && !this.fresh ? this.commandsPanel(t)
      : this.open === "mention" ? this.mentionPanel(t) : null;
    if (this.inPlace) return v_flex().w_full().when(menu !== null, (e) => e.child(/** @type {any} */ (menu).mb(R.gap)))
      .child(box);
    return Popup.new("commands-panel", box).w_full().anchor("bottom_left")
      .when(menu !== null, (e) => e.content(/** @type {any} */ (menu).mb(R.gap)
        .on_mouse_down_out((/** @type {any} */ _e, /** @type {any} */ cx) => this.shutMenu(false, cx))));
  }

  /** The clock: this folder's chats, in the dock's Chats list (their one home), its group open and scrolled
   * to: the space's, else the folder's own, as the list names it. */
  history() {
    askChats({ space: folderGroup(this.folder(), folderSpaces(spaces(), panes())) ?? this.space?.name ?? null });
  }

  /** The files attached to the next message, chips over what is typed (the plan's Upload): each its type's icon,
   * its name (its path its tip) and an × taking it off; they wrap where many. */
  attached(t) {
    return h_flex().id("attached").flex_wrap().px(R.inset).pt(R.inset).gap(R.pad)
      .children(this.files.map((path, n) => h_flex().id(`attached-${n}`).h(24).flex_none().pl(6).pr(2).gap(6)
        .items_center().rounded(6).bg(t.raised).text_size(12).tooltip(path)
        .child(fileMark(fileIcon(path.slice(path.lastIndexOf("/") + 1))))
        .child(div().max_w(ATTACHED).truncate().child(path.slice(path.lastIndexOf("/") + 1)))
        .child(div().id(`attached-${n}-off`).size(20).flex_none().flex().items_center().justify_center().rounded(4)
          .text_color(t.muted).cursor_pointer().hover((s) => s.bg(t.hover).text_color(t.foreground))
          .on_click((_e, cx) => {
            this.files = this.files.filter((one) => one !== path);
            cx.notify();
          }).child(icon("x", 12)))));
  }

  /** The prompt's bar: the + (its menu), the commands (the / menu), Claude's terminal, the context meter (the Context
   * panel), the clock (this folder's chats), the model chip with its effort (its panel), the mode (the Modes
   * panel), send or stop; never wider than the prompt (fit's). */
  bar(t) {
    const context = this.status?.context, mode = this.modeShown(), working = this.agent?.status === "working";
    const shown = this.terminalShown();
    const pressable = (/** @type {string} */ id, /** @type {(cx: any) => void} */ act) => h_flex().id(id).h(28)
      .flex_none().px(R.gap).gap(R.inner).items_center().rounded(6).text_size(12).cursor_pointer()
      .on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();
        this.pressed = e.bounds;
      }).on_click((_e, cx) => act(cx));
    const started = !this.fresh, agentIcon = this.agentIcon(t, 14), chip = this.modelChip(t);
    // the bar's tools: in a chat too narrow for them beside the chip, the mode and send, whole ones leave from the end
    const tools = h_flex().id("bar-tools").h(28).min_w(0).flex_wrap().overflow_hidden().gap(R.pad).items_center()
      .when(Boolean(this.adapter.files) || this.adapter.connectors, (e) => e.child(this.panelChip(t, "plus",
        div().id("plus").size(BUTTON).flex_none().flex().items_center().justify_center()
          .text_color(this.lit("plus") ? t.foreground : t.muted).tooltip("Add").child(icon("plus", 16)), false)))
      .when(started, (e) => e.child(this.chipLook(t, "commands", div().id("commands").size(BUTTON).flex_none()
        .flex().items_center().justify_center().text_color(this.lit("commands") ? t.foreground : t.muted)
        .tooltip("Commands").child(icon("square-slash", 16)), false)
        .on_click((_e, cx) => this.slashButton(cx))))
      .when(started, (e) => e.child(iconButton(t, "chat-terminal", "square-terminal",
        `${shown ? "Hide" : "Show"} ${this.adapter.name}'s terminal`, (cx) => {
          this.showTerminal();
          cx.notify();
        }, { size: 16, color: shown ? t.accent : t.muted })))
      .when(typeof context === "number", (e) => e.child(this.panelChip(t, "context", this.meter(t, Number(context)),
        false)))
      .child(iconButton(t, "chat-history", "clock", "This folder's chats", () => this.history(),
        { size: 16 }));
    return h_flex().px(R.gap).pb(R.gap).pt(R.pad).gap(R.pad).items_center().child(tools)
      .child(div().id("bar-room").flex_1().on_size_change((size, cx) => this.fit({ spare: size.width }, cx)))
      // the empty chat's agent: a chip as the model's, its caret, its list upward from it (decisions.html's)
      .when(!started, (e) => e.child(pressable("agent", () => this.menus.open(this.agentList(), this.pressed,
        undefined, { width: LIST, find: "Search agents", none: "No agent matches" })).bg(t.raised)
        .text_color(t.foreground).hover((s) => s.bg(t.hover))
        .when(Boolean(agentIcon), (e) => e.child(agentIcon)).child(this.adapter.name)
        .child(icon("chevron-down", 12).text_color(t.dim))))
      .when(Boolean(chip), (e) => e.child(chip))
      .when(Boolean(mode), (e) => e.child(this.panelChip(t, "modes", h_flex().id("mode").h(28).flex_none().px(R.gap)
        .gap(R.inner).items_center().text_size(12).text_color(t.foreground)
        .child(icon(mode?.icon ?? "hand", 14)).child(mode?.label ?? ""), false)))
      .child(div().id(working ? "stop" : "send").size(28).flex_none().flex().items_center().justify_center()
        .rounded(6).bg(t.raised).text_color(t.foreground).cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => (working ? void hc(["interrupt", String(this.address)]) : this.send(cx)))
        .child(working ? div().size(10).rounded(4).bg(t.foreground) : icon("arrow-up", 14)));
  }

  /** The context meter (center-chat.html's .ctxm): the ring, `context` and its share in the ring's tone (green, yellow
   * from 50 %, red from 80 %); with no room its words go first (its tip then says it), and a press opens the Context
   * panel. @param {number} context */
  meter(t, context) {
    const tone = { green: t.ansi2, yellow: t.ansi3, red: t.ansi1 }[contextColor(context)], words = this.folded < 1;
    return h_flex().id("context").h(28).flex_none().px(R.gap).gap(CHIP_GAP).items_center().text_size(12)
      .text_color(this.lit("context") ? t.foreground : t.dim)
      .when(!words, (e) => e.tooltip(`Context ${contextLine(this.status ?? { context })}`))
      // its words gone or back, the bar's room is looked at again (it may say nothing new: fit's)
      .on_size_change((_size, cx) => cx.timer.after(0, (cx) => this.fit({}, cx)))
      .child(ring(t, context, tone))
      .when(words, (e) => e.child(h_flex().id("context-words").flex_none().gap(R.pad).items_center()
        .on_size_change((size, cx) => this.fit({ label: size.width }, cx))
        .child("context").child(div().font_semibold().text_color(tone).child(`${Math.round(context)}%`))));
  }

  /** The model chip (center-chat.html's .chip): the model and its level dimmer; with no room its level is left out
   * after the context's words (its tip says it), then the tools and the name give way, never the mode or send; a
   * press opens its models. None for an agent whose adapter offers neither. */
  modelChip(t) {
    const model = this.modelShown(), level = this.effortShown();
    const words = level ? effortLabel(this.adapter, String(level)) : null, out = this.folded >= 2;
    if (!model && !words) return null;
    const chip = h_flex().id("model").h(28).min_w(0).px(R.gap).gap(CHIP_GAP).items_center().text_size(12)
      .when(out && Boolean(words), (e) => e.tooltip(`Effort: ${words}`))
      .child(div().min_w(0).truncate().text_color(t.foreground).child(model?.label ?? ""))
      .when(Boolean(words) && !out, (e) => e.child(div().id("model-level").flex_none().text_color(t.muted)
        .on_size_change((size, cx) => this.fit({ level: size.width }, cx)).child(words ?? "")));
    return this.adapter.models.length || model?.id === null ? this.panelChip(t, "model", chip, true) : chip;
  }

  /** Whether the chip or tool opening panel WHICH is lit: while its panel is open (the styleguide's: as it shows it).
   * @param {Panel} which */
  lit(which) {
    return this.litShown === undefined ? this.open === which : this.litShown === which;
  }

  /** CHIP opening panel WHICH upward (gpui-base's Popover: Esc or a press beside closes it), right-aligned on a chip,
   * left on the + and the context meter (the / menu is the prompt's: prompt()); its look chipLook's.
   * @param {"plus" | "model" | "modes" | "context"} which @param {boolean} raised */
  panelChip(t, which, chip, raised) {
    const open = this.open === which, panels = { model: () => this.modelPanel(t), modes: () => this.modesPanel(t),
      context: () => this.contextPanel(t), plus: () => this.plusPanel(t) };
    const left = which === "context" || which === "plus";
    return Popover.new(`${which}-panel`).anchor(left ? "bottom_left" : "bottom_right").open(open)
      .track_focus(this.panelFocus).on_open_change((opened, cx) => this.showPanel(opened ? which : null, cx))
      .trigger(this.chipLook(t, which, chip, raised))
      .when(open, (e) => e.content(panels[which]().mb(R.pad)));        // built only while open: a long list
  }

  /** A chip or tool opening panel WHICH: raised when RAISED (the model's), else flat; lit as the mockup's while open
   * (raised, an accent ring). @param {Panel} which @param {boolean} raised */
  chipLook(t, which, chip, raised) {
    const lit = this.lit(which), clear = `${t.accent}00`;
    return chip.rounded(6).border_1().border_color(lit ? t.accent : clear).cursor_pointer()
      .when(raised || lit, (e) => e.bg(t.raised))
      .hover((s) => s.bg(t.hover).text_color(t.foreground).border_color(lit ? t.accent : clear));
  }

  /** The bar's free room and the context's words' and the chip's level's px, as last drawn (MEASURED: those that
   * changed): the words left out once nothing is free (a bar too narrow), then the level; each back once it fits
   * again with room to spare (barFolds'). Parts not there (no context yet, no level) are never kept out. */
  fit(measured, cx) {
    const now = { spare: this.spare, label: this.labelWide, level: this.levelWide, ...measured };
    const context = typeof this.status?.context === "number", level = Boolean(this.effortShown());
    const folded = barFolds(this.folded, now.spare, [context ? now.label + CHIP_GAP : null,
      level ? now.level + CHIP_GAP : null]);
    const redraw = folded !== this.folded;
    [this.spare, this.labelWide, this.levelWide, this.folded] = [now.spare, now.label, now.level, folded];
    if (redraw) cx.notify();
  }

  /** Row INDEX in the timeline's column: the person's message boxed, the agent's text with its time, a step on the
   * line with its dot. */
  row(t, code, index) {
    const row = this.rows[index];
    const column = (/** @type {any} */ inner) => div().w_full().flex().justify_center().px(R.edge)
      .child(div().w_full().max_w(COLUMN).child(inner));
    if (row.kind === "user") {
      const user = userLayout();
      return column(v_flex().pt(user.top).pb(user.bottom).gap(user.label)
        .child(div().text_right().text_size(11).text_color(t.dim).child(clock(row.at)))
        .child(div().px(user.inset).py(user.boxY).rounded(8).border(1).border_color(t.border).bg(t.chrome)
          .child(row.text)));
    }
    const step = stepLayout(row.kind);
    return column(h_flex().id(`row-${index}`).items_start().gap(R.gap)
      .when(this.opens(index), (e) => e.cursor_pointer().on_click((_e, cx) => {
        this.opened.set(this.key(index), !this.isOpen(index));
        cx.notify();
      }))
      .child(this.dot(t, row, step))
      .child(v_flex().flex_1().min_w(0).py(step.pad).gap(R.inner).child(this.body(t, code, row, index, step))));
  }

  /** Whether ROW is a call still running: its agent at work, no outcome yet. */
  running(row) {
    return row.ok === null && this.agent?.status === "working";
  }

  /** Whether ROW is a call waiting on the person: its agent asks, no outcome yet. */
  waiting(row) {
    return row.ok === null && this.agent?.status === "blocked";
  }

  /** The row's dot on the timeline's line, on the middle of its first line (stepLayout's): done green (a task added
   * or done is), failed red, running the accent, waiting on the person yellow and hesitating, else gray; a sign-in's
   * step as it stands. */
  dot(t, row, step = stepLayout(row.kind)) {
    const signin = row.kind === "signin" ? this.signin(row).state : null;
    const running = this.running(row) || signin === "busy", waiting = this.waiting(row) || signin === "ask";
    const done = row.ok === true || signin === "done" || row.kind === "tasks" || row.kind === "task";
    const color = done ? t.done : row.ok === false ? t.ansi1 : waiting ? t.ansi3 : running ? t.accent : t.dim;
    const disc = () => div().absolute().top(step.dotTop).left(0.5).size(step.dot).rounded_full();   // on the line
    return div().w(10).flex_none().self_stretch().relative()                 // the line through the whole row
      .child(div().absolute().top_0().bottom_0().left(4).w(1).bg(t.border))
      .child(disc().bg(t.surface))                                        // hides the line as it fades
      .child(disc().bg(color).when(waiting, (e) => e.loop("opacity", { from: 0.35, to: 1, period: 1200 })));
  }

  /** Whether row INDEX has more to show than its line: a change, an output. */
  opens(index) {
    const row = this.rows[index];
    return typeof row.plan !== "number" && Boolean(row.change || (row.output && ["tool", "agent"].includes(row.kind)));
  }

  /** What a step says, its first line stepLayout's line high (its dot on its middle): a thought dim, a call's name
   * bold with its main argument (a skill's source, a connector's logo, tool and first words), a chevron for more; a
   * sign-in with Connect, tasks added, a step done ticked, a plan approved and its link, the agent's markdown timed */
  body(t, code, row, index, step = stepLayout(row.kind)) {
    const line = () => h_flex().h(step.line).items_center();
    const head = (/** @type {string} */ name, /** @type {string | null | undefined} */ main,
      /** @type {string | null} */ tail = null, /** @type {any} */ mark = null) => line().gap(R.gap)
      .when(Boolean(mark), (e) => e.child(mark))
      .child(div().flex_none().font_semibold().child(name))
      .child(div().min_w(0).truncate().font_family(code).text_size(12).text_color(t.muted)
        .when(!tail, (e) => e.flex_1()).when(Boolean(mark), (e) => e.flex_none()).child(main ? String(main) : ""))
      .when(Boolean(tail), (e) => e.child(div().min_w(0).truncate().text_color(t.dim).child(String(tail)))
        .child(div().flex_1()))
      .when(this.running(row), (e) => e.child(div().flex_none().text_size(11).text_color(t.dim).child("running…")))
      .when(this.waiting(row), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
        .child("waiting for you")))
      .when(this.opens(index), (e) => e.child(fold(`row-${index}-fold`, this.isOpen(index), 12, t.dim)));
    if (row.kind === "thought") return line().text_color(t.dim).child(row.label);
    if (row.kind === "signin") {                  // connectors.html's: the brand, what it needs, Connect at the end
      const one = this.signin(row);
      return line().gap(R.gap).child(brandMark(t, one.brand, one.label))
        .child(div().flex_none().font_semibold().child(one.label))
        .child(div().flex_1().min_w(0).truncate().text_color(one.error ? toneInk(t, "bad") : t.muted)
          .child(one.error ? `couldn't start its sign-in: ${one.error}` : one.words))
        .when(one.state === "busy", (e) => e.child(spinner(t)))
        .when(one.state === "ask", (e) => e.child(h_flex().id(`row-${index}-connect`).h(24).px(R.gap).flex_none()
          .items_center().rounded(6).bg(t.raised).text_size(12).text_color(t.foreground).cursor_pointer()
          .hover((s) => s.bg(t.hover)).on_click((_e, cx) => this.connect(one.server, cx)).child("Connect")));
    }
    if (row.kind === "text") {                    // its time at its first line's right end, as wide as it needs
      return h_flex().items_start().gap(R.gap)
        .child(TextView.markdown(`text-${index}`, timelineMarkdown(row.text)).flex_1().min_w(0)
          .line_height(`${step.line}px`))
        .child(line().flex_none().text_size(11).text_color(t.dim).child(clock(row.at)));
    }
    if (row.kind === "other") return line().gap(R.gap).text_color(t.dim).child(row.summary || row.type);
    if (row.kind === "skill") {                   // its source matched from the setup: Project, Global, a plugin's
      const skill = skillOf(this.adapter, String(row.name ?? ""), this.setup?.skills ?? []);
      return head("Skill", skill.name, skill.source);
    }
    if (row.kind === "agent") return v_flex().gap(R.inner).child(head(row.name ?? "Agent", row.task))
      .when(this.isOpen(index) && Boolean(row.output), (e) => e.child(this.output(t, code, row.output)));
    const named = (/** @type {string} */ mark, /** @type {string} */ name, /** @type {string} */ words) => line()
      .gap(R.gap).child(icon(mark).text_color(t.muted)).child(div().flex_none().font_semibold().child(name))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(words));
    if (row.kind === "tasks") return named("list-checks", "Tasks", `${row.added} added`);
    if (row.kind === "task") return line().gap(R.gap).child(icon("check").text_color(t.done))
      .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(row.text));
    if (typeof row.plan === "number") {     // the Plan mode's icon
      return named("notebook", "Plan", planWords(row.plan)).child(this.planLink(t, `row-${index}-plan`));
    }
    const open = this.isOpen(index), via = this.adapter.connectors ? connectorRow(row.name, this.servers()) : null;
    return v_flex().gap(R.inner)
      .child(via ? head(via.label, via.tool, callWords(row.input) || null, brandMark(t, via.brand, via.label))
        : head(row.name, row.main))
      .when(open && Boolean(row.change), (e) => e.child(this.change(t, code, row.change)))
      .when(open && !row.change && Boolean(row.output), (e) => e.child(this.output(t, code, row.output)));
  }

  /** A call's output, its first OUTPUT lines, as code. @param {string} text */
  output(t, code, text) {
    const lines = text.split("\n");
    const shown = lines.length > OUTPUT ? [...lines.slice(0, OUTPUT), `… ${lines.length - OUTPUT} more lines`] : lines;
    return div().px(R.gap).py(R.inner).rounded(6).border(1).border_color(t.border).bg(t.chrome).font_family(code)
      .text_size(12).text_color(t.muted).child(shown.join("\n"));
  }

  /** A file's change as the preview's diff: its path and counts on top, its lines numbered by the file.
   * @param {{ path: string, lines: string[] }} change */
  change(t, code, change) {
    const added = change.lines.filter((l) => l.startsWith("+")).length;
    const removed = change.lines.filter((l) => l.startsWith("-")).length;
    const line = ({ kind, number, text }) => kind === "gap" ? div().h(8)
      : h_flex().w_full().gap(R.inset).px(R.gap).when(kind === "+", (e) => e.bg(t.ansi2 + "18"))
        .when(kind === "-", (e) => e.bg(t.ansi1 + "18"))
        .child(div().w(32).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
        .child(div().w(10).flex_none().text_color(kind === "+" ? t.ansi2 : kind === "-" ? t.ansi1 : t.dim)
          .child(kind === "+" || kind === "-" ? kind : ""))
        .child(div().flex_1().min_w(0).truncate().child(text));
    return v_flex().rounded(6).border(1).border_color(t.border).bg(t.chrome).overflow_hidden()
      .child(h_flex().px(R.gap).py(R.pad).gap(R.gap).border_b(1).border_color(t.border).text_size(12)
        .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(change.path))
        .child(div().text_color(t.ansi2).child(`+${added}`)).child(div().text_color(t.ansi1).child(`−${removed}`)))
      .child(v_flex().py(R.pad).font_family(code).text_size(12).children(diffRows(change.lines).map(line)));
  }
}
