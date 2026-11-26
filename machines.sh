#!/bin/bash
# Remote machines (Linux, macOS, Windows) in herdr on the central Mac: their spaces show in herdr's sidebar, while
# Claude/Codex, the sidebar and the terminal run on the machine. install.sh calls it; run it alone to add a machine.
# Commands: ./machines.sh help (the machines.help key of src/lang/<language>.txt).
set -u
cd "$(dirname "$0")" || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
. "$DOT/src/remote.sh"

core_list() { python3 "$DOT/core/machines.py" "$@"; }    # the list's own reader and writer (core/machines.py)

# remove_from_list NAME — takes NAME's line off the machine list (herdr-fold's ssh file follows it)
remove_from_list() {
  local tmp; tmp=$(mktemp)
  awk -F'|' -v n="$1" '{ name = $1; gsub(/^[ \t]+|[ \t]+$/, "", name) } name != n' "$MACHINE_LIST" > "$tmp" \
    && mv "$tmp" "$MACHINE_LIST" && core_list hosts "$MACHINE_LIST"
}

# "name|target|os|key|routes" lines from the machine list (filtered to the given names); an older line has no key or
# routes yet
machines() {
  [ -f "$MACHINE_LIST" ] || return 0
  grep -vE '^[[:space:]]*(#|$)' "$MACHINE_LIST" | while IFS='|' read -r name target os key routes; do
    name=$(echo "$name" | trim); target=$(echo "$target" | trim); os=$(echo "$os" | trim)
    key=$(echo "${key:-}" | trim); routes=$(echo "${routes:-}" | trim)
    if [ $# -gt 0 ]; then
      case " $* " in *" $name "*) ;; *) continue ;; esac
    fi
    echo "$name|$target|$os|$key|$routes"
  done
}

# add_line NAME TARGET OS [KEY] — a machine onto the list with its host key's fingerprint, else the one known_hosts
# trusts where TARGET leads; a new list starts with the header that explains its fields
add_line() { core_list add "$MACHINE_LIST" "$@"; }

# Without a machine list yet (e.g. machines connected in herdr by hand), the machines connected in herdr go onto it,
# with their OS; an unreachable one waits for the next run. An existing list is left as it is, so a machine taken off it
# stays off.
take_over_connected() {
  local name target os
  [ -f "$MACHINE_LIST" ] && return 0
  of_parts tui $(installed_parts) || return 0                        # herdr's machines: the TUI's
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
  local hosts name target alias tmp
  hosts=$(ssh_config_hosts plain)
  [ -n "$hosts" ] || return 0
  while IFS='|' read -r name target _ <&3; do
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

said() { _line "  " "$@"; }        # a line at the questions' own indent, saying what the next one is about

# route_on NETWORK — a route's network in a sentence ("on Tailscale"; "at that address" for one not known)
route_on() {
  case $1 in
    tailscale) printf '%s' "$(t machines.route_on_tailscale)" ;;
    netbird) printf '%s' "$(t machines.route_on_netbird)" ;;
    local) printf '%s' "$(t machines.route_on_local)" ;;
    *) printf '%s' "$(t machines.route_at)" ;;
  esac
}

# other_routes NAME — NAME's routes besides the one in use, a line each under its heading ("also Tailscale: …")
other_routes() {
  local network address
  while IFS='|' read -r network address; do
    case $network in
      tailscale) note "$(t machines.also_on "$(t machines.network_tailscale)" "$address")" ;;
      netbird) note "$(t machines.also_on "$(t machines.network_netbird)" "$address")" ;;
      local) note "$(t machines.also_on "$(t machines.network_local)" "$address")" ;;
      *) note "$(t machines.also_at "$address")" ;;
    esac
  done < <(core_list routes "$MACHINE_LIST" "$1")
}

# The listed machines' host keys, "name|fingerprint" a line: the one on the list, else the one known_hosts trusts
machine_keys() { [ ! -f "$MACHINE_LIST" ] || core_list keys "$MACHINE_LIST"; }

# identify KNOWN KEYS NETWORK NAME [ADDRESS…] — what a machine offered is, KNOWN machine_keys' lines: "listed|NAME" at
# a listed machine's own name or address, "known|NAME" at another of its routes, "route|NAME|NETWORK" when its key is
# NAME's (another way to it), else "new|the name it gets|NETWORK"
identify() { local known=$1; shift; core_list identify "$MACHINE_LIST" "$@" <<< "$known"; }

