#requires -Version 5.1
# Windows PowerShell 5.1+. Uses only Windows built-in facilities; no Python.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$script:VtdRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script:VtdName = 'territorial_doctrine'
$script:VtdUtf8 = New-Object System.Text.UTF8Encoding($false)

function Write-VtdFile([string] $Path, [string] $Text) {
    [IO.File]::WriteAllText($Path, $Text, $script:VtdUtf8)
}

function Test-VtdWithin([string] $Path, [string] $Parent) {
    $base = $Parent.TrimEnd([char[]]"/\")
    return $Path.Equals($base, [StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-VtdRegular([string] $Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -ne $item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing a symbolic link, junction or reparse point: $Path"
        }
    }
}

function Assert-VtdTree([string] $Path) {
    Assert-VtdRegular $Path
    $pending = New-Object 'Collections.Generic.Stack[string]'
    $pending.Push($Path)
    while ($pending.Count -gt 0) {
        foreach ($item in (Get-ChildItem -LiteralPath ($pending.Pop()) -Force)) {
            Assert-VtdRegular $item.FullName
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

function Get-VtdInstallation([string] $Destination) {
    $folder = Join-Path $Destination $script:VtdName
    $launcher = Join-Path $Destination ($script:VtdName + '.mod')
    Assert-VtdRegular $folder
    Assert-VtdRegular $launcher
    $hasFolder = Test-Path -LiteralPath $folder
    $hasLauncher = Test-Path -LiteralPath $launcher
    $version = 'unknown'
    if ($hasFolder) {
        if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw "Not a mod directory: $folder" }
        $metadata = Join-Path $folder '.metadata/metadata.json'
        Assert-VtdRegular (Join-Path $folder '.metadata')
        Assert-VtdRegular $metadata
        try { $data = Get-Content -LiteralPath $metadata -Raw -Encoding UTF8 | ConvertFrom-Json }
        catch { throw "Cannot identify existing folder as VTD; left untouched: $folder" }
        if ($data.id -ne $script:VtdName -or $data.game_id -ne 'victoria3') {
            throw "Existing folder belongs to another mod; left untouched: $folder"
        }
        $version = $data.version
    }
    if ($hasLauncher) {
        $text = [IO.File]::ReadAllText($launcher)
        $paths = [regex]::Matches($text, '(?m)^\s*path\s*=\s*"([^"\r\n]+)"\s*$')
        $names = [regex]::Matches($text, '(?m)^\s*name\s*=\s*"([^"\r\n]+)"\s*$')
        if ($paths.Count -ne 1 -or $names.Count -ne 1) { throw "Unrecognized VTD descriptor: $launcher" }
        if (-not $hasFolder -and $names[0].Groups[1].Value -ne 'Territorial Doctrine') {
            throw "Descriptor belongs to another mod; left untouched: $launcher"
        }
        $target = $paths[0].Groups[1].Value
        if (-not [IO.Path]::IsPathRooted($target)) {
            $target = Join-Path (Split-Path -Parent $Destination) $target
        }
        if (-not [IO.Path]::GetFullPath($target).Equals($folder, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Descriptor points to another folder; left untouched: $launcher"
        }
    }
    return @{ Present = ($hasFolder -or $hasLauncher); Partial = ($hasFolder -ne $hasLauncher); Version = $version }
}

function New-VtdBackup([string] $Destination, [string] $Action) {
    $base = Join-Path (Split-Path -Parent $Destination) 'vtd-backups'
    Assert-VtdRegular $base
    [void][IO.Directory]::CreateDirectory($base)
    $label = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + $Action + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $temporary = Join-Path $base ('.incomplete-' + $label)
    [void][IO.Directory]::CreateDirectory($temporary)
    try {
        $folder = Join-Path $Destination $script:VtdName
        $launcher = Join-Path $Destination ($script:VtdName + '.mod')
        if (Test-Path -LiteralPath $folder) {
            Assert-VtdTree $folder
            Copy-Item -LiteralPath $folder -Destination (Join-Path $temporary $script:VtdName) -Recurse -Force
        }
        if (Test-Path -LiteralPath $launcher) { Copy-Item -LiteralPath $launcher -Destination $temporary -Force }
        Write-VtdFile (Join-Path $temporary 'backup.json') (@{ operation = $Action; mod_dir = $Destination } | ConvertTo-Json)
        $backup = Join-Path $base $label
        Move-Item -LiteralPath $temporary -Destination $backup
        return $backup
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
}

function Invoke-VtdManage([string] $Action, [string] $Destination, [bool] $DryRun) {
    $Destination = [IO.Path]::GetFullPath($Destination)
    if ($Destination.Length -gt [IO.Path]::GetPathRoot($Destination).Length) {
        $Destination = $Destination.TrimEnd([char[]]"/\")
    }
    $folder = Join-Path $Destination $script:VtdName
    $launcher = Join-Path $Destination ($script:VtdName + '.mod')
    if ((Test-VtdWithin $Destination $script:VtdRoot) -or (Test-VtdWithin $script:VtdRoot $folder)) {
        throw 'The installation must be outside the source checkout.'
    }
    if ($Destination -match '["\r\n]') { throw 'The mod directory cannot contain quotes or line breaks.' }
    if ((Test-Path -LiteralPath $Destination) -and -not (Test-Path -LiteralPath $Destination -PathType Container)) {
        throw "Not a directory: $Destination"
    }
    Assert-VtdRegular $Destination
    $existing = Get-VtdInstallation $Destination
    Write-Host "Mod directory: $Destination"
    if ($Action -eq 'status') {
        if ($existing.Present) {
            $state = 'installed'
            if ($existing.Partial) { $state = 'partial (update repairs it)' }
            Write-Host "VTD: $state; version $($existing.Version)"
        } else { Write-Host 'VTD: not installed' }
        return
    }
    if ($Action -eq 'install' -and $existing.Present) { throw 'VTD already exists. Use update for an automatic backup.' }
    if ($Action -ne 'install' -and -not $existing.Present) {
        if ($Action -eq 'remove') { Write-Host 'VTD is already absent.'; return }
        throw 'VTD is not installed here. Run install first.'
    }
    Write-Host "$Action VTD"
    if ($DryRun) { Write-Host 'Preview only; no source or game files changed. Updates/removals keep a backup.'; return }
    $data = $null
    if ($Action -ne 'remove') {
        Write-Host 'Checking source metadata and required files (no Python required)...'
        Assert-VtdTree (Join-Path $script:VtdRoot 'mod')
        Assert-VtdRegular (Join-Path $script:VtdRoot 'LICENSE')
        foreach ($required in @('LICENSE', 'mod/.metadata/metadata.json', 'mod/common/law_groups/td_law_group.txt', 'mod/localization/english/td_laws_l_english.yml')) {
            if (-not (Test-Path -LiteralPath (Join-Path $script:VtdRoot $required) -PathType Leaf)) {
                throw "Missing source file: $required. Use a complete repository checkout."
            }
        }
        $data = Get-Content -LiteralPath (Join-Path $script:VtdRoot 'mod/.metadata/metadata.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($data.id -ne $script:VtdName -or $data.game_id -ne 'victoria3' -or $data.version -notmatch '^[\w.\-]+$') {
            throw 'Source metadata does not identify the VTD mod.'
        }
    }
    [void][IO.Directory]::CreateDirectory($Destination)
    $lockPath = Join-Path $Destination '.vtd-install.lock'
    try { $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None) }
    catch { throw "Cannot acquire install lock: $lockPath. Check for another running installer or a stale lock before retrying. $($_.Exception.Message)" }
    $staging = Join-Path $Destination ('.vtd-stage-' + [guid]::NewGuid().ToString('N'))
    try {
        $existing = Get-VtdInstallation $Destination
        if (($Action -eq 'install') -eq [bool]$existing.Present) { throw 'The installation changed; run status and retry.' }
        [void][IO.Directory]::CreateDirectory($staging)
        $nextFolder = Join-Path $staging 'next_payload'
        $nextLauncher = Join-Path $staging 'next.mod'
        if ($Action -ne 'remove') {
            Write-Host 'Staging mod files...'
            Copy-Item -LiteralPath (Join-Path $script:VtdRoot 'mod') -Destination $nextFolder -Recurse -Force
            Copy-Item -LiteralPath (Join-Path $script:VtdRoot 'LICENSE') -Destination $nextFolder -Force
            Write-VtdFile (Join-Path $nextFolder '.vtd-install.json') (@{ tool = 'vtd-installer'; schema = 1; version = $data.version } | ConvertTo-Json)
            $modPath = $folder.Replace('\', '/')
            $descriptor = "name=`"Territorial Doctrine`"`nversion=`"$($data.version)`"`nsupported_version=`"1.13.*`"`ntags={ `"Gameplay`" `"Politics`" }`npath=`"$modPath`"`n"
            Write-VtdFile $nextLauncher $descriptor
        }
        $backup = $null
        if ($existing.Present) {
            Write-Host 'Backing up the previous installation...'
            $backup = New-VtdBackup $Destination $Action
            Write-Host "Previous installation backed up: $backup"
        }
        $oldFolder = Join-Path $staging 'previous_payload'
        $oldLauncher = Join-Path $staging 'previous.mod'
        $committed = $false
        Write-Host 'Applying installation changes...'
        try {
            if (Test-Path -LiteralPath $folder) { Move-Item -LiteralPath $folder -Destination $oldFolder }
            if (Test-Path -LiteralPath $launcher) { Move-Item -LiteralPath $launcher -Destination $oldLauncher }
            if ($Action -ne 'remove') {
                Move-Item -LiteralPath $nextFolder -Destination $folder
                Move-Item -LiteralPath $nextLauncher -Destination $launcher
            }
            $committed = $true
        } finally {
            if (-not $committed) {
                Write-Host "Restoring previous installation. Backup: $backup"
                if ($Action -ne 'remove') {
                    if (-not (Test-Path -LiteralPath $nextLauncher) -and (Test-Path -LiteralPath $launcher)) { Remove-Item -LiteralPath $launcher -Force }
                    if (-not (Test-Path -LiteralPath $nextFolder) -and (Test-Path -LiteralPath $folder)) { Remove-Item -LiteralPath $folder -Recurse -Force }
                }
                if (Test-Path -LiteralPath $oldFolder) { Move-Item -LiteralPath $oldFolder -Destination $folder }
                if (Test-Path -LiteralPath $oldLauncher) { Move-Item -LiteralPath $oldLauncher -Destination $launcher }
            }
        }
        if ($Action -eq 'remove') { Write-Host 'Removed VTD.' }
        else { Write-Host 'VTD ready. Restart the launcher and enable it in a playset.' }
    } finally {
        $lock.Dispose()
        Remove-Item -LiteralPath $lockPath -Force
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
}

$vtdCode = 1
$vtdTranscript = $false
try {
    if (-not $env:VTD_LOG_FILE) { $env:VTD_LOG_FILE = Join-Path ([IO.Path]::GetTempPath()) ('vtd-installer-' + [guid]::NewGuid().ToString('N') + '.log') }
    Write-Host "VTD Windows installer (built-in PowerShell; no Python)`nLog file: $env:VTD_LOG_FILE"
    Start-Transcript -LiteralPath $env:VTD_LOG_FILE -Append | Out-Null
    $vtdTranscript = $true
    $vtdAction = ''
    $vtdDirectory = $env:VTD_MOD_DIR
    $vtdDryRun = $false
    $vtdHelp = $false
    for ($vtdIndex = 0; $vtdIndex -lt $args.Count; $vtdIndex++) {
        switch ($args[$vtdIndex]) {
            { $_ -in 'install', 'update', 'remove', 'status' } {
                if ($vtdAction) { throw 'Choose one operation only.' }
                $vtdAction = $_; break
            }
            '--mod-dir' {
                $vtdIndex++
                if ($vtdIndex -ge $args.Count) { throw '--mod-dir requires a path.' }
                $vtdDirectory = $args[$vtdIndex]; break
            }
            '--dry-run' { $vtdDryRun = $true; break }
            '--menu' { break }
            '--generate' { throw 'Windows installation uses checked-in generated assets. Regenerate using the Python developer tools, or git pull --ff-only for published assets.' }
            { $_ -in '--help', '-h' } { $vtdHelp = $true; break }
            default { throw "Unknown argument: $_" }
        }
    }
    if ($vtdHelp) {
        Write-Host 'vtd.cmd [install|update|remove|status] [--mod-dir PATH] [--dry-run]'
        Write-Host 'No command opens the menu. Update copies local files; run git pull --ff-only first for remote changes.'
    } else {
        if (-not $vtdDirectory) {
            $vtdDocuments = [Environment]::GetFolderPath('MyDocuments')
            if (-not $vtdDocuments) { $vtdDocuments = Join-Path $env:USERPROFILE 'Documents' }
            $vtdDirectory = Join-Path $vtdDocuments 'Paradox Interactive/Victoria 3/mod'
        }
        if (-not $vtdAction) {
            Write-Host "Mod directory: $vtdDirectory"
            Write-Host "1 Install / 安装`n2 Update local copy / 更新`n3 Remove / 移除`n4 Status / 状态`n0 Exit / 退出"
            $vtdChoice = Read-Host 'Choose / 选择'
            if ($vtdChoice -eq '0') { $vtdAction = 'exit' }
            else {
                $vtdActions = @{ '1' = 'install'; '2' = 'update'; '3' = 'remove'; '4' = 'status' }
                if (-not $vtdActions.ContainsKey($vtdChoice)) { throw 'Choose 0, 1, 2, 3 or 4.' }
                $vtdAction = $vtdActions[$vtdChoice]
            }
        }
        if ($vtdAction -ne 'exit') { Invoke-VtdManage $vtdAction $vtdDirectory $vtdDryRun }
    }
    $vtdCode = 0
} catch {
    Write-Host "VTD ERROR: $($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace
} finally {
    Write-Host "VTD exit code: $vtdCode"
    if ($vtdTranscript) { Stop-Transcript | Out-Null }
}
exit $vtdCode
