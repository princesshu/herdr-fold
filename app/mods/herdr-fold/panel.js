// @ts-check
// The right panel as the TUI's sidebar: its views' text tabs, then one view at a time, or the Chats list in its
// place, and the tab's terminal at its foot; folded, a rail of icons. Chats and More are the tab bar's (tabs.js).
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { home, layout, notify, openOverlay, panes, setShared, shared, spaces, watchFolder, run as command }
  from "herdr";
import { UPDATE } from "./helper.js";
import { BOTTOM_PX, bottomPx, bottomShown, bottomToggle, chatsToggle, chosenFor, columnToggle, dockRest, dragPx,
  fitFloatPx,
  FLOAT_GRIP, floatMax, floatMin, foldCommands, floating, floatTop, floatX, keepFloat, railFloatPx, hideCommands,
  keepChosen, panelChoices, PANEL_NAMES, PANEL_PX, panelPx, panelRailed, panelShown, pickCommands, repoTold, restAt,
  SETTLE, shownPanels, shownView, TAB_COUNT, TAB_GAP, TAB_H, tabFit, TAB_IN, TABS_PAD, TABS_SIDE, CHATS_BLOCK, DOCK,
  find, restoreCommands, updateNotice } from "./logic.js";
import { badge, icon, iconButton, iconTab } from "./parts.js";
import { agentHere, agentMark, problemsHere, programs } from "./agent.js";
import { AGENTS_ASK, AGENTS_TAB, agentsTab, askAgents } from "./graph.js";
import { AGENT_ASK, AGENT_CHOSEN, keepAgent, toneColor } from "./layers.js";
import { OPENED } from "./chats.js";
import { openSettings, UPDATES } from "./settings.js";
import { floatPanel, RAIL_FLOAT, shutFloat } from "./sidebar.js";

export const TABS = "herdr-fold.tabs";        // what the row and the rail show of the repository: { github, changed }
export const SUMMON = "herdr-fold.summon";    // a key's ask for a view: { view, command, at }, the tab bar's
const KEPT = "herdr-fold.panel-width";        // the right panel's width while open, which its rail opens to again
const CHOSEN = "herdr-fold.dock-view";        // each space's view, by its id, shown again once it can (Issues)
const BOTTOM_KEPT = "herdr-fold.terminal-px";  // the terminal's height under the centre, as last dragged
const BOTTOM_SHOWN = "herdr-fold.terminal-shown";      // whether it shows there, as the rail's Terminal left it
const FLOAT_KEPT = "herdr-fold.float-heights";        // each view's float beside the rail, as high as last dragged
const RAIL_PX = "herdr-fold.rail-px";         // the folded rail's height, which a float's tallest follows
const DRAG_SLACK = 48;                        // px under the grip while it is dragged: the pointer stays on the float
/** @type {[string, import("./icons.js").IconName, string][]} the rail's panels: its id, its icon, its label */
const RAILED = [["files", "files", "Files"], ["search", "search", "Search"], ["changes", "git-branch", "Changes"],
  ["issues", "circle-dot", "Issues"], ["agent", "bot", "Agent"], ["terminal", "square-terminal", "Terminal"]];
/** @type {Map<string, number>} each tab's width as last drawn (its words, Changes' count), which tabFit fits by */
const TAB_PX = new Map();
/** @type {Record<string, { px: number | null, from: number | null, pending: number | null }>} each side's width as
 * the tab bar last saw it, the width it last came to rest at (null: none yet), the one it was last set to (restAt) */
const RESTS = { dock: { px: null, from: null, pending: null }, side: { px: null, from: null, pending: null } };

/** The space shown's id, or null. */
const spaceShown = () => spaces().find((s) => s.active)?.id ?? null;

/** The view the space shown chose last, Files while it chose none; shown again once it can (Issues off GitHub
 * meanwhile). @returns {string} */
export const chosenView = () => chosenFor(shared(CHOSEN), spaceShown());

/** PANEL picked, by its button or its key: the space's choice from now on (the spaces gone forgotten), shown, the
 * dock opened. @param {string} panel */
