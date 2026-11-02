# The Herdr app

herdr's desktop app takes mods: JavaScript that draws panels in its window. herdr-fold brings one, `herdr-fold`, the
TUI sidebar's counterpart in the app, with the same data layer underneath (`core/`), so a repository shows and commits
the same in both. It installs on its own, without the TUI environment.

Its first view is Changes. The other sidebar views (Files, Search, Issues) and the Conversations column are not in the
app yet.

## Changes

For the repository of the focused pane, top to bottom:

| Part | What it does |
|---|---|
| Header | the number of changed files, and the sync button with how far the branch is from its upstream (`↻ 1↓ 2↑`: one commit to pull, two to push); it pulls (fast-forward only) and pushes, and when that fails, a line under the diff says what to do, with nothing lost |
| Files | the changed files, staged ones first; a click shows a file's diff below, a new file's as all added; the first one's shows at once |
| ✦ | stages every change and has Claude or Codex write the message, as the TUI's ✦ and Cmd + Shift + C do: the same writer, rules and checks for anything private ([Commit and push](usage.md#commit-and-push)); within a minute or so the message fills the field, to read and change |
| Commit | stages every change and commits with the message (Enter in the field too); a file whose name looks like a secret's (`.env`, a key, a certificate) is asked about first: the button says Commit anyway, and pressing it again commits |

The list follows the files: on this Mac a change shows at once, on another machine within ten seconds.

## Installing it

It needs the Herdr app, and Python 3 and git on the machine the space is on (Claude Code or Codex too, for the ✦).

1. Copy the `app/mods/herdr-fold` folder into the app's mods folder:

   ```bash
   cp -R app/mods/herdr-fold ~/.config/herdr-app/mods/
   ```

2. In a terminal of the space, open it beside that terminal:

   ```bash
   herdr-app do pane.split --direction right --mod herdr-fold
   ```

The pane belongs to the tab and stays there; close it like any pane. To remove the mod, delete
`~/.config/herdr-app/mods/herdr-fold`.

## Keys

None are bound yet. The mod takes three commands, for `~/.config/herdr-app/keys.json`:

```json
{ "global": { "cmd-shift-c": "herdr-fold.write", "cmd-shift-y": "herdr-fold.sync" } }
```

`herdr-fold.write` writes the message, `herdr-fold.commit` commits, `herdr-fold.sync` syncs; they reach a shown
herdr-fold only.

## On another machine

A space on another machine (Settings → Machines in the app) works the same: the git commands and the message writer
run there, through the app's own connection. Nothing is installed or left on that machine; the mod carries its code
and runs it with that machine's `python3`.

## What it runs and reads

- git, on the space's machine, and herdr-fold's own code with `python3 -I`: isolated, so no module in the repository's
  folder (a `json.py`) is ever imported in its place.
- The list and the diff are asked for unasked, so they run nothing a repository's own config names: no fsmonitor,
  filter, external diff, text conversion or submodule look. Staging (the ✦ and Commit) runs its filters, and
  committing and syncing its hooks, as git in a terminal does.
- The message writer hands Claude or Codex what the TUI's does, and nothing else; its answer waits in a temporary
  folder of its own, removed once read (or ten minutes after it is written, should the pane be closed meanwhile).
- The mod itself sends nothing anywhere; the sync talks to the repository's remote, the AI tool to its own service.
