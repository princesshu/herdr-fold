# Tab layout (herdr-fold)

A herdr plugin of herdr-fold that keeps the workspace layout:

- A new workspace from herdr's **new** button (or Ctrl + B, then Shift + N) opens the folder picker instead of reusing
  the active workspace's folder. A workspace of a git worktree keeps its own folder.
- Every other new tab gets the columns: the Conversations column, then the sidebar on top of a terminal, with the tab's
  own shell on the left. It acts only on an empty new tab: one with a single unnamed pane still running a shell after
  1.5 seconds.
- When herdr starts, it restarts the Conversations columns, the sidebars and the still-empty agent panes.
- It shows the confirmation window when you close a tab that holds a conversation.

## What it reads and writes

- herdr, through its command line (`herdr`): the tabs and panes it lays out.
- git (`git rev-parse`), to tell a git worktree's folder.
- herdr-fold's scripts in `~/.config/herdr-fold/` (`herdrlib.py`, `new_workspace.py`, `restore_panes.py`,
  `close_tab.py`, `plugins/sidebar/conversations_pane.py`).
- The sidebar plugin's state folder (`~/.local/state/herdr/plugins/herdr-fold.sidebar/`): the remembered column widths
  (`column.json`, `conversations.json`) for a new tab's columns, and `panels.json`, where the tab is noted as having
  them.

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
