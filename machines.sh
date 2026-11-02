#!/bin/bash
# Remote machines (Linux, macOS, Windows) in herdr on the central Mac: their workspaces show in herdr's sidebar, while
# Claude/Codex, the sidebar and the terminal run on the machine. install.sh calls it; run it alone to add a machine.
# Commands: ./machines.sh help (the machines.help key of src/lang/<language>.txt).
set -u
cd "$(dirname "$0")" || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
. "$DOT/src/remote.sh"

# remove_from_list NAME — takes NAME's line off the machine list
remove_from_list() {
  local tmp; tmp=$(mktemp)
  awk -F'|' -v n="$1" '{ name = $1; gsub(/^[ \t]+|[ \t]+$/, "", name) } name != n' "$MACHINE_LIST" > "$tmp" \
    && mv "$tmp" "$MACHINE_LIST"
}

# "name|target|os" lines from the machine list (filtered to the given names)
machines() {
  [ -f "$MACHINE_LIST" ] || return 0
  grep -vE '^[[:space:]]*(#|$)' "$MACHINE_LIST" | while IFS='|' read -r name target os; do
    name=$(echo "$name" | trim); target=$(echo "$target" | trim); os=$(echo "$os" | trim)
    if [ $# -gt 0 ]; then
      case " $* " in *" $name "*) ;; *) continue ;; esac
    fi
    echo "$name|$target|$os"
  done
}

add_line() {
  if [ ! -f "$MACHINE_LIST" ]; then
    mkdir -p "$(dirname "$MACHINE_LIST")"
    cat > "$MACHINE_LIST" <<'LIST'
# Remote machines in herdr (herdr-fold), filled in by the installer; edit by hand if you like. No passwords or keys
# here: login uses this Mac's SSH key. Lines:  name | user@machine | os (linux / macos / windows)
#   name: shown in herdr's sidebar (--machine <name>); machine: a DNS name, IP address or Tailscale name
LIST
  fi
  printf '%-16s | %s | %s\n' "$1" "$2" "$3" >> "$MACHINE_LIST"
}

# Without a machine list yet (e.g. machines connected in herdr by hand), the machines connected in herdr go onto it,
# with their OS; an unreachable one waits for the next run. An existing list is left as it is, so a machine taken off it
# stays off.
take_over_connected() {
  local name target os
  [ -f "$MACHINE_LIST" ] && return 0
  while IFS='|' read -r name target <&3; do
    machines | cut -d'|' -f1 | grep -qxF "$name" && continue
    os=$(remote_os "$target")
    if [ -n "$os" ]; then add_line "$name" "$target" "$os"; ok "$(t machines.taken_over "$name" "$os")"
    else warn "$(t machines.take_over_unreachable "$name")"; fi
  done 3< <(herdr machine list --json 2>/dev/null | python3 -c '
import json, sys
try:
    machines = json.load(sys.stdin)
except ValueError:
    machines = []
for m in machines:
    if m.get("label") and m.get("target"):
        print(m["label"] + "|" + m["target"])')
}

# A listed machine at the very address of a ~/.ssh/config Host (User and HostName) goes through that Host and its key
# and options. Not a Host with its own port, jump host, proxy or host key alias: that is another endpoint, whose key
# ssh would take unasked, while the listed address had its fingerprint confirmed.
use_config_hosts() {
  [ -f "$MACHINE_LIST" ] && [ -f "$HOME/.ssh/config" ] || return 0
  local hosts name target os alias tmp
  hosts=$(ssh_config_hosts plain)
  [ -n "$hosts" ] || return 0
  while IFS='|' read -r name target os <&3; do
    alias=$(printf '%s\n' "$hosts" | awk -F'|' -v t="$target" '$2 == t { print $1; exit }')
    [ -n "$alias" ] && [ "$alias" != "$target" ] || continue
    tmp=$(mktemp)
    awk -F'|' -v n="$name" -v a="$alias" 'BEGIN { OFS = "|" } { m = $1; gsub(/^[ \t]+|[ \t]+$/, "", m) }
      m == n && !/^[[:space:]]*#/ { $2 = " " a " " } { print }' "$MACHINE_LIST" > "$tmp" \
      && mv "$tmp" "$MACHINE_LIST" && ok "$(t machines.through_config "$name")"
  done 3< <(machines)
}

ssh_says() { ssh "${SSH_OPTS[@]}" -- "$1" exit 2>&1 >/dev/null; }   # ssh_says <target>: only what ssh itself says

# Can this Mac log in to the machine? If not: why, from what ssh says, and what to do about it
reachable() {   # reachable <target>
  local said
  said=$(LOADING_PLAIN=1 loading "$(t machines.reaching "$1")" ssh_says "$1") && return 0   # ssh's timeout ends it soon
  case "$said" in
    *"Could not resolve hostname"*) warn "$(t machines.ssh_unknown_name "$1")" ;;
    *"Connection refused"*) warn "$(t machines.ssh_refused "$1")"; note "$(t machines.ssh_turn_on)" ;;
    *"timed out"*|*"No route to host"*|*"Network is unreachable"*|*"Host is down"*)
      warn "$(t machines.ssh_unreachable "$1")" ;;
    *"Permission denied"*) warn "$(t machines.ssh_failed "$1")"; note "$(t machines.ssh_passphrase)" ;;
    *"Host key verification failed"*) warn "$(t machines.ssh_host_key "$1" "${1#*@}")" ;;
    *) warn "$(t machines.ssh_failed_why "$1" "$(printf '%s\n' "$said" | grep . | tail -1)")" ;;
  esac
  return 1
}