# keyscan LABEL HOST [PORT] — what ssh-keyscan reads of HOST's ED25519 key in 5 s at most, its lines as known_hosts has
# them, under the waiting line "checking LABEL's key" (a line, as reaching one: its own timeout ends it soon)
keyscan() {
  LOADING_PLAIN=1 loading "$(t machines.checking_key "$1")" ssh-keyscan -T 5 -t ed25519 ${3:+-p "$3"} -- "$2" \
    2>/dev/null | awk '!/^#/ && $2 == "ssh-ed25519"'
}
# scanned_key LABEL HOST [PORT] — the ED25519 key HOST shows now, "ssh-ed25519 AAAA…"
scanned_key() { keyscan "$@" | awk '{ print $2, $3; exit }'; }
# fingerprint_of KEYS — the fingerprint of the first of KEYS (key or known_hosts lines), as ssh-keygen -l prints it
fingerprint_of() { [ -z "$1" ] || printf '%s\n' "$1" | ssh-keygen -lf - 2>/dev/null | awk '{ print $2; exit }'; }

# tailscale_key_ok NAME DNS KEYS — false, said, when the machine at DNS shows another ED25519 key than those Tailscale
# knows for it (KEYS): nothing of it is added, and the key it showed is never trusted. No answer: as before
tailscale_key_ok() {
  local shows; shows=$(fingerprint_of "$(scanned_key "$1" "$2")")
  [ -z "$shows" ] || printf ',%s,' "$3" | grep -qF ",$shows," && return 0
  warn "$(t machines.key_mismatch "$1")"
  return 1
}

# connected NAME — herdr (with the TUI) or the Herdr app (with its part) has NAME already: it keeps the target it has
connected() {
  { of_parts tui $(installed_parts) && [ -n "$(machine_field "$1" id)" ]; } \
    || grep -qxF "$1" "$APP_MACHINES" 2>/dev/null
}

# include_hosts — whether ~/.ssh/config includes herdr-fold's own Hosts: already, or after its question, asked once (a
# no is kept and asked again only by ./machines.sh include)
include_hosts() {
  core_list included "$HOME/.ssh/config" && return 0
  [ ! -f "$INCLUDE_REFUSED" ] || return 1
  note "$(t machines.include_line)"
  if ! ask "$(t machines.include_ask)" y; then
    mkdir -p "$(dirname "$INCLUDE_REFUSED")" && : > "$INCLUDE_REFUSED"
    return 1
  fi
  core_list include "$HOME/.ssh/config" && record_outside ssh-include
}

