// @ts-check
// The window's status bar, where the app's own was, as the mockups' .status: the machine, the branch, the agents, and
// at its end the one update there is (Herdr's, herdr-core's, else a newer herdr-fold). The palette: title.js.
import { div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { agents, shared, spaces, updates, run as command } from "herdr";
import { agentsSaid, updateReady } from "./logic.js";
import { SPINNER } from "./parts.js";
import { openSettings, UPDATES } from "./settings.js";

/** @typedef {{ machine: string | null, branch: string | null, agents: ReturnType<typeof agentsSaid>,
 * update: ReturnType<typeof updateReady> }} Status what the bar says */

/** The bar as the shown space, the agents, Herdr's updates and herdr-fold's own check have it now. */
export function liveStatus(t) {
  const space = spaces().find((s) => s.active);
  return statusBar(t, { machine: space?.machine ?? null, branch: space?.branch ?? null,
    agents: agentsSaid(agents().map((a) => a.status)), update: updateReady(updates(), shared(UPDATES)) });
}

/** The status bar (STATUS), on the side's level (chrome) under a hairline, 16 in and its items 16 apart, 12 in the
 * captions' tone: the machine, the branch, the agents' dot and words; at its end the update item.
 * @param {Status} status */
export function statusBar(t, { machine, branch, agents: said, update }) {
  const dot = (/** @type {string} */ color) => div().size(6).flex_none().rounded_full().bg(color);
  const role = said.role === "waiting" ? t.ansi3 : said.role === "working" ? t.accent : t.dim;
  return h_flex().id("status").size_full().min_w(0).px(16).gap(16).items_center().bg(t.chrome).border_t(1)
    .border_color(t.border).text_size(12).text_color(t.muted)
    .child(div().flex_none().child(machine ?? "This computer"))
    .when(Boolean(branch), (e) => e.child(div().flex_shrink(1).min_w(0).truncate().child(String(branch))))
    .child(h_flex().flex_none().gap(6).items_center().child(dot(role)).child(said.words))
    .child(div().flex_1())
    .when(Boolean(update), (e) => e.child(updateItem(t, /** @type {any} */ (update), dot)));
}

/** The update, quiet: a green dot and its words, a press updating (herdr-core), restarting (Herdr) or opening
 * Settings at About (a newer herdr-fold), its tip saying which; while herdr-core updates, a spinner and no press.
 * @param {NonNullable<ReturnType<typeof updateReady>>} update @param {(color: string) => any} dot */
function updateItem(t, update, dot) {
  const item = h_flex().id("status-update").h(20).flex_none().px(6).gap(6).items_center().rounded(4)
    .tooltip(update.tip)
    .child(update.busy ? div().flex_none().text_color(t.ansi2).frames(SPINNER, 100) : dot(t.ansi2))
    .child(update.words);
  return update.busy ? item : item.cursor_pointer().hover((s) => s.bg(t.hover).text_color(t.foreground))
    .on_click(() => (update.opens ? openSettings(update.opens) : command(String(update.command))));
}
