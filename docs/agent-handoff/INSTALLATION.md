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
