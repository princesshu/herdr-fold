// @ts-check
// The Spaces list where the app's own was, drawn as it draws one: by machine (by network once many), a worktree under
// its checkout, each space's branch, dragged into order, the app's menu on a right click; agents' waits, as the TUI's.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { agents, focused, hc, home, machines, openOverlay, panes, pickFolder, setShared, shared, spaces, watchFolder,
  window, run as command } from "herdr";
import { chatWaits, newSpace } from "./chat.js";
import { GIT } from "./helper.js";
import { atHome, avatarFill, CENTRED, folderKey, HOME_NAME, homeFirst, homeId, homesEmpty, homesSeen, importCommand,
  LIST, nested, NETWORKS_FOLDED, NETWORKS_SEEN, nextWaits, placeKey, placeLabel, spaceColor, spaceColors, spaceLabel,
  spacesItems, spaceWaits, toAddWords, toggleUnread, hovering, waited, withHomes }
  from "./logic.js";
import { openMachines } from "./panel.js";
import { GAP, icon, iconButton, listHead, networkMark } from "./parts.js";

const WAITS = "herdr-fold.waits";                  // each agent waiting on you: since when, and Cmd + Shift + U's mark
export const FOLDED = "herdr-fold.machines-folded";       // the machines whose spaces are folded away
const MENDING = "herdr-fold.machines-mending";     // a rebuilt machine forgotten and added again, step by step
const FALLBACK = 60000;            // ms: a repository in view looked at again this often, with the window in front
const SETTLE = 1500;               // ms: a new space waits this long for its place, to show under its checkout at once
const OPENING = 3000;              // ms: a home's stand-in takes no second click while its space is being made

/** @type {Record<string, string>} each machine's home folder as known ("": this computer's) */
let homes = {};
/** @type {Record<string, number>} homeId() → when its stand-in was last clicked */
const opening = {};

/** Whether a space is at its machine's home, by the homes LIST shows (PS: panes()). @param {any[]} list
 * @param {any[]} ps @returns {(s: any) => boolean} */
function homeTest(list, ps) {
  homes = homesSeen({ "": home(), ...homes }, list, ps);
  return (s) => atHome(s, ps, homes);
}

/** Whether SPACE is at its machine's home now (the homes the list shows): no chat first there (chat.js's firstChat).
 * @param {any} space */
export const isHome = (space) => homeTest(spaces(), panes())(space);

/** The machines whose home has no space, of those a terminal can start on now: this computer, and each whose layout
 * is ready. @param {any[]} list @param {(s: any) => boolean} isHome */
function emptyHomes(list, isHome) {
  const known = machines(), local = known.find((m) => !m.name)?.layout;
  return homesEmpty([...(local === "loading" || local === "unavailable" ? [] : [null]),
    ...known.filter((m) => m.name && m.layout === "ready").map((m) => m.name)], list, isHome);
}

/** The spaces as the floating list shows them: by machine, each home first, a stand-in where none is open. */
export function floatSpaces() {
  const list = spaces(), isHome = homeTest(list, panes());
  return withHomes(list, emptyHomes(list, isHome), isHome);
}

/** A terminal opened in MACHINE's home (null: this computer), its space the app's "~": a stand-in's click.
 * @param {string | null} machine */
export function openHome(machine) {
  const id = homeId(machine), now = Date.now();
  if (now - (opening[id] ?? 0) < OPENING) return;
  opening[id] = now;
  command("space.new", machine ? { machine } : { machine: "", folder: home() });
}

/** Ctrl+B, Shift+N, as the TUI's: a folder picked on this Mac, a new space there, its agent started as
 * Spaces' + starts one (newSpace's). */
export async function pickSpace() {
  const folder = await pickFolder({ prompt: "New space" });
  if (folder) await newSpace({ machine: "", folder });
}

/** The waits as the agents are now, written only when they changed; kept while the sidebar is folded too. */
function trackWaits() {
  const known = /** @type {Record<string, any>} */ (shared(WAITS) ?? {});
  const next = nextWaits(known, agents(), Date.now(), focused()?.pane ?? null);
  if (JSON.stringify(next) !== JSON.stringify(known)) setShared(WAITS, next);
}

