# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Cmd + Shift + U marks the focused agent unread: its workspace says `waiting` again, from then, until you come back
  to it after leaving it; again on a marked one takes the mark off. See [Sessions](docs/usage.md#sessions).
- herdr-fold in herdr's desktop app: a mod with the sidebar's Changes view (the changed files, staged by file or all at
  once, a tracked file's change discarded, a file's diff, the message Claude or Codex writes, Commit, Commit & Push or
  Commit & Sync, sync, and the Graph of the last commits with each one's diff), for a space on this Mac or on another
  machine (Linux, macOS or Windows), with the TUI's data layer underneath; a layout of its own puts it in the right
  panel, where the app's Changes was (Cmd + Shift + G). Where the Herdr app is on the Mac, `install.sh` asks once and
  sets it all up, the remote machines in the app too; `uninstall.sh` takes it off. See [The Herdr app](docs/app.md).
- The sidebar in a workspace whose folder is no repository itself (your home folder, a folder of projects): Changes
  shows the repository of the folder or file chosen in Files, however deep, with its changes, commit and sync; Files'
  marks and the Issues view follow it. See [The sidebar](docs/sidebar.md#how-it-starts).
- Tips in the sidebar: a control shown by an icon alone says what it does once the mouse rests on it
  (✦, ↻, the view tabs, a row's Stage, Unstage, Discard and diff icons, the Files and Search buttons). A changed
  file's row in Changes shows its whole path in the repository, as in GitHub Desktop, on more rows when it is long;
  so does the Herdr app mod's.

### Changed

- Committing needs no staging, as in GitHub Desktop: with nothing staged, a commit and its written message take every
  change, in the sidebar and in the Herdr app mod; a file .gitignore names is never one of them, nor shows in Changes,
  even if it was tracked before. The sidebar commits exactly the changes it showed (and asked about, for files named
  like secrets): one come since waits. Something staged by hand is still committed alone.
- The sidebar's Changes view keeps the Graph at its bottom, the changes scrolling above it on their own; ↑ and ↓
  cross from one to the other. Each file's letter stands under its section's count. A folded section stays folded
  after an update or a restart, and a new version comes back to the rows you were on.

### Fixed

- The sidebar's fields select text as text fields do, the commit message too, where it went only a letter at a
  time: Cmd + A, Shift with an arrow, Home or End, and in the message a drag, a double click (a word) or a triple
  click (all of it); Backspace or Delete takes the selection whole, typing or pasting replaces it, and
  Alt + Backspace takes the word before the cursor. Cmd + A no longer flashes the window (Ghostty's own select
  all, of every pane): it reaches only the sidebar's field you are in. See [Keys](docs/keybindings.md).
- Cmd + Shift + I opens the sidebar's Issues view: the key herdr sends it for that (F12) was not read.
- The AI's button beside a commit message of several lines has its star in the middle: the field opens to an odd
  number of rows, up to seven, a message of two lines with an empty third.

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
