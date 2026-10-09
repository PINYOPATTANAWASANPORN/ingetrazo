# Verified local Windows installation

On 2026-10-06 (Asia/Bangkok), the Windows 10 x64 installation at
`C:\Program Files\IngeTrazo` was updated from the stacked branch
`feature/ai-cross-provider-review` at code commit
`b0dce0f7d483d8eeca1a3788d8aa286a8e18bde2`. The build includes the
Windows PyInstaller fix in that commit. The original installation was copied
to a separate workspace backup before replacement and remains available for
rollback. User settings outside the install directory were not changed.

| Artifact | Installed SHA-256 |
| --- | --- |
| `ingetrazo.exe` | `65176134443C6BB7EA152841E46E5467DF685D6317C483E0F62C0861E31982A2` |
| `ingetrazo-mcp.exe` | `09F687096E4B398ADAEA89E81D396778EA67ACF86FDE55CB3A931A3FD830BB4B` |

The installed `BUILD-INFO.json` records the commit, hashes, and UTC install
time (`2026-10-05T22:09:40.8710750Z`). Independent verification found both
hashes equal to the build manifest, 823 runtime files in `_internal`, no
foreign `icuuc.dll`, `ingetrazo.exe --check` exit code 0, an opened GUI window
named `IngeTrazo — Untitled`, and 22 MCP tools from `tools/list` (including
the specialist review and audit tools). This verifies local packaging and
startup, not complete feature behavior or real-provider model quality.

The first build failed at startup because PyInstaller collected a Poppler
`icuuc.dll` from the build environment's PATH. Its versioned exports were
incompatible with the unversioned ICU imports of Qt6Core. The installer
rolled back to the original files. The fix in `ingetrazo.spec` excludes that
foreign ICU pair on Windows; rebuilding and retesting `--check` passed before
installation. The MCP executable was staged and renamed during deployment
because an active MCP client can immediately restart and lock the old image.

For future deployments, build with `python -m PyInstaller --noconfirm --clean
ingetrazo.spec`, test the **frozen** `dist/ingetrazo/ingetrazo.exe --check`
and MCP `tools/list`, retain a separate copy of the installed directory, then
verify the installed-path hashes, self-check, and GUI. A successful PyInstaller
exit alone is insufficient. The local installer and build manifest used for
this deployment are in the workspace root as `install-latest-b0dce0f.ps1`
and `build-latest-b0dce0f.json`.

## Installed build with the AI tray UI fix

On 2026-10-06 a new Windows bundle was built from `b2573b7` on
`fix/ai-assistant-review-controls`. Its frozen `--check` passed and the MCP
executable returned 22 tools. SHA-256: main
`C7B365032C35EA2CBF675E3F6A78E1E56C933157DF67CC3E8BE6DA409CE92959`,
MCP `287125D075FB34C7A6D7AC879BBCD49AAEC918C21E5F8FDC15960EBD6B617937`.
The manifest and rollback-capable installer are in the workspace root as
`build-latest-b2573b7.json` and `install-latest-b2573b7.ps1`. A separate
backup of the previous installation was verified at
`backups/IngeTrazo-installed-before-20261006-pr47`. After the open GUI was
saved and closed, the installer completed successfully at 05:51 on 2026-10-06
(Asia/Bangkok). Independent installed-path checks confirmed both executable
hashes, 823 runtime files, `ingetrazo.exe --check` exit 0, and 22 MCP tools.
The GUI was not relaunched during this verification; actual display of the
new tray layout remains a manual visual check on next launch.

## Full-width row refinement installed

On 2026-10-06 at 06:07 (Asia/Bangkok), build `3815ef8` replaced the prior
`b2573b7` installation after a verified backup to
`backups/IngeTrazo-installed-before-20261006-rowfix`. This build gives
Export review its own row and places suggestions in full-width rows. The
manifest and rollback-capable installer are `build-latest-3815ef8.json` and
`install-latest-3815ef8.ps1` in the workspace root. The installed executable
hashes match the manifest: main
`0F6B8364DA2084D67A374F1A318E2116913995D4732C85D88BC80846BA6D4937`,
MCP `141905CFE38CC9545610EBBE3DB9308D9C6D52867EEDB414CE40601F5710AE66`.
Independent installed-path checks found 823 runtime files, `--check` exit 0,
and 22 MCP tools. The GUI was not relaunched for visual verification.

