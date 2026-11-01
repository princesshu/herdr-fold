# Starts the sidebar on Windows in a plain herdr pane, at the top of the right column (the counterpart of sidebar.sh).
# herdrlib.sidebar_command() runs it in the pane's PowerShell; argument: the folder (defaults to the pane's).
# Quitting it (q) → back to the shell.
param([string]$Dir = (Get-Location).Path, [switch]$Conversations)

# Python as prepare-windows.ps1 finds it: not the Store's "python" in WindowsApps, else a python.org install
$python = (Get-Command python -All -CommandType Application -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1).Source
if (-not $python) {
    $python = (
        Get-ChildItem -ErrorAction SilentlyContinue -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe" | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not $python) {
    Write-Output 'The sidebar needs Python 3.9 or newer: https://www.python.org/downloads/'
    exit 1
}
if ($Conversations) { & $python -B (Join-Path $PSScriptRoot 'plugins\sidebar\sidebar.py') --conversations }
else { & $python -B (Join-Path $PSScriptRoot 'plugins\sidebar\sidebar.py') $Dir }
exit $LASTEXITCODE
