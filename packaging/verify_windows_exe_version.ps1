# Check the PE version resource in both frozen Windows entry points.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Bundle,
    [Parameter(Mandatory)][string]$ExpectedVersion
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

foreach ($name in @('ingetrazo.exe', 'ingetrazo-mcp.exe')) {
    $path = Join-Path $Bundle $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing frozen executable: $path"
    }
    $info = (Get-Item -LiteralPath $path).VersionInfo
    if ($info.FileVersion -ne $ExpectedVersion -or
        $info.ProductVersion -ne $ExpectedVersion -or
        $info.ProductName -ne 'IngeTrazo' -or
        $info.OriginalFilename -ne $name -or
        [string]::IsNullOrWhiteSpace($info.FileDescription)) {
        throw "Incorrect PE version resource in $name`: file=$($info.FileVersion), product=$($info.ProductVersion), name=$($info.ProductName), original=$($info.OriginalFilename)"
    }
    Write-Output "$name`: IngeTrazo $ExpectedVersion ($($info.FileDescription))"
}