## Newer staged build, not installed

On 2026-10-06, `test/windows-qt-integration-gates` at `d70e782` was built into
the ignored `dist/ingetrazo` directory. The frozen main executable passed
`--check`, and the frozen MCP executable returned 22 tools. Main and MCP
SHA-256 values and test limits are recorded in
[`WINDOWS_QT_INTEGRATION_GATE.md`](WINDOWS_QT_INTEGRATION_GATE.md).
`C:\Program Files\IngeTrazo` still contains the older verified `3815ef8`
build. The new bundle has not been deployed.

On 2026-10-07 a separate cumulative bundle from `7ebc770` (draft PR #63)
was staged at `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-qt-7ebc770\ingetrazo`.
PyInstaller exited 0, its frozen `ingetrazo.exe --check` exited 0, the frozen
MCP executable listed 22 tools, and the GUI process survived a ten-second
offscreen startup check. The bundle contains 819 files. SHA-256 values and
the exact bundle path are in the workspace-root `build-staged-7ebc770.json`.
The installed main executable still matches the recorded `3815ef8` hash.
This staged build has **not** replaced the installation or received a visible
interactive GUI check.

On 2026-10-08, a cumulative bundle from draft PR #82 at `31ae5b7c` was
staged separately at `C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-pr82\ingetrazo`.
The frozen app passed `--check`, its MCP executable listed 22 tools, and an
offscreen GUI process stayed alive for ten seconds. Hashes and file count are
recorded in the workspace-root `build-staged-pr82.json` and
`INTEGRATION_CHECKPOINT_2026-10-08.md`. This remains a **staged test build**;
the installed application is still the verified `3815ef8` build.

## PR #95 staged preview and update rehearsal (2026-10-09)

The clean `perf/igz-flat-pick-triangles` tree at `7e4becf` was frozen into
`C:\Users\Lenovo\Desktop\IngeTrazoTest\dist-pr95-gate\ingetrazo` (874 files).
The workspace-root `build-pr95-gate.json` records the exact source commit,
file count and executable SHA-256 values. The app hash is
`C2A50CECD8053BB7FC8C425E28F50D02CB59A94B25426A24A726FEC2C9B60B22`;
the MCP hash is
`57D7B6AD96F84F23C9DFDC2A9575BE80DF924A9BAB5C2BA66A06F2C802A7E81A`.
Frozen `--check` exited 0, MCP `tools/list` returned 22 tools, both Windows
executables reported version 0.5.7, and the notice verifier matched 43 wheel
metadata/license files plus project/OpenSKP notices.

The frozen document probe passed offscreen open/edit/save/reopen/Undo/Redo on
`sofa.igz` and a generated six-group nested fixture. A native Windows probe
passed the same workflow on `examples/arco-yanque.igz`, preserving all 30
groups and the original document hash. Reports are
`smoke-pr95-sofa.json`, `smoke-pr95-nested.json`, and
`smoke-pr95-arco-native.json` in the workspace root. These probes do not
validate visible pixels, physical pointer actions or every modelling/AI flow.

The updater was exercised only against a copied 832-file installation under
`updater-pr95-fixture`. A deliberate failure after cleanup returned
`rolled_back`, restored the original `3815ef8` commit and main executable
hash, and reported no rollback error. A following normal run returned
`updated` and passed its activated frozen self-check. Reports and retained
snapshots are under that fixture. The installed Program Files bundle is
**unchanged**. Four installed MCP processes were still running and this
session did not have an Administrator token. The hosted Windows release build,
visible interaction/pixel review, Qt/framework binary notice and fork identity
review, and actual elevated installation remain open gates.
