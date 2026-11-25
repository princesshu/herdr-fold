// @ts-check
// The Agents tab's Runs' rules (runsview.js draws them): which runs a scope shows, the buttons a run's properties
// offer, the sentence under New run's choices, the status bar's words. The runs themselves are core's (runs.py).

export const LIVE = ["running", "blocked"];         // the states of a run that works now (runs.py's)

/** A run as core lists it (runs.py's row(): its words too). @typedef {{ key: string, agent: string, kind: string,
 * state: string, title: string, prompt: string, folder: string, place: string, files: string[], media: { path: string,
 * kind: string }[], pr: { number: number, url: string } | null, url?: string, [word: string]: any }} Run */

/** What the form under the list holds while New run is open. @typedef {{ agent: string, where: string,
 * when: string, env: string | null, busy: boolean, note: import("./parts.js").Note | null }} Form */

/** Whether RUN, from a space's FOLDER (null: every space's), is shown with AGENT's filter (null: every agent's): its
 * folder in it, a cloud task by its environment's name. @param {Run} run @param {string | null} folder
 * @param {string | null} agent */
export const runShown = (run, folder, agent) => (!agent || run.agent === agent) && (!folder
  || (run.kind === "cloud" ? run.place === folder.split("/").pop() : run.folder === folder
    || run.folder.startsWith(`${folder}/`)));

/** The buttons RUN's properties offer, as [id, label, look]: Attach and Stop while Claude's session works; Open as
 * chat, Run again, Remove once it ended; a cloud task's Show diff, Apply to INTO (the space's folder's name) and
 * Open on the web; a PR it opened. @param {Run} run @param {string} into */
export function runActions(run, into) {
  const live = LIVE.includes(run.state), cloud = run.kind === "cloud";
  return /** @type {[string, string, string][]} */ ([
    ...(run.kind === "background" && live ? [["attach", "Attach", "raised"], ["stop", "Stop", "raised"]] : []),
    ...(!cloud && !live ? [["chat", "Open as chat", "raised"], ["again", "Run again", "raised"]] : []),
    ...(cloud && ["ready", "applied"].includes(run.state) ? [["diff", "Show diff", "raised"]] : []),
    ...(cloud && run.state === "ready" ? [["apply", `Apply to ${into}`, "raised"]] : []),
    ...(cloud && run.state === "failed" ? [["again", "Run again", "raised"]] : []),
    ...(run.pr ? [["pr", `Open PR #${run.pr.number}`, "plain"]] : []),
    ...(cloud && run.url ? [["web", "Open on the web", "plain"]] : []),
    ...(run.kind === "background" && !live ? [["remove", "Remove", "plain"]] : [])]);
}

/** The sentence under New run's choices: what starts where, as the agent does it. @param {Form} form
 * @param {string} into */
export function formNote(form, into) {
  if (form.agent === "claude" && form.when === "schedule") {
    return "Claude keeps schedules in the cloud (routines). A new chat opens with /schedule and your words; Claude "
      + "asks when and where there. Their runs are not listed here.";
  }
  if (form.agent === "codex" && form.when === "schedule") return "Codex schedules only in its own app.";
  if (form.agent === "claude") return "Runs on this Mac in the background; Attach shows it as it works, Stop ends it.";
  return form.where === "cloud" ? `Codex makes a diff in the cloud; Apply brings it into ${into}.`
    : "Runs on this Mac with codex exec, on its own; it shows here as it works.";
}

/** The status bar's words for N runs working: 1 run working, 2 runs working. @param {number} n */
export const runsWorking = (n) => `${n} run${n === 1 ? "" : "s"} working`;
