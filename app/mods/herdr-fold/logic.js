// @ts-check
// What the mod works out without the window: a diff's rows, the sync button's words, a long job run in the background
// on the space's machine (exec stops a program after 30 s; an AI may take minutes), the commit message writer's answer.

import { JOB, MEDIA_KINDS, MEDIA_WEB } from "./helper.js";
import { BY_EXTENSION, BY_NAME, FILE, FOLDER, LETTER } from "./icons.js";
import { format, written as timeIn } from "./timeline.js";

/** @typedef {{ kind: string, number?: number, text: string }} Row */

/** A diff's lines as rows, each numbered once: removed ones by the old file, the others by the new one; no hunk
 * header (the numbers say where), a gap between two hunks instead. @param {string[]} lines @returns {Row[]} */
export function diffRows(lines) {
  let old = 0, next = 0, hunks = 0;
  return lines.flatMap((line) => {
    const hunk = /^@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(line);
    if (hunk) {
      old = Number(hunk[1]);
      next = Number(hunk[2]);
      return hunks++ ? [{ kind: "gap", text: "" }] : [];
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

/** A row's buttons, as the TUI sidebar's: a staged file unstages; a change stages and discards (a new file to the
 * Trash, never deleted), but a conflict's, which is settled in the file.
 * @param {"staged" | "changes"} kind @param {string} code @returns {string[]} */
export function rowActions(kind, code) {
  if (kind === "staged") return ["unstage"];
  return code === "U" ? ["stage"] : ["discard", "stage"];
}

/** A row's on_hover: HOLDER.hovered is KEY while the pointer is over it, so its buttons show only then.
 * @param {{ hovered: string | null }} holder @param {string} key */
export const hovering = (holder, key) => (/** @type {boolean} */ over, /** @type {any} */ cx) => {
  if (over) holder.hovered = key;
  else if (holder.hovered === key) holder.hovered = null;
  cx.notify();
};

/** The folded sections as KEPT, as the TUI sidebar keeps them (staged, changes, graph): a set, empty for anything
 * else. @param {unknown} kept @returns {Set<string>} */
export const foldedSections = (kept) => new Set(Array.isArray(kept)
  ? kept.filter((kind) => ["repositories", "staged", "changes", "graph"].includes(kind)) : []);

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

/** A folder's icon, Catppuccin Icons' closed or OPEN. @param {boolean} open */
export const folderIcon = (open) => (open ? FOLDER.open : FOLDER.closed);

/** A change's color, as the TUI's: new green, deleted or in conflict red, any other change yellow.
 * @param {any} t @param {string} code */
export const changeColor = (t, code) => (code === "A" || code === "?" ? t.ansi2
  : code === "D" || code === "U" ? t.ansi1 : t.ansi3);

/** An entry of a folder, as core/tree.py lists it. @typedef {{ name: string, dir: boolean, mark: string | null,
 *   ignored: boolean }} Entry */
/** A row of the Files tree: an entry, its path from the root, how deep and whether open; or a full folder's rest.
 * @typedef {(Entry & { path: string, depth: number, open: boolean }) | { path: null, more: number, depth: number }}
 *   FileRow */

/** The Files tree's rows as the TUI's: each read folder's entries in order, an open folder's under it, a very full
 * one's count of the rest last. @param {Record<string, { entries: Entry[], more: number }>} folders
 * @param {Set<string>} open @param {string} [folder] @param {number} [depth] @returns {FileRow[]} */
export function fileRows(folders, open, folder = "", depth = 0) {
  const read = folders[folder];
  if (!read) return [];
  /** @type {FileRow[]} */
  const rows = [];
  for (const entry of read.entries) {
    const path = folder ? `${folder}/${entry.name}` : entry.name, opened = entry.dir && open.has(path);
    rows.push({ ...entry, path, depth, open: opened });
    if (opened) rows.push(...fileRows(folders, open, path, depth + 1));
  }
  if (read.more) rows.push({ path: null, more: read.more, depth });
  return rows;
}

/** A file's icon, Catppuccin Icons' by the path the app loads it, as core/icons.py's file_type(): by the name's
 * start, else its extension. @param {string} name */
export function fileIcon(name) {
  const lower = name.toLowerCase(), dot = lower.lastIndexOf(".");
  const named = BY_NAME.find(([, starts]) => starts.some((start) => lower.startsWith(start)));
  if (named) return named[0];
  /** @type {Record<string, string>} */
  const byExtension = BY_EXTENSION, ext = dot > 0 ? lower.slice(dot + 1) : "";
  return Object.hasOwn(byExtension, ext) ? byExtension[ext] : FILE;       // never an object's own property
}

/** A change's letter as the TUI sidebar shows git's CODE (an untracked file U, a conflict !). @param {string} code */
export const letter = (code) => /** @type {Record<string, string>} */ (LETTER)[code] ?? code;

const CHANGES = { M: "Modified", A: "Added", D: "Deleted", "?": "Untracked", U: "Conflict", R: "Renamed", C: "Copied",
  T: "Type changed" };

/** What git's CODE says of a change, as the mouse resting on its letter says it. @param {string} code */
export const changeName = (code) => /** @type {Record<string, string>} */ (CHANGES)[code] ?? code;

/** An issue's MARKDOWN as its preview shows it. Anyone may write an issue: an unseen word joiner splits each "![" and
 * each tag's "<", in code or not (no guess at where code is), so an image is a link, never fetched (that would tell its
 * host the viewer's address), and HTML shows as text. @param {string} markdown */
export const safeMarkdown = (markdown) => markdown.replace(/!\[/g, "!⁠[").replace(/<(?=[A-Za-z/!?])/g, "<⁠");

/** A priority's color by its rank (LEVEL, core/github.py's: Urgent 0 to Low 3), as the TUI sidebar's traffic light;
 * the accent without one. @param {Record<string, string>} t @param {number | null | undefined} level */
export const priorityColor = (t, level) => (level === null || level === undefined ? t.accent
  : [t.ansi1, t.ansi1, t.ansi3, t.ansi2][level]);

/** The focused TAB's own Claude or Codex, to hand an issue to: one in a pane among AGENTS (the app's agents()), else a
 * chat tab's agent among TERMINALS (the app's); or null. @param {{ tab: string, program?: { key: string } }[]} agents
 * @param {string | undefined} tab @param {any[]} [terminals] @returns {any} */
export const issueAgent = (agents, tab, terminals = []) =>
  agents.find((a) => a.tab === tab && ["claude", "codex"].includes(a.program?.key ?? ""))
  ?? (tab ? terminals.filter((c) => c.state === "live" && c.labels?.[CHAT_TAB] === tab)
    .map((c) => ({ ...c, chat: true }))[0] : null) ?? null;

/** A chat as core/chats.py lists it: a running one's STATE (herdr's) and PANE (its terminal) set.
 * @typedef {{ agent: string, id: string, title: string, folder: string, time: number, state: string,
 *   pane: string }} Chat */

/** The app's AGENTS as core/chats.py takes herdr's: those whose chats it lists (RESUME's) in this Mac's spaces
 * (LOCAL, their ids), each with its pane's folder (from PANES), its terminal for its pane.
 * @param {any[]} agents @param {any[]} panes @param {Set<string>} local */
export const coreAgents = (agents, panes, local) => agents
  .filter((a) => local.has(a.space) && Object.hasOwn(RESUME, a.program?.key ?? ""))
  .map((a) => ({ agent: a.program.key, agent_status: a.status, pane_id: a.address,
    cwd: panes.find((p) => p.pane === a.pane)?.cwd ?? null }));

/** {folder: space name}: each folder a pane of this Mac's SPACES is in, the first such pane's space, as the TUI's
 * column reads herdr's panes. @param {any[]} spaces @param {any[]} panes */
export function folderSpaces(spaces, panes) {
  const of = new Map(spaces.filter((s) => s.machine === null).flatMap((s) => s.tabs.map((t) => [t.id, s.name])));
  /** @type {Record<string, string>} */
  const folders = {};
  for (const pane of panes) {
    const space = of.get(pane.tab);
    if (pane.cwd && space && !(pane.cwd in folders)) folders[pane.cwd] = space;
  }
  return folders;
}

const URGENCY = ["blocked", "done", "working", "idle"];      // as the app orders a space's agents

/** The most urgent of STATES, as the app's SpaceInfo.status has it; null when none is an agent's.
 * @param {(string | null | undefined)[]} states */
export const urgent = (states) => URGENCY.find((state) => states.includes(state)) ?? null;

/** ITEM's key among the archived, as the TUI's column keeps it. @param {Chat} item */
export const archiveKey = (item) => `${item.agent}:${item.id}`;

/** Each space of ORDER with its ITEMS (PLACE: {folder: space}) matching TYPED, FRONT's first, then the newest; none
 * shown: left out; archived ones typed or shown; HERE open unless CLOSED, others OPENED or typed. @param {Chat[]} items
 * @param {string[]} order @param {Record<string, string>} place @param {any} how */
export function chatRows(items, order, place, how) {
  const { typed = "", archived = new Set(), showArchived = false, opened = new Set(), closed = new Set(), here = null,
    front = new Set() } = how;
  const word = typed.toLowerCase();
  const matches = (item) => !word || [item.title, place[item.folder] ?? "", item.folder,
    archived.has(archiveKey(item)) ? "archived" : ""].some((part) => part.toLowerCase().includes(word));
  const open = (name) => Boolean(word) || opened.has(name) || (!closed.has(name) && name === here);
  // a chat outside every open space under its folder's name, as a project: none is left out for want of a space
  const named = { ...place }, projects = [];
  for (const item of [...items].sort((a, b) => b.time - a.time)) {
    if (named[item.folder]) continue;
    named[item.folder] = item.folder.split(/[\\/]/).filter(Boolean).pop() ?? item.folder;
    const name = named[item.folder];
    if (!order.includes(name) && !projects.includes(name)) projects.push(name);
  }
  place = named;
  return [...order, ...projects].flatMap((name) => {
    const found = items.filter((item) => place[item.folder] === name && matches(item)
      && (!archived.has(archiveKey(item)) || Boolean(word) || showArchived))
      .sort((a, b) => Number(front.has(b.pane)) - Number(front.has(a.pane)) || b.time - a.time);
    if (!found.length) return [];
    const group = { kind: "group", name, items: found, open: open(name), here: name === here };
    const under = group.open ? found.map((item, n) => ({ kind: "item", item, last: n === found.length - 1 })) : [];
    return [group, ...under];
  });
}

/** The group FOLDER's chats stand under in the list (chatRows'): its space's (PLACE: {folder: space}), else the
 * folder's own name; null for no folder. @param {string} folder @param {Record<string, string>} place */
export const folderGroup = (folder, place) => place[folder] ?? folder.split(/[\\/]/).filter(Boolean).pop() ?? null;

/** The list's opening as KEPT (herdr-fold.chats-opened): when, and the group a chat's clock asked for (none: the
 * tab bar's Chats). @param {unknown} kept @returns {{ at: number | null, space: string | null }} */
export function chatsAsked(kept) {
  const one = /** @type {any} */ (kept && typeof kept === "object" ? kept : { at: kept });
  return { at: typeof one.at === "number" ? one.at : null, space: typeof one.space === "string" ? one.space : null };
}

/** Where the group NAME stands among the list's children as drawn from ROWS (chatRows': a group is its head, then
 * its chats' block): its head's place and the list's last, which it is scrolled back from, so it comes first in view;
 * null for no such group. @param {{ kind: string, name?: string }[]} rows @param {string} name */
export function groupPlace(rows, name) {
  const groups = rows.filter((row) => row.kind === "group"), at = groups.findIndex((row) => row.name === name);
  return at < 0 ? null : { head: at * 2, last: groups.length * 2 - 1 };
}

/** A chat's id as each agent's CLI takes it to reopen: from a file's content, so never an option, a space or a
 * control code. */
const SESSION = /^[0-9A-Za-z][0-9A-Za-z._-]*$/;
/** The agents whose chats core lists, each with the word its CLI takes before the id it reopens (core's RESUME). */
const RESUME = /** @type {Record<string, string>} */ ({ claude: "--resume", codex: "resume", opencode: "--session" });

/** The command that reopens ITEM, a closed chat: its agent resuming it. @param {Chat} item */
export function resumeArgv(item) {
  if (!SESSION.test(item.id) || !Object.hasOwn(RESUME, item.agent)) throw new Error("not a chat's id");
  return [item.agent, RESUME[item.agent], item.id];
}

const CHOICES = ["Open", "Copy chat", "Rename"];

/** The right click's menu on ITEM: Archive for a closed one, Unarchive for an archived one, then Delete… (off for a
 * running one: deleteOff); on none (null), Show or Hide archived while any is. @param {Chat | null} item
 * @param {Set<string>} archived @param {boolean} showArchived */
export function chatChoices(item, archived, showArchived) {
  if (!item) return archived.size ? [showArchived ? "Hide archived" : "Show archived"] : [];
  const tidy = archived.has(archiveKey(item)) ? ["Unarchive"] : item.state ? [] : ["Archive"];
  return [...CHOICES, ...tidy, "Delete…"];
}

/** Why ITEM's Delete… is off, its tip: a running chat's file is its agent's, an OpenCode chat is no file of its own
 * (core's TRASHED); null for a closed one. @param {Chat} item */
export const deleteOff = (item) => (item.state ? "A running chat is not deleted: close it first"
  : item.agent === "opencode" ? "OpenCode keeps its chats in its own database: delete it there" : null);

/** ITEMS without the chats on their way to the Trash (LEAVING: archiveKey's): a deleted one's row leaves at once.
 * @template {Chat} T @param {T[]} items @param {Set<string>} leaving */
export const withoutLeaving = (items, leaving) => (leaving.size ? items.filter((c) => !leaving.has(archiveKey(c)))
  : items);

/** LEAVING still to hide once ITEMS were read again: those the list still holds (a read begun before the file left).
 * @param {Set<string>} leaving @param {Chat[]} items */
export const stillLeaving = (leaving, items) => new Set(items.map(archiveKey).filter((key) => leaving.has(key)));

const TAB_NAME = 24;          // a chat's name on its tab, as the TUI's column (AI Sessions') puts it there

/** TITLE as a reopened chat's tab name: printable characters only, no leading dash, cut with "…".
 * @param {string} title */
export function tabLabel(title) {
  const name = [...title].filter((ch) => ch === " " || !/[\p{C}\p{Z}]/u.test(ch)).join("").replace(/^[- ]+/, "");
  return name.length <= TAB_NAME ? name : `${name.slice(0, TAB_NAME - 1)}…`;
}

/** An issue as its preview shows it, with its priority as the list ranked it; a pull request's review.
 * @typedef {{ kind: "issue" | "pull", github: string, number: number, title: string, level?: number | null,
 *   ranked_by?: string | null }} ShownIssue */
/** What a preview shows, where (ROOT on ON): a change's diff (a new file's as all added), a file (from its LINE), a
 * commit, an issue or a pull request. @typedef {{ root: string, on: string | null } & ({ kind: "diff" | "file",
 *   path: string, line?: number } | { kind: "commit", hash: string } | ShownIssue)} Shown */

/** A preview tab's name starts so, as the TUI sidebar's: what it shows follows. */
const PREVIEWED = "preview: ";
const TAB_TITLE = 20;              // characters of an issue's title in its preview tab's name, as the TUI sidebar's

/** WHAT's preview tab name, as the TUI sidebar's: the file, the commit, or the issue's number and its title's start.
 * @param {Shown} what */
export function previewName(what) {
  if (what.kind === "diff" || what.kind === "file") return PREVIEWED + what.path;
  if (what.kind === "commit") return PREVIEWED + what.hash;
  const title = what.title.length > TAB_TITLE ? `${what.title.slice(0, TAB_TITLE - 1).trimEnd()}…` : what.title;
  return `${PREVIEWED}#${what.number} ${title}`;
}

/** SPACE's preview tab: a tab named as one with herdr-fold as its pane (PANES, the app's panes()); or null.
 * @param {{ tabs?: { id: string, name: string }[] } | undefined} space
 * @param {{ tab: string, mod?: string }[]} panes */
export const previewTab = (space, panes) => space?.tabs?.find((t) => t.name.startsWith(PREVIEWED) &&
  panes.some((p) => p.tab === t.id && p.mod === "herdr-fold")) ?? null;

/** The sync button's words after its icon: how far the branch is from its upstream, as the TUI sidebar says it.
 * @param {{ upstream: string | null, ahead: number, behind: number } | null} status */
export function syncLabel(status) {
  return status?.upstream && (status.behind || status.ahead) ? `${status.behind}↓ ${status.ahead}↑` : "";
}

/** Cmd + Shift + C's question with nothing to commit and commits ahead of the upstream, as the TUI's asks; else null.
 * @param {any} status @returns {string | null} */
export function pushOffer(status) {
  if (!status?.upstream || !status.ahead || status.staged.length || status.changes.length) return null;
  return `Nothing to commit. Push ${status.ahead} commit${status.ahead === 1 ? "" : "s"}?`;
}

/** The repository row's branch, as the TUI sidebar's footer names it: * after it with changes; detached without one.
 * @param {any} status */
export function branchLabel(status) {
  if (!status) return "";
  return `${status.branch ?? "detached"}${status.staged.length || status.changes.length ? "*" : ""}`;
}

/** The node of the layout tree NODE named ID, or null. @param {any} node @param {string} id @returns {any} */
export function find(node, id) {
  if (!node || node.id === id) return node ?? null;
  for (const child of node.children ?? []) {
    const found = find(child, id);
    if (found) return found;
  }
  return null;
}

const RAIL_BELOW = 160;       // px: a sidebar narrower draws its mods as a rail, as the app's own mods do

/** Layout ROOT's sidebar's width in px, or null. @param {any} root @returns {number | null} */
export const sidebarPx = (root) => find(root, "sidebar")?.size?.px ?? null;

/** Whether layout ROOT's sidebar is folded to a rail. @param {any} root */
export const railed = (root) => (sidebarPx(root) ?? Infinity) < RAIL_BELOW;

export const SIDEBAR_PX = 268;               // px: the left sidebar open, unless it kept another width

/** The left sidebar's rail, as the app's own toggle folds it: as wide as the traffic lights on macOS (MACOS), RAIL,
 * else 44. @param {boolean} macos */
export const sidebarRail = (macos) => (macos ? RAIL : 44);

/** The width layout ROOT's sidebar takes when its toggle is pressed, as the app's own toggle has it: folded, its rail
 * (MACOS's); opened, KEPT, the width it had, else SIDEBAR_PX.
 * @param {any} root @param {boolean} macos @param {number | undefined} kept */
export const foldedWidth = (root, macos, kept) => (railed(root) ? kept ?? SIDEBAR_PX : sidebarRail(macos));

// a side's width once a drag lets go of it, as the TUI's: SETTLE ms unchanged is let go, not on the way; a rail
// widened more than UNFOLD px (the TUI's 3 cells) opens as its toggle does
export const UNFOLD = 24, SETTLE = 300;

/** Where a side dragged PX wide comes to rest (null: as it is), having rested FROM px wide last (null: not seen yet):
 * a rail widened past UNFOLD at KEPT, its toggle's width, however far; else under RAIL_BELOW at its RAIL.
 * @param {number | null} px @param {number | null} from @param {number} rail @param {number} kept */
export function restWidth(px, from, rail, kept) {
  if (px === null) return null;
  const to = from !== null && from < RAIL_BELOW && px - rail > UNFOLD ? kept : px < RAIL_BELOW ? rail : px;
  return to === px ? null : to;
}

/** A side's width PX unchanged for SETTLE ms, as its follower SEEN ({ from, pending }) had it: its own last setting
 * (PENDING) held, rested there; else REST(from) sets where it comes to rest, which counts once it holds (a pause in a
 * drag, the drag going on, never moves FROM). @param {any} seen @param {number | null} px @param {any} rest */
export function restAt(seen, px, rest) {
  if (px !== null && px === seen.pending) return void Object.assign(seen, { from: px, pending: null });
  const to = rest(seen.from);
  Object.assign(seen, to === px ? { from: px, pending: null } : { pending: to });
}

/** Where ROOT's left sidebar comes to rest once let go (restWidth: FROM px last, KEPT its open width, its rail MACOS's
 * but never under the layout's least): its width, whether open, the command putting it there; hidden, as it is.
 * @param {any} root @param {number | null} from @param {number | undefined} kept @param {boolean} macos */
export function sidebarRest(root, from, kept, macos) {
  const side = find(root, "sidebar"), px = sidebarPx(root), rail = Math.max(sidebarRail(macos), side?.min ?? 0);
  const to = side && !side.hidden ? restWidth(px, from, rail, kept ?? SIDEBAR_PX) : null, at = to ?? px;
  return { to: at, open: at !== null && at >= RAIL_BELOW,
    commands: /** @type {[string, any][]} */ (to === null ? [] : [["layout.resize", { id: "sidebar", px: to }]]) };
}

export const SIDE_FOOT = "sidebar-footer";         // the sidebar's footer under Spaces, while the sidebar is open

/** The commands that show layout ROOT's left side as its width says: open or a rail, never hidden (anything that hid
 * it, shown again at once: its toggle is in it), its footer while it is open. @param {any} root
 * @returns {[string, any][]} */
export function sidebarFollow(root) {
  const side = find(root, "sidebar"), foot = find(root, SIDE_FOOT);
  if (!side) return [];
  if (side.hidden) return [["layout.show", { id: "sidebar" }]];
  const open = !railed(root);
  return foot && Boolean(foot.hidden) === open ? [[open ? "layout.show" : "layout.hide", { id: SIDE_FOOT }]] : [];
}

/** The commands of the sidebar's toggle (in its head; Cmd+B) in layout ROOT: open, folded to its rail
 * (MACOS's); a rail, opened KEPT wide (else SIDEBAR_PX); hidden by the app's own key, shown open.
 * @param {any} root @param {boolean} macos @param {number | undefined} kept @returns {[string, any][]} */
export function sidebarToggle(root, macos, kept) {
  const side = find(root, "sidebar");
  if (!side) return [];
  const resize = (/** @type {number} */ px) => /** @type {[string, any]} */ (["layout.resize", { id: "sidebar", px }]);
  if (side.hidden) return [["layout.show", { id: "sidebar" }], ...(railed(root) ? [resize(kept ?? SIDEBAR_PX)] : [])];
  return [resize(foldedWidth(root, macos, kept))];
}

/** Whether a press AT ({ x, y }, the window's) outside a float of PANEL closes it, in layout ROOT a window WIDTH wide,
 * the tab bar's end END px from its edge: never while a menu or window of the mod is UP (a press there is the float's
 * own), nor on its side's own controls (its rail, the toggle over it; ✦, More, «), which open and close floats. */
export function pressCloses(panel, { x, y }, root, width, end, up) {
  const title = find(root, "title")?.size?.px ?? 0, bar = title + (find(root, "top")?.size?.px ?? 0);
  if (up) return false;
  if (y < title) return true;
  if (panel === "spaces") return x > (sidebarPx(root) ?? RAIL) + (find(root, "workspace")?.divider?.width ?? 0);
  if (y < bar) return x < width - end;
  return x < width - (find(root, "work-body")?.padding ?? 0) - (panelPx(root) ?? RAIL);
}

/** Whether a float of PANEL beside its rail has outlived it in layout ROOT: Spaces once the sidebar opens or hides, a
 * view (Chats too) once the dock does; its side shows it then. @param {string} panel @param {any} root */
export const floatStale = (panel, root) => (panel === "spaces" ? !railed(root) || Boolean(find(root, "sidebar")?.hidden)
  : !panelRailed(root) || !panelShown(root));

/** A side's float as its shared value KEPT names it ({ panel, overlay } while one shows), else null. @param {any} kept
 * @returns {{ panel: string, overlay: string } | null} */
export const floating = (kept) => (kept && typeof kept === "object" && typeof kept.panel === "string"
  && typeof kept.overlay === "string" ? { panel: kept.panel, overlay: kept.overlay } : null);

/** SPACE's tabs as the tab bar draws them: one nobody named takes the space's name on the first, else its program's
 * (a chat tab's: CHATS), else Terminal; an agent's icon (TINT: the text's color), its state (a chat WAITING on you
 * blocked), zoomed marked Z, an editor's UNSAVED changes. @param {any} space @param {any[]} panes */
export function tabRows(space, panes, /** @type {Record<string, any>} */ chats = {},
  /** @type {Set<string>} */ waiting = new Set(), /** @type {Set<string>} */ unsaved = new Set()) {
  return (space?.tabs ?? []).map((/** @type {any} */ c, /** @type {number} */ i) => {
    const program = chats[c.id]?.program ?? panes.find((p) => p.tab === c.id && p.program?.agent)?.program
      ?? panes.find((p) => p.tab === c.id)?.program;
    const given = !c.named, first = i === 0 && space.name;
    const name = !given ? c.name : first ? space.name : program?.name ?? "Terminal";
    const agent = program?.agent ? program : null;
    return { id: c.id, name: c.zoomed ? `${name} Z` : name, active: Boolean(c.active),
      status: waiting.has(c.id) ? "blocked" : c.status ?? chats[c.id]?.status ?? null,
      icon: agent?.icon ?? null, tint: Boolean(agent?.tint), unsaved: unsaved.has(c.id) };
  });
}

/** Whether an SVG's or a page's code goes above its picture: as CHOSEN, else where the ROOM (logical px) is taller
 * than wide, as the TUI's. @param {boolean | null} chosen @param {{ width: number, height: number } | null} room */
export function stacks(chosen, room) {
  return chosen ?? Boolean(room && room.height > room.width);
}

const MENU_EDGE = 8, MENU_OFF = 4;       // px a menu keeps from the window's edges, and from its button

/** Where a menu HIGH and WIDE opens for BUTTON in a window ROOM: under it, right edges in line (LEFT: left edges),
 * where it fits; else above it; else as far in as the window lets it. @param {{ x: number, y: number, width: number,
 * height: number }} button @param {number} high @param {{ width: number, height: number }} room @param {number} wide */
export function menuPlace(button, high, room, wide, left = false) {
  const x = Math.max(MENU_EDGE, Math.min(left ? button.x : button.x + button.width - wide,
    room.width - MENU_EDGE - wide));
  const under = button.y + button.height + MENU_OFF, over = button.y - MENU_OFF - high;
  if (under + high <= room.height - MENU_EDGE) return { x, y: under };
  return { x, y: over >= MENU_EDGE ? over : Math.max(MENU_EDGE, room.height - MENU_EDGE - high) };
}

/** A list a key opens (Cmd+Shift+L's files, Cmd+K Cmd+T's themes), WIDE px: under a button ROOM's top centre, so
 * menuPlace sets it where the palette stands (palettePlace). @param {{ width: number }} room @param {number} wide */
export const keyMenuBounds = (room, wide) => ({ x: Math.round((room.width - wide) / 2), y: 0, width: wide,
  height: MENU_EDGE - MENU_OFF });

const MENU_ROW = 28, MENU_RULE = 9, MENU_GAP = 2, MENU_PAD = 4;      // px: a menu's row, its rule, between, round
const MENU_FIND = 32;              // px: a menu's filter on top, a field (parts.js's)

/** The height of a menu of ITEMS (null: a rule between its parts) under its HEAD, under a filter (FIND).
 * @param {(object | null)[]} items @param {object} [head] @param {boolean} [find] */
export const menuHeight = (items, head, find = false) => items.reduce((h, item) => h + (item ? MENU_ROW : MENU_RULE)
  + MENU_GAP, (head ? MENU_ROW + MENU_GAP : 0) + (find ? MENU_FIND + MENU_GAP : 0)) + 2 * MENU_PAD;

// the one Settings (settings.html): the sidebar's Settings and ⌘, open it, one window of one size, its sections at its
// left (a row ROW high), the Herdr app's under its title APART below them
export const SETTINGS = { wide: 600, high: 380, head: 44, side: 160, pad: 24, row: 28, apart: 10 };
/** Its sections in order, each [id, name]. @type {[string, string][]} */
export const SECTIONS = [["general", "General"], ["notifications", "Notifications"], ["about", "About"]];
/** The app's own sections under Application, each [id, name]: each opens the app's Settings there (app.settings); its
 * Alerts is Notifications' last row. @type {[string, string][]} */
export const APP_SECTIONS = [["look", "Look"], ["machines", "Machines"], ["updates", "Updates"],
  ["privacy", "Privacy"]];

/** The section shown for the one KEPT (the one last looked at; General at first). @param {unknown} kept */
export const settingsSection = (kept) => (SECTIONS.some(([id]) => id === kept) ? String(kept) : SECTIONS[0][0]);

/** The section STEP (↑ -1, ↓ 1) from SECTION, staying at the list's ends. @param {string} section
 * @param {number} step */
export function sectionStep(section, step) {
  const at = SECTIONS.findIndex(([id]) => id === section);
  return SECTIONS[Math.max(0, Math.min(SECTIONS.length - 1, at + step))][0];
}

/** What Tab steps through in SECTION: General's one choice, Notifications' and its Herdr app alerts, About's links and
 * buttons (ABOUT: aboutState's). @param {string} section @param {ReturnType<typeof aboutState>} about */
export const settingsTargets = (section, about) => (section === "about" ? aboutTargets(about)
  : section === "notifications" ? ["notes", "alerts"] : ["opens"]);

/** herdr-fold's layout file's TEXT with its root's toast as An agent waits on you (ON) says: off, MOD's (its part
 * closes each note at once); on, none (the app's own); null when so already, or another mod's.
 * @param {string} text @param {boolean} on @param {string} mod */
export function layoutToast(text, on, mod) {
  const root = JSON.parse(text);
  if (on ? root.toast !== mod : root.toast !== undefined) return null;
  if (on) delete root.toast;
  else root.toast = mod;
  return `${JSON.stringify(root, null, 2)}\n`;
}

/** Whether a note of LEVEL (notify()'s: info, success, warning, error) shows while An agent waits on you is off:
 * an error or a warning always does. @param {unknown} level */
export const noteShown = (level) => level === "error" || level === "warning";

/** The app's settings.json TEXT (null: none yet) with its sounds as An agent waits on you (ON) says, and the person's
 * own value KEPT to give back: off, none, theirs kept; on, theirs again (none kept: on).
 * @param {string | null} text @param {boolean} on @param {boolean | null} kept */
export function soundsFor(text, on, kept) {
  const settings = text ? JSON.parse(text) : {}, now = settings.sounds?.enabled !== false;
  const sounds = { ...(settings.sounds ?? {}), enabled: on ? kept !== false : false };
  return { text: `${JSON.stringify({ ...settings, sounds }, null, 2)}\n`, kept: on ? null : now };
}

// its About section, in the TUI's words

/** The license TEXT (the mod's own LICENSE) says: its kind (its first line), the year, the holder's name and page.
 * @param {string} text @returns {{ kind: string, year: string, name: string, url: string | null } | null} */
export function licenseOf(text) {
  const held = /^Copyright \(c\) (\d{4}) (.+?)(?: \((https?:\/\/[^)\s]+)\))?\s*$/m.exec(text);
  return held ? { kind: text.split("\n")[0].trim(), year: held[1], name: held[2], url: held[3] ?? null } : null;
}

/** When a look was (SECONDS, epoch), as About says it: at its time today (this Mac's form), else on its day (Nov 12).
 * @param {number} seconds @param {number} now ms */
const lookedWhen = (seconds, now) => {
  const when = new Date(seconds * 1000), today = new Date(now);
  return when.toDateString() === today.toDateString() ? `at ${timeIn(when, "time")}` : `on ${format(when, "MMM d")}`;
};

/** About's rows from FOUND (core/update.py's check; null before it answers), CHECKING, at NOW (ms), LICENSE: the
 * version line's groups (the holder's name a link), the state (a mark, words, when it looked, tone, a spinner), how
 * to update, its buttons (none without an install), the box (null: none). @param {any} found @param {any} [how] */
export function aboutState(found, { checking = false, now = Date.now(), license = null } = {}) {
  const version = found?.version ?? null, latest = found?.latest, checked = found?.checked ?? null;
  const state = (/** @type {string | null} */ mark, /** @type {string} */ title, note = "", tone = "foreground",
    spin = false) => ({ mark, title, note, tone, spin });
  const shown = checking || !found ? state(null, "Checking for updates…", "", "muted", true)
    : !version ? state(null, "Not installed by herdr-fold's installer", "", "muted")
      : found.error ? state(null, "Couldn't check", checked ? `Last checked ${lookedWhen(checked, now)}` : found.error,
        "ansi1")
        : found.newer ? state("up", `${latest} is out`, `Checked ${lookedWhen(checked ?? now / 1000, now)}`)
          : checked ? state("ok", "Up to date", `Checked ${lookedWhen(checked, now)}`)
            : state(null, "Checked by hand only", "", "muted");
  const newer = Boolean(found?.newer) && Boolean(version);
  const held = /** @type {{ kind: string, year: string, name: string, url: string | null } | null} */ (license);
  const credits = [...(version ? [[{ text: `Version ${version}` }]] : []), ...(held ? [[{ text: `© ${held.year}` },
    held.url ? { text: held.name, url: held.url } : { text: held.name }], [{ text: held.kind }]] : [])];
  return { credits, state: shown,
    how: !newer || checking ? null : found.error ? `${latest} is out: ${found.how}` : found.how,
    buttons: version ? [newer ? { id: "first", label: "Release notes ↗", url: found.releases }
      : { id: "first", label: "What's new" }, { id: "check", label: "Check now" }] : [],
    box: version ? found.on !== false : null };
}

/** What About's keys step through (Tab, Shift+Tab), in order: the author's link, its buttons, the box, the notices.
 * @param {ReturnType<typeof aboutState>} state */
export const aboutTargets = (state) => [...(state.credits.flat().some((part) => "url" in part) ? ["author"] : []),
  ...state.buttons.map((b) => b.id), ...(state.box === null ? [] : ["box"]), "notices"];

/** About's sizes, px: its head (the name and the version line), between its parts, the state's row, the how line and
 * its gap over it, the box's row, the notices' line. */
export const ABOUT = { head: 52, gap: 20, state: 36, howGap: 8, how: 32, box: 20, legal: 16 };

/** The height About's rows take for STATE (aboutState's): the window keeps its one size, so its tallest (a newer one's
 * how line) fills the section's room and no other moves. @param {ReturnType<typeof aboutState>} state */
export const aboutHeight = (state) => ABOUT.head + ABOUT.gap + ABOUT.state
  + (state.how ? ABOUT.howGap + ABOUT.how : 0) + (state.box === null ? 0 : ABOUT.gap + ABOUT.box) + ABOUT.gap
  + ABOUT.legal;

/** The status bar's agents (AGENTS' statuses) in words, as the mockups' bar says them, and their dot's role: those
 * waiting on you first, else those working, else how many. @param {(string | null)[]} statuses */
export function agentsSaid(statuses) {
  const all = statuses.length, count = (/** @type {number} */ n) => `${n} agent${n === 1 ? "" : "s"}`;
  const some = (/** @type {number} */ n, /** @type {string} */ doing) => n === all ? `${count(n)} ${doing}`
    : `${n} of ${count(all)} ${doing}`;
  const waiting = statuses.filter((s) => s === "blocked").length;
  const working = statuses.filter((s) => s === "working").length;
  if (waiting) return { words: some(waiting, "waiting for you"), role: "waiting" };
  if (working) return { words: some(working, "working"), role: "working" };
  return { words: all ? count(all) : "No agents", role: null };
}

/** @typedef {{ words: string, tip: string, busy: boolean, command?: string, opens?: string }} Update the status
 * bar's item: a press runs COMMAND, or OPENS Settings at that section */
/** The status bar's one update item from U (updates()) and FOUND (core/update.py's check): Herdr's own ready first
 * (herdr-core with it), else herdr-core's unless a package manager owns it, else a newer herdr-fold, which a press
 * only shows how to get; null with none. @param {any} u @param {any} [found] @returns {Update | null} */
export function updateReady(u, found = null) {
  const core = u?.core?.ready && !u.core.managed ? u.core : null, also = core ? ` and herdr-core ${core.ready}` : "";
  if (u?.app?.ready) return { words: `Update ready: Herdr ${u.app.ready}`, command: "app.update", busy: false,
    tip: `Restart into Herdr ${u.app.ready}${also}; your terminals keep running` };
  if (!core) {
    return found?.version && found.newer ? { words: `herdr-fold ${found.latest} is out`, opens: "about", busy: false,
      tip: "Open herdr-fold's Settings at About" } : null;
  }
  return { words: core.updating ? `Updating herdr-core to ${core.ready}…` : `Update ready: herdr-core ${core.ready}`,
    command: "app.update_core", busy: Boolean(core.updating),
    tip: `Update herdr-core to ${core.ready} now; your terminals keep running` };
}

/** The toast after an update, said by the one copy that marked FOUND's update seen (SAID, core/update.py's seen), its
 * What's new opening this version's CHANGELOG section. @param {any} found @param {boolean} said */
export const updateNotice = (found, said) => (found?.updated && said
  ? { title: `Updated to herdr-fold ${found.updated}`, body: "What's new", level: "success",
    action: { name: "herdr-fold.whats-new" } }
  : null);

// the title row's command field as commands.html's B draws it, on the window's centre (where the app opens its
// palette); narrower than its mark, a name and its key need, its mark alone
export const FIELD = 300, FIELD_LEAST = 160;

/** The room the title row keeps at each end: BUTTONS where window W has no system buttons, else on macOS (no title
 * bar, not full screen) as far as ROOT's traffic lights reach at ZOOM (the lights do not zoom), else PAD.
 * @param {any} root @param {any} w @param {number} zoom @param {number} buttons */
export function titleSide(root, w, zoom, buttons) {
  if (w?.buttons) return buttons;
  if (w?.platform !== "macos" || w.titlebar !== "none" || w.fullscreen || !root?.traffic_lights) return PAD;
  return (root.traffic_lights[0] + 64) / zoom;
}

/** The command field's width in a title row WIDE px (null: not measured yet) that keeps SIDE clear at each end: as
 * drawn, else the room between them, else 0 (its mark alone). @param {number | null} wide @param {number} side */
export function fieldWidth(wide, side) {
  const room = wide === null ? FIELD : Math.min(FIELD, wide - 2 * side);
  return room < FIELD_LEAST ? 0 : room;
}

// a key's parts as the platform names them: macOS's signs, elsewhere words (joined by +); the rest as its key cap reads
const KEY_NAMES = { mac: { cmd: "⌘", ctrl: "⌃", shift: "⇧", alt: "⌥", option: "⌥", enter: "↩", backspace: "⌫",
  tab: "⇥", escape: "Esc", left: "←", right: "→", up: "↑", down: "↓", space: "Space", pageup: "PgUp",
  pagedown: "PgDn" },
other: { cmd: "Ctrl", ctrl: "Ctrl", shift: "Shift", alt: "Alt", option: "Alt", enter: "Enter",
  backspace: "Backspace", tab: "Tab", escape: "Esc", left: "←", right: "→", up: "↑", down: "↓", space: "Space",
  pageup: "PgUp", pagedown: "PgDn" } };

/** KEYS as keys.json writes them ("cmd-shift-p", "cmd--", "cmd-k cmd-p"), each chord's parts in the platform's
 * names (MAC: ⌘ ⇧ P; else Ctrl Shift P), as their key caps read. @param {string} keys @param {boolean} mac */
export const keyNames = (keys, mac) => keys.split(" ").map((chord) => (chord.endsWith("--")
  ? [...chord.slice(0, -2).split("-"), "-"] : chord.split("-")).map((part) => /** @type {Record<string, string>} */
  (mac ? KEY_NAMES.mac : KEY_NAMES.other)[part.toLowerCase()] ?? part.toUpperCase()));

/** KEYS as one word, as a field's or a tip's end says it: ⌘⇧P on macOS (MAC), Ctrl+Shift+P elsewhere.
 * @param {string} keys @param {boolean} mac */
export const keyWord = (keys, mac) => keyNames(keys, mac).map((chord) => chord.join(mac ? "" : "+")).join(" ");

/** The palette's key, herdr-fold's own (`herdr-fold.palette`), as LIST (keys()'s) binds it where layout NAME shows
 * (its own section over global), in the platform's words (MAC); unbound, null.
 * @param {{ section: string, keys: string, action: string }[]} list @param {boolean} mac @param {unknown} name */
export function paletteKey(list, mac, name) {
  const bound = (/** @type {string} */ section) => list.find((k) => k.section === section
    && k.action === PALETTE_COMMAND);
  const key = (bound(`layout:${name}`) ?? bound("global"))?.keys;
  return key ? keyWord(key, mac) : null;
}

// the command palette, herdr-fold's own in place of the app's (commands.html's Nyitva): the app's commands named as
// the app's palette names them (its frame's NAMED, the words a search finds besides), in its groups, and a few it only
// titles from their name named here; a key's binding its action. After them herdr-fold's own, in a group of its name
export const PALETTE_COMMAND = "herdr-fold.palette";
export const PALETTE_OWN = "herdr-fold";
export const PALETTE_GROUPS = ["Tab", "Pane", "Space", "Layout", "Terminal", "Agent", "Window", "App", PALETTE_OWN];
const WAYS = ["left", "right", "up", "down"];
/** @typedef {[string, Record<string, unknown>, string, string, string]} Named [command, args, group, title, words] */
/** @param {string} command @param {Record<string, unknown>} args @param {string} group @param {string} title
 * @param {string} words @returns {Named} */
const named = (command, args, group, title, words) => [command, args, group, title, words];
/** @type {Named[]} */
export const PALETTE_NAMED = [
  ["tab.new", {}, "Tab", "New tab", "tab agent new task"],
  ["mod.open", { name: "picker" }, "Tab", "Go to space or tab…", "switch jump find"],
  ["tab.rename", {}, "Tab", "Rename tab", "tab"],
  ["tab.close", {}, "Tab", "Close tab", "tab kill"],
  ["tab.next", {}, "Tab", "Next tab", "tab"],
  ["tab.prev", {}, "Tab", "Previous tab", "tab"],
  ["pane.split", { direction: "right" }, "Pane", "Split right", "vertical"],
  ["pane.split", { direction: "down" }, "Pane", "Split down", "horizontal"],
  ["pane.close", {}, "Pane", "Close pane", "kill"],
  ["pane.zoom", {}, "Pane", "Zoom pane", "maximize fullscreen"],
  ...WAYS.map((way) => named("pane.go", { direction: way }, "Pane", `Focus pane ${way}`, "move go")),
  ...WAYS.map((way) => named("pane.swap", { direction: way }, "Pane", `Swap pane ${way}`, "move")),
  ["space.new", {}, "Space", "New space", "workspace"],
  ["space.rename", {}, "Space", "Rename space", "workspace"],
  ["space.close", {}, "Space", "Close space", "workspace kill"],
  ["space.next", {}, "Space", "Next space", "workspace"],
  ["space.prev", {}, "Space", "Previous space", "workspace"],
  ["layout.switch", {}, "Layout", "Next layout", "look switch"],
  ["layout.reset", {}, "Layout", "Reset layout", "new version default restore herdr's"],
  ["layout.clone", {}, "Layout", "Duplicate layout", "clone copy customize"],
  ["mod.clone", {}, "Layout", "Duplicate mod", "clone copy customize"],
  ["terminal.open", {}, "Terminal", "New terminal", "shell"],
  ["terminal.copy", {}, "Terminal", "Copy", "clipboard"],
  ["terminal.paste", {}, "Terminal", "Paste", "clipboard"],
  ["terminal.paste_image", {}, "Terminal", "Paste image", "clipboard picture screenshot"],
  ["terminal.search", {}, "Terminal", "Find in terminal", "search scrollback"],
  ["terminal.scroll", { to: "top" }, "Terminal", "Scroll to top", "history start"],
  ["terminal.scroll", { to: "bottom" }, "Terminal", "Scroll to bottom", "history end latest"],
  ["agent.next", {}, "Agent", "Next agent", ""],
  ["agent.prev", {}, "Agent", "Previous agent", ""],
  ["window.minimize", {}, "Window", "Minimize window", ""],
  ["window.maximize", {}, "Window", "Maximize window", "restore"],
  ["window.close", {}, "Window", "Close window", "quit"],
  ["app.help", {}, "App", "Keys", "keybindings shortcuts help"],
  ["app.welcome", {}, "App", "Welcome", "intro start onboarding"],
  ["app.whats_new", {}, "App", "What's new", "release changes news update"],
  ["app.check_updates", {}, "App", "Check for updates", "update version"],
  ["app.update_core", {}, "App", "Update herdr-core", "core version"],
  ["app.update", {}, "App", "Restart to update", "update version"],
  ["app.feedback", {}, "App", "Send feedback…", "bug report idea"],
  ["app.reset", {}, "App", "Reset to the default screen", "escape hatch broken restore"],
  ["app.zoom_in", {}, "App", "Zoom in", "bigger font size"],
  ["app.zoom_out", {}, "App", "Zoom out", "smaller font size"],
  ["app.zoom_reset", {}, "App", "Reset zoom", "font size"],
  ["app.quit", {}, "App", "Quit Herdr", "exit"],
  ...["graphite", "ink", "moss", "atom-one-dark"].map((name) => named("app.theme", { name }, "App",
    `Theme: ${name.replace(/-/g, " ")}`, "colors look"))];
// herdr-fold's own commands (main.js's route and dispatch), those that work wherever the keys are: [command, title,
// words]. Not the palette itself, Commit (it needs the message typed in Changes) or the update's toast's What's new
/** @type {[string, string, string][]} */
export const PALETTE_OWNED = [
  ["herdr-fold.settings", "Settings…", "herdr-fold preferences options config agents about update look font theme "
    + "sound machines alerts privacy"],
  ["herdr-fold.files", "Files", "view dock panel explorer tree folder show"],
  ["herdr-fold.search", "Search", "view dock panel find grep show"],
  ["herdr-fold.changes", "Changes", "view dock panel git diff show"],
  ["herdr-fold.issues", "Issues", "view dock panel github pull requests show"],
  ["herdr-fold.agent", "Agent", "view dock panel setup rules permissions skills connectors mcp show"],
  ["herdr-fold.agents", "Agents", "tab graph wiring rules skills subagents tools connectors gates show"],
  ["herdr-fold.usage", "Usage", "tab agents cost tokens spent value budget models conversations report show"],
  ["herdr-fold.runs", "Runs", "tab agents background headless cloud exec runs tasks schedule new run show"],
  ["herdr-fold.chats", "Chats", "view dock panel conversations sessions history show"],
  ["herdr-fold.sidebar", "Collapse or expand sidebar", "left dock rail icons spaces toggle fold show hide"],
  ["herdr-fold.panels", "Collapse or expand panels", "right dock rail icons views toggle fold show hide"],
  ["herdr-fold.column", "Show or hide the dock", "right column panel views terminal toggle"],
  ["herdr-fold.restore", "Restore panels", "views dock terminal hidden back show"],
  ["herdr-fold.new-agent", "New chat", "agent start"],
  ["herdr-fold.new-space", "New space in a folder…", "workspace folder picker open"],
  ["herdr-fold.add-machine", "Add machine…", "remote ssh server"],
  ["herdr-fold.open-file", "Open file from output…", "path line traceback terminal preview"],
  ["herdr-fold.theme", "Color theme…", "colors look picker"],
  ["herdr-fold.styleguide", "Styleguide", "parts components design"],
  ["herdr-fold.unread", "Mark agent unread", "waiting"],
  ["herdr-fold.commit-push", "Commit and push", "git changes"],
  ["herdr-fold.write", "Write commit message", "git changes"]];
/** Cmd+K Cmd+T's list: herdr-fold's THEMES (themes()') by the TUI's NAMES (THEME_NAMES) in its order, the one in use
 * (CURRENT; the layout's own herdr-fold too) checked by its colors. @param {{ name: string, colors: Record<string,
 * string> }[]} themes @param {Record<string, string>} names @param {string} current */
export function themeChoices(themes, names, current) {
  const colors = JSON.stringify(themes.find((theme) => theme.name === current)?.colors ?? null);
  const known = new Map(themes.map((theme) => [theme.name, JSON.stringify(theme.colors)]));
  return Object.entries(names).filter(([name]) => known.has(name))
    .map(([name, label]) => ({ name, label, on: known.get(name) === colors }));
}
// what acts on something pointed at (an id, a terminal), or is the palette itself: not for a list
const PALETTE_HIDDEN = new Set(["space.move", "tab.move", "space.select", "tab.select", "pane.focus", "terminal.keep",
  "terminal.park", "terminal.kill", "terminal.show", "agent.focus", "layout.set", "layout.toggle", "layout.show",
  "layout.hide", "layout.resize", "layout.select", "mod.open", "overlay.close", "tab.settle", "tab.unsettle",
  "app.palette", "app.hide", "app.hide_others", "app.show_all", "app.theme", "app.settings"]);
const LAYOUT_TITLES = /** @type {Record<string, string>} */ ({ main: "Herdr", terminals: "Terminals",
  win98: "Herdr 98", "herdr-fold": "herdr-fold" });

/** A palette's entry: the COMMAND it runs with its ARGS, its GROUP, its TITLE, the WORDS a search finds it by besides,
 * its ID. @typedef {{ name: string, args: Record<string, unknown>, group: string, title: string, words: string,
 * id: string }} PaletteEntry */

/** An app's command, as commands() lists it. @typedef {{ name: string, args: { name: string, required: boolean }[],
 * about: string }} AppCommand */
/** A key bound, as keys() lists it. @typedef {{ section: string, keys: string, action: string }} Binding */

/** How herdr-fold's own commands list: Issues on GITHUB only, the new agent named as + names it (PLUS).
 * @typedef {{ github: boolean, plus: string }} Own */

/** The palette's entries for the app's COMMANDS and LAYOUTS in the groups' order: those named (the window's off macOS,
 * MAC), a layout each, any other needing no argument but a name, titled from it; with OWN, herdr-fold's own after the
 * app's. @param {AppCommand[]} commands @param {string[]} layouts @param {boolean} mac @param {Own | null} [own] */
export function paletteEntries(commands, layouts, mac, own = null) {
  const known = new Set(commands.map((c) => c.name)), titled = new Set(PALETTE_NAMED.map(([name]) => name));
  const list = PALETTE_NAMED.filter(([name]) => known.has(name) && !(mac && name.startsWith("window.")))
    .map(([name, args, group, title, words]) => ({ name, args, group, title, words }));
  if (known.has("layout.switch")) {
    for (const name of layouts) {
      list.push({ name: "layout.switch", args: { name }, group: "Layout", words: `look ${name}`,
        title: `Layout: ${LAYOUT_TITLES[name] ?? name.charAt(0).toUpperCase() + name.slice(1)}` });
    }
  }
  for (const c of commands) {
    if (titled.has(c.name) || PALETTE_HIDDEN.has(c.name) || c.args.some((a) => a.required && a.name !== "name")) {
      continue;
    }
    const [noun, verb = ""] = c.name.split(".");
    list.push({ name: c.name, args: {}, group: noun.charAt(0).toUpperCase() + noun.slice(1), words: c.about,
      title: `${verb.replace(/_/g, " ")} ${noun}`.replace(/^./, (first) => first.toUpperCase()) });
  }
  for (const [name, title, words] of own ? PALETTE_OWNED : []) {
    if (name === "herdr-fold.issues" && !own?.github) continue;
    list.push({ name, args: {}, group: PALETTE_OWN, words,
      title: name === "herdr-fold.new-agent" ? own?.plus ?? title : title });
  }
  const order = (/** @type {string} */ group) => (PALETTE_GROUPS.includes(group) ? PALETTE_GROUPS.indexOf(group)
    : PALETTE_GROUPS.length);
  return list.map((entry, n) => ({ entry, n })).sort((a, b) => order(a.entry.group) - order(b.entry.group) || a.n - b.n)
    .map(({ entry }) => ({ ...entry, id: `${entry.name}:${JSON.stringify(entry.args)}` }));
}

/** ENTRY's key where layout NAME shows, as LIST binds its action (`name`, `name:value` its first argument's): the
 * layout's own, else a global one the layout leaves, else a terminal's; null. @param {Binding[]} list
 * @param {{ name: string, args: Record<string, unknown> }} entry @param {unknown} name */
export function entryKey(entry, list, name) {
  const value = Object.values(entry.args)[0];
  const action = value === undefined ? entry.name : `${entry.name}:${value}`;
  const own = list.filter((k) => k.section === `layout:${name}`);
  const global = list.find((k) => k.section === "global" && k.action === action && !own.some((o) => o.keys === k.keys));
  return (own.find((k) => k.action === action) ?? global
    ?? list.find((k) => k.section === "terminal" && k.action === action))?.keys ?? null;
}

/** Where the palette opens in a window ROOM: WIDE (or the window less 8 at each side) on its centre, 8 under its top
 * (the nearest the app lets a popup come: measured), its field over the title row's; HIGH, or as the window leaves.
 * @param {{ width: number, height: number }} room @param {number} wide @param {number} high */
export function palettePlace(room, wide, high) {
  const width = Math.min(wide, room.width - 2 * MENU_EDGE);
  return { x: Math.round((room.width - width) / 2), y: MENU_EDGE, width,
    height: Math.min(high, room.height - 2 * MENU_EDGE) };
}

/** The room the tab bar leaves at its end so its panel toggle, BUTTON px wide, sits over the middle of the rail,
 * inside the work body's padding (layout ROOT's). @param {any} root @param {number} button */
export const toggleRoom = (root, button) => (find(root, "work-body")?.padding ?? 0) + (RAIL - button) / 2;

// the layout's right panel and its card, the stack of the views under the row (the stack's header): herdr-fold's own
// ids, so the app's Settings, which shows and hides a panel under the app's ids, leaves them alone
export const PANEL = "fold-panel", DOCK = "fold-views";
export const RAIL_BLOCK = "panel-rail";      // the right panel's block while it is folded to its rail
export const RAIL = 76;                      // px: the right panel folded to its rail, as the left sidebar folds
export const PANEL_PX = 368;                 // px: the right panel open, unless it kept another width

export const TALL = 440;          // Spaces floating beside the folded sidebar, at most

const FLOAT_ROW = 30, FLOAT_FOOT = 6;        // px: Spaces' float's row and the gap after it; its foot less that gap

/** Spaces floating beside the folded sidebar, as tall as its head and its SHOWN rows (a count), up to TALL and the
 * ROOM the window has under its top, a row at least (it scrolls then). @param {number} shown @param {number} [room] */
export const floatHeight = (shown, room = Infinity) => {
  const rows = (/** @type {number} */ n) => FLOAT_HEAD + FLOAT_ROW * n + FLOAT_FOOT;
  return Math.min(TALL, rows(shown), Math.max(rows(1), room));
};

/** The ✦'s count, as the TUI's: the chats waiting on you, this Mac's (LOCAL spaces') Claude and Codex blocked and
 * the chat tabs waiting (CHATS: their agents), each agent once (a chat's terminal shown in a pane is among AGENTS).
 * @param {any[]} agents @param {Set<string>} local @param {Set<string>} [chats] */
export const waitingChats = (agents, local, chats = new Set()) => new Set([...coreAgents(agents, [], local)
  .filter((a) => a.agent_status === "blocked").map((a) => a.pane_id), ...chats]).size;

const UNITS = /** @type {[number, string][]} */ ([[1e6, "m"], [1e3, "k"]]);     // the largest first, as the TUI's

/** Issues (NOUN's: pull requests too) loading, moving nothing: in the list's first row's place the first load, a
 * failure or none found (faint as the TUI's), else rows; the head's refresh a spinner while a list is ASKED again.
 * @param {any} s @returns {{ refresh: string, say: [string, string] | null }} */
export function issuesParts({ asked, listing, shown, filtered, state, noun = "issues" }) {
  const say = !listing ? (asked ? [`Loading ${noun}…`, "dim"] : null) : listing.error ? [listing.error, "ansi1"]
    : shown ? null : [filtered ? `No ${noun} match` : `No ${state} ${noun}`, "dim"];
  return { refresh: asked && listing ? "spinner" : "button", say: /** @type {[string, string] | null} */ (say) };
}

// a view floating beside the folded rail (a window as tall as its content): as tall as dragged by the grip at its
// foot, its head and 3 rows at least (each view's head and rows below), the rail's height at most; FLOAT_GAP from it
export const FLOAT_GRIP = 12, FLOAT_HEAD = 36, FLOAT_FALLBACK = 560, FLOAT_GAP = 8;
const FLOAT_PARTS = {           // px: each view's own head, then 3 of its rows
  files: [38, 3 * 26],                          // the toolbar (PAD + an icon button)
  chats: [50, 26 + 2 * 24],                     // the filter (PAD, a field, 6), a space and two chats
  search: [81, 3 * 24],                         // the field and its status line, PAD round them, the rule
  issues: [38 + 84, 3 * 48],                    // the switch (PAD, a choice), the field's row and Open and Closed
  changes: [58 + 97, 3 * 26 + 12],              // the repository and the composer; the list's rows and its pads
  agent: [44 + 37, 4 + 28 + 2 * 26],            // the head and the health line; a section's head and two rows
  spaces: [0, FLOAT_ROW + FLOAT_FOOT],          // a space's row and the list's foot
};

/** The least a float of VIEW may be: its head, the view's own head, 3 rows, the grip. @param {string} view */
export function floatMin(view) {
  const [head, rows] = FLOAT_PARTS[/** @type {keyof typeof FLOAT_PARTS} */ (view)] ?? FLOAT_PARTS.files;
  return FLOAT_HEAD + head + rows + FLOAT_GRIP;
}

/** The most: the rail's height (RAIL_PX), from the centre card's top (floatTop) to its foot, so the float stays in the
 * window and off the tab bar. @param {number} railPx @param {any} _root */
export const floatMax = (railPx, _root) => railPx;

/** Where a float beside a rail starts in layout ROOT: at the centre card's top, under the title row and the tab bar,
 * so their buttons (✦, More, ») stay in reach. @param {any} root */
export const floatTop = (root) => (find(root, "title")?.size?.px ?? 0) + (find(root, "top")?.size?.px ?? 0)
  + (find(root, "work-body")?.padding ?? 0);

/** Where a float of PANEL, WIDE px wide, starts across a window WIDTH px wide (layout ROOT): Spaces FLOAT_GAP right of
 * the sidebar's rail and divider, a view FLOAT_GAP left of the dock's rail, whichever icon was pressed: on the centre
 * card's edges. @param {string} panel @param {any} root @param {number} width @param {number} wide */
export function floatX(panel, root, width, wide) {
  if (panel === "spaces") return (sidebarPx(root) ?? RAIL) + (find(root, "workspace")?.divider?.width ?? 0) + FLOAT_GAP;
  const rail = (find(root, "work-body")?.padding ?? 0) + (panelPx(root) ?? RAIL);      // the rail, from the edge
  return Math.max(FLOAT_GAP, width - rail - FLOAT_GAP - wide);
}

/** A height clamped to MIN..MAX (MAX never under MIN). @param {number} px @param {number} min @param {number} max */
const clampPx = (px, min, max) => Math.min(Math.max(px, min), Math.max(min, max));

/** VIEW's float's height: as KEPT for it ({view: px}), else the most, inside its bounds (RAIL_PX unknown yet:
 * FLOAT_FALLBACK at most). @param {string} view @param {any} kept @param {number | null} railPx @param {any} root */
export function railFloatPx(view, kept, railPx, root) {
  const max = railPx ? floatMax(railPx, root) : FLOAT_FALLBACK, want = kept?.[view];
  return clampPx(typeof want === "number" ? want : max, floatMin(view), max);
}

/** VIEW's float's height where it fits FIT px (its rows, Spaces'): as KEPT for it ({view: px}), else FIT, its least
 * to MOST (the window's room under it). @param {string} view @param {any} kept @param {number} fit
 * @param {number} most */
export function fitFloatPx(view, kept, fit, most) {
  const want = kept?.[view];
  return clampPx(typeof want === "number" ? want : fit, floatMin(view), most);
}

/** KEPT with VIEW's float PX high, only heights kept. @param {any} kept @param {string} view @param {number} px */
export function keepFloat(kept, view, px) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([, v]) => typeof v === "number")), [view]: px };
}

