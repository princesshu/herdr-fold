// @ts-check
// What the mod works out without the window: a diff's rows, the sync button's words, a long job run in the background
// on the space's machine (exec stops a program after 30 s; an AI may take minutes), the commit message writer's answer.

import { JOB } from "./helper.js";

/** @typedef {{ kind: string, number?: number, text: string }} Row */

/** A diff's lines as rows, each numbered once: removed ones by the old file, the others by the new one.
 * @param {string[]} lines
 * @returns {Row[]} */
export function diffRows(lines) {
  let old = 0, next = 0;
  return lines.map((line) => {
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(line);
    if (hunk) {
      old = Number(hunk[1]);
      next = Number(hunk[2]);
      return { kind: "@", text: line };
    }
    const kind = line[0], text = line.slice(1) || " ";
    if (kind === "-") return { kind, number: old++, text };
    if (kind === "+") return { kind, number: next++, text };
    if (kind === " ") {
      old++;
      return { kind, number: next++, text };
    }
    return { kind: "", text: line };
  });
}

/** A commit's message and diff (core/git.py's show) as rows: its header as it is, each file's name a heading, its
 * hunks numbered; a file's own lines (index, ---, +++) left out, what git says instead of a hunk kept.
 * @param {string} text @returns {Row[]} */
export function commitRows(text) {
  /** @type {Row[]} */
  const rows = [];
  /** @type {string[] | null} the file's hunk lines; null before the first file */
  let hunks = null;
  const flush = () => hunks && rows.push(...diffRows(hunks));
  for (const line of text.replace(/\n$/, "").split("\n")) {
    const file = /^diff --git a\/.* b\/(.*)$/.exec(line);
    if (file) {
      flush();
      hunks = [];
      rows.push({ kind: "@", text: file[1] });
    } else if (!hunks) rows.push({ kind: "", text: line });
    else if (hunks.length || line.startsWith("@@")) hunks.push(line);
    else if (line.startsWith("Binary files")) rows.push({ kind: "", text: line });
  }
  flush();
  return rows;
}

/** Each changed file once from core/git.py's status, staged ones first, as git lists them.
 * @param {{ staged: { path: string, code: string }[], changes: { path: string, code: string }[] }} status */
export function changedFiles(status) {
  const seen = new Map();
  for (const { path, code } of [...status.staged, ...status.changes]) {
    if (!seen.has(path)) seen.set(path, { path, code });
  }
  return [...seen.values()];
}

/** A row's buttons, as the TUI sidebar's: a staged file unstages; a change stages and discards (a new file to the
 * Trash, never deleted), but a conflict's, which is settled in the file.
 * @param {"staged" | "changes"} kind @param {string} code @returns {string[]} */
export function rowActions(kind, code) {
  if (kind === "staged") return ["unstage"];
  return code === "U" ? ["stage"] : ["discard", "stage"];
}

/** The Commit button's modes, as the TUI sidebar names them. */
export const MODES = { commit: "Commit", push: "Commit & Push", sync: "Commit & Sync" };

/** The mode kept, or Commit for anything else. @param {unknown} kept @returns {keyof MODES} */
export const commitMode = (kept) => (typeof kept === "string" && kept in MODES ? /** @type {any} */ (kept) : "commit");

/** What follows a commit in MODE: a push, a sync, or nothing. @param {string} mode */
export const afterCommit = (mode) => (mode === "push" || mode === "sync" ? mode : null);

/** @typedef {{ path: string, line: number, text: string, spans: number[][] }} Hit */

/** The search's hits (core/search.py) as the list's rows: each file's row, counting its hits, then its hits.
 * @param {Hit[]} hits */
export function searchRows(hits) {
  /** @type {({ kind: "file", path: string, count: number } | ({ kind: "hit" } & Hit))[]} */
  const rows = [];
  for (const hit of hits) {
    const last = rows.findLast((row) => row.kind === "file");
    if (last?.path === hit.path) /** @type {{ count: number }} */ (last).count++;
    else rows.push({ kind: "file", path: hit.path, count: 1 });
    rows.push({ kind: "hit", ...hit });
  }
  return rows;
}

/** TEXT in pieces, the SPANS (where the query matched, from core/search.py) marked.
 * @param {string} text @param {number[][]} spans */