/** Cmd + Shift + U: the focused pane's agent marked unread, waiting on you again; marked already, unmarked. */
export function markUnread() {
  const pane = focused()?.pane, agent = agents().find((a) => a.pane === pane);
  if (agent) setShared(WAITS, toggleUnread(/** @type {any} */ (shared(WAITS) ?? {}), agent, Date.now()));
}

/** Since when an agent or a chat in each space waits on you. */
export const waitsBySpace = () => spaceWaits(/** @type {any} */ (shared(WAITS) ?? {}), agents(), chatWaits().spaces);

/** The spaces' colors as every app mod keeps them, one given to a new space. */
export function spaceColorsKept() {
  const kept = /** @type {Record<string, string>} */ (shared("space.colors") ?? {}), next = spaceColors(spaces(), kept);
  if (next) setShared("space.colors", next);
  return next ?? kept;
}

/** @typedef {{ id: string, name: string, active: boolean, color: string, tree: boolean, label: string, ahead: number,
 *   behind: number, wait: string | null, home?: boolean, empty?: boolean, machine?: string | null }} Row */
/** @typedef {{ machine: string | null, connected: boolean, state: string, rebuilt: boolean, error: string | null,
 *   busy: boolean, folded: boolean, wait: string | null, since: number | null, rows: Row[],
 *   loading: boolean }} Group */
/** @typedef {import("./logic.js").SpacesItem} Item */

export class SpacesView {
  /** PYTHON: main.js's, core/ on a space's machine. @param {(source: string, args: string[], root: string,
   * on: string | null) => Promise<any>} python */
  constructor(python, cx) {
    this.python = python;
    /** @type {Record<string, any>} placeKey() → its place (core/git.py's; repo with its machine), null: none */
    this.places = {};
    /** @type {Record<string, number>} */
    this.checked = {};
    this.unsure = new Set();           // placeKey()s git could not answer for (a machine away)
    this.pending = new Set();          // placeKey()s to look at next
    /** @type {Record<string, boolean>} pane → an agent working or a program in front of its shell */
    this.busy = {};
    /** @type {Record<string, boolean>} */
    this.ready = {};
    /** @type {Record<string, string>} space → its placeKey() at the last look */
    this.at = {};
    this.watching = new Set();
    this.shown = new Set(spaces().map((s) => s.id));
    /** @type {Record<string, number>} */
    this.born = {};
    /** @type {string | null} */
    this.pressed = null;
    /** @type {string | null} */
    this.over = null;
    /** @type {string | null} the machine head the pointer is on (hovering's): its + shown */
    this.hovered = null;
    /** @type {any[]} hc's machines, with their state */
    this.machines = [];
    /** @type {any} */
    this.ordering = null;
    this.mending = new Set();          // the machines being added again now
    this.said = "";                    // the waits as last drawn: a minute on, drawn again
    this.refreshMachines(cx);
    cx.timer.every(15000, (cx) => this.refreshMachines(cx));
    cx.timer.every(250, (cx) => this.tick(cx));
  }

  tick(cx) {
    const now = Date.now(), list = spaces();
    for (const s of list) if (!this.shown.has(s.id)) this.born[s.id] ??= now;
    const due = this.due(now, list, panes());
    if (due.size) this.look(due, cx);
    trackWaits();
    const said = JSON.stringify(Object.values(waitsBySpace()).map((since) => waited(now - since)));
    if (said !== this.said || list.some((s) => !this.shown.has(s.id)) || this.orderingDue(now)) {
      this.said = said;
      cx.notify();
    }
  }

