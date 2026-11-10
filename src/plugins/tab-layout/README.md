# Tab Layout

A herdr plugin of herdr-fold that keeps the workspace layout:

- A new workspace from herdr's **new** button (or Ctrl + B, then Shift + N) opens the folder picker instead of reusing
  the active workspace's folder. A workspace of a git worktree keeps its own folder.
- Every other new tab gets the right column: the sidebar on top of a terminal, with the tab's own shell on the left.
  It acts only on an empty new tab: one with a single unnamed pane still running a shell after 1.5 seconds.
- When herdr starts, it restarts the sidebars and the still-empty agent panes, and closes an older install's
  Conversations columns (their list is in the sidebar now).
- It shows the confirmation window when you close a tab that holds a conversation.
- A workspace named after its folder takes the folder's new name, and so does its main tab, when the folder is renamed
  or moved (seen at the next pane you focus). A folder renamed before is known by the Claude conversations kept under
  its old name. A name you gave the workspace yourself stays.
- A workspace whose folder is gone says deleted beside its branch: its `folder` token, which herdr-fold's theme shows
  in the Spaces list (`$folder`).

## What it reads and writes

- herdr, through its command line (`herdr`): the workspaces, tabs and panes it lays out and names.
- git (`git rev-parse`), to tell a git worktree's folder.
- Claude's conversation folders (`~/.claude/projects/`): only whether one exists for a workspace's old folder;
  nothing in them is read.
- herdr-fold's scripts in `~/.config/herdr-fold/` (`herdrlib.py`, `new_workspace.py`, `restore_panes.py`,
  `close_tab.py`, `plugins/sidebar/panes.py`).
- The sidebar plugin's state folder (`~/.local/state/herdr/plugins/herdr-fold.sidebar/`): the remembered column width
  (`column.json`) for a new tab's right column, and `panels.json`, where the tab is noted as having it.
- Its own state folder (`~/.local/state/herdr/plugins/herdr-fold.tab-layout/`): `spaces.json`, each workspace named
  after its folder, with that folder, so a renamed folder is recognized; `focus.json`, the workspace in front and the
  one before it, so Esc in the folder picker goes back there. The uninstaller removes both.

It sends nothing anywhere.

## Install

It is part of herdr-fold and needs herdr-fold's scripts: herdr-fold's installer links it from
`~/.config/herdr-fold/plugins/tab-layout`.

## Requirements

- herdr 0.9.5 or newer;
- Python 3.9 or newer, standard library only: `/usr/bin/python3` on macOS and Linux, `python` on Windows.

## Author and license

Created by [princesshu](https://github.com/princesshu) as part of
[herdr-fold](https://github.com/princesshu/herdr-fold); herdr itself is the work of
[herdrdev](https://github.com/herdrdev/herdr). MIT, see [LICENSE](LICENSE). If you use or adapt it, please credit it
with a link to herdr-fold.