/** The height a drag that started at DRAG ({y, px}) gives with the pointer at Y, inside MIN..MAX.
 * @param {{ y: number, px: number }} drag @param {number} y @param {number} min @param {number} max */
export const dragPx = (drag, y, min, max) => clampPx(drag.px + y - drag.y, min, max);

export const NOTE_MS = 4000;      // ms a done thing's line stays under a list, as the TUI's last row; an error stays
export const BADGE = 14;          // px: a count's badge, as VS Code's activity bar's: this high, at least as wide

/** Where a count's badge goes on an icon whose top-right corner is at X, Y: a one-digit badge's centre on that corner,
 * over it a little; a longer count grows to the right. @param {number} x @param {number} y */
export const badgeSpot = (x, y) => ({ left: x - BADGE / 2, top: y - BADGE / 2 });

/** COUNT short when large, 4 characters at most, as the TUI's: as it is to 999; under ten of a unit one decimal,
 * floored, none for .0 (1.2k, 1k); from ten whole (18k, 111k); 999m at most. @param {number} count */
export function shortCount(count) {
  const n = Math.min(count, 999999999), found = UNITS.find(([unit]) => n >= unit);
  if (!found) return String(n);
  const [unit, name] = found, tenths = Math.floor((n * 10) / unit), whole = Math.floor(tenths / 10);
  return `${whole}${whole < 10 && tenths % 10 ? `.${tenths % 10}` : ""}${name}`;
}

