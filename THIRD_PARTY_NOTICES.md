# Third-party notices

herdr-fold is made by [princesshu](https://github.com/princesshu) and MIT-licensed (see [LICENSE](LICENSE)). It
builds on the work below, made by others.

## Themes

The colors in `src/themes/themes.js` come from Ghostty's theme files (the
[iTerm2-Color-Schemes](https://github.com/mbadolato/iTerm2-Color-Schemes) collection, MIT, Copyright (c) 2011 to
Present Mark Badolato), from herdr's built-in palettes ([herdr](https://github.com/herdrdev/herdr), Apache-2.0), and
from VS Code's Dark Modern theme. Each palette was designed by its own project:

| Theme | Project | License | Copyright |
|---|---|---|---|
| Catppuccin Mocha | [catppuccin/catppuccin](https://github.com/catppuccin/catppuccin) | MIT | Copyright (c) 2021 Catppuccin |
| VS Code (Dark Modern) | [microsoft/vscode](https://github.com/microsoft/vscode) | MIT | Copyright (c) 2015 - present Microsoft Corporation |
| Vesper | [raunofreiberg/vesper](https://github.com/raunofreiberg/vesper) | MIT | Copyright (c) 2023 Rauno Freiberg |
| GitHub Dark | [primer/github-vscode-theme](https://github.com/primer/github-vscode-theme) | MIT | Copyright (c) 2020 Primer |
| Tokyo Night | [tokyo-night/tokyo-night-vscode-theme](https://github.com/tokyo-night/tokyo-night-vscode-theme) | MIT | Copyright (c) 2018-present Enkia |
| Kanagawa | [rebelot/kanagawa.nvim](https://github.com/rebelot/kanagawa.nvim) | MIT | Copyright (c) 2021 Tommaso Laurenzi |
| Rosé Pine | [rose-pine/rose-pine-theme](https://github.com/rose-pine/rose-pine-theme) | MIT | Copyright (c) 2023 Rosé Pine |
| One Dark | [atom/one-dark-syntax](https://github.com/atom/one-dark-syntax) | MIT | Copyright (c) 2016 GitHub Inc. |
| Dracula | [dracula/dracula-theme](https://github.com/dracula/dracula-theme) | MIT | Copyright (c) 2023 Dracula Theme |
| Gruvbox | [morhetz/gruvbox](https://github.com/morhetz/gruvbox) | MIT/X11 (stated in its README) | morhetz (no copyright line in the repository) |
| Nord | [nordtheme/nord](https://github.com/nordtheme/nord) | MIT | Copyright (c) 2016-present Sven Greb |
| Solarized | [altercation/solarized](https://github.com/altercation/solarized) | MIT | Copyright (c) 2011 Ethan Schoonover |

## Icons

The Herdr app mod's icons, fetched from [Iconify](https://iconify.design) by `tools/icons.py`, are unchanged but for
line breaks. The views' (`app/mods/herdr-fold/icons/lucide/`) are [Lucide](https://lucide.dev)'s:

```text
ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All
other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

A file's (`app/mods/herdr-fold/icons/catppuccin/`) are [Catppuccin Icons](https://github.com/catppuccin/vscode-icons)':

```text
MIT License

Copyright (c) 2023 Catppuccin
Copyright (c) 2023 thang-nm

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Programs it installs

These are not part of this repository: the installer gets them with Homebrew (and Homebrew itself, if it is missing),
and a remote Windows machine gets Python from winget or python.org.

| Program | Project | License |
|---|---|---|
| Homebrew | [Homebrew/brew](https://github.com/Homebrew/brew) | BSD-2-Clause |
| herdr | [herdrdev/herdr](https://github.com/herdrdev/herdr) | Apache-2.0 |
| Ghostty | [ghostty-org/ghostty](https://github.com/ghostty-org/ghostty) | MIT |
| starship | [starship/starship](https://github.com/starship/starship) | ISC |
| gh | [cli/cli](https://github.com/cli/cli) | MIT |
| JetBrains Mono Nerd Font | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono), patched by [ryanoasis/nerd-fonts](https://github.com/ryanoasis/nerd-fonts) | OFL-1.1 (the fonts), MIT (the Nerd Fonts patcher) |
| bat | [sharkdp/bat](https://github.com/sharkdp/bat) | MIT or Apache-2.0 |
| delta | [dandavison/delta](https://github.com/dandavison/delta) | MIT |
| ripgrep | [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep) | Unlicense or MIT |
| Python (Windows machines) | [python/cpython](https://github.com/python/cpython) | Python Software Foundation License Version 2 |

Ghostty's app icon in a theme's colors is herdr-fold's logo, the sheep: herdr-fold's own drawing, in the shape of the
Mac's own app icons. None of Ghostty's artwork is in it or in this repository.

## Trademarks

Claude Code, Codex, VS Code, GitHub, Tailscale, herdr and Ghostty are trademarks of their respective owners. herdr-fold
is an independent project, not affiliated with or endorsed by them.

herdr-fold's name and its logo, the sheep (`src/themes/logo.svg`, and the app icon in each theme's colors made from
it), identify this project. The MIT license covers the code and the files, but gives no right to use the name or the
logo to identify another project or product.
