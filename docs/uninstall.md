# Uninstall

In the `herdr-fold` folder (installed from herdr's marketplace: `~/.local/share/herdr-fold`):

```bash
./uninstall.sh
```

`herdr plugin uninstall herdr-fold` alone takes only the plugin that opened the installer off; the rest stays. The
uninstaller takes that plugin off too, and the folder in `~/.local/share` last. A plugin of herdr-fold's you had
installed alone from herdr's marketplace, which the installer then took over, goes too: the uninstaller names the
command that brings it back.

It works from the installer's records in `~/.local/state/herdr-fold/`. With the TUI and the Herdr app installed, it
asks first `Take off`: `1` the TUI, `2` the Herdr app or `3` both (the default); with one, it asks
`Take herdr-fold off this Mac?`. `HERDR_FOLD_PARTS=tui`, `app` or `both` answers either question.

## One part, or both

One part goes and the other keeps working: what both use goes with the last.

- **The TUI**: its files, the `~/.zshrc` block, herdr-fold's part of herdr's settings, its herdr plugins and
  integrations, Ghostty's icon, and the sidebar's own state (the theme's colors, the column, the panels, the
  handovers, previews and issues it keeps). The remote machines stay in the Herdr app, and connected in herdr:
  `herdr machine remove <id>` disconnects one.
- **The Herdr app**: herdr-fold's mod, layout, themes, keys and settings in it, its chats' own files (what Claude waits
  on, the answers, the bar's numbers; the conversations stay), and the machines herdr-fold added there, as below. An
  update of the TUI does not offer it again; choosing it in the installer brings it back.
- **The last part**, or both: also the files both use (the status line and its `time.json`, the themes, the texts),
  Claude's earlier status line, the sidebar's settings (which keep the issue linked to each repository's next commit),
  the archived conversations, the records, what was made on first use (`~/.cache/herdr-fold`, the preview's helpers),
  herdr-fold's plugin from herdr's marketplace and the package folder.

## What goes, and what stays

- the installed files go, and your own earlier ones come back;
- a file you changed since the install is set aside in `~/.local/state/herdr-fold/changed-<date>/`, not deleted;
- the `~/.zshrc` block and the parts added to your own herdr settings come out; a copy of those settings from before
  the first install stays in `~/.local/state/herdr-fold/original/`;
- the plugins and herdr integrations it put there are removed, with the empty folders herdr keeps of them;
- in the Herdr app: herdr-fold's mod, its layout, its themes, its keys and its settings, what the app keeps for them
  (the layout's `layouts/.state/herdr-fold.json`, the mod's `data/herdr-fold/` and its folder in `~/Library/Application
  Support/gpui-shell/apps/`), and the machines herdr-fold added there. A running app shows its main layout first, the
  terminals herdr-fold started for its tabs end, and it closes for that moment and opens again, as it would write
  herdr-fold's settings back (your terminals keep running). Your own mods, layouts, themes, keys, settings, machines and
  terminals stay;
- Claude's earlier status line comes back (or herdr-fold's just goes);
- Ghostty's own app icon comes back: the icons the themes drew go.

It never touches your conversations (Claude and Codex sessions and their names), herdr's own data, or the programs: it
prints the `brew uninstall` line for those. Codex keeps the status line items it was given (`[tui] status_line` in
`~/.codex/config.toml`).

These stay too, because they are yours to keep: the SSH key and the `Host *` block in `~/.ssh/config`, the machines'
keys in `~/.ssh/known_hosts`, Homebrew's line in `~/.zprofile`, git's commit author and GitHub sign-in, and the
projects Claude trusts in `~/.claude.json`.

At the end it names what stays, each with where it is: AI Sessions' conversation names, the machine list, the
private word list, your files' earlier versions, the machines still connected in herdr, and of the things above, those
the installer itself made (it records them in `~/.local/state/herdr-fold/outside.txt`), with the command that takes
one off where there is one, such as `gh auth logout`.

## A remote machine

```bash
./machines.sh remove alpha
```

This takes the machine off the list and the package off the machine (its files, the shell block, the plugins), and
puts Claude's earlier status line and the machine's own files that the package replaced back. The conversations and
their names in AI Sessions stay there, and it says where the names are. Files changed there since stay in its
backups (`~/.local/state/herdr-fold/prepared-*`).