// herdr-fold's Spaces list, where the app's own was: the same rows, and how long an agent there waits on you, as the
// TUI's Space rows say it

/** A wait as a Space row says it, as the TUI's: under a minute, then minutes, hours or days. @param {number} ms */
export function waited(ms) {
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return "waiting <1m";
  const units = /** @type {[string, number][]} */ ([["d", 1440], ["h", 60], ["m", 1]]);
  const [unit, size] = /** @type {[string, number]} */ (units.find(([, n]) => minutes >= n));
  return `waiting ${Math.floor(minutes / size)}${unit}`;
}

const WAITING = ["blocked", "done"];         // waiting on you: a question, or an answer not seen yet

/** @typedef {{ address: string, pane: string, space: string, status: string, seq: number }} Waiter */

/** The waits after a look at AGENTS at NOW, FOCUSED the pane in focus, KNOWN the ones before: each agent blocked
 * or done since its last change, or marked unread till its pane is left and come back to, as the TUI keeps them.
 * @param {Record<string, any>} known @param {Waiter[]} agents @param {number} now @param {string | null} focused */
export function nextWaits(known, agents, now, focused) {
  /** @type {Record<string, any>} */
  const waits = {};
  for (const { address, pane, status, seq } of agents) {
    let was = known[address];
    if (was?.unread) {
      if (focused !== pane) waits[address] = { ...was, left: true };
      else if (!was.left) waits[address] = was;
      if (waits[address]) continue;
      was = null;                                 // read: back on it after leaving it
    }
    if (WAITING.includes(status)) waits[address] = { seq, since: was?.seq === seq ? was.since : now };
  }
  return waits;
}

