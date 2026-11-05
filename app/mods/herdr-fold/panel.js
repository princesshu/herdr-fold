// @ts-check
// The right panel as one of Adobe's panel groups: herdr-fold's views and the app's Files as its tabs, on the header of
// the stack that holds them, so they stay while Files shows; its toggle at the tab bar's right end.
import { div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { layout, setShared, shared, run as command } from "herdr";
import { PANEL, PANEL_BODY, panelShown, shownTab } from "./logic.js";
import { GAP, iconButton } from "./parts.js";

export const VIEW = "herdr-fold.view";        // the view shown, kept: changes, search or issues
export const TABS = "herdr-fold.tabs";        // what the views tell the tabs: { github, changed }
const NAMES = { changes: "Changes", search: "Search", issues: "Issues", files: "Files" };
const BUTTONS = "workspace.panels";           // the app's: the panels its tab bar has a button for
const BEFORE = "herdr-fold.app-panels";       // those before this layout took them off, given back as it goes

/** The group's tabs, in VS Code's order: SHOWN's on a raised pad, the changed files' count (CHANGED) in a badge,
 * Issues only for a repository on GitHub (GITHUB); at the end, × closes the panel.
 * @param {{ shown: string, github: boolean, changed: number }} state */
export function panelTabs(t, { shown, github, changed }) {
  const tab = (id) => {
    const on = shown === id;
    return h_flex().id(`panel-tab-${id}`).h(28).px(10).gap(6).items_center().rounded(6).cursor_pointer()
      .text_size(12.5).text_color(on ? t.foreground : t.dim).when(on, (e) => e.bg(t.raised).font_semibold())
      .when(!on, (e) => e.hover((s) => s.bg(t.hover).text_color(t.muted))).on_click(() => pick(id))
      .child(NAMES[id])
      .when(id === "changes" && changed > 0, (e) => e.child(div().h(16).min_w(16).px(4).flex().items_center()
        .justify_center().rounded_full().bg(t.accent).text_color(t.accent_foreground ?? t.background).text_size(10)
        .font_bold().child(String(changed))));                  // a round badge, as VS Code's on its Source Control
  };
  return h_flex().size_full().px(6).gap(GAP).items_center().border_b(1).border_color(t.border)
    .children(["files", "search", "changes", ...(github ? ["issues"] : [])].map(tab)).child(div().flex_1())
    .child(iconButton(t, "panel-close", "x", "Close panel", () => command("layout.hide", { id: PANEL })));
}

/** The tabs as the panel shows them now. */
export function liveTabs(t) {
  const told = /** @type {{ github?: boolean, changed?: number } | null} */ (shared(TABS)) ?? {};
  const github = Boolean(told.github);
  return panelTabs(t, { shown: shownTab(layout(), shared(VIEW), github), github, changed: told.changed ?? 0 });
}

/** Tab ID picked: Files is the app's own block; a view is herdr-fold's, which shows it (main.js follows VIEW). */
function pick(id) {
  if (id !== "files") setShared(VIEW, id);
  command("layout.select", { stack: PANEL_BODY, child: id === "files" ? "files" : "changes" });
}

/** The tab bar's right end: the right panel's toggle, where the app's Files and Changes buttons were. */
export function panelTrigger(t) {
  const shown = panelShown(layout());
  const tip = shown ? "Hide panel" : "Show panel";
  return h_flex().size_full().pr(10).items_center().justify_end().border_b(1).border_color(t.border)
    .child(iconButton(t, "panel-open", "panel-right", tip,
      () => command(shown ? "layout.hide" : "layout.show", { id: PANEL }), { size: 15 }));
}

/** The app's own panel buttons off its tab bar while this layout shows (the panel's tabs are them), what they were
 * kept for giveBack. */
export function takeAppButtons() {
  if (!shared(BEFORE)) setShared(BEFORE, { panels: shared(BUTTONS) ?? null });
  setShared(BUTTONS, []);
}

/** The app's panel buttons as they were, as the layout goes (lib/herdr_app.py does it for an app that stopped). */
export function giveBack() {
  const before = /** @type {{ panels: unknown } | null} */ (shared(BEFORE));
  if (!before) return;
  setShared(BUTTONS, before.panels);
  setShared(BEFORE, null);
}
