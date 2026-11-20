// @ts-check
// The agents a chat draws, each an adapter: how to start and resume it, its modes, efforts and commands in its own
// words. A new agent is a new adapter here, not new UI; the app draws its icon as it draws the program's (knownAgents).

import { CHAT_HOOK } from "./helper.js";
import { pythonCommand } from "./logic.js";
import { money } from "./report.js";
import { written } from "./timeline.js";

/** @typedef {{ id: string, label: string, description: string, icon: string, written?: string, shown: RegExp }} Mode */
/** A session switch of an agent's (Claude's Ultracode): its words and tip, its key in the launch settings, the commands
 * that turn it on and off, and how the agent's screen says it refused (its own words, kept). @typedef {{ id: string,
 * label: string, tip: string, setting: string, on: string, off: string, refused: RegExp }} Switch */
/** A model an agent offers: its id (its CLI's), its name, a line on what it is for. @typedef {{ id: string,
 * label: string, description: string }} Model */
/** How an agent names a skill: typed after COMMAND as a command, a plugin's as the plugin's name, PLUGIN, the skill's
 * (its Skill tool's input too). @typedef {{ command: string, plugin: string }} SkillWords */
/** What a chat reads of its agent: SETUP, agent_setup.py's word for it (null: none read), how it names a SKILL, its
 * command that COMPACTs a chat. @typedef {{ setup: string | null, skill: SkillWords | null,
 * compact: string | null } & Attaches} Reads */
/** FILES: what names a file in a message, before its path (null: none attached); CONNECTORS: switched from a chat
 * (core's toggle), their calls drawn by brand; CHECK: agent_state.py's word for its own look at a server (null: the
 * setup read again). @typedef {{ files: string | null, connectors: boolean, check: string | null }} Attaches */
/** MODELS: the first is the one the agent starts with unasked (its own default). @typedef {{ name: string,
 * models: Model[], modes: Mode[], efforts: { id: string, label: string }[], switches: Switch[],
 * commands: { name: string, description: string, words?: boolean }[] } & Reads} Adapter */

const SESSION = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
// a terminal's escape sequence (CSI, OSC to its end, else ESC and one more), and every other control code but tab and
// new line: neither may reach the agent's terminal from a pasted prompt
const ESCAPES = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)?|[\s\S])/g;
const CONTROLS = /[\x00-\x08\x0b-\x1f\x7f-\x9f]/g;
const FOOTER = 3;                     // the screen's last lines where Claude's footer says its mode
const LIMIT = 80;                     // % of a usage window from which the chat says so (the status line's red)
const WINDOWS = [["five_hour", "5-hour"], ["week", "weekly"]];      // status.json's windows, as a notice names them
const SCOPES = ["session", "project", "user"];   // where a kept rule goes: this chat, this project, everywhere
const EDITS = new Set(["Edit", "MultiEdit", "Write", "NotebookEdit"]);
const NO = { label: "No, tell Claude what to do instead", choice: "deny" };

/** The agents by their program's key. @type {Record<string, Adapter>} */
export const ADAPTERS = {
  claude: {
    name: "Claude",
    // Claude Code's own model list (claude 2.1.325's catalog, its main section, in its order) and its words for each;
    // Default as /model's first line: what the account gets unasked. A model it does not list is drawn as said.
    models: [{ id: "default", label: "Default", description: "The recommended model for your account" },
      { id: "claude-opus-5-5", label: "Opus 5.5", description: "For complex work and everyday tasks" },
      { id: "claude-fable-5-2", label: "Fable 5.2", description: "For your toughest challenges" },
      { id: "claude-sonnet-5-5", label: "Sonnet 5.5", description: "Most efficient for simpler tasks" },
      { id: "claude-haiku-5-5", label: "Haiku 5.5", description: "Fastest for quick answers" }],
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
    // Ultracode: a session setting under the effort (its own --settings key; --effort ultracode would force xhigh)
    switches: [{ id: "ultracode", label: "Ultracode",
      tip: "Plans a multi-agent workflow for each task; uses more tokens", setting: "ultracode",
      on: "/effort ultracode", off: "/effort ultracode off", refused: new RegExp(
        "(Ultracode needs dynamic workflows enabled[^.\\n]*|ultracode is not available for this session[^\\n]*"
        + "|Ultracode isn['’]t available[^.\\n]*)", "i") }],
    commands: [
      { name: "/compact", description: "Free the context, keep a summary" },
      { name: "/review", description: "Review a pull request", words: true },
    ],
    setup: "claude",
    skill: { command: "/", plugin: ":" },       // /api-routes, /code-review:code-review; the Skill tool's input as well
    compact: "/compact",
    files: "@",                                 // @src/books.py, @"docs/error format.md": Claude reads the file
    connectors: true,                           // /mcp enable and disable, per folder
    check: "claude",                            // `claude mcp get`: a sign-in's end tells nothing in a session
  },
};

