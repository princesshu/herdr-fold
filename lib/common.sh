# Shared helpers and settings for install.sh, uninstall.sh, machines.sh and tools/sync.sh. Load with: source, after
# setting DOT (the package folder).

# No Python cache next to the scripts, in the package or the installed folders: the python3 on PATH may be one that
# writes it there (Homebrew's), unlike the Mac's own, which keeps it in ~/Library/Caches
export PYTHONDONTWRITEBYTECODE=1

trim() { sed 's/^[[:space:]]*//; s/[[:space:]]*$//'; }

# The remote machines (machines.sh fills it in) — outside the package, so a new copy of the package keeps it
MACHINE_LIST="$HOME/.config/herdr-fold/machines.txt"
# The machines herdr-fold added to the Herdr app's core (hc); only these come off it again
APP_MACHINES="$HOME/.local/state/herdr-fold/app-machines.txt"

# The Herdr app's core, hc (herdr-core): on PATH, else beside the app's command line
hc_bin() {
  local app
  command -v herdr-core || command -v hc \
    || { app=$(python3 "$DOT/lib/herdr_app.py" cli) && [ -x "${app%/*}/herdr-core" ] && echo "${app%/*}/herdr-core"; }
}

# remove_from_app NAME — a machine herdr-fold added to the Herdr app leaves it (its terminals keep running there)
remove_from_app() {
  local hc tmp
  grep -qxF "$1" "$APP_MACHINES" 2>/dev/null || return 0
  hc=$(hc_bin)
  if [ -n "$hc" ] && "$hc" machine rm "$1" >/dev/null 2>&1; then ok "$(t machines.app_removed "$1")"
  else warn "$(t machines.app_remove_failed "$1" "$1")"; fi
  tmp=$(mktemp) && grep -vxF "$1" "$APP_MACHINES" > "$tmp"; mv "$tmp" "$APP_MACHINES"
}

# The package's files and where they go on the machine, from files.txt, as "path in the package|path under HOME"
# lines. A line with a * stands for every matching file in the package: `src/lang/*.txt | .config/herdr-fold/lang/`
# puts every language file in place, so a new language needs no new line.
package_files() {
  local src rel f
  grep -vE '^[[:space:]]*(#|$)' "$DOT/files.txt" | while IFS='|' read -r src rel; do
    src=$(echo "$src" | trim); rel=$(echo "$rel" | trim)
    case "$src" in
      *'*'*) for f in "$DOT"/$src; do [ -f "$f" ] && echo "${f#"$DOT"/}|$rel${f##*/}"; done ;;
      *) echo "$src|$rel" ;;
    esac
  done
}

# The texts (t) and the status lines (ok, warn, fail, …): shared with the prepare script of a remote machine
CATALOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/src/lang"
. "$(dirname "${BASH_SOURCE[0]}")/i18n.sh"
. "$(dirname "${BASH_SOURCE[0]}")/output.sh"
. "$(dirname "${BASH_SOURCE[0]}")/files.sh"

# Is there a terminal to ask questions on? (HERDR_FOLD_YES=1: no questions, every answer is the default)
interactive() { [ "${HERDR_FOLD_YES:-}" != 1 ] && { : > /dev/tty; } 2>/dev/null; }

# ask "Question?" y|n — yes/no question, [Y/n] or [y/N]: the capital letter is the default, which Enter picks.
ask() {
  local default=$2 ans= hint word
  if interactive; then
    if [ "$default" = y ]; then hint=$(t lib.ask_default_yes); else hint=$(t lib.ask_default_no); fi
    printf '  %s %s ' "$1" "$hint" > /dev/tty
    read -r ans < /dev/tty
  fi
  [ -n "$ans" ] || { [ "$default" = y ]; return; }
  # the answers that mean yes are the language's (English: y yes), in any case; everything else means no
  ans=$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')
  for word in $(t lib.yes_answers); do [ "$ans" = "$word" ] && return 0; done
  return 1
}

