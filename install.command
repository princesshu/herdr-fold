#!/bin/bash
# Double-click to start the installer in the macOS Terminal app. macOS always opens a .command file with Terminal;
# once Ghostty is installed, a .sh file would open in Ghostty, which would also start the old herdr mid-install.
cd "$(dirname "$0")" && exec ./install.sh