// the ways in (+, Chats, Issues, a new chat's agent list) open an agent as More's menu says, in a chat or a terminal
export const DRAWABLE = Object.keys(ADAPTERS);               // the agents a chat draws; every other one a terminal's
export const RECENT_AGENTS = "herdr-fold.agents-recent";     // shared: the agents started last, the latest first
export const AGENTS_OPEN = "herdr-fold.agents-open";         // shared: chat or terminal, Settings' General's
const RECENT = 8;                                            // agents remembered at most

/** How a way in opens an agent, as More's menu left it (KEPT): "chat", the default, or "terminal".
 * @param {unknown} kept @returns {"chat" | "terminal"} */
export const agentsOpen = (kept) => (kept === "terminal" ? "terminal" : "chat");

/** How AGENT opens, as HOW (agentsOpen's) says, in a space on MACHINE (null: this Mac): a chat where an adapter draws
 * it on this Mac (milestone 1), else its own CLI in a terminal tab. @param {string} agent @param {string} how
 * @param {string | null} [machine] @returns {"chat" | "terminal"} */
export const opensAs = (agent, how, machine = null) =>
  (how === "chat" && Object.hasOwn(ADAPTERS, agent) && !machine ? "chat" : "terminal");

/** The agent + and Issues' To agent start, and how, by HOW in a space on MACHINE: a chat's, the latest of RECENT a
 * chat draws (its list picks another), else the latest of RECENT in a terminal. @param {unknown} recent
 * @param {string} how @param {string | null} [machine] @returns {{ agent: string, as: "chat" | "terminal" }} */
export function newAgent(recent, how, machine = null) {
  const keys = Array.isArray(recent) ? recent.filter((k) => typeof k === "string") : [];
  const agent = how === "chat" ? keys.find((k) => Object.hasOwn(ADAPTERS, k)) ?? DRAWABLE[0] : keys[0] ?? DRAWABLE[0];
  return { agent, as: opensAs(agent, how, machine) };
}

/** How a closed chat of Chats' (ITEM) reopens by HOW: a chat where its agent has an adapter and its id is a session
 * the adapter resumes, else its agent resuming it in a terminal (Codex's until its adapter). @param {{ agent: string,
 * id: string }} item @param {string} how @returns {"chat" | "terminal"} */
export const reopensAs = (item, how) => (opensAs(item.agent, how) === "chat" && SESSION.test(item.id) ? "chat"
  : "terminal");

/** RECENT with KEY first, each once, RECENT at most. @param {unknown} recent @param {string} key */
export const rememberAgent = (recent, key) => [key, ...(Array.isArray(recent) ? recent : [])
  .filter((k) => typeof k === "string" && k !== key)].slice(0, RECENT);

/** An agent a list offers. @typedef {{ key: string, name: string, installed: boolean, terminal: boolean,
 * recent: boolean, signIn: boolean, icon: string | null, tint: boolean, run: string[] }} Choice */

/** A new chat's agent list: KNOWN (the app's) and the DRAWABLE it does not name, installed ones only (the app's word,
 * else core's AGENTS'), RECENT first, the rest by name; no adapter: terminal; signed out by core: signIn.
 * @param {any[]} known @param {string[]} drawable @param {unknown} recent @param {unknown} [agents] */
export function agentChoices(known, drawable, recent, agents = null) {
  const keys = Array.isArray(recent) ? recent : [];
  const told = new Map((Array.isArray(agents) ? agents : []).map((a) => [a?.key, a]));
  const listed = new Map((known ?? []).filter((a) => typeof a?.key === "string").map((a) => [a.key, a]));
  for (const key of drawable) {
    if (listed.has(key)) continue;
    listed.set(key, { key, name: ADAPTERS[key]?.name ?? key, installed: told.get(key)?.installed });
  }
  const rank = (/** @type {string} */ key) => (keys.includes(key) ? keys.indexOf(key) : keys.length);
  return [...listed.values()].filter((a) => a.installed !== false).map((a) => ({ key: a.key,
    name: String(a.name ?? a.key), installed: true, terminal: !drawable.includes(a.key),
    recent: keys.includes(a.key), signIn: told.get(a.key)?.signed_in === false,
    icon: typeof a.icon === "string" ? a.icon : null, tint: Boolean(a.tint),
    run: Array.isArray(a.run) && a.run.length ? a.run.map(String) : [a.key] }))
    .sort((a, b) => rank(a.key) - rank(b.key) || a.name.localeCompare(b.name));
}

