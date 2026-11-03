# The real Python on a Windows machine, as its path (nothing, exit 1, without one): Python on the PATH, but not the
# Store's alias in WindowsApps (it only offers the Store), else a python.org install for the user or for all. The
# sidebar's launcher, prepare-windows.ps1 and the Herdr app mod ask it.
$python = (Get-Command python -All -CommandType Application -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1).Source
if (-not $python) {
    $python = (
        Get-ChildItem -ErrorAction SilentlyContinue -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe" | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not $python) { exit 1 }
$python
