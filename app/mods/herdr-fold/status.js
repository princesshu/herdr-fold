// @ts-check
// The window's status bar, where the app's own was, as the mockups' .status: the machine and its network's mark, the
// branch, the agents, the runs working, at its end the one update there is; the networks' look, Spaces' too.
import { div } from "gpui-kit";
import { h_flex } from "gpui-base";
import { agents, hc, home, machines, readTextFile, setShared, shared, spaces, terminals, updates,
  run as command } from "herdr";
import { chatWaits } from "./chat.js";
import { NETWORKS, RUNS } from "./helper.js";
import { agentsSaid, appMachines, barStatuses, CENTRED, networkOf, networksSeen, NETWORKS_SEEN, setupFolder,
  updateReady } from "./logic.js";
import { openAgents } from "./panel.js";
import { networkMark, SPINNER } from "./parts.js";
import { runsWorking } from "./runs.js";
import { openSettings, UPDATES } from "./settings.js";

const RUNS_EVERY = 30000;          // ms between two counts of the runs working (core keeps Claude's list as long)
const NETWORKS_EVERY = 60000;      // ms between two looks at the networks while a remote machine shows (no login)
const NETWORKS_SOON = 5000;        // ms: a machine come or gone is looked at this soon
let working = 0;                   // the runs working, as core counted them last (runs.py's working)

/** @typedef {{ machine: string | null, network?: string | null, branch: string | null,
 * agents: ReturnType<typeof agentsSaid>, update: ReturnType<typeof updateReady>, runs?: number }} Status what the bar
 * says */

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

/** The networks looked at while the app shows a remote machine, every NETWORKS_EVERY and soon after one comes or goes:
 * core/networks.py's here on this Mac (CORE: main.js's python) with the app's own machines, checked, shared with the
 * package's folder. @param {(source: string, args: string[], root: string, on: string | null) => Promise<any>} core */
export function watchNetworks(core, cx) {
  let asked = 0, names = "", asking = false, folder = /** @type {string | null} */ (null), runs = false;
  const look = (/** @type {any} */ cx) => {
    const remote = JSON.stringify(machines().filter((m) => m.name).map((m) => m.name).sort());
    if (asking || remote === "[]" || (remote === names && Date.now() - asked < NETWORKS_EVERY)) return;
    asking = true;
    asked = Date.now();
    names = remote;
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const listed = await hc(["machine", "ls", "--json"]);
        const own = listed.code === 0 ? appMachines(JSON.parse(listed.stdout)) : [];
        const said = await core(NETWORKS, ["here", `${home()}/.config/herdr-fold/machines.txt`, ...own.flat()], home(),
          null);
        const found = setupFolder(await readTextFile(`${home()}/.config/herdr-fold/setup-folder`));
        if (found !== folder) {                   // its machines.sh looked for once a folder
          runs = Boolean(found && await readTextFile(`${found}/machines.sh`));
          folder = found;
        }
        setShared(NETWORKS_SEEN, { ...networksSeen(said), at: Date.now(), setup: runs ? folder : null });
      } catch {
        // the networks as they were: looked at again next time
      } finally {
        asking = false;
      }
    });
  };
  look(cx);
  cx.timer.every(NETWORKS_SOON, look);
}

/** The bar as the shown space, the agents (in panes and chat tabs), the runs, Herdr's updates and herdr-fold's own
 * check have it now. */
export function liveStatus(t) {
  const space = spaces().find((s) => s.active), machine = space?.machine ?? null;
  return statusBar(t, { machine, network: machine ? networkOf(shared(NETWORKS_SEEN), machine) : null,
    branch: space?.branch ?? null,
    agents: agentsSaid(barStatuses(agents(), terminals(), chatWaits().agents)),
    update: updateReady(updates(), shared(UPDATES)), runs: working });
}

/** The status bar (STATUS), on the side's level (chrome) under a hairline, 16 in and its items 16 apart, 12 in the
 * captions' tone: the machine (its network's mark before it, 6 apart), the branch, the agents' dot and words, the runs
 * working (a press shows them in Runs); at its end the update item. @param {Status} status */
export function statusBar(t, { machine, network = null, branch, agents: said, update, runs = 0 }) {
  const dot = (/** @type {string} */ color) => div().size(6).flex_none().rounded_full().bg(color);
  const role = said.role === "waiting" ? t.ansi3 : said.role === "working" ? t.accent : t.dim;
  const mark = network ? networkMark(t, network, CENTRED.barMark[1]) : null;
  return h_flex().id("status").size_full().min_w(0).px(16).gap(16).items_center().bg(t.chrome).border_t(1)
    .border_color(t.border).text_size(12).text_color(t.muted)
    .child(h_flex().flex_none().gap(6).items_center().when(Boolean(mark), (e) => e.child(mark))
      .child(machine ?? "This computer"))
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