/** tab.new's arguments for CHOICE's own CLI in a terminal tab of SPACE, in FOLDER, PROMPT its first message (the
 * app types it once the agent is ready). @param {{ name: string, run: string[] }} choice
 * @param {{ space?: string, folder?: string | null, prompt?: string }} where */
export const terminalTab = (choice, { space, folder = null, prompt = "" }) => ({ name: choice.name,
  ...(space ? { space } : {}), ...(folder ? { folder } : {}), argv: choice.run, ...(prompt ? { task: prompt } : {}) });

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
 * source run with PYTHON (nothing installed; the user's own settings untouched), and the session's switches on (MORE).
 * @param {string} python @param {Record<string, boolean>} [more] */
export function claudeSettings(python, more = {}) {
  const run = [...pythonCommand(python), CHAT_HOOK].map(shellQuote).join(" ");
  return JSON.stringify({
    hooks: { PermissionRequest: [{ matcher: "*", hooks: [{ type: "command", command: `${run} permission`,
      timeout: 600 }] }] },
    statusLine: { type: "command", command: `${run} status` },
    ...more,
  });
}

/** The command that turns ADAPTER's switch ID ON or off, null for an agent with no such switch.
 * @param {Adapter} adapter @param {string} id @param {boolean} on */
export const switchCommand = (adapter, id, on) => {
  const found = adapter.switches.find((sw) => sw.id === id);
  return found ? (on ? found.on : found.off) : null;
};

/** Why ADAPTER's agent refused its switch ID, in its own words off its SCREEN after the switch's latest command there;
 * null when it did not say so. @param {Adapter} adapter @param {string} id @param {string} screen */
export const switchRefused = (adapter, id, screen) => {
  const found = adapter.switches.find((sw) => sw.id === id);
  const said = found?.refused.exec(screen.slice(Math.max(0, screen.lastIndexOf(found.on))));
  return said ? said[1].trim() : null;
};

/** Claude's command line for a chat: a new SESSION or the one it resumes, its settings (SWITCHES on), a MODEL (none for
 * Default), a MODE, an EFFORT, the first PROMPT; one Claude does not know throws. @param {{ python: string, session:
 * string, resume?: boolean, model?: string, mode?: string, effort?: string, prompt?: string, switches?: any }} chat */
export function claudeArgv({ python, session, resume = false, model, mode, effort, prompt, switches = {} }) {
  const claude = ADAPTERS.claude;
  if (!SESSION.test(session)) throw new Error("not a session id");
  if (model && !claude.models.some((m) => m.id === model)) throw new Error(`not a model: ${model}`);
  if (mode && !claude.modes.some((m) => m.id === mode)) throw new Error(`not a mode: ${mode}`);
  if (effort && !claude.efforts.some((e) => e.id === effort)) throw new Error(`not an effort: ${effort}`);
  const on = Object.fromEntries(claude.switches.filter((sw) => switches[sw.id]).map((sw) => [sw.setting, true]));
  return ["claude", resume ? "--resume" : "--session-id", session, "--settings", claudeSettings(python, on),
    ...(model && model !== claude.models[0].id ? ["--model", model] : []),
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

/** TOKENS as the Context panel's legend says them: 6k, 18k, 1.2M; under a thousand to a tenth of one (0.3k).
 * @param {number} tokens */
export const kilo = (tokens) => (tokens >= 1e6 ? `${+(tokens / 1e6).toFixed(1)}M` : tokens >= 1000
  ? `${Math.round(tokens / 1000)}k` : `${Math.max(0.1, +(tokens / 1000).toFixed(1))}k`);

const REST = "Conversation & tools";  // the context beside the rules and skills: one part till tools are read

/** A part of the context in use. @typedef {{ key: "rules" | "skills" | "rest" | "used", label: string | null,
 * tokens: number, share: number }} ContextPart */
/** The context in use as the Context panel's bar draws it, from STATUS (its share, the window) and SETUP (the
 * estimates): the rules read at the start, the skills' list, the rest, each at most what is left, with its share of
 * the window; while either is unknown, the use. @param {any} status @param {any} setup @returns {ContextPart[]} */
export function contextParts(status, setup) {
  const percent = Number(status?.context) || 0, window = Number(status?.window) || 0;
  if (!(window > 0) || !setup) return [{ key: "used", label: null, tokens: (window * percent) / 100,
    share: percent / 100 }];
  let left = (window * percent) / 100;
  const take = (/** @type {number} */ tokens) => {
    const taken = Math.min(Math.max(0, tokens), left);
    left -= taken;
    return taken;
  };
  const sum = (/** @type {any[]} */ items) => items.reduce((n, item) => n + (Number(item?.tokens) || 0), 0);
  // a rule with paths is read once a file it names is: not known to be in use
  const parts = [{ key: /** @type {const} */ ("rules"), label: "Rules",
    tokens: take(sum((setup.rules ?? []).filter((r) => !r?.paths?.length))) },
  { key: /** @type {const} */ ("skills"), label: "Skills", tokens: take(sum(setup.skills ?? [])) },
  { key: /** @type {const} */ ("rest"), label: REST, tokens: left }];
  return parts.filter((p) => p.tokens > 0).map((p) => ({ ...p, share: p.tokens / window }));
}

/** Where RULE (agent_setup.py's) is, as the Context panel says it after its name: the chat's FOLDER by its name, a
 * folder in it from it (.claude/rules), one in HOME from ~, else whole; the globs it is read for after a dot.
 * @param {{ path: string, paths?: string[] }} rule @param {string} folder @param {string} home */
export function ruleWhere(rule, folder, home) {
  const trim = (/** @type {string} */ path) => path.replace(/\/+$/, "") || "/";
  const dir = rule.path.slice(0, rule.path.lastIndexOf("/")) || "/", top = trim(folder), mine = trim(home);
  const inside = (/** @type {string} */ base) => base !== "/" && dir.startsWith(`${base}/`);
  const where = dir === top ? top.slice(top.lastIndexOf("/") + 1) : inside(top) ? dir.slice(top.length + 1)
    : dir === mine ? "~" : inside(mine) ? `~${dir.slice(mine.length)}` : dir;
  return [where, (rule.paths ?? []).join(", ")].filter(Boolean).join(" · ");
}

/** A skill as a chat names it. @typedef {{ name: string, source: string | null, path: string | null,
 * known: boolean }} Skill */
/** The skill CALLED names (the Skill tool's input, a plugin's plugin:skill) as SKILLS (agent_setup.py's) list it: its
 * name, source (Personal, Project, a plugin's) and file; one they lack its name, a plugin's its plugin as its source.
 * @param {Adapter} adapter @param {string} called @param {any[]} skills @returns {Skill} */
export function skillOf(adapter, called, skills) {
  const cut = adapter.skill ? called.indexOf(adapter.skill.plugin) : -1;
  const plugin = cut > 0 ? called.slice(0, cut) : null;
  const name = plugin && adapter.skill ? called.slice(cut + adapter.skill.plugin.length) : called;
  const listed = (skills ?? []).filter((s) => s?.name === name);
  const found = listed.find((s) => (plugin ? s.source === plugin : s.source === s.scope))
    ?? (plugin ? null : listed[0]);
  return { name, source: found?.source ?? plugin, path: found?.path ?? null, known: Boolean(found) };
}

/** The skills the chat's ROWS (the timeline's) called, each once, the latest call first: its skill (skillOf's) and
 * when it was called last. @param {Adapter} adapter @param {any[]} rows @param {any[]} skills */
export function usedSkills(adapter, rows, skills) {
  /** @type {Map<string, string | null>} */
  const last = new Map();
  for (const row of rows) {
    if (row?.kind !== "skill" || !row.name) continue;
    last.delete(String(row.name));
    last.set(String(row.name), row.at ?? null);
  }
  return [...last].reverse().map(([called, at]) => ({ skill: skillOf(adapter, called, skills), at }));
}

/** What SKILL (agent_setup.py's) is typed as to ADAPTER's agent: /api-routes, a plugin's /code-review:code-review;
 * null for an agent with no such command. @param {Adapter} adapter @param {{ name: string, source: string,
 * scope: string }} skill */
export const skillCommand = (adapter, skill) => (adapter.skill ? `${adapter.skill.command}${skill.source !== skill.scope
  ? `${skill.source}${adapter.skill.plugin}` : ""}${skill.name}` : null);

/** SKILLS (agent_setup.py's) in the / menu's order: those the chat's ROWS (the timeline's) called, the latest first,
 * then the rest as listed. @param {Adapter} adapter @param {any[]} rows @param {any[]} skills */
export function menuSkills(adapter, rows, skills) {
  const used = usedSkills(adapter, rows, skills).map(({ skill }) => skills.find((s) => s?.name === skill.name
    && s?.source === skill.source)).filter(Boolean);
  return [...used, ...skills.filter((s) => !used.includes(s))];
}

/** What follows the "/" the prompt's text (VALUE) starts with while a command is typed there ("/rev": rev; "/": none
 * yet); null once anything else is: a space, a new line, words before it. @param {string} value */
export const slashQuery = (value) => /^\/(\S*)$/.exec(value)?.[1] ?? null;

/** A / menu row: PART, NAME, what it is TYPED as after "/" (null: it acts), LINE, source TAG, ICON, what a pick does.
 * @typedef {{ part: string, name: string, typed: string | null, line: string, tag: string | null, icon: string,
 * row: PanelRow }} SlashItem */

/** How well QUERY finds ITEM, case aside: 0 its name or what it is typed as starts with it, 1 a word of either does
 * (after - _ : / . or a space), 2 either holds it, 3 its line or its WORDS (found by, not shown) do; else null.
 * @param {{ name: string, typed: string | null, line: string, words?: string }} item @param {string} query */
export function slashRank(item, query) {
  const q = query.toLowerCase(), names = [item.name, item.typed ?? ""].map((n) => n.toLowerCase().replace(/^\//, ""));
  if (names.some((n) => n.startsWith(q))) return 0;
  if (names.some((n) => n.split(/[-_:/.\s]+/).some((word) => word.startsWith(q)))) return 1;
  if (names.some((n) => n.includes(q))) return 2;
  return [item.line, item.words ?? ""].some((text) => text.toLowerCase().includes(q)) ? 3 : null;
}

/** The / menu of ITEMS for QUERY (null or "": none typed): the parts, FEW of each, and how many more; typed, what it
 * finds in one unnamed part, the best first (Claude Code's own). @template {{ part: string, name: string,
 * typed: string | null, line: string }} T @param {T[]} items @param {string | null} query @param {number} few */
export function slashMenu(items, query, few) {
  if (query) {
    const found = items.map((item, n) => ({ item, n, rank: slashRank(item, query) })).filter((f) => f.rank !== null)
      .sort((a, b) => Number(a.rank) - Number(b.rank) || a.n - b.n).map((f) => f.item);
    return { parts: found.length ? [{ name: null, items: found }] : [], more: 0 };
  }
  const parts = [...new Set(items.map((item) => item.part))].map((name) => ({ name,
    items: items.filter((item) => item.part === name).slice(0, few) }));
  return { parts, more: items.length - parts.reduce((n, part) => n + part.items.length, 0) };
}

const ABSOLUTE = /^\/[^\x00-\x1f\x7f]*$/;   // a path from the root, no control code in it

/** The files macOS's chooser answered (OUTPUT: a path a line): the absolute ones, each once; none: cancelled.
 * @param {string} output @returns {string[]} */
export const uploadPaths = (output) => [...new Set(output.split("\n").map((line) => line.replace(/\r$/, ""))
  .filter((line) => ABSOLUTE.test(line)))];

/** PATH as a message names it after MARK: quoted where it holds a space. @param {string} path @param {string} mark */
const mention = (path, mark) => (/\s/.test(path) ? `${mark}"${path}"` : `${mark}${path}`);

/** PATHS as a message names them (the adapter's MARK before each), a space apart: from FOLDER (the chat's) when in
 * it. @param {string[]} paths @param {string} folder @param {string} [mark] */
export const mentions = (paths, folder, mark = "@") => paths.map((path) => mention(path.startsWith(`${folder}/`)
  ? path.slice(folder.length + 1) : path, mark)).join(" ");

/** TEXT with the files attached (PATHS) named after its words. @param {string} text @param {string[]} paths
 * @param {string} folder @param {string} [mark] */
export const withFiles = (text, paths, folder, mark = "@") => [text, mentions(paths, folder, mark)].filter(Boolean)
  .join(" ");

/** What follows the "@" a word starts with at the end of the prompt's text (VALUE) while a file is named there
 * ("@boo": boo; "@": none yet); null once a space follows, or with none. @param {string} value
 * @param {string} [mark] */
export const mentionQuery = (value, mark = "@") => (new RegExp(`(?:^|\\s)${mark}(\\S*)$`).exec(value)?.[1] ?? null);

/** VALUE with the "@" Add context… types at its end, a space before it where a word ends there; as it is where one
 * is typed already. @param {string} value @param {string} [mark] */
export const atTyped = (value, mark = "@") => (mentionQuery(value, mark) !== null ? value
  : `${value}${value && !/\s$/.test(value) ? " " : ""}${mark}`);

/** VALUE with PATH picked in the place of the "@…" typed at its end (none: at its end), a space after it.
 * @param {string} value @param {string} path @param {string} [mark] */
export function mentionPick(value, path, mark = "@") {
  const typed = atTyped(value, mark), query = mentionQuery(typed, mark) ?? "";
  return `${typed.slice(0, typed.length - query.length - mark.length)}${mention(path, mark)} `;
}

/** Add context's list for QUERY (what follows the "@"): the CHANGED files, then the folder's other FILES, FEW of each
 * and how many more; typed, what it finds, the best first (slashMenu's); a row its name, then its folder.
 * @param {string[]} changed @param {string[]} files @param {string} query @param {number} few */
export function mentionMenu(changed, files, query, few) {
  const item = (/** @type {string} */ part) => (/** @type {string} */ path) => {
    const cut = path.lastIndexOf("/");
    return { part, name: path.slice(cut + 1), typed: path, line: cut < 0 ? "" : path.slice(0, cut),
      row: { kind: /** @type {const} */ ("mention"), path } };
  };
  const first = new Set(changed);
  return slashMenu([...changed.map(item("Changed")), ...files.filter((path) => !first.has(path))
    .map(item("Files"))], query, few);
}

/** The file a conversation exported as MARKDOWN (core/chats.py's, "# its title" first) is named at first: its title,
 * no slash or colon (macOS's), 80 characters at most, .md. @param {string} markdown */
export function exportName(markdown) {
  const title = (/^# (.*)/.exec(markdown)?.[1] ?? "").replace(/[/:\\]/g, "-").replace(/\s+/g, " ").trim();
  return `${title.slice(0, 80).trim() || "Conversation"}.md`;
}

/** @typedef {"personal" | "project" | "plugin" | "account" | "local"} TagRole */

/** A source's tag role, as center-chat.html's and connectors.html's tags: the user's own (.tagu), the project's
 * (.tagp), the account's connectors' (claude.ai, .tagc), a local or managed one's (muted), else a plugin's (.tagl).
 * @param {string} source @returns {TagRole} */
export const tagRole = (source) => (source === "Personal" ? "personal" : source === "Project" ? "project"
  : source === "claude.ai" ? "account" : source === "Local" || source === "Managed" ? "local" : "plugin");

// the tags' hues (OKLCh degrees) as the mockups draw them: Project teal, a plugin's peach, claude.ai blue; each taken
// from the theme's palette, the nearest at least TAG_PART from the ones taken before it (Personal's accent first)
export const TAG_HUES = { project: 183, plugin: 53, account: 260 }, TAG_PART = 30;
export const READ = 4.5;                // small text's contrast on what it stands on (WCAG AA)
const TAG_SLOTS = [2, 3, 4, 5, 6, 10, 11, 12, 13, 14];     // the palette's hues; red (1, 9) is the errors'
const GRAY = 0.03;                      // a color's chroma (OKLCh) under which it reads as gray, as Local's muted

/** @param {string} hex @returns {number[]} its channels, 0 to 1 */
const channels = (hex) => [1, 3, 5].map((n) => parseInt(hex.slice(n, n + 2), 16) / 255);

/** HEX moved SHARE of the way (0 to 1) toward TOWARD, as the themes' tool mixes (src/themes/apply.py).
 * @param {string} hex @param {string} toward @param {number} share */
export function mixColor(hex, toward, share) {
  const [a, b] = [channels(hex), channels(toward)];
  return `#${a.map((v, n) => Math.round((v + (b[n] - v) * share) * 255).toString(16).padStart(2, "0")).join("")}`;
}

/** The WCAG contrast of two colors. @param {string} one @param {string} other */
export function contrast(one, other) {
  const lum = (/** @type {string} */ hex) => {
    const [r, g, b] = channels(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [light, dark] = [lum(one), lum(other)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/** HEX's chroma and hue (OKLCh, degrees). @param {string} hex @returns {{ chroma: number, hue: number }} */
export function oklch(hex) {
  const [r, g, b] = channels(hex).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const x = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, y = 0.0259040371 * l + 0.7827717662 * m
    - 0.808675766 * s;
  return { chroma: Math.hypot(x, y), hue: ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360 };
}

/** The degrees between two hues. @param {number} a @param {number} b */
export const hueGap = (a, b) => Math.min(Math.abs(a - b) % 360, 360 - (Math.abs(a - b) % 360));

/** HEX, or moved toward TOWARD by tenths until it reads READ on GROUND (apply.py's readable).
 * @param {string} hex @param {string} toward @param {string} ground */
export function readableOn(hex, toward, ground) {
  for (let tenth = 0; tenth <= 10; tenth += 1) {
    const made = mixColor(hex, toward, tenth / 10);
    if (contrast(made, ground) >= READ) return made;
  }
  return toward;
}

/** @type {Map<string, Record<TagRole, string>>} */
const TAGS = new Map();

/** Each tag role's color in theme T, read by READ on canvas, where a tag stands: Personal the accent; Project, a
 * plugin's and claude.ai the palette's hues nearest TAG_HUES, each TAG_PART from those taken before; Local muted.
 * @param {Record<string, string>} t @returns {Record<TagRole, string>} */
export function tagColors(t) {
  const key = [t.accent, t.muted, t.foreground, t.canvas, t.ansi1, ...TAG_SLOTS.map((n) => t[`ansi${n}`])].join();
  const known = TAGS.get(key);
  if (known) return known;
  const hexes = (/** @type {string[]} */ ...all) => all.every((v) => /^#[0-9a-f]{6}/i.test(v ?? ""));
  const read = (/** @type {string} */ hex) => (hexes(hex, t.foreground, t.canvas) ? readableOn(hex, t.foreground,
    t.canvas) : hex);
  const slots = TAG_SLOTS.map((n) => t[`ansi${n}`]).filter((hex) => hexes(hex));
  const pool = [...slots, ...(hexes(t.ansi1, t.ansi3) ? [mixColor(t.ansi1, t.ansi3, 0.5)] : [])].map(read)
    .map((hex) => ({ hex, ...oklch(hex) })).filter((c) => c.chroma >= GRAY);
  const accent = read(t.accent), taken = [{ hex: accent, ...(hexes(accent) ? oklch(accent) : { chroma: 0, hue: 0 }) }];
  /** @type {Record<string, string>} */
  const colors = { personal: taken[0].hex };
  for (const [role, target] of Object.entries(TAG_HUES)) {
    const free = pool.filter((c) => taken.every((o) => hueGap(c.hue, o.hue) >= TAG_PART));
    const near = free.reduce((best, c) => (!best || hueGap(c.hue, target) < hueGap(best.hue, target) ? c : best),
      /** @type {typeof pool[number] | null} */ (null)) ?? pool[0] ?? taken[0];
    taken.push(near);
    colors[role] = near.hex;
  }
  const made = /** @type {Record<TagRole, string>} */ ({ ...colors, local: read(t.muted) });
  TAGS.set(key, made);
  return made;
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

/** ADAPTER's model the agent names NAME (an id, as its session file has it: claude-opus-5-5[1m], dated or not; or a
 * name, as its status line has it: Opus 5.5, Opus 5.5 (1M context), Opus); null for one it does not list, or none.
 * @param {Adapter} adapter @param {string | null | undefined} name @returns {Model | null} */
export function modelOf(adapter, name) {
  const said = String(name ?? "").toLowerCase().replace(/\[[^\]]*\]$|\s*\([^)]*\)$/, "").trim();
  if (!said) return null;
  const listed = adapter.models.slice(1);                    // the first, the agent's own default, is never one said
  const family = listed.filter((m) => m.label.toLowerCase().split(" ")[0] === said);
  return listed.find((m) => said === m.id || said === m.label.toLowerCase() || (said.startsWith(`${m.id}-`)
    && /^\d{8}$/.test(said.slice(m.id.length + 1)))) ?? (family.length === 1 ? family[0] : null);
}

/** The Modes panel's effort slider (center-chat.html's), px: its height, its inside, a stop's room (a dot and the gap
 * to the next; the knob fits it, so it moves nothing), a stop's dot, the knob. */
export const SLIDER = { high: 24, pad: 4, stop: 16, dot: 4, knob: 14 };

const SLACK = 8;                      // px more than a part needs before the bar shows it again

/** How many of the bar's parts that give way in turn (the context's words, the chip's level) are out (FOLDED now),
 * SPARE px free, each WIDE px (null: not there): the next out once none is free, the last back once it fits with SLACK
 * to spare, so none flickers. @param {number} folded @param {number} spare @param {(number | null)[]} wide */
export function barFolds(folded, spare, wide) {
  if (spare <= 0) {
    const next = wide.findIndex((w, n) => n >= folded && w !== null);
    return next === -1 ? folded : next + 1;
  }
  let out = folded;
  while (out > 0 && wide[out - 1] === null) out -= 1;
  return out > 0 && spare >= Number(wide[out - 1]) + SLACK ? out - 1 : out;
}

/** The effort STEPS away from CURRENT among ADAPTER's, held at their ends; none said yet (or one it does not know),
 * from the middle one. @param {Adapter} adapter @param {string | null | undefined} current @param {number} steps */
export function nearEffort(adapter, current, steps) {
  const ids = adapter.efforts.map((e) => e.id), at = ids.indexOf(String(current));
  const from = at === -1 ? Math.floor((ids.length - 1) / 2) : at;
  return ids[Math.min(ids.length - 1, Math.max(0, from + steps))];
}

/** The effort whose stop is under the pointer at X on the slider whose left edge is at LEFT, held at its ends.
 * @param {Adapter} adapter @param {number} x @param {number} left */
export function effortAt(adapter, x, left) {
  const ids = adapter.efforts.map((e) => e.id);
  const at = Math.floor((x - left - SLIDER.pad) / SLIDER.stop);
  return ids[Math.min(ids.length - 1, Math.max(0, at))];
}

/** A bar panel's row (WORDS: the prompt waits for them). @typedef {{ kind: "model", id: string | null, label: string,
 * description: string } | { kind: "mode" | "switch", id: string } | { kind: "effort" | "export" | "agent" | "usage" }
 * | { kind: "file" | "mention", path: string } | { kind: "command", text: string, words: boolean } | Plus} PanelRow */
/** A row of the + menu. @typedef {{ kind: "upload" | "context" | "manage" } | { kind: "connector", name: string,
 * on: boolean }} Plus */

/** The model chip's rows: ADAPTER's models (Codex's would bring its own), the one in use first where it lists none
 * such (SHOWN with no id). @param {Adapter} adapter @param {{ id: string | null, label: string } | null} shown
 * @returns {PanelRow[]} */
export const modelRows = (adapter, shown) => [
  ...(shown && shown.id === null ? [{ kind: /** @type {const} */ ("model"), id: null, label: shown.label,
    description: "In use in this chat" }] : []),
  ...adapter.models.map((m) => ({ kind: /** @type {const} */ ("model"), ...m }))];

/** The mode chip's rows (center-chat.html's Modes): ADAPTER's modes, then its effort where it has levels, then its
 * switches (Claude's Ultracode; none for an agent without). @param {Adapter} adapter @returns {PanelRow[]} */
export const modeRows = (adapter) => [
  ...adapter.modes.map((m) => ({ kind: /** @type {const} */ ("mode"), id: m.id })),
  ...(adapter.efforts.length ? [{ kind: /** @type {const} */ ("effort") }] : []),
  ...adapter.switches.map((sw) => ({ kind: /** @type {const} */ ("switch"), id: sw.id }))];

/** Of COUNT rows, the one the keys go to from AT, STEP rows on (up while negative), over those OFF (a switch refused),
 * held at the ends; from none, FIRST (the model in use), else the first. @param {number} count @param {number | null}
 * at @param {number} step @param {(n: number) => boolean} off @param {number} [first] */
export function panelStep(count, at, step, off, first = -1) {
  const usable = [...Array(count).keys()].filter((n) => !off(n));
  if (!usable.length) return null;
  if (at === null) return usable.includes(first) ? first : usable[0];
  const next = step > 0 ? usable.find((n) => n > at) : [...usable].reverse().find((n) => n < at);
  return next ?? at;
}

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

/** The budget's notice above the prompt: the first of core's (ANSWER: report.py notice's, an agent's month near or
 * past its budget, in core's words) not closed here (DISMISSED, by key); null for none.
 * @param {any} answer @param {Set<string>} dismissed @returns {{ key: string, text: string } | null} */
export function budgetNotice(answer, dismissed) {
  const found = (Array.isArray(answer?.notices) ? answer.notices : []).find((/** @type {any} */ one) =>
    typeof one?.key === "string" && typeof one.text === "string" && !dismissed.has(one.key));
  return found ? { key: found.key, text: found.text } : null;
}

/** The Context panel's cost block from COSTS (costs.py's answer for the conversation): its whole with core's word
 * for it (API value, spent; none with no price), a row a model (the agent's, then the sub-agents' by their model),
 * and the tokens' line; null with no costs. @param {any} costs */
export function costBlock(costs) {
  if (!costs?.agent?.model || typeof costs.text !== "string") return null;
  /** @type {Map<string, { color: string, count: number, cost: number | null }>} */
  const subs = new Map();
  for (const one of Object.values(costs.subs ?? {})) {
    const was = subs.get(one.model.name) ?? { color: one.model.color, count: 0, cost: null };
    subs.set(one.model.name, { ...was, count: was.count + 1,
      cost: typeof one.cost === "number" ? (was.cost ?? 0) + one.cost : was.cost });
  }
  return { session: String(costs.session ?? ""), label: "This conversation", figure: costs.text,
    unit: /\d/.test(costs.text) ? String(costs.kind ?? "") : "",
    rows: [{ name: costs.agent.model.name, color: costs.agent.model.color, figure: costs.agent.text },
      ...[...subs].map(([name, one]) => ({ name: `${name} · ${one.count} sub-agent${one.count === 1 ? "" : "s"}`,
        color: one.color, figure: one.cost === null ? "no price" : money(one.cost, true) }))],
    line: String(costs.line ?? "") };
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
        ? { label: "Yes, and allow edits for the rest of this chat", choice: "keep" } : null);
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
