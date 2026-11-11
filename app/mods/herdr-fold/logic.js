// @ts-check
// What the mod works out without the window: a diff's rows, the sync button's words, a long job run in the background
// on the space's machine (exec stops a program after 30 s; an AI may take minutes), the commit message writer's answer.

import { JOB, MEDIA_KINDS, MEDIA_WEB } from "./helper.js";
import { BY_EXTENSION, BY_NAME, FILE, FOLDER, LETTER } from "./icons.js";

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

/** The focused TAB's own Claude or Codex among AGENTS (the app's agents()), to hand an issue to; or null.
 * @param {{ tab: string, program?: { key: string } }[]} agents @param {string | undefined} tab */
export const issueAgent = (agents, tab) =>
  agents.find((a) => a.tab === tab && ["claude", "codex"].includes(a.program?.key ?? "")) ?? null;

/** A conversation as core/conversations.py lists it: a running one's STATE (herdr's) and PANE (its terminal) set.
 * @typedef {{ agent: string, id: string, title: string, folder: string, time: number, state: string,
 *   pane: string }} Conversation */

/** The app's AGENTS as core/conversations.py takes herdr's: Claude and Codex in this Mac's spaces (LOCAL, their ids),
 * each with its pane's folder (from PANES), its terminal for its pane.
 * @param {any[]} agents @param {any[]} panes @param {Set<string>} local */
export const coreAgents = (agents, panes, local) => agents
  .filter((a) => local.has(a.space) && ["claude", "codex"].includes(a.program?.key ?? ""))
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

/** ITEM's key among the archived, as the TUI's column keeps it. @param {Conversation} item */
export const archiveKey = (item) => `${item.agent}:${item.id}`;

/** The rows: each space of ORDER, its STATES' state, with its ITEMS (PLACE: {folder: space}) that match TYPED, FRONT's
 * panes first, then the newest; archived ones only typed or shown; HERE open unless CLOSED, others OPENED or typed.
 * @param {Conversation[]} items @param {string[]} order @param {Record<string, string>} place @param {any} how */
export function conversationRows(items, order, place, how) {
  const { typed = "", archived = new Set(), showArchived = false, opened = new Set(), closed = new Set(), here = null,
    front = new Set(), states = {} } = how;
  const word = typed.toLowerCase();
  const matches = (item) => !word || [item.title, place[item.folder] ?? "", item.folder,
    archived.has(archiveKey(item)) ? "archived" : ""].some((part) => part.toLowerCase().includes(word));
  const open = (name) => Boolean(word) || opened.has(name) || (!closed.has(name) && name === here);
  return order.flatMap((name) => {
    const found = items.filter((item) => place[item.folder] === name && matches(item)
      && (!archived.has(archiveKey(item)) || Boolean(word) || showArchived))
      .sort((a, b) => Number(front.has(b.pane)) - Number(front.has(a.pane)) || b.time - a.time);
    if (word && !found.length) return [];
    const group = { kind: "group", name, items: found, open: open(name), here: name === here,
      state: states[name] ?? null };
    const under = group.open ? found.map((item, n) => ({ kind: "item", item, last: n === found.length - 1 })) : [];
    return [group, ...under];
  });
}

/** A conversation's id as claude --resume and codex resume take it: from a file's content, so never an option, a space
 * or a control code. */
const SESSION = /^[0-9A-Za-z][0-9A-Za-z._-]*$/;

/** The command that reopens ITEM, a closed conversation: its agent resuming it. @param {Conversation} item */
export function resumeArgv(item) {
  if (!SESSION.test(item.id) || !["claude", "codex"].includes(item.agent)) throw new Error("not a conversation's id");
  return item.agent === "claude" ? ["claude", "--resume", item.id] : ["codex", "resume", item.id];
}

const CHOICES = ["Open", "Copy conversation", "Rename"];

/** The right click's menu on ITEM: Archive for a closed one, Unarchive for an archived one; on none (null), Show or
 * Hide archived while any is. @param {Conversation | null} item @param {Set<string>} archived
 * @param {boolean} showArchived */
