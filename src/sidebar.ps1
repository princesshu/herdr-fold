# Starts the sidebar on Windows in a plain herdr pane, at the top of the right column (the counterpart of sidebar.sh).
# herdrlib.sidebar_command() runs it in the pane's PowerShell; argument: the folder (defaults to the pane's).
# Quitting it (q) → back to the shell.
param([string]$Dir = (Get-Location).Path)

$python = & (Join-Path $PSScriptRoot 'python.ps1')       # the real Python, not the Store's alias
if (-not $python) {
    Write-Output 'The sidebar needs Python 3.9 or newer: https://www.python.org/downloads/'
    exit 1
}
& $python -B (Join-Path $PSScriptRoot 'plugins\sidebar\sidebar.py') $Dir
exit $LASTEXITCODE