# Status of a machine's apps, on one line
tools_line() {
  if [ "$2" = windows ]; then
    win_ps "$1" '
$env:Path = "$env:USERPROFILE\.local\bin;" + [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:Path"
$out = foreach ($c in "herdr","claude","codex","git","starship","python") {
  $ok = Get-Command $c -ErrorAction SilentlyContinue
  if ($c -eq "python" -and $ok -and $ok.Source -like "*WindowsApps*") { $ok = $null }
  if ($ok) { "✓$c" } else { "·$c" } }
$out -join " "'
  else
    ssh "${SSH_OPTS[@]}" -- "$1" 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
      for c in herdr claude codex git starship python3; do
        if command -v $c >/dev/null 2>&1; then printf "✓%s " $c; else printf "·%s " $c; fi; done' </dev/null
  fi
}

# The per-machine loops read the list from file descriptor 3, not from standard input: that way the ssh and herdr
# commands inside the loop cannot swallow the rest of the list (otherwise only the first machine would get a turn).
cmd_status() {
  local any=
  while IFS='|' read -r name target os <&3; do
    any=1
    echo "== $(t machines.heading "$name" "$target" "$os")"
    reachable "$target" || continue
    if [ -n "$(machine_field "$name" id)" ]; then ok "$(t machines.connected)"
    else note "$(t machines.not_connected "$name")"; fi
    note "$(tools_line "$target" "$os")"
  done 3< <(machines "$@")
  [ -n "$any" ] || skip "$(t machines.none_listed)"
}

# The machines on the Tailscale network (Linux, macOS, Windows), one "short|dns|os|online/offline|ips" line each.
# Exit status 1 without Tailscale, 2 if it does not answer.
tailnet_peers() {
  local ts; ts=$(tailscale_bin) || return 1
  "$ts" status --json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin)
for p in sorted((d.get("Peer") or {}).values(), key=lambda p: p.get("DNSName", "")):
    os_ = {"linux": "linux", "windows": "windows", "macOS": "macos"}.get(p.get("OS"))
    if os_:
        dns = p.get("DNSName", "").rstrip(".")
        print("|".join([dns.split(".")[0], dns, os_, "online" if p.get("Online") else "offline",
                        ",".join(p.get("TailscaleIPs") or [])]))' || return 2
}

