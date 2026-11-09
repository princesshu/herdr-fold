// @ts-check
// The chat tab: an agent's conversation drawn as a timeline from its session file (core/chat.py, read as it grows),
// the agent itself in a core terminal with no pane, started with herdr-fold's hook and status line (agents.js).
import { div } from "gpui-kit";
import { v_flex, h_flex, Textarea, TextareaState, TextView } from "gpui-base";
import { randomUUID } from "crypto";
import { exec, focused, hc, spaces, terminals, run as command } from "herdr";
import { CHAT } from "./helper.js";
import { ADAPTERS, claudeArgv, contextColor, contextLine, effortLabel, limitNotice, modelName, modeOf, promptText,
  screenChoices, screenMode } from "./agents.js";
import { Answer } from "./card.js";
import { Menus } from "./menus.js";
import { BUTTON, fold, icon, iconButton, keyCap, ring } from "./parts.js";
import { clock, setForms, timeline } from "./timeline.js";
import { CHAT_TAB, diffRows, lastLine, said } from "./logic.js";

const LABEL = "herdr-fold.chat";      // the core keeps a chat's agent under this label, its session the value
const WORKING = 500, IDLE = 2000;     // ms between two reads of the session file, while the agent works and not
const COLUMN = 760;                   // px: the timeline's width at most, in the middle of the tab
const OUTPUT = 12;                    // an open call's output: its lines shown at most
const NAME = 40;                      // a new chat tab's name: its first prompt's characters at most
const ROWS = 8;                       // the prompt's rows at most, as it grows with what is typed
const SHOWN = 200;                    // the timeline's latest rows drawn; Show earlier adds as many again
// how this Mac's user has a time written (Language & Region): macOS's own pattern for each template, asked once a run
const FORMS = "ObjC.import('Foundation'); const f = (t) => $.NSDateFormatter.dateFormatFromTemplateOptionsLocale(t, 0, "
  + "$.NSLocale.currentLocale).js; JSON.stringify({ time: f('jmm'), day: f('MMMdjmm'), year: f('yMMMdjmm'), "
  + "weekday: f('EEEMMMdjmm') })";
/** @type {Promise<any> | null} */
let forms = null;