# also_route NAME NETWORK ADDRESS KEY — a machine offered whose host key KEY is NAME's: the same machine, at ADDRESS.
# A yes makes that a route of NAME's (the Include line first); one herdr has not connected yet is then reached through
# its own Host, its key trusted under that Host's name. Without the Include line it keeps one route.
also_route() {
  local name=$1 network=$2 address=$3 key=$4 move= alias
  said "$(t machines.also_route "${address#*@}" "$name" "$(route_on "$network")")"
  if [ -f "$INCLUDE_REFUSED" ] && ! core_list included "$HOME/.ssh/config"; then
    skip "$(t machines.include_refused "$name")"; return 0
  fi
  ask "$(t machines.also_route_ask)" y || return 0
  include_hosts || { skip "$(t machines.include_refused "$name")"; return 0; }
  connected "$name" || move=move
  alias=$(core_list route "$MACHINE_LIST" "$name" "$key" "$network" "$address" $move) && [ -n "$alias" ] || return 0
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  printf '%s\n' "$alias" >> "$HOME/.ssh/known_hosts"
  record_outside "known-host herdr-fold.$name"
}

# include: the Include line of herdr-fold's Hosts at the top of ~/.ssh/config, asked again after a no
cmd_include() {
  if core_list included "$HOME/.ssh/config"; then have "$(t machines.include_done)"; return 0; fi
  rm -f "$INCLUDE_REFUSED"
  include_hosts && core_list hosts "$MACHINE_LIST" && ok "$(t machines.include_done)"
}

# The per-machine loops read the list from file descriptor 3, not from standard input: that way the ssh and herdr
# commands inside the loop cannot swallow the rest of the list (otherwise only the first machine would get a turn).
cmd_status() {
  local any=
  while IFS='|' read -r name target os _ routes <&3; do
    any=1
    echo "== $(t machines.heading "$name" "$target" "$os")"
    [ -z "$routes" ] || other_routes "$name"
    reachable "$target" || continue
    if ! of_parts tui $(installed_parts); then :
    elif [ -n "$(machine_field "$name" id)" ]; then ok "$(t machines.connected)"
    else note "$(t machines.not_connected "$name")"; fi
    note "$(tools_line "$target" "$os")"
  done 3< <(machines "$@")
  [ -n "$any" ] || skip "$(t machines.none_listed)"
}

# The machines on the Tailscale network that can be yours (Linux, macOS, Windows; tagged and shared-in ones too), one
# "short|dns|os|online/offline|ips|ED25519 host key fingerprints" line each; [FILE] gets a word for each one left out
# (exit, shared, expired). Exit status 1 without Tailscale, 2 if it does not answer.
tailnet_peers() {
  local ts; ts=$(tailscale_bin) || return 1
  "$ts" status --json 2>/dev/null | python3 -c '
import base64, binascii, hashlib, json, sys

def left_out(peer, dns):
    """Why a peer is none of yours: a Mullvad exit node, a node of someone a machine is shared with, an expired key."""
    if peer.get("Location") or dns.lower().split(".")[-3:] == ["mullvad", "ts", "net"]:
        return "exit"
    if peer.get("ShareeNode"):
        return "shared"
    if peer.get("Expired"):
        return "expired"
    return None

def fingerprints(keys):
    """Its ED25519 host keys (sshHostKeys) as ssh-keygen -l prints them; a malformed one is passed over."""
    found = []
    for key in keys if isinstance(keys, list) else []:
        parts = str(key).split()
        try:
            blob = base64.b64decode(parts[1], validate=True)
        except (IndexError, binascii.Error):
            continue
        if parts[0] == "ssh-ed25519" and blob.startswith(b"\0\0\0\x0bssh-ed25519"):
            found.append("SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("="))
    return ",".join(found)

d, skipped = json.load(sys.stdin), []
for p in sorted((d.get("Peer") or {}).values(), key=lambda p: p.get("DNSName", "")):
    os_ = {"linux": "linux", "windows": "windows", "macOS": "macos"}.get(p.get("OS"))
    dns = p.get("DNSName", "").rstrip(".")
    why = left_out(p, dns)
    if os_ and why:                                    # a phone or a TV is neither offered nor counted
        skipped.append(why)
    elif os_:
        print("|".join([dns.split(".")[0], dns, os_, "online" if p.get("Online") else "offline",
                        ",".join(p.get("TailscaleIPs") or []), fingerprints(p.get("sshHostKeys"))]))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w") as f:
        f.write("".join(word + "\n" for word in skipped))' "$@" || return 2
}

# tailnet_left_out WORDS — the line counting the machines tailnet_peers left out (WORDS: its words, a line each)
tailnet_left_out() {
  local word n said=()
  for word in exit shared expired; do
    n=$(printf '%s\n' "$1" | grep -cx "$word")
    case "$word:$n" in
      *:0) ;;
      exit:1) said+=("$(t machines.left_out_exit_node)") ;;
      exit:*) said+=("$(t machines.left_out_exit_nodes "$n")") ;;
      shared:1) said+=("$(t machines.left_out_shared_node)") ;;
      shared:*) said+=("$(t machines.left_out_shared_nodes "$n")") ;;
      expired:1) said+=("$(t machines.left_out_expired_node)") ;;
      expired:*) said+=("$(t machines.left_out_expired_nodes "$n")") ;;
    esac
  done
  [ ${#said[@]} = 0 ] && return 0
  skip "$(t machines.tailscale_skipped "$(printf '%s\n' "$1" | grep -c .)" "$(joined "${said[@]}")")"
}

# Pick from the machines on the Tailscale network, one question each
cmd_tailscale() {
  local peers status hosts known left_file left; left_file=$(mktemp)
  peers=$(tailnet_peers "$left_file"); status=$?
  left=$(cat "$left_file"); rm -f "$left_file"
  case $status in
    1) skip "$(t machines.no_tailscale)"; return 0 ;;
    2) warn "$(t machines.tailscale_failed)"; return 0 ;;
  esac
  [ -n "$peers" ] || { skip "$(t machines.tailscale_empty)"; tailnet_left_out "$left"; return 0; }
  hosts=$(ssh_config_hosts); known=$(machine_keys)
  local added=0 kept=() short dns os state ips given keys alias name user found listed_as shown mine shows
  while IFS='|' read -r short dns os state ips given <&3; do
    # its ~/.ssh/config Host, if it has one: then it goes on the list under that name (with that file's user and key).
    # The Host's name or its HostName is the machine's name or address here, as cmd_sshconfig leaves such a Host to
    # this step (its HostName may be another address of it, such as a public name)
    alias=$(printf '%s\n' "$hosts" | awk -F'|' -v d="$dns" -v s="$short" -v ips=",$ips," '{ h = $2; sub(/.*@/, "", h) }
      $1 == d || $1 == s || h == d || h == s || index(ips, "," h ",") { print $1; exit }')
    name=${alias:-$short}
    # where it would connect: for a Host, that file's address (a device named like it may not be that machine)
    shown=$(printf '%s\n' "$hosts" | awk -F'|' -v a="$alias" 'a != "" && $1 == a { print $2; exit }')
    shown=${shown:-$dns}
    # its host key: Tailscale's record of it, else, when a listed machine's could be it, the one it shows now
    keys=$given
    [ -n "$keys" ] || [ -z "$known" ] || [ "$state" = offline ] \
      || keys=$(fingerprint_of "$(scanned_key "$name" "$dns")")
    found=$(identify "$known" "$keys" tailscale "$name" "$short" "$dns" ${ips//,/ })
    listed_as=$(cut -d'|' -f2 <<< "$found")
    case $found in
      listed\|*)
        ask "$(t machines.select_ask_listed "$name" "$os" "$shown")" y && { kept+=("$listed_as"); continue; }
        remove_from_list "$listed_as"; note "$(t machines.removed_from_list "$listed_as")"; continue ;;
      known\|*) kept+=("$listed_as"); continue ;;
    esac
    # another way to a listed machine only when it answers with that very key now: Tailscale's list is what a peer says
    # of itself, so an offline peer, or one that does not answer, is never taken for it
    case $found in
      route\|*)
        mine=$(printf '%s\n' "$known" | awk -F'|' -v n="$listed_as" '$1 == n { print $2; exit }'); shows=
        [ "$state" = offline ] || shows=$(fingerprint_of "$(scanned_key "$name" "$dns")")
        if [ -z "$shows" ]; then skip "$(t machines.route_unchecked "$dns" "$listed_as")"; continue; fi
        if [ "$shows" != "$mine" ]; then warn "$(t machines.route_key_mismatch "$dns" "$listed_as")"; continue; fi
        also_route "$listed_as" tailscale "$dns" "$mine"; kept+=("$listed_as"); continue ;;
    esac
    # before a machine goes on the list: the key it shows must be one Tailscale's record has
    [ -z "$given" ] || [ "$state" = offline ] || tailscale_key_ok "$name" "$dns" "$given" || continue
    name=$listed_as                       # its own, or with -tailscale where a machine of that name is another one
    ask "$(t machines.select_ask "$name" "$os" "$shown" \
      "$([ "$state" = offline ] && echo " $(t machines.select_offline)")")" n || continue
    if [ -n "$alias" ]; then
      add_line "$name" "$alias" "$os" "${keys%%,*}"
    else
      # the suggested user: root on Linux, elsewhere the same user name as on this Mac
      [ "$os" = linux ] && user=root || user=${USER:-$(id -un)}
      user=$(prompt "$(t machines.select_user)" "$user")
      add_line "$name" "$user@$dns" "$os" "${keys%%,*}"
    fi
    added=$((added + 1)); known=$(machine_keys)
  done 3<<< "$peers"
  added_summary "$added" ${kept[@]+"${kept[@]}"}        # (bash 3.2 + set -u: an empty array is unset)
  tailnet_left_out "$left"
}

