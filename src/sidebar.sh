#!/bin/bash
# Starts the sidebar (the herdr-fold.sidebar plugin) in a plain herdr pane at the top of the right column; argument: the
# folder (default: the pane's). Not a plugin pane: herdr brings one back as an empty shell after a restart, while
# restore_panes.py restarts a plain one. Quitting it (q) leaves the shell.

# The Python the plugin's actions use; -B: no caches next to the plugin
py=/usr/bin/python3
[ -x "$py" ] || py=$(command -v python3) || { echo "The sidebar needs Python 3.9 or newer (python3)." >&2; exit 1; }
exec "$py" -B "$HOME/.config/herdr-fold/plugins/sidebar/sidebar.py" "${1:-$PWD}"