/** This Mac's forms of a time (timeline.js's setForms), asked of macOS once; null where it cannot say. */
function systemForms() {
  forms = forms ?? exec("osascript", ["-l", "JavaScript", "-e", FORMS])
    .then((done) => (done.code === 0 ? JSON.parse(done.stdout) : null)).catch(() => null);
  return forms;
}

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
    this.shown = SHOWN;                           // the latest rows drawn
    /** px the timeline is scrolled back from its end (0: at its end, new rows in view); its own and its rows' height */
    this.back = 0;
    this.view = 0;
    this.content = 0;
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
    this.recheck = 0;                             // reads left that look at the mode on Claude's screen (a dialog's)
    /** @type {Set<string>} limit notices closed, by key */
    this.dismissed = new Set();
    /** @type {any} the bounds of the chip pressed, the menu's place */
    this.pressed = null;
    /** @type {any} the prompt (init's: a host call), and whether the cursor is in it */
    this.input = null;
    this.typing = false;
    this.blank = true;                            // the prompt empty, as last drawn: its words over it
    /** @type {Answer | null} the card in the prompt's place (init's) */
    this.answer = null;
    /** @type {string | null} the request answered last: shown no more while the hook takes the answer */
    this.answered = null;
  }

  /** Once, after tab.new has selected its tab: the agent found again (the tab drawn anew, the app opened again) or
   * started; then its file read. */
  init(cx) {
    this.input = TextareaState.new({ placeholder: "" });                // its words drawn over it (prompt())
    this.input.set_auto_grow(1, ROWS);
    this.input.on("submit", (event, cx) => {
      if (!event.shift) this.send(cx);                                     // Shift+Enter: a new line
    });
    this.input.on("change", (_e, cx) => {
      if (this.blank !== !this.input.value()) cx.notify();               // its words drawn over it, or gone
    });
    for (const [event, typing] of /** @type {const} */ ([["focus", true], ["blur", false]])) {
      this.input.on(event, (_e, cx) => {
        this.typing = typing;                     // the prompt's edge lit while the cursor is in it
        cx.notify();
      });
    }
    this.answer = new Answer((reply, cx) => this.reply(reply, cx), cx);
    cx.timer.after(0, (cx) => {
      this.tab = focused()?.tab ?? null;
      cx.spawn(async (cx) => {
        try {
          if (await this.start()) this.input.focus();         // a new chat: typing goes to its prompt
        } catch (e) {
          this.note = `Claude could not start: ${said(e)}`;
        }
        cx.notify();
      });
    });
    cx.timer.every(WORKING, (cx) => this.look(cx));
    cx.spawn(async (cx) => {
      setForms(await systemForms());              // its times as this Mac writes them
      cx.notify();
    });
  }

  get space() {
    return spaces().find((s) => s.id === this.props.space) ?? null;
  }

  get agent() {
    return terminals().find((t) => t.address === this.address) ?? null;
  }

  /** The agent found again (its tab the one it was started for; the keys left where they are, as the copy drawn anew
   * may not be shown) or started; true when started. */
  async start() {
    const space = this.space;
    if (!space?.folder) throw new Error("its space has no folder");
    if (space.machine) throw new Error("a chat runs on this Mac for now");
    const kept = terminals().find((t) => t.labels?.[LABEL] === this.session && t.state === "live");
    if (kept) {
      this.address = kept.address;
      this.tab = kept.labels?.[CHAT_TAB] ?? this.tab;
      this.recheck = 1;                           // its mode as its screen says it now
      return false;
    }
    const argv = claudeArgv({ python: await this.pythonOn(null), session: this.session,
      resume: Boolean(this.props.resume), prompt: this.props.resume ? "" : String(this.props.prompt ?? "") });
    // --rm: an agent ended (its tab closed, /exit) leaves nothing; it outlives the app quitting all the same
    const done = await hc(["run", "--bg", "--json", "--rm", "--no-parent", "--cwd", space.folder, "--label",
      `${LABEL}=${this.session}`, ...(this.tab ? ["--label", `${CHAT_TAB}=${this.tab}`] : []), "--", ...argv]);
    if (done.code !== 0) throw new Error(lastLine(done));
    this.address = JSON.parse(done.stdout).address;
    return true;
  }

  /** Every WORKING ms: the session file's new lines, what Claude waits on and the status line's numbers while the agent
   * works or a mode is asked for, every IDLE ms while it waits. */
  look(cx) {
    if (!this.address || this.reading) return;
    const waiting = ["working", "blocked"].includes(this.agent?.status);
    if (!waiting && !this.wanted && Date.now() - this.read < IDLE) return;
    this.reading = true;
    this.read = Date.now();
    cx.spawn(async (cx) => {
      try {
        const got = await this.core(CHAT, ["steps", this.session, String(this.offset)], this.space?.folder ?? "/",
          null);
        const before = JSON.stringify([this.status, this.pending, this.named]);
        this.offset = got.offset;
        this.status = got.status;
        this.pending = got.pending?.id === this.answered ? null : got.pending;
        const choices = this.pending?.kind === "dialog"           // asked in Claude's own dialog: its choices there
          ? screenChoices((await hc(["read", String(this.address)])).stdout) : undefined;
        if (!this.answer?.shows(this.pending, choices)) {
          const fresh = !this.answer?.shows(this.pending);
          this.answer?.reset(this.pending, choices);
          if (this.pending && fresh) this.answer?.focus.focus();
        }
        this.named = { model: got.model ?? this.named.model, effort: got.effort ?? this.named.effort,
          mode: got.mode ?? this.named.mode };
        await this.turn();
        if (got.steps.length) {
          this.steps.push(...got.steps);
          this.rows = timeline(this.steps);
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

  /** The mode as Claude's screen says it (its session file says one only with the next message), after a dialog, and
   * towards the mode asked for: Claude's own shift+tab, one press a read, at most once round its cycle. */
  async turn() {
    if (!(this.wanted || this.recheck) || !this.address) return;
    const now = screenMode(this.adapter, (await hc(["read", this.address])).stdout);
    if (now) this.named.mode = now;
    this.recheck = Math.max(0, this.recheck - 1);
    if (!this.wanted) return;
    if (now === this.wanted || this.presses > this.adapter.modes.length) {
      this.wanted = null;
      return;
    }
    this.presses += 1;
    await hc(["keys", this.address, "shift+tab"]);
  }

  /** REPLY (card.js's) to what Claude waits on, through the hook, or in Claude's own dialog by its key there (a No's
   * words typed after it); the card goes, the prompt comes back. */
  reply(reply, cx) {
    this.answered = reply.id;
    this.pending = null;
    this.answer?.reset(null);
    this.input.focus();                           // the card gone: the keys back to the prompt
    this.read = 0;                                // the turn goes on: read again at once
    cx.spawn(async () => {
      if (reply.key) {
        await hc(["keys", String(this.address), reply.key]);
        if (reply.text) await hc(["send", String(this.address), reply.text]);
        this.recheck = 4;                         // a dialog may change the mode: its line read off the screen
      }
      await this.core(CHAT, ["answer", this.session, JSON.stringify(reply)], this.space?.folder ?? "/", null);
    });
    cx.notify();
  }

  /** TEXT typed to the agent and sent (a working one queues it). @param {string} text */
  tell(text) {
    if (this.address) hc(["send", this.address, text]);
  }

  /** The prompt's text to the agent, the prompt emptied. */
  send(cx) {
    const text = promptText(this.input.value());
    if (!text || !this.address) return;
    this.tell(text);
    this.input.set_value("");
    cx.notify();
  }

  /** The mode chip's menu: the adapter's modes in its own words, the one in effect checked. */
  modes() {
    return this.adapter.modes.map((mode) => ({ label: mode.label, on: mode.id === this.mode?.id,
      act: () => void ((this.wanted = mode.id), (this.presses = 0)) }));
  }

  /** The model chip's menu: the adapter's efforts in its own words, the one in effect checked. */
  efforts() {
    const effort = this.status?.effort ?? this.named.effort;
    return this.adapter.efforts.map((e) => ({ label: e.label, on: e.id === effort,
      act: () => this.tell(`/effort ${e.id}`) }));
  }

  /** The / menu: the adapter's commands, sent at once, or put in the prompt when one takes words. */
  commands() {
    return this.adapter.commands.map((c) => ({ label: c.name, act: () => {
      if (!c.words) return this.tell(c.name);
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
    const frame = v_flex().id("chat").size_full().min_h(0).bg(t.canvas).text_color(t.foreground).text_size(13);
    const line = this.note ?? (this.address ? "Waiting for Claude…" : "Starting Claude…");
    return frame.child(this.rows.length ? this.timeline(t, code)
      : div().flex_1().p(24).text_size(12).text_color(this.note ? t.ansi1 : t.dim).child(line))
      .when(Boolean(this.address), (e) => e.child(this.bottom(t, code)));
  }

  /** The timeline, held at its end as rows come (GPUI's scroll areas start at their top, so it scrolls itself: its
   * rows stand on its bottom edge, BACK px below it once the wheel takes them back); its latest SHOWN rows. */
  timeline(t, code) {
    const from = Math.max(0, this.rows.length - this.shown);
    return div().id("timeline").flex_1().min_h(0).relative().overflow_hidden()
      .on_size_change((size, cx) => this.measured(size.height, this.content, cx))
      .on_scroll_wheel((event, cx) => this.scrolled(event.delta.y, cx))
      .child(v_flex().id("timeline-rows").absolute().left_0().right_0().bottom(-this.back).pb(8)
        .on_size_change((size, cx) => this.measured(this.view, size.height, cx))
        .when(from > 0, (e) => e.child(div().w_full().flex().justify_center().py(8)
          .child(div().id("earlier").px(12).py(4).rounded(10).border(1).border_color(t.border).text_size(12)
            .text_color(t.muted).cursor_pointer().hover((s) => s.bg(t.hover)).child("Show earlier")
            .on_click((_e, cx) => {
              this.shown += SHOWN;
              cx.notify();
            }))))
        .children(this.rows.slice(from).map((_row, n) => this.row(t, code, from + n))))
      .when(this.back > 0, (e) => e.child(div().absolute().bottom(16).left_0().right_0().flex().justify_center()
        .child(div().id("latest").px(12).py(4).rounded(10).bg(t.raised).border(1).border_color(t.border)
          .text_size(12).cursor_pointer().hover((s) => s.bg(t.hover)).child("Jump to latest")
          .on_click((_e, cx) => {
            this.back = 0;
            cx.notify();
          }))));
  }

  /** The timeline VIEW px high, its rows CONTENT px: rows come while scrolled back keep the reader's place. */
  measured(view, content, cx) {
    if (view === this.view && content === this.content) return;
    if (this.back > 0 && content > this.content) this.back += content - this.content;
    this.view = view;
    this.content = content;
    this.back = Math.min(this.back, Math.max(0, content - view));
    cx.notify();
  }

  /** The wheel's DY px: back into the conversation, or towards its end; never past either. */
  scrolled(dy, cx) {
    const back = Math.min(Math.max(0, this.back + dy), Math.max(0, this.content - this.view));
    if (back === this.back) return;
    this.back = back;
    cx.notify();
  }

  /** Under the timeline, as wide as its column: a usage limit near its end, then what Claude waits on in the prompt's
   * place, else the prompt and its bar. */
  bottom(t, code) {
    const notice = limitNotice(this.status, this.dismissed);
    return div().w_full().flex().justify_center().px(24).pb(16).pt(8)
      .child(v_flex().w_full().max_w(COLUMN).gap(8)
        .when(Boolean(notice), (e) => e.child(h_flex().px(12).py(6).gap(8).rounded(8).bg(t.ansi3 + "1f")
          .border(1).border_color(t.ansi3 + "40").text_size(12).text_color(t.ansi3)
          .child(div().flex_1().min_w(0).child(notice?.text ?? ""))
          .child(iconButton(t, "notice-close", "x", "Close", (cx) => {
            if (notice) this.dismissed.add(notice.key);
            cx.notify();
          }, { size: 12, color: t.ansi3 }))))
        .child(this.answer?.card ? this.answer.render(t, code) : this.prompt(t)));
  }

  /** The prompt: what is typed, its words while empty (the agent's name; a working one queues a message, Esc stops
   * it), its bar. */
  prompt(t) {
    const working = this.agent?.status === "working";
    this.blank = !this.input.value();
    return v_flex().id("prompt").rounded(10).border(1).border_color(this.typing ? t.accent : t.border).bg(t.surface)
      .on_key_down((e) => void (e.key === "escape" && working && hc(["interrupt", String(this.address)])))
      .child(div().relative().child(Textarea.new(this.input).px(12).pt(8).text_size(13))
        .when(this.blank, (e) => e.child(h_flex().absolute().top(8).left(12).gap(6).items_center().text_size(13)
          .text_color(t.dim).when(working, (e) => e.child("Queue another message ·").child(keyCap(t, "esc"))
            .child("to interrupt")).when(!working, (e) => e.child(`Message ${this.adapter.name}`)))))
      .child(this.bar(t));
  }

  /** The prompt's bar: the commands, the context ring (its numbers and Compact a click away), the model and its
   * effort (the efforts' menu), the mode (the modes' menu), send or stop. */
  bar(t) {
    const context = this.status?.context, mode = this.mode, working = this.agent?.status === "working";
    const effort = this.status?.effort ?? this.named.effort;
    const model = this.status?.model ?? modelName(this.named.model ?? "");
    const tone = { green: t.ansi2, yellow: t.ansi3, red: t.ansi1 }[contextColor(context ?? 0)];
    const pressable = (/** @type {string} */ id, /** @type {(cx: any) => void} */ act) => h_flex().id(id).h(28)
      .px(8).gap(6).items_center().rounded(6).text_size(12).cursor_pointer()
      .on_mouse_down("left", (e, cx) => {
        cx.stop_propagation();
        this.pressed = e.bounds;
      }).on_click((_e, cx) => act(cx));
    return h_flex().px(8).pb(8).pt(4).gap(4).items_center()
      .child(iconButton(t, "commands", "square-slash", "Commands", () => this.menus.open(this.commands(), this.pressed),
        { size: 16 }).on_mouse_down("left", (e) => void (this.pressed = e.bounds)))
      .when(typeof context === "number", (e) => e.child(div().id("context").size(BUTTON).flex_none().flex()
        .items_center().justify_center().rounded(6).cursor_pointer().hover((s) => s.bg(t.hover))
        .tooltip(`Context ${contextLine(this.status)}`)
        .on_mouse_down("left", (ev, cx) => {
          cx.stop_propagation();
          this.pressed = ev.bounds;
        })
        .on_click(() => this.menus.open([{ label: "Compact the conversation", act: () => this.tell("/compact") }],
          this.pressed, { label: "Context", note: contextLine(this.status) }))
        .child(ring(t, Number(context), tone))))
      .child(div().flex_1())
      .when(Boolean(model), (e) => e.child(pressable("model", () => this.menus.open(this.efforts(), this.pressed))
        .bg(t.raised).hover((s) => s.bg(t.hover)).child(div().text_color(t.foreground).child(model))
        .when(Boolean(effort), (e) => e.child(div().text_color(t.muted).child(effortLabel(this.adapter,
          String(effort)))))))
      .when(Boolean(mode), (e) => e.child(pressable("mode", () => this.menus.open(this.modes(), this.pressed))
        .text_color(t.foreground).hover((s) => s.bg(t.hover)).child(icon(mode?.icon ?? "hand", 14))
        .child(mode?.label ?? "").child(icon("chevron-down", 12).text_color(t.dim))))
      .child(div().id(working ? "stop" : "send").size(28).flex_none().flex().items_center().justify_center()
        .rounded(6).bg(t.raised).text_color(t.foreground).cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => (working ? void hc(["interrupt", String(this.address)]) : this.send(cx)))
        .child(working ? div().size(10).rounded(4).bg(t.foreground) : icon("arrow-up", 14)));
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
    return column(h_flex().id(`row-${index}`).items_start().gap(8)
      .when(this.opens(index), (e) => e.cursor_pointer().on_click((_e, cx) => {
        this.opened.set(this.key(index), !this.isOpen(index));
        cx.notify();
      }))
      .child(this.dot(t, row))
      .child(v_flex().flex_1().min_w(0).py(4).gap(6).child(this.body(t, code, row, index))));
  }

  /** Whether ROW is a call still running: its agent at work, no outcome yet. */
  running(row) {
    return row.ok === null && this.agent?.status === "working";
  }

  /** Whether ROW is a call waiting on the person: its agent asks, no outcome yet. */
  waiting(row) {
    return row.ok === null && this.agent?.status === "blocked";
  }

  /** The row's dot on the timeline's line, by its first line of words (the agent's text's, under its time): done
   * green, failed red, running the accent, waiting on the person yellow and hesitating, else gray. */
  dot(t, row) {
    const running = this.running(row), waiting = this.waiting(row);
    const color = row.ok === true ? t.done : row.ok === false ? t.ansi1 : waiting ? t.ansi3 : running ? t.accent
      : t.dim;
    const top = row.kind === "text" ? 28 : 10;
    return div().w(10).flex_none().self_stretch().relative()
      .child(div().absolute().top_0().bottom_0().left(4).w(1).bg(t.border))
      .child(div().absolute().top(top).left(1).w(7).h(7).rounded(4).bg(t.canvas))   // hides the line as the dot fades
      .child(div().absolute().top(top).left(1).w(7).h(7).rounded(4).bg(color)
        .when(waiting, (e) => e.loop("opacity", { from: 0.35, to: 1, period: 1200 })));
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
      .when(this.running(row), (e) => e.child(div().flex_none().text_size(11).text_color(t.dim).child("running…")))
      .when(this.waiting(row), (e) => e.child(div().flex_none().text_size(11).text_color(t.ansi3)
        .child("waiting for you")))
      .when(this.opens(index), (e) => e.child(fold(`row-${index}-fold`, this.isOpen(index), 12, t.dim)));
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
    return div().px(8).py(6).rounded(6).border(1).border_color(t.border).bg(t.background).font_family(code)
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
    return v_flex().rounded(6).border(1).border_color(t.border).bg(t.background).overflow_hidden()
      .child(h_flex().px(8).py(4).gap(8).border_b(1).border_color(t.border).text_size(12)
        .child(div().flex_1().min_w(0).truncate().text_color(t.muted).child(change.path))
        .child(div().text_color(t.ansi2).child(`+${added}`)).child(div().text_color(t.ansi1).child(`−${removed}`)))
      .child(v_flex().py(4).font_family(code).text_size(12).children(diffRows(change.lines).map(line)));
  }
}