  /** The places whose git could have changed, as the app's list looks: new ones (a new space, a cd, another active
   * pane where the folder is no repository), where a command or an agent's turn just ended, those on a machine back
   * again, and the shown ones whose FALLBACK is due. @param {number} now @param {any[]} list @param {any[]} ps */
  due(now, list, ps) {
    /** @type {Record<string, string>} */
    const at = {};
    for (const s of list) at[s.id] = placeKey(s, ps, this.places);
    const keys = new Set(Object.values(at).filter((k) => JSON.parse(k)[1]));
    const due = new Set([...keys].filter((k) => !(k in this.places)));
    for (const [id, k] of Object.entries(at)) if (this.at[id] && this.at[id] !== k && keys.has(k)) due.add(k);
    this.at = at;
    const spaceOf = Object.fromEntries(list.flatMap((s) => (s.tabs ?? []).map((tab) => [tab.id, s])));
    /** @type {Record<string, boolean>} */
    const busy = {};
    for (const p of ps) {
      if (!p.terminal || !spaceOf[p.tab]) continue;
      busy[p.pane] = p.status === "working" || !(p.program?.shell || p.program?.agent);
      if (this.busy[p.pane] && !busy[p.pane]) this.sameRepo(at[spaceOf[p.tab].id], keys).forEach((k) => due.add(k));
    }
    this.busy = busy;
    for (const m of machines()) {
      const ready = m.layout === "ready";
      if (ready && this.ready[String(m.name)] === false) {
        for (const k of keys) if (JSON.parse(k)[0] === m.name) due.add(k);
      }
      this.ready[String(m.name)] = ready;
    }
    if (window().active) {
      const folded = new Set(/** @type {any[]} */ (shared(FOLDED) ?? []));
      for (const k of keys) {
        const asks = this.places[k] || this.unsure.has(k);
        if (asks && !folded.has(JSON.parse(k)[0]) && now - (this.checked[k] ?? 0) > FALLBACK) due.add(k);
      }
    }
    return due;
  }

  /** KEY and the other places in its repository (a commit there moves their ahead and behind).
   * @param {string} key @param {Set<string>} keys */
  sameRepo(key, keys) {
    const repo = this.places[key]?.repo;
    return [key, ...(repo ? [...keys].filter((k) => this.places[k]?.repo === repo) : [])];
  }

  refreshMachines(cx) {
    cx.spawn(async (cx) => {
      try {
        const listed = await hc(["machine", "ls", "--json"]);
        if (listed.code === 0) this.machines = (JSON.parse(listed.stdout).machines ?? []).filter((m) => !m.temporary);
      } catch {
        // the core away: the machines as they were
      }
      cx.notify();
    });
  }

  /** Whether MACHINE was rebuilt or replaced: another core answers at its address. @param {any} machine */
  rebuilt(machine) {
    return machine?.state === "unreachable" && /^a different core answers there \("[^"]+"\)$/.test(machine.why ?? "");
  }

  /** A rebuilt MACHINE added again, as the app's own list does it: forgotten, then added the way it was, each step
   * kept, so a quit between them goes on from there. @param {any} machine */
  reconnect(machine, cx) {
    const name = machine.name;
    if (this.mending.has(name)) return;
    this.mending.add(name);
    const keep = (/** @type {any} */ state) => setShared(MENDING, { ...(/** @type {any} */ (shared(MENDING)) ?? {}),
      [name]: state });
    const state = { machine, removed: false, error: null, ...(/** @type {any} */ (shared(MENDING)) ?? {})[name] };
    keep({ ...state, error: null });
    cx.spawn(async (cx) => {
      const ask = async (/** @type {string[]} */ args) => {
        const done = await hc([...args, "--json"]);
        if (done.code === 0) return;
        let error;
        try {
          error = JSON.parse(done.stdout || done.stderr).error?.message;
        } catch {
          // not JSON: its own words
        }
        throw new Error(error || done.stderr || done.stdout || "Couldn't connect.");
      };
      try {
        if (!state.removed) {
          await ask(["machine", "rm", name]);
          keep({ ...state, removed: true });
        }
        await ask(["machine", "add", ...(machine.via ? ["--via", machine.target] : [machine.target]), "--name", name,
          ...(machine.session ? ["--session", machine.session] : []), ...(machine.temporary ? ["--temp"] : [])]);
        setShared(FOLDED, (/** @type {any[]} */ (shared(FOLDED) ?? [])).filter((m) => m !== name));
        const { [name]: _done, ...rest } = /** @type {any} */ (shared(MENDING)) ?? {};
        setShared(MENDING, rest);
      } catch (e) {
        keep({ ...(/** @type {any} */ (shared(MENDING)) ?? {})[name], error: String(e?.message ?? e) });
      } finally {
        this.mending.delete(name);
        this.refreshMachines(cx);
        cx.notify();
      }
    });
    cx.notify();
  }

