# Themes

Twelve themes set the colors of herdr-fold's parts together, the TUI's Ghostty, herdr, prompt and sidebar and
herdr-fold's layout in the Herdr app: Catppuccin Mocha, VS Code (Dark Modern), Vesper, GitHub Dark, Tokyo Night,
Kanagawa, Rosé Pine, One Dark, Dracula, Gruvbox, Nord and Solarized. With both parts installed, one theme sets both.

## Picking a theme

Cmd + K, then Cmd + T opens the picker: the themes with color swatches, Enter applies, `p` opens the preview in the
browser. herdr switches at once; press Cmd + Shift + , in Ghostty; the prompt changes in new panes.

From a herdr pane:

```bash
open "$(python3 ~/.config/herdr-fold/themes/apply.py --preview)"   # all twelve in the browser, with their icons
python3 ~/.config/herdr-fold/themes/apply.py       # the list, the current one marked
python3 ~/.config/herdr-fold/themes/apply.py 2     # by number or by name, for example vscode
```

![The twelve themes, each as a sketch of the work window in its colors, with its loading sheep and its app
icon](../assets/screenshots/themes.webp)

## What a theme sets

- Ghostty's colors;
- herdr's colors, the Spaces and Sessions highlight too, and the Spaces list's labels: `waiting 12m` in the theme's
  yellow, `deleted` in its red;
- the prompt's colors;
- the sidebar's colors (`herdr-fold.sidebar`), in its state folder; a running sidebar switches at once;
- in the Herdr app, herdr-fold's layout: its `theme` names the theme's `themes/herdr-fold-<id>.json`, and a running
  app switches at once; the theme picker in the app's Settings overrides a layout's theme, as the app has it;
- on a Mac, Ghostty's app icon in the Dock and the app switcher: herdr-fold's logo, the sheep, in the theme's colors
  (above), with Liquid Glass as the Mac's own icons have it. It is written into
  `~/.local/state/herdr-fold/ghostty-icon/`, the theme in use's alone; Ghostty finds it through
  `~/.config/ghostty/herdr-fold-icon` when it reloads. macOS 27 does not let Ghostty put it into the app itself, so App
  Exposé, Finder and Launchpad keep Ghostty's own icon.

Where each theme's colors come from: [Third-party notices](../THIRD_PARTY_NOTICES.md#themes).

When you run the installer again, it offers the current theme: the TUI's, else the Herdr app's. `./tools/sync.sh` also makes it the package's default.
