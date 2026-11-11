// @ts-check
// The Spaces list where the app's own was, drawn as it draws one: by machine, a worktree under its checkout, each
// space's branch, dragged into order, the app's menu on a right click; and how long agents wait, as the TUI's.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { agents, focused, hc, layout, machines, openOverlay, panes, setShared, shared, spaces, watchFolder, window,
  run as command } from "herdr";
import { GIT } from "./helper.js";
import { avatarFill, folderKey, headed, LIST, listBody, listHeight, nested, nextWaits, placeKey, placeLabel,
  spaceColors, spaceWaits, toggleUnread, hovering, waited, withMax } from "./logic.js";
import { icon, iconButton, listHead } from "./parts.js";

const WAITS = "herdr-fold.waits";                  // each agent waiting on you: since when, and Cmd + Shift + U's mark
const FOLDED = "herdr-fold.machines-folded";       // the machines whose spaces are folded away
const MENDING = "herdr-fold.machines-mending";     // a rebuilt machine forgotten and added again, step by step
const FALLBACK = 60000;            // ms: a repository in view looked at again this often, with the window in front
const SETTLE = 1500;               // ms: a new space waits this long for its place, to show under its checkout at once

/** The waits as the agents are now, written only when they changed; kept while the list is folded away too. */
export function trackWaits() {
  const known = /** @type {Record<string, any>} */ (shared(WAITS) ?? {});
  const next = nextWaits(known, agents(), Date.now(), focused()?.pane ?? null);
  if (JSON.stringify(next) !== JSON.stringify(known)) setShared(WAITS, next);
}

/** Cmd + Shift + U: the focused pane's agent marked unread, waiting on you again; marked already, unmarked. */
export function markUnread() {
  const pane = focused()?.pane, agent = agents().find((a) => a.pane === pane);
  if (agent) setShared(WAITS, toggleUnread(/** @type {any} */ (shared(WAITS) ?? {}), agent, Date.now()));
}

/** Since when an agent in each space waits on you. */
export const waitsBySpace = () => spaceWaits(/** @type {any} */ (shared(WAITS) ?? {}), agents());

/** The spaces' colors as every app mod keeps them, one given to a new space. */
export function spaceColorsKept() {
  const kept = /** @type {Record<string, string>} */ (shared("space.colors") ?? {}), next = spaceColors(spaces(), kept);
  if (next) setShared("space.colors", next);
  return next ?? kept;
}

/** @typedef {{ id: string, name: string, active: boolean, color: string, tree: boolean, label: string, ahead: number,
 *   behind: number, wait: string | null }} Row */
