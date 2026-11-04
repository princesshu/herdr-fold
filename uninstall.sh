#!/bin/bash
# herdr-fold uninstaller: takes off this Mac what install.sh put there, by its records; never AI conversations, herdr's
# own data or Homebrew programs. Usage:  cd <the herdr-fold folder> && ./uninstall.sh (HERDR_FOLD_YES=1: no question);
# from herdr's marketplace the folder is ~/.local/share/herdr-fold. What goes and what stays: docs/uninstall.md.
set -u
cd "$(dirname "$0")" || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
state="$HOME/.local/state/herdr-fold"; record="$state/installed.txt"
changed="$state/changed-$(date +%Y%m%d-%H%M%S)"

[ -f "$record" ] || { note "$(t uninstall.nothing)"; exit 0; }
ask "$(t uninstall.ready)" y || exit 0

step "$(t uninstall.step_herdr)"
# herdr-fold in the Herdr app: a running app leaves its layout first and the terminals the mod started for tabs end
# (its core runs then; asking a stopped one would start it), then the mod, the layout and the keys go
app_off() {
  local app status; app=$(python3 "$DOT/lib/herdr_app.py" cli)
  if [ -n "$app" ] && status=$("$app" status 2>/dev/null); then
    grep -q '"layout": *"herdr-fold"' <<<"$status" && "$app" do layout.switch --name main >/dev/null 2>&1
    python3 "$DOT/lib/herdr_app.py" end-terminals
  fi
  python3 "$DOT/lib/herdr_app.py" uninstall "$DOT" && ok "$(t uninstall.app_off)"
}
# the plugins and integrations first: a running herdr then calls nothing that is about to go. A plugin herdr no longer
# has is left alone (its list answers without a running herdr); one it does not take off (only a running herdr takes
# a plugin off) is named with the command that does it
if [ -f "$state/plugins.txt" ]; then
  linked=$(herdr plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    print("\n".join(p.get("plugin_id", "") for p in json.load(sys.stdin)["result"]["plugins"]))
except (ValueError, KeyError, TypeError):
    pass')
  while IFS= read -r id; do
    case "$id" in
      taken:*)        # installed alone from herdr's marketplace before, the installer's took its place: the way back
        taken=${id#taken:} back="herdr plugin install princesshu/herdr-fold/src/plugins/${id#taken:herdr-fold.}"
        note "$(t uninstall.taken_back "$taken" "$back")"
        continue ;;
      herdr-fold.app) app_off; continue ;;
      herdr-fold.*) off="herdr plugin unlink $id" ;;
      integration:*) off="herdr integration uninstall ${id#integration:}" ;;
      *) continue ;;
    esac
    case "$id" in integration:*) ;; *) grep -qxF "$id" <<< "$linked" || continue ;; esac
    if $off >/dev/null 2>&1; then ok "$(t uninstall.plugin_removed "$id")"
    elif [ "${id#integration:}" != "$id" ]; then warn "$(t uninstall.integration_left "${id#integration:}" "$off")"
    else warn "$(t uninstall.plugin_left "$id" "$off")"; fi
  done < "$state/plugins.txt"
fi
# the machines herdr-fold added to the Herdr app leave it (their terminals keep running there)
while IFS= read -r name; do remove_from_app "$name"; done < <(cat "$APP_MACHINES" 2>/dev/null)
rm -f "$APP_MACHINES"
# herdr-fold's whole environment from herdr's marketplace (the plugin that offered the installer): on no record, as the
# installer did not put it there, and herdr-fold's all the same
if herdr plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    sys.exit(0 if any(p.get("plugin_id") == "herdr-fold" for p in json.load(sys.stdin)["result"]["plugins"]) else 1)
except (ValueError, KeyError, TypeError):
    sys.exit(1)'; then
  if herdr plugin uninstall herdr-fold >/dev/null 2>&1; then ok "$(t uninstall.plugin_removed herdr-fold)"
  else warn "$(t uninstall.plugin_left herdr-fold "herdr plugin uninstall herdr-fold")"; whole_left=1; fi
fi

step "$(t uninstall.step_files)"
# Claude's status line first: herdr-fold's runs a script that is about to go
python3 "$DOT/src/statusline_setup.py" --claude-restore "$state/original"
case $? in
  0) ok "$(t uninstall.claude_status_line)" ;;
  1) warn "$(t status.claude_unreadable "$HOME/.claude/settings.json")" ;;
