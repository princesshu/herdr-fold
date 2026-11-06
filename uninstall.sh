#!/bin/bash
# herdr-fold uninstaller: takes off this Mac what install.sh put there, by its records, the TUI, the Herdr app or both
# (what they share goes with the last); never AI conversations, herdr's own data or Homebrew programs. Usage:  cd <the
# herdr-fold folder> && ./uninstall.sh (HERDR_FOLD_YES=1: no question; HERDR_FOLD_PARTS=tui|app|both). docs/uninstall.md
set -u
cd "$(dirname "$0")" || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
state="$HOME/.local/state/herdr-fold"; record="$state/installed.txt"
changed="$state/changed-$(date +%Y%m%d-%H%M%S)"

[ -f "$record" ] || { note "$(t uninstall.nothing)"; exit 0; }
# The parts it takes off: both installed, the question which (the default both); one, the question as before.
# HERDR_FOLD_PARTS answers either. What both share goes with the last part (last)
had=$(python3 "$DOT/src/parts.py" "$state" | xargs); had=${had:-tui}      # no part on the record: an earlier TUI's
off=$(parts_of "${HERDR_FOLD_PARTS:-}")
if [ -n "${HERDR_FOLD_PARTS:-}" ]; then
  [ -n "$off" ] || { note "$(t uninstall.parts_unknown "$HERDR_FOLD_PARTS")"; exit 0; }
elif [ "$had" = "tui app" ]; then
  if interactive; then
    printf '   1. %s\n   2. %s\n   3. %s\n' "$(t install.parts_tui)" "$(t install.parts_app)" \
      "$(t uninstall.parts_both)"
  fi
  answer=$(prompt "$(t uninstall.parts_ask)" 3); off=$(parts_of "$answer")
  [ -n "$off" ] || { note "$(t uninstall.parts_unknown "$answer")"; exit 0; }
else
  ask "$(t uninstall.ready)" y || exit 0
  off=$had
fi
off=$(for part in $off; do ! of_parts "$part" $had || echo "$part"; done | xargs)
[ -n "$off" ] || { note "$(t uninstall.part_not_there "$HERDR_FOLD_PARTS")"; exit 0; }
left=$(for part in $had; do of_parts "$part" $off || echo "$part"; done | xargs)
last=; [ -n "$left" ] || last=1