function pickPanel(panel) {
  const space = spaceShown();
  if (space && chosenFor(shared(CHOSEN), space) !== panel) {
    setShared(CHOSEN, keepChosen(shared(CHOSEN), space, panel, new Set(spaces().map((s) => s.id))));
  }
  runPanel(pickCommands(layout(), panel, { github: tabsState().github, kept: keptWidth() }));
}

/** Whether the Chats list shows in the dock, in the view's place. */
export const chatsShown = () => find(layout(), DOCK)?.active === CHATS_BLOCK;

/** Chats' button, Cmd+Shift+R, Esc in its list, a chat opened: its list in the view's place (its filter taking the
 * keys), the dock opened from its rail; again, the view back, as the TUI's. With SPACE (a chat's clock: its folder's
 * group) the list is shown, never put away, that group open and scrolled to. @param {{ space?: string | null }} [to] */
export function toggleChats({ space = null } = {}) {
  const shown = chatsShown();
  if (!shown || space) setShared(OPENED, { at: Date.now(), space });
  if (!shown || !space) runPanel(chatsToggle(layout(), tabsState().github, chosenView(), keptWidth()));
}

/** The tab bar's Chats, Cmd+Shift+R or a chat's clock (TO: its group): the list in the dock's view place and back
 * (toggleChats); the dock a rail, the list floating beside it, as a rail's view floats, and closed again (a clock only
 * shows it). @param {{ space?: string | null }} [to] */
export function askChats(to = {}) {
  if (dockOpen()) return toggleChats(to);
  if (!to.space && floatingView() === "chats") return void shutFloat(RAIL_FLOAT);     // ✦ lit: closes it, as a rail's
  if (to.space) setShared(OPENED, { at: Date.now(), space: to.space });
  openRail("chats", null);
}

/** The shown space's Agents tab (usage.html's, one a space) shown, made where it has none, and told what to show
 * (ASK): a NODE chosen in its graph (an Agent panel's row), the conversation it is read with (SESSION).
 * @param {{ node?: string, session?: string | null }} [ask] */
export function openAgents(ask = {}) {
  const all = spaces(), space = all.find((s) => s.active);
  if (!space) return;
  setShared(AGENTS_ASK, askAgents(shared(AGENTS_ASK), space.id, ask, new Set(all.map((s) => s.id)), Date.now()));
  const tab = agentsTab(space, panes());
  if (tab) return void command("tab.select", { id: tab.id });
  command("tab.new", { name: AGENTS_TAB, mod: "herdr-fold", props: { part: "agents", space: space.id } });
}

/** @typedef {{ shown: string | null, views: string[], changed: number, opened?: boolean, px?: number,
 * hovered?: string | null, agent?: any, problems?: { tone: string, said: string } | null }} Tabs */

/** View ID's tab: MARK (Agent's: its agent's icon) before its NAME, Changes' COUNT after it, Agent's DOT (a color)
 * while its setup has a problem, as a tab's state dot; SHOWN on the raised pill in the text's color, else muted, the
 * hover's under the pointer (HOVERED: drawn so); its width kept for tabFit as drawn. @param {string} id */
const viewTab = (t, id, { shown, count, hovered, pick, mark = null, dot = null, tip = null }) => h_flex()
  .id(`dock-${id}`)
  .h(TAB_H).px(TAB_IN).gap(6).flex_none().items_center().rounded(8).text_size(13).cursor_pointer().whitespace_nowrap()
  .text_color(shown || hovered ? t.foreground : t.muted).when(shown || hovered, (e) => e.bg(hovered ? t.hover
    : t.raised)).hover((s) => s.bg(t.hover).text_color(t.foreground)).on_click(() => pick(id))
  .on_size_change((size, cx) => {
    if (TAB_PX.get(id) === size.width) return;
    TAB_PX.set(id, size.width);
    cx.notify();
  })
  .when(Boolean(mark), (e) => e.child(mark))
  .child(PANEL_NAMES[/** @type {keyof typeof PANEL_NAMES} */ (id)])
  .when(count > 0, (e) => e.child(badge(t, count, TAB_COUNT, 11)))
  .when(Boolean(dot), (e) => e.child(div().size(6).flex_none().rounded_full().bg(String(dot))).tooltip(String(tip)));

