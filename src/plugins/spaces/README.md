# Spaces

A herdr plugin of herdr-fold that keeps herdr's spaces, the rows of the Spaces list (herdr's commands call them
workspaces). It draws no list of its own: herdr draws Spaces, and this plugin looks after what is in it:

- A new space from herdr's **new** button (or Ctrl + B, then Shift + N) opens the folder picker instead of reusing
  the active space's folder. A space of a git worktree keeps its own folder. The sidebar's New Space on a folder
  opens the same picker there.
- It shows the confirmation window when you close a tab that holds a chat.
- A space named after its folder takes the folder's new name, and so does its main tab, when the folder is renamed
  or moved (seen at the next pane you focus). A folder renamed before is known by the Claude chats kept under
  its old name. A name you gave the space yourself stays.
- A space herdr named after the home folder or a root, by its path (`~`, `/`, `C:\`), takes herdr-fold's name:
  `home`, `root`, or the drive, `C:`, and so does its main tab (seen at the next pane you focus, and when herdr
  starts). A name you gave the space yourself stays.
- A space whose folder is not a git repository but holds one shows that repository in the Spaces list, where
  herdr shows a repository's own branch: its name under the space's (left out where it is the same), and its branch
  under that with how far it is from its upstream on any git host, as herdr does: `main ↑2 ↓1` for two commits to
  push and one to pull. A branch always stands under the name it belongs to. It is the repository the space's active
  pane is in, else the one a pane of it was last in, else the only one up to two folders down (your home folder
  itself is never searched). A space whose folder is in a repository shows herdr's own branch alone. These are its
  `repo` and `repo_branch` tokens, which herdr-fold's theme shows after herdr's branch and git status and on the
  row under it (`$repo`, `$repo_branch`).
- A space whose folder is gone says deleted beside its branch: its `folder` token, which herdr-fold's theme shows
  in the Spaces list (`$folder`).
- A space herdr ended with its last tab stays a row in Spaces: it is made again at once in its place, with its
  name as its main tab's, its folder and a shell, and in front again when it was. herdr says so with two events, the
  space's close and the tab's; closed on purpose (the row's menu, herdr's close-workspace key,
  `herdr workspace close`) it sends the first alone, and that space stays closed. So does one whose folder is
  gone, and one whose last pane was moved to another space.
- The home folder's space is always there: herdr ends a space with its last tab, so when none is left at home
  (none named `home` or `~`, none whose first pane is in the home folder), one named `home` is made again, behind the
  one in front, with a shell; seen when a space closes and at the next pane you focus.
- That space is the first row in Spaces: made again, or below another one after a space is made or moved, it
  goes back to the top, the one in front staying in front (at herdr's start, at the next pane you focus). The one
  named `home` or `~` is taken, else the first one in the home folder.
- When herdr starts, the agents herdr-fold started start again in their empty shell (herdr resumes only those with a
  chat), never in the `home` space; the spaces herdr names `~`, `/` or `C:\` are named `home`, `root` or `C:`.

It works on macOS and Linux. On Windows it only starts the agents again and names the spaces herdr named after the
home folder or a root, when herdr starts: the folder picker's key handling is Unix-only, and Windows does not let a
folder in use be renamed. Without it, herdr's own **new** button works as herdr's, and every new tab still gets the
sidebar and a terminal: the sidebar lays them out itself.

## What it reads and writes

- herdr, through its command line (`herdr`): the spaces, tabs and panes it names, the agents it starts again, and
  the folder picker and the confirmation window it opens. Through its socket (`HERDR_SOCKET_PATH`, else
  `~/.config/herdr/herdr.sock`) one request, `workspace.move`, which the command line has not: the home folder's
  space to the top, a space made again to its place. A herdr that does not know it leaves the order as it is.
- git (`git rev-parse`), to tell a git worktree's folder. For a repository inside a space's folder: when its
  HEAD, config and refs last changed, and after a change `git rev-parse` for its name, `git symbolic-ref` and
  `git rev-list` for its branch and how far it is from its upstream.
- Claude's chat folders (`~/.claude/projects/`): only whether one exists for a space's old folder;
  nothing in them is read.
- herdr-fold's scripts in `~/.config/herdr-fold/` (`herdrlib.py`, `new_workspace.py`, `close_tab.py`,
  `restore_panes.py`).
- Its own state folder (`~/.local/state/herdr/plugins/herdr-fold.spaces/`): `spaces.json`, each space named
  after its folder, with that folder, so a renamed folder is recognized; `focus.json`, the space in front and the
  one before it, so Esc in the folder picker goes back there, and the repository each space's pane was last in
  with each one's name and branch as last read, so git runs again only after a change; `closed.json`, each space's
  folder (herdr's close names none) and, for a minute, what herdr said of one that just closed. herdr-fold's
  uninstaller removes them.

It sends nothing anywhere.

## Install

It is part of herdr-fold and needs herdr-fold's scripts: herdr-fold's installer links it from
`~/.config/herdr-fold/plugins/spaces`.

## Requirements

- herdr 0.9.5 or newer;
- Python 3.9 or newer, standard library only: `/usr/bin/python3` on macOS and Linux, `python` on Windows.

## Author and license

Created by [princesshu](https://github.com/princesshu) as part of
[herdr-fold](https://github.com/princesshu/herdr-fold); herdr itself is the work of
[herdrdev](https://github.com/herdrdev/herdr). MIT, see [LICENSE](LICENSE). If you use or adapt it, please credit it
with a link to herdr-fold.