/** WAITS with AGENT marked unread (Cmd + Shift + U) from NOW, or from when it began to wait; marked already, unmarked.
 * @param {Record<string, any>} waits @param {Waiter} agent @param {number} now */
export function toggleUnread(waits, agent, now) {
  const was = waits[agent.address], next = { ...waits };
  if (was?.unread) delete next[agent.address];
  else next[agent.address] = { seq: agent.seq, since: was?.since ?? now, unread: true, left: false };
  return next;
}

/** Each space's longest wait: since when the first of its AGENTS in WAITS waits, or a chat there (CHATS: each space's,
 * logic.js's waiting). @param {Record<string, any>} waits @param {{ address: string, space: string }[]} agents
 * @param {Record<string, number>} [chats] */
export function spaceWaits(waits, agents, chats = {}) {
  /** @type {Record<string, number>} */
  const first = { ...chats };
  for (const { address, space } of agents) {
    if (waits[address]) first[space] = Math.min(first[space] ?? Infinity, waits[address].since);
  }
  return first;
}

/** What a Space row says after its NAME: its PLACE's branch, main too, as the TUI's, and its repository where that
 * is not the name; neither when it is the name again; a worktree's (TREE, under its checkout) never its repository.
 * @param {{ name: string, branch: string | null }} place @param {boolean} tree @param {string} name */