  /** KEYS' places looked at, one look at a time, each once however often it was asked for meanwhile.
   * @param {Set<string>} keys */
  look(keys, cx) {
    for (const k of keys) this.pending.add(k);
    if (this.looking) return;
    this.looking = true;
    cx.spawn(async (cx) => {
      while (this.pending.size) {
        const next = [...this.pending];
        this.pending.clear();
        for (const key of next) await this.check(key, cx);
      }
      const used = new Set(Object.values(this.places).filter(Boolean).map((g) => JSON.parse(g.repo))
        .filter(([on]) => !on).map(([, repo]) => repo));
      for (const repo of this.watching) if (!used.has(repo)) this.watching.delete(repo);
      this.looking = false;
      cx.notify();
    });
  }

  /** KEY's place (core/git.py place, with the active pane's folder where the space's is no repository): only git's
   * own "no" is kept as none; anything else is asked again later. @param {string} key */
  async check(key, cx) {
    const [on, cwd, active] = JSON.parse(key);
    this.checked[key] = Date.now();
    this.unsure.delete(key);
    try {
      const found = await this.python(GIT, ["place", cwd, ...(active ? [active] : [])], cwd, on);
      this.places[key] = found && { ...found, repo: JSON.stringify([on, found.repo]) };
      if (found && !on) this.watch(found.repo, cx);
    } catch {
      this.places[key] ??= null;
      this.unsure.add(key);
    }
  }

  /** A repository on this Mac looked at again whenever its .git folder changes (a commit, a checkout elsewhere).
   * @param {string} repo */
  watch(repo, cx) {
    if (this.watching.has(repo)) return;
    this.watching.add(repo);
    cx.spawn(async (cx) => {
      try {
        while (this.watching.has(repo)) {
          await watchFolder(repo);
          const mine = JSON.stringify([null, repo]);
          if (this.watching.has(repo)) {
            this.look(new Set(Object.keys(this.places).filter((k) => this.places[k]?.repo === mine)), cx);
          }
        }
      } catch {
        this.watching.delete(repo);
      }
    });
  }

  /** Whether moves made a second ago may be made again: a write can lose to a sync, on machines ready again.
   * @param {number} now */
  orderingDue(now) {
    return Boolean(this.ordering && now - this.ordering.at >= 1000 && this.ordering.machines.every((name) =>
      machines().some((m) => m.name === name && m.layout === "ready")));
  }

  /** Space W's place as known, its folder's while its active pane's is looked at; undefined: neither known yet.
   * @param {any} w @param {any[]} ps */
  placeOf(w, ps) {
    return this.places[placeKey(w, ps, this.places)] ?? this.places[folderKey(w, ps)];
  }

