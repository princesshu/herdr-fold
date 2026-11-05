#!/bin/bash
# Copies this machine's (possibly changed) settings back into the repo, except a file of your own settings with
# herdr-fold's between marks (yours never reach the repo) and one edited in the repo but not committed (never
# overwritten). Then runs the privacy check, as what comes back may hold this machine's names.
cd "$(dirname "$0")/.." || exit 1
DOT=$(pwd)
. "$DOT/lib/common.sh"
in_git=; git -C "$DOT" rev-parse --git-dir >/dev/null 2>&1 && in_git=1

package_files | while IFS='|' read -r src rel; do
  dst="$HOME/$rel"
  if grep -qxF '# >>> herdr-fold >>>' "$dst" 2>/dev/null; then
    warn "$(t sync.merged "$rel")"       # your own settings with herdr-fold's between marks: yours stay off the package
  elif [ ! -f "$dst" ]; then
    warn "$(t sync.not_here "$rel")"
  elif cmp -s "$dst" "$DOT/$src"; then
    :
  elif [ -n "$in_git" ] && [ -n "$(git -C "$DOT" status --porcelain -- "$src")" ]; then
    warn "$(t sync.edited "$src")"
  else
    mkdir -p "$(dirname "$DOT/$src")" && cp "$dst" "$DOT/$src"
  fi
done

if [ -n "$in_git" ]; then
  section "$(t sync.changes)"
  git -C "$DOT" status --short
fi
# the files' privacy check (tests/test_repo_privacy.py), its findings one per line: path:line: what
check=test_repo_privacy.Privacy.test_no_file_holds_personal_data
if [ ! -f "$DOT/tests/test_repo_privacy.py" ]; then
  warn "$(t sync.private_unchecked)"
elif out=$(cd "$DOT/tests" && python3 -B -m unittest "$check" 2>&1); then
  ok "$(t sync.private_clean)"
else
  warn "$(t sync.private_found)"
  printf '%s\n' "$out" | grep -E '^[A-Za-z0-9._/-]+:[0-9]+: ' | awk '!seen[$0]++' \
    | while IFS= read -r found; do note "$found"; done
fi