/** The dock's text tabs atop its card: VIEWS by name, SHOWN's raised (none while the Chats list is OPENED), Changes'
 * count (CHANGED) after its name, Agent wearing its AGENT's icon (none known: Lucide's bot) and, while its setup has
 * PROBLEMS, the worst one's dot; as many as a card PX wide holds (tabFit). @param {Tabs} r @param {any} acts */
export function dockTabs(t, { shown, views, changed, opened = false, px = PANEL_PX, hovered = null, agent = null,
  problems = null }, acts) {
  const lit = opened ? null : shown;
  const { tabs } = tabFit(px, views.map((id) => [id, TAB_PX.get(id) ?? 0]), lit);
  return h_flex().id("dock-head").size_full().py(TABS_PAD).px(TABS_SIDE).gap(TAB_GAP).items_center()
    .overflow_hidden().border_b(1).border_color(t.border)
    .children(tabs.map((id) => viewTab(t, id, { shown: id === lit, count: id === "changes" ? changed : 0,
      hovered: id === hovered, pick: acts.pick,
      mark: id === "agent" ? agentMark(agent, 14) ?? icon("bot") : null,
      ...(id === "agent" && problems ? { dot: toneColor(t, problems.tone), tip: problems.said } : {}) })));
}

/** The dock's tabs as the layout shows them now: the view the space chose, the Chats list over it while it shows,
 * Agent with the icon of the agent its panel shows here. */
export function liveDockTabs(t, cx) {
  const root = layout(), { github, changed } = tabsState();
  return dockTabs(t, { shown: shownView(root, github, chosenView()), views: shownPanels(root, github), changed,
    opened: chatsShown(), px: panelPx(root) ?? PANEL_PX, agent: programs(cx)[agentHere().agent] ?? null,
    problems: problemsHere() },
  { pick: (/** @type {string} */ panel) => pickPanel(panel) });
}

/** More's menu in MENUS under its button (BOUNDS): CHATS' own choice first while Chats shows (Show archived), the
 * views with their ✓, then About herdr-fold (Settings at About; Settings itself is the sidebar's and Cmd+,'s).
 * @param {import("./menus.js").Menus} menus @param {any} bounds @param {import("./menus.js").Item | null} [chats] */
export function openMore(menus, bounds, chats = null) {
  const root = layout(), { github } = tabsState();
  const panels = panelChoices(root, github).map(({ panel, label, on, off }) => ({ label, on, off,
    act: () => runPanel(hideCommands(layout(), panel, on, tabsState().github, chosenView())) }));
  menus.open([...(chats ? [chats, null] : []), ...panels, null,
    { label: "About herdr-fold", act: () => openSettings("about") }], bounds);
}

/** What the row and the rail show (TABS): whether the repository is on GitHub, its changed files' count. */
export function tabsState() {
  const told = /** @type {{ github?: boolean, changed?: number } | null} */ (shared(TABS)) ?? {};
  return { github: Boolean(told.github), changed: told.changed ?? 0 };
}

/** TOLD (a repository looked at) as the row and the rail show it, written only when it changed.
 * @param {{ github: boolean, changed: number }} told */
export function tell(told) {
  if (JSON.stringify(shared(TABS)) !== JSON.stringify(told)) setShared(TABS, told);
}

/** The focused folder's repository as the row and the rail show it, looked at by the tab bar, which always shows: a
 * view copy starts only once it first shows, so with Files shown no other would tell Changes' count nor Issues.
 * ASK: main.js's git and core/git.py there (logic.js's repoTold). */
export class RepoLook {
  constructor(ask) {
    this.ask = ask;
    /** @type {Map<string, boolean>} each repository's GitHub answer */
    this.known = new Map();
    /** @type {{ cwd: string | null, on: string | null } | null} the place looked at, and followFolder's holder */
    this.here = null;
    this.key = null; this.root = null; this.on = null; this.watched = null; this.busy = false; this.again = false;
  }

