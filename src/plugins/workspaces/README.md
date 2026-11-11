# Workspaces

A herdr plugin of herdr-fold that keeps the workspaces:

- A new workspace from herdr's **new** button (or Ctrl + B, then Shift + N) opens the folder picker instead of reusing
  the active workspace's folder. A workspace of a git worktree keeps its own folder. The sidebar's New Workspace on a
  folder opens the same picker there.
- It shows the confirmation window when you close a tab that holds a conversation.
- A workspace named after its folder takes the folder's new name, and so does its main tab, when the folder is renamed
  or moved (seen at the next pane you focus). A folder renamed before is known by the Claude conversations kept under
  its old name. A name you gave the workspace yourself stays.
- A workspace whose folder is not a git repository but holds one shows that repository's branch in the Spaces list,
  where herdr shows a repository's own, and how far it is from its upstream on any git host, as herdr does:
  `main ↑2 ↓1` for two commits to push and one to pull. It is the repository the workspace's active pane is in, else
  the one a pane of it was last in, else the only one up to two folders down (your home folder itself is never
  searched). A workspace whose folder is in a repository shows herdr's own branch alone. This is its `repo` token,
  which herdr-fold's theme shows after herdr's branch and git status (`$repo`).
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
- git (`git rev-parse`), to tell a git worktree's folder. For a repository inside a workspace's folder: when its
  HEAD, config and refs last changed, and after a change `git symbolic-ref` and `git rev-list` for its branch and how
  far it is from its upstream.
- Claude's conversation folders (`~/.claude/projects/`): only whether one exists for a workspace's old folder;
  nothing in them is read.
- herdr-fold's scripts in `~/.config/herdr-fold/` (`herdrlib.py`, `new_workspace.py`, `close_tab.py`,
  `restore_panes.py`).
- Its own state folder (`~/.local/state/herdr/plugins/herdr-fold.workspaces/`): `spaces.json`, each workspace named
  after its folder, with that folder, so a renamed folder is recognized; `focus.json`, the workspace in front and the
  one before it, so Esc in the folder picker goes back there, and the repository each workspace's pane was last in
  with each one's branch as last read, so git runs again only after a change. herdr-fold's uninstaller removes both;
  its installer moves an earlier install's Tab Layout ones here.

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