  /** The spaces in order, each machine's home first, each worktree's under its checkout's, as shown; the app's order
   * moved to it (space.move, each move counted in for the next). */
  ordered() {
    const list = spaces(), ps = panes(), now = Date.now(), isHome = homeTest(list, ps);
    const settled = (w) => isHome(w) || this.placeOf(w, ps) !== undefined || now - (this.born[w.id] ??= now) > SETTLE;
    for (const w of list) if (!this.shown.has(w.id) && settled(w)) this.shown.add(w.id);
    const rows = homeFirst(nested(list.map((w) => ({ w, g: this.placeOf(w, ps) ?? null, home: isHome(w) }))),
      (r) => r.home);
    const order = list.map((w) => w.id), target = rows.map((r) => r.w.id);
    const key = JSON.stringify([order, target, machines()]);
    if (order.every((id, i) => id === target[i])) this.ordering = null;
    else if (this.ordering?.key !== key || this.orderingDue(now)) {
      const moved = new Set();
      this.ordering = { key, at: now, machines: [] };
      target.forEach((id, i) => {
        const from = order.indexOf(id);
        if (from === i) return;
        command("space.move", { id, index: i + 1 });
        moved.add(rows[i].w.machine ?? null);
        order.splice(i, 0, order.splice(from, 1)[0]);
      });
      this.ordering.machines = [...moved];
    }
    return rows.filter((r) => this.shown.has(r.w.id));
  }

  /** What the list shows now: the spaces by machine, once another machine is known, each group's head as it is; a
   * machine's home with no space there, a stand-in at its head. */
  model() {
    const rows = this.ordered(), colors = spaceColorsKept(), since = waitsBySpace(), now = Date.now();
    const mending = /** @type {Record<string, any>} */ (shared(MENDING) ?? {});
    const folded = new Set(/** @type {any[]} */ (shared(FOLDED) ?? []));
    const row = ({ w, g, tree, home }) => ({ id: w.id, name: w.name, active: w.active, color: spaceColor(w, colors),
      tree, label: g ? placeLabel(g, tree, w.name) : "", ahead: g?.ahead ?? 0, behind: g?.behind ?? 0,
      wait: since[w.id] ? waited(now - since[w.id]) : null, home });
    const empty = new Set(emptyHomes(spaces(), homeTest(spaces(), panes())));
    const standIn = (m) => ({ id: homeId(m), name: HOME_NAME, active: false, color: "ansi6", tree: false, label: "",
      ahead: 0, behind: 0, wait: null, home: true, empty: true, machine: m });
    const loading = (m) => {
      const doc = machines().find((k) => k.name === m)?.layout;
      return doc === "loading" || (!doc && this.machines.some((k) => k.name === m && k.state === "connected")) ||
        spaces().some((s) => (s.machine ?? null) === m && !this.shown.has(s.id));
    };
    const remote = [...new Set([...rows.map((r) => r.w.machine).filter(Boolean), ...this.machines.map((m) => m.name),
      ...Object.keys(mending)])].sort();
    return (remote.length ? [null, ...remote] : [null]).map((m) => {
      const mine = rows.filter((r) => (r.w.machine ?? null) === m), repair = mending[m ?? ""];
      const machine = this.machines.find((k) => k.name === m) ?? repair?.machine;
      const waits = mine.map((r) => since[r.w.id]).filter(Boolean);
      return { machine: m, connected: !m || machine?.state === "connected", state: machine?.state ?? "asleep",
        rebuilt: this.rebuilt(machine) || Boolean(repair), error: repair?.error ?? null,
        busy: this.mending.has(String(m)), folded: folded.has(m), loading: loading(m),
        rows: [...(empty.has(m) && (!m || machine?.state === "connected") ? [standIn(m)] : []), ...mine.map(row)],
        wait: waits.length ? waited(now - Math.min(...waits)) : null, since: waits.length ? Math.min(...waits) : null };
    });
  }

  render(t) {
    return this.draw(t, this.model());
  }