export function conversationChoices(item, archived, showArchived) {
  if (!item) return archived.size ? [showArchived ? "Hide archived" : "Show archived"] : [];
  if (archived.has(archiveKey(item))) return [...CHOICES, "Unarchive"];
  return item.state ? CHOICES : [...CHOICES, "Archive"];
}

const TAB_NAME = 24;          // a conversation's name on its tab, as the TUI's column (AI Sessions') puts it there

/** TITLE as a reopened conversation's tab name: printable characters only, no leading dash, cut with "…".
 * @param {string} title */
export function tabLabel(title) {
  const name = [...title].filter((ch) => ch === " " || !/[\p{C}\p{Z}]/u.test(ch)).join("").replace(/^[- ]+/, "");
  return name.length <= TAB_NAME ? name : `${name.slice(0, TAB_NAME - 1)}…`;
}

/** An issue as its preview shows it, with its priority as the list ranked it.
 * @typedef {{ kind: "issue", github: string, number: number, title: string, level?: number | null,
 *   ranked_by?: string | null }} ShownIssue */
/** What a preview shows, where (ROOT on machine ON): a change's diff (a new file's as all added), a file, a commit or
 * an issue. @typedef {{ root: string, on: string | null } & ({ kind: "diff" | "file", path: string }
 *   | { kind: "commit", hash: string } | ShownIssue)} Shown */

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
function find(node, id) {
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

/** The width layout ROOT's sidebar takes when its toggle is pressed, as the app's own toggle has it: folded, as wide
 * as the traffic lights on macOS (MACOS), RAIL; opened, KEPT, the width it had, else 268.
 * @param {any} root @param {boolean} macos @param {number | undefined} kept */
export const foldedWidth = (root, macos, kept) => (railed(root) ? kept ?? 268 : macos ? RAIL : 44);

/** SPACE's tabs as the tab bar draws them, as the app's own: one nobody named takes the space's name on the first
 * (the TUI's main tab), else its program's (an agent's first, a chat tab's agent: CHATS, by tab), else Terminal; an
 * agent's icon (TINT: the text's color), its state, zoomed marked Z. @param {any} space @param {any[]} panes */
export function tabRows(space, panes, /** @type {Record<string, any>} */ chats = {}) {
  return (space?.tabs ?? []).map((/** @type {any} */ c, /** @type {number} */ i) => {
    const program = chats[c.id]?.program ?? panes.find((p) => p.tab === c.id && p.program?.agent)?.program
      ?? panes.find((p) => p.tab === c.id)?.program;
    const given = !c.named, first = i === 0 && space.name;
    const name = !given ? c.name : first ? space.name : program?.name ?? "Terminal";
    const agent = program?.agent ? program : null;
    return { id: c.id, name: c.zoomed ? `${name} Z` : name, active: Boolean(c.active),
      status: c.status ?? chats[c.id]?.status ?? null,
      icon: agent?.icon ?? null, tint: Boolean(agent?.tint) };
  });
}

/** Whether an SVG's or a page's code goes above its picture: as CHOSEN, else where the ROOM (logical px) is taller
 * than wide, as the TUI's. @param {boolean | null} chosen @param {{ width: number, height: number } | null} room */
export function stacks(chosen, room) {
  return chosen ?? Boolean(room && room.height > room.width);
}

const MENU_EDGE = 8, MENU_OFF = 4;       // px a menu keeps from the window's edges, and from its button

/** Where a menu HIGH and WIDE opens for BUTTON in a window ROOM: under it, right edges in line, where it fits;
 * else above it; else as far in as the window lets it. @param {{ x: number, y: number, width: number,
 * height: number }} button @param {number} high @param {{ width: number, height: number }} room @param {number} wide */
export function menuPlace(button, high, room, wide) {
  const x = Math.max(MENU_EDGE, Math.min(button.x + button.width - wide, room.width - MENU_EDGE - wide));
  const under = button.y + button.height + MENU_OFF, over = button.y - MENU_OFF - high;
  if (under + high <= room.height - MENU_EDGE) return { x, y: under };
  return { x, y: over >= MENU_EDGE ? over : Math.max(MENU_EDGE, room.height - MENU_EDGE - high) };
}

const MENU_ROW = 28, MENU_RULE = 9, MENU_GAP = 2, MENU_PAD = 4;      // px: a menu's row, its rule, between, round

/** The height of a menu of ITEMS (null: a rule between its parts) under its HEAD. @param {(object | null)[]} items
 * @param {object} [head] */
export const menuHeight = (items, head) => items.reduce((h, item) => h + (item ? MENU_ROW : MENU_RULE) + MENU_GAP,
  head ? MENU_ROW + MENU_GAP : 0) + 2 * MENU_PAD;

/** The panel menu's lines about herdr-fold, as the TUI sidebar's ⋯ has them: its version (a newer one's, once out),
 * opening its releases, and Check for Updates; none before a look or where the installer never ran.
 * @param {any} found core/update.py's check */
export function aboutLines(found) {
  if (!found?.version) return [];
  return [{ label: found.newer ? `herdr-fold ${found.latest} is out` : `herdr-fold ${found.version}`,
    url: found.releases }, { label: "Check for Updates", on: Boolean(found.on) }];
}

/** The room the tab bar leaves at its start for the traffic lights of window W (macOS, no title bar, not full
 * screen): what the sidebar and its toggle beside them leave of them at ZOOM, 10 px at least, as the app's own.
 * @param {any} root @param {any} w @param {number} zoom */
export function lightsRoom(root, w, zoom) {
  if (w?.platform !== "macos" || w.titlebar !== "none" || w.fullscreen || !root?.traffic_lights) return 10;
  const width = (/** @type {string} */ id) => (find(root, id)?.hidden ? 0 : find(root, id)?.size?.px ?? 0);
  return Math.max(10, (root.traffic_lights[0] + 64) / zoom - width("sidebar") - width("sidebar-trigger"));
}

/** The room the tab bar leaves at its end so its panel toggle, BUTTON px wide, sits over the middle of the rail,
 * inside the work body's padding (layout ROOT's). @param {any} root @param {number} button */
export const toggleRoom = (root, button) => (find(root, "work-body")?.padding ?? 0) + (RAIL - button) / 2;

// the layout's right panel, its dock's head and its dock of groups: herdr-fold's own ids, so the app's Settings, which
// shows and hides a panel under the app's ids, leaves them alone
export const PANEL = "fold-panel", DOCK_HEAD = "fold-dock-head", DOCK = "fold-dock";
export const RAIL_BLOCK = "panel-rail";      // the right panel's block while it is folded to its rail
export const RAIL = 76;                      // px: the right panel folded to its rail, as the left sidebar folds
export const PANEL_PX = 368;                 // px: the right panel open, unless it kept another width

export const TALL = 440;          // a panel floating beside the folded sidebar, at most

/** A floating panel as tall as its content, up to TALL: its head, then Spaces' SHOWN rows (a count), or the
 * Conversations filter and SHOWN (conversationRows'), each group's head and an open one's conversations.
 * @param {string} panel @param {any} shown */
export function floatHeight(panel, shown) {
  const groups = panel === "spaces" ? [] : shown.filter((row) => row.kind === "group");
  const body = panel === "spaces" ? 29 * shown + 8
    : 38 + (groups.length ? groups.reduce((h, g) => h + 26 + (g.open ? 24 * g.items.length : 0), 0) : 28) + 8;
  return Math.min(TALL, 36 + body);
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

/** Each space's longest wait: since when the first of its AGENTS in WAITS waits.
 * @param {Record<string, any>} waits @param {{ address: string, space: string }[]} agents */
export function spaceWaits(waits, agents) {
  /** @type {Record<string, number>} */
  const first = {};
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

// a space's avatar color, as every app mod draws one: one strong color per hue, light and dark alike
export const MARK = { ansi6: "#22a99a", ansi3: "#e3814f", ansi4: "#5b8def", ansi5: "#8b7cf6", ansi2: "#3fae6a",
  ansi1: "#d9649a" };
const PALETTE = ["ansi6", "ansi3", "ansi4", "ansi5", "ansi2", "ansi1"];

/** The spaces' colors as every app mod keeps them (shared "space.colors"): KEPT's for the spaces of LIST still there,
 * one without given the color fewest use, in LIST's order, the home folder's ("~") none; null when nothing changed.
 * @param {{ id: string, name: string }[]} list @param {Record<string, string>} kept */
export function spaceColors(list, kept) {
  const ids = new Set(list.map((s) => s.id));
  const colors = Object.fromEntries(Object.entries(kept).filter(([id]) => ids.has(id)));
  let changed = Object.keys(colors).length !== Object.keys(kept).length;
  for (const { id, name } of list) {
    if (colors[id] || name === "~") continue;
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

/** The Spaces list's height as GROUPS draw it: the block, its edge dragged, grows only as far as that.
 * @param {SpaceGroup[]} groups */
export function listHeight(groups) {
  const heads = headed(groups), one = { none: 0, loading: LIST.tree, empty: LIST.tree };
  return LIST.head + LIST.foot + groups.reduce((h, g) => h + (heads ? LIST.machine : 0) + (listBody(g, heads) ===
    "rows" ? g.rows.reduce((n, r) => n + (r.tree ? LIST.tree : LIST.row), 0) : one[listBody(g, heads)]), 0);
}

/** TREE (a layout) with node ID's max at PX, never under its min: a copy, and whether it differs from TREE (else
 * nothing to write). @param {any} tree @param {string} id @param {number} px */
export function withMax(tree, id, px) {
  const node = find(tree, id), max = Math.max(node?.min ?? 0, px);
  if (!node || node.max === max) return { tree, changed: false };
  const copy = JSON.parse(JSON.stringify(tree));
  find(copy, id).max = max;
  return { tree: copy, changed: true };
}

/** Whether layout ROOT shows the right panel. @param {any} root */
export function panelShown(root) {
  const panel = find(root, PANEL);
  return Boolean(panel && !panel.hidden);
}

// the right dock's groups, as core/dock.py's GROUPS: each a column of its own (fold-project), its head over a stack of
// its panels' blocks (fold-project-body); a panel hidden from the dock's ⋯ is its block hidden
export const GROUPS_APP = { project: ["files", "search"], work: ["changes", "issues"] };
export const PANEL_NAMES = { files: "Files", search: "Search", changes: "Changes", issues: "Issues" };
// px inside a card, on every side: a terminal's text, a group's tabs, a view's words and fields; a row's hover pad
// reaches halfway in (PAD / 2). Here, as the dock's sizes need it; parts.js hands it to the views.
export const PAD = 12;
export const GROUP_HEAD = PAD + 24;          // px: a group's head, its tabs (24 high) and its fold PAD under the top
export const FOLDED_GROUP = GROUP_HEAD + PAD + 2;    // px: a group folded to its head, PAD under it, in its frame
export const GROUP_WEIGHTS = { project: 2, work: 3 };    // the layout's own shares, a group opened again without one
const column = (/** @type {string} */ group) => `fold-${group}`, body = (/** @type {string} */ group) =>
  `fold-${group}-body`;

/** The group PANEL is in, or null. @param {string} panel @returns {string | null} */
export const groupOf = (panel) => Object.keys(GROUPS_APP).find((g) => GROUPS_APP[g].includes(panel)) ?? null;

/** Whether PANEL can show here: Issues for a repository on GitHub (GITHUB) only. */
const available = (/** @type {string} */ panel, /** @type {boolean} */ github) => panel !== "issues" || github;

/** GROUP's tabs in layout ROOT: its panels whose blocks are there and not hidden, Issues only on GitHub (GITHUB).
 * @param {any} root @param {string} group @param {boolean} github @returns {string[]} */
export const groupTabs = (root, group, github) => (GROUPS_APP[group] ?? [])
  .filter((panel) => available(panel, github) && find(root, panel) && !find(root, panel).hidden);

/** Every panel layout ROOT shows, group by group. @param {any} root @param {boolean} github */
export const shownPanels = (root, github) => Object.keys(GROUPS_APP).flatMap((g) => groupTabs(root, g, github));

/** The tab GROUP shows in layout ROOT: its stack's child while it is a tab, else its first tab, else null.
 * @param {any} root @param {string} group @param {boolean} github @returns {string | null} */
export function shownTab(root, group, github) {
  const tabs = groupTabs(root, group, github), active = find(root, body(group))?.active;
  return tabs.includes(active) ? active : tabs[0] ?? null;
}

/** Whether GROUP is folded to its head in layout ROOT: its stack hidden. @param {any} root @param {string} group */
export const groupFolded = (root, group) => Boolean(find(root, body(group))?.hidden);

/** GROUP's size in layout ROOT ({ weight } or { px }), kept while it folds. @param {any} root @param {string} group */
export const groupSize = (root, group) => find(root, column(group))?.size;

/** The commands that fold GROUP in layout ROOT to its head, or open it again at SIZE (the size it had; a fold's own,
 * or none: the layout's share). @param {any} root @param {string} group @param {any} size @returns {[string, any][]} */
export function foldCommands(root, group, size) {
  if (!find(root, body(group))) return [];
  if (!groupFolded(root, group)) {
    return [["layout.hide", { id: body(group) }], ["layout.resize", { id: column(group), px: FOLDED_GROUP }]];
  }
  const back = size?.weight ? { weight: size.weight } : size?.px > FOLDED_GROUP ? { px: size.px }
    : { weight: GROUP_WEIGHTS[group] };
  return [["layout.show", { id: body(group) }], ["layout.resize", { id: column(group), ...back }]];
}

/** Each group's tab kept in layout ROOT: CHOSEN's (the one last picked), else the one its stack is on.
 * @param {any} root @param {Record<string, string>} chosen @returns {Record<string, string>} */
export function keptTabs(root, chosen) {
  const kept = { ...chosen };
  for (const g of Object.keys(GROUPS_APP)) kept[g] ??= find(root, body(g))?.active;
  return Object.fromEntries(Object.entries(kept).filter(([, tab]) => tab));
}

/** The commands that make layout ROOT's groups show what their panels say: a group with no tab hidden, the others
 * shown, a stack on its CHOSEN tab while it can show it, else on another (Issues off GitHub: Changes meanwhile).
 * @param {any} root @param {boolean} github @param {Record<string, string>} [chosen] @returns {[string, any][]} */
export function panelsFollow(root, github, chosen = {}) {
  const groups = Object.keys(GROUPS_APP).filter((g) => find(root, column(g)));
  /** @type {[string, any][]} */
  const shows = groups.flatMap((g) => {
    const on = groupTabs(root, g, github).length > 0;
    return !find(root, column(g)).hidden === on ? [] : [[on ? "layout.show" : "layout.hide", { id: column(g) }]];
  });
  /** @type {[string, any][]} */
  const picks = groups.flatMap((g) => {
    const tabs = groupTabs(root, g, github), active = find(root, body(g))?.active;
    const want = tabs.includes(chosen[g]) ? chosen[g] : tabs.includes(active) ? active : tabs[0];
    return want && want !== active ? [["layout.select", { stack: body(g), child: want }]] : [];
  });
  return [...shows, ...picks];
}

/** A panel's key or tab in layout ROOT: PANEL shown in its group, its new choice over CHOSEN's (hidden in the ⋯: shown
 * again), the group opened (SIZES'), the dock too (KEPT px wide); none where it can't (GITHUB). @param {any} root
 * @param {string} panel @param {{ github?: boolean, kept?: number, sizes?: any, chosen?: any }} [how] */
export function pickCommands(root, panel, { github = false, kept = undefined, sizes = {}, chosen = {} } = {}) {
  const group = groupOf(panel);
  if (!group || !available(panel, github) || !find(root, panel) || !find(root, PANEL)) return [];
  const after = JSON.parse(JSON.stringify(root)), stack = find(after, body(group));
  /** @type {[string, any][]} */
  const commands = [];
  if (find(after, panel).hidden) {
    commands.push(["layout.show", { id: panel }]);
    find(after, panel).hidden = false;
  }
  if (stack.active !== panel) {
    commands.push(["layout.select", { stack: body(group), child: panel }]);
    stack.active = panel;
  }
  if (stack.hidden) {
    commands.push(...foldCommands(after, group, sizes[group]));
    stack.hidden = false;
  }
  commands.push(...panelsFollow(after, github, { ...chosen, [group]: panel }));
  return find(after, PANEL).hidden || panelRailed(after) ? [...commands, ...railOpen(after, kept)] : commands;
}

/** The dock's ⋯'s panels, as the TUI's: each with its ✓ while shown (ON), Issues on GitHub only; the last one shown
 * can't be unchecked (OFF). @param {any} root @param {boolean} github */
export function panelChoices(root, github) {
  const shown = shownPanels(root, github);
  return Object.values(GROUPS_APP).flat().filter((panel) => available(panel, github) && find(root, panel))
    .map((panel) => ({ panel, label: PANEL_NAMES[panel], on: shown.includes(panel),
      off: shown.length === 1 && shown[0] === panel }));
}

/** The commands that hide PANEL from layout ROOT's dock (HIDE) or show it again, back on its group's CHOSEN tab;
 * hidden: its group on its other tab, or gone with none left; never the last. @param {any} root @param {string} panel
 * @param {boolean} hide @param {boolean} github @param {any} [chosen] @returns {[string, any][]} */
export function hideCommands(root, panel, hide, github, chosen = {}) {
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

/** The commands that make ROOT's right panel show what its width says, a drag's too: its rail's block, at RAIL px, or
 * its dock's head and its dock; nothing while it is hidden. @param {any} root @returns {[string, any][]} */
export function railFollow(root) {
  const panel = find(root, PANEL);
  if (!panel || panel.hidden) return [];
  const railed = panelRailed(root);
  /** @type {[string, boolean][]} */
  const blocks = [[DOCK_HEAD, !railed], [DOCK, !railed], [RAIL_BLOCK, railed]];
  return [...blocks.filter(([id, on]) => find(root, id) && !find(root, id).hidden !== on)
    .map(([id, on]) => /** @type {[string, any]} */ ([on ? "layout.show" : "layout.hide", { id }])),
  ...(railed && panel.size?.px !== RAIL ? [/** @type {[string, any]} */ (["layout.resize", { id: PANEL, px: RAIL }])]
    : [])];
}

/** COMMANDS, then what ROOT's right panel, shown PX wide, has to show. @param {any} root @param {number} px
 * @param {[string, any][]} commands */
function panelAt(root, px, commands) {
  const after = JSON.parse(JSON.stringify(root));
  Object.assign(find(after, PANEL), { hidden: false, size: { px } });
  return [...commands, ...railFollow(after)];
}

/** ROOT's right panel folded to its rail. @param {any} root */
const railFold = (root) => panelAt(root, RAIL, [["layout.resize", { id: PANEL, px: RAIL }]]);

/** ROOT's right panel shown open: KEPT px wide (the width it had, else PANEL_PX) when it was a rail. @param {any} root
 * @param {number | undefined} kept @returns {[string, any][]} */
function railOpen(root, kept) {
  const panel = find(root, PANEL), px = panelRailed(root) ? kept ?? PANEL_PX : panel.size?.px ?? PANEL_PX;
  return panelAt(root, px, [...(panel.hidden ? [/** @type {[string, any]} */ (["layout.show", { id: PANEL }])] : []),
    ["layout.resize", { id: PANEL, px }]]);
}

/** The commands of the dock's » and the tab bar's «: an open right panel folded to its rail, else opened (KEPT px
 * wide when it was a rail). @param {any} root @param {number | undefined} kept */
export function railToggle(root, kept) {
  const panel = find(root, PANEL);
  if (!panel) return [];
  return !panel.hidden && !panelRailed(root) ? railFold(root) : railOpen(root, kept);
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

/** The reopened conversations KEPT ({terminal: id}) whose agents still run (LIVE, their terminals); all of them while
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
