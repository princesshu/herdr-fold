# Themes

Twelve themes set the colors of herdr-fold's parts together, the TUI's Ghostty, herdr, prompt and sidebar and
herdr-fold's layout in the Herdr app: Catppuccin Mocha, VS Code (Dark Modern), Vesper, GitHub Dark, Tokyo Night,
Kanagawa, Rosé Pine, One Dark, Dracula, Gruvbox, Nord and Solarized. With both parts installed, one theme sets both.

## Picking a theme

In the TUI, Cmd + K, then Cmd + T opens the picker: the themes with color swatches, Enter applies, `p` opens the
preview in the browser. herdr switches at once; press Cmd + Shift + , in Ghostty; the prompt changes in new panes.

From a terminal (a herdr pane, or any one with the Herdr app alone, where a running app switches at once):

```bash
open "$(python3 ~/.config/herdr-fold/themes/apply.py --preview)"   # all twelve in the browser, with their icons
python3 ~/.config/herdr-fold/themes/apply.py       # the list, the current one marked
python3 ~/.config/herdr-fold/themes/apply.py 2     # by number or by name, for example vscode
```

![The twelve themes, each as a sketch of the TUI's window in its colors (Spaces, Claude's pane, the sidebar on
Changes over the terminal), with its loading sheep and its app icon](../assets/screenshots/tui-themes.webp)

## What a theme sets

- Ghostty's colors;
- herdr's colors, the Spaces and Sessions highlight too, and the Spaces list's labels: `waiting 12m` in the theme's
  yellow, `deleted` in its red, and a repository inside a folder that is not one: its name in the text color, its
  branch under it in a gray still legible on the active row;
- the prompt's colors. The prompt never names the repository, which the space already shows: at a repository's top
  it is the branch, its status and the ❯ on one line; below the top, the path inside it (`/src`) stands above them;
  outside a repository, the path;
- the sidebar's colors (`herdr-fold.sidebar`), in its state folder; a running sidebar switches at once;
- in the Herdr app, herdr-fold's layout: its `theme` names the theme's `themes/herdr-fold-<id>.json`, and a running
  app switches at once; the theme picker in the app's Settings overrides a layout's theme, as the app has it;
- on a Mac, Ghostty's app icon in the Dock and the app switcher: herdr-fold's logo, the sheep, in the theme's colors
  (above), with Liquid Glass as the Mac's own icons have it. It is drawn as a PNG (macOS's `sips`) into
  `~/.local/state/herdr-fold/ghostty-icon/`, the theme in use's alone; Ghostty finds it through
  `~/.config/ghostty/herdr-fold-icon` when it reloads, and the theme's line warns where Ghostty's own config
  (`ghostty +show-config`) does not take it. Ghostty keeps one app icon for all its windows, set by the Ghostty started
  or reloaded last: one started with a config of its own shows Ghostty's icon until herdr-fold's reloads. macOS 27
  does not let Ghostty put it into the app itself, so App Exposé, Finder and Launchpad keep Ghostty's own icon.

Where each theme's colors come from: [Third-party notices](../THIRD_PARTY_NOTICES.md#themes).

When you run the installer again, it offers the current theme: the TUI's, else the Herdr app's. `./tools/sync.sh`
also makes it the package's default.
