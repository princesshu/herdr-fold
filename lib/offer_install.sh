#!/bin/sh
# herdr-fold's whole-environment plugin, run on herdr's start and a pane's focus: the installer in an unfocused tab,
# once per package copy (a folder per version). The mark comes first (set -C): many focus events open one tab, and a
# tab herdr could not open drops it. Again: herdr plugin pane open --plugin herdr-fold --entrypoint install
[ -n "${HERDR_PLUGIN_ROOT:-}" ] && [ -n "${HERDR_PLUGIN_STATE_DIR:-}" ] || exit 0
mkdir -p "$HERDR_PLUGIN_STATE_DIR" 2>/dev/null || exit 0
mark="$HERDR_PLUGIN_STATE_DIR/offered-$(printf '%s' "$HERDR_PLUGIN_ROOT" | cksum | cut -d' ' -f1)"
[ -e "$mark" ] && exit 0
(set -C; : > "$mark") 2>/dev/null || exit 0
for other in "$HERDR_PLUGIN_STATE_DIR"/offered-*; do
  [ "$other" = "$mark" ] || rm -f "$other"
done
herdr=${HERDR_BIN_PATH:-herdr}
if "$herdr" plugin pane open --plugin herdr-fold --entrypoint install --no-focus >/dev/null 2>&1; then
  CATALOG_DIR="$HERDR_PLUGIN_ROOT/src/lang"
  [ -f "$HERDR_PLUGIN_ROOT/lib/i18n.sh" ] && . "$HERDR_PLUGIN_ROOT/lib/i18n.sh" \
    && "$herdr" notification show "$(t offer.ready)" --body "$(t offer.ready_body)" >/dev/null 2>&1
else
  rm -f "$mark"
fi
exit 0