/** @typedef {{ machine: string | null, connected: boolean, state: string, rebuilt: boolean, error: string | null,
 *   busy: boolean, folded: boolean, wait: string | null, rows: Row[], loading: boolean }} Group */

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

  /** The spaces in order, each worktree's under its checkout's, as shown; the app's order moved to it (space.move,
   * each move counted in for the next). */
  ordered() {
    const list = spaces(), ps = panes(), now = Date.now();
    const settled = (w) => this.placeOf(w, ps) !== undefined || now - (this.born[w.id] ??= now) > SETTLE;
    for (const w of list) if (!this.shown.has(w.id) && settled(w)) this.shown.add(w.id);
    const rows = nested(list.map((w) => ({ w, g: this.placeOf(w, ps) ?? null })));
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

  /** What the list shows now: the spaces by machine, once another machine is known, each group's head as it is. */
  model() {
    const rows = this.ordered(), colors = spaceColorsKept(), since = waitsBySpace(), now = Date.now();
    const mending = /** @type {Record<string, any>} */ (shared(MENDING) ?? {});
    const folded = new Set(/** @type {any[]} */ (shared(FOLDED) ?? []));
    const row = ({ w, g, tree }) => ({ id: w.id, name: w.name, active: w.active, color: colors[w.id] ?? "ansi6",
      tree, label: g ? placeLabel(g, tree, w.name) : "", ahead: g?.ahead ?? 0, behind: g?.behind ?? 0,
      wait: since[w.id] ? waited(now - since[w.id]) : null });
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
        busy: this.mending.has(String(m)), folded: folded.has(m), rows: mine.map(row), loading: loading(m),
        wait: waits.length ? waited(now - Math.min(...waits)) : null };
    });
  }

  render(t, cx) {
    const groups = this.model(), tall = listHeight(groups);
    if (withMax(layout(), "spaces", tall).changed && !this.capping) {
      this.capping = true;
      cx.timer.after(0, () => {                   // the layout as it is then: a fold or a resize meanwhile stays
        this.capping = false;
        const capped = withMax(layout(), "spaces", tall);
        if (capped.changed) command("layout.set", { layout: capped.tree });
      });
    }
    return this.draw(t, groups);
  }

  /** GROUPS drawn as the app's own list: its head and +, then each machine's head (once one is not this computer)
   * and its spaces. @param {Group[]} groups */
  draw(t, groups) {
    const heads = headed(groups);
    return v_flex().size_full().min_h(0).bg(t.chrome ?? t.background).text_size(13)
      .child(listHead(t, "Spaces", iconButton(t, "space-new", "plus", "New space", () => command("space.new", {}))))
      .child(v_flex().id("spaces-list").flex_1().min_h(0).px(8).pb(LIST.foot).overflow_y_scrollbar()
        .on_mouse_up("left", (_e, cx) => {
          this.pressed = null;
          cx.notify();
        })
        .children(groups.flatMap((g) => [...(heads ? [this.head(t, g)] : []), ...{ none: [],
          rows: g.rows.map((r) => this.row(t, r, g.rows)), loading: [this.loadingRow(t, g)],
          empty: [this.emptyRow(t, g)] }[listBody(g, heads)]])));
  }

  /** A machine's head: its name, how it is, + for a space there (its place kept, shown on hover: the list's head has
   * one too), its dot, its chevron folding its spaces; folded, its longest wait. @param {Group} g */
  head(t, g) {
    const m = g.machine, id = m ?? "local";
    return h_flex().id(`machine-${id}`).h(LIST.machine).flex_none().px(8).gap(6).items_center().text_size(11)
      .text_color(t.dim).cursor_pointer().hover((s) => s.bg(t.hover)).on_hover(hovering(this, id))
      .on_click((_e, cx) => {
        const folded = new Set(/** @type {any[]} */ (shared(FOLDED) ?? []));
        if (folded.has(m)) folded.delete(m);
        else folded.add(m);
        setShared(FOLDED, [...folded]);
        cx.notify();
      })
      .child(icon(m ? "server" : "monitor", 13).flex_none())
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
      .when(g.connected, (e) => e.child(div().id(`machine-add-${id}`).size(18).flex_none().flex().items_center()
        .justify_center().rounded(4).when(this.hovered !== id, (s) => s.invisible())
        .hover((s) => s.bg(t.hover).text_color(t.foreground)).tooltip("New space there")
        .on_click((_e, cx) => {
          cx.stop_propagation();
          command("space.new", { machine: m ?? "" });
        }).child(icon("plus", 12))))
      .child(div().size(6).rounded_full().flex_none().bg(g.connected ? t.ansi2 : t.dim))
      .child(icon(g.folded ? "chevron-right" : "chevron-down", 11).flex_none());
  }

  /** A space's row: avatar (a worktree its branch under its checkout), name, branch, how far from its upstream, how
   * long it waits on you; its highlight 2 in from its edges, a drag's line in the gap between two; a right click, the
   * app's menu. @param {Row} r @param {Row[]} rows its group's */
  row(t, r, rows) {
    const from = rows.findIndex((x) => x.id === this.pressed), at = rows.findIndex((x) => x.id === r.id);
    const mine = () => rows.some((x) => x.id === this.pressed);        // a drag stays within its machine's spaces
    return v_flex().relative().id(`space-${r.id}`).py(2).h(r.tree ? LIST.tree : LIST.row).flex_none()
      .when(this.pressed === r.id && this.over !== r.id, (e) => e.opacity(0.5))
      .when(this.pressed !== null && this.over === r.id && this.pressed !== r.id, (e) => e.child(div().absolute()
        .left(8).right(8).h(2).rounded_full().bg(t.accent).when(from < at, (line) => line.bottom(-1))
        .when(from > at, (line) => line.top(-1))))
      .on_mouse_down("left", () => {
        this.pressed = this.over = r.id;
      })
      .on_mouse_move((_e, cx) => {
        const over = mine() ? r.id : null;
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
        } else if (pressed === r.id) command("space.select", { id: r.id });
        cx.notify();
      })
      .on_mouse_down("right", () => openOverlay({ mod: "menu", kind: "popup", width: 200, height: 260,
        props: { tab: "space", target: { id: r.id } } }))
      .child(v_flex().flex_1().px(8).justify_center().rounded(8).when(r.active, (e) => e.bg(t.selected))
        .when(!r.active, (e) => e.hover((s) => s.bg(t.hover)))
        .child(h_flex().gap(8).items_center()
          .when(r.tree, (e) => e.pl(18 + 8).child(icon("git-branch", 13).text_color(t.dim)))  // under its checkout
          .when(!r.tree, (e) => e.child(h_flex().size(18).flex_none().rounded(4).bg(avatarFill(r.color, t))
            .items_center().justify_center().text_size(11).font_bold().text_color("#ffffff")
            .child([...r.name][0]?.toUpperCase() ?? "?")))
          .child(div().flex_shrink(0).max_w(150).truncate().text_color(t.foreground).child(r.name))
          .child(h_flex().flex_1().min_w(0).gap(6).justify_end().items_center().text_size(11).text_color(t.dim)
            .when(Boolean(r.label), (e) => e.child(div().min_w(0).truncate().child(r.label)))
            .when(r.ahead > 0, (e) => e.child(div().flex_none().text_color(t.ansi2).child(`↑${r.ahead}`)))
            .when(r.behind > 0, (e) => e.child(div().flex_none().text_color(t.ansi1).child(`↓${r.behind}`)))
            .when(Boolean(r.wait), (e) => e.child(div().flex_none().text_color(t.ansi3).child(r.wait))))));
  }

  /** @param {Group} g */
  loadingRow(t, g) {
    return div().id(`machine-loading-${g.machine ?? "local"}`).h(LIST.tree).flex_none().px(8).flex().items_center()
      .text_size(12).text_color(t.dim).child("Loading…");
  }

  /** A machine with no space yet: one made there by a click. @param {Group} g */
  emptyRow(t, g) {
    return h_flex().id(`machine-new-${g.machine ?? "local"}`).h(LIST.tree).flex_none().px(8).gap(6).items_center()
      .rounded(6).text_size(12).text_color(t.dim).cursor_pointer().hover((s) => s.bg(t.hover).text_color(t.foreground))
      .on_click(() => command("space.new", { machine: g.machine ?? "" }))
      .child(icon("plus", 12)).child("New space there");
  }
}
