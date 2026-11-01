# Shared helpers for remote machines (machines.sh, herdr_layout.py), over OpenSSH and the herdr CLI. A Windows SSH
# shell can be cmd or PowerShell, so commands go as -EncodedCommand, which gets through either unchanged.

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

# A text as a single-quoted literal for the machine's shell (sh_quote) or for PowerShell (ps_quote): nothing in it is
# expanded. PowerShell ends a single-quoted string at the typographic quotes ‘ ’ ‚ ‛ too, so each of them is doubled.
sh_quote() { local q="'"; printf "'%s'" "${1//$q/$q\\$q$q}"; }
ps_quote() {
  local s=$1 q
  for q in "'" "‘" "’" "‚" "‛"; do s=${s//$q/$q$q}; done
  printf "'%s'" "$s"
}
# ssh calls that need no input read from /dev/null: otherwise ssh swallows whatever is on the caller's standard
# input (the list of a `while read` loop, or keys typed while it runs). The machine goes after --: a name that starts
# with - (typed, from a config Host line or a network's peer list) is then a name, never an option.

# One field of a machine saved in herdr, looked up by name (target | id | enabled); empty if there is no such machine
machine_field() {
  herdr machine list --json 2>/dev/null | python3 -c '
import sys, json
label, field = sys.argv[1], sys.argv[2]
try:
    machines = json.load(sys.stdin)
except ValueError:          # no herdr, or no answer from it
    machines = []
for m in machines:
    if m.get("label") == label:
        print(m.get(field, "")); break' "$1" "$2"
}

ssh_ok() { ssh "${SSH_OPTS[@]}" -- "$1" exit </dev/null >/dev/null 2>&1; }

# linux | macos | windows (empty if unreachable)
remote_os() {
  local out
  out=$(ssh "${SSH_OPTS[@]}" -- "$1" uname -s </dev/null 2>/dev/null | tr -d '\r')
  case "$out" in
    Linux) echo linux ;;
    Darwin) echo macos ;;
    *) ssh_ok "$1" && echo windows ;;
  esac
}

# Run a PowerShell script on a Windows machine; output is UTF-8, without line-ending carriage returns (\r). The exit
# status is the remote script's (pipefail: not tr's)
win_ps() {
  local script="\$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; $2"
  local enc; enc=$(printf '%s' "$script" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')
  (
    set -o pipefail
    ssh "${SSH_OPTS[@]}" -- "$1" "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $enc" \
      </dev/null | tr -d '\r'
  )
}

remote_home() {
  if [ "$2" = windows ]; then win_ps "$1" '[Console]::Out.Write($env:USERPROFILE)'
  else ssh "${SSH_OPTS[@]}" -- "$1" 'printf %s "$HOME"' </dev/null; fi
}

# Expand ~ and ~/… to the remote machine's home folder
remote_path() {
  case "$3" in
    "~") remote_home "$1" "$2" ;;
    "~/"*|"~\\"*) printf '%s%s' "$(remote_home "$1" "$2")" "${3#\~}" ;;
    *) printf '%s' "$3" ;;
  esac
}

# remote_is_dir <target> <os> <path> — true if the folder exists on the machine
remote_is_dir() {
  if [ "$2" = windows ]; then
    [ "$(win_ps "$1" "if (Test-Path -LiteralPath $(ps_quote "$3") -PathType Container) { 'yes' }")" = yes ]
  else
    ssh "${SSH_OPTS[@]}" -- "$1" "test -d $(printf %q "$3")" </dev/null
  fi
}