# The machines on the NetBird network, as core/networks.py reads NetBird's own status (5 s at most, under a waiting
# line): a "state|this Mac's address" line, then a "name|fqdn|ip|status|path|latency_ms" line each. Nothing without it
netbird_peers() {
  local nb; nb=$(netbird_bin) || return 1
  LOADING_PLAIN=1 loading "$(t machines.asking_netbird)" python3 "$DOT/core/networks.py" netbird "$nb"
}

# Pick from the machines on the NetBird network, one question each. NetBird tells no OS (it is read by logging in, so
# a phone that answers no SSH is not added) and keeps no host key: a machine's is the one it shows now
cmd_netbird() {
  local said state peers
  said=$(netbird_peers) || { skip "$(t machines.no_netbird)"; return 0; }
  state=$(head -n 1 <<< "$said" | cut -d'|' -f1); peers=$(tail -n +2 <<< "$said")
  case $state in
    signed_out) warn "$(t machines.netbird_signed_out)"; return 0 ;;
    expired) warn "$(t machines.netbird_expired)"; return 0 ;;
    on|no_management) ;;                  # out of its management server's reach: the machines it was told of last
    *) warn "$(t machines.netbird_failed)"; return 0 ;;
  esac
  if [ -z "$peers" ]; then
    if [ "$state" = on ]; then skip "$(t machines.netbird_empty)"; else warn "$(t machines.netbird_failed)"; fi
    return 0
  fi
  local hosts known added=0 kept=() short fqdn ip alias name shown key found listed_as user target os
  hosts=$(ssh_config_hosts); known=$(machine_keys)
  while IFS='|' read -r short fqdn ip _ <&3; do
    # its ~/.ssh/config Host by its name or address, as in cmd_tailscale: then under that name, with that file's user
    alias=$(printf '%s\n' "$hosts" | awk -F'|' -v d="$fqdn" -v s="$short" -v i="$ip" '{ h = $2; sub(/.*@/, "", h) }
      $1 == d || $1 == s || h == d || h == s || (i != "" && h == i) { print $1; exit }')
    name=${alias:-$short}
    shown=$(printf '%s\n' "$hosts" | awk -F'|' -v a="$alias" 'a != "" && $1 == a { print $2; exit }')
    shown=${shown:-$fqdn}
    # its host key, when a listed machine's could be it: the one it shows now. NetBird's list is what a peer says of
    # itself, so one that shows none (off, silent) is never another way to a listed machine
    key=
    [ -z "$known" ] || key=$(fingerprint_of "$(scanned_key "$name" "$fqdn")")
    found=$(identify "$known" "$key" netbird "$name" "$short" "$fqdn" ${ip:+"$ip"})
    listed_as=$(cut -d'|' -f2 <<< "$found")
    case $found in
      listed\|*)
        os=$(machines "$listed_as" | cut -d'|' -f3)
        ask "$(t machines.select_ask_listed "$name" "$os" "$shown")" y && { kept+=("$listed_as"); continue; }
        remove_from_list "$listed_as"; note "$(t machines.removed_from_list "$listed_as")"; continue ;;
      known\|*) kept+=("$listed_as"); continue ;;
      route\|*) also_route "$listed_as" netbird "$fqdn" "$key"; kept+=("$listed_as"); continue ;;   # its key, just now
    esac
    name=$listed_as                         # its own, or with -netbird where a machine of that name is another one
    ask "$(t machines.select_ask_netbird "$name" "$shown")" n || continue
    if [ -n "$alias" ]; then
      target=$alias
    else
      user=$(prompt "$(t machines.select_user)" root)              # no OS to go by: root, as by hand
      target="$user@$fqdn"
    fi
    reachable "$target" || continue
    os=$(remote_os "$target")
    add_line "$name" "$target" "$os" "$key"
    ok "$(t machines.added "$name" "$os")"
    added=$((added + 1)); known=$(machine_keys)
  done 3<<< "$peers"
  added_summary "$added" ${kept[@]+"${kept[@]}"}        # (bash 3.2 + set -u: an empty array is unset)
}

