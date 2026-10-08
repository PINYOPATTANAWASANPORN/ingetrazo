# Update the portable Windows preview bundle with a verified backup and rollback.
# Use a disposable target under WorkspaceRoot first. Program Files needs an
# explicit switch, an Administrator token, and a stopped app and MCP bridge.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceBundle,
    [Parameter(Mandatory)][string]$BuildManifest,
    [Parameter(Mandatory)][string]$TargetBundle,
    [Parameter(Mandatory)][string]$WorkspaceRoot,
    [Parameter(Mandatory)][string]$BackupDirectory,
    [switch]$AllowProgramFiles,
    [ValidateSet('none', 'internal', 'app', 'mcp', 'metadata', 'check')]
    [string]$InjectFailureAfter = 'none'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
}

function Is-Child([string]$Path, [string]$Parent) {
    return (FullPath $Path).StartsWith(
        (FullPath $Parent) + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-TargetPath([string]$Path) {
    if (-not (Is-Child $Path $target)) { throw "Path outside target: $Path" }
}

function Assert-BackupPath([string]$Path) {
    if (-not (Is-Child $Path $backup)) { throw "Path outside backup: $Path" }
}

function Move-Checked([string]$From, [string]$To) {
    if (-not ((Is-Child $From $target) -or (Is-Child $From $backup))) {
        throw "Unsafe move source: $From"
    }
    if (-not ((Is-Child $To $target) -or (Is-Child $To $backup))) {
        throw "Unsafe move destination: $To"
    }
    Move-Item -LiteralPath $From -Destination $To -ErrorAction Stop
}

function FileManifest([string]$Directory) {
    $root = FullPath $Directory
    $prefix = $root + [System.IO.Path]::DirectorySeparatorChar
    return @(
        Get-ChildItem -LiteralPath $root -Recurse -File -Force |
            ForEach-Object {
                "$($_.FullName.Substring($prefix.Length).Replace('\', '/'))`t$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
            } | Sort-Object -CaseSensitive
    )
}

function Assert-Same([string[]]$Expected, [string[]]$Actual, [string]$Label) {
    if (@(Compare-Object -ReferenceObject $Expected -DifferenceObject $Actual -CaseSensitive).Count) {
        throw "File manifest mismatch: $Label"
    }
}

function Assert-Hash([string]$Path, [string]$Expected) {
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw "SHA-256 mismatch: $Path"
    }
}

function Assert-NoReparse([string]$Directory, [switch]$RootOnly) {
    if ((Get-Item -LiteralPath $Directory -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Reparse point is not allowed: $Directory"
    }
    if (-not $RootOnly -and @(Get-ChildItem -LiteralPath $Directory -Recurse -Force -Attributes ReparsePoint).Count) {
        throw "Bundle contains a reparse point: $Directory"
    }
}

function Assert-NotRunning([string]$Directory) {
    $executables = @(
        (Join-Path $Directory 'ingetrazo.exe'),
        (Join-Path $Directory 'ingetrazo-mcp.exe')
    )
    $running = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and ($executables -contains $_.ExecutablePath)
    })
    if ($running.Count) {
        throw "Close the app and MCP bridge using this target before updating: $Directory"
    }
}

$source = FullPath $SourceBundle
$manifestPath = FullPath $BuildManifest
$target = FullPath $TargetBundle
$workspace = FullPath $WorkspaceRoot
$backup = FullPath $BackupDirectory
$programFilesTarget = 'C:\Program Files\IngeTrazo'

if (-not (Test-Path -LiteralPath $workspace -PathType Container)) { throw "Missing workspace: $workspace" }
if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Missing source: $source" }
if (-not (Test-Path -LiteralPath $target -PathType Container)) { throw "Missing target: $target" }
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Missing manifest: $manifestPath" }
Assert-NoReparse $workspace -RootOnly
Assert-NoReparse $source
Assert-NoReparse $target
if ($source -eq $target -or (Is-Child $target $source) -or (Is-Child $source $target)) {
    throw 'Source and target must be separate directories.'
}
if ((FullPath ([System.IO.Path]::GetDirectoryName($backup))) -ne $workspace) {
    throw 'Backup must be a new direct child of the workspace.'
}
if (Test-Path -LiteralPath $backup) { throw "Backup path already exists: $backup" }
if ((Is-Child $backup $source) -or (Is-Child $backup $target)) {
    throw 'Backup cannot be inside the source or target.'
}
if ([System.IO.Path]::GetPathRoot($backup) -ne [System.IO.Path]::GetPathRoot($target)) {
    throw 'Backup and target must be on the same volume.'
}
if ($target -eq $programFilesTarget) {
    if (-not $AllowProgramFiles) { throw 'Program Files requires -AllowProgramFiles.' }
    if ($InjectFailureAfter -ne 'none') { throw 'Failure injection is unavailable for Program Files.' }
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw 'Administrator token is required for Program Files.' }
} else {
    if ($AllowProgramFiles) { throw '-AllowProgramFiles requires the exact IngeTrazo Program Files path.' }
    if (-not (Is-Child $target $workspace) -or
        (FullPath ([System.IO.Path]::GetDirectoryName($target))) -ne $workspace) {
        throw 'Test target must be a direct child of the workspace.'
    }
}

