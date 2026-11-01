# AI Sessions list (herdr-fold)

A herdr plugin that turns herdr's Agents panel into a Sessions list: only the current workspace's Claude and Codex
agents that have a conversation, each under its name.

![herdr-fold's window: at the bottom left, in herdr's sidebar under the workspaces, the Sessions list with the
workspace's one conversation, its name and its state](../../../docs/media/hero.webp)

- A session shows once its conversation holds a message, the agent is working, or the conversation has a title.
- Its name is the pane name. Rename it from herdr's right-click menu (**Rename pane**), or with **Rename** in
  herdr-fold's Conversations column; until then it follows the conversation's title. **Clear pane name** brings the
  title back.
- A conversation that has its tab to itself names the tab too, cut to 24 characters; a workspace's main tab keeps the
  workspace's name. A new title goes on the tab only while the tab shows the conversation's name or herdr's number for
  it, so a tab you renamed yourself keeps your name until you rename the conversation.
- The list updates when an agent appears or changes state, and when a pane or tab gets the focus. Its action
  **Reapply sessions view** sets it again by hand.

## What it reads and writes

- herdr, through its socket (`~/.config/herdr/herdr.sock`, or `HERDR_SOCKET_PATH`): it reads the agents, panes and
  tabs, and gives the panes and the conversations' own tabs their names.
- Claude's transcripts (`~/.claude/projects/*/<session>.jsonl`) and Codex's sessions (`~/.codex/sessions/`,
  `~/.codex/session_index.jsonl`): read only, to see whether a session has a conversation and what its title is.
- `names.json` in its herdr state folder (`~/.local/state/herdr/plugins/herdr-fold.sessions-view/`, or
  `HERDR_PLUGIN_STATE_DIR`): the names, and whether you or the conversation gave them; herdr-fold's Conversations column
  writes a name given there too. A damaged file is set aside as `names.json.damaged-<date>`, never deleted.

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
