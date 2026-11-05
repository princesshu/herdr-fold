# Translating

Everything the installer prints or asks comes from one file, `src/lang/en.txt`: `install.sh`, `machines.sh`, the remote
machines' setup scripts (Linux, macOS, Windows), the uninstaller, the status line and theme setters, and the small
windows in herdr (commit, close, the folder and theme pickers). A new language is one more file next to it,
`<code>.txt`. No code changes are needed.

## Steps

1. **Copy the English file** under the language's code. The code may contain only letters, digits, `_` and `-`
   (for example `de`, `pt-BR`); remote machines get English for anything else.
   ```bash
   cp src/lang/en.txt src/lang/de.txt
   ```
2. **Translate the text after ` = `** on every line, following the rules below. Never change a key. The installer puts
   every file of `src/lang/` in place on the Mac, and `machines.sh` copies them to the remote machines.
3. **Run the check:**
   ```bash
   /usr/bin/python3 -m unittest tests.test_repo_i18n
   ```
   It fails when a key is missing, extra or duplicated, or when a line is not in `key = text` form. A missing key does
   not fall back to English: it prints an empty line.
4. **Look at the result without installing anything.** Both commands only print:
   ```bash
   HERDR_FOLD_LANG=de ./machines.sh help
   HERDR_FOLD_LANG=de python3 src/themes/apply.py
   ```
5. **Install in that language:**
   ```bash
   HERDR_FOLD_LANG=de ./install.sh
   ```
   The remote machines get the same language (`machines.sh` passes it on, to Windows too). Without the variable, or
   without a file for the code, everything is in English.

## Rules for the texts

| In the English text | In the translation |
|---|---|
| `key = text` | Keep the space on both sides of `=`. Lines starting with `#` are comments; empty lines are skipped. |
| `%s` | A value the installer fills in (a path, a name, a number). Keep every one, in the same order: the values cannot be reordered, so phrase the sentence around them. |
| `%%` | A percent sign. A single `%` that is not followed by `s` stays as it is. |
| `\n` | A line break inside the text. Keep the line count of banners and lists. |
| Spaces at the start | Indentation. Keep them. |
| `\` at the end of a line | The text goes on in the next line, indented by two spaces (the indentation is not part of it). Keep lines at 120 characters at most: break after a space between two words, or right before a `\n`. |
| `[Y/n]`, `[y/N]` | Use the language's own letters, for example German `[J/n]` and `[j/N]`; the capital one is the default. List the answers that mean yes in `lib.yes_answers`, lowercase, separated by spaces, for example `lib.yes_answers = j ja`. Every other answer means no, the English `y` too. |

Save the file as UTF-8. Windows line endings (CRLF) also work.

## Keeping the language

The installer does not store the language. `./machines.sh`, `statusline_setup.py` and `themes/apply.py` read
`HERDR_FOLD_LANG` each time they run. To keep it, add this to `~/.zshrc`:

```bash
export HERDR_FOLD_LANG=de
```

## When the English file changes

A new key in `en.txt` makes the check fail for every other language until it is added there too. Copy the line from
`en.txt` and translate it; the failure lists the missing keys.

## What stays in English

- The sidebar's own words (its views, buttons, menus and questions), the herdr plugins' command names, AI Sessions'
  one notification (a damaged names file), and the words the plugins put in the Spaces list (`waiting 12m`,
  `deleted`).
- The status line itself (`context:`, `current:`, `weekly:`) and its samples in the checkbox list.
- Theme names and their short descriptions (`themes.js`, shared with the browser preview).
- Commit messages written with Cmd + Shift + C.
- The interfaces of herdr, Ghostty, Claude Code and Codex.
