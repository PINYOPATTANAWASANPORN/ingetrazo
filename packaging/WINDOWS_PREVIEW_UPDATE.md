# Windows preview update transaction

`update_windows_preview.ps1` replaces the frozen `_internal` runtime and the
two executables in an existing portable preview. It is separate from the
public Inno Setup installer. Use a copied installation in a workspace first;
do not treat this script or its fixture tests as approval to distribute or
install a new preview.

The script requires a staged one-dir bundle and its JSON build manifest. It
checks the old and new executable hashes, source file count, and absence of
reparse points. It refuses a running app or MCP bridge at the target. It then
copies the entire target into a new backup snapshot and compares SHA-256 for
every file. Only after that does it stage and activate the runtime,
executables, and `BUILD-INFO.json`. The activated application must pass
`--check` within 30 seconds. A failure at any activation point restores the
old files and verifies the complete target manifest against the snapshot.
The script retains the immutable snapshot and failed candidate for inspection.

Example fixture invocation (PowerShell, with paths adjusted to the machine):

```powershell
$root = 'C:\path\to\workspace\updater-fixture'
New-Item -ItemType Directory -Path $root | Out-Null
Copy-Item -LiteralPath 'C:\Program Files\IngeTrazo' -Destination (Join-Path $root 'active') -Recurse
& .\packaging\update_windows_preview.ps1 `
  -SourceBundle 'C:\path\to\staged\ingetrazo' `
  -BuildManifest 'C:\path\to\build.json' `
  -TargetBundle (Join-Path $root 'active') `
  -WorkspaceRoot $root `
  -BackupDirectory (Join-Path $root 'backup')
```

For a rollback drill, add `-InjectFailureAfter internal`, `app`, `mcp`,
`metadata`, `check`, or `cleanup` and inspect `backup\report.json`. An injected failure
intentionally exits with an error even if rollback succeeds. Backups are
never overwritten; the caller must choose a fresh backup path for each run.
An already-current target is verified and returned without writing or
creating a backup.

`C:\Program Files\IngeTrazo` can be targeted only with the exact path,
`-AllowProgramFiles`, an Administrator token, no failure injection, and a
stopped app and MCP bridge. The backup must be a new direct child of a real
workspace directory on the same volume. This production mode remains
**untested**; the previous installation must be kept until frozen GUI
document workflows and the release review pass. This script does not replace
or test Inno Setup's install/uninstall behavior.
