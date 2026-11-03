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

/** Each changed file once from core/git.py's status, staged ones first, as git lists them.
 * @param {{ staged: { path: string, code: string }[], changes: { path: string, code: string }[] }} status */
export function changedFiles(status) {
  const seen = new Map();
  for (const { path, code } of [...status.staged, ...status.changes]) {
    if (!seen.has(path)) seen.set(path, { path, code });
  }
  return [...seen.values()];
}

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
