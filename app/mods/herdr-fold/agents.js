// @ts-check
// The agents a chat draws, each an adapter: how to start and resume it, its modes, efforts and commands in its own
// words. A new agent is a new adapter here, not new UI; the app draws its icon as it draws the program's (knownAgents).

import { CHAT_HOOK } from "./helper.js";
import { pythonCommand } from "./logic.js";
import { written } from "./timeline.js";

/** @typedef {{ id: string, label: string, description: string, icon: string, written?: string, shown: RegExp }} Mode */
/** @typedef {{ name: string, modes: Mode[], efforts: { id: string, label: string }[], switches: string[],
 * commands: { name: string, description: string, words?: boolean }[] }} Adapter */

const SESSION = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
// a terminal's escape sequence (CSI, OSC to its end, else ESC and one more), and every other control code but tab and
// new line: neither may reach the agent's terminal from a pasted prompt
const ESCAPES = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?|[\s\S])/g;
const CONTROLS = /[\x00-\x08\x0b-\x1f\x7f-\x9f]/g;
const FOOTER = 3;                     // the screen's last lines where Claude's footer says its mode
const LIMIT = 80;                     // % of a usage window from which the chat says so (the status line's red)
const WINDOWS = [["five_hour", "5-hour"], ["week", "weekly"]];      // status.json's windows, as a notice names them
const SCOPES = ["session", "project", "user"];   // where a kept rule goes: this conversation, this project, everywhere
const EDITS = new Set(["Edit", "MultiEdit", "Write", "NotebookEdit"]);
const NO = { label: "No, tell Claude what to do instead", choice: "deny" };

/** The agents by their program's key. @type {Record<string, Adapter>} */
export const ADAPTERS = {
  claude: {
    name: "Claude",
    modes: [
      // written: the name Claude's session file gives the mode, when not its command line's; shown: its footer's line
      // on Claude's own screen, the one place a mode changed by shift+tab is said at once
      { id: "manual", label: "Manual", description: "Claude asks before each edit and command", icon: "hand",
        written: "default", shown: /^\s*⏸ manual mode on\b/ },
      { id: "acceptEdits", label: "Edit automatically",
        description: "Claude edits files without asking; commands still ask", icon: "code",
        shown: /^\s*⏵⏵ accept edits on\b/ },
      { id: "plan", label: "Plan", description: "Claude explores the code and presents a plan before editing",
        icon: "notebook", shown: /^\s*⏸ plan mode on\b/ },
      { id: "auto", label: "Auto",
        description: "Claude approves what passes a safety check and pauses for anything risky", icon: "zap",
        shown: /^\s*⏵⏵ auto mode on\b/ },
    ],
    efforts: [{ id: "low", label: "Low" }, { id: "medium", label: "Medium" }, { id: "high", label: "High" },
      { id: "xhigh", label: "Extra high" }, { id: "max", label: "Max" }],
    switches: [],
    commands: [
      { name: "/compact", description: "Summarize the conversation so far to free up context" },
      { name: "/review", description: "Review a pull request", words: true },
    ],
  },
};

/** The mode ADAPTER's agent says it is in on SCREEN (its terminal's text): its footer's mode line, in the screen's last
 * FOOTER lines (the words of its output never pass for it); null for none. @param {Adapter} adapter
 * @param {string} screen */
export function screenMode(adapter, screen) {
  for (const line of screen.split("\n").filter((l) => l.trim()).slice(-FOOTER).reverse()) {
    const mode = adapter.modes.find((m) => m.shown.test(line));
    if (mode) return mode.id;
  }
  return null;
}

/** ADAPTER's mode by NAME, as its command line or its session file names it; null for one it has no chip for.
 * @param {Adapter} adapter @param {string} name */
export const modeOf = (adapter, name) => adapter.modes.find((m) => m.id === name || m.written === name) ?? null;

/** TEXT as one word for a POSIX shell, in single quotes. @param {string} text */
export const shellQuote = (text) => `'${text.split("'").join("'\\''")}'`;

/** The JSON Claude takes with --settings for a chat: its PermissionRequest hook and its status line, both the hook's
 * source run with PYTHON (nothing installed; the user's own settings untouched). @param {string} python */
export function claudeSettings(python) {
  const run = [...pythonCommand(python), CHAT_HOOK].map(shellQuote).join(" ");
  return JSON.stringify({
    hooks: { PermissionRequest: [{ matcher: "*", hooks: [{ type: "command", command: `${run} permission`,
      timeout: 600 }] }] },
    statusLine: { type: "command", command: `${run} status` },
  });
}

/** Claude's command line for a chat: a new SESSION or the one it resumes, the chat's settings, and when given a mode,
 * an effort and the first prompt; a session id, mode or effort Claude does not know throws. @param {{ python: string,
 * session: string, resume?: boolean, mode?: string, effort?: string, prompt?: string }} chat */