# The machines of ~/.ssh/config (Include-d files too, but herdr-fold's own Hosts), one "alias|user@host" line each —
# no patterns or git hosts
ssh_config_hosts() {   # [plain]: only the Hosts that change nothing but the name (see use_config_hosts)
  [ -f "$HOME/.ssh/config" ] || return 0
  python3 - "$HOME/.ssh/config" "${1:-}" "$SSH_HOSTS" <<'PY'
import glob, os, re, sys
GIT = re.compile(r"(^|\.)(github\.com|gitlab\.com|bitbucket\.org|ssh\.dev\.azure\.com|vs-ssh\.visualstudio\.com)$",
                 re.I)
OWN = os.path.realpath(sys.argv[3])     # herdr-fold's ssh file: its Hosts are routes of the list's machines

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
                        if os.path.realpath(inc) != OWN:
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
    if any(ch in alias for ch in "*?!") or c.get("user") == "git" or GIT.search(host) or GIT.search(alias) \
            or alias.startswith("herdr-fold."):
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

# Pick from the machines in ~/.ssh/config, one question each, no unless said yes (a Host line may name a machine not
# meant for this: a jump host, a client's server) — those on the Tailscale or NetBird network are left to its own step
# (cmd_tailscale, cmd_netbird), asked after it. One imported earlier is asked too: no takes it off the list.
cmd_sshconfig() {
  [ -f "$HOME/.ssh/config" ] || { skip "$(t machines.no_ssh_config)"; return 0; }
  local hosts peers; hosts=$(ssh_config_hosts)
  [ -n "$hosts" ] || { skip "$(t machines.ssh_config_empty)"; return 0; }
  peers=$(tailnet_peers 2>/dev/null \
    | awk -F'|' '{ print $1; print $2; n = split($5, ip, ","); for (i = 1; i <= n; i++) print ip[i] }'
    netbird_peers 2>/dev/null | awk -F'|' 'NR > 1 { print $1; print $2; if ($3 != "") print $3 }')
  local added=0 kept=() alias where os known key reach found listed_as
  known=$(machine_keys)
  while IFS='|' read -r alias where <&3; do
    printf '%s\n' "$alias" "${where#*@}" | grep -qxF -f <(printf '%s\n' "$peers" | grep .) && continue
    # its host key, when a listed machine's could be it: what answers where the Host leads (none past a jump or proxy)
    key= reach=
    [ -z "$known" ] || reach=$(core_list resolve "$alias")
    [ -z "$reach" ] || key=$(fingerprint_of "$(scanned_key "$alias" "$(cut -d'|' -f1 <<< "$reach")" \
      "$(cut -d'|' -f2 <<< "$reach")")")
    found=$(identify "$known" "$key" "" "$alias" "${where#*@}")
    listed_as=$(cut -d'|' -f2 <<< "$found")
    case $found in
      listed\|*)
        ask "$(t machines.sshconfig_ask_listed "$alias" "$where")" y && { kept+=("$listed_as"); continue; }
        remove_from_list "$listed_as"; note "$(t machines.removed_from_list "$listed_as")"; continue ;;
      known\|*) kept+=("$listed_as"); continue ;;
      route\|*) also_route "$listed_as" "$(cut -d'|' -f3 <<< "$found")" "$(cut -d'|' -f3 <<< "$reach")" "$key"
        kept+=("$listed_as"); continue ;;
    esac
    ask "$(t machines.sshconfig_ask "$alias" "$where")" n || continue
    reachable "$alias" || continue
    os=$(remote_os "$alias")
    add_line "$listed_as" "$alias" "$os" "$key"
    ok "$(t machines.added "$listed_as" "$os")"
    added=$((added + 1)); known=$(machine_keys)
  done 3<<< "$hosts"
  added_summary "$added" ${kept[@]+"${kept[@]}"}        # (bash 3.2 + set -u: an empty array is unset)
}

