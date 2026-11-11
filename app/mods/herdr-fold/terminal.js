// @ts-check
// The focused tab's own terminal under herdr-fold's views, as the TUI's right column has one per tab: the layout's
// fold-terminals stack holds a block per tab; its header, 0 high and always shown with it, picks it (this part).
import { div } from "gpui-kit";
import { focused, spaces, terminals, machines, layout, hc, shared, setShared, run as command } from "herdr";
import { lastLine, machineOf, orphanChats, said, strays, TERMINALS, terminalId, withoutTabs, withTerminal }
  from "./logic.js";
import { PAD } from "./parts.js";

const LABEL = "herdr-fold.tab";    // the core keeps a tab's terminal by this label, the tab's id its value
const NOTE = "herdr-fold.terminal";      // why the focused tab has no terminal, for the stack's stand-in to say

/** The live terminal at ADDRESS, if any. @param {string | null} address */
const live = (address) => terminals().find((t) => t.address === address && t.state === "live");

/** The terminals started for tabs, by tab: the app lists a new one a moment later, and a copy started over meanwhile
 * (a layout change does that) must not start another. @type {Map<string, Promise<string>>} */
const started = new Map();

/** TAB's terminal: the live one its label names, else the one started for it (unless it has ended since), else a new
 * one. @param {string} tab @param {any} space */
async function terminalOf(tab, space) {
  const labelled = terminals().find((t) => t.labels?.[LABEL] === tab && t.state === "live");
  if (labelled) return labelled.address;
  const earlier = started.get(tab);
  if (earlier) {
    const address = await earlier, listed = terminals().find((t) => t.address === address);
    if (!listed || listed.state === "live") return address;
  }
  const next = start(tab, space);
  started.set(tab, next);
  next.catch(() => started.delete(tab));
  return next;
}

export class TerminalFollower {
  constructor() {
    /** @type {string | null} the tab whose terminal shows */
    this.tab = null;
    /** @type {string | null} */
    this.address = null;
    this.starting = false;
    this.due = false;
  }

  /** @returns {string | null} why the tab has no terminal */
  get note() {
    return /** @type {string | null} */ (shared(NOTE) ?? null);
  }

  /** From render: the focused tab's terminal followed once the render is over (that changes the layout and redraws);
   * again when it has ended (exit). A tab whose terminal could not start waits for the next look. */
  watch(cx) {
    const tab = focused()?.tab;
    if (!tab || this.due || this.starting || (tab === this.tab && (live(this.address) || this.note))) return;
    this.due = true;
    cx.timer.after(0, (cx) => {
      this.due = false;
      this.follow(cx);
    });
  }

  /** Every so often: the terminals of closed tabs tidied, a start that failed tried again. */
  look(cx) {
    this.tidy();
    if (this.note) this.tab = null;
    this.watch(cx);
  }

  /** The focused tab's terminal shown: the one its label names, else one started in the tab's folder on its machine. */
  follow(cx) {
    const tab = focused()?.tab;
    if (!tab || this.starting) return;
    const space = spaces().find((s) => s.tabs?.some((t) => t.id === tab)) ?? null;
    this.starting = true;
    this.tab = tab;
    cx.spawn(async (cx) => {
      try {
        const address = await terminalOf(tab, space);
        const next = withTerminal(layout(), tab, address);
        if (next.changed) command("layout.set", { layout: next.tree });
        command("layout.select", { stack: TERMINALS, child: terminalId(tab) });
        this.address = address;
        if (this.note) setShared(NOTE, null);
      } catch (e) {
        setShared(NOTE, `No terminal: ${said(e)}`);
        command("layout.select", { stack: TERMINALS, child: "fold-terminal-none" });
        this.address = null;
      } finally {
        this.starting = false;
        cx.notify();
      }
    });
  }

  /** The terminals of tabs closed since, any second one a tab got, and the agents of chat tabs closed since: ended,
   * and out of the stack. A machine away lists no tabs, so its terminals stay until it is back. */
  tidy() {
    const shown = spaces();
    if (!shown.length) return;
    const tabs = shown.flatMap((s) => (s.tabs ?? []).map((t) => t.id));
    const reachable = new Set(machines().filter((m) => m.layout === "ready").map((m) => m.name));
    const labelled = terminals().filter((t) => t.labels?.[LABEL])
      .map((t) => ({ address: t.address, tab: t.labels[LABEL], live: t.state === "live" }));
    const closed = labelled.filter((t) => t.live && !tabs.includes(t.tab)).map((t) => t.address);
    for (const address of [...closed, ...strays(layout(), labelled), ...orphanChats(terminals(), tabs)]) {
      if (reachable.has(machineOf(address))) hc(["kill", "--", address]);
    }
    for (const t of labelled) if (!tabs.includes(t.tab)) started.delete(t.tab);
    const next = withoutTabs(layout(), tabs, reachable);
    if (next.gone.length) command("layout.set", { layout: next.tree });
  }
}

/** The stack's stand-in, shown while the focused tab has no terminal: why (NOTE), if it could not start.
 * @param {string | null} [note] */
export const standIn = (t, note = /** @type {string | null} */ (shared(NOTE) ?? null)) =>
  div().size_full().p(PAD).text_size(12).text_color(t.ansi1).child(note ?? "");

/** A terminal for TAB of SPACE, in its folder on its machine, with that machine's own shell; kept by the core (a lost
 * one gets a shell in its place) under herdr-fold's label. Its address, the machine's name and all.
 * @param {string} tab @param {any} space */
async function start(tab, space) {
  const on = space?.machine ?? null;
  const started = await hc(["run", "--bg", "--json", "--keep", "--no-parent", "--label", `${LABEL}=${tab}`,
    ...(space?.folder ? ["--cwd", space.folder] : []), ...(on ? ["--on", on] : [])]);
  if (started.code !== 0) throw new Error(lastLine(started));
  return JSON.parse(started.stdout).address;
}