step "$(t uninstall.step_herdr)"
# herdr-fold in the Herdr app: a running app leaves its layout, the terminals the mod started for tabs end (its core
# runs then; asking a stopped one would start it) and it closes for the moment herdr-fold's shared values go (it holds
# them and writes them back), then the mod, the layout and the keys go
app_off() {
  local app status closed=; app=$(python3 "$DOT/lib/herdr_app.py" cli)
  if [ -n "$app" ] && status=$("$app" status 2>/dev/null); then
    grep -q '"layout": *"herdr-fold"' <<<"$status" && "$app" do layout.switch --name main >/dev/null 2>&1
    python3 "$DOT/lib/herdr_app.py" end-terminals
    note "$(t uninstall.app_closing)"
    if python3 "$DOT/lib/herdr_app.py" close; then closed=1
    else warn "$(t uninstall.app_still_open "$(shown "$(python3 "$DOT/lib/herdr_app.py" home)/shared.json")")"; fi
  fi
  python3 "$DOT/lib/herdr_app.py" uninstall "$DOT" && ok "$(t uninstall.app_off)"
  [ -z "$closed" ] || python3 "$DOT/lib/herdr_app.py" open || warn "$(t uninstall.app_not_reopened)"
}
# the plugins and integrations first: a running herdr then calls nothing that is about to go. A plugin herdr no longer
# has is left alone (its list answers without a running herdr); one it does not take off (only a running herdr takes
# a plugin off) is named with the command that does it. herdr's are the TUI's, herdr-fold.app the app's
if [ -f "$state/plugins.txt" ]; then
  linked=; ! of_parts tui $off || linked=$(herdr plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    print("\n".join(p.get("plugin_id", "") for p in json.load(sys.stdin)["result"]["plugins"]))
except (ValueError, KeyError, TypeError):
    pass')
  while IFS= read -r id; do
    if [ "$id" = herdr-fold.app ]; then of_parts app $off || continue; else of_parts tui $off || continue; fi
    case "$id" in
      taken:*)        # installed alone from herdr's marketplace before, the installer's took its place: the way back
        taken=${id#taken:} back="herdr plugin install princesshu/herdr-fold/src/plugins/${id#taken:herdr-fold.}"
        note "$(t uninstall.taken_back "$taken" "$back")"
        continue ;;
      herdr-fold.app) app_off; continue ;;
      herdr-fold.*) cmd="herdr plugin unlink $id" ;;
      integration:*) cmd="herdr integration uninstall ${id#integration:}" ;;
      *) continue ;;
    esac
    case "$id" in integration:*) ;; *) grep -qxF "$id" <<< "$linked" || continue ;; esac
    if $cmd >/dev/null 2>&1; then ok "$(t uninstall.plugin_removed "$id")"
    elif [ "${id#integration:}" != "$id" ]; then warn "$(t uninstall.integration_left "${id#integration:}" "$cmd")"
    else warn "$(t uninstall.plugin_left "$id" "$cmd")"; fi
  done < "$state/plugins.txt"
fi
# the machines herdr-fold added to the Herdr app leave it (their terminals keep running there)
if of_parts app $off; then
  while IFS= read -r name; do remove_from_app "$name"; done < <(cat "$APP_MACHINES" 2>/dev/null)
  rm -f "$APP_MACHINES"
fi
# herdr-fold's whole environment from herdr's marketplace (the plugin that offered the installer), with the last part:
# on no record, as the installer did not put it there, and herdr-fold's all the same
if [ -n "$last" ] && herdr plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    sys.exit(0 if any(p.get("plugin_id") == "herdr-fold" for p in json.load(sys.stdin)["result"]["plugins"]) else 1)
except (ValueError, KeyError, TypeError):
    sys.exit(1)'; then
  if herdr plugin uninstall herdr-fold >/dev/null 2>&1; then ok "$(t uninstall.plugin_removed herdr-fold)"
  else warn "$(t uninstall.plugin_left herdr-fold "herdr plugin uninstall herdr-fold")"; whole_left=1; fi
fi

step "$(t uninstall.step_files)"
tui=; ! of_parts tui $off || tui=1
# Claude's status line first, with the last part: herdr-fold's runs a script that is about to go
if [ -n "$last" ]; then
  python3 "$DOT/src/statusline_setup.py" --claude-restore "$state/original"
  case $? in
    0) ok "$(t uninstall.claude_status_line)" ;;
    1) warn "$(t status.claude_unreadable "$HOME/.claude/settings.json")" ;;
  esac
fi
# what a Python that writes its cache in place left next to the package's scripts
[ -d "$HOME/.config/herdr-fold" ] && find "$HOME/.config/herdr-fold" -name __pycache__ -type d -prune -exec rm -rf {} +
if [ -n "$tui" ]; then
  # the app icon the theme drew for Ghostty: the file its config includes, and the icons (Ghostty's own comes back)
  rm -f "$HOME/.config/ghostty/herdr-fold-icon" "$HOME/.config/ghostty"/.herdr-fold-icon.*.tmp  # .*.tmp: cut short
  rm -rf "$state/ghostty-icon"
fi
# The record's files: all of them with the last part; with the TUI alone, those the app does not share (a line
# files.txt does not name, a config, is the TUI's); with the app alone, none (its own are in the Herdr app's folder)
shared=; [ -n "$last" ] || shared=$(package_files app | cut -d'|' -f2)
if [ -n "$tui$last" ]; then
  removed=0
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    ai_session_file "$rel" && continue
    grep -qxF "$rel" <<< "$shared" && continue                          # the app's too: it stays with the app
    grep -qxF "$rel" "$state/prepared.txt" 2>/dev/null && continue       # another Mac's prepare still uses it
    dst="$HOME/$rel"
    if [ -f "$dst" ] && [ ! -L "$dst" ] && [ "$(sum_of "$dst")" = "$(recorded_sum "$state" "$rel")" ]; then
      rm -f "$dst"; removed=$((removed + 1))
    elif [ -e "$dst" ] || [ -L "$dst" ]; then                             # yours since the install: kept, never deleted
      if mkdir -p "$(dirname "$changed/$rel")" && mv "$dst" "$changed/$rel"; then
        saved "$(t files.changed_kept "$rel" "$(shown "$changed/$rel")")"
      else
        warn "$(t uninstall.not_kept "$rel")"; continue                   # nor is the original put over it
      fi
    fi
    if [ -f "$state/original/$rel" ] || [ -L "$state/original/$rel" ]; then
      mkdir -p "$(dirname "$dst")" && mv "$state/original/$rel" "$dst" && ok "$(t uninstall.restored "$rel")"
    fi
    remove_empty_dirs "$(dirname "$dst")"
  done < "$record"
  ok "$(t uninstall.removed "$removed")"
