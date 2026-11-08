// @ts-check
// The chat tab: an agent's conversation drawn as a timeline from its session file (core/chat.py, read as it grows),
// the agent itself in a core terminal with no pane, started with herdr-fold's hook and status line (agents.js).
import { div, list } from "gpui-kit";
import { v_flex, h_flex, Scrollbar, Textarea, TextareaState, TextView, VirtualListScrollHandle } from "gpui-base";
import { randomUUID } from "crypto";
import { focused, hc, spaces, terminals, run as command } from "herdr";
import { CHAT } from "./helper.js";
import { ADAPTERS, claudeArgv, contextColor, effortLabel, limitNotice, modelName, modeOf, promptText }
  from "./agents.js";
import { Menus } from "./menus.js";
import { icon, iconButton } from "./parts.js";
import { clock, timeline } from "./timeline.js";
import { CHAT_TAB, diffRows, lastLine, said } from "./logic.js";

const LABEL = "herdr-fold.chat";      // the core keeps a chat's agent under this label, its session the value
const WORKING = 500, IDLE = 2000;     // ms between two reads of the session file, while the agent works and not
const COLUMN = 760;                   // px: the timeline's width at most, in the middle of the tab
const OUTPUT = 12;                    // an open call's output: its lines shown at most
const NAME = 40;                      // a new chat tab's name: its first prompt's characters at most
const ROWS = 8;                       // the prompt's rows at most, as it grows with what is typed

/** A new chat tab in SPACE (its id): AGENT's conversation SESSION, a new one (and its first PROMPT) or one it resumes.
 * @param {{ space: string, agent?: string, session?: string, resume?: boolean, prompt?: string,
 *   name?: string }} chat */
export function openChat({ space, agent = "claude", session = randomUUID(), resume = false, prompt = "",
  name = "" }) {
  const first = prompt.split("\n")[0].trim();
  command("tab.new", { name: name || (first.length > NAME ? `${first.slice(0, NAME - 1)}…` : first) || "New chat",
    mod: "herdr-fold", props: { part: "chat", space, agent, session, resume, prompt } });
}

export class Chat {
  /** The chat tab PROPS opened (openChat's); CORE runs core/'s code (main.js's python), PYTHON_ON names the Python
   * there. @param {any} props @param {(source: string, args: string[], root: string, on: string | null) =>
   * Promise<any>} core @param {(on: string | null) => Promise<string>} pythonOn */
  constructor(props, core, pythonOn) {
    this.props = props;
    this.core = core;
    this.pythonOn = pythonOn;
    this.session = String(props.session);
    /** @type {string | null} the tab it is drawn in: the one focused once tab.new has selected it */
    this.tab = null;
    /** @type {string | null} the agent's terminal */
    this.address = null;
    /** @type {any[]} core/chat.py's steps so far, and where its next read starts */
    this.steps = [];
    this.offset = 0;
    /** @type {import("./timeline.js").Moment[]} */
    this.rows = [];
    this.reading = false;
    this.read = 0;                                // when the session file was last read
    /** @type {Map<string, boolean>} rows opened or folded by a click, by key */
    this.opened = new Map();
    this.following = true;                        // the timeline kept at its latest row
    this.scroll = VirtualListScrollHandle.new();
    /** @type {string | null} why there is no chat */
    this.note = null;
    this.adapter = ADAPTERS[String(props.agent)] ?? ADAPTERS.claude;
    this.menus = new Menus();                     // the mode's, the commands'
    /** @type {any} the status line's numbers (core/chat.py's status); what Claude waits on (Task 7's cards) */
    this.status = null;
    this.pending = null;
    /** @type {{ model: string | null, effort: string | null, mode: string | null }} as the session file names them */
    this.named = { model: null, effort: null, mode: null };
    /** @type {string | null} the mode asked for, and the shift+tab presses made towards it */
    this.wanted = null;
    this.presses = 0;
    /** @type {Set<string>} limit notices closed, by key */
    this.dismissed = new Set();
    /** @type {any} the bounds of the chip pressed, the menu's place */
    this.pressed = null;
    /** @type {any} the prompt (init's: a host call) */
    this.input = null;
  }