# confirm_host_key HOST [KEYS] — a machine typed in by hand that ssh does not know yet: its ED25519 fingerprint (the
# one the docs have you compare) is confirmed first, and exactly that key (KEYS, ssh-keyscan's lines, read here
# without) goes into ~/.ssh/known_hosts, so ssh refuses any other. No ED25519 key (or no answer): not added.
confirm_host_key() {
  local keys=${2:-} fp
  ssh-keygen -F "$1" >/dev/null 2>&1 && return 0
  [ $# -ge 2 ] || keys=$(keyscan "$1" "$1")
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

# unique_name NAME [NETWORK] — NAME, else NAME-NETWORK, else NAME-2, NAME-3… when the list has a machine called so
unique_name() { core_list name "$MACHINE_LIST" "$1" "${2:-}"; }

# host_keys HOST — HOST's ED25519 key: the one known_hosts trusts for it, else what it shows now (ssh-keyscan's lines)
host_keys() {
  local trusted; trusted=$(ssh-keygen -F "$1" 2>/dev/null | awk '!/^#/ && $2 == "ssh-ed25519"')
  if [ -n "$trusted" ]; then printf '%s\n' "$trusted"; else keyscan "$1" "$1"; fi
}

# Add a machine by SSH address; the OS (Linux / macOS / Windows) is detected by logging in. One that shows the key of
# a machine on the list is that machine, at another address: a route of it, not a second machine
cmd_manual() {
  local user host target name os keys key found
  while :; do
    user=$(prompt "$(t machines.manual_user)" root)
    host=$(prompt "$(t machines.manual_host)")
    if [ -n "$host" ] && listed_target "$user@$host"; then
      note "$(t machines.already_listed "$user@$host")"
    elif [ -n "$host" ]; then
      keys=$(host_keys "$host"); key=$(fingerprint_of "$keys")
      found=$(identify "$(machine_keys)" "$key" "" "$host" "$host")
      if [ "${found%%|*}" = route ]; then
        also_route "$(cut -d'|' -f2 <<< "$found")" "$(cut -d'|' -f3 <<< "$found")" "$user@$host" "$key"
      elif confirm_host_key "$host" "$keys"; then
        target="$user@$host"
        if reachable "$target"; then
          os=$(remote_os "$target")
          # the name in herdr's sidebar: an IP address as it is, a host name up to its first dot (made unique)
          case "$host" in *[!0-9.]*) name=${host%%.*} ;; *) name=$host ;; esac
          name=$(unique_name "$name" "$(cut -d'|' -f3 <<< "$found")")
          add_line "$name" "$target" "$os" "$key"
          ok "$(t machines.added "$name" "$os")"
        fi
      fi
    fi
    ask "$(t machines.manual_more)" n || break
  done
}