esac
# what a Python that writes its cache in place left next to the package's scripts
[ -d "$HOME/.config/herdr-fold" ] && find "$HOME/.config/herdr-fold" -name __pycache__ -type d -prune -exec rm -rf {} +
# the app icon the theme drew for Ghostty: the file Ghostty's config includes, and the icons (Ghostty's own comes back)
rm -f "$HOME/.config/ghostty/herdr-fold-icon" "$HOME/.config/ghostty"/.herdr-fold-icon.*.tmp    # .*.tmp: cut short
rm -rf "$state/ghostty-icon"
removed=0
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  ai_session_file "$rel" && continue
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
if grep -qxF '# >>> herdr-fold >>>' "$HOME/.zshrc" 2>/dev/null; then
  remove_marked_block "$HOME/.zshrc" && ok "$(t uninstall.zshrc)"
fi
if grep -qxF '# >>> herdr-fold >>>' "$HOME/.config/herdr/config.toml" 2>/dev/null; then
  if out=$(python3 "$DOT/src/herdr_config.py" strip "$HOME/.config/herdr/config.toml"); then
    ok "$(t uninstall.config_stripped)"
  else warn "$out"; fi
fi
# This Mac's state (the machine list and the private word list stay: written by you), and the sidebar plugin's: the
# theme's colors and its toggles (only its own folder goes, herdr's around it stays)
rm -f "$HOME/.config/herdr-fold/setup-folder" "$HOME/.config/herdr-fold/statusline.json"
remove_empty_dirs "$HOME/.config/herdr-fold"
sidebar_state="$HOME/.local/state/herdr/plugins/herdr-fold.sidebar"
rm -f "$sidebar_state/colors.json" "$sidebar_state/settings.json" "$sidebar_state/column.json" \
  "$sidebar_state/conversations.json" "$sidebar_state/conversation-index.json" "$sidebar_state/panels.json" \
  "$sidebar_state"/resume-*.json "$sidebar_state"/seed-*.json "$sidebar_state"/preview-*.json \
  "$sidebar_state"/issues-*.json \
  "$sidebar_state"/.*.tmp                                                     # .*.tmp: a write cut short
rmdir "$sidebar_state" 2>/dev/null                                  # only when nothing else is in it
# the empty folders herdr keeps of the plugins taken off above (the conversation names stay)
# the whole environment's marks, once it is off (left on, it would offer the installer again on herdr's start)
[ -n "${whole_left:-}" ] || rm -f "$HOME/.local/state/herdr/plugins/herdr-fold"/offered-*
drop_plugin_folders herdr-fold herdr-fold.sidebar herdr-fold.sessions-view herdr-fold.tab-layout
herdr server reload-config >/dev/null 2>&1                          # a running herdr drops herdr-fold's keys

# The records, the loading colors and earlier versions go; anything of yours stays and is named with where it is: the
# conversation names, the machine list, the private word list, outside.txt (named, then removed), a file changed since
# the install, an original that did not go back, another Mac's prepare record.
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
# the Brewfile's programs Homebrew has (a herdr from its own installer is not Homebrew's to remove)
homebrews() {   # homebrews brew|cask
  local have; have=$(brew list --"$([ "$1" = cask ] && echo cask || echo formula)" -1 2>/dev/null)
  awk -F'"' -v kind="$1" '$1 == kind " " { print $2 }' "$DOT/Brewfile" | while IFS= read -r name; do
    printf '%s\n' "$have" | grep -qxF "$name" && printf '%s\n' "$name"
  done | paste -sd' ' -
}
command -v brew >/dev/null 2>&1 || brew_env
formulae=$(homebrews brew) casks=$(homebrews cask) hint=
[ -z "$formulae" ] || hint="brew uninstall $formulae"
[ -z "$casks" ] || hint="${hint:+$hint && }brew uninstall --cask $casks"
[ -z "$hint" ] || note "$(t uninstall.brew "$hint")"
machines=$(awk -F'|' '!/^[[:space:]]*(#|$)/ { gsub(/^[ \t]+|[ \t]+$/, "", $1); print $1 }' "$MACHINE_LIST" 2>/dev/null \
  | paste -sd, - | sed 's/,/, /g')
[ -n "$machines" ] && note "$(t uninstall.machines "$machines")"
ok "$(t uninstall.done)"
# Last, as the uninstaller may run from it and reads its texts there: the package kept for herdr's marketplace copy,
# marked as the installer's own (a folder of someone's by that name stays)
for kept in "$HOME/.local/share/herdr-fold" "$HOME/.local/share/herdr-fold.new" "$HOME/.local/share/herdr-fold.old"; do
  if [ -e "$kept/.kept-by-herdr-fold" ]; then rm -rf "$kept"; fi
done