# Pick from the machines on the Tailscale network, one question each
cmd_tailscale() {
  local peers hosts; peers=$(tailnet_peers)
  case $? in
    1) skip "$(t machines.no_tailscale)"; return 0 ;;
    2) warn "$(t machines.tailscale_failed)"; return 0 ;;
  esac
  [ -n "$peers" ] || { skip "$(t machines.tailscale_empty)"; return 0; }
  hosts=$(ssh_config_hosts)
  local added=0 kept=() short dns os state ips alias name user listed_as shown
  while IFS='|' read -r short dns os state ips <&3; do
    # its ~/.ssh/config Host, if it has one: then it goes on the list under that name (with that file's user and key).
    # The Host's name or its HostName is the machine's name or address here, as cmd_sshconfig leaves such a Host to
    # this step (its HostName may be another address of it, such as a public name)
    alias=$(printf '%s\n' "$hosts" | awk -F'|' -v d="$dns" -v s="$short" -v ips=",$ips," '{ h = $2; sub(/.*@/, "", h) }
      $1 == d || $1 == s || h == d || h == s || index(ips, "," h ",") { print $1; exit }')
    name=${alias:-$short}
    # where it would connect: for a Host, that file's address (a device named like it may not be that machine)
    shown=$(printf '%s\n' "$hosts" | awk -F'|' -v a="$alias" 'a != "" && $1 == a { print $2; exit }')
    shown=${shown:-$dns}
    listed_as=$(listed_name_for "$name" "$short" "$dns" ${ips//,/ })
    if [ -n "$listed_as" ]; then
      ask "$(t machines.select_ask_listed "$name" "$os" "$shown")" y && { kept+=("$listed_as"); continue; }
      remove_from_list "$listed_as"; note "$(t machines.removed_from_list "$listed_as")"; continue
    fi
    ask "$(t machines.select_ask "$name" "$os" "$shown" \
      "$([ "$state" = offline ] && echo " $(t machines.select_offline)")")" n || continue
    if [ -n "$alias" ]; then
      add_line "$name" "$alias" "$os"
    else
      # the suggested user: root on Linux, elsewhere the same user name as on this Mac
      [ "$os" = linux ] && user=root || user=${USER:-$(id -un)}
      user=$(prompt "$(t machines.select_user)" "$user")
      add_line "$name" "$user@$dns" "$os"
    fi
    added=$((added + 1))
  done 3<<< "$peers"
  added_summary "$added" ${kept[@]+"${kept[@]}"}        # (bash 3.2 + set -u: an empty array is unset)
}

# The machines of ~/.ssh/config (Include-d files too), one "alias|user@host" line each — no patterns or git hosts
ssh_config_hosts() {   # [plain]: only the Hosts that change nothing but the name (see use_config_hosts)
  [ -f "$HOME/.ssh/config" ] || return 0
  python3 - "$HOME/.ssh/config" "${1:-}" <<'PY'
import glob, os, re, sys
GIT = re.compile(r"(^|\.)(github\.com|gitlab\.com|bitbucket\.org|ssh\.dev\.azure\.com|vs-ssh\.visualstudio\.com)$",
                 re.I)

def entries(path, depth=0):
    """(key, value) pairs from the file, including Include-d files (relative to ~/.ssh, glob patterns too)."""
    try:
        f = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with f:
        for raw in f:
            m = re.match(r"\s*([^\s=]+)\s*=?\s*(.*)", raw.split("#", 1)[0])
            if not m or not m.group(1):
                continue
            key, value = m.group(1).lower(), m.group(2).strip()
            if key == "include" and depth < 8:
                for pattern in value.split():
                    pattern = os.path.expanduser(pattern)
                    pattern = pattern if os.path.isabs(pattern) else os.path.join(os.path.expanduser("~/.ssh"), pattern)
                    for inc in sorted(glob.glob(pattern)):
                        yield from entries(inc, depth + 1)
            else:
                yield key, value

order, conf, current = [], {}, []
for key, value in entries(sys.argv[1]):
    if key in ("host", "match"):
        current = value.split() if key == "host" else []
        for alias in current:
            if alias not in conf:
                order.append(alias); conf[alias] = {}
    elif key in ("hostname", "user", "port", "proxyjump", "proxycommand", "hostkeyalias"):
        for alias in current:
            conf[alias].setdefault(key, value)
for alias in order:
    c = conf[alias]
    host = c.get("hostname", alias)
    if any(ch in alias for ch in "*?!") or c.get("user") == "git" or GIT.search(host) or GIT.search(alias):
        continue
    if sys.argv[2] == "plain" and (c.get("port", "22") != "22" or
                                   any(c.get(key) for key in ("proxyjump", "proxycommand", "hostkeyalias"))):
        continue
    print(f"{alias}|{c['user'] + '@' if c.get('user') else ''}{host}")
PY
}

# added_summary COUNT NAME… — "COUNT new machine(s) on the list, N already there: NAME, NAME…"
added_summary() {
  local count=$1; shift
  local names; names=$(IFS=,; echo "$*"); names=${names//,/, }
  ok "$(t machines.added_count "$count" "$#" "${names:+: $names}")"
}

# listed_name_for CANDIDATE… — the name of the first machine on the list whose name, address or host is a CANDIDATE
listed_name_for() {
  local name target os c
  while IFS='|' read -r name target os; do
    for c in "$@"; do
      [ -n "$c" ] && { [ "$c" = "$name" ] || [ "$c" = "$target" ] || [ "$c" = "${target#*@}" ]; } \
        && { echo "$name"; return; }
    done
  done <<< "$(machines)"            # read whole, as returning early would break a pipe from machines
}

# Pick from the machines in ~/.ssh/config, one question each, no unless said yes (a Host line may name a machine not
# meant for this: a jump host, a client's server) — those on the Tailscale network are left to its own step
# (cmd_tailscale), asked after it. One imported earlier is asked too: no takes it off the list.
cmd_sshconfig() {
  [ -f "$HOME/.ssh/config" ] || { skip "$(t machines.no_ssh_config)"; return 0; }
  local hosts tailnet; hosts=$(ssh_config_hosts)
  [ -n "$hosts" ] || { skip "$(t machines.ssh_config_empty)"; return 0; }
  tailnet=$(tailnet_peers 2>/dev/null \
    | awk -F'|' '{ print $1; print $2; n = split($5, ip, ","); for (i = 1; i <= n; i++) print ip[i] }')
  local added=0 kept=() alias where os listed_as
  while IFS='|' read -r alias where <&3; do
    printf '%s\n' "$alias" "${where#*@}" | grep -qxF -f <(printf '%s\n' "$tailnet" | grep .) && continue
    listed_as=$(listed_name_for "$alias" "${where#*@}")
    if [ -n "$listed_as" ]; then
      ask "$(t machines.sshconfig_ask_listed "$alias" "$where")" y && { kept+=("$listed_as"); continue; }
      remove_from_list "$listed_as"; note "$(t machines.removed_from_list "$listed_as")"; continue
    fi
    ask "$(t machines.sshconfig_ask "$alias" "$where")" n || continue
    reachable "$alias" || continue
    os=$(remote_os "$alias")
    add_line "$alias" "$alias" "$os"
    ok "$(t machines.added "$alias" "$os")"
    added=$((added + 1))
  done 3<<< "$hosts"
  added_summary "$added" ${kept[@]+"${kept[@]}"}        # (bash 3.2 + set -u: an empty array is unset)
}

# confirm_host_key HOST — a machine typed in by hand that ssh does not know yet: its ED25519 fingerprint (the one the
# docs have you compare) is confirmed first, and exactly that key goes into ~/.ssh/known_hosts, so ssh refuses any
# other. No ED25519 key (or no answer): not added, as ssh would trust whatever answered then.
confirm_host_key() {
  local keys fp
  ssh-keygen -F "$1" >/dev/null 2>&1 && return 0
  keys=$(ssh-keyscan -T 5 -t ed25519 -- "$1" 2>/dev/null)
  fp=$(printf '%s\n' "$keys" | ssh-keygen -lf - 2>/dev/null)
  if [ -z "$fp" ]; then warn "$(t machines.hostkey_unreadable "$1")"; return 1; fi
  note "$fp"                              # the fingerprint (data, not a text)
  ask "$(t machines.hostkey_ask "$1")" n || return 1     # a typed yes, after comparing: Enter alone is no
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  printf '%s\n' "$keys" >> "$HOME/.ssh/known_hosts"
  record_outside "known-host $1"
}

# listed_target TARGET — the machine list already has a machine at TARGET (user@host)
listed_target() { machines | cut -d'|' -f2 | grep -qxF "$1"; }

# unique_name NAME — NAME, or NAME-2, NAME-3… when the machine list already has a machine called NAME
unique_name() {
  local name=$1 n=2
  while machines | cut -d'|' -f1 | grep -qxF "$name"; do name="$1-$n"; n=$((n + 1)); done
  printf '%s' "$name"
}

# Add a machine by SSH address; the OS (Linux / macOS / Windows) is detected by logging in
cmd_manual() {
  local user host target name os
  while :; do
    user=$(prompt "$(t machines.manual_user)" root)
    host=$(prompt "$(t machines.manual_host)")
    if [ -n "$host" ] && listed_target "$user@$host"; then
      note "$(t machines.already_listed "$user@$host")"
    elif [ -n "$host" ] && confirm_host_key "$host"; then
      target="$user@$host"
      if reachable "$target"; then
        os=$(remote_os "$target")
        # the name in herdr's sidebar: an IP address as it is, a host name up to its first dot (made unique)
        case "$host" in *[!0-9.]*) name=${host%%.*} ;; *) name=$host ;; esac
        name=$(unique_name "$name")
        add_line "$name" "$target" "$os"
        ok "$(t machines.added "$name" "$os")"
      fi
    fi
    ask "$(t machines.manual_more)" n || break
  done
}

# The installer's step 8, and Ctrl+B, Shift+M: where to read new machines from — each source on its own question, its
# machines then one by one: ~/.ssh/config, the Tailscale network (it skips the machines already on the list), an
# address typed in. Exit status 1 if none was asked for.
cmd_pick() {
  local picked=1
  if [ -f "$HOME/.ssh/config" ] && ask "$(t machines.pick_sshconfig)" n; then
    has_ssh_key || make_ssh_key; cmd_sshconfig; picked=0
  fi
  if [ -n "$(tailscale_bin)" ] && ask "$(t machines.pick_tailscale)" n; then
    has_ssh_key || make_ssh_key; cmd_tailscale; picked=0
  fi
  if ask "$(t machines.pick_manual)" n; then
    has_ssh_key || make_ssh_key; cmd_manual; picked=0
  fi
  return $picked
}

# Ctrl+B, Shift+M (add_machine.py — herdr itself has no button for adding a machine): the same questions, then only
# the machines they put on the list get set up; the window stays open until a key press
cmd_new() {
  local before name new=()
  before=$(machines | cut -d'|' -f1)
  cmd_pick || skip "$(t machines.none_picked)"
  while IFS='|' read -r name _; do
    printf '%s\n' "$before" | grep -qxF "$name" || new+=("$name")
  done < <(machines)
  [ ${#new[@]} -eq 0 ] || cmd_add "${new[@]}" || warn "$(t machines.new_failed)"
  wait_for_key
}

# remote_files KIND — the files of remote/files.txt for a KIND of machine (unix | windows), as "path in the package|
# location on the machine" lines; a path with a * stands for every matching file (its location is a folder)
remote_files() {
  local src rel kinds f
  grep -vE '^[[:space:]]*(#|$)' "$DOT/remote/files.txt" | while IFS='|' read -r src rel kinds; do
    src=$(echo "$src" | trim); rel=$(echo "$rel" | trim); kinds=$(echo "$kinds" | trim)
    [ "$kinds" = all ] || [ "$kinds" = "$1" ] || continue
    case "$src" in
      *'*'*) for f in "$DOT"/$src; do [ -f "$f" ] && echo "${f#"$DOT"/}|$rel${f##*/}"; done ;;
      *) echo "$src|$rel" ;;
    esac
  done
}

# Build the payload for the machine (in STAGE): the prepare script with what it runs on (the texts, the status lines,
# the downloader), and files/<location> for every file of remote/files.txt — plus the Mac's prompt in the colors of its
# current theme and its status line choice — with files.list, the list of those locations
stage_payload() {   # stage_payload <stage> <script> [remove]: with remove, nothing is listed to put in place
  local stage=$1 script=$2 kind src rel
  [ "$script" = prepare-unix.sh ] && kind=unix || kind=windows
  mkdir -p "$stage/files"
  : > "$stage/files.list"
  cp "$DOT/remote/$script" "$stage/"
  mkdir -p "$stage/lang" && cp "$DOT"/src/lang/*.txt "$stage/lang/"      # the texts it prints, either way
  if [ "$kind" = unix ]; then
    mkdir -p "$stage/lib" \
      && cp "$DOT/lib/i18n.sh" "$DOT/lib/output.sh" "$DOT/lib/files.sh" "$stage/lib/"
    cp "$DOT/remote/fetch-tool.sh" "$stage/"     # its only way to download a program
  fi
  stage_file() {  # stage_file <source> <location>; a listed file missing from the package is said, not sent
    [ -f "$1" ] || { echo "  [!] $(t machines.not_in_package "${1#"$DOT"/}")"; return; }
    mkdir -p "$(dirname "$stage/files/$2")" && cp "$1" "$stage/files/$2" && echo "$2" >> "$stage/files.list"
  }
  while IFS='|' read -r src rel; do stage_file "$DOT/$src" "$rel"; done < <(remote_files "$kind")
  stage_file "$( [ -f "$HOME/.config/starship.toml" ] && echo "$HOME/.config/starship.toml" \
    || echo "$DOT/config/starship.toml")" .config/starship.toml
  [ -f "$HOME/.config/herdr-fold/statusline.json" ] \
    && stage_file "$HOME/.config/herdr-fold/statusline.json" .config/herdr-fold/statusline.json
  # the sidebar's colors in the Mac's theme (its theme setter writes them on the Mac): without them a machine's sidebar
  # falls back to the terminal's 16 colors
  local colors=.local/state/herdr/plugins/herdr-fold.sidebar/colors.json
  [ -f "$HOME/$colors" ] && stage_file "$HOME/$colors" "$colors"
  unset -f stage_file
  # taking it off: the files still travel (one the machine changed is kept, compared to these), the list is empty
  if [ "${3:-}" = remove ]; then : > "$stage/files.list"; fi
}

# Step 1: apps and settings onto the machine — BEFORE connecting it to herdr, so the herdr server already starts
#    with the updated PATH (on Windows the panes inherit the server's environment)
prepare_files() {   # prepare_files <target> <os> [remove]
  local target=$1 os=$2 mode=${3:-} tmp lang=${HERDR_FOLD_LANG:-en} label
  label=$(t machines.preparing); [ "$mode" = remove ] && label=$(t machines.removing)
  case "$lang" in *[!A-Za-z0-9_-]*) lang=en ;; esac      # the language goes into the remote command line as it is
  tmp=$(mktemp -d)
  local out rc
  out=$(loading "$label" copy_and_prepare "$tmp" "$target" "$os" "$lang" "$mode"); rc=$?
  rm -rf "$tmp"
  # done: one line for what went fine (warnings keep theirs); failed: all of it, to see where
  if [ $rc = 0 ]; then printf '%s\n' "$out" | summarize "$label"
  else printf '%s\n' "$out"; warn "$(t machines.prepare_failed)"; fi
  return $rc
}

# Windows gets the payload as text: a PowerShell-shell server closes scp's SFTP, and stdin does not get through. Each
# `echo x<piece> >> ~\.herdr-fold.b64` runs in cmd, PowerShell (the space before >>; x: digits alone are a number) and
# Git Bash, under cmd's 8191-char limit, over one connection whose socket is in this run's private folder.
WIN_PIECE=7000
win_put() {   # win_put <target> <folder> <socket>: the folder's files into ~\.herdr-fold on the machine
  local data shared=(-o ControlMaster=auto -o "ControlPath=$3" -o ControlPersist=10)
  data=$(COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -C "$2" -czf - . | base64 | tr -d '\n') || return 1
  win_ps "$1" 'Remove-Item -Recurse -Force (Join-Path $env:USERPROFILE .herdr-fold),
    (Join-Path $env:USERPROFILE .herdr-fold.b64) -ErrorAction SilentlyContinue' >/dev/null
  while [ -n "$data" ]; do
    ssh -n "${SSH_OPTS[@]}" "${shared[@]}" -- "$1" "echo x${data:0:WIN_PIECE} >> .herdr-fold.b64" >/dev/null || break
    data=${data:WIN_PIECE}
  done
  ssh "${shared[@]}" -O exit -- "$1" >/dev/null 2>&1
  [ -z "$data" ] || return 1
  win_ps "$1" '
$dir = Join-Path $env:USERPROFILE .herdr-fold
$text = (Get-Content "$dir.b64" | ForEach-Object { $_.Trim().Substring(1) }) -join ""
Remove-Item -Force "$dir.b64"
New-Item -ItemType Directory -Force $dir | Out-Null
[IO.File]::WriteAllBytes("$dir.tgz", [Convert]::FromBase64String($text))
tar -xzf "$dir.tgz" -C $dir
$unpacked = $LASTEXITCODE
Remove-Item -Force "$dir.tgz"
exit $unpacked'
}

# Copies the payload (staged in TMP) to the machine and runs its prepare script there; the loading line shows the
# sending, then the machine's sections
copy_and_prepare() {   # copy_and_prepare <tmp> <target> <os> <lang> [remove]
  local tmp=$1 target=$2 os=$3 lang=$4 mode=${5:-}
  loading_phase "$(t machines.phase_sending)"
  if [ "$os" = windows ]; then
    stage_payload "$tmp/payload" prepare-windows.ps1 "$mode"
    (                     # pipefail: the exit status is the prepare script's, not the filters'
      set -o pipefail
      win_put "$target" "$tmp/payload" "$tmp/ssh" \
        && ssh "${SSH_OPTS[@]}" -- "$target" 'powershell -NoProfile -ExecutionPolicy Bypass' \
             '-File .herdr-fold\prepare-windows.ps1 '"$lang$([ "$mode" = remove ] && echo ' -Remove')" \
             </dev/null | tr -d '\r' | machine_phases
    )
  else
    stage_payload "$tmp" prepare-unix.sh "$mode"
    COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -C "$tmp" -czf - . |
      ssh "${SSH_OPTS[@]}" -- "$target" \
        'rm -rf ~/.herdr-fold && mkdir -p ~/.herdr-fold && tar -xzf - -C ~/.herdr-fold' \
      && (                # pipefail: the exit status is the prepare script's, not the filter's
        set -o pipefail
        ssh "${SSH_OPTS[@]}" -- "$target" \
          "HERDR_FOLD_LANG=$lang bash ~/.herdr-fold/prepare-unix.sh${mode:+ --$mode}" </dev/null | machine_phases
      )
  fi
}

# machine_phases — passes the machine's lines on; its section headers ("  -- …") are also the loading line's phase
machine_phases() {
  local line
  while IFS= read -r line || [ -n "$line" ]; do
    printf '%s\n' "$line"
    case "$line" in "  -- "*) loading_phase "${line#  -- }" ;; esac
  done
}

# The machine-side part of step 2 on Linux / macOS (TEXTS: the texts of the lines it prints, as shell assignments)
finish_unix() {
  ssh "${SSH_OPTS[@]}" -- "$1" "$2 bash -s" <<'EOF'
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
# herdr-sidebar of the machine's own: it does what herdr-fold's sidebar does, so it is named, and left as it is
herdr plugin list 2>/dev/null | grep -qF "herdr-sidebar (herdr-sidebar)" && echo "  [-] $T_SIDEBAR_TOO"
for a in claude codex; do
  if ! command -v $a >/dev/null 2>&1; then echo "  [-] ${T_AGENT_MISSING//@@/$a}"; continue; fi
  if [ $a = codex ] && [ ! -d "$HOME/.codex" ]; then echo "  [-] $T_CODEX_SIGN_IN"; continue; fi
  herdr integration install $a >/dev/null 2>&1 && echo "  [✓] herdr ↔ $a" || echo "  [!] ${T_AGENT_FAILED//@@/$a}"
done
EOF
}

# Step 2 (after connecting, with herdr running on the machine): the herdr ↔ Claude/Codex integration, a
#    herdr-sidebar of the machine's own named (Linux, macOS, Windows), then from the central Mac: linking the sessions
#    and tab-layout plugins, and the sidebar back in every column
finish_machine() {
  local name=$1 target=$2 os=$3 out rc
  if [ "$os" = windows ]; then
    out=$(loading "$(t machines.finishing)" win_ps "$target" '
$env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
  [Environment]::GetEnvironmentVariable("Path", "Machine")
$h = (Get-Command herdr -ErrorAction SilentlyContinue).Source
if (-not $h) { $h = "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" }
foreach ($a in "claude", "codex") {
  if (-not (Get-Command $a -ErrorAction SilentlyContinue)) {
    "  [-] " + '"$(ps_quote "$(t machines.agent_missing @@)")"'.Replace("@@", $a); continue }
  if ($a -eq "codex" -and -not (Test-Path "$env:USERPROFILE\.codex")) {
    "  [-] " + '"$(ps_quote "$(t machines.codex_sign_in)")"'; continue }
  & $h integration install $a *> $null
  if ($LASTEXITCODE -eq 0) { "  [✓] herdr ↔ $a" } else {
    "  [!] " + '"$(ps_quote "$(t machines.integration_failed @@)")"'.Replace("@@", $a) } }
if ((& $h plugin list 2>$null | Out-String) -match "herdr-sidebar \(herdr-sidebar\)") {
  "  [-] " + '"$(ps_quote "$(t machines.herdr_sidebar_too)")"' }'); rc=$?
    printf '%s\n' "$out" | summarize "$(t machines.finishing)" "$rc"
  else
    # the texts of the lines printed on the machine (@@ stands for the agent's name)
    local texts="T_SIDEBAR_TOO=$(sh_quote "$(t machines.herdr_sidebar_too)")"
    texts+=" T_CODEX_SIGN_IN=$(sh_quote "$(t machines.codex_sign_in)")"
    texts+=" T_AGENT_MISSING=$(sh_quote "$(t machines.agent_missing @@)")"
    texts+=" T_AGENT_FAILED=$(sh_quote "$(t machines.integration_failed @@)")"
    out=$(loading "$(t machines.finishing)" finish_unix "$target" "$texts"); rc=$?
    printf '%s\n' "$out" | summarize "$(t machines.finishing)" "$rc"
  fi
  loading "$(t machines.linking)" link_plugins "$name" "$target" "$os"
}

# link_plugins <name> <target> <os> — AI Sessions and the tab layout linked on the machine (said in one line),
# then the right column put back in its workspaces: a dozen commands over SSH, so it runs under the loading
link_plugins() {
  local name=$1 target=$2 os=$3 home plugin tl linked=()
  home=$(remote_home "$target" "$os")
  plugin="$home/.config/herdr-fold/plugins/sessions-view" tl="$home/.config/herdr-fold/plugins/tab-layout"
  if [ "$os" = windows ]; then
    plugin="$home\\.config\\herdr-fold\\plugins\\sessions-view" tl="$home\\.config\\herdr-fold\\plugins\\tab-layout"
  fi
  herdr --machine "$name" plugin link "$plugin" >/dev/null 2>&1 \
    && { herdr --machine "$name" plugin action invoke "$([ "$os" = windows ] && echo apply-windows || echo apply)" \
           --plugin herdr-fold.sessions-view >/dev/null 2>&1
         linked+=("$(t install.plugin_sessions)"); } \
    || warn "$(t machines.sessions_failed "$name" "$plugin")"
  herdr --machine "$name" plugin link "$tl" >/dev/null 2>&1 \
    && linked+=("$(t install.plugin_tab_layout)") \
    || warn "$(t machines.tab_layout_failed "$name" "$tl")"
  [ ${#linked[@]} = 0 ] || ok "$(t install.plugins "$(joined "${linked[@]}")")"
  # workspaces left without the right column (sidebar + terminal) get it back
  python3 "$HOME/.config/herdr-fold/restore_panes.py" --machine "$name"
}

# add_to_app NAME TARGET — with the Herdr app part installed (install.sh's question), the machine joins the app's
# core too, which copies itself there; one the app has already is left as it is, and not recorded
add_to_app() {
  local hc out
  grep -qxF herdr-fold.app "$HOME/.local/state/herdr-fold/plugins.txt" 2>/dev/null || return 0
  hc=$(hc_bin) || { warn "$(t machines.app_no_hc "$1")"; return 0; }
  if "$hc" machine ls --json 2>/dev/null | python3 -c '
import json, sys
try:
    machines = json.load(sys.stdin).get("machines", [])
except (ValueError, AttributeError):                 # no list: as if the app had none
    machines = []
sys.exit(0 if any(isinstance(m, dict) and m.get("name") == sys.argv[1] for m in machines) else 1)' "$1"; then
    verbose && have "$(t machines.app_already "$1")"
    return 0
  fi
  if out=$("$hc" machine add "$2" --name "$1" --install 2>&1 </dev/null); then
    mkdir -p "$(dirname "$APP_MACHINES")" && echo "$1" >> "$APP_MACHINES"
    ok "$(t machines.app_added "$1")"
  else
    warn "$(t machines.app_failed "$1" "${out##*$'\n'}")"
  fi
}

cmd_add() {
  local failed=0
  while IFS='|' read -r name target os <&3; do
    step "$(t machines.heading "$name" "$target" "$os")"
    reachable "$target" || { failed=1; continue; }
    prepare_files "$target" "$os" || { failed=1; continue; }
    if [ -n "$(machine_field "$name" id)" ]; then
      verbose && have "$(t machines.already_connected)"
    else
      note "$(t machines.herdr_asks_install)"
      note "$(t machines.herdr_asks_stop)"
      herdr machine add "$target" --label "$name" </dev/tty \
        || { warn "$(t machines.connect_failed)"; failed=1; continue; }
    fi
    finish_machine "$name" "$target" "$os"
    add_to_app "$name" "$target"
  done 3< <(machines "$@")
  return $failed
}

cmd_prepare() {
  while IFS='|' read -r name target os <&3; do
    step "$(t machines.heading "$name" "$target" "$os")"
    reachable "$target" || continue
    prepare_files "$target" "$os" || continue
    [ -n "$(machine_field "$name" id)" ] && finish_machine "$name" "$target" "$os"
  done 3< <(machines "$@")
}

# remove <machine>: what this package put on it comes off (the machine's own files and settings come back), then it
# is disconnected in herdr and taken off the machine list
cmd_remove() {
  local name=${1:-} target os id
  IFS='|' read -r _ target os < <(machines "$name")
  if [ -z "$name" ] || [ -z "${target:-}" ]; then fail "$(t machines.not_listed "$name")"; return 1; fi
  step "$(t machines.heading "$name" "$target" "$os")"
  reachable "$target" || return 1
  prepare_files "$target" "$os" remove || return 1
  id=$(machine_field "$name" id)
  if [ -n "$id" ]; then
    herdr machine remove "$id" >/dev/null 2>&1 && ok "$(t machines.disconnected "$name")" \
      || warn "$(t machines.disconnect_failed "$name" "$id")"
  fi
  remove_from_app "$name"
  remove_from_list "$name" && ok "$(t machines.off_the_list "$name")"
}

# sourced (the tests): only the functions above
[ "${BASH_SOURCE[0]}" = "$0" ] || return 0
case "${1:-status}" in
  status|tailscale|sshconfig|manual|pick|new|add|prepare) take_over_connected; use_config_hosts ;;
esac
case "${1:-status}" in
  status)  shift $(( $# > 0 )); cmd_status "$@" ;;
  tailscale) cmd_tailscale ;;
  sshconfig) cmd_sshconfig ;;
  manual)  cmd_manual ;;
  pick)    cmd_pick ;;
  new)     cmd_new ;;
  add)     shift; cmd_add "$@" ;;
  prepare) shift; cmd_prepare "$@" ;;
  remove)  shift; cmd_remove "$@" ;;
  -h|--help|help) echo "$(t machines.help)" ;;
  *) echo "$(t machines.unknown_command "$1")" >&2; exit 1 ;;
esac
