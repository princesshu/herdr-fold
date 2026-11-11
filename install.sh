#!/bin/bash
# herdr-fold installer wizard — for the central Mac (every machine is visible and controlled from here).
# Usage:  cd <the herdr-fold folder> && ./install.sh — safe to rerun: done steps are skipped, overwritten files backed
# up. The HERDR_FOLD_* switches: docs/installation.md.
set -u
cd "$(dirname "$0")" || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
# The [!] and [✗] lines of this run, counted for the closing line (machines.sh, run from here, adds its own)
HERDR_FOLD_WARNINGS=$(mktemp); export HERDR_FOLD_WARNINGS
# When the installer ends — also when it stops early — say so, then wait for a key: started with a double-click, the
# terminal app would close the window right away
finish() {
  local status=$?
  [ "$status" = 0 ] || fail "$(t install.stopped)"
  rm -f "$HERDR_FOLD_WARNINGS"
  wait_for_key
}
trap finish EXIT

if [ "$(uname -s)" != Darwin ]; then
  echo "$(t install.macos_only)" >&2
  exit 1
fi
# a terminal left in a folder that went to the Trash runs that old copy, not the one unpacked in its place
case "$DOT/" in
  "$HOME"/.Trash/*|*/.Trashes/*) warn "$(t install.in_trash "$(shown "$DOT")")"; exit 1 ;;
esac

# Ghostty open while the install runs (started from one of its herdr panes, or from any other terminal): it has to be
# reopened afterward to start with the new settings, the theme and its icon (herdr and the agents keep running) — said
# once, at the end, where it can be done
ghostty_open() { [ -n "${HERDR_PANE_ID:-}" ] || [ "${HERDR_ENV:-}" = 1 ] || pgrep -xq ghostty; }
# Run from herdr's marketplace (a folder per version, old ones removed), the package moves to PACKAGE_HOME, where
# Ctrl+B, Shift+M, updates and the uninstaller find it. PACKAGE_HOME(.new|.old) is touched only with KEPT_MARK in it.
PACKAGE_HOME=$HOME/.local/share/herdr-fold KEPT_MARK=.kept-by-herdr-fold
# HERDR_FOLD_STARTED, HERDR_FOLD_UPDATE: the moved installer started again from PACKAGE_HOME, already said yes to (an
# update with the earlier choices); anywhere else nothing, and never handed on
started=${HERDR_FOLD_STARTED:-} update=${HERDR_FOLD_UPDATE:-}; unset HERDR_FOLD_STARTED HERDR_FOLD_UPDATE
[ "$DOT" = "$PACKAGE_HOME" ] || started=
[ "$started" = 1 ] || update=
state="$HOME/.local/state/herdr-fold"
this_version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$DOT/herdr-plugin.toml" | head -n 1)
if [ "$started" != 1 ]; then
  echo "$(t install.intro)"
  echo
  # installed here already: one question, the earlier choices or every question again
  if [ -f "$state/installed.txt" ] && interactive; then
    earlier=$(cat "$state/version" 2>/dev/null)
    if [ -n "$earlier" ]; then echo "  $(t install.update_found "$earlier" "$this_version")"
    else echo "  $(t install.update_found_earlier "$this_version")"; fi
    ask "$(t install.update_ask)" y && update=1
  else
    wait_for_start || exit 0
  fi
fi
# an update with the earlier choices: only a question about something new is asked
updating() { [ "$update" = 1 ]; }

keep_package() {
  remove_marked "$PACKAGE_HOME.new" "$KEPT_MARK" && remove_marked "$PACKAGE_HOME.old" "$KEPT_MARK" || return 1
  mkdir -p "$PACKAGE_HOME.new" && : > "$PACKAGE_HOME.new/$KEPT_MARK" && cp -R "$DOT/." "$PACKAGE_HOME.new" || return 1
  trap '' INT TERM HUP                                        # the two moves go together: no Ctrl+C between them
  if [ -e "$PACKAGE_HOME" ]; then mv "$PACKAGE_HOME" "$PACKAGE_HOME.old" || { trap - INT TERM HUP; return 1; }; fi
  mv "$PACKAGE_HOME.new" "$PACKAGE_HOME" || { mv "$PACKAGE_HOME.old" "$PACKAGE_HOME"; trap - INT TERM HUP; return 1; }
  trap - INT TERM HUP
  remove_marked "$PACKAGE_HOME.old" "$KEPT_MARK"
}
# herdr-fold linked to a working copy (herdr plugin link), not herdr's own copy from its marketplace
linked() {
  "${HERDR_BIN_PATH:-herdr}" plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    plugins = json.load(sys.stdin)["result"]["plugins"]
except (ValueError, KeyError, TypeError):
    plugins = []
sys.exit(not any(p.get("plugin_id") == "herdr-fold" and str((p.get("source") or {}).get("kind")).lower() == "local"
                 for p in plugins if isinstance(p, dict)))'
}
if [ -n "${HERDR_PLUGIN_ROOT:-}" ] && [ "$(cd "$HERDR_PLUGIN_ROOT" 2>/dev/null && pwd -P)" = "$(pwd -P)" ] && ! linked
then
  for kept in "$PACKAGE_HOME" "$PACKAGE_HOME.new" "$PACKAGE_HOME.old"; do
    if [ -e "$kept" ] && [ ! -e "$kept/$KEPT_MARK" ]; then
      warn "$(t install.package_not_herdr_folds "$(shown "$kept")")"
      exit 1
    fi
  done
  if keep_package; then
    note "$(t install.package_kept "$(shown "$PACKAGE_HOME")")"
    rm -f "$HERDR_FOLD_WARNINGS"; trap - EXIT
    HERDR_FOLD_STARTED=1 HERDR_FOLD_UPDATE=$update exec /bin/bash "$PACKAGE_HOME/install.sh" "$@"
  fi
  remove_marked "$PACKAGE_HOME.new" "$KEPT_MARK"
  warn "$(t install.package_not_kept "$(shown "$PACKAGE_HOME")")"
  exit 1
fi

# herdr's plugins, one "id|version|does|source" line each: does lists tab.created (lays out new tabs) and agent.view.set
# (sets the Agents list; herdr-fold's own are not searched); source is github (marketplace) or local (linked).
plugin_facts() {
  herdr plugin list --json 2>/dev/null | python3 -c '
import json, os, re, sys
try:
    plugins = json.load(sys.stdin)["result"]["plugins"]
except (ValueError, KeyError, TypeError):
    plugins = []
def sets_the_view(root):
    for base, dirs, files in os.walk(root) if root else ():
        for name in files:
            try:
                with open(os.path.join(base, name), encoding="utf-8") as f:
                    if "agent.view.set" in f.read(1000000):
                        return True
            except (OSError, UnicodeDecodeError):
                pass
    return False
# the retired Tab Layout among them, from an earlier install: this run takes it off
herdr_fold_ids = {"herdr-fold", "herdr-fold.sidebar", "herdr-fold.sessions-view", "herdr-fold.workspaces",
                  "herdr-fold.tab-layout"}
valid = re.compile(r"[A-Za-z0-9._:-]+")             # the id characters herdr allows: no line or field break
for p in plugins:
    pid = str(p.get("plugin_id", ""))
    if not valid.fullmatch(pid):
        continue
    of_herdr_fold = pid in herdr_fold_ids
    does = ["tab.created"] if any(e.get("on") == "tab.created" for e in p.get("events") or []) else []
    does += ["agent.view.set"] if not of_herdr_fold and sets_the_view(p.get("plugin_root")) else []
    kind = str((p.get("source") or {}).get("kind") or "local").lower()
    version = str(p.get("version") or "")
    print("%s|%s|%s|%s" % (pid, version if valid.fullmatch(version) else "", ",".join(does), kind))'
}

# take_over ID FOLDER — one of herdr-fold's installed alone from herdr's marketplace (herdr's own copy): this
# installer's (FOLDER, in place) takes its place, on the record (plugins.txt, taken:ID), so the uninstaller names the
# way back; without its own in place, the marketplace's stays
take_over() {
  [ -f "$2/herdr-plugin.toml" ] || return 0
  printf '%s\n' "$facts" | awk -F'|' -v id="$1" '$1 == id && $4 == "github" { found = 1 } END { exit !found }' \
    || return 0
  herdr plugin uninstall "$1" >/dev/null 2>&1 || return 0
  note "$(t install.plugin_taken_over "$1")"
  grep -qxF "taken:$1" "$plugins.new" || echo "taken:$1" >> "$plugins.new"
}

# The parts this run sets up, the TUI, the Herdr app or both ("tui app"): asked first, beside their page in the
# browser (the one installed, or the app on this Mac, marked); an update keeps what is installed, HERDR_FOLD_PARTS
# answers it. Fewer than are installed keep the others: ./uninstall.sh takes a part off
app=$(python3 "$DOT/lib/herdr_app.py" cli)
had=$(python3 "$DOT/src/parts.py" "$state" | xargs)
parts=$(parts_of "${HERDR_FOLD_PARTS:-}")
[ -n "$parts" ] || [ -z "${HERDR_FOLD_PARTS:-}" ] || warn "$(t install.parts_unknown "$HERDR_FOLD_PARTS")"
if [ -z "$parts" ] && updating && [ -n "$had" ]; then parts=$had; fi
if [ -z "$parts" ]; then
  if [ -n "$had" ]; then default=$had
  elif [ -n "$app" ] && ! grep -qxF declined:herdr-fold.app "$state/plugins.txt" 2>/dev/null; then default="tui app"
  else default=tui; fi
  case $default in tui) number=1 ;; app) number=2 ;; *) number=3 ;; esac
  listed=0
  if interactive; then
    open "$(python3 "$DOT/src/parts.py" --preview $had ${app:+found})" 2>/dev/null \
      && note "$(t install.parts_preview)" && listed=1
    mark() {
      case " $had " in *" $1 "*) printf '   %s' "$(t install.parts_installed)"; return ;; esac
      [ "$1" != app ] || [ -z "$app" ] || printf '   %s' "$(t install.parts_found)"
    }
    printf '   1. %s%s\n   2. %s%s\n   3. %s\n' "$(t install.parts_tui)" "$(mark tui)" "$(t install.parts_app)" \
      "$(mark app)" "$(t install.parts_both)"
    listed=$((listed + 3))
  fi
  parts=$(parts_of "$(prompt "$(t install.parts_ask)" "$number")")
  parts=${parts:-$default}
  [ "$listed" = 0 ] || [ ! -t 1 ] || printf '\033[%dA\r\033[J' $((listed + 1))
fi
kept=
for part in $had; do
  case " $parts " in *" $part "*) ;; *) parts="$parts $part" kept="$kept $part" ;; esac
done
parts=$(for part in tui app; do case " $parts " in (*" $part "*) echo "$part" ;; esac; done | xargs)
case $parts in
  tui) ok "$(t install.parts_set_tui)" ;;
  app) ok "$(t install.parts_set_app)" ;;
  *) ok "$(t install.parts_set_both)" ;;
esac
case $kept in *tui*) note "$(t install.parts_kept_tui)" ;; esac
case $kept in *app*) note "$(t install.parts_kept_app)" ;; esac

step "$(t install.step_prerequisites)"
# what is there, in one line; what is missing, a line each under it
there=() missing=()
command -v brew >/dev/null 2>&1 || brew_env
if command -v brew >/dev/null 2>&1; then
  there+=("$(t install.homebrew)")
else
  warn "$(t install.homebrew_missing)"
  ask "$(t install.homebrew_ask)" y || { note "$(t install.homebrew_later)"; exit 1; }
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty \
    && brew_env || { warn "$(t install.homebrew_failed)"; exit 1; }
  grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null \
    || echo "eval \"\$($(command -v brew) shellenv)\"" >> "$HOME/.zprofile"
  ok "$(t install.homebrew)"
fi
# The Herdr app, its part chosen and not on this Mac: its own installer (releases.herdr.dev: the app in ~/Applications,
# herdr-app in ~/.local/bin), after a yes in a terminal; a no, or no terminal, names it for later and goes on
APP_INSTALLER=https://releases.herdr.dev/app/install.sh
if [ -z "$app" ] && of_parts app $parts; then
  warn "$(t install.app_missing)"
  if interactive && ask "$(t install.app_install_ask)" y; then
    /bin/sh -c "$(curl -fsSL "$APP_INSTALLER")" </dev/tty
    app=$(python3 "$DOT/lib/herdr_app.py" cli)
    [ -n "$app" ] && ok "$(t install.app_installed)" || warn "$(t install.app_install_failed)"
  fi
  [ -n "$app" ] || note "$(t install.app_install_later "curl -fsSL $APP_INSTALLER | sh")"
fi
if command -v claude >/dev/null 2>&1; then there+=("$(t install.claude)")
else missing+=("warn|$(t install.claude_missing)"); fi
command -v codex >/dev/null 2>&1 && there+=("$(t install.codex)") || missing+=("note|$(t install.codex_missing)")
has_ssh_key && there+=("$(t install.ssh_key)") || missing+=("note|$(t install.ssh_key_missing)")
[ -n "$(tailscale_bin)" ] && there+=("$(t install.tailscale)") || missing+=("note|$(t install.tailscale_missing)")
[ ${#there[@]} = 0 ] || have "$(joined "${there[@]}")"
[ ${#missing[@]} = 0 ] || for said in "${missing[@]}"; do "${said%%|*}" "${said#*|}"; done

step "$(t install.step_apps)"
# For this run only: no analytics, cleanup, upgrades on install, hints or list of new programs
export HOMEBREW_NO_ANALYTICS=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_INSTALL_UPGRADE=1 HOMEBREW_NO_ENV_HINTS=1 \
  HOMEBREW_NO_UPDATE_REPORT_NEW=1
# A program already on the Mac stays, whoever installed it: no second copy, no takeover of an app.
# What is missing is installed after a yes. Nothing is upgraded, except a Homebrew herdr that is too old.
HERDR_MIN=0.9.5
# Where a Brewfile program is on this Mac, or nothing: a command, an app, or the font
on_this_mac() {
  local app
  case $1 in
    ghostty)
      for app in /Applications/Ghostty.app "$HOME/Applications/Ghostty.app"; do
        [ "$(defaults read "$app/Contents/Info" CFBundleIdentifier 2>/dev/null)" = com.mitchellh.ghostty ] \
          && echo "$app" && return
      done ;;
    font-jetbrains-mono-nerd-font) ls -d "$HOME"/Library/Fonts/JetBrainsMono*NerdFont* 2>/dev/null | head -n 1 ;;
    git-delta) command -v delta ;;
    ripgrep) command -v rg ;;
    *) command -v "$1" ;;
  esac
}
# The herdr on PATH if it is not Homebrew's (its own installer, mise, a download), else nothing
foreign_herdr() {
  local found=${HERDR_BIN_PATH:-$(command -v herdr 2>/dev/null)}
  [ -n "$found" ] || return 0
  case "$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$found")" in
    */Cellar/herdr/*) ;;
    *) printf '%s\n' "$found" ;;
  esac
}
herdr_too_old() {
  local version; version=$("${HERDR_BIN_PATH:-herdr}" --version 2>/dev/null | awk '{ print $NF }')
  [ -n "$version" ] && python3 -c '
import sys
try:
    have, need = (tuple(int(part) for part in v.split(".")[:3]) for v in sys.argv[1:])
except ValueError:
    sys.exit(1)
sys.exit(0 if have < need else 1)' "$version" "$HERDR_MIN"
}
# Ghostty finds a herdr not from Homebrew only in ~/.local/bin, elsewhere it is named (mise's by its shim, which
# outlives a version's folder); Homebrew's, if there too, it finds first
foreign=; ! of_parts tui $parts || foreign=$(foreign_herdr)
if [ -n "$foreign" ]; then
  link=$foreign shim=${foreign%%/installs/*}/shims/herdr
  case "$foreign" in */mise/installs/*) [ -x "$shim" ] && link=$shim ;; esac
  case "$(dirname "$foreign")" in
    /opt/homebrew/bin|/usr/local/bin|"$HOME/.local/bin") ;;
    *) warn "$(t install.herdr_unseen "$link")" ;;                     # in full: the line runs as it is
  esac
  for other in $(type -ap herdr); do
    case "$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$other")" in
      */Cellar/herdr/*) warn "$(t install.herdr_twice "$other" "$foreign")"; break ;;
    esac
  done
fi
if [ "${HERDR_FOLD_NO_BREW:-}" = 1 ]; then
  skip "$(t install.apps_skipped)"
else
  apps=() formulae=() casks=() upgrade= later=
  while read -r kind name; do
    [ -n "$(on_this_mac "$name")" ] && continue
    apps+=("$name")
    case $kind in cask) casks+=("$name") ;; *) formulae+=("$name") ;; esac
  done < <(brew_lines $parts)
  of_parts tui $parts && [ -z "$foreign" ] && command -v herdr >/dev/null 2>&1 && herdr_too_old && upgrade=1
  if [ ${#apps[@]} = 0 ] && [ -z "$upgrade" ]; then
    have "$(t install.apps_there)"
  else
    [ ${#formulae[@]} = 0 ] || later="brew install ${formulae[*]}"
    [ ${#casks[@]} = 0 ] || later="${later:+$later && }brew install --cask ${casks[*]}"
    [ -z "$upgrade" ] || later="${later:+$later && }brew upgrade herdr"
    [ ${#apps[@]} = 0 ] || note "$(t install.apps_missing "$(joined "${apps[@]}")")"
    [ -z "$upgrade" ] || note "$(t install.herdr_old "$HERDR_MIN")"
    ask "$(t install.apps_ask)" y || { note "$(t install.apps_later "$later")"; exit 1; }
    { [ ${#formulae[@]} = 0 ] || brew install "${formulae[@]}"; } \
      && { [ ${#casks[@]} = 0 ] || brew install --cask "${casks[@]}"; } \
      || { warn "$(t install.brew_install_failed)"; exit 1; }
    if [ -z "$upgrade" ]; then :
    elif brew upgrade herdr; then ok "$(t install.herdr_upgraded "$HERDR_MIN")"
    else warn "$(t install.herdr_too_old "$HERDR_MIN")"
    fi
  fi
  [ -n "$foreign" ] && herdr_too_old && warn "$(t install.herdr_too_old_own "$HERDR_MIN")"
fi

step "$(t install.step_theme)"
# The choice sets the colors of the chosen parts: Ghostty, herdr and starship; herdr-fold's layout in the Herdr app
# (src/themes/apply.py). Default: the theme in use here (the TUI's, else the app's), or the package's.
THEMES="$DOT/src/themes"
theme_of() { python3 "$THEMES/apply.py" --current "$1" 2>/dev/null; }
current=$(python3 "$THEMES/apply.py" --current 2>/dev/null); theme=${current:-$(theme_of "$DOT/config/ghostty/config")}
# the preview in the browser (every theme with its app icon, this Mac's marked) and the list; once a theme is chosen,
# they and the question give way to its line. An update keeps the theme there is
if ! updating || [ -z "$current" ]; then
  listed=0
  if interactive; then
    preview=$(python3 "$THEMES/apply.py" --preview ${current:+"$current"})
    open "$preview" 2>/dev/null && note "$(t install.theme_preview)" && listed=1
    list=$(python3 "$THEMES/apply.py") && printf '%s\n' "$list" && listed=$((listed + $(grep -c . <<< "$list")))
  fi
  theme=$(prompt "$(t install.theme_ask)" "${theme:-1}")
  [ "$listed" = 0 ] || [ ! -t 1 ] || printf '\033[%dA\r\033[J' $((listed + 1))
fi
name=$(python3 "$THEMES/apply.py" --name "$theme" 2>/dev/null) && ok "$(t install.theme_set "$name")"
python3 "$THEMES/apply.py" --loading-colors "$theme" >/dev/null 2>&1   # the sheep in its colors from here on

step "$(t install.step_settings)"
# The installer's records in ~/.local/state/herdr-fold: docs/architecture.md. original/ and changed-<date>/ are never
# pruned, and a file prepared.txt lists stays even when the package drops it.
record="$state/installed.txt"; backup="$state/$(date +%Y%m%d-%H%M%S)"
changed="$state/changed-$(date +%Y%m%d-%H%M%S)"
# its owner's only: the backups hold the machine's own files; a copy keeps its file's mode too (cp -p)
mkdir -p "$state" && chmod 700 "$state"
# keep_installed REL — an installed file, before it is replaced or removed: one you may have changed since the install
# (it differs from what installed.sha256 recorded, or nothing was recorded of it) goes to changed-<date>/, which is
# never pruned; the package's earlier version to the dated backup
keep_installed() {
  local was; was=$(recorded_sum "$state" "$1")
  if [ -z "$was" ] || [ "$(sum_of "$HOME/$1")" != "$was" ]; then
    mkdir -p "$(dirname "$changed/$1")" && cp -p "$HOME/$1" "$changed/$1" \
      && saved "$(t files.changed_kept "$1" "$(shown "$changed/$1")")"
  else
    mkdir -p "$(dirname "$backup/$1")" && cp -p "$HOME/$1" "$backup/$1"
  fi
}
# herdr set up here already (its own config.toml, not one herdr-fold installed): what is there, then the question — add
# herdr-fold's to theirs (marked, every line of theirs stays), or replace theirs (kept, back on uninstall). Added once:
# not asked again.
herdr_config="$HOME/.config/herdr/config.toml"; config_mode=package
facts=; ! of_parts tui $parts || facts=$(plugin_facts)
if of_parts tui $parts && [ -f "$herdr_config" ] && ! grep -qxF .config/herdr/config.toml "$record" 2>/dev/null; then
  if grep -qxF '# >>> herdr-fold >>>' "$herdr_config"; then
    config_mode=add
  else
    section "$(t install.existing_herdr)"
    note "$(t install.existing_config)"
    theirs=$(printf '%s\n' "$facts" | cut -d'|' -f1 \
      | grep -vE '^(herdr-fold(\.(sessions-view|workspaces|tab-layout|sidebar))?)?$' \
      | paste -sd, - | sed 's/,/, /g')
    [ -z "$theirs" ] || note "$(t install.existing_plugins "$theirs")"
    case "${HERDR_FOLD_CONFIG:-}" in
      add|replace) config_mode=$HERDR_FOLD_CONFIG ;;
      *) if updating || ask "$(t install.config_add_ask)" y; then config_mode=add; else config_mode=replace; fi ;;
    esac
  fi
fi
: > "$record.new"
package_files $parts | while IFS='|' read -r src rel; do
  dst="$HOME/$rel"
  [ "$rel" = .config/herdr/config.toml ] && [ "$config_mode" = add ] && continue
  # missing from this copy of the package: the installed one stays (and stays on the record), never deleted for it
  [ -f "$DOT/$src" ] || { warn "$(t install.missing_from_package "$src")"; echo "$rel" >> "$record.new"; continue; }
  # what is there is saved first; one that cannot be is left as it is (on the record only if it was)
  recorded=; grep -qxF "$rel" "$record" 2>/dev/null && recorded=1
  if [ -L "$dst" ]; then
    # a link (to a dotfiles repo): the link itself is set aside, its target is never written through
    if [ -n "$recorded" ]; then aside="$changed/$rel"; else aside="$state/original/$rel"; fi
    if mkdir -p "$(dirname "$aside")" && mv "$dst" "$aside"; then saved "$(t install.original_set_aside "$rel")"
    else warn "$(t install.not_kept "$rel")"; [ -z "$recorded" ] || echo "$rel" >> "$record.new"; continue; fi
  elif [ -f "$dst" ] && ! cmp -s "$DOT/$src" "$dst"; then
    if [ -n "$recorded" ]; then
      keep_installed "$rel" || { warn "$(t install.not_kept "$rel")"; echo "$rel" >> "$record.new"; continue; }
    elif mkdir -p "$(dirname "$state/original/$rel")" && cp -p "$dst" "$state/original/$rel"; then
      saved "$(t install.original_set_aside "$rel")"
    else
      warn "$(t install.not_kept "$rel")"; continue
    fi
  fi
  mkdir -p "$(dirname "$dst")" && cp "$DOT/$src" "$dst"
  case "$dst" in *.sh|*/bin/*) chmod +x "$dst" ;; esac
  echo "$rel" >> "$record.new"
  if verbose; then ok "$(t install.file_installed "$rel")"; else progress "$rel"; fi
done
verbose || ok "$(t install.files_in_place "$(grep -c . "$record.new")")"
# Where this package is: the TUI's Ctrl+B, Shift+M (add_machine.py) runs its machines.sh
! of_parts tui $parts || printf '%s\n' "$DOT" > "$HOME/.config/herdr-fold/setup-folder"
# Put in place by an earlier install but no longer in the package: delete it, or restore the machine's original. An
# empty new record (an unreadable file list) deletes nothing: the earlier record stays.
[ -s "$record.new" ] || { rm -f "$record.new"; cp "$record" "$record.new" 2>/dev/null || : > "$record.new"; }
# What would be deleted (no original to restore) is listed and asked about first; kept, the next install asks again
dropped=$([ -f "$record" ] && grep -vxF -f "$record.new" "$record" | while IFS= read -r rel; do
  [ -n "$rel" ] && [ -f "$HOME/$rel" ] && [ ! -e "$state/original/$rel" ] && [ ! -L "$state/original/$rel" ] \
    && ! ai_session_file "$rel" && ! grep -qxF "$rel" "$state/prepared.txt" 2>/dev/null && echo "$rel"
done)
if [ -n "$dropped" ]; then
  # one file by its name, several in a folder by the folder; a single entry on the heading's line
  listing=$(printf '%s\n' "$dropped" | awk '{ dir = $0; sub("/[^/]*$", "", dir); n[dir]++; one[dir] = $0 }
    END { for (dir in n) print n[dir], (n[dir] == 1 ? one[dir] : dir) }' | sort -k 2 \
    | while read -r count rel; do
        if [ "$count" = 1 ]; then echo "~/$rel"; else printf '%s\n' "$(t install.dropped_folder "~/$rel" "$count")"; fi
      done)
  if [ "$(printf '%s\n' "$listing" | grep -c .)" = 1 ]; then skip "$(t install.dropped_heading) $listing"
  else skip "$(t install.dropped_heading)"; printf '%s\n' "$listing" | while IFS= read -r entry; do note "$entry"; done
  fi
  if updating || ask "$(t install.dropped_ask)" y; then removed=1
  else printf '%s\n' "$dropped" >> "$record.new"; skip "$(t install.dropped_kept)"; fi
fi
[ -f "$record" ] && grep -vxF -f "$record.new" "$record" | while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  if ai_session_file "$rel"; then skip "$(t install.ai_session_kept "$rel")"; continue; fi
  grep -qxF "$rel" "$state/prepared.txt" 2>/dev/null && continue
  dst="$HOME/$rel"
  if [ -f "$dst" ] && ! keep_installed "$rel"; then
    warn "$(t install.not_kept "$rel")"; echo "$rel" >> "$record.new"; continue
  fi
  if [ -f "$state/original/$rel" ] || [ -L "$state/original/$rel" ]; then
    mkdir -p "$(dirname "$dst")" && mv "$state/original/$rel" "$dst"
    ok "$(t install.original_restored "$rel")"
  elif [ -f "$dst" ]; then
    rm -f "$dst"; remove_empty_dirs "$(dirname "$dst")"
    verbose && ok "$(t install.dropped_deleted "$rel")"
  fi
done
[ -z "${removed:-}" ] || ok "$(t install.dropped_removed "$(shown "$backup")")"
mv "$record.new" "$record"
ls -d "$state"/[0-9]*-[0-9]* 2>/dev/null | sort -r | tail -n +4 | while IFS= read -r old; do rm -rf "$old"; done
if [ "$config_mode" = add ]; then
  # before the first add, as they were, with the originals; later, with herdr-fold's part, to the dated backup
  if grep -qxF '# >>> herdr-fold >>>' "$herdr_config"; then kept="$backup"; else kept="$state/original"; fi
  if ! { mkdir -p "$kept/.config/herdr" && cp -p "$herdr_config" "$kept/.config/herdr/config.toml"; }; then
    warn "$(t install.not_kept .config/herdr/config.toml)"
  elif out=$(python3 "$DOT/src/herdr_config.py" add "$DOT/config/herdr/config.toml" "$herdr_config"); then
    printf '%s\n' "$out" | summarize "$(t install.config_added)"
  else warn "$(t install.config_left "$out")"; fi
fi
if out=$(loading "$(t install.theme_setting)" python3 "$HOME/.config/herdr-fold/themes/apply.py" "$theme" $parts); then
  printf '%s\n' "$out" | summarize ""                      # step 3 named the theme: only what needs attention shows
else
  printf '%s\n' "$out"; warn "$(t install.theme_failed)"
fi
# What each installed file holds now (installed.sha256): the uninstaller sets a file changed since aside, never
# deletes it
( cd "$HOME" && while IFS= read -r rel; do [ -f "$rel" ] && shasum -a 256 "$rel"; done < "$record" ) \
  > "$state/installed.sha256"
[ -z "$this_version" ] || printf '%s\n' "$this_version" > "$state/version"   # the next install names it

step "$(t install.step_prompt)"
# The herdr panes' environment (pane-env.sh), in herdr panes only: one marked block in ~/.zshrc, replaced on every run.
# An if, so a shell outside herdr (or without the file) ends it with a success status, not a red first prompt.
if of_parts tui $parts; then
  before=$(mktemp); cp "$HOME/.zshrc" "$before" 2>/dev/null
  pane_env='if [ -n "$HERDR_PANE_ID" ] && [ -f "$HOME/.config/herdr-fold/pane-env.sh" ]; '
  pane_env+='then . "$HOME/.config/herdr-fold/pane-env.sh"; fi'
  marked_block "$HOME/.zshrc" "# written by herdr-fold's install.sh — replaced on every run" "$pane_env"
  if verbose; then                            # a part of the status line's step: said with every part only
    if cmp -s "$HOME/.zshrc" "$before"; then have "$(t install.pane_env)"; else ok "$(t install.pane_env)"; fi
  fi
  rm -f "$before"
fi
# Claude Code's status line: herdr-fold's; an own one is saved first, to the backups that are never pruned
# (original/); a damaged settings.json is left alone, and so is the status line chosen to be your own (the list below
# says so)
python3 "$HOME/.config/herdr-fold/statusline_setup.py" --claude-settings "$state/original" \
  'python3 "$HOME/.config/herdr-fold/statusline.py"' >/dev/null
case $? in
  0|3) ;;                                       # set, or left: the line below says it
  2) saved "$(t status.claude_replaced "$(shown "$state/original")")" ;;
  *) warn "$(t status.claude_unreadable "$(shown "$HOME/.claude/settings.json")")" ;;
esac
# What goes in the status line next to the model (one checkbox list, a group for Claude and one for Codex); without
# questions, the defaults
if interactive && ! updating; then
  python3 "$HOME/.config/herdr-fold/statusline_setup.py" || warn "$(t install.statusline_failed)"
else
  python3 "$HOME/.config/herdr-fold/statusline_setup.py" --apply
fi
# Claude runs the status line only in projects it trusts: offer to trust those of this Mac's Claude panes it does not
# (never the home folder or above), each shown under ~ and without control characters; a yes trusts exactly those shown
untrusted=; ! of_parts tui $parts || untrusted=$(python3 "$HOME/.config/herdr-fold/claude_trust.py" list 2>/dev/null)
if [ -n "$untrusted" ] && ! updating; then
  note "$(t install.trust_intro)"
  while IFS= read -r folder; do note "$(shown "$folder" | LC_ALL=C tr -d '\000-\037\177')"; done <<< "$untrusted"
  if ask "$(t install.trust_ask)" n; then
    if out=$(printf '%s\n' "$untrusted" | python3 "$HOME/.config/herdr-fold/claude_trust.py" trust); then
      ok "$(t install.trust_done)"
    else warn "$(t install.trust_failed "$out")"; fi
  fi
fi

step "$(t install.step_plugins)"
# Deliberately NO background service: herdr starts and stops together with Ghostty. On reopen, herdr restores
# the layout, and through the integration Claude/Codex continue the same conversation.
# The plugins this installer put there (plugins.txt): the uninstaller takes out exactly these
plugins="$state/plugins.txt"; : > "$plugins.new"
# an earlier run's take-over stays on the record, but the retired Tab Layout's: it has no way back
grep '^taken:' "$plugins" 2>/dev/null | grep -vxF taken:herdr-fold.tab-layout >> "$plugins.new"
linked=() hooked=()                           # said in one line each at the end of the step
# herdr's own part, with the TUI only: herdr-fold's plugins, then herdr's hooks into Claude and Codex
if of_parts tui $parts; then
  # herdr-sidebar of your own: it does what herdr-fold's sidebar does, so it is named, and left as it is
  printf '%s\n' "$facts" | grep -q '^herdr-sidebar|' && warn "$(t install.herdr_sidebar_too)"
  take_over herdr-fold.sidebar "$HOME/.config/herdr-fold/plugins/sidebar"
  if herdr plugin link "$HOME/.config/herdr-fold/plugins/sidebar" >/dev/null 2>&1; then
    echo herdr-fold.sidebar >> "$plugins.new"; linked+=("$(t install.plugin_sidebar)")
  else
    warn "$(t install.sidebar_failed "$(shown "$HOME/.config/herdr-fold/plugins/sidebar")")"
  fi
  # herdr-fold's plugins: one of someone's own that does the same is named first; with herdr set up already, each is a
  # question — its default the last answer, so one said no to stays unlinked unless you say yes
  doing() {   # doing tab.created|agent.view.set: the ids of the plugins not herdr-fold's that do it
    printf '%s\n' "$facts" | awk -F'|' -v does="$1" \
      '$1 !~ /^herdr-fold(\.(sidebar|sessions-view|workspaces|tab-layout))?$/ && index($3, does) { print $1 }'
  }
  wanted() {   # wanted <id> <question> [<the id it had before>]
    if grep -qxF -e "declined:$1" -e "declined:${3:-$1}" "$plugins" 2>/dev/null; then   # a no stays
      ! updating && ask "$2" n && return 0
    elif [ "$config_mode" = package ] || updating || ask "$2" y; then return 0; fi
    echo "declined:$1" >> "$plugins.new"
    return 1
  }
  for other in $(doing agent.view.set); do
    warn "$(t install.plugin_like_sessions "$other")"
  done
  if wanted herdr-fold.sessions-view "$(t install.sessions_ask)"; then
    take_over herdr-fold.sessions-view "$HOME/.config/herdr-fold/plugins/sessions-view"
    if herdr plugin link "$HOME/.config/herdr-fold/plugins/sessions-view" >/dev/null 2>&1; then
      echo herdr-fold.sessions-view >> "$plugins.new"
      # relinking makes herdr drop the plugin's view — so apply it again right away (if herdr is running)
      herdr plugin action invoke apply --plugin herdr-fold.sessions-view >/dev/null 2>&1
      linked+=("$(t install.plugin_sessions)")
    else
      warn "$(t install.sessions_failed)"
    fi
  else
    herdr plugin unlink herdr-fold.sessions-view >/dev/null 2>&1
    skip "$(t install.plugin_declined herdr-fold.sessions-view)"
  fi
  # an earlier install's Tab Layout, retired (a new tab's column is the sidebar's now, the rest Workspaces'): off herdr
  # before Workspaces comes (herdr's marketplace copy uninstalled), its state Workspaces'; one herdr keeps (it is not
  # running) stays on the record for a later run
  case $(printf '%s\n' "$facts" | awk -F'|' '$1 == "herdr-fold.tab-layout" { print $4 }') in
    "") off= ;;
    github) off="herdr plugin uninstall herdr-fold.tab-layout" ;;
    *) off="herdr plugin unlink herdr-fold.tab-layout" ;;
  esac
  if [ -z "$off" ]; then :
  elif $off >/dev/null 2>&1; then ok "$(t install.tab_layout_retired)"
  else warn "$(t install.tab_layout_left "$off")"; echo herdr-fold.tab-layout >> "$plugins.new"; fi
  retire_tab_layout
  for other in $(doing tab.created); do warn "$(t install.plugin_like_workspaces "$other")"; done
  if wanted herdr-fold.workspaces "$(t install.workspaces_ask)" herdr-fold.tab-layout; then
    take_over herdr-fold.workspaces "$HOME/.config/herdr-fold/plugins/workspaces"
    if herdr plugin link "$HOME/.config/herdr-fold/plugins/workspaces" >/dev/null 2>&1; then
      echo herdr-fold.workspaces >> "$plugins.new"
      linked+=("$(t install.plugin_workspaces)")
    else
      warn "$(t install.workspaces_failed)"
    fi
  else
    herdr plugin unlink herdr-fold.workspaces >/dev/null 2>&1; skip "$(t install.plugin_declined herdr-fold.workspaces)"
  fi
  # herdr ↔ Claude / Codex: recorded (plugins.txt) when this installer put it there — not there before, or
  # herdr-fold's already
  integration() {
    herdr integration install "$1" >/dev/null 2>&1 || return 1
    if grep -qxF "integration:$1" "$plugins" 2>/dev/null || [ "$2" = "$1: not installed" ]; then
      echo "integration:$1" >> "$plugins.new"
    fi
  }
  was() { herdr integration status 2>/dev/null | sed -n "s/^\($1: not installed\).*/\1/p"; }
  integration claude "$(was claude)" && hooked+=("$(t install.claude)") \
    || warn "$(t install.claude_integration_failed)"
  if ! command -v codex >/dev/null 2>&1; then
    skip "$(t install.codex_not_found)"
  elif [ ! -d "$HOME/.codex" ]; then
    # herdr can only hook it up once Codex has run at least once (and created ~/.codex)
    skip "$(t install.codex_not_run)"
  else
    integration codex "$(was codex)" && hooked+=("$(t install.codex)") \
      || warn "$(t install.codex_integration_failed)"
  fi
