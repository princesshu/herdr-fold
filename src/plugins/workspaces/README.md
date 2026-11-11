# Workspaces

A herdr plugin of herdr-fold that keeps the workspaces:

- A new workspace from herdr's **new** button (or Ctrl + B, then Shift + N) opens the folder picker instead of reusing
  the active workspace's folder. A workspace of a git worktree keeps its own folder. The sidebar's New Workspace on a
  folder opens the same picker there.
- It shows the confirmation window when you close a tab that holds a conversation.
- A workspace named after its folder takes the folder's new name, and so does its main tab, when the folder is renamed
  or moved (seen at the next pane you focus). A folder renamed before is known by the Claude conversations kept under
  its old name. A name you gave the workspace yourself stays.
- A workspace whose folder is gone says deleted beside its branch: its `folder` token, which herdr-fold's theme shows
  in the Spaces list (`$folder`).
- When herdr starts, the agents herdr-fold started start again in their empty shell (herdr resumes only those with a
  conversation), never in the `home` workspace; the workspace herdr names `~` is named `home`.

It works on macOS and Linux. On Windows it only starts the agents again: the folder picker's key handling is
Unix-only, and Windows does not let a folder in use be renamed. Without it, herdr's own **new** button works as
herdr's, and every new tab still gets the sidebar and a terminal: the sidebar lays them out itself.

## What it reads and writes

- herdr, through its command line (`herdr`): the workspaces, tabs and panes it names, the agents it starts again, and
  the folder picker and the confirmation window it opens.
- git (`git rev-parse`), to tell a git worktree's folder.
- Claude's conversation folders (`~/.claude/projects/`): only whether one exists for a workspace's old folder;
  nothing in them is read.
- herdr-fold's scripts in `~/.config/herdr-fold/` (`herdrlib.py`, `new_workspace.py`, `close_tab.py`,
  `restore_panes.py`).
- Its own state folder (`~/.local/state/herdr/plugins/herdr-fold.workspaces/`): `spaces.json`, each workspace named
  after its folder, with that folder, so a renamed folder is recognized; `focus.json`, the workspace in front and the
  one before it, so Esc in the folder picker goes back there. herdr-fold's uninstaller removes both; its installer
  moves an earlier install's Tab Layout ones here.

It sends nothing anywhere.

## Install

It is part of herdr-fold and needs herdr-fold's scripts: herdr-fold's installer links it from
`~/.config/herdr-fold/plugins/workspaces`.

## Requirements

- herdr 0.9.5 or newer;
- Python 3.9 or newer, standard library only: `/usr/bin/python3` on macOS and Linux, `python` on Windows.

## Author and license

Created by [princesshu](https://github.com/princesshu) as part of
[herdr-fold](https://github.com/princesshu/herdr-fold); herdr itself is the work of
[herdrdev](https://github.com/herdrdev/herdr). MIT, see [LICENSE](LICENSE). If you use or adapt it, please credit it
with a link to herdr-fold.
