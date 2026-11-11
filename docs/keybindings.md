# Keys

Ghostty turns the Cmd keys below into herdr commands. herdr's own keys start with Ctrl + B; Ctrl + B, then ? lists them
all.

## Workspaces and sessions

| Key | What it does |
|---|---|
| Cmd + 1…9 | jump to workspace 1…9 |
| Cmd + ↓ / Cmd + ↑ | next / previous workspace, wrapping around |
| Cmd + → / Cmd + ← | next / previous pane of the tab (the agent, the sidebar, the terminal), wrapping around; in typing, Ctrl + A / Ctrl + E (or Fn + ← / Fn + →) go to the start or end of the line |
| Ctrl + B, then w | make the Spaces list active: W / S or ↑ / ↓ move the highlight, Enter switches, Esc cancels, 1–9 jumps |
| Ctrl + B, then Shift + N | new workspace, with the folder picker (the same as the **new** button under Spaces) |
| Cmd + D / Cmd + E | next / previous session of the current workspace, even while typing; wraps around |
| Cmd + Shift + U | mark the focused agent unread: its workspace says `waiting` again, from now, until you come back to it after leaving it; again on a marked one takes the mark off |
| Cmd + B | show / hide herdr's sidebar (Spaces and Sessions) |
| Ctrl + B, then Shift + M | add a remote machine |

## Panes and tabs

| Key | What it does |
|---|---|
| Cmd + Shift + E | show / hide the right column (sidebar and terminal); a sidebar or terminal closed by hand comes back |
| Cmd + Shift + O | restore panels: every pane closed by hand in the tab comes back (sidebar, terminal), the right column shown |
| Cmd + Shift + G | the sidebar's Changes view |
| Cmd + Shift + I | the sidebar's Issues view, for a repository on GitHub |
| Cmd + A | in the sidebar's field you are in (the commit message, a search): select its whole text, for Backspace, typing or a paste; in other panes it does nothing |
| Cmd + Shift + C | commit and push, with a message written by Claude or Codex: Enter commits and pushes, `e` edits, `r` writes a new one, Esc cancels |
| Cmd + Shift + L | open a file the focused pane's output names (`src/app.py:42`, a traceback's line), at that line, in the sidebar's preview tab: the newest first, type to narrow the list |
| Cmd + T / Cmd + R | next / previous tab of the workspace, wrapping around; keep Cmd held and tap again to step on |
| Ctrl + B, then 1…9 | tab 1…9 of the workspace |
| Cmd + W | close the active tab, never the main tab (a workspace's first); a tab with a conversation asks first |

## Conversations

| Key | What it does |
|---|---|
| Cmd + Shift + R | find a conversation: the sidebar shows Chats in this tab (on its rail too, beside it; a sidebar closed by hand comes back, a tab without one goes to the workspace's first), its filter empty and the keys going to it; Enter goes to a running one or reopens a closed one in a new tab |
| Space / Shift + ↑ ↓ | in the sidebar's Conversations, with nothing typed: mark closed conversations, to archive them together with a right click on one of them; Esc unmarks them |
| Cmd + F | search the Claude conversation: Enter accepts, `n` / `N` next / previous match, Esc goes back to typing |

## Copy and links

| Key | What it does |
|---|---|
| mouse | select text; in a Claude pane it is copied when you release |
| Cmd + C | copy the selection (in other panes); text selected from a Claude or Codex reply is copied formatted too |
| Ctrl + click | open a link in your browser, also one that shows only its title |

Cmd + click does not open links: herdr handles the mouse and does not see Cmd.

## Ghostty

| Key | What it does |
|---|---|
| Cmd + K, then Cmd + T | pick a color theme |
| Cmd + Shift + , | reload Ghostty's settings |
| Ctrl + Option + 0 | type a zero, on the keyboard layouts that put it there |

Cmd + K starts a key sequence, so Ghostty's own clear screen is not available.

## Without Ghostty

In another terminal, the same commands are on herdr's keys:

| Cmd key | herdr key |
|---|---|
| Cmd + 1…9 | Option + 1…9 |
| Cmd + ↓ / Cmd + ↑ | Ctrl + B, then ↓ / Ctrl + B, then ↑ |
| Cmd + → / Cmd + ← | Ctrl + B, then Tab / Ctrl + B, then Shift + Tab |
| Cmd + T / Cmd + R | Ctrl + B, then n / Ctrl + B, then p |
| Cmd + D / Cmd + E | Ctrl + B, then Shift + ↓ / Ctrl + B, then Shift + ↑ |
| Cmd + B | Ctrl + B, then b |
| Cmd + Shift + E | Ctrl + B, then f |
| Cmd + Shift + O | Ctrl + B, then Shift + O |
| Cmd + Shift + G | Ctrl + B, then u |
| Cmd + Shift + I | Ctrl + B, then Shift + I |
| Cmd + A | Ctrl + B, then Shift + A |
| Cmd + W | Ctrl + B, then t |
| Cmd + Shift + C | Ctrl + B, then y |
| Cmd + Shift + L | Ctrl + B, then Shift + L |
| Cmd + F | Ctrl + B, then a |
| Cmd + Shift + R | Ctrl + B, then m |
| Cmd + Shift + U | Ctrl + B, then Shift + U |
| Cmd + K, then Cmd + T | Ctrl + B, then i |

## Remapping keys

When you run the installer again, it puts its own `~/.config/ghostty/config` and `~/.config/herdr/config.toml` back
(the herdr file only if it is not your own with herdr-fold's added) and keeps yours in
`~/.local/state/herdr-fold/changed-<date>/`. To keep a change, carry it into the package first: `./tools/sync.sh` in
the `herdr-fold` folder copies this Mac's settings back.

- **A Cmd key:** in `~/.config/ghostty/config`, change the left side of its `keybind = <keys>=text:…` line (for example
  `super+d` → `super+alt+s`), keep the right side, then press Cmd + Shift + ,. Use a Cmd combination: Ghostty sends
  Ctrl combinations such as Ctrl + Tab on release, or macOS takes them.
- **The W / S keys of the Spaces list:** `navigate_workspace_up` and `navigate_workspace_down` in the `[keys]` section
  of `~/.config/herdr/config.toml` (each can hold several keys), then Ctrl + B, then Shift + R.

Check that a key is free first:

```bash
/Applications/Ghostty.app/Contents/MacOS/ghostty +list-keybinds | grep -i 'super+alt+s'
```

herdr's keys: Ctrl + B, then ?. Claude Code's: `~/.claude/keybindings.json`.
