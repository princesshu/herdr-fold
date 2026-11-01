# Troubleshooting

| Symptom | Fix |
|---|---|
| macOS will not open `install.command` or Ghostty | System Settings → Privacy & Security → **Open Anyway**. On macOS 15 and later, right-click → Open no longer helps. |
| `herdr plugin install princesshu/herdr-fold`: `… is already linked from a local path` | herdr-fold is installed here from its folder (`git clone` or a zip), and herdr keeps one copy of a plugin: update it from that folder (`git pull`, `./install.sh`), or to move to herdr's marketplace, run `./uninstall.sh` first |
| The installer stops at once: this herdr-fold folder is in the Trash | the terminal was left in a folder that went to the Trash, so its old copy ran: `cd` into the folder you unpacked and run `./install.sh` there |
| The installer sums a step up in one line, and you want every item | `HERDR_FOLD_VERBOSE=1 ./install.sh` (warnings and errors always get a line of their own) |
| `nested herdr is disabled` | start Ghostty from the Dock or Applications, not from a herdr pane |
| The Dock or the app switcher shows an earlier theme's sheep | Ghostty takes the theme's icon when it loads its settings: in Ghostty, Cmd + Shift + , |
| App Exposé, Finder and Launchpad show Ghostty's own icon | macOS 27 does not let Ghostty put its icon into the app itself, so only the Dock and the app switcher show the theme's sheep. Turning Ghostty on under Privacy & Security → App Management does not change that: Ghostty then shows as a blank folder, even after it is turned off again, until `xattr -d com.apple.FinderInfo /Applications/Ghostty.app` |
| After the installer, herdr still runs the old version | `herdr server live-handoff` switches the running herdr to the new one without stopping your agents (`herdr status` shows both versions) |
| A machine will not connect | the installer says why: no such name (check it, and that Tailscale is on), no SSH server on it (it says how to turn one on), no answer (off, asleep or on another network), a key it does not take, or a host key that changed. For "key-based login failed", try `ssh dev@alpha.example` by hand; for a key with a passphrase, run `ssh-add --apple-use-keychain` first |
| **Attention** next to a machine in herdr | run the command herdr shows (for example `herdr --remote dev@alpha.example`) in Terminal, then reopen Ghostty |
| The sidebar and the terminal are gone | Cmd + Shift + E: hidden, it shows them; closed, it brings them back. An empty shell where the sidebar should be: `python3 ~/.config/herdr-fold/restore_panes.py` |
| Only the terminal is in the right column | Cmd + Shift + E puts the sidebar back above it (so does Show sidebar in the Conversations column's menu); the terminal keeps what runs in it |
| Claude's status line is empty | Claude has not been told to trust the folder yet: in the pane, `/exit`, then `claude --continue`, and answer yes |
| An update put herdr-fold's status line back over your own | turn it off for good: `python3 ~/.config/herdr-fold/statusline_setup.py`, Space on Claude Code or Codex (your earlier one comes back) |
| Claude does not start in the agent pane | start it by hand: `claude` (in a new folder, the trust question comes first) |
| Claude is not full screen, or Cmd + F does not search | the tab's shell started before the install: open a new tab, or `exec zsh`, then `claude --continue` |
| Text selected from a reply pastes as plain text | reopen Ghostty (Cmd + Q, then open it): herdr gets its own `pbcopy` only that way. From a remote machine, plain text is expected |
| The terminal colors did not change with the theme | Cmd + Shift + , in Ghostty; the prompt changes in new panes |
| Cmd + D / Cmd + E do not switch sessions | they step through the current workspace's sessions only. Otherwise herdr or Ghostty runs the old settings: Ctrl + B, then Shift + R in herdr; Cmd + Shift + , in Ghostty |
| Push or Sync does not work | the repo has no remote: see [A repo without a remote](usage.md#commit-and-push) |
| Something in the sidebar | see [The sidebar](sidebar.md) |