  /** Once, after tab.new has selected its tab: the agent found again (the tab drawn anew, the app opened again) or
   * started; then its file read. */
  init(cx) {
    this.input = TextareaState.new({ placeholder: "Message Claude" });
    this.input.set_auto_grow(1, ROWS);
    this.input.on("submit", (event, cx) => {
      if (!event.shift) this.send(cx);                                     // Shift+Enter: a new line
    });
    cx.timer.after(0, (cx) => {
      this.tab = focused()?.tab ?? null;
      cx.spawn(async (cx) => {
        try {
          await this.start();
        } catch (e) {
          this.note = `Claude could not start: ${said(e)}`;
        }
        cx.notify();
      });
    });
    cx.timer.every(WORKING, (cx) => this.look(cx));
  }

  get space() {
    return spaces().find((s) => s.id === this.props.space) ?? null;
  }

  get agent() {
    return terminals().find((t) => t.address === this.address) ?? null;
  }

  async start() {
    const space = this.space;
    if (!space?.folder) throw new Error("its space has no folder");
    if (space.machine) throw new Error("a chat runs on this Mac for now");
    const kept = terminals().find((t) => t.labels?.[LABEL] === this.session && t.state === "live");
    if (kept) return void (this.address = kept.address);
    const argv = claudeArgv({ python: await this.pythonOn(null), session: this.session,
      resume: Boolean(this.props.resume), prompt: this.props.resume ? "" : String(this.props.prompt ?? "") });
    const done = await hc(["run", "--bg", "--json", "--keep", "--no-parent", "--cwd", space.folder, "--label",
      `${LABEL}=${this.session}`, ...(this.tab ? ["--label", `${CHAT_TAB}=${this.tab}`] : []), "--", ...argv]);
    if (done.code !== 0) throw new Error(lastLine(done));
    this.address = JSON.parse(done.stdout).address;
  }

  /** Every WORKING ms: the session file's new lines, what Claude waits on and the status line's numbers while the agent
   * works or a mode is asked for, every IDLE ms while it waits. */
  look(cx) {
    if (!this.address || this.reading) return;
    if (this.agent?.status !== "working" && !this.wanted && Date.now() - this.read < IDLE) return;
    this.reading = true;
    this.read = Date.now();
    cx.spawn(async (cx) => {
      try {
        const got = await this.core(CHAT, ["steps", this.session, String(this.offset)], this.space?.folder ?? "/",
          null);
        const before = JSON.stringify([this.status, this.pending, this.named]);
        this.offset = got.offset;
        this.status = got.status;
        this.pending = got.pending;
        this.named = { model: got.model ?? this.named.model, effort: got.effort ?? this.named.effort,
          mode: got.mode ?? this.named.mode };
        this.turn();
        if (got.steps.length) {
          this.steps.push(...got.steps);
          this.rows = timeline(this.steps);
          if (this.following) this.scroll.scroll_to_bottom();
        }
        if (got.steps.length || before !== JSON.stringify([this.status, this.pending, this.named])) cx.notify();
      } catch (e) {
        this.note = said(e);
        cx.notify();
      } finally {
        this.reading = false;
      }
    });
  }

  /** The mode in effect, as the adapter names it; null before the session file says. */
  get mode() {
    return this.named.mode ? modeOf(this.adapter, this.named.mode) : null;
  }

  /** Towards the mode asked for: Claude's own shift+tab, one press a read, until the session file names it (the cycle
   * is Claude's, so at most once round). */
  turn() {
    if (!this.wanted) return;
    if (this.mode?.id === this.wanted || this.presses > this.adapter.modes.length) {
      this.wanted = null;
      return;
    }
    this.presses += 1;
    hc(["keys", String(this.address), "shift+tab"]);
  }