export function placeLabel(place, tree, name) {
  const same = (text) => text.toLowerCase() === name.toLowerCase(), raw = place.branch ?? "detached";
  return [tree || same(place.name) ? "" : place.name, same(raw) ? "" : raw].filter(Boolean).join(" · ");
}

/** ROWS ({ w: a space, g: its place }) in order, each worktree under the first space of its checkout, TREE marking it;
 * one whose checkout has no space stays where it is, and so does one showing the repository inside its folder (its
 * folder neither that checkout nor its worktree). @template {{ g: any }} R @param {R[]} rows */
export function nested(rows) {
  const own = (/** @type {R} */ r) => (r.g?.inside ? null : r.g);
  const checkouts = new Set(rows.filter((r) => own(r) && !r.g.linked).map((r) => r.g.repo));
  const under = (/** @type {R} */ r) => Boolean(own(r)?.linked && checkouts.has(r.g.repo));
  const out = [], placed = new Set();
  for (const row of rows) {
    if (under(row)) continue;
    out.push({ ...row, tree: false });
    if (!own(row) || row.g.linked || placed.has(row.g.repo)) continue;
    placed.add(row.g.repo);
    out.push(...rows.filter((r) => under(r) && r.g.repo === row.g.repo).map((r) => ({ ...r, tree: true })));
  }
  return out;
}

/** Where space S is (PS: the app's panes()): its first terminal's live folder, else where it was made, on its machine.
 * @param {any} s @param {any[]} ps */
export function folderKey(s, ps) {
  const tabs = new Set((s.tabs ?? []).map((/** @type {any} */ tab) => tab.id));
  return JSON.stringify([s.machine ?? null, ps.find((p) => tabs.has(p.tab) && p.cwd)?.cwd || s.folder]);
}

/** Space S's place's key: its folderKey, and where PLACES says that folder is no repository, its active pane's folder
 * (its shown tab's focused pane) too, core/git.py's place showing the repository inside that pane is in (no pane's
 * past is kept: never the one last in). @param {any} s @param {any[]} ps @param {Record<string, any>} places */
export function placeKey(s, ps, places) {
  const key = folderKey(s, ps), known = places[key], [on, folder] = JSON.parse(key);
  const tab = (s.tabs ?? []).find((/** @type {any} */ t) => t.active)?.id;
  const active = ps.find((p) => p.tab === tab && p.focused && p.cwd)?.cwd;
  return known === undefined || (known && !known.inside) || !active || active === folder ? key
    : JSON.stringify([on, folder, active]);
}

