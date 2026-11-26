// @ts-check
// The Agents tab's Runs (runs.html's): the agents' background and cloud runs, a row each under its day, the chosen
// one's properties at the list's foot and New run's form in their place. The runs and their words are core's (runs.py).
import { div, image } from "gpui-kit";
import { h_flex, v_flex, ScrollHandle, Textarea, TextareaState } from "gpui-base";
import { home, run as command, spaces } from "herdr";
import { openChat } from "./chat.js";
import { showChat } from "./chats.js";
import { MEDIA, RUNS } from "./helper.js";
import { chosenFill, toneInk, usageAgents } from "./layers.js";
import { primaryLit, said } from "./logic.js";
import { actButton, button, footNote, icon, keepNote, PAD, segmented, small, spinner } from "./parts.js";
import { showPreview } from "./preview.js";
import { formNote, LIVE, runActions, runShown } from "./runs.js";

/** @typedef {import("./runs.js").Run} Run */
/** @typedef {import("./runs.js").Form} Form */

const POLL = 30000, QUICK = 5000;  // ms between two reads while it shows; while a run works
const WIDE = 1000;                 // px: the list's column at most, as Usage's
const MARK = 14;                   // px: a run's mark (runs.html's .mk)
// the columns after the name: px wide, and whether it gives way in a narrow tab (cut, its words in the row's tip)
const COLUMNS = /** @type {[number, boolean][]} */ ([[56, false], [90, true], [48, false], [100, true], [56, false]]);
const LEAST = 80;                  // px the run's name keeps at least: past it Folder and Made give way
const LABEL = 64;                  // px: a property's label (.ikv)
const THUMB = 112;                 // px: a picture a run made, 16:9 (.th)
const AGENTS = /** @type {[string, string][]} */ ([["all", "All agents"], ["claude", "Claude"], ["codex", "Codex"]]);
const WHERE = /** @type {[string, string][]} */ ([["here", "This Mac"], ["cloud", "Cloud"]]);
const WHEN = /** @type {[string, string][]} */ ([["now", "Now"], ["schedule", "On a schedule"]]);

/** RUN's mark (runs.html's .mk): a spinner while it works, the waiting dot while it needs you, a red ✕ for one that
 * failed, none for one done. @param {Run} run */
export function runMark(t, run) {
  const mark = run.state === "running" ? spinner(t) : run.state === "blocked" ? div().size(7).rounded_full()
    .bg(t.ansi3) : run.state === "failed" ? div().text_size(11).text_color(toneInk(t, "bad")).child("✕") : null;
  return div().w(MARK).flex_none().flex().items_center().justify_center().when(Boolean(mark), (e) => e.child(mark));
}

export class RunsView {
  /** CORE runs core/'s code (main.js's python: its JSON answer); USAGE, the tab's Usage, has the agents' plans and
   * the scope both views share. @param {(source: string, args: string[], root: string, on: string | null) =>
   * Promise<any>} core @param {import("./usageview.js").UsageView} usage */
  constructor(core, usage) {
    this.core = core;
    this.usage = usage;
    /** @type {any} core's answer: its runs, notes, environments; null: not read yet */
    this.answer = null;
    /** @type {string | null} why the read failed, while nothing is shown */
    this.error = null;
    this.busy = false; this.again = false; this.readAt = 0; this.fresh = false;
    /** @type {string | null} the agent filtered to; null: all */
    this.agent = null;
    /** @type {string | null} the chosen run's key: its properties under the list */
    this.chosen = null;
    /** @type {Form | null} New run's form, open in the properties' place */
    this.form = null;
    this.prompt = TextareaState.new({ placeholder: "What the agent should do" });
    this.prompt.set_auto_grow(3, 8);
    this.prompt.on("change", (/** @type {any} */ _e, /** @type {any} */ cx) => cx.notify());  // Start follows it
    /** @type {string | null} the run a press works on now */
    this.acting = null;
    /** @type {import("./parts.js").Note | null} what was done, or what went wrong, under the properties */
    this.note = null;
    /** @type {Record<string, string | null>} each picture's PNG as the app draws it (media.py's), by its path */
    this.thumbs = {};
    this.scroll = ScrollHandle.new();
    this.still = false;                           // the styleguide's: nothing read, nothing pressed
  }

