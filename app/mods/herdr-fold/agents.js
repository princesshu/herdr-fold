// @ts-check
// The agents a chat draws, each an adapter: how to start and resume it, its modes, efforts and commands in its own
// words. A new agent is a new adapter here, not new UI; the app draws its icon as it draws the program's (knownAgents).

import { CHAT_HOOK } from "./helper.js";
import { pythonCommand } from "./logic.js";

/** @typedef {{ id: string, label: string, description: string, icon: string, written?: string }} Mode */
/** @typedef {{ name: string, modes: Mode[], efforts: { id: string, label: string }[], switches: string[],
 * commands: { name: string, description: string }[] }} Adapter */

const SESSION = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** The agents by their program's key. @type {Record<string, Adapter>} */
export const ADAPTERS = {
  claude: {
    name: "Claude",
    modes: [
      // written: the name Claude's session file gives the mode, when it is not the one its command line takes
      { id: "manual", label: "Manual", description: "Claude asks before each edit and command", icon: "hand",
        written: "default" },
      { id: "acceptEdits", label: "Edit automatically",
        description: "Claude edits files without asking; commands still ask", icon: "code" },
      { id: "plan", label: "Plan", description: "Claude explores the code and presents a plan before editing",
        icon: "notebook" },
      { id: "auto", label: "Auto",
        description: "Claude approves what passes a safety check and pauses for anything risky", icon: "zap" },
    ],
    efforts: [{ id: "low", label: "Low" }, { id: "medium", label: "Medium" }, { id: "high", label: "High" },
      { id: "xhigh", label: "Extra high" }, { id: "max", label: "Max" }],
    switches: [],
    commands: [
      { name: "/compact", description: "Summarize the conversation so far to free up context" },
      { name: "/context", description: "Show what fills the context window" },
      { name: "/review", description: "Review a pull request" },
      { name: "/usage", description: "Show the plan's usage limits" },
    ],
  },
};

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
