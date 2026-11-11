// @ts-check
// The right panel as Adobe's dock: its head (⋯ and »), then its groups, Files and Search, Changes and Issues, each a
// head of tabs over the stack of its panels, which folds to that head; folded whole, the dock is a rail of icons.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { home, layout, notify, openOverlay, setShared, shared, watchFolder, run as command } from "herdr";
import { UPDATE } from "./helper.js";
import { aboutLines, foldCommands, groupFolded, groupOf, groupSize, groupTabs, hideCommands, keptTabs, panelChoices,
  PANEL_NAMES, PANEL_PX, panelPx, panelRailed, panelShown, pickCommands, railToggle, shownPanels, shownTab }
  from "./logic.js";
import { badge, BUTTON, fold, GAP, icon, iconButton, iconTab, PAD } from "./parts.js";

export const TABS = "herdr-fold.tabs";        // what the views tell the heads: { github, changed }
export const SUMMON = "herdr-fold.summon";    // a key's ask for a view: { view, command, at }, the tab bar's
const KEPT = "herdr-fold.panel-width";        // the right panel's width while open, which its rail opens to again
const SIZES = "herdr-fold.group-sizes";       // each group's size before it folded, which it opens to again
const CHOSEN = "herdr-fold.group-tabs";       // each group's tab last picked, shown again once it can (Issues)
const UPDATES = "herdr-fold.updates";         // core/update.py's last check, for the dock's ⋯ (shared)
const FLOAT_H = 0.85;                         // a view floating beside the rail: this share of the window high
/** @type {[string, import("./icons.js").IconName, string][]} the rail's views: the panel, its icon, its label */
const RAILED = [["files", "files", "Files"], ["search", "search", "Search"], ["changes", "git-branch", "Changes"],
  ["issues", "circle-dot", "Issues"], ["terminal", "square-terminal", "Terminal"]];

/** @typedef {{ group: string, tabs: [string, string][], shown: string | null, folded: boolean,
 * counts: Record<string, number>, hovered?: string | null }} Head */
/** @typedef {{ pick: (panel: string) => void, fold: () => void }} HeadActs */

/** A group's head, as Adobe's panel group: its fold, then its TABS ([panel, name]), the SHOWN one raised, a COUNT in
 * its badge (Changes'), HOVERED's as the pointer lights it; a tab's click shows it and opens the group (ACTS).
 * @param {Head} head @param {HeadActs} [acts] */
export function groupHead(t, { group, tabs, shown, folded, counts, hovered = null }, acts = liveActs(group)) {
  const tab = ([id, name]) => {
    const on = shown === id, lit = !on && hovered === id;
    return h_flex().id(`group-tab-${id}`).h(24).px(8).gap(6).items_center().rounded(6).cursor_pointer()
      .text_size(13).text_color(on ? t.foreground : lit ? t.muted : t.dim)
      .when(on, (e) => e.bg(t.raised).font_semibold()).when(lit, (e) => e.bg(t.hover))
      .when(!on, (e) => e.hover((s) => s.bg(t.hover).text_color(t.muted))).on_click(() => acts.pick(id))
      .child(name)
      .when((counts[id] ?? 0) > 0, (e) => e.child(badge(t, counts[id])));
  };
  // its tabs PAD under the frame's top; its fold's chevron PAD in, over its rows' chevrons, its pad halfway as theirs
  return h_flex().id(`group-head-${group}`).size_full().pt(PAD).px(PAD / 2).gap(GAP).items_center()
    .child(div().id(`group-fold-${group}`).w(BUTTON).h(24).flex_none().flex().items_center().justify_center().rounded(6)
      .text_color(t.dim).cursor_pointer().tooltip(folded ? "Open group" : "Fold group")
      .hover((s) => s.bg(t.hover).text_color(t.foreground)).on_click(() => acts.fold())
      .child(fold(`group-fold-${group}-mark`, !folded, 14)))
    .children(tabs.map(tab));
}

/** What a live head's clicks do to GROUP: a tab shown and the group opened; the group folded or opened again, the
 * size it had kept. @param {string} group @returns {HeadActs} */