// A machine's home folder is always a row in Spaces, first among its machine's: a space there, or with none (the app
// ends a space with its last tab) a stand-in saying nothing is open, a click opening a terminal there.
export const HOME_NAME = "~";
// the app names a root's space by its path, as herdr does: / or a drive's (C:\), its letter and colon kept
const ROOT_PATH = /^([A-Za-z]:)?[\\/]$/;
/** A space's NAME as shown, as the TUI names its workspace: the app's "~" reads home, a root's root, a drive's its
 * letter (C:); its avatar keeps the path's first character. @param {string | null | undefined} name */
export function spaceLabel(name) {
  const root = name?.match(ROOT_PATH);
  return name === HOME_NAME ? "home" : root ? root[1] ?? "root" : name ?? "";
}
/** Whether NAME is the app's for a machine's own place, its home or a root, not a project. @param {string} name */
const ownPlace = (name) => name === HOME_NAME || ROOT_PATH.test(name);
/** Space S's avatar color, COLORS the kept ones: home's for a machine's own place, else its own.
 * @param {{ id: string, name: string }} s @param {Record<string, string>} colors */
export const spaceColor = (s, colors) => (ownPlace(s.name) ? "ansi6" : colors[s.id] ?? "ansi6");
/** The stand-in's id for MACHINE's home (null: this computer). @param {string | null} machine */
export const homeId = (machine) => `home:${machine ?? ""}`;
const folderOnly = (/** @type {string} */ path) => path.replace(/[\\/]+$/, "");

/** Whether space S is at its machine's home (PS: the app's panes()): one the app itself calls "~" (nobody named it, its
 * first terminal there), or one whose folderKey is HOMES' for its machine ("": this computer).
 * @param {any} s @param {any[]} ps @param {Record<string, string>} homes */
export function atHome(s, ps, homes) {
  if (!s.named && s.name === HOME_NAME) return true;
  const [on, folder] = JSON.parse(folderKey(s, ps)), home = homes[on ?? ""];
  return Boolean(home && folder) && folderOnly(folder) === folderOnly(home);
}

/** KNOWN with the home folder of each machine a space of LIST shows it for: the folder of one the app calls "~" (a
 * named space there is known by it afterwards). @param {Record<string, string>} known @param {any[]} list
 * @param {any[]} ps */
export function homesSeen(known, list, ps) {
  const homes = { ...known };
  for (const s of list) {
    const folder = !s.named && s.name === HOME_NAME && JSON.parse(folderKey(s, ps))[1];
    if (folder) homes[s.machine ?? ""] ??= folder;
  }
  return homes;
}

/** ROWS with each machine's rows at HOME first among that machine's, a checkout's worktrees (nested()'s TREE) staying
 * under it; MACHINE: a row's. @template R @param {R[]} rows @param {(row: R) => boolean} home
 * @param {(row: R) => string | null} [machine] */
export function homeFirst(rows, home, machine = (/** @type {any} */ r) => r.w.machine ?? null) {
  let lifted = false;
  const marked = rows.map((row) => {
    if (!(/** @type {any} */ (row)).tree) lifted = home(row);
    return { row, lifted };
  });
  return [...new Set(rows.map(machine))].flatMap((m) => {
    const mine = marked.filter((r) => machine(r.row) === m);
    return [...mine.filter((r) => r.lifted), ...mine.filter((r) => !r.lifted)].map((r) => r.row);
  });
}

/** The machines of OPEN (where a terminal can start now; null: this computer) with no space of LIST at HOME: their
 * home's row is a stand-in. @param {(string | null)[]} open @param {any[]} list @param {(s: any) => boolean} home */
export const homesEmpty = (open, list, home) => open.filter((m) => !list.some((s) => (s.machine ?? null) === m &&
  home(s)));

/** LIST (spaces, in the app's order) as a flat list shows it: by machine, this computer first, then by name, each
 * home first and each of EMPTY's a stand-in ({ empty: true }) at its machine's head. @param {any[]} list
 * @param {(string | null)[]} empty @param {(s: any) => boolean} home */
export function withHomes(list, empty, home) {
  const of = (/** @type {any} */ s) => s.machine ?? null;
  const names = [...new Set([...list.map(of), ...empty])].sort((a, b) => (a === null ? -1 : b === null ? 1
    : a < b ? -1 : 1));
  const rows = homeFirst(list, home, of);
  return names.flatMap((m) => [...(empty.includes(m) ? [{ id: homeId(m), name: HOME_NAME, machine: m, active: false,
    status: null, empty: true }] : []), ...rows.filter((s) => of(s) === m)]);
}

/** The line a review comment on ROW (core/github.py's files_of) goes on: its number in the new file and the RIGHT
 * side, a removed line's in the old one and LEFT; null on a hunk's head. @param {{ kind: string, old: number | null,
 * new: number | null }} row @returns {{ line: number, side: "LEFT" | "RIGHT" } | null} */
export function commentAt(row) {
  if (row.kind === "@") return null;
  return row.kind === "-" ? { line: Number(row.old), side: "LEFT" } : { line: Number(row.new), side: "RIGHT" };
}

/** Whether a review of EVENT (comment, approve, request) can go: Approve but on one's own pull request (MINE: GitHub
 * refuses it), Comment and Request changes with a SUMMARY (GitHub's REST API asks for their body).
 * @param {string} event @param {string} summary @param {boolean} mine */
export const reviewReady = (event, summary, mine) => (event === "approve" ? !mine : Boolean(summary.trim()));

/** Whether a primary button is lit: it can be pressed (READY), or its work runs (BUSY, its label says so); else unlit,
 * as Commit with nothing to commit. @param {boolean} ready @param {unknown} busy */
export const primaryLit = (ready, busy) => Boolean(ready || busy);

/** A login's avatar color: one of MARK's, the same for it every time. @param {string} login */
export function loginColor(login) {
  const sum = [...login].reduce((n, ch) => (n * 31 + ch.charCodeAt(0)) % 997, 7);
  return MARK[/** @type {keyof typeof MARK} */ (PALETTE[sum % PALETTE.length])];
}

// a space's avatar color, as every app mod draws one: one strong color per hue, light and dark alike
export const MARK = { ansi6: "#22a99a", ansi3: "#e3814f", ansi4: "#5b8def", ansi5: "#8b7cf6", ansi2: "#3fae6a",
  ansi1: "#d9649a" };
const PALETTE = ["ansi6", "ansi3", "ansi4", "ansi5", "ansi2", "ansi1"];

/** The spaces' colors as every app mod keeps them (shared "space.colors"): KEPT's for the spaces of LIST still there,
 * one without given the color fewest use, in LIST's order, home's and a root's none; null when nothing changed.
 * @param {{ id: string, name: string }[]} list @param {Record<string, string>} kept */
export function spaceColors(list, kept) {
  const ids = new Set(list.map((s) => s.id));
  const colors = Object.fromEntries(Object.entries(kept).filter(([id]) => ids.has(id)));
  let changed = Object.keys(colors).length !== Object.keys(kept).length;
  for (const { id, name } of list) {
    if (colors[id] || ownPlace(name)) continue;
    const uses = (c) => Object.values(colors).filter((v) => v === c).length;
    colors[id] = PALETTE.reduce((best, c) => (uses(c) < uses(best) ? c : best));
    changed = true;
  }
  return changed ? colors : null;
}

/** An avatar's fill for COLOR (kept): the strong one for a theme color's name, a picked #rrggbb as it is.
 * @param {string} color @param {Record<string, any>} t */
export const avatarFill = (color, t) => (color.startsWith("#") ? color : MARK[color] ?? t[color] ?? MARK.ansi6);

export const LIST = { head: 32, foot: 16, machine: 28, row: 32, tree: 28 };     // the Spaces list's, on the grid

/** @typedef {{ machine: string | null, folded: boolean, rebuilt: boolean, loading: boolean,
 *   rows: { tree: boolean }[] }} SpaceGroup */

/** What a Spaces list's group G shows under its head (HEADED: once another machine is there): its rows, Loading…,
 * New space there, or nothing (folded, or rebuilt: only its head). @param {SpaceGroup} g @param {boolean} headed */
export const listBody = (g, headed) => (headed && (g.folded || g.rebuilt) ? "none" : g.rows.length ? "rows"
  : g.loading ? "loading" : headed ? "empty" : "none");

/** Whether GROUPS get a machine's head each: once a machine other than this computer is there.
 * @param {SpaceGroup[]} groups */
export const headed = (groups) => groups.length > 1 || Boolean(groups[0]?.machine);

/** The Spaces list's height as GROUPS draw it, each machine's head and rows. @param {SpaceGroup[]} groups */
export function listHeight(groups) {
  const heads = headed(groups), one = { none: 0, loading: LIST.tree, empty: LIST.tree };
  return LIST.head + LIST.foot + groups.reduce((h, g) => h + (heads ? LIST.machine : 0) + (listBody(g, heads) ===
    "rows" ? g.rows.reduce((n, r) => n + (r.tree ? LIST.tree : LIST.row), 0) : one[listBody(g, heads)]), 0);
}

/** Whether layout ROOT shows the right panel. @param {any} root */
export function panelShown(root) {
  const panel = find(root, PANEL);
  return Boolean(panel && !panel.hidden);
}

// the right dock's views, as the TUI's row has them: one stack (DOCK) of their blocks under the row of buttons, one
// shown at a time; a view hidden from More's menu is its block hidden
export const VIEWS_APP = ["files", "search", "changes", "issues", "agent"];
export const CHATS_BLOCK = "fold-chats";           // the Chats list's block in that stack, shown in a view's place
export const PANEL_NAMES = { files: "Files", search: "Search", changes: "Changes", issues: "Issues", agent: "Agent" };
// px inside a card, on every side: a terminal's text, a view's words and fields; a row's hover pad reaches halfway in
// (PAD / 2). Here, as the dock's sizes need it; parts.js hands it to the views.
export const PAD = 12;

/** Whether PANEL can show here: Issues for a repository on GitHub (GITHUB) only. */
const available = (/** @type {string} */ panel, /** @type {boolean} */ github) => panel !== "issues" || github;

/** Every view layout ROOT shows: its block there and not hidden, Issues only on GitHub (GITHUB).
 * @param {any} root @param {boolean} github @returns {string[]} */
export const shownPanels = (root, github) => VIEWS_APP
  .filter((panel) => available(panel, github) && find(root, panel) && !find(root, panel).hidden);

/** The view layout ROOT shows, as the TUI's: CHOSEN (the space's own) while it is on the row, else Files, else the
 * row's first. @param {any} root @param {boolean} github @param {string | null} [chosen] @returns {string | null} */
export function shownView(root, github, chosen = null) {
  const shown = shownPanels(root, github);
  return shown.includes(chosen ?? "") ? chosen : shown.includes(START) ? START : shown[0] ?? null;
}

export const START = "files";                 // the view a space first shows, as the TUI's

/** The view SPACE (its id) chose, as KEPT ({space: view}) holds it; else Files, as a new space starts (an older
 * version's one view for all is no space's). @param {any} kept @param {string | null} space */
export const chosenFor = (kept, space) => (kept && typeof kept === "object" && space !== null &&
  typeof kept[space] === "string" ? kept[space] : START);

/** KEPT with SPACE's view VIEW, the spaces no longer LIVE (their ids) left out, as the TUI's dock.json drops a folder
 * gone. @param {any} kept @param {string} space @param {string} view @param {Set<string>} live
 * @returns {Record<string, string>} */
export function keepChosen(kept, space, view, live) {
  const was = kept && typeof kept === "object" && !Array.isArray(kept) ? kept : {};
  return { ...Object.fromEntries(Object.entries(was).filter(([id, v]) => live.has(id) && typeof v === "string")),
    [space]: view };
}

/** Chats' button, Cmd+Shift+R, Esc in its list (layout ROOT): shown, the view back (shownView's of CHOSEN); else the
 * list in the view's place, the dock opened from its rail (KEPT px). @param {any} root @param {boolean} github
 * @param {string | null} chosen @param {number} [kept] @returns {[string, any][]} */
export function chatsToggle(root, github, chosen, kept = undefined) {
  if (find(root, DOCK)?.active === CHATS_BLOCK) {
    const view = shownView(root, github, chosen);
    return view ? [["layout.select", { stack: DOCK, child: view }]] : [];
  }
  return [["layout.select", { stack: DOCK, child: CHATS_BLOCK }], ...(panelRailed(root) ? railToggle(root, kept) : [])];
}

// the dock's text tabs atop its card (its stack's header), center-chat.html's .ptabs: TABS_PAD over and under them,
// TABS_SIDE at the sides, a hairline under; a tab TAB_H high (the window's tabs'), its words TAB_IN in each side (the
// first tab's PAD in, as the views' words under it), TAB_GAP from the next (one control)
export const TAB_H = 28, TABS_PAD = 8, TABS_SIDE = 6, TAB_IN = 6, TAB_GAP = 2;
export const TAB_COUNT = 18;      // px: Changes' count after its name, this high and at least as wide
export const TABS_H = TABS_PAD + TAB_H + TABS_PAD + 1, TABS_IN = 1 + TABS_SIDE;    // in the card's border

/** The tabs a card PX wide holds, in order: WIDTHS' [id, px] (as drawn; 0 not yet), the last left out first, never
 * CHOSEN (the shown one). @param {number} px @param {[string, number][]} widths @param {string | null} chosen
 * @returns {{ tabs: string[] }} */