$info = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$oldInfo = Get-Content -LiteralPath (Join-Path $target 'BUILD-INFO.json') -Raw | ConvertFrom-Json
Assert-Hash (Join-Path $source 'ingetrazo.exe') $info.app_sha256
Assert-Hash (Join-Path $source 'ingetrazo-mcp.exe') $info.mcp_sha256
Assert-Hash (Join-Path $target 'ingetrazo.exe') $oldInfo.main_sha256
Assert-Hash (Join-Path $target 'ingetrazo-mcp.exe') $oldInfo.mcp_sha256
$sourceFiles = @(FileManifest $source)
if ($sourceFiles.Count -ne [int]$info.file_count) { throw 'Source file count differs from build manifest.' }
if (-not (Test-Path -LiteralPath (Join-Path $source '_internal') -PathType Container)) {
    throw 'Source runtime is missing.'
}
foreach ($name in @('_internal.next', '_internal.previous', 'ingetrazo.next.exe',
        'ingetrazo.previous.exe', 'ingetrazo-mcp.next.exe', 'ingetrazo-mcp.previous.exe',
        'BUILD-INFO.next.json', 'BUILD-INFO.previous.json')) {
    if (Test-Path -LiteralPath (Join-Path $target $name)) {
        throw "Target has an unfinished update: $name"
    }
}
if ($oldInfo.source_commit -eq $info.source_commit -and
    $oldInfo.main_sha256 -eq $info.app_sha256 -and
    $oldInfo.mcp_sha256 -eq $info.mcp_sha256) {
    Assert-Same @(FileManifest (Join-Path $source '_internal')) @(
        FileManifest (Join-Path $target '_internal')) 'already-current runtime'
    Write-Output (@{
        result = 'already_current'
        source_commit = $info.source_commit
        target = $target
        backup_created = $false
    } | ConvertTo-Json)
    return
}
Assert-NotRunning $target

$before = @(FileManifest $target)
New-Item -ItemType Directory -Path $backup | Out-Null
$snapshot = Join-Path $backup 'snapshot'
$failed = Join-Path $backup 'failed-candidate'
$replaced = Join-Path $backup 'replaced-originals'
foreach ($path in @($snapshot, $failed, $replaced)) { Assert-BackupPath $path }
Copy-Item -LiteralPath $target -Destination $snapshot -Recurse -Force
New-Item -ItemType Directory -Path $failed, $replaced | Out-Null
Assert-Same $before @(FileManifest $snapshot) 'backup snapshot'

