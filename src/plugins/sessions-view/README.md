# AI Sessions

A herdr plugin that narrows herdr's Agents panel to AI sessions: only the current space's Claude and Codex
agents that have a chat, each under its name.

![herdr-fold's window: at the bottom left, in herdr's sidebar under the spaces, AI Sessions with the
space's one chat, its name and its state, done](../../../assets/screenshots/tui-hero.webp)

- A session shows once its chat holds a message, the agent is working, or the chat has a title.
- Its name is the pane name. Rename it from herdr's right-click menu (**Rename pane**), or with **Rename** in
  herdr-fold's sidebar, in its Chats; until then it follows the chat's title. **Clear pane name** brings
  the title back.
- A chat that has its tab to itself names the tab too, cut to 24 characters; a space's main tab keeps the
  space's name. A new title goes on the tab only while the tab shows the chat's name or herdr's number for
  it, so a tab you renamed yourself keeps your name until you rename the chat.
- The list updates when an agent appears or changes state, and when a pane or tab gets the focus. Its action
  **AI Sessions: reapply** sets it again by hand.
- A space where an agent waits on you, blocked or done and not seen yet, gets its `waiting` token: `waiting 12m`,
  the longest wait there. herdr-fold's theme shows it in the Spaces list beside the name (`$waiting`); in your own
  settings, put `"$waiting"` in a row of `[ui.sidebar.spaces]`. While an agent waits, one run of the plugin stays to
  count the minutes, looking again every 20 seconds, and ends once none waits.
- Its action **AI Sessions: mark unread** (herdr-fold's Cmd + Shift + U) marks the focused agent unread: it waits on
  you again, from then, until you come back to its pane after leaving it; again on a marked one takes the mark off.

## What it reads and writes

- herdr, through its socket (`~/.config/herdr/herdr.sock`, or `HERDR_SOCKET_PATH`): it reads the agents, panes and
  tabs, gives the panes and the chats' own tabs their names, and the spaces their `waiting` token.
- Claude's transcripts (`~/.claude/projects/*/<session>.jsonl`) and Codex's sessions (`~/.codex/sessions/`,
  `~/.codex/session_index.jsonl`): read only, to see whether a session has a chat and what its title is.
- `names.json` in its herdr state folder (`~/.local/state/herdr/plugins/herdr-fold.sessions-view/`, or
  `HERDR_PLUGIN_STATE_DIR`): the names, and whether you or the chat gave them; herdr-fold's Chats
  writes a name given there too. A damaged file is set aside as `names.json.damaged-<date>`, never deleted.
- `waits.json` in the same folder: each waiting agent's pane and since when it waits. Beside them, the lock files
  that keep its runs from writing at once (`names.json.lock`, `waits.json.lock`, `clock.lock`).

It sends nothing anywhere.

## Install

herdr-fold's installer links it. On its own, from herdr's marketplace:

```bash
herdr plugin install princesshu/herdr-fold/src/plugins/sessions-view
```

or from a copy of the folder: `herdr plugin link /path/to/herdr-fold/src/plugins/sessions-view`.

## Requirements

- herdr 0.9.5 or newer;
- Python 3.9 or newer, standard library only: `/usr/bin/python3` on macOS and Linux, `python` on Windows.

## Author and license

Created by [princesshu](https://github.com/princesshu) as part of
[herdr-fold](https://github.com/princesshu/herdr-fold); herdr itself is the work of
[herdrdev](https://github.com/herdrdev/herdr). MIT, see [LICENSE](LICENSE). If you use or adapt it, please credit it
with a link to herdr-fold.
