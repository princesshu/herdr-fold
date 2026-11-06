# Contributing

herdr-fold is made and maintained by [princesshu](https://github.com/princesshu).

## Issues

Write an issue yourself. An issue written by an AI tool, or one that names an AI tool as its author or co-author, is
deleted. This is about this repository's issues only: how you use AI with herdr-fold is up to you. A security issue goes
in a private report, not in an issue: see [Security](SECURITY.md).

## Running the tests

```bash
/usr/bin/python3 -m unittest discover -s tests
```

The Windows scripts' tests need PowerShell 7: put `pwsh` on your `PATH`, or point `PWSH` at it; without it, they are
skipped. The tests run in temporary folders with stand-ins for herdr, Homebrew, SSH and the clipboard; they never touch
your own settings.

The remote way on a real machine runs in the lab, only when called: `python3 lab/lab.py test` brings up a Linux
machine in a container (Apple's container tool), runs `lab/tests` on it over SSH and takes it down
([the lab's README](lab/README.md)). A clean Mac, Linux on x86_64 and Windows, and the unit tests on a clean Mac,
are in its workflow on GitHub's runners, started by hand at the end of a larger piece of work: `gh workflow run lab`.

## Writing code

- Bash 3.2 (the one macOS ships), PowerShell 5.1 with a UTF-8 BOM (without one it reads a script as ANSI), Python
  3.9 with the standard library only.
- Every text a script prints goes through a key of `src/lang/en.txt`: `t key` in the shell scripts, `t("key")` in
  Python, `T 'key'` in PowerShell. A test checks that every key exists and none is unused.
- A new file the installer puts on a machine goes in `files.txt` (and `remote/files.txt` for remote machines) with its
  part (`tui`, or `both` when the Herdr app uses it too), and in the table of
  [How it is built](docs/architecture.md#whats-in-the-package).
- A new question, switch or key goes in the docs too: the docs tests check them against the code.
- Comments say what the code cannot: the why, a gotcha. None repeats the code, and no comment or docstring runs
  longer than three lines (a test checks); a longer explanation goes in `docs/`.
- A new part of the Herdr app mod, or a new state of one, goes into its styleguide in the same change
  (`app/mods/herdr-fold/styleguide.js`, drawn by the view's own code), and its picture in
  [Styleguide](docs/styleguide.md) is made again.
- A change to a theme, to the sidebar's colors or icons, to the loading sheep or to the logo (`tools/logo.swift`):
  run `/usr/bin/python3 tools/preview_colors.py`, so the theme preview and the logo show it (a test fails until then).

## Keeping up

`/usr/bin/python3 tools/check_updates.py` says whether what herdr-fold builds on moved on, and what to do: a newer
starship than the one pinned for remote machines, a newer herdr than the one last tried, a new major version of Claude
Code or Codex. GitHub runs it every Monday and mails a failed run to whoever last changed its schedule; a fork does
not run it. In a public repository GitHub turns the schedule off after 60 days without activity: the Actions tab turns
it back on.

## Privacy

The privacy test checks every file and every commit for e-mail addresses, IP addresses, Tailscale names, home folder
paths, secrets and AI attribution. It also reads your own tailnet's names and addresses, and a private word list kept
outside the repository: `~/.config/herdr-fold/private-words.txt`, one name, machine or project per line.

- Run `git config core.hooksPath .githooks` once: then the privacy test runs before every commit and reads its
  message too, and a commit with something personal in it stops.
- Use placeholders in examples: `example.com`, `alpha.example`, `192.0.2.10`, `100.115.92.5`, `tail0000`, `dev`.
- `./tools/sync.sh` copies this Mac's settings into the package, leaves out a package file you edited and did not
  commit yet, and checks the files for private data; take out what it names before you commit.

## Commits

- US English, [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `feat:`, `fix:`, `docs:` and so
  on, an imperative subject of at most 72 characters.
- Use your GitHub noreply address as the author (GitHub → Settings → Emails), so your own address stays private.