export function tabFit(px, widths, chosen) {
  const need = (/** @type {[string, number][]} */ tabs) => tabs.reduce((sum, [, w]) => sum + w, 0)
    + TAB_GAP * (tabs.length - 1);
  let fit = [...widths];
  for (;;) {
    const last = [...fit].reverse().find(([id]) => id !== chosen);
    if (fit.length < 2 || need(fit) <= px - 2 * TABS_IN || !last) return { tabs: fit.map(([id]) => id) };
    fit = fit.filter((tab) => tab !== last);
  }
}

/** @typedef {{ root: string | null, github: boolean, changed: number }} Told */

/** The repository at HERE ({cwd, on}) as the row and the rail show it: its root, on GitHub or not, its changed files;
 * ASK's top, status, github look there (git, core/git.py), KNOWN keeps each one's GitHub answer.
 * @param {any} here @param {any} ask @param {Map<string, boolean>} known @returns {Promise<Told>} */
export async function repoTold(here, ask, known) {
  const root = here.cwd ? await ask.top(here.cwd, here.on) : null;
  if (!root) return { root: null, github: false, changed: 0 };
  const status = await ask.status(root, here.on), key = `${here.on ?? ""}:${root}`;
  if (!known.has(key)) known.set(key, Boolean(await ask.github(root, here.on)));
  return { root, github: Boolean(known.get(key)),
    changed: (status?.staged?.length ?? 0) + (status?.changes?.length ?? 0) };
}

/** The commands that put layout ROOT's stack on shownView() (Issues off GitHub: another meanwhile).
 * @param {any} root @param {boolean} github @param {string | null} [chosen] @returns {[string, any][]} */
export function panelsFollow(root, github, chosen = null) {
  const want = shownView(root, github, chosen), active = find(root, DOCK)?.active;
  if (active === CHATS_BLOCK) return [];                     // the Chats list over the view, till it closes
  return want && want !== active ? [["layout.select", { stack: DOCK, child: want }]] : [];
}

/** A view's button or key in layout ROOT: PANEL shown (hidden in More's menu: shown again; the Chats list: in its
 * place), the dock too (KEPT px wide); none where it can't (GITHUB). @param {any} root @param {string} panel
 * @param {{ github?: boolean, kept?: number }} [how] @returns {[string, any][]} */
export function pickCommands(root, panel, { github = false, kept = undefined } = {}) {
  if (!VIEWS_APP.includes(panel) || !available(panel, github) || !find(root, panel) || !find(root, PANEL)) return [];
  const after = JSON.parse(JSON.stringify(root));
  if (find(after, DOCK)?.active === CHATS_BLOCK) find(after, DOCK).active = null;
  /** @type {[string, any][]} */
  const commands = [];
  if (find(after, panel).hidden) {
    commands.push(["layout.show", { id: panel }]);
    find(after, panel).hidden = false;
  }
  commands.push(...panelsFollow(after, github, panel));
  return find(after, PANEL).hidden || panelRailed(after) ? [...commands, ...railOpen(after, kept)] : commands;
}

/** More's views, as the TUI's: each with its ✓ while shown (ON), Issues on GitHub only; the last one shown can't be
 * unchecked (OFF). @param {any} root @param {boolean} github */
export function panelChoices(root, github) {
  const shown = shownPanels(root, github);
  return VIEWS_APP.filter((panel) => available(panel, github) && find(root, panel))
    .map((panel) => ({ panel, label: PANEL_NAMES[panel], on: shown.includes(panel),
      off: shown.length === 1 && shown[0] === panel }));
}

/** The commands that hide PANEL from layout ROOT's dock (HIDE) or show it again; hidden, the stack on CHOSEN or
 * another; never the last. @param {any} root @param {string} panel @param {boolean} hide @param {boolean} github
 * @param {string | null} [chosen] @returns {[string, any][]} */
export function hideCommands(root, panel, hide, github, chosen = null) {
  if (!find(root, panel) || (hide && !shownPanels(root, github).some((other) => other !== panel))) return [];
  const after = JSON.parse(JSON.stringify(root));
  find(after, panel).hidden = hide;
  return [[hide ? "layout.hide" : "layout.show", { id: panel }], ...panelsFollow(after, github, chosen)];
}

/** The popup mod.open made, if this copy (PROPS) is it: the mod's own popups name their part.
 * @param {any} props @returns {string | null} */
export const launcher = (props) => (props?.overlay && !props.part ? props.overlay : null);

/** Layout ROOT's right panel's width in px, or null. @param {any} root @returns {number | null} */
export const panelPx = (root) => find(root, PANEL)?.size?.px ?? null;

/** Whether layout ROOT's right panel is its rail: narrower than a sidebar's rail starts. @param {any} root */
export const panelRailed = (root) => (panelPx(root) ?? Infinity) < RAIL_BELOW;

/** @typedef {{ shown: boolean, px: number }} Bottom the terminal under the centre: shown or not, its height */

/** The commands that make ROOT's right panel show what its width says, a drag's too (its width once let go: dockRest):
 * its rail's block and the tab's terminal under the centre as BOTTOM says (none in the tab, or no centre: hidden), or
 * its card and the terminal's at its foot; nothing while hidden. @param {any} root @param {Bottom} [bottom] */
export function railFollow(root, { shown, px } = { shown: true, px: BOTTOM_PX }) {
  const panel = find(root, PANEL);
  if (!panel || panel.hidden) return [];
  const bottom = { shown: shown && activeTerminal(root) !== null, px };       // no stand-in taking the centre's room
  const railed = panelRailed(root), moved = placeTerminals(root, railed ? "bottom" : "dock", bottom);
  /** @type {[string, any][]} */
  const set = moved.changed ? [["layout.set", { layout: moved.tree }],
    ["layout.resize", { id: TERMINALS, ...(railed ? { px: bottom.px } : { weight: TERMINALS_WEIGHT }) }]] : [];
  /** @type {[string, boolean][]} */
  const blocks = [[DOCK, !railed], [TERMINALS, !railed || (Boolean(find(root, CENTER)) && bottom.shown)],
    [RAIL_BLOCK, railed]];
  return [...set, ...blocks.filter(([id, on]) => find(root, id) && (!find(root, id).hidden !== on
    || (moved.changed && id === TERMINALS)))         // moved: said again, over what the app kept of it
    .map(([id, on]) => /** @type {[string, any]} */ ([on ? "layout.show" : "layout.hide", { id }]))];
}

/** Where ROOT's dock comes to rest once let go (restWidth: FROM px last, KEPT «'s width): its width, whether open, the
 * commands that put it there, its blocks and terminal following (BOTTOM); hidden, as it is. @param {any} root
 * @param {number | null} from @param {number | undefined} kept @param {Bottom} [bottom] */
export function dockRest(root, from, kept, bottom = undefined) {
  const px = panelPx(root), to = panelShown(root) ? restWidth(px, from, RAIL, kept ?? PANEL_PX) : null, at = to ?? px;
  return { to: at, open: at !== null && at >= RAIL_BELOW,
    commands: to === null ? [] : panelAt(root, to, [["layout.resize", { id: PANEL, px: to }]], bottom) };
}

// the tab's terminal while the dock is its rail: under the tab, in the centre's column (CENTER), as VS Code's panel,
// BOTTOM_PX high at first, then as dragged; the rail's Terminal shows and hides it; open, back at the dock's foot
export const CENTER = "fold-center", BOTTOM_PX = 240, TERMINALS_WEIGHT = 2;

/** Where layout ROOT has the tab's terminals: under the centre ("bottom") or at the dock's foot. @param {any} root */
export const terminalsAt = (root) => ((find(root, CENTER)?.children ?? []).some((/** @type {any} */ c) =>
  c.id === TERMINALS) ? "bottom" : "dock");

/** The terminal's height under the centre, as dragged; null at the dock's foot. @param {any} root
 * @returns {number | null} */
export const bottomPx = (root) => (terminalsAt(root) === "bottom" ? find(root, TERMINALS)?.size?.px ?? null : null);

/** Whether the terminal shows under the centre. @param {any} root */
export const bottomShown = (root) => terminalsAt(root) === "bottom" && !find(root, TERMINALS)?.hidden;

/** ROOT with its terminals' stack moved WHERE: under the tab (SHOWN or not, PX high) or back after the dock's views (as
 * the layout has it, shown); a copy, and whether it moved. @param {any} root @param {"bottom" | "dock"} where
 * @param {Partial<Bottom>} [bottom] */
export function placeTerminals(root, where, { shown = true, px = BOTTOM_PX } = {}) {
  const there = terminalsAt(root) === where || !find(root, CENTER) || !find(root, TERMINALS);
  if (there) return { tree: root, changed: false };
  const copy = JSON.parse(JSON.stringify(root)), from = find(copy, where === "bottom" ? PANEL : CENTER);
  const stack = from.children.find((/** @type {any} */ c) => c.id === TERMINALS);
  from.children = from.children.filter((/** @type {any} */ c) => c !== stack);
  if (where === "bottom") find(copy, CENTER).children.push(Object.assign(stack, { size: { px }, hidden: !shown }));
  else {
    const panel = find(copy, PANEL), at = panel.children.findIndex((/** @type {any} */ c) => c.id === DOCK) + 1;
    panel.children.splice(at, 0, Object.assign(stack, { size: { weight: TERMINALS_WEIGHT }, hidden: false }));
  }
  return { tree: copy, changed: true };
}

/** The rail's Terminal pressed: the terminal under the centre hidden or shown, and the choice (SHOWN) to keep for the
 * next fold; nothing while it is at the dock's foot. @param {any} root */
export function bottomToggle(root) {
  if (terminalsAt(root) !== "bottom") return { commands: /** @type {[string, any][]} */ ([]), shown: null };
  const shown = bottomShown(root);
  return { commands: /** @type {[string, any][]} */ ([[shown ? "layout.hide" : "layout.show", { id: TERMINALS }]]),
    shown: !shown };
}

/** COMMANDS, then what ROOT's right panel, shown PX wide, has to show (BOTTOM: its terminal's, folded).
 * @param {any} root @param {number} px @param {[string, any][]} commands @param {Bottom} [bottom] */
function panelAt(root, px, commands, bottom = undefined) {
  const after = JSON.parse(JSON.stringify(root));
  Object.assign(find(after, PANEL), { hidden: false, size: { px } });
  return [...commands, ...railFollow(after, bottom)];
}

/** ROOT's right panel folded to its rail, its terminal under the centre as BOTTOM says. @param {any} root
 * @param {Bottom} [bottom] */
const railFold = (root, bottom) => panelAt(root, RAIL, [["layout.resize", { id: PANEL, px: RAIL }]], bottom);

/** ROOT's right panel shown open: KEPT px wide (the width it had, else PANEL_PX) when it was a rail. @param {any} root
 * @param {number | undefined} kept @returns {[string, any][]} */
function railOpen(root, kept) {
  const panel = find(root, PANEL), px = panelRailed(root) ? kept ?? PANEL_PX : panel.size?.px ?? PANEL_PX;
  return panelAt(root, px, [...(panel.hidden ? [/** @type {[string, any]} */ (["layout.show", { id: PANEL }])] : []),
    ["layout.resize", { id: PANEL, px }]]);
}

/** Cmd+Shift+E in layout ROOT, as the TUI's right column: the dock (open or its rail, the terminal at its foot) hidden
 * entirely, or shown again as it was, its blocks following (BOTTOM). @param {any} root @param {Bottom} [bottom]
 * @returns {[string, any][]} */
export function columnToggle(root, bottom = undefined) {
  const panel = find(root, PANEL);
  if (!panel) return [];
  if (!panel.hidden) return [["layout.hide", { id: PANEL }]];
  const after = JSON.parse(JSON.stringify(root));
  find(after, PANEL).hidden = false;
  return [["layout.show", { id: PANEL }], ...railFollow(after, bottom)];
}

/** Cmd+Shift+O in layout ROOT, as the TUI's Restore panels: every view More hid shown again (Issues on GITHUB only),
 * the dock if hidden, its blocks following BOTTOM (on its rail, the terminal under the tab). @param {any} root
 * @param {boolean} github @param {Bottom} bottom @returns {[string, any][]} */
export function restoreCommands(root, github, bottom) {
  const after = JSON.parse(JSON.stringify(root));
  const ids = [...VIEWS_APP.filter((view) => available(view, github) && find(after, view)?.hidden),
    ...(find(after, PANEL)?.hidden ? [PANEL] : [])];
  for (const id of ids) find(after, id).hidden = false;
  return [...ids.map((id) => /** @type {[string, any]} */ (["layout.show", { id }])), ...railFollow(after, bottom)];
}

/** » / « and Cmd+Option+B in layout ROOT: railToggle's (KEPT, BOTTOM), the Chats list in the open dock closed first,
 * the view CHOSEN back (GITHUB's): a fold never only closes it. @param {any} root @param {boolean} github
 * @param {string | null} chosen @param {number | undefined} kept @param {Bottom} [bottom] @returns {[string, any][]} */
export function foldCommands(root, github, chosen, kept, bottom = undefined) {
  const open = panelShown(root) && !panelRailed(root) && find(root, DOCK)?.active === CHATS_BLOCK;
  return [...(open ? chatsToggle(root, github, chosen) : []), ...railToggle(root, kept, bottom)];
}

/** The commands of the tab bar's » / «: an open right panel folded to its rail (its terminal under the centre as
 * BOTTOM says), else opened (KEPT px wide when it was a rail). @param {any} root @param {number | undefined} kept
 * @param {Bottom} [bottom] */
export function railToggle(root, kept, bottom = undefined) {
  const panel = find(root, PANEL);
  if (!panel) return [];
  return !panel.hidden && !panelRailed(root) ? railFold(root, bottom) : railOpen(root, kept);
}