fi
# herdr-fold in the Herdr app (herdr's desktop app), its part chosen: its mod, layout and keys; a running app shows
# the layout at once. An update of the TUI alone, the app on this Mac and never asked about: asked once
app_wanted() {
  of_parts app $parts && return 0
  if [ -z "${HERDR_FOLD_PARTS:-}" ] && updating && ! grep -qxF declined:herdr-fold.app "$plugins" 2>/dev/null \
    && ask "$(t install.app_ask)" y; then                     # HERDR_FOLD_PARTS answers it as it does the first
    parts="$parts app"; return 0
  fi
  echo declined:herdr-fold.app >> "$plugins.new"
  return 1
}
if [ -n "$app" ] && app_wanted; then
  python3 "$DOT/lib/herdr_app.py" install "$DOT" "$theme"; rc=$?
  app_home=$(python3 "$DOT/lib/herdr_app.py" home)
  case $rc in
    0|3)
      echo herdr-fold.app >> "$plugins.new"; ok "$(t install.app_done)"
      [ $rc = 0 ] || warn "$(t install.app_keys_unread "$(shown "$app_home/keys.json")")"
      out=$("$app" check "$app_home/mods/herdr-fold" 2>&1) || warn "$(t install.app_check_failed "${out##*$'\n'}")"
      for editor in gpui-kit.d.ts herdr.d.ts jsconfig.json; do    # what the check writes for an editor beside it
        rm -f "$app_home/mods/herdr-fold/$editor"
      done
      "$app" status >/dev/null 2>&1 && "$app" do layout.switch --name herdr-fold >/dev/null 2>&1 \
        && note "$(t install.app_layout)" ;;
    4) warn "$(t install.app_not_herdr_folds "$(shown "$app_home/mods/herdr-fold")")" ;;
    *) warn "$(t install.app_failed)" ;;
  esac