export function claudeArgv({ python, session, resume = false, mode, effort, prompt }) {
  const claude = ADAPTERS.claude;
  if (!SESSION.test(session)) throw new Error("not a session id");
  if (mode && !claude.modes.some((m) => m.id === mode)) throw new Error(`not a mode: ${mode}`);
  if (effort && !claude.efforts.some((e) => e.id === effort)) throw new Error(`not an effort: ${effort}`);
  return ["claude", resume ? "--resume" : "--session-id", session, "--settings", claudeSettings(python),
    ...(mode ? ["--permission-mode", mode] : []), ...(effort ? ["--effort", effort] : []),
    ...(prompt ? ["--", prompt] : [])];
}

/** RAW, typed or pasted, as the text sent to the agent: no escape sequence or control code, new lines and tabs kept,
 * no spaces at its end. @param {string} raw */
export const promptText = (raw) => raw.replace(ESCAPES, "").replace(/\r\n?/g, "\n").replace(CONTROLS, "").trimEnd();

/** The context ring's color at PERCENT, by the status line's thresholds (core's statusline level). @param {number}
 * percent @returns {"green" | "yellow" | "red"} */
export const contextColor = (percent) => (percent >= 80 ? "red" : percent >= 50 ? "yellow" : "green");

/** Where the context ring's arc ends at PERCENT, run clockwise from the top of a 16 px square's circle (radius 6):
 * null at none, "whole" at all of it. @param {number} percent
 * @returns {{ x: number, y: number, large: boolean } | null | "whole"} */
export function ringArc(percent) {
  if (!(percent > 0)) return null;
  if (percent >= 100) return "whole";
  const turn = (2 * Math.PI * percent) / 100;
  return { x: 8 + 6 * Math.sin(turn), y: 8 - 6 * Math.cos(turn), large: percent > 50 };
}

/** The context in use in words, from the status line's numbers: "68k of 200k · 34%"; its share alone while the window
 * is not known. @param {{ context: number, window?: number | null }} status */
export function contextLine({ context, window }) {
  const size = (/** @type {number} */ n) => (n >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : `${Math.round(n / 1000)}k`);
  return window ? `${size((window * context) / 100)} of ${size(window)} · ${context}%` : `${context}%`;
}

/** A model's ID as its name ("claude-opus-5-5[1m]": Opus 5.5), for the bar until the status line names it; an id of
 * another kind as it is. @param {string} id */
export function modelName(id) {
  const named = /^claude-([a-z]+)-(\d+)-(\d+)(?:\b|$)/.exec(id);
  return named ? `${named[1][0].toUpperCase()}${named[1].slice(1)} ${named[2]}.${named[3]}` : id;
}

/** EFFORT (its id) in ADAPTER's own words. @param {Adapter} adapter @param {string} effort */
export const effortLabel = (adapter, effort) => adapter.efforts.find((e) => e.id === effort)?.label ?? effort;

/** When a window resets, SECONDS since 1970: its time today, else its day, date and time. @param {number} seconds
 * @param {Date} now */
function resets(seconds, now) {
  const when = new Date(seconds * 1000);
  return written(when, when.toDateString() === now.toDateString() ? "time" : "weekday");
}

/** The usage window STATUS (core/chat.py's status) has at LIMIT% or more, the more used first, as the notice above the
 * prompt says it; null for none, or for one in DISMISSED (by its key: the window and its reset, so it comes back with
 * the next). @param {any} status @param {Set<string>} dismissed @param {Date} [now] */
export function limitNotice(status, dismissed, now = new Date()) {
  const used = WINDOWS.map(([key, name]) => ({ key, name, ...(status?.limits?.[key] ?? {}) }))
    .filter((w) => typeof w.used === "number" && w.used >= LIMIT).sort((a, b) => b.used - a.used)
    .map((w) => ({ key: `${w.key}:${w.resets ?? ""}`,
      text: `You've used ${w.used}% of your ${w.name} limit${w.resets ? ` · resets ${resets(w.resets, now)}` : ""}` }));
  return used.find((notice) => !dismissed.has(notice.key)) ?? null;
}


/** A card's answer. @typedef {{ key: string, label: string, choice: string, scope?: string }} Option */
/** What Claude waits on, as its card says it (DIALOG: asked in Claude's own dialog, answered there by its keys).
 * @typedef {{ id: string, kind: string, title: string, sentence: string, detail?: string, old?: string, new?: string,
 * change?: { path: string, lines: string[] } | null, questions?: any[], options: Option[], dialog?: boolean }} Card */

const CHOICE = /^\s*(❯\s*)?(\d+)\.\s+(.*\S)\s*$/;   // a numbered line of Claude's dialog, its cursor on it
const TAIL = 4;                       // the lines at most under a dialog's choices: its hints and its frame
const DECLINE = /^(?:No|Tell Claude)\b/;                   // a dialog's choice that turns Claude back: words follow

/** The choices of the dialog Claude shows on SCREEN (its terminal's text): the run of lines numbered from 1 that its
 * cursor is in, at the screen's foot; none while no dialog is drawn (a plan's numbered steps have no cursor).
 * @param {string} screen @returns {{ key: string, label: string }[]} */