  /** The prompt's text to the agent (a working one queues it), the prompt emptied, the timeline back at its end. */
  send(cx) {
    const text = promptText(this.input.value());
    if (!text || !this.address) return;
    hc(["send", this.address, text]);
    this.input.set_value("");
    this.following = true;
    this.scroll.scroll_to_bottom();
    cx.notify();
  }

  /** The mode's menu: the adapter's modes, then its efforts, each in its own words, the one in effect checked. */
  modes() {
    const effort = this.status?.effort ?? this.named.effort;
    return [...this.adapter.modes.map((mode) => ({ label: mode.label, on: mode.id === this.mode?.id,
      act: () => void ((this.wanted = mode.id), (this.presses = 0)) })),
    { label: "Effort", off: true }, ...this.adapter.efforts.map((e) => ({ label: e.label, on: e.id === effort,
      act: () => void hc(["send", String(this.address), `/effort ${e.id}`]) }))];
  }

  /** The / menu: the adapter's commands, one put in the prompt for its arguments. */
  commands() {
    return this.adapter.commands.map((c) => ({ label: c.name, act: () => {
      this.input.set_value(`${c.name} `);
      this.input.focus();
    } }));
  }

  /** A row's key, its place in the timeline (rows only ever come after it). @param {number} index */
  key = (index) => String(index);

  /** Whether row INDEX is open: as clicked, else as it starts. @param {number} index */
  isOpen(index) {
    return this.opened.get(this.key(index)) ?? Boolean(this.rows[index]?.open);
  }

  render(t, code) {
    const frame = v_flex().id("chat").size_full().min_h(0).bg(t.surface).text_color(t.foreground).text_size(13);
    const line = this.note ?? (this.address ? "Waiting for Claude…" : "Starting Claude…");
    return frame.child(this.rows.length ? this.timeline(t, code)
      : div().flex_1().p(24).text_size(12).text_color(this.note ? t.ansi1 : t.dim).child(line))
      .when(Boolean(this.address), (e) => e.child(this.bottom(t)));
  }

  timeline(t, code) {
    return div().flex_1().min_h(0).relative()
      .child(list("timeline", this.rows.length, this.key, (index) => this.row(t, code, index))
        .track_scroll(this.scroll).size_full()
        .on_item_click((key, cx) => {
          this.opened.set(key, !this.isOpen(Number(key)));
          cx.notify();
        })
        .on_scroll_wheel((event, cx) => {
          if (event.delta.y > 0 && this.following) {          // up: the reader stays where they went
            this.following = false;
            cx.notify();
          }
        }))
      .child(Scrollbar.vertical("timeline").absolute().inset_0())
      .when(!this.following, (e) => e.child(div().absolute().bottom(16).left_0().right_0().flex().justify_center()
        .child(div().id("latest").px(12).py(4).rounded(10).bg(t.raised).border(1).border_color(t.border)
          .text_size(12).cursor_pointer().hover((s) => s.bg(t.hover)).child("Jump to latest")
          .on_click((_e, cx) => {
            this.following = true;
            this.scroll.scroll_to_bottom();
            cx.notify();
          }))));
  }

  /** Under the timeline, as wide as its column: a usage limit near its end, then the prompt and its bar. */
  bottom(t) {
    const notice = limitNotice(this.status, this.dismissed);
    return div().w_full().flex().justify_center().px(24).pb(16).pt(8)
      .child(v_flex().w_full().max_w(COLUMN).gap(8)
        .when(Boolean(notice), (e) => e.child(h_flex().px(12).py(6).gap(8).rounded(8).border(1)
          .border_color(t.blocked).text_size(12).text_color(t.blocked)
          .child(div().flex_1().min_w(0).child(notice?.text ?? ""))
          .child(iconButton(t, "notice-close", "x", "Close", (cx) => {
            if (notice) this.dismissed.add(notice.key);
            cx.notify();
          }, { size: 12, color: t.blocked }))))
        .child(v_flex().rounded(10).border(1).border_color(t.border).bg(t.raised)
          .child(Textarea.new(this.input).px(12).pt(8).text_size(13))
          .child(this.bar(t))));
  }