fi
if [ -n "$tui" ]; then
  if grep -qxF '# >>> herdr-fold >>>' "$HOME/.zshrc" 2>/dev/null; then
    remove_marked_block "$HOME/.zshrc" && ok "$(t uninstall.zshrc)"
  fi
  if grep -qxF '# >>> herdr-fold >>>' "$HOME/.config/herdr/config.toml" 2>/dev/null; then
    if out=$(python3 "$DOT/src/herdr_config.py" strip "$HOME/.config/herdr/config.toml"); then
      ok "$(t uninstall.config_stripped)"
    else warn "$out"; fi
  fi
fi
# This Mac's state (the machine list and the private word list stay: written by you), and the sidebar plugin's: its
# own with the TUI (the theme's colors, the column, the panels, handovers, previews, issues), with the last part what
# the app shares (the settings, which hold the linked issues, the archived conversations and their index)
[ -z "$tui" ] || rm -f "$HOME/.config/herdr-fold/setup-folder"
[ -z "$last" ] || rm -f "$HOME/.config/herdr-fold/statusline.json"
remove_empty_dirs "$HOME/.config/herdr-fold"
sidebar_state="$HOME/.local/state/herdr/plugins/herdr-fold.sidebar"
[ -z "$tui" ] || rm -f "$sidebar_state/colors.json" "$sidebar_state/column.json" "$sidebar_state/panels.json" \
  "$sidebar_state"/resume-*.json "$sidebar_state"/seed-*.json "$sidebar_state"/preview-*.json \
  "$sidebar_state"/issues-*.json
[ -z "$last" ] || rm -f "$sidebar_state/settings.json" "$sidebar_state/conversations.json" \
  "$sidebar_state/conversation-index.json" "$sidebar_state"/.*.tmp           # .*.tmp: a write cut short
rmdir "$sidebar_state" 2>/dev/null                                  # only when nothing else is in it
# the empty folders herdr keeps of the plugins taken off above (the conversation names stay); with the last part, the
# whole environment's marks once it is off (left on, it would offer the installer again on herdr's start)
[ -z "$last" ] || [ -n "${whole_left:-}" ] || rm -f "$HOME/.local/state/herdr/plugins/herdr-fold"/offered-*
drop_plugin_folders ${last:+herdr-fold} ${tui:+herdr-fold.sidebar herdr-fold.sessions-view herdr-fold.tab-layout}
[ -z "$tui" ] || herdr server reload-config >/dev/null 2>&1         # a running herdr drops herdr-fold's keys

if [ -n "$last" ]; then
  # The records, the loading colors and earlier versions go; anything of yours stays and is named with where it is:
  # the conversation names, the machine list, the private word list, outside.txt (named, then removed), a file changed
  # since the install, an original that did not go back, another Mac's prepare record.
  rm -rf "$state"/[0-9]*-[0-9]*
  rm -f "$record" "$state/installed.sha256" "$state/version" "$state/plugins.txt" "$state/loading-colors.txt" \
    "$state"/.loading-colors.txt.*.tmp
  [ -d "$state/original" ] && find "$state/original" -depth -type d -empty -delete
  names="$HOME/.local/state/herdr/plugins/herdr-fold.sessions-view/names.json"
  [ -f "$names" ] && note "$(t uninstall.kept_names "$(shown "$names")")"
  fold="$HOME/.config/herdr-fold"
  [ -f "$MACHINE_LIST" ] && note "$(t uninstall.kept_machine_list "$(shown "$MACHINE_LIST")")"
  [ -f "$fold/private-words.txt" ] && note "$(t uninstall.kept_private_words "$(shown "$fold/private-words.txt")")"
  [ -n "$(ls -A "$fold" 2>/dev/null | grep -vxE 'machines\.txt|private-words\.txt')" ] \
    && note "$(t uninstall.kept "$(shown "$fold")")"
  outside="$state/outside.txt"
  if [ -f "$outside" ]; then
    grep -qxF ssh-key "$outside" && note "$(t uninstall.kept_ssh_key)"
    hosts=$(sed -n 's/^known-host //p' "$outside" | paste -sd, - | sed 's/,/, /g')
    [ -n "$hosts" ] && note "$(t uninstall.kept_host_keys "$hosts")"
    grep -qxF github-sign-in "$outside" && note "$(t uninstall.kept_github)"
    grep -qxF github-git "$outside" && note "$(t uninstall.kept_github_git)"
    grep -qxF git-author "$outside" && note "$(t uninstall.kept_git_author)"
    rm -f "$outside"
  fi
  remove_empty_dirs "$state"
  [ -e "$state" ] && note "$(t uninstall.kept "$(shown "$state")")"