function liveActs(group) {
  return {
    pick: (panel) => pickPanel(panel),
    fold: () => {
      const root = layout();
      if (!groupFolded(root, group)) setShared(SIZES, { ...groupSizes(), [group]: groupSize(root, group) });
      runPanel(foldCommands(root, group, groupSizes()[group]));
    },
  };
}

/** Each group's size before it folded. @returns {Record<string, any>} */
const groupSizes = () => /** @type {any} */ (shared(SIZES)) ?? {};

/** Each group's tab last picked, else the one its stack is on (keptTabs). @returns {Record<string, string>} */
export function chosenTabs() {
  const told = shared(CHOSEN);
  return keptTabs(layout(), told && typeof told === "object" ? /** @type {any} */ (told) : {});
}

/** CHOSEN kept as the groups' tabs: before a stack gives way to another tab, the one it was on stays the choice.
 * @param {Record<string, string>} chosen */
export function keepTabs(chosen) {
  if (JSON.stringify(shared(CHOSEN)) !== JSON.stringify(chosen)) setShared(CHOSEN, chosen);
}

/** PANEL picked, by its tab or its key: its group's choice from now on, shown there, the group opened.
 * @param {string} panel */
function pickPanel(panel) {
  const chosen = chosenTabs(), group = groupOf(panel);
  if (group) keepTabs({ ...chosen, [group]: panel });
  runPanel(pickCommands(layout(), panel, { github: tabsState().github, kept: keptWidth(), sizes: groupSizes(),
    chosen }));
}

/** GROUP's head as the layout shows it now: its tabs, the one shown, its fold, Changes' count. @param {string} group */
export function liveGroupHead(t, group) {
  const root = layout(), { github, changed } = tabsState();
  return groupHead(t, { group, tabs: groupTabs(root, group, github).map((id) => [id, PANEL_NAMES[id]]),
    shown: shownTab(root, group, github), folded: groupFolded(root, group), counts: { changes: changed } });
}

/** The dock's head, over its groups: ⋯ opening MORE's menu under it (PRESSED keeps where it was pressed), and »
 * folding the dock to its rail. @param {{ pressed?: any }} pressed @param {() => void} more */
export function dockHead(t, pressed, more) {
  return h_flex().id("dock-head").size_full().px(4).gap(GAP).items_center().justify_end()
    .child(iconButton(t, "dock-more", "ellipsis", "More", () => more(),
      { press: (/** @type {any} */ e) => (pressed.pressed = e.bounds) }))
    .child(iconButton(t, "dock-fold", "chevrons-right", "Collapse to icons",
      () => runPanel(railToggle(layout(), keptWidth()))));
}

/** The dock's head as it is now, its ⋯ in MENUS: the panels with their ✓, as the TUI's, then herdr-fold's version
 * and its update check; CORE runs core/'s code (main.js's python). @param {{ pressed?: any }} pressed
 * @param {import("./menus.js").Menus} menus */
export function liveDockHead(t, pressed, menus, core) {
  const { github } = tabsState();
  const panels = panelChoices(layout(), github).map(({ panel, label, on, off }) => ({ label, on, off,
    act: () => runPanel(hideCommands(layout(), panel, on, tabsState().github, chosenTabs())) }));
  const about = aboutLines(shared(UPDATES)).map((item) => item.on === undefined ? item
    : { ...item, act: () => void checkUpdates(core, ["switch", item.on ? "off" : "on"]) });
  return dockHead(t, pressed, () => menus.open(about.length ? [...panels, null, ...about] : panels, pressed.pressed));
}

/** What the views tell the heads and the rail (TABS): whether the repository is on GitHub, its changed files' count. */
export function tabsState() {
  const told = /** @type {{ github?: boolean, changed?: number } | null} */ (shared(TABS)) ?? {};
  return { github: Boolean(told.github), changed: told.changed ?? 0 };
}

/** herdr-fold's version and newest release (core/update.py, after FIRST: a switch), kept for the dock's ⋯; a newer
 * one told once, for the TUI's sidebars too. @param {string[]} [first]
 * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
export async function checkUpdates(core, first) {
  try {
    if (first) await core(UPDATE, first, home(), null);
    const found = await core(UPDATE, ["check"], home(), null);
    setShared(UPDATES, found);
    if (found.newer && found.told !== found.latest) {
      notify({ title: `herdr-fold ${found.latest} is out`, body: found.how, level: "info" });
      await core(UPDATE, ["told", found.latest], home(), null);
    }
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

/** The right panel's COMMANDS run (its » or «, a head's, a key's), its width kept first while it is open.
 * @param {[string, any][]} commands */
