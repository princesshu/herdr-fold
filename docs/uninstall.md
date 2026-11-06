# Uninstall

In the `herdr-fold` folder (installed from herdr's marketplace: `~/.local/share/herdr-fold`):

```bash
./uninstall.sh
```

`herdr plugin uninstall herdr-fold` alone takes only the plugin that opened the installer off; the rest stays. The
uninstaller takes that plugin off too, and the folder in `~/.local/share` last. A plugin of herdr-fold's you had
installed alone from herdr's marketplace, which the installer then took over, goes too: the uninstaller names the
command that brings it back.

It asks `Take herdr-fold off this Mac?`, then works from the installer's records in `~/.local/state/herdr-fold/`:

- the installed files go, and your own earlier ones come back;
- a file you changed since the install is set aside in `~/.local/state/herdr-fold/changed-<date>/`, not deleted;
- the `~/.zshrc` block and the parts added to your own herdr settings come out; a copy of those settings from before
  the first install stays in `~/.local/state/herdr-fold/original/`;
- the plugins and herdr integrations it put there are removed, with the empty folders herdr keeps of them;
- in the Herdr app: herdr-fold's mod, its layout, its themes, its keys and its settings, and the machines
  herdr-fold added there. A running app shows its main layout first, the terminals herdr-fold started for its tabs
  end, and it closes for that moment and opens again, as it would write herdr-fold's settings back (your terminals
  keep running). Your own mods, layouts, themes, keys, settings, machines and terminals stay;
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
