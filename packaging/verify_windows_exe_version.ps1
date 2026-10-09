# Check the PE version resource in both frozen Windows entry points.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Bundle,
    [Parameter(Mandatory)][string]$ExpectedVersion
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($ExpectedVersion -notmatch '^[0-9]+(\.[0-9]+){0,3}$') {
    throw "ExpectedVersion must have one to four ASCII numeric parts: $ExpectedVersion"
}
$parts = @($ExpectedVersion.Split('.') | ForEach-Object { [int]$_ })
if (@($parts | Where-Object { $_ -gt 65535 }).Count) {
    throw "ExpectedVersion part exceeds 65535: $ExpectedVersion"
}
$fixed = @(0, 0, 0, 0)
for ($i = 0; $i -lt $parts.Count; $i++) { $fixed[$i] = $parts[$i] }
$expectedFixed = $fixed -join '.'

foreach ($name in @('ingetrazo.exe', 'ingetrazo-mcp.exe')) {
    $path = Join-Path $Bundle $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing frozen executable: $path"
    }
    $info = (Get-Item -LiteralPath $path).VersionInfo
    $fileFixed = @($info.FileMajorPart, $info.FileMinorPart,
                   $info.FileBuildPart, $info.FilePrivatePart) -join '.'
    $productFixed = @($info.ProductMajorPart, $info.ProductMinorPart,
                      $info.ProductBuildPart, $info.ProductPrivatePart) -join '.'
    if ($info.FileVersion -ne $ExpectedVersion -or
        $info.ProductVersion -ne $ExpectedVersion -or
        $fileFixed -ne $expectedFixed -or
        $productFixed -ne $expectedFixed -or
        $info.ProductName -ne 'IngeTrazo' -or
        $info.OriginalFilename -ne $name -or
        [string]::IsNullOrWhiteSpace($info.FileDescription)) {
        throw "Incorrect PE version resource in $name`: file=$($info.FileVersion), product=$($info.ProductVersion), fixed=$fileFixed/$productFixed, name=$($info.ProductName), original=$($info.OriginalFilename)"
    }
    Write-Output "$name`: IngeTrazo $ExpectedVersion ($($info.FileDescription))"
}
