// @ts-check
// The window's status bar, where the app's own was, as the mockups' .status: the machine, the branch, the agents, the
// runs working (runs.html's), at its end the one update there is (Herdr's, herdr-core's, else a newer herdr-fold).
import { div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { agents, home, shared, spaces, terminals, updates, run as command } from "herdr";
import { chatWaits } from "./chat.js";
import { RUNS } from "./helper.js";
import { agentsSaid, barStatuses, updateReady } from "./logic.js";
import { openAgents } from "./panel.js";
import { SPINNER } from "./parts.js";
import { runsWorking } from "./runs.js";
import { openSettings, UPDATES } from "./settings.js";

const RUNS_EVERY = 30000;          // ms between two counts of the runs working (core keeps Claude's list as long)
let working = 0;                   // the runs working, as core counted them last (runs.py's working)

/** @typedef {{ machine: string | null, branch: string | null, agents: ReturnType<typeof agentsSaid>,
 * update: ReturnType<typeof updateReady>, runs?: number }} Status what the bar says */

/** The runs working counted now and every RUNS_EVERY (CORE: main.js's python), the bar drawn anew when that changes.
 * @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
export function watchRuns(core, cx) {
  const count = (/** @type {any} */ cx) => cx.spawn(async (/** @type {any} */ cx) => {
    try {
      const n = Number((await core(RUNS, ["working"], home(), null))?.working) || 0;
      if (n === working) return;
      working = n;
      cx.notify();
    } catch {
      // counted again next time
    }
  });
  count(cx);
  cx.timer.every(RUNS_EVERY, count);
}

/** The bar as the shown space, the agents (in panes and chat tabs), the runs, Herdr's updates and herdr-fold's own
 * check have it now. */
export function liveStatus(t) {
  const space = spaces().find((s) => s.active);
  return statusBar(t, { machine: space?.machine ?? null, branch: space?.branch ?? null,
    agents: agentsSaid(barStatuses(agents(), terminals(), chatWaits().agents)),
    update: updateReady(updates(), shared(UPDATES)), runs: working });
}

/** The status bar (STATUS), on the side's level (chrome) under a hairline, 16 in and its items 16 apart, 12 in the
 * captions' tone: the machine, the branch, the agents' dot and words, the runs working (a press shows them in Runs);
 * at its end the update item. @param {Status} status */
export function statusBar(t, { machine, branch, agents: said, update, runs = 0 }) {
  const dot = (/** @type {string} */ color) => div().size(6).flex_none().rounded_full().bg(color);
  const role = said.role === "waiting" ? t.ansi3 : said.role === "working" ? t.accent : t.dim;
  return h_flex().id("status").size_full().min_w(0).px(16).gap(16).items_center().bg(t.chrome).border_t(1)
    .border_color(t.border).text_size(12).text_color(t.muted)
    .child(div().flex_none().child(machine ?? "This computer"))
    .when(Boolean(branch), (e) => e.child(div().flex_shrink(1).min_w(0).truncate().child(String(branch))))
    .child(h_flex().flex_none().gap(6).items_center().child(dot(role)).child(said.words))
    .when(runs > 0, (e) => e.child(h_flex().id("status-runs").h(20).flex_none().px(6).items_center().rounded(4)
      .text_color(t.foreground).cursor_pointer().hover((/** @type {any} */ s) => s.bg(t.hover))
      .tooltip("Show them in the Agents tab's Runs").on_click(() => openAgents({ view: "runs" }))
      .child(runsWorking(runs))))
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
