# Sidebar

A herdr plugin: AI agents' harnesses in one pane, the same on macOS, Linux and Windows: every space's Claude and Codex
chats and the Agent view (each agent's rules, skills, subagents, permissions and connectors, its limits and costs, a
Usage view, its graph as a tree), with Files, Search, Changes (git) and Issues (GitHub). Every new empty tab gets it on
the right, above a terminal, beside the tab's own shell, as wide as in every other tab; when herdr starts, it comes
back in every tab, but where a pane was closed by hand.

The views are buttons in one row at the top, each its icon over its name: Files, Search, Changes, Issues, Agent,
then Chats and More. One view shows under the row, the whole height; a click on a button, or its key, shows its view,
and each folder keeps the one it shows (`dock.json`). Changes and Chats have a dot beside their icons while there is
something to count, the number in the button's tip, and Agent while its setup has a problem. Without a Nerd Font
(Settings' Icons, or `i` in Files) the icons are plain marks: ▤ ⌕ ⎇ # ◇ ✦ ⋯.

- Chats, under the AI sparkle, opens the Chats list over the sidebar, with the keys; its lit button, Esc, a click
  outside it or another pane closes it.
- More opens the pane's own menu: the views, each checked while shown (one unchecked leaves the row in every tab:
  `hidden_panels` in `settings.json`; one always stays), the tab's other panes, and Settings… (`settings.py`, herdr's
  popup: General with the icons, About with the version, the update check and its switch, What's new). More has a dot
  while a newer version is out.
- Narrower than the names need (80 cells, 69 without Issues), the row shows its icons alone, each name in its tip.
- The » at the row's end, or Cmd + Option + B, folds the dock to its rail in every tab: the icons alone, one under
  another, the terminal moved under the agent. A press on an icon, or a view's key, opens the dock again on that view;
  so do « and dragging the rail wider (`column.json` keeps the width, in cells, and the rail, after herdr restarts
  too).

The row, the column's width and the rail in full: [The sidebar](../../../docs/sidebar.md#how-it-starts).

![The four views: Files with its git marks, Search narrowed to the folder chosen in Files, Changes with a message,
the issue it fixes and the Graph, Issues by priority](../../../assets/screenshots/tui-sidebar.webp)