  /** From the tab bar's render: HERE looked at once it is another place than the last. */
  follow(here, cx) {
    if (JSON.stringify(here) !== this.key) this.look(here, cx);
  }

  /** HERE looked at (one look at a time, the latest place after it), told, and its folder followed. */
  look(here, cx) {
    Object.assign(this, { here, key: JSON.stringify(here) });
    if (this.busy) return void (this.again = true);
    const key = this.key;
    this.busy = true;
    cx.spawn(async (cx) => {
      try {
        const told = await repoTold(here, this.ask, this.known);
        if (key !== this.key) return;
        Object.assign(this, { root: told.root, on: here.on, watched: told.root ? this.watched : null });
        tell({ github: told.github, changed: told.changed });
        if (told.root) followFolder(this, (cx) => this.here && this.look(this.here, cx), cx);
      } catch {
        // git or core/git.py failed there: the row as it was, the next look tries again
      } finally {
        this.busy = false;
        if (this.again && this.here) {
          this.again = false;
          this.look(this.here, cx);
        }
      }
    });
  }
}

/** herdr-fold's version and newest release (core/update.py), kept for Settings' About and the status bar's item;
 * after an update, once for every client (the copy that marks it seen), "Updated to herdr-fold X" with What's new.
 * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
export async function checkUpdates(core) {
  try {
    const found = await core(UPDATE, ["check"], home(), null);
    setShared(UPDATES, found);
    if (!found.updated) return;
    const notice = updateNotice(found, (await core(UPDATE, ["seen", found.updated], home(), null)).said);
    if (notice) notify(notice);
  } catch {
    // no Python, or core/update.py failed: no version to show, nothing to tell
  }
}

/** HOLDER's folder (its root, on this computer) followed while it is the one watched: AGAIN once it changes; another
 * machine's has no watch (its view looks again on a timer). */
export function followFolder(holder, again, cx) {
  if (holder.on || holder.watched === holder.root) return;
  const root = (holder.watched = holder.root);
  cx.spawn(async (cx) => {
    try {
      while (holder.watched === root) {
        await watchFolder(root);
        if (holder.watched === root) again(cx);
      }
    } catch {
      holder.watched = null;
    }
  });
}

/** The width the right panel had open, which its rail opens to again. */
export const keptWidth = () => /** @type {number | undefined} */ (shared(KEPT) ?? undefined);

/** The right panel's COMMANDS run (the tab bar's » or «, a key's), its width kept first while it is open, its
 * terminal's height while it is under the centre. @param {[string, any][]} commands */
export function runPanel(commands) {
  const root = layout();
  if (panelShown(root) && !panelRailed(root)) setShared(KEPT, panelPx(root));
  keepBottom(root);
  for (const [name, args] of commands) command(name, args);
}

/** The terminal under the centre as kept: shown unless the rail's Terminal hid it, as high as last dragged.
 * @returns {import("./logic.js").Bottom} */
export const bottomChoice = () => ({ shown: shared(BOTTOM_SHOWN) !== false,
  px: /** @type {number} */ (shared(BOTTOM_KEPT) ?? BOTTOM_PX) });

/** Layout ROOT's terminal's height under the centre kept, as dragged. @param {any} root */
export function keepBottom(root) {
  const px = bottomPx(root);
  if (px !== null && px !== shared(BOTTOM_KEPT)) setShared(BOTTOM_KEPT, px);
}

/** The rail's Terminal: the tab's terminal under the centre shown or hidden, as the TUI's rail raises and lowers its
 * terminal; the choice kept for the next fold. */
export function toggleBottom() {
  const { commands, shown } = bottomToggle(layout());
  if (shown !== null) setShared(BOTTOM_SHOWN, shown);
  for (const [name, args] of commands) command(name, args);
}

/** Cmd+Shift+E, as the TUI's: the dock hidden entirely, or shown again as it was. */
export const toggleColumn = () => runPanel(columnToggle(layout(), bottomChoice()));

