// @ts-check
// The Start tab, a home space's first tab (no agent works in the home folder): Open project… picks a folder, the
// projects of the chats so far one press away; each opens as a space, a new chat its first tab (chat.js's firstChat).
import { div } from "gpui-kit";
import { v_flex, h_flex } from "gpui-base";
import { exec, home, pickFolder, run as command, setShared, shared, spaces } from "herdr";
import { CHATS } from "./helper.js";
import { newSpace } from "./chat.js";
import { folderIcon, homeShort, recentProjects } from "./logic.js";
import { button, fileMark, listName } from "./parts.js";

const SHOWN = "herdr-fold.start";      // shared: the homes given a Start tab once, so one closed stays closed
const WIDE = 440;                      // px: its column, the New chat's words' measure

/** HOME (a space at its machine's home, spaces.js's isHome) given its Start tab, once and shown: where it holds shells
 * alone. @param {any} space @param {boolean} shellsOnly */
export function firstStart(space, shellsOnly) {
  const kept = shared(SHOWN), met = Array.isArray(kept) ? kept : [];
  if (met.includes(space.id)) return;
  const live = new Set(spaces().map((s) => s.id));
  setShared(SHOWN, [...met.filter((id) => live.has(id)), space.id]);
  if (shellsOnly) command("tab.new", { name: "Start", space: space.id, mod: "herdr-fold", props: { part: "start" } });
}

export class StartView {
  /** CORE runs core/'s code on this Mac (main.js's python): the chats' projects asked for once. @param {any} core */
  constructor(core, cx) {
    /** @type {string[]} the projects offered, the newest first (the folders that are still there) */
    this.projects = [];
    cx.spawn(async (cx) => {
      try {
        const answer = await core(CHATS, ["list", "[]", "{}"], home(), null);
        const found = recentProjects(answer.chats ?? [], home());
        const there = found.length ? await exec("/bin/ls", ["-1d", "--", ...found]).catch(() => null) : null;
        const alive = new Set(String(there?.stdout ?? "").split("\n"));      // a folder gone is offered no more
        this.projects = found.filter((folder) => alive.has(folder));
      } catch {
        this.projects = [];
      } finally {
        cx.notify();
      }
    });
  }

  /** FOLDER shown: its space where one has it, else a new one there (its first tab a chat). @param {string} folder */
  open(folder) {
    const space = spaces().find((s) => !s.machine && s.folder === folder);
    if (space) command("space.select", { id: space.id });
    else void newSpace({ machine: "", folder }).catch(() => {});
  }

  render(t) {
    const rows = this.projects.map((folder, n) => h_flex().id(`start-${n}`).h(32).px(8).gap(8).items_center()
      .rounded(6).cursor_pointer().hover((s) => s.bg(t.raised)).on_click(() => this.open(folder))
      .tooltip(folder)
      .child(fileMark(folderIcon(false)))                                   // as Files draws a folder
      .child(div().flex_none().text_size(13).child(folder.split("/").pop() ?? folder))
      .child(div().flex_1().min_w(0).truncate().text_size(12).text_color(t.dim).child(homeShort(folder, home()))));
    return v_flex().id("start").size_full().bg(t.background).pt(64).px(24).items_center().overflow_y_scrollbar()
      .child(v_flex().w_full().max_w(WIDE).gap(8).items_center()
        .child(div().text_size(15).font_semibold().child("Open a project"))
        .child(div().text_size(12).text_color(t.dim).text_center()
          .child("An agent works in a project's folder: its files, its git, its issues. Each opens as a space, "
            + "a new chat its first tab."))
        .child(div().pt(8).child(button(t, "start-open", "Open project…", true, true,
          () => void pickFolder({ prompt: "Open project" }).then((folder) => folder && this.open(folder))))))
      .when(this.projects.length > 0, (e) => e.child(v_flex().w_full().max_w(WIDE).pt(32).gap(2)
        .child(div().px(8).pb(4).child(listName(t, "Recent")))
        .children(rows)));
  }
}