export function runPanel(commands) {
  const root = layout();
  if (panelShown(root) && !panelRailed(root)) setShared(KEPT, panelPx(root));
  for (const [name, args] of commands) command(name, args);
}

/** The tab bar's end while the dock is a rail (or hidden, as an earlier version's × left it): « opens it again (open,
 * its head's » folds it). */
export function panelToggle(t) {
  const root = layout();
  if (panelShown(root) && !panelRailed(root)) return div();
  return iconButton(t, "panel-open", "chevrons-left", "Expand panels",
    () => runPanel(railToggle(layout(), keptWidth())), { size: 15, left: true });
}

/** A key's VIEW (changes, search, issues) shown, as the TUI's: in its group, opened; floating beside the rail while the
 * dock is one; then COMMAND (the key's: write, commit-push…; else the view's own) run by that view's copy, once.
 * @param {string} view @param {string} [asked] */
export function summon(view, asked = view) {
  const root = layout(), { github } = tabsState();
  if (view === "issues" && !github) return;                           // off GitHub: left as it is, as the TUI's
  if (panelShown(root) && panelRailed(root)) return void openRail(view, null, null, asked);
  pickPanel(view);
  setShared(SUMMON, { view, command: asked, at: Date.now() });
}

/** The dock folded to its rail, as the left sidebar's: its views on squares, a label under each, Changes with its
 * count (CHANGED), the SHOWN ones (else all, Issues on GITHUB only), the tab's TERMINAL (none: off); a press floats
 * one. @param {{ github: boolean, changed: number }} tabs @param {string | null} terminal @param {any} [shown] */
export function rail(t, { github, changed }, terminal, shown = null) {
  const on = (/** @type {string} */ panel) => panel === "terminal" || (shown ? shown.includes(panel)
    : panel !== "issues" || github);
  return v_flex().id("panel-rail").size_full().items_center().pt(8).gap(12)
    .children(RAILED.filter(([panel]) => on(panel)).map(([panel, name, label]) => {
      const off = panel === "terminal" && !terminal;
      return v_flex().id(`rail-${panel}`).flex_none().items_center().gap(4)
        .when(!off, (e) => e.on_mouse_down("left", (e, cx) => {
          cx.stop_propagation();
          openRail(panel, e.bounds, terminal);
        }))
        .child(iconTab(t, `rail-${panel}-tab`, icon(name, 15), { count: panel === "changes" ? changed : 0,
          tip: off ? "No terminal in this tab" : label, act: () => {} }))
        .child(div().text_size(10).text_color(off ? t.border : t.dim).child(label));
    }));
}

/** The rail as the layout shows it now: the panels shown, the tab's TERMINAL. @param {string | null} terminal */
export const liveRail = (t, terminal) => rail(t, tabsState(), terminal, shownPanels(layout(), tabsState().github));

/** PANEL floating left of the rail's button (BOUNDS; for a key, where the app puts it): a view, THEN its command run
 * first, or the tab's TERMINAL under a head of herdr-fold's; one at a time, as the left rail's floats.
 * @param {string} panel @param {any} bounds @param {string | null} terminal @param {string} [then] */
export function openRail(panel, bounds, terminal, then) {
  const spec = { kind: /** @type {"window"} */ ("window"), key: "herdr-fold.rail", width: PANEL_PX, height: FLOAT_H,
    ...(bounds ? { at: { x: Math.max(8, bounds.x - PANEL_PX - 8), y: 48 } } : {}) };
  if (panel !== "terminal") {
    return void openOverlay({ ...spec, mod: "herdr-fold", props: { part: "float", panel, then } });
  }
  openOverlay({ ...spec, layout: { id: "rail-terminal", type: "column", children: [
    { id: "rail-terminal-head", type: "block", size: { px: 36 }, content: { mod: "herdr-fold",
      props: { part: "float-head", name: "Terminal" } } },
    { id: "rail-terminal-body", type: "block", content: { terminal } }] } });
}