/** Cmd+Shift+O, as the TUI's Restore panels: the views More hid, the dock and the terminal under the tab back. */
export function restorePanels() {
  setShared(BOTTOM_SHOWN, true);
  runPanel(restoreCommands(layout(), tabsState().github, bottomChoice()));
}

/** Whether the dock is open: neither its rail nor hidden. */
export const dockOpen = () => panelShown(layout()) && !panelRailed(layout());

/** », « and Cmd+Option+B: the open dock folded to its rail (the Chats list in it closed first), a rail (or a panel an
 * earlier version's × hid) opened again. */
export const foldDock = () => runPanel(foldCommands(layout(), tabsState().github, chosenView(), keptWidth(),
  bottomChoice()));

/** A press on ✦'s neighbours (More): the Chats list or a float beside the rail closed, as it goes on to its own. */
export function closeChats() {
  shutFloat(RAIL_FLOAT);
  if (chatsShown()) toggleChats();
}

/** The rail's Terminal pressed: a float beside the rail closed, the terminal under the centre shown or hidden. */
export function terminalPress() {
  shutFloat(RAIL_FLOAT);
  toggleBottom();
}

/** From the tab bar's render: SIDE's width PX (a drag's, its toggle's) looked at again once unchanged for SETTLE ms,
 * let go then, not on the way: REST puts it where it comes to rest, given where it rested last (restAt).
 * @param {string} side @param {number | null} px @param {(from: number | null) => number | null} rest */
export function restFollow(side, px, rest, cx) {
  const seen = RESTS[side];
  if (px === seen.px) return;
  seen.px = px;
  cx.timer.after(SETTLE, () => {
    if (seen.px === px) restAt(seen, px, rest);
  });
}

/** The dock let go of after a drag, rested FROM px wide last: a rail widened past UNFOLD opened as « opens it, else
 * narrower than a rail starts its rail; open, its width kept for «. @param {number | null} from */
export function restDock(from) {
  const { to, open, commands } = dockRest(layout(), from, keptWidth(), bottomChoice());
  for (const [name, args] of commands) command(name, args);
  if (open && !commands.length && to !== shared(KEPT)) setShared(KEPT, to);
  return to;
}

/** The tab bar's end, the row of the left sidebar's own toggle: » while the dock is OPEN, else «, ACT (foldDock); in
 * the same place in every state. @param {boolean} open @param {() => void} act */
export function panelToggle(t, open, act) {
  return iconButton(t, "panel-toggle", open ? "chevrons-right" : "chevrons-left", open ? "Collapse to icons"
    : "Expand panels", () => act(), { size: 15, left: true });
}

/** A key's VIEW (changes, search, issues, agent) shown, as the TUI's: opened; floating beside the rail while the dock
 * is one; then COMMAND (the key's: write, commit-push…; else the view's own) run by that view's copy, once.
 * @param {string} view @param {string} [asked] */
export function summon(view, asked = view) {
  const root = layout(), { github } = tabsState();
  if (view === "issues" && !github) return;                           // off GitHub: left as it is, as the TUI's
  if (panelShown(root) && panelRailed(root)) return void openRail(view, null, asked);
  pickPanel(view);
  setShared(SUMMON, { view, command: asked, at: Date.now() });
}

/** The Agent panel shown in the dock, beside the rail while it is one: AGENT's (kept for the space, as a pick in its
 * list), SECTION opened, ROW chosen, LOOK only looked at (how it installs), as a dim one picked there (agent.js).
 * @param {{ section?: string | null, row?: string | null, agent?: string | null, look?: string | null }} [what] */
export function openAgentPanel({ section = null, row = null, agent = null, look = null } = {}) {
  const space = spaceShown();
  if (agent && space) {
    setShared(AGENT_CHOSEN, keepAgent(shared(AGENT_CHOSEN), space, agent, new Set(spaces().map((s) => s.id))));
  }
  setShared(AGENT_ASK, { space, section, row, look, at: Date.now() });
  summon("agent");
}