# The installer's step 8, and Ctrl+B, Shift+M: a line saying any network works, then where to read new machines from —
# each source on its own question, its machines then one by one: ~/.ssh/config, the Tailscale and NetBird networks
# (each skips the machines already on the list), an address typed in. Exit status 1 if none was asked for.
cmd_pick() {
  local picked=1
  note "$(t machines.any_network)"
  if [ -f "$HOME/.ssh/config" ] && ask "$(t machines.pick_sshconfig)" n; then
    has_ssh_key || make_ssh_key; cmd_sshconfig; picked=0
  fi
  if [ -n "$(tailscale_bin)" ] && ask "$(t machines.pick_tailscale)" n; then
    has_ssh_key || make_ssh_key; cmd_tailscale; picked=0
  fi
  if [ -n "$(netbird_bin)" ] && ask "$(t machines.pick_netbird)" n; then
    has_ssh_key || make_ssh_key; cmd_netbird; picked=0
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

# remote_files KIND [PART...] — the files of remote/files.txt for a KIND of machine (unix | windows) and the PARTs
# (every part's, unnamed), as "path in the package|location on the machine" lines; a path with a * stands for every
# matching file (its location is a folder)
remote_files() {
  local kind=$1 src rel kinds part f; shift
  grep -vE '^[[:space:]]*(#|$)' "$DOT/remote/files.txt" | while IFS='|' read -r src rel kinds part; do
    src=$(echo "$src" | trim); rel=$(echo "$rel" | trim); kinds=$(echo "$kinds" | trim); part=$(echo "$part" | trim)
    [ "$kinds" = all ] || [ "$kinds" = "$kind" ] || continue
    of_parts "$part" "$@" || continue
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
  local stage=$1 script=$2 kind src rel parts
  parts=$(installed_parts | paste -sd' ' -)
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
  while IFS='|' read -r src rel; do stage_file "$DOT/$src" "$rel"; done < <(remote_files "$kind" $parts)
  [ -f "$HOME/.config/herdr-fold/statusline.json" ] \
    && stage_file "$HOME/.config/herdr-fold/statusline.json" .config/herdr-fold/statusline.json
  # with the TUI, its prompt, and the sidebar's colors in the Mac's theme (its theme setter writes them on the Mac):
  # without them a machine's sidebar falls back to the terminal's 16 colors
  case " $parts " in *" tui "*)
    stage_file "$( [ -f "$HOME/.config/starship.toml" ] && echo "$HOME/.config/starship.toml" \
      || echo "$DOT/config/starship.toml")" .config/starship.toml
    local colors=.local/state/herdr/plugins/herdr-fold.sidebar/colors.json
    [ -f "$HOME/$colors" ] && stage_file "$HOME/$colors" "$colors" ;;
  esac
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
copy_and_prepare() {   # copy_and_prepare <tmp> <target> <os> <lang> [remove]: the installed parts' (tui, app)
  local tmp=$1 target=$2 os=$3 lang=$4 mode=${5:-} parts; parts=$(installed_parts | xargs)
  loading_phase "$(t machines.phase_sending)"
  if [ "$os" = windows ]; then
    stage_payload "$tmp/payload" prepare-windows.ps1 "$mode"
    local args="$lang -Parts ${parts// /,}"; [ "$mode" = remove ] && args+=" -Remove"
    (                     # pipefail: the exit status is the prepare script's, not the filters'
      set -o pipefail
      win_put "$target" "$tmp/payload" "$tmp/ssh" \
        && ssh "${SSH_OPTS[@]}" -- "$target" 'powershell -NoProfile -ExecutionPolicy Bypass' \
             "-File .herdr-fold\\prepare-windows.ps1 $args" </dev/null | tr -d '\r' | machine_phases
    )
  else
    stage_payload "$tmp" prepare-unix.sh "$mode"
    COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -C "$tmp" -czf - . |
      ssh "${SSH_OPTS[@]}" -- "$target" \
        'rm -rf ~/.herdr-fold && mkdir -p ~/.herdr-fold && tar -xzf - -C ~/.herdr-fold' \
      && (                # pipefail: the exit status is the prepare script's, not the filter's
        set -o pipefail
        ssh "${SSH_OPTS[@]}" -- "$target" \
          "HERDR_FOLD_LANG=$lang HERDR_FOLD_PARTS='$parts' bash ~/.herdr-fold/prepare-unix.sh${mode:+ --$mode}" \
          </dev/null | machine_phases
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
#    herdr-sidebar of the machine's own named (Linux, macOS, Windows), then from the central Mac: linking the sidebar,
#    AI Sessions and Spaces, and the sidebar back in every column
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

# link_plugins <name> <target> <os> — the sidebar, AI Sessions and Spaces linked (said in one line), then the right
# column put back in its spaces: a dozen commands over SSH, under the loading
link_plugins() {
  local name=$1 target=$2 os=$3 home plugins linked=()
  home=$(remote_home "$target" "$os")
  plugins="$home/.config/herdr-fold/plugins/"
  [ "$os" != windows ] || plugins="$home\\.config\\herdr-fold\\plugins\\"
  herdr --machine "$name" plugin link "${plugins}sidebar" >/dev/null 2>&1 \
    && linked+=("$(t install.plugin_sidebar)") \
    || warn "$(t machines.sidebar_failed "$name" "${plugins}sidebar")"
  herdr --machine "$name" plugin link "${plugins}sessions-view" >/dev/null 2>&1 \
    && { herdr --machine "$name" plugin action invoke "$([ "$os" = windows ] && echo apply-windows || echo apply)" \
           --plugin herdr-fold.sessions-view >/dev/null 2>&1
         linked+=("$(t install.plugin_sessions)"); } \
    || warn "$(t machines.sessions_failed "$name" "${plugins}sessions-view")"
  herdr --machine "$name" plugin link "${plugins}spaces" >/dev/null 2>&1 \
    && linked+=("$(t install.plugin_spaces)") \
    || warn "$(t machines.spaces_failed "$name" "${plugins}spaces")"
  [ ${#linked[@]} = 0 ] || ok "$(t install.plugins "$(joined "${linked[@]}")")"
  # spaces left without the right column (sidebar + terminal) get it back
  python3 "$HOME/.config/herdr-fold/restore_panes.py" --machine "$name"
}

# add_to_app NAME TARGET — the machine joins the Herdr app's core too (cmd_add, with the app's part installed), which
# copies itself there; one the app has already is left as it is, and not recorded
add_to_app() {
  local hc out
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
  local failed=0 parts; parts=$(installed_parts | xargs)
  while IFS='|' read -r name target os _ <&3; do
    step "$(t machines.heading "$name" "$target" "$os")"
    reachable "$target" || { failed=1; continue; }
    prepare_files "$target" "$os" || { failed=1; continue; }
    if ! of_parts tui $parts; then :                                  # herdr's connection: the TUI's
    elif [ -n "$(machine_field "$name" id)" ]; then
      verbose && have "$(t machines.already_connected)"
    else
      note "$(t machines.herdr_asks_install)"
      note "$(t machines.herdr_asks_stop)"
      herdr machine add "$target" --label "$name" </dev/tty \
        || { warn "$(t machines.connect_failed)"; failed=1; continue; }
    fi
    ! of_parts tui $parts || finish_machine "$name" "$target" "$os"
    ! of_parts app $parts || add_to_app "$name" "$target"
  done 3< <(machines "$@")
  return $failed
}

cmd_prepare() {
  while IFS='|' read -r name target os _ <&3; do
    step "$(t machines.heading "$name" "$target" "$os")"
    reachable "$target" || continue
    prepare_files "$target" "$os" || continue
    of_parts tui $(installed_parts) && [ -n "$(machine_field "$name" id)" ] && finish_machine "$name" "$target" "$os"
  done 3< <(machines "$@")
}

# remove <machine>: what this package put on it comes off (the machine's own files and settings come back), then it
# is disconnected in herdr and taken off the machine list
cmd_remove() {
  local name=${1:-} target os id
  IFS='|' read -r _ target os _ < <(machines "$name")
  if [ -z "$name" ] || [ -z "${target:-}" ]; then fail "$(t machines.not_listed "$name")"; return 1; fi
  step "$(t machines.heading "$name" "$target" "$os")"
  reachable "$target" || return 1
  prepare_files "$target" "$os" remove || return 1
  id=; ! of_parts tui $(installed_parts) || id=$(machine_field "$name" id)
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
  status|tailscale|netbird|sshconfig|manual|pick|new|add|prepare) take_over_connected; use_config_hosts ;;
esac
case "${1:-status}" in
  status)  shift $(( $# > 0 )); cmd_status "$@" ;;
  tailscale) cmd_tailscale ;;
  netbird) cmd_netbird ;;
  sshconfig) cmd_sshconfig ;;
  manual)  cmd_manual ;;
  pick)    cmd_pick ;;
  new)     cmd_new ;;
  add)     shift; cmd_add "$@" ;;
  prepare) shift; cmd_prepare "$@" ;;
  remove)  shift; cmd_remove "$@" ;;
  include) cmd_include ;;
  -h|--help|help) echo "$(t machines.help)" ;;
  *) echo "$(t machines.unknown_command "$1")" >&2; exit 1 ;;
esac
