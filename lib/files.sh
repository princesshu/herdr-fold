# Rules for the files the installer and the prepare scripts put on a machine. Load with: source.

# ai_session_file REL — REL (relative to HOME) is Claude's, Codex's or herdr's own data: a conversation, its name, the
# history, AI Sessions' names — anything under ~/.claude, ~/.codex or ~/.local/state/herdr. Nothing the
# installer, a prepare script or the uninstaller does may ever delete one.
ai_session_file() {
  case "$1" in
    .claude/*|.codex/*|.local/state/herdr/*) return 0 ;;
  esac
  return 1
}

# remove_marked DIR MARK — DIR goes only with MARK in it, checked after a move to a name of this run's own, so nothing
# swapped in after a check goes; a link, or a folder without MARK, goes back to its name
remove_marked() {
  [ -e "$1" ] || [ -L "$1" ] || return 0
  local aside; aside=$(mktemp -d "$1.gone.XXXXXX") || return 1
  mv "$1" "$aside/dir" || { rmdir "$aside"; return 1; }
  if [ ! -L "$aside/dir" ] && [ -f "$aside/dir/$2" ]; then rm -rf "$aside"; return 0; fi
  mv "$aside/dir" "$1"; rmdir "$aside"; return 1
}

# drop_plugin_folders ID… — the empty folders herdr keeps of a plugin after `plugin unlink` (its config folder, its
# state folder once nothing of the plugin's is left in it, the tab layout's and AI Sessions' own records gone first,
# the conversation names kept); nothing of a plugin herdr still lists, nothing at all when herdr cannot say what it has
drop_plugin_folders() {
  local listed id state
  listed=$(herdr plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    print("\n".join(p["plugin_id"] for p in json.load(sys.stdin)["result"]["plugins"]))
except (ValueError, KeyError, TypeError):
    sys.exit(1)') || return 0
  for id in "$@"; do
    grep -qxF "$id" <<< "$listed" && continue
    state="$HOME/.local/state/herdr/plugins/$id"
    case "$id" in
      herdr-fold.tab-layout) rm -f "$state"/{spaces,focus}.json "$state"/.{spaces,focus}.json.*.tmp ;;
      herdr-fold.sessions-view) rm -f "$state"/{waits.json,clock.lock} "$state"/{names,waits}.json.lock \
        "$state"/.{names,waits}.json.*.tmp ;;
    esac
    rmdir "$HOME/.config/herdr/plugins/config/$id" "$state" 2>/dev/null
  done
  return 0
}

# recorded_sum STATE REL — the SHA-256 the installer recorded for REL right after installing it
# (STATE/installed.sha256); nothing when it recorded none
recorded_sum() {
  awk -v rel="$2" '{ sum = $1; sub(/^[^ ]+  /, "") } $0 == rel { print sum }' "$1/installed.sha256" 2>/dev/null
}
sum_of() { shasum -a 256 "$1" | cut -d' ' -f1; }
# shown PATH — PATH as it is said: ~/… under the home folder
shown() { case "$1" in "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;; *) printf '%s' "$1" ;; esac; }

# write_whole FILE NEW — NEW's text (a file beside FILE) into FILE itself, so a linked file (a dotfiles repo) stays a
# link; NEW goes. Made beside FILE, NEW took the room the text needs there, so a full disk stopped it before FILE was
# touched; a FILE that still cannot take it keeps NEW, which is named: it holds every line FILE had.
write_whole() {
  if cat "$2" > "$1"; then rm -f "$2"; return 0; fi
  warn "$(t files.not_written "$(shown "$1")" "$(shown "$2")")"
  return 1
}

# marked_block FILE LINE… — puts the lines into FILE between "# >>> herdr-fold >>>" and "# <<< herdr-fold <<<": in place
# of an earlier block (every one, if there are more), otherwise at the end; a begin marker without its end is left as it
# is (write_whole)
marked_block() {
  local file=$1 tmp; shift
  [ -f "$file" ] || : > "$file"
  tmp=$(mktemp "$file.XXXXXX") || return 1
  MARK_BEGIN='# >>> herdr-fold >>>' MARK_END='# <<< herdr-fold <<<' BLOCK=$(printf '%s\n' "$@") awk '
    BEGIN { b = ENVIRON["MARK_BEGIN"]; e = ENVIRON["MARK_END"]; block = b "\n" ENVIRON["BLOCK"] "\n" e }
    FNR == 1 { pass++ }
    pass == 1 { if ($0 == b) start = FNR; else if ($0 == e && start) { whole[start] = 1; start = 0 }; next }
    $0 == b && (FNR in whole) { if (!done) print block; done = 1; skip = 1; next }
    skip { if ($0 == e) skip = 0; next }
    { print; n++ }
    END { if (!done) { if (n) print ""; print block } }
  ' "$file" "$file" > "$tmp" || { rm -f "$tmp"; return 1; }
  write_whole "$file" "$tmp"
}

# remove_marked_block FILE — takes the marked lines (every complete pair) out of FILE again, with the empty line
# marked_block put before them (write_whole)
remove_marked_block() {
  local file=$1 tmp
  [ -f "$file" ] && grep -qxF '# >>> herdr-fold >>>' "$file" || return 0
  tmp=$(mktemp "$file.XXXXXX") || return 1
  MARK_BEGIN='# >>> herdr-fold >>>' MARK_END='# <<< herdr-fold <<<' awk '
    BEGIN { b = ENVIRON["MARK_BEGIN"]; e = ENVIRON["MARK_END"] }
    FNR == 1 { pass++ }
    pass == 1 { if ($0 == b) start = FNR; else if ($0 == e && start) { whole[start] = 1; start = 0 }; next }
    $0 == b && (FNR in whole) { held = 0; skip = 1; next }
    skip { if ($0 == e) skip = 0; next }
    { if (held) print ""; held = 0 }
    $0 == "" { held = 1; next }
    { print }
    END { if (held) print "" }
  ' "$file" "$file" > "$tmp" || { rm -f "$tmp"; return 1; }
  write_whole "$file" "$tmp"
}

# remove_empty_dirs DIR — removes DIR and then each parent while they are empty; never HOME and its shared folders
remove_empty_dirs() {
  local d=$1
  while case "$d" in "$HOME"|"$HOME/.config"|"$HOME/.local"|"$HOME/.local/state"|/|.) false ;; *) true ;; esac \
    && rmdir "$d" 2>/dev/null; do
    d=$(dirname "$d")
  done
}