export function marked(text, spans) {
  const pieces = [];
  let at = 0;
  for (const [start, end] of spans) {
    if (start > at) pieces.push({ text: text.slice(at, start), hit: false });
    pieces.push({ text: text.slice(start, end), hit: true });
    at = end;
  }
  if (at < text.length || !pieces.length) pieces.push({ text: text.slice(at), hit: false });
  return pieces;
}

/** COUNT lines of TEXT from BEFORE lines above line LINE (counted from 1, never before the first): where they start,
 * and the lines, each ending at its newline as the search counts them. @param {string} text @param {number} line
 * @param {number} before @param {number} count */
export function excerpt(text, line, before, count) {
  const start = Math.max(1, line - before), all = text.split("\n");
  if (all.at(-1) === "") all.pop();
  return { start, lines: all.slice(start - 1, start - 1 + count).map((l) => l.replace(/\r$/, "")) };
}

/** The line above the hits, as the TUI sidebar says it.
 * @param {{ total: number, files: number, hits: unknown[], error: string | null }} found */
export function searchSummary(found) {
  if (found.error) return found.error;
  if (!found.total) return "No results found";
  if (found.hits.length < found.total) return `${found.hits.length} of ${found.total} results shown`;
  const s = (n) => (n === 1 ? "" : "s");
  return `${found.total} result${s(found.total)} in ${found.files} file${s(found.files)}`;
}

/** What a program that failed said last (its error, else its output), or its exit code.
 * @param {{ code: number, stdout: string, stderr: string }} out */
export const lastLine = (out) => (out.stderr || out.stdout).trim().split("\n").pop() || `exit ${out.code}`;

/** An error's message, or the thrown value as text. @param {unknown} e */
export const said = (e) => String(e instanceof Error ? e.message : e);

/** The sync button: how far the branch is from its upstream, as the TUI sidebar says it.
 * @param {{ upstream: string | null, ahead: number, behind: number } | null} status */
export function syncLabel(status) {
  return status?.upstream ? `↻ ${status.behind}↓ ${status.ahead}↑` : "↻";
}

