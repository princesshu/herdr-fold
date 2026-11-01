# Status lines of the installer, machines.sh and the remote prepare script: [✓] done, dim [✓] already there, [!] needs
# attention, [✗] stopped, [-] skipped, [+] a copy was kept. Colored only in a terminal without NO_COLOR; a remote
# machine's plain lines come back for summarize to read.

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  _mark() { printf '\033[2m[\033[0m%s%s\033[0m\033[2m]\033[0m' "$1" "$2"; }   # _mark COLOR GLYPH
  MARK_OK=$(_mark $'\033[32m' ✓) MARK_HAVE=$'\033[2m[✓]\033[0m' MARK_WARN=$(_mark $'\033[33m' !)
  MARK_FAIL=$(_mark $'\033[31m' ✗) MARK_SKIP=$'\033[2m[-]\033[0m' MARK_SAVED=$(_mark '' '+')
  MARK_BUSY=$(_mark '' '…')
  BOLD=$'\033[1m' PLAIN=$'\033[0m'
  unset -f _mark
else
  MARK_OK='[✓]' MARK_HAVE='[✓]' MARK_WARN='[!]' MARK_FAIL='[✗]' MARK_SKIP='[-]' MARK_SAVED='[+]' MARK_BUSY='[…]'
  BOLD= PLAIN=
fi

# What needs attention is also written to $HERDR_FOLD_WARNINGS (if set): the installer counts it at the end
_count() { [ -z "${HERDR_FOLD_WARNINGS:-}" ] || echo "$*" >> "$HERDR_FOLD_WARNINGS"; }

# _shown TEXT… — TEXT with control characters but tab and line break as ?: a name from elsewhere may set the window
# title, write the clipboard or move the cursor. Bytewise (LC_ALL=C): C0, DEL and UTF-8 C1 (\302\200-\237, as some
# terminals take U+009B for an escape); none of these bytes is part of another character.
_CONTROLS=$'\001\002\003\004\005\006\007\010\013\014\015\016\017\020\021\022\023\024\025'
_CONTROLS+=$'\026\027\030\031\032\033\034\035\036\037\177'
_shown() {
  local LC_ALL=C text="$*"
  text=${text//[$_CONTROLS]/?}
  printf '%s' "${text//$'\302'[$'\200'-$'\237']/?}"
}
_line() { local start=$1; shift; progress_clear; printf '%s%s\n' "$start" "$(_shown "$@")"; }

step()    { progress_clear; printf '\n%s== %s%s\n' "$BOLD" "$1" "$PLAIN"; }
section() { _line "  -- " "$@"; }                                      # a part of a step (folded away by summarize)
ok()      { _line "  $MARK_OK " "$@"; }
have()    { _line "  $MARK_HAVE " "$@"; }
warn()    { _line "  $MARK_WARN " "$@"; _count "$*"; }
fail()    { _line "  $MARK_FAIL " "$@"; _count "$*"; }
skip()    { _line "  $MARK_SKIP " "$@"; }
saved()   { _line "  $MARK_SAVED " "$@"; }
note()    { _line "      " "$@"; }                                     # under the text of the line above

# Steps that go through many small items show them on one line that keeps changing (progress), then sum up in a single
# line; anything that needs attention still gets a line of its own. HERDR_FOLD_VERBOSE=1: every item on its own line.
verbose() { [ "${HERDR_FOLD_VERBOSE:-}" = 1 ]; }
progress() { [ -t 1 ] && printf '\r\033[K  %s %s' "$MARK_BUSY" "$(_shown "$@")"; return 0; }       # progress ITEM
progress_clear() { [ -t 1 ] && printf '\r\033[K'; return 0; }
joined() { local out=$1 item; shift; for item in "$@"; do out+=", $item"; done; printf '%s' "$out"; }  # joined ITEM…

# summarize LABEL [STATUS] — the plain status lines of a step (stdin: a remote machine's, a helper's): what needs
# attention, what was skipped or saved keeps its own line; the done ones and the section headers fold into one
# "[✓] LABEL" line — or a warning if the step's exit STATUS was not 0
summarize() {
  local line status=${2:-0}
  while IFS= read -r line; do
    case "$line" in
      "") ;;
      "  [✓] "*|"  -- "*) verbose && _line "" "$line" ;;
      "  [!] "*) warn "${line#  \[!\] }" ;;
      "  [✗] "*) fail "${line#  \[✗\] }" ;;
      "  [-] "*) skip "${line#  \[-\] }" ;;
      "  [+] "*) saved "${line#  \[+\] }" ;;
      *) _line "" "$line" ;;
    esac
  done
  if [ "$status" != 0 ]; then warn "$1"; elif [ -n "$1" ]; then ok "$1"; fi           # no LABEL: quiet when done
}