/** The dock folded to its rail: the SHOWN views (else all, Issues on GITHUB only; Changes' count CHANGED), a square
 * named under each, a press floating one, lit while FLOATING (pressed again: closed); Agent's dot while PROBLEMS; the
 * TERMINAL (none: off) lit while under the centre (BOTTOM). @param {any} tabs @param {string | null} terminal */
export function rail(t, { github, changed }, terminal, shown = /** @type {any} */ (null), bottom = false,
  problems = null, floating = null) {
  const on = (/** @type {string} */ panel) => panel === "terminal" || (shown ? shown.includes(panel)
    : panel !== "issues" || github);
  const counts = /** @type {Record<string, number>} */ ({ changes: changed });
  return v_flex().id("panel-rail").size_full().items_center().pt(8).gap(12)
    .children(RAILED.filter(([panel]) => on(panel)).map(([panel, name, word]) => {
      const off = panel === "terminal" && !terminal, lit = panel === "terminal" ? !off && bottom : panel === floating;
      const dot = panel === "agent" && problems ? toneColor(t, problems.tone) : null;
      const label = dot ? `${word}: ${problems?.said}` : word;
      return v_flex().id(`rail-${panel}`).flex_none().items_center().gap(4)
        .when(!off, (e) => e.on_mouse_down("left", (e, cx) => {
          cx.stop_propagation();
          panel === "terminal" ? terminalPress() : railPress(panel, e.bounds);
        }))
        .child(iconTab(t, `rail-${panel}-tab`, icon(name, 15).when(lit, (e) => e.text_color(t.accent)),
          { count: counts[panel] ?? 0, active: lit, dot, tip: off ? "No terminal in this tab" : label,
            act: () => {} }))
        .child(div().text_size(10).text_color(off ? t.border : lit ? t.accent : t.dim).child(word));
    }));
}

/** The rail as the layout shows it now: the panels shown, the tab's TERMINAL and whether it shows under the centre,
 * the view floating beside it. @param {string | null} terminal */
export const liveRail = (t, terminal) => rail(t, tabsState(), terminal, shownPanels(layout(), tabsState().github),
  bottomShown(layout()), problemsHere(), floatingView())
  .on_size_change((size) => {                 // the rail's height, a float's tallest (floatMax)
    if (Math.round(size.height) !== shared(RAIL_PX)) setShared(RAIL_PX, Math.round(size.height));
  });

/** The view floating beside the rail now (Chats too), or null. */
export const floatingView = () => floating(shared(RAIL_FLOAT))?.panel ?? null;

/** A rail's view pressed (BOUNDS: its button): floating beside the rail, or closed while it is the one floating, as
 * Adobe's lit icon closes its panel. @param {string} panel @param {any} bounds */
export function railPress(panel, bounds) {
  const open = floating(shared(RAIL_FLOAT));
  if (open?.panel === panel) return void shutFloat(RAIL_FLOAT);
  openRail(panel, bounds);
}

/** View PANEL (Chats too) floating beside the rail every time, under the tab bar, pressed there or by a key, THEN its
 * command run first; one at a time, the one before closed first, as the left rail's; marked, so its icon is lit.
 * @param {string} panel @param {any} _bounds its button's, pressed @param {string} [then] */
export function openRail(panel, _bounds, then) {
  const root = layout();
  shutFloat(RAIL_FLOAT);
  setShared(RAIL_FLOAT, { panel, overlay: openOverlay({ kind: "window", width: PANEL_PX,       // as tall as its content
    at: { x: floatX(panel, root, window.viewport_size().width, PANEL_PX), y: floatTop(root) },
    mod: "herdr-fold", props: { part: "float", panel, then } }) });
}

/** A view's float's height (VIEW's): as kept, dragged by its foot's grip (shrinking and growing as the pointer goes,
 * the window following its content), a double click there its tallest or back to the height dragged last. */