export function screenChoices(screen) {
  const lines = screen.split("\n").filter((line) => line.trim());
  /** @type {{ key: string, label: string, at: boolean }[]} */
  let run = [], found = [], end = 0;
  for (const [n, line] of [...lines, ""].entries()) {
    const choice = CHOICE.exec(line);
    if (choice && Number(choice[2]) === run.length + 1) {
      run.push({ key: choice[2], label: choice[3], at: Boolean(choice[1]) });
      continue;
    }
    if (run.some((c) => c.at)) [found, end] = [run, n];
    run = choice?.[2] === "1" ? [{ key: "1", label: choice[3], at: Boolean(choice[1]) }] : [];
  }
  return lines.length - end <= TAIL ? found.map(({ key, label }) => ({ key, label })) : [];   // at its foot alone
}

/** OPTIONS, each keyed by its place: the digit that picks it is the one drawn. @param {Omit<Option, "key">[]} options
 * @returns {Option[]} */
const numbered = (options) => options.map((option, n) => ({ key: String(n + 1), ...option }));

/** The card for REQUEST (request.json, core/chat_hook.py's): a command, a file's change, Claude's questions, its plan
 * (CHOICES its dialog's), or another tool; Yes, Yes and keep the rule Claude suggests (where it does), No with words.
 * @returns {Card} */
export function cardFor(request, choices = /** @type {{ key: string, label: string }[]} */ ([])) {
  const input = request?.tool_input ?? {}, tool = String(request?.tool_name ?? ""), id = String(request?.id ?? "");
  const suggested = Array.isArray(request?.permission_suggestions) ? request.permission_suggestions[0] : null;
  // kept only as the card says it (core/chat_hook.py's kept): the one rule Claude suggests, or edits for now
  const rule = suggested?.type === "addRules" && suggested.rules?.length === 1 ? suggested.rules[0] : null;
  const card = (/** @type {string} */ kind, /** @type {string} */ title, /** @type {any} */ sentence,
    /** @type {object} */ extra, /** @type {Omit<Option, "key"> | null} */ keep) => ({ id, kind, title,
    sentence: String(sentence ?? ""), ...extra,
    options: numbered([{ label: "Yes", choice: "allow" }, ...(keep ? [keep] : []), NO]) });
  if (tool === "Bash") {
    const words = rule?.toolName === "Bash" && typeof rule.ruleContent === "string" ? rule.ruleContent : null;
    return card("command", "Run a command?", input.command, { detail: String(input.description ?? "") },
      words ? { label: `Yes, and don't ask again for ${words.replace(/:\*$/, "")} commands`, choice: "keep",
        scope: "project" } : null);
  }
  if (EDITS.has(tool)) {
    const path = String(input.file_path ?? input.notebook_path ?? ""), root = `${request.cwd ?? ""}/`;
    return card("change", "Change a file?", request.cwd && path.startsWith(root) ? path.slice(root.length) : path,
      { change: request.change ?? null, old: String(input.old_string ?? ""),
        new: String(input.new_string ?? input.content ?? input.new_source ?? "") },
      suggested?.type === "setMode" && suggested.mode === "acceptEdits"
        ? { label: "Yes, and allow edits for the rest of this conversation", choice: "keep" } : null);
  }
  if (tool === "AskUserQuestion") {
    const questions = Array.isArray(input.questions) ? input.questions : [];
    return { id, kind: "question", title: "Claude asks", sentence: String(questions[0]?.question ?? ""), questions,
      options: numbered([{ label: "Submit", choice: "allow" }, NO]) };
  }
  if (tool === "ExitPlanMode") {
    return { id, kind: "plan", title: "Ready to code?", sentence: "", detail: String(input.plan ?? ""), dialog: true,
      options: choices.map(({ key, label }) => ({ key, label, choice: DECLINE.test(label) ? "deny" : "key" })) };
  }
  const named = rule && `${rule.toolName}${typeof rule.ruleContent === "string" ? `(${rule.ruleContent})` : ""}`;
  return card("tool", `Use ${tool}?`, Object.values(input).find((v) => typeof v === "string"), {},
    named ? { label: `Yes, and don't ask again for ${named}`, choice: "keep", scope: "project" } : null);
}

/** The reply to CARD (core/chat_hook.py's): OPTION's choice (its key in Claude's own dialog), the scope chosen where it
 * keeps a rule, the person's words with a No, the answers. @param {Card} card @param {Option} option
 * @param {{ scope?: string, text?: string, answers?: Record<string, string> }} [given] */
export function replyFor(card, option, { scope, text, answers } = {}) {
  return { id: card.id, choice: option.choice, ...(card.dialog ? { key: option.key } : {}),
    ...(option.scope ? { scope: scope ?? option.scope } : {}),
    ...(text ? { text } : {}), ...(answers ? { answers } : {}) };
}

/** The scope after SCOPE in DIRECTION (1 wider, -1 narrower), held at its ends. @param {string} scope
 * @param {number} direction */
export const nextScope = (scope, direction) =>
  SCOPES[Math.min(SCOPES.length - 1, Math.max(0, SCOPES.indexOf(scope) + direction))];
