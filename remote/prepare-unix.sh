#!/bin/bash
# Prepares a remote Linux / macOS machine for herdr: the central Mac's installer copies it to ~/.herdr-fold and runs it
# over SSH before connecting. Adds git, python3 and herdr-fold's settings; with the TUI (HERDR_FOLD_PARTS) starship and
# the prompt and ~/.local/bin in herdr panes; --remove (machines.sh remove) brings the machine's own back. Rerunnable.
set -u
remove=; [ "${1:-}" = --remove ] && remove=1
tui=; case " ${HERDR_FOLD_PARTS:-tui} " in *" tui "*) tui=1 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)
F="$HERE/files"
BIN="$HOME/.local/bin"
export PATH="$BIN:/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p "$BIN"
has() { command -v "$1" >/dev/null 2>&1; }
# The texts and the status lines, as on the Mac (lib/i18n.sh, lib/output.sh came along with this script); the texts
# are the Mac's: lang/<language>.txt (HERDR_FOLD_LANG, default en)
CATALOG_DIR="$HERE/lang"
. "$HERE/lib/i18n.sh"
. "$HERE/lib/output.sh"
. "$HERE/lib/files.sh"

if [ -z "$remove" ]; then
  platform=${HERDR_FOLD_PLATFORM:-$(uname -s)-$(uname -m)}   # test switch: HERDR_FOLD_PLATFORM
  case "$platform" in
    Linux-x86_64)               os=linux; ss=x86_64-unknown-linux-musl ;;
    Linux-aarch64|Linux-arm64)  os=linux; ss=aarch64-unknown-linux-musl ;;
    Darwin-arm64)               os=macos; ss=aarch64-apple-darwin ;;
    Darwin-x86_64)              os=macos; ss=x86_64-apple-darwin ;;
    *) fail "$(t prepare.unix.unsupported "$platform")"; exit 1 ;;
  esac

  section "$(t prepare.unix.apps "$platform")"
  apt_updated=
  for p in git python3; do
    if has "$p"; then have "$p"; continue; fi
    if [ "$os" = linux ] && [ "$(id -u)" = 0 ]; then
      if has apt-get; then
        # a fresh image has empty package lists; no question may wait for an answer over ssh
        [ -n "$apt_updated" ] || { DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null; apt_updated=1; }
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$p" >/dev/null
      elif has dnf; then dnf install -y -q "$p" >/dev/null
      elif has yum; then yum install -y -q "$p" >/dev/null; fi
    fi
    if has "$p"; then ok "$p"; else warn "$(t prepare.unix.package_missing "$p")"; fi
  done

  # the prompt, the TUI's: Homebrew's on a Mac that has it, else a pinned release, checksum-verified, into ~/.local/bin
  if [ -z "$tui" ]; then :
  elif has starship; then have starship
  elif [ "$os" = macos ] && has brew && HOMEBREW_NO_ANALYTICS=1 brew install -q starship >/dev/null 2>&1; then
    ok "$(t prepare.unix.installed_brew starship)"
  elif bash "$HERE/fetch-tool.sh" starship "$ss" "$BIN"; then ok starship
  else warn "$(t prepare.unix.not_installed starship)"; fi
fi

if [ -n "$remove" ]; then section "$(t prepare.unix.removing)"; else section "$(t prepare.unix.settings)"; fi
# The files of files.list (the Mac's remote/files.txt) into place: a changed earlier version is backed up first, the
# machine's own to prepared-original/, and a link (to a dotfiles repository) is set aside, never written through. What
# the last list (prepared.txt) had and this one drops goes, the machine's own back, unless this Mac's install uses it.
state="$HOME/.local/state/herdr-fold"; record="$state/prepared.txt"; backup="$state/prepared-$(date +%Y%m%d-%H%M%S)"
original="$state/prepared-original"
# its owner's only: the backups hold the machine's own files; a copy keeps its file's mode too (cp -p)
mkdir -p "$state" && chmod 700 "$state"
# a Mac with an install of its own (install.sh, its record installed.txt): its files, shell block, status line and
# plugins are its own install's — this prepare leaves them alone
own=; [ -f "$state/installed.txt" ] && own=1
owned_here() {   # owned_here REL: the own install's file, or its status line choice
  [ -n "$own" ] && { grep -qxF "$1" "$state/installed.txt" || [ "$1" = .config/herdr-fold/statusline.json ]; }
}
keep() { mkdir -p "$(dirname "$backup/$1")" && cp -p "$HOME/$1" "$backup/$1"; }   # keep <file relative to $HOME>
if [ -n "$remove" ] && [ -z "$own" ]; then
  # Claude's status line first (its script is about to go): the one the machine had — the first one saved — comes
  # back, or herdr-fold's just goes
  first=$(ls "$state"/prepared-*/claude-statusLine.json 2>/dev/null | sort | head -1)
  if [ -f "$HOME/.config/herdr-fold/statusline_setup.py" ]; then
    python3 "$HOME/.config/herdr-fold/statusline_setup.py" --claude-restore "$(dirname "${first:-$state/none/x}")"
    case $? in
      0) ok "$(t prepare.unix.status_line_back)" ;;
      1) warn "$(t status.claude_unreadable "$HOME/.claude/settings.json")" ;;
    esac
  fi
fi
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  owned_here "$rel" && continue
  if grep -qxF "$rel" "$record" 2>/dev/null; then aside="$backup/$rel"; else aside="$original/$rel"; fi
  if [ -L "$HOME/$rel" ]; then set_aside=mv
  elif [ -f "$HOME/$rel" ] && ! cmp -s "$F/$rel" "$HOME/$rel"; then set_aside="cp -p"
  else set_aside=; fi
  if [ -n "$set_aside" ] && ! { mkdir -p "$(dirname "$aside")" && $set_aside "$HOME/$rel" "$aside"; }; then
    warn "$(t prepare.unix.not_kept "~/$rel")"; continue
  fi
  mkdir -p "$(dirname "$HOME/$rel")" && cp "$F/$rel" "$HOME/$rel" && ok "~/$rel"
  case "$rel" in *.sh) chmod +x "$HOME/$rel" ;; esac