  /** From render, while the view shows: the runs read when due, sooner while one works; the chosen run's pictures
   * made small once. */
  follow(cx) {
    const every = this.answer?.working ? QUICK : POLL;
    if (Date.now() - this.readAt > every && !this.still) this.read(cx);
    const chosen = this.shown().find((run) => run.key === this.chosen);
    if (chosen) this.pictures(chosen, cx);
  }

  /** The runs read (one read at a time, once more after it when asked meanwhile; FRESH: the agents asked again,
   * after an action), kept where a read fails. @param {boolean} [fresh] */
  read(cx, fresh = false) {
    this.fresh ||= fresh;
    if (this.busy) return void (this.again = true);
    const asked = this.fresh;
    Object.assign(this, { busy: true, readAt: Date.now(), fresh: false });
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        await this.usage.plans();
        const args = ["list", `--agents=${JSON.stringify(usageAgents(this.usage.agents))}`, ...asked ? ["--fresh"]
          : []];
        Object.assign(this, { answer: await this.core(RUNS, args, home(), null), error: null });
      } catch (e) {
        this.error = said(e);
      } finally {
        this.busy = false;
        if (this.again) {
          this.again = false;
          this.read(cx);
        }
        cx.notify();
      }
    });
  }

  /** The runs shown: the scope's space's (Usage's), the agent's. @returns {Run[]} */
  shown() {
    return (this.answer?.runs ?? []).filter((/** @type {Run} */ run) => runShown(run, this.usage.folder,
      this.agent));
  }

  /** Run KEY chosen (null: none), its properties under the list; New run's form put away. @param {string | null} key */
  choose(key, cx) {
    Object.assign(this, { chosen: key === this.chosen ? null : key, form: null });
    cx.notify();
  }

  /** New run's form opened in the properties' place: Claude, now, this Mac, the prompt empty. */
  open(cx) {
    this.form = { agent: "claude", where: "here", when: "now", env: this.answer?.envs?.[0]?.id ?? null, busy: false,
      note: null };
    this.prompt.set_value("");
    this.chosen = null;
    this.prompt.focus();
    cx.notify();
  }

  /** The form's run started, or its schedule's chat opened (Claude's /schedule, with the words typed), in SPACE's
   * folder; what happened said under the list, a failure in the agent's words under the form. @param {any} space */
  start(space, cx) {
    const form = this.form, prompt = this.prompt.value().trim();
    if (!form || !prompt || form.busy) return;
    if (form.agent === "claude" && form.when === "schedule") {
      openChat({ space: space.id, agent: "claude", prompt: `/schedule ${prompt}`, folder: space.folder });
      this.form = null;
      return void keepNote(this, { text: "Opened a chat with /schedule", error: false }, cx);
    }
    form.busy = true;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const done = await this.core(RUNS, ["start", form.agent, form.where, space.folder, prompt,
          ...form.where === "cloud" ? [form.env ?? ""] : []], home(), null);
        if (!done.ok) return void (form.note = { text: done.said, error: true });
        this.form = null;
        keepNote(this, { text: done.said, error: false }, cx);
        this.read(cx, true);
      } catch (e) {
        form.note = { text: said(e), error: true };
      } finally {
        form.busy = false;
        cx.notify();
      }
    });
  }

  /** WHAT done to RUN from its properties (runActions'), in SPACE: a terminal, a chat, the preview or the browser
   * opened, or the agent's own command run, what happened said under them. @param {string} what @param {Run} run
   * @param {any} space */
  act(what, run, space, cx) {
    if (what === "attach") {
      return void command("tab.new", { space: space.id, name: run.title.slice(0, 40), folder: run.folder,
        argv: ["claude", "attach", run.id] });
    }
    if (what === "web" || what === "pr") return void cx.open_url(what === "pr" ? run.pr?.url : run.url);
    if (what === "again") {
      this.form = { agent: run.agent, where: run.kind === "cloud" ? "cloud" : "here", when: "now",
        env: run.env_id ?? null, busy: false, note: null };
      this.prompt.set_value(run.prompt);
      return void this.start({ ...space, folder: run.folder || space.folder }, cx);
    }
    if (this.acting) return;
    this.acting = run.key;
    cx.notify();
    cx.spawn(async (/** @type {any} */ cx) => {
      try {
        const asked = what === "chat" ? (run.kind === "background" ? ["remove", run.id] : null)
          : what === "apply" ? ["apply", run.id, space.folder] : [what, run.id];
        const done = asked ? await this.core(RUNS, asked, home(), null) : { ok: true, said: "" };
        if (!done.ok) return void keepNote(this, { text: done.said, error: true }, cx);
        if (what === "diff") {
          const cut = done.path.lastIndexOf("/");
          showPreview({ kind: "file", root: done.path.slice(0, cut), path: done.path.slice(cut + 1), on: null });
        } else if (what === "chat") {
          const failed = showChat({ agent: run.agent, id: String(run.session), title: run.title, folder: run.folder,
            time: 0, state: "", pane: "" });
          keepNote(this, { text: failed ?? (run.kind === "background" ? "Opened as a chat: it is in Chats now"
            : "Opened as a chat"), error: Boolean(failed) }, cx);
        } else keepNote(this, { text: done.said, error: false }, cx);
        if (what !== "diff") this.read(cx, true);
      } catch (e) {
        keepNote(this, { text: said(e), error: true }, cx);
      } finally {
        this.acting = null;
        cx.notify();
      }
    });
  }

  /** The PNGs of RUN's pictures and videos' frames read once (media.py's, THUMB wide twice for the screen), then drawn
   * small. @param {Run} run */
  pictures(run, cx) {
    const wanted = run.media.filter((one) => one.kind !== "audio" && !(one.path in this.thumbs))
      .map((one) => one.path);
    if (!wanted.length || this.still) return;
    for (const path of wanted) this.thumbs[path] = null;
    cx.spawn(async (/** @type {any} */ cx) => {
      for (const path of wanted) {
        try {
          this.thumbs[path] = (await this.core(MEDIA, ["picture", path, "0", String(2 * THUMB)], home(), null)).png;
        } catch {
          // left as its name alone
        }
      }
      cx.notify();
    });
  }

  /** The view: HEAD (the tab's own: the scope and its views), the agents and New run, the list in one column WIDE at
   * most, its foot saying what is not listed; under it the chosen run's properties or New run's form.
   * @param {any} head @param {any} space */
  draw(t, head, space) {
    const runs = this.shown(), chosen = runs.find((run) => run.key === this.chosen) ?? null;
    const say = (/** @type {string} */ words, bad = false) => div().flex_none().px(PAD).py(8).text_size(12)
      .text_color(bad ? toneInk(t, "bad") : t.muted).child(words);
    const body = !this.answer ? say(this.error ? `Couldn't read the runs: ${this.error}` : "Loading runs…",
      Boolean(this.error)) : runs.length ? this.list(t, runs) : say(this.answer.runs.length ? "No runs here"
      : "No runs yet: New run starts one in the background");
    const into = String(space?.folder ?? "").split("/").pop() ?? "";
    return v_flex().id("runs").flex_1().min_h(0).items_center().px(PAD).pb(PAD)
      .child(div().w_full().max_w(WIDE).flex_none().child(head))
      .child(v_flex().w_full().max_w(WIDE).flex_1().min_h(0).rounded(10).border_1().border_color(t.border)
        .overflow_hidden()
        .child(this.bar(t))
        .child(v_flex().id("runs-list").flex_1().min_h(0).overflow_y_scroll().track_scroll(this.scroll).child(body)
          .when(Boolean(this.answer), (e) => e.child(this.foot(t, space))))
        .when(Boolean(this.form), (e) => e.child(this.formView(t, space, into)))
        .when(!this.form && Boolean(chosen), (e) => e.child(this.properties(t, /** @type {Run} */ (chosen), space,
          into)))
        .when(Boolean(this.note) && !this.form && !chosen, (e) => e.child(footNote(t, /** @type {any} */ (this.note))
          .border_t_1().border_color(t.border))));
  }

  /** The bar over the list (runs.html's .vrow2): the agents, and at its right end New run, the view's one primary
   * button. */
  bar(t) {
    return h_flex().id("runs-bar").flex_none().px(PAD).py(8).gap(PAD).items_center().border_b_1()
      .border_color(t.border)
      .child(segmented(t, "runs-agent", AGENTS, this.agent ?? "all", (value, cx) => {
        this.agent = value === "all" ? null : value;
        cx.notify();
      }))
      .child(div().flex_1())
      .child(button(t, "runs-new", "New run", !this.form, !this.form, (cx) => this.open(cx)));  // the form's own lit
  }

  /** The list: its columns' names, then each day's runs under its name (Running first). @param {Run[]} runs */
  list(t, runs) {
    const heads = this.line(t, [div(), div().truncate().child("Run"), "Agent", "Folder", "Started", "Made",
      div().w_full().text_right().child("Cost")]).h(26).text_size(11).text_color(t.muted);
    const rows = [heads];
    let group = null;
    for (const run of runs) {
      if (run.group !== group) {
        group = run.group;
        rows.push(div().flex_none().px(PAD).pt(12).pb(2).text_size(11).font_semibold().text_color(t.muted)
          .child(group));
      }
      rows.push(this.row(t, run));
    }
    return v_flex().id("runs-columns").w_full().flex_none().children(rows);
  }

  /** A row's cells in the list's columns (the run's name takes the rest, LEAST at least; Folder and Made give way
   * in a narrow tab), 8 apart. @param {any[]} cells */
  line(t, cells) {
    const [mark, name, ...rest] = cells;
    return h_flex().w_full().flex_none().px(PAD).gap(8).items_center().text_size(12)
      .child(h_flex().w(MARK).flex_none().child(mark))
      .child(div().flex_1().min_w(LEAST).overflow_hidden().child(name))
      .children(rest.map((cell, n) => h_flex().w(COLUMNS[n][0]).min_w(0).overflow_hidden()
        .flex_shrink(COLUMNS[n][1] ? 1 : 0).child(cell)));
  }

  /** RUN's row: its mark, name, agent, folder, time, what it made and its cost; chosen on the chosen fill.
   * @param {Run} run */
  row(t, run) {
    const muted = (/** @type {string} */ words) => div().min_w(0).truncate().text_color(t.muted).child(words);
    const made = run.made && LIVE.includes(run.state) ? `${run.made} so far` : run.made;
    return this.line(t, [runMark(t, run), div().truncate().child(run.title), muted(run.name), muted(run.place),
      muted(run.time), div().min_w(0).truncate().text_color(run.state === "failed" ? toneInk(t, "bad") : t.muted)
        .child(made || "–"), div().w_full().text_right().text_color(t.muted).child(run.cost)])
      .id(`runs-row-${run.key}`).h(30).tooltip(`${run.title}\n${run.place} · ${run.made || run.said}`)
      .when(run.key === this.chosen, (e) => e.bg(chosenFill(t)))
      .when(!this.still, (e) => e.cursor_pointer().hover((/** @type {any} */ s) => s.bg(run.key === this.chosen
        ? chosenFill(t) : t.hover)).on_click((/** @type {any} */ _e, /** @type {any} */ cx) => this.choose(run.key,
        cx)));
  }

  /** The list's foot (runs.html's .lfoot): that scheduled cloud runs are not listed, and Claude's routines, a new
   * chat in SPACE's folder with /schedule list (Claude's own way to list them); what could not be read.
   * @param {any} space */
  foot(t, space) {
    const notes = /** @type {string[]} */ (this.answer?.notes ?? []);
    return v_flex().id("runs-foot").flex_none().mt(6).px(PAD).pt(12).pb(PAD).gap(4).border_t_1()
      .border_color(t.border).text_size(12).text_color(t.muted)
      .child(h_flex().gap(8).items_start().child(div().flex_1().min_w(0).child(String(this.answer.scheduled)))
        .child(div().id("runs-routines").flex_none().text_color(t.foreground).cursor_pointer().border_b_1()
          .border_color(`${t.foreground}2a`).tooltip("A new chat with /schedule list")
          .when(!this.still && Boolean(space), (e) => e.on_click((/** @type {any} */ _e, /** @type {any} */ cx) => {
            openChat({ space: space.id, agent: "claude", prompt: "/schedule list", folder: space.folder });
            keepNote(this, { text: "Opened a chat with /schedule list", error: false }, cx);
          })).child("Claude's routines")))
      .children(notes.map((note) => div().text_color(toneInk(t, "bad")).child(note)));
  }

  /** A property: its LABEL muted in its column, then its value (a string wraps; an element as it is).
   * @param {string} label @param {any} value */
  property(t, label, value) {
    return h_flex().flex_none().gap(12).items_start().text_size(12)
      .child(div().w(LABEL).flex_none().text_color(t.muted).child(label))
      .child(div().flex_1().min_w(0).child(value));
  }

  /** RUN's properties (runs.html's .insp): its name and state, how it ran, where and when, its prompt, what it does
   * now or made (its pictures small, a press opening one in the preview), its cost; its buttons, then what was done.
   * @param {Run} run @param {any} space @param {string} into */
  properties(t, run, space, into) {
    const code = (/** @type {string} */ words) => div().truncate().text_size(11).child(words);
    const short = (/** @type {string} */ path) => (run.folder && path.startsWith(`${run.folder}/`)
      ? path.slice(run.folder.length + 1) : path);
    const pictures = run.media.filter((one) => one.kind !== "audio").map((one) => one.path);
    const made = pictures.length ? h_flex().flex_wrap().gap(8).children(pictures.map((path, n) => v_flex()
      .id(`runs-picture-${n}`).w(THUMB).gap(4).cursor_pointer().tooltip(path)
      .when(!this.still, (e) => e.on_click(() => {
        const cut = path.lastIndexOf("/");
        showPreview({ kind: "file", root: path.slice(0, cut), path: path.slice(cut + 1), on: null });
      }))
      .child(this.thumbs[path] ? image(String(this.thumbs[path])).w(THUMB).h(THUMB * 9 / 16).rounded(6)
        : div().w(THUMB).h(THUMB * 9 / 16).rounded(6).border_1().border_color(t.border).bg(t.raised))
      .child(code(path.split("/").pop() ?? path).text_color(t.muted))))
      : run.files.length ? v_flex().gap(2).children(run.files.slice(0, 6).map((path) => code(short(path))
        .tooltip(path))).when(run.files.length > 6, (e) => e.child(div().text_color(t.muted)
        .child(`${run.files.length - 6} more`))) : div().text_color(t.muted).child(run.made || "Nothing yet");
    const where = run.kind === "cloud" ? ["Environment", `${run.place} · ${run.day} ${run.time}`]
      : ["Folder", [run.place, `${run.day} ${run.time}`, ...run.took ? [run.took] : []].join(" · ")];
    const actions = runActions(run, into);
    return v_flex().id("runs-properties").flex_none().max_h("60%").overflow_y_scroll().px(PAD).pt(12).pb(PAD)
      .gap(4).border_t_1().border_color(t.border).bg(t.chrome)
      .child(h_flex().gap(8).mb(4).items_center().text_size(13).child(runMark(t, run))
        .child(div().flex_1().min_w(0).truncate().font_semibold().tooltip(run.title).child(run.title))
        .child(div().flex_none().text_size(12).text_color(run.state === "failed" ? toneInk(t, "bad") : t.muted)
          .child(run.said))
        .child(small(t, "runs-close", icon("x", 12), "Close the properties", true,
          (/** @type {any} */ cx) => this.choose(null, cx))))
      .child(this.property(t, "Ran as", run.ran_as))
      .child(this.property(t, where[0], div().tooltip(run.folder || run.place).child(where[1])))
      .child(this.property(t, "Prompt", run.prompt))
      .when(Boolean(run.now), (e) => e.child(this.property(t, "Now", code(String(run.now)))))
      .when(Boolean(run.diff), (e) => e.child(this.property(t, "Diff", String(run.diff))))
      .when(!run.diff, (e) => e.child(this.property(t, LIVE.includes(run.state) ? "So far" : "Made", made)))
      .child(this.property(t, "Cost", run.cost_line))
      .when(actions.length > 0, (e) => e.child(h_flex().mt(8).flex_wrap().gap(8).items_center()
        .children(actions.map(([id, label, look]) => actButton(t, `runs-${id}`, label, look, !this.acting,
          (/** @type {any} */ cx) => this.act(id, run, space, cx))))))
      .when(Boolean(this.note), (e) => e.child(div().pt(4).text_size(11).text_color(this.note?.error
        ? toneInk(t, "bad") : t.muted).child(this.note?.text ?? "")));
  }

  /** New run's form (runs.html's) in the properties' place: the agent, folder, prompt, where and when (Codex's schedule
   * greyed: its app's), what that does; Cancel, and at the right end Start run or Open in a chat, the one accent, lit
   * once there is a prompt. @param {any} space @param {string} into */
  formView(t, space, into) {
    const form = /** @type {Form} */ (this.form), envs = /** @type {{ id: string, label: string }[]} */ (
      this.answer?.envs ?? []);
    const pick = (/** @type {keyof Form} */ name) => (/** @type {string} */ value, /** @type {any} */ cx) => {
      Object.assign(form, { [name]: value, note: null });
      if (form.agent === "codex" && form.when === "schedule") form.when = "now";
      cx.notify();
    };
    /** NAME's switch (`segmented`), its own width. @param {keyof Form} name @param {[string, string][]} list */
    const choice = (name, list, off = /** @type {string[]} */ ([])) => h_flex().child(segmented(t, `runs-form-${name}`,
      list, String(form[name]), pick(name), off));
    const schedules = form.agent === "claude" && form.when === "schedule";
    const ready = Boolean(this.prompt.value().trim()) && !form.busy && !(form.agent === "codex"
      && form.where === "cloud" && !form.env);
    return v_flex().id("runs-form").flex_none().px(PAD).pt(12).pb(PAD).gap(8).border_t_1().border_color(t.border)
      .bg(t.chrome).text_size(12).on_key_down((/** @type {any} */ e, /** @type {any} */ cx) => {
        if (e.key !== "escape") return;
        this.form = null;
        cx.notify();
      })
      .child(div().text_size(13).font_semibold().child("New run"))
      .child(this.property(t, "Agent", choice("agent", [["claude", "Claude"], ["codex", "Codex"]])))
      .child(this.property(t, "Folder", div().truncate().tooltip(String(space?.folder ?? "")).child(into)))
      .child(this.property(t, "Prompt", div().min_h(64).rounded(6).border_1().border_color(t.border)
        .bg(t.background).child(Textarea.new(this.prompt).px(8).py(6).text_size(12))))
      .when(form.agent === "codex", (e) => e.child(this.property(t, "Where", choice("where", WHERE,
        envs.length ? [] : ["cloud"]))))
      .when(form.agent === "codex" && form.where === "cloud", (e) => e.child(this.property(t, "Env",
        choice("env", envs.map((one) => [one.id, one.label])))))
      .child(this.property(t, "When", choice("when", WHEN, form.agent === "codex" ? ["schedule"] : [])))
      .child(this.property(t, "", div().text_color(t.muted).child(formNote(form, into))))
      .when(Boolean(form.note), (e) => e.child(this.property(t, "", div().text_size(11)
        .text_color(toneInk(t, "bad")).child(form.note?.text ?? ""))))
      .child(h_flex().flex_wrap().gap(8).items_center().justify_end()
        .child(actButton(t, "runs-form-cancel", "Cancel", "plain", true, (/** @type {any} */ cx) => {
          this.form = null;
          cx.notify();
        }))
        .child(button(t, "runs-form-start", form.busy ? "Starting…" : schedules ? "Open in a chat" : "Start run",
          ready, primaryLit(ready, form.busy), (cx) => this.start(space, cx))));
  }
}
