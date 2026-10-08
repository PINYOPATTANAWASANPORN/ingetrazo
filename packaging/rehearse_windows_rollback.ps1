# Rehearse a frozen-bundle replacement and rollback in a disposable workspace.
# This script never writes to InstalledBundle or StagedBundle.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InstalledBundle,
    [Parameter(Mandatory)][string]$StagedBundle,
    [Parameter(Mandatory)][string]$StagedManifest,
    [Parameter(Mandatory)][string]$WorkspaceRoot,
    [Parameter(Mandatory)][string]$EvidenceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
}

function Assert-ChildPath([string]$Path, [string]$Root) {
    $parent = FullPath $Root
    $child = FullPath $Path
    $prefix = $parent + [System.IO.Path]::DirectorySeparatorChar
    if (-not $child.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to mutate a path outside the workspace: $child"
    }
}

function FileManifest([string]$Directory) {
    $root = FullPath $Directory
    $prefix = $root + [System.IO.Path]::DirectorySeparatorChar
    return @(
        Get-ChildItem -LiteralPath $root -Recurse -File -Force |
            ForEach-Object {
                $relative = $_.FullName.Substring($prefix.Length).Replace('\', '/')
                "$relative`t$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)"
            } | Sort-Object -CaseSensitive
    )
}

function Assert-SameManifest([string[]]$Expected, [string[]]$Actual, [string]$Label) {
    $delta = @(Compare-Object -ReferenceObject $Expected -DifferenceObject $Actual -CaseSensitive)
    if ($delta.Count -ne 0) {
        throw "$Label differs from the installed bundle ($($delta.Count) manifest entries)."
    }
}

function Assert-Hash([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($actual -ne $Expected) { throw "SHA-256 mismatch: $Path" }
}

function Move-InFixture([string]$Source, [string]$Destination) {
    Assert-ChildPath $Source $workspace
    Assert-ChildPath $Destination $workspace
    Move-Item -LiteralPath $Source -Destination $Destination
}

$workspace = FullPath $WorkspaceRoot
$evidence = FullPath $EvidenceDirectory
$installed = FullPath $InstalledBundle
$staged = FullPath $StagedBundle
$manifestPath = FullPath $StagedManifest
Assert-ChildPath $evidence $workspace
if (Test-Path -LiteralPath $evidence) { throw "Evidence directory already exists: $evidence" }
foreach ($path in @($installed, $staged)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Missing bundle: $path" }
    if ($evidence.StartsWith($path + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Evidence directory cannot be inside a source bundle: $path"
    }
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Missing staged manifest: $manifestPath" }

$installedInfo = Get-Content -LiteralPath (Join-Path $installed 'BUILD-INFO.json') -Raw | ConvertFrom-Json
$stagedInfo = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
Assert-Hash (Join-Path $installed 'ingetrazo.exe') $installedInfo.main_sha256
Assert-Hash (Join-Path $installed 'ingetrazo-mcp.exe') $installedInfo.mcp_sha256
Assert-Hash (Join-Path $staged 'ingetrazo.exe') $stagedInfo.app_sha256
Assert-Hash (Join-Path $staged 'ingetrazo-mcp.exe') $stagedInfo.mcp_sha256

$sourceManifest = @(FileManifest $installed)
$stagedFiles = @(FileManifest $staged)
if ($stagedFiles.Count -ne [int]$stagedInfo.file_count) {
    throw "Staged file count differs from build manifest: $($stagedFiles.Count)"
}

New-Item -ItemType Directory -Path $evidence | Out-Null
$active = Join-Path $evidence 'active'
$backup = Join-Path $evidence 'backup'
$failed = Join-Path $evidence 'failed-activation'
foreach ($path in @($active, $backup, $failed)) { Assert-ChildPath $path $workspace }
Copy-Item -LiteralPath $installed -Destination $active -Recurse -Force
Copy-Item -LiteralPath $installed -Destination $backup -Recurse -Force
New-Item -ItemType Directory -Path $failed | Out-Null
Assert-SameManifest $sourceManifest (FileManifest $active) 'Active fixture copy'
Assert-SameManifest $sourceManifest (FileManifest $backup) 'Backup fixture copy'

Copy-Item -LiteralPath (Join-Path $staged '_internal') -Destination (Join-Path $active '_internal.next') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $staged 'ingetrazo.exe') -Destination (Join-Path $active 'ingetrazo.next.exe') -Force
Copy-Item -LiteralPath (Join-Path $staged 'ingetrazo-mcp.exe') -Destination (Join-Path $active 'ingetrazo-mcp.next.exe') -Force
Assert-Hash (Join-Path $active 'ingetrazo.next.exe') $stagedInfo.app_sha256
Assert-Hash (Join-Path $active 'ingetrazo-mcp.next.exe') $stagedInfo.mcp_sha256

$components = @(
    @{ Name = '_internal'; Next = '_internal.next'; Previous = '_internal.previous' },
    @{ Name = 'ingetrazo.exe'; Next = 'ingetrazo.next.exe'; Previous = 'ingetrazo.previous.exe' },
    @{ Name = 'ingetrazo-mcp.exe'; Next = 'ingetrazo-mcp.next.exe'; Previous = 'ingetrazo-mcp.previous.exe' }
)
$activated = @()
$selfCheckExit = $null
$injectedFailureSeen = $false
$rollbackError = $null
try {
    foreach ($component in $components) {
        $current = Join-Path $active $component.Name
        $previous = Join-Path $active $component.Previous
        $next = Join-Path $active $component.Next
        Move-InFixture $current $previous
        # Track this component before activating it so partial swaps roll back too.
        $activated += $component
        Move-InFixture $next $current
    }
    Assert-Hash (Join-Path $active 'ingetrazo.exe') $stagedInfo.app_sha256
    Assert-Hash (Join-Path $active 'ingetrazo-mcp.exe') $stagedInfo.mcp_sha256
    $process = Start-Process -FilePath (Join-Path $active 'ingetrazo.exe') -ArgumentList '--check' -WorkingDirectory $active -Wait -PassThru -WindowStyle Hidden
    $selfCheckExit = $process.ExitCode
    if ($selfCheckExit -ne 0) { throw "Activated bundle self-check failed: $selfCheckExit" }
    throw 'INJECTED_FAILURE_AFTER_ACTIVATION'
} catch {
    if ($_.Exception.Message -eq 'INJECTED_FAILURE_AFTER_ACTIVATION') {
        $injectedFailureSeen = $true
    } else {
        $rollbackError = $_.Exception.Message
    }
} finally {
    # Preserve the failed candidate for inspection; restore every original path.
    [array]::Reverse($activated)
    foreach ($component in $activated) {
        $current = Join-Path $active $component.Name
        $previous = Join-Path $active $component.Previous
        $next = Join-Path $active $component.Next
        if (Test-Path -LiteralPath $current) {
            Move-InFixture $current (Join-Path $failed $component.Name)
        }
        if (Test-Path -LiteralPath $previous) { Move-InFixture $previous $current }
        if (Test-Path -LiteralPath $next) { Move-InFixture $next (Join-Path $failed $component.Next) }
    }
    foreach ($component in $components) {
        $next = Join-Path $active $component.Next
        if (Test-Path -LiteralPath $next) { Move-InFixture $next (Join-Path $failed $component.Next) }
    }
}

$restoredManifest = FileManifest $active
$backupManifest = FileManifest $backup
Assert-SameManifest $sourceManifest $restoredManifest 'Restored active fixture'
Assert-SameManifest $backupManifest $restoredManifest 'Restored fixture versus backup'
Assert-SameManifest $sourceManifest (FileManifest $installed) 'Read-only installed source after rehearsal'
Assert-SameManifest $stagedFiles (FileManifest $staged) 'Read-only staged source after rehearsal'
if ($null -ne $rollbackError) { throw "Swap failed before injected failure: $rollbackError" }
if (-not $injectedFailureSeen) { throw 'Injected failure was not observed.' }

$report = [ordered]@{
    schema_version = 1
    tested_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_installed_bundle = $installed
    source_staged_bundle = $staged
    installed_source_commit = $installedInfo.source_commit
    staged_source_commit = $stagedInfo.source_commit
    installed_file_count = $sourceManifest.Count
    staged_file_count = $stagedFiles.Count
    staged_self_check_exit = $selfCheckExit
    injected_failure_observed = $injectedFailureSeen
    restored_manifest_matches_installed = $true
    restored_manifest_matches_backup = $true
    installed_source_unchanged = $true
    staged_source_unchanged = $true
    fixture_directory = $evidence
    scope = 'Disposable workspace fixture only; installed Program Files bundle was not modified.'
}
$reportPath = Join-Path $evidence 'report.json'
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Output ($report | ConvertTo-Json -Depth 4)