/** The stack under the panel's views showing the focused tab's own terminal, as the TUI's right column does; its
 * stand-in shows until a tab's terminal is there, its header names the one shown. */
export const TERMINALS = "fold-terminals";
const PREFIX = "fold-terminal-", NONE = "fold-terminal-none";

/** The layout id of TAB's terminal in that stack. @param {string} tab */
export const terminalId = (tab) => PREFIX + tab.toLowerCase().replace(/[^a-z0-9-]+/g, "-");

/** The tab's terminal the layout ROOT's stack shows (its address), for the rail's float; null while its stand-in shows.
 * @param {any} root @returns {string | null} */
export function activeTerminal(root) {
  const stack = find(root, TERMINALS), shown = stack?.children?.find((c) => c.id === stack.active);
  return typeof shown?.content?.terminal === "string" ? shown.content.terminal : null;
}

/** A terminal's machine, from its address (`lab/t7`): null for this computer's. @param {string} address */
export const machineOf = (address) => (address.includes("/") ? address.split("/")[0] : null);

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

/** A chat's agent's label: its chat tab's id. A tab closing leaves it running (the app quitting closes tabs too, and
 * they come back), so it ends once its tab is gone. */
export const CHAT_TAB = "herdr-fold.chat-tab";
export const CHAT_LABEL = "herdr-fold.chat";       // its other label: its session, by which it is found again

// a chat waiting on you, in herdr-fold's own signals: its tab, its space's row, the ✦'s count, Chats, sound, toast
export const CHAT_WAITS = "herdr-fold.chat-waits";      // shared: each chat waiting on you, by its tab
export const WAY_OUT = 2000;     // ms an agent asks in its own terminal, no card coming, before the chat says so

/** How a chat waits on you at NOW: "request" while its card asks (PENDING), "terminal" once its agent has asked in its
 * own terminal (since BLOCKED, no card) for WAY_OUT ms, else null. @param {any} pending
 * @param {number | null} blocked @param {number} now */
export const chatWait = (pending, blocked, now) => (pending ? "request"
  : blocked !== null && now - blocked >= WAY_OUT ? "terminal" : null);

/** KEPT (CHAT_WAITS) with TAB's WAIT ({space, address, since}; null: gone), the chats whose agent is not LIVE any more
 * dropped. @param {any} kept @param {string} tab @param {any} wait @param {Set<string>} live */
export function keepWait(kept, tab, wait, live) {
  const next = Object.fromEntries(Object.entries(kept ?? {}).filter(([at, w]) => at !== tab && live.has(w?.address)));
  return wait ? { ...next, [tab]: wait } : next;
}

/** The chats waiting in KEPT (CHAT_WAITS) whose agent still runs among TERMINALS (the app's): their tabs, each space's
 * longest wait (since when), their agents. @param {any} kept @param {any[]} terminals */
export function waiting(kept, terminals) {
  const live = new Set(terminals.filter((t) => t.state === "live").map((t) => t.address));
  const found = Object.entries(kept ?? {}).filter(([, w]) => live.has(w?.address));
  /** @type {Record<string, number>} */
  const spaces = {};
  for (const [, w] of found) spaces[w.space] = Math.min(spaces[w.space] ?? Infinity, w.since);
  return { tabs: new Set(found.map(([tab]) => tab)), spaces, agents: new Set(found.map(([, w]) => w.address)) };
}

/** The chat tabs' agents among TERMINALS as core/chats.py takes herdr's (coreAgents'): each by its session and its
 * program (Claude or Codex; Claude until it says), blocked while its chat waits on you (WAITING: their addresses), else
 * as it says. @param {any[]} terminals @param {Set<string>} waiting */
export const chatAgents = (terminals, waiting) => terminals
  .filter((t) => t.state === "live" && t.labels?.[CHAT_TAB] && t.labels?.[CHAT_LABEL])
  .map((t) => ({ agent: t.program?.key === "codex" ? "codex" : "claude",
    agent_status: waiting.has(t.address) ? "blocked" : t.status ?? "idle",
    pane_id: t.address, agent_session: { value: t.labels[CHAT_LABEL] } }));

/** The live chat agents among TERMINALS (the app's) whose tab is no longer among TABS (ids), to end.
 * @param {any[]} terminals @param {string[]} tabs */
export const orphanChats = (terminals, tabs) => terminals
  .filter((t) => t.state === "live" && t.labels?.[CHAT_TAB] && !tabs.includes(t.labels[CHAT_TAB]))
  .map((t) => t.address);

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

/** The reopened chats KEPT ({terminal: id}) whose agents still run (LIVE, their terminals); all of them while
 * none is known (the app starting, its core reconnecting): never forgotten for a moment's empty list.
 * @param {Record<string, string>} kept @param {Set<string>} live */
export function stillResumed(kept, live) {
  return live.size ? Object.fromEntries(Object.entries(kept).filter(([terminal]) => live.has(terminal))) : { ...kept };
}

/** The message field on a change of space: FROM's MESSAGE kept in DRAFTS (an empty one forgotten), TO's own given
 * back and taken out ("" for one without). @param {Map<string, string>} drafts @param {string | null} from
 * @param {string} to @param {string} message */
export function swapDraft(drafts, from, to, message) {
  if (from !== null && message.trim()) drafts.set(from, message);
  else if (from !== null) drafts.delete(from);
  const back = drafts.get(to) ?? "";
  drafts.delete(to);
  return back;
}

/** PATH's extension, lowercase with its dot; "" without one. @param {string} path */
function extension(path) {
  const dot = path.lastIndexOf("."), name = path.lastIndexOf("/") + 1;
  return dot > name ? path.slice(dot).toLowerCase() : "";
}

/** PATH's kind by its extension, as core/media.py has it: image, pdf or html, else null. @param {string} path */
export function mediaKind(path) {
  return /** @type {Record<string, string>} */ (MEDIA_KINDS)[extension(path)] ?? null;
}

/** Where Open in … opens PATH on PLATFORM (window()'s), as core/media.py's opener(): the browser, or on a Mac Preview
 * for a picture no browser shows (a browser would only download a PSD or an EXR). */
export function opener(path, platform) {
  return platform === "macos" && !MEDIA_WEB.includes(extension(path)) ? "Preview" : "Browser";
}

/** A changed picture's sides, as VS Code's image diff: the last commit's and the file's (HEAD, Working Tree), each
 * [its caption with its own pixels, it]; a new one's after alone, a deleted one's before alone.
 * @param {{ before: any, after: any }} change @returns {[string, any][]} */
export function changeSides({ before, after }) {
  return /** @type {[string, any][]} */ ([["HEAD", before], ["Working Tree", after]].filter(([, side]) => side)
    .map(([label, side]) => [side.pixels ? `${label} · ${side.pixels[0]} × ${side.pixels[1]}` : label, side]));
}

/** Whether WHAT, the preview's, opens in the browser: a page, a PDF or a picture, a file on this Mac.
 * @param {{ kind: string, path: string, on?: string | null } | null} what */
export function browsable(what) {
  return what?.kind === "file" && !what.on && mediaKind(what.path) !== null;
}

const MARKDOWN = [".md", ".markdown"];
/** The editor's language by a file's extension; another is plain text. */
const LANGUAGES = /** @type {Record<string, string>} */ ({ ".json": "json", ".jsonc": "json", ".toml": "toml",
  ".yaml": "yaml", ".yml": "yaml", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
  ".jsx": "javascript", ".ts": "typescript", ".tsx": "tsx", ".py": "python", ".rs": "rust", ".go": "go",
  ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".md": "markdown", ".markdown": "markdown", ".html": "html",
  ".htm": "html", ".svg": "html", ".css": "css", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".java": "java",
  ".rb": "ruby", ".swift": "swift", ".sql": "sql", ".lua": "lua", ".zig": "zig" });
export const FOUND_MOST = 9999;    // a find's matches counted at most (the count says "9999+")

/** Whether PATH opens in an editor tab of its own: text, nothing the preview draws (a picture, a PDF, a page, an SVG,
 * Markdown, each with its code a view away). @param {string} path */
export const editsInTab = (path) => mediaKind(path) === null && !MARKDOWN.includes(extension(path));

/** Whether PATH is Markdown, which the preview draws. @param {string} path */
export const markdownFile = (path) => MARKDOWN.includes(extension(path));

/** PATH's language for the editor, by its extension. @param {string} path */
export const editorLanguage = (path) => LANGUAGES[extension(path)] ?? "text";

/** TEXT's indent as its lines have it: tabs where more lines start with one than with spaces, else the fewest
 * spaces an indented line has (2 to 8), 2 without any. @param {string} text */
export function indentOf(text) {
  const starts = text.split("\n", 2000).map((line) => /^(\t+| +)\S/.exec(line)?.[1] ?? "").filter(Boolean);
  const tabs = starts.filter((start) => start[0] === "\t").length;
  const spaces = starts.filter((start) => start[0] === " ").map((start) => start.length).filter((n) => n > 1);
  return { size: Math.min(8, Math.max(2, spaces.length ? Math.min(...spaces) : 2)), hard: tabs > spaces.length };
}

/** TEXT as it is written over DISK (the file's text as read): CRLF throughout where the file had it, as a line typed
 * comes in as LF. @param {string} text @param {string | null} disk */
export const withEnds = (text, disk) => (disk?.includes("\r\n") ? text.replace(/\r?\n/g, "\r\n") : text);

/** QUERY's places in TEXT, case aside, as VS Code's find: [start, end] (UTF-16 offsets), MOST at most.
 * @param {string} text @param {string} query @returns {[number, number][]} */
export function findAll(text, query, most = FOUND_MOST) {
  if (!query) return [];
  const found = /** @type {[number, number][]} */ ([]);
  const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  for (let hit = pattern.exec(text); hit && found.length < most; hit = pattern.exec(text)) {
    found.push([hit.index, hit.index + hit[0].length]);
  }
  return found;
}

/** The match to go to among MATCHES from the selection's start AT: the first at or after it, or (BACK) the last before
 * it, round past either end; -1 for none. @param {[number, number][]} matches @param {number} at */
export function nextMatch(matches, at, back = false) {
  if (!matches.length) return -1;
  if (back) {
    const after = matches.findIndex(([start]) => start >= at);
    return (after < 0 ? matches.length : after || matches.length) - 1;
  }
  const after = matches.findIndex(([start]) => start >= at);
  return after < 0 ? 0 : after;
}

/** The find bar's count: "2 of 3", "No results" for a query found nowhere. @param {number} at
 * @param {[number, number][]} matches @param {string} query */
export const findCount = (at, matches, query) => (!query ? "" : !matches.length ? "No results"
  : `${at + 1} of ${matches.length}${matches.length >= FOUND_MOST ? "+" : ""}`);

/** A draft's file name for the file at PATH: a hash of it (cyrb53), so the state folder's names hold no path.
 * @param {string} path */
export function draftName(path) {
  let a = 0xdeadbeef, b = 0x41c6ce57;
  for (let i = 0; i < path.length; i++) {
    const ch = path.charCodeAt(i);
    a = Math.imul(a ^ ch, 2654435761);
    b = Math.imul(b ^ ch, 1597334677);
  }
  a = Math.imul(a ^ (a >>> 16), 2246822507) ^ Math.imul(b ^ (b >>> 13), 3266489909);
  b = Math.imul(b ^ (b >>> 16), 2246822507) ^ Math.imul(a ^ (a >>> 13), 3266489909);
  return `${(4294967296 * (2097151 & b) + (a >>> 0)).toString(16).padStart(14, "0")}.json`;
}

/** SPACE's tab named NAME with herdr-fold in it (PANES, the app's panes()): an editor's, named for its file; or null.
 * @param {{ tabs?: { id: string, name: string }[] } | undefined} space @param {string} name
 * @param {{ tab: string, mod?: string }[]} panes */
export const modTab = (space, name, panes) => space?.tabs?.find((t) => t.name === name &&
  panes.some((p) => p.tab === t.id && p.mod === "herdr-fold"))?.id ?? null;

/** The key an editor's unsaved changes are kept under in UNSAVED (shared): the space and its tab's name.
 * @param {string} space @param {string} tab */
export const unsavedKey = (space, tab) => `${space}\t${tab}`;

/** SPACE's tabs with unsaved changes, as UNSAVED (shared: unsavedKey()'s) says: their × a dot.
 * @param {{ id: string, tabs?: { id: string, name: string }[] } | undefined} space
 * @param {Record<string, boolean>} unsaved */
export const unsavedTabs = (space, unsaved) => new Set((space?.tabs ?? [])
  .filter((t) => unsaved[unsavedKey(space?.id ?? "", t.name)]).map((t) => t.id));

/** The projects the Start tab offers: the folders of CHATS (core/chats.py's list), the newest first, each once, at
 * most LIMIT; HOME and a folder above it left out (an agent works in a project, never there).
 * @param {{ folder: string, time: number }[]} chats @param {string} home @returns {string[]} */
export function recentProjects(chats, home, limit = 6) {
  const out = (/** @type {string} */ f) => f === "/" || f === home || home.startsWith(`${f}/`);
  const found = [];
  for (const chat of [...chats].sort((a, b) => b.time - a.time)) {
    const folder = String(chat.folder ?? "").replace(/(.)\/+$/, "$1");
    if (folder.startsWith("/") && !out(folder) && !found.includes(folder)) found.push(folder);
    if (found.length === limit) break;
  }
  return found;
}

/** FOLDER as the Start tab says it: under HOME as ~/…. @param {string} folder @param {string} home */
export const homeShort = (folder, home) => folder.startsWith(`${home}/`) ? `~${folder.slice(home.length)}` : folder;