export class FloatSize {
  /** VIEW's; FIT (its rows, Spaces') its height until dragged, MOST its tallest (the window's room under it), else
   * the rail's. @param {string} view @param {{ fit?: number | null, most?: number | null }} [how] */
  constructor(view, { fit = null, most = null } = {}) {
    this.view = view;
    this.fit = fit;
    this.most = most;
    /** @type {number | null} its height now; null: as kept */
    this.px = null;
    /** @type {{ y: number, px: number } | null} a drag under way: where it started */
    this.drag = null;
    this.over = false;                          // the pointer on the grip
  }

  /** Its bounds now: the view's least, MOST or the rail's height (from under the tab bar to the card's foot). */
  get bounds() {
    const rail = /** @type {number | null} */ (shared(RAIL_PX) ?? null), min = floatMin(this.view);
    if (this.most !== null) return { min, max: Math.max(min, this.most) };
    return { min, max: Math.max(min, rail ? floatMax(rail, layout()) : railFloatPx(this.view, {}, null, layout())) };
  }

  /** Its height until dragged now: as kept for the view, else as it fits (FIT) or the rail's tallest. */
  kept() {
    return this.fit !== null ? fitFloatPx(this.view, shared(FLOAT_KEPT), this.fit, this.bounds.max)
      : railFloatPx(this.view, shared(FLOAT_KEPT), /** @type {any} */ (shared(RAIL_PX)), layout());
  }

  /** Its height now, inside its bounds (the window resized meanwhile). */
  height() {
    const { min, max } = this.bounds;
    return Math.min(Math.max(this.px ?? this.kept(), min), max);
  }

  /** The grip pressed at E: a drag starts. */
  press(e) {
    this.drag = { y: e.position.y, px: this.height() };
  }

  /** The pointer at E while dragging: the height follows it. */
  move(e, cx) {
    if (!this.drag) return;
    const { min, max } = this.bounds, px = dragPx(this.drag, e.position.y, min, max);
    if (px === this.px) return;
    this.px = px;
    cx.notify();
  }

  /** The drag over (released, or the pointer gone off the float): its height kept for the view's next float. */
  end(cx) {
    if (!this.drag) return;
    this.drag = null;
    setShared(FLOAT_KEPT, keepFloat(shared(FLOAT_KEPT), this.view, this.height()));
    cx.notify();
  }

  /** A double click on the grip: the tallest, or from there back to the height dragged last. */
  toggle(cx) {
    const { max } = this.bounds;
    this.px = this.height() < max ? max : this.kept();
    cx.notify();
  }
}

/** The grip at a float's foot, FLOAT_GRIP high: a short bar faint, lit under the pointer, the resize cursor; a press
 * drags SIZE, a double click toggles it. @param {FloatSize} size */
export const floatGrip = (t, size) => div().id("float-grip").w_full().h(FLOAT_GRIP).flex_none().flex().items_center()
  .justify_center().cursor_row_resize()
  .on_hover((over, cx) => void ((size.over = over), cx.notify()))
  .on_mouse_down("left", (e, cx) => {
    cx.stop_propagation();                      // not the window's own drag
    e.click_count === 2 ? size.toggle(cx) : size.press(e);
  })
  .child(div().w(24).h(4).rounded_full().bg(size.drag ? t.accent : size.over ? t.muted : t.border));

/** View NAME floating beside a rail (OVERLAY), BODY under its head (BUTTONS), as tall as SIZE says, its grip at its
 * foot, FOCUS, PANEL and OWNS as floatPanel's; the pointer followed while it drags, a band under it meanwhile so it
 * stays on the float. @param {FloatSize} size @param {string} name @param {string} overlay @param {any} [how] */
export function sizedFloat(t, size, name, overlay, body,
  { focus = null, panel = null, buttons = [], owns = null } = {}) {
  return v_flex().id("float-sized").w_full()
    .on_mouse_move((e, cx) => size.move(e, cx)).on_mouse_up("left", (_e, cx) => size.end(cx))
    .on_hover((over, cx) => void (!over && size.end(cx)))
    .child(floatPanel(t, name, overlay, size.height(), buttons, body, { foot: floatGrip(t, size), focus, panel, owns }))
    .when(Boolean(size.drag), (e) => e.child(div().h(DRAG_SLACK).flex_none()));
}