# wait_for_start — the installer's first line: "Press Enter to start, any other key to cancel." (only when it asks
# questions); whether to start. Not a yes/no question: the first [Y/n] or [y/N] is then a real decision's.
wait_for_start() {
  local key=
  interactive || return 0
  printf '  %s ' "$(t lib.press_enter_to_start)" > /dev/tty
  IFS= read -r -n 1 -s key < /dev/tty
  echo > /dev/tty
  [ -z "$key" ]
}

# wait_for_key — the installer's very last step: "Press any key to exit." and waits (only when it asks questions).
# Started with a double-click in Finder, Terminal or Ghostty closes the window as soon as the installer ends — this way
# the result stays readable.
wait_for_key() {
  interactive || return 0
  printf '\n  %s ' "$(t lib.press_any_key)" > /dev/tty
  read -r -n 1 -s < /dev/tty
  echo > /dev/tty
}

# prompt "Question" [default] — free-text answer (empty = default)
prompt() {
  local ans=
  if interactive; then
    printf '  %s%s: ' "$1" "${2:+ [$2]}" > /dev/tty
    read -r ans < /dev/tty
  fi
  printf '%s' "${ans:-${2:-}}"
}

# Homebrew in its own place, for a run whose PATH lacks it (a double-click, herdr's tab)
brew_env() {
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && return 0; done
  return 1
}

# Remote machines need an SSH key (step 8, Ctrl+B Shift+M: machines.sh pick); Tailscale is one place to find them
has_ssh_key() { ls "$HOME"/.ssh/id_* 2>/dev/null | grep -qv '\.pub$' || ssh-add -l >/dev/null 2>&1; }
tailscale_bin() {
  command -v tailscale 2>/dev/null \
    || { [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] \
           && echo /Applications/Tailscale.app/Contents/MacOS/Tailscale; }
}
# The Host * block for the new key, written once; IgnoreUnknown comes first: Homebrew's OpenSSH does not
# know UseKeychain
ssh_config_block() {
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  grep -q 'UseKeychain' "$HOME/.ssh/config" 2>/dev/null && return 0
  printf '%s\n' '' 'Host *' '  IgnoreUnknown UseKeychain' '  AddKeysToAgent yes' '  UseKeychain yes' \
    '  IdentityFile ~/.ssh/id_ed25519' >> "$HOME/.ssh/config"
  chmod 600 "$HOME/.ssh/config"
}
# record_outside WHAT — something done outside herdr-fold's own folders (the SSH key, a trusted host key, the GitHub
# sign-in, git's settings), once each, for the uninstaller to name: it stays, being yours
record_outside() {
  local file="$HOME/.local/state/herdr-fold/outside.txt"
  mkdir -p "$(dirname "$file")" && { grep -qxF "$1" "$file" 2>/dev/null || printf '%s\n' "$1" >> "$file"; }
}
# make_ssh_key — a new ED25519 key, after a question; its comment is herdr-fold's name, not user@host: the public key
# goes into every machine's authorized_keys and shows on screen, and those would name the account and the Mac
make_ssh_key() {
  ask "$(t install.ssh_key_ask)" y || return 0
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519" -C herdr-fold </dev/tty || return 0
  record_outside ssh-key
  ssh_config_block
  ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519" </dev/tty 2>/dev/null
  echo "  $(t install.ssh_key_authorize)"
  note "$(t install.ssh_key_unix)"
  note "$(t install.ssh_key_windows_admin 'C:\ProgramData\ssh\administrators_authorized_keys')"
  note "$(t install.ssh_key_windows_other 'C:\Users\<user>\.ssh\authorized_keys')"
  echo; cat "$HOME/.ssh/id_ed25519.pub"; echo
  prompt "$(t install.ssh_key_done)" >/dev/null
}

# The loading animation for the long steps (lib/loading.sh)
. "$(dirname "${BASH_SOURCE[0]}")/loading.sh"