- **Chats** (the list over the sidebar): the Claude Code, Codex and OpenCode chats of herdr's spaces, each space
  with a chat a group in the Spaces list's order, its chats under it, a running one's mark in its state's color and
  the closed ones faint, their agent and age at the right (an OpenCode chat is archived, never deleted here: OpenCode
  keeps its chats in its own database); under the chosen one its task list (Claude's tasks, Codex's plan: the done
  steps in one row, the step at work, the ones to do; `plan.py`), with Open the plan where a plan mode's plan was
  approved, in the preview tab. Typing filters; Enter or a click goes to a running one, or reopens a closed
  one in a new tab of its space with the right column beside it; a right click offers Open, Copy chat (the whole of it,
  formatted on a Mac), Rename (the name AI Sessions, a running one's pane and the tab it has to itself show too) and,
  for a closed one, Archive (off the list, its file as it was), several at once when marked (Space, Shift + ↑ ↓, or the
  box at a closed row's start); More (⋯) and a right click beside them, while any is archived, Show archived (the
  archived ones back in sight, a shade fainter; Unarchive puts one back). Delete…, last in a closed chat's menu, is the
  rarer one: asked first at the list's foot, by the chat's name, then its row leaves and its file is moved to the
  system's Trash; never a running chat's. The action
  **Chats: find** (`actions.py find-chat`) opens the list, its filter empty and the keys going to it, in the tab's
  sidebar (one closed by hand comes back) or the space's first.

  ![Chats open in the sidebar beside Claude: each space's chats, lumen-api's open with Claude's two and Codex's
  four, a running one's mark in its state's color, the closed ones faint](../../../assets/screenshots/tui-chats.webp)

- **Files:** the folder as a tree, with git's letter on each changed file and a dot on each folder holding changes; a
  new file or folder, renaming, moving to the Trash, copying a path. A click or Enter opens a text file in your editor
  (`$VISUAL`, `$EDITOR`, else micro, nano or vim) in a tab of its own, a new file too; anything drawn in a preview tab:
  an image
  (any macOS reads: PNG, JPEG, HEIC, AVIF, WebP, PSD, EXR, a camera's raw file…) or a PDF drawn there (Ghostty shows
  pictures in herdr), an image fitted and never larger than it is, a PDF's pages one under another, a row apart,
  scrolled as the pager scrolls its lines, an SVG or a page drawn beside its code as VS Code's preview to the side, or
  under it in a pane taller than wide (macOS's WebKit draws it, offline): the divider between them drags and the page is
  drawn for its side as a browser that size shows it, once the divider is let go (an SVG at its own size, never larger,
  what it leaves empty clear); the status row starts with Code, Split and Picture (a click, or `c` for the next) and in
  Split the turn between side by side and one under the other (a click, or `v`), a narrow row keeping them whole, and a
  right click in the preview offers them, Open in Browser and Close Preview; `o` there, or
  the right click's Open in Browser, opens a page, a PDF or an image in the default browser (a picture no browser shows,
  as a PSD or an EXR, in Preview: Open in Preview) (never over SSH: a browser there would open on the machine, out of
  sight). While the space has a preview tab, the right click offers Close Preview, as `q` there. With herdr-fold's
  Spaces plugin, a folder's right click offers New space: its folder picker opens on it.
- **Search:** as you type (typing on narrows the hits at once, before the search answers), with match case, whole word
  and regular expression; the hits by file. A hit opens the preview at its line. A folder or file you chose in Files (an
  arrow key or a click on it) is the one searched, named above the field, a file even when git ignores it (a link chosen
  narrows nothing); the field's × or Esc clears the text and it, until Search is shown again and takes the choice in
  Files anew. A search stops after 60 s and says so. In a folder that is no repository, each repository in it is
  searched as git sees it: its ignored files (node_modules, build output) are neither hits nor read.
- **Changes** (git): on top, as VS Code's Repositories, the repository's row: its name, ⎇ its branch, ↻ the sync (how
  far the branch is from its upstream, when it is) and ⋯ to pull or push alone, or open it on GitHub; in a folder that
  is no repository itself, the repository of the folder or file chosen in Files, as Search searches there, else the
  one the Spaces row names; the staged
  and unstaged changes, staging, unstaging and discarding them, none of them needed: with nothing staged, the message
  and the commit take every change shown, as GitHub Desktop does (never a file .gitignore names, even one tracked
  before, nor a repository inside; a file come after the commit was asked for waits for the next one); a commit message
  written by Claude or Codex from what the commit takes (a file whose name looks like a secret's, such as `.env` or a
  key, by its name only), the empty field saying who writes it meanwhile (with text in it, ✦'s tip says so); Commit,
  Commit & Push or Commit & Sync, after a question when such a file goes in; the last 20 commits in the Graph, kept at
  the view's bottom while the changes scroll above it; each file's letter under its section's count. Nothing moves the
  list: a commit, sync, pull or push running spins in the sync glyph's place, its tip naming the step, and a failure
  stands on the sidebar's last row, red, until a key.
- **Pull requests**, the Issues view's other list (`p`, or its switch on top): each one's checks' mark, number,
  title and review's state (your review yellow), its branch, author and age; Enter shows its review in the preview tab,
  read only: each file's diff, each thread under its line. In Changes, under the repository row, the branch's own, or
  Create pull request…, whose form takes the message's place: Into, the Title and Body Claude or Codex writes from the
  branch's commits, Draft or Ready; Commit is not lit while nothing is to commit.
- **Issues** (for a repository on GitHub), laid out and keyed as GitHub's own issue list: the search field with the
  filters button (assigned to me, created by me, a label, the priority), Open and Closed, the refresh button at their
  right (`R` too): while gh runs over the issues shown it spins and the list stays where it is; the first ask, a failure
  or none found is said on the first issue's row. While shown, the list is asked for every minute; while it holds any,
  behind another view too, so an issue made on GitHub or in another tab shows up and the chosen one stays chosen. Open
  ones with a priority come first, the most pressing at the top: GitHub's own Priority field where the repository's
  organization uses it (Urgent, High, Medium, Low), else a priority label (`priority: high`, `P1`, `prio:3-low`, Jira's
  `Priority: Highest`, Kubernetes' `priority/critical-urgent`…), then a severity label (`severity: major`, `sev1`), then
  a word alone (`urgent`, `blocker`, `low`…; `minor`, `major`, `normal`, `moderate` and `backlog` only in a named label;
  `P4` on: low); critical, urgent and high red, medium yellow, low green, on the mark, the number and the priority. One
  opens in the preview tab with its comments; handed to the agent, it becomes a prompt in the tab's Claude or Codex
  pane (with none there, in the one started last, in a new tab of the space), and the next written commit message
  fixes it (`Fixes #42`), until a commit from anywhere closes it. A new issue,
  a reply, closing, reopening, assigning to you (the right click's menu).
- **Agent:** what the agent in the tab starts with in the folder: its model, effort and start-up context, then Usage
  (a plan's limits or an API key's month against its budget), Subagents, Rules, Skills, Permissions (Mode, Sandbox,
  the rules, every hook) and Connectors. The chosen row has its properties, its buttons and, where it can be changed,
  its form: saved in the layer you choose, the lines it writes shown first, Undo after. `U` opens the Usage view over
  the tab, `g` the agent's graph as a tree in the preview tab. All of it:
  [The agent's harness](../../../docs/harness.md).

The preview opens in a tab of its own, one per space, laid out as the tab it was opened from: the preview where the
agent is, and the sidebar and the terminal beside it as they are there, its sidebar where the one that opened it was.
The next file, diff, commit or issue opened shows there too; `q`, Esc or Ctrl + C closes the whole tab, its terminal
too. A pipe or a device is never shown, and a program that does not finish in 30 s (`gh` asking GitHub) is stopped with
what it showed. `bat` colors a file and `delta` lays out a diff when they are installed (else the file plain, the diff
in git's colors); the built-in pager shows either. A changed picture shows as VS Code's image diff does: before and
after side by side, each under its name and size (Index and Working Tree, staged HEAD and Index), one above the other in
a pane taller than wide, the status row's turn, `v` or the right click turning them; a new one's after alone.

## Keys

| Where | Keys |
|---|---|
| Everywhere | `1` to `5` show the row's views, Files to Agent (on the rail, the dock opened), the keys going to the view shown; on the rail `6` raises or lowers the tab's terminal; `q` quits, unless a field, a menu or a question has the keys; F9 F10 F11 F12 show Files to Issues and Ctrl + C quits even then; F7 opens the Chats list, F6 folds or opens the dock (Cmd + Option + B sends it); Esc closes the list once its menu, a name being typed or a question has taken its own Esc |
| Files | ↑ ↓ ← → or `j` `k` `h` `l`, PgUp PgDn, Home End or `g` `G`, Enter or Space opens, `n` new file, `N` new folder, `r` rename, Delete to the Trash, `m` the menu, `.` hides or shows hidden files (shown by default), `i` plain icons, `R` refresh |
| Search | type to search; a click or Alt + C, Alt + W, Alt + R the switches; Esc or the field's × clears the text and the folder or file; Tab or ↓ to the hits (PgUp PgDn Home End too), Enter opens a hit or folds a file's, Esc, Tab or another letter goes back to the field |
| Changes | `c` or typing writes the message (Enter a new line; Esc, then Enter commits), `A` or the star beside the message has it written, Enter stages or unstages, Space shows the diff, `d` discards, `S` syncs, `P` the branch's pull request (its review, or with none the form: Tab and Shift + Tab its parts, ← → Into and Draft or Ready, Enter on the button opens it, `A` there writes it again, Esc gives it up) |
| Issues | `p` switches to Pull requests and back (there: `/` `s` filter, `c` a new one in Changes, `o` or Enter its review, `t` to the agent, `b` the browser, `R`, ← →); GitHub's: `/` `s` or Ctrl + / search, `c` a new issue, `a` `u` `l` the assignee, author and label filters, `o` or Enter opens it; herdr-fold's: `t` hands it to the agent, `r` replies, `b` opens it in the browser, `x` closes or reopens it, `R` asks again; ↑ ↓ PgUp PgDn Home End, ← → Open and Closed; a right click: all of it, Assign to me too |
| Agent | ↑ ↓ PgUp PgDn Home End choose a section or a row; → opens a section (on an open one, to its first row), ← folds it (on a row, up to its section); Enter opens or folds a section, opens "N more", or does the row's first action (Open, Retry, Connect, Open Usage; with none, into its form); → on a row, the head's line or Hooks puts the keys in its form: ↑ ↓ step through it, ← → or Space choose, Tab changes the layer, Enter saves, Esc leaves; `a` on Permissions adds a rule, `x` on a rule removes it (it asks once), `u` undoes the last save while the foot shows it; `U` opens the Usage view (Tab steps the periods, `a` the agents, Enter edits the budget, Esc closes), `g` shows the graph as a tree; `a` adds a connector by URL (Tab or ↓ steps through the form, ← → choose For, Enter adds, Esc leaves); a click chooses, on a section opens or folds it, on Usage's ↗ opens its view, on a problem at the top chooses its server; a right click on a row: its actions |
| Chats | every key goes to the list while it is open: type to filter; ↑ ↓ PgUp PgDn Home End; ← closes a group, → or Enter opens it; on a chat → lists its plan's done steps, ← folds them again; Enter goes to a running chat or reopens a closed one in a new tab; Space or Shift + ↑ ↓ marks closed ones (closing the list unmarks them); a right click: Open, Copy chat, Rename (Enter keeps the new name, Esc the old one), Archive, or with several marked, all of them at once, and Delete… for a closed one; Delete (fn + ⌫ on a Mac's own keyboard), while nothing is typed, asks the same of the chosen closed chat: Move the chat to the Trash? ← → or Tab choose, Enter presses the chosen button (Cancel at first), y moves it, n or Esc keeps it; its lit button, Esc or a click outside closes it |
| Settings | herdr's popup, from More: ↑ ↓ choose the section; in General ← → or Tab switch the icons; in About Tab or ← → choose a button or a link, Enter presses it, Space switches Check for updates automatically; Esc or `q` closes it |
| Preview | ↑ ↓ or `j` `k`, PgUp PgDn or `b` Space, Home End or `g` `G`, `/` search, `n` `N` the next and previous hit, `c` turns an SVG or a page to its next view (Code, Split, Picture: the status row's, a click there chooses one), `v` sets them side by side or one under the other (the status row's turn; a right click: those, Open in Browser, Close Preview), `e` edits the page or the SVG in your editor (the status row's Edit), `o` opens it in the browser (or Preview), `q`, Esc or Ctrl + C closes the whole tab |

Everything works with the mouse too: a click, a right click for the menu, the wheel, and the row icons on hover. A
control shown by an icon alone (the message's ✦, ↻, », a row's icons, the row's when narrow…) says what it does once the
mouse rests on it for half a second, a changed file's row in Changes its whole path in the repository, and a name Files
cuts short its whole path in the folder, on more rows when it is wider than the pane. The sections folded in Changes
stay folded after an update or a restart (a sidebar started later, in another tab too, takes them); a new version comes
back to the rows you were on.
In a field, Shift with an arrow, Home or End selects, and Cmd + A its whole text (herdr-fold's Ghostty and herdr
keys send F8); in the commit message a drag, a double click (a word) or a triple click (all of it) too. The wheel
shows the rest of a message longer than the field, as does a drag past its edge, and while a drag selects, the wheel
moves the message. Backspace or Delete takes the selection, typing replaces it, and Alt + Backspace takes the word
before the cursor.
The Alt keys need Option to work as Alt in the terminal (herdr-fold's Ghostty leaves Option to the keyboard layout);
Alt + Enter commits from the message there too.

## What it reads and writes

- The folder it shows, and git there: the status, the diffs, the recent commits, the search's file list, what the commit
  message is written from. A repository's own fsmonitor, signature check, external diff and text conversion programs
  never run, nor does any filter for the status the sidebar asks for on its own, and no submodule is asked for one. Its
  filters (git-lfs, git-crypt) run when you stage a change (a commit or message with nothing staged stages them all)
  or show its diff, and its hooks when you commit or sync, as
  with git in a terminal: open only folders whose `.git` you trust (a folder from a zip or a share may bring its own).
- `rg` for the search when installed, else `git grep`, else its own search (over git's file list of each repository
  in the folder); `bat` and `delta` for the previews.
- On a Mac, the preview's pictures: `sips` for an image, and two small Swift helpers compiled by `swiftc` into
  `~/.cache/herdr-fold/` the first time each is needed, PDFKit for a PDF's pages and WebKit for an SVG or a page. WebKit
  draws with every address blocked but the file's own folder, none of the page's scripts run, and an SVG as an image
  from its own bytes, so nothing reaches the network. Each picture is made in a folder of its own, gone with the tab.
- herdr's command line, for the preview tab (`herdr tab create`, `herdr pane split`, `herdr pane run`, `herdr tab
  rename`, `herdr tab focus`, `herdr pane process-info` to tell whether its pager still runs, `herdr tab close` on `q`
  and for a preview tab whose pager no longer runs), to hand an issue to the tab's agent (`herdr pane send-text`:
  typed in, not sent; `herdr agent focus`; with none there, `herdr tab create` and `herdr agent start` first, as a
  reopened chat), to lay out a new tab and bring each tab's panes back when herdr
  starts (`herdr workspace list`, `herdr pane list`, `herdr agent list`, `herdr pane split`, `herdr pane rename`,
  `herdr pane run`), and on the rail to move each tab's terminal under its agent and back (`herdr pane move`, through
  a tab of its own that goes by itself; its program runs on).
- herdr's socket, for the right column's width: when it is dragged wider or narrower, the sidebar reads that tab's
  layout once it stays put, keeps each tab's right column at least as wide as its sidebar's row of icons (43 cells
  inside herdr's frame without Issues, 49 with them; under it, let go, the dock folds to its rail) and at most as wide
  as leaves the agent 30 % of the tab,
  remembers the width to the cell (`column.json` in its state folder), and sets every other tab's to it. A window
  resized (herdr keeps each split's share) sets the column back to that width, nothing remembered: narrower only while
  the window leaves the agent less. A window too narrow for the row cuts it at its right end; the keys still
  show every view. Folded to its rail, every tab's column takes 5 cells inside the frame, an icon's five (a tenth of the
  tab where that is more: herdr's narrowest split; a cell more where that is even, every icon on its very middle), and
  the width stays kept for the dock opened again.
- For a repository with a remote on github.com: `gh`, the GitHub CLI, as you are signed in to it on that machine, for
  the issues (once a minute while the view is shown or lists any, for all the sidebars of a repository; `R` at once)
  and what you do with them there; a new issue and a comment are gh's own prompts, in a tab of their own. No token is
  copied anywhere.
- When you ask for a message: `claude` (or `codex`) gets the staged diff, the staged file names, and either the
  repository's `/commit` rules (`.claude/skills/commit/SKILL.md`, `.claude/commands/commit.md` or
  `.agents/skills/commit/SKILL.md`, read only from inside the repository, else `~/.claude/skills/commit/SKILL.md` or
  `~/.claude/commands/commit.md`) or, without rules, the recent commit subjects; nothing from ignored or unstaged
  files. The AI runs with no tools, memories or plugins, and Claude with none of your instructions (Codex still reads
  its own `~/.codex/AGENTS.md`), so a diff cannot make it read or send anything else. The AI tool sends what it gets to
  its own service; the sidebar itself sends nothing anywhere but the look for a newer herdr-fold (below).
- Chats reads Claude's and Codex's chat files (`~/.claude/projects/`, `~/.codex/sessions/`,
  `~/.codex/session_index.jsonl`), OpenCode's database (`~/.local/share/opencode/opencode.db`, read-only, asked
  whole each time) and AI Sessions' names (`names.json` of `herdr-fold.sessions-view`), never
  writing the chat files (Rename writes the name you give into that `names.json`, under AI Sessions' own
  lock; Delete…, once you answer its question, moves a closed chat's own file to the system's Trash and nothing
  else, as [A chat you delete](../../../SECURITY.md#a-chat-you-delete) lists); each file is read through once, then
  only where it grew, kept in `chat-index.json` in its state folder; the chosen chat's file is read on for its task
  list, and Open the plan copies the plan it approved into `plans/<id>/plan.md` there, for the preview tab.
  The archived chats, whether they are shown, the chat a pane reopens (until herdr knows its
  session), and whether the one-time note on a pane closed by hand was shown are in `chats.json` there. What
  each tab has had is in `panels.json` there: a pane closed by hand stays closed until it is brought back: its key,
  Restore panels (`panes.py --restore`, Cmd+Shift+O in herdr-fold), or the sidebar's ⋯ menu (a right click on the
  row too: the terminal closed or shown back, Restore panels). Copy chat puts one on the
  clipboard (`pbcopy` and, on a Mac, `osascript` for the formatted version). herdr's command line lists the running
  agents, goes to one (`herdr agent focus`), and reopens a closed chat (`herdr tab create`, `herdr pane split`,
  `herdr agent start` with the agent's own resume: `--resume`, `resume`, `--session`), and names a running one's pane
  and its own tab on Rename (`herdr pane rename`, `herdr tab rename`).
- For Agent, what the agent reads in the folder and in your home, as text: Claude's `CLAUDE.md` files and rules, its
  settings files (the organization's too), skills, subagents, `.mcp.json`, `~/.claude.json` (the servers and this
  folder's settings, never the account), the enabled plugins' own, and the lines of its newest sessions that tell the
  servers' state and what the open conversation used; Codex's `AGENTS.md` files, rules and skills, and its servers
  through `codex mcp list --json` (in a tab with Codex); OpenCode's `AGENTS.md` or `CLAUDE.md` files, and its config
  files and servers through `opencode debug config --standalone` in the home folder (a private server, never its
  background service), a project's `opencode.json` read as text, never run (its plugins are code).
  herdr's command line names the tab's agent (`herdr pane list`,
  `herdr agent list`). Retry runs `claude mcp get <name>` in the folder, which checks only a server Claude approved.
  On your press it runs the agent's own commands, each one argv with the server's name as one argument: `claude mcp
  login <name>` or `codex mcp login <name>` in a herdr tab (its pane read only for the address to open again), `mcp
  logout <name>`, and `claude mcp add --transport http --scope local|user <name> <url>` or `codex mcp add <name> --url
  <url>`; `/mcp enable|disable <name>` is typed into the tab's Claude, not sent. A form's Save writes one key of the
  agent's own settings file in the layer you choose (Claude's `settings.json` or `settings.local.json`, Codex's
  `config.toml`; never your organization's), and its Undo puts it back:
  [What each edit writes](../../../docs/harness.md#what-each-edit-writes). It reads and keeps no token.
- For Usage's costs and the graph's, every message's token counts in Claude's sessions and Codex's chats (no message's
  text), kept by the hour, model and session in `~/.local/state/herdr-fold/usage-index.json`, each file read once and
  then where it grew. A monthly budget you set in the Usage view is kept in `usage.json` there. The prices are fetched
  once a day (the request alone, under the update check's switch), else the bundled ones.
- Once a day at most, on a Mac where the installer ran, herdr-fold's latest release from api.github.com (the request
  alone), and at once on Check now in Settings' About, kept in `~/.local/state/herdr-fold/update.json` with the version
  last said as installed: a newer one puts a dot on More, and Settings' About says which and how to get it; after an
  update one herdr notification says it. About's Check for updates automatically switches the daily look;
  `HERDR_FOLD_NO_UPDATE_CHECK=1` keeps it off.
- It writes only what you ask for: a new file or folder, a new name, a commit, a push. Deleting moves to the system's
  Trash (the Recycle Bin on Windows, which asks first when an item cannot be recycled); an untracked file you discard
  goes there too. It never deletes for good on its own, pulls only fast-forward, and its file operations never touch
  `~/.claude`, `~/.codex` or `~/.local/state/herdr`, nor move a folder that holds one of them; the two exceptions
  are a chat you delete and a settings key an Agent form saves, both above.
- Its settings (hidden files, icons, the commit mode, the panels hidden, the issue each repository's next commit fixes,
  the Agent view's sections folded, the agent started last, which the folder picker and a new agent start as) are in
  `settings.json` in its state folder, `~/.local/state/herdr/plugins/herdr-fold.sidebar/`. A `colors.json` there,
  written by herdr-fold's theme setter, gives the theme's exact colors; without it the sidebar uses the terminal's
  own 16. What a space's preview tab shows is in `preview-<workspace>.json` there until the tab closes (`q`, Close
  Preview, or herdr's own close); a new preview tab's sidebar finds where the one that opened it was in a
  `seed-<tab>.json`, and deletes it. Either one left untouched for an hour goes when a sidebar starts (a pager ended
  without a chance to clean up leaves it); the next preview then opens a new preview tab in place of an old one. The
  issues of each repository and filter as last asked, a private repository's titles too, are in an `issues-….json`
  there, readable by you alone, for its other sidebars to take instead of asking GitHub again within the minute; one an
  hour old goes when a sidebar starts, and all of them when herdr-fold is removed.
- When an update changes its own files, it starts the new version in the same pane, once every file is in place,
  nothing of its own is running (a status or a search either: the program it runs would be left behind) and no
  question or name being typed is on screen, with the view, the open folders, the search and the message it had; an
  open menu does not hold it, and closes. The new version waits for whatever an earlier one still left behind. For
  that moment they wait in a `resume-….json` of its own in its state folder, which only its new version reads and
  deletes.

## Install

It comes with herdr-fold, in `~/.config/herdr-fold/plugins/sidebar`. On its own, from herdr's marketplace:

```sh
herdr plugin install princesshu/herdr-fold/src/plugins/sidebar
herdr plugin action invoke restore-panels --plugin herdr-fold.sidebar
```

The second command (`restore-panels-windows` on Windows) lays out the tab you are in: the sidebar above a terminal,
beside the agent, on the folder of the tab's panes; a new tab after it gets them by itself. To give it a key, a
`[[keys.command]]` in herdr's config with `type = "plugin_action"` and
`command = "herdr-fold.sidebar.restore-panels"`. From a copy of the folder, link it instead (`herdr plugin link
/path/to/sidebar`), or start it by hand in a herdr pane named `sidebar`
(`python3 /path/to/sidebar/sidebar.py ~/my-project`).

Its actions: the four that switch its view, Chats: find, and Restore panels; and the one-time tip when a pane
is closed by hand.

## Requirements

- herdr 0.9.5 or newer;
- Python 3.9 or newer, standard library only: `/usr/bin/python3` on macOS and Linux, `python` on Windows;
- git; and if you have them: ripgrep, bat, git-delta, a Nerd Font for the icons, Claude Code or Codex for the
  messages, gh for the issues.

## Author and license

Created by [princesshu](https://github.com/princesshu) as part of
[herdr-fold](https://github.com/princesshu/herdr-fold); herdr itself is the work of
[herdrdev](https://github.com/herdrdev/herdr). MIT, see [LICENSE](LICENSE). If you use or adapt it, please credit it
with a link to herdr-fold.