elif [ -n "$tui" ]; then
  # The app stays, and the records it needs: the shared files' lines and sums, its plugin line
  grep -xF -f <(printf '%s\n' "$shared") "$record" > "$record.new"; mv "$record.new" "$record"
  awk 'NR == FNR { kept[$0]; next } { rel = $0; sub(/^[^ ]+  /, "", rel) } rel in kept' "$record" \
    "$state/installed.sha256" > "$state/installed.sha256.new" 2>/dev/null
  mv "$state/installed.sha256.new" "$state/installed.sha256"
  grep -xF herdr-fold.app "$state/plugins.txt" > "$state/plugins.txt.new"
  mv "$state/plugins.txt.new" "$state/plugins.txt"
else
  # The TUI stays, with its records: the app's line goes, a no to it in its place (an update then does not ask again)
  { grep -vxF -e herdr-fold.app -e declined:herdr-fold.app "$state/plugins.txt"; echo declined:herdr-fold.app; } \
    > "$state/plugins.txt.new"
  mv "$state/plugins.txt.new" "$state/plugins.txt"
fi
# the Brewfile's programs no part left uses that Homebrew has (a herdr from its own installer is not Homebrew's to
# remove): all of them with the last part, the TUI's alone with the TUI
going=; if [ -n "$last" ]; then going=$(brew_lines); elif [ -n "$tui" ]; then
  going=$(brew_lines tui | grep -vxF -f <(brew_lines app)); fi
homebrews() {   # homebrews brew|cask
  local have; have=$(brew list --"$([ "$1" = cask ] && echo cask || echo formula)" -1 2>/dev/null)
  printf '%s\n' "$going" | sed -n "s/^$1 //p" | while IFS= read -r name; do
    printf '%s\n' "$have" | grep -qxF "$name" && printf '%s\n' "$name"
  done | paste -sd' ' -
}
if [ -n "$going" ]; then
  command -v brew >/dev/null 2>&1 || brew_env
  formulae=$(homebrews brew) casks=$(homebrews cask) hint=
  [ -z "$formulae" ] || hint="brew uninstall $formulae"
  [ -z "$casks" ] || hint="${hint:+$hint && }brew uninstall --cask $casks"
  [ -z "$hint" ] || note "$(t uninstall.brew "$hint")"
fi
machines=$(awk -F'|' '!/^[[:space:]]*(#|$)/ { gsub(/^[ \t]+|[ \t]+$/, "", $1); print $1 }' "$MACHINE_LIST" 2>/dev/null \
  | paste -sd, - | sed 's/,/, /g')
if [ -n "$machines" ]; then
  if [ -n "$last" ]; then note "$(t uninstall.machines "$machines")"
  elif [ -n "$tui" ]; then note "$(t uninstall.machines_herdr "$machines")"; fi
fi
if [ -z "$last" ]; then
  if [ -n "$tui" ]; then ok "$(t uninstall.part_off_tui)"; else ok "$(t uninstall.part_off_app)"; fi
  exit 0
fi
ok "$(t uninstall.done)"
# Last, as the uninstaller may run from it and reads its texts there: the package kept for herdr's marketplace copy,
# marked as the installer's own (a folder of someone's by that name stays)
for kept in "$HOME/.local/share/herdr-fold" "$HOME/.local/share/herdr-fold.new" "$HOME/.local/share/herdr-fold.old"; do
  if [ -e "$kept/.kept-by-herdr-fold" ]; then rm -rf "$kept"; fi
done