done < "$HERE/files.list"
if [ -f "$record" ]; then
  grep -vxF -f "$HERE/files.list" "$record" | while IFS= read -r rel; do
    [ -n "$rel" ] && ! ai_session_file "$rel" || continue
    grep -qxF "$rel" "$state/installed.txt" 2>/dev/null && continue
    owned_here "$rel" && continue
    # taken off: one that is still the package's own version just goes; one changed here is kept first
    if [ -f "$HOME/$rel" ]; then
      if [ -z "$remove" ] || ! cmp -s "$F/$rel" "$HOME/$rel"; then keep "$rel" || continue; fi
      rm -f "$HOME/$rel" && ok "$(t prepare.unix.removed "~/$rel")"
    fi
    if [ -f "$original/$rel" ] || [ -L "$original/$rel" ]; then
      mkdir -p "$(dirname "$HOME/$rel")" && mv "$original/$rel" "$HOME/$rel" \
        && ok "$(t prepare.unix.restored "~/$rel")"
    else
      remove_empty_dirs "$(dirname "$HOME/$rel")"
    fi
  done
fi
if [ -n "$remove" ]; then
  rm -f "$record"
else
  mkdir -p "$state" && cp "$HERE/files.list" "$record"
fi
[ -d "$backup" ] && saved "$(t prepare.unix.backup "$backup")"

if [ -z "$remove" ] && [ -z "$own" ]; then
  # Claude Code status line — herdr-fold's; one the machine had before is saved to the backup folder
  # (statusline_setup.py); chosen on the Mac to be your own, the machine's own stays (--apply below brings it back)
  python3 "$HOME/.config/herdr-fold/statusline_setup.py" --claude-settings "$backup" \
    'python3 "$HOME/.config/herdr-fold/statusline.py"' >/dev/null
  case $? in
    0) ok "$(t status.claude_set)" ;;
    2) ok "$(t status.claude_replaced "$backup")" ;;
    3) ;;
    *) warn "$(t status.claude_unreadable "$HOME/.claude/settings.json")" ;;
  esac
  # The status line items as chosen on the Mac (statusline.json came with the files; statusline.py reads it, Codex
  # gets them in its own settings)
  python3 "$HOME/.config/herdr-fold/statusline_setup.py" --apply

  # Prompt and apps in herdr panes (the TUI's), for the login shell: one marked block, replaced on every run
  if [ -n "$tui" ]; then
    case "$(basename "${SHELL:-bash}")" in zsh) rc="$HOME/.zshrc"; sh=zsh ;; *) rc="$HOME/.bashrc"; sh=bash ;; esac
    before=$(mktemp); cp "$rc" "$before" 2>/dev/null
    marked_block "$rc" "# only inside herdr panes (other logins on the machine are unaffected)" \
      'if [ -n "${HERDR_ENV:-}" ]; then' '  export PATH="$HOME/.local/bin:$PATH"' \
      "  command -v starship >/dev/null 2>&1 && eval \"\$(starship init $sh)\"" 'fi'
    cmp -s "$rc" "$before" || ok "$(t prepare.unix.prompt_added "${rc#$HOME/}")"
    rm -f "$before"
  fi
elif [ -n "$remove" ] && [ -z "$own" ]; then
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do remove_marked_block "$rc"; done
  # herdr-fold's plugins, and the empty folders herdr keeps of them (the conversation names stay)
  for id in herdr-fold.sessions-view herdr-fold.tab-layout; do
    herdr plugin unlink "$id" >/dev/null 2>&1
  done
  drop_plugin_folders herdr-fold.sessions-view herdr-fold.tab-layout
  # what Python and the status line setup made here next to the package's files
  find "$HOME/.config/herdr-fold" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  rm -f "$HOME/.config/herdr-fold/statusline.json"
  remove_empty_dirs "$HOME/.config/herdr-fold"
  # the sidebar's own settings, its folder only when nothing else is in it (the rest of herdr's state is herdr's)
  sidebar_state="$HOME/.local/state/herdr/plugins/herdr-fold.sidebar"
  rm -f "$sidebar_state/settings.json" "$sidebar_state/colors.json" "$sidebar_state/column.json" \
    "$sidebar_state/conversations.json" "$sidebar_state/conversation-index.json" "$sidebar_state/panels.json" \
    "$sidebar_state"/resume-*.json "$sidebar_state"/seed-*.json "$sidebar_state"/preview-*.json \
    "$sidebar_state"/issues-*.json \
    "$sidebar_state"/.*.tmp                                                   # .*.tmp: a write cut short
  rmdir "$sidebar_state" 2>/dev/null
fi
if [ -n "$remove" ]; then
  # AI Sessions' conversation names stay, as the conversations themselves, and are named
  names="$HOME/.local/state/herdr/plugins/herdr-fold.sessions-view/names.json"
  [ -z "$own" ] && [ -f "$names" ] && saved "$(t prepare.unix.kept_names "~/${names#$HOME/}")"
  [ -d "$state" ] && find "$state" -depth -type d -empty -delete
  [ -d "$state" ] && [ -z "$own" ] && saved "$(t prepare.unix.kept "~/${state#$HOME/}")"
fi
# the payload this ran from goes (machines.sh sends a fresh one each time)
[ "$HERE" = "$HOME/.herdr-fold" ] && rm -rf "$HERE"
exit 0