  /** GROUPS drawn as the app's own list: its head and +, then (once a machine is not this computer) each machine's
   * head and its spaces, by network once they are many (spacesItems), with what the networks said (SEEN) and the
   * networks FOLDED. @param {Group[]} groups @param {any} [seen] @param {any} [folded] */
  draw(t, groups, seen = shared(NETWORKS_SEEN) ?? null, folded = shared(NETWORKS_FOLDED)) {
    const items = spacesItems(groups, seen, Array.isArray(folded) ? folded : []);
    return v_flex().size_full().min_h(0).bg(t.chrome).text_size(13)               // the left sidebar's level
      .child(listHead(t, "Spaces", h_flex().gap(GAP).child(iconButton(t, "spaces-machines", "waypoints", "Machines",
        () => openMachines())).child(iconButton(t, "space-new", "plus", "New space",
        () => void newSpace().catch(() => {})))))
      .child(v_flex().id("spaces-list").flex_1().min_h(0).px(8).pb(LIST.foot).overflow_y_scrollbar()
        .on_mouse_up("left", (_e, cx) => {
          this.pressed = null;
          cx.notify();
        })
        .children(items.map((item) => item.kind === "network" ? this.networkHead(t, item)
          : item.kind === "add" ? this.addRow(t, item, seen?.setup ?? null)
            : item.kind === "machine" ? this.head(t, item)
              : item.kind === "row" ? this.row(t, item.row, item.group.rows, item.indent)
                : item.kind === "loading" ? this.loadingRow(t, item.group, item.indent)
                  : this.emptyRow(t, item.group, item.indent))));
  }