$components = @(
    @{ Name = '_internal'; Next = '_internal.next'; Previous = '_internal.previous'; Inject = 'internal' },
    @{ Name = 'ingetrazo.exe'; Next = 'ingetrazo.next.exe'; Previous = 'ingetrazo.previous.exe'; Inject = 'app' },
    @{ Name = 'ingetrazo-mcp.exe'; Next = 'ingetrazo-mcp.next.exe'; Previous = 'ingetrazo-mcp.previous.exe'; Inject = 'mcp' },
    @{ Name = 'BUILD-INFO.json'; Next = 'BUILD-INFO.next.json'; Previous = 'BUILD-INFO.previous.json'; Inject = 'metadata' }
)
$activated = @()
$checkExit = $null
$failure = $null
$rollbackFailure = $null
try {
    $runtimeNext = Join-Path $target '_internal.next'
    Assert-TargetPath $runtimeNext
    Copy-Item -LiteralPath (Join-Path $source '_internal') -Destination $runtimeNext -Recurse -Force
    Assert-Same @(FileManifest (Join-Path $source '_internal')) @(FileManifest $runtimeNext) 'staged runtime'
    foreach ($item in @(
        @{ Source = 'ingetrazo.exe'; Next = 'ingetrazo.next.exe'; Hash = $info.app_sha256 },
        @{ Source = 'ingetrazo-mcp.exe'; Next = 'ingetrazo-mcp.next.exe'; Hash = $info.mcp_sha256 }
    )) {
        $nextPath = Join-Path $target $item.Next
        Assert-TargetPath $nextPath
        Copy-Item -LiteralPath (Join-Path $source $item.Source) -Destination $nextPath -Force
        Assert-Hash $nextPath $item.Hash
    }
    $newInfo = [ordered]@{
        source_commit = $info.source_commit
        branch = $info.branch
        installed_at = (Get-Date).ToUniversalTime().ToString('o')
        main_sha256 = $info.app_sha256
        mcp_sha256 = $info.mcp_sha256
        bundle_check = 'passed'
    }
    $newInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $target 'BUILD-INFO.next.json') -Encoding UTF8
    foreach ($component in $components) {
        $current = Join-Path $target $component.Name
        $previous = Join-Path $target $component.Previous
        $next = Join-Path $target $component.Next
        Move-Checked $current $previous
        $activated += $component
        Move-Checked $next $current
        if ($InjectFailureAfter -eq $component.Inject) {
            throw "INJECTED_FAILURE_AFTER_$($component.Inject)"
        }
    }
    Assert-Hash (Join-Path $target 'ingetrazo.exe') $info.app_sha256
    Assert-Hash (Join-Path $target 'ingetrazo-mcp.exe') $info.mcp_sha256
    Assert-Same @(FileManifest (Join-Path $source '_internal')) @(FileManifest (Join-Path $target '_internal')) 'activated runtime'
    $process = Start-Process -FilePath (Join-Path $target 'ingetrazo.exe') -ArgumentList '--check' -WorkingDirectory $target -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(30000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw 'Activated app self-check timed out.'
    }
    $checkExit = $process.ExitCode
    if ($checkExit -ne 0) { throw "Activated app self-check failed: $checkExit" }
    if ($InjectFailureAfter -eq 'check') { throw 'INJECTED_FAILURE_AFTER_check' }
    foreach ($component in $components) {
        Move-Checked (Join-Path $target $component.Previous) (Join-Path $replaced $component.Name)
    }
} catch {
    $failure = $_.Exception.Message
    try {
        [array]::Reverse($activated)
        foreach ($component in $activated) {
            $current = Join-Path $target $component.Name
            $previous = Join-Path $target $component.Previous
            if (Test-Path -LiteralPath $current) {
                Move-Checked $current (Join-Path $failed $component.Name)
            }
            if (Test-Path -LiteralPath $previous) {
                Move-Checked $previous $current
            } else {
                Copy-Item -LiteralPath (Join-Path $snapshot $component.Name) -Destination $current -Recurse -Force
            }
        }
        foreach ($component in $components) {
            $next = Join-Path $target $component.Next
            if (Test-Path -LiteralPath $next) { Move-Checked $next (Join-Path $failed $component.Next) }
        }
        Assert-Same $before @(FileManifest $target) 'restored target'
        Assert-Same $before @(FileManifest $snapshot) 'unchanged backup snapshot'
    } catch {
        $rollbackFailure = $_.Exception.Message
    }
}

$report = [ordered]@{
    schema_version = 1
    tested_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    mode = if ($target -eq $programFilesTarget) { 'program_files' } else { 'workspace_fixture' }
    source_commit = $info.source_commit
    prior_commit = $oldInfo.source_commit
    source_file_count = $sourceFiles.Count
    prior_file_count = $before.Count
    injected_failure_after = $InjectFailureAfter
    self_check_exit = $checkExit
    result = if ($null -eq $failure) { 'updated' } elseif ($null -eq $rollbackFailure) { 'rolled_back' } else { 'rollback_failed' }
    error = $failure
    rollback_error = $rollbackFailure
    target = $target
    backup_snapshot = $snapshot
}
$reportPath = Join-Path $backup 'report.json'
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $reportPath -Encoding UTF8
if ($null -ne $failure) {
    throw "Update failed: $failure; rollback status: $($report.result); report: $reportPath"
}
Assert-Hash (Join-Path $target 'ingetrazo.exe') $info.app_sha256
Assert-Hash (Join-Path $target 'ingetrazo-mcp.exe') $info.mcp_sha256
Write-Output ($report | ConvertTo-Json -Depth 4)
