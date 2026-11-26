# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The whole environment `herdr-fold 0.4.0` and its plugins `herdr-fold.sidebar 0.4.0`, `herdr-fold.sessions-view 0.4.0`
and `herdr-fold.spaces 0.4.0` (in Tab Layout's place), with herdr-fold's mod for herdr's desktop app.

### Added

- The Herdr app's title row and command palette: a row of its own across the window's top, the traffic lights in it on
  macOS, and at its centre a command field with the shown space's name; a press or Cmd + Shift + P opens herdr-fold's
  palette onto it, in place of the app's: the app's commands in the app's groups, then herdr-fold's own (Settings…,
  the views, Agents, Usage, Runs, New chat, Commit and push and more), each with its key, found as you type. See
  [The title row](docs/app.md#the-title-row).
- The Spaces list shows the repository inside a folder that is no repository itself, its branch with ↑ to push and ↓
  to pull, in both clients; Changes and the app's tab bar follow that repository, where they said "Not a git
  repository" before.
- An agent in another tab of the TUI that starts waiting on you says so once, in herdr's own note at the bottom right
  (`claude needs attention`, `claude finished`), never for the tab in front; herdr's sounds stay off.
- The TUI's New space picker has Add machine…, beside Cancel and Open.
- A chat tab in the Herdr app: Claude's chat drawn as a timeline from its session file, a call and its result one row;
  what Claude waits on (a command, a change, a question, its plan) answered in a card in the prompt's place, its answers
  numbered; a message typed while Claude works waits its turn; Claude's own terminal a press away, shown by itself when
  Claude asks there. See [The chat](docs/app.md#the-chat).
- New chats in the Herdr app: + after the tabs (Cmd + N) opens a chat with the agent used last, nothing running until
  the first message starts it; the agent's chip lists the installed agents (the recent first, one to sign in marked,
  the ones not installed dim), one the chat cannot draw yet opening its own CLI in a terminal tab. >_ opens a terminal.
  Settings' Open agents in, Chat or Terminal, decides how every way in opens an agent (+, Chats, Issues' To the agent,
  a new space); with Chat, a space on this Mac that holds shells alone gets an empty chat as its first tab, once. See
  [New chats](docs/app.md#new-chats).
- The chat's model and modes: the model chip names the model and its effort (Opus 5.5 High; on Default, the model
  Default runs as), and lists Claude's models; the mode chip opens Modes, with Effort on a slider and Ultracode's
  switch. Picked before the agent runs, they go with its start; after, as `/model`, `/effort` and Claude's own
  shift+tab. See [Model, mode and effort](docs/app.md#model-mode-and-effort).
- The chat's context and cost: the bar's meter (`context 34%`) opens the Context panel, with what fills the context in
  the Agent panel's colors, what the chat cost by model, Compact and `Show all in Agent`; over the prompt, a notice
  once a month when an agent on an API key nears or passes its budget. See
  [Context and cost](docs/app.md#context-and-cost).
- The chat's + and / menus: + uploads files from your Mac or adds a file by "@" (the changed files first), and turns
  each connector on or off in the folder; / lists this chat's Export the chat…, the folder's skills and Claude's
  commands, found as you type. A connector's call wears its service's logo in the timeline, and a server that comes to
  need a sign-in is a step with Connect. The bar's clock shows this folder's chats in Chats.
- The Start tab: a home space opens on `Open a project`, Open project… and the folders of the chats so far, each one
  press from a space of its own with a new chat. An empty chat whose agent is not signed in lists every installed agent
  with its Sign in or Use, and shows its prompt once one is in.
- OpenCode as a coding agent, in both clients: in the agents' lists, its CLI in a terminal tab from New chat and a new
  space (the TUI's picker: `claude │ codex │ opencode`), its chats in Chats from its own database (reopened with
  `opencode --session`, copied and archived, never deleted here), and in the Agent panel the instructions it reads,
  its model and its MCP servers, a project's config read as text and never run. It has no form, graph or run here, and
  Usage says its limits are not told.
- A chat's task list and its approved plan, in both clients: Claude's tasks and Codex's plan in one place, a strip over
  the app's prompt (`3 of 5 done`) and under the chosen chat in the TUI's Chats; a plan approved in plan mode opens with
  Open the plan. The app's timeline tells only the changes (`Tasks 5 added`, a ticked line for each step done).
- Checkpoints: a Claude chat's files back to how they were at one of its prompts. In the app the prompt under the
  mouse offers Restore files to here; in the TUI a Claude chat's Checkpoints… in Chats (or →). Claude says first which
  files would change and what stays; the restore is Claude's own `--rewind-files`, and one Undo puts the files back.
  See [Checkpoints](docs/usage.md#checkpoints).
- The TUI sidebar folds to a rail of icons by » or Cmd + Option + B, in every tab, the tab's terminal moved under the
  agent and raised or lowered by the rail's Terminal; a press on an icon or a view's key opens it again on that view.
- The TUI sidebar's More lists its views, each checked while shown: one unchecked leaves the row in every tab.
- Pull requests, in both clients: the branch's own under Changes' repository row (its checks and state), or Create
  pull request…, its title and body written by Claude or Codex from the branch's commits, Draft by default; the
  repository's Pull requests beside Issues, `your review` in yellow where one waits on you. In the Herdr app a review
  in the preview tab: comments on a line, Reply, Resolve, Comment, Approve or Request changes; the TUI shows it read
  only. See [Pull requests](docs/usage.md#pull-requests).
- An issue handed to the agent with none in the tab starts one, in both clients: the agent started last, with the
  issue's prompt (in the app, as + starts it: a chat or a terminal).
- Delete… for a closed chat in Chats, in both clients: asked first by the chat's name, then the chat's file goes to the
  system's Trash, its archive mark and name dropped; Archive stays the everyday way. See
  [A chat you delete](SECURITY.md#a-chat-you-delete).
- herdr-fold's own Settings in both clients, More's Settings… in the TUI (herdr's popup) and one window in the app
  (the sidebar's Settings, Cmd + ,): General (the TUI's icons; the app's Open agents in), Notifications (An agent waits
  on you, on or off) and About (the version and license, the update check and its switch, What's new, Third-party
  notices). The app's Application sections open the app's own Settings there.
- The Agent panel, in both clients (the app's dock tab, the TUI sidebar's Agent view, `5`): what the agent starts with
  in the folder, its model, effort and start-up context, then Usage, Subagents, Rules, Skills, Permissions (the mode or
  approval, the sandbox, the rules, the conflicts, every hook) and Connectors, a failed server or one to sign in to
  first; a row's properties with Open, Show in graph and Retry; the head's list switches between the agents on the Mac,
  says one to sign in and shows how one not installed installs. Its tab or icon carries a dot while the setup has a
  problem. See [The agent's harness](docs/harness.md).
- Changing an agent's setup from the Agent panel, in both clients: the mode, the model and effort, the sandbox and its
  hosts, Codex's approval, a permission rule added, changed, moved or removed, a conflict solved, a skill, a subagent,
  a connector or every hook off or on for the folder, a project's server approved. A form shows the layer it saves in,
  the line it writes and when it applies before anything is written; a save writes one key of the agent's own settings
  file, never your organization's, with Undo after. See [Changing the setup](docs/harness.md#changing-the-setup).
- Connectors managed from the Agent panel, each change the agent's own command and no token kept: Connect signs in
  through your browser, Sign out, a connector added from claude.ai or by its address, and each one off or on for the
  folder. A known service's connector wears its maker's name and logo.
- Media connectors: image, voice and video services (fal, ElevenLabs, FLUX, Runway, Higgsfield, Luma, Cartesia,
  Meshy), each saying what it makes and its calls today, as they bill in credits; the hosted ones offered by name in the
  add form, signed in to in the browser, never a key. What a chat made shows in the preview tab with the model, the
  prompt, the skill and the calls under it, audio and video too; Ask for another asks that chat. See
  [Media services](docs/harness.md#media-services).
- Usage in the Agent panel, its first section: an agent a row, a plan's 5-hour and weekly limits as bars in the status
  line's colors, or an API key's month against its budget, the agent shown first; folded, one figure.
- The TUI's keys in the Herdr app's herdr-fold layout: moving (Cmd + 1…9, Cmd + ↓ / ↑, Cmd + T / R, Cmd + D / E,
  Ctrl + B, then 1…9 or w) and the TUI's commands (a new space in a folder, Add machine…, the dock hidden or shown,
  Restore panels, a file the terminal's output names, the color themes). See [Keys](docs/keybindings.md#the-herdr-app).
- Editing files. In the Herdr app a text file opens in a tab of its own in the app's editor: Cmd + S saves in place,
  Cmd + F finds, a draft is kept so closing asks nothing, and a bar offers Reload or Keep mine when the disk changed. In
  the TUI it opens in your own editor (`$VISUAL`, `$EDITOR`, else micro, which the installer brings) in a tab of its
  own, the Cmd keys the editor's own there; `e` edits a drawn page or SVG. See
  [Editing files](docs/usage.md#editing-files).
- The preview draws every picture macOS reads (HEIC, AVIF, PSD, EXR, a camera's raw file…), one no browser shows
  opening in Preview; an SVG's or a page's code above its picture where the room is taller than wide, or as chosen; the
  TUI's status row starts with Code, Split and Picture, as the app's buttons.
- A changed picture in Changes shows as an image diff in both clients: before and after side by side, each under its
  name and size.
- An agent's graph: the Herdr app's Agents tab draws what goes in, the agent with its subagents and what they use, each
  edge with its gates (`allow pytest`, `deny git push`); the TUI writes it as a tree in the preview tab (`g`). This chat
  shows what one chat ran, numbered in order, with each agent's cost. See [The graph](docs/harness.md#the-graph).
- The Usage view: what the agents used and what that cost, each message at its model's list price (fetched once a
  day under the update check's switch): the period, a summary, each day by model, an API key's month against its
  budget, the projects, chats and models; Budget… and, in the app, Export CSV. The app's Agents tab has it; the TUI
  opens it over the tab (`U`). See [The Usage view](docs/harness.md#the-usage-view).
- Runs, the Agents tab's third view (the TUI: `r` in the Agent view): Claude's background sessions and Codex's
  `codex exec` runs and cloud tasks, each with what it made and its cost; Attach, Stop, Open as chat, Run again, Show
  diff and Apply, each the agent's own command; New run starts one. The app's status bar says `1 run working`. See
  [The Runs view](docs/harness.md#the-runs-view).
- One tilde before every dollar figure herdr-fold computes (`~$18.40`, `~$130.90 API value`): an estimate at list
  prices, on a plan what that use would cost on the API; a budget you set wears none.
- The session's cost in Claude's status line, one more item to choose (off until chosen): `~$4.12`, Claude's own count.
- herdr-fold Mono, both clients' monospace font: JetBrains Mono with Nerd Fonts' icons, its line 10% taller, and the
  symbols Claude Code, Codex, herdr and starship print that it lacked. The TUI's installer puts it in
  `~/Library/Fonts`; the Herdr app loads it from the mod. See [The font](docs/installation.md#the-font).
- Every popup herdr-fold opens in the TUI (Settings, closing a tab, the folder and theme pickers, Cmd + Shift + L's
  files) has a close button at its top right, its tip `Close (Esc)`.

### Changed

- Tab Layout (`herdr-fold.tab-layout`) is gone, its work split: the sidebar lays out every new empty tab and comes back
  in every tab when herdr starts, and Spaces (`herdr-fold.spaces`) keeps the rest (the **new** button's folder picker,
  a space following its folder, the question before a tab with a chat closes, the agents started again after a
  restart). The installer asks `Let a new space ask for its folder, and herdr-fold's agents start again after a
  restart?` in place of its old question, and a remote machine gets the three plugins linked.
- Conversations is Chats in both clients, its saved state and its actions too: herdr's action
  `herdr-fold.sidebar.find-conversation` is `herdr-fold.sidebar.find-chat` (a key bound by hand to the old id has to
  name the new one).
- The TUI's Chats list opens over the sidebar from Chats, after Issues in the row, a dot beside it while a chat waits
  on you; the chat column, its rail and a tab's third column are gone.
- The TUI sidebar shows one view at a time under a row of buttons, each its icon over its name (the icons alone when
  narrow); the right column keeps one width, in cells, in every tab and window and after a restart.
- The TUI's Spaces list stands a space's branch under its name, its wait (`waiting 12m`) beside the name.
- A root's space is named by a word in both clients, as home's is: `root`, or the drive (`C:`).
- The terminal's prompt no longer names the repository, which the space already shows: at its top the branch, its
  status and the ❯ alone; below it the path inside it above them.
- The theme preview sketches each theme's window as the TUI draws it now.
- Chats look alike in both clients: no space dot or tree lines, the agent and the age as two muted columns, `Filter
  chats`, `Archived "Login redirect fix"` under the list.
- A fold turns its chevron as it opens or shuts, one chevron everywhere in the TUI.
- A theme, the dock folded or opened, and a setting changed in another tab reach every TUI sidebar within a second.
- The Herdr app's right panel is one card with its views' text tabs on top (Files, Search, Changes, Issues, Agent),
  Changes' count in a badge; Chats, More and » stand at the tab bar's end, Chats opening its list in the view's place
  (it left the left sidebar); folded, the tab's terminal stands under the tab.
- The Herdr app's two side docks work as one: a panel floats beside its rail every time and closes on a press beside
  it; Cmd + B folds the left sidebar, which is never hidden; Esc in a float goes to its view first.
- The Herdr app draws its surfaces as the TUI does: every card (the chat, the dock, the preview, the terminal) on the
  terminals' background, the window, its bars and the left sidebar in herdr's sidebar color, one color in most themes,
  the cards parted by their border; the popovers a step lighter, so they float. See
  [Color](docs/styleguide.md#color).
- The Herdr app's status bar is herdr-fold's own: the machine and branch, the agents in words (`1 of 3 agents waiting
  for you`), and the one update there is (Herdr's, herdr-core's or a newer herdr-fold).
- Hidden files show in Files by default, in both clients.
- One wording in both clients: a folder's right click says New space, and Add machine… ends in … where it opens a
  window.
- The TUI's Add machine opens its own window, Add a machine, framed as Settings: its close button, Esc or Ctrl + C end
  it at any question.
- The installer no longer lists Tailscale as missing: it is one way to a machine, any SSH reaches one.
- The installer keeps no copy of herdr-fold's own earlier files, which the package has; what is yours stays saved as
  before, on a remote machine too.
- The Herdr app's styleguide lists its parts in an index at its side and draws the one picked.
- The sidebar plugin is named "Sidebar" on herdr's marketplace card, and Spaces stands in Tab Layout's place there.

### Removed

- The installer no longer installs JetBrainsMono Nerd Font nor sets Ghostty's `adjust-cell-height`: herdr-fold Mono
  carries both. One installed before stays.
- The update notices on the TUI sidebar's last row and in a toast, and More's version line and Check for Updates, in
  both clients: More's dot, the app's status bar and Settings' About say it now.
- Cmd + Shift + H, which collapsed the TUI's chat column.

### Fixed

- A New space or Add machine left before it is done no longer leaves an empty "new" space in the list.
- Shift + Enter starts a new line in Claude Code in every pane of the TUI and every terminal of the Herdr app; it sent
  the message where the agent had not asked the terminal for the extended keys.
- In the Herdr app, the terminal at the dock's foot can be made taller or lower: the boundary drags, as the TUI's.
- The 5-hour and weekly limits are the same in every space, status line and notice: an idle chat no longer puts an
  older reading back, and a chat's second weekly limit no longer takes the weekly's place.
- The TUI's right column keeps the width chosen when the window changes, and no longer jumps when herdr's own sidebar
  folds or opens; a column dragged past the least it can be comes back to it in every tab.
- Chats no longer lists one chat as many rows: a project folder linked to another's listed its chats twice, and a
  program's runs through Claude's Agent SDK were rows. Copy chat no longer repeats a compacted chat.
- The home folder stays the first row of Spaces in both clients, though its last tab is closed.
- In the TUI, a space whose only tab is closed with herdr's own close is made again in its place; one closed on purpose
  stays closed.
- Issues, Chats and Changes no longer jump, in both clients: a refresh keeps the list where it is, a spinner in its
  button's place, and what was done or went wrong stands under the list.
- The TUI's terminal, moved or resized by the sidebar, draws a bare shell's prompt again from its top.
- An update while the Herdr app runs closes it for that moment and opens it again on the new mod, your terminals
  running on; before, it drew the earlier version until it was quit.
- The TUI's Changes no longer misses a change made just after its last look.
- Changes made at the same moment are all kept: a chat archived while the list is read, a width dragged, a setting
  changed in two tabs or in the TUI and the app.
- A second Enter or click on a closed chat while it reopens no longer opens it in a second tab.
- The TUI preview's key hints in a narrow pane are left out whole, never cut.
- Claude's status line writes the weekly reset as the machine writes hours (`Monday 13:00` on a Mac set to 24 hours).
- The license and the notices of what herdr-fold builds on go with every install: each machine's folder and the Herdr
  app's mod.
- The Herdr app's themes: a control has its own fill, frame and hover; captions, counts and the words under the pointer
  read 4.5:1 at least; each source's tag has a color of its own. The styleguide opens in a tab named Styleguide.
- A menu opens above its button, or the row clicked, where it does not fit under it, in both clients.
- Ghostty's app icon in the theme's colors is a PNG, a format Ghostty documents, and the theme's line warns where
  Ghostty's own config does not take it.
- The TUI sidebar's last row says what herdr refused in herdr's own sentence, not its JSON answer.
- The Herdr app's sides, dragged and let go, settle as the TUI sidebar does: under 160 px a side is its rail, and a rail
  dragged more than 24 px wider opens as wide as it was.

## [0.3.0] - 2026-11-08

The whole environment `herdr-fold 0.3.0` and its plugins `herdr-fold.sidebar 0.3.0`, `herdr-fold.sessions-view 0.3.0`
and `herdr-fold.tab-layout 0.3.0`, with herdr-fold's mod for herdr's desktop app.

### Added

- herdr-fold in herdr's desktop app: a mod with the sidebar's Changes view (the changed files, staged by file or all at
  once, a change discarded (a new file into the Trash), a file's diff, the message Claude or Codex writes, Commit,
  Commit & Push or Commit & Sync, Cmd + Shift + C's commit and push in one step (with nothing to commit, the push of the
  commits ahead), the repository's row as VS Code's (sync, pull, push), and the Graph of the last commits with each
  one's diff), Search (the space's folder, with the TUI's switches, a hit's file shown at its line) and Issues (by
  priority, with the TUI's filters; an issue handed to the tab's Claude or Codex and linked to the next commit, a reply,
  Assign to me, close or reopen; Cmd + Shift + I); a diff, a commit or an issue opens in the space's preview tab, as in
  the TUI; its own Spaces list, as the app's, with the TUI's waits (`waiting 12m`, Cmd + Shift + U), and its own tab
  bar, as the app's, each button saying what it does; Conversations in the left sidebar (this Mac's conversations by
  space, a closed one reopened in a new tab, Rename, Copy conversation, Archive; Cmd + Shift + R), the archived ones and
  the names shared with the TUI's column, and folded, the sidebar a dock of icons, as Illustrator's panels, and so the
  right panel (its toggle, Cmd + Shift + G or a drag), each view and the tab's terminal floating beside its rail; the
  right panel one panel group, its views as its tabs, Files among them (the TUI's, where the app's own was: Catppuccin
  Icons' files and folders, git's marks, a file in the preview tab, New File, New Folder, Rename, Copy Path, Move to
  Trash, New Workspace); for a space on this Mac or on another machine (Linux, macOS or Windows), with the TUI's data
  layer underneath; a layout of its own puts it in the right panel, where the app's Changes was (Cmd + Shift + G), dark
  in the TUI's colors (Catppuccin Mocha), its terminals and code in Menlo as VS Code's, at the TUI's size; the TUI's
  twelve themes come along in the app's Settings; under it, each tab's own terminal, as the TUI's right column has it,
  on the space's machine; Lucide's icons, and a file's Catppuccin Icons' for its type. Where the Herdr app is on the
  Mac, `install.sh` sets it up when its first question names the app, the remote machines in the app too;
  `uninstall.sh` takes it off. See
  [The Herdr app](docs/app.md).
- The installer asks first for the TUI, the Herdr app or both, a page in the browser showing each; the default is
  what is installed, and `HERDR_FOLD_PARTS` answers it. Each step sets up only what the chosen parts need: the Herdr
  app alone installs nothing of the TUI's and runs no herdr. The other part is added later by running it again. With
  the Herdr app chosen and not on this Mac, it offers the app's own installer. See
  [Installation](docs/installation.md#the-tui-the-herdr-app-or-both).
- One theme for both parts: the installer and the TUI's theme picker set herdr-fold's layout in the Herdr app too, and
  a running app switches at once; an update keeps the theme there is. See [Themes](docs/themes.md).
- An image or a PDF chosen in Files is drawn in the preview tab, an image fitted to it and never larger than it is, a
  PDF's pages one under another, a gap apart, scrolled (in the app clear of the scrollbar, smaller in a narrower tab):
  in the sidebar (Ghostty shows pictures in herdr; the wheel, ↑ ↓, Space, `g` `G`) and in the Herdr app mod, its page in
  view above them. A page, a PDF or an image opens in the default browser from Files' right click, or `o` and a button
  in the preview tab. See [The sidebar](docs/sidebar.md) and [The Herdr app](docs/app.md#the-preview-tab).
- An SVG or an HTML page chosen in Files shows its code and its picture side by side in the preview tab, as VS Code's
  preview to the side: the divider between them drags and the page is drawn for its side as a browser that size shows
  it, an SVG at its own size, never larger, what it leaves empty clear (in the Herdr app mod on a canvas, as a design
  tool's artboard). `c` in the sidebar, Code, Split and Picture in the app show either alone or both again; a right
  click in the preview tab offers them, Open in Browser and Close Preview. macOS's WebKit draws it offline: nothing is
  asked of the network and none of its scripts run, so a file cannot learn who opened it. See [the sidebar's
  README](src/plugins/sidebar/README.md) and [The Herdr app](docs/app.md#the-preview-tab).
- In the Herdr app mod, a space's first tab is named as the space until it is renamed, as the TUI's main tab.
- herdr-fold says when a newer version is out: once a day it asks api.github.com for its latest release (the request
  alone), says a newer one once (a herdr or Herdr app notification) and keeps it on the sidebar's last row. The
  version installed is in the sidebar's ⋯ menu, a right click on the app panel's tabs and the installer's last line;
  Check for Updates there, or `HERDR_FOLD_NO_UPDATE_CHECK=1`, turns the look off. See
  [Installation](docs/installation.md#a-newer-version).
- Files' right click offers Close Preview while the workspace has a preview tab, in the sidebar and in the Herdr app
  mod; a preview tab closed any way forgets what it showed, as `q` does.
- A remote machine is prepared for the parts installed on the Mac: with the Herdr app alone it gets git, Python and
  the status line, joins the app's core and nothing of herdr's or starship's. See
  [Remote machines](docs/remote-machines.md).
- The uninstaller takes off the TUI, the Herdr app or both: with both installed it asks which, both by default, and
  `HERDR_FOLD_PARTS` answers it. Either goes alone and the other keeps working; what both use (the status line, the
  archived conversations, the linked issues, the records) goes with the last. See [Uninstall](docs/uninstall.md).
- Cmd + Shift + U marks the focused agent unread: its workspace says `waiting` again, from then, until you come back
  to it after leaving it; again on a marked one takes the mark off. See [Sessions](docs/usage.md#sessions).
- The Herdr app's layout comes with its recipe and a picture, `app/RECIPE.md` and `app/preview.png`, as the app's
  catalog of layouts lists one: what it shows, how it behaves, what it is built from, so another agent can build it
  again. See [The Herdr app](docs/app.md#installing-it).
- A styleguide for the Herdr app mod: its colors, type, sizes and icons, each part in each of its states and the
  panels they make, drawn by the views' own code; `herdr-app do herdr-fold.styleguide` opens it, and
  [Styleguide](docs/styleguide.md) shows it on GitHub.
- The sidebar in a workspace whose folder is no repository itself (your home folder, a folder of projects): Changes
  shows the repository of the folder or file chosen in Files, however deep, with its changes, commit and sync; Files'
  marks and the Issues view follow it. See [The sidebar](docs/sidebar.md#how-it-starts).
- Tips in the sidebar: a control shown by an icon alone says what it does once the mouse rests on it
  (✦, ↻, the view tabs, a row's Stage, Unstage, Discard and diff icons, the Files and Search buttons). A changed
  file's row in Changes shows its whole path in the repository, as in GitHub Desktop, on more rows when it is long;
  so does the Herdr app mod's. A name Files cuts short shows its whole path in the folder the same way.

- An update takes off what an earlier version put in the Herdr app and the new one no longer brings: a theme, a key,
  a setting the mod no longer keeps. The uninstaller takes herdr-fold's settings in the app off too, closing a running
  app for that moment (your terminals keep running) and opening it again. Without the TUI, `python3 lib/herdr_app.py
  install .` sets the mod up and updates it. See [Uninstall](docs/uninstall.md).

### Changed

- While the AI writes the commit message, the field says who writes it, with a spinner: "Claude is writing the
  message…" (Codex when it writes), in the sidebar and in the Herdr app mod; with a message of yours in the field,
  the sidebar says it under Commit.
- The sidebar names its views and the tab's panes in lowercase, as herdr names its own (`changes` beside the view
  tabs, Close conversations in the ⋯ menu).
- The sidebar's Changes view puts the repository on top, as VS Code's Repositories: its name, branch, sync and a
  ⋯ that pulls or pushes alone or opens it on GitHub; the status bar at the sidebar's bottom is gone, its branch
  and sync with it. See [The sidebar](docs/sidebar.md).
- Committing needs no staging, as in GitHub Desktop: with nothing staged, a commit and its written message take every
  change, in the sidebar and in the Herdr app mod; a file .gitignore names is never one of them, nor shows in Changes,
  even if it was tracked before. The sidebar commits exactly the changes it showed (and asked about, for files named
  like secrets): one come since waits. Something staged by hand is still committed alone.
- The sidebar's Changes view keeps the Graph at its bottom, the changes scrolling above it on their own; ↑ and ↓
  cross from one to the other. Each file's letter stands under its section's count. A folded section stays folded
  after an update or a restart, and a new version comes back to the rows you were on.
- The sidebar's Commit button looks the same however the focus came to it, with no dark box over its label; the
  Herdr app mod's stays in the accent too while it cannot commit yet, its message and ✦ above it.

### Fixed

- The sidebar's fields select text as text fields do, the commit message too, where it went only a letter at a
  time: Cmd + A, Shift with an arrow, Home or End, and in the message a drag, a double click (a word) or a triple
  click (all of it); Backspace or Delete takes the selection whole, typing or pasting replaces it, and
  Alt + Backspace takes the word before the cursor. Cmd + A no longer flashes the window (Ghostty's own select
  all, of every pane): it reaches only the sidebar's field you are in. See [Keys](docs/keybindings.md).
- Cmd + Shift + I opens the sidebar's Issues view: the key herdr sends it for that (F12) was not read.
- The AI's button beside a commit message of several lines has its star in the middle: the field opens to an odd
  number of rows, up to seven, a message of two lines with an empty third.
- In the Herdr app mod, a changed file asked about before a discard keeps its name clear of the question: the name
  is cut short, and "Discard?", "Discard all?" and "Move to Trash?" stay whole.
- A preview tab opens as the tab it came from: its columns as wide to the cell, a folded Conversations column folded
  from the start, and it shows once its sidebar and Conversations column have started, with no shell's prompt or
  empty column for a moment.
- The sidebar's commit message scrolls with the wheel: a message longer than the field (one Claude or Codex wrote)
  shows its other rows, the cursor where it was, until a key moves it. A selection goes on past the field's edge,
  the rows following it, and the wheel moves the message while a drag selects.
- The sidebar's lists start at their top when a preview tab or a new version brings back the row chosen: a commit
  chosen in the Graph no longer hides the Graph's heading.

### Security

- The commit message writer (the sidebar's Changes view and Cmd + Shift + C) reads a repository's `/commit` rules only
  from inside it: a downloaded folder's rule file linking to a file elsewhere, a key, is passed over, as its text would
  go to the AI. A written message is checked against the changes alone, never against the rules.

## [0.2.0] - 2026-11-02

The whole environment `herdr-fold 0.2.0` and its plugins `herdr-fold.sidebar 0.2.0`, `herdr-fold.sessions-view 0.2.0`
and `herdr-fold.tab-layout 0.2.0`.

### Changed

- The plugins' names, as herdr's marketplace lists them: `Full Setup` (`herdr-fold`), `AI Sessions`
  (`herdr-fold.sessions-view`), `Files · Search · Git · Issues · AI Conversations` (`herdr-fold.sidebar`) and
  `Tab Layout` (`herdr-fold.tab-layout`); AI Sessions' action is now `AI Sessions: reapply`.
- The folder picker is a tree, as the sidebar's Files view: the folder on top in place of the . row, → and ← open and
  close a folder, ← on the top row goes up one; no repositories from elsewhere at its top.

### Added

- The sidebar's Files view: a folder's right click offers New Workspace, which opens herdr-fold's folder picker on it,
  as herdr's new button does.
- A workspace whose folder is deleted says deleted beside its branch, in the theme's red.
- A workspace where an agent waits on you, blocked or done and not seen yet, says how long beside its branch
  (`waiting 12m`), in the theme's yellow; it counts on while you work elsewhere. See
  [Sessions](docs/usage.md#sessions).
- Cmd + Shift + L: the files the focused pane's output names (`src/app.py:42`, a traceback's line), the newest first;
  Enter shows one at that line in the sidebar's preview tab. See
  [Opening a file the agent named](docs/usage.md#opening-a-file-the-agent-named).
- Buttons where a key was the only way: Cancel and Open in the folder picker, Cancel and Close when a tab with a
  conversation is closed.
- The folder picker takes the mouse: a click chooses a folder, a double click opens it, the wheel moves, and a click
  on Claude or Codex switches the agent.

### Fixed

- A folder renamed or moved: its workspace and main tab take the new name (a name you gave the workspace stays; a
  folder renamed earlier is known by the Claude conversations kept under its old name), and the sidebar opens on it
  again, where it was. Before, the workspace kept the old name and the sidebar showed an empty list.
- Esc in the folder picker goes back to the workspace it was opened from; before, herdr showed a neighbour of the
  closed one.
- The folder picker's rows fit a narrow window (a half-screen Ghostty); before, they wrapped and a click landed a row
  off.
- The small windows (the folder picker, Cmd + Shift + L's list, the close question) keep a cell clear at both edges;
  before, the buttons touched the right border and the title the left one.

## [0.1.0] - 2026-11-01

First release.

### Added

- The installer: Ghostty, herdr, starship, gh, bat, git-delta, ripgrep and the JetBrains Mono Nerd Font with Homebrew,
  after a yes and only what the Mac lacks; their settings, twelve color themes (Ghostty's app icon too: herdr-fold's
  logo, the sheep, in each theme's colors), the Claude Code and Codex status lines, and herdr's Claude and Codex
  integrations; herdr settings of your own are kept. Run again, it updates after one question, with your earlier
  choices. See [Installation](docs/installation.md) and [Themes](docs/themes.md).
- Workspaces: one per repository from a folder picker, the agent beside the Conversations column and the sidebar above
  a terminal; keys for workspaces, tabs, panes and sessions; commit and push with an AI-written message; formatted
  copy; search in the Claude conversation. See [Using it](docs/usage.md) and [Keys](docs/keybindings.md).
- herdr's marketplace: `herdr plugin install princesshu/herdr-fold` (`herdr-fold 0.1.0`, the whole environment)
  opens the installer in a herdr tab; the sidebar and the Sessions list install alone from there too.
- Three herdr plugins; the first two also install on their own:
  - `herdr-fold.sidebar 0.1.0`: Files, Search, Changes and GitHub Issues with previews, on macOS, Linux and Windows,
    and the Conversations column with every workspace's Claude and Codex conversations. See
    [The sidebar](docs/sidebar.md).
  - `herdr-fold.sessions-view 0.1.0`: the Sessions list, each conversation under its name, with its state; the same
    name on its pane and on the tab it has to itself.
  - `herdr-fold.tab-layout 0.1.0`: new workspaces and tabs laid out, and the panes back after a restart.
- Remote Linux, macOS and Windows machines over SSH, with their own workspaces, sidebar and status line. See
  [Remote machines](docs/remote-machines.md).
- The uninstaller, which names what it leaves and where. See [Uninstall](docs/uninstall.md).
- Privacy: no telemetry; the plugins' state readable by you alone; a hand-added machine's host key shown and confirmed
  before the first connection; a privacy test over every file and every commit. See [Security](SECURITY.md).

[Unreleased]: https://github.com/princesshu/herdr-fold/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.3.0
[0.2.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.2.0
[0.1.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.1.0
