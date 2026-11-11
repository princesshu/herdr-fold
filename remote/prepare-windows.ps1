# Prepares a remote Windows machine (x86_64, PowerShell 5.1 too) for herdr: machines.sh unpacks it into
# %USERPROFILE%\.herdr-fold and runs it over SSH before connecting. Adds git, Python (winget, which often fails over
# SSH, else python.org), herdr-fold's settings and, with the TUI (-Parts), starship; -Remove takes them off. Rerunnable.
param([string]$Lang = $(if ($env:HERDR_FOLD_LANG) { $env:HERDR_FOLD_LANG } else { 'en' }), [string]$Parts = 'tui',
      [switch]$Remove)
$Tui = ($Parts -split ',') -contains 'tui'           # the parts herdr-fold has on the Mac: the prompt, the TUI's
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$F = Join-Path $Here 'files'
$env:HERDR_FOLD_LANG = $Lang     # statusline_setup.py prints in the same language

# The texts, from the Mac: lang\<language>.txt (en.txt if there is no file for the language), one `key = text` per line
# (a line ending in \ goes on in the next, indented one). T 'key' [args…] returns the text: %s takes the next argument,
# %% is a percent sign, \n a new line.
$Texts = @{}
$LangFile = Join-Path $Here "lang\$Lang.txt"
if (-not (Test-Path $LangFile)) { $LangFile = Join-Path $Here 'lang\en.txt' }
$key = $null
foreach ($line in Get-Content -Encoding UTF8 $LangFile) {
    if ($key) {
        $Texts[$key] += $line.TrimStart()                    # the text goes on: without its indentation
    } else {
        $at = $line.IndexOf(' = ')
        if ($at -le 0 -or $line.StartsWith('#')) { continue }
        $key = $line.Substring(0, $at)
        $Texts[$key] = $line.Substring($at + 3)
    }
    if ($Texts[$key].EndsWith('\')) { $Texts[$key] = $Texts[$key].Substring(0, $Texts[$key].Length - 1) }
    else { $key = $null }
}
function T($key) {
    $text = [string]$Texts[$key]; $out = New-Object Text.StringBuilder; $n = 0
    for ($i = 0; $i -lt $text.Length; $i++) {
        $pair = if ($i + 1 -lt $text.Length) { $text.Substring($i, 2) } else { '' }
        if ($pair -ceq '%s') { [void]$out.Append([string]$args[$n]); $n++; $i++ }
        elseif ($pair -ceq '%%') { [void]$out.Append('%'); $i++ }
        elseif ($pair -ceq '\n') { [void]$out.Append("`n"); $i++ }
        else { [void]$out.Append($text[$i]) }
    }
    $out.ToString()
}
# Status lines, as on the Mac (lib/output.sh): "  [✓] text", "  [!] text", … — the Mac's summarize reads them
function Line($kind, $text) {
    $mark = @{
        ok = '[✓]'; have = '[✓]'; warn = '[!]'; fail = '[✗]'; skip = '[-]'; saved = '[+]'; section = '--'
    }[$kind]
    Write-Output "  $mark $text"
}

# This machine's record of what it got (prepared.txt), and the backups of what it replaced
$State = Join-Path $env:USERPROFILE '.local\state\herdr-fold'
$Record = Join-Path $State 'prepared.txt'
$Backup = Join-Path $State ('prepared-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$Original = Join-Path $State 'prepared-original'   # the machine's own files, as they were before the first prepare
function Get-Local($rel) {  # a listed path, as this system writes it
    $rel.Replace('/', [IO.Path]::DirectorySeparatorChar)
}
# Keep REL (relative to the profile) in the folder INTO, the backup unless said; a link is moved there as it is (MOVE),
# never followed. An error when it cannot be kept: the caller then leaves the file as it is.
function Keep($rel, $into = $Backup, [switch]$Move) {
    $keep = Join-Path $into (Get-Local $rel)
    New-Item -ItemType Directory -Force -ErrorAction Stop -Path (Split-Path $keep) | Out-Null
    $path = Join-Path $env:USERPROFILE (Get-Local $rel)
    if ($Move) { Move-Item -Force -ErrorAction Stop $path $keep }
    else { Copy-Item -Force -ErrorAction Stop $path $keep }
}
# After REL is taken off: the machine's own one (prepared-original) back in its place; without one, the folders left
# empty go
function Restore-Own($rel) {
    $path = Join-Path $env:USERPROFILE (Get-Local $rel)
    $own = Join-Path $Original (Get-Local $rel)
    if (Get-Item -Force -ErrorAction SilentlyContinue $own) {
        New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
        Move-Item -Force $own $path
        Line ok (T 'prepare.win.restored' $path)
    } else { Remove-EmptyDirs (Split-Path $path) }
}
# Claude's, Codex's and herdr's own data is never removed, whatever the record says (lib/files.sh ai_session_file)
function Test-AiSession($rel) {
    $rel -match '^(\.claude|\.codex|\.local/state/herdr)/'
}
# The empty folders herdr keeps of plugins IDS after `plugin unlink` (a config folder, a state folder once nothing of
# the plugin's is left in it); nothing of a plugin herdr still lists, nothing at all when herdr cannot say what it has
function Remove-PluginFolders([string[]]$ids) {
    $h = (Get-Command herdr -ErrorAction SilentlyContinue).Source
    if (-not $h) { $h = "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" }
    if (-not (Test-Path $h)) { return }
    try { $answer = (& $h plugin list --json 2>$null | Out-String) | ConvertFrom-Json } catch { return }
    if (-not ($answer.result.PSObject.Properties.Name -contains 'plugins')) { return }
    $herdrHas = @($answer.result.plugins | ForEach-Object { $_.plugin_id })
    foreach ($id in $ids) {
        if ($herdrHas -contains $id) { continue }
        $pluginState = Join-Path $env:USERPROFILE ".local\state\herdr\plugins\$id"
        if ($id -eq 'herdr-fold.sessions-view' -and (Test-Path $pluginState)) {   # its waits and locks; names stay
            Get-ChildItem -Force $pluginState | Where-Object {
                $_.Name -in 'waits.json', 'clock.lock', 'names.json.lock', 'waits.json.lock' -or
                $_.Name -like '.names.json.*.tmp' -or $_.Name -like '.waits.json.*.tmp'
            } | Remove-Item -Force -ErrorAction SilentlyContinue
        }
        foreach ($folder in (Join-Path $env:USERPROFILE ".config\herdr\plugins\config\$id"), $pluginState) {
            if ((Test-Path $folder) -and -not (Get-ChildItem -Force $folder)) { Remove-Item -Force $folder }
        }
    }
}
# A folder left empty goes, and so do its parents — up to the profile's own folders
function Remove-EmptyDirs($dir) {
    while ($dir.Length -gt $env:USERPROFILE.Length -and (Split-Path -Leaf $dir) -notin '.config', '.local', 'state' -and
           (Test-Path $dir) -and -not (Get-ChildItem -Force $dir)) {
        Remove-Item -Force $dir
        $dir = Split-Path $dir
    }
}
# The prompt goes into the PowerShell profiles (the Documents folder) as one marked block — not where the execution
# policy blocks profiles: there it never was
$Blocked = (Get-ExecutionPolicy) -in 'Restricted', 'AllSigned'
$Docs = [Environment]::GetFolderPath('MyDocuments')
$Profiles = "$Docs\WindowsPowerShell\Microsoft.PowerShell_profile.ps1",
    "$Docs\PowerShell\Microsoft.PowerShell_profile.ps1"
# A status line this package wrote: PowerShell running statusline.py with the machine's Python (anything else is the
# machine's own)
function Test-HerdrFoldStatusLine($line) {
    "$($line.command)" -match ('^powershell -NoProfile -Command "& ''[^"]*'' ''[^"]*[/\\]\.config' +
        '[/\\]herdr-fold[/\\]statusline\.py''"$')
}
# The marked BLOCK at the end of the file PATH, in place of an earlier one ('': none). Every other byte stays as it was:
# a UTF-16 file is read and written as UTF-16 (by its byte order mark), any other byte for byte (Latin-1 gives each
# byte a character of its own), so an ANSI or a UTF-8 profile keeps its encoding.
function Set-Block($path, $block) {
    $encoding, $text = [Text.Encoding]::GetEncoding(28591), ''
    if (Test-Path $path) {
        $bytes = [IO.File]::ReadAllBytes($path)
        $mark = if ($bytes.Length -ge 2) { '{0:X2}{1:X2}' -f $bytes[0], $bytes[1] } else { '' }
        if ($mark -eq 'FFFE') { $encoding = [Text.Encoding]::Unicode }
        elseif ($mark -eq 'FEFF') { $encoding = [Text.Encoding]::BigEndianUnicode }
        $text = $encoding.GetString($bytes)
    }
    $new = [regex]::Replace($text, '(\r?\n)?# >>> herdr-fold >>>[\s\S]*?# <<< herdr-fold <<<\r?\n?', '')
    if ($block) { $new += $block + [Environment]::NewLine }
    if ($new -cne $text) {
        New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
        [IO.File]::WriteAllBytes($path, $encoding.GetBytes($new))
    }
}

if ($Remove) {
    Line section (T 'prepare.win.removing')
    # Claude's status line first (its script is about to go): the one the machine had — the first one saved — comes
    # back, or herdr-fold's just goes
    $settings = [IO.Path]::Combine($env:USERPROFILE, '.claude', 'settings.json')
    if (Test-Path $settings) {
        $data = $null
        try { $data = Get-Content -Raw -Encoding UTF8 $settings | ConvertFrom-Json -ErrorAction Stop } catch { }
        if (-not ($data -is [System.Management.Automation.PSCustomObject])) {
            Line warn (T 'prepare.win.settings_unreadable' $settings)
        } elseif (Test-HerdrFoldStatusLine $data.statusLine) {
            $saved = Get-ChildItem -Path (Join-Path $State 'prepared-*') -Filter claude-statusLine.json -Recurse `
                -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -First 1
            if ($saved) {
                $data.statusLine = Get-Content -Raw -Encoding UTF8 $saved.FullName | ConvertFrom-Json
                Remove-Item -Force $saved.FullName
            } else { $data.PSObject.Properties.Remove('statusLine') }
            [IO.File]::WriteAllText($settings, ($data | ConvertTo-Json -Depth 20),
                (New-Object Text.UTF8Encoding $false))
            Line ok (T 'prepare.win.status_line_back')
        }
    }
    # the recorded files off: one that is still the package's own version just goes; one changed here is kept first
    # (a plugin manifest carries this machine's Python path: compared without it)
    if (Test-Path $Record) {
        foreach ($rel in Get-Content -Encoding UTF8 $Record) {
            $path = Join-Path $env:USERPROFILE (Get-Local $rel)
            if (-not $rel -or (Test-AiSession $rel)) { continue }
            if (Test-Path -PathType Leaf $path) {
                $packaged = Join-Path $F (Get-Local $rel)
                # (PowerShell variable names ignore case: a name differing from $Here only in case would overwrite it)
                $installed = [IO.File]::ReadAllText($path) -replace "command = \['[^']*', ", 'command = ["python", '
                if (-not ((Test-Path $packaged) -and [IO.File]::ReadAllText($packaged) -ceq $installed)) {
                    try { Keep $rel } catch { Line warn (T 'prepare.win.not_kept' $path); continue }
                }
                Remove-Item -Force $path
                Line ok (T 'prepare.win.removed' $path)
            }
            Restore-Own $rel
        }
        Remove-Item -Force $Record
    }
    if (-not $Blocked) { foreach ($p in $Profiles) { Set-Block $p '' } }
    # herdr-fold's plugins (an earlier prepare's Tab Layout too), and the empty folders herdr keeps of them (the
    # conversation names stay)
    $h = (Get-Command herdr -ErrorAction SilentlyContinue).Source
    if (-not $h) { $h = "$env:LOCALAPPDATA\Programs\Herdr\bin\herdr.exe" }
    $plugins = 'herdr-fold.sidebar', 'herdr-fold.sessions-view', 'herdr-fold.workspaces', 'herdr-fold.tab-layout'
    if (Test-Path $h) {
        foreach ($id in $plugins) { & $h plugin unlink $id *> $null }
    }
    Remove-PluginFolders $plugins
    # what Python and the status line setup made next to the package's files
    $fold = Join-Path $env:USERPROFILE '.config\herdr-fold'
    Remove-Item -Recurse -Force (Join-Path $fold '__pycache__'),
        (Join-Path $fold 'statusline.json') -ErrorAction SilentlyContinue
    Remove-EmptyDirs $fold
    # the sidebar's own settings, its folder only when nothing else is in it (the rest of herdr's state is herdr's)
    $sidebarState = Join-Path $env:USERPROFILE '.local\state\herdr\plugins\herdr-fold.sidebar'
    Remove-Item -Force -ErrorAction SilentlyContinue -Path (Join-Path $sidebarState 'settings.json'),
        (Join-Path $sidebarState 'colors.json'), (Join-Path $sidebarState 'column.json'),
        (Join-Path $sidebarState 'conversations.json'), (Join-Path $sidebarState 'conversation-index.json'),
        (Join-Path $sidebarState 'panels.json'), (Join-Path $sidebarState 'dock.json'),
        (Join-Path $sidebarState 'resume-*.json'), (Join-Path $sidebarState 'seed-*.json'),
        (Join-Path $sidebarState 'preview-*.json'), (Join-Path $sidebarState 'issues-*.json'),
        (Join-Path $sidebarState '*.json.lock'),
        (Join-Path $sidebarState '.*.tmp')                                         # a write cut short
    if ((Test-Path $sidebarState) -and -not (Get-ChildItem -Force $sidebarState)) {
        Remove-Item -Force $sidebarState
    }
    if (Test-Path $Backup) { Line saved (T 'prepare.win.backup' $Backup) }
    if (Test-Path $State) {
        Get-ChildItem -Recurse -Directory -Force $State | Sort-Object { $_.FullName.Length } -Descending |
            Where-Object { -not (Get-ChildItem -Force $_.FullName) } | Remove-Item -Force
        Remove-EmptyDirs $State
    }
    if (Test-Path $State) { Line saved (T 'prepare.win.kept' $State) }
    # AI Sessions' conversation names stay, as the conversations themselves, and are named
    $names = Join-Path $env:USERPROFILE '.local\state\herdr\plugins\herdr-fold.sessions-view\names.json'
    if (Test-Path $names) { Line saved (T 'prepare.win.kept_names' $names) }
    if ((Split-Path -Leaf $Here) -eq '.herdr-fold') { Remove-Item -Recurse -Force $Here -ErrorAction SilentlyContinue }
    exit 0
}

if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    Line fail (T 'prepare.win.unsupported' $env:PROCESSOR_ARCHITECTURE)
    exit 1
}

$Bin = Join-Path $env:USERPROFILE '.local\bin'
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ('herdr-fold-' + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $Bin, $Tmp | Out-Null
$env:Path = "$Bin;$env:Path"

function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Get-Url($url, $out) { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out }
# A pinned release, kept only if its SHA-256 matches the release's own published checksum
function Get-Verified($url, $out, $sha256) {
    Get-Url $url $out
    if ((Get-FileHash -Algorithm SHA256 $out).Hash -ne $sha256) {
        Remove-Item -Force $out -ErrorAction SilentlyContinue
        throw "checksum mismatch: $url"
    }
}
function Expand-Exe($zip, $exe) {
    Expand-Archive -Force -Path $zip -DestinationPath $Tmp
    Move-Item -Force (Join-Path $Tmp $exe) (Join-Path $Bin $exe)
}

# The real Python (not the Microsoft Store "python" shortcut), by the payload's python.ps1: the sidebar's own rule
function Find-Python { & (Join-Path $F '.config\herdr-fold\python.ps1') }

Line section (T 'prepare.win.apps')
# User PATH: herdr's panes start from this environment
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not (($userPath -split ';') -contains $Bin)) {
    [Environment]::SetEnvironmentVariable('Path',
        (@($Bin) + ($userPath -split ';' | Where-Object { $_ })) -join ';', 'User')
    Line ok (T 'prepare.win.on_path' $Bin)
}

# the prompt, the TUI's: a pinned release, checksum-verified
if (-not $Tui) { }
elseif (Test-Command starship) { Line have starship }
else {
    try {
        Get-Verified `
            'https://github.com/starship/starship/releases/download/v1.27.0/starship-x86_64-pc-windows-msvc.zip' `
            (Join-Path $Tmp 'ss.zip') '7764F861805376AF2812DD78C84FADC16B714CF3F346BAED9B597BFDA8484403'
        Expand-Exe (Join-Path $Tmp 'ss.zip') 'starship.exe'
        Line ok starship
    }
    catch { Line warn (T 'prepare.win.tool_failed' 'starship' $_.Exception.Message) }
}

$winget = Test-Command winget
if (-not (Test-Command git)) {
    if ($winget) {
        winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
    }
    if (Test-Command git) { Line ok 'git' } else { Line warn (T 'prepare.win.git_missing') }
}
# Whether SIGNATURE (Get-AuthenticodeSignature's) is valid and the Python Software Foundation's own: the certificate's
# whole name, as another name containing it is someone else's
function Test-PythonSigner($signature) {
    $signature.Status -eq 'Valid' -and
        $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,
                                                 $false) -ceq 'Python Software Foundation'
}
# python.org's newest Python 3 that has a Windows installer (security-fix releases ship without one), silently, for
# this user only (no admin rights)
function Install-PythonOrg {
    $listing = (Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/').Content
    $versions = [regex]::Matches($listing, 'href="(3\.\d+\.\d+)/"') | ForEach-Object { [version]$_.Groups[1].Value } |
        Sort-Object -Descending | Select-Object -First 15
    foreach ($v in $versions) {
        $url = "https://www.python.org/ftp/python/$v/python-$v-amd64.exe"
        try { Invoke-WebRequest -UseBasicParsing -Method Head -Uri $url | Out-Null } catch { continue }
        $setup = Join-Path $Tmp 'python-setup.exe'
        Get-Url $url $setup
        # run only the Python Software Foundation's own, validly signed installer
        if (-not (Test-PythonSigner (Get-AuthenticodeSignature $setup))) {
            Remove-Item -Force $setup -ErrorAction SilentlyContinue
            throw (T 'prepare.win.python_unsigned')
        }
        Start-Process -Wait -FilePath $setup -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1',
            'Include_test=0'
        return
    }
}
$python = Find-Python
if (-not $python -and $winget) {
    winget install --id Python.Python.3.13 -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
    $python = Find-Python
}
if (-not $python) {
    try { Install-PythonOrg } catch { Line warn (T 'prepare.win.python_installer_failed' $_.Exception.Message) }
    $python = Find-Python
}
if ($python) { Line ok (T 'prepare.win.python_present' $python) }
else { Line warn (T 'prepare.win.python_missing') }

Line section (T 'prepare.win.settings')
# The files of files.list (the Mac's remote/files.txt) into place: a changed earlier version is backed up first, the
# machine's own to prepared-original, and a link is set aside, never written through. What the last list (prepared.txt)
# had and this one drops is backed up and removed, and the machine's own comes back.
$Listed = @(Get-Content -Encoding UTF8 (Join-Path $Here 'files.list') | Where-Object { $_ })
$Recorded = @(if (Test-Path $Record) { Get-Content -Encoding UTF8 $Record })
foreach ($rel in $Listed) {
    $from = Join-Path $F (Get-Local $rel)
    $dst = Join-Path $env:USERPROFILE (Get-Local $rel)
    # a plugin's command uses Python's full path (independent of the herdr server's PATH)
    if ($python -and $rel -like '*/herdr-plugin.toml') {
        $manifest = (Get-Content -Raw -Encoding UTF8 $from).Replace('command = ["python", ', "command = ['$python', ")
        [IO.File]::WriteAllText($from, $manifest, (New-Object Text.UTF8Encoding $false))
    }
    $into = if ($Recorded -contains $rel) { $Backup } else { $Original }
    $item = Get-Item -Force -ErrorAction SilentlyContinue $dst
    try {
        if ($item -and $item.LinkType) { Keep $rel $into -Move }
        elseif ($item -and ((Get-FileHash $dst).Hash -ne (Get-FileHash $from).Hash)) { Keep $rel $into }
    } catch { Line warn (T 'prepare.win.not_kept' $dst); continue }
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    Copy-Item -Force $from $dst
    Line ok $dst
}
if (Test-Path $Record) {
    foreach ($rel in Get-Content -Encoding UTF8 $Record) {
        $path = Join-Path $env:USERPROFILE (Get-Local $rel)
        if (-not $rel -or $Listed -contains $rel -or (Test-AiSession $rel)) { continue }
        if (Test-Path -PathType Leaf $path) {
            try { Keep $rel } catch { Line warn (T 'prepare.win.not_kept' $path); continue }
            Remove-Item -Force $path
            Line ok (T 'prepare.win.removed' $path)
        }
        Restore-Own $rel
    }
}
New-Item -ItemType Directory -Force -Path $State | Out-Null
Copy-Item -Force (Join-Path $Here 'files.list') $Record
if (Test-Path $Backup) { Line saved (T 'prepare.win.backup' $Backup) }

# Starship prompt inside herdr panes (PowerShell profile; other logins on the machine are unaffected): one marked block,
# replaced on every run
if (-not $Tui) { }
elseif ($Blocked) {
    Line skip (T 'prepare.win.profiles_blocked' (Get-ExecutionPolicy))
} else {
    $block = @'

# >>> herdr-fold >>>
# starship prompt, only inside herdr panes
if ($env:HERDR_ENV -eq '1' -and (Get-Command starship -ErrorAction SilentlyContinue)) {
    Invoke-Expression (& starship init powershell)
}
# <<< herdr-fold <<<
'@
    foreach ($p in $Profiles) { Set-Block $p $block }
    Line ok (T 'prepare.win.prompt_added')
}
# The Claude Code status line (statusline.py, with the machine's Python): the machine's earlier one is backed up; an
# unreadable settings file, or a status line chosen on the Mac to be your own, is left as it is (statusline_setup.py
# --apply below brings the machine's own back)
$settings = [IO.Path]::Combine($env:USERPROFILE, '.claude', 'settings.json')
$data = New-Object PSObject
if (Test-Path $settings) {
    try { $data = Get-Content -Raw -Encoding UTF8 $settings | ConvertFrom-Json -ErrorAction Stop }
    catch { $data = $null }
}
$choice = $null
try {
    $choice = Get-Content -Raw -Encoding UTF8 ([IO.Path]::Combine($env:USERPROFILE, '.config', 'herdr-fold',
        'statusline.json')) -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
} catch { }
$mine = $choice -and $choice.claude -and $choice.claude.on -eq $false       # the machine's own status line chosen
if (-not $mine -and $python -and $data -is [System.Management.Automation.PSCustomObject]) {   # an object, not a list
    # Claude Code runs it in Git Bash or, without that, in PowerShell: powershell starts it in either. The paths with
    # forward slashes (Git Bash takes a backslash for an escape), in single quotes with a ' doubled (a user folder like
    # C:\Users\Test User has a space in it)
    $quoted = foreach ($path in $python, "$env:USERPROFILE\.config\herdr-fold\statusline.py") {
        "'" + $path.Replace('\', '/').Replace("'", "''") + "'"
    }
    # drawn again every 10 seconds, as statusline_setup.py's REFRESH: for a pane made narrower, and the reset times
    $wanted = [ordered]@{ type = 'command'; command = "powershell -NoProfile -Command `"& $($quoted -join ' ')`"";
                          refreshInterval = 10 }
    $old = $data.statusLine
    if (Test-HerdrFoldStatusLine $old) { $old = $null }    # an earlier form of herdr-fold's: nothing of yours to keep
    if ($old -and $old.command -ne $wanted.command) {
        New-Item -ItemType Directory -Force -Path $Backup | Out-Null
        [IO.File]::WriteAllText([IO.Path]::Combine($Backup, 'claude-statusLine.json'),
            ($old | ConvertTo-Json -Depth 20),
            (New-Object Text.UTF8Encoding $false))
    }
    $data | Add-Member -Force -NotePropertyName statusLine -NotePropertyValue $wanted
    New-Item -ItemType Directory -Force -Path (Split-Path $settings) | Out-Null
    [IO.File]::WriteAllText($settings, ($data | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding $false))
    if ($old -and $old.command -ne $wanted.command) { Line ok (T 'prepare.win.statusline_replaced' $Backup) }
    else { Line ok (T 'prepare.win.statusline_set') }
} elseif (-not $mine -and $python) {
    Line warn (T 'prepare.win.settings_unreadable' $settings)
}
# The status line items as chosen on the Mac (Claude: statusline.py reads them from here; Codex: its own settings)
if ($python) { & $python "$env:USERPROFILE\.config\herdr-fold\statusline_setup.py" --apply }

Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
# the payload this ran from goes (machines.sh sends a fresh one each time)
if ((Split-Path -Leaf $Here) -eq '.herdr-fold') { Remove-Item -Recurse -Force $Here -ErrorAction SilentlyContinue }
