# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The installer asks first for the TUI, the Herdr app or both, a page in the browser showing each; the default is
  what is installed, and `HERDR_FOLD_PARTS` answers it. Each step sets up only what the chosen parts need: the Herdr
  app alone installs nothing of the TUI's and runs no herdr. The other part is added later by running it again. With
  the Herdr app chosen and not on this Mac, it offers the app's own installer. See
  [Installation](docs/installation.md#the-tui-the-herdr-app-or-both).
- One theme for both parts: the installer and the TUI's theme picker set herdr-fold's layout in the Herdr app too, and
  a running app switches at once; an update keeps the theme there is. See [Themes](docs/themes.md).
- An image or a PDF chosen in Files is drawn in the preview tab, fitted to it, a PDF page by page: in the sidebar
  (Ghostty shows pictures in herdr; ↑ ↓ turn the pages) and in the Herdr app mod (Previous, Next). A page, a PDF or
  an image opens in the default browser from Files' right click, or `o` and a button in the preview tab. See
  [The sidebar](docs/sidebar.md) and [The Herdr app](docs/app.md#the-preview-tab).
- A remote machine is prepared for the parts installed on the Mac: with the Herdr app alone it gets git, Python and
  the status line, joins the app's core and nothing of herdr's or starship's. See
  [Remote machines](docs/remote-machines.md).
- The uninstaller takes off the TUI, the Herdr app or both: with both installed it asks which, both by default, and
  `HERDR_FOLD_PARTS` answers it. Either goes alone and the other keeps working; what both use (the status line, the
  archived conversations, the linked issues, the records) goes with the last. See [Uninstall](docs/uninstall.md).
- Cmd + Shift + U marks the focused agent unread: its workspace says `waiting` again, from then, until you come back
  to it after leaving it; again on a marked one takes the mark off. See [Sessions](docs/usage.md#sessions).
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
  Mac, `install.sh` asks once and sets it all up, the remote machines in the app too; `uninstall.sh` takes it off. See
  [The Herdr app](docs/app.md).
- A styleguide for the Herdr app mod: its colors, type, sizes and icons, each part in each of its states and the
  panels they make, drawn by the views' own code; `herdr-app do herdr-fold.styleguide` opens it, and
  [Styleguide](docs/styleguide.md) shows it on GitHub.
- The sidebar in a workspace whose folder is no repository itself (your home folder, a folder of projects): Changes
  shows the repository of the folder or file chosen in Files, however deep, with its changes, commit and sync; Files'
  marks and the Issues view follow it. See [The sidebar](docs/sidebar.md#how-it-starts).
- Tips in the sidebar: a control shown by an icon alone says what it does once the mouse rests on it
  (✦, ↻, the view tabs, a row's Stage, Unstage, Discard and diff icons, the Files and Search buttons). A changed
  file's row in Changes shows its whole path in the repository, as in GitHub Desktop, on more rows when it is long;
  so does the Herdr app mod's.

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

[Unreleased]: https://github.com/princesshu/herdr-fold/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.2.0
[0.1.0]: https://github.com/princesshu/herdr-fold/releases/tag/v0.1.0
