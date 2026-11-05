# Styleguide

The Herdr app mod's look, part by part: the foundations it is built on, each component in each of its states, and the
panels they make. The pictures are the styleguide inside the mod itself, drawn by the views' own code from made-up
states, so they show what the mod draws; in the Herdr app, `herdr-app do herdr-fold.styleguide` opens it in a tab. The
colors are the layout's theme, Catppuccin Mocha, as in the TUI.

## Foundations

### Color

![The theme's colors by role: surfaces, text, accent and the states of a change](../assets/styleguide/color.webp)

| Token | Use |
|---|---|
| `background` | panels and fields |
| `raised` | buttons and chips |
| `hover` | what the mouse is on |
| `selected` | the chosen row |
| `selection` | a match in Search, the ✦ button |
| `border` | frames and rules |
| `foreground` | body text |
| `muted` | icons and captions |
| `dim` | folders, line numbers, authors |
| `accent` | the checked-out commit, branches and tags, the ✦ |
| `solid`, `solid_foreground` | Commit and its arrow, and their words |
| `ansi2` | an added or untracked file, an added line |
| `blocked` | a modified file |
| `ansi1` | a deleted file, a conflict, a removed line, an error |

### Type, shape and size

![The type scale, the radii and the heights](../assets/styleguide/type.webp)

Body text is 13, a button's words 12 bold, a folder or a caption 11; code is Menlo, 13 in the preview tab and 11 for
a hit's file. Panels are rounded 10, controls 8, rows 6 and chips 5.

### Motion

A section, and the Graph, slides open and shut: its height in 180 ms, easing out, animated by the app itself
(`transition`), never by the mod's own timer.

### Iconography

![The mod's icons, Lucide's, by name](../assets/styleguide/icons.webp)

![Each file type's icon, Catppuccin Icons'](../assets/styleguide/file-types.webp)

The views' icons are Lucide's, drawn by `icon(name)` in the text's color; a file's is Catppuccin Icons' for its type,
in its own colors (`fileMark`), the types told apart as the TUI sidebar tells them (`core/icons.py`). `tools/icons.py`
fetches both from Iconify into `app/mods/herdr-fold/icons/`, `icons.js` names each once, and a test fails on an icon
no view draws.

## Components

States are named alike throughout: Default, Hover, Selected, Busy, Asking (a second press to confirm) and Error.

### Buttons

![Primary, busy, secondary, disabled, icon and row buttons](../assets/styleguide/buttons.webp)

Commit is the one solid button; it keeps its color while it cannot commit yet. A secondary button dims its words when
it cannot be pressed. A row's buttons show only with the mouse on the row.

### Commit

![The repository row, as VS Code's Repositories, in sync, behind and ahead, its ⋯ open, with no upstream and
folded; the message field with its ✦, Commit and its mode arrow, in each state, and the issue the next commit
fixes](../assets/styleguide/commit.webp)

### Panel tabs and the search field

![The right panel's tabs, the shown one raised, Changes with its count, Issues on GitHub only; and the search field
with its switches](../assets/styleguide/tabs.webp)

The right panel is one of Adobe's panel groups: herdr-fold's views and the app's Files as its tabs, on the header of
the stack that holds them. Two hover backgrounds side by side keep 4 apart (`GAP`), tabs and icon buttons alike.

### Section header and count chip

![A section's header: default, with the mouse on it, asking, folded; the count chip](../assets/styleguide/sections.webp)

### File row

![A changed file's row in each state](../assets/styleguide/rows.webp)

### Graph and mode menu

![The Graph open, a commit chosen, folded; the Commit button's modes](../assets/styleguide/graph.webp)

### Problems and empty states

![A sync's problem, and the list's empty states](../assets/styleguide/content.webp)

### Issues

![An issue's row in each state](../assets/styleguide/issues.webp)

![The list with its filters, an issue's menu, loading, busy, none and an error](../assets/styleguide/issue-list.webp)

An issue's number takes its priority's color, as the TUI's traffic light: urgent and high red, medium yellow, low
green; without one, the accent. Closing or reopening asks on the row first.

### The preview tab

![The preview tab with a diff, a commit, loading and an error](../assets/styleguide/preview.webp)

![An issue in the preview tab, with its comments](../assets/styleguide/preview-issue.webp)

### Conversations

![The left sidebar's Conversations: by space, the running ones marked in herdr's colors; filtered, a menu open, one
renamed in its row, the archived shown, loading, none yet; folded to a rail, and the toggle left of the
tabs](../assets/styleguide/conversations.webp)

Folded, the sidebar is a dock, as Adobe's panels collapse to icons: each panel on a square (`iconTab`: 30 square,
radius 6), its name under it, its most urgent state's dot at the corner; a press floats it beside the dock, a window
its head drags and its × closes (`floatPanel`). The app's footer buttons sit centered at its foot, its toggle left of
the tabs, where the window's buttons leave it room. Every icon button is `iconButton`: 26 square, radius 6.

### Search results

![Hits by file, one shown at its line below](../assets/styleguide/search.webp)

### The tab's terminal

![The tab's terminal when it could not start: why, in its place](../assets/styleguide/terminal.webp)

## Patterns

![The Changes, Search and Issues panels](../assets/styleguide/panels.webp)

## A new part

A new component, or a new state of one, goes into the styleguide in the same change: into
`app/mods/herdr-fold/styleguide.js`, drawn by the view's own method from a made-up state, and its picture here is made
again. See [The Herdr app](app.md) for the mod itself.