fi
mv "$plugins.new" "$plugins"
[ ${#linked[@]} = 0 ] || ok "$(t install.plugins "$(joined "${linked[@]}")")"
[ ${#hooked[@]} = 0 ] || ok "$(t install.integrations "$(joined "${hooked[@]}")")"

# Tabs left without the right-hand column (e.g. a workspace's first tab) get it now, if herdr is running; the remote
# machines' tabs in step 8
! of_parts tui $parts || python3 "$HOME/.config/herdr-fold/restore_panes.py" 2>/dev/null

step "$(t install.step_github)"
# To push (the sidebar's Sync / push, Cmd+Shift+C) the machine has to be signed in to GitHub. The installer never asks
# for or stores a token: GitHub's own browser sign-in (gh auth login --web) keeps the credential in the macOS Keychain
# (revocable any time in your GitHub account), and git pushes through it (gh auth setup-git).
if ! command -v gh >/dev/null 2>&1; then
  skip "$(t install.gh_missing)"
elif gh auth status --hostname github.com >/dev/null 2>&1; then
  have "$(t install.github_account "$(gh api user --jq .login 2>/dev/null || echo "$(t install.github_signed_in)")")"
  git config --global --get-regexp '^credential\..*github\.com.*\.helper$' 2>/dev/null \
    | grep -q 'gh auth git-credential' \
    || { ! updating && ask "$(t install.git_push_ask)" y && gh auth setup-git --hostname github.com \
         && record_outside github-git && ok "$(t install.git_push_ok)"; }
elif interactive && ! updating && ask "$(t install.github_login_ask)" y; then
  if gh auth login --hostname github.com --git-protocol https --web </dev/tty && record_outside github-sign-in \
     && gh auth setup-git --hostname github.com && record_outside github-git; then
    ok "$(t install.github_login_ok "$(gh api user --jq .login 2>/dev/null || echo "$(t install.github_signed_in)")")"
  else
    warn "$(t install.github_login_failed)"
  fi
else
  skip "$(t install.github_later)"
fi
# Commit author: only if not set yet — an existing name and email are never changed. Under GitHub's sign-in its login
# and noreply address are offered: a commit's address goes public with it, and a real one shows to anyone
if [ -n "$(git config --global user.name)" ] && [ -n "$(git config --global user.email)" ]; then
  have "$(t install.git_author "$(git config --global user.name)" "$(git config --global user.email)")"
elif interactive && ! updating; then
  login=; noreply=
  if command -v gh >/dev/null 2>&1 && gh auth status --hostname github.com >/dev/null 2>&1; then
    login=$(gh api user --jq .login 2>/dev/null); id=$(gh api user --jq .id 2>/dev/null)
    [ -n "$login" ] && [ -n "$id" ] && noreply="$id+$login@users.noreply.github.com"
  fi
  [ -n "$(git config --global user.name)" ] || { name=$(prompt "$(t install.git_author_name)" "$login")
    [ -z "$name" ] || { git config --global user.name "$name" && record_outside git-author; }; }
  [ -n "$(git config --global user.email)" ] || { mail=$(prompt "$(t install.git_author_email)" "$noreply")
    [ -z "$mail" ] || { git config --global user.email "$mail" && record_outside git-author; }; }
  [ -n "$(git config --global user.name)" ] && [ -n "$(git config --global user.email)" ] \
    && ok "$(t install.git_author "$(git config --global user.name)" "$(git config --global user.email)")"
else
  skip "$(t install.git_author_later)"
fi

step "$(t install.step_machines)"
if [ "${HERDR_FOLD_NO_MACHINES:-}" = 1 ]; then
  skip "$(t install.machines_skipped)"
elif [ -z "$(python3 "$DOT/src/parts.py" "$state")" ]; then     # the app chosen and not on this Mac: nothing set up
  skip "$(t install.machines_no_part)"
else
  # new machines: from ~/.ssh/config, the Tailscale network or an address typed in — a question each (Ctrl+B, Shift+M
  # asks the same later)
  updating || "$DOT/machines.sh" pick || skip "$(t install.machines_later)"   # an update looks for no new one
  # Every machine on the list — the ones connected earlier too — gets this version, and is connected if it isn't yet
  "$DOT/machines.sh" add || warn "$(t install.machines_failed)"
fi

step "$(t install.step_done)"
# a herdr upgraded by this run (or earlier) while the background one keeps the old version: hand over, never stop
versions=; ! of_parts tui $parts || versions=$(herdr status 2>/dev/null | awk '
  /^client:/ { s = "c" } /^server:/ { s = "s" } /^  status:/ { up = $2 } /^  version:/ { v[s] = $2 }
  END { if (up == "running" && v["c"] != v["s"]) print v["c"], v["s"] }')
if [ -n "$versions" ]; then set -- $versions; warn "$(t install.handoff "$1" "$2")"; fi
warnings=$(grep -c . "$HERDR_FOLD_WARNINGS")
if [ "$warnings" = 0 ]; then ok "$(t install.finished "$this_version")"
else warn "$(t install.finished_warnings "$this_version" "$warnings")"; fi
# what to do next: open Ghostty, or reopen it (started from it, or it is open) for the settings, the theme, its icon
if of_parts tui $parts; then
  if ghostty_open; then note "$(t install.reopen_ghostty)"; else note "$(t install.open_ghostty)"; fi
  note "$(t install.next_steps)"
fi
! of_parts app $parts || [ -z "$app" ] || "$app" status >/dev/null 2>&1 || note "$(t install.open_app)"
