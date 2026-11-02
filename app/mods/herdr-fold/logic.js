// @ts-check
// What the mod works out without the window: a diff's rows, the sync button's words, a long job run in the background
// on the space's machine (exec stops a program after 30 s; an AI may take minutes), the commit message writer's answer.

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

// core/'s code runs in the repository's folder, isolated: a module there (a json.py) is never imported for Python's
export const PYTHON = ["python3", "-I", "-c"];

// a job's own folder, made by mktemp: poll answers 3 while the job runs, then 0 and its output or 4 and its error;
// clear removes that folder and nothing else
const START = 'd=$(mktemp -d "${TMPDIR:-/tmp}/herdr-fold.XXXXXX") || exit 1; src=$1; shift; '
  + `(${PYTHON.join(" ")} "$src" "$@" >"$d/out" 2>"$d/err"; echo $? >"$d/done") </dev/null >/dev/null 2>&1 & echo "$d"`;
const POLL = 'test -f "$1/done" || exit 3; read code <"$1/done"; '
  + 'if [ "$code" = 0 ]; then cat "$1/out"; else tail -n 3 "$1/err" >&2; exit 4; fi';
const CLEAR = 'case "$1" in */herdr-fold.*) rm -rf -- "$1" ;; esac';

/** SOURCE (python) run with ARGS in the background: start prints its folder, poll answers 3, 0 or 4, clear removes it.
 * @param {string} source
 * @param {string[]} args */
export function background(source, args) {
  return {
    start: ["sh", "-c", START, "sh", source, ...args],
    /** @param {string} folder */
    poll: (folder) => ["sh", "-c", POLL, "sh", folder],
    /** @param {string} folder */
    clear: (folder) => ["sh", "-c", CLEAR, "sh", folder],
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