  /** A network's head (machines.html's .nhead), 8 under what is above it: its mark, name, state while it is not on
   * (its tip the ladder's sentence), folded its machines' longest wait, their count, its chevron folding them away.
   * @param {Item} item */
  networkHead(t, item) {
    const quiet = item.said?.tone === "dim";
    return h_flex().id(`network-${item.network}`).h(LIST.machine).flex_none().mt(LIST.gap).px(8).gap(6).items_center()
      .rounded(6).text_size(12).text_color(t.muted).cursor_pointer().hover((s) => s.bg(t.hover))
      .when(Boolean(item.tip), (e) => e.tooltip(String(item.tip)))
      .on_click((_e, cx) => {
        const folded = new Set(/** @type {any[]} */ (shared(NETWORKS_FOLDED) ?? []));
        if (!folded.delete(item.network)) folded.add(item.network);
        setShared(NETWORKS_FOLDED, [...folded]);
        cx.notify();
      })
      .child(networkMark(t, item.network, CENTRED.headMark[1]))
      .child(div().min_w(0).truncate().font_semibold().when(quiet, (e) => e.text_color(t.dim)).child(item.name))
      .when(Boolean(item.said), (e) => e.child(div().flex_none().text_size(11)
        .text_color(quiet ? t.dim : t.ansi3).child(String(item.said?.word))))
      .when(item.folded && Boolean(item.wait), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
        .child(String(item.wait))))
      .child(div().flex_1())
      .child(div().flex_none().text_size(11).text_color(t.dim).child(String(item.count)))
      .child(icon(item.folded ? "chevron-right" : "chevron-down", CENTRED.headChevron[1]).text_color(t.dim));
  }

  /** A network with none of its machines added yet: how many it offers, its tip naming them; a click asks about each
   * (the package's machines.sh, SETUP its folder) in a terminal tab on this Mac. @param {Item} item
   * @param {string | null} setup */
  addRow(t, item, setup) {
    const { words, tip } = toAddWords(item.network, item.offered);
    return h_flex().id(`network-add-${item.network}`).h(LIST.tree).flex_none().pl(8 + item.indent).pr(8).gap(6)
      .items_center().rounded(6).text_size(12).text_color(t.dim).cursor_pointer()
      .hover((s) => s.bg(t.hover).text_color(t.foreground)).tooltip(tip)
      .on_click(() => setup && this.ask(item.network, setup))
      .child(icon("plus", CENTRED.headAddIcon[1])).child(words);
  }

  /** NETWORK's machines asked about, ./machines.sh in the package's FOLDER, in a terminal tab on this Mac.
   * @param {string} network @param {string} folder */
  ask(network, folder) {
    const [name, args] = importCommand(network, folder, spaces());
    command(name, args);
  }

  /** A machine's head: its icon, network's mark or corner (item.lead), its name, how it is, + for a space there (shown
   * on hover), its dot, its chevron folding its spaces; folded, its longest wait; its tip the way it is reached where
   * its group does not say it. @param {Item} item */
  head(t, item) {
    const g = item.group, m = g.machine, id = m ?? "local";
    return h_flex().id(`machine-${id}`).h(LIST.machine).flex_none().when(item.gap, (e) => e.mt(LIST.gap))
      .pl(8 + item.indent).pr(8).gap(6).items_center().rounded(6).text_size(11).text_color(t.dim).cursor_pointer()
      .hover((s) => s.bg(t.hover)).on_hover(hovering(this, id))
      .when(Boolean(item.tip), (e) => e.tooltip(String(item.tip)))
      .on_click((_e, cx) => {
        const folded = new Set(/** @type {any[]} */ (shared(FOLDED) ?? []));
        if (folded.has(m)) folded.delete(m);
        else folded.add(m);
        setShared(FOLDED, [...folded]);
        cx.notify();
      })
      .when(item.lead === "monitor" || item.lead === "server", (e) => e.child(icon(item.lead === "server" ? "server"
        : "monitor", CENTRED.headMark[1])))
      .when(item.lead === "mark", (e) => e.child(networkMark(t, item.network, CENTRED.headMark[1])))
      .when(item.lead === "corner", (e) => e.child(icon("corner-down-right", CENTRED.headCorner[1])))
      .child(div().flex_1().truncate().child(m ?? "This computer"))
      .when(!g.connected && !g.rebuilt, (e) => e.child(div().flex_none().child(g.state.replace(/_/g, " "))))
      .when(g.rebuilt, (e) => e.child(h_flex().flex_none().gap(4).items_center()
        .child(div().max_w(140).truncate().child(g.error || "rebuilt"))
        .child(div().id(`machine-connect-${id}`).text_color(g.error ? t.blocked ?? t.ansi1 : t.muted)
          .hover((s) => s.text_color(t.foreground))
          .tooltip(g.error || "This machine was rebuilt or replaced. Click to connect to the new one.")
          .on_click((_e, cx) => {
            cx.stop_propagation();
            this.reconnect(this.machines.find((k) => k.name === m) ?? (/** @type {any} */ (shared(MENDING)) ?? {})[
              String(m)]?.machine, cx);
          })
          .child(g.busy ? "Connecting…" : "Connect"))))
      .when(g.folded && Boolean(g.wait), (e) => e.child(div().flex_none().text_color(t.ansi3).child(g.wait)))
      .when(g.connected, (e) => e.child(div().id(`machine-add-${id}`).size(CENTRED.headAdd[1]).flex_none().flex()
        .items_center().justify_center().rounded(4).when(this.hovered !== id, (s) => s.invisible())
        .hover((s) => s.bg(t.hover).text_color(t.foreground)).tooltip("New space there")
        .on_click((_e, cx) => {
          cx.stop_propagation();
          newSpace({ machine: m ?? "" }).catch(() => {});
        }).child(icon("plus", CENTRED.headAddIcon[1]))))
      .child(div().size(CENTRED.headDot[1]).rounded_full().flex_none().bg(g.connected ? t.ansi2 : t.dim))
      .child(icon(g.folded ? "chevron-right" : "chevron-down", CENTRED.headChevron[1]));
  }

  /** A space's row: avatar (a worktree its branch under its checkout), name, branch, how far from upstream, its wait,
   * INDENT in; its highlight 2 in, a drag's line between rows; a right click, the app's menu. A home stays first; with
   * nothing open, outlined and dim, a click opens a terminal. @param {Row} r @param {Row[]} rows */
  row(t, r, rows, indent = 0) {
    const from = rows.findIndex((x) => x.id === this.pressed), at = rows.findIndex((x) => x.id === r.id);
    // a drag stays within its machine's spaces, and off its home
    const mine = () => !r.home && rows.some((x) => x.id === this.pressed && !x.home);
    return v_flex().relative().id(`space-${r.id}`).py(2).h(r.tree ? LIST.tree : LIST.row).flex_none()
      .when(Boolean(r.empty), (e) => e.tooltip("Nothing open in the home folder. Click to open a terminal there."))
      .when(this.pressed === r.id && this.over !== r.id && !r.home, (e) => e.opacity(0.5))
      .when(this.pressed !== null && this.over === r.id && this.pressed !== r.id, (e) => e.child(div().absolute()
        .left(8).right(8).h(2).rounded_full().bg(t.accent).when(from < at, (line) => line.bottom(-1))
        .when(from > at, (line) => line.top(-1))))
      .on_mouse_down("left", () => {
        this.pressed = this.over = r.id;
      })
      .on_mouse_move((_e, cx) => {
        const over = mine() || this.pressed === r.id ? r.id : null;
        if (this.pressed !== null && this.over !== over) {
          this.over = over;
          cx.notify();
        }
      })
      .on_mouse_up("left", (_e, cx) => {
        const pressed = this.pressed, over = this.over;
        this.pressed = this.over = null;
        if (pressed !== null && over === r.id && pressed !== r.id) {
          const index = spaces().findIndex((s) => s.id === r.id);
          if (index !== -1) command("space.move", { id: pressed, index: index + 1 });
        } else if (pressed === r.id && r.empty) openHome(r.machine ?? null);
        else if (pressed === r.id) command("space.select", { id: r.id });
        cx.notify();
      })
      .on_mouse_down("right", () => r.empty || openOverlay({ mod: "menu", kind: "popup", width: 200, height: 260,
        props: { tab: "space", target: { id: r.id } } }))
      .child(v_flex().flex_1().pl(8 + indent).pr(8).justify_center().rounded(8).when(r.active, (e) => e.bg(t.selected))
        .when(!r.active, (e) => e.hover((s) => s.bg(t.hover)))
        .child(h_flex().gap(8).items_center()
          .when(r.tree, (e) => e.pl(18 + 8).child(icon("git-branch", 13).text_color(t.dim)))  // under its checkout
          .when(!r.tree && !r.empty, (e) => e.child(h_flex().size(18).flex_none().rounded(4).bg(avatarFill(r.color, t))
            .items_center().justify_center().text_size(11).font_bold().text_color("#ffffff")
            .child([...r.name][0]?.toUpperCase() ?? "?")))
          .when(Boolean(r.empty), (e) => e.child(h_flex().size(18).flex_none().rounded(4).border(1)
            .border_color(t.border).items_center().justify_center().text_size(11).font_bold().text_color(t.dim)
            .child(HOME_NAME)))
          .child(div().flex_shrink(0).max_w(150).truncate().text_color(r.empty ? t.dim : t.foreground)
            .child(spaceLabel(r.name)))
          .child(h_flex().flex_1().min_w(0).gap(6).justify_end().items_center().text_size(11).text_color(t.dim)
            .when(Boolean(r.label), (e) => e.child(div().min_w(0).truncate().child(r.label)))
            .when(r.ahead > 0, (e) => e.child(div().flex_none().text_color(t.ansi2).child(`↑${r.ahead}`)))
            .when(r.behind > 0, (e) => e.child(div().flex_none().text_color(t.ansi1).child(`↓${r.behind}`)))
            .when(Boolean(r.wait), (e) => e.child(div().flex_none().text_color(t.ansi3).child(r.wait))))));
  }

  /** @param {Group} g */
  loadingRow(t, g, indent = 0) {
    return div().id(`machine-loading-${g.machine ?? "local"}`).h(LIST.tree).flex_none().pl(8 + indent).pr(8).flex()
      .items_center().text_size(12).text_color(t.dim).child("Loading…");
  }

  /** A machine with no space yet: one made there by a click. @param {Group} g */
  emptyRow(t, g, indent = 0) {
    return h_flex().id(`machine-new-${g.machine ?? "local"}`).h(LIST.tree).flex_none().pl(8 + indent).pr(8).gap(6)
      .items_center().rounded(6).text_size(12).text_color(t.dim).cursor_pointer()
      .hover((s) => s.bg(t.hover).text_color(t.foreground))
      .on_click(() => void newSpace({ machine: g.machine ?? "" }).catch(() => {}))
      .child(icon("plus", 12)).child("New space there");
  }
}