/** The node of the layout tree NODE named ID, or null. @param {any} node @param {string} id @returns {any} */
function find(node, id) {
  if (!node || node.id === id) return node ?? null;
  for (const child of node.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

/** What Cmd+Shift+G runs in layout ROOT: the right panel shown at herdr-fold, as the Changes button does, or hidden
 * when it shows that already. @param {any} root */
export function panelToggle(root) {
  const panel = find(root, "panel"), body = find(root, "panel-body");
  return panel && !panel.hidden && body?.active === "changes" ? [["layout.hide", { id: "panel" }]]
    : [["layout.select", { stack: "panel-body", child: "changes" }], ["layout.show", { id: "panel" }]];
}

/** The stack under the panel's views showing the focused tab's own terminal, as the TUI's right column does; its
 * stand-in shows until a tab's terminal is there, its header names the one shown. */
export const TERMINALS = "fold-terminals";
const PREFIX = "fold-terminal-", NONE = "fold-terminal-none";

/** The layout id of TAB's terminal in that stack. @param {string} tab */
export const terminalId = (tab) => PREFIX + tab.toLowerCase().replace(/[^a-z0-9-]+/g, "-");

/** A terminal's machine, from its address (`lab/t7`): null for this computer's. @param {string} address */
export const machineOf = (address) => (address.includes("/") ? address.split("/")[0] : null);

/** CWD as the app's pane header names a folder: from ~ under HOME (this computer's). @param {string | null} cwd
 * @param {string | null} home */
export function folderName(cwd, home) {
  if (!cwd) return "";
  return home && (cwd === home || cwd.startsWith(home + "/")) ? "~" + cwd.slice(home.length) : cwd;
}

/** TREE (a layout) with TAB's terminal, at ADDRESS, in the TERMINALS stack (which draws its frame): a copy, and
 * whether it differs from TREE (else nothing to write).
 * @param {any} tree @param {string} tab @param {string} address */
export function withTerminal(tree, tab, address) {
  const copy = JSON.parse(JSON.stringify(tree)), stack = find(copy, TERMINALS), id = terminalId(tab);
  const child = stack?.children?.find((c) => c.id === id);
  if (!stack || child?.content?.terminal === address) return { tree, changed: false };
  if (child) child.content = { terminal: address };
  else stack.children.push({ id, type: "block", content: { terminal: address } });
  return { tree: copy, changed: true };
}

/** TREE without the terminals of tabs not in LIVE (tab ids) whose machine is in REACHABLE (null: this computer): a
 * copy, and the ids taken out. A machine away lists no tabs, so its terminals wait for it.
 * @param {any} tree @param {string[]} live @param {Set<string | null>} reachable */
export function withoutTabs(tree, live, reachable) {
  const keep = new Set(live.map(terminalId)), copy = JSON.parse(JSON.stringify(tree)), stack = find(copy, TERMINALS);
  const gone = (stack?.children ?? []).filter((c) => c.id.startsWith(PREFIX) && c.id !== NONE && !keep.has(c.id) &&
    reachable.has(machineOf(String(c.content?.terminal ?? "")))).map((c) => c.id);
  if (!gone.length) return { tree, gone };
  stack.children = stack.children.filter((c) => !gone.includes(c.id));
  if (gone.includes(stack.active)) stack.active = NONE;
  return { tree: copy, gone };
}

/** The terminals started for a tab beside the one its block shows (the mod reloaded while one started), to end: only
 * while that one is live, as a terminal replacing an ended one is not in the block yet.
 * @param {any} tree @param {{ address: string, tab: string, live: boolean }[]} labelled */
export function strays(tree, labelled) {
  const shows = new Map((find(tree, TERMINALS)?.children ?? []).map((c) => [c.id, c.content?.terminal]));
  const live = new Set(labelled.filter((t) => t.live).map((t) => t.address));
  return labelled.filter((t) => {
    const shown = shows.get(terminalId(t.tab));
    return t.live && shown && shown !== t.address && live.has(shown);
  }).map((t) => t.address);
}

// core/'s code runs where the repository is, isolated (a module there, a json.py, is never imported for Python's)
// and in UTF-8 on every system; BINARY: python3, or the Python a Windows machine's python.ps1 names
/** @param {string} binary @returns {string[]} */
export const pythonCommand = (binary) => [binary, "-X", "utf8", "-I", "-c"];

/** core/'s SOURCE with ARGS in the background (core/job.py): prepare makes its folder; start, hc's arguments, runs it
 * in a core terminal, which outlives the 30 s an exec may take; poll answers 3, 0 or 4; clear removes the folder.
 * @param {string} binary @param {string} source @param {string[]} args @param {number} [keep] */
export function background(binary, source, args, keep = 600) {
  /** @param {string[]} rest */
  const job = (...rest) => [...pythonCommand(binary), JOB, ...rest];
  return {
    prepare: job("prepare", source),
    /** @param {string} folder @param {string} root @param {string | null} on */
    start: (folder, root, on) => ["run", "--bg", "--json", "--no-parent", "--rm", ...(on ? ["--on", on] : []),
      "--cwd", root, "--", ...job("run", folder, String(keep), ...args)],
    /** @param {string} folder */
    poll: (folder) => job("poll", folder),
    /** @param {string} folder */
    clear: (folder) => job("clear", folder),
  };
}

/** The question before a commit of PATHS, staged files named like secrets (core/commit_message.py), or null.
 * @param {string[]} paths */
export function secretQuestion(paths) {
  const names = paths.map((path) => path.split("/").pop());
  if (!names.length) return null;
  const shown = names.slice(0, 3).join(", ") + (names.length > 3 ? ` and ${names.length - 3} more` : "");
  return names.length === 1 ? `${shown} looks like a secret. Commit it anyway?`
    : `${shown} look like secrets. Commit them anyway?`;
}

/** The commit message writer's answer (core/commit_message.py): the message to fill in, a line to show beside it.
 * @param {{ message: string | null, note: string | null, secret_looking: string[], files?: string[] }} answer */
export function written(answer) {
  if (answer.message) {
    const secrets = answer.secret_looking ?? [];
    const note = secrets.length ? `Staged, named like a secret: ${secrets.join(", ")}` : null;
    return { message: answer.message, note };
  }
  if (!answer.files?.length) return { message: null, note: "Nothing to commit" };
  return { message: null, note: `No message: ${answer.note}` };
}