  /** The prompt's bar: the commands, the context in use in its color, the model and effort, the mode, send or stop. */
  bar(t) {
    const context = this.status?.context, mode = this.mode, working = this.agent?.status === "working";
    const effort = this.status?.effort ?? this.named.effort;
    const model = [this.status?.model ?? modelName(this.named.model ?? ""), effort && effortLabel(this.adapter, effort)]
      .filter(Boolean).join(" ");
    const tone = { green: t.ansi2, yellow: t.ansi3, red: t.ansi1 }[contextColor(context ?? 0)];
    const chip = (/** @type {string} */ id, /** @type {(cx: any) => void} */ act) => h_flex().id(id).h(26).px(8)
      .gap(6).items_center().rounded(6).text_size(12).text_color(t.muted).cursor_pointer()
      .hover((s) => s.bg(t.hover).text_color(t.foreground))
      .on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();
        this.pressed = e.bounds;
      }).on_click((_e, cx) => act(cx));
    return h_flex().px(8).pb(8).gap(4).items_center()
      .child(chip("commands", () => this.menus.open(this.commands(), this.pressed)).font_family("Menlo").child("/"))
      .when(typeof context === "number", (e) => e.child(h_flex().px(8).gap(4).text_size(12).text_color(t.dim)
        .child("context").child(div().text_color(tone).child(`${context}%`))))
      .child(div().flex_1())
      .when(Boolean(model), (e) => e.child(div().px(8).text_size(12).text_color(t.dim).child(model)))
      .when(Boolean(mode), (e) => e.child(chip("mode", () => this.menus.open(this.modes(), this.pressed))
        .child(icon(mode?.icon ?? "hand", 12)).child(mode?.label ?? "")
        .child(icon("chevron-down", 12).text_color(t.dim))))
      .child(working ? iconButton(t, "stop", "square", "Stop", () => void hc(["interrupt", String(this.address)]))
        : iconButton(t, "send", "arrow-up", "Send", (cx) => this.send(cx)));
  }

  /** Row INDEX in the timeline's column: the person's message boxed, the agent's text with its time, a step on the
   * line with its dot. */
  row(t, code, index) {
    const row = this.rows[index], when = clock(row.at);
    const column = (/** @type {any} */ inner) => div().w_full().flex().justify_center().px(24)
      .child(div().w_full().max_w(COLUMN).child(inner));
    if (row.kind === "user") {
      return column(v_flex().pt(16).pb(8).gap(4)
        .child(div().text_right().text_size(11).text_color(t.dim).child(when))
        .child(div().px(12).py(8).rounded(8).border(1).border_color(t.border).bg(t.raised).child(row.text)));
    }
    return column(h_flex().items_start().gap(8)
      .child(this.dot(t, row))
      .child(v_flex().flex_1().min_w(0).py(4).gap(6).child(this.body(t, code, row, index))));
  }

  /** Whether ROW is a call still running: its agent at work, no outcome yet. */
  running(row) {
    return row.ok === null && this.agent?.status === "working";
  }

  /** The row's dot on the timeline's line: done green, failed red, running the accent and breathing, else gray. */
  dot(t, row) {
    const running = this.running(row);
    const color = row.ok === true ? t.done : row.ok === false ? t.ansi1 : running ? t.accent : t.dim;
    return div().w(10).flex_none().self_stretch().relative()
      .child(div().absolute().top_0().bottom_0().left(4).w(1).bg(t.border))
      .child(div().absolute().top(10).left(1).w(7).h(7).rounded(4).bg(color)
        .when(running, (e) => e.loop("opacity", { from: 0.35, to: 1, period: 1200 })));
  }

  /** Whether row INDEX has more to show than its line: a change, an output. */
  opens(index) {
    const row = this.rows[index];
    return Boolean(row.change || (row.output && ["tool", "agent"].includes(row.kind)));
  }

  /** What a step says: a thought dim, a call's name bold with its main argument and, when it has more, a chevron
   * (open: its change or its output), the agent's text as markdown with its time. */
  body(t, code, row, index) {
    const head = (/** @type {string} */ name, /** @type {string | null | undefined} */ main) => h_flex().gap(8)
      .child(div().flex_none().font_semibold().child(name))
      .child(div().flex_1().min_w(0).truncate().font_family(code).text_size(12).text_color(t.muted)
        .child(main ? String(main) : ""))
      .when(this.opens(index), (e) => e.child(icon(this.isOpen(index) ? "chevron-down" : "chevron-right", 12)
        .text_color(t.dim)));
    if (row.kind === "thought") return div().text_color(t.dim).child(row.label);
    if (row.kind === "text") {
      return v_flex().gap(4).child(div().text_right().text_size(11).text_color(t.dim).child(clock(row.at)))
        .child(TextView.markdown(`text-${index}`, row.text));
    }
    if (row.kind === "other") return h_flex().gap(8).text_color(t.dim).child(row.summary || row.type);
    if (row.kind === "skill") return head("Skill", row.name);
    if (row.kind === "agent") return v_flex().gap(4).child(head(row.name ?? "Agent", row.task))
      .when(this.isOpen(index) && Boolean(row.output), (e) => e.child(this.output(t, code, row.output)));
    if (row.kind === "todo") {
      return v_flex().gap(2).child(head("Todos", null)).children((row.items ?? []).map((item) => h_flex().gap(8)
        .text_color(item.done ? t.dim : t.foreground).child(item.done ? "☑" : "☐").child(item.text)));
    }
    const open = this.isOpen(index);
    return v_flex().gap(6).child(head(row.name, row.main))
      .when(open && Boolean(row.change), (e) => e.child(this.change(t, code, row.change)))
      .when(open && !row.change && Boolean(row.output), (e) => e.child(this.output(t, code, row.output)));
  }

  /** A call's output, its first OUTPUT lines, as code. @param {string} text */
  output(t, code, text) {
    const lines = text.split("\n");
    const shown = lines.length > OUTPUT ? [...lines.slice(0, OUTPUT), `… ${lines.length - OUTPUT} more lines`] : lines;
    return div().px(8).py(6).rounded(6).border(1).border_color(t.border).bg(t.canvas).font_family(code)
      .text_size(12).text_color(t.muted).child(shown.join("\n"));
  }

  /** A file's change as the preview's diff: its path and counts on top, its lines numbered by the file.
   * @param {{ path: string, lines: string[] }} change */
  change(t, code, change) {
    const added = change.lines.filter((l) => l.startsWith("+")).length;
    const removed = change.lines.filter((l) => l.startsWith("-")).length;
    const line = ({ kind, number, text }) => kind === "gap" ? div().h(8)
      : h_flex().w_full().gap(12).px(8).when(kind === "+", (e) => e.bg(t.ansi2 + "18"))
        .when(kind === "-", (e) => e.bg(t.ansi1 + "18"))
        .child(div().w(32).flex_none().text_right().text_color(t.dim).child(number === undefined ? "" : String(number)))
        .child(div().w(10).flex_none().text_color(kind === "+" ? t.ansi2 : kind === "-" ? t.ansi1 : t.dim)
          .child(kind === "+" || kind === "-" ? kind : ""))
        .child(div().flex_1().min_w(0).truncate().child(text));
    return v_flex().rounded(6).border(1).border_color(t.border).bg(t.canvas).overflow_hidden()
      .child(h_flex().px(8).py(4).gap(8).border_b(1).border_color(t.border).text_size(12)
        .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(change.path))
        .child(div().text_color(t.ansi2).child(`+${added}`)).child(div().text_color(t.ansi1).child(`−${removed}`)))
      .child(v_flex().py(4).font_family(code).text_size(12).children(diffRows(change.lines).map(line)));
  }
}
