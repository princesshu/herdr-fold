# The Herdr app

herdr's desktop app takes mods: JavaScript that draws panels in its window. herdr-fold brings one, `herdr-fold`, the
TUI sidebar's counterpart in the app, with the same data layer underneath (`core/`), so a repository shows and commits
the same in both. It installs on its own, without the TUI environment.

It comes with a layout of its own, `herdr-fold`: the app's main layout, with herdr-fold in the right panel where the
app's own Changes was. The Changes button at the top right opens it there, and so does Cmd + Shift + G.

Its views are Changes and Search, the tabs at its top; it keeps the one shown. The other sidebar views (Files, Issues)
and the Conversations column are not in the app yet.

## Changes

For the repository of the focused pane, top to bottom:

| Part | What it does |
|---|---|
| Header | the number of changed files, and the sync button with how far the branch is from its upstream (`↻ 1↓ 2↑`: one commit to pull, two to push); it pulls (fast-forward only) and pushes, and when that fails, a line under the diff says what to do, with nothing lost |
| Staged Changes, Changes | the changed files in two sections, as the TUI sidebar lists them; a row's + stages the file, − unstages it, ↶ undoes its change once Discard is pressed too, a new file sent to the system's Trash, never deleted (not a conflict's: that is settled in the file); a click shows a file's diff below, a new file's as all added; the first one's shows at once; the mouse resting on one shows its whole path in the repository |
| Graph | the last 20 commits, the one checked out marked, each with its branches and tags; a click shows the commit's message and diff above, its author by name; its heading folds it and opens it again, and it stays so |
| ✦ | with nothing staged, stages every change (never a file .gitignore names), and has Claude or Codex write the message for what the commit takes, as the TUI's ✦ and Cmd + Shift + C do: the same writer, rules and checks for anything private ([Commit and push](usage.md#commit-and-push)); within a minute or so the message fills the field, to read and change |
| Commit | commits the staged changes, or every change with none staged, with the message (Enter in the field too); a file whose name looks like a secret's (`.env`, a key, a certificate) is asked about first: the button says Commit anyway, and pressing it again commits. Its arrow chooses Commit, Commit & Push or Commit & Sync, as the TUI's: after the commit, a push or a sync; the choice stays for the next commit |

The list follows the files: on this Mac a change shows at once, on another machine within ten seconds.

## Search

The focused pane's folder, searched as the TUI sidebar's Search does it, on the space's machine: ripgrep where it is,
else git grep in a repository, else herdr-fold's own search; a file .gitignore names is never a hit nor read.

| Part | What it does |
|---|---|
| Field | the text to find: the search runs once typing stops, Enter at once; Aa matches case, ab whole words, .* takes it as a regular expression |
| The line under it | the folder searched, then how many hits in how many files (the first 1000 shown), or what went wrong |
| Hits | by file, each with its line number, the match marked; a click shows the file below, from a few lines above the hit, its line marked |

## Installing it

It needs the Herdr app, and Python 3 and git on the machine the space is on (Claude Code or Codex too, for the ✦).

With the TUI environment, `./install.sh` does it all: where the Herdr app is on the Mac, it asks
`Set up herdr-fold in the Herdr app too?`, and a yes puts the mod, the layout and the keys in place, and shows the
layout in a running app. `./uninstall.sh` takes them off again.

Without the TUI environment, from the `app` folder of herdr-fold:

1. Copy the mod and the layout into the app's home:

   ```bash
   cp -R mods/herdr-fold ~/.config/herdr-app/mods/
   cp layouts/herdr-fold.json ~/.config/herdr-app/layouts/
   ```

2. Add the `layout:herdr-fold` section of `keys.json` to `~/.config/herdr-app/keys.json`.
3. Show the layout:

   ```bash
   herdr-app do layout.switch --name herdr-fold
   ```

Your own layout stays as it was: Cmd + Shift + L switches between the layouts. To remove it all, delete the two copied
items and the keys section.

Without the layout, herdr-fold also opens beside a terminal, as a pane of that tab:
`herdr-app do pane.split --direction right --mod herdr-fold`.

## Keys

In the herdr-fold layout:

| Key | What it does |
|---|---|
| Cmd + Shift + G | shows the right panel at herdr-fold, as the Changes button does; again hides it |
| Cmd + Shift + C | has Claude or Codex write the message, as the ✦ does; Enter commits |

The mod takes commands for keys of your own: `herdr-fold.write`, `herdr-fold.commit` and `herdr-fold.sync`, and
`herdr-fold.changes` and `herdr-fold.search`, which show that view (Search with the keys in its field); they reach a
herdr-fold that shows.

## On another machine

A space on another machine works the same: the git commands and the message writer run there, through the app's own
connection. With the TUI environment, `install.sh` (and `./machines.sh add` later) adds each of herdr-fold's machines
to the app, prepared as for the TUI; without it, add one in Settings → Machines. The mod installs nothing there: it
carries its code and runs it with that machine's Python: `python3`, or on Windows the one herdr-fold's preparation
finds there (not the Store's alias). The message writer runs as a job of its own, so the app's connection ending does
not take it.

## What it runs and reads

- git, on the space's machine, and herdr-fold's own code with Python's `-I`: isolated, so no module in the repository's
  folder (a `json.py`) is ever imported in its place. Search runs ripgrep or git grep there, with no input, no terminal
  and a time limit; a hit's file is read with the app's own file reader, on that machine.
- The list and the diff are asked for unasked, so they run nothing a repository's own config names: no fsmonitor,
  filter, external diff, text conversion or submodule look. Staging (the ✦ and Commit) runs its filters, and
  committing and syncing its hooks, as git in a terminal does.
- The message writer hands Claude or Codex what the TUI's does, and nothing else; its answer waits in a temporary
  folder of its own, removed once read (or ten minutes after it is written, should the pane be closed meanwhile).
- The mod itself sends nothing anywhere; the sync talks to the repository's remote, the AI tool to its own service.
