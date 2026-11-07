// @ts-check
// The right panel as one of Adobe's panel groups: herdr-fold's views, Files among them, as its tabs, on the header of
// the stack that holds them, so they stay while Files shows; its toggle at the tab bar's right end.
import { div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { home, layout, notify, openOverlay, setShared, shared, watchFolder, run as command } from "herdr";
import { UPDATE } from "./helper.js";
import { aboutLines, PANEL, PANEL_BODY, PANEL_PX, panelPx, panelRailed, panelShown, railToggle, shownTab }
  from "./logic.js";
import { badge, GAP, icon, iconButton, iconTab } from "./parts.js";

export const VIEW = "herdr-fold.view";        // the view shown, kept: changes, search or issues
export const TABS = "herdr-fold.tabs";        // what the views tell the tabs: { github, changed }
export const VIEW_NAMES = { changes: "Changes", search: "Search", issues: "Issues", files: "Files" };
const KEPT = "herdr-fold.panel-width";        // the right panel's width while open, which its rail opens to again
const UPDATES = "herdr-fold.updates";         // core/update.py's last check, for the panel's menu (shared)
const FLOAT_H = 0.85;                         // a view floating beside the rail: this share of the window high
/** @type {[string, import("./icons.js").IconName, string][]} the rail's views: the panel, its icon, its label */
const RAILED = [["files", "files", "Files"], ["search", "search", "Search"], ["changes", "git-branch", "Changes"],
  ["issues", "circle-dot", "Issues"], ["terminal", "square-terminal", "Terminal"]];

/** The group's tabs, in VS Code's order: SHOWN's on a raised pad, the changed files' count (CHANGED) in a badge,
 * Issues only for a repository on GitHub (GITHUB); at the end, × closes the panel; a right click opens ABOUT's menu.
 * @param {{ shown: string, github: boolean, changed: number }} state @param {() => void} [about] */
export function panelTabs(t, { shown, github, changed }, about) {
  const tab = (id) => {
    const on = shown === id;
    return h_flex().id(`panel-tab-${id}`).h(28).px(12).gap(6).items_center().rounded(6).cursor_pointer()
      .text_size(13).text_color(on ? t.foreground : t.dim).when(on, (e) => e.bg(t.raised).font_semibold())
      .when(!on, (e) => e.hover((s) => s.bg(t.hover).text_color(t.muted))).on_click(() => pick(id))
      .child(VIEW_NAMES[id])
      .when(id === "changes" && changed > 0, (e) => e.child(badge(t, changed)));
  };
  return h_flex().id("panel-tabs").size_full().px(6).gap(GAP).items_center().border_b(1).border_color(t.border)
    .when(Boolean(about), (e) => e.on_mouse_down("right", () => about?.()))
    .children(["files", "search", "changes", ...(github ? ["issues"] : [])].map(tab)).child(div().flex_1())
    .child(iconButton(t, "panel-close", "x", "Close panel", () => command("layout.hide", { id: PANEL })));
}

/** What the views tell the tabs and the rail (TABS): whether the repository is on GitHub, its changed files' count. */
export function tabsState() {
  const told = /** @type {{ github?: boolean, changed?: number } | null} */ (shared(TABS)) ?? {};
  return { github: Boolean(told.github), changed: told.changed ?? 0 };
}

/** The tabs as the panel shows them now, MENUS opening its menu about herdr-fold; CORE runs core/'s code (main.js's
 * python). @param {import("./menus.js").Menus} menus */
export function liveTabs(t, menus, core) {
  const { github, changed } = tabsState();
  const items = aboutLines(shared(UPDATES)).map((item) => item.on === undefined ? item
    : { ...item, act: () => void checkUpdates(core, ["switch", item.on ? "off" : "on"]) });
  return panelTabs(t, { shown: shownTab(layout(), shared(VIEW), github), github, changed },
    items.length ? () => menus.open(items) : undefined);
}

/** herdr-fold's version and newest release (core/update.py, after FIRST: a switch), kept for the panel's menu; a newer
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

/** Tab ID picked: Files is a block of its own; another view is the Changes block's, which shows it (main.js follows
 * VIEW). */
function pick(id) {
  if (id !== "files") setShared(VIEW, id);
  command("layout.select", { stack: PANEL_BODY, child: id === "files" ? "files" : "changes" });
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

/** The right panel's COMMANDS run (its toggle's, Cmd+Shift+G's), its width kept first while it is open.
 * @param {[string, any][]} commands */
export function runPanel(commands) {
  const root = layout();
  if (panelShown(root) && !panelRailed(root)) setShared(KEPT, panelPx(root));
  for (const [name, args] of commands) command(name, args);
}

/** The right panel's toggle, at the tab bar's end: it folds the panel to its rail and opens it again. */
export function panelToggle(t) {
  const root = layout(), open = panelShown(root) && !panelRailed(root);
  return iconButton(t, "panel-open", "panel-right", open ? "Fold panel" : "Open panel",
    () => runPanel(railToggle(layout(), keptWidth())), { size: 15, left: true });
}

/** The right panel folded to its rail, as the left sidebar's: its views on squares, a label under each, Changes with
 * its count (CHANGED), Issues only on GitHub (GITHUB), the tab's TERMINAL (none: its button off); a press floats one.
 * @param {{ github: boolean, changed: number }} tabs @param {string | null} terminal */
export function rail(t, { github, changed }, terminal) {
  return v_flex().id("panel-rail").size_full().items_center().pt(8).gap(12)
    .children(RAILED.filter(([panel]) => panel !== "issues" || github).map(([panel, name, label]) => {
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

